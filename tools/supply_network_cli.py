# supply_network_cli.py
# -*- coding: utf-8 -*-
"""
Interface CLI pour visualiser le réseau d'approvisionnement.

Exemples :
  - Tracer tout le réseau d’un matériau :
    python supply_network_cli.py --material aluminium --plot-all --save aluminium_network.png

  - Tracer uniquement le chemin jusqu’à un site :
    python supply_network_cli.py --material foam --site France --save foam_to_france.png
"""

import argparse
import networkx as nx
import matplotlib.pyplot as plt
from resilience.supply_network import SUPPLY_NETWORK, trace_path, _find_node

def build_full_graph(material: str) -> nx.DiGraph:
    G = nx.DiGraph()
    tiers = SUPPLY_NETWORK.get(material, {}).get("tiers", [])
    for node in tiers:
        G.add_node(node["name"], **node)
        for nxt in node.get("next", []):
            G.add_edge(node["name"], nxt)
    return G

def plot_graph(G: nx.DiGraph, path: list[str] = None, save: str = None):
    # Utilise shell_layout par type de nœud pour meilleure lisibilité
    try:
        pos = nx.shell_layout(G)
    except:
        pos = nx.spring_layout(G, seed=42)

    plt.figure(figsize=(14, 8))
    
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

    edge_colors = ["red" if path and (u, v) in zip(path, path[1:]) else "black" for u, v in G.edges()]

    nx.draw(
        G, pos,
        with_labels=False,
        node_size=1600,
        node_color=node_colors,
        edge_color=edge_colors,
        font_size=9,
        font_weight="bold",
        arrows=True
    )
    
    # Ajoute les noms dans des boîtes en dessous
    for node, (x, y) in pos.items():
        plt.text(x, y + 0.08, node, ha='center', fontsize=9, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", alpha=0.7))

    if save:
        plt.savefig(save, bbox_inches="tight", dpi=150)
        print(f"[OK] Figure enregistrée : {save}")
    else:
        plt.show()

def main():
    parser = argparse.ArgumentParser(description="Visualiser le réseau d’approvisionnement d’un matériau")
    parser.add_argument("--material", required=True, help="Nom du matériau (aluminium, foam, fabric, paint)")
    parser.add_argument("--site", help="Nom du site final (France, UK, Texas, California)")
    parser.add_argument("--plot-all", action="store_true", help="Tracer tout le réseau du matériau")
    parser.add_argument("--save", help="Fichier image de sortie")
    args = parser.parse_args()

    material = args.material.lower()
    if material not in SUPPLY_NETWORK:
        raise ValueError(f"Matériau inconnu : {material}")

    G = build_full_graph(material)

    if args.plot_all:
        plot_graph(G, save=args.save)
    elif args.site:
        try:
            p = trace_path(material, args.site)
            print(" > Chemin :", " -> ".join(p))
            plot_graph(G, path=p, save=args.save)
        except Exception as e:
            print(f"[ERREUR] Impossible de tracer le chemin : {e}")
    else:
        print("[INFO] Précisez --plot-all ou --site SITE_NAME")


if __name__ == "__main__":
    main()
