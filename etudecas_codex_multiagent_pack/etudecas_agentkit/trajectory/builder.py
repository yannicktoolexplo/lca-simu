from __future__ import annotations

from typing import Any

import pandas as pd


class TrajectoryBuilder:
    """Construit une trajectoire depuis des dimensions configurées."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        dimensions = list(self.config.get("dimensions", []))
        time_column = self.config.get("time_column")
        entity_column = self.config.get("entity_column")
        required = [time_column, entity_column, *dimensions]
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise ValueError(f"Missing columns for trajectory: {missing}")

        result = df[required].copy()
        result[time_column] = pd.to_datetime(result[time_column])
        return result.sort_values([entity_column, time_column]).reset_index(drop=True)
