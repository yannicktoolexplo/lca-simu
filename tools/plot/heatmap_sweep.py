# heatmap_sweep.py
import argparse, pandas as pd, numpy as np
import matplotlib.pyplot as plt
import os

def pick_metric(row, metric):
    if metric == "lost_area_rel":
        return float(row.get("lost_area_rel", row.get("area_rel", 0.0)) or 0.0)
    if metric == "amplitude_rel":
        return float(row.get("amplitude_rel", row.get("ampl_rel", 0.0)) or 0.0)
    if metric == "cost_delta_rel":
        return float(row.get("cost_delta_rel", row.get("Δcost_rel", 0.0)) or 0.0)
    if metric == "score":
        return float(row.get("score", 0.0) or 0.0)
    return 0.0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sweep", required=True)
    p.add_argument("--metric", default="lost_area_rel",
                   choices=["lost_area_rel","score","cost_delta_rel","amplitude_rel"])
    p.add_argument("--save", default="plots/heatmap.png")
    p.add_argument("--durations", nargs="+", type=int, default=[15])
    args = p.parse_args()

    df = pd.read_csv(args.sweep)
    if "shock_name" not in df.columns:
        if "shock" in df.columns: df["shock_name"] = df["shock"]
        else: raise SystemExit("shock_name absent")
    if "duration_days" not in df.columns:
        raise SystemExit("duration_days absent (regénère sweep.csv)")

    df["_val"] = df.apply(lambda r: pick_metric(r, args.metric), axis=1)
    piv = df.pivot_table(index="shock_name", columns="duration_days", values="_val", aggfunc="mean")
    # trie par moyenne décroissante (ou l’inverse si tu veux “pire d’abord” selon la métrique)
    piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index]

    plt.figure(figsize=(10, max(4, len(piv)/3)))
    im = plt.imshow(piv.values, aspect="auto", interpolation="nearest")
    plt.colorbar(im, label=args.metric)
    plt.yticks(range(len(piv.index)), piv.index)
    plt.xticks(range(len(piv.columns)), piv.columns)
    plt.xlabel("Durée (jours)")
    plt.title(f"Heatmap {args.metric} (moyenne par durée)")
    os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
    plt.savefig(args.save, bbox_inches="tight", dpi=150)
    print(f"[OK] {args.save}")

if __name__ == "__main__":
    main()
