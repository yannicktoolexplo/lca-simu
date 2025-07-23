import random
import simpy
from supply.supply_engine import manage_fixed_supply
from event_engine import EventManager

class ProductionLine:
    def __init__(self, env, config, seat_weight=130):
        self.env = env
        self.config = config
        self.init_containers()
        self.init_controls(seat_weight)
        self.init_data_tracking()
        # 🔻 Ajout des drapeaux de perturbation
        self.active = True  # indique si la ligne tourne normalement
        self.supply_enabled = {
            'aluminium': True,
            'foam': True,
            'fabric': True,
            'paint': True
        }
        self.start_production_processes()


    def init_containers(self):
        # Initialiser les containers avec les capacités et stocks initiaux configurables
        self.aluminium = simpy.Container(self.env, capacity=self.config['aluminium_capacity'], init=self.config['initial_aluminium'])
        self.foam = simpy.Container(self.env, capacity=self.config['foam_capacity'], init=self.config['initial_foam'])
        self.fabric = simpy.Container(self.env, capacity=self.config['fabric_capacity'], init=self.config['initial_fabric'])
        self.paint = simpy.Container(self.env, capacity=self.config['paint_capacity'], init=self.config['initial_paint'])
        self.dispatch = simpy.Container(self.env, capacity=self.config['dispatch_capacity'], init=2)
        self.frame_pre_paint = simpy.Container(self.env, capacity=self.config['frame_pre_paint_capacity'], init=5)
        self.armrest_pre_paint = simpy.Container(self.env, capacity=self.config['armrest_pre_paint_capacity'], init=2)
        self.frame_post_paint = simpy.Container(self.env, capacity=self.config['frame_post_paint_capacity'], init=2)
        self.armrest_post_paint = simpy.Container(self.env, capacity=self.config['armrest_post_paint_capacity'], init=2)

    def init_controls(self, seat_weight):
        # Contrôle des stocks
        supply = manage_fixed_supply(self.config['location'], seat_weight)
        self.env.process(self.stock_control(self.aluminium, self.config['aluminium_critial_stock'],  supply['aluminium']['quantity'],  supply['aluminium']['delivery_time'], 'aluminium'))
        self.env.process(self.stock_control(self.foam, self.config['foam_critical_stock'], supply['polymers']['quantity'], supply['polymers']['delivery_time'], 'foam'))
        self.env.process(self.stock_control(self.fabric, self.config['fabric_critical_stock'], supply['fabric']['quantity'], supply['fabric']['delivery_time'], 'fabric'))
        self.env.process(self.stock_control(self.paint, self.config['paint_critical_stock'],  supply['paint']['quantity'], supply['paint']['delivery_time'], 'paint'))
        self.env.process(self.dispatch_seats_control())

    def init_data_tracking(self):
        self.seats_made = 0
        self.seats_made_data = []
        self.seat_stock_data = []
        self.conso_elec = []
        self.conso_eau = []
        self.mineral_metal_used = []
        self.frame_data = []
        self.armrest_data = []
        self.time_frame = []
        self.time_armrest = []
        self.aluminium_stock_data = []
        self.foam_stock_data = []
        self.fabric_stock_data = []
        self.paint_stock_data = []
        self.time_aluminium = []
        self.time_foam = []
        self.time_fabric = []
        self.time_paint = []
        self.time = []

    def start_production_processes(self):
        # Démarrer les processus de fabrication
        self.env.process(self.process_generator(self.env, self.config['num_frame'], self.frame_maker))
        self.env.process(self.process_generator(self.env, self.config['num_armrest'], self.armrest_maker))
        self.env.process(self.process_generator(self.env, self.config['num_paint'], self.painter))
        self.env.process(self.process_generator(self.env, self.config['num_ensam'], self.assembler))

    def process_generator(self, env, num, process_func):
        for _ in range(num):
            env.process(process_func(env))
            yield env.timeout(0)

    def frame_maker(self, env):
        while True:
            # ➡️ Si la ligne est en panne, on attend 1h avant de re-tester
            if not self.active:
                yield env.timeout(1)   # pause d'un pas de temps (1 heure) pendant la panne
                continue
            # Reprise du fonctionnement normal si self.active = True)
            yield self.aluminium.get(1)
            yield self.foam.get(1)
            yield self.fabric.get(1)
            frame_time = random.gauss(self.config['mean_frame'], self.config['std_frame'])
            yield env.timeout(frame_time)
            yield self.frame_pre_paint.put(1)
            self.frame_data.append(self.frame_pre_paint.level)
            self.time_frame.append(env.now / 8)  # Update frame time vector

    def armrest_maker(self, env):
        while True:
            yield self.aluminium.get(0.1)
            yield self.foam.get(0.1)
            yield self.fabric.get(0.1)
            armrest_time = random.gauss(self.config['mean_armrest'], self.config['std_armrest'])
            yield env.timeout(armrest_time)
            yield self.armrest_pre_paint.put(2)
            self.armrest_data.append(self.armrest_pre_paint.level)
            self.time_armrest.append(env.now / 8)  # Update armrest time vector

    def painter(self, env):
        while True:
            yield self.paint.get(1)
            yield self.frame_pre_paint.get(2)
            yield self.armrest_pre_paint.get(4)
            paint_time = random.gauss(self.config['mean_paint'], self.config['std_paint'])
            yield env.timeout(paint_time)
            yield self.frame_post_paint.put(2)
            yield self.armrest_post_paint.put(4)

    def assembler(self, env):
        while True:
            yield self.frame_post_paint.get(1)
            yield self.armrest_post_paint.get(2)
            assembling_time = max(random.gauss(self.config['mean_ensam'], self.config['std_ensam']), 1)
            yield env.timeout(assembling_time)
            yield self.dispatch.put(1)

    def stock_control(self, container, critical_level, refill_amount, delivery_time, name):
        while True:
            # ➡️ Si la ressource est en rupture fournisseur, on suspend les réapprovisionnements
            if not self.supply_enabled.get(name, True):
                yield self.env.timeout(1)  # on attend 1h avant de re-vérifier
            elif container.level <= critical_level:
                yield self.env.timeout(delivery_time)
                yield container.put(refill_amount)
                yield self.env.timeout(8)
            else:
                yield self.env.timeout(1)

            # Collect stock data
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

    def dispatch_seats_control(self):
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

    def get_data(self):
        return {
            'Seat Stock': (self.time, self.seat_stock_data),
            'Frame Data': (self.time_frame, self.frame_data),
            'Armrest Data': (self.time_armrest, self.armrest_data),
            'Foam Stock': (self.time_foam, self.foam_stock_data),
            'Fabric Stock': (self.time_fabric, self.fabric_stock_data),
            'Paint Stock': (self.time_paint, self.paint_stock_data),
            'Total Seats made': (self.time, self.seats_made_data),
            'Aluminium Stock': (self.time_aluminium, self.aluminium_stock_data)
        }


    def get_data_enviro(self):
        return {
            'Electrical Consumption': (self.time, self.conso_elec),
            'Water Consumption': (self.time, self.conso_eau),
            'Mineral and Metal Used': (self.time, self.mineral_metal_used),
        }

def run_simulation(lines_config, seat_weight=130, events=None):
    env = simpy.Environment()
    production_lines = []

    for config in lines_config:
        line = ProductionLine(env, config, seat_weight)
        production_lines.append(line)

        # 🔻 Intégration du moteur d’événements
    if events:
        for event in events:
            if event.event_type == "panne":
                env.process(handle_breakdown_event(env, event, production_lines))
            elif event.event_type == "rupture_fournisseur":
                env.process(handle_supply_event(env, event, production_lines))
            elif event.event_type == "retard":
                # env.process(handle_delay_event(env, event, production_lines))
                pass
    # Lancement de la simulation jusqu'à la fin de l'horizon temporel
    env.run(until=max(cfg['total_time'] for cfg in lines_config))

    all_production_data = [line.get_data() for line in production_lines]
    all_enviro_data = [line.get_data_enviro() for line in production_lines]

    return all_production_data, all_enviro_data

def handle_breakdown_event(env, event, production_lines):
    # Arrêt complet d'un site de production pendant event.duration heures
    yield env.timeout(event.time)
    print(f"⚡ [t={env.now}] Panne sur site {event.target} : arrêt de la production ({event.description})")
    # Désactiver la ligne ciblée
    for line in production_lines:
        if line.config['location'] == event.target:
            line.active = False
    # Maintenir la panne pendant la durée spécifiée
    yield env.timeout(event.duration)
    # Fin de la panne, on réactive la ligne
    for line in production_lines:
        if line.config['location'] == event.target:
            line.active = True
    print(f"✅ [t={env.now}] Fin de la panne sur {event.target}, reprise de la production.")

def handle_supply_event(env, event, production_lines):
    # Rupture d'une ressource (matière première) pendant event.duration
    yield env.timeout(event.time)
    print(f"⚡ [t={env.now}] Rupture de fourniture : {event.target} indisponible ({event.description})")
    # Désactiver l'approvisionnement de la ressource sur tous les sites
    for line in production_lines:
        if event.target in line.supply_enabled:
            line.supply_enabled[event.target] = False
            # Optionnel : vider le stock actuel pour simuler rupture immédiate
            if line.__dict__.get(event.target) is not None:
                # Retire tout le contenu du container correspondant (ex: aluminium)
                amount = line.__dict__[event.target].level
                if amount > 0:
                    yield line.__dict__[event.target].get(amount)
    # Durée de la perturbation
    yield env.timeout(event.duration)
    # Rétablissement de l'approvisionnement
    for line in production_lines:
        if event.target in line.supply_enabled:
            line.supply_enabled[event.target] = True
    print(f"✅ [t={env.now}] Fin de rupture : {event.target} de nouveau approvisionné.")
