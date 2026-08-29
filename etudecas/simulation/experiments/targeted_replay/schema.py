"""Data contracts for targeted scenario replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

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
