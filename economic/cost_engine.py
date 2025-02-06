def get_supply_cost(quantity, distance):
    """
    Calcule le coût d'approvisionnement pour une quantité donnée.

    :param quantity: Quantité en tonnes.
    :param distance: Distance en km.
    :param cost_per_km_ton: Coût par tonne-kilomètre (par défaut 0.1 €/tonne-km).
    :return: Coût total en euros.
    """
    cost_per_km_ton=0.1
    
    return quantity * distance * cost_per_km_ton


def calculate_total_costs(source, target, value, production_totals, market_totals, loc_prod, loc_demand, cap):
    """
    Calculate production costs for each country and total costs based on capacity, fixed costs,
    and variable costs.

    :param source: List of source indices corresponding to emissions.
    :param target: List of target indices corresponding to emissions.
    :param value: List of quantities transported between source and target.
    :param production_totals: List of total production quantities per source.
    :param market_totals: Dictionary with market demand totals per region (e.g., {'USA': 176.0, 'France': 308.0}).
    :param loc_prod: List of production locations (e.g., ['Texas', 'California', 'UK', 'France']).
    :param loc_demand: List of demand locations (e.g., ['USA', 'Canada', 'Japan', 'Brazil', 'France']).
    :param cap: Dictionary with production capacities (keys are locations, values are {'Low': x, 'High': y}).
    :return: Dictionary with production distribution, costs per country, and the total cost.
    """
    # Initialize results
    production_distribution = {location: 0 for location in loc_prod}
    total_costs = {location: 0.0 for location in loc_prod}

    # Distribute market demand to production countries
    for market, demand in market_totals.items():
        # Sort by capacity to prioritize higher capacity locations
        sorted_capacity = sorted(cap.items(), key=lambda x: x[1]['High'], reverse=True)
        remaining_demand = demand

        for country, capacities in sorted_capacity:
            if country not in loc_prod:
                continue

            low_cap = capacities['Low']
            high_cap = capacities['High']

            # Determine how much of the demand can be fulfilled by this country
            allocated = min(remaining_demand, high_cap)
            production_distribution[country] += allocated
            remaining_demand -= allocated

            # Break if demand is fully allocated
            if remaining_demand <= 0:
                break

    # Calculate costs for each country
    for i, source_index in enumerate(source):
        location = loc_prod[source_index]
        low_cap = cap[location]['Low']
        high_cap = cap[location]['High']

        # Determine if low or high capacity applies
        capacity_type = 'Low' if production_totals[location] <= low_cap else 'High'

        # Example fixed and variable costs (replace these with actual values as needed)
        fixed_cost = 1000 if capacity_type == 'Low' else 2000  # Replace with actual fixed costs
        variable_cost = 10  # Replace with actual variable costs per unit

        # Calculate total cost for the country
        total_costs[location] += fixed_cost + (variable_cost * production_totals[location])

    # Calculate total cost across all countries
    total_cost = sum(total_costs.values())

    return {
        'production_distribution': production_distribution,
        'country_costs': total_costs,
        'total_cost': total_cost
    }
