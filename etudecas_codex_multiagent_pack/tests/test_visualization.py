from __future__ import annotations

import pandas as pd

from etudecas_agentkit.core.config_loader import load_yaml
from etudecas_agentkit.visualization.figure_factory import FigureFactory

from .conftest import ROOT


def test_figure_factory_generates_3d_trajectory(tmp_path):
    spec = load_yaml(ROOT / "configs/visuals/trajectory_3d.yaml")
    spec["output"]["path"] = "trajectory.png"
    df = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "aircraft_id": ["A001", "A001"],
            "quality": [0.8, 0.9],
            "delay": [0.7, 0.6],
            "stress": [0.4, 0.5],
        }
    )
    output = FigureFactory(spec).render(df, base_dir=tmp_path)
    assert output.exists()
    assert output.stat().st_size > 0
