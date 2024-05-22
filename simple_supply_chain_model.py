import pysd
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Load the PySD model
model = pysd.load('ProductionLine.py')

# Run the model
results = model.run()

# Print the columns and first few rows of the results to inspect the structure
print(results.columns)
print(results.head())

# Save the results to a CSV file
results.to_csv('simulation_results.csv')

# Create subplots
fig, axs = plt.subplots(4, 1, figsize=(10, 20))

# Plot the inventory levels over time
for i in range(1, 8):
    axs[0].plot(results.index, results[f'Inventory {i}'], label=f'Workstation {i}')

axs[0].set_xlabel('Time')
axs[0].set_ylabel('Inventory')
axs[0].legend()
axs[0].set_title('Inventory Levels Over Time')

# Plot the processing times over time
processing_times = results[[f'Processing Time {i}' for i in range(1, 8)]]

for i in range(1, 8):
    axs[1].plot(results.index, processing_times[f'Processing Time {i}'], label=f'Workstation {i}')

axs[1].set_xlabel('Time')
axs[1].set_ylabel('Processing Time')
axs[1].legend()
axs[1].set_title('Processing Times Over Time')

# Plot the carbon emissions over time
for i in range(1, 8):
    axs[2].plot(results.index, results[f'Carbon Emissions {i}'], label=f'Workstation {i}')

axs[2].set_xlabel('Time')
axs[2].set_ylabel('Carbon Emissions (kg CO2)')
axs[2].legend()
axs[2].set_title('Carbon Emissions Over Time')

# Plot the carbon emissions from supply over time
axs[2].plot(results.index, results['Carbon Emissions Supply'], label='Carbon Emissions Supply')
# Plot the carbon emissions from supply over time
axs[2].plot(results.index, results['Carbon Emissions Supply with Recycling'], label='Carbon Emissions Supply with Recycling')

# Plot the recycled materials over time
axs[3].plot(results.index, results['Recycled Materials'], label='Recycled Materials')

axs[3].set_xlabel('Time')
axs[3].set_ylabel('Recycled Materials')
axs[3].legend()
axs[3].set_title('Recycled Materials Over Time')

# Adjust layout
plt.tight_layout()

# Show plots
plt.show()
