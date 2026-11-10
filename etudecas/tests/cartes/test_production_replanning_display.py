"""Pure display contracts: an unknown programme rate must stay unknown."""
from etudecas.visualization.maps.build_supplychain_worldmap import sensitivity_replanning_rate_percent
from etudecas.visualization.maps.scenario_comparison_payload import (
    comparison_replanning_metrics, select_comparable_production_programme,
)


def test_sensitivity_uses_programme_comparisons_instead_of_physical_passes():
    assert sensitivity_replanning_rate_percent({
        'production_replanning_count': 1, 'production_replanning_comparable_count': 4,
        'production_planning_line_count': 1}, baseline_production_planning_line_count=1) == 25


def test_explicit_unknown_cannot_borrow_nominal_denominator():
    assert sensitivity_replanning_rate_percent({
        'production_replanning_rate': None, 'production_replanning_count': 1,
        'production_planning_line_count': 1}, baseline_production_planning_line_count=4) is None


def test_known_zero_is_displayed_as_zero():
    assert sensitivity_replanning_rate_percent({'production_replanning_rate': 0}) == 0


def test_input_waits_do_not_become_programme_revisions():
    metrics = comparison_replanning_metrics({'production_input_delay_count': 9,
        'production_planning_line_count': 10})
    assert metrics['production_replanning_count'] is None
    assert metrics['production_replanning_rate'] is None


def test_native_programme_basis_and_explicit_denominator_are_preserved():
    source = {'production_replanning_count': 1, 'production_replanning_comparable_count': 4,
        'production_replanning_rate': .25, 'production_replanning_basis': 'simulated_weekly_launch_programme_v1',
        'production_replanning_label': 'Programme simulé'}
    assert comparison_replanning_metrics(source) == source


def test_unknown_variant_cannot_inherit_the_nominal_rate():
    result = comparison_replanning_metrics({'production_replanning_rate': .2},
        {'kpi::production_replanning_rate': None, 'kpi::production_replanning_count': None})
    assert result['production_replanning_rate'] is None
    assert result['production_replanning_count'] is None


def test_invalid_rate_is_not_shown_as_two_hundred_percent():
    assert sensitivity_replanning_rate_percent({'production_replanning_rate': 2}) is None


def test_incomplete_coverage_does_not_become_a_known_rate():
    result = comparison_replanning_metrics({'production_replanning_rate': .2,
        'production_replanning_coverage_complete': False})
    assert result['production_replanning_rate'] is None


def test_unknown_programmes_cannot_be_ranked_by_material_waits():
    scenarios = [{'kpis': {'production_replanning_basis': 'A',
        'production_replanning_rate': None, 'input_delay_count': count}} for count in (0, 9)]
    assert select_comparable_production_programme(scenarios,
        {'production_replanning_basis': 'A'}) is None


def test_programme_ranking_requires_the_same_basis_and_preserves_zero():
    def case(name, basis, rate, count):
        return {'label': name, 'kpis': {'production_replanning_basis': basis,
            'production_replanning_rate': rate, 'production_replanning_count': count,
            'input_delay_count': 50}}
    cases = [case('unknown', 'A', None, None), case('other', 'B', 0, 0),
        case('positive', 'A', .1, 1), case('zero', 'A', 0, 0)]
    assert select_comparable_production_programme(cases,
        {'production_replanning_basis': 'A'})['label'] == 'zero'
