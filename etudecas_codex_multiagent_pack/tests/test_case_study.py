from __future__ import annotations

from etudecas_agentkit.core.case import CaseStudy

from .conftest import ROOT


def test_case_study_loads_minimal_config():
    case = CaseStudy.from_yaml(ROOT / "configs/cases/example_minimal.yaml")
    assert case.case_id == "example_minimal"
    assert case.data_config["schema"] == "configs/schemas/example_schema.yaml"
    assert "performance" in case.kpi_tree
