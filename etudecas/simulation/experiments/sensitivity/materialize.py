"""Materialize sensitivity scenario designs into runnable simulation cases."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from etudecas.simulation.analysis_batch_common import apply_scales, load_json, write_json

from .designs import ScenarioDesign, build_scenario_designs
from .schema import StudySpec


FACTOR_ALIASES = {
    "supplier_opening_stock_scale": "supplier_stock_scale",
    "supplier_stock_scale": "supplier_stock_scale",
    "supplier_capacity_scale": "supplier_capacity_scale",
    "supplier_lead_time_scale": "lead_time_scale",
    "lead_time_scale": "lead_time_scale",
    "demand_scale": "demand_scale",
    "capacity_scale": "capacity_scale",
    "production_stock_scale": "production_stock_scale",
    "safety_stock_days_scale": "safety_stock_days_scale",
    "review_period_scale": "review_period_scale",
    "external_procurement_daily_cap_days_scale": "external_procurement_daily_cap_days_scale",
    "external_procurement_lead_days_scale": "external_procurement_lead_days_scale",
}


def numeric_factor_values(design: ScenarioDesign) -> dict[str, float]:
    factors: dict[str, float] = {}
    for name, value in design.parameter_values.items():
        factor_name = FACTOR_ALIASES.get(name, name)
        try:
            factors[factor_name] = float(value)
        except (TypeError, ValueError):
            continue
    return factors


def command_for_case(study: StudySpec, case_input: Path, case_output: Path) -> str:
    output_profile = "full" if study.retention == "full" else "compact"
    return (
        f'python "{study.run_script}" '
        f'--input "{case_input}" '
        f'--output-dir "{case_output}" '
        f'--scenario-id "{study.scenario_id}" '
        f"--days {study.horizon_days} "
        "--skip-map --skip-plots "
        f"--output-profile {output_profile}"
    )


def materialize_cases(study: StudySpec, output_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(output_dir)
    cases_dir = root / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    base_data = load_json(Path(study.input_graph))
    rows: list[dict[str, Any]] = []
    commands: list[str] = []

    for design in build_scenario_designs(study):
        case_dir = cases_dir / design.scenario_id
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input_case.json"
        output_path = case_dir / "simulation_output"
        factors = numeric_factor_values(design)
        case_data = apply_scales(base_data, study.scenario_id, factors)
        write_json(input_path, case_data)
        scenario_manifest = {
            "scenario_id": design.scenario_id,
            "study_id": study.study_id,
            "kind": design.kind,
            "changed_parameters": list(design.changed_parameters),
            "parameter_values": design.parameter_values,
            "applied_factors": factors,
            "input_case": str(input_path),
            "case_output_dir": str(output_path),
        }
        write_json(case_dir / "scenario_manifest.json", scenario_manifest)
        command = command_for_case(study, input_path, output_path)
        commands.append(command)
        rows.append(
            {
                "scenario_id": design.scenario_id,
                "study_id": study.study_id,
                "kind": design.kind,
                "changed_parameters": ",".join(design.changed_parameters),
                "input_case": str(input_path),
                "case_output_dir": str(output_path),
                "parameter_values_json": json.dumps(design.parameter_values, ensure_ascii=False, sort_keys=True),
                "applied_factors_json": json.dumps(factors, ensure_ascii=False, sort_keys=True),
            }
        )

    write_materialized_cases_csv(root / "materialized_cases.csv", rows)
    (root / "run_commands.ps1").write_text("\n".join(commands) + "\n", encoding="utf-8")
    return rows


def write_materialized_cases_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    preferred = [
        "scenario_id",
        "study_id",
        "kind",
        "changed_parameters",
        "input_case",
        "case_output_dir",
        "parameter_values_json",
        "applied_factors_json",
    ]
    fieldnames = [field for field in preferred if field in fieldnames] + [
        field for field in fieldnames if field not in preferred
    ]
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

