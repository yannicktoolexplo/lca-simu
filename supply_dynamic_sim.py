# supply_dynamic_sim.py
# -*- coding: utf-8 -*-
"""
Simulation SimPy d’un flux matière dynamique dans le réseau multi-niveaux.
"""

import simpy
from typing import List, Dict, Optional
from supply_network import SUPPLY_NETWORK, REGION_FOR_SITE, MATERIALS_PER_SEAT

HOURS_PER_DAY = 8

def _find_node(tiers: List[Dict], name: str) -> Optional[Dict]:
    for n in tiers:
        if n.get("name") == name:
            return n
    return None

def _build_path(material: str, site: str) -> List[Dict]:
    tiers = SUPPLY_NETWORK[material]["tiers"]
    hub = REGION_FOR_SITE.get(site, "hub_Europe")
    global_name = f"supplier_global_{material.capitalize()}"
    plant_name = f"plant_{site}"
    names = [global_name, hub, plant_name]
    return [n for n in tiers if n.get("name") in names]

def run_supply_simulation(material: str, site: str, daily_demand: float, duration_days: int):
    env = simpy.Environment()
    path = _build_path(material, site)

    inventory = {node["name"]: 0.0 for node in path}
    logs = {node["name"]: [] for node in path}

    def delivery_process(env, src: Dict, dst: Dict):
        while True:
            yield env.timeout(dst["lead_time_days"] * HOURS_PER_DAY)
            qty = dst.get("capacity_tonnes_per_day", 10.0)
            inventory[dst["name"]] += qty
            logs[dst["name"]].append((env.now / HOURS_PER_DAY, inventory[dst["name"]]))

    def consumption(env):
        plant = path[-1]["name"]
        while True:
            yield env.timeout(HOURS_PER_DAY)
            inventory[plant] -= daily_demand
            if inventory[plant] < 0:
                inventory[plant] = 0
            logs[plant].append((env.now / HOURS_PER_DAY, inventory[plant]))

    for i in range(1, len(path)):
        src = path[i - 1]
        dst = path[i]
        env.process(delivery_process(env, src, dst))

    env.process(consumption(env))
    env.run(until=duration_days * HOURS_PER_DAY)

    return logs
