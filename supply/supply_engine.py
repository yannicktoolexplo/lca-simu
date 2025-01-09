# supply_engine.py
from environment.environment_engine import calculate_supply_co2_supply_emissions


def get_supply_cost():
    """
    Calcule le fournisseur optimal en fonction du coût et des émissions pour un matériau donné.
    
    :param material: Type de matériau (ex. 'aluminium', 'fabric', 'polymers')
    :param quantity: Quantité en tonnes
    :param site_location: Localisation de l’usine (ex. 'Texas')
    :return: Dictionnaire avec le fournisseur choisi, les coûts et les émissions
    """
    # Coût et émission par km et par tonne
    cost_per_km_ton = 0.1  # € par km par tonne
    # Récupérer les fournisseurs pour la matière
    return cost_per_km_ton  # € par km par tonne
