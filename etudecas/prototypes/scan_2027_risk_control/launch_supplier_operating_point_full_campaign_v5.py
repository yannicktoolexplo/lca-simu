#!/usr/bin/env python3
"""Launch the frozen incident campaign through the V5 operating-point bridge.

All discovery, smoke and shard scheduling remains the hash-pinned V4 launcher.
Only its bridge validator and default runner are temporarily redirected to the
additive V5 adapters.  This keeps the mature 3,330-row result format intact.
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
    launch_supplier_operating_point_full_campaign_v4 as implementation_v4,
)


EXPECTED_V4_LAUNCHER_SHA256 = (
    "ee79cfc4d61ca98e7030217bdbf52886402e68074b66f7c7380d5e9890838e4c"
)
RUNNER = (
    Path(__file__).resolve().with_name("supplier_operating_point_full_campaign_v5.py")
)


class V5LauncherAdapterError(RuntimeError):
    """The frozen launcher implementation or adapter contract changed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v4.__file__).resolve()
    if _sha256_file(path) != EXPECTED_V4_LAUNCHER_SHA256:
        raise V5LauncherAdapterError(
            "The frozen V4 launcher changed; refusing V5 reuse"
        )
    if not RUNNER.is_file():
        raise V5LauncherAdapterError(f"Missing V5 campaign runner: {RUNNER}")
    return path


@contextmanager
def patched_v5_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_runner: Any = implementation_v4.RUNNER
    implementation_v4.v4_bridge = v5_bridge
    implementation_v4.RUNNER = RUNNER
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.RUNNER = previous_runner


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v5_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
