
import os
import math
import copy

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

# from greytheory import GreyTheory
import line_production
from SupplyChainOptimization import run_supply_chain_optimization


from data_tools import plot_surface, visualize_stock_levels, plot_co2_emissions, round_to_nearest_significant



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



    visualize_stock_levels(data, ytick_param)


    fig_opti, fig2_opti, value, cap = run_supply_chain_optimization()
    print(cap)

    # Show the figure
    fig_opti.show()


    # Show the figure
    fig2_opti.show()

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
    print(recent_data_subset)
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


    # Simplified GM(1,1) model implementation
    class GreyLib:
    
        def __init__(self, alpha=0.5):
            self.alpha = alpha

        # Generates AGO via patterns.
        def ago(self, patterns):
            # do ago
            ago_boxes = [] #np.array([], dtype=np.float)
            z_boxes   = []
            pattern_index = 0
            # x1 which is index 0 the output, x2 ~ xn are the inputs.
            for x_patterns in patterns:
                x_ago   = []
                sum     = 0.0
                z_value = 0.0
                x_index = 0
                for x_value in x_patterns:
                    sum += x_value
                    x_ago.append(sum)
                    # Only first pattern need to calculate the Z value.
                    if pattern_index == 0 and x_index > 0:
                        # Alpha 0.5 that means z is mean value, others alpha number means z is IAGO.
                        z_value = (self.alpha * sum) + (self.alpha * x_ago[x_index - 1])
                        z_boxes.append(z_value)
                    x_index += 1
                ago_boxes.append(x_ago)
                pattern_index += 1
            
            return (ago_boxes, z_boxes)
    
    class GreyMath:

        # Least Squares Method (LSM) to solve the equations, solves that simultaneous equations.
        def solve_equations(self, equations, equals):
            # Formula is ( B^T x B )^-1 x B^T x Yn, to be a square matrix first.
            transposed_equations = np.asarray(equations).T.tolist()
            # Doing ( B^T x B )
            square_matrix = np.dot(transposed_equations, equations)
            # Doing (B^T x Yn)
            bx_y = np.dot(transposed_equations, equals)
            # Solves equations.
            return np.linalg.solve(square_matrix, bx_y).tolist()
        
    class GreyFactory:

        name           = ""
        equation_value = ""
        ranking        = ""
    
    class GreyForecast:

        tag = ""
        k   = 0
        original_value = 0.0
        forecast_value = 0.0
        error_rate     = 0.0
        average_error_rate = 0.0
        


    class GreyClass (object):

        _TAG_FORECAST_NEXT_MOMENT = "forecasted_next_moment"
        _TAG_FORECAST_HISTORY     = "history"

        def __init__(self):
            self.tag               = self.__class__.__name__
            self.patterns          = []
            self.keys              = []
            self.analyzed_results  = []
            self.influence_degrees = []
            self.grey_lib          = GreyLib()
            self.grey_math         = GreyMath()
        
        # Those outputs are the results of all patterns.
        def _add_outputs(self, outputs, pattern_key):
            self.patterns.insert(0, outputs)
            self.keys.append(pattern_key)
        
        # Those patterns are using in AGO generator.
        def _add_patterns(self, patterns, pattern_key):
            self.patterns.append(patterns)
            self.keys.append(pattern_key)

        def ago(self, patterns):
            return self.grey_lib.ago(patterns)
        
        def remove_all_analysis(self):
            # Deeply removing without others copied array.
            self.analyzed_results  = []
            self.influence_degrees = []
            self.forecasts         = []

            # Removing all reference links with others array.
            #del self.analyzed_results
            #del self.influence_degrees
            #del self.forecasts

        def print_self(self):
            print("%r" % self.__class__.__name__)

        def print_analyzed_results(self):
            self.print_self()
            for factory in self.analyzed_results:
                print("Pattern key: %r, grey value: %r, ranking: %r" % (factory.name, factory.equation_value, factory.ranking))

        def print_influence_degrees(self):
            self.print_self()
            string = " > ".join(self.influence_degrees)
            print("The keys of parameters their influence degrees (ordering): %r" % string)

        def print_forecasted_results(self):
            self.print_self()
            for forecast in self.analyzed_results:
                print("K = %r" % forecast.k)
                if forecast.tag == self._TAG_FORECAST_HISTORY:
                    # History.
                    print("From revised value %r to forecasted value is %r" % (forecast.original_value, forecast.forecast_value))
                    print("The error rate is %r" % forecast.error_rate)
                else:
                    # Next moments.
                    print("Forcasted next moment value is %r" % forecast.forecast_value)
            
            # Last forecasted moment.
            last_moment = self.analyzed_results[-1]
            print("The average error rate %r" % last_moment.average_error_rate)

        def deepcopy(self):
            return copy.deepcopy(self)

        @property
        def alpha(self):
            return self.grey_lib.alpha
        
        @alpha.setter
        def alpha(self, value = 0.5):
            self.grey_lib.alpha = value

    class GreyGM11 (GreyClass):

        def __init__(self):
            super(GreyGM11, self).__init__() # Calling super object __init__
            self.forecasted_outputs = []
            self.stride      = 1
            self.length      = 4
            self.period      = 1 # Default is 1, the parameter means how many next moments need to forcast continually.
            self.convolution = False
        
        def add_pattern(self, pattern, pattern_key):
            self._add_patterns(pattern, pattern_key)

        def __forecast_value(self, x1, a_value, b_value, k):
            return (1 - math.exp(a_value)) * (x1 - (b_value / a_value)) * math.exp(-a_value * k)
        
        def __forecast(self, patterns, period=1):
            self.remove_all_analysis()
            ago     = self.ago([patterns])
            z_boxes = ago[1]
            # Building B matrix, manual transpose z_boxes and add 1.0 to every sub-object.
            factors = []
            # for z in z_boxes:
            #     x_t = []
            #     # Add negative z
            #     x_t.append(-z)
            #     x_t.append(1.0)
            #     factors.append(x_t)
            factors = [[-z, 1.0] for z in z_boxes]
            # Building Y matrix to be output-goals of equations.
            y_vectors = []
            y_vectors = patterns[1:]
            # for passed_number in patterns[1::]:
            #     y_vectors.append(passed_number)
            
            solved_equations = self.grey_math.solve_equations(factors, y_vectors)
            # Then, forecasting them at all include next moment value.
            analyzed_results = []
            forecast_value = []
            sum_error = 0.0
            x1        = patterns[0]
            a_value   = solved_equations[0]
            b_value   = solved_equations[1]
            k         = 1
            length    = len(patterns)
            for passed_number in patterns[1::]:
                grey_forecast  = GreyForecast()
                forecast_value = self.__forecast_value(x1, a_value, b_value, k)

                original_value  = patterns[k]
                error_rate      = abs((original_value - forecast_value) / original_value)
                sum_error      += error_rate
                grey_forecast.tag = self._TAG_FORECAST_HISTORY
                grey_forecast.k   = k
                grey_forecast.original_value = original_value
                grey_forecast.forecast_value = forecast_value
                grey_forecast.error_rate     = error_rate
                analyzed_results.append(grey_forecast)
                k += 1
            
            # Continuous forecasting next moments.
            if period > 0:
                for go_head in range(period):
                    forecast_value = self.__forecast_value(x1, a_value, b_value, k)

                    grey_forecast     = GreyForecast()
                    grey_forecast.tag = self._TAG_FORECAST_NEXT_MOMENT
                    grey_forecast.k   = k # This k means the next moment of forecasted.
                    grey_forecast.average_error_rate = sum_error / (length - 1)
                    grey_forecast.forecast_value     = forecast_value
                    analyzed_results.append(grey_forecast)
                    k += 1

            self.analyzed_results = analyzed_results
            return analyzed_results

        # stride: the N-gram, shift step-size for each forecasting.
        # length: the Filter kernel, shift length of distance for each forecasting.
        def __forecast_convolution(self, patterns=[], stride=1, length=4):
            pattern_count = len(patterns)
            # Convolution formula: (pattern_count - length) / stride + 1, 
            # e.g. (7 - 3) / 1 + 1 = 5 (Needs to shift 5 times.)
            # e.g. (7 - 3) / 3 + 1 = 2.33, to get floor() or ceil()
            # total_times at least for once.
            total_times  = int(math.floor(float(pattern_count - length) / stride + 1))
            convolutions = []
            stride_index = 0
            for i in range(0, total_times):
                # If it is last convolution, we directly pick it all.
                stride_length = stride_index+length
                if i == total_times - 1:
                    stride_length = len(patterns)

                convolution_patterns = patterns[stride_index:stride_length]
                period_forecasts     = self.__forecast(convolution_patterns)
                convolutions.append(period_forecasts)

                # Fetchs forecasted moment and revises it to be fix with average error rate.
                forecasted_moment    = period_forecasts[-1]
                forecasted_value     = forecasted_moment.forecast_value
                revised_value        = forecasted_value + (forecasted_value * forecasted_moment.average_error_rate)
                self.forecasted_outputs.append(revised_value)

                # Next stride start index.
                stride_index += stride
            
            #print "forecasted_outputs % r" % self.forecasted_outputs

            # Using extracted convolution that forecasted values to do final forecasting.
            if total_times > 1:
                self.__forecast(self.forecasted_outputs)
                self.forecasted_outputs.append(self.last_moment)
            
            return convolutions
        
        # period: , default: 1
        def forecast(self):
            if self.convolution == True:
                return self.__forecast_convolution(self.patterns, self.stride, self.length)
            else:
                return self.__forecast(self.patterns, self.period)

        # In next iteration of forecasting, we wanna continue use last forecasted results to do next forecasting, 
        # but if we removed gm11.forecasted_outputs list before,  
        # we can use continue_forecasting() to extend / recall the last forecasted result come back to be convolutional features. 
        def continue_forecasting(self, last_forecasted_outputs = []):
            self.forecasted_outputs.extend(last_forecasted_outputs)
        
        # Clean forecasted outputs.
        def clean_forecasted(self):
            self.forecasted_outputs = []
            
        @property
        def last_moment(self):
            # Last GreyForecast() object is the next moment forecasted.
            return self.analyzed_results[-1].forecast_value

    class GreyTheory:
        def __init__(self):
            self.gm11 = GreyGM11()

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
    
   

   