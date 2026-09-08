from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    verify_supplier_v8_stage3_closure as subject,
)


def _campaign_contract() -> dict[str, object]:
    receipt = {
        "counts": {
            "validation_seeds": 150,
            "validation_cases": 450,
            "campaign_seeds": 30,
            "baseline_rows": 90,
            "incident_rows": 3_240,
            "campaign_rows": 3_330,
        }
    }
    overlay = {
        "counts": {
            "campaign_seed_count": 30,
            "baseline_row_count": 90,
            "incident_row_count": 3_240,
            "campaign_row_count": 3_330,
        }
    }
    validation = {
        "expected_contract": {
            "paired_repetition_count": 30,
            "repetition_ids": list(range(30)),
            "baseline_row_count": 90,
            "incident_row_count": 3_240,
            "mechanisms": list(subject.EXPECTED_MECHANISMS),
        },
        "signed_case_evidence": {
            "status": "complete_reconstructed",
            "case_count": 3_330,
            "baseline_case_count": 90,
            "incident_case_count": 3_240,
        },
        "shard_progress": {
            "status": "complete",
            "planned_case_count": 3_330,
            "completed_case_count": 3_330,
            "failed_case_count": 0,
        },
        "comparability_checks": {
            "complete_3x18x2x30_matrix": True,
            "all_18_shard_progress_documents_complete": True,
            "all_3330_metrics_reconstructed_from_signed_case_evidence": True,
            "shipment_set_and_incident_trace_proven": True,
            "quality_or_availability_incident_count": 0,
        },
    }
    dashboard = {
        "states": [{"id": value} for value in subject.EXPECTED_STATES],
        "mechanisms": [{"id": value} for value in subject.EXPECTED_MECHANISMS],
        "repetitions": 30,
        "laneCount": 18,
    }
    launch = {
        "status": "complete",
        "completed_shard_count": 18,
        "failed_shard_count": 0,
        "active_shard_count": 0,
        "queued_shard_count": 0,
    }
    return {
        "receipt": receipt,
        "overlay": overlay,
        "validation": validation,
        "dashboard": dashboard,
        "launch": launch,
    }


def _html_contract() -> tuple[str, dict[str, object], dict[str, object]]:
    document = '<!doctype html><html lang="fr"><section class="view"></section></html>'
    manifest = {
        "standalone": True,
        "external_dependency_count": 0,
        "view_count": 1,
        "scientific_contract": {
            "campaign_rows": 3_330,
            "incident_rows": 3_240,
            "maximum_detailed_dossiers": 3,
            "quality": False,
            "capacity_or_availability_invented": False,
            "actions_open_loop": True,
            "automatic_regulation": False,
            "multiple_incidents_combined": False,
            "full_dynamic_cascade_claimed": False,
            "clients_aggregated": True,
            "action_lot_trace_available": False,
            "days_recovered_cost_or_roi_claimed": False,
        },
    }
    payload = {
        "cascade": {
            "all_incidents_have_lot_trace": False,
            "full_dynamic_stock_mrp_production_service_cascade_proven": False,
        },
        "limits": {
            "consequences_depend_on_evolving_network_state": True,
            "automatic_regulation": False,
            "action_control_mode": "boucle ouverte",
            "customers": "clients agrégés uniquement",
            "lots": "lots simulés uniquement",
        },
        "presentation": {"future_or_placeholder_results_displayed": False},
    }
    return document, manifest, payload


def _business_inputs() -> tuple[
    dict[str, object], dict[str, object], dict[str, object]
]:
    lots = {
        "qualification": {
            "dossiers": [
                {
                    "dossier_id": "D-1",
                    "supplier_id": "S-1",
                    "item_id": "item:1",
                    "dst_node_id": "M-1",
                    "target_product_id": "P-1",
                    "mechanism": "transport_delay",
                    "proof_level": "partial",
                    "trace_counts": {"shipments": 2, "material_receipts": 1},
                }
            ]
        }
    }
    delivery = {
        "payload": {
            "cascade": {
                "detailed_replays": [
                    {"dossier_id": "D-1", "genealogy_rows": [{"lot": "MP-1"}]}
                ]
            }
        }
    }
    registry = {"availableDetailedReplayCount": 1}
    return lots, delivery, registry


def test_campaign_contract_accepts_exact_matrix_and_rejects_one_failure() -> None:
    contract = _campaign_contract()
    subject._assert_campaign_contract(**contract)  # noqa: SLF001

    changed = copy.deepcopy(contract)
    changed["validation"]["shard_progress"]["failed_case_count"] = 1
    with pytest.raises(subject.ClosureVerificationError, match="matrice 3 niveaux"):
        subject._assert_campaign_contract(**changed)  # noqa: SLF001


def test_campaign_contract_requires_both_mechanisms_kept_separate() -> None:
    contract = _campaign_contract()
    contract["dashboard"]["mechanisms"] = [{"id": "transport_delay"}]
    with pytest.raises(subject.ClosureVerificationError, match="mécanismes séparés"):
        subject._assert_campaign_contract(**contract)  # noqa: SLF001


def test_html_contract_accepts_french_standalone_and_rejects_external_url() -> None:
    document, manifest, payload = _html_contract()
    subject._assert_html_contract(document, manifest, payload)  # noqa: SLF001

    with pytest.raises(subject.ClosureVerificationError, match="HTML autonome"):
        subject._assert_html_contract(  # noqa: SLF001
            document.replace(
                "</html>", '<script src="https://x.invalid/a.js"></script></html>'
            ),
            manifest,
            payload,
        )


def test_html_contract_rejects_more_than_three_views() -> None:
    document, manifest, payload = _html_contract()
    document = document.replace(
        '<section class="view"></section>', '<section class="view"></section>' * 4
    )
    with pytest.raises(subject.ClosureVerificationError, match="trois vues"):
        subject._assert_html_contract(document, manifest, payload)  # noqa: SLF001


def test_action_gain_requires_physical_exercise() -> None:
    summary = {
        "action_results": [
            {
                "dossier_id": "D-1",
                "action_id": "stock_scale_at_j0",
                "status": "estimated_on_physically_exercised_seeds",
                "physically_exercised_seed_count": 2,
                "gain_statistics": {"service_gain_pp": {"count": 2}},
            }
        ]
    }
    applications = [
        {"included_in_gain_statistics": "true", "physically_exercised": "true"}
    ]
    presentation = [
        {
            "dossier_id": "D-1",
            "action_id": "stock_scale_at_j0",
            "metrics": [{"available": True}],
        }
    ]
    subject._assert_action_gain_contract(  # noqa: SLF001
        summary, applications, presentation
    )

    applications[0]["physically_exercised"] = "false"
    with pytest.raises(subject.ClosureVerificationError, match="n'a pas agi"):
        subject._assert_action_gain_contract(  # noqa: SLF001
            summary, applications, presentation
        )


def test_business_verdict_distinguishes_usable_lot_from_missing_lot() -> None:
    lots, delivery, registry = _business_inputs()
    verdict = subject._business_verdict(  # noqa: SLF001
        technical_ok=True,
        lots=lots,
        delivery=delivery,
        registry=registry,
    )
    assert verdict["code"] == "EXPLOITABLE_METIER_AVEC_LIMITES"
    assert verdict["dossier_lot_exploitable_count"] == 1

    lots["qualification"]["dossiers"] = []
    delivery["payload"]["cascade"]["detailed_replays"] = []
    registry["availableDetailedReplayCount"] = 0
    verdict = subject._business_verdict(  # noqa: SLF001
        technical_ok=True,
        lots=lots,
        delivery=delivery,
        registry=registry,
    )
    assert verdict["code"] == "INSUFFISANT_METIER"
    assert verdict["exploitable"] is False


def test_new_or_identical_report_never_overwrites(tmp_path: Path) -> None:
    output = tmp_path / "audit" / "closure.json"
    first = {"value": 1}
    subject.publish_new_or_identical(output, first)
    initial_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    subject.publish_new_or_identical(output, first)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == initial_hash

    with pytest.raises(subject.ClosureVerificationError, match="écrasement refusé"):
        subject.publish_new_or_identical(output, {"value": 2})
    assert hashlib.sha256(output.read_bytes()).hexdigest() == initial_hash


def test_final_context_refuses_a_waiting_stage3_without_audit(tmp_path: Path) -> None:
    supervision = tmp_path / "supervision"
    supervision.mkdir()
    path_values = {
        name: str(tmp_path / name)
        for name in subject.common.Stage2Paths.__dataclass_fields__
    }
    path_values["supervision_dir"] = str(supervision)
    path_values["observed_2025_dir"] = None
    contract = subject.common.signed(
        {
            "schema_version": f"{subject.pipeline_v3.SCHEMA_VERSION}.contract.v1",
            "paths": path_values,
        },
        "contract_signature",
    )
    status = subject.common.signed(
        {
            "schema_version": f"{subject.pipeline_v3.SCHEMA_VERSION}.status.v1",
            "contract_signature": contract["contract_signature"],
            "status": "waiting",
            "step": "attente_campagne_v8",
            "results": {},
        },
        "status_signature",
    )
    (supervision / subject.pipeline_v3.CONTRACT_NAME).write_text(
        subject._raw_report(contract).decode("utf-8"),  # noqa: SLF001
        encoding="utf-8",
    )
    (supervision / subject.pipeline_v3.STATUS_NAME).write_text(
        subject._raw_report(status).decode("utf-8"),  # noqa: SLF001
        encoding="utf-8",
    )

    with pytest.raises(subject.ClosureNotFinal, match="pas encore terminé"):
        subject.load_final_context(supervision)
