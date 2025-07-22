# supply_engine.py
from .supply_settings import suppliers
from economic.cost_engine import get_supply_cost
from optimization.optimization_engine import select_best_supplier

def manage_fixed_supply(location, seat_weight=130):
    """
    Gère l'approvisionnement en matériaux avec des quantités proportionnelles au poids du siège.
    """
    materials_ratio = {
        'aluminium': 0.4,
        'fabric': 0.3,
        'polymers': 0.2,
        'paint': 0.1
    }

    materials = {}

    for material, ratio in materials_ratio.items():
        kg_quantity = ratio * seat_weight
        quantity_tonnes = kg_quantity / 1000

        selected_supplier = select_best_supplier(material, quantity_tonnes, location, suppliers)
        distance = suppliers[material][0]['distance_to_sites'][location]
        delivery_time = max(1, int(distance / 1000))

        materials[material] = {
            'quantity': kg_quantity,
            'delivery_time': delivery_time,
            'supplier': selected_supplier['supplier']
        }

    return materials

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