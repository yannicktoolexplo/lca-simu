from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VisualSpec:
    figure_id: str
    type: str
    data: dict[str, Any]
    labels: dict[str, str]
    output: dict[str, Any]

    @classmethod
    def from_dict(cls, spec: dict[str, Any]) -> "VisualSpec":
        return cls(
            figure_id=str(spec["figure_id"]),
            type=str(spec["type"]),
            data=dict(spec.get("data", {})),
            labels=dict(spec.get("labels", {})),
            output=dict(spec.get("output", {})),
        )

    def output_path(self, base_dir: str | Path = ".") -> Path:
        path = Path(self.output.get("path", f"outputs/figures/{self.figure_id}.png"))
        if path.is_absolute():
            return path
        return Path(base_dir) / path
