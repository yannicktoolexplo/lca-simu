from line_production.line_production import run_simulation
from line_production.line_production_settings import lines_config
from line_production.production_engine import load_capacity_limits, load_fixed_and_variable_costs
from distribution.distribution_engine import load_freight_costs_and_demands
from utils.data_tools import plot_production_sankey
from economic.cost_engine import calculate_total_costs
from environment.environment_engine import (
    calculate_lca_production_IFE_raw,
    calculate_distribution_co2_emissions
)
from environment.environment_engine import (
    calculate_lca_indicators_usage_phase,
    calculate_lca_indicators_pers_eq,
    calculate_lca_indicators_total
)


def run_scenario(allocation_function, config):
    """
    Lance un scénario de simulation avec allocation flexible.
    :param allocation_function: fonction d'allocation (simple ou optimisation)
    :param config: dictionnaire de configuration générale
    :return: dictionnaire structuré avec tous les résultats
    """
    # 1. Simulation de la production
    all_production_data, all_enviro_data = run_simulation(config["lines_config"])

    max_production = {
        config["lines_config"][i]['location']: data['Total Seats made'][1][-1]
        for i, data in enumerate(all_production_data)
    }

    # 2. Capacités, coûts, logistique
    cap = load_capacity_limits(max_production)
    freight_costs, demand = load_freight_costs_and_demands()
    fixed_costs, variable_costs = load_fixed_and_variable_costs(freight_costs)

    # 3. Allocation de la production
    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = allocation_function(cap, demand)

    # 4. Calcul des coûts
    cost_results = calculate_total_costs({
        "source": source,
        "target": target,
        "value": value,
        "production_totals": production_totals,
        "market_totals": market_totals,
        "loc_prod": loc_prod,
        "loc_demand": loc_demand,
        "cap": cap,
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "include_supply": config.get("include_supply", True),
        "include_storage": config.get("include_storage", True)
    })

    # 5. Calcul CO2 total (production + transport)
    total_co2 = sum([
        calculate_lca_production_IFE_raw(value[i], loc_prod[source[i]])["Climate Change"] +
        calculate_distribution_co2_emissions(loc_prod[source[i]], loc_demand[target[i]], value[i])
        for i in range(len(source))
    ])

    # 6. Retour structuré
    return {
        "source": source,
        "target": target,
        "value": value,
        "production_totals": production_totals,
        "market_totals": market_totals,
        "loc_prod": loc_prod,
        "loc_demand": loc_demand,
        "cap": cap,
        "costs": cost_results,
        "total_co2": total_co2,
        "production_data": all_production_data,
        "environment_data": all_enviro_data,
        "config": config
    }

import plotly.graph_objects as go
import plotly.subplots as sp
from utils.data_tools import display_all_lca_indicators
from line_production.line_production_settings import lines_config


def compare_scenarios(results_dict):
    """
    Compare plusieurs scénarios à partir des résultats standardisés retournés par run_scenario.
    :param results_dict: dict nom_scenario → result (dict)
    """
    scenario_names = list(results_dict.keys())

    # Extraire les données comparables
    total_costs = [results_dict[name]["costs"]["total_cost"] for name in scenario_names]
    total_co2 = [results_dict[name]["total_co2"] for name in scenario_names]

    # Optionnel : production par site
    all_sites = list(results_dict[scenario_names[0]]['production_totals'].keys())
    production_per_site = {
        site: [results_dict[name]['production_totals'][site] for name in scenario_names]
        for site in all_sites
    }

    # Initialiser la figure Plotly
    fig = sp.make_subplots(rows=1, cols=3, subplot_titles=("Coût total (€)", "Émissions CO₂ totales (kg)", "Production par site"))

    # Coûts
    fig.add_trace(
        go.Bar(
            x=scenario_names,
            y=total_costs,
            name="Coût (€)",
            marker_color="skyblue",
            text=[f"{int(v/1000):,}k".replace(",", " ") for v in total_costs],
            textposition='auto'
        ),
        row=1, col=1
    )


    # CO2
    fig.add_trace(
        go.Bar(
            x=scenario_names,
            y=total_co2,
            name="CO₂ (kg)",
            marker_color="lightgreen",
            text=[f"{int(v/1000):,}k".replace(",", " ") for v in total_co2],
            textposition='auto'
        ),
        row=1, col=2
    )

    # Production par site (groupé en barres)
    for site in all_sites:
        fig.add_trace(
            go.Bar(
                x=scenario_names,
                y=production_per_site[site],
                name=site,
                text=[round(v) for v in production_per_site[site]],
                textposition='auto'
            ),
            row=1,
            col=3
        )

    fig.update_layout(title_text="Comparaison des scénarios", height=500, width=1200, barmode='stack')
    fig.show()

        # LCA unitaire pour France
    usage_fr = calculate_lca_indicators_usage_phase(1)
    pers_eq_fr = calculate_lca_indicators_pers_eq(1, site='France')
    total_fr = calculate_lca_indicators_total(1, site='France')

    indicators = ["Climate Change", "Resource use, fossils", "Water use"]
    unit_lca_data = [
        [usage_fr[i] for i in indicators],
        [pers_eq_fr[i] for i in indicators],
        [total_fr[i] for i in indicators],
    ]

    # Affichage du tableau LCA
    fake_config = [cfg for cfg in lines_config if cfg["location"] == "France"]
    fake_production_data = [{"Total Seats made": ([], [1])}]
    fake_enviro_data = [{}]  # ou une valeur factice

    display_all_lca_indicators(
    fake_production_data,
    fake_enviro_data,
    fake_config,
    {"France": 1}
    )   

from plotly.subplots import make_subplots
import plotly.graph_objects as go


from utils.data_tools import plot_production_sankey, plot_sankey_production_co2_emissions
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def display_sankey_for_scenarios(results_dict):
    """
    Affiche tous les diagrammes de Sankey (production et CO2) côte à côte dans une figure unique pour chaque scénario.
    :param results_dict: dict {nom_scenario: result_dict standardisé}
    """
    for name, result in results_dict.items():
        print(f"\n📊 Diagrammes Sankey – {name}")

        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{"type": "domain"}, {"type": "domain"}]],
            subplot_titles=("Flux de production", "Émissions CO₂")
        )

        # Sankey de production
        sankey_prod = plot_production_sankey(
            source=result["source"],
            target=result["target"],
            value=result["value"],
            production_totals=result["production_totals"],
            market_totals=result["market_totals"],
            loc_prod=result["loc_prod"],
            loc_demand=result["loc_demand"],
            return_figure=True
        )

        for trace in sankey_prod.data:
            fig.add_trace(trace, row=1, col=1)

        # Sankey CO2
        co2_emissions = [
            calculate_distribution_co2_emissions(result["loc_prod"][s], result["loc_demand"][t], v)
            for s, t, v in zip(result["source"], result["target"], result["value"])
        ]
        production_co2_emissions = [
            calculate_lca_production_IFE_raw(v, result["loc_prod"][s])["Climate Change"]
            for s, v in zip(result["source"], result["value"])
        ]

        sankey_co2 = plot_sankey_production_co2_emissions(
            source=result["source"],
            target=result["target"],
            co2_emissions=co2_emissions,
            production_co2_emissions=production_co2_emissions,
            value=result["value"],
            loc_prod=result["loc_prod"],
            loc_demand=result["loc_demand"],
            return_figure=True
        )

        for trace in sankey_co2.data:
            fig.add_trace(trace, row=1, col=2)

        fig.update_layout(title_text=f"Diagrammes Sankey – {name}", height=600, width=1200)
        fig.show()
