"""Identify components likely under-modeled (too fast / too local).

Heuristic: mean distance < 100 km OR max arrival < 40 jours.
Writes CSV report in analysis/sim_report_extended/under_modeled_components.csv.
"""

import argparse
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--edges', default='analysis/component_edges_modes.csv')
    ap.add_argument('--arrivals', default='analysis/supply_arrivals.csv')
    ap.add_argument('--out', default='analysis/sim_report_extended/under_modeled_components.csv')
    ap.add_argument('--dist_threshold', type=float, default=100.0)
    ap.add_argument('--arrival_threshold', type=float, default=40.0)
    args = ap.parse_args()

    edges = pd.read_csv(args.edges)
    arr = pd.read_csv(args.arrivals)

    edge_stats = edges.groupby('component')['distance_km'].agg(['count','mean','median','max']).reset_index()
    arr_stats = arr.groupby('component')['arrival_day'].agg(['count','mean','median','max']).reset_index()
    stats = edge_stats.merge(arr_stats, on='component', suffixes=('_dist','_arr'))

    under = stats[(stats['mean_dist'] < args.dist_threshold) | (stats['max_arr'] < args.arrival_threshold)].copy()
    under = under.sort_values(['max_arr','mean_dist'])

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    under.to_csv(out_path, index=False)
    print(f"Under-modeled components written to {out_path} ({len(under)} rows)")


if __name__ == '__main__':
    main()
