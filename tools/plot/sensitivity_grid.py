# sensitivity_grid.py
# -*- coding: utf-8 -*-
import argparse, copy, math, csv
from typing import Any, Dict, List, Tuple
from types import SimpleNamespace
import matplotlib.pyplot as plt

from line_production.line_production import run_simulation  # type: ignore
from line_production.line_production_settings import lines_config  # type: ignore

HOURS_PER_DAY = 8

def clone_config_with_horizon(base_cfg: Any, horizon_days: int):
    cfg = copy.deepcopy(base_cfg)
    def _force(site_cfg: Dict[str, Any]):
        if not isinstance(site_cfg, dict): return
        hours = int(site_cfg.get("hours", HOURS_PER_DAY))
        site_cfg["total_time"] = horizon_days * hours
        site_cfg["n_days"] = horizon_days
    if isinstance(cfg, dict):
        for _, sc in cfg.items(): _force(sc)
    else:
        for sc in cfg: _force(sc)
    return cfg

def build_event(stype: str, target: str, start: int, duration: int, magnitude: float):
    if stype in ("site_shutdown", "site_capacity_drop"):
        ev_type = "panne"                  # interprété avec magnitude (1=shutdown)
    elif stype == "material_block":
        ev_type = "rupture_fournisseur"
    else:
        ev_type = "retard"
    return SimpleNamespace(
        event_type=ev_type,
        target=target,
        time=start * HOURS_PER_DAY,
        duration=duration * HOURS_PER_DAY,
        magnitude=float(magnitude),
        drain=(ev_type == "rupture_fournisseur"),
    )

def _diff_per_day_from_cumulative(times, cum, hours_per_day=1):
    if not times or not cum or len(times)!=len(cum): return []
    if max(times)<=0: return []
    n_days = int(math.ceil(max(times)/float(hours_per_day)))
    out, last = [], 0.0
    for d in range(1, n_days+1):
        end = d*hours_per_day
        idx = max(i for i,t in enumerate(times) if t<=end)
        val = float(cum[idx]); out.append(max(0.0, val-last)); last=val
    return out

def call_run(cfg, events_list=None, seed=42):
    res = run_simulation(cfg, events=events_list, seed=seed)
    prod = res[0] if isinstance(res, tuple) else res
    return prod

def extract_aggregate_daily(sim_result):
    # sim_result est une LISTE de blocs (un par site) avec 'Total Seats made': (times, cum)
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

def loss_for(cfg, stype, target, start, duration, horizon, magnitude, seed=42):
    cfg = clone_config_with_horizon(cfg, horizon)
    base = extract_aggregate_daily(call_run(cfg, None, seed))[:horizon]
    shock = extract_aggregate_daily(call_run(cfg, [build_event(stype, target, start, duration, magnitude)], seed))[:horizon]
    L = max(len(base), len(shock), horizon)
    base += [0.0]*(L-len(base)); shock += [0.0]*(L-len(shock))
    return sum(max(0.0, base[i]-shock[i]) for i in range(horizon))

def main():
    ap = argparse.ArgumentParser(description="Grille de sensibilité perte cumulée")
    ap.add_argument("--shock-type", required=True, choices=["site_shutdown","site_capacity_drop","material_block","retard"])
    ap.add_argument("--targets", required=True, help="cibles séparées par des virgules (France,UK,aluminium,...)")
    ap.add_argument("--horizon", type=int, required=True)
    ap.add_argument("--magnitudes", default="0.2,0.4,0.6,0.8,1.0")
    ap.add_argument("--starts", default="10,20,30")
    ap.add_argument("--durations", default="10,20,30")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--png-prefix", default="grid")
    ap.add_argument("--csv-prefix", default="grid")
    args = ap.parse_args()

    mags  = [float(x) for x in args.magnitudes.split(",")]
    starts= [int(x) for x in args.starts.split(",")]
    durs  = [int(x) for x in args.durations.split(",")]
    tgts  = [t.strip() for t in args.targets.split(",") if t.strip()]

    for tgt in tgts:
        # 1) CSV 3D : (magnitude, start, duration, loss)
        rows = []
        for m in mags:
            for s in starts:
                for d in durs:
                    loss = loss_for(lines_config, args.shock_type, tgt, s, d, args.horizon, m, args.seed)
                    rows.append((m,s,d,int(loss)))
        csv_path = f"{args.csv_prefix}_{args.shock_type}_{tgt}.csv".replace(" ", "_")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["magnitude","start","duration","loss"])
            w.writerows(rows)
        print(f"[OK] CSV: {csv_path}")

        # 2) Heatmaps 2D : (magnitude × duration) pour chaque 'start'
        for s in starts:
            Z = []
            for m in mags:
                row=[]
                for d in durs:
                    row.append(loss_for(lines_config, args.shock_type, tgt, s, d, args.horizon, m, args.seed))
                Z.append(row)

            fig = plt.figure(figsize=(6,4))
            ax = plt.gca()
            im = ax.imshow(Z, origin="lower", aspect="auto")
            ax.set_xticks(range(len(durs))); ax.set_xticklabels([str(x) for x in durs])
            ax.set_yticks(range(len(mags))); ax.set_yticklabels([str(x) for x in mags])
            ax.set_xlabel("durée (jours)"); ax.set_ylabel("magnitude")
            ax.set_title(f"Perte cumulée — {args.shock_type}::{tgt} (start={s}, horizon={args.horizon})")
            fig.colorbar(im, ax=ax, label="perte (u)")
            out = f"{args.png_prefix}_{args.shock_type}_{tgt}_start{s}.png".replace(" ", "_")
            plt.savefig(out, bbox_inches="tight", dpi=150)
            print(f"[OK] PNG: {out}")

if __name__ == "__main__":
    main()
