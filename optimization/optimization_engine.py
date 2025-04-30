# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.16.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---
import os
import pandas as pd
from pulp import *
from pulp import utilities
import plotly.graph_objects as go
import line_production.production_engine as production_engine
import distribution.distribution_engine as distribution_engine
import environment.environment_engine as environment_engine
from environment.environment_engine import calculate_supply_co2_supply_emissions
from economic.cost_engine import get_supply_cost
from economic.cost_engine import get_supply_cost, get_unit_cost, calculate_total_costs
import math
import random
random.seed(1447)
from environment.environment_engine import (
    calculate_distribution_co2_emissions,
    calculate_lca_production_IFE_raw
)
from distribution.distribution_engine import load_freight_costs_and_demands
from line_production.production_engine import load_fixed_and_variable_costs, load_capacity_limits

def add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand):
    """
    Contraintes de base communes à tous les scénarios :
    - Capacité maximale autorisée selon Low/High
    - Minimum 50 unités si une usine est activée
    - Non-activation simultanée Low + High
    - Satisfaction de la demande
    """
    for i in loc_prod:
        # Capacité maximale (selon activation Low ou High)
        model += lpSum([x[(i, j)] for j in loc_demand]) <= (
            cap[i]['Low'] * y[(i, 'Low')] + cap[i]['High'] * y[(i, 'High')]
        ), f"Cap_max_{i}"

        # Minimum de production si l’usine est activée
        model += lpSum([x[(i, j)] for j in loc_demand]) >= 50 * lpSum([y[(i, s)] for s in size]), f"Min_prod_{i}"

        # Interdiction d'activer Low et High en même temps
        model += y[(i, 'Low')] + y[(i, 'High')] <= 1, f"Exclusive_LH_{i}"

    # Satisfaction de la demande par marché
    for j in loc_demand:
        print(f"[DEBUG] Contrainte demand {j} = {demand.loc[j, 'Demand']}")
        model += lpSum([x[(i, j)] for i in loc_prod]) == demand.loc[j, 'Demand'], f"Demand_{j}"


def run_supply_chain_optimization(capacity_limits, demand=None):
    """
    Optimisation mono-objectif sur le coût total.
    Ne tient compte que des contraintes économiques + contraintes de base.
    """
    # Données
    freight_costs, demand = load_freight_costs_and_demands()
    fixed_costs, var_cost = load_fixed_and_variable_costs(freight_costs)
    cap = capacity_limits

    loc_prod = ['Texas', 'California', 'UK', 'France']
    loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
    size = ['Low', 'High']

    model = LpProblem("Cost_Minimization", LpMinimize)

    x = LpVariable.dicts("production_", [(i, j) for i in loc_prod for j in loc_demand], lowBound=0, cat='Continuous')
    y = LpVariable.dicts("plant_", [(i, s) for i in loc_prod for s in size], cat='Binary')

    # OBJECTIF : coût total
    total_cost = lpSum([
        fixed_costs.loc[i, s] * y[(i, s)]
        for i in loc_prod for s in size
    ]) + lpSum([
        get_unit_cost(i, j, var_cost) * x[(i, j)]
        for i in loc_prod for j in loc_demand
    ])
    model += total_cost

    # Contraintes de base (capacité, activation, minimum production, demande)
    add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand)

    # Contraintes logiques économiques (si souhaitées)
    model += y[('Texas','High')] <= y[('California','Low')]
    model += y[('California','High')] <= y[('Texas','Low')]
    model += y[('Texas','High')] + y[('California','High')] <= y[('France','Low')]
    model += y[('UK','High')] <= y[('France','Low')]
    model += y[('France','High')] <= y[('UK','Low')]
    model += y[('France','High')] + y[('UK','High')] <= y[('Texas','Low')]

    # Résolution
    model.solve()
    print("Total Cost = {:,} €".format(int(utilities.value(model.objective))))
    print("Status:", LpStatus[model.status])

    # Extraction
    dict_prod = {
        (i, j): x[(i, j)].varValue
        for i in loc_prod for j in loc_demand if x[(i, j)].varValue > 0
    }

    source, target, value_list = [], [], []
    for (i, j), v in dict_prod.items():
        source.append(loc_prod.index(i))
        target.append(loc_demand.index(j))
        value_list.append(v)

    production_totals = {i: 0 for i in loc_prod}
    market_totals = {j: 0 for j in loc_demand}
    for s, t, v in zip(source, target, value_list):
        production_totals[loc_prod[s]] += v
        market_totals[loc_demand[t]] += v

    return source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap


def run_supply_chain_optimization_minimize_co2(capacity_limits, demand=None):
    """
    Optimisation mono-objectif pour minimiser les émissions de CO₂.
    Inclut uniquement les contraintes environnementales + contraintes de base.
    """
    freight_costs, demand = load_freight_costs_and_demands()
    fixed_costs, var_cost = load_fixed_and_variable_costs(freight_costs)
    cap = capacity_limits

    loc_prod = ['Texas', 'California', 'UK', 'France']
    loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
    size = ['Low', 'High']

    model = LpProblem("CO2_Minimization", LpMinimize)

    x = LpVariable.dicts("production_", [(i, j) for i in loc_prod for j in loc_demand], lowBound=0, cat='Continuous')
    y = LpVariable.dicts("plant_", [(i, s) for i in loc_prod for s in size], cat='Binary')

    # OBJECTIF : CO2 total (production + transport)
    total_co2 = lpSum([
        calculate_distribution_co2_emissions(i, j, x[(i, j)]) +
        calculate_lca_production_IFE_raw(x[(i, j)], i)["Climate Change"]
        for i in loc_prod for j in loc_demand
    ])
    model += total_co2

    # Contraintes de base
    add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand)

    # Contraintes environnementales (priorité sobriété CO₂)
    production_co2_factors = {'France': 1, 'UK': 3, 'California': 3, 'Texas': 3.5}
    sorted_sites = sorted(production_co2_factors.items(), key=lambda x: x[1])
    for i in range(1, len(sorted_sites)):
        prev_site = sorted_sites[i - 1][0]
        curr_site = sorted_sites[i][0]
        model += y[(curr_site, 'Low')] <= y[(prev_site, 'High')], f"Env_Low_{curr_site}"
        model += y[(curr_site, 'High')] <= y[(curr_site, 'Low')], f"Env_High_{curr_site}"

    # SOLVE
    model.solve()
    print("Total CO₂ Emissions = {:,} kg".format(int(utilities.value(model.objective))))
    print("Status:", LpStatus[model.status])

    # Résultats
    dict_prod = {
        (i, j): x[(i, j)].varValue
        for i in loc_prod for j in loc_demand if x[(i, j)].varValue > 0
    }

    source, target, value_list = [], [], []
    for (i, j), v in dict_prod.items():
        source.append(loc_prod.index(i))
        target.append(loc_demand.index(j))
        value_list.append(v)

    production_totals = {i: 0 for i in loc_prod}
    market_totals = {j: 0 for j in loc_demand}
    for s, t, v in zip(source, target, value_list):
        production_totals[loc_prod[s]] += v
        market_totals[loc_demand[t]] += v

    return source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap




def run_supply_chain_optimization_multiobjective(capacity_limits, demand, alpha=1.0, beta=1.0):
    """
    Optimisation multi-objectif pondérée : coût + émissions de CO₂.
    Inclut à la fois contraintes économiques et environnementales.
    """
    # Références pour normalisation
    ref_result_cost = run_supply_chain_optimization(capacity_limits, demand)
    ref_costs = calculate_total_costs({
        "source": ref_result_cost[0],
        "target": ref_result_cost[1],
        "value": ref_result_cost[2],
        "production_totals": ref_result_cost[3],
        "market_totals": ref_result_cost[4],
        "loc_prod": ref_result_cost[5],
        "loc_demand": ref_result_cost[6],
        "cap": ref_result_cost[7],
        "fixed_costs": load_fixed_and_variable_costs(load_freight_costs_and_demands()[0])[0],
        "variable_costs": load_fixed_and_variable_costs(load_freight_costs_and_demands()[0])[1],
    })
    ref_cost = ref_costs["total_cost"]

    ref_result_co2 = run_supply_chain_optimization_minimize_co2(capacity_limits, demand)
    ref_co2 = sum([
        calculate_lca_production_IFE_raw(v, ref_result_co2[5][s])["Climate Change"] +
        calculate_distribution_co2_emissions(ref_result_co2[5][s], ref_result_co2[6][t], v)
        for s, t, v in zip(ref_result_co2[0], ref_result_co2[1], ref_result_co2[2])
    ])

    # Données
    freight_costs, _ = load_freight_costs_and_demands()
    fixed_costs, var_cost = load_fixed_and_variable_costs(freight_costs)
    cap = capacity_limits

    loc_prod = ['Texas', 'California', 'UK', 'France']
    loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
    size = ['Low', 'High']

    model = LpProblem("MultiObjectiveOptimization", LpMinimize)

    # Création de noms propres et sans caractères spéciaux
    x_names = [f"{i}_{j}" for i in loc_prod for j in loc_demand]
    x_vars = LpVariable.dicts("x", x_names, lowBound=0, cat='Continuous')

    # Mapping clair (i, j) → variable
    x = {
        (i, j): x_vars[f"{i}_{j}"]
        for i in loc_prod for j in loc_demand
    }

    y = LpVariable.dicts("plant_", [(i, s) for i in loc_prod for s in size], cat='Binary')

    # OBJECTIF
    cost_expr = lpSum([fixed_costs.loc[i, s] * y[(i, s)] for i in loc_prod for s in size]) + \
                lpSum([get_unit_cost(i, j, var_cost) * x[(i, j)] for i in loc_prod for j in loc_demand])

    co2_expr = lpSum([
        calculate_distribution_co2_emissions(i, j, x[(i, j)]) +
        calculate_lca_production_IFE_raw(x[(i, j)], i)["Climate Change"]
        for i in loc_prod for j in loc_demand
    ])

    norm_cost = cost_expr / ref_cost if ref_cost > 0 else cost_expr
    norm_co2 = co2_expr / ref_co2 if ref_co2 > 0 else co2_expr

    model += alpha * norm_cost + beta * norm_co2

    # Contraintes de base
    add_common_constraints(model, x, y, cap, loc_prod, loc_demand, size, demand)



    # # Contraintes environnementales (sobriété progressive)
    # production_co2_factors = {'France': 1, 'UK': 3, 'California': 3, 'Texas': 3.5}
    # sorted_sites = sorted(production_co2_factors.items(), key=lambda x: x[1])
    # for i in range(1, len(sorted_sites)):
    #     prev_site = sorted_sites[i - 1][0]
    #     curr_site = sorted_sites[i][0]
    #     model += y[(curr_site, 'Low')] <= y[(prev_site, 'High')], f"Env_Low_{curr_site}"
    #     model += y[(curr_site, 'High')] <= y[(curr_site, 'Low')], f"Env_High_{curr_site}"

    # Contraintes économiques (logique d'ouverture)
    model += y[('Texas','High')] <= y[('California','Low')]
    model += y[('California','High')] <= y[('Texas','Low')]
    model += y[('Texas','High')] + y[('California','High')] <= y[('France','Low')]
    model += y[('UK','High')] <= y[('France','Low')]
    model += y[('France','High')] <= y[('UK','Low')]
    model += y[('France','High')] + y[('UK','High')] <= y[('Texas','Low')]


    model.writeLP("debug_model.lp")

    # Résolution
    model.solve()
    print("\n[VAR CHECK] Toutes les variables avec valeur négative :")
    for v in model.variables():
        if v.varValue is not None and v.varValue < -0.001:
            print(v.name, "=", v.varValue)
    print("Status:", LpStatus[model.status])
    print("Normalized Objective =", round(value(model.objective), 3))
    if LpStatus[model.status] != 'Optimal':
        print("⚠️ Aucune solution réalisable. Abandon de l'extraction.")
        return None, None, None, None, None, None, None, None

    # Résultats
    dict_prod = {
        (i, j): x[(i, j)].varValue
        for i in loc_prod for j in loc_demand if x[(i, j)].varValue > 0
    }

    source, target, value_list = [], [], []
    for (i, j), v in dict_prod.items():
        source.append(loc_prod.index(i))
        target.append(loc_demand.index(j))
        value_list.append(v)

    production_totals = {i: 0 for i in loc_prod}
    market_totals = {j: 0 for j in loc_demand}
    for s, t, v in zip(source, target, value_list):
        production_totals[loc_prod[s]] += v
        market_totals[loc_demand[t]] += v

    print("\n[DEBUG] Total production =", sum(production_totals.values()))
    print("[DEBUG] Total demand =", demand['Demand'].sum())
    print(f"[DEBUG] Flux : {loc_prod[s]} → {loc_demand[t]} = {v}")

    for market, val in market_totals.items():
        print(f"[CHECK] Total reçu par {market}: {val} (vs. demande {demand.loc[market, 'Demand']})")

    print("\n[VAR DEBUG] Variables non nulles dans le modèle :")
    for v in model.variables():
        if abs(v.varValue) > 0.01:
            print(v.name, "=", v.varValue)

    return source, target, value_list, production_totals, market_totals, loc_prod, loc_demand, cap


def select_best_supplier(material, quantity, site_location, suppliers):
    """
    Sélectionne le fournisseur optimal pour un matériau donné en fonction des coûts et des émissions.

    :param material: Type de matériau (ex. 'aluminium', 'fabric', 'polymers')
    :param quantity: Quantité en tonnes
    :param site_location: Localisation du site (ex. 'Texas')
    :param suppliers: Liste des fournisseurs pour le matériau
    :return: Dictionnaire avec le fournisseur choisi, les coûts et les émissions
    """
    material_suppliers = suppliers[material]


    best_supplier = None
    min_cost = float('inf')
    total_emissions = 0

    for supplier in material_suppliers:
        distance = supplier['distance_to_sites'][site_location]
        cost = get_supply_cost(quantity, distance)
        emissions = calculate_supply_co2_supply_emissions(distance, quantity)

        if cost < min_cost:  # Trouver le fournisseur le plus économique
            min_cost = cost
            total_emissions = emissions
            best_supplier = supplier['name']

    return {'supplier': best_supplier, 'cost': min_cost, 'emissions': total_emissions}