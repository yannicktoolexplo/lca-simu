from __future__ import annotations

import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_preliminary_15_audit as preliminary,
)


def _product_row(seed: int, *, extension: str = "temporal_robustness") -> dict:
    return {
        "extension": extension,
        "case_id": "case-a",
        "seed": seed,
        "failure_mode": "transport_delay",
        "mechanism_value": 120,
        "mechanism_unit": "jours_ajoutes",
        "stress_start_day": 0,
        "stress_end_day": 179,
        "outcome_spec_id": "calendar_window_1_fixed_followup",
        "outcome_start_day": 0,
        "outcome_end_day": 522,
        "product_id": "268091",
        "product_uom": "UN",
        "delta_on_due_percentage_points": -20.0 - seed,
        "delta_backlog_days_per_demand_unit": 2.0 + seed / 10.0,
        "delta_backlog_end_qty": 100.0 + seed,
        "signed_production_shortfall_ratio": 0.0,
    }


def _flow_row(seed: int, *, extension: str = "temporal_robustness") -> dict:
    return {
        "extension": extension,
        "case_id": "case-a",
        "seed": seed,
        "failure_mode": "transport_delay",
        "stress_start_day": 0,
        "stress_end_day": 179,
        "chain_id": "chain-a",
        "supplier_id": "SUP-A",
        "item_id": "item:338929",
        "dst_node_id": "M-1810",
        "uom": "UN",
        "baseline_flow_exercised": True,
        "risk_event_applied_on_lane": seed != 15,
    }


def _focus_338929_product_rows() -> list[dict]:
    mechanisms = (
        ("transport_delay", 120, "jours_ajoutes", -28.0),
        ("supply_availability", 0.5, "part_disponible", -18.0),
        ("quality_hold", 90, "jours_ajoutes", -12.0),
        ("quality_yield", 0.8, "part_utilisable", -7.0),
    )
    rows = []
    for failure_mode, mechanism_value, mechanism_unit, centre in mechanisms:
        for seed in range(1, 16):
            row = _product_row(
                seed,
                extension="priority_four_business_causes",
            )
            row.update(
                {
                    "case_id": (
                        "four_causes__slot3__sdc_vd0914360c_338929_m_1810__"
                        f"{failure_mode}"
                    ),
                    "failure_mode": failure_mode,
                    "mechanism_value": mechanism_value,
                    "mechanism_unit": mechanism_unit,
                    "delta_on_due_percentage_points": centre + (seed - 8) / 5,
                }
            )
            rows.append(row)
    return rows


def _lineage() -> dict:
    suppliers = ["SUP-A", "SUP-B", "SUP-C", "SUP-D"]
    mappings = [
        {
            "supplier_id": supplier,
            "driver_chain_id": f"chain-{index}",
            "driver_scenario_id": f"scenario-{index}",
            "driver_failure_mode": "transport_delay",
        }
        for index, supplier in enumerate(suppliers, 1)
    ]
    return {
        "follow_up_supplier_ids": suppliers,
        "follow_up_driver_mappings": mappings,
    }


def _boundary_rows() -> list[dict]:
    rows = []
    for supplier_index, supplier in enumerate(
        ["SUP-A", "SUP-B", "SUP-C", "SUP-D"], 1
    ):
        for metric_index, metric in enumerate(preliminary.BOUNDARY_METRIC_KEYS, 1):
            rows.append(
                {
                    "supplier_id": supplier,
                    "metric_key": metric,
                    "metric_value": str(-0.01 * supplier_index * metric_index),
                }
            )
    return rows


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _valid_package(root: Path) -> dict:
    root.mkdir()
    audit = {
        "schema_version": preliminary.SCHEMA_VERSION,
        "status": "preliminary_15_of_30_complete_not_final",
        "completed_seed_count": 15,
        "checkpoint_evidence_case_count": 634,
        "preliminary_not_final": True,
        "preliminary_results_publishable_as_final": False,
        "supplier_ranking_allowed": False,
        "historical_probability_estimated": False,
        "confirmatory_interval_claimed": False,
        "global_network_priority_robustness_evaluable": False,
        "action_effectiveness_evaluated": False,
        "action_promotion_allowed": False,
        "promotion_allowed": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "days_recovered_claimed": False,
        "causal_lot_attribution_available": False,
        "counterfactual_entity_identity_validated": False,
        "service_nonseparation_group_is_unordered": True,
        "service_nonseparation_group_supplier_count": 4,
        "lot_genealogical_exposure_detail_count": 1,
        "lot_genealogical_exposure_is_upper_bound": True,
    }
    _write_json(root / preliminary.OUTPUT_FILES[0], audit)
    for name in preliminary.OUTPUT_FILES[1:]:
        (root / name).write_text("test\n", encoding="utf-8")
    artifacts = {
        name: preliminary._sha256(root / name) for name in preliminary.OUTPUT_FILES
    }
    signature_payload = {
        "schema_version": preliminary.PACKAGE_SCHEMA_VERSION,
        "status": "complete_preliminary_not_final",
        "builder_sha256": preliminary._sha256(Path(preliminary.__file__).resolve()),
        "source_file_sha256": {
            key: "1" * 64 for key in preliminary.SOURCE_HASH_KEYS
        },
        "artifact_file_sha256": artifacts,
        "checkpoint_signature": "2" * 64,
        "runner_signature": "3" * 64,
        "plan_signature": "4" * 64,
        "completed_seed_count": 15,
        "signed_full_seed_count": 30,
        "preliminary_not_final": True,
        "promotion_allowed": False,
        "action_promotion_allowed": False,
    }
    manifest = {
        **signature_payload,
        "package_signature": preliminary._canonical_sha256(signature_payload),
        "package_signature_semantics": (
            "unkeyed_internal_consistency_digest_not_authentication"
        ),
        "cryptographic_authentication_present": False,
        "sources_mutated": False,
        "runner_output_mutated": False,
        "large_case_directories_copied": False,
    }
    _write_json(root / preliminary.MANIFEST_FILE, manifest)
    return manifest


def test_effect_aggregation_requires_the_exact_fifteen_seed_prefix() -> None:
    rows = [_product_row(seed) for seed in range(1, 16)]
    result = preliminary.aggregate_effect_rows(rows)
    assert len(result) == 1
    assert result[0]["paired_seed_count"] == 15
    assert result[0]["stress_start_day"] == "0"
    assert result[0]["outcome_start_day"] == "0"
    assert result[0]["mean_service_delta_percentage_points"] == pytest.approx(-28)
    assert result[0]["mean_released_production_shortfall_ratio"] == 0
    assert result[0]["interval_is_confirmatory"] is False
    assert result[0]["action_promotion_allowed"] is False

    with pytest.raises(preliminary.PreliminaryAuditError, match="incomplète"):
        preliminary.aggregate_effect_rows(rows[:-1])


def test_one_seed_lot_illustration_is_not_averaged_as_fifteen() -> None:
    row = _product_row(1, extension="causal_lot_attribution_subset")
    result = preliminary.aggregate_effect_rows([row])
    assert result[0]["paired_seed_count"] == 1
    assert result[0]["expected_paired_seed_count"] == 1
    assert result[0]["preliminary_not_final"] is True
    assert preliminary._service_range_label(result[0]) == (
        "non applicable (1 simulation)"
    )


def test_active_exposure_is_counted_on_the_same_seed_intersection() -> None:
    result = preliminary.aggregate_exposure_rows(
        [_flow_row(seed) for seed in range(1, 16)]
    )
    assert result[0]["baseline_active_seed_count"] == 15
    assert result[0]["risk_applied_seed_count"] == 14
    assert result[0]["joint_active_exposure_seed_count"] == 14
    assert result[0]["stress_start_day"] == "0"
    assert result[0]["active_exposure_interpretation_complete_15"] is False
    assert result[0]["zero_effect_means_no_risk"] is False


def test_boundary_group_is_rendered_unordered_without_production_loss_claim() -> None:
    confirmed = preliminary.boundary_group_rows(_boundary_rows(), _lineage())
    assert len(confirmed) == 4
    assert all(row["group_is_unordered"] is True for row in confirmed)
    effects = preliminary.aggregate_effect_rows(_focus_338929_product_rows())
    exposures = preliminary.aggregate_exposure_rows(
        [_flow_row(seed) for seed in range(1, 16)]
    )
    lots = [
        {
            "supplier_id": "SUP-A",
            "item_id": "item:338929",
            "target_product_id": "268091",
            "root_lot_count": 329,
            "genealogical_exposed_lot_count": 780,
        }
    ]
    lot_details = [
        {
            "supplier_ids": "SUP-A",
            "lot_id": "simulated-lot-338929-001",
            "exposure_role": "risk_tagged_usable_receipt_root",
            "genealogy_depth": 0,
            "node_id": "M-1810",
            "item_id": "item:338929",
            "day": 120,
            "qty": 42.0,
            "uom": "UN",
        }
    ]
    document = preliminary.render_html(
        boundary_rows=confirmed,
        effect_rows=effects,
        exposure_rows=exposures,
        lot_rows=lots,
        lot_detail_rows=lot_details,
    )
    assert "PRÉLIMINAIRE — 15 simulations sur 30" in document
    assert "Comment lire les indicateurs" in document
    assert "Service à la date demandée" in document
    assert "Pire période de 28 jours" in document
    assert "Retard cumulé ramené à la demande" in document
    assert "Rattrapage de production" in document
    assert "simulations ne permettent pas d’ordonner" in document
    assert document.count("class='bar-row'") == 4
    assert document.count("class='range-row'") == 4
    assert "plage constatée parmi les 15 simulations" in document
    assert "moyenne. Axe commun" in document
    assert "Type d’incident métier" in document
    assert "Retard de transport ou d’expédition (120 jours)" in document
    assert "four_causes__slot3" not in document
    assert "non applicable (1 simulation)" not in document
    assert "Cela ne doit pas être présenté comme une perte de production" in document
    assert "Une seule comparaison technique est examinée par dossier" in document
    assert "Aucun des quatre leviers opérationnels n’est testé ni recommandé" in document
    assert "aucun nombre de jours récupérés n’est calculé" in document
    assert "classer tous les fournisseurs" in document
    assert "prédire leur survenue" in document
    assert "simulated-lot-338929-001" in document
    assert "pas une perte attribuée" in document
    assert "Réception fournisseur à l’origine du suivi" in document
    assert preliminary.LOT_DETAIL_FILE in document
    for jargon in (
        "répétition",
        "backlog",
        "cellule",
        "préfixe",
        "promotion d’action",
        "contrefactuel",
    ):
        assert jargon not in document.casefold()


def test_focus_service_chart_rejects_a_mean_outside_its_range() -> None:
    effects = preliminary.aggregate_effect_rows(_focus_338929_product_rows())
    effects[0]["mean_service_delta_percentage_points"] = (
        effects[0]["max_service_delta_percentage_points"] + 1.0
    )
    with pytest.raises(preliminary.PreliminaryAuditError, match="hors de la plage"):
        preliminary._focus_338929_range_chart(effects)


def test_package_validator_is_exact_and_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "preliminary"
    manifest = _valid_package(root)
    assert preliminary.validate_preliminary_package(root) == manifest

    (root / "undeclared.json").write_text("{}", encoding="utf-8")
    with pytest.raises(preliminary.PreliminaryAuditError, match="Inventaire"):
        preliminary.validate_preliminary_package(root)
    (root / "undeclared.json").unlink()

    html_path = root / preliminary.OUTPUT_FILES[-1]
    html_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(preliminary.PreliminaryAuditError, match="altéré"):
        preliminary.validate_preliminary_package(root)


def test_even_resigned_manifest_cannot_promote_preliminary_results(
    tmp_path: Path,
) -> None:
    root = tmp_path / "preliminary"
    manifest = _valid_package(root)
    manifest["promotion_allowed"] = True
    payload = {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "status",
            "builder_sha256",
            "source_file_sha256",
            "artifact_file_sha256",
            "checkpoint_signature",
            "runner_signature",
            "plan_signature",
            "completed_seed_count",
            "signed_full_seed_count",
            "preliminary_not_final",
            "promotion_allowed",
            "action_promotion_allowed",
        )
    }
    manifest["package_signature"] = preliminary._canonical_sha256(payload)
    _write_json(root / preliminary.MANIFEST_FILE, manifest)
    with pytest.raises(preliminary.PreliminaryAuditError, match="Manifeste"):
        preliminary.validate_preliminary_package(root)


def test_destination_cannot_be_inside_runner_or_plan(tmp_path: Path) -> None:
    runner_dir = tmp_path / "runner"
    runner_dir.mkdir()
    with pytest.raises(preliminary.PreliminaryAuditError, match="dossier externe"):
        preliminary._assert_external_destination(
            runner_dir / "preliminary",
            (runner_dir, tmp_path / "plan", tmp_path / "boundary"),
        )
