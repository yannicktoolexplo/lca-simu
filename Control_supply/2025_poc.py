import numpy as np
import matplotlib.pyplot as plt
import random

# Simulation parameters
T = 100
stock = 100
stock_cible = 120
capacite_base = 20

# PID gains
Kp, Ki, Kd = 0.8, 0.1, 0.0
integrale, erreur_prec = 0, 0

# PoD (Physique des Décisions)
inertie_max = 0.3
inertie = 0
perturbation_production = 1.0
proba_risque = 0.1
proba_opp = 0.1
ampli_risque = 0.5
ampli_opp = 1.5

# Disruptions majeures
disruption_active = False
disruption_duree_restante = 0
proba_disruption = 0.05  # 5% chance de déclencher
duree_disruption_min = 5
duree_disruption_max = 10
impact_disruption = 0.2  # capacité réduite à 20%

# Historique
H_stock, H_prod, H_prod_ideale, H_dem = [], [], [], []
H_inertie, H_capacite_eff = [], []
H_carbone, H_cout, H_disruption = [], [], []

for t in range(T):
    # Demande (DES)
    demande = random.randint(5, 15) if random.random() > 0.1 else random.randint(20, 40)
    erreur = stock_cible - stock
    integrale += erreur
    derivee = erreur - erreur_prec

    # Inertie
    if abs(erreur) > 10:
        inertie = min(inertie + 0.05, inertie_max)
    else:
        inertie = max(inertie - 0.01, 0)

    # Risque / Opportunité (perturbation modérée)
    rand = random.random()
    if rand < proba_risque:
        perturbation_production = ampli_risque
    elif rand < proba_risque + proba_opp:
        perturbation_production = ampli_opp
    else:
        perturbation_production = 1.0

    # 🎯 Disruption majeure
    if not disruption_active and random.random() < proba_disruption:
        disruption_active = True
        disruption_duree_restante = random.randint(duree_disruption_min, duree_disruption_max)

    if disruption_active:
        perturbation_production *= impact_disruption
        disruption_duree_restante -= 1
        if disruption_duree_restante <= 0:
            disruption_active = False

    # Production idéale (sans PoD)
    prod_ideale = max(0, min(capacite_base, Kp * erreur + Ki * integrale + Kd * derivee))

    # Production réelle (PoD active)
    prod_reelle = (Kp * erreur + Ki * integrale + Kd * derivee)
    prod_reelle *= (1 - inertie)
    prod_reelle = max(0, min(capacite_base * perturbation_production, prod_reelle))

    # Mise à jour du stock
    stock += prod_reelle - demande
    stock = max(0, stock)

    # Enregistrement des données
    H_stock.append(stock)
    H_prod.append(prod_reelle)
    H_prod_ideale.append(prod_ideale)
    H_dem.append(demande)
    H_inertie.append(inertie)
    H_capacite_eff.append(capacite_base * perturbation_production)
    H_disruption.append(1 if disruption_active else 0)
    H_carbone.append((H_carbone[-1] if H_carbone else 0) + prod_reelle * 0.5)
    H_cout.append((H_cout[-1] if H_cout else 0) + prod_reelle * 2.0)
    erreur_prec = erreur

# 📊 Visualisation
plt.figure(figsize=(14, 10))

plt.subplot(3, 1, 1)
plt.plot(H_stock, label='Stock')
plt.plot(H_dem, label='Demande', linestyle=':')
plt.plot(H_prod, label='Production réelle', color='red')
plt.plot(H_prod_ideale, label='Production idéale', linestyle='--', color='green')
plt.title('Stock, Production et Demande')
plt.ylabel('Unités')
plt.legend()
plt.grid(True)

plt.subplot(3, 1, 2)
plt.plot(H_carbone, label='Carbone cumulé')
plt.plot(H_cout, label='Coût cumulé')
plt.title('Indicateurs globaux (System Dynamics)')
plt.ylabel('Cumul')
plt.legend()
plt.grid(True)

plt.subplot(3, 1, 3)
plt.plot(H_inertie, label='Inertie décisionnelle', color='orange')
plt.plot(H_capacite_eff, label='Capacité effective', color='blue')
plt.plot(H_disruption, label='Disruption active', linestyle='--', color='black')
plt.title('PoD et Disruptions')
plt.xlabel('Temps')
plt.ylabel('Facteurs')
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.show()
