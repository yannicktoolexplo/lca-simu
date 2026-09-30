"""JSON study contracts and scenario design generation for sensitivity studies."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

from etudecas.simulation.analysis_batch_common import safe_name

from .results import write_csv


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


def slug(value: Any) -> str:
    text = str(value).replace(".", "_")
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "x"


@dataclass(frozen=True)
class ScenarioDesign:
    scenario_id: str
    study_id: str
    kind: str
    parameter_values: dict[str, Any]
    changed_parameters: tuple[str, ...]

    def to_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "scenario_id": self.scenario_id,
            "study_id": self.study_id,
            "kind": self.kind,
            "changed_parameters": ",".join(self.changed_parameters),
            "parameter_values_json": json.dumps(self.parameter_values, ensure_ascii=False, sort_keys=True),
        }
        for key, value in sorted(self.parameter_values.items()):
            row[f"param::{key}"] = value
        return row


def _baseline_values(study: StudySpec) -> dict[str, Any]:
    return {param.name: param.baseline for param in study.parameters}


def _changed_parameters(study: StudySpec, values: dict[str, Any]) -> tuple[str, ...]:
    changed: list[str] = []
    for param in study.parameters:
        if values.get(param.name) != param.baseline:
            changed.append(param.name)
    return tuple(changed)


def _scenario_id(study: StudySpec, values: dict[str, Any], kind: str) -> str:
    changed = _changed_parameters(study, values)
    if not changed:
        return f"{slug(study.study_id)}__baseline"
    parts = [slug(study.study_id), slug(kind)]
    for name in changed:
        parts.append(f"{slug(name)}_{slug(values.get(name))}")
    return "__".join(parts)


def build_scenario_designs(study: StudySpec) -> list[ScenarioDesign]:
    method = str(study.sampling.get("method") or "one_at_a_time").lower()
    include_baseline = bool(study.sampling.get("include_baseline", True))
    max_scenarios = int(study.sampling.get("max_scenarios") or 0)
    baseline = _baseline_values(study)
    designs: list[ScenarioDesign] = []

    if include_baseline:
        designs.append(
            ScenarioDesign(
                scenario_id=_scenario_id(study, baseline, "baseline"),
                study_id=study.study_id,
                kind="baseline",
                parameter_values=dict(baseline),
                changed_parameters=(),
            )
        )

    if method in {"one_at_a_time", "oat"}:
        for param in study.parameters:
            for level in param.levels:
                if level == param.baseline:
                    continue
                values = dict(baseline)
                values[param.name] = level
                designs.append(
                    ScenarioDesign(
                        scenario_id=_scenario_id(study, values, "oat"),
                        study_id=study.study_id,
                        kind="one_at_a_time",
                        parameter_values=values,
                        changed_parameters=(param.name,),
                    )
                )
    elif method in {"grid", "full_factorial"}:
        names = [param.name for param in study.parameters]
        for levels in itertools.product(*[param.levels for param in study.parameters]):
            values = dict(zip(names, levels, strict=True))
            if values == baseline and include_baseline:
                continue
            changed = _changed_parameters(study, values)
            designs.append(
                ScenarioDesign(
                    scenario_id=_scenario_id(study, values, "grid"),
                    study_id=study.study_id,
                    kind="grid",
                    parameter_values=values,
                    changed_parameters=changed,
                )
            )
    else:
        raise ValueError(f"Unsupported sensitivity sampling method: {method}")

    if max_scenarios > 0 and len(designs) > max_scenarios:
        return designs[:max_scenarios]
    return designs


def write_scenario_design_csv(path: str | Path, designs: list[ScenarioDesign]) -> None:
    rows = [design.to_row() for design in designs]
    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = ["scenario_id", "study_id", "kind", "changed_parameters", "parameter_values_json"]
    fieldnames = preferred + [field for field in fieldnames if field not in preferred]
    write_csv(path, rows, fieldnames=fieldnames)


# Stable identifiers shared by local and threshold sensitivity studies.
GLOBAL_PARAMETER_ALIASES = {
    "baseline": "base",
    "lead_time_scale": "lt",
    "transport_cost_scale": "tc",
    "supplier_stock_scale": "sstk",
    "production_stock_scale": "pstk",
    "capacity_scale": "cap",
    "supplier_capacity_scale": "scap",
    "safety_stock_days_scale": "ss",
    "supplier_reliability_scale": "srel",
    "review_period_scale": "rev",
    "opening_stock_bootstrap_scale": "boot",
    "external_procurement_enabled": "ep_on",
    "external_procurement_daily_cap_days_scale": "ep_cap",
    "external_procurement_lead_days_scale": "ep_lt",
    "external_procurement_cost_multiplier_scale": "ep_cost",
    "holding_cost_scale": "hold",
}

SCOPED_PARAMETER_ALIASES = {
    "demand_item": "dem",
    "capacity_node": "cap",
    "supplier_stock_node": "sstk",
    "supplier_capacity_node": "scap",
    "supplier_lead_time_node": "slt",
    "supplier_reliability_node": "srel",
}

DIRECTION_ALIASES = {
    "base": "base",
    "repeat": "rpt",
    "low": "lo",
    "high": "hi",
    "stress": "str",
}


def _clip_with_hash(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    head_len = max(8, max_len - len(digest) - 1)
    return f"{value[:head_len].rstrip('_-')}_{digest}"


def parameter_key_slug(parameter_key: str, *, max_len: int = 36) -> str:
    parameter_key = str(parameter_key or "").strip()
    if not parameter_key:
        return "param"
    if "::" not in parameter_key:
        return _clip_with_hash(GLOBAL_PARAMETER_ALIASES.get(parameter_key, safe_name(parameter_key)), max_len)
    scope, target = parameter_key.split("::", 1)
    scope_slug = SCOPED_PARAMETER_ALIASES.get(scope, safe_name(scope))
    target_slug = safe_name(target)
    return _clip_with_hash(f"{scope_slug}_{target_slug}", max_len)


def level_slug(level: Any) -> str:
    if isinstance(level, bool):
        return "1" if level else "0"
    if isinstance(level, int):
        return str(level)
    if isinstance(level, float):
        if level.is_integer():
            return f"{int(level)}_0"
        text = f"{level:.4f}".rstrip("0").rstrip(".")
        return safe_name(text.replace("-", "m"))
    return safe_name(str(level).replace("-", "m"))


def realistic_case_id(*, study: str, parameter_key: str, direction: str) -> str:
    study = str(study or "").strip()
    direction = str(direction or "").strip()
    if study == "baseline":
        return "baseline_repeat" if direction == "repeat" else "baseline"
    study_slug = {"local": "loc", "stress": "str"}.get(study, safe_name(study))
    direction_slug = DIRECTION_ALIASES.get(direction, safe_name(direction))
    return _clip_with_hash(
        f"{study_slug}_{parameter_key_slug(parameter_key, max_len=28)}_{direction_slug}",
        48,
    )


def threshold_case_id(*, parameter_key: str, level: Any) -> str:
    if str(parameter_key or "").strip() == "baseline":
        return "baseline"
    return _clip_with_hash(
        f"th_{parameter_key_slug(parameter_key, max_len=28)}_{level_slug(level)}",
        48,
    )
