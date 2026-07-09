from __future__ import annotations

import math
from collections import Counter, defaultdict
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
from .indexes import (
    build_lot_trace_indexes,
    lot_trace_downstream_stats,
    lot_trace_upstream_roots,
    lot_trace_upstream_stats,
)
from .rules import LotTraceItemClassifier
from .schema import (
    compact_lot_trace_row,
    to_float,
)
from .stock_context import LotTraceStockContextSources, build_lot_trace_stock_context


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
                "deferred_order_completed_count": sum(
                    1 for row in campaign_deferred_orders if str(row.get("status") or "") == "completed_after_delay"
                ),
                "deferred_order_blocked_count": sum(
                    1 for row in campaign_deferred_orders if str(row.get("status") or "") != "completed_after_delay"
                ),
                "deferred_order_delay_event_count": sum(
                    int(row.get("delay_event_count") or 0) for row in campaign_deferred_orders
                ),
                "selectable_filter": "business_lots_pf_pfi_mp_no_transport_receipts",
                "physical_lot_policy": "select_business_lots_contextual_transport_receipts",
            },
        }
    plan_events_by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plan_events:
        plan_events_by_campaign[str(row.get("campaign_id") or "")].append(row)

    event_counts: dict[str, int] = defaultdict(int)
    for row in events:
        event_counts[str(row.get("event_type") or "")] += 1

    link_counts: dict[str, int] = defaultdict(int)
    for row in genealogy:
        link_counts[str(row.get("link_type") or "")] += 1

    trace_indexes = build_lot_trace_indexes({"events": events, "genealogy": genealogy})
    events_by_lot = trace_indexes.events_by_lot
    item_classifier = LotTraceItemClassifier.from_raw(raw)
    node_type_by_id = item_classifier.node_type_by_id

    creation_priority = {
        "production_output": 0,
        "lane_receipt": 1,
        "external_procurement_receipt": 2,
        "estimated_source_receipt": 3,
        "estimated_capacity_receipt": 4,
        "opening_stock": 5,
    }

    def row_day(row: dict[str, Any]) -> int:
        numeric = to_float(row.get("day"))
        return int(round(numeric)) if numeric is not None and not math.isnan(numeric) else 0

    stock_context = build_lot_trace_stock_context(
        events,
        genealogy,
        LotTraceStockContextSources(
            input_stocks_csv=input_stocks_csv,
            output_products_csv=output_products_csv,
            dc_stocks_csv=dc_stocks_csv,
            demand_service_csv=demand_service_csv,
            supplier_stocks_csv=supplier_stocks_csv,
        ),
    )

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
        roots = lot_trace_upstream_roots(trace_indexes, lot_id)
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
    selectable_creation_types = {
        "production_output",
        "external_procurement_receipt",
        "estimated_source_receipt",
        "estimated_capacity_receipt",
        "opening_stock",
    }
    empty_downstream_stats = {
        "downstream_lot_count": 0,
        "downstream_node_count": 0,
        "downstream_finished_product_lot_count": 0,
        "downstream_link_types": [],
    }
    empty_upstream_stats = {
        "upstream_lot_count": 0,
        "upstream_node_count": 0,
        "upstream_material_lot_count": 0,
        "upstream_link_types": [],
    }
    empty_supply_origin = {
        "upstream_root_lot_count": 0,
        "upstream_factory_stock_root_count": 0,
        "upstream_supplier_root_count": 0,
        "upstream_unknown_root_count": 0,
        "produced_from_factory_stock_only": False,
        "upstream_supply_origin_label": "Sans ascendance tracee",
    }
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
        scope, scope_label = item_classifier.scope_for_creation(creation)
        creation_type = str(creation.get("event_type") or "")
        can_be_selected = creation_type in selectable_creation_types
        if can_be_selected:
            downstream_stats = lot_trace_downstream_stats(trace_indexes, lot_id)
            upstream_stats = lot_trace_upstream_stats(trace_indexes, lot_id)
            supply_origin = upstream_supply_origin(lot_id)
        else:
            downstream_stats = dict(empty_downstream_stats)
            upstream_stats = dict(empty_upstream_stats)
            supply_origin = dict(empty_supply_origin)
        pf_status = finished_product_availability_status(lot_id, creation, scope)
        days = [row_day(row) for row in sorted_rows]
        created_day = row_day(creation)
        created_qty = to_float(creation.get("qty"))
        qty_text = f"{created_qty:.1f}" if created_qty is not None and not math.isnan(created_qty) else ""
        upstream_count = int(upstream_stats["upstream_lot_count"])
        downstream_count = int(downstream_stats["downstream_lot_count"])
        traceable = upstream_count > 0 or downstream_count > 0 or len(sorted_rows) > 1
        selectable = traceable and can_be_selected
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
            "deferred_order_completed_count": sum(
                1 for row in deferred_orders if str(row.get("status") or "") == "completed_after_delay"
            ),
            "deferred_order_blocked_count": sum(
                1 for row in deferred_orders if str(row.get("status") or "") != "completed_after_delay"
            ),
            "deferred_order_delay_event_count": sum(int(row.get("delay_event_count") or 0) for row in deferred_orders),
            "traceable_lot_count": len(lot_options),
            "internal_traceable_lot_count": sum(1 for lot in lots.values() if lot.get("traceable")),
            "stock_context_count": len(stock_context),
            "selectable_filter": "business_lots_pf_pfi_mp_no_transport_receipts",
            "physical_lot_policy": "select_business_lots_contextual_transport_receipts",
            "selectable_scope_counts": dict(
                sorted(Counter(str(lot.get("trace_scope") or "unknown") for lot in lot_options).items())
            ),
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
