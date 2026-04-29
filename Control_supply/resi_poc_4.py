# Importation des bibliothèques nécessaires
import numpy as np
import matplotlib.pyplot as plt

# **1️⃣ Paramètres de simulation**
N = 100  # Nombre de jours
D_0, S_0, N_s0, P_0 = 10, 95, 500, 100  # Références des indicateurs opérationnels
C_0, M_0, T_0 = 100, 30, 10  # Références des indicateurs économiques (Coût total, Marge, Transport)
E_0, R_0 = 50, 40  # Références des indicateurs environnementaux (Émissions CO2, Matériaux recyclés)

# **2️⃣ Définition des indicateurs et corrections pour la résilience opérationnelle**
D_corrected = np.ones(N) * D_0  
S_corrected = np.ones(N) * S_0  
N_s_corrected = np.ones(N) * N_s0  
P_corrected = np.ones(N) * P_0  

# **3️⃣ Définition des indicateurs et corrections pour la résilience économique**
C_corrected = np.ones(N) * C_0  
M_corrected = np.ones(N) * M_0  
T_corrected = np.ones(N) * T_0  

# **4️⃣ Définition des indicateurs et corrections pour la résilience environnementale**
E_corrected = np.ones(N) * E_0  
R_corrected = np.ones(N) * R_0  

# **5️⃣ Simulation de la perturbation au temps t=20**
for t in range(20, N):
    if t < 30:  # Période de crise
        # Résilience Opérationnelle
        D_corrected[t] = min(D_0 * 1.5, D_corrected[t-1] + np.random.normal(1, 0.5))  
        S_corrected[t] = max(S_0 * 0.7, S_corrected[t-1] - np.random.normal(3, 1))  
        N_s_corrected[t] = max(N_s0 * 0.5, N_s_corrected[t-1] - np.random.normal(25, 5))  
        P_corrected[t] = max(P_0 * 0.6, P_corrected[t-1] - np.random.normal(8, 2))  

        # Résilience Économique
        C_corrected[t] = max(C_0 * 1.3, C_corrected[t-1] + np.random.normal(2, 1))  
        M_corrected[t] = max(M_0 * 0.7, M_corrected[t-1] - np.random.normal(1, 0.5))  
        T_corrected[t] = max(T_0 * 1.4, T_corrected[t-1] + np.random.normal(1, 0.3))  

        # Résilience Environnementale
        E_corrected[t] = max(E_0 * 1.2, E_corrected[t-1] + np.random.normal(2, 1))  
        R_corrected[t] = max(R_0 * 0.6, R_corrected[t-1] - np.random.normal(2, 1))  

# **6️⃣ Ajout de points de retour à la normale différents**
np.random.seed(42)  # Assurer la reproductibilité
retour_normal_op = np.random.randint(40, 60)  # Opérationnel
retour_normal_eco = np.random.randint(40, 60)  # Économique
retour_normal_env = np.random.randint(40, 60)  # Environnemental

# **7️⃣ Application du retour à la normale variable**
for t in range(30, N):  
    if t <= retour_normal_op:  # Récupération opérationnelle
        D_corrected[t] = D_corrected[t-1] - (D_corrected[t-1] - D_0) / (retour_normal_op - t + 1)
        S_corrected[t] = S_corrected[t-1] + (S_0 - S_corrected[t-1]) / (retour_normal_op - t + 1)
        N_s_corrected[t] = N_s_corrected[t-1] + (N_s0 - N_s_corrected[t-1]) / (retour_normal_op - t + 1)
        P_corrected[t] = P_corrected[t-1] + (P_0 - P_corrected[t-1]) / (retour_normal_op - t + 1)

    if t <= retour_normal_eco:  # Récupération économique
        C_corrected[t] = C_corrected[t-1] - (C_corrected[t-1] - C_0) / (retour_normal_eco - t + 1)
        M_corrected[t] = M_corrected[t-1] + (M_0 - M_corrected[t-1]) / (retour_normal_eco - t + 1)
        T_corrected[t] = T_corrected[t-1] - (T_corrected[t-1] - T_0) / (retour_normal_eco - t + 1)

    if t <= retour_normal_env:  # Récupération environnementale
        E_corrected[t] = E_corrected[t-1] - (E_corrected[t-1] - E_0) / (retour_normal_env - t + 1)
        R_corrected[t] = R_corrected[t-1] + (R_0 - R_corrected[t-1]) / (retour_normal_env - t + 1)

# **8️⃣ Affichage des indicateurs avec retours variables**
plt.figure(figsize=(12, 12))

# Indicateurs Opérationnels
plt.subplot(3, 1, 1)
plt.plot(D_corrected, label="Délai de Livraison", color='red')
plt.plot(S_corrected, label="Taux de Service", color='blue')
plt.plot(N_s_corrected, label="Stock Disponible", color='green')
plt.plot(P_corrected, label="Production", color='orange')
plt.axvline(x=20, color='black', linestyle="dotted", label="Perturbation")
plt.axvline(x=retour_normal_op, color='black', linestyle="dashdot", label="Retour Opérationnel")
plt.legend()
plt.title("Évolution des Indicateurs Opérationnels avec Retours Variables")

# Indicateurs Économiques
plt.subplot(3, 1, 2)
plt.plot(C_corrected, label="Coût Total", color='red')
plt.plot(M_corrected, label="Marge Bénéficiaire", color='purple')
plt.plot(T_corrected, label="Coût Transport", color='brown')
plt.axvline(x=20, color='black', linestyle="dotted")
plt.axvline(x=retour_normal_eco, color='black', linestyle="dashdot", label="Retour Économique")
plt.legend()
plt.title("Évolution des Indicateurs Économiques avec Retours Variables")

# Indicateurs Environnementaux
plt.subplot(3, 1, 3)
plt.plot(E_corrected, label="Émissions CO₂", color='gray')
plt.plot(R_corrected, label="Matériaux Recyclés", color='green')
plt.axvline(x=20, color='black', linestyle="dotted")
plt.axvline(x=retour_normal_env, color='black', linestyle="dashdot", label="Retour Environnemental")
plt.legend()
plt.title("Évolution des Indicateurs Environnementaux avec Retours Variables")

plt.tight_layout()
plt.show()

# **Affichage des points de retour à la normale choisis**
print(f"Retour à la normale Opérationnel : {retour_normal_op} jours")
print(f"Retour à la normale Économique : {retour_normal_eco} jours")
print(f"Retour à la normale Environnemental : {retour_normal_env} jours")


# **9️⃣ Calcul du Triangle de Résilience**
def calcul_triangle_resilience(valeurs, t_perturbation, t_recup):
    """
    Calcule la résilience selon le triangle de résilience :
    - Valeur minimale atteinte après la perturbation.
    - Temps nécessaire pour retrouver 90% de la valeur initiale.
    - Aire sous la courbe de récupération.
    """
    valeur_min = np.min(valeurs[t_perturbation:])  # Point le plus bas après perturbation
    index_min = np.argmin(valeurs[t_perturbation:]) + t_perturbation  # Index du point bas

    # Définir le seuil de récupération (90% de la valeur initiale)
    seuil_recuperation = valeurs[0] * 0.9
    temps_recup = np.where(valeurs[index_min:t_recup] >= seuil_recuperation)[0]
    temps_recup = temps_recup[0] + index_min if len(temps_recup) > 0 else t_recup

    # Calcul de l'aire sous la courbe de récupération
    aire = np.trapz(np.abs(valeurs[t_perturbation:temps_recup] - valeurs[0]), dx=1)

    return valeur_min, temps_recup - index_min, aire

# **Calcul de la résilience pour chaque dimension**
resilience_op = calcul_triangle_resilience(N_s_corrected, 20, retour_normal_op)
resilience_eco = calcul_triangle_resilience(M_corrected, 20, retour_normal_eco)
resilience_env = calcul_triangle_resilience(R_corrected, 20, retour_normal_env)

# **Affichage des résultats**
print(f"Résilience Opérationnelle : Valeur Min: {resilience_op[0]:.2f}, Temps de Récup: {resilience_op[1]} jours, Aire: {resilience_op[2]:.2f}")
print(f"Résilience Économique : Valeur Min: {resilience_eco[0]:.2f}, Temps de Récup: {resilience_eco[1]} jours, Aire: {resilience_eco[2]:.2f}")
print(f"Résilience Environnementale : Valeur Min: {resilience_env[0]:.2f}, Temps de Récup: {resilience_env[1]} jours, Aire: {resilience_env[2]:.2f}")

# **Affichage graphique de la récupération et du triangle de résilience**
plt.figure(figsize=(12, 6))

# Résilience Opérationnelle
plt.subplot(3, 1, 1)
plt.plot(N_s_corrected, label="Stock Disponible", color='green')
plt.axvline(x=20, color='black', linestyle="dotted", label="Perturbation")
plt.axvline(x=retour_normal_op, color='black', linestyle="dashdot", label="Retour Opérationnel")
plt.scatter(resilience_op[1] + 20, resilience_op[0], color="red", label="Valeur Min")
plt.legend()
plt.title("Triangle de Résilience Opérationnelle")

# Résilience Économique
plt.subplot(3, 1, 2)
plt.plot(M_corrected, label="Marge Bénéficiaire", color='purple')
plt.axvline(x=20, color='black', linestyle="dotted")
plt.axvline(x=retour_normal_eco, color='black', linestyle="dashdot", label="Retour Économique")
plt.scatter(resilience_eco[1] + 20, resilience_eco[0], color="red", label="Valeur Min")
plt.legend()
plt.title("Triangle de Résilience Économique")

# Résilience Environnementale
plt.subplot(3, 1, 3)
plt.plot(R_corrected, label="Matériaux Recyclés", color='blue')
plt.axvline(x=20, color='black', linestyle="dotted")
plt.axvline(x=retour_normal_env, color='black', linestyle="dashdot", label="Retour Environnemental")
plt.scatter(resilience_env[1] + 20, resilience_env[0], color="red", label="Valeur Min")
plt.legend()
plt.title("Triangle de Résilience Environnementale")

plt.tight_layout()
plt.show()

