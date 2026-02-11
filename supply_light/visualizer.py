# supply/visualizer.py
# -*- coding: utf-8 -*-
"""
Visualisation du réseau d'approvisionnement pour un matériau donné.
Exemples CLI :
  - Tracer tout le réseau :
      python visualizer.py --material aluminium --save aluminium.png
  - Tracer avec un chemin mis en valeur :
      python visualizer.py --material foam --highlight node1 node2 node3
"""

import sys
import os

# Ajoute le dossier parent au path d'import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import networkx as nx
import matplotlib.pyplot as plt
from supply.network import SUPPLY_NETWORK

def build_graph(material: str) -> nx.DiGraph:
    G = nx.DiGraph()
    tiers = SUPPLY_NETWORK.get(material, {}).get("tiers", [])
    for node in tiers:
        G.add_node(node["name"], **node)
        for nxt in node.get("next", []):
            G.add_edge(node["name"], nxt)
    return G

def plot_graph(material: str, highlight: list[str] = None, save: str = None):
    G = build_graph(material)
    pos = nx.kamada_kawai_layout(G)

    plt.figure(figsize=(12, 7))
    node_colors = []
    for node in G.nodes():
        t = G.nodes[node].get("type", "other")
        if t == "extraction":
            node_colors.append("sienna")
        elif t == "raffinage":
            node_colors.append("orange")
        elif t == "transformation":
            node_colors.append("skyblue")
        elif t == "fournisseur_global":
            node_colors.append("green")
        elif t == "entrepot_regional":
            node_colors.append("purple")
        elif t == "site_assemblage":
            node_colors.append("gray")
        else:
            node_colors.append("lightgray")

    edge_colors = ["red" if highlight and (u in highlight and v in highlight) else "black" for u, v in G.edges()]

    nx.draw(G, pos, with_labels=True, node_color=node_colors, edge_color=edge_colors,
            node_size=1000, font_size=9, font_weight="bold")

    labels = {n: G.nodes[n].get("location", n) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)

    if save:
        plt.savefig(save, bbox_inches="tight", dpi=150)
        print(f"[OK] Figure enregistrée : {save}")
    else:
        plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualiser le réseau d’approvisionnement d’un matériau")
    parser.add_argument("--material", required=True, help="Nom du matériau (ex: aluminium, foam, fabric, paint)")
    parser.add_argument("--highlight", nargs="*", help="Liste de nœuds à mettre en évidence")
    parser.add_argument("--save", help="Fichier image de sortie")
    args = parser.parse_args()

    plot_graph(material=args.material, highlight=args.highlight, save=args.save)
