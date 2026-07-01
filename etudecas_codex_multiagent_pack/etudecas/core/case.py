from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etudecas.core.config_loader import load_yaml


@dataclass(frozen=True)
class CaseStudy:
    """Configuration d’un cas d’étude.

    Le cas sait où sont les données, les KPI, les visuels et les règles.
    Il ne contient pas de logique métier exécutable.
    """

    case_id: str
    business_question: str
    data_config: dict[str, Any]
    trajectory_config: dict[str, Any]
    kpi_tree: dict[str, Any]
    visuals: dict[str, str]
    validation_rules_path: str
    raw_config: dict[str, Any]
    base_dir: Path

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CaseStudy":
        path = Path(path)
        raw = load_yaml(path)
        required = ["case_id", "data", "trajectory", "kpi_tree", "visuals", "validation_rules"]
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError(f"Missing required case sections in {path}: {missing}")

        return cls(
            case_id=str(raw["case_id"]),
            business_question=str(raw.get("business_question", "")),
            data_config=dict(raw["data"]),
            trajectory_config=dict(raw["trajectory"]),
            kpi_tree=dict(raw["kpi_tree"]),
            visuals=dict(raw["visuals"]),
            validation_rules_path=str(raw["validation_rules"]),
            raw_config=raw,
            base_dir=path.resolve().parents[2] if path.parts[-3:-1] == ("configs", "cases") else path.resolve().parent,
        )

    def resolve_path(self, path: str | Path) -> Path:
        path = Path(path)
        if path.is_absolute():
            return path
        return self.base_dir / path
