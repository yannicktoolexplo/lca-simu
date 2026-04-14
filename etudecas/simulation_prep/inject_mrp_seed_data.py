#!/usr/bin/env python3
"""Inject MRP snapshot seed data into a simulation-ready supply graph."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


DIVISION_TO_NODE = {
    "1430": "M-1430",
    "1810": "M-1810",
    "1450": "SDC-1450",
    "1920": "DC-1920",
}

XLSX_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

DEFAULT_HOLDING_COST = {
    "value": 0.0,
    "per": "unit*day",
    "is_default": True,
    "source": "mrp_seed_placeholder_pending_value_model",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject MRP seed data into a simulation graph.")
    parser.add_argument(
        "--input-graph",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_current.json",
        help="Source simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--stocks-mrp-xlsx",
        default="etudecas/donnees/Stocks_MRP.xlsx",
        help="MRP workbook path.",
    )
    parser.add_argument(
        "--output-graph",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_seeded.json",
        help="Output graph JSON.",
    )
    parser.add_argument(
        "--output-report-json",
        default="etudecas/simulation_prep/result/reference_baseline/mrp_seed_report.json",
        help="Output report JSON.",
    )
    parser.add_argument(
        "--output-report-md",
        default="etudecas/simulation_prep/result/reference_baseline/mrp_seed_report.md",
        help="Output report Markdown.",
    )
    parser.add_argument(
        "--include-mrp-lot-policies",
        action="store_true",
        help="Inject MRP lot rules on matching production processes.",
    )
    parser.add_argument(
        "--apply-safe-lot-sizes",
        action="store_true",
        help="Deprecated legacy mode: also overwrite batch_size for non-ambiguous lot rows.",
    )
    return parser.parse_args()


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_unit(unit: Any) -> str:
    text = str(unit or "").strip().upper()
    aliases = {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITS": "UN",
        "ZUN": "UN",
    }
    return aliases.get(text, text)


def convert_quantity(value: float, from_unit: Any, to_unit: Any) -> float:
    source = normalize_unit(from_unit)
    target = normalize_unit(to_unit)
    if not source or not target or source == target:
        return value
    if source == "KG" and target == "G":
        return value * 1000.0
    if source == "G" and target == "KG":
        return value / 1000.0
    return value


def canonical_article_id(raw: Any) -> str:
    text = str(raw or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def excel_serial_to_iso(raw: Any) -> str | None:
    serial = to_float(raw)
    if serial is None:
        return None
    origin = datetime(1899, 12, 30, tzinfo=timezone.utc)
    stamp = origin + timedelta(days=serial)
    return stamp.isoformat()


def excel_column_index(ref: str) -> int:
    match = re.match(r"([A-Z]+)", ref)
    if not match:
        return 0
    acc = 0
    for char in match.group(1):
        acc = acc * 26 + ord(char) - 64
    return acc - 1


def read_xlsx_tables(path: Path) -> dict[str, list[dict[str, str]]]:
    with zipfile.ZipFile(path) as workbook:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for node in root.findall("a:si", XLSX_NS):
                parts = [text.text or "" for text in node.findall(".//a:t", XLSX_NS)]
                shared_strings.append("".join(parts))

        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root
        }

        out: dict[str, list[dict[str, str]]] = {}
        for sheet in workbook_root.find("a:sheets", XLSX_NS) or []:
            name = sheet.attrib["name"]
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = "xl/" + rel_map[rel_id]
            sheet_root = ET.fromstring(workbook.read(target))
            rows: list[list[str]] = []
            for row in sheet_root.findall(".//a:sheetData/a:row", XLSX_NS):
                values: dict[int, str] = {}
                for cell in row.findall("a:c", XLSX_NS):
                    idx = excel_column_index(cell.attrib.get("r", "A1"))
                    cell_type = cell.attrib.get("t")
                    if cell_type == "inlineStr":
                        value = "".join(text.text or "" for text in cell.findall(".//a:t", XLSX_NS))
                    else:
                        raw_value = cell.findtext("a:v", default="", namespaces=XLSX_NS)
                        if cell_type == "s" and raw_value != "":
                            value = shared_strings[int(raw_value)]
                        else:
                            value = raw_value
                    values[idx] = value
                max_idx = max(values.keys(), default=-1)
                rows.append([values.get(i, "") for i in range(max_idx + 1)])
            if not rows:
                out[name] = []
                continue
            headers = [str(h).strip() for h in rows[0]]
            data_rows: list[dict[str, str]] = []
            for raw_row in rows[1:]:
                if not any(str(value).strip() for value in raw_row):
                    continue
                record = {
                    headers[idx]: str(raw_row[idx]).strip() if idx < len(raw_row) else ""
                    for idx in range(len(headers))
                }
                data_rows.append(record)
            out[name] = data_rows
        return out


def infer_item_unit_map(data: dict[str, Any]) -> dict[str, str]:
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for node in data.get("nodes") or []:
        inventory = (node.get("inventory") or {}).get("states") or []
        for state in inventory:
            item_id = str(state.get("item_id") or "")
            unit = normalize_unit(state.get("uom"))
            if item_id and unit:
                votes[item_id][unit] += 4
        for process in node.get("processes") or []:
            for raw_input in process.get("inputs") or []:
                item_id = str(raw_input.get("item_id") or "")
                unit = normalize_unit(raw_input.get("ratio_unit"))
                if item_id and unit:
                    votes[item_id][unit] += 2
            for raw_output in process.get("outputs") or []:
                item_id = str(raw_output.get("item_id") or "")
                unit = normalize_unit(raw_output.get("ratio_unit"))
                if item_id and unit:
                    votes[item_id][unit] += 1
    for edge in data.get("edges") or []:
        unit = normalize_unit(((edge.get("order_terms") or {}).get("quantity_unit")))
        if not unit:
            continue
        for raw_item_id in edge.get("items") or []:
            item_id = str(raw_item_id or "")
            if item_id:
                votes[item_id][unit] += 3
    priority = {"KG": 4, "G": 3, "UN": 2, "M": 1}
    result: dict[str, str] = {}
    for item_id, counter in votes.items():
        best_unit = sorted(counter.items(), key=lambda pair: (-pair[1], -priority.get(pair[0], 0), pair[0]))[0][0]
        result[item_id] = best_unit
    return result


def build_modeled_pairs(data: dict[str, Any]) -> set[tuple[str, str]]:
    modeled_pairs: set[tuple[str, str]] = set()
    for node in data.get("nodes") or []:
        node_id = str(node.get("id") or "")
        for state in ((node.get("inventory") or {}).get("states") or []):
            modeled_pairs.add((node_id, str(state.get("item_id") or "")))
        for process in node.get("processes") or []:
            for raw_input in process.get("inputs") or []:
                modeled_pairs.add((node_id, str(raw_input.get("item_id") or "")))
            for raw_output in process.get("outputs") or []:
                modeled_pairs.add((node_id, str(raw_output.get("item_id") or "")))
    for edge in data.get("edges") or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        for raw_item_id in edge.get("items") or []:
            item_id = str(raw_item_id or "")
            modeled_pairs.add((src, item_id))
            modeled_pairs.add((dst, item_id))
    return modeled_pairs


def ensure_inventory_state(
    *,
    node: dict[str, Any],
    item_id: str,
    initial: float,
    uom: str,
    source: str,
) -> tuple[str, float | None]:
    inventory = node.get("inventory")
    if not isinstance(inventory, dict):
        inventory = {"states": [], "backlogs": [], "wip": []}
        node["inventory"] = inventory
    states = inventory.get("states")
    if not isinstance(states, list):
        states = []
        inventory["states"] = states
    state = next((s for s in states if str(s.get("item_id") or "") == item_id), None)
    initial = round(max(0.0, initial), 6)
    if not isinstance(state, dict):
        state = {
            "item_id": item_id,
            "state_id": f"I_{item_id.replace('item:', '')}_{str(node.get('id') or '').replace('-', '_')}",
            "initial": initial,
            "uom": uom,
            "holding_cost": dict(DEFAULT_HOLDING_COST),
            "is_default_initial": False,
            "initial_source": source,
            "uom_source": "mrp_snapshot",
        }
        states.append(state)
        return "created", None
    previous = to_float(state.get("initial"))
    state["initial"] = initial
    state["uom"] = uom or str(state.get("uom") or "")
    state["is_default_initial"] = False
    state["initial_source"] = source
    if "holding_cost" not in state or not isinstance(state.get("holding_cost"), dict):
        state["holding_cost"] = dict(DEFAULT_HOLDING_COST)
    return "updated", previous


def main() -> None:
    args = parse_args()
    input_graph = Path(args.input_graph)
    mrp_xlsx = Path(args.stocks_mrp_xlsx)
    output_graph = Path(args.output_graph)
    output_report_json = Path(args.output_report_json)
    output_report_md = Path(args.output_report_md)

    data = json.loads(input_graph.read_text(encoding="utf-8"))
    tables = read_xlsx_tables(mrp_xlsx)
    stock_rows = tables.get("Stocks") or []
    policy_rows = tables.get("Politique de Stock MRP") or []
    lot_rows = tables.get("Taille de Lots") or []

    node_by_id = {str(node.get("id") or ""): node for node in data.get("nodes") or []}
    item_unit_map = infer_item_unit_map(data)
    modeled_pairs = build_modeled_pairs(data)
    modeled_items = {item_id for _node_id, item_id in modeled_pairs}

    snapshot_iso = None
    if stock_rows:
        snapshot_iso = excel_serial_to_iso(stock_rows[0].get("Date de photo DMP"))
    source_tag = "mrp_snapshot" if snapshot_iso is None else f"mrp_snapshot_{snapshot_iso}"

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_graph": str(input_graph),
        "output_graph": str(output_graph),
        "stocks_mrp_xlsx": str(mrp_xlsx),
        "snapshot_at_utc": snapshot_iso,
        "stock_rows_total": len(stock_rows),
        "policy_rows_total": len(policy_rows),
        "lot_rows_total": len(lot_rows),
        "stock_rows_injected": 0,
        "stock_rows_skipped": 0,
        "inventory_states_created": 0,
        "inventory_states_updated": 0,
        "qty_by_node_item": [],
        "skipped_stock_rows": [],
        "lot_policies_applied": [],
        "lot_updates": [],
        "skipped_lot_rows": [],
        "policy_rows_by_node": {},
    }

    policy_counter: dict[str, int] = Counter()
    for row in policy_rows:
        node_id = DIVISION_TO_NODE.get(str(row.get("Division") or "").strip())
        if node_id:
            policy_counter[node_id] += 1
    report["policy_rows_by_node"] = dict(sorted(policy_counter.items()))

    for row in stock_rows:
        division = str(row.get("Division") or "").strip()
        node_id = DIVISION_TO_NODE.get(division)
        article = canonical_article_id(row.get("Numéro d'article"))
        item_id = f"item:{article}" if article else ""
        qty = to_float(row.get("Stock Total"))
        source_unit = normalize_unit(row.get("Unité de quantité de base"))
        if not node_id or not item_id or qty is None:
            report["stock_rows_skipped"] += 1
            report["skipped_stock_rows"].append(
                {
                    "division": division,
                    "item_id": item_id,
                    "reason": "missing_mapping_or_qty",
                }
            )
            continue
        if item_id not in modeled_items:
            report["stock_rows_skipped"] += 1
            report["skipped_stock_rows"].append(
                {
                    "node_id": node_id,
                    "item_id": item_id,
                    "reason": "item_not_modeled_in_graph",
                    "source_qty": qty,
                    "source_unit": source_unit,
                }
            )
            continue
        if (node_id, item_id) not in modeled_pairs:
            report["stock_rows_skipped"] += 1
            report["skipped_stock_rows"].append(
                {
                    "node_id": node_id,
                    "item_id": item_id,
                    "reason": "node_item_pair_not_modeled",
                    "source_qty": qty,
                    "source_unit": source_unit,
                }
            )
            continue
        node = node_by_id.get(node_id)
        if not isinstance(node, dict):
            report["stock_rows_skipped"] += 1
            report["skipped_stock_rows"].append(
                {
                    "node_id": node_id,
                    "item_id": item_id,
                    "reason": "node_missing_in_graph",
                }
            )
            continue
        target_unit = item_unit_map.get(item_id, source_unit)
        converted_qty = convert_quantity(qty, source_unit, target_unit)
        action, previous_initial = ensure_inventory_state(
            node=node,
            item_id=item_id,
            initial=converted_qty,
            uom=target_unit,
            source=source_tag,
        )
        if action == "created":
            report["inventory_states_created"] += 1
        else:
            report["inventory_states_updated"] += 1
        report["stock_rows_injected"] += 1
        report["qty_by_node_item"].append(
            {
                "node_id": node_id,
                "item_id": item_id,
                "initial_before": previous_initial,
                "initial_after": converted_qty,
                "uom": target_unit,
                "source_qty": qty,
                "source_unit": source_unit,
            }
        )

    if not args.include_mrp_lot_policies and not args.apply_safe_lot_sizes:
        report["skipped_lot_rows"].append({"reason": "lot_rule_injection_not_requested"})
    for row in lot_rows:
        for row in lot_rows:
            division = str(row.get("Division") or "").strip()
            node_id = DIVISION_TO_NODE.get(division)
            article = canonical_article_id(row.get("Numéro d'article"))
            item_id = f"item:{article}" if article else ""
            fixed = to_float(row.get("Taille de lot fixe")) or 0.0
            max_lot = to_float(row.get("Taille de lot maximale")) or 0.0
            min_lot = to_float(row.get("Taille de lot minimale")) or 0.0
            if not node_id or not item_id:
                report["skipped_lot_rows"].append(
                    {
                        "division": division,
                        "item_id": item_id,
                        "reason": "missing_mapping",
                    }
                )
                continue
            node = node_by_id.get(node_id)
            if not isinstance(node, dict):
                report["skipped_lot_rows"].append(
                    {
                        "node_id": node_id,
                        "item_id": item_id,
                        "reason": "node_missing_in_graph",
                    }
                )
                continue
            target_batch = None
            rule = ""
            if fixed > 0:
                target_batch = fixed
                rule = "fixed_lot"
            elif max_lot > 0 and abs(max_lot - min_lot) <= 1e-9:
                target_batch = max_lot
                rule = "min_equals_max"
            if target_batch is None:
                report["skipped_lot_rows"].append(
                    {
                        "node_id": node_id,
                        "item_id": item_id,
                        "reason": "ambiguous_lot_rule",
                        "fixed": fixed,
                        "max": max_lot,
                        "min": min_lot,
                    }
                )
                continue
            process = next(
                (
                    proc
                    for proc in (node.get("processes") or [])
                    if any(str(raw_output.get("item_id") or "") == item_id for raw_output in (proc.get("outputs") or []))
                ),
                None,
            )
            if not isinstance(process, dict):
                report["skipped_lot_rows"].append(
                    {
                        "node_id": node_id,
                        "item_id": item_id,
                        "reason": "matching_output_process_missing",
                    }
                )
                continue
            previous_batch = to_float(process.get("batch_size"))
            process["batch_size"] = target_batch
            process["batch_size_source"] = f"mrp_lot_size_{rule}"
            report["lot_updates"].append(
                {
                    "node_id": node_id,
                    "process_id": str(process.get("id") or ""),
                    "item_id": item_id,
                    "batch_before": previous_batch,
                    "batch_after": target_batch,
                    "rule": rule,
                }
            )

    report["qty_by_node_item"].sort(key=lambda row: (row["node_id"], row["item_id"]))
    report["skipped_stock_rows"].sort(key=lambda row: (row.get("node_id", ""), row.get("item_id", ""), row.get("reason", "")))
    report["lot_updates"].sort(key=lambda row: (row["node_id"], row["item_id"]))
    report["skipped_lot_rows"].sort(key=lambda row: (row.get("node_id", ""), row.get("item_id", ""), row.get("reason", "")))

    meta = data.get("meta") or {}
    meta["mrp_seed"] = {
        "generated_at_utc": report["generated_at_utc"],
        "stocks_mrp_xlsx": str(mrp_xlsx),
        "snapshot_at_utc": snapshot_iso,
        "stock_rows_injected": report["stock_rows_injected"],
        "inventory_states_created": report["inventory_states_created"],
        "inventory_states_updated": report["inventory_states_updated"],
        "lot_updates": len(report["lot_updates"]),
    }
    data["meta"] = meta

    output_graph.parent.mkdir(parents=True, exist_ok=True)
    output_graph.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    output_report_json.parent.mkdir(parents=True, exist_ok=True)
    output_report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# MRP Seed Injection Report",
        "",
        f"- Source graph: `{input_graph}`",
        f"- Output graph: `{output_graph}`",
        f"- Workbook: `{mrp_xlsx}`",
        f"- Snapshot UTC: `{snapshot_iso or 'unknown'}`",
        f"- Stock rows injected: `{report['stock_rows_injected']}` / `{report['stock_rows_total']}`",
        f"- Inventory states created: `{report['inventory_states_created']}`",
        f"- Inventory states updated: `{report['inventory_states_updated']}`",
        f"- Safe lot-size updates: `{len(report['lot_updates'])}`",
        "",
        "## Injected stock rows",
    ]
    for row in report["qty_by_node_item"]:
        before = "none" if row["initial_before"] is None else f"{row['initial_before']}"
        lines.append(
            f"- {row['node_id']} / {row['item_id']}: `{before}` -> `{row['initial_after']}` `{row['uom']}` "
            f"(source `{row['source_qty']}` `{row['source_unit']}`)"
        )
    if report["skipped_stock_rows"]:
        lines.extend(["", "## Skipped stock rows"])
        for row in report["skipped_stock_rows"]:
            lines.append(
                f"- {row.get('node_id', row.get('division', '?'))} / {row.get('item_id', '?')}: `{row['reason']}`"
            )
    if report["lot_updates"]:
        lines.extend(["", "## Lot-size updates"])
        for row in report["lot_updates"]:
            lines.append(
                f"- {row['node_id']} / {row['process_id']} / {row['item_id']}: "
                f"`{row['batch_before']}` -> `{row['batch_after']}` via `{row['rule']}`"
            )
    if report["skipped_lot_rows"]:
        lines.extend(["", "## Skipped lot rows"])
        for row in report["skipped_lot_rows"]:
            lines.append(
                f"- {row.get('node_id', row.get('division', '?'))} / {row.get('item_id', '?')}: `{row['reason']}`"
            )
    output_report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
