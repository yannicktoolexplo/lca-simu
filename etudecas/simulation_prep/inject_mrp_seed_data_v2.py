#!/usr/bin/env python3
"""Inject MRP snapshot stock and lot data into a simulation-ready supply graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


DIVISION_TO_NODE = {
    "1430": "M-1430",
    "1810": "M-1810",
    "1450": "SDC-1450",
    "1920": "DC-1920",
}

MRP_POLICY_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("DC-1920", "item:268091"): {
        "safety_time_days": 20.0,
        "source": "industrial_confirmation_2026-04-10",
    },
    ("DC-1920", "item:268967"): {
        "safety_time_days": 25.0,
        "source": "industrial_confirmation_2026-04-10",
    },
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
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated.json",
        help="Source graph JSON after the real-demand calibration step.",
    )
    parser.add_argument(
        "--stocks-mrp-xlsx",
        default="etudecas/data/source/Extract_Données_Complémentaires.xlsx",
        help="MRP complementary workbook path.",
    )
    parser.add_argument(
        "--policy-xlsx",
        help="Explicit newer stock-policy workbook; its rows take precedence over historical policy overrides, without replacing opening stocks.",
    )
    parser.add_argument(
        "--customer-demand-xlsx",
        help="Optional dated customer history and forecast workbook (Historique/Projection); replaces the demand proxy only.",
    )
    parser.add_argument(
        "--output-graph",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json",
        help="Output graph JSON with MRP snapshot and lot-policy data injected.",
    )
    parser.add_argument(
        "--output-report-json",
        default="etudecas/simulation_prep/result/reference_baseline/mrp_lot_policy_report.json",
        help="Output report JSON.",
    )
    parser.add_argument(
        "--output-report-md",
        default="etudecas/simulation_prep/result/reference_baseline/mrp_lot_policy_report.md",
        help="Output report Markdown.",
    )
    parser.add_argument(
        "--include-mrp-lot-policies",
        action="store_true",
        help="Inject lot sizing rules from the MRP workbook onto matching production processes.",
    )
    parser.add_argument(
        "--apply-safe-lot-sizes",
        action="store_true",
        help="Legacy compatibility mode: also overwrite batch_size for fixed lots or min=max cases.",
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


def row_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row:
            return str(row.get(key) or "").strip()
    return ""


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
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}

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


def set_state_mrp_policy(
    *,
    node: dict[str, Any],
    item_id: str,
    safety_time_days: float | None,
    safety_stock_qty: float | None,
    source_unit: str,
    default_uom: str,
    source: str,
) -> dict[str, Any] | None:
    inventory = node.get("inventory")
    if not isinstance(inventory, dict):
        return None
    states = inventory.get("states")
    if not isinstance(states, list):
        return None
    state = next((s for s in states if str(s.get("item_id") or "") == item_id), None)
    if not isinstance(state, dict):
        return None
    target_uom = normalize_unit(state.get("uom") or default_uom)
    converted_safety_stock = None
    if safety_stock_qty is not None:
        converted_safety_stock = round(
            max(0.0, convert_quantity(max(0.0, safety_stock_qty), source_unit, target_uom)),
            6,
        )
    policy = state.get("mrp_policy")
    if not isinstance(policy, dict):
        policy = {}
    if safety_time_days is not None:
        policy["safety_time_days"] = round(max(0.0, safety_time_days), 6)
    if converted_safety_stock is not None:
        policy["safety_stock_qty"] = converted_safety_stock
        policy["safety_stock_uom"] = target_uom
    policy["source"] = source
    state["mrp_policy"] = policy
    return {
        "node_id": str(node.get("id") or ""),
        "item_id": item_id,
        "safety_time_days": round(max(0.0, safety_time_days or 0.0), 6) if safety_time_days is not None else None,
        "safety_stock_qty": converted_safety_stock,
        "uom": target_uom,
        "source": source,
    }


def apply_source_mrp_policy_rows(
    data: dict[str, Any], rows: list[dict[str, str]], *, source: str,
) -> list[dict[str, Any]]:
    """Apply an explicitly selected policy vintage, including genuine zero values.

    Stocks, lots and absent site/article policies are untouched. Validate all
    applicable rows before updating any state; unit mismatches must not silently
    reinterpret a safety quantity.
    """
    states = {(str(node.get("id")), str(state.get("item_id"))): state
              for node in data.get("nodes", [])
              for state in node.get("inventory", {}).get("states", [])}
    pending = []
    seen = set()
    for row_number, row in enumerate(rows, 2):
        article = canonical_article_id(row.get("Numéro d'article"))
        key = (DIVISION_TO_NODE.get(canonical_article_id(row.get("Division"))),
               f"item:{article}")
        if key not in states:
            continue
        if key in seen:
            raise ValueError(f"Duplicate source MRP policy for {key}")
        seen.add(key)
        days = to_float(row.get("Délai de sécurité (en jours ouvrés)"))
        qty = to_float(row.get("Stock de sécurité"))
        if any(value is None or not math.isfinite(value) or value < 0 for value in (days, qty)):
            raise ValueError(f"Invalid source MRP safety at row {row_number}: {key}")
        state = states[key]
        source_unit = normalize_unit(row.get("Unité de quantité de base"))
        target_unit = normalize_unit(state.get("uom"))
        if not source_unit or not target_unit or (source_unit != target_unit and
                {source_unit, target_unit} != {"G", "KG"}):
            raise ValueError(f"Incompatible source MRP units for {key}: {source_unit}/{target_unit}")
        policy = {**state.get("mrp_policy", {}), "safety_time_days": days,
                  "safety_stock_qty": convert_quantity(qty, source_unit, target_unit),
                  "safety_stock_uom": target_unit, "source": f"{source}!E{row_number}:G{row_number}"}
        pending.append((state, policy, {"node_id": key[0], "item_id": key[1],
                        "previous_policy": dict(state.get("mrp_policy", {})),
                        "applied_policy": policy}))
    for state, policy, _ in pending:
        state["mrp_policy"] = policy
    return [record for _, _, record in pending]


def build_customer_demand_payloads(
    graph: dict[str, Any], history_rows: list[dict[str, Any]],
    projection_rows: list[dict[str, Any]], *, source_file: str,
    source_sha256: str, origin: str = "2025-01-01",
) -> dict[str, Any]:
    """Validate dated customer data in memory, without changing graph or sources.

    Workbook quantities are signed outflows. Weeks start on Monday; the
    snapshot's Monday is an explicit information-date convention, not proof of
    the publication day. Unit and customer assignment come from the graph.
    """
    origin_date = date.fromisoformat(origin)
    customers: dict[str, tuple[str, str]] = {}
    for node in graph.get("nodes", []):
        if node.get("type") != "customer":
            continue
        for state in node.get("inventory", {}).get("states", []):
            item_id = state["item_id"]
            article = item_id.removeprefix("item:")
            if article in customers or normalize_unit(state.get("uom")) != "UN":
                raise ValueError(f"Ambiguous customer or non-UN unit for {article}")
            customers[article] = (node["id"], item_id)
    if not customers or not history_rows or not projection_rows:
        raise ValueError("Customer graph, history and forecasts must be populated")

    def monday(value: Any) -> date:
        if isinstance(value, datetime):
            result = value.date()
        elif isinstance(value, date):
            result = value
        elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            result = date.fromisoformat(value)
        else:
            serial = to_float(value)
            if serial is None or not math.isfinite(serial) or not serial.is_integer():
                raise ValueError(f"Invalid customer date: {value!r}")
            result = date(1899, 12, 30) + timedelta(days=int(serial))
        if result.weekday() != 0:
            raise ValueError(f"Customer week must start on Monday: {result}")
        return result

    def quantity(value: Any) -> int:
        number = to_float(value)
        if (isinstance(value, bool) or number is None or not math.isfinite(number)
                or number > 0 or not number.is_integer()):
            raise ValueError(f"Customer outflow must be a non-positive integer: {value!r}")
        return -int(number)

    def convert(rows: list[dict[str, Any]], forecast: bool) -> list[dict[str, Any]]:
        sheet = "Projection" if forecast else "Historique"
        converted, seen = [], set()
        periods: dict[tuple[str, int | None], list[int]] = defaultdict(list)
        for number, row in enumerate(rows, start=2):
            article = canonical_article_id(row.get("SKU Code"))
            if article not in customers:
                raise ValueError(f"{sheet}!{number}: unknown customer article {article}")
            node_id, item_id = customers[article]
            start = (monday(row.get("First day of Week Year Horizon")) - origin_date).days
            vintage = ((monday(row.get("First day of Week Year Snapshot")) - origin_date).days
                       if forecast else None)
            if forecast and (vintage < -6 or start < vintage + 7):
                raise ValueError(f"{sheet}!{number}: forecast must follow its dated snapshot")
            key = (article, vintage, start)
            if key in seen:
                raise ValueError(f"{sheet}!{number}: duplicate customer week {key}")
            seen.add(key)
            periods[(article, vintage)].append(start)
            entry = {
                "node_id": node_id, "item_id": item_id, "uom": "UN",
                "period_start_day": start, "period_days": 7,
                "qty": quantity(row.get("Forecasted Demand" if forecast else "Actual Demand")),
                "source_file": source_file,
                "source_row": f"{sheet}!A{number}:{'E' if forecast else 'D'}{number}",
            }
            if forecast:
                entry["vintage_day"] = vintage
            converted.append(entry)
        if {key[0] for key in periods} != set(customers):
            raise ValueError(f"{sheet}: source must cover every modeled customer article")
        for key, starts in periods.items():
            starts.sort()
            if any(b - a != 7 for a, b in zip(starts, starts[1:])):
                raise ValueError(f"{sheet}: missing customer week for {key}")
            if forecast and len(starts) != 52:
                raise ValueError(f"{sheet}: expected 52 weeks per snapshot for {key}")
        return sorted(converted, key=lambda r: (r["item_id"], r.get("vintage_day", -9999), r["period_start_day"]))

    history, forecasts = convert(history_rows, False), convert(projection_rows, True)
    provenance = {"file": source_file, "sha256": source_sha256}
    common = {"schema_version": 1, "origin": origin, "calendar": "monday_start"}
    return {
        "customer_demand_policy": "source_customer_history_v1",
        "mrp_forecast_missing_period_policy": "last_known_period_v1",
        "forecast_consumption_policy": "weekly_actual_orders_v1",
        "customer_demand_history": {
            **common, "rows": history, "source": {**provenance, "sheet": "Historique", "column": "D"},
            "scope": "Demand requests; not proof of fulfilled industrial shipments",
            "allocation": "Whole UN spread uniformly over seven days; year boundaries clipped without redistribution",
        },
        "mrp_forecasts": {
            **common, "repeat_period_days": 365, "rows": forecasts,
            "current_bucket_policy": "excluded_unresolved_carry_over",
            "source": {**provenance, "sheet": "Projection", "column": "E"},
            "snapshot_date_assumption": "Snapshot week Monday used as knowledge date; exact publication timestamp unknown",
            "scope": "Dated commercial forecast at customer; not component demand or physical shipments",
            "repeat_policy": "Disabled in source_customer_history_v1; retain source 2026 forecasts without growth multiplier",
            "missing_period_policy": "Retain older known period; otherwise borrow nearest period from latest known snapshot, visibly estimated",
            "unit_basis": "UN from modeled customer states; workbook has no unit or site column",
        },
    }


def apply_customer_demand_source(
    graph: dict[str, Any], workbook: Path, *, origin: str = "2025-01-01",
) -> dict[str, Any]:
    """Read-only Excel import; mutate graph metadata only after full validation."""
    workbook = Path(workbook)
    before = hashlib.sha256(workbook.read_bytes()).hexdigest()
    sheets = read_xlsx_tables(workbook)
    updates = build_customer_demand_payloads(
        graph, sheets.get("Historique", []), sheets.get("Projection", []),
        source_file=workbook.name, source_sha256=before, origin=origin,
    )
    if before != hashlib.sha256(workbook.read_bytes()).hexdigest():
        raise RuntimeError("Customer workbook changed during import")
    if graph.get("meta", {}).get("forecast_annual_projection_policy"):
        raise ValueError("Remove annual projection override explicitly before importing dated customer forecasts")
    graph.setdefault("meta", {}).update(updates)
    return {
        "source_file": workbook.name, "sha256": before, "source_unchanged": True,
        "history_rows": len(updates["customer_demand_history"]["rows"]),
        "forecast_rows": len(updates["mrp_forecasts"]["rows"]),
        "changed_meta_keys": sorted(updates), "origin": origin,
    }


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

    snapshot_iso = excel_serial_to_iso(stock_rows[0].get("Date de photo DMP")) if stock_rows else None
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
        "mrp_policies_applied": [],
        "mrp_policy_overrides_applied": [],
        "skipped_policy_rows": [],
    }

    policy_counter: dict[str, int] = Counter()
    for row in policy_rows:
        node_id = DIVISION_TO_NODE.get(row_value(row, "Division"))
        if node_id:
            policy_counter[node_id] += 1
    report["policy_rows_by_node"] = dict(sorted(policy_counter.items()))

    for row in stock_rows:
        division = row_value(row, "Division")
        node_id = DIVISION_TO_NODE.get(division)
        article = canonical_article_id(row_value(row, "Numéro d'article", "NumÃ©ro d'article"))
        item_id = f"item:{article}" if article else ""
        qty = to_float(row_value(row, "Stock Total"))
        source_unit = normalize_unit(row_value(row, "Unité de quantité de base", "UnitÃ© de quantitÃ© de base"))
        if not node_id or not item_id or qty is None:
            report["stock_rows_skipped"] += 1
            report["skipped_stock_rows"].append(
                {"division": division, "item_id": item_id, "reason": "missing_mapping_or_qty"}
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
                {"node_id": node_id, "item_id": item_id, "reason": "node_missing_in_graph"}
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

    for row in policy_rows:
        division = row_value(row, "Division")
        node_id = DIVISION_TO_NODE.get(division)
        article = canonical_article_id(row_value(row, "Numéro d'article", "NumÃ©ro d'article"))
        item_id = f"item:{article}" if article else ""
        safety_time_days = to_float(
            row_value(
                row,
                "Délai de sécurité (en jours ouvrés)",
                "DÃ©lai de sÃ©curitÃ© (en jours ouvrÃ©s)",
            )
        )
        safety_stock_qty = to_float(row_value(row, "Stock de sécurité", "Stock de sÃ©curitÃ©"))
        source_unit = normalize_unit(row_value(row, "Unité de quantité de base", "UnitÃ© de quantitÃ© de base"))
        if not node_id or not item_id:
            report["skipped_policy_rows"].append(
                {"division": division, "item_id": item_id, "reason": "missing_mapping"}
            )
            continue
        node = node_by_id.get(node_id)
        if not isinstance(node, dict):
            report["skipped_policy_rows"].append(
                {"node_id": node_id, "item_id": item_id, "reason": "node_missing_in_graph"}
            )
            continue
        if (node_id, item_id) not in modeled_pairs:
            report["skipped_policy_rows"].append(
                {"node_id": node_id, "item_id": item_id, "reason": "node_item_pair_not_modeled"}
            )
            continue
        payload = set_state_mrp_policy(
            node=node,
            item_id=item_id,
            safety_time_days=safety_time_days,
            safety_stock_qty=safety_stock_qty,
            source_unit=source_unit,
            default_uom=item_unit_map.get(item_id, source_unit),
            source="mrp_policy_sheet",
        )
        if payload is not None:
            report["mrp_policies_applied"].append(payload)

    for (node_id, item_id), override in sorted(MRP_POLICY_OVERRIDES.items()):
        node = node_by_id.get(node_id)
        if not isinstance(node, dict):
            report["skipped_policy_rows"].append(
                {"node_id": node_id, "item_id": item_id, "reason": "override_node_missing_in_graph"}
            )
            continue
        payload = set_state_mrp_policy(
            node=node,
            item_id=item_id,
            safety_time_days=to_float(override.get("safety_time_days")),
            safety_stock_qty=to_float(override.get("safety_stock_qty")),
            source_unit=normalize_unit(override.get("uom") or item_unit_map.get(item_id, "")),
            default_uom=item_unit_map.get(item_id, "UN"),
            source=str(override.get("source") or "mrp_policy_override"),
        )
        if payload is None:
            report["skipped_policy_rows"].append(
                {"node_id": node_id, "item_id": item_id, "reason": "override_state_missing"}
            )
            continue
        report["mrp_policy_overrides_applied"].append(payload)

    if args.policy_xlsx:
        current_tables = read_xlsx_tables(Path(args.policy_xlsx))
        sheets = [name for name in current_tables if name.casefold() == "politique de stock mrp"]
        if len(sheets) != 1 or not current_tables[sheets[0]]:
            raise ValueError("Expected one non-empty stock-policy sheet in --policy-xlsx")
        report["selected_source_policy"] = apply_source_mrp_policy_rows(
            data, current_tables[sheets[0]], source=f"{args.policy_xlsx}/{sheets[0]}",
        )
        with Path(args.policy_xlsx).open("rb") as stream:
            policy_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        data.setdefault("meta", {})["selected_stock_policy_source"] = {
            "file": str(args.policy_xlsx), "sheet": sheets[0], "sha256": policy_sha256,
            "historical_overrides_superseded": True,
        }

    if not args.include_mrp_lot_policies and not args.apply_safe_lot_sizes:
        report["skipped_lot_rows"].append({"reason": "lot_rule_injection_not_requested"})

    for row in lot_rows:
        division = row_value(row, "Division")
        node_id = DIVISION_TO_NODE.get(division)
        article = canonical_article_id(row_value(row, "Numéro d'article", "NumÃ©ro d'article"))
        item_id = f"item:{article}" if article else ""
        fixed = to_float(row_value(row, "Taille de lot fixe")) or 0.0
        max_lot = to_float(row_value(row, "Taille de lot maximale")) or 0.0
        min_lot = to_float(row_value(row, "Taille de lot minimale")) or 0.0
        if not node_id or not item_id:
            report["skipped_lot_rows"].append(
                {"division": division, "item_id": item_id, "reason": "missing_mapping"}
            )
            continue
        node = node_by_id.get(node_id)
        if not isinstance(node, dict):
            report["skipped_lot_rows"].append(
                {"node_id": node_id, "item_id": item_id, "reason": "node_missing_in_graph"}
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
                {"node_id": node_id, "item_id": item_id, "reason": "matching_output_process_missing"}
            )
            continue

        fixed_lot = fixed
        normalization_rule = ""
        if fixed_lot <= 0 and max_lot > 0 and abs(max_lot - min_lot) <= 1e-9:
            fixed_lot = max_lot
            normalization_rule = "min_equals_max_as_fixed"

        output_uom = normalize_unit(item_unit_map.get(item_id, "UN"))
        if args.include_mrp_lot_policies:
            process["lot_sizing"] = {
                "fixed_lot_qty": fixed_lot if fixed_lot > 0 else 0.0,
                "min_lot_qty": max(0.0, min_lot),
                "max_lot_qty": max(0.0, max_lot),
                "uom": output_uom,
                "source": "mrp_lot_sheet",
                "normalization_rule": normalization_rule,
            }
            report["lot_policies_applied"].append(
                {
                    "node_id": node_id,
                    "process_id": str(process.get("id") or ""),
                    "item_id": item_id,
                    "fixed_lot_qty": fixed_lot if fixed_lot > 0 else 0.0,
                    "min_lot_qty": max(0.0, min_lot),
                    "max_lot_qty": max(0.0, max_lot),
                    "uom": output_uom,
                    "normalization_rule": normalization_rule,
                }
            )

        if args.apply_safe_lot_sizes:
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
                        "reason": "ambiguous_lot_rule_for_legacy_batch_size",
                        "fixed": fixed,
                        "max": max_lot,
                        "min": min_lot,
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
    report["skipped_stock_rows"].sort(
        key=lambda row: (row.get("node_id", ""), row.get("item_id", ""), row.get("reason", ""))
    )
    report["mrp_policies_applied"].sort(key=lambda row: (row["node_id"], row["item_id"]))
    report["mrp_policy_overrides_applied"].sort(key=lambda row: (row["node_id"], row["item_id"]))
    report["skipped_policy_rows"].sort(
        key=lambda row: (row.get("node_id", ""), row.get("item_id", ""), row.get("reason", ""))
    )
    report["lot_policies_applied"].sort(key=lambda row: (row["node_id"], row["item_id"]))
    report["lot_updates"].sort(key=lambda row: (row["node_id"], row["item_id"]))
    report["skipped_lot_rows"].sort(
        key=lambda row: (row.get("node_id", ""), row.get("item_id", ""), row.get("reason", ""))
    )

    meta = data.get("meta") or {}
    meta["mrp_seed"] = {
        "generated_at_utc": report["generated_at_utc"],
        "stocks_mrp_xlsx": str(mrp_xlsx),
        "snapshot_at_utc": snapshot_iso,
        "stock_rows_injected": report["stock_rows_injected"],
        "inventory_states_created": report["inventory_states_created"],
        "inventory_states_updated": report["inventory_states_updated"],
        "mrp_policies_applied": len(report["mrp_policies_applied"]),
        "mrp_policy_overrides_applied": len(report["mrp_policy_overrides_applied"]),
        "lot_policies_applied": len(report["lot_policies_applied"]),
        "legacy_batch_updates": len(report["lot_updates"]),
    }
    data["meta"] = meta
    if args.customer_demand_xlsx:
        report["customer_demand_source"] = apply_customer_demand_source(
            data, Path(args.customer_demand_xlsx)
        )

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
        f"- MRP policy rows applied: `{len(report['mrp_policies_applied'])}`",
        f"- MRP policy overrides applied: `{len(report['mrp_policy_overrides_applied'])}`",
        f"- MRP lot policies applied: `{len(report['lot_policies_applied'])}`",
        f"- Legacy batch-size updates: `{len(report['lot_updates'])}`",
        "",
        "## Injected stock rows",
    ]
    for row in report["qty_by_node_item"]:
        before = "none" if row["initial_before"] is None else f"{row['initial_before']}"
        lines.append(
            f"- {row['node_id']} / {row['item_id']}: `{before}` -> `{row['initial_after']}` `{row['uom']}` "
            f"(source `{row['source_qty']}` `{row['source_unit']}`)"
        )
    if report["mrp_policies_applied"]:
        lines.extend(["", "## Injected MRP safety policies"])
        for row in report["mrp_policies_applied"]:
            lines.append(
                f"- {row['node_id']} / {row['item_id']}: safety time `{row['safety_time_days']}` d, "
                f"safety stock `{row['safety_stock_qty']}` `{row['uom']}` (source `{row['source']}`)"
            )
    if report["mrp_policy_overrides_applied"]:
        lines.extend(["", "## Applied policy overrides"])
        for row in report["mrp_policy_overrides_applied"]:
            lines.append(
                f"- {row['node_id']} / {row['item_id']}: safety time `{row['safety_time_days']}` d, "
                f"safety stock `{row['safety_stock_qty']}` `{row['uom']}` (source `{row['source']}`)"
            )
    if report["lot_policies_applied"]:
        lines.extend(["", "## Injected MRP lot policies"])
        for row in report["lot_policies_applied"]:
            lines.append(
                f"- {row['node_id']} / {row['process_id']} / {row['item_id']}: "
                f"fixed `{row['fixed_lot_qty']}`, min `{row['min_lot_qty']}`, max `{row['max_lot_qty']}` "
                f"`{row['uom']}` ({row['normalization_rule'] or 'direct'})"
            )
    if report["skipped_stock_rows"]:
        lines.extend(["", "## Skipped stock rows"])
        for row in report["skipped_stock_rows"]:
            lines.append(
                f"- {row.get('node_id', row.get('division', '?'))} / {row.get('item_id', '?')}: `{row['reason']}`"
            )
    if report["skipped_policy_rows"]:
        lines.extend(["", "## Skipped policy rows"])
        for row in report["skipped_policy_rows"]:
            lines.append(
                f"- {row.get('node_id', row.get('division', '?'))} / {row.get('item_id', '?')}: `{row['reason']}`"
            )
    if report["lot_updates"]:
        lines.extend(["", "## Legacy batch-size updates"])
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
