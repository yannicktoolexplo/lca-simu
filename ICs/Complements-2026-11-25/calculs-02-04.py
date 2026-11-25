"""Recalculs pédagogiques des thèmes 2 à 4, complément du 2026-11-25.

Exécution : python calculs-02-04.py. Les résultats publics du cahier sont
identifiés séparément des nouveaux exemples synthétiques.
"""
import json
from math import ceil
from pathlib import Path


def calculate():
    emergency = []
    for fraction, on_time in [(1, True), (0.9, True), (0.7, True), (1, False)]:
        usable = 1000 * fraction if on_time else 0
        gap = max(0, 1850 - 150 - usable)
        order = 200 * ceil(max(400, gap) / 200) if gap else 0
        emergency.append({
            "fraction_longue_usable": fraction, "liberation_avant_J10": on_time,
            "arrivage_utilisable_kg": usable, "manque_net_kg": gap,
            "commande_minimale_kg": order, "capacite_suffisante": order <= 800,
            "manque_apres_achat_au_plafond_kg": max(0, gap - 800),
        })
    audits = []
    for x, y in [(0, 0), (-2, 0), (0, 4), (-2, 4), (-2, 3)]:
        c, d = 70 + x, 65 + y
        third = [name for name, score in [("C", c), ("D", d)] if score == max(c, d)]
        audits.append({"x_points": x, "y_points": y, "C_points": c,
                       "D_points": d, "troisiemes_possibles": third})
    depot = [{"jour": j, "besoin_cumule_unites": 10 * j,
              "solde_arrivee_J5_unites": 40 + (10 if j >= 5 else 0) - 10 * j,
              "solde_arrivee_J6_unites": 40 + (10 if j >= 6 else 0) - 10 * j}
             for j in range(1, 7)]
    return {"ratios_recalcules_depuis_cahier": {
                "theme_02_configurations_sans_rupture": 46 / 60,
                "theme_03_cotations_qui_modifient_selection": 16 / 84},
            "theme_02_exemple_pedagogique": emergency,
            "theme_03_exemple_pedagogique": audits,
            "theme_04_exemple_pedagogique": depot,
            "theme_04_jours_de_quantite_statique": (40 + 10) / 10}


if __name__ == "__main__":
    path = Path(__file__).with_name("themes-02-04.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    computed = calculate()
    if data["calculs_executes"] != computed:
        raise SystemExit("Écart entre les calculs reproduits et le JSON livré")
    print(json.dumps(computed, ensure_ascii=False, indent=2))
