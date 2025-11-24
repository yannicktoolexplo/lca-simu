import os, csv, simpy, argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
from config_supply import (
    DEFAULT_UNITS_PER_COMPONENT, SIM_HORIZON_DAYS,
    EVENTS_CSV, ARRIVALS_CSV
)
from data_loader_supply import load_json, load_geocoding, build_graph
from sim_supply import simulate_supply

# Fichiers par défaut (surchargables par variables d'environnement)
JSON_PATH = os.environ.get("JSON_PATH", "supplychain_ultimate_DEDUP.json")
GEOCODING_XLSX = os.environ.get("GEOCODING_XLSX", "geocoding_table_filled.xlsx")

def run_simulation():
    assert os.path.exists(JSON_PATH), f"JSON not found: {JSON_PATH}"
    records = load_json(JSON_PATH)
    geolook = load_geocoding(GEOCODING_XLSX if os.path.exists(GEOCODING_XLSX) else None)
    nodes, edges = build_graph(records, geolook)

    components = sorted(set([e[3] for e in edges if e[3]]))
    # Exclure packaging (emballage de transport) de la demande
    demands = {c: DEFAULT_UNITS_PER_COMPONENT for c in components
               if c.strip().lower() not in {"packaging", "transport"}}
    if not demands and components:
        # fallback si tout a été filtré
        demands = {components[0]: DEFAULT_UNITS_PER_COMPONENT}
    elif not demands:
        demands = {"GENERIC": DEFAULT_UNITS_PER_COMPONENT}

    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["day", "event", "component", "unit_id", "node_or_leg", "role_or_mode", "distance_km", "speed_kmph"])
        env = simpy.Environment()
        arrivals = simulate_supply(env, nodes, edges, demands, writer)
        env.run(until=SIM_HORIZON_DAYS)

    with open(ARRIVALS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["component", "unit_id", "arrival_day"])
        for comp, unit_id, t in arrivals:
            w.writerow([comp, unit_id, round(t, 3)])

    print(f"✅ Simulation terminée : {EVENTS_CSV} / {ARRIVALS_CSV}")
    return arrivals, nodes, edges

def show_arrivals():
    if not os.path.exists(ARRIVALS_CSV):
        print("Aucun résultat trouvé. Lance d'abord la simulation (--run).")
        return
    df = pd.read_csv(ARRIVALS_CSV)
    print("\n📦 Arrivées prévues chez Safran (extrait) :")
    print(df.head(20).to_string(index=False))
    print(f"\n→ {len(df)} arrivées au total.")

def show_summary():
    if not os.path.exists(EVENTS_CSV):
        print("Aucun résultat trouvé. Lance d'abord la simulation (--run).")
        return
    df = pd.read_csv(EVENTS_CSV)
    summary = df.groupby("event")["day"].count().sort_values(ascending=False)
    print("\n📊 Événements enregistrés :")
    print(summary)
    print("\n📈 Nombre total d’événements :", len(df))

def show_flow():
    if not os.path.exists(EVENTS_CSV):
        print("Aucun résultat trouvé. Lance d'abord la simulation (--run).")
        return
    df = pd.read_csv(EVENTS_CSV)
    grouped = df.groupby(["component","event"])["day"].count().unstack(fill_value=0)
    print("\n🔁 Flux par composant (extrait) :")
    print(grouped.head(15))
    print("\nNombre total de composants :", len(grouped))

# -------------------- Plotting helpers (matplotlib) --------------------

def plot_arrivals(output_png="arrivals_cumulative.png"):
    if not os.path.exists(ARRIVALS_CSV):
        print("Aucun résultat trouvé. Lance d'abord la simulation (--run).")
        return None
    df = pd.read_csv(ARRIVALS_CSV)
    # Histogram by day and cumulative
    series = df["arrival_day"].round(0).astype(int).value_counts().sort_index()
    cum = series.cumsum()
    plt.figure()
    cum.plot(kind="line")
    plt.title("Arrivées cumulées chez Safran (unités)")
    plt.xlabel("Jour")
    plt.ylabel("Unités cumulées")
    plt.tight_layout()
    plt.savefig(output_png)
    plt.close()
    print(f"📈 Graphique enregistré : {output_png}")
    return output_png

def plot_workload_by_role(output_png="workload_by_role.png"):
    if not os.path.exists(EVENTS_CSV):
        print("Aucun résultat trouvé. Lance d'abord la simulation (--run).")
        return None
    df = pd.read_csv(EVENTS_CSV)
    # Approx: compter les START_PROC par rôle et par jour
    procs = df[df["event"] == "START_PROC"].copy()
    if procs.empty:
        print("Aucun événement START_PROC trouvé.")
        return None
    procs["day_int"] = procs["day"].round(0).astype(int)
    # Agrégation par jour et rôle
    grp = procs.groupby(["day_int","role_or_mode"]).size().unstack(fill_value=0)
    # On trace la somme (toutes rôles empilées -> ici on fait une courbe de la charge totale)
    # (une seule figure, pas de couleurs explicites)
    plt.figure()
    grp.sum(axis=1).plot(kind="line")
    plt.title("Charge journalière (nombre de démarrages de process)")
    plt.xlabel("Jour")
    plt.ylabel("Démarrages de process")
    plt.tight_layout()
    plt.savefig(output_png)
    plt.close()
    print(f"📈 Graphique enregistré : {output_png}")
    return output_png

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulation supply chain Safran")
    parser.add_argument("--run", action="store_true", help="Exécuter la simulation complète")
    parser.add_argument("--show", choices=["arrivals", "summary", "flow"], help="Afficher les résultats existants")
    parser.add_argument("--plot", choices=["arrivals", "workload"], help="Générer un graphique PNG")
    args = parser.parse_args()

    if args.run:
        run_simulation()

    if args.show == "arrivals":
        show_arrivals()
    elif args.show == "summary":
        show_summary()
    elif args.show == "flow":
        show_flow()

    if args.plot == "arrivals":
        plot_arrivals()
    elif args.plot == "workload":
        plot_workload_by_role()

    if not any([args.run, args.show, args.plot]):
        parser.print_help()
