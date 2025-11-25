# montecarlo_sensitivity.py
# -*- coding: utf-8 -*-
import argparse, random, csv, copy, math
import matplotlib.pyplot as plt
from types import SimpleNamespace
from typing import Any, Dict, List

from line_production.line_production_settings import lines_config  # type: ignore
from line_production.line_production import run_simulation         # type: ignore

HOURS_PER_DAY = 8  # ton moteur logge env.now/8 => 1 "jour" = 8h

# --- Helpers repris de plot_timeseries (versions compactes) -------------------
def clone_config_with_horizon(base_cfg: Any, horizon_days: int):
    cfg = copy.deepcopy(base_cfg)
    def _force(sc):
        if not isinstance(sc, dict): return
        hours = int(sc.get("hours", HOURS_PER_DAY))
        sc["total_time"] = horizon_days * hours
        sc["n_days"] = horizon_days
    if isinstance(cfg, dict):
        for _, sc in cfg.items(): _force(sc)
    else:
        for sc in cfg: _force(sc)
    return cfg

def build_event(stype: str, target: str, start: int, duration: int, magnitude: float):
    # Map identique à plot_timeseries
    if stype == "site_shutdown":
        ev_type, mag = "panne", 1.0
    elif stype == "site_capacity_drop":
        ev_type, mag = "panne", float(magnitude)
    elif stype == "material_block":
        ev_type, mag = "rupture_fournisseur", float(magnitude)  # <== magnitude utilisée
    else:
        ev_type, mag = "retard", float(magnitude)
    return SimpleNamespace(
        event_type=ev_type,
        target=target,
        time=int(start * HOURS_PER_DAY),
        duration=int(duration * HOURS_PER_DAY),
        magnitude=mag,
        drain=True,
    )

def _diff_per_day_from_cumulative(times, cum, hours_per_day=1) -> List[float]:
    if not times or not cum or len(times)!=len(cum): return []
    if max(times) <= 0: return []
    n_days = int(math.ceil(max(times)/float(hours_per_day)))
    out, last = [], 0.0
    for d in range(1, n_days+1):
        end = d*hours_per_day
        idx = max(i for i,t in enumerate(times) if t<=end)
        val = float(cum[idx]); out.append(max(0.0, val-last)); last = val
    return out

def extract_aggregate_daily(sim_result) -> List[float]:
    # run_simulation -> (list_par_site, list_env)
    if isinstance(sim_result, tuple):
        sim_result = sim_result[0]
    series, mlen = [], 0
    for blk in sim_result:  # un dict par site
        val = blk.get("Total Seats made")
        if isinstance(val, (list, tuple)) and len(val) == 2:
            times, cum = list(val[0]), list(val[1])  # 'times' sont déjà en jours (= env.now/8)
            arr = _diff_per_day_from_cumulative(times, cum, 1)
            if arr:
                series.append(arr); mlen = max(mlen, len(arr))
    if not series: return []
    for i,a in enumerate(series):
        if len(a) < mlen: series[i] = a + [0.0]*(mlen-len(a))
    return [sum(v) for v in zip(*series)]

def daily_loss(cfg, stype, tgt, start, duration, horizon, magnitude) -> float:
    cfg = clone_config_with_horizon(cfg, horizon)
    base  = extract_aggregate_daily(run_simulation(cfg, events=None))[:horizon]
    shock = extract_aggregate_daily(run_simulation(cfg, events=[build_event(stype, tgt, start, duration, magnitude)]))[:horizon]
    L = max(len(base), len(shock), horizon)
    base  += [0.0]*(L - len(base))
    shock += [0.0]*(L - len(shock))
    return float(sum(max(0.0, base[i]-shock[i]) for i in range(horizon)))

# --- Script Monte-Carlo -------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Monte-Carlo sensibilité globale (perte cumulée)")
    ap.add_argument("--shock-type", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--horizon", type=int, required=True)
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--mag-min", type=float, default=0.2)
    ap.add_argument("--mag-max", type=float, default=1.0)
    ap.add_argument("--start-min", type=int, default=5)
    ap.add_argument("--start-max", type=int, default=40)
    ap.add_argument("--dur-min", type=int, default=5)
    ap.add_argument("--dur-max", type=int, default=30)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--csv", default="mc.csv")
    ap.add_argument("--save", default="mc.png")
    ap.add_argument("--debug-one", action="store_true", help="fait un run fixe (mag=1, start=20, dur=20) et affiche la perte")
    args = ap.parse_args()

    if args.debug_one:
        L = daily_loss(lines_config, args.shock_type, args.target, 20, 20, args.horizon, 1.0)
        print(f"[DEBUG] perte (mag=1,start=20,dur=20) = {L:.1f} u")
        return

    rng = __import__("random").Random(args.seed)

    rows, losses = [], []
    for i in range(args.runs):
        m = rng.uniform(args.mag_min, args.mag_max)
        s = rng.randint(args.start_min, args.start_max)
        d = rng.randint(args.dur_min, args.dur_max)
        L = daily_loss(lines_config, args.shock_type, args.target, s, d, args.horizon, m)
        rows.append((i, round(m,3), s, d, int(L))); losses.append(L)

    # CSV
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["run","magnitude","start","duration","loss"])
        w.writerows(rows)
    print(f"[OK] CSV: {args.csv}")

    # Histo
    plt.figure(figsize=(6,4))
    plt.hist(losses, bins=20)
    plt.title(f"Monte-Carlo pertes — {args.shock_type}::{args.target} (n={args.runs})")
    plt.xlabel("perte cumulée (u)"); plt.ylabel("fréquence")
    plt.tight_layout()
    plt.savefig(args.save, dpi=150)
    print(f"[OK] PNG: {args.save}")

if __name__ == "__main__":
    main()
