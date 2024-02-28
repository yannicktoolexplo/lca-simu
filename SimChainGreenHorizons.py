
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

# from greytheory import GreyTheory
import line_production
from SupplyChainOptimization import run_supply_chain_optimization


from data_tools import plot_surface, visualize_stock_levels, plot_co2_emissions, round_to_nearest_significant, plot_bar


def main_function():
    # Your main function logic

    absolute_path = os.path.dirname(__file__)

    #Round to nearest multiple of the power of 10
    def round_to_nearest_significant(number):
        if number == 0:
            return 0
        power = 10 ** math.floor(math.log10(abs(number)))
        return power * 10 if number >= power * 5 else power
    
    data = line_production.get_data()
    
    data_set = [8, 16, 16, 16, 20, 24, 32, 40, 48, 56, 64, 72, 80, 88, 92, 100, 108, 116, 124, 132, 140, 148, 156, 164, 172, 180, 184, 192, 200, 284, 292, 300, 308, 316, 324, 332, 340, 348, 356, 360, 368, 372, 380, 388, 396, 404, 412, 420, 428, 520, 524, 532, 540, 548, 556, 560, 568, 576, 584, 592, 600, 608, 616, 620, 628, 636, 644, 652, 660, 748, 756, 764, 772, 780, 788, 796, 804, 812, 820, 824, 832, 840, 848, 856, 864, 872, 880, 888, 972, 980, 988, 996, 1004, 1012, 1020, 1028, 1036, 1040, 1048, 1056, 1060, 1068, 1076, 1084, 1092, 1100, 1108, 1116, 1204, 1212, 1220, 1228, 1236, 1244, 1244, 1252, 1260, 1268, 1276, 1284, 1292, 1300, 1304]
    data_set = data['Total Seats made'][1]
    number_of_seat = data['Total Seats made'][1][-1]
    rounded_value = round_to_nearest_significant(number_of_seat)
    ytick_param = rounded_value / (rounded_value/(rounded_value/10))



    #visualize_stock_levels(data, ytick_param)


    fig_opti, fig2_opti, value, cap = run_supply_chain_optimization()
    print(cap)

    # Show the figure
    fig_opti.show()


    # Show the figure
    #fig2_opti.show()

    data_bars = [1, 2, 3, 4, 5]
    modes = ['Car', 'Bus', 'Train', 'Plane', 'Bike']
    plot_bar(data_bars, modes, xlabel='Transportation Mode', ylabel='CO2 Emissions (kg CO2e)', title='Total CO2 Emissions by Transportation Mode')

    #########################################################################################################

    # Original data: Number of seats
    original_data = data_set[:-50]
    # original_data = data
    original_data_np = np.array(original_data)
    print(original_data)

    # ARIMA Model Implementation for multiple future points
    num_future_points = 50  # Number of points you want to predict
    subset_size = int(len(original_data_np) * 0.2)  # 20% of the data
    recent_data_subset = original_data_np[-subset_size:]
    # print(recent_data_subset)
    arima_model = ARIMA(recent_data_subset, order=(1, 1, 1))
    arima_model_fit = arima_model.fit()
    arima_predictions = arima_model_fit.forecast(steps=num_future_points)

    # grey = GreyTheory()
    # gm11 = grey.gm11

    # Recent subset of data for GM(1,1)
    # subset_size = int(len(original_data_np) * 0.1)  # 20% of the data
    # recent_data_subset = original_data_np[-subset_size:]

    # Predicting multiple future points with GM(1,1)
    # gm11.clean_forecasted()  # Clear previous data patterns
    # current_data = list(recent_data_subset)
    
    # for value in current_data:
    #     gm11.add_pattern(value, "a")

    # gm_predictions_or = []
    # gm11.alpha = 0.55

    # for i in range(num_future_points):

    #     gm11.period = i
    #     gm11.forecast()
    #     next_value = gm11.analyzed_results[-1].forecast_value
    #     gm_predictions_or.append(next_value)
    #     current_data.append(next_value)  # Append prediction for the next iteration
    #     gm11.clean_forecasted()  # Clear for the next iteration


    

    grey = GreyTheory()
    gm11 = grey.gm11
    grey_data_set = list(recent_data_subset)
    
    for value in grey_data_set:
        gm11.add_pattern(value,"a{}".format(grey_data_set.index))

    gm_predictions = []
    gm11.alpha = 0.53

    for i in range(1,num_future_points+1):
        gm11.period = 1
        gm11.forecast()
        next_value = gm11.last_moment
        gm11.add_pattern(next_value, "a")
        # grey_data_set.append(next_value)
        # print(grey_data_set)
        gm_predictions.append(next_value)  # Append prediction for the next iteration
        gm11.clean_forecasted()  # Clear for the next iteration only work with convolution

    gm11.clean_forecasted()
    gm11.remove_all_analysis()

    gm11_conv = grey.gm11

    for value in grey_data_set:
        gm11_conv.add_pattern(value,"a{}".format(grey_data_set.index))

    gm_predictions_conv =[]
    # To try customized alpha for IAGO of Z.
    gm11_conv.convolution = True # Convolutional forecasting of GM11.
    gm11_conv.alpha = 0.53
    gm11_conv.stride = 3
    gm11_conv.length = 3    
    gm11_conv.forecast()
    gm_predictions_conv = gm11_conv.forecasted_outputs
    gm11.clean_forecasted()

    # Construction gm_predictions_conv indexes.
    gm_predictions_conv_indexes = []
    for i in range(0, len(gm_predictions_conv)):
        gm_predictions_conv_indexes.append(i)


    gm11_conv = grey.gm11
    forecast_horizon = 50  # Total number of points you want to forecast

    # Start with the initial dataset
    current_data_set = list(grey_data_set)

    while len(gm_predictions_conv) < forecast_horizon:
        gm11_conv.clean_forecasted()
        gm11_conv.remove_all_analysis()

        # Add the current dataset to the model
        for value in current_data_set:
            gm11_conv.add_pattern(value, "a{}".format(current_data_set.index(value)))

        # Convolutional forecasting of GM11
        gm11_conv.convolution = True
        gm11_conv.alpha = 0.53
        gm11_conv.stride = 3
        gm11_conv.length = 3
        
        # Perform the forecast
        gm11_conv.forecast()
        new_forecasts = gm11_conv.forecasted_outputs

        # Update the dataset and the list of predictions
        current_data_set.extend(new_forecasts)
        gm_predictions_conv.extend(new_forecasts)

        # Optional: Limit the size of current_data_set if memory is a concern
        # current_data_set = current_data_set[-some_length:]

        # Check if we've reached the forecast horizon
        if len(gm_predictions_conv) >= forecast_horizon:
            gm_predictions_conv = gm_predictions_conv[:forecast_horizon]
            break


    # len(gm_predictions)
    arima_predictions = [round(num, 1) for num in arima_predictions]
    print(arima_predictions)

    # gm_predictions = [round(num, 1) for num in gm_predictions]
    # print(gm_predictions)

    gm_predictions_conv = [round(num, 1) for num in gm_predictions_conv]
    print(gm_predictions_conv)


    # Plotting
    plt.figure(figsize=(12, 6))
    extended_original_data = original_data + arima_predictions
    # plt.plot(extended_original_data, marker='x', linestyle='--', color='gray', label='Original Data with ARIMA Predictions')
    plt.scatter(range(len(original_data), len(original_data) + num_future_points), arima_predictions, marker='o', linestyle='--', color='red', label='ARIMA Predictions')

    # Assuming you want to plot the recent subset along with GM(1,1) predictions
    shift_index = len(original_data) - len(recent_data_subset)
    shifted_recent_indices = [i + shift_index for i in range(len(recent_data_subset))]
    shifted_conv_indices =[shift_index + gm11.length + i * gm11.stride for i in range(len(gm_predictions_conv_indexes))]
    plt.plot(shifted_recent_indices, recent_data_subset, marker='o', linestyle='--', color='blue', label='Recent Data for GM(1,1)')
    # plt.plot(shifted_conv_indices, gm_predictions_conv, marker='o', linestyle='--', color='black', label='GM(1,1) Predictions with Convolution')
    plt.scatter(range(len(original_data), len(original_data)  + num_future_points ), gm_predictions, marker='o', linestyle='--', color='green', label='GM(1,1) Predictions')
    # plt.scatter(len(original_data)  + gm11.period - 1 , gm_predictions, color='green', label='GM(1,1) Predictions')
    # plt.scatter(range(len(original_data), len(original_data)  + num_future_points ), gm_predictions_or, color='orange', label='GM(1,1) Predictions or')
    
    shifted_indices = [0 + i for i in range(len(data_set))]
    plt.plot(shifted_indices,data_set, marker='.', linestyle='--', color='gray', label='Original Data')
   
    # plot gm_predictions_conv 
    plt.plot

    plt.title("Comparison of ARIMA and GM(1,1) Predictions with Recent Data Subset")
    plt.xlabel("Data Points")
    plt.ylabel("Values")
    plt.legend()
    plt.grid(True)
    # plt.show()


if __name__ == '__main__':

    main_function()
    
   

   