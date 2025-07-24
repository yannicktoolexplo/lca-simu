from optimization.optimization_engine import (
    run_simple_allocation_dict,
    run_optimization_allocation_dict,
    run_optimization_co2_allocation_dict,
    run_multiobjective_allocation_dict,
    run_supply_chain_lightweight_scenario,

)
from line_production.line_production_settings import lines_config, scenario_events
from line_production.line_production import run_simulation
from sqlalchemy import create_engine, Table, MetaData, insert
from sqlalchemy.orm import sessionmaker
from utils.data_tools import display_all_lca_indicators
from hybrid_regulation_engine import run_simulation_vivant
from scenario_engine import run_scenario, compare_scenarios, display_sankey_for_scenarios

# Configuration constants
DEFAULT_SEAT_WEIGHT = 130       # Poids de siège par défaut (kg)
LIGHTWEIGHT_SEAT_WEIGHT = 70    # Poids de siège utilisé pour le scénario lightweight (kg)
DB_PATH = 'sqlite:///simchain.db'  # Chemin de la base de données SQLite

def main_function():
    """Exécute la simulation logistique pour différents scénarios, calcule les coûts, 
    émissions et scores de résilience, puis retourne les résultats formatés pour le tableau de bord."""
    # 1. Simulation de base (production sans événements)
    all_production_data, _ = run_simulation(lines_config)
    # Calculer la production totale simulée par site (pour définir capacités)
    max_production = {
        cfg['location']: data['Total Seats made'][1][-1]
        for cfg, data in zip(lines_config, all_production_data)
    }

    # Configuration de base pour les scénarios
    base_config = {
        "lines_config": lines_config,
        "include_supply": True,
        "include_storage": True
    }

    # 2. Exécuter les différents scénarios sans perturbation
    result_baseline = run_scenario(run_simple_allocation_dict, base_config)
    # Scénario avec perturbations (crise)
    config_crise = {**base_config, "events": scenario_events["crise"]}
    result_crise = run_scenario(run_simple_allocation_dict, config_crise)
    # Optimisation coût, optimisation CO₂, multi-objectifs, scénario simplifié léger
    result_optim_cost = run_scenario(run_optimization_allocation_dict, base_config)
    result_optim_co2 = run_scenario(run_optimization_co2_allocation_dict, base_config)
    result_multi = run_scenario(run_multiobjective_allocation_dict, base_config)
    result_lightweight = run_scenario(
        lambda cap, demand: run_supply_chain_lightweight_scenario(cap, demand, seat_weight=LIGHTWEIGHT_SEAT_WEIGHT),
        {**base_config, "seat_weight": LIGHTWEIGHT_SEAT_WEIGHT}
    )

    # 3. Simulation vivante (système vivant avec logique de régulation cognitive)
    result_vivant_raw = run_simulation_vivant(lines_config)
    # Construire un résultat compatible avec les autres scénarios (mêmes clés attendu par le dashboard)
    result_vivant = {
        "production_totals": {
            site: sum(r["stock"] for r in result_vivant_raw if r["site"] == site)
            for site in {r["site"] for r in result_vivant_raw}
        },
        "production_data": result_vivant_raw,
        "environment_data": [{} for _ in lines_config],
        "costs": {"total_cost": 0},
        "total_co2": 0,
        # Clés vides pour compatibilité avec les fonctions Sankey
        "source": [],
        "target": [],
        "value": [],
        "loc_prod": {},
        "loc_demand": {},
        "market_totals": {},
        "cap": {}
    }

    # 4. Préparation de la base de données SQLite et insertion des résultats
    engine = create_engine(DB_PATH)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    result_table = Table('result', metadata, autoload_with=engine)
    Session = sessionmaker(bind=engine)
    session = Session()


    # Regrouper tous les résultats de scénarios dans un dictionnaire
    scenario_results = {
        "Baseline":        {**result_baseline,   "allocation_func": run_simple_allocation_dict},
        "Optimisation Coût":  {**result_optim_cost, "allocation_func": run_optimization_allocation_dict},
        "Optimisation CO₂":   {**result_optim_co2,  "allocation_func": run_optimization_co2_allocation_dict},
        "MultiObjectifs":  {**result_multi,     "allocation_func": run_multiobjective_allocation_dict},
        "Lightweight":     {**result_lightweight, "allocation_func": lambda cap, demand: run_supply_chain_lightweight_scenario(cap, demand, seat_weight=LIGHTWEIGHT_SEAT_WEIGHT)}
    }
    # Stocker également le scénario de crise à part
    crisis_result = {**result_crise, "allocation_func": run_simple_allocation_dict}

    # 5. Pour chaque scénario, simuler des perturbations de type choc (approvisionnement, production, distribution)
    for name, scenario_res in scenario_results.items():
        # Config de base pour les simulations de choc (pas d'événement initial dans loc_prod)
        config_shock = {**base_config, "loc_prod": {}}
        # Exécuter les trois types de chocs séparément
        res_supply = run_scenario(scenario_res["allocation_func"], {**config_shock, "events": scenario_events["shock_supply"]})
        res_prod   = run_scenario(scenario_res["allocation_func"], {**config_shock, "events": scenario_events["shock_production"]})
        res_dist   = run_scenario(scenario_res["allocation_func"], {**config_shock, "events": scenario_events["shock_distribution"]})
        # Enregistrer les résultats des tests de résilience dans le scénario correspondant
        scenario_results[name]["resilience_test"] = {
            "supply": res_supply,
            "production": res_prod,
            "distribution": res_dist
        }
        # Pour le scénario de crise, on utilise les mêmes chocs (on prend le dernier calculé dans la boucle)
        crisis_result["resilience_test"] = {
            "supply": res_supply,
            "production": res_prod,
            "distribution": res_dist
        }

    # 6. Calculer les scores de résilience pour chaque scénario et pour la crise
    def compute_resilience_score(result_nominal, result_crisis):
        """Calcule un score de résilience (en %) entre un scénario nominal et son scénario sous choc."""
        prod_nominal = result_nominal.get("production_totals", {})
        prod_crisis = result_crisis.get("production_totals", {})
        total_nominal = sum(prod_nominal.values())
        total_crisis = sum(prod_crisis.values())
        if total_nominal == 0:
            return 0.0
        # Score = 100 * (production sous choc / production nominale) (limité à 100 si crise > nominal par exception)
        return round(100 * min(total_crisis, total_nominal) / total_nominal, 1)

    for name, scenario_res in scenario_results.items():
        tests = scenario_res["resilience_test"]
        scores = {phase: compute_resilience_score(scenario_res, tests[phase]) for phase in ["supply", "production", "distribution"]}
        scores["total"] = round(sum(scores.values()) / 3, 1)
        scenario_results[name]["resilience_scores"] = scores
    # Score pour le scénario de crise
    tests = crisis_result["resilience_test"]
    crisis_scores = {phase: compute_resilience_score(crisis_result, tests[phase]) for phase in ["supply", "production", "distribution"]}
    crisis_scores["total"] = round(sum(crisis_scores.values()) / 3, 1)
    crisis_result["resilience_scores"] = crisis_scores

    # 7. Enregistrer les résultats de production dans la base de données
    for scenario_id, (name, scenario_res) in enumerate(scenario_results.items(), start=1):
        for site, total in scenario_res["production_totals"].items():
            session.execute(insert(result_table).values(
                scenario_id=scenario_id,
                site=site,
                total_production=total,
                total_cost=scenario_res["costs"].get("total_cost", 0.0),
                total_co2=scenario_res.get("total_co2", 0.0)
            ))
    session.commit()

    # 8. Préparer les visualisations comparatives des scénarios
    comparison_figs = compare_scenarios(scenario_results, return_figures=True)
    sankey_figs = display_sankey_for_scenarios(scenario_results, return_figures=True)
    # Visualisations pour le scénario de crise seul
    crisis_figs = compare_scenarios({"Crise": crisis_result}, return_figures=True)
    crisis_sankey_figs = display_sankey_for_scenarios({"Crise": crisis_result}, return_figures=True)

    # 9. Analyse LCA ciblée sur la France (scénario multi-objectifs)
    fr_config = [cfg for cfg in lines_config if cfg["location"] == "France"]
    fr_index = lines_config.index(fr_config[0]) if fr_config else 0
    fr_production_data = [result_multi["production_data"][fr_index]]
    fr_enviro_data = [result_multi["environment_data"][fr_index]]
    fr_totals = {"France": result_multi["production_totals"].get("France", 0)}
    # Utiliser le poids de siège du scénario multi (ou défaut)
    seat_weight = result_multi.get("seat_weight", DEFAULT_SEAT_WEIGHT)
    fig_lca_fr = display_all_lca_indicators(
        all_production_data=fr_production_data,
        all_enviro_data=fr_enviro_data,
        lines_config=fr_config,
        production_totals=fr_totals,
        use_allocated_production=True,
        seat_weight=seat_weight
    )

    # 10. Analyse LCA globale tous sites (scénario multi-objectifs)
    total_production = sum(result_multi["production_totals"].values())
    fig_lca_total = display_all_lca_indicators(
        all_production_data=result_multi["production_data"],
        all_enviro_data=result_multi["environment_data"],
        lines_config=lines_config,
        production_totals=result_multi["production_totals"],
        use_allocated_production=True,
        seat_weight=DEFAULT_SEAT_WEIGHT
    )

    # Préparer le dictionnaire de résultats final à retourner
    return {
        "figures": comparison_figs + sankey_figs,
        "lca_fig": fig_lca_fr,
        "production_totals_sum": total_production,
        "lca_fig_total": fig_lca_total,
        "vivant_raw_data": result_vivant_raw,
        "scenario_results": scenario_results,
        "crisis_result": crisis_result,
        "crisis_figures": crisis_figs + crisis_sankey_figs
    }

if __name__ == '__main__':
    main_function()
