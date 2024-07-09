"""
Python model 'recycling_poc_model.py'
Simplified model with one workstation, production machine, and recycling
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
    "saveper": lambda: 0.125,
}

def _init_outer_references(data):
    for key in data:
        __data[key] = data[key]

@component.add(name="Time")
def time():
    return __data["time"]()

@component.add(name="FINAL TIME", units="Minute", comp_type="Constant", comp_subtype="Normal")
def final_time():
    return _control_vars["final_time"]()

@component.add(name="INITIAL TIME", units="Minute", comp_type="Constant", comp_subtype="Normal")
def initial_time():
    return _control_vars["initial_time"]()

@component.add(name="SAVEPER", units="Minute", comp_type="Auxiliary", comp_subtype="Normal", depends_on={"time_step": 1})
def saveper():
    return _control_vars["saveper"]()

@component.add(name="TIME STEP", units="Minute", comp_type="Constant", comp_subtype="Normal")
def time_step():
    return _control_vars["time_step"]()

#######################################################################
#                           MODEL VARIABLES                           #
#######################################################################

# Quantité de matière utilisée par heure (en kg)
SUPPLY_QUANTITY_PER_HOUR = 900

@component.add(
    name="Supply Rate",
    units="kg/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal"
)
def supply_rate():
    return (SUPPLY_QUANTITY_PER_HOUR) # Conversion en kg par minute, ajout des matériaux recyclés

@component.add(
    name="Matière Première Utilisée",
    units="kg/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"supply_rate": 1, "recycled_materials": 1}
)
def matiere_premiere_utilisee():
    return supply_rate() + recycled_materials()

@component.add(
    name="Production Rate",
    units="kg/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"matiere_premiere_utilisee": 1}
)
def production_rate():
    return matiere_premiere_utilisee() * 0.95  # 90% de la matière première est utilisée en production

@component.add(
    name="Finished Products",
    units="Units/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"production_rate": 1}
)
def finished_products():
    return round(production_rate() / 10 ) # Ex. 1 unité produite pour chaque 10 kg de matière transformée


@component.add(
    name="Recycling Rate",
    units="%",
    comp_type="Constant",
    comp_subtype="Normal"
)
def recycling_rate():
    return 0.2  # Taux de recyclage de 20%

@component.add(
    name="Recycled Materials",
    units="kg/Minute",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"production_rate": 1, "recycling_rate": 1}
)
def recycled_materials():
    return recycling_rate() * production_rate()


@component.add(
    name="Inventory",
    units="kg",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_inventory": 1},
    other_deps={"_integ_inventory": {"initial": {}, "step": {"production_rate": 1}}}
)
def inventory():
    return _integ_inventory()

_integ_inventory = Integ(
    lambda: finished_products(), lambda: 0, "_integ_inventory"
)
