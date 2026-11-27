"""Narrow tests of evidence validation and the shareable projection, entirely in memory."""
import unittest
from pathlib import Path
import struct
import zlib

from render import prepare_exhibit, resolve_template, clean_visual, private_note_path, reviewed_image, selected_rows, static_png


class ReviewedMaterialTests(unittest.TestCase):
    def setUp(self):
        public = {
            "name": "Cas fictif", "family": "Planification", "decision": "Choisir le seuil.",
            "method": "Comparer au témoin.", "finding": "Essai préparé.", "limit": "Un seul scénario.",
            "next_test": "Varier la demande.",
        }
        self.sha = "a" * 40
        self.cap = {
            **public, "id": "dossier", "name": "Interne", "status": "implemente",
            "external_ok": True, "public": public,
            "evidence": [{"branch": "dev", "sha": self.sha, "path": "confidentiel.csv"}],
        }
        self.review = {"snapshot": {"branches": {"dev": self.sha}}, "capabilities": [self.cap],
                       "gaps": [{"title": "Lacune interne", "impact": "A", "test": "B", "priority": "P1"}]}

    def test_external_projection_has_only_approved_wording(self):
        rows, gaps = selected_rows(self.review, "mixte", True, None)
        self.assertEqual(rows[0]["name"], "Cas fictif")
        self.assertEqual(rows[0]["evidence"], [])
        self.assertNotIn("Interne", str(rows))
        self.assertEqual(gaps, [])

    def test_external_copy_is_required_even_when_approved(self):
        del self.cap["public"]["limit"]
        with self.assertRaises(ValueError):
            selected_rows(self.review, "operations", True, None)

    def test_internal_proof_matches_exact_branch_head(self):
        self.cap["evidence"][0]["sha"] = "b" * 40
        with self.assertRaises(ValueError):
            selected_rows(self.review, "science", False, None)

    def test_external_question_has_private_destination(self):
        for path in (None, Path("client"), Path("client/interne.md")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                private_note_path(Path("client"), path, True, "Hypothèse interne")
        path = Path("dossier-prive/notes.md")
        self.assertEqual(private_note_path(Path("client"), path, True, "Hypothèse"), path.resolve())

    def test_external_png_requires_approval_of_its_exact_blob(self):
        ref = {"branch": "dev", "path": "figure.png", "blob": "b" * 40}
        fig = {"title": "Stocks", "caption": "Scénario témoin.", "evidence": ref}
        with self.assertRaisesRegex(ValueError, "approved_blob"):
            reviewed_image(fig, [ref], Path("."), True)

    def test_png_preserves_pixels_and_drops_text_metadata(self):
        def chunk(kind, data):
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        magic = b"\x89PNG\r\n\x1a\n"
        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
        pixels = chunk(b"IDAT", zlib.compress(b"\0\0")) + chunk(b"IEND", b"")
        png, size = static_png(magic + ihdr + chunk(b"tEXt", b"Author\0Interne") + pixels)
        self.assertEqual(size, (1, 1))
        self.assertEqual(png, magic + ihdr + pixels)

    def test_external_exhibits_only_use_reviewed_public_data(self):
        self.cap["exhibits"] = [{"kind": "table", "title": "Secret", "caption": "Interne",
                                 "columns": ["Code"], "rows": [["Non partagé"]]}]
        self.cap["public"]["exhibits"] = [{"kind": "flow", "title": "Suivi", "caption": "Schéma de méthode",
                                         "steps": [{"label": "Lot", "detail": "Entrée"},
                                                   {"label": "Service", "detail": "Sortie"}]}]
        items, _ = selected_rows(self.review, "operations", True, None)
        self.assertEqual([v["kind"] for v in items[0]["exhibits"]], ["flow"])
        self.assertNotIn("Secret", str(items))

    def test_focus_uses_meeting_order(self):
        second = dict(self.cap, id="second", public=dict(self.cap["public"], name="Deuxième cas"))
        self.review["capabilities"].append(second)
        items, _ = selected_rows(self.review, "mixte", True, ["second", "dossier"])
        self.assertEqual([i["name"] for i in items], ["Deuxième cas", "Cas fictif"])

    def test_unequal_table_width_fails(self):
        with self.assertRaisesRegex(ValueError, "colonnes"):
            prepare_exhibit({"kind": "table", "title": "Cas", "caption": "Hypothèses",
                             "columns": ["Paramètre", "Valeur"], "rows": [["Horizon"]]}, [], Path("."), False)

    def test_inverted_quantiles_fail(self):
        chart = {"kind": "band", "title": "Service", "unit": "%", "x_label": "Jour",
                 "caption": "Simulation", "categories": ["1", "2"], "series": [
                     {"name": n, "values": v} for n, v in (("P10", [40, 70]), ("P50", [50, 60]), ("P90", [70, 80]))]}
        with self.assertRaisesRegex(ValueError, "bornes"):
            clean_visual(chart)

    def test_unavailable_explicit_template_is_reported(self):
        with self.assertRaisesRegex(ValueError, "Modèle Scalian introuvable"):
            resolve_template(Path("modele-inexistant-pour-ce-test.pptx"), Path("."))

    def test_mismatched_series_is_rejected(self):
        fig = {"kind": "line", "title": "Stock", "unit": "Unités", "x_label": "Jour",
               "caption": "Exemple", "categories": ["1", "2"], "series": [{"name": "Stock", "values": [1]}]}
        with self.assertRaises(ValueError):
            clean_visual(fig)


if __name__ == "__main__":
    unittest.main()
