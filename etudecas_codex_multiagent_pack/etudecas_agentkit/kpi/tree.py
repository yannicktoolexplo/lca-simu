from __future__ import annotations

from typing import Any


def detect_cycles(kpi_tree: dict[str, dict[str, Any]]) -> list[list[str]]:
    """Retourne les cycles détectés dans un arbre/graphe KPI."""
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[list[str]] = []

    def children_of(node: str) -> list[str]:
        children = kpi_tree.get(node, {}).get("children", {})
        if isinstance(children, dict):
            return list(children)
        return list(children or [])

    def visit(node: str, stack: list[str]) -> None:
        if node in visiting:
            cycles.append(stack[stack.index(node):] + [node] if node in stack else [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for child in children_of(node):
            visit(child, stack + [child])
        visiting.remove(node)
        visited.add(node)

    for node in kpi_tree:
        visit(node, [node])
    return cycles
