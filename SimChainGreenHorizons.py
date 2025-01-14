import os
import math
import copy


import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import line_production.line_production as line_production
import distribution.distribution_engine as distribution_engine
from optimization.optimization_engine import run_supply_chain_optimization, run_supply_chain_optimization_minimize_co2
import environment.environment_engine as environment_engine 
import utils.data_tools as data_tools
from line_production.line_production_settings import lines_config
from line_production.production_engine import calculate_capacity_limits
from supply.supply_settings import suppliers
from optimization.optimization_engine import select_best_supplier

def main_function():

    # Exécution de la simulation pour plusieurs lignes de production
    all_production_data, all_enviro_data = line_production.run_simulation(lines_config)

    # Traiter les données de chaque ligne indépendamment ou les agréger
    for i, (production_data, enviro_data) in enumerate(zip(all_production_data, all_enviro_data)):
        print(f"Ligne de production {i+1} :")
        total_seats_made = production_data['Total Seats made'][1][-1]

        # Calcul des indicateurs pour la phase de production
        production_lca = environment_engine.calculate_lca_indicators_pers_eq(total_seats_made)
        
        # Calcul des indicateurs pour la phase d'utilisation
        usage_lca = environment_engine.calculate_lca_indicators_usage_phase(total_seats_made, seat_weight=120)
        
        # # Affichage des indicateurs environnementaux pour la production (en bleu par défaut)
        # data_tools.plot_lca_indicators(production_lca, title=f"Ligne {i+1} - Production LCA Indicators")

        # # Affichage des indicateurs environnementaux pour l'utilisation (en jaune)
        # data_tools.plot_lca_indicators(usage_lca, title=f"Ligne {i+1} - Usage LCA Indicators", color='rgba(255, 223, 0, 0.6)')

        # Affichage des indicateurs environnementaux combinés (production + utilisation)
        data_tools.plot_lca_combined_indicators(production_lca, usage_lca, title=f"Ligne {i+1} - Combined LCA Indicators")
        
        # Plot des niveaux de stock et du total des sièges produits
        data_tools.plot_stock_levels(production_data, production_data['Total Seats made'])


    for i, (production_data, enviro_data) in enumerate(zip(all_production_data, all_enviro_data)):
        location = lines_config[i]['location']
        print(f"Ligne de production {i+1} - Location: {location}")
        
        # Quantités en tonnes
        alu_quantity = 5 * total_seats_made / 1000
        fabric_quantity = 2 * total_seats_made / 1000
        polymer_quantity = 3 * total_seats_made / 1000

        # Calculs logistiques
        alu_supply = select_best_supplier('aluminium', alu_quantity, location, suppliers)
        fabric_supply = select_best_supplier('fabric', fabric_quantity, location, suppliers)
        polymer_supply = select_best_supplier('polymers', polymer_quantity, location, suppliers)

        # Résumer les résultats
        print(f"Fournisseur aluminium: {alu_supply['supplier']}, Coût: {alu_supply['cost']:.2f} €, CO₂: {alu_supply['emissions']:.2f} kg")
        print(f"Fournisseur tissu: {fabric_supply['supplier']}, Coût: {fabric_supply['cost']:.2f} €, CO₂: {fabric_supply['emissions']:.2f} kg")
        print(f"Fournisseur polymères: {polymer_supply['supplier']}, Coût: {polymer_supply['cost']:.2f} €, CO₂: {polymer_supply['emissions']:.2f} kg")


#     """Main function to run the analysis and plots."""
    
    # Configuration personnalisée
    # custom_config = line_production.line_production.FactoryConfig(
    #     hours=8,  # Par exemple, changer les heures de travail par jour à 10
    #     days=21,  # Par exemple, changer le nombre de jours ouvrables à 30
    #     initial_aluminium=150,  # Par exemple, changer le stock initial d'aluminium
    #     initial_foam=150,  # Par exemple, changer le stock initial de mousse
    #     initial_fabric=150,  # Par exemple, changer le stock initial de tissu
    #     initial_paint=150  # Par exemple, changer le stock initial de peinture
    # )

    # Exécution de la simulation avec la configuration personnalisée
    # seat_factory = line_production.line_production.run_simulation(custom_config)

    # Collectez les données depuis line_production
    # production_data = line_production.get_data(seat_factory)
#     total_seats_made = production_data['Total Seats made'][1][-1]

#     # Calcul des indicateurs environnementaux
#     # enviro_data = environment_engine.calculate_lca_indicators(total_seats_made)
#     enviro_data = environment_engine.calculate_lca_indicators_pers_eq(total_seats_made)

#     # Plot des indicateurs environnementaux
#     data_tools.plot_lca_indicators(enviro_data)

#     # Préparer les données de stock pour chaque composant sauf 'Total Seats made'
#     stock_data = {
#         'Seat Stock': production_data['Seat Stock'],
#         'Frame Data': production_data['Frame Data'],
#         'Armrest Data': production_data['Armrest Data'],
#         'Foam Stock': production_data['Foam Stock'],
#         'Fabric Stock': production_data['Fabric Stock'],
#         'Paint Stock': production_data['Paint Stock'],
#         'Aluminium Stock': production_data['Aluminium Stock']
#     }

    # Préparer les données pour 'Total Seats made'
    # total_seats_data = production_data['Total Seats made']
    
#     # Plot des niveaux de stock et du total des sièges produits
#     data_tools.plot_stock_levels(stock_data, total_seats_data)
    
#     # Plot de la consommation des ressources
#     # data_tools.plot_resource_consumption(enviro_data)
    
#     # Plot de la consommation totale des ressources
#     # data_tools.plot_total_resource_consumption(enviro_data)

    # # Calculer les limites de capacité basées sur les données de production
    # capacity_limits = calculate_capacity_limits(production_data)

    # # Exécuter l'optimisation de la chaîne d'approvisionnement avec les limites de capacité calculées
    # source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_supply_chain_optimization(capacity_limits)
    # print(source)
    # print(target)
    # print(value)
    # print(production_totals)
    # print(market_totals)
    # print(loc_prod)
    # print(loc_demand)
    # print(cap)
#     # Préparer les étiquettes et couleurs pour le diagramme Sankey de la production
#     node_labels = [f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))]
#     node_labels += [f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]
#     link_labels = [f"{v:,.0f} Units" for v in value]

#     base_colors = {
#         'Texas': 'rgba(255, 127, 14, 0.8)',
#         'California': 'rgba(255, 127, 14, 0.8)',
#         'UK': 'rgba(148, 103, 189, 0.8)',
#         'France': 'rgba(214, 39, 40, 0.8)',
#     }

#     target_colors = {
#         'USA': 'rgba(255, 127, 14, 0.5)',
#         'Canada': 'rgba(255, 215, 0, 0.5)',
#         'Japan': 'rgba(44, 160, 44, 0.5)',
#         'Brazil': 'rgba(31, 119, 180, 0.5)',
#         'France': 'rgba(214, 39, 40, 0.5)'
#     }

#     production_colors = [base_colors[place] for place in loc_prod]
#     market_colors = [target_colors[place] for place in loc_demand]
#     node_colors = production_colors + market_colors
#     link_colors = [market_colors[i] for i in target]

#     # Créer et afficher le diagramme Sankey pour la production
#     fig_prod = go.Figure(data=[go.Sankey(
#         node=dict(
#             pad=15,
#             thickness=20,
#             line=dict(color="black", width=0.5),
#             label=node_labels,
#             color=node_colors
#         ),
#         link=dict(
#             source=source,
#             target=[i + len(loc_prod) for i in target],
#             value=value,
#             label=link_labels,
#             color=link_colors
#         ))])

# # Calculer les émissions de CO2 pour le transport et la production
#     co2_emissions = [environment_engine.calculate_distribution_co2_emissions(loc_prod[s], loc_demand[t], value[i]) for i, (s, t) in enumerate(zip(source, target))]
#     production_co2_emissions = [environment_engine.calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

#     def calculate_total_co2_emissions(loc_prod, source, co2_emissions,production_co2_emissions):

#         total_emissions = {location: 0.0 for location in loc_prod}

#         for i, source_index in enumerate(source):
#                 location = loc_prod[source_index]
#                 # Add distribution CO2 emissions
#                 total_emissions[location] += co2_emissions[i]
#                 # Add production CO2 emissions
#                 total_emissions[location] += production_co2_emissions[source_index]

#         return total_emissions
    
#     production_totals_emissions = calculate_total_co2_emissions(loc_prod, source, co2_emissions, production_co2_emissions)
#     print(production_totals_emissions)

#     def calculate_total_costs(source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap):
#         """
#         Calculate production costs for each country and total costs based on capacity, fixed costs,
#         and variable costs.

#         :param source: List of source indices corresponding to emissions.
#         :param target: List of target indices corresponding to emissions.
#         :param value: List of quantities transported between source and target.
#         :param production_totals: List of total production quantities per source.
#         :param market_totals: Dictionary with market demand totals per region (e.g., {'USA': 176.0, 'France': 308.0}).
#         :param loc_prod: List of production locations (e.g., ['Texas', 'California', 'UK', 'France']).
#         :param loc_demand: List of demand locations (e.g., ['USA', 'Canada', 'Japan', 'Brazil', 'France']).
#         :param cap: Dictionary with production capacities (keys are locations, values are {'Low': x, 'High': y}).
#         :return: Dictionary with production distribution, costs per country, and the total cost.
#         """
#         # Initialize results
#         production_distribution = {location: 0 for location in loc_prod}
#         total_costs = {location: 0.0 for location in loc_prod}

#         # Distribute market demand to production countries
#         for market, demand in market_totals.items():
#             # Sort by capacity to prioritize higher capacity locations
#             sorted_capacity = sorted(cap.items(), key=lambda x: x[1]['High'], reverse=True)
#             remaining_demand = demand

#             for country, capacities in sorted_capacity:
#                 if country not in loc_prod:
#                     continue

#                 low_cap = capacities['Low']
#                 high_cap = capacities['High']

#                 # Determine how much of the demand can be fulfilled by this country
#                 allocated = min(remaining_demand, high_cap)
#                 production_distribution[country] += allocated
#                 remaining_demand -= allocated

#                 # Break if demand is fully allocated
#                 if remaining_demand <= 0:
#                     break

#         # Calculate costs for each country
#         for i, source_index in enumerate(source):
#             location = loc_prod[source_index]
#             low_cap = cap[location]['Low']
#             high_cap = cap[location]['High']

#             # Determine if low or high capacity applies
#             capacity_type = 'Low' if production_totals[source_index] <= low_cap else 'High'

#             # Example fixed and variable costs (replace these with actual values as needed)
#             fixed_cost = 1000 if capacity_type == 'Low' else 2000  # Replace with actual fixed costs
#             variable_cost = 10  # Replace with actual variable costs per unit

#             # Calculate total cost for the country
#             total_costs[location] += fixed_cost + (variable_cost * production_totals[source_index])

#         # Calculate total cost across all countries
#         total_cost = sum(total_costs.values())

#         return {
#             'production_distribution': production_distribution,
#             'country_costs': total_costs,
#             'total_cost': total_cost
#         }

#     def plot_costs(country_costs, total_cost):
#         """
#         Plot the costs per producing country and the total cost using Plotly.

#         :param country_costs: Dictionary with costs per country.
#         :param total_cost: Total cost across all countries.
#         """
#         countries = list(country_costs.keys())
#         costs = list(country_costs.values())

#         # Create the bar chart
#         fig = go.Figure()

#         # Add bars for each country
#         fig.add_trace(go.Bar(
#             x=countries,
#             y=costs,
#             text=[f'{cost:.2f}' for cost in costs],
#             textposition='auto',
#             name='Country Costs'
#         ))

#         # Add a bar for the total cost
#         fig.add_trace(go.Bar(
#             x=['Total'],
#             y=[total_cost],
#             text=[f'{total_cost:.2f}'],
#             textposition='auto',
#             name='Total Cost',
#             marker=dict(color='red')
#         ))

#         # Update layout
#         fig.update_layout(
#             title='Production Costs per Country and Total',
#             xaxis_title='Producing Country',
#             yaxis_title='Cost (€)',
#             barmode='group',
#             legend_title='Legend'
#         )

#         # Show the plot
#         fig.show()


#     # Example Usage
#     source = [1, 3, 0, 0, 2]
#     target = [1, 3, 4, 0, 2]
#     value = [99.0, 187.0, 308.0, 176.0, 159.5]
#     production_totals = [484.0, 99, 159.5, 187]
#     market_totals = {'USA': 176.0, 'Canada': 99.0, 'Japan': 159.5, 'Brazil': 187.0, 'France': 308.0}
#     loc_prod = ['Texas', 'California', 'UK', 'France']
#     loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
#     cap = {
#         'Texas': {'Low': 252, 'High': 503},
#         'California': {'Low': 126, 'High': 252},
#         'UK': {'Low': 63, 'High': 126},
#         'France': {'Low': 189, 'High': 378}
#     }

#     result = calculate_total_costs(source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap)

#     # Display results
#     print("Production Distribution:", result['production_distribution'])
#     print("Country Costs:", result['country_costs'])
#     print("Total Cost:", result['total_cost'])

#     # Plot the costs
#     plot_costs(result['country_costs'], result['total_cost'])


#     market2_totals = {location: 0 for location in loc_demand}

#     # Agréger les émissions de CO2 par lieu de production et marché
#     for s, t, p, v in zip(source, target, production_co2_emissions, value):
#         production_co2_totals[loc_prod[s]] += p
#         market2_totals[loc_demand[t]] += v

#     node2_labels = [f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))]
#     node2_labels += [f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

#     link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

#     # Créer et afficher le diagramme Sankey pour les émissions de CO2
#     fig_CO2 = go.Figure(data=[go.Sankey(
#         node=dict(
#             pad=15,
#             thickness=20,
#             line=dict(color="black", width=0.5),
#             label=node2_labels,
#             color=node_colors
#         ),
#         link=dict(
#             source=source,
#             target=[i + len(loc_prod) for i in target],
#             value=co2_emissions,
#             label=link2_labels,
#             color=link_colors
#         ))])

#     # Afficher les diagrammes Sankey
#     fig_prod.show()
#     fig_CO2.show()

    # # Plot des émissions de CO2 de production par pays
    # data_tools.plot_production_co2_emissions(production_totals_emissions)



# ########################### CO2_opti

#  # Exécuter l'optimisation de la chaîne d'approvisionnement avec les limites de capacité calculées
#     source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_supply_chain_optimization_minimize_co2(capacity_limits)

#     # Préparer les étiquettes et couleurs pour le diagramme Sankey de la production
#     node_labels = [f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))]
#     node_labels += [f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]
#     link_labels = [f"{v:,.0f} Units" for v in value]

#     base_colors = {
#         'Texas': 'rgba(255, 127, 14, 0.8)',
#         'California': 'rgba(255, 127, 14, 0.8)',
#         'UK': 'rgba(148, 103, 189, 0.8)',
#         'France': 'rgba(214, 39, 40, 0.8)',
#     }

#     target_colors = {
#         'USA': 'rgba(255, 127, 14, 0.5)',
#         'Canada': 'rgba(255, 215, 0, 0.5)',
#         'Japan': 'rgba(44, 160, 44, 0.5)',
#         'Brazil': 'rgba(31, 119, 180, 0.5)',
#         'France': 'rgba(214, 39, 40, 0.5)'
#     }

#     production_colors = [base_colors[place] for place in loc_prod]
#     market_colors = [target_colors[place] for place in loc_demand]
#     node_colors = production_colors + market_colors
#     link_colors = [market_colors[i] for i in target]

#     # Créer et afficher le diagramme Sankey pour la production
#     fig_prod = go.Figure(data=[go.Sankey(
#         node=dict(
#             pad=15,
#             thickness=20,
#             line=dict(color="black", width=0.5),
#             label=node_labels,
#             color=node_colors
#         ),
#         link=dict(
#             source=source,
#             target=[i + len(loc_prod) for i in target],
#             value=value,
#             label=link_labels,
#             color=link_colors
#         ))])

#     # Calculer les émissions de CO2 pour le transport et la production
#     co2_emissions = [environment_engine.calculate_distribution_co2_emissions(loc_prod[s], loc_demand[t], value[i]) for i, (s, t) in enumerate(zip(source, target))]
#     production_co2_emissions = [environment_engine.calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

#     production_co2_totals = {location: 0 for location in loc_prod}
#     market2_totals = {location: 0 for location in loc_demand}

#     # Agréger les émissions de CO2 par lieu de production et marché
#     for s, t, p, v in zip(source, target, production_co2_emissions, value):
#         production_co2_totals[loc_prod[s]] += p
#         market2_totals[loc_demand[t]] += v

#     node2_labels = [f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))]
#     node2_labels += [f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

#     link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

#     # Créer et afficher le diagramme Sankey pour les émissions de CO2
#     fig_CO2 = go.Figure(data=[go.Sankey(
#         node=dict(
#             pad=15,
#             thickness=20,
#             line=dict(color="black", width=0.5),
#             label=node2_labels,
#             color=node_colors
#         ),
#         link=dict(
#             source=source,
#             target=[i + len(loc_prod) for i in target],
#             value=co2_emissions,
#             label=link2_labels,
#             color=link_colors
#         ))])

#     # Afficher les diagrammes Sankey
#     fig_prod.show()
#     fig_CO2.show()

#     # Plot des émissions de CO2 de production par pays
#     data_tools.plot_production_co2_emissions(production_co2_totals)

if __name__ == '__main__':
    main_function()
