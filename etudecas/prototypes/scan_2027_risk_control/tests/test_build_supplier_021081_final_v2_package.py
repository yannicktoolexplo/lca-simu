from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_021081_final_v2_package as final,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_calibration_reports_discrete_bracket_without_interpolation(tmp_path: Path) -> None:
    rows = []
    values = {
        "intermediate_stock_only_300d": (300, 0.7984104352855397),
        "intermediate_stock_only_384d": (384, 0.8673400287356322),
        "intermediate_stock_only_385d": (385, 0.9707352941176471),
    }
    for state, (days, service) in values.items():
        rows.append(
            {
                "state_regime": state,
                "scenario_id": "baseline_observed_order_book",
                "state_regime_target_cover_days": days,
                "product_on_due_volume_proxy": service,
                "product_268967_released_qty": 100,
                "component_consumed_qty_kg": 0,
                "replayed_shipped_qty_kg": 1000,
                "product_on_due_delta_vs_paired_baseline": 0,
                "product_268967_released_qty_delta_vs_paired_baseline": 0,
            }
        )
    _write_csv(tmp_path / "baseline_calibration_metrics.csv", rows)
    result = final._collect_calibration(tmp_path)
    assert result["target_80"]["selected_cover_days"] == 300
    assert result["target_93"]["exact_state_found"] is False
    assert result["target_93"]["lower_cover_days"] == 384
    assert result["target_93"]["upper_cover_days"] == 385
    assert result["target_93"]["interpolation_allowed"] is False


def test_package_record_rejects_unaudited_source(tmp_path: Path) -> None:
    root = tmp_path / "source_v2"
    root.mkdir()
    (root / "required.csv").write_text("a\n1\n", encoding="utf-8")
    (root / "campaign_manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "execution_provenance_audit": {
                    "reproducibility_wording_allowed": False
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(final.FinalPackageError, match="Unaudited"):
        final._package_record(
            root,
            role="test",
            required_files=("required.csv",),
            require_v2_suffix=True,
        )


def test_autonomous_page_embeds_data_and_unit_boundary() -> None:
    payload = {
        "observed_2025_order_book": {
            "order_count": 23,
            "quantity_kg": 1_320_000,
            "supplier_rows": [{}, {}, {}, {}],
        },
        "evidence_dictionary": {
            "observed": "Donnée planifiée fournie, pas une livraison réelle.",
            "simulated": "Résultat calculé, pas une performance mesurée.",
            "priority_signal": "Point à vérifier, pas une probabilité.",
            "hypothesis": "Paramètre à valider.",
        },
        "service_metric": final.SERVICE_METRIC,
        "service_state_calibration": {
            "target_80": {"achieved_service": 0.7984},
            "target_93": {"interval_percentage": [86.73, 97.07]},
        },
        "state_layer_analysis": [],
        "drilldown_scenarios": [],
        "paired_causal_lot_proof": {
            "technical_rows_with_paired_receipt_effect": 23,
            "affected_opening_po_technical_row_count": 23,
            "technical_rows_with_paired_descendant_effect": 0,
        },
        "bom_unit_sensitivity": {
            "why_inconclusive": "L’essai n’arbitre pas l’unité.",
            "production_semantics": "28,8 M G + 3,2 M G = 32 M G.",
            "rows": [],
        },
        "orderbook_only_lanes": {
            "snapshot": {"lane_state_summaries": []},
            "prospective": {"lane_state_summaries": []},
            "paired_multiseed_confirmation": {
                "physical_engine_run_count": 40,
                "state_summaries": [],
            },
        },
        "limitations": [],
    }
    page = final._autonomous_html(payload)
    assert "aucune ressource externe" in page
    assert "L’essai n’arbitre pas l’unité" in page
    assert "86.73" in page and "97.07" in page
    assert "Confirmation sur dix répétitions comparables" in page
    assert "fréquence historique" in page
    assert "part simulée du volume demandé du produit 268967" in page
    assert "J0 à J719" in page
    assert "Calibrage diagnostique de l’état de stock 773474" in page
    assert "ni des cibles, ni une politique de stock, ni des actions" in page
    assert "Référence simulée à partir du snapshot 2025" in page
    assert "SIGNAL DE PRIORITÉ" in page
    assert "ni un numéro de commande industrielle ni un numéro de lot industriel" in page
    assert "donnée d’entrée du modèle à valider" in page
    assert "aucun effet client, aucun coût et aucune action corrective" in page
    assert "proche de la cible 80" not in page
    assert "<script src=" not in page


def test_business_labels_do_not_turn_diagnostic_states_into_actions() -> None:
    assert final._scenario_label("baseline_observed_order_book") == (
        "Référence simulée à partir du snapshot 2025"
    )
    for days in (300, 384, 385):
        label = final._state_label(f"intermediate_stock_only_{days}d")
        assert "Calibrage diagnostique" in label
        assert "hypothèse" in label
        assert "cible" not in label.lower()
        assert "action" not in label.lower()


def test_service_metric_names_product_demand_and_horizon() -> None:
    assert final.SERVICE_METRIC == {
        "metric_id": "product_on_due_volume_proxy",
        "product_id": "268967",
        "horizon_days": 720,
        "horizon_label": "J0 à J719",
        "label_fr": (
            "part simulée du volume demandé du produit 268967 servie "
            "à la date attendue"
        ),
        "interpretation_boundary": (
            "Indicateur conditionnel du modèle sur J0 à J719 ; ce n’est ni "
            "l’OTIF d’un fournisseur ni une performance observée."
        ),
    }


def test_masking_constants_use_corrected_not_retracted_ratio() -> None:
    assert final.MASKING_AUDIT["released_268967_lot_count"] == 29
    assert final.MASKING_AUDIT["stock_multiple_of_horizon_need"] == pytest.approx(
        0.8015550848
    )
    assert final.MASKING_AUDIT[
        "stock_plus_production_multiple_of_horizon_need"
    ] == pytest.approx(1.7557478861)
