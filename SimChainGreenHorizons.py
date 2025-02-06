import os
import math
import copy
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import line_production.line_production as line_production
import economic.cost_engine as cost_engine
import distribution.distribution_engine as distribution_engine
from optimization.optimization_engine import run_supply_chain_optimization, run_supply_chain_optimization_minimize_co2
import environment.environment_engine as environment_engine
import utils.data_tools as data_tools
from line_production.line_production_settings import lines_config
from line_production.production_engine import calculate_capacity_limits, load_capacity_limits, run_simple_supply_allocation
from supply.supply_settings import suppliers
import supply.supply_engine as supply_engine
from optimization.optimization_engine import select_best_supplier

def main_function():

    # Exécution de la simulation pour plusieurs lignes de production
    all_production_data, all_enviro_data = line_production.run_simulation(lines_config)
    max_production = {}
    capacity_limits = {}
    cap = {}


    # Traiter les données de chaque ligne indépendamment ou les agréger
    for i, (production_data, enviro_data) in enumerate(zip(all_production_data, all_enviro_data)):
    
        location = lines_config[i]['location']
        total_seats_made = production_data['Total Seats made'][1][-1]  # Dernier total produit
        max_production[location] = total_seats_made

        print(f"Max Ligne de production {i+1} ({location}): {total_seats_made} sièges produits.")



    # data_tools.display_all_lca_indicators(all_production_data, all_enviro_data, lines_config)
    # data_tools.display_all_stock_variations(all_production_data, lines_config)



    # Calculer les capacités dynamiquement
    capacity_limits = load_capacity_limits(max_production)


    freight_cost, demand = distribution_engine.load_freight_costs_and_demands()


    


    # Appel de la fonction
    source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap = run_simple_supply_allocation(capacity_limits, demand)
    allocation = supply_engine.simple_supply_allocation(production_totals)


    # 5️⃣ **Vérification de l’approvisionnement et des fournisseurs sélectionnés**
    print("\n📦 **Fournisseurs sélectionnés pour chaque site de production :**")
    for location in production_totals.keys():
        supply_details = supply_engine.manage_fixed_supply(location)
        print(f"📍 {location}:")
        for material, details in supply_details.items():
            print(f"  - {material.capitalize()} : {details['supplier']} (délai {details['delivery_time']} jours)")
    

    # Affichage des résultats
    # print("Capacités dynamiques calculées :", capacity_limits)
    # print("Supply Allocation:",allocation)
    # print("Production Totals:", production_totals)
    # print("Market Totals:", market_totals)
    # print("Capacités:", cap)

    # 6️⃣ **Vérification de l’équilibre production vs demande**
    total_production = sum(production_totals.values())
    total_demand = sum(market_totals.values())

    print("\n📊 **Résumé de l’allocation :**")
    print(f"🔹 Production totale : {total_production}")
    print(f"🔹 Demande totale : {total_demand}")
    if total_production >= total_demand:
        print("✅ L’offre est suffisante pour répondre à la demande.")
    else:
        print("⚠️ L’offre est insuffisante pour couvrir la demande !")

    # 7️⃣ **Calcul des coûts**
    cost_results = cost_engine.calculate_total_costs(
        source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap
    )

    print("\n💰 **Coûts par pays :**")
    for country, cost in cost_results['country_costs'].items():
        print(f"  {country}: {cost:.2f} €")

    print(f"\n💰 **Coût total :** {cost_results['total_cost']:.2f} €")

    # 8️⃣ **Calcul des indicateurs environnementaux**
    production_co2_totals = {}
    transport_co2_totals = []

    for i, source_index in enumerate(source):
        source_location = loc_prod[source_index]
        dest_location = loc_demand[target[i]]
        seats_sent = value[i]  # 🔹 Nombre de sièges envoyés à ce pays

        print(f"🔎 Vérification : Source = {source_location}, Destination = {dest_location}, Sièges envoyés : {seats_sent}")
        
        # Utiliser directement l’indicateur "Climate Change" du LCA Production basé sur les sièges envoyés
        lca_indicators = environment_engine.calculate_lca_production_IFE_raw(seats_sent)
        production_co2 = lca_indicators["Climate Change"]

        # 🔹 Ajouter les émissions LCA pour ce flux spécifique
        if dest_location not in production_co2_totals:
            production_co2_totals[dest_location] = 0  # Initialiser si besoin
        production_co2_totals[dest_location] += production_co2

        print(f"🔍 Vérification des émissions LCA pour {source_location} → {dest_location}:")
        print(f"➡ Sièges envoyés : {seats_sent}")
        print(f"➡ Valeur LCA Climate Change : {production_co2:.2f} kg CO₂")

        # Calcul des émissions liées au transport
        transport_co2 = environment_engine.calculate_distribution_co2_emissions(source_location, dest_location, seats_sent)
        transport_co2_totals.append(transport_co2)

    total_co2 = sum(production_co2_totals.values()) + sum(transport_co2_totals)

    # 📊 **Affichage des nouvelles émissions LCA**
    print("\n🌱 **Émissions de CO₂ par pays (Production) :**")
    for country, emissions in production_co2_totals.items():
        print(f"  {country}: {emissions:.2f} kg CO₂")

    print("\n🚛 **Émissions de CO₂ liées au transport :**")
    print(f"🔹 Total : {sum(transport_co2_totals):.2f} kg CO₂")


    print("\n🚛 **Vérification des flux de transport et des distances utilisées :**")
    for i, source_index in enumerate(source):
        source_location = loc_prod[source_index]
        dest_location = loc_demand[target[i]]
        distance_used = distribution_engine.distances.get((source_location, dest_location), "Non trouvé")

        print(f"📍 {source_location} → {dest_location} | Distance utilisée : {distance_used} km | CO₂ : {transport_co2_totals[i]:.2f} kg")


    print(f"\n🌍 **Émissions de CO₂ totales :** {total_co2:.2f} kg CO₂")

    # 9️⃣ **Visualisation des résultats**
    print("\n📈 **Affichage des résultats :**")

    #Affichage des données de production

    # 🔹 Création d'un seul graphique avec deux subplots (Sankey + Bar Chart)
    fig = make_subplots(
        rows=2, cols=1, 
        subplot_titles=[
            "Flux de production et de distribution (Sankey)", 
            "Coûts de production par pays"
        ],
        specs=[[{"type": "domain"}], [{"type": "xy"}]],  # 🔹 Définir Sankey en "domain" et Bar Chart en "xy"
        vertical_spacing=0.15  # 🔹 Réduction de l'espacement pour une meilleure répartition
    )

    # Graphique 1️⃣ : Diagramme de Sankey
    sankey_figure = data_tools.plot_production_sankey(
        source, target, value, production_totals, market_totals, loc_prod, loc_demand, return_figure=True
    )

    # Ajouter le diagramme de Sankey au subplot (avec type domain)
    fig.add_trace(
        go.Sankey(
            node=sankey_figure.data[0].node,  # Récupérer les noeuds du Sankey
            link=sankey_figure.data[0].link   # Récupérer les liens du Sankey
        ),
        row=1, col=1
    )

    # Graphique 2️⃣ : Coûts de production par pays
    fig.add_trace(go.Bar(
        x=list(cost_results['country_costs'].keys()),
        y=list(cost_results['country_costs'].values()),
        text=[f"{v:.2f} €" for v in cost_results['country_costs'].values()],
        textposition='outside',
        marker_color='green'
    ), row=2, col=1)

    # Mise à jour de la mise en page
    fig.update_layout(
        title="Analyse des flux de production et des coûts",
        height=900,  # 🔹 Ajustement de la hauteur totale
        showlegend=False
    )

    # Ajustement des titres des axes
    fig.update_xaxes(title_text="Pays producteur", row=2, col=1)
    fig.update_yaxes(title_text="Coût de production (€)", row=2, col=1)

    # Affichage du graphique combiné
    fig.show()



    # 🔹 Données pour les graphiques
    production_co2_per_producer = {}  # Total par pays de production
    production_co2_per_requester = {}  # Répartition par pays demandeur

    for i, source_index in enumerate(source):
        source_location = loc_prod[source_index]
        dest_location = loc_demand[target[i]]
        seats_sent = value[i]  # 🔹 Nombre de sièges envoyés
        production_co2 = production_co2_totals[dest_location]  # Déjà calculé

        # 🔹 Agréger les émissions par pays producteur
        if source_location not in production_co2_per_producer:
            production_co2_per_producer[source_location] = 0
        production_co2_per_producer[source_location] += production_co2

        # 🔹 Répartition des émissions de production par pays demandeur
        if dest_location not in production_co2_per_requester:
            production_co2_per_requester[dest_location] = 0
        production_co2_per_requester[dest_location] += production_co2

    # 🔹 Création d'un seul graphique avec deux subplots
    fig = make_subplots(
        rows=2, cols=1, 
        subplot_titles=[
            "Total des émissions de production par pays producteur", 
            "Répartition des émissions de production par pays demandeur"
        ],
        vertical_spacing=0.2  # Espacement entre les deux graphiques
    )

    # Graphique 1️⃣ : Total des émissions de production par pays producteur
    fig.add_trace(go.Bar(
        x=list(production_co2_per_producer.keys()),
        y=list(production_co2_per_producer.values()),
        text=[f"{v:.2f}" for v in production_co2_per_producer.values()],
        textposition='outside',
        marker_color='blue'
    ), row=1, col=1)

    # Graphique 2️⃣ : Répartition des émissions de production par pays demandeur
    fig.add_trace(go.Bar(
        x=list(production_co2_per_requester.keys()),
        y=list(production_co2_per_requester.values()),
        text=[f"{v:.2f}" for v in production_co2_per_requester.values()],
        textposition='outside',
        marker_color='orange'
    ), row=2, col=1)

    # Mise à jour de la mise en page
    fig.update_layout(
        title="Analyse des émissions de production et de leur répartition",
        height=800,  # Ajustement de la hauteur pour tout afficher
        showlegend=False
    )

    # Ajustement des titres des axes
    fig.update_xaxes(title_text="Pays producteur", row=1, col=1)
    fig.update_yaxes(title_text="Émissions CO₂ (kg CO₂)", row=1, col=1)

    fig.update_xaxes(title_text="Pays demandeur", row=2, col=1)
    fig.update_yaxes(title_text="Émissions CO₂ (kg CO₂)", row=2, col=1)

    # Affichage du graphique
    fig.show()


    # 🔍 10️⃣ Filtrer uniquement les lignes de production actives APRES allocation
    active_production_data = []
    active_enviro_data = []
    active_lines_config = []

    for i, production_data in enumerate(all_production_data):
        location = lines_config[i]['location']
        total_seats_made = production_data['Total Seats made'][1][-1]

        # 🔥 Si la ligne a effectivement produit, on la garde
        if location in production_totals and production_totals[location] > 0:
            active_production_data.append(production_data)
            active_enviro_data.append(all_enviro_data[i])
            active_lines_config.append(lines_config[i])

    # 🔥 Vérification finale
    print("\n🔍 **Lignes de production actives après allocation :**")
    for line in active_lines_config:
        print(f"✅ {line['location']} - Production : {production_totals[line['location']]} sièges")

    # 📈 Affichage des indicateurs environnementaux uniquement pour les lignes actives
    if active_production_data:
        print(f"📊 Affichage des indicateurs environnementaux pour {len(active_production_data)} ligne(s) active(s).")
        data_tools.display_all_lca_indicators(active_production_data, active_enviro_data, active_lines_config,production_totals)


    else:
        print("\n⚠️ Aucune ligne de production active, pas d'affichage des indicateurs environnementaux.")



if __name__ == '__main__':
    main_function()
