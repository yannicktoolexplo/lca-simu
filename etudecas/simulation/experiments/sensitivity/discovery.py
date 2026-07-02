"""Discovery helpers for historical sensitivity result files."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from .results import ingest_case_csvs, registry_rows, summarize_metrics, write_csv, write_json


CASE_LEVEL_FILENAMES = {
    "scenario_results.csv",
    "sensitivity_cases.csv",
    "local_cases.csv",
    "stress_cases.csv",
    "threshold_sweep_cases.csv",
    "supplier_parameter_sensitivity_cases.csv",
    "supplier_risk_campaign_cases.csv",
}

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    "cases",
    "data",
    "maps",
    "plots",
    "reports",
    "simulation_output",
    "summaries",
}


def discover_case_csvs(root: str | Path) -> list[Path]:
    """Return case-level CSVs without traversing heavy simulation outputs."""

    root_path = Path(root)
    if root_path.is_file():
        return [root_path] if root_path.name in CASE_LEVEL_FILENAMES else []
    if not root_path.exists():
        return []

    found: list[Path] = []
    for current, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIR_NAMES]
        current_path = Path(current)
        for filename in filenames:
            if filename in CASE_LEVEL_FILENAMES:
                found.append(current_path / filename)
    return sorted(found)


def source_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.append(
            {
                "source_result_dir": path.parent.name,
                "source_dataset": path.name,
                "source_file": str(path),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return rows


def consolidate_case_csvs(root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = discover_case_csvs(root)
    metrics_rows = []
    for path in paths:
        metrics_rows.extend(ingest_case_csvs([path], study_id=path.parent.name))

    write_csv(output / "metrics.csv", metrics_rows)
    write_csv(output / "registry.csv", registry_rows(metrics_rows))
    write_source_csv(output / "source_files.csv", source_rows(paths))
    summary = summarize_metrics(metrics_rows)
    summary["source_file_count"] = len(paths)
    summary["source_files"] = [str(path) for path in paths]
    write_json(output / "summary.json", summary)
    return {
        "paths": paths,
        "metrics_rows": metrics_rows,
        "summary": summary,
        "output_dir": output,
    }


def write_source_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_result_dir", "source_dataset", "source_file", "size_bytes"]
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

