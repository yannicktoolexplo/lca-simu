from optimization.optimization_engine import (
    run_simple_allocation_dict,
    run_optimization_allocation_dict,
    run_optimization_co2_allocation_dict,
    run_multiobjective_allocation_dict,
    run_supply_chain_lightweight_scenario
)
from line_production.line_production_settings import lines_config
from line_production.production_engine import run_simple_supply_allocation
from scenario_engine import run_scenario, compare_scenarios
from scenario_engine import display_sankey_for_scenarios
from line_production.line_production import run_simulation
from sqlalchemy import create_engine, Table, MetaData, insert
from sqlalchemy.orm import sessionmaker
import streamlit as st
from utils.data_tools import display_all_lca_indicators
from environment.environment_engine import (
    calculate_lca_indicators_usage_phase,
    calculate_lca_indicators_pers_eq,
    calculate_lca_indicators_total
)
from optimization.optimization_engine import (
    run_supply_chain_optimization,
    run_supply_chain_optimization_minimize_co2,
    run_supply_chain_lightweight_scenario
)
from hybrid_regulation_engine import run_simulation_vivant
import pprint

from event_engine import EventManager, PerturbationEvent
from line_production.line_production_settings import lines_config, scenario_events
from line_production.line_production import run_simulation

def main_function():
    # Simulation DES
    all_production_data, _ = run_simulation(lines_config)

    max_production = {
        lines_config[i]['location']: data['Total Seats made'][1][-1]
        for i, data in enumerate(all_production_data)
    }


    print("\n🧮 Capacité maximale par site (simulation) :")
    for site, total in max_production.items():
        print(f"  {site} : Low = {round(total/2)} unités, High = {int(total)} unités")


    config = {
        "lines_config": lines_config,
        "include_supply": True,
        "include_storage": True,
    }



    # Scénario baseline (aucun événement)
    result_baseline = run_scenario(run_simple_allocation_dict, config)

    # Scénario crise (perturbations activées)
    config_crise = { **config, "events": scenario_events["crise"] }
    result_crise = run_scenario(run_simple_allocation_dict, config_crise)

    result_optim_cost = run_scenario(run_optimization_allocation_dict, config)
    result_optim_co2 = run_scenario(run_optimization_co2_allocation_dict, config)
    result_multi = run_scenario(run_multiobjective_allocation_dict, config)
    result_lightweight = run_scenario(
    lambda cap, demand: run_supply_chain_lightweight_scenario(cap, demand, seat_weight=70),
    {**config, "seat_weight": 70})




    # 🧠 Nouveau scénario vivant
    result_vivant_raw = run_simulation_vivant(lines_config)
    pprint.pprint(lines_config)
    result_vivant = {
        "production_totals": {
            site: sum([r["stock"] for r in result_vivant_raw if r["site"] == site])
            for site in set(r["site"] for r in result_vivant_raw)
        },
        "production_data": result_vivant_raw,
        "environment_data": [{} for _ in lines_config],
        "costs": {"total_cost": 0},
        "total_co2": 0,
        # ⛏️ Clés vides pour compatibilité Sankey
        "source": [],
        "target": [],
        "value": [],
        "loc_prod": {},
        "loc_demand": {},
        "market_totals": {},
        "cap": {}
    }

    result_vivant["costs"]["total_cost"] = 0  # Fictif
    result_vivant["total_co2"] = 0        # Fictif

    # Connexion à SQLite
    engine = create_engine('sqlite:///simchain.db')
    metadata = MetaData()
    metadata.reflect(bind=engine)
    result_table = Table('result', metadata, autoload_with=engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    scenario_results = {
        "Baseline": {**result_baseline, "allocation_func": run_simple_allocation_dict},
        "Optimisation Coût": {**result_optim_cost, "allocation_func": run_optimization_allocation_dict},
        "Optimisation CO₂": {**result_optim_co2, "allocation_func": run_optimization_co2_allocation_dict},
        "MultiObjectifs": {**result_multi, "allocation_func": run_multiobjective_allocation_dict},
        "Lightweight": {**result_lightweight, "allocation_func": lambda cap, demand: run_supply_chain_lightweight_scenario(cap, demand, seat_weight=70)},
    }

    # --- Résultat du scénario de crise à part ---
    crisis_result = {**result_crise, "allocation_func": run_simple_allocation_dict}

    for name, result in scenario_results.items():
        base_config = {
            "lines_config": lines_config,
            "include_supply": True,
            "include_storage": True,
            "loc_prod": {},  # <-- ajout temporaire si tu n’as pas la vraie valeur
        }

        res_supply = run_scenario(result["allocation_func"], {**base_config, "events": scenario_events["shock_supply"]})
        res_prod   = run_scenario(result["allocation_func"], {**base_config, "events": scenario_events["shock_production"]})
        res_dist   = run_scenario(result["allocation_func"], {**base_config, "events": scenario_events["shock_distribution"]})

        scenario_results[name]["resilience_test"] = {
            "supply": res_supply,
            "production": res_prod,
            "distribution": res_dist
        }

        crisis_result["resilience_test"] = {
        "supply": res_supply,
        "production": res_prod,
        "distribution": res_dist
    }

    # --- Ensuite SEULEMENT, boucle pour calculer les scores de résilience ---
    def compute_resilience_score(result_nominal, result_crisis):
        prod_nominal = result_nominal.get("production_totals")
        prod_crisis  = result_crisis.get("production_totals")
        if prod_nominal is None or prod_crisis is None:
            return 0
        prod_nominal_sum = sum(prod_nominal.values())
        prod_crisis_sum = sum(prod_crisis.values())
        if prod_nominal_sum == 0:
            return 0
        return round(100 * min(prod_crisis_sum, prod_nominal_sum) / max(prod_nominal_sum, 1), 1)


    for name, results in scenario_results.items():
        # On récupère le résultat nominal (sans choc) et ceux des 3 chocs
        nominal = results
        tests   = results["resilience_test"]
    scores = {}
    for phase in ["supply", "production", "distribution"]:
        test = tests.get(phase)
        if test is None:
            scores[phase] = 0
        else:
            scores[phase] = compute_resilience_score(nominal, test)

        scores["total"] = round(sum(scores.values()) / 3, 1)
        scenario_results[name]["resilience_scores"] = scores
    tests = crisis_result["resilience_test"]
    scores = {phase: compute_resilience_score(crisis_result, tests[phase]) for phase in ["supply", "production", "distribution"]}
    scores["total"] = round(sum(scores.values()) / 3, 1)
    crisis_result["resilience_scores"] = scores

    for scenario_id, (name, result) in enumerate(scenario_results.items(), start=1):
        for site, total in result["production_totals"].items():
            session.execute(insert(result_table).values(
                scenario_id=scenario_id,
                site=site,
                total_production=total,
                total_cost=result["costs"].get("total_cost", 0),
                total_co2=result.get("total_co2", 0)
            ))
    session.commit()

    # Visualisation comparative
    comparison_figs = compare_scenarios(scenario_results, return_figures=True)
    sankey_figs = display_sankey_for_scenarios(scenario_results, return_figures=True)

    # Visualisation comparative pour la crise seule (ou plusieurs scénarios de crise si besoin)
    crisis_figs = compare_scenarios({"Crise": crisis_result}, return_figures=True)
    # Sankey pour la crise seule
    crisis_sankey_figs = display_sankey_for_scenarios({"Crise": crisis_result}, return_figures=True)



    # 🇫🇷 Analyse LCA France uniquement (sur scénario multi-objectif)
    fr_config = [cfg for cfg in lines_config if cfg["location"] == "France"]
    fr_index = lines_config.index(fr_config[0])

    fr_production_data = [result_multi["production_data"][fr_index]]
    fr_enviro_data = [result_multi["environment_data"][fr_index]]
    fr_totals = {"France": result_multi["production_totals"]["France"]}


    for name, result in scenario_results.items():
        # extraction minimale utile
        if len(result) == 9:
            seat_weight = result_multi[8]
        else:
            seat_weight = 130

    fig_lca_fr = display_all_lca_indicators(
        all_production_data=fr_production_data,
        all_enviro_data=fr_enviro_data,
        lines_config=fr_config,
        production_totals=fr_totals,
        use_allocated_production=True,seat_weight=seat_weight
    )





    # 2. Préparer les données pour tous les sites
    all_production_data_tot = result_multi["production_data"]  # Liste de dicts pour chaque site
    all_enviro_data_tot = result_multi["environment_data"]
    all_config_tot = lines_config  # toute la config

    production_totals_tot = result_multi["production_totals"]  # dict par site
    seat_weight = 130  # ou adapte si variable

    # 1. Calculer la production totale tous sites (sur le scénario de référence ou multi-objectifs)
    total_production = sum(result_multi["production_totals"].values())

    # 3. Génère la figure LCA totale (tous sites, toutes productions)
    fig_lca_total = display_all_lca_indicators(
        all_production_data=all_production_data_tot,
        all_enviro_data=all_enviro_data_tot,
        lines_config=all_config_tot,
        production_totals=production_totals_tot,
        use_allocated_production=True, seat_weight=seat_weight
)


    return {
        "figures": comparison_figs + sankey_figs,
        "lca_fig": fig_lca_fr,
        "production_totals_sum": total_production,
        "lca_fig_total": fig_lca_total,  # <-- Nouvelle clé
        "vivant_raw_data": result_vivant_raw,  # Pour affichage tension dans dashboard
         "scenario_results": scenario_results,
         "crisis_result": crisis_result,   
         "crisis_figures": crisis_figs + crisis_sankey_figs       # Crise à part !
    }



if __name__ == '__main__':
    main_function()
    # 🟦 Simulation vivante avec perturbation

