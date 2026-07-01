from __future__ import annotations

import pandas as pd


def weighted_mean(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    missing = [column for column in weights if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns for weighted mean: {missing}")
    total = float(sum(weights.values()))
    if total <= 0:
        raise ValueError("Sum of weights must be positive")
    result = sum(frame[column] * weight for column, weight in weights.items()) / total
    return result


def simple_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns for mean: {missing}")
    return frame[columns].mean(axis=1)
