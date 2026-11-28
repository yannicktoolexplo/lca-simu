"""Vérifier en mémoire les trois dossiers, les corrigés et les pièges de provenance."""
import copy
import re
import unittest
from datetime import date
from unittest.mock import patch

import eval_mrp


class MrpEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = eval_mrp.read_json(eval_mrp.DATA / "cases.json")
        cls.rules = eval_mrp.read_json(eval_mrp.DATA / "oracles.json")

    def answer(self, case):
        return {
            "constats": {
                key: {"valeur": copy.deepcopy(rule["valeur"]), "pieces": list(rule["pieces"])}
                for key, rule in self.rules[case].items()
            },
            "note_reunion": "Texte témoin pour les contrôles structurés.",
        }

    def test_cases_have_answers_and_source_ids(self):
        self.assertEqual(set(self.cases), {"stock", "prevision", "gel"})
        for case, packet in self.cases.items():
            rules = self.rules[case]
            self.assertEqual(rules.keys(), packet["champs"].keys())
            for rule in rules.values():
                self.assertTrue(set(rule["pieces"] + rule.get("aussi", [])) <= packet["pieces"].keys())
            self.assertTrue(eval_mrp.score(rules, self.answer(case))["reussi_controles_structures"])

    def test_numeric_oracles_follow_source_rows(self):
        stock = self.cases["stock"]["pieces"]
        opening, receipts, shipments, adjustment, closing = map(int, re.findall(r"\d+", stock["B2"]))
        self.assertEqual(opening + receipts - shipments + adjustment, closing)
        old = [int(x) for x in re.findall(r"\d+", stock["B1"])]
        self.assertEqual(old[0] + old[1] - old[2] + old[3], old[4])
        lots = [int(re.search(r"(\d+) unités", stock[key])[1]) for key in ("R1", "R2", "R3", "R4", "R5")]
        delta = closing - old[4]
        self.assertEqual(delta, sum(lots))
        self.assertEqual(delta, self.rules["stock"]["ecart_stock"]["valeur"])
        self.assertEqual(shipments - old[2], self.rules["stock"]["ecart_expeditions"]["valeur"])
        self.assertEqual(len(lots), self.rules["stock"]["lots_supplementaires"]["valeur"])
        forecast = self.cases["prevision"]["pieces"]
        terms = [int(re.search(r", (\d+)\.", forecast[key])[1]) for key in ("F1", "F2")]
        self.assertEqual(terms, self.rules["prevision"]["decomposition"]["valeur"])
        self.assertEqual(sum(terms), self.rules["prevision"]["besoin_reconstitue"]["valeur"])
        orders = self.cases["gel"]["pieces"]
        for prefix, order in (("A", "OF01"), ("B", "OF02")):
            before, after = orders[prefix + "1"], orders[prefix + "2"]
            first, second = [date.fromisoformat(row[-11:-1]) for row in (before, after)]
            zone = 1 if (first - date(2025, 3, 31)).days < 28 else 2
            quantities = [int(re.search(r"(\d+) unités", row)[1]) for row in (before, after)]
            statuses = [row.split(", ")[1] for row in (before, after)]
            actual = [zone, (second - first).days, quantities[1] - quantities[0], statuses[0] != statuses[1]]
            self.assertEqual(actual, self.rules["gel"][order]["valeur"])

    def test_prompt_reads_only_case_data(self):
        for case in self.cases:
            for with_skill in (False, True):
                with patch.object(eval_mrp, "read_json", return_value=self.cases) as reader:
                    prompt = eval_mrp.make_prompt(case, with_skill)
                reader.assert_called_once_with(eval_mrp.DATA / "cases.json")
                self.assertIn(self.cases[case]["question"], prompt)
                self.assertEqual("# Diagnostic supply chain" in prompt, with_skill)

    def test_rejects_coincidences_future_data_fictitious_execution_and_wrong_owner(self):
        changes = [
            ("stock", "ecart_stock", "valeur", 107800, "calcul"),
            ("stock", "besoin_par_ordre", "valeur", {"T01": None, "T02": "N11", "T03": "N12", "T04": None, "T05": None}, "incertitude"),
            ("stock", "decision", "valeur", "bons_livraison_client", "suite"),
            ("prevision", "besoin_reconstitue", "pieces", ["M1", "F4"], "sources"),
            ("prevision", "regroupement_systematique", "valeur", "demontre", "incertitude"),
            ("gel", "OF01", "pieces", ["A1", "A3"], "sources"),
            ("gel", "OF01", "valeur", [1, 4, 0, 0], "calcul"),
            ("gel", "fin_reelle_OF01", "valeur", "2025-04-28", "incertitude"),
        ]
        for case, field, key, replacement, axis in changes:
            with self.subTest(case=case, field=field, key=key):
                answer = self.answer(case)
                answer["constats"][field][key] = replacement
                result = eval_mrp.score(self.rules[case], answer)
                self.assertFalse(result["reussi_controles_structures"])
                self.assertIn(field, result["champs_en_echec"][axis])

    def test_missing_value_differs_from_null(self):
        answer = self.answer("gel")
        del answer["constats"]["fin_reelle_OF01"]["valeur"]
        with self.assertRaises(ValueError):
            eval_mrp.score(self.rules["gel"], answer)


if __name__ == "__main__":
    unittest.main()
