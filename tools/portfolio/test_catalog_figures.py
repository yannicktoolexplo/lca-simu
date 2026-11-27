"""Read-only numerical oracles for the example charts in catalog.json."""
import csv
import io
import json
import subprocess
import unittest
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
CARDS = {c["id"]: c for c in json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))["capabilities"]}


def rows(card, filename):
    ref, = [e for e in CARDS[card]["evidence"] if e["path"].rsplit("/", 1)[-1] == filename]
    obj = f"{ref['sha']}:{ref['path']}"
    data = subprocess.check_output(["git", "-C", str(HERE), "show", obj])
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


class CatalogFigureTests(unittest.TestCase):
    def check_views(self, card, expected):
        for view in (CARDS[card], CARDS[card]["public"]):
            self.assertEqual([item["values"] for item in view["visual"]["series"]], expected)

    def test_cumulative_impact(self):
        card = "sddlca-52s"
        source = {int(r["week"]): r for r in rows(card, "poc_method_cumulative_comparison.csv")}
        cols = ["classical_cumulative_kgCO2e", "dynamic_cumulative_kgCO2e", "sdd_cumulative_kgCO2e"]
        self.check_views(card, [[round(float(source[w][c]), 1) for w in (13, 26, 39, 52)] for c in cols])

    def test_weekly_coverage(self):
        card = "politiques-stock-service"
        source = {r["policy_name"]: r for r in rows(card, "poc_policy_decision_summary.csv")}
        policies = ["baseline", "inventory_buffer", "low_carbon", "service_first"]
        self.check_views(card, [[float(source[p]["same_week_service_pct"]) for p in policies]])

    def test_long_horizon(self):
        card = "adaptation-20ans"
        source = {r["method"]: float(r["total_kgCO2e"]) for r in
                  rows(card, "ha_method_comparison.csv") if r["policy_label"] == "Baseline degradee"}
        order = ["Classical LCA", "Time-Dependent DLCA", "State-Dependent Dynamic LCA"]
        self.check_views(card, [[round(source[m] / 1000, 1) for m in order]])

    def test_incident_probability(self):
        card = "risque-fournisseur-calibre"
        groups = [[], [], []]
        for row in rows(card, "prediction_test_scored_rows.csv"):
            prob = float(row["predicted_incident_probability_30d"])
            index = 0 if prob < 0.1 else 1 if prob < 0.2 else 2
            groups[index].append((prob, float(row["incident_next_30d"])))
        self.assertEqual([len(g) for g in groups], [328, 106, 46])
        self.check_views(card, [[round(100 * mean(row[i] for row in g), 1) for g in groups] for i in (0, 1)])

    def test_backlog_figure_commentary(self):
        source = rows("stock-retard-52s", "poc_supply_chain_states.csv")
        self.assertEqual(next(r["week"] for r in source if float(r["fg_stock_end"]) == 0), "26")
        peak = max(source, key=lambda r: float(r["backlog_end"]))
        self.assertEqual((peak["week"], round(float(peak["backlog_end"]), 1)), ("37", 36.4))
        self.assertEqual((source[-1]["week"], float(source[-1]["backlog_end"])), ("52", 0))


if __name__ == "__main__":
    unittest.main()
