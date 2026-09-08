from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_node_comparison import (
    build_canonical_node_comparison,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    paired = tmp_path / "paired"
    reference = paired / "mrp_reference" / "seed_7"
    feedback = paired / "canonical_feedback" / "seed_7"
    for run in (reference, feedback):
        (run / "data").mkdir(parents=True)
        (run / "run").mkdir()
        (run / "summaries").mkdir()
        (run / "run" / "nodes.json").write_text(
            json.dumps(
                [
                    {
                        "id": "PLANT",
                        "type": "factory",
                        "name": "Plant",
                        "lat": 45.0,
                        "lon": 2.0,
                    },
                    {
                        "id": "SUP",
                        "type": "supplier_dc",
                        "name": "Supplier",
                        "lat": 50.0,
                        "lon": 4.0,
                    },
                ]
            ),
            encoding="utf-8",
        )
        (run / "run" / "flows.json").write_text(
            json.dumps(
                [
                    {
                        "id": "edge:SUP_TO_PLANT_ITEM",
                        "from": "SUP",
                        "to": "PLANT",
                        "items": ["item:A"],
                    }
                ]
            ),
            encoding="utf-8",
        )
        (run / "summaries" / "first_simulation_summary.json").write_text(
            json.dumps(
                {
                    "policy": {
                        "warmup_boundary_audit": {
                            "core_state_sha256": "same-state"
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    pd.DataFrame(
        {
            "day": [0, 1],
            "demand": [10.0, 10.0],
            "served": [9.0, 10.0],
            "backlog_end": [1.0, 0.0],
            "inventory_total": [20.0, 18.0],
            "total_supply_cost_day": [100.0, 110.0],
        }
    ).to_csv(reference / "data" / "first_simulation_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": [0, 1],
            "demand": [10.0, 10.0],
            "served": [9.0, 10.0],
            "backlog_end": [1.0, 0.0],
            "inventory_total": [19.0, 16.0],
            "total_supply_cost_day": [101.0, 111.0],
        }
    ).to_csv(feedback / "data" / "first_simulation_daily.csv", index=False)

    pd.DataFrame(
        {
            "day": [0, 1],
            "node_id": ["PLANT", "PLANT"],
            "item_id": ["item:A", "item:A"],
            "stock_before_production": [10.0, 8.0],
            "stock_end_of_day": [8.0, 7.0],
        }
    ).to_csv(reference / "data" / "production_input_stocks_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": [0, 1],
            "node_id": ["PLANT", "PLANT"],
            "item_id": ["item:A", "item:A"],
            "stock_before_production": [10.0, 7.0],
            "stock_end_of_day": [7.0, 5.0],
        }
    ).to_csv(feedback / "data" / "production_input_stocks_daily.csv", index=False)

    for run, consumed, shipped in (
        (reference, [2.0, 1.0], [4.0, 0.0]),
        (feedback, [3.0, 2.0], [3.0, 2.0]),
    ):
        pd.DataFrame(
            {
                "day": [0, 1],
                "node_id": ["PLANT", "PLANT"],
                "item_id": ["item:A", "item:A"],
                "consumed_qty": consumed,
                "uom": ["UN", "UN"],
            }
        ).to_csv(
            run / "data" / "production_input_consumption_daily.csv",
            index=False,
        )
        pd.DataFrame(
            {
                "day": [0, 1],
                "node_id": ["PLANT", "PLANT"],
                "item_id": ["item:A", "item:A"],
                "shipped_to_node_qty": shipped,
                "uom": ["UN", "UN"],
            }
        ).to_csv(
            run
            / "data"
            / "production_input_replenishment_shipments_daily.csv",
            index=False,
        )

    pd.DataFrame(
        {
            "day": [0],
            "node_id": ["PLANT"],
            "item_id": ["item:P"],
            "stock_end_of_day": [4.0],
        }
    ).to_csv(reference / "data" / "production_dc_stocks_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": [1],
            "node_id": ["PLANT"],
            "item_id": ["item:P"],
            "stock_end_of_day": [6.0],
        }
    ).to_csv(feedback / "data" / "production_dc_stocks_daily.csv", index=False)

    pd.DataFrame(
        {
            "day": [0],
            "src_node_id": ["SUP"],
            "dst_node_id": ["PLANT"],
            "item_id": ["item:A"],
            "shipped_qty": [3.0],
            "pulled_qty": [3.0],
            "lead_days": [2.0],
            "reliability": [1.0],
            "transport_cost": [4.0],
        }
    ).to_csv(
        reference / "data" / "production_supplier_shipments_daily.csv",
        index=False,
    )
    pd.DataFrame(
        {
            "day": [1],
            "src_node_id": ["SUP"],
            "dst_node_id": ["PLANT"],
            "item_id": ["item:A"],
            "shipped_qty": [5.0],
            "pulled_qty": [5.0],
            "lead_days": [2.0],
            "reliability": [1.0],
            "transport_cost": [6.0],
        }
    ).to_csv(
        feedback / "data" / "production_supplier_shipments_daily.csv",
        index=False,
    )

    for run, cause in ((reference, "input"), (feedback, "capacity")):
        pd.DataFrame(
            {
                "day": [0],
                "node_id": ["PLANT"],
                "output_item_id": ["item:P"],
                "desired_qty": [10.0],
                "actual_qty": [8.0],
                "binding_cause": [cause],
            }
        ).to_csv(run / "data" / "production_constraint_daily.csv", index=False)

    for run, qty, lot_id in (
        (reference, 2.0, "LOT-MRP"),
        (feedback, 3.0, "LOT-V3"),
    ):
        pd.DataFrame(
            {
                "event_id": [f"EVENT-{lot_id}"],
                "day": [0],
                "event_type": ["production_consumption"],
                "lot_id": [lot_id],
                "node_id": ["PLANT"],
                "item_id": ["item:A"],
                "qty": [qty],
                "qty_after": [10.0 - qty],
                "uom": ["UN"],
                "source_id": [f"SOURCE-{lot_id}"],
            }
        ).to_csv(run / "data" / "production_lot_events.csv", index=False)
        pd.DataFrame(
            {
                "day": [0],
                "link_type": ["production"],
                "parent_lot_id": [lot_id],
                "parent_node_id": ["PLANT"],
                "parent_item_id": ["item:A"],
                "child_lot_id": [f"CHILD-{lot_id}"],
                "child_node_id": ["PLANT"],
                "child_item_id": ["item:P"],
                "parent_qty": [qty],
                "child_qty": [8.0],
                "allocation_share": [0.25 if run == reference else 0.375],
            }
        ).to_csv(run / "data" / "production_lot_genealogy.csv", index=False)

    pd.DataFrame(
        [
            {
                "policy": "mrp_reference",
                "seed": 7,
                "status": "ok",
                "result_dir": str(reference),
                "scenario_id": "scn:BASE",
                "days": 2,
                "common_random_numbers": True,
                "state_dependent_risks": True,
                "graph_sha256": "graph",
                "engine_profile_sha256": "profile",
            },
            {
                "policy": "canonical_feedback",
                "seed": 7,
                "status": "ok",
                "result_dir": str(feedback),
                "scenario_id": "scn:BASE",
                "days": 2,
                "common_random_numbers": True,
                "state_dependent_risks": True,
                "graph_sha256": "graph",
                "engine_profile_sha256": "profile",
            },
        ]
    ).to_csv(paired / "canonical_closed_loop_runs.csv", index=False)
    return paired, reference, feedback


def test_builds_granular_flow_state_and_derived_consumption(tmp_path: Path) -> None:
    paired, reference, feedback = _write_pair(tmp_path)
    source_hashes = {
        path: _digest(path)
        for path in (
            reference / "data" / "production_input_stocks_daily.csv",
            feedback / "data" / "production_input_stocks_daily.csv",
        )
    }
    output = tmp_path / "comparison"
    artifacts = build_canonical_node_comparison(
        paired_results_dir=paired,
        output_dir=output,
        seed=7,
        make_plots=False,
    )

    consumption = artifacts.summary.loc[
        artifacts.summary["family"].eq("plant_input_stock")
        & artifacts.summary["metric"].eq("derived_consumed_qty")
    ].iloc[0]
    assert consumption["mrp_value"] == pytest.approx(3.0)
    assert consumption["v3_value"] == pytest.approx(5.0)
    assert consumption["delta"] == pytest.approx(2.0)

    direct_consumption = artifacts.summary.loc[
        artifacts.summary["family"].eq("plant_input_consumption")
        & artifacts.summary["metric"].eq("consumed_qty")
    ].iloc[0]
    assert direct_consumption["mrp_value"] == pytest.approx(3.0)
    assert direct_consumption["v3_value"] == pytest.approx(5.0)

    plant_shipments = artifacts.summary.loc[
        artifacts.summary["family"].eq("plant_input_shipments")
        & artifacts.summary["metric"].eq("shipped_to_node_qty")
    ].iloc[0]
    assert plant_shipments["mrp_value"] == pytest.approx(4.0)
    assert plant_shipments["v3_value"] == pytest.approx(5.0)
    statuses = artifacts.missing_metrics.set_index("indicator")["status"]
    assert statuses["consommation_composants_usine"] == "direct_table_compared"
    assert (
        statuses["expeditions_reapprovisionnement_usine"]
        == "direct_table_compared"
    )
    assert (
        statuses["traces_lots_et_genealogie"]
        == "aggregated_event_comparison_available"
    )
    lot_qty = artifacts.summary.loc[
        artifacts.summary["family"].eq("lot_events")
        & artifacts.summary["metric"].eq("qty")
    ].iloc[0]
    assert lot_qty["mrp_value"] == pytest.approx(2.0)
    assert lot_qty["v3_value"] == pytest.approx(3.0)
    column_coverage = pd.read_csv(
        output / "canonical_node_comparison_column_coverage.csv"
    )
    assert column_coverage.loc[
        column_coverage["column"].eq("qty_after"), "status"
    ].eq("not_comparable_without_lot_identity").all()

    shipments = pd.read_csv(
        output / "tables_by_family" / "supplier_shipments_paired.csv"
    ).sort_values("day")
    assert shipments["shipped_qty_mrp"].tolist() == [3.0, 0.0]
    assert shipments["shipped_qty_v3"].tolist() == [0.0, 5.0]

    dc_stock = pd.read_csv(
        output / "tables_by_family" / "distribution_stock_paired.csv"
    ).sort_values("day")
    assert pd.isna(dc_stock.iloc[0]["stock_end_of_day_v3"])
    assert pd.isna(dc_stock.iloc[1]["stock_end_of_day_mrp"])

    categories = pd.read_csv(
        output / "canonical_node_comparison_categorical_changes.csv"
    )
    binding = categories.loc[categories["column"].eq("binding_cause")].iloc[0]
    assert binding["mrp_value"] == "input"
    assert binding["v3_value"] == "capacity"
    assert all(_digest(path) == digest for path, digest in source_hashes.items())


def test_dashboard_is_autonomous_and_contains_pairing_evidence(tmp_path: Path) -> None:
    paired, _, _ = _write_pair(tmp_path)
    artifacts = build_canonical_node_comparison(
        paired_results_dir=paired,
        output_dir=tmp_path / "comparison",
        make_plots=False,
    )
    dashboard = artifacts.dashboard_path.read_text(encoding="utf-8")
    assert "DecompressionStream" in dashboard
    assert "application/octet-stream" in dashboard
    assert "<script src=" not in dashboard
    assert "fetch(" not in dashboard
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["pairing_contract"]["same_physical_state_at_measurement_start"]
    assert manifest["counts"]["node_count"] == 2


def test_refuses_non_empty_output_without_touching_marker(tmp_path: Path) -> None:
    paired, _, _ = _write_pair(tmp_path)
    output = tmp_path / "comparison"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        build_canonical_node_comparison(
            paired_results_dir=paired,
            output_dir=output,
            make_plots=False,
        )
    assert marker.read_text(encoding="utf-8") == "do not overwrite"


def test_rejects_different_network_topologies(tmp_path: Path) -> None:
    paired, _, feedback = _write_pair(tmp_path)
    nodes_path = feedback / "run" / "nodes.json"
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    nodes[0]["id"] = "OTHER_PLANT"
    nodes_path.write_text(json.dumps(nodes), encoding="utf-8")
    with pytest.raises(ValueError, match="topology mismatch"):
        build_canonical_node_comparison(
            paired_results_dir=paired,
            output_dir=tmp_path / "comparison",
            make_plots=False,
        )
