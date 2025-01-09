import numpy as np
import matplotlib.pyplot as plt

# Paramètres initiaux
S_initial = 500  # Niveau de stock initial
S_target = 500   # Niveau de stock cible (fixe)
stock_securite = 200  # Niveau de stock de sécurité
perturbation_frequency = 40  # Fréquence des perturbations (en jours)
demande_moyenne = 50  # Demande moyenne par jour (réduite)
periode = 200  # Période de simulation (jours)

# Paramètres optimisés du correcteur PID
Kp = 0.8  # Gain proportionnel, réduit pour limiter les oscillations
Ki_base = 0.1  # Gain intégral de base, réduit pour minimiser l'accumulation d'erreur
Kd = 0.01  # Gain dérivatif, augmenté pour améliorer l'amortissement

# Limite de commande
limite_commande_max = 800

# Simulation de la dynamique du stock pour le système régulé
stock_regulated = S_initial
stock_history_regulated = []
erreur_integrale = 0
erreur_precedente = 0

# Simulation de la dynamique du stock pour le système non régulé
stock_non_regulated = S_initial
stock_history_non_regulated = []
delai_reapprovisionnement = 2  # Délai entre chaque réapprovisionnement pour les systèmes
quantite_reapprovisionnement_non_regule = limite_commande_max  # Limite de la quantité de réapprovisionnement pour le système non régulé

# Perturbations sur la demande : inclut à la fois des chutes et des hausses
demande_perturbations = [
    (-20, 10),   # Chute de 20 pendant 10 jours
    (+30, 10),   # Hausse de 30 pendant 10 jours
    (-10, 15),   # Chute de 10 pendant 15 jours
    (+25, 15)    # Hausse de 25 pendant 15 jours
]
perturbation_points = []
current_t_min = 10
for amplitude, duree in demande_perturbations:
    current_t_95 = current_t_min + duree
    perturbation_points.append((current_t_min, current_t_95, amplitude))
    current_t_min += perturbation_frequency

# Historique de la demande
demande_history = []

# Boucle de simulation pour chaque jour de la période
for jour in range(periode):
    # Demande par défaut
    demande = demande_moyenne

    # Détecter si une perturbation est en cours sur la demande
    for (t_min, t_95, delta_demande) in perturbation_points:
        if t_min <= jour <= t_95:
            demande += delta_demande  # Modification de la demande (hausse ou baisse) pendant la perturbation

    # Assurer que la demande ne soit pas négative
    demande = max(demande, 0)

    # Enregistrer la demande dans l'historique
    demande_history.append(demande)

    # Système non régulé - Réapprovisionnement limité à des intervalles fixes
    if jour % delai_reapprovisionnement == 0:  # Réapprovisionnement toutes les X jours seulement
        if stock_non_regulated < S_initial:
            # Calcul de la quantité nécessaire pour atteindre la consigne
            manque = S_initial - stock_non_regulated
            # Réapprovisionnement limité à la valeur maximale fixée
            reapprovisionnement = min(manque, quantite_reapprovisionnement_non_regule)
            stock_non_regulated += reapprovisionnement

    # Réduire le stock selon la demande du jour pour le système non régulé
    stock_non_regulated -= demande

    # Assurer que le stock non régulé ne soit pas négatif
    if stock_non_regulated < 0:
        stock_non_regulated = 0

    # Assurer un minimum de stock de sécurité pour le système non régulé
    if stock_non_regulated < stock_securite:
        stock_non_regulated += stock_securite

    # Enregistrer le niveau de stock du système non régulé
    stock_history_non_regulated.append(stock_non_regulated)

    # Système régulé - PID avec réapprovisionnement limité à des intervalles fixes
    if jour % delai_reapprovisionnement == 0:  # Réapprovisionnement toutes les X jours seulement
        # Calcul de l'erreur entre le niveau de stock actuel et le niveau cible
        erreur = S_target - stock_regulated

        # Modulation de Ki en fonction de la distance par rapport à la consigne
        if abs(erreur) > 200:
            Ki = Ki_base * 2  # Augmenter Ki si l'erreur est importante
        else:
            Ki = Ki_base  # Utiliser le gain intégral de base sinon

        # Anti-windup : limiter l'accumulation de l'erreur intégrale si la commande approche la limite
        if abs(erreur_integrale * Ki) < limite_commande_max:
            erreur_integrale += erreur

        # Correction proportionnelle, intégrale et dérivée
        correction_P = Kp * erreur
        correction_I = Ki * erreur_integrale
        correction_D = Kd * (erreur - erreur_precedente)

        # Calcul de la quantité à commander
        commande = correction_P + correction_I + correction_D

        # Limiter la valeur de la commande
        commande = max(min(commande, limite_commande_max), 0)

        # Appliquer la commande (quantité commandée) au stock
        stock_regulated += commande

        # Mise à jour de l'erreur précédente
        erreur_precedente = erreur

    # Réduire le stock selon la demande du jour pour le système régulé
    stock_regulated -= demande

    # Assurer que le stock régulé ne soit pas négatif
    if stock_regulated < 0:
        stock_regulated = 0

    # Assurer un minimum de stock de sécurité pour le système régulé
    if stock_regulated < stock_securite:
        stock_regulated += stock_securite

    # Enregistrer le niveau de stock du système régulé
    stock_history_regulated.append(stock_regulated)

# Visualisation des niveaux de stock, de la consigne, et de la demande
plt.figure(figsize=(14, 8))

# Demande
plt.plot(range(periode), demande_history, label="Demande avec Perturbations", color='green', linestyle='-.')
# Système Non Régulé
plt.plot(range(periode), stock_history_non_regulated, label="Système Non Régulé avec Réapprovisionnement Traditionnel", color='blue')
# Système Régulé
plt.plot(range(periode), stock_history_regulated, label="Système Régulé avec Correcteur de Stock PID", color='red')
# Consigne
plt.axhline(y=S_target, color='purple', linestyle='--', label="Consigne de Stock (1200 unités)")

# Annotations des cycles de perturbations
for (t_min, t_95, amplitude) in perturbation_points:
    plt.axvline(x=t_min, color='g', linestyle='--', label="Début Perturbation" if t_min == perturbation_points[0][0] else "")
    plt.axvline(x=t_95, color='orange', linestyle='--', label="Fin de Récupération" if t_95 == perturbation_points[0][1] else "")

plt.xlabel("Temps (jours)")
plt.ylabel("Niveau de Stock / Demande")
plt.title("Comparaison entre Système Régulé (PID) et Système Non Régulé avec Perturbations sur la Demande (Réapprovisionnement Fixe)")
plt.legend()
plt.grid(True)
plt.show()

# Calcul et visualisation des coûts de stockage
cost_non_regulated = np.trapz(stock_history_non_regulated, dx=1)
cost_regulated = np.trapz(stock_history_regulated, dx=1)

print(f"Coût de stockage pour le système non régulé : {cost_non_regulated:.2f}")
print(f"Coût de stockage pour le système régulé : {cost_regulated:.2f}")

# Visualisation des coûts de stockage
plt.figure(figsize=(10, 6))
labels = ['Système Non Régulé', 'Système Régulé']
costs = [cost_non_regulated, cost_regulated]

plt.bar(labels, costs, color=['blue', 'red'])
plt.xlabel("Type de Système")
plt.ylabel("Coût de Stockage (unités de coût)")
plt.title("Comparaison des Coûts de Stockage entre Système Régulé (PID) et Non Régulé")
plt.grid(axis='y')
plt.show()

# Calcul et visualisation de la résilience
new_max_stock = max(max(stock_history_non_regulated), max(stock_history_regulated))

resilience_non_regulated = np.trapz([abs(new_max_stock - s) for s in stock_history_non_regulated], dx=1)
resilience_regulated = np.trapz([abs(new_max_stock - s) for s in stock_history_regulated], dx=1)

print(f"Résilience pour le système non régulé (aire sous la courbe de récupération) : {resilience_non_regulated:.2f}")
print(f"Résilience pour le système régulé (aire sous la courbe de récupération) : {resilience_regulated:.2f}")

# Visualisation de la résilience
plt.figure(figsize=(10, 6))
labels = ['Système Non Régulé', 'Système Régulé']
resilience_values = [resilience_non_regulated, resilience_regulated]

plt.bar(labels, resilience_values, color=['blue', 'red'])
plt.xlabel("Type de Système")
plt.ylabel("Résilience (Aire sous la courbe de récupération)")
plt.title("Comparaison de la Résilience entre Système Régulé (PID) et Non Régulé")
plt.grid(axis='y')
plt.show()
