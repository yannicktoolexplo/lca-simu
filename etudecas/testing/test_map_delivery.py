import csv
import json

import pytest

from . import map_delivery


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
