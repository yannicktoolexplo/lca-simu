"""Multi-KPI ranking of scenario influence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .schema import KpiSpec, ScenarioCandidate


def _directed_delta(candidate: float, baseline: float, direction: str) -> float:
    delta = candidate - baseline
    if direction == "higher":
        return max(0.0, delta)
    if direction == "lower":
        return max(0.0, -delta)
    return abs(delta)


@dataclass(frozen=True)
class RankedScenario:
    rank: int
    candidate: ScenarioCandidate
    score: float
    metric_details: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "scenario": self.candidate.to_dict(),
            "metric_details": self.metric_details,
        }


def rank_scenarios(
    baseline: ScenarioCandidate,
    candidates: Iterable[ScenarioCandidate],
    specs: Iterable[KpiSpec],
) -> list[RankedScenario]:
    """Rank adverse or absolute KPI deltas after per-KPI normalization."""

    candidate_rows = list(candidates)
    kpi_specs = list(specs)
    if not candidate_rows:
        return []
    if not kpi_specs:
        raise ValueError("At least one KPI specification is required.")

    directed_by_scenario: list[dict[str, float | None]] = []
    maxima = {spec.name: 0.0 for spec in kpi_specs}
    for candidate in candidate_rows:
        row: dict[str, float | None] = {}
        for spec in kpi_specs:
            baseline_value = baseline.metrics.get(spec.name)
            candidate_value = candidate.metrics.get(spec.name)
            if baseline_value is None or candidate_value is None:
                row[spec.name] = None
                continue
            directed = _directed_delta(candidate_value, baseline_value, spec.direction)
            row[spec.name] = directed
            maxima[spec.name] = max(maxima[spec.name], directed)
        directed_by_scenario.append(row)

    unranked: list[tuple[ScenarioCandidate, float, dict[str, dict[str, Any]]]] = []
    for candidate, directed_row in zip(candidate_rows, directed_by_scenario):
        weighted_score = 0.0
        available_weight = 0.0
        details: dict[str, dict[str, Any]] = {}
        for spec in kpi_specs:
            baseline_value = baseline.metrics.get(spec.name)
            candidate_value = candidate.metrics.get(spec.name)
            directed = directed_row.get(spec.name)
            maximum = maxima[spec.name]
            normalized = None if directed is None else (directed / maximum if maximum > 0 else 0.0)
            if normalized is not None:
                weighted_score += normalized * spec.weight
                available_weight += spec.weight
            details[spec.name] = {
                "baseline": baseline_value,
                "candidate": candidate_value,
                "raw_delta": (
                    candidate_value - baseline_value
                    if candidate_value is not None and baseline_value is not None
                    else None
                ),
                "directed_delta": directed,
                "normalized_influence": normalized,
                "direction": spec.direction,
                "weight": spec.weight,
            }
        score = weighted_score / available_weight if available_weight else 0.0
        unranked.append((candidate, score, details))

    unranked.sort(key=lambda row: (-row[1], row[0].scenario_id, row[0].label))
    return [
        RankedScenario(rank=index, candidate=candidate, score=score, metric_details=details)
        for index, (candidate, score, details) in enumerate(unranked, start=1)
    ]
