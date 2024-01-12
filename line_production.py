import random
import simpy


seats_made = 0
val1 = 0
val2 = 0
data1 = []
data2 = []
frame_data = []
armrest_data = []
time_frame = []
time_armrest = []
aluminium_stock_data = []
foam_stock_data = []
fabric_stock_data = []
time_aluminium = []
time_foam = []
time_fabric = []
time =[]
print(f'STARTING SIMULATION')
print(f'----------------------------------')

#-------------------------------------------------

#Parameters

#working hours
hours = 8

#business days
days = 23

#total working time (hours)
total_time = hours * days

#number of lines
lines_number_per_factory = 1
factories_number = 4
total_factory_lines = lines_number_per_factory * factories_number

#-------------------------------------------------
#model for 1 factory line

#containers
    #aluminium
aluminium_capacity = 600
initial_aluminium = 600

    #foam
foam_capacity = 300
initial_foam = 300

    #fabric
fabric_capacity = 300
initial_fabric = 300

    #paint
frame_pre_paint_capacity = 60
armrest_pre_paint_capacity = 60
frame_post_paint_capacity = 120
armrest_post_paint_capacity = 120
    
    #dispatch
dispatch_capacity = 500


#employees per activity
    #frame
num_frame = 2
mean_frame = 1
std_frame = 0.1

    #armrest
num_armrest = 2
mean_armrest = 1
std_armrest = 0.2

    #paint
num_paint = 3
mean_paint = 2
std_paint = 0.3

    #ensambling
num_ensam = 2
mean_ensam = 1
std_ensam = 0.2


#critical levels
    #critical stock should be 1 business day greater than supplier take to come
aluminium_critial_stock = (((8/mean_frame) * num_frame +
                      (8/mean_armrest) * num_armrest) * 3) #2 days to deliver + 1 marging

foam_critical_stock = (8/mean_ensam) * num_ensam * 2 #1 day to deliver + 1 marging
fabric_critical_stock = (8/mean_ensam) * num_ensam * 2 #1 day to deliver + 1 marging




#-------------------------------------------------

class seat_Factory:
    def __init__(self, env):
        self.aluminium = simpy.Container(env, capacity = aluminium_capacity, init = initial_aluminium)
        self.aluminium_control = env.process(self.aluminium_stock_control(env))
        self.foam = simpy.Container(env, capacity = foam_capacity, init = initial_foam)
        self.foam_control = env.process(self.foam_stock_control(env))
        self.fabric = simpy.Container(env, capacity = fabric_capacity, init = initial_fabric)
        self.fabric_control = env.process(self.fabric_stock_control(env))
        self.frame_pre_paint = simpy.Container(env, capacity = frame_pre_paint_capacity, init = 2)
        self.armrest_pre_paint = simpy.Container(env, capacity = armrest_pre_paint_capacity, init = 2)
        self.frame_post_paint = simpy.Container(env, capacity = frame_post_paint_capacity, init = 2)
        self.armrest_post_paint = simpy.Container(env, capacity = armrest_post_paint_capacity, init = 2)
        self.dispatch = simpy.Container(env ,capacity = dispatch_capacity, init = 2)
        self.dispatch_control = env.process(self.dispatch_seats_control(env))

        
    def aluminium_stock_control(self, env):
        yield env.timeout(0)
        while True:
            if self.aluminium.level <= aluminium_critial_stock:
                # print('aluminium stock bellow critical level ({0}) at day {1}, hour {2}'.format(
                #     self.aluminium.level, int(env.now/8), env.now % 8))
                # print('calling aluminium supplier')
                # print('----------------------------------')
                yield env.timeout(16)
                # print('aluminium supplier arrives at day {0}, hour {1}'.format(
                #     int(env.now/8), env.now % 8))
                yield self.aluminium.put(300)
                # print('new aluminium stock is {0}'.format(
                #     self.aluminium.level))
                # print('----------------------------------')
                yield env.timeout(8)
            else:
                yield env.timeout(1)
            
            aluminium_stock_data.append(self.aluminium.level)
            time_aluminium.append(env.now)  # Update time vector for aluminium

    
    def foam_stock_control(self, env):
        yield env.timeout(0)
        while True:
            if self.foam.level <= foam_critical_stock:
                # print('foam stock bellow critical level ({0}) at day {1}, hour {2}'.format(
                #     self.foam.level, int(env.now/8), env.now % 8))
                # print('calling foam supplier')
                # print('----------------------------------')
                yield env.timeout(9)
                # print('foam supplier arrives at day {0}, hour {1}'.format(
                #     int(env.now/8), env.now % 8))
                yield self.foam.put(50)
                # print('new foam stock is {0}'.format(
                #     self.foam.level))
                # print('----------------------------------')
                yield env.timeout(8)
            else:
                yield env.timeout(1)

            foam_stock_data.append(self.foam.level)
            time_foam.append(env.now)  # Update time vector for foam

    def fabric_stock_control(self, env):
        yield env.timeout(0)
        while True:
            if self.fabric.level <= fabric_critical_stock:
                # print('fabric stock bellow critical level ({0}) at day {1}, hour {2}'.format(
                    # self.fabric.level, int(env.now/8), env.now % 8))
                # print('calling fabric supplier')
                # print('----------------------------------')
                yield env.timeout(9)
                # print('fabric supplier arrives at day {0}, hour {1}'.format(
                    # int(env.now/8), env.now % 8))
                yield self.fabric.put(50)
                # print('new fabric stock is {0}'.format(
                    # self.fabric.level))
                # print('----------------------------------')
                yield env.timeout(8)
            else:
                yield env.timeout(1)

            fabric_stock_data.append(self.fabric.level)
            time_fabric.append(env.now)  # Update time vector for fabric   

    def dispatch_seats_control(self, env):
        global seats_made
        yield env.timeout(0)
        while True:
            if self.dispatch.level >= 50:
                # print('dispach stock is {0}, calling store to pick seats at day {1}, hour {2}'.format(
                    # self.dispatch.level, int(env.now/8), env.now % 8))   
                # print('----------------------------------')
                yield env.timeout(4)
                # print('store picking {0} seats at day {1}, hour {2}'.format(
                    # self.dispatch.level, int(env.now/8), env.now % 8))  
                seats_made += self.dispatch.level              
                yield env.timeout(1)
                yield self.dispatch.get(self.dispatch.level)
                # print('----------------------------------')
                yield env.timeout(8)
 
            else:   
                yield env.timeout(1)

            val2 = self.dispatch.level
            data2.append(val2*total_factory_lines) 
            val1 = seats_made + self.dispatch.level
            data1.append(val1*total_factory_lines)  
            time.append(env.now/8)    
        
def frame_maker(env, seat_factory):
    while True:
        yield seat_factory.aluminium.get(1)
        yield seat_factory.foam.get(1)
        yield seat_factory.fabric.get(1)
        frame_time = random.gauss(mean_frame, std_frame)
        yield env.timeout(frame_time)
        yield seat_factory.frame_pre_paint.put(1)
        frame_data.append(seat_factory.frame_pre_paint.level*total_factory_lines)
        time_frame.append(env.now)  # Update frame time vector

def armrest_maker(env, seat_factory):
    while True:
        yield seat_factory.aluminium.get(0.1)
        yield seat_factory.foam.get(0.1)
        yield seat_factory.fabric.get(0.1)
        armrest_time = random.gauss(mean_armrest, std_armrest)
        yield env.timeout(armrest_time)
        yield seat_factory.armrest_pre_paint.put(2)
        armrest_data.append(seat_factory.armrest_pre_paint.level*total_factory_lines)
        time_armrest.append(env.now)  # Update armrest time vector

def painter(env, seat_factory):
    while True:
        yield seat_factory.frame_pre_paint.get(5)
        yield seat_factory.armrest_pre_paint.get(5)
        paint_time = random.gauss(mean_paint, std_paint)
        yield env.timeout(paint_time)
        yield seat_factory.frame_post_paint.put(5)
        yield seat_factory.armrest_post_paint.put(5)

def assembler(env, seat_factory):
    while True:
        yield seat_factory.frame_post_paint.get(1)
        yield seat_factory.armrest_post_paint.get(1)
        assembling_time = max(random.gauss(mean_ensam, std_ensam), 1)
        yield env.timeout(assembling_time)
        yield seat_factory.dispatch.put(1)
        
        
#Generators
        
def frame_maker_gen(env, seat_factory):
    for i in range(num_frame):
        env.process(frame_maker(env, seat_factory))
        yield env.timeout(0)

def armrest_maker_gen(env, seat_factory):
    for i in range(num_armrest):
        env.process(armrest_maker(env, seat_factory))
        yield env.timeout(0)

def painter_maker_gen(env, seat_factory):
    for i in range(num_paint):
        env.process(painter(env, seat_factory))
        yield env.timeout(0)

def assembler_maker_gen(env, seat_factory):
    for i in range(num_ensam):
        env.process(assembler(env, seat_factory))
        yield env.timeout(0)


#-------------------------------------------------     
env = simpy.Environment()
seat_factory = seat_Factory(env)

frame_gen = env.process(frame_maker_gen(env, seat_factory))
armrest_gen = env.process(armrest_maker_gen(env, seat_factory))
painter_gen = env.process(painter_maker_gen(env, seat_factory))
assembler_gen = env.process(assembler_maker_gen(env, seat_factory))

env.run(until = total_time)


# print('Pre paint has {0} bodies and {1} armrests ready to be painted'.format(
#     seat_factory.frame_pre_paint.level, seat_factory.armrest_pre_paint.level))
# print('Post paint has {0} bodies and {1} armrests ready to be assembled'.format(
#     seat_factory.frame_post_paint.level, seat_factory.armrest_post_paint.level))
# print(f'Dispatch has %d seats ready to go!' % seat_factory.dispatch.level)
print(f'----------------------------------')
print('total seats made: {0}'.format((seats_made + seat_factory.dispatch.level)*total_factory_lines))
print(f'----------------------------------')
print(f'SIMULATION COMPLETED')


# val2 = seat_factory.dispatch.level
# data2.append(val2*total_factory_lines) 
# val1 = seats_made + val2
# data1.append(val1*total_factory_lines)  
# time.append(env.now/8)   


data = {
    'Seat Stock': (time, data2),
    'Frame Data': (time_frame, frame_data),
    'Armrest Data': (time_armrest, armrest_data),
    'Aluminium Stock': (time_aluminium, aluminium_stock_data),
    'Foam Stock': (time_foam, foam_stock_data),
    'Fabric Stock': (time_fabric, fabric_stock_data),
    'Total Seats made': (time, data1)
}

def get_data():
    return data, total_factory_lines