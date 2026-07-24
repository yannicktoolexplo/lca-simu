#!/usr/bin/env python3
"""Build a Monte Carlo calibration file from supplier sensitivity results.

The calibration is deliberately compact: it does not replace the sensitivity
study, it tells the Monte Carlo runner which uncertainty profile is strong
enough for the current model and records the business reason.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILE_RANK = {
    "workshop": 0,
    "risk_probe": 1,
    "stress_probe": 2,
    "breakpoint_probe": 3,
    "legacy": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate Monte Carlo ranges from sensitivity cases.")
    parser.add_argument("--cases-csv", required=True, help="supplier_parameter_sensitivity_cases.csv")
    parser.add_argument("--summary-json", default="", help="Optional supplier_parameter_sensitivity_summary.json")
    parser.add_argument("--output-json", required=True, help="Calibration JSON written for Monte Carlo")
    parser.add_argument(
        "--minimum-profile",
        default="risk_probe",
        choices=["workshop", "risk_probe", "stress_probe", "breakpoint_probe"],
        help="Lower bound for the recommended profile when sensitivity is available.",
    )
    return parser.parse_args()


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(value):
        return default
    return value


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def kpi(row: dict[str, str], *names: str, default: float = 0.0) -> float:
    for name in names:
        if name in row and str(row.get(name) or "") != "":
            return to_float(row.get(name), default)
    return default


def family_from_parameter(row: dict[str, str]) -> str:
    group = str(row.get("parameter_group") or row.get("parameter") or row.get("parameter_key") or "").lower()
    key = str(row.get("parameter_key") or "").lower()
    token = f"{group} {key}"
    if "lead" in token:
        return "supplier_lead"
    if "reliability" in token or "fiabil" in token:
        return "supplier_reliability"
    if "external" in token or "appro" in token or "upstream" in token:
        return "external_procurement"
    if "capacity" in token or "capac" in token:
        return "supplier_capacity"
    if "stock" in token:
        return "supplier_stock"
    if "cost" in token or "cout" in token:
        return "supplier_cost"
    if "demand" in token:
        return "demand"
    return "other"


def supplier_from_parameter(row: dict[str, str]) -> str:
    key = str(row.get("parameter_key") or "")
    if "::" in key:
        return key.split("::", 1)[1]
    return "GLOBAL"


def case_impact(row: dict[str, str], baseline: dict[str, str]) -> dict[str, float]:
    base_availability = kpi(baseline, "kpi::product_availability", "kpi::fill_rate", default=1.0)
    availability = kpi(row, "kpi::product_availability", "kpi::fill_rate", default=base_availability)
    base_backlog = kpi(baseline, "kpi::ending_backlog", default=0.0)
    backlog = kpi(row, "kpi::ending_backlog", default=base_backlog)
    base_cost = max(1.0, kpi(baseline, "kpi::total_cost", default=1.0))
    cost = kpi(row, "kpi::total_cost", default=base_cost)
    demand = max(1.0, kpi(baseline, "kpi::measured_required_total", "kpi::total_demand", default=1.0))
    base_replanning_rate = kpi(baseline, "kpi::production_replanning_rate", default=0.0)
    replanning_rate = kpi(row, "kpi::production_replanning_rate", default=base_replanning_rate)
    base_replanning_count = kpi(baseline, "kpi::production_replanning_count", default=0.0)
    replanning_count = kpi(row, "kpi::production_replanning_count", default=base_replanning_count)
    base_stockout_days = kpi(baseline, "kpi::raw_material_stockout_days", default=0.0)
    stockout_days = kpi(row, "kpi::raw_material_stockout_days", default=base_stockout_days)
    base_material_delay_days = kpi(baseline, "kpi::material_delay_days", default=0.0)
    material_delay_days = kpi(row, "kpi::material_delay_days", default=base_material_delay_days)
    base_binding = kpi(baseline, "kpi::total_supplier_capacity_binding_qty", default=0.0)
    binding = kpi(row, "kpi::total_supplier_capacity_binding_qty", default=base_binding)

    return {
        "availability_drop": max(0.0, base_availability - availability),
        "backlog_ratio": max(0.0, backlog - base_backlog) / demand,
        "cost_increase_ratio": max(0.0, cost - base_cost) / base_cost,
        "replanning_rate_delta": max(0.0, replanning_rate - base_replanning_rate),
        "replanning_count_delta": max(0.0, replanning_count - base_replanning_count),
        "stockout_days_delta": max(0.0, stockout_days - base_stockout_days),
        "material_delay_days_delta": max(0.0, material_delay_days - base_material_delay_days),
        "supplier_capacity_binding_ratio": max(0.0, binding - base_binding) / demand,
    }


def normalized_score(impact: dict[str, float]) -> float:
    """Business-oriented spread score.

    1.0 means the sensitivity test already found a clearly visible operational
    effect. Values well below 1.0 mean the system is buffered and Monte Carlo
    should use stronger ranges to reveal fragility.
    """

    service = impact["availability_drop"] / 0.03
    backlog = impact["backlog_ratio"] / 0.015
    cost = impact["cost_increase_ratio"] / 0.12
    replanning = max(impact["replanning_rate_delta"] / 0.03, impact["replanning_count_delta"] / 30.0)
    material = max(impact["stockout_days_delta"], impact["material_delay_days_delta"]) / 30.0
    primary = max(service, backlog, cost, replanning, material)

    # Supplier-capacity binding is useful as an early warning, but it is not a
    # final business KPI by itself. Keep it as a secondary signal so it does not
    # hide a flat availability/backlog/cost response behind a huge internal flow.
    capacity_warning = min(1.0, impact["supplier_capacity_binding_ratio"] / 0.03) * 0.25
    return max(primary, capacity_warning)


def recommendation_from_strength(strength: float, minimum_profile: str) -> str:
    min_rank = PROFILE_RANK.get(minimum_profile, 1)
    if strength < 0.15:
        profile = "breakpoint_probe"
    elif strength < 0.55:
        profile = "stress_probe"
    elif strength < 1.50:
        profile = "stress_probe"
    else:
        profile = "risk_probe"
    if PROFILE_RANK[profile] < min_rank:
        return minimum_profile
    return profile


def build_calibration(
    *,
    cases_csv: Path,
    summary_json: Path | None,
    minimum_profile: str,
) -> dict[str, Any]:
    rows = read_csv_rows(cases_csv)
    if not rows:
        return {
            "schema_version": "etudecas.montecarlo_sensitivity_calibration.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "empty",
            "recommended_profile": "breakpoint_probe",
            "reason": "No sensitivity rows were available; use a strong exploratory profile.",
        }

    baseline = next((row for row in rows if str(row.get("case_id") or "").lower() == "baseline"), rows[0])
    non_baseline = [
        row
        for row in rows
        if str(row.get("case_id") or "").lower() != "baseline"
        and str(row.get("status") or "ok").lower() == "ok"
    ]

    top_cases: list[dict[str, Any]] = []
    family_scores: dict[str, float] = defaultdict(float)
    supplier_scores: dict[str, float] = defaultdict(float)
    max_impact = {
        "availability_drop": 0.0,
        "backlog_ratio": 0.0,
        "cost_increase_ratio": 0.0,
        "replanning_rate_delta": 0.0,
        "replanning_count_delta": 0.0,
        "stockout_days_delta": 0.0,
        "material_delay_days_delta": 0.0,
        "supplier_capacity_binding_ratio": 0.0,
    }

    for row in non_baseline:
        impact = case_impact(row, baseline)
        score = normalized_score(impact)
        family = family_from_parameter(row)
        supplier = supplier_from_parameter(row)
        family_scores[family] = max(family_scores[family], score)
        supplier_scores[supplier] = max(supplier_scores[supplier], score)
        for key, value in impact.items():
            max_impact[key] = max(max_impact[key], value)
        top_cases.append(
            {
                "case_id": row.get("case_id"),
                "parameter_key": row.get("parameter_key"),
                "parameter_group": row.get("parameter_group"),
                "parameter_label": row.get("parameter_label"),
                "level": to_float(row.get("level"), 1.0),
                "family": family,
                "supplier": supplier,
                "score": round(score, 6),
                "impact": {k: round(v, 8) for k, v in impact.items()},
            }
        )

    top_cases.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    strength = float(top_cases[0]["score"]) if top_cases else 0.0
    recommended = recommendation_from_strength(strength, minimum_profile)
    summary = read_json(summary_json) if summary_json else {}
    reason = (
        "Sensitivity found visible KPI movement; Monte Carlo can stay in a readable stress range."
        if strength >= 0.55
        else "Sensitivity barely moved the KPI; Monte Carlo must use stronger ranges to expose weak points."
    )
    if strength < 0.15:
        reason = "Sensitivity was almost flat; Monte Carlo is escalated to breakpoint probing."

    return {
        "schema_version": "etudecas.montecarlo_sensitivity_calibration.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "cases_csv": str(cases_csv),
        "summary_json": str(summary_json) if summary_json else "",
        "sensitivity_days": summary.get("days"),
        "sensitivity_groups": summary.get("groups"),
        "selected_suppliers": summary.get("selected_suppliers"),
        "case_count": len(non_baseline),
        "baseline": {
            "availability": kpi(baseline, "kpi::product_availability", "kpi::fill_rate", default=1.0),
            "total_cost": kpi(baseline, "kpi::total_cost", default=0.0),
            "total_demand": kpi(baseline, "kpi::measured_required_total", "kpi::total_demand", default=0.0),
            "replanning_rate": kpi(baseline, "kpi::production_replanning_rate", default=0.0),
        },
        "recommended_profile": recommended,
        "minimum_profile": minimum_profile,
        "sensitivity_strength_score": round(strength, 6),
        "reason": reason,
        "max_impact_observed": {k: round(v, 8) for k, v in max_impact.items()},
        "family_priority": [
            {"family": family, "score": round(score, 6)}
            for family, score in sorted(family_scores.items(), key=lambda kv: kv[1], reverse=True)
            if score > 0
        ],
        "supplier_priority": [
            {"supplier": supplier, "score": round(score, 6)}
            for supplier, score in sorted(supplier_scores.items(), key=lambda kv: kv[1], reverse=True)
            if supplier and supplier != "GLOBAL" and score > 0
        ][:20],
        "top_cases": top_cases[:20],
        "selection_rule": (
            "If sensitivity is flat, escalate to breakpoint_probe; if it moves KPI moderately, use stress_probe; "
            "if it is already very disruptive, keep risk_probe to preserve readable Monte Carlo envelopes."
        ),
    }


def main() -> None:
    args = parse_args()
    calibration = build_calibration(
        cases_csv=Path(args.cases_csv),
        summary_json=Path(args.summary_json) if args.summary_json else None,
        minimum_profile=args.minimum_profile,
    )
    write_json(Path(args.output_json), calibration)
    print(
        "[OK] Monte Carlo calibration: "
        f"{Path(args.output_json).resolve()} profile={calibration.get('recommended_profile')} "
        f"score={calibration.get('sensitivity_strength_score')}",
        flush=True,
    )


if __name__ == "__main__":
    main()
