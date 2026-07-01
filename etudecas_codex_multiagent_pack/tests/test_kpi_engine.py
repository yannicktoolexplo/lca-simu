from __future__ import annotations

import pandas as pd

from etudecas.core.case import CaseStudy
from etudecas.kpi.engine import KPIEngine

from tests.conftest import ROOT


def test_kpi_engine_computes_elementary_and_composite_scores():
    case = CaseStudy.from_yaml(ROOT / "configs/cases/example_minimal.yaml")
    df = pd.read_csv(ROOT / "data/reference/fal_aircraft_tiny.csv")
    result = KPIEngine(case.kpi_tree).compute(df)
    assert {"quality", "delay", "stress", "performance"}.issubset(result.columns)
    assert result["performance"].between(0, 1).all()
