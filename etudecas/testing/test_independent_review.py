"""Known-answer cases and deliberate corruption of independent audit evidence."""
import csv
import json

import pytest

from etudecas.testing.independent_review import Evidence, audit_run, audit_service


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
