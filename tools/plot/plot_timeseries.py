# plot_timeseries.py
# -*- coding: utf-8 -*-
"""
Comparaison baseline vs choc (shutdown site / rupture matière, etc.)
Exemple :
python plot_timeseries.py --shock-type site_shutdown --target PLANT_FR \
  --start 20 --duration 25 --horizon 60 --save ts_panne_FR.png
"""

import argparse
import copy
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from types import SimpleNamespace
import numpy as np


import matplotlib.pyplot as plt

# ---- Imports du projet (adapter si besoin) -----------------------------------
# run_simulation est dans line_production.line_production (confirmé)
from line_production.line_production import run_simulation  # type: ignore
# lines_config est dans line_production.line_production_settings (confirmé)
from line_production.line_production_settings import lines_config  # type: ignore


def _ordered_site_names(cfg_obj):
    """Retourne la liste des noms de sites dans l'ordre de lines_config."""
    names = []
    if isinstance(cfg_obj, dict):
        names = list(cfg_obj.keys())
    elif isinstance(cfg_obj, list):
        for sc in cfg_obj:
            if isinstance(sc, dict):
                # tes configs utilisent 'location' pour cibler les événements
                nm = sc.get("location") or sc.get("name") or sc.get("site") or sc.get("id")
                names.append(str(nm) if nm else None)
            else:
                names.append(None)
    return names

def _hours_per_site_from_cfg(cfg_obj, default=8):
    """Construit un dict {site_name: hours_per_day}. Par défaut 8h car tu divises env.now par 8."""
    res = {}
    names = _ordered_site_names(cfg_obj)
    if isinstance(cfg_obj, dict):
        for nm in names:
            sc = cfg_obj.get(nm, {})
            h = sc.get("hours")
            try:
                res[str(nm)] = int(h) if h is not None else default
            except Exception:
                res[str(nm)] = default
    elif isinstance(cfg_obj, list):
        for nm, sc in zip(names, cfg_obj):
            if not isinstance(sc, dict) or nm is None:
                continue
            h = sc.get("hours")
            try:
                res[str(nm)] = int(h) if h is not None else default
            except Exception:
                res[str(nm)] = default
    return res



def _site_name_from_block(block: dict) -> Optional[str]:
    # Essaie différentes clés courantes pour le nom du site
    for k in ("name", "site", "id", "site_name"):
        v = block.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def _normalize_sites_map(sim_result: Any, site_names: Optional[List[str]] = None) -> Dict[str, dict]:
    """
    Convertit dict/list/tuple -> dict {site_name: block}.
    Pour une LISTE (cas de ton moteur), on injecte les noms via lines_config (site_names).
    """
    # déballer un éventuel tuple
    if isinstance(sim_result, tuple):
        for part in sim_result:
            if isinstance(part, (dict, list)):
                sim_result = part
                break

    sites_map: Dict[str, dict] = {}

    # dict avec sous-bloc 'sites'
    if isinstance(sim_result, dict) and isinstance(sim_result.get("sites"), dict):
        for s, blk in sim_result["sites"].items():
            if isinstance(blk, dict):
                sites_map[str(s)] = blk
        if sites_map:
            return sites_map

    # dict plat {site: block}
    if isinstance(sim_result, dict):
        for s, blk in sim_result.items():
            if isinstance(blk, dict):
                sites_map[str(s)] = blk
        if sites_map:
            return sites_map

    # liste -> on utilise l'ordre et les noms fournis
    if isinstance(sim_result, list):
        n = len(sim_result)
        for i, blk in enumerate(sim_result):
            if not isinstance(blk, dict):
                continue
            nm = None
            if site_names and i < len(site_names):
                nm = site_names[i]
            if not nm:
                nm = f"site_{i+1}"
            sites_map[str(nm)] = blk
        return sites_map

    return {}


def _daily_from_cum(times, cum, hours_per_day: int) -> Optional[List[float]]:
    times = _as_num_list(times)
    cum = _as_num_list(cum)
    if not times or not cum or len(times) != len(cum):
        return None
    return _diff_per_day_from_cumulative(times, cum, hours_per_day)

def _daily_from_log(block: dict, hours_per_day: int) -> Optional[List[float]]:
    """
    Cherche un log d'événements avec champs ('time' ou 't') + ('qty'|'quantity'|'produced'|'units')
    et agrège par jour.
    """
    logs = _pick_first(block, LOG_KEYS)
    if not isinstance(logs, (list, tuple)) or not logs:
        return None
    per_day = {}
    max_day = 0
    for ev in logs:
        if not isinstance(ev, dict):
            continue
        t = ev.get("time", ev.get("t", ev.get("hour")))
        q = ev.get("qty", ev.get("quantity", ev.get("produced", ev.get("units"))))
        try:
            t = float(t)
            q = float(q)
        except Exception:
            continue
        day = int(t // hours_per_day) + 1
        per_day[day] = per_day.get(day, 0.0) + q
        if day > max_day:
            max_day = day
    if max_day == 0:
        return None
    return [per_day.get(d, 0.0) for d in range(1, max_day + 1)]

def _extract_daily_from_block(block: dict, hours_per_day: int) -> Optional[List[float]]:
    # 1) séries journalières directes
    daily = _pick_first(block, DAILY_KEYS)
    daily = _as_num_list(daily)
    if daily:
        return daily

    # 2) cumul + temps
    times = _pick_first(block, TIME_KEYS)
    cum   = _pick_first(block, CUM_KEYS)
    daily = _daily_from_cum(times, cum, hours_per_day)
    if daily:
        return daily

    # 3) logs d'événements
    daily = _daily_from_log(block, hours_per_day)
    if daily:
        return daily

    return None

NUM_LIKE = (int, float)

# clés candidates
TIME_KEYS = ("times", "time", "t", "hours", "timestamps")
CUM_KEYS  = ("Total Seats made", "total_seats_made", "production_cumulative",
             "cumulative_production", "cum", "total", "cum_production")
DAILY_KEYS = ("daily", "daily_production", "production_daily", "prod_day",
              "output_per_day", "q_per_day", "units_per_day")
LOG_KEYS = ("log", "logs", "events", "history", "trace")

SITE_NAME_KEYS = ("name", "site", "id", "site_name", "plant")


def _site_name_from_block(block: dict) -> Optional[str]:
    for k in SITE_NAME_KEYS:
        v = block.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _as_num_list(x):
    if isinstance(x, (list, tuple)):
        out = []
        for v in x:
            try:
                out.append(float(v))
            except Exception:
                return None
        return out
    return None


def _pick_first(block: dict, keys: tuple) -> Optional[Any]:
    for k in keys:
        if k in block:
            return block[k]
    return None

# ------------------------------------------------------------------------------
# Utilitaires : cibles, événements, horizon
# ------------------------------------------------------------------------------

SITE_ALIASES = {
    # normalisations usuelles -> nom du site dans ta config
    "PLANT_FR": "France",
    "PLANT_UK": "UK",
    "PLANT_TX": "Texas",
    "PLANT_CA": "California",
    # variantes courantes
    "FR": "France",
    "UK": "UK",
    "TX": "Texas",
    "CA": "California",
    "USA_TX": "Texas",
    "USA_CA": "California",
}

MATERIAL_ALIASES = {
    # à compléter selon tes ressources si besoin
    "ALU": "aluminium",
    "ALUMINIUM": "aluminium",
    "FOAM": "foam",
    "TISSU": "fabric",
}


def normalize_target(raw: str) -> str:
    t = raw.strip()
    return SITE_ALIASES.get(t, MATERIAL_ALIASES.get(t.upper(), t))


def guess_target_type(target: str, config: Dict[str, Any]) -> str:
    """Devine si la cible correspond à un site ('site') ou une ressource ('resource')."""
    t = normalize_target(target)
    site_names = set()

    # config peut être un dict {name: cfg} OU une liste [cfg, cfg, ...]
    if isinstance(lines_config, dict):
        site_names = set(lines_config.keys())
    elif isinstance(lines_config, list):
        for sc in lines_config:
            if isinstance(sc, dict):
                name = sc.get("name") or sc.get("site") or sc.get("id")
                if name:
                    site_names.add(str(name))

    if t in site_names:
        return "site"
    return "resource"



def build_event(
    shock_type: str,
    target: str,
    start_day: int,
    duration_days: int,
    magnitude: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Construit un événement COMPATIBLE avec run_simulation:
      - event_type: 'panne' | 'rupture_fournisseur' | 'retard'
      - target: nom du site (ex: 'France') OU nom de matière (ex: 'aluminium')
      - time, duration: en HEURES (pas en jours)
    """
    HOURS_PER_DAY = 8  # cohérent avec get_data() qui fait env.now/8

    t_norm = normalize_target(target)
    st = shock_type.strip().lower()

    if st == "site_shutdown":
        event_type = "panne"
    elif st == "site_capacity_drop":
        # pas de baisse partielle native → fallback sur 'panne' (arrêt total)
        event_type = "panne"
    elif st == "material_block":
        event_type = "rupture_fournisseur"
    elif st == "material_capacity_drop":
        event_type = "retard"
    else:
        event_type = "retard"

    # time/duration attendus en heures dans les handlers
    time_h = int(start_day) * HOURS_PER_DAY
    duration_h = int(duration_days) * HOURS_PER_DAY

    # Option 'drain' utile pour rupture_fournisseur (purge du stock)
    drain = True if event_type == "rupture_fournisseur" else False

    return SimpleNamespace(
        event_type=event_type,
        target=t_norm,
        time=time_h,
        duration=duration_h,
        magnitude=float(magnitude) if magnitude is not None else None,
        drain=drain,
    )



def clone_config_with_horizon(
    base_cfg: Dict[str, Any],
    horizon_days: int,
) -> Dict[str, Any]:
    """
    Copie profonde de la config, en imposant un horizon en jours :
    - si config est un dict : on parcourt les valeurs
    - si config est une liste : on parcourt les éléments
    et on ajuste 'total_time' = days * hours (si possible).
    """
    cfg = copy.deepcopy(base_cfg)

    def _force(site_cfg: Dict[str, Any]):
        if not isinstance(site_cfg, dict):
            return
        hours_per_day = site_cfg.get("hours", 24)
        try:
            hours_per_day = int(hours_per_day)
        except Exception:
            hours_per_day = 24
        site_cfg["total_time"] = int(horizon_days * hours_per_day)
        site_cfg["n_days"] = int(horizon_days)

    if isinstance(cfg, dict):
        for _, site_cfg in cfg.items():
            _force(site_cfg)
    elif isinstance(cfg, list):
        for site_cfg in cfg:
            _force(site_cfg)

    return cfg


# ------------------------------------------------------------------------------
# Lancement simulation robuste (essaie plusieurs signatures)
# ------------------------------------------------------------------------------

def call_run_simulation_positional(
    cfg: Dict[str, Any],
    events_list: Optional[List[Any]] = None,
) -> Any:
    """
    Passe la config en 1er argument et les événements via le kwarg 'events'.
    Déballe (production, enviro) → production.
    """
    result = run_simulation(cfg, events=events_list)
    if isinstance(result, tuple) and len(result) >= 1:
        return result[0]  # on garde la partie "production"
    return result




# ------------------------------------------------------------------------------
# Extraction de séries : production journalière baseline et choc
# ------------------------------------------------------------------------------

def _diff_per_day_from_cumulative(
    times: List[float], cum: List[float], hours_per_day: int
) -> List[float]:
    """
    Convertit une série cumulée (par ex. 'Total Seats made') indexée en heures
    en production par jour (différence jour par jour).
    """
    if not times or not cum or len(times) != len(cum):
        return []

    # position des "fins de jour" en heures : hours_per_day, 2*hours_per_day, ...
    max_hour = max(times)
    if max_hour <= 0:
        return []

    n_days = int(math.ceil(max_hour / float(hours_per_day)))
    res = []
    last_val = 0.0

    for d in range(1, n_days + 1):
        end_h = d * hours_per_day
        # trouver l'index dans times <= end_h le plus proche
        idx = max(i for i, t in enumerate(times) if t <= end_h)
        val = float(cum[idx])
        res.append(max(0.0, val - last_val))
        last_val = val
    return res


def _unwrap_result(sim_result: Any) -> Any:
    """
    Si run_simulation renvoie un tuple (env, data) ou (data, logs), retourne la partie 'data'.
    Sinon, retourne sim_result inchangé.
    """
    if isinstance(sim_result, tuple):
        # heuristique : on prend le 1er dict rencontré
        for part in sim_result:
            if isinstance(part, dict):
                return part
        # à défaut, 2e élément
        if len(sim_result) >= 2:
            return sim_result[1]
    return sim_result




def _extract_site_daily_production_from_block(block: dict, hours_per_day: int) -> Optional[List[float]]:
    """
    Ton format renvoie 'Total Seats made': (times, series).
    On convertit ce cumul (en jours déjà, car tu stockes env.now/8) en production/jour via diff.
    """
    # cas natif (tuple)
    val = block.get("Total Seats made") or block.get("total_seats_made")
    if isinstance(val, (list, tuple)) and len(val) == 2:
        times, cum = val[0], val[1]
        # ici, 'times' est déjà en JOURS (tu fais env.now/8 dans get_data)
        if isinstance(times, (list, tuple)) and isinstance(cum, (list, tuple)):
            # times est en jours => on peut regrouper par jour entier directement
            # mais pour rester générique on réutilise le diff avec hours_per_day=1
            return _diff_per_day_from_cumulative(list(times), list(cum), hours_per_day=1)

    # compat : si jamais quelqu'un met un dict "_ts" futur
    tsb = block.get("_ts")
    if isinstance(tsb, dict):
        t2 = tsb.get("times")
        c2 = tsb.get("Total Seats made")
        if isinstance(t2, (list, tuple)) and isinstance(c2, (list, tuple)):
            return _diff_per_day_from_cumulative(list(t2), list(c2), hours_per_day=1)

    # autres formats non rencontrés ici
    return None



def _aggregate_daily_across_sites(
    sim_result: Any,
    site_hours: Dict[str, int],
    site_names: Optional[List[str]] = None
) -> Optional[List[float]]:
    """
    Agrège la production journalière sur tous les sites disponibles.
    Supporte les résultats sous forme de liste en utilisant l'ordre/noms de lines_config (site_names).
    """
    sites_map = _normalize_sites_map(sim_result, site_names)
    if not sites_map:
        return None

    series = []
    max_len = 0
    for site, blk in sites_map.items():
        # tes times sont déjà en jours => hours_per_day=1 pour le diff cumul -> journalier
        daily = _extract_site_daily_production_from_block(blk, hours_per_day=1)
        if daily:
            series.append(daily)
            max_len = max(max_len, len(daily))

    if not series:
        return None

    # padding
    for i, arr in enumerate(series):
        if len(arr) < max_len:
            series[i] = arr + [0.0] * (max_len - len(arr))

    return [sum(vals) for vals in zip(*series)]




# ------------------------------------------------------------------------------
# Plot
# ------------------------------------------------------------------------------
def moving_average(arr: List[float], win: int) -> List[float]:
    if not arr or win <= 1:
        return arr
    out, s = [], 0.0
    q = []
    for x in arr:
        q.append(x); s += x
        if len(q) > win:
            s -= q.pop(0)
        out.append(s / len(q))
    return out

def compute_kpis(base: List[float], shock: List[float], threshold: float = None):
    """
    Retourne dict: loss, max_gap, days_below (nbr de jours shock<threshold),
    ttr (1er jour où shock >= 95% baseline ET reste au-dessus ensuite).
    """
    n = min(len(base), len(shock))
    if n == 0:
        return {"loss": 0.0, "max_gap": 0.0, "days_below": 0, "ttr": None}

    diff = [max(0.0, base[i] - shock[i]) for i in range(n)]
    loss = float(sum(diff))
    max_gap = float(max(diff)) if diff else 0.0

    # days_below: si pas de threshold fourni, on prend 50% du médian baseline
    if threshold is None:
        b_sorted = sorted(base[:n])
        med = b_sorted[n//2] if n else 0.0
        threshold = 0.5 * med
    days_below = sum(1 for i in range(n) if shock[i] < threshold)

    # TTR: time to recover (jour où shock >= 0.95*baseline et le reste)
    ttr = None
    for i in range(n):
        if base[i] <= 0:
            continue
        if shock[i] >= 0.95 * base[i]:
            # vérifie qu'on reste proche ensuite (fenêtre prudente de 5 jours)
            ok = True
            for j in range(i, min(n, i+5)):
                if base[j] > 0 and shock[j] < 0.9 * base[j]:
                    ok = False; break
            if ok:
                ttr = i + 1  # index->jour
                break

    return {"loss": loss, "max_gap": max_gap, "days_below": int(days_below), "ttr": ttr}




def plot_baseline_vs_shock(
    daily_base: List[float],
    daily_shock: List[float],
    start: int,
    duration: int,
    title: str,
    save_path: Optional[str] = None,
    kpi_box: Optional[Dict[str, float]] = None,
):
    days = list(range(1, max(len(daily_base), len(daily_shock)) + 1))

    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    ax.plot(days[: len(daily_base)], daily_base, marker="o", label="baseline")
    ax.plot(days[: len(daily_shock)], daily_shock, marker="o", label=title)

    if duration > 0:
        ax.axvspan(start, start + duration, alpha=0.15, hatch="///", label="fenêtre de choc")

    ax.set_title("Baseline vs choc — production")
    ax.set_xlabel("Temps (jours)")
    ax.set_ylabel("Production totale (u/jour)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Encadré KPI
    if kpi_box:
        txt = (f"Perte: {int(kpi_box['loss'])} u\n"
               f"Creux max: {int(kpi_box['max_gap'])} u/j\n"
               f"Jours < seuil: {kpi_box['days_below']}\n"
               f"TTR: {kpi_box['ttr'] if kpi_box['ttr'] is not None else '—'} j")
        ax.text(0.02, 0.98, txt, transform=ax.transAxes, va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.8))

    if save_path:
        plt.savefig(save_path, bbox_inches="tight", dpi=150)
        print(f"[OK] Figure sauvegardée : {save_path}")
    else:
        plt.show()



# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def _iter_site_cfgs(cfg_obj):
    """Itère sur les dictionnaires de site, que la config soit un dict ou une liste."""
    if isinstance(cfg_obj, dict):
        for _, scfg in cfg_obj.items():
            if isinstance(scfg, dict):
                yield scfg
    elif isinstance(cfg_obj, list):
        for scfg in cfg_obj:
            if isinstance(scfg, dict):
                yield scfg


def cap_from_baseline(series: List[float], mode: str = "max") -> float:
    arr = np.array(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return 0.0
    if mode == "p95":
        return float(np.percentile(arr, 95))
    return float(np.max(arr))

def clip_to_cap(series: List[float], cap: float) -> List[float]:
    if cap <= 0:
        return series
    return [min(float(x), cap) for x in series]



def main():
    p = argparse.ArgumentParser(description="Comparer baseline vs choc (production/jour)")
    p.add_argument("--shock-type", required=True, help="site_shutdown, site_capacity_drop, material_block, ...")
    p.add_argument("--target", required=True, help="ex: PLANT_FR, France, aluminium, ...")
    p.add_argument("--start", type=int, required=True, help="début du choc (en jours, entier)")
    p.add_argument("--duration", type=int, required=True, help="durée du choc (en jours, entier)")
    p.add_argument("--horizon", type=int, required=True, help="horizon de simulation (en jours)")
    p.add_argument("--magnitude", type=float, default=None, help="intensité (optionnel, ex: 0.5)")
    p.add_argument("--save", default=None, help="chemin du PNG de sortie")
    p.add_argument("--kpi-threshold", type=float, default=None, help="seuil u/j pour 'jours sous seuil' (défaut=50% médian baseline)")
    p.add_argument("--ma", type=int, default=0, help="fenêtre de moyenne glissante appliquée aux courbes (0=aucun)")
    p.add_argument("--csv", default=None, help="chemin CSV pour exporter baseline/shock/diff (optionnel)")
    p.add_argument("--cap-mode", choices=["max", "p95"], default="max",
               help="Comment estimer la capacité depuis la baseline: max ou p95 (défaut: max)")
    p.add_argument("--cap-mult", type=float, default=1.0,
                help="Facteur d'overdrive autorisé par rapport à la capacité (ex: 1.1 = +10%)")
    p.add_argument("--enforce-cap", action="store_true",
                help="Si présent, on bride la courbe choc à la capacité estimée")


    
    args = p.parse_args()

    # 1) Construire l'événement et horizon
    event = build_event(
        shock_type=args.shock_type,
        target=args.target,
        start_day=args.start,
        duration_days=args.duration,
        magnitude=args.magnitude,
        config=lines_config,
    )
    horizon = max(int(args.horizon), int(args.start) + int(args.duration))

    # 2) Cloner et forcer l’horizon (supporte dict OU liste)
    cfg_base = clone_config_with_horizon(lines_config, horizon_days=horizon)
    cfg_shock = clone_config_with_horizon(lines_config, horizon_days=horizon)



    # 5) Sanity checks
    def _count_sites(cfg_obj):
        return sum(1 for _ in _iter_site_cfgs(cfg_obj))
    if _count_sites(cfg_base) == 0 or _count_sites(cfg_shock) == 0:
        raise RuntimeError("Configuration des sites vide après clonage. Vérifie lines_config et clone_config_with_horizon.")

    # 6) Lancer baseline PUIS choc (baseline sans event, choc avec event)
    print("[Sim] baseline…")
    res_base = call_run_simulation_positional(cfg_base, events_list=None)

    print("[Sim] choc…")
    res_shock = call_run_simulation_positional(cfg_shock, events_list=[event])

    # 7) Noms/sites & heures
    site_names = _ordered_site_names(cfg_base)              # ex: ['France','Texas','UK','California']
    site_hours = _hours_per_site_from_cfg(cfg_base, 8)      # 8 par défaut (times déjà en 'jours')

    # 8) Normaliser → {site_name: block}
    sites_base = _normalize_sites_map(res_base, site_names)
    sites_shock = _normalize_sites_map(res_shock, site_names)

    # 9) Choisir la série à tracer (site cible pour site_*, sinon agrégé)
    shock_is_site = args.shock_type.lower().startswith("site_")
    target_norm = normalize_target(args.target)

    if shock_is_site and target_norm in sites_base:
        base_daily = _extract_site_daily_production_from_block(sites_base[target_norm], hours_per_day=1)
        shock_daily = _extract_site_daily_production_from_block(sites_shock.get(target_norm, {}), hours_per_day=1)
        if not base_daily or not shock_daily:
            base_daily = _aggregate_daily_across_sites(res_base, site_hours, site_names)
            shock_daily = _aggregate_daily_across_sites(res_shock, site_hours, site_names)
            title = f"{args.shock_type}::{args.target} (agrégé)"
        else:
            title = f"{args.shock_type}::{args.target}"
    else:
        base_daily = _aggregate_daily_across_sites(res_base, site_hours, site_names)
        shock_daily = _aggregate_daily_across_sites(res_shock, site_hours, site_names)
        title = f"{args.shock_type}::{args.target}"


    # === CAPACITÉ NOMINALE DEPUIS BASELINE ===
    # Cap = (max ou p95) des u/j de la baseline, multiplié par cap_mult
    nominal_cap = cap_from_baseline(base_daily[:horizon], mode=args.cap_mode) * float(args.cap_mult)

    print(f"[INFO] Capacité nominale estimée ({args.cap_mode} * {args.cap_mult:.2f}) : {nominal_cap:.2f} u/j")

    # (option) calcul “mensuel” indicatif si tu utilises des jours ouvrés fixes (ex: 20)
    working_days = 20
    print(f"[INFO] Capacité mensuelle indicative ≈ {nominal_cap*working_days:.0f} u / {working_days} j ouvrés")

    # ENFORCE: brider la courbe choc si demandé
    if args.enforce_cap and nominal_cap > 0:
        shock_daily = clip_to_cap(shock_daily, nominal_cap)
        print("[INFO] enforce-cap: courbe choc bridée à la capacité nominale")


    # 10) Garde-fous + debug utile
    if not base_daily or not shock_daily:
        print("[DBG] sites_base keys:", list(sites_base.keys()))
        print("[DBG] sites_shock keys:", list(sites_shock.keys()))
        if shock_is_site:
            print("[DBG] target_norm:", target_norm)
        raise RuntimeError(
            "Impossible d'extraire des séries journalières (baseline ou choc). "
            "Vérifie que chaque bloc site contient 'Total Seats made': (times, cumul)."
        )

    # 11) Harmoniser longueurs et tracer
    L = max(len(base_daily), len(shock_daily), horizon)
    if len(base_daily) < L:
        base_daily += [0.0] * (L - len(base_daily))
    if len(shock_daily) < L:
        shock_daily += [0.0] * (L - len(shock_daily))


        # Lissage si demandé
    if args.ma and args.ma > 1:
        base_daily = moving_average(base_daily, args.ma)
        shock_daily = moving_average(shock_daily, args.ma)

    # KPIs
    kpis = compute_kpis(base_daily[:horizon], shock_daily[:horizon], threshold=args.kpi_threshold)

    # Export CSV si demandé
    if args.csv:
        import csv
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["day", "baseline", "shock", "diff"])
            for d in range(1, horizon+1):
                b = base_daily[d-1] if d-1 < len(base_daily) else 0.0
                s = shock_daily[d-1] if d-1 < len(shock_daily) else 0.0
                w.writerow([d, b, s, max(0.0, b-s)])
        print(f"[OK] CSV exporté: {args.csv}")
    

    plot_baseline_vs_shock(
            daily_base=base_daily[:horizon],
            daily_shock=shock_daily[:horizon],
            start=int(args.start),
            duration=int(args.duration),
            title=title,
            save_path=args.save,
            kpi_box=kpis,
        )





if __name__ == "__main__":
    main()
