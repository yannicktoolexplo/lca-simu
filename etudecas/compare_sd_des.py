"""PoC comparatif SD vs DES.

But:
- montrer quand SD et DES sont equivalents (cas agrege deterministe),
- montrer ce que DES apporte (variabilite, risque operationnel),
- montrer ce que SD apporte (exploration rapide de politiques).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import argparse
import random
import statistics
import time

import numpy as np

from main_system_dynamics import SystemDynamicsConfig, run_simulation, slugify
from main_supply_chain_des import DESConfig, SupplyChainDES
from supply_graph_tools import derive_supply_graph_summary


@dataclass
class CompareConfig:
    horizon_days: int = 180
    step_day: int = 60
    step_demand: float = 80.0
    replications: int = 30
    seed: int = 7
    delay_noise: float = 0.30
    disruption_prob: float = 0.08
    disruption_factor: float = 0.50
    transport_1_days: int = 5
    transport_2_days: int = 4
    transport_3_days: int = 3
    plot_file: str = "sd_des_tradeoff.png"


class StochasticSupplyChainDES(SupplyChainDES):
    """DES operationnel avec aleas de transport et de capacite."""

    def __init__(
        self,
        cfg: DESConfig,
        rng: random.Random,
        delay_noise: float,
        disruption_prob: float,
        disruption_factor: float,
    ) -> None:
        self.rng = rng
        self.delay_noise = max(0.0, delay_noise)
        self.disruption_prob = max(0.0, min(1.0, disruption_prob))
        self.disruption_factor = max(0.0, min(1.0, disruption_factor))
        super().__init__(cfg)

    def _ship_all_links(self) -> None:
        for i in range(self.n_stages - 1):
            source_cfg = self.stages_cfg[i]
            source_state = self.stage_states[i]
            link_state = self.link_states[i]

            request = self.orders[i + 1] + link_state.backlog
            max_output_from_stock = source_state.inventory * source_cfg.conversion_yield
            ship_capacity = min(source_cfg.max_ship_rate, max_output_from_stock)

            # Capacite aleatoire pour simuler indisponibilites operationnelles.
            if self.rng.random() < self.disruption_prob:
                ship_capacity *= self.disruption_factor

            shipment = min(request, ship_capacity)
            self.daily_shipments[i] += shipment

            consumed_stock = shipment / source_cfg.conversion_yield
            source_state.inventory = max(0.0, source_state.inventory - consumed_stock)
            link_state.backlog = max(0.0, request - shipment)
            self._record_event_state()

            if shipment > 0:
                self.shipment_event_times.append(float(self.env.now))
                self._dispatch_delivery(i, shipment)

    def _dispatch_delivery(self, link_index: int, quantity: float) -> None:
        link_state = self.link_states[link_index]
        base_lead = link_state.lead_time_days
        if base_lead <= 0:
            self._receive_delivery(link_index, quantity, has_been_in_transit=False)
            return

        sigma = max(0.1, self.delay_noise * base_lead)
        sampled_lead = max(0.0, self.rng.gauss(base_lead, sigma))
        if sampled_lead <= 1e-9:
            self._receive_delivery(link_index, quantity, has_been_in_transit=False)
            return

        link_state.in_transit += quantity
        delay = sampled_lead * self.cfg.dt_day
        self.env.process(self._deliver_after(link_index, quantity, delay))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare SD vs DES sur un PoC supply chain")
    parser.add_argument("--horizon", type=int, default=180, help="Horizon simulation (jours)")
    parser.add_argument("--step-day", type=int, default=60, help="Jour du step de demande")
    parser.add_argument("--step-demand", type=float, default=80.0, help="Demande apres step")
    parser.add_argument("--replications", type=int, default=30, help="Nombre de repetitions DES stochastique")
    parser.add_argument("--seed", type=int, default=7, help="Seed global")
    parser.add_argument("--delay-noise", type=float, default=0.30, help="Bruit relatif des delais transport")
    parser.add_argument("--disruption-prob", type=float, default=0.08, help="Probabilite journaliere de capacite degradee")
    parser.add_argument("--disruption-factor", type=float, default=0.50, help="Facteur de capacite en cas de disruption")
    parser.add_argument("--transport-1", type=int, default=5, help="Delai transport amont -> manufacturer")
    parser.add_argument("--transport-2", type=int, default=4, help="Delai transport manufacturer -> distribution")
    parser.add_argument("--transport-3", type=int, default=3, help="Delai transport distribution -> client")
    parser.add_argument("--use-graph", action="store_true", help="Calibre les delais de transport depuis knowledge_graph/actor_coords")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json", help="Path to knowledge graph")
    parser.add_argument("--coords", type=str, default="actor_coords.json", help="Path to actor coordinates")
    parser.add_argument("--plot-file", type=str, default="sd_des_tradeoff.png", help="Fichier PNG de synthese")
    return parser.parse_args()


def _make_sd_cfg(cfg: CompareConfig) -> SystemDynamicsConfig:
    return SystemDynamicsConfig(
        horizon_days=cfg.horizon_days,
        demand_step_day=cfg.step_day,
        demand_step_value=cfg.step_demand,
        transport_1_days=cfg.transport_1_days,
        transport_2_days=cfg.transport_2_days,
        transport_3_days=cfg.transport_3_days,
    )


def _make_des_cfg(cfg: CompareConfig, dynamic: bool = True) -> DESConfig:
    return DESConfig(
        horizon_days=cfg.horizon_days,
        demand_step_day=cfg.step_day,
        demand_step_value=cfg.step_demand,
        enable_dynamics=dynamic,
        transport_1_days=cfg.transport_1_days,
        transport_2_days=cfg.transport_2_days,
        transport_3_days=cfg.transport_3_days,
    )


def _deterministic_equivalence(cfg: CompareConfig) -> tuple[dict[str, list[float]], dict[str, list[float]], float]:
    sd_cfg = _make_sd_cfg(cfg)
    des_cfg = _make_des_cfg(cfg, dynamic=True)

    sd_series = run_simulation(sd_cfg).series
    des_series = SupplyChainDES(des_cfg).run().series

    stage_names = [
        "extraction",
        "stock_amont",
        "stock_apres_transport_amont",
        "transformation_1",
        "stock_apres_transformation_1",
        "stock_apres_transport_t1",
        "transformation_2",
        "stock_distribution",
        "distribution",
        "stock_arrivee_ligne_production",
    ]
    keys = [
        "customer_backlog",
        "customer_shipment",
        "orders_total",
        "shipments_total",
        "in_transit_total",
    ] + [f"inventory_{slugify(name)}" for name in stage_names]

    max_abs_diff = 0.0
    for key in keys:
        diff = max(abs(a - b) for a, b in zip(sd_series[key], des_series[key]))
        max_abs_diff = max(max_abs_diff, diff)

    return sd_series, des_series, max_abs_diff


def _run_des_replication(base_cfg: DESConfig, rng: random.Random, cfg: CompareConfig) -> dict[str, object]:
    result = StochasticSupplyChainDES(
        base_cfg,
        rng=rng,
        delay_noise=cfg.delay_noise,
        disruption_prob=cfg.disruption_prob,
        disruption_factor=cfg.disruption_factor,
    ).run()
    series = result.series
    total_demand = sum(series["customer_demand"])
    total_shipped = sum(series["customer_shipment"])
    service_level = (total_shipped / total_demand) if total_demand > 0 else 1.0
    max_backlog = max(series["customer_backlog"])
    days_backlog = sum(1 for value in series["customer_backlog"] if value > 1e-9)
    return {
        "series": series,
        "service_level": service_level,
        "max_backlog": max_backlog,
        "days_backlog": days_backlog,
    }


def _des_stochastic_study(cfg: CompareConfig) -> dict[str, object]:
    base_des_cfg = _make_des_cfg(cfg, dynamic=True)
    rng_master = random.Random(cfg.seed)

    backlog_matrix = []
    service_levels = []
    max_backlogs = []
    days_backlog = []

    t0 = time.perf_counter()
    for _ in range(cfg.replications):
        seed = rng_master.randint(1, 10_000_000)
        rep = _run_des_replication(base_des_cfg, random.Random(seed), cfg)
        backlog_matrix.append(rep["series"]["customer_backlog"])
        service_levels.append(rep["service_level"])
        max_backlogs.append(rep["max_backlog"])
        days_backlog.append(rep["days_backlog"])
    elapsed = time.perf_counter() - t0

    backlog_array = np.array(backlog_matrix)
    p10 = np.percentile(backlog_array, 10, axis=0).tolist()
    p50 = np.percentile(backlog_array, 50, axis=0).tolist()
    p90 = np.percentile(backlog_array, 90, axis=0).tolist()

    return {
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "service_levels": service_levels,
        "max_backlogs": max_backlogs,
        "days_backlog": days_backlog,
        "elapsed_sec": elapsed,
    }


def _sd_policy_sweep(cfg: CompareConfig) -> dict[str, object]:
    sd_base = _make_sd_cfg(cfg)
    adjust_times = [6, 8, 10, 12, 15, 18, 22, 28]

    t0 = time.perf_counter()
    max_backlogs = []
    avg_backlogs = []
    for tau in adjust_times:
        run_cfg = replace(sd_base, inventory_adjust_time=float(tau))
        series = run_simulation(run_cfg).series
        max_backlogs.append(max(series["customer_backlog"]))
        avg_backlogs.append(statistics.fmean(series["customer_backlog"]))
    elapsed = time.perf_counter() - t0

    return {
        "adjust_times": adjust_times,
        "max_backlogs": max_backlogs,
        "avg_backlogs": avg_backlogs,
        "elapsed_sec": elapsed,
    }


def _des_policy_cost_indicator(cfg: CompareConfig) -> dict[str, object]:
    """Petit indicateur de cout d'analyse DES: moins de points, avec repetitions."""
    adjust_times = [8, 15, 22]
    replications = max(6, cfg.replications // 5)
    base_cfg = _make_des_cfg(cfg, dynamic=True)
    rng_master = random.Random(cfg.seed + 1234)

    t0 = time.perf_counter()
    mean_max_backlogs = []
    for tau in adjust_times:
        values = []
        for _ in range(replications):
            seed = rng_master.randint(1, 10_000_000)
            run_cfg = replace(base_cfg, inventory_adjust_time=float(tau))
            rep = _run_des_replication(run_cfg, random.Random(seed), cfg)
            values.append(rep["max_backlog"])
        mean_max_backlogs.append(statistics.fmean(values))
    elapsed = time.perf_counter() - t0

    return {
        "adjust_times": adjust_times,
        "mean_max_backlogs": mean_max_backlogs,
        "replications": replications,
        "elapsed_sec": elapsed,
    }


def _format_pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def plot_summary(
    cfg: CompareConfig,
    sd_series: dict[str, list[float]],
    des_series: dict[str, list[float]],
    max_diff: float,
    des_stochastic: dict[str, object],
    sd_sweep: dict[str, object],
    des_cost: dict[str, object],
    output_path: str,
) -> None:
    import matplotlib.pyplot as plt

    days = sd_series["day"]
    stock_key = f"inventory_{slugify('stock_arrivee_ligne_production')}"

    p10 = des_stochastic["p10"]
    p50 = des_stochastic["p50"]
    p90 = des_stochastic["p90"]
    service_levels = des_stochastic["service_levels"]
    max_backlogs = des_stochastic["max_backlogs"]
    days_backlog = des_stochastic["days_backlog"]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    ax.plot(days, sd_series[stock_key], label="SD stock arrivee", linewidth=2)
    ax.step(days, des_series[stock_key], where="post", label="DES stock arrivee (det.)", linewidth=1.7)
    ax.plot(days, sd_series["customer_backlog"], label="SD backlog client", alpha=0.8)
    ax.step(days, des_series["customer_backlog"], where="post", label="DES backlog (det.)", alpha=0.8)
    ax.set_title("A) Cas deterministe: equivalence SD ~= DES")
    ax.set_xlabel("Jour")
    ax.set_ylabel("Unites")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    ax.text(
        0.02,
        0.98,
        f"Max |SD-DES| = {max_diff:.2e}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "0.8"},
    )

    ax = axes[0, 1]
    ax.fill_between(days, p10, p90, alpha=0.25, label="DES stochastique P10-P90")
    ax.plot(days, p50, label="DES stochastique mediane")
    ax.plot(days, sd_series["customer_backlog"], linestyle="--", label="SD backlog (deterministe)")
    ax.set_title("B) Apport DES: distribution du risque backlog")
    ax.set_xlabel("Jour")
    ax.set_ylabel("Backlog client")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    ax.plot(sd_sweep["adjust_times"], sd_sweep["max_backlogs"], marker="o", label="SD max backlog")
    ax.plot(sd_sweep["adjust_times"], sd_sweep["avg_backlogs"], marker="o", label="SD backlog moyen")
    ax.scatter(
        des_cost["adjust_times"],
        des_cost["mean_max_backlogs"],
        marker="x",
        s=80,
        label=f"DES mean max backlog ({des_cost['replications']} reps/pt)",
    )
    ax.set_title("C) Apport SD: balayage rapide de politiques")
    ax.set_xlabel("Inventory adjust time (jours)")
    ax.set_ylabel("Backlog (unites)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    ax.axis("off")
    prob_backlog = sum(1 for value in max_backlogs if value > 0.0) / len(max_backlogs)
    text = "\n".join(
        [
            "Lecture PoC:",
            "",
            "DES apporte (operationnel):",
            f"- Risque backlog (P95 max): {np.percentile(max_backlogs, 95):.1f} u",
            f"- Prob. backlog > 0: {_format_pct(prob_backlog)}",
            f"- Service level median: {_format_pct(float(np.percentile(service_levels, 50)))}",
            f"- Jours backlog median: {np.percentile(days_backlog, 50):.0f} j",
            "",
            "SD apporte (strategie/politique):",
            f"- 8 policies evaluees en {sd_sweep['elapsed_sec']:.2f}s",
            f"- Vue deterministe structurelle des boucles",
            "",
            "Cout DES pour explorer des politiques:",
            f"- 3 policies x {des_cost['replications']} reps en {des_cost['elapsed_sec']:.2f}s",
            "",
            f"Etude DES stochastique: {cfg.replications} reps en {des_stochastic['elapsed_sec']:.2f}s",
        ]
    )
    ax.text(0.0, 1.0, text, va="top", ha="left")

    plt.tight_layout()
    fig.savefig(output_path, dpi=170)
    plt.show()


def main() -> None:
    args = parse_args()
    transport_1 = args.transport_1
    transport_2 = args.transport_2
    transport_3 = args.transport_3
    graph_summary = None
    if args.use_graph:
        graph_summary = derive_supply_graph_summary(args.graph, args.coords)
        transport_1 = graph_summary.suggested_transport_days["transport_1_days"]
        transport_2 = graph_summary.suggested_transport_days["transport_2_days"]
        transport_3 = graph_summary.suggested_transport_days["transport_3_days"]

    cfg = CompareConfig(
        horizon_days=args.horizon,
        step_day=args.step_day,
        step_demand=args.step_demand,
        replications=args.replications,
        seed=args.seed,
        delay_noise=args.delay_noise,
        disruption_prob=args.disruption_prob,
        disruption_factor=args.disruption_factor,
        transport_1_days=transport_1,
        transport_2_days=transport_2,
        transport_3_days=transport_3,
        plot_file=args.plot_file,
    )

    sd_series, des_series, max_diff = _deterministic_equivalence(cfg)
    des_stochastic = _des_stochastic_study(cfg)
    sd_sweep = _sd_policy_sweep(cfg)
    des_cost = _des_policy_cost_indicator(cfg)

    print("\n=== PoC SD vs DES ===")
    print(
        "Transports (jours): "
        f"{cfg.transport_1_days}, {cfg.transport_2_days}, {cfg.transport_3_days}"
    )
    if graph_summary is not None:
        print(
            f"Calibration graphe: actors={graph_summary.actor_count}, "
            f"supply_edges={graph_summary.supply_edge_count}"
        )
    print(f"Equivalence SD/DES deterministe: max |diff| = {max_diff:.3e}")
    print(
        f"DES stochastique: {cfg.replications} repetitions, "
        f"P95(max backlog)={np.percentile(des_stochastic['max_backlogs'], 95):.1f} u, "
        f"service median={100*np.percentile(des_stochastic['service_levels'], 50):.1f}%"
    )
    print(f"Balayage SD (8 policies): {sd_sweep['elapsed_sec']:.2f}s")
    print(
        f"Balayage DES indicatif (3 policies x {des_cost['replications']} reps): "
        f"{des_cost['elapsed_sec']:.2f}s"
    )

    plot_summary(
        cfg=cfg,
        sd_series=sd_series,
        des_series=des_series,
        max_diff=max_diff,
        des_stochastic=des_stochastic,
        sd_sweep=sd_sweep,
        des_cost=des_cost,
        output_path=cfg.plot_file,
    )
    print(f"\nPlot de synthese enregistre: {cfg.plot_file}")


if __name__ == "__main__":
    main()
