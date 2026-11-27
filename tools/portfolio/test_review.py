"""Check evidence freshness and dependent gaps without touching the filesystem."""
import unittest

from review import qualify


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tip = "b" * 40
        self.blob = "c" * 40
        self.branch = "experiences/boucle"
        self.heads = {self.branch: self.tip}
        self.history = {("a" * 40, "sortie.csv"): self.blob}
        self.paths = {"sortie.csv": {self.branch: self.blob}}
        self.card = {
            "id": "flux", "method_ids": ["inventory"], "name": "Stock", "family": "Pilotage",
            "decision": "Fixer la réserve.", "method": "Comparer deux règles.",
            "finding": "Écart mesuré.", "limit": "Un seul horizon.", "next_test": "Prolonger le suivi.",
            "external_ok": False, "status": "resultat_archive",
            "evidence": [{"branch": self.branch, "sha": "a" * 40, "path": "sortie.csv", "blob": self.blob}],
        }
        self.gap = {"title": "Demande", "priority": "haute", "impact": "Sensibilité du résultat.",
                    "test": "Varier le profil de demande.", "capability_ids": ["flux"]}
        self.catalog = {"capabilities": [self.card], "gaps": [self.gap]}

    def test_unchanged_archive_keeps_reviewed_and_current_revisions(self):
        cards, held, gaps, _ = qualify(self.catalog, self.heads, self.paths, self.history)
        self.assertEqual((len(cards), len(held), len(gaps)), (1, 0, 1))
        self.assertEqual(cards[0]["evidence"][0]["reviewed_sha"], "a" * 40)
        self.assertEqual(cards[0]["evidence"][0]["sha"], self.tip)

    def test_changed_blob_suspends_claim_and_dependent_gap(self):
        self.paths["sortie.csv"][self.branch] = "d" * 40
        cards, held, gaps, held_gaps = qualify(self.catalog, self.heads, self.paths, self.history)
        self.assertEqual((len(cards), len(held), len(gaps), len(held_gaps)), (0, 1, 0, 1))

    def test_replay_requires_a_new_run_after_head_moves(self):
        self.card.update(status="reproduit", replay=dict(command="test", environment="3.11",
                         oracle="volume", tolerance="0", observed="4", manifest="sortie.csv"))
        self.assertFalse(qualify(self.catalog, self.heads, self.paths, self.history)[0])

    def test_unknown_historical_sha_cannot_be_reassigned(self):
        self.card["evidence"][0]["sha"] = "f" * 40
        self.assertFalse(qualify(self.catalog, self.heads, self.paths, self.history)[0])

    def test_unknown_gap_reference_is_an_error(self):
        self.gap["capability_ids"] = ["inconnu"]
        with self.assertRaises(ValueError):
            qualify(self.catalog, self.heads, self.paths, self.history)


if __name__ == "__main__":
    unittest.main()
