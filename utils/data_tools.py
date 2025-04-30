import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math
import environment.environment_engine as environment_engine

def plot_lca_indicators(lca_data,title="LCA Indicators", color='rgba(0, 0, 255, 0.6)'):
    """
    Plot LCA indicators using Plotly.
    
    :param lca_data: Dictionary with LCA indicators
    """
    categories = list(lca_data.keys())
    values = list(lca_data.values())

     # Ajouter des annotations pour afficher les valeurs au-dessus de chaque barre
    annotations = []
    for i, value in enumerate(values):
        annotations.append(dict(x=categories[i], y=value, text=f'{value:.2f}', showarrow=False, yshift=10))

    fig = go.Figure(data=[go.Bar(x=categories, y=values, marker_color=color)])
    fig.update_layout(
        title_text=title,
        xaxis_title="Indicator",
        yaxis_title="Value",
        annotations=annotations
    )

    fig.show()

def plot_lca_combined_indicators(production_lca, usage_lca, title="Combined LCA Indicators"):
    """
    Plot combined LCA indicators showing both production and usage phases stacked.
    
    :param production_lca: Dictionary with production LCA indicators
    :param usage_lca: Dictionary with usage LCA indicators
    :param title: Title for the plot
    """
    categories = list(production_lca.keys())
    production_values = list(production_lca.values())
    usage_values = list(usage_lca.values())

    fig = go.Figure()

    # Production bar with annotations
    fig.add_trace(go.Bar(
        name='Production',
        x=categories,
        y=production_values,
        marker_color='rgba(0, 0, 255, 0.6)',
        text=[f'{v:.2f}' for v in production_values],  # Annotation text
        textposition='inside'  # Position annotations inside bars
    ))


    # Usage bar with annotations, stacked on top of production
    fig.add_trace(go.Bar(
        name='Usage',
        x=categories,
        y=usage_values,
        marker_color='rgba(255, 223, 0, 0.6)',
        text=[f'{v:.2f}' for v in usage_values],  # Annotation text
        textposition='inside'  # Position annotations inside bars
    ))

    fig.update_layout(
        title_text=title,
        xaxis_title="Indicator",
        yaxis_title="Value",
        barmode='stack',  # Stack bars on top of each other
        showlegend=True
    )

    fig.show() 

def plot_stock_levels(stock_data, total_seats_data):
    """Plot stock levels using Plotly."""
    fig = make_subplots(rows=1, cols=1, shared_xaxes=True, subplot_titles=["Stock Levels Over Time"])

    for label, (time_vector, values) in stock_data.items():
        fig.add_trace(go.Scatter(x=time_vector, y=values, mode='lines+markers', name=label), row=1, col=1)

    fig.update_layout(height=600, title_text="Stock Levels Over Time", showlegend=True)
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Stock Level", row=1, col=1)

    fig.show()


def plot_resource_consumption(data_enviro):
    """Plot resource consumption using Plotly."""
    fig_conso = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("Electrical Consumption", "Water Consumption", "Mineral and Metal Used"))

    fig_conso.add_trace(go.Scatter(x=data_enviro['Electrical Consumption'][0], y=data_enviro['Electrical Consumption'][1], fill='tozeroy', name='Electrical Consumption', fillcolor='rgba(0, 0, 255, 0.2)', marker={'color': 'rgba(0, 0, 255, 1)'}), row=1, col=1)
    fig_conso.add_trace(go.Scatter(x=data_enviro['Water Consumption'][0], y=data_enviro['Water Consumption'][1], fill='tozeroy', name='Water Consumption', fillcolor='rgba(0, 255, 0, 0.2)', marker={'color': 'rgba(0, 255, 0, 1)'}), row=2, col=1)
    fig_conso.add_trace(go.Scatter(x=data_enviro['Mineral and Metal Used'][0], y=data_enviro['Mineral and Metal Used'][1], fill='tozeroy', name='Mineral and Metal Used', fillcolor='rgba(255, 0, 0, 0.2)', marker={'color': 'rgba(255, 0, 0, 1)'}), row=3, col=1)

    fig_conso.update_layout(height=900, title_text="Resource Consumption over Time", showlegend=False)
    fig_conso.update_xaxes(title_text="Time")
    fig_conso.update_yaxes(title_text="Consumption")

    fig_conso.show()

def plot_total_resource_consumption(data_enviro):
    """Plot total resource consumption using Plotly."""
    total_electrical = sum(data_enviro['Electrical Consumption'][1])
    total_water = sum(data_enviro['Water Consumption'][1])
    total_minerals = sum(data_enviro['Mineral and Metal Used'][1])

    categories = ['Electrical Consumption', 'Water Consumption', 'Mineral and Metal Used']
    totals = [total_electrical, total_water, total_minerals]

    fig = go.Figure(data=[go.Bar(x=categories, y=totals, marker_color=['rgba(0, 0, 255, 0.6)', 'rgba(0, 255, 0, 0.6)', 'rgba(255, 0, 0, 0.6)'])])
    fig.update_layout(title_text="Total Resource Consumption", xaxis_title="Resource Type", yaxis_title="Total Consumption")

    fig.show()

def plot_production_co2_emissions(production_co2_totals):
    """Plot production CO2 emissions by country using Plotly."""
    countries = list(production_co2_totals.keys())
    co2_emissions = list(production_co2_totals.values())

    # Calculer les émissions globales
    total_emissions = sum(co2_emissions)
    countries.append('Global Total')
    co2_emissions.append(total_emissions)

    fig = go.Figure(data=[go.Bar(x=countries, y=co2_emissions, marker_color='rgba(255, 0, 0, 0.6)')])

    # Ajouter des annotations pour afficher les totaux des émissions de CO2
    annotations = []
    for i, value in enumerate(co2_emissions):
        annotations.append(dict(x=countries[i], y=value, text=f'{value:.2f} kg', showarrow=False, yshift=10))

    fig.update_layout(title_text="Production CO2 Emissions by Country", xaxis_title="Country", yaxis_title="CO2 Emissions (kg)", annotations=annotations)

    fig.show()    

def plot_surface(absolute_path):
    """
    Creates a surface chart from a dataframe and three columns.
    The function reads a CSV file, filters data based on station IDs, and plots the surface roughness over simulated time.
    """
    surface_data = pd.read_csv(os.path.join(absolute_path, 'output/shaft.csv'))

    # Convert station_id, surface, and time columns to numeric values
    surface_data['station_id'] = pd.to_numeric(surface_data['station_id'], errors='coerce').astype('Int64')
    surface_data['surface'] = pd.to_numeric(surface_data['surface'], errors='coerce').astype(float)
    surface_data['time'] = pd.to_numeric(surface_data['time'], errors='coerce').astype('Int64')

    labels = ['drill', 'lathe', 'polisher']

    # Plot surface roughness over simulated time for each station ID
    for index, label in enumerate(labels):
        plt.plot(surface_data[surface_data['station_id'] == index]['time'],
                 surface_data[surface_data['station_id'] == index]['surface'], label=label)

    plt.xlabel('Sim. time')
    plt.ylabel('Surface roughness')
    plt.title('Surface over simulated time')
    plt.legend(loc='upper right')
    plt.savefig(os.path.join(absolute_path, 'output/shaft_surface.png'))


def plotting_of_data(ax, time, data_entry, ysize, label_string):
    """
    Plots data on the given axes with custom gridlines and labels.
    The function takes axes, time data, data entry, y-axis tick size, and label string as input and plots the data on the axes.
    """
    ax.grid()
    ax.set_xlim(0, max(time))
    ax.xaxis.set_major_locator(ticker.LinearLocator(2))
    xminors = ["%d" % int(x) for x in np.arange(0, int(max(time)), 1)]
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(1.0))
    ax.xaxis.set_minor_formatter(ticker.FixedFormatter(xminors))
    ax.tick_params(which='minor', width=0.75, length=3.6, labelsize=10)

    ax.set_ylim(0, max(data_entry))
    ax.yaxis.set_major_locator(ticker.LinearLocator(2))
    yminors = ["%d" % int(y) for y in np.arange(0, int(max(data_entry)), ysize)]
    ax.yaxis.set_minor_locator(ticker.MultipleLocator(ysize))
    ax.yaxis.set_minor_formatter(ticker.FixedFormatter(yminors))
    ax.tick_params(which='minor', width=0.75, length=3.6, labelsize=10)

    ax.plot(time, data_entry, label=label_string)
    ax.legend()

def plot_co2_emissions(csv_file_path):
    """
    Creates a bar chart of total CO2 emissions by transportation mode.
    The function reads a CSV file, calculates the sum of CO2 emissions for each transportation mode,
    and creates a bar chart with customized colors, labels, and numeric annotations.
    """
    # Read the CSV file
    df = pd.read_csv(csv_file_path)

    # Calculate the sum of CO2 emissions for each transportation mode
    total_co2_road = df['CO2 Road'].sum()
    total_co2_rail = df['CO2 Rail'].sum()
    total_co2_sea = df['CO2 Sea'].sum()
    total_co2_air = df['CO2 Air'].sum()
    total_co2 = df['CO2 Total'].sum()

    # Prepare data for the bar chart
    modes = ['Road', 'Rail', 'Sea', 'Air', 'Total']  # Transportation modes
    emissions = [total_co2_road, total_co2_rail, total_co2_sea, total_co2_air, total_co2]  # CO2 emissions for each mode

    # Create a bar diagram with customized colors
    plt.figure(figsize=(10, 6))
    plt.bar(modes, emissions, color=['blue', 'orange', 'green', 'red', 'purple'])

    # Add labels and title to the chart
    plt.xlabel('Transportation Mode')
    plt.ylabel('CO2 Emissions (kg CO2e)')
    plt.title('Total CO2 Emissions by Transportation Mode')

    # Display numeric labels on each bar with a small offset for better visibility
    for i, v in enumerate(emissions):
        plt.text(i, v + max(emissions) * 0.01, f"{v:.2f}", ha='center', va='bottom')

    # Adjust layout and show the plot
    plt.tight_layout()
    plt.show()

def plot_bar(data_bars, modes, xlabel='X Label', ylabel='Y Label', title='Title'):
    """
    Creates a customizable bar chart from given data and mode names.
    The function takes data, mode names, and optional labels and title as input,
    and creates a bar chart with numeric annotations on each bar.
    """
    # Create a bar diagram
    plt.figure(figsize=(10, 6))
    plt.bar(modes, data_bars)

    # Add labels and title to the chart
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)

    # Display numeric labels on each bar with a small offset for better visibility
    for i, v in enumerate(data_bars):
        plt.text(i, v + max(data_bars) * 0.01, f"{v:.2f}", ha='center', va='bottom')

    # Adjust layout and show the plot
    plt.tight_layout()
    plt.show()

def round_to_nearest_significant(number):
    """
    Rounds a number to the nearest significant multiple of the power of 10.
    This function helps in rounding numbers to a more human-readable format by finding the closest significant power of 10.
    """
    if number == 0:
        return 0

    # Calculate the power of 10 based on the logarithm of the absolute value of the number
    power = 10 ** math.floor(math.log10(abs(number)))

    # Determine the nearest significant multiple of the power of 10
    return power * 10 if number >= power * 5 else power

# def plot_production_sankey(source, target, value, production_totals, market_totals, loc_prod, loc_demand):
#     """
#     Create and display a Sankey diagram for production distribution.

#     :param source: List of source indices corresponding to production locations.
#     :param target: List of target indices corresponding to demand locations.
#     :param value: List of quantities transported between source and target.
#     :param production_totals: Dictionary with total production quantities for each location.
#     :param market_totals: Dictionary with market demand totals for each location.
#     :param loc_prod: List of production locations.
#     :param loc_demand: List of demand locations.
#     """
#     # Prepare labels and colors for the Sankey diagram
#     node_labels = [
#         f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))
#     ]
#     node_labels += [
#         f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))
#     ]
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
#         'France': 'rgba(214, 39, 40, 0.5)',
#     }

#     production_colors = [base_colors[place] for place in loc_prod]
#     market_colors = [target_colors[place] for place in loc_demand]
#     node_colors = production_colors + market_colors
#     link_colors = [market_colors[i] for i in target]

#     # Create and display the Sankey diagram
#     fig_prod = go.Figure(
#         data=[
#             go.Sankey(
#                 node=dict(
#                     pad=15,
#                     thickness=20,
#                     line=dict(color="black", width=0.5),
#                     label=node_labels,
#                     color=node_colors,
#                 ),
#                 link=dict(
#                     source=source,
#                     target=[i + len(loc_prod) for i in target],
#                     value=value,
#                     label=link_labels,
#                     color=link_colors,
#                 ),
#             )
#         ]
#     )

#     # Update layout and show plot
#     fig_prod.update_layout(
#         title_text="Production Distribution Sankey Diagram",
#         font_size=10
#     )
#     fig_prod.show()

import plotly.graph_objects as go

def plot_production_sankey(source, target, value, production_totals, market_totals, loc_prod, loc_demand, return_figure=False):
    """
    Génère un diagramme de Sankey pour représenter les flux de production et de distribution.

    :param source: Liste des indices des sources.
    :param target: Liste des indices des cibles.
    :param value: Liste des valeurs des flux.
    :param production_totals: Dictionnaire des productions totales.
    :param market_totals: Dictionnaire des demandes totales.
    :param loc_prod: Liste des sites de production.
    :param loc_demand: Liste des marchés de consommation.
    :param return_figure: Booléen, si True retourne la figure Plotly au lieu de l'afficher.
    :return: Objet Plotly Figure si return_figure=True, sinon affiche directement le graphique.
    """

    # 🔹 Création des labels pour les nœuds avec quantité produite et demandée
    node_labels = [
        f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))
    ]
    node_labels += [
        f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))
    ]
    link_labels = [f"{v:,.0f} Units" for v in value]

    # 🔹 Définition des couleurs
    base_colors = {
        'Texas': 'rgba(255, 127, 14, 0.8)',
        'California': 'rgba(255, 127, 14, 0.8)',
        'UK': 'rgba(148, 103, 189, 0.8)',
        'France': 'rgba(214, 39, 40, 0.8)',
    }

    target_colors = {
        'USA': 'rgba(255, 127, 14, 0.5)',
        'Canada': 'rgba(255, 215, 0, 0.5)',
        'Japan': 'rgba(44, 160, 44, 0.5)',
        'Brazil': 'rgba(31, 119, 180, 0.5)',
        'France': 'rgba(214, 39, 40, 0.5)',
    }

    # 🔹 Attribution des couleurs aux nœuds et liens
    production_colors = [base_colors.get(place, 'rgba(100, 100, 100, 0.8)') for place in loc_prod]
    market_colors = [target_colors.get(place, 'rgba(150, 150, 150, 0.5)') for place in loc_demand]
    node_colors = production_colors + market_colors
    link_colors = [market_colors[i] for i in target]  # Couleur des flux basée sur la destination

    # 🔹 Création du diagramme de Sankey
    fig_prod = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=node_labels,
                    color=node_colors,
                ),
                link=dict(
                    source=source,
                    target=[i + len(loc_prod) for i in target],  # Décalage pour séparer source & destination
                    value=value,
                    label=link_labels,
                    color=link_colors,
                ),
            )
        ]
    )

    # 🔹 Mise en page améliorée
    fig_prod.update_layout(
        title_text="Flux de production et de distribution (Sankey)",
        font_size=10,
        height=600  # Ajustement pour une meilleure visibilité
    )

    # 🔹 Retourne ou affiche le diagramme
    if return_figure:
        return fig_prod  # 🔹 Retourne l'objet Plotly si demandé
    else:
        fig_prod.show()  # 🔹 Sinon, affiche directement


def plot_sankey_production_co2_emissions(source, target, co2_emissions, production_co2_emissions, value, loc_prod, loc_demand, return_figure=False):
    """
    Create and display a Sankey diagram for CO2 emissions.

    :param source: List of source indices corresponding to production locations.
    :param target: List of target indices corresponding to demand locations.
    :param co2_emissions: List of CO2 emissions for transportation between source and target.
    :param production_co2_emissions: List of CO2 emissions for production at each source location.
    :param value: List of quantities transported between source and target.
    :param loc_prod: List of production locations.
    :param loc_demand: List of demand locations.
    """
    # Aggregate CO2 emissions by production location and market
    production_co2_totals = {location: 0 for location in loc_prod}
    market2_totals = {location: 0 for location in loc_demand}

    for s, t, p, v in zip(source, target, production_co2_emissions, value):
        production_co2_totals[loc_prod[s]] += p
        market2_totals[loc_demand[t]] += v

    # Prepare labels and colors for the Sankey diagram
    node2_labels = [
        f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))
    ]
    node2_labels += [
        f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))
    ]

    link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

    base_colors = {
        'Texas': 'rgba(255, 127, 14, 0.8)',
        'California': 'rgba(255, 127, 14, 0.8)',
        'UK': 'rgba(148, 103, 189, 0.8)',
        'France': 'rgba(214, 39, 40, 0.8)',
    }

    target_colors = {
        'USA': 'rgba(255, 127, 14, 0.5)',
        'Canada': 'rgba(255, 215, 0, 0.5)',
        'Japan': 'rgba(44, 160, 44, 0.5)',
        'Brazil': 'rgba(31, 119, 180, 0.5)',
        'France': 'rgba(214, 39, 40, 0.5)',
    }

    production_colors = [base_colors[place] for place in loc_prod]
    market_colors = [target_colors[place] for place in loc_demand]
    node_colors = production_colors + market_colors
    link_colors = [market_colors[i] for i in target]

    # Create and display the Sankey diagram for CO2 emissions
    fig_CO2 = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=node2_labels,
                    color=node_colors,
                ),
                link=dict(
                    source=source,
                    target=[i + len(loc_prod) for i in target],
                    value=co2_emissions,
                    label=link2_labels,
                    color=link_colors,
                ),
            )
        ]
    )

    # Update layout and show plot
    fig_CO2.update_layout(
        title_text="CO2 Emissions Sankey Diagram",
        font_size=10
    )
    if return_figure:
        return fig_CO2
    else:
        fig_CO2.show()

def plot_costs(country_costs, total_cost):
    """
    Plot the costs per producing country and the total cost using Plotly.

    :param country_costs: Dictionary with costs per country.
    :param total_cost: Total cost across all countries.
    """
    countries = list(country_costs.keys())
    costs = list(country_costs.values())

    # Create the bar chart
    fig = go.Figure()

    # Add bars for each country
    fig.add_trace(go.Bar(
        x=countries,
        y=costs,
        text=[f'{cost:.2f}' for cost in costs],
        textposition='auto',
        name='Country Costs'
    ))

    # Add a bar for the total cost
    fig.add_trace(go.Bar(
        x=['Total'],
        y=[total_cost],
        text=[f'{total_cost:.2f}'],
        textposition='auto',
        name='Total Cost',
        marker=dict(color='red')
    ))

    # Update layout
    fig.update_layout(
        title='Production Costs per Country and Total',
        xaxis_title='Producing Country',
        yaxis_title='Cost (€)',
        barmode='group',
        legend_title='Legend'
    )

    # Show the plot
    fig.show()





# def display_all_lca_indicators(all_production_data, all_enviro_data, lines_config, production_totals, use_allocated_production=True):
#     """
#     Affiche les indicateurs LCA pour chaque pays en utilisant soit la production réelle après allocation,
#     soit la production maximale initialement simulée.

#     :param all_production_data: Liste des données de production par ligne.
#     :param all_enviro_data: Liste des données environnementales.
#     :param lines_config: Configuration des lignes de production.
#     :param production_totals: Dictionnaire des productions réelles après allocation.
#     :param use_allocated_production: Booléen, si True utilise la production réelle, sinon utilise la production simulée.
#     """

#     # 🔍 Vérification stricte des lignes actives
#     active_data = [
#         (prod_data, enviro_data, config)
#         for prod_data, enviro_data, config in zip(all_production_data, all_enviro_data, lines_config)
#         if production_totals.get(config['location'], 0) > 0  # Filtre basé sur la production réelle
#     ]

#     if not active_data:
#         print("⚠️ Aucune ligne active, pas d'affichage des indicateurs LCA.")
#         return


#     # 🔥 Debugging: Afficher exactement les lignes prises en compte
#     for _, _, line_config in active_data:
#         print(f"✅ {line_config['location']} inclus dans l'affichage des LCA.")

#     # Titles for each column
#     column_titles = ["Production LCA", "Usage LCA", "Combined LCA"]

#     # Create subplots: One row per production line, one column per type of LCA
#     fig_lca = make_subplots(
#         rows=len(active_data), cols=3,
#         column_titles=column_titles,
#         horizontal_spacing=0.1,
#         vertical_spacing=0.1
#     )

#     for i, (production_data, enviro_data, line_config) in enumerate(active_data):
#         location = line_config['location']
        
#         # Choix de la production à utiliser
#         total_seats_made = production_totals.get(location, 0) if use_allocated_production else production_data['Total Seats made'][1][-1]

#         print(f"🔍 Vérification LCA pour {location} (mode {'alloué' if use_allocated_production else 'simulé'}):")
#         print(f"➡ Production utilisée : {total_seats_made}")

#         # Calcul des indicateurs LCA
#         production_lca = environment_engine.calculate_lca_indicators_pers_eq(total_seats_made)
#         usage_lca = environment_engine.calculate_lca_indicators_usage_phase(total_seats_made, seat_weight=120)
#         combined_lca = {key: production_lca[key] + usage_lca[key] for key in production_lca.keys()}

#         # Ajouter les valeurs sur les barres (text)
#         fig_lca.add_trace(
#             go.Bar(
#                 x=list(production_lca.keys()),
#                 y=list(production_lca.values()),
#                 text=[f"{v:.2f}" for v in production_lca.values()],
#                 textposition='inside',
#                 marker_color='blue'
#             ),
#             row=i + 1, col=1
#         )

#         fig_lca.add_trace(
#             go.Bar(
#                 x=list(usage_lca.keys()),
#                 y=list(usage_lca.values()),
#                 text=[f"{v:.2f}" for v in usage_lca.values()],
#                 textposition='inside',
#                 marker_color='orange'
#             ),
#             row=i + 1, col=2
#         )

#         fig_lca.add_trace(
#             go.Bar(
#                 x=list(combined_lca.keys()),
#                 y=list(combined_lca.values()),
#                 text=[f"{v:.2f}" for v in combined_lca.values()],
#                 textposition='inside',
#                 marker_color='green'
#             ),
#             row=i + 1, col=3
#         )

#         # 🔹 Ajout de la localisation dans l'axe Y
#         fig_lca.update_yaxes(title_text=f"LCA Value ({location})", row=i + 1, col=1)
#         fig_lca.update_yaxes(title_text=f"LCA Value ({location})", row=i + 1, col=2)
#         fig_lca.update_yaxes(title_text=f"LCA Value ({location})", row=i + 1, col=3)

#     # Mise à jour du layout général
#     fig_lca.update_layout(
#         title="LCA Indicators for Active Production Lines",
#         height=400 * len(active_data),  # Ajustement dynamique de la hauteur
#         showlegend=False,  # ❌ Suppression des légendes inutiles
#         legend_tracegroupgap=30
#     )

#     # Ajustement de la police globale pour une meilleure lisibilité
#     fig_lca.update_xaxes(tickfont=dict(size=8))

#     # Affichage du graphique
#     fig_lca.show()



def display_all_lca_indicators(all_production_data, all_enviro_data, lines_config, production_totals, use_allocated_production=True):
    """
    Affiche les indicateurs LCA :
    - Échelle adaptative pour Production et Usage.
    - Échelle fixe pour la LCA combinée avec superposition des barres (Usage en bas, Production au-dessus).
    - Affichage des valeurs à l'intérieur des barres pour tous les graphiques.
    
    :param all_production_data: Liste des données de production par ligne.
    :param all_enviro_data: Liste des données environnementales.
    :param lines_config: Configuration des lignes de production.
    :param production_totals: Dictionnaire des productions réelles après allocation.
    :param use_allocated_production: Booléen, si True utilise la production réelle, sinon utilise la production simulée.
    """

    # 🔍 Filtrage des lignes actives
    active_data = [
        (prod_data, enviro_data, config)
        for prod_data, enviro_data, config in zip(all_production_data, all_enviro_data, lines_config)
        if production_totals.get(config['location'], 0) > 0
    ]

    if not active_data:
        print("⚠️ Aucune ligne active, pas d'affichage des indicateurs LCA.")
        return

    # 🔥 Debugging: Afficher les lignes incluses
    for _, _, line_config in active_data:
        print(f"✅ {line_config['location']} inclus dans l'affichage des LCA.")

    # 🔹 Définir les titres des colonnes
    column_titles = ["Production LCA", "Usage LCA", "Combined LCA"]

    # 🔹 Créer les sous-graphes
    fig_lca = make_subplots(
        rows=len(active_data), cols=3,
        column_titles=column_titles,
        horizontal_spacing=0.1,
        vertical_spacing=0.1
    )

    # Calcul de la valeur maximale pour les graphiques combinés
    max_value_global_combined = 0
    for production_data, _, line_config in active_data:
        location = line_config['location']
        total_seats_made = production_totals.get(location, 0) if use_allocated_production else production_data['Total Seats made'][1][-1]

        for site, total_seats_made in production_totals.items():
            production_lca = environment_engine.calculate_lca_indicators_pers_eq(total_seats_made, site)
            usage_lca = environment_engine.calculate_lca_indicators_usage_phase(total_seats_made, seat_weight=120)
            combined_lca = {key: production_lca[key] + usage_lca[key] for key in production_lca.keys()}

        max_value_line_combined = max(combined_lca.values())
        max_value_global_combined = max(max_value_global_combined, max_value_line_combined)

    # Boucle sur chaque ligne active
    for i, (production_data, enviro_data, line_config) in enumerate(active_data):
        location = line_config['location']
        total_seats_made = production_totals.get(location, 0) if use_allocated_production else production_data['Total Seats made'][1][-1]

        print(f"🔍 Vérification LCA pour {location} (mode {'alloué' if use_allocated_production else 'simulé'}):")
        print(f"➡ Production utilisée : {total_seats_made}")

        # 🔹 Calcul des indicateurs LCA
        production_lca = environment_engine.calculate_lca_indicators_pers_eq(total_seats_made, site)
        usage_lca = environment_engine.calculate_lca_indicators_usage_phase(total_seats_made, seat_weight=120)
        combined_lca = {key: production_lca[key] + usage_lca[key] for key in production_lca.keys()}

        # 🔹 Graphique Production LCA avec échelle adaptative
        fig_lca.add_trace(
            go.Bar(
                x=list(production_lca.keys()),
                y=list(production_lca.values()),
                text=[f"{v:.2f}" for v in production_lca.values()],
                textposition='inside',
                marker_color='blue',
                name='Production'
            ),
            row=i + 1, col=1
        )

        # 🔹 Graphique Usage LCA avec échelle adaptative
        fig_lca.add_trace(
            go.Bar(
                x=list(usage_lca.keys()),
                y=list(usage_lca.values()),
                text=[f"{v:.2f}" for v in usage_lca.values()],
                textposition='inside',
                marker_color='orange',
                name='Usage'
            ),
            row=i + 1, col=2
        )

        # 🔹 Graphique combiné avec superposition et affichage des valeurs
        fig_lca.add_trace(
            go.Bar(
                x=list(usage_lca.keys()),
                y=list(usage_lca.values()),
                text=[f"{v:.2f}" for v in usage_lca.values()],
                textposition='inside',
                marker_color='orange',
                name='Usage'
            ),
            row=i + 1, col=3
        )
        fig_lca.add_trace(
            go.Bar(
                x=list(production_lca.keys()),
                y=list(production_lca.values()),
                text=[f"{v:.2f}" for v in production_lca.values()],
                textposition='inside',
                marker_color='blue',
                name='Production'
            ),
            row=i + 1, col=3
        )

        # 🔹 Échelle fixe pour les graphiques combinés uniquement
        fig_lca.update_yaxes(range=[0, max_value_global_combined], row=i + 1, col=3)

        # 🔹 Ajouter la localisation dans l'axe Y
        for col in range(1, 4):
            fig_lca.update_yaxes(title_text=f"LCA Value ({location})", row=i + 1, col=col)

    # 🔹 Mise à jour du layout
    fig_lca.update_layout(
        title="LCA Indicators for Active Production Lines",
        height=400 * len(active_data),
        barmode='stack',  # Mode superposition pour les graphiques combinés
        showlegend=False,
    )

    # 🔹 Ajustement de la police
    fig_lca.update_xaxes(tickfont=dict(size=8))

    # 🔹 Affichage final
    fig_lca.show()




def display_all_stock_variations(all_production_data, lines_config):
        """
        Display all stock level variations for all production lines with separate legend groups.

        :param all_production_data: List of production data for all lines.
        :param lines_config: Configuration for all production lines.
        """
        # Create subplot titles
        subplot_titles = [f"Ligne {i + 1} - Stock Levels ({lines_config[i]['location']})" for i in range(len(all_production_data))]
        fig_stock = make_subplots(
            rows=len(all_production_data), cols=1,
            subplot_titles=subplot_titles,
            vertical_spacing=0.1
        )

        for i, production_data in enumerate(all_production_data):
            legend_group = str(i + 1)  # Create a unique legend group for each subplot
            for label, (time_vector, values) in production_data.items():
                # Add trace for stock level
                fig_stock.add_trace(
                    go.Scatter(
                        x=list(time_vector),
                        y=values,
                        mode='lines+markers',
                        name=f"{label} ({lines_config[i]['location']})",
                        legendgroup=legend_group  # Assign traces to a specific legend group
                    ),
                    row=i + 1, col=1
                )

        # Update layout to include legend trace group gap
        fig_stock.update_layout(
            title="All Stock Level Variations",
            height=400 * len(all_production_data),  # Adjust height dynamically
            showlegend=True,
            legend_tracegroupgap= 400 * len(all_production_data)* 0.18  # Add space between legend groups
        )

        # Update axis labels
        fig_stock.update_xaxes(title_text="Time (Steps)")
        fig_stock.update_yaxes(title_text="Stock Level")

        # Show the plot
        fig_stock.show()
