import random
import simpy

# Initialize variables for tracking simulation data
seats_made = 0
val1 = 0
val2 = 0
data1 = []
conso_elec = []
conso_eau = []  # m3 world equivalent
mineral_metal_used = []  # equivalent kg antimoine
data2 = []
frame_data = []
armrest_data = []
time_frame = []
time_armrest = []
aluminium_stock_data = []
foam_stock_data = []
fabric_stock_data = []
paint_stock_data = []
time_aluminium = []
time_foam = []
time_fabric = []
time_paint = []
time = []

print(f'STARTING SIMULATION')
print(f'----------------------------------')

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
aluminium_capacity = 600
initial_aluminium = 100

# Foam container
foam_capacity = 400
initial_foam = 100

# Fabric container
fabric_capacity = 300
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
                         (8 / mean_armrest) * num_armrest) * 1)  # 1 day to deliver + 1 margin

paint_critical_stock = (8 / mean_paint) * num_paint  # 1 day to deliver + 1 margin





#-------------------------------------------------

class seat_Factory:
    def __init__(self, env):
        """
        Initialize the seat factory with containers for each material and process control.
        """
        self.aluminium = simpy.Container(env, capacity=aluminium_capacity, init=initial_aluminium)
        self.aluminium_control = env.process(self.aluminium_stock_control(env))

        self.foam = simpy.Container(env, capacity=foam_capacity, init=initial_foam)
        self.foam_control = env.process(self.foam_stock_control(env))

        self.fabric = simpy.Container(env, capacity=fabric_capacity, init=initial_fabric)
        self.fabric_control = env.process(self.fabric_stock_control(env))

        self.frame_pre_paint = simpy.Container(env, capacity=frame_pre_paint_capacity, init=5)
        self.armrest_pre_paint = simpy.Container(env, capacity=armrest_pre_paint_capacity, init=2)
        self.frame_post_paint = simpy.Container(env, capacity=frame_post_paint_capacity, init=2)
        self.armrest_post_paint = simpy.Container(env, capacity=armrest_post_paint_capacity, init=2)

        self.paint = simpy.Container(env, capacity=paint_capacity, init=initial_paint)
        self.paint_control = env.process(self.paint_stock_control(env))

        self.dispatch = simpy.Container(env, capacity=dispatch_capacity, init=2)
        self.dispatch_control = env.process(self.dispatch_seats_control(env))

    def aluminium_stock_control(self, env):
        """
        Control the aluminium stock and call the supplier when the stock is below the critical level.
        """
        yield env.timeout(0)
        while True:
            if self.aluminium.level <= aluminium_critial_stock:
                # ... (existing code)
                yield env.timeout(8)
            else:
                yield env.timeout(1)

            aluminium_stock_data.append(self.aluminium.level)
            time_aluminium.append(env.now / 8)  # Update time vector for aluminium

    def foam_stock_control(self, env):
        """
        Control the foam stock and call the supplier when the stock is below the critical level.
        """
        yield env.timeout(0)
        while True:
            if self.foam.level <= foam_critical_stock:
                # ... (existing code)
                yield env.timeout(8)
            else:
                yield env.timeout(1)

            foam_stock_data.append(self.foam.level)
            time_foam.append(env.now / 8)  # Update time vector for foam

    def fabric_stock_control(self, env):
        """
        Control the fabric stock and call the supplier when the stock is below the critical level.
        """
        yield env.timeout(0)
        while True:
            if self.fabric.level <= fabric_critical_stock:
                # ... (existing code)
                yield env.timeout(8)
            else:
                yield env.timeout(1)

            fabric_stock_data.append(self.fabric.level)
            time_fabric.append(env.now / 8)  # Update time vector for fabric

    def paint_stock_control(self, env):
            """
            Monitor and manage the paint stock level. If the paint stock level is below or equal to the critical level,
            order more paint from the supplier.
            """
            yield env.timeout(0)
            while True:
                if self.paint.level <= paint_critical_stock:
                    # Wait for the supplier delivery time (9 hours)
                    yield env.timeout(9)
                    # Add paint to the stock (50 units)
                    yield self.paint.put(50)
                    # Wait for the unloading time (8 hours)
                    yield env.timeout(8)
                else:
                    # If the paint stock level is above the critical level, wait for 1 hour before checking again
                    yield env.timeout(1)

                # Update paint stock data and time vector
                paint_stock_data.append(self.paint.level)
                time_paint.append(env.now / 8)

    def dispatch_seats_control(self, env):
        """
        Monitor and manage the dispatch of seats. If there are 50 or more seats in the dispatch area,
        call the store to pick up the seats and update the related data.
        """
        global seats_made
        yield env.timeout(0)
        while True:
            if self.dispatch.level >= 50:
                # Wait for the store to arrive (4 hours)
                yield env.timeout(4)
                # Update the number of seats made
                seats_made += self.dispatch.level
                # Wait for the loading time (1 hour)
                yield env.timeout(1)
                # Remove the seats from the dispatch areaS
                yield self.dispatch.get(self.dispatch.level)
                # Wait for the store to leave (8 hours)
                yield env.timeout(8)
            else:
                # If there are less than 50 seats in the dispatch area, wait for 1 hour before checking again
                yield env.timeout(1)

            # Update data vectors for seats made, dispatch level, electrical consumption, water consumption,
            # mineral and metal used, and time
            val2 = self.dispatch.level
            data2.append(val2)
            val1 = seats_made + self.dispatch.level
            data1.append(val1)
            conso_elec.append(val1 * 113.53)
            conso_eau.append(val1 * 31652.52)  # m3 world equivalent
            mineral_metal_used.append(val1 * 0.4525)  # equivalent kg antimoine
            time.append(env.now / 8)


def frame_maker(env, seat_factory):
    """
    A continuous loop that simulates the frame making process in the seat factory.

    The function first retrieves the required materials (aluminium, foam, and fabric) from their respective
    containers. Then, it generates a random frame making time using a Gaussian distribution with the given
    mean and standard deviation. After the frame making process is complete, it places the frame in the
    pre-paint container and updates the frame data and time vectors.
    """
    while True:
        yield seat_factory.aluminium.get(1)
        yield seat_factory.foam.get(1)
        yield seat_factory.fabric.get(1)
        frame_time = random.gauss(mean_frame, std_frame)
        yield env.timeout(frame_time)
        yield seat_factory.frame_pre_paint.put(1)
        frame_data.append(seat_factory.frame_pre_paint.level)
        time_frame.append(env.now / 8)  # Update frame time vector

def armrest_maker(env, seat_factory):
    """
    A continuous loop that simulates the armrest making process in the seat factory.

    The function first retrieves the required materials (aluminium, foam, and fabric) from their respective
    containers. Then, it generates a random armrest making time using a Gaussian distribution with the given
    mean and standard deviation. After the armrest making process is complete, it places the armrests in the
    pre-paint container and updates the armrest data and time vectors.
    """
    while True:
        yield seat_factory.aluminium.get(0.1)
        yield seat_factory.foam.get(0.1)
        yield seat_factory.fabric.get(0.1)
        armrest_time = random.gauss(mean_armrest, std_armrest)
        yield env.timeout(armrest_time)
        yield seat_factory.armrest_pre_paint.put(2)
        armrest_data.append(seat_factory.armrest_pre_paint.level)
        time_armrest.append(env.now / 8)  # Update armrest time vector

def painter(env, seat_factory):
    """
    A continuous loop that simulates the painting process in the seat factory.

    The function first retrieves the required materials (paint, frames, and armrests) from their respective
    containers. Then, it generates a random painting time using a Gaussian distribution with the given
    mean and standard deviation. After the painting process is complete, it places the painted frames and
    armrests in the post-paint containers.
    """
    while True:
        yield seat_factory.paint.get(1)
        yield seat_factory.frame_pre_paint.get(2)
        yield seat_factory.armrest_pre_paint.get(4)
        paint_time = random.gauss(mean_paint, std_paint)
        yield env.timeout(paint_time)
        yield seat_factory.frame_post_paint.put(2)
        yield seat_factory.armrest_post_paint.put(4)

def assembler(env, seat_factory):
    """
    A continuous loop that simulates the seat assembly process in the seat factory.

    The function first retrieves the required materials (painted frames and armrests) from their respective
    containers. Then, it generates a random assembly time using a Gaussian distribution with the given
    mean and standard deviation. After the assembly process is complete, it places the assembled seat in the
    dispatch container.
    """
    while True:
        yield seat_factory.frame_post_paint.get(1)
        yield seat_factory.armrest_post_paint.get(2)
        assembling_time = max(random.gauss(mean_ensam, std_ensam), 1)
        yield env.timeout(assembling_time)
        yield seat_factory.dispatch.put(1)
        
        
# Generators

def frame_maker_gen(env, seat_factory):
    """
    A generator function that creates multiple frame maker processes in the seat factory.

    The function loops through the given number of frame maker processes, creates each process using the
    frame_maker function, and adds them to the environment.
    """
    for i in range(num_frame):
        env.process(frame_maker(env, seat_factory))
        yield env.timeout(0)

def armrest_maker_gen(env, seat_factory):
    """
    A generator function that creates multiple armrest maker processes in the seat factory.

    The function loops through the given number of armrest maker processes, creates each process using the
    armrest_maker function, and adds them to the environment.
    """
    for i in range(num_armrest):
        env.process(armrest_maker(env, seat_factory))
        yield env.timeout(0)

def painter_maker_gen(env, seat_factory):
    """
    A generator function that creates multiple painter processes in the seat factory.

    The function loops through the given number of painter processes, creates each process using the
    painter function, and adds them to the environment.
    """
    for i in range(num_paint):
        env.process(painter(env, seat_factory))
        yield env.timeout(0)

def assembler_maker_gen(env, seat_factory):
    """
    A generator function that creates multiple assembler processes in the seat factory.

    The function loops through the given number of assembler processes, creates each process using the
    assembler function, and adds them to the environment.
    """
    for i in range(num_ensam):
        env.process(assembler(env, seat_factory))
        yield env.timeout(0)

# Create the simulation environment and the seat factory, and start the generators
env = simpy.Environment()
seat_factory = seat_Factory(env)

frame_gen = env.process(frame_maker_gen(env, seat_factory))
armrest_gen = env.process(armrest_maker_gen(env, seat_factory))
painter_gen = env.process(painter_maker_gen(env, seat_factory))
assembler_gen = env.process(assembler_maker_gen(env, seat_factory))

# Run the simulation until the given total time
env.run(until=total_time)

# Print the results
print(f'----------------------------------')
print('total seats made: {0}'.format(seats_made + seat_factory.dispatch.level))
print(f'----------------------------------')
print(f'SIMULATION COMPLETED')

# Prepare the data to be returned
data = {
    'Seat Stock': (time, data2),
    'Frame Data': (time_frame, frame_data),
    'Armrest Data': (time_armrest, armrest_data),
    'Foam Stock': (time_foam, foam_stock_data),
    'Fabric Stock': (time_fabric, fabric_stock_data),
    'Paint Stock': (time_paint, paint_stock_data),
    'Total Seats made': (time, data1),
    'Electrical Consumption': (time, conso_elec),
    'Water Consumption': (time, conso_eau),
    'Mineral and Metal Used': (time, mineral_metal_used),
    'Aluminium Stock': (time_aluminium, aluminium_stock_data)
}

def get_data():
    """
    A function that returns the simulation data.
    """
    return data
