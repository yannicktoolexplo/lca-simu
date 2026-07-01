from __future__ import annotations

from typing import Any

import pandas as pd

from etudecas.kpi.aggregators import simple_mean, weighted_mean
from etudecas.kpi.normalizers import bounded_score
from etudecas.kpi.tree import detect_cycles


class KPIEngine:
    """Calcule des KPI élémentaires et composites depuis une config YAML."""

    def __init__(self, kpi_tree: dict[str, Any]):
        self.kpi_tree = kpi_tree
        cycles = detect_cycles(kpi_tree)
        if cycles:
            raise ValueError(f"KPI tree contains cycles: {cycles}")

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        computed: set[str] = set()

        def compute_node(name: str) -> None:
            if name in computed:
                return
            if name not in self.kpi_tree:
                raise ValueError(f"Unknown KPI node: {name}")
            spec = self.kpi_tree[name]
            kind = spec.get("type")
            if kind == "elementary":
                source = spec.get("source_column")
                if source not in result.columns:
                    raise ValueError(f"Missing source column for KPI {name}: {source}")
                result[name] = bounded_score(
                    result[source],
                    direction=str(spec.get("direction", "maximize")),
                    target=float(spec.get("target", 1.0)),
                    min_value=float(spec.get("min", 0.0)),
                    max_value=float(spec.get("max", 1.0)),
                )
            elif kind == "composite":
                children = spec.get("children", {})
                child_names = list(children) if isinstance(children, dict) else list(children or [])
                for child in child_names:
                    compute_node(child)
                aggregation = spec.get("aggregation", "weighted_mean")
                if aggregation == "weighted_mean":
                    weights = children if isinstance(children, dict) else {child: 1.0 for child in child_names}
                    result[name] = weighted_mean(result, {str(k): float(v) for k, v in weights.items()})
                elif aggregation == "mean":
                    result[name] = simple_mean(result, child_names)
                else:
                    raise ValueError(f"Unknown aggregation for {name}: {aggregation}")
            else:
                raise ValueError(f"Unknown KPI type for {name}: {kind}")
            computed.add(name)

        for node_name in self.kpi_tree:
            compute_node(node_name)
        return result
