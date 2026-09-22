from pathlib import Path
import shutil

import pandas as pd
import pytest

from etudecas_agentkit import cli
from etudecas_agentkit.data.validator import DataValidator
from etudecas_agentkit.kpi.aggregators import weighted_mean
from etudecas_agentkit.kpi.normalizers import bounded_score
from etudecas_agentkit.validation.result_checks import ResultValidator
from etudecas_agentkit.validation.report import ValidationReport


@pytest.mark.parametrize("value", [1.5, float("inf"), float("nan")])
def test_count_column_rejects_nonphysical_values(value):
    report = DataValidator({"columns": {"pieces": {"type": "integer", "required": True}}}).validate(pd.DataFrame({"pieces": [value]}))
    assert report.status == "reject"


@pytest.mark.parametrize("weights", [{"a": 2, "b": -1}, {"a": float("nan")}, {"a": float("inf")}, {"a": 0}])
def test_invalid_weights_cannot_make_a_score(weights):
    with pytest.raises(ValueError):
        weighted_mean(pd.DataFrame({"a": [1], "b": [0]}), weights)


def test_inverted_normalization_is_rejected():
    with pytest.raises(ValueError):
        bounded_score(pd.Series([2]), direction="maximize", target=1, min_value=3, max_value=4)


@pytest.mark.parametrize("rules", [
    {"score_bounds": {"enabled": True, "columns": ["score"]}},
    {"temporal_order": {"enabled": True, "time_column": "date"}},
    {"business_rules": [{"when": {"column": "a"}, "then_not": {"column": "b"}}]},
])
def test_missing_required_evidence_rejects(rules):
    assert ResultValidator(rules).validate(pd.DataFrame({"unrelated": [1]})).status == "reject"


@pytest.fixture
def examples(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for folder in ("configs", "data"):
        shutil.copytree(root / folder, tmp_path / folder)
    return tmp_path


@pytest.mark.parametrize("case", ["example_minimal", "fal_aircraft", "supply_chain_bullwhip"])
def test_each_shipped_example_passes_its_own_rules(examples, case):
    cli.run(examples / "configs/cases" / (case + ".yaml"))
    runs = list((examples / "outputs").glob("*/*"))
    assert len(runs) == 1
    assert (runs[0] / "validation_report.json").is_file()
    assert list(runs[0].glob("*.png"))


def test_cli_reject_stops_before_publishing_figures(examples, monkeypatch):
    report = ValidationReport(name="injected")
    report.add_issue("critical", "Intentional invalid result")
    monkeypatch.setattr(cli.ResultValidator, "validate", lambda *args: report)
    with pytest.raises(SystemExit, match="Results rejected"):
        cli.run(examples / "configs/cases/example_minimal.yaml")
    assert not list((examples / "outputs").rglob("*.png"))
    assert list((examples / "outputs").rglob("validation_report.json"))
