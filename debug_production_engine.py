# debug_production_engine.py

from copy import deepcopy

from line_production.line_production import run_simulation
from line_production.line_production_settings import lines_config, scenario_events
from line_production.production_engine import build_capacity_limits_from_cap_max
from scenario_engine import run_scenario
from optimization.optimization_engine import run_simple_allocation_dict

def compute_daily_from_cumul(cumul):
    if not cumul:
        return []
    daily = [cumul[0]]
    for i in range(1, len(cumul)):
        daily.append(max(cumul[i] - cumul[i-1], 0.0))
    return daily

def summarize_daily(daily):
    nb_days = len(daily)
    nb_active = sum(1 for d in daily if d > 0)
    first_zero = next((i for i, d in enumerate(daily) if d == 0), None)
    return nb_days, nb_active, first_zero

def print_daily_debug(label, all_production_data, lines_cfg):
    print(f"\n===== {label} =====")
    for cfg, site_data in zip(lines_cfg, all_production_data):
        loc = cfg["location"]
        cumul = site_data["Total Seats made"][1]
        daily = compute_daily_from_cumul(cumul)
        nb_days, nb_active, first_zero = summarize_daily(daily)
        print(f"[{loc}] jours={nb_days}, jours_actifs={nb_active}, "
              f"premier_jour_zero={first_zero}, prod_totale={sum(daily)}")
        # Tu peux aussi afficher une petite tranche pour vérifier visuellement
        print(f"  daily[0:20] = {[round(x,2) for x in daily[0:20]]}")

def main():
    # 1. Baseline actuel (celui de SimChainGreenHorizons)
    all_prod_baseline, _ = run_simulation(lines_config, events=None)
    print_daily_debug("Baseline brut (run_simulation, sans allocation)", all_prod_baseline, lines_config)

    # 2. Baseline avec cap_max très large (comme tu fais pour cap_max)
    lines_config_max = deepcopy(lines_config)
    for cfg in lines_config_max:
        for mat in ["aluminium", "foam", "fabric", "paint"]:
            cfg[f"initial_{mat}"] = 1_000_000
            cfg[f"{mat}_capacity"] = max(cfg.get(f"{mat}_capacity", 0), cfg[f"initial_{mat}"])

    # run_simulation sans events pour voir la prod brute potentielle
    all_prod_unconstrained, _ = run_simulation(lines_config_max, events=None)
    print_daily_debug("Prod brute avec stocks énormes (sans events)", all_prod_unconstrained, lines_config_max)

    # 3. Scénario complet avec allocation (comme dans SimChainGreenHorizons)
    config_maxcap = {
        "lines_config": lines_config_max,
        "include_supply": False,
        "include_storage": True,
        "events": None,
    }
    result_maxcap = run_scenario(run_simple_allocation_dict, config_maxcap)
    all_prod_alloc = result_maxcap.get("production_data", [])
    print_daily_debug("Prod avec allocation (result_maxcap)", all_prod_alloc, lines_config)

if __name__ == "__main__":
    main()
