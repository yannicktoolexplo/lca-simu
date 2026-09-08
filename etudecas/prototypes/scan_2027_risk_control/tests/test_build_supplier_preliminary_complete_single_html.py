from __future__ import annotations

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_preliminary_complete_single_html as subject,
)


def _fixture_payload() -> dict[str, object]:
    ranking = []
    for rank in range(1, 17):
        ranking.append(
            {
                "supplier_sensitivity_rank": str(rank),
                "supplier_id": f"SDC-{rank:02d}",
                "worst_item_id": f"item:{rank:06d}",
                "worst_dst_node_id": "M-1810",
                "worst_service_delta": str(-0.3 if rank == 1 else 0),
            }
        )
    common_top = {
        "target_on_due_date_proxy_delta_vs_paired_baseline_mean": "-0.30",
        "target_on_due_date_proxy_delta_vs_paired_baseline_sample_std": "0.01",
        "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_low": "-0.32",
        "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_high": "-0.28",
        "target_on_due_date_proxy_delta_vs_paired_baseline_min": "-0.35",
        "target_on_due_date_proxy_delta_vs_paired_baseline_max": "-0.25",
    }
    time = []
    for item in ("338929", "344135"):
        for start in (0, 180, 360, 540):
            time.append(
                {
                    "case_id": f"temporal__{item}__window{start}",
                    "stress_start_day": str(start),
                    "mean_service_delta_percentage_points": "-20",
                }
            )
    illustrations = []
    for item in ("016332", "029313", "338929", "344135"):
        illustrations.append(
            {
                "item_id": f"item:{item}",
                "supplier_id": "SDC-EXAMPLE",
                "target_product_id": "268091",
                "root_lot_count": "1",
                "exposed_descendant_lot_count": "2",
                "genealogical_exposure_quantity_by_uom": '{"UN": 3}',
                "root_quantity_by_uom": '{"UN": 1}',
            }
        )
    return {
        "rankings": ranking,
        "top": {"338929": common_top, "344135": common_top},
        "time": time,
        "common": [],
        "illustrations": illustrations,
        "lots": [
            {
                "supplier_ids": "SDC-EXAMPLE",
                "lot_id": "LOT-1",
                "exposure_role": "genealogical_descendant",
                "genealogy_depth": "1",
                "node_id": "M-1810",
                "item_id": "item:338929",
                "day": "5",
                "qty": "10",
                "uom": "UN",
                "shipment_id": "SHIP-1",
                "production_campaign_id": "",
            }
        ],
    }


def test_render_is_one_offline_html_with_full_business_sections() -> None:
    document = subject.render_html(_fixture_payload())
    subject.validate_html(document)
    assert document.count("<!doctype html>") == 1
    assert "https://" not in document
    assert "16 fournisseurs" in document
    assert "Lots" in document
    assert "Données industrielles 2025" in document
    assert "Matrice de maturité" in document
    assert "−-" not in document


def test_output_excludes_out_of_scope_terms() -> None:
    document = subject.render_html(_fixture_payload()).casefold()
    hidden_terms = ("quality_hold", "quality_yield", "retenue qualité", "quarantaine")
    assert all(term not in document for term in hidden_terms)


def test_real_evidence_loads_when_artifact_root_is_available() -> None:
    if not subject.SCREEN_DIR.is_dir() or not subject.PRELIM_DIR.is_dir():
        return
    payload = subject.load_payload()
    assert len(payload["rankings"]) == 16
    assert len(payload["lots"]) == 2231
    assert len(payload["time"]) == 8
    assert "case_key" in payload["lots"][0]
    assert "source_id" in payload["lots"][0]
