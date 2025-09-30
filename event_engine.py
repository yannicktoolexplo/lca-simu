from collections import namedtuple

# Définition de la structure d'un événement perturbateur
PerturbationEvent = namedtuple('PerturbationEvent', [
    'time',         # Instant de déclenchement (int, pas de temps)
    'target',       # Site ou ressource visé (ex: 'France' ou 'aluminium')
    'event_type',   # Type d'événement: 'panne', 'rupture_fournisseur', 'retard', etc.
    'magnitude',    # Intensité (ex: 1.0 pour arrêt total, 0.5 pour réduction de 50%, +2 pour délai supplémentaire)
    'duration',     # Durée de l'événement (en pas de temps)
    'description',  # Description de l'événement (pour logs ou suivi)
])

class EventManager:
    def __init__(self, events):
        # Trier les événements par ordre chronologique
        self.events = sorted(events, key=lambda e: e.time)
        self.active_events = []     # Événements en cours (avec temps restant)
        self.current_time = 0

    def step(self, time, system_state):
        """Avance la simulation d'une unité de temps en appliquant les perturbations actives et en déclenchant les nouvelles."""
        self.current_time = time
        # 1. Activer les nouveaux événements dont le temps de déclenchement est arrivé
        for event in list(self.events):
            if event.time == time:
                self.active_events.append({'event': event, 'time_left': event.duration})
                self.events.remove(event)
                # (Optionnel: journalisation d'un événement déclenché)

        # 2. Appliquer les effets de toutes les perturbations actives sur l'état du système
        for active in list(self.active_events):
            event = active['event']
            if event.event_type == "panne":
                # Panne machine/site: arrêt total (magnitude=1.0) ou réduction de capacité
                if event.magnitude == 1.0:
                    system_state['capacity'][event.target] = 0
                else:
                    system_state['capacity'][event.target] = system_state['capacity_nominal'][event.target] * (1 - event.magnitude)
            elif event.event_type == "rupture_fournisseur":
                # Rupture de matière première: plus de stock disponible pour la ressource ciblée
                system_state['supply'][event.target] = 0
            elif event.event_type == "retard":
                # Retard fournisseur: on augmente le délai de livraison associé à la ressource
                system_state['delays'][event.target] = system_state['delays'].get(event.target, 0) + event.magnitude
            # Réduire d'une unité le temps restant de l'événement
            active['time_left'] -= 1

        # 3. Désactiver les événements expirés et rétablir l’état nominal après leur fin
        for active in list(self.active_events):
            if active['time_left'] <= 0:
                event = active['event']
                # Rétablir les valeurs nominales à la fin de l'événement
                if event.event_type == "panne":
                    system_state['capacity'][event.target] = system_state['capacity_nominal'][event.target]
                elif event.event_type == "rupture_fournisseur":
                    system_state['supply'][event.target] = system_state['supply_nominal'][event.target]
                elif event.event_type == "retard":
                    # On réduit le délai supplémentaire ajouté (retour à l'état initial)
                    system_state['delays'][event.target] -= event.magnitude
                self.active_events.remove(active)
