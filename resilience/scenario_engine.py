from line_production.line_production import run_simulation
from line_production.line_production_settings import lines_config
from line_production.production_engine import load_capacity_limits, load_fixed_and_variable_costs
from distribution.distribution_engine import load_freight_costs_and_demands
from tools.data_tools import plot_production_sankey, plot_sankey_production_co2_emissions, display_all_lca_indicators
from economic.cost_engine import calculate_total_costs, calculer_penalite_non_livraison
from environment.environment_engine import (
    calculate_lca_production_IFE_raw,
    calculate_distribution_co2_emissions,
    calculate_lca_indicators_usage_phase,
    calculate_lca_indicators_pers_eq,
    calculate_lca_indicators_total
)
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def run_scenario(allocation_function, config):
    """
    Exécute une simulation complète de chaîne d'approvisionnement pour un scénario donné.
    :param allocation_function: Fonction d'allocation (prend en entrée cap, demand et retourne un dict de résultats).
    :param config: Dictionnaire de configuration pour la simulation (peut contenir 'lines_config', 'events', etc.).
    :return: Dictionnaire de résultats du scénario (production_totals, market_totals, costs, total_co2, etc.).
    """
    # 1) Simulation de production (avec éventuels événements)
    all_production_data, all_enviro_data = run_simulation(
        config["lines_config"],
        events=config.get("events")
    )
    seat_weight = config.get("seat_weight", 130)

    # 2) Capacités : soit on utilise celles fournies dans la config, soit on les reconstruit
    capacity_limits_cfg = config.get("capacity_limits", None)

    if capacity_limits_cfg is not None:
        # ✅ Capacités de référence (cap_max → capacity_limits) passées par simchaingreenhorizons.py
        cap = capacity_limits_cfg
    else:
        # ⚠️ Fallback : ancien comportement, dérivé de la production cumulée SimPy
        max_production = {
            cfg['location']: data['Total Seats made'][1][-1]
            for cfg, data in zip(config["lines_config"], all_production_data)
        }
        cap = load_capacity_limits(max_production)

    # 3) Demande + coûts
    freight_costs, demand = load_freight_costs_and_demands()
    fixed_costs, variable_costs = load_fixed_and_variable_costs(freight_costs)

    # 4) Allocation
    result = allocation_function(cap, demand)
    # Vérifier qu'il y a au moins un site de production sélectionné, sinon renvoyer résultat minimal
    loc_prod = result.get("loc_prod")
    if not loc_prod:
        # Aucun site alloué -> retourner un résultat vide avec coûts nuls
        return {
            **result,
            "costs": {},
            "total_co2": 0,
            "production_data": all_production_data,
            "environment_data": all_enviro_data,
            "config": config,
            "seat_weight": seat_weight
        }
    # Calculer les coûts totaux pour ce scénario
    cost_results = calculate_total_costs({
        "source": result["source"],
        "target": result["target"],
        "value": result["value"],
        "production_totals": result["production_totals"],
        "market_totals": result["market_totals"],
        "loc_prod": result["loc_prod"],
        "loc_demand": result["loc_demand"],
        "cap": result["cap"],
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "include_supply": config.get("include_supply", True),
        "include_storage": config.get("include_storage", True)
    }, seat_weight=seat_weight)
    # Calcul de la pénalité de non-livraison
    penalties, total_penalty = calculer_penalite_non_livraison(result["market_totals"], demand)
    cost_results["penalties"] = penalties
    cost_results["total_penalty"] = total_penalty
    cost_results["total_cost_with_penalty"] = cost_results.get("total_cost", 0) + total_penalty
    # Calcul des émissions totales de CO₂ (production + transport)
    total_co2 = sum(
        calculate_lca_production_IFE_raw(result["value"][i], result["loc_prod"][result["source"][i]], seat_weight=seat_weight)["Climate Change"]
        + calculate_distribution_co2_emissions(result["loc_prod"][result["source"][i]], result["loc_demand"][result["target"][i]], result["value"][i], seat_weight=seat_weight)
        for i in range(len(result["source"]))
    )
    # Renvoyer le résultat complet du scénario
    return {
        **result,
        "costs": cost_results,
        "total_co2": total_co2,
        "production_data": all_production_data,
        "environment_data": all_enviro_data,
        "config": config,
        "seat_weight": seat_weight
    }

def compare_scenarios(results_dict, return_figures=True):
    """
    Compare plusieurs scénarios : production totale, coût, CO2, production par site.
    Version robuste qui tolère des production_totals / costs manquants ou None.
    """
    if not results_dict:
        print("⚠️ compare_scenarios : results_dict est vide")
        return {} if return_figures else None

    print("DEBUG compare_scenarios – scénarios :", list(results_dict.keys()))

    # 1. Normaliser les résultats (production_totals, costs, total_co2)
    normalized = {}
    for name, res in results_dict.items():
        if res is None:
            print(f"⚠️ Résultats vides pour le scénario '{name}'")
            res = {}

        prod = res.get("production_totals") or {}
        if not isinstance(prod, dict):
            print(f"⚠️ production_totals invalide pour '{name}' :", prod)
            prod = {}

        costs = res.get("costs") or {}
        if not isinstance(costs, dict):
            print(f"⚠️ costs invalide pour '{name}' :", costs)
            costs = {}

        total_cost = costs.get("total_cost_with_penalty",costs.get("total_cost", 0.0))
        total_co2 = res.get("total_co2", 0.0)

        normalized[name] = {
            "production_totals": prod,
            "total_cost": total_cost,
            "total_co2": total_co2,
        }

    scenario_names = list(normalized.keys())

    # 2. Union de tous les sites sur tous les scénarios
    all_sites = sorted({
        site
        for res in normalized.values()
        for site in res["production_totals"].keys()
    })

    if not all_sites:
        print("⚠️ Aucun site dans production_totals pour aucun scénario.")
        if return_figures:
            # Tu peux ici renvoyer un dict de figures vides si ton dashboard s'y attend
            return {}
        return None

    # 3. Agrégats par scénario
    total_production = [
        sum(normalized[name]["production_totals"].values())
        for name in scenario_names
    ]
    total_costs = [normalized[name]["total_cost"] for name in scenario_names]
    total_co2 = [normalized[name]["total_co2"] for name in scenario_names]

    # 4. Production par site et par scénario
    production_per_site = {
        site: [
            normalized[name]["production_totals"].get(site, 0)
            for name in scenario_names
        ]
        for site in all_sites
    }

    # 5. Construction des figures Plotly (garde ton code existant ici)
    # ----------------------------------------------------------------
    # Exemple générique, à adapter à ce que tu as déjà :

    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Production totale", "Coût total", "CO₂ total"),
        shared_yaxes=False
    )

    # Barres production totale
    fig.add_trace(
        go.Bar(x=scenario_names, y=total_production, name="Production totale"),
        row=1, col=1
    )

    # Barres coût total
    fig.add_trace(
        go.Bar(x=scenario_names, y=total_costs, name="Coût total"),
        row=1, col=2
    )

    # Barres CO2 total
    fig.add_trace(
        go.Bar(x=scenario_names, y=total_co2, name="CO₂ total"),
        row=1, col=3
    )

    fig.update_layout(barmode="group", title="Comparaison des scénarios")

    # Exemple de figure "production par site" (facultatif selon ton code initial)
    fig_sites = go.Figure()
    for site, values in production_per_site.items():
        fig_sites.add_trace(go.Bar(x=scenario_names, y=values, name=site))
    fig_sites.update_layout(
        barmode="stack",
        title="Production par site et par scénario"
    )

    if return_figures:
        # Adapte la structure retournée si ton dashboard attend autre chose
        return {
            "summary": fig,
            "per_site": fig_sites,
        }
    else:
        fig.show()
        fig_sites.show()
        return None


def display_sankey_for_scenarios(results_dict, return_figures=True):
    """
    Construit les Sankey pour chaque scénario.
    Version robuste : tolère des champs manquants, saute les scénarios bancals.
    """
    if not results_dict:
        print("⚠️ display_sankey_for_scenarios : results_dict vide")
        return {} if return_figures else None

    from tools.data_tools import plot_production_sankey  # adapte l'import si besoin

    sankey_figs = {}

    for name, result in results_dict.items():
        print(f"\nDEBUG Sankey – scénario '{name}'")

        if result is None:
            print(f"  ⚠️ Résultat None pour '{name}', Sankey ignoré.")
            continue

        # Normalisation : None → structures vides
        source = result.get("source") or []
        target = result.get("target") or []
        value = result.get("value") or []
        production_totals = result.get("production_totals") or {}
        market_totals = result.get("market_totals") or {}
        loc_prod = result.get("loc_prod") or []
        loc_demand = result.get("loc_demand") or []

        print("  source len :", len(source) if source is not None else "None")
        print("  target len :", len(target) if target is not None else "None")
        print("  value len  :", len(value)  if value  is not None else "None")
        print("  loc_prod   :", loc_prod)
        print("  loc_demand :", loc_demand)

        # Vérifs minimales pour éviter les crashs
        if not source or not target or not value:
            print(f"  ⚠️ Scénario '{name}' : source/target/value vides, Sankey ignoré.")
            continue

        if len(source) != len(target) or len(source) != len(value):
            print(f"  ⚠️ Scénario '{name}' : tailles incohérentes source/target/value, Sankey ignoré.")
            continue

        if not loc_prod or not loc_demand:
            print(f"  ⚠️ Scénario '{name}' : loc_prod/loc_demand vides, Sankey ignoré.")
            continue

        if not isinstance(production_totals, dict) or not isinstance(market_totals, dict):
            print(f"  ⚠️ Scénario '{name}' : production_totals/market_totals non dict, Sankey ignoré.")
            continue

        try:
            sankey_prod = plot_production_sankey(
                source=source,
                target=target,
                value=value,
                production_totals=production_totals,
                market_totals=market_totals,
                loc_prod=loc_prod,
                loc_demand=loc_demand,
                return_figure=True,
            )
            sankey_figs[name] = sankey_prod

        except Exception as e:
            print(f"  ⚠️ Erreur lors de plot_production_sankey pour '{name}' :", e)
            continue

    if return_figures:
        return sankey_figs
    else:
        # Si tu veux les afficher directement : 
        # for fig in sankey_figs.values(): fig.show()
        return None
