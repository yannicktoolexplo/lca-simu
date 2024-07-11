# logistics_engine.py

import os
import pandas as pd

def load_freight_costs_and_demands():
    """Load costs and demand data from Excel files."""
    absolute_path = os.path.dirname(__file__)

    # Load Freight Costs
    freight_costs = pd.read_excel(os.path.join(absolute_path, 'data/freight_costs.xlsx'), index_col=0)

    # Load Demand
    demand = pd.read_excel(os.path.join(absolute_path, 'data/demand.xlsx'), index_col=0)

    return freight_costs, demand
