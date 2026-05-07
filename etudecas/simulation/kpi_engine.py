from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

OptimizationDirection = Literal["higher_is_better", "lower_is_better"]


@dataclass(frozen=True)
class KpiDefinition:
    name: str
    target: float
    catastrophic_value: float
    optimization: OptimizationDirection
    multiplying_factor: float = 1.0


@dataclass(frozen=True)
class KpiObservation:
    name: str
    actual: float
    target: float
    catastrophic_value: float
    optimization: OptimizationDirection
    multiplying_factor: float = 1.0


DEFAULT_PHYSICS_KPI_DEFINITIONS: tuple[KpiDefinition, ...] = (
    KpiDefinition(
        name="product_availability",
        target=0.98,
        catastrophic_value=0.70,
        optimization="higher_is_better",
        multiplying_factor=3.0,
    ),
    KpiDefinition(
        name="line_adherence",
        target=0.95,
        catastrophic_value=0.60,
        optimization="higher_is_better",
        multiplying_factor=1.0,
    ),
    KpiDefinition(
        name="line_nervousness",
        target=5.0,
        catastrophic_value=40.0,
        optimization="lower_is_better",
        multiplying_factor=0.75,
    ),
    KpiDefinition(
        name="production_replanning_count",
        target=2.0,
        catastrophic_value=25.0,
        optimization="lower_is_better",
        multiplying_factor=0.75,
    ),
    KpiDefinition(
        name="raw_material_stockout_days",
        target=0.0,
        catastrophic_value=20.0,
        optimization="lower_is_better",
        multiplying_factor=2.0,
    ),
    KpiDefinition(
        name="material_delay_days",
        target=0.0,
        catastrophic_value=30.0,
        optimization="lower_is_better",
        multiplying_factor=1.5,
    ),
    KpiDefinition(
        name="inventory_cost",
        target=1.0,
        catastrophic_value=3.0,
        optimization="lower_is_better",
        multiplying_factor=0.75,
    ),
)


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def normalized_distance(
    actual: float,
    target: float,
    catastrophic_value: float,
    optimization: OptimizationDirection,
) -> float:
    actual = _finite_float(actual)
    target = _finite_float(target)
    catastrophic_value = _finite_float(catastrophic_value)
    if optimization == "higher_is_better":
        denominator = target - catastrophic_value
        if abs(denominator) <= 1e-12:
            return 0.0
        return _clip01((target - actual) / denominator)
    if optimization == "lower_is_better":
        denominator = catastrophic_value - target
        if abs(denominator) <= 1e-12:
            return 0.0
        return _clip01((actual - target) / denominator)
    raise ValueError(f"Unsupported optimization direction: {optimization!r}")


def observation_distance(observation: KpiObservation) -> float:
    return normalized_distance(
        observation.actual,
        observation.target,
        observation.catastrophic_value,
        observation.optimization,
    )


def weighted_euclidean_score(observations: Iterable[KpiObservation]) -> float:
    numerator = 0.0
    denominator = 0.0
    for observation in observations:
        factor = max(0.0, _finite_float(observation.multiplying_factor, 1.0))
        distance = observation_distance(observation)
        numerator += (factor * distance) ** 2
        denominator += factor**2
    if denominator <= 1e-12:
        return 0.0
    return math.sqrt(numerator / denominator)


def build_observations(
    definitions: Iterable[KpiDefinition],
    actuals: Mapping[str, Any],
) -> list[KpiObservation]:
    observations: list[KpiObservation] = []
    for definition in definitions:
        actual = _finite_float(actuals.get(definition.name), definition.target)
        observations.append(
            KpiObservation(
                name=definition.name,
                actual=actual,
                target=definition.target,
                catastrophic_value=definition.catastrophic_value,
                optimization=definition.optimization,
                multiplying_factor=definition.multiplying_factor,
            )
        )
    return observations


def evaluate_observations(observations: Iterable[KpiObservation]) -> dict[str, Any]:
    observed = list(observations)
    terms: dict[str, float] = {}
    distances: dict[str, float] = {}
    for observation in observed:
        distance = observation_distance(observation)
        factor = max(0.0, _finite_float(observation.multiplying_factor, 1.0))
        distances[observation.name] = distance
        terms[observation.name] = (factor * distance) ** 2
    numerator = sum(terms.values())
    denominator = sum(max(0.0, _finite_float(obs.multiplying_factor, 1.0)) ** 2 for obs in observed)
    global_score = math.sqrt(numerator / denominator) if denominator > 1e-12 else 0.0
    contributions = {
        name: (term / numerator if numerator > 1e-12 else 0.0)
        for name, term in terms.items()
    }
    return {
        "global_score": global_score,
        "distances": distances,
        "weighted_terms": terms,
        "contributions": contributions,
    }


def compute_kpi_rows(
    days: Iterable[int],
    actual_series_by_kpi: Mapping[str, Mapping[int, Any]],
    definitions: Iterable[KpiDefinition] = DEFAULT_PHYSICS_KPI_DEFINITIONS,
) -> list[dict[str, Any]]:
    specs = list(definitions)
    rows: list[dict[str, Any]] = []
    for day in sorted(int(day) for day in days):
        actuals = {
            spec.name: _finite_float(
                (actual_series_by_kpi.get(spec.name) or {}).get(day),
                spec.target,
            )
            for spec in specs
        }
        observations = build_observations(specs, actuals)
        evaluation = evaluate_observations(observations)
        row: dict[str, Any] = {
            "day": day,
            "global_score": evaluation["global_score"],
            "health_score": 1.0 - evaluation["global_score"],
        }
        for observation in observations:
            name = observation.name
            row[f"{name}__actual"] = observation.actual
            row[f"{name}__target"] = observation.target
            row[f"{name}__catastrophic_value"] = observation.catastrophic_value
            row[f"{name}__distance"] = evaluation["distances"][name]
            row[f"{name}__contribution"] = evaluation["contributions"][name]
            row[f"{name}__multiplying_factor"] = observation.multiplying_factor
        top_contributors = sorted(
            evaluation["contributions"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
        row["top_contributors"] = "; ".join(
            f"{name}:{value:.4f}" for name, value in top_contributors[:3]
        )
        rows.append(row)
    return rows


def write_kpi_rows_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
