"""Counterexamples from the September audit, with independent physical oracles."""
from __future__ import annotations

import csv
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.model_semantics import (
    ReceiptLeadObservations, inventory_holding_rate, safety_calendar_anchor,
    safety_calendar_days, shipment_execution_state, transport_charge,
)
from etudecas.simulation.engine.run_first_simulation import scenario_initialization_policy
from etudecas.simulation_prep.prepare_simulation_graph import (
    derive_item_unit_value_map, holding_cost_per_unit_day_from_value,
)

ROOT = Path(__file__).resolve().parents[3]
ENGINE = ROOT / "etudecas/simulation/engine/run_first_simulation.py"


@pytest.mark.parametrize(
    "profile,expected",
    [
        ([], {-1: 0.0, 0: 0.0, 7: 0.0}),
        ([{"value": -2.5}], {-7: -2.5, 0: -2.5, 1825: -2.5}),
        ([{"type": "step", "start_day": 0, "value": 99},
          {"type": "constant", "value": 4},
          {"type": "constant", "value": 6}], {-1: 4.0, 0: 4.0, 7: 4.0}),
        ([{"type": "step", "start_day": 7, "value": 70},
          {"type": "step", "start_day": 0, "value": 2},
          {"type": "step", "start_day": 3, "value": 30},
          {"type": "step", "start_day": 3, "value": 31}],
         {-1: 0.0, 0: 2.0, 3: 31.0, 7: 70.0}),
        ([{"type": "piecewise", "points": [
            {"t": 7, "value": 70}, {"t": 3, "value": 30},
            {"t": -1, "value": 999}, None,
            {"t": 0, "value": 2}, {"t": 3, "value": 31},
        ]}], {-1: 0.0, 0: 2.0, 3: 31.0, 7: 70.0}),
        ([{"type": "piecewise", "repeat_period_days": 7, "points": [
            {"t": 6, "value": 60}, {"t": 0, "value": 10}, {"t": 3, "value": 30},
        ]}], {-8: 60.0, -7: 10.0, -1: 60.0, 0: 10.0, 3: 30.0, 7: 10.0}),
        ([{"type": "step", "repeat_period_days": 7, "start_day": 0, "value": 2},
          {"type": "piecewise", "repeat_period_days": 5, "points": [
              {"t": 1, "value": 11}, {"t": 4, "value": 14},
          ]}], {-1: 14.0, 0: 2.0, 4: 14.0, 6: 11.0}),
        ([None, "invalid", {"type": "unknown", "value": 999}], {-1: 0.0, 0: 0.0, 7: 0.0}),
    ],
)
def test_demand_profile_cache_matches_daily_semantics_and_uncached_windows(profile, expected):
    cache = {}
    for day, value in expected.items():
        assert engine.profile_value(profile, day) == value
        assert engine.profile_window_average(profile, day, 1, value_cache=cache) == value
    profiles = {("D", "A"): profile}
    for day in (-365, -8, -1, 0, 1, 3, 6, 7, 365, 1824):
        for window in (-2, 0, 1, 2, 7, 31, 365):
            uncached = engine.profile_window_average(profile, day, window)
            cached = engine.profile_window_average(profile, day, window, value_cache=cache)
            assert cached.hex() == uncached.hex()
            assert engine.demand_targets_for_day(
                profiles, day, window_days=window, value_cache=cache,
            ) == engine.demand_targets_for_day(profiles, day, window_days=window)


def test_demand_profile_cache_preserves_ordered_float_sum():
    profile = [{"type": "piecewise", "points": [
        {"t": 0, "value": 1e16}, {"t": 1, "value": 1.0},
        {"t": 2, "value": -1e16}, {"t": 3, "value": 3.0},
    ]}]
    cache = {}
    assert engine.profile_window_average(profile, 0, 3, value_cache=cache) == sum([1e16, 1.0, -1e16]) / 3.0
    assert engine.profile_window_average(profile, 0, 4, value_cache=cache) == sum([1e16, 1.0, -1e16, 3.0]) / 4.0
    for day, window in ((1, 3), (0, 4), (2, 2), (0, 3)):
        assert engine.profile_window_average(profile, day, window, value_cache=cache).hex() == (
            engine.profile_window_average(profile, day, window).hex()
        )


def test_demand_profile_cache_reuses_overlapping_days_and_keeps_profiles_separate(monkeypatch):
    profiles = {("D", "A"): [{"value": 0}], ("D", "B"): [{"value": 7}]}
    original = engine.profile_value
    calls = []

    def counted(profile, day):
        calls.append((id(profile), day))
        return original(profile, day)

    monkeypatch.setattr(engine, "profile_value", counted)
    cache = {}
    for day in (0, 1, 0, 1):
        result = engine.demand_targets_for_day(profiles, day, window_days=7, value_cache=cache)
        assert result == {("D", "A"): 0.0, ("D", "B"): 7.0}
        result[("D", "A")] = 999.0
    assert len(calls) == len(set(calls)) == 16
    assert engine.demand_targets_for_day(profiles, 0, window_days=7) == {
        ("D", "A"): 0.0, ("D", "B"): 7.0,
    }
    assert len(calls) == 30  # Omitting the cache still exercises the original evaluator.


def test_demand_profile_cache_is_scoped_to_each_run():
    def evaluate_run(profiles):
        cache = {}
        return [engine.demand_targets_for_day(profiles, day, window_days=7, value_cache=cache)
                for day in (-1, 0, 1)]

    first = {("D", "A"): [{"value": 2}]}
    second = {("D", "A"): [{"value": 9}]}
    assert evaluate_run(first) == [{("D", "A"): 2.0}] * 3
    assert evaluate_run(second) == [{("D", "A"): 9.0}] * 3
    first[("D", "A")][0]["value"] = 5
    assert evaluate_run(first) == [{("D", "A"): 5.0}] * 3
    assert engine.profile_window_average(first[("D", "A")], 0, 7) == 5.0
    first[("D", "A")][0]["value"] = 6
    assert engine.profile_window_average(first[("D", "A")], 0, 7) == 6.0


@pytest.mark.parametrize("other_uom,other_price", [("KG", 10.0), ("G", 0.01), ("UN", 90000.0)])
def test_missing_price_is_not_imputed_from_unrelated_dimension(other_uom, other_price):
    prices, stats = derive_item_unit_value_map(
        [{"from": "S", "to": "M", "items": ["known"],
          "order_terms": {"sell_price": other_price, "price_base": 1, "quantity_unit": other_uom}}],
        {"known": other_uom, "unknown": "UN"}, {},
    )
    rate, source, value = holding_cost_per_unit_day_from_value(
        item_id="unknown", unit="UN", item_unit_map={"unknown": "UN"},
        item_unit_value_map=prices, fallback_global_unit_value=123456,
        annual_carry_rate=0.2,
    )
    assert (rate, value, stats["fallback_global_unit_value_per_item_unit"]) == (None, None, None)
    assert source == "missing_dimensioned_inventory_value"


def test_known_same_material_cost_is_invariant_under_kg_to_g_conversion():
    rates = []
    for unit, qty in [("KG", 12), ("G", 12000)]:
        rate, _, _ = holding_cost_per_unit_day_from_value(
            item_id="material", unit=unit, item_unit_map={"material": "KG"},
            item_unit_value_map={"material": 7}, fallback_global_unit_value=None,
            annual_carry_rate=0.2,
        )
        rates.append(rate * qty)
    assert rates[0] == pytest.approx(rates[1])


def test_piece_price_cannot_silently_become_kg_price():
    values, _ = derive_item_unit_value_map(
        [{"from": "S", "to": "M", "items": ["A"],
          "order_terms": {"sell_price": 8, "quantity_unit": "UN"}}], {"A": "KG"}, {},
    )
    assert values == {}


def test_unknown_and_explicit_zero_cost_remain_distinguishable():
    assert inventory_holding_rate({"value": 0}) == (0, "configured_rate")
    assert inventory_holding_rate({"value": None})[0] is None
    assert inventory_holding_rate({"value": 123, "source": "simulation_prep_global_value_median_fallback"})[0] is None


@pytest.mark.parametrize("procurement_lot", [1, 5000, 100000])
def test_unit_tariff_obeys_declared_unit_not_order_size(procurement_lot):
    lane = {"unit_transport_cost": 0.3614, "transport_cost_basis": "unit",
            "standard_order_qty": procurement_lot}
    cost, basis, units = transport_charge(lane, 5000, 5000)
    assert cost == pytest.approx(1807)
    assert (basis, units) == ("unit", 5000)
    assert sum(transport_charge(lane, q, q)[0] for q in [1000, 1600, 2400]) == pytest.approx(cost)


def test_batch_tariff_requires_its_own_explicit_conversion():
    lane = {"unit_transport_cost": 15, "transport_cost_basis": "batch", "standard_order_qty": 5000}
    with pytest.raises(ValueError, match="batch_qty"):
        transport_charge(lane, 10000, 10000)
    lane["transport_tariff_batch_qty"] = 2000
    assert transport_charge(lane, 10000, 10000) == (75, "batch", 5)
    with pytest.raises(ValueError, match="Unsupported"):
        transport_charge({"transport_cost_basis": "truck"}, 1000, 1000)


@pytest.mark.parametrize("observation,status", [(2, "reserved_pending_departure"), (3, "in_transit"), (7, "in_transit"), (8, "received")])
def test_shipment_status_depends_on_physical_dates(observation, status):
    assert shipment_execution_state(3, 8, observation) == status
    assert shipment_execution_state(3, 8, 2, reserved=False) == "planned_pending_departure"


def test_receipt_observation_never_reveals_future_sampled_delay():
    pending = ReceiptLeadObservations()
    pending.schedule(arrival_day=8, departure_day=3, supplier_pair=("S", "A"), reference_days=2, quantity=5)
    pending.schedule(arrival_day=9, departure_day=3, supplier_pair=("S", "A"), reference_days=2, quantity=0)
    for day in range(8):
        assert dict(pending.observe(day)) == {}
    assert dict(pending.observe(8)) == {("S", "A"): [(5, 2)]}
    assert dict(pending.observe(8)) == {}  # no repeated evidence
    assert dict(pending.observe(9)) == {}  # zero physical receipt is not evidence


@pytest.mark.parametrize("weekday", range(7))
@pytest.mark.parametrize("source_days", [1, 2, 5, 20])
def test_working_day_coverage_matches_independent_calendar(weekday, source_days):
    start = date(2025, 1, 6) + timedelta(days=weekday)
    cursor = start
    working = 0
    while working < source_days:
        cursor += timedelta(days=1)
        working += cursor.weekday() < 5
    assert safety_calendar_days(source_days, day=0, anchor_weekday=weekday, calendar="weekdays") == (cursor-start).days
    assert safety_calendar_days(source_days, day=0, anchor_weekday=weekday, calendar="calendar_days") == source_days


def test_calendar_anchor_and_full_source_target_are_explicit():
    assert safety_calendar_anchor({"meta": {"mrp_seed": {"snapshot_at_utc": "2025-01-01T03:03:48+00:00"}}}, {})["weekday"] == 2
    assert safety_calendar_anchor({}, {})["anchor_basis"] == "explicit_convention_J0_Monday_without_civil_date"
    default = scenario_initialization_policy({}, review_period_days=7, safety_stock_days=0)
    assert default["soft_safety_time_stock_target_factor"] == 1


def _fixture_graph():
    return {
        "meta": {"mrp_seed": {"snapshot_at_utc": "2025-01-01T03:03:48+00:00"}},
        "items": [{"id": "item:A", "uom": "UN"}],
        "nodes": [
            {"id": "SDC-TEST", "type": "supplier_dc", "inventory": {"states": [
                {"item_id": "item:A", "uom": "UN", "initial": 100000,
                 "holding_cost": {"value": 4, "source": "simulation_prep_global_value_median_fallback"},
                 "mrp_policy": {"safety_time_days": 1}}]}},
            {"id": "C-TEST", "type": "customer", "inventory": {"states": [
                {"item_id": "item:A", "uom": "UN", "initial": 0,
                 "holding_cost": {"value": 0}, "mrp_policy": {"safety_time_days": 1}}]}},
        ],
        "edges": [{"id": "edge:S_TO_C", "type": "transport", "from": "SDC-TEST", "to": "C-TEST",
                   "items": ["item:A"], "lead_time": {"mean": 12}, "service_level": {"otif": 1},
                   "transport_cost": {"value": 2, "per": "unit"},
                   "order_terms": {"quantity_unit": "UN", "sell_price": 3, "price_base": 1},
                   "attrs": {"standard_order_qty": 10}}],
        "scenarios": [{"id": "scn:BASE", "horizon": {"steps_to_run": 8},
                       "initialization_policy": {"mode": "explicit_state", "state_scale": 1,
                                                 "seed_in_transit": False, "seed_estimated_source_pipeline": False},
                       "demand": [{"node_id": "C-TEST", "item_id": "item:A", "profile": [{"type": "piecewise", "points": [
                           {"t": 0, "value": 10}, {"t": 7, "value": 100}, {"t": 14, "value": 20}]}]}]}],
    }


def run_fixture(output: Path, smoothing: int, *, days: int = 8, graph_override=None, extra_args=()):
    output.parent.mkdir(parents=True, exist_ok=True)
    graph = output.parent / "fixture.json"
    graph.write_text(json.dumps(_fixture_graph() if graph_override is None else graph_override), encoding="utf-8")
    command = [sys.executable, str(ENGINE), "--input", str(graph), "--output-dir", str(output),
               "--scenario-id", "scn:BASE", "--days", str(days), "--warmup-days", "0", "--seed", "9102",
               "--output-profile", "full", "--skip-map", "--skip-plots", "--no-lot-trace", "--skip-lot-audit",
               "--no-stochastic-lead-times", "--supplier-state-dependent-risks",
               "--use-bom-demand-signal-for-mrp",
               "--mrp-demand-signal-smoothing-days", str(smoothing), *extra_args]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads((output / "summaries/first_simulation_summary.json").read_text(encoding="utf-8"))


def csv_rows(output: Path, name: str):
    with (output / "data" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_family_filter_blocks_stock_events_but_does_not_disable_all_state_risks(tmp_path):
    graph = _fixture_graph()
    graph["nodes"][0]["inventory"]["states"][0]["initial"] = 0
    outputs = {family: tmp_path / family for family in ("all", "stock", "quality")}
    summaries = {
        family: run_fixture(path, 1, days=14, graph_override=graph,
                            extra_args=("--supplier-state-risk-families", family,
                                        "--supplier-state-risk-observation-warmup-days", "0"))
        for family, path in outputs.items()
    }
    events = {family: csv_rows(path, "supplier_state_dependent_risk_events.csv")
              for family, path in outputs.items()}
    assert any(row["risk_family"] == "stock" for row in events["all"])
    assert events["stock"] and all(row["risk_family"] == "stock" for row in events["stock"])
    assert not any(row["risk_family"] == "stock" for row in events["quality"])
    policy = summaries["quality"]["policy"]["supplier_state_dependent_risk"]
    assert policy["enabled"] and policy["enabled_families"] == ["quality"]
    assert policy["stock_rules"] == [] and policy["cost_rule"] == ""
    assert len(policy["reliability_quality_rules"]) == 1
    assert "quality" in policy["reliability_quality_rules"][0]
    assert "family_filter_mode" not in summaries["all"]["policy"]["supplier_state_dependent_risk"]


@pytest.mark.parametrize("families", ["typo", "all,stock"])
def test_family_filter_rejects_ambiguous_or_unknown_names(families):
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        engine._parse_supplier_state_risk_families(families)


def test_engine_preserves_source_demand_and_qualifies_incomplete_costs(tmp_path):
    outputs = [tmp_path / "raw", tmp_path / "planning_smoothed"]
    summaries = [run_fixture(output, smoothing) for output, smoothing in zip(outputs, [1, 7])]
    for output, summary in zip(outputs, summaries):
        rows = csv_rows(output, "production_demand_service_daily.csv")
        assert [float(row["demand_qty"]) for row in rows] == [10] * 7 + [100]
        assert summary["kpis"]["total_demand"] == 170
        assert summary["economic_valuation"]["complete"] is False
        assert summary["economic_valuation"]["unknown_inventory_pairs"][0]["item_id"] == "item:A"
        assert summary["kpis"]["total_holding_cost"] == 0
        assert summary["kpis"]["known_cost_subtotal"] == summary["kpis"]["total_cost"]
        assert summary["model_qualifications"]["safety_calendar"]["start_date"] == "2025-01-01"
        assert summary["model_qualifications"]["process_tau_semantics"] == "planning_cover_only_physical_duration_pending_business_confirmation"
        assert summary["model_qualifications"]["static_mrp_basis"] == "nominal_process_capacity_times_bom_not_observed_demand"
        assert summary["model_qualifications"]["reserved_inventory_holding"] == "excluded_from_available_stock_holding_pending_ownership_rule"
        traces = csv_rows(output, "mrp_trace_daily.csv")
        day_two = [row for row in traces if int(row["day"]) == 2 and row["item_id"] == "item:A"]
        assert day_two and all(float(row["safety_time_source_days"]) == 1 for row in day_two)
        assert all(float(row["safety_time_days"]) == 3 for row in day_two)  # Friday -> Monday
        shipments = csv_rows(output, "production_supplier_shipments_daily.csv")
        assert shipments
        assert any(int(row["day"]) >= 8 for row in shipments)
        for row in shipments:
            assert row["execution_status"] == ("in_transit" if int(row["day"]) < 8 else "reserved_pending_departure")
            assert int(row["departure_executed"]) == int(int(row["day"]) < 8)
            assert float(row["executed_shipped_qty"]) == (float(row["shipped_qty"]) if int(row["day"]) < 8 else 0)
            assert row["realized_transport_lead_days"] == ""
            assert row["lead_time_information_status"] == "planned_not_yet_observed"
        # A transport taking 12 days has not yielded a lead-time observation by day 7.
        events = csv_rows(output, "supplier_state_dependent_risk_events.csv")
        assert not any(str(row.get("trigger_metric", "")).startswith("observed_lead") for row in events)
        assert summary["kpis"]["total_transport_cost"] == pytest.approx(
            sum(float(row["transport_cost"]) for row in shipments if int(row["day"]) < 8), abs=1e-4,
        )
    raw_mrp = csv_rows(outputs[0], "mrp_trace_daily.csv")
    smoothed_mrp = csv_rows(outputs[1], "mrp_trace_daily.csv")
    assert [row["bb_demand_signal_qty"] for row in raw_mrp] != [row["bb_demand_signal_qty"] for row in smoothed_mrp]


def test_engine_preserves_last_day_of_year_and_repeating_source_boundary(tmp_path):
    graph = _fixture_graph()
    graph["meta"]["generated_by_pipeline"] = {"repeat_period_days": 365}
    graph["scenarios"][0]["demand"][0]["profile"] = [{
        "type": "piecewise", "repeat_period_days": 365,
        "points": [{"t": 0, "value": 1}, {"t": 357, "value": 7}, {"t": 364, "value": 100}],
    }]
    output = tmp_path / "annual_boundary"
    summary = run_fixture(output, 7, days=366, graph_override=graph)
    rows = csv_rows(output, "production_demand_service_daily.csv")
    expected = [1] * 357 + [7] * 7 + [100, 1]
    assert [float(row["demand_qty"]) for row in rows] == expected
    assert summary["kpis"]["total_demand"] == sum(expected)
    shipments = csv_rows(output, "production_supplier_shipments_daily.csv")
    received = [row for row in shipments if row["execution_status"] == "received"]
    assert received
    for row in received:
        assert row["lead_time_information_status"] == "realized_at_receipt"
        assert int(row["realized_transport_lead_days"]) == int(row["arrival_day"]) - int(row["day"])
