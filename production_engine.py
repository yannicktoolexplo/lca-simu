# production_engine.py

import os
import math
import pandas as pd

def calculate_capacity_limits(data):
    """Calculate the capacity limits for each plant based on the total seats made."""
    nos_texas_low = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_texas_high = math.ceil(1.2 * data['Total Seats made'][1][-1])
    nos_california_low = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_california_high = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_UK_low = math.ceil(0.15 * data['Total Seats made'][1][-1])
    nos_UK_high = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_france_low = math.ceil(0.45 * data['Total Seats made'][1][-1])
    nos_france_high = math.ceil(0.9 * data['Total Seats made'][1][-1])

    capacity_limits = {
        'Texas': (nos_texas_low, nos_texas_high),
        'California': (nos_california_low, nos_california_high),
        'UK': (nos_UK_low, nos_UK_high),
        'France': (nos_france_low, nos_france_high)
    }
    return capacity_limits


def load_fixed_and_variable_costs(freight_costs):
    """Load fixed and variable costs from Excel files."""
    absolute_path = os.path.dirname(__file__)
    
    fixed_costs = pd.read_excel(os.path.join(absolute_path, 'data/fixed_cost.xlsx'), index_col=0)
    manvar_costs = pd.read_excel(os.path.join(absolute_path, 'data/variable_costs.xlsx'), index_col=0)
    
    variable_costs = freight_costs / 1000 + manvar_costs
    
    return fixed_costs, variable_costs

def load_capacity_limits(capacity_limits):
    """Load and update capacity limits."""
    absolute_path = os.path.dirname(__file__)
    cap = pd.read_excel(os.path.join(absolute_path, 'data/capacity.xlsx'), index_col=0)
    
    # Update the capacity DataFrame with the calculated limits
    for location, (low, high) in capacity_limits.items():
        cap.loc[location, 'Low'] = low
        cap.loc[location, 'High'] = high

    # Save the modified DataFrame back to the Excel file
    cap.to_excel(os.path.join(absolute_path, 'data/capacity.xlsx'))
    
    return cap
