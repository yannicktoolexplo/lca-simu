from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_aggregator_v4 as aggregator,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v4_final_standalone_delivery as delivery,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_operating_point_full_campaign_v4_dashboard as dashboard_fixture,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signed(payload: dict[str, object], field: str) -> dict[str, object]:
    return {**payload, field: delivery.stable_sha256(payload)}


def _campaign_fixture(
    tmp_path: Path, *, selected_count: int = 1
) -> tuple[Path, Path, Path]:
    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    results, registry = dashboard_fixture._make_results_fixture(tmp_path)
    validation_path = results / "campaign_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["expected_contract"].update(
        {
            "operating_point_count": 3,
            "lane_count": 18,
            "baseline_row_count": 90,
            "incident_row_count": 3240,
        }
    )
    validation["comparability_checks"][
        "all_3330_metrics_reconstructed_from_signed_case_evidence"
    ] = True
    if selected_count == 0:
        lot_path = results / "lot_replay_plan.json"
        lot_plan = json.loads(lot_path.read_text(encoding="utf-8"))
        lot_plan.pop("selection_signature")
        lot_plan["selected_dossiers"] = []
        lot_plan = _signed(lot_plan, "selection_signature")
        _write_json(lot_path, lot_plan)
        for entry in (
            validation["lot_replay_plan"],
            validation["outputs"]["lot_replay_plan.json"],
        ):
            entry.update(
                {
                    "sha256": _sha(lot_path),
                    "row_count": 0,
                    "selection_signature": lot_plan["selection_signature"],
                }
            )
    _write_json(validation_path, validation)
    return campaign_root, results, registry


def _curve_rows(domain: str) -> list[dict[str, object]]:
    definitions: list[tuple[str, int, list[tuple[str, str]], str]]
    if domain == "service":
        definitions = [
            (
                "on_due_service_ratio",
                28,
                [("C-XXXXX", "item:268091"), ("C-XXXXX", "item:268967")],
                "ratio_0_1",
            ),
            (
                "backlog_end_qty",
                0,
                [("C-XXXXX", "item:268091"), ("C-XXXXX", "item:268967")],
                "UN",
            ),
            (
                "backlog_end_qty",
                7,
                [("C-XXXXX", "item:268091"), ("C-XXXXX", "item:268967")],
                "UN",
            ),
        ]
    elif domain == "production":
        entities = [("M-1810", "item:268091"), ("M-1430", "item:268967")]
        definitions = [
            ("released_qty", 28, entities, "UN_par_jour"),
            ("wip_end_qty", 0, entities, "UN"),
            ("wip_end_qty", 7, entities, "UN"),
            ("finished_stock_end_qty", 0, entities, "UN"),
            ("finished_stock_end_qty", 7, entities, "UN"),
        ]
    elif domain == "input_stock":
        definitions = [
            ("input_stock_end_qty", 0, [("M-1810", "item:338929")], "UN"),
            ("input_stock_end_qty", 7, [("M-1810", "item:338929")], "UN"),
        ]
    else:
        return []
    rows: list[dict[str, object]] = []
    for state_index, state in enumerate(delivery.EXPECTED_STATES):
        for metric, window, entities, unit in definitions:
            for node, item in entities:
                for day in range(delivery.EXPECTED_HORIZON_DAYS):
                    start = max(0, window - 1)
                    complete = day >= start
                    if metric == "on_due_service_ratio":
                        median = 0.99 - state_index * 0.08
                        spread = 0.005
                    else:
                        median = 100 + state_index * 10 + day % 29
                        spread = 5.0
                    rows.append(
                        {
                            "target_group": state,
                            "candidate_id": f"candidate-{state}",
                            "day": day,
                            "node_id": node,
                            "item_id": item,
                            "metric": metric,
                            "unit": unit,
                            "rolling_window_days": window,
                            "sample_count": 30 if complete else 0,
                            "p10": median - spread if complete else "",
                            "median": median if complete else "",
                            "p90": median + spread if complete else "",
                        }
                    )
    return rows


def _curves_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = tmp_path / "curves"
    aggregate_root = root / aggregator.AGGREGATE_SUBDIRECTORY
    aggregate_root.mkdir(parents=True)
    files: list[dict[str, object]] = []
    for domain in ("service", "production", "input_stock", "constraint"):
        rows = _curve_rows(domain)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(aggregator.OUTPUT_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
        path = aggregate_root / f"{domain}_quantiles_daily.csv.gz"
        path.write_bytes(
            gzip.compress(stream.getvalue().encode("utf-8"), compresslevel=9, mtime=0)
        )
        files.append(
            {
                "domain": domain,
                "path": str(path.resolve()),
                "sha256": _sha(path),
                "row_count": len(rows),
            }
        )
    unsigned: dict[str, object] = {
        "schema_version": aggregator.MANIFEST_SCHEMA_VERSION,
        "aggregate_contract_signature": "a" * 64,
        "output_schema_version": aggregator.OUTPUT_SCHEMA_VERSION,
        "status": "complete",
        "state_count": 3,
        "case_count": 90,
        "horizon_days": 720,
        "files": files,
    }
    manifest = _signed(unsigned, "manifest_signature")
    _write_json(aggregate_root / "aggregate_manifest.json", manifest)
    validation = {
        "valid": True,
        "manifest_signature": manifest["manifest_signature"],
        "case_count": 90,
        "state_count": 3,
        "file_count": 4,
    }
    return root, validation


TRACE_SCHEMAS = {
    "shipment_to_mp_lots.csv": (
        "shipment_id",
        "risk_decision_day",
        "receipt_lot_id",
        "receipt_item_id",
    ),
    "exposed_consumption_wip.csv": (
        "shipment_ids",
        "material_lot_id",
        "campaign_id",
        "batch_id",
    ),
    "exposed_finished_lots.csv": ("shipment_ids", "finished_lot_id", "day"),
    "exposed_client_events.csv": (
        "shipment_ids",
        "client_lot_id",
        "client_node_id",
        "day",
    ),
}


def _replay_fixture(
    tmp_path: Path, *, campaign_root: Path, results: Path
) -> tuple[Path, dict[str, object]]:
    root = tmp_path / "replay"
    dossier_id = "dossier_fixture"
    plan: dict[str, object] = {
        "campaign_root": str(campaign_root.resolve()),
        "results_dir": str(results.resolve()),
        "plan_signature": "b" * 64,
        "dossiers": [
            {
                "dossier_id": dossier_id,
                "seed": 17,
                "priority": {
                    "operating_point_id": "op_93",
                    "mechanism": "transport_delay",
                    "supplier_id": "S-338",
                    "lane_id": "lane-338",
                    "item_id": "338929",
                    "dst_node_id": "M-1810",
                    "target_product_id": "268091",
                },
                "incident_metric": {
                    "representative_valid_exercised_seed_count": 27,
                },
            }
        ],
    }
    receipt = _signed(
        {
            "schema_version": delivery.lot_replay.RUN_RECEIPT_SCHEMA_VERSION,
            "status": "complete_validated",
            "plan_signature": plan["plan_signature"],
        },
        "run_receipt_signature",
    )
    _write_json(root / "replay_run_receipt.json", receipt)
    dossier_root = root / "finalized" / "dossiers" / dossier_id
    _write_csv(
        dossier_root / "shipment_to_mp_lots.csv",
        [
            {
                "shipment_id": "incident::SHIP-1",
                "risk_decision_day": 120,
                "receipt_lot_id": "incident::MP-1",
                "receipt_item_id": "item:338929",
            }
        ],
        TRACE_SCHEMAS["shipment_to_mp_lots.csv"],
    )
    _write_csv(
        dossier_root / "exposed_consumption_wip.csv",
        [
            {
                "shipment_ids": "incident::SHIP-1",
                "material_lot_id": "incident::MP-1",
                "campaign_id": "incident::CAM-1",
                "batch_id": "incident::BATCH-1",
            }
        ],
        TRACE_SCHEMAS["exposed_consumption_wip.csv"],
    )
    _write_csv(
        dossier_root / "exposed_finished_lots.csv",
        [
            {
                "shipment_ids": "incident::SHIP-1",
                "finished_lot_id": "incident::PF-1",
                "day": 150,
            }
        ],
        TRACE_SCHEMAS["exposed_finished_lots.csv"],
    )
    _write_csv(
        dossier_root / "exposed_client_events.csv",
        [
            {
                "shipment_ids": "incident::SHIP-1",
                "client_lot_id": "incident::CLIENT-LOT-1",
                "client_node_id": "C-XXXXX",
                "day": 160,
            }
        ],
        TRACE_SCHEMAS["exposed_client_events.csv"],
    )
    curve_fields = (
        "day",
        "metric",
        "baseline_value",
        "incident_value",
        "delta_incident_minus_baseline",
    )
    curve_rows = []
    for metric in (
        "component_stock",
        "production_released",
        "wip",
        "served_on_due",
        "backlog",
    ):
        for day in range(5):
            baseline = float(100 + day)
            incident = baseline - 10 if metric != "backlog" else baseline + 10
            curve_rows.append(
                {
                    "day": day,
                    "metric": metric,
                    "baseline_value": baseline,
                    "incident_value": incident,
                    "delta_incident_minus_baseline": incident - baseline,
                }
            )
    _write_csv(dossier_root / "paired_daily_curves.csv", curve_rows, curve_fields)
    lag_fields = (
        "baseline_volume_fraction",
        "threshold_qty",
        "baseline_reach_day",
        "incident_reach_day",
        "lag_days",
        "status",
    )
    _write_csv(
        dossier_root / "cumulative_release_lag.csv",
        [
            {
                "baseline_volume_fraction": 0.5,
                "threshold_qty": 500,
                "baseline_reach_day": 140,
                "incident_reach_day": 146,
                "lag_days": 6,
                "status": "calculated",
            }
        ],
        lag_fields,
    )
    _write_json(
        dossier_root / "dossier_kpis.json",
        {
            "service_loss_pp": 2.4,
            "on_due_units_lost": 1200,
            "production_released_loss_qty": 900,
            "backlog_recovery_day": 210,
        },
    )
    standalone = root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html"
    standalone.write_text("<!doctype html><title>fixture</title>", encoding="utf-8")
    artifact_paths = sorted(
        [path for path in (root / "finalized").rglob("*") if path.is_file()]
        + [standalone]
    )
    inventory_rows = [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in artifact_paths
    ]
    inventory = root / "finalized" / "artifact_inventory.csv"
    _write_csv(
        inventory,
        inventory_rows,
        ("relative_path", "size_bytes", "sha256"),
    )
    replay_validation = _signed(
        {
            "schema_version": delivery.lot_replay.VALIDATION_SCHEMA_VERSION,
            "status": "complete_validated",
            "plan_signature": plan["plan_signature"],
            "run_receipt_signature": receipt["run_receipt_signature"],
            "dossiers": [
                {
                    "dossier_id": dossier_id,
                    "status": "native_trace_to_client",
                    "trace_counts": {
                        "shipments": 1,
                        "material_receipts": 1,
                        "consumptions": 1,
                        "campaigns": 1,
                        "batches": 1,
                        "finished_lots": 1,
                        "client_events": 1,
                        "clients": 1,
                    },
                }
            ],
            "artifact_inventory": str(inventory.resolve()),
            "artifact_inventory_sha256": _sha(inventory),
            "standalone_html": str(standalone.resolve()),
            "standalone_html_sha256": _sha(standalone),
            "lot_identity_contract": {
                "ids_are_run_local": True,
                "cross_arm_lot_id_matching_allowed": False,
            },
        },
        "validation_signature",
    )
    _write_json(root / "finalized" / "replay_validation.json", replay_validation)
    return root, plan


def _action_fixture(
    tmp_path: Path,
    *,
    campaign_payload: dict[str, object],
    campaign_binding: dict[str, object],
) -> tuple[Path, dict[str, object], dict[str, object]]:
    dossier = campaign_payload["lotSelection"]["dossiers"][0]
    root = tmp_path / "actions"
    root.mkdir()
    paired_seeds = list(range(30))
    measurement_windows = {
        "impact_service": {
            "metric_ids": ["service_gain_pp"],
            "day_count": 360,
            "ranges": [
                {
                    "dossier_id": dossier["dossierId"],
                    "seed": seed,
                    "start_day": 180,
                    "end_day": 539,
                    "day_count": 360,
                }
                for seed in paired_seeds
            ],
        },
        "state": {
            "metric_ids": [
                "state_window_service_gain_pp",
                "backlog_qty_days_avoided",
                "production_released_gain_qty",
            ],
            "start_day": 0,
            "end_day": 719,
            "day_count": 720,
        },
    }
    summary: dict[str, object] = {
        "schema_version": ("etudecas.supplier_priority_action_replay.v4.summary.v1"),
        "status": "complete_validated",
        "campaign_signature": campaign_binding["campaign_signature"],
        "plan_signature": "plan-action-fixture",
        "summary_signature": "summary-action-fixture",
        "reference_mode": "signed_reference",
        "reference_engine_rerun_count": 0,
        "executed_engine_arm_type": "incident_with_action_only",
        "bootstrap": {"historical_probability": False},
        "measurement_windows": measurement_windows,
        "action_summary_count": 2,
        "refused_action_count": 1,
        "action_results": [
            {
                "dossier_id": dossier["dossierId"],
                "operating_point_id": dossier["state"],
                "mechanism": dossier["mechanism"],
                "lane_id": dossier["lane"],
                "supplier_id": dossier["supplier"],
                "item_id": dossier["item"],
                "dst_node_id": dossier["destination"],
                "target_product_id": dossier["targetProduct"],
                "action_id": "prepositioned_free_stock_j0",
                "action_label_fr": "Stock libre ciblé à J0",
                "client_scope": "C-XXXXX",
                "closed_loop": False,
                "recommendation_claimed": False,
                "paired_seed_count": 30,
                "paired_seeds": paired_seeds,
                "physically_exercised_seed_count": 24,
                "non_exercised_seed_count": 6,
                "status": "estimated_on_physically_exercised_seeds",
                "gain_statistics_population": (
                    "physically_exercised_paired_seeds_only"
                ),
                "paired_arms": {
                    "without_incident": "signed_v4_campaign_reference",
                    "incident_without_action": "signed_v4_campaign_reference",
                    "incident_with_action": "executed_action_arm",
                    "reference_engine_rerun_count": 0,
                },
                "action_parameters": {"stock_scale": 1.25},
                "action_physical_scope": {"day": 0},
                "cost_interpretation": {
                    "complete_intervention_cost": False,
                    "roi_calculable": False,
                },
                "gain_statistics": {
                    "service_gain_pp": {
                        "count": 24,
                        "mean": 1.6,
                        "median": 1.5,
                        "p10": 0.4,
                        "p90": 2.6,
                        "mean_ci95_low": 1.0,
                        "mean_ci95_high": 2.2,
                    },
                    "state_window_service_gain_pp": {
                        "count": 24,
                        "mean": 1.2,
                        "median": 1.1,
                        "p10": 0.2,
                        "p90": 2.1,
                        "mean_ci95_low": 0.7,
                        "mean_ci95_high": 1.7,
                    },
                    "backlog_qty_days_avoided": {
                        "count": 24,
                        "mean": 1200,
                        "median": 1100,
                        "p10": 200,
                        "p90": 2100,
                        "mean_ci95_low": 700,
                        "mean_ci95_high": 1700,
                    },
                    "production_released_gain_qty": {
                        "count": 24,
                        "mean": 800,
                        "median": 700,
                        "p10": 100,
                        "p90": 1500,
                        "mean_ci95_low": 400,
                        "mean_ci95_high": 1200,
                    },
                },
                "limits_fr": "Coût d'acquisition non fourni.",
            },
            {
                "dossier_id": dossier["dossierId"],
                "operating_point_id": dossier["state"],
                "mechanism": dossier["mechanism"],
                "lane_id": dossier["lane"],
                "supplier_id": dossier["supplier"],
                "item_id": dossier["item"],
                "dst_node_id": dossier["destination"],
                "target_product_id": dossier["targetProduct"],
                "action_id": "future_departures_lead_reduction",
                "action_label_fr": "Réduction du délai des futurs départs",
                "client_scope": "C-XXXXX",
                "closed_loop": False,
                "recommendation_claimed": False,
                "paired_seed_count": 30,
                "paired_seeds": paired_seeds,
                "physically_exercised_seed_count": 0,
                "non_exercised_seed_count": 30,
                "status": "non_exercised_no_gain_estimate",
                "gain_statistics_population": (
                    "physically_exercised_paired_seeds_only"
                ),
                "paired_arms": {
                    "without_incident": "signed_v4_campaign_reference",
                    "incident_without_action": "signed_v4_campaign_reference",
                    "incident_with_action": "executed_action_arm",
                    "reference_engine_rerun_count": 0,
                },
                "action_parameters": {"lead_reduction_days": 14},
                "action_physical_scope": {"future_departures_only": True},
                "cost_interpretation": {
                    "complete_intervention_cost": False,
                    "roi_calculable": False,
                },
                "gain_statistics": {},
                "limits_fr": "Aucun futur départ touché dans ce cas.",
            },
        ],
        "refused_actions": [
            {
                "dossier_id": dossier["dossierId"],
                "action_id": "named_shipment_transport",
                "label_fr": "Transport d'une expédition nommée",
                "status": "refused_not_simulated",
                "simulated": False,
                "refusal_reason": "L'actionneur physique n'existe pas.",
                "limits_fr": "Aucun gain n'est annoncé.",
            }
        ],
    }
    validation: dict[str, object] = {
        "schema_version": ("etudecas.supplier_priority_action_replay.v4.validation.v1"),
        "status": "complete_validated",
        "campaign_signature": campaign_binding["campaign_signature"],
        "validation_signature": "validation-action-fixture",
        "measurement_windows": measurement_windows,
        "checks": {
            "all_source_hashes_revalidated": True,
            "all_commands_revalidated": True,
            "all_planned_arms_validated": True,
            "signed_reference_triplets_paired_by_seed": True,
            "reference_engine_rerun_count": 0,
            "only_incident_with_action_arms_executed": True,
            "demand_identical_within_each_triplet": True,
            "actions_kept_separate": True,
            "non_exercised_seeds_excluded_from_gain_statistics": True,
            "refused_actions_not_simulated": True,
            "state_dependent_risks_disabled": True,
            "quality_incident_or_action_absent": True,
            "capacity_or_availability_not_invented": True,
            "named_shipment_actuator_absent": True,
            "unavailable_reference_curve_kpis_are_null": True,
            "closed_loop_claimed": False,
            "complete_cost_or_roi_claimed": False,
        },
    }
    _write_json(root / "action_replay_summary.json", summary)
    _write_json(root / "action_replay_validation.json", validation)
    return root, summary, validation


def test_builds_three_view_offline_delivery_from_synthetic_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path)
    curves, curve_validation = _curves_fixture(tmp_path)
    replay_root, replay_plan = _replay_fixture(
        tmp_path, campaign_root=campaign, results=results
    )
    monkeypatch.setattr(
        delivery.curve_aggregator,
        "validate_aggregates",
        lambda _path: curve_validation,
    )
    monkeypatch.setattr(
        delivery.lot_replay,
        "load_and_validate_plan",
        lambda _path: replay_plan,
    )
    legacy_a = tmp_path / "legacy" / "risks.html"
    legacy_b = tmp_path / "legacy" / "control.html"
    legacy_a.parent.mkdir()
    legacy_a.write_text("old risks", encoding="utf-8")
    legacy_b.write_text("old control", encoding="utf-8")
    output = tmp_path / "delivery" / "OUVRIR_RESILIENCE_SCAN_V4.html"

    manifest = delivery.build_delivery(
        campaign_root=campaign,
        results_dir=results,
        curves_dir=curves,
        replay_root=replay_root,
        target_registry_path=registry,
        legacy_risk_html=legacy_a,
        legacy_control_html=legacy_b,
        output_html=output,
    )

    document = output.read_text(encoding="utf-8")
    assert manifest["status"] == "complete_validated"
    assert manifest["view_count"] == 3
    assert manifest["scientific_scope"]["campaign_result_count"] == 3330
    assert document.count('class="view') == 3
    assert all(
        chart_id in document
        for chart_id in (
            "nominal-chart",
            "priority-chart",
            "sensitivity-chart",
            "lot-chart",
        )
    )
    assert "P10–P90" in document
    assert "338929" in document
    assert "C-XXXXX" in document
    assert "Aucune régulation automatique" in document
    assert "incident qualité" not in document.casefold()
    assert "retenue qualité" not in document.casefold()
    assert "https://" not in document.casefold()
    assert output.stat().st_size < 5_000_000
    payload = delivery._embedded_payload(document)
    assert payload["package"]["htmlBytes"] == output.stat().st_size
    assert payload["package"]["embeddedCurveSeries"] > 0
    assert payload["package"]["embeddedCurvePoints"] == sum(
        len(row["median"]) for row in payload["curves"]["series"]
    )
    assert manifest["scientific_scope"]["curve_downsampling_applied"] is False
    assert len(payload["dataLinks"]) == 4
    assert payload["curves"]["series"][0]["label"] == "Service à l'heure — 28 jours"
    validation = delivery.validate_delivery(output)
    assert validation["valid"] is True
    assert validation["view_count"] == 3


def test_allows_missing_curve_capture_and_zero_non_forced_dossier(
    tmp_path: Path,
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path, selected_count=0)
    output = tmp_path / "preliminary_without_curves.html"

    manifest = delivery.build_delivery(
        campaign_root=campaign,
        results_dir=results,
        curves_dir=None,
        replay_root=None,
        target_registry_path=registry,
        output_html=output,
    )

    payload = delivery._embedded_payload(output.read_text(encoding="utf-8"))
    assert payload["curves"]["status"] == "unavailable"
    assert payload["lots"]["status"] == "not_selected"
    assert manifest["source_bindings"]["curves"] is None
    assert manifest["scientific_scope"]["nominal_curve_days"] == 0


def test_embeds_signed_action_results_without_replaying_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path)
    campaign_payload, campaign_binding = delivery.load_campaign_payload(
        campaign_root=campaign,
        results_dir=results,
        target_registry_path=registry,
    )
    replay_root, replay_plan = _replay_fixture(
        tmp_path, campaign_root=campaign, results=results
    )
    action_root, action_summary, action_validation = _action_fixture(
        tmp_path,
        campaign_payload=campaign_payload,
        campaign_binding=campaign_binding,
    )
    monkeypatch.setattr(
        delivery.lot_replay,
        "load_and_validate_plan",
        lambda _path: replay_plan,
    )
    monkeypatch.setattr(
        delivery.importlib,
        "import_module",
        lambda _name: SimpleNamespace(
            SUMMARY_SCHEMA_VERSION=(
                "etudecas.supplier_priority_action_replay.v4.summary.v1"
            ),
            VALIDATION_SCHEMA_VERSION=(
                "etudecas.supplier_priority_action_replay.v4.validation.v1"
            ),
            validate_action_results=lambda _root: (
                action_summary,
                action_validation,
            ),
        ),
    )
    output = tmp_path / "delivery_with_actions.html"

    manifest = delivery.build_delivery(
        campaign_root=campaign,
        results_dir=results,
        curves_dir=None,
        replay_root=replay_root,
        action_results_root=action_root,
        target_registry_path=registry,
        output_html=output,
    )

    payload = delivery._embedded_payload(output.read_text(encoding="utf-8"))
    assert payload["actions"]["status"] == "complete_validated"
    assert payload["actions"]["results"][0]["exercisedCount"] == 24
    assert payload["actions"]["results"][0]["nonExercisedCount"] == 6
    assert payload["actions"]["results"][1]["status"] == (
        "non_exercised_no_gain_estimate"
    )
    assert payload["actions"]["results"][1]["gains"] == []
    assert payload["actions"]["refusals"][0]["status"] == "refused_not_simulated"
    assert (
        "seuls les scénarios avec action ont été recalculés"
        in payload["actions"]["message"]
    )
    assert "fenêtre d'impact de 360 jours" in payload["actions"]["message"]
    assert "J0–J719" in payload["actions"]["message"]
    assert "J0–J359" not in payload["actions"]["message"]
    gain_labels = {
        row["id"]: row["label"] for row in payload["actions"]["results"][0]["gains"]
    }
    assert gain_labels == {
        "service_gain_pp": "Service récupéré sur la fenêtre d'impact de 360 jours",
        "state_window_service_gain_pp": (
            "Service récupéré sur la fenêtre d'état J0–J719"
        ),
        "backlog_qty_days_avoided": (
            "Retard cumulé évité sur la fenêtre d'état J0–J719"
        ),
        "production_released_gain_qty": (
            "Production libérée récupérée sur la fenêtre d'état J0–J719"
        ),
    }
    document = output.read_text(encoding="utf-8")
    assert "NON TESTABLE SUR CE CAS" in document
    assert (
        "new Set(rows.filter(row=>row.allStates).map(row=>row.supplier)).size"
        in document
    )
    assert "fournisseur(s) distinct(s)" in document
    assert manifest["source_bindings"]["actions"]["action_result_count"] == 2
    assert manifest["scientific_scope"]["signed_action_results_included"] is True


def test_refuses_action_measurement_window_shorter_than_signed_v4_horizon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path)
    campaign_payload, campaign_binding = delivery.load_campaign_payload(
        campaign_root=campaign,
        results_dir=results,
        target_registry_path=registry,
    )
    action_root, action_summary, action_validation = _action_fixture(
        tmp_path,
        campaign_payload=campaign_payload,
        campaign_binding=campaign_binding,
    )
    state_window = action_summary["measurement_windows"]["state"]
    state_window.update({"end_day": 149, "day_count": 150})
    monkeypatch.setattr(
        delivery.importlib,
        "import_module",
        lambda _name: SimpleNamespace(
            SUMMARY_SCHEMA_VERSION=(
                "etudecas.supplier_priority_action_replay.v4.summary.v1"
            ),
            VALIDATION_SCHEMA_VERSION=(
                "etudecas.supplier_priority_action_replay.v4.validation.v1"
            ),
            validate_action_results=lambda _root: (
                action_summary,
                action_validation,
            ),
        ),
    )

    with pytest.raises(delivery.FinalDeliveryError, match="Bornes ou métriques"):
        delivery.load_action_payload(
            action_results_root=action_root,
            campaign=campaign_payload,
            campaign_binding=campaign_binding,
        )


def test_refuses_extra_measurement_range_without_compared_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path)
    campaign_payload, campaign_binding = delivery.load_campaign_payload(
        campaign_root=campaign,
        results_dir=results,
        target_registry_path=registry,
    )
    action_root, action_summary, action_validation = _action_fixture(
        tmp_path,
        campaign_payload=campaign_payload,
        campaign_binding=campaign_binding,
    )
    ranges = action_summary["measurement_windows"]["impact_service"]["ranges"]
    ranges.append(
        {
            "dossier_id": campaign_payload["lotSelection"]["dossiers"][0]["dossierId"],
            "seed": 30,
            "start_day": 180,
            "end_day": 539,
            "day_count": 360,
        }
    )
    monkeypatch.setattr(
        delivery.importlib,
        "import_module",
        lambda _name: SimpleNamespace(
            SUMMARY_SCHEMA_VERSION=(
                "etudecas.supplier_priority_action_replay.v4.summary.v1"
            ),
            VALIDATION_SCHEMA_VERSION=(
                "etudecas.supplier_priority_action_replay.v4.validation.v1"
            ),
            validate_action_results=lambda _root: (
                action_summary,
                action_validation,
            ),
        ),
    )

    with pytest.raises(
        delivery.FinalDeliveryError, match="actions réellement comparées"
    ):
        delivery.load_action_payload(
            action_results_root=action_root,
            campaign=campaign_payload,
            campaign_binding=campaign_binding,
        )


def test_refuses_selected_lot_dossier_without_finalized_replay(tmp_path: Path) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path)
    with pytest.raises(
        delivery.FinalDeliveryError, match="replay finalisé obligatoire"
    ):
        delivery.build_delivery_payload(
            campaign_root=campaign,
            results_dir=results,
            curves_dir=None,
            replay_root=None,
            output_html=tmp_path / "never.html",
            target_registry_path=registry,
        )


def test_refuses_tampered_curve_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path, selected_count=0)
    curves, curve_validation = _curves_fixture(tmp_path)
    monkeypatch.setattr(
        delivery.curve_aggregator,
        "validate_aggregates",
        lambda _path: curve_validation,
    )
    path = curves / aggregator.AGGREGATE_SUBDIRECTORY / "service_quantiles_daily.csv.gz"
    path.write_bytes(b"tampered")

    with pytest.raises(delivery.FinalDeliveryError, match="Empreinte"):
        delivery.build_delivery_payload(
            campaign_root=campaign,
            results_dir=results,
            curves_dir=curves,
            replay_root=None,
            output_html=tmp_path / "never.html",
            target_registry_path=registry,
        )


def test_refuses_tampered_signed_replay_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path)
    replay_root, replay_plan = _replay_fixture(
        tmp_path, campaign_root=campaign, results=results
    )
    monkeypatch.setattr(
        delivery.lot_replay,
        "load_and_validate_plan",
        lambda _path: replay_plan,
    )
    kpis = (
        replay_root / "finalized" / "dossiers" / "dossier_fixture" / "dossier_kpis.json"
    )
    kpis.write_text('{"service_loss_pp":999}\n', encoding="utf-8")

    with pytest.raises(delivery.FinalDeliveryError, match="Sortie replay modifiée"):
        delivery.build_delivery_payload(
            campaign_root=campaign,
            results_dir=results,
            curves_dir=None,
            replay_root=replay_root,
            output_html=tmp_path / "never.html",
            target_registry_path=registry,
        )


def test_validation_detects_modified_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path, selected_count=0)
    output = tmp_path / "delivery.html"
    delivery.build_delivery(
        campaign_root=campaign,
        results_dir=results,
        curves_dir=None,
        replay_root=None,
        target_registry_path=registry,
        output_html=output,
    )
    output.write_text(
        output.read_text(encoding="utf-8") + "\nchanged", encoding="utf-8"
    )
    with pytest.raises(delivery.FinalDeliveryError, match="Manifeste"):
        delivery.validate_delivery(output)


def test_refuses_overwrite(tmp_path: Path) -> None:
    campaign, results, registry = _campaign_fixture(tmp_path, selected_count=0)
    output = tmp_path / "delivery.html"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="écraser"):
        delivery.build_delivery(
            campaign_root=campaign,
            results_dir=results,
            curves_dir=None,
            replay_root=None,
            target_registry_path=registry,
            output_html=output,
        )
