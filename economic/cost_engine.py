def get_supply_cost(quantity, distance, seat_weight = 130):
    """
    Calcule le coût d'approvisionnement pour une quantité donnée.

    :param quantity: Quantité en tonnes.
    :param distance: Distance en km.
    :param cost_per_km_ton: Coût par tonne-kilomètre (par défaut 0.1 €/tonne-km).
    :return: Coût total en euros.
    """
    cost_per_km_ton=0.1
    weight_factor = seat_weight / 130

    return weight_factor * quantity * distance * cost_per_km_ton

def calculate_additional_costs(production_totals, material_usage_kg, distance_to_supplier, cost_per_km_ton=0.1, storage_cost_per_unit=2.0, seat_weight = 130):
    """
    Calcule les coûts d'approvisionnement (transport des matériaux) et de stockage pour chaque site.

    :param production_totals: dict {location: units_produced}
    :param material_usage_kg: dict {material: kg_per_unit}
    :param distance_to_supplier: dict {location: distance in km}
    :param cost_per_km_ton: coût en €/tonne.km
    :param storage_cost_per_unit: coût de stockage par unité produite
    :return: dict {location: total_additional_cost}
    """
    weight_factor = seat_weight / 130
    locations = production_totals.keys()
    materials = material_usage_kg.keys()
    total_additional_costs = {}

    for loc in locations:
        supply_cost_total = 0
        for mat in materials:
            kg_per_unit = material_usage_kg[mat]
            total_kg = weight_factor * kg_per_unit * production_totals[loc]
            total_ton = total_kg / 1000
            dist = distance_to_supplier[loc]
            supply_cost = total_ton * dist * cost_per_km_ton
            supply_cost_total += supply_cost

        storage_cost = storage_cost_per_unit * production_totals[loc]
        total_additional_costs[loc] = supply_cost_total + storage_cost

    return total_additional_costs


def calculate_total_costs(data, seat_weight=130):
    """
    Calcule les coûts totaux d'une allocation de production.
    Prend en argument un dictionnaire contenant tous les éléments nécessaires.
    """
    source = data["source"]
    target = data["target"]
    value = data["value"]
    production_totals = data["production_totals"]
    market_totals = data["market_totals"]
    loc_prod = data.get("loc_prod") or []
    # print("DEBUG dans cost_engine avant test vide : loc_prod =", loc_prod, "type =", type(loc_prod))

    if isinstance(loc_prod, dict):
        loc_prod_list = list(loc_prod.keys())
    else:
        loc_prod_list = loc_prod

    if not loc_prod_list:
        raise ValueError("loc_prod_list est vide : la fonction d'allocation ne fournit pas la liste des sites de production.")

    loc_demand = data.get("loc_demand") or []
    if isinstance(loc_demand, dict):
        loc_demand_list = list(loc_demand.keys())
    else:
        loc_demand_list = loc_demand
    cap = data["cap"]
    fixed_costs = data["fixed_costs"]
    variable_costs = data["variable_costs"]

    include_supply = data.get("include_supply", True)
    include_storage = data.get("include_storage", True)

    if isinstance(loc_prod, list):
        production_distribution = {location: 0 for location in loc_prod}
    elif isinstance(loc_prod, dict):
        production_distribution = {location: 0 for location in loc_prod.keys()}
    else:
        production_distribution = {}


    production_distribution = {location: 0 for location in loc_prod}
    total_costs = {location: 0.0 for location in loc_prod}

    weight_factor = seat_weight / 130

    # Paramètres simplifiés
    material_usage_kg = {
    'aluminium': 5 * weight_factor,
    'fabric': 3 * weight_factor,
    'polymers': 4 * weight_factor,
    'paint': 1 * weight_factor
    }

    distance_to_supplier = {
        'Texas': 8000,
        'California': 7500,
        'UK': 500,
        'France': 300
    }
    cost_per_km_ton = 0.1
    storage_cost_per_unit = 2.0

    for i, source_index in enumerate(source):
        location = loc_prod_list[source_index]
        destination = loc_demand_list[target[i]]
        quantity = value[i]

        low_cap = cap[location]['Low']
        high_cap = cap[location]['High']
        capacity_type = 'Low' if production_totals[location] <= low_cap else 'High'

        fixed = fixed_costs.loc[location, capacity_type]
        variable = variable_costs.loc[location, destination]
        cost = fixed + variable * quantity

        if include_supply:
            supply_cost = 0
            for mat, kg_per_unit in material_usage_kg.items():
                tons = (kg_per_unit * quantity) / 1000
                dist = distance_to_supplier[location]
                supply_cost += tons * dist * cost_per_km_ton
            cost += supply_cost

        if include_storage:
            storage_cost = quantity * storage_cost_per_unit
            cost += storage_cost

        total_costs[location] += cost
        production_distribution[location] += quantity

    return {
        "production_distribution": production_distribution,
        "country_costs": total_costs,
        "total_cost": sum(total_costs.values())
    }

def get_unit_cost(i, j, variable_costs, include_supply=True, include_storage=True, seat_weight=130):
    """
    Calcule le coût unitaire total pour un flux i → j, incluant :
    - coût variable (production + transport)
    - approvisionnement en matières premières (optionnel)
    - coût de stockage (optionnel)
    """
    # Coût variable de base
    total = variable_costs.loc[i, j]

    weight_factor = seat_weight / 130
    # Approvisionnement (matières premières → fournisseur)
    if include_supply:
        material_usage_kg = {
        'aluminium': 5 * weight_factor,
        'fabric': 3 * weight_factor,
        'polymers': 4 * weight_factor,
        'paint': 1 * weight_factor
        }
        cost_per_km_ton = 0.1
        distance_to_supplier = {
            'Texas': 8000,
            'California': 7500,
            'UK': 500,
            'France': 300
        }
        dist = distance_to_supplier.get(i, 500)
        supply_cost = sum((kg / 1000) * dist * cost_per_km_ton for kg in material_usage_kg.values())
        total += supply_cost

    # Stockage
    if include_storage:
        total += 2.0  # €/unité stockée

    return total

# Montant de la pénalité par unité non livrée (modifiable selon le secteur)
PENALITE_NON_LIVRAISON = 200  # €/unité

def calculer_penalite_non_livraison(market_totals, demand):
    # --- Patch pour supporter DataFrame ou Series pandas
    if hasattr(demand, "to_dict"):
        if hasattr(demand, "columns") and "Demand" in demand.columns:
            demand_dict = demand["Demand"].to_dict()
        else:
            demand_dict = demand.to_dict()
    else:
        demand_dict = demand
    # ---

    total_penalty = 0
    penalties = {}
    for market in demand_dict:
        prod = market_totals.get(market, 0)
        demande = demand_dict.get(market, 0)
        manque = max(0, demande - prod)
        penalty = manque * 200  # adapte si besoin
        penalties[market] = penalty
        total_penalty += penalty
        # print(f"[DEBUG PENALITE] market={market}, prod={prod}, demande={demande}, manque={manque}, pénalité={penalty}")

    # print(f"[PENALITE TOTALE] {total_penalty}")
    return penalties, total_penalty

