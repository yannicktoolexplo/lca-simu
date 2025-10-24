# supply_chain_sim.py
# -*- coding: utf-8 -*-
"""
Simulation dynamique des fournisseurs/logistique avec SimPy.
Chaque nœud produit, stocke et expédie vers les suivants.
"""

import simpy
from typing import Dict, List, Optional

# === Paramètres généraux ===
HOURS_PER_DAY = 8  # 1 jour = 8h dans le moteur principal

# === Classe SupplyNode ===
class SupplyNode:
    def __init__(self, env: simpy.Environment, name: str, capacity: float, next_nodes: List[str], lead_time_days: int):
        self.env = env
        self.name = name
        self.capacity = capacity  # capacité de prod ou d'envoi (par jour)
        self.next_nodes = next_nodes  # noms des noeuds suivants
        self.lead_time = lead_time_days * HOURS_PER_DAY
        self.stock = 0.0
        self.outgoing: List[TransportLink] = []
        self.process = env.process(self.run())

    def attach_link(self, link):
        self.outgoing.append(link)

    def run(self):
        while True:
            # production continue
            self.stock += self.capacity / HOURS_PER_DAY  # production par heure
            yield self.env.timeout(1)
            # tentative d'expédition
            for link in self.outgoing:
                if self.stock >= link.batch_size:
                    self.stock -= link.batch_size
                    link.send(batch=link.batch_size)


# === Classe TransportLink ===
class TransportLink:
    def __init__(self, env: simpy.Environment, source: SupplyNode, dest: SupplyNode, delay: int, batch_size: float):
        self.env = env
        self.source = source
        self.dest = dest
        self.delay = delay
        self.batch_size = batch_size

    def send(self, batch: float):
        def _delivery():
            yield self.env.timeout(self.delay)
            self.dest.stock += batch
        self.env.process(_delivery())


# === Construction du graphe pour un matériau (ex: aluminium) ===
def setup_supply_chain(env: simpy.Environment, material_network: List[Dict]) -> Dict[str, SupplyNode]:
    nodes = {}
    # Création des noeuds
    for node in material_network:
        name = node["name"]
        cap = node.get("capacity_tonnes_per_day") or node.get("capacity_seats_per_day") or 20
        nexts = node.get("next", [])
        lead = node.get("lead_time_days", 1)
        nodes[name] = SupplyNode(env, name, cap, nexts, lead)

    # Connexion des noeuds
    for node in material_network:
        src = nodes[node["name"]]
        for nxt_name in node.get("next", []):
            if nxt_name in nodes:
                link = TransportLink(env, src, nodes[nxt_name], delay=nodes[nxt_name].lead_time, batch_size=10.0)
                src.attach_link(link)

    return nodes
