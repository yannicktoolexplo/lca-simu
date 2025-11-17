# supply_dynamic_sim.py
import matplotlib.pyplot as plt
from supply_network import get_supply_plan

def run_supply_simulation(material: str, site: str, duration_days: int, daily_demand: float):
    plan = get_supply_plan(site, seat_weight=130)
    delivery_info = plan.get(material)
    if not delivery_info:
        print(f"[ERREUR] Pas de plan d'approvisionnement pour {material} vers {site}")
        return

    delivery_qty = delivery_info["quantity"]
    delivery_freq = delivery_info["delivery_time"]  # en heures SimPy → 1 jour = 8h
    delivery_freq_days = int(delivery_freq // 8)

    print(f"[INFO] Simulation {material} vers {site} ({duration_days} jours)")
    print(f"  - Demande journalière : {daily_demand}")
    print(f"  - Livraison : {delivery_qty} toutes les {delivery_freq_days} jours")

    stock = 0.0
    stock_series = []
    deliveries = []
    shortages = []

    for day in range(1, duration_days + 1):
        # Livraison si le jour est un multiple
        if (day - 1) % delivery_freq_days == 0:
            stock += delivery_qty
            deliveries.append(day)
        else:
            deliveries.append(None)

        if stock >= daily_demand:
            stock -= daily_demand
            shortages.append(0)
        else:
            shortages.append(daily_demand - stock)
            stock = 0

        stock_series.append(stock)

    # Affichage texte
    total_shortage = sum(shortages)
    print(f"[RÉSULTAT] Manque total sur {duration_days} jours : {total_shortage:.1f} unités")

    # Graphe
    days = list(range(1, duration_days + 1))
    plt.figure(figsize=(10, 5))
    plt.plot(days, stock_series, label="Stock")
    plt.bar(days, shortages, color="red", alpha=0.3, label="Manque")
    plt.xlabel("Jour")
    plt.ylabel("Stock")
    plt.title(f"Stock de {material} vers {site}")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
