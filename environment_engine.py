# environment_engine.py

import math
from logistics_engine import distances

# Define distances to Paris for each country


# CO2 emission factors (in kg CO2 per ton-km)
co2_factors = {
    'road': 0.096,
    'train': 0.028,
    'air': 2.1
}

# Production CO2 factors (in kg CO2 per unit produced)
production_co2_factors = {
    'Texas': 3.5,
    'California': 3,
    'UK': 3,
    'France': 2
}

def calculate_distribution_co2_emissions(source, destination, amount):
    """Calculate the CO2 emissions for transporting a given quantity from source to destination."""
    # Default mode is air unless specified otherwise
    mode = 'air'
    
    if source == 'France' and destination == 'France':
        mode = 'road'
    elif source == 'France' and destination == 'UK':
        mode = 'train'
    elif source == 'UK' and destination == 'France':
        mode = 'train'
    
    # Calculate distance
    distance = distances.get((source, destination), 0)
    
    # Calculate CO2 emissions
    return amount * distance * co2_factors[mode] / 1000

def calculate_production_co2_emissions(country, amount):
    co2_factor = production_co2_factors.get(country, 0)
    return amount * co2_factor
