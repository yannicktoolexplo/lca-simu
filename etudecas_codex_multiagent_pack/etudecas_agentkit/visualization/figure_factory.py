from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from etudecas_agentkit.visualization.specs import VisualSpec


class FigureFactory:
    """Fabrique de figures pilotée par YAML."""

    def __init__(self, spec: dict[str, Any] | VisualSpec):
        self.spec = spec if isinstance(spec, VisualSpec) else VisualSpec.from_dict(spec)

    def render(self, df: pd.DataFrame, base_dir: str | Path = ".") -> Path:
        if self.spec.type == "3d_trajectory":
            return self._render_3d_trajectory(df, base_dir)
        if self.spec.type == "time_series":
            return self._render_time_series(df, base_dir)
        raise ValueError(f"Unknown figure type: {self.spec.type}")

    def _render_3d_trajectory(self, df: pd.DataFrame, base_dir: str | Path) -> Path:
        data = self.spec.data
        x, y, z = data["x"], data["y"], data["z"]
        entity = data.get("entity")
        for column in [x, y, z]:
            if column not in df.columns:
                raise ValueError(f"Missing visual column: {column}")

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        if entity and entity in df.columns:
            for label, group in df.groupby(entity):
                ax.plot(group[x], group[y], group[z], marker="o", label=str(label))
            ax.legend()
        else:
            ax.plot(df[x], df[y], df[z], marker="o")

        labels = self.spec.labels
        ax.set_title(labels.get("title", self.spec.figure_id))
        ax.set_xlabel(labels.get("x", x))
        ax.set_ylabel(labels.get("y", y))
        ax.set_zlabel(labels.get("z", z))
        return self._save(fig, base_dir)

    def _render_time_series(self, df: pd.DataFrame, base_dir: str | Path) -> Path:
        data = self.spec.data
        x = data["x"]
        y_columns = data.get("y", [])
        if isinstance(y_columns, str):
            y_columns = [y_columns]
        entity = data.get("entity")
        missing = [column for column in [x, *y_columns] if column not in df.columns]
        if missing:
            raise ValueError(f"Missing visual columns: {missing}")

        fig, ax = plt.subplots()
        if entity and entity in df.columns:
            for label, group in df.groupby(entity):
                for y in y_columns:
                    ax.plot(pd.to_datetime(group[x]), group[y], marker="o", label=f"{label}:{y}")
        else:
            for y in y_columns:
                ax.plot(pd.to_datetime(df[x]), df[y], marker="o", label=y)

        labels = self.spec.labels
        ax.set_title(labels.get("title", self.spec.figure_id))
        ax.set_xlabel(labels.get("x", x))
        ax.set_ylabel(labels.get("y", "value"))
        if y_columns or entity:
            ax.legend()
        fig.autofmt_xdate()
        return self._save(fig, base_dir)

    def _save(self, fig, base_dir: str | Path) -> Path:
        output_path = self.spec.output_path(base_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dpi = int(self.spec.output.get("dpi", 120))
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return output_path
