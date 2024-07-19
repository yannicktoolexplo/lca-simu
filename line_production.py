import random
import simpy

# -------------------------------------------------
# Parameters

# Working hours per day
hours = 8

# Number of business days
days = 23

# Total working time (hours)
total_time = hours * days

# -------------------------------------------------
# Model for 1 factory line

# Containers

# Aluminium container
aluminium_capacity = 400
initial_aluminium = 100

# Foam container
foam_capacity = 400
initial_foam = 100

# Fabric container
fabric_capacity = 400
initial_fabric = 100

# Paint container
frame_pre_paint_capacity = 60
armrest_pre_paint_capacity = 60
frame_post_paint_capacity = 120
armrest_post_paint_capacity = 120
paint_capacity = 200
initial_paint = 100

# Dispatch container
dispatch_capacity = 500

# Number of employees per activity

# Frame assembly
num_frame = 2
mean_frame = 1
std_frame = 0.1

# Armrest assembly
num_armrest = 2
mean_armrest = 1
std_armrest = 0.2

# Painting
num_paint = 2
mean_paint = 2
std_paint = 0.3

# Final assembly
num_ensam = 5
mean_ensam = 1
std_ensam = 0.2

# Critical stock levels (based on 1 business day greater than supplier delivery time)

aluminium_critial_stock = (((8 / mean_frame) * num_frame +
                           (8 / mean_armrest) * num_armrest) * 1)  # 2 days to deliver + 1 margin

foam_critical_stock = (((8 / mean_frame) * num_frame +
                       (8 / mean_armrest) * num_armrest) * 1)  # 1 day to deliver + 1 margin
fabric_critical_stock = (((8 / mean_frame) * num_frame +
                         (8 / mean_armrest) * num_armrest) * 1)  # 1 day à deliver + 1 margin

paint_critical_stock = (8 / mean_paint) * num_paint  # 1 day to deliver + 1 margin

# -------------------------------------------------

class SeatFactory:
    def __init__(self, env: simpy.Environment):
        self.env = env
        self.init_containers()
        self.init_controls()

        self.seats_made = 0
        self.data1 = []
        self.data2 = []
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

    def init_containers(self):
        self.aluminium = simpy.Container(self.env, capacity=aluminium_capacity, init=initial_aluminium)
        self.foam = simpy.Container(self.env, capacity=foam_capacity, init=initial_foam)
        self.fabric = simpy.Container(self.env, capacity=fabric_capacity, init=initial_fabric)
        self.paint = simpy.Container(self.env, capacity=paint_capacity, init=initial_paint)
        self.dispatch = simpy.Container(self.env, capacity=dispatch_capacity, init=2)

        self.frame_pre_paint = simpy.Container(self.env, capacity=frame_pre_paint_capacity, init=5)
        self.armrest_pre_paint = simpy.Container(self.env, capacity=armrest_pre_paint_capacity, init=2)
        self.frame_post_paint = simpy.Container(self.env, capacity=frame_post_paint_capacity, init=2)
        self.armrest_post_paint = simpy.Container(self.env, capacity=armrest_post_paint_capacity, init=2)

    def init_controls(self):
        self.env.process(self.stock_control(self.aluminium, aluminium_critial_stock, 100, 8, 'aluminium'))
        self.env.process(self.stock_control(self.foam, foam_critical_stock, 100, 12, 'foam'))
        self.env.process(self.stock_control(self.fabric, fabric_critical_stock, 100, 10, 'fabric'))
        self.env.process(self.stock_control(self.paint, paint_critical_stock, 50, 9, 'paint'))
        self.env.process(self.dispatch_seats_control())

    def stock_control(self, container, critical_level, refill_amount, delivery_time, name):
        while True:
            if container.level <= critical_level:
                yield self.env.timeout(delivery_time)
                yield container.put(refill_amount)
                yield self.env.timeout(8)
            else:
                yield self.env.timeout(1)

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

            val2 = self.dispatch.level
            self.data2.append(val2)
            val1 = self.seats_made + self.dispatch.level
            self.data1.append(val1)
            self.conso_elec.append(val1 * 113.53)
            self.conso_eau.append(val1 * 31652.52)  # m3 world equivalent
            self.mineral_metal_used.append(val1 * 0.4525)  # equivalent kg antimoine
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
        frame_time = random.gauss(mean_frame, std_frame)
        yield env.timeout(frame_time)
        yield seat_factory.frame_pre_paint.put(1)
        seat_factory.frame_data.append(seat_factory.frame_pre_paint.level)
        seat_factory.time_frame.append(env.now / 8)  # Update frame time vector

def armrest_maker(env, seat_factory):
    while True:
        yield seat_factory.aluminium.get(0.1)
        yield seat_factory.foam.get(0.1)
        yield seat_factory.fabric.get(0.1)
        armrest_time = random.gauss(mean_armrest, std_armrest)
        yield env.timeout(armrest_time)
        yield seat_factory.armrest_pre_paint.put(2)
        seat_factory.armrest_data.append(seat_factory.armrest_pre_paint.level)
        seat_factory.time_armrest.append(env.now / 8)  # Update armrest time vector

def painter(env, seat_factory):
    while True:
        yield seat_factory.paint.get(1)
        yield seat_factory.frame_pre_paint.get(2)
        yield seat_factory.armrest_pre_paint.get(4)
        paint_time = random.gauss(mean_paint, std_paint)
        yield env.timeout(paint_time)
        yield seat_factory.frame_post_paint.put(2)
        yield seat_factory.armrest_post_paint.put(4)

def assembler(env, seat_factory):
    while True:
        yield seat_factory.frame_post_paint.get(1)
        yield seat_factory.armrest_post_paint.get(2)
        assembling_time = max(random.gauss(mean_ensam, std_ensam), 1)
        yield env.timeout(assembling_time)
        yield seat_factory.dispatch.put(1)

# Initialize the simulation environment
env = simpy.Environment()
seat_factory = SeatFactory(env)

env.process(process_generator(env, seat_factory, num_frame, frame_maker))
env.process(process_generator(env, seat_factory, num_armrest, armrest_maker))
env.process(process_generator(env, seat_factory, num_paint, painter))
env.process(process_generator(env, seat_factory, num_ensam, assembler))

# Run the simulation
env.run(until=total_time)

# Print results
print(f'Total seats made: {seat_factory.seats_made + seat_factory.dispatch.level}')

# Data collection functions
def get_data():
    return {
        'Seat Stock': (seat_factory.time, seat_factory.data2),
        'Frame Data': (seat_factory.time_frame, seat_factory.frame_data),
        'Armrest Data': (seat_factory.time_armrest, seat_factory.armrest_data),
        'Foam Stock': (seat_factory.time_foam, seat_factory.foam_stock_data),
        'Fabric Stock': (seat_factory.time_fabric, seat_factory.fabric_stock_data),
        'Paint Stock': (seat_factory.time_paint, seat_factory.paint_stock_data),
        'Total Seats made': (seat_factory.time, seat_factory.data1),
        'Aluminium Stock': (seat_factory.time_aluminium, seat_factory.aluminium_stock_data)
    }

def get_data_enviro():
    return {
        'Electrical Consumption': (seat_factory.time, seat_factory.conso_elec),
        'Water Consumption': (seat_factory.time, seat_factory.conso_eau),
        'Mineral and Metal Used': (seat_factory.time, seat_factory.mineral_metal_used),
    }
