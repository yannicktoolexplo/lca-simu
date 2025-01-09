import random
import simpy

class FactoryConfig:
     def __init__(self, hours=8, days=23, initial_aluminium=100, initial_foam=100, initial_fabric=100, initial_paint=100):
        self.hours = hours
        self.days = days
        self.total_time = self.hours * self.days

        # Containers capacities
        self.aluminium_capacity = 400
        self.initial_aluminium = initial_aluminium
        self.foam_capacity = 400
        self.initial_foam = initial_foam
        self.fabric_capacity = 400
        self.initial_fabric = initial_fabric
        self.paint_capacity = 200
        self.initial_paint = initial_paint
        self.dispatch_capacity = 500

        # Other capacities
        self.frame_pre_paint_capacity = 60
        self.armrest_pre_paint_capacity = 60
        self.frame_post_paint_capacity = 120
        self.armrest_post_paint_capacity = 120

        # Number of employees per activity
        self.num_frame = 2
        self.mean_frame = 1
        self.std_frame = 0.1
        self.num_armrest = 2
        self.mean_armrest = 1
        self.std_armrest = 0.2
        self.num_paint = 2
        self.mean_paint = 2
        self.std_paint = 0.3
        self.num_ensam = 5
        self.mean_ensam = 1
        self.std_ensam = 0.2

        # Critical stock levels (based on 1 business day greater than supplier delivery time)
        self.aluminium_critial_stock = (((8 / self.mean_frame) * self.num_frame +
                                        (8 / self.mean_armrest) * self.num_armrest) * 1)  # 2 days to deliver + 1 margin
        self.foam_critical_stock = (((8 / self.mean_frame) * self.num_frame +
                                    (8 / self.mean_armrest) * self.num_armrest) * 1)  # 1 day to deliver + 1 margin
        self.fabric_critical_stock = (((8 / self.mean_frame) * self.num_frame +
                                      (8 / self.mean_armrest) * self.num_armrest) * 1)  # 1 day to deliver + 1 margin
        self.paint_critical_stock = (8 / self.mean_paint) * self.num_paint  # 1 day to deliver + 1 margin

# Factory Class
class SeatFactory:
    def __init__(self, env, config):
        self.env = env
        self.config = config
        self.init_containers()
        self.init_controls()
        self.init_data_tracking()

    def init_containers(self):
        self.aluminium = simpy.Container(self.env, capacity=self.config.aluminium_capacity, init=self.config.initial_aluminium)
        self.foam = simpy.Container(self.env, capacity=self.config.foam_capacity, init=self.config.initial_foam)
        self.fabric = simpy.Container(self.env, capacity=self.config.fabric_capacity, init=self.config.initial_fabric)
        self.paint = simpy.Container(self.env, capacity=self.config.paint_capacity, init=self.config.initial_paint)
        self.dispatch = simpy.Container(self.env, capacity=self.config.dispatch_capacity, init=2)
        self.frame_pre_paint = simpy.Container(self.env, capacity=self.config.frame_pre_paint_capacity, init=5)
        self.armrest_pre_paint = simpy.Container(self.env, capacity=self.config.armrest_pre_paint_capacity, init=2)
        self.frame_post_paint = simpy.Container(self.env, capacity=self.config.frame_post_paint_capacity, init=2)
        self.armrest_post_paint = simpy.Container(self.env, capacity=self.config.armrest_post_paint_capacity, init=2)

    def init_controls(self):
        self.env.process(self.stock_control(self.aluminium, self.config.aluminium_critial_stock, 100, 8, 'aluminium'))
        self.env.process(self.stock_control(self.foam, self.config.foam_critical_stock, 100, 12, 'foam'))
        self.env.process(self.stock_control(self.fabric, self.config.fabric_critical_stock, 100, 10, 'fabric'))
        self.env.process(self.stock_control(self.paint, self.config.paint_critical_stock, 50, 9, 'paint'))
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

    def stock_control(self, container, critical_level, refill_amount, delivery_time, name):
        while True:
            if container.level <= critical_level:
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

def process_generator(env, seat_factory, num, process_func):
    for _ in range(num):
        env.process(process_func(env, seat_factory))
        yield env.timeout(0)

def frame_maker(env, seat_factory):
    while True:
        yield seat_factory.aluminium.get(1)
        yield seat_factory.foam.get(1)
        yield seat_factory.fabric.get(1)
        frame_time = random.gauss(seat_factory.config.mean_frame, seat_factory.config.std_frame)
        yield env.timeout(frame_time)
        yield seat_factory.frame_pre_paint.put(1)
        seat_factory.frame_data.append(seat_factory.frame_pre_paint.level)
        seat_factory.time_frame.append(env.now / 8)  # Update frame time vector

def armrest_maker(env, seat_factory):
    while True:
        yield seat_factory.aluminium.get(0.1)
        yield seat_factory.foam.get(0.1)
        yield seat_factory.fabric.get(0.1)
        armrest_time = random.gauss(seat_factory.config.mean_armrest, seat_factory.config.std_armrest)
        yield env.timeout(armrest_time)
        yield seat_factory.armrest_pre_paint.put(2)
        seat_factory.armrest_data.append(seat_factory.armrest_pre_paint.level)
        seat_factory.time_armrest.append(env.now / 8)  # Update armrest time vector

def painter(env, seat_factory):
    while True:
        yield seat_factory.paint.get(1)
        yield seat_factory.frame_pre_paint.get(2)
        yield seat_factory.armrest_pre_paint.get(4)
        paint_time = random.gauss(seat_factory.config.mean_paint, seat_factory.config.std_paint)
        yield env.timeout(paint_time)
        yield seat_factory.frame_post_paint.put(2)
        yield seat_factory.armrest_post_paint.put(4)

def assembler(env, seat_factory):
    while True:
        yield seat_factory.frame_post_paint.get(1)
        yield seat_factory.armrest_post_paint.get(2)
        assembling_time = max(random.gauss(seat_factory.config.mean_ensam, seat_factory.config.std_ensam), 1)
        yield env.timeout(assembling_time)
        yield seat_factory.dispatch.put(1)

def run_simulation(config):
    env = simpy.Environment()
    seat_factory = SeatFactory(env, config)

    env.process(process_generator(env, seat_factory, config.num_frame, frame_maker))
    env.process(process_generator(env, seat_factory, config.num_armrest, armrest_maker))
    env.process(process_generator(env, seat_factory, config.num_paint, painter))
    env.process(process_generator(env, seat_factory, config.num_ensam, assembler))

    env.run(until=config.total_time)

    print(f'Total seats made: {seat_factory.seats_made + seat_factory.dispatch.level}')
    return seat_factory

# Data collection functions
def get_data(seat_factory):
    return {
        'Seat Stock': (seat_factory.time, seat_factory.seat_stock_data),
        'Frame Data': (seat_factory.time_frame, seat_factory.frame_data),
        'Armrest Data': (seat_factory.time_armrest, seat_factory.armrest_data),
        'Foam Stock': (seat_factory.time_foam, seat_factory.foam_stock_data),
        'Fabric Stock': (seat_factory.time_fabric, seat_factory.fabric_stock_data),
        'Paint Stock': (seat_factory.time_paint, seat_factory.paint_stock_data),
        'Total Seats made': (seat_factory.time, seat_factory.seats_made_data),
        'Aluminium Stock': (seat_factory.time_aluminium, seat_factory.aluminium_stock_data)
    }

def get_data_enviro(seat_factory):
    return {
        'Electrical Consumption': (seat_factory.time, seat_factory.conso_elec),
        'Water Consumption': (seat_factory.time, seat_factory.conso_eau),
        'Mineral and Metal Used': (seat_factory.time, seat_factory.mineral_metal_used),
    }

# Main execution
if __name__ == "__main__":
    config = FactoryConfig()
    seat_factory = run_simulation(config)