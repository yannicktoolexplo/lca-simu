from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etudecas.case_config import is_upstream_internal_site


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
