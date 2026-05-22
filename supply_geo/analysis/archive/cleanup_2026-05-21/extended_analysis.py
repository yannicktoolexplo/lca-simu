"""
Extended analyses on supply simulation outputs.

Outputs a summary text file plus a few PNGs:
- bottlenecks_wait.png : waiting time per node (sorted)
- arrivals_cumulative.png : cumulative arrivals overall
- long_edges_hist.png : distance distribution with 5000 km marker
- modes_breakdown.png : share of transport modes

Run:
  python analysis/extended_analysis.py \
    --arrivals supply_arrivals.csv \
    --events supply_events.csv \
    --edges analysis/component_edges_modes.csv \
    --outdir analysis/sim_report_extended
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def compute_waiting_by_node(events: pd.DataFrame) -> pd.DataFrame:
    """Compute waiting time (END_PROC - START_PROC) per node/unit."""
    proc = events[events.event.isin(["START_PROC", "END_PROC"])].copy()
    proc["is_start"] = proc.event == "START_PROC"
    proc["pair_id"] = (
        proc.component
        + "|"
        + proc.node_or_leg.astype(str)
        + "|"
        + proc.unit_id.astype(str)
    )
    starts = proc[proc.is_start].set_index("pair_id")["day"]
    ends = proc[~proc.is_start].set_index("pair_id")["day"]
    waiting = (ends - starts).dropna()
    node_map = proc.drop_duplicates("pair_id").set_index("pair_id")["node_or_leg"]
    grouped = waiting.groupby(node_map.reindex(waiting.index)).agg(
        count="count", mean="mean", max="max"
    )
    return grouped.sort_values("mean", ascending=False)


def occupation_by_node(events: pd.DataFrame) -> pd.DataFrame:
    start = events[events.event == "START_PROC"]
    occup = (
        start.groupby(["node_or_leg", "day"]).size().groupby("node_or_leg")
        .agg(mean="mean", max="max")
        .sort_values("max", ascending=False)
    )
    return occup


def mode_breakdown(edges: pd.DataFrame):
    exploded = edges.assign(mode=edges["modes"].str.split("|")).explode("mode")
    counts = exploded["mode"].value_counts()
    dist = (
        exploded.groupby("mode")["distance_km"].sum().sort_values(ascending=False)
    )
    return counts, dist


def cumulative_arrivals(arrivals: pd.DataFrame):
    arr_sorted = arrivals.sort_values("arrival_day")
    arr_sorted["cum_all"] = range(1, len(arr_sorted) + 1)
    return arr_sorted


def plot_waiting(waiting_df: pd.DataFrame, out: Path, top_n: int = 20):
    subset = waiting_df.head(top_n)
    plt.figure(figsize=(9, 4))
    plt.bar(subset.index, subset["mean"], color="#4c72b0")
    plt.xticks(rotation=75, ha="right")
    plt.ylabel("Attente moyenne (jours)")
    plt.title(f"Top {top_n} goulots (attente moyenne)")
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def plot_modes(counts: pd.Series, out: Path):
    plt.figure(figsize=(6, 4))
    counts.plot(kind="bar", color="#55a868")
    plt.ylabel("Occurrences")
    plt.title("Répartition des modes de transport (arêtes)")
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def plot_distances(edges: pd.DataFrame, out: Path):
    plt.figure(figsize=(7, 4))
    plt.hist(edges["distance_km"], bins=50, color="#c44e52", edgecolor="white")
    plt.axvline(5000, color="black", linestyle="--", label=">5000 km")
    plt.xlabel("Distance (km)")
    plt.ylabel("Nombre d'arêtes")
    plt.title("Distribution des distances")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def plot_cumulative(arr_sorted: pd.DataFrame, out: Path):
    plt.figure(figsize=(7, 4))
    plt.plot(arr_sorted["arrival_day"], arr_sorted["cum_all"], color="#8172b3")
    plt.xlabel("Jour")
    plt.ylabel("Arrivées cumulées")
    plt.title("Arrivées cumulées (tous composants)")
    plt.tight_layout()
    plt.savefig(out)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Analyses supply avancées")
    parser.add_argument("--arrivals", default="analysis/supply_arrivals.csv")
    parser.add_argument("--events", default="analysis/supply_events.csv")
    parser.add_argument("--edges", default="analysis/component_edges_modes.csv")
    parser.add_argument("--outdir", default="analysis/sim_report_extended")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    arrivals = pd.read_csv(args.arrivals)
    events = pd.read_csv(args.events)
    edges = pd.read_csv(args.edges)

    waiting = compute_waiting_by_node(events)
    occup = occupation_by_node(events)
    mode_counts, mode_dist = mode_breakdown(edges)
    arr_sorted = cumulative_arrivals(arrivals)

    # Text report
    report = outdir / "extended_summary.txt"
    with report.open("w", encoding="utf-8") as f:
        f.write("=== Goulots (attente prod) ===\n")
        f.write(waiting.head(20).to_string() + "\n\n")

        f.write("=== Occupation (START_PROC par jour) ===\n")
        f.write(occup.head(20).to_string() + "\n\n")

        f.write("=== Modes (occurrences) ===\n")
        f.write(mode_counts.to_string() + "\n\n")

        f.write("=== Modes (distance cumulée km) ===\n")
        f.write(mode_dist.to_string() + "\n\n")

        f.write("=== Distances > 5000 km (top 10) ===\n")
        long_edges = edges[edges["distance_km"] > 5000]
        f.write(
            long_edges[
                [
                    "component",
                    "from_name",
                    "from_country",
                    "to_name",
                    "to_country",
                    "distance_km",
                ]
            ]
            .head(10)
            .to_string(index=False)
            + "\n"
        )

    # Plots
    plot_waiting(waiting, outdir / "bottlenecks_wait.png")
    plot_modes(mode_counts, outdir / "modes_breakdown.png")
    plot_distances(edges, outdir / "long_edges_hist.png")
    plot_cumulative(arr_sorted, outdir / "arrivals_cumulative.png")

    print(f"Rapport écrit dans {report}")
    print("Graphiques générés :")
    for name in [
        "bottlenecks_wait.png",
        "modes_breakdown.png",
        "long_edges_hist.png",
        "arrivals_cumulative.png",
    ]:
        print(f" - {outdir / name}")


if __name__ == "__main__":
    main()
