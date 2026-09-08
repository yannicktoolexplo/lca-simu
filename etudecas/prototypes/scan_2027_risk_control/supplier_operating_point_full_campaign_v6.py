#!/usr/bin/env python3
"""Run the unchanged 3,330-row incident campaign through the V6 bridge."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v6 as v6_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v5 as adapter_v5,
)


implementation_v4 = adapter_v5.implementation_v4
ADAPTER_PATH = Path(__file__).resolve()
V6CampaignAdapterError = adapter_v5.V5CampaignAdapterError
EXPECTED_V5_ADAPTER_SHA256 = (
    "302c59d76d9bf490886ba3f100075992566292b1761b71bed9fd27746e6e7b12"
)


def validate_frozen_implementation() -> Path:
    path = Path(adapter_v5.__file__).resolve()
    if adapter_v5._sha256_file(path) != EXPECTED_V5_ADAPTER_SHA256:  # noqa: SLF001
        raise V6CampaignAdapterError("Frozen V5 campaign adapter changed")
    return adapter_v5.validate_frozen_implementation()


@contextmanager
def patched_v6_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_file: Any = implementation_v4.__file__
    implementation_v4.v4_bridge = v6_bridge
    implementation_v4.__file__ = str(ADAPTER_PATH)
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.__file__ = previous_file


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v6_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
