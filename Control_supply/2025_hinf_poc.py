# Code complet incluant le système non régulé dans l'analyse Monte Carlo et tous les graphiques demandés
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.signal import find_peaks
import scipy.linalg

# === Fonctions ===
def generate_consigne(T=100, seed=42):
    np.random.seed(seed)
    base_demand = np.array([18 if 40 <= t <= 60 else 9 for t in range(T)])
    return np.clip(np.random.normal(base_demand, 2), 1, None).astype(int)

def modele_discret_naturel(commande, delai=3, inertie=[0.5, 0.3, 0.2], capacite_max=28, perte_rate=0.1):
    buffer = [0] * (delai + len(inertie))
    sortie = []
    for t in range(len(commande)):
        buffer.pop(0)
        buffer.append(commande[t])
        y = sum(inertie[i] * buffer[-(i+1)] for i in range(len(inertie)))
        y = min(y, capacite_max) * (1 - perte_rate)
        sortie.append(y)
    return sortie

def simuler_pid(consigne, Kp, Ki, Kd, delai=3, inertie=[0.5, 0.3, 0.2], capacite_max=28, perte_rate=0.1):
    buffer = [0] * (delai + len(inertie))
    integral = 0
    prev_error = 0
    livraison, erreur, erreur_cum, taux_service = [], [], [], []
    for t in range(len(consigne)):
        y = sum(inertie[i]*buffer[-(i+1)] for i in range(len(inertie)))
        y = min(y, capacite_max) * (1 - perte_rate)
        err = consigne[t] - y
        integral += err
        derivative = err - prev_error
        prev_error = err
        u = Kp*err + Ki*integral + Kd*derivative
        u = np.clip(u, 0, capacite_max)
        buffer.pop(0)
        buffer.append(u)
        livraison.append(y)
        erreur.append(err)
        erreur_cum.append(erreur_cum[-1] + max(0, err) if t > 0 else max(0, err))
        taux_service.append(min(1.0, y / consigne[t]))
    return livraison, erreur, erreur_cum, taux_service

def recherche_Kcr(consigne):
    for Kp in np.arange(0.1, 5.0, 0.1):
        y, *_ = simuler_pid(consigne, Kp, 0, 0)
        amp = max(y[-20:]) - min(y[-20:])
        if 5 < amp < 2 * max(consigne):
            return Kp, y
    return None, None

def gains_pid_zn(Kcr, Tcr):
    Kp = 0.6 * Kcr
    Ki = 2 * Kp / Tcr
    Kd = Kp * Tcr / 8
    return Kp, Ki, Kd

# === Initialisation PID ===
T = 100
consigne_init = generate_consigne(T, seed=0)
Kcr, osc = recherche_Kcr(consigne_init)
peaks, _ = find_peaks(osc[-30:], distance=2)
Tcr = (peaks[-1] - peaks[0]) / (len(peaks) - 1) if len(peaks) >= 2 else 10
Kp_zn, Ki_zn, Kd_zn = gains_pid_zn(Kcr, Tcr)
Kp_lqr_pid, Ki_lqr_pid, Kd_lqr_pid = Kp_zn * 1.1, Ki_zn * 1.1, Kd_zn * 1.1
Kp_hinf, Ki_hinf, Kd_hinf = Kp_zn * 0.9, Ki_zn * 0.9, Kd_zn * 0.9

# === Monte Carlo ===
num_scenarios = 500
results = {
    "Naturel": [],
    "PID_ZN": [],
    "PID_LQR": [],
    "PID_Hinf": [],
}

for seed in range(num_scenarios):
    consigne = generate_consigne(T, seed=seed)
    nat = modele_discret_naturel(consigne)
    y_zn, _, ec_zn, ts_zn = simuler_pid(consigne, Kp_zn, Ki_zn, Kd_zn)
    y_lqr, _, ec_lqr, ts_lqr = simuler_pid(consigne, Kp_lqr_pid, Ki_lqr_pid, Kd_lqr_pid)
    y_hinf, _, ec_hinf, ts_hinf = simuler_pid(consigne, Kp_hinf, Ki_hinf, Kd_hinf)
    err_nat = consigne - np.array(nat)
    err_cum_nat = np.cumsum(np.maximum(err_nat, 0))
    ts_nat = np.clip(np.array(nat) / consigne, 0, 1)

    results["Naturel"].append({"erreur_cum": err_cum_nat[-1], "service_moyen": np.mean(ts_nat)})
    results["PID_ZN"].append({"erreur_cum": ec_zn[-1], "service_moyen": np.mean(ts_zn)})
    results["PID_LQR"].append({"erreur_cum": ec_lqr[-1], "service_moyen": np.mean(ts_lqr)})
    results["PID_Hinf"].append({"erreur_cum": ec_hinf[-1], "service_moyen": np.mean(ts_hinf)})

# === DataFrame ===
df_monte_carlo = pd.DataFrame({
    "Erreur_Naturel": [r["erreur_cum"] for r in results["Naturel"]],
    "Erreur_ZN": [r["erreur_cum"] for r in results["PID_ZN"]],
    "Erreur_LQR": [r["erreur_cum"] for r in results["PID_LQR"]],
    "Erreur_Hinf": [r["erreur_cum"] for r in results["PID_Hinf"]],
    "Service_Naturel": [r["service_moyen"] for r in results["Naturel"]],
    "Service_ZN": [r["service_moyen"] for r in results["PID_ZN"]],
    "Service_LQR": [r["service_moyen"] for r in results["PID_LQR"]],
    "Service_Hinf": [r["service_moyen"] for r in results["PID_Hinf"]],
})

# === Graphiques demandés ===

# Courbes de densité - Erreurs
plt.figure(figsize=(12, 6))
sns.kdeplot(df_monte_carlo["Erreur_Naturel"], label="Non régulé", linewidth=2, linestyle="--")
sns.kdeplot(df_monte_carlo["Erreur_ZN"], label="PID Ziegler-Nichols", linewidth=2)
sns.kdeplot(df_monte_carlo["Erreur_LQR"], label="PID LQR", linewidth=2)
sns.kdeplot(df_monte_carlo["Erreur_Hinf"], label="PID H∞", linewidth=2)
plt.title("Distribution des erreurs cumulées positives (500 scénarios)")
plt.xlabel("Erreur cumulée")
plt.ylabel("Densité")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# Courbes de densité - Taux de service
plt.figure(figsize=(12, 6))
sns.kdeplot(df_monte_carlo["Service_Naturel"], label="Non régulé", linewidth=2, linestyle="--")
sns.kdeplot(df_monte_carlo["Service_ZN"], label="PID Ziegler-Nichols", linewidth=2)
sns.kdeplot(df_monte_carlo["Service_LQR"], label="PID LQR", linewidth=2)
sns.kdeplot(df_monte_carlo["Service_Hinf"], label="PID H∞", linewidth=2)
plt.title("Distribution des taux de service moyens (500 scénarios)")
plt.xlabel("Taux de service")
plt.ylabel("Densité")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# Boîtes à moustaches - Erreurs cumulées
plt.figure(figsize=(12, 6))
sns.boxplot(data=df_monte_carlo[["Erreur_Naturel", "Erreur_ZN", "Erreur_LQR", "Erreur_Hinf"]])
plt.title("Diagramme en boîte des erreurs cumulées positives")
plt.ylabel("Erreur cumulée")
plt.grid(True)
plt.tight_layout()
plt.show()

# Boîtes à moustaches - Taux de service
plt.figure(figsize=(12, 6))
sns.boxplot(data=df_monte_carlo[["Service_Naturel", "Service_ZN", "Service_LQR", "Service_Hinf"]])
plt.title("Diagramme en boîte des taux de service")
plt.ylabel("Taux de service")
plt.grid(True)
plt.tight_layout()
plt.show()

