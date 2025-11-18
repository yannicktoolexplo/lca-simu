from optimization.optimization_engine import (
    run_simple_allocation_dict,
    run_optimization_allocation_dict,
    run_optimization_co2_allocation_dict,
    run_multiobjective_allocation_dict,
    run_supply_chain_lightweight_scenario,

)
from line_production.line_production_settings import lines_config, scenario_events
from line_production.line_production import run_simulation
from line_production.production_engine import get_global_production_rate
from sqlalchemy import create_engine, Table, MetaData, insert
from sqlalchemy.orm import sessionmaker
from utils.data_tools import display_all_lca_indicators, get_total_prod_curve
from hybrid_regulation_engine import run_simulation_vivant
from scenario_engine import run_scenario, compare_scenarios, display_sankey_for_scenarios
from resilience_indicators import compute_resilience_indicators, resilience_on_curve
from copy import deepcopy

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
    lines_config_max = deepcopy(lines_config)
    for cfg in lines_config_max:
        for mat in ["aluminium", "foam", "fabric", "paint"]:
            cap_key = f"{mat}_capacity"
            init_key = f"initial_{mat}"
            # Met un stock initial très grand
            cfg[init_key] = 1_000_000
            # Aligne la capacité sur ce stock si besoin
            cfg[cap_key] = max(cfg.get(cap_key, 0), cfg[init_key])


    config_maxcap = {
        "lines_config": lines_config_max,
        "include_supply": False,   # on ne veut pas de réapprovisionnement automatique
        "include_storage": True,
        "events": None
    }

    result_maxcap = run_scenario(run_simple_allocation_dict, config_maxcap)


    cap_max = {}
    prod_datas = result_maxcap.get("production_data", [])
    for cfg, site_data in zip(lines_config, prod_datas):
        # Attention, on cherche la *prod max sur un pas de temps*, pas le cumul
        prod_par_temps = site_data["Total Seats made"][1]
        cap_max[cfg['location']] = max(prod_par_temps)
        print(f"Capacité max observée pour {cfg['location']} : {cap_max[cfg['location']]}")




    # Configuration de base pour les scénarios
    base_config = {
        "lines_config": lines_config,
        "include_supply": True,
        "include_storage": True
    }

    # 2. Exécuter les différents scénarios sans perturbation
    result_baseline = run_scenario(run_simple_allocation_dict, base_config)
    # Scénario avec perturbations (crise)
    config_crise = {**base_config, "events": scenario_events["Rupture Alu"]}
    config_crise2 = {**base_config, "events": scenario_events["Panne Texas"]}
    result_crise = run_scenario(run_simple_allocation_dict, config_crise)
    result_crise2 = run_scenario(run_simple_allocation_dict, config_crise2)
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
    crisis_results = {
    "Baseline": {**result_baseline,   "allocation_func": run_simple_allocation_dict},
    "Crise 1": {**result_crise, "allocation_func": run_simple_allocation_dict},
    "Crise 2": {**result_crise2, "allocation_func": run_simple_allocation_dict}
}


    # 5. Pour chaque scénario nominal (hors crise)
    for name, scenario_res in scenario_results.items():
        config_shock = {**base_config, "loc_prod": {}}
        res_supply = run_scenario(scenario_res["allocation_func"], {**config_shock, "events": scenario_events["shock_supply"]})
        res_prod   = run_scenario(scenario_res["allocation_func"], {**config_shock, "events": scenario_events["shock_production"]})
        res_dist   = run_scenario(scenario_res["allocation_func"], {**config_shock, "events": scenario_events["shock_distribution"]})
        scenario_res["resilience_test"] = {
            "supply": res_supply,
            "production": res_prod,
            "distribution": res_dist
        }

    # 5bis. Pour chaque scénario de crise
    for name, crisis_res in crisis_results.items():
        # Tu peux adapter les chocs ici si tu veux, ou garder ceux de scenario_events["shock_*"]
        config_shock = {**base_config, "loc_prod": {}}
        res_supply = run_scenario(crisis_res["allocation_func"], {**config_shock, "events": scenario_events["shock_supply"]})
        res_prod   = run_scenario(crisis_res["allocation_func"], {**config_shock, "events": scenario_events["shock_production"]})
        res_dist   = run_scenario(crisis_res["allocation_func"], {**config_shock, "events": scenario_events["shock_distribution"]})
        crisis_res["resilience_test"] = {
            "supply": res_supply,
            "production": res_prod,
            "distribution": res_dist
        }

    # 6. Score de résilience - scenarios normaux
    def compute_resilience_score(result_nominal, result_crisis):

        prod_nominal = (result_nominal or {}).get("production_totals") or {}
        prod_crisis = {}
        if result_crisis and isinstance(result_crisis, dict):
            prod_crisis = (result_crisis or {}).get("production_totals") or {}
        total_nominal = sum(prod_nominal.values())
        total_crisis = sum(prod_crisis.values())
        if total_nominal == 0:
            return 0.0
        return round(100 * min(total_crisis, total_nominal) / total_nominal, 1)

    for name, scenario_res in scenario_results.items():
        tests = scenario_res["resilience_test"]
        scores = {phase: compute_resilience_score(scenario_res, tests[phase]) for phase in ["supply", "production", "distribution"]}
        scores["total"] = round(sum(scores.values()) / 3, 1)
        scenario_res["resilience_scores"] = scores

    # Calculer les scores de résilience pour chaque scénario de crise
    for name, scenario_res in crisis_results.items():
        tests = scenario_res.get("resilience_test", {})
        scores = {phase: compute_resilience_score(scenario_res, tests.get(phase, {})) for phase in ["supply", "production", "distribution"]}
        scores["total"] = round(sum(scores.values()) / 3, 1)
        crisis_results[name]["resilience_scores"] = scores


    # 7. Enregistrer les résultats de production dans la base de données
    for scenario_id, (name, scenario_res) in enumerate(scenario_results.items(), start=1):
        # Récupérer les totaux de production de façon robuste
        prod_totals = scenario_res.get("production_totals") or {}

        # Sécurité : si ce n’est pas un dict, on log et on ignore
        if not isinstance(prod_totals, dict):
            print(f"⚠️ production_totals invalide pour le scénario '{name}':", prod_totals)
            prod_totals = {}

        # Récupérer aussi les coûts/CO2 de façon défensive
        costs = scenario_res.get("costs") or {}
        if not isinstance(costs, dict):
            print(f"⚠️ costs invalide pour le scénario '{name}':", costs)
            costs = {}

        total_cost = costs.get("total_cost", 0.0)
        total_co2 = scenario_res.get("total_co2", 0.0)

        for site, total in prod_totals.items():
            session.execute(insert(result_table).values(
                scenario_id=scenario_id,
                site=site,
                total_production=total,
                total_cost=total_cost,
                total_co2=total_co2
            ))

    session.commit()

    # 8. Préparer les visualisations comparatives des scénarios
    comparison_figs = compare_scenarios(scenario_results, return_figures=True)
    sankey_figs = display_sankey_for_scenarios(scenario_results, return_figures=True)
    # Pour la visualisation groupée de tous les scénarios de crise :
    crisis_figs = compare_scenarios(crisis_results, return_figures=True)
    crisis_sankey_figs = display_sankey_for_scenarios(crisis_results, return_figures=True)


    print("DEBUG scenario_results keys =", list(scenario_results.keys()))
    print("DEBUG type MultiObjectifs =", type(scenario_results.get("MultiObjectifs", None)))


    # ------------------------------------------------------------------
    # Petit utilitaire pour uniformiser ce qu'on reçoit (list, dict, etc.)
    # ------------------------------------------------------------------
    def _extract_figs(obj):
        """
        Normalise en liste de figures Plotly, quel que soit le format :
        - None -> []
        - list -> list
        - dict -> valeurs (et sous-valeurs si dict de dict/list)
        - figure seule -> [figure]
        """
        if obj is None:
            return []

        # Déjà une liste de figures
        if isinstance(obj, list):
            return obj

        # Dictionnaire : on a peut-être {scenario: fig} ou {scenario: {type: fig}}
        if isinstance(obj, dict):
            figs = []
            for v in obj.values():
                if isinstance(v, list):
                    figs.extend(v)
                elif isinstance(v, dict):
                    # dict imbriqué, on récupère les valeurs
                    for vv in v.values():
                        figs.append(vv)
                else:
                    figs.append(v)
            return figs

        # Cas "figure seule"
        return [obj]

    all_figs = []
    all_figs += _extract_figs(comparison_figs)
    all_figs += _extract_figs(sankey_figs)
    all_figs += _extract_figs(crisis_figs)
    all_figs += _extract_figs(crisis_sankey_figs)

    # 9. Analyse LCA ciblée sur la France (scénario multi-objectifs)
    fr_config = [c for c in lines_config if c["location"] == "France"]
    fr_index = lines_config.index(fr_config[0]) if fr_config else 0

    fr_production_data = [result_multi["production_data"][fr_index]]
    fr_enviro_data = [result_multi["environment_data"][fr_index]]

    prod_totals_multi = result_multi.get("production_totals") or {}
    print("DEBUG MultiObjectifs – production_totals =", prod_totals_multi)

    fr_totals = {"France": prod_totals_multi.get("France", 0)}

    seat_weight = result_multi.get("seat_weight", DEFAULT_SEAT_WEIGHT)  # utilisé ailleurs, pas dans cette fonction

    fig_lca_fr = display_all_lca_indicators(
        fr_production_data,
        fr_enviro_data,
        [fr_config[0]],
        fr_totals,
        use_allocated_production=True,
        seat_weight=seat_weight,
        return_fig=True,  # <-- important
    )






    # 10. Analyse LCA globale tous sites (scénario multi-objectifs)
    result_multi = scenario_results.get("MultiObjectifs", {})
    prod_totals_multi = result_multi.get("production_totals", {}) or {}

    print("DEBUG MultiObjectifs production_totals =",
      scenario_results.get("MultiObjectifs", {}).get("production_totals"))
    total_production = sum(prod_totals_multi.values())

    if total_production <= 0:
        print("⚠️ Analyse LCA globale : aucune production totale dans le scénario multi-objectifs.")
        fig_lca_total = None
    else:
        fig_lca_total = display_all_lca_indicators(
            all_production_data=result_multi["production_data"],
            all_enviro_data=result_multi["environment_data"],
            lines_config=lines_config,
            production_totals=prod_totals_multi,
            use_allocated_production=True,
            seat_weight=seat_weight,
            return_fig=True,
        )




    # 1. Calcule la courbe du taux de prod (%) pour chaque scénario (baseline et crises)
    rate_curve_baseline = get_global_production_rate(result_baseline,lines_config, cap_max)
    time_vector = list(range(len(rate_curve_baseline)))

    for name, result_crise in crisis_results.items():
        rate_curve_crise = get_global_production_rate(result_crise,lines_config, cap_max)
        min_len = min(len(rate_curve_baseline), len(rate_curve_crise), len(time_vector))
        rate_curve_baseline_aligned = rate_curve_baseline[:min_len]
        rate_curve_crise_aligned = rate_curve_crise[:min_len]
        time_vector_aligned = time_vector[:min_len]
        
        # 1. Résilience "comparée au nominal" (sur taux)
        indicators_ref = compute_resilience_indicators(
            rate_curve_baseline_aligned, rate_curve_crise_aligned, time_vector_aligned
        )
        # 2. Résilience "auto-détection" sur la courbe de taux
        indicators_auto = resilience_on_curve(rate_curve_crise_aligned, time_vector=time_vector_aligned)
        
        result_crise["resilience_indicators"] = indicators_ref
        result_crise["resilience_auto_indicators"] = indicators_auto

    # 10bis. Normaliser aussi les figures de crise
    crisis_all_figs = _extract_figs(crisis_figs) + _extract_figs(crisis_sankey_figs) 


    # Préparer le dictionnaire de résultats final à retourner
    return {
        "figures": all_figs,
        "lca_fig": fig_lca_fr,
        "production_totals_sum": total_production,
        "lca_fig_total": fig_lca_total,
        "vivant_raw_data": result_vivant_raw,
        "scenario_results": scenario_results,
        "crisis_results": crisis_results,
        "crisis_figures": crisis_all_figs,
        "cap_max": cap_max, 
        "lines_config": lines_config
    }

if __name__ == '__main__':
    main_function()
