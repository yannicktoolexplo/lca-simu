"""Conditional local MRP identification; no industrial H enters prediction.

Each known vintage is a separate planning experiment, never an annual order
ledger. Physical chain simulation, observed-stock resets and source edits are
outside this module. The default CLI writes one compact benchmark JSON.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import statistics

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, _conserved_weekly_forecast_parts,
    plan_anticipated_requirements,
)
from etudecas.simulation.engine.run_first_simulation import dated_supply_release_calendar


ROOT = Path(__file__).resolve().parents[3]
FOLDER = ROOT / "etudecas/artifacts/testing/mrp_local_20261007"
ORIGIN = date(2025, 1, 1)
HORIZON = 364
CURRENT_MODES = ("entirely_remaining", "excluded")
FLOOR_MODES = ("additive", "maximum")
# Explicit experiment catalogue, not article-specific planner branches.
CATALOGUE = {
    ("049371", "1810"): {"operation": "external_purchase", "standard_binding": True,
        "review_weekday": None, "lot_basis": "C8R experimental standard treated as minimum and multiple, not attested industrial constraint"},
    ("338929", "1810"): {"operation": "external_purchase", "standard_binding": False,
        "review_weekday": 6, "lot_basis": "C8R packaging standard nonbinding experiment"},
    ("333362", "1430"): {"operation": "external_purchase", "standard_binding": False,
        "review_weekday": 6, "lot_basis": "C8R packaging standard nonbinding experiment"},
    ("773474", "1430"): {"operation": "internal_transfer_unconstrained_origin", "standard_binding": False,
        "review_weekday": None, "lot_basis": "No manufacturing batch imposed on transfer; upstream availability not modeled"},
}


def day(value):
    return (date.fromisoformat(str(value)) - ORIGIN).days


def stamp(value):
    return (ORIGIN + timedelta(days=value)).isoformat()


def decimal_sum(values):
    return sum((Decimal(str(v)) for v in values), Decimal(0))


def fingerprint(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_snapshot(article, decision_date):
    """Only a vintage already known at the decision can affect prediction."""
    eligible = [s for s in article["MRP_snapshots"] if s["vintage"] <= decision_date]
    if not eligible:
        raise ValueError("No known MRP vintage")
    return max(eligible, key=lambda s: s["vintage"])


def parameters(article, specification=None):
    spec = dict(specification if specification is not None else CATALOGUE[article["article"], article["division"]])
    if len(article["FIA_offers"]) != 1 or len(article["receipt_workdays_in_MRP"]) != 1:
        raise ValueError("Local experiment requires one explicit offer and one receipt calendar")
    offer = article["FIA_offers"][0]
    policy = article["stock_policy"]
    quantity = offer["standard_order_quantity"] if spec["standard_binding"] else 0
    return {**spec, "physical_lead_days": int(offer["supplier_lead_days"]),
        "receipt_workdays": int(next(iter(article["receipt_workdays_in_MRP"]))),
        "safety_workdays": int(policy["safety_workdays"]), "fixed_floor_qty": policy["fixed_safety_stock"],
        "minimum": quantity, "multiple": quantity, "maximum": None,
        "integer": article["unit"] == "UN", "net_rounding_quantum": 1 if article["unit"] == "kg" else 0,
        "grouping_days": 1, "supplier": offer["supplier"], "source_offer": offer["source"],
        "source_safety": policy["source"], "receipt_source": "Flow_Data_MRP_results.xlsx!Feuille1 column E in selected pair"}


def supply_calendar(decision_day, through_day, config):
    """Daily helper calendar filtered by actual weekday, not a Jan-1 modulo."""
    rows = dated_supply_release_calendar(decision_day=decision_day, through_day=through_day + 7,
        physical_lead_days=config["physical_lead_days"], receipt_days=config["receipt_workdays"],
        origin_date=ORIGIN.isoformat())
    weekday = config["review_weekday"]
    return tuple((release, available) for release, available in rows
                 if weekday is None or (ORIGIN.weekday() + release) % 7 == weekday)


def coverage(snapshot):
    first = day(snapshot["vintage"])
    rows = {day(r[0]): r for r in snapshot["rows"]}
    expected = list(range(first, first + HORIZON, 7))
    prefix = 0
    for marker in expected:
        if marker not in rows:
            break
        prefix += 1
    return {"present_week_count": sum(d in rows for d in expected),
        "absent_markers": [stamp(d) for d in expected if d not in rows],
        "contiguous_prefix_week_count": prefix,
        "contiguous_prefix_end_exclusive": stamp(first + 7 * prefix),
        "weekly_I": [rows[d][2] if d in rows else None for d in expected],
        "weekly_H_target": [rows[d][1] if d in rows else None for d in expected],
        "week_markers": [stamp(d) for d in expected],
        "status": "complete_documented_window" if prefix == 52 else "conditional_on_documented_needs_incomplete"}


def dated_needs(snapshot, decision_day, current_mode):
    if current_mode not in CURRENT_MODES:
        raise ValueError("Current-week assumption must be explicit")
    requirements, budgets = [], []
    for marker, _h, quantity, _j, _k, _receipt, source_row in snapshot["rows"]:
        start = day(marker)
        if start < decision_day or start >= decision_day + HORIZON:
            continue
        current = start == decision_day
        retained = 0 if current and current_mode == "excluded" else quantity
        dates = (decision_day,) if current else tuple(range(start, start + 7))
        parts = _conserved_weekly_forecast_parts(Fraction(str(retained)), dates)
        # Last-day residues can share a day; the fragment index is essential.
        for index, (due, qty) in enumerate(parts):
            requirements.append(Requirement(f"source_I:{source_row}:fragment:{index}", due, qty))
        represented = decimal_sum(q for _, q in parts)
        if represented != Decimal(str(retained)):
            raise ValueError("Dated forecast lost its weekly source budget")
        budgets.append({"source_row": source_row, "source_I": quantity, "retained": retained,
                        "fragment_count": len(parts), "sum_fragments": float(represented)})
    return tuple(requirements), budgets


def stock_and_book(article, snapshot, decision_day):
    available = Decimal(0)
    receipts, held, retained, excluded = [], [], [], []
    for marker, _h, _i, quantity, _k, _receipt, source_row in snapshot["rows"]:
        if not quantity:
            continue
        release = day(marker)
        if release <= decision_day:
            available += Decimal(str(quantity))
        else:
            identity = f"existing_J:{source_row}"
            receipts.append(FirmReceipt(identity, release, quantity, "held"))
            held.append({"id": identity, "quantity": quantity, "available_day": release,
                         "source_row": source_row, "physical_receipt": False})
    for order in article["opening_orders"]:
        physical, usable = day(order["physical_delivery_G"]), day(order["availability_I"])
        entry = {"id": f"Extract_En_cours:{order['source_row']}", "source_row": order["source_row"],
                 "qty": order["quantity"], "physical_day": physical, "available_day": usable,
                 "supplier": order["supplier"]}
        if physical > decision_day:
            if usable < physical:
                raise ValueError("Initial availability precedes physical promise")
            receipts.append(FirmReceipt(entry["id"], usable, order["quantity"], "confirmed"))
            retained.append({**entry, "assumption": "initial physical and usable promises unchanged; execution and identity linkage to J unknown"})
        else:
            reason = "possible_already_held_do_not_add_over_J" if usable > decision_day else "elapsed_initial_promise_execution_unconfirmed"
            excluded.append({**entry, "reason": reason})
    return float(available), tuple(receipts), {"existing_J_held": held,
        "initial_retained": retained, "initial_excluded": excluded,
        "identity_limit": "No order IDs connect J or H to Extract; distinct future promises are a stated hypothesis."}


def raw_deficit_profile(available, requirements, receipts, decision_day):
    """Independent chronological arithmetic, with no proposed receipts."""
    events = defaultdict(lambda: [Decimal(0), Decimal(0)])
    events[decision_day]
    for need in requirements:
        events[max(decision_day, need.due_day)][1] += Decimal(str(need.qty))
    for receipt in receipts:
        events[receipt.available_day][0] += Decimal(str(receipt.qty))
    balance, points = Decimal(str(available)), []
    intervals, active = [], None
    maximum, first = Decimal(0), None
    for when, (incoming, needs) in sorted(events.items()):
        balance += incoming - needs
        deficit = max(Decimal(0), -balance)
        maximum = max(maximum, deficit)
        if deficit and first is None:
            first = when
        if deficit:
            if active is None:
                active = {"start_day": when, "end_day_exclusive": None,
                          "max_deficit": float(deficit), "peak_day": when}
            elif float(deficit) > active["max_deficit"]:
                active.update(max_deficit=float(deficit), peak_day=when)
        elif active is not None:
            active["end_day_exclusive"] = when
            intervals.append(active)
            active = None
        points.append([when, float(incoming), float(needs), float(balance), float(deficit)])
    if active is not None:
        intervals.append(active)
    critical = []
    for point in ([next((p for p in points if p[4]), points[0]),
                   max(points, key=lambda p: p[4]), points[-1]] if points else []):
        if point not in critical:
            critical.append(point)
    return {"columns": ["day", "existing_receipts", "requirements", "balance", "deficit"],
            "critical_points": sorted(critical), "deficit_intervals": intervals,
            "chronological_event_count": len(points), "first_deficit_day": first, "max_deficit": float(maximum),
            "interpretation": "Availability deficit before proposals; later commitments remain credited and do not trigger duplicate purchases."}


def reference_comparison(snapshot, book, proposals, config, mask):
    """H is accessed only here, after all predictions have been computed."""
    first = day(snapshot["vintage"])
    physical, usable = defaultdict(Decimal), defaultdict(Decimal)
    for order in book["initial_retained"]:
        physical[(order["physical_day"] - first) // 7] += Decimal(str(order["qty"]))
        usable[(order["available_day"] - first) // 7] += Decimal(str(order["qty"]))
    for proposal in proposals:
        physical[(proposal.release_day + config["physical_lead_days"] - first) // 7] += Decimal(str(proposal.qty))
        usable[(proposal.available_day - first) // 7] += Decimal(str(proposal.qty))
    # Existing J releases are already physical stock; exclude them from both
    # comparisons with H. Available comparison is new receipts usable by week.
    result = []
    for index, marker in enumerate(mask["week_markers"]):
        target = mask["weekly_H_target"][index]
        result.append([marker, target, float(physical[index]), float(usable[index]),
                       index < mask["contiguous_prefix_week_count"]])
    def score(indices):
        selected = [result[i] for i in indices if result[i][1] is not None]
        reference = sum(r[1] for r in selected)
        matched_physical = sum(min(r[1], r[2]) for r in selected)
        matched_available = sum(min(r[1], r[3]) for r in selected)
        return {"weeks": len(selected), "reference_H": reference,
            "predicted_physical": sum(r[2] for r in selected), "predicted_available": sum(r[3] for r in selected),
            "physical_exact_matched_qty": matched_physical,
            "physical_unmatched_reference_H": reference - matched_physical,
            "physical_unmatched_prediction": sum(r[2] for r in selected) - matched_physical,
            "available_exact_matched_qty": matched_available,
            "available_unmatched_reference_H": reference - matched_available,
            "available_unmatched_prediction": sum(r[3] for r in selected) - matched_available,
            "physical_absolute_error": sum(abs(r[2] - r[1]) for r in selected),
            "available_absolute_error": sum(abs(r[3] - r[1]) for r in selected),
            "physical_WAPE": sum(abs(r[2] - r[1]) for r in selected) / reference if reference else None,
            "available_WAPE": sum(abs(r[3] - r[1]) for r in selected) / reference if reference else None}
    return {"columns": ["Sunday_marker", "H_target_or_null", "predicted_physical", "predicted_available", "within_contiguous_prefix"],
        "weekly": result, "contiguous_prefix_conditional_score": score(range(mask["contiguous_prefix_week_count"])),
        "all_present_weeks_descriptive_only": score(range(52)),
        "positive_H_target_weeks_descriptive_only": score(i for i, row in enumerate(result) if row[1] is not None and row[1] > 0),
        "tolerance_one_week_matching": "not_performed_no_conservative_quantity_matching_implemented",
        "missing_week_predictions": [{"marker": row[0], "physical": row[2], "available": row[3]}
            for row in result if row[1] is None and (row[2] or row[3])],
        "outside_52week_prediction": {"physical": sum(float(q) for i, q in physical.items() if i < 0 or i >= 52),
            "available": sum(float(q) for i, q in usable.items() if i < 0 or i >= 52)},
        "meaning": "H is a planned weekly reference, not proven committed orders or observed physical execution. Dates use Sun-Sat convention."}


def run_case(article, decision_date, current_mode="entirely_remaining", fixed_floor_mode="additive", specification=None):
    snapshot = select_snapshot(article, decision_date)
    if snapshot["vintage"] != decision_date:
        raise ValueError("This independent-snapshot bench decides exactly at known vintages")
    decision = day(decision_date)
    config = parameters(article, specification)
    mask = coverage(snapshot)
    needs, budgets = dated_needs(snapshot, decision, current_mode)
    available, receipts, book = stock_and_book(article, snapshot, decision)
    total = decimal_sum(n.qty for n in needs)
    supply = Decimal(str(available)) + decimal_sum(r.qty for r in receipts)
    lower = max(Decimal(0), total - supply)
    floor_lower = max(Decimal(0), total + Decimal(str(config["fixed_floor_qty"])) - supply)
    calendar = supply_calendar(decision, decision + HORIZON, config)
    sizing = LotSizing(minimum=config["minimum"], multiple=config["multiple"], maximum=config["maximum"],
                      integer=config["integer"], net_rounding_quantum=config["net_rounding_quantum"])
    physical, _sourced, audit = plan_anticipated_requirements(decision_day=decision, available_qty=available,
        requirements=needs, firm_receipts=receipts, source_working_days=config["safety_workdays"],
        origin_weekday=ORIGIN.weekday(), fixed_floor_qty=config["fixed_floor_qty"],
        lead_days=calendar[0][1] - calendar[0][0], lot_sizing=sizing,
        grouping_days=config["grouping_days"], fixed_floor_mode=fixed_floor_mode, exact_release_calendar=calendar)
    protected = audit["anticipated_plan"]
    identity = f"{article['article']}@{article['division']}/{decision_date}/{current_mode}/{fixed_floor_mode}"
    proposed = [{"id": f"{identity}/{p.proposal_id}", "local_id": p.proposal_id, "qty": p.qty,
        "release_day": p.release_day, "physical_arrival_day": p.release_day + config["physical_lead_days"],
        "available_day": p.available_day, "protected_requested_day": p.requested_day}
        for p in physical.proposals]
    return {"case_id": identity, "article": article["article"], "division": article["division"],
        "unit": article["unit"], "vintage": decision_date, "decision_day": decision,
        "current_week_assumption": current_mode, "fixed_floor_mode": fixed_floor_mode,
        "source_snapshot_id": f"{article['article']}@{article['division']}/{decision_date}",
        "scope_status": mask["status"], "quantity_bounds": {"documented_requirements": float(total),
            "available_J": available, "later_existing_J": sum(r["quantity"] for r in book["existing_J_held"]),
            "initial_external_commitments": sum(r["qty"] for r in book["initial_retained"]),
            "unprotected_net_lower_bound": float(lower), "net_plus_fixed_floor_lower_bound": float(floor_lower)},
        "weekly_budget_conservation": budgets, "requirement_fragment_count": len(needs),
        "proposals": proposed, "proposed_qty": physical.proposed_qty,
        "physical_late_qty": physical.late_qty, "physical_late_qty_days": physical.late_qty_days,
        "retained_firm_late_qty": physical.firm_late_qty,
        "protected_late_qty": protected.late_qty, "protected_late_qty_days": protected.late_qty_days,
        "uncovered_rounding_requirement_qty": sum(n.qty for n in physical.uncovered_requirements),
        "closing_projected_qty": physical.closing_projected_qty,
        "first_possible_new_release_day": calendar[0][0],
        "first_possible_new_available_day": calendar[0][1],
        "raw_deficit_before_proposals": raw_deficit_profile(available, needs, receipts, decision),
        "protected_raw_deficit_before_proposals": raw_deficit_profile(available, audit["anticipated_requirements"], receipts, decision),
        "H_reference_comparison": reference_comparison(snapshot, book, physical.proposals, config, mask)}


def build_benchmark(contract):
    cases, inputs, configured = [], [], []
    for article in contract["articles"]:
        pair = article["article"], article["division"]
        if pair not in CATALOGUE:
            raise ValueError(f"Pair outside explicit benchmark catalogue: {pair}")
        config = parameters(article)
        configured.append({"article": pair[0], "division": pair[1], "unit": article["unit"], "parameters": config})
        versions = sorted(s["vintage"] for s in article["MRP_snapshots"] if s["vintage"].startswith("2025-"))
        if len(versions) != 52 or len(set(versions)) != 52:
            raise ValueError("Expected 52 distinct known 2025 vintages per pair")
        for vintage in versions:
            snap = select_snapshot(article, vintage)
            available, _receipts, book = stock_and_book(article, snap, day(vintage))
            inputs.append({"snapshot_id": f"{pair[0]}@{pair[1]}/{vintage}", "vintage": vintage,
                "source_cells": [f"Feuille1!A{row[6]}:K{row[6]}" for row in snap["rows"]],
                "coverage": coverage(snap), "available_J": available, "book": book,
                "source_contract_location": {"article": pair[0], "division": pair[1], "vintage": vintage}})
            for current in CURRENT_MODES:
                for floor in FLOOR_MODES:
                    cases.append(run_case(article, vintage, current, floor))
    comparison = []
    by_case = {c["case_id"]: c for c in cases}
    for case in cases:
        if case["fixed_floor_mode"] != "additive":
            continue
        maximum = by_case[case["case_id"].rsplit("/", 1)[0] + "/maximum"]
        comparison.append({"article": case["article"], "division": case["division"], "unit": case["unit"],
            "vintage": case["vintage"], "current_week_assumption": case["current_week_assumption"],
            "additive_case": case["case_id"], "maximum_case": maximum["case_id"],
            "additive_minus_maximum_proposed_qty": case["proposed_qty"] - maximum["proposed_qty"],
            "additive_minus_maximum_physical_late_qty": case["physical_late_qty"] - maximum["physical_late_qty"]})
    monthly = []
    for conf in configured:
        for current in CURRENT_MODES:
            for floor in FLOOR_MODES:
                for month in range(1, 13):
                    rows = [c for c in cases if c["article"] == conf["article"] and c["division"] == conf["division"]
                            and c["current_week_assumption"] == current and c["fixed_floor_mode"] == floor
                            and int(c["vintage"][5:7]) == month]
                    monthly.append({"article": conf["article"], "division": conf["division"], "unit": conf["unit"],
                        "month": month, "current_week_assumption": current, "fixed_floor_mode": floor,
                        "snapshot_count": len(rows), "median_plan_proposal_qty": statistics.median(c["proposed_qty"] for c in rows),
                        "minimum_plan_proposal_qty": min(c["proposed_qty"] for c in rows),
                        "maximum_plan_proposal_qty": max(c["proposed_qty"] for c in rows),
                        "not_an_annual_or_monthly_purchase_total": True})
    highlights = [c["case_id"] for c in cases if c["vintage"] in {"2025-01-05", "2025-03-30", "2025-06-29", "2025-09-28"}]
    return {"schema_version": 1, "status": "conditional_local_plans_not_autonomous_chain_validation",
        "case_count": len(cases), "snapshot_count": len(inputs), "catalogue": configured,
        "protocol": {"physical_year": 2025, "rolling_horizon_days": HORIZON, "future_2026_needs_allowed": True,
            "H_is_input": False, "future_vintage_is_input": False, "observed_photo_is_input": False,
            "requirement_calendar": "Sun-Sat; current I entirely at decision or excluded, separate hypotheses",
            "stock": "J current available; future J already held; no double physical receipt",
            "new_order_safety": "Monday-Friday anticipation; dated exact receipt calendar; additive baseline and maximum sensitivity",
            "missing": "null remains unknown; entire plan conditional on supplied rows; prefix and supplied-week scores separate",
            "plans_not_summable": "52 overlapping plans are never summed as annual purchases",
            "internal_route_limit": "773474 source Gaillac stock/capacity not simulated",
            "firm_limit": "Original future Extract promises retained once with original identities/dates; intervening ERP revisions unknown"},
        "inputs": inputs, "cases": cases, "floor_comparisons": comparison,
        "monthly_snapshot_summaries": monthly, "highlight_case_ids": highlights,
        "adoption": "No chain correction adopted; industrial calibration and Scan3 scope remain unresolved."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=FOLDER / "source_contract.json")
    args = parser.parse_args(argv)
    contract_path = args.contract.resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    dependencies = [contract_path, Path(__file__),
        ROOT / "etudecas/tests/simulation/test_local_mrp_bench.py",
        ROOT / "etudecas/simulation/engine/mrp_planning.py",
        ROOT / "etudecas/simulation/engine/run_first_simulation.py"]
    dependencies += [ROOT / item["path"] for item in contract["sources"]]
    before = {p: fingerprint(p) for p in dependencies}
    for item in contract["sources"]:
        if before[ROOT / item["path"]] != item["sha256"]:
            raise RuntimeError(f"Source contract is stale: {item['path']}")
    result = build_benchmark(contract)
    for path, old in before.items():
        if fingerprint(path) != old:
            raise RuntimeError(f"Dependency changed during benchmark: {path}")
    result["provenance"] = [{"path": p.relative_to(ROOT).as_posix(), "sha256": h} for p, h in before.items()]
    result["postcheck"] = "all_dependencies_unchanged_read_only_hash_comparison"
    output = FOLDER / "bench.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "cases": result["case_count"],
                      "snapshots": result["snapshot_count"], "sha256": fingerprint(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
