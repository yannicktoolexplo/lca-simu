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
from event_engine import EventManager, example_events


def main_function():
    # Simulation DES
    all_production_data, _ = run_simulation(lines_config)

    max_production = {
        lines_config[i]['location']: data['Total Seats made'][1][-1]
        for i, data in enumerate(all_production_data)
    }

    # ----------- AJOUT GESTIONNAIRE ÉVÉNEMENTS ----------- #
    system_state = {
        'capacity': max_production.copy(),
        'capacity_nominal': max_production.copy(),
        'supply': {'aluminium': 1000, 'fabric': 800, 'polymers': 600, 'paint': 400},
        'supply_nominal': {'aluminium': 1000, 'fabric': 800, 'polymers': 600, 'paint': 400},
    }
    event_manager = EventManager(example_events)
    # ----------- FIN AJOUT -----------



    print("\n🧮 Capacité maximale par site (simulation) :")
    for site, total in max_production.items():
        print(f"  {site} : Low = {round(total/2)} unités, High = {int(total)} unités")


    config = {
        "lines_config": lines_config,
        "include_supply": True,
        "include_storage": True,
    }

    # Simulation événements perturbateurs avant les scénarios
    N = 60  # nombre de pas à simuler (ou adapte à ta durée)
    for t in range(N):
        event_manager.step(t, system_state)
        # Ici tu pourrais loguer ou afficher la capacité courante
        if t in [19, 20, 24, 25, 50, 59, 60]:  # exemples pour voir le changement
            print(f"[t={t}] Capacité France = {system_state['capacity']['France']}, Aluminium = {system_state['supply']['aluminium']}")

    config["capacity_override"] = system_state["capacity"]

    result_baseline = run_scenario(run_simple_allocation_dict, config)
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
        "Baseline": result_baseline,
        "Optimisation Coût": result_optim_cost,
        "Optimisation CO₂": result_optim_co2,
        "MultiObjectifs": result_multi,
        "Lightweight": result_lightweight 
    }


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







    return {
        "figures": comparison_figs + sankey_figs,
        "lca_fig": fig_lca_fr,
        "vivant_raw_data": result_vivant_raw,  # Pour affichage tension dans dashboard
         "scenario_results": scenario_results,
    }



if __name__ == '__main__':
    main_function()
    # 🟦 Simulation vivante avec perturbation

