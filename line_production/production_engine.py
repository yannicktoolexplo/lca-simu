# production_engine.py

import os
import math
import pandas as pd
import copy

def calculate_capacity_limits(data):
    """Calculate the capacity limits for each plant based on the total seats made."""
    nos_texas_low = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_texas_high = math.ceil(1.2 * data['Total Seats made'][1][-1])
    nos_california_low = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_california_high = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_UK_low = math.ceil(0.15 * data['Total Seats made'][1][-1])
    nos_UK_high = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_france_low = math.ceil(0.45 * data['Total Seats made'][1][-1])
    nos_france_high = math.ceil(0.9 * data['Total Seats made'][1][-1])

    capacity_limits = {
        'Texas': (nos_texas_low, nos_texas_high),
        'California': (nos_california_low, nos_california_high),
        'UK': (nos_UK_low, nos_UK_high),
        'France': (nos_france_low, nos_france_high)
    }
    return capacity_limits


def load_fixed_and_variable_costs(freight_costs):
    """Load fixed and variable costs from Excel files."""
    absolute_path = os.path.dirname(__file__)
    
    fixed_costs = pd.read_excel(os.path.join(absolute_path, 'data/fixed_cost.xlsx'), index_col=0)
    manvar_costs = pd.read_excel(os.path.join(absolute_path, 'data/variable_costs.xlsx'), index_col=0)
    
    variable_costs = freight_costs / 1000 + manvar_costs
    
    return fixed_costs, variable_costs

# def load_capacity_limits(capacity_limits):
#     """Load and update capacity limits."""
#     absolute_path = os.path.dirname(__file__)
#     cap = pd.read_excel(os.path.join(absolute_path, 'data/capacity.xlsx'), index_col=0)
    
#     # Update the capacity DataFrame with the calculated limits
#     for location, (low, high) in capacity_limits.items():
#         cap.loc[location, 'Low'] = low
#         cap.loc[location, 'High'] = high

#     # Save the modified DataFrame back to the Excel file
#     cap.to_excel(os.path.join(absolute_path, 'data/capacity.xlsx'))
    
#     return cap

def load_capacity_limits(production_totals):
    """
    Charge les limites de capacité en fonction des totaux de production simulés pour chaque ligne.

    :param production_totals: Liste des totaux de production pour chaque ligne.
    :return: Dictionnaire des limites de capacité par localisation.
    """
    capacity_l = {}

    for location, total_production in production_totals.items():
        capacity_l[location] = {
            'Low': total_production / 2,  # La moitié du total de production comme capacité basse
            'High': total_production      # Total de production comme capacité haute
        }

    return capacity_l


def run_simple_supply_allocation(capacity_limits, demand):
    """
    Réalise une allocation simple de la production en priorisant :
    - France puis UK pour la demande française
    - UK puis France pour la demande britannique
    - Texas puis California pour la demande américaine
    """

    # Faire une copie profonde des capacités pour éviter les modifications accidentelles
    original_capacity_limits = copy.deepcopy(capacity_limits)

    # Si `demand` est un DataFrame, convertir correctement
    if isinstance(demand, pd.DataFrame):
        if 'Demand' in demand.columns:
            demand = demand['Demand'].to_dict()
        else:
            raise ValueError("Le DataFrame `demand` doit contenir une colonne nommée 'Demand'.")

    loc_prod = list(capacity_limits.keys())  # Sites de production
    loc_demand = list(demand.keys())  # Marchés de consommation

    # Initialisation des allocations
    allocation = {prod: {market: 0 for market in loc_demand} for prod in loc_prod}
    production_totals = {prod: 0 for prod in loc_prod}
    market_totals = {market: 0 for market in loc_demand}

    # Réinitialisation des capacités
    capacity_limits = copy.deepcopy(original_capacity_limits)

    # 🔹 Allocation avec priorité locale optimisée
    for market, qty in demand.items():
        remaining_qty = int(qty)

        # Définir l'ordre de priorité des sites de production
        if market == "France":
            priority_sites = ["France", "UK", "Texas", "California"]  # France > UK > USA
        elif market == "UK":
            priority_sites = ["UK", "France", "Texas", "California"]  # UK > France > USA
        else:
            priority_sites = ["Texas", "California", "France", "UK"]  # USA > EU

        for prod_site in priority_sites:
            available_capacity = int(capacity_limits[prod_site]['High'])

            if available_capacity > 0:
                allocated = min(remaining_qty, available_capacity)
                allocation[prod_site][market] += allocated
                capacity_limits[prod_site]['High'] -= allocated
                production_totals[prod_site] += allocated
                market_totals[market] += allocated
                remaining_qty -= allocated

                print(f"✅ {allocated} sièges alloués de {prod_site} vers {market}")

            if remaining_qty <= 0:
                break  # Toute la demande a été couverte, on passe au marché suivant

    # Conversion en source, target, value
    source, target, value = [], [], []
    for prod, markets in allocation.items():
        for market, qty in markets.items():
            if qty > 0:
                source.append(loc_prod.index(prod))
                target.append(loc_demand.index(market))
                value.append(qty)

    # Restaurer les capacités à l'état d'origine pour vérification
    capacity_limits = original_capacity_limits

    return source, target, value, production_totals, market_totals, loc_prod, loc_demand, capacity_limits

def run_simulation_step(current_stock, command_quantity, max_capacity=50, daily_consumption=10):
    """
    Simule un pas de production pour une ligne vivante.
    
    :param current_stock: stock actuel
    :param command_quantity: commande décidée par le moteur vivant
    :param max_capacity: capacité maximale de production par jour
    :param daily_consumption: consommation fixe ou estimée
    :return: dictionnaire avec résultats du step
    """

    # Appliquer la contrainte de capacité
    actual_production = min(command_quantity, max_capacity)

    # Mise à jour du stock
    stock_variation = actual_production - daily_consumption
    new_stock = current_stock + stock_variation

    return {
        "produced": actual_production,
        "new_stock": new_stock,
        "stock_variation": stock_variation
    }
