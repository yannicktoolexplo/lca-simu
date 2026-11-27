"""Contrôles en mémoire du rapprochement des exports du cas tampon."""
import csv
import io
import unittest
from contextlib import redirect_stdout

import check_buffer as check


class BufferTests(unittest.TestCase):
    def setUp(self):
        self.reference = check.read_reference()
        self.header = list(check.KEY_FIELDS + check.MEASURES)
        self.rows = [list(key) + list(measures.values()) for key, measures in self.reference.items()]

    def load(self, rows, header=None):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(self.header if header is None else header)
        writer.writerows(rows)
        stream.seek(0)
        return check.read_observed(stream, self.reference)

    def compare(self, observed):
        output = io.StringIO()
        with redirect_stdout(output):
            code = check.compare(self.reference, observed)
        return code, output.getvalue()

    def test_all_four_runs_and_fifo_indicators(self):
        observed = self.load(reversed(self.rows))
        code, output = self.compare(observed)
        self.assertEqual(code, 0)
        self.assertIn("CONFORME", output)
        self.assertIn("choc, stock initial 0 pièces | échéance 5/15 | livré fin J3 15/15"
                      " | retard 15 pièces-jours | stock fin J3 0 pièces", output)
        for regime, stock in (("nominal", 0), ("nominal", 10), ("choc", 10)):
            self.assertIn(f"{regime}, stock initial {stock} pièces | échéance 15/15"
                          f" | livré fin J3 15/15 | retard 0 pièces-jours | stock fin J3 {stock}", output)

    def test_missing_day_and_measured_difference_both_reported(self):
        self.rows.pop(0)
        self.rows[0][self.header.index("recu")] = "4"
        code, output = self.compare(self.load(self.rows))
        self.assertEqual(code, 1)
        self.assertIn("nominal, stock initial 0, J1, ligne absente", output)
        self.assertIn("nominal, stock initial 0, J2, recu attendu 5, observé 4", output)
        self.assertIn("échéance ?/15", output)

    def test_daily_difference_without_impact_on_final_total(self):
        self.rows[0][self.header.index("stock_fin")] = 1
        code, output = self.compare(self.load(self.rows))
        self.assertEqual(code, 1)
        self.assertIn("ÉCART", output)
        self.assertIn("J1, stock_fin attendu 0, observé 1", output)
        self.assertNotIn("INCOMPLET", output)

    def test_missing_cell_and_column_never_become_zero(self):
        self.rows[0][-1] = ""
        for observed in (self.load(self.rows), self.load([row[:-1] for row in self.rows], self.header[:-1])):
            with self.subTest():
                code, output = self.compare(observed)
                self.assertEqual(code, 1)
                self.assertIn("INCOMPLET", output)
                self.assertIn("J1, reliquat", output)
                self.assertIn("retard ? pièces-jours", output)
                self.assertNotIn("ÉCART", output)

    def test_invalid_exports(self):
        sample = self.rows[0]
        invalid = (
            (self.header, [sample, sample]),
            (self.header + ["jour"], []),
            (self.header + ["kg"], []),
            (self.header[1:], []),
            (self.header, [sample[:-1]]),
            (self.header, [sample[:2] + ["J4"] + sample[3:]]),
            (self.header, [sample[:-1] + ["1.2"]]),
            (self.header, [sample[:-1] + ["-1"]]),
        )
        for header, rows in invalid:
            with self.subTest(header=header, rows=rows), self.assertRaises(ValueError):
                self.load(rows, header)


if __name__ == "__main__":
    unittest.main()
