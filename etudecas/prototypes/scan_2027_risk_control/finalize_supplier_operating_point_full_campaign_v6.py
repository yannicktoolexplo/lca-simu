#!/usr/bin/env python3
"""Finalize V6-fed campaign results with the frozen V4 finalizer."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v6 as v6_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v5 as adapter_v5,
)


implementation_v4 = adapter_v5.implementation_v4
V6_CAMPAIGN_RUNNER = Path(__file__).resolve().with_name(
    "supplier_operating_point_full_campaign_v6.py"
)
V6FinalizerAdapterError = adapter_v5.V5FinalizerAdapterError
EXPECTED_V5_ADAPTER_SHA256 = (
    "2bbfd696b0654f5837da0a51d0022ec1cf4cc9b9eaf98dfd6207a95603898c82"
)


def validate_frozen_implementation() -> Path:
    adapter_path = Path(adapter_v5.__file__).resolve()
    if adapter_v5._sha256_file(adapter_path) != EXPECTED_V5_ADAPTER_SHA256:  # noqa: SLF001
        raise V6FinalizerAdapterError("Frozen V5 finalizer adapter changed")
    path = adapter_v5.validate_frozen_implementation()
    if not V6_CAMPAIGN_RUNNER.is_file():
        raise V6FinalizerAdapterError(
            f"Missing V6 campaign runner: {V6_CAMPAIGN_RUNNER}"
        )
    return path


@contextmanager
def patched_v6_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_hash: Any = implementation_v4.SOURCE_RUNNER_SHA256
    implementation_v4.v4_bridge = v6_bridge
    implementation_v4.SOURCE_RUNNER_SHA256 = adapter_v5._sha256_file(  # noqa: SLF001
        V6_CAMPAIGN_RUNNER
    )
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.SOURCE_RUNNER_SHA256 = previous_hash


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v6_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
