# supply_engine.py


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
            min_cost = cost
            total_emissions = emissions
            best_supplier = supplier['name']

    return {'supplier': best_supplier, 'cost': min_cost, 'emissions': total_emissions}
