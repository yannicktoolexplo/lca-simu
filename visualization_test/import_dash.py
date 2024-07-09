import matplotlib.pyplot as plt
import numpy as np

def create_plot(categories, emissions, label, color=None):
    """
    Create a plot for each type of emissions
    """
    ax.plot(categories, emissions, marker='', label=label, color=color)
    ax.fill_between(categories, emissions, color=color)

# Data
categories = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
energy_emissions = np.array([30, 25, 20, 15, 10, 5, 0, 0, 0, 0, 0, 0])
transportation_emissions = np.array([0, 5, 15, 20, 25, 30, 25, 20, 15, 10, 5, 0])
waste_emissions = np.array([0, 0, 0, 5, 10, 15, 20, 25, 30, 30, 25, 15])

# Colors
energy_color = (1, 0.5, 0.5)
transportation_color = (0.5, 1, 0.5)
waste_color = (0.5, 0.5, 1)

# Create the figure and the subplot
fig, ax = plt.subplots()

# Set labels
fig.suptitle("Emissions over Time (MTCO2e)")
ax.set_ylabel("Emissions (MTCO2e)")
ax.set_xlabel("Months")

# Plot data
create_plot(categories, energy_emissions, 'Energy', energy_color)
create_plot(categories, transportation_emissions, 'Transportation', transportation_color)
create_plot(categories, waste_emissions, 'Waste', waste_color)

# Set legend
ax.legend()

# Show the plot
plt.show()