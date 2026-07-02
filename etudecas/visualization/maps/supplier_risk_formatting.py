"""Formatting helpers for supplier criticality views."""

from __future__ import annotations

import math
from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


def risk_ratio(value: Any) -> float:
    numeric = _to_float(value)
    if numeric is None or math.isnan(numeric):
        return 0.0
    return max(0.0, min(1.0, float(numeric)))


def risk_pct(value: Any, digits: int = 1) -> str:
    numeric = 100.0 * risk_ratio(value)
    return f"{numeric:.{digits}f}%"


def supplier_risk_zone_rank(zone: Any) -> int:
    value = str(zone or "").strip().lower()
    return {
        "vert": 0,
        "green": 0,
        "jaune": 1,
        "amber": 1,
        "orange": 2,
        "rouge": 3,
        "red": 3,
        "critique": 4,
        "critical": 4,
    }.get(value, -1)


def supplier_risk_zone_color(zone: Any) -> str:
    rank = supplier_risk_zone_rank(zone)
    if rank >= 3:
        return "#dc2626"
    if rank == 2:
        return "#d97706"
    if rank == 1:
        return "#f59e0b"
    return "#0f766e"


def supplier_risk_zone_label(zone: Any) -> str:
    rank = supplier_risk_zone_rank(zone)
    if rank >= 3:
        return "Critique"
    if rank == 2:
        return "Eleve"
    if rank == 1:
        return "Modere"
    if rank == 0:
        return "Faible"
    return str(zone or "n/a")


def supplier_risk_action_label(action: Any) -> str:
    value = str(action or "").strip()
    labels = {
        "routine_monitoring": "surveillance de routine",
        "standard_monitoring": "surveillance standard",
        "watch_collect_data_and_confirm_supplier_status": "surveiller, completer les donnees et confirmer le fournisseur",
    }
    return labels.get(value, value or "n/a")


def supplier_risk_worst_zone(rows: list[dict[str, str]], field: str = "decision_zone") -> str:
    if not rows:
        return "n/a"
    return max((str(row.get(field) or "n/a") for row in rows), key=supplier_risk_zone_rank)


def supplier_risk_zone_counts_text(counts: dict[str, Any] | None) -> str:
    if not counts:
        return "n/a"
    ordered = ["rouge", "orange", "jaune", "vert", "red", "amber", "green"]
    seen: set[str] = set()
    parts: list[str] = []
    for zone in ordered:
        if zone in counts:
            parts.append(f"{zone}={counts.get(zone)}")
            seen.add(zone)
    for zone, count in sorted(counts.items()):
        if zone not in seen:
            parts.append(f"{zone}={count}")
    return ", ".join(parts) or "n/a"

