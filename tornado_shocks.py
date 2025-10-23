# tornado_shocks.py
# -*- coding: utf-8 -*-
import argparse, copy, math
import matplotlib.pyplot as plt
from typing import Any
from sensitivity_grid import loss_for  # réutilise helpers

def main():
    ap = argparse.ArgumentParser(description="Tornado plot – élasticités locales")
    ap.add_argument("--shock-type", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--horizon", type=int, required=True)
    ap.add_argument("--magnitude", type=float, default=0.5)
    ap.add_argument("--start", type=int, default=20)
    ap.add_argument("--duration", type=int, default=20)
    ap.add_argument("--delta-mag", type=float, default=0.2)
    ap.add_argument("--delta-start", type=int, default=5)
    ap.add_argument("--delta-dur", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save", default="tornado.png")
    args = ap.parse_args()

    base_loss = loss_for(lines_config, args.shock_type, args.target, args.start, args.duration, args.horizon, args.magnitude, args.seed)

    tests = [
        ("magnitude −", max(0.0, args.magnitude-args.delta_mag)),
        ("magnitude +", min(1.0, args.magnitude+args.delta_mag)),
    ]
    losses = []
    # magnitude
    for label, m in tests:
        L = loss_for(lines_config, args.shock_type, args.target, args.start, args.duration, args.horizon, m, args.seed)
        losses.append((label, L-base_loss))
    # start
    for label, s in [("start −", max(0, args.start-args.delta_start)), ("start +", args.start+args.delta_start)]:
        L = loss_for(lines_config, args.shock_type, args.target, s, args.duration, args.horizon, args.magnitude, args.seed)
        losses.append((label, L-base_loss))
    # duration
    for label, d in [("duration −", max(1, args.duration-args.delta_dur)), ("duration +", args.duration+args.delta_dur)]:
        L = loss_for(lines_config, args.shock_type, args.target, args.start, d, args.horizon, args.magnitude, args.seed)
        losses.append((label, L-base_loss))

    # Plot horizontal bars (absolu trié)
    labels = [l for l,_ in losses]
    deltas = [abs(x) for _,x in losses]
    order = sorted(range(len(deltas)), key=lambda i: deltas[i], reverse=True)
    labels = [labels[i] for i in order]; deltas = [deltas[i] for i in order]

    plt.figure(figsize=(6,4))
    y = range(len(labels))
    plt.barh(list(y), deltas)
    plt.yticks(list(y), labels)
    plt.xlabel("Variation de perte (u)")
    plt.title(f"Tornado — {args.shock_type}::{args.target} (ref: loss={int(base_loss)})")
    plt.tight_layout()
    plt.savefig(args.save, dpi=150)
    print(f"[OK] Tornado: {args.save}")

if __name__ == "__main__":
    from line_production.line_production_settings import lines_config  # lazy import
    main()
