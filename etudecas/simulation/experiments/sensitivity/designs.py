"""Scenario design generation for sensitivity studies."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import itertools
import json
import re
from pathlib import Path
from typing import Any

from .schema import StudySpec


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
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [design.to_row() for design in designs]
    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = ["scenario_id", "study_id", "kind", "changed_parameters", "parameter_values_json"]
    fieldnames = preferred + [field for field in fieldnames if field not in preferred]
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

