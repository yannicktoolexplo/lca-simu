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



    # Get the last value of the total seats made
    number_of_seat = data['Total Seats made'][1][-1]
    electric_consum = data_enviro['Electrical Consumption'][1][-1]

    # Round the last value to the nearest significant value
    rounded_value = round_to_nearest_significant(number_of_seat)
    rounded_value2 = round_to_nearest_significant(electric_consum)
    rounded_value2 = math.ceil(electric_consum)

    # Calculate the ytick parameter for the visualization of stock levels
    ytick_param = rounded_value / (rounded_value/(rounded_value/10))
    # ytick_param_enviro = rounded_value2 / (rounded_value2/(rounded_value2/10))
    ytick_param_enviro = rounded_value2

    # Run the supply chain optimization function
    fig_opti, fig2_opti, value, cap = run_supply_chain_optimization()

    # Show the optimization figure
    fig_opti.show()

    # Show the CO2 emissions figure
    fig2_opti.show()

    # Visualize the stock levels
    # fig, ax = plt.subplots()
    # for label, (time_vector, values) in data.items():
    #     plotting_of_data(ax, time_vector, values, ytick_param, label)

    # plt.show()

    # Création des subplots
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        subplot_titles=("Electrical Consumption", "Water Consumption", "Mineral and Metal Used"))

    # Electrical Consumption Plot
    fig.add_trace(go.Scatter(x=data_enviro['Electrical Consumption'][0], y=data_enviro['Electrical Consumption'][1], fill='tozeroy', name='Electrical Consumption', fillcolor='rgba(0, 0, 255, 0.2)', marker={'color': 'rgba(0, 0, 255, 1)'}), row=1, col=1)

    # Water Consumption Plot
    fig.add_trace(go.Scatter(x=data_enviro['Water Consumption'][0], y=data_enviro['Water Consumption'][1], fill='tozeroy', name='Water Consumption', fillcolor='rgba(0, 255, 0, 0.2)', marker={'color': 'rgba(0, 255, 0, 1)'}), row=2, col=1)

    # Mineral and Metal Used Plot
    fig.add_trace(go.Scatter(x=data_enviro['Mineral and Metal Used'][0], y=data_enviro['Mineral and Metal Used'][1], fill='tozeroy', name='Mineral and Metal Used', fillcolor='rgba(255, 0, 0, 0.2)', marker={'color': 'rgba(255, 0, 0, 1)'}), row=3, col=1)

    # Mise à jour de la disposition
    fig.update_layout(height=900, title_text="Resource Consumption over Time", showlegend=False)
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Consumption")

    # Affichage du graphique
    fig.show()

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

   


if __name__ == '__main__':
    main_function()
