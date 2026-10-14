"""Read-only arithmetic audit of exported runs, independent of simulation code.

This is an explicit set of invariants, not a scientific certification. No engine,
payload builder or production validator is imported. Missing evidence fails the
audit. Run with --run DIR --output FILE. Exit 1 means a failed invariant.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from decimal import Decimal
from datetime import date, timedelta
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


def audit_production_consumption(links, consumed, completed_campaigns, evidence):
    """Closed campaigns must account for every consumed parent quantity.

    Open campaigns can retain consumed material in WIP, so their released
    genealogy is bounded above instead of being forced equal prematurely.
    Iterate the union: a completely missing parent link must also fail.
    """
    for key in links.keys() | consumed.keys():
        linked, actual = links.get(key, 0.0), consumed.get(key, 0.0)
        if key[1] in completed_campaigns:
            evidence.close("closed_campaign_material_genealogy", linked, actual,
                           list(key), tolerance=0.02)
        else:
            evidence.close("genealogy_consumption_within_recorded",
                           min(linked, actual), linked, list(key), tolerance=0.02)


def audit_production_availability(events, evidence):
    """Independently count usable outputs; creation and quality release differ.

    Planned dates never create a flow. Raw lot creation remains the physical
    stock/BOM evidence elsewhere in this audit. Only initially held production
    lots contribute a delayed usable output, once and at their actual release.
    """
    available, held_outputs, actual_holds = Counter(), {}, Counter()
    unheld_outputs = set()
    for row in events:
        event, lot = row['event_type'], row['lot_id']
        if event == 'stock_availability_hold':
            actual_holds[int(row['day']), lot] += number(row, 'qty')
        if event not in ('production_output', 'opening_production_order'):
            continue
        day, qty = int(row['day']), number(row, 'qty')
        notes_text = row.get('notes') or ''
        notes = json.loads(notes_text) if notes_text.lstrip().startswith('{') else {}
        if notes.get('availability_state') == 'held':
            available_day = notes.get('available_day')
            valid_date = type(available_day) is int and available_day >= day
            evidence.check('production_held_date_documented', valid_date, row)
            held_outputs[lot] = dict(day=day, available_day=available_day if valid_date else day,
                qty=qty, remaining=qty, node=row['node_id'], item=row['item_id'], uom=row['uom'])
        else:
            available[day, row['node_id'], row['item_id']] += qty
            unheld_outputs.add((day, lot))
    for key in unheld_outputs:
        evidence.check('production_initial_hold_requires_availability_metadata',
            actual_holds[key] == 0, key)
    for lot, physical in held_outputs.items():
        evidence.close('production_held_output_matches_neutral_hold',
            actual_holds[physical['day'], lot], physical['qty'], lot)
    for row in events:
        if row['event_type'] != 'stock_availability_release' or row['lot_id'] not in held_outputs:
            continue
        physical = held_outputs[row['lot_id']]
        day, qty = int(row['day']), number(row, 'qty')
        evidence.check('production_quality_release_identity',
            (row['node_id'], row['item_id'], row['uom']) ==
            (physical['node'], physical['item'], physical['uom']), row)
        evidence.check('production_quality_release_not_early', day >= physical['available_day'], row)
        evidence.check('production_quality_release_once', 0 <= qty <= physical['remaining'] + 0.00002, row)
        physical['remaining'] -= qty
        available[day, row['node_id'], row['item_id']] += qty
    return available


def audit_declared_receipt_dates(meta, policy, events, orders, evidence):
    """Recount new G-to-I dates from declared calendars, without engine helpers.

    Source-dated opening orders and initial held stock are deliberately excluded.
    This optional contract certifies date arithmetic, not the industrial duration.
    """
    declaration = meta.get("receipt_calendar_policy")
    if declaration is None:
        return
    exported = policy.get("dated_component_planning", {}).get("receipt_calendar_policy", {})
    evidence.check("receipt_calendar_export_matches_input",
                   isinstance(exported, dict) and all(exported.get(k) == v for k, v in declaration.items()))
    valid = (type(declaration.get("schema_version")) is int and declaration.get("schema_version") == 1
             and declaration.get("mode") == "explicit_site_nonworking_dates_v1"
             and isinstance(declaration.get("sites"), list))
    evidence.check("receipt_calendar_declared_contract", valid)
    if not valid:
        return
    try:
        origin = date.fromisoformat(meta.get("mrp_forecasts", {}).get("origin", ""))
    except (TypeError, ValueError):
        evidence.check("receipt_calendar_origin_documented", False)
        return
    evidence.check("receipt_calendar_origin_documented", True)
    closed = {}
    for row in declaration["sites"]:
        node = row.get("node_id")
        evidence.check("receipt_calendar_unique_site", bool(node) and node not in closed, node)
        try:
            values = row["nonworking_dates"]
            parsed = {date.fromisoformat(v) for v in values}
            valid = (isinstance(values, list) and len(parsed) == len(values)
                     and all(d.isoformat() in values for d in parsed))
        except (KeyError, TypeError, ValueError):
            valid, parsed = False, set()
        evidence.check("receipt_calendar_explicit_unique_dates", valid, node)
        closed[node] = parsed
    receipt_rows = meta.get("supplier_delivery_receipt_policy", {}).get("rows", [])
    suppliers = {(r["node_id"], r["item_id"]): r for r in receipt_rows}
    transfers = {(r["node_id"], r["item_id"]): r
                 for r in meta.get("internal_component_policy", {}).get("rows", [])}
    productions = {(r["node_id"], r["item_id"]): r
                   for key in ("production_release_policy", "finished_goods_release_policy")
                   for r in meta.get(key, {}).get("rows", [])}

    def check_date(g, available, rule, pair, context, kind):
        days = rule.get("receipt_days")
        valid = (type(g) is int and g >= 0 and type(available) is int
                 and type(days) is int and days >= 0)
        evidence.check("receipt_calendar_" + kind + "_integers", valid, context)
        if not valid:
            return
        exclusions = set(closed.get(pair[0], set()))
        try:
            exclusions.update(date.fromisoformat(v) for v in rule.get("nonworking_dates", []))
        except (TypeError, ValueError):
            evidence.check("receipt_calendar_pair_dates_valid", False, context)
            return
        target, remaining = origin + timedelta(days=g), days
        while remaining:
            target += timedelta(days=1)
            if target.weekday() < 5 and target not in exclusions:
                remaining -= 1
        evidence.check("receipt_calendar_" + kind + "_exact_date",
                       available == (target - origin).days,
                       {"id": context, "actual": available, "expected": (target - origin).days})

    for event in events:
        pair = event["node_id"], event["item_id"]
        if event["event_type"] != "production_output" or pair not in productions:
            continue
        text = event.get("notes", "")
        note = json.loads(text) if text.lstrip().startswith("{") else {}
        day = int(event["day"])
        check_date(day, note.get("available_day", day), productions[pair], pair,
                   event["lot_id"], "production")
        if "physical_day" in note:
            evidence.check("receipt_calendar_production_physical_anchor", note["physical_day"] == day,
                           event["lot_id"])
    for order in orders:
        pair = order["node_id"], order["item_id"]
        kind = order["order_type"]
        rule = (suppliers.get(pair) if kind == "external_procurement_supplier_delivery"
                else transfers.get(pair) if kind == "lane_release" else None)
        if rule is None or "receipt_days" not in rule:
            continue
        identity = order.get("mrp_order_id", "")
        try:
            g, available = int(order["physical_delivery_day"]), int(order["available_day"])
        except (KeyError, TypeError, ValueError):
            evidence.check("receipt_calendar_order_dates_present", False, identity)
            continue
        if kind == "external_procurement_supplier_delivery":
            evidence.check("receipt_calendar_order_source_duration",
                           str(order.get("receipt_source_days", "")) == str(rule["receipt_days"]), identity)
        check_date(g, available, rule, pair, identity, "order")


def audit_opening_receipt_fragments(orders, events, horizon, evidence, *, meta, fragments,
                                  execution_summary, item_units):
    """Reconstruct the declared execution in Decimal, without runtime helpers.

    The hashed input book and historical-execution input determine the oracle;
    neither the exported fragments nor their summary determine expected flows.
    This verifies a conditional scenario, not the industrial truth of that input.
    """
    policy = (meta or {}).get("opening_receipt_execution_policy")
    exported = any(r.get("opening_execution_mode") for r in orders)
    if policy is None:
        evidence.check("opening_execution_no_undeclared_replay",
                       not fragments and not execution_summary and not exported)
        return set(), set()
    valid = (isinstance(policy, dict) and type(policy.get("schema_version")) is int
             and policy.get("schema_version") == 1 and policy.get("mode") == "known_weekly_receipts_fifo_v1"
             and policy.get("calendar") == "monday_friday" and isinstance(policy.get("pairs"), list)
             and bool(policy["pairs"]) and isinstance(policy.get("events"), list))
    evidence.check("opening_execution_declared_contract", valid)
    if not valid:
        return set(), set()
    try:
        pairs = [(p["node_id"], p["item_id"]) for p in policy["pairs"]]
        origin = date.fromisoformat(meta["mrp_forecasts"]["origin"])
        valid = all(all(isinstance(s, str) and s.strip() for s in p) for p in pairs)
    except (KeyError, TypeError, ValueError):
        valid = False
    evidence.check("opening_execution_origin_and_pairs", valid)
    if not valid:
        return set(), set()
    evidence.check("opening_execution_unique_pairs", len(pairs) == len(set(pairs)))
    pairs = set(pairs)
    evidence.check("opening_execution_summary_present", isinstance(execution_summary, dict))
    summary = execution_summary if isinstance(execution_summary, dict) else {}
    evidence.check("opening_execution_summary_contract", summary.get("mode") == policy["mode"]
                   and summary.get("pairs") == policy["pairs"])

    def integer(raw):
        if isinstance(raw, bool):
            raise ValueError("Boolean date")
        value = Decimal(str(raw))
        if not value.is_finite() or value < 0 or value != int(value):
            raise ValueError("Expected nonnegative integral date")
        return int(value)

    def positive(raw, unit):
        if isinstance(raw, bool):
            raise ValueError("Boolean quantity")
        value = Decimal(str(raw))
        if not value.is_finite() or value <= 0 or (unit == "UN" and value != int(value)):
            raise ValueError("Expected positive physical quantity")
        return value

    def release_day(physical, days):
        current = origin + timedelta(days=physical)
        while days:
            current += timedelta(days=1)
            if current.weekday() < 5:
                days -= 1
        return (current - origin).days

    # Independent dimensional conversion; unsupported conversions fail closed.
    scales = {"G": ("mass", Decimal(".001")), "KG": ("mass", Decimal(1)),
              "MG": ("mass", Decimal(".000001")), "T": ("mass", Decimal(1000)),
              "ML": ("volume", Decimal(".001")), "L": ("volume", Decimal(1))}
    original, remaining, queues = {}, {}, defaultdict(list)
    book = meta.get("opening_open_orders", {})
    for raw in book.get("rows", []):
        pair = raw.get("dst_node_id"), raw.get("item_id")
        if raw.get("order_type") != "purchase_open_order" or pair not in pairs:
            continue
        try:
            source_file = raw.get("source_file") or book["source_file"]
            source_row = str(raw["source_row"])
            unit = str((item_units or {}).get(pair[1], raw["uom"])).upper()
            source_unit = str(raw["uom"]).upper()
            qty = positive(raw["quantity"], source_unit)
            if source_unit != unit:
                if scales[source_unit][0] != scales[unit][0]:
                    raise ValueError("Incompatible source quantity")
                qty *= scales[source_unit][1] / scales[unit][1]
            qty = positive(qty, unit)
            g, available, days = (integer(raw[k]) for k in ("physical_delivery_day", "usable_day", "receipt_release_days"))
            valid = (isinstance(source_file, str) and bool(source_file.strip()) and bool(source_row.strip())
                     and not isinstance(raw["source_row"], bool) and available >= g)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        evidence.check("opening_execution_original_source_contract", valid, raw)
        if not valid:
            continue
        identity = "OPENING_DATED_PURCHASE|" + json.dumps([source_file, source_row], ensure_ascii=False, separators=(",", ":"))
        evidence.check("opening_execution_unique_original_source", identity not in original, identity)
        if identity in original:
            continue
        original[identity] = dict(pair=pair, qty=qty, unit=unit, g=g, available=available, days=days,
                                  source_file=source_file, source_row=source_row, supplier=raw.get("src_node_id"))
        remaining[identity] = qty
        queues[pair].append(identity)
    evidence.check("opening_execution_all_pairs_have_source_orders", set(queues) == pairs)
    for pair in queues:
        queues[pair].sort(key=lambda identity: (original[identity]["g"], original[identity]["available"],
                         original[identity]["source_file"], original[identity]["source_row"]))

    source_receipts, known_sources = [], set()
    for raw in policy["events"]:
        try:
            pair = raw["node_id"], raw["item_id"]
            known = integer(raw["known_day"])
            source_row = integer(raw["source_row"])
            source_key = raw["source_file"], source_row, raw["source_cell"]
            unit = raw["uom"]
            qty = positive(raw["quantity"], unit)
            valid = (pair in queues and source_row > 0 and unit == original[queues[pair][0]]["unit"]
                     and all(isinstance(s, str) and s.strip() for s in (source_key[0], source_key[2])))
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        evidence.check("opening_execution_receipt_input_contract", valid, raw)
        if not valid:
            continue
        evidence.check("opening_execution_unique_receipt_source_cell", source_key not in known_sources, source_key)
        known_sources.add(source_key)
        if known < horizon:
            source_receipts.append((known, pair, source_key, qty))
    expected = {}
    for known, pair, source_key, qty in sorted(source_receipts, key=lambda row: row[0]):
        unassigned = qty
        for identity in queues[pair]:
            assigned = min(remaining[identity], unassigned)
            if assigned <= 0:
                continue
            expected[identity, source_key] = dict(quantity=assigned, physical=known,
                available=release_day(known, original[identity]["days"]))
            remaining[identity] -= assigned
            unassigned -= assigned
            if not unassigned:
                break
        evidence.check("opening_execution_source_within_original_book", unassigned == 0, source_key)

    by_origin = defaultdict(list)
    for event in events:
        by_origin[event.get("source_id", "")].append(event)
    markers, exported_keys, lots = set(), set(), set()
    actual_received = defaultdict(Decimal)
    for row in fragments:
        marker, identity = row.get("marker", ""), row.get("original_marker", "")
        try:
            source_key = row["receipt_source_file"], integer(row["receipt_source_row"]), row["receipt_source_cell"]
            key = identity, source_key
            source = original[identity]
            wanted = expected[key]
            qty = positive(row["quantity"], source["unit"])
            physical, available, known, days = (integer(row[k]) for k in (
                "physical_delivery_day", "arrival_day", "receipt_known_day", "receipt_release_days"))
            encoded = json.loads(marker.removeprefix("OPENING_EXECUTED_FRAGMENT|"))
            valid = (marker.startswith("OPENING_EXECUTED_FRAGMENT|") and len(encoded) == 2
                     and encoded[0] == identity and json.loads(encoded[1]) == list(source_key))
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        evidence.check("opening_execution_fragment_declared_identity", valid, row)
        if not valid:
            continue
        evidence.check("opening_execution_unique_fragment", marker not in markers and key not in exported_keys, marker)
        markers.add(marker)
        exported_keys.add(key)
        actual_received[identity] += qty
        evidence.close("opening_execution_fragment_fifo_quantity", float(qty), float(wanted["quantity"]), marker)
        evidence.check("opening_execution_fragment_dates", physical == known == wanted["physical"]
                       and available == wanted["available"] and days == source["days"] and physical < horizon, marker)
        evidence.check("opening_execution_fragment_source_preserved",
            (row.get("node_id"), row.get("item_id")) == source["pair"] and row.get("uom") == source["unit"]
            and row.get("original_source_file") == source["source_file"]
            and str(row.get("original_source_row", "")) == source["source_row"]
            and str(row.get("original_promised_physical_day", "")) == str(source["g"])
            and str(row.get("original_promised_available_day", "")) == str(source["available"]), marker)
        evidence.check("opening_execution_fragment_hypothesis_explicit",
            row.get("allocation_basis") == "fifo_technical_not_observed_order_identity"
            and row.get("availability_basis") == "original_receipt_workdays_after_known_physical_receipt", marker)
        matching = by_origin[marker]
        stages = (("physical", "opening_purchase_order_receipt", wanted["physical"]),
                  ("hold", "stock_availability_hold", wanted["physical"]),
                  ("availability", "stock_availability_release", wanted["available"]))
        stage_lots = set()
        for stage, kind, due in stages:
            group = [event for event in matching if event["event_type"] == kind]
            evidence.check("opening_execution_single_" + stage, len(group) == int(due < horizon), marker)
            for event in group:
                lot = event.get("lot_id", "")
                stage_lots.add(lot)
                evidence.check("opening_execution_" + stage + "_date_pair_unit",
                    str(event["day"]) == str(due) and bool(lot.strip())
                    and (event["node_id"], event["item_id"]) == source["pair"]
                    and event.get("uom") == source["unit"], marker)
                evidence.close("opening_execution_" + stage + "_quantity",
                               number(event, "qty"), float(wanted["quantity"]), marker)
                if stage == "physical":
                    evidence.check("opening_execution_creation_original_genealogy",
                        event.get("planned_order_id") == identity and event.get("baseline_reference_id") == identity
                        and str(event.get("source_row", "")) == source["source_row"]
                        and event.get("supplier_id") == source["supplier"], marker)
        evidence.check("opening_execution_same_unique_lot", len(stage_lots) == 1 and not (stage_lots & lots), marker)
        lots.update(stage_lots)
    evidence.check("opening_execution_complete_fragment_export", exported_keys == set(expected),
                   {"missing": len(set(expected) - exported_keys), "unexpected": len(exported_keys - set(expected))})
    evidence.check("opening_execution_no_orphan_fragment_events", all(
        event.get("source_id") in markers for event in events
        if str(event.get("source_id", "")).startswith("OPENING_EXECUTED_FRAGMENT|")))
    evidence.check("opening_execution_no_undeclared_order_mode", all(
        row.get("mrp_order_id") in original for row in orders if row.get("opening_execution_mode")))
    selected = [r for r in orders if r.get("order_type") == "opening_purchase_order"
                and (r.get("node_id"), r.get("item_id")) in pairs]
    evidence.check("opening_execution_original_identities_preserved",
                   len(selected) == len(original) and {r.get("mrp_order_id") for r in selected} == set(original))
    for row in selected:
        identity = row.get("mrp_order_id")
        if identity not in original:
            continue
        source = original[identity]
        received = source["qty"] - remaining[identity]
        available = sum((r["quantity"] for (parent, _), r in expected.items()
                         if parent == identity and r["available"] < horizon), Decimal(0))
        amounts = dict(received=received, available=available, pending=remaining[identity], held=received-available)
        evidence.close("opening_execution_fragments_plus_pending_equal_original",
            float(actual_received[identity] + remaining[identity]), float(source["qty"]), identity)
        evidence.check("opening_execution_no_overreceipt", actual_received[identity] <= source["qty"], identity)
        evidence.check("opening_execution_no_duplicate_original_receipt", not any(event["event_type"] in {
            "opening_purchase_order_receipt", "stock_availability_hold", "stock_availability_release"}
            for event in by_origin[identity]), identity)
        evidence.close("opening_execution_original_planned_quantity", number(row, "planned_receipt_qty"), float(source["qty"]), identity)
        evidence.close("opening_execution_original_release_quantity", number(row, "release_qty"), float(source["qty"]), identity)
        evidence.check("opening_execution_original_promises_preserved", all(
            str(row.get(field, "")) == str(value) for field, value in (
                ("physical_delivery_day", source["g"]), ("available_day", source["available"]),
                ("arrival_day", source["available"]), ("source_file", source["source_file"]),
                ("source_row", source["source_row"]), ("baseline_reference_id", identity))), identity)
        evidence.check("opening_execution_order_mode", row.get("opening_execution_mode") == policy["mode"], identity)
        for field, value in amounts.items():
            evidence.close("opening_execution_order_" + field, number(row, "opening_execution_" + field + "_qty"), float(value), identity)
        completed_physical = received == source["qty"]
        completed_available = available == source["qty"]
        own = [r for (parent, _), r in expected.items() if parent == identity]
        g = str(max(r["physical"] for r in own)) if completed_physical else ""
        available_day = str(max(r["available"] for r in own)) if completed_available else ""
        for field, wanted in (("actual_physical_receipt_day", g), ("actual_available_day", available_day),
                              ("actual_receipt_day", available_day)):
            evidence.check("opening_execution_" + field, str(row.get(field, "")) == wanted, identity)
        state = ("available" if completed_available else "held_pending_availability" if completed_physical else
                 "partially_received_opening_commitment" if received else "awaiting_physical_delivery")
        evidence.check("opening_execution_final_status", row.get("order_status_end_of_run") == state, identity)
    evidence.check("opening_execution_summary_counts", summary.get("original_order_count") == len(original)
                   and summary.get("known_receipt_fragment_count") == len(expected))
    pending = summary.get("pending_by_marker", {})
    evidence.check("opening_execution_pending_identities", isinstance(pending, dict) and set(pending) == set(original))
    if isinstance(pending, dict):
        for identity, qty in remaining.items():
            evidence.close("opening_execution_summary_pending", float(pending.get(identity, float("nan"))), float(qty), identity)
    return set(original), markers


def audit_opening_purchase_availability(orders, events, horizon, evidence, *, meta=None,
                                       fragments=(), execution_summary=None, item_units=None):
    """Reconcile source-book G/I against one physical lot, without engine helpers."""
    orders = list(orders)
    managed, fragment_markers = audit_opening_receipt_fragments(orders, events, horizon, evidence,
        meta=meta, fragments=fragments, execution_summary=execution_summary, item_units=item_units)
    by_origin = defaultdict(list)
    for event in events:
        by_origin[event.get("source_id", "")].append(event)
    seen = set()
    count = 0
    for order in orders:
        if order["order_type"] != "opening_purchase_order":
            continue
        count += 1
        identity = order["mrp_order_id"]
        evidence.check("opening_purchase_unique_identity", bool(identity) and identity not in seen, identity)
        seen.add(identity)
        provenance = [str(order.get("source_file", "")), str(order.get("source_row", ""))]
        evidence.check("opening_purchase_source_provenance", all(part.strip() for part in provenance)
                       and identity == "OPENING_DATED_PURCHASE|" + json.dumps(provenance, ensure_ascii=False, separators=(",", ":")), identity)
        physical_day, available_day = int(order["physical_delivery_day"]), int(order["available_day"])
        quantity = number(order, "planned_receipt_qty")
        evidence.check("opening_purchase_positive_quantity", quantity > 0, identity)
        evidence.check("opening_purchase_valid_dates", 0 <= physical_day <= available_day, identity)
        evidence.check("opening_purchase_legacy_arrival_is_availability", int(order["arrival_day"]) == available_day, identity)
        if identity in managed:
            continue
        relevant = by_origin[identity]
        created = [row for row in relevant if row["event_type"] == "opening_purchase_order_receipt"]
        holds = [row for row in relevant if row["event_type"] == "stock_availability_hold"]
        releases = [row for row in relevant if row["event_type"] == "stock_availability_release"]
        for kind, group, due in (("physical", created, physical_day), ("hold", holds, physical_day),
                                 ("availability", releases, available_day)):
            evidence.check("opening_purchase_single_" + kind, len(group) == int(due < horizon), identity)
            for row in group:
                evidence.check("opening_purchase_nonempty_lot_identity", bool(row["lot_id"].strip()), identity)
                evidence.check("opening_purchase_" + kind + "_date", int(row["day"]) == due, identity)
                evidence.close("opening_purchase_" + kind + "_quantity", number(row, "qty"), quantity, identity)
                evidence.check("opening_purchase_" + kind + "_pair",
                               (row["node_id"], row["item_id"]) == (order["node_id"], order["item_id"]), identity)
        evidence.check("opening_purchase_same_lot_G_I", len({row["lot_id"] for row in created + holds + releases}) == int(physical_day < horizon), identity)
        for field, due in (("actual_physical_receipt_day", physical_day), ("actual_available_day", available_day)):
            expected = str(due) if due < horizon else ""
            evidence.check("opening_purchase_" + field, order[field] == expected, identity)
    orphaned = [row["event_id"] for row in events
                if row["event_type"] == "opening_purchase_order_receipt" and row.get("source_id") not in seen | fragment_markers]
    evidence.check("opening_purchase_no_unmatched_creation", not orphaned, orphaned[:5])
    return count


def audit_internal_transfer_availability(orders, events, genealogy, horizon, pairs, evidence):
    """One transported child lot at G, held until I; no production helper."""
    by_order, by_state, shipments, links = (defaultdict(list) for _ in range(4))
    for event in events:
        if event.get("event_type") == "lane_receipt":
            by_order[event.get("planned_order_id", "")].append(event)
        if event.get("source_type") == "internal_transfer_availability":
            by_state[event.get("source_id", "")].append(event)
        if event.get("event_type") == "lane_ship":
            shipments[event.get("shipment_id", "")].append(event)
    for link in genealogy:
        if link.get("link_type") == "transport":
            links[link["child_lot_id"]].append(link)
    seen = set()
    for order in orders:
        pair = order.get("node_id"), order.get("item_id")
        if order.get("order_type") != "lane_release" or pair not in pairs:
            continue
        identity = order.get("mrp_order_id", "")
        evidence.check("internal_transfer_unique_order", bool(identity) and identity not in seen, identity)
        seen.add(identity)
        fields = ("physical_delivery_day", "available_day", "source_file", "source_row")
        complete = all(str(order.get(field, "")).strip() for field in fields)
        evidence.check("internal_transfer_dates_and_provenance_present", complete, identity)
        if not complete:
            continue
        g, available = int(order["physical_delivery_day"]), int(order["available_day"])
        qty = number(order, "planned_receipt_qty")
        evidence.check("internal_transfer_valid_dates_and_quantity", 0 <= g <= available and qty > 0, identity)
        evidence.check("internal_transfer_arrival_means_availability", int(order["arrival_day"]) == available, identity)
        evidence.check("internal_transfer_policy_provenance", order["source_file"] == "graph.meta.internal_component_policy", identity)
        created = by_order[identity]
        held = [e for e in by_state[identity] if e["event_type"] == "stock_availability_hold"]
        released = [e for e in by_state[identity] if e["event_type"] == "stock_availability_release"]
        for kind, group, due in (("physical", created, g), ("hold", held, g), ("availability", released, available)):
            evidence.check("internal_transfer_single_" + kind, len(group) == int(due < horizon), identity)
            for row in group:
                evidence.check("internal_transfer_" + kind + "_date", int(row["day"]) == due, identity)
                evidence.check("internal_transfer_" + kind + "_pair", (row["node_id"], row["item_id"]) == pair, identity)
                evidence.check("internal_transfer_nonempty_lot", bool(row.get("lot_id", "").strip()), identity)
                evidence.close("internal_transfer_" + kind + "_quantity", number(row, "qty"), qty, identity)
        evidence.check("internal_transfer_same_lot_G_I", len({e["lot_id"] for e in created + held + released}) == int(g < horizon), identity)
        for field, due in (("actual_physical_receipt_day", g), ("actual_available_day", available)):
            evidence.check("internal_transfer_" + field, str(order.get(field, "")) == (str(due) if due < horizon else ""), identity)
        for child in created:
            shipment = child.get("shipment_id", "")
            shipped = shipments[shipment]
            evidence.check("internal_transfer_shipment_identity", bool(shipment) and bool(shipped), identity)
            ancestry = links[child["lot_id"]]
            parents = {r["lot_id"] for r in shipped}
            evidence.check("internal_transfer_transported_parents", bool(ancestry)
                           and all(r["parent_lot_id"] in parents and r.get("shipment_id", "") == shipment for r in ancestry), identity)
            # child_qty is the full child lot repeated on each parental edge,
            # not an additive contribution. Shares are exported at9decimals.
            parents_qty = math.fsum(number(r, "parent_qty") for r in ancestry)
            evidence.close("internal_transfer_genealogy_parent_quantity", parents_qty, qty, identity)
            for link in ancestry:
                evidence.close("internal_transfer_genealogy_child_quantity", number(link, "child_qty"), qty, identity)
                evidence.close("internal_transfer_genealogy_parent_share", number(link, "allocation_share"),
                               number(link, "parent_qty") / parents_qty if parents_qty else 0.0,
                               identity, tolerance=0.5e-9 + 1e-15)
            share_tolerance = len(ancestry) * 0.5e-9 + 1e-15
            evidence.close("internal_transfer_genealogy_share_sum",
                           math.fsum(number(r, "allocation_share") for r in ancestry), 1.0,
                           identity, tolerance=share_tolerance)
            evidence.close("internal_transfer_genealogy_weighted_child_quantity",
                           math.fsum(number(r, "child_qty") * number(r, "allocation_share") for r in ancestry),
                           qty, identity, tolerance=qty * share_tolerance + len(ancestry) * 0.5e-6)
    evidence.check("internal_transfer_no_orphan_availability", set(by_state) <= seen, sorted(set(by_state) - seen)[:5])
    return len(seen)


def declared_scan3_requirements(contract, budgets, events, horizon, scenario, evidence):
    """Rebuild declared historical residuals without reading their runtime export.

    Own withdrawals come from executed BOM lot events. Earlier residuals are
    credited when requested, including amounts still waiting for stock.
    """
    valid = (isinstance(contract, dict)
             and set(contract) == {"schema_version", "mode", "cumulative_pairs"}
             and type(contract.get("schema_version")) is int and contract["schema_version"] == 1
             and contract.get("mode") == "scan3_residual_v1"
             and isinstance(contract.get("cumulative_pairs"), list)
             and isinstance(budgets, list) and bool(budgets))
    evidence.check("scan3_declared_contract", valid)
    if not valid:
        return {}
    cumulative = contract["cumulative_pairs"]
    valid = all(isinstance(p, list) and len(p) == 2
                and all(isinstance(s, str) and s for s in p) for p in cumulative)
    evidence.check("scan3_cumulative_pair_contract", valid)
    if not valid:
        return {}
    cumulative = [tuple(p) for p in cumulative]
    evidence.check("scan3_cumulative_pairs_unique", len(set(cumulative)) == len(cumulative))
    seen, intervals, pairs, normalized = set(), defaultdict(list), set(), []
    for source in budgets:
        try:
            pair = source["node_id"], source["item_id"]
            first, end, closing = (source[k] for k in ("first_day", "end_day_exclusive", "closing_day"))
            qty = Decimal(str(source["covered_scan3_qty"]))
            full = Decimal(str(source["full_week_scan3_qty"]))
            signed = Decimal(str(source["raw_signed_scan3_qty"]))
            valid = (all(isinstance(s, str) and s for s in pair)
                     and all(type(d) is int for d in (first, end, closing))
                     and 0 <= first < end <= horizon and end - first <= 7 and closing == end - 1
                     and (closing - 4) % 7 == 0 and source["covered_days"] == end - first
                     and source["uom"] in {"G", "KG", "UN"}
                     and type(source.get("source_row")) is int and source["source_row"] > 0
                     and all(v.is_finite() for v in (qty, full, signed))
                     and qty >= 0 and full >= 0 and signed == -full
                     and all(isinstance(source.get(k), str) and source[k].strip()
                             for k in ("source_file", "scan3_source_cell", "source_week_marker", "budget_id")))
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        evidence.check("scan3_budget_contract", valid, source)
        if not valid:
            continue
        identity = source["budget_id"]
        evidence.check("scan3_budget_identity", identity == f"{pair[0]}:{pair[1]}:R{source.get('source_row')}", identity)
        evidence.check("scan3_budget_unique", identity not in seen, identity)
        evidence.check("scan3_budget_disjoint", all(end <= a or first >= b for a, b in intervals[pair]), identity)
        partial = end - first != 7
        evidence.check("scan3_partial_week_convention",
            source.get("partial_week") is partial
            and source.get("include_in_main_source_balance") is (not partial)
            and (not partial or (first == 0 and end == 5)), identity)
        evidence.check("scan3_source_cell_and_coverage",
            source["scan3_source_cell"].split("!")[-1] == f"J{source['source_row']}"
            and source.get("coverage_status") == ("documented_zero" if full == 0 else "documented_withdrawals"), identity)
        # R5 retains the full source quantity at the initial partial closing.
        # It is explicitly excluded from complete-week calibration balances.
        # Audit that frozen convention; do not introduce a new prorating rule.
        if source["uom"] == "UN":
            evidence.check("scan3_source_integer_UN", full == int(full) and qty == int(qty), identity)
        evidence.close("scan3_covered_source_quantity", float(qty), float(full), identity)
        seen.add(identity)
        intervals[pair].append((first, end))
        pairs.add(pair)
        normalized.append(source)
    evidence.check("scan3_cumulative_pairs_have_budgets", set(cumulative) <= pairs)
    own = defaultdict(Decimal)
    units = { (s["node_id"], s["item_id"]): s["uom"] for s in normalized }
    evidence.check("scan3_pair_unit_consistent", all(s["uom"] == units[s["node_id"], s["item_id"]]
                                                    for s in normalized))
    for event in events:
        if event["event_type"] == "production_consume" and (event["node_id"], event["item_id"]) in pairs:
            key = int(event["day"]), event["node_id"], event["item_id"]
            amount = Decimal(str(event["qty"]))
            valid = amount.is_finite() and amount >= 0
            evidence.check("scan3_own_quantity", valid, key)
            evidence.check("scan3_own_unit", event.get("uom") == units[key[1:]], key)
            if valid:
                own[key] += amount
    totals, result = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)]), {}
    for source in sorted(normalized, key=lambda s: (s["closing_day"], s["budget_id"])):
        pair = source["node_id"], source["item_id"]
        day = source["closing_day"]
        quantity = Decimal(str(source["covered_scan3_qty"]))
        used = sum((own[d, *pair] for d in range(source["first_day"], source["end_day_exclusive"])), Decimal(0))
        excess = max(Decimal(0), used - quantity)
        if pair in cumulative:
            total = totals[pair]
            total[0] += quantity
            total[1] += used
            previous = total[2]
            requested = max(Decimal(0), total[0] - total[1] - previous)
            total[2] += requested
            basis = dict(method="cumulative_documented_scan3_minus_own_and_prior_requested",
                node_id=pair[0], item_id=pair[1], closing_day=day, source_cells=source["scan3_source_cell"],
                covered_source_cumulative_qty=float(total[0]), covered_own_cumulative_qty=float(total[1]),
                prior_requested_including_backlog_qty=float(previous), new_residual_qty=float(requested),
                total_requested_qty=float(total[2]),
                cumulative_unreversed_excess_qty=float(max(Decimal(0), total[1] + total[2] - total[0])),
                timing="Sunday closing, not measured production date", planning_use="no future observation supplied to planner")
        else:
            requested = max(Decimal(0), quantity - used)
            basis = dict(method="weekly_scan3_minus_actual_own_BOM_residual", budget_id=source["budget_id"],
                source_week_marker=source["source_week_marker"], first_day=source["first_day"],
                end_day_exclusive=source["end_day_exclusive"], J_covered_qty=float(quantity),
                own_BOM_qty=float(used), residual_qty=float(requested), own_excess_qty=float(excess),
                I_preserved_separately=True, actual_alternate_SKU_scope="not_identified",
                timing="Sunday closing accounting convention, not a measured production date",
                planning_use="not available before closing day")
        if source["uom"] == "UN":
            evidence.check("scan3_residual_integer_UN", used == int(used) and requested == int(requested), source["budget_id"])
        if requested <= 0:
            continue
        identity = f"external:{scenario}:zz-reconciled-F3:{source['budget_id']}:D{day}"
        result[identity] = dict(pair=pair, day=day, known=day, qty=float(requested), cycle=0,
            source=dict(demand_id=source["budget_id"], source_file=source["source_file"],
                        source_cells=source["scan3_source_cell"], uom=source["uom"]),
            physical_source="reconstructed_scan3_residual_not_identified_other_format", reconciliation_basis=basis)
    return result


def declared_prospective_other_uses(meta, policy, horizon, evidence, source_bytes):
    """Verify the frozen exogenous profile from original CSV bytes, not engine helpers.

    The caller supplies metadata only from the SHA-256-verified input graph.
    The opening fragment is expanded only for future seasons. Requested use,
    not served use or backlog, is the fixed scenario quantity.
    """
    before = sum(row["failed"] for row in evidence.checks.values())
    expected_contract = dict(
        mode="retained_W_historical_then_synthetic_v1", first_synthetic_day=362,
        historical_days=362, season_days=364, annual_growth=0.05,
        planning_horizon_days=364,
        physical_other_uses="fixed_W_requested_weekly_profile_not_future_BOM_residual",
        first_partial_week="five_observed_days_scaled_to_seven_for_future_only",
        customer_orders="historical_weekly_orders_times_1.05_per_52_week_cycle",
        forecast="known_source_first_then_same_week_known_forecast_times_growth",
        closures="Avene_first_two_full_August_workweeks_assumed_after_2025",
        initial_orders="opening_once_never_repeated",
        industrial_status="scenario_assumptions_not_observations",
        schema_version=1, scenario_id="scn:BASE", days=horizon)
    declaration = meta.get("current_reference_projection")
    # Two exact contracts, independently enumerated here. A source-priority
    # contract mixed with candidate fields is rejected, never silently accepted.
    coherent = isinstance(declaration, dict) and declaration.get("forecast_mode") == "coherent_scenario"
    if coherent:
        expected_contract.update(
            forecast_mode="coherent_scenario", forecast="coherent_scenario_after_2025",
            known_day=365, first_target_day=369,
            customer_forecast="same_synthetic_customer_week_as_executed_orders",
            other_use_forecast="same_fixed_W_requested_profile_as_executed_other_uses",
            industrial_total="source_I_not_substituted_for_BOM_plus_other_uses_after_cutover",
            status="explicit_candidate_not_industrial_observation")
    valid = (isinstance(declaration, dict) and declaration == expected_contract
             and type(horizon) is int and 362 < horizon <= 1825
             and all(type(declaration.get(k)) is type(v) for k, v in expected_contract.items())
             and policy.get("scenario_id") == "scn:BASE")
    evidence.check("prospective_projection_contract", valid)
    if not valid:
        return None
    profile = meta.get("current_reference_other_use_profile")
    fields = {"schema_version", "quantity", "source_file", "source_sha256", "first_partial_week", "rows"}
    valid = (isinstance(profile, dict) and set(profile) == fields
             and type(profile.get("schema_version")) is int and profile["schema_version"] == 1
             and profile.get("quantity") == "W_requested_weekly_not_served"
             and profile.get("first_partial_week") == "Only future copy of W day0..4 normalized by7/5"
             and isinstance(profile.get("rows"), list)
             and isinstance(profile.get("source_file"), str) and bool(profile["source_file"].strip())
             and isinstance(profile.get("source_sha256"), str) and len(profile["source_sha256"]) == 64)
    evidence.check("prospective_profile_contract", valid)
    if not valid:
        return None
    matched = isinstance(source_bytes, bytes) and hashlib.sha256(source_bytes).hexdigest() == profile["source_sha256"]
    evidence.check("prospective_profile_original_csv_sha256", matched)
    if not matched:
        return None
    units = {}
    declarations = (list(policy.get("rows", [])) + list(policy.get("versioned_series", []))
                    + list(meta.get("observed_external_component_demands", {}).get("rows", []))
                    + list(meta.get("formats_reconciled_weekly_budgets", [])))
    for row in declarations:
        pair = row["node_id"], row["item_id"]
        evidence.check("prospective_declared_unit_consistency",
                       row["uom"] in {"UN", "KG", "G", "M"} and units.get(pair, row["uom"]) == row["uom"], pair)
        units[pair] = row["uom"]
    evidence.check("prospective_declared_27_pairs", len(units) == 27)
    seen, weekly = set(), defaultdict(Decimal)
    try:
        csv_bytes = gzip.decompress(source_bytes) if profile["source_file"].lower().endswith(".gz") else source_bytes
        raw_rows = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"), newline=""))
        for row in raw_rows:
            day = int(row["day"])
            pair = row["node_id"], row["item_id"]
            key = day, *pair
            qty = Decimal(row["demand_qty"])
            valid = (0 <= day < 362 and key not in seen and pair in units
                     and row["uom"] == units[pair] and qty.is_finite() and qty >= 0
                     and (row["uom"] != "UN" or qty == int(qty)))
            evidence.check("prospective_profile_original_daily_row", valid, key)
            if not valid:
                continue
            seen.add(key)
            weekly[pair, day - (day + 2) % 7] += qty
    except (OSError, UnicodeError, KeyError, ValueError, ArithmeticError) as exc:
        evidence.check("prospective_profile_original_csv_parse", False, str(exc))
        return None
    wanted_days = {(day, *pair) for pair in units for day in range(362)}
    evidence.check("prospective_profile_original_complete_362_days", seen == wanted_days)
    # W begins on Wednesday. Only the first future Monday week is normalized.
    for pair in units:
        weekly[pair, -2] = weekly[pair, -2] * 7 / 5
    declared = {}
    row_fields = {"node_id", "item_id", "uom", "period_start_day", "qty"}
    for row in profile["rows"]:
        try:
            pair = row["node_id"], row["item_id"]
            start = row["period_start_day"]
            key = pair, start
            qty = Decimal(row["qty"])
            valid = (set(row) == row_fields and pair in units and row["uom"] == units[pair]
                     and type(start) is int and start in range(-2, 356, 7)
                     and isinstance(row["qty"], str) and qty.is_finite() and qty >= 0
                     and key not in declared)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        evidence.check("prospective_profile_declared_week", valid, row)
        if valid:
            declared[key] = qty
            evidence.check("prospective_profile_exact_requested_week", qty == weekly.get(key), [pair, start])
    expected_weeks = {(pair, start) for pair in units for start in range(-2, 356, 7)}
    evidence.check("prospective_profile_complete_27_by_52", set(declared) == expected_weeks)
    evidence.check("prospective_scan3_historical_only", all(
        type(row.get("end_day_exclusive")) is int and row["end_day_exclusive"] <= 362
        for row in meta.get("formats_reconciled_weekly_budgets", [])))
    if sum(row["failed"] for row in evidence.checks.values()) != before:
        return None
    result = dict(units=units, weekly=declared, source_file=profile["source_file"])
    if coherent:
        result.update(forecast_mode="coherent_scenario", known_day=365, first_target_day=369)
    return result


def prospective_other_use_requirement(profile, pair, day):
    """Independent 52-week arithmetic: weekly UN floor then daily remainders."""
    cycle = (day + 2) // 364
    local = day - 364 * cycle
    start = local - (local + 2) % 7
    weekly = profile["weekly"][pair, start] * Decimal("1.05") ** cycle
    unit = profile["units"][pair]
    offset = local - start
    quantity = (int(weekly) * (offset + 1) // 7 - int(weekly) * offset // 7
                if unit == "UN" else float(weekly / 7))
    identity = f"external:scn:BASE:synthetic_W:{pair[0]}:{pair[1]}:D{day}"
    source = dict(demand_id=identity, source_file=profile["source_file"], uom=unit,
        source_cells="demand_qty; fixed W requested weekly profile",
        estimation_basis="52-week repeat with 5% growth; independent of future production and shortages")
    return identity, dict(pair=pair, day=day, known=start+6, qty=float(quantity), source=source,
                          cycle=cycle, physical_source="synthetic_fixed_W_other_uses")


def prospective_forecast_day_audit(audit, component, day, profile):
    """Independent source-priority or explicitly published coherent-scenario audit."""
    if profile.get("forecast_mode") == "coherent_scenario" and day >= profile["first_target_day"]:
        # Publication365 precedes the first affected Monday369. These fields
        # label a hypothesis; source observations and physical demands stay intact.
        return dict(audit, forecast_selection_mode="coherent_synthetic_other_uses_52_week_5pct_growth",
                    forecast_coverage_reason="declared_scenario_not_industrial_source",
                    forecast_source_covered=0, forecast_known_day=profile["known_day"],
                    forecast_vintage_id="coherent_scenario_20260101",
                    forecast_latest_known_day=profile["known_day"],
                    forecast_latest_known_vintage_id="coherent_scenario_20260101",
                    forecast_period_start_day=day - (day + 2) % 7,
                    forecast_source_file=profile["source_file"],
                    forecast_source_cells="W requested demand_qty profile")
    if day < 362 or audit["forecast_source_covered"]:
        return audit
    pair = component["node_id"], component["item_id"]
    cycle = (day + 2) // 364
    local = day - cycle * 364
    start = 4 + ((local - 4) // 7) * 7  # MRP periods use Sunday, unlike physical weeks.
    candidates = [v for v in component["versions"] if v["known_day"] <= min(day, 361, start-1)]
    version = max(candidates, key=lambda v: v["known_day"]) if candidates else None
    source = next((r for r in version["rows"] if r["period_start_day"] == start), None) if version and local >= 0 else None
    if source is not None or pair in profile["units"]:
        known = version["known_day"] if source is not None else local - (local+2) % 7 + 6
        return dict(audit, forecast_selection_mode="synthetic_52_week_forecast_5pct_growth",
                    forecast_coverage_reason="synthetic_scenario_not_source_observation",
                    forecast_source_covered=0, forecast_known_day=known)
    return audit


def audit_external_component_service(series, events, core_rows, policy, horizon, evidence, *,
                                     observed_policy=None, reconciliation=None, projection=None):
    """Independent accounting of a declared incremental-use scenario, not its calibration.

    Reconstruct each dated UN demand with integer quotient/remainder arithmetic,
    then reconcile identities, backlog, available stock and the separate lot debits.
    H/K/source inventory and the production calendar implementation are not used.
    """
    expected, demands, policy_pairs = {}, Counter(), set()
    revision_audit = {}
    prospective = None
    if projection is not None:
        prospective = declared_prospective_other_uses(projection["meta"], policy, horizon,
            evidence, projection.get("source_bytes"))
    repeat = policy.get("repeat_period_days")
    evidence.check("external_repeat_convention", repeat in (None, 365), repeat)
    scenario = policy.get("scenario_id")
    for source in policy.get("rows", []):
        pair = source["node_id"], source["item_id"]
        policy_pairs.add(pair)
        start, known, length = [int(source[k]) for k in ("period_start_day", "known_day", "period_days")]
        quantity = Decimal(str(source["qty"]))
        evidence.check("external_declared_period", 0 <= known <= start < 365 and
                       1 <= length <= 7 and start + length <= 365 and quantity >= 0, source["demand_id"])
        cycles = range((horizon - 1) // 365 + 1) if repeat else range(1)
        for cycle in cycles:
            shift = cycle * 365
            for offset in range(length):
                day = start + shift + offset
                if day >= horizon:
                    continue
                if source["uom"] == "UN":
                    evidence.check("external_declared_integer_UN", quantity == int(quantity), source["demand_id"])
                    amount = (int(quantity) * (offset + 1)) // length - (int(quantity) * offset) // length
                else:
                    amount = float(quantity / length)
                if amount <= 0:
                    continue
                identity = f"external:{scenario}:{source['demand_id']}:C{cycle}:D{day}"
                evidence.check("external_unique_declared_identity", identity not in expected, identity)
                expected[identity] = {"pair": pair, "day": day, "known": known + shift,
                    "qty": float(amount), "source": source, "cycle": cycle}
                demands[(day, *pair)] += float(amount)
    # Independently choose the last forecast strictly before each physical
    # week's start. Later revisions replace future forecasts, never past use.
    # This oracle reads declared rows directly and imports no engine calendar.
    revisions = policy.get("versioned_series", [])
    extended_revision_horizon = policy.get("schema_version") == 3
    if revisions:
        evidence.check("external_revision_schema", type(policy.get("schema_version")) is int
                       and policy["schema_version"] in (2, 3))
    for component in revisions:
        pair = component["node_id"], component["item_id"]
        evidence.check("external_revision_pair_not_duplicated", pair not in policy_pairs, pair)
        policy_pairs.add(pair)
        evidence.check("external_revision_conventions", all((
            component.get("repeat_period_days") == 0,
            component.get("period_anchor_day") == 4,
            component.get("period_days") == 7,
            component.get("current_bucket_policy") == "freeze_previous_exclude_current_vintage",
            component.get("missing_future_policy") == "unprovided_not_observed_zero",
        )), pair)
        versions = sorted(component["versions"], key=lambda v: v["known_day"])
        evidence.check("external_revision_unique_versions", len({v["known_day"] for v in versions}) == len(versions)
                       and len({v["vintage_id"] for v in versions}) == len(versions), pair)
        for version in versions:
            known_day = version["known_day"]
            valid_known_day = type(known_day) is int and 0 <= known_day < 365
            evidence.check("external_revision_vintage_known_in2025", valid_known_day, [pair, version["vintage_id"]])
            starts = [r["period_start_day"] for r in version["rows"]]
            evidence.check("external_revision_unique_weeks", len(starts) == len(set(starts)), [pair, version["vintage_id"]])
            for source in version["rows"]:
                start, length = source["period_start_day"], source["period_days"]
                valid_week = valid_known_day and type(start) is int and type(length) is int
                if valid_week:
                    valid_week = known_day < start and (start - 4) % 7 == 0 and (
                        (start <= known_day + 364 and length == 7) if extended_revision_horizon
                        else (start < 365 and length == min(7, 365 - start)))
                evidence.check("external_revision_only_future_source", valid_week, [pair, version["vintage_id"], start])
                source_qty = Decimal(str(source["qty"]))
                evidence.check("external_revision_declared_quantity", source_qty.is_finite() and source_qty >= 0,
                               [pair, version["vintage_id"], start])
        for day in range(horizon):
            start = day - ((day - 4) % 7)
            earlier = [v for v in versions if v["known_day"] < start]
            selected = earlier[-1] if earlier else None
            known = [v for v in versions if v["known_day"] <= day]
            latest = known[-1] if known else None
            matching = ([r for r in selected["rows"] if r["period_start_day"] == start]
                        if selected and (extended_revision_horizon or day < 365) else [])
            source = matching[0] if matching else None
            key = day, *pair
            audit = {
                "forecast_selection_mode": "rolling_vintages_current_week_frozen",
                "forecast_vintage_id": selected["vintage_id"] if selected else "",
                "forecast_known_day": selected["known_day"] if selected else "",
                "forecast_latest_known_vintage_id": latest["vintage_id"] if latest else "",
                "forecast_latest_known_day": latest["known_day"] if latest else "",
                "forecast_period_start_day": start,
                "forecast_source_covered": int(source is not None),
                "forecast_coverage_reason": ("provided_scenario_period" if source is not None else
                    "outside_revision_horizon" if not extended_revision_horizon and day >= 365 else
                    "no_known_vintage_before_period" if selected is None else "missing_period_in_selected_vintage"),
                "forecast_source_file": source["source_file"] if source else "",
                "forecast_source_cells": source["source_cells"] if source else "",
            }
            revision_audit[key] = (prospective_forecast_day_audit(audit, component, day, prospective)
                                   if prospective is not None else audit)
            if source is None:
                continue
            quantity, length = Decimal(str(source["qty"])), source["period_days"]
            evidence.check("external_revision_nonnegative_qty", quantity.is_finite() and quantity >= 0, key)
            offset = day - start
            if component["uom"] == "UN":
                evidence.check("external_declared_integer_UN", quantity == int(quantity), key)
                amount = (int(quantity) * (offset + 1)) // length - (int(quantity) * offset) // length
            else:
                amount = float(quantity / length)
            if amount <= 0:
                continue
            identity = f"external:{scenario}:revision:{pair[0]}:{pair[1]}:W{start}:D{day}"
            evidence.check("external_unique_declared_identity", identity not in expected, identity)
            expected[identity] = {"pair": pair, "day": day, "known": selected["known_day"],
                "qty": float(amount), "source": {**source, "uom": component["uom"]}, "cycle": 0,
                "vintage_id": selected["vintage_id"], "period_start_day": start}
            demands[key] += float(amount)
    # From day362, every estimated physical use is replaced by the frozen W
    # scenario. Real observations below still override it, including zero.
    if prospective is not None:
        expected = {identity: value for identity, value in expected.items() if value["day"] < 362}
        demands = Counter({key: value for key, value in demands.items() if key[0] < 362})
        policy_pairs.update(prospective["units"])
        for day in range(362, horizon):
            for pair in prospective["units"]:
                identity, requirement = prospective_other_use_requirement(prospective, pair, day)
                demands[day, *pair] = requirement["qty"]
                if requirement["qty"] > 0:
                    evidence.check("prospective_unique_external_identity", identity not in expected, identity)
                    expected[identity] = requirement
    # Observations replace only the physical due amount of covered days.
    # Forecast revision provenance above remains independently audited.
    physical_audit = {}
    if observed_policy is not None:
        evidence.check("observed_physical_policy_contract", all((
            observed_policy.get("schema_version") == 1,
            observed_policy.get("physical_use_only") is True,
            observed_policy.get("repeat_period_days") is None,
            observed_policy.get("scenario_id") == scenario,
        )))
        ids_by_day = defaultdict(list)
        for identity, requirement in expected.items():
            ids_by_day[(requirement["day"], *requirement["pair"])].append(identity)
        for source in observed_policy.get("rows", []):
            pair = source["node_id"], source["item_id"]
            day, known = source["period_start_day"], source["known_day"]
            quantity = Decimal(str(source["qty"]))
            key = day, *pair
            valid = (type(day) is int and type(known) is int and day == known
                     and 0 <= day < 365 and source.get("period_days") == 1
                     and quantity.is_finite() and quantity >= 0)
            evidence.check("observed_physical_declared_day_quantity", valid, source.get("demand_id"))
            evidence.check("observed_physical_unique_day", key not in physical_audit, key)
            evidence.check("observed_physical_source_provenance", bool(source.get("source_file"))
                           and bool(source.get("source_cells")), key)
            if source.get("uom") == "UN":
                evidence.check("observed_physical_integer_UN", quantity == int(quantity), key)
            if not valid:
                continue
            policy_pairs.add(pair)
            if day >= horizon:
                continue
            physical_audit[key] = source
            for identity in ids_by_day.get(key, []):
                expected.pop(identity, None)
            demands[key] = float(quantity)
            if quantity > 0:
                identity = f"external:{scenario}:{source['demand_id']}:C0:D{day}"
                evidence.check("observed_physical_unique_identity", identity not in expected, identity)
                expected[identity] = {"pair": pair, "day": day, "known": known,
                    "qty": float(quantity), "source": source, "cycle": 0,
                    "physical_source": "observed_other_uses"}
    evidence.check("external_declared_pairs_present", bool(policy_pairs))
    core = Counter()
    for row in core_rows:
        core[(int(row["day"]), row["node_id"], row["item_id"])] += number(row, "consumed_qty")
    if reconciliation is not None:
        extra = declared_scan3_requirements(reconciliation["contract"], reconciliation["budgets"],
                                            events, horizon, scenario, evidence)
        for identity, requirement in extra.items():
            evidence.check("scan3_unique_external_identity", identity not in expected, identity)
            expected[identity] = requirement
            demands[requirement["day"], *requirement["pair"]] += requirement["qty"]
            policy_pairs.add(requirement["pair"])
    issues, issued_by_identity = Counter(), Counter()
    for row in events:
        if row["event_type"] != "external_component_consume":
            continue
        day, pair = int(row["day"]), (row["node_id"], row["item_id"])
        evidence.check("external_event_within_execution_horizon", 0 <= day < horizon, [pair, day])
        identity, qty = row.get("source_id"), number(row, "qty")
        key = day, *pair
        issues[key] += qty
        issued_by_identity[identity] += qty
        source = expected.get(identity)
        evidence.check("external_event_matches_declared_requirement", source is not None, identity)
        if source is None:
            continue
        evidence.check("external_event_pair_and_unit", pair == source["pair"] and
                       row["uom"] == source["source"]["uom"], identity)
        evidence.check("external_event_known_and_due", day >= max(source["known"], source["day"]), [identity, day])
        evidence.check("external_event_positive", qty > 0, identity)
        evidence.check("external_identity_not_served_twice", issued_by_identity[identity] <= source["qty"] + .00002, identity)
        try:
            note = json.loads(row.get("notes", ""))
        except (ValueError, TypeError):
            note = {}
        evidence.check("external_event_provenance", all((
            note.get("scope") == ("observed_non_modelled_component_use" if
                source.get("physical_source") == "observed_other_uses" else "estimated_non_modelled_component_use"),
            observed_policy is None or note.get("physical_demand_source") ==
                source.get("physical_source", "estimated_other_uses"),
            note.get("due_day") == source["day"], note.get("known_day") == source["known"],
            note.get("cycle_index") == source["cycle"], note.get("scenario_id") == scenario,
            note.get("demand_id") == source["source"]["demand_id"],
            note.get("source_file") == source["source"]["source_file"],
            note.get("source_cells") == source["source"]["source_cells"],
            "reconciliation_basis" in source or note.get("estimation_basis") == source["source"].get("estimation_basis"),
        )), identity)
        if source.get("physical_source") == "synthetic_fixed_W_other_uses":
            evidence.check("prospective_event_exact_provenance_fields", set(note) == {
                "scope", "due_day", "demand_id", "scenario_id", "cycle_index", "known_day",
                "source_file", "source_cells", "physical_demand_source", "estimation_basis"}, identity)
        if "reconciliation_basis" in source:
            try:
                basis = json.loads(note.get("estimation_basis", ""))
            except (ValueError, TypeError):
                basis = None
            expected_basis = source["reconciliation_basis"]
            evidence.check("scan3_event_basis_fields", isinstance(basis, dict) and set(basis) == set(expected_basis), identity)
            for field, value in expected_basis.items():
                actual = basis.get(field) if isinstance(basis, dict) else None
                if type(value) in (int, float) and type(actual) in (int, float):
                    evidence.close("scan3_event_basis_" + field, actual, value, identity)
                else:
                    evidence.check("scan3_event_basis_" + field, actual == value, identity)
        if "vintage_id" in source:
            evidence.check("external_event_frozen_revision_provenance", all((
                note.get("vintage_id") == source["vintage_id"],
                note.get("period_start_day") == source["period_start_day"],
                note.get("forecast_update_mode") == "rolling_vintages_future_replacement_current_week_frozen",
            )), identity)
    previous, last, exported = defaultdict(float), defaultdict(lambda: -1), set()
    for row in series:
        day, pair = int(row["day"]), (row["node_id"], row["item_id"])
        evidence.check("external_daily_within_execution_horizon", 0 <= day < horizon, [pair, day])
        key = day, *pair
        evidence.check("external_unique_daily_pair", key not in exported, key)
        exported.add(key)
        evidence.check("external_contiguous_days", day == last[pair] + 1, key)
        fields = ("demand_qty", "backlog_start_qty", "required_qty", "consumed_qty",
                  "backlog_end_qty", "available_before_qty", "available_after_qty",
                  "core_consumed_qty", "total_component_consumed_qty")
        values = {field: number(row, field) for field in fields}
        if key in revision_audit:
            for field, value in revision_audit[key].items():
                evidence.check("external_revision_daily_" + field, str(row.get(field, "")) == str(value), key)
        if observed_policy is not None:
            observation = physical_audit.get(key)
            expected_fields = {
                "physical_demand_source": "observed_other_uses" if observation else "estimated_other_uses",
                "physical_source_file": observation["source_file"] if observation else "",
                "physical_source_cells": observation["source_cells"] if observation else "",
                "physical_demand_known_day": observation["known_day"] if observation else "",
            }
            if prospective is not None and day >= 362 and observation is None:
                _, requirement = prospective_other_use_requirement(prospective, pair, day)
                synthetic_fields = {
                    "physical_demand_source": "synthetic_fixed_W_other_uses",
                    "physical_source_file": prospective["source_file"],
                    "physical_source_cells": "W demand_qty weekly profile",
                    "physical_demand_known_day": requirement["known"],
                }
                # These fields must replace the expected values before their checks.
                expected_fields.update(synthetic_fields)
            for field, value in expected_fields.items():
                evidence.check("external_daily_" + field, str(row.get(field, "")) == str(value), key)
            if observation:
                evidence.close("external_daily_physical_observation_qty",
                    number(row, "physical_observation_qty"), float(observation["qty"]), key)
            else:
                evidence.check("external_daily_no_undeclared_observation",
                    row.get("physical_observation_qty", "") == "", key)
        if prospective is not None:
            evidence.check("prospective_daily_unit", row.get("uom") == prospective["units"].get(pair), key)
        evidence.check("external_nonnegative", all(v >= -.00002 for v in values.values()), key)
        evidence.close("external_known_daily_demand", values["demand_qty"], demands[key], key)
        evidence.close("external_backlog_continuity", values["backlog_start_qty"], previous[pair], key)
        evidence.close("external_required_balance", values["required_qty"],
                       values["demand_qty"] + values["backlog_start_qty"], key)
        evidence.close("external_backlog_balance", values["backlog_end_qty"],
                       values["required_qty"] - values["consumed_qty"], key)
        evidence.close("external_available_balance", values["available_after_qty"],
                       values["available_before_qty"] - values["consumed_qty"], key)
        evidence.close("external_available_allocation", values["consumed_qty"],
                       min(values["available_before_qty"], values["required_qty"]), key)
        evidence.close("external_lot_debits_match_service", values["consumed_qty"], issues[key], key)
        evidence.close("external_core_consumption_kept_separate", values["core_consumed_qty"], core[key], key)
        evidence.close("external_total_component_consumption", values["total_component_consumed_qty"],
                       core[key] + issues[key], key)
        if row["uom"] == "UN":
            for field, value in values.items():
                integral(evidence, "external_integer_UN_" + field, value, key)
        previous[pair], last[pair] = values["backlog_end_qty"], day
    evidence.check("external_all_declared_pairs_exported", set(last) == policy_pairs,
                   {"declared": sorted(policy_pairs), "exported": sorted(last)})
    for pair, final in last.items():
        evidence.check("external_complete_horizon", final == horizon - 1, [pair, final])
    evidence.check("external_no_orphan_debit", all(key in exported for key in issues),
                   [key for key in issues if key not in exported][:5])
    return len(exported)


def observed_policy_from_graph_bytes(data, expected_sha256, evidence):
    """Check the original graph bytes before accepting declared observations."""
    valid = bool(expected_sha256) and hashlib.sha256(data).hexdigest() == expected_sha256
    evidence.check("observed_original_input_sha256", valid)
    if not valid:
        return None
    graph = json.loads(data)
    policy = graph.get("meta", {}).get("observed_external_component_demands")
    evidence.check("observed_original_input_policy_present", isinstance(policy, dict))
    return policy if isinstance(policy, dict) else None


def audit_run(run):
    e = Evidence()
    summary = json.loads((run / "summaries/first_simulation_summary.json").read_text(encoding="utf-8"))
    kpis = summary["kpis"]
    horizon = int(summary["sim_days"])
    events = list(rows(run, "production_lot_events"))
    # Inspect the hashed input even when the summary omits its calendar export.
    # Otherwise omission of the field under audit would silently disable it.
    calendar_exported = bool(summary.get("policy", {}).get("dated_component_planning", {}).get("receipt_calendar_policy"))
    execution_export = summary.get("policy", {}).get("opening_receipt_execution_policy")
    fragment_path = run / "data/opening_receipt_execution.csv"
    declared_meta = None
    if summary.get("input_file"):
        declared = Path(summary["input_file"])
        if not declared.is_absolute():
            declared = Path(__file__).resolve().parents[2] / declared
        present = declared.is_file()
        if calendar_exported or execution_export or fragment_path.exists():
            e.check("receipt_calendar_original_input_present", present)
        if present:
            raw = declared.read_bytes()
            matches = hashlib.sha256(raw).hexdigest() == summary.get("input_sha256")
            e.check("receipt_calendar_original_input_sha256", matches)
            if matches:
                declared_meta = json.loads(raw).get("meta", {})
                audit_declared_receipt_dates(declared_meta, summary["policy"],
                                             events, rows(run, "mrp_orders_daily"), e)
    elif calendar_exported or execution_export or fragment_path.exists():
        e.check("receipt_calendar_original_input_present", False)
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
                 "opening_production_order", "opening_purchase_order_receipt", "stock_reconciliation", "estimated_source_receipt", "estimated_capacity_receipt"}
    debits = {"production_consume", "production_consume_reference_transition", "external_component_consume", "demand_service", "writeoff", "stock_writeoff", "shipment_reserve", "lane_ship"}
    neutral = {"stock_availability_hold", "stock_availability_release"}
    availability_path = run / "data/production_stock_availability_daily.csv"
    availability_rows = list(rows(run, "production_stock_availability_daily")) if availability_path.exists() else []
    opening_availability = summary.get("policy", {}).get("opening_purchase_availability")
    if summary.get("policy", {}).get("initial_stock_availability_enabled") or opening_availability:
        e.check("enabled_availability_export_present", bool(availability_rows))
    declared_execution = (declared_meta or {}).get("opening_receipt_execution_policy")
    if opening_availability or declared_execution or execution_export or fragment_path.exists():
        if declared_execution:
            e.check("opening_execution_fragment_csv_present", fragment_path.exists())
            e.check("opening_execution_availability_summary_present", isinstance(opening_availability, dict))
        fragments = list(rows(run, "opening_receipt_execution")) if fragment_path.exists() else []
        checked_orders = audit_opening_purchase_availability(rows(run, "mrp_orders_daily"), events, horizon, e,
            meta=declared_meta, fragments=fragments, execution_summary=execution_export, item_units=item_units)
        # Availability contains original bookkeeping rows AND each physical
        # execution fragment. Orders still contain only the original identities.
        expected_rows = checked_orders + (len(fragments) if declared_execution else 0)
        e.check("opening_purchase_exported_order_count", isinstance(opening_availability, dict)
                and expected_rows == opening_availability.get("row_count"),
                {"original_orders": checked_orders, "execution_fragments": len(fragments), "availability_rows": expected_rows})
        for row in rows(run, "mrp_trace_daily"):
            held = number(row, "held_pending_availability_qty")
            undelivered = number(row, "recv_prev_undelivered_qty")
            e.check("opening_purchase_commitments_nonnegative", min(held, undelivered) >= -0.00002, [row["day"], row["node_id"], row["item_id"]])
            e.close("opening_purchase_commitment_partition", number(row, "recv_prev_future_qty"),
                    held + undelivered, [row["day"], row["node_id"], row["item_id"]])
    availability = {}
    for r in availability_rows:
        key = int(r["day"]), r["node_id"], r["item_id"]
        e.check("availability_unique_day_pair", key not in availability, key)
        availability[key] = r
        available, held, reserved, physical, released = [number(r, f) for f in (
            "available_qty", "held_qty", "reserved_qty", "physical_qty", "released_qty")]
        e.check("availability_nonnegative", min(available, held, reserved, physical, released) >= -0.00002, key)
        e.close("availability_physical_partition", physical, available + held + reserved, key)
        if r["uom"] == "UN":
            for value in (available, held, reserved, physical, released):
                integral(e, "availability_physical_integer_UN", value, key)
    reservations = {(r["lot_id"], r["shipment_id"]) for r in events if r["event_type"] == "shipment_reserve"}
    event_ids, state, first = set(), {}, {}
    produced_available = audit_production_availability(events, e)
    consumed = Counter()
    receipt_qty = Counter()
    shipment_qty = Counter()
    stock_by_pair = defaultdict(float)
    snapshots = {}
    types = Counter()
    held_by_lot, held_by_pair = Counter(), Counter()
    held_snapshots, released_by_day = {}, Counter()
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
        e.check("event_type_known", typ in creations | debits | neutral, typ)
        before = state.get(lot, 0.0)
        if typ in creations:
            e.check("lot_single_creation", lot not in first, lot)
            first[lot] = r
            delta = qty
        elif typ in neutral:
            delta = 0.0
            e.check("availability_export_present", bool(availability_rows), r["event_id"])
            if typ == "stock_availability_hold":
                e.check("hold_within_unreserved_lot", qty <= before - held_by_lot[lot] + 0.00002, r["event_id"])
                held_by_lot[lot] += qty
                held_by_pair[pair] += qty
            else:
                e.check("release_within_held_lot", qty <= held_by_lot[lot] + 0.00002, r["event_id"])
                held_by_lot[lot] -= qty
                held_by_pair[pair] -= qty
                released_by_day[(day, *pair)] += qty
            held_snapshots[(day, *pair)] = held_by_pair[pair]
        elif typ == "lane_ship" and (lot, r["shipment_id"]) in reservations:
            delta = 0.0  # Physical departure of a quantity already reserved/debited.
        else:
            delta = -qty
            e.check("debit_excludes_held_stock", qty <= before - held_by_lot[lot] + 0.00002, r["event_id"])
        e.close("lot_movement_balance", after, before + delta, [r["event_id"], lot, typ])
        e.check("lot_identity_stable", lot in first and (first[lot]["node_id"], first[lot]["item_id"], first[lot]["uom"]) == (*pair, r["uom"]), r["event_id"])
        state[lot] = after
        stock_by_pair[pair] += delta
        snapshots[(day, *pair)] = stock_by_pair[pair]
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
            held = number(availability[key], "held_qty") if key in availability else 0.0
            e.close("ledger_vs_" + name, last_stock[pair], number(r, "stock_end_of_day") + held, list(key), tolerance=0.02)
            if item_units.get(r["item_id"]) == "UN":
                integral(e, "physical_stock_integer_UN_" + name, number(r, "stock_end_of_day"), list(key))
            if name == "production_output_products_daily":
                e.close("released_vs_lot_output", produced_available[key], number(r, "released_qty"), list(key))
        e.check("stock_rows_present_" + name, bool(observed_days))
        for pair, days in observed_days.items():
            e.check("stock_horizon_" + name, days == list(range(horizon)), list(pair))

    # Rebuild held stock exclusively from neutral lot events, independently of
    # the simulator's availability scheduler. Reservation is a separate state.
    held_state = defaultdict(float)
    availability_days = defaultdict(list)
    for (day, node, item), r in sorted(availability.items()):
        pair = node, item
        if day == 0:
            prior = [(d, q) for (d, n, i), q in held_snapshots.items()
                     if d < 0 and (n, i) == pair]
            if prior:
                held_state[pair] = max(prior)[1]
        if (day, *pair) in held_snapshots:
            held_state[pair] = held_snapshots[(day, *pair)]
        e.close("held_export_vs_neutral_lot_events", number(r, "held_qty"), held_state[pair], [day, *pair])
        e.close("released_export_vs_neutral_lot_events", number(r, "released_qty"), released_by_day[(day, *pair)], [day, *pair])
        availability_days[pair].append(day)
    for pair, days in availability_days.items():
        e.check("availability_complete_horizon", days == list(range(horizon)), list(pair))

    genealogy = list(rows(run, "production_lot_genealogy"))
    internal_policy_rows = summary.get("policy", {}).get("internal_component_policy", {}).get("rows", [])
    internal_receipt_pairs = {(r["node_id"], r["item_id"]) for r in internal_policy_rows if "receipt_days" in r}
    if internal_receipt_pairs:
        audit_internal_transfer_availability(rows(run, "mrp_orders_daily"), events, genealogy,
                                             horizon, internal_receipt_pairs, e)
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
    campaign_path = run / "data/production_campaigns.csv"
    e.check("campaign_evidence_present", campaign_path.is_file(), str(campaign_path))
    completed_campaigns = set()
    if campaign_path.is_file():
        for campaign in rows(run, "production_campaigns"):
            if (str(campaign["status"]).startswith("completed")
                    and number(campaign, "remaining_qty") <= 0.00002
                    and number(campaign, "wip_qty") <= 0.00002):
                completed_campaigns.add(campaign["campaign_id"])
    audit_production_consumption(production_links, consumed, completed_campaigns, e)

    external_policy = summary.get("policy", {}).get("external_component_demands")
    observed_policy = None
    reconciliation = None
    if summary.get("policy", {}).get("observed_external_component_execution"):
        declared_path = summary.get("input_file")
        e.check("observed_original_input_path_declared", bool(declared_path))
        if declared_path:
            input_path = Path(declared_path)
            if not input_path.is_absolute():
                input_path = Path(__file__).resolve().parents[2] / input_path
            e.check("observed_original_input_present", input_path.is_file(), str(input_path))
            if input_path.is_file():
                input_bytes = input_path.read_bytes()
                observed_policy = observed_policy_from_graph_bytes(input_bytes, summary.get("input_sha256"), e)
                if hashlib.sha256(input_bytes).hexdigest() == summary.get("input_sha256"):
                    meta = json.loads(input_bytes).get("meta", {})
                    if "formats_reconciled_execution" in meta:
                        reconciliation = dict(contract=meta["formats_reconciled_execution"],
                            budgets=meta.get("formats_reconciled_weekly_budgets"))
    projection = None
    if declared_meta is not None and ("current_reference_projection" in declared_meta
                                      or "current_reference_other_use_profile" in declared_meta):
        projection = dict(meta=declared_meta, source_bytes=None)
        profile_declaration = declared_meta.get("current_reference_other_use_profile")
        source_file = profile_declaration.get("source_file") if isinstance(profile_declaration, dict) else None
        root = Path(__file__).resolve().parents[2]
        source_path = (root / source_file).resolve() if isinstance(source_file, str) and source_file else None
        valid_path = (source_path is not None and source_path.is_relative_to(root)
                      and not Path(source_file).is_absolute() and source_path.is_file())
        e.check("prospective_original_profile_path", valid_path, source_file)
        if valid_path:
            projection["source_bytes"] = source_path.read_bytes()
    external_csv = run / "data/external_component_demand_daily.csv"
    if external_policy:
        e.check("external_component_export_present", external_csv.is_file(), str(external_csv))
        if external_csv.is_file():
            audit_external_component_service(rows(run, "external_component_demand_daily"), events,
                rows(run, "production_input_consumption_daily"), external_policy, horizon, e,
                observed_policy=observed_policy, reconciliation=reconciliation, projection=projection)
    else:
        e.check("external_component_absent_without_policy", not external_csv.exists() and
                not any(row["event_type"] == "external_component_consume" for row in events))

    # This report covers additional identities/path constraints. Its errors
    # must not be hidden by the independent arithmetic checks above.
    path_audit = run / "data/lot_path_audit_issues.csv"
    e.check("lot_path_audit_present", path_audit.is_file(), str(path_audit))
    if path_audit.is_file():
        for issue in rows(run, "lot_path_audit_issues"):
            severity = str(issue.get("severity", "")).strip().lower()
            e.check("lot_path_audit_severity_known", severity in {"info", "warning", "error"}, issue)
            e.check("lot_path_audit_without_error", severity != "error", issue)
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
