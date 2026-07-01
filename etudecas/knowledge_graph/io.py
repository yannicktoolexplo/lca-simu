from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import ensure_graph_shape


def load_graph(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"graph JSON must be an object: {path}")
    return ensure_graph_shape(data)


def save_graph(path: str | Path, graph: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


def append_provenance(graph: dict[str, Any], *, step: str, source: str, details: dict[str, Any] | None = None) -> None:
    meta = graph.setdefault("meta", {})
    entries = meta.setdefault("knowledge_graph_enrichment", [])
    if not isinstance(entries, list):
        entries = []
        meta["knowledge_graph_enrichment"] = entries
    entries.append(
        {
            "step": step,
            "source": source,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
    )
