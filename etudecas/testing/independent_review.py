"""Read-only arithmetic audit of exported runs, independent of simulation code.

This is an explicit set of invariants, not a scientific certification. No engine,
payload builder or production validator is imported. Missing evidence fails the
audit. Run with --run DIR --output FILE. Exit 1 means a failed invariant.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path


class Evidence:
    def __init__(self):
        self.checks = {}

    def check(self, name, passed, example=None):
        check = self.checks.setdefault(name, {"checked": 0, "failed": 0, "examples": []})
        check["checked"] += 1
        if not passed:
            check["failed"] += 1
            if len(check["examples"]) < 5:
                check["examples"].append(example)

    def close(self, name, actual, expected, example=None, tolerance=0.00002):
        valid = math.isfinite(actual) and math.isfinite(expected)
        self.check(name, valid and math.isclose(actual, expected, abs_tol=tolerance, rel_tol=1e-10),
                   {"actual": actual, "expected": expected, "context": example})
        check = self.checks[name]
        check["absolute_tolerance"] = tolerance
        check["relative_tolerance"] = 1e-10
        gap = abs(actual - expected)
        if valid and gap > check.get("max_absolute_gap", -1):
            check["max_absolute_gap"] = gap
            check["max_gap_example"] = {"actual": actual, "expected": expected, "context": example}


def rows(run, name):
    with (run / "data" / (name + ".csv")).open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def number(row, field):
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {field}: {row}")
    return value


def integral(evidence, name, value, context):
    """User-confirmed rule: physical UN quantities are indivisible."""
    evidence.check(name, math.isfinite(value) and abs(value - round(value)) <= 1e-6,
                   {"quantity": value, "context": context})


def audit_service(series, evidence, item_units=None):
    """Demand balance, capacity to serve, and contiguous days per customer/item."""
    previous = defaultdict(float)
    last_day = defaultdict(lambda: -1)
    totals = Counter()
    for row in series:
        key = row["node_id"], row["item_id"]
        day = int(row["day"])
        demand, served, backlog, required, available = [number(row, f) for f in (
            "demand_qty", "served_qty", "backlog_end_qty", "required_with_backlog_qty",
            "available_before_service_qty")]
        if last_day[key] == -1:
            # An opening backlog is possible after warm-up; preserve it explicitly.
            previous[key] = required - demand
        evidence.check("service_contiguous_days", day == last_day[key] + 1, [key, day])
        evidence.check("service_nonnegative", min(demand, served, backlog, available, previous[key]) >= -0.00002, row)
        evidence.close("service_required", required, previous[key] + demand, [key, day])
        evidence.close("service_balance", backlog, previous[key] + demand - served, [key, day])
        evidence.check("service_within_available", served <= min(required, available) + 0.00002, row)
        if (item_units or {}).get(row["item_id"]) == "UN":
            integral(evidence, "customer_physical_service_integer_UN", served, [key, day])
            integral(evidence, "customer_physical_available_integer_UN", available, [key, day])
        totals["demand"] += demand
        totals["served"] += served
        totals["backlog_quantity_days"] += backlog
        previous[key] = backlog
        last_day[key] = day
    evidence.check("service_not_empty", bool(last_day))
    return {**totals, "ending_backlog": sum(previous.values()), "pairs": len(last_day),
            "last_days": list(last_day.values())}


def audit_run(run):
    e = Evidence()
    summary = json.loads((run / "summaries/first_simulation_summary.json").read_text(encoding="utf-8"))
    kpis = summary["kpis"]
    horizon = int(summary["sim_days"])
    events = list(rows(run, "production_lot_events"))
    item_units = {r["item_id"]: r["uom"] for r in events if r["uom"]}
    service = audit_service(rows(run, "production_demand_service_daily"), e, item_units)
    e.check("service_complete_horizon", bool(service["last_days"]) and all(d == horizon - 1 for d in service["last_days"]))
    for key, field in [("demand", "total_demand"), ("served", "total_served"),
                       ("ending_backlog", "ending_backlog"), ("backlog_quantity_days", "customer_delay_qty_day")]:
        e.close("service_summary_" + key, service[key], kpis[field], tolerance=0.02)

    daily = list(rows(run, "first_simulation_daily"))
    if summary.get("quantity_metric_contract"):
        # Capacity-limited requests never entered the physical system. Rebuild
        # quality loss from actual released purchase orders, not rejected needs.
        quality_loss = 0.0
        for order in rows(run, "mrp_orders_daily"):
            if not order["order_type"].startswith("external_procurement"):
                continue
            released = number(order, "release_qty")
            received = number(order, "planned_receipt_qty")
            e.check("procurement_receipt_within_release", 0 <= received <= released + 1e-6, order.get("mrp_order_id"))
            if item_units.get(order["item_id"]) == "UN":
                integral(e, "procurement_physical_integer_UN", released, order.get("mrp_order_id"))
                integral(e, "procurement_physical_integer_UN", received, order.get("mrp_order_id"))
            quality_loss += released - received
        e.close("procurement_quality_summary", quality_loss, kpis["total_external_quality_rejected_qty"], tolerance=0.02)
        e.close("procurement_quality_daily", quality_loss,
                sum(number(r, "external_quality_rejected_qty") for r in daily), tolerance=0.02)
        writeoff = sum(number(r, "stock_writeoff_qty") for r in rows(run, "production_supplier_stock_flows_daily"))
        e.close("losses_exclude_unexecuted_requests", kpis["non_quality_loss_qty"],
                kpis["total_unreliable_loss_qty"] + quality_loss + writeoff, tolerance=0.02)
    e.check("daily_horizon", [int(r["day"]) for r in daily] == list(range(horizon)))
    cost_columns = ["holding_cost_day", "warehouse_operating_cost_day", "inventory_risk_cost_day",
                    "transport_cost_day", "purchase_cost_day", "production_cost_day"]
    for r in daily:
        e.close("daily_cost_components", sum(number(r, f) for f in cost_columns),
                number(r, "total_supply_cost_day"), r["day"], tolerance=0.0004)
        e.close("daily_economic_exposure", number(r, "total_supply_cost_day") + number(r, "exceptional_supply_cost_day"),
                number(r, "total_economic_exposure_day"), r["day"], tolerance=0.0002)
    for field, metric in [("demand", "total_demand"), ("served", "total_served"),
                          ("produced_qty", "total_produced"), ("total_supply_cost_day", "total_cost"),
                          ("total_economic_exposure_day", "total_economic_exposure")]:
        e.close("daily_summary_" + metric, sum(number(r, field) for r in daily), kpis[metric],
                tolerance=len(daily) * 0.00005 + 0.0001)

    supplier_rows = 0
    for r in rows(run, "production_supplier_stock_flows_daily"):
        supplier_rows += 1
        expected = number(r, "stock_start_of_day") + number(r, "incoming_qty") - number(r, "stock_writeoff_qty") - number(r, "outgoing_pulled_qty")
        e.close("supplier_stock_balance", number(r, "stock_end_of_day"), expected, [r["day"], r["node_id"], r["item_id"]])
        e.close("supplier_loss_balance", number(r, "outgoing_pulled_qty"),
                number(r, "outgoing_shipped_qty") + number(r, "outgoing_unreliable_loss_qty"), [r["day"], r["node_id"], r["item_id"]])
        e.check("supplier_stock_nonnegative", number(r, "stock_end_of_day") >= -0.00002, r)
    e.check("supplier_rows_present", supplier_rows > 0)

    e.check("lot_events_present", bool(events))
    creations = {"opening_stock", "production_output", "lane_receipt", "external_procurement_receipt",
                 "opening_production_order", "stock_reconciliation", "estimated_source_receipt", "estimated_capacity_receipt"}
    debits = {"production_consume", "production_consume_reference_transition", "demand_service", "writeoff", "stock_writeoff", "shipment_reserve", "lane_ship"}
    reservations = {(r["lot_id"], r["shipment_id"]) for r in events if r["event_type"] == "shipment_reserve"}
    event_ids, state, first = set(), {}, {}
    produced = Counter()
    consumed = Counter()
    receipt_qty = Counter()
    shipment_qty = Counter()
    stock_by_pair = defaultdict(float)
    snapshots = {}
    types = Counter()
    previous_event_day = -1
    for r in events:
        typ, lot, day = r["event_type"], r["lot_id"], int(r["day"])
        pair = r["node_id"], r["item_id"]
        types[typ] += 1
        e.check("event_chronological_order", previous_event_day <= day, r["event_id"])
        previous_event_day = day
        e.check("event_unique_id", r["event_id"] not in event_ids, r["event_id"])
        event_ids.add(r["event_id"])
        qty, after = number(r, "qty"), number(r, "qty_after")
        e.check("lot_nonnegative", min(qty, after) >= -0.00002, r["event_id"])
        if r["uom"] == "UN":
            integral(e, "lot_physical_movement_integer_UN", qty, [r["event_id"], typ])
            integral(e, "lot_physical_stock_integer_UN", after, [r["event_id"], typ])
        e.check("event_type_known", typ in creations | debits, typ)
        before = state.get(lot, 0.0)
        if typ in creations:
            e.check("lot_single_creation", lot not in first, lot)
            first[lot] = r
            delta = qty
        elif typ == "lane_ship" and (lot, r["shipment_id"]) in reservations:
            delta = 0.0  # Physical departure of a quantity already reserved/debited.
        else:
            delta = -qty
        e.close("lot_movement_balance", after, before + delta, [r["event_id"], lot, typ])
        e.check("lot_identity_stable", lot in first and (first[lot]["node_id"], first[lot]["item_id"], first[lot]["uom"]) == (*pair, r["uom"]), r["event_id"])
        state[lot] = after
        stock_by_pair[pair] += delta
        snapshots[(day, *pair)] = stock_by_pair[pair]
        if typ in {"production_output", "opening_production_order"}:
            produced[(day, *pair)] += qty
        if typ.startswith("production_consume"):
            consumed[(lot, r["production_campaign_id"])] += qty
        if typ == "lane_receipt":
            receipt_qty[lot] += qty
        if typ == "lane_ship":
            shipment_qty[r["shipment_id"]] += qty

    for name in ["production_input_stocks_daily", "production_dc_stocks_daily", "production_output_products_daily", "production_supplier_stocks_daily"]:
        last_stock = defaultdict(float)
        observed_days = defaultdict(list)
        for r in rows(run, name):
            key = int(r["day"]), r["node_id"], r["item_id"]
            pair = key[1:]
            observed_days[pair].append(key[0])
            if key in snapshots:
                last_stock[pair] = snapshots[key]
            e.close("ledger_vs_" + name, last_stock[pair], number(r, "stock_end_of_day"), list(key), tolerance=0.02)
            if item_units.get(r["item_id"]) == "UN":
                integral(e, "physical_stock_integer_UN_" + name, number(r, "stock_end_of_day"), list(key))
            if name == "production_output_products_daily":
                e.close("released_vs_lot_output", produced[key], number(r, "released_qty"), list(key))
        e.check("stock_rows_present_" + name, bool(observed_days))
        for pair, days in observed_days.items():
            e.check("stock_horizon_" + name, days == list(range(horizon)), list(pair))

    genealogy = list(rows(run, "production_lot_genealogy"))
    production_links = Counter()
    transport_parents = Counter()
    for r in genealogy:
        parent, child = r["parent_lot_id"], r["child_lot_id"]
        e.check("genealogy_endpoints_exist", parent in first and child in first, [parent, child])
        if parent in first and child in first:
            e.check("genealogy_time_order", int(first[parent]["day"]) <= int(r["day"]) and int(first[child]["day"]) >= int(first[parent]["day"]), [parent, child, r["day"]])
        if r["link_type"] == "production":
            production_links[(parent, r["production_campaign_id"])] += number(r, "parent_qty")
        if r["link_type"] == "transport":
            transport_parents[child] += number(r, "parent_qty")
            e.check("transport_same_item", r["parent_item_id"] == r["child_item_id"], [parent, child])
    for key, amount in production_links.items():
        e.close("genealogy_consumption_within_recorded", min(amount, consumed[key]), amount, list(key), tolerance=0.02)
    for lot, received in receipt_qty.items():
        if lot in transport_parents:
            # Losses may occur during transport; receipts may not exceed inputs.
            e.check("transport_receipt_within_sent", received <= transport_parents[lot] + 0.02,
                    {"lot": lot, "received": received, "sent": transport_parents[lot]})

    return {"run": str(run.resolve()), "ok": all(v["failed"] == 0 for v in e.checks.values()),
            "scope": "Exported arithmetic and identities only; no source truth, causal attribution, or scientific qualification.",
            "horizon": horizon, "events": len(events), "lots": len(first), "genealogy_rows": len(genealogy),
            "event_types": dict(types), "checks": e.checks}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = audit_run(args.run)
    except (OSError, ValueError, KeyError) as exc:
        result = {"ok": False, "error": str(exc), "run": str(args.run)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "error": result.get("error"), "failed": {
        k: v["failed"] for k, v in result.get("checks", {}).items() if v["failed"]}}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
