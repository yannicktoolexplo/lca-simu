import simpy
import random
from supply.supply_engine import manage_fixed_supply

class ProductionLine:
    def __init__(self, env, config, seat_weight=130):
        """Initialise une ligne de production SimPy avec son environnement et ses ressources."""
        self.env = env
        self.config = config
        self.seat_weight = seat_weight
        self._init_containers()
        self._init_tracking()
        self.active = True
        self.supply_enabled = {mat: True for mat in ['aluminium', 'foam', 'fabric', 'paint']}
        self._launch_processes()

    def _init_containers(self):
        c = self.config
        # Stocks matières premières et postes de production
        self.aluminium = simpy.Container(self.env, c['aluminium_capacity'], init=c['initial_aluminium'])
        self.foam = simpy.Container(self.env, c['foam_capacity'], init=c['initial_foam'])
        self.fabric = simpy.Container(self.env, c['fabric_capacity'], init=c['initial_fabric'])
        self.paint = simpy.Container(self.env, c['paint_capacity'], init=c['initial_paint'])
        self.dispatch = simpy.Container(self.env, c['dispatch_capacity'], init=2)
        self.frame_pre_paint = simpy.Container(self.env, c['frame_pre_paint_capacity'], init=5)
        self.armrest_pre_paint = simpy.Container(self.env, c['armrest_pre_paint_capacity'], init=2)
        self.frame_post_paint = simpy.Container(self.env, c['frame_post_paint_capacity'], init=2)
        self.armrest_post_paint = simpy.Container(self.env, c['armrest_post_paint_capacity'], init=2)

    def _init_tracking(self):
        # Historique pour monitoring
        self.seats_made = 0
        self.seats_made_data = []
        self.seat_stock_data = []
        self.aluminium_stock_data, self.foam_stock_data = [], []
        self.fabric_stock_data, self.paint_stock_data = [], []
        self.frame_data, self.armrest_data = [], []
        self.time, self.time_aluminium = [], []
        self.time_foam, self.time_fabric = [], []
        self.time_paint, self.time_frame, self.time_armrest = [], [], []

    def _launch_processes(self):
        cfg = self.config
        env = self.env
        # Approvisionnements, contrôles de stocks
        supply_plan = manage_fixed_supply(cfg['location'], self.seat_weight)
        env.process(self._stock_control(self.aluminium, cfg.get('aluminium_critical_stock', 0),
                                       supply_plan['aluminium']['quantity'], supply_plan['aluminium']['delivery_time'], 'aluminium'))
        env.process(self._stock_control(self.foam, cfg.get('foam_critical_stock', 0),
                                       supply_plan['polymers']['quantity'], supply_plan['polymers']['delivery_time'], 'foam'))
        env.process(self._stock_control(self.fabric, cfg.get('fabric_critical_stock', 0),
                                       supply_plan['fabric']['quantity'], supply_plan['fabric']['delivery_time'], 'fabric'))
        env.process(self._stock_control(self.paint, cfg.get('paint_critical_stock', 0),
                                       supply_plan['paint']['quantity'], supply_plan['paint']['delivery_time'], 'paint'))
        env.process(self._dispatch_seats_control())
        # Processus de production
        for _ in range(cfg['num_frame']):
            env.process(self._frame_maker())
        for _ in range(cfg['num_armrest']):
            env.process(self._armrest_maker())
        for _ in range(cfg['num_paint']):
            env.process(self._painter())
        for _ in range(cfg['num_ensam']):
            env.process(self._assembler())

    # --- Processus de production ---

    def _frame_maker(self):
        while True:
            if not self.active:
                yield self.env.timeout(1)
                continue
            yield self.aluminium.get(1)
            yield self.foam.get(1)
            yield self.fabric.get(1)
            t = random.gauss(self.config['mean_frame'], self.config['std_frame'])
            yield self.env.timeout(t)
            yield self.frame_pre_paint.put(1)
            self.frame_data.append(self.frame_pre_paint.level)
            self.time_frame.append(self.env.now / 8)

    def _armrest_maker(self):
        while True:
            yield self.aluminium.get(0.1)
            yield self.foam.get(0.1)
            yield self.fabric.get(0.1)
            t = random.gauss(self.config['mean_armrest'], self.config['std_armrest'])
            yield self.env.timeout(t)
            yield self.armrest_pre_paint.put(2)
            self.armrest_data.append(self.armrest_pre_paint.level)
            self.time_armrest.append(self.env.now / 8)

    def _painter(self):
        while True:
            yield self.paint.get(1)
            yield self.frame_pre_paint.get(2)
            yield self.armrest_pre_paint.get(4)
            t = random.gauss(self.config['mean_paint'], self.config['std_paint'])
            yield self.env.timeout(t)
            yield self.frame_post_paint.put(2)
            yield self.armrest_post_paint.put(4)

    def _assembler(self):
        while True:
            yield self.frame_post_paint.get(1)
            yield self.armrest_post_paint.get(2)
            t = max(random.gauss(self.config['mean_ensam'], self.config['std_ensam']), 1)
            yield self.env.timeout(t)
            yield self.dispatch.put(1)

    def _stock_control(self, container, critical_level, refill_amount, delivery_time, name):
        while True:
            if not self.supply_enabled.get(name, True):
                yield self.env.timeout(1)
            elif container.level <= critical_level:
                yield self.env.timeout(delivery_time)
                yield container.put(refill_amount)
                yield self.env.timeout(8)
            else:
                yield self.env.timeout(1)
            # Stock tracking (échantillonnage)
            if name == 'aluminium':
                self.aluminium_stock_data.append(container.level)
                self.time_aluminium.append(self.env.now / 8)
            elif name == 'foam':
                self.foam_stock_data.append(container.level)
                self.time_foam.append(self.env.now / 8)
            elif name == 'fabric':
                self.fabric_stock_data.append(container.level)
                self.time_fabric.append(self.env.now / 8)
            elif name == 'paint':
                self.paint_stock_data.append(container.level)
                self.time_paint.append(self.env.now / 8)

    def _dispatch_seats_control(self):
        while True:
            if self.dispatch.level >= 50:
                yield self.env.timeout(4)
                self.seats_made += self.dispatch.level
                yield self.env.timeout(1)
                yield self.dispatch.get(self.dispatch.level)
                yield self.env.timeout(8)
            else:
                yield self.env.timeout(1)
            self.seat_stock_data.append(self.dispatch.level)
            self.seats_made_data.append(self.seats_made + self.dispatch.level)
            self.time.append(self.env.now / 8)

    # --- Fonctions d'export de données ---
    def get_data(self):
        return {
            'Seat Stock': (self.time, self.seat_stock_data),
            'Frame Data': (self.time_frame, self.frame_data),
            'Armrest Data': (self.time_armrest, self.armrest_data),
            'Total Seats made': (self.time, self.seats_made_data),
            'Aluminium Stock': (self.time_aluminium, self.aluminium_stock_data),
            'Foam Stock': (self.time_foam, self.foam_stock_data),
            'Fabric Stock': (self.time_fabric, self.fabric_stock_data),
            'Paint Stock': (self.time_paint, self.paint_stock_data)
        }

    def get_data_enviro(self):
        # (Placeholder pour les variables environnementales)
        return {}

def run_simulation(lines_config, seat_weight=130, events=None):
    """
    Simule l'ensemble des lignes de production sur la période définie, avec gestion d'événements.
    :param lines_config: Liste des configurations de lignes (dictionnaires)
    :param seat_weight: Poids du siège pour les calculs de besoins matières
    :param events: Liste d'événements à injecter (ou None)
    :return: (all_production_data, all_enviro_data)
    """
    env = simpy.Environment()
    lines = []
    for cfg in lines_config:
        line = ProductionLine(env, cfg, seat_weight)
        lines.append(line)
    # Gestion des perturbations
    if events:
        for event in events:
            if event.event_type == "panne":
                env.process(_handle_breakdown_event(env, event, lines))
            elif event.event_type == "rupture_fournisseur":
                env.process(_handle_supply_event(env, event, lines))
            elif event.event_type == "retard":
                env.process(_handle_delay_event(env, event, lines))
    # Exécution jusqu'à la fin du planning
    env.run(until=max(cfg['total_time'] for cfg in lines_config))
    all_production_data = [line.get_data() for line in lines]
    all_enviro_data = [line.get_data_enviro() for line in lines]
    return all_production_data, all_enviro_data

# --- Handlers pour événements ---

def _handle_breakdown_event(env, event, lines):
    yield env.timeout(event.time)
    for line in lines:
        if line.config['location'] == event.target:
            line.active = False
    yield env.timeout(event.duration)
    for line in lines:
        if line.config['location'] == event.target:
            line.active = True

def _handle_supply_event(env, event, lines):
    yield env.timeout(event.time)
    for line in lines:
        if event.target in line.supply_enabled:
            line.supply_enabled[event.target] = False
            # (Optionnel) vider stock immédiatement
            if hasattr(line, event.target):
                container = getattr(line, event.target)
                if container.level > 0:
                    yield container.get(container.level)
    yield env.timeout(event.duration)
    for line in lines:
        if event.target in line.supply_enabled:
            line.supply_enabled[event.target] = True

def _handle_delay_event(env, event, lines):
    # (Exemple : bloque l’approvisionnement d’un composant pendant event.duration)
    yield env.timeout(event.time)
    for line in lines:
        if event.target in line.supply_enabled:
            line.supply_enabled[event.target] = False
    yield env.timeout(event.duration)
    for line in lines:
        if event.target in line.supply_enabled:
            line.supply_enabled[event.target] = True
