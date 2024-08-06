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


def calculate_lca_indicators(total_seats_made):
    """
    Calculate LCA indicators based on the number of seats made using EF 3.0 format.
    
    :param total_seats_made: Number of seats produced
    :return: Dictionary with LCA indicators
    """
    lca_indicators = {
        'Climate Change': total_seats_made * 50,  # kg CO2 eq
        'Ozone Depletion': total_seats_made * 0.0005,  # kg CFC-11 eq
        'Terrestrial Ecotoxicity': total_seats_made * 2,  # CTUe
        'Freshwater Ecotoxicity': total_seats_made * 1.5,  # CTUe
        'Terrestrial Acidification': total_seats_made * 0.3,  # mol H+ eq
        'Marine Eutrophication': total_seats_made * 0.1,  # kg N eq
        'Freshwater Eutrophication': total_seats_made * 0.05,  # kg P eq
        'Water Use': total_seats_made * 31652.52,  # m³
        'Fossil Fuel Depletion': total_seats_made * 2000,  # MJ
        'Particulate Matter Formation': total_seats_made * 0.02  # kg PM2.5 eq
    }
    return lca_indicators

def calculate_lca_indicators_pers_eq(total_seats_made):
    """
    Calculate LCA indicators based on the number of seats made using EF 3.0 format (pers. eq.).
    
    :param total_seats_made: Number of seats produced
    :return: Dictionary with LCA indicators
    """
    lca_indicators = {
        'Acidification': total_seats_made * 0.3,  # pers. eq.
        'Climate Change': total_seats_made * 1.2,  # pers. eq.
        'Ecotoxicity, freshwater': total_seats_made * 1.7,  # pers. eq.
        'Eutrophication, freshwater': total_seats_made * 0.6,  # pers. eq.
        'Eutrophication, marine': total_seats_made * 0.1,  # pers. eq.
        'Eutrophication, terrestrial': total_seats_made * 0.1,  # pers. eq.
        'Human toxicity, cancer': total_seats_made * 0.1,  # pers. eq.
        'Human toxicity, non-cancer': total_seats_made * 0.2,  # pers. eq.
        'Ionising radiation, human health': total_seats_made * 0.1,  # pers. eq.
        'Land Use': total_seats_made * 0.0,  # pers. eq.
        'Ozone depletion': total_seats_made * 0.0,  # pers. eq.
        'Particulate matter': total_seats_made * 0.3,  # pers. eq.
        'Photochemical ozone formation, human health': total_seats_made * 0.2,  # pers. eq.
        'Resource use, fossils': total_seats_made * 0.8,  # pers. eq.
        'Resource use, mineral and metals': total_seats_made * 12.8,  # pers. eq.
        'Water use': total_seats_made * 5.3  # pers. eq.
    }
    return lca_indicators


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
