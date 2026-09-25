"""Trace fields, CSV readers, business classification and vocabulary."""

from __future__ import annotations
import math
import csv
from typing import Any
from pathlib import Path
from .campaigns import PRODUCTION_CAMPAIGN_FIELDS
from .causal_links import (
    LOT_CAUSAL_EVENT_FIELDS,
    LOT_CAUSAL_GENEALOGY_FIELDS,
    PLAN_CAUSAL_FIELDS,
)
from dataclasses import dataclass, field
from etudecas.case_config import is_upstream_internal_site


# Schema

LOT_TRACE_NUMERIC_FIELDS = {
    "qty",
    "qty_after",
    "parent_qty",
    "child_qty",
    "allocation_share",
    "component_allocation_share",
    "desired_qty",
    "planned_qty_after_lot_rule",
    "actual_qty",
    "shortfall_vs_desired_qty",
    "shortfall_vs_lot_plan_qty",
    "planned_qty_before",
    "planned_qty_after",
    "lot_fixed_qty",
    "lot_min_qty",
    "lot_max_qty",
    "lot_multiple_qty",
    "campaign_requested_qty",
    "campaign_started_qty",
    "campaign_remaining_start_qty",
    "campaign_remaining_end_qty",
    "batch_target_qty",
    "batch_executed_start_qty",
    "batch_executed_today_qty",
    "batch_executed_end_qty",
    "process_tau_days",
    "wip_start_qty",
    "wip_end_qty",
    "released_qty",
    "planned_qty",
    "requested_qty",
    "started_qty",
    "actual_qty",
    "completed_lot_qty",
    "blocked_lot_qty",
    "max_daily_shortfall_qty",
    "repeated_daily_shortfall_qty",
    "remaining_qty",
    "wip_qty",
    "replacement_qty",
}


LOT_TRACE_INTEGER_FIELDS = {
    "day",
    "risk_decision_day",
    "departure_day",
    "arrival_day",
    "next_expected_receipt_day",
    "first_event_day",
    "first_delay_day",
    "last_delay_day",
    "completed_day",
    "delay_event_count",
    "delay_day_count",
    "delay_span_days",
    "event_count",
    "max_lots_per_week",
    "started_lots_this_week",
    "requested_lot_starts",
    "actual_lot_starts",
    "campaign_started_day",
    "batch_started_day",
    "is_day_zero_carry_in",
    "last_release_day",
    "first_execution_day",
    "last_execution_day",
    "released_batch_count",
}


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compact_lot_trace_row(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        value = row.get(field, "")
        if value == "":
            out[field] = ""
            continue
        if field in LOT_TRACE_INTEGER_FIELDS:
            numeric = to_float(value)
            out[field] = int(round(numeric)) if numeric is not None and not math.isnan(numeric) else value
        elif field in LOT_TRACE_NUMERIC_FIELDS:
            numeric = to_float(value)
            out[field] = round(numeric, 6) if numeric is not None and not math.isnan(numeric) else value
        else:
            out[field] = value
    return out


# Io

LOT_TRACE_CONTRACT_VERSION = "3.0"


LOT_TRACE_EVENT_FIELDS = [
    "event_id",
    "day",
    "event_type",
    "lot_id",
    "node_id",
    "item_id",
    "qty",
    "qty_after",
    "uom",
    "source_type",
    "source_id",
    "shipment_id",
    "risk_decision_day",
    "risk_event_ids",
    "related_lot_id",
    "production_campaign_id",
    "notes",
    "business_batch_id",
    "stock_lot_id",
    "lot_occurrence_id",
    "provenance_batch_id",
    "departure_day",
    "arrival_day",
    "handling_unit_id",
    "trace_status",
    "trace_reason",
    "lot_trace_contract_version",
    *LOT_CAUSAL_EVENT_FIELDS,
]


LOT_TRACE_GENEALOGY_FIELDS = [
    "day",
    "link_type",
    "parent_lot_id",
    "parent_node_id",
    "parent_item_id",
    "child_lot_id",
    "child_node_id",
    "child_item_id",
    "parent_qty",
    "child_qty",
    "allocation_share",
    "source_id",
    "shipment_id",
    "risk_decision_day",
    "risk_event_ids",
    "production_campaign_id",
    "notes",
    "component_allocation_share",
    "business_batch_id",
    "stock_lot_id",
    "lot_occurrence_id",
    "parent_business_batch_id",
    "parent_stock_lot_id",
    "parent_lot_occurrence_id",
    "child_business_batch_id",
    "child_stock_lot_id",
    "child_lot_occurrence_id",
    "provenance_batch_id",
    "departure_day",
    "arrival_day",
    "handling_unit_id",
    "trace_status",
    "trace_reason",
    "lot_trace_contract_version",
    *LOT_CAUSAL_GENEALOGY_FIELDS,
]


LOT_TRACE_PLAN_EVENT_FIELDS = [
    "day",
    "campaign_id",
    "semantics_version",
    "campaign_started_day",
    "node_id",
    "output_item_id",
    "batch_id",
    "batch_started_day",
    "batch_target_qty",
    "batch_executed_start_qty",
    "batch_executed_today_qty",
    "batch_executed_end_qty",
    "process_tau_days",
    "release_gate_mode",
    "wip_start_qty",
    "wip_end_qty",
    "released_qty",
    "released_lot_id",
    "is_day_zero_carry_in",
    "event_type",
    "reason",
    "desired_qty",
    "planned_qty_after_lot_rule",
    "actual_qty",
    "shortfall_vs_desired_qty",
    "shortfall_vs_lot_plan_qty",
    "binding_input_item_id",
    "planned_qty_before",
    "planned_qty_after",
    "lot_policy_mode",
    "lot_fixed_qty",
    "lot_min_qty",
    "lot_max_qty",
    "lot_multiple_qty",
    "max_lots_per_week",
    "started_lots_this_week",
    "requested_lot_starts",
    "actual_lot_starts",
    "campaign_requested_qty",
    "campaign_started_qty",
    "campaign_remaining_start_qty",
    "campaign_remaining_end_qty",
    "next_expected_receipt_day",
    "notes",
    *PLAN_CAUSAL_FIELDS,
]


LOT_TRACE_CAMPAIGN_FIELDS = PRODUCTION_CAMPAIGN_FIELDS


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def count_csv_rows(csv_path: Path) -> int:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


# Labels

EVENT_TYPE_LABELS = {
    "create": "Création du lot",
    "opening_stock": "Stock initial",
    "opening_production_order": "Ordre de production en cours à J0",
    "opening_production_consume": "Composant déjà engagé avant J0",
    "stock_reconciliation": "Régularisation du stock lotifié",
    "production_output": "Production terminée",
    "production_consume": "Consommation en production",
    "production_consume_reference_transition": "Consommation de l'ancienne référence",
    "lane_ship": "Départ logistique simulé",
    "shipment_reserve": "Reservation logistique avant depart",
    "supplier_backorder_fulfillment": "Mise a disposition amont modelisee",
    "lane_receipt": "Réception logistique simulée",
    "external_procurement_receipt": "Réception chez le fournisseur",
    "estimated_source_receipt": "Réception fournisseur estimée",
    "estimated_capacity_receipt": "Réception amont estimée",
    "demand_service": "Allocation au client (service de la demande)",
    "writeoff": "Mise au rebut",
    "partial_run_input_shortage": "Production partielle faute de composants",
    "delay_input_shortage": "Production reportée faute de composants",
    "partial_run_capacity": "Production partielle faute de capacité",
    "delay_capacity": "Production reportée faute de capacité",
    "delay_weekly_lot_limit": "Production reportée par limite hebdomadaire de lots",
    "delay_lot_campaign_blocked": "Campagne de production bloquée",
    "start_campaign": "Démarrage de la campagne de production",
    "run_campaign_partial": "Campagne de production partielle",
    "run_campaign_complete": "Campagne de production terminée",
    "plan_no_run": "Production planifiée non lancée",
}


SCOPE_LABELS = {
    "finished_product": "Produit fini fabriqué",
    "semi_finished": "Produit semi-fini fabriqué",
    "supplier_material": "Matière première chez le fournisseur",
    "finished_product_receipt": "Produit fini reçu",
    "semi_finished_receipt": "Produit semi-fini reçu",
    "raw_material_receipt": "Matière première reçue",
    "inventory_receipt": "Article reçu en stock",
    "finished_product_opening": "Produit fini en stock initial",
    "semi_finished_opening": "Produit semi-fini en stock initial",
    "raw_material_opening": "Matière première en stock initial",
    "opening_stock": "Article en stock initial",
    "material_consumption": "Composant consommé en production",
    "customer_service": "Produit alloue a la demande client",
    "inventory_lot": "Lot en stock",
}


NODE_LABEL_OVERRIDES = {
    "SDC-1450": "Site PFI interne D1450",
    "DC-1450": "Site PFI interne D1450",
}


def event_type_label(event_type: Any) -> str:
    code = str(event_type or "").strip()
    if not code:
        return "Événement non renseigné"
    if code in EVENT_TYPE_LABELS:
        return EVENT_TYPE_LABELS[code]
    if code.endswith("_reference_transition"):
        base_code = code[: -len("_reference_transition")]
        base_label = EVENT_TYPE_LABELS.get(base_code, "Mouvement de stock")
        return f"{base_label} avec transition de référence"
    return "Événement métier non référencé"


def scope_label(scope: Any, fallback: Any = "") -> str:
    code = str(scope or "").strip()
    return SCOPE_LABELS.get(code) or str(fallback or "").strip() or "Lot métier"


def node_business_label(node_id: Any) -> str:
    code = str(node_id or "").strip()
    if not code:
        return "Site non renseigné"
    return NODE_LABEL_OVERRIDES.get(code, code)


def format_quantity(qty: Any, uom: Any) -> str:
    unit = str(uom or "").strip() or "unité non renseignée"
    try:
        numeric = float(qty)
    except (TypeError, ValueError):
        return f"quantité non renseignée {unit}"
    if math.isnan(numeric):
        return f"quantité non renseignée {unit}"
    if abs(numeric - round(numeric)) < 1e-9:
        quantity = f"{int(round(numeric)):,}".replace(",", " ")
    else:
        quantity = f"{numeric:,.1f}".replace(",", " ").replace(".", ",")
    return f"{quantity} {unit}"


def build_business_lot_label(
    *,
    scope: Any,
    fallback_scope_label: Any,
    lot_id: Any,
    created_day: int,
    event_type: Any,
    node_id: Any,
    item_id: Any,
    qty: Any,
    uom: Any,
    business_identity_label: Any = "",
    stock_occurrence_id: Any = "",
) -> str:
    identity_label = str(business_identity_label or "").strip()
    if not identity_label:
        identity_label = f"Occurrence technique {str(lot_id or '').strip()}"
    occurrence_label = str(stock_occurrence_id or lot_id or "").strip()
    return " | ".join(
        [
            f"[{scope_label(scope, fallback_scope_label)}]",
            identity_label,
            f"Occurrence {occurrence_label}",
            f"{event_type_label(event_type)} J{created_day}",
            node_business_label(node_id),
            str(item_id or "").strip() or "article non renseigné",
            format_quantity(qty, uom),
        ]
    )


# Rules

@dataclass(frozen=True)
class LotTraceItemSets:
    final_good_item_ids: frozenset[str] = field(default_factory=frozenset)
    produced_item_ids: frozenset[str] = field(default_factory=frozenset)
    consumed_item_ids: frozenset[str] = field(default_factory=frozenset)
    semi_finished_item_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_raw(
        cls,
        raw: dict[str, Any] | None,
        node_type_by_id: dict[str, str],
    ) -> "LotTraceItemSets":
        if not raw:
            return cls()

        final_good_item_ids: set[str] = set()
        produced_item_ids: set[str] = set()
        consumed_item_ids: set[str] = set()
        semi_finished_item_ids: set[str] = set()

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
        return cls(
            final_good_item_ids=frozenset(final_good_item_ids),
            produced_item_ids=frozenset(produced_item_ids),
            consumed_item_ids=frozenset(consumed_item_ids),
            semi_finished_item_ids=frozenset(semi_finished_item_ids),
        )


@dataclass(frozen=True)
class LotTraceItemClassifier:
    node_type_by_id: dict[str, str] = field(default_factory=dict)
    item_sets: LotTraceItemSets = field(default_factory=LotTraceItemSets)

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | None) -> "LotTraceItemClassifier":
        if not raw:
            return cls()
        node_type_by_id = {
            str(node.get("id") or ""): str(node.get("type") or "")
            for node in raw.get("nodes", []) or []
        }
        return cls(
            node_type_by_id=node_type_by_id,
            item_sets=LotTraceItemSets.from_raw(raw, node_type_by_id),
        )

    def item_family(self, item_id: Any, node_id: Any = "") -> str:
        item = str(item_id or "")
        node = str(node_id or "")
        node_type = self.node_type_by_id.get(node, "")
        if item in self.item_sets.final_good_item_ids or node_type in {"distribution_center", "customer"}:
            return "finished_product"
        if item in self.item_sets.semi_finished_item_ids or is_upstream_internal_site(node):
            return "semi_finished"
        if item in self.item_sets.consumed_item_ids or node_type == "supplier_dc":
            return "raw_material"
        if item in self.item_sets.produced_item_ids:
            return "produced_item"
        return "inventory_item"

    def scope_for_creation(self, creation: dict[str, Any]) -> tuple[str, str]:
        event_type = str(creation.get("event_type") or "")
        item_family = self.item_family(creation.get("item_id"), creation.get("node_id"))
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
