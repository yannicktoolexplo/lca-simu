# compare_shocks.py
"""
Lance une campagne Baseline vs. Suite de chocs sur toute la supply,
calcule les métriques de résilience et affiche/exports un tableau comparatif.

Prérequis:
- adapters.py : implémenter default_sim_func() pour appeler TA simulation
                (ou utiliser le fallback de test ci-dessous en mettant --use-dummy)
- shock_experiments.py, shock_suite.py, resilience_metrics.py : tels que fournis
"""

from typing import Dict, Any, List
from dataclasses import asdict, is_dataclass
from copy import deepcopy
from pprint import pprint
import argparse
import csv
import math
import sys

from shocks.shock_experiments import ShockExperimentRunner
from adapters import (
    default_sim_func,
    default_ts_extractor,
    default_cost_extractor,
    default_service_extractor,
)

# ---------------------------------------------------------------------------
# [OPTIONNEL] Fallback de démo si tu n'as pas encore branché default_sim_func.
#   Utilise --use-dummy pour tester l'enchaînement complet sans ta simu réelle.
#   Ce dummy renvoie une série "production" linéaire et applique une perte
#   simpliste pendant la fenêtre du choc pour montrer les métriques.
# ---------------------------------------------------------------------------

def _dummy_sim_func(config: Dict[str, Any], events: List[Any]) -> Dict[str, Any]:
    """
    Dummy réaliste :
    - Prod baseline: 100 u/jour sur H jours
    - Impact d'un événement = drop fractionnel *part du système touchée* selon le type
    - Combinaison des drops multiplicative (eff = prod * Π(1 - drop_i))
    - Ramp-up linéaire après fin de crise (5 jours)
    - Coûts: production + transport + pénalités + coût fixe (pour Δcost_rel pertinent)
    """
    horizon = int(config.get("horizon", 120))
    state = config.get("_suite_state", {})  # capacity_nominal, supply_nominal, routes
    base = [100.0] * horizon

    caps = state.get("capacity_nominal", {}) or state.get("capacity", {})
    sup  = state.get("supply_nominal", {}) or state.get("supply", {})
    routes = state.get("routes", {})

    tot_cap = float(sum(caps.values())) or 1.0
    tot_sup = float(sum(sup.values())) or 1.0
    tot_lane_cap = float(sum(info.get("cap_per_day", 0) for info in routes.values())) or 1.0

    def share_site(site: str) -> float:
        return float(caps.get(str(site), 0.0)) / tot_cap

    def share_mat(mat: str) -> float:
        return float(sup.get(str(mat), 0.0)) / tot_sup

    def share_lane(lane) -> float:
        info = routes.get(tuple(lane), {})
        return float(info.get("cap_per_day", 0.0)) / tot_lane_cap

    def share_mode(md: str) -> float:
        s = 0.0
        for (o, d, m), info in routes.items():
            if m == md:
                s += float(info.get("cap_per_day", 0.0))
        return s / tot_lane_cap if tot_lane_cap > 0 else 0.0

    def share_node(node: str) -> float:
        """Part de capacité des lanes touchant ce nœud (origin ou dest)."""
        s = 0.0
        for (o, d, m), info in routes.items():
            if o == node or d == node:
                s += float(info.get("cap_per_day", 0.0))
        return s / tot_lane_cap if tot_lane_cap > 0 else 0.0

    # profil d’impact par type (drop de production “équivalent”)
    def event_drop(ev) -> float:
        t = getattr(ev, "type", "")
        mag = float(getattr(ev, "magnitude", 0.0))
        tgt = getattr(ev, "target", None)

        if t == "site_shutdown":
            return min(1.0, 1.0 * share_site(tgt))
        if t == "site_capacity_drop":
            return min(1.0, mag * share_site(tgt))

        if t == "material_block":
            return min(1.0, 0.8 * share_mat(tgt))
        if t == "material_capacity_drop":
            return min(1.0, mag * share_mat(tgt))

        if t == "route_blocked":
            return min(1.0, 0.7 * share_lane(tgt))
        if t == "capacity_drop":
            return min(1.0, mag * share_lane(tgt))

        if t == "mode_ban":
            return min(1.0, 0.6 * share_mode(str(tgt)))

        if t == "node_closed":
            return min(1.0, 0.6 * share_node(str(tgt)))  # <-- proportionnel à la part réelle

        if t == "leadtime_spike":
            return min(0.3, 0.05 * mag)

        if t == "cost_surge":
            return 0.0

        return min(1.0, mag * 0.1)

    # calendrier de drop + ramp-up
    prod = base[:]
    service_ts = [1.0] * horizon
    cost_factor_ts = [1.0] * horizon
    per_day_drops = [0.0] * horizon
    per_day_service_loss = [0.0] * horizon
    RAMP = 5  # jours

    for ev in events or []:
        t0 = int(getattr(ev, "time", 0))
        dur = int(getattr(ev, "duration", 0))
        t1 = min(horizon, max(0, t0 + dur))
        dr = event_drop(ev)

        for t in range(max(0, t0), t1):
            per_day_drops[t] = 1.0 - (1.0 - per_day_drops[t]) * (1.0 - dr)

        for k in range(1, RAMP + 1):
            t = t1 + k - 1
            if t >= horizon: break
            ramp_dr = dr * max(0.0, 1.0 - k / (RAMP + 0.0001))
            per_day_drops[t] = 1.0 - (1.0 - per_day_drops[t]) * (1.0 - ramp_dr)

        etype = getattr(ev, "type", "")
        if etype in ("leadtime_spike","route_blocked","capacity_drop","mode_ban","node_closed"):
            for t in range(max(0, t0), min(horizon, t0 + dur)):
                per_day_service_loss[t] = 1.0 - (1.0 - per_day_service_loss[t]) * (1.0 - min(0.7, dr))
        if etype == "cost_surge":
            for t in range(max(0, t0), min(horizon, t0 + dur)):
                cost_factor_ts[t] *= (1.0 + float(getattr(ev, "magnitude", 0.0)))

    penalties = 0.0
    c_unit_prod = 1.0
    c_unit_trans = 0.1
    penalty_per_missing_unit = 1.2     # ↑ pénalités
    fixed_cost_per_day = 50.0          # ↑ coût fixe (site/structuration)

    for t in range(horizon):
        eff = max(0.0, 1.0 - per_day_drops[t])
        prod[t] = base[t] * eff
        service_ts[t] *= max(0.0, 1.0 - per_day_service_loss[t])

    total_prod = sum(prod)
    missing = sum(max(0.0, b - p) for b, p in zip(base, prod))
    penalties += missing * penalty_per_missing_unit

    avg_cost_factor = sum(cost_factor_ts) / float(horizon)
    costs = {
        "production": total_prod * c_unit_prod * avg_cost_factor,
        "transport":  total_prod * c_unit_trans * avg_cost_factor,
        "penalties":  penalties,
        "inventory":  0.0,
        "fixed":      fixed_cost_per_day * horizon,  # <-- nouveau
    }

    service_on_time = sum(service_ts) / float(horizon)

    return {
        "production_ts_total": prod,
        "costs": costs,
        "service": {"on_time": service_on_time},
    }


# ---------------------------------------------------------------------------
# Helpers pour construire rapidement une config de base & un état nominal
# Si tu as déjà ces objets dans ton projet, ignore ces fonctions et passe
# directement tes objets à main() (base_config, state_for_suite).
# ---------------------------------------------------------------------------

# --- AJOUT EN HAUT DU FICHIER SI ABSENT ---
import importlib

def _auto_load_lines_config():
    """
    Essaie de récupérer lines_config/LINES_CONFIG où qu'il soit :
    - line_production.line_production_settings
    - line_production_settings
    - scenario_engine
    Si non trouvé, essaye des builders (build_lines_config / get_lines_config / make_lines_config).
    """
    candidates = [
        ("line_production.line_production_settings", "LINES_CONFIG"),
        ("line_production.line_production_settings", "lines_config"),
        ("line_production_settings", "LINES_CONFIG"),
        ("line_production_settings", "lines_config"),
        ("resilience.scenario_engine", "LINES_CONFIG"),
        ("resilience.scenario_engine", "lines_config"),
    ]
    for mod_name, var_name in candidates:
        try:
            m = importlib.import_module(mod_name)
            if hasattr(m, var_name):
                val = getattr(m, var_name)
                if isinstance(val, list) and len(val) > 0:
                    return val
        except Exception:
            pass
        # tente des builders dans ce module
        try:
            m = importlib.import_module(mod_name)
            for fn_name in ("build_lines_config", "get_lines_config", "make_lines_config"):
                if hasattr(m, fn_name):
                    val = getattr(m, fn_name)()
                    if isinstance(val, list) and len(val) > 0:
                        return val
        except Exception:
            pass
    raise RuntimeError(
        "Impossible de trouver 'lines_config' / 'LINES_CONFIG'. "
        "Expose une variable LINES_CONFIG (liste de dicts lignes) "
        "ou adapte _auto_load_lines_config()."
    )

def build_base_config() -> dict:
    """
    Base config MINIMALE exigée par run_scenario: elle DOIT contenir 'lines_config'.
    On calcule aussi un 'horizon' raisonnable (max total_time des lignes).
    """
    LINES_CONFIG = _auto_load_lines_config()
    horizon = max([lc.get("total_time", 0) for lc in LINES_CONFIG] + [120])
    return {
        "lines_config": LINES_CONFIG,
        "target_daily_output": "auto",
        "horizon": horizon,
        "time_units_per_day": 8,           # ← pour adapter le calendrier des événements
        "cost_params": {
            "c_var": 100.0,
            "c_fixed_per_day": 2000.0,
            "c_freight": 10.0,
            "penalty_per_missing": 150.0,
        },
    }




def build_state_for_suite() -> Dict[str, Any]:
    """
    État nominal minimal pour générer des chocs (sites, matières, routes).
    Essaie d'importer depuis ton projet ; sinon, fallback de démonstration.
    """
    # 1) essaie d'importer un état nominal du projet
    try:
        from resilience.scenario_engine import get_nominal_state  # si tu as une fonction utilitaire
        st = get_nominal_state()
        # s'assure que les clés attendues existent
        if "routes" in st and any(k in st for k in ("capacity_nominal","capacity")) and any(k in st for k in ("supply_nominal","supply")):
            return st
    except Exception:
        pass

    # 2) fallback : routes/parts de démo
    return {
        "capacity_nominal": {"PLANT_FR": 800, "PLANT_UK": 500, "PLANT_US": 600},
        "supply_nominal": {"Al": 10000, "Fabric": 500, "Foam": 8000},
        "routes": {
            ("SUP_Al", "PLANT_FR", "road"): {"cap_per_day": 5000, "lead_time": 2, "active": True},
            ("PLANT_FR", "DC_FR", "road"):  {"cap_per_day": 1200, "lead_time": 1, "active": True},
            ("DC_FR", "FR", "road"):        {"cap_per_day": 1000, "lead_time": 1, "active": True},
            ("PLANT_UK", "DC_UK", "sea"):   {"cap_per_day": 800,  "lead_time": 5, "active": True},
            ("DC_UK", "UK", "road"):        {"cap_per_day": 900,  "lead_time": 1, "active": True},
            ("PLANT_US", "DC_US", "road"):  {"cap_per_day": 1000, "lead_time": 2, "active": True},
            ("DC_US", "US", "road"):        {"cap_per_day": 1000, "lead_time": 1, "active": True},
        },
    }


# ---------------------------------------------------------------------------
# Affichage du tableau de résultats
# ---------------------------------------------------------------------------

def _print_table(rows: List[Any], top: int = 20):
    rows = _rows_to_dicts(rows)  # accepte dict/dataclass/objets
    print("\n=== Classement des chocs (du plus critique au plus résilient) ===")
    header = ["rank","shock","type","target","exo_sev","ampl_rel","area_rel","area_rel_norm","recovery","Δcost_rel","score"]
    print("{:<4}  {:<28}  {:<18}  {:<28}  {:>7}  {:>8}  {:>8}  {:>13}  {:>8}  {:>9}  {:>6}".format(*header))
    for i, rd in enumerate(rows[:top], 1):
        name = rd.get("shock", rd.get("shock_name", ""))

        exo  = float(rd.get("exo_sev", rd.get("exogenous_severity", 0.0)) or 0.0)
        ampl = float(rd.get("ampl_rel", rd.get("amplitude_rel", 0.0)) or 0.0)
        area = float(rd.get("area_rel", rd.get("lost_area_rel", 0.0)) or 0.0)
        area_norm = float(rd.get("area_rel_norm", (area/exo if exo > 1e-9 else 0.0)) or 0.0)
        rec  = int(rd.get("recovery", rd.get("recovery_time", 0)) or 0)
        dcost= float(rd.get("Δcost_rel", rd.get("cost_delta_rel", 0.0)) or 0.0)
        score= float(rd.get("score", 0.0) or 0.0)

        print(str(i).ljust(5),
              str(name)[:28].ljust(30),
              str(rd.get("type",""))[:18].ljust(20),
              str(rd.get("target",""))[:26].ljust(28),
              f"{exo:7.3f}", f"{ampl:9.3f}",
              f"{area:9.3f}", f"{area_norm:14.3f}",
              f"{rec:9d}",   f"{dcost:10.3f}",
              f"{score:7.3f}")
    print()


def _export_csv(path: str, rows: List[Dict[str, Any]]):
    fieldnames = [
        "shock_name","type","target",
        "exogenous_severity","amplitude_rel","lost_area_rel","area_rel_norm",
        "recovery_time","cost_delta_rel","score"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            row = dict(r)
            if "shock" in row and "shock_name" not in row:
                row["shock_name"] = row["shock"]
            exo = float(row.get("exogenous_severity", 0.0))
            area_rel = float(row.get("lost_area_rel", 0.0))
            row["area_rel_norm"] = (area_rel / exo) if exo > 1e-9 else 0.0
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"[OK] Export CSV -> {path}")

def _parse_duration_range(expr: str):
    """
    "5:40:5" -> [5,10,15,20,25,30,35,40]
    "5:20"   -> [5,6,7,...,20]
    """
    if not expr:
        return []
    parts = [p.strip() for p in expr.split(':')]
    if len(parts) == 2:
        start, end = map(int, parts)
        step = 1
    elif len(parts) == 3:
        start, end, step = map(int, parts)
    else:
        raise ValueError(f"Format attendu 'start:end[:step]', reçu: {expr}")
    if step == 0:
        raise ValueError("Le pas (step) doit être non nul.")
    if start > end and step > 0:
        step = -step
    return list(range(start, end + (1 if step > 0 else -1), step))


def _export_csv_sweep(path: str, rows: List[Dict[str, Any]]):
    """
    Export consolidé multi-durées. On ajoute 'duration_days' aux colonnes existantes
    sans modifier _export_csv(...) que tu utilises déjà ailleurs.
    """
    import csv
    fieldnames = [
        "duration_days",                      # ← colonne supplémentaire
        "shock_name","type","target",
        "exogenous_severity","amplitude_rel","lost_area_rel","area_rel_norm",
        "recovery_time","cost_delta_rel","score"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            row = _row_to_dict(r)
            # harmonisation des noms de clés
            if "shock" in row and "shock_name" not in row:
                row["shock_name"] = row["shock"]
            # calcule area_rel_norm si besoin
            exo = float(row.get("exogenous_severity", row.get("exo_sev", 0.0)) or 0.0)
            area_rel = float(row.get("lost_area_rel", row.get("area_rel", 0.0)) or 0.0)
            row["exogenous_severity"] = row.get("exogenous_severity", row.get("exo_sev", 0.0))
            row["amplitude_rel"] = row.get("amplitude_rel", row.get("ampl_rel", 0.0))
            row["lost_area_rel"] = area_rel
            row["area_rel_norm"] = (area_rel / exo) if exo > 1e-9 else 0.0
            row["recovery_time"] = row.get("recovery_time", row.get("recovery", 0))
            row["cost_delta_rel"] = row.get("cost_delta_rel", row.get("Δcost_rel", 0.0))
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"[OK] Export sweep CSV -> {path}")

def _row_to_dict(r: Any) -> Dict[str, Any]:
    if isinstance(r, dict):
        return r
    try:
        if is_dataclass(r):
            return asdict(r)
    except Exception:
        pass
    if hasattr(r, "_asdict"):
        try:
            return dict(r._asdict())
        except Exception:
            pass
    out: Dict[str, Any] = {}
    for k in (
        "shock","shock_name","type","target",
        "exo_sev","exogenous_severity",
        "ampl_rel","amplitude_rel",
        "area_rel","lost_area_rel","area_rel_norm",
        "recovery","recovery_time",
        "Δcost_rel","cost_delta_rel",
        "score"
    ):
        if hasattr(r, k):
            out[k] = getattr(r, k)
    return out

def _rows_to_dicts(rows: List[Any]) -> List[Dict[str, Any]]:
    return [_row_to_dict(x) for x in rows]


def _print_rows_simple(rows: List[Any], top: int = 10):
    rows = _rows_to_dicts(rows)
    print("rank  shock".ljust(31), "type".ljust(20), "target".ljust(28),
          "exo_sev".rjust(7), "ampl_rel".rjust(9),
          "area_rel".rjust(9), "area_rel_norm".rjust(14),
          "recovery".rjust(9), "Δcost_rel".rjust(10), "score".rjust(7))
    for i, rd in enumerate(rows[:top], 1):
        name = rd.get("shock", rd.get("shock_name", ""))
        exo  = float(rd.get("exo_sev", rd.get("exogenous_severity", 0.0)) or 0.0)
        ampl = float(rd.get("ampl_rel", rd.get("amplitude_rel", 0.0)) or 0.0)
        area = float(rd.get("area_rel", rd.get("lost_area_rel", 0.0)) or 0.0)
        area_norm = float(rd.get("area_rel_norm", (area/exo if exo > 1e-9 else 0.0)) or 0.0)
        rec  = int(rd.get("recovery", rd.get("recovery_time", 0)) or 0)
        dcost= float(rd.get("Δcost_rel", rd.get("cost_delta_rel", 0.0)) or 0.0)
        score= float(rd.get("score", 0.0) or 0.0)

        print(str(i).ljust(5),
              str(name)[:28].ljust(30),
              str(rd.get("type",""))[:18].ljust(20),
              str(rd.get("target",""))[:26].ljust(28),
              f"{exo:7.3f}", f"{ampl:9.3f}",
              f"{area:9.3f}", f"{area_norm:14.3f}",
              f"{rec:9d}",   f"{dcost:10.3f}",
              f"{score:7.3f}")
        
def _linreg(xs: List[float], ys: List[float]):
    """Régression linéaire Y = a + b X -> (b, a, R^2)."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0), 0.0
    meanx = sum(xs) / n
    meany = sum(ys) / n
    cov = sum((x - meanx) * (y - meany) for x, y in zip(xs, ys))
    varx = sum((x - meanx) ** 2 for x in xs)
    slope = (cov / varx) if varx > 1e-12 else 0.0
    intercept = meany - slope * meanx
    vary = sum((y - meany) ** 2 for y in ys)
    r2 = (cov * cov) / (varx * vary) if varx > 1e-12 and vary > 1e-12 else 0.0
    return slope, intercept, r2

def _metric_value(rd: Dict[str, Any], metric: str) -> float:
    # Harmonise les alias
    if metric == 'lost_area_rel':
        return float(rd.get('lost_area_rel', rd.get('area_rel', 0.0)) or 0.0)
    if metric == 'amplitude_rel':
        return float(rd.get('amplitude_rel', rd.get('ampl_rel', 0.0)) or 0.0)
    if metric == 'cost_delta_rel':
        return float(rd.get('cost_delta_rel', rd.get('Δcost_rel', 0.0)) or 0.0)
    if metric == 'score':
        return float(rd.get('score', 0.0) or 0.0)
    return 0.0

def _build_summary(all_rows: List[Dict[str, Any]], metric: str = 'lost_area_rel') -> List[Dict[str, Any]]:
    # Regroupe par choc
    groups: Dict[str, Dict[str, Any]] = {}
    for r in all_rows:
        rd = _row_to_dict(r)
        name = rd.get('shock', rd.get('shock_name', ''))
        g = groups.setdefault(name, {'rows': [], 'type': rd.get('type', ''), 'target': rd.get('target', '')})
        g['rows'].append(rd)

    out = []
    for name, g in groups.items():
        rows = sorted(g['rows'], key=lambda x: float(x.get('duration_days', 0)))
        xs = [float(r.get('duration_days', 0)) for r in rows]
        ys = [_metric_value(r, metric) for r in rows]

        slope_d, intercept, r2 = _linreg(xs, ys)
        mean_y = sum(ys) / len(ys) if ys else 0.0
        std_y = (sum((y - mean_y) ** 2 for y in ys) / len(ys)) ** 0.5 if ys else 0.0

        out.append({
            'shock_name': name,
            'type': g['type'],
            'target': g['target'],
            'metric': metric,
            'n_points': len(xs),
            'mean': mean_y,
            'min': min(ys) if ys else 0.0,
            'max': max(ys) if ys else 0.0,
            'std': std_y,
            'slope_per_day': slope_d,
            'slope_per_10d': slope_d * 10.0,
            'r2': r2,
        })
    # Classement par pente décroissante (les plus sensibles en tête)
    return sorted(out, key=lambda d: d['slope_per_day'], reverse=True)

def _export_summary_csv(path: str, summary_rows: List[Dict[str, Any]]):
    fieldnames = ['shock_name','type','target','metric','n_points','mean','min','max','std','slope_per_day','slope_per_10d','r2']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in summary_rows:
            w.writerow({k: r.get(k, '') for k in fieldnames})
    print(f"[OK] Export summary -> {path}")

def _print_summary(summary_rows: List[Dict[str, Any]], top: int = 10):
    print("\n=== Sensibilité vs durée (pente décroissante) ===")
    print("rank  shock                         metric                slope/10d    mean      R²")
    for i, r in enumerate(summary_rows[:top], 1):
        print(f"{i:<5}{str(r['shock_name'])[:28]:<30}{r['metric']:<20}"
              f"{r['slope_per_10d']:>11.3f}{r['mean']:>9.3f}{r['r2']:>8.2f}")
        

# --- Helpers de tracé (à coller dans compare_shocks.py, avant main()) ---
import matplotlib.pyplot as plt

def _is_daily_series(ts, base_config) -> bool:
    """True si la série est déjà agrégée par jour (longueur ≈ nombre de jours)."""
    if not isinstance(ts, (list, tuple)):
        return False
    H   = int(base_config.get("horizon", len(ts)))
    tud = max(1, int(base_config.get("time_units_per_day", 1)))
    expected_days = max(1, math.ceil(H / tud))
    # tolérance ±2 points
    return abs(len(ts) - expected_days) <= 2

def _x_for_ts(ts, base_config):
    """Axe X en JOURS, quel que soit l’échantillonnage en entrée."""
    tud = max(1, int(base_config.get("time_units_per_day", 1)))
    if _is_daily_series(ts, base_config):
        return list(range(len(ts)))           # 0..N-1 (déjà en jours)
    else:
        return [t / tud for t in range(len(ts))]  # conversion pas→jours

def plot_baseline_vs_shock(baseline_res, shock_res, start_days, duration_days,
                           base_config, metric="production",
                           title=None, out_path=None):
    """
    Trace baseline vs scénario de choc. start/duration sont en JOURS.
    metric: "production" (défaut) | "service" | "cost" (si tu en as).
    """
    # récupère les séries (utilise ton extracteur par défaut)
    if metric == "production":
        base_ts  = default_ts_extractor(baseline_res)
        shock_ts = default_ts_extractor(shock_res)
        ylab = "Production totale (u/jour)"
    else:
        # adapte ici si tu as d'autres séries temporelles
        base_ts  = default_ts_extractor(baseline_res)
        shock_ts = default_ts_extractor(shock_res)
        ylab = metric

    # construit l’axe X correctement en jours (pas de /8 en trop)
    x_base  = _x_for_ts(base_ts,  base_config)
    x_shock = _x_for_ts(shock_ts, base_config)

    plt.figure(figsize=(12, 5))
    label = shock_res.get("shock", shock_res.get("shock_name", "choc"))

    plt.plot(x_base,  base_ts,  "-o", label="baseline")
    plt.plot(x_shock, shock_ts, "-o", label=str(label))

    # fenêtre du choc : on travaille en JOURS ici
    t0 = float(start_days)
    t1 = float(start_days + duration_days)
    plt.axvspan(t0, t1, color="#3b82f6", alpha=0.12, label="fenêtre de choc")

    plt.xlabel("Temps (jours)")
    plt.ylabel(ylab)
    plt.title(title or "Baseline vs choc — production")
    plt.legend()
    plt.grid(True, alpha=0.3)

    if out_path:
        plt.savefig(out_path, bbox_inches="tight", dpi=140)
    else:
        plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():

    # AJOUTE juste avant l’appel :
    include = {
        "site_shutdown": True,
        "site_capacity_drop": True,
        "material_block": True,
        "material_capacity_drop": True,
        # tout le reste désactivé pour l’instant
        "route_blocked": False,
        "capacity_drop": False,
        "leadtime_spike": False,
        "mode_ban": False,
        "node_closed": False,
    }



    parser = argparse.ArgumentParser(description="Comparatif de chocs & métriques de résilience")
    parser.add_argument("--start", type=int, default=20, help="Instant de début des chocs (pas de temps)")
    parser.add_argument("--duration", type=int, default=10, help="Durée des chocs (pas de temps)")
    parser.add_argument("--recovery-th", type=float, default=0.95, help="Seuil de récupération (ex: 0.95)")
    parser.add_argument("--export-csv", type=str, default="", help="Chemin CSV d’export (facultatif)")
    parser.add_argument("--use-dummy", action="store_true", help="Utiliser la simu de démonstration (fallback)")
    parser.add_argument('--durations', type=int, nargs='+',
                    help='Liste de durées (en jours) à tester. Ex: --durations 5 10 20 40')
    parser.add_argument('--duration-range', type=str,
                    help='Plage "de:a:pas" en jours. Ex: --duration-range 5:40:5')
    parser.add_argument('--top-per-duration', type=int, default=10,
                    help='Nombre de lignes à afficher pour chaque durée (défaut: 10)')
    parser.add_argument('--export-csv-sweep', type=str,
                    help='Chemin CSV pour exporter toutes les lignes de toutes les durées (ex: sweep.csv)')
    parser.add_argument('--export-summary', type=str,
                    help='Chemin CSV pour le résumé agrégé (pentes vs durée)')
    parser.add_argument('--summary-metric', type=str, default='lost_area_rel',
        choices=['lost_area_rel','score','cost_delta_rel','amplitude_rel'],
                    help='Métrique analysée pour la pente vs durée')
    parser.add_argument('--summary-top', type=int, default=10,
                    help='Nb de lignes à afficher dans le résumé console')

    args = parser.parse_args()

    # Base config & état nominal
    base_config = build_base_config()
    state_for_suite = build_state_for_suite()

    # rendre l’état nominal disponible au dummy
    base_config["_suite_state"] = state_for_suite



    # Choix de la fonction de simulation
    sim = _dummy_sim_func if args.use_dummy else default_sim_func

    # Runner
    runner = ShockExperimentRunner(
        sim_func=sim,
        ts_extractor=default_ts_extractor,
        cost_extractor=default_cost_extractor,
        service_extractor=default_service_extractor,
        recovery_threshold=args.recovery_th,
    )

    # Exécution
    try:
        # MODIFIE l’appel run_suite :
        baseline_res, rows = runner.run_suite(
            base_config,
            state_for_suite,
            start_time=args.start,
            duration_days=args.duration,
            include=include,                 # <-- ici
        )
    except NotImplementedError as e:
        print("[ERREUR] default_sim_func n’est pas encore branché.")
        print("=> Implémente-le dans adapters.py OU lance ce script avec --use-dummy pour tester le pipeline.")
        sys.exit(2)

    # Tableau
    table = runner.to_table(rows)
    _print_table(table, top=20)

    # Export CSV éventuel
    if args.export_csv:
        _export_csv(args.export_csv, table)

    print("[Fini] Tu peux maintenant identifier les maillons les plus vulnérables et prioriser les leviers de résilience.")


    # === NOUVEAU: sweep de durées ===
    durations = []
    if args.durations:
        durations.extend(args.durations)
    if args.duration_range:
        durations.extend(_parse_duration_range(args.duration_range))
    durations = sorted(set(durations))

    if durations:
        all_rows = []
        for dur in durations:
            # Exécution de la suite pour cette durée
            try:
                baseline_res, rows = runner.run_suite(
                    base_config,
                    state_for_suite,
                    start_time=args.start,
                    duration_days=dur,
                    include=include,     # ← important pour filtrer les chocs
                )
            except TypeError:
                baseline_res, rows = runner.run_suite(
                    base_config,
                    state_for_suite,
                    start_time=args.start,
                    duration_days=dur,
                    include=include,
                )

            # IMPORTANT : on transforme en tableau de métriques agrégées
            table = runner.to_table(rows)

            print(f"\n=== Classement pour durée = {dur} jours ===")
            try:
                _print_table(table, top=args.top_per_duration)
            except Exception:
                _print_rows_simple(table, top=args.top_per_duration)

            # Ajoute la durée pour l’export consolidé
            for r in table:
                rr = _row_to_dict(r)  # normalise (objet/dataclass -> dict)
                rr["duration_days"] = dur
                # harmonisation des clés (sécurité si noms alternatifs)
                rr.setdefault("exogenous_severity", rr.get("exo_sev", 0.0))
                rr.setdefault("amplitude_rel", rr.get("ampl_rel", 0.0))
                rr.setdefault("lost_area_rel", rr.get("area_rel", 0.0))
                rr.setdefault("recovery_time", rr.get("recovery", 0))
                rr.setdefault("cost_delta_rel", rr.get("Δcost_rel", 0.0))
                all_rows.append(rr)

        # Export consolidé si demandé
        if args.export_csv_sweep:
            _export_csv_sweep(args.export_csv_sweep, all_rows)
        
          # === Résumé agrégé: pentes vs durée ===
        if args.export_summary:
            summary = _build_summary(all_rows, metric=args.summary_metric)
            _export_summary_csv(args.export_summary, summary)
            _print_summary(summary, top=args.summary_top)


        print("\n[Fini] Comparaison multi-durées terminée.")
        return


if __name__ == "__main__":
    main()
