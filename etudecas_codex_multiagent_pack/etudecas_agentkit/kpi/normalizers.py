from __future__ import annotations

import numpy as np
import pandas as pd


def bounded_score(
    values: pd.Series,
    *,
    direction: str,
    target: float,
    min_value: float,
    max_value: float,
) -> pd.Series:
    """Convertit une valeur brute en score 0..1.

    `maximize` : 1 au niveau de la cible ou au-dessus.
    `minimize` : 1 au niveau de la cible ou en-dessous.
    """
    values = pd.to_numeric(values, errors="coerce")
    direction = direction.lower()

    if direction == "maximize":
        denominator = target - min_value
        if denominator == 0:
            raise ValueError("target and min_value must differ for maximize normalization")
        score = (values - min_value) / denominator
    elif direction == "minimize":
        denominator = max_value - target
        if denominator == 0:
            raise ValueError("max_value and target must differ for minimize normalization")
        score = 1 - ((values - target) / denominator)
    else:
        raise ValueError(f"Unknown direction: {direction}")

    return pd.Series(np.clip(score, 0.0, 1.0), index=values.index)
