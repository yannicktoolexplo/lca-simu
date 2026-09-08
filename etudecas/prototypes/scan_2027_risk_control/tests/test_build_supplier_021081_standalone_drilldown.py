from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_021081_standalone_drilldown as dashboard,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def completed_campaign(tmp_path: Path) -> Path:
    root = tmp_path / "campaign_v1"
    root.mkdir()
    (root / "campaign_manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "days": 720,
                "engine_sha256": "e" * 64,
                "source_graph_sha256": "g" * 64,
                "orchestrator_sha256_at_process_start": "o" * 64,
            }
        ),
        encoding="utf-8",
    )
    write_csv(
        root / "scenario_design.csv",
        [{"scenario_id": "stress", "label": "Retenue qualité 180 jours"}],
    )
    write_csv(
        root / "screening_metrics.csv",
        [
            {
                "stage": "screening_prospective_cover",
                "scenario_id": "stress",
                "scope_id": "all_021081",
                "mechanism": "quality_hold",
                "seed": 42,
                "days": 720,
                "observed_order_count": 23,
                "observed_order_qty_kg": 1320000,
                "order_book_simulated_usable_qty_kg": 1200000,
                "order_book_simulated_quantity_loss_kg": 120000,
                "order_book_weighted_planned_usable_date_shift_days": 180,
                "order_book_after_horizon_qty_kg": 0,
                "product_on_due_volume_proxy": 0.998,
                "product_on_due_delta_vs_paired_baseline": 0,
                "product_backlog_qty_days_delta_vs_paired_baseline": 0,
                "component_stock_min_qty_kg": 10,
                "state_regime": "prospective_30d_cover",
                "state_regime_evidence_class": "simulated_hypothesis",
                "state_regime_target_cover_days": 30,
            }
        ],
    )
    audit = []
    for index in range(23):
        audit.append(
            {
                "source_row": index + 1,
                "shipment_id": f"opening_po_sr{index + 1}",
                "supplier_id": "SDC-VD0960508A",
                "planned_qty_before": 1000,
                "pulled_qty_after": 1000,
                "physical_shipped_qty_after": 1000,
                "usable_qty_after": 1000,
                "physical_delivery_day_before": 6,
                "physical_delivery_day_after": 6,
                "usable_day_before": 112,
                "usable_day_after": 292,
                "risk_event_ids": "evt",
                "risk_types": "quality_delay",
                "unsupported_risk_types": "",
            }
        )
    write_csv(
        root
        / "cases"
        / "prospective_30d_cover"
        / "stress"
        / "seed_42"
        / "proofs"
        / dashboard.AUDIT_NAME,
        audit,
    )
    return root


def test_package_payload_requires_complete_campaign(tmp_path: Path) -> None:
    root = completed_campaign(tmp_path)
    manifest = root / "campaign_manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["status"] = "running"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="not complete"):
        dashboard.package_payload(root)


def test_payload_has_23_audited_rows_and_keeps_provenance(tmp_path: Path) -> None:
    root = completed_campaign(tmp_path)
    payload = dashboard.build_payload([root], [])
    assert len(payload["cases"]) == 1
    case = payload["cases"][0]
    assert len(case["audits"]) == 23
    assert case["audits"][0]["horizon_status"] == "disponible dans l’horizon"
    assert payload["packages"][0]["manifest_sha256"]
    assert payload["masking_audit"]["stock_multiple_of_horizon_need"] == pytest.approx(
        0.8015550848
    )


def test_render_is_offline_and_uses_business_warnings(tmp_path: Path) -> None:
    payload = dashboard.build_payload([completed_campaign(tmp_path)], [])
    rendered = dashboard.render_html(payload)
    assert "Aucun écart client n’apparaît" in rendered
    assert "source_row est le numéro technique" in rendered
    assert "Unité à valider avec l’industriel" in rendered
    assert "https://" not in rendered
    assert "<script id=\"payload\" type=\"application/json\">" in rendered


def test_incomplete_ledger_case_is_not_displayed(tmp_path: Path) -> None:
    root = completed_campaign(tmp_path)
    audit = (
        root
        / "cases"
        / "prospective_30d_cover"
        / "stress"
        / "seed_42"
        / "proofs"
        / dashboard.AUDIT_NAME
    )
    rows = dashboard.read_csv(audit)[:22]
    write_csv(audit, rows)
    with pytest.raises(ValueError, match="No complete 23-line"):
        dashboard.build_payload([root], [])


def test_fifo_overlay_ledger_is_used_when_native_audit_is_empty(
    tmp_path: Path,
) -> None:
    root = completed_campaign(tmp_path)
    proofs = (
        root
        / "cases"
        / "prospective_30d_cover"
        / "stress"
        / "seed_42"
        / "proofs"
    )
    (proofs / dashboard.AUDIT_NAME).write_text("", encoding="utf-8")
    rows = [
        {
            "source_row": index + 1,
            "observed_order_id": f"Extract_En_cours.xlsx:{index + 1}",
            "supplier_id": "SDC-VD0960508A",
            "observed_quantity_kg": 1000,
            "simulated_usable_quantity_kg": 1000,
            "source_planned_physical_delivery_day": 6,
            "simulated_physical_delivery_day": 9,
            "source_planned_usable_day": 112,
            "simulated_usable_day": 115,
            "mechanism": "capacity_rationing",
            "order_risk_application_layer": "campaign_overlay_capacity_fallback",
        }
        for index in range(23)
    ]
    write_csv(proofs / dashboard.LEDGER_NAME, rows)
    case = dashboard.build_payload([root], [])["cases"][0]
    assert len(case["audits"]) == 23
    assert case["audits"][0]["physical_day_after"] == 9
    assert "overlay FIFO" in case["audits"][0]["application_layer"]
