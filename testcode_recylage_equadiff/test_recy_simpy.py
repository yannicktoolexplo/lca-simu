import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint

# Paramètres du modèle
alpha = 1.0  # Taux de production initial
beta = 0.1   # Taux d'ajustement de la production
gamma = 0.05  # Taux de consommation des stocks
delta = 0.1  # Taux de création de déchets par unité de production
d = 0.5      # Demande constante
r = 0.2      # Fraction de déchets recyclés

# Équations différentielles
def model(y, t):
    P, S, D = y
    R = r * D
    dPdt = alpha + R - beta * P
    dSdt = P - d - gamma * S
    dDdt = delta * P - R
    return [dPdt, dSdt, dDdt]

# Conditions initiales
P0 = 0.0  # Production initiale
S0 = 10.0  # Stock initial
D0 = 0.0  # Déchets initiaux
y0 = [P0, S0, D0]

# Échelle de temps
t = np.linspace(0, 50, 500)

# Résolution des équations différentielles
solution = odeint(model, y0, t)
P = solution[:, 0]
S = solution[:, 1]
D = solution[:, 2]
R = r * D  # Calcul de la quantité recyclée pour la visualisation

# Visualisation des résultats
plt.figure(figsize=(20, 5))

plt.subplot(1, 4, 1)
plt.plot(t, P, 'b-', label='Production (P)')
plt.xlabel('Temps')
plt.ylabel('Production')
plt.title('Évolution de la Production')
plt.legend()

plt.subplot(1, 4, 2)
plt.plot(t, S, 'r-', label='Stock (S)')
plt.xlabel('Temps')
plt.ylabel('Stock')
plt.title('Évolution des Stocks')
plt.legend()

plt.subplot(1, 4, 3)
plt.plot(t, D, 'g-', label='Déchets (D)')
plt.xlabel('Temps')
plt.ylabel('Déchets')
plt.title('Évolution des Déchets')
plt.legend()

plt.subplot(1, 4, 4)
plt.plot(t, R, 'm-', label='Recyclage (R)')
plt.xlabel('Temps')
plt.ylabel('Recyclage')
plt.title('Évolution du Recyclage')
plt.legend()

plt.tight_layout()
plt.show()
