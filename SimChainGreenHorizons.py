from optimization.optimization_engine import (
    run_simple_allocation_dict,
    run_optimization_allocation_dict,
    run_optimization_co2_allocation_dict,
    run_multiobjective_allocation_dict,
    run_supply_chain_lightweight_scenario,
    run_resilience_allocation_dict,
    run_resilience_optimization,
    build_capacity_limits_from_cap_max,

)
from line_production.line_production_settings import lines_config, scenario_events
from line_production.line_production import run_simulation
from line_production.production_engine import (
    get_global_production_rate,
    get_global_production_rate_journalier,
    compute_line_rate_curves,
    build_capacity_limits_from_cap_max,
)
from event_engine import PerturbationEvent

from sqlalchemy import (
    create_engine,
    Table,
    MetaData,
    insert,
    Column,
    Integer,
    Float,
    String,
)
from sqlalchemy.orm import sessionmaker
from utils.data_tools import display_all_lca_indicators, get_total_prod_curve
from hybrid_regulation_engine import run_simulation_vivant
from scenario_engine import run_scenario, compare_scenarios, display_sankey_for_scenarios
from resilience_indicators import compute_resilience_indicators, resilience_on_curve
from resilience_analysis import radar_indicators
from copy import deepcopy
from performance_engine import compute_perf_signal, aggregate_multi_kpi
from typing import Dict, Iterable, List, Tuple


# Configuration constants
DEFAULT_SEAT_WEIGHT = 130       # Poids de siège par défaut (kg)
LIGHTWEIGHT_SEAT_WEIGHT = 70    # Poids de siège utilisé pour le scénario lightweight (kg)
DB_PATH = 'sqlite:///simchain.db'  # Chemin de la base de données SQLite


def _prepare_lines_config_max(lines: List[Dict], stock_level: int = 1_000_000) -> List[Dict]:
    """Return a copy of ``lines`` with oversized stocks to measure peak capacities."""
    lines_config_max = deepcopy(lines)
    for cfg in lines_config_max:
        for mat in ["aluminium", "foam", "fabric", "paint"]:
            cap_key = f"{mat}_capacity"
            init_key = f"initial_{mat}"
            cfg[init_key] = stock_level
            cfg[cap_key] = max(cfg.get(cap_key, 0), cfg[init_key])
    return lines_config_max


def _compute_capacity_limits(lines_max: List[Dict]) -> Tuple[Dict, Dict]:
    """Simulate with large stocks to derive baseline capacity limits."""
    config_maxcap = {
        "lines_config": lines_max,
        "include_supply": False,
        "include_storage": True,
        "events": None,
    }
    result_maxcap = run_scenario(run_simple_allocation_dict, config_maxcap)

    cap_max: Dict[str, float] = {}
    for cfg, site_data in zip(lines_config, result_maxcap.get("production_data", [])):
        prod_par_temps = site_data["Total Seats made"][1]
        cap_max[cfg["location"]] = max(prod_par_temps)
        print(f"Capacité max observée pour {cfg['location']} : {cap_max[cfg['location']]}")

    return build_capacity_limits_from_cap_max(cap_max), cap_max


def _build_scenario_config(
    lines: List[Dict],
    capacity_limits: Dict | None = None,
    seat_weight: float | None = None,
    include_supply: bool = True,
    include_storage: bool = True,
    events: Iterable | None = None,
) -> Dict:
    config = {
        "lines_config": deepcopy(lines),
        "include_supply": include_supply,
        "include_storage": include_storage,
    }
    if capacity_limits is not None:
        config["capacity_limits"] = capacity_limits
    if seat_weight is not None:
        config["seat_weight"] = seat_weight
    if events is not None:
        config["events"] = events
    return config


def _run_allocation_with_weight(
    allocation_func,
    base_lines: List[Dict],
    capacity_limits: Dict,
    seat_weight: float,
):
    custom_lines = []
    for cfg in base_lines:
        custom_cfg = deepcopy(cfg)
        custom_cfg["seat_weight"] = seat_weight
        custom_cfg["include_site"] = True
        custom_lines.append(custom_cfg)
    scenario_config = _build_scenario_config(
        custom_lines,
        capacity_limits=capacity_limits,
        seat_weight=seat_weight,
    )
    return run_scenario(allocation_func, scenario_config)


def _adjust_production_curves_to_match_totals(scenario_res: Dict) -> None:
    prod_totals = scenario_res.get("production_totals") or {}
    prod_data = scenario_res.get("production_data") or []
    if not prod_totals or not prod_data:
        return
    for site_data in prod_data:
        name = site_data.get("name") or site_data.get("location") or ""
        totals = site_data.get("Total Seats made")
        if not totals or len(totals) < 2:
            continue
        curve = totals[1]
        if not curve:
            continue
        sim_total = float(curve[-1])
        target_total = float(prod_totals.get(name, sim_total))
        scale = 0.0 if sim_total <= 0 else target_total / sim_total
        if abs(scale - 1.0) > 1e-6:
            site_data["Total Seats made"] = (
                totals[0],
                [v * scale for v in curve],
            )


def _build_resilience_event_definitions(lines: List[Dict]) -> Dict[str, List[PerturbationEvent]]:
    resilience_event_definitions: Dict[str, List[PerturbationEvent]] = {}
    material_events = ["aluminium", "foam", "fabric", "paint"]
    site_names = [cfg.get("location") for cfg in lines if cfg.get("location")]
    for mat in material_events:
        resilience_event_definitions[f"Rupture {mat.capitalize()}"] = [
            PerturbationEvent(
                time=20,
                target=mat,
                event_type="rupture_fournisseur",
                magnitude=1.0,
                duration=200,
                description=f"Rupture {mat}",
            )
        ]
    for site in site_names:
        resilience_event_definitions[f"Panne {site}"] = [
            PerturbationEvent(
                time=20,
                target=site,
                event_type="panne",
                magnitude=1.0,
                duration=200,
                description=f"Panne {site}",
            )
        ]
    return resilience_event_definitions


def _compute_resilience_score(result_nominal: Dict, result_crisis: Dict) -> float:
    prod_nominal = (result_nominal or {}).get("production_totals") or {}
    prod_crisis = (result_crisis or {}).get("production_totals") or {}
    total_nominal = sum(prod_nominal.values())
    total_crisis = sum(prod_crisis.values())
    if total_nominal == 0:
        return 0.0
    return round(100 * min(total_crisis, total_nominal) / total_nominal, 1)


def _build_global_rate_curve(result_dict: Dict) -> Tuple[List, List, float]:
    prod_datas = result_dict.get("production_data") or []
    time = None
    global_cumul = None
    for site_data in prod_datas:
        total = site_data.get("Total Seats made")
        if not total or len(total) < 2:
            continue
        t_site = list(total[0])
        cumul_site = [float(v) for v in total[1]]
        if time is None:
            time = t_site
            global_cumul = cumul_site
        else:
            n = min(len(time), len(t_site), len(cumul_site))
            if n <= 0:
                continue
            time = time[:n]
            global_cumul = global_cumul[:n]
            for k in range(n):
                global_cumul[k] += cumul_site[k]
    if not time or not global_cumul:
        return [], [], 0.0
    daily = []
    prev = 0.0
    for v in global_cumul:
        inc = max(float(v) - prev, 0.0)
        daily.append(inc)
        prev = float(v)
    peak = max(daily) if daily else 0.0
    if peak <= 0:
        peak = 1.0
    norm_curve = [d / peak for d in daily]
    time = time[: len(norm_curve)]
    total = float(sum(daily))
    return time, norm_curve, total


def _compute_average_radar(nominal_result: Dict, crisis_results: Dict) -> Dict | None:
    time_nom, curve_nom, total_nom = _build_global_rate_curve(nominal_result)
    if not curve_nom or not time_nom or total_nom <= 0:
        return None
    radars = []
    for crisis_res in (crisis_results or {}).values():
        t_cr, curve_cr, total_cr = _build_global_rate_curve(crisis_res)
        if not curve_cr or not t_cr or total_cr <= 0:
            continue
        min_len = min(len(curve_nom), len(curve_cr), len(time_nom), len(t_cr))
        if min_len == 0:
            continue
        scores = radar_indicators(
            curve_nom[:min_len],
            curve_cr[:min_len],
            time_nom[:min_len],
            total_nom,
            total_cr,
        )
        radars.append(scores)
    if not radars:
        return None
    keys = ["R1 Amplitude", "R2 Recovery", "R3 Aire", "R4 Ratio", "R5 ProdCumul", "Score global"]
    return {key: sum(r.get(key, 0.0) for r in radars) / len(radars) for key in keys}


def _extract_figs(obj):
    """Normalise en liste de figures Plotly quel que soit le format en entrée."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        figs = []
        for v in obj.values():
            if isinstance(v, list):
                figs.extend(v)
            elif isinstance(v, dict):
                figs.extend(v.values())
            else:
                figs.append(v)
        return figs
    return [obj]


def _run_resilience_phases(allocation_func, base_cfg: Dict, shocks: Dict[str, Iterable]) -> Dict[str, Dict]:
    """Execute standard supply/production/distribution shocks for a scenario config."""
    return {
        phase: run_scenario(allocation_func, {**deepcopy(base_cfg), "events": shock_events})
        for phase, shock_events in shocks.items()
    }


def _compute_daily_from_cumul(cumul: List[float]) -> List[float]:
    if not cumul:
        return []
    daily = [cumul[0]]
    for i in range(1, len(cumul)):
        daily.append(max(cumul[i] - cumul[i - 1], 0.0))
    return daily


def _persist_results_to_db(scenario_results: Dict, db_path: str = DB_PATH) -> None:
    engine = create_engine(db_path)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    if 'result' in metadata.tables:
        result_table = metadata.tables['result']
    else:
        result_table = Table(
            'result',
            metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('scenario_id', Integer),
            Column('site', String),
            Column('total_production', Float),
            Column('total_cost', Float),
            Column('total_co2', Float),
        )
        metadata.create_all(engine, tables=[result_table])
    Session = sessionmaker(bind=engine)
    session = Session()
    for scenario_id, (name, scenario_res) in enumerate(scenario_results.items(), start=1):
        prod_totals = scenario_res.get("production_totals") or {}
        if not isinstance(prod_totals, dict):
            print(f"⚠️ production_totals invalide pour le scénario '{name}':", prod_totals)
            prod_totals = {}
        costs = scenario_res.get("costs") or {}
        if not isinstance(costs, dict):
            print(f"⚠️ costs invalide pour le scénario '{name}':", costs)
            costs = {}
        total_cost = costs.get("total_cost", 0.0)
        total_co2 = scenario_res.get("total_co2", 0.0)
        for site, total in prod_totals.items():
            session.execute(insert(result_table).values(
                scenario_id=scenario_id,
                site=site,
                total_production=total,
                total_cost=total_cost,
                total_co2=total_co2
            ))
    session.commit()
    session.close()

def main_function():
    """Exécute la simulation logistique pour différents scénarios, calcule les coûts,
    émissions et scores de résilience, puis retourne les résultats formatés pour le tableau de bord."""
    # 1. Simulation de base (production sans événements)
    all_production_data, _ = run_simulation(lines_config)

    lines_config_max = _prepare_lines_config_max(lines_config)
    baseline_capacity_limits, cap_max = _compute_capacity_limits(lines_config_max)

    # Configuration de base pour les scénarios
    base_config = _build_scenario_config(
        lines_config_max,
        capacity_limits=baseline_capacity_limits,
        include_supply=True,
        include_storage=True,
    )

    # 2. Exécuter les différents scénarios sans perturbation
    result_baseline = run_scenario(run_simple_allocation_dict, base_config)
    # --- Configs CRISES : SANS capacity_limits pour laisser run_scenario
    # recalculer les capacités à partir de la simu avec événements ---

    crisis_base_config = _build_scenario_config(
        lines_config_max,
        include_supply=True,
        include_storage=True,
    )

    config_crise = {**crisis_base_config, "events": scenario_events["Rupture Alu"]}
    config_crise2 = {**crisis_base_config, "events": scenario_events["Panne Texas"]}

    # Ces résultats de crise auront des capacités dégradées
    result_crise = run_scenario(run_simple_allocation_dict, config_crise)
    result_crise2 = run_scenario(run_simple_allocation_dict, config_crise2)

    # Optimisation coût, optimisation CO₂, multi-objectifs, scénario simplifié léger
    result_optim_cost = _run_allocation_with_weight(
        run_optimization_allocation_dict,
        lines_config_max,
        base_config["capacity_limits"],
        DEFAULT_SEAT_WEIGHT,
    )
    result_optim_co2 = _run_allocation_with_weight(
        run_optimization_co2_allocation_dict,
        lines_config_max,
        base_config["capacity_limits"],
        DEFAULT_SEAT_WEIGHT,
    )
    result_multi = _run_allocation_with_weight(
        run_multiobjective_allocation_dict,
        lines_config_max,
        base_config["capacity_limits"],
        DEFAULT_SEAT_WEIGHT,
    )
    result_lightweight = _run_allocation_with_weight(
        lambda cap, demand: run_supply_chain_lightweight_scenario(cap, demand, seat_weight=LIGHTWEIGHT_SEAT_WEIGHT),
        lines_config_max,
        base_config["capacity_limits"],
        LIGHTWEIGHT_SEAT_WEIGHT,
    )

    # 3. Simulation vivante (système vivant avec logique de régulation cognitive)
    result_vivant_raw = run_simulation_vivant(lines_config)
    # Construire un résultat compatible avec les autres scénarios (mêmes clés attendu par le dashboard)
    result_vivant = {
        "production_totals": {
            site: sum(r["stock"] for r in result_vivant_raw if r["site"] == site)
            for site in {r["site"] for r in result_vivant_raw}
        },
        "production_data": result_vivant_raw,
        "environment_data": [{} for _ in lines_config],
        "costs": {"total_cost": 0},
        "total_co2": 0,
        # Clés vides pour compatibilité avec les fonctions Sankey
        "source": [],
        "target": [],
        "value": [],
        "loc_prod": {},
        "loc_demand": {},
        "market_totals": {},
        "cap": {}
    }

    # Regrouper tous les résultats de scénarios dans un dictionnaire
    scenario_results = {
        "Baseline":        {**result_baseline,   "allocation_func": run_simple_allocation_dict},
        "Optimisation Coût":  {**result_optim_cost, "allocation_func": run_optimization_allocation_dict},
        "Optimisation CO₂":   {**result_optim_co2,  "allocation_func": run_optimization_co2_allocation_dict},
        "MultiObjectifs":  {**result_multi,     "allocation_func": run_multiobjective_allocation_dict},
        "Lightweight":     {**result_lightweight, "allocation_func": lambda cap, demand: run_supply_chain_lightweight_scenario(cap, demand, seat_weight=LIGHTWEIGHT_SEAT_WEIGHT)},
        "Optimisation Résilience": {    "allocation_func": run_resilience_allocation_dict},
    }
    for scenario_res in scenario_results.values():
        _adjust_production_curves_to_match_totals(scenario_res)
    # Scénarios de crises pour la résilience : rupture de chaque matière et panne de chaque site
    resilience_event_definitions = _build_resilience_event_definitions(lines_config)

    # Stocker également le scénario de crise à part
    crisis_results = {
    "Baseline": {**result_baseline,   "allocation_func": run_simple_allocation_dict},
    "Crise 1": {**result_crise, "allocation_func": run_simple_allocation_dict},
    "Crise 2": {**result_crise2, "allocation_func": run_simple_allocation_dict}
}

    # ==================================================
    # Optimisation Résilience (avant les comparaisons)
    # ==================================================
    scenario_events_res = {}
    crisis_counter = 1
    for crisis_name, events in resilience_event_definitions.items():
        scenario_events_res[f"Crise {crisis_counter}"] = events
        crisis_counter += 1

    resilience_base_config = deepcopy(base_config)
    resilience_base_config["lines_config"] = deepcopy(lines_config)
    resilience_crisis_config = deepcopy(crisis_base_config)
    resilience_crisis_config["lines_config"] = deepcopy(lines_config)

    best_resilient, summary_resilience = run_resilience_optimization(
        base_config["capacity_limits"],
        resilience_base_config,
        resilience_crisis_config,
        scenario_events_res,
    )

    if best_resilient is None:
        print("[ResilienceOpt] Aucune configuration valide trouvée.")
        resilience_opt_result = {
            "best_score": 0.0,
            "best_name": "Aucune configuration valide",
            "best_capacities": {},
            "radar_crise1": {},
            "radar_crise2": {},
            "summary": []
        }
    else:
        best_score, best_name, best_capacities, radar_c1, radar_c2 = best_resilient[:5]
        best_score_pct = round(best_score * 100.0, 1)
        optimized_config = {
            **base_config,
            "capacity_limits": best_capacities
        }
        result_resilience = run_scenario(run_optimization_allocation_dict, optimized_config)
        # calcul moyenne radars sur toutes les crises utilisées
        radar_keys = ["R1 Amplitude", "R2 Recovery", "R3 Aire", "R4 Ratio", "R5 ProdCumul", "Score global"]
        radar_avg_opt = {key: (radar_c1.get(key, 0.0) + radar_c2.get(key, 0.0)) / 2.0 for key in radar_keys}

        scenario_results["Optimisation Résilience"] = {
            **result_resilience,
            "allocation_func": run_optimization_allocation_dict,
            "resilience_score": best_score_pct,
            "best_config_name": best_name,
            "resilience_radar_avg": radar_avg_opt,
        }
        _adjust_production_curves_to_match_totals(scenario_results["Optimisation Résilience"])
        resilience_opt_result = {
            "best_score": best_score_pct,
            "best_name": best_name,
            "best_capacities": best_capacities,
            "radar_crise1": radar_c1,
            "radar_crise2": radar_c2,
            "summary": [
                {"score": round(s[0] * 100.0, 1), "name": s[1]}
                for s in sorted(summary_resilience, key=lambda item: item[0], reverse=True)
            ]
        }

    # Jeux de chocs standard utilisés pour les tests de résilience
    standard_shocks = {
        "supply": scenario_events["shock_supply"],
        "production": scenario_events["shock_production"],
        "distribution": scenario_events["shock_distribution"],
    }

    def _base_config_without_events(scenario_res: Dict) -> Dict:
        cfg = deepcopy(scenario_res.get("config", base_config))
        cfg.pop("events", None)
        return cfg

    # 5. Pour chaque scénario nominal (hors crise)
    for name, scenario_res in scenario_results.items():
        base_cfg = _base_config_without_events(scenario_res)
        scenario_res["resilience_test"] = _run_resilience_phases(
            scenario_res["allocation_func"],
            base_cfg,
            standard_shocks,
        )
        scenario_res["resilience_crises"] = {}
        for crisis_name, events in resilience_event_definitions.items():
            res_crisis = run_scenario(
                scenario_res["allocation_func"],
                {**deepcopy(base_cfg), "events": events},
            )
            scenario_res["resilience_crises"][crisis_name] = res_crisis

    # 5bis. Pour chaque scénario de crise
    crisis_res_base_cfg = {**base_config, "loc_prod": {}}
    for name, crisis_res in crisis_results.items():
        crisis_res["resilience_test"] = _run_resilience_phases(
            crisis_res["allocation_func"],
            crisis_res_base_cfg,
            standard_shocks,
        )

    # 6. Score de résilience - scenarios normaux
    for name, scenario_res in scenario_results.items():
        tests = scenario_res["resilience_test"]
        scores = {phase: _compute_resilience_score(scenario_res, tests[phase]) for phase in ["supply", "production", "distribution"]}
        scores["total"] = round(sum(scores.values()) / 3, 1)
        scenario_res["resilience_scores"] = scores

    # Calculer les scores de résilience pour chaque scénario de crise
    for name, scenario_res in crisis_results.items():
        tests = scenario_res.get("resilience_test", {})
        scores = {phase: _compute_resilience_score(scenario_res, tests.get(phase, {})) for phase in ["supply", "production", "distribution"]}
        scores["total"] = round(sum(scores.values()) / 3, 1)
        crisis_results[name]["resilience_scores"] = scores

    for scenario_res in scenario_results.values():
        radar_avg = _compute_average_radar(scenario_res, scenario_res.get("resilience_crises"))
        if radar_avg:
            scenario_res["resilience_radar_avg"] = radar_avg


    # 7. Enregistrer les résultats de production dans la base de données
    _persist_results_to_db(scenario_results)

    # 8. Préparer les visualisations comparatives des scénarios
    comparison_figs = compare_scenarios(scenario_results, return_figures=True)
    sankey_figs = display_sankey_for_scenarios(scenario_results, return_figures=True)
    # Pour la visualisation groupée de tous les scénarios de crise :
    crisis_figs = compare_scenarios(crisis_results, return_figures=True)
    crisis_sankey_figs = display_sankey_for_scenarios(crisis_results, return_figures=True)


    print("DEBUG scenario_results keys =", list(scenario_results.keys()))
    print("DEBUG type MultiObjectifs =", type(scenario_results.get("MultiObjectifs", None)))


    # Figures "nominales" (sans crises)
    all_figs = []
    all_figs += _extract_figs(comparison_figs)
    all_figs += _extract_figs(sankey_figs)

    # Figures spécifiques aux crises, affichées dans une section dédiée du dashboard
    crisis_all_figs = _extract_figs(crisis_figs) + _extract_figs(crisis_sankey_figs)


    # 9. Analyse LCA ciblée sur la France (scénario multi-objectifs)
    fr_config = [c for c in lines_config if c["location"] == "France"]
    fr_index = lines_config.index(fr_config[0]) if fr_config else 0

    fr_production_data = [result_multi["production_data"][fr_index]]
    fr_enviro_data = [result_multi["environment_data"][fr_index]]

    prod_totals_multi = result_multi.get("production_totals") or {}
    print("DEBUG MultiObjectifs – production_totals =", prod_totals_multi)

    fr_totals = {"France": prod_totals_multi.get("France", 0)}

    seat_weight = result_multi.get("seat_weight", DEFAULT_SEAT_WEIGHT)  # utilisé ailleurs, pas dans cette fonction

    fig_lca_fr = display_all_lca_indicators(
        fr_production_data,
        fr_enviro_data,
        [fr_config[0]],
        fr_totals,
        use_allocated_production=True,
        seat_weight=seat_weight,
        return_fig=True,  # <-- important
    )






    # 10. Analyse LCA globale tous sites (scénario multi-objectifs)
    result_multi = scenario_results.get("MultiObjectifs", {})
    prod_totals_multi = result_multi.get("production_totals", {}) or {}

    print("DEBUG MultiObjectifs production_totals =",
      scenario_results.get("MultiObjectifs", {}).get("production_totals"))
    total_production = sum(prod_totals_multi.values())

    if total_production <= 0:
        print("⚠️ Analyse LCA globale : aucune production totale dans le scénario multi-objectifs.")
        fig_lca_total = None
    else:
        fig_lca_total = display_all_lca_indicators(
            all_production_data=result_multi["production_data"],
            all_enviro_data=result_multi["environment_data"],
            lines_config=lines_config,
            production_totals=prod_totals_multi,
            use_allocated_production=True,
            seat_weight=seat_weight,
            return_fig=True,
        )

    # --- Capacités de normalisation pour les courbes de taux (0–1) ---
    # On ne touche PAS à cap_max utilisé pour l’optimisation.
    # --- Capacités de normalisation pour les courbes de taux (0–1) ---
    # On ne touche PAS à cap_max utilisé pour l’optimisation.
    cap_norm = {}
    prod_datas_baseline = result_baseline.get("production_data", [])
    for cfg, site_data in zip(lines_config, prod_datas_baseline):
        location = cfg["location"]
        cumul = site_data["Total Seats made"][1]
        daily = _compute_daily_from_cumul(cumul)
        # on évite de diviser par 0 : si aucune production, on met 1.0
        cap_norm[location] = max(daily) if daily else 1.0
        print(
            f"Capacité de normalisation (prod/jour max) pour {location} : {cap_norm[location]}"
        )


    # 1. Courbes de taux de production (normalisé par ligne avec cap_norm)
    _, baseline_rates_smooth, baseline_global_smooth = compute_line_rate_curves(
        result_baseline,
        lines_config,
        cap_norm,
        window=5,
    )

    # === Vecteur de temps réel issu du moteur de production ===
    # On récupère l'axe des temps utilisé pour "Total Seats made"
    raw_time_vector = result_baseline["production_data"][0]["Total Seats made"][0]

    # Le lissage peut réduire un peu la longueur -> on aligne les deux
    n = min(len(baseline_global_smooth), len(raw_time_vector))
    baseline_global_smooth = baseline_global_smooth[:n]
    raw_time_vector = raw_time_vector[:n]


    # ➜ Normalisation globale : 1 = pic global du Baseline
    global_peak = max(baseline_global_smooth) if baseline_global_smooth else 1.0
    if global_peak <= 0:
        global_peak = 1.0
    baseline_global_norm_full = [x / global_peak for x in baseline_global_smooth]

    # --- WARM-UP : on enlève la montée en régime --------------------
    WARMUP_THRESHOLD = 0.15  # 15 % du pic global

    warmup_idx = 0
    for i, v in enumerate(baseline_global_norm_full):
        if v >= WARMUP_THRESHOLD:
            warmup_idx = i
            break

    # baseline tronquée après warm-up
    baseline_global_norm = baseline_global_norm_full[warmup_idx:]
    time_vector = raw_time_vector[warmup_idx:]  # on garde les jours réels (3,4,...,20)

    # Sécurité : si pour une raison quelconque la courbe est vide
    if not baseline_global_norm:
        baseline_global_norm = baseline_global_norm_full
        time_vector = raw_time_vector
        warmup_idx = 0

    rate_curve_baseline = baseline_global_norm  # utilisé comme référence résilience

    # Tronquer aussi les courbes par ligne pour rester cohérent
    baseline_rates_cut = {
        site: curve[warmup_idx:] for site, curve in baseline_rates_smooth.items()
    }

    scenario_results["Baseline"]["rate_curves"] = {
        "per_line": baseline_rates_cut,   # toujours 0–1 par ligne, post warm-up
        "global": rate_curve_baseline,   # 0–1, pic Baseline = 1, post warm-up
        "time": time_vector,
    }

    # --- 11. Construction d'un signal de performance agrégé (Baseline + Crises) ---

    # KPI 1 : taux de production global normalisé (déjà bien défini)
    kpi_baseline = {
        "prod_rate": rate_curve_baseline,
    }

    # Pondérations : pour l'instant, on met tout sur le taux de prod
    weights_perf = {
        "prod_rate": 1.0,
    }

    perf_baseline = compute_perf_signal(
        kpi_baseline,
        weights=weights_perf,
        window=7,   # lissage plus fort que pour les taux bruts
    )

    # On garde un time_vector cohérent (même découpe que baseline_global_norm)
    time_perf = time_vector[: len(perf_baseline)]

    scenario_results["Baseline"]["perf_signal"] = {
        "global": list(perf_baseline),
        "time": time_perf,
    }
    scenario_results["Baseline"]["global_production"] = list(perf_baseline)
    # 2. Pour chaque scénario de crise : courbes de taux + indicateurs de résilience
    for name, result_crise in crisis_results.items():
        _, crise_rates_smooth, crise_global_smooth = compute_line_rate_curves(
            result_crise,
            lines_config,
            cap_norm,
            window=5,
        )

        # ➜ Appliquer la même normalisation globale que pour le Baseline
        crise_global_norm_full = [x / global_peak for x in crise_global_smooth]

        # on tronque la crise au même warm-up que le Baseline
        crise_global_norm = crise_global_norm_full[warmup_idx:]
        crise_per_line_cut = {
            site: curve[warmup_idx:] for site, curve in crise_rates_smooth.items()
        }

        # alignement des longueurs
        min_len = min(
            len(rate_curve_baseline),
            len(crise_global_norm),
            len(time_vector),
        )
        rate_curve_baseline_aligned = rate_curve_baseline[:min_len]
        rate_curve_crise_aligned = crise_global_norm[:min_len]
        time_vector_aligned = time_vector[:min_len]

        # 2.1 Résilience "comparée au nominal" (baseline vs crise) – sur le taux
        indicators_ref = compute_resilience_indicators(
            rate_curve_baseline_aligned,
            rate_curve_crise_aligned,
            time_vector_aligned,
        )

        # 2.2 Résilience "auto-détection" – sur le taux
        indicators_auto = resilience_on_curve(
            rate_curve_crise_aligned,
            time_vector=time_vector_aligned,
        )

        result_crise["resilience_indicators"] = indicators_ref
        result_crise["resilience_auto_indicators"] = indicators_auto
        result_crise["rate_curves"] = {
            "per_line": crise_per_line_cut,     # 0–1 par ligne, aligné, post warm-up
            "global": rate_curve_crise_aligned, # 0–1, aligné, post warm-up
            "time": time_vector_aligned,
        }

        # --- Signal de performance agrégé pour ce scénario de crise ---
        kpi_crise = {
            "prod_rate": rate_curve_crise_aligned,
        }

        perf_crise = compute_perf_signal(
            kpi_crise,
            weights=weights_perf,   # même pondération pour comparer correctement
            window=7,
        )

        # On aligne la longueur avec le signal baseline
        min_len_perf = min(len(perf_baseline), len(perf_crise))
        perf_baseline_aligned = perf_baseline[:min_len_perf]
        perf_crise_aligned = perf_crise[:min_len_perf]
        time_perf_aligned = time_perf[:min_len_perf]

        # Indicateurs de résilience basés sur la performance agrégée
        indicators_ref_perf = compute_resilience_indicators(
            list(perf_baseline_aligned),
            list(perf_crise_aligned),
            list(time_perf_aligned),
        )
        indicators_auto_perf = resilience_on_curve(
            list(perf_crise_aligned),
            time_vector=list(time_perf_aligned),
        )

        result_crise["resilience_perf_indicators"] = indicators_ref_perf
        result_crise["resilience_perf_auto_indicators"] = indicators_auto_perf
        result_crise["perf_signal"] = {
            "global": list(perf_crise),
            "time": list(time_perf_aligned),
        }
        result_crise["global_production"] = list(perf_crise_aligned)

    # Auto-résilience du baseline lui-même – sur le taux
    scenario_results["Baseline"]["resilience_auto_indicators"] = resilience_on_curve(
        rate_curve_baseline,
        time_vector=time_vector,
    )

    # Auto-résilience sur le signal de performance agrégé (Baseline)
    scenario_results["Baseline"]["resilience_perf_auto_indicators"] = resilience_on_curve(
        list(perf_baseline),
        time_vector=list(time_perf),
    )
 

    # ==================================================
    # Optimisation Résilience
    # ==================================================

    # Étape intermédiaire : vérifier la correspondance des sites
    baseline_capacity_limits_clean = build_capacity_limits_from_cap_max(cap_max)

    print("Type de base_config['capacity_limits']:", type(base_config["capacity_limits"]))
    print("Contenu de base_config['capacity_limits']:", base_config["capacity_limits"])

    # Mapping cohérent avec ce qu'on a utilisé plus haut pour les crises
    # Préparer le dictionnaire de résultats final à retourner
    return {
        "figures": all_figs,
        "lca_fig": fig_lca_fr,
        "production_totals_sum": total_production,
        "lca_fig_total": fig_lca_total,
        "vivant_raw_data": result_vivant_raw,
        "scenario_results": scenario_results,
        "crisis_results": crisis_results,
        "crisis_figures": crisis_all_figs,
        "resilience_optimized": resilience_opt_result,
        "cap_max": cap_max, 
        "lines_config": lines_config
    }

if __name__ == '__main__':
    main_function()
