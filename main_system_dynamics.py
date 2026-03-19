"""PoC supply chain en dynamique des systemes avec focus fournisseurs et tiers.

Le modele represente une chaine multi-noeuds:
- extraction,
- stockages intermediaires,
- transports explicites (delais),
- premieres et secondes transformations,
- distribution,
- stockage a l'arrivee de la ligne de production.

Chaque noeud applique une boucle de reapprovisionnement (demande percue +
correction vers stock cible), ce qui permet d'observer retards, oscillations
et congestions entre fournisseurs et tiers.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import argparse
import math
from typing import Callable


@dataclass
class StageConfig:
    name: str
    initial_inventory: float
    target_inventory: float
    max_order_rate: float
    max_ship_rate: float
    conversion_yield: float = 1.0
    source_capacity: float = 0.0


@dataclass
class SystemDynamicsConfig:
    horizon_days: int = 180
    dt_day: float = 1.0
    initial_demand: float = 50.0
    demand_step_day: int = 60
    demand_step_value: float = 70.0
    smoothing_days: float = 10.0
    inventory_adjust_time: float = 15.0
    transport_1_days: int = 5
    transport_2_days: int = 4
    transport_3_days: int = 3


@dataclass
class SimulationResult:
    series: dict[str, list[float]]
    stages: list[StageConfig]
    lead_times: list[int]


@dataclass
class FrequencyAnalysisResult:
    frequencies_cpd: list[float]
    gain_stock: list[float]
    phase_stock_deg: list[float]
    gain_backlog: list[float]
    phase_backlog_deg: list[float]


def default_stages() -> list[StageConfig]:
    """Chaine de reference: extraction -> transformations -> distribution."""
    return [
        StageConfig("extraction", 300.0, 360.0, 260.0, 220.0, conversion_yield=1.0, source_capacity=160.0),
        StageConfig("stock_amont", 230.0, 270.0, 230.0, 220.0),
        StageConfig("stock_apres_transport_amont", 220.0, 260.0, 220.0, 210.0),
        StageConfig("transformation_1", 190.0, 230.0, 210.0, 190.0, conversion_yield=0.97),
        StageConfig("stock_apres_transformation_1", 180.0, 220.0, 200.0, 190.0),
        StageConfig("stock_apres_transport_t1", 170.0, 210.0, 190.0, 180.0),
        StageConfig("transformation_2", 160.0, 200.0, 180.0, 170.0, conversion_yield=0.95),
        StageConfig("stock_distribution", 160.0, 200.0, 180.0, 170.0),
        StageConfig("distribution", 150.0, 190.0, 170.0, 160.0),
        StageConfig("stock_arrivee_ligne_production", 170.0, 230.0, 180.0, 170.0),
    ]


def default_lead_times(cfg: SystemDynamicsConfig, n_stages: int) -> list[int]:
    """Delais de transport explicites entre les noeuds."""
    if n_stages != 10:
        raise ValueError("Le profil de transport par defaut attend 10 noeuds.")
    return [0, cfg.transport_1_days, 0, 0, cfg.transport_2_days, 0, 0, 0, cfg.transport_3_days]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def slugify(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name.lower()).strip("_")


def customer_demand(day: int, cfg: SystemDynamicsConfig) -> float:
    """Demande client avec palier (step)."""
    return cfg.initial_demand if day < cfg.demand_step_day else cfg.demand_step_value


def run_simulation(
    cfg: SystemDynamicsConfig,
    demand_fn: Callable[[int, SystemDynamicsConfig], float] | None = None,
) -> SimulationResult:
    """Simulation stock-flux multi-tiers."""
    if cfg.smoothing_days <= 0:
        raise ValueError("smoothing_days doit etre > 0")
    if cfg.inventory_adjust_time <= 0:
        raise ValueError("inventory_adjust_time doit etre > 0")

    stages = default_stages()
    n_stages = len(stages)
    lead_times = default_lead_times(cfg, n_stages)

    if any(lead < 0 for lead in lead_times):
        raise ValueError("Tous les delais de transport doivent etre >= 0")
    for stage in stages:
        if stage.conversion_yield <= 0:
            raise ValueError(f"conversion_yield invalide pour {stage.name}")

    inventories = [stage.initial_inventory for stage in stages]
    expected_demand = [cfg.initial_demand for _ in stages]
    customer_backlog = 0.0
    link_backlogs = [0.0] * (n_stages - 1)

    pipelines: list[deque[float] | None] = []
    for lead in lead_times:
        if lead > 0:
            pipelines.append(deque([cfg.initial_demand] * lead, maxlen=lead))
        else:
            pipelines.append(None)

    series: dict[str, list[float]] = {
        "day": [],
        "customer_demand": [],
        "customer_shipment": [],
        "customer_backlog": [],
        "extraction_output": [],
        "orders_total": [],
        "shipments_total": [],
        "in_transit_total": [],
    }

    stage_slugs = [slugify(stage.name) for stage in stages]
    link_slugs = [f"{stage_slugs[i]}_to_{stage_slugs[i + 1]}" for i in range(n_stages - 1)]

    for slug in stage_slugs:
        series[f"inventory_{slug}"] = []
    for i in range(1, n_stages):
        series[f"order_{stage_slugs[i]}"] = []
    for link_slug in link_slugs:
        series[f"shipment_{link_slug}"] = []
        series[f"delivery_{link_slug}"] = []
        series[f"backlog_{link_slug}"] = []
        series[f"in_transit_{link_slug}"] = []

    demand_signal = demand_fn or customer_demand

    for day in range(cfg.horizon_days):
        demand = max(0.0, demand_signal(day, cfg))
        deliveries = [0.0] * (n_stages - 1)

        # 1) Receptions dues aux transports en cours
        for i in range(n_stages - 1):
            pipe = pipelines[i]
            if pipe is not None:
                delivery = pipe.popleft()
                deliveries[i] = delivery
                inventories[i + 1] += delivery

        # 2) Service de la demande client sur le stock a l'arrivee ligne production
        to_ship_customer = demand + customer_backlog
        customer_shipment = min(inventories[-1], to_ship_customer)
        inventories[-1] -= customer_shipment
        customer_backlog = max(0.0, to_ship_customer - customer_shipment)

        # 3) Calcul des commandes (pull) de l'aval vers l'amont
        orders = [0.0] * n_stages
        for j in range(n_stages - 1, 0, -1):
            downstream_signal = demand if j == n_stages - 1 else orders[j + 1]
            expected_demand[j] += (downstream_signal - expected_demand[j]) * (cfg.dt_day / cfg.smoothing_days)
            inventory_gap = stages[j].target_inventory - inventories[j]
            desired_order = expected_demand[j] + (inventory_gap / cfg.inventory_adjust_time)
            orders[j] = clamp(desired_order, 0.0, stages[j].max_order_rate)

        # 4) Extraction amont pilotee par la demande percue du noeud suivant
        expected_demand[0] += (orders[1] - expected_demand[0]) * (cfg.dt_day / cfg.smoothing_days)
        extraction_control = expected_demand[0] + (stages[0].target_inventory - inventories[0]) / cfg.inventory_adjust_time
        extraction_output = clamp(extraction_control, 0.0, stages[0].source_capacity or stages[0].max_ship_rate)
        inventories[0] += extraction_output

        # 5) Expedition amont -> aval avec backlogs internes et rendement de transformation
        shipments = [0.0] * (n_stages - 1)
        for i in range(n_stages - 1):
            stage = stages[i]
            request = orders[i + 1] + link_backlogs[i]
            max_output_from_stock = inventories[i] * stage.conversion_yield
            ship_capacity = min(stage.max_ship_rate, max_output_from_stock)
            shipment = min(request, ship_capacity)
            shipments[i] = shipment

            consumed_stock = shipment / stage.conversion_yield
            inventories[i] = max(0.0, inventories[i] - consumed_stock)
            link_backlogs[i] = max(0.0, request - shipment)

            pipe = pipelines[i]
            if pipe is None:
                deliveries[i] = shipment
                inventories[i + 1] += shipment
            else:
                pipe.append(shipment)

        # 6) Enregistrement des series
        series["day"].append(day)
        series["customer_demand"].append(demand)
        series["customer_shipment"].append(customer_shipment)
        series["customer_backlog"].append(customer_backlog)
        series["extraction_output"].append(extraction_output)
        series["orders_total"].append(sum(orders[1:]))
        series["shipments_total"].append(sum(shipments))

        in_transit_total = 0.0
        for i, slug in enumerate(stage_slugs):
            series[f"inventory_{slug}"].append(inventories[i])
            if i > 0:
                series[f"order_{slug}"].append(orders[i])

        for i, link_slug in enumerate(link_slugs):
            pipe = pipelines[i]
            in_transit = float(sum(pipe)) if pipe is not None else 0.0
            in_transit_total += in_transit
            series[f"shipment_{link_slug}"].append(shipments[i])
            series[f"delivery_{link_slug}"].append(deliveries[i])
            series[f"backlog_{link_slug}"].append(link_backlogs[i])
            series[f"in_transit_{link_slug}"].append(in_transit)

        series["in_transit_total"].append(in_transit_total)

    return SimulationResult(series=series, stages=stages, lead_times=lead_times)


def _log_spaced_frequencies(freq_min: float, freq_max: float, n_points: int) -> list[float]:
    if n_points < 1:
        raise ValueError("freq_points doit etre >= 1")
    if freq_min <= 0 or freq_max <= 0:
        raise ValueError("freq_min/freq_max doivent etre > 0")
    if freq_max < freq_min:
        raise ValueError("freq_max doit etre >= freq_min")
    if n_points == 1:
        return [freq_min]
    ratio = (freq_max / freq_min) ** (1.0 / (n_points - 1))
    return [freq_min * (ratio**i) for i in range(n_points)]


def _estimate_amplitude_phase(signal: list[float], frequency_cpd: float, dt_day: float) -> tuple[float, float]:
    n_samples = len(signal)
    if n_samples < 4:
        raise ValueError("Pas assez d'echantillons pour estimer amplitude/phase")
    omega = 2.0 * math.pi * frequency_cpd
    mean_value = sum(signal) / n_samples
    sin_proj = 0.0
    cos_proj = 0.0
    for k, value in enumerate(signal):
        centered = value - mean_value
        theta = omega * k * dt_day
        sin_proj += centered * math.sin(theta)
        cos_proj += centered * math.cos(theta)
    sin_coeff = (2.0 / n_samples) * sin_proj
    cos_coeff = (2.0 / n_samples) * cos_proj
    amplitude = math.sqrt(sin_coeff * sin_coeff + cos_coeff * cos_coeff)
    phase_deg = math.degrees(math.atan2(cos_coeff, sin_coeff))
    return amplitude, phase_deg


def _wrap_phase_deg(phase_deg: float) -> float:
    wrapped = phase_deg
    while wrapped <= -180.0:
        wrapped += 360.0
    while wrapped > 180.0:
        wrapped -= 360.0
    return wrapped


def analyze_frequency_response(
    cfg: SystemDynamicsConfig,
    freq_min: float,
    freq_max: float,
    freq_points: int,
    demand_amplitude: float,
    warmup_cycles: int,
    measure_cycles: int,
) -> FrequencyAnalysisResult:
    """Analyse frequentielle empirique (gain/phase) du modele discret."""
    if demand_amplitude <= 0:
        raise ValueError("demand_amplitude doit etre > 0")
    if warmup_cycles < 0:
        raise ValueError("warmup_cycles doit etre >= 0")
    if measure_cycles < 2:
        raise ValueError("measure_cycles doit etre >= 2")

    nyquist_cpd = 0.5 / cfg.dt_day
    if freq_max >= nyquist_cpd:
        raise ValueError(
            f"freq_max={freq_max:.4f} doit etre < Nyquist={nyquist_cpd:.4f} cycles/jour (dt={cfg.dt_day})"
        )

    frequencies = _log_spaced_frequencies(freq_min, freq_max, freq_points)
    gain_stock: list[float] = []
    phase_stock_deg: list[float] = []
    gain_backlog: list[float] = []
    phase_backlog_deg: list[float] = []

    base_demand = cfg.initial_demand
    for frequency in frequencies:
        period_days = 1.0 / frequency
        horizon_days = int(math.ceil((warmup_cycles + measure_cycles) * period_days))
        horizon_days = max(horizon_days, 60)
        measure_samples = int(math.ceil(measure_cycles * period_days))
        measure_samples = max(measure_samples, 30)

        cfg_run = replace(
            cfg,
            horizon_days=horizon_days,
            demand_step_day=horizon_days + 1,
            demand_step_value=base_demand,
        )

        def sinusoidal_demand(day: int, run_cfg: SystemDynamicsConfig, freq: float = frequency) -> float:
            theta = 2.0 * math.pi * freq * day * run_cfg.dt_day
            return base_demand + demand_amplitude * math.sin(theta)

        result = run_simulation(cfg_run, demand_fn=sinusoidal_demand)
        series = result.series
        stage_slugs = [slugify(stage.name) for stage in result.stages]
        stock_key = f"inventory_{stage_slugs[-1]}"

        start_index = max(0, len(series["day"]) - measure_samples)
        input_window = series["customer_demand"][start_index:]
        stock_window = series[stock_key][start_index:]
        backlog_window = series["customer_backlog"][start_index:]

        input_amp, input_phase = _estimate_amplitude_phase(input_window, frequency, cfg.dt_day)
        stock_amp, stock_phase = _estimate_amplitude_phase(stock_window, frequency, cfg.dt_day)
        backlog_amp, backlog_phase = _estimate_amplitude_phase(backlog_window, frequency, cfg.dt_day)

        reference_amp = max(input_amp, 1e-12)
        gain_stock.append(stock_amp / reference_amp)
        gain_backlog.append(backlog_amp / reference_amp)
        phase_stock_deg.append(_wrap_phase_deg(stock_phase - input_phase))
        phase_backlog_deg.append(_wrap_phase_deg(backlog_phase - input_phase))

    return FrequencyAnalysisResult(
        frequencies_cpd=frequencies,
        gain_stock=gain_stock,
        phase_stock_deg=phase_stock_deg,
        gain_backlog=gain_backlog,
        phase_backlog_deg=phase_backlog_deg,
    )


def plot_frequency_response(result: FrequencyAnalysisResult, output_path: str | None = None) -> None:
    """Trace un diagramme de Bode (gain/phase) sur la chaine discretisee."""
    import matplotlib.pyplot as plt

    eps = 1e-12
    gain_stock_db = [20.0 * math.log10(max(value, eps)) for value in result.gain_stock]
    gain_backlog_db = [20.0 * math.log10(max(value, eps)) for value in result.gain_backlog]

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    axes[0].semilogx(result.frequencies_cpd, gain_stock_db, marker="o", label="Gain stock arrivee ligne")
    axes[0].semilogx(result.frequencies_cpd, gain_backlog_db, marker="o", label="Gain backlog client")
    axes[0].set_ylabel("Gain (dB)")
    axes[0].set_title("Analyse frequentielle (Bode) - modele discret")
    axes[0].legend()
    axes[0].grid(alpha=0.3, which="both")

    axes[1].semilogx(result.frequencies_cpd, result.phase_stock_deg, marker="o", label="Phase stock arrivee ligne")
    axes[1].semilogx(result.frequencies_cpd, result.phase_backlog_deg, marker="o", label="Phase backlog client")
    axes[1].set_ylabel("Phase (deg)")
    axes[1].set_xlabel("Frequence (cycles/jour)")
    axes[1].legend()
    axes[1].grid(alpha=0.3, which="both")

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=160)
    plt.show()


def plot_results(result: SimulationResult, output_path: str | None = None) -> None:
    """Affiche les signaux principaux et les variations de stock."""
    import matplotlib.pyplot as plt

    series = result.series
    days = series["day"]
    stage_slugs = [slugify(stage.name) for stage in result.stages]
    final_slug = stage_slugs[-1]
    distribution_slug = slugify("distribution")
    transformation_1_slug = slugify("transformation_1")
    transformation_2_slug = slugify("transformation_2")

    stock_levels = {slug: series[f"inventory_{slug}"] for slug in stage_slugs}
    stock_variations = {}
    for slug, values in stock_levels.items():
        variations = [0.0]
        for i in range(1, len(values)):
            variations.append(values[i] - values[i - 1])
        stock_variations[slug] = variations

    fig, axes = plt.subplots(5, 1, figsize=(13, 15), sharex=True)

    axes[0].plot(days, series[f"inventory_{final_slug}"], label="Stock arrivee ligne production", linewidth=2)
    axes[0].plot(days, series["customer_backlog"], label="Backlog client", linewidth=2)
    axes[0].set_ylabel("Unites")
    axes[0].set_title("Service aval")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(days, series["customer_demand"], label="Demande client", linestyle="--")
    axes[1].plot(days, series["customer_shipment"], label="Livraisons client")
    axes[1].plot(days, series[f"order_{final_slug}"], label="Commande amont (ligne prod)")
    axes[1].set_ylabel("Unites/jour")
    axes[1].set_title("Demande vs approvisionnement ligne production")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    axes[2].plot(days, series["extraction_output"], label="Extraction")
    axes[2].plot(days, series[f"inventory_{transformation_1_slug}"], label="Stock transfo 1")
    axes[2].plot(days, series[f"inventory_{transformation_2_slug}"], label="Stock transfo 2")
    axes[2].plot(days, series[f"inventory_{distribution_slug}"], label="Stock distribution")
    axes[2].set_ylabel("Unites")
    axes[2].set_title("Etats des noeuds fournisseurs/tiers")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    for stage, slug in zip(result.stages, stage_slugs):
        axes[3].plot(days, stock_levels[slug], label=stage.name)
    axes[3].set_ylabel("Unites")
    axes[3].set_title("Niveaux de stock par noeud")
    axes[3].legend(ncol=2, fontsize=8)
    axes[3].grid(alpha=0.3)

    for stage, slug in zip(result.stages, stage_slugs):
        axes[4].plot(days, stock_variations[slug], label=stage.name)
    axes[4].axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    axes[4].set_ylabel("Delta stock/jour")
    axes[4].set_xlabel("Jour")
    axes[4].set_title("Variations de stock par noeud")
    axes[4].legend(ncol=2, fontsize=8)
    axes[4].grid(alpha=0.3)

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=160)
    plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PoC supply chain multi-tiers en dynamique des systemes")
    parser.add_argument("--horizon", type=int, default=180, help="Horizon de simulation (jours)")
    parser.add_argument("--step-day", type=int, default=60, help="Jour de changement de demande")
    parser.add_argument("--step-demand", type=float, default=70.0, help="Nouvelle demande apres step")
    parser.add_argument("--lead-time", type=int, default=None, help="Compatibilite: applique le meme delai aux 3 transports")
    parser.add_argument("--transport-1", type=int, default=5, help="Delai transport extraction -> transfo 1")
    parser.add_argument("--transport-2", type=int, default=4, help="Delai transport transfo 1 -> transfo 2")
    parser.add_argument("--transport-3", type=int, default=3, help="Delai transport distribution -> ligne production")
    parser.add_argument(
        "--plot-file",
        type=str,
        default="supply_chain_stocks.png",
        help="Nom du fichier PNG de sortie quand --plot est active",
    )
    parser.add_argument("--plot", action="store_true", help="Affiche les graphiques (necessite matplotlib)")
    parser.add_argument("--freq-analysis", action="store_true", help="Lance une analyse frequentielle (Bode)")
    parser.add_argument("--freq-min", type=float, default=0.005, help="Frequence min (cycles/jour)")
    parser.add_argument("--freq-max", type=float, default=0.20, help="Frequence max (cycles/jour)")
    parser.add_argument("--freq-points", type=int, default=12, help="Nombre de frequences testees")
    parser.add_argument("--freq-amplitude", type=float, default=5.0, help="Amplitude sinusoidale de demande")
    parser.add_argument("--freq-warmup-cycles", type=int, default=3, help="Cycles ignores (transitoire)")
    parser.add_argument("--freq-measure-cycles", type=int, default=6, help="Cycles utilises pour mesure gain/phase")
    parser.add_argument(
        "--freq-file",
        type=str,
        default="supply_chain_bode.png",
        help="Nom du fichier PNG de sortie pour l'analyse frequentielle",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.lead_time is not None:
        transport_1 = transport_2 = transport_3 = args.lead_time
    else:
        transport_1 = args.transport_1
        transport_2 = args.transport_2
        transport_3 = args.transport_3

    cfg = SystemDynamicsConfig(
        horizon_days=args.horizon,
        demand_step_day=args.step_day,
        demand_step_value=args.step_demand,
        transport_1_days=transport_1,
        transport_2_days=transport_2,
        transport_3_days=transport_3,
    )

    result = run_simulation(cfg)
    series = result.series
    stages = result.stages
    stage_slugs = [slugify(stage.name) for stage in stages]
    final_stock_key = f"inventory_{stage_slugs[-1]}"

    backlog_keys = [key for key in series if key.startswith("backlog_")]
    max_internal_backlog = max(max(series[key]) for key in backlog_keys) if backlog_keys else 0.0

    print("\n=== Resume PoC Supply Chain Multi-Tiers (System Dynamics) ===")
    print(f"Horizon: {cfg.horizon_days} jours")
    print(f"Demande initiale: {cfg.initial_demand:.1f} u/j")
    print(f"Demande apres step: {cfg.demand_step_value:.1f} u/j (jour {cfg.demand_step_day})")
    print(
        "Transports (jours): "
        f"extraction->t1={cfg.transport_1_days}, "
        f"t1->t2={cfg.transport_2_days}, "
        f"distribution->ligne={cfg.transport_3_days}"
    )
    print(f"Stock final (arrivee ligne): {series[final_stock_key][-1]:.1f} u")
    print(f"Backlog client final: {series['customer_backlog'][-1]:.1f} u")
    print(f"Backlog client max: {max(series['customer_backlog']):.1f} u")
    print(f"Backlog interne max (tiers): {max_internal_backlog:.1f} u")

    print("\nStocks finaux par noeud:")
    for stage, slug in zip(stages, stage_slugs):
        print(f"- {stage.name}: {series[f'inventory_{slug}'][-1]:.1f} u")

    if args.plot:
        plot_results(result, output_path=args.plot_file)
        print(f"\nPlot enregistre: {args.plot_file}")

    if args.freq_analysis:
        freq_result = analyze_frequency_response(
            cfg=cfg,
            freq_min=args.freq_min,
            freq_max=args.freq_max,
            freq_points=args.freq_points,
            demand_amplitude=args.freq_amplitude,
            warmup_cycles=args.freq_warmup_cycles,
            measure_cycles=args.freq_measure_cycles,
        )
        nyquist_cpd = 0.5 / cfg.dt_day
        print("\n=== Analyse frequentielle (Bode) ===")
        print(
            f"Plage: {args.freq_min:.4f} -> {args.freq_max:.4f} cycles/jour "
            f"(Nyquist={nyquist_cpd:.4f}, points={args.freq_points})"
        )
        print("f(c/j)\tGainStock(dB)\tPhaseStock(deg)\tGainBacklog(dB)\tPhaseBacklog(deg)")
        for f_cpd, g_s, p_s, g_b, p_b in zip(
            freq_result.frequencies_cpd,
            freq_result.gain_stock,
            freq_result.phase_stock_deg,
            freq_result.gain_backlog,
            freq_result.phase_backlog_deg,
        ):
            gain_stock_db = 20.0 * math.log10(max(g_s, 1e-12))
            gain_backlog_db = 20.0 * math.log10(max(g_b, 1e-12))
            print(f"{f_cpd:.4f}\t{gain_stock_db:>12.2f}\t{p_s:>15.1f}\t{gain_backlog_db:>14.2f}\t{p_b:>16.1f}")

        plot_frequency_response(freq_result, output_path=args.freq_file)
        print(f"\nBode enregistre: {args.freq_file}")


if __name__ == "__main__":
    main()
