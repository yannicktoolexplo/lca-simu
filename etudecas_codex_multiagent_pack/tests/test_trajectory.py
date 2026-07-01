from __future__ import annotations

import pandas as pd

from etudecas_agentkit.core.case import CaseStudy
from etudecas_agentkit.kpi.engine import KPIEngine
from etudecas_agentkit.trajectory.builder import TrajectoryBuilder

from tests.conftest import ROOT


def test_trajectory_builder_sorts_and_keeps_dimensions():
    case = CaseStudy.from_yaml(ROOT / "configs/cases/example_minimal.yaml")
    df = pd.read_csv(ROOT / "data/reference/fal_aircraft_tiny.csv")
    kpi_df = KPIEngine(case.kpi_tree).compute(df)
    trajectory = TrajectoryBuilder(case.trajectory_config).build(kpi_df)
    assert list(trajectory.columns) == ["date", "aircraft_id", "quality", "delay", "stress"]
    assert trajectory["date"].is_monotonic_increasing
