"""Manual in-memory programme comparisons; no filesystem or simulation fixture."""
from copy import deepcopy
from fractions import Fraction
import json

import pytest

from etudecas.simulation.analysis.production_replanning_metrics import (
    production_programme_metrics, programme_metrics_with_contract, replanning_rate_from_metrics,
    BASIS, AUTHORIZATION_BASIS,
)
from etudecas.simulation.analysis.production_daily_metrics import daily_plan_metrics


def snapshot(day, target=None, *, identity='A', item='PF', uom='UN',
             committed=None, start=0, stop=7, version=None, known=None):
    target = target or {}
    committed = committed or {}
    total = {str(d): target.get(d, 0) for d in range(start, stop)}
    firm = {str(d): committed.get(d, 0) for d in range(start, stop)}
    proposed = {str(d): total[str(d)] - firm[str(d)] for d in range(start, stop)}
    return dict(schema_version=1, basis='simulated_weekly_launch_programme_v1',
        scenario_id='BASE', programme_id=identity, node_id='factory', output_item_id=item,
        uom=uom, decision_day=day, known_day=day if known is None else known,
        version=day + 1 if version is None else version, week_start_day=0,
        coverage_start_day=start, coverage_end_day_exclusive=stop,
        launch_quantities_json=json.dumps(total), committed_quantities_json=json.dumps(firm),
        proposed_quantities_json=json.dumps(proposed))


def test_date_only_revision_counts_once_even_with_equal_total_quantity():
    result = production_programme_metrics([snapshot(0, {3: 10}), snapshot(1, {4: 10})])
    assert result['production_replanning_count'] == 1
    assert result['production_replanning_comparable_count'] == 1
    assert result['production_replanning_rate'] == 1


def test_two_programmes_have_a_programme_denominator_not_a_daily_denominator():
    rows = [snapshot(0, {3: 10}), snapshot(1, {3: 15}),
            snapshot(0, {3: 20}, identity='B', item='bulk', uom='KG'),
            snapshot(1, {3: 20}, identity='B', item='bulk', uom='KG')]
    result = production_programme_metrics(rows)
    assert result['production_replanning_count'] == 1
    assert result['production_replanning_comparable_count'] == 2
    assert result['production_replanning_rate'] == float(Fraction(1, 2))
    rows[-1] = snapshot(1, {3: 25}, identity='B', item='bulk', uom='KG')
    assert production_programme_metrics(rows)['production_replanning_rate'] == 1


def test_normal_execution_preserves_total_target_and_is_not_replanning():
    rows = [snapshot(1, {2: 100}, version=1), snapshot(2, {2: 100}, committed={2: 100}, version=2)]
    before = deepcopy(rows)
    result = production_programme_metrics(rows)
    assert result['production_replanning_count'] == 0
    assert result['production_replanning_rate'] == 0
    assert rows == before


def test_first_nonzero_target_is_creation_even_after_zero_book_snapshots():
    result = production_programme_metrics([snapshot(0), snapshot(1, {3: 10}), snapshot(2, {3: 10})])
    assert result['production_replanning_count'] == 0
    assert result['production_replanning_comparable_count'] == 1
    assert result['production_replanning_diagnostics']['programme_creations_excluded'] == 1


def test_explicit_cancellation_and_reactivation_of_known_programme_count():
    result = production_programme_metrics([snapshot(0, {3: 10}), snapshot(1), snapshot(2, {3: 10})])
    assert result['production_replanning_count'] == 2
    assert result['production_replanning_comparable_count'] == 2
    assert result['production_replanning_rate'] == 1


def test_multiple_changed_fields_are_one_comparison_not_two_revisions():
    result = production_programme_metrics([snapshot(0, {3: 10}), snapshot(1, {4: 20})])
    assert result['production_replanning_count'] == 1
    assert result['production_replanning_rate'] == 1


def test_zero_opportunity_stays_unknown_instead_of_zero_percent():
    for rows in ([], [snapshot(0)], [snapshot(0), snapshot(1)], [snapshot(0, {3: 10})]):
        result = production_programme_metrics(rows)
        assert result['production_replanning_rate'] is None
        assert result['production_replanning_count'] is None
        assert result['production_replanning_comparable_count'] == 0


def test_missing_first_versions_cannot_be_identified_as_programme_creation():
    rows = [snapshot(3, {4: 100}, version=4), snapshot(4, version=5)]
    with pytest.raises(ValueError, match='version 1'):
        production_programme_metrics(rows)


def test_missing_zero_publication_before_creation_prevents_complete_rate():
    rows = [snapshot(0), snapshot(2), snapshot(3, {4: 100}), snapshot(4, {4: 100})]
    result = production_programme_metrics(rows)
    assert result['production_replanning_coverage_complete'] is False
    assert result['production_replanning_rate'] is None
    assert result['production_replanning_diagnostics']['missing_publication_comparisons_excluded'] == 1
    assert result['production_replanning_comparable_count'] == 1


def test_changed_partial_coverage_is_not_an_annulment():
    result = production_programme_metrics([snapshot(0, {3: 10}, stop=4), snapshot(1, {3: 20}, stop=5)])
    assert result['production_replanning_comparable_count'] == 0
    assert result['production_replanning_rate'] is None
    assert result['production_replanning_diagnostics']['coverage_change_comparisons_excluded'] == 1


def test_exact_duplicate_is_counted_once_and_conflicting_duplicate_refused():
    first, second = snapshot(0, {3: 10}), snapshot(1, {3: 20})
    result = production_programme_metrics([first, second, deepcopy(second)])
    assert result['production_replanning_comparable_count'] == 1
    assert result['production_replanning_diagnostics']['exact_duplicate_publications'] == 1
    with pytest.raises(ValueError, match='contradictoires'):
        production_programme_metrics([first, second, snapshot(1, {3: 30})])


def test_missing_publication_does_not_certify_a_complete_rate():
    result = production_programme_metrics([snapshot(0, {4: 10}), snapshot(2, {4: 20}, version=2)])
    assert result['production_replanning_rate'] is None
    assert not result['production_replanning_coverage_complete']


def test_missing_expected_site_or_disabled_journal_stays_unmeasurable():
    rows = [snapshot(0, {3: 10}), snapshot(1, {3: 10})]
    result = production_programme_metrics(rows, expected_pairs=[('factory', 'PF'), ('Gaillac', 'bulk')])
    assert result['production_replanning_rate'] is None
    assert result['production_replanning_diagnostics']['missing_pairs'] == [['Gaillac', 'bulk']]
    assert production_programme_metrics(rows, enabled=False)['production_replanning_rate'] is None


@pytest.mark.parametrize('kind', ['future_knowledge', 'changed_unit', 'regressed_version', 'changed_identity', 'wrong_decomposition'])
def test_invalid_snapshot_contracts_are_refused(kind):
    first, second = snapshot(0, {3: 10}), snapshot(1, {3: 20})
    if kind == 'future_knowledge': second['known_day'] = 2
    if kind == 'changed_unit': second['uom'] = 'KG'
    if kind == 'regressed_version': second['version'] = 1
    if kind == 'changed_identity': second['output_item_id'] = 'other'
    if kind == 'wrong_decomposition': second['committed_quantities_json'] = json.dumps({str(d): 0 for d in range(7)})
    if kind == 'wrong_decomposition': second['launch_quantities_json'] = json.dumps({str(d): 50 for d in range(7)})
    with pytest.raises(ValueError):
        production_programme_metrics([first, second])


def legacy(day, identity, qty, due):
    return dict(day=day, node_id='factory', output_item_id='PF', planned_qty_after_lot_rule=qty,
        actual_qty=0, desired_qty=qty, proposal_id=identity, proposal_version=str(day + 1),
        proposal_due_day=due, proposal_known_day=day, proposal_qty=qty)


def test_legacy_stable_proposal_detects_date_only_change():
    result = daily_plan_metrics([legacy(0, 'A', 10, 3), legacy(1, 'A', 10, 4)])
    assert result['production_replanning_count'] == 1
    assert result['production_replanning_comparable_count'] == 1
    assert result['production_replanning_rate'] == 1


def test_legacy_two_revisions_cannot_produce_two_hundred_percent():
    rows = [legacy(0, 'A', 10, 3), legacy(0, 'B', 20, 3),
            legacy(1, 'A', 15, 3), legacy(1, 'B', 25, 3)]
    result = daily_plan_metrics(rows)
    assert result['production_replanning_count'] == 2
    assert result['production_replanning_comparable_count'] == 2
    assert result['production_replanning_rate'] == 1


def test_unchanged_overdue_absolute_recommendation_does_not_invent_a_delay():
    result = production_programme_metrics([snapshot(0, {0: 100}), snapshot(1, {0: 100})])
    assert result['production_replanning_comparable_count'] == 1
    assert result['production_replanning_count'] == 0
    assert result['production_replanning_rate'] == 0


def contract(count):
    return dict(schema_version=1, basis='simulated_weekly_launch_programme_v1',
        enabled=True, complete_scope=True, published_snapshot_count=count,
        expected_pairs=[dict(node_id='factory', output_item_id='PF')])


def test_export_receipt_count_detects_missing_tail_without_modifying_files():
    rows = [snapshot(0, {3: 10}), snapshot(1, {3: 20})]
    assert programme_metrics_with_contract(rows, contract(2))['production_replanning_rate'] == 1
    with pytest.raises(ValueError, match='nombre de publications'):
        programme_metrics_with_contract(rows, contract(3))
    with pytest.raises(ValueError, match='nombre de publications'):
        programme_metrics_with_contract(rows + [deepcopy(rows[-1])], contract(2))


def test_missing_or_disabled_export_contract_cannot_certify_a_rate():
    rows = [snapshot(0, {3: 10}), snapshot(1, {3: 20})]
    assert programme_metrics_with_contract(rows, {})['production_replanning_rate'] is None
    disabled = dict(contract(2), enabled=False)
    assert programme_metrics_with_contract(rows, disabled)['production_replanning_rate'] is None


def test_metric_selector_honours_explicit_unknown_and_prefixed_values():
    assert replanning_rate_from_metrics({'kpi::production_replanning_rate': 0, 'production_replanning_rate': .5}) == 0
    for missing in (None, ''):
        row = {'kpi::production_replanning_rate': missing, 'production_replanning_rate': .5,
               'production_replanning_count': 1, 'production_replanning_comparable_count': 2}
        assert replanning_rate_from_metrics(row) is None
    row = {'production_replanning_rate': .5, 'production_replanning_coverage_complete': False}
    assert replanning_rate_from_metrics(row) is None


def test_metric_selector_uses_only_the_matching_comparable_programme_denominator():
    assert replanning_rate_from_metrics({'production_replanning_count': 1, 'production_planning_line_count': 2}) is None
    assert replanning_rate_from_metrics({'production_replanning_count': 1, 'production_replanning_comparable_count': 2}) == .5
    assert replanning_rate_from_metrics({'production_replanning_count': 2, 'production_replanning_comparable_count': 1}) is None
    assert replanning_rate_from_metrics({'production_replanning_count': 0, 'production_replanning_comparable_count': 0}) is None


@pytest.mark.parametrize('basis', [BASIS, AUTHORIZATION_BASIS])
def test_supported_commitment_bases_are_returned_without_changing_comparison_arithmetic(basis):
    rows = [dict(snapshot(0, {3: 10}), basis=basis), dict(snapshot(1, {3: 20}), basis=basis)]
    before = deepcopy(rows)
    result = production_programme_metrics(rows)
    assert result['production_replanning_basis'] == basis
    assert result['production_replanning_count'] == 1
    assert result['production_replanning_comparable_count'] == 1
    assert result['production_replanning_rate'] == 1
    expected = 'campaign_creation_authorization' if basis == AUTHORIZATION_BASIS else 'first_physical_execution_v1'
    assert result['production_replanning_diagnostics']['commitment_milestone'] == expected
    assert rows == before


def test_commitment_bases_cannot_be_mixed_even_between_distinct_programmes():
    rows = [snapshot(0, {3: 10}), dict(snapshot(0, {3: 20}, identity='B'), basis=AUTHORIZATION_BASIS)]
    with pytest.raises(ValueError, match='bases'):
        production_programme_metrics(rows)


@pytest.mark.parametrize('enabled', [True, False])
def test_export_contract_basis_must_match_every_snapshot_even_when_disabled(enabled):
    rows = [dict(snapshot(0, {3: 10}), basis=AUTHORIZATION_BASIS),
            dict(snapshot(1, {3: 20}), basis=AUTHORIZATION_BASIS)]
    with pytest.raises(ValueError, match='base'):
        programme_metrics_with_contract(rows, dict(contract(2), enabled=enabled))
    result = programme_metrics_with_contract(rows, dict(contract(2), enabled=enabled, basis=AUTHORIZATION_BASIS))
    assert result['production_replanning_basis'] == AUTHORIZATION_BASIS
    assert result['production_replanning_rate'] == (1 if enabled else None)


def test_empty_disabled_journal_keeps_its_explicit_commitment_basis():
    result = production_programme_metrics([], enabled=False, basis=AUTHORIZATION_BASIS)
    assert result['production_replanning_basis'] == AUTHORIZATION_BASIS
    assert result['production_replanning_rate'] is None
    assert result['production_replanning_comparable_count'] == 0
