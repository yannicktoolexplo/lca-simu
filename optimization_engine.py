# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.16.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---
import os
import pandas as pd
from pulp import *
from pulp import utilities
import plotly.graph_objects as go
import line_production
import math
import random
random.seed(1447)

def run_supply_chain_optimization():
    """
    Runs the supply chain optimization using given data and constraints.
    This function reads data from multiple Excel files, processes the data, and sets up the optimization problem.
    """
    absolute_path = os.path.dirname(__file__)

    # ### Plant Location

    # #### Manufacturing variable costs

    # Import Costs
    manvar_costs = pd.read_excel(os.path.join(absolute_path, 'data/variable_costs.xlsx'), index_col=0)

    # #### Freight costs

    # Import Costs
    freight_costs = pd.read_excel(os.path.join(absolute_path, 'data/freight_costs.xlsx'), index_col=0)

    # #### Variable Costs

    # Variable Costs
    var_cost = freight_costs / 1000 + manvar_costs

    # #### Fixed Costs

    # Import Costs
    fixed_costs = pd.read_excel(os.path.join(absolute_path, 'data/fixed_cost.xlsx'), index_col=0)

    # #### Plants Capacity

    # Two types of plants: Low Capacity and High Capacity Plant
    file_path = os.path.join(absolute_path, 'data/capacity.xlsx')
    cap = pd.read_excel(file_path, index_col=0)
    data = line_production.get_data()

    # Calculate the capacity limits for each plant based on the total seats made
    nos_texas_low = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_texas_high = math.ceil(1.2 * data['Total Seats made'][1][-1])
    nos_california_low = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_california_high = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_UK_low = math.ceil(0.15 * data['Total Seats made'][1][-1])
    nos_UK_high = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_france_low = math.ceil(0.45 * data['Total Seats made'][1][-1])
    nos_france_high = math.ceil(0.9 * data['Total Seats made'][1][-1])

    # Update the capacity DataFrame with the calculated limits
    cap.iloc[0, 0] = nos_texas_low
    cap.iloc[0, 1] = nos_texas_high
    cap.iloc[1, 0] = nos_california_low
    cap.iloc[1, 1] = nos_california_high
    cap.iloc[2, 0] = nos_UK_low
    cap.iloc[2, 1] = nos_UK_high
    cap.iloc[3, 0] = nos_france_low
    cap.iloc[3, 1] = nos_france_high

    # Save the modified DataFrame back to the Excel file
    cap.to_excel(file_path)
    # cap = pd.read_excel(file_path, index_col = 0)

# #### Demand

    # -- Demand
    demand = pd.read_excel(os.path.join(absolute_path, 'data/demand.xlsx'), index_col=0)

    # Define Decision Variables
    loc_prod = ['Texas', 'California', 'UK', 'France']
    loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
    size = ['Low', 'High']

    # Initialize Class
    model = LpProblem("Capacitated Plant Location Model", LpMinimize)

    # Create Decision Variables
    x = LpVariable.dicts("production_", [(i, j) for i in loc_prod for j in loc_demand],
                         lowBound=0, upBound=None, cat='continuous')
    y = LpVariable.dicts("plant_",
                         [(i, s) for s in size for i in loc_prod], cat='Binary')

    # Define Objective Function
    model += (lpSum([fixed_costs.loc[i, s] * y[(i, s)] for s in size for i in loc_prod])
              + lpSum([var_cost.loc[i, j] * x[(i, j)] for i in loc_prod for j in loc_demand]))

    # Add Constraints
    for j in loc_demand:
        model += lpSum([x[(i, j)] for i in loc_prod]) == demand.loc[j, 'Demand']
    for i in loc_prod:
        model += lpSum([x[(i, j)] for j in loc_demand]) <= lpSum([cap.loc[i, s] * y[(i, s)]
                                                                 for s in size])

    # Solve Model
    model.solve()
    print("Total Costs = {:,} ($/Month)".format(int(utilities.value(model.objective))))
    print("---------")
    print('\n' + "Status: {}".format(LpStatus[model.status]))

    # Create a dictionary to store plant and production decision variables
    dict_plant = {}
    dict_prod = {}
    for v in model.variables():
        if 'plant' in v.name:
            name = v.name.replace('plant__', '').replace('_', '')
            dict_plant[name] = int(v.varValue)
            p_name = name
        else:
            name = v.name.replace('production__', '').replace('_', '')
            dict_prod[name] = v.varValue

    # Filter to keep only non-zero flux
    non_zero_flux = {k: v for k, v in dict_prod.items() if v > 0}

    # Clean and transform keys
    transformed_flux = {}
    for key, value in non_zero_flux.items():
        clean_key = key.replace("('", "").replace("')", "").replace("'", "")
        src, tgt = clean_key.split(',')
        transformed_flux[(src.strip(), tgt.strip())] = value

    # Create lists for the Sankey diagram
    source = []
    target = []
    value = []

    for (src, tgt), val in transformed_flux.items():
        source.append(loc_prod.index(src))
        target.append(loc_demand.index(tgt))
        value.append(val)

    # print(source)
    # print(target)
    # print(value)

    # Calculate total units for each production and market node
    production_totals = {location: 0 for location in loc_prod}
    market_totals = {location: 0 for location in loc_demand}

    for s, t, v in zip(source, target, value):
        production_totals[loc_prod[s]] += v
        market_totals[loc_demand[t]] += v



    # Return
    return source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap
