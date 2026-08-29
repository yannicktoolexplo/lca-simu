from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_cascade_campaign import (
    CascadeCampaignError,
    RUN_COLUMNS,
)
from etudecas.prototypes.scan_2027_risk_control.canonical_cascade_comparison import (
    compare_campaign,
)


CASCADE_ID = "quality_quarantine_021081_to_268967"
STATE_HASH = "a" * 64
COMPONENT_HASHES = json.dumps({"inventory": "b" * 64}, sort_keys=True)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(
    path: Path, columns: list[str] | tuple[str, ...], rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_result(
    path: Path,
    *,
    backlog: list[float],
    served: list[float],
    production: list[float],
) -> None:
    _write_csv(
        path / "data" / "production_demand_service_daily.csv",
        ["day", "node_id", "item_id", "demand_qty", "served_qty", "backlog_end_qty"],
        [
            {
                "day": day,
                "node_id": "C-XXXXX",
                "item_id": "item:268967",
                "demand_qty": 10,
                "served_qty": served[day],
                "backlog_end_qty": backlog[day],
            }
            for day in range(len(backlog))
        ],
    )
    _write_csv(
        path / "data" / "production_output_products_daily.csv",
        ["day", "node_id", "item_id", "produced_qty"],
        [
            {
                "day": day,
                "node_id": "M-1430",
                "item_id": "item:268967",
                "produced_qty": qty,
            }
            for day, qty in enumerate(production)
        ],
    )


def _complete_run_row(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {column: "" for column in RUN_COLUMNS}
    row.update(
        {
            "cascade_id": CASCADE_ID,
            "seed": 7,
            "status": "ok",
            "returncode": 0,
            "days": 7,
            "scenario_id": "baseline",
            "production_lot_count": 2,
            "target_order_qty": 100,
            "target_stock_qty_days": 500,
            "base_operational_supply_cost": 900,
            "opening_transport_cost": 40,
            "opening_purchase_cost": 60,
            "external_transport_cost": 0,
            "external_purchase_cost": 0,
            "controllable_operating_cost": 900,
            "decision_total_cost": 1000,
            "decision_transport_cost": 100,
            "decision_purchase_cost": 700,
            "supplier_risk_applied_row_count": 0,
            "supplier_risk_applied_event_ids": "",
            "action_execution_status": "not_applicable",
            "expected_action_signature_count": 0,
            "verified_action_signature_count": 0,
            "verified_action_row_count": 0,
            "verified_action_evidence_json": "{}",
            "measurement_start_state_sha256": STATE_HASH,
            "measurement_start_component_sha256_json": COMPONENT_HASHES,
            "pairing_status": "measurement_start_state_matched",
            "incident_validation_status": "reference_no_incident",
        }
    )
    row.update(updates)
    return row


def _refresh_manifest(campaign: Path) -> None:
    runs = campaign / "canonical_cascade_runs.csv"
    commands = campaign / "canonical_cascade_commands.json"
    snapshot = campaign / "canonical_cascade_config_snapshot.json"
    with runs.open("r", encoding="utf-8", newline="") as stream:
        run_rows = [dict(row) for row in csv.DictReader(stream)]
    manifest = {
        "schema_version": "scan.canonical_cascade_manifest.v2",
        "status": "complete",
        "failure_count": 0,
        "skipped_fail_fast_count": 0,
        "seeds": sorted({int(row["seed"]) for row in run_rows}),
        "cascade_ids": sorted({str(row["cascade_id"]) for row in run_rows}),
        "variant_ids": sorted({str(row["variant_id"]) for row in run_rows}),
        "run_count": len(run_rows),
        "config": {"sha256": _digest(snapshot)},
        "output_sha256": {
            "runs": _digest(runs),
            "commands": _digest(commands),
            "config_snapshot": _digest(snapshot),
        },
    }
    (campaign / "canonical_cascade_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _campaign_fixture(tmp_path: Path) -> Path:
    campaign = tmp_path / "campaign"
    normal = campaign / "runs" / "normal"
    untreated = campaign / "runs" / "untreated"
    solution = campaign / "runs" / "solution"
    _write_result(
        normal,
        backlog=[0, 0, 0, 0, 0, 0, 0],
        served=[10, 10, 10, 10, 10, 10, 10],
        production=[10, 10, 10, 10, 10, 10, 10],
    )
    _write_result(
        untreated,
        backlog=[0, 10, 10, 10, 0, 0, 0],
        served=[10, 0, 10, 10, 20, 10, 10],
        production=[10, 0, 7, 7, 16, 10, 10],
    )
    _write_result(
        solution,
        backlog=[0, 5, 5, 0, 0, 0, 0],
        served=[10, 5, 10, 15, 10, 10, 10],
        production=[10, 3, 8, 10, 12, 10, 10],
    )

    config = {
        "schema_version": "scan.canonical_cascade_campaign.v2",
        "campaign": {"days": 7},
        "cascades": [
            {
                "id": CASCADE_ID,
                "customer_id": "C-XXXXX",
                "finished_item_id": "item:268967",
                "reference_lot_qty": 10,
                "production_target": {
                    "node_id": "M-1430",
                    "item_id": "item:268967",
                },
                "incident": {
                    "start_day": 1,
                    "end_day": 2,
                    "risk_events": [
                        {
                            "event_id": "quality_hold",
                            "risk_type": "quality_delay",
                        }
                    ],
                },
                "recovery_consecutive_days": 2,
                "backlog_tolerance_qty": 1e-6,
                "solutions": [
                    {
                        "id": "expedited_transport",
                        "lever_fidelity": "native_simplified",
                        "native_levers": ["expedite_level"],
                        "approximation_levers": [],
                        "approximation_notes": "Only newly released flows are accelerated.",
                    }
                ],
            }
        ],
    }
    campaign.mkdir(parents=True, exist_ok=True)
    (campaign / "canonical_cascade_config_snapshot.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    rows = [
        _complete_run_row(
            variant_id="normal",
            case_type="normal",
            solution_id="",
            result_dir=str(normal),
        ),
        _complete_run_row(
            variant_id="incident_no_action",
            case_type="incident_no_action",
            solution_id="",
            result_dir=str(untreated),
            supplier_risk_applied_row_count=2,
            supplier_risk_applied_event_ids="quality_hold",
            incident_validation_status="physically_applied_with_customer_exposure",
        ),
        _complete_run_row(
            variant_id="incident_expedited_transport",
            case_type="incident_with_solution",
            solution_id="expedited_transport",
            result_dir=str(solution),
            production_lot_count=3,
            target_order_qty=130,
            target_stock_qty_days=520,
            base_operational_supply_cost=1250,
            external_transport_cost=50,
            external_purchase_cost=50,
            controllable_operating_cost=1350,
            decision_total_cost=1500,
            decision_transport_cost=200,
            decision_purchase_cost=900,
            action_execution_status="fully_verified",
            expected_action_signature_count=1,
            verified_action_signature_count=1,
            verified_action_row_count=3,
            verified_action_evidence_json=json.dumps(
                {"verified_groups": [{"action": "expedite_level", "uom": "KG"}]}
            ),
            incident_validation_status="paired_untreated_incident_with_customer_exposure",
        ),
    ]
    _write_csv(campaign / "canonical_cascade_runs.csv", RUN_COLUMNS, rows)
    commands = [
        {
            "cascade_id": row["cascade_id"],
            "variant_id": row["variant_id"],
            "seed": row["seed"],
        }
        for row in rows
    ]
    (campaign / "canonical_cascade_commands.json").write_text(
        json.dumps(commands), encoding="utf-8"
    )
    _refresh_manifest(campaign)
    return campaign


def _read_comparison(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return next(csv.DictReader(stream))


def test_compares_paired_trajectories_and_copies_demo_inputs(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    source_runs = campaign / "canonical_cascade_runs.csv"
    source_digest = _digest(source_runs)
    output = tmp_path / "comparison"

    summary_path = compare_campaign(campaign_dir=campaign, output_dir=output)

    row = _read_comparison(output / "canonical_cascade_comparison.csv")
    assert float(row["customer_impact_onset_day_no_action"]) == pytest.approx(1)
    assert float(row["terminal_recovery_day_no_action"]) == pytest.approx(4)
    assert float(row["terminal_recovery_day_solution"]) == pytest.approx(3)
    assert float(row["days_recovered_vs_no_action"]) == pytest.approx(1)
    assert float(row["shortage_days_avoided"]) == pytest.approx(1)
    assert float(row["gross_positive_customer_service_gain_qty"]) == pytest.approx(10)
    assert float(row["net_customer_service_gain_qty"]) == pytest.approx(0)
    assert float(row["gross_positive_production_gain_qty"]) == pytest.approx(7)
    assert float(row["net_production_gain_qty"]) == pytest.approx(3)
    assert float(row["gross_positive_production_lot_starts"]) == pytest.approx(1)
    assert float(row["net_production_lot_starts"]) == pytest.approx(1)
    assert float(row["gross_additional_mrp_release_qty"]) == pytest.approx(30)
    assert float(row["incremental_decision_total_cost_vs_no_action"]) == pytest.approx(500)
    assert float(row["incremental_controllable_operating_cost_vs_no_action"]) == pytest.approx(450)
    assert float(row["remaining_customer_impact_ratio"]) == pytest.approx(1 / 3)
    assert row["action_execution_status"] == "fully_verified"
    assert row["ranking_eligible"] == "True"

    copied_runs = output / "canonical_cascade_runs.csv"
    assert _digest(copied_runs) == source_digest
    assert _digest(source_runs) == source_digest
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["comparison_row_count"] == 1
    assert (
        summary["best_solution_by_remaining_customer_impact_then_recovery_and_cost"][
            CASCADE_ID
        ]
        == "expedited_transport"
    )
    assert summary["outputs"]["runs_csv"] == str(copied_runs.resolve())
    assert summary["outputs"]["runs_csv_sha256"] == source_digest


def test_comparator_refuses_nonempty_output(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    output = tmp_path / "comparison"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("older comparison", encoding="utf-8")

    with pytest.raises(CascadeCampaignError, match="Refusing to overwrite"):
        compare_campaign(campaign_dir=campaign, output_dir=output)
    assert marker.read_text(encoding="utf-8") == "older comparison"


def test_comparator_rejects_unfinished_physical_runs(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    runs_path = campaign / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    rows[-1]["status"] = "planned"
    _write_csv(runs_path, RUN_COLUMNS, rows)
    _refresh_manifest(campaign)

    with pytest.raises(CascadeCampaignError, match="successful physical runs"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_comparator_rejects_measurement_start_state_mismatch(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    runs_path = campaign / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    rows[-1]["measurement_start_state_sha256"] = "c" * 64
    _write_csv(runs_path, RUN_COLUMNS, rows)
    _refresh_manifest(campaign)

    with pytest.raises(CascadeCampaignError, match="state mismatch"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_comparator_rejects_incident_without_customer_effect(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    untreated = campaign / "runs" / "untreated"
    _write_result(
        untreated,
        backlog=[0] * 7,
        served=[10] * 7,
        production=[10] * 7,
    )

    with pytest.raises(CascadeCampaignError, match="no positive incremental"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_comparator_keeps_physically_applied_incident_absorbed_before_customer(
    tmp_path: Path,
) -> None:
    campaign = _campaign_fixture(tmp_path)
    config_path = campaign / "canonical_cascade_config_snapshot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["scientific_guards"] = {
        "require_positive_incremental_customer_backlog": False
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    for variant in ("untreated", "solution"):
        _write_result(
            campaign / "runs" / variant,
            backlog=[0] * 7,
            served=[10] * 7,
            production=[10, 8, 9, 10, 11, 10, 10],
        )
    runs_path = campaign / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    rows[1]["incident_validation_status"] = (
        "physically_applied_no_customer_exposure"
    )
    rows[2]["incident_validation_status"] = (
        "paired_untreated_incident_no_customer_exposure"
    )
    _write_csv(runs_path, RUN_COLUMNS, rows)
    _refresh_manifest(campaign)

    summary_path = compare_campaign(
        campaign_dir=campaign, output_dir=tmp_path / "comparison"
    )

    row = _read_comparison(
        tmp_path / "comparison" / "canonical_cascade_comparison.csv"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    aggregate = summary["aggregates"][0]
    assert row["incident_application_verified"] == "True"
    assert row["customer_exposure_detected"] == "False"
    assert row["customer_exposure_status"] == "absorbed_before_customer"
    assert row["recovery_status"] == "untreated_incident_absorbed_before_customer"
    assert row["days_recovered_vs_no_action"] == ""
    assert row["remaining_customer_impact_ratio"] == ""
    assert row["ranking_eligible"] == "False"
    assert "physically applied but caused no customer exposure" in row[
        "ranking_exclusion_reasons"
    ]
    assert aggregate["customer_exposure_seed_count"] == 0
    assert aggregate["customer_exposure_frequency"] == pytest.approx(0.0)
    assert aggregate[
        "mean_no_action_incremental_customer_backlog_qty_days_unconditional"
    ] == pytest.approx(0.0)
    assert aggregate["worst_no_action_incremental_customer_backlog_qty_days"] == pytest.approx(
        0.0
    )
    assert aggregate["mean_days_recovered_vs_no_action"] is None
    assert (
        summary["best_solution_by_remaining_customer_impact_then_recovery_and_cost"][
            CASCADE_ID
        ]
        == ""
    )


def test_comparator_aggregates_mixed_customer_exposure_without_biasing_mean(
    tmp_path: Path,
) -> None:
    campaign = _campaign_fixture(tmp_path)
    config_path = campaign / "canonical_cascade_config_snapshot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["scientific_guards"] = {
        "require_positive_incremental_customer_backlog": False
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    normal = campaign / "runs" / "normal-seed-8"
    untreated = campaign / "runs" / "untreated-seed-8"
    solution = campaign / "runs" / "solution-seed-8"
    for path in (normal, untreated, solution):
        _write_result(
            path,
            backlog=[0] * 7,
            served=[10] * 7,
            production=[10] * 7,
        )
    runs_path = campaign / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    second_seed_rows: list[dict[str, object]] = []
    for source, result_dir in zip(
        rows,
        (normal, untreated, solution),
        strict=True,
    ):
        copied: dict[str, object] = dict(source)
        copied["seed"] = 8
        copied["result_dir"] = str(result_dir)
        if copied["case_type"] == "incident_no_action":
            copied["incident_validation_status"] = (
                "physically_applied_no_customer_exposure"
            )
        elif copied["case_type"] == "incident_with_solution":
            copied["incident_validation_status"] = (
                "paired_untreated_incident_no_customer_exposure"
            )
        second_seed_rows.append(copied)
    _write_csv(runs_path, RUN_COLUMNS, [*rows, *second_seed_rows])
    commands_path = campaign / "canonical_cascade_commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands.extend(
        {
            "cascade_id": row["cascade_id"],
            "variant_id": row["variant_id"],
            "seed": row["seed"],
        }
        for row in second_seed_rows
    )
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    _refresh_manifest(campaign)

    summary_path = compare_campaign(
        campaign_dir=campaign, output_dir=tmp_path / "comparison"
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    aggregate = summary["aggregates"][0]
    assert aggregate["seed_count"] == 2
    assert aggregate["customer_exposure_seed_count"] == 1
    assert aggregate["no_customer_exposure_seed_count"] == 1
    assert aggregate["customer_exposure_frequency"] == pytest.approx(0.5)
    assert aggregate[
        "mean_no_action_incremental_customer_backlog_qty_days_unconditional"
    ] == pytest.approx(15.0)
    assert aggregate["worst_no_action_incremental_customer_backlog_qty_days"] == pytest.approx(
        30.0
    )
    assert aggregate["mean_days_recovered_vs_no_action"] == pytest.approx(1.0)
    assert aggregate["ranking_eligible_for_all_seeds"] is False
    assert aggregate["ranking_eligible_for_all_exposed_seeds"] is True
    assert (
        summary["best_solution_by_remaining_customer_impact_then_recovery_and_cost"][
            CASCADE_ID
        ]
        == "expedited_transport"
    )


def test_comparator_rejects_absorbed_incident_with_inconsistent_campaign_status(
    tmp_path: Path,
) -> None:
    campaign = _campaign_fixture(tmp_path)
    config_path = campaign / "canonical_cascade_config_snapshot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["scientific_guards"] = {
        "require_positive_incremental_customer_backlog": False
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    _write_result(
        campaign / "runs" / "untreated",
        backlog=[0] * 7,
        served=[10] * 7,
        production=[10] * 7,
    )
    _refresh_manifest(campaign)

    with pytest.raises(CascadeCampaignError, match="validation status is inconsistent"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_comparator_rejects_missing_measured_day(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    service_path = (
        campaign
        / "runs"
        / "solution"
        / "data"
        / "production_demand_service_daily.csv"
    )
    with service_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    _write_csv(service_path, list(rows[0]), rows[:-1])

    with pytest.raises(CascadeCampaignError, match="Incomplete measured-day coverage"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_nonranking_variant_is_kept_but_excluded_from_selection(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    config_path = campaign / "canonical_cascade_config_snapshot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    solution = config["cascades"][0]["solutions"][0]
    solution["ranking_eligible"] = False
    solution["ranking_exclusion_reason"] = "Diagnostic negative control."
    config_path.write_text(json.dumps(config), encoding="utf-8")
    _refresh_manifest(campaign)

    summary_path = compare_campaign(
        campaign_dir=campaign, output_dir=tmp_path / "comparison"
    )
    row = _read_comparison(
        tmp_path / "comparison" / "canonical_cascade_comparison.csv"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert row["ranking_eligible"] == "False"
    assert row["ranking_exclusion_reasons"] == "Diagnostic negative control."
    assert (
        summary["best_solution_by_remaining_customer_impact_then_recovery_and_cost"][
            CASCADE_ID
        ]
        == ""
    )


def test_comparator_requires_complete_manifest(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    manifest_path = campaign / "canonical_cascade_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "completed_with_failures"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(CascadeCampaignError, match="status must be complete"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_comparator_rejects_duplicate_campaign_grid_row(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    runs_path = campaign / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    rows.append(dict(rows[-1]))
    _write_csv(runs_path, RUN_COLUMNS, rows)
    _refresh_manifest(campaign)

    with pytest.raises(CascadeCampaignError, match="duplicate"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


def test_comparator_rejects_missing_planned_grid_row(tmp_path: Path) -> None:
    campaign = _campaign_fixture(tmp_path)
    runs_path = campaign / "canonical_cascade_runs.csv"
    with runs_path.open("r", encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    _write_csv(runs_path, RUN_COLUMNS, rows[:-1])
    _refresh_manifest(campaign)

    with pytest.raises(CascadeCampaignError, match="differs from the planned"):
        compare_campaign(campaign_dir=campaign, output_dir=tmp_path / "comparison")


@pytest.mark.parametrize("censored_variant", ["untreated", "solution"])
def test_censored_recovery_excludes_solution_without_partial_mean(
    tmp_path: Path, censored_variant: str
) -> None:
    campaign = _campaign_fixture(tmp_path)
    result = campaign / "runs" / censored_variant
    _write_result(
        result,
        backlog=[0, 5, 5, 5, 5, 5, 5],
        served=[10, 5, 10, 10, 10, 10, 10],
        production=[10, 3, 8, 10, 12, 10, 10],
    )

    summary_path = compare_campaign(
        campaign_dir=campaign, output_dir=tmp_path / "comparison"
    )
    row = _read_comparison(
        tmp_path / "comparison" / "canonical_cascade_comparison.csv"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert row["ranking_eligible"] == "False"
    assert "censored by the simulation horizon" in row["ranking_exclusion_reasons"]
    assert summary["aggregates"][0]["mean_days_recovered_vs_no_action"] is None
    assert (
        summary["best_solution_by_remaining_customer_impact_then_recovery_and_cost"][
            CASCADE_ID
        ]
        == ""
    )
