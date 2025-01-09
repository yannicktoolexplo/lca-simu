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
import line_production.production_engine as production_engine
import distribution.distribution_engine as distribution_engine
import environment.environment_engine as environment_engine
import math
import random
random.seed(1447)

def run_supply_chain_optimization(capacity_limits):
    """
    Runs the supply chain optimization using given data and constraints.
    This function reads data from multiple Excel files, processes the data, and sets up the optimization problem.
    """
    absolute_path = os.path.dirname(__file__)

    """Runs the supply chain optimization using given data and constraints."""
    # Load freight costs and demand data
    freight_costs, demand = distribution_engine.load_freight_costs_and_demands()

    # Load fixed and variable costs
    fixed_costs, var_cost = production_engine.load_fixed_and_variable_costs(freight_costs)
    
    
    # Load and update capacity limits
    cap = production_engine.load_capacity_limits(capacity_limits)


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
        model += lpSum([x[(i, j)] for j in loc_demand]) <= lpSum([cap.loc[i, s] * y[(i, s)] for s in size]) +lpSum([x[(i, j)] for j in loc_demand]) >= 50 * lpSum([y[(i, s)] for s in size])
    
    # Define logical constraint: Add a logical constraint so that if the high capacity plant in USA is open, then a low capacity plant in Germany is also opened.
    model += y[('Texas','High')] <= y[('California','Low')]
    model += y[('California','High')] <= y[('Texas','Low')]
    model += y[('Texas','High')] + y[('California','High')] <= y[('France','Low')]
    model += y[('UK','High')] <= y[('France','Low')]  
    model += y[('France','High')] <= y[('UK','Low')]  
    model += y[('France','High')] + y[('UK','High')] <= y[('Texas','Low')]

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
        # print(name, "=", v.varValue)

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

def run_supply_chain_optimization_minimize_co2(capacity_limits):
    """
    Runs the supply chain optimization with the goal of minimizing CO2 emissions.
    This function reads data from multiple Excel files, processes the data, and sets up the optimization problem.
    """
    absolute_path = os.path.dirname(__file__)

    # Load freight costs and demand data
    freight_costs, demand = distribution_engine.load_freight_costs_and_demands()

    # Load fixed and variable costs
    fixed_costs, var_cost = production_engine.load_fixed_and_variable_costs(freight_costs)
    
    # Load and update capacity limits
    cap = production_engine.load_capacity_limits(capacity_limits)

    # Define Decision Variables
    loc_prod = ['Texas', 'California', 'UK', 'France']
    loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
    size = ['Low', 'High']

    # Initialize Class
    model = LpProblem("Capacitated Plant Location Model", LpMinimize)

    # Create Decision Variables
    x = LpVariable.dicts("production_", [(i, j) for i in loc_prod for j in loc_demand], lowBound=0, upBound=None, cat='continuous')
    y = LpVariable.dicts("plant_", [(i, s) for s in size for i in loc_prod], cat='Binary')

    # Define Objective Function with CO2 emissions
    co2_emissions = lpSum([environment_engine.calculate_distribution_co2_emissions(i, j, x[(i, j)]) for i in loc_prod for j in loc_demand]) + lpSum([environment_engine.calculate_production_co2_emissions(i, x[(i, j)]) for i in loc_prod for j in loc_demand])
    
    # Set the objective to minimize CO2 emissions
    model += co2_emissions

    # Add Constraints
    for j in loc_demand:
        model += lpSum([x[(i, j)] for i in loc_prod]) == demand.loc[j, 'Demand']
    for i in loc_prod:
        model += lpSum([x[(i, j)] for j in loc_demand]) <= lpSum([cap.loc[i, s] * y[(i, s)] for s in size]) +lpSum([x[(i, j)] for j in loc_demand]) >= 50 * lpSum([y[(i, s)] for s in size])

    # Define logical constraint: Add a logical constraint so that if the high capacity plant in USA is open, then a low capacity plant in Germany is also opened.
    model += y[('Texas','High')] <= y[('California','Low')]
    model += y[('California','High')] <= y[('Texas','Low')]
    model += y[('Texas','High')] + y[('California','High')] <= y[('France','Low')]
    model += y[('UK','High')] <= y[('France','Low')]  
    model += y[('France','High')] <= y[('UK','Low')]  
    model += y[('France','High')] + y[('UK','High')] <= y[('Texas','Low')]

    # New constraint: minimum production of 50 units per node


    # Solve Model
    model.solve()
    print("Total CO2 Emissions = {:,} (kg)".format(int(utilities.value(model.objective))))
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

    # Calculate total units for each production and market node
    production_totals = {location: 0 for location in loc_prod}
    market_totals = {location: 0 for location in loc_demand}

    for s, t, v in zip(source, target, value):
        production_totals[loc_prod[s]] += v
        market_totals[loc_demand[t]] += v

    # Return
    return source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap