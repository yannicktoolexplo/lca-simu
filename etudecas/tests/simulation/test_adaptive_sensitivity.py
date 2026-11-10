"""Pure in-memory oracles: no file fixtures, native run or integrity alteration."""
from fractions import Fraction
from copy import deepcopy

import pytest

from etudecas.simulation.analysis_batch_common import SUPPORTED_FACTORS
from etudecas.simulation.sensibility.run_adaptive_sensitivity import (
    METRICS, PARAMETER_LABELS, effective_projection, historical_graph_copy, metric_values, search_thresholds, tolerances, validate_resume_report,
    customer_service_diagnostic_text,
)


def row(availability=.8, replanning=.1, cost=100):
    return {"status": "ok", "kpi::quantity_service_rate": availability,
            "kpi::production_replanning_rate": replanning, "kpi::inventory_cost": cost}


def run(evaluate, **options):
    return search_thresholds(parameters=["supplier_stock_scale"], baseline=row(), evaluate=evaluate,
        effective_key=lambda parameter, factor: str(factor), **options)


def test_catalog_covers_exactly_the_19_supported_global_factors():
    assert len(SUPPORTED_FACTORS) == 19
    assert set(PARAMETER_LABELS) == SUPPORTED_FACTORS
    assert len(METRICS) == 3


def test_missing_replanning_is_unknown_and_blocks_before_any_probe():
    calls = []
    baseline = row(replanning=None)
    baseline.update({"kpi::fill_rate": .99, "kpi::total_cost": 10000})
    result = search_thresholds(parameters=["holding_cost_scale"], baseline=baseline,
        evaluate=lambda *args: calls.append(args), effective_key=lambda p, f: str(f))
    assert result["status"] == "blocked_missing_indicators" and result["native_runs"] == 0
    assert result["missing_indicators"] == ["kpi::production_replanning_rate"]
    assert not result["all_three_satisfied"] and not calls


def test_strict_metric_reader_never_substitutes_fill_rate_or_total_cost():
    assert all(value is None for value in metric_values({"kpi::product_availability": 1,
        "kpi::fill_rate": 1, "kpi::total_cost": 0}).values())
    assert metric_values(row(replanning=0))["kpi::production_replanning_rate"] == 0


def test_first_thresholds_are_separate_per_indicator_and_both_directions():
    def evaluate(parameter, factor):
        severity = factor if factor > 1 else 1 / factor
        return row(.79 if severity >= 5 else .8, .11 if severity >= 20 else .1, 102)
    result = run(evaluate)
    for direction in result["directions"]:
        thresholds = direction["thresholds"]
        assert thresholds["kpi::inventory_cost"]["first_tested_factor"] in {.5, 2}
        assert thresholds["kpi::quantity_service_rate"]["first_tested_factor"] in {.1, 5}
        assert thresholds["kpi::production_replanning_rate"]["first_tested_factor"] in {.01, 20}
        assert direction["all_three_satisfied"]
    assert result["native_runs"] == 7 and result["all_three_satisfied"]


def test_cost_only_effect_does_not_satisfy_other_indicators():
    result = run(lambda p, f: row(cost=100 * f))
    assert not result["all_three_satisfied"]
    assert all(set(state["thresholds"]) == {"kpi::inventory_cost"} for state in result["directions"])
    assert all(state["status"] == "bounds_reached_no_further_effect" for state in result["directions"])


def test_partial_mode_never_claims_success_on_three_indicators():
    result = search_thresholds(parameters=["holding_cost_scale"], baseline=row(replanning=None),
        evaluate=lambda p, f: row(.79, None, 102), effective_key=lambda p, f: str(f), allow_partial=True)
    assert result["status"] == "partial_indicators" and result["native_runs"] == 3
    assert not result["all_three_satisfied"]
    assert all(state["status"] == "thresholds_detected_measurable_only" for state in result["directions"])


def test_round_robin_covers_parameters_before_deepening_and_budget_is_exact():
    calls = []
    def evaluate(p, f):
        calls.append((p, f)); return row()
    result = search_thresholds(parameters=["holding_cost_scale", "supplier_stock_scale"], baseline=row(),
        evaluate=evaluate, effective_key=lambda p, f: str(f), max_runs=5)
    assert calls == [("holding_cost_scale", .5), ("holding_cost_scale", 2),
                     ("supplier_stock_scale", .5), ("supplier_stock_scale", 2)]
    assert result["native_runs"] == 5 and result["budget_stop"] == "max_runs"
    assert result["status"] == 'budget_reached' and not result['all_three_satisfied']
    assert all(state["status"] == "budget_reached" for state in result["directions"])


def test_true_saturation_skips_native_execution_without_inventing_zero_effect():
    calls = []
    result = search_thresholds(parameters=["fg_target_days_scale"], baseline=row(),
        evaluate=lambda *args: calls.append(args), effective_key=lambda p, f: "always_zero")
    assert not calls and result["native_runs"] == 1
    assert all(state["status"] == "parameter_unchanged" for state in result["directions"])
    assert not result["all_three_satisfied"]


def test_quantization_plateau_does_not_hide_a_later_effective_change():
    calls = []
    def evaluate(p, f):
        calls.append(f); return row(.7, .2, 120)
    result = search_thresholds(parameters=["lead_time_scale"], baseline=row(), evaluate=evaluate,
        effective_key=lambda p, f: str(1 if f >= .9 and f <= 1 else f),
        down=(.9, .5), up=(2,))
    assert calls == [2, .5]
    assert result["all_three_satisfied"]


def test_nonmonotone_response_reports_only_local_tested_interval():
    result = run(lambda p, f: row(.79 if f in {.1, 5} else .8, .1, 100))
    for state in result["directions"]:
        threshold = state["thresholds"]["kpi::quantity_service_rate"]
        assert threshold["adjacent_tested_interval"] in [[.1, .5], [2, 5]]
        assert "pas de monotonie globale" in threshold["interpretation"]
    assert not result["all_three_satisfied"]


def test_storage_tolerance_matches_fraction_oracle_and_preserves_cost_zero():
    limits = tolerances(row(cost=1234), rate_delta=.001, cost_relative=.01, cost_absolute=1)
    assert limits["kpi::inventory_cost"] == float(Fraction(1234, 100))
    assert tolerances(row(cost=0))["kpi::inventory_cost"] == 1


def test_budget_callback_stops_before_any_probe():
    calls = []
    result = run(lambda *args: calls.append(args), budget_reason=lambda: "storage_budget")
    assert not calls and result["native_runs"] == 1 and result["budget_stop"] == "storage_budget"


def test_effective_projection_ignores_provenance_but_keeps_actual_source_demand():
    baseline = {"nodes": [{"inventory": {"initial": 100, "initial_source": "source"}}],
                "meta": {"customer_demand_history": {"rows": [{"quantity": 100}]}}}
    variant = {"nodes": [{"inventory": {"initial": 100, "initial_source": "hypothetical",
                          "initial_before_scenario_scale": 100}}],
               "meta": {"customer_demand_history": {"rows": [{"quantity": 100}]}, "lead_time_scale_scenario": {"requested": 2}}}
    assert effective_projection(baseline) == effective_projection(variant)
    variant["meta"]["customer_demand_history"]["rows"][0]["quantity"] = 99
    assert effective_projection(baseline) != effective_projection(variant)


def test_existing_long_horizon_values_are_never_the_search_baseline():
    # The scheduler receives its recalculated same-horizon row, not observability values.
    result = search_thresholds(parameters=["holding_cost_scale"], baseline=row(cost=200),
        evaluate=lambda p, f: row(cost=204), effective_key=lambda p, f: str(f), max_runs=3)
    assert all(state["thresholds"]["kpi::inventory_cost"]["baseline"] == 200 for state in result["directions"])


def test_later_thresholds_do_not_erase_an_unmeasurable_required_trial():
    result = search_thresholds(parameters=["holding_cost_scale"], baseline=row(),
        evaluate=lambda p, f: row(.7, None if f == .5 else .2, 120),
        effective_key=lambda p, f: str(f), down=(.5, .1), up=(2,))
    assert result["status"] == "partial_indicators" and not result["all_three_satisfied"]
    lower = result["directions"][0]
    assert len(lower["thresholds"]) == 3
    assert lower["thresholds"]["kpi::production_replanning_rate"]["first_tested_factor"] == .1
    assert lower["unavailable_trial_indicators"] == {"kpi::production_replanning_rate": [.5]}
    assert not lower["all_three_satisfied"]


def prospective_graph():
    from etudecas.simulation import current_reference
    contract = dict(current_reference.projection_contract(current_reference.read(current_reference.CONFIG), "coherent_scenario"),
                    schema_version=1, scenario_id="scn:BASE", days=1825)
    return {"nodes": [{"id": "demo", "inventory": {"states": [{"item_id": "item:U", "initial": 10, "uom": "UN"}]}}],
            "edges": [], "meta": {"current_reference_projection": contract,
                "opening_open_orders": [{"quantity": 10, "physical_delivery_day": 7, "available_day": 9}],
                "manufacturing_closures": {"rows": [{"start_date": "2026-08-03"}]},
                "current_reference_other_use_profile": {"source_sha256": "unchanged", "rows": []},
                "customer_demand_history": {"rows": [{"qty": 20}]},
                "mrp_forecasts": {"rows": [{"qty": 30, "known_day": 0}]}}}


def test_historical_copy_removes_only_validated_prospective_contract_and_keeps_source_immutable():
    from etudecas.simulation.current_reference import validate_projection_contract
    original = prospective_graph()
    before = deepcopy(original)
    adapted, report = historical_graph_copy(original, 21)
    expected = deepcopy(before)
    del expected["meta"]["current_reference_projection"]
    assert adapted == expected and original == before
    assert validate_projection_contract(adapted["meta"], 21) is False
    assert report["removed_keys"] == ["meta.current_reference_projection"]
    assert report["source_contract_days"] == 1825 and report["target_historical_days"] == 21
    assert report["source_semantic_graph_sha256"] != report["adapted_semantic_graph_sha256"]


def test_invalid_incoming_prospective_contract_is_rejected_before_removal():
    original = prospective_graph()
    original["meta"]["current_reference_projection"]["days"] = 21
    before = deepcopy(original)
    with pytest.raises(ValueError, match="Invalid retained-W"):
        historical_graph_copy(original, 21)
    assert original == before


def test_historical_graph_without_prospective_contract_is_preserved_and_copied():
    original = prospective_graph()
    del original["meta"]["current_reference_projection"]
    result, report = historical_graph_copy(original, 362)
    assert result == original and result is not original and result["meta"] is not original["meta"]
    assert report["removed_keys"] == [] and report["historical_projection_validation"] is False
    assert report["source_semantic_graph_sha256"] == report["adapted_semantic_graph_sha256"]


@pytest.mark.parametrize("days", [0, 363, 1825, True, 21.0])
def test_historical_graph_copy_refuses_nonhistorical_or_noninteger_horizons(days):
    with pytest.raises(ValueError, match="horizon entier"):
        historical_graph_copy(prospective_graph(), days)


def test_historical_conversion_matches_normal_preparation_and_preserves_custom_calendars():
    from etudecas.simulation import current_reference as reference
    config = reference.read(reference.CONFIG)
    base = {"nodes": [], "edges": [], "meta": {
        "current_reference_customer_demand_source": {"policy": reference.CUSTOMER_DEMAND_MODE,
                                                   "historical_execution_days": reference.CUSTOMER_HISTORY_DAYS},
        "manufacturing_closures": {"rows": [
            {"node_id": "M-1810", "start_date": "2025-08-04", "end_date": "2025-08-15", "provenance": "source2025"},
            {"node_id": "M-1810", "start_date": "2026-08-03", "end_date": "2026-08-14", "provenance": "custom industrial schedule"}]},
        "opening_open_orders": [{"quantity": 10, "physical_delivery_day": 7, "available_day": 9}],
        "customer_demand_history": {"rows": [{"qty": 20}]}, "mrp_forecasts": {"rows": [{"qty": 30}]}}}
    expected = reference.prepare_graph(base, config, 362, "coherent_scenario")
    future = reference.prepare_graph(base, config, 1825, "coherent_scenario")
    before = deepcopy(future)
    adapted, report = historical_graph_copy(future, 362)
    assert adapted == expected and future == before
    assert len(adapted["meta"]["manufacturing_closures"]["rows"]) == 2
    assert len(report["removed_recognized_prospective_closures"]) > 0
    assert "meta.current_reference_other_use_profile" in report["removed_keys"]
    assert report["conversion_reference_hashes"]


def test_non_generated_custom_profile_and_similar_closure_are_not_deleted():
    source = prospective_graph()
    source["meta"]["manufacturing_closures"]["rows"][0]["provenance"] = "custom industrial schedule"
    before = deepcopy(source)
    adapted, report = historical_graph_copy(source, 21)
    assert adapted["meta"]["manufacturing_closures"] == before["meta"]["manufacturing_closures"]
    assert adapted["meta"]["current_reference_other_use_profile"] == before["meta"]["current_reference_other_use_profile"]
    assert not report["removed_recognized_prospective_closures"]
    assert source == before


def test_progress_is_published_after_each_trial_with_detached_state():
    snapshots = []
    def progress(snapshot):
        snapshots.append(deepcopy(snapshot))
        snapshot['directions'].clear()
        snapshot['trials'].clear()
    result = run(lambda p, f: row(.7, .2, 120), down=(.5,), up=(2,), on_progress=progress)
    assert [len(value['trials']) for value in snapshots] == [0, 1, 2, 2]
    assert result['all_three_satisfied'] and len(result['directions']) == 2
    assert snapshots[-1]['status'] == 'bounded_search_finished'


def test_progress_records_saturation_without_inventing_a_native_run():
    snapshots = []
    result = search_thresholds(parameters=['fg_target_days_scale'], baseline=row(),
        evaluate=lambda p, f: pytest.fail('No changed input, so no native probe'),
        effective_key=lambda p, f: 'zero', on_progress=snapshots.append)
    assert len(snapshots) == 4
    assert len(snapshots[1]['trials']) == 1
    assert snapshots[1]['trials'][0]['native_execution'] is False
    assert result['native_runs'] == 1 and not result['all_three_satisfied']


def test_completed_rows_replay_the_same_search_without_another_native_calculation():
    completed = {}
    fresh_calls = []
    def fresh(p, f):
        fresh_calls.append((p, f))
        completed[p, f] = row(.7, .2, 120)
        return completed[p, f]
    original = run(fresh, down=(.5,), up=(2,))
    replay_calls = []
    def replay(p, f):
        replay_calls.append((p, f))
        return deepcopy(completed[p, f])
    reconstructed = run(replay, down=(.5,), up=(2,))
    assert fresh_calls == replay_calls and len(fresh_calls) == 2
    assert reconstructed == original


def resume_pair():
    contract = {'schema': 'etudecas.adaptive-sensitivity.v2', 'parameters': ['holding_cost_scale'],
        'days': 21, 'baseline_manifest': 'same/manifest.json', 'input_graph': 'same/graph.json',
        'runtime': 'same.py', 'metric_definitions': dict(METRICS), 'down_levels': [.5], 'up_levels': [2],
        'criteria': {'rate': .001}, 'implementation': {'engine.py': 'same-sha'},
        'dependency_hashes': {'graph.json': 'same-sha'}, 'observability_hashes': {'service.csv': 'same-sha'},
        'allow_partial_indicators': False, 'artifact_policy': 'all', 'max_runs': 3}
    previous = dict(deepcopy(contract), status='bounded_search_finished',
        budget_stop='max_runs', completed_native_cases=[{'case_id': 'baseline'}])
    return previous, contract


def test_resume_contract_allows_only_budget_changes_with_identical_study():
    previous, current = resume_pair()
    current['max_runs'] = 5
    current['max_wall_minutes'] = 60
    validate_resume_report(previous, current)


@pytest.mark.parametrize('field', ['days', 'parameters', 'criteria', 'implementation',
    'dependency_hashes', 'observability_hashes', 'metric_definitions', 'down_levels', 'allow_partial_indicators'])
def test_resume_contract_refuses_changed_design_sources_or_indicator(field):
    previous, current = resume_pair()
    current[field] = 'different'
    with pytest.raises(ValueError, match='contrat différent'):
        validate_resume_report(previous, current)


def test_resume_contract_refuses_failed_and_older_studies_or_smaller_budget():
    previous, current = resume_pair()
    previous['status'] = 'failed_stopped_without_retry'
    with pytest.raises(ValueError, match='après échec'):
        validate_resume_report(previous, current)
    previous, current = resume_pair()
    previous['schema'] = 'etudecas.adaptive-sensitivity.v1'
    with pytest.raises(ValueError, match='ancien'):
        validate_resume_report(previous, current)
    previous, current = resume_pair()
    current['max_runs'] = 0
    with pytest.raises(ValueError, match='inférieur'):
        validate_resume_report(previous, current)


@pytest.mark.parametrize('status,stop', [('running_native_case', None), ('running', None),
    ('bounded_search_finished', None), ('blocked_missing_indicators', None)])
def test_resume_only_accepts_clean_budget_boundaries(status, stop):
    previous, current = resume_pair()
    previous.update(status=status, budget_stop=stop)
    with pytest.raises(ValueError, match='entre deux cas'):
        validate_resume_report(previous, current)


def test_customer_service_diagnostic_preserves_deliveries_with_zero_cleared_days():
    metrics = {'kpi::quantity_service_rate': float(Fraction(183841, 215001)),
        'kpi::quantity_service_served_qty': 183841, 'kpi::quantity_service_demand_qty': 215001,
        'kpi::quantity_service_opening_backlog_qty': 0, 'kpi::quantity_service_ending_backlog_qty': 31160,
        'kpi::fully_served_customer_item_days': 0, 'kpi::active_customer_item_days': 42}
    text = customer_service_diagnostic_text(metrics)
    assert '85,51 %' in text and '0 / 42' in text
    assert '183\u202f841' in text and '31\u202f160' in text
    assert '0 unités en retard au début' in text
    assert 'stock disponible' not in text


def test_customer_service_diagnostic_does_not_invent_zero_for_missing_values():
    text = customer_service_diagnostic_text({})
    assert 'inconnue' in text and 'inconnu / inconnu' in text
    assert '0 / 0' not in text and '100' not in text
