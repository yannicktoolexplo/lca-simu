# adapters.py
# NOTE: pas d'import __future__ pour éviter les soucis d'ordre d'import.

from typing import Any, Dict, List, Tuple
from dataclasses import dataclass
import importlib
import math

# === 1) Import direct de ta simu SimPy ==============================
#    -> Ton moteur : line_production.line_production.run_simulation
try:
    from line_production.line_production import run_simulation as _run_lines
except Exception as e:
    raise ImportError(
        f"Impossible d'importer line_production.line_production.run_simulation : {e}"
    )

# === 2) Compatibilité des événements ================================
# nombre d’unités SimPy par “jour” logique (tu traces déjà env.now/8)
TIME_UNITS_PER_DAY_DEFAULT = 8

@dataclass
class _CompatEvent:
    time: int
    duration: int
    event_type: str      # ce que ta simu attend: 'panne' | 'rupture_fournisseur' | 'retard'
    target: Any          # site ('PLANT_FR'...) ou matière ('aluminium'...)
    magnitude: float = 1.0
    description: str = ""

# mapping des types "riches" -> types gérés par ta simu
_TYPE_MAP = {
    "site_shutdown": "panne",
    "site_capacity_drop": "panne",           # approx panne totale
    "material_block": "rupture_fournisseur",
    "material_capacity_drop": "retard",      # approx retard d'appro
    "route_blocked": "retard",               # si on arrive à lier à une matière
    "capacity_drop": "retard",
    "leadtime_spike": "retard",
    "mode_ban": "retard",
    "node_closed": "retard",
    # déjà compatibles
    "panne": "panne",
    "rupture_fournisseur": "rupture_fournisseur",
    "retard": "retard",
}

def _material_alias(name: Any) -> Any:
    """Normalise les alias matières vers ce que ta simu utilise."""
    if not isinstance(name, str):
        return name
    m = name.strip().lower()
    aliases = {
        "al": "aluminium",
        "alu": "aluminium",
        "aluminum": "aluminium",
        "aluminium": "aluminium",
        "foam": "foam",
        "fabric": "fabric",
        "paint": "paint",
        "polymers": "foam",
    }
    return aliases.get(m, name)

def _infer_material_from_lane(lane) -> Any:
    """
    lane = (origin, dest, mode).
    Si origin commence par 'SUP_', on infère la matière: ('SUP_Al', 'PLANT_FR','road') -> 'aluminium'
    """
    if not isinstance(lane, tuple) or len(lane) < 1:
        return None
    origin = str(lane[0])
    if origin.upper().startswith("SUP_"):
        mat_code = origin.split("_", 1)[1] if "_" in origin else origin[4:]
        return _material_alias(mat_code)
    return None

def _normalize_events_for_run_simulation(events: List[Any], time_units_per_day: int) -> List[_CompatEvent]:
    out: List[_CompatEvent] = []
    scale = max(1, int(time_units_per_day))
    for ev in events or []:
        raw_type = getattr(ev, "event_type", None) or getattr(ev, "type", None)
        if not raw_type:
            continue
        mapped = _TYPE_MAP.get(str(raw_type), None)
        if not mapped:
            continue

        # ⚠️ on convertit jours → unités SimPy
        time = int(getattr(ev, "time", 0)) * scale
        duration = int(getattr(ev, "duration", 0)) * scale

        target = getattr(ev, "target", None)
        magnitude = float(getattr(ev, "magnitude", 1.0))
        desc = getattr(ev, "description", "") or ""

        if isinstance(target, tuple):
            maybe_mat = _infer_material_from_lane(target)
            if maybe_mat is None:
                continue
            target = maybe_mat
            mapped = "retard"

        if mapped in ("rupture_fournisseur", "retard"):
            target = _material_alias(target)

        out.append(_CompatEvent(
            time=time,
            duration=duration,
            event_type=mapped,
            target=target,
            magnitude=magnitude,
            description=str(desc),
        ))
    return out

def _build_total_ts_from_lines(all_lines: List[Dict[str, Any]]) -> List[float]:
    import math as _math
    def _find_total_key(d: Dict[str, Any]) -> str | None:
        for k in d.keys():
            ks = str(k).lower()
            if "total" in ks and "seat" in ks and "made" in ks:
                return k
        return None
    lines_cum_series = []
    t_max = 0.0
    for line_dict in all_lines or []:
        if not isinstance(line_dict, dict):
            continue
        key = _find_total_key(line_dict)
        if key is None:
            continue
        pair = line_dict.get(key)
        if (isinstance(pair, (list, tuple)) and len(pair) == 2
                and isinstance(pair[0], list) and isinstance(pair[1], list)):
            times = [float(x) for x in pair[0]]
            cumul = [float(x) for x in pair[1]]
            if times and cumul:
                zipped = sorted(zip(times, cumul), key=lambda x: x[0])
                times = [z for z, _ in zipped]
                cumul = [c for _, c in zipped]
                t_max = max(t_max, times[-1])
                lines_cum_series.append((times, cumul))
    if not lines_cum_series:
        return [0.0]
    T = max(1, int(_math.ceil(t_max)))
    grid = list(range(T))
    def _step_at(times, cumul, t):
        idx = 0
        while idx < len(times) and times[idx] <= t + 1e-9:
            idx += 1
        return 0.0 if idx == 0 else cumul[idx - 1]
    total = [0.0] * T
    for times, cumul in lines_cum_series:
        cum_on_grid = [_step_at(times, cumul, t) for t in grid]
        flow = [cum_on_grid[0]] + [max(0.0, cum_on_grid[i] - cum_on_grid[i-1]) for i in range(1, T)]
        for i in range(T):
            total[i] += flow[i]
    return total

def _compute_costs(prod_ts: List[float], config: Dict[str, Any]) -> Dict[str, float]:
    T = len(prod_ts)
    demand_per_day = float(config.get("target_daily_output", 100.0))
    demand_ts = [demand_per_day] * T
    params = dict(
        c_var= float(config.get("cost_params", {}).get("c_var", 100.0)),
        c_fixed_per_day=float(config.get("cost_params", {}).get("c_fixed_per_day", 2000.0)),
        c_freight=float(config.get("cost_params", {}).get("c_freight", 10.0)),
        penalty_per_missing=float(config.get("cost_params", {}).get("penalty_per_missing", 150.0)),
    )
    variable = params["c_var"] * sum(prod_ts)
    fixed    = params["c_fixed_per_day"] * T
    freight  = params["c_freight"] * sum(prod_ts)
    missing  = sum(max(0.0, d - p) for d, p in zip(demand_ts, prod_ts))
    penalties = params["penalty_per_missing"] * missing
    return {
        "variable": variable,
        "fixed": fixed,
        "freight": freight,
        "penalties": penalties,
        "total": variable + fixed + freight + penalties,
    }



# === 3) Fonction de simulation par défaut ===========================

def default_sim_func(config: Dict[str, Any], events: List[Any]) -> Dict[str, Any]:
    lines_cfg = config.get("lines_config")
    if not isinstance(lines_cfg, list) or not lines_cfg:
        raise KeyError("config['lines_config'] est requis et doit être une liste de configs de lignes.")

    seat_weight = config.get("seat_weight", 130)
    time_units_per_day = int(config.get("time_units_per_day", TIME_UNITS_PER_DAY_DEFAULT))

    norm_events = _normalize_events_for_run_simulation(events, time_units_per_day)

    all_prod, all_env = _run_lines(lines_cfg, seat_weight=seat_weight, events=norm_events)

        # --- après avoir obtenu all_prod, all_env ---
    prod_ts_total = _build_total_ts_from_lines(all_prod)

    # 1) Déterminer la demande cible (si absente ou "auto")
    target_cfg = config.get("target_daily_output", "auto")
    if (target_cfg is None) or (isinstance(target_cfg, str) and target_cfg.lower() == "auto"):
        # si on est en scénario (events non vides), on calcule une baseline interne
        if events:
            base_prod, _ = _run_lines(lines_cfg, seat_weight=seat_weight, events=[])
            base_ts = _build_total_ts_from_lines(base_prod)
            target_daily_output = max(1.0, sum(base_ts) / max(1, len(base_ts)))
        else:
            # en baseline, on prend la moyenne observée
            target_daily_output = max(1.0, sum(prod_ts_total) / max(1, len(prod_ts_total)))
    else:
        target_daily_output = float(target_cfg)

    # 2) Calculer les coûts en utilisant cette cible
    cost_cfg = dict(config)
    cost_cfg["target_daily_output"] = target_daily_output
    costs_raw = _compute_costs(prod_ts_total, cost_cfg)

    # 3) Ajouter des alias de clés pour coller à ce que le comparateur peut chercher
    costs = dict(costs_raw)
    costs.setdefault("production", costs["variable"])   # alias
    costs.setdefault("transport", costs["freight"])     # alias
    costs.setdefault("inventory", costs["fixed"])       # alias

    return {
        "all_production_data": all_prod,
        "all_enviro_data": all_env,
        "events_used": [e.__dict__ for e in norm_events],
        "production_ts_total": prod_ts_total,
        "costs": costs,
    }


# === 4) Extracteur de série temporelle agrégée ======================

def default_ts_extractor(res: Dict[str, Any]) -> List[float]:
    """
    Construit une série agrégée (toute chaîne) à partir des sorties SimPy de ton line_production :
    chaque ligne produit un dict avec ('Total Seats made') = (times, cumul).
    On interpole le cumul sur un grillage d'entiers (jours), puis on différencie (diff) pour
    obtenir la production par pas de temps, avant d'agréger toutes les lignes.
    """
    # Chemin direct si déjà présent
    if isinstance(res.get("production_ts_total"), list):
        return list(res["production_ts_total"])

    # Récupérer la liste des dicts "line.get_data()" (all_production_data)
    all_lines = None
    if isinstance(res, dict):
        for k in ("all_production_data", "all_prod", "production_data"):
            if k in res:
                all_lines = res[k]
                break
    if not isinstance(all_lines, list) or not all_lines:
        return [0.0]

    # repérer la clé "Total Seats made"
    def _find_total_key(d: Dict[str, Any]) -> str | None:
        for k in d.keys():
            ks = str(k).lower()
            if "total" in ks and "seat" in ks and "made" in ks:
                return k
        return None

    # collecter (times, cumul) pour chaque ligne
    lines_cum_series: List[Tuple[List[float], List[float]]] = []
    t_max = 0.0
    for line_dict in all_lines:
        if not isinstance(line_dict, dict):
            continue
        key = _find_total_key(line_dict)
        if key is None:
            continue
        pair = line_dict.get(key)
        if (isinstance(pair, (list, tuple)) and len(pair) == 2
                and isinstance(pair[0], list) and isinstance(pair[1], list)):
            times = [float(x) for x in pair[0]]
            cumul = [float(x) for x in pair[1]]
            if times and cumul:
                zipped = sorted(zip(times, cumul), key=lambda x: x[0])
                times = [z for z, _ in zipped]
                cumul = [c for _, c in zipped]
                t_max = max(t_max, times[-1])
                lines_cum_series.append((times, cumul))

    if not lines_cum_series:
        return [0.0]

    # grille d'échantillonnage : jours entiers [0, ..., T]
    T = max(1, int(math.ceil(t_max)))
    grid = list(range(T))

    def _step_at(times: List[float], cumul: List[float], t: int) -> float:
        # cumul(t) = dernière valeur observée <= t
        idx = 0
        while idx < len(times) and times[idx] <= t + 1e-9:
            idx += 1
        return 0.0 if idx == 0 else cumul[idx - 1]

    total_prod = [0.0] * T
    for times, cumul in lines_cum_series:
        cum_on_grid = [_step_at(times, cumul, t) for t in grid]
        flow = [cum_on_grid[0]] + [max(0.0, cum_on_grid[i] - cum_on_grid[i-1]) for i in range(1, T)]
        for i in range(T):
            total_prod[i] += flow[i]

    return total_prod

# === 5) Extracteur de coûts (robuste aux dicts imbriqués) ============

def _sum_numeric(x) -> float:
    from numbers import Number
    if isinstance(x, Number):
        return float(x)
    if x is None:
        return 0.0
    if isinstance(x, dict):
        return sum(_sum_numeric(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return sum(_sum_numeric(v) for v in x)
    try:
        return float(x)
    except Exception:
        return 0.0

def default_cost_extractor(res: Dict[str, Any]) -> Dict[str, float]:
    c = res.get("costs")
    if isinstance(c, dict):
        flat: Dict[str, float] = {}
        for k, v in c.items():
            flat[k] = _sum_numeric(v)
        return flat
    # fallback si pas de coûts
    return {"production": 0.0, "transport": 0.0, "penalties": 0.0, "inventory": 0.0}

# === 6) Extracteur de service (optionnel) ============================

def default_service_extractor(res: Dict[str, Any]) -> float | None:
    """
    Si ta simu expose un service agrégé (ex: fill_rate moyen), tu peux le renvoyer ici.
    Sinon, renvoie None -> les métriques se basent uniquement sur la série de production.
    """
    s = res.get("service")
    if isinstance(s, dict) and "on_time" in s:
        try:
            return float(s["on_time"])
        except Exception:
            return None
    return None
