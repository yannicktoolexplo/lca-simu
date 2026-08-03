from __future__ import annotations

from etudecas_agentkit.cli import run

from .conftest import ROOT


def test_end_to_end_case_runs():
    run(ROOT / "configs/cases/example_minimal.yaml")
    assert (ROOT / "outputs/reports/validation_report.json").exists()
    assert (ROOT / "outputs/figures/trajectory_3d.png").exists()
