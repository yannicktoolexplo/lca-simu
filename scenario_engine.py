from line_production.line_production import run_simulation
from line_production.line_production_settings import lines_config
from line_production.production_engine import load_capacity_limits, load_fixed_and_variable_costs
from distribution.distribution_engine import load_freight_costs_and_demands
from utils.data_tools import plot_production_sankey, plot_sankey_production_co2_emissions, display_all_lca_indicators
from economic.cost_engine import calculate_total_costs, calculer_penalite_non_livraison
from environment.environment_engine import (
    calculate_lca_production_IFE_raw,
    calculate_distribution_co2_emissions,
    calculate_lca_indicators_usage_phase,
    calculate_lca_indicators_pers_eq,
    calculate_lca_indicators_total
)
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def run_scenario(allocation_function, config):
    """
    Exécute une simulation complète de chaîne d'approvisionnement pour un scénario donné.
    :param allocation_function: Fonction d'allocation (prend en entrée cap, demand et retourne un dict de résultats).
    :param config: Dictionnaire de configuration pour la simulation (peut contenir 'lines_config', 'events', etc.).
    :return: Dictionnaire de résultats du scénario (production_totals, market_totals, costs, total_co2, etc.).
    """
    # Lancer la simulation de production (éventuellement avec événements perturbateurs)
    all_production_data, all_enviro_data = run_simulation(config["lines_config"], events=config.get("events"))
    seat_weight = config.get("seat_weight", 130)
    # Calcul des capacités Low/High pour chaque site en fonction de la production simulée
    max_production = {
        cfg['location']: data['Total Seats made'][1][-1] 
        for cfg, data in zip(config["lines_config"], all_production_data)
    }
    cap = load_capacity_limits(max_production)
    # Charger les coûts de transport (freight) et la demande depuis les données
    freight_costs, demand = load_freight_costs_and_demands()
    fixed_costs, variable_costs = load_fixed_and_variable_costs(freight_costs)
    # Exécuter l'allocation de production/distribution avec la fonction spécifiée
    result = allocation_function(cap, demand)
    # Vérifier qu'il y a au moins un site de production sélectionné, sinon renvoyer résultat minimal
    loc_prod = result.get("loc_prod")
    if not loc_prod:
        # Aucun site alloué -> retourner un résultat vide avec coûts nuls
        return {
            **result,
            "costs": {},
            "total_co2": 0,
            "production_data": all_production_data,
            "environment_data": all_enviro_data,
            "config": config,
            "seat_weight": seat_weight
        }
    # Calculer les coûts totaux pour ce scénario
    cost_results = calculate_total_costs({
        "source": result["source"],
        "target": result["target"],
        "value": result["value"],
        "production_totals": result["production_totals"],
        "market_totals": result["market_totals"],
        "loc_prod": result["loc_prod"],
        "loc_demand": result["loc_demand"],
        "cap": result["cap"],
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "include_supply": config.get("include_supply", True),
        "include_storage": config.get("include_storage", True)
    }, seat_weight=seat_weight)
    # Calcul de la pénalité de non-livraison
    penalties, total_penalty = calculer_penalite_non_livraison(result["market_totals"], demand)
    cost_results["penalties"] = penalties
    cost_results["total_penalty"] = total_penalty
    cost_results["total_cost_with_penalty"] = cost_results.get("total_cost", 0) + total_penalty
    # Calcul des émissions totales de CO₂ (production + transport)
    total_co2 = sum(
        calculate_lca_production_IFE_raw(result["value"][i], result["loc_prod"][result["source"][i]], seat_weight=seat_weight)["Climate Change"]
        + calculate_distribution_co2_emissions(result["loc_prod"][result["source"][i]], result["loc_demand"][result["target"][i]], result["value"][i], seat_weight=seat_weight)
        for i in range(len(result["source"]))
    )
    # Renvoyer le résultat complet du scénario
    return {
        **result,
        "costs": cost_results,
        "total_co2": total_co2,
        "production_data": all_production_data,
        "environment_data": all_enviro_data,
        "config": config,
        "seat_weight": seat_weight
    }

def compare_scenarios(results_dict, return_figures=False):
    """
    Compare plusieurs scénarios en produisant des graphiques barres pour le coût total, le CO₂ total et la production par site.
    :param results_dict: dict {nom_scenario: result_dict}
    :param return_figures: Si True, retourne les figures Plotly au lieu de les afficher.
    :return: Liste de figures Plotly si return_figures=True.
    """
    scenario_names = list(results_dict.keys())
    total_costs = [
        results_dict[name]["costs"].get("total_cost_with_penalty", results_dict[name]["costs"].get("total_cost", 0)) 
        for name in scenario_names
    ]
    total_co2 = [results_dict[name]["total_co2"] for name in scenario_names]
    # Préparer les données de production par site pour chaque scénario
    all_sites = list(results_dict[scenario_names[0]]['production_totals'].keys())
    production_per_site = {
        site: [results_dict[name]['production_totals'].get(site, 0) for name in scenario_names]
        for site in all_sites
    }
    # Créer la figure avec 3 sous-graphiques comparatifs
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Coût total (€)", "Émissions CO₂ totales (kg)", "Production par site"))
    fig.add_trace(go.Bar(x=scenario_names, y=total_costs, name="Coût (€)", marker_color="skyblue",
                         text=[f"{int(v/1000):,}k".replace(",", " ") for v in total_costs], textposition='auto'),
                  row=1, col=1)
    fig.add_trace(go.Bar(x=scenario_names, y=total_co2, name="CO₂ (kg)", marker_color="lightgreen",
                         text=[f"{int(v/1000):,}k".replace(",", " ") for v in total_co2], textposition='auto'),
                  row=1, col=2)
    for site in all_sites:
        fig.add_trace(go.Bar(x=scenario_names, y=production_per_site[site], name=site,
                             text=[round(v) for v in production_per_site[site]], textposition='auto'),
                      row=1, col=3)
    fig.update_layout(title_text="Comparaison des scénarios", height=500, width=1200, barmode='stack')
    if return_figures:
        return [fig]
    else:
        fig.show()
        return None

def display_sankey_for_scenarios(results_dict, return_figures=False):
    """
    Génère pour chaque scénario un diagramme de Sankey double (flux de production et flux de CO₂).
    :param results_dict: dict {nom_scenario: result_dict}
    :param return_figures: Si True, retourne les figures au lieu de les afficher.
    :return: Liste de figures Plotly si return_figures=True.
    """
    figures = []
    for name, result in results_dict.items():
        seat_weight = result.get("seat_weight", 130)
        # Diagramme Sankey pour la production
        sankey_prod = plot_production_sankey(
            source=result["source"], target=result["target"], value=result["value"],
            production_totals=result["production_totals"], market_totals=result["market_totals"],
            loc_prod=result["loc_prod"], loc_demand=result["loc_demand"], return_figure=True
        )
        # Diagramme Sankey pour les émissions CO₂
        co2_emissions = [
            calculate_distribution_co2_emissions(result["loc_prod"][s], result["loc_demand"][t], v, seat_weight=seat_weight)
            for s, t, v in zip(result["source"], result["target"], result["value"])
        ]
        production_co2 = [
            calculate_lca_production_IFE_raw(v, result["loc_prod"][s], seat_weight=seat_weight)["Climate Change"]
            for s, v in zip(result["source"], result["value"])
        ]
        sankey_co2 = plot_sankey_production_co2_emissions(
            source=result["source"], target=result["target"],
            co2_emissions=co2_emissions, production_co2_emissions=production_co2,
            value=result["value"], loc_prod=result["loc_prod"], loc_demand=result["loc_demand"],
            return_figure=True
        )
        # Combiner les deux diagrammes Sankey dans une figure
        fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]],
                            subplot_titles=(f"Flux de production – {name}", f"Émissions CO₂ – {name}"))
        # Ajouter les trace Sankey pour la production (col1) et CO2 (col2)
        for trace in sankey_prod.data:
            fig.add_trace(trace, row=1, col=1)
        for trace in sankey_co2.data:
            fig.add_trace(trace, row=1, col=2)
        fig.update_layout(height=600, width=1200)
        if return_figures:
            figures.append(fig)
        else:
            fig.show()
    return figures if return_figures else None
