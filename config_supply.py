
# Default parameters for the supply simulation (non-OOP, functional)
DEFAULT_RANDOM_SEED = 42

PROCESSING_TIME_DAYS = {
    "Matière 1ère": 2.0,
    "1ère transformation": 3.0,
    "Tier 1": 4.0,
    "Client": 0.0,
}

ROLE_CAPACITY = {
    "Matière 1ère": 10,
    "1ère transformation": 8,
    "Tier 1": 6,
    "Client": 999999,
}

SPEEDS_KMPH = {"road": 60, "rail": 50, "sea": 30, "air": 750}
INTERCONTINENTAL_MODE = "air"
TRANSPORT_OVERRIDE = {}
PROCESSING_JITTER = 0.2
TRANSIT_JITTER = 0.15

DEFAULT_UNITS_PER_COMPONENT = 5
SIM_HORIZON_DAYS = 60

EVENTS_CSV = "supply_events.csv"
ARRIVALS_CSV = "supply_arrivals.csv"
