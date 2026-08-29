from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .uom import as_decimal, normalize_uom, uom_dimension


class PolicyScope(str, Enum):
    PRODUCTION = "production"
    PROCUREMENT = "procurement"
    TRANSPORT = "transport"


class SourceKind(str, Enum):
    INDUSTRIAL_SOURCE = "industrial_source"
    BUSINESS_RULE = "business_rule"
    DERIVED = "derived"
    ASSUMPTION = "assumption"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConsolidationMode(str, Enum):
    PER_ORDER = "per_order"
    PERIODIC = "periodic"


@dataclass(frozen=True)
class PolicySource:
    reference: str
    kind: SourceKind
    confidence: Confidence
    note: str = ""

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("Policy source reference is required")


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    uom: str

    def __init__(self, value: Decimal | float | int | str, uom: str) -> None:
        amount = as_decimal(value)
        if amount <= 0:
            raise ValueError("Policy quantity must be positive")
        object.__setattr__(self, "value", amount)
        object.__setattr__(self, "uom", normalize_uom(uom))


@dataclass(frozen=True)
class UomPolicy:
    base_uom: str
    allowed_uoms: tuple[str, ...]
    production_uom: str | None = None
    procurement_uom: str | None = None
    transport_uom: str | None = None

    def __post_init__(self) -> None:
        base = normalize_uom(self.base_uom)
        allowed = tuple(dict.fromkeys(normalize_uom(value) for value in self.allowed_uoms))
        if base not in allowed:
            allowed = (base, *allowed)
        base_dimension = uom_dimension(base)
        incompatible = [value for value in allowed if uom_dimension(value) != base_dimension]
        if incompatible:
            raise ValueError(
                f"Allowed UOMs {incompatible} are not compatible with base UOM {base}"
            )
        object.__setattr__(self, "base_uom", base)
        object.__setattr__(self, "allowed_uoms", allowed)
        for field_name in ("production_uom", "procurement_uom", "transport_uom"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = normalize_uom(value)
                if normalized not in allowed:
                    raise ValueError(f"{field_name}={normalized} is not an allowed UOM")
                object.__setattr__(self, field_name, normalized)


@dataclass(frozen=True)
class ProductionLotPolicy:
    item_id: str
    site_id: str
    uom: str
    source: PolicySource
    fixed_qty: Decimal | None = None
    minimum_qty: Decimal | None = None
    maximum_qty: Decimal | None = None
    multiple_qty: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uom", normalize_uom(self.uom))
        for field_name in ("fixed_qty", "minimum_qty", "maximum_qty", "multiple_qty"):
            value = getattr(self, field_name)
            if value is not None:
                amount = as_decimal(value)
                if amount <= 0:
                    raise ValueError(f"{field_name} must be positive when defined")
                object.__setattr__(self, field_name, amount)
        if all(
            value is None
            for value in (self.fixed_qty, self.minimum_qty, self.maximum_qty, self.multiple_qty)
        ):
            raise ValueError("A production lot policy requires at least one sizing rule")
        if (
            self.minimum_qty is not None
            and self.maximum_qty is not None
            and self.minimum_qty > self.maximum_qty
        ):
            raise ValueError("Production minimum_qty cannot exceed maximum_qty")
        if self.fixed_qty is not None:
            if self.minimum_qty is not None and self.fixed_qty < self.minimum_qty:
                raise ValueError("Production fixed_qty cannot be below minimum_qty")
            if self.maximum_qty is not None and self.fixed_qty > self.maximum_qty:
                raise ValueError("Production fixed_qty cannot exceed maximum_qty")


@dataclass(frozen=True)
class ProcurementLotPolicy:
    item_id: str
    supplier_id: str
    destination_id: str
    uom: str
    source: PolicySource
    moq: Decimal
    order_multiple: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uom", normalize_uom(self.uom))
        moq = as_decimal(self.moq)
        if moq <= 0:
            raise ValueError("Procurement MOQ must be positive")
        object.__setattr__(self, "moq", moq)
        if self.order_multiple is not None:
            multiple = as_decimal(self.order_multiple)
            if multiple <= 0:
                raise ValueError("Procurement order_multiple must be positive")
            object.__setattr__(self, "order_multiple", multiple)


@dataclass(frozen=True)
class QuantityGranularityPolicy:
    item_id: str
    scope: PolicyScope
    quantity: Quantity
    source: PolicySource
    site_id: str = ""
    origin_id: str = ""
    destination_id: str = ""


@dataclass(frozen=True)
class TransportConsolidationPolicy:
    item_id: str
    origin_id: str
    destination_id: str
    uom: str
    mode: ConsolidationMode
    source: PolicySource
    window_days: int = 1
    minimum_dispatch_qty: Decimal | None = None
    dispatch_multiple: Decimal | None = None
    maximum_dispatch_qty: Decimal | None = None
    group_by: tuple[str, ...] = ("origin_id", "destination_id", "item_id")

    def __post_init__(self) -> None:
        object.__setattr__(self, "uom", normalize_uom(self.uom))
        if self.window_days <= 0:
            raise ValueError("Transport consolidation window_days must be positive")
        if self.mode == ConsolidationMode.PER_ORDER and self.window_days != 1:
            raise ValueError("PER_ORDER consolidation must use a one-day window")
        for field_name in (
            "minimum_dispatch_qty",
            "dispatch_multiple",
            "maximum_dispatch_qty",
        ):
            value = getattr(self, field_name)
            if value is not None:
                amount = as_decimal(value)
                if amount <= 0:
                    raise ValueError(f"{field_name} must be positive when defined")
                object.__setattr__(self, field_name, amount)
        if (
            self.minimum_dispatch_qty is not None
            and self.maximum_dispatch_qty is not None
            and self.minimum_dispatch_qty > self.maximum_dispatch_qty
        ):
            raise ValueError("Transport minimum_dispatch_qty cannot exceed maximum_dispatch_qty")


@dataclass(frozen=True)
class ItemLotPolicy:
    item_id: str
    uom: UomPolicy
    production: tuple[ProductionLotPolicy, ...] = ()
    procurement: tuple[ProcurementLotPolicy, ...] = ()
    granularity: tuple[QuantityGranularityPolicy, ...] = ()
    transport: tuple[TransportConsolidationPolicy, ...] = ()

    def __post_init__(self) -> None:
        rules = (*self.production, *self.procurement, *self.granularity, *self.transport)
        invalid_items = sorted({rule.item_id for rule in rules if rule.item_id != self.item_id})
        if invalid_items:
            raise ValueError(
                f"Rules {invalid_items} do not belong to item policy {self.item_id}"
            )
        for rule in (*self.production, *self.procurement, *self.transport):
            if rule.uom not in self.uom.allowed_uoms:
                raise ValueError(
                    f"Rule UOM {rule.uom} is not allowed for item policy {self.item_id}"
                )
        for rule in self.granularity:
            if rule.quantity.uom not in self.uom.allowed_uoms:
                raise ValueError(
                    f"Granularity UOM {rule.quantity.uom} is not allowed for "
                    f"item policy {self.item_id}"
                )


@dataclass(frozen=True)
class TransportRequest:
    request_id: str
    day: int
    item_id: str
    origin_id: str
    destination_id: str
    quantity: Quantity

    def __post_init__(self) -> None:
        if self.day < 0:
            raise ValueError("Transport request day cannot be negative")
        if not self.request_id:
            raise ValueError("Transport request_id is required")


@dataclass(frozen=True)
class ConsolidatedTransportPlan:
    item_id: str
    origin_id: str
    destination_id: str
    bucket_start_day: int
    bucket_end_day: int
    demand_qty: Quantity
    dispatch_qty: Quantity
    planned_overage_qty: Quantity | None
    request_ids: tuple[str, ...]


@dataclass
class LotPolicyRegistry:
    _items: dict[str, ItemLotPolicy] = field(default_factory=dict)

    def register(self, policy: ItemLotPolicy) -> None:
        if policy.item_id in self._items:
            raise ValueError(f"Duplicate lot policy for {policy.item_id}")
        self._items[policy.item_id] = policy

    def get(self, item_id: str) -> ItemLotPolicy | None:
        return self._items.get(item_id)

    def require(self, item_id: str) -> ItemLotPolicy:
        policy = self.get(item_id)
        if policy is None:
            raise KeyError(f"No canonical lot policy for {item_id}")
        return policy

    def items(self) -> tuple[ItemLotPolicy, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    @classmethod
    def from_policies(cls, policies: Iterable[ItemLotPolicy]) -> "LotPolicyRegistry":
        registry = cls()
        for policy in policies:
            registry.register(policy)
        return registry
