from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


SENSITIVITY_LEGACY_KEYS = (
    "factory_sensitivity_hover_images",
    "supplier_sensitivity_hover_images",
    "distribution_center_sensitivity_hover_images",
    "factory_structural_hover_images",
    "supplier_structural_hover_images",
    "distribution_center_structural_hover_images",
    "supplier_parameter_sensitivity_nodes",
    "realistic_sensitivity",
    "threshold_sensitivity",
)


def build_sensitivity_payload_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Describe sensitivity payload sections without copying their panels."""

    return {
        "domain": "sensitivity",
        "generic_outputs": ["diagnostics"],
        "legacy_keys": [key for key in SENSITIVITY_LEGACY_KEYS if key in payload],
        "counts": {
            "factory_panels": _count_mapping(payload.get("factory_sensitivity_hover_images")),
            "supplier_panels": _count_mapping(payload.get("supplier_sensitivity_hover_images")),
            "dc_panels": _count_mapping(payload.get("distribution_center_sensitivity_hover_images")),
            "factory_structural_panels": _count_mapping(payload.get("factory_structural_hover_images")),
            "supplier_structural_panels": _count_mapping(payload.get("supplier_structural_hover_images")),
            "dc_structural_panels": _count_mapping(payload.get("distribution_center_structural_hover_images")),
            "supplier_parameter_nodes": _count_mapping(payload.get("supplier_parameter_sensitivity_nodes")),
        },
    }


def build_sensitivity_generic_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Project legacy sensitivity sections to the generic map contract."""

    return {
        "diagnostics": {
            "realistic": payload.get("realistic_sensitivity", {}) or {},
            "threshold": payload.get("threshold_sensitivity", {}) or {},
            "supplier_parameter_nodes": payload.get("supplier_parameter_sensitivity_nodes", {}) or {},
        }
    }


def _count_mapping(value: Any) -> int:
    return len(value) if isinstance(value, dict) else 0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


def case_rows_by_id(case_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        str(row.get("case_id") or ""): row
        for row in case_rows
        if str(row.get("status") or "").lower() == "ok"
    }


def first_case_row(
    by_case_id: dict[str, dict[str, str]],
    *case_ids: str,
) -> dict[str, str] | None:
    for case_id in case_ids:
        row = by_case_id.get(case_id)
        if row is not None:
            return row
    return None


def baseline_sensitivity_row(by_case_id: dict[str, dict[str, str]]) -> dict[str, str] | None:
    return first_case_row(
        by_case_id,
        "baseline",
        "baseline_baseline_base",
    )


def case_multiplier_value(case_row: dict[str, str] | None) -> float | None:
    if not case_row:
        return None
    return _to_float(case_row.get("value")) or _to_float(case_row.get("factor_value"))


def case_output_dir(case_row: dict[str, str] | None) -> Path | None:
    if not case_row:
        return None
    raw = str(case_row.get("case_output_dir") or "").strip()
    return Path(raw) if raw else None


def safe_case_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def kpi_from_case(case_row: dict[str, str] | None, kpi_name: str) -> float | None:
    if not case_row:
        return None
    value = _to_float(case_row.get(f"kpi::{kpi_name}"))
    if value is None or math.isnan(value):
        return None
    return value


def multiplier_label(value: float | None, fallback: str) -> str:
    if value is None:
        return fallback
    if abs(value - 1.0) <= 1e-9:
        return "Base"
    return f"x{value:.2f}"


def align_series(
    baseline_points: list[tuple[int, float]],
    scenario_points: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    base_map = {day: value for day, value in baseline_points}
    scen_map = {day: value for day, value in scenario_points}
    days = sorted(set(base_map) | set(scen_map))
    return [(day, scen_map.get(day, 0.0) - base_map.get(day, 0.0)) for day in days]


def cumulative_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    total = 0.0
    out: list[tuple[int, float]] = []
    for day, value in points:
        total += value
        out.append((day, total))
    return out


def local_signal_strength(
    baseline_row: dict[str, str] | None,
    low_row: dict[str, str] | None,
    high_row: dict[str, str] | None,
) -> tuple[float, float]:
    base_fill = kpi_from_case(baseline_row, "fill_rate") or 0.0
    base_backlog = kpi_from_case(baseline_row, "ending_backlog") or 0.0
    fill_impact = max(
        abs((kpi_from_case(low_row, "fill_rate") or base_fill) - base_fill),
        abs((kpi_from_case(high_row, "fill_rate") or base_fill) - base_fill),
    )
    backlog_impact = max(
        abs((kpi_from_case(low_row, "ending_backlog") or base_backlog) - base_backlog),
        abs((kpi_from_case(high_row, "ending_backlog") or base_backlog) - base_backlog),
    )
    return fill_impact, backlog_impact
