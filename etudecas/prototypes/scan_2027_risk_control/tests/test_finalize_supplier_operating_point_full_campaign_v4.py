from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v4 as subject,
)


def _signed_case(path: Path, payload: dict[str, object]) -> None:
    payload = dict(payload)
    payload["evidence_signature"] = subject._stable_sha256(payload)
    subject._write_json(path, payload)


def _lot_selection_fixture(tmp_path):
    campaign_signature = "a" * 64
    engine_sha = "b" * 64
    lane_id = "lane_01"
    identity = ("SUP-01", "item:000001", "M-1810", "edge:01", "268091")
    manifest = {
        "campaign_signature": campaign_signature,
        "engine_sha256": engine_sha,
    }
    context = subject.SignedCampaignContext(
        manifest=manifest,
        operating_point_provenance={},
        preflight={},
        registry={},
        achieved_services={},
        lane_identity={lane_id: identity},
        shard_ids=frozenset({"op_80__seed_block_01"}),
        disruption_window_days=42,
        preflight_path=tmp_path / "binding.json",
        registry_path=tmp_path / "registry.json",
        discovery_progress_path=tmp_path / "progress.json",
    )
    priority_rows = []
    paired_rows = []
    shard_id = "op_80__seed_block_01"
    evidence_dir = tmp_path / "shards" / shard_id / "case_evidence"
    risk_dir = tmp_path / "shards" / shard_id / "inputs" / "risk_events"
    evidence_dir.mkdir(parents=True)
    risk_dir.mkdir(parents=True)
    seeds = subject.EXPECTED_SEEDS[:2]
    for mechanism_index, mechanism in enumerate(subject.MECHANISMS, 1):
        priority_rows.append(
            {
                "operating_point_id": "op_80",
                "mechanism": mechanism,
                "lane_id": lane_id,
                "supplier_id": identity[0],
                "item_id": identity[1],
                "dst_node_id": identity[2],
                "edge_id": identity[3],
                "target_product_id": identity[4],
                "priority_status": (
                    "robust_priority"
                    if mechanism_index == 1
                    else "dossier_to_investigate"
                ),
                "position": mechanism_index,
                "bootstrap_unambiguous_top3_probability": 0.9 / mechanism_index,
                "bootstrap_top3_inclusion_probability": 0.95,
                "fixed360_effect_mean_pp": 2.0,
            }
        )
        for seed_index, seed in enumerate(seeds):
            baseline_key = f"op_80__baseline__seed_{seed}"
            baseline_signature = subject._stable_sha256(
                {"kind": "baseline", "seed": seed}
            )
            baseline_path = evidence_dir / f"{baseline_key}.json"
            if not baseline_path.exists():
                _signed_case(
                    baseline_path,
                    {
                        "schema_version": subject.INPUT_METRIC_SCHEMA_VERSION,
                        "contract_revision": (
                            "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
                        ),
                        "campaign_signature": campaign_signature,
                        "engine_sha256": engine_sha,
                        "case_key": baseline_key,
                        "case_signature": baseline_signature,
                        "operating_point_id": "op_80",
                        "seed": seed,
                        "stage": "baseline",
                        "shard_id": shard_id,
                        "status": "valid",
                        "valid": True,
                        "validation_errors": [],
                        "quality_branch_included": False,
                        "availability_incident_included": False,
                        "supplier_state_dependent_risks_enabled": False,
                        "metrics": {"warmup_core_state_sha256": "c" * 64},
                    },
                )
            incident_key = f"op_80__{lane_id}__{mechanism}__seed_{seed}"
            incident_signature = subject._stable_sha256(
                {"kind": "incident", "mechanism": mechanism, "seed": seed}
            )
            risk_path = risk_dir / f"{incident_key}.csv"
            risk_path.write_text(
                f"event_id,risk_type\ncase,{mechanism}\n", encoding="utf-8"
            )
            _signed_case(
                evidence_dir / f"{incident_key}.json",
                {
                    "schema_version": subject.INPUT_METRIC_SCHEMA_VERSION,
                    "contract_revision": (
                        "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
                    ),
                    "campaign_signature": campaign_signature,
                    "engine_sha256": engine_sha,
                    "case_key": incident_key,
                    "case_signature": incident_signature,
                    "baseline_case_signature": baseline_signature,
                    "operating_point_id": "op_80",
                    "seed": seed,
                    "stage": "incident",
                    "shard_id": shard_id,
                    "simulation_days": 800,
                    "status": "valid",
                    "valid": True,
                    "validation_errors": [],
                    "quality_branch_included": False,
                    "availability_incident_included": False,
                    "supplier_state_dependent_risks_enabled": False,
                    "lane": {
                        "lane_id": lane_id,
                        "supplier_id": identity[0],
                        "item_id": identity[1],
                        "dst_node_id": identity[2],
                        "edge_id": identity[3],
                        "target_product_id": identity[4],
                    },
                    "mechanism": {"key": mechanism},
                    "incident_proof": {"incident_physically_exercised": True},
                    "risk_csv_sha256": subject._sha256(risk_path),
                    "metrics": {"warmup_core_state_sha256": "c" * 64},
                },
            )
            paired_rows.append(
                {
                    "operating_point_id": "op_80",
                    "mechanism": mechanism,
                    "lane_id": lane_id,
                    "incident_physically_exercised": True,
                    subject.PRIMARY_METRIC: 1.0 + 2.0 * seed_index,
                    "seed": seed,
                    "shard_id": shard_id,
                    "case_key": incident_key,
                    "case_signature": incident_signature,
                    "baseline_case_signature": baseline_signature,
                    "required_simulation_days": 800,
                    "warmup_core_state_sha256": "c" * 64,
                }
            )
    return context, pd.DataFrame(paired_rows), pd.DataFrame(priority_rows), risk_dir


def test_priority_wording_does_not_force_a_top_three() -> None:
    assert subject._priority_status(
        detected=True, robust_probability=0.1, possible_probability=0.5
    ) == "dossier_to_investigate"
    assert subject._priority_status(
        detected=False, robust_probability=1.0, possible_probability=1.0
    ) == "no_detected_effect"


def test_finalizer_pin_matches_frozen_v4_runner() -> None:
    assert subject._sha256(Path(subject.v4_runner.__file__)) == subject.SOURCE_RUNNER_SHA256


def test_backlog_signal_is_separate_from_service_ranking() -> None:
    record = {
        f"{subject.PRIMARY_METRIC}_mean": 0.0,
        f"{subject.PRIMARY_METRIC}_ci95_low": 0.0,
        f"{subject.PRIMARY_METRIC}_positive_effect_count": 0,
        f"{subject.CAUSAL_RANK_METRIC}_mean": 0.0,
        f"{subject.SUPPLEMENTARY_BACKLOG_METRIC}_ci95_low": 0.1,
        f"{subject.SUPPLEMENTARY_BACKLOG_METRIC}_positive_effect_count": 24,
    }
    subject._decorate_rank_group(
        [record],
        [np.zeros(10)],
        [np.zeros(10)],
    )

    assert record["priority_status"] == "supplementary_backlog_signal"
    assert record["model_effect_detected"] is False
    assert record["supplementary_backlog_effect_detected"] is True


def test_lane_statistics_preserve_signed_nonnumeric_seed_order() -> None:
    rows = []
    for index, seed in enumerate(sorted(subject.EXPECTED_SEEDS)):
        row = {
            "operating_point_id": "op_93",
            "mechanism": "transport_delay",
            "target_product_id": "268091",
            "lane_id": "lane_01",
            "seed": seed,
            "operating_point_service_pct": 93.0,
            "operating_point_service_268091_pct": 92.5,
            "operating_point_service_268967_pct": 93.5,
            "operating_point_input_label_pct": 93.0,
            "supplier_id": "SUP-01",
            "item_id": "item:000001",
            "dst_node_id": "M-1810",
            "edge_id": "edge:01",
            "target_uom": "UN",
            "incident_physically_exercised": True,
            "target_planned_qty": 100.0,
            "target_shipment_count": 1,
            "effective_exposure_dose": 50.0,
            "effective_exposure_dose_unit": "UN*day",
            "state_comparison_valid": True,
            "seed_cross_state_exposure_comparable": True,
            "required_comparable_seed_count": 24,
            "causal_window_days": 480,
            "simulation_days": 900,
            "baseline_impact_demand_268091_qty": 100.0,
            "baseline_impact_demand_global_qty": 200.0,
            "baseline_causal_demand_268091_qty": 100.0,
            "baseline_causal_demand_global_qty": 200.0,
        }
        row.update({metric: 1.0 + index / 100.0 for metric in subject.STATISTIC_METRICS})
        rows.append(row)

    statistics, _bootstrap = subject.build_lane_statistics(
        pd.DataFrame(rows), bootstrap_replicates=20
    )

    assert len(statistics) == 1
    assert statistics.iloc[0]["paired_repetition_count"] == 30
    assert tuple(sorted(subject.EXPECTED_SEEDS)) != subject.EXPECTED_SEEDS


def test_lot_replay_selection_is_signed_separate_by_cause_and_representative(tmp_path) -> None:
    context, paired, priorities, _ = _lot_selection_fixture(tmp_path)

    result = subject.build_lot_replay_selection(
        campaign_root=tmp_path,
        context=context,
        paired=paired,
        priority_lanes=priorities,
    )

    assert result["schema_version"].endswith(".lot_replay_selection.v1")
    assert len(result["selected_dossiers"]) == 2
    assert {row["mechanism"] for row in result["selected_dossiers"]} == set(
        subject.MECHANISMS
    )
    assert {
        row["representative_seed"] for row in result["selected_dossiers"]
    } == {subject.EXPECTED_SEEDS[0]}
    assert all(row["cell_median_effect_pp"] == 2.0 for row in result["selected_dossiers"])
    unsigned = dict(result)
    signature = unsigned.pop("selection_signature")
    assert signature == subject._stable_sha256(unsigned)
    assert all(
        not Path(row["incident_evidence_path"]).is_absolute()
        for row in result["selected_dossiers"]
    )
    assert result["selection_contract"]["risk_paths_relative_to_campaign_root"] is True
    assert (
        result["selection_contract"]["supplementary_backlog_signal_eligible"] is False
    )
    assert all(
        not Path(row["risk_csv_path"]).is_absolute()
        for row in result["selected_dossiers"]
    )


def test_lot_replay_selection_fails_if_source_risk_csv_changed(tmp_path) -> None:
    context, paired, priorities, risk_dir = _lot_selection_fixture(tmp_path)
    next(
        risk_dir.glob(f"*seed_{subject.EXPECTED_SEEDS[0]}.csv")
    ).write_text("tampered", encoding="utf-8")

    with pytest.raises(subject.CampaignValidationError, match="physical proof"):
        subject.build_lot_replay_selection(
            campaign_root=tmp_path,
            context=context,
            paired=paired,
            priority_lanes=priorities,
        )


def test_all_metric_rows_are_rebuilt_from_signed_case_evidence(
    tmp_path, monkeypatch
) -> None:
    fields = ("case_key", "shard_id", "case_signature", "value")
    monkeypatch.setattr(subject, "EXPECTED_TOTAL_COUNT", 2)
    monkeypatch.setattr(subject.v4_runner, "METRIC_FIELDS", fields)
    monkeypatch.setattr(
        subject.v4_runner,
        "_validate_evidence",
        lambda payload, *, manifest, case_key, case_signature: None,
    )
    monkeypatch.setattr(
        subject.v4_runner,
        "_flatten_metric_row",
        lambda payload, *, baseline_by_signature: payload["rebuilt"],
    )

    shard = tmp_path / "shards" / "s1"
    evidence_dir = shard / "case_evidence"
    risk_dir = shard / "inputs" / "risk_events"
    evidence_dir.mkdir(parents=True)
    risk_dir.mkdir(parents=True)
    baseline_key = "baseline"
    incident_key = "incident"
    baseline_signature = "a" * 64
    incident_signature = "b" * 64
    common = {
        "contract_revision": (
            "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
        ),
        "shard_id": "s1",
        "valid": True,
        "status": "valid",
        "validation_errors": [],
        "metrics": {
            "warmup_core_state_sha256": "c" * 64,
            "summary_sha256": "d" * 64,
        },
    }
    baseline = {
        **common,
        "case_key": baseline_key,
        "case_signature": baseline_signature,
        "stage": "baseline",
        "rebuilt": {
            "case_key": baseline_key,
            "shard_id": "s1",
            "case_signature": baseline_signature,
            "value": "10.0",
        },
    }
    risk_path = risk_dir / f"{incident_key}.csv"
    risk_path.write_text("event_id\nincident\n", encoding="utf-8")
    incident = {
        **common,
        "case_key": incident_key,
        "case_signature": incident_signature,
        "stage": "incident",
        "risk_csv_sha256": subject._sha256(risk_path),
        "rebuilt": {
            "case_key": incident_key,
            "shard_id": "s1",
            "case_signature": incident_signature,
            "value": "20.0",
        },
    }
    subject._write_json(evidence_dir / f"{baseline_key}.json", baseline)
    subject._write_json(evidence_dir / f"{incident_key}.json", incident)
    metrics_path = shard / "campaign_metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows((baseline["rebuilt"], incident["rebuilt"]))

    result = subject.validate_metrics_against_signed_case_evidence(
        campaign_root=tmp_path,
        metrics_paths=(metrics_path,),
        manifest={},
    )
    assert result["status"] == "complete_reconstructed"
    assert result["case_count"] == 2

    with metrics_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            (
                baseline["rebuilt"],
                {**incident["rebuilt"], "value": "999.0"},
            )
        )
    with pytest.raises(subject.CampaignValidationError, match="differs from signed"):
        subject.validate_metrics_against_signed_case_evidence(
            campaign_root=tmp_path,
            metrics_paths=(metrics_path,),
            manifest={},
        )
