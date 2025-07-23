from event_engine import EventManager, example_events

def run_simulation_vivante(lines_config, N=60):
    # Prépare les sites
    sites = [cfg["location"] for cfg in lines_config]
    # Init capacité nominale
    nominal = {cfg["location"]: cfg.get("capacity", 100) for cfg in lines_config}
    # Init état système
    system_state = {
        'capacity': nominal.copy(),
        'capacity_nominal': nominal.copy(),
        'supply': {'aluminium': 1000, 'fabric': 800, 'polymers': 600, 'paint': 400},
        'supply_nominal': {'aluminium': 1000, 'fabric': 800, 'polymers': 600, 'paint': 400},
    }
    event_manager = EventManager(example_events)
    # Stocke la prod journalière de chaque site
    prod = {site: [] for site in sites}

    for t in range(N):
        event_manager.step(t, system_state)
        for site in sites:
            # Ici la production du jour est simplement la capacité du jour
            prod_day = system_state['capacity'][site]
            prod[site].append(prod_day)
            # ➡️ Ici tu pourras ajouter du calcul de stock, de coût, etc.
    return prod  # dict site → [prod_jour_0, prod_jour_1, ...]
