"""Capacity-constrained and auditable truck consolidation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import math
import re
from typing import Iterable, Mapping

from .models import (
    ConsolidationPolicy,
    ConsolidationResult,
    FallbackGroup,
    ItemLogisticsProfile,
    LoadAllocation,
    QuantifiedLine,
    ShipmentLine,
    TruckCapacity,
    TruckLoad,
)

EPSILON = 1e-9


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-") or "X"


def _profile_key(item_id: str, uom: str) -> tuple[str, str]:
    normalized_item = re.sub(r"^item:", "", item_id.strip(), flags=re.IGNORECASE)
    return normalized_item, uom.strip().upper()


def quantify_line(
    line: ShipmentLine,
    profiles: Mapping[tuple[str, str], ItemLogisticsProfile] | None,
    capacity: TruckCapacity,
) -> QuantifiedLine:
    """Quantify a line without converting unknown business units."""

    profile = (profiles or {}).get(_profile_key(line.item_id, line.uom))
    uom = line.uom.strip().upper()

    if line.explicit_weight_kg is not None:
        weight = line.explicit_weight_kg
        weight_basis = f"explicit:{line.physical_data_source}"
        weight_is_gross = True
    elif profile and profile.kg_per_unit is not None:
        weight = line.quantity * profile.kg_per_unit
        weight_basis = f"profile:{profile.source_reference}"
        weight_is_gross = True
    elif uom == "KG":
        weight = line.quantity
        weight_basis = "uom_definition:KG_to_net_kg"
        weight_is_gross = False
    elif uom == "G":
        weight = line.quantity / 1000.0
        weight_basis = "uom_definition:G_to_net_kg"
        weight_is_gross = False
    else:
        weight = None
        weight_basis = "unknown"
        weight_is_gross = False

    if line.explicit_pallets is not None:
        pallets = line.explicit_pallets
        pallets_basis = f"explicit:{line.physical_data_source}"
    elif profile and profile.pallets_per_unit is not None:
        pallets = line.quantity * profile.pallets_per_unit
        pallets_basis = f"profile:{profile.source_reference}"
    else:
        pallets = None
        pallets_basis = "unknown"

    if line.explicit_volume_m3 is not None:
        volume = line.explicit_volume_m3
        volume_basis = f"explicit:{line.physical_data_source}"
    elif profile and profile.volume_m3_per_unit is not None:
        volume = line.quantity * profile.volume_m3_per_unit
        volume_basis = f"profile:{profile.source_reference}"
    else:
        volume = None
        volume_basis = "unknown"

    missing: list[str] = []
    if weight is None or not weight_is_gross:
        missing.append("gross_weight_kg")
    if pallets is None:
        missing.append("pallets")
    if capacity.max_volume_m3 is not None and volume is None:
        missing.append("volume_m3")
    return QuantifiedLine(
        line=line,
        compatibility_group=(
            profile.compatibility_group
            if profile and line.compatibility_group == "default"
            else line.compatibility_group
        ),
        weight_kg=weight,
        weight_is_gross=weight_is_gross,
        pallets=pallets,
        volume_m3=volume,
        weight_basis=weight_basis,
        pallets_basis=pallets_basis,
        volume_basis=volume_basis,
        missing_dimensions=tuple(missing),
    )


@dataclass
class _MutableLoad:
    allocations: list[LoadAllocation] = field(default_factory=list)
    weight_kg: float = 0.0
    pallets: float = 0.0
    volume_m3: float = 0.0
    has_volume: bool = False

    def max_quantity_fit(self, row: QuantifiedLine, capacity: TruckCapacity) -> float:
        quantity = row.line.quantity
        weight_per_unit = float(row.weight_kg or 0.0) / quantity
        pallets_per_unit = float(row.pallets or 0.0) / quantity
        limits = [
            (capacity.max_weight_kg - self.weight_kg) / weight_per_unit,
            (capacity.max_pallets - self.pallets) / pallets_per_unit,
        ]
        if capacity.max_volume_m3 is not None:
            volume_per_unit = float(row.volume_m3 or 0.0) / quantity
            limits.append((capacity.max_volume_m3 - self.volume_m3) / volume_per_unit)
        return max(0.0, min(limits))

    def add(self, row: QuantifiedLine, quantity: float) -> None:
        ratio = quantity / row.line.quantity
        weight = float(row.weight_kg or 0.0) * ratio
        pallets = float(row.pallets or 0.0) * ratio
        volume = float(row.volume_m3 or 0.0) * ratio if row.volume_m3 is not None else None
        self.allocations.append(
            LoadAllocation(
                line_id=row.line.line_id,
                item_id=row.line.item_id,
                quantity=quantity,
                uom=row.line.uom,
                lot_id=row.line.lot_id,
                shipment_id=row.line.shipment_id,
                weight_kg=weight,
                pallets=pallets,
                volume_m3=volume,
            )
        )
        self.weight_kg += weight
        self.pallets += pallets
        if volume is not None:
            self.volume_m3 += volume
            self.has_volume = True


def _group_key(
    row: QuantifiedLine,
    policy: ConsolidationPolicy,
) -> tuple[str, str, str, str, str, int]:
    line = row.line
    item_key = line.item_id if not policy.mix_items else "*"
    return (
        line.origin_node_id,
        line.destination_node_id,
        line.mode,
        row.compatibility_group,
        item_key,
        policy.bucket_start(line.departure_day),
    )


def _dominant_ratio(row: QuantifiedLine, capacity: TruckCapacity) -> float:
    ratios = [
        float(row.weight_kg or 0.0) / capacity.max_weight_kg,
        float(row.pallets or 0.0) / capacity.max_pallets,
    ]
    if capacity.max_volume_m3 is not None:
        ratios.append(float(row.volume_m3 or 0.0) / capacity.max_volume_m3)
    return max(ratios)


def _build_loads(
    rows: list[QuantifiedLine],
    key: tuple[str, str, str, str, str, int],
    capacity: TruckCapacity,
    policy: ConsolidationPolicy,
) -> list[TruckLoad]:
    origin, destination, mode, compatibility, item_key, window_start = key
    mutable_loads: list[_MutableLoad] = []
    for row in sorted(rows, key=lambda item: (-_dominant_ratio(item, capacity), item.line.line_id)):
        remaining = row.line.quantity
        while remaining > EPSILON:
            target: _MutableLoad | None = None
            fit = 0.0
            for candidate in mutable_loads:
                candidate_fit = candidate.max_quantity_fit(row, capacity)
                if candidate_fit > fit + EPSILON:
                    target = candidate
                    fit = candidate_fit
            if target is None or fit <= EPSILON:
                target = _MutableLoad()
                mutable_loads.append(target)
                fit = target.max_quantity_fit(row, capacity)
            allocation_qty = min(remaining, fit)
            if allocation_qty <= EPSILON:
                raise ValueError(
                    f"Line {row.line.line_id} cannot fit into an empty {capacity.name}; "
                    "check physical conversion factors."
                )
            target.add(row, allocation_qty)
            remaining -= allocation_qty

    consolidation_day = max(row.line.departure_day for row in rows)
    loads: list[TruckLoad] = []
    group_slug = (
        f"{_slug(origin)}-{_slug(destination)}-"
        f"{_slug(mode)}-{_slug(compatibility)}-{_slug(item_key)}"
    )
    for index, load in enumerate(mutable_loads, start=1):
        volume_value = load.volume_m3 if load.has_volume else None
        loads.append(
            TruckLoad(
                load_id=f"TRK-{group_slug}-D{window_start:05d}-{index:03d}",
                origin_node_id=origin,
                destination_node_id=destination,
                mode=mode,
                compatibility_group=compatibility,
                window_start_day=window_start,
                window_end_day=window_start + policy.bucket_days - 1,
                consolidation_day=consolidation_day,
                weight_kg=load.weight_kg,
                pallets=load.pallets,
                volume_m3=volume_value,
                weight_utilization=load.weight_kg / capacity.max_weight_kg,
                pallet_utilization=load.pallets / capacity.max_pallets,
                volume_utilization=(
                    load.volume_m3 / capacity.max_volume_m3
                    if capacity.max_volume_m3 is not None
                    else None
                ),
                allocations=tuple(load.allocations),
            )
        )
    return loads


def _known_lower_bound(
    rows: list[QuantifiedLine],
    capacity: TruckCapacity,
) -> tuple[int, float, float, float, int, int, int]:
    weights = [row.weight_kg for row in rows if row.weight_kg is not None]
    pallets = [row.pallets for row in rows if row.pallets is not None]
    volumes = [row.volume_m3 for row in rows if row.volume_m3 is not None]
    weight_total = sum(float(value) for value in weights)
    pallet_total = sum(float(value) for value in pallets)
    volume_total = sum(float(value) for value in volumes)
    bounds = [
        math.ceil(weight_total / capacity.max_weight_kg) if weight_total > 0 else 0,
        math.ceil(pallet_total / capacity.max_pallets) if pallet_total > 0 else 0,
    ]
    if capacity.max_volume_m3 is not None and volume_total > 0:
        bounds.append(math.ceil(volume_total / capacity.max_volume_m3))
    return (
        max(bounds, default=0),
        weight_total,
        pallet_total,
        volume_total,
        len(weights),
        len(pallets),
        len(volumes),
    )


def _build_fallback(
    rows: list[QuantifiedLine],
    key: tuple[str, str, str, str, str, int],
    capacity: TruckCapacity,
    policy: ConsolidationPolicy,
) -> FallbackGroup:
    origin, destination, mode, compatibility, item_key, window_start = key
    quantities: dict[str, float] = defaultdict(float)
    item_quantities: dict[str, float] = defaultdict(float)
    for row in rows:
        normalized_uom = row.line.uom.strip().upper()
        quantities[normalized_uom] += row.line.quantity
        item_quantities[f"{row.line.item_id}|{normalized_uom}"] += row.line.quantity
    (
        lower_bound,
        known_weight,
        known_pallets,
        known_volume,
        weight_count,
        pallet_count,
        volume_count,
    ) = _known_lower_bound(rows, capacity)
    missing = sorted({dimension for row in rows for dimension in row.missing_dimensions})
    return FallbackGroup(
        group_id=(
            f"FB-{_slug(origin)}-{_slug(destination)}-{_slug(mode)}-"
            f"{_slug(compatibility)}-{_slug(item_key)}-D{window_start:05d}"
        ),
        origin_node_id=origin,
        destination_node_id=destination,
        mode=mode,
        compatibility_group=compatibility,
        window_start_day=window_start,
        window_end_day=window_start + policy.bucket_days - 1,
        consolidation_day=max(row.line.departure_day for row in rows),
        line_ids=tuple(sorted(row.line.line_id for row in rows)),
        lot_ids=tuple(sorted({row.line.lot_id for row in rows if row.line.lot_id})),
        shipment_ids=tuple(
            sorted({row.line.shipment_id for row in rows if row.line.shipment_id})
        ),
        item_ids=tuple(sorted({row.line.item_id for row in rows})),
        quantities_by_uom=dict(sorted(quantities.items())),
        quantities_by_item_uom=dict(sorted(item_quantities.items())),
        known_weight_kg=known_weight,
        weight_bases=tuple(sorted({row.weight_basis for row in rows})),
        known_pallets=known_pallets,
        known_volume_m3=known_volume,
        weight_known_line_count=weight_count,
        pallet_known_line_count=pallet_count,
        volume_known_line_count=volume_count,
        missing_dimensions=tuple(missing),
        known_capacity_lower_bound_trucks=lower_bound,
        basis=policy.fallback_basis,
    )


def consolidate_shipments(
    lines: Iterable[ShipmentLine],
    *,
    profiles: Iterable[ItemLogisticsProfile] = (),
    capacity: TruckCapacity | None = None,
    policy: ConsolidationPolicy | None = None,
) -> ConsolidationResult:
    """Consolidate physically known lines and isolate incomplete evidence."""

    truck_capacity = capacity or TruckCapacity()
    consolidation_policy = policy or ConsolidationPolicy()
    profile_map: dict[tuple[str, str], ItemLogisticsProfile] = {}
    for profile in profiles:
        key = _profile_key(profile.item_id, profile.uom)
        if key in profile_map:
            raise ValueError(f"Duplicate logistics profile for {key[0]} / {key[1]}.")
        profile_map[key] = profile

    quantified = [
        quantify_line(line, profile_map, truck_capacity)
        for line in sorted(lines, key=lambda row: (row.departure_day, row.line_id))
    ]
    groups: dict[tuple[str, str, str, str, str, int], list[QuantifiedLine]] = defaultdict(list)
    for row in quantified:
        groups[_group_key(row, consolidation_policy)].append(row)

    loads: list[TruckLoad] = []
    fallbacks: list[FallbackGroup] = []
    for key in sorted(groups):
        rows = groups[key]
        complete = [row for row in rows if row.fully_dimensioned]
        incomplete = [row for row in rows if not row.fully_dimensioned]
        if complete:
            loads.extend(_build_loads(complete, key, truck_capacity, consolidation_policy))
        if incomplete:
            fallbacks.append(
                _build_fallback(incomplete, key, truck_capacity, consolidation_policy)
            )

    input_by_uom: dict[str, float] = defaultdict(float)
    output_by_uom: dict[str, float] = defaultdict(float)
    for row in quantified:
        input_by_uom[row.line.uom.strip().upper()] += row.line.quantity
    for load in loads:
        for allocation in load.allocations:
            output_by_uom[allocation.uom.strip().upper()] += allocation.quantity
    for group in fallbacks:
        for uom, quantity in group.quantities_by_uom.items():
            output_by_uom[uom] += quantity
    conservation = {
        uom: {
            "input_qty": input_by_uom[uom],
            "allocated_or_fallback_qty": output_by_uom[uom],
            "difference": output_by_uom[uom] - input_by_uom[uom],
        }
        for uom in sorted(set(input_by_uom) | set(output_by_uom))
    }
    missing_dimension_counts = Counter(
        dimension
        for row in quantified
        for dimension in row.missing_dimensions
    )
    audit = {
        "contract_version": "etudecas.truck_consolidation.v1",
        "allocation_algorithm": (
            "deterministic_best_fit_decreasing_by_dominant_capacity_ratio"
        ),
        "capacity": truck_capacity.to_dict(),
        "policy": consolidation_policy.to_dict(),
        "profile_count": len(profile_map),
        "profile_source_references": sorted(
            {profile.source_reference for profile in profile_map.values()}
        ),
        "input_line_count": len(quantified),
        "fully_dimensioned_line_count": sum(row.fully_dimensioned for row in quantified),
        "fallback_line_count": sum(not row.fully_dimensioned for row in quantified),
        "truck_load_count": len(loads),
        "fallback_group_count": len(fallbacks),
        "fallback_known_capacity_lower_bound_trucks": sum(
            group.known_capacity_lower_bound_trucks for group in fallbacks
        ),
        "missing_dimension_line_counts": dict(sorted(missing_dimension_counts.items())),
        "partially_dimensioned_group_count": sum(
            any(row.fully_dimensioned for row in rows)
            and any(not row.fully_dimensioned for row in rows)
            for rows in groups.values()
        ),
        "physical_truck_count_is_complete": not fallbacks,
        "volume_capacity_status": (
            "configured" if truck_capacity.max_volume_m3 is not None else "not_configured"
        ),
        "no_unknown_weight_invention": True,
        "conservation_by_uom": conservation,
        "conservation_ok": all(
            math.isclose(
                row["input_qty"],
                row["allocated_or_fallback_qty"],
                rel_tol=1e-12,
                abs_tol=1e-6,
            )
            for row in conservation.values()
        ),
    }
    return ConsolidationResult(
        loads=tuple(loads),
        fallback_groups=tuple(fallbacks),
        audit=audit,
    )
