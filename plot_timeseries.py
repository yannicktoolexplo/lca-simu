# plot_timeseries.py
import argparse
import importlib
import os
import matplotlib.pyplot as plt

from adapters import default_sim_func, default_ts_extractor

# --------- utilitaires pour récupérer ta config lignes ----------
def _auto_load_lines_config():
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
    raise RuntimeError("Impossible de trouver LINES_CONFIG. Expose une variable liste de configs de lignes.")

def build_base_config():
    LINES_CONFIG = _auto_load_lines_config()
    horizon = max([lc.get("total_time", 0) for lc in LINES_CONFIG] + [120])
    return {
        "lines_config": LINES_CONFIG,
        "horizon": horizon,
        "time_units_per_day": 8,
        "target_daily_output": 120.0,
        "cost_params": {
            "c_var": 100.0, "c_fixed_per_day": 2000.0, "c_freight": 10.0, "penalty_per_missing": 150.0,
        },
    }

# --------- mapping "haut niveau" -> events SimPy que ton moteur comprend ----------
_MAT_ALIASES = {
    "al": "aluminium", "aluminium": "aluminium",
    "foam": "foam", "polymers": "foam",
    "fabric": "fabric", "tissu": "fabric",
    "paint": "paint",
}

def _mk_event(shock_type: str, target: str, t0_days: int, dur_days: int, tu_per_day: int, magnitude: float = 1.0, drain: bool = None):
    """
    Retourne un dict "event" pour ton run_simulation :
      {'event_type': 'panne'|'rupture_fournisseur'|'retard', 'target': <...>, 'time': <tu>, 'duration': <tu>, 'magnitude': <f>, 'drain': <bool?>}
    """
    t0 = int(t0_days * tu_per_day)
    dur = int(dur_days * tu_per_day)
    st = shock_type.lower()

    if st in ("site_shutdown", "panne"):
        return {"event_type": "panne", "target": target, "time": t0, "duration": dur, "magnitude": magnitude}

    if st in ("material_block", "rupture", "rupture_fournisseur"):
        tgt = _MAT_ALIASES.get(target.lower(), target)
        ev = {"event_type": "rupture_fournisseur", "target": tgt, "time": t0, "duration": dur, "magnitude": magnitude}
        if drain is not None:
            ev["drain"] = bool(drain)  # optionnel : si tu patches _handle_supply_event pour lire ev.get("drain")
        return ev

    if st in ("leadtime_spike", "retard", "material_delay"):
        tgt = _MAT_ALIASES.get(target.lower(), target)
        return {"event_type": "retard", "target": tgt, "time": t0, "duration": dur, "magnitude": magnitude}

    raise ValueError(f"Type de choc non supporté ici: {shock_type}")

# --------- exécution & extraction série ----------
def _run_and_get_ts(sim_fn, base_cfg, events):
    cfg = dict(base_cfg)
    cfg["events"] = events
    res = sim_fn(cfg, events)  # adapters.default_sim_func sait dispatch vers ta SimPy
    ts = default_ts_extractor(res)
    return ts  # liste[float] longueur = horizon

def main():
    p = argparse.ArgumentParser(description="Courbe temporelle baseline vs choc (production totale)")
    p.add_argument("--shock-type", required=True,
                   choices=["site_shutdown","material_block","material_delay","panne","rupture_fournisseur","retard"],
                   help="Type de perturbation à injecter")
    p.add_argument("--target", required=True, help="Cible du choc (ex: PLANT_FR, aluminium, fabric, foam)")
    p.add_argument("--start", type=int, default=20, help="Début (en jours)")
    p.add_argument("--duration", type=int, default=10, help="Durée (en jours)")
    p.add_argument("--magnitude", type=float, default=1.0, help="Amplitude relative (si pertinent)")
    p.add_argument("--no-drain", action="store_true",
                   help="Pour material_block: ne pas purger le stock à t0 (si tu as patché _handle_supply_event pour lire 'drain').")
    p.add_argument("--use-dummy", action="store_true", help="Forcer le dummy (debug)")
    p.add_argument("--save", type=str, default="", help="Chemin PNG (facultatif). Sinon, affiche à l'écran.")
    args = p.parse_args()

    base = build_base_config()
    tu_per_day = int(base.get("time_units_per_day", 8))

    # baseline
    ts_base = _run_and_get_ts(default_sim_func if not args.use_dummy else (lambda c, e: _dummy_fallback(c, e)), base, [])

    # choc
    ev = _mk_event(args.shock_type, args.target, args.start, args.duration, tu_per_day,
                   magnitude=args.magnitude, drain=(False if args.no_drain else None))
    ts_choc = _run_and_get_ts(default_sim_func if not args.use_dummy else (lambda c, e: _dummy_fallback(c, e)), base, [ev])

    # axe temps en jours
    import numpy as np
    t = np.arange(len(ts_base)) / float(tu_per_day)

    # plot
    plt.figure(figsize=(10, 5))
    plt.plot(t, ts_base, label="baseline", marker="o")
    plt.plot(t, ts_choc, label=f"{args.shock_type}::{args.target}", marker="o")
    # fenêtre du choc
    plt.axvspan(args.start, args.start + args.duration, alpha=0.15, label="fenêtre de choc")
    plt.xlabel("Temps (jours)")
    plt.ylabel("Production totale (u/jour)")
    plt.title("Baseline vs choc — production")
    plt.legend()
    plt.grid(True, alpha=0.3)

    if args.save:
        os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
        plt.savefig(args.save, bbox_inches="tight", dpi=150)
        print(f"[OK] Figure -> {args.save}")
    else:
        plt.show()

# fallback minuscule si --use-dummy (optionnel)
def _dummy_fallback(cfg, events):
    # production plate + drop simple (utile si tu veux tester sans ta SimPy)
    H = cfg.get("horizon", 120)
    base = [100.0]*H
    prod = base[:]
    tu_per_day = cfg.get("time_units_per_day", 8)
    for ev in events:
        t0, d = int(ev["time"]), int(ev["duration"])
        drop = 0.5
        for t in range(t0, min(H, t0+d)):
            prod[t] *= (1.0 - drop)
    return {"production_ts_total": prod, "costs": {}, "service": {}}

if __name__ == "__main__":
    main()
