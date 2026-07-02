from __future__ import annotations

from pathlib import Path


def figure_exists(path: str | Path) -> bool:
    path = Path(path)
    return path.exists() and path.stat().st_size > 0
