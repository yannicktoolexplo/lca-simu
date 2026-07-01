from __future__ import annotations

import pandas as pd

from etudecas_agentkit.core.config_loader import load_yaml
from etudecas_agentkit.validation.result_checks import ResultValidator

from tests.conftest import ROOT


def test_result_validator_accepts_scores_in_bounds():
    rules = load_yaml(ROOT / "configs/validation/validation_rules.yaml")
    df = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "aircraft_id": ["A001", "A001"],
            "quality": [0.8, 0.9],
            "delay": [0.7, 0.6],
            "stress": [0.4, 0.5],
            "performance": [0.7, 0.75],
            "delay_days": [2, 3],
        }
    )
    report = ResultValidator(rules).validate(df)
    assert report.status == "ok"


def test_result_validator_rejects_score_out_of_bounds():
    rules = load_yaml(ROOT / "configs/validation/validation_rules.yaml")
    df = pd.DataFrame(
        {
            "date": ["2026-01-01"],
            "aircraft_id": ["A001"],
            "quality": [1.2],
            "delay": [0.5],
            "stress": [0.5],
            "performance": [0.5],
            "delay_days": [1],
        }
    )
    report = ResultValidator(rules).validate(df)
    assert report.status == "reject"
