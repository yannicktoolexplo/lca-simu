#!/usr/bin/env python3
"""Shared helpers for organizing simulation result artifacts."""

from __future__ import annotations

from pathlib import Path


DATA_DIRNAME = "data"
REPORTS_DIRNAME = "reports"
SUMMARIES_DIRNAME = "summaries"
MAPS_DIRNAME = "maps"
PLOTS_DIRNAME = "plots"


def data_path(base_dir: Path | str, filename: str) -> Path:
    return Path(base_dir) / DATA_DIRNAME / filename


def report_path(base_dir: Path | str, filename: str) -> Path:
    return Path(base_dir) / REPORTS_DIRNAME / filename


def summary_path(base_dir: Path | str, filename: str) -> Path:
    return Path(base_dir) / SUMMARIES_DIRNAME / filename


def map_path(base_dir: Path | str, filename: str) -> Path:
    return Path(base_dir) / MAPS_DIRNAME / filename


def plots_path(base_dir: Path | str) -> Path:
    return Path(base_dir) / PLOTS_DIRNAME


def ensure_standard_dirs(base_dir: Path | str) -> dict[str, Path]:
    root = Path(base_dir)
    paths = {
        "data": root / DATA_DIRNAME,
        "reports": root / REPORTS_DIRNAME,
        "summaries": root / SUMMARIES_DIRNAME,
        "maps": root / MAPS_DIRNAME,
        "plots": root / PLOTS_DIRNAME,
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def resolve_existing_path(preferred: Path, *legacy_candidates: Path) -> Path:
    candidates = (preferred,) + legacy_candidates
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return preferred
