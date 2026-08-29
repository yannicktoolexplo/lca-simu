"""Small engine-facing adapter for auditable internal truck estimates."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from .models import TruckCapacity


def _item_key(value: Any) -> str:
    text = re.sub(r"^item:", "", str(value or "").strip(), flags=re.IGNORECASE)
    return f"item:{text}" if text else ""


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


@dataclass(frozen=True)
class InternalTruckEstimate:
    truck_count: int | None
    pallet_count: int | None
    known_net_weight_kg: float | None
    basis: str
    confidence: str
    missing_checks: tuple[str, ...]

    @property
    def handling_unit_kind(self) -> str:
        if self.truck_count == 1:
            return "TRUCK"
        if self.truck_count and self.truck_count > 1:
            return "TRUCKSET"
        return ""

    def trace_note(self) -> str:
        if self.truck_count is None:
            return (
                "internal_road_transport;truck_count_not_quantified;"
                f"basis={self.basis};missing={','.join(self.missing_checks) or 'none'}"
            )
        details = [
            "internal_road_transport",
            f"estimated_trucks={self.truck_count}",
            f"basis={self.basis}",
            f"confidence={self.confidence}",
        ]
        if self.pallet_count is not None:
            details.append(f"estimated_pallets={self.pallet_count}")
        if self.known_net_weight_kg is not None:
            details.append(f"known_net_weight_kg={self.known_net_weight_kg:.3f}")
        if self.missing_checks:
            details.append(f"to_validate={','.join(self.missing_checks)}")
        return ";".join(details)


def estimate_internal_truck_handling(
    *,
    item_id: Any,
    quantity: Any,
    uom: Any,
    logistics_assumptions: Mapping[str, Mapping[str, Any]] | None = None,
    capacity: TruckCapacity | None = None,
) -> InternalTruckEstimate:
    """Estimate truck count from known mass or explicit packaging assumptions."""

    truck = capacity or TruckCapacity()
    qty = max(0.0, float(quantity or 0.0))
    unit = str(uom or "").strip().upper()
    profile = dict((logistics_assumptions or {}).get(_item_key(item_id), {}) or {})

    net_weight_kg: float | None = None
    weight_trucks: int | None = None
    if unit == "KG":
        net_weight_kg = qty
    elif unit == "G":
        net_weight_kg = qty / 1000.0
    else:
        mass_per_unit = _positive(
            profile.get("estimatedGrossMassKgPerUnit")
            or profile.get("grossMassKgPerUnit")
        )
        if mass_per_unit is not None:
            net_weight_kg = qty * mass_per_unit
    if net_weight_kg is not None:
        weight_trucks = max(1, int(math.ceil(net_weight_kg / truck.max_weight_kg)))

    pallets: int | None = None
    pallet_trucks: int | None = None
    units_per_case = _positive(profile.get("unitsPerCase"))
    cases_per_pallet = _positive(profile.get("centralCasesPerPallet"))
    pallet_slots = _positive(profile.get("truckPalletSlots")) or truck.max_pallets
    if unit == "UN" and units_per_case and cases_per_pallet:
        cases = int(math.ceil(qty / units_per_case))
        pallets = int(math.ceil(cases / cases_per_pallet))
        pallet_trucks = max(1, int(math.ceil(pallets / pallet_slots)))

    known_counts = [
        value for value in (weight_trucks, pallet_trucks) if value is not None
    ]
    if not known_counts:
        return InternalTruckEstimate(
            truck_count=None,
            pallet_count=pallets,
            known_net_weight_kg=net_weight_kg,
            basis="insufficient_physical_dimensions",
            confidence="unknown",
            missing_checks=("weight", "pallets"),
        )

    missing: list[str] = []
    if weight_trucks is None:
        missing.append("gross_weight")
    if pallet_trucks is None:
        missing.append("pallets")
    basis_parts = []
    if pallet_trucks is not None:
        basis_parts.append("configured_case_pallet_profile")
    if weight_trucks is not None:
        basis_parts.append("known_mass_uom")
    return InternalTruckEstimate(
        truck_count=max(known_counts),
        pallet_count=pallets,
        known_net_weight_kg=net_weight_kg,
        basis="+".join(basis_parts),
        confidence="high" if not missing else "business_estimate",
        missing_checks=tuple(missing),
    )
