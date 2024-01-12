
import os
from greytheory import GreyTheory
import line_production
from SupplyChainOptimization import run_supply_chain_optimization
import matplotlib.pyplot as plt


import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from greytheory import GreyTheory
grey = GreyTheory()

from data_tools import plot_surface, visualize_stock_levels, plot_co2_emissions, round_to_nearest_significant

import pandas as pd

def main_function():
    # Your main function logic

    absolute_path = os.path.dirname(__file__)

    # Example usage of the plotting functions from data_tools.py
    
    data, total_factory_lines = line_production.get_data()
    number_of_seat = data['Total Seats made'][1][-1] 
    rounded_value = round_to_nearest_significant(number_of_seat)
    ytick_param = rounded_value / (rounded_value/(rounded_value/10))


    # visualize_stock_levels(data, ytick_param)


    fig_opti, fig2_opti, source, target, value, node_labels = run_supply_chain_optimization()

    # Show the figure
    # fig_opti.show()


    # Show the figure
    # fig2_opti.show()

    #########################################################################################################

    # Original data: Number of seats
    original_data = data['Total Seats made'][1]
    original_data_np = np.array(original_data)
    print(original_data)

    # ARIMA Model Implementation for multiple future points
    num_future_points = 20  # Number of points you want to predict
    arima_model = ARIMA(original_data, order=(1, 1, 1))
    arima_model_fit = arima_model.fit()
    arima_predictions = arima_model_fit.forecast(steps=num_future_points)

    gm11 = grey.gm11

    # Recent subset of data for GM(1,1)
    subset_size = int(len(original_data_np) * 0.2)  # 20% of the data
    recent_data_subset = original_data_np[-subset_size:]

    # Predicting multiple future points with GM(1,1)
    # gm11.clean_forecasted()  # Clear previous data patterns
    current_data = list(recent_data_subset)
    
    for value in current_data:
        gm11.add_pattern(value, "a")

    gm_predictions = []

    for i in range(num_future_points):

        gm11.period = i
        gm11.forecast()
        next_value = gm11.analyzed_results[-1].forecast_value
        gm_predictions.append(next_value)
        current_data.append(next_value)  # Append prediction for the next iteration
        # gm11.clean_forecasted()  # Clear for the next iteration

    # Plotting
    plt.figure(figsize=(12, 6))
    extended_original_data = original_data + arima_predictions.tolist()
    plt.plot(extended_original_data, marker='x', linestyle='--', color='gray', label='Original Data with ARIMA Predictions')
    plt.scatter(range(len(original_data), len(original_data) + num_future_points), arima_predictions, color='red', label='ARIMA Predictions')

    # Assuming you want to plot the recent subset along with GM(1,1) predictions
    shift_index = len(original_data) - len(recent_data_subset)
    shifted_recent_indices = [i + shift_index for i in range(len(recent_data_subset))]
    plt.plot(shifted_recent_indices, recent_data_subset, marker='o', linestyle='-', color='blue', label='Recent Data for GM(1,1)')
    plt.scatter(range(len(original_data), len(original_data) + num_future_points), gm_predictions, color='green', label='GM(1,1) Predictions')

    plt.title("Comparison of ARIMA and GM(1,1) Predictions with Recent Data Subset")
    plt.xlabel("Data Points")
    plt.ylabel("Values")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == '__main__':

    main_function()
    
   

   