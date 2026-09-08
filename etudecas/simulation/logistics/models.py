"""Business contracts for truck consolidation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _positive_or_none(value: float | None, field_name: str) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be strictly positive when provided.")


@dataclass(frozen=True)
class TruckCapacity:
    """Physical capacity constraints for one truck type."""

    name: str = "standard_eu_semitrailer"
    max_weight_kg: float = 23_000.0
    max_pallets: float = 33.0
    max_volume_m3: float | None = None
    source_reference: str = "user_requirement_33_euro_pallets_23t"

    def __post_init__(self) -> None:
        _positive_or_none(self.max_weight_kg, "max_weight_kg")
        _positive_or_none(self.max_pallets, "max_pallets")
        _positive_or_none(self.max_volume_m3, "max_volume_m3")
        if not self.source_reference.strip():
            raise ValueError("Truck capacity requires a source_reference.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "max_weight_kg": self.max_weight_kg,
            "max_pallets": self.max_pallets,
            "max_volume_m3": self.max_volume_m3,
            "source_reference": self.source_reference,
        }


@dataclass(frozen=True)
class ItemLogisticsProfile:
    """Sourced conversion from a business UOM to loaded truck dimensions.

    ``kg_per_unit`` is the gross loaded weight, including the packaging or
    handling unit represented by the profile.
    """

    item_id: str
    uom: str
    source_reference: str
    kg_per_unit: float | None = None
    pallets_per_unit: float | None = None
    volume_m3_per_unit: float | None = None
    compatibility_group: str = "default"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.item_id.strip() or not self.uom.strip():
            raise ValueError("A logistics profile requires item_id and uom.")
        if not self.source_reference.strip():
            raise ValueError("A logistics conversion requires a non-empty source_reference.")
        if all(
            value is None
            for value in (self.kg_per_unit, self.pallets_per_unit, self.volume_m3_per_unit)
        ):
            raise ValueError("A logistics profile must define at least one physical conversion.")
        _positive_or_none(self.kg_per_unit, "kg_per_unit")
        _positive_or_none(self.pallets_per_unit, "pallets_per_unit")
        _positive_or_none(self.volume_m3_per_unit, "volume_m3_per_unit")


@dataclass(frozen=True)
class ShipmentLine:
    """One source shipment line before physical consolidation."""

    line_id: str
    departure_day: int
    origin_node_id: str
    destination_node_id: str
    item_id: str
    quantity: float
    uom: str
    mode: str = "truck"
    lot_id: str = ""
    shipment_id: str = ""
    arrival_day: int | None = None
    compatibility_group: str = "default"
    explicit_weight_kg: float | None = None
    explicit_pallets: float | None = None
    explicit_volume_m3: float | None = None
    physical_data_source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.line_id.strip():
            raise ValueError("Shipment line_id is required.")
        if not self.origin_node_id.strip() or not self.destination_node_id.strip():
            raise ValueError("Shipment origin and destination are required.")
        if not self.item_id.strip() or not self.uom.strip():
            raise ValueError("Shipment item_id and uom are required.")
        if self.departure_day < 0:
            raise ValueError("departure_day cannot be negative.")
        if self.quantity <= 0:
            raise ValueError("Shipment quantity must be strictly positive.")
        _positive_or_none(self.explicit_weight_kg, "explicit_weight_kg")
        _positive_or_none(self.explicit_pallets, "explicit_pallets")
        _positive_or_none(self.explicit_volume_m3, "explicit_volume_m3")
        if any(
            value is not None
            for value in (
                self.explicit_weight_kg,
                self.explicit_pallets,
                self.explicit_volume_m3,
            )
        ) and not self.physical_data_source.strip():
            raise ValueError("Explicit physical shipment data requires physical_data_source.")


@dataclass(frozen=True)
class ConsolidationPolicy:
    """Planning window and compatibility rules for consolidation."""

    bucket_days: int = 7
    anchor_day: int = 0
    mix_items: bool = True
    fallback_basis: str = "weekly_route_quantity_lot"

    def __post_init__(self) -> None:
        if self.bucket_days <= 0:
            raise ValueError("bucket_days must be strictly positive.")
        if not self.fallback_basis.strip():
            raise ValueError("fallback_basis is required.")

    def bucket_start(self, day: int) -> int:
        relative = day - self.anchor_day
        return self.anchor_day + (relative // self.bucket_days) * self.bucket_days

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket_days": self.bucket_days,
            "anchor_day": self.anchor_day,
            "mix_items": self.mix_items,
            "fallback_basis": self.fallback_basis,
        }


@dataclass(frozen=True)
class QuantifiedLine:
    line: ShipmentLine
    compatibility_group: str
    weight_kg: float | None
    weight_is_gross: bool
    pallets: float | None
    volume_m3: float | None
    weight_basis: str
    pallets_basis: str
    volume_basis: str
    missing_dimensions: tuple[str, ...]

    @property
    def fully_dimensioned(self) -> bool:
        return not self.missing_dimensions


@dataclass(frozen=True)
class LoadAllocation:
    line_id: str
    item_id: str
    quantity: float
    uom: str
    lot_id: str
    shipment_id: str
    weight_kg: float
    pallets: float
    volume_m3: float | None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TruckLoad:
    load_id: str
    origin_node_id: str
    destination_node_id: str
    mode: str
    compatibility_group: str
    window_start_day: int
    window_end_day: int
    consolidation_day: int
    weight_kg: float
    pallets: float
    volume_m3: float | None
    weight_utilization: float
    pallet_utilization: float
    volume_utilization: float | None
    allocations: tuple[LoadAllocation, ...]

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["allocations"] = [allocation.to_dict() for allocation in self.allocations]
        return data


@dataclass(frozen=True)
class FallbackGroup:
    group_id: str
    origin_node_id: str
    destination_node_id: str
    mode: str
    compatibility_group: str
    window_start_day: int
    window_end_day: int
    consolidation_day: int
    line_ids: tuple[str, ...]
    lot_ids: tuple[str, ...]
    shipment_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    quantities_by_uom: dict[str, float]
    quantities_by_item_uom: dict[str, float]
    known_weight_kg: float
    weight_bases: tuple[str, ...]
    known_pallets: float
    known_volume_m3: float
    weight_known_line_count: int
    pallet_known_line_count: int
    volume_known_line_count: int
    missing_dimensions: tuple[str, ...]
    known_capacity_lower_bound_trucks: int
    truck_count: None = None
    basis: str = "weekly_route_quantity_lot"
    reason: str = "physical_dimensions_incomplete"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ConsolidationResult:
    loads: tuple[TruckLoad, ...]
    fallback_groups: tuple[FallbackGroup, ...]
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "loads": [load.to_dict() for load in self.loads],
            "fallback_groups": [group.to_dict() for group in self.fallback_groups],
            "audit": self.audit,
        }
