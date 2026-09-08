from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as bridge_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7 as adapter_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v8 as subject,
)


V7_BRIDGE = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\validated_operating_points_v7_20260905_v1.json"
)

EXPECTED_START_BY_ITEM = {
    "item:099439": 271,
    "item:730384": 482,
    "item:016332": 253,
    "item:001848": 215,
    "item:029313": 202,
    "item:708073": 482,
    "item:038005": 391,
    "item:049371": 204,
    "item:333362": 278,
    "item:338928": 213,
    "item:001893": 500,
    "item:055703": 232,
    "item:338929": 214,
    "item:042342": 528,
    "item:001757": 216,
    "item:426331": 208,
    "item:344135": 310,
    "item:734545": 520,
}


def _walk_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [
            key for child in value.values() for key in _walk_keys(child)
        ]
    if isinstance(value, list):
        return [key for child in value for key in _walk_keys(child)]
    return []


@pytest.fixture(scope="module")
def real_registry() -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    if not V7_BRIDGE.is_file():
        pytest.skip("Local signed V7 campaign traces are unavailable")
    with subject.patched_v8_context():
        impl = subject.implementation_v4
        # Source validation is performed once below by the native V7 validator.
        points = impl.load_operating_points(V7_BRIDGE, require_prevalidated=False)
        lanes = impl.load_lanes(impl.DEFAULT_LANE_REFERENCE)
        bridge = bridge_v7.validate_bridge(V7_BRIDGE, revalidate_source=True)
        traces = impl._import_v4_holdout_shipment_rows(  # noqa: SLF001
            bridge_path=V7_BRIDGE,
            bridge=bridge,
            points=points,
            lanes=lanes,
        )
        manifest = {
            "campaign_signature": "a" * 64,
            "engine_sha256": bridge["source_hashes"]["engine_sha256"],
            "operating_points_artifact_signature": bridge["artifact_signature"],
            "operating_points_trace_index_signature": bridge[
                "trace_index_signature"
            ],
        }
        registry = subject.build_cross_state_target_registry(
            manifest=manifest,
            points=points,
            lanes=lanes,
            shipment_rows_by_state_seed=traces,
        )
        return registry, manifest, lanes


def test_v8_context_patches_and_restores_target_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    impl = subject.implementation_v4
    monkeypatch.setattr(subject, "validate_frozen_implementation", lambda: Path())
    monkeypatch.setattr(adapter_v7, "validate_frozen_implementation", lambda: Path())
    before = (
        impl.__file__,
        impl._design_payload,  # noqa: SLF001
        impl._build_v4_state_validation_binding,  # noqa: SLF001
        impl.build_cross_state_target_registry,
        impl.run_target_discovery,
        impl.load_target_registry,
        impl.parse_args,
    )
    with subject.patched_v8_context():
        assert Path(impl.__file__).resolve() == subject.ADAPTER_PATH
        assert impl._design_payload is subject._build_v8_design_payload  # noqa: SLF001
        assert (  # noqa: SLF001
            impl._build_v4_state_validation_binding
            is subject._build_v8_state_validation_binding
        )
        assert impl.build_cross_state_target_registry is subject.build_cross_state_target_registry
        assert impl.run_target_discovery is subject.run_target_discovery
        assert impl.load_target_registry is subject.load_target_registry
        assert impl.parse_args is subject._parse_v8_args  # noqa: SLF001
    assert (
        impl.__file__,
        impl._design_payload,  # noqa: SLF001
        impl._build_v4_state_validation_binding,  # noqa: SLF001
        impl.build_cross_state_target_registry,
        impl.run_target_discovery,
        impl.load_target_registry,
        impl.parse_args,
    ) == before


def test_v8_help_describes_trace_only_selection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        subject._parse_v8_args(["--help"])  # noqa: SLF001
    help_text = capsys.readouterr().out
    assert "V8" in help_text
    assert "changes only how the 42-day supplier-incident window" in help_text
    assert "Target selection runs no simulation" in help_text
    assert "design seed" not in help_text.lower()


def test_v8_design_payload_keeps_source_cohorts_but_replaces_target_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_cohorts = {
        "campaign_repetitions_reuse_v4_fresh_holdout": list(
            subject.CAMPAIGN_SEEDS
        ),
        "incident_window_design_reserved": [900659036],
    }
    monkeypatch.setattr(
        adapter_v7,
        "_build_v7_design_payload",
        lambda *args, **kwargs: {
            "expected_counts": {
                "auxiliary_discovery_runs": 3,
                "design_window_engine_runs": 3,
            },
            "operating_points_cohorts": source_cohorts,
            "operating_point_preflight_contract": {
                "design_seed": 900659036,
                "design_seed_excluded": 900659036,
            },
            "target_discovery_contract": {"minimum_comparable_campaign_seeds": 24},
            "target_selection": {"selection_rule": "legacy"},
        },
    )
    payload = subject._build_v8_design_payload()  # noqa: SLF001
    assert payload["operating_points_cohorts"] == source_cohorts
    assert payload["v8_target_selection_cohort"] == {
        "campaign_baselines_used_for_exposure_stratification": list(
            subject.CAMPAIGN_SEEDS
        ),
        "source_trace_count": 90,
        "reserved_target_design_cohort_used": False,
        "incident_outcomes_used": False,
    }
    assert payload["target_selection_engine_runs"] == 0
    assert payload["expected_counts"]["target_selection_engine_runs"] == 0
    assert payload["target_discovery_contract"][
        "required_comparable_seed_count"
    ] == 30
    assert payload["target_discovery_contract"]["candidate_start_day_min"] == 180
    assert payload["target_discovery_contract"]["candidate_start_day_max"] == 678
    assert "design_seed" not in payload["target_discovery_contract"]
    assert "design_seed" not in payload["operating_point_preflight_contract"]


def test_target_selection_rejects_incident_or_outcome_fields() -> None:
    impl = subject.implementation_v4
    matrix = {
        (point_id, seed): []
        for point_id in impl.OPERATING_POINT_IDS
        for seed in subject.CAMPAIGN_SEEDS
    }
    key = next(iter(matrix))
    baseline_row = {
        field: "" for field in subject.BASELINE_SELECTION_TRACE_FIELDS
    }
    matrix[key] = [{**baseline_row, "service_loss_pp": 1.0}]
    with pytest.raises(ValueError, match="forbidden"):
        subject._assert_baseline_only_trace_matrix(matrix)  # noqa: SLF001
    matrix[key] = [{**baseline_row, "risk_event_ids": "incident-1"}]
    with pytest.raises(ValueError, match="baseline shipment traces only"):
        subject._assert_baseline_only_trace_matrix(matrix)  # noqa: SLF001


def test_real_signed_traces_produce_exact_18_earliest_windows_and_1620_cells(
    real_registry: tuple[dict[str, Any], dict[str, Any], list[Any]],
) -> None:
    registry, _manifest, _lanes = real_registry
    starts = {
        row["item_id"]: row["fixed_window_start_day"]
        for row in registry["lane_contracts"]
    }
    assert starts == EXPECTED_START_BY_ITEM
    assert registry["campaign_exposure_gate_passed"] is True
    assert registry["target_selection_engine_runs"] == 0
    assert registry["incident_outcomes_used"] is False
    assert len(registry["targets"]) == 1_620
    assert len(registry["state_exposure_descriptive"]) == 1_620
    assert all(
        row["comparable_campaign_seed_count"] == 30
        and row["required_comparable_seed_count"] == 30
        and row["fixed_window_start_day"] == row["eligible_window_start_days"][0]
        for row in registry["lane_contracts"]
    )
    assert "design_seed" not in _walk_keys(registry)


def test_registry_distinguishes_shipped_gate_from_pulled_description(
    real_registry: tuple[dict[str, Any], dict[str, Any], list[Any]],
) -> None:
    registry, _manifest, _lanes = real_registry
    assert registry["exposure_quantity_field"] == "shipped_qty"
    for row in registry["targets"]:
        assert row["cross_state_quantity_basis"] == "shipped_qty"
        assert row["cross_state_shipped_quantity_ratio"] <= 1.5 + 1e-12
        assert "cross_state_pulled_quantity_ratio_descriptive" in row


def test_public_validator_rejects_signed_and_resigned_tampering(
    real_registry: tuple[dict[str, Any], dict[str, Any], list[Any]],
) -> None:
    registry, manifest, lanes = real_registry
    subject.validate_v8_target_registry_payload(
        registry,
        manifest=manifest,
        lanes=lanes,
    )
    changed = copy.deepcopy(registry)
    changed["targets"][0]["target_expected_delivered_qty"] += 1.0
    with pytest.raises(ValueError, match="signature"):
        subject.validate_v8_target_registry_payload(
            changed,
            manifest=manifest,
            lanes=lanes,
        )
    unsigned = dict(changed)
    unsigned.pop("registry_signature")
    changed["registry_signature"] = subject.implementation_v4._stable_sha256(  # noqa: SLF001
        unsigned
    )
    with pytest.raises(ValueError, match="target cell is inconsistent"):
        subject.validate_v8_target_registry_payload(
            changed,
            manifest=manifest,
            lanes=lanes,
        )


def test_incident_mechanisms_remain_two_supplier_stresses_without_quality() -> None:
    mechanisms = subject.implementation_v4._mechanism_contract()  # noqa: SLF001
    assert {row["key"] for row in mechanisms} == {
        "transport_delay",
        "planned_delivery_shortfall",
    }
    assert not (
        {row["risk_type"] for row in mechanisms}
        & subject.implementation_v4.FORBIDDEN_INCIDENT_RISK_TYPES
    )
