from line_production.production_engine import run_simulation_step

def init_organism_states(lines_config, initial_stock=100):
    """
    Initialise l'état interne pour chaque ligne de production du système vivant.
    :param lines_config: liste des configurations de lignes (avec dispatch_capacity, yield, etc.)
    :param initial_stock: stock initial de sièges pour chaque site (par défaut 100)
    :return: dictionnaire {site: state_dict}
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
            "base_consumption": 10  # consommation de base quotidienne (à ajuster si nécessaire)
        }
    return states

def organism_controller(state, target_stock, alpha=0.2, beta=0.1, gamma=0.05, Kp=1.0, Ki=0.1, Kd=0.05):
    """
    Contrôleur d'organisme vivant (PID modifié) ajustant la production en fonction de l'écart au stock cible.
    :param state: état actuel de la ligne (dictionnaire)
    :param target_stock: stock cible souhaité
    :param alpha, beta, gamma: coefficients pour la tension cognitive (perception inertielle)
    :param Kp, Ki, Kd: coefficients du contrôleur PID (proportionnel, intégral, dérivé)
    :return: commande de production (nombre de sièges à produire)
    """
    # Calcul de l'écart (gap) par rapport au stock cible
    gap = target_stock - state["stock"]
    delta_gap = gap - state.get("prev_gap", 0.0)
    perception = alpha * gap + beta * delta_gap  # perception ajustée
    # Tension cognitive inertielle
    new_tension = state["tension"] + gamma * (perception - state["tension"])
    # Mémoire adaptative (intégration de l'écart)
    new_memory = state["memory"] + gap
    # Commande de production (PID vivant)
    command = Kp * gap + Ki * new_memory + Kd * perception
    command = max(command, 0.0)  # la commande ne peut pas être négative
    # Mettre à jour l'état de l'organisme
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
    Simule un système vivant sur n_days jours, où chaque ligne ajuste sa production 
    en fonction d'un stock cible et d'un contrôleur vivant (organism_controller).
    :param lines_config: liste de configurations des lignes de production
    :param n_days: nombre de jours de simulation
    :param target_stock: stock cible de sécurité à maintenir pour chaque site
    :return: Liste des enregistrements (dict) par jour et par site, contenant stock, tension, commande, etc.
    """
    # Initialiser l'état de chaque organisme (ligne de production)
    states = init_organism_states(lines_config)
    results = []
    for day in range(n_days):
        for line in lines_config:
            site = line["location"]
            state = states[site]
            # 1. Décision cognitive (commande calculée via le contrôleur vivant)
            command_quantity = organism_controller(state, target_stock)
            # 2. Simulation du moteur physique pour ce jour (production effective et consommation)
            output = run_simulation_step(current_stock=state["stock"], command_quantity=command_quantity,
                                         max_capacity=state["capacity"], daily_consumption=state["base_consumption"])
            # 3. Mise à jour du stock avec la production du jour
            state["stock"] = output["new_stock"]
            state["day"] = day
            # 4. Enregistrer les résultats du jour pour ce site
            results.append({
                "day": day,
                "site": site,
                "stock": state["stock"],
                "tension": state["tension"],
                "command": state["command"],
                "stimulus": state["stimulus"]
            })
    return results
