"""Advanced diagnostics for SD/DES supply chain analyses.

Focus:
- SD: deeper frequency response diagnostics (gain/phase/distortion) on multiple outputs.
- DES: distribution-focused risk diagnostics (quantiles, tails, bottlenecks, variability).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import argparse
import json
import math
import random
from typing import Callable

import numpy as np

from main_system_dynamics import SystemDynamicsConfig, run_simulation, slugify
from main_supply_chain_des import DESConfig, SupplyChainDES
from supply_graph_tools import derive_supply_graph_summary


@dataclass
class AdvancedConfig:
    horizon_days: int = 240
    step_day: int = 80
    step_demand: float = 85.0
    transport_1_days: int = 5
    transport_2_days: int = 4
    transport_3_days: int = 3
    replications: int = 80
    seed: int = 7
    delay_noise: float = 0.35
    disruption_prob: float = 0.10
    disruption_factor: float = 0.50
    freq_min: float = 0.005
    freq_max: float = 0.25
    freq_points: int = 16
    freq_amplitude: float = 6.0
    freq_warmup_cycles: int = 3
    freq_measure_cycles: int = 8


class DiagnosticStochasticDES(SupplyChainDES):
    """DES with stochastic capacity and transport delay for distribution analyses."""

    def __init__(
        self,
        cfg: DESConfig,
        rng: random.Random,
        delay_noise: float,
        disruption_prob: float,
        disruption_factor: float,
        demand_fn: Callable[[int, DESConfig], float] | None = None,
    ) -> None:
        self.rng = rng
        self.delay_noise = max(0.0, delay_noise)
        self.disruption_prob = max(0.0, min(1.0, disruption_prob))
        self.disruption_factor = max(0.0, min(1.0, disruption_factor))
        self.sampled_lead_days: list[float] = []
        self.disruption_events = 0
        super().__init__(cfg, demand_fn=demand_fn)

    def _ship_all_links(self) -> None:
        for i in range(self.n_stages - 1):
            source_cfg = self.stages_cfg[i]
            source_state = self.stage_states[i]
            link_state = self.link_states[i]

            request = self.orders[i + 1] + link_state.backlog
            max_output_from_stock = source_state.inventory * source_cfg.conversion_yield
            ship_capacity = min(source_cfg.max_ship_rate, max_output_from_stock)

            if self.rng.random() < self.disruption_prob:
                ship_capacity *= self.disruption_factor
                self.disruption_events += 1

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
        self.sampled_lead_days.append(sampled_lead)
        if sampled_lead <= 1e-9:
            self._receive_delivery(link_index, quantity, has_been_in_transit=False)
            return

        link_state.in_transit += quantity
        self.env.process(self._deliver_after(link_index, quantity, sampled_lead * self.cfg.dt_day))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advanced SD/DES diagnostics for supply chain issues")
    parser.add_argument("--horizon", type=int, default=240, help="Simulation horizon")
    parser.add_argument("--step-day", type=int, default=80, help="Demand step day")
    parser.add_argument("--step-demand", type=float, default=85.0, help="Demand after step")
    parser.add_argument("--transport-1", type=int, default=5, help="Transport lead 1")
    parser.add_argument("--transport-2", type=int, default=4, help="Transport lead 2")
    parser.add_argument("--transport-3", type=int, default=3, help="Transport lead 3")
    parser.add_argument("--use-graph", action="store_true", help="Calibrate transport from knowledge_graph + coords")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json", help="knowledge_graph path")
    parser.add_argument("--coords", type=str, default="actor_coords.json", help="actor_coords path")
    parser.add_argument("--replications", type=int, default=80, help="DES stochastic replications")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument("--delay-noise", type=float, default=0.35, help="Relative std-dev of delay")
    parser.add_argument("--disruption-prob", type=float, default=0.10, help="Probability of reduced capacity")
    parser.add_argument("--disruption-factor", type=float, default=0.50, help="Capacity factor under disruption")
    parser.add_argument("--freq-min", type=float, default=0.005, help="Min frequency (cycles/day)")
    parser.add_argument("--freq-max", type=float, default=0.25, help="Max frequency (cycles/day)")
    parser.add_argument("--freq-points", type=int, default=16, help="Number of frequencies")
    parser.add_argument("--freq-amplitude", type=float, default=6.0, help="Demand sinus amplitude")
    parser.add_argument("--freq-warmup-cycles", type=int, default=3, help="Warmup cycles per frequency")
    parser.add_argument("--freq-measure-cycles", type=int, default=8, help="Measurement cycles per frequency")
    parser.add_argument("--plot-prefix", type=str, default="advanced_supply", help="Prefix for plot outputs")
    parser.add_argument(
        "--report-file",
        type=str,
        default="advanced_supply_diagnostics.json",
        help="Output JSON report",
    )
    return parser.parse_args()


def _wrap_phase(phase_deg: float) -> float:
    value = phase_deg
    while value <= -180.0:
        value += 360.0
    while value > 180.0:
        value -= 360.0
    return value


def _estimate_amplitude_phase(signal: list[float], frequency_cpd: float, dt_day: float) -> tuple[float, float]:
    n = len(signal)
    if n < 4:
        raise ValueError("Not enough samples for amplitude/phase estimation")
    omega = 2.0 * math.pi * frequency_cpd
    mean_value = float(sum(signal) / n)
    sin_proj = 0.0
    cos_proj = 0.0
    for k, value in enumerate(signal):
        centered = value - mean_value
        theta = omega * k * dt_day
        sin_proj += centered * math.sin(theta)
        cos_proj += centered * math.cos(theta)
    sin_coeff = (2.0 / n) * sin_proj
    cos_coeff = (2.0 / n) * cos_proj
    amplitude = math.sqrt(sin_coeff * sin_coeff + cos_coeff * cos_coeff)
    phase = math.degrees(math.atan2(cos_coeff, sin_coeff))
    return amplitude, phase


def _harmonic_ratio(signal: list[float], fundamental_cpd: float, dt_day: float) -> float:
    nyquist = 0.5 / dt_day
    harmonic = 2.0 * fundamental_cpd
    if harmonic >= nyquist:
        return 0.0
    amp1, _ = _estimate_amplitude_phase(signal, fundamental_cpd, dt_day)
    amp2, _ = _estimate_amplitude_phase(signal, harmonic, dt_day)
    if amp1 <= 1e-12:
        return 0.0
    return amp2 / amp1


def _summarize_distribution(samples: list[float]) -> dict[str, float]:
    arr = np.array(samples, dtype=float)
    if arr.size == 0:
        return {
            k: float("nan")
            for k in ("mean", "std", "p10", "p50", "p90", "p95", "p99", "min", "max", "cvar95")
        }
    p95 = float(np.percentile(arr, 95))
    tail = arr[arr >= p95]
    cvar95 = float(np.mean(tail)) if tail.size > 0 else p95
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "p95": p95,
        "p99": float(np.percentile(arr, 99)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "cvar95": cvar95,
    }


def _make_sd_cfg(cfg: AdvancedConfig) -> SystemDynamicsConfig:
    return SystemDynamicsConfig(
        horizon_days=cfg.horizon_days,
        demand_step_day=cfg.step_day,
        demand_step_value=cfg.step_demand,
        transport_1_days=cfg.transport_1_days,
        transport_2_days=cfg.transport_2_days,
        transport_3_days=cfg.transport_3_days,
    )


def _make_des_cfg(cfg: AdvancedConfig) -> DESConfig:
    return DESConfig(
        horizon_days=cfg.horizon_days,
        demand_step_day=cfg.step_day,
        demand_step_value=cfg.step_demand,
        enable_dynamics=True,
        transport_1_days=cfg.transport_1_days,
        transport_2_days=cfg.transport_2_days,
        transport_3_days=cfg.transport_3_days,
    )


def run_sd_frequency_analysis(cfg: AdvancedConfig) -> dict[str, object]:
    base_cfg = _make_sd_cfg(cfg)
    nyquist = 0.5 / base_cfg.dt_day
    if cfg.freq_max >= nyquist:
        raise ValueError(f"freq_max={cfg.freq_max} must be < Nyquist={nyquist}")

    frequencies = np.geomspace(cfg.freq_min, cfg.freq_max, cfg.freq_points).tolist()
    output_keys = {
        "stock_arrivee": f"inventory_{slugify('stock_arrivee_ligne_production')}",
        "backlog_client": "customer_backlog",
        "orders_total": "orders_total",
        "in_transit_total": "in_transit_total",
    }

    results: dict[str, dict[str, list[float]]] = {}
    for name in output_keys:
        results[name] = {"gain_db": [], "phase_deg": [], "distortion_ratio": []}

    for freq in frequencies:
        period_days = 1.0 / freq
        horizon_days = max(90, int(math.ceil((cfg.freq_warmup_cycles + cfg.freq_measure_cycles) * period_days)))
        measure_samples = max(50, int(math.ceil(cfg.freq_measure_cycles * period_days)))
        run_cfg = replace(
            base_cfg,
            horizon_days=horizon_days,
            demand_step_day=horizon_days + 1,
            demand_step_value=base_cfg.initial_demand,
        )

        def sinus_demand(day: int, local_cfg: SystemDynamicsConfig, ff: float = freq) -> float:
            return local_cfg.initial_demand + cfg.freq_amplitude * math.sin(2.0 * math.pi * ff * day * local_cfg.dt_day)

        series = run_simulation(run_cfg, demand_fn=sinus_demand).series
        start = max(0, len(series["day"]) - measure_samples)
        input_window = series["customer_demand"][start:]
        in_amp, in_phase = _estimate_amplitude_phase(input_window, freq, run_cfg.dt_day)
        ref_amp = max(in_amp, 1e-12)

        for out_name, out_key in output_keys.items():
            signal = series[out_key][start:]
            out_amp, out_phase = _estimate_amplitude_phase(signal, freq, run_cfg.dt_day)
            gain_db = 20.0 * math.log10(max(out_amp, 1e-12) / ref_amp)
            phase = _wrap_phase(out_phase - in_phase)
            distortion = _harmonic_ratio(signal, freq, run_cfg.dt_day)
            results[out_name]["gain_db"].append(gain_db)
            results[out_name]["phase_deg"].append(phase)
            results[out_name]["distortion_ratio"].append(distortion)

    summary: dict[str, dict[str, float]] = {}
    for out_name, values in results.items():
        gain_arr = np.array(values["gain_db"])
        distortion_arr = np.array(values["distortion_ratio"])
        idx = int(np.argmax(gain_arr))
        summary[out_name] = {
            "peak_gain_db": float(gain_arr[idx]),
            "resonance_freq_cpd": float(frequencies[idx]),
            "phase_at_resonance_deg": float(values["phase_deg"][idx]),
            "max_distortion_ratio": float(np.max(distortion_arr)),
        }

    return {
        "frequencies_cpd": frequencies,
        "outputs": results,
        "summary": summary,
    }


def run_des_distribution_analysis(cfg: AdvancedConfig) -> dict[str, object]:
    base_cfg = _make_des_cfg(cfg)
    rng_master = random.Random(cfg.seed)

    final_stock_key = f"inventory_{slugify('stock_arrivee_ligne_production')}"
    sample_keys = {
        "service_level": [],
        "max_customer_backlog": [],
        "days_customer_backlog": [],
        "max_internal_backlog": [],
        "stockout_days_arrivee": [],
        "bullwhip_ratio": [],
        "disruption_events": [],
    }
    lead_time_samples: list[float] = []
    link_backlog_max_samples: dict[str, list[float]] = {}

    for _ in range(cfg.replications):
        seed = rng_master.randint(1, 10_000_000)
        rng = random.Random(seed)
        sim = DiagnosticStochasticDES(
            cfg=base_cfg,
            rng=rng,
            delay_noise=cfg.delay_noise,
            disruption_prob=cfg.disruption_prob,
            disruption_factor=cfg.disruption_factor,
        )
        result = sim.run()
        series = result.series

        total_demand = sum(series["customer_demand"])
        total_ship = sum(series["customer_shipment"])
        service_level = (total_ship / total_demand) if total_demand > 0 else 1.0
        max_customer_backlog = max(series["customer_backlog"])
        days_customer_backlog = sum(1 for value in series["customer_backlog"] if value > 1e-9)
        stockout_days_arrivee = sum(1 for value in series[final_stock_key] if value <= 1e-9)

        backlog_keys = [k for k in series if k.startswith("backlog_")]
        max_internal_backlog = max(max(series[k]) for k in backlog_keys) if backlog_keys else 0.0

        demand_std = float(np.std(series["customer_demand"]))
        orders_std = float(np.std(series["orders_total"]))
        bullwhip = orders_std / demand_std if demand_std > 1e-9 else 0.0

        sample_keys["service_level"].append(service_level)
        sample_keys["max_customer_backlog"].append(max_customer_backlog)
        sample_keys["days_customer_backlog"].append(float(days_customer_backlog))
        sample_keys["max_internal_backlog"].append(max_internal_backlog)
        sample_keys["stockout_days_arrivee"].append(float(stockout_days_arrivee))
        sample_keys["bullwhip_ratio"].append(bullwhip)
        sample_keys["disruption_events"].append(float(sim.disruption_events))

        lead_time_samples.extend(sim.sampled_lead_days)

        for key in backlog_keys:
            link_backlog_max_samples.setdefault(key, []).append(max(series[key]))

    summary = {name: _summarize_distribution(values) for name, values in sample_keys.items()}
    summary["lead_time_days"] = _summarize_distribution(lead_time_samples)

    bottlenecks = []
    for key, values in link_backlog_max_samples.items():
        metric = _summarize_distribution(values)
        bottlenecks.append(
            {
                "link_backlog_key": key,
                "mean_max_backlog": metric["mean"],
                "p95_max_backlog": metric["p95"],
            }
        )
    bottlenecks = sorted(bottlenecks, key=lambda x: x["p95_max_backlog"], reverse=True)

    return {
        "summary": summary,
        "samples": sample_keys,
        "lead_time_samples": lead_time_samples,
        "top_bottlenecks": bottlenecks[:8],
    }


def build_issue_list(sd_freq: dict[str, object], des_dist: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    sd_summary = sd_freq["summary"]
    des_summary = des_dist["summary"]

    orders_peak = sd_summary["orders_total"]["peak_gain_db"]
    if orders_peak > 0.0:
        issues.append(
            {
                "severity": "high",
                "area": "SD frequency",
                "issue": (
                    f"Potential bullwhip resonance: orders peak gain {orders_peak:.1f} dB at "
                    f"{sd_summary['orders_total']['resonance_freq_cpd']:.3f} cycles/day."
                ),
            }
        )

    backlog_peak = sd_summary["backlog_client"]["peak_gain_db"]
    if backlog_peak > -6.0:
        issues.append(
            {
                "severity": "medium",
                "area": "SD frequency",
                "issue": (
                    f"Backlog highly sensitive to periodic demand: peak gain {backlog_peak:.1f} dB."
                ),
            }
        )

    distortion_orders = sd_summary["orders_total"]["max_distortion_ratio"]
    if distortion_orders > 0.15:
        issues.append(
            {
                "severity": "medium",
                "area": "SD nonlinearity",
                "issue": (
                    f"Order signal distortion is elevated (2nd harmonic ratio {distortion_orders:.2f})."
                ),
            }
        )

    backlog_p95 = des_summary["max_customer_backlog"]["p95"]
    if backlog_p95 > 100.0:
        issues.append(
            {
                "severity": "high",
                "area": "DES tail risk",
                "issue": f"Customer backlog tail risk is high: P95 max backlog {backlog_p95:.1f} units.",
            }
        )

    service_p10 = des_summary["service_level"]["p10"]
    if service_p10 < 0.995:
        issues.append(
            {
                "severity": "medium",
                "area": "DES service",
                "issue": f"Service robustness issue: service distribution under stress (P90={100*service_p10:.2f}%).",
            }
        )

    bullwhip_p95 = des_summary["bullwhip_ratio"]["p95"]
    if bullwhip_p95 > 1.5:
        issues.append(
            {
                "severity": "high",
                "area": "DES variability",
                "issue": f"Bullwhip ratio tail is high (P95={bullwhip_p95:.2f}).",
            }
        )

    lead_p95 = des_summary["lead_time_days"]["p95"]
    if not math.isnan(lead_p95) and lead_p95 > 1.75 * des_summary["lead_time_days"]["mean"]:
        issues.append(
            {
                "severity": "medium",
                "area": "DES transport",
                "issue": (
                    f"Lead-time variability is significant (mean={des_summary['lead_time_days']['mean']:.2f}d, "
                    f"P95={lead_p95:.2f}d)."
                ),
            }
        )

    if not issues:
        issues.append(
            {
                "severity": "low",
                "area": "global",
                "issue": "No critical issue crossed current thresholds. Consider stronger stress scenarios.",
            }
        )
    return issues


def plot_sd_frequency(sd_freq: dict[str, object], output_path: str) -> None:
    import matplotlib.pyplot as plt

    freqs = sd_freq["frequencies_cpd"]
    outputs = sd_freq["outputs"]
    output_order = [
        ("stock_arrivee", "Stock arrivee"),
        ("backlog_client", "Backlog client"),
        ("orders_total", "Orders total"),
        ("in_transit_total", "In transit total"),
    ]

    fig, axes = plt.subplots(len(output_order), 2, figsize=(14, 13), sharex="col")
    for row, (key, label) in enumerate(output_order):
        gain = outputs[key]["gain_db"]
        phase = outputs[key]["phase_deg"]
        distortion = outputs[key]["distortion_ratio"]

        axes[row, 0].semilogx(freqs, gain, marker="o")
        axes[row, 0].set_ylabel(f"{label}\nGain (dB)")
        axes[row, 0].grid(alpha=0.3, which="both")

        axes[row, 1].semilogx(freqs, phase, marker="o", label="phase")
        axes[row, 1].semilogx(freqs, [100.0 * v for v in distortion], marker="x", linestyle="--", label="distortion %")
        axes[row, 1].set_ylabel(f"{label}\nPhase / Distortion")
        axes[row, 1].grid(alpha=0.3, which="both")
        if row == 0:
            axes[row, 1].legend(fontsize=8)

    axes[-1, 0].set_xlabel("Frequency (cycles/day)")
    axes[-1, 1].set_xlabel("Frequency (cycles/day)")
    fig.suptitle("Advanced SD Frequency Diagnostics", y=0.995)
    plt.tight_layout()
    fig.savefig(output_path, dpi=170)
    plt.show()


def plot_des_distributions(des_dist: dict[str, object], output_path: str) -> None:
    import matplotlib.pyplot as plt

    samples = des_dist["samples"]
    lead_samples = des_dist["lead_time_samples"]
    bottlenecks = des_dist["top_bottlenecks"][:5]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))

    axes[0, 0].hist(samples["max_customer_backlog"], bins=20, color="tab:red", alpha=0.8)
    axes[0, 0].set_title("Max customer backlog")
    axes[0, 0].set_xlabel("Units")
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].hist(samples["service_level"], bins=20, color="tab:green", alpha=0.8)
    axes[0, 1].set_title("Service level")
    axes[0, 1].set_xlabel("Ratio")
    axes[0, 1].grid(alpha=0.3)

    axes[0, 2].hist(samples["stockout_days_arrivee"], bins=20, color="tab:purple", alpha=0.8)
    axes[0, 2].set_title("Stockout days (arrival node)")
    axes[0, 2].set_xlabel("Days")
    axes[0, 2].grid(alpha=0.3)

    axes[1, 0].hist(samples["bullwhip_ratio"], bins=20, color="tab:orange", alpha=0.8)
    axes[1, 0].set_title("Bullwhip ratio")
    axes[1, 0].set_xlabel("orders std / demand std")
    axes[1, 0].grid(alpha=0.3)

    axes[1, 1].hist(lead_samples, bins=20, color="tab:blue", alpha=0.8)
    axes[1, 1].set_title("Sampled transport lead times")
    axes[1, 1].set_xlabel("Days")
    axes[1, 1].grid(alpha=0.3)

    link_labels = [b["link_backlog_key"].replace("backlog_", "") for b in bottlenecks]
    link_values = [b["p95_max_backlog"] for b in bottlenecks]
    axes[1, 2].bar(range(len(link_labels)), link_values, color="tab:brown", alpha=0.8)
    axes[1, 2].set_title("Top bottlenecks (P95 max backlog)")
    axes[1, 2].set_xticks(range(len(link_labels)))
    axes[1, 2].set_xticklabels(link_labels, rotation=35, ha="right", fontsize=8)
    axes[1, 2].set_ylabel("Units")
    axes[1, 2].grid(alpha=0.3)

    fig.suptitle("Advanced DES Distribution Diagnostics", y=0.995)
    plt.tight_layout()
    fig.savefig(output_path, dpi=170)
    plt.show()


def _jsonify(obj):
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


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

    cfg = AdvancedConfig(
        horizon_days=args.horizon,
        step_day=args.step_day,
        step_demand=args.step_demand,
        transport_1_days=transport_1,
        transport_2_days=transport_2,
        transport_3_days=transport_3,
        replications=args.replications,
        seed=args.seed,
        delay_noise=args.delay_noise,
        disruption_prob=args.disruption_prob,
        disruption_factor=args.disruption_factor,
        freq_min=args.freq_min,
        freq_max=args.freq_max,
        freq_points=args.freq_points,
        freq_amplitude=args.freq_amplitude,
        freq_warmup_cycles=args.freq_warmup_cycles,
        freq_measure_cycles=args.freq_measure_cycles,
    )

    print("\n=== Advanced Supply Diagnostics ===")
    print(
        "Transports (days): "
        f"{cfg.transport_1_days}, {cfg.transport_2_days}, {cfg.transport_3_days}"
    )
    if graph_summary is not None:
        print(
            f"Graph calibration: actors={graph_summary.actor_count}, "
            f"supply_edges={graph_summary.supply_edge_count}"
        )

    sd_frequency = run_sd_frequency_analysis(cfg)
    des_distribution = run_des_distribution_analysis(cfg)
    issues = build_issue_list(sd_frequency, des_distribution)

    sd_plot = f"{args.plot_prefix}_sd_frequency.png"
    des_plot = f"{args.plot_prefix}_des_distributions.png"
    plot_sd_frequency(sd_frequency, sd_plot)
    plot_des_distributions(des_distribution, des_plot)

    report = {
        "config": cfg.__dict__,
        "graph_summary": None if graph_summary is None else graph_summary.__dict__,
        "sd_frequency": sd_frequency,
        "des_distribution": {
            "summary": des_distribution["summary"],
            "top_bottlenecks": des_distribution["top_bottlenecks"],
        },
        "issues": issues,
        "artifacts": {
            "sd_frequency_plot": sd_plot,
            "des_distribution_plot": des_plot,
        },
    }

    with open(args.report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, default=_jsonify, ensure_ascii=True, indent=2)

    print(f"SD frequency plot: {sd_plot}")
    print(f"DES distribution plot: {des_plot}")
    print(f"Report JSON: {args.report_file}")
    print("\nDetected issues:")
    for issue in issues:
        print(f"- [{issue['severity']}] {issue['area']}: {issue['issue']}")


if __name__ == "__main__":
    main()
