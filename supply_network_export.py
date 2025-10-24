# supply_network_export.py
# -*- coding: utf-8 -*-
"""
Construit un dictionnaire SUPPLY_NETWORK compatible avec SimPy à partir de
la structure de graphe définie dans supply_network_model.
"""

from supply_network_model import supply_graph


def export_supply_network():
    SUPPLY_NETWORK = {}

    for material in supply_graph.materials():
        tiers = []
        for node in supply_graph.nodes_for_material(material):
            # Construction du nœud
            nd = {
                "name": node.name,
                "type": node.node_type,
                "location": node.location,
                "lead_time_days": node.lead_time_days,
            }
            if node.capacity_tonnes_per_day:
                nd["capacity_tonnes_per_day"] = node.capacity_tonnes_per_day
            if node.capacity_seats_per_day:
                nd["capacity_seats_per_day"] = node.capacity_seats_per_day

            # Nœuds cibles aval
            nd["next"] = [n.name for n in node.next_nodes]
            tiers.append(nd)

        SUPPLY_NETWORK[material] = {"tiers": tiers}

    return SUPPLY_NETWORK


# Pour test manuel
if __name__ == "__main__":
    import json
    sn = export_supply_network()
    print(json.dumps(sn, indent=2, ensure_ascii=False))
