from __future__ import annotations

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
