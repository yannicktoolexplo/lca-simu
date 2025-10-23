# sensitivity_curve.py
# -*- coding: utf-8 -*-
import argparse, copy, math
from typing import Any, Dict, List, Optional
from types import SimpleNamespace
import matplotlib.pyplot as plt

from line_production.line_production import run_simulation  # type: ignore
from line_production.line_production_settings import lines_config  # type: ignore

def clone_config_with_horizon(base_cfg: Dict[str, Any], horizon_days: int) -> Dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)
    def _force(site_cfg: Dict[str, Any]):
        if not isinstance(site_cfg, dict): return
        hours_per_day = int(site_cfg.get("hours", 8))
        site_cfg["total_time"] = int(horizon_days * hours_per_day)
        site_cfg["n_days"] = int(horizon_days)
    if isinstance(cfg, dict):
        for _, sc in cfg.items(): _force(sc)
    else:
        for sc in cfg: _force(sc)
    return cfg

def build_event(stype: str, target: str, start_day: int, duration_days: int, magnitude: float):
    HOURS_PER_DAY = 8
    if stype == "site_capacity_drop" or stype == "site_shutdown":
        ev_type = "panne"  # interprété avec magnitude (1=shutdown)
    elif stype == "material_block":
        ev_type = "rupture_fournisseur"
    else:
        ev_type = "retard"
    return SimpleNamespace(
        event_type=ev_type, target=target,
        time=start_day*HOURS_PER_DAY, duration=duration_days*HOURS_PER_DAY,
        magnitude=float(magnitude), drain=(ev_type=="rupture_fournisseur")
    )

def _diff_per_day_from_cumulative(times, cum, hours_per_day=1):
    if not times or not cum or len(times)!=len(cum): return []
    n_days = int(math.ceil(max(times)/float(hours_per_day))) if max(times)>0 else 0
    out, last = [], 0.0
    for d in range(1, n_days+1):
        end = d*hours_per_day
        idx = max(i for i,t in enumerate(times) if t<=end)
        val = float(cum[idx]); out.append(max(0.0, val-last)); last=val
    return out

def call_run(cfg, events_list=None):
    res = run_simulation(cfg, events=events_list)
    prod = res[0] if isinstance(res, tuple) else res
    return prod

def extract_aggregate_daily(sim_result):
    # sim_result = liste de blocs dict par site
    series, mlen = [], 0
    for blk in sim_result:
        val = blk.get("Total Seats made")
        if isinstance(val, (list, tuple)) and len(val)==2:
            arr = _diff_per_day_from_cumulative(list(val[0]), list(val[1]), 1)
            if arr:
                series.append(arr); mlen=max(mlen, len(arr))
    if not series: return []
    for i,a in enumerate(series):
        if len(a)<mlen: series[i] = a+[0.0]*(mlen-len(a))
    return [sum(v) for v in zip(*series)]

def loss_vs_magnitude(cfg, stype, target, start, duration, horizon, mags):
    cfg = clone_config_with_horizon(cfg, horizon)
    base = extract_aggregate_daily(call_run(cfg, None))[:horizon]
    out = []
    for m in mags:
        shock_res = extract_aggregate_daily(call_run(cfg, [build_event(stype, target, start, duration, m)]))[:horizon]
        L = max(len(base), len(shock_res), horizon)
        b = base + [0.0]*(L-len(base)); s = shock_res + [0.0]*(L-len(shock_res))
        loss = sum(max(0.0, b[i]-s[i]) for i in range(horizon))
        out.append((m, loss))
    return out

def main():
    ap = argparse.ArgumentParser(description="Courbe de sensibilité : perte vs magnitude")
    ap.add_argument("--shock-type", required=True, choices=["site_shutdown","site_capacity_drop","material_block","retard"])
    ap.add_argument("--target", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--horizon", type=int, required=True)
    ap.add_argument("--magnitudes", default="0.2,0.4,0.6,0.8,1.0")
    ap.add_argument("--save", default="sensitivity.png")
    args = ap.parse_args()

    mags = [float(x) for x in args.magnitudes.split(",")]
    pairs = loss_vs_magnitude(lines_config, args.shock_type, args.target, args.start, args.duration, args.horizon, mags)

    xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
    plt.figure(figsize=(7,4))
    plt.plot(xs, ys, marker="o")
    plt.title(f"Sensibilité — perte vs magnitude ({args.shock_type}::{args.target})")
    plt.xlabel("magnitude (0=aucun choc, 1=shutdown/blocage)"); plt.ylabel("perte cumulée (u)")
    plt.grid(True, alpha=0.3)
    plt.savefig(args.save, bbox_inches="tight", dpi=150)
    print(f"[OK] Figure sauvegardée: {args.save}")
    for m,l in pairs:
        print(f"m={m:.2f} -> perte={int(l)} u")

if __name__ == "__main__":
    main()
