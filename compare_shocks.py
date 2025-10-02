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
from copy import deepcopy
from pprint import pprint
import argparse
import csv
import sys

from shock_experiments import ShockExperimentRunner
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
        ("scenario_engine", "LINES_CONFIG"),
        ("scenario_engine", "lines_config"),
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
        "target_daily_output": 120.0,      # ← demande/jour (ajuste à ta réalité)
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
        from scenario_engine import get_nominal_state  # si tu as une fonction utilitaire
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

def _print_table(rows: List[Dict[str, Any]], top: int = 20):
    print("\n=== Classement des chocs (du plus critique au plus résilient) ===")
    header = ["rank","shock","type","target","exo_sev","ampl_rel","area_rel","area_rel_norm","recovery","Δcost_rel","score"]
    print("{:<4}  {:<28}  {:<18}  {:<28}  {:>7}  {:>8}  {:>8}  {:>13}  {:>8}  {:>9}  {:>6}".format(*header))
    for i, r in enumerate(rows[:top], start=1):
        name = r.get("shock", r.get("shock_name", ""))
        exo = float(r.get("exogenous_severity", 0.0))
        area_rel = float(r.get("lost_area_rel", 0.0))
        area_rel_norm = (area_rel / exo) if exo > 1e-9 else 0.0
        print("{:<4}  {:<28}  {:<18}  {:<28}  {:>7.3f}  {:>8.3f}  {:>8.3f}  {:>13.3f}  {:>8}  {:>9.3f}  {:>6.3f}".format(
            i,
            name[:28],
            r.get("type","")[:18],
            r.get("target","")[:28],
            exo,
            float(r.get("amplitude_rel", 0.0)),
            area_rel,
            area_rel_norm,
            r.get("recovery_time", "-") if r.get("recovery_time") is not None else "-",
            float(r.get("cost_delta_rel", 0.0)),
            float(r.get("score", 0.0)),
        ))
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

if __name__ == "__main__":
    main()
