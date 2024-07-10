# SimChainGreenHorizons.py

import os
import math
import copy

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from grey_modeling import GreyTheory
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import line_production
from optimization_engine import run_supply_chain_optimization
from environment_engine import calculate_co2_emissions, calculate_production_co2_emissions

from data_tools import plot_surface, plotting_of_data, plot_co2_emissions, round_to_nearest_significant, plot_bar

# This function rounds a number to the nearest multiple of the power of 10
def round_to_nearest_significant(number):
    if number == 0:
        return 0
    power = 10 ** math.floor(math.log10(abs(number)))
    return power * 10 if number >= power * 5 else power

def main_function():
    # Get the absolute path of the current file
    absolute_path = os.path.dirname(__file__)

    # Load the data
    data  = line_production.get_data()
    data_enviro = line_production.get_data_enviro()
    data_set = data['Total Seats made'][1]



    # # Get the last value of the total seats made
    # number_of_seat = data['Total Seats made'][1][-1]
    # electric_consum = data_enviro['Electrical Consumption'][1][-1]

    # # Round the last value to the nearest significant value
    # rounded_value = round_to_nearest_significant(number_of_seat)
    # rounded_value2 = round_to_nearest_significant(electric_consum)
    # rounded_value2 = math.ceil(electric_consum)

    # # Calculate the ytick parameter for the visualization of stock levels
    # ytick_param = rounded_value / (rounded_value/(rounded_value/10))
    # # ytick_param_enviro = rounded_value2 / (rounded_value2/(rounded_value2/10))


    # # Visualize the stock levels
    # fig_old, ax = plt.subplots()
    # for label, (time_vector, values) in data.items():
    #     plotting_of_data(ax, time_vector, values, ytick_param, label)

    # plt.show()


    # Function to plot stock levels using Plotly
    def plot_stock_levels(stock_data, total_seats_data):
        # Create a figure with two rows
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=["Stock Levels Over Time", "Total Seats Made Over Time"])

        # Plot all stock data except 'Total Seats made' in the first row
        for label, (time_vector, values) in stock_data.items():
            fig.add_trace(go.Scatter(x=time_vector, y=values, mode='lines+markers', name=label), row=1, col=1)
        
        # Plot 'Total Seats made' in the second row
        fig.add_trace(go.Scatter(x=total_seats_data[0], y=total_seats_data[1], mode='lines+markers', name='Total Seats made'), row=2, col=1)

        # Update layout
        fig.update_layout(height=800, title_text="Stock Levels and Total Seats Made Over Time", showlegend=True)
        fig.update_xaxes(title_text="Time")
        fig.update_yaxes(title_text="Stock Level", row=1, col=1)
        fig.update_yaxes(title_text="Total Seats Made", row=2, col=1)

        fig.show()

    # Plot stock levels using Plotly
    stock_data = {
        'Seat Stock': (line_production.time, line_production.data2),
        'Frame Data': (line_production.time_frame, line_production.frame_data),
        'Armrest Data': (line_production.time_armrest, line_production.armrest_data),
        'Foam Stock': (line_production.time_foam, line_production.foam_stock_data),
        'Fabric Stock': (line_production.time_fabric, line_production.fabric_stock_data),
        'Paint Stock': (line_production.time_paint, line_production.paint_stock_data),
        'Aluminium Stock': (line_production.time_aluminium, line_production.aluminium_stock_data)
    }
    total_seats_data = (line_production.time, line_production.data1)    
    plot_stock_levels(stock_data, total_seats_data)

    # Création des subplots
    fig_conso = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        subplot_titles=("Electrical Consumption", "Water Consumption", "Mineral and Metal Used"))

    # Electrical Consumption Plot
    fig_conso.add_trace(go.Scatter(x=data_enviro['Electrical Consumption'][0], y=data_enviro['Electrical Consumption'][1], fill='tozeroy', name='Electrical Consumption', fillcolor='rgba(0, 0, 255, 0.2)', marker={'color': 'rgba(0, 0, 255, 1)'}), row=1, col=1)

    # Water Consumption Plot
    fig_conso.add_trace(go.Scatter(x=data_enviro['Water Consumption'][0], y=data_enviro['Water Consumption'][1], fill='tozeroy', name='Water Consumption', fillcolor='rgba(0, 255, 0, 0.2)', marker={'color': 'rgba(0, 255, 0, 1)'}), row=2, col=1)

    # Mineral and Metal Used Plot
    fig_conso.add_trace(go.Scatter(x=data_enviro['Mineral and Metal Used'][0], y=data_enviro['Mineral and Metal Used'][1], fill='tozeroy', name='Mineral and Metal Used', fillcolor='rgba(255, 0, 0, 0.2)', marker={'color': 'rgba(255, 0, 0, 1)'}), row=3, col=1)

    # Mise à jour de la disposition
    fig_conso.update_layout(height=900, title_text="Resource Consumption over Time", showlegend=False)
    fig_conso.update_xaxes(title_text="Time")
    fig_conso.update_yaxes(title_text="Consumption")

    # Affichage du graphique
    fig_conso.show()

    # Calcul des totaux pour chaque type de consommation
    total_electrical = sum(data_enviro['Electrical Consumption'][1])
    total_water = sum(data_enviro['Water Consumption'][1])
    total_minerals = sum(data_enviro['Mineral and Metal Used'][1])

    # Préparation des données pour le diagramme en barres
    categories = ['Electrical Consumption', 'Water Consumption', 'Mineral and Metal Used']
    totals = [total_electrical, total_water, total_minerals]

    # Création du diagramme en barres
    fig = go.Figure(data=[go.Bar(x=categories, y=totals, marker_color=['rgba(0, 0, 255, 0.6)', 'rgba(0, 255, 0, 0.6)', 'rgba(255, 0, 0, 0.6)'])])

    # Mise à jour de la disposition
    fig.update_layout(title_text="Total Resource Consumption", xaxis_title="Resource Type", yaxis_title="Total Consumption")

    # Affichage du graphique
    fig.show()

    # Plot the CO2 emissions
    # plot_co2_emissions(os.path.join(absolute_path, 'data/CO2_emissions.csv'))

    # Plot a bar chart
    # data_bars = [1, 2, 3, 4, 5]
    # modes = ['Car', 'Bus', 'Train', 'Plane', 'Bike']
    # plot_bar(data_bars, modes, xlabel='Transportation Mode', ylabel='CO2 Emissions (kg CO2e)', title='Total CO2 Emissions by Transportation Mode')



    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_supply_chain_optimization()

        # Update node labels to include total units
    node_labels = [f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))]
    node_labels += [f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

    # Labels for links indicating the units exchanged
    link_labels = [f"{v:,.0f} Units" for v in value]

    # Define the base colors for production nodes
    base_colors = {
        'Texas': 'rgba(255, 127, 14, 0.8)',      # Orange
        'California': 'rgba(255, 127, 14, 0.8)',  # Orange
        'UK': 'rgba(148, 103, 189, 0.8)',     # Purple
        'France': 'rgba(214, 39, 40, 0.8)',    # Red
    }

    # Define the colors for market nodes (can be the same or different)
    # Use the base colors for production nodes and create lighter versions for market nodes
    production_colors = [base_colors[place] for place in loc_prod]
    target_colors = {
        'USA': 'rgba(255, 127, 14, 0.5)',      # Orange
        'Canada': 'rgba(255, 215, 0, 0.5)',  # Yellow
        'Japan': 'rgba(44, 160, 44, 0.5)',     # Green
        'Brazil': 'rgba(31, 119, 180, 0.5)',    # Blue
        'France': 'rgba(214, 39, 40, 0.5)'    # Red
    }
    market_colors = [target_colors[place] for place in loc_demand]

    # Combine the colors for all nodes
    node_colors = production_colors + market_colors

    # Use the market colors for links
    link_colors = [market_colors[i] for i in target]

    # Create the Sankey diagram
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


    # Calculate CO2 emissions for each link
    co2_emissions = [calculate_co2_emissions(loc_demand[s], value[i]) for i, s in enumerate(source)]

    # Assuming 'value' represents the quantity produced
    production_co2_emissions = [calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

    # Calculate total CO2 emissions for each production and market node
    production_co2_totals = {location: 0 for location in loc_prod}
    market2_totals = {location: 0 for location in loc_demand}

    for s, t, p, v in zip(source, target, production_co2_emissions, value):
        production_co2_totals[loc_prod[s]] += p
        market2_totals[loc_demand[t]] += v

    # Update node labels to include total CO2 emissions
    node2_labels = [f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))]
    node2_labels += [f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

    # Update link labels to include CO2 emissions
    link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

    # Create the Sankey diagram with updated link labels
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

    # Show the optimization figure
    fig_prod.show()

    # Show the CO2 emissions figure
    fig_CO2.show()

if __name__ == '__main__':
    main_function()
