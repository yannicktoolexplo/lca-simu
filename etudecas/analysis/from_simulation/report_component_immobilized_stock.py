"""Compare source component stock snapshots with simulated component stock.

The source files in ``etudecas/data/source`` expose an aggregate column named
``Sum_Valeur totale du stock``. For calibration, that must be compared with
the simulated total component stock value on the same snapshot dates. The
surplus-vs-target indicators remain diagnostics, not the primary KPI.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis.component_immobilized_stock import (
    build_unit_values,
    discover_product_scopes,
    read_json,
)


SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "etudecas" / "analysis" / "from_simulation" / "result" / "component_immobilized_stock"
SIM_START_DATE = date(2025, 1, 1)

DEFAULT_PRODUCT_SOURCES = {
    # Current business convention given by the user. The source workbooks carry
    # some ambiguous labels, so the report keeps this mapping explicit.
    "268091": "Stock_Composants*_Cos.csv",
    "268967": "Stock_Composants*_Pharma.csv",
}

SIMULATED_METRIC_LABELS = {
    "stock_total_value": "Diagnostic: stock composant brut, PFI inclus si valorise",
    "stock_total_value_without_internal_rollup": "Stock composant valorise hors PFI/flux internes",
    "excess_over_90d": "Diagnostic: excedent au-dessus couverture 90j",
    "excess_vs_mrp_target": "Diagnostic: excedent au-dessus cible MRP",
}

ALIGNMENTS = {
    "same_day": 0,
    # Source photos are taken around 00:06 while simulation stocks are end of day.
    # This alignment tests whether the source photo should be read as previous
    # simulated day closing stock.
    "previous_day": -1,
}


@dataclass(frozen=True)
class Stats:
    count: int
    mean: float
    median: float
    minimum: float
    maximum: float


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(" ", "").replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def stats(values: list[float]) -> Stats:
    if not values:
        return Stats(0, 0.0, 0.0, 0.0, 0.0)
    return Stats(
        count=len(values),
        mean=statistics.mean(values),
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
        return list(csv.DictReader(handle, dialect=dialect))


def find_single_source(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one source file for {pattern}, found {len(matches)}: {matches}")
    return matches[0]


def default_graph_for_run(run_dir: Path) -> Path | None:
    candidates = [
        run_dir / "input_graph.json",
        run_dir.parent / "input_graph.json",
        run_dir.parent.parent / "input_graph.json",
    ]
    return next((path for path in candidates if path.exists()), None)


def read_observed_values(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(path):
        value_key = next((key for key in row if "valeur" in key.lower() or "stock" in key.lower()), "")
        date_key = next((key for key in row if "date" in key.lower()), "")
        if not value_key:
            continue
        snapshot_date: date | None = None
        if date_key and row.get(date_key):
            try:
                snapshot_date = datetime.fromisoformat(str(row[date_key])).date()
            except ValueError:
                snapshot_date = None
        day = (snapshot_date - SIM_START_DATE).days if snapshot_date else None
        rows.append(
            {
                "date": snapshot_date.isoformat() if snapshot_date else "",
                "day": day,
                "observed_value_eur": parse_float(row.get(value_key)),
            }
        )
    return [row for row in rows if row.get("day") is not None and int(row["day"]) >= 0]


def read_simulated_values(run_dir: Path, product_code: str) -> dict[str, dict[int, float]]:
    path = run_dir / "data" / "component_immobilized_stock_daily.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing simulated artifact: {path}")
    by_metric: dict[str, dict[int, float]] = {}
    for row in read_csv_rows(path):
        if str(row.get("product_code") or "") != str(product_code):
            continue
        mode = str(row.get("threshold_mode") or "")
        if not mode:
            continue
        day = int(parse_float(row.get("day")))
        if mode == "target_stock":
            by_metric.setdefault("stock_total_value", {})[day] = max(0.0, parse_float(row.get("stock_value_eur")))
            by_metric.setdefault("excess_vs_mrp_target", {})[day] = max(
                0.0,
                parse_float(row.get("immobilized_stock_value_eur")),
            )
        elif mode == "demand_90d":
            by_metric.setdefault("excess_over_90d", {})[day] = max(
                0.0,
                parse_float(row.get("immobilized_stock_value_eur")),
            )

    component_path = run_dir / "data" / "component_immobilized_stock_components_daily.csv"
    if component_path.exists():
        without_internal: dict[int, float] = {}
        for row in read_csv_rows(component_path):
            if str(row.get("product_code") or "") != str(product_code):
                continue
            if str(row.get("threshold_mode") or "") != "target_stock":
                continue
            source = str(row.get("value_source") or "")
            if source in {"internal_bom_rollup", "internal_transfer_bom_rollup"}:
                continue
            day = int(parse_float(row.get("day")))
            without_internal[day] = without_internal.get(day, 0.0) + max(
                0.0,
                parse_float(row.get("stock_value_eur")),
            )
        if without_internal:
            by_metric["stock_total_value_without_internal_rollup"] = without_internal
    return by_metric


def read_component_values(
    run_dir: Path,
    product_code: str,
    *,
    exclude_internal_rollup: bool = True,
) -> list[dict[str, Any]]:
    path = run_dir / "data" / "component_immobilized_stock_components_daily.csv"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(path):
        if str(row.get("product_code") or "") != str(product_code):
            continue
        if str(row.get("threshold_mode") or "") != "target_stock":
            continue
        if exclude_internal_rollup and str(row.get("value_source") or "") in {
            "internal_bom_rollup",
            "internal_transfer_bom_rollup",
        }:
            continue
        rows.append(
            {
                "day": int(parse_float(row.get("day"))),
                "product_code": str(product_code),
                "node_id": row.get("node_id") or "",
                "component_item_id": row.get("component_item_id") or "",
                "stock_qty": parse_float(row.get("stock_qty")),
                "unit_value_eur": parse_float(row.get("unit_value_eur")),
                "stock_value_eur": parse_float(row.get("stock_value_eur")),
                "value_source": row.get("value_source") or "",
            }
        )
    return rows


def read_component_counts(run_dir: Path, product_code: str) -> dict[int, dict[str, float]]:
    path = run_dir / "data" / "component_immobilized_stock_daily.csv"
    counts: dict[int, dict[str, float]] = {}
    if not path.exists():
        return counts
    for row in read_csv_rows(path):
        if str(row.get("product_code") or "") != str(product_code):
            continue
        if str(row.get("threshold_mode") or "") != "target_stock":
            continue
        counts[int(parse_float(row.get("day")))] = {
            "component_count": parse_float(row.get("component_count")),
            "priced_component_count": parse_float(row.get("priced_component_count")),
        }
    return counts


def read_input_stock_series(run_dir: Path) -> dict[tuple[str, str], dict[int, dict[str, float]]]:
    path = run_dir / "data" / "production_input_stocks_daily.csv"
    series: dict[tuple[str, str], dict[int, dict[str, float]]] = {}
    if not path.exists():
        return series
    for row in read_csv_rows(path):
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(parse_float(row.get("day")))
        series.setdefault((node_id, item_id), {})[day] = {
            "stock_before_production": parse_float(row.get("stock_before_production")),
            "stock_end_of_day": parse_float(row.get("stock_end_of_day")),
        }
    return series


def read_arrivals_by_component(run_dir: Path) -> dict[tuple[str, str], dict[str, float]]:
    path = run_dir / "data" / "production_input_replenishment_arrivals_daily.csv"
    out: dict[tuple[str, str], dict[str, float]] = {}
    if not path.exists():
        return out
    for row in read_csv_rows(path):
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        qty = parse_float(row.get("arrived_qty"))
        if not node_id or not item_id or qty <= 0:
            continue
        day = int(parse_float(row.get("day")))
        bucket = out.setdefault(
            (node_id, item_id),
            {"arrived_qty_total": 0.0, "arrival_days": 0.0, "first_arrival_day": float("inf"), "last_arrival_day": -1.0},
        )
        bucket["arrived_qty_total"] += qty
        bucket["arrival_days"] += 1.0
        bucket["first_arrival_day"] = min(bucket["first_arrival_day"], float(day))
        bucket["last_arrival_day"] = max(bucket["last_arrival_day"], float(day))
    return out


def read_order_quantities_by_component(run_dir: Path) -> dict[tuple[str, str], dict[str, float]]:
    path = run_dir / "data" / "mrp_orders_daily.csv"
    out: dict[tuple[str, str], dict[str, float]] = {}
    if not path.exists():
        return out
    for row in read_csv_rows(path):
        node_id = str(row.get("node_id") or row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        qty = parse_float(row.get("planned_receipt_qty")) or parse_float(row.get("release_qty"))
        if qty <= 0:
            continue
        order_type = str(row.get("order_type") or "")
        bucket = out.setdefault(
            (node_id, item_id),
            {
                "order_count": 0.0,
                "planned_receipt_qty_total": 0.0,
                "opening_order_qty": 0.0,
                "generated_mrp_qty": 0.0,
            },
        )
        bucket["order_count"] += 1.0
        bucket["planned_receipt_qty_total"] += qty
        if order_type.startswith("opening_"):
            bucket["opening_order_qty"] += qty
        else:
            bucket["generated_mrp_qty"] += qty
    return out


def component_flow_rows(run_dir: Path, contributors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stock_series = read_input_stock_series(run_dir)
    arrivals = read_arrivals_by_component(run_dir)
    orders = read_order_quantities_by_component(run_dir)
    unique_keys = sorted(
        {
            (
                str(row["product_code"]),
                str(row.get("component_item_id") or ""),
            )
            for row in contributors
            if row.get("component_item_id")
        }
    )
    # Use the contributor rows to recover the consuming node. The key is stable
    # because each product scope is attached to one factory in this case study.
    node_by_product_component: dict[tuple[str, str], str] = {}
    value_by_product_component: dict[tuple[str, str], float] = {}
    for row in contributors:
        key = (str(row["product_code"]), str(row.get("component_item_id") or ""))
        node_by_product_component[key] = str(row.get("node_id") or "")
        if str(row.get("alignment") or "") == "previous_day":
            value_by_product_component[key] = float(row.get("mean_stock_value_eur") or 0.0)

    rows: list[dict[str, Any]] = []
    for product_code, component_item_id in unique_keys:
        node_id = node_by_product_component.get((product_code, component_item_id), "")
        if not node_id:
            continue
        series = stock_series.get((node_id, component_item_id), {})
        if not series:
            continue
        days = sorted(series)
        first_day = days[0]
        last_day = days[-1]
        first = series[first_day]
        last = series[last_day]
        stock_end_values = [float(series[day]["stock_end_of_day"]) for day in days]
        arrival = arrivals.get((node_id, component_item_id), {})
        order = orders.get((node_id, component_item_id), {})
        start_stock = float(first["stock_before_production"])
        end_stock = float(last["stock_end_of_day"])
        arrived_total = float(arrival.get("arrived_qty_total") or 0.0)
        rows.append(
            {
                "product_code": product_code,
                "node_id": node_id,
                "component_item_id": component_item_id,
                "mean_stock_value_eur_previous_day": value_by_product_component.get((product_code, component_item_id), 0.0),
                "start_stock_qty": start_stock,
                "end_stock_qty": end_stock,
                "min_stock_qty": min(stock_end_values),
                "max_stock_qty": max(stock_end_values),
                "arrived_qty_total": arrived_total,
                "arrival_days": float(arrival.get("arrival_days") or 0.0),
                "first_arrival_day": "" if arrival.get("first_arrival_day") in (None, float("inf")) else int(arrival["first_arrival_day"]),
                "last_arrival_day": "" if not arrival else int(arrival.get("last_arrival_day") or 0.0),
                "approx_consumed_qty": start_stock + arrived_total - end_stock,
                "order_count": float(order.get("order_count") or 0.0),
                "planned_receipt_qty_total": float(order.get("planned_receipt_qty_total") or 0.0),
                "opening_order_qty": float(order.get("opening_order_qty") or 0.0),
                "generated_mrp_qty": float(order.get("generated_mrp_qty") or 0.0),
            }
        )
    rows.sort(key=lambda row: (str(row["product_code"]), -float(row["mean_stock_value_eur_previous_day"])))
    return rows


def paired_snapshot_rows(
    *,
    product_code: str,
    observed_rows: list[dict[str, Any]],
    simulated_by_metric: dict[str, dict[int, float]],
    direct_metric_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for alignment, offset in ALIGNMENTS.items():
        for metric_id, values_by_day in simulated_by_metric.items():
            for observed in observed_rows:
                source_day = int(observed["day"])
                sim_day = source_day + offset
                if sim_day not in values_by_day:
                    continue
                observed_value = float(observed["observed_value_eur"])
                simulated_value = float(values_by_day[sim_day])
                gap = simulated_value - observed_value
                rows.append(
                    {
                        "product_code": product_code,
                        "alignment": alignment,
                        "metric_id": metric_id,
                        "metric_label": SIMULATED_METRIC_LABELS.get(metric_id, metric_id),
                        "comparison_role": "direct_real_like" if metric_id == direct_metric_id else "diagnostic",
                        "source_date": observed["date"],
                        "source_day": source_day,
                        "sim_day": sim_day,
                        "observed_value_eur": observed_value,
                        "simulated_value_eur": simulated_value,
                        "gap_eur": gap,
                        "gap_pct": 100.0 * gap / observed_value if observed_value else 0.0,
                    }
                )
    return rows


def comparison_rows(
    *,
    product_code: str,
    observed_rows: list[dict[str, Any]],
    simulated_by_metric: dict[str, dict[int, float]],
    pairs: list[dict[str, Any]],
    component_counts: dict[int, dict[str, float]],
    direct_metric_id: str,
) -> list[dict[str, Any]]:
    observed_stats = stats([float(row["observed_value_eur"]) for row in observed_rows])
    rows: list[dict[str, Any]] = []
    for alignment in ALIGNMENTS:
        for metric_id, sim_by_day in sorted(simulated_by_metric.items()):
            selected_pairs = [
                row for row in pairs if row["alignment"] == alignment and row["metric_id"] == metric_id
            ]
            if not selected_pairs:
                continue
            sampled = [float(row["simulated_value_eur"]) for row in selected_pairs]
            gaps = [float(row["gap_eur"]) for row in selected_pairs]
            sim_full = list(sim_by_day.values())
            sim_stats = stats(sampled)
            daily_stats = stats([float(value) for value in sim_full])
            mean_gap = statistics.mean(gaps)
            mae = statistics.mean(abs(gap) for gap in gaps)
            matched_days = [int(row["sim_day"]) for row in selected_pairs]
            count_rows = [component_counts[day] for day in matched_days if day in component_counts]
            component_count = statistics.mean([row["component_count"] for row in count_rows]) if count_rows else 0.0
            priced_count = statistics.mean([row["priced_component_count"] for row in count_rows]) if count_rows else 0.0
            rows.append(
                {
                    "product_code": product_code,
                    "alignment": alignment,
                    "metric_id": metric_id,
                    "metric_label": SIMULATED_METRIC_LABELS.get(metric_id, metric_id),
                    "comparison_role": "direct_real_like" if metric_id == direct_metric_id else "diagnostic",
                    "observed_count": observed_stats.count,
                    "matched_count": len(selected_pairs),
                    "observed_mean_eur": observed_stats.mean,
                    "observed_median_eur": observed_stats.median,
                    "observed_min_eur": observed_stats.minimum,
                    "observed_max_eur": observed_stats.maximum,
                    "simulated_snapshot_mean_eur": sim_stats.mean,
                    "simulated_snapshot_median_eur": sim_stats.median,
                    "simulated_snapshot_min_eur": sim_stats.minimum,
                    "simulated_snapshot_max_eur": sim_stats.maximum,
                    "simulated_daily_mean_eur": daily_stats.mean,
                    "mean_gap_eur": mean_gap,
                    "mean_gap_pct": 100.0 * mean_gap / observed_stats.mean if observed_stats.mean else 0.0,
                    "mae_eur": mae,
                    "mae_pct": 100.0 * mae / observed_stats.mean if observed_stats.mean else 0.0,
                    "sim_above_observed_snapshots": sum(1 for row in selected_pairs if float(row["gap_eur"]) > 0),
                    "mean_component_count": component_count,
                    "mean_priced_component_count": priced_count,
                }
            )
    rows.sort(
        key=lambda row: (
            0 if row["comparison_role"] == "direct_real_like" else 1,
            str(row["alignment"]),
            abs(float(row["mean_gap_eur"])),
        )
    )
    return rows


def component_contributor_rows(
    *,
    product_code: str,
    observed_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    alignment: str,
) -> list[dict[str, Any]]:
    wanted_days = {int(row["day"]) + ALIGNMENTS[alignment] for row in observed_rows}
    by_component: dict[str, list[dict[str, Any]]] = {}
    for row in component_rows:
        if int(row["day"]) not in wanted_days:
            continue
        by_component.setdefault(str(row["component_item_id"]), []).append(row)
    totals: list[dict[str, Any]] = []
    total_value = 0.0
    for component, rows in by_component.items():
        values = [float(row["stock_value_eur"]) for row in rows]
        stock_qty = [float(row["stock_qty"]) for row in rows]
        unit_values = [float(row["unit_value_eur"]) for row in rows if float(row["unit_value_eur"]) > 0]
        mean_value = statistics.mean(values) if values else 0.0
        total_value += mean_value
        totals.append(
            {
                "product_code": product_code,
                "alignment": alignment,
                "node_id": next((str(row["node_id"]) for row in rows if row.get("node_id")), ""),
                "component_item_id": component,
                "mean_stock_qty": statistics.mean(stock_qty) if stock_qty else 0.0,
                "unit_value_eur": statistics.median(unit_values) if unit_values else 0.0,
                "mean_stock_value_eur": mean_value,
                "max_stock_value_eur": max(values) if values else 0.0,
                "value_source": next((str(row["value_source"]) for row in rows if row.get("value_source")), ""),
                "snapshot_count": len(rows),
            }
        )
    for row in totals:
        row["share_of_simulated_stock_pct"] = (
            100.0 * float(row["mean_stock_value_eur"]) / total_value if total_value else 0.0
        )
    totals.sort(key=lambda row: -float(row["mean_stock_value_eur"]))
    return totals


def unpriced_components(graph_path: Path | None, product_codes: list[str]) -> list[dict[str, Any]]:
    if not graph_path or not graph_path.exists():
        return []
    graph = read_json(graph_path)
    scopes = {scope.product_code: scope for scope in discover_product_scopes(graph)}
    unit_values = build_unit_values(graph)
    rows: list[dict[str, Any]] = []
    for product_code in product_codes:
        scope = scopes.get(str(product_code))
        if not scope:
            continue
        for item_id in sorted(scope.component_items):
            info = unit_values.get((scope.factory, item_id))
            if info:
                continue
            rows.append(
                {
                    "product_code": product_code,
                    "node_id": scope.factory,
                    "product_item_id": scope.product_item,
                    "component_item_id": item_id,
                    "issue": "missing_or_fallback_unit_value",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def format_money(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def format_pct(value: float) -> str:
    return f"{value:.1f}%"


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    run_dir: Path,
    graph_path: Path | None,
    sources: dict[str, Path],
    contributors: list[dict[str, Any]],
    flows: list[dict[str, Any]],
    missing_price_rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    direct_rows = [
        row for row in rows if row["comparison_role"] == "direct_real_like" and row["alignment"] == "previous_day"
    ]
    fallback_direct_rows = [
        row for row in rows if row["comparison_role"] == "direct_real_like" and row["alignment"] == "same_day"
    ]
    lines = [
        "# Stock composants immobilise - verification source vs simulation",
        "",
        f"- Run: `{run_dir}`",
        f"- Graphe: `{graph_path}`" if graph_path else "- Graphe: non fourni",
        f"- Produits compares: {', '.join(sorted(sources)) or 'n/a'}",
        "",
        "## Contrat de comparaison",
        "",
        "- Source de verite: fichiers de `etudecas/data/source`.",
        "- Les CSV source exposent `Sum_Valeur totale du stock`: on compare donc le stock composant physique valorise simule.",
        "- Les PFI et flux internes ne sont pas valorises dans la ligne principale; une ligne brute reste disponible en diagnostic si un roll-up interne existe.",
        "- Les commandes ouvertes ne sont pas ajoutees au stock tant qu'elles ne sont pas receptionnees.",
        "- Les diagnostics de surstock (`90j`, `cible MRP`) servent a expliquer, pas a calibrer directement.",
        "- L'alignement `previous_day` est prioritaire car les photos DMP sont vers 00:06 et la simulation stocke des fins de jour.",
        "- Convention produit utilisee ici: `268091 -> Cos`, `268967 -> Pharma`; les workbooks source ont des libelles ambigus, donc ce mapping reste explicite.",
        "",
        "## Resultat principal",
        "",
        "| Produit | Alignement | Reel moyen | Simulation moyenne aux photos | Ecart | Ecart % | MAE | MAE % | Sim > reel | Composants valorises |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in direct_rows or fallback_direct_rows:
        lines.append(
            "| {product_code} | {alignment} | {real} | {sim} | {gap} | {gap_pct} | {mae} | {mae_pct} | {above}/{matched} | {priced:.1f}/{count:.1f} |".format(
                product_code=row["product_code"],
                alignment=row["alignment"],
                real=format_money(float(row["observed_mean_eur"])),
                sim=format_money(float(row["simulated_snapshot_mean_eur"])),
                gap=format_money(float(row["mean_gap_eur"])),
                gap_pct=format_pct(float(row["mean_gap_pct"])),
                mae=format_money(float(row["mae_eur"])),
                mae_pct=format_pct(float(row["mae_pct"])),
                above=int(row["sim_above_observed_snapshots"]),
                matched=int(row["matched_count"]),
                priced=float(row["mean_priced_component_count"]),
                count=float(row["mean_component_count"]),
            )
        )
    lines.extend(
        [
            "",
            "## Diagnostics disponibles",
            "",
            "| Produit | Alignement | Lecture simulation | Role | Reel moyen | Simulation moyenne | Ecart | Ecart % |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| {product_code} | {alignment} | {metric_label} | {role} | {real} | {sim} | {gap} | {gap_pct} |".format(
                product_code=row["product_code"],
                alignment=row["alignment"],
                metric_label=row["metric_label"],
                role="direct" if row["comparison_role"] == "direct_real_like" else "diagnostic",
                real=format_money(float(row["observed_mean_eur"])),
                sim=format_money(float(row["simulated_snapshot_mean_eur"])),
                gap=format_money(float(row["mean_gap_eur"])),
                gap_pct=format_pct(float(row["mean_gap_pct"])),
            )
        )
    lines.extend(["", "## Top composants expliquant le stock simule", ""])
    for product_code in sorted(sources):
        top = [row for row in contributors if row["product_code"] == product_code and row["alignment"] == "previous_day"][:10]
        lines.extend(
            [
                f"### {product_code}",
                "",
                "| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |",
                "| --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for row in top:
            lines.append(
                "| {component} | {value} | {share} | {qty:,.1f} | {unit:.6g} | {source} |".format(
                    component=str(row["component_item_id"]).replace("item:", ""),
                    value=format_money(float(row["mean_stock_value_eur"])),
                    share=format_pct(float(row["share_of_simulated_stock_pct"])),
                    qty=float(row["mean_stock_qty"]),
                    unit=float(row["unit_value_eur"]),
                    source=row["value_source"] or "n/a",
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Flux des composants principaux",
            "",
            "Lecture: si les arrivees et commandes generees depassent la consommation approximative, le surplus vient de la politique MRP/lotification ou des commandes ouvertes, pas du stock J0 seul.",
            "",
        ]
    )
    for product_code in sorted(sources):
        top_flows = [row for row in flows if row["product_code"] == product_code][:10]
        lines.extend(
            [
                f"### {product_code}",
                "",
                "| Composant | Stock debut | Arrivees | Conso approx. | Stock fin | Commandes totales | Ouvertes | Generees MRP |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in top_flows:
            lines.append(
                "| {component} | {start:,.1f} | {arrived:,.1f} | {consumed:,.1f} | {end:,.1f} | {ordered:,.1f} | {opening:,.1f} | {generated:,.1f} |".format(
                    component=str(row["component_item_id"]).replace("item:", ""),
                    start=float(row["start_stock_qty"]),
                    arrived=float(row["arrived_qty_total"]),
                    consumed=float(row["approx_consumed_qty"]),
                    end=float(row["end_stock_qty"]),
                    ordered=float(row["planned_receipt_qty_total"]),
                    opening=float(row["opening_order_qty"]),
                    generated=float(row["generated_mrp_qty"]),
                )
            )
        lines.append("")
    if missing_price_rows:
        lines.extend(
            [
                "## Composants non valorises",
                "",
                "Ces lignes sont dans le BOM mais n'ont pas de prix fiable exploitable dans le graphe. Elles peuvent creer un ecart de scope si la source finance les inclut.",
                "",
                "| Produit | Noeud | Composant | Probleme |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in missing_price_rows:
            lines.append(
                f"| {row['product_code']} | {row['node_id']} | {str(row['component_item_id']).replace('item:', '')} | {row['issue']} |"
            )
    lines.extend(["", "## Sources", ""])
    for product_code, source in sorted(sources.items()):
        lines.append(f"- {product_code}: `{source}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(
    *,
    run_dir: Path,
    product_codes: list[str],
    output_dir: Path,
    graph_path: Path | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    contributor_rows: list[dict[str, Any]] = []
    sources: dict[str, Path] = {}
    product_codes = [str(code) for code in product_codes]
    for product_code in product_codes:
        pattern = DEFAULT_PRODUCT_SOURCES.get(product_code)
        if not pattern:
            continue
        source = find_single_source(pattern)
        sources[product_code] = source
        observed = read_observed_values(source)
        simulated = read_simulated_values(run_dir, product_code)
        direct_metric_id = (
            "stock_total_value_without_internal_rollup"
            if "stock_total_value_without_internal_rollup" in simulated
            else "stock_total_value"
        )
        product_pairs = paired_snapshot_rows(
            product_code=product_code,
            observed_rows=observed,
            simulated_by_metric=simulated,
            direct_metric_id=direct_metric_id,
        )
        counts = read_component_counts(run_dir, product_code)
        paired_rows.extend(product_pairs)
        rows.extend(
            comparison_rows(
                product_code=product_code,
                observed_rows=observed,
                simulated_by_metric=simulated,
                pairs=product_pairs,
                component_counts=counts,
                direct_metric_id=direct_metric_id,
            )
        )
        component_rows = read_component_values(run_dir, product_code, exclude_internal_rollup=True)
        for alignment in ALIGNMENTS:
            contributor_rows.extend(
                component_contributor_rows(
                    product_code=product_code,
                    observed_rows=observed,
                    component_rows=component_rows,
                    alignment=alignment,
                )
            )

    missing_price_rows = unpriced_components(graph_path, product_codes)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "component_immobilized_stock_comparison.csv"
    md_path = output_dir / "component_immobilized_stock_comparison.md"
    json_path = output_dir / "component_immobilized_stock_comparison.json"
    snapshots_path = output_dir / "component_immobilized_stock_snapshot_pairs.csv"
    contributors_path = output_dir / "component_immobilized_stock_component_contributors.csv"
    flows_path = output_dir / "component_immobilized_stock_component_flows.csv"
    missing_price_path = output_dir / "component_immobilized_stock_unpriced_components.csv"
    flow_rows = component_flow_rows(run_dir, contributor_rows)
    write_csv(csv_path, rows)
    write_csv(snapshots_path, paired_rows)
    write_csv(contributors_path, contributor_rows)
    write_csv(flows_path, flow_rows)
    write_csv(missing_price_path, missing_price_rows)
    write_markdown(
        md_path,
        rows,
        run_dir=run_dir,
        graph_path=graph_path,
        sources=sources,
        contributors=contributor_rows,
        flows=flow_rows,
        missing_price_rows=missing_price_rows,
    )
    payload = {
        "schema_version": "etudecas.component_immobilized_stock_comparison.v2",
        "run_dir": str(run_dir.resolve(strict=False)),
        "graph": str(graph_path.resolve(strict=False)) if graph_path else "",
        "sources": {key: str(value.resolve(strict=False)) for key, value in sources.items()},
        "rows": rows,
        "paired_snapshot_rows": paired_rows,
        "component_contributors": contributor_rows,
        "component_flows": flow_rows,
        "unpriced_components": missing_price_rows,
        "best_direct_by_product": {
            product_code: next(
                (
                    row
                    for row in rows
                    if str(row["product_code"]) == product_code
                    and row["comparison_role"] == "direct_real_like"
                    and row["alignment"] == "previous_day"
                ),
                None,
            )
            for product_code in sorted({str(row["product_code"]) for row in rows})
        },
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "rows": len(rows),
        "snapshot_rows": len(paired_rows),
        "contributors": len(contributor_rows),
        "flows": len(flow_rows),
        "csv": str(csv_path),
        "snapshots": str(snapshots_path),
        "contributors_csv": str(contributors_path),
        "flows_csv": str(flows_path),
        "markdown": str(md_path),
        "json": str(json_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--product-code", action="append", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    graph_path = args.graph or default_graph_for_run(args.run_dir)
    product_codes = args.product_code or sorted(DEFAULT_PRODUCT_SOURCES)
    summary = build_report(
        run_dir=args.run_dir,
        graph_path=graph_path,
        product_codes=product_codes,
        output_dir=args.output_dir,
    )
    print(
        "[OK] component stock source comparison "
        f"rows={summary['rows']} snapshots={summary['snapshot_rows']} markdown={summary['markdown']}"
    )


if __name__ == "__main__":
    main()
