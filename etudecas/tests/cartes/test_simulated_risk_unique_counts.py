"""Pure in-memory oracles for repeated native risk identifiers.

No files, timestamps, native simulation, plotting process or integrity probe.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from etudecas.visualization.maps import supplier_risk_panels as panels


def _events() -> list[dict]:
    return [
        {
            "event_id": "state_stock_S1_A_d1",
            "supplier_id": "S-1",
            "item_id": "item:A",
            "source": "state_dependent_supplier_risk",
            "risk_family": "stock",
            "risk_type": "availability",
            "multiplier": 0.85,
            "trigger_day": 1,
            "start_day": 2,
            "end_day": 15,
            "trigger_metric": "stock_cover_below_3d",
            "trigger_value": 1.0,
            "threshold": 3.0,
            "consecutive_days": 2,
        },
        {
            "event_id": "state_capacity_S1_B_d8",
            "supplier_id": "S-1",
            "item_id": "item:B",
            "source": "state_dependent_supplier_risk",
            "risk_family": "capacity",
            "risk_type": "capacity",
            "multiplier": 0.90,
            "trigger_day": 8,
            "start_day": 9,
            "end_day": 22,
            "trigger_metric": "capacity_utilization_above_85pct",
            "trigger_value": 0.95,
            "threshold": 0.85,
            "consecutive_days": 3,
        },
    ]


def test_configured_family_and_source_counts_use_unique_nonempty_native_ids() -> None:
    events = _events()
    configured = events + deepcopy(events) + [{"event_id": "", "risk_type": "stock"}]
    before = deepcopy(configured)
    result = panels.build_simulated_supplier_risk_metrics(
        configured_by_node={"S-1": configured}, applied_by_node={}
    )

    # Manual oracle: two real IDs, one in each family, both state-generated.
    for scope in [result["global"], result["nodes"]["S-1"]]:
        assert scope["configured_event_count"] == 2
        assert scope["configured_source_counts"] == {"state": 2}
        assert scope["configured_family_counts"] == {"capacity": 1, "stock": 1}
        assert scope["applied_event_count"] == 0
    assert result["global"]["node_count"] == 1
    assert configured == before


def test_diagnostic_keeps_two_roots_when_summary_repeats_native_state_csv() -> None:
    events = _events()
    summary = {
        "production_tracking": {
            "supplier_risk_events": deepcopy(events) + [{"event_id": ""}]
        }
    }
    raw = {
        "nodes": [{"id": "S-1", "type": "supplier_dc"}],
        "edges": [],
        "items": [{"id": "item:A", "code": "A"}, {"id": "item:B", "code": "B"}],
    }
    before = deepcopy((summary, events, raw))

    def csv_rows(path: Path) -> list[dict]:
        return deepcopy(events) if path.name == "supplier_state_dependent_risk_events.csv" else []

    with patch.object(panels, "load_json_dict", return_value=summary), patch.object(
        panels, "read_csv_rows", side_effect=csv_rows
    ):
        result = panels.build_simulated_risk_global_diagnostic_payload(
            raw=raw,
            output_root=Path("unused-in-memory-root"),
            simulated_risk_metrics={},
        )

    # Summary and CSV describe the same two signals, not four independent events.
    assert result["summary"]["configured_event_count"] == 2
    assert result["summary"]["cascade_signal_count"] == 2
    assert len(result["events"]) == 2
    assert {row["event_id"] for row in result["events"]} == {
        "state_stock_S1_A_d1", "state_capacity_S1_B_d8"
    }
    assert len(result["cascade_roots"]) == 2
    assert result["summary"]["applied_event_count"] == 0
    assert (summary, events, raw) == before
