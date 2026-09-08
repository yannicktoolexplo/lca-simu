from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8_compat as subject,
)


def _metric_row(
    *,
    stage: str,
    operating_point_id: str = "op_100",
    seed: int = 101,
    lane_id: str = "lane_01",
    required: Any = "",
    comparable: Any = "",
    cross_state: Any = "",
) -> dict[str, Any]:
    return {
        "stage": stage,
        "operating_point_id": operating_point_id,
        "seed": seed,
        "lane_id": lane_id,
        "required_comparable_seed_count": required,
        "comparable_campaign_seed_count": comparable,
        "seed_cross_state_exposure_comparable": cross_state,
    }


def _target(
    *,
    operating_point_id: str = "op_100",
    seed: int = 101,
    lane_id: str = "lane_01",
    required: int = 30,
    comparable: int = 30,
    cross_state: bool = True,
) -> dict[str, Any]:
    return {
        "operating_point_id": operating_point_id,
        "seed": seed,
        "lane_id": lane_id,
        "required_comparable_seed_count": required,
        "comparable_campaign_seed_count": comparable,
        "seed_cross_state_exposure_comparable": cross_state,
    }


def _context(targets: list[dict[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(
        registry={
            "required_comparable_seed_count": 30,
            "targets": targets,
        }
    )


def test_frozen_hash_guard_rejects_an_unexpected_finalizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject.implementation_v4, "_sha256", lambda _path: "0" * 64)

    with pytest.raises(
        subject.V8FinalizerCompatibilityError,
        match="Frozen V8 finalizer changed",
    ):
        subject.validate_frozen_implementation()


def test_projection_uses_a_deep_copy_and_leaves_baseline_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "EXPECTED_TARGET_COUNT", 1)
    baseline = _metric_row(
        stage="baseline",
        required="baseline-required",
        comparable="baseline-comparable",
        cross_state="baseline-cross-state",
    )
    incident = _metric_row(stage="incident")
    source = pd.DataFrame([baseline, incident])
    source_before = source.copy(deep=True)

    projected = subject.v8_validation_frame(source, _context([_target()]))

    assert projected is not source
    pd.testing.assert_frame_equal(source, source_before)
    assert projected.loc[0, subject.COMPARABILITY_FIELDS].to_dict() == {
        "required_comparable_seed_count": "baseline-required",
        "comparable_campaign_seed_count": "baseline-comparable",
        "seed_cross_state_exposure_comparable": "baseline-cross-state",
    }
    assert projected.loc[1, subject.COMPARABILITY_FIELDS].to_dict() == {
        "required_comparable_seed_count": 30,
        "comparable_campaign_seed_count": 30,
        "seed_cross_state_exposure_comparable": True,
    }


def test_matching_prefilled_metric_values_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "EXPECTED_TARGET_COUNT", 1)
    source = pd.DataFrame(
        [
            _metric_row(
                stage="incident",
                required="30.0",
                comparable=30,
                cross_state="oui",
            )
        ]
    )

    projected = subject.v8_validation_frame(source, _context([_target()]))

    assert projected.loc[0, subject.COMPARABILITY_FIELDS].to_dict() == {
        "required_comparable_seed_count": 30,
        "comparable_campaign_seed_count": 30,
        "seed_cross_state_exposure_comparable": True,
    }


def test_projection_rejects_a_metric_without_a_signed_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "EXPECTED_TARGET_COUNT", 1)
    source = pd.DataFrame([_metric_row(stage="incident", lane_id="unknown")])

    with pytest.raises(
        subject.V8FinalizerCompatibilityError,
        match="has no signed target cell",
    ):
        subject.v8_validation_frame(source, _context([_target()]))


def test_projection_rejects_duplicate_signed_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "EXPECTED_TARGET_COUNT", 2)
    duplicate = _target()
    source = pd.DataFrame([_metric_row(stage="incident")])

    with pytest.raises(
        subject.V8FinalizerCompatibilityError,
        match="duplicate cell",
    ):
        subject.v8_validation_frame(source, _context([duplicate, duplicate.copy()]))


def test_projection_rejects_a_metric_registry_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "EXPECTED_TARGET_COUNT", 1)
    source = pd.DataFrame(
        [_metric_row(stage="incident", required=29, comparable=30, cross_state=True)]
    )

    with pytest.raises(
        subject.V8FinalizerCompatibilityError,
        match="metric/registry mismatch: required_comparable_seed_count",
    ):
        subject.v8_validation_frame(source, _context([_target()]))


def test_patched_validation_delegates_the_projection_and_restores_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "EXPECTED_TARGET_COUNT", 1)
    monkeypatch.setattr(subject, "validate_frozen_implementation", lambda: None)
    observed: dict[str, Any] = {}
    expected_result = object()

    def original_validator(frame: pd.DataFrame, context: Any) -> object:
        observed["frame"] = frame
        observed["context"] = context
        return expected_result

    implementation = subject.implementation_v4
    monkeypatch.setattr(implementation, "validate_and_pair", original_validator)
    source = pd.DataFrame([_metric_row(stage="incident")])
    context = _context([_target()])

    with pytest.raises(RuntimeError, match="force restoration"):
        with subject.patched_metric_validation():
            patched_validator = implementation.validate_and_pair
            assert patched_validator is not original_validator
            assert patched_validator(source, context) is expected_result
            raise RuntimeError("force restoration")

    assert implementation.validate_and_pair is original_validator
    assert observed["context"] is context
    assert observed["frame"] is not source
    assert observed["frame"].loc[0, "required_comparable_seed_count"] == 30
    assert source.loc[0, "required_comparable_seed_count"] == ""


def test_main_wraps_the_frozen_finalizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Any] = []
    arguments = ["--campaign-root", "fixture"]

    @contextmanager
    def patched_validation() -> Iterator[None]:
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    def frozen_main(argv: Sequence[str] | None = None) -> int:
        events.append(("main", argv))
        return 7

    monkeypatch.setattr(subject, "patched_metric_validation", patched_validation)
    monkeypatch.setattr(subject.frozen_v8, "main", frozen_main)

    assert subject.main(arguments) == 7
    assert events == ["enter", ("main", arguments), "exit"]
