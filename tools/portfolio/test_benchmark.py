"""Check the internal comparison and that meeting inputs stay unchanged."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import review
from benchmark import protocol_href, render_comparison


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.source = {"product": "Produit témoin", "title": "Démonstration publique",
                       "url": "https://example.org/demo", "checked": "2026-11-27",
                       "kind": "démonstration", "observation": "Le film affiche le stock par site."}
        self.case = {"id": "stock", "title": "Rupture entre deux sites",
                     "question": "Quel stock couvre le retard ?", "capabilities": ["flux", "retard"],
                     "references": ["demo"], "opportunity": "Relier un délai au lot concerné.",
                     "procedure": ["Décaler une réception.", "Comparer au témoin."],
                     "metric": "Unités livrées à la date prévue.", "decision": "Vérifier le stock de fin."}
        self.registry = {"sources": {"demo": self.source}, "cases": [self.case]}
        self.head = "b" * 40
        self.evidence = {"path": "runs/stock.csv", "branch": "production",
                         "sha": self.head, "reviewed_sha": "a" * 40}
        self.card = {"id": "flux", "name": "Suivi du stock", "status": "resultat_archive",
                     "finding": "Le stock ferme à 10 unités.", "limit": "Un seul site.",
                     "evidence": [self.evidence]}
        self.review = {"capabilities": [self.card], "suspended": [
            {"id": "retard", "title": "Lecture du retard", "reasons": ["Branche absente"]}]}

    def report(self):
        return render_comparison(self.registry, self.review, "../tools/portfolio/essai-tampon.md",
                                 github_url="https://github.com/equipe/depot")

    def test_marks_source_scope_freshness_and_internal_evidence(self):
        report = self.report()
        for text in ("27/11/2026", "https://example.org/demo", self.source["observation"],
                     "résultat archivé", self.card["finding"], self.card["limit"],
                     self.evidence["branch"], self.head, self.evidence["reviewed_sha"],
                     self.evidence["path"], "fiche suspendue", "Branche absente",
                     f"https://github.com/equipe/depot/blob/{self.head}/runs/stock.csv",
                     "Aucune mesure comparative", "Non mesurée", "essai-tampon.md",
                     "2. Comparer au témoin."):
            with self.subTest(text=text):
                self.assertIn(text, report)

    def test_unassigned_sources_are_in_the_opening_with_their_provenance(self):
        register = dict(self.source, title="Registre public", url="https://example.org/registry",
                        observation="Le registre identifie l’éditeur du produit.")
        self.registry["sources"]["registre"] = register
        report = self.report()
        self.assertLess(report.index(register["url"]), report.index(self.case["title"]))
        self.assertEqual(report.count(self.source["url"]), 1)

    def test_rejects_unresolved_links_and_empty_cases(self):
        for field in ("references", "capabilities"):
            with self.subTest(field=field), patch.dict(self.case, {field: ["autre"]}):
                with self.assertRaisesRegex(ValueError, field):
                    self.report()
        with patch.dict(self.registry, cases=[]), self.assertRaisesRegex(ValueError, "cas"):
            self.report()
        with patch.dict(self.registry, cases=[self.case, self.case]), self.assertRaisesRegex(ValueError, "répété"):
            self.report()

    def test_rejects_missing_public_source_provenance(self):
        for field, invalid in (("url", "demo.html"), ("checked", "2026-13-01"), ("observation", " ")):
            with self.subTest(field=field), patch.dict(self.source, {field: invalid}):
                with self.assertRaisesRegex(ValueError, field):
                    self.report()

    def test_opt_in_adds_only_the_internal_report(self):
        inventory = {"branches": [{"name": "production", "sha": self.head, "file_count": 1}],
                     "methods": [{"id": "stock", "label": "Stock", "counts": {"code": 1},
                                  "branches": ["production"]}], "tools": []}
        sha = self.head
        source = {"branch": "production", "sha": sha, "blob": "c" * 40, "path": "runs/stock.csv"}
        card = dict(self.card, family="Flux", method_ids=["stock"], decision="Fixer le seuil.",
                    method="Rejouer la semaine.", next_test="Étendre au mois.", external_ok=False,
                    evidence=[source])
        paused = dict(card, id="retard", evidence=[dict(source, path="runs/retard.csv")],
                      finding="Ancien résultat suspendu.")
        catalog = {"capabilities": [card, paused], "gaps": []}
        snapshot = inventory, {"production": sha}, {"runs/stock.csv": {"production": source["blob"]}}
        with TemporaryDirectory() as folder, patch.object(review, "load_snapshot", return_value=snapshot):
            root = Path(folder)
            plain, compared = root / "standard", root / "comparée"
            with patch.object(review, "read_json", side_effect=[catalog]) as read:
                review.run(root, root / "catalog.json", plain, root)
                self.assertEqual(read.call_count, 1)
            with patch.object(review, "read_json", side_effect=[catalog, self.registry]):
                review.run(root, root / "catalog.json", compared, root, compare_solutions=True)
            original = {path.name for path in plain.iterdir()}
            self.assertEqual({path.name for path in compared.iterdir()} - original, {"comparaison-solutions.md"})
            for name in original:
                self.assertEqual((plain / name).read_bytes(), (compared / name).read_bytes())
            report = (compared / "comparaison-solutions.md").read_text(encoding="utf-8")
            self.assertNotIn(paused["finding"], report)
            self.assertNotIn(self.source["product"], (compared / "review.json").read_text(encoding="utf-8"))
            self.assertIn("fiche suspendue", report)
            self.assertEqual((compared / unquote(protocol_href(compared))).resolve(),
                             Path(review.__file__).with_name("essai-tampon.md").resolve())


if __name__ == "__main__":
    unittest.main()
