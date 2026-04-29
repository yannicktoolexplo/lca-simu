import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# Paramètres
T = 120
capacite_fournisseur = 40
capacite_production = 30
perte_livraison = 0.1

# Génération de la consigne client avec perturbation
def generate_consigne_avec_perturbation(T=120, seed=1):
    np.random.seed(seed)
    base_demand = np.array([0]*20 + [18 if 40 <= t <= 60 else 9 for t in range(T-20)])
    consigne = np.clip(np.random.normal(base_demand, 2), 0, None).astype(float)
    if T > 50:
        consigne[50:55] += 15
    return consigne

consigne_client = generate_consigne_avec_perturbation(T)

# PID Controller
class PIDController:
    def __init__(self, Kp, Ki, Kd):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.integral = 0
        self.prev_error = 0

    def compute(self, setpoint, measurement):
        error = setpoint - measurement
        self.integral += error
        derivative = error - self.prev_error
        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        self.prev_error = error
        return output

# Simulation naturelle
def simulation_flux_corrected(consigne):
    stock_appro = [0] * 3
    stock_prod = [0] * 3
    stock_livr = [0] * 3
    approvisionnement, production, livraison = [], [], []

    for t in range(T):
        besoin_livraison = consigne[t-1] if t > 0 else consigne[t]
        sortie_livraison = sum([0.5, 0.3, 0.2][i]*stock_livr[-(i+1)] for i in range(3)) * (1 - perte_livraison)
        livraison.append(sortie_livraison)
        stock_livr.append(besoin_livraison)
        stock_livr.pop(0)

        besoin_production = livraison[-1]
        perturbation_prod = 1.0 if not (60 <= t <= 70) else 0.5
        sortie_production = sum([0.5, 0.3, 0.2][i]*stock_prod[-(i+1)] for i in range(3)) * perturbation_prod
        production.append(sortie_production)
        stock_prod.append(besoin_production)
        stock_prod.pop(0)

        besoin_appro = production[-1]
        sortie_approvisionnement = sum([0.5, 0.3, 0.2][i]*stock_appro[-(i+1)] for i in range(3))
        approvisionnement.append(sortie_approvisionnement)
        stock_appro.append(besoin_appro)
        stock_appro.pop(0)

    return {
        "consigne": consigne,
        "approvisionnement": approvisionnement,
        "production": production,
        "livraison": livraison
    }

# Simulation flux régulé
def simulation_flux_regulated(consigne, pid_controller_prod, pid_controller_appro):
    stock_appro = [0] * 3
    stock_prod = [0] * 3
    stock_livr = [0] * 3
    approvisionnement, production, livraison = [], [], []

    for t in range(T):
        perturbation_prod = 1.0 if not (60 <= t <= 70) else 0.5

        besoin_livraison = consigne[t-1] if t > 0 else consigne[t]
        sortie_livraison = sum([0.5, 0.3, 0.2][i]*stock_livr[-(i+1)] for i in range(3)) * (1 - perte_livraison)
        livraison.append(sortie_livraison)
        stock_livr.append(besoin_livraison)
        stock_livr.pop(0)

        prod = sum([0.5, 0.3, 0.2][i]*stock_prod[-(i+1)] for i in range(3))
        correction = pid_controller_prod.compute(sortie_livraison, prod)
        prod += correction
        prod = np.clip(prod, 0, capacite_production) * perturbation_prod
        stock_prod.append(prod)
        stock_prod.pop(0)
        production.append(prod)

        appro = sum([0.5, 0.3, 0.2][i]*stock_appro[-(i+1)] for i in range(3))
        correction_appro = pid_controller_appro.compute(prod, appro)
        appro += correction_appro
        appro = np.clip(appro, 0, capacite_fournisseur)
        stock_appro.append(appro)
        stock_appro.pop(0)
        approvisionnement.append(appro)

    return {
        "consigne": consigne,
        "approvisionnement": approvisionnement,
        "production": production,
        "livraison": livraison
    }

# Simulate production only with PID (Kp, Ki, Kd)
def simulate_production_pid(Kp, Ki, Kd, consigne, livraison_naturelle):
    stock_prod = [0] * 3
    production = []
    pid_prod = PIDController(Kp=Kp, Ki=Ki, Kd=Kd)

    for t in range(T):
        perturbation_prod = 1.0 if not (60 <= t <= 70) else 0.5
        prod = sum([0.5, 0.3, 0.2][i]*stock_prod[-(i+1)] for i in range(3))
        correction = pid_prod.compute(livraison_naturelle[t], prod)
        prod_corrige = np.clip(prod + correction, 0, capacite_production) * perturbation_prod
        stock_prod.append(prod_corrige)
        stock_prod.pop(0)
        production.append(prod_corrige)

    return np.array(production)

# Fonctions de coût
def hinf_cost_p_only(Kp, consigne, livraison_naturelle):
    if Kp < 0:
        return 1e6
    production = simulate_production_pid(Kp, 0, 0, consigne, livraison_naturelle)
    error = np.abs(production - livraison_naturelle)
    return np.max(error)

def hinf_cost_pi(params, consigne, livraison_naturelle):
    Kp, Ki = params
    if Kp < 0 or Ki < 0:
        return 1e6
    production = simulate_production_pid(Kp, Ki, 0, consigne, livraison_naturelle)
    error = np.abs(production - livraison_naturelle)
    return np.max(error)

def hinf_cost_pid(params, consigne, livraison_naturelle):
    Kp, Ki, Kd = params
    if Kp < 0 or Ki < 0 or Kd < 0:
        return 1e6
    production = simulate_production_pid(Kp, Ki, Kd, consigne, livraison_naturelle)
    error = np.abs(production - livraison_naturelle)
    return np.max(error)

# Simulation naturelle
res_natural = simulation_flux_corrected(consigne_client)

# Optimisations
res_p_only = minimize(hinf_cost_p_only, [0.95], args=(consigne_client, res_natural["livraison"]),
                      bounds=[(0.01, 5)], method='L-BFGS-B')
Kp_p_only = res_p_only.x[0]

res_pi = minimize(hinf_cost_pi, [0.95, 0], args=(consigne_client, res_natural["livraison"]),
                  bounds=[(0.01, 5), (0, 1)], method='L-BFGS-B')
Kp_pi, Ki_pi = res_pi.x

res_pid = minimize(hinf_cost_pid, [0.95, 0, 0], args=(consigne_client, res_natural["livraison"]),
                   bounds=[(0.01, 5), (0, 1), (0, 1)], method='L-BFGS-B')
Kp_pid, Ki_pid, Kd_pid = res_pid.x

print(f"PID robuste H∞ P-only : Kp = {Kp_p_only:.4f}")
print(f"PID robuste H∞ PI : Kp = {Kp_pi:.4f}, Ki = {Ki_pi:.4f}")
print(f"PID robuste H∞ complet : Kp = {Kp_pid:.4f}, Ki = {Ki_pid:.4f}, Kd = {Kd_pid:.4f}")

# Contrôleurs
pid_standard = PIDController(Kp=0.95, Ki=0, Kd=0)
pid_hinf_p_only = PIDController(Kp=Kp_p_only, Ki=0, Kd=0)
pid_hinf_pi = PIDController(Kp=Kp_pi, Ki=Ki_pi, Kd=0)
pid_hinf_pid = PIDController(Kp=Kp_pid, Ki=Ki_pid, Kd=Kd_pid)
pid_appro = PIDController(Kp=0.9, Ki=0, Kd=0)

# Simulations
res_standard = simulation_flux_regulated(consigne_client, pid_standard, pid_appro)
res_hinf_p_only = simulation_flux_regulated(consigne_client, pid_hinf_p_only, pid_appro)
res_hinf_pi = simulation_flux_regulated(consigne_client, pid_hinf_pi, pid_appro)
res_hinf_pid = simulation_flux_regulated(consigne_client, pid_hinf_pid, pid_appro)

# Erreurs
error_standard = np.abs(np.array(res_standard["production"]) - np.array(res_natural["livraison"]))
error_hinf_p_only = np.abs(np.array(res_hinf_p_only["production"]) - np.array(res_natural["livraison"]))
error_hinf_pi = np.abs(np.array(res_hinf_pi["production"]) - np.array(res_natural["livraison"]))
error_hinf_pid = np.abs(np.array(res_hinf_pid["production"]) - np.array(res_natural["livraison"]))

# IAE
IAE_standard = np.sum(error_standard)
IAE_hinf_p_only = np.sum(error_hinf_p_only)
IAE_hinf_pi = np.sum(error_hinf_pi)
IAE_hinf_pid = np.sum(error_hinf_pid)

# Gains
gain_p_only = (1 - IAE_hinf_p_only / IAE_standard) * 100
gain_pi = (1 - IAE_hinf_pi / IAE_standard) * 100
gain_pid = (1 - IAE_hinf_pid / IAE_standard) * 100

print(f"IAE PID standard : {IAE_standard:.2f}")
print(f"IAE PID robuste H∞ P-only : {IAE_hinf_p_only:.2f} (gain {gain_p_only:.2f}%)")
print(f"IAE PID robuste H∞ PI : {IAE_hinf_pi:.2f} (gain {gain_pi:.2f}%)")
print(f"IAE PID robuste H∞ complet : {IAE_hinf_pid:.2f} (gain {gain_pid:.2f}%)")

# Affichage
fig, axs = plt.subplots(6, 1, figsize=(14, 28), sharex=True)

for idx, (res, title, color) in enumerate([
    (res_natural, "Système 100% Naturel", 'orange'),
    (res_standard, "PID Standard", 'red'),
    (res_hinf_p_only, "PID Robuste H∞ (P-only)", 'blue'),
    (res_hinf_pi, "PID Robuste H∞ (PI)", 'green'),
    (res_hinf_pid, "PID Robuste H∞ (PID complet)", 'purple')
]):
    axs[idx].plot(res["approvisionnement"], 'g--', label="Approvisionnement")
    axs[idx].plot(res["production"], color=color, label="Production")
    axs[idx].plot(res["livraison"], 'b--', label="Livraison")
    axs[idx].plot(res["consigne"], 'k--', label="Consigne client")
    axs[idx].axvline(x=50, color='orange', linestyle='--')
    axs[idx].axvline(x=60, color='purple', linestyle='--')
    axs[idx].axvline(x=70, color='purple', linestyle='--')
    axs[idx].set_title(title)
    axs[idx].legend()
    axs[idx].grid(True)
    axs[idx].set_ylabel("Quantité")

axs[5].plot(error_standard, 'r', label="Erreur PID Standard")
axs[5].plot(error_hinf_p_only, 'b', label="Erreur PID H∞ (P-only)")
axs[5].plot(error_hinf_pi, 'g', label="Erreur PID H∞ (PI)")
axs[5].plot(error_hinf_pid, 'purple', label="Erreur PID H∞ (PID complet)")
axs[5].set_title("Erreur absolue Production vs Livraison")
axs[5].legend()
axs[5].grid(True)
axs[5].set_xlabel("Temps")
axs[5].set_ylabel("Erreur")

plt.tight_layout()
plt.show()

# ======================
# 🔥 Analyse de la Résilience 🔥
# ======================

# Regrouper toutes les erreurs
errors = {
    'Standard': error_standard,
    'Hinf P-only': error_hinf_p_only,
    'Hinf PI': error_hinf_pi,
    'Hinf PID complet': error_hinf_pid
}

# 🎯 1. Histogrammes des erreurs
plt.figure(figsize=(14, 8))
for name, err in errors.items():
    plt.hist(err, bins=30, alpha=0.6, label=f'{name}', density=True)

plt.title("Distribution des erreurs absolues (Histogrammes)")
plt.xlabel("Erreur absolue")
plt.ylabel("Densité")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# 🎯 2. Boxplot des erreurs
plt.figure(figsize=(10, 6))
plt.boxplot(errors.values(), labels=errors.keys(), patch_artist=True)
plt.title("Comparaison des erreurs (Boxplot)")
plt.ylabel("Erreur absolue")
plt.grid(True)
plt.tight_layout()
plt.show()

# 🎯 3. Zoom temporel pendant la perturbation (50 à 70)
plt.figure(figsize=(14, 8))
t_zoom = np.arange(50, 70)

plt.plot(t_zoom, res_standard["production"][50:70], 'r', label="PID Standard")
plt.plot(t_zoom, res_hinf_p_only["production"][50:70], 'b', label="PID H∞ P-only")
plt.plot(t_zoom, res_hinf_pi["production"][50:70], 'g', label="PID H∞ PI")
plt.plot(t_zoom, res_hinf_pid["production"][50:70], 'purple', label="PID H∞ PID complet")
plt.plot(t_zoom, res_natural["livraison"][50:70], 'k--', label="Livraison cible")

plt.title("Zoom sur la Perturbation [50-70]")
plt.xlabel("Temps")
plt.ylabel("Production")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
