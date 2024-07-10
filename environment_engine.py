# environment_engine.py

import math

# Define distances to Paris for each country
distances_to_paris = {
    'Canada': 6000,   # by air
    'France': 800,    # by road
    'USA': 6000,      # by air
    'Brazil': 7000,   # by air
    'Japan': 10000    # by air
}

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

def calculate_co2_emissions(country, amount):
    mode = 'air'  # Default mode
    if country == 'France':
        mode = 'road'
    # Calculate distance
    distance = distances_to_paris.get(country, 0)
    # Calculate CO2 emissions
    return amount * distance * co2_factors[mode] / 1000

def calculate_production_co2_emissions(country, amount):
    co2_factor = production_co2_factors.get(country, 0)
    return amount * co2_factor
