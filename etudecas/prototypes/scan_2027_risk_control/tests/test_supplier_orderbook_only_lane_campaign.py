from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as active,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_orderbook_only_lane_campaign as campaign,
)


def graph_with_orders() -> dict:
    return {
        "meta": {
            "opening_open_orders": {
                "rows": [
                    {
                        "order_type": "purchase_open_order",
                        "source_row": 8,
                        "src_node_id": "SDC-VD0951020A",
                        "dst_node_id": "M-1810",
                        "item_id": "item:001848",
                        "quantity": 6_000_000,
                        "uom": "G",
                        "physical_delivery_day": 50,
                        "usable_day": 69,
                    },
                    {
                        "order_type": "purchase_open_order",
                        "source_row": 14,
                        "src_node_id": "SDC-VD0910216A",
                        "dst_node_id": "M-1810",
                        "item_id": "item:002612",
                        "quantity": 22_500,
                        "uom": "KG",
                        "physical_delivery_day": 19,
                        "usable_day": 29,
                    },
                    {
                        "order_type": "purchase_open_order",
                        "source_row": 15,
                        "src_node_id": "SDC-VD0910216A",
                        "dst_node_id": "M-1810",
                        "item_id": "item:002612",
                        "quantity": 22_500,
                        "uom": "KG",
                        "physical_delivery_day": 35,
                        "usable_day": 47,
                    },
                ]
            }
        },
        "nodes": [
            {
                "id": "M-1810",
                "inventory": {
                    "states": [
                        {"item_id": "item:001848", "initial": 10_262.646},
                        {"item_id": "item:002612", "initial": 153_521.636719},
                    ]
                },
            }
        ],
        "edges": [
            {
                "id": "edge:001848",
                "from": "SDC-VD0951020A",
                "to": "M-1810",
                "items": ["item:001848"],
            },
            {
                "id": "edge:002612",
                "from": "SDC-VD0910216A",
                "to": "M-1810",
                "items": ["item:002612"],
            },
        ],
    }


def test_source_order_audit_converts_graph_g_to_standard_kg() -> None:
    audit = campaign.source_order_audit(graph_with_orders(), campaign.LANES[0])
    assert audit["observed_snapshot_order_row_count"] == 1
    assert audit["observed_snapshot_order_qty_standard"] == pytest.approx(6000.0)
    assert audit["raw_uoms"] == "G"
    assert audit["standard_uom"] == "KG"
    assert audit["source_rows"] == "8"


def test_risk_row_targets_exact_orderbook_lane() -> None:
    scenario = campaign.SCENARIO_BY_ID["quality_hold_180"]
    rows = campaign.risk_rows(
        graph_with_orders(), campaign.LANES[1], scenario, 720
    )
    assert rows == [
        {
            "event_id": "vd0910216a_002612_m1810__quality_hold_180",
            "risk_type": "quality_delay",
            "supplier_id": "SDC-VD0910216A",
            "item_id": "item:002612",
            "dst_node_id": "M-1810",
            "edge_id": "edge:002612",
            "start_day": 0,
            "end_day": 719,
            "multiplier": 180.0,
            "notes": (
                "simulated hypothesis applied to already-planned opening "
                "purchase order"
            ),
        }
    ]


def test_v10_audit_uses_measured_day_zero_and_consumption(tmp_path: Path) -> None:
    lane = campaign.LANES[0]
    data = tmp_path / "data"
    active.write_csv(
        data / "production_input_stocks_daily.csv",
        [
            {
                "day": day,
                "node_id": lane.destination_id,
                "item_id": lane.item_id,
                "stock_before_production": lane.v10_measurement_start_qty
                if day == 0
                else 100.0,
                "stock_end_of_day": (
                    lane.v10_measurement_start_qty
                    - lane.v10_horizon_consumption_qty
                    if day == 0
                    else 100.0
                ),
            }
            for day in range(720)
        ],
    )
    active.write_csv(
        data / "production_supplier_shipments_daily.csv",
        [
            {
                "arrival_day": 10,
                "src_node_id": "SDC-OTHER",
                "dst_node_id": lane.destination_id,
                "item_id": lane.item_id,
                "shipped_qty": lane.v10_dynamic_arrival_qty,
            }
        ],
    )
    audit = campaign.v10_masking_audit(tmp_path, lane)
    assert audit["validated"] is True
    assert audit["measurement_start_stock_qty"] == pytest.approx(7579.1484)
    assert audit["horizon_consumption_qty"] == pytest.approx(8857.296)
    assert audit["physical_cover_days_before_dynamic_arrivals"] == pytest.approx(
        616.1007657, rel=1e-6
    )


def test_pairing_separates_receipt_exposure_from_downstream_causality() -> None:
    common = {
        "state_id": "observed_snapshot_2025",
        "lane_id": "lane",
        "seed": 7,
        "product_on_due_volume_proxy": 0.95,
        "product_fill_rate": 1.0,
        "product_backlog_qty_days": 5.0,
        "product_backlog_end_qty": 0.0,
        "product_released_qty": 100.0,
        "opening_order_usable_qty": 10.0,
        "opening_order_weighted_usable_day": 20.0,
        "total_cost": 1.0,
        "descendant_signature_sha256": "same-descendants",
    }
    rows = campaign.attach_pairs(
        [
            {
                **common,
                "scenario_id": "baseline_orderbook_replay",
                "opening_order_receipt_signature_sha256": "baseline-receipt",
            },
            {
                **common,
                "scenario_id": "quality_hold_180",
                "opening_order_receipt_signature_sha256": "shifted-receipt",
                "opening_order_weighted_usable_day": 200.0,
            },
        ]
    )
    stress = rows[1]
    assert stress["causal_effect_on_receipt"] is True
    assert stress["causal_effect_on_descendants"] is False
    assert stress["causal_effect_on_client"] is False
    assert "was not consumed differently" in stress["effect_interpretation"]


def test_parse_seeds_deduplicates_ranges() -> None:
    assert campaign.parse_seeds("7-9,8,11") == (7, 8, 9, 11)


def test_execution_provenance_requires_unique_cases_and_retained_inputs(
    tmp_path: Path,
) -> None:
    orchestrator = tmp_path / "orchestrator.py"
    risk = tmp_path / "risk.csv"
    scale = tmp_path / "scale.csv"
    orchestrator.write_text("# frozen\n", encoding="utf-8")
    risk.write_text("risk\n", encoding="utf-8")
    scale.write_text("scale\n", encoding="utf-8")
    orchestrator_sha = active.sha256_file(orchestrator)
    manifest = {
        "planned_physical_engine_run_count": 1,
        "orchestrator_sha256_at_process_start": orchestrator_sha,
        "active_flow_library_sha256_at_process_start": "library-sha",
        "engine_sha256": "engine-sha",
        "source_graph_sha256": "graph-sha",
        "profile_args_sha256": "profile-sha",
    }
    records = [
        {
            "case_dir": str(tmp_path / "case"),
            "orchestrator_sha256_at_process_start": orchestrator_sha,
            "active_flow_library_sha256_at_process_start": "library-sha",
            "engine_sha256_at_case": "engine-sha",
            "source_graph_sha256_at_case": "graph-sha",
            "engine_profile_args_sha256": "profile-sha",
            "engine_command_normalized_sha256": "command-sha",
            "engine_command_normalized_json": "[]",
            "risk_csv": str(risk),
            "risk_csv_sha256": active.sha256_file(risk),
            "stock_scale_csv": str(scale),
            "stock_scale_csv_sha256": active.sha256_file(scale),
        }
    ]
    audit = campaign.build_execution_provenance_audit(
        records, manifest, orchestrator_path=orchestrator
    )
    assert audit["case_count_matches_plan"] is True
    assert audit["retained_risk_and_scale_inputs_match"] is True
    assert audit["reproducibility_wording_allowed"] is True

    risk.write_text("changed\n", encoding="utf-8")
    changed = campaign.build_execution_provenance_audit(
        records, manifest, orchestrator_path=orchestrator
    )
    assert changed["retained_risk_and_scale_inputs_match"] is False
    assert changed["reproducibility_wording_allowed"] is False


def test_business_summary_does_not_call_masking_resilience() -> None:
    common = {
        "state_id": "observed_snapshot_2025",
        "state_evidence_class": "observed_2025_snapshot_replayed",
        "lane_id": "lane",
        "supplier_id": "SDC-X",
        "item_id": "item:X",
        "destination_id": "M-X",
        "product_on_due_volume_proxy": 0.9,
        "causal_effect_on_receipt": False,
        "causal_effect_on_descendants": False,
        "causal_effect_on_client": False,
    }
    summary = campaign.build_business_summary(
        [
            {**common, "scenario_id": "baseline_orderbook_replay"},
            {
                **common,
                "scenario_id": "quality_hold_180",
                "causal_effect_on_receipt": True,
            },
        ],
        mode="snapshot",
        source_audits=[
            {
                "lane_id": "lane",
                "observed_snapshot_order_row_count": 1,
                "observed_snapshot_order_qty_standard": 10.0,
                "standard_uom": "KG",
                "physical_delivery_day_min": 1,
                "physical_delivery_day_max": 1,
                "usable_day_min": 2,
                "usable_day_max": 2,
            }
        ],
        masking_audits=[
            {
                "lane_id": "lane",
                "measurement_start_stock_qty": 100.0,
                "simulated_daily_consumption_qty": 1.0,
                "physical_cover_days_before_dynamic_arrivals": 100.0,
                "dynamic_arrival_qty": 0.0,
            }
        ],
    )
    row = summary["lane_state_summaries"][0]
    assert row["stress_with_receipt_effect_count"] == 1
    assert row["stress_with_descendant_lot_effect_count"] == 0
    assert "masking" in row["claim_not_allowed"]
    assert "resilience" in row["claim_not_allowed"]
