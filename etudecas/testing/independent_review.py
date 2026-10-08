"""Read-only arithmetic audit of exported runs, independent of simulation code.

This is an explicit set of invariants, not a scientific certification. No engine,
payload builder or production validator is imported. Missing evidence fails the
audit. Run with --run DIR --output FILE. Exit 1 means a failed invariant.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from decimal import Decimal
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


def audit_opening_purchase_availability(orders, events, horizon, evidence):
    """Reconcile source-book G/I against one physical lot, without engine helpers."""
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
                if row["event_type"] == "opening_purchase_order_receipt" and row.get("source_id") not in seen]
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


def audit_external_component_service(series, events, core_rows, policy, horizon, evidence, *, observed_policy=None):
    """Independent accounting of a declared incremental-use scenario, not its calibration.

    Reconstruct each dated UN demand with integer quotient/remainder arithmetic,
    then reconcile identities, backlog, available stock and the separate lot debits.
    H/K/source inventory and the production calendar implementation are not used.
    """
    expected, demands, policy_pairs = {}, Counter(), set()
    revision_audit = {}
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
            revision_audit[key] = audit
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
            note.get("estimation_basis") == source["source"]["estimation_basis"],
        )), identity)
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
            for field, value in expected_fields.items():
                evidence.check("external_daily_" + field, str(row.get(field, "")) == str(value), key)
            if observation:
                evidence.close("external_daily_physical_observation_qty",
                    number(row, "physical_observation_qty"), float(observation["qty"]), key)
            else:
                evidence.check("external_daily_no_undeclared_observation",
                    row.get("physical_observation_qty", "") == "", key)
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
    if opening_availability:
        checked_orders = audit_opening_purchase_availability(rows(run, "mrp_orders_daily"), events, horizon, e)
        e.check("opening_purchase_exported_order_count", checked_orders == opening_availability["row_count"], checked_orders)
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
    if summary.get("policy", {}).get("observed_external_component_execution"):
        declared_path = summary.get("input_file")
        e.check("observed_original_input_path_declared", bool(declared_path))
        if declared_path:
            input_path = Path(declared_path)
            if not input_path.is_absolute():
                input_path = Path(__file__).resolve().parents[2] / input_path
            e.check("observed_original_input_present", input_path.is_file(), str(input_path))
            if input_path.is_file():
                observed_policy = observed_policy_from_graph_bytes(
                    input_path.read_bytes(), summary.get("input_sha256"), e)
    external_csv = run / "data/external_component_demand_daily.csv"
    if external_policy:
        e.check("external_component_export_present", external_csv.is_file(), str(external_csv))
        if external_csv.is_file():
            audit_external_component_service(rows(run, "external_component_demand_daily"), events,
                rows(run, "production_input_consumption_daily"), external_policy, horizon, e,
                observed_policy=observed_policy)
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
