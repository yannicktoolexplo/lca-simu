from .supply_settings import suppliers  # Données de fournisseurs (par matériau)

# Configuration de la proportion des matériaux composant un siège (en % du poids total)
MATERIALS_RATIO = {
    'aluminium': 0.4,
    'fabric': 0.3,
    'polymers': 0.2,
    'paint': 0.1
}

def manage_fixed_supply(location, seat_weight=130):
    """
    Gère l'approvisionnement en matières premières nécessaires à la production d'un siège 
    en calculant les quantités à commander et en sélectionnant le meilleur fournisseur.
    :param location: Site de production (pour calculer la distance fournisseur-site)
    :param seat_weight: Poids du siège (kg) utilisé pour calculer les besoins en matériaux
    :return: Dictionnaire des matériaux avec quantité (kg), délai de livraison et fournisseur sélectionné.
    """
    from optimization.optimization_engine import select_best_supplier
    materials = {}
    # Calculer les besoins en matériaux en fonction du poids du siège
    for material, ratio in MATERIALS_RATIO.items():
        kg_quantity = ratio * seat_weight              # quantité en kg pour ce matériau
        quantity_tonnes = kg_quantity / 1000           # conversion en tonnes
        # Sélectionner le meilleur fournisseur pour ce matériau et cette quantité
        best_supplier = select_best_supplier(material, quantity_tonnes, location, suppliers)
        distance = suppliers[material][0]['distance_to_sites'][location]
        delivery_time = max(1, int(distance / 1000))   # délai de livraison estimé (>=1)
        materials[material] = {
            'quantity': kg_quantity,
            'delivery_time': delivery_time,
            'supplier': best_supplier['supplier']
        }
    return materials

def simple_supply_allocation(production_totals):
    """
    Alloue de façon simple un fournisseur par défaut pour chaque matériau, 
    en couvrant la demande de chaque site de production.
    :param production_totals: Dictionnaire {site: total unités produites} 
    :return: Allocation simple des fournisseurs pour chaque site de production.
    """
    # Fournisseur par défaut pour chaque matériau (premier de la liste des fournisseurs dans supply_settings)
    default_suppliers = {
        'aluminium': suppliers['aluminium'][0]['name'],
        'fabric': suppliers['fabric'][0]['name'],
        'polymers': suppliers['polymers'][0]['name'],
        'paint': suppliers['paint'][0]['name']
    }
    allocation = {}
    for location, total_production in production_totals.items():
        allocation[location] = {
            'supplier': default_suppliers,
            'demand_fulfilled': total_production
        }
    return allocation
