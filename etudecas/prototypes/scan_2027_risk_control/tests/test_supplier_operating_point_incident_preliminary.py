from __future__ import annotations

import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    merge_supplier_operating_point_shards as merger,
)

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_incident_preliminary as subject,
)


def _priority_row(
    *, chain: str, point: str, loss: float, exercised: bool = True
) -> dict[str, object]:
    return {
        "operating_point_id": point,
        "chain_id": chain,
        "incident_mechanism": "transport_delay",
        "seed": 340281,
        "supplier_id": f"supplier-{chain}",
        "item_id": chain,
        "factory_id": "M-1810",
        "product_id": "268091",
        "global_service_loss_pp": loss,
        "service_loss_pp": loss,
        "backlog_qty_days_delta": loss * 10,
        "production_delta": -loss,
        "incident_physically_exercised": exercised,
    }


def test_compact_schema_contains_global_and_physical_evidence() -> None:
    required = {
        "chain_id",
        "baseline_global_service",
        "incident_global_service",
        "global_service_loss_pp",
        "risk_applied_row_count",
        "risk_applied_event_count",
        "incident_physically_exercised",
    }
    assert required <= set(subject.DETAIL_FIELDS)


def test_priority_excludes_non_exercised_incident(tmp_path) -> None:
    rows = [
        _priority_row(chain="real", point="op_93", loss=2.0),
        _priority_row(chain="not-exercised", point="op_93", loss=99.0, exercised=False),
        _priority_row(chain="real", point="op_80", loss=3.0),
    ]
    payload = subject._priority_outputs(rows, tmp_path)
    selected = payload["selected_cases"]
    assert selected
    assert {row["chain_id"] for row in selected} == {"real"}
    assert payload["opaque_composite_score_used"] is False


def test_availability_is_exercised_when_applied_before_shipment() -> None:
    incident = {"incident_mechanism": "supply_availability"}
    metrics = {
        "risk_applied_row_count": 179,
        "risk_applied_event_count": 1,
        # Legacy cached evidence required a positive shipment and therefore
        # recorded False even when the restriction prevented every shipment.
        "incident_physically_exercised": False,
    }

    assert subject._physical_exercise_from_evidence(incident, metrics)
    metrics["risk_applied_row_count"] = 0
    assert not subject._physical_exercise_from_evidence(incident, metrics)
    metrics["risk_applied_row_count"] = 179
    incident["incident_mechanism"] = "transport_delay"
    assert not subject._physical_exercise_from_evidence(incident, metrics)


def test_priority_confirms_union_chain_at_both_degraded_points(tmp_path) -> None:
    rows = [
        _priority_row(chain="only-at-93", point="op_93", loss=8.0),
        _priority_row(chain="both", point="op_93", loss=4.0),
        _priority_row(chain="both", point="op_80", loss=3.0),
        _priority_row(chain="only-at-80", point="op_80", loss=7.0),
    ]

    payload = subject._priority_outputs(rows, tmp_path)
    selected = {
        (row["chain_id"], row["operating_point_id"]): row
        for row in payload["selected_cases"]
    }

    assert set(selected) == {
        ("only-at-93", "op_93"),
        ("only-at-93", "op_80"),
        ("both", "op_93"),
        ("both", "op_80"),
        ("only-at-80", "op_93"),
        ("only-at-80", "op_80"),
    }
    assert selected[("only-at-93", "op_80")]["confirmation_cause_fallback"]
    assert selected[("only-at-80", "op_93")]["confirmation_cause_fallback"]
    assert not selected[("both", "op_93")]["confirmation_cause_fallback"]


def test_risk_note_does_not_reintroduce_excluded_business_branch() -> None:
    point = {"operating_point_id": "op_93"}
    incident = {
        "scenario_id": "lane__transport_delay__120",
        "risk_type": "lead_time_extra_days",
        "supplier_id": "S1",
        "item_id": "338929",
        "factory_id": "M-1810",
        "start_day": 10,
        "end_day": 20,
        "incident_value": 120.0,
    }
    row = subject._risk_row(point, incident)
    assert row["risk_type"] == "lead_time_extra_days"
    assert "qualit" not in str(row["notes"]).casefold()


def _merge_write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

def _merge_fixture(base, profile):
    points = merger.PROFILES[profile].point_ids
    inputs = [base / "source_a", base / "source_b"]
    rows_by_shard = [[], []]
    for point in points:
        operating_point = {
            "operating_point_id": point,
            "operating_point_label": point,
            "degradation_family": "supplier_planned_lead",
            "degradation_value": 1,
        }
        metrics = {
            "seed": merger.protocol.SCREENING_SEED,
            "warmup_core_state_sha256": "paired-j0",
            "system_on_due_service": 0.9,
            "on_due_service_268091": 0.9,
            "on_due_service_268967": 0.9,
            "backlog_qty_days_268091": 100,
            "released_qty_268091": 1000,
            "risk_applied_row_count": 1,
            "risk_applied_event_count": 1,
            "incident_physically_exercised": True,
        }
        baseline = {"operating_point": operating_point, "incident": None, "metrics": metrics}
        for path in inputs:
            _merge_write_json(path / "case_evidence" / f"{point}_baseline.json", baseline)
        for index in range(18):
            for mechanism in subject.MECHANISMS:
                incident = {
                    "chain_id": f"chain_{index:02d}",
                    "product_id": "268091",
                    "supplier_id": f"supplier_{index:02d}",
                    "item_id": str(index),
                    "factory_id": "M-1810",
                    "incident_mechanism": mechanism,
                    "incident_value": 0.5,
                }
                evidence = {
                    "operating_point": operating_point,
                    "incident": incident,
                    "metrics": {**metrics, "on_due_service_268091": 0.7, "system_on_due_service": 0.8},
                }
                row = subject._detail_row(baseline, evidence)
                rows_by_shard[index % 2].append(row)
                _merge_write_json(
                    inputs[index % 2] / "case_evidence" / f"{point}_{index}_{mechanism}.json",
                    evidence,
                )
    # An identical duplicate is allowed and must not count twice.
    rows_by_shard[1].append(rows_by_shard[0][0])
    for path, rows in zip(inputs, rows_by_shard):
        subject._write_csv(path / merger.PROFILES[profile].detail_file, rows, subject.DETAIL_FIELDS)
    return inputs


@pytest.mark.parametrize("profile, expected_rows, expected_proofs", [("healthy", 36, 37), ("degraded", 72, 74)])
def test_merge_profiles_rebuild_exact_complete_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    profile: str, expected_rows: int, expected_proofs: int,
) -> None:
    engine = tmp_path / "fixture_engine.py"
    engine.write_text("# synthetic engine identity\n", encoding="utf-8")
    monkeypatch.setattr(merger.protocol, "DEFAULT_ENGINE", engine)
    inputs = _merge_fixture(tmp_path, profile)
    output = tmp_path / "merged"
    merger.merge(inputs=inputs, output=output, profile=profile)
    manifest = json.loads((output / "merge_manifest.json").read_text(encoding="utf-8"))
    rows = subject._read_csv(output / merger.PROFILES[profile].detail_file)
    assert manifest["row_count"] == len(rows) == expected_rows
    assert manifest["atomic_case_evidence_count"] == expected_proofs
    assert manifest["duplicate_identical_row_count"] == 1
    assert manifest["rows_rebuilt_from_atomic_evidence"] is True
    assert {row["operating_point_id"] for row in rows} == set(merger.PROFILES[profile].point_ids)
    assert {row["engine_sha256"] for row in rows} == {merger.protocol.sha256_file(engine)}
    assert all(float(row["service_loss_pp"]) == pytest.approx(20.0) for row in rows)
    assert all(float(row["global_service_loss_pp"]) == pytest.approx(10.0) for row in rows)
    assert len(list((output / "case_evidence").glob("*.json"))) == expected_proofs


@pytest.mark.parametrize("profile", ["healthy", "degraded"])
@pytest.mark.parametrize("case, error", [
    ("divergent_duplicate", "Divergent duplicate"),
    ("missing_evidence", "Missing atomic evidence"),
    ("wrong_engine", "Expected 36|coverage is incomplete"),
    ("different_j0", "same J0 state"),
])
def test_merge_profiles_refuse_invalid_or_incomplete_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, case: str, error: str,
) -> None:
    engine = tmp_path / "fixture_engine.py"
    engine.write_text("# synthetic engine identity\n", encoding="utf-8")
    monkeypatch.setattr(merger.protocol, "DEFAULT_ENGINE", engine)
    inputs = _merge_fixture(tmp_path, profile)
    first_incident = sorted((inputs[0] / "case_evidence").glob("*0_supply_availability.json"))[0]
    if case in {"divergent_duplicate", "wrong_engine"}:
        path = inputs[1] / merger.PROFILES[profile].detail_file
        rows = subject._read_csv(path)
        if case == "divergent_duplicate":
            rows[-1]["service_loss_pp"] = "999"
        else:
            for row in rows:
                row["engine_sha256"] = "obsolete"
        subject._write_csv(path, rows, subject.DETAIL_FIELDS)
    elif case == "missing_evidence":
        first_incident.unlink()
    else:
        evidence = json.loads(first_incident.read_text(encoding="utf-8"))
        evidence["metrics"]["warmup_core_state_sha256"] = "different-j0"
        _merge_write_json(first_incident, evidence)
    with pytest.raises(ValueError, match=error):
        merger.merge(inputs=inputs, output=tmp_path / "merged", profile=profile)
    assert not (tmp_path / "merged").exists()
