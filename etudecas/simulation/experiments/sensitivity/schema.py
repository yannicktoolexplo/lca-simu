"""Schema objects for generic sensitivity studies.

The schema is intentionally JSON-first. YAML can be added later, but JSON keeps
the dependency surface small and makes the contract easy to validate in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    levels: tuple[Any, ...]
    baseline: Any = 1.0
    target: str = ""
    family: str = ""
    kind: str = "factor"
    unit: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ParameterSpec":
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ValueError("Parameter is missing required field 'name'.")
        levels = tuple(raw.get("levels") or [])
        if not levels:
            raise ValueError(f"Parameter {name!r} is missing non-empty 'levels'.")
        return cls(
            name=name,
            levels=levels,
            baseline=raw.get("baseline", 1.0),
            target=str(raw.get("target") or ""),
            family=str(raw.get("family") or ""),
            kind=str(raw.get("kind") or "factor"),
            unit=str(raw.get("unit") or ""),
            description=str(raw.get("description") or ""),
            metadata=_as_dict(raw.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "family": self.family,
            "kind": self.kind,
            "baseline": self.baseline,
            "levels": list(self.levels),
            "unit": self.unit,
            "description": self.description,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StudySpec:
    study_id: str
    title: str
    baseline: str
    input_graph: str
    run_script: str
    scenario_id: str
    horizon_days: int
    retention: str
    sampling: dict[str, Any]
    parameters: tuple[ParameterSpec, ...]
    metrics: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StudySpec":
        study_id = str(raw.get("study_id") or "").strip()
        if not study_id:
            raise ValueError("Study is missing required field 'study_id'.")
        parameters = tuple(ParameterSpec.from_dict(p) for p in (raw.get("parameters") or []))
        if not parameters:
            raise ValueError(f"Study {study_id!r} must define at least one parameter.")
        horizon_days = int(raw.get("horizon_days") or raw.get("days") or 0)
        if horizon_days <= 0:
            raise ValueError(f"Study {study_id!r} must define a positive horizon_days.")
        retention = str(raw.get("retention") or "summary")
        if retention not in {"summary", "compact", "full"}:
            raise ValueError("retention must be one of: summary, compact, full.")
        return cls(
            study_id=study_id,
            title=str(raw.get("title") or study_id),
            baseline=str(raw.get("baseline") or "nominal"),
            input_graph=str(raw.get("input_graph") or raw.get("input") or ""),
            run_script=str(raw.get("run_script") or "etudecas/simulation/engine/run_first_simulation.py"),
            scenario_id=str(raw.get("scenario_id") or "scn:BASE"),
            horizon_days=horizon_days,
            retention=retention,
            sampling=_as_dict(raw.get("sampling")),
            parameters=parameters,
            metrics=tuple(str(m) for m in (raw.get("metrics") or [])),
            metadata=_as_dict(raw.get("metadata")),
        )

    @classmethod
    def from_path(cls, path: str | Path) -> "StudySpec":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "title": self.title,
            "baseline": self.baseline,
            "input_graph": self.input_graph,
            "run_script": self.run_script,
            "scenario_id": self.scenario_id,
            "horizon_days": self.horizon_days,
            "retention": self.retention,
            "sampling": dict(self.sampling),
            "parameters": [p.to_dict() for p in self.parameters],
            "metrics": list(self.metrics),
            "metadata": dict(self.metadata),
        }

    def write_manifest(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def example_study_dict() -> dict[str, Any]:
    return {
        "study_id": "supplier_lead_capacity_example",
        "title": "Supplier lead-time and capacity sensitivity",
        "baseline": "nominal_5y",
        "input_graph": "etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json",
        "run_script": "etudecas/simulation/engine/run_first_simulation.py",
        "scenario_id": "scn:BASE",
        "horizon_days": 1825,
        "retention": "summary",
        "sampling": {
            "method": "one_at_a_time",
            "include_baseline": True,
            "max_scenarios": 200,
        },
        "parameters": [
            {
                "name": "supplier_capacity_scale",
                "target": "supplier.capacity",
                "family": "capacity",
                "kind": "factor",
                "baseline": 1.0,
                "levels": [0.5, 0.75, 1.0, 1.25],
                "description": "Supplier daily throughput multiplier.",
            },
            {
                "name": "supplier_lead_time_scale",
                "target": "supplier.lead_time",
                "family": "lead_time",
                "kind": "factor",
                "baseline": 1.0,
                "levels": [1.0, 1.25, 1.5, 2.0],
                "description": "Supplier planned lead-time multiplier.",
            },
            {
                "name": "supplier_opening_stock_scale",
                "target": "supplier.opening_stock",
                "family": "stock",
                "kind": "factor",
                "baseline": 1.0,
                "levels": [0.25, 0.5, 0.75, 1.0],
                "description": "Available supplier opening stock multiplier.",
            },
        ],
        "metrics": [
            "fill_rate",
            "max_backlog",
            "ending_backlog",
            "production_replanning_count",
            "input_delay_volume",
            "total_cost",
            "total_external_procured_ordered_qty",
        ],
    }

