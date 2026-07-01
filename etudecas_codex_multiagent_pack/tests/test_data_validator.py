from __future__ import annotations

import pandas as pd

from etudecas.core.config_loader import load_yaml
from etudecas.data.validator import DataValidator

from tests.conftest import ROOT


def test_data_validator_accepts_reference_dataset():
    schema = load_yaml(ROOT / "configs/schemas/fal_aircraft_schema.yaml")
    df = pd.read_csv(ROOT / "data/reference/fal_aircraft_tiny.csv")
    report = DataValidator(schema).validate(df)
    assert report.status == "ok"


def test_data_validator_rejects_missing_required_column():
    schema = load_yaml(ROOT / "configs/schemas/example_schema.yaml")
    df = pd.DataFrame({"date": ["2026-01-01"], "aircraft_id": ["A001"]})
    report = DataValidator(schema).validate(df)
    assert report.status == "reject"
    assert any(issue["column"] == "quality_score" for issue in report.issues)
