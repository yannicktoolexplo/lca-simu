# top_shocks.py
# -*- coding: utf-8 -*-

import argparse
import copy
import math
from typing import Any, Dict, List, Optional, Tuple
from types import SimpleNamespace

import matplotlib.pyplot as plt

from line_production.line_production import run_simulation  # type: ignore
from line_production.line_production_settings import lines_config  # type: ignore

# ---------- Aliases & helpers config ----------
SITE_ALIASES = {
    "PLANT_FR": "France", "PLANT_UK": "UK", "PLANT_TX": "Texas", "PLANT_CA": "California",
    "FR": "France", "UK": "UK", "TX": "Texas", "CA": "California"
}
MATERIALS = ["aluminium", "foam", "fabric", "paint"]

def _ordered_site_names(cfg_obj):
    names = []
    if isinstance(cfg_obj, dict):
        names = list(cfg_obj.keys())
    elif isinstance(cfg_obj, list):
        for sc in cfg_obj:
            if isinstance(sc, dict):
                nm = sc.get("location") or sc.get("name") or sc.get("site") or sc.get("id")
                names.append(str(nm) if nm else None)
            else:
                names.append(None)
    return [n for n in names if n]

def clone_config_with_horizon(base_cfg: Dict[str, Any], horizon_days: int) -> Dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    def _force(site_cfg: Dict[str, Any]):
        if not isinstance(site_cfg, dict): return
        hours_per_day = int(site_cfg.get("hours", 8))
        site_cfg["total_time"] = int(horizon_days * hours_per_day)
        site_cfg["n_days"] = int(horizon_days)
    if isinstance(cfg, dict):
        for _, site_cfg in cfg.items(): _force(site_cfg)
    elif isinstance(cfg, list):
        for site_cfg in cfg: _force(site_cfg)
    return cfg

def build_event(shock_type: str, target: str, start_day: int, duration_days: int) -> Any:
    HOURS_PER_DAY = 8  # car get_data() utilise env.now/8 => times déjà en jours
    st = shock_type.strip().lower()
    if st == "site_shutdown":
        event_type = "panne"
    elif st == "material_block":
        event_type = "rupture_fournisseur"
    else:
        event_type = "retard"
    time_h = int(start_day) * HOURS_PER_DAY
    duration_h = int(duration_days) * HOURS_PER_DAY
    drain = True if event_type == "rupture_fournisseur" else False
    return SimpleNamespace(event_type=event_type, target=target, time=time_h, duration=duration_h, drain=drain)

def call_run(cfg: Dict[str, Any], events_list: Optional[List[Any]] = None) -> Any:
    res = run_simulation(cfg, events=events_list)
    # run_simulation retourne (production, enviro)
    return res[0] if isinstance(res, tuple) and len(res)>=1 else res

# ---------- Extraction séries ----------
def _diff_per_day_from_cumulative(times: List[float], cum: List[float], hours_per_day: int) -> List[float]:
    if not times or not cum or len(times)!=len(cum): return []
    max_t = max(times)
    if max_t <= 0: return []
    n_days = int(math.ceil(max_t / float(hours_per_day)))
    res, last = [], 0.0
    for d in range(1, n_days+1):
        end = d * hours_per_day
        idx = max(i for i,t in enumerate(times) if t <= end)
        val = float(cum[idx])
        res.append(max(0.0, val - last))
        last = val
    return res

def _normalize_sites_map(sim_result: Any, site_names: Optional[List[str]] = None) -> Dict[str, dict]:
    if isinstance(sim_result, tuple):
        for part in sim_result:
            if isinstance(part, (dict, list)): sim_result = part; break
    sites_map = {}
    if isinstance(sim_result, dict) and isinstance(sim_result.get("sites"), dict):
        for s, blk in sim_result["sites"].items():
            if isinstance(blk, dict): sites_map[str(s)] = blk
        return sites_map
    if isinstance(sim_result, dict):
        for s, blk in sim_result.items():
            if isinstance(blk, dict): sites_map[str(s)] = blk
        if sites_map: return sites_map
    if isinstance(sim_result, list):
        for i, blk in enumerate(sim_result):
            if not isinstance(blk, dict): continue
            nm = site_names[i] if (site_names and i < len(site_names)) else f"site_{i+1}"
            sites_map[str(nm)] = blk
        return sites_map
    return {}

def _site_daily_from_block(block: dict) -> List[float]:
    # Ton format: "Total Seats made": (times_en_jours, cumul)
    val = block.get("Total Seats made") or block.get("total_seats_made")
    if isinstance(val, (list, tuple)) and len(val)==2:
        times, cum = list(val[0]), list(val[1])
        # times sont déjà en jours -> hours_per_day = 1 pour diff
        return _diff_per_day_from_cumulative(times, cum, hours_per_day=1)
    # compat: sous-bloc _ts éventuel
    tsb = block.get("_ts")
    if isinstance(tsb, dict):
        t2 = tsb.get("times"); c2 = tsb.get("Total Seats made")
        if isinstance(t2, (list,tuple)) and isinstance(c2, (list,tuple)):
            return _diff_per_day_from_cumulative(list(t2), list(c2), hours_per_day=1)
    return []

def _aggregate_daily(sim_result: Any, site_names: List[str]) -> List[float]:
    mp = _normalize_sites_map(sim_result, site_names)
    series, mlen = [], 0
    for _, blk in mp.items():
        arr = _site_daily_from_block(blk)
        if arr:
            series.append(arr)
            mlen = max(mlen, len(arr))
    if not series: return []
    for i, a in enumerate(series):
        if len(a) < mlen: series[i] = a + [0.0]*(mlen-len(a))
    return [sum(vals) for vals in zip(*series)]

# ---------- Impact & Ranking ----------
def _impact_loss(baseline: List[float], shock: List[float], horizon: int) -> float:
    L = min(horizon, len(baseline), len(shock))
    return float(sum(max(0.0, baseline[i]-shock[i]) for i in range(L)))

def evaluate_shock(cfg_base, cfg_shock, site_names, shock_type, target, start, duration, horizon, mode="auto"):
    event = build_event(shock_type, target, start, duration)
    # baseline
    base_res = call_run(cfg_base, events_list=None)
    # choc
    shock_res = call_run(cfg_shock, events_list=[event])

    if mode == "site":
        # série du site ciblé
        base_site = _normalize_sites_map(base_res, site_names).get(target, {})
        shock_site = _normalize_sites_map(shock_res, site_names).get(target, {})
        base_daily = _site_daily_from_block(base_site)
        shock_daily = _site_daily_from_block(shock_site)
        if not base_daily or not shock_daily:
            # fallback agrégé
            base_daily = _aggregate_daily(base_res, site_names)
            shock_daily = _aggregate_daily(shock_res, site_names)
    else:
        # agrégé multi-sites (utile pour chocs matière)
        base_daily = _aggregate_daily(base_res, site_names)
        shock_daily = _aggregate_daily(shock_res, site_names)

    # pad pour comparabilité
    L = max(horizon, len(base_daily), len(shock_daily))
    if len(base_daily) < L: base_daily += [0.0]*(L-len(base_daily))
    if len(shock_daily) < L: shock_daily += [0.0]*(L-len(shock_daily))
    loss = _impact_loss(base_daily, shock_daily, horizon)
    return {"shock_type": shock_type, "target": target, "start": start, "duration": duration,
            "loss": loss, "base_daily": base_daily[:horizon], "shock_daily": shock_daily[:horizon]}

def plot_top_k(ranked: List[dict], k: int, start: int, duration: int, save: Optional[str]):
    k = min(k, len(ranked))
    rows, cols = 2, 5
    plt.figure(figsize=(18, 9))
    for i in range(k):
        r = ranked[i]
        ax = plt.subplot(rows, cols, i+1)
        days = list(range(1, len(r["base_daily"])+1))
        ax.plot(days, r["base_daily"], marker="o", label="baseline")
        ax.plot(days, r["shock_daily"], marker="o", label=f'{r["shock_type"]}::{r["target"]}')
        if duration > 0:
            ax.axvspan(start, start+duration, alpha=0.12, hatch="///", label="fenêtre de choc")
        ax.set_title(f'{i+1}. {r["shock_type"]}::{r["target"]}  (perte={int(r["loss"])} u)')
        ax.set_xlabel("jours"); ax.set_ylabel("u/jour")
        ax.grid(True, alpha=0.3)
        if i == 0: ax.legend(loc="upper left")
    plt.suptitle("Top chocs — comparaison baseline vs choc (perte cumulée)", fontsize=16, y=0.98)
    plt.tight_layout(rect=[0,0,1,0.96])
    if save:
        plt.savefig(save, bbox_inches="tight", dpi=150)
        print(f"[OK] Figure sauvegardée: {save}")
    else:
        plt.show()

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Top-K des chocs (baseline vs choc)")
    ap.add_argument("--start", type=int, required=True, help="début choc (jours)")
    ap.add_argument("--duration", type=int, required=True, help="durée choc (jours)")
    ap.add_argument("--horizon", type=int, required=True, help="horizon simulé (jours)")
    ap.add_argument("--k", type=int, default=10, help="nombre de chocs à afficher")
    ap.add_argument("--save", default="top_shocks.png", help="fichier PNG de sortie (grille)")
    args = ap.parse_args()

    horizon = max(args.horizon, args.start + args.duration)
    # configs clonées avec horizon forcé
    cfg_base = clone_config_with_horizon(lines_config, horizon_days=horizon)
    cfg_shock = clone_config_with_horizon(lines_config, horizon_days=horizon)

    # candidats: shutdown de chaque site + rupture de chaque matière
    site_names = _ordered_site_names(cfg_base)
    candidates: List[Tuple[str, str, str]] = []
    for s in site_names:
        candidates.append(("site_shutdown", s, "site"))
    for m in MATERIALS:
        candidates.append(("material_block", m, "agg"))

    print(f"[Info] Candidats à évaluer: {len(candidates)} ({len(site_names)} sites + {len(MATERIALS)} matières)")

    results = []
    for stype, target, mode in candidates:
        try:
            r = evaluate_shock(cfg_base, cfg_shock, site_names, stype, target, args.start, args.duration, horizon,
                               mode=("site" if mode=="site" else "agg"))
            results.append(r)
            print(f"[OK] {stype}::{target}  perte={int(r['loss'])} u")
        except Exception as e:
            print(f"[WARN] échec {stype}::{target}: {e}")

    # tri par impact décroissant et top-k
    ranked = sorted(results, key=lambda x: x["loss"], reverse=True)
    topk = ranked[:args.k]
    print("\n=== TOP CHOCS (perte d’unités) ===")
    for i, r in enumerate(topk, 1):
        print(f"{i:2d}. {r['shock_type']}::{r['target']:>10s}  perte={int(r['loss'])} u")

    # grille
    plot_top_k(topk, args.k, args.start, args.duration, args.save)

if __name__ == "__main__":
    main()
