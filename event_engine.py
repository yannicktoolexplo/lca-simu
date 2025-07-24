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

class EventManager:
    def __init__(self, events):
        self.events = sorted(events, key=lambda e: e.time)
        self.active_events = []
        self.current_time = 0

    def step(self, time, system_state):
        self.current_time = time
        # 1. Activer les nouveaux événements dont le temps de déclenchement est arrivé
        for event in list(self.events):
            if event.time == time:
                self.active_events.append({'event': event, 'time_left': event.duration})
                self.events.remove(event)
                # print(f"⚡ [t={time}] Déclenchement : {event.description}")
        # 2. Appliquer les effets de toutes les perturbations actives
        for e in self.active_events:
            event = e['event']
            if event.event_type == "panne":
                # Arrêt total (magnitude=1.0) ou réduction de capacité
                system_state['capacity'][event.target] = (0 if event.magnitude == 1.0 
                                                         else system_state['capacity_nominal'][event.target] * (1 - event.magnitude))
            elif event.event_type == "rupture_fournisseur":
                # Rupture de matière première : plus de stock disponible pour la ressource
                system_state['supply'][event.target] = 0
            elif event.event_type == "retard":
                # Retard fournisseur : on augmente le délai de livraison associé
                system_state['delays'][event.target] += event.magnitude
            # ... autres types d'événements éventuels ...
            e['time_left'] -= 1
        # 3. Désactiver les événements expirés et rétablir l’état nominal
        for e in list(self.active_events):
            if e['time_left'] <= 0:
                event = e['event']
                # print(f"✅ [t={time}] Fin de l'événement : {event.description}")
                # Restaurer les valeurs nominales à la fin de l'événement
                if event.event_type == "panne":
                    system_state['capacity'][event.target] = system_state['capacity_nominal'][event.target]
                elif event.event_type == "rupture_fournisseur":
                    system_state['supply'][event.target] = system_state['supply_nominal'][event.target]
                elif event.event_type == "retard":
                    system_state['delays'][event.target] -= event.magnitude
                self.active_events.remove(e)
