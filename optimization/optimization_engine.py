from pulp import LpProblem, LpMinimize, lpSum, LpVariable, PULP_CBC_CMD, LpStatus
from line_production.line_production import run_simulation
from environment import environment_engine
from economic.cost_engine import get_supply_cost, get_unit_cost, calculate_total_costs
from distribution.distribution_engine import load_freight_costs_and_demands
from line_production.production_engine import load_fixed_and_variable_costs, run_simple_supply_allocation
from line_production.line_production_settings import lines_config

# Configuration par défaut des sites de production et marchés de demande
DEFAULT_PROD_SITES = ['Texas', 'California', 'UK', 'France']
DEFAULT_DEMAND_MARKETS = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
MIN_PRODUCTION_IF_ACTIVE = 50  # Production minimale (unités) si un site est activé

def add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand):
    """
    Ajoute les contraintes communes de base au modèle d'optimisation :
    - Capacité maximale autorisée selon Low/High par site.
    - Minimum de production (MIN_PRODUCTION_IF_ACTIVE) si une usine est activée.
    - Pas d'activation simultanée des modes Low et High.
    - Satisfaction complète de la demande pour chaque marché.
    """
    for i in loc_prod:
        # 1. Contraintes de production minimale si l'usine est ouverte
        model += lpSum([x[(i, j)] for j in loc_demand]) >= MIN_PRODUCTION_IF_ACTIVE * lpSum([y[(i, s)] for s in size]), f"MinProd_{i}"
        # 2. Contraintes de capacité maximale (selon niveau Low/High actif)
        model += lpSum([x[(i, j)] for j in loc_demand]) <= (
            cap[i]['Low'] * y[(i, 'Low')] + cap[i]['High'] * y[(i, 'High')]
        ), f"CapMax_{i}"
        # 3. Empêcher d'activer Low et High simultanément pour un même site
        model += y[(i, 'Low')] + y[(i, 'High')] <= 1, f"Exclusive_LH_{i}"
    # 4. Satisfaction de la demande de chaque marché j
    for j in loc_demand:
        model += lpSum([x[(i, j)] for i in loc_prod]) == demand.loc[j, 'Demand'], f"Demand_{j}"

def run_supply_chain_optimization(capacity_limits, demand=None):
    """
    Optimisation mono-objectif minimisant le coût total (production + transport). 
    Ne considère que les contraintes économiques et de capacité.
    :param capacity_limits: dict des capacités Low/High par site (ex: {'France': {'Low': ..., 'High': ...}, ...})
    :param demand: DataFrame ou None (si None, on utilisera les données internes via load_freight_costs_and_demands)
    :return: tuple (source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap)
    """
    # Charger les données de demande et coûts si non fournies
    freight_costs, demand_df = load_freight_costs_and_demands() if demand is None else (load_freight_costs_and_demands()[0], demand)
    fixed_costs, var_costs = load_fixed_and_variable_costs(freight_costs)
    cap = capacity_limits
    loc_prod = list(cap.keys())
    loc_demand = list(demand_df.index)
    size = ['Low', 'High']
    # Définir le modèle d'optimisation (minimisation de coût)
    model = LpProblem("Cost_Minimization", LpMinimize)
    # Variables de décision: x(i,j) = quantité produite sur site i pour marché j, y(i,s) = binaire activation niveau s sur site i
    x = LpVariable.dicts("production", [(i, j) for i in loc_prod for j in loc_demand], lowBound=0, cat='Continuous')
    y = LpVariable.dicts("plant", [(i, s) for i in loc_prod for s in size], cat='Binary')
    # Objectif: minimiser le coût total
    total_cost_expr = lpSum([
        fixed_costs.loc[i, s] * y[(i, s)] 
        for i in loc_prod for s in size
    ]) + lpSum([
        get_unit_cost(i, j, var_costs) * x[(i, j)]
        for i in loc_prod for j in loc_demand
    ])
    model += total_cost_expr
    # Contraintes de base
    add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand_df)
    # Résoudre le modèle sans affichage de log
    model.solve(PULP_CBC_CMD(msg=False))
    # Extraire les variables solution (production non nulles)
    production = {
        (i, j): x[(i, j)].value() 
        for i in loc_prod for j in loc_demand if x[(i, j)].value() is not None and x[(i, j)].value() > 0
    }
    # Construire les listes source, target, value correspondant au flux >0
    source, target, value_list = [], [], []
    for (i, j), qty in production.items():
        source.append(loc_prod.index(i))
        target.append(loc_demand.index(j))
        value_list.append(qty)
    # Totaux de production par site et par marché
    production_totals = {i: 0 for i in loc_prod}
    market_totals = {j: 0 for j in loc_demand}
    for s_idx, t_idx, qty in zip(source, target, value_list):
        production_totals[loc_prod[s_idx]] += qty
        market_totals[loc_demand[t_idx]] += qty
    return source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap

def run_supply_chain_optimization_minimize_co2(capacity_limits, demand=None):
    """
    Optimisation mono-objectif minimisant les émissions CO₂ totales (production + transport).
    Utilise les mêmes contraintes de base.
    """
    freight_costs, demand_df = load_freight_costs_and_demands() if demand is None else (load_freight_costs_and_demands()[0], demand)
    fixed_costs, var_costs = load_fixed_and_variable_costs(freight_costs)
    cap = capacity_limits
    loc_prod = list(cap.keys())
    loc_demand = list(demand_df.index)
    size = ['Low', 'High']
    model = LpProblem("CO2_Minimization", LpMinimize)
    x = LpVariable.dicts("production", [(i, j) for i in loc_prod for j in loc_demand], lowBound=0, cat='Continuous')
    y = LpVariable.dicts("plant", [(i, s) for i in loc_prod for s in size], cat='Binary')
    # Objectif: minimiser le CO₂ total (production + distribution)
    total_co2_expr = lpSum([
        environment_engine.calculate_distribution_co2_emissions(i, j, x[(i, j)]) +
        environment_engine.calculate_lca_production_IFE_raw(x[(i, j)], i)["Climate Change"]
        for i in loc_prod for j in loc_demand
    ])
    model += total_co2_expr
    add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand_df)
    model.solve(PULP_CBC_CMD(msg=False))
    production = {
        (i, j): x[(i, j)].value() 
        for i in loc_prod for j in loc_demand if x[(i, j)].value() is not None and x[(i, j)].value() > 0
    }
    source, target, value_list = [], [], []
    for (i, j), qty in production.items():
        source.append(loc_prod.index(i))
        target.append(loc_demand.index(j))
        value_list.append(qty)
    production_totals = {i: 0 for i in loc_prod}
    market_totals = {j: 0 for j in loc_demand}
    for s_idx, t_idx, qty in zip(source, target, value_list):
        production_totals[loc_prod[s_idx]] += qty
        market_totals[loc_demand[t_idx]] += qty
    return source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap

def run_supply_chain_optimization_multiobjective(capacity_limits, demand, alpha=1.0, beta=1.0):
    """
    Optimisation bi-objectif pondérée (coût + CO₂). 
    Combine les contraintes économiques et environnementales.
    :param alpha: poids du coût dans la fonction objectif
    :param beta: poids des émissions CO₂ dans la fonction objectif
    """
    # Calculer solutions de référence pour normaliser les objectifs
    ref_cost_solution = run_supply_chain_optimization(capacity_limits, demand)
    ref_costs = calculate_total_costs({
        "source": ref_cost_solution[0],
        "target": ref_cost_solution[1],
        "value": ref_cost_solution[2],
        "production_totals": ref_cost_solution[3],
        "market_totals": ref_cost_solution[4],
        "loc_prod": ref_cost_solution[5],
        "loc_demand": ref_cost_solution[6],
        "cap": ref_cost_solution[7],
        "fixed_costs": load_fixed_and_variable_costs(load_freight_costs_and_demands()[0])[0],
        "variable_costs": load_fixed_and_variable_costs(load_freight_costs_and_demands()[0])[1]
    })
    ref_total_cost = ref_costs["total_cost"]
    ref_co2_solution = run_supply_chain_optimization_minimize_co2(capacity_limits, demand)
    ref_total_co2 = sum([
        environment_engine.calculate_lca_production_IFE_raw(v, ref_co2_solution[5][s])["Climate Change"] +
        environment_engine.calculate_distribution_co2_emissions(ref_co2_solution[5][s], ref_co2_solution[6][t], v)
        for s, t, v in zip(ref_co2_solution[0], ref_co2_solution[1], ref_co2_solution[2])
    ])
    freight_costs, demand_df = load_freight_costs_and_demands() if demand is None else (load_freight_costs_and_demands()[0], demand)
    fixed_costs, var_costs = load_fixed_and_variable_costs(freight_costs)
    cap = capacity_limits
    loc_prod = list(cap.keys())
    loc_demand = list(demand_df.index)
    size = ['Low', 'High']
    model = LpProblem("MultiObjectiveOptimization", LpMinimize)
    # Variables x (production) avec nom unique pour éviter conflits de nommage
    x_names = [f"{i}_{j}" for i in loc_prod for j in loc_demand]
    x_vars = LpVariable.dicts("x", x_names, lowBound=0, cat='Continuous')
    x = {(i, j): x_vars[f"{i}_{j}"] for i in loc_prod for j in loc_demand}
    y = LpVariable.dicts("plant", [(i, s) for i in loc_prod for s in size], cat='Binary')
    # Fonction objectif pondérée normalisée
    cost_expr = lpSum([fixed_costs.loc[i, s] * y[(i, s)] for i in loc_prod for s in size]) + \
               lpSum([get_unit_cost(i, j, var_costs) * x[(i, j)] for i in loc_prod for j in loc_demand])
    co2_expr = lpSum([
        environment_engine.calculate_distribution_co2_emissions(i, j, x[(i, j)]) +
        environment_engine.calculate_lca_production_IFE_raw(x[(i, j)], i)["Climate Change"]
        for i in loc_prod for j in loc_demand
    ])
    norm_cost = cost_expr / ref_total_cost if ref_total_cost > 0 else cost_expr
    norm_co2 = co2_expr / ref_total_co2 if ref_total_co2 > 0 else co2_expr
    model += alpha * norm_cost + beta * norm_co2
    add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand_df)
    model.solve(PULP_CBC_CMD(msg=False))
    if LpStatus[model.status] != 'Optimal':
        # Pas de solution réalisable
        return (None,)*8
    production = {
        (i, j): x[(i, j)].value() 
        for i in loc_prod for j in loc_demand if x[(i, j)].value() is not None and x[(i, j)].value() > 0
    }
    source, target, value_list = [], [], []
    for (i, j), qty in production.items():
        source.append(loc_prod.index(i))
        target.append(loc_demand.index(j))
        value_list.append(qty)
    production_totals = {i: 0 for i in loc_prod}
    market_totals = {j: 0 for j in loc_demand}
    for s_idx, t_idx, qty in zip(source, target, value_list):
        production_totals[loc_prod[s_idx]] += qty
        market_totals[loc_demand[t_idx]] += qty
    return source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap

def select_best_supplier(material, quantity, site_location, suppliers):
    """
    Sélectionne le meilleur fournisseur (coût minimal) pour fournir `quantity` tonnes de `material` au site `site_location`.
    Retourne un dictionnaire avec le nom du fournisseur, le coût et les émissions correspondantes.
    """
    material_suppliers = suppliers[material]
    best_supplier_name = None
    min_cost = float('inf')
    emissions_for_best = 0.0
    for supplier in material_suppliers:
        distance = supplier['distance_to_sites'][site_location]
        cost = get_supply_cost(quantity, distance)
        emissions = environment_engine.calculate_supply_co2_supply_emissions(distance, quantity)
        if cost < min_cost:
            min_cost = cost
            emissions_for_best = emissions
            best_supplier_name = supplier['name']
    return {'supplier': best_supplier_name, 'cost': min_cost, 'emissions': emissions_for_best}

def run_supply_chain_lightweight_scenario(capacity_limits, demand, seat_weight=110):
    """
    Exécute un scénario simplifié "lightweight" (ex: variation de poids de siège), 
    puis calcule ses coûts et émissions totales.
    """
    # Utiliser une allocation simple pour ce scénario
    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_simple_supply_allocation(capacity_limits, demand)
    # Simuler la production détaillée pour collecter les données environnementales (avec seat_weight spécifique)
    all_production_data, all_enviro_data = run_simulation(lines_config, seat_weight=seat_weight)
    freight_costs, _ = load_freight_costs_and_demands()
    fixed_costs, variable_costs = load_fixed_and_variable_costs(freight_costs)
    cost_results = calculate_total_costs({
        "source": source,
        "target": target,
        "value": value,
        "production_totals": production_totals,
        "market_totals": market_totals,
        "loc_prod": loc_prod,
        "loc_demand": loc_demand,
        "cap": cap,
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "include_supply": True,
        "include_storage": True
    })
    total_co2 = sum(
        environment_engine.calculate_lca_production_IFE_raw(value[i], loc_prod[source[i]])["Climate Change"]
        + environment_engine.calculate_distribution_co2_emissions(loc_prod[source[i]], loc_demand[target[i]], value[i])
        for i in range(len(source))
    )
    return {
        "source": source,
        "target": target,
        "value": value,
        "production_totals": production_totals,
        "market_totals": market_totals,
        "loc_prod": loc_prod,
        "loc_demand": loc_demand,
        "cap": cap,
        "costs": cost_results,
        "total_co2": total_co2,
        "production_data": all_production_data,
        "environment_data": all_enviro_data,
        "config": {"lines_config": capacity_limits},  # Conserver la config utilisée (capacités)
        "seat_weight": seat_weight
    }

def run_supply_chain_allocation_as_dict(allocation_function, capacity_limits, demand):
    """
    Enveloppe pour exécuter une fonction d'allocation de supply chain et retourner un dictionnaire standardisé.
    """
    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = allocation_function(capacity_limits, demand)
    return {
        "source": source,
        "target": target,
        "value": value,
        "production_totals": production_totals,
        "market_totals": market_totals,
        "loc_prod": loc_prod,
        "loc_demand": loc_demand,
        "cap": cap
    }

# Fonctions utilitaires renvoyant un dictionnaire de résultat à partir des différentes stratégies
def run_simple_allocation_dict(capacity_limits, demand):
    return run_supply_chain_allocation_as_dict(run_simple_supply_allocation, capacity_limits, demand)

def run_optimization_allocation_dict(capacity_limits, demand):
    return run_supply_chain_allocation_as_dict(run_supply_chain_optimization, capacity_limits, demand)

def run_optimization_co2_allocation_dict(capacity_limits, demand):
    return run_supply_chain_allocation_as_dict(run_supply_chain_optimization_minimize_co2, capacity_limits, demand)

def run_multiobjective_allocation_dict(capacity_limits, demand):
    return run_supply_chain_allocation_as_dict(
        lambda cap, dem: run_supply_chain_optimization_multiobjective(cap, dem, alpha=1.0, beta=1.0),
        capacity_limits, demand
    )
