from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v4 as subject,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as contract,
)


def test_bridge_rejects_test_only_v4_before_reading_any_holdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = Path(subject.refinement_v4.__file__).resolve()
    plan = SimpleNamespace(
        manifest={
            "source_hashes": {"v4_driver_sha256": contract.sha256_file(driver)}
        }
    )
    monkeypatch.setattr(subject.refinement_v4, "validate_plan", lambda _path: plan)
    monkeypatch.setattr(
        subject.refinement_v4,
        "_registered_execution_mode",
        lambda _plan, _run: subject.refinement_v4.TEST_ONLY_EXECUTION_MODE,
    )

    with pytest.raises(subject.V4BridgeError, match="test-only"):
        subject._load_official_source(tmp_path / "plan", tmp_path / "run")


def test_bridge_contract_requires_exactly_ninety_official_trace_entries() -> None:
    assert len(contract.CAMPAIGN_SEEDS) == 30
    assert len(contract.OPERATING_POINT_IDS) * len(contract.CAMPAIGN_SEEDS) == 90
    assert subject.INTERPRETATION.startswith("Simulation hypotheses only")
    assert "artifact_signature" in subject.BRIDGE_FIELDS
    assert "shipment_trace" in subject.TRACE_INDEX_FIELDS

