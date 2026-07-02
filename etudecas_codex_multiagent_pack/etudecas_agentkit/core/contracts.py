from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactContract:
    """Contrat simple d’entrée/sortie entre agents ou modules."""

    name: str
    required_inputs: list[str]
    produced_outputs: list[str]
    checks: list[str]
    metadata: dict[str, Any] | None = None
