import os
import pandas as pd

# Distances par défaut (km) entre les sites de production et les marchés de demande.
distances = {
    # Texas vers marchés
    ('Texas', 'USA'): 2400,
    ('Texas', 'Canada'): 3000,
    ('Texas', 'Japan'): 11000,
    ('Texas', 'Brazil'): 8000,
    ('Texas', 'France'): 8500,
    # California vers marchés
    ('California', 'USA'): 3800,
    ('California', 'Canada'): 1300,
    ('California', 'Japan'): 9000,
    ('California', 'Brazil'): 10500,
    ('California', 'France'): 9300,
    # UK vers marchés
    ('UK', 'USA'): 5600,
    ('UK', 'Canada'): 5200,
    ('UK', 'Japan'): 9600,
    ('UK', 'Brazil'): 9400,
    ('UK', 'France'): 800,
    # France vers marchés
    ('France', 'USA'): 7600,
    ('France', 'Canada'): 6000,
    ('France', 'Japan'): 9700,
    ('France', 'Brazil'): 8900,
    ('France', 'France'): 200
}

def load_freight_costs_and_demands():
    """Charge les coûts de fret et la demande à partir des fichiers Excel dans le dossier data."""
    base_path = os.path.join(os.path.dirname(__file__), 'data')
    freight_costs = pd.read_excel(os.path.join(base_path, 'freight_costs.xlsx'), index_col=0)
    demand = pd.read_excel(os.path.join(base_path, 'demand.xlsx'), index_col=0)
    return freight_costs, demand
