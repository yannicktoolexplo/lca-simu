"""Reconcile delivered map runs with their daily demand CSV and package checks."""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import json
import math
from pathlib import Path

from etudecas.simulation.run_format.validator import validate_run_package


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reconcile_run(root: Path) -> dict:
    summary_path = root / "summaries/first_simulation_summary.json"
    csv_path = root / "data/production_demand_service_daily.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    days = int(summary["sim_days"])
    totals = defaultdict(float)
    backlog = defaultdict(float)
    product = defaultdict(lambda: defaultdict(float))
    seen = set()
    observed_days = set()
    errors = []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            day = int(row["day"])
            key = day, row["node_id"], row["item_id"]
            if key in seen:
                errors.append(f"duplicate demand row: {key}")
            seen.add(key)
            observed_days.add(day)
            values = {field: float(row[field]) for field in (
                "demand_qty", "served_qty", "backlog_end_qty", "required_with_backlog_qty")}
            if any(not math.isfinite(value) or value < -1e-6 for value in values.values()):
                errors.append(f"invalid quantity: {key}")
                continue
            for field in ("demand_qty", "served_qty"):
                totals[field] += values[field]
                product[row["item_id"]][field] += values[field]
            backlog[day] += values["backlog_end_qty"]
            if day == 0:
                totals["opening_backlog"] += values["required_with_backlog_qty"] - values["demand_qty"]
            if day == days - 1:
                product[row["item_id"]]["ending_backlog"] += values["backlog_end_qty"]
    if observed_days != set(range(days)):
        errors.append("daily horizon differs from summary")
    totals["ending_backlog"] = backlog.get(days - 1, 0.0)
    totals["fill_rate"] = totals["served_qty"] / totals["demand_qty"] if totals["demand_qty"] else None
    for csv_field, summary_field in (("demand_qty", "total_demand"), ("served_qty", "total_served"),
                                    ("ending_backlog", "ending_backlog"), ("fill_rate", "fill_rate")):
        expected = summary["kpis"].get(summary_field)
        actual = totals[csv_field]
        tolerance = 1e-6 if csv_field == "fill_rate" else .01
        if expected is None or actual is None or not math.isclose(actual, float(expected), rel_tol=0, abs_tol=tolerance):
            errors.append(f"CSV/summary mismatch: {summary_field}: {actual} vs {expected}")
    balance = totals["opening_backlog"] + totals["demand_qty"] - totals["served_qty"] - totals["ending_backlog"]
    if not math.isclose(balance, 0, rel_tol=0, abs_tol=.01):
        errors.append(f"demand balance mismatch: {balance}")
    package_checks = validate_run_package(root / "run")
    errors.extend(f"package: {check['name']}" for check in package_checks if not check["ok"])
    return {"output_dir": str(root.resolve()), "scenario_id": summary["scenario_id"], "days": days,
            "rows": len(seen), "csv_sha256": file_hash(csv_path), "summary_sha256": file_hash(summary_path),
            "csv_totals": dict(totals), "products": {key: dict(value) for key, value in product.items()},
            # Forecast residuals remain meaningful below one physical unit.
            # Use the documented comparison threshold, not a different cutoff.
            "days_with_backlog_including_startup": sum(v > 1e-9 for v in backlog.values()),
            "peak_backlog": max(backlog.values(), default=0), "backlog_quantity_days": sum(backlog.values()),
            "total_cost": summary["kpis"].get("total_cost"), "package_checks": package_checks,
            "errors": errors, "ok": not errors}


def reconcile_exported_cost(values: list[str], summary_total: float, *, rounding_terms_per_value: int) -> dict:
    """Bound export rounding, without a relative or arbitrary money tolerance.

    The engine exports monetary columns and summary totals to four decimals.
    total_supply_cost_day combines five already-rounded costs and rounds its
    sum with raw production cost once more: six rounding terms per daily value.
    Each external purchase/transport column has just one rounding term.
    A final half-quantum covers the independently rounded summary total.
    See run_first_simulation.py daily_rows, total_supply_cost_day and kpis.
    """
    quantum = Decimal("0.0001")
    try:
        numbers = [Decimal(value) for value in values]
        summary = Decimal(str(summary_total))
        if any(not value.is_finite() or value != value.quantize(quantum) for value in [*numbers, summary]):
            raise ValueError("monetary export is not finite at the documented four-decimal precision")
    except InvalidOperation as exc:
        raise ValueError("invalid monetary export") from exc
    total = sum(numbers, Decimal(0))
    terms = len(numbers) * rounding_terms_per_value + 1
    tolerance = terms * quantum / 2
    difference = abs(total - summary)
    return dict(csv_total=str(total), summary_total=str(summary), absolute_difference=str(difference),
                rounding_tolerance=str(tolerance), rounding_terms=terms, export_decimals=4,
                exported_values=len(numbers), rounding_terms_per_value=rounding_terms_per_value,
                ok=difference <= tolerance)


def reconcile_browser(browser: dict, runs: list[dict], *, cost_checks: list | None = None) -> list[str]:
    """Independent source oracle for browser values, monetary scopes and v3 score.

    Do not import a map producer: summaries and daily CSVs are read directly.
    The score is checked against those quantities, not another payload score.
    """
    errors = []
    if not browser.get("ok"):
        errors.append("browser review failed")
    try:
        if file_hash(Path(browser["html"])) != browser["html_sha256"]:
            errors.append("reviewed HTML changed")
        payload = browser["payload"]
        scenarios = payload["comparison"]
        by_id = {s["id"]: s for s in scenarios}
        expected = {Path(r["output_dir"]).name: r for r in runs}
        if set(by_id) != set(expected) or len(by_id) != len(scenarios):
            errors.append("HTML scenario set differs from reviewed runs")
        references = [s for s in scenarios if s.get("is_reference")]
        if len(references) != 1:
            errors.append("HTML must identify one reference")
        reference = expected[references[0]["id"]] if len(references) == 1 else None
        source = {}
        for sid, run in expected.items():
            root = Path(run["output_dir"])
            summary_path = root / "summaries/first_simulation_summary.json"
            demand_path = root / "data/production_demand_service_daily.csv"
            if file_hash(summary_path) != run["summary_sha256"] or file_hash(demand_path) != run["csv_sha256"]:
                errors.append(f"{sid}: sources changed since run reconciliation")
            summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
            money = summary.get("kpis", {})
            coverage = summary.get("economic_valuation") or {}
            complete = coverage.get("status") == "complete" and coverage.get("complete") is True
            if complete and coverage.get("unknown_inventory_pairs"):
                errors.append(f"{sid}: complete valuation contradicts unknown inventory pairs")
            def numeric(field, fallback=None):
                value = money.get(field)
                if value is None and fallback:
                    value = money.get(fallback)
                if value is None:
                    return None
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError(f"{sid}: nonfinite monetary source {field}")
                return value
            operating = numeric("known_cost_subtotal", "total_cost")
            external = numeric("total_external_procurement_cost", "exceptional_supply_cost")
            exposure = numeric("known_economic_exposure_subtotal", "total_economic_exposure")
            if operating is not None and external is not None:
                if exposure is not None and not math.isclose(exposure, operating + external, rel_tol=0, abs_tol=.01):
                    errors.append(f"{sid}: economic exposure source differs from operating plus external")
                if exposure is None:
                    exposure = operating + external
            if complete and any(value is None for value in (operating, external, exposure)):
                errors.append(f"{sid}: complete valuation lacks a monetary scope")
            cost_path = root / "data/first_simulation_daily.csv"
            if cost_path.exists():
                with cost_path.open(encoding="utf-8-sig", newline="") as stream:
                    daily_costs = list(csv.DictReader(stream))
                if len(daily_costs) != run["days"] or {int(row["day"]) for row in daily_costs} != set(range(run["days"])):
                    errors.append(f"{sid}: daily cost CSV horizon or uniqueness differs")
                for column, amount in (("total_supply_cost_day", operating),):
                    if amount is not None and daily_costs and all(row.get(column) not in (None, "") for row in daily_costs):
                        check = reconcile_exported_cost([row[column] for row in daily_costs], amount, rounding_terms_per_value=6)
                        if cost_checks is not None:
                            cost_checks.append(dict(scenario=sid, scope="operating", csv=str(cost_path), csv_sha256=file_hash(cost_path), **check))
                        if not check["ok"]:
                            errors.append(f"{sid}: daily CSV operating cost differs from summary")
                external_fields = ("external_procurement_transport_cost_day", "external_procurement_purchase_cost_day")
                if external is not None and daily_costs and all(row.get(field) not in (None, "") for row in daily_costs for field in external_fields):
                    check = reconcile_exported_cost([row[field] for row in daily_costs for field in external_fields], external, rounding_terms_per_value=1)
                    if cost_checks is not None:
                        cost_checks.append(dict(scenario=sid, scope="external_procurement", csv=str(cost_path), csv_sha256=file_hash(cost_path), **check))
                    if not check["ok"]:
                        errors.append(f"{sid}: daily CSV external cost differs from summary")
            per_day = defaultdict(lambda: [0.0, 0.0])
            with demand_path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    per_day[int(row["day"])][0] += float(row["served_qty"])
                    per_day[int(row["day"])][1] += float(row["backlog_end_qty"])
            startup = []
            for day in range(run["days"]):
                served, backlog = per_day[day]
                if served <= 1e-9 and backlog > 1e-9:
                    startup.append(day)
                else:
                    break
            later = [values[1] for day, values in per_day.items() if day not in startup]
            source[sid] = dict(operating_cost=operating, external_procurement_cost=external,
                               economic_exposure=exposure, complete=complete,
                               status="complete" if complete else "incomplete" if coverage else "unknown",
                               startup=len(startup), backlog_days=sum(value > 1e-9 for value in later),
                               max_backlog=max(later, default=0.0))
        base = source[references[0]["id"]] if reference else None
        for sid, run in expected.items():
            scenario = by_id[sid]
            kpis = scenario["kpis"]
            oracle = source[sid]
            if scenario["horizon_days"] != run["days"]:
                errors.append(f"{sid}: HTML horizon differs")
            pairs = [("total_demand", run["csv_totals"]["demand_qty"], .01),
                     ("total_served", run["csv_totals"]["served_qty"], .01),
                     ("ending_backlog", run["csv_totals"]["ending_backlog"], .01),
                     ("fill_rate", run["csv_totals"]["fill_rate"], 1e-6),
                     ("total_cost", oracle["operating_cost"], .01),
                     ("operating_cost", oracle["operating_cost"], .01),
                     ("external_procurement_cost", oracle["external_procurement_cost"], .01),
                     ("economic_exposure", oracle["economic_exposure"], .01),
                     ("max_backlog", oracle["max_backlog"], .01)]
            if reference:
                comparable = oracle["complete"] and base["complete"]
                signed_operating = oracle["operating_cost"] - base["operating_cost"]
                signed_exposure = oracle["economic_exposure"] - base["economic_exposure"] if oracle["economic_exposure"] is not None and base["economic_exposure"] is not None else None
                monetary_pct = 100 * max(0, oracle["operating_cost"] - max(1, base["operating_cost"])) / max(1, base["operating_cost"]) if comparable else None
                service_loss_pp = max(0, 100 * (reference["csv_totals"]["fill_rate"] - run["csv_totals"]["fill_rate"]))
                backlog_pct = 100 * oracle["max_backlog"] / max(1, run["csv_totals"]["demand_qty"] or reference["csv_totals"]["demand_qty"])
                score = 5 * service_loss_pp + 3 * backlog_pct + .25 * (monetary_pct or 0)
                pairs.extend([("cost_delta", signed_operating, .01), ("operating_cost_delta", signed_operating, .01),
                              ("economic_exposure_delta", signed_exposure, .01), ("cost_delta_pct", monetary_pct, 1e-6),
                              ("observed_impact_score", score, 1e-6),
                              ("fill_rate_delta_pp", 100 * (run["csv_totals"]["fill_rate"] - reference["csv_totals"]["fill_rate"]), 1e-4)])
                if kpis.get("monetary_comparison_eligible") is not comparable:
                    errors.append(f"{sid}: monetary comparison eligibility differs")
                excluded = {"material_loss", "replanning"} | ({"cost"} if not comparable else set())
                if set(kpis.get("score_excluded_dimensions", [])) != excluded:
                    errors.append(f"{sid}: score excluded dimensions differ")
            if kpis.get("score_contract") != "customer_cost_v3_valuation_guard":
                errors.append(f"{sid}: obsolete or missing score contract")
            for key in ("valuation_complete", "economic_ranking_eligible"):
                if kpis.get(key) is not oracle["complete"]:
                    errors.append(f"{sid}: HTML {key} differs")
            if kpis.get("valuation_status") != oracle["status"]:
                errors.append(f"{sid}: valuation status differs")
            for key, value, tolerance in pairs:
                actual = kpis[key]
                matches = actual is None if value is None else isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) and math.isclose(actual, value, rel_tol=0, abs_tol=tolerance)
                if not matches:
                    errors.append(f"{sid}: HTML {key} differs")
            if kpis["backlog_days"] != oracle["backlog_days"] or kpis["startup_backlog_days"] != oracle["startup"]:
                errors.append(f"{sid}: HTML backlog days differ")
    except (KeyError, TypeError, ValueError, OSError) as exc:
        errors.append(f"invalid browser review: {exc}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-review", type=Path)
    args = parser.parse_args(argv)
    result = {"schema_version": "etudecas.map_delivery_review.v1",
              "scope": "CSV reconciliation and run packages; cumulative service is not on-time service",
              "runs": [reconcile_run(root) for root in args.run]}
    result["ok"] = all(run["ok"] for run in result["runs"])
    if args.browser_review:
        result["cost_rounding_checks"] = []
        result["browser_errors"] = reconcile_browser(
            json.loads(args.browser_review.read_text(encoding="utf-8")), result["runs"], cost_checks=result["cost_rounding_checks"])
        result["ok"] = result["ok"] and not result["browser_errors"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "runs": [{"scenario": r["scenario_id"], "errors": r["errors"]} for r in result["runs"]]}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
