"""Mass-transport fuel screening, separate from historical seat-use impacts."""

from __future__ import annotations

import math
from typing import Any


ARTICLE_METHOD = "steinegger_a322_2017"
POINTS = ((2000, 0.07), (4000, 0.12), (5000, 0.16))


def _number(mapping: dict[str, Any], key: str, *, positive: bool = False) -> float:
    value = mapping.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key} must be a finite number") from exc
    if isinstance(value, bool) or not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(f"{key} must be finite and {'positive' if positive else 'nonnegative'}")
    return number


def build_mission(config: dict[str, Any]) -> dict[str, Any] | None:
    """Use configured kg, km, cycles/year and years; no invented uncertainty bounds."""
    flight = config.get("flight_use", {})
    method = flight.get("calculation_method")
    if method is None:
        return None
    if method != ARTICLE_METHOD:
        raise ValueError(f"Unsupported flight_use.calculation_method: {method}")
    distance = _number(flight, "average_flight_distance_km", positive=True)
    cycles = _number(flight, "annual_flight_cycles")
    years = _number(flight, "lifetime_years")
    baseline_mass = _number(config, "baseline_mass_kg", positive=True)
    target_mass = _number(config, "target_mass_kg")
    outside = distance < POINTS[0][0] or distance > POINTS[-1][0]
    if outside and flight.get("allow_extrapolation") is not True:
        raise ValueError("Distance outside 2000..5000 km requires allow_extrapolation=true")
    left, right = POINTS[:2] if distance <= 4000 else POINTS[1:]
    coefficient = left[1] + (distance - left[0]) * (right[1] - left[1]) / (right[0] - left[0])
    status = "extrapolated_not_validated" if outside else (
        "source_point" if distance in dict(POINTS) else "interpolated")
    baseline = baseline_mass * cycles * years * coefficient
    target = target_mass * cycles * years * coefficient
    return {
        "calculation_method": method,
        "distance_km": distance,
        "average_flight_distance_km": distance,
        "annual_flight_cycles": cycles,
        "lifetime_years": years,
        "lifetime_flight_cycles": cycles * years,
        "lifetime_distance_km": distance * cycles * years,
        "baseline_mass_kg": baseline_mass,
        "target_mass_kg": target_mass,
        "coefficient_kg_fuel_per_kg_per_flight": coefficient,
        "fuel_coefficient_kg_per_kg_per_flight": coefficient,
        "valid_distance_domain_km": [2000, 5000],
        "status": status,
        "warning": "Extrapolation outside 2000..5000 km; not validated." if outside else "",
        "baseline_fuel_kg": baseline,
        "target_fuel_kg": target,
        "avoided_fuel_kg": baseline - target,
        "avoided_fuel_low_kg": None,
        "avoided_fuel_high_kg": None,
        "direct_co2_kg_per_kg_fuel": 3.16,
        "baseline_direct_co2_kg": baseline * 3.16,
        "target_direct_co2_kg": target * 3.16,
        "avoided_direct_co2_kg": (baseline - target) * 3.16,
        "source": {"id": ARTICLE_METHOD, "author": "Steinegger", "year": 2017,
                   "page": 11, "points": [
                       {"distance_km": d, "kg_fuel_per_kg_per_flight": c} for d, c in POINTS]},
        "scope": "mass_transport_only",
        "excluded_use": ["ife", "cleaning", "non_co2_altitude_effects"],
    }
