# logistics_engine.py

import os
import pandas as pd

# Define distances between locations in km
distances = {
    # Texas to demand locations
    ('Texas', 'USA'): 2400,
    ('Texas', 'Canada'): 3000,
    ('Texas', 'Japan'): 11000,
    ('Texas', 'Brazil'): 8000,
    ('Texas', 'France'): 8500,
    
    # California to demand locations
    ('California', 'USA'): 3800,
    ('California', 'Canada'): 1300,
    ('California', 'Japan'): 9000,
    ('California', 'Brazil'): 10500,
    ('California', 'France'): 9300,
    
    # UK to demand locations
    ('UK', 'USA'): 5600,
    ('UK', 'Canada'): 5200,
    ('UK', 'Japan'): 9600,
    ('UK', 'Brazil'): 9400,
    ('UK', 'France'): 800,  # by road
    
    # France to demand locations
    ('France', 'USA'): 7600,
    ('France', 'Canada'): 6000,
    ('France', 'Japan'): 9700,
    ('France', 'Brazil'): 8900,
    ('France', 'France'): 200  # local production
}

def load_freight_costs_and_demands():
    """Load costs and demand data from Excel files."""
    absolute_path = os.path.dirname(__file__)

    # Load Freight Costs
    freight_costs = pd.read_excel(os.path.join(absolute_path, 'data/freight_costs.xlsx'), index_col=0)

    # Load Demand
    demand = pd.read_excel(os.path.join(absolute_path, 'data/demand.xlsx'), index_col=0)

    return freight_costs, demand
