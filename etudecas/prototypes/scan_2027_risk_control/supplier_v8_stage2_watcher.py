#!/usr/bin/env python3
"""Arm the detached, fail-closed watcher for the additive V8 delivery stage."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_watcher as implementation,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_pipeline as pipeline,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage2_watcher.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservation.v1"
RECEIPT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.ready.v1"
MODULE_NAME = "etudecas.prototypes.scan_2027_risk_control.supplier_v8_stage2_watcher"
DEFAULT_POLL_SECONDS = implementation.DEFAULT_POLL_SECONDS
DEFAULT_MAX_WAIT_HOURS = implementation.DEFAULT_MAX_WAIT_HOURS
DEFAULT_STARTUP_TIMEOUT_SECONDS = implementation.DEFAULT_STARTUP_TIMEOUT_SECONDS

Stage2WatcherError = implementation.Stage2WatcherError
Stage2WatcherTimeout = implementation.Stage2WatcherTimeout
KeepAwake = implementation.KeepAwake


@contextmanager
def patched_v8_watcher_context() -> Iterator[None]:
    """Make the mature detached-process protocol start the V8 module and pipeline."""

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_delivery as legacy_delivery,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_delivery as delivery_v8,
    )

    previous_common = implementation.common
    previous_pipeline = implementation.pipeline
    previous_doc = implementation.__doc__
    previous_schema = implementation.SCHEMA_VERSION
    previous_reservation_schema = implementation.RESERVATION_SCHEMA_VERSION
    previous_receipt_schema = implementation.RECEIPT_SCHEMA_VERSION
    previous_module = implementation.MODULE_NAME
    previous_delivery_validator: Any = legacy_delivery.validate_delivery
    implementation.common = common
    implementation.pipeline = pipeline
    implementation.__doc__ = __doc__
    implementation.SCHEMA_VERSION = SCHEMA_VERSION
    implementation.RESERVATION_SCHEMA_VERSION = RESERVATION_SCHEMA_VERSION
    implementation.RECEIPT_SCHEMA_VERSION = RECEIPT_SCHEMA_VERSION
    implementation.MODULE_NAME = MODULE_NAME
    # The mature watcher imports the legacy delivery locally only for the
    # already-complete fast path.  Redirect that one callable while patched.
    legacy_delivery.validate_delivery = delivery_v8.validate_delivery
    try:
        yield
    finally:
        legacy_delivery.validate_delivery = previous_delivery_validator
        implementation.common = previous_common
        implementation.pipeline = previous_pipeline
        implementation.__doc__ = previous_doc
        implementation.SCHEMA_VERSION = previous_schema
        implementation.RESERVATION_SCHEMA_VERSION = previous_reservation_schema
        implementation.RECEIPT_SCHEMA_VERSION = previous_receipt_schema
        implementation.MODULE_NAME = previous_module


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v8_watcher_context():
        return int(implementation.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
