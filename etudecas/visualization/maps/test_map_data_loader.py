from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etudecas.visualization.maps.map_data_loader import read_csv_rows


class MapDataLoaderTest(unittest.TestCase):
    def test_read_csv_rows_falls_back_to_nested_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "metrics.csv").write_text("id,value\nA,10\n", encoding="utf-8")

            rows = read_csv_rows(root / "metrics.csv")

            self.assertEqual(rows, [{"id": "A", "value": "10"}])


if __name__ == "__main__":
    unittest.main()
