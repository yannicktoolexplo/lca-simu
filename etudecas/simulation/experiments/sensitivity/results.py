"""Normalize heterogeneous sensitivity result files into a common metrics table."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Iterable


CANONICAL_KPI_SOURCES: dict[str, tuple[str, ...]] = {
    "fill_rate": ("kpi::fill_rate", "fill_rate"),
    "ending_backlog": ("kpi::ending_backlog", "ending_backlog"),
    "max_backlog": ("kpi::max_backlog", "max_backlog"),
    "total_cost": ("kpi::total_cost", "total_cost"),
    "avg_inventory": ("kpi::avg_inventory", "avg_inventory"),
    "total_demand": ("kpi::total_demand", "total_demand"),
    "total_served": ("kpi::total_served", "total_served"),
    "total_shipped": ("kpi::total_shipped", "total_shipped"),
    "production_replanning_count": (
        "kpi::production_replanning_count",
        "production_replanning_count",
        "input_delay_count",
    ),
    "input_delay_volume": ("kpi::input_delay_volume", "input_delay_volume", "input_delay_volume_qty"),
    "raw_material_stockout_days": ("kpi::raw_material_stockout_days", "raw_material_stockout_days"),
    "material_delay_days": ("kpi::material_delay_days", "material_delay_days"),
    "inventory_cost": ("kpi::inventory_cost", "inventory_cost"),
    "product_availability": ("kpi::product_availability", "product_availability"),
    "line_adherence": ("kpi::line_adherence", "line_adherence"),
    "line_nervousness": ("kpi::line_nervousness", "line_nervousness"),
    "total_external_procured_ordered_qty": (
        "kpi::total_external_procured_ordered_qty",
        "total_external_procured_ordered_qty",
        "external_procured_ordered_qty",
    ),
    "total_external_procurement_cost": (
        "kpi::total_external_procurement_cost",
        "total_external_procurement_cost",
        "external_procurement_cost",
    ),
    "total_unreliable_loss_qty": ("kpi::total_unreliable_loss_qty", "total_unreliable_loss_qty"),
    "impact_score": ("kpi::impact_score", "impact_score", "impact_metier_score"),
    "impact_pct": ("kpi::impact_pct", "impact_pct", "impact_metier_pct"),
    "decision_score": ("kpi::decision_score", "score_decisionnel_modele"),
    "decision_pct": ("kpi::decision_pct", "score_decisionnel_pct"),
}

CANONICAL_DELTA_SOURCES: dict[str, tuple[str, ...]] = {
    "fill_rate": ("fill_rate_delta",),
    "fill_rate_pts": ("fill_rate_delta_pts",),
    "product_availability": ("product_availability_delta",),
    "product_availability_pts": ("product_availability_delta_pts",),
    "line_adherence": ("line_adherence_delta",),
    "line_adherence_pts": ("line_adherence_delta_pts",),
    "line_nervousness": ("line_nervousness_delta",),
    "production_replanning_count": ("production_replanning_delta",),
    "raw_material_stockout_days": ("raw_material_stockout_days_delta",),
    "material_delay_days": ("material_delay_days_delta",),
    "total_cost": ("total_cost_delta",),
    "inventory_cost": ("inventory_cost_delta",),
    "total_unreliable_loss_qty": ("total_unreliable_loss_delta",),
    "total_shipped": ("total_shipped_delta",),
    "impact": ("impact_metier_delta",),
}

CANONICAL_DELTA_PCT_SOURCES: dict[str, tuple[str, ...]] = {
    "total_cost": ("total_cost_delta_pct",),
}

DESIGN_PREFIXES = (
    "param::",
    "factor::",
    "policy::",
    "supplier_node::",
    "supplier_capacity_node::",
    "capacity_node::",
    "demand_item::",
    "edge_src_lead_time::",
    "edge_src_reliability::",
)

IDENTITY_FIELDS = (
    "case_id",
    "scenario_id",
    "study_id",
    "status",
    "case_input",
    "case_output_dir",
    "source_result_dir",
    "source_dataset",
    "source_file",
)

DIMENSION_FIELDS = (
    "parameter_group",
    "parameter_key",
    "parameter_label",
    "factor_value",
    "level",
    "family",
    "risk_family",
    "supplier_id",
    "node_id",
    "target",
    "scope",
    "label",
    "kind",
    "severity",
    "category",
    "direction",
    "study",
    "risk_type",
    "multiplier",
    "event_start_day",
    "event_end_day",
)


def to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _first_present(row: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row and row.get(name) not in (None, ""):
            return row.get(name)
    return None


def normalize_metric_row(row: dict[str, Any], *, study_id: str = "", source_file: str = "") -> dict[str, Any]:
    case_id = str(_first_present(row, ("case_id", "scenario_id", "id", "case")) or "").strip()
    scenario_id = str(_first_present(row, ("scenario_id", "case_id", "id", "case")) or case_id).strip()
    error_text = str(row.get("error") or "").strip()
    status = str(row.get("status") or ("error" if error_text else "ok"))
    source_path = Path(source_file) if source_file else None
    normalized: dict[str, Any] = {
        "case_id": case_id,
        "scenario_id": scenario_id,
        "study_id": str(row.get("study_id") or row.get("study") or study_id),
        "status": status,
        "case_input": str(row.get("case_input") or row.get("input_case") or ""),
        "case_output_dir": str(row.get("case_output_dir") or row.get("output_dir") or row.get("case_dir") or ""),
        "source_result_dir": source_path.parent.name if source_path else "",
        "source_dataset": source_path.name if source_path else "",
        "source_file": source_file,
    }

    for field in DIMENSION_FIELDS:
        if field in row and row.get(field) not in (None, ""):
            normalized[field] = row.get(field)

    for key, value in row.items():
        if key.startswith(DESIGN_PREFIXES):
            normalized[key] = value

    for canonical, sources in CANONICAL_KPI_SOURCES.items():
        number = to_number(_first_present(row, sources))
        if number is not None:
            normalized[f"kpi::{canonical}"] = number

    for canonical, sources in CANONICAL_DELTA_SOURCES.items():
        number = to_number(_first_present(row, sources))
        if number is not None:
            normalized[f"delta::{canonical}"] = number

    for canonical, sources in CANONICAL_DELTA_PCT_SOURCES.items():
        number = to_number(_first_present(row, sources))
        if number is not None:
            normalized[f"delta_pct::{canonical}"] = number

    for key, value in row.items():
        if key.startswith("kpi::"):
            number = to_number(value)
            if number is not None:
                normalized[key] = number
        elif key.startswith("delta::"):
            number = to_number(value)
            if number is not None:
                normalized[key.replace("delta::kpi::", "delta::")] = number
        elif key.startswith("delta_pct::"):
            number = to_number(value)
            if number is not None:
                normalized[key.replace("delta_pct::kpi::", "delta_pct::")] = number
        elif key.startswith("guard::"):
            number = to_number(value)
            normalized[key] = number if number is not None else value

    return normalized


def ingest_case_csvs(paths: list[str | Path], *, study_id: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        source = str(path)
        for row in read_csv_rows(path):
            rows.append(normalize_metric_row(row, study_id=study_id, source_file=source))
    return rows


def summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if str(row.get("status") or "ok").lower() in {"ok", "complete", "completed"}]
    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "ok_count": len(ok_rows),
        "error_count": len(rows) - len(ok_rows),
        "kpis": {},
    }
    kpi_keys = sorted({key for row in rows for key in row if key.startswith("kpi::")})
    for key in kpi_keys:
        values = [to_number(row.get(key)) for row in ok_rows]
        numeric = [value for value in values if value is not None]
        if not numeric:
            continue
        summary["kpis"][key] = {
            "min": min(numeric),
            "max": max(numeric),
            "mean": sum(numeric) / len(numeric),
            "count": len(numeric),
        }
    return summary


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    preferred = list(IDENTITY_FIELDS) + list(DIMENSION_FIELDS)
    fieldnames = [field for field in preferred if field in fieldnames] + [
        field for field in fieldnames if field not in preferred
    ]
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def registry_rows(metrics_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in metrics_rows:
        out.append({field: row.get(field, "") for field in IDENTITY_FIELDS if field in row})
    return out
