"""
Python model 'ProductionLine.py'
Based on the Teacup model, translated using PySD
"""

from pathlib import Path
import numpy as np
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
    "final_time": lambda: 30,
    "time_step": lambda: 0.125,
    "saveper": lambda: time_step(),
}

def _init_outer_references(data):
    for key in data:
        __data[key] = data[key]

@component.add(name="Time")
def time():
    return __data["time"]()

@component.add(
    name="FINAL TIME", units="Minute", comp_type="Constant", comp_subtype="Normal"
)
def final_time():
    return _control_vars["final_time"]()

@component.add(
    name="INITIAL TIME", units="Minute", comp_type="Constant", comp_subtype="Normal"
)
def initial_time():
    return _control_vars["initial_time"]()

@component.add(
    name="SAVEPER",
    units="Minute",
    limits=(0.0, np.nan),
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time_step": 1},
)
def saveper():
    return _control_vars["saveper"]()

@component.add(
    name="TIME STEP",
    units="Minute",
    limits=(0.0, np.nan),
    comp_type="Constant",
    comp_subtype="Normal",
)
def time_step():
    return _control_vars["time_step"]()

#######################################################################
#                           MODEL VARIABLES                           #
#######################################################################

# Define the number of workstations
NUM_WORKSTATIONS = 7

# Define the maximum supply rate
MAX_SUPPLY_RATE = 15

# Define the maximum production rate
MAX_PRODUCTION_RATE = 10


# Supply rate for new raw materials
@component.add(
    name="Supply Rate",
    units="Units/Minute",
    limits=(0.0, MAX_SUPPLY_RATE),
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def supply_rate():
    return MAX_SUPPLY_RATE  # Fixed maximum supply rate

# Production rate for each workstation
@component.add(
    name="Production Rate",
    units="Units/Minute",
    limits=(0.0, np.nan),
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"supply_rate": 1}
)
def production_rate():
    return min(supply_rate(), MAX_SUPPLY_RATE)  # Production rate limited by supply rate


# Adjusted supply rate to account for recycling and supply
@component.add(
    name="Adjusted Supply Rate",
    units="Units/Minute",
    limits=(0.0, MAX_SUPPLY_RATE),
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"supply_rate": 1, "recycled_materials": 1}
)
def adjusted_supply_rate():
    # Calculate the total available materials (new supply + recycled)
    total_materials = supply_rate() + recycled_materials()
    # Ensure the production rate does not exceed the maximum rate
    return min(total_materials, MAX_PRODUCTION_RATE)

@component.add(
    name="Recycled Materials",
    units="Units",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"inventory_7": 1, "recycling_rate": 1}
)
def recycled_materials():
    return recycling_rate() * inventory_7()

# Buffers between workstations
@component.add(
    name="Buffer Size",
    units="Units",
    comp_type="Constant",
    comp_subtype="Normal",
)
def buffer_size():
    return 50  # Example buffer size for all buffers

# Define separate processing times for each workstation
@component.add(
    name="Processing Time 1",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_1():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

@component.add(
    name="Processing Time 2",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_2():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

@component.add(
    name="Processing Time 3",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_3():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

@component.add(
    name="Processing Time 4",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_4():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

@component.add(
    name="Processing Time 5",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_5():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

@component.add(
    name="Processing Time 6",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_6():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

@component.add(
    name="Processing Time 7",
    units="Minutes",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def processing_time_7():
    return np.random.uniform(0.8, 1.2)  # Variable processing time between 0.8 and 1.2 minutes

# Define carbon emissions rate for each workstation
@component.add(
    name="Carbon Emissions Rate 1",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_1():
    return 0.5  # Example emissions rate in kg CO2 per minute

@component.add(
    name="Carbon Emissions Rate 2",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_2():
    return 0.6  # Example emissions rate in kg CO2 per minute

@component.add(
    name="Carbon Emissions Rate 3",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_3():
    return 0.7  # Example emissions rate in kg CO2 per minute

@component.add(
    name="Carbon Emissions Rate 4",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_4():
    return 0.8  # Example emissions rate in kg CO2 per minute

@component.add(
    name="Carbon Emissions Rate 5",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_5():
    return 0.9  # Example emissions rate in kg CO2 per minute

@component.add(
    name="Carbon Emissions Rate 6",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_6():
    return 1.0  # Example emissions rate in kg CO2 per minute

@component.add(
    name="Carbon Emissions Rate 7",
    units="kg CO2/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
)
def carbon_emissions_rate_7():
    return 1.1  # Example emissions rate in kg CO2 per minute

# Define the recycling rate
@component.add(
    name="Recycling Rate",
    units="%",
    comp_type="Constant",
    comp_subtype="Normal",
)
def recycling_rate():
    return 0.2  # Example recycling rate of 20%

# Define the carbon emissions rate for the supply
CARBON_EMISSIONS_RATE_SUPPLY = 2.0  # Example emissions rate in kg CO2 per unit supplied

# Calculate carbon emissions for supply
@component.add(
    name="Carbon Emissions Supply",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_supply": 1},
    other_deps={"_integ_carbon_emissions_supply": {"initial": {}, "step": {"supply_rate": 1}}}
)
def carbon_emissions_supply():
    return _integ_carbon_emissions_supply()

_integ_carbon_emissions_supply = Integ(
    lambda: CARBON_EMISSIONS_RATE_SUPPLY * supply_rate() , lambda: 0, "_integ_carbon_emissions_supply"
)

# Calculate carbon emissions for supply with recycling
@component.add(
    name="Carbon Emissions Supply with Recycling",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_supply_with_recycling": 1},
    other_deps={"_integ_carbon_emissions_supply_with_recycling": {"initial": {}, "step": {"production_rate": 1, "recycling_rate": 1}}}
)
def carbon_emissions_supply_with_recycling():
    return _integ_carbon_emissions_supply_with_recycling()

_integ_carbon_emissions_supply_with_recycling = Integ(
    lambda: CARBON_EMISSIONS_RATE_SUPPLY * (supply_rate() - production_rate() * recycling_rate()), lambda: 0, "_integ_carbon_emissions_supply_with_recycling"
)


# Define the energy consumption per unit and the emission factor
ENERGY_CONSUMPTION_PER_UNIT = 0.5  # kWh per unit

# Calculate carbon emissions for each workstation
@component.add(
    name="Carbon Emissions 1",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_1": 1},
    other_deps={"_integ_carbon_emissions_1": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_1": 1}}}
)
def carbon_emissions_1():
    return _integ_carbon_emissions_1()

_integ_carbon_emissions_1 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_1(), lambda: 0, "_integ_carbon_emissions_1"
)


@component.add(
    name="Carbon Emissions 2",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_2": 1},
    other_deps={"_integ_carbon_emissions_2": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_2": 1}}}
)
def carbon_emissions_2():
    return _integ_carbon_emissions_2()

_integ_carbon_emissions_2 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_2(), lambda: 0, "_integ_carbon_emissions_2"
)

@component.add(
    name="Carbon Emissions 3",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_3": 1},
    other_deps={"_integ_carbon_emissions_3": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_3": 1}}}
)
def carbon_emissions_3():
    return _integ_carbon_emissions_3()

_integ_carbon_emissions_3 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_3(), lambda: 0, "_integ_carbon_emissions_3"
)

@component.add(
    name="Carbon Emissions 4",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_4": 1},
    other_deps={"_integ_carbon_emissions_4": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_4": 1}}}
)
def carbon_emissions_4():
    return _integ_carbon_emissions_4()

_integ_carbon_emissions_4 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_4(), lambda: 0, "_integ_carbon_emissions_4"
)
@component.add(
    name="Carbon Emissions 5",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_5": 1},
    other_deps={"_integ_carbon_emissions_5": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_5": 1}}}
)
def carbon_emissions_5():
    return _integ_carbon_emissions_5()

_integ_carbon_emissions_5 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_5(), lambda: 0, "_integ_carbon_emissions_5"
)

@component.add(
    name="Carbon Emissions 6",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_6": 1},
    other_deps={"_integ_carbon_emissions_6": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_6": 1}}}
)
def carbon_emissions_6():
    return _integ_carbon_emissions_6()

_integ_carbon_emissions_6 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_6(), lambda: 0, "_integ_carbon_emissions_6"
)

@component.add(
    name="Carbon Emissions 7",
    units="kg CO2",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_carbon_emissions_7": 1},
    other_deps={"_integ_carbon_emissions_7": {"initial": {}, "step": {"production_rate": 1, "carbon_emissions_rate_7": 1}}}
)
def carbon_emissions_7():
    return _integ_carbon_emissions_7()

_integ_carbon_emissions_7 = Integ(
    lambda: production_rate() * ENERGY_CONSUMPTION_PER_UNIT * carbon_emissions_rate_7(), lambda: 0, "_integ_carbon_emissions_7"
)


# Workstation 1
@component.add(
    name="Inventory 1",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_1": 1},
    other_deps={"_integ_inventory_1": {"initial": {}, "step": {"production_rate": 1, "processing_time_1": 1}}}
)
def inventory_1():
    return _integ_inventory_1()

_integ_inventory_1 = Integ(
    lambda: production_rate() - processing_time_1(), lambda: 0, "_integ_inventory_1"
)


# Workstation 2
@component.add(
    name="Inventory 2",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_2": 1},
    other_deps={"_integ_inventory_2": {"initial": {}, "step": {"production_rate": 1, "processing_time_2": 1}}},
)
def inventory_2():
    return _integ_inventory_2()

_integ_inventory_2 = Integ(
    lambda: production_rate() - processing_time_2(), lambda: 0, "_integ_inventory_2"
)

# Workstation 3
@component.add(
    name="Inventory 3",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_3": 1},
    other_deps={"_integ_inventory_3": {"initial": {}, "step": {"production_rate": 1, "processing_time_3": 1}}},
)
def inventory_3():
    return _integ_inventory_3()

_integ_inventory_3 = Integ(
    lambda: production_rate() - processing_time_3(), lambda: 0, "_integ_inventory_3"
)

# Workstation 4
@component.add(
    name="Inventory 4",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_4": 1},
    other_deps={"_integ_inventory_4": {"initial": {}, "step": {"production_rate": 1, "processing_time_4": 1}}},
)
def inventory_4():
    return _integ_inventory_4()

_integ_inventory_4 = Integ(
    lambda: production_rate() - processing_time_4(), lambda: 0, "_integ_inventory_4"
)

# Workstation 5
@component.add(
    name="Inventory 5",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_5": 1},
    other_deps={"_integ_inventory_5": {"initial": {}, "step": {"production_rate": 1, "processing_time_5": 1}}},
)
def inventory_5():
    return _integ_inventory_5()

_integ_inventory_5 = Integ(
    lambda: production_rate() - processing_time_5(), lambda: 0, "_integ_inventory_5"
)

# Workstation 6
@component.add(
    name="Inventory 6",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_6": 1},
    other_deps={"_integ_inventory_6": {"initial": {}, "step": {"production_rate": 1, "processing_time_6": 1}}},
)
def inventory_6():
    return _integ_inventory_6()

_integ_inventory_6 = Integ(
    lambda: production_rate() - processing_time_6(), lambda: 0, "_integ_inventory_6"
)

# Workstation 7
@component.add(
    name="Inventory 7",
    units="Units",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory_7": 1},
    other_deps={"_integ_inventory_7": {"initial": {}, "step": {"production_rate": 1, "processing_time_7": 1}}},
)
def inventory_7():
    return _integ_inventory_7()

_integ_inventory_7 = Integ(
    lambda: production_rate() - processing_time_7(), lambda: 0, "_integ_inventory_7"
)
