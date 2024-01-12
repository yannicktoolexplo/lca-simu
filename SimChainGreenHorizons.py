
import os
from greytheory import GreyTheory
import line_production
from SupplyChainOptimization import run_supply_chain_optimization
import matplotlib.pyplot as plt

from data_tools import plot_surface, visualize_stock_levels, plot_co2_emissions, round_to_nearest_significant

from statsmodels.tsa.arima.model import ARIMA
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
    # print(original_data)


    # Fit an ARIMA model to the original data
    # The order (p, d, q) of the ARIMA model is a hyperparameter that usually requires tuning
    # For simplicity, we'll start with a basic configuration (1, 1, 1), but this may need to be adjusted
    arima_model = ARIMA(original_data, order=(1, 1, 1))
    arima_results = arima_model.fit()  

    # Forecasting 50% more data points than the original dataset
    forecast_length = int(len(original_data) * 0.5)
    forecasted_data_arima = arima_results.forecast(steps=forecast_length)

    # Generating x-coordinates for the forecasted data for plotting
    x_forecast_arima = list(range(len(original_data) + 1, len(original_data) + 1 + forecast_length))  

    # Number of original data points
    n_original = len(original_data)

    # X-coordinates for the original data
    x_original = list(range(1, n_original + 1))


    # # Initialize Grey Theory
    grey = GreyTheory()

    # # Reinitializing the Grey GM(1,1) model
    gm11 = grey.gm11

    # Configuring GM11 model parameters
    gm11.alpha = 0.55
    gm11.convolution = True  # Convolutional forecasting of GM11.
    gm11.stride = 5 
    gm11.length = 6
    pattern_count = len(original_data)

    # Adding each value of original_data as a separate pattern
    for i, value in enumerate(original_data):
        gm11.add_pattern(value, "d{}".format(i))

    # Perform forecasting
    gm11.forecast()

    # Retrieving the forecasted results
    forecasted_results = gm11.forecasted_outputs
    # Starting point of forcasted data
    forecast_start_point = len(original_data) - pattern_count + gm11.length
    # Adjusting the x-coordinates for the forecasted data
    x_forecasted_corrected = [forecast_start_point + i * gm11.stride for i in range(len(forecasted_results))]

    gm11.clean_forecasted()

    # Configuring GM11 model parameters
    gm11.alpha = 0.55
    gm11.convolution = True  # Convolutional forecasting of GM11.
    gm11.stride = 10 
    gm11.length = 3

    # Adding each value of original_data as a separate pattern
    for i, value in enumerate(forecasted_results[-gm11.stride:]):
        gm11.add_pattern(value, "d{}".format(i))

    gm11.continue_forecasting(forecasted_results[-gm11.stride:])
    next_forecasted_results = gm11.forecasted_outputs

    # Display the forecasted results
    # print(forecasted_results)


    next_forecast_start_point = len(original_data) - gm11.stride * (len(forecasted_results[-gm11.stride:])- 1) + gm11.stride * gm11.length


    x_next_forecasted_corrected = [next_forecast_start_point + i * gm11.stride for i in range(len(next_forecasted_results))]

    # Create a figure
    plt.figure(figsize=(12, 6))

    plt.plot(x_original, original_data, label='Original Data', color='blue')
    plt.plot(x_forecast_arima, forecasted_data_arima, label='ARIMA Forecasted Data', color='red', linestyle='--')
    plt.plot(x_forecasted_corrected, forecasted_results, label='Forecasted Data (Convolutional)', color='green', linestyle='--')
    plt.plot(x_next_forecasted_corrected, next_forecasted_results, label='Forecasted Data (Convolutional)', color='orange', linestyle='--')
    plt.title('Original Data and ARIMA Forecasted Data and Forecasted Data (Convolutional)')
    plt.xlabel('Time Period / Sequence Number')
    plt.ylabel('Values')
    plt.show()


if __name__ == '__main__':

    main_function()
    
   

   