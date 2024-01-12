import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import math

def plot_surface(absolute_path):
    surface_data = pd.read_csv(os.path.join(absolute_path, 'output/shaft.csv'))
    surface_data['station_id'] = pd.to_numeric(surface_data['station_id'], errors='coerce').astype('Int64')
    surface_data['surface'] = pd.to_numeric(surface_data['surface'], errors='coerce').astype(float)
    surface_data['time'] = pd.to_numeric(surface_data['time'], errors='coerce').astype('Int64')

    labels = ['drill', 'lathe', 'polisher']
    
    for index, label in enumerate(labels):
        plt.plot(surface_data[surface_data['station_id'] == index]['time'],
                 surface_data[surface_data['station_id'] == index]['surface'], label=label)
    
    plt.xlabel('Sim. time')
    plt.ylabel('Surface roughness')
    plt.title('Surface over simulated time')
    plt.legend(loc='upper right')
    plt.savefig(os.path.join(absolute_path, 'output/shaft_surface.png'))

def visualize_stock_levels(data, ytick_param):
    fig, ax = plt.subplots()

    for label, (time_vector, values) in data.items():
        plotting_of_data(ax, time_vector, values, ytick_param, label)

    plt.show()

def plotting_of_data(ax, time, data_entry, ysize, label_string):
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
    # Read the CSV file
    df = pd.read_csv(csv_file_path)
    
    # Calculate the sum of CO2 emissions for each transportation mode
    total_co2_road = df['CO2 Road'].sum()
    total_co2_rail = df['CO2 Rail'].sum()
    total_co2_sea = df['CO2 Sea'].sum()
    total_co2_air = df['CO2 Air'].sum()
    total_co2 = df['CO2 Total'].sum()
    
    # Data to plot
    modes = ['Road', 'Rail', 'Sea', 'Air', 'Total']
    emissions = [total_co2_road, total_co2_rail, total_co2_sea, total_co2_air, total_co2]
    
    # Create a bar diagram
    plt.figure(figsize=(10, 6))
    plt.bar(modes, emissions, color=['blue', 'orange', 'green', 'red', 'purple'])
    
    # Adding labels and title
    plt.xlabel('Transportation Mode')
    plt.ylabel('CO2 Emissions (kg CO2e)')
    plt.title('Total CO2 Emissions by Transportation Mode')
    
    # Display numeric labels on each bar
    for i, v in enumerate(emissions):
        plt.text(i, v + max(emissions) * 0.01, f"{v:.2f}", ha='center', va='bottom')
    
    # Show plot
    plt.tight_layout()
    plt.show()

#Round to nearest multiple of the power of 10
def round_to_nearest_significant(number):
    if number == 0:
        return 0
    power = 10 ** math.floor(math.log10(abs(number)))
    return power * 10 if number >= power * 5 else power