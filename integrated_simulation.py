import pysd
import simpy

# Charger et exécuter le modèle PySD
model_definition = """
stock flow {
    stock[Stock] = 100;
    flow[Inflow] = 10;
    flow[Outflow] = 8;
    Stock = Stock + Inflow - Outflow;
}
"""

with open('simple_supply_chain.mdl', 'w') as f:
    f.write(model_definition)

model = pysd.load('simple_supply_chain.py')
results = model.run()

# Extraire les niveaux de stock pour SimPy
stock_levels = results['Stock'].values

# Simulation des événements discrets avec SimPy
def warehouse(env, num_docks, load_time, unload_time, stock_levels):
    dock = simpy.Resource(env, num_docks)

    for stock in stock_levels:
        if stock > 0:
            yield env.timeout(1)  # Simuler une arrivée toutes les unités de temps
            env.process(load_and_unload(env, dock, load_time, unload_time, stock))

def load_and_unload(env, dock, load_time, unload_time, stock):
    with dock.request() as request:
        yield request
        print(f'Loading started at {env.now} with stock {stock}')
        yield env.timeout(load_time)
        print(f'Loading finished at {env.now}')

        print(f'Unloading started at {env.now}')
        yield env.timeout(unload_time)
        print(f'Unloading finished at {env.now}')

# Paramètres de la simulation
num_docks = 2
load_time = 3
unload_time = 2

# Créer l'environnement de simulation SimPy
env = simpy.Environment()
env.process(warehouse(env, num_docks, load_time, unload_time, stock_levels))
env.run(until=len(stock_levels))  # Exécuter la simulation pour la durée des données de stock
