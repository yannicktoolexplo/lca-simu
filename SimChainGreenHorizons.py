
import os
from greytheory import GreyTheory
grey = GreyTheory()
import line_production
from SupplyChainOptimization import run_supply_chain_optimization

from data_tools import plot_surface, visualize_stock_levels, plot_co2_emissions, round_to_nearest_significant


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


    forecasted_data = []
    previous_forecasted_results = []
    curve =[]
    original_data = []


    gm11 = grey.gm11

    original_data=data['Total Seats made'][1]
    # print(original_data)


if __name__ == '__main__':

    main_function()
    
   

   