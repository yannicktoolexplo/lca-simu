import csv
import json
from pathlib import Path

from etudecas.visualization.maps.scan_dashboard_payload import (
    SCAN_DASHBOARD_SCHEMA_VERSION,
    build_scan_dashboard_payload,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_scan_dashboard_is_unavailable_without_manifest(tmp_path: Path) -> None:
    payload = build_scan_dashboard_payload(tmp_path)

    assert payload == {
        "schema_version": SCAN_DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": "scan_results_not_provided",
        "html": "",
        "figure_count": 0,
    }


def test_scan_dashboard_builds_self_contained_summary_and_curves(tmp_path: Path) -> None:
    manifest = {
        "schema_version": "scan.end_2026.validation.v1",
        "source": {
            "mode": "etudecas_baseline",
            "days": 90,
            "baseline_origin": "etudecas_case_simulation_output",
            "baseline_industrial_status": "non_industrial",
        },
        "provenance": {"forecast_origin": "synthetic_prediction_poc"},
        "prediction_to_physics": {
            "granular_pairs": 30,
            "granular_physical_rows": 2700,
            "forecast_validity_days": 30,
        },
        "canonical_replay": {
            "successful_runs": 7,
            "expected_runs": 7,
            "derived_oracle_rows": 1,
            "risk_event_count": 18,
        },
        "rci_business_validation": {
            "status": "pending_business_review",
            "pack_episode_count": 58,
            "selected_episode_count": 13,
        },
        "limitations": ["Exploratory evidence only."],
    }
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_csv(
        tmp_path / "data" / "paired_policy_runs.csv",
        [
            {"seed": 1, "policy": "mrp_reference"},
            {"seed": 1, "policy": "adaptive"},
            {"seed": 2, "policy": "mrp_reference"},
            {"seed": 2, "policy": "adaptive"},
        ],
    )
    _write_csv(
        tmp_path / "data" / "paired_policy_summary.csv",
        [
            {
                "policy": "adaptive",
                "mean_delta_score": -2,
                "mean_delta_service_loss": -1,
                "mean_delta_backlog_area": -3,
                "mean_delta_nervousness": -0.2,
                "mean_delta_risk_creation": -0.4,
                "win_rate_vs_mrp_service_loss": 0.75,
            }
        ],
    )
    _write_csv(
        tmp_path / "data" / "canonical_runs.csv",
        [
            {
                "policy": "adaptive",
                "run_kind": "physical_replay",
                "status": "ok",
                "mean_service": 0.97,
                "service_loss": 0,
                "backlog_area_days": 0.4,
                "canonical_risk_creation_proxy": 1.2,
                "recovery_status": "observed",
            }
        ],
    )
    _write_csv(
        tmp_path / "data" / "forecast_confusion_summary.csv",
        [
            {
                "case": "TP",
                "runs": 5,
                "mean_service_loss": 1,
                "mean_backlog_area": 2,
                "mean_total_cost_proxy": 3,
                "response_intensity": 0.8,
            }
        ],
    )
    _write_csv(
        tmp_path / "data" / "regime_calibration_evidence.csv",
        [
            {
                "regime": "NOMINAL",
                "anchor_count": 72,
                "confidence": "high",
                "separation": 0.3,
                "label_provenance": "pseudo_labels_only",
            }
        ],
    )
    _write_csv(
        tmp_path
        / "canonical_replay"
        / "adaptive"
        / "seed_1"
        / "data"
        / "canonical_supplier_risk_event_validation.csv",
        [{"matched": "true", "applied": "true", "status": "affected_nonzero_flow"}],
    )
    plot_path = tmp_path / "plots" / "regime_timeline.png"
    plot_path.parent.mkdir(parents=True)
    plot_path.write_bytes(b"\x89PNG\r\n\x1a\nscan-test")

    payload = build_scan_dashboard_payload(tmp_path)
    payload_with_explicit_legacy_defaults = build_scan_dashboard_payload(
        tmp_path,
        None,
        None,
        None,
    )

    assert payload["available"] is True
    assert payload_with_explicit_legacy_defaults == payload
    assert payload["status"] == "ready"
    assert payload["figure_count"] == 1
    assert payload["metrics"]["paired_seed_count"] == 2
    assert payload["metrics"]["paired_run_count"] == 4
    assert payload["metrics"]["canonical_nonzero_validation_count"] == 1
    assert 'data-scan-dashboard-tab="summary"' in payload["html"]
    assert 'data-scan-dashboard-tab="curves"' in payload["html"]
    assert "75.0%" in payload["html"]
    assert "En attente" in payload["html"]
    assert "data:image/png;base64," in payload["html"]
    assert str(tmp_path) not in payload["html"]
    assert 'data-scan-dashboard-tab="closed-loop-v2"' not in payload["html"]
    assert "closed_loop_v2_available" not in payload["metrics"]
    assert 'data-scan-dashboard-tab="frequency"' not in payload["html"]
    assert "frequency_available" not in payload["metrics"]

    closed_loop_root = tmp_path / "closed_loop_campaign"
    (closed_loop_root / "canonical_closed_loop_manifest.json").parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    (closed_loop_root / "canonical_closed_loop_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_closed_loop_campaign.v1",
                "paired_seed_count": 1,
                "true_state_feedback_count": 1,
                "all_feedback_runs_confirmed_by_engine": True,
                "seeds": [1],
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        closed_loop_root / "canonical_closed_loop_paired_deltas.csv",
        [
            {
                "seed": 1,
                "true_state_feedback": True,
                "delta_vs_mrp_service": 0,
                "delta_vs_mrp_backlog_area_days": 0,
                "delta_vs_mrp_mean_inventory_days": 12.5,
                "delta_vs_mrp_order_nervousness": 3.2,
                "delta_vs_mrp_supplier_risk_area": -0.2,
                "delta_vs_mrp_total_economic_exposure": 42,
            }
        ],
    )
    provider_summary = (
        closed_loop_root
        / "canonical_feedback"
        / "seed_1"
        / "summaries"
        / "first_simulation_summary.json"
    )
    provider_summary.parent.mkdir(parents=True, exist_ok=True)
    provider_summary.write_text(
        json.dumps(
            {
                "policy": {
                    "control_provider": {
                        "closed_loop_claimed": True,
                        "observation_causal_contract_satisfied": True,
                        "controller_observation_forecast_lookahead_days": 0,
                        "future_realization_access": False,
                        "physically_applied_action_count": 7,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (closed_loop_root / "canonical_closed_loop_comparison.png").write_bytes(
        b"\x89PNG\r\n\x1a\nclosed-loop-test"
    )

    combined = build_scan_dashboard_payload(tmp_path, closed_loop_root)
    combined_with_explicit_no_v2 = build_scan_dashboard_payload(
        tmp_path,
        closed_loop_root,
        None,
    )

    assert combined_with_explicit_no_v2 == combined
    assert combined["figure_count"] == 2
    assert combined["metrics"]["closed_loop_available"] is True
    assert combined["metrics"]["closed_loop_true_feedback_count"] == 1
    assert combined["metrics"]["closed_loop_causal_contract_confirmed"] is True
    assert 'data-scan-dashboard-tab="closed-loop"' in combined["html"]
    assert 'data-scan-dashboard-pane="closed-loop"' in combined["html"]
    assert "J vers J+1" in combined["html"]
    assert "look-ahead nul" in combined["html"]
    assert "7" in combined["html"]
    assert str(closed_loop_root) not in combined["html"]
    assert 'data-scan-dashboard-tab="closed-loop-v2"' not in combined["html"]

    closed_loop_v2_root = tmp_path / "closed_loop_v2_campaign"
    closed_loop_v2_root.mkdir(parents=True)
    (closed_loop_v2_root / "canonical_closed_loop_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_closed_loop_campaign.v1",
                "paired_seed_count": 2,
                "true_state_feedback_count": 2,
                "all_feedback_runs_confirmed_by_engine": True,
                "seeds": [41, 42],
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        closed_loop_v2_root / "canonical_closed_loop_paired_deltas.csv",
        [
            {
                "seed": seed,
                "true_state_feedback": True,
                "delta_vs_mrp_service": 0.001,
                "delta_vs_mrp_backlog_area_days": -0.2,
                "delta_vs_mrp_mean_inventory_days": -3.0,
                "delta_vs_mrp_order_nervousness": -1.5,
                "delta_vs_mrp_supplier_risk_area": -0.1,
                "delta_vs_mrp_total_economic_exposure": -12.0,
            }
            for seed in (41, 42)
        ],
    )
    v2_provider_summary = (
        closed_loop_v2_root
        / "canonical_feedback_v2"
        / "seed_41"
        / "summaries"
        / "first_simulation_summary.json"
    )
    v2_provider_summary.parent.mkdir(parents=True)
    v2_provider_summary.write_text(
        json.dumps(
            {
                "policy": {
                    "control_provider": {
                        "closed_loop_claimed": True,
                        "observation_causal_contract_satisfied": True,
                        "controller_observation_forecast_lookahead_days": 0,
                        "future_realization_access": False,
                        "physically_applied_action_count": 11,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (closed_loop_v2_root / "canonical_closed_loop_v2_protocol.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_closed_loop_v2_protocol.v1",
                "phase": "holdout_validation",
                "warmup_days": 60,
                "train_seeds": [1, 2, 3],
                "validation_seeds": [41, 42],
                "opening_state_match_all": True,
                "costly_gate_violation_count": 0,
                "selected_policy_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    # A V2 package may deliberately retain the V1 artifact names.
    (closed_loop_v2_root / "canonical_closed_loop_comparison.png").write_bytes(
        b"\x89PNG\r\n\x1a\nclosed-loop-v2-test"
    )

    with_v2 = build_scan_dashboard_payload(
        tmp_path,
        closed_loop_root,
        closed_loop_v2_root,
    )

    assert with_v2["figure_count"] == 3
    assert with_v2["metrics"]["closed_loop_v2_available"] is True
    assert with_v2["metrics"]["closed_loop_v2_paired_seed_count"] == 2
    assert with_v2["metrics"]["closed_loop_v2_true_feedback_count"] == 2
    assert (
        with_v2["metrics"]["closed_loop_v2_causal_contract_confirmed"]
        is True
    )
    assert with_v2["metrics"]["closed_loop_v2_protocol_available"] is True
    assert 'data-scan-dashboard-tab="closed-loop"' in with_v2["html"]
    assert 'data-scan-dashboard-pane="closed-loop"' in with_v2["html"]
    assert 'data-scan-dashboard-tab="closed-loop-v2"' in with_v2["html"]
    assert 'data-scan-dashboard-pane="closed-loop-v2"' in with_v2["html"]
    assert "Closed-Loop V2" in with_v2["html"]
    assert "60 jours" in with_v2["html"]
    assert "3 / 2 graines; disjoints" in with_v2["html"]
    assert "abc123" in with_v2["html"]
    assert str(closed_loop_v2_root) not in with_v2["html"]

    wrapper_root = tmp_path / "closed_loop_v2_protocol_root"
    wrapper_root.mkdir()
    (wrapper_root / "canonical_closed_loop_v2_protocol.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_closed_loop_v2_protocol.v1",
                "status": "partial_validation_only",
                "config": {
                    "sha256_frozen_before_execution": "frozen-v2-sha",
                },
                "warm_start_contract": {
                    "physical_warmup_days": 60,
                },
                "seed_protocol": {
                    "training": list(range(10)),
                    "validation": list(range(100, 130)),
                    "disjoint": True,
                },
                "executed_splits": ["validation"],
                "gate_audit": {"violation_count": 0},
                "burn_in_stability": {
                    "status": "stability_not_demonstrated",
                },
                "splits": {
                    "validation": {
                        "output_dir": str(closed_loop_v2_root),
                        "all_boundary_hashes_match": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    from_wrapper_root = build_scan_dashboard_payload(
        tmp_path,
        closed_loop_root,
        wrapper_root,
    )
    assert from_wrapper_root["metrics"]["closed_loop_v2_available"] is True
    assert (
        from_wrapper_root["metrics"]["closed_loop_v2_paired_seed_count"]
        == 2
    )
    assert (
        from_wrapper_root["metrics"]["closed_loop_v2_protocol_available"]
        is True
    )
    assert 'data-scan-dashboard-tab="closed-loop-v2"' in from_wrapper_root[
        "html"
    ]
    assert "10 / 30 graines; disjoints" in from_wrapper_root["html"]
    assert "frozen-v2-sha" in from_wrapper_root["html"]
    assert "stability_not_demonstrated" in from_wrapper_root["html"]

    invalid_v2 = build_scan_dashboard_payload(
        tmp_path,
        closed_loop_root,
        tmp_path / "missing_v2_campaign",
    )
    assert invalid_v2["metrics"]["closed_loop_v2_available"] is False
    assert 'data-scan-dashboard-tab="closed-loop-v2"' not in invalid_v2["html"]

    frequency_root = tmp_path / "frequency_campaign"
    frequency_root.mkdir()
    (frequency_root / "canonical_frequency_protocol.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_frequency_protocol.v1",
                "sample_period_days": 1,
                "measured_days": 720,
                "coherence_threshold": 0.7,
                "global_stability_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        frequency_root / "canonical_frequency_response.csv",
        [
            {
                "policy": "canonical_feedback_v2",
                "regime": "NOMINAL",
                "input_signal": "demand_probe",
                "output_signal": "orders",
                "frequency_cpd": 0.05,
                "magnitude_db": -1.0,
                "phase_deg": -25.0,
                "coherence": 0.9,
                "valid_bin": True,
            }
        ],
    )
    _write_csv(
        frequency_root / "canonical_frequency_resonances.csv",
        [
            {
                "policy": "canonical_feedback_v2",
                "regime": "NOMINAL",
                "input_signal": "demand_probe",
                "output_signal": "orders",
                "peak_frequency_cpd": 0.05,
                "peak_period_days": 20,
                "peak_gain_db": -1.0,
                "peak_coherence": 0.9,
            }
        ],
    )
    _write_csv(
        frequency_root / "canonical_frequency_stability.csv",
        [
            {
                "policy": "canonical_feedback_v2",
                "regime": "NOMINAL",
                "spectral_radius": 0.8,
                "locally_stable": True,
                "gain_margin_db": 8,
                "phase_margin_deg": 45,
                "quality_status": "identified",
            }
        ],
    )
    (frequency_root / "canonical_frequency_bode_frf.png").write_bytes(
        b"\x89PNG\r\n\x1a\nfrequency-test"
    )

    with_frequency = build_scan_dashboard_payload(
        tmp_path,
        closed_loop_root,
        closed_loop_v2_root,
        frequency_root,
    )

    assert with_frequency["figure_count"] == 4
    assert with_frequency["metrics"]["frequency_available"] is True
    assert (
        with_frequency["metrics"]["frequency_claim_scope"]
        == "empirical_tested_amplitude_regime_conditioned_active_set_unverified"
    )
    assert (
        with_frequency["metrics"]["frequency_global_stability_claimed"]
        is False
    )
    assert 'data-scan-dashboard-tab="closed-loop"' in with_frequency["html"]
    assert 'data-scan-dashboard-tab="closed-loop-v2"' in with_frequency["html"]
    assert 'data-scan-dashboard-tab="frequency"' in with_frequency["html"]
    assert 'data-scan-dashboard-pane="frequency"' in with_frequency["html"]
    assert "Analyse fréquentielle" in with_frequency["html"]
    assert "ni une réponse locale linéaire, ni une preuve de stabilité globale" in with_frequency[
        "html"
    ]
    assert str(frequency_root) not in with_frequency["html"]

    invalid_frequency = build_scan_dashboard_payload(
        tmp_path,
        closed_loop_root,
        closed_loop_v2_root,
        tmp_path / "missing_frequency_campaign",
    )
    assert invalid_frequency["metrics"]["frequency_available"] is False
    assert 'data-scan-dashboard-tab="frequency"' not in invalid_frequency["html"]
    assert 'data-scan-dashboard-tab="closed-loop-v2"' in invalid_frequency["html"]

    missing_lookahead = json.loads(provider_summary.read_text(encoding="utf-8"))
    missing_lookahead["policy"]["control_provider"].pop(
        "controller_observation_forecast_lookahead_days"
    )
    provider_summary.write_text(
        json.dumps(missing_lookahead),
        encoding="utf-8",
    )
    unconfirmed = build_scan_dashboard_payload(tmp_path, closed_loop_root)
    assert (
        unconfirmed["metrics"]["closed_loop_causal_contract_confirmed"]
        is False
    )
    assert "n'est pas confirme" in unconfirmed["html"]


def test_worldmap_cli_accepts_optional_closed_loop_v2_results_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from etudecas.visualization.maps.build_supplychain_worldmap import parse_args

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_supplychain_worldmap.py",
            "--closed-loop-v2-results-dir",
            str(tmp_path),
            "--scan-frequency-results-dir",
            str(tmp_path / "frequency"),
        ],
    )

    args = parse_args()

    assert args.closed_loop_v2_results_dir == str(tmp_path)
    assert args.scan_frequency_results_dir == str(tmp_path / "frequency")
