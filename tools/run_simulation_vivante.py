from line_production.line_production_settings import scenario_events
from resilience.hybrid_regulation_engine import run_simulation_vivant

def run_simulation_vivante(lines_config, N=60):
    """
    Exécute une simulation "vivante" simplifiée sur N pas de temps (par exemple N jours).
    Utilise le moteur d'événements sur les lignes de production sans cycle de production complet.
    :param lines_config: configuration des lignes de production
    :param N: nombre de pas de temps à simuler
    :return: dict site -> [production par pas de temps] sur la période simulée
    """
    # Préparation des sites de production
    sites = [cfg["location"] for cfg in lines_config]
    # État système initial (capacités nominales et stocks initiaux de matières premières)
    nominal_capacity = {cfg["location"]: cfg.get("capacity", 100) for cfg in lines_config}
    system_state = {
        'capacity': nominal_capacity.copy(),
        'capacity_nominal': nominal_capacity.copy(),
        'supply': {'aluminium': 1000, 'fabric': 800, 'polymers': 600, 'paint': 400},
        'supply_nominal': {'aluminium': 1000, 'fabric': 800, 'polymers': 600, 'paint': 400},
        'delays': {material: 0 for material in ['aluminium', 'fabric', 'polymers', 'paint']}
    }
    # Utiliser le EventManager avec des événements exemples (scénario "vivant")
    events_vivants = scenario_events.get("vivant", [])
    from resilience.event_engine import EventManager
    event_manager = EventManager(events_vivants)
    # Dictionnaire pour stocker la production quotidienne de chaque site
    production_per_site = {site: [] for site in sites}
    # Boucle de simulation sur N pas de temps
    for t in range(N):
        event_manager.step(t, system_state)
        for site in sites:
            # Production du jour = capacité actuelle du site (après éventuelles perturbations)
            produced_today = system_state['capacity'][site]
            production_per_site[site].append(produced_today)
            # (Ici on pourrait ajouter le calcul de stock, coût, etc.)
    return production_per_site
