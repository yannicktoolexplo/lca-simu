# supply_dynamic_sim.py
# -*- coding: utf-8 -*-
"""
Moteur SimPy pour simuler dynamiquement un réseau d'approvisionnement.
Basé sur le graph supply_network.py.

Chaque nœud (mine, usine, hub...) devient un processus SimPy avec :
- une production (ou transformation) selon une capacité
- des transferts vers les nœuds suivants via un délai (transport)

Ce moteur est *indépendant* du moteur de production de sièges existant.
"""

import simpy
from typing import Dict, List
from supply_network import SUPPLY_NETWORK


class SupplyNode:
    def __init__(self, env, name: str, node_def: Dict, next_names: List[str], all_nodes: Dict[str, 'SupplyNode']):
        self.env = env
        self.name = name
        self.node_def = node_def
        self.next_names = next_names
        self.all_nodes = all_nodes
        self.output = simpy.Store(env)
        self.stock = 0
        self.capacity = node_def.get("capacity_tonnes_per_day", 0)
        self.period = 1  # jour
        env.process(self.run())

    def run(self):
        while True:
            if self.capacity > 0 and self.next_names:
                produced = self.capacity
                self.stock += produced
                print(f"[{self.env.now}] {self.name} produit {produced} u (stock: {self.stock})")
                for next_name in self.next_names:
                    link = TransportLink(self.env, self, self.all_nodes[next_name])
                    self.env.process(link.transfer(produced / len(self.next_names)))
                    self.stock -= produced / len(self.next_names)
            yield self.env.timeout(self.period)


class TransportLink:
    def __init__(self, env, src: SupplyNode, dst: SupplyNode):
        self.env = env
        self.src = src
        self.dst = dst
        self.delay = dst.node_def.get("lead_time_days", 1)

    def transfer(self, quantity):
        print(f"[{self.env.now}] → Transport de {quantity} u de {self.src.name} vers {self.dst.name} (délai {self.delay}j)")
        yield self.env.timeout(self.delay)
        self.dst.stock += quantity
        print(f"[{self.env.now}] ✓ {quantity} u livrés à {self.dst.name} (stock: {self.dst.stock})")


def build_sim_network(env, material: str) -> Dict[str, SupplyNode]:
    tiers = SUPPLY_NETWORK[material]["tiers"]
    all_nodes = {}
    name_to_next = {n["name"]: n.get("next", []) for n in tiers}
    for node in tiers:
        name = node["name"]
        next_names = name_to_next.get(name, [])
        sn = SupplyNode(env, name, node, next_names, all_nodes)
        all_nodes[name] = sn
    return all_nodes


def run_supply_simulation(material: str, duration_days: int = 30):
    env = simpy.Environment()
    nodes = build_sim_network(env, material)
    env.run(until=duration_days)
    return nodes


if __name__ == "__main__":
    run_supply_simulation("aluminium", duration_days=30)
