"""PoC supply chain en DES (Discrete-Event Simulation) avec SimPy.

Objectif: reproduire la meme logique metier que le modele System Dynamics
discret, mais executee sous forme de simulation a evenements discrets.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
from typing import Callable

import simpy


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
class DESConfig:
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
    enable_dynamics: bool = False


@dataclass
class DESResult:
    series: dict[str, list[float]]
    stages: list[StageConfig]
    lead_times: list[int]
    event_series: dict[str, list[float]]
    shipment_event_times: list[float]
    delivery_event_times: list[float]


@dataclass
class StageState:
    inventory: float
    expected_demand: float


@dataclass
class LinkState:
    lead_time_days: int
    backlog: float = 0.0
    in_transit: float = 0.0


def default_stages() -> list[StageConfig]:
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


def default_lead_times(cfg: DESConfig, n_stages: int) -> list[int]:
    if n_stages != 10:
        raise ValueError("Le profil de transport par defaut attend 10 noeuds.")
    return [0, cfg.transport_1_days, 0, 0, cfg.transport_2_days, 0, 0, 0, cfg.transport_3_days]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def slugify(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name.lower()).strip("_")


def customer_demand(day: int, cfg: DESConfig) -> float:
    if not cfg.enable_dynamics:
        return cfg.initial_demand
    return cfg.initial_demand if day < cfg.demand_step_day else cfg.demand_step_value


class SupplyChainDES:
    def __init__(
        self,
        cfg: DESConfig,
        demand_fn: Callable[[int, DESConfig], float] | None = None,
    ) -> None:
        if cfg.smoothing_days <= 0:
            raise ValueError("smoothing_days doit etre > 0")
        if cfg.inventory_adjust_time <= 0:
            raise ValueError("inventory_adjust_time doit etre > 0")
        if cfg.dt_day <= 0:
            raise ValueError("dt_day doit etre > 0")

        self.cfg = cfg
        self.demand_fn = demand_fn or customer_demand
        self.env = simpy.Environment()
        self.stages_cfg = default_stages()
        self.n_stages = len(self.stages_cfg)
        self.lead_times = default_lead_times(cfg, self.n_stages)
        self.stage_slugs = [slugify(stage.name) for stage in self.stages_cfg]
        self.link_slugs = [f"{self.stage_slugs[i]}_to_{self.stage_slugs[i + 1]}" for i in range(self.n_stages - 1)]

        self.stage_states = [StageState(stage.initial_inventory, cfg.initial_demand) for stage in self.stages_cfg]
        self.link_states = [LinkState(lead_time_days=lead) for lead in self.lead_times]

        self.orders = [0.0] * self.n_stages
        self.customer_backlog = 0.0
        self.customer_shipment = 0.0
        self.extraction_output = 0.0
        self.last_demand = cfg.initial_demand

        self.daily_shipments = [0.0] * (self.n_stages - 1)
        self.daily_deliveries = [0.0] * (self.n_stages - 1)

        self.series: dict[str, list[float]] = {
            "day": [],
            "customer_demand": [],
            "customer_shipment": [],
            "customer_backlog": [],
            "extraction_output": [],
            "orders_total": [],
            "shipments_total": [],
            "in_transit_total": [],
        }
        for slug in self.stage_slugs:
            self.series[f"inventory_{slug}"] = []
        for i in range(1, self.n_stages):
            self.series[f"order_{self.stage_slugs[i]}"] = []
        for link_slug in self.link_slugs:
            self.series[f"shipment_{link_slug}"] = []
            self.series[f"delivery_{link_slug}"] = []
            self.series[f"backlog_{link_slug}"] = []
            self.series[f"in_transit_{link_slug}"] = []

        self.event_series: dict[str, list[float]] = {
            "time": [],
            "customer_backlog": [],
            "in_transit_total": [],
        }
        for slug in self.stage_slugs:
            self.event_series[f"inventory_{slug}"] = []
        self.shipment_event_times: list[float] = []
        self.delivery_event_times: list[float] = []

        self._bootstrap_transports()
        self._record_event_state()

    def run(self) -> DESResult:
        self.env.process(self._daily_loop())
        self.env.run(until=self.cfg.horizon_days * self.cfg.dt_day + 1e-9)
        return DESResult(
            series=self.series,
            stages=self.stages_cfg,
            lead_times=self.lead_times,
            event_series=self.event_series,
            shipment_event_times=self.shipment_event_times,
            delivery_event_times=self.delivery_event_times,
        )

    def _record_event_state(self) -> None:
        """Capture l'etat instantane pour des tracés DES en escalier."""
        now = float(self.env.now)
        in_transit_total = sum(link.in_transit for link in self.link_states)

        if self.event_series["time"] and abs(self.event_series["time"][-1] - now) < 1e-12:
            self.event_series["customer_backlog"][-1] = self.customer_backlog
            self.event_series["in_transit_total"][-1] = in_transit_total
            for i, slug in enumerate(self.stage_slugs):
                self.event_series[f"inventory_{slug}"][-1] = self.stage_states[i].inventory
            return

        self.event_series["time"].append(now)
        self.event_series["customer_backlog"].append(self.customer_backlog)
        self.event_series["in_transit_total"].append(in_transit_total)
        for i, slug in enumerate(self.stage_slugs):
            self.event_series[f"inventory_{slug}"].append(self.stage_states[i].inventory)

    def _bootstrap_transports(self) -> None:
        """Initialise les pipelines de transport comme dans le modele SD."""
        for link_index, link_state in enumerate(self.link_states):
            lead = link_state.lead_time_days
            if lead <= 0:
                continue

            # Livraison immediate au jour 0 (popleft du pipeline precharge).
            self._receive_delivery(link_index, self.cfg.initial_demand, has_been_in_transit=False)

            # Livraisons futures deja en transit pour les jours suivants.
            for step in range(1, lead):
                link_state.in_transit += self.cfg.initial_demand
                delay = step * self.cfg.dt_day
                self.env.process(self._deliver_after(link_index, self.cfg.initial_demand, delay))

    def _daily_loop(self):
        for day in range(self.cfg.horizon_days):
            self.last_demand = max(0.0, self.demand_fn(day, self.cfg))
            self._serve_customer(self.last_demand)
            self._compute_orders(self.last_demand)
            self._run_extraction()
            self._ship_all_links()
            self._record_day(day)

            self.daily_shipments = [0.0] * (self.n_stages - 1)
            self.daily_deliveries = [0.0] * (self.n_stages - 1)
            yield self.env.timeout(self.cfg.dt_day)

    def _serve_customer(self, demand: float) -> None:
        final_stage = self.stage_states[-1]
        to_ship = demand + self.customer_backlog
        shipment = min(final_stage.inventory, to_ship)
        final_stage.inventory -= shipment
        self.customer_shipment = shipment
        self.customer_backlog = max(0.0, to_ship - shipment)
        self._record_event_state()

    def _compute_orders(self, demand: float) -> None:
        orders = [0.0] * self.n_stages
        alpha = self.cfg.dt_day / self.cfg.smoothing_days

        for j in range(self.n_stages - 1, 0, -1):
            downstream_signal = demand if j == self.n_stages - 1 else orders[j + 1]
            stage_cfg = self.stages_cfg[j]
            stage_state = self.stage_states[j]
            stage_state.expected_demand += (downstream_signal - stage_state.expected_demand) * alpha
            inventory_gap = stage_cfg.target_inventory - stage_state.inventory
            desired_order = stage_state.expected_demand + inventory_gap / self.cfg.inventory_adjust_time
            orders[j] = clamp(desired_order, 0.0, stage_cfg.max_order_rate)

        self.orders = orders

    def _run_extraction(self) -> None:
        alpha = self.cfg.dt_day / self.cfg.smoothing_days
        stage_cfg = self.stages_cfg[0]
        stage_state = self.stage_states[0]
        stage_state.expected_demand += (self.orders[1] - stage_state.expected_demand) * alpha
        extraction_control = (
            stage_state.expected_demand + (stage_cfg.target_inventory - stage_state.inventory) / self.cfg.inventory_adjust_time
        )
        cap = stage_cfg.source_capacity or stage_cfg.max_ship_rate
        self.extraction_output = clamp(extraction_control, 0.0, cap)
        stage_state.inventory += self.extraction_output
        self._record_event_state()

    def _ship_all_links(self) -> None:
        for i in range(self.n_stages - 1):
            source_cfg = self.stages_cfg[i]
            source_state = self.stage_states[i]
            link_state = self.link_states[i]

            request = self.orders[i + 1] + link_state.backlog
            max_output_from_stock = source_state.inventory * source_cfg.conversion_yield
            ship_capacity = min(source_cfg.max_ship_rate, max_output_from_stock)
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
        if link_state.lead_time_days <= 0:
            self._receive_delivery(link_index, quantity, has_been_in_transit=False)
            return

        link_state.in_transit += quantity
        delay = link_state.lead_time_days * self.cfg.dt_day
        self.env.process(self._deliver_after(link_index, quantity, delay))

    def _deliver_after(self, link_index: int, quantity: float, delay: float):
        yield self.env.timeout(delay)
        self._receive_delivery(link_index, quantity, has_been_in_transit=True)

    def _receive_delivery(self, link_index: int, quantity: float, has_been_in_transit: bool) -> None:
        if has_been_in_transit:
            link_state = self.link_states[link_index]
            link_state.in_transit = max(0.0, link_state.in_transit - quantity)
        self.stage_states[link_index + 1].inventory += quantity
        self.daily_deliveries[link_index] += quantity
        self.delivery_event_times.append(float(self.env.now))
        self._record_event_state()

    def _record_day(self, day: int) -> None:
        self.series["day"].append(day)
        self.series["customer_demand"].append(self.last_demand)
        self.series["customer_shipment"].append(self.customer_shipment)
        self.series["customer_backlog"].append(self.customer_backlog)
        self.series["extraction_output"].append(self.extraction_output)
        self.series["orders_total"].append(sum(self.orders[1:]))
        self.series["shipments_total"].append(sum(self.daily_shipments))

        in_transit_total = 0.0
        for i, slug in enumerate(self.stage_slugs):
            self.series[f"inventory_{slug}"].append(self.stage_states[i].inventory)
            if i > 0:
                self.series[f"order_{slug}"].append(self.orders[i])

        for i, link_slug in enumerate(self.link_slugs):
            link_state = self.link_states[i]
            in_transit_total += link_state.in_transit
            self.series[f"shipment_{link_slug}"].append(self.daily_shipments[i])
            self.series[f"delivery_{link_slug}"].append(self.daily_deliveries[i])
            self.series[f"backlog_{link_slug}"].append(link_state.backlog)
            self.series[f"in_transit_{link_slug}"].append(link_state.in_transit)

        self.series["in_transit_total"].append(in_transit_total)


def plot_results(result: DESResult, output_path: str | None = None) -> None:
    import matplotlib.pyplot as plt

    series = result.series
    days = series["day"]
    event_time = result.event_series["time"]
    stage_slugs = [slugify(stage.name) for stage in result.stages]
    final_slug = stage_slugs[-1]
    distribution_slug = slugify("distribution")
    transformation_1_slug = slugify("transformation_1")
    transformation_2_slug = slugify("transformation_2")

    stock_levels = {slug: result.event_series[f"inventory_{slug}"] for slug in stage_slugs}

    fig, axes = plt.subplots(5, 1, figsize=(13, 15), sharex=True)

    axes[0].step(event_time, stock_levels[final_slug], where="post", label="Stock arrivee ligne production", linewidth=2)
    axes[0].step(
        event_time,
        result.event_series["customer_backlog"],
        where="post",
        label="Backlog client",
        linewidth=2,
    )
    axes[0].set_ylabel("Unites")
    axes[0].set_title("DES - Service aval (traces en escalier)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].step(days, series["customer_demand"], where="post", label="Demande client", linestyle="--")
    axes[1].step(days, series["customer_shipment"], where="post", label="Livraisons client")
    axes[1].step(days, series[f"order_{final_slug}"], where="post", label="Commande amont (ligne prod)")
    axes[1].set_ylabel("Unites/jour")
    axes[1].set_title("DES - Flux journaliers echantillonnes")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    axes[2].step(days, series["extraction_output"], where="post", label="Extraction")
    axes[2].step(event_time, stock_levels[transformation_1_slug], where="post", label="Stock transfo 1")
    axes[2].step(event_time, stock_levels[transformation_2_slug], where="post", label="Stock transfo 2")
    axes[2].step(event_time, stock_levels[distribution_slug], where="post", label="Stock distribution")
    axes[2].set_ylabel("Unites")
    axes[2].set_title("DES - Etats fournisseurs/tiers (escalier)")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    for stage, slug in zip(result.stages, stage_slugs):
        axes[3].step(event_time, stock_levels[slug], where="post", label=stage.name)
    axes[3].set_ylabel("Unites")
    axes[3].set_title("DES - Niveaux de stock par noeud (event time)")
    axes[3].legend(ncol=2, fontsize=8)
    axes[3].grid(alpha=0.3)

    if result.shipment_event_times:
        axes[4].eventplot(
            result.shipment_event_times,
            lineoffsets=1.0,
            linelengths=0.7,
            colors="tab:blue",
            label="Events expeditions",
        )
    if result.delivery_event_times:
        axes[4].eventplot(
            result.delivery_event_times,
            lineoffsets=2.2,
            linelengths=0.7,
            colors="tab:orange",
            label="Events livraisons",
        )
    axes[4].set_yticks([1.0, 2.2], ["Expeditions", "Livraisons"])
    axes[4].set_xlabel("Temps simulation (jours)")
    axes[4].set_title("DES - Timeline des evenements")
    axes[4].grid(alpha=0.3)

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=160)
    plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PoC supply chain en DES (SimPy)")
    parser.add_argument("--horizon", type=int, default=180, help="Horizon de simulation (jours)")
    parser.add_argument("--step-day", type=int, default=60, help="Jour de changement de demande")
    parser.add_argument("--step-demand", type=float, default=70.0, help="Nouvelle demande apres step")
    parser.add_argument("--lead-time", type=int, default=None, help="Compatibilite: applique le meme delai aux 3 transports")
    parser.add_argument("--transport-1", type=int, default=5, help="Delai transport extraction -> transfo 1")
    parser.add_argument("--transport-2", type=int, default=4, help="Delai transport transfo 1 -> transfo 2")
    parser.add_argument("--transport-3", type=int, default=3, help="Delai transport distribution -> ligne production")
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help="Active un step de demande. Sans --dynamic: demande constante mais logique SD conservee.",
    )
    parser.add_argument("--plot", action="store_true", help="Affiche les graphiques")
    parser.add_argument("--plot-file", type=str, default="supply_chain_des.png", help="Fichier PNG de sortie")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.lead_time is not None:
        transport_1 = transport_2 = transport_3 = args.lead_time
    else:
        transport_1 = args.transport_1
        transport_2 = args.transport_2
        transport_3 = args.transport_3

    cfg = DESConfig(
        horizon_days=args.horizon,
        demand_step_day=args.step_day,
        demand_step_value=args.step_demand,
        transport_1_days=transport_1,
        transport_2_days=transport_2,
        transport_3_days=transport_3,
        enable_dynamics=args.dynamic,
    )

    result = SupplyChainDES(cfg).run()
    series = result.series
    stage_slugs = [slugify(stage.name) for stage in result.stages]
    final_stock_key = f"inventory_{stage_slugs[-1]}"
    backlog_keys = [key for key in series if key.startswith("backlog_")]
    max_internal_backlog = max(max(series[key]) for key in backlog_keys) if backlog_keys else 0.0

    print("\n=== Resume PoC Supply Chain Multi-Tiers (DES SimPy) ===")
    print(f"Horizon: {cfg.horizon_days} jours")
    print(f"Demande initiale: {cfg.initial_demand:.1f} u/j")
    if cfg.enable_dynamics:
        print(f"Demande apres step: {cfg.demand_step_value:.1f} u/j (jour {cfg.demand_step_day})")
    else:
        print("Mode DES: demande constante (sans step), logique SD active")
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
    for stage, slug in zip(result.stages, stage_slugs):
        print(f"- {stage.name}: {series[f'inventory_{slug}'][-1]:.1f} u")

    if args.plot:
        plot_results(result, output_path=args.plot_file)
        print(f"\nPlot enregistre: {args.plot_file}")


if __name__ == "__main__":
    main()
