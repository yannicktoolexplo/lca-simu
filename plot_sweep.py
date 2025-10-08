# plot_sweep.py
import argparse
import csv
import os
from typing import Dict, List, Any, Tuple

import pandas as pd
import matplotlib.pyplot as plt


def _linreg(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
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


def _metric_from_row(row: Dict[str, Any], metric: str) -> float:
    # Harmonise les noms de colonnes possibles
    if metric == "lost_area_rel":
        return float(row.get("lost_area_rel", row.get("area_rel", 0.0)) or 0.0)
    if metric == "amplitude_rel":
        return float(row.get("amplitude_rel", row.get("ampl_rel", 0.0)) or 0.0)
    if metric == "cost_delta_rel":
        return float(row.get("cost_delta_rel", row.get("Δcost_rel", 0.0)) or 0.0)
    if metric == "score":
        return float(row.get("score", 0.0) or 0.0)
    return 0.0


def build_summary(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Résumé par choc : pente vs durée, moyenne, min/max, R²…"""
    rows = []
    for shock_name, grp in df.groupby("shock_name"):
        xs = grp["duration_days"].astype(float).tolist()
        ys = [_metric_from_row(r, metric) for r in grp.to_dict("records")]
        slope, intercept, r2 = _linreg(xs, ys)
        rows.append({
            "shock_name": shock_name,
            "type": grp["type"].iloc[0] if "type" in grp.columns and len(grp) > 0 else "",
            "target": grp["target"].iloc[0] if "target" in grp.columns and len(grp) > 0 else "",
            "metric": metric,
            "n_points": len(xs),
            "mean": sum(ys)/len(ys) if ys else 0.0,
            "min": min(ys) if ys else 0.0,
            "max": max(ys) if ys else 0.0,
            "std": (sum((y - (sum(ys)/len(ys)))**2 for y in ys)/len(ys))**0.5 if ys else 0.0,
            "slope_per_day": slope,
            "slope_per_10d": slope * 10.0,
            "r2": r2,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("slope_per_day", ascending=False)
    return out


def plot_metric_vs_duration(df: pd.DataFrame, metric: str, top: int, by: str,
                            save_path: str = None, title_suffix: str = ""):
    """
    Trace les courbes 'metric' vs durée pour les 'top' chocs, triés par 'by':
      - by = 'slope' -> plus forte pente (sensibilité à la durée)
      - by = 'mean'  -> plus forte moyenne
    """
    summary = build_summary(df, metric)
    if summary.empty:
        print("[WARN] Pas de données à tracer.")
        return

    if by == "slope":
        top_shocks = summary.head(top)["shock_name"].tolist()
        title_by = "pente vs durée"
    else:
        top_shocks = summary.sort_values("mean", ascending=False).head(top)["shock_name"].tolist()
        title_by = "moyenne"

    # Prépare la figure (une seule figure avec plusieurs lignes)
    plt.figure()
    for sn in top_shocks:
        sub = df[df["shock_name"] == sn].sort_values("duration_days")
        xs = sub["duration_days"].tolist()
        ys = [_metric_from_row(r, metric) for r in sub.to_dict("records")]
        plt.plot(xs, ys, marker="o", label=sn)

    plt.xlabel("Durée de perturbation (jours)")
    plt.ylabel(metric)
    plt.title(f"{metric} vs durée — top {top} par {title_by}{(' • ' + title_suffix) if title_suffix else ''}")
    plt.legend()
    plt.grid(True)

    if save_path:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight", dpi=150)
        print(f"[OK] Figure -> {save_path}")

    # Affiche si lancé en interactif
    if not save_path:
        plt.show()


def main():
    p = argparse.ArgumentParser(description="Tracer des courbes de perturbations à partir d'un sweep.csv")
    p.add_argument("--sweep", required=True, help="Chemin vers sweep.csv (export compare_shocks)")
    p.add_argument("--metric", default="lost_area_rel",
                   choices=["lost_area_rel","score","cost_delta_rel","amplitude_rel"],
                   help="Métrique à tracer (défaut: lost_area_rel)")
    p.add_argument("--top", type=int, default=8, help="Nombre de chocs à afficher (défaut: 8)")
    p.add_argument("--rank-by", default="slope", choices=["slope","mean"],
                   help="Critère de sélection (pente vs durée ou moyenne)")
    p.add_argument("--save-dir", default="plots", help="Dossier de sortie pour les PNG (défaut: plots)")
    p.add_argument("--prefix", default="", help="Préfixe des fichiers PNG")
    p.add_argument("--also-per-shock", action="store_true",
                   help="Génère un PNG par choc en plus de la figure combinée")
    args = p.parse_args()

    df = pd.read_csv(args.sweep)
    if "duration_days" not in df.columns:
        raise SystemExit("[ERREUR] Le CSV ne contient pas la colonne 'duration_days' (relance compare_shocks avec --export-csv-sweep).")
    if "shock_name" not in df.columns:
        # Compat : reconstitue si 'shock' est présent
        if "shock" in df.columns:
            df["shock_name"] = df["shock"]
        else:
            raise SystemExit("[ERREUR] Colonne 'shock_name' absente.")

    title_suffix = os.path.basename(args.sweep)
    combo_path = os.path.join(args.save_dir, f"{args.prefix}metric_{args.metric}_top{args.top}_{args.rank_by}.png")
    plot_metric_vs_duration(df, args.metric, args.top, args.rank_by, save_path=combo_path, title_suffix=title_suffix)

    if args.also_per_shock:
        # Un PNG par choc (pratique pour des rapports)
        for sn, grp in df.groupby("shock_name"):
            sp = os.path.join(args.save_dir, f"{args.prefix}metric_{args.metric}_{sn.replace('::','_').replace(' ','_')}.png")
            plot_metric_vs_duration(grp, args.metric, top=1, by="mean", save_path=sp, title_suffix=sn)


if __name__ == "__main__":
    main()
