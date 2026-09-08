from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_curves as curves,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_delivery as delivery,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_pipeline as pipeline,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_watcher as watcher,
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _paths(tmp_path: Path, *, action_root: Path | None = None) -> common.Stage2Paths:
    source = tmp_path / "sources"
    source.mkdir(exist_ok=True)
    return common.Stage2Paths(
        repo=Path(__file__).resolve().parents[4],
        v7_plan_dir=source / "plan",
        v7_run_dir=source / "run",
        trace_package_dir=source / "trace",
        bridge_json=source / "bridge.json",
        campaign_root=source / "campaign",
        results_dir=source / "results",
        stage1_supervision_dir=source / "stage1_supervision",
        observed_2025_dir=None,
        lot_replay_root=tmp_path / "lots",
        qualification_dir=tmp_path / "qualification",
        action_replay_root=action_root or tmp_path / "actions",
        curves_dir=tmp_path / "curves",
        registry_dir=tmp_path / "registry",
        final_html=tmp_path / "delivery" / "OUVRIR_V7.html",
        supervision_dir=tmp_path / "stage2_supervision",
    ).resolved()


def _observed_pack(tmp_path: Path) -> Path:
    root = tmp_path / "observed"
    root.mkdir()
    ca = [
        {
            "product_code": "268091",
            "ca_delivered_source_value": 90,
            "ca_lost_raw_source_value": 10,
            "ca_lost_negative_adjustments_source_value": -1,
            "lost_share_of_raw_potential": 0.1,
            "unit_note": "valeur monétaire; devise absente du CSV source",
            "interpretation_limit": "taux financier, pas service en unités",
        },
        {
            "product_code": "268967",
            "ca_delivered_source_value": 80,
            "ca_lost_raw_source_value": 20,
            "ca_lost_negative_adjustments_source_value": 0,
            "lost_share_of_raw_potential": 0.2,
            "unit_note": "valeur monétaire; devise absente du CSV source",
            "interpretation_limit": "taux financier, pas service en unités",
        },
    ]
    stocks = [
        {
            "series_id": "component_stock_cos",
            "stock_scope": "component_immobilized_accounting_value",
            "product_code": "",
            "source_family_label": "Cos",
            "mean_stock_value_source": 100,
            "last_stock_value_source": 120,
            "physical_quantity_available": "false",
            "unit_note": "valeur monétaire; devise absente du CSV source",
            "interpretation_limit": "valeur comptable agrégée, pas quantité",
        }
    ]
    _write_csv(root / "observed_ca_product_summary_2025.csv", ca)
    _write_csv(root / "observed_stock_value_summary_2025.csv", stocks)
    _write_csv(
        root / "validation_checks.csv",
        [{"check_id": "all", "status": "PASS", "detail": "ok"}],
    )
    bilan = {
        "schema_version": "etudecas.observed_2025_supply_bilan.v1",
        "currency_status": "not_declared_in_source; EUR_is_working_convention",
        "supplier_attribution_status": "not_supported_by_available_observed_files",
        "component_stock_product_mapping_status": "unresolved_conflicting_hypotheses",
        "ca_summary": [
            {
                **row,
                "ca_delivered_source_value": float(row["ca_delivered_source_value"]),
                "ca_lost_raw_source_value": float(row["ca_lost_raw_source_value"]),
                "ca_lost_negative_adjustments_source_value": float(
                    row["ca_lost_negative_adjustments_source_value"]
                ),
                "lost_share_of_raw_potential": float(
                    row["lost_share_of_raw_potential"]
                ),
            }
            for row in ca
        ],
        "stock_summary": [
            {
                **stocks[0],
                "mean_stock_value_source": 100.0,
                "last_stock_value_source": 120.0,
                "physical_quantity_available": False,
            }
        ],
    }
    (root / "bilan_observed_2025.json").write_text(
        json.dumps(bilan, ensure_ascii=False), encoding="utf-8"
    )
    names = [
        "bilan_observed_2025.json",
        "observed_ca_product_summary_2025.csv",
        "observed_stock_value_summary_2025.csv",
        "validation_checks.csv",
    ]
    manifest = {
        "schema_version": "etudecas.observed_2025_supply_bilan.manifest.v1",
        "all_validation_checks_pass": True,
        "files": [
            {
                "name": name,
                "size_bytes": (root / name).stat().st_size,
                "sha256": common.sha256_file(root / name),
            }
            for name in names
        ],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return root


def test_observed_pack_uses_pass_status_and_preserves_financial_limits(
    tmp_path: Path,
) -> None:
    root = _observed_pack(tmp_path)
    payload = common.validate_observed_2025_pack(root)
    assert payload is not None
    assert payload["products"][0]["negative_adjustments_source_value"] == -1
    assert payload["products"][0]["lost_share_of_raw_potential_pct"] == 10
    assert payload["stocks"][0]["physical_quantity_available"] is False
    assert payload["stocks"][0]["product_id"] == ""
    assert payload["supplier_causality_available"] is False


def test_observed_pack_rejects_tamper_and_component_product_mapping(
    tmp_path: Path,
) -> None:
    root = _observed_pack(tmp_path)
    rows = common._read_csv(root / "observed_stock_value_summary_2025.csv")  # noqa: SLF001
    rows[0]["product_code"] = "268091"
    _write_csv(root / "observed_stock_value_summary_2025.csv", rows)
    manifest = common.read_json(root / "manifest.json")
    for row in manifest["files"]:
        if row["name"] == "observed_stock_value_summary_2025.csv":
            row["size_bytes"] = (root / row["name"]).stat().st_size
            row["sha256"] = common.sha256_file(root / row["name"])
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(common.Stage2Error, match="Cos/Pharma"):
        common.validate_observed_2025_pack(root)


def _service_rows() -> list[dict[str, Any]]:
    return [
        {
            "day": day,
            "node_id": "C-XXXXX",
            "item_id": product,
            "demand_qty": 10,
            "required_with_backlog_qty": 15,
            "served_qty": 12,
            "backlog_end_qty": 3,
        }
        for day in range(curves.HORIZON_DAYS)
        for product in curves.PRODUCTS
    ]


def test_service_curve_uses_required_with_backlog_and_aggregate_client() -> None:
    output = curves._service_case(_service_rows())  # noqa: SLF001
    assert output[("268091", "service_a_l_heure", 28)][27] == pytest.approx(0.7)
    assert output[("global", "service_a_l_heure", 28)][27] == pytest.approx(0.7)
    assert output[("268091", "retard_client", 7)][6] == pytest.approx(3.0)


def test_service_curve_rejects_non_aggregated_client() -> None:
    rows = _service_rows()
    rows[0]["node_id"] = "REAL-CUSTOMER"
    with pytest.raises(curves.Stage2CurveError, match="C-XXXXX"):
        curves._service_case(rows)  # noqa: SLF001


def test_curve_inventory_is_exactly_108_and_uses_metric_specific_windows() -> None:
    stock_pairs = {(f"M-{index}", f"ITEM-{index}") for index in range(18)}
    keys = curves._expected_series_keys(stock_pairs)  # noqa: SLF001
    assert len(keys) == curves.EXPECTED_SERIES_COUNT == 108
    assert all(
        window == 28
        for _state, _domain, _entity, metric, window in keys
        if metric == "ecart_plan_lot"
    )
    assert all(
        window == 7
        for _state, _domain, _entity, metric, window in keys
        if metric == "penurie_entree"
    )
    series = []
    for state, domain, entity, metric, window in sorted(keys):
        series.append(
            {
                "state": state,
                "domain": domain,
                "entity": entity,
                "metric": metric,
                "rolling_window_days": window,
                "columns": ["day", "mean", "p10", "median", "p90"],
                "sample_count": 30,
                "points": [
                    [day, 1.0, 0.0, 1.0, 2.0]
                    for day in range(window - 1, curves.HORIZON_DAYS)
                ],
            }
        )
    payload = {"series": series}
    curves._validate_series_inventory(payload, stock_pairs)  # noqa: SLF001
    payload["series"] = series[:-1]
    with pytest.raises(curves.Stage2CurveError, match="108 séries"):
        curves._validate_series_inventory(payload, stock_pairs)  # noqa: SLF001


def test_curve_smoothing_metadata_names_both_constraint_windows() -> None:
    assert curves.SMOOTHING_CONTRACT == {
        "service_days": 28,
        "production_flow_days": 28,
        "stock_wip_backlog_days": 7,
        "lot_plan_gap_days": 28,
        "input_shortage_signal_days": 7,
        "complete_windows_only": True,
        "daily_raw_sources_retained_upstream": True,
    }


def _result_fixture() -> dict[str, Any]:
    values = {
        "op_100": {"global": 99.4, "268091": 99.2, "268967": 99.6},
        "op_93": {"global": 93.1, "268091": 92.8, "268967": 93.4},
        "op_80": {"global": 80.2, "268091": 79.9, "268967": 80.5},
    }
    return {
        "descriptive_diagnostics": {
            "seed_block_count": 150,
            "states": {
                state: {
                    **{
                        measure: {"pooled_service_pct": value}
                        for measure, value in measures.items()
                    },
                    "pooled_product_gap_pp": abs(
                        measures["268091"] - measures["268967"]
                    ),
                }
                for state, measures in values.items()
            },
        },
        "bootstrap": {
            "global_service_ci90_pct": {
                "op_93": {"lower_pct": 92.6, "upper_pct": 93.5},
                "op_80": {"lower_pct": 79.7, "upper_pct": 80.7},
            },
            "op100_one_sided_lower95_pct": {
                "global": 99.0,
                "268091": 98.8,
                "268967": 99.1,
            },
        },
        "fixed_triplet": [row.payload() for row in protocol_candidates()],
    }


def protocol_candidates() -> tuple[Any, ...]:
    return protocol_v7_candidates()


def protocol_v7_candidates() -> tuple[Any, ...]:
    # Avoid importing the large protocol twice in the test namespace.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_fresh_development_holdout_protocol_v7 as protocol,
    )

    return protocol.FIXED_TRIPLET


def test_validation_state_cards_use_150_seed_result_and_exact_interval_labels() -> None:
    assert delivery._number(0.0, label="zéro réel") == 0.0  # noqa: SLF001
    states = delivery._validation_states(_result_fixture())  # noqa: SLF001
    assert states[0]["planned_lead_offset_days"] == {
        "268091": 0.0,
        "268967": 0.0,
    }
    assert states[0]["measures"][0]["interval"]["label"] == (
        "borne basse unilatérale 95 %"
    )
    assert states[1]["measures"][0]["interval"]["label"] == (
        "intervalle bilatéral 90 %"
    )
    assert states[1]["measures"][1]["interval"]["low"] is None
    assert states[1]["planned_lead_offset_days"] == {
        "268091": 8.4,
        "268967": 80.6,
    }


def test_lane_sensitivity_uses_paired_differences_not_opposite_marginals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = []
    for mechanism in delivery.MECHANISM_ORDER:
        rows.append(
            {
                "analysis_level": "lane",
                "mechanism": mechanism,
                "target_product_id": "268091",
                "supplier_id": "SUPPLIER-A",
                "lane_id": "lane-a",
                "comparison_lane_id": "lane-a",
                "state_comparison_valid": "true",
                "comparable_seed_count": "26",
                "required_comparable_seed_count": "24",
                "priority_status": "state_specific_priority",
                "priority_status_op_100": "dossier_to_investigate",
                "priority_status_op_93": "dossier_to_investigate",
                "priority_status_op_80": "dossier_to_investigate",
                "rank_min_op_100": "1",
                "rank_max_op_100": "1",
                "rank_min_op_93": "1",
                "rank_max_op_93": "1",
                "rank_min_op_80": "1",
                "rank_max_op_80": "1",
                # The marginal means slope down because four non-comparable cases
                # dominate them; the signed paired conclusion slopes up.
                "fixed360_effect_mean_pp_op_100": "5",
                "fixed360_effect_mean_pp_op_93": "1",
                "fixed360_effect_mean_pp_op_80": "-2",
                "fixed360_op_93_minus_op_100_pp_mean": "2",
                "fixed360_op_93_minus_op_100_pp_ci95_low": "1",
                "fixed360_op_93_minus_op_100_pp_ci95_high": "3",
                "fixed360_op_80_minus_op_100_pp_mean": "4",
                "fixed360_op_80_minus_op_100_pp_ci95_low": "2",
                "fixed360_op_80_minus_op_100_pp_ci95_high": "6",
                "state_sensitivity_interpretation_fr": "effet apparié croissant",
            }
        )
    monkeypatch.setattr(delivery, "_bound_results_csv", lambda *_a: rows)
    parsed = delivery._lane_sensitivity(_paths(tmp_path))  # noqa: SLF001
    assert parsed[0]["states"]["op_80"]["effect_mean_pp"] == -2
    assert parsed[0]["paired_changes_vs_reference_pp"]["op_80"] == {
        "mean": 4.0,
        "ci95_low": 2.0,
        "ci95_high": 6.0,
    }
    html = delivery.render_html({"fixture": True})
    assert (
        "row.state_comparison_valid?paired.map(v=>v.mean)"
        ":order.map(s=>row.states[s].effect_mean_pp)" in html
    )


def test_portfolio_keeps_all_supplier_signals_without_forced_top_three() -> None:
    rows = []
    for mechanism in delivery.MECHANISM_ORDER:
        for index in range(5):
            rows.append(
                {
                    "mechanism": mechanism,
                    "supplier_id": f"S-{index}",
                    "priority_in_all_three_states": index < 2,
                    "robust_priority_in_all_three_states": index == 0,
                }
            )
    portfolio = delivery._portfolio_summary(rows)  # noqa: SLF001
    assert all(group["supplier_count"] == 5 for group in portfolio["mechanisms"])
    assert all(
        group["recurring_signal_count"] == 2 for group in portfolio["mechanisms"]
    )
    assert all(len(group["rows"]) == 5 for group in portfolio["mechanisms"])
    assert "aucun top 3" in portfolio["selection_rule"]


def _focus_rows() -> list[dict[str, Any]]:
    return [
        {
            "state": state,
            "mechanism": mechanism,
            "lane_id": delivery.FOCUS_LANE_ID,
            **delivery.FOCUS_IDENTITY,
            "priority_status": "no_detected_effect",
        }
        for state in delivery.STATE_ORDER
        for mechanism in delivery.MECHANISM_ORDER
    ]


def test_focus_338929_is_default_but_not_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        delivery.protocol_v7, "validate_plan", lambda *_a, **_k: object()
    )
    monkeypatch.setattr(
        delivery.traces_v7,
        "_campaign_lanes",
        lambda _plan: [
            {
                "lane_id": delivery.FOCUS_LANE_ID,
                **delivery.FOCUS_IDENTITY,
                "planned_lead_days": 42.0,
            }
        ],
    )
    result = delivery._focus(paths, _focus_rows(), [])  # noqa: SLF001
    assert result["requested_338929_present"] is True
    assert result["selected_for_detailed_replay"] is False
    assert result["planned_lead_days"] == pytest.approx(
        {"op_100": 42.0, "op_93": 50.4, "op_80": 59.5}
    )
    assert all(
        row["priority_status"] == "no_detected_effect"
        for row in result["aggregate_incident_results"]
    )


def test_focus_absent_without_detailed_selection_names_aggregate_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    identity = {
        "supplier_id": "SUP-OTHER",
        "item_id": "OTHER",
        "dst_node_id": "M-1810",
        "target_product_id": "268091",
    }
    lane_id = "other_lane"
    rows = [
        {
            "state": state,
            "mechanism": mechanism,
            "lane_id": lane_id,
            **identity,
            "priority_status": "no_detected_effect",
        }
        for state in delivery.STATE_ORDER
        for mechanism in delivery.MECHANISM_ORDER
    ]
    monkeypatch.setattr(
        delivery.protocol_v7, "validate_plan", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(
        delivery.traces_v7,
        "_campaign_lanes",
        lambda _plan: [{"lane_id": lane_id, **identity, "planned_lead_days": 42.0}],
    )
    result = delivery._focus(paths, rows, [])  # noqa: SLF001
    assert result["display_rule"] == (
        "338929 absent et aucune sélection détaillée; première voie agrégée "
        "affichée sans reclassement"
    )
    assert "dossier signé" not in result["display_rule"]


def test_nominal_selector_uses_exhaustive_french_business_labels() -> None:
    assert set(delivery.NOMINAL_METRIC_LABELS.values()) == {
        "Service à l'heure",
        "Retard client agrégé",
        "Production libérée",
        "Encours de production",
        "Stock de l'article entrant",
    }
    html = delivery.render_html({"fixture": True})
    assert "${esc(s.label_fr)} · ${esc(s.entity_label_fr)}" in html
    assert ">${esc(s.metric)} · ${esc(s.entity)}" not in html


def test_detailed_identity_canonicalises_prefixed_registry_item_only() -> None:
    assert delivery._canonical_identity_value("item_id", "item:338929") == "338929"  # noqa: SLF001
    assert delivery._canonical_identity_value("item_id", "338929") == "338929"  # noqa: SLF001
    assert (  # noqa: SLF001
        delivery._canonical_identity_value("lane_id", "item:338929") == "item:338929"
    )


def test_genealogy_keeps_all_native_quantity_kinds() -> None:
    row = {
        "parent_qty": 100,
        "child_qty": 90,
        "consumed_qty": 40,
        "released_qty_same_day": 35,
        "released_qty": 30,
        "service_event_qty_on_contacted_lot": 25,
        "uom": "UN",
    }
    details = delivery._genealogy_quantity_details(row)  # noqa: SLF001
    assert [entry["source_field"] for entry in details] == [
        "parent_qty",
        "child_qty",
        "consumed_qty",
        "released_qty_same_day",
        "released_qty",
        "service_event_qty_on_contacted_lot",
    ]
    assert all(entry["uom"] == "UN" for entry in details)
    html = delivery.render_html({"fixture": True})
    assert "g.quantity_details" in html
    assert "g.consumed_qty??g.released_qty" not in html


def test_j0_context_maps_all_six_native_metrics_to_client_units() -> None:
    rows = [
        {
            "dossier_id": "D1",
            "metric": metric,
            "measurement_kind": (
                "niveau de fin de journée"
                if metric in {"component_stock", "wip", "backlog"}
                else "flux cumulé sur la journée"
            ),
            "observation_convention": "valeur au premier jour de la fenêtre",
            "baseline_value_at_incident_j0": 0.0,
            "incident_value_at_incident_j0": 0.0,
        }
        for metric in delivery.J0_CLIENT_METRICS
    ]
    output = delivery._client_j0_rows(rows, "D1")  # noqa: SLF001
    assert len(output) == 6
    assert {row["label_fr"] for row in output} == {
        "Stock de l'article entrant",
        "Production libérée",
        "Encours de production",
        "Demande client agrégée",
        "Unités servies à l'heure",
        "Retard client agrégé",
    }
    assert {row["unit_fr"] for row in output} == {
        "UN en fin de journée",
        "UN sur la journée",
    }
    html = delivery.render_html({"fixture": True})
    assert "r.label_fr" in html and "r.unit_fr" in html
    assert "r.metric} à J0" not in html


def _gain_stats(value: float) -> dict[str, Any]:
    return {
        "count": 1,
        "mean": value,
        "median": value,
        "p10": value,
        "p90": value,
        "mean_ci95_low": value,
        "mean_ci95_high": value,
    }


def _action_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    result = {
        "dossier_id": "D1",
        "operating_point_id": "op_80",
        "mechanism": "transport_delay",
        "lane_id": delivery.FOCUS_LANE_ID,
        "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
        "item_id": delivery.FOCUS_IDENTITY["item_id"],
        "dst_node_id": delivery.FOCUS_IDENTITY["dst_node_id"],
        "target_product_id": delivery.FOCUS_IDENTITY["target_product_id"],
        "action_id": "future_departures_lead_reduction",
        "action_label_fr": "Réduction contractuelle du délai des futurs départs",
        "action_parameters": {"lead_time_adjustment_days": -14},
        "action_parameter_units": {"lead_time_adjustment_days": "jour"},
        "action_physical_scope": {
            "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
            "item_id": delivery.FOCUS_IDENTITY["item_id"],
            "dst_node_id": delivery.FOCUS_IDENTITY["dst_node_id"],
        },
        "limits_fr": "Seulement les futurs départs de cette voie.",
        "status": "estimated_on_physically_exercised_seeds",
        "paired_seed_count": 2,
        "physically_exercised_seed_count": 1,
        "gain_statistics": {
            "service_gain_pp": _gain_stats(10),
            "backlog_qty_days_avoided": _gain_stats(60),
            "production_released_gain_qty": _gain_stats(100),
        },
    }
    return (
        {
            "status": "complete_validated",
            "action_results": [result],
            "refused_actions": [],
        },
        {"checks": {"closed_loop_claimed": False}},
    )


def _action_row(*, included: bool, multiplier: float = 1.0) -> dict[str, Any]:
    return {
        "dossier_id": "D1",
        "operating_point_id": "op_80",
        "mechanism": "transport_delay",
        "lane_id": delivery.FOCUS_LANE_ID,
        "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
        "item_id": f"item:{delivery.FOCUS_IDENTITY['item_id']}",
        "dst_node_id": delivery.FOCUS_IDENTITY["dst_node_id"],
        "target_product_id": f"item:{delivery.FOCUS_IDENTITY['target_product_id']}",
        "action_id": "future_departures_lead_reduction",
        "included_in_action_gain_statistics": str(included).lower(),
        "baseline__impact_window_service_on_due_pct": 95 * multiplier,
        "incident_no_action__impact_window_service_on_due_pct": 80 * multiplier,
        "incident_with_action__service_on_due_pct": 90 * multiplier,
        "action_vs_incident__service_gain_pp": 10 * multiplier,
        "baseline__state_window_global_backlog_qty_days": 0,
        "incident_no_action__state_window_global_backlog_qty_days": 100 * multiplier,
        "incident_with_action__state_window_global_backlog_qty_days": 40 * multiplier,
        "action_vs_incident__backlog_qty_days_avoided": 60 * multiplier,
        "baseline__state_window_production_released_qty": 1000 * multiplier,
        "incident_no_action__state_window_production_released_qty": 800 * multiplier,
        "incident_with_action__state_window_production_released_qty": 900 * multiplier,
        "action_vs_incident__production_released_gain_qty": 100 * multiplier,
    }


def _selected_action_dossier() -> dict[str, str]:
    return {
        "dossier_id": "D1",
        "operating_point_id": "op_80",
        "mechanism": "transport_delay",
        "lane_id": delivery.FOCUS_LANE_ID,
        "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
        "item_id": f"item:{delivery.FOCUS_IDENTITY['item_id']}",
        "dst_node_id": delivery.FOCUS_IDENTITY["dst_node_id"],
        "target_product_id": f"item:{delivery.FOCUS_IDENTITY['target_product_id']}",
        "edge_id": "edge-focus",
        "priority_status": "dossier_to_investigate",
    }


def test_action_readout_excludes_non_exercised_seed_and_does_not_clamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    action_root = tmp_path / "actions"
    _write_csv(
        action_root / "action_replay_per_seed.csv",
        [_action_row(included=True), _action_row(included=False, multiplier=100)],
    )
    monkeypatch.setattr(
        delivery.actions_v4, "validate_action_results", lambda _root: _action_summary()
    )
    payload = delivery._action_results(  # noqa: SLF001
        _paths(tmp_path, action_root=action_root), [_selected_action_dossier()]
    )
    action = payload["actions"][0]
    assert action["physically_exercised_seed_count"] == 1
    service = next(row for row in action["metrics"] if row["id"] == "service")
    assert service["signed_action_effect"]["mean"] == 10
    assert service["signed_reference_minus_action_gap"]["mean"] == 5
    assert action["days_recovered_available"] is False
    assert action["lot_trace_available"] is False
    assert "action_parameters" not in action
    assert action["parameter_lines_fr"] == [
        "délai planifié des futurs départs réduit de 14 jours"
    ]


def test_action_presentation_rejects_unknown_internal_parameter() -> None:
    summary, _validation = _action_summary()
    result = summary["action_results"][0]
    result["action_parameters"] = {
        "lead_time_adjustment_days": -14,
        "magic_capacity": 999,
    }
    with pytest.raises(delivery.Stage2DeliveryError, match="Paramètre inconnu"):
        delivery._action_presentation(result)  # noqa: SLF001


def test_action_presentation_maps_stock_and_active_reallocation_to_french() -> None:
    stock = {
        "action_id": delivery.actions_v4.ACTION_STOCK,
        "action_parameters": {"measurement_start_stock_scale": 1.25},
        "action_parameter_units": {"measurement_start_stock_scale": "ratio_sans_unité"},
        "action_physical_scope": {
            "node_id": "M-1810",
            "item_id": "item:338929",
            "graph_opening_stock_qty": 100,
            "uom": "UN",
        },
    }
    stock_view = delivery._action_presentation(stock)  # noqa: SLF001
    assert stock_view["parameter_lines_fr"] == [
        "stock libre cible à J0 : 1.25 fois le stock initial signé (soit +25.0 %)"
    ]
    reallocation = {
        "action_id": delivery.actions_v4.ACTION_REALLOCATION,
        "action_parameters": {"target_lane_priority_weight": 0.6},
        "action_parameter_units": {
            "target_lane_priority_weight": "poids_relatif_sans_unité"
        },
        "action_physical_scope": {
            "target_supplier_id": "SUP-A",
            "item_id": "item:338929",
            "dst_node_id": "M-1810",
            "active_alternatives": [{"supplier_id": "SUP-B", "lane_id": "lane-b"}],
        },
    }
    reallocation_view = delivery._action_presentation(reallocation)  # noqa: SLF001
    assert reallocation_view["parameter_lines_fr"] == [
        "poids relatif conservé sur la voie ciblée : 60.0 %"
    ]
    assert "SUP-B (lane-b)" in reallocation_view["scope_lines_fr"][1]


def test_action_readout_rejects_gain_not_matching_signed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    action_root = tmp_path / "actions"
    row = _action_row(included=True)
    row["action_vs_incident__service_gain_pp"] = 11
    _write_csv(action_root / "action_replay_per_seed.csv", [row])
    monkeypatch.setattr(
        delivery.actions_v4, "validate_action_results", lambda _root: _action_summary()
    )
    with pytest.raises(delivery.Stage2DeliveryError, match="résumé signé"):
        delivery._action_results(  # noqa: SLF001
            _paths(tmp_path, action_root=action_root), [_selected_action_dossier()]
        )


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("operating_point_id", "op_93"),
        ("mechanism", "planned_delivery_shortfall"),
        ("lane_id", "wrong-lane"),
        ("supplier_id", "wrong-supplier"),
        ("item_id", "item:wrong-item"),
        ("dst_node_id", "wrong-site"),
        ("target_product_id", "item:wrong-product"),
        ("edge_id", "wrong-edge"),
        ("priority_status", "wrong-status"),
    ],
)
def test_action_readout_rejects_every_mismatched_dossier_identity_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    wrong_value: str,
) -> None:
    action_root = tmp_path / "actions"
    _write_csv(action_root / "action_replay_per_seed.csv", [_action_row(included=True)])
    summary, validation = _action_summary()
    summary["action_results"][0][field] = wrong_value
    monkeypatch.setattr(
        delivery.actions_v4,
        "validate_action_results",
        lambda _root: (summary, validation),
    )
    with pytest.raises(delivery.Stage2DeliveryError, match=field):
        delivery._action_results(  # noqa: SLF001
            _paths(tmp_path, action_root=action_root), [_selected_action_dossier()]
        )


def test_action_readout_keeps_never_exercised_action_without_inventing_gain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    action_root = tmp_path / "actions"
    _write_csv(
        action_root / "action_replay_per_seed.csv", [_action_row(included=False)]
    )
    summary, validation = _action_summary()
    result = summary["action_results"][0]
    result["status"] = "non_exercised_no_gain_estimate"
    result["paired_seed_count"] = 1
    result["physically_exercised_seed_count"] = 0
    result["gain_statistics"] = {
        key: {
            "count": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
        }
        for key in (
            "service_gain_pp",
            "backlog_qty_days_avoided",
            "production_released_gain_qty",
        )
    }
    monkeypatch.setattr(
        delivery.actions_v4,
        "validate_action_results",
        lambda _root: (summary, validation),
    )
    payload = delivery._action_results(  # noqa: SLF001
        _paths(tmp_path, action_root=action_root), [_selected_action_dossier()]
    )
    action = payload["actions"][0]
    assert action["physically_exercised_seed_count"] == 0
    assert all(metric["available"] is False for metric in action["metrics"])
    assert all(
        "aucun gain estimable" in metric["reason_fr"] for metric in action["metrics"]
    )


def test_html_is_three_view_offline_and_uses_required_client_vocabulary() -> None:
    html = delivery.render_html({"fixture": True})
    assert html.count('class="view') == 3
    assert "http://" not in html and "https://" not in html and "€" not in html
    folded = html.casefold()
    for phrase in (
        "aucune probabilité historique",
        "boucle ouverte",
        "aucun incident qualité",
        "aucune capacité/disponibilité modifiée",
        "clients agrégés",
        "lots simulés",
        "devise non renseignée",
    ):
        assert phrase in folded
    assert "ca non livré" not in folded
    assert "pire cas" not in folded
    assert "150 simulations indépendantes" in folded
    assert "30 scénarios aléatoires comparables" in folded
    assert "écart moyen de service sans incident − incident" in folded
    assert "positif = perte, négatif = amélioration" in folded
    assert "effet signé de l'action" in folded
    assert "positif = amélioration, négatif = dégradation" in folded
    assert "récupéré :" not in folded
    assert "perte moyenne de service" not in folded
    assert "mm28 pour service et flux, dont l'écart au plan de lots" in folded
    assert "mm7 pour stocks, encours, retard et signal de contrainte" in folded
    assert "m.recovered" not in html
    assert "m.signed_action_effect" in html
    assert "avec les mêmes aléas" not in folded
    assert "mêmes identifiants de scénarios" in folded
    assert "les trajectoires peuvent ensuite diverger avec l'état" in folded
    assert "intervalle central p10–p90" in folded
    assert "8 simulations sur 10" not in folded
    assert "8 résultats sur 10" not in folded


def test_prepare_supervision_creates_only_its_owned_directory(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    contract = pipeline.prepare_supervision(paths)
    assert contract["scientific_contract"][
        "signed_selection_preserved_without_override"
    ]
    assert paths.supervision_dir.is_dir()
    assert {path.name for path in paths.supervision_dir.iterdir()} == {
        pipeline.CONTRACT_NAME,
        pipeline.INVENTORY_NAME,
        pipeline.STATUS_NAME,
    }
    assert not any(path.exists() for path in paths.output_roots[:-1])
    assert not any(path.exists() for path in paths.output_files)


def test_source_inventory_tamper_is_fail_closed(tmp_path: Path) -> None:
    inventory = common.build_source_inventory(Path(__file__).resolve().parents[4])
    inventory["entries"][0]["sha256"] = "0" * 64
    unsigned = dict(inventory)
    unsigned.pop("inventory_signature")
    inventory["inventory_signature"] = common.stable_sha256(unsigned)
    with pytest.raises(common.Stage2Error, match="modifiée ou absente"):
        common.verify_source_inventory(inventory)


def test_real_source_inventory_contains_complete_critical_transitive_set() -> None:
    repo = Path(__file__).resolve().parents[4]
    paths = {path.relative_to(repo).as_posix() for path in common.source_paths(repo)}
    package = "etudecas/prototypes/scan_2027_risk_control"
    expected = {
        "etudecas/__init__.py",
        f"{package}/__init__.py",
        *(
            f"{package}/{name}.py"
            for name in (
                "calibration",
                "core",
                "decision",
                "experiments",
                "model",
                "risk_mapping",
                "supplier_priority_lot_replay_v4",
                "supplier_priority_action_replay_v4",
                "supplier_physical_cascade_qualification_v5",
                "supplier_v6_full_incident_lot_registry",
                "supplier_fresh_development_holdout_protocol_v7",
                "supplier_operating_point_full_campaign_v7",
                "finalize_supplier_operating_point_full_campaign_v7",
                "supplier_operating_point_full_campaign_v7_dashboard",
                "supplier_v7_campaign_trace_package",
                "build_validated_operating_points_v7",
                "continue_supplier_full_campaign_v7",
                "supplier_v7_stage2_common",
                "supplier_v7_stage2_curves",
                "supplier_v7_stage2_pipeline",
                "supplier_v7_stage2_delivery",
                "supplier_v7_stage2_watcher",
            )
        ),
    }
    assert len(paths) == 62
    assert expected <= paths


def test_failed_windows_lock_acquisition_is_not_followed_by_unlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if common.os.name != "nt":
        pytest.skip("contrôle spécifique au verrou Windows")
    import msvcrt

    modes: list[int] = []

    def fail_lock(_fd: int, mode: int, _length: int) -> None:
        modes.append(mode)
        raise OSError("busy")

    monkeypatch.setattr(msvcrt, "locking", fail_lock)
    with pytest.raises(common.Stage2Error, match="détient déjà le verrou"):
        with common.exclusive_lock(tmp_path / "lock"):
            raise AssertionError("verrou ne devait pas être acquis")
    assert modes == [msvcrt.LK_NBLCK]


@pytest.mark.parametrize("owned", ["lot_replay_root", "action_replay_root"])
def test_unplanned_v4_root_is_archived_for_fail_closed_resume(
    tmp_path: Path, owned: str
) -> None:
    paths = _paths(tmp_path)
    candidate = getattr(paths, owned)
    marker = candidate / "inputs" / "partial.csv"
    marker.parent.mkdir(parents=True)
    marker.write_text("incomplete", encoding="utf-8")
    destination = pipeline._archive_owned_unplanned_root(  # noqa: SLF001
        paths, candidate, owned
    )
    assert not candidate.exists()
    assert destination.is_relative_to(paths.supervision_dir / "recovery")
    assert (destination / "inputs" / "partial.csv").read_text(
        encoding="utf-8"
    ) == "incomplete"


def test_unplanned_root_recovery_refuses_any_non_owned_path(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source = paths.campaign_root
    source.mkdir(parents=True)
    (source / "protected.txt").write_text("source", encoding="utf-8")
    with pytest.raises(pipeline.Stage2PipelineError, match="sorties possédées"):
        pipeline._archive_owned_unplanned_root(paths, source, "forbidden")  # noqa: SLF001
    assert (source / "protected.txt").read_text(encoding="utf-8") == "source"


def test_lot_runner_recovers_partial_plan_root_before_v4_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    marker = paths.lot_replay_root / "inputs" / "partial.csv"
    marker.parent.mkdir(parents=True)
    marker.write_text("partial", encoding="utf-8")
    plan = {
        "plan_signature": "p" * 64,
        "dossiers": [{"dossier_id": "D-1", "arms": {}}],
    }

    def create(**_kwargs: Any) -> dict[str, Any]:
        assert not paths.lot_replay_root.exists()
        return plan

    monkeypatch.setattr(pipeline.lots_v4, "create_replay_plan", create)
    monkeypatch.setattr(pipeline, "_lot_receipt_valid", lambda *_args: {"ok": True})
    monkeypatch.setattr(
        pipeline.lots_v4,
        "finalize_replay",
        lambda _root: {
            "status": "complete_validated",
            "dossiers": [{}],
            "validation_signature": "v" * 64,
        },
    )
    result = pipeline._run_lot_replays(paths, [{}])  # noqa: SLF001
    assert result["status"] == "complete_validated"
    assert list((paths.supervision_dir / "recovery").rglob("partial.csv"))


def test_action_runner_recovers_partial_plan_root_before_v4_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    marker = paths.action_replay_root / "inputs" / "partial.csv"
    marker.parent.mkdir(parents=True)
    marker.write_text("partial", encoding="utf-8")
    plan = {
        "dossiers": [],
        "scientific_contract": {
            "closed_loop_claimed": False,
            "reference_engine_reruns": 0,
            "availability_or_capacity_invented": False,
        },
    }

    def create(**_kwargs: Any) -> dict[str, Any]:
        assert not paths.action_replay_root.exists()
        return plan

    receipt = {
        "status": "complete_no_representable_action",
        "planned_action_arm_count": 0,
    }
    summary = {"summary_signature": "s" * 64}
    validation = {
        "status": "complete_no_representable_action",
        "validation_signature": "v" * 64,
    }
    monkeypatch.setattr(pipeline.actions_v4, "create_action_plan", create)
    monkeypatch.setattr(
        pipeline.actions_v4, "run_action_replay", lambda *_args, **_kwargs: receipt
    )
    monkeypatch.setattr(
        pipeline.actions_v4,
        "finalize_action_replay",
        lambda _root: (summary, validation),
    )
    monkeypatch.setattr(
        pipeline.actions_v4,
        "validate_action_results",
        lambda _root: (summary, validation),
    )
    result = pipeline._run_actions(paths, [{}])  # noqa: SLF001
    assert result["status"] == "complete_no_representable_action"
    assert list((paths.supervision_dir / "recovery").rglob("partial.csv"))


def test_source_inventory_includes_initializers_and_relative_imports_and_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    files = {
        "etudecas/__init__.py": "from . import shared\n",
        "etudecas/shared.py": "VALUE = 1\n",
        "etudecas/pkg/__init__.py": "from . import core\n",
        "etudecas/pkg/core.py": "from .. import shared\nVALUE = shared.VALUE\n",
        "etudecas/pkg/runner.py": "from .core import VALUE\n",
    }
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    discovered = common._transitive_source_paths(  # noqa: SLF001
        {repo / "etudecas/pkg/runner.py"}, repo
    )
    relative_paths = {path.relative_to(repo).as_posix() for path in discovered}
    assert relative_paths == set(files)
    unsigned = {
        "schema_version": common.SOURCE_INVENTORY_SCHEMA_VERSION,
        "repo": str(repo.resolve()),
        "entry_count": len(discovered),
        "entries": [
            {
                "relative_path": path.relative_to(repo).as_posix(),
                "sha256": common.sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in discovered
        ],
        "critical_protocol_sha256": common.EXPECTED_PROTOCOL_SHA256,
    }
    inventory = common.signed(unsigned, "inventory_signature")
    monkeypatch.setattr(common, "source_paths", lambda _repo: discovered)
    common.verify_source_inventory(inventory)
    (repo / "etudecas/pkg/core.py").write_text(
        "from .. import shared\nVALUE = 2\n", encoding="utf-8"
    )
    with pytest.raises(common.Stage2Error, match="modifiée ou absente"):
        common.verify_source_inventory(inventory)


def test_bound_stage1_receipt_rejects_coherent_upstream_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    receipt = common.signed(
        {
            "schema_version": common.UPSTREAM_SCHEMA_VERSION,
            "status": "complete_validated",
            "v7_result_signature": "a" * 64,
        },
        "validation_signature",
    )
    receipt_path = tmp_path / common.STAGE1_RECEIPT_NAME
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(
        common, "validate_complete_stage1", lambda _paths: dict(receipt)
    )
    assert common.validate_bound_stage1_receipt(paths, receipt_path) == receipt
    replacement = common.signed(
        {
            "schema_version": common.UPSTREAM_SCHEMA_VERSION,
            "status": "complete_validated",
            "v7_result_signature": "b" * 64,
        },
        "validation_signature",
    )
    monkeypatch.setattr(common, "validate_complete_stage1", lambda _paths: replacement)
    with pytest.raises(common.Stage2Error, match="ont changé"):
        common.validate_bound_stage1_receipt(paths, receipt_path)


def test_pipeline_guard_revalidates_published_upstream_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    paths.supervision_dir.mkdir()
    (paths.supervision_dir / common.STAGE1_RECEIPT_NAME).write_text(
        "{}", encoding="utf-8"
    )
    relay = object.__new__(pipeline.Stage2Pipeline)
    relay.paths = paths
    relay.contract = {"contract_signature": "c" * 64}
    relay.inventory = {"fixture": True}
    calls: list[Path] = []
    monkeypatch.setattr(
        pipeline,
        "validate_bound_contract",
        lambda checked, **_kwargs: calls.append(checked.supervision_dir) or {},
    )
    monkeypatch.setattr(
        common,
        "validate_bound_stage1_receipt",
        lambda _paths, path: calls.append(path) or {},
    )
    relay.guard()
    assert calls == [
        paths.supervision_dir,
        paths.supervision_dir / common.STAGE1_RECEIPT_NAME,
    ]


def test_guard_rejects_coherent_observed_pack_substitution_after_armament(
    tmp_path: Path,
) -> None:
    observed = _observed_pack(tmp_path)
    base = _paths(tmp_path)
    paths = common.Stage2Paths(
        **{**base.__dict__, "observed_2025_dir": observed}
    ).resolved()
    relay = pipeline.Stage2Pipeline(paths)

    bilan_path = observed / "bilan_observed_2025.json"
    bilan = json.loads(bilan_path.read_text(encoding="utf-8"))
    bilan["coherent_substitution_marker"] = "changed after armament"
    bilan_path.write_text(json.dumps(bilan, ensure_ascii=False), encoding="utf-8")
    manifest_path = observed / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = next(
        row for row in manifest["files"] if row["name"] == "bilan_observed_2025.json"
    )
    declared["size_bytes"] = bilan_path.stat().st_size
    declared["sha256"] = common.sha256_file(bilan_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    assert common.validate_observed_2025_pack(observed) is not None
    with pytest.raises(pipeline.Stage2PipelineError, match="source liée"):
        relay.guard()


def test_watcher_refuses_double_detach_while_previous_child_is_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    paths.supervision_dir.mkdir()
    monkeypatch.setattr(
        watcher.pipeline,
        "prepare_supervision",
        lambda _paths: {"contract_signature": "a" * 64},
    )
    monkeypatch.setattr(
        watcher,
        "_latest_receipt",
        lambda *_a: {"child_pid": 123, "receipt_signature": "b" * 64},
    )
    monkeypatch.setattr(watcher, "_pid_alive", lambda _pid: True)
    with pytest.raises(watcher.Stage2WatcherError, match="déjà actif"):
        watcher._detach(  # noqa: SLF001
            paths, poll_seconds=1, max_wait_hours=1, startup_timeout_seconds=1
        )


def test_watcher_recovers_after_dead_process_with_new_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    paths.supervision_dir.mkdir()
    contract = {"contract_signature": "a" * 64}
    monkeypatch.setattr(
        watcher.pipeline, "prepare_supervision", lambda _paths: contract
    )
    monkeypatch.setattr(watcher, "_latest_receipt", lambda *_a: {"child_pid": 123})
    monkeypatch.setattr(watcher, "_pid_alive", lambda pid: pid == 456)
    monkeypatch.setattr(
        watcher.pipeline,
        "_verify_status",
        lambda *_a: {"status": "waiting"},
    )
    monkeypatch.setattr(
        watcher,
        "_reserve_attempt",
        lambda *_a: (2, "token", paths.supervision_dir / "reservation.json"),
    )
    ready = watcher._receipt_path(paths.supervision_dir, 2)  # noqa: SLF001

    class FakeProcess:
        pid = 456

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            ready.parent.mkdir(parents=True, exist_ok=True)
            ready.write_text("{}", encoding="utf-8")

        @staticmethod
        def poll() -> None:
            return None

    receipt = {
        "attempt": 2,
        "token": "token",
        "child_pid": 456,
        "contract_signature": "a" * 64,
        "lock_acquired_before_ready": True,
        "source_inventory_verified_before_ready": True,
        "keep_awake": {"requested": True, "active": True},
        "official_engine_started_before_ready": False,
        "receipt_signature": "b" * 64,
    }
    monkeypatch.setattr(watcher.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(watcher, "_read_signed", lambda *_a, **_k: receipt)
    result = watcher._detach(  # noqa: SLF001
        paths, poll_seconds=1, max_wait_hours=1, startup_timeout_seconds=1
    )
    assert result["status"] == "detached_ready"
    assert result["attempt"] == 2
    assert result["pid"] == 456


def test_watcher_complete_status_revalidates_delivery_before_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    paths.supervision_dir.mkdir()
    contract = {"contract_signature": "a" * 64}
    monkeypatch.setattr(watcher.pipeline, "prepare_supervision", lambda _p: contract)
    monkeypatch.setattr(watcher, "_latest_receipt", lambda *_a: None)
    monkeypatch.setattr(
        watcher.pipeline, "_verify_status", lambda *_a: {"status": "complete"}
    )
    calls: list[common.Stage2Paths] = []
    monkeypatch.setattr(
        delivery,
        "validate_delivery",
        lambda p: calls.append(p) or {"valid": True, "html_sha256": "c" * 64},
    )
    result = watcher._detach(  # noqa: SLF001
        paths, poll_seconds=1, max_wait_hours=1, startup_timeout_seconds=1
    )
    assert result["status"] == "already_complete"
    assert result["delivery"]["valid"] is True
    assert calls == [paths]
    monkeypatch.setattr(
        delivery,
        "validate_delivery",
        lambda _p: (_ for _ in ()).throw(
            delivery.Stage2DeliveryError("HTML final modifié")
        ),
    )
    with pytest.raises(delivery.Stage2DeliveryError, match="HTML final modifié"):
        watcher._detach(  # noqa: SLF001
            paths, poll_seconds=1, max_wait_hours=1, startup_timeout_seconds=1
        )


def test_watcher_invalid_ready_receipt_stops_spawned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    paths.supervision_dir.mkdir()
    contract = {"contract_signature": "a" * 64}
    monkeypatch.setattr(watcher.pipeline, "prepare_supervision", lambda _p: contract)
    monkeypatch.setattr(watcher, "_latest_receipt", lambda *_a: None)
    monkeypatch.setattr(
        watcher.pipeline, "_verify_status", lambda *_a: {"status": "waiting"}
    )
    monkeypatch.setattr(
        watcher,
        "_reserve_attempt",
        lambda *_a: (1, "token", paths.supervision_dir / "reservation.json"),
    )
    ready = watcher._receipt_path(paths.supervision_dir, 1)  # noqa: SLF001
    holder: dict[str, Any] = {}

    class FakeProcess:
        pid = 456

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.terminated = False
            holder["child"] = self
            ready.parent.mkdir(parents=True, exist_ok=True)
            ready.write_text("{}", encoding="utf-8")

        def poll(self) -> int | None:
            return -15 if self.terminated else None

        def terminate(self) -> None:
            self.terminated = True

        @staticmethod
        def wait(*, timeout: float) -> int:
            assert timeout == 10
            return -15

    invalid_receipt = {
        "attempt": 1,
        "token": "token",
        "child_pid": 456,
        "contract_signature": "a" * 64,
        "lock_acquired_before_ready": True,
        "source_inventory_verified_before_ready": True,
        "keep_awake": {"requested": True, "active": False},
        "official_engine_started_before_ready": False,
        "receipt_signature": "b" * 64,
    }
    monkeypatch.setattr(watcher.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(watcher, "_read_signed", lambda *_a, **_k: invalid_receipt)
    monkeypatch.setattr(watcher, "_pid_alive", lambda _pid: True)
    with pytest.raises(watcher.Stage2WatcherError, match="fils vivant et protégé"):
        watcher._detach(  # noqa: SLF001
            paths, poll_seconds=1, max_wait_hours=1, startup_timeout_seconds=1
        )
    assert holder["child"].terminated is True


def test_watcher_startup_timeout_stops_spawned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    paths.supervision_dir.mkdir()
    contract = {"contract_signature": "a" * 64}
    monkeypatch.setattr(watcher.pipeline, "prepare_supervision", lambda _p: contract)
    monkeypatch.setattr(watcher, "_latest_receipt", lambda *_a: None)
    monkeypatch.setattr(
        watcher.pipeline, "_verify_status", lambda *_a: {"status": "waiting"}
    )
    monkeypatch.setattr(
        watcher,
        "_reserve_attempt",
        lambda *_a: (1, "token", paths.supervision_dir / "reservation.json"),
    )
    holder: dict[str, Any] = {}

    class FakeProcess:
        pid = 456

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.terminated = False
            holder["child"] = self

        def poll(self) -> int | None:
            return -15 if self.terminated else None

        def terminate(self) -> None:
            self.terminated = True

        @staticmethod
        def wait(*, timeout: float) -> int:
            assert timeout == 10
            return -15

    ticks = iter((0.0, 0.2))
    monkeypatch.setattr(watcher.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(watcher.time, "monotonic", lambda: next(ticks))
    with pytest.raises(watcher.Stage2WatcherError, match="Délai dépassé"):
        watcher._detach(  # noqa: SLF001
            paths, poll_seconds=1, max_wait_hours=1, startup_timeout_seconds=0.1
        )
    assert holder["child"].terminated is True


class _FakeRelay:
    def __init__(self, _paths: common.Stage2Paths) -> None:
        self.status: dict[str, Any] = {}
        self.updates: list[tuple[str, str]] = []

    def guard(self) -> None:
        return None

    def update(self, status: str, step: str, _message: str, **extra: Any) -> None:
        self.updates.append((status, step))
        self.status = {"status": status, **extra}

    def execute(self) -> int:
        self.status = {"status": "complete", "results": {}}
        return 0


class _FakeKeeper:
    def __init__(self) -> None:
        self.active = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def payload(self) -> dict[str, Any]:
        return {"requested": True, "active": self.active}


@contextmanager
def _fake_lock(_path: Path):
    yield


def test_watcher_timeout_is_terminal_without_downstream_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        watcher.pipeline,
        "prepare_supervision",
        lambda _paths: {"contract_signature": "a" * 64},
    )
    monkeypatch.setattr(watcher.common, "exclusive_lock", _fake_lock)
    holder: dict[str, _FakeRelay] = {}

    def relay_factory(p: common.Stage2Paths) -> _FakeRelay:
        holder["relay"] = _FakeRelay(p)
        return holder["relay"]

    monkeypatch.setattr(watcher.pipeline, "Stage2Pipeline", relay_factory)
    monkeypatch.setattr(watcher, "KeepAwake", _FakeKeeper)
    monkeypatch.setattr(
        watcher.common, "probe_stage1", lambda _paths: "waiting_campaign_3330"
    )
    ticks = iter((0.0, 1.0))
    monkeypatch.setattr(watcher.time, "monotonic", lambda: next(ticks))
    result = watcher._child_main(  # noqa: SLF001
        paths,
        attempt=0,
        token="foreground",
        poll_seconds=0.1,
        max_wait_hours=0.0001,
    )
    assert result == 4
    assert holder["relay"].updates[-1][0] == "waiting_timeout"
    assert not any(path.exists() for path in paths.output_roots[:-1])


def test_watcher_stops_immediately_on_signed_scientific_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        watcher.pipeline,
        "prepare_supervision",
        lambda _paths: {"contract_signature": "a" * 64},
    )
    monkeypatch.setattr(watcher.common, "exclusive_lock", _fake_lock)
    holder: dict[str, _FakeRelay] = {}

    def relay_factory(p: common.Stage2Paths) -> _FakeRelay:
        holder["relay"] = _FakeRelay(p)
        return holder["relay"]

    monkeypatch.setattr(watcher.pipeline, "Stage2Pipeline", relay_factory)
    monkeypatch.setattr(watcher, "KeepAwake", _FakeKeeper)

    def rejected(_paths: common.Stage2Paths) -> str:
        raise common.Stage2ScientificNoGo("rejet signé")

    monkeypatch.setattr(watcher.common, "probe_stage1", rejected)
    result = watcher._child_main(  # noqa: SLF001
        paths,
        attempt=0,
        token="foreground",
        poll_seconds=0.1,
        max_wait_hours=1,
    )
    assert result == 3
    assert holder["relay"].updates[-1][0] == "scientific_no_go"
    assert not any(path.exists() for path in paths.output_roots[:-1])
