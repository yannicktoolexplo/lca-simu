# Constantes de calcul par défaut
DEFAULT_SEAT_WEIGHT = 130           # Poids de référence du siège (kg) pour les calculs de coûts
DEFAULT_COST_PER_KM_TON = 0.1       # Coût par tonne-kilomètre (€/tonne-km)
DEFAULT_STORAGE_COST_PER_UNIT = 2.0 # Coût de stockage par unité produite (€
# Usage des matériaux par siège (kg) pour l'approvisionnement (base 130kg siège)
BASE_MATERIAL_USAGE = {
    'aluminium': 5.0,
    'fabric': 3.0,
    'polymers': 4.0,
    'paint': 1.0
}
# Distances par défaut du site de production au fournisseur principal (km)
BASE_DISTANCE_TO_SUPPLIER = {
    'Texas': 8000,
    'California': 7500,
    'UK': 500,
    'France': 300
}
PENALITE_NON_LIVRAISON = 200  # Pénalité par unité non livrée (€/unité)

def get_supply_cost(quantity, distance, seat_weight=DEFAULT_SEAT_WEIGHT, cost_per_km_ton=DEFAULT_COST_PER_KM_TON):
    """
    Calcule le coût d'approvisionnement pour une quantité donnée de matériau en tonnes sur une distance donnée.
    :param quantity: Quantité en tonnes.
    :param distance: Distance en km.
    :param seat_weight: Poids du siège (pour ajuster le coût si siège de poids différent).
    :param cost_per_km_ton: Coût par tonne-kilomètre (défaut 0.1 €/tonne-km).
    :return: Coût total d'approvisionnement en euros.
    """
    weight_factor = seat_weight / DEFAULT_SEAT_WEIGHT
    return weight_factor * quantity * distance * cost_per_km_ton

def calculate_additional_costs(production_totals, material_usage_kg, distance_to_supplier, 
                               cost_per_km_ton=DEFAULT_COST_PER_KM_TON, storage_cost_per_unit=DEFAULT_STORAGE_COST_PER_UNIT, 
                               seat_weight=DEFAULT_SEAT_WEIGHT):
    """
    Calcule les coûts additionnels par site (approvisionnement en matières premières + stockage).
    :param production_totals: dict {location: units_produced}
    :param material_usage_kg: dict {material: kg_per_unit} consommés par siège
    :param distance_to_supplier: dict {location: distance en km}
    :param cost_per_km_ton: coût par tonne.km (€/tonne-km)
    :param storage_cost_per_unit: coût de stockage par unité produite (€)
    :param seat_weight: poids du siège pour ajuster les coûts
    :return: dict {location: total_additional_cost}
    """
    weight_factor = seat_weight / DEFAULT_SEAT_WEIGHT
    total_additional_costs = {}
    for loc, units in production_totals.items():
        # Coût d'approvisionnement total pour le site loc
        supply_cost_total = 0.0
        for mat, kg_per_unit in material_usage_kg.items():
            total_kg = weight_factor * kg_per_unit * units
            total_ton = total_kg / 1000.0
            dist = distance_to_supplier.get(loc, 0)
            supply_cost_total += total_ton * dist * cost_per_km_ton
        # Coût de stockage total pour le site
        storage_cost = storage_cost_per_unit * units
        total_additional_costs[loc] = supply_cost_total + storage_cost
    return total_additional_costs

def calculate_total_costs(result_data, seat_weight=DEFAULT_SEAT_WEIGHT):
    """
    Calcule les coûts totaux d'une allocation de production (fixes, variables, approvisionnement et stockage).
    :param result_data: Dictionnaire contenant les clés 'source', 'target', 'value', 'production_totals', 
                        'market_totals', 'loc_prod', 'loc_demand', 'cap', 'fixed_costs', 'variable_costs', 
                        et éventuellement 'include_supply' et 'include_storage'.
    :param seat_weight: poids du siège pour ajuster la consommation matière (kg)
    :return: dict contenant la distribution de production et les coûts par pays, ainsi que le coût total.
    """
    source = result_data["source"]
    target = result_data["target"]
    value = result_data["value"]
    production_totals = result_data["production_totals"]
    market_totals = result_data["market_totals"]
    loc_prod = result_data.get("loc_prod", [])
    loc_demand = result_data.get("loc_demand", [])
    cap = result_data["cap"]
    fixed_costs = result_data["fixed_costs"]
    variable_costs = result_data["variable_costs"]
    include_supply = result_data.get("include_supply", True)
    include_storage = result_data.get("include_storage", True)

    # Préparer structures de résultats
    if isinstance(loc_prod, dict):
        production_distribution = {location: 0 for location in loc_prod.keys()}
    else:
        production_distribution = {location: 0 for location in loc_prod}
    total_costs = {location: 0.0 for location in production_distribution.keys()}

    weight_factor = seat_weight / DEFAULT_SEAT_WEIGHT
    # Paramètres simplifiés pour l'approvisionnement (consommation de matériaux par unité produite)
    material_usage_kg = {mat: BASE_MATERIAL_USAGE[mat] * weight_factor for mat in BASE_MATERIAL_USAGE}
    distance_to_supplier = BASE_DISTANCE_TO_SUPPLIER.copy()
    cost_per_km_ton = DEFAULT_COST_PER_KM_TON
    storage_cost_per_unit = DEFAULT_STORAGE_COST_PER_UNIT

    # Calculer le coût par flux (chaque élément source→destination)
    for i, source_idx in enumerate(source):
        prod_location = loc_prod[source_idx] if isinstance(loc_prod, list) else list(loc_prod.keys())[source_idx]
        dest_market = loc_demand[target[i]] if isinstance(loc_demand, list) else list(loc_demand.keys())[target[i]]
        quantity = value[i]
        # Choisir le type de capacité (Low/High) en fonction du volume produit sur le site
        low_cap = cap[prod_location]['Low']
        high_cap = cap[prod_location]['High']
        cap_type = 'Low' if production_totals[prod_location] <= low_cap else 'High'
        fixed_cost = fixed_costs.loc[prod_location, cap_type]
        variable_cost = variable_costs.loc[prod_location, dest_market]
        cost = fixed_cost + variable_cost * quantity
        # Ajouter le coût d'approvisionnement en matières premières si activé
        if include_supply:
            supply_cost = 0.0
            for mat, kg_per_unit in material_usage_kg.items():
                tons = (kg_per_unit * quantity) / 1000.0
                dist = distance_to_supplier.get(prod_location, 0)
                supply_cost += tons * dist * cost_per_km_ton
            cost += supply_cost
        # Ajouter le coût de stockage si activé
        if include_storage:
            storage_cost = quantity * storage_cost_per_unit
            cost += storage_cost
        # Cumuler le coût total et la distribution de production
        total_costs[prod_location] += cost
        production_distribution[prod_location] += quantity

    return {
        "production_distribution": production_distribution,
        "country_costs": total_costs,
        "total_cost": sum(total_costs.values())
    }

def get_unit_cost(i, j, variable_costs, include_supply=True, include_storage=True, seat_weight=DEFAULT_SEAT_WEIGHT):
    """
    Calcule le coût unitaire total pour expédier une unité du site de production i vers le marché j, 
    incluant les coûts variables de production et transport, l'approvisionnement (optionnel) et le stockage (optionnel).
    :param i: Nom du site de production (ex: 'France')
    :param j: Nom du marché de destination (ex: 'USA')
    :param variable_costs: DataFrame des coûts variables par site et marché (€/unité)
    :param include_supply: bool, inclure le coût d'approvisionnement matières premières
    :param include_storage: bool, inclure le coût de stockage
    :param seat_weight: poids du siège pour ajuster la consommation matière (kg)
    :return: Coût unitaire total pour le flux i → j en euros.
    """
    # Coût variable de base (production + transport jusqu'au marché j)
    total = variable_costs.loc[i, j]
    weight_factor = seat_weight / DEFAULT_SEAT_WEIGHT
    # Coût d'approvisionnement matières premières
    if include_supply:
        # Quantités de matériaux par unité produite ajustées au poids du siège
        material_usage_kg = {mat: BASE_MATERIAL_USAGE[mat] * weight_factor for mat in BASE_MATERIAL_USAGE}
        cost_per_km_ton = DEFAULT_COST_PER_KM_TON
        distance = BASE_DISTANCE_TO_SUPPLIER.get(i, 500)  # 500 km par défaut si site inconnu
        # Calcul du coût d'approvisionnement pour une unité
        supply_cost = sum((kg / 1000.0) * distance * cost_per_km_ton for kg in material_usage_kg.values())
        total += supply_cost
    # Coût de stockage par unité
    if include_storage:
        total += DEFAULT_STORAGE_COST_PER_UNIT
    return total

def calculer_penalite_non_livraison(market_totals, demand):
    """
    Calcule la pénalité de non-livraison pour chaque marché et au total, 
    en comparant la production totale fournie à la demande.
    :param market_totals: dict des unités produites par marché (ex. {"USA": 100, ...})
    :param demand: soit dict ou pandas Series/DataFrame des demandes par marché
    :return: tuple (penalties_dict, total_penalty) avec les pénalités par marché et la pénalité totale (€).
    """
    # Supporter l'entrée demand comme DataFrame/Series en convertissant en dict
    if hasattr(demand, "to_dict"):
        if hasattr(demand, "columns") and "Demand" in demand.columns:
            demand_dict = demand["Demand"].to_dict()
        else:
            demand_dict = demand.to_dict()
    else:
        demand_dict = dict(demand)
    penalties = {}
    total_penalty = 0
    for market, demande in demand_dict.items():
        prod = market_totals.get(market, 0)
        manque = max(0, demande - prod)
        penalty = manque * PENALITE_NON_LIVRAISON
        penalties[market] = penalty
        total_penalty += penalty
        # (Optionnel: debug info pour chaque marché)
    return penalties, total_penalty
