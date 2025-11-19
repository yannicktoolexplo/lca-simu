import os
import math
import pandas as pd
import copy

def calculate_capacity_limits(data):
    """Calculate the capacity limits for each plant based on the total seats made."""
    nos_texas_low = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_texas_high = math.ceil(1.2 * data['Total Seats made'][1][-1])
    nos_california_low = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_california_high = math.ceil(0.6 * data['Total Seats made'][1][-1])
    nos_UK_low = math.ceil(0.15 * data['Total Seats made'][1][-1])
    nos_UK_high = math.ceil(0.3 * data['Total Seats made'][1][-1])
    nos_france_low = math.ceil(0.45 * data['Total Seats made'][1][-1])
    nos_france_high = math.ceil(0.9 * data['Total Seats made'][1][-1])

    capacity_limits = {
        'Texas': (nos_texas_low, nos_texas_high),
        'California': (nos_california_low, nos_california_high),
        'UK': (nos_UK_low, nos_UK_high),
        'France': (nos_france_low, nos_france_high)
    }
    return capacity_limits

def _moving_average(series, window):
    """
    Moyenne glissante simple sur une liste de valeurs.
    """
    if window <= 1:
        return list(series)
    out = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        window_vals = series[start:i+1]
        out.append(sum(window_vals) / len(window_vals))
    return out


def compute_line_rate_curves(result, lines_config, cap_max, window=5):
    """
    Calcule les courbes de taux de production normalisés (0–1) par ligne
    + une courbe globale pondérée par la capacité.

    - result["production_data"][k]["Total Seats made"][1] : courbe cumulée
    - cap_max[location] : capacité max observée pour la ligne

    Retourne :
      line_rates_raw      : {location: [r_i(t)]} taux instantané normalisé
      line_rates_smooth   : {location: [r_i^smooth(t)]} après moyenne glissante
      global_rate_smooth  : [R^smooth(t)] taux global pondéré par capacité
    """
    prod_datas = result.get("production_data", [])
    line_rates_raw = {}
    n_times = None

    # --- 1. Taux instantané normalisé par ligne ---
    for cfg, site_data in zip(lines_config, prod_datas):
        loc = cfg.get("location")
        total_seats = site_data.get("Total Seats made")

        if not loc or not total_seats or not isinstance(total_seats, (list, tuple)) or len(total_seats) < 2:
            continue

        cum_curve = total_seats[1]
        if not isinstance(cum_curve, (list, tuple)) or len(cum_curve) == 0:
            continue

        if n_times is None:
            n_times = len(cum_curve)
        else:
            n_times = min(n_times, len(cum_curve))

        cap = cap_max.get(loc, 0) or 0
        rates = []
        for t in range(len(cum_curve)):
            prod_t = cum_curve[t] if t == 0 else cum_curve[t] - cum_curve[t-1]
            rate = prod_t / cap if cap > 0 else 0.0
            rates.append(rate)

        line_rates_raw[loc] = rates

    if n_times is None:
        # Aucun site exploitable
        return {}, {}, []

    # Tronquer toutes les courbes à la même longueur
    for loc in list(line_rates_raw.keys()):
        line_rates_raw[loc] = line_rates_raw[loc][:n_times]

    # --- 2. Lissage par moyenne glissante ---
    line_rates_smooth = {
        loc: _moving_average(vals, window)
        for loc, vals in line_rates_raw.items()
    }

    # --- 3. Courbe globale pondérée par la capacité ---
    total_cap = sum(cap_max.get(cfg["location"], 0) for cfg in lines_config)
    global_raw = []
    for t in range(n_times):
        num = 0.0
        for cfg in lines_config:
            loc = cfg["location"]
            cap = cap_max.get(loc, 0)
            if loc in line_rates_raw:
                num += line_rates_raw[loc][t] * cap
        global_raw.append(num / total_cap if total_cap > 0 else 0.0)

    global_smooth = _moving_average(global_raw, window)

    return line_rates_raw, line_rates_smooth, global_smooth


def load_fixed_and_variable_costs(freight_costs):
    """Load fixed and variable costs from Excel files."""
    absolute_path = os.path.dirname(__file__)
    
    fixed_costs = pd.read_excel(os.path.join(absolute_path, 'data/fixed_cost.xlsx'), index_col=0)
    manvar_costs = pd.read_excel(os.path.join(absolute_path, 'data/variable_costs.xlsx'), index_col=0)
    
    variable_costs = freight_costs / 1000 + manvar_costs
    
    return fixed_costs, variable_costs

# def load_capacity_limits(capacity_limits):
#     """Load and update capacity limits."""
#     absolute_path = os.path.dirname(__file__)
#     cap = pd.read_excel(os.path.join(absolute_path, 'data/capacity.xlsx'), index_col=0)
    
#     # Update the capacity DataFrame with the calculated limits
#     for location, (low, high) in capacity_limits.items():
#         cap.loc[location, 'Low'] = low
#         cap.loc[location, 'High'] = high

#     # Save the modified DataFrame back to the Excel file
#     cap.to_excel(os.path.join(absolute_path, 'data/capacity.xlsx'))
    
#     return cap

def get_global_production_rate(result,lines_config, cap_max):
    prod_datas = result.get("production_data", [])
    filtered = [
        site_data for site_data in prod_datas
        if site_data.get("Total Seats made")
        and isinstance(site_data["Total Seats made"], (list, tuple))
        and len(site_data["Total Seats made"]) > 1
        and isinstance(site_data["Total Seats made"][1], (list, tuple))
        and len(site_data["Total Seats made"][1]) > 0
    ]
    if not filtered:
        return []
    n_times = min(len(site_data["Total Seats made"][1]) for site_data in filtered)
    total_cap_max = sum(cap_max[cfg['location']] for cfg in lines_config)
    taux = []
    for t in range(n_times):
        prod_reelle = sum(site_data["Total Seats made"][1][t] for site_data in filtered)
        taux.append(prod_reelle / total_cap_max if total_cap_max > 0 else 0)
    return taux

def get_global_production_rate_journalier(result, lines_config, cap_max):
    """
    Retourne la courbe de taux de production instantané (journalier, par pas) pour l'ensemble du système.
    """
    prod_datas = result.get("production_data", [])
    filtered = [
        site_data for site_data in prod_datas
        if site_data.get("Total Seats made")
        and isinstance(site_data["Total Seats made"], (list, tuple))
        and len(site_data["Total Seats made"]) > 1
        and isinstance(site_data["Total Seats made"][1], (list, tuple))
        and len(site_data["Total Seats made"][1]) > 0
    ]
    if not filtered:
        return []
    n_times = min(len(site_data["Total Seats made"][1]) for site_data in filtered)
    total_cap_max = sum(cap_max[cfg['location']] for cfg in lines_config)
    taux = []
    for t in range(n_times):
        # Calcule la production instantanée (non cumulée)
        prod_reelle = 0
        for site_data in filtered:
            prod_curve = site_data["Total Seats made"][1]
            prod_jour = prod_curve[t] if t == 0 else prod_curve[t] - prod_curve[t-1]
            prod_reelle += prod_jour
        taux.append(prod_reelle / total_cap_max if total_cap_max > 0 else 0)
    return taux



def load_capacity_limits(production_totals):
    """
    Charge les limites de capacité en fonction des totaux de production simulés pour chaque ligne.

    :param production_totals: Liste des totaux de production pour chaque ligne.
    :return: Dictionnaire des limites de capacité par localisation.
    """
    capacity_l = {}

    for location, total_production in production_totals.items():
        capacity_l[location] = {
            'Low': total_production / 2,  # La moitié du total de production comme capacité basse
            'High': total_production      # Total de production comme capacité haute
        }

    return capacity_l


def build_capacity_limits_from_cap_max(cap_max, factor_low=0.0):
    """
    Construit des limites de capacité à partir du cap_max SimPy :
    cap_max[site] = capacité journalière maximale (ou totale selon ton interprétation).

    factor_low permet (si tu veux) d'avoir un Low > 0, mais pour la baseline
    simple on peut juste mettre 0.
    """
    capacity_l = {}
    for location, cap in cap_max.items():
        cap = float(cap)
        capacity_l[location] = {
            "Low": factor_low * cap,
            "High": cap
        }
    return capacity_l


def run_simple_supply_allocation(capacity_limits, demand):
    """
    Allocation baseline "simple" qui cherche uniquement à
    SATISFAIRE LA DEMANDE, sans optimiser coût/CO₂.

    Hypothèse : si la somme des capacités High est suffisante,
    toute la demande sera couverte.

    :param capacity_limits: dict
        {site: {"Low": ..., "High": ...}}
    :param demand: dict ou DataFrame avec une colonne 'Demand'
    :return: source, target, value, production_totals, market_totals, loc_prod, loc_demand, capacity_limits
    """

    # --- Normalisation des capacités ---
    # On travaille sur une copie pour ne pas modifier l'objet d'entrée
    cap = {}
    for site, vals in capacity_limits.items():
        if isinstance(vals, dict):
            low  = float(vals.get("Low", 0.0))
            high = float(vals.get("High", 0.0))
        elif isinstance(vals, (list, tuple)) and len(vals) >= 2:
            low, high = float(vals[0]), float(vals[1])
        else:
            low = high = float(vals)
        cap[site] = {"Low": low, "High": high}

    loc_prod = list(cap.keys())

    # --- Normalisation de la demande ---
    if isinstance(demand, pd.DataFrame):
        if "Demand" not in demand.columns:
            raise ValueError("Le DataFrame `demand` doit contenir une colonne 'Demand'.")
        demand_dict = demand["Demand"].astype(float).to_dict()
    elif isinstance(demand, dict):
        demand_dict = {k: float(v) for k, v in demand.items()}
    else:
        raise TypeError("`demand` doit être un dict ou un DataFrame avec colonne 'Demand'.")

    loc_demand = list(demand_dict.keys())

    # --- Vérif globale capacité vs demande ---
    total_capacity = sum(v["High"] for v in cap.values())
    total_demand   = sum(demand_dict.values())
    if total_capacity + 1e-6 < total_demand:
        print(
            f"⚠️ run_simple_supply_allocation : capacité totale {total_capacity:.2f} "
            f"< demande totale {total_demand:.2f} → la demande ne pourra PAS être entièrement couverte."
        )

    # --- Structures de résultat ---
    flows = {(i, j): 0.0 for i in loc_prod for j in loc_demand}
    production_totals = {i: 0.0 for i in loc_prod}
    market_totals     = {j: 0.0 for j in loc_demand}

    # --- Allocation greedy par marché, avec tes priorités ---
    for market in loc_demand:
        remaining = demand_dict[market]

        if market == "France":
            priority_sites = ["France", "UK", "Texas", "California"]
        elif market == "UK":
            priority_sites = ["UK", "France", "Texas", "California"]
        else:
            # USA, Canada, Japan, Brazil, etc.
            priority_sites = ["Texas", "California", "France", "UK"]

        for site in priority_sites:
            if remaining <= 1e-9:
                break
            if site not in cap:
                continue

            avail = cap[site]["High"]
            if avail <= 1e-9:
                continue

            alloc = min(remaining, avail)
            flows[(site, market)] += alloc
            cap[site]["High"]     -= alloc
            production_totals[site] += alloc
            market_totals[market]   += alloc
            remaining -= alloc

        if remaining > 1e-6:
            print(
                f"⚠️ Marché {market} : demande non couverte de {remaining:.2f} unités "
                f"(capacité globale insuffisante ou mal répartie)."
            )

    # --- Conversion en listes pour le Sankey ---
    source, target, value = [], [], []
    for (site, market), qty in flows.items():
        if qty > 0:
            source.append(loc_prod.index(site))
            target.append(loc_demand.index(market))
            value.append(qty)

    # --- Debug cohérence ---
    print("[Baseline] somme demande   =", total_demand)
    print("[Baseline] somme production =", sum(production_totals.values()))
    print("[Baseline] production_totals =", production_totals)
    print("[Baseline] market_totals     =", market_totals)

    # On renvoie l’objet capacity_limits d’origine (non modifié)
    return source, target, value, production_totals, market_totals, loc_prod, loc_demand, capacity_limits


def run_simulation_step(current_stock, command_quantity, max_capacity=50, daily_consumption=10):
    """
    Simule un pas de production pour une ligne vivante.
    
    :param current_stock: stock actuel
    :param command_quantity: commande décidée par le moteur vivant
    :param max_capacity: capacité maximale de production par jour
    :param daily_consumption: consommation fixe ou estimée
    :return: dictionnaire avec résultats du step
    """

    # Appliquer la contrainte de capacité
    actual_production = min(command_quantity, max_capacity)

    # Mise à jour du stock
    stock_variation = actual_production - daily_consumption
    new_stock = current_stock + stock_variation

    return {
        "produced": actual_production,
        "new_stock": new_stock,
        "stock_variation": stock_variation
    }
