"""Compare observed immobilized component stock with simulated excess stock.

The business CSVs provide a value of immobilized component stock. They should not
be compared with the whole simulated component inventory. This script values only
the simulated stock above a useful threshold and compares it with the observed
weekly snapshots.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "result"
    / "_reruns"
    / "active_mrp_physical_state_dependent_5y_20260702_213259"
)
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
SIM_START_DATE = date(2025, 1, 1)


PRODUCTS = {
    "cos": {
        "code": "268091",
        "factory": "M-1810",
        "csv_pattern": "Stock_Composants*_Cos.csv",
    },
    "pharma": {
        "code": "268967",
        "factory": "M-1430",
        "csv_pattern": "Stock_Composants*_Pharma.csv",
    },
}

THRESHOLD_MODES = (
    "target_stock",
    "coverage",
    "safety_plus_coverage",
    "max_safety_coverage",
    "demand_90d",
    "demand_180d",
)


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def single_source(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one source for {pattern}, found {len(matches)}: {matches}")
    return matches[0]


def read_observed_stock(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            snapshot_date = datetime.fromisoformat(row["Date de photo DMP"]).date()
            rows.append(
                {
                    "date": snapshot_date.isoformat(),
                    "day": (snapshot_date - SIM_START_DATE).days,
                    "observed_value": parse_float(row["Sum_Valeur totale du stock"]),
                }
            )
    return [row for row in rows if 0 <= row["day"] <= 1824]


def production_component_items(run_dir: Path) -> dict[str, set[str]]:
    path = run_dir / "data" / "production_lot_genealogy.csv"
    out: dict[str, set[str]] = {domain: set() for domain in PRODUCTS}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("link_type") != "production":
                continue
            for domain, meta in PRODUCTS.items():
                if row.get("child_node_id") == meta["factory"] and row.get("child_item_id") == f"item:{meta['code']}":
                    item_id = row.get("parent_item_id")
                    if item_id:
                        out[domain].add(item_id)
    return out


def component_prices(
    graph: dict[str, Any], component_items: dict[str, set[str]]
) -> dict[str, dict[str, dict[str, Any]]]:
    prices: dict[str, dict[str, list[float]]] = {domain: {} for domain in PRODUCTS}
    source_count: dict[str, dict[str, int]] = {domain: {} for domain in PRODUCTS}
    zero_count: dict[str, dict[str, int]] = {domain: {} for domain in PRODUCTS}
    price_scope: dict[str, dict[str, set[str]]] = {domain: {} for domain in PRODUCTS}
    product_priced_items: dict[str, set[str]] = {domain: set() for domain in PRODUCTS}

    for edge in graph.get("edges", []):
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        if edge.get("type") != "transport":
            continue
        for domain, meta in PRODUCTS.items():
            if edge.get("to") != meta["factory"] or attrs.get("product_code") != meta["code"]:
                continue
            item_id = (edge.get("items") or [None])[0]
            if item_id:
                product_priced_items[domain].add(item_id)

    for edge in graph.get("edges", []):
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        if edge.get("type") != "transport":
            continue
        for domain, meta in PRODUCTS.items():
            if edge.get("to") != meta["factory"]:
                continue
            item_id = (edge.get("items") or [None])[0]
            if not item_id:
                continue
            is_product_price = attrs.get("product_code") == meta["code"]
            is_fallback_price = item_id in component_items.get(domain, set()) and not attrs.get("product_code")
            if not is_product_price and not is_fallback_price:
                continue
            if is_fallback_price and item_id in product_priced_items[domain]:
                continue
            sell_price = parse_float(terms.get("sell_price"), default=float("nan"))
            price_base = parse_float(terms.get("price_base"), default=1.0) or 1.0
            source_count[domain][item_id] = source_count[domain].get(item_id, 0) + 1
            price_scope[domain].setdefault(item_id, set()).add(
                "product_code" if is_product_price else "factory_item_fallback"
            )
            if sell_price != sell_price:
                continue
            unit_price = sell_price / price_base
            if unit_price <= 0:
                zero_count[domain][item_id] = zero_count[domain].get(item_id, 0) + 1
                continue
            prices[domain].setdefault(item_id, []).append(unit_price)

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for domain, by_item in prices.items():
        out[domain] = {}
        all_items = set(source_count[domain]) | set(by_item) | component_items.get(domain, set())
        for item_id in sorted(all_items):
            values = by_item.get(item_id, [])
            scopes = sorted(price_scope[domain].get(item_id, set()))
            out[domain][item_id] = {
                "unit_price": statistics.median(values) if values else None,
                "priced_sources": len(values),
                "source_count": source_count[domain].get(item_id, 0),
                "zero_price_sources": zero_count[domain].get(item_id, 0),
                "price_scope": "+".join(scopes) if scopes else "missing",
            }
    return out


def read_input_stocks(run_dir: Path) -> dict[tuple[int, str, str], float]:
    path = run_dir / "data" / "production_input_stocks_daily.csv"
    stocks: dict[tuple[int, str, str], float] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            stocks[(int(row["day"]), row["node_id"], row["item_id"])] = parse_float(row["stock_end_of_day"])
    return stocks


def read_mrp_trace(run_dir: Path) -> dict[tuple[int, str, str], dict[str, float]]:
    path = run_dir / "data" / "mrp_trace_daily.csv"
    fields = (
        "target_stock_qty",
        "coverage_target_qty",
        "safety_stock_qty",
        "soft_safety_target_qty",
        "target_demand_signal_qty",
    )
    trace: dict[tuple[int, str, str], dict[str, float]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            trace[(int(row["day"]), row["node_id"], row["item_id"])] = {
                field: parse_float(row.get(field)) for field in fields
            }
    return trace


def threshold_value(values: dict[str, float], mode: str) -> float:
    if mode == "target_stock":
        return values["target_stock_qty"]
    if mode == "coverage":
        return values["coverage_target_qty"]
    if mode == "safety_plus_coverage":
        return values["coverage_target_qty"] + values["safety_stock_qty"]
    if mode == "max_safety_coverage":
        return max(values["coverage_target_qty"], values["safety_stock_qty"], values["soft_safety_target_qty"])
    if mode == "demand_90d":
        return values["target_demand_signal_qty"] * 90.0
    if mode == "demand_180d":
        return values["target_demand_signal_qty"] * 180.0
    raise ValueError(f"Unknown threshold mode: {mode}")


def simulated_immobilized_value(
    *,
    domain: str,
    day: int,
    mode: str,
    prices: dict[str, dict[str, Any]],
    stocks: dict[tuple[int, str, str], float],
    mrp_trace: dict[tuple[int, str, str], dict[str, float]],
) -> tuple[float, list[dict[str, Any]]]:
    factory = PRODUCTS[domain]["factory"]
    total = 0.0
    details: list[dict[str, Any]] = []
    for item_id, price_info in prices.items():
        unit_price = price_info.get("unit_price")
        if unit_price is None:
            continue
        stock_qty = stocks.get((day, factory, item_id), 0.0)
        mrp = mrp_trace.get((day, factory, item_id))
        if not mrp:
            continue
        useful_qty = threshold_value(mrp, mode)
        immobilized_qty = max(stock_qty - useful_qty, 0.0)
        value = immobilized_qty * float(unit_price)
        total += value
        if value > 0:
            details.append(
                {
                    "item_id": item_id,
                    "stock_qty": stock_qty,
                    "useful_qty": useful_qty,
                    "immobilized_qty": immobilized_qty,
                    "unit_price": unit_price,
                    "immobilized_value": value,
                }
            )
    details.sort(key=lambda row: row["immobilized_value"], reverse=True)
    return total, details


def metric_row(values: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    observed = [float(row["observed_value"]) for row in values]
    simulated = [float(row[f"sim_{mode}"]) for row in values]
    diffs = [sim - obs for obs, sim in zip(observed, simulated)]
    observed_mean = statistics.mean(observed)
    simulated_mean = statistics.mean(simulated)
    return {
        "mode": mode,
        "snapshots": len(values),
        "observed_mean": observed_mean,
        "simulated_mean": simulated_mean,
        "ratio_mean": simulated_mean / observed_mean if observed_mean else None,
        "bias": statistics.mean(diffs),
        "bias_pct": statistics.mean(diffs) / observed_mean if observed_mean else None,
        "mae": statistics.mean(abs(diff) for diff in diffs),
        "mae_pct": statistics.mean(abs(diff) for diff in diffs) / observed_mean if observed_mean else None,
        "observed_min": min(observed),
        "observed_max": max(observed),
        "simulated_min": min(simulated),
        "simulated_max": max(simulated),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_eur(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.0f} EUR".replace(",", " ")


def format_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Comparaison stock composants immobilise",
        "",
        "Stock immobilise simule = max(stock usine - seuil utile, 0) x prix composant.",
        "Les prix viennent des liens fournisseur-usine du graphe prepare.",
        "",
        "| Domaine | PF | Mode | Reel moyen | Simule moyen | Ratio | Biais | Erreur absolue moyenne |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for domain, payload in summary["domains"].items():
        for row in payload["metrics"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        domain,
                        payload["product_code"],
                        row["mode"],
                        format_eur(row["observed_mean"]),
                        format_eur(row["simulated_mean"]),
                        f"{row['ratio_mean']:.2f}" if row["ratio_mean"] is not None else "n/a",
                        format_pct(row["bias_pct"]),
                        format_pct(row["mae_pct"]),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Lecture", ""])
    for domain, payload in summary["domains"].items():
        best = min(payload["metrics"], key=lambda row: row["mae_pct"] if row["mae_pct"] is not None else 1e9)
        lines.append(
            f"- {domain} / PF {payload['product_code']}: meilleur seuil `{best['mode']}`, "
            f"simule moyen {format_eur(best['simulated_mean'])} vs reel {format_eur(best['observed_mean'])}, "
            f"erreur moyenne {format_pct(best['mae_pct'])}."
        )
        missing = payload.get("components_without_price") or []
        if missing:
            lines.append(f"  Composants non valorises: {', '.join(missing)}.")
    return "\n".join(lines) + "\n"


def build_report(run_dir: Path, graph_path: Path, output_dir: Path) -> dict[str, Any]:
    graph = read_json(graph_path)
    component_universe = production_component_items(run_dir)
    prices = component_prices(graph, component_universe)
    stocks = read_input_stocks(run_dir)
    mrp_trace = read_mrp_trace(run_dir)

    summary: dict[str, Any] = {
        "schema_version": "etudecas.component_immobilized_stock_comparison.v1",
        "run_dir": str(run_dir),
        "graph": str(graph_path),
        "domains": {},
    }
    snapshot_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []

    for domain, meta in PRODUCTS.items():
        observed = read_observed_stock(single_source(meta["csv_pattern"]))
        rows: list[dict[str, Any]] = []
        first_details: dict[str, list[dict[str, Any]]] = {}
        for obs in observed:
            row = dict(obs)
            for mode in THRESHOLD_MODES:
                value, details = simulated_immobilized_value(
                    domain=domain,
                    day=int(obs["day"]),
                    mode=mode,
                    prices=prices[domain],
                    stocks=stocks,
                    mrp_trace=mrp_trace,
                )
                row[f"sim_{mode}"] = value
                if obs is observed[0]:
                    first_details[mode] = details[:12]
            rows.append(row)
            snapshot_rows.append({"domain": domain, "product_code": meta["code"], **row})
        metrics = [metric_row(rows, mode) for mode in THRESHOLD_MODES]
        for metric in metrics:
            metric_rows.append({"domain": domain, "product_code": meta["code"], **metric})
        for mode, details in first_details.items():
            for detail in details:
                component_rows.append({"domain": domain, "product_code": meta["code"], "mode": mode, **detail})

        summary["domains"][domain] = {
            "product_code": meta["code"],
            "factory": meta["factory"],
            "metrics": metrics,
            "components_without_price": [
                item_id for item_id, info in prices[domain].items() if info.get("unit_price") is None
            ],
            "price_info": prices[domain],
            "first_snapshot_top_components": first_details,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "component_immobilized_stock_comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "component_immobilized_stock_comparison.md").write_text(markdown_report(summary), encoding="utf-8")
    write_csv(output_dir / "component_immobilized_stock_snapshots.csv", snapshot_rows)
    write_csv(output_dir / "component_immobilized_stock_metrics.csv", metric_rows)
    write_csv(output_dir / "component_immobilized_stock_components.csv", component_rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or (args.run_dir / "reports")
    summary = build_report(args.run_dir, args.graph, output_dir)
    for domain, payload in summary["domains"].items():
        best = min(payload["metrics"], key=lambda row: row["mae_pct"] if row["mae_pct"] is not None else 1e9)
        print(
            f"{domain} PF {payload['product_code']}: best={best['mode']} "
            f"obs_mean={best['observed_mean']:.1f} sim_mean={best['simulated_mean']:.1f} "
            f"mae_pct={best['mae_pct'] * 100:.1f}%"
        )
    print(f"[OK] Wrote reports to {output_dir}")


if __name__ == "__main__":
    main()
