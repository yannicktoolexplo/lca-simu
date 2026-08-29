from __future__ import annotations

import math
from typing import Any


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
