
# Default parameters for the supply simulation (non-OOP, functional)
DEFAULT_RANDOM_SEED = 42

PROCESSING_TIME_DAYS = {
    "Matière 1ère": 2.0,
    "1ère transformation": 3.0,
    "Tier 1": 4.0,
    "Client": 0.0,
}

ROLE_CAPACITY = {
    # Capacités élargies pour réduire les files d'attente
    "Matière 1ère": 30,
    "1ère transformation": 24,
    "Tier 1": 18,
    "Client": 999999,
}

SPEEDS_KMPH = {"road": 60, "rail": 50, "sea": 30, "air": 750}
INTERCONTINENTAL_MODE = "air"
TRANSPORT_OVERRIDE = {}
PROCESSING_JITTER = 0.2
TRANSIT_JITTER = 0.15

DEFAULT_UNITS_PER_COMPONENT = 5
# Horizon suffisamment long tout en restant compact (packaging/transport exclus)
SIM_HORIZON_DAYS = 200

EVENTS_CSV = "analysis/supply_events.csv"
ARRIVALS_CSV = "analysis/supply_arrivals.csv"
