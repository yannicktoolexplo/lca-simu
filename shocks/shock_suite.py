# shock_suite.py
from typing import Any, Dict, List, Tuple, Optional

# Essaie d'importer ta CrisisEvent ; sinon fallback compatible
try:
    from resilience.event_engine import CrisisEvent  # adapte si ton module a un autre nom
except Exception:
    from dataclasses import dataclass
    @dataclass
    class CrisisEvent:
        time: int
        duration: int
        type: str
        target: Any
        magnitude: float = 1.0
        meta: Optional[Dict[str, Any]] = None
        _id: Optional[str] = None

def _iter_sites(state: Dict) -> List[str]:
    caps = state.get("capacity_nominal") or state.get("capacity") or {}
    return list(caps.keys())

def _iter_materials(state: Dict) -> List[str]:
    sup = state.get("supply_nominal") or state.get("supply") or {}
    return list(sup.keys())

def _iter_lanes(state: Dict) -> List[Tuple[str, str, str]]:
    routes = state.get("routes") or {}
    return list(routes.keys())

def _iter_modes(state: Dict) -> List[str]:
    lanes = _iter_lanes(state)
    return sorted(list({m for (_, _, m) in lanes}))

def _iter_nodes_from_routes(state: Dict) -> List[str]:
    lanes = _iter_lanes(state)
    nodes = {o for (o, _, _) in lanes} | {d for (_, d, _) in lanes}
    return sorted(list(nodes))

def _share_site(state: Dict, site: str) -> float:
    caps = state.get("capacity_nominal") or {}
    total = sum(caps.values()) or 1.0
    return float(caps.get(site, 0.0)) / float(total)

def _share_material(state: Dict, mat: str) -> float:
    sup = state.get("supply_nominal") or {}
    total = sum(sup.values()) or 1.0
    return float(sup.get(mat, 0.0)) / float(total)

def _share_lane_capacity(state: Dict, lane: Tuple[str, str, str]) -> float:
    routes = state.get("routes") or {}
    cap = routes.get(lane, {}).get("cap_per_day", 0)
    total = sum(info.get("cap_per_day", 0) for info in routes.values()) or 1.0
    return float(cap) / float(total)

def build_shock_suite(
    state: Dict,
    *,
    start_time: int = 20,
    duration_days: int = 10,
    include: Dict[str, bool] = None
) -> Dict[str, List[CrisisEvent]]:
    """
    Construit un portefeuille de chocs couvrant : sites, matières, routes, modes, nœuds.
    Types standardisés attendus par l'EventManager:
      site_shutdown, site_capacity_drop, material_block, material_capacity_drop,
      route_blocked, capacity_drop, leadtime_spike, mode_ban, node_closed
    """
    inc = include or {
        "site_shutdown": True,
        "site_capacity_drop": True,
        "material_block": True,
        "material_capacity_drop": True,
        "route_blocked": True,
        "capacity_drop": True,
        "leadtime_spike": True,
        "mode_ban": True,
        "node_closed": True,
    }
    out: Dict[str, List[CrisisEvent]] = {}

    if inc.get("site_shutdown"):
        for s in _iter_sites(state):
            out[f"site_shutdown::{s}"] = [CrisisEvent(start_time, duration_days, "site_shutdown", s, 1.0)]
    if inc.get("site_capacity_drop"):
        for s in _iter_sites(state):
            out[f"site_drop40::{s}"] = [CrisisEvent(start_time, duration_days, "site_capacity_drop", s, 0.4)]
    if inc.get("material_block"):
        for m in _iter_materials(state):
            out[f"material_block::{m}"] = [CrisisEvent(start_time, duration_days, "material_block", m, 1.0)]
    if inc.get("material_capacity_drop"):
        for m in _iter_materials(state):
            out[f"material_drop50::{m}"] = [CrisisEvent(start_time, duration_days, "material_capacity_drop", m, 0.5)]
    if inc.get("route_blocked"):
        for ln in _iter_lanes(state):
            out[f"route_blocked::{ln}"] = [CrisisEvent(start_time, duration_days, "route_blocked", ln, 1.0)]
    if inc.get("capacity_drop"):
        for ln in _iter_lanes(state):
            out[f"route_drop60::{ln}"] = [CrisisEvent(start_time, duration_days, "capacity_drop", ln, 0.6)]
    if inc.get("leadtime_spike"):
        for ln in _iter_lanes(state):
            out[f"leadtime_spike+3::{ln}"] = [CrisisEvent(start_time, duration_days, "leadtime_spike", ln, 3)]
    if inc.get("mode_ban"):
        for md in _iter_modes(state):
            out[f"mode_ban::{md}"] = [CrisisEvent(start_time, duration_days, "mode_ban", md, 1.0)]
    if inc.get("node_closed"):
        for nd in _iter_nodes_from_routes(state):
            out[f"node_closed::{nd}"] = [CrisisEvent(start_time, duration_days, "node_closed", nd, 1.0)]
    return out

def estimate_exogenous_severity(state: Dict, ev: CrisisEvent) -> float:
    """
    Indice de sévérité 'exogène' ~ magnitude * durée * part impactée.
    Sert à comparer des chocs de criticité 'similaire' sur des cibles différentes.
    """
    part = 1.0
    if ev.type in ("site_shutdown", "site_capacity_drop"):
        part = _share_site(state, str(ev.target))
    elif ev.type in ("material_block", "material_capacity_drop"):
        part = _share_material(state, str(ev.target))
    elif ev.type in ("route_blocked", "capacity_drop", "leadtime_spike"):
        part = _share_lane_capacity(state, tuple(ev.target))
    elif ev.type in ("mode_ban", "node_closed"):
        part = 1.0
    mag = float(ev.magnitude)
    dur = int(ev.duration)
    return mag * dur * max(1e-6, part)
