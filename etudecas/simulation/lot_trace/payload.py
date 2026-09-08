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
from .causal_links import LOT_CAUSAL_LINK_FIELDS
from .io import (
    LOT_TRACE_CONTRACT_VERSION,
    LOT_TRACE_CAMPAIGN_FIELDS,
    LOT_TRACE_EVENT_FIELDS,
    LOT_TRACE_GENEALOGY_FIELDS,
    LOT_TRACE_PLAN_EVENT_FIELDS,
    count_csv_rows,
    read_csv_rows,
)
from .indexes import (
    build_lot_trace_indexes,
    lot_trace_downstream_stats,
    lot_trace_upstream_roots,
    lot_trace_upstream_stats,
)
from .labels import (
    EVENT_TYPE_LABELS,
    build_business_lot_label,
    event_type_label,
    node_business_label,
    scope_label as business_scope_label,
)
from .procurement import enrich_lot_trace_with_procurement
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
    mrp_orders_csv: Path | None = None,
    lot_causal_links_csv: Path | None = None,
    include_causal_links: bool = True,
) -> dict[str, Any]:
    events_raw = read_csv_rows(lot_events_csv)
    genealogy_raw = read_csv_rows(lot_genealogy_csv)
    plan_events_raw = read_csv_rows(production_plan_events_csv)
    if production_campaigns_csv is None:
        production_campaigns_csv = production_plan_events_csv.parent / "production_campaigns.csv"
    if mrp_orders_csv is None:
        mrp_orders_csv = production_plan_events_csv.parent / "mrp_orders_daily.csv"
    if lot_causal_links_csv is None:
        lot_causal_links_csv = production_plan_events_csv.parent / "lot_causal_links.csv"
    campaign_rows_raw = read_csv_rows(production_campaigns_csv)
    mrp_order_rows_raw = read_csv_rows(mrp_orders_csv)
    causal_link_count = count_csv_rows(lot_causal_links_csv)
    causal_link_rows_raw = (
        read_csv_rows(lot_causal_links_csv) if include_causal_links else []
    )
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
    raw_event_by_id = {
        str(row.get("event_id") or "").strip(): row
        for row in events_raw
        if str(row.get("event_id") or "").strip()
    }
    raw_genealogy_by_child: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in genealogy_raw:
        child_lot_id = str(row.get("child_lot_id") or "").strip()
        if child_lot_id:
            raw_genealogy_by_child[child_lot_id].append(row)
    genealogy = [
        compact_lot_trace_row(row, LOT_TRACE_GENEALOGY_FIELDS)
        for row in genealogy_raw
        if str(row.get("parent_lot_id") or "").strip() or str(row.get("child_lot_id") or "").strip()
    ]
    procurement_trace = enrich_lot_trace_with_procurement(
        events,
        genealogy,
        mrp_order_rows_raw,
        supply_graph=raw,
    )
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
    causal_link_rows = [
        compact_lot_trace_row(row, LOT_CAUSAL_LINK_FIELDS)
        for row in causal_link_rows_raw
        if str(row.get("entity_id") or "").strip()
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
            "procurement_orders": procurement_trace["orders"],
            "procurement_summary": procurement_trace["summary"],
            "stock_context": {},
            "nomenclature": _lot_trace_nomenclature(),
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
            label = "Stock usine initial uniquement"
        elif supplier_roots:
            label = "Fournisseur amont tracé"
        elif unknown_roots:
            label = "Origine amont partiellement tracée"
        else:
            label = "Origine non tracée par lot"
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
        "upstream_supply_origin_label": "Origine non tracée par lot",
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
        upstream_count = int(upstream_stats["upstream_lot_count"])
        downstream_count = int(downstream_stats["downstream_lot_count"])
        traceable = upstream_count > 0 or downstream_count > 0 or len(sorted_rows) > 1
        selectable = traceable and can_be_selected
        creation_event_type = str(creation.get("event_type") or "")
        creation_event_label = event_type_label(creation_event_type)
        translated_scope_label = business_scope_label(scope, scope_label)
        node_id = str(creation.get("node_id") or "")
        uom = str(creation.get("uom") or "")
        lots[lot_id] = {
            "lot_id": lot_id,
            "label": build_business_lot_label(
                scope=scope,
                fallback_scope_label=scope_label,
                lot_id=lot_id,
                created_day=created_day,
                event_type=creation_event_type,
                node_id=node_id,
                item_id=creation.get("item_id"),
                qty=created_qty,
                uom=uom,
            ),
            "trace_scope": scope,
            "trace_scope_label": translated_scope_label,
            "created_day": created_day,
            "created_event_type": creation_event_type,
            "created_event_type_label": creation_event_label,
            "node_id": node_id,
            "node_label": node_business_label(node_id),
            "item_id": str(creation.get("item_id") or ""),
            "qty": round(created_qty, 6) if created_qty is not None and not math.isnan(created_qty) else "",
            "uom": uom,
            "uom_label": uom or "unité non renseignée",
            "source_type": str(creation.get("source_type") or ""),
            "source_id": str(creation.get("source_id") or ""),
            "mrp_order_id": str(creation.get("mrp_order_id") or ""),
            "order_day": creation.get("order_day"),
            "mrp_decision_day": creation.get("mrp_decision_day"),
            "requested_release_day": creation.get("requested_release_day"),
            "planned_release_day": creation.get("planned_release_day"),
            "actual_release_day": creation.get("actual_release_day"),
            "estimated_release_day": creation.get("estimated_release_day"),
            "planned_arrival_day": creation.get("planned_arrival_day"),
            "actual_receipt_day": creation.get("actual_receipt_day"),
            "procurement_lead_days": creation.get("procurement_lead_days"),
            "procurement_lead_basis": str(
                creation.get("procurement_lead_basis") or ""
            ),
            "procurement_status": str(creation.get("procurement_status") or ""),
            "supplier_node_id": str(creation.get("supplier_node_id") or ""),
            "procurement_trace_status": str(
                creation.get("procurement_trace_status") or ""
            ),
            "procurement_trace_reason": str(
                creation.get("procurement_trace_reason") or ""
            ),
            "trace_status": str(creation.get("trace_status") or ""),
            "trace_reason": str(creation.get("trace_reason") or ""),
            "provenance_batch_id": str(creation.get("provenance_batch_id") or ""),
            "lot_trace_contract_version": str(
                creation.get("lot_trace_contract_version") or ""
            ),
            "production_campaign_id": str(creation.get("production_campaign_id") or ""),
            "scenario_id": str(creation.get("scenario_id") or ""),
            "planned_order_id": str(creation.get("planned_order_id") or ""),
            "baseline_reference_id": str(creation.get("baseline_reference_id") or ""),
            "causal_event_ids": str(creation.get("causal_event_ids") or ""),
            "causal_root_ids": str(creation.get("causal_root_ids") or ""),
            "causal_status": str(creation.get("causal_status") or ""),
            "origin_production_order_ids": str(
                creation.get("origin_production_order_ids") or ""
            ),
            "origin_production_contributions_json": str(
                creation.get("origin_production_contributions_json") or ""
            ),
            "origin_allocation_basis": str(
                creation.get("origin_allocation_basis") or ""
            ),
            "first_day": min(days) if days else created_day,
            "last_day": max(days) if days else created_day,
            "event_count": len(sorted_rows),
            "traceable": traceable,
            "selectable": selectable,
            "technical_trace_label": f"amont {upstream_count} / aval {downstream_count}",
            "trace_counts": {
                "upstream_lots": upstream_count,
                "downstream_lots": downstream_count,
            },
            **downstream_stats,
            **upstream_stats,
            **supply_origin,
            **pf_status,
        }

    _enrich_lot_identities(
        lots=lots,
        trace_indexes=trace_indexes,
        raw_event_by_id=raw_event_by_id,
        raw_genealogy_by_child=raw_genealogy_by_child,
    )

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
            "mrp_orders": str(mrp_orders_csv),
            "causal_links": str(lot_causal_links_csv),
        },
        "default_lot": default_lot,
        "config": lot_trace_config,
        "lots": lots,
        "lot_options": lot_options,
        "events": events,
        "genealogy": genealogy,
        "plan_events": plan_events,
        "campaigns": campaign_rows,
        "causal_links": causal_link_rows,
        "deferred_orders": deferred_orders,
        "procurement_orders": procurement_trace["orders"],
        "procurement_summary": procurement_trace["summary"],
        "stock_context": stock_context,
        "nomenclature": _lot_trace_nomenclature(),
        "summary": {
            "lot_count": len(lots),
            "event_count": len(events),
            "genealogy_count": len(genealogy),
            "plan_event_count": len(plan_events),
            "campaign_count": len(campaign_rows),
            "causal_link_count": causal_link_count,
            "causal_link_rows_embedded": len(causal_link_rows),
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
            "untraced_transport_receipt_count": sum(
                1
                for lot in lots.values()
                if str(lot.get("origin_trace_status") or "") == "untraced_transport_origin"
            ),
            "procurement_order_count": len(procurement_trace["orders"]),
            "procurement_matched_lot_event_count": int(
                procurement_trace["summary"].get("matched_lot_event_count") or 0
            ),
            "procurement_unmatched_lane_receipt_count": int(
                procurement_trace["summary"].get("unmatched_lane_receipt_count") or 0
            ),
            "procurement_inferred_aggregate_receipt_count": int(
                procurement_trace["summary"].get(
                    "inferred_aggregate_receipt_count"
                )
                or 0
            ),
        },
    }
    if default_lot:
        from .view_model import build_lot_trace_view_model

        payload["default_view_model"] = build_lot_trace_view_model(payload, default_lot)
        payload["summary"]["default_view_model_lot"] = default_lot
    return payload


def _lot_trace_nomenclature() -> dict[str, Any]:
    return {
        "contract_version": LOT_TRACE_CONTRACT_VERSION,
        "language": "fr",
        "event_type_labels": dict(sorted(EVENT_TYPE_LABELS.items())),
        "identity_model": {
            "business_lot_id": "Identité métier stable du lot entre les mouvements logistiques.",
            "stock_occurrence_id": "Occurrence du lot dans un stock ou sur un site donné.",
            "shipment_id": (
                "Identité d'une expédition simulée regroupée par route et dates ; "
                "ce n'est pas une preuve de camion réel."
            ),
            "mrp_order_id": (
                "Identité de l'ordre d'approvisionnement MRP relié au mouvement : "
                "décision MRP, départ demandé, expédition simulée et réception."
            ),
            "planned_order_id": (
                "Identite stable de l'ordre de production ou d'approvisionnement "
                "utilisee pour comparer nominal et scenario."
            ),
            "origin_production_order_ids": (
                "Ordres de production PF dont les quantites sont encore presentes "
                "dans cette occurrence de stock."
            ),
            "origin_allocation_basis": (
                "Regle d'allocation des contributions d'origine, explicite notamment "
                "lorsqu'un stock melange plusieurs lots."
            ),
            "logistics_lane_id": "Identité de la ligne logistique, distincte d'une expédition physique.",
            "business_identity_origin": (
                "Origine de l'identité métier : simulée, dérivée de la généalogie "
                "ou inconnue."
            ),
        },
        "selection_policy": (
            "Seuls les lots métier MP, PFI et PF sont sélectionnables ; "
            "les réceptions de transport restent contextuelles."
        ),
    }


def _enrich_lot_identities(
    *,
    lots: dict[str, dict[str, Any]],
    trace_indexes: Any,
    raw_event_by_id: dict[str, dict[str, Any]],
    raw_genealogy_by_child: dict[str, list[dict[str, Any]]],
) -> None:
    explicit_business_ids: dict[str, list[str]] = {}
    explicit_provenance_ids: dict[str, list[str]] = {}
    explicit_occurrence_ids: dict[str, str] = {}
    explicit_shipment_ids: dict[str, str] = {}

    for lot_id in lots:
        creation_rows = trace_indexes.events_by_lot.get(lot_id, [])
        creation_event_id = ""
        if creation_rows:
            creation_event_id = str(
                sorted(
                    creation_rows,
                    key=lambda row: (
                        int(to_float(row.get("day")) or 0),
                        str(row.get("event_id") or ""),
                    ),
                )[0].get("event_id")
                or ""
            )
        raw_creation = raw_event_by_id.get(creation_event_id, {})
        explicit_business = _first_value(
            raw_creation,
            ("business_lot_id", "business_batch_id", "batch_id", "source_batch_id"),
        )
        explicit_occurrence = _first_value(
            raw_creation,
            ("stock_occurrence_id", "lot_occurrence_id", "inventory_lot_id"),
        )
        explicit_shipment = _first_value(
            raw_creation,
            ("shipment_id", "consignment_id", "transport_id"),
        )
        explicit_provenance = _first_value(
            raw_creation,
            ("provenance_batch_id", "provenance_business_batch_ids"),
        )
        if not explicit_shipment:
            for raw_link in raw_genealogy_by_child.get(lot_id, []):
                explicit_shipment = _first_value(
                    raw_link,
                    ("shipment_id", "consignment_id", "transport_id"),
                )
                if explicit_shipment:
                    break
        if explicit_business:
            explicit_business_ids[lot_id] = [explicit_business]
        if explicit_provenance:
            explicit_provenance_ids[lot_id] = sorted(
                {
                    value.strip()
                    for value in explicit_provenance.replace(",", "|").split("|")
                    if value.strip()
                }
            )
        explicit_occurrence_ids[lot_id] = explicit_occurrence or lot_id
        if explicit_shipment:
            explicit_shipment_ids[lot_id] = explicit_shipment

    inferred_cache: dict[str, list[str]] = {}

    def business_ids(lot_id: str, visiting: set[str] | None = None) -> list[str]:
        if lot_id in inferred_cache:
            return list(inferred_cache[lot_id])
        if lot_id in explicit_business_ids:
            inferred_cache[lot_id] = explicit_business_ids[lot_id]
            return list(inferred_cache[lot_id])
        if lot_id in explicit_provenance_ids:
            inferred_cache[lot_id] = explicit_provenance_ids[lot_id]
            return list(inferred_cache[lot_id])
        lot = lots.get(lot_id, {})
        trace_status = str(lot.get("trace_status") or "").strip().lower()
        if trace_status.startswith("untraced"):
            inferred_cache[lot_id] = []
            return []
        if str(lot.get("created_event_type") or "") != "lane_receipt":
            inferred_cache[lot_id] = [lot_id]
            return [lot_id]
        visiting = set(visiting or set())
        if lot_id in visiting:
            return []
        visiting.add(lot_id)
        parent_ids: set[str] = set()
        for link in trace_indexes.link_rows_by_child.get(lot_id, []):
            if str(link.get("link_type") or "") != "transport":
                continue
            parent_lot_id = str(link.get("parent_lot_id") or "")
            parent_ids.update(business_ids(parent_lot_id, visiting))
        inferred_cache[lot_id] = sorted(parent_ids)
        return list(inferred_cache[lot_id])

    for lot_id, lot in lots.items():
        identities = business_ids(lot_id)
        trace_status = str(lot.get("trace_status") or "").strip().lower()
        transport_links = [
            row
            for row in trace_indexes.link_rows_by_child.get(lot_id, [])
            if str(row.get("link_type") or "") == "transport"
        ]
        is_transport_receipt = str(lot.get("created_event_type") or "") == "lane_receipt"
        if trace_status == "partially_traced_mixed_occurrence":
            business_lot_id = ""
            business_status = "partially_traced_mixed"
            business_origin = "derived_from_simulation_genealogy"
            business_label = (
                f"Mélange partiellement tracé : {len(identities)} lot(s) identifié(s) "
                "et origine complémentaire inconnue"
            )
        elif len(identities) == 1:
            business_lot_id = identities[0]
            business_status = "identified"
            business_origin = "simulated"
            business_label = f"Lot métier {business_lot_id}"
        elif identities:
            business_lot_id = ""
            business_status = "mixed"
            business_origin = "derived_from_simulation_genealogy"
            business_label = f"Réception issue de {len(identities)} lots métier"
        else:
            business_lot_id = ""
            business_status = "untraced"
            business_origin = "unknown"
            business_label = "Lot métier d'origine non tracé"

        shipment_id = explicit_shipment_ids.get(lot_id, "")
        if shipment_id:
            shipment_status = "identified"
            shipment_label = f"Expédition simulée {shipment_id}"
        elif is_transport_receipt:
            shipment_status = "not_available_legacy"
            shipment_label = "Mouvement logistique sans identifiant d'expédition"
        else:
            shipment_status = "not_applicable"
            shipment_label = "Aucune expédition associée à la création du lot"

        if is_transport_receipt and not transport_links:
            origin_status = "untraced_transport_origin"
            origin_label = "Origine non tracée par lot (réception agrégée ou ancien format)"
        elif is_transport_receipt and str(lot.get("trace_status") or "").startswith(
            "untraced"
        ):
            origin_status = "untraced_transport_origin"
            origin_label = "Mouvement simulé identifié, origine du lot non tracée"
        elif is_transport_receipt:
            origin_status = "traced_transport_origin"
            origin_label = business_label
        elif str(lot.get("trace_status") or "").startswith("untraced"):
            origin_status = str(lot.get("trace_status") or "untraced_origin")
            origin_label = (
                "Origine avant l'horizon non détaillée par lot"
                if origin_status == "untraced_before_horizon"
                else "Origine non tracée par lot"
            )
        else:
            origin_status = "business_lot_origin"
            origin_label = str(lot.get("upstream_supply_origin_label") or business_label)

        stock_occurrence_id = explicit_occurrence_ids.get(lot_id, lot_id)
        logistics_lane_id = str(lot.get("source_id") or "") if is_transport_receipt else ""
        identity = {
            "business_lot_id": business_lot_id,
            "business_lot_ids": identities,
            "business_identity_status": business_status,
            "business_identity_origin": business_origin,
            "business_identity_label": business_label,
            "stock_occurrence_id": stock_occurrence_id,
            "stock_occurrence_label": f"Occurrence stock {stock_occurrence_id}",
            "shipment_id": shipment_id,
            "shipment_identity_status": shipment_status,
            "shipment_identity_origin": "simulated" if shipment_id else "unknown",
            "shipment_identity_label": shipment_label,
            "logistics_lane_id": logistics_lane_id,
        }
        lot.update(identity)
        lot["identity"] = dict(identity)
        lot["origin_trace_status"] = origin_status
        lot["origin_trace_label"] = origin_label
        lot["label"] = build_business_lot_label(
            scope=lot.get("trace_scope"),
            fallback_scope_label=lot.get("trace_scope_label"),
            lot_id=lot_id,
            created_day=int(lot.get("created_day") or 0),
            event_type=lot.get("created_event_type"),
            node_id=lot.get("node_id"),
            item_id=lot.get("item_id"),
            qty=lot.get("qty"),
            uom=lot.get("uom"),
            business_identity_label=business_label,
            stock_occurrence_id=stock_occurrence_id,
        )


def _first_value(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""
