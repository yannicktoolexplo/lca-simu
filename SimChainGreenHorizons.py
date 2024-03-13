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

import line_production
from SupplyChainOptimization import run_supply_chain_optimization

from data_tools import plot_surface, visualize_stock_levels, plot_co2_emissions, round_to_nearest_significant, plot_bar

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
    data = line_production.get_data()

    # Get the last value of the total seats made
    number_of_seat = data['Total Seats made'][1][-1]

    # Round the last value to the nearest significant value
    rounded_value = round_to_nearest_significant(number_of_seat)

    # Calculate the ytick parameter for the visualization of stock levels
    ytick_param = rounded_value / (rounded_value/(rounded_value/10))

    # Run the supply chain optimization function
    fig_opti, fig2_opti, value, cap = run_supply_chain_optimization()

    # Show the optimization figure
    fig_opti.show()

    # Show the CO2 emissions figure
    # fig2_opti.show()

    # Visualize the stock levels
    # visualize_stock_levels(data, ytick_param)

    # Plot the CO2 emissions
    # plot_co2_emissions(os.path.join(absolute_path, 'data/CO2_emissions.csv'))

    # Plot a bar chart
    data_bars = [1, 2, 3, 4, 5]
    modes = ['Car', 'Bus', 'Train', 'Plane', 'Bike']
    plot_bar(data_bars, modes, xlabel='Transportation Mode', ylabel='CO2 Emissions (kg CO2e)', title='Total CO2 Emissions by Transportation Mode')

    # Load the historical data
    historical_data = data['Total Seats made'][1]

    # Perform the ARIMA modeling
    arima_model = ARIMA(historical_data, order=(1, 1, 1))
    arima_model_fit = arima_model.fit()

    # Forecast the future data points
    num_future_points = 50
    arima_predictions = arima_model_fit.forecast(steps=num_future_points)

    # Perform the Grey Theory modeling
    grey_theory = GreyTheory()
    grey_predictions = grey_theory.grey_model(historical_data, num_future_points)

    # Plot the results
    plt.figure(figsize=(12, 6))
    plt.plot(historical_data, label='Historical Data')
    plt.plot(arima_predictions, label='ARIMA Predictions')
    plt.plot(grey_predictions, label='Grey Theory Predictions')
    plt.legend()
    plt.show()

if __name__ == '__main__':
    main_function()
