"""Compatibility contracts for the three relocated source-comparison reports."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
REPORTS = (
    "report_component_immobilized_stock",
    "report_finished_goods_stock_value",
    "audit_source_truth_alignment",
)


@pytest.mark.parametrize("name", REPORTS)
def test_legacy_imports_share_canonical_objects_and_configuration(name, monkeypatch, tmp_path):
    canonical = importlib.import_module(f"etudecas.simulation.analysis.{name}")
    legacy = importlib.import_module(f"etudecas.analysis.from_simulation.{name}")

    assert legacy is canonical
    assert legacy.build_report is canonical.build_report
    assert canonical.REPO_ROOT == REPO_ROOT
    assert canonical.SOURCE_DIR == REPO_ROOT / "etudecas/data/source"
    # Existing callers that replace a source directory through the old module
    # must affect the functions' actual global namespace, not a copied wrapper.
    monkeypatch.setattr(legacy, "SOURCE_DIR", tmp_path)
    assert canonical.build_report.__globals__["SOURCE_DIR"] == tmp_path


def test_component_report_retains_its_historical_default_output_directory():
    from etudecas.simulation.analysis import report_component_immobilized_stock as report

    assert report.DEFAULT_OUTPUT_DIR == (
        REPO_ROOT / "etudecas/analysis/from_simulation/result/component_immobilized_stock"
    )


@pytest.mark.parametrize("name", REPORTS)
@pytest.mark.parametrize("mode", ("direct", "module"))
def test_historical_and_canonical_cli_help_are_equivalent(name, mode, tmp_path):
    environment = dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
    outputs = []
    for package in ("etudecas.analysis.from_simulation", "etudecas.simulation.analysis"):
        if mode == "direct":
            target = REPO_ROOT / Path(*package.split(".")) / f"{name}.py"
            command = [sys.executable, "-B", str(target), "--help"]
            cwd = tmp_path  # Exercise the bootstrap independently of repository cwd.
        else:
            command = [sys.executable, "-B", "-m", f"{package}.{name}", "--help"]
            cwd = REPO_ROOT
        process = subprocess.run(
            command, cwd=cwd, env=environment, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20, check=False,
        )
        assert process.returncode == 0, process.stderr
        assert process.stderr == ""
        assert "--run-dir" in process.stdout
        outputs.append(process.stdout)
    assert outputs[0] == outputs[1]
