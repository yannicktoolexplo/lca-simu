import numpy as np
import matplotlib.pyplot as plt

# Définir les paramètres initiaux
S_initial = 1200  # Niveau de stock initial et valeur cible
S_target = 1200   # Niveau de stock cible
stock_securite = 200  # Niveau de stock de sécurité
perturbation_frequency = 50  # Fréquence des perturbations (en jours)
demande_moyenne = 50  # Demande moyenne par jour
periode = 200  # Période de simulation (jours) augmentée pour observer les effets à long terme
delai_reapprovisionnement = 2  # Délai en jours

# Scénarios de perturbations plus réalistes
perturbation_amplitudes = [800, 700, 900, 1000, 500]  # Variabilité plus importante
number_of_cycles = 5  # Nombre de cycles de perturbations

perturbation_points = []
current_t_min = 10
for cycle in range(number_of_cycles):
    current_t_95 = current_t_min + np.random.randint(3, 10)  # Durée aléatoire de perturbation
    S_min = S_initial - perturbation_amplitudes[cycle]  # Impact de la perturbation
    perturbation_points.append((current_t_min, current_t_95, S_min))
    current_t_min += perturbation_frequency + np.random.randint(-5, 5)  # Intervalle aléatoire entre perturbations

# Simulation du stock non régulé
stock_non_regulated = S_initial
stock_history_non_regulated = []

for jour in range(periode):
    demande = demande_moyenne + np.random.randint(-10, 10)

    for (t_min, t_95, S_min) in perturbation_points:
        if t_min <= jour <= t_95:
            stock_non_regulated = S_min  # Chute du stock lors d'une perturbation

    stock_non_regulated -= demande
    stock_non_regulated = max(stock_non_regulated, stock_securite)  # Stock de sécurité

    stock_history_non_regulated.append(stock_non_regulated)

# Simulation du stock régulé (PID)
Kp, Ki_base, Kd = 0.8, 0.1, 0.01
limite_commande_max = 500
stock_regulated = S_initial
stock_history_regulated = []
erreur_integrale, erreur_precedente = 0, 0

for jour in range(periode):
    demande = demande_moyenne + np.random.randint(-10, 10)

    for (t_min, t_95, S_min) in perturbation_points:
        if t_min <= jour <= t_95:
            stock_regulated = S_min
            S_target = S_min
            erreur_integrale = 0  # Réinitialisation de l'erreur

    erreur = S_target - stock_regulated

    if abs(erreur) > 200:
        Ki = Ki_base * 2
    else:
        Ki = Ki_base

    if abs(erreur_integrale * Ki) < limite_commande_max:
        erreur_integrale += erreur

    correction_P = Kp * erreur
    correction_I = Ki * erreur_integrale
    correction_D = Kd * (erreur - erreur_precedente)

    commande = max(min(correction_P + correction_I + correction_D, limite_commande_max), 0)
    stock_regulated += commande - demande
    stock_regulated = max(stock_regulated, stock_securite)  # Stock de sécurité

    stock_history_regulated.append(stock_regulated)
    erreur_precedente = erreur

# Affichage des résultats
plt.figure(figsize=(12, 8))
plt.plot(stock_history_non_regulated, label="Stock Non Régulé", color='blue')
plt.plot(stock_history_regulated, label="Stock Régulé (PID)", color='red', linestyle='--')
plt.xlabel("Temps (jours)")
plt.ylabel("Niveau de Stock")
plt.title("Comparaison entre Système Régulé (PID) et Non Régulé avec Scénarios Réalistes")
plt.legend()
plt.grid(True)
plt.show()

# Calcul des coûts et de la résilience
cost_non_regulated = np.trapz(stock_history_non_regulated, dx=1)
cost_regulated = np.trapz(stock_history_regulated, dx=1)

resilience_non_regulated = np.trapz([abs(S_initial - s) for s in stock_history_non_regulated], dx=1)
resilience_regulated = np.trapz([abs(S_initial - s) for s in stock_history_regulated], dx=1)

cost_non_regulated, cost_regulated, resilience_non_regulated, resilience_regulated
