import pysd
import matplotlib.pyplot as plt
import pandas as pd

# Charger le modèle PySD
model = pysd.load('recycling_poc_model.py')

# Exécuter le modèle
results = model.run()

# Afficher les colonnes et les premières lignes des résultats pour inspecter la structure
print(results.columns)
print(results.head())

# Enregistrer les résultats dans un fichier CSV
results.to_csv('recycling_poc_sim_results.csv')

# Créer des sous-graphiques
fig, axs = plt.subplots(3, 1, figsize=(10, 15))

# Tracer les niveaux d'inventaire dans le temps
axs[0].plot(results.index, results['Inventory'], label='Inventory')
axs[0].set_xlabel('Time')
axs[0].set_ylabel('Inventory')
axs[0].legend()
axs[0].set_title('Inventory Levels Over Time')

# Tracer les matériaux recyclés dans le temps
axs[1].plot(results.index, results['Recycled Materials'], label='Recycled Materials')
axs[1].set_xlabel('Time')
axs[1].set_ylabel('Recycled Materials')
axs[1].legend()
axs[1].set_title('Recycled Materials Over Time')

# Ajuster la disposition
plt.tight_layout()

# Afficher les graphiques
plt.show()
