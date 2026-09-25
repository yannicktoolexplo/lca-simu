from __future__ import annotations

import math
import shutil

from openpyxl import load_workbook

from etudecas.risk.supplier_audit import (
    DEFAULT_SUPPLIER_AUDIT_SOURCE,
    DEFAULT_SUPPLIER_AUDIT_XLSX,
    attach_supplier_audit_panels,
    blend_criticality_with_audit,
    build_supplier_audit_panel_asset,
    build_supplier_audit_radar_figures,
    estimate_supplier_audit_profiles,
    expand_supplier_audit_coverage,
    load_supplier_audits,
    render_supplier_audit_criteria_html,
    render_supplier_audit_html,
    render_supplier_public_context_html,
    supplier_audit_coverage_summary,
    supplier_audit_score,
    supplier_estimated_score,
)


def test_load_supplier_audit_workbook() -> None:
    audits = load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_XLSX)

    audit = audits["SDC-VD0993480A"]
    assert audit["criterion_count"] == 28
    assert audit["question_count"] == 167
    assert audit["answered_question_count"] == 167
    assert len(audit["families"]) == 6
    assert audit["maturity"] == 0.599552
    assert audit["criticality"] == 19.874702
    assert audit["resilience_weeks"] == 95.449877
    assert audit["audit_risk_index"] == 0.559588
    assert audit["aggregated_criterion_count"] == 27
    assert audit["unassigned_criteria"] == ["Risques sociaux"]
    assert len(audit["calculation_corrections"]) == 2
    assert audit["recommended_action"] == "Action immédiate"


def test_audit_directory_discovers_finalized_workbook() -> None:
    audits = load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_SOURCE)

    assert set(audits) == {"SDC-VD0993480A"}
    audit = audits["SDC-VD0993480A"]
    assert audit["audited_company"] == "RAJA"
    assert "finalis" in audit["source_file"].casefold()
    assert audit["audit_risk_index"] == 0.559588


def test_directory_ignores_excel_temporary_file(tmp_path) -> None:
    audit_copy = tmp_path / DEFAULT_SUPPLIER_AUDIT_XLSX.name
    shutil.copy2(DEFAULT_SUPPLIER_AUDIT_XLSX, audit_copy)
    (tmp_path / "~$audit fournisseur.xlsx").write_bytes(b"not an xlsx")

    audits = load_supplier_audits(tmp_path)

    assert set(audits) == {"SDC-VD0993480A"}


def test_partial_workbook_does_not_change_criticality(tmp_path) -> None:
    partial_path = tmp_path / "audit fournisseur partiel.xlsx"
    workbook = load_workbook(DEFAULT_SUPPLIER_AUDIT_XLSX, data_only=False)
    workbook.worksheets[3]["D13"] = None
    workbook.save(partial_path)
    workbook.close()

    partial = load_supplier_audits(partial_path)["SDC-VD0993480A"]

    assert partial["audit_status"] == "in_progress"
    assert partial["answered_criterion_count"] == 27
    assert partial["answered_question_count"] == 166
    assert supplier_audit_score(partial) is None
    assert blend_criticality_with_audit(0.4, partial) == 0.4


def test_invalid_audit_scores_are_rejected() -> None:
    assert supplier_audit_score({"audit_status": "audited", "audit_risk_index": "bad"}) is None
    assert supplier_audit_score({"audit_status": "audited", "audit_risk_index": math.nan}) is None
    assert supplier_audit_score({"audit_status": "audited", "audit_risk_index": math.inf}) is None
    assert supplier_audit_score({"audit_risk_index": 0.5}) is None


def test_audit_blends_into_structural_criticality() -> None:
    audit = load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_XLSX)["SDC-VD0993480A"]

    assert blend_criticality_with_audit(0.228302, audit) == 0.3276878
    assert blend_criticality_with_audit(0.228302, None) == 0.228302


def test_every_supplier_gets_a_profile_without_copying_completed_scores() -> None:
    completed = load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_XLSX)
    profiles = expand_supplier_audit_coverage(
        [
            {
                "id": "SDC-VD0993480A",
                "type": "supplier_dc",
                "name": "RAJA",
                "geo": {"lat": 48.8, "lon": 2.3},
            },
            {"id": "SDC-VD0000001A", "type": "supplier_dc", "name": "Autre fournisseur"},
            {"id": "M-1430", "type": "factory", "name": "Usine"},
        ],
        completed,
    )

    assert set(profiles) == {"SDC-VD0993480A", "SDC-VD0000001A"}
    assert profiles["SDC-VD0993480A"]["audit_status"] == "audited"
    pending = profiles["SDC-VD0000001A"]
    assert pending["audit_status"] == "not_assessed"
    assert pending["criterion_count"] == 28
    assert pending["answered_criterion_count"] == 0
    assert pending["audit_risk_index"] is None
    assert blend_criticality_with_audit(0.4, pending) == 0.4
    assert supplier_audit_coverage_summary(profiles) == {
        "supplier_count": 2,
        "audited_supplier_count": 1,
        "estimated_supplier_count": 0,
        "pending_supplier_count": 1,
        "audited_supplier_ids": ["SDC-VD0993480A"],
        "estimated_supplier_ids": [],
        "pending_supplier_ids": ["SDC-VD0000001A"],
        "map_marker_supplier_count": 1,
        "unlocated_supplier_count": 1,
        "unlocated_supplier_ids": ["SDC-VD0000001A"],
    }
    pending_html = render_supplier_audit_html(pending)
    assert "Audit à renseigner" in pending_html
    assert "28 critères prêt" in pending_html
    assert "Indice de risque estimé</div><div class=\"dataKvValue\">À renseigner" in pending_html
    pending_radars = build_supplier_audit_radar_figures(pending)
    assert len(pending_radars) == 3
    assert all(radar["values"] == [] for radar in pending_radars)
    assert [radar["threshold"] for radar in pending_radars] == [75.0, 15.0, 70.0]


def test_audit_panel_uses_visible_tabs_without_dropping_existing_summary() -> None:
    audit = load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_XLSX)["SDC-VD0993480A"]
    existing = {
        "SDC-VD0993480A": {
            "incoming": {"html": "<div>Résumé existant</div>"},
            "outgoing": {"figure": {"kind": "line_multi"}},
        }
    }

    merged = attach_supplier_audit_panels(existing, {"SDC-VD0993480A": audit})
    incoming_bundle = merged["SDC-VD0993480A"]["incoming"]["bundle"]
    assert [entry["label"] for entry in incoming_bundle] == [
        "Audit fournisseur",
        "Criticité simulée",
    ]
    audit_tabs = incoming_bundle[0]["asset"]["bundle"]
    assert [entry["label"] for entry in audit_tabs] == [
        "Synthèse",
        "Contexte public",
        "Radar maturité",
        "Radar criticité",
        "Radar résilience",
        "28 critères",
    ]
    summary_html = audit_tabs[0]["asset"]["html"]
    public_context_html = audit_tabs[1]["asset"]["html"]
    criteria_html = audit_tabs[5]["asset"]["html"]
    radar_figures = [entry["asset"]["figure"] for entry in audit_tabs[2:5]]

    assert incoming_bundle[1]["asset"]["html"] == "<div>Résumé existant</div>"
    assert "Critères fournisseur" in summary_html
    assert "Familles de criticité" in summary_html
    assert "Contexte public documenté" in public_context_html
    assert "Détail des 28 critères" in criteria_html
    assert all(figure["kind"] == "radar" for figure in radar_figures)
    assert all(len(figure["categories"]) == 6 for figure in radar_figures)
    assert [figure["threshold"] for figure in radar_figures] == [75.0, 15.0, 70.0]
    assert radar_figures[0]["values"][0] == 86.8384
    assert radar_figures[1]["values"][3] == 31.388889
    assert radar_figures[2]["values"][5] == 336.666667
    assert merged["SDC-VD0993480A"]["outgoing"] == existing["SDC-VD0993480A"]["outgoing"]
    rendered_audit = render_supplier_audit_html(audit)
    assert "Critères fournisseur" in rendered_audit
    assert "RAJA" not in rendered_audit
    assert "Packaging" not in rendered_audit
    assert "Détail des 28 critères" in render_supplier_audit_criteria_html(audit)
    assert len(build_supplier_audit_panel_asset(audit)["bundle"]) == 6


def test_proxy_estimation_populates_all_criteria_without_becoming_an_audit() -> None:
    template = load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_XLSX)
    profiles = expand_supplier_audit_coverage(
        [
            {"id": "SDC-VD0993480A", "type": "supplier_dc", "geo": {"lat": 1, "lon": 1}},
            {"id": "SDC-VD0960508A", "type": "supplier_dc", "geo": {"lat": 1, "lon": 1}},
        ],
        template,
    )
    estimate_supplier_audit_profiles(
        profiles,
        [
            {
                "supplier_id": "SDC-VD0960508A",
                "active_days": 9,
                "total_shipped_qty": 820000,
                "shortage_supported_qty": 0,
                "structural_criticality_score": 0.132605,
                "local_criticality_score": 0.2411,
                "system_criticality_score": 0,
                "avg_procurement_lead_days": 120,
                "sole_source_pairs": 0,
                "shared_source_pairs": 1,
                "max_capacity_utilization": 0,
            }
        ],
    )

    estimated = profiles["SDC-VD0960508A"]
    assert estimated["audit_status"] == "estimated"
    assert estimated["estimated_criterion_count"] == 28
    assert estimated["answered_criterion_count"] == 0
    assert supplier_audit_score(estimated) is None
    assert supplier_estimated_score(estimated) is not None
    assert all(row["response_status"] == "estimated" for row in estimated["criteria"])
    assert all(row["maturity"] is not None for row in estimated["criteria"])
    assert len(build_supplier_audit_radar_figures(estimated)[0]["values"]) == 6
    assert "Estimation par proxy" in render_supplier_audit_html(estimated)
    assert "SDC-VD0960508A" in render_supplier_audit_html(estimated)
    assert "LALILAB" not in render_supplier_audit_html(estimated)
    public_html = render_supplier_public_context_html(estimated)
    assert "Réussite / capacité" in public_html
    assert "LALILAB" not in public_html
    assert "Ouvrir la source" not in public_html
    assert "href=" not in public_html
    assert all("source_url" not in row for row in estimated["public_evidence"])
    assert profiles["SDC-VD0993480A"]["audit_status"] == "audited"
    assert "identité du classeur" in render_supplier_public_context_html(profiles["SDC-VD0993480A"])
