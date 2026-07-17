"""Build component stock valuation artifacts from a simulation run.

This module separates three business notions that were previously mixed in
ad-hoc audits:

* total component stock: physical stock available at the factory;
* useful component stock: stock justified by the selected MRP threshold;
* immobilized component stock: stock above the useful threshold, valued in EUR.

The calculation is intentionally a post-processing step over standard run CSVs.
It does not change the simulation dynamics.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


THRESHOLD_MODES = (
    "target_stock",
    "coverage",
    "safety_plus_coverage",
    "max_safety_coverage",
    "demand_90d",
    "demand_180d",
)


@dataclass(frozen=True)
class ProductScope:
    factory: str
    product_item: str
    product_code: str
    component_items: frozenset[str]


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _norm_item_code(item_id: str) -> str:
    text = str(item_id or "").strip()
    if text.startswith("item:"):
        text = text.split(":", 1)[1]
    return text


def _norm_uom(uom: Any) -> str:
    text = str(uom or "").strip().upper().replace(".", "")
    if text in {"ZUN", "UN", "UNIT", "UNITE", "UNITES"}:
        return "UN"
    if text in {"G", "GR", "GRAMME", "GRAMMES"}:
        return "G"
    if text in {"KG", "KILO", "KILOGRAMME", "KILOGRAMMES"}:
        return "KG"
    if text in {"M", "ML", "METER", "METRE", "METRES"}:
        return "M"
    return text


def _convert_qty(qty: float, from_uom: Any, to_uom: Any) -> float | None:
    src = _norm_uom(from_uom)
    dst = _norm_uom(to_uom)
    if not src or not dst or src == dst:
        return qty
    mass_to_g = {"G": 1.0, "KG": 1000.0}
    if src in mass_to_g and dst in mass_to_g:
        return qty * mass_to_g[src] / mass_to_g[dst]
    return None


def _unit_value_from_state(state: dict[str, Any]) -> float | None:
    holding = state.get("holding_cost") if isinstance(state.get("holding_cost"), dict) else {}
    source = str(holding.get("source") or "").lower()
    if holding.get("is_default") or "global_value_median_fallback" in source or "fallback" in source:
        return None
    value = holding.get("unit_value_basis")
    parsed = parse_float(value, default=float("nan"))
    if parsed == parsed and parsed > 0:
        return parsed
    return None


def _unit_value_from_edge(edge: dict[str, Any]) -> float | None:
    terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
    source = str(terms.get("source") or "").lower()
    if terms.get("is_default") or "global_value_median_fallback" in source or "fallback" in source:
        return None
    sell_price = parse_float(terms.get("sell_price"), default=float("nan"))
    price_base = parse_float(terms.get("price_base"), default=1.0) or 1.0
    if sell_price == sell_price and sell_price > 0:
        return sell_price / price_base
    return None


def _selected_unit_info(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    values = [float(row["unit_value_eur"]) for row in rows if parse_float(row.get("unit_value_eur")) > 0]
    if not values:
        return None
    preferred = [row for row in rows if row.get("source") == "inventory_state_unit_value_basis"]
    preferred_values = [float(row["unit_value_eur"]) for row in preferred if parse_float(row.get("unit_value_eur")) > 0]
    selected = preferred_values or values
    return {
        "unit_value_eur": statistics.median(selected),
        "source": "inventory_state_unit_value_basis" if preferred_values else str((preferred or rows)[0].get("source") or ""),
        "source_count": len(rows),
        "uom": _norm_uom((preferred or rows)[0].get("uom") or ""),
    }


def _add_internal_bom_rollups(
    graph: dict[str, Any],
    by_pair: dict[tuple[str, str], list[dict[str, Any]]],
) -> None:
    """Value internal transfer-price-zero items from their upstream BOM.

    FIA/Relations_acteurs often expose a zero price for intra-network transfers
    such as Gaillac -> Gien.  That is a transfer price, not a zero economic
    value.  When the producing site has a BOM and the input material is valued,
    derive the output item unit value from the input material cost.
    """

    changed = True
    for _ in range(8):
        if not changed:
            break
        changed = False
        for node in graph.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "")
            if not node_id:
                continue
            for process in node.get("processes") or []:
                if not isinstance(process, dict):
                    continue
                outputs = process.get("outputs") if isinstance(process.get("outputs"), list) else []
                inputs = process.get("inputs") if isinstance(process.get("inputs"), list) else []
                if not outputs or not inputs:
                    continue
                output = outputs[0] if isinstance(outputs[0], dict) else {}
                output_item = str(output.get("item_id") or "")
                if not output_item or by_pair.get((node_id, output_item)):
                    continue
                batch_size = parse_float(process.get("batch_size"), default=0.0)
                batch_uom = process.get("batch_size_unit") or ""
                output_uom = _norm_uom(batch_uom)
                if batch_size <= 0 or not output_uom:
                    continue
                total_input_cost = 0.0
                complete = True
                for component in inputs:
                    if not isinstance(component, dict):
                        continue
                    input_item = str(component.get("item_id") or "")
                    unit_info = _selected_unit_info(by_pair.get((node_id, input_item), []))
                    if not input_item or not unit_info:
                        complete = False
                        break
                    ratio = parse_float(component.get("ratio_per_batch"), default=0.0)
                    ratio_uom = component.get("ratio_unit") or unit_info.get("uom") or ""
                    converted = _convert_qty(ratio, ratio_uom, unit_info.get("uom") or ratio_uom)
                    if ratio <= 0 or converted is None:
                        complete = False
                        break
                    total_input_cost += converted * float(unit_info["unit_value_eur"])
                output_qty = _convert_qty(batch_size, batch_uom, output_uom)
                if complete and output_qty and output_qty > 0 and total_input_cost > 0:
                    by_pair[(node_id, output_item)].append(
                        {
                            "unit_value_eur": total_input_cost / output_qty,
                            "source": "internal_bom_rollup",
                            "source_count": 1,
                            "uom": output_uom,
                        }
                    )
                    changed = True

    # Propagate internally produced value over zero-price internal transfer edges.
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        sell_price = parse_float(terms.get("sell_price"), default=0.0)
        if not src or not dst or sell_price > 0:
            continue
        for item_id in edge.get("items") if isinstance(edge.get("items"), list) else []:
            item_id = str(item_id or "")
            if not item_id or by_pair.get((dst, item_id)):
                continue
            source_info = _selected_unit_info(by_pair.get((src, item_id), []))
            if not source_info:
                continue
            by_pair[(dst, item_id)].append(
                {
                    "unit_value_eur": source_info["unit_value_eur"],
                    "source": "internal_transfer_bom_rollup",
                    "source_count": 1,
                    "uom": source_info.get("uom") or _norm_uom(terms.get("quantity_unit")),
                }
            )


def discover_product_scopes(graph: dict[str, Any], *, factory_filter: set[str] | None = None) -> list[ProductScope]:
    """Discover factory PF -> BOM component scopes from graph processes."""

    scopes: list[ProductScope] = []
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        factory = str(node.get("id") or "")
        if not factory or (factory_filter and factory not in factory_filter):
            continue
        if str(node.get("type") or "") != "factory":
            continue
        for process in node.get("processes") or []:
            if not isinstance(process, dict):
                continue
            outputs = process.get("outputs") if isinstance(process.get("outputs"), list) else []
            inputs = process.get("inputs") if isinstance(process.get("inputs"), list) else []
            if not outputs or not inputs:
                continue
            output_item = str(outputs[0].get("item_id") or "")
            if not output_item:
                continue
            component_items = frozenset(
                str(row.get("item_id") or "")
                for row in inputs
                if isinstance(row, dict) and str(row.get("item_id") or "")
            )
            if not component_items:
                continue
            scopes.append(
                ProductScope(
                    factory=factory,
                    product_item=output_item,
                    product_code=_norm_item_code(output_item),
                    component_items=component_items,
                )
            )
    return scopes


def build_unit_values(graph: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Return median unit values by (factory, item), preferring inventory state values.

    Direct supplier prices remain the first source of truth.  Internal transfer
    prices equal to zero are then valued with BOM roll-up when upstream
    material prices are available.
    """

    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        for state in ((node.get("inventory") or {}).get("states") or []):
            if not isinstance(state, dict):
                continue
            item_id = str(state.get("item_id") or "")
            unit_value = _unit_value_from_state(state)
            if node_id and item_id and unit_value is not None:
                by_pair[(node_id, item_id)].append(
                    {
                        "unit_value_eur": unit_value,
                        "source": "inventory_state_unit_value_basis",
                        "uom": state.get("uom") or "",
                    }
                )

    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        dst = str(edge.get("to") or "")
        items = edge.get("items") if isinstance(edge.get("items"), list) else []
        unit_value = _unit_value_from_edge(edge)
        if not dst or unit_value is None:
            continue
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        for item_id in items:
            if item_id:
                by_pair[(dst, str(item_id))].append(
                    {
                        "unit_value_eur": unit_value,
                        "source": "transport_order_terms",
                        "uom": terms.get("quantity_unit") or "",
                    }
                )

    _add_internal_bom_rollups(graph, by_pair)

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, rows in by_pair.items():
        selected = _selected_unit_info(rows)
        if not selected:
            continue
        if selected["source"] == "transport_order_terms":
            selected["source"] = "transport_order_terms_median"
        out[key] = selected
    return out


def threshold_value(row: dict[str, str], mode: str) -> float:
    coverage = parse_float(row.get("coverage_target_qty"))
    safety = parse_float(row.get("safety_stock_qty"))
    soft = parse_float(row.get("soft_safety_target_qty"))
    target = parse_float(row.get("target_stock_qty"))
    demand_signal = parse_float(row.get("target_demand_signal_qty"))
    if mode == "target_stock":
        return target
    if mode == "coverage":
        return coverage
    if mode == "safety_plus_coverage":
        return coverage + safety
    if mode == "max_safety_coverage":
        return max(coverage, safety, soft)
    if mode == "demand_90d":
        return demand_signal * 90.0
    if mode == "demand_180d":
        return demand_signal * 180.0
    raise ValueError(f"Unknown threshold mode: {mode}")


def _stock_by_key(rows: list[dict[str, str]]) -> dict[tuple[int, str, str], dict[str, str]]:
    out: dict[tuple[int, str, str], dict[str, str]] = {}
    for row in rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        out[(int(parse_float(row.get("day"))), node_id, item_id)] = row
    return out


def _mrp_by_key(rows: list[dict[str, str]]) -> dict[tuple[int, str, str], dict[str, str]]:
    out: dict[tuple[int, str, str], dict[str, str]] = {}
    for row in rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        out[(int(parse_float(row.get("day"))), node_id, item_id)] = row
    return out


def build_component_immobilized_stock_artifacts(
    *,
    run_dir: Path,
    graph_path: Path,
    output_dir: Path | None = None,
    threshold_modes: tuple[str, ...] = THRESHOLD_MODES,
) -> dict[str, Any]:
    """Build daily and summary CSVs for component stock valuation."""

    output_dir = output_dir or run_dir / "data"
    graph = read_json(graph_path)
    scopes = discover_product_scopes(graph)
    unit_values = build_unit_values(graph)
    stock_rows = _stock_by_key(read_csv_rows(run_dir / "data" / "production_input_stocks_daily.csv"))
    mrp_rows = _mrp_by_key(read_csv_rows(run_dir / "data" / "mrp_trace_daily.csv"))

    daily_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    summary_acc: dict[tuple[str, str, str, str], list[dict[str, float]]] = defaultdict(list)

    all_days = sorted({key[0] for key in stock_rows} | {key[0] for key in mrp_rows})
    for scope in scopes:
        for day in all_days:
            for mode in threshold_modes:
                total_value = 0.0
                useful_value = 0.0
                immobilized_value = 0.0
                total_qty_rows = 0
                priced_components = 0
                for item_id in sorted(scope.component_items):
                    stock = stock_rows.get((day, scope.factory, item_id))
                    mrp = mrp_rows.get((day, scope.factory, item_id))
                    if not stock and not mrp:
                        continue
                    total_qty_rows += 1
                    stock_qty = parse_float((stock or {}).get("stock_end_of_day"))
                    useful_qty = max(0.0, threshold_value(mrp or {}, mode))
                    immobilized_qty = max(stock_qty - useful_qty, 0.0)
                    unit_info = unit_values.get((scope.factory, item_id), {})
                    unit_value = unit_info.get("unit_value_eur")
                    if unit_value is None:
                        continue
                    priced_components += 1
                    item_total_value = stock_qty * float(unit_value)
                    item_useful_value = min(stock_qty, useful_qty) * float(unit_value)
                    item_immobilized_value = immobilized_qty * float(unit_value)
                    total_value += item_total_value
                    useful_value += item_useful_value
                    immobilized_value += item_immobilized_value
                    detail = {
                        "day": day,
                        "node_id": scope.factory,
                        "product_item_id": scope.product_item,
                        "product_code": scope.product_code,
                        "component_item_id": item_id,
                        "threshold_mode": mode,
                        "stock_qty": stock_qty,
                        "useful_qty": useful_qty,
                        "immobilized_qty": immobilized_qty,
                        "unit_value_eur": unit_value,
                        "stock_value_eur": item_total_value,
                        "useful_value_eur": item_useful_value,
                        "immobilized_value_eur": item_immobilized_value,
                        "value_source": unit_info.get("source", ""),
                    }
                    detail_rows.append(detail)
                    summary_acc[(scope.factory, scope.product_item, item_id, mode)].append(
                        {
                            "stock_value_eur": item_total_value,
                            "useful_value_eur": item_useful_value,
                            "immobilized_value_eur": item_immobilized_value,
                            "stock_qty": stock_qty,
                            "useful_qty": useful_qty,
                            "immobilized_qty": immobilized_qty,
                        }
                    )
                daily_rows.append(
                    {
                        "day": day,
                        "node_id": scope.factory,
                        "product_item_id": scope.product_item,
                        "product_code": scope.product_code,
                        "threshold_mode": mode,
                        "stock_value_eur": total_value,
                        "useful_stock_value_eur": useful_value,
                        "immobilized_stock_value_eur": immobilized_value,
                        "component_count": total_qty_rows,
                        "priced_component_count": priced_components,
                    }
                )

    summary_rows: list[dict[str, Any]] = []
    for (node_id, product_item_id, component_item_id, mode), values in summary_acc.items():
        def col(name: str) -> list[float]:
            return [float(row[name]) for row in values]

        unit_info = unit_values.get((node_id, component_item_id), {})
        summary_rows.append(
            {
                "node_id": node_id,
                "product_item_id": product_item_id,
                "product_code": _norm_item_code(product_item_id),
                "component_item_id": component_item_id,
                "threshold_mode": mode,
                "unit_value_eur": unit_info.get("unit_value_eur", ""),
                "value_source": unit_info.get("source", ""),
                "mean_stock_value_eur": statistics.mean(col("stock_value_eur")),
                "mean_useful_stock_value_eur": statistics.mean(col("useful_value_eur")),
                "mean_immobilized_stock_value_eur": statistics.mean(col("immobilized_value_eur")),
                "max_immobilized_stock_value_eur": max(col("immobilized_value_eur")),
                "mean_stock_qty": statistics.mean(col("stock_qty")),
                "mean_useful_qty": statistics.mean(col("useful_qty")),
                "mean_immobilized_qty": statistics.mean(col("immobilized_qty")),
                "days": len(values),
            }
        )
    summary_rows.sort(
        key=lambda row: (
            str(row["node_id"]),
            str(row["product_item_id"]),
            str(row["threshold_mode"]),
            -float(row["mean_immobilized_stock_value_eur"]),
        )
    )

    write_csv(
        output_dir / "component_immobilized_stock_daily.csv",
        daily_rows,
        columns=[
            "day",
            "node_id",
            "product_item_id",
            "product_code",
            "threshold_mode",
            "stock_value_eur",
            "useful_stock_value_eur",
            "immobilized_stock_value_eur",
            "component_count",
            "priced_component_count",
        ],
    )
    write_csv(
        output_dir / "component_immobilized_stock_components_daily.csv",
        detail_rows,
        columns=[
            "day",
            "node_id",
            "product_item_id",
            "product_code",
            "component_item_id",
            "threshold_mode",
            "stock_qty",
            "useful_qty",
            "immobilized_qty",
            "unit_value_eur",
            "stock_value_eur",
            "useful_value_eur",
            "immobilized_value_eur",
            "value_source",
        ],
    )
    write_csv(
        output_dir / "component_immobilized_stock_summary.csv",
        summary_rows,
        columns=[
            "node_id",
            "product_item_id",
            "product_code",
            "component_item_id",
            "threshold_mode",
            "unit_value_eur",
            "value_source",
            "mean_stock_value_eur",
            "mean_useful_stock_value_eur",
            "mean_immobilized_stock_value_eur",
            "max_immobilized_stock_value_eur",
            "mean_stock_qty",
            "mean_useful_qty",
            "mean_immobilized_qty",
            "days",
        ],
    )

    run_summary = {
        "schema_version": "etudecas.component_immobilized_stock.v1",
        "run_dir": str(run_dir.resolve(strict=False)),
        "graph": str(graph_path.resolve(strict=False)),
        "scopes": [
            {
                "node_id": scope.factory,
                "product_item_id": scope.product_item,
                "product_code": scope.product_code,
                "component_count": len(scope.component_items),
            }
            for scope in scopes
        ],
        "threshold_modes": list(threshold_modes),
        "daily_rows": len(daily_rows),
        "component_daily_rows": len(detail_rows),
        "summary_rows": len(summary_rows),
    }
    summaries_dir = run_dir / "summaries"
    write_json(summaries_dir / "component_immobilized_stock_summary.json", run_summary)
    return run_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--threshold-mode",
        action="append",
        choices=THRESHOLD_MODES,
        help="Threshold mode to compute. Defaults to all standard modes.",
    )
    args = parser.parse_args()
    modes = tuple(args.threshold_mode) if args.threshold_mode else THRESHOLD_MODES
    summary = build_component_immobilized_stock_artifacts(
        run_dir=args.run_dir,
        graph_path=args.graph,
        output_dir=args.output_dir,
        threshold_modes=modes,
    )
    print(
        "[OK] component_immobilized_stock "
        f"daily_rows={summary['daily_rows']} component_rows={summary['component_daily_rows']}"
    )


if __name__ == "__main__":
    main()
