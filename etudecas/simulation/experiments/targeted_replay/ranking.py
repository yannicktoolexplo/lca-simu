"""Scenario contracts and multi-KPI ranking of scenario influence."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

ImpactDirection = Literal["absolute", "higher", "lower"]


@dataclass(frozen=True)
class KpiSpec:
    """One KPI used to rank scenario influence against the nominal run."""

    name: str
    direction: ImpactDirection = "absolute"
    weight: float = 1.0

    @classmethod
    def parse(cls, value: str) -> "KpiSpec":
        parts = [part.strip() for part in str(value).split(":")]
        if not parts or not parts[0]:
            raise ValueError("A KPI specification must start with a KPI name.")
        direction = parts[1].lower() if len(parts) > 1 and parts[1] else "absolute"
        aliases = {
            "abs": "absolute",
            "increase": "higher",
            "decrease": "lower",
            "higher_is_worse": "higher",
            "lower_is_worse": "lower",
        }
        direction = aliases.get(direction, direction)
        if direction not in {"absolute", "higher", "lower"}:
            raise ValueError(
                f"Unsupported KPI direction '{direction}'. Expected absolute, higher, or lower."
            )
        weight = float(parts[2]) if len(parts) > 2 and parts[2] else 1.0
        if weight <= 0:
            raise ValueError("KPI weight must be strictly positive.")
        return cls(name=parts[0], direction=direction, weight=weight)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "direction": self.direction, "weight": self.weight}


DEFAULT_KPI_SPECS: tuple[KpiSpec, ...] = (
    KpiSpec("product_availability", "lower", 3.0),
    KpiSpec("production_replanning_rate", "higher", 2.0),
    KpiSpec("ending_backlog", "higher", 2.0),
    KpiSpec("total_cost", "higher", 1.0),
)


@dataclass
class ScenarioCandidate:
    """A scenario that can be ranked and replayed from a recorded command."""

    scenario_id: str
    label: str
    source_run_dir: Path
    source_manifest: Path
    simulator_command: list[str]
    metrics: dict[str, float | None]
    role: str = "candidate"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "role": self.role,
            "source_run_dir": str(self.source_run_dir),
            "source_manifest": str(self.source_manifest),
            "simulator_command": list(self.simulator_command),
            "metrics": dict(self.metrics),
            "metadata": dict(self.metadata),
        }


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
