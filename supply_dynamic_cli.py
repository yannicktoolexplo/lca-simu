# supply_dynamic_cli.py
# -*- coding: utf-8 -*-
"""
Script CLI pour lancer une simulation dynamique du flux matière dans le réseau d'approvisionnement.

Exemple :
    python supply_dynamic_cli.py --material aluminium --duration 30
"""

import argparse
from supply_dynamic_sim import run_supply_simulation


def main():
    parser = argparse.ArgumentParser(description="Simuler le flux dynamique dans le réseau d'appro")
    parser.add_argument("--material", required=True, help="Nom du matériau (ex: aluminium, foam, fabric, paint)")
    parser.add_argument("--duration", type=int, default=30, help="Durée de simulation (en jours)")
    parser.add_argument("--daily_demand", type=float, default=20.0, help="Demande journalière du site final")
    parser.add_argument("--site", default="France", help="Nom du site final (France, UK, Texas, California)")
    args = parser.parse_args()

    run_supply_simulation(
        material=args.material.lower(),
        duration_days=args.duration,
        site_target=args.site,
        demand_per_day=args.daily_demand,
    )


if __name__ == "__main__":
    main()
