from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from etudecas.case_config import (
    build_lot_trace_config,
    is_upstream_internal_site,
)
from .campaigns import (
    build_production_campaign_rows,
    deferred_orders_from_campaign_rows,
)
from .io import (
    LOT_TRACE_CAMPAIGN_FIELDS,
    LOT_TRACE_EVENT_FIELDS,
    LOT_TRACE_GENEALOGY_FIELDS,
    LOT_TRACE_PLAN_EVENT_FIELDS,
    read_csv_rows,
)
from .schema import (
    compact_lot_trace_row,
    to_float,
)


def build_lot_trace_payload(
    lot_events_csv: Path,
    lot_genealogy_csv: Path,
    production_plan_events_csv: Path,
    raw: dict[str, Any] | None = None,
    input_stocks_csv: Path | None = None,
    output_products_csv: Path | None = None,
    dc_stocks_csv: Path | None = None,
    demand_service_csv: Path | None = None,
    supplier_stocks_csv: Path | None = None,
    visible_finished_product_items: Iterable[str] | None = None,
    production_campaigns_csv: Path | None = None,
) -> dict[str, Any]:
    events_raw = read_csv_rows(lot_events_csv)
    genealogy_raw = read_csv_rows(lot_genealogy_csv)
    plan_events_raw = read_csv_rows(production_plan_events_csv)
    if production_campaigns_csv is None:
        production_campaigns_csv = production_plan_events_csv.parent / "production_campaigns.csv"
    campaign_rows_raw = read_csv_rows(production_campaigns_csv)
    lot_trace_config = build_lot_trace_config(raw)
    visible_finished_product_items_set = {
        str(item_id)
        for item_id in (visible_finished_product_items or [])
        if str(item_id)
    }
    events = [
        compact_lot_trace_row(row, LOT_TRACE_EVENT_FIELDS)
        for row in events_raw
        if str(row.get("lot_id") or "").strip()
    ]
    genealogy = [
        compact_lot_trace_row(row, LOT_TRACE_GENEALOGY_FIELDS)
        for row in genealogy_raw
        if str(row.get("parent_lot_id") or "").strip() or str(row.get("child_lot_id") or "").strip()
    ]
    plan_events = [
        compact_lot_trace_row(row, LOT_TRACE_PLAN_EVENT_FIELDS)
        for row in plan_events_raw
        if str(row.get("campaign_id") or "").strip()
    ]
    plan_events_for_campaign_build = [
        compact_lot_trace_row(row, LOT_TRACE_PLAN_EVENT_FIELDS)
        for row in plan_events_raw
        if str(row.get("campaign_id") or "").strip()
        or str(row.get("event_type") or "").strip()
        or str(row.get("reason") or "").strip()
    ]
    campaign_rows = [
        compact_lot_trace_row(row, LOT_TRACE_CAMPAIGN_FIELDS)
        for row in campaign_rows_raw
        if str(row.get("campaign_id") or "").strip()
    ]
    if not campaign_rows and plan_events_for_campaign_build:
        campaign_rows = build_production_campaign_rows(plan_events_for_campaign_build, events)
    campaign_deferred_orders = deferred_orders_from_campaign_rows(
        campaign_rows,
        visible_finished_product_items=visible_finished_product_items_set,
    )
    if not events_raw and not genealogy_raw:
        return {
            "available": False,
            "reason": "production_lot_events.csv and production_lot_genealogy.csv not found or empty",
            "config": lot_trace_config,
            "lots": {},
            "lot_options": [],
            "events": [],
            "genealogy": [],
            "plan_events": plan_events,
            "campaigns": campaign_rows,
            "deferred_orders": campaign_deferred_orders,
            "stock_context": {},
            "summary": {
                "lot_count": 0,
                "event_count": 0,
                "genealogy_count": 0,
                "plan_event_count": len(plan_events),
                "campaign_count": len(campaign_rows),
                "deferred_order_count": len(campaign_deferred_orders),
                "deferred_order_delay_event_count": sum(
                    int(row.get("delay_event_count") or 0) for row in campaign_deferred_orders
                ),
            },
        }
    plan_events_by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plan_events:
        plan_events_by_campaign[str(row.get("campaign_id") or "")].append(row)

    events_by_lot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_counts: dict[str, int] = defaultdict(int)
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        events_by_lot[lot_id].append(row)
        event_counts[str(row.get("event_type") or "")] += 1

    children_by_parent: dict[str, list[str]] = defaultdict(list)
    parents_by_child: dict[str, list[str]] = defaultdict(list)
    link_rows_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    link_rows_by_child: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in genealogy:
        parent_lot = str(row.get("parent_lot_id") or "")
        child_lot = str(row.get("child_lot_id") or "")
        if parent_lot and child_lot:
            children_by_parent[parent_lot].append(child_lot)
            parents_by_child[child_lot].append(parent_lot)
            link_rows_by_parent[parent_lot].append(row)
            link_rows_by_child[child_lot].append(row)

    link_counts: dict[str, int] = defaultdict(int)
    for row in genealogy:
        link_counts[str(row.get("link_type") or "")] += 1

    node_type_by_id: dict[str, str] = {}
    final_good_item_ids: set[str] = set()
    produced_item_ids: set[str] = set()
    consumed_item_ids: set[str] = set()
    semi_finished_item_ids: set[str] = set()
    if raw:
        node_type_by_id = {str(node.get("id") or ""): str(node.get("type") or "") for node in raw.get("nodes", []) or []}
        for edge in raw.get("edges", []) or []:
            src = str(edge.get("from") or "")
            dst = str(edge.get("to") or "")
            dst_type = node_type_by_id.get(dst, "")
            src_type = node_type_by_id.get(src, "")
            edge_items = {str(item_id) for item_id in (edge.get("items") or []) if str(item_id)}
            if dst_type == "customer":
                final_good_item_ids.update(edge_items)
            if src_type == "factory" and dst_type == "factory":
                semi_finished_item_ids.update(edge_items)
            if is_upstream_internal_site(src) or is_upstream_internal_site(dst):
                semi_finished_item_ids.update(edge_items)
        for node in raw.get("nodes", []) or []:
            node_id = str(node.get("id") or "")
            for proc in node.get("processes") or []:
                for output in proc.get("outputs") or []:
                    item_id = str(output.get("item_id") or "")
                    if not item_id:
                        continue
                    produced_item_ids.add(item_id)
                    if is_upstream_internal_site(node_id):
                        semi_finished_item_ids.add(item_id)
                for input_row in proc.get("inputs") or []:
                    item_id = str(input_row.get("item_id") or "")
                    if item_id:
                        consumed_item_ids.add(item_id)
        semi_finished_item_ids.update(produced_item_ids & consumed_item_ids)
        semi_finished_item_ids.difference_update(final_good_item_ids)

    def lot_trace_item_family(item_id: Any, node_id: Any = "") -> str:
        item = str(item_id or "")
        node = str(node_id or "")
        node_type = node_type_by_id.get(node, "")
        if item in final_good_item_ids or node_type in {"distribution_center", "customer"}:
            return "finished_product"
        if item in semi_finished_item_ids or is_upstream_internal_site(node):
            return "semi_finished"
        if item in consumed_item_ids or node_type == "supplier_dc":
            return "raw_material"
        if item in produced_item_ids:
            return "produced_item"
        return "inventory_item"

    creation_priority = {
        "production_output": 0,
        "lane_receipt": 1,
        "external_procurement_receipt": 2,
        "estimated_source_receipt": 3,
        "estimated_capacity_receipt": 4,
        "opening_stock": 5,
    }

    def lot_trace_scope(creation: dict[str, Any]) -> tuple[str, str]:
        event_type = str(creation.get("event_type") or "")
        item_family = lot_trace_item_family(creation.get("item_id"), creation.get("node_id"))
        if event_type == "production_output":
            if item_family == "semi_finished":
                return "semi_finished", "Semi-fini produit"
            return "finished_product", "PF produit"
        if event_type in {"external_procurement_receipt", "estimated_source_receipt", "estimated_capacity_receipt"}:
            return "supplier_material", "MP fournisseur"
        if event_type == "lane_receipt":
            if item_family == "finished_product":
                return "finished_product_receipt", "PF recu"
            if item_family == "semi_finished":
                return "semi_finished_receipt", "Semi-fini recu"
            if item_family == "raw_material":
                return "raw_material_receipt", "MP recue"
            return "inventory_receipt", "Lot recu"
        if event_type == "opening_stock":
            if item_family == "finished_product":
                return "finished_product_opening", "PF stock initial"
            if item_family == "semi_finished":
                return "semi_finished_opening", "Semi-fini stock initial"
            if item_family == "raw_material":
                return "raw_material_opening", "MP stock initial"
            return "opening_stock", "Stock initial"
        if event_type == "production_consume":
            return "material_consumption", "MP consommee"
        if event_type == "demand_service":
            return "customer_service", "Service client"
        return "inventory_lot", "Lot stock"

    def row_day(row: dict[str, Any]) -> int:
        numeric = to_float(row.get("day"))
        return int(round(numeric)) if numeric is not None and not math.isnan(numeric) else 0

    def build_lot_trace_stock_context() -> dict[str, dict[str, Any]]:
        relevant_keys: set[tuple[str, str, int]] = set()
        for row in events:
            node_id = str(row.get("node_id") or "")
            item_id = str(row.get("item_id") or "")
            if node_id and item_id:
                relevant_keys.add((node_id, item_id, row_day(row)))
        for row in genealogy:
            day = row_day(row)
            parent_node = str(row.get("parent_node_id") or "")
            parent_item = str(row.get("parent_item_id") or "")
            child_node = str(row.get("child_node_id") or "")
            child_item = str(row.get("child_item_id") or "")
            if parent_node and parent_item:
                relevant_keys.add((parent_node, parent_item, day))
            if child_node and child_item:
                relevant_keys.add((child_node, child_item, day))
        if not relevant_keys:
            return {}

        relevant_by_pair: dict[tuple[str, str], set[int]] = defaultdict(set)
        for node_id, item_id, day in relevant_keys:
            relevant_by_pair[(node_id, item_id)].add(day)

        out: dict[str, dict[str, Any]] = {}

        def key(node_id: str, item_id: str, day: int) -> str:
            return f"{node_id}|{item_id}|{day}"

        def set_context(
            *,
            node_id: str,
            item_id: str,
            day: int,
            label: str,
            before: float | None = None,
            after: float | None = None,
            delta: float | None = None,
            extra: dict[str, Any] | None = None,
            overwrite: bool = False,
        ) -> None:
            if not node_id or not item_id:
                return
            if (node_id, item_id, day) not in relevant_keys:
                return
            ctx_key = key(node_id, item_id, day)
            if ctx_key in out and not overwrite:
                return
            payload: dict[str, Any] = {
                "node_id": node_id,
                "item_id": item_id,
                "day": day,
                "label": label,
            }
            if before is not None and not math.isnan(before):
                payload["before_qty"] = round(before, 6)
            if after is not None and not math.isnan(after):
                payload["after_qty"] = round(after, 6)
            if delta is not None and not math.isnan(delta):
                payload["delta_qty"] = round(delta, 6)
            elif before is not None and after is not None and not math.isnan(before) and not math.isnan(after):
                payload["delta_qty"] = round(after - before, 6)
            if extra:
                payload.update(extra)
            out[ctx_key] = payload

        def add_end_of_day_context(csv_path: Path | None, *, stock_field: str, label: str) -> None:
            if csv_path is None or not csv_path.exists():
                return
            rows = read_csv_rows(csv_path)
            by_pair: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
            for row in rows:
                node_id = str(row.get("node_id") or "")
                item_id = str(row.get("item_id") or "")
                if (node_id, item_id) not in relevant_by_pair:
                    continue
                day = int(to_float(row.get("day")) or 0)
                value = to_float(row.get(stock_field))
                if value is None or math.isnan(value):
                    continue
                by_pair[(node_id, item_id)][day] = value
            for (node_id, item_id), wanted_days in relevant_by_pair.items():
                series = by_pair.get((node_id, item_id), {})
                if not series:
                    continue
                for day in wanted_days:
                    if day not in series:
                        continue
                    before = series.get(day - 1)
                    if before is None and day == 0:
                        before = 0.0
                    after = series.get(day)
                    set_context(
                        node_id=node_id,
                        item_id=item_id,
                        day=day,
                        label=label,
                        before=before,
                        after=after,
                    )

        if input_stocks_csv is not None and input_stocks_csv.exists():
            for row in read_csv_rows(input_stocks_csv):
                node_id = str(row.get("node_id") or "")
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                if (node_id, item_id, day) not in relevant_keys:
                    continue
                before = to_float(row.get("stock_before_production"))
                after = to_float(row.get("stock_end_of_day"))
                set_context(
                    node_id=node_id,
                    item_id=item_id,
                    day=day,
                    label="stock intrant usine",
                    before=before,
                    after=after,
                    overwrite=True,
                )

        add_end_of_day_context(output_products_csv, stock_field="stock_end_of_day", label="stock produit usine fin de jour")
        add_end_of_day_context(dc_stocks_csv, stock_field="stock_end_of_day", label="stock DC fin de jour")
        add_end_of_day_context(supplier_stocks_csv, stock_field="stock_end_of_day", label="stock fournisseur fin de jour")

        if demand_service_csv is not None and demand_service_csv.exists():
            for row in read_csv_rows(demand_service_csv):
                node_id = str(row.get("node_id") or "")
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                if (node_id, item_id, day) not in relevant_keys:
                    continue
                available = to_float(row.get("available_before_service_qty"))
                served = to_float(row.get("served_qty")) or 0.0
                backlog = to_float(row.get("backlog_end_qty"))
                after = (available - served) if available is not None and not math.isnan(available) else None
                set_context(
                    node_id=node_id,
                    item_id=item_id,
                    day=day,
                    label="stock client avant/apres service",
                    before=available,
                    after=after,
                    extra={"served_qty": round(served, 6), "backlog_end_qty": round(backlog or 0.0, 6)},
                    overwrite=True,
                )

        return out

    stock_context = build_lot_trace_stock_context()

    def lot_trace_downstream_stats(lot_id: str) -> dict[str, Any]:
        visited: set[str] = set()
        queue = list(children_by_parent.get(lot_id, []))
        link_types: set[str] = set()
        nodes: set[str] = set()
        finished_product_lots = 0
        while queue and len(visited) < 5000:
            child = queue.pop(0)
            if child in visited:
                continue
            visited.add(child)
            for row in events_by_lot.get(child, []):
                node_id = str(row.get("node_id") or "")
                if node_id:
                    nodes.add(node_id)
                if str(row.get("event_type") or "") == "production_output":
                    finished_product_lots += 1
            for row in link_rows_by_parent.get(child, []):
                link_type = str(row.get("link_type") or "")
                if link_type:
                    link_types.add(link_type)
            queue.extend(children_by_parent.get(child, []))
        for row in link_rows_by_parent.get(lot_id, []):
            link_type = str(row.get("link_type") or "")
            if link_type:
                link_types.add(link_type)
        return {
            "downstream_lot_count": len(visited),
            "downstream_node_count": len(nodes),
            "downstream_finished_product_lot_count": finished_product_lots,
            "downstream_link_types": sorted(link_types),
        }

    def lot_trace_upstream_stats(lot_id: str) -> dict[str, Any]:
        visited: set[str] = set()
        queue = list(parents_by_child.get(lot_id, []))
        link_types: set[str] = set()
        nodes: set[str] = set()
        supplier_material_lots = 0
        while queue and len(visited) < 5000:
            parent = queue.pop(0)
            if parent in visited:
                continue
            visited.add(parent)
            for row in events_by_lot.get(parent, []):
                node_id = str(row.get("node_id") or "")
                if node_id:
                    nodes.add(node_id)
                if str(row.get("event_type") or "") in {
                    "external_procurement_receipt",
                    "estimated_source_receipt",
                    "estimated_capacity_receipt",
                    "opening_stock",
                }:
                    supplier_material_lots += 1
            for row in link_rows_by_child.get(parent, []):
                link_type = str(row.get("link_type") or "")
                if link_type:
                    link_types.add(link_type)
            queue.extend(parents_by_child.get(parent, []))
        for row in link_rows_by_child.get(lot_id, []):
            link_type = str(row.get("link_type") or "")
            if link_type:
                link_types.add(link_type)
        return {
            "upstream_lot_count": len(visited),
            "upstream_node_count": len(nodes),
            "upstream_material_lot_count": supplier_material_lots,
            "upstream_link_types": sorted(link_types),
        }

    def upstream_root_lots(lot_id: str) -> set[str]:
        roots: set[str] = set()
        visited: set[str] = set()
        queue = list(parents_by_child.get(lot_id, []))
        while queue and len(visited) < 5000:
            parent = queue.pop(0)
            if parent in visited:
                continue
            visited.add(parent)
            grandparents = parents_by_child.get(parent, [])
            if grandparents:
                queue.extend(grandparents)
            else:
                roots.add(parent)
        return roots

    def lot_creation_row(lot_id: str) -> dict[str, Any]:
        rows = events_by_lot.get(lot_id, [])
        if not rows:
            return {}
        return sorted(
            rows,
            key=lambda row: (
                row_day(row),
                creation_priority.get(str(row.get("event_type") or ""), 9),
                str(row.get("event_id") or ""),
            ),
        )[0]

    def is_factory_opening_stock_root(lot_id: str) -> bool:
        creation = lot_creation_row(lot_id)
        if str(creation.get("event_type") or "") != "opening_stock":
            return False
        node_id = str(creation.get("node_id") or "")
        return node_type_by_id.get(node_id, "") == "factory" or node_id.startswith("M-") or is_upstream_internal_site(node_id)

    def upstream_supply_origin(lot_id: str) -> dict[str, Any]:
        roots = upstream_root_lots(lot_id)
        factory_stock_roots = {root for root in roots if is_factory_opening_stock_root(root)}
        supplier_roots: set[str] = set()
        unknown_roots: set[str] = set()
        for root in roots:
            creation = lot_creation_row(root)
            event_type = str(creation.get("event_type") or "")
            node_id = str(creation.get("node_id") or "")
            node_type = node_type_by_id.get(node_id, "")
            if event_type in {"external_procurement_receipt", "estimated_source_receipt", "estimated_capacity_receipt"}:
                supplier_roots.add(root)
            elif node_type == "supplier_dc" or node_id.startswith("SDC-VD"):
                supplier_roots.add(root)
            elif root not in factory_stock_roots:
                unknown_roots.add(root)
        factory_stock_only = bool(roots) and len(factory_stock_roots) == len(roots)
        if factory_stock_only:
            label = "Stock usine J0 uniquement"
        elif supplier_roots:
            label = "Fournisseur amont present"
        elif unknown_roots:
            label = "Origine amont mixte/incomplete"
        else:
            label = "Sans ascendance tracee"
        return {
            "upstream_root_lot_count": len(roots),
            "upstream_factory_stock_root_count": len(factory_stock_roots),
            "upstream_supplier_root_count": len(supplier_roots),
            "upstream_unknown_root_count": len(unknown_roots),
            "produced_from_factory_stock_only": factory_stock_only,
            "upstream_supply_origin_label": label,
        }

    def lot_remaining_in_finished_stock(lot_id: str, creation: dict[str, Any]) -> float:
        creation_node = str(creation.get("node_id") or "")
        rows = [
            row
            for row in events_by_lot.get(lot_id, [])
            if str(row.get("node_id") or "") == creation_node
        ]
        if not rows:
            return 0.0
        latest = sorted(
            rows,
            key=lambda row: (
                row_day(row),
                creation_priority.get(str(row.get("event_type") or ""), 9),
                str(row.get("event_id") or ""),
            ),
        )[-1]
        return max(0.0, to_float(latest.get("qty_after")) or 0.0)

    def production_input_availability_status(creation: dict[str, Any]) -> dict[str, Any]:
        campaign_id = str(creation.get("production_campaign_id") or "")
        created_day = row_day(creation)
        rows = plan_events_by_campaign.get(campaign_id, []) if campaign_id else []
        same_day_rows = [row for row in rows if row_day(row) == created_day]
        evaluation_rows = same_day_rows or rows
        input_shortage_rows = [
            row
            for row in evaluation_rows
            if str(row.get("reason") or "") == "input_shortage"
            or str(row.get("event_type") or "") == "partial_run_input_shortage"
            or bool(str(row.get("binding_input_item_id") or ""))
        ]
        if input_shortage_rows:
            blocking_items = sorted(
                {
                    str(row.get("binding_input_item_id") or "")
                    for row in input_shortage_rows
                    if str(row.get("binding_input_item_id") or "")
                }
            )
            shortfall_qty = sum(max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0) for row in input_shortage_rows)
            return {
                "pf_input_status": "input_shortage",
                "pf_input_status_label": "MP/PFI insuffisante en stock entree usine",
                "pf_blocking_input_item_ids": blocking_items,
                "pf_input_shortfall_qty": round(shortfall_qty, 6),
            }
        return {
            "pf_input_status": "inputs_available",
            "pf_input_status_label": "MP/PFI disponibles pour produire",
            "pf_blocking_input_item_ids": [],
            "pf_input_shortfall_qty": 0.0,
        }

    def finished_product_availability_status(lot_id: str, creation: dict[str, Any], scope: str) -> dict[str, Any]:
        if scope != "finished_product":
            return {
                "pf_availability_status": "",
                "pf_availability_status_label": "",
                "pf_remaining_stock_qty": 0.0,
                "pf_input_status": "",
                "pf_input_status_label": "",
                "pf_blocking_input_item_ids": [],
                "pf_input_shortfall_qty": 0.0,
            }
        remaining_qty = lot_remaining_in_finished_stock(lot_id, creation)
        input_status = production_input_availability_status(creation)
        if remaining_qty > 1e-9:
            return {
                **input_status,
                "pf_availability_status": "in_finished_stock",
                "pf_availability_status_label": "En stock produit fini",
                "pf_remaining_stock_qty": round(remaining_qty, 6),
            }
        if input_status["pf_input_status"] == "input_shortage":
            return {
                **input_status,
                "pf_availability_status": "input_shortage",
                "pf_availability_status_label": input_status["pf_input_status_label"],
                "pf_remaining_stock_qty": 0.0,
            }
        return {
            **input_status,
            "pf_availability_status": "inputs_available",
            "pf_availability_status_label": input_status["pf_input_status_label"],
            "pf_remaining_stock_qty": 0.0,
        }

    def build_deferred_production_orders() -> list[dict[str, Any]]:
        output_lot_by_campaign: dict[str, dict[str, Any]] = {}
        for lot_id, rows in events_by_lot.items():
            for row in rows:
                if str(row.get("event_type") or "") != "production_output":
                    continue
                campaign_id = str(row.get("production_campaign_id") or "")
                if not campaign_id:
                    continue
                output_lot_by_campaign[campaign_id] = {
                    "lot_id": lot_id,
                    "day": row_day(row),
                    "qty": to_float(row.get("qty")) or 0.0,
                }

        delay_event_types = {
            "delay_input_shortage",
            "delay_capacity",
            "delay_weekly_lot_limit",
            "delay_lot_campaign_blocked",
        }
        completion_event_types = {
            "start_campaign",
            "run_campaign_complete",
        }
        out: list[dict[str, Any]] = []
        for campaign_id, rows in plan_events_by_campaign.items():
            ordered_rows = sorted(rows, key=lambda row: row_day(row))
            if not ordered_rows:
                continue
            output_item = str(ordered_rows[0].get("output_item_id") or "")
            if visible_finished_product_items_set and output_item not in visible_finished_product_items_set:
                continue
            delay_rows = [
                row
                for row in ordered_rows
                if str(row.get("event_type") or "") in delay_event_types
                or (
                    str(row.get("reason") or "") == "input_shortage"
                    and max(0.0, to_float(row.get("actual_qty")) or 0.0) <= 1e-9
                )
            ]
            if not delay_rows:
                continue
            first_delay_day = min(row_day(row) for row in delay_rows)
            last_delay_day = max(row_day(row) for row in delay_rows)
            completion_rows = [
                row
                for row in ordered_rows
                if str(row.get("event_type") or "") in completion_event_types
                and row_day(row) >= first_delay_day
                and max(0.0, to_float(row.get("actual_qty")) or 0.0) > 1e-9
            ]
            completion_row = sorted(completion_rows, key=lambda row: row_day(row))[0] if completion_rows else {}
            output_lot = output_lot_by_campaign.get(campaign_id, {})
            planned_qty = max(max(0.0, to_float(row.get("planned_qty_after_lot_rule")) or 0.0) for row in ordered_rows)
            actual_completion_qty = max(0.0, to_float(completion_row.get("actual_qty")) or 0.0) if completion_row else 0.0
            blocking_inputs = sorted(
                {
                    str(row.get("binding_input_item_id") or "")
                    for row in delay_rows
                    if str(row.get("binding_input_item_id") or "")
                }
            )
            next_receipts = sorted(
                {
                    int(to_float(row.get("next_expected_receipt_day")) or 0)
                    for row in delay_rows
                    if str(row.get("next_expected_receipt_day") or "").strip()
                }
            )
            status = "completed_after_delay" if completion_row else "still_blocked"
            status_label = "Produit apres report" if completion_row else "Toujours bloque"
            label = (
                f"[ORDRE REPORTE] {campaign_id} | J{first_delay_day}->{row_day(completion_row) if completion_row else last_delay_day} "
                f"| {ordered_rows[0].get('node_id') or ''} {output_item} | {planned_qty:.1f}"
            )
            out.append(
                {
                    "campaign_id": campaign_id,
                    "label": label,
                    "status": status,
                    "status_label": status_label,
                    "node_id": str(ordered_rows[0].get("node_id") or ""),
                    "output_item_id": output_item,
                    "first_delay_day": first_delay_day,
                    "last_delay_day": last_delay_day,
                    "delay_days": len(delay_rows),
                    "planned_qty": round(planned_qty, 6),
                    "actual_completion_qty": round(actual_completion_qty, 6),
                    "blocking_input_item_ids": blocking_inputs,
                    "next_expected_receipt_days": next_receipts,
                    "completed_day": row_day(completion_row) if completion_row else "",
                    "completed_lot_id": str(output_lot.get("lot_id") or ""),
                    "completed_lot_qty": round(to_float(output_lot.get("qty")) or 0.0, 6) if output_lot else 0.0,
                    "event_count": len(ordered_rows),
                    "delay_event_count": len(delay_rows),
                }
            )
        return sorted(
            out,
            key=lambda row: (
                int(row.get("first_delay_day") or 0),
                str(row.get("campaign_id") or ""),
            ),
        )

    lots: dict[str, dict[str, Any]] = {}
    for lot_id, rows in events_by_lot.items():
        sorted_rows = sorted(
            rows,
            key=lambda row: (
                row_day(row),
                creation_priority.get(str(row.get("event_type") or ""), 9),
                str(row.get("event_id") or ""),
            ),
        )
        creation = sorted_rows[0]
        scope, scope_label = lot_trace_scope(creation)
        downstream_stats = lot_trace_downstream_stats(lot_id)
        upstream_stats = lot_trace_upstream_stats(lot_id)
        supply_origin = upstream_supply_origin(lot_id)
        pf_status = finished_product_availability_status(lot_id, creation, scope)
        days = [row_day(row) for row in sorted_rows]
        created_day = row_day(creation)
        created_qty = to_float(creation.get("qty"))
        qty_text = f"{created_qty:.1f}" if created_qty is not None and not math.isnan(created_qty) else ""
        upstream_count = int(upstream_stats["upstream_lot_count"])
        downstream_count = int(downstream_stats["downstream_lot_count"])
        traceable = upstream_count > 0 or downstream_count > 0 or len(sorted_rows) > 1
        selectable = traceable and str(creation.get("event_type") or "") in {
            "production_output",
            "external_procurement_receipt",
            "estimated_source_receipt",
            "estimated_capacity_receipt",
            "opening_stock",
        }
        trace_label = f"amont {upstream_count} / aval {downstream_count}"
        label_parts = [
            f"[{scope_label} - {trace_label}]",
            lot_id,
            f"J{created_day}",
            str(creation.get("event_type") or "creation"),
            str(creation.get("node_id") or ""),
            str(creation.get("item_id") or ""),
        ]
        if qty_text:
            label_parts.append(qty_text)
        lots[lot_id] = {
            "lot_id": lot_id,
            "label": " | ".join(part for part in label_parts if part),
            "trace_scope": scope,
            "trace_scope_label": scope_label,
            "created_day": created_day,
            "created_event_type": str(creation.get("event_type") or ""),
            "node_id": str(creation.get("node_id") or ""),
            "item_id": str(creation.get("item_id") or ""),
            "qty": round(created_qty, 6) if created_qty is not None and not math.isnan(created_qty) else "",
            "uom": str(creation.get("uom") or ""),
            "source_type": str(creation.get("source_type") or ""),
            "source_id": str(creation.get("source_id") or ""),
            "production_campaign_id": str(creation.get("production_campaign_id") or ""),
            "first_day": min(days) if days else created_day,
            "last_day": max(days) if days else created_day,
            "event_count": len(sorted_rows),
            "traceable": traceable,
            "selectable": selectable,
            **downstream_stats,
            **upstream_stats,
            **supply_origin,
            **pf_status,
        }

    default_lot = ""
    finished_product_root_scopes = {"finished_product"}
    business_selectable_scopes = {
        "finished_product",
        "semi_finished",
        "supplier_material",
        "finished_product_opening",
        "semi_finished_opening",
        "raw_material_opening",
    }

    def is_business_selectable_lot(lot: dict[str, Any]) -> bool:
        if not lot.get("traceable") or not lot.get("selectable"):
            return False
        scope = str(lot.get("trace_scope") or "")
        if scope in finished_product_root_scopes:
            if visible_finished_product_items_set and str(lot.get("item_id") or "") not in visible_finished_product_items_set:
                return False
            return int(lot.get("upstream_material_lot_count") or 0) > 0
        if scope not in business_selectable_scopes:
            return False
        return int(lot.get("upstream_lot_count") or 0) > 0 or int(lot.get("downstream_lot_count") or 0) > 0

    lot_options = [
        lot for lot in lots.values()
        if is_business_selectable_lot(lot)
    ]
    supplier_material_candidates = [
        lot for lot in lot_options
        if lot.get("trace_scope") == "supplier_material"
    ]
    finished_product_candidates = [
        lot for lot in lot_options
        if lot.get("trace_scope") in finished_product_root_scopes
    ]
    default_candidates = finished_product_candidates or supplier_material_candidates
    if default_candidates:
        default_lot = str(
            sorted(default_candidates, key=lambda lot: (lot["created_day"], lot["lot_id"]))[0].get("lot_id") or ""
        )
    if not default_lot and lot_options:
        default_lot = sorted(lot_options, key=lambda lot: (lot["created_day"], lot["lot_id"]))[0]["lot_id"]

    lot_options = sorted(
        lot_options,
        key=lambda lot: (
            {
                "finished_product": 0,
                "semi_finished": 1,
                "supplier_material": 2,
                "finished_product_opening": 3,
                "semi_finished_opening": 4,
                "raw_material_opening": 5,
            }.get(str(lot.get("trace_scope") or ""), 9),
            int(lot.get("created_day") or 0),
            str(lot.get("lot_id") or ""),
        ),
    )
    deferred_orders = campaign_deferred_orders or build_deferred_production_orders()
    payload = {
        "available": bool(lot_options),
        "files": {
            "events": str(lot_events_csv),
            "genealogy": str(lot_genealogy_csv),
            "plan_events": str(production_plan_events_csv),
            "campaigns": str(production_campaigns_csv),
        },
        "default_lot": default_lot,
        "config": lot_trace_config,
        "lots": lots,
        "lot_options": lot_options,
        "events": events,
        "genealogy": genealogy,
        "plan_events": plan_events,
        "campaigns": campaign_rows,
        "deferred_orders": deferred_orders,
        "stock_context": stock_context,
        "summary": {
            "lot_count": len(lots),
            "event_count": len(events),
            "genealogy_count": len(genealogy),
            "plan_event_count": len(plan_events),
            "campaign_count": len(campaign_rows),
            "deferred_order_count": len(deferred_orders),
            "deferred_order_delay_event_count": sum(int(row.get("delay_event_count") or 0) for row in deferred_orders),
            "traceable_lot_count": len(lot_options),
            "internal_traceable_lot_count": sum(1 for lot in lots.values() if lot.get("traceable")),
            "stock_context_count": len(stock_context),
            "selectable_filter": "business_lots_pf_pfi_mp_no_transport_receipts",
            "selectable_finished_product_items": sorted(visible_finished_product_items_set),
            "factory_stock_only_finished_product_count": sum(
                1 for lot in lot_options if lot.get("produced_from_factory_stock_only")
            ),
            "finished_product_availability_counts": {
                status: sum(1 for lot in lot_options if str(lot.get("pf_availability_status") or "") == status)
                for status in ["in_finished_stock", "inputs_available", "input_shortage"]
            },
            "event_counts": dict(sorted(event_counts.items())),
            "link_counts": dict(sorted(link_counts.items())),
        },
    }
    if default_lot:
        from .view_model import build_lot_trace_view_model

        payload["default_view_model"] = build_lot_trace_view_model(payload, default_lot)
        payload["summary"]["default_view_model_lot"] = default_lot
    return payload
