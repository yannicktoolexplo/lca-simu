#!/usr/bin/env python3
"""Validate V5-fed campaign results with the frozen V4 finalizer logic.

The statistical design and compact output schema are unchanged.  This adapter
only teaches the hash-pinned finalizer to reopen the V5 bridge and to expect the
V5 campaign adapter recorded in the campaign manifest.
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
    finalize_supplier_operating_point_full_campaign_v4 as implementation_v4,
)


EXPECTED_V4_FINALIZER_SHA256 = (
    "0a71a62a3ede37df18024ee9349e6f96e0fbfe80e6dd371f253215bac13e5984"
)
V5_CAMPAIGN_RUNNER = (
    Path(__file__).resolve().with_name("supplier_operating_point_full_campaign_v5.py")
)


class V5FinalizerAdapterError(RuntimeError):
    """The frozen finalizer or its V5 runner binding changed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v4.__file__).resolve()
    if _sha256_file(path) != EXPECTED_V4_FINALIZER_SHA256:
        raise V5FinalizerAdapterError(
            "The frozen V4 finalizer changed; refusing V5 reuse"
        )
    if not V5_CAMPAIGN_RUNNER.is_file():
        raise V5FinalizerAdapterError(
            f"Missing V5 campaign runner: {V5_CAMPAIGN_RUNNER}"
        )
    return path


@contextmanager
def patched_v5_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_runner_hash: Any = implementation_v4.SOURCE_RUNNER_SHA256
    implementation_v4.v4_bridge = v5_bridge
    implementation_v4.SOURCE_RUNNER_SHA256 = _sha256_file(V5_CAMPAIGN_RUNNER)
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.SOURCE_RUNNER_SHA256 = previous_runner_hash


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v5_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
