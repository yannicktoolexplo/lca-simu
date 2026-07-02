from __future__ import annotations

import numpy as np
import pandas as pd


def euclidean_step_distance(df: pd.DataFrame, dimensions: list[str]) -> pd.Series:
    """Distance entre points successifs d’une trajectoire."""
    values = df[dimensions].to_numpy(dtype=float)
    if len(values) == 0:
        return pd.Series(dtype=float)
    diffs = np.diff(values, axis=0)
    distances = np.sqrt((diffs**2).sum(axis=1))
    return pd.Series([0.0, *distances.tolist()], index=df.index)
