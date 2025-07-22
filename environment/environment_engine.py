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
    'France': 1
}


def calculate_lca_production_IFE_raw(total_seats_made, site, seat_weight=130):
    """
    Calculate LCA indicators (production phase) using IFE data, adjusted by seat_weight.

    :param total_seats_made: Number of seats produced
    :param site: Production location
    :param seat_weight: Weight of the seat in kg (default 130)
    :return: Dict of LCA indicators [raw units]
    """
    weight_factor = seat_weight / 130

    lca_indicators = {
        'Acidification': total_seats_made * 13.09237607 * weight_factor,  # [Mole of H+ eq.]
        'Climate Change': total_seats_made * 2582.287353 * production_co2_factors[site] * weight_factor,  # [kg CO2 eq.]
        'Ecotoxicity, freshwater': total_seats_made * 232243.8539 * weight_factor,  # [CTUe]
        'Eutrophication, freshwater': total_seats_made * 2.309760193 * weight_factor,  # [kg P eq.]
        'Eutrophication, marine': total_seats_made * 3.704748951 * weight_factor,  # [kg N eq.]
        'Eutrophication, terrestrial': total_seats_made * 38.02415126 * weight_factor,  # [Mole of N eq.]
        'Human toxicity, cancer': total_seats_made * 3.95365e-06 * weight_factor,  # [CTUh]
        'Human toxicity, non-cancer': total_seats_made * 9.79493e-05 * weight_factor,  # [CTUh]
        'Ionising radiation, human health': total_seats_made * 443.5525878 * weight_factor,  # [kBq U235 eq.]
        'Land Use': total_seats_made * 10624.50424 * weight_factor,  # [Pt]
        'Ozone depletion': total_seats_made * 0.000140771 * weight_factor,  # [kg CFC-11 eq.]
        'Particulate matter': total_seats_made * 0.000137194 * weight_factor,  # [Disease incidences]
        'Photochemical ozone formation, human health': total_seats_made * 8.273784513 * weight_factor,  # [kg NMVOC eq.]
        'Resource use, fossils': total_seats_made * 34240.35081 * weight_factor,  # [MJ]
        'Resource use, mineral and metals': total_seats_made * 0.674237358 * weight_factor,  # [kg Sb eq.]
        'Water use': total_seats_made * 43061.84508 * weight_factor  # [m³ world equiv.]
    }
    return lca_indicators

def calculate_lca_production_raw(total_seats_made, site, seat_weight=130):
    """
    Calculate LCA indicators (production phase, no IFE), adjusted by seat_weight.

    :return: Dict [raw units]
    """
    weight_factor = seat_weight / 130

    lca_indicators = {
        'Acidification': total_seats_made * 6.490526071 * weight_factor,  # [Mole of H+ eq.]
        'Climate Change': total_seats_made * 1220.749353 * production_co2_factors[site] * weight_factor,  # [kg CO2 eq.]
        'Ecotoxicity, freshwater': total_seats_made * 8262.833891 * weight_factor,  # [CTUe]
        'Eutrophication, freshwater': total_seats_made * 0.026654693 * weight_factor,  # [kg P eq.]
        'Eutrophication, marine': total_seats_made * 1.081066951 * weight_factor,  # [kg N eq.]
        'Eutrophication, terrestrial': total_seats_made * 14.96747126 * weight_factor,  # [Mole of N eq.]
        'Human toxicity, cancer': total_seats_made * 2.32202e-06 * weight_factor,  # [CTUh]
        'Human toxicity, non-cancer': total_seats_made * 1.8811e-05 * weight_factor,  # [CTUh]
        'Ionising radiation, human health': total_seats_made * 237.1920013 * weight_factor,  # [kBq U235 eq.]
        'Land Use': total_seats_made * 3141.142985 * weight_factor,  # [Pt]
        'Ozone depletion': total_seats_made * 9.73286e-06 * weight_factor,  # [kg CFC-11 eq.]
        'Particulate matter': total_seats_made * 6.53679e-05 * weight_factor,  # [Disease incidences]
        'Photochemical ozone formation, human health': total_seats_made * 2.535363827 * weight_factor,  # [kg NMVOC eq.]
        'Resource use, fossils': total_seats_made * 16664.58542 * weight_factor,  # [MJ]
        'Resource use, mineral and metals': total_seats_made * 0.015825398 * weight_factor,  # [kg Sb eq.]
        'Water use': total_seats_made * 3913.457619 * weight_factor  # [m³ world equiv.]
    }
    return lca_indicators


def calculate_lca_indicators_pers_eq(total_seats_made, site, seat_weight=130):
    """
    Calculate personal equipment LCA indicators [pers. eq.], adjusted by seat_weight
    """
    weight_factor = seat_weight / 130

    lca_indicators = {
        'Acidification': total_seats_made * 0.252205866014651 * weight_factor,  # [pers. eq.]
        'Climate Change': total_seats_made * 1.17634325257031 * production_co2_factors[site] * weight_factor,  # [pers. eq.]
        'Ecotoxicity, freshwater': total_seats_made * 1.68770297069081 * weight_factor,  # [pers. eq.]
        'Eutrophication, freshwater': total_seats_made * 0.644605414956476 * weight_factor,  # [pers. eq.]
        'Eutrophication, marine': total_seats_made * 0.100959582665168 * weight_factor,  # [pers. eq.]
        'Eutrophication, terrestrial': total_seats_made * 0.144348763282092 * weight_factor,  # [pers. eq.]
        'Human toxicity, cancer': total_seats_made * 0.0864879317605519 * weight_factor,  # [pers. eq.]
        'Human toxicity, non-cancer': total_seats_made * 0.172399381072778 * weight_factor,  # [pers. eq.]
        'Ionising radiation, human health': total_seats_made * 0.0831667270412339 * weight_factor,  # [pers. eq.]
        'Land Use': total_seats_made * 0.0337028028743999 * weight_factor,  # [pers. eq.]
        'Ozone depletion': total_seats_made * 0.00266218991861066 * weight_factor,  # [pers. eq.]
        'Particulate matter': total_seats_made * 0.34122498549978 * weight_factor,  # [pers. eq.]
        'Photochemical ozone formation, human health': total_seats_made * 0.179067786872986 * weight_factor,  # [pers. eq.]
        'Resource use, fossils': total_seats_made * 0.765188055661992 * weight_factor,  # [pers. eq.]
        'Resource use, mineral and metals': total_seats_made * 12.7985017792711 * weight_factor,  # [pers. eq.]
        'Water use': total_seats_made * 5.27315165400531 * weight_factor  # [pers. eq.]
    }
    return lca_indicators


def calculate_lca_indicators_usage_phase(total_seats_made, seat_weight=130):
    """
    Calculate LCA indicators for the usage phase based on coefficients.
    All indicators are scaled proportionally to seat_weight.

    :param total_seats_made: Number of seats used
    :param seat_weight: Actual seat weight (default 130 kg)
    :return: Dictionary with LCA indicators [pers. eq.]
    """
    weight_factor = seat_weight / 130

    lca_indicators_usage = {
        'Acidification': total_seats_made * 32.89490848 * weight_factor,  # [pers. eq.]
        'Climate Change': total_seats_made * 191.7976657 * weight_factor,  # [pers. eq.]
        'Ecotoxicity, freshwater': total_seats_made * 32.70539059 * weight_factor,  # [pers. eq.]
        'Eutrophication, freshwater': total_seats_made * 0.04010944 * weight_factor,  # [pers. eq.]
        'Eutrophication, marine': total_seats_made * 20.18520851 * weight_factor,  # [pers. eq.]
        'Eutrophication, terrestrial': total_seats_made * 30.64722193 * weight_factor,  # [pers. eq.]
        'Human toxicity, cancer': total_seats_made * 1.69458949 * weight_factor,  # [pers. eq.]
        'Human toxicity, non-cancer': total_seats_made * 4.886710522 * weight_factor,  # [pers. eq.]
        'Ionising radiation, human health': total_seats_made * 0.138318785 * weight_factor,  # [pers. eq.]
        'Land Use': total_seats_made * 0.021393943 * weight_factor,  # [pers. eq.]
        'Ozone depletion': total_seats_made * 0.000119436 * weight_factor,  # [pers. eq.]
        'Particulate matter': total_seats_made * 14.16878515 * weight_factor,  # [pers. eq.]
        'Photochemical ozone formation, human health': total_seats_made * 44.7173626 * weight_factor,  # [pers. eq.]
        'Resource use, fossils': total_seats_made * 127.7143008 * weight_factor,  # [pers. eq.]
        'Resource use, mineral and metals': total_seats_made * 0.304359535 * weight_factor,  # [pers. eq.]
        'Water use': total_seats_made * 0.086087309 * weight_factor  # [pers. eq.]
    }
    return lca_indicators_usage


def calculate_lca_indicators_total(total_seats_made, site, seat_weight=130):
    """
    Sum usage and personal LCA indicators.
    """
    usage = calculate_lca_indicators_usage_phase(total_seats_made, seat_weight)
    pers_eq = calculate_lca_indicators_pers_eq(total_seats_made, site, seat_weight)

    total = {}
    for indicator in usage:
        total[indicator] = usage[indicator] + pers_eq.get(indicator, 0)

    return total


def calculate_distribution_co2_emissions(source, destination, amount, seat_weight=130):
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
    weight_factor = seat_weight / 130
    return weight_factor*amount * distance * co2_factors[mode] / 1000

def calculate_production_co2_emissions(country, amount):
    co2_factor = production_co2_factors.get(country, 0)
    return amount * co2_factor


def calculate_supply_co2_supply_emissions(distance, quantity, co2_per_km_ton=0.02, seat_weight = 130):
    """
    Calcule les coûts et les émissions liés au transport.
    
    :param distance: Distance parcourue (en km)
    :param quantity: Quantité transportée (en tonnes)
    :param cost_per_km_ton: Coût par km par tonne
    :param co2_per_km_ton: Émissions de CO2 par km par tonne
    :return: Dictionnaire contenant le coût et les émissions
    """
    weight_factor = seat_weight / 130
    emissions = weight_factor * distance * quantity * co2_per_km_ton
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