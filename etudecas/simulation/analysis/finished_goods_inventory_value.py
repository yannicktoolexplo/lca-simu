"""Build finished-goods stock valuation artifacts from a simulation run.

The component-stock module handles input materials and PFI separately.  This
module keeps finished goods as a distinct valuation surface so component stock
and PF stock can be discussed without double counting.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis.component_immobilized_stock import build_unit_values


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(" ", "").replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def norm_item_code(item_id: Any) -> str:
    text = str(item_id or "").strip()
    if text.startswith("item:"):
        text = text.split(":", 1)[1]
    return text


def norm_uom(uom: Any) -> str:
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


def convert_qty(qty: float, from_uom: Any, to_uom: Any) -> float | None:
    src = norm_uom(from_uom)
    dst = norm_uom(to_uom)
    if not src or not dst or src == dst:
        return qty
    mass_to_g = {"G": 1.0, "KG": 1000.0}
    if src in mass_to_g and dst in mass_to_g:
        return qty * mass_to_g[src] / mass_to_g[dst]
    return None


def is_finished_good_item(graph: dict[str, Any], item_id: str) -> bool:
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or "") != "factory":
            continue
        for process in node.get("processes") or []:
            if not isinstance(process, dict):
                continue
            outputs = process.get("outputs") if isinstance(process.get("outputs"), list) else []
            if any(str(output.get("item_id") or "") == item_id for output in outputs if isinstance(output, dict)):
                return True
    return False


def finished_good_items(graph: dict[str, Any]) -> set[str]:
    items: set[str] = set()
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or "") != "factory":
            continue
        for process in node.get("processes") or []:
            if not isinstance(process, dict):
                continue
            for output in process.get("outputs") if isinstance(process.get("outputs"), list) else []:
                if isinstance(output, dict) and str(output.get("item_id") or ""):
                    items.add(str(output["item_id"]))
    return items


def _state_unit_value(state: dict[str, Any]) -> tuple[float | None, str, bool]:
    holding = state.get("holding_cost") if isinstance(state.get("holding_cost"), dict) else {}
    value = parse_float(holding.get("unit_value_basis"), default=float("nan"))
    if value != value or value <= 0:
        return None, "", False
    source = str(holding.get("source") or "")
    is_fallback = bool(holding.get("is_default")) or "fallback" in source.lower()
    return value, source, is_fallback


def _production_cost_values(graph: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Compute PF unit production costs from BOM inputs valued at purchase cost.

    MP/component costs come from ``build_unit_values``. That function rejects
    generic fallback values and rolls up internal PFI transfer prices when the
    upstream BOM is available. Missing input prices are reported explicitly and
    produce a partial production cost rather than an invisible fallback.
    """

    component_values = build_unit_values(graph)
    values: dict[tuple[str, str], dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory" or not node_id:
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
            batch_size = parse_float(process.get("batch_size"), default=0.0)
            output_uom = process.get("batch_size_unit") or output.get("uom") or "UN"
            output_qty = convert_qty(batch_size, output_uom, output_uom)
            if not output_item or not output_qty or output_qty <= 0:
                continue
            total_input_cost = 0.0
            missing_components: list[str] = []
            priced_components = 0
            for component in inputs:
                if not isinstance(component, dict):
                    continue
                input_item = str(component.get("item_id") or "")
                ratio = parse_float(component.get("ratio_per_batch"), default=0.0)
                if not input_item or ratio <= 0:
                    continue
                unit_info = component_values.get((node_id, input_item))
                if not unit_info:
                    missing_components.append(norm_item_code(input_item))
                    continue
                ratio_uom = component.get("ratio_unit") or unit_info.get("uom") or ""
                converted_qty = convert_qty(ratio, ratio_uom, unit_info.get("uom") or ratio_uom)
                if converted_qty is None:
                    missing_components.append(norm_item_code(input_item))
                    continue
                total_input_cost += converted_qty * float(unit_info["unit_value_eur"])
                priced_components += 1
            if total_input_cost <= 0:
                continue
            complete = not missing_components
            values[(node_id, output_item)] = {
                "unit_value_eur": total_input_cost / output_qty,
                "value_source": "bom_purchase_production_cost" if complete else "bom_purchase_production_cost_partial",
                "is_fallback_unit_value": False,
                "valuation_status": "complete_production_cost" if complete else "partial_production_cost",
                "source_count": priced_components,
                "missing_component_count": len(missing_components),
                "missing_components": ",".join(missing_components),
            }
    return values


def build_finished_good_unit_values(graph: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Return unit values for finished goods by (node, item).

    Business rule:
    * PF is valued at production cost, built from BOM inputs valued at purchase
      cost / internal production roll-up.
    * Generic graph fallback values are used only as a last resort and remain
      flagged.
    """

    finished_items = finished_good_items(graph)
    fallback_values: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    fallback_product_values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        for state in ((node.get("inventory") or {}).get("states") or []):
            if not isinstance(state, dict):
                continue
            item_id = str(state.get("item_id") or "")
            if item_id not in finished_items:
                continue
            unit_value, source, is_fallback = _state_unit_value(state)
            if unit_value is None:
                continue
            row = {
                "unit_value_eur": unit_value,
                "value_source": source,
                "is_fallback_unit_value": is_fallback,
                "valuation_status": "fallback_unit_value" if is_fallback else "inventory_state_unit_value",
                "missing_component_count": 0,
                "missing_components": "",
            }
            fallback_values[(node_id, item_id)].append(row)
            fallback_product_values[item_id].append(row)

    production_values = _production_cost_values(graph)
    production_product_values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (_, item_id), row in production_values.items():
        production_product_values[item_id].append(row)
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for key, row in production_values.items():
        selected[key] = row
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        for item_id, rows in production_product_values.items():
            selected.setdefault((node_id, item_id), _select_unit_value(rows))
    for key, rows in fallback_values.items():
        selected.setdefault(key, _select_unit_value(rows))
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        for item_id, rows in fallback_product_values.items():
            selected.setdefault((node_id, item_id), _select_unit_value(rows))
    return selected


def _select_unit_value(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reliable = [row for row in rows if not row.get("is_fallback_unit_value")]
    scoped = reliable or rows
    unit_values = [float(row["unit_value_eur"]) for row in scoped if parse_float(row.get("unit_value_eur")) > 0]
    representative = scoped[0] if scoped else {}
    return {
        "unit_value_eur": statistics.median(unit_values) if unit_values else 0.0,
        "value_source": representative.get("value_source", ""),
        "is_fallback_unit_value": not bool(reliable),
        "source_count": len(rows),
        "valuation_status": representative.get("valuation_status", ""),
        "missing_component_count": representative.get("missing_component_count", 0),
        "missing_components": representative.get("missing_components", ""),
    }


def _stock_rows(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = [
        ("factory", run_dir / "data" / "production_output_products_daily.csv"),
        ("distribution", run_dir / "data" / "production_dc_stocks_daily.csv"),
    ]
    for location_type, path in sources:
        for row in read_csv_rows(path):
            item_id = str(row.get("item_id") or "")
            node_id = str(row.get("node_id") or "")
            if not item_id or not node_id:
                continue
            rows.append(
                {
                    "day": int(parse_float(row.get("day"))),
                    "node_id": node_id,
                    "location_type": location_type,
                    "product_item_id": item_id,
                    "product_code": norm_item_code(item_id),
                    "stock_qty": parse_float(row.get("stock_end_of_day")),
                }
            )
    return rows


def build_finished_goods_inventory_value_artifacts(
    *,
    run_dir: Path,
    graph_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir or run_dir / "data"
    graph = read_json(graph_path)
    stock_rows = _stock_rows(run_dir)
    stocked_at_distribution = {
        str(row["product_item_id"])
        for row in stock_rows
        if str(row.get("location_type") or "") == "distribution"
    }
    finished_items = stocked_at_distribution or finished_good_items(graph)
    unit_values = build_finished_good_unit_values(graph)

    detail_rows: list[dict[str, Any]] = []
    totals: dict[tuple[int, str], dict[str, Any]] = {}
    for row in stock_rows:
        item_id = str(row["product_item_id"])
        if item_id not in finished_items:
            continue
        unit_info = unit_values.get((str(row["node_id"]), item_id), {})
        unit_value = parse_float(unit_info.get("unit_value_eur"))
        stock_value = float(row["stock_qty"]) * unit_value
        detail = {
            **row,
            "unit_value_eur": unit_value,
            "stock_value_eur": stock_value,
            "value_source": unit_info.get("value_source", ""),
            "is_fallback_unit_value": bool(unit_info.get("is_fallback_unit_value")),
            "valuation_status": unit_info.get("valuation_status", ""),
            "missing_component_count": unit_info.get("missing_component_count", 0),
            "missing_components": unit_info.get("missing_components", ""),
        }
        detail_rows.append(detail)
        key = (int(row["day"]), item_id)
        total = totals.setdefault(
            key,
            {
                "day": int(row["day"]),
                "node_id": "ALL",
                "location_type": "total",
                "product_item_id": item_id,
                "product_code": row["product_code"],
                "stock_qty": 0.0,
                "stock_value_eur": 0.0,
                "unit_value_eur": unit_value,
                "value_source": unit_info.get("value_source", ""),
                "is_fallback_unit_value": bool(unit_info.get("is_fallback_unit_value")),
                "valuation_status": unit_info.get("valuation_status", ""),
                "missing_component_count": unit_info.get("missing_component_count", 0),
                "missing_components": unit_info.get("missing_components", ""),
            },
        )
        total["stock_qty"] += float(row["stock_qty"])
        total["stock_value_eur"] += stock_value

    all_rows = detail_rows + list(totals.values())
    all_rows.sort(key=lambda row: (int(row["day"]), str(row["product_code"]), str(row["location_type"]), str(row["node_id"])))
    columns = [
        "day",
        "node_id",
        "location_type",
        "product_item_id",
        "product_code",
        "stock_qty",
        "unit_value_eur",
        "stock_value_eur",
        "value_source",
        "is_fallback_unit_value",
        "valuation_status",
        "missing_component_count",
        "missing_components",
    ]
    write_csv(output_dir / "finished_goods_stock_value_daily.csv", all_rows, columns=columns)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        grouped[(str(row["product_code"]), str(row["location_type"]))].append(row)
    summary_rows: list[dict[str, Any]] = []
    for (product_code, location_type), rows in grouped.items():
        qty_values = [float(row["stock_qty"]) for row in rows]
        value_values = [float(row["stock_value_eur"]) for row in rows]
        fallback_count = sum(1 for row in rows if row.get("is_fallback_unit_value"))
        summary_rows.append(
            {
                "product_code": product_code,
                "location_type": location_type,
                "mean_stock_qty": statistics.mean(qty_values),
                "mean_stock_value_eur": statistics.mean(value_values),
                "min_stock_value_eur": min(value_values),
                "max_stock_value_eur": max(value_values),
                "unit_value_eur": rows[0].get("unit_value_eur", 0.0),
                "value_source": rows[0].get("value_source", ""),
                "fallback_value_days": fallback_count,
                "valuation_status": rows[0].get("valuation_status", ""),
                "missing_component_count": rows[0].get("missing_component_count", 0),
                "missing_components": rows[0].get("missing_components", ""),
                "days": len(rows),
            }
        )
    summary_rows.sort(key=lambda row: (str(row["product_code"]), str(row["location_type"])))
    write_csv(
        output_dir / "finished_goods_stock_value_summary.csv",
        summary_rows,
        columns=[
            "product_code",
            "location_type",
            "mean_stock_qty",
            "mean_stock_value_eur",
            "min_stock_value_eur",
            "max_stock_value_eur",
            "unit_value_eur",
            "value_source",
            "fallback_value_days",
            "valuation_status",
            "missing_component_count",
            "missing_components",
            "days",
        ],
    )

    summary = {
        "schema_version": "etudecas.finished_goods_inventory_value.v1",
        "run_dir": str(run_dir.resolve(strict=False)),
        "graph": str(graph_path.resolve(strict=False)),
        "finished_good_items": sorted(norm_item_code(item_id) for item_id in finished_items),
        "daily_rows": len(all_rows),
        "summary_rows": len(summary_rows),
        "fallback_daily_rows": sum(1 for row in all_rows if row.get("is_fallback_unit_value")),
    }
    write_json(run_dir / "summaries" / "finished_goods_stock_value_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    summary = build_finished_goods_inventory_value_artifacts(
        run_dir=args.run_dir,
        graph_path=args.graph,
        output_dir=args.output_dir,
    )
    print(
        "[OK] finished_goods_inventory_value "
        f"daily_rows={summary['daily_rows']} summary_rows={summary['summary_rows']}"
    )


if __name__ == "__main__":
    main()
