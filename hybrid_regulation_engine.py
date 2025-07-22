from line_production.line_production_settings import lines_config
from line_production.production_engine import run_simulation_step

def init_organism_states(lines_config, initial_stock=100):
    """
    Initialise les états internes vivants pour chaque ligne.
    """
    states = {}
    for line in lines_config:
        site = line["location"]
        states[site] = {
            "stock": initial_stock,
            "memory": 0.0,
            "tension": 0.0,
            "prev_gap": 0.0,
            "day": 0,
            "command": 0.0,
            "stimulus": 0.0,
            "capacity": line.get("dispatch_capacity", 50),
            "yield": line.get("yield", 1.0),
            "base_consumption": 10  # À rendre dynamique plus tard
        }
    return states

def organism_controller(state, target_stock,
                        alpha=0.2, beta=0.1, gamma=0.05,
                        Kp=1.0, Ki=0.1, Kd=0.05):
    """
    Fonction de régulation vivante : tension cognitive, mémoire, commande.
    """
    # Perception de l'écart
    gap = target_stock - state["stock"]
    delta_gap = gap - state.get("prev_gap", 0.0)
    perception = alpha * gap + beta * delta_gap

    # Tension cognitive inertielle
    new_tension = state["tension"] + gamma * (perception - state["tension"])

    # Mémoire adaptative (intégrale du gap)
    new_memory = state["memory"] + gap

    # Commande (PID vivant)
    command = Kp * gap + Ki * new_memory + Kd * perception
    command = max(command, 0)

    # Mise à jour de l’état
    state.update({
        "memory": new_memory,
        "tension": new_tension,
        "prev_gap": gap,
        "stimulus": perception,
        "command": command
    })

    return command

def run_simulation_vivant(lines_config, n_days=30, target_stock=120):
    """
    Boucle de simulation vivante (système vivant avec surcouche cognitive).
    """
    states = init_organism_states(lines_config)
    results = []

    for day in range(n_days):
        for line in lines_config:
            site = line["location"]
            state = states[site]

            # 1. Décision cognitive
            command = organism_controller(state, target_stock)

            # 2. Simulation du moteur physique (ici simplifié via run_simulation_step)
            production_output = run_simulation_step(
                current_stock=state["stock"],
                command_quantity=command,
                max_capacity=state["capacity"],
                daily_consumption=state["base_consumption"]
            )

            # 3. Mise à jour du stock
            state["stock"] = production_output["new_stock"]
            state["day"] = day

            # 4. Archivage des résultats
            results.append({
                "day": day,
                "site": site,
                "stock": state["stock"],
                "tension": state["tension"],
                "command": command,
                "stimulus": state["stimulus"]
            })

    return results
