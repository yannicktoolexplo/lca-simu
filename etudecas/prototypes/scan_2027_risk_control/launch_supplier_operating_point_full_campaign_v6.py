#!/usr/bin/env python3
"""Launch the unchanged incident shards through the additive V6 adapters."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v6 as v6_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v5 as adapter_v5,
)


implementation_v4 = adapter_v5.implementation_v4
RUNNER = Path(__file__).resolve().with_name(
    "supplier_operating_point_full_campaign_v6.py"
)
V6LauncherAdapterError = adapter_v5.V5LauncherAdapterError
EXPECTED_V5_ADAPTER_SHA256 = (
    "59f1c33552f19bcf09c773733ece132e0e04d341c98807ca9c7087a2de1f4d13"
)


def validate_frozen_implementation() -> Path:
    adapter_path = Path(adapter_v5.__file__).resolve()
    if adapter_v5._sha256_file(adapter_path) != EXPECTED_V5_ADAPTER_SHA256:  # noqa: SLF001
        raise V6LauncherAdapterError("Frozen V5 launcher adapter changed")
    path = adapter_v5.validate_frozen_implementation()
    if not RUNNER.is_file():
        raise V6LauncherAdapterError(f"Missing V6 campaign runner: {RUNNER}")
    return path


@contextmanager
def patched_v6_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_runner: Any = implementation_v4.RUNNER
    implementation_v4.v4_bridge = v6_bridge
    implementation_v4.RUNNER = RUNNER
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.RUNNER = previous_runner


# Compatibility name consumed by the mature downstream relay.
patched_v5_context = patched_v6_context


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v6_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
