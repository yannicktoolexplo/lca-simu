import numpy as np
from scipy.integrate import odeint
import matplotlib.pyplot as plt

# Fonction modèle avec recyclage
def model_with_recycling(y, t):
    WIP_init, WIP_cut, WIP_drill, WIP_assy, Recycled_materials = y
    production_rate = 25 if WIP_drill <= 1000 else 0
    recycling_rate = 0.1 * WIP_assy  # 10% du WIP d'assemblage est recyclé
    reuse_rate = 0.8 * Recycled_materials  # 80% des matériaux recyclés sont réutilisés

    dWIP_init_dt = -production_rate + reuse_rate
    dWIP_cut_dt = production_rate - WIP_cut + reuse_rate
    dWIP_drill_dt = WIP_cut - WIP_drill
    dWIP_assy_dt = WIP_drill - WIP_assy - recycling_rate
    dRecycled_materials_dt = recycling_rate - reuse_rate

    return [dWIP_init_dt, dWIP_cut_dt, dWIP_drill_dt, dWIP_assy_dt, dRecycled_materials_dt]

# Fonction modèle sans recyclage
def model_without_recycling(y, t):
    WIP_init, WIP_cut, WIP_drill, WIP_assy = y
    production_rate = 25 if WIP_drill <= 1000 else 0

    dWIP_init_dt = -production_rate
    dWIP_cut_dt = production_rate - WIP_cut
    dWIP_drill_dt = WIP_cut - WIP_drill
    dWIP_assy_dt = WIP_drill - WIP_assy

    return [dWIP_init_dt, dWIP_cut_dt, dWIP_drill_dt, dWIP_assy_dt]

# Conditions initiales
initial_conditions_recycling = [1000, 100, 50, 25, 0]  # Avec matériaux recyclés
initial_conditions_no_recycling = [1000, 100, 50, 25]  # Sans matériaux recyclés
time = np.linspace(0, 50, 500)  # Simulation sur 50 unités de temps

# Résolution des équations différentielles
solution_with_recycling = odeint(model_with_recycling, initial_conditions_recycling, time)
solution_without_recycling = odeint(model_without_recycling, initial_conditions_no_recycling, time)

# Affichage des résultats
plt.figure(figsize=(12, 8))

# Avec recyclage
plt.plot(time, solution_with_recycling[:, 0], 'b-', label='WIP Initial (avec recyclage)')
plt.plot(time, solution_with_recycling[:, 1], 'r-', label='WIP Cutting (avec recyclage)')
plt.plot(time, solution_with_recycling[:, 2], 'g-', label='WIP Drilling (avec recyclage)')
plt.plot(time, solution_with_recycling[:, 3], 'c-', label='WIP Assembly (avec recyclage)')
plt.plot(time, solution_with_recycling[:, 4], 'm-', label='Recycled Materials')

# Sans recyclage
plt.plot(time, solution_without_recycling[:, 0], 'b--', label='WIP Initial (sans recyclage)')
plt.plot(time, solution_without_recycling[:, 1], 'r--', label='WIP Cutting (sans recyclage)')
plt.plot(time, solution_without_recycling[:, 2], 'g--', label='WIP Drilling (sans recyclage)')
plt.plot(time, solution_without_recycling[:, 3], 'c--', label='WIP Assembly (sans recyclage)')

plt.title("Impact du Recyclage sur la Production")
plt.xlabel("Temps")
plt.ylabel("Quantité")
plt.legend()
plt.grid(True)
plt.show()
