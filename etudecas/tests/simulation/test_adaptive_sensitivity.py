"""Pure in-memory oracles: no file fixtures, native run or integrity alteration."""
from fractions import Fraction
from copy import deepcopy

import pytest

from etudecas.simulation.analysis_batch_common import SUPPORTED_FACTORS
from etudecas.simulation.sensibility.run_adaptive_sensitivity import (
    METRICS, PARAMETER_LABELS, effective_projection, historical_graph_copy, metric_values, search_thresholds, tolerances,
)


def row(availability=.8, replanning=.1, cost=100):
    return {"status": "ok", "kpi::product_availability": availability,
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
    assert all(value is None for value in metric_values({"kpi::fill_rate": 1, "kpi::total_cost": 0}).values())
    assert metric_values(row(replanning=0))["kpi::production_replanning_rate"] == 0


def test_first_thresholds_are_separate_per_indicator_and_both_directions():
    def evaluate(parameter, factor):
        severity = factor if factor > 1 else 1 / factor
        return row(.79 if severity >= 5 else .8, .11 if severity >= 20 else .1, 102)
    result = run(evaluate)
    for direction in result["directions"]:
        thresholds = direction["thresholds"]
        assert thresholds["kpi::inventory_cost"]["first_tested_factor"] in {.5, 2}
        assert thresholds["kpi::product_availability"]["first_tested_factor"] in {.1, 5}
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
        threshold = state["thresholds"]["kpi::product_availability"]
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
