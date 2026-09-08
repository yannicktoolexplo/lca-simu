from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Any


class IncompatibleUomError(ValueError):
    """Raised when a quantity conversion crosses physical dimensions."""


_UOM_ALIASES = {
    "G": "G",
    "GRAM": "G",
    "GRAMME": "G",
    "GRAMMES": "G",
    "GRAMS": "G",
    "KG": "KG",
    "KILOGRAM": "KG",
    "KILOGRAMME": "KG",
    "KILOGRAMMES": "KG",
    "KILOGRAMS": "KG",
    "UN": "UN",
    "UNIT": "UN",
    "UNITE": "UN",
    "UNITES": "UN",
    "UNITS": "UN",
    "ZUN": "UN",
    "M": "M",
    "METER": "M",
    "METERS": "M",
    "METRE": "M",
    "METRES": "M",
}

_UOM_DIMENSION = {
    "G": "mass",
    "KG": "mass",
    "UN": "count",
    "M": "length",
}

_TO_BASE_FACTOR = {
    "G": Decimal("1"),
    "KG": Decimal("1000"),
    "UN": Decimal("1"),
    "M": Decimal("1"),
}


def as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def normalize_uom(value: Any) -> str:
    text = str(value or "").strip().upper()
    normalized = _UOM_ALIASES.get(text)
    if normalized is None:
        raise ValueError(f"Unsupported UOM: {value!r}")
    return normalized


def uom_dimension(value: Any) -> str:
    return _UOM_DIMENSION[normalize_uom(value)]


def convert_quantity(value: Any, from_uom: Any, to_uom: Any) -> Decimal:
    source = normalize_uom(from_uom)
    target = normalize_uom(to_uom)
    if _UOM_DIMENSION[source] != _UOM_DIMENSION[target]:
        raise IncompatibleUomError(
            f"Cannot convert {source} ({_UOM_DIMENSION[source]}) "
            f"to {target} ({_UOM_DIMENSION[target]})"
        )
    return as_decimal(value) * _TO_BASE_FACTOR[source] / _TO_BASE_FACTOR[target]


def quantity_multiple(value: Any, multiple: Any, *, tolerance: Decimal = Decimal("1e-9")) -> bool:
    amount = as_decimal(value)
    step = as_decimal(multiple)
    if step <= 0:
        raise ValueError("Quantity multiple must be positive")
    quotient = amount / step
    nearest = quotient.to_integral_value()
    return abs(quotient - nearest) <= tolerance


def round_up_to_multiple(value: Any, multiple: Any) -> Decimal:
    amount = as_decimal(value)
    step = as_decimal(multiple)
    if amount < 0:
        raise ValueError("Quantity cannot be negative")
    if step <= 0:
        raise ValueError("Quantity multiple must be positive")
    if amount == 0:
        return Decimal("0")
    units = (amount / step).to_integral_value(rounding=ROUND_CEILING)
    return units * step
