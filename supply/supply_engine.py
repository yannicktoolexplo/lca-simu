# supply_engine.py
from .supply_settings import suppliers
from economic.cost_engine import get_supply_cost
from optimization.optimization_engine import select_best_supplier

def manage_fixed_supply(location):
    """
    Gère l'approvisionnement en matériaux avec des quantités fixes et ajuste les délais de livraison
    en fonction du fournisseur sélectionné.

    :param location: Localisation de la ligne de production.
    :return: Dictionnaire contenant les quantités, délais de livraison et fournisseurs sélectionnés.
    """
    materials = {
        'aluminium': {'quantity': 25},  # Quantité en kg
        'fabric': {'quantity': 25},
        'polymers': {'quantity': 25},
        'paint': {'quantity': 25}
    }

    supply_summary = {}

    for material, info in materials.items():
        quantity_tonnes = info['quantity'] / 1000  # Convertir en tonnes
        selected_supplier = select_best_supplier(material, quantity_tonnes, location, suppliers)

        # Calculer le délai de livraison en fonction de la distance
        distance = suppliers[material][0]['distance_to_sites'][location]
        delivery_time = max(1, int(distance / 1000))  # Exemple : 1 jour par 1000 km

        supply_summary[material] = {
            'quantity': info['quantity'],
            'delivery_time': delivery_time,
            'supplier': selected_supplier['supplier']
        }

    return supply_summary

def simple_supply_allocation(production_totals):
    """
    Mode simple pour répondre à la demande en fonction de la production.

    :param production_totals: Dictionnaire des totaux de production par site.
    :return: Allocation simple des fournisseurs et matériaux.
    """
    suppliers = {
        'aluminium': 'Constellium',
        'fabric': 'Toray Industries',
        'polymers': 'Sabic',
        'paint': 'PPG Industries'
    }

    allocation = {}
    for location, total_production in production_totals.items():
        allocation[location] = {
            'supplier': suppliers,
            'demand_fulfilled': total_production
        }
    return allocation