from __future__ import annotations

from pathlib import Path

import pandas as pd


class DataLoader:
    """Chargement générique des datasets."""

    @staticmethod
    def load_csv(path: str | Path, **kwargs) -> pd.DataFrame:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        return pd.read_csv(path, **kwargs)
