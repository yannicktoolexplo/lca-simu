
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
    original_data=data['Total Seats made'][1]
    original_data_np = np.array(original_data)
    print(original_data)

    # ARIMA Model Implementation
    # 1. Fit ARIMA(1,1,1) model
    arima_model = ARIMA(original_data, order=(1, 1, 1))
    arima_model_fit = arima_model.fit()
    arima_prediction = arima_model_fit.forecast(steps=1)[0]

    # Grey Theory GM(1,1) Model Implementation
    class GreyMath:
        def solve_equations(self, equations, equals):
            transposed_equations = np.asarray(equations).T.tolist()
            square_matrix = np.dot(transposed_equations, equations)
            bx_y = np.dot(transposed_equations, equals)
            return np.linalg.solve(square_matrix, bx_y).tolist()

    class GreyLib:
        def __init__(self, alpha=0.5):
            self.alpha = alpha
            self.grey_math = GreyMath()

        def ago(self, patterns):
            ago_boxes = [] 
            z_boxes   = []
            pattern_index = 0
            for x_patterns in patterns:
                x_ago   = []
                sum     = 0.0
                x_index = 0
                for x_value in x_patterns:
                    sum += x_value
                    x_ago.append(sum)
                    if pattern_index == 0 and x_index > 0:
                        z_value = (self.alpha * sum) + ((1 - self.alpha) * x_ago[x_index - 1])
                        z_boxes.append(z_value)
                    x_index += 1
                ago_boxes.append(x_ago)
                pattern_index += 1
            return (ago_boxes, z_boxes)

        def forecast(self, data):
            ago_result = self.ago([data])
            z_boxes = ago_result[1]
            factors = []
            for z in z_boxes:
                factors.append([-z, 1])
            Y = data[1:]
            a, b = self.grey_math.solve_equations(factors, Y)
            x1 = data[0]
            next_value = (1 - np.exp(a)) * (x1 - (b / a)) * np.exp(-a * len(data))
            return next_value


    # GM11
    gm11 = grey.gm11

    # Recent subset of data for gm11
    subset_size = int(len(original_data_np) * 0.2)  # 20% of the data
    recent_data_subset = original_data_np[-subset_size:]

    # To try customized alpha for IAGO of Z.
    gm11.alpha = 0.5
    
    # Applying GM(1,1) on the most recent subset of data
    for value in recent_data_subset:
        gm11.add_pattern(value, "a")
    gm11.forecast()
    gm_prediction_recent_subset = [gm11.analyzed_results[-1].forecast_value]
    print(gm_prediction_recent_subset)

    # Plotting
    plt.figure(figsize=(12, 6))
    extended_original_data = original_data + [arima_prediction]
    plt.plot(extended_original_data, marker='x', linestyle='--', color='gray', label='Original Data with ARIMA Prediction')
    plt.scatter(len(original_data), arima_prediction, color='red', label='ARIMA Prediction')
    shift_index = len(original_data) - len(recent_data_subset)
    shifted_recent_indices = [i + shift_index for i in range(len(recent_data_subset))]
    plt.plot(shifted_recent_indices, recent_data_subset, marker='o', linestyle='-', color='blue', label='Recent Data for GM(1,1)')
    plt.scatter(len(original_data), gm_prediction_recent_subset, color='green', label='GM(1,1) Prediction')
    plt.title("Comparison of ARIMA Prediction and GM(1,1) with Recent Data Subset")
    plt.xlabel("Data Points")
    plt.ylabel("Values")
    plt.legend()
    plt.grid(True)
    plt.show()    


if __name__ == '__main__':

    main_function()
    
   

   