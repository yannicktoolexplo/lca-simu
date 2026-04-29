import numpy as np
import matplotlib.pyplot as plt

# Définir les paramètres initiaux
S_initial = 1200  # Niveau de stock initial et valeur cible
S_target = 1200   # Niveau de stock cible
stock_securite = 200  # Niveau de stock de sécurité
perturbation_frequency = 50  # Fréquence des perturbations (en jours)
demande_moyenne = 50  # Demande moyenne par jour
periode = 200  # Période de simulation (jours) augmentée pour permettre de finir la dernière perturbation
delai_reapprovisionnement = 2 # Jours

# Réapprovisionnement par saut pour le système non régulé
stock_saut = 950  # Seuil de déclenchement d'un saut d'approvisionnement
quantite_saut = 100  # Quantité de réapprovisionnement par saut, réduite pour montrer l'impact de la demande

# Générer des perturbations en échelon (soudaines et de grande amplitude)
perturbation_amplitudes = [800, 700, 900, 1000]  # Amplitudes des perturbations (grandes pour impact sévère)
number_of_cycles = 4  # Nombre de cycles d'approvisionnement et de perturbations

perturbation_points = []
current_t_min = 10
for cycle in range(number_of_cycles):
    current_t_95 = current_t_min + 5  # Un échelon rapide (presque instantané)
    S_min = S_initial - perturbation_amplitudes[cycle]  # Définir l'amplitude de la perturbation
    perturbation_points.append((current_t_min, current_t_95, S_min))
    current_t_min += perturbation_frequency + np.random.randint(-5, 5)  # Définir quand la prochaine perturbation commencera

# Simulation de la dynamique du stock pour le système non régulé avec réapprovisionnement dynamique et limitation
stock_non_regulated = S_initial
stock_history_non_regulated = []
inertia_very_low = 0.05  # Inertie très faible pour représenter une correction limitée
en_perturbation = False
limite_commande_max = 600  # Limitation de la quantité réapprovisionnée à 500 unités par cycle

for jour in range(periode):
    # Calcul de la demande aléatoire (autour de la moyenne)
    demande = demande_moyenne + np.random.randint(-10, 10)

    # Détecter si une perturbation est en cours
    for (t_min, t_95, S_min) in perturbation_points:
        if t_min <= jour <= t_95:
            en_perturbation = True
            stock_non_regulated = S_min  # Stock subit une chute directe (perturbation)
        elif jour > t_95:
            en_perturbation = False

    # Si la perturbation est terminée, appliquer la correction ou réapprovisionnement
    if not en_perturbation:
        # Réduire le stock selon la demande du jour
        stock_non_regulated -= demande

        # Assurer que le stock ne soit pas négatif
        if stock_non_regulated < 0:
            stock_non_regulated = 0

        # Réapprovisionnement par quantité limitée si le stock est trop bas, effectué toutes les 7 jours
        if stock_non_regulated < stock_saut and jour % delai_reapprovisionnement == 0:  # Réapprovisionnement moins fréquent, toutes les 7 jours
            quantite_a_commander = S_target - stock_non_regulated
            # Limiter la quantité à commander à la limite maximale
            quantite_a_commander = min(quantite_a_commander, limite_commande_max)
            stock_non_regulated += quantite_a_commander  # Ajouter la quantité limitée

    # Enregistrer le niveau de stock
    stock_history_non_regulated.append(stock_non_regulated)

# Configuration des gains PID pour le contrôle avec Anti-Windup et Modulation de Ki
Kp = 0.8  # Gain proportionnel, inchangé
Ki_base = 0.1  # Gain intégral de base
Kd = 0.01   # Gain dérivatif, inchangé

# Limite de commande pour éviter un windup trop important
limite_commande_max = 500  # Limite maximale pour la commande

# Simulation de la dynamique du stock pour le système régulé (PID) avec Anti-Windup et modulation de Ki
stock_regulated = S_initial
stock_history_regulated = []
erreur_integrale = 0
erreur_precedente = 0
consigne_history = []  # Historique de la valeur de consigne incluant les perturbations
en_perturbation = False

# Boucle de simulation pour le système régulé avec PID et délai de réapprovisionnement
for jour in range(periode):
    # Calcul de la demande aléatoire (autour de la moyenne)
    demande = demande_moyenne + np.random.randint(-10, 10)

    # Détecter si une perturbation est en cours
    for (t_min, t_95, S_min) in perturbation_points:
        if t_min <= jour <= t_95:
            en_perturbation = True
            # FORCER le système régulé à suivre la perturbation
            stock_regulated = S_min
            S_target = S_min  # Ajuster la consigne vers la valeur perturbée
            erreur_integrale = 0  # Réinitialiser l'erreur intégrale à chaque nouvelle perturbation
        elif jour > t_95:
            en_perturbation = False
            S_target = S_initial  # Retour à la consigne d'origine après perturbation

    # Enregistrer la valeur de consigne dans l'historique
    consigne_history.append(S_target)

    # Réapprovisionnement limité à des intervalles fixes (tous les 7 jours)
    if jour % delai_reapprovisionnement == 0 and not en_perturbation:
        if stock_regulated < S_target:
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
            if commande > 0:
                stock_regulated += commande

            # Mise à jour de l'erreur précédente
            erreur_precedente = erreur

    # Réduire le stock selon la demande du jour, mais seulement après la perturbation
    if not en_perturbation:
        stock_regulated -= demande

    # Assurer un minimum de stock de sécurité
    if stock_regulated < stock_securite:
        stock_regulated += stock_securite

    # Enregistrer le niveau de stock
    stock_history_regulated.append(stock_regulated)





# Visualisation de la dynamique des stocks pour les cycles de perturbations
plt.figure(figsize=(12, 8))

# Système Non Régulé avec Réapprovisionnement Progressif (Trait Continu)
plt.plot(range(periode), stock_history_non_regulated, label="Système Non Régulé avec Réapprovisionnement Traditionnel", color='b')

# Système Régulé avec Correcteur de Stock PID
plt.plot(range(periode), stock_history_regulated, label="Système Régulé avec Correcteur de Stock PID", color='r')

# Valeur de Consigne avec Perturbations (en pointillé)
plt.plot(range(periode), consigne_history, label="Valeur de Consigne avec Perturbations", color='g', linestyle='--')

# Annotation des cycles
for (t_min, t_95, S_min) in perturbation_points:
    plt.axvline(x=t_min, color='g', linestyle='--', label=f"Début Perturbation (t_min = {t_min} jours)" if t_min == perturbation_points[0][0] else "")
    plt.axvline(x=t_95, color='orange', linestyle='--', label=f"Fin de Récupération (t_95 = {t_95} jours)" if t_95 == perturbation_points[0][1] else "")

plt.xlabel("Temps (jours)")
plt.ylabel("Niveau de Stock")
plt.title("Comparaison entre Système Régulé (PID) et Système Non Régulé avec Perturbations en Échelon")
plt.legend()
plt.grid(True)
plt.show()

# Calcul et visualisation du coût de stockage
cost_non_regulated = np.trapz(stock_history_non_regulated, range(periode))
cost_regulated = np.trapz(stock_history_regulated, range(periode))

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

# Calcul et visualisation de la résilience pour les systèmes régulé et non régulé
# La résilience est mesurée ici comme l'aire sous la courbe de récupération par rapport au niveau de stock initial
# Calcul de la résilience à partir de la différence avec le nouveau maximum établi
new_max_stock = max(max(stock_history_non_regulated), max(stock_history_regulated))

# Calcul de la résilience pour le système non régulé
resilience_non_regulated = np.trapz([abs(new_max_stock - s) for s in stock_history_non_regulated], dx=1)

# Calcul de la résilience pour le système régulé
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