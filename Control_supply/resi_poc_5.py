# Réimportation des bibliothèques nécessaires après la réinitialisation de l'environnement
import numpy as np
import scipy.signal
import matplotlib.pyplot as plt

# Définition des constantes de temps pour chaque variable
tau_s_mp = 5    # Temps pour le Stock MP
tau_s_pf = 7    # Temps pour le Stock PF
tau_p = 10      # Temps pour le Délai de production
tau_d = 8       # Temps pour le Délai logistique

# Définition des matrices de l'espace d'état
A = np.array([
    [-1/tau_s_mp,  0,          0,         0,        0,        0],
    [0, -1/tau_s_pf, 0,         0,        0,        0],
    [0, 0, -1/tau_p,  0,        0,        0],
    [0, 0, 0, -1/tau_d, 0,        0],
    [0, 0, 0, 0,        0,        0],
    [0, 0, 0, 0,        0,        0]
])

B = np.array([
    [1/tau_s_mp,  0,         0,         0],   # Stock MP dépend de sa consigne
    [0, 1/tau_s_pf, 0,         0],   # Stock PF dépend de sa consigne
    [0, 0, 1/tau_p,  0],   # Délai production influencé uniquement par sa consigne
    [0, 0, 0, 1/tau_d],   # Délai logistique influencé uniquement par sa consigne
    [0, 0, 0, 0],   # Pas d'effet direct sur les coûts
    [0, 0, 0, 0]    # Pas d'effet direct sur CO2
])

# Simulation
T = 100  # Durée de la simulation en jours
dt = 1   # Pas de temps
timesteps = np.arange(0, T, dt)

# Définition des consignes en entrée du système
step_time_start = 10  # Début de l'échelon
step_time_change = 50  # Moment de la perturbation (changement de consigne)

# Initialisation des consignes
u_stock_mp = np.full_like(timesteps, 100)
u_stock_pf = np.full_like(timesteps, 50)
u_delai_prod = np.full_like(timesteps, 10)
u_delai_log = np.full_like(timesteps, 5)

# Application des consignes à t=10 et modifications à t=50
u_stock_mp[timesteps >= step_time_start] = 150
u_stock_pf[timesteps >= step_time_start] = 75
u_delai_prod[timesteps >= step_time_start] = 15
u_delai_log[timesteps >= step_time_start] = 8

u_stock_mp[timesteps >= step_time_change] = 130
u_stock_pf[timesteps >= step_time_change] = 65
u_delai_prod[timesteps >= step_time_change] = 12
u_delai_log[timesteps >= step_time_change] = 6

# Réinitialisation de l'état initial du système
x = np.array([100, 50, 10, 5, 10000, 500]).reshape(-1, 1)
X_pid = [x.flatten()]

# Implémentation d'un régulateur PID
class PIDController:
    def __init__(self, Kp, Ki, Kd, setpoint=0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.prev_error = 0
        self.integral = 0

    def compute(self, measurement, dt):
        error = self.setpoint - measurement
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt
        self.prev_error = error
        return self.Kp * error + self.Ki * self.integral + self.Kd * derivative

# Définition des paramètres PID
Kp, Ki, Kd = 2.0, 0.5, 1.0
pid_stock_mp = PIDController(Kp, Ki, Kd, setpoint=100)
pid_stock_pf = PIDController(Kp, Ki, Kd, setpoint=50)
pid_delai_prod = PIDController(Kp, Ki, Kd, setpoint=10)
pid_delai_log = PIDController(Kp, Ki, Kd, setpoint=5)

# Simulation avec PID
for t_idx, t in enumerate(timesteps[1:]):
    pid_stock_mp.setpoint = u_stock_mp[t_idx]
    pid_stock_pf.setpoint = u_stock_pf[t_idx]
    pid_delai_prod.setpoint = u_delai_prod[t_idx]
    pid_delai_log.setpoint = u_delai_log[t_idx]
    
    u_pid = np.array([
        [pid_stock_mp.compute(x[0, 0], dt)],
        [pid_stock_pf.compute(x[1, 0], dt)],
        [pid_delai_prod.compute(x[2, 0], dt)],
        [pid_delai_log.compute(x[3, 0], dt)]
    ])
    x = x + (A @ x + B @ u_pid) * dt
    X_pid.append(x.flatten())

X_pid = np.array(X_pid)

# Analyse des performances : Transformation de Laplace et diagrammes de Bode
s = scipy.signal.lti([1, 0], [1])
G_stock_mp = scipy.signal.TransferFunction([1/tau_s_mp], [1, 1/tau_s_mp])
G_stock_pf = scipy.signal.TransferFunction([1/tau_s_pf], [1, 1/tau_s_pf])
G_delai_prod = scipy.signal.TransferFunction([1/tau_p], [1, 1/tau_p])
G_delai_log = scipy.signal.TransferFunction([1/tau_d], [1, 1/tau_d])

w, mag_stock_mp, phase_stock_mp = scipy.signal.bode(G_stock_mp)
w, mag_stock_pf, phase_stock_pf = scipy.signal.bode(G_stock_pf)
w, mag_delai_prod, phase_delai_prod = scipy.signal.bode(G_delai_prod)
w, mag_delai_log, phase_delai_log = scipy.signal.bode(G_delai_log)

# Affichage des résultats
fig, axs = plt.subplots(2, 2, figsize=(12, 8))

# Stock MP
axs[0, 0].semilogx(w, mag_stock_mp, label="Magnitude", color="blue")
axs[0, 0].semilogx(w, phase_stock_mp, label="Phase", linestyle="dotted", color="blue")
axs[0, 0].set_title("Bode - Stock MP")
axs[0, 0].legend()
axs[0, 0].grid()

# Stock PF
axs[0, 1].semilogx(w, mag_stock_pf, label="Magnitude", color="orange")
axs[0, 1].semilogx(w, phase_stock_pf, label="Phase", linestyle="dotted", color="orange")
axs[0, 1].set_title("Bode - Stock PF")
axs[0, 1].legend()
axs[0, 1].grid()

# Délai production
axs[1, 0].semilogx(w, mag_delai_prod, label="Magnitude", color="green")
axs[1, 0].semilogx(w, phase_delai_prod, label="Phase", linestyle="dotted", color="green")
axs[1, 0].set_title("Bode - Délai production")
axs[1, 0].legend()
axs[1, 0].grid()

# Délai logistique
axs[1, 1].semilogx(w, mag_delai_log, label="Magnitude", color="red")
axs[1, 1].semilogx(w, phase_delai_log, label="Phase", linestyle="dotted", color="red")
axs[1, 1].set_title("Bode - Délai logistique")
axs[1, 1].legend()
axs[1, 1].grid()

plt.suptitle("Diagrammes de Bode - Magnitude et Phase")
plt.tight_layout()
plt.show()

