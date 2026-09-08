from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.supplier_service_landscape_dashboard import (
    CAMPAIGN_FILES,
    build_supplier_service_landscape_dashboard,
    load_supplier_service_campaign,
)


def _write_csv(path: Path, rows: list[dict[str, object]], columns: list[str] | None = None) -> None:
    fieldnames = columns or sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _campaign(root: Path, *, sparse: bool = False) -> Path:
    root.mkdir()
    (root / CAMPAIGN_FILES["manifest"]).write_text(
        json.dumps(
            {
                "schema_version": "test.campaign.v1",
                "status": "complete",
                "days": 720,
                "confirmation_seeds": list(range(1, 11)),
                "incident_window": {"start_day": 45, "end_day": 224, "duration_days": 180},
                "mechanism_equivalence_warning": "reliability and quality_yield are equivalent",
                "purpose": "Configuration compacte de test",
                "business_targets": {"268091": 0.93, "268967": 0.80},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if sparse:
        _write_csv(root / CAMPAIGN_FILES["scenario_design"], [{"scenario_id": "S-VIDE", "extra": "conservé"}])
        for key in ("screening_metrics", "confirmation_metrics", "scenario_summary", "worst_cases"):
            _write_csv(root / CAMPAIGN_FILES[key], [{"scenario_id": "S-VIDE"}])
        return root

    design = [
        {
            "scenario_id": "S-338929",
            "chain_id": "338929_m1810_268091",
            "chain_label": "338929 → M-1810 → 268091",
            "mechanism": "lead_extra",
            "mechanism_label": "Retard fournisseur constant",
            "target_product_id": "268091",
            "parameter_values_json": json.dumps({"lead_scale": 0.88}),
            "extra_design_column": "doit rester embarquée",
        },
        {
            "scenario_id": "S-M1430",
            "chain_id": "344135_m1430_268967",
            "chain_label": "344135 → M-1430 → 268967",
            "mechanism": "capacity",
            "mechanism_label": "Capacité fournisseur",
            "target_product_id": "268967",
            "parameter_values_json": json.dumps({"capacity_scale": 0.20}),
            "extra_design_column": "doit rester embarquée",
        },
    ]
    _write_csv(root / CAMPAIGN_FILES["scenario_design"], design)
    _write_csv(
        root / CAMPAIGN_FILES["screening_metrics"],
        [
            {
                "scenario_id": "S-338929",
                "supplier_service_horizon": 0.91,
                "supplier_on_due_date_proxy": 0.83,
                "product_service_horizon": 0.93,
                "product_on_due_date_proxy": 0.85,
                "backlog_qty": 1200,
                "target_first_backlog_day": 190,
                "target_backlog_days": 45,
                "target_backlog_end_qty": 0,
                "valid": True,
                "screening_extra": "présent",
            },
            {
                "scenario_id": "S-M1430",
                "supplier_service_horizon": "72,0%",
                "supplier_on_due_date_proxy": 0.68,
                "product_service_horizon": 0.80,
                "product_on_due_date_proxy": 0.78,
                "backlog_qty": 9000,
                "target_first_backlog_day": 180,
                "target_backlog_days": 120,
                "target_backlog_end_qty": 500,
                "valid": True,
                "screening_extra": "présent",
            },
            {
                "scenario_id": "baseline_nominal",
                "baseline_chain__338929_m1810_268091__incident_pulled_qty": 1000,
                "baseline_chain__338929_m1810_268091__incident_shipped_qty": 1000,
                "baseline_chain__344135_m1430_268967__incident_pulled_qty": 0,
                "baseline_chain__344135_m1430_268967__incident_shipped_qty": 0,
                "valid": True,
                "screening_extra": "référence",
            },
        ],
    )
    confirmation_rows: list[dict[str, object]] = []
    for seed in range(1, 11):
        product_due = 0.84 + seed * 0.002
        supplier_due = 0.80 + seed * 0.003
        confirmation_rows.append(
            {
                "scenario_id": "S-338929",
                "seed": seed,
                "valid": True,
                "supplier_service_horizon": 1.0,
                "supplier_on_due_date_proxy": supplier_due,
                "product_service_horizon": 1.0,
                "product_on_due_date_proxy": product_due,
                "paired_baseline_product_on_due_date_proxy": 1.0,
                "target_on_due_date_proxy_delta_vs_paired_baseline": product_due - 1.0,
                "incremental_target_backlog_qty_days": 1500 + seed * 100,
                "target_worst_rolling_28d_on_due_proxy": product_due - 0.10,
                "paired_baseline_target_worst_rolling_28d_on_due_proxy": 1.0,
                "target_worst_rolling_28d_on_due_delta_vs_paired_baseline": product_due - 1.10,
                "target_first_backlog_day": 190 + seed,
                "target_backlog_days": 40 + seed,
                "target_backlog_end_qty": 0,
                "target_recovered_within_horizon": True,
                "target_recovery_day_after_incident": 250 + seed,
                "backlog_qty": 2000 - seed * 100,
                "confirmation_extra": f"seed-{seed}",
            }
        )
    for seed in range(1, 11):
        product_due = 0.74 + seed * 0.004
        supplier_due = 0.65 + seed * 0.004
        confirmation_rows.append(
            {
                "scenario_id": "S-M1430",
                "seed": seed,
                "valid": True,
                "supplier_service_horizon": 1.0,
                "supplier_on_due_date_proxy": supplier_due,
                "product_service_horizon": 1.0,
                "product_on_due_date_proxy": product_due,
                "paired_baseline_product_on_due_date_proxy": 1.0,
                "target_on_due_date_proxy_delta_vs_paired_baseline": product_due - 1.0,
                "incremental_target_backlog_qty_days": 9000 + seed * 100,
                "target_worst_rolling_28d_on_due_proxy": product_due - 0.15,
                "paired_baseline_target_worst_rolling_28d_on_due_proxy": 1.0,
                "target_worst_rolling_28d_on_due_delta_vs_paired_baseline": product_due - 1.15,
                "target_first_backlog_day": 180 + seed,
                "target_backlog_days": 100 + seed,
                "target_backlog_end_qty": 0 if seed <= 8 else 500,
                "target_recovered_within_horizon": seed <= 8,
                "target_recovery_day_after_incident": 280 + seed if seed <= 8 else -1,
                "backlog_qty": 10000 - seed * 200,
                "confirmation_extra": f"seed-{seed}",
            }
        )
    _write_csv(root / CAMPAIGN_FILES["confirmation_metrics"], confirmation_rows)
    _write_csv(
        root / CAMPAIGN_FILES["scenario_summary"],
        [
            {
                "scenario_id": "S-338929",
                "product_service_rate": 0.93,
                "product_service_p10": 0.914,
                "product_service_p90": 0.946,
                "business_explanation": "Le délai amont fragilise le service.",
            },
            {
                "scenario_id": "S-M1430",
                "product_service_rate": 0.80,
                "product_service_p10": 0.736,
                "product_service_p90": 0.832,
                "business_explanation": "La capacité crée un seuil.",
            },
        ],
    )
    _write_csv(
        root / CAMPAIGN_FILES["worst_cases"],
        [
            {
                "scenario_id": "S-M1430",
                "product_service_horizon": 0.72,
                "backlog_qty": 9800,
                "business_note": "Cas défavorable simulé, sans probabilité industrielle.",
            }
        ],
    )
    return root


def _actual_schema_campaign(root: Path) -> Path:
    root.mkdir()
    (root / CAMPAIGN_FILES["manifest"]).write_text(
        json.dumps({"schema_version": "etudecas.supplier_service_landscape_campaign.v1"}),
        encoding="utf-8",
    )
    design = [
        {
            "scenario_id": "delay-critical",
            "chain_id": "338929 → M-1810 → 268091",
            "mechanism": "délai fournisseur",
            "level_index": 4,
            "level_code": "critical",
            "level_label": "Critique",
            "mechanism_value": 42,
            "mechanism_unit": "jours",
        },
        {
            "scenario_id": "delay-excellent",
            "chain_id": "338929 → M-1810 → 268091",
            "mechanism": "délai fournisseur",
            "level_index": 0,
            "level_code": "excellent",
            "level_label": "Excellent",
            "mechanism_value": 14,
            "mechanism_unit": "jours",
        },
        {
            "scenario_id": "delay-nominal",
            "chain_id": "338929 → M-1810 → 268091",
            "mechanism": "délai fournisseur",
            "level_index": 1,
            "level_code": "nominal",
            "level_label": "Nominal",
            "mechanism_value": 21,
            "mechanism_unit": "jours",
        },
        {
            "scenario_id": "quality-reliability-proxy",
            "chain_id": "021081 → 773474 → 268967",
            "mechanism": "retenue qualité",
            "level_index": 3,
            "level_code": "degraded",
            "level_label": "Dégradé",
            "mechanism_value": 0.78,
            "mechanism_unit": "facteur",
        },
        {
            "scenario_id": "capacity-shipped-pulled-proxy",
            "chain_id": "fournisseurs → M-1430 → 268967",
            "mechanism": "capacité fournisseur",
            "level_index": 3,
            "level_code": "degraded",
            "level_label": "Dégradé",
            "mechanism_value": 0.5,
            "mechanism_unit": "facteur",
        },
    ]
    _write_csv(root / CAMPAIGN_FILES["scenario_design"], design)
    _write_csv(
        root / CAMPAIGN_FILES["screening_metrics"],
        [
            {
                "scenario_id": "delay-critical",
                "supplier_service_horizon": 0.71,
                "supplier_on_due_date_proxy": 0.65,
                "target_fill_rate": 0.79,
                "target_on_due_volume_proxy": 0.74,
                "target_backlog_qty_days": 7800,
            }
        ],
    )
    confirmation = [
        {
            "scenario_id": "delay-critical",
            "supplier_service_horizon_mean": 0.72,
            "supplier_on_due_date_proxy_mean": 0.66,
            "target_fill_rate_mean": 0.80,
            "target_on_due_volume_proxy_mean": 0.75,
            "target_backlog_qty_days_mean": 7500,
            "shared_baseline_target_fill_rate_mean": 0.96,
            "target_fill_rate_delta_vs_baseline_mean": -0.16,
            "shared_baseline_id": "delay-nominal",
        },
        {
            "scenario_id": "delay-excellent",
            "supplier_service_horizon_mean": 0.98,
            "supplier_on_due_date_proxy_mean": 0.95,
            "target_fill_rate_mean": 0.97,
            "target_on_due_volume_proxy_mean": 0.94,
            "target_backlog_qty_days_mean": 50,
            "shared_baseline_target_fill_rate_mean": 0.96,
            "target_fill_rate_delta_vs_baseline_mean": 0.01,
            "shared_baseline_id": "delay-nominal",
        },
        {
            "scenario_id": "delay-nominal",
            "supplier_service_horizon_mean": 0.94,
            "supplier_on_due_date_proxy_mean": 0.90,
            "target_fill_rate_mean": 0.96,
            "target_on_due_volume_proxy_mean": 0.92,
            "target_backlog_qty_days_mean": 200,
            "shared_baseline_target_fill_rate_mean": 0.96,
            "target_fill_rate_delta_vs_baseline_mean": 0.0,
            "shared_baseline_id": "delay-nominal",
        },
        {
            "scenario_id": "quality-reliability-proxy",
            "supplier_weighted_reliability_mean": 0.78,
            "target_fill_rate_mean": 0.82,
            "target_on_due_volume_proxy_mean": 0.80,
            "target_backlog_qty_days_mean": 6100,
        },
        {
            "scenario_id": "capacity-shipped-pulled-proxy",
            "supplier_shipped_qty_mean": 750,
            "supplier_pulled_qty_mean": 1000,
            "target_fill_rate_mean": 0.84,
            "target_on_due_volume_proxy_mean": 0.81,
            "target_backlog_qty_days_mean": 5000,
        },
    ]
    _write_csv(root / CAMPAIGN_FILES["confirmation_metrics"], confirmation)
    _write_csv(root / CAMPAIGN_FILES["scenario_summary"], [{"scenario_id": "delay-critical"}])
    _write_csv(root / CAMPAIGN_FILES["worst_cases"], [{"scenario_id": "delay-critical"}])
    return root


def _embedded_payload(document: str) -> dict[str, object]:
    match = re.search(
        r'<script id="campaign-data" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    assert match
    return json.loads(match.group(1))


def test_builds_one_autonomous_three_view_dashboard_with_filters_and_svg(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path / "campaign")
    output = tmp_path / "dashboard.html"

    result = build_supplier_service_landscape_dashboard(campaign, output)
    document = output.read_text(encoding="utf-8")

    assert result["view_count"] == 3
    assert document.count('data-view="') == 3
    assert "Du fournisseur au client" in document
    assert "Les configurations les plus fragiles" in document
    assert "Décisions à tester" in document
    assert 'id="chain-filter"' in document
    assert 'id="mechanism-filter"' in document
    assert document.count('class="service-curve"') == 2
    assert 'class="service-scatter"' in document
    assert "Servi avant la fin de l’horizon" in document
    assert "Servi à la date attendue — proxy" in document
    assert "Moyenne et min–max" in document
    assert "Retard cumulé supplémentaire" in document
    assert "Demandé" in document and "Confirmé" in document
    assert "Exécuté" in document and "Refusé" in document


def test_guardrails_are_explicit_and_actions_are_not_claimed_as_simulated(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(_campaign(tmp_path / "campaign"), output)
    document = output.read_text(encoding="utf-8")

    for label in (
        "OBSERVÉ 2025",
        "SIMULÉ",
        "HYPOTHÈSE À CONFIRMER",
        "SIGNAL DE PRIORITÉ",
    ):
        assert label in document
    assert "aucun OTIF fournisseur observé n’est disponible" in document
    assert "Les repères 80 % et 93 % désignent ici" in document
    assert "cette campagne de sensibilité est exécutée en boucle ouverte" in document
    assert "aucun régulateur automatique ne choisit ni n’applique ces actions" in document
    assert "ils ne sont pas des décisions simulées dans cette campagne" in document
    assert "Réserver un transport sur une expédition identifiée" in document
    assert "Réserver une capacité chez une source approuvée" in document
    assert "Limiter la retenue qualité aux lots réellement concernés" in document
    assert "Aucun recalcul de simulation" in document


def test_output_has_no_network_dependency_or_unrelated_api_reference(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(_campaign(tmp_path / "campaign"), output)
    document = output.read_text(encoding="utf-8")
    lowered = document.lower()

    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "fred_api" not in lowered
    assert "fred api" not in lowered
    assert "<script src=" not in lowered
    assert "<link rel=" not in lowered
    assert "fetch(" not in lowered
    assert "xmlhttprequest" not in lowered


def test_all_compact_rows_and_extra_columns_are_embedded(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path / "campaign")
    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(campaign, output)
    payload = _embedded_payload(output.read_text(encoding="utf-8"))

    assert payload["manifest"]["business_targets"] == {"268091": 0.93, "268967": 0.80}
    assert len(payload["tables"]["confirmation_metrics"]["rows"]) == 20
    assert payload["tables"]["scenario_design"]["rows"][0]["extra_design_column"] == "doit rester embarquée"
    assert payload["tables"]["screening_metrics"]["rows"][0]["screening_extra"] == "présent"
    assert payload["tables"]["confirmation_metrics"]["rows"][0]["confirmation_extra"] == "seed-1"


def test_missing_metric_columns_are_tolerated(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path / "campaign", sparse=True)
    payload = load_supplier_service_campaign(campaign)
    output = tmp_path / "dashboard.html"

    build_supplier_service_landscape_dashboard(
        campaign,
        output,
        allow_incomplete_campaign=True,
    )

    record = payload["normalised"]["confirmation_metrics"][0]
    assert record["scenario_id"] == "S-VIDE"
    assert record["supplier_horizon"] is None
    assert record["product_horizon"] is None
    assert output.is_file()


def test_refuses_to_overwrite_and_requires_every_compact_file(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path / "campaign")
    output = tmp_path / "dashboard.html"
    original_manifest = (campaign / CAMPAIGN_FILES["manifest"]).read_bytes()

    build_supplier_service_landscape_dashboard(campaign, output)
    with pytest.raises(FileExistsError):
        build_supplier_service_landscape_dashboard(campaign, output)
    assert (campaign / CAMPAIGN_FILES["manifest"]).read_bytes() == original_manifest

    incomplete = _campaign(tmp_path / "incomplete")
    (incomplete / CAMPAIGN_FILES["worst_cases"]).unlink()
    with pytest.raises(FileNotFoundError, match="worst_cases.csv"):
        build_supplier_service_landscape_dashboard(incomplete, tmp_path / "other.html")


def test_actual_campaign_columns_are_normalised_and_levels_are_ordered(tmp_path: Path) -> None:
    campaign = _actual_schema_campaign(tmp_path / "campaign")
    payload = load_supplier_service_campaign(campaign)
    confirmation = payload["normalised"]["confirmation_metrics"]
    delay = [row for row in confirmation if row["mechanism"] == "délai fournisseur"]

    assert [row["scenario_id"] for row in delay] == [
        "delay-excellent",
        "delay-nominal",
        "delay-critical",
    ]
    assert [row["level_index"] for row in delay] == [0.0, 1.0, 4.0]
    assert delay[0]["level_code"] == "excellent"
    assert delay[0]["level_label"] == "Excellent"
    assert delay[0]["mechanism_value"] == "14"
    assert delay[0]["mechanism_unit"] == "jours"
    assert delay[0]["level_display"] == "+14 jours de retard fournisseur"
    assert delay[2]["product_horizon"] == pytest.approx(0.80)
    assert delay[2]["product_due"] == pytest.approx(0.75)
    assert delay[2]["backlog"] == pytest.approx(7500)
    assert delay[2]["supplier_horizon"] == pytest.approx(0.72)
    assert delay[2]["supplier_due"] == pytest.approx(0.66)
    assert delay[2]["client_delta_vs_baseline"] == pytest.approx(-0.16)

    screening = payload["normalised"]["screening_metrics"][0]
    assert screening["product_horizon"] == pytest.approx(0.79)
    assert screening["product_due"] == pytest.approx(0.74)
    assert screening["backlog"] == pytest.approx(7800)


def test_supplier_fallbacks_are_explicitly_labelled_as_proxies(tmp_path: Path) -> None:
    payload = load_supplier_service_campaign(_actual_schema_campaign(tmp_path / "campaign"))
    by_id = {
        row["scenario_id"]: row
        for row in payload["normalised"]["confirmation_metrics"]
    }

    reliability = by_id["quality-reliability-proxy"]
    assert reliability["supplier_horizon"] == pytest.approx(0.78)
    assert reliability["supplier_metric_is_proxy"] is True
    assert reliability["supplier_metric_kind"] == "proxy de fiabilité fournisseur pondérée"

    shipped = by_id["capacity-shipped-pulled-proxy"]
    assert shipped["supplier_horizon"] == pytest.approx(0.75)
    assert shipped["supplier_metric_is_proxy"] is True
    assert shipped["supplier_metric_kind"] == "proxy fournisseur expédié / appelé"


def test_dashboard_exposes_ordered_physical_levels_and_confirmed_ranking(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(
        _actual_schema_campaign(tmp_path / "campaign"),
        output,
        allow_incomplete_campaign=True,
    )
    document = output.read_text(encoding="utf-8")

    assert "Hypothèse physique testée" in document
    assert "Impacts maximaux confirmés parmi les niveaux testés" in document
    assert "perte de service à date" in document
    assert "Affinez les filtres : une courbe ne relie qu’une chaîne et un mécanisme" in document
    assert "levelOrder(a)-levelOrder(b)" in document
    assert "levelDisplay" in document
    assert "Indicateur fournisseur simulé ou proxy" in document
    assert "OTIF fournisseur historique" in document


def test_v4_paired_due_backlog_rolling_and_backlog_timeline_fields_are_normalised(
    tmp_path: Path,
) -> None:
    payload = load_supplier_service_campaign(_campaign(tmp_path / "campaign"))
    record = next(
        row
        for row in payload["normalised"]["confirmation_metrics"]
        if row["scenario_id"] == "S-338929" and row["repetition"] == "1"
    )

    assert record["chain_id"] == "338929_m1810_268091"
    assert record["chain"] == "338929 → M-1810 → 268091"
    assert record["mechanism_id"] == "lead_extra"
    assert record["mechanism"] == "Retard fournisseur constant"
    assert record["target_product_id"] == "268091"
    assert record["product_horizon"] == pytest.approx(1.0)
    assert record["product_due"] == pytest.approx(0.842)
    assert record["baseline_product_due"] == pytest.approx(1.0)
    assert record["product_due_delta_vs_baseline"] == pytest.approx(-0.158)
    assert record["product_due_loss_vs_baseline"] == pytest.approx(0.158)
    assert record["incremental_backlog"] == pytest.approx(1600)
    assert record["worst_rolling_28d_due"] == pytest.approx(0.742)
    assert record["worst_rolling_28d_due_delta"] == pytest.approx(-0.258)
    assert record["first_backlog_day"] == pytest.approx(191)
    assert record["backlog_days"] == pytest.approx(41)
    assert record["backlog_end_qty"] == pytest.approx(0)
    assert "recovered_fraction" not in record
    assert "recovery_day" not in record


def test_unexercised_baseline_chain_is_marked_and_excluded_from_ranking(
    tmp_path: Path,
) -> None:
    campaign = _campaign(tmp_path / "campaign")
    payload = load_supplier_service_campaign(campaign)
    confirmations = payload["normalised"]["confirmation_metrics"]
    active = next(row for row in confirmations if row["scenario_id"] == "S-338929")
    inactive = next(row for row in confirmations if row["scenario_id"] == "S-M1430")

    assert active["baseline_incident_flow_exercised"] is True
    assert active["baseline_incident_pulled_qty"] == pytest.approx(1000)
    assert inactive["baseline_incident_flow_exercised"] is False
    assert inactive["baseline_incident_shipped_qty"] == pytest.approx(0)

    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(campaign, output)
    document = output.read_text(encoding="utf-8")
    assert "Chaîne non exercée dans la référence" in document
    assert "Chaîne non exercée · non interprétable" in document
    influence = document.split("function renderInfluence", 1)[1].split(
        "function appendDistribution", 1
    )[0]
    assert "group.baselineFlowExercised!==false" in influence
    table = document.split("function renderTable", 1)[1].split(
        "function renderReading", 1
    )[0]
    assert 'row.className="not-exercised"' in table


def test_javascript_uses_due_date_then_business_tie_breakers_and_due_scatter(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(_campaign(tmp_path / "campaign"), output)
    document = output.read_text(encoding="utf-8")

    grouping = document.split("function groupRows(records)", 1)[1].split(
        "function levelOrder", 1
    )[0]
    assert 'const dueValues=values("product_due")' in grouping
    assert 'mean(values("product_horizon"))' in grouping
    assert "quantile(client" not in grouping

    severity = document.split("function severityCompare", 1)[1].split(
        "function backlogStatusText", 1
    )[0]
    ordered = [
        severity.index("dueLoss"),
        severity.index("incrementalBacklog"),
        severity.index("worst28Loss"),
    ]
    assert ordered == sorted(ordered)
    assert "recoveredFraction" not in severity
    assert "recoveryDelay" not in severity

    scatter = document.split("function drawScatter", 1)[1].split(
        "const severityValue", 1
    )[0]
    assert "group.supplierDue" in scatter
    assert "group.productDue" in scatter
    assert "group.supplierHorizon" not in scatter
    assert "group.productHorizon" not in scatter


def test_dashboard_exposes_ten_individual_due_results_and_scientific_limits(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.html"
    build_supplier_service_landscape_dashboard(_campaign(tmp_path / "campaign"), output)
    document = output.read_text(encoding="utf-8")

    payload = _embedded_payload(document)
    confirmations = payload["normalised"]["confirmation_metrics"]
    assert len([row for row in confirmations if row["scenario_id"] == "S-338929"]) == 10
    assert "simulations ·" in document
    assert "runValues.map" in document
    assert "ni une probabilité industrielle, ni un intervalle de confiance" in document
    assert "plus défavorable parmi les hypothèses testées, pas pire cas possible" in document
    assert "Leurs effets ne doivent ni être additionnés ni présentés comme deux facteurs indépendants" in document
    assert "Chronologie et état en fin d’horizon" in document
    assert "Premier retard : J" in document
    assert "jours touchés" in document
    assert "Retard restant" in document
    assert "Le résumé compact actuel ne permet pas de dater le retour définitif à zéro" in document
    visible_markup = document.split('<script id="campaign-data"', 1)[0]
    assert "Récupération" not in visible_markup
    assert "function recoveryText" not in document
    assert "recoveryDelay" not in document


def test_final_dashboard_refuses_running_invalid_or_incomplete_confirmation(tmp_path: Path) -> None:
    running = _campaign(tmp_path / "running")
    manifest_path = running / CAMPAIGN_FILES["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "running"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="status=complete"):
        build_supplier_service_landscape_dashboard(running, tmp_path / "running.html")
    assert not (tmp_path / "running.html").exists()

    incomplete = _campaign(tmp_path / "incomplete-confirmation")
    confirmation_path = incomplete / CAMPAIGN_FILES["confirmation_metrics"]
    with confirmation_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    rows = [
        row
        for row in rows
        if not (row["scenario_id"] == "S-338929" and row["seed"] == "10")
    ]
    _write_csv(confirmation_path, rows, columns)
    with pytest.raises(ValueError, match="same 10 configured simulations"):
        build_supplier_service_landscape_dashboard(
            incomplete,
            tmp_path / "incomplete.html",
        )

    invalid = _campaign(tmp_path / "invalid")
    screening_path = invalid / CAMPAIGN_FILES["screening_metrics"]
    with screening_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    rows[0]["valid"] = "False"
    _write_csv(screening_path, rows, columns)
    with pytest.raises(ValueError, match="Invalid run"):
        build_supplier_service_landscape_dashboard(
            invalid,
            tmp_path / "invalid.html",
            allow_incomplete_campaign=True,
        )
