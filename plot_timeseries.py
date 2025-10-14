#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt
from line_production.line_production_settings import lines_config

# --- import robuste du moteur de simulation (plusieurs chemins possibles) ---
def _import_run_simulation():
    try:
        from line_production.production_engine import run_simulation
        return run_simulation
    except Exception:
        pass
    try:
        from line_production.line_production import run_simulation
        return run_simulation
    except Exception:
        pass
    raise ImportError(
        "Impossible d’importer run_simulation (essaie line_production.production_engine ou line_production.line_production)."
    )

# --- extraction robuste d'une série depuis le résultat retour du moteur ---
# --- extraction robuste d'une série depuis le résultat retour du moteur ---
def _get_series(res, prefer=None):
    """
    Accepte:
      - dict : on prend prefer ou une clé candidate
      - list/tuple : on fouille chaque item (dict -> clé, ou array 1D directement)
      - array/list 1D : on le prend tel quel
    """
    import numpy as _np

    candidate_keys = [
        "total_production", "production_total", "prod_total",
        "production", "prod", "y_total", "y", "total_output"
    ]

    def _as_series(obj):
        # ndarray / list / tuple -> si 1D on le prend
        if isinstance(obj, (list, tuple, _np.ndarray)):
            arr = _np.asarray(obj, dtype=float)
            if arr.ndim == 1:
                return arr
            if arr.ndim > 1 and 1 in arr.shape:
                return arr.reshape(-1)
            return None
        # dict -> prefer puis candidates
        if isinstance(obj, dict):
            if prefer and prefer in obj:
                return _np.asarray(obj[prefer], dtype=float)
            for k in candidate_keys:
                if k in obj:
                    return _np.asarray(obj[k], dtype=float)
            return None
        return None

    # 1) essai direct
    s = _as_series(res)
    if s is not None:
        return s

    # 2) si c'est un conteneur, on le parcourt
    if isinstance(res, (list, tuple)):
        for it in res:
            s = _as_series(it)
            if s is not None:
                return s

    # 3) rien trouvé -> message explicite
    raise TypeError(
        f"Impossible d'extraire une série. Type(res)={type(res).__name__}; "
        f"contenu indicatif={str(res)[:200]}..."
    )



def main():
    parser = argparse.ArgumentParser(description="Baseline vs choc — production (matplotlib, fond clair)")
    parser.add_argument("--shock-type", required=True, help="type de choc (ex: site_shutdown)")
    parser.add_argument("--target", required=True, help="cible du choc (ex: PLANT_FR)")
    parser.add_argument("--start", type=int, default=20, help="début du choc (jour)")
    parser.add_argument("--duration", type=int, default=25, help="durée du choc (jours)")
    parser.add_argument("--horizon", type=int, default=45, help="nb de jours à simuler (>= start+duration)")
    parser.add_argument("--series-key", type=str, default=None, help="(optionnel) clé explicite de la série dans le retour simu")
    parser.add_argument("--save", type=str, default=None, help="chemin du PNG à enregistrer (sinon plt.show())")
    args = parser.parse_args()

    # horizon effectif au moins jusqu'à la fin du choc
    horizon = max(int(args.horizon), int(args.start + args.duration))


    run_simulation = _import_run_simulation()

    # --- 1) Baseline : même système, aucun choc ---
    res_base = None
    try:
        res_base = run_simulation(lines_config, n_days=horizon)
    except TypeError:
        try:
            res_base = run_simulation(lines_config, horizon=horizon)
        except TypeError:
            try:
                # dernier recours : sans param de durée (le moteur gère l'horizon en interne)
                res_base = run_simulation(lines_config)
            except Exception as e:
                raise RuntimeError(f"Echec baseline: {e}")

    # --- 2) Choc : même système + arrêt ciblé dans la fenêtre de choc ---
    shock_kwargs = dict(
        shock_type=args.shock_type,
        target=args.target,
        shock_start=int(args.start),
        shock_duration=int(args.duration),
    )

    res_choc = None
    # ordre d'essai: kwargs à plat, puis horizon=..., puis shock=dict
    try:
        res_choc = run_simulation(lines_config, n_days=horizon, **shock_kwargs)
    except TypeError:
        try:
            res_choc = run_simulation(lines_config, horizon=horizon, **shock_kwargs)
        except TypeError:
            try:
                res_choc = run_simulation(lines_config, n_days=horizon, shock=shock_kwargs)
            except TypeError:
                try:
                    res_choc = run_simulation(lines_config, shock=shock_kwargs)
                except Exception as e:
                    raise RuntimeError(f"Echec choc: {e}")

    # Sanity check
    if res_base is None:
        raise RuntimeError("Baseline: run_simulation(...) n'a rien retourné (None).")
    if res_choc is None:
        raise RuntimeError("Choc: run_simulation(...) n'a rien retourné (None).")

    # Logs de types (protégés)
    print("[baseline] type:", type(res_base).__name__)
    print("[choc    ] type:", type(res_choc).__name__)


    # --- extraction des séries (sans modif des données) ---
    y_base_raw = _get_series(res_base, prefer=args.series_key)
    y_choc_raw = _get_series(res_choc, prefer=args.series_key)

    # === diagnostics (affichage console) ===
    def _diag(name, a):
        a = np.asarray(a, dtype=float)
        n = a.size
        if n == 0:
            print(f"[{name}] len=0 (vide)")
            return
        mask = ~np.isnan(a)
        if not mask.any():
            print(f"[{name}] len={n} (toutes valeurs NaN)")
            return
        first = int(np.argmax(mask))
        last = int(n - 1 - np.argmax(mask[::-1]))
        print(f"[{name}] len={n}  first_valid={first}  last_valid={last}")

    print(">> DIAG: horizon=", horizon, "start=", args.start, "duration=", args.duration)
    _diag("baseline", y_base_raw)
    _diag("choc    ", y_choc_raw)


    # on trace UNIQUEMENT ce qui existe (pas de ffill, pas de padding visuel)
    n_base = min(len(y_base_raw), horizon)
    n_choc = min(len(y_choc_raw), horizon)
    t_base = np.arange(n_base)
    t_choc = np.arange(n_choc)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(12, 6), facecolor="white")
    ax.set_facecolor("white")

    # fenêtre de choc derrière les courbes
    x0 = int(args.start)
    x1 = int(min(args.start + args.duration, horizon))
    ax.axvspan(x0, x1, alpha=0.08, color="grey", label="fenêtre de choc", zorder=0)

    ax.plot(t_base, y_base_raw[:n_base], marker="o", label="baseline", zorder=2)
    ax.plot(t_choc, y_choc_raw[:n_choc], marker="o",
            label=f"{args.shock_type}::{args.target}", zorder=2)

    ax.set_xlim(0, horizon - 1)
    ax.set_xlabel("Temps (jours)")
    ax.set_ylabel("Production totale (u/jour)")
    ax.set_title("Baseline vs choc — production")
    ax.grid(True, alpha=0.3)
    ax.legend(framealpha=0.95, facecolor="white")

    if args.save:
        plt.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"[OK] Figure -> {args.save}")
    else:
        plt.show()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERREUR:", e, file=sys.stderr)
        sys.exit(1)
