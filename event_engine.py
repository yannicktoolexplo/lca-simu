# event_engine.py
from collections import namedtuple

# 1. Définition de la structure d'un événement perturbateur
PerturbationEvent = namedtuple('PerturbationEvent', [
    'time',         # Instant de déclenchement (int)
    'target',       # Site ou ressource visé (ex: 'France', 'aluminium')
    'event_type',   # 'panne', 'rupture_fournisseur', 'retard'
    'magnitude',    # Intensité (ex: 1.0 pour arrêt total, 0.5 pour partiel, +2 pour délai supplémentaire)
    'duration',     # Durée de l'événement (pas de temps)
    'description',  # Pour logs et suivi
])

# 2. Gestionnaire d'événements
class EventManager:
    def __init__(self, events):
        self.events = sorted(events, key=lambda e: e.time)
        self.active_events = []
        self.current_time = 0

    def step(self, time, system_state):
        self.current_time = time
        # Activer les nouveaux événements dont le temps est arrivé
        for event in list(self.events):
            if event.time == time:
                self.active_events.append({'event': event, 'time_left': event.duration})
                self.events.remove(event)
                print(f"⚡ [t={time}] Déclenchement : {event.description}")

        # Appliquer les perturbations actives
        for event_dict in self.active_events:
            event = event_dict['event']
            if event.event_type == "panne":
                system_state['capacity'][event.target] = 0
            elif event.event_type == "rupture_fournisseur":
                system_state['supply'][event.target] = 0
            elif event.event_type == "retard":
                system_state['delays'][event.target] += event.magnitude

            event_dict['time_left'] -= 1

        # Désactiver les événements arrivés à échéance
        for event_dict in list(self.active_events):
            if event_dict['time_left'] <= 0:
                event = event_dict['event']
                print(f"✅ [t={time}] Fin de l'événement : {event.description}")
                # Rétablir les valeurs nominales
                if event.event_type == "panne":
                    system_state['capacity'][event.target] = system_state['capacity_nominal'][event.target]
                elif event.event_type == "rupture_fournisseur":
                    system_state['supply'][event.target] = system_state['supply_nominal'][event.target]
                elif event.event_type == "retard":
                    system_state['delays'][event.target] -= event.magnitude
                self.active_events.remove(event_dict)

# 3. Exemple d'événements à simuler
example_events = [
    PerturbationEvent(time=20, target="France", event_type="panne", magnitude=1.0, duration=5, description="Arrêt total France"),
    PerturbationEvent(time=50, target="aluminium", event_type="rupture_fournisseur", magnitude=1.0, duration=10, description="Plus d'aluminium"),
    # Ajoute ici d'autres scénarios si besoin
]
