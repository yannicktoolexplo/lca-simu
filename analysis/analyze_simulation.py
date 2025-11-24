import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def describe_arrivals(arr_df: pd.DataFrame):
    stats = {}
    vals = arr_df['arrival_day'].values
    stats['count'] = len(vals)
    stats['min'] = float(np.min(vals)) if len(vals) else None
    stats['mean'] = float(np.mean(vals)) if len(vals) else None
    stats['median'] = float(np.median(vals)) if len(vals) else None
    stats['max'] = float(np.max(vals)) if len(vals) else None
    qs = np.percentile(vals, [5, 25, 50, 75, 90, 95, 99]) if len(vals) else [None]*7
    stats['percentiles'] = dict(zip([5, 25, 50, 75, 90, 95, 99], qs))
    return stats


def top_components(arr_df: pd.DataFrame, n: int = 15, fastest: bool = False):
    agg = arr_df.groupby('component')['arrival_day'].agg(['count', 'mean', 'median', 'max'])
    agg = agg.sort_values('max', ascending=fastest)
    return agg.head(n)


def arrivals_histogram(arr_df: pd.DataFrame, out_path: Path):
    plt.figure(figsize=(8, 4))
    plt.hist(arr_df['arrival_day'], bins=30, color='#4c72b0', edgecolor='white')
    plt.title('Distribution des jours d\'arrivée')
    plt.xlabel('Jour d\'arrivée')
    plt.ylabel('Nombre d\'unités')
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def slow_components_boxplot(arr_df: pd.DataFrame, out_path: Path, top_n: int = 10):
    agg = arr_df.groupby('component')['arrival_day'].max().sort_values(ascending=False).head(top_n)
    comps = agg.index.tolist()
    data = [arr_df[arr_df['component'] == c]['arrival_day'].values for c in comps]
    plt.figure(figsize=(10, 5))
    plt.boxplot(data, labels=comps, vert=True, patch_artist=True,
                boxprops=dict(facecolor='#55a868', alpha=0.6),
                medianprops=dict(color='black'))
    plt.xticks(rotation=75, ha='right')
    plt.title(f'Top {top_n} composants les plus lents (distribution des arrivées)')
    plt.ylabel('Jour d\'arrivée')
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def events_summary(events_df: pd.DataFrame):
    return events_df['event'].value_counts()


def main():
    parser = argparse.ArgumentParser(description='Analyse des résultats de simulation supply.')
    parser.add_argument('--arrivals', default='supply_arrivals.csv', help='CSV des arrivées (supply_arrivals.csv)')
    parser.add_argument('--events', default='supply_events.csv', help='CSV des événements (supply_events.csv)')
    parser.add_argument('--outdir', default='analysis/sim_report', help='Répertoire de sortie pour graphiques et résumé')
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    arr_df = pd.read_csv(args.arrivals)
    events_df = pd.read_csv(args.events)

    stats = describe_arrivals(arr_df)
    slow = top_components(arr_df, n=15, fastest=False)
    fast = top_components(arr_df, n=10, fastest=True)
    ev_summary = events_summary(events_df)

    # Graphiques
    arrivals_histogram(arr_df, outdir / 'arrivals_hist.png')
    slow_components_boxplot(arr_df, outdir / 'slow_components_boxplot.png')

    # Rapport texte
    report_path = outdir / 'summary.txt'
    with report_path.open('w', encoding='utf-8') as f:
        f.write('=== Statistiques globales des arrivées ===\n')
        f.write(f"Count: {stats['count']}\n")
        f.write(f"Min / Mean / Median / Max: {stats['min']} / {stats['mean']} / {stats['median']} / {stats['max']}\n")
        f.write('Percentiles (j): ' + ', '.join([f"p{p}={v:.2f}" for p, v in stats['percentiles'].items()]) + '\n\n')

        f.write('=== Événements (tous types) ===\n')
        f.write(ev_summary.to_string() + '\n\n')

        f.write('=== Top 15 composants les plus lents (par max arrivée) ===\n')
        f.write(slow.to_string() + '\n\n')

        f.write('=== Top 10 composants les plus rapides (par max arrivée) ===\n')
        f.write(fast.to_string() + '\n')

    print(f"Rapport écrit dans {report_path}")
    print(f"Graphiques : {outdir / 'arrivals_hist.png'}, {outdir / 'slow_components_boxplot.png'}")


if __name__ == '__main__':
    main()
