from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_industrial_results import (
    _cost_bridge_frame,
    _crisis_response_frame,
    _horizon_deferral_frame,
    _load_pair,
    _percentage_change,
    _prepare_output,
)


def _data_dir(root: Path) -> Path:
    data = root / "data"
    data.mkdir(parents=True)
    return data


def _write_pairing_contract(tmp_path: Path) -> Path:
    paired = tmp_path / "paired"
    rows = []
    for policy in ("mrp_reference", "canonical_feedback"):
        run = paired / policy / "seed_7"
        (run / "summaries").mkdir(parents=True)
        (run / "summaries" / "first_simulation_summary.json").write_text(
            json.dumps(
                {
                    "policy": {
                        "warmup_boundary_audit": {
                            "method": "deterministic_paired_burn_in_replay",
                            "core_state_sha256": "same-initial-state",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        rows.append(
            {
                "policy": policy,
                "seed": 7,
                "status": "ok",
                "result_dir": str(run),
                "days": 10,
                "scenario_id": "scn:test",
                "engine_artifact_profile": "full",
                "engine_artifact_contract_status": "validated_full",
                "common_random_numbers": True,
                "state_dependent_risks": True,
                "graph_sha256": "same-graph",
                "risk_events_sha256": "",
                "engine_profile_sha256": "same-profile",
            }
        )
    pd.DataFrame(rows).to_csv(paired / "canonical_closed_loop_runs.csv", index=False)
    (paired / "canonical_closed_loop_manifest.json").write_text(
        json.dumps(
            {
                "common_random_numbers": True,
                "state_dependent_risks": True,
                "seeds": [7],
                "scenario_id": "scn:test",
                "days": 10,
                "graph": {"sha256": "same-graph"},
                "engine_profile": {"sha256": "same-profile"},
                "engine_artifact_profile": "full",
                "engine_artifact_contract": {"status": "validated_full"},
            }
        ),
        encoding="utf-8",
    )
    return paired


def test_percentage_change_uses_reference_magnitude() -> None:
    assert _percentage_change(10.0, 8.0) == pytest.approx(-20.0)
    assert _percentage_change(-10.0, -8.0) == pytest.approx(20.0)


def test_output_directory_refuses_existing_content(tmp_path: Path) -> None:
    output = tmp_path / "pack"
    assert _prepare_output(output) == output.resolve()
    (output / "existing.txt").write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _prepare_output(output)


def test_pair_loader_validates_exogenous_and_initial_state_contract(
    tmp_path: Path,
) -> None:
    paired = _write_pairing_contract(tmp_path)

    seed, _mrp_dir, _v3_dir, _mrp, _v3, days = _load_pair(paired, seed=7)

    assert seed == 7
    assert days == 10


def test_pair_loader_rejects_unconfirmed_common_random_numbers(
    tmp_path: Path,
) -> None:
    paired = _write_pairing_contract(tmp_path)
    runs_path = paired / "canonical_closed_loop_runs.csv"
    runs = pd.read_csv(runs_path)
    runs.loc[runs["policy"].eq("canonical_feedback"), "common_random_numbers"] = False
    runs.to_csv(runs_path, index=False)

    with pytest.raises(ValueError, match="Common-random-number"):
        _load_pair(paired, seed=7)


def test_horizon_deferral_never_merges_mixed_units(tmp_path: Path) -> None:
    mrp = tmp_path / "mrp"
    v3 = tmp_path / "v3"
    mrp_data = _data_dir(mrp)
    v3_data = _data_dir(v3)
    columns = [
        "day",
        "src_node_id",
        "dst_node_id",
        "item_id",
        "uom",
        "shipped_qty",
    ]
    pd.DataFrame(
        [
            [0, "SUP", "M-1", "item:A", "G", 100.0],
            [365, "SUP", "M-1", "item:A", "G", 0.0],
            [0, "SUP", "M-1", "item:B", "UN", 10.0],
            [365, "SUP", "M-1", "item:B", "UN", 0.0],
        ],
        columns=columns,
    ).to_csv(mrp_data / "production_supplier_shipments_daily.csv", index=False)
    pd.DataFrame(
        [
            [0, "SUP", "M-1", "item:A", "G", 0.0],
            [365, "SUP", "M-1", "item:A", "G", 100.0],
            [0, "SUP", "M-1", "item:B", "UN", 0.0],
            [365, "SUP", "M-1", "item:B", "UN", 10.0],
        ],
        columns=columns,
    ).to_csv(v3_data / "production_supplier_shipments_daily.csv", index=False)

    result = _horizon_deferral_frame(mrp, v3, days=365)

    assert len(result) == 2
    assert set(result["uom"]) == {"G", "UN"}
    assert dict(zip(result["uom"], result["delta_measured"])) == {
        "G": -100.0,
        "UN": -10.0,
    }
    assert result["delta_all"].abs().max() == pytest.approx(0.0)


def test_cost_bridge_reconciles_total_cost(tmp_path: Path) -> None:
    mrp = tmp_path / "mrp"
    v3 = tmp_path / "v3"
    (mrp / "run").mkdir(parents=True)
    (v3 / "run").mkdir(parents=True)
    base = {
        "total_purchase_cost": 100.0,
        "total_transport_cost": 20.0,
        "total_holding_cost": 30.0,
        "total_warehouse_operating_cost": 40.0,
        "total_inventory_risk_cost": 10.0,
        "total_production_cost": 50.0,
        "total_cost": 250.0,
    }
    feedback = dict(base)
    feedback.update(
        {
            "total_purchase_cost": 95.0,
            "total_holding_cost": 37.0,
            "total_cost": 252.0,
        }
    )
    (mrp / "run" / "kpis.json").write_text(json.dumps(base), encoding="utf-8")
    (v3 / "run" / "kpis.json").write_text(json.dumps(feedback), encoding="utf-8")

    bridge = _cost_bridge_frame(mrp, v3)

    assert bridge["delta"].sum() == pytest.approx(2.0)
    assert bridge.loc[bridge["component"].eq("Achats"), "delta"].iloc[0] == -5.0


def test_crisis_response_measures_detection_action_gap(tmp_path: Path) -> None:
    run = tmp_path / "v3"
    data = _data_dir(run)
    pd.DataFrame(
        {
            "day": [0, 1, 2, 3, 4, 5],
            "node_id": ["CLIENT"] * 6,
            "item_id": ["item:FG"] * 6,
            "demand_qty": [10.0] * 6,
            "served_qty": [10.0, 0.0, 0.0, 10.0, 10.0, 10.0],
            "backlog_end_qty": [0.0, 10.0, 20.0, 0.0, 0.0, 0.0],
            "available_before_service_qty": [20.0, 0.0, 0.0, 30.0, 20.0, 10.0],
        }
    ).to_csv(data / "production_demand_service_daily.csv", index=False)
    pd.DataFrame(
        {
            "day": [0, 1, 2, 3, 4, 5],
            "confirmed_regime": [
                "NOMINAL",
                "CRISIS",
                "CRISIS",
                "CRISIS",
                "NOMINAL",
                "NOMINAL",
            ],
        }
    ).to_csv(data / "canonical_closed_loop_observations.csv", index=False)
    pd.DataFrame(
        {
            "effective_day": [1, 2, 3, 4, 5],
            "active": [0, 0, 0, 1, 0],
        }
    ).to_csv(data / "canonical_closed_loop_commands.csv", index=False)

    _frame, context = _crisis_response_frame(run, days=6)

    assert context["backlog_start_day"] == 1
    assert context["backlog_end_day"] == 2
    assert context["crisis_recognition_day"] == 1
    assert context["first_active_effective_day"] == 4
    assert context["active_during_backlog_days"] == 0
    assert context["zero_service_days"] == 2
