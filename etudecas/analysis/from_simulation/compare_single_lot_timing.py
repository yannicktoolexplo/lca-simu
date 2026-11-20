"""Compare bounded work calendars for one engaged lot against 2025 records.

The source run supplies the other physical flows. This is a conditional lot
and stock replay, not an autonomous run or a fit of the factory's throughput.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import psutil

from etudecas.simulation.engine.production_component_issues import incremental_component_issue
from etudecas.simulation.engine.run_first_simulation import supplier_receipt_available_day

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "etudecas/artifacts/testing"
ORIGIN = date(2025, 1, 1)
PF = "268967"
EPS = 1e-6


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Inputs:
    def __init__(self):
        self.hashes = {}

    def bind(self, path):
        path = path.resolve()
        self.hashes[path] = digest(path)
        return path

    def json(self, path):
        return json.loads(self.bind(path).read_text(encoding="utf-8"))

    def rows(self, path, predicate):
        with self.bind(path).open(encoding="utf-8-sig", newline="") as stream:
            return [row for row in csv.DictReader(stream) if predicate(row)]

    def freeze(self):
        if any(digest(path) != signature for path, signature in self.hashes.items()):
            raise ValueError("An input changed during the comparison")
        return {path.relative_to(ROOT).as_posix(): signature for path, signature in self.hashes.items()}


def calendar_date(day):
    return (ORIGIN + timedelta(days=day)).isoformat()


def relative_day(stamp):
    return (date.fromisoformat(stamp) - ORIGIN).days


def equal(value, expected, label):
    if not math.isclose(value, expected, rel_tol=0, abs_tol=EPS):
        raise ValueError(f"{label}: {value} differs from {expected}")


def work_calendar(start, count, quantity):
    days = {}
    cursor = start
    while len(days) < count:
        if (ORIGIN + timedelta(days=cursor)).weekday() < 5:
            i = len(days)
            days[cursor] = ((i + 1) * quantity) // count - (i * quantity) // count
        cursor += 1
    return days


def component_debits(work, components, initial, witness_issues):
    cumulative = 0
    issued = {component["item"]: 0.0 for component in components}
    ledger = []
    for day, quantity in work.items():
        daily = {}
        for component in components:
            item, unit, ratio = (component[key] for key in ("item", "unit", "qty_per_pf"))
            increment = incremental_component_issue(cumulative, quantity, ratio, unit, issued[item])
            daily[item] = increment
            issued[item] += increment
            if unit == "UN" and not increment.is_integer():
                raise ValueError("A physical integer component was split fractionally")
            if issued[item] > witness_issues[item] + EPS:
                raise ValueError("The lot debits more than its reserved kit")
        cumulative += quantity
        ledger.append(dict(day=day, work=quantity, cumulative_work=cumulative, debits=daily))
    for item, quantity in issued.items():
        equal(quantity, witness_issues[item], f"conserved BOM issue {item}")
        if initial[item] + EPS < quantity:
            raise ValueError(f"No complete kit on the witness launch date for {item}")
    return ledger


def read_witness(inputs, folder, params, source):
    proof = inputs.json(folder / "final_manifest.json")
    if proof["status"] != "completed_comparison_of_exactly_one_explicit_factory_commitment" or proof["days"] != params["days"]:
        raise ValueError("Expected the qualified one-order witness")
    pair_proof = inputs.json(folder / "validator/run_pair_review.json")
    if pair_proof["passed"] is not True:
        raise ValueError("Missing independent review of the witness")
    trace = pair_proof["details"]["target_lot_trace"]["candidate"]
    if not trace["executed"] or trace["release_day"] != params["start_day"] or trace["qty"] != params["quantity"]:
        raise ValueError("The actual lot does not match the protocol")
    if trace["served_from_target_lot"] != 0:
        raise ValueError("This overlay requires dispatches allocated to the other stock")
    data = folder / "runs/candidate/run/data"
    observed_compare = inputs.json(folder / "comparison/comparison.json")
    start = params["start_day"]
    key = "item:" + PF
    outputs = inputs.rows(data / "production_output_products_daily.csv",
        lambda r: r["node_id"] == "M-1430" and r["item_id"] == key and float(r["executed_qty"]) != 0)
    if [(int(r["day"]), float(r["executed_qty"]), float(r["released_qty"])) for r in outputs] != [(start, params["quantity"], params["quantity"])]:
        raise ValueError("Another execution would make the single-lot overlay invalid")
    native_events = inputs.rows(data / "production_lot_events.csv", lambda r:
        r["event_type"] == "production_consume" and r["production_campaign_id"] == trace["campaign_id"])
    issues = defaultdict(float)
    for row in native_events:
        item = row["item_id"].removeprefix("item:")
        issues[item] += float(row["qty"]) / (1000 if row["uom"] == "G" else 1)
    components = source["products"][PF]["components"]
    if set(issues) != {r["item"] for r in components}:
        raise ValueError("The lot's material identity changed")
    native_stocks = inputs.rows(data / "production_input_stocks_daily.csv", lambda r:
        r["day"] == str(start) and r["node_id"] == "M-1430" and r["item_id"].removeprefix("item:") in issues)
    units = {r["item_id"].removeprefix("item:"): r["uom"] for r in native_events}
    kit = {r["item_id"].removeprefix("item:"): float(r["stock_before_production"]) /
           (1000 if units[r["item_id"].removeprefix("item:")] == "G" else 1) for r in native_stocks}

    days = params["days"]
    stock = {int(r["day"]): {k: float(r[k]) for k in ("physical_qty", "available_qty", "held_qty", "reserved_qty")}
             for r in inputs.rows(data / "production_stock_availability_daily.csv", lambda r:
                 r["node_id"] == "DC-1920" and r["item_id"] == key)}
    departures = defaultdict(float)
    for row in inputs.rows(data / "production_supplier_shipments_daily.csv", lambda r:
            r["src_node_id"] == "DC-1920" and r["item_id"] == key and r["realized_departure_day"] != ""):
        departures[int(row["realized_departure_day"])] += float(row["executed_shipped_qty"])
    service = inputs.rows(data / "production_demand_service_daily.csv", lambda r: r["item_id"] == key)
    assert sorted(stock) == list(range(days)) and len(service) == days
    weekly = [r for r in observed_compare["weekly"] if r["product"] == PF and r["real"] is not None]
    assert len(weekly) == 10
    real_index = {r["start"]: r for r in source["products"][PF]["weeks"]}
    for row in weekly:
        equal(row["real"], real_index[row["start"]]["estimated_production"], "same real packaging week")
    photos = [r for r in observed_compare["photos"][PF] if r["comparable"]]
    assert len(photos) == 17
    for row in photos:
        equal(row["qty"], real_index[row["date"]]["stock_start"], "same real stock photo")
    native_dates = {event: trace["physical_chain"][event][0]["day"]
                    for event in ("lane_ship", "lane_receipt", "stock_availability_release")}
    return dict(trace=trace, stock=stock, departures=departures, weekly=weekly, photos=photos,
                metrics=observed_compare["products"][PF]["candidate"], issues=dict(issues), kit=kit,
                components=components, service=service, native_dates=native_dates)


def open_stock_without_lot(native, params):
    receipt = native["native_dates"]["lane_receipt"]
    release = native["native_dates"]["stock_availability_release"]
    quantity = params["quantity"]
    remainder = {}
    for day, balances in native["stock"].items():
        b = balances.copy()
        if day >= receipt:
            b["physical_qty"] -= quantity
            b["available_qty" if day >= release else "held_qty"] -= quantity
        equal(b["physical_qty"], b["available_qty"] + b["held_qty"] + b["reserved_qty"], "remainder stock")
        if min(b.values()) < 0:
            raise ValueError("The lot was used or did not enter stock as declared")
        remainder[day] = b
    if native["departures"][0] != 0:
        raise ValueError("A first-day dispatch requires an opening-stock witness")
    margins = {day: remainder[day - 1]["available_qty"] - native["departures"][day]
               for day in range(1, params["days"])}
    if min(margins.values()) < 0:
        raise ValueError("Frozen client dispatches are not supported by the common stock")
    return remainder, margins


def scenario(workdays, params, native, common, real):
    work = work_calendar(params["start_day"], workdays, params["quantity"])
    ledger = component_debits(work, native["components"], native["kit"], native["issues"])
    finish = max(work)
    arrival = finish + params["transport_calendar_days"]
    usable = supplier_receipt_available_day(arrival, params["muret_receipt_workdays"],
        origin_date=ORIGIN.isoformat(), calendar="monday_friday")
    stock = []
    quantity = params["quantity"]
    cumulative_work = 0
    for day, balance in common.items():
        b = balance.copy()
        if day >= arrival:
            b["physical_qty"] += quantity
            b["available_qty" if day >= usable else "held_qty"] += quantity
        cumulative_work += work.get(day, 0)
        stock.append(dict(day=day, date=calendar_date(day), **b, work=work.get(day, 0),
            wip_work_equivalent=cumulative_work if day < finish else 0, finished_pf=quantity if day==finish else 0))
    weeks = []
    for row in native["weekly"]:
        first = relative_day(row["start"])
        candidate = sum(work.get(d, 0) for d in range(first, first + 7))
        weeks.append(dict(start=row["start"], real=row["real"], packaging=candidate, abs_error=abs(candidate-row["real"])))
    photos = []
    for row in native["photos"]:
        physical = stock[relative_day(row["date"]) - 1]["physical_qty"]
        photos.append(dict(date=row["date"], real=row["qty"], physical=physical, abs_error=abs(physical-row["qty"])))
    cumulative_arrivals = []
    target = 0
    for row in real:
        target += row["conditional_inbound"]
        visible = quantity if arrival < relative_day(row["stock_end_date"]) else 0
        cumulative_arrivals.append(dict(week=row["start"], reconstructed=target, simulated=visible,
                                        abs_error=abs(visible-target)))
    metrics = dict(packaging_mae=sum(row["abs_error"] for row in weeks)/len(weeks),
        stock_mae=sum(row["abs_error"] for row in photos)/len(photos), packaging_on_known_weeks=sum(row["packaging"] for row in weeks),
        end_stock=stock[-1]["physical_qty"], march_cumulative_arrival_error=sum(r["abs_error"] for r in cumulative_arrivals))
    return dict(workdays=workdays, finish_day=finish, muret_arrival_day=arrival, muret_usable_day=usable,
        dates=dict(finish=calendar_date(finish), arrival=calendar_date(arrival), usable=calendar_date(usable)),
        metrics=metrics, material_ledger=ledger, stock=stock, weeks=weeks, photos=photos,
        march_cumulative_arrivals=cumulative_arrivals)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--protocol", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    t0 = time.monotonic()
    inputs = Inputs()
    for path in (Path(__file__), ROOT/"etudecas/simulation/engine/production_component_issues.py",
                 ROOT/"etudecas/simulation/engine/run_first_simulation.py"):
        inputs.bind(path)
    study = inputs.json(args.protocol)
    params = study["hypotheses"]
    assert params["origin"] == ORIGIN.isoformat() and params["workdays"] == [1, 5, 10]
    source = ROOT/study["sources"]
    source_proof = inputs.json(source/"final_manifest.json")
    source_path = ROOT/source_proof["dataset"]["path"]
    source_data = inputs.json(source_path)
    assert source_proof["dataset"]["sha256"] == inputs.hashes[source_path.resolve()]
    native = read_witness(inputs, ROOT/study["witness"], params, source_data)
    # In this trial the target remains untouched by the dispatch ledger, and
    # the rest of the available stock covers every dispatch without same-day receipts.
    common, margins = open_stock_without_lot(native, params)
    march = [r for r in source_data["products"][PF]["weeks"]
             if "2025-03-17" <= r["start"] <= "2025-03-31"]
    assert len(march) == 3 and [r["conditional_inbound"] for r in march] == [40824, 63504, 5920]
    cases = {str(n): scenario(n, params, native, common, march) for n in params["workdays"]}
    witness = cases["1"]
    equal(witness["metrics"]["packaging_mae"], native["metrics"]["all"]["absolute_error"], "native packaging MAE")
    equal(witness["metrics"]["stock_mae"], native["metrics"]["stock"]["mae_units"], "native stock MAE")
    assert (witness["finish_day"], witness["muret_arrival_day"], witness["muret_usable_day"]) == (
        native["native_dates"]["lane_ship"], native["native_dates"]["lane_receipt"], native["native_dates"]["stock_availability_release"])
    for row in witness["stock"]:
        for k, value in native["stock"][row["day"]].items():
            equal(row[k], value, "native daily stock reconstruction")
    assert all(w["packaging"] == r["candidate"] for w,r in zip(witness["weeks"],native["weekly"],strict=True))
    # Positive changes on two disjoint, zero-adjustment weeks require two
    # incoming contributions if the only other physical movement is withdrawal.
    assert all(r["balance_residual"] == r["movement"]["divers"] == 0 and r["stock_change"] > 0 for r in march[:2])
    no_common_single_receipt = [r["stock_change"] for r in march[:2]]
    evidence = inputs.freeze()
    elapsed = time.monotonic() - t0
    mem = psutil.Process().memory_info()
    peak = max(mem.rss, getattr(mem, "peak_wset", 0))
    assert elapsed < study["budget"]["local_seconds"] and peak < study["budget"]["memory_mib"] * 1024**2
    result = dict(status="passed_single_lot_conditional_replay", source_stable=True,
        cases=cases, inputs_sha256=evidence, elapsed_seconds=elapsed, peak_memory_bytes=peak,
        client_service=dict(conditional_same_ledger=True, min_available_after_covering_dispatches=min(margins.values()),
            total_served=sum(float(r["served_qty"]) for r in native["service"]),
            lot_native_client_allocation=0),
        order_trace=native["trace"], reserved_launch_kit=native["issues"], kit_available_at_launch=native["kit"],
        positive_stock_changes_two_disjoint_weeks=no_common_single_receipt,
        limits=["Conditional replay. Subsequent MRP decisions and other lot timings are fixed.",
            "Work periods and whole-lot shipment are tested hypotheses.",
            "Conditional March receipts assume contemporaneous service.",
            "A partial receipt, another lot or a different stock perimeter remains possible."])
    serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    assert len(serialized.encode("utf-8")) < study["budget"]["result_mib"] * 1024**2
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(serialized)
    print(json.dumps(dict(status=result["status"], cases={k:v["metrics"] for k,v in cases.items()}, seconds=elapsed)))


if __name__ == "__main__":
    main()
