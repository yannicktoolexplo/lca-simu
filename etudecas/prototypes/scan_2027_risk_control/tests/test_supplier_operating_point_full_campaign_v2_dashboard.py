from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v2_dashboard as dashboard,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _signed_payload(
    payload: dict[str, object], *, signature_field: str
) -> dict[str, object]:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {**payload, signature_field: hashlib.sha256(raw).hexdigest()}


def _metric_fields(effect: float) -> dict[str, object]:
    return {
        "global_service_loss_pp_mean": effect,
        "global_service_loss_pp_median": effect * 0.95,
        "global_service_loss_pp_ci95_low": max(0.0, effect - 0.2),
        "global_service_loss_pp_ci95_high": effect + 0.2,
        "global_service_loss_pp_p90": effect + 0.4,
        "global_service_loss_pp_positive_effect_rate": 0.9,
        "backlog_qty_days_per_demand_unit_mean": effect / 10,
        "backlog_qty_days_per_demand_unit_median": effect / 11,
        "backlog_qty_days_per_demand_unit_ci95_low": effect / 12,
        "backlog_qty_days_per_demand_unit_ci95_high": effect / 8,
        "backlog_qty_days_per_demand_unit_p90": effect / 7,
        "backlog_qty_days_per_demand_unit_positive_effect_rate": 0.9,
        "fed_product_production_loss_share_of_demand_mean": effect / 100,
        "fed_product_production_loss_share_of_demand_median": effect / 110,
        "fed_product_production_loss_share_of_demand_ci95_low": effect / 120,
        "fed_product_production_loss_share_of_demand_ci95_high": effect / 80,
        "fed_product_production_loss_share_of_demand_p90": effect / 70,
        "fed_product_production_loss_share_of_demand_positive_effect_rate": 0.8,
    }


def _results_fixture(
    root: Path, *, unexpected_mechanism: bool = False
) -> tuple[Path, Path]:
    results = root / "results"
    results.mkdir()
    signature = "campaign-fixture-v2"
    (results / dashboard.RESULT_FILES["validation"]).write_text(
        json.dumps(
            {
                "status": "complete_validated",
                "campaign_signature": signature,
                "evidence_class": "conditional_reproducible_simulation_hypothesis",
                "historical_incident_probability_estimated": False,
                "expected_contract": {
                    "mechanisms": list(dashboard.MECHANISMS),
                    "paired_repetition_count": 2,
                    "quality_branch_included": False,
                    "availability_incident_included": False,
                },
                "comparability_checks": {
                    "complete_3x18x2x30_matrix": True,
                    "same_repetitions_in_every_cell": True,
                    "same_engine_sha256": True,
                    "same_campaign_signature": True,
                    "lane_identity_invariant": True,
                    "baseline_pairing_complete": True,
                    "paired_warmup_state_identical": True,
                    "shipment_set_and_incident_trace_proven": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    suppliers = (
        ("S-338", "338929", "M-1810", "L-338"),
        ("S-344", "344135", "M-1430", "L-344"),
        ("S-029", "029313", "M-1810", "L-029"),
    )
    services = {"op_100": 100.0, "op_93": 93.2, "op_80": 80.4}
    supplier_rows: list[dict[str, object]] = []
    lane_rows: list[dict[str, object]] = []
    priority_rows: list[dict[str, object]] = []
    for state_index, state in enumerate(dashboard.STATE_IDS):
        for supplier_index, (supplier, item, destination, lane) in enumerate(suppliers):
            dominant = (
                "transport_delay"
                if (supplier_index + state_index) % 2 == 0
                else "planned_delivery_shortfall"
            )
            for mechanism_index, mechanism in enumerate(dashboard.MECHANISMS):
                current_mechanism = (
                    "unregistered_mechanism"
                    if unexpected_mechanism
                    and state_index == supplier_index == mechanism_index == 0
                    else mechanism
                )
                effect = (
                    3.0 - supplier_index * 0.5 - mechanism_index * 0.3 + state_index
                )
                common = {
                    "operating_point_id": state,
                    "operating_point_service_pct": services[state],
                    "mechanism": current_mechanism,
                    "supplier_id": supplier,
                    "item_id": item,
                    "dst_node_id": destination,
                    "paired_repetition_count": 2,
                    "physical_exercise_rate": 1.0,
                    "target_planned_qty_mean": 2400 + supplier_index * 100,
                    "target_shipment_count_mean": 4,
                    "target_uom": "UN",
                    **_metric_fields(effect),
                }
                supplier_rows.append({**common, "representative_lane_id": lane})
                lane_rows.append({**common, "lane_id": lane})
            priority_rows.append(
                {
                    "position": supplier_index + 1,
                    "operating_point_id": state,
                    "mechanism": dominant,
                    "supplier_id": supplier,
                    "positive_mean_effect": True,
                    "top3_inclusion_probability": 0.95 - supplier_index * 0.1,
                    "rank_ci95_low": supplier_index + 1,
                    "rank_ci95_high": supplier_index + 2,
                }
            )
    _write_csv(results / dashboard.RESULT_FILES["supplier_statistics"], supplier_rows)
    _write_csv(results / dashboard.RESULT_FILES["lane_statistics"], lane_rows)
    _write_csv(results / dashboard.PRIORITY_FILE_CANDIDATES[1], priority_rows)
    stability_rows = []
    for supplier, *_rest in suppliers:
        stability_rows.append(
            {
                "supplier_id": supplier,
                "in_top3_op_100": True,
                "in_top3_op_93": True,
                "in_top3_op_80": True,
                "same_dominant_reason_when_in_top3": supplier == "S-338",
                "dominant_reasons_when_in_top3": "transport_delay",
            }
        )
    _write_csv(results / dashboard.STABILITY_FILE_CANDIDATES[1], stability_rows)
    achieved_services = {
        "op_100": (100.0, 99.8, 99.7, 99.9),
        "op_93": (93.0, 92.6, 93.1, 92.1),
        "op_80": (80.0, 79.5, 82.0, 77.0),
    }
    operating_point_registry = _signed_payload(
        {
            "schema_version": "fixture.operating_point_preflight.v2",
            "campaign_signature": signature,
            "status": dashboard.SIGNED_OPERATING_POINT_STATUS,
            "campaign_seed_count": 2,
            "states": [
                {
                    "operating_point_id": state,
                    "target_service_pct": values[0],
                    "service_global_ratio_of_sums_pct": values[1],
                    "service_268091_ratio_of_sums_pct": values[2],
                    "service_268967_ratio_of_sums_pct": values[3],
                    "accepted": True,
                    "failures": [],
                }
                for state, values in achieved_services.items()
            ],
        },
        signature_field="preflight_signature",
    )
    (results / dashboard.RESULT_FILES["operating_point_registry"]).write_text(
        json.dumps(operating_point_registry, ensure_ascii=False),
        encoding="utf-8",
    )
    targets: list[dict[str, object]] = []
    coverage: list[dict[str, object]] = []
    for _supplier, item, destination, lane in suppliers:
        for seed in (1, 2):
            coverage.append(
                {
                    "lane_id": lane,
                    "seed": seed,
                    "state_comparison_valid": True,
                }
            )
            for state_index, state in enumerate(dashboard.STATE_IDS):
                targets.append(
                    {
                        "operating_point_id": state,
                        "seed": seed,
                        "lane_id": lane,
                        "item_id": item,
                        "dst_node_id": destination,
                        "target_window_days": 42,
                        "target_window_start_day": 100 + seed,
                        "target_window_end_day": 141 + seed,
                        "target_planned_qty": 2000 + 100 * state_index,
                        "target_shipment_count": 3 + state_index,
                        "target_uom": "UN",
                    }
                )
    registry = root / "target_registry.json"
    registry.write_text(
        json.dumps(
            {
                "campaign_signature": signature,
                "disruption_window_days": 42,
                "targets": targets,
                "coverage": coverage,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return results, registry


def test_builds_lightweight_three_view_offline_dashboard(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    output = tmp_path / "OUVRIR_CAMPAGNE_FOURNISSEURS_V2.html"
    source_before = {path: path.read_bytes() for path in (*results.iterdir(), registry)}

    manifest = dashboard.build_dashboard(
        results_dir=results,
        target_registry_path=registry,
        output_html=output,
    )

    document = output.read_text(encoding="utf-8")
    assert manifest["view_count"] == 3
    assert manifest["offline_single_file"] is True
    assert manifest["all_lanes_cross_state_comparable"] is True
    assert manifest["supplier_count"] == 3
    assert '"windowDays":42' in document
    assert '"globalServicePct":92.6' in document
    assert '"pf091ServicePct":93.1' in document
    assert '"pf967ServicePct":92.1' in document
    assert "SIMULÉ · TAUX DE SERVICE GLOBAL OBTENU" in document
    assert "SIMULÉ · PF091 (268091)" in document
    assert "SIMULÉ · PF967 (268967)" in document
    assert "HYPOTHÈSE · POINT" in document
    assert "registre final validé des points de fonctionnement" in document
    assert document.count('<section class="view') == 3
    assert all(
        word in document
        for word in ("OBSERVÉ", "SIMULÉ", "SIGNAL DE PRIORITÉ", "HYPOTHÈSE")
    )
    assert "Retard de transport de 120 jours" in document
    assert "Livraison planifiée reçue à 50 %" in document
    assert "généalogie lot par lot sera ajoutée après le replay ciblé" in document
    assert "https://" not in document
    assert "http://" not in document
    assert '<script src="' not in document
    assert '<link rel="stylesheet"' not in document
    assert "availability" not in document.casefold()
    assert "quality_hold" not in document.casefold()
    assert output.stat().st_size < 250_000
    for path, before in source_before.items():
        assert path.read_bytes() == before


def test_state_service_rates_come_from_signed_final_registry(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)

    payload = dashboard.load_dashboard_data(
        results_dir=results,
        target_registry_path=registry,
    )

    by_state = {row["id"]: row for row in payload["states"]}
    assert by_state["op_100"] == {
        "id": "op_100",
        "label": "Réseau robuste",
        "pointLabel": "100",
        "targetServicePct": pytest.approx(100.0),
        "globalServicePct": pytest.approx(99.8),
        "pf091ServicePct": pytest.approx(99.7),
        "pf967ServicePct": pytest.approx(99.9),
        "servicePct": pytest.approx(99.8),
    }
    assert by_state["op_93"]["globalServicePct"] == pytest.approx(92.6)
    assert by_state["op_93"]["pf091ServicePct"] == pytest.approx(93.1)
    assert by_state["op_93"]["pf967ServicePct"] == pytest.approx(92.1)
    assert by_state["op_80"]["globalServicePct"] == pytest.approx(79.5)
    assert payload["operatingPointRegistry"]["validated"] is True
    assert payload["operatingPointRegistry"]["sourceFile"] == (
        "operating_point_preflight.json"
    )


def test_rejects_unsigned_or_tampered_operating_point_registry(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    preflight_path = results / dashboard.RESULT_FILES["operating_point_registry"]
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload["states"][1]["service_268091_ratio_of_sums_pct"] = 12.3
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(dashboard.DashboardInputError, match="signature.*incohérente"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_signed_registry_missing_a_finished_product_rate(
    tmp_path: Path,
) -> None:
    results, registry = _results_fixture(tmp_path)
    preflight_path = results / dashboard.RESULT_FILES["operating_point_registry"]
    payload = json.loads(preflight_path.read_text(encoding="utf-8"))
    payload.pop("preflight_signature")
    payload["states"][2].pop("service_268967_ratio_of_sums_pct")
    payload = _signed_payload(payload, signature_field="preflight_signature")
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(dashboard.DashboardInputError, match="service PF967 op_80"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_marks_lane_non_comparable_without_hiding_state_results(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["coverage"][0]["state_comparison_valid"] = False
    registry.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "dashboard.html"

    manifest = dashboard.build_dashboard(
        results_dir=results,
        target_registry_path=registry,
        output_html=output,
    )

    assert manifest["all_lanes_cross_state_comparable"] is False
    document = output.read_text(encoding="utf-8")
    assert "COMPARAISON INTER-ÉTATS NON VALIDÉE" in document
    assert '"comparisonValid":false' in document
    assert '"campaignStatus":"complete_validated"' in document


def test_prefers_new_by_cause_priority_contract(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    legacy_priority = results / dashboard.PRIORITY_FILE_CANDIDATES[1]
    with legacy_priority.open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    lane_by_supplier = {
        "S-338": "L-338",
        "S-344": "L-344",
        "S-029": "L-029",
    }
    modern_rows = [
        {
            "operating_point_id": row["operating_point_id"],
            "mechanism": row["mechanism"],
            "supplier_id": row["supplier_id"],
            "exposed_lane_id": lane_by_supplier[row["supplier_id"]],
            "fixed360_effect_mean_pp": 2.4,
            "bootstrap_ci95_low": 2.0,
            "bootstrap_ci95_high": 2.8,
            "top3_inclusion_probability": 0.91,
            "rank_median": row["position"],
            "rank_ci95_low": row["position"],
            "rank_ci95_high": int(row["position"]) + 1,
            "model_effect_detected": True,
            "priority_status": "robust_priority",
            "impact_masked_by_existing_backlog": False,
            "horizon_dependent": False,
            "state_comparison_valid": True,
        }
        for row in source_rows
    ]
    _write_csv(results / dashboard.PRIORITY_FILE_CANDIDATES[0], modern_rows)
    legacy_priority.unlink()
    legacy_stability = results / dashboard.STABILITY_FILE_CANDIDATES[1]
    with legacy_stability.open("r", encoding="utf-8", newline="") as handle:
        stability_source = list(csv.DictReader(handle))
    modern_stability = [
        {
            "mechanism": "transport_delay",
            "supplier_id": row["supplier_id"],
            "priority_status": "robust_priority",
        }
        for row in stability_source
    ]
    _write_csv(results / dashboard.STABILITY_FILE_CANDIDATES[0], modern_stability)
    legacy_stability.unlink()

    payload = dashboard.load_dashboard_data(
        results_dir=results,
        target_registry_path=registry,
    )

    assert payload["priorities"]
    assert all(
        row["priorityGroup"] == "robust_priority" for row in payload["priorities"]
    )
    assert all(
        row["service"]["mean"] == pytest.approx(2.4) for row in payload["priorities"]
    )
    assert all(row["comparisonValid"] is True for row in payload["priorities"])


def test_accepts_v3_lane_contract_registry_threshold(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    lane_ids = sorted({row["lane_id"] for row in payload["targets"]})
    payload.pop("coverage")
    payload["campaign_seeds"] = [1, 2]
    payload["lane_contracts"] = [
        {
            "lane_id": lane,
            "comparable_campaign_seed_count": 2 if lane != "L-029" else 1,
            "required_comparable_seed_count": 2,
            "state_comparison_valid": lane != "L-029",
        }
        for lane in lane_ids
    ]
    registry.write_text(json.dumps(payload), encoding="utf-8")

    loaded = dashboard.load_dashboard_data(
        results_dir=results,
        target_registry_path=registry,
    )

    assert loaded["targetRegistry"]["validLaneCount"] == 2
    assert loaded["targetLanes"]["L-338"]["requiredComparisonCount"] == 2
    assert loaded["targetLanes"]["L-029"]["comparisonValid"] is False


def test_without_registry_disables_cross_state_claim(tmp_path: Path) -> None:
    results, _registry = _results_fixture(tmp_path)
    _registry.unlink()
    output = tmp_path / "dashboard.html"

    manifest = dashboard.build_dashboard(results_dir=results, output_html=output)

    assert manifest["target_registry_available"] is False
    assert manifest["all_lanes_cross_state_comparable"] is False
    assert "Registre de fenêtres communes absent" in output.read_text(encoding="utf-8")


def test_rejects_registry_with_mixed_window_durations(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["targets"][0]["target_window_days"] = 1
    registry.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(dashboard.DashboardInputError, match="durée de fenêtre unique"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_unregistered_incident_mechanism(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path, unexpected_mechanism=True)

    with pytest.raises(dashboard.DashboardInputError, match="Mécanismes inattendus"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_refuses_to_overwrite_an_existing_html(tmp_path: Path) -> None:
    results, registry = _results_fixture(tmp_path)
    output = tmp_path / "dashboard.html"
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refus d'écraser"):
        dashboard.build_dashboard(
            results_dir=results,
            target_registry_path=registry,
            output_html=output,
        )
    assert output.read_text(encoding="utf-8") == "existing"


def test_embedded_data_cannot_close_its_script_element() -> None:
    encoded = dashboard._safe_json({"supplier": "</script><script>alert(1)</script>"})

    assert "</script>" not in encoded
    assert "\\u003c/script\\u003e" in encoded
