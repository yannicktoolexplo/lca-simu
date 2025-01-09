import numpy as np
import copy
import math

# Simplified GM(1,1) model implementation
class GreyLib:
    """
    Class containing methods for calculating the AGO and Z series for the simplified GM(1,1) model.
    """
    def __init__(self, alpha=0.5):
        """
        Initialize the value of alpha used for the calculation of the Z series.
        """
        self.alpha = alpha

    # Generates AGO via patterns.
    def ago(self, patterns):
        """
        Calculates the AGO series from a list of patterns.
        """
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
    """
    Class containing methods for solving equations using the least squares method.
    """
    # Least Squares Method (LSM) to solve the equations, solves that simultaneous equations.
    def solve_equations(self, equations, equals):
        """
        Solves a system of linear equations using the least squares method.
        """
        # Formula is ( B^T x B )^-1 x B^T x Yn, to be a square matrix first.
        transposed_equations = np.asarray(equations).T.tolist()
        # Doing ( B^T x B )
        square_matrix = np.dot(transposed_equations, equations)
        # Doing (B^T x Yn)
        bx_y = np.dot(transposed_equations, equals)
        # Solves equations.
        return np.linalg.solve(square_matrix, bx_y).tolist()

class GreyFactory:
    """
    Class representing a factory in the simplified GM(1,1) model.
    """
    name           = ""
    equation_value = ""
    ranking        = ""

class GreyForecast:
    """
    Class representing a forecast in the simplified GM(1,1) model.
    """
    tag = ""
    k   = 0
    original_value = 0.0
    forecast_value = 0.0
    error_rate     = 0.0
    average_error_rate = 0.0

class GreyClass (object):
    """
    Base class for the simplified GM(1,1) model.
    """
    _TAG_FORECAST_NEXT_MOMENT = "forecasted_next_moment"
    _TAG_FORECAST_HISTORY     = "history"

    def __init__(self):
        """
        Initializes the attributes of the class.
        """
        self.tag               = self.__class__.__name__
        self.patterns          = []
        self.keys              = []
        self.analyzed_results  = []
        self.influence_degrees = []
        self.grey_lib          = GreyLib()
        self.grey_math         = GreyMath()

    # Those outputs are the results of all patterns.
    def _add_outputs(self, outputs, pattern_key):
        """
        Adds an output and its corresponding key to the list of outputs.
        """
        self.patterns.insert(0, outputs)
        self.keys.append(pattern_key)

    # Those patterns are using in AGO generator.
    def _add_patterns(self, patterns, pattern_key):
        """
        Adds a pattern and its corresponding key to the list of patterns.
        """
        self.patterns.append(patterns)
        self.keys.append(pattern_key)

    def ago(self, patterns):
        """
        Calculates the AGO series from a list of patterns.
        """
        return self.grey_lib.ago(patterns)

    def remove_all_analysis(self):
        """
        Removes all previous analyses.
        """
        # Deeply removing without others copied array.
        self.analyzed_results  = []
        self.influence_degrees = []
        self.forecasts         = []

        # Removing all reference links with others array.
        #del self.analyzed_results
        #del self.influence_degrees
        #del self.forecasts


    def print_self(self):
        """
        Prints the name of the class.
        """
        print("%r" % self.__class__.__name__)

    def print_analyzed_results(self):
        """
        Prints the analysis results for each model.
        """
        self.print_self()
        for factory in self.analyzed_results:
            print("Pattern key: %r, grey value: %r, ranking: %r" % (factory.name, factory.equation_value, factory.ranking))

    def print_influence_degrees(self):
        """
        Prints the degrees of influence of each parameter.
        """
        self.print_self()
        string = " > ".join(self.influence_degrees)
        print("The keys of parameters their influence degrees (ordering): %r" % string)

    def print_forecasted_results(self):
        """
        Prints the forecast results for each model.
        """
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

class GreyGM11(GreyClass):
    """
    Class representing the simplified GM(1,1) model.
    """

    def __init__(self):
        """
        Initializes the attributes of the class.
        """
        super(GreyGM11, self).__init__()
        self.forecasted_outputs = []
        self.stride = 1
        self.length = 4
        self.period = 1 # Default is 1, the parameter means how many next moments need to be forecasted continuously.
        self.convolution = False

    def add_pattern(self, pattern, pattern_key):
        """
        Adds a model and its corresponding key to the list of models.
        """
        self._add_patterns(pattern, pattern_key)

    def __forecast_value(self, x1, a_value, b_value, k):
        """
        Calculates the forecast value based on the model parameters.
        """
        return (1 - math.exp(a_value)) * (x1 - (b_value / a_value)) * math.exp(-a_value * k)

    def __forecast(self, patterns, period=1):
        """
        Performs a forecast based on a list of models.
        """
        self.remove_all_analysis()
        ago = self.ago([patterns])
        z_boxes = ago[1]
        # Building B matrix, manual transpose z_boxes and add 1.0 to every sub-object.
        factors = [[-z, 1.0] for z in z_boxes]
        # Building Y matrix to be output-goals of equations.
        y_vectors = patterns[1:]

        solved_equations = self.grey_math.solve_equations(factors, y_vectors)
        # Then, forecasting them at all include next moment value.
        analyzed_results = []
        forecast_value = []
        sum_error = 0.0
        x1 = patterns[0]
        a_value = solved_equations[0]
        b_value = solved_equations[1]
        k = 1
        length = len(patterns)
        for passed_number in patterns[1::]:
            grey_forecast = GreyForecast()
            forecast_value = self.__forecast_value(x1, a_value, b_value, k)

            original_value = patterns[k]
            error_rate = abs((original_value - forecast_value) / original_value)
            sum_error += error_rate
            grey_forecast.tag = self._TAG_FORECAST_HISTORY
            grey_forecast.k = k
            grey_forecast.original_value = original_value
            grey_forecast.forecast_value = forecast_value
            grey_forecast.error_rate = error_rate
            analyzed_results.append(grey_forecast)
            k += 1
        
        
        # Continuous forecasting for the next moments.
        if period > 0:
            # Loop through the period for forecasting each moment
            for go_head in range(period):
                # Calculate the forecast value
                forecast_value = self.__forecast_value(x1, a_value, b_value, k)

                # Initialize a new GreyForecast object
                grey_forecast = GreyForecast()
                # Set the tag for the new forecast
                grey_forecast.tag = self._TAG_FORECAST_NEXT_MOMENT
                # Set the 'k' attribute, which represents the next moment to be forecasted
                grey_forecast.k = k  # This 'k' means the next moment of forecasted.
                # Calculate and set the average error rate
                grey_forecast.average_error_rate = sum_error / (length - 1)
                # Set the forecast value for the new forecast
                grey_forecast.forecast_value = forecast_value
                # Add the new forecast to the list of analyzed results
                analyzed_results.append(grey_forecast)
                # Increment 'k' for the next moment
                k += 1

        # Set the analyzed results to the class instance
        self.analyzed_results = analyzed_results
        # Return the analyzed results
        return analyzed_results


    # stride: the N-gram, shift step-size for each forecasting.
    # length: the Filter kernel, shift length of distance for each forecasting.
    def __forecast_convolution(self, patterns=[], stride=1, length=4):
        """
        Performs a forecast by convolution from a list of patterns.
        """
        pattern_count = len(patterns)
        # Convolution formula: (pattern_count - length) / stride + 1,
        # e.g. (7 - 3) / 1 + 1 = 5 (Needs to shift 5 times.)
        # e.g. (7 - 3) / 3 + 1 = 2.33, to get floor() or ceil()
        # total_times at least for once.
        total_times = int(math.floor(float(pattern_count - length) / stride + 1))
        convolutions = []
        stride_index = 0
        for i in range(0, total_times):
            # If it is the last convolution, we directly pick it all.
            stride_length = stride_index + length
            if i == total_times - 1:
                stride_length = len(patterns)

            convolution_patterns = patterns[stride_index:stride_length]
            period_forecasts = self.__forecast(convolution_patterns)
            convolutions.append(period_forecasts)

            # Fetches the forecasted moment and revises it to be fixed with the average error rate.
            forecasted_moment = period_forecasts[-1]
            forecasted_value = forecasted_moment.forecast_value
            revised_value = forecasted_value + (forecasted_value * forecasted_moment.average_error_rate)
            self.forecasted_outputs.append(revised_value)

            # Next stride start index.
            stride_index += stride

        # Using extracted convolution that forecasted values to do final forecasting.
        if total_times > 1:
            self.__forecast(self.forecasted_outputs)
            self.forecasted_outputs.append(self.last_moment)

        return convolutions

    # period: , default: 1
    def forecast(self):
        """
        Performs a forecast from the list of patterns.
        """
        if self.convolution == True:
            return self.__forecast_convolution(self.patterns, self.stride, self.length)
        else:
            return self.__forecast(self.patterns, self.period)

    # In the next iteration of forecasting, we want to continue using the last forecasted results to do the next forecasting,
    # but if we removed gm11.forecasted_outputs list before,
    # we can use continue_forecasting() to extend / recall the last forecasted result back to be convolutional features.
    def continue_forecasting(self, last_forecasted_outputs=[]):
        """
        Continues the forecast from the last forecasted results.
        """
        self.forecasted_outputs.extend(last_forecasted_outputs)

    # Clean forecasted outputs.
    def clean_forecasted(self):
        """
        Removes the last forecasted results.
        """
        self.forecasted_outputs = []

    @property
    def last_moment(self):
        """
        Returns the last forecasted value.
        """
        # Last GreyForecast() object is the next moment forecasted.
        return self.analyzed_results[-1].forecast_value

class GreyTheory:
    def __init__(self):
        self.gm11 = GreyGM11()
