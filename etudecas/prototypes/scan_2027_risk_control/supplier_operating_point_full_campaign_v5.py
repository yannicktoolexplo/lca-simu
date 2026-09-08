#!/usr/bin/env python3
"""V5 entry point for the frozen 3,330-row V4 incident campaign.

The incident design itself is intentionally unchanged.  This narrow adapter
replaces only the operating-point bridge by the accepted V5 bridge and makes
the campaign manifest pin this V5 entry point as its runner.  The imported V4
implementation is hash-pinned and is never edited by this module.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v5 as v5_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4 as implementation_v4,
)


EXPECTED_V4_IMPLEMENTATION_SHA256 = (
    "3bc8795490c6ef9ac1fef25d5dedb22811306ae869477df57e70d483881a5d9d"
)
ADAPTER_PATH = Path(__file__).resolve()


class V5CampaignAdapterError(RuntimeError):
    """The frozen campaign implementation or adapter contract changed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v4.__file__).resolve()
    if _sha256_file(path) != EXPECTED_V4_IMPLEMENTATION_SHA256:
        raise V5CampaignAdapterError(
            "The frozen V4 incident implementation changed; refusing V5 reuse"
        )
    return path


@contextmanager
def patched_v5_context() -> Iterator[None]:
    """Install the V5 bridge only for the duration of one CLI invocation."""

    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_file: Any = implementation_v4.__file__
    implementation_v4.v4_bridge = v5_bridge
    # The planner signs ``Path(__file__)`` as the runner.  Point that binding to
    # this adapter so every later shard validates and executes the same entry.
    implementation_v4.__file__ = str(ADAPTER_PATH)
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.__file__ = previous_file


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v5_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
