# logistics_engine.py

import os
import pandas as pd

# Define distances between locations in km
distances = {
    # Texas to demand locations
    ('Texas', 'USA'): 2400,
    ('Texas', 'Canada'): 3000,
    ('Texas', 'Japan'): 11000,
    ('Texas', 'Brazil'): 8000,
    ('Texas', 'France'): 8500,
    
    # California to demand locations
    ('California', 'USA'): 3800,
    ('California', 'Canada'): 1300,
    ('California', 'Japan'): 9000,
    ('California', 'Brazil'): 10500,
    ('California', 'France'): 9300,
    
    # UK to demand locations
    ('UK', 'USA'): 5600,
    ('UK', 'Canada'): 5200,
    ('UK', 'Japan'): 9600,
    ('UK', 'Brazil'): 9400,
    ('UK', 'France'): 800,  # by road
    
    # France to demand locations
    ('France', 'USA'): 7600,
    ('France', 'Canada'): 6000,
    ('France', 'Japan'): 9700,
    ('France', 'Brazil'): 8900,
    ('France', 'France'): 200  # local production
}

def load_freight_costs_and_demands():
    """Load costs and demand data from Excel files."""
    absolute_path = os.path.dirname(__file__)

    # Load Freight Costs
    freight_costs = pd.read_excel(os.path.join(absolute_path, 'data/freight_costs.xlsx'), index_col=0)

    # Load Demand
    demand = pd.read_excel(os.path.join(absolute_path, 'data/demand.xlsx'), index_col=0)

    return freight_costs, demand



def calculate_best_supply_chain(material, quantity, site_location, suppliers):
    """
    Calcule le fournisseur optimal en fonction du coût et des émissions pour un matériau donné.
    
    :param material: Type de matériau (ex. 'aluminium', 'fabric', 'polymers')
    :param quantity: Quantité en tonnes
    :param site_location: Localisation de l’usine (ex. 'Texas')
    :return: Dictionnaire avec le fournisseur choisi, les coûts et les émissions
    """
    # Coût et émission par km et par tonne
    cost_per_km_ton = 0.1  # € par km par tonne
    co2_per_km_ton = 0.02  # kg CO2 par km par tonne

    # Récupérer les fournisseurs pour la matière
    material_suppliers = suppliers[material]

    # Évaluer chaque fournisseur
    best_supplier = None
    min_cost = float('inf')
    total_emissions = 0

    for supplier in material_suppliers:
        distance = supplier['distance_to_sites'][site_location]
        cost = quantity * distance * cost_per_km_ton
        emissions = quantity * distance * co2_per_km_ton

        if cost < min_cost:  # Trouver le fournisseur le plus économique
            min_cost = cost
            total_emissions = emissions
            best_supplier = supplier['name']

    return {'supplier': best_supplier, 'cost': min_cost, 'emissions': total_emissions}
