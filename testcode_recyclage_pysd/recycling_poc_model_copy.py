"""
Python model 'ClosedLoopSupplyChain.py'
Translated using PySD
"""

from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from pysd.py_backend.statefuls import Integ
from pysd import Component

__pysd_version__ = "3.14.0"

__data = {"scope": None, "time": lambda: 0}

_root = Path(__file__).parent


component = Component()

#######################################################################
#                          CONTROL VARIABLES                          #
#######################################################################

_control_vars = {
    "initial_time": lambda: 0,
    "final_time": lambda: 50,
    "time_step": lambda: 0.1,
    "saveper": lambda: time_step(),
}


def _init_outer_references(data):
    for key in data:
        __data[key] = data[key]


@component.add(name="Time")
def time():
    return __data["time"]()


@component.add(name="FINAL TIME", units="Month", comp_type="Constant", comp_subtype="Normal")
def final_time():
    return __data["time"].final_time()


@component.add(name="INITIAL TIME", units="Month", comp_type="Constant", comp_subtype="Normal")
def initial_time():
    return __data["time"].initial_time()


@component.add(name="SAVEPER", units="Month", limits=(0.0, np.nan), comp_type="Auxiliary", comp_subtype="Normal", depends_on={"time_step": 1})
def saveper():
    return __data["time"].saveper()


@component.add(name="TIME STEP", units="Month", limits=(0.0, np.nan), comp_type="Constant", comp_subtype="Normal")
def time_step():
    return __data["time"].time_step()

#######################################################################
#                           MODEL VARIABLES                           #
#######################################################################

@component.add(name="Demand", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal")
def demand():
    base_demand = 950
    seasonal_variation = 50 * np.sin(2 * np.pi * time() / 12)  # Variation saisonnière
    random_variation = np.random.normal(0, 20)  # Variation aléatoire
    return base_demand + seasonal_variation + random_variation

@component.add(name="Max Production Capacity", units="kg/Month", comp_type="Constant", comp_subtype="Normal")
def max_production_capacity():
    return 1000  # Maximum production capacity per month

@component.add(name="Raw Material Input", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"production_rate": 1, "recycling_rate": 1})
def raw_material_input():
    return production_rate() * (1 - recycling_rate())

@component.add(name="Recycled Material Input", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"waste_generation": 1, "recycling_efficiency": 1})
def recycled_material_input():
    return waste_generation() * recycling_efficiency()

@component.add(name="Production Rate", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"demand": 1, "max_production_capacity": 1})
def production_rate():
    return min(demand(), max_production_capacity())

@component.add(name="Waste Generation", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"production_rate": 1})
def waste_generation():
    return production_rate() * 0.2

@component.add(name="Recycling Efficiency", units="Dimensionless", limits=(0, 1), comp_type="Constant", comp_subtype="Normal")
def recycling_efficiency():
    return 0.8

@component.add(name="Recycling Rate", units="Dimensionless", limits=(0, 1), comp_type="Auxiliary", comp_subtype="Normal", depends_on={"recycling_efficiency": 1, "waste_generation": 1, "production_rate": 1})
def recycling_rate():
    return recycling_efficiency() * waste_generation() / production_rate()

@component.add(name="Total Material Input", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"raw_material_input": 1, "recycled_material_input": 1})
def total_material_input():
    return raw_material_input() + recycled_material_input()

@component.add(name="CO2 Emissions from Raw Materials", units="kg CO2/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"raw_material_input": 1})
def co2_emissions_raw():
    return raw_material_input() * 3.0

@component.add(name="CO2 Emissions from Recycling", units="kg CO2/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"recycled_material_input": 1})
def co2_emissions_recycling():
    return recycled_material_input() * 0.5

@component.add(name="Total CO2 Emissions", units="kg CO2/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"co2_emissions_raw": 1, "co2_emissions_recycling": 1})
def total_co2_emissions():
    return co2_emissions_raw() + co2_emissions_recycling()

@component.add(name="Carbon Tax Rate", units="$/kg CO2", comp_type="Constant", comp_subtype="Normal")
def carbon_tax_rate():
    return 0.1

@component.add(name="Total Carbon Tax", units="$/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"total_co2_emissions": 1, "carbon_tax_rate": 1})
def total_carbon_tax():
    return total_co2_emissions() * carbon_tax_rate()

@component.add(name="Variable Production Cost", units="$/kg", comp_type="Constant", comp_subtype="Normal")
def variable_production_cost():
    return 2.0

@component.add(name="Fixed Production Cost", units="$/Month", comp_type="Constant", comp_subtype="Normal")
def fixed_production_cost():
    return 5000

@component.add(name="Revenue from Products", units="$/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"production_rate": 1})
def revenue_from_products():
    return production_rate() * 3.0  # Prix de vente unitaire de 3$

@component.add(name="Total Cost", units="$/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"variable_production_cost": 1, "production_rate": 1, "fixed_production_cost": 1, "total_carbon_tax": 1})
def total_cost():
    return variable_production_cost() * production_rate() + fixed_production_cost() + total_carbon_tax()

@component.add(name="Total Profit", units="$/Month", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"revenue_from_products": 1, "total_cost": 1})
def total_profit():
    return revenue_from_products() - total_cost()

#######################################################################
#                           STOCK VARIABLES                           #
#######################################################################

@component.add(name="Raw Material Stock", units="kg", comp_type="Stateful", comp_subtype="Integ", depends_on={"_integ_raw_material_stock": 1}, other_deps={"_integ_raw_material_stock": {"initial": {}, "step": {"total_material_input": 1, "production_rate": 1}}})
def raw_material_stock():
    return _integ_raw_material_stock()

_integ_raw_material_stock = Integ(lambda: total_material_input() - production_rate(), lambda: 10000, "_integ_raw_material_stock")


@component.add(name="Recycled Material Stock", units="kg", comp_type="Stateful", comp_subtype="Integ", depends_on={"_integ_recycled_material_stock": 1}, other_deps={"_integ_recycled_material_stock": {"initial": {}, "step": {"recycling_rate": 1, "waste_generation": 1, "recycled_material_input": 1}}})
def recycled_material_stock():
    return _integ_recycled_material_stock()

_integ_recycled_material_stock = Integ(lambda: recycling_rate() * waste_generation() - recycled_material_input(), lambda: 5000, "_integ_recycled_material_stock")


@component.add(name="Waste Stock", units="kg", comp_type="Stateful", comp_subtype="Integ", depends_on={"_integ_waste_stock": 1}, other_deps={"_integ_waste_stock": {"initial": {}, "step": {"waste_generation": 1, "recycled_material_input": 1}}})
def waste_stock():
    return _integ_waste_stock()

_integ_waste_stock = Integ(lambda: waste_generation() - recycled_material_input(), lambda: 2000, "_integ_waste_stock")

#######################################################################
#                           OPTIMISATION                              #
#######################################################################

def objective_function(x):
    # x[0] = production_rate, x[1] = recycling_rate
    production_rate = x[0]
    recycling_rate = x[1]
    total_cost = variable_production_cost() * production_rate + fixed_production_cost()
    total_emissions = production_rate * 3.0 + recycling_rate * 0.5
    return total_cost + total_emissions * carbon_tax_rate()

initial_guess = [950, 0.8]
bounds = [(0, max_production_capacity()), (0, 1)]
result = minimize(objective_function, initial_guess, bounds=bounds)

@component.add(name="Optimized Production Rate", units="kg/Month", comp_type="Auxiliary", comp_subtype="Normal")
def optimized_production_rate():
    return result.x[0]

@component.add(name="Optimized Recycling Rate", units="Dimensionless", comp_type="Auxiliary", comp_subtype="Normal")
def optimized_recycling_rate():
    return result.x[1]  
