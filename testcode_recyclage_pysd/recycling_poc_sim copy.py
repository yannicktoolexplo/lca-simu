import pysd
import matplotlib.pyplot as plt
import pandas as pd

# Charger le modèle PySD
model = pysd.load('recycling_poc_model_copy.py')

# Exécuter le modèle
results = model.run()

# Afficher les colonnes et les premières lignes des résultats pour inspecter la structure
print(results.columns)
print(results.head())


# Enregistrer les résultats dans un fichier CSV
results.to_csv('recycling_poc_copy_results.csv')


# Charger le fichier CSV
file_path = './recycling_poc_copy_results.csv'
df = pd.read_csv(file_path)

# Afficher les premières lignes du DataFrame pour vérifier la structure
print(df.head())

# Tracer les données
plt.figure(figsize=(16, 12))

# Tracer Raw Material Stock
plt.subplot(4, 2, 1)
plt.plot(df['time'], df['Raw Material Stock'], label='Raw Material Stock')
plt.xlabel('Time')
plt.ylabel('Raw Material Stock (kg)')
plt.legend()
plt.grid(True)

# Tracer Recycled Material Stock
plt.subplot(4, 2, 2)
plt.plot(df['time'], df['Recycled Material Stock'], label='Recycled Material Stock', color='orange')
plt.xlabel('Time')
plt.ylabel('Recycled Material Stock (kg)')
plt.legend()
plt.grid(True)

# Tracer Waste Stock
plt.subplot(4, 2, 3)
plt.plot(df['time'], df['Waste Stock'], label='Waste Stock', color='red')
plt.xlabel('Time')
plt.ylabel('Waste Stock (kg)')
plt.legend()
plt.grid(True)

# Tracer Total CO2 Emissions
plt.subplot(4, 2, 4)
plt.plot(df['time'], df['Total CO2 Emissions'], label='Total CO2 Emissions', color='green')
plt.xlabel('Time')
plt.ylabel('Total CO2 Emissions (kg CO2)')
plt.legend()
plt.grid(True)

# # Tracer Optimized Production Rate
# plt.subplot(4, 2, 5)
# plt.plot(df['time'], df['Optimized Production Rate'], label='Optimized Production Rate', color='blue')
# plt.xlabel('Time')
# plt.ylabel('Optimized Production Rate (kg/month)')
# plt.legend()
# plt.grid(True)

# # Tracer Optimized Recycling Rate
# plt.subplot(4, 2, 6)
# plt.plot(df['time'], df['Optimized Recycling Rate'], label='Optimized Recycling Rate', color='purple')
# plt.xlabel('Time')
# plt.ylabel('Optimized Recycling Rate')
# plt.legend()
# plt.grid(True)

# Tracer Total Cost
plt.subplot(4, 2, 5)
plt.plot(df['time'], df['Total Cost'], label='Total Cost', color='brown')
plt.xlabel('Time')
plt.ylabel('Total Cost ($)')
plt.legend()
plt.grid(True)

# # Tracer Total Profit
# plt.subplot(4, 2, 8)
# plt.plot(df['time'], df['Total Profit'], label='Total Profit', color='cyan')
# plt.xlabel('Time')
# plt.ylabel('Total Profit ($)')
# plt.legend()
# plt.grid(True)

plt.tight_layout()
plt.show()