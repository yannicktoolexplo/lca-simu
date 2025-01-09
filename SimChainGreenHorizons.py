import os
import math
import copy



import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import line_production
import logistics_engine
import production_engine
from optimization_engine import run_supply_chain_optimization, run_supply_chain_optimization_minimize_co2
import environment_engine 
import data_tools

def main_function():

    # Configuration de plusieurs lignes de production
    lines_config = [
        {   'location': 'Texas',  # Location added
            'hours': 8,
            'days': 30,
            'total_time': 240,  # En heures
            'aluminium_capacity': 500,
            'initial_aluminium': 200,
            'foam_capacity': 450,
            'initial_foam': 180,
            'fabric_capacity': 500,
            'initial_fabric': 180,
            'paint_capacity': 250,
            'initial_paint': 180,
            'dispatch_capacity': 600,
            'frame_pre_paint_capacity': 80,
            'armrest_pre_paint_capacity': 80,
            'frame_post_paint_capacity': 140,
            'armrest_post_paint_capacity': 140,
            'aluminium_critial_stock': 60,
            'foam_critical_stock': 60,
            'fabric_critical_stock': 60,
            'paint_critical_stock': 30,
            'num_frame': 3,
            'mean_frame': 0.9,
            'std_frame': 0.15,
            'num_armrest': 3,
            'mean_armrest': 0.9,
            'std_armrest': 0.15,
            'num_paint': 3,
            'mean_paint': 1.8,
            'std_paint': 0.25,
            'num_ensam': 6,
            'mean_ensam': 1,
            'std_ensam': 0.25
        },
        {   'location': 'California',
            'hours': 8,
            'days': 21,
            'total_time': 168,  # En heures
            'aluminium_capacity': 400,
            'initial_aluminium': 150,
            'foam_capacity': 400,
            'initial_foam': 150,
            'fabric_capacity': 400,
            'initial_fabric': 150,
            'paint_capacity': 200,
            'initial_paint': 150,
            'dispatch_capacity': 500,
            'frame_pre_paint_capacity': 60,
            'armrest_pre_paint_capacity': 60,
            'frame_post_paint_capacity': 120,
            'armrest_post_paint_capacity': 120,
            'aluminium_critial_stock': 50,
            'foam_critical_stock': 50,
            'fabric_critical_stock': 50,
            'paint_critical_stock': 20,
            'num_frame': 2,
            'mean_frame': 1,
            'std_frame': 0.1,
            'num_armrest': 2,
            'mean_armrest': 1,
            'std_armrest': 0.2,
            'num_paint': 2,
            'mean_paint': 2,
            'std_paint': 0.3,
            'num_ensam': 5,
            'mean_ensam': 1,
            'std_ensam': 0.2
        },
        {   'location': 'France',
            'hours': 8,
            'days': 21,
            'total_time': 168,  # En heures
            'aluminium_capacity': 400,
            'initial_aluminium': 150,
            'foam_capacity': 400,
            'initial_foam': 150,
            'fabric_capacity': 400,
            'initial_fabric': 150,
            'paint_capacity': 200,
            'initial_paint': 150,
            'dispatch_capacity': 500,
            'frame_pre_paint_capacity': 60,
            'armrest_pre_paint_capacity': 60,
            'frame_post_paint_capacity': 120,
            'armrest_post_paint_capacity': 120,
            'aluminium_critial_stock': 50,
            'foam_critical_stock': 50,
            'fabric_critical_stock': 50,
            'paint_critical_stock': 20,
            'num_frame': 2,
            'mean_frame': 1,
            'std_frame': 0.1,
            'num_armrest': 2,
            'mean_armrest': 1,
            'std_armrest': 0.2,
            'num_paint': 2,
            'mean_paint': 2,
            'std_paint': 0.3,
            'num_ensam': 5,
            'mean_ensam': 1,
            'std_ensam': 0.2
        },
        {   'location': 'UK',
            'hours': 8,
            'days': 21,
            'total_time': 168,  # En heures
            'aluminium_capacity': 400,
            'initial_aluminium': 150,
            'foam_capacity': 400,
            'initial_foam': 150,
            'fabric_capacity': 400,
            'initial_fabric': 150,
            'paint_capacity': 200,
            'initial_paint': 150,
            'dispatch_capacity': 500,
            'frame_pre_paint_capacity': 60,
            'armrest_pre_paint_capacity': 60,
            'frame_post_paint_capacity': 120,
            'armrest_post_paint_capacity': 120,
            'aluminium_critial_stock': 50,
            'foam_critical_stock': 50,
            'fabric_critical_stock': 50,
            'paint_critical_stock': 20,
            'num_frame': 2,
            'mean_frame': 1,
            'std_frame': 0.1,
            'num_armrest': 2,
            'mean_armrest': 1,
            'std_armrest': 0.2,
            'num_paint': 2,
            'mean_paint': 2,
            'std_paint': 0.3,
            'num_ensam': 5,
            'mean_ensam': 1,
            'std_ensam': 0.2
        }
    ]

    suppliers = {
    'aluminium': [
        {'name': 'Constellium', 'location': 'France', 'distance_to_sites': {'Texas': 8000, 'California': 8200, 'France': 200, 'UK': 500}},
        {'name': 'Arconic', 'location': 'USA', 'distance_to_sites': {'Texas': 2000, 'California': 3000, 'France': 8500, 'UK': 9000}},
        {'name': 'Norsk Hydro', 'location': 'Norway', 'distance_to_sites': {'Texas': 7500, 'California': 8000, 'France': 1500, 'UK': 1200}}
    ],
    'fabric': [
        {'name': 'Toray Industries', 'location': 'Japan', 'distance_to_sites': {'Texas': 11000, 'California': 10500, 'France': 9400, 'UK': 9100}},
        {'name': 'Hexcel', 'location': 'USA', 'distance_to_sites': {'Texas': 1000, 'California': 2500, 'France': 8500, 'UK': 8700}}
    ],
    'polymers': [
        {'name': 'Sabic', 'location': 'Saudi Arabia', 'distance_to_sites': {'Texas': 13000, 'California': 12500, 'France': 4500, 'UK': 4200}},
        {'name': 'BASF', 'location': 'Germany', 'distance_to_sites': {'Texas': 9500, 'California': 9800, 'France': 300, 'UK': 600}}
    ]
    }

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
        alu_supply = logistics_engine.calculate_best_supply_chain('aluminium', alu_quantity, location, suppliers)
        fabric_supply = logistics_engine.calculate_best_supply_chain('fabric', fabric_quantity, location, suppliers)
        polymer_supply = logistics_engine.calculate_best_supply_chain('polymers', polymer_quantity, location, suppliers)

        # Résumer les résultats
        print(f"Fournisseur aluminium: {alu_supply['supplier']}, Coût: {alu_supply['cost']:.2f} €, CO₂: {alu_supply['emissions']:.2f} kg")
        print(f"Fournisseur tissu: {fabric_supply['supplier']}, Coût: {fabric_supply['cost']:.2f} €, CO₂: {fabric_supply['emissions']:.2f} kg")
        print(f"Fournisseur polymères: {polymer_supply['supplier']}, Coût: {polymer_supply['cost']:.2f} €, CO₂: {polymer_supply['emissions']:.2f} kg")


#     """Main function to run the analysis and plots."""
    
#     # Configuration personnalisée
#     custom_config = line_production.FactoryConfig(
#         hours=8,  # Par exemple, changer les heures de travail par jour à 10
#         days=21,  # Par exemple, changer le nombre de jours ouvrables à 30
#         initial_aluminium=150,  # Par exemple, changer le stock initial d'aluminium
#         initial_foam=150,  # Par exemple, changer le stock initial de mousse
#         initial_fabric=150,  # Par exemple, changer le stock initial de tissu
#         initial_paint=150  # Par exemple, changer le stock initial de peinture
#     )

#     # Exécution de la simulation avec la configuration personnalisée
#     seat_factory = line_production.run_simulation(custom_config)

#     # Collectez les données depuis line_production
#     production_data = line_production.get_data(seat_factory)
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

#     # Préparer les données pour 'Total Seats made'
#     total_seats_data = production_data['Total Seats made']
    
#     # Plot des niveaux de stock et du total des sièges produits
#     data_tools.plot_stock_levels(stock_data, total_seats_data)
    
#     # Plot de la consommation des ressources
#     # data_tools.plot_resource_consumption(enviro_data)
    
#     # Plot de la consommation totale des ressources
#     # data_tools.plot_total_resource_consumption(enviro_data)

#     # Calculer les limites de capacité basées sur les données de production
#     capacity_limits = production_engine.calculate_capacity_limits(production_data)

#     # Exécuter l'optimisation de la chaîne d'approvisionnement avec les limites de capacité calculées
#     source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_supply_chain_optimization(capacity_limits)

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
