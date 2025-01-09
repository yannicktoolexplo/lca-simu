import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math

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
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=["Stock Levels Over Time", "Total Seats Made Over Time"])

    for label, (time_vector, values) in stock_data.items():
        fig.add_trace(go.Scatter(x=time_vector, y=values, mode='lines+markers', name=label), row=1, col=1)

    fig.add_trace(go.Scatter(x=total_seats_data[0], y=total_seats_data[1], mode='lines+markers', name='Total Seats made'), row=2, col=1)

    fig.update_layout(height=800, title_text="Stock Levels and Total Seats Made Over Time", showlegend=True)
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Stock Level", row=1, col=1)
    fig.update_yaxes(title_text="Total Seats Made", row=2, col=1)

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