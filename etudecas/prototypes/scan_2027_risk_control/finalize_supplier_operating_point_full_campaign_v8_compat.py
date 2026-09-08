#!/usr/bin/env python3
"""Finalize native V8 evidence through a validation-only compatibility view.

The signed V8 case rows intentionally leave three legacy V4 comparability
columns empty.  Their authoritative values live in the signed V8 target
registry.  The frozen V4 validator parses those columns before checking the
registry, so this additive adapter projects the signed values onto a deep copy
used only during validation.  It never rewrites campaign metrics or evidence.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as frozen_v8,
)


implementation_v4 = frozen_v8.implementation_v4
V8FinalizerCompatibilityError = frozen_v8.V8FinalizerAdapterError
FROZEN_V8_FINALIZER = Path(frozen_v8.__file__).resolve()
EXPECTED_FROZEN_V8_FINALIZER_SHA256 = (
    "a3cc635a8adc30522ecf2dbbb066bd81a3c4ac9bedf0a1d4552a14ec65f7c7ec"
)
EXPECTED_TARGET_COUNT = frozen_v8.EXPECTED_TARGET_COUNT
REQUIRED_COMPARABLE_SEED_COUNT = frozen_v8.REQUIRED_COMPARABLE_SEED_COUNT
COMPARABILITY_FIELDS = (
    "required_comparable_seed_count",
    "comparable_campaign_seed_count",
    "seed_cross_state_exposure_comparable",
)


def validate_frozen_implementation() -> Path:
    digest = implementation_v4._sha256(FROZEN_V8_FINALIZER)  # noqa: SLF001
    if digest != EXPECTED_FROZEN_V8_FINALIZER_SHA256:
        raise V8FinalizerCompatibilityError(
            f"Frozen V8 finalizer changed: {digest}"
        )
    frozen_v8.validate_frozen_implementation()
    return FROZEN_V8_FINALIZER


def v8_validation_frame(frame: Any, context: Any) -> Any:
    """Populate signed comparability fields on a disposable deep copy."""

    missing_columns = [field for field in COMPARABILITY_FIELDS if field not in frame]
    if "stage" not in frame or missing_columns:
        missing = (["stage"] if "stage" not in frame else []) + missing_columns
        raise V8FinalizerCompatibilityError(
            "V8 metrics lack validation compatibility columns: "
            + ", ".join(missing)
        )

    registry = context.registry
    targets = registry.get("targets") if isinstance(registry, Mapping) else None
    required_seed_count = (
        registry.get("required_comparable_seed_count")
        if isinstance(registry, Mapping)
        else None
    )
    if (
        not isinstance(targets, list)
        or len(targets) != EXPECTED_TARGET_COUNT
        or required_seed_count != REQUIRED_COMPARABLE_SEED_COUNT
    ):
        raise V8FinalizerCompatibilityError(
            "Signed V8 registry cannot supply validation compatibility fields"
        )

    registry_by_key: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for target in targets:
        if not isinstance(target, Mapping):
            raise V8FinalizerCompatibilityError(
                "Signed V8 registry contains a non-object cell"
            )
        try:
            key = (
                str(target["operating_point_id"]),
                int(target["seed"]),
                str(target["lane_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise V8FinalizerCompatibilityError(
                "Signed V8 registry contains an incomplete cell identity"
            ) from exc
        if key in registry_by_key:
            raise V8FinalizerCompatibilityError(
                f"Signed V8 registry contains a duplicate cell: {key!r}"
            )
        registry_by_key[key] = target

    projected = frame.copy(deep=True)
    for field in COMPARABILITY_FIELDS:
        projected[field] = projected[field].astype(object)
    incident_mask = (
        projected["stage"].astype(str).str.strip().str.casefold() == "incident"
    )

    def is_blank(value: Any) -> bool:
        return value is None or str(value).strip() in {"", "nan", "None"}

    for index, row in projected.loc[incident_mask].iterrows():
        try:
            key = (
                str(row["operating_point_id"]),
                int(float(row["seed"])),
                str(row["lane_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise V8FinalizerCompatibilityError(
                "V8 incident metric contains an incomplete cell identity"
            ) from exc
        target = registry_by_key.get(key)
        if target is None:
            raise V8FinalizerCompatibilityError(
                f"V8 incident metric has no signed target cell: {key!r}"
            )
        expected = {
            "required_comparable_seed_count": target.get(
                "required_comparable_seed_count"
            ),
            "comparable_campaign_seed_count": target.get(
                "comparable_campaign_seed_count"
            ),
            "seed_cross_state_exposure_comparable": target.get(
                "seed_cross_state_exposure_comparable"
            ),
        }
        if (
            expected["required_comparable_seed_count"] != required_seed_count
            or expected["comparable_campaign_seed_count"] != required_seed_count
            or expected["seed_cross_state_exposure_comparable"] is not True
        ):
            raise V8FinalizerCompatibilityError(
                f"Signed V8 comparability contract differs for cell {key!r}"
            )
        for field, expected_value in expected.items():
            actual = row[field]
            if not is_blank(actual):
                if field == "seed_cross_state_exposure_comparable":
                    matches = (
                        implementation_v4._truthy(actual) is bool(expected_value)  # noqa: SLF001
                    )
                else:
                    try:
                        matches = math.isclose(
                            float(actual),
                            float(expected_value),
                            rel_tol=0.0,
                            abs_tol=implementation_v4.NUMERIC_TOLERANCE,
                        )
                    except (TypeError, ValueError):
                        matches = False
                if not matches:
                    raise V8FinalizerCompatibilityError(
                        f"V8 metric/registry mismatch: {field} for {key!r}"
                    )
            projected.at[index, field] = expected_value
    return projected


@contextmanager
def patched_metric_validation() -> Iterator[None]:
    """Temporarily adapt only the V4 validation call and restore it exactly."""

    validate_frozen_implementation()
    previous_validate_and_pair = implementation_v4.validate_and_pair

    def validate_and_pair_v8(frame: Any, context: Any) -> Any:
        return previous_validate_and_pair(v8_validation_frame(frame, context), context)

    implementation_v4.validate_and_pair = validate_and_pair_v8
    try:
        yield
    finally:
        implementation_v4.validate_and_pair = previous_validate_and_pair


def main(argv: Sequence[str] | None = None) -> int:
    try:
        with patched_metric_validation():
            return int(frozen_v8.main(argv))
    except (V8FinalizerCompatibilityError, OSError) as exc:
        print(f"CAMPAGNE V8 INVALIDE : {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
