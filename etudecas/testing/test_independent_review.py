"""Regression tests grouped by business responsibility; original cases retained."""
from __future__ import annotations

import csv
import json
import pytest
from etudecas.testing.independent_review import Evidence, audit_run, audit_service, audit_production_availability


@pytest.mark.parametrize('notes', [
    'semantics=campaign-batch-wip-release-v1;batch_id=CMP-16-B001',
    '{"semantics":"campaign-batch-wip-release-v1","availability_state":"held","available_day":108}',
])
def test_memory_wip_genealogy_recognizes_held_and_legacy_contracts(notes):
    from etudecas.simulation.analysis.audit_lot_paths import is_campaign_wip_release
    # Gien T: inputs consumed at J86 and J87 belong to the physical batch
    # completed at J87, even though its availability is later. The JSON
    # contract must select the same campaign reconciliation as legacy notes.
    assert is_campaign_wip_release(notes)


@pytest.mark.parametrize('notes', [
    None, '', '{broken JSON', '[]',
    '{"semantics":"campaign-batch-wip-release-v2"}',
    '{"availability_state":"held"}',
    '{"comment":"semantics=campaign-batch-wip-release-v1"}',
    '{"semantics":"other","comment":"semantics=campaign-batch-wip-release-v1"}',
])
def test_memory_wip_genealogy_does_not_infer_a_contract_from_hold_or_comment(notes):
    from etudecas.simulation.analysis.audit_lot_paths import is_campaign_wip_release
    assert not is_campaign_wip_release(notes)


def _quality_memory_event(kind, day, qty, *, lot='made', notes=''):
    return dict(event_type=kind, day=str(day), qty=str(qty), lot_id=lot,
                node_id='factory', item_id='PF', uom='UN', notes=notes)


def test_memory_independent_quality_preserves_physical_creation_and_releases_once():
    rows = [
        _quality_memory_event('production_output', 9, 100,
            notes='{"availability_state":"held","available_day":23}'),
        _quality_memory_event('stock_availability_hold', 9, 100),
        _quality_memory_event('stock_availability_release', 23, 100),
        _quality_memory_event('stock_availability_release', 23, 900, lot='purchased'),
    ]
    evidence = Evidence()
    output = audit_production_availability(rows, evidence)
    assert output[9, 'factory', 'PF'] == 0
    assert output[23, 'factory', 'PF'] == 100
    assert sum(output.values()) == 100
    assert all(c['failed'] == 0 for c in evidence.checks.values())
    assert rows[0]['day'] == '9' and rows[0]['qty'] == '100'


def test_memory_independent_quality_schedule_alone_does_not_create_available_stock():
    rows = [
        _quality_memory_event('opening_production_order', 9, 100,
            notes='{"availability_state":"held","available_day":23}'),
        _quality_memory_event('stock_availability_hold', 9, 100),
    ]
    evidence = Evidence()
    assert audit_production_availability(rows, evidence) == {}
    assert all(c['failed'] == 0 for c in evidence.checks.values())


def test_memory_independent_quality_keeps_legacy_unheld_outputs_available_immediately():
    rows = [_quality_memory_event('opening_production_order', 9, 100),
            _quality_memory_event('production_output', 12, 50, lot='new')]
    assert audit_production_availability(rows, Evidence()) == {
        (9, 'factory', 'PF'): 100, (12, 'factory', 'PF'): 50}


def test_memory_independent_quality_rejects_undocumented_initial_hold():
    rows = [_quality_memory_event('production_output', 9, 100),
            _quality_memory_event('stock_availability_hold', 9, 100),
            _quality_memory_event('stock_availability_release', 23, 100)]
    evidence = Evidence()
    audit_production_availability(rows, evidence)
    assert evidence.checks['production_initial_hold_requires_availability_metadata']['failed'] == 1


@pytest.mark.parametrize('fault, expected_check', [
    ('missing_hold', 'production_held_output_matches_neutral_hold'),
    ('early', 'production_quality_release_not_early'),
    ('duplicate', 'production_quality_release_once'),
])
def test_memory_independent_quality_rejects_invalid_in_memory_release(fault, expected_check):
    rows = [_quality_memory_event('production_output', 9, 100,
            notes='{"availability_state":"held","available_day":23}')]
    if fault != 'missing_hold':
        rows.append(_quality_memory_event('stock_availability_hold', 9, 100))
    rows.append(_quality_memory_event('stock_availability_release', 22 if fault == 'early' else 23, 100))
    if fault == 'duplicate':
        rows.append(_quality_memory_event('stock_availability_release', 24, 100))
    evidence = Evidence()
    audit_production_availability(rows, evidence)
    assert evidence.checks[expected_check]['failed'] == 1


def test_memory_path_completion_separates_work_physical_batch_and_availability():
    from etudecas.simulation.analysis.audit_lot_paths import physical_production_completions
    base = dict(campaign_id='campaign', semantics_version='campaign-batch-wip-release-v1')
    work = dict(base, event_type='execute_campaign', actual_qty='40', released_qty='0',
                physical_completed_qty='0')
    completed = dict(base, event_type='execute_campaign', actual_qty='60', released_qty='0',
                     physical_completed_qty='100',
                     release_gate_mode='physical_completion_then_source_weekday_quality')
    release = dict(base, event_type='quality_release', actual_qty='0', released_qty='100',
                   physical_completed_qty='0', release_gate_mode='source_weekday_quality_release')
    assert physical_production_completions([work]) == {'campaign': 0}
    assert physical_production_completions([work, completed]) == {'campaign': 100}
    assert physical_production_completions([work, completed, release]) == {'campaign': 100}


def test_memory_path_completion_keeps_legacy_release_contract():
    from etudecas.simulation.analysis.audit_lot_paths import physical_production_completions
    rows = [dict(campaign_id='old', event_type='start_campaign', actual_qty='12'),
            dict(campaign_id='batch', semantics_version='campaign-batch-wip-release-v1', released_qty='100'),
            dict(campaign_id='batch', semantics_version='campaign-batch-wip-release-v1',
                 released_qty='50', physical_completed_qty='')]
    assert physical_production_completions(rows) == {'old': 12, 'batch': 150}


@pytest.mark.parametrize('changes', [
    {}, {'physical_completed_qty': '-1'}, {'physical_completed_qty': 'nan'},
    {'physical_completed_qty': '100', 'event_type': 'quality_release'},
])
def test_memory_path_completion_rejects_missing_invalid_or_duplicate_physical_quantity(changes):
    from etudecas.simulation.analysis.audit_lot_paths import physical_production_completions
    row = dict(campaign_id='held', semantics_version='campaign-batch-wip-release-v1',
               release_gate_mode='physical_completion_then_source_weekday_quality', **changes)
    with pytest.raises(ValueError):
        physical_production_completions([row])


@pytest.mark.parametrize('mode,function,names', [
    ('journey', 'review_journey', ('html', 'data', 'output')),
    ('case', 'review_case', ('html', 'scenario_html', 'data', 'output')),
    ('explorer', 'review_explorer', ('html', 'data', 'graph', 'output')),
    ('scenario', 'review_scenario', ('html', 'data', 'output')),
    ('material', 'review_material', ('html', 'data', 'output')),
    ('usability', 'audit_usability', ('html', 'output')),
])
def test_historical_browser_dispatch_preserves_arguments_and_failure_status(monkeypatch, mode, function, names):
    from etudecas.testing import historical_browser
    calls = []
    def unsuccessful(*args):
        calls.append(args)
        return {'ok': False, 'javascript_errors': []}
    monkeypatch.setattr(historical_browser, function, unsuccessful)
    argv = [mode]
    expected = []
    for name in names:
        value = name + '-fixture'
        argv += ['--' + name.replace('_', '-'), value]
        expected.append(Path(value))
    assert historical_browser.main(argv) == (0 if mode == 'usability' else 1)
    assert calls == [tuple(expected)]
from collections import defaultdict
from etudecas.simulation.engine.run_first_simulation import (
    LotLedger, physical_execution_quantity, seed_lane_pipeline_uniform, scale_physical_allocations,
)
from etudecas.simulation.analysis_batch_common import apply_scales
from etudecas.simulation.source_fingerprint import implementation_fingerprint
from etudecas.testing.qualification import qualify, require_run_invariants
from . import map_delivery
from pathlib import Path
import subprocess
import sys


# Independent review

def write_csv(root, name, rows):
    path = root / "data" / (name + ".csv")
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def known_run(tmp_path):
    # Ten initial units: four move to a depot; six remain at the factory.
    # Four customer units are requested but none are delivered during this day.
    (tmp_path / "summaries").mkdir()
    (tmp_path / "summaries/first_simulation_summary.json").write_text(json.dumps({
        "sim_days": 1, "kpis": {"total_demand": 4, "total_served": 0,
        "ending_backlog": 4, "customer_delay_qty_day": 4, "total_produced": 0,
        "total_cost": 0, "total_economic_exposure": 0}}))
    write_csv(tmp_path, "production_demand_service_daily", [{"day": 0, "node_id": "C", "item_id": "FG",
        "demand_qty": 4, "served_qty": 0, "backlog_end_qty": 4, "required_with_backlog_qty": 4,
        "available_before_service_qty": 0}])
    write_csv(tmp_path, "first_simulation_daily", [{"day": 0, "demand": 4, "served": 0,
        "produced_qty": 0, **{c: 0 for c in ["holding_cost_day", "warehouse_operating_cost_day",
        "inventory_risk_cost_day", "transport_cost_day", "purchase_cost_day", "production_cost_day",
        "total_supply_cost_day", "exceptional_supply_cost_day", "total_economic_exposure_day"]}}])
    write_csv(tmp_path, "production_supplier_stock_flows_daily", [{"day": 0, "node_id": "S", "item_id": "RAW",
        **{c: 0 for c in ["stock_start_of_day", "incoming_qty", "stock_writeoff_qty", "outgoing_pulled_qty",
        "outgoing_shipped_qty", "outgoing_unreliable_loss_qty", "stock_end_of_day"]}}])
    events = []
    for id_, typ, lot, node, qty, after in [("E1", "opening_stock", "A", "F", 10, 10),
                                          ("E2", "lane_ship", "A", "F", 4, 6),
                                          ("E3", "lane_receipt", "B", "D", 4, 4)]:
        events.append(dict(event_id=id_, day=0, event_type=typ, lot_id=lot, node_id=node,
                           item_id="FG", uom="UN", qty=qty, qty_after=after,
                           shipment_id="SHIP" if id_ != "E1" else "", production_campaign_id=""))
    write_csv(tmp_path, "production_lot_events", events)
    for name, node, item, stock in [("production_input_stocks_daily", "F", "RAW", 0),
            ("production_dc_stocks_daily", "D", "FG", 4),
            ("production_supplier_stocks_daily", "S", "RAW", 0),
            ("production_output_products_daily", "F", "FG", 6)]:
        write_csv(tmp_path, name, [dict(day=0, node_id=node, item_id=item, stock_end_of_day=stock, released_qty=0)])
    write_csv(tmp_path, "production_lot_genealogy", [dict(day=0, link_type="transport", parent_lot_id="A",
        child_lot_id="B", parent_item_id="FG", child_item_id="FG", parent_qty=4, child_qty=4)])
    return tmp_path


def test_independent_known_answer(known_run):
    result = audit_run(known_run)
    assert result["ok"], result


def test_unexecuted_purchase_request_is_not_a_physical_loss(known_run):
    path = known_run / "summaries/first_simulation_summary.json"
    summary = json.loads(path.read_text())
    summary["quantity_metric_contract"] = {"external_procured_rejected_qty": "unexecuted requests"}
    summary["kpis"].update(total_external_quality_rejected_qty=1,
                           total_unreliable_loss_qty=0, non_quality_loss_qty=1)
    path.write_text(json.dumps(summary))
    daily_path = known_run / "data/first_simulation_daily.csv"
    with daily_path.open(newline="") as stream:
        daily = list(csv.DictReader(stream))
    daily[0].update(external_quality_rejected_qty=1, external_procured_rejected_qty=100)
    write_csv(known_run, "first_simulation_daily", daily)
    write_csv(known_run, "mrp_orders_daily", [{"order_type": "external_procurement", "item_id": "FG",
        "mrp_order_id": "P1", "release_qty": 1, "planned_receipt_qty": 0}])
    assert audit_run(known_run)["ok"]
    # One physically rejected piece plus 100 unexecuted requests is NOT 101 lost pieces.
    summary["kpis"]["non_quality_loss_qty"] = 101
    path.write_text(json.dumps(summary))
    assert audit_run(known_run)["checks"]["losses_exclude_unexecuted_requests"]["failed"] == 1


@pytest.mark.parametrize("file,field,value,check", [
    ("production_dc_stocks_daily", "stock_end_of_day", 5, "ledger_vs_production_dc_stocks_daily"),
    ("production_output_products_daily", "stock_end_of_day", 10, "ledger_vs_production_output_products_daily"),
    ("production_demand_service_daily", "served_qty", 1, "service_balance"),
    ("production_supplier_stock_flows_daily", "stock_end_of_day", 3, "supplier_stock_balance"),
    ("production_lot_events", "qty", 11, "lot_movement_balance"),
    ("production_lot_genealogy", "parent_lot_id", "ABSENT", "genealogy_endpoints_exist"),
])
def test_corruption_is_rejected(known_run, file, field, value, check):
    with (known_run / "data" / (file + ".csv")).open(newline="") as stream:
        records = list(csv.DictReader(stream))
    records[0][field] = value
    write_csv(known_run, file, records)
    result = audit_run(known_run)
    assert not result["ok"]
    assert result["checks"][check]["failed"] > 0


def test_missing_evidence_not_success(known_run):
    (known_run / "data/production_lot_genealogy.csv").unlink()
    with pytest.raises(FileNotFoundError):
        audit_run(known_run)


def test_fractional_forecast_allowed_but_fractional_physical_service_rejected():
    forecast = dict(day=0, node_id="C", item_id="FG", demand_qty=1.5, served_qty=0,
                    backlog_end_qty=1.5, required_with_backlog_qty=1.5, available_before_service_qty=0)
    e = Evidence()
    audit_service([forecast], e, {"FG": "UN"})
    assert all(c["failed"] == 0 for c in e.checks.values())
    e = Evidence()
    audit_service([{**forecast, "served_qty": 1.5, "backlog_end_qty": 0, "available_before_service_qty": 2}], e, {"FG": "UN"})
    assert e.checks["service_balance"]["failed"] == 0
    assert e.checks["customer_physical_service_integer_UN"]["failed"] == 1


# Correction contracts

def test_fractional_forecast_accumulates_without_losing_demand():
    ledger = LotLedger(enabled=True)
    ledger.create_lot(day=0, node_id="C", item_id="P", qty=10, uom="UN", source_type="opening_stock")
    stock, backlog, services = 10, 0, []
    for day in range(4):
        required = backlog + 0.5
        served = physical_execution_quantity(min(stock, required), "UN")
        ledger.consume(day=day, node_id="C", item_id="P", qty=served, uom="UN", event_type="demand_service")
        stock -= served
        backlog = required - served
        services.append(served)
    assert services == [0, 1, 0, 1]
    assert backlog == 0 and stock == 8
    assert sum(lot["qty_remaining"] for lot in ledger.lots.values()) == 8


def test_uniform_transit_preserves_ten_whole_units_across_three_days():
    pipeline, transit = defaultdict(list), defaultdict(float)
    seed_lane_pipeline_uniform(pipeline, transit, dst="D", item_id="P", qty=10,
                               edge_id="E", lead_days=3, uom="UN")
    assert [pipeline[day][0][2] for day in range(3)] == [3, 3, 4]
    assert transit[("D", "P")] == 10


def test_physical_execution_retains_mass_precision():
    assert physical_execution_quantity(0.125, "KG") == 0.125
    assert physical_execution_quantity(2.9, "UN") == 2
    with pytest.raises(ValueError):
        physical_execution_quantity(float("nan"), "UN")


def test_scaled_transit_parents_conserve_whole_total():
    parents = [{"lot_id": "a", "qty": 3}, {"lot_id": "b", "qty": 7}]
    actual = scale_physical_allocations(parents, 0.75, "UN")
    assert [p["qty"] for p in actual] == [2, 5]
    assert sum(p["qty"] for p in actual) == physical_execution_quantity(10 * .75, "UN")


@pytest.mark.parametrize("factors", [{"typo": 0.5}, {"capacity_scale": float("nan")}, {"capacity_scale": "0.5"}])
def test_invalid_sensitivity_cannot_be_recorded_as_applied(factors):
    with pytest.raises(ValueError):
        apply_scales({"scenarios": [{"id": "base"}]}, "base", factors)


def test_sibling_runtime_change_invalidates_cache(tmp_path):
    engine = tmp_path / "etudecas/simulation/engine/main.py"
    sibling = tmp_path / "etudecas/simulation/lot_policy/rule.py"
    engine.parent.mkdir(parents=True)
    sibling.parent.mkdir(parents=True)
    engine.write_text("from etudecas.simulation.lot_policy.rule import RATE")
    sibling.write_text("RATE = 1")
    before = implementation_fingerprint(engine)
    sibling.write_text("RATE = 2")
    assert implementation_fingerprint(engine) != before


def test_delivery_gate_refuses_corrupt_stock_and_missing_evidence(known_run):
    assert require_run_invariants(known_run)["ok"]
    write_csv(known_run, "production_output_products_daily", [dict(day=0, node_id="F", item_id="FG", stock_end_of_day=10, released_qty=0)])
    with pytest.raises(ValueError, match="Delivery refused"):
        require_run_invariants(known_run)
    report = qualify([known_run], known_run / "review")
    assert not report["ok"] and not report["display_verified"]
    (known_run / "data/production_lot_events.csv").unlink()
    assert not qualify([known_run], known_run / "review")["ok"]


# Map delivery

@pytest.fixture
def run(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "summaries").mkdir()
    (tmp_path / "summaries/first_simulation_summary.json").write_text(json.dumps({
        "sim_days": 2, "scenario_id": "synthetic", "kpis": {
            "total_demand": 10, "total_served": 9, "ending_backlog": 1,
            "fill_rate": .9, "total_cost": 12, "total_external_procurement_cost": 4, "total_economic_exposure": 16}}))
    (tmp_path / "data/first_simulation_daily.csv").write_text(
        "day,total_supply_cost_day,external_procurement_transport_cost_day,external_procurement_purchase_cost_day\n"
        "0,5,1,2\n1,7,0,1\n")
    path = tmp_path / "data/production_demand_service_daily.csv"
    path.write_text("day,node_id,item_id,demand_qty,served_qty,backlog_end_qty,required_with_backlog_qty\n"
                    "0,C,A,5,3,2,5\n1,C,A,5,6,1,7\n")
    monkeypatch.setattr(map_delivery, "validate_run_package", lambda _: [{"name": "isolated_package_check", "ok": True}])
    return tmp_path


def test_cumulative_service_and_backlog_include_delayed_deliveries(run):
    result = map_delivery.reconcile_run(run)
    assert result["ok"]
    assert result["csv_totals"]["fill_rate"] == .9
    assert result["days_with_backlog_including_startup"] == 2
    assert result["backlog_quantity_days"] == 3


def test_fractional_forecast_days_are_not_hidden_by_a_different_cutoff(run):
    csv_path = run / "data/production_demand_service_daily.csv"
    csv_path.write_text("day,node_id,item_id,demand_qty,served_qty,backlog_end_qty,required_with_backlog_qty\n"
                        "0,C,A,0.0001,0,0.0001,0.0001\n1,C,A,0,0,0.0001,0.0001\n")
    summary_path = run / "summaries/first_simulation_summary.json"
    summary = json.loads(summary_path.read_text())
    summary["kpis"].update(total_demand=.0001,total_served=0,ending_backlog=.0001,fill_rate=0)
    summary_path.write_text(json.dumps(summary))
    result = map_delivery.reconcile_run(run)
    assert result["ok"]
    assert result["days_with_backlog_including_startup"] == 2


@pytest.mark.parametrize("damage", ["duplicate", "missing_day", "changed_total", "negative", "nan"])
def test_reconciliation_rejects_damaged_csv(run, damage):
    path = run / "data/production_demand_service_daily.csv"
    text = path.read_text()
    if damage == "duplicate":
        text += "1,C,A,5,6,1,7\n"
    elif damage == "missing_day":
        text = text.replace("1,C,A,5,6,1,7\n", "")
    else:
        replacement = {"changed_total": "4", "negative": "-1", "nan": "nan"}[damage]
        text = text.replace("0,C,A,5,3,2,5", f"0,C,A,5,{replacement},2,5")
    path.write_text(text)
    assert not map_delivery.reconcile_run(run)["ok"]


def test_package_failure_remains_a_delivery_failure(run, monkeypatch):
    monkeypatch.setattr(map_delivery, "validate_run_package", lambda _: [{"name": "missing_csv", "ok": False}])
    assert map_delivery.reconcile_run(run)["errors"] == ["package: missing_csv"]


@pytest.mark.parametrize("damage", [None, "score_source", "cost_delta", "fill_rate", "html", "duplicate", "scope", "score", "unknown_as_complete", "null_as_zero", "cost_exclusion", "old_contract", "startup", "duplicate_cost_day", "missing_cost_day"])
def test_browser_values_are_reconciled_with_runs(run, damage):
    numeric = map_delivery.reconcile_run(run)
    html = run / "map.html"
    html.write_text("reviewed")
    scenario = {"id": run.name, "is_reference": True, "horizon_days": 2,
                "kpis": {"total_demand": 10, "total_served": 9, "ending_backlog": 1,
                         "fill_rate": .9, "total_cost": 12, "cost_delta": 0,
                         "fill_rate_delta_pp": 0, "backlog_days": 2, "startup_backlog_days": 0,
                         "max_backlog": 2, "operating_cost": 12, "external_procurement_cost": 4,
                         "economic_exposure": 16, "operating_cost_delta": 0, "economic_exposure_delta": 0,
                         "valuation_complete": False, "valuation_status": "unknown", "economic_ranking_eligible": False,
                         "monetary_comparison_eligible": False, "score_contract": "customer_cost_v3_valuation_guard",
                         "score_excluded_dimensions": ["material_loss", "replanning", "cost"],
                         "cost_delta_pct": None, "observed_impact_score": 60}}
    browser = {"ok": True, "html": str(html), "html_sha256": map_delivery.file_hash(html),
               "payload": {"comparison": [scenario]}}
    if damage == "score_source":
        browser["ok"] = False  # A failed display check must not be hidden by matching quantities.
    elif damage in {"cost_delta", "fill_rate"}:
        scenario["kpis"][damage] = 42
    elif damage == "html":
        html.write_text("changed after review")
    elif damage == "duplicate":
        browser["payload"]["comparison"].append(scenario)
    elif damage == "scope":
        scenario["kpis"]["economic_exposure"] = 12
    elif damage == "score":
        scenario["kpis"]["observed_impact_score"] = 60.5
    elif damage == "unknown_as_complete":
        scenario["kpis"]["valuation_complete"] = True
    elif damage == "null_as_zero":
        scenario["kpis"]["cost_delta_pct"] = 0
    elif damage == "cost_exclusion":
        scenario["kpis"]["score_excluded_dimensions"].remove("cost")
    elif damage == "old_contract":
        scenario["kpis"]["score_contract"] = "customer_cost_v2"
    elif damage == "startup":
        scenario["kpis"].update(backlog_days=1, startup_backlog_days=1)
    elif damage in {"duplicate_cost_day", "missing_cost_day"}:
        costs = run / "data/first_simulation_daily.csv"
        text = costs.read_text()
        costs.write_text(text + "1,0,0,0\n" if damage == "duplicate_cost_day" else text.replace("1,7,0,1\n", ""))
    errors = map_delivery.reconcile_browser(browser, [numeric])
    assert bool(errors) == (damage is not None)


@pytest.mark.parametrize("daily_terms, summary, expected", [
    (6, 12.0006, True), (6, 12.0007, False),
    (1, 12.0001, True), (1, 12.0002, False),
])
def test_cost_rounding_bound_accepts_only_mathematically_possible_error(daily_terms, summary, expected):
    result = map_delivery.reconcile_exported_cost(["5.0000", "7.0000"], summary, rounding_terms_per_value=daily_terms)
    assert result["ok"] is expected
    assert result["rounding_terms"] == 2 * daily_terms + 1
    assert result["rounding_tolerance"] == ("0.00065" if daily_terms == 6 else "0.00015")


def test_long_horizon_rounding_accepts_accumulation_but_rejects_one_currency_unit():
    values = ["100.0000"] * 1825
    result = map_delivery.reconcile_exported_cost(values, 182500.0378, rounding_terms_per_value=6)
    assert result["ok"]
    assert result["rounding_tolerance"] == "0.54755"
    assert not map_delivery.reconcile_exported_cost(values, 182501, rounding_terms_per_value=6)["ok"]
    external = map_delivery.reconcile_exported_cost(values * 2, 365000.0112, rounding_terms_per_value=1)
    assert external["ok"]
    assert external["rounding_tolerance"] == "0.18255"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "invalid", "1.00001"])
def test_unexpected_cost_export_precision_is_not_silently_tolerated(value):
    with pytest.raises(ValueError):
        map_delivery.reconcile_exported_cost([value], 1, rounding_terms_per_value=6)


@pytest.mark.parametrize("damage", [None, "exposure_used_in_score", "summary_and_html_forged", "inconsistent_coverage"])
def test_complete_cost_scopes_use_independent_csv_and_operating_score(run, damage):
    import shutil
    summary_path = run / "summaries/first_simulation_summary.json"
    summary = json.loads(summary_path.read_text())
    summary["economic_valuation"] = {"status": "complete", "complete": True, "unknown_inventory_pairs": []}
    summary_path.write_text(json.dumps(summary))
    risk = run / "risk"
    shutil.copytree(run / "data", risk / "data")
    shutil.copytree(run / "summaries", risk / "summaries")
    risk_summary_path = risk / "summaries/first_simulation_summary.json"
    risk_summary = json.loads(risk_summary_path.read_text())
    risk_summary["kpis"].update(total_cost=18, total_external_procurement_cost=1, total_economic_exposure=19)
    if damage == "inconsistent_coverage":
        risk_summary["economic_valuation"]["unknown_inventory_pairs"] = [{"node_id": "M", "item_id": "missing-price"}]
    risk_summary_path.write_text(json.dumps(risk_summary))
    (risk / "data/first_simulation_daily.csv").write_text(
        "day,total_supply_cost_day,external_procurement_transport_cost_day,external_procurement_purchase_cost_day\n"
        "0,10,1,0\n1,8,0,0\n")
    # Literal oracle: same backlog (2/10=20%), no service loss; operating
    # cost +50% contributes 12.5 points. Exposure increases by only 3.
    common = dict(total_demand=10, total_served=9, ending_backlog=1, fill_rate=.9, fill_rate_delta_pp=0,
                  max_backlog=2, backlog_days=2, startup_backlog_days=0, valuation_complete=True,
                  valuation_status="complete", economic_ranking_eligible=True, monetary_comparison_eligible=True,
                  score_contract="customer_cost_v3_valuation_guard", score_excluded_dimensions=["material_loss", "replanning"])
    scenarios = [dict(id=run.name, is_reference=True, horizon_days=2, kpis=dict(common, total_cost=12, operating_cost=12, external_procurement_cost=4, economic_exposure=16, cost_delta=0, operating_cost_delta=0, economic_exposure_delta=0, cost_delta_pct=0, observed_impact_score=60)),
                 dict(id="risk", is_reference=False, horizon_days=2, kpis=dict(common, total_cost=18, operating_cost=18, external_procurement_cost=1, economic_exposure=19, cost_delta=6, operating_cost_delta=6, economic_exposure_delta=3, cost_delta_pct=50, observed_impact_score=72.5))]
    if damage == "exposure_used_in_score":
        scenarios[1]["kpis"]["observed_impact_score"] = 64.6875
    elif damage == "summary_and_html_forged":
        risk_summary["kpis"].update(total_cost=24, total_economic_exposure=25)
        risk_summary_path.write_text(json.dumps(risk_summary))
        scenarios[1]["kpis"].update(total_cost=24, operating_cost=24, economic_exposure=25, cost_delta=12, operating_cost_delta=12, economic_exposure_delta=9, cost_delta_pct=100, observed_impact_score=85)
    html = run / "map.html"
    html.write_text("reviewed")
    browser = dict(ok=True, html=str(html), html_sha256=map_delivery.file_hash(html), payload=dict(comparison=scenarios))
    errors = map_delivery.reconcile_browser(browser, [map_delivery.reconcile_run(run), map_delivery.reconcile_run(risk)])
    assert bool(errors) == (damage is not None)


# Delivery compatibility

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name', ['journey_scenario_delivery', 'material_delivery'])
def test_delivery_cli_help_remains_available(name):
    mode = 'scenario' if name == 'journey_scenario_delivery' else 'refresh'
    arguments = ['-m', 'etudecas.visualization.maps.material_delivery', '--mode', mode]
    result = subprocess.run([sys.executable, '-B', *arguments, '--help'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    for option in ('--data', '--graph', '--output', '--evidence'):
        assert option in result.stdout


def test_scenario_cli_publishes_with_canonical_source_paths(tmp_path):
    from etudecas.testing.test_lot_journey import scenario_files
    from etudecas.visualization.maps import material_delivery as canonical

    data, graph = scenario_files(tmp_path)
    output = tmp_path / 'scenario.html'
    evidence = tmp_path / 'proof'
    result = subprocess.run([
        sys.executable, '-B', '-m', 'etudecas.visualization.maps.material_delivery',
        '--mode', 'scenario',
        '--data', str(data), '--graph', str(graph), '--output', str(output),
        '--evidence', str(evidence),
    ], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads((evidence / 'scenario-provenance.json').read_text(encoding='utf8'))
    assert report['scenario'] == 'scn:TEST'
    sources = {Path(path).resolve() for path in report['sources']}
    assert Path(canonical.__file__).resolve() in sources
    assert ROOT / 'etudecas/simulation/lot_trace/materials.py' in sources
    assert ROOT / 'etudecas/visualization/maps/lot_journey.js' in sources
    assert all(path.is_file() for path in sources)
    assert output.is_file()


import hashlib
import json
from copy import deepcopy


def _observed_qualification_memory_case():
    source = dict(node_id='M', item_id='X', uom='KG', demand_id='forecast',
                  known_day=0, period_start_day=0, period_days=3, qty=6,
                  source_file='forecast.xlsx', source_cells='I2', estimation_basis='forecast')
    forecast = dict(schema_version=1, scenario_id='memory', repeat_period_days=None, rows=[source])
    observed_rows = [dict(source, demand_id='observed-' + str(day), known_day=day,
                         period_start_day=day, period_days=1, qty=qty,
                         source_file='movements.xlsx', source_cells='I3', estimation_basis='observed I')
                     for day, qty in ((1, 0), (2, 3))]
    observed = dict(schema_version=1, physical_use_only=True, repeat_period_days=None,
                    scenario_id='memory', rows=observed_rows)
    series = []
    for day, demand, backlog, available, consumed, end in [(0, 2, 0, 1, 1, 1), (1, 0, 1, 0, 0, 1), (2, 3, 1, 5, 4, 0)]:
        observation = next((r for r in observed_rows if r['known_day'] == day), None)
        series.append(dict(day=day, node_id='M', item_id='X', uom='KG', demand_qty=demand,
            backlog_start_qty=backlog, required_qty=demand + backlog, consumed_qty=consumed,
            backlog_end_qty=end, available_before_qty=available, available_after_qty=available - consumed,
            core_consumed_qty=0, total_component_consumed_qty=consumed,
            physical_demand_source='observed_other_uses' if observation else 'estimated_other_uses',
            physical_source_file=observation['source_file'] if observation else '',
            physical_source_cells=observation['source_cells'] if observation else '',
            physical_observation_qty=observation['qty'] if observation else '',
            physical_demand_known_day=day if observation else ''))
    events = []
    for execution_day, quantity, declared, due in [(0, 1, source, 0), (2, 1, source, 0), (2, 3, observed_rows[1], 2)]:
        actual = declared is not source
        note = dict(scope='observed_non_modelled_component_use' if actual else 'estimated_non_modelled_component_use',
            physical_demand_source='observed_other_uses' if actual else 'estimated_other_uses',
            due_day=due, known_day=declared['known_day'], cycle_index=0, scenario_id='memory',
            **{k: declared[k] for k in ('demand_id', 'source_file', 'source_cells', 'estimation_basis')})
        events.append(dict(event_type='external_component_consume', day=execution_day, node_id='M',
            item_id='X', uom='KG', qty=quantity,
            source_id=f"external:memory:{declared['demand_id']}:C0:D{due}", notes=json.dumps(note)))
    return series, events, forecast, observed


def test_memory_observed_qualification_replaces_zero_and_retains_earlier_backlog():
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    series, events, forecast, observed = _observed_qualification_memory_case()
    e = Evidence()
    audit_external_component_service(series, events, [], forecast, 3, e, observed_policy=observed)
    assert not {k: v for k, v in e.checks.items() if v['failed']}


def test_memory_observed_qualification_rejects_falsified_quantities_and_provenance():
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    for mutation in ('demand', 'known', 'scope', 'double_debit', 'zero_missing'):
        series, events, forecast, observed = deepcopy(_observed_qualification_memory_case())
        if mutation == 'demand':
            series[2]['demand_qty'] = 4
        elif mutation == 'known':
            observed['rows'][1]['known_day'] = 1
        elif mutation == 'scope':
            note = json.loads(events[-1]['notes'])
            note['scope'] = 'estimated_non_modelled_component_use'
            events[-1]['notes'] = json.dumps(note)
        elif mutation == 'double_debit':
            events[-1]['qty'] = 4
        else:
            observed['rows'].pop(0)
        e = Evidence()
        audit_external_component_service(series, events, [], forecast, 3, e, observed_policy=observed)
        assert any(v['failed'] for v in e.checks.values()), mutation


def test_memory_observed_qualification_requires_original_graph_sha():
    from etudecas.testing.independent_review import Evidence, observed_policy_from_graph_bytes
    _, _, _, observed = _observed_qualification_memory_case()
    data = json.dumps({'meta': {'observed_external_component_demands': observed}}).encode()
    e = Evidence()
    assert observed_policy_from_graph_bytes(data, hashlib.sha256(data).hexdigest(), e) == observed
    assert all(not v['failed'] for v in e.checks.values())
    bad = Evidence()
    assert observed_policy_from_graph_bytes(data, '0' * 64, bad) is None
    assert bad.checks['observed_original_input_sha256']['failed'] == 1
