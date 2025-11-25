from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Node:
    name: str
    node_type: str  # 'extraction', 'transfo', 'hub', 'assembly'
    material: Optional[str] = None  # ex: 'aluminium'
    component: Optional[str] = None  # ex: 'frame'
    country: Optional[str] = None
    co2_impact: float = 0.0
    lead_time_days: int = 0
    capacity_per_day: Optional[int] = None
    criticality: int = 1  # 1 = faible, 5 = critique
    downstream: List[str] = field(default_factory=list)  # list of node names


class SupplyNetwork:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}

    def add_node(self, node: Node):
        self.nodes[node.name] = node

    def link(self, from_node: str, to_node: str):
        if from_node in self.nodes:
            self.nodes[from_node].downstream.append(to_node)

    def get_path(self, material: str) -> List[str]:
        """
        Renvoie le chemin complet (supply chain) pour un matériau donné.
        """
        path = []
        for node in self.nodes.values():
            if node.material == material:
                path.append(node.name)
                path.extend(self._trace_downstream(node.name))
                break
        return path

    def _trace_downstream(self, node_name: str, visited=None) -> List[str]:
        if visited is None:
            visited = set()
        visited.add(node_name)
        result = []
        node = self.nodes.get(node_name)
        if node:
            for child in node.downstream:
                if child not in visited:
                    result.append(child)
                    result.extend(self._trace_downstream(child, visited))
        return result


# Exemple d'initialisation réseau pour l'aluminium et l'électronique
if __name__ == "__main__":
    net = SupplyNetwork()

    net.add_node(Node("Bauxite_Guinea", "extraction", material="aluminium", country="Guinée", co2_impact=10.0))
    net.add_node(Node("Refining_China", "transfo", material="aluminium", country="Chine", co2_impact=25.0, lead_time_days=5))
    net.add_node(Node("FrameForge_Thailand", "transfo", component="frame", material="aluminium", country="Thaïlande", co2_impact=50.0, lead_time_days=10))
    net.add_node(Node("AluHub_FR", "hub", material="aluminium", country="France", lead_time_days=3))
    net.add_node(Node("Assembly_FR", "assembly", component="seat", country="France"))

    net.link("Bauxite_Guinea", "Refining_China")
    net.link("Refining_China", "FrameForge_Thailand")
    net.link("FrameForge_Thailand", "AluHub_FR")
    net.link("AluHub_FR", "Assembly_FR")

    # Exemple électronique
    net.add_node(Node("RareEarth_China", "extraction", material="electronic", country="Chine", co2_impact=15))
    net.add_node(Node("PCB_Malaysia", "transfo", component="electronics", country="Malaisie", lead_time_days=8))
    net.link("RareEarth_China", "PCB_Malaysia")
    net.link("PCB_Malaysia", "Assembly_FR")

    # Affichage chemin complet pour l'aluminium
    print("Chemin aluminium:", " -> ".join(net.get_path("aluminium")))
