"""Data loading helpers for map visualizations."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_json_dict(json_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def output_root_from_csv(csv_path: Path) -> Path:
    if csv_path.parent.name == "data":
        return csv_path.parent.parent
    return csv_path.parent


def read_timeline_horizon_days(output_root: Path) -> int | None:
    summary = load_json_dict(output_root / "summaries" / "first_simulation_summary.json")
    for key in ("timeline_days", "sim_days", "total_simulated_timeline_days"):
        value = _to_float(summary.get(key))
        if value is not None and value > 0:
            return int(math.ceil(value))
    return None
