"""
Python model 'Defects.py'
Translated using PySD
"""

from pathlib import Path
import numpy as np

from pysd.py_backend.functions import pulse
from pysd.py_backend.statefuls import Integ
from pysd.py_backend.lookups import HardcodedLookups
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
    "time_step": lambda: 0.015625,
    "saveper": lambda: time_step(),
}


def _init_outer_references(data):
    for key in data:
        __data[key] = data[key]


@component.add(name="Time")
def time():
    """
    Current time of the model.
    """
    return __data["time"]()


@component.add(
    name="FINAL TIME", units="Day", comp_type="Constant", comp_subtype="Normal"
)
def final_time():
    """
    The final time for the simulation.
    """
    return __data["time"].final_time()


@component.add(
    name="INITIAL TIME", units="Day", comp_type="Constant", comp_subtype="Normal"
)
def initial_time():
    """
    The initial time for the simulation.
    """
    return __data["time"].initial_time()


@component.add(
    name="SAVEPER",
    units="Day",
    limits=(0.0, np.nan),
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time_step": 1},
)
def saveper():
    """
    The frequency with which output is stored.
    """
    return __data["time"].saveper()


@component.add(
    name="TIME STEP",
    units="Day",
    limits=(0.0, np.nan),
    comp_type="Constant",
    comp_subtype="Normal",
)
def time_step():
    """
    The time step for the simulation.
    """
    return __data["time"].time_step()


#######################################################################
#                           MODEL VARIABLES                           #
#######################################################################


@component.add(
    name="Influence of Backlog on Speed",
    comp_type="Lookup",
    comp_subtype="Normal",
    depends_on={"__lookup__": "_hardcodedlookup_influence_of_backlog_on_speed"},
)
def influence_of_backlog_on_speed(x, final_subs=None):
    return _hardcodedlookup_influence_of_backlog_on_speed(x, final_subs)


_hardcodedlookup_influence_of_backlog_on_speed = HardcodedLookups(
    [0.0, 5.0, 10.0, 15.0, 20.0, 80.0],
    [0.1, 0.1, 0.09, 0.05, 0.04, 0.04],
    {},
    "interpolate",
    {},
    "_hardcodedlookup_influence_of_backlog_on_speed",
)


@component.add(
    name="Influence of Backlog on Workday",
    comp_type="Lookup",
    comp_subtype="Normal",
    depends_on={"__lookup__": "_hardcodedlookup_influence_of_backlog_on_workday"},
)
def influence_of_backlog_on_workday(x, final_subs=None):
    return _hardcodedlookup_influence_of_backlog_on_workday(x, final_subs)


_hardcodedlookup_influence_of_backlog_on_workday = HardcodedLookups(
    [0.0, 2.76986, 5.53971, 10.3462, 13.1161, 16.5377, 20.5295, 60.0],
    [0.1, 0.128571, 0.188095, 0.347619, 0.416667, 0.452381, 0.469048, 0.5],
    {},
    "interpolate",
    {},
    "_hardcodedlookup_influence_of_backlog_on_workday",
)


@component.add(
    name="Length of workday",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"backlog": 1, "influence_of_backlog_on_workday": 1},
)
def length_of_workday():
    return influence_of_backlog_on_workday(backlog())


@component.add(
    name="Fulfillment Rate",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={
        "number_of_employees": 1,
        "length_of_workday": 1,
        "time_allocated_per_unit": 1,
        "defect_rate": 1,
    },
)
def fulfillment_rate():
    return (
        number_of_employees()
        * length_of_workday()
        / time_allocated_per_unit()
        * (1 - defect_rate())
    )


@component.add(
    name="Time allocated per unit",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"backlog": 1, "influence_of_backlog_on_speed": 1},
)
def time_allocated_per_unit():
    return influence_of_backlog_on_speed(backlog())


@component.add(name="Number of Employees", comp_type="Constant", comp_subtype="Normal")
def number_of_employees():
    return 2


@component.add(
    name="Arrival Rate",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"time": 1},
)
def arrival_rate():
    return 10 + 12 * pulse(__data["time"], 20, width=10)


@component.add(
    name="Backlog",
    comp_type="Stateful",
    comp_subtype="Integ",
    depends_on={"_integ_backlog": 1},
    other_deps={
        "_integ_backlog": {
            "initial": {},
            "step": {"arrival_rate": 1, "fulfillment_rate": 1},
        }
    },
)
def backlog():
    return _integ_backlog()


_integ_backlog = Integ(
    lambda: arrival_rate() - fulfillment_rate(), lambda: 11.7, "_integ_backlog"
)


@component.add(
    name="Defect Rate",
    comp_type="Auxiliary",
    comp_subtype="Normal",
    depends_on={"length_of_workday": 1, "time_allocated_per_unit": 1},
)
def defect_rate():
    return 0.01 * length_of_workday() / time_allocated_per_unit()
