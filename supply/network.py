# supply/network.py
# -*- coding: utf-8 -*-
"""
Contient la définition du réseau d'approvisionnement multi-niveaux.
"""
from typing import Dict, List, Optional

HOURS_PER_DAY = 8

SUPPLY_NETWORK: Dict[str, Dict[str, List[Dict]]] = {
    "aluminium": {
        "tiers": [
            {"name": "mine", "type": "extraction", "location": "Australia", "lead_time_days": 10, "next": ["refinery"]},
            {"name": "refinery", "type": "raffinage", "location": "China", "lead_time_days": 6, "next": ["rolling"]},
            {"name": "rolling", "type": "transformation", "location": "France", "lead_time_days": 4, "next": ["global_supplier"]},
            {"name": "global_supplier", "type": "fournisseur_global", "location": "Germany", "lead_time_days": 3, "next": ["hub"]},
            {"name": "hub", "type": "entrepot_regional", "location": "Toulouse", "lead_time_days": 2, "next": ["plant"]},
            {"name": "plant", "type": "site_assemblage", "location": "France", "lead_time_days": 1}
        ]
    }
}

REGION_FOR_SITE = {"France": "hub"}

MATERIALS_PER_SEAT = {"aluminium": 1.0}

def get_supply_path(material: str) -> List[Dict]:
    return SUPPLY_NETWORK[material]["tiers"]

def get_supply_plan(site: str, material: str) -> Dict[str, float]:
    tiers = get_supply_path(material)
    route = [t for t in tiers if t["type"] in ("fournisseur_global", "entrepot_regional", "site_assemblage")]
    total_days = sum(t["lead_time_days"] for t in route)
    return {"quantity": 24.0, "delivery_time": total_days * HOURS_PER_DAY}  # en heures

def trace_path(material: str) -> List[str]:
    return [t["name"] for t in SUPPLY_NETWORK[material]["tiers"]]

def get_node(material: str, name: str) -> Optional[Dict]:
    return next((n for n in SUPPLY_NETWORK[material]["tiers"] if n["name"] == name), None)

def get_all_sites(material: str) -> List[str]:
    return [n["location"] for n in SUPPLY_NETWORK[material]["tiers"] if n["type"] == "site_assemblage"]
