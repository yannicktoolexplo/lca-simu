from __future__ import annotations

import pandas as pd


def ensure_datetime(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Retourne une copie avec une colonne convertie en datetime."""
    result = df.copy()
    result[column] = pd.to_datetime(result[column], errors="raise")
    return result
