import os
import math
import copy

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import line_production
from optimization_engine import run_supply_chain_optimization, run_supply_chain_optimization_minimize_co2
from environment_engine import calculate_distribution_co2_emissions, calculate_production_co2_emissions

from data_tools import round_to_nearest_significant

def plot_stock_levels(stock_data, total_seats_data):
    """Plot stock levels using Plotly."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=["Stock Levels Over Time", "Total Seats Made Over Time"])

    for label, (time_vector, values) in stock_data.items():
        fig.add_trace(go.Scatter(x=time_vector, y=values, mode='lines+markers', name=label), row=1, col=1)

    fig.add_trace(go.Scatter(x=total_seats_data[0], y=total_seats_data[1], mode='lines+markers', name='Total Seats made'), row=2, col=1)

    fig.update_layout(height=800, title_text="Stock Levels and Total Seats Made Over Time", showlegend=True)
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Stock Level", row=1, col=1)
    fig.update_yaxes(title_text="Total Seats Made", row=2, col=1)

    fig.show()

def plot_resource_consumption(data_enviro):
    """Plot resource consumption using Plotly."""
    fig_conso = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("Electrical Consumption", "Water Consumption", "Mineral and Metal Used"))

    fig_conso.add_trace(go.Scatter(x=data_enviro['Electrical Consumption'][0], y=data_enviro['Electrical Consumption'][1], fill='tozeroy', name='Electrical Consumption', fillcolor='rgba(0, 0, 255, 0.2)', marker={'color': 'rgba(0, 0, 255, 1)'}), row=1, col=1)
    fig_conso.add_trace(go.Scatter(x=data_enviro['Water Consumption'][0], y=data_enviro['Water Consumption'][1], fill='tozeroy', name='Water Consumption', fillcolor='rgba(0, 255, 0, 0.2)', marker={'color': 'rgba(0, 255, 0, 1)'}), row=2, col=1)
    fig_conso.add_trace(go.Scatter(x=data_enviro['Mineral and Metal Used'][0], y=data_enviro['Mineral and Metal Used'][1], fill='tozeroy', name='Mineral and Metal Used', fillcolor='rgba(255, 0, 0, 0.2)', marker={'color': 'rgba(255, 0, 0, 1)'}), row=3, col=1)

    fig_conso.update_layout(height=900, title_text="Resource Consumption over Time", showlegend=False)
    fig_conso.update_xaxes(title_text="Time")
    fig_conso.update_yaxes(title_text="Consumption")

    fig_conso.show()

def plot_total_resource_consumption(data_enviro):
    """Plot total resource consumption using Plotly."""
    total_electrical = sum(data_enviro['Electrical Consumption'][1])
    total_water = sum(data_enviro['Water Consumption'][1])
    total_minerals = sum(data_enviro['Mineral and Metal Used'][1])

    categories = ['Electrical Consumption', 'Water Consumption', 'Mineral and Metal Used']
    totals = [total_electrical, total_water, total_minerals]

    fig = go.Figure(data=[go.Bar(x=categories, y=totals, marker_color=['rgba(0, 0, 255, 0.6)', 'rgba(0, 255, 0, 0.6)', 'rgba(255, 0, 0, 0.6)'])])
    fig.update_layout(title_text="Total Resource Consumption", xaxis_title="Resource Type", yaxis_title="Total Consumption")

    fig.show()

def plot_production_co2_emissions(production_co2_totals):
    """Plot production CO2 emissions by country using Plotly."""
    countries = list(production_co2_totals.keys())
    co2_emissions = list(production_co2_totals.values())

    # Calculer les émissions globales
    total_emissions = sum(co2_emissions)
    countries.append('Global Total')
    co2_emissions.append(total_emissions)

    fig = go.Figure(data=[go.Bar(x=countries, y=co2_emissions, marker_color='rgba(255, 0, 0, 0.6)')])

    # Ajouter des annotations pour afficher les totaux des émissions de CO2
    annotations = []
    for i, value in enumerate(co2_emissions):
        annotations.append(dict(x=countries[i], y=value, text=f'{value:.2f} kg', showarrow=False, yshift=10))

    fig.update_layout(title_text="Production CO2 Emissions by Country", xaxis_title="Country", yaxis_title="CO2 Emissions (kg)", annotations=annotations)

    fig.show()

def calculate_capacity_limits(data):
    """Calculate the capacity limits for each plant based on the total seats made."""
    nos_texas_low = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_texas_high = math.ceil(1.2 * data['Total Seats made'][1][-1])
    nos_california_low = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_california_high = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_UK_low = math.ceil(0.15 * data['Total Seats made'][1][-1])
    nos_UK_high = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_france_low = math.ceil(0.45 * data['Total Seats made'][1][-1])
    nos_france_high = math.ceil(0.9 * data['Total Seats made'][1][-1])

    capacity_limits = {
        'Texas': (nos_texas_low, nos_texas_high),
        'California': (nos_california_low, nos_california_high),
        'UK': (nos_UK_low, nos_UK_high),
        'France': (nos_france_low, nos_france_high)
    }
    return capacity_limits


def main_function():
    """Main function to run the analysis and plots."""
    
    # Définir le chemin absolu du répertoire courant
    absolute_path = os.path.dirname(__file__)

    # Charger les données de production et environnementales
    data = line_production.get_data()
    data_enviro = line_production.get_data_enviro()

    # Collectez les données depuis line_production
    production_data = line_production.get_data()
    enviro_data = line_production.get_data_enviro()

    # Utilisez les données collectées dans le reste du script
    seat_stock = production_data['Seat Stock']
    frame_data = production_data['Frame Data']
    armrest_data = production_data['Armrest Data']
    foam_stock = production_data['Foam Stock']
    fabric_stock = production_data['Fabric Stock']
    paint_stock = production_data['Paint Stock']
    total_seats_made = production_data['Total Seats made']
    aluminium_stock = production_data['Aluminium Stock']

    electrical_consumption = enviro_data['Electrical Consumption']
    water_consumption = enviro_data['Water Consumption']
    mineral_metal_used = enviro_data['Mineral and Metal Used']
    
    # Préparer les données de stock pour chaque composant sauf 'Total Seats made'
    stock_data = {
        'Seat Stock': (line_production.time, line_production.data2),
        'Frame Data': (line_production.time_frame, line_production.frame_data),
        'Armrest Data': (line_production.time_armrest, line_production.armrest_data),
        'Foam Stock': (line_production.time_foam, line_production.foam_stock_data),
        'Fabric Stock': (line_production.time_fabric, line_production.fabric_stock_data),
        'Paint Stock': (line_production.time_paint, line_production.paint_stock_data),
        'Aluminium Stock': (line_production.time_aluminium, line_production.aluminium_stock_data)
    }

    # Préparer les données pour 'Total Seats made'
    total_seats_data = (line_production.time, line_production.data1)
    
    # Plot des niveaux de stock et du total des sièges produits
    plot_stock_levels(stock_data, total_seats_data)
    
    # Plot de la consommation des ressources
    plot_resource_consumption(data_enviro)
    
    # Plot de la consommation totale des ressources
    plot_total_resource_consumption(data_enviro)

    # Calculer les limites de capacité basées sur les données de production
    capacity_limits = calculate_capacity_limits(data)

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
    co2_emissions = [calculate_distribution_co2_emissions(loc_prod[s], loc_demand[t], value[i]) for i, (s, t) in enumerate(zip(source, target))]
    production_co2_emissions = [calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

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
    plot_production_co2_emissions(production_co2_totals)



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
    co2_emissions = [calculate_distribution_co2_emissions(loc_prod[s], loc_demand[t], value[i]) for i, (s, t) in enumerate(zip(source, target))]
    production_co2_emissions = [calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

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
    plot_production_co2_emissions(production_co2_totals)

if __name__ == '__main__':
    main_function()
