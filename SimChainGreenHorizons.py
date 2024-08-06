import os
import math
import copy

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import line_production
import production_engine
from optimization_engine import run_supply_chain_optimization, run_supply_chain_optimization_minimize_co2
import environment_engine 
import data_tools

def main_function():
    """Main function to run the analysis and plots."""
    
    # Configuration personnalisée
    custom_config = line_production.FactoryConfig(
        hours=8,  # Par exemple, changer les heures de travail par jour à 10
        days=21,  # Par exemple, changer le nombre de jours ouvrables à 30
        initial_aluminium=150,  # Par exemple, changer le stock initial d'aluminium
        initial_foam=150,  # Par exemple, changer le stock initial de mousse
        initial_fabric=150,  # Par exemple, changer le stock initial de tissu
        initial_paint=150  # Par exemple, changer le stock initial de peinture
    )

    # Exécution de la simulation avec la configuration personnalisée
    seat_factory = line_production.run_simulation(custom_config)

    # Collectez les données depuis line_production
    production_data = line_production.get_data(seat_factory)
    total_seats_made = production_data['Total Seats made'][1][-1]

    # Calcul des indicateurs environnementaux
    # enviro_data = environment_engine.calculate_lca_indicators(total_seats_made)
    enviro_data = environment_engine.calculate_lca_indicators_pers_eq(total_seats_made)

    # Plot des indicateurs environnementaux
    data_tools.plot_lca_indicators(enviro_data)

    # Préparer les données de stock pour chaque composant sauf 'Total Seats made'
    stock_data = {
        'Seat Stock': production_data['Seat Stock'],
        'Frame Data': production_data['Frame Data'],
        'Armrest Data': production_data['Armrest Data'],
        'Foam Stock': production_data['Foam Stock'],
        'Fabric Stock': production_data['Fabric Stock'],
        'Paint Stock': production_data['Paint Stock'],
        'Aluminium Stock': production_data['Aluminium Stock']
    }

    # Préparer les données pour 'Total Seats made'
    total_seats_data = production_data['Total Seats made']
    
    # Plot des niveaux de stock et du total des sièges produits
    data_tools.plot_stock_levels(stock_data, total_seats_data)
    
    # Plot de la consommation des ressources
    # data_tools.plot_resource_consumption(enviro_data)
    
    # Plot de la consommation totale des ressources
    # data_tools.plot_total_resource_consumption(enviro_data)

    # Calculer les limites de capacité basées sur les données de production
    capacity_limits = production_engine.calculate_capacity_limits(production_data)

    # Exécuter l'optimisation de la chaîne d'approvisionnement avec les limites de capacité calculées
    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_supply_chain_optimization(capacity_limits)

    # Préparer les étiquettes et couleurs pour le diagramme Sankey de la production
    node_labels = [f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))]
    node_labels += [f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]
    link_labels = [f"{v:,.0f} Units" for v in value]

    base_colors = {
        'Texas': 'rgba(255, 127, 14, 0.8)',
        'California': 'rgba(255, 127, 14, 0.8)',
        'UK': 'rgba(148, 103, 189, 0.8)',
        'France': 'rgba(214, 39, 40, 0.8)',
    }

    target_colors = {
        'USA': 'rgba(255, 127, 14, 0.5)',
        'Canada': 'rgba(255, 215, 0, 0.5)',
        'Japan': 'rgba(44, 160, 44, 0.5)',
        'Brazil': 'rgba(31, 119, 180, 0.5)',
        'France': 'rgba(214, 39, 40, 0.5)'
    }

    production_colors = [base_colors[place] for place in loc_prod]
    market_colors = [target_colors[place] for place in loc_demand]
    node_colors = production_colors + market_colors
    link_colors = [market_colors[i] for i in target]

    # Créer et afficher le diagramme Sankey pour la production
    fig_prod = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node_labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=[i + len(loc_prod) for i in target],
            value=value,
            label=link_labels,
            color=link_colors
        ))])

    # Calculer les émissions de CO2 pour le transport et la production
    co2_emissions = [environment_engine.calculate_distribution_co2_emissions(loc_prod[s], loc_demand[t], value[i]) for i, (s, t) in enumerate(zip(source, target))]
    production_co2_emissions = [environment_engine.calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

    production_co2_totals = {location: 0 for location in loc_prod}
    market2_totals = {location: 0 for location in loc_demand}

    # Agréger les émissions de CO2 par lieu de production et marché
    for s, t, p, v in zip(source, target, production_co2_emissions, value):
        production_co2_totals[loc_prod[s]] += p
        market2_totals[loc_demand[t]] += v

    node2_labels = [f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))]
    node2_labels += [f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

    link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

    # Créer et afficher le diagramme Sankey pour les émissions de CO2
    fig_CO2 = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node2_labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=[i + len(loc_prod) for i in target],
            value=co2_emissions,
            label=link2_labels,
            color=link_colors
        ))])

    # Afficher les diagrammes Sankey
    fig_prod.show()
    fig_CO2.show()

    # Plot des émissions de CO2 de production par pays
    data_tools.plot_production_co2_emissions(production_co2_totals)



########################### CO2_opti

 # Exécuter l'optimisation de la chaîne d'approvisionnement avec les limites de capacité calculées
    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_supply_chain_optimization_minimize_co2(capacity_limits)

    # Préparer les étiquettes et couleurs pour le diagramme Sankey de la production
    node_labels = [f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))]
    node_labels += [f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]
    link_labels = [f"{v:,.0f} Units" for v in value]

    base_colors = {
        'Texas': 'rgba(255, 127, 14, 0.8)',
        'California': 'rgba(255, 127, 14, 0.8)',
        'UK': 'rgba(148, 103, 189, 0.8)',
        'France': 'rgba(214, 39, 40, 0.8)',
    }

    target_colors = {
        'USA': 'rgba(255, 127, 14, 0.5)',
        'Canada': 'rgba(255, 215, 0, 0.5)',
        'Japan': 'rgba(44, 160, 44, 0.5)',
        'Brazil': 'rgba(31, 119, 180, 0.5)',
        'France': 'rgba(214, 39, 40, 0.5)'
    }

    production_colors = [base_colors[place] for place in loc_prod]
    market_colors = [target_colors[place] for place in loc_demand]
    node_colors = production_colors + market_colors
    link_colors = [market_colors[i] for i in target]

    # Créer et afficher le diagramme Sankey pour la production
    fig_prod = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node_labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=[i + len(loc_prod) for i in target],
            value=value,
            label=link_labels,
            color=link_colors
        ))])

    # Calculer les émissions de CO2 pour le transport et la production
    co2_emissions = [environment_engine.calculate_distribution_co2_emissions(loc_prod[s], loc_demand[t], value[i]) for i, (s, t) in enumerate(zip(source, target))]
    production_co2_emissions = [environment_engine.calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

    production_co2_totals = {location: 0 for location in loc_prod}
    market2_totals = {location: 0 for location in loc_demand}

    # Agréger les émissions de CO2 par lieu de production et marché
    for s, t, p, v in zip(source, target, production_co2_emissions, value):
        production_co2_totals[loc_prod[s]] += p
        market2_totals[loc_demand[t]] += v

    node2_labels = [f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))]
    node2_labels += [f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

    link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

    # Créer et afficher le diagramme Sankey pour les émissions de CO2
    fig_CO2 = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node2_labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=[i + len(loc_prod) for i in target],
            value=co2_emissions,
            label=link2_labels,
            color=link_colors
        ))])

    # Afficher les diagrammes Sankey
    fig_prod.show()
    fig_CO2.show()

    # Plot des émissions de CO2 de production par pays
    data_tools.plot_production_co2_emissions(production_co2_totals)

if __name__ == '__main__':
    main_function()
