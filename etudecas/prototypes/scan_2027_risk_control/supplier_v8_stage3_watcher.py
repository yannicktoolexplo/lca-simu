#!/usr/bin/env python3
"""Arm the detached fail-closed watcher for corrected V8 Stage2 V3."""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_watcher as implementation,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_pipeline as pipeline,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage3_watcher.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservation.v1"
RECEIPT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.ready.v1"
MODULE_NAME = "etudecas.prototypes.scan_2027_risk_control.supplier_v8_stage3_watcher"
DEFAULT_POLL_SECONDS = 60.0
DEFAULT_MAX_WAIT_HOURS = implementation.DEFAULT_MAX_WAIT_HOURS
DEFAULT_STARTUP_TIMEOUT_SECONDS = implementation.DEFAULT_STARTUP_TIMEOUT_SECONDS

Stage2WatcherError = implementation.Stage2WatcherError
Stage2WatcherTimeout = implementation.Stage2WatcherTimeout
KeepAwake = implementation.KeepAwake


@contextmanager
def patched_v3_watcher_context() -> Iterator[None]:
    """Make the mature detached protocol start only the V3 module and outputs."""

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_delivery as legacy_delivery,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage3_delivery as delivery_v3,
    )

    previous_common = implementation.common
    previous_pipeline = implementation.pipeline
    previous_doc = implementation.__doc__
    previous_schema = implementation.SCHEMA_VERSION
    previous_reservation_schema = implementation.RESERVATION_SCHEMA_VERSION
    previous_receipt_schema = implementation.RECEIPT_SCHEMA_VERSION
    previous_module = implementation.MODULE_NAME
    previous_poll_seconds = implementation.DEFAULT_POLL_SECONDS
    previous_delivery_validator: Any = legacy_delivery.validate_delivery
    implementation.common = common
    implementation.pipeline = pipeline
    implementation.__doc__ = __doc__
    implementation.SCHEMA_VERSION = SCHEMA_VERSION
    implementation.RESERVATION_SCHEMA_VERSION = RESERVATION_SCHEMA_VERSION
    implementation.RECEIPT_SCHEMA_VERSION = RECEIPT_SCHEMA_VERSION
    implementation.MODULE_NAME = MODULE_NAME
    implementation.DEFAULT_POLL_SECONDS = DEFAULT_POLL_SECONDS
    legacy_delivery.validate_delivery = delivery_v3.validate_delivery
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
        implementation.DEFAULT_POLL_SECONDS = previous_poll_seconds


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v3_watcher_context():
        # Do not turn the Stage2 helper into a concurrent reader of the campaign
        # writer on Windows.  The final V8 overlay can only exist after campaign
        # completion and finalization; until then we exit without opening any
        # launch/shard progress JSON.  A Windows scheduled task may retry later.
        args = implementation._parser().parse_args(argv)  # noqa: SLF001
        paths = pipeline.paths_from_args(args)
        release_marker = paths.results_dir / finalizer_v8.V8_RESULT_OVERLAY_NAME
        if not release_marker.is_file():
            print(
                "ÉTAPE 2 V3 EN ATTENTE : la surcouche finale V8 est absente; "
                "aucun fichier de progression de campagne n'a été ouvert.",
                file=sys.stderr,
            )
            return 4
        return int(implementation.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
