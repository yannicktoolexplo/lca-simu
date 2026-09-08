from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v5_final_standalone_delivery as delivery,
)


def _base_payload(*, complete: bool = True) -> dict[str, object]:
    service = {"mean": 2.4, "p10": 1.1, "p90": 3.7}
    return {
        "campaign": {
            "states": [
                {
                    "id": "op_93",
                    "label": "Situation dégradée proche de 93 %",
                    "globalServicePct": 93.1,
                }
            ],
            "mechanisms": [
                {
                    "id": "transport_delay",
                    "label": "Retard de transport de 120 jours",
                    "hypothesis": "Les expéditions ciblées arrivent 120 jours plus tard.",
                },
                {
                    "id": "planned_delivery_shortfall",
                    "label": "Quantité normalement livrable divisée par deux",
                    "hypothesis": "La quantité normalement livrable est divisée par deux.",
                },
            ],
            "repetitions": 30,
            "laneCount": 18,
            "priorities": [
                {
                    "state": "op_93",
                    "mechanism": "transport_delay",
                    "lane": "lane-338",
                    "supplier": "S-338",
                    "item": "338929",
                    "destination": "M-1810",
                    "targetProduct": "268091",
                    "position": 1,
                    "supplementaryBacklogSignal": False,
                    "service": service,
                    "backlog": {"mean": 0.0},
                }
            ],
            "matrix": {
                "baselineRows": 90,
                "incidentRows": 3240,
                "totalRows": 3330,
            },
            "lotSelection": {"dossiers": [{"dossierId": "dossier_fixture"}]},
        },
        "lots": {
            "status": "complete_validated",
            "dossiers": [
                {
                    "id": "dossier_fixture",
                    "state": "op_93",
                    "mechanism": "transport_delay",
                    "supplier": "S-338",
                    "lane": "lane-338",
                    "item": "338929",
                    "destination": "M-1810",
                    "targetProduct": "268091",
                    "exercisedCount": 27,
                    "traceCounts": {
                        "shipments": 1,
                        "material_receipts": 1,
                        "consumptions": 1,
                        "campaigns": 1,
                        "batches": 1,
                        "finished_lots": 1 if complete else 0,
                        "client_events": 1 if complete else 0,
                        "clients": 1 if complete else 0,
                    },
                    "chain": [],
                    "chainRowsTotal": 0,
                    "chainRowsShown": 0,
                    "kpis": {
                        "service_loss_pp": 2.2,
                        "on_due_units_lost": 120,
                    },
                    "lags": [],
                }
            ],
        },
        "actions": {
            "status": "complete_no_representable_action",
            "results": [],
            "refusals": [],
        },
        "package": {"campaignResultCount": 3330},
    }


def _qualification(*, complete: bool = True) -> dict[str, object]:
    counts = {
        "shipments": 1,
        "material_receipts": 1,
        "consumptions": 1,
        "campaigns": 1,
        "batches": 1,
        "finished_lots": 1 if complete else 0,
        "client_events": 1 if complete else 0,
        "clients": 1 if complete else 0,
    }
    selected_label = (
        "Trace native complète jusqu’au client agrégé — hors preuve de réponse MRP"
        if complete
        else "Trace physique partielle — arrêt avant le client agrégé"
    )
    lanes = [
        {
            "lane_id": "lane-338" if index == 0 else f"lane-{index:02d}",
            "proof_level": (
                ("complete" if complete else "partial")
                if index == 0
                else "not_exercised"
            ),
            "display_label_fr": (
                selected_label if index == 0 else "Incident non exercé physiquement"
            ),
            "complete_cascade_label_allowed": False,
            "full_dynamic_stock_mrp_production_service_cascade_proven": False,
        }
        for index in range(18)
    ]
    return {
        "status": "complete_qualified",
        "qualification_signature": "q" * 64,
        "scope_signature": "s" * 64,
        "counts": {
            "dynamic_mrp_lane_count": 2,
            "static_mrp_lane_count": 16,
            "full_dynamic_cascade_proven_count": 0,
        },
        "lanes": lanes,
        "dossiers": [
            {
                "dossier_id": "dossier_fixture",
                "proof_level": "complete" if complete else "partial",
                "display_label_fr": selected_label,
                "mrp_requirement_mode": "dynamic_explicit",
                "trace_counts": counts,
                "missing_native_trace_stages": (
                    [] if complete else ["finished_lots", "client_events"]
                ),
                "campaign_shipment_exercised": True,
                "replay_shipment_to_receipt_exercised": True,
                "complete_cascade_label_allowed": False,
                "full_dynamic_stock_mrp_production_service_cascade_proven": False,
            }
        ],
    }


def _inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, complete: bool = True
) -> tuple[Path, Path, Path, Path, Path]:
    campaign = tmp_path / "campaign"
    results = tmp_path / "results"
    registry = tmp_path / "registry.json"
    replay = tmp_path / "replay"
    for directory in (campaign, results, replay):
        directory.mkdir()
    registry.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        delivery.delivery_v4,
        "build_delivery_payload",
        lambda **_: (_base_payload(complete=complete), {"campaign": "fixture"}),
    )
    qualification_dir = tmp_path / "qualification"
    qualification_dir.mkdir()
    return campaign, results, registry, replay, qualification_dir


def test_builds_exactly_three_v5_business_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry, replay, qualification_dir = _inputs(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        delivery.physical_qualification,
        "validate_qualification_sidecar",
        lambda **_: _qualification(),
    )
    output = tmp_path / "delivery" / "OUVRIR_RESULTATS_SUPPLY_CHAIN_V5.html"

    manifest = delivery.build_delivery(
        campaign_root=campaign,
        results_dir=results,
        curves_dir=None,
        replay_root=replay,
        qualification_dir=qualification_dir,
        output_html=output,
        target_registry_path=registry,
    )

    document = output.read_text(encoding="utf-8")
    assert document.count('class="view') == 3
    assert "1. Incident fournisseur" in document
    assert "2. Lots, client et impact" in document
    assert "3. Leviers et risque restant" in document
    assert "Trace native complète jusqu’au client agrégé" in document
    assert "ce n’est pas la moyenne" in document
    assert "moyenne et la variation P10–P90" in document
    assert "Risque restant" in document
    assert "retour sur investissement" in document
    assert "CAMPAGNE FOURNISSEURS V4" not in document
    assert "cascade complète" not in document.casefold()
    assert "sweep" not in document.casefold()
    assert " gate " not in document.casefold()
    assert "hash" not in document.casefold()
    assert manifest["view_count"] == 3
    assert manifest["scientific_scope"]["full_dynamic_cascade_claimed"] is False
    assert delivery.validate_delivery(output)["valid"] is True


def test_keeps_partial_trace_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry, replay, qualification_dir = _inputs(
        tmp_path, monkeypatch, complete=False
    )
    monkeypatch.setattr(
        delivery.physical_qualification,
        "validate_qualification_sidecar",
        lambda **_: _qualification(complete=False),
    )
    payload, _bindings = delivery.build_delivery_payload(
        campaign_root=campaign,
        results_dir=results,
        curves_dir=None,
        replay_root=replay,
        qualification_dir=qualification_dir,
        output_html=tmp_path / "delivery.html",
        target_registry_path=registry,
    )

    proof = payload["lots"]["dossiers"][0]["traceProof"]
    assert proof["level"] == "partial"
    assert proof["label"] == "Trace physique partielle — arrêt avant le client agrégé"
    assert payload["lots"]["demonstrationStatus"] == "partial_trace_only"
    document = delivery.render_html(payload)
    assert (
        "Le livrable reste publiable avec une démonstration physique partielle"
        in document
    )


def test_refuses_complete_label_when_one_required_stage_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry, replay, qualification_dir = _inputs(
        tmp_path, monkeypatch
    )
    inconsistent = _qualification()
    inconsistent["dossiers"][0]["trace_counts"]["client_events"] = 0
    monkeypatch.setattr(
        delivery.physical_qualification,
        "validate_qualification_sidecar",
        lambda **_: inconsistent,
    )

    with pytest.raises(delivery.V5FinalDeliveryError, match="contraire aux preuves"):
        delivery.build_delivery_payload(
            campaign_root=campaign,
            results_dir=results,
            curves_dir=None,
            replay_root=replay,
            qualification_dir=qualification_dir,
            output_html=tmp_path / "delivery.html",
            target_registry_path=registry,
        )


def test_refuses_unqualified_or_differently_selected_dossier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, results, registry, replay, qualification_dir = _inputs(
        tmp_path, monkeypatch
    )
    qualification = _qualification()
    qualification["dossiers"][0]["dossier_id"] = "another_dossier"
    monkeypatch.setattr(
        delivery.physical_qualification,
        "validate_qualification_sidecar",
        lambda **_: qualification,
    )

    with pytest.raises(delivery.V5FinalDeliveryError, match="diffèrent"):
        delivery.build_delivery_payload(
            campaign_root=campaign,
            results_dir=results,
            curves_dir=None,
            replay_root=replay,
            qualification_dir=qualification_dir,
            output_html=tmp_path / "delivery.html",
            target_registry_path=registry,
        )
