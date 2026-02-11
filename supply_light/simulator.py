# supply/simulator.py
# -*- coding: utf-8 -*-
"""
Simulation dynamique de flux logistiques sur le réseau d'approvisionnement.
Entrée : matrice du réseau, site final, demande journalière, durée.
Sortie : état de chaque noeud au fil du temps.
"""

from __future__ import annotations
import simpy
from typing import Dict, List, Any
from .network import SUPPLY_NETWORK, trace_path, route_time_days, MATERIALS_PER_SEAT, HOURS_PER_DAY


def run_supply_simulation(
    material: str,
    site: str,
    daily_demand: float,
    duration_days: int,
) -> Dict[str, Any]:
    """
    Simule la demande quotidienne depuis un site sur le réseau d'approvisionnement.
    Retourne une structure contenant les livraisons prévues et l'état du stock par noeud.
    """
    if material not in SUPPLY_NETWORK:
        raise ValueError(f"Matériau inconnu : {material}")

    path = trace_path(material, site)
    tiers = SUPPLY_NETWORK[material]["tiers"]
    nodes = {n["name"]: n for n in tiers}

    env = simpy.Environment()
    state = {
        name: {
            "stock": 0.0,
            "outgoing": []  # liste des livraisons planifiées
        }
        for name in path
    }

    # --- Processus de livraison entre les noeuds ---
    def transporter(src: str, dst: str, delay: int):
        while True:
            if state[src]["stock"] >= daily_demand:
                yield env.timeout(delay * HOURS_PER_DAY)
                state[src]["stock"] -= daily_demand
                state[dst]["stock"] += daily_demand
                state[src]["outgoing"].append({"to": dst, "day": int(env.now / HOURS_PER_DAY)})
            yield env.timeout(1)  # réessaye chaque heure

    # --- Génère les stocks initiaux en amont ---
    for i in range(len(path) - 1):
        src, dst = path[i], path[i+1]
        lead_time = nodes[src].get("lead_time_days", 1)
        env.process(transporter(src, dst, lead_time))

    # --- Ajoute une production infinie au premier noeud ---
    def producer():
        while True:
            state[path[0]]["stock"] += 2 * daily_demand  # marge de sécurité
            yield env.timeout(HOURS_PER_DAY)

    env.process(producer())

    # --- Consommation finale au site ---
    def consumer():
        while True:
            if state[path[-1]]["stock"] >= daily_demand:
                state[path[-1]]["stock"] -= daily_demand
            yield env.timeout(HOURS_PER_DAY)

    env.process(consumer())
    env.run(until=duration_days * HOURS_PER_DAY)

    return {
        "path": path,
        "state": state,
        "duration_days": duration_days,
        "daily_demand": daily_demand,
    }
