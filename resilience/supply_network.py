# supply_network.py
# -*- coding: utf-8 -*-
"""
Réseau d'appro multi-niveaux :
⛰ Extraction -> ⚙ Raffinage/Transformation -> 🚛 Fournisseur global -> 🚚 Hub régional -> 🏭 Site

Ce module expose une API compatible avec line_production :
- get_supply_plan(site_name: str, seat_weight: float) -> dict
  (mêmes clés que ton manage_fixed_supply historique : aluminium, polymers (foam), fabric, paint)
- helpers pour introspection : trace_path(material, site), route_time_days(material, site)
"""

from __future__ import annotations
from typing import Dict, List, Optional

# === Paramètres généraux ===
HOURS_PER_DAY = 8  # ton modèle utilise env.now/8 -> 1 "jour" = 8h

# --- Réseau multi-niveaux par matière -----------------------------------------
# NB: "next" liste les nœuds aval accessibles depuis le nœud courant.
SUPPLY_NETWORK: Dict[str, Dict[str, List[Dict]]] = {
    "aluminium": {
        "tiers": [
            {"name": "bauxite_mine_Australia", "type": "extraction",     "location": "Western Australia", "lead_time_days": 20, "capacity_tonnes_per_day": 500, "next": ["refinery_China"]},
            {"name": "refinery_China",         "type": "raffinage",      "location": "Guangxi (CN)",      "lead_time_days": 10, "capacity_tonnes_per_day": 450, "next": ["rolling_France", "rolling_USA"]},
            {"name": "rolling_France",         "type": "transformation", "location": "Dunkerque (FR)",    "lead_time_days": 5,  "capacity_tonnes_per_day": 400, "next": ["supplier_global_Alu"]},
            {"name": "rolling_USA",            "type": "transformation", "location": "Alabama (US)",       "lead_time_days": 6,  "capacity_tonnes_per_day": 350, "next": ["supplier_global_Alu"]},
            {"name": "supplier_global_Alu",    "type": "fournisseur_global","location": "Hamburg (DE)",   "lead_time_days": 3,  "capacity_tonnes_per_day": 700, "next": ["hub_Europe", "hub_America"]},
            {"name": "hub_Europe",             "type": "entrepot_regional","location": "Toulouse (FR)",    "lead_time_days": 2,  "capacity_tonnes_per_day": 350, "next": ["plant_France", "plant_UK"]},
            {"name": "hub_America",            "type": "entrepot_regional","location": "Dallas (US)",      "lead_time_days": 2,  "capacity_tonnes_per_day": 350, "next": ["plant_Texas", "plant_California"]},
            {"name": "plant_France",           "type": "site_assemblage", "location": "France",            "lead_time_days": 1,  "capacity_seats_per_day": 20},
            {"name": "plant_UK",               "type": "site_assemblage", "location": "UK",                "lead_time_days": 1,  "capacity_seats_per_day": 15},
            {"name": "plant_Texas",            "type": "site_assemblage", "location": "Texas",             "lead_time_days": 1,  "capacity_seats_per_day": 18},
            {"name": "plant_California",       "type": "site_assemblage", "location": "California",        "lead_time_days": 1,  "capacity_seats_per_day": 12},
        ]
    },
    "foam": {
        "tiers": [
            {"name": "chemical_feedstock",      "type": "extraction",      "location": "Saudi Arabia", "lead_time_days": 15, "next": ["polyurethane_plant_EU"]},
            {"name": "polyurethane_plant_EU",   "type": "transformation",  "location": "Cologne (DE)", "lead_time_days": 7,  "next": ["supplier_global_Foam"]},
            {"name": "supplier_global_Foam",    "type": "fournisseur_global","location": "Lyon (FR)",  "lead_time_days": 3,  "next": ["hub_Europe", "hub_America"]},
            {"name": "hub_Europe",              "type": "entrepot_regional","location": "Toulouse (FR)","lead_time_days": 2,  "next": ["plant_France", "plant_UK"]},
            {"name": "hub_America",             "type": "entrepot_regional","location": "Dallas (US)",  "lead_time_days": 2,  "next": ["plant_Texas", "plant_California"]},
            {"name": "plant_France",            "type": "site_assemblage", "location": "France",       "lead_time_days": 1},
            {"name": "plant_UK",                "type": "site_assemblage", "location": "UK",           "lead_time_days": 1},
            {"name": "plant_Texas",             "type": "site_assemblage", "location": "Texas",        "lead_time_days": 1},
            {"name": "plant_California",        "type": "site_assemblage", "location": "California",   "lead_time_days": 1},
        ]
    },
    "fabric": {
        "tiers": [
            {"name": "cotton_farm_India",       "type": "extraction",      "location": "Gujarat (IN)", "lead_time_days": 25, "next": ["weaving_Poland"]},
            {"name": "weaving_Poland",          "type": "transformation",  "location": "Łódź (PL)",    "lead_time_days": 8,  "next": ["supplier_global_Fabric"]},
            {"name": "supplier_global_Fabric",  "type": "fournisseur_global","location": "Toulouse (FR)","lead_time_days": 3, "next": ["hub_Europe", "hub_America"]},
            {"name": "hub_Europe",              "type": "entrepot_regional","location": "Toulouse (FR)","lead_time_days": 2, "next": ["plant_France", "plant_UK"]},
            {"name": "hub_America",             "type": "entrepot_regional","location": "Dallas (US)",  "lead_time_days": 2, "next": ["plant_Texas", "plant_California"]},
            {"name": "plant_France",            "type": "site_assemblage", "location": "France",       "lead_time_days": 1},
            {"name": "plant_UK",                "type": "site_assemblage", "location": "UK",           "lead_time_days": 1},
            {"name": "plant_Texas",             "type": "site_assemblage", "location": "Texas",        "lead_time_days": 1},
            {"name": "plant_California",        "type": "site_assemblage", "location": "California",   "lead_time_days": 1},
        ]
    },
    "paint": {
        "tiers": [
            {"name": "chemical_plant_Netherlands","type": "transformation","location": "Rotterdam (NL)","lead_time_days": 5, "next": ["supplier_global_Paint"]},
            {"name": "supplier_global_Paint",     "type": "fournisseur_global","location": "Hamburg (DE)","lead_time_days": 2, "next": ["hub_Europe", "hub_America"]},
            {"name": "hub_Europe",                "type": "entrepot_regional","location": "Toulouse (FR)","lead_time_days": 2, "next": ["plant_France", "plant_UK"]},
            {"name": "hub_America",               "type": "entrepot_regional","location": "Dallas (US)",  "lead_time_days": 2, "next": ["plant_Texas", "plant_California"]},
            {"name": "plant_France",              "type": "site_assemblage", "location": "France",        "lead_time_days": 1},
            {"name": "plant_UK",                  "type": "site_assemblage", "location": "UK",            "lead_time_days": 1},
            {"name": "plant_Texas",               "type": "site_assemblage", "location": "Texas",         "lead_time_days": 1},
            {"name": "plant_California",          "type": "site_assemblage", "location": "California",    "lead_time_days": 1},
        ]
    },
}

# --- Mapping région -> sites (pour choisir le hub) -----------------------------
REGION_FOR_SITE = {
    "France": "hub_Europe",
    "UK": "hub_Europe",
    "Texas": "hub_America",
    "California": "hub_America",
}

# --- Besoins matière (unités "container" par siège) ---------------------------
# NB: ton moteur consomme 1 alu + 1 foam + 1 fabric + 1 paint pour un frame maker,
# et des fractions pour armrest. On reste simple (1u/siège) pour calibrer les livraisons.
MATERIALS_PER_SEAT = {
    "aluminium": 1.0,
    "foam": 1.0,
    "fabric": 1.0,
    "paint": 1.0,
}

# --- État global pour activer/désactiver un fournisseur -----------------------
GLOBAL_STATE = {
    "aluminium": {"enabled": True},
    "foam":      {"enabled": True},
    "fabric":    {"enabled": True},
    "paint":     {"enabled": True},
}

def set_global_enabled(material: str, enabled: bool):
    if material in GLOBAL_STATE:
        GLOBAL_STATE[material]["enabled"] = bool(enabled)

# --- Helpers de cheminement ----------------------------------------------------
def _find_node(tiers: List[Dict], name: str) -> Optional[Dict]:
    for n in tiers:
        if n.get("name") == name:
            return n
    return None

def _route_from_global_to_site(material: str, site_name: str) -> List[Dict]:
    tiers = SUPPLY_NETWORK[material]["tiers"]
    # Choisir le hub selon la région du site
    hub = REGION_FOR_SITE.get(site_name)
    if hub is None:
        # fallback: Europe
        hub = "hub_Europe"
    path_names = ["supplier_global_" + {"aluminium":"Alu","foam":"Foam","fabric":"Fabric","paint":"Paint"}[material], hub, f"plant_{site_name}"]
    path = []
    for nm in path_names:
        node = _find_node(tiers, nm)
        if node:
            path.append(node)
    return path

def route_time_days(material: str, site_name: str) -> int:
    """Somme des lead times du fournisseur global -> hub -> site (en jours)."""
    path = _route_from_global_to_site(material, site_name)
    return sum(int(n.get("lead_time_days", 0)) for n in path)

def trace_path(material: str, site_name: str) -> List[str]:
    return [n["name"] for n in _route_from_global_to_site(material, site_name)]

# --- API principale : plan d'appro compatible line_production ------------------
def get_supply_plan(site_name: str, seat_weight: float) -> Dict[str, Dict[str, float]]:
    """
    Renvoie un dict au format de ton manage_fixed_supply historique :
    {
      'aluminium': {'quantity': Q, 'delivery_time': T_hours},
      'polymers' : {'quantity': Q, 'delivery_time': T_hours},  # foam
      'fabric'   : {'quantity': Q, 'delivery_time': T_hours},
      'paint'    : {'quantity': Q, 'delivery_time': T_hours},
    }
    """
    # Quantité par livraison : on vise ~2 jours de prod moyenne par arrivée (simple, empirique)
    # Si un site produit ~12 sièges/jour, Q ~ 24 unités par livraison.
    # Comme on ne lis pas la vraie capacité ici, on prend une valeur par défaut raisonnable.
    Q_DEFAULT = 24.0

    def _entry(material: str):
        days = route_time_days(material, site_name)
        hours = max(1, int(days * HOURS_PER_DAY))  # délai logistique total -> heures SimPy
        return {"quantity": Q_DEFAULT, "delivery_time": hours}

    plan = {
        "aluminium": _entry("aluminium"),
        "polymers":  _entry("foam"),     # NOTE: clé 'polymers' attendue par ton _stock_control pour la foam
        "fabric":    _entry("fabric"),
        "paint":     _entry("paint"),
    }
    return plan
