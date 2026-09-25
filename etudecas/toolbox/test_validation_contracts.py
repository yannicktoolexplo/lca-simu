"""Generic validation contracts; these do not define simulation KPI policy."""
import pandas as pd
import pytest

from etudecas.toolbox.validation_contracts import (
    DataValidator, ResultValidator, ValidationReport, weighted_mean, simple_mean,
)


@pytest.mark.parametrize('value', [1.5, float('inf'), float('nan')])
def test_count_column_rejects_nonphysical_values(value):
    report = DataValidator({'columns': {'pieces': {'type': 'integer', 'required': True}}}).validate(pd.DataFrame({'pieces': [value]}))
    assert report.status == 'reject'


@pytest.mark.parametrize('weights', [{'a': 2, 'b': -1}, {'a': float('nan')}, {'a': float('inf')}, {'a': 0}])
def test_invalid_weights_cannot_make_a_score(weights):
    with pytest.raises(ValueError):
        weighted_mean(pd.DataFrame({'a': [1], 'b': [0]}), weights)


@pytest.mark.parametrize('rules', [
    {'score_bounds': {'enabled': True, 'columns': ['score']}},
    {'temporal_order': {'enabled': True, 'time_column': 'date'}},
    {'business_rules': [{'when': {'column': 'a'}, 'then_not': {'column': 'b'}}]},
])
def test_missing_required_evidence_rejects(rules):
    assert ResultValidator(rules).validate(pd.DataFrame({'unrelated': [1]})).status == 'reject'


@pytest.mark.parametrize('value,status', [(0, 'ok'), (1, 'ok'), (1.2, 'reject'), (float('nan'), 'reject')])
def test_score_bounds(value, status):
    assert ResultValidator({'score_bounds': {'enabled': True, 'columns': ['score']}}).validate(pd.DataFrame({'score': [value]})).status == status


def test_schema_positive_and_missing_column():
    validator = DataValidator({'columns': {'count': {'type': 'integer', 'required': True, 'min': 0, 'max': 4}}})
    frame = pd.DataFrame({'count': [0, 4]})
    assert validator.validate_or_raise(frame) is frame
    with pytest.raises(ValueError):
        validator.validate_or_raise(pd.DataFrame({'other': [1]}))
    assert validator.validate(pd.DataFrame({'count': [5]})).status == 'reject'


def test_weighted_mean_positive_and_missing_inputs():
    frame = pd.DataFrame({'a': [1.0], 'b': [0.0]})
    assert weighted_mean(frame, {'a': 3, 'b': 1}).tolist() == [0.75]
    assert simple_mean(frame, ['a', 'b']).tolist() == [0.5]
    with pytest.raises(ValueError):
        weighted_mean(frame, {'missing': 1})
    with pytest.raises(ValueError):
        weighted_mean(pd.DataFrame({'a': [float('inf')]}), {'a': 1})


def test_business_and_temporal_rules():
    temporal = ResultValidator({'temporal_order': {'enabled': True, 'time_column': 'date'}})
    assert temporal.validate(pd.DataFrame({'date': ['2026-02-01', '2026-01-01']})).status == 'warning'
    assert temporal.validate(pd.DataFrame({'date': ['invalid']})).status == 'reject'
    rules = {'business_rules': [{'when': {'column': 'a', 'value': 1}, 'then_not': {'column': 'b', 'value': 2}, 'severity': 'critical'}]}
    assert ResultValidator(rules).validate(pd.DataFrame({'a': [1], 'b': [2]})).status == 'reject'


def test_report_serialization(tmp_path):
    import json
    report = ValidationReport()
    report.add_check('schema', 'passed')
    assert report.status == 'ok'
    report.add_issue('warning', 'review')
    assert report.status == 'warning'
    report.add_issue('critical', 'missing')
    assert report.status == 'reject'
    target = report.write_json(tmp_path / 'report.json')
    assert json.loads(target.read_text(encoding='utf-8')) == report.to_dict()
