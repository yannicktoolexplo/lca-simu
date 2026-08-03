from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_canonical_risk_events,
    load_canonical_lane_activity,
    select_top_prediction_pairs,
)
from etudecas.prototypes.scan_2027_risk_control.run_end_2026_validation import (
    _prepare_canonical_activity_selection,
)


def _graph(*lanes: tuple[str, str, str]) -> dict[str, object]:
    return {
        "edges": [
            {
                "id": f"edge:{supplier}_TO_{destination}_{item.removeprefix('item:')}",
                "from": supplier,
                "to": destination,
                "items": [item],
            }
            for supplier, item, destination in lanes
        ]
    }


def _prediction(path: Path) -> None:
    pd.DataFrame(
        {
            "snapshot_date": ["2026-06-01"] * 3,
            "supplier_id": ["SUP-INACTIVE", "SUP-ACTIVE-1", "SUP-ACTIVE-2"],
            "factory_id": ["FACTORY"] * 3,
            "item_id": ["item:I", "item:A", "item:B"],
            "predicted_incident_probability_30d": [0.8, 0.7, 0.6],
            "predicted_priority_score": [1.0, 0.9, 0.8],
        }
    ).to_csv(path, index=False)


def _physical_envelope(days: int = 30) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "scope": ["portfolio"] * days,
            "day": np.arange(days),
            "risk_upper": np.full(days, 0.8),
            "availability_multiplier_upper": np.full(days, 0.7),
            "capacity_multiplier_upper": np.full(days, 0.8),
            "lead_time_extra_days_upper": np.full(days, 4.0),
            "quality_yield_multiplier_upper": np.full(days, 0.9),
            "purchase_cost_multiplier_upper": np.full(days, 1.2),
            "transport_cost_multiplier_upper": np.full(days, 1.1),
        }
    )


def _standardized_activity() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "supplier_id": ["SUP-ACTIVE-1", "SUP-ACTIVE-2"],
            "item_id": ["item:A", "item:B"],
            "dst_node_id": ["FACTORY", "FACTORY"],
            "day": [2, 9],
            "qty": [12.0, 7.0],
            "activity_source": ["shipment", "mrp_order"],
            "activity_path": ["shipments.csv", "orders.csv"],
        }
    )


def test_activity_loader_discovers_siblings_and_matches_strict_day_semantics(
    tmp_path: Path,
) -> None:
    data = tmp_path / "run" / "data"
    data.mkdir(parents=True)
    baseline = data / "first_simulation_daily.csv"
    pd.DataFrame({"day": [0, 1]}).to_csv(baseline, index=False)
    pd.DataFrame(
        {
            "day": [2, 30, 4, 0],
            "src_node_id": [
                "SUP-SHIP",
                "SUP-OUT",
                "SUP-ZERO",
                "SUP-OPEN",
            ],
            "dst_node_id": ["FACTORY"] * 4,
            "item_id": ["item:S", "item:O", "item:Z", "item:OPEN"],
            "pulled_qty": [5.0, 99.0, 0.0, 100.0],
            "shipped_qty": [5.0, 99.0, 0.0, 100.0],
            "transport_cost_basis": [
                "lot",
                "lot",
                "lot",
                "opening_order_book",
            ],
        }
    ).to_csv(data / "production_supplier_shipments_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": [0, 3],
            "src_node_id": ["SUP-OPEN", "SUP-ORDER"],
            "dst_node_id": ["FACTORY", "FACTORY"],
            "item_id": ["item:OPEN", "item:R"],
            "order_type": ["opening_purchase_order", "planned_purchase_order"],
            "release_qty": [100.0, 7.0],
            "planned_receipt_qty": [100.0, 7.0],
        }
    ).to_csv(data / "mrp_orders_daily.csv", index=False)

    activity, metadata = load_canonical_lane_activity(
        baseline,
        horizon_days=30,
    )

    assert activity is not None
    assert metadata["evidence_status"] == "provided"
    assert metadata["horizon_end_day"] == 29
    assert metadata["row_count"] == 2
    assert metadata["lane_count"] == 2
    assert metadata["total_evidence_qty"] == 12.0
    assert metadata["excluded_opening_flow_row_count"] == 2
    assert metadata["excluded_opening_flow_lane_count"] == 1
    assert metadata["excluded_opening_flow_qty"] == 200.0
    assert metadata["excluded_opening_flow_lanes"] == [
        {
            "supplier_id": "SUP-OPEN",
            "item_id": "item:OPEN",
            "dst_node_id": "FACTORY",
            "excluded_opening_flow_qty": 200.0,
            "excluded_opening_flow_row_count": 2,
            "excluded_opening_flow_first_day": 0,
            "excluded_opening_flow_last_day": 0,
        }
    ]
    assert set(activity["supplier_id"]) == {"SUP-SHIP", "SUP-ORDER"}
    assert set(activity["activity_source"]) == {"shipment", "mrp_order"}
    assert all(Path(path).is_absolute() for path in metadata["paths_used"])


def test_opening_only_prediction_is_rejected_and_refilled(
    tmp_path: Path,
) -> None:
    data = tmp_path / "baseline" / "data"
    data.mkdir(parents=True)
    baseline = data / "first_simulation_daily.csv"
    pd.DataFrame({"day": np.arange(30)}).to_csv(baseline, index=False)
    pd.DataFrame(
        {
            "day": [0, 0, 8],
            "src_node_id": [
                "SUP-INACTIVE",
                "SUP-ACTIVE-1",
                "SUP-ACTIVE-2",
            ],
            "dst_node_id": ["FACTORY"] * 3,
            "item_id": ["item:I", "item:A", "item:B"],
            "pulled_qty": [100.0, 12.0, 7.0],
            "shipped_qty": [100.0, 12.0, 7.0],
            "transport_cost_basis": ["opening_order_book", "lot", "unit"],
        }
    ).to_csv(data / "production_supplier_shipments_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": [0, 0, 8],
            "src_node_id": [
                "SUP-INACTIVE",
                "SUP-ACTIVE-1",
                "SUP-ACTIVE-2",
            ],
            "dst_node_id": ["FACTORY"] * 3,
            "item_id": ["item:I", "item:A", "item:B"],
            "order_type": [
                "opening_purchase_order",
                "lane_release",
                "lane_release",
            ],
            "release_qty": [100.0, 12.0, 7.0],
            "planned_receipt_qty": [100.0, 12.0, 7.0],
        }
    ).to_csv(data / "mrp_orders_daily.csv", index=False)
    prediction_path = tmp_path / "prediction.csv"
    _prediction(prediction_path)
    graph = _graph(
        ("SUP-INACTIVE", "item:I", "FACTORY"),
        ("SUP-ACTIVE-1", "item:A", "FACTORY"),
        ("SUP-ACTIVE-2", "item:B", "FACTORY"),
    )

    activity, metadata = load_canonical_lane_activity(
        baseline,
        horizon_days=30,
    )
    selected = select_top_prediction_pairs(
        prediction_path,
        top_pairs=2,
        canonical_graph=graph,
        canonical_activity=activity,
        canonical_activity_metadata=metadata,
        canonical_horizon_days=30,
    )

    assert selected["supplier_id"].tolist() == [
        "SUP-ACTIVE-1",
        "SUP-ACTIVE-2",
    ]
    audit = selected.attrs["selection_audit"]
    assert audit[0]["supplier_id"] == "SUP-INACTIVE"
    assert audit[0]["canonical_activity_evidence_status"] == (
        "opening_only_flow_not_risk_addressable"
    )
    assert audit[0]["selection_status"] == "rejected_opening_only_flow"

    events, ledger = build_canonical_risk_events(
        prediction_path,
        _physical_envelope(),
        days=30,
        top_pairs=2,
        canonical_graph=graph,
        canonical_activity=activity,
        canonical_activity_metadata=metadata,
    )
    assert set(events["supplier_id"]) == {"SUP-ACTIVE-1", "SUP-ACTIVE-2"}
    opening_rejection = ledger.loc[
        ledger["selection_status"].eq("rejected_opening_only_flow")
    ].iloc[0]
    assert opening_rejection["mapping_status"] == (
        "not_applied_opening_only_flow_not_risk_addressable"
    )


def test_top_inactive_prediction_is_rejected_and_refilled_with_active_lanes(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "prediction.csv"
    _prediction(prediction_path)
    graph = _graph(
        ("SUP-INACTIVE", "item:I", "FACTORY"),
        ("SUP-ACTIVE-1", "item:A", "FACTORY"),
        ("SUP-ACTIVE-2", "item:B", "FACTORY"),
    )
    activity = _standardized_activity()
    metadata = {
        "evidence_status": "provided",
        "horizon_start_day": 0,
        "horizon_end_day": 29,
    }

    selected = select_top_prediction_pairs(
        prediction_path,
        top_pairs=2,
        canonical_graph=graph,
        canonical_activity=activity,
        canonical_activity_metadata=metadata,
        canonical_horizon_days=30,
    )

    assert selected["supplier_id"].tolist() == [
        "SUP-ACTIVE-1",
        "SUP-ACTIVE-2",
    ]
    assert set(selected["selection_status"]) == {
        "selected_graph_compatible_active_flow"
    }
    assert selected["canonical_activity_qty"].tolist() == [12.0, 7.0]
    audit = selected.attrs["selection_audit"]
    assert len(audit) == 1
    assert audit[0]["supplier_id"] == "SUP-INACTIVE"
    assert (
        audit[0]["selection_status"]
        == "rejected_no_nonzero_canonical_flow"
    )

    events, ledger = build_canonical_risk_events(
        prediction_path,
        _physical_envelope(),
        days=30,
        top_pairs=2,
        canonical_graph=graph,
        canonical_activity=activity,
        canonical_activity_metadata=metadata,
    )
    assert set(events["supplier_id"]) == {"SUP-ACTIVE-1", "SUP-ACTIVE-2"}
    rejected = ledger.loc[
        ledger["selection_status"].eq(
            "rejected_no_nonzero_canonical_flow"
        )
    ]
    assert len(rejected) == 1
    assert (
        rejected.iloc[0]["mapping_status"]
        == "not_applied_no_nonzero_canonical_flow"
    )
    selected_ledger = ledger.loc[ledger["event_id"].astype(str).str.len().gt(0)]
    assert set(selected_ledger["canonical_activity_path"]) == {
        "shipments.csv",
        "orders.csv",
    }
    assert set(selected_ledger["canonical_activity_horizon_end_day"]) == {29}


def test_no_activity_evidence_uses_explicit_unverified_fallback(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "prediction.csv"
    _prediction(prediction_path)
    graph = _graph(("SUP-INACTIVE", "item:I", "FACTORY"))

    selected = select_top_prediction_pairs(
        prediction_path,
        top_pairs=1,
        canonical_graph=graph,
        canonical_activity=None,
        canonical_activity_metadata={"evidence_status": "not_provided"},
        canonical_horizon_days=30,
    )

    assert selected["supplier_id"].tolist() == ["SUP-INACTIVE"]
    assert selected.iloc[0]["selection_status"] == "selected_graph_compatible"
    assert (
        selected.iloc[0]["canonical_activity_evidence_status"]
        == "activity_unverified_not_provided"
    )
    assert "active" not in selected.iloc[0][
        "canonical_activity_evidence_status"
    ]


def test_canonical_stage_preparation_freezes_same_active_prediction_lanes(
    tmp_path: Path,
) -> None:
    data = tmp_path / "baseline" / "data"
    data.mkdir(parents=True)
    baseline = data / "first_simulation_daily.csv"
    pd.DataFrame({"day": np.arange(30)}).to_csv(baseline, index=False)
    activity = _standardized_activity()
    activity.rename(
        columns={
            "supplier_id": "src_node_id",
            "qty": "shipped_qty",
        }
    ).assign(pulled_qty=lambda frame: frame["shipped_qty"])[
        [
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "pulled_qty",
            "shipped_qty",
        ]
    ].to_csv(
        data / "production_supplier_shipments_daily.csv",
        index=False,
    )
    prediction_path = tmp_path / "prediction.csv"
    _prediction(prediction_path)
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            _graph(
                ("SUP-INACTIVE", "item:I", "FACTORY"),
                ("SUP-ACTIVE-1", "item:A", "FACTORY"),
                ("SUP-ACTIVE-2", "item:B", "FACTORY"),
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "canonical"

    (
        replay_prediction_path,
        expected_events,
        expected_ledger,
        metadata,
    ) = _prepare_canonical_activity_selection(
        graph_path=graph_path,
        baseline_path=baseline,
        prediction_path=prediction_path,
        physical_risk_envelope=_physical_envelope(),
        output_root=output,
        days=30,
        risk_top_pairs=2,
        prediction_horizon_days=30,
    )

    assert replay_prediction_path == (
        output / "canonical_prediction_active_lanes.csv"
    )
    replay_prediction = pd.read_csv(replay_prediction_path)
    assert set(replay_prediction["supplier_id"]) == {
        "SUP-ACTIVE-1",
        "SUP-ACTIVE-2",
    }
    assert set(expected_events["supplier_id"]) == {
        "SUP-ACTIVE-1",
        "SUP-ACTIVE-2",
    }
    assert (
        expected_ledger["mapping_status"]
        .eq("not_applied_no_nonzero_canonical_flow")
        .sum()
        == 1
    )
    assert metadata["activity_filter_applied"] is True
    assert metadata["selected_pair_count"] == 2
    assert metadata["rejected_pair_count"] == 1
    assert not metadata["fallback_statement"]
