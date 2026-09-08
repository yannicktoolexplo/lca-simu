from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_industrial_supply_preliminary_delivery as delivery,
)


def _json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    roots = {name: tmp_path / name for name in (
        "preliminary",
        "observed",
        "quality",
        "regime",
        "actions",
        "stock_calibration",
    )}
    for root in roots.values():
        root.mkdir()

    _json(
        roots["preliminary"] / delivery.preliminary_audit.MANIFEST_FILE,
        {"checkpoint_signature": "checkpoint-15"},
    )
    _json(
        roots["preliminary"] / delivery.preliminary_audit.OUTPUT_FILES[0],
        {
            "preliminary_not_final": True,
            "promotion_allowed": False,
            "days_recovered_claimed": False,
            "network_recovery_metric_status": "excluded_invalid_common_window",
        },
    )
    (
        roots["preliminary"]
        / "PRELIMINAIRE_15_SUR_30.html"
    ).write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        "<body>Préliminaire 15/30</body></html>",
        encoding="utf-8",
    )
    _csv(
        roots["preliminary"] / delivery.preliminary_audit.BOUNDARY_FILE,
        [
            {
                "supplier_id": delivery.FOCUS_SUPPLIER_ID,
                "driver_chain_id": delivery.FOCUS_CHAIN_ID,
                "driver_scenario_id": delivery.FOCUS_SCENARIO_ID,
                "driver_failure_mode": "transport_delay",
                "horizon_service_delta_percentage_points": -30.2919941632,
                "worst_rolling_28d_service_delta_percentage_points": -99.0008351724,
                "backlog_delta_days_per_demand_unit": 11.4469232968,
                "released_production_shortfall_percent": 0.0,
                "paired_seed_count": 30,
                "group_is_unordered": True,
                "universal_supplier_ranking_claimed": False,
                "historical_probability_estimated": False,
            }
        ],
    )
    monkeypatch.setattr(
        delivery.preliminary_audit,
        "validate_preliminary_package",
        lambda root: {"valid": True},
    )

    _json(roots["observed"] / "manifest.json", {"status": "complete"})
    _json(
        roots["observed"] / "bilan_observed_2025.json",
        {
            "currency_status": (
                "not_declared_in_source; EUR_is_working_convention"
            ),
            "ca_summary": [
                {
                    "product_code": "268091",
                    "delivered_share_of_raw_potential": 0.9287,
                    "ca_lost_positive_only_source_value": 1_611_220,
                },
                {
                    "product_code": "268967",
                    "delivered_share_of_raw_potential": 0.954,
                    "ca_lost_positive_only_source_value": 1_082_210,
                },
            ],
            "stock_summary": [
                {
                    "series_id": "finished_goods_stock_268091",
                    "mean_stock_value_source": 402_762,
                    "snapshot_count": 52,
                }
            ],
            "supplier_risk_prediction_readiness": {
                "industrial_probability_status": "NOT_READY",
                "current_safe_wording": (
                    "signal de priorité à instruire; pas une probabilité"
                ),
            },
        },
    )
    monkeypatch.setattr(delivery.final_package, "_validate_observed", lambda root: {})

    quality_manifest = {
        "status": "complete",
        "outputs": {"dashboard_payload": "future_autonomous_page_payload.json"},
    }
    _json(roots["quality"] / "campaign_manifest.json", quality_manifest)
    _json(
        roots["quality"] / "future_autonomous_page_payload.json",
        {
            "observed_2025_order_book": {"order_count": 23},
            "paired_causal_lot_proof": {
                "scenario_id": "all_021081__quality_hold__180",
                "affected_opening_po_technical_row_count": 23,
                "technical_rows_with_paired_receipt_effect": 23,
                "technical_rows_with_paired_descendant_effect": 0,
                "no_descendant_wording": "receipt not consumed in the tested horizon",
                "seed": 422081,
            },
            "scientific_conclusions": {
                "lots": "Aucun effet client, coût ou action n’est démontré."
            },
        },
    )
    quality_page = roots["quality"] / "index.html"
    quality_page.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        "<body>Qualité et lots</body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        delivery.final_package,
        "_validate_component_package",
        lambda root: (quality_manifest, quality_page),
    )

    inventory = {
        "candidate-a": {
            "input_sha256": "1" * 64,
            "change_ledger_sha256": "2" * 64,
        }
    }
    plan = {
        "schema_version": delivery.regime_protocol.SCHEMA_VERSION,
        "status": "planned_not_executed",
        "evidence_class": "simulation_hypothesis_not_observed_performance",
        "old_results_mutated": False,
        "engine_mutated": False,
        "graph_source_mutated": False,
        "reference_audit": {},
        "families": [],
        "stages": {
            "preliminary": {"publishable_as_final_confirmation": False},
            "final": {"reuses_preliminary_exactly": True},
        },
        "selection_rule": {},
        "service_definition": {"targets": [0.93, 0.8]},
        "execution_contract": {"implemented_by_this_prepare_only_module": False},
        "screening_candidate_count": 1,
    }
    plan["plan_signature"] = delivery.regime_protocol.stable_sha256(
        {
            "schema_version": delivery.regime_protocol.SCHEMA_VERSION,
            "reference_audit": plan["reference_audit"],
            "families": plan["families"],
            "candidate_inputs": inventory,
            "stages": plan["stages"],
            "selection_rule": plan["selection_rule"],
            "service_definition": plan["service_definition"],
            "execution_contract": plan["execution_contract"],
        }
    )
    _json(roots["regime"] / "calibration_plan.json", plan)
    _json(roots["regime"] / "input_inventory.json", inventory)
    _csv(roots["regime"] / "scenario_design.csv", [{"scenario_id": "candidate-a"}])

    _json(
        roots["actions"] / "exploratory_action_protocol_manifest.json",
        {
            "schema_version": delivery.action_protocol.SCHEMA_VERSION,
            "contract_revision": delivery.action_protocol.CONTRACT_REVISION,
            "status": "planned_not_executed",
            "engine_execution_enabled": False,
            "protocol_signature": "action-plan-v5",
            "stock_buffers_lotified": True,
            "industrial_action_cost_published": False,
            "closed_loop_claimed": False,
        },
    )
    _json(
        roots["actions"] / "scientific_controls.json",
        {
            "claims": {
                "supplier_probability_estimated": False,
                "action_recommended": False,
                "action_promotion_allowed": False,
                "industrial_cost_claimed": False,
            },
            "execution": {"engine_execution_enabled": False},
        },
    )
    action_rows = []
    lane_inputs = (
        ("016332", "M-1810", 1100.0, "KG"),
        ("029313", "M-1810", 300.0, "KG"),
        ("338929", "M-1810", 150000.0, "UN"),
        ("344135", "M-1430", 120000.0, "UN"),
    )
    for item_id, dst_node_id, stock_qty, stock_uom in lane_inputs:
        for lever in delivery.action_protocol.EXPECTED_LEVERS:
            action_rows.append(
                {
                    "lever_id": lever,
                    "item_id": f"item:{item_id}",
                    "dst_node_id": dst_node_id,
                    "new_action_run_status": (
                        "blocked_missing_explicit_alternative_source_register"
                        if lever == "explicit_counterfactual_alternative_source"
                        else (
                            "conditional_positive_paired_J0_stock"
                            if lever == "prepositioned_free_stock_14d"
                            else (
                                "planned_after_V3_quality_pair_available"
                                if lever
                                == "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
                                else "planned_new_run"
                            )
                        )
                    ),
                    "industrial_cost_status": (
                        "not_estimated_missing_industrial_cost_inputs"
                    ),
                    "industrial_action_cost_available": False,
                    "closed_loop_claimed": False,
                    "not_a_recommendation": True,
                    "action_promotion_allowed": False,
                    "buffer_rounded_qty": (
                        stock_qty if lever == "prepositioned_free_stock_14d" else ""
                    ),
                    "buffer_uom": (
                        stock_uom if lever == "prepositioned_free_stock_14d" else ""
                    ),
                    "buffer_procurement_lot_count": (
                        1 if lever == "prepositioned_free_stock_14d" else ""
                    ),
                    "stock_present_at_j0_hypothesis": (
                        True if lever == "prepositioned_free_stock_14d" else ""
                    ),
                    "stock_acquisition_simulated": (
                        False if lever == "prepositioned_free_stock_14d" else ""
                    ),
                    "action_timing": (
                        "fixed_calendar_open_loop_whole_lane_in_quality_scenario"
                        if lever
                        == "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
                        else ""
                    ),
                    "quality_hold_reduction_claimed": False,
                    "identified_lot_claimed": False,
                }
            )
    _csv(roots["actions"] / "action_lever_parameters.csv", action_rows)
    monkeypatch.setattr(
        delivery.action_protocol,
        "validate_protocol_artifact",
        lambda root: {"valid": True},
    )

    stock_payload = {
        "schema_version": delivery.stock_calibration_audit.SCHEMA_VERSION,
        "simulation_count": 15,
        "material_count": 24,
        "status_counts": {"ecart_majeur_de_calibration": 21},
        "focus": [
            {
                "node_id": "M-1430",
                "item_id": "item:038005",
                "safety_time_days_mean": 20.0,
                "physical_consumption_avg_qty_per_calendar_day_mean": 75.98045,
                "safety_target_rate_to_physical_ratio_mean": 35.46798,
                "reference_stock_cover_physical_days_mean": 709.359606,
                "preincident_stock_minus_window_consumption_qty_mean": 23075.187254,
                "preincident_stock_minus_window_consumption_qty_min": 13075.187254,
                "preincident_stock_minus_window_consumption_qty_max": 33075.187254,
                "preincident_stock_covers_window_simulation_count": 15,
                "calibration_status": "ecart_majeur_de_calibration",
                "mrp_gross_requirement_basis": "static_requirement_override",
            },
            {
                "node_id": "M-1810",
                "item_id": "item:049371",
                "safety_time_days_mean": 40.0,
                "physical_consumption_avg_qty_per_calendar_day_mean": 15.411701,
                "safety_target_rate_to_physical_ratio_mean": 19.842923,
                "reference_stock_cover_physical_days_mean": 793.71693,
                "preincident_stock_minus_window_consumption_qty_mean": 3663.039227,
                "preincident_stock_minus_window_consumption_qty_min": 676.37256,
                "preincident_stock_minus_window_consumption_qty_max": 5476.37256,
                "preincident_stock_covers_window_simulation_count": 15,
                "calibration_status": "ecart_majeur_de_calibration",
                "mrp_gross_requirement_basis": "static_requirement_override",
            },
        ],
    }
    _json(
        roots["stock_calibration"] / delivery.stock_calibration_audit.RESULT_JSON,
        stock_payload,
    )
    _csv(
        roots["stock_calibration"] / delivery.stock_calibration_audit.SUMMARY_CSV,
        [{"node_id": "M-1430", "item_id": "item:038005"}],
    )
    _csv(
        roots["stock_calibration"] / delivery.stock_calibration_audit.DETAIL_CSV,
        [{"seed": 340282, "node_id": "M-1430", "item_id": "item:038005"}],
    )
    stock_page = (
        roots["stock_calibration"] / delivery.stock_calibration_audit.RESULT_HTML
    )
    stock_page.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head><body>'
        "<p>L’absence d’effet ne démontre pas que la chaîne industrielle résisterait.</p>"
        '<div class="card"><div class="big">21</div>écarts majeurs</div>'
        "</body></html>",
        encoding="utf-8",
    )
    stock_outputs = {}
    for name in (
        delivery.stock_calibration_audit.RESULT_JSON,
        delivery.stock_calibration_audit.SUMMARY_CSV,
        delivery.stock_calibration_audit.DETAIL_CSV,
        delivery.stock_calibration_audit.RESULT_HTML,
    ):
        path = roots["stock_calibration"] / name
        stock_outputs[name] = {
            "size_bytes": path.stat().st_size,
            "sha256": delivery.stock_calibration_audit._sha256(path),
        }
    _json(
        roots["stock_calibration"] / delivery.stock_calibration_audit.MANIFEST_JSON,
        {
            "schema_version": delivery.stock_calibration_audit.SCHEMA_VERSION,
            "status": "complete",
            "engine_invoked": False,
            "source_files_mutated": False,
            "simulation_count": 15,
            "material_count": 24,
            "output_files": stock_outputs,
        },
    )

    map_page = tmp_path / "map.html"
    map_page.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        "<body>Carte autonome</body></html>",
        encoding="utf-8",
    )
    roots["map"] = map_page
    return roots


def _resign_delivery_manifest(root: Path, manifest: dict) -> None:
    signature_payload = {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "status",
            "builder_sha256",
            "source_file_sha256",
            "artifact_file_sha256",
            "view_files",
            "view_count",
            "preliminary_checkpoint_signature",
            "regime_plan_signature",
            "action_protocol_signature",
            "stock_calibration_schema_version",
            "stock_calibration_simulation_count",
            "stock_calibration_material_count",
            "stock_calibration_major_gap_count",
            "stock_calibration_focus_keys",
            "stock_calibration_warning_present",
            "stock_calibration_annex_offline_verified",
            "stock_calibration_annex_size_bytes",
            "stock_calibration_annex_external_resource_count",
            "network_map_offline_verified",
            "network_map_size_bytes",
            "network_map_external_resource_count",
            "lighter_network_map_excluded",
            "lighter_network_map_exclusion_reason",
            "preliminary_not_final",
            "probability_estimated",
            "currency_assumed",
            "industrial_cost_claimed",
            "days_recovered_claimed",
            "supplier_ranking_promoted",
            "service_regime_results_available",
            "action_result_available",
            "action_promotion_allowed",
        )
    }
    manifest["package_signature"] = delivery._canonical_sha256(signature_payload)
    _json(root / delivery.MANIFEST_FILE, manifest)


def test_builds_exactly_three_views_without_mutating_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    before = {
        path: delivery._sha256(path)
        for root in roots.values()
        for path in ([root] if root.is_file() else root.rglob("*"))
        if path.is_file()
    }
    output = tmp_path / "delivery"
    result = delivery.build_preliminary_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        quality_dir=roots["quality"],
        network_map_html=roots["map"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        stock_calibration_audit_dir=roots["stock_calibration"],
        output_dir=output,
    )
    assert result["view_count"] == 3
    assert result["preliminary_not_final"] is True
    assert result["action_result_available"] is False
    assert result["network_map_external_resource_count"] == 0
    assert result["stock_calibration_simulation_count"] == 15
    assert result["stock_calibration_material_count"] == 24
    assert result["stock_calibration_major_gap_count"] == 21
    assert result["source_file_sha256"]["map/page"] == delivery._sha256(
        roots["map"]
    )
    assert delivery.validate_preliminary_delivery(output) == result
    assert all(delivery._sha256(path) == digest for path, digest in before.items())
    launcher = (output / delivery.LAUNCHER_FILE).read_text(encoding="utf-8")
    assert sum(f'href="{name}"' in launcher for name in delivery.VIEW_FILES) == 3
    assert delivery.STOCK_CALIBRATION_ASSET not in launcher
    assert "SIMULÉ</strong> mesure ce que le modèle produirait" in launcher
    assert "SIGNAL DE PRIORITÉ</strong> ouvre un dossier à instruire" in launcher
    assert "Parcours officiel : 01 → 02 → 03" in launcher
    network = (output / delivery.VIEW_FILES[0]).read_text(encoding="utf-8")
    assert "Résultat déjà consolidé sur 30 simulations comparables" in network
    assert "120 jours de retard de transport" in network
    assert "−30,29 points" in network
    assert "−99,00 points" in network
    assert "+11,45 jours" in network
    assert "0,00 %" in network
    assert network.count("Annexe interactive —") == 2
    quality = (output / delivery.VIEW_FILES[1]).read_text(encoding="utf-8")
    assert "retenue qualité de 180 jours" in quality
    assert "23 / 23" in quality
    assert "0" in quality and "Descendant consommé" in quality
    assert "1 simulation" in quality
    assert "aucun effet client n’est donc démontré" in quality
    assert quality.count("<strong>Annexe interactive —") == 1
    decision = (output / delivery.VIEW_FILES[2]).read_text(encoding="utf-8")
    assert "Préparé, aucun résultat" in decision
    assert "Devise non déclarée" in decision
    assert "aucun coût industriel n’est chiffré" in decision
    assert "Réduire de 7 jours le délai des futurs envois" in decision
    assert "Second fournisseur" in decision
    assert "sans raccourcir l’attente qualité" in decision
    assert "Stock comptable de produit fini 268091" in decision
    assert "finished_goods_stock_268091" not in decision
    assert "boucle ouverte" not in decision
    assert "commandes livrées complètes et à l’heure" in decision
    assert "données insuffisantes pour calculer une probabilité fournisseur" in decision
    assert "NOT_READY" not in decision
    assert "pas une quantité minimale contractuelle confirmée" in decision
    assert "historique qualité : quarantaine, libération, rejet" in decision
    assert "1 100 KG" in decision
    assert "150 000 UN" in decision
    assert "dated_post_quality_release_transport_reduction" not in decision
    assert all(
        decision.count(sentence) == 1
        for sentence in delivery.STOCK_CALIBRATION_CLIENT_SENTENCES
    )
    assert decision.count(f'href="{delivery.STOCK_CALIBRATION_ASSET}"') == 1
    assert "n’est pas une quatrième vue officielle" in decision
    assert (output / delivery.STOCK_CALIBRATION_ASSET).is_file()
    assert "€" not in decision


def test_regime_plan_with_result_like_file_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    (roots["regime"] / "results.csv").write_text("value\n93\n", encoding="utf-8")
    with pytest.raises(delivery.PreliminaryDeliveryError, match="résultat"):
        delivery._validate_regime_plan(roots["regime"])


def test_action_plan_cannot_claim_an_industrial_cost_or_recommendation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    controls_path = roots["actions"] / "scientific_controls.json"
    controls = json.loads(controls_path.read_text(encoding="utf-8"))
    controls["claims"]["industrial_cost_claimed"] = True
    _json(controls_path, controls)
    with pytest.raises(delivery.PreliminaryDeliveryError, match="non exécuté"):
        delivery._validate_action_plan(roots["actions"])


def test_focus_network_cards_reject_an_unrelated_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    path = roots["preliminary"] / delivery.preliminary_audit.BOUNDARY_FILE
    rows = delivery._read_csv(path)
    rows[0]["driver_scenario_id"] = "unrelated_scenario"
    _csv(path, rows)

    with pytest.raises(delivery.PreliminaryDeliveryError, match="Lignée"):
        delivery._load_focus_network_result(roots["preliminary"])


def test_quality_cards_reject_an_unverified_descendant_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    payload_path = roots["quality"] / "future_autonomous_page_payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["paired_causal_lot_proof"][
        "technical_rows_with_paired_descendant_effect"
    ] = 1
    _json(payload_path, payload)

    with pytest.raises(delivery.PreliminaryDeliveryError, match="compteurs signés"):
        delivery._validate_quality(roots["quality"])


def test_stock_calibration_source_must_keep_exact_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    audit_path = (
        roots["stock_calibration"] / delivery.stock_calibration_audit.RESULT_JSON
    )
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["status_counts"]["ecart_majeur_de_calibration"] = 20
    _json(audit_path, payload)
    manifest_path = (
        roots["stock_calibration"] / delivery.stock_calibration_audit.MANIFEST_JSON
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_files"][delivery.stock_calibration_audit.RESULT_JSON] = {
        "size_bytes": audit_path.stat().st_size,
        "sha256": delivery.stock_calibration_audit._sha256(audit_path),
    }
    _json(manifest_path, manifest)

    with pytest.raises(delivery.PreliminaryDeliveryError, match="21 écarts majeurs"):
        delivery._validate_stock_calibration_audit(roots["stock_calibration"])


def test_delivery_inventory_and_content_tamper_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "delivery"
    delivery.build_preliminary_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        quality_dir=roots["quality"],
        network_map_html=roots["map"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        stock_calibration_audit_dir=roots["stock_calibration"],
        output_dir=output,
    )
    (output / "undeclared.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(delivery.PreliminaryDeliveryError, match="Inventaire"):
        delivery.validate_preliminary_delivery(output)
    (output / "undeclared.txt").unlink()
    (output / delivery.VIEW_FILES[2]).write_text("tampered", encoding="utf-8")
    with pytest.raises(delivery.PreliminaryDeliveryError, match="altéré"):
        delivery.validate_preliminary_delivery(output)


def test_resigned_manifest_cannot_hide_a_remote_resource_in_copied_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "delivery"
    manifest = delivery.build_preliminary_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        quality_dir=roots["quality"],
        network_map_html=roots["map"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        stock_calibration_audit_dir=roots["stock_calibration"],
        output_dir=output,
    )
    copied_map = output / delivery.MAP_ASSET
    copied_map.write_text(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<script src="https://example.invalid/plot.js"></script></head>'
        "<body>Carte modifiée</body></html>",
        encoding="utf-8",
    )
    copied_hash = delivery._sha256(copied_map)
    manifest["artifact_file_sha256"][delivery.MAP_ASSET] = copied_hash
    manifest["source_file_sha256"]["map/page"] = copied_hash
    manifest["network_map_size_bytes"] = copied_map.stat().st_size
    _resign_delivery_manifest(output, manifest)

    with pytest.raises(delivery.PreliminaryDeliveryError, match="Carte autonome invalide"):
        delivery.validate_preliminary_delivery(output)


def test_resigned_launcher_cannot_add_a_fourth_official_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "delivery"
    manifest = delivery.build_preliminary_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        quality_dir=roots["quality"],
        network_map_html=roots["map"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        stock_calibration_audit_dir=roots["stock_calibration"],
        output_dir=output,
    )
    launcher = output / delivery.LAUNCHER_FILE
    document = launcher.read_text(encoding="utf-8").replace(
        "</main>",
        f'<a href="{delivery.MAP_ASSET}">Quatrième lien</a></main>',
    )
    launcher.write_text(document, encoding="utf-8")
    manifest["artifact_file_sha256"][delivery.LAUNCHER_FILE] = delivery._sha256(
        launcher
    )
    _resign_delivery_manifest(output, manifest)

    with pytest.raises(delivery.PreliminaryDeliveryError, match="exactement les trois"):
        delivery.validate_preliminary_delivery(output)


def test_resigned_manifest_cannot_hide_removed_stock_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "delivery"
    manifest = delivery.build_preliminary_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        quality_dir=roots["quality"],
        network_map_html=roots["map"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        stock_calibration_audit_dir=roots["stock_calibration"],
        output_dir=output,
    )
    decision = output / delivery.VIEW_FILES[2]
    document = decision.read_text(encoding="utf-8").replace(
        delivery.STOCK_CALIBRATION_CLIENT_SENTENCES[0],
        "Avertissement supprimé.",
    )
    decision.write_text(document, encoding="utf-8")
    manifest["artifact_file_sha256"][delivery.VIEW_FILES[2]] = delivery._sha256(
        decision
    )
    _resign_delivery_manifest(output, manifest)

    with pytest.raises(delivery.PreliminaryDeliveryError, match="Limites métier"):
        delivery.validate_preliminary_delivery(output)


def test_output_must_be_external_and_new(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(delivery.PreliminaryDeliveryError, match="dossier externe"):
        delivery._assert_external_output(source / "delivery", [source])


def test_validate_only_cli_does_not_require_build_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "delivery"
    monkeypatch.setattr(
        delivery,
        "validate_preliminary_delivery",
        lambda root: {"status": "valid"},
    )
    assert delivery.main(["--validate-only", "--output-dir", str(output)]) == 0
