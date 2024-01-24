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
import line_production
import random
random.seed(1447)

def run_supply_chain_optimization():
    absolute_path = os.path.dirname(__file__)

    # ## Plant Location  

    # #### Manufacturing variable costs

    # Import Costs
    manvar_costs = pd.read_excel(os.path.join(absolute_path,'data/variable_costs.xlsx'), index_col = 0)


    # #### Freight costs

    # Import Costs
    freight_costs = pd.read_excel(os.path.join(absolute_path,'data/freight_costs.xlsx'), index_col = 0)


    # #### Variable Costs

    # +
    # Variable Costs
    var_cost = freight_costs/1000 + manvar_costs 


    # #### Fixed Costs

    # Import Costs
    fixed_costs = pd.read_excel(os.path.join(absolute_path,'data/fixed_cost.xlsx'), index_col = 0)
 

    # #### Plants Capacity

    # Two types of plants: Low Capacity and High Capacity Plant
    file_path = os.path.join(absolute_path, 'data/capacity.xlsx')
    cap = pd.read_excel(file_path, index_col = 0)
    data = line_production.get_data()
    nos_texas_low = 0.6 * data['Total Seats made'][1][-1]
    nos_texas_high = 1.2 * data['Total Seats made'][1][-1]
    nos_california_low = 0.3 * data['Total Seats made'][1][-1]
    nos_california_high = 0.6 * data['Total Seats made'][1][-1]
    nos_UK_low = 0.15 * data['Total Seats made'][1][-1]
    nos_UK_high = 0.3 * data['Total Seats made'][1][-1]
    nos_france_low = 0.45 * data['Total Seats made'][1][-1]
    nos_france_high = 0.9 * data['Total Seats made'][1][-1]
    cap.iloc[0, 0] = nos_texas_low
    cap.iloc[0, 1] = nos_texas_high
    cap.iloc[1, 0] = nos_california_low
    cap.iloc[1, 1] = nos_california_high
    cap.iloc[2, 0] = nos_UK_low
    cap.iloc[2, 1] = nos_UK_high
    cap.iloc[3, 0] = nos_france_low
    cap.iloc[3, 1] = nos_france_high

    # Save the modified DataFrame back to the Excel file
    cap.to_excel(file_path)
    # cap = pd.read_excel(file_path, index_col = 0)

    # #### Demand 

    # -- Demand
    demand = pd.read_excel(os.path.join(absolute_path,'data/demand.xlsx'), index_col = 0)
   

    # +
    # Define Decision Variables
    loc_prod = ['Texas', 'California', 'UK', 'France']
    loc_demand = ['USA', 'Canada', 'Japan', 'Brazil', 'France']
    size = ['Low', 'High']

    # Initialize Class
    model = LpProblem("Capacitated Plant Location Model", LpMinimize)


    # Create Decision Variables
    x = LpVariable.dicts("production_", [(i,j) for i in loc_prod for j in loc_demand],
        lowBound=0, upBound=None, cat='continuous')
    y = LpVariable.dicts("plant_", 
        [(i,s) for s in size for i in loc_prod], cat='Binary')

    # Define Objective Function
    model += (lpSum([fixed_costs.loc[i,s] * y[(i,s)] for s in size for i in loc_prod])
    + lpSum([var_cost.loc[i,j] * x[(i,j)]   for i in loc_prod for j in loc_demand]))

    # Add Constraints
    for j in loc_demand:
        model += lpSum([x[(i, j)] for i in loc_prod]) == demand.loc[j,'Demand']
    for i in loc_prod:
        model += lpSum([x[(i, j)] for j in loc_demand]) <= lpSum([cap.loc[i,s]*y[(i,s)] 
                                        for s in size])


    # Define logical constraint: Add a logical constraint so that if the high capacity plant in USA is open, then a low capacity plant in Germany is also opened.
    # model += y[('USA','High_Cap')] <= y[('Germany','Low_Cap')]                                                       
                                        
    # Solve Model
    model.solve()
    print("Total Costs = {:,} ($/Month)".format(int(utilities.value(model.objective))))
    print("---------")  
    print('\n' + "Status: {}".format(LpStatus[model.status]))


    # Dictionnary
    dict_plant = {}
    dict_prod = {}
    for v in model.variables():
        if 'plant' in v.name:
            name = v.name.replace('plant__', '').replace('_', '')
            dict_plant[name] = int(v.varValue)
            p_name = name
        else:
            name = v.name.replace('production__', '').replace('_', '')
            dict_prod[name] = v.varValue
            # print(name, "=", v.varValue)

    # print(dict_prod)

    # Filtrer pour garder uniquement les flux non nuls
    non_zero_flux = {k: v for k, v in dict_prod.items() if v > 0}

    # Nettoyer et transformer les clés
    transformed_flux = {}
    for key, value in non_zero_flux.items():
        # Enlever les caractères superflus des chaînes
        clean_key = key.replace("('", "").replace("')", "").replace("'", "")
        src, tgt = clean_key.split(',')
        transformed_flux[(src.strip(), tgt.strip())] = value

    # Création des listes pour le diagramme de Sankey
    source = []
    target = []
    value = []

    for (src, tgt), val in transformed_flux.items():
        source.append(loc_prod.index(src))
        target.append(loc_demand.index(tgt))
        value.append(val)

    # print(source)
    # print(target)
    # print(value)

    # Calculate total units for each production and market node
    production_totals = {location: 0 for location in loc_prod}
    market_totals = {location: 0 for location in loc_demand}

    for s, t, v in zip(source, target, value):
        production_totals[loc_prod[s]] += v
        market_totals[loc_demand[t]] += v  # Adjust target index for market nodes % len(loc_prod)

    # Update node labels to include total units
    node_labels = [f"{loc_prod[i]} Production\n({production_totals[loc_prod[i]]} Units)" for i in range(len(loc_prod))]
    node_labels += [f"{loc_demand[i]} Market\n({market_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

    # Les labels des liens pour les unités échangées
    link_labels = [f"{v:,.0f} Units" for v in value]

    # Define the base colors for production nodes
    base_colors = {
    'Texas': 'rgba(255, 127, 14, 0.8)',      # Orange
    'California': 'rgba(255, 127, 14, 0.8)',  # Orange
    'UK': 'rgba(148, 103, 189, 0.8)',     # Purple
    'France': 'rgba(214, 39, 40, 0.8)',    # Red
    }

    # Define the colors for market nodes (can be the same or different)
    # Use the base colors for production nodes and create lighter versions for market nodes
    production_colors = [base_colors[place] for place in loc_prod]
    target_colors = {
    'USA': 'rgba(255, 127, 14, 0.5)',      # Orange
    'Canada': 'rgba(255, 215, 0, 0.5)',  # Yellow
    'Japan': 'rgba(44, 160, 44, 0.5)',     # Green
    'Brazil': 'rgba(31, 119, 180, 0.5)',    # Blue
    'France': 'rgba(214, 39, 40, 0.5)'    # red
    }
    market_colors = [target_colors[place] for place in loc_demand]

    # Combine the colors for all nodes
    node_colors = production_colors + market_colors  # Concatenate the color lists

    # Use the market colors for links
    link_colors = [market_colors[i] for i in target]

    # Create the Sankey diagram
    fig= go.Figure(data=[go.Sankey(
    node=dict(
    pad=15,
    thickness=20,
    line=dict(color="black", width=0.5),
    label=node_labels,
    color=node_colors  # Use the combined list of colors for nodes
    ),
    link=dict(
    source=source,
    target=[i + len(loc_prod) for i in target],  # Adjust the indices for market nodes
    value=value,
    label=link_labels,
    color=link_colors  # Use the production colors for links
    ))])

    distances_to_paris = {
    'Canada': 6000,   # by air
    'France': 1000,    # by road
    'USA': 6000,      # by air
    'Brazil': 7000,   # by air
    'Japan': 10000    # by air
    }

    # CO2 emission factors (in kg CO2 per ton-km)
    co2_factors = {
        'road': 0.096,
        'train': 0.028,
        'air': 2.1
    }

    # Function to calculate CO2 emissions for each country
    def calculate_co2_emissions(country, amount):
        mode = 'air'  # Default mode
        if country == 'France':
            mode = 'road'
        # Calculate distance
        distance = distances_to_paris.get(country, 0)
        # Calculate CO2 emissions
        return amount * distance * co2_factors[mode] / 1000  # Convert to tonnes

    # Calculate CO2 emissions for each link
    co2_emissions = [calculate_co2_emissions(loc_demand[s], value[i]) for i, s in enumerate(source)]
    # print(co2_emissions)

    production_co2_factors = {
    'Texas': 3.5,        # Example values
    'California': 3,
    'UK': 3,
    'France': 2
    }
    # Function to calculate CO2 emissions for production in each country
    def calculate_production_co2_emissions(country, amount):
        co2_factor = production_co2_factors.get(country, 0)
        return amount * co2_factor

    # Assuming 'value' represents the quantity produced
    production_co2_emissions = [calculate_production_co2_emissions(loc_prod[s], value[i]) for i, s in enumerate(source)]

    # # Calculate total units for each production and market node
    production_co2_totals = {location: 0 for location in loc_prod}
    market2_totals = {location: 0 for location in loc_demand}

    for s, t, p, v in zip(source, target, production_co2_emissions, value):
        production_co2_totals[loc_prod[s]] += p
        market2_totals[loc_demand[t]] += v  # Adjust target index for market nodes % len(loc_demand)

    # # Update node labels to include total units
    node2_labels = [f"{loc_prod[i]} CO2 Emission\n({production_co2_totals[loc_prod[i]]} kg CO2)" for i in range(len(loc_prod))]
    node2_labels += [f"{loc_demand[i]} Market\n({market2_totals[loc_demand[i]]} Units)" for i in range(len(loc_demand))]

    # Update link_labels to include CO2 emissions
    link2_labels = [f"{c:,.2f} kg CO2" for c in co2_emissions]

    # Create the Sankey diagram with updated link labels
    fig2 = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node2_labels,
            color=node_colors
        ),
        link=dict(
            source=source,
            target=[i + len(loc_prod) for i in target],
            value=co2_emissions,
            label=link2_labels,
            color=link_colors
        ))])
    
    # # Generate the HTML representation of the figure
    # html_content = py_offline.plot(fig_opti, include_plotlyjs='cdn', output_type='div')

    # # Set up the Qt application and WebEngineView
    # app = QApplication(sys.argv)
    # main_window = QMainWindow()
    # web_engine_view = QWebEngineView()

    # # Load the HTML content in the web view
    # web_engine_view.setHtml(html_content)
    # main_window.setCentralWidget(web_engine_view)
    # main_window.resize(1200, 900)  # Adjust the size as needed
    # main_window.show()
    # exit_code = app.exec_()

    # # Clean up
    # web_engine_view.deleteLater()
    # main_window.deleteLater()
    # sys.exit(exit_code)


    return fig, fig2, value, cap