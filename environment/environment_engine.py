# environment_engine.py

import math
from distribution.distribution_engine import distances

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


def calculate_lca_production_IFE_raw(total_seats_made):
    """
    Calculate LCA indicators based on the number of seats made using EF 3.0 format with raw units, here with IFE production.
    
    :param total_seats_made: Number of seats produced
    :return: Dictionary with LCA indicators
    """
    lca_indicators = {
        'Acidification': total_seats_made * 13.09237607,  # [Mole of H+ eq.]
        'Climate Change': total_seats_made * 2582.287353,  # [kg CO2 eq.]
        'Ecotoxicity, freshwater': total_seats_made * 232243.8539,  #  [CTUe]
        'Eutrophication, freshwater': total_seats_made * 2.309760193,  # [kg P eq.]
        'Eutrophication, marine': total_seats_made * 3.704748951,  #  [kg N eq.]
        'Eutrophication, terrestrial': total_seats_made * 38.02415126,  # [Mole of N eq.]
        'Human toxicity, cancer': total_seats_made * 3.95365e-06,  # [CTUh]
        'Human toxicity, non-cancer': total_seats_made * 9.79493e-05,  # [CTUh]
        'Ionising radiation, human health': total_seats_made * 443.5525878,  # [kBq U235 eq.]
        'Land Use': total_seats_made * 10624.50424,  # [Pt]
        'Ozone depletion': total_seats_made * 0.000140771,  # [kg CFC-11 eq.]
        'Particulate matter': total_seats_made * 0.000137194,  #  [Disease incidences]
        'Photochemical ozone formation, human health': total_seats_made * 8.273784513,  #  [kg NMVOC eq.]
        'Resource use, fossils': total_seats_made * 34240.35081,  #  [MJ]
        'Resource use, mineral and metals': total_seats_made * 0.674237358,  # [kg Sb eq.]
        'Water use': total_seats_made * 43061.84508  # [m³ world equiv.]
    }
    return lca_indicators

def calculate_lca_production_raw(total_seats_made):
    """
    Calculate LCA indicators based on the number of seats made using EF 3.0 format with raw units, here without IFE production.
    
    :param total_seats_made: Number of seats produced
    :return: Dictionary with LCA indicators
    """
    lca_indicators = {
        'Acidification': total_seats_made * 6.490526071,  # [Mole of H+ eq.]
        'Climate Change': total_seats_made * 1220.749353,  # [kg CO2 eq.]
        'Ecotoxicity, freshwater': total_seats_made * 8262.833891,  #  [CTUe]
        'Eutrophication, freshwater': total_seats_made * 0.026654693,  # [kg P eq.]
        'Eutrophication, marine': total_seats_made * 1.081066951,  #  [kg N eq.]
        'Eutrophication, terrestrial': total_seats_made * 14.96747126,  # [Mole of N eq.]
        'Human toxicity, cancer': total_seats_made * 2.32202e-06,  # [CTUh]
        'Human toxicity, non-cancer': total_seats_made * 1.8811e-05,  # [CTUh]
        'Ionising radiation, human health': total_seats_made * 237.1920013,  # [kBq U235 eq.]
        'Land Use': total_seats_made * 3141.142985,  # [Pt]
        'Ozone depletion': total_seats_made * 9.73286e-06,  # [kg CFC-11 eq.]
        'Particulate matter': total_seats_made * 6.53679e-05,  #  [Disease incidences]
        'Photochemical ozone formation, human health': total_seats_made * 2.535363827,  #  [kg NMVOC eq.]
        'Resource use, fossils': total_seats_made * 16664.58542,  #  [MJ]
        'Resource use, mineral and metals': total_seats_made * 0.015825398,  # [kg Sb eq.]
        'Water use': total_seats_made * 3913.457619 # [m³ world equiv.]
    }
    return lca_indicators

def calculate_lca_indicators_pers_eq(total_seats_made):
    """
    Calculate LCA indicators based on the number of seats made using EF 3.0 format (pers. eq.).
    
    :param total_seats_made: Number of seats produced
    :return: Dictionary with LCA indicators
    """
    lca_indicators = {
        'Acidification': total_seats_made * 0.252205866014651,  # pers. eq.
        'Climate Change': total_seats_made * 1.17634325257031,  # pers. eq.
        'Ecotoxicity, freshwater': total_seats_made * 1.68770297069081,  # pers. eq.
        'Eutrophication, freshwater': total_seats_made * 0.644605414956476,  # pers. eq.
        'Eutrophication, marine': total_seats_made * 0.100959582665168,  # pers. eq.
        'Eutrophication, terrestrial': total_seats_made * 0.144348763282092,  # pers. eq.
        'Human toxicity, cancer': total_seats_made * 0.0864879317605519,  # pers. eq.
        'Human toxicity, non-cancer': total_seats_made * 0.172399381072778,  # pers. eq.
        'Ionising radiation, human health': total_seats_made * 0.0831667270412339,  # pers. eq.
        'Land Use': total_seats_made * 0.0337028028743999,  # pers. eq.
        'Ozone depletion': total_seats_made * 0.00266218991861066,  # pers. eq.
        'Particulate matter': total_seats_made * 0.34122498549978,  # pers. eq.
        'Photochemical ozone formation, human health': total_seats_made * 0.179067786872986,  # pers. eq.
        'Resource use, fossils': total_seats_made * 0.765188055661992,  # pers. eq.
        'Resource use, mineral and metals': total_seats_made * 12.7985017792711,  # pers. eq.
        'Water use': total_seats_made * 5.27315165400531  # pers. eq.
    }
    return lca_indicators


def calculate_lca_indicators_usage_phase(total_seats_made, seat_weight=130):
    """
    Calculate LCA indicators for the usage phase based on alternative coefficients.
    
    :param total_seats_made: Number of seats produced and used
    :return: Dictionary with LCA indicators for usage phase
    """

    # Ajustement de Climate Change basé sur le poids du siège
    climate_change_base = 191.7976657  # Impact pour un siège de 130 kg
    climate_change_adjusted = climate_change_base * (seat_weight / 130)

    # Coefficients for the usage phase
    lca_indicators_usage = {
        'Acidification': total_seats_made * 32.89490848,  # pers. eq.
        'Climate Change': total_seats_made * climate_change_adjusted,  # pers. eq.
        'Ecotoxicity, freshwater': total_seats_made * 32.70539059,  # pers. eq.
        'Eutrophication, freshwater': total_seats_made * 0.04010944,  # pers. eq.
        'Eutrophication, marine': total_seats_made * 20.18520851,  # pers. eq.
        'Eutrophication, terrestrial': total_seats_made * 30.64722193,  # pers. eq.
        'Human toxicity, cancer': total_seats_made * 1.69458949,  # pers. eq.
        'Human toxicity, non-cancer': total_seats_made * 4.886710522,  # pers. eq.
        'Ionising radiation, human health': total_seats_made * 0.138318785,  # pers. eq.
        'Land Use': total_seats_made * 0.021393943,  # pers. eq.
        'Ozone depletion': total_seats_made * 0.000119436,  # pers. eq.
        'Particulate matter': total_seats_made * 14.16878515,  # pers. eq.
        'Photochemical ozone formation, human health': total_seats_made * 44.7173626,  # pers. eq.
        'Resource use, fossils': total_seats_made * 127.7143008,  # pers. eq.
        'Resource use, mineral and metals': total_seats_made * 0.304359535,  # pers. eq.
        'Water use': total_seats_made * 0.086087309  # pers. eq.
    }
    return lca_indicators_usage

def calculate_lca_indicators_total(total_seats_made):
    """
    Calculate LCA indicators for the usage phase based on alternative coefficients.
    
    :param total_seats_made: Number of seats produced and used
    :return: Dictionary with LCA indicators for usage phase
    """
    # Coefficients for the usage phase
    lca_indicators_total = {
        'Acidification': total_seats_made * 33.1471143460147,  # pers. eq.
        'Climate Change': total_seats_made * 192.97400894857,  # pers. eq.
        'Ecotoxicity, freshwater': total_seats_made * 34.3930935626908,  # pers. eq.
        'Eutrophication, freshwater': total_seats_made * 0.684714854956476,  # pers. eq.
        'Eutrophication, marine': total_seats_made * 20.2861680946652,  # pers. eq.
        'Eutrophication, terrestrial': total_seats_made * 30.7915706944821,  # pers. eq.
        'Human toxicity, cancer': total_seats_made * 1.78107742136055,  # pers. eq.
        'Human toxicity, non-cancer': total_seats_made * 5.05910990339973,  # pers. eq.
        'Ionising radiation, human health': total_seats_made * 0.221485511553737,  # pers. eq.
        'Land Use': total_seats_made * 0.0550967460501254,  # pers. eq.
        'Ozone depletion': total_seats_made * 0.00278162628444284,  # pers. eq.
        'Particulate matter': total_seats_made * 14.5100101363764,  # pers. eq.
        'Photochemical ozone formation, human health': total_seats_made * 44.8964303908889,  # pers. eq.
        'Resource use, fossils': total_seats_made * 128.4794888717,  # pers. eq.
        'Resource use, mineral and metals': total_seats_made * 13.1028613145325,  # pers. eq.
        'Water use': total_seats_made * 5.35923896308499  # pers. eq.
    }
    return lca_indicators_total


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


def calculate_supply_co2_supply_emissions(distance, quantity, co2_per_km_ton=0.02):
    """
    Calcule les coûts et les émissions liés au transport.
    
    :param distance: Distance parcourue (en km)
    :param quantity: Quantité transportée (en tonnes)
    :param cost_per_km_ton: Coût par km par tonne
    :param co2_per_km_ton: Émissions de CO2 par km par tonne
    :return: Dictionnaire contenant le coût et les émissions
    """

    emissions = distance * quantity * co2_per_km_ton
    return  emissions

def calculate_total_co2_emissions(loc_prod, source, co2_emissions,production_co2_emissions):

    total_emissions = {location: 0.0 for location in loc_prod}

    for i, source_index in enumerate(source):
            location = loc_prod[source_index]
            # Add distribution CO2 emissions
            total_emissions[location] += co2_emissions[i]
            # Add production CO2 emissions
            total_emissions[location] += production_co2_emissions[source_index]

    return total_emissions