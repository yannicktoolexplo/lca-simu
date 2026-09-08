#!/usr/bin/env python3
"""Launch the unchanged incident shards through the additive V7 adapters."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as v7_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v6 as adapter_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


implementation_v4 = adapter_v6.implementation_v4
RUNNER = (
    Path(__file__).resolve().with_name("supplier_operating_point_full_campaign_v7.py")
)
V7LauncherAdapterError = adapter_v6.V6LauncherAdapterError
EXPECTED_V6_ADAPTER_SHA256 = (
    "5b6f166d753c6a8e25b7da3156fe6815ec80457d09e41f7f051939a4b9873cec"
)


def validate_frozen_implementation() -> Path:
    trace_package.validate_frozen_v7_protocol()
    path = Path(adapter_v6.__file__).resolve()
    digest = adapter_v6.adapter_v5._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V6_ADAPTER_SHA256:
        raise V7LauncherAdapterError(f"Frozen V6 launcher adapter changed: {digest}")
    parent = adapter_v6.validate_frozen_implementation()
    if not RUNNER.is_file():
        raise V7LauncherAdapterError(f"Missing V7 campaign runner: {RUNNER}")
    return parent


@contextmanager
def patched_v7_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_runner: Any = implementation_v4.RUNNER
    previous_seeds: Any = implementation_v4.EXPECTED_CAMPAIGN_SEEDS
    implementation_v4.v4_bridge = v7_bridge
    implementation_v4.RUNNER = RUNNER
    implementation_v4.EXPECTED_CAMPAIGN_SEEDS = trace_package.CAMPAIGN_SEEDS
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.RUNNER = previous_runner
        implementation_v4.EXPECTED_CAMPAIGN_SEEDS = previous_seeds


# Compatibility name consumed by the mature downstream relay.
patched_v5_context = patched_v7_context


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v7_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
