"""Executed flows, physical material balances and simulation valuation contracts."""
from __future__ import annotations
from collections import defaultdict
import html, math
from pathlib import Path
from typing import Any
from etudecas.case_config import ITEM_DISPLAY_REFERENCE_NOTES
from etudecas.visualization.maps.map_payload_builder import (
    read_csv_rows,
    display_node_label,
    is_simulation_hidden_item,
    is_upstream_internal_site,
    fmt_qty,
)






SIMULATION_LEGACY_KEYS = (
    "factory_hover_series",
    "factory_hover_images",
    "supplier_hover_images",
    "distribution_center_hover_images",
    "customer_hover_images",
    "simulation_diagnostics",
    "model_panel",
    "global_kpi_tree",
    "lot_trace",
    "material_balance_rows",
)


def normalize_unit_label(unit: Any) -> str:
    value = str(unit or "").strip().upper()
    aliases = {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITS": "UN",
    }
    return aliases.get(value, value)


def convert_unit_quantity(value: float, from_unit: str, to_unit: str) -> float:
    src = normalize_unit_label(from_unit)
    dst = normalize_unit_label(to_unit)
    if not src or not dst or src == dst:
        return value
    if src == "G" and dst == "KG":
        return value / 1000.0
    if src == "KG" and dst == "G":
        return value * 1000.0
    return value


def build_material_balance_table_rows(
    raw: dict[str, Any],
    *,
    demand_service_csv: Path,
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    sim_dc_stocks_csv: Path | None = None,
    supplier_shipments_csv: Path,
    safety_reference_csv: Path | None = None,
    lot_events_csv: Path | None = None,
) -> list[dict[str, Any]]:
    item_labels = _build_item_label_lookup(raw)
    node_type_by_id = _build_node_type_lookup(raw)
    demand_rows = read_csv_rows(demand_service_csv)
    input_rows = read_csv_rows(sim_input_stocks_csv)
    output_rows = read_csv_rows(sim_output_products_csv)
    dc_stock_rows = read_csv_rows(sim_dc_stocks_csv) if sim_dc_stocks_csv else []
    shipment_rows = read_csv_rows(supplier_shipments_csv)
    safety_reference_rows = read_csv_rows(safety_reference_csv) if safety_reference_csv else []
    safety_reference_by_pair: dict[tuple[str, str], dict[str, Any]] = {
        (str(row.get("node_id") or ""), str(row.get("item_id") or "")): row
        for row in safety_reference_rows
        if str(row.get("node_id") or "") and str(row.get("item_id") or "")
    }
    max_day = max(
        [
            int(_to_float(row.get("day")) or 0)
            for dataset in (demand_rows, input_rows, output_rows, dc_stock_rows)
            for row in dataset
        ]
        or [0]
    )
    sim_days = max(1, max_day + 1)
    shipment_rows = [row for row in shipment_rows if 0 <= int(_to_float(row.get("day")) or 0) < sim_days
                     and str(row.get("departure_executed", "")).lower() not in {"false", "0"}]
    year_count = max(1, int(math.ceil(sim_days / 365.0)))

    def year_for_day(day: int) -> int:
        return max(1, min(year_count, int(day // 365) + 1))

    def year_days(year: int) -> int:
        start_day = (year - 1) * 365
        if start_day >= sim_days:
            return 0
        return max(0, min(365, sim_days - start_day))

    def new_yearly_payload() -> dict[str, dict[str, float]]:
        return {
            str(year): {
                "days": float(year_days(year)),
                "planned_qty": 0.0,
                "delivered_qty": 0.0,
                "consumed_qty": 0.0,
                "initial_qty": 0.0,
                "final_stock_qty": 0.0,
            }
            for year in range(1, year_count + 1)
        }

    def ensure_yearly(row: dict[str, Any]) -> dict[str, dict[str, float]]:
        yearly = row.get("yearly")
        if not isinstance(yearly, dict):
            yearly = new_yearly_payload()
            row["yearly"] = yearly
        return yearly

    def add_yearly(row: dict[str, Any], year: int, field: str, value: float) -> None:
        yearly = ensure_yearly(row)
        bucket = yearly.setdefault(str(year), {"days": float(year_days(year))})
        bucket[field] = max(0.0, float(bucket.get(field, 0.0) or 0.0) + max(0.0, value))

    demand_total_by_item: dict[str, float] = defaultdict(float)
    served_total_by_item: dict[str, float] = defaultdict(float)
    demand_by_item_year: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    served_by_item_year: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in demand_rows:
        if str(row.get("node_id") or "") not in {
            node_id for node_id, node_type in node_type_by_id.items() if node_type == "customer"
        }:
            continue
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        day = int(_to_float(row.get("day")) or 0)
        year = year_for_day(day)
        demand_qty = max(0.0, _to_float(row.get("demand_qty")) or 0.0)
        served_qty = max(0.0, _to_float(row.get("served_qty")) or 0.0)
        demand_total_by_item[item_id] += max(0.0, _to_float(row.get("demand_qty")) or 0.0)
        served_total_by_item[item_id] += max(0.0, _to_float(row.get("served_qty")) or 0.0)
        demand_by_item_year[item_id][year] += demand_qty
        served_by_item_year[item_id][year] += served_qty

    produced_total_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    produced_by_pair_year: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    latest_output_stock_by_pair: dict[tuple[str, str], tuple[int, float]] = {}
    output_stock_end_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in output_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(_to_float(row.get("day")) or 0)
        year = year_for_day(day)
        produced_qty = max(0.0, _to_float(row.get("produced_qty")) or 0.0)
        produced_total_by_pair[(node_id, item_id)] += produced_qty
        produced_by_pair_year[(node_id, item_id)][year] += produced_qty
        stock_value = max(0.0, _to_float(row.get("stock_end_of_day")) or 0.0)
        key = (node_id, item_id)
        output_stock_end_by_pair_day[key][day] = stock_value
        prev = latest_output_stock_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_output_stock_by_pair[key] = (day, stock_value)

    latest_input_stock_by_pair: dict[tuple[str, str], tuple[int, float]] = {}
    input_stock_before_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    input_stock_end_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(_to_float(row.get("day")) or 0)
        before_value = max(0.0, _to_float(row.get("stock_before_production")) or 0.0)
        stock_value = max(0.0, _to_float(row.get("stock_end_of_day")) or 0.0)
        key = (node_id, item_id)
        input_stock_before_by_pair_day[key][day] = before_value
        input_stock_end_by_pair_day[key][day] = stock_value
        prev = latest_input_stock_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_input_stock_by_pair[key] = (day, stock_value)

    dc_stock_end_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in dc_stock_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(_to_float(row.get("day")) or 0)
        dc_stock_end_by_pair_day[(node_id, item_id)][day] = max(
            0.0,
            _to_float(row.get("stock_end_of_day")) or 0.0,
        )

    shipped_total_to_pair: dict[tuple[str, str], float] = defaultdict(float)
    shipped_total_from_pair: dict[tuple[str, str], float] = defaultdict(float)
    shipped_to_pair_year: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    shipped_from_pair_year: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in shipment_rows:
        src_node_id = str(row.get("src_node_id") or "")
        node_id = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(_to_float(row.get("day")) or 0)
        year = year_for_day(day)
        shipped_qty = max(0.0, _to_float(row.get("shipped_qty")) or 0.0)
        shipped_total_to_pair[(node_id, item_id)] += shipped_qty
        shipped_to_pair_year[(node_id, item_id)][year] += shipped_qty
        if src_node_id:
            shipped_total_from_pair[(src_node_id, item_id)] += shipped_qty
            shipped_from_pair_year[(src_node_id, item_id)][year] += shipped_qty

    initial_stock_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    unit_by_pair: dict[tuple[str, str], str] = {}
    pf_initial_by_item: dict[str, float] = defaultdict(float)
    pf_unit_by_item: dict[str, str] = {}
    safety_policy_by_pair: dict[tuple[str, str], dict[str, float]] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        for state in (((node.get("inventory") or {}).get("states") or [])):
            item_id = str(state.get("item_id") or "")
            if not item_id:
                continue
            initial_qty = max(0.0, _to_float(state.get("initial")) or 0.0)
            key = (node_id, item_id)
            initial_stock_by_pair[key] += initial_qty
            unit = normalize_unit_label(state.get("uom"))
            if unit and key not in unit_by_pair:
                unit_by_pair[key] = unit
            if node_type in {"distribution_center", "customer"}:
                pf_initial_by_item[item_id] += initial_qty
                if unit and item_id not in pf_unit_by_item:
                    pf_unit_by_item[item_id] = unit
            mrp_policy = state.get("mrp_policy") or {}
            safety_time_days = max(0.0, _to_float(mrp_policy.get("safety_time_days")) or 0.0)
            safety_stock_qty = 0.0
            if safety_time_days > 0.0:
                safety_policy_by_pair[key] = {
                    "safety_time_days": safety_time_days,
                    "safety_stock_qty": safety_stock_qty,
                }

    def start_stock_for_year(
        pair: tuple[str, str],
        year: int,
        *,
        initial_qty: float,
        before_by_pair_day: dict[tuple[str, str], dict[int, float]] | None = None,
        end_by_pair_day: dict[tuple[str, str], dict[int, float]] | None = None,
    ) -> float:
        start_day = (year - 1) * 365
        if before_by_pair_day:
            before_by_day = before_by_pair_day.get(pair, {})
            if start_day in before_by_day:
                return max(0.0, before_by_day[start_day])
        if start_day <= 0:
            return max(0.0, initial_qty)
        end_by_day = (end_by_pair_day or {}).get(pair, {})
        if (start_day - 1) in end_by_day:
            return max(0.0, end_by_day[start_day - 1])
        previous_days = [day for day in end_by_day if day < start_day]
        if previous_days:
            return max(0.0, end_by_day[max(previous_days)])
        return max(0.0, initial_qty)

    def end_stock_for_year(
        pair: tuple[str, str],
        year: int,
        *,
        fallback_qty: float,
        end_by_pair_day: dict[tuple[str, str], dict[int, float]] | None = None,
    ) -> float:
        end_day = min(sim_days - 1, year * 365 - 1)
        end_by_day = (end_by_pair_day or {}).get(pair, {})
        if end_day in end_by_day:
            return max(0.0, end_by_day[end_day])
        previous_days = [day for day in end_by_day if day <= end_day]
        if previous_days:
            return max(0.0, end_by_day[max(previous_days)])
        return max(0.0, fallback_qty)

    material_rows_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        for proc in (node.get("processes") or []):
            batch_size = max(1.0, _to_float(proc.get("batch_size")) or 1.0)
            outputs = [out for out in (proc.get("outputs") or []) if str(out.get("item_id") or "")]
            inputs = [inp for inp in (proc.get("inputs") or []) if str(inp.get("item_id") or "")]
            if not outputs or not inputs:
                continue
            for out in outputs:
                out_item = str(out.get("item_id") or "")
                full_demand_qty = demand_total_by_item.get(out_item, 0.0)
                actual_prod_qty = produced_total_by_pair.get((node_id, out_item), 0.0)
                if full_demand_qty <= 0.0 and actual_prod_qty <= 0.0:
                    continue
                for inp in inputs:
                    input_item = str(inp.get("item_id") or "")
                    if is_simulation_hidden_item(input_item):
                        continue
                    ratio_qty = max(0.0, _to_float(inp.get("ratio_per_batch")) or 0.0)
                    ratio_unit = normalize_unit_label(inp.get("ratio_unit"))
                    pair_key = (node_id, input_item)
                    unit = unit_by_pair.get(pair_key) or ratio_unit or ""
                    need_qty = convert_unit_quantity((ratio_qty / batch_size) * full_demand_qty, ratio_unit, unit)
                    consumed_qty = convert_unit_quantity((ratio_qty / batch_size) * actual_prod_qty, ratio_unit, unit)
                    bucket = material_rows_by_pair.setdefault(
                        pair_key,
                        {
                            "scope": "material",
                            "scope_label": "Matiere",
                            "node_id": node_id,
                            "item_id": input_item,
                            "item_label": item_labels.get(input_item, _compact_item_label(input_item)),
                            "node_label": display_node_label(node_id),
                            "planned_qty": 0.0,
                            "initial_qty": initial_stock_by_pair.get(pair_key, 0.0),
                            "delivered_qty": shipped_total_to_pair.get(pair_key, 0.0),
                            "consumed_qty": 0.0,
                            "final_stock_qty": (latest_input_stock_by_pair.get(pair_key) or (0, 0.0))[1],
                            "unit": unit or ratio_unit or "",
                            "yearly": new_yearly_payload(),
                        },
                    )
                    bucket["planned_qty"] += need_qty
                    bucket["consumed_qty"] += consumed_qty
                    for year in range(1, year_count + 1):
                        year_demand_qty = demand_by_item_year[out_item].get(year, 0.0)
                        year_produced_qty = produced_by_pair_year[(node_id, out_item)].get(year, 0.0)
                        add_yearly(
                            bucket,
                            year,
                            "planned_qty",
                            convert_unit_quantity((ratio_qty / batch_size) * year_demand_qty, ratio_unit, unit),
                        )
                        add_yearly(
                            bucket,
                            year,
                            "consumed_qty",
                            convert_unit_quantity((ratio_qty / batch_size) * year_produced_qty, ratio_unit, unit),
                        )

    rows: list[dict[str, Any]] = []
    for item_id in sorted(demand_total_by_item):
        pf_policy_pair = next(
            (
                pair
                for pair in sorted(safety_policy_by_pair)
                if pair[1] == item_id and node_type_by_id.get(pair[0]) in {"distribution_center", "customer"}
            ),
            ("DC / client final", item_id),
        )
        pf_yearly = new_yearly_payload()
        for year in range(1, year_count + 1):
            year_planned = demand_by_item_year[item_id].get(year, 0.0)
            year_served = served_by_item_year[item_id].get(year, 0.0)
            pf_yearly[str(year)]["planned_qty"] = year_planned
            pf_yearly[str(year)]["delivered_qty"] = year_served
            pf_yearly[str(year)]["consumed_qty"] = year_served
            initial_total = 0.0
            final_total = 0.0
            for pair, initial_qty in initial_stock_by_pair.items():
                node_id, pair_item_id = pair
                if pair_item_id != item_id or node_type_by_id.get(node_id) not in {"distribution_center", "customer"}:
                    continue
                if node_type_by_id.get(node_id) == "distribution_center":
                    initial_total += start_stock_for_year(
                        pair,
                        year,
                        initial_qty=initial_qty,
                        end_by_pair_day=dc_stock_end_by_pair_day,
                    )
                    final_total += end_stock_for_year(
                        pair,
                        year,
                        fallback_qty=initial_qty,
                        end_by_pair_day=dc_stock_end_by_pair_day,
                    )
                elif year == 1:
                    initial_total += max(0.0, initial_qty)
                    final_total += max(0.0, initial_qty)
            pf_yearly[str(year)]["initial_qty"] = initial_total
            pf_yearly[str(year)]["final_stock_qty"] = final_total
        rows.append(
            {
                "scope": "pf",
                "scope_label": "PF",
                "node_id": pf_policy_pair[0],
                "item_id": item_id,
                "item_label": item_labels.get(item_id, _compact_item_label(item_id)),
                "node_label": "DC / client final",
                "planned_qty": demand_total_by_item.get(item_id, 0.0),
                "initial_qty": pf_initial_by_item.get(item_id, 0.0),
                "delivered_qty": served_total_by_item.get(item_id, 0.0),
                "consumed_qty": served_total_by_item.get(item_id, 0.0),
                "unit": pf_unit_by_item.get(item_id, ""),
                "gap_vs_need_qty": served_total_by_item.get(item_id, 0.0) - demand_total_by_item.get(item_id, 0.0),
                "diagnostic": "demande finale issue du scenario courant",
                "yearly": pf_yearly,
            }
        )

    upstream_pfi_rows_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not is_upstream_internal_site(node_id):
            continue
        output_item_ids: set[str] = set()
        for proc in (node.get("processes") or []):
            for out in (proc.get("outputs") or []):
                item_id = str(out.get("item_id") or "")
                if item_id:
                    output_item_ids.add(item_id)
        for pair_key in list(shipped_total_from_pair.keys()):
            pair_node_id, item_id = pair_key
            if pair_node_id == node_id and item_id:
                output_item_ids.add(item_id)
        for item_id in sorted(output_item_ids):
            pair_key = (node_id, item_id)
            produced_qty = produced_total_by_pair.get(pair_key, 0.0)
            shipped_qty = shipped_total_from_pair.get(pair_key, 0.0)
            initial_qty = initial_stock_by_pair.get(pair_key, 0.0)
            final_stock_qty = (latest_output_stock_by_pair.get(pair_key) or (0, 0.0))[1]
            if produced_qty <= 0.0 and shipped_qty <= 0.0 and initial_qty <= 0.0 and final_stock_qty <= 0.0:
                continue
            pfi_yearly = new_yearly_payload()
            for year in range(1, year_count + 1):
                year_produced = produced_by_pair_year[pair_key].get(year, 0.0)
                year_shipped = shipped_from_pair_year[pair_key].get(year, 0.0)
                pfi_yearly[str(year)]["planned_qty"] = max(year_produced, year_shipped)
                pfi_yearly[str(year)]["delivered_qty"] = year_shipped
                pfi_yearly[str(year)]["consumed_qty"] = year_produced
                pfi_yearly[str(year)]["initial_qty"] = start_stock_for_year(
                    pair_key,
                    year,
                    initial_qty=initial_qty,
                    end_by_pair_day=output_stock_end_by_pair_day,
                )
                pfi_yearly[str(year)]["final_stock_qty"] = end_stock_for_year(
                    pair_key,
                    year,
                    fallback_qty=initial_qty,
                    end_by_pair_day=output_stock_end_by_pair_day,
                )
            upstream_pfi_rows_by_pair[pair_key] = {
                "scope": "pfi",
                "scope_label": "PFI",
                "node_id": node_id,
                "item_id": item_id,
                "item_label": item_labels.get(item_id, _compact_item_label(item_id)),
                "node_label": display_node_label(node_id),
                "planned_qty": max(produced_qty, shipped_qty),
                "initial_qty": initial_qty,
                "delivered_qty": shipped_qty,
                "consumed_qty": produced_qty,
                "final_stock_qty": final_stock_qty,
                "unit": unit_by_pair.get(pair_key, ""),
                "gap_vs_need_qty": shipped_qty - max(produced_qty, shipped_qty),
                "diagnostic": "sortie PFI du centre interne D-1450 vers les usines aval",
                "yearly": pfi_yearly,
            }
    rows.extend(
        row for _, row in sorted(upstream_pfi_rows_by_pair.items(), key=lambda item: (item[0][0], item[0][1]))
    )

    for pair_key, row in sorted(material_rows_by_pair.items(), key=lambda item: (item[0][0], item[0][1])):
        if is_simulation_hidden_item(str(row.get("item_id") or "")):
            continue
        initial_qty = max(0.0, row.get("initial_qty") or 0.0)
        delivered_qty = max(0.0, row.get("delivered_qty") or 0.0)
        consumed_qty = max(0.0, row.get("consumed_qty") or 0.0)
        final_stock_qty = max(0.0, row.get("final_stock_qty") or 0.0)
        planned_qty = max(0.0, row.get("planned_qty") or 0.0)
        gap_vs_need_qty = consumed_qty - planned_qty
        balance_gap = (initial_qty + delivered_qty) - consumed_qty - final_stock_qty
        tol = max(1.0, abs(consumed_qty) * 0.02)
        if consumed_qty <= 1e-9 and delivered_qty <= 1e-9 and initial_qty > 0:
            diagnostic = "coherent dormant: stock initial couvre le run"
        elif abs(balance_gap) > tol:
            diagnostic = "stock balance mismatch vs BOM consumption"
        elif delivered_qty > 0.0 or consumed_qty > 0.0:
            diagnostic = "active on current run"
        else:
            diagnostic = "inactive on current run"
        yearly = ensure_yearly(row)
        for year in range(1, year_count + 1):
            bucket = yearly[str(year)]
            bucket["delivered_qty"] = shipped_to_pair_year[pair_key].get(year, 0.0)
            bucket["initial_qty"] = start_stock_for_year(
                pair_key,
                year,
                initial_qty=initial_qty,
                before_by_pair_day=input_stock_before_by_pair_day,
                end_by_pair_day=input_stock_end_by_pair_day,
            )
            bucket["final_stock_qty"] = end_stock_for_year(
                pair_key,
                year,
                fallback_qty=initial_qty,
                end_by_pair_day=input_stock_end_by_pair_day,
            )
        rows.append(
            {
                **row,
                "gap_vs_need_qty": gap_vs_need_qty,
                "diagnostic": diagnostic,
            }
        )

    for row in rows:
        pair = (str(row.get("node_id") or ""), str(row.get("item_id") or ""))
        safety_reference = safety_reference_by_pair.get(pair) or {}
        safety_policy = safety_policy_by_pair.get(pair) or {}
        safety_days = max(
            0.0,
            (
                _to_float(safety_reference.get("safety_time_days"))
                if safety_reference
                else _to_float(safety_policy.get("safety_time_days"))
            )
            or 0.0,
        )
        explicit_safety_stock = max(
            0.0,
            (
                _to_float(safety_reference.get("explicit_safety_stock_qty"))
                if safety_reference
                else _to_float(safety_policy.get("safety_stock_qty"))
            )
            or 0.0,
        )
        avg_daily_need = max(
            0.0,
            (
                _to_float(safety_reference.get("planned_avg_daily_demand_qty"))
                if safety_reference
                else (max(0.0, _to_float(row.get("planned_qty")) or 0.0) / float(sim_days))
            )
            or 0.0,
        )
        stock_equiv_safety = max(
            0.0,
            (
                _to_float(safety_reference.get("stock_equiv_safety_time_qty"))
                if safety_reference
                else avg_daily_need * safety_days
            )
            or 0.0,
        )
        row["avg_daily_need_qty"] = avg_daily_need
        row["safety_time_days"] = safety_days
        row["stock_equiv_safety_time_qty"] = stock_equiv_safety
        row["explicit_safety_stock_qty"] = explicit_safety_stock
        row["effective_reference_stock_qty"] = max(
            explicit_safety_stock,
            stock_equiv_safety,
            (_to_float(safety_reference.get("effective_reference_stock_qty")) if safety_reference else 0.0) or 0.0,
        )
        calendar_days = _to_float(safety_reference.get("safety_time_calendar_days"))
        if calendar_days is None:
            calendar_days = _to_float(safety_policy.get("safety_time_calendar_days"))
        row["safety_time_calendar_days"] = calendar_days
        row["safety_time_basis"] = str(safety_reference.get("safety_time_calendar") or "source_working_days_unverified")
        row["safety_time_effective_at_day"] = _to_float(safety_reference.get("safety_time_effective_at_day"))
        row["safety_time_days"] = _to_float(safety_reference.get("safety_time_source_days")) or safety_days
        if safety_days > 0 and calendar_days is None:
            row["stock_equiv_safety_time_qty"] = None
        elif not safety_reference and calendar_days is not None:
            row["stock_equiv_safety_time_qty"] = avg_daily_need * calendar_days
    physical_path = lot_events_csv or sim_input_stocks_csv.parent / "production_lot_events.csv"
    apply_physical_material_balances(
        rows, read_csv_rows(physical_path) if physical_path.exists() else [], input_rows,
        horizon_days=sim_days, source_available=physical_path.exists(),
    )
    return rows


def render_material_balance_table_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan='13'>Aucune ligne de bilan disponible.</td></tr>"
    html_rows: list[str] = []
    for row in rows:
        scope = str(row.get("scope") or "")
        if scope == "pf":
            badge_class = "scopeBadge scopeFinal"
        elif scope == "pfi":
            badge_class = "scopeBadge scopeIntermediate"
        else:
            badge_class = "scopeBadge"
        html_rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td><span class=\"{badge_class}\">{html.escape(str(row.get('scope_label') or ''))}</span></td>",
                    f"<td>{html.escape(_compact_item_label(str(row.get('item_id') or '')))}</td>",
                    f"<td>{html.escape(str(row.get('node_label') or ''))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('planned_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('avg_daily_need_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('safety_time_days'), 1))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('stock_equiv_safety_time_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('initial_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('delivered_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('consumed_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('gap_vs_need_qty'), 3))}</td>",
                    f"<td>{html.escape(str(row.get('unit') or ''))}</td>",
                    f"<td>{html.escape(str(row.get('diagnostic') or ''))}</td>",
                    "</tr>",
                ]
            )
        )
    return "".join(html_rows)


def build_simulation_payload_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Describe the simulation domain payload without duplicating heavy data."""

    lot_trace = payload.get("lot_trace", {}) if isinstance(payload.get("lot_trace"), dict) else {}
    return {
        "domain": "simulation",
        "generic_outputs": ["time_series", "events", "lots", "diagnostics"],
        "legacy_keys": [key for key in SIMULATION_LEGACY_KEYS if key in payload],
        "counts": {
            "factory_series": _count_mapping(payload.get("factory_hover_series")),
            "factory_panels": _count_mapping(payload.get("factory_hover_images")),
            "supplier_panels": _count_mapping(payload.get("supplier_hover_images")),
            "dc_panels": _count_mapping(payload.get("distribution_center_hover_images")),
            "customer_panels": _count_mapping(payload.get("customer_hover_images")),
            "lot_events": _count_sequence(lot_trace.get("events")),
            "lot_genealogy": _count_sequence(lot_trace.get("genealogy")),
            "lot_options": _count_sequence(lot_trace.get("lot_options")),
            "material_balance_rows": _count_sequence(payload.get("material_balance_rows")),
        },
    }




def _count_mapping(value: Any) -> int:
    return len(value) if isinstance(value, dict) else 0


def _count_sequence(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _compact_item_label(item_id: str) -> str:
    raw = str(item_id or "").strip()
    if raw.startswith("item:"):
        return raw.split(":", 1)[1]
    return raw or "n/a"


def _build_node_type_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        out[node_id] = str(node.get("type") or "")
    return out


def _build_item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code or name or _compact_item_label(item_id)
        out[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return out


# Consolidated from physical_material_balance: unchanged business definitions.

def apply_physical_material_balances(
    rows: list[dict[str, Any]], events: list[dict[str, Any]],
    stock_rows: list[dict[str, Any]], *, horizon_days: int, source_available: bool,
) -> None:
    def number(value: Any) -> float:
        return float(value or 0)

    ledger = defaultdict(list)
    snapshots = defaultdict(dict)
    for event in events:
        day = int(number(event.get("day")))
        if 0 <= day < horizon_days:
            ledger[(event.get("node_id"), event.get("item_id"))].append(event)
    for stock in stock_rows:
        day = int(number(stock.get("day")))
        if 0 <= day < horizon_days:
            snapshots[(stock.get("node_id"), stock.get("item_id"))][day] = number(stock.get("stock_end_of_day"))

    receipt_types = {"lane_receipt", "opening_purchase_order_receipt", "external_procurement_receipt", "estimated_source_receipt", "estimated_capacity_receipt"}
    consume_types = {"production_consume", "production_consume_reference_transition"}
    outflow_types = {"shipment_reserve", "demand_service", "writeoff", "stock_writeoff"}
    adjustment_types = {"stock_reconciliation", "production_output"}
    availability_types = {"stock_availability_hold", "stock_availability_release"}
    known_types = receipt_types | consume_types | outflow_types | adjustment_types | availability_types | {"opening_stock", "lane_ship", "opening_production_order"}

    for pair, pair_events in ledger.items():
        held_changes = defaultdict(float)
        for event in pair_events:
            kind = event.get("event_type")
            if kind in availability_types:
                held_changes[int(number(event.get("day")))] += (
                    number(event.get("qty")) * (1 if kind == "stock_availability_hold" else -1)
                )
        if not held_changes:
            continue
        # Historical stock CSVs contain usable stock after reservations. Held
        # quantities remain physically present; a release changes usability only.
        changes = sorted(held_changes.items())
        position = 0
        held_qty = 0.0
        for day in sorted(snapshots[pair]):
            while position < len(changes) and changes[position][0] <= day:
                held_qty += changes[position][1]
                position += 1
            snapshots[pair][day] += held_qty

    for row in rows:
        scope = row.get("scope")
        if scope != "material":
            # These historical rows describe service (PF) or production and
            # dispatch (PFI), not a material stock conservation equation.
            row["balance_status"] = "not_applicable"
            row["physical_source_available"] = False
            row["quantity_basis"] = "customer_service" if scope == "pf" else "production_and_dispatch"
            row["source_notes"] = ["Ligne de service client, hors bilan matière." if scope == "pf" else "Production et expéditions du PFI ; hors bilan des intrants."]
            for bucket in row.get("yearly", {}).values():
                bucket.update(balance_status="not_applicable", physical_source_available=False, source_notes=row["source_notes"])
            continue
        pair = (row.get("node_id"), row.get("item_id"))
        pair_events = ledger[pair]
        stock = snapshots[pair]
        opening_events = [event for event in pair_events if event.get("event_type") == "opening_stock"]
        initial = sum(number(event.get("qty")) for event in opening_events)
        unknown = sorted({str(event.get("event_type")) for event in pair_events if event.get("event_type") not in known_types})
        expected_unit = str(row.get("unit") or "").upper()
        mismatched_units = sorted({str(event.get("uom")) for event in pair_events if event.get("uom") and str(event["uom"]).upper() != expected_unit})
        available = bool(source_available and pair_events and not unknown and not mismatched_units)
        notes = ["Consommations et réceptions : événements physiques datés du registre des lots ; clôtures : stocks journaliers."]
        if any(event.get("event_type") in availability_types for event in pair_events):
            notes.append("Clôtures physiques hors réservations : stock utilisable + stock détenu indisponible à cette date ; les libérations ne sont pas des réceptions.")
        if unknown:
            notes.append("Types d'événements non rapprochés : " + ", ".join(unknown))
        if mismatched_units:
            notes.append("Unités du registre incompatibles avec la ligne : " + ", ".join(mismatched_units))
        if not source_available or not pair_events:
            notes.append("Registre physique absent pour cette référence ; calcul BOM conservé séparément.")
        row["theoretical_consumed_qty"] = row.get("consumed_qty")
        row["quantity_basis"] = "physical_ledger"
        yearly = row.get("yearly", {})
        for year, bucket in yearly.items():
            first = (int(year) - 1) * 365
            last = min(horizon_days, first + 365) - 1
            bucket["theoretical_consumed_qty"] = bucket.get("consumed_qty")
            period_available = available and last in stock and (first == 0 or first - 1 in stock)
            bucket.update(physical_source_available=period_available, source_notes=notes, balance_tolerance_qty=1e-5)
            if not period_available:
                for field in ("delivered_qty", "consumed_qty", "stock_outflow_qty", "stock_adjustment_qty", "balance_expected_final_qty", "balance_gap_qty"):
                    bucket[field] = None
                bucket["balance_status"] = "unavailable"
                continue
            relevant = [event for event in pair_events if first <= int(number(event.get("day"))) <= last]
            def total(types: set[str]) -> float:
                return sum(number(event.get("qty")) for event in relevant if event.get("event_type") in types)
            bucket.update(
                initial_qty=initial if first == 0 else stock[first - 1],
                final_stock_qty=stock[last], delivered_qty=total(receipt_types),
                consumed_qty=total(consume_types), stock_outflow_qty=total(outflow_types),
                stock_adjustment_qty=total(adjustment_types),
            )
            # lane_ship confirms the departure of a previously reserved lot;
            # it does not remove the same quantity from on-hand a second time.
            expected = bucket["initial_qty"] + bucket["delivered_qty"] + bucket["stock_adjustment_qty"] - bucket["consumed_qty"] - bucket["stock_outflow_qty"]
            gap = expected - bucket["final_stock_qty"]
            bucket.update(balance_expected_final_qty=expected, balance_gap_qty=gap,
                          balance_status="reconciled" if abs(gap) <= 1e-5 else "mismatch")
        complete = bool(yearly) and all(bucket["physical_source_available"] for bucket in yearly.values())
        row.update(physical_source_available=complete, source_notes=notes, balance_tolerance_qty=1e-5 * len(yearly))
        for field in ("delivered_qty", "consumed_qty", "stock_outflow_qty", "stock_adjustment_qty", "balance_gap_qty"):
            row[field] = sum(bucket[field] for bucket in yearly.values()) if complete else None
        if complete:
            row["initial_qty"] = initial
            row["final_stock_qty"] = stock[horizon_days - 1]
            row["balance_expected_final_qty"] = row["final_stock_qty"] + row["balance_gap_qty"]
            row["gap_vs_need_qty"] = row["consumed_qty"] - number(row.get("planned_qty"))
            row["balance_status"] = "reconciled" if all(bucket["balance_status"] == "reconciled" for bucket in yearly.values()) else "mismatch"
            row["diagnostic"] = "Bilan physique rapproché" if row["balance_status"] == "reconciled" else "Écart de bilan physique à vérifier"
        else:
            row.update(balance_status="unavailable", balance_expected_final_qty=None, gap_vs_need_qty=None,
                       diagnostic="Bilan physique non vérifiable avec les sources disponibles")

# Consolidated from shipment_execution: unchanged business definitions.

def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def executed_shipment_day(row: dict, *, arrival: bool = False, horizon_days: int | None = None) -> int | None:
    """Use explicit execution flags when present; bound legacy dates by observation."""
    prefix = "arrival" if arrival else "departure"
    flag = str(row.get(prefix + "_executed", "")).strip().lower()
    if flag and flag not in {"1", "1.0", "true", "yes"}:
        return None
    status = str(row.get("execution_status") or "")
    if status in {"reserved_pending_departure", "planned_pending_departure"}:
        return None
    if arrival and status == "in_transit":
        return None
    day = number(row.get("realized_" + prefix + "_day"))
    if day is None:
        # An explicit execution contract must carry its actual date. Historical
        # exports without that contract use their event date, with horizon checks.
        if flag and "realized_" + prefix + "_day" in row:
            return None
        day = number(row.get("arrival_day" if arrival else "day"))
    if day is None or day < 0:
        return None
    observation = number(row.get("observation_day"))
    if observation is not None and day > observation:
        return None
    if horizon_days is not None and horizon_days > 0 and day >= horizon_days:
        return None
    return int(day)


def observed_transport_lead(row: dict, *, horizon_days: int | None = None) -> float | None:
    receipt = executed_shipment_day(row, arrival=True, horizon_days=horizon_days)
    departure = executed_shipment_day(row, horizon_days=horizon_days)
    if receipt is None or departure is None or receipt < departure:
        return None
    return float(receipt - departure)

# Consolidated from economic_valuation: unchanged business definitions.

def economic_cost_view(summary: dict[str, Any]) -> dict[str, Any]:
    kpis = summary.get("kpis") or {}
    valuation = summary.get("economic_valuation") or {}
    complete = valuation.get("complete") is True and valuation.get("status") == "complete"
    status = "complete" if complete else ("incomplete" if valuation else "unknown")
    def amount(*keys: str) -> float | None:
        for key in keys:
            if kpis.get(key) is not None:
                return float(kpis[key])
        return None
    operating = amount("known_cost_subtotal", "total_cost")
    external = amount("total_external_procurement_cost", "exceptional_supply_cost")
    exposure = amount("known_economic_exposure_subtotal", "total_economic_exposure")
    if exposure is None and operating is not None and external is not None:
        exposure = operating + external
    return {
        "operating_cost": operating, "external_procurement_cost": external,
        "economic_exposure": exposure, "valuation_status": status,
        "valuation_complete": complete, "economic_ranking_eligible": complete,
        "cost_label": "Coût opérationnel simulé" if complete else "Coût partiellement valorisé — sous-total connu",
        "economic_valuation": valuation or {"status": "unknown", "complete": False, "metric_basis": "historical_valuation_unverified"},
        "cost_scope_note": "Opérationnel : possession, production, achats et transport opérationnels. Approvisionnement externe : complément séparé. Exposition économique : somme de ces deux périmètres ; ce sont des coûts du modèle.",
    }
