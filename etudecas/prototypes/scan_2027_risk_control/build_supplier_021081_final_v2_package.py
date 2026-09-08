#!/usr/bin/env python3
"""Build the final dashboard-compatible 021081 package from audited runs only.

This is a reporting-only consolidation.  It does not rerun or alter the
simulation engine, source graph, cold start, previous pages or prior artifacts.
The generated HTML is fully autonomous: CSS, JavaScript and data are embedded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


MASKING_AUDIT = {
    "released_268967_lot_count": 29,
    "approx_horizon_need_g": 30_182_579.4116,
    "opening_stock_total_g": 24_193_000.0,
    "horizon_773474_production_g": 28_800_000.0,
    "stock_multiple_of_horizon_need": 0.8015550848,
    "stock_plus_production_multiple_of_horizon_need": 1.7557478861,
    "021081_stock_multiple_of_horizon_intermediate_consumption": 4.4358221477,
    "021081_order_book_multiple_of_horizon_intermediate_consumption": 5.1267710664,
}

SERVICE_METRIC = {
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


class FinalPackageError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise FinalPackageError(f"Expected JSON object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if not fieldnames:
            handle.write("\n")
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _finite_or_none(value: Any) -> float | None:
    number = _number(value)
    return number if math.isfinite(number) else None


def _provenance_allowed(root: Path, manifest: Mapping[str, Any]) -> bool:
    embedded = manifest.get("execution_provenance_audit")
    if isinstance(embedded, Mapping):
        return _truthy(embedded.get("reproducibility_wording_allowed"))
    audit_path = root / "execution_provenance_audit.json"
    if audit_path.is_file():
        return _truthy(_read_json(audit_path).get("reproducibility_wording_allowed"))
    return False


def _package_record(
    root: Path,
    *,
    role: str,
    required_files: Sequence[str],
    require_v2_suffix: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    manifest_path = root / "campaign_manifest.json"
    if not manifest_path.is_file():
        raise FinalPackageError(f"Missing campaign manifest: {manifest_path}")
    manifest = _read_json(manifest_path)
    if str(manifest.get("status") or "") != "complete":
        raise FinalPackageError(f"Incomplete source package for {role}: {root}")
    if require_v2_suffix and not root.name.lower().endswith("_v2"):
        raise FinalPackageError(f"{role} must be a V2 package: {root}")
    if not _provenance_allowed(root, manifest):
        raise FinalPackageError(f"Unaudited execution provenance for {role}: {root}")
    files: dict[str, str] = {}
    for name in required_files:
        path = root / name
        if not path.is_file():
            raise FinalPackageError(f"Missing {role} file: {path}")
        files[name] = _sha(path)
    return manifest, {
        "role": role,
        "directory": str(root),
        "artifact_name": root.name,
        "status": "complete",
        "execution_provenance_reproducible": True,
        "manifest_sha256": _sha(manifest_path),
        "files_sha256": files,
    }


def _scenario_label(scenario_id: str) -> str:
    labels = {
        "baseline_observed_order_book": (
            "Référence simulée à partir du snapshot 2025"
        ),
        "all_021081__usable_yield__0p1": "10 % de matière utilisable",
        "all_021081__delivery_availability__0p25": "25 % de quantité disponible",
        "all_021081__quality_hold__180": "Retenue qualité de 180 jours",
    }
    return labels.get(scenario_id, scenario_id.replace("_", " "))


def _state_label(state_id: str) -> str:
    labels = {
        "observed_all_layers": "Couches du snapshot rejouées",
        "component_only_90d": "Stock 021081 seul réduit à 90 j",
        "component_only_30d": "Stock 021081 seul réduit à 30 j",
        "intermediate_stock_only_90d": "Stock 773474 seul réduit à 90 j",
        "intermediate_stock_only_30d": "Stock 773474 seul réduit à 30 j",
        "intermediate_production_only_90d": "Production 773474 seule limitée à 90 j",
        "intermediate_production_only_30d": "Production 773474 seule limitée à 30 j",
        "joint_90d": "021081 + stock et production 773474 à 90 j",
        "joint_30d": "021081 + stock et production 773474 à 30 j",
        "intermediate_stock_only_300d": (
            "Calibrage diagnostique — stock 773474 à 300 j (hypothèse)"
        ),
        "intermediate_stock_only_384d": (
            "Calibrage diagnostique — stock 773474 à 384 j (hypothèse)"
        ),
        "intermediate_stock_only_385d": (
            "Calibrage diagnostique — stock 773474 à 385 j (hypothèse)"
        ),
    }
    return labels.get(state_id, state_id.replace("_", " "))


def _collect_demasking(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _read_csv(root / "screening_metrics.csv")
    effects = _read_csv(root / "layer_effect_table.csv")
    baseline_by_state = {
        str(row.get("state_regime") or ""): row
        for row in rows
        if str(row.get("scenario_id") or "") == "baseline_observed_order_book"
    }
    states: list[dict[str, Any]] = []
    dashboard_rows: list[dict[str, Any]] = []
    for effect in effects:
        state_id = str(effect.get("state_regime") or "")
        baseline = baseline_by_state[state_id]
        state = {
            "state_id": state_id,
            "label": _state_label(state_id),
            "cover_days": (
                _number(effect.get("cover_days"))
                if str(effect.get("cover_days") or "").strip()
                else None
            ),
            "reduced_layers": str(effect.get("reduced_layers") or ""),
            "baseline_service": _number(
                baseline.get("product_on_due_volume_proxy")
            ),
            "released_268967_qty": _number(
                baseline.get("product_268967_released_qty")
            ),
            "component_021081_consumed_kg": _number(
                baseline.get("component_consumed_qty_kg")
            ),
            "opening_stock_773474_g": _number(
                baseline.get("intermediate_773474_measurement_start_total_qty_g")
            ),
            "dynamic_production_773474_g": _number(
                baseline.get("intermediate_773474_dynamic_production_qty_g")
            ),
            "opening_production_order_773474_g": _number(
                baseline.get(
                    "intermediate_773474_opening_production_order_receipt_qty_g"
                )
            ),
            "tested_incident_count": _integer(
                effect.get("tested_incident_count")
            ),
            "incidents_with_downstream_effect": _integer(
                effect.get("incidents_with_downstream_effect")
            ),
            "interpretation": (
                "Les couches restantes absorbent les incidents testés dans l’horizon ; "
                "ce résultat ne prouve pas une résilience acquise."
            ),
        }
        states.append(state)
        dashboard_rows.append(
            {
                "state_regime": (
                    "observed_2025" if state_id == "observed_all_layers" else state_id
                ),
                "target_cover_days": state["cover_days"],
                "tested_stress_configurations": state["tested_incident_count"],
                "configurations_with_simulated_downstream_product_effect": state[
                    "incidents_with_downstream_effect"
                ],
            }
        )
    return states, dashboard_rows


def _collect_calibration(root: Path) -> dict[str, Any]:
    rows = _read_csv(root / "baseline_calibration_metrics.csv")
    baseline = {
        str(row.get("state_regime") or ""): row
        for row in rows
        if str(row.get("scenario_id") or "") == "baseline_observed_order_book"
    }
    required = (
        "intermediate_stock_only_300d",
        "intermediate_stock_only_384d",
        "intermediate_stock_only_385d",
    )
    missing = [state for state in required if state not in baseline]
    if missing:
        raise FinalPackageError(f"Missing calibrated states: {missing}")
    states: list[dict[str, Any]] = []
    for state_id in required:
        reference = baseline[state_id]
        stress_rows = [
            row
            for row in rows
            if str(row.get("state_regime") or "") == state_id
            and str(row.get("scenario_id") or "") != "baseline_observed_order_book"
        ]
        states.append(
            {
                "state_id": state_id,
                "label": _state_label(state_id),
                "cover_days": _number(reference.get("state_regime_target_cover_days")),
                "baseline_service": _number(
                    reference.get("product_on_due_volume_proxy")
                ),
                "baseline_released_268967_qty": _number(
                    reference.get("product_268967_released_qty")
                ),
                "component_021081_consumed_kg": _number(
                    reference.get("component_consumed_qty_kg")
                ),
                "tested_incidents": [
                    {
                        "scenario_id": str(row.get("scenario_id") or ""),
                        "label": _scenario_label(str(row.get("scenario_id") or "")),
                        "replayed_shipped_qty_kg": _number(
                            row.get("replayed_shipped_qty_kg")
                        ),
                        "service": _number(row.get("product_on_due_volume_proxy")),
                        "service_delta": _number(
                            row.get("product_on_due_delta_vs_paired_baseline")
                        ),
                        "released_268967_delta": _number(
                            row.get(
                                "product_268967_released_qty_delta_vs_paired_baseline"
                            )
                        ),
                    }
                    for row in stress_rows
                ],
            }
        )
    lower = baseline["intermediate_stock_only_384d"]
    upper = baseline["intermediate_stock_only_385d"]
    near_80 = baseline["intermediate_stock_only_300d"]
    return {
        "states": states,
        "target_80": {
            "target": 0.80,
            "selected_cover_days": 300,
            "achieved_service": _number(
                near_80.get("product_on_due_volume_proxy")
            ),
            "distance_percentage_points": 100
            * (
                _number(near_80.get("product_on_due_volume_proxy"))
                - 0.80
            ),
            "interpretation": "État discret le plus proche testé ; pas un réglage optimal.",
        },
        "target_93": {
            "target": 0.93,
            "exact_state_found": False,
            "lower_cover_days": 384,
            "lower_service": _number(lower.get("product_on_due_volume_proxy")),
            "upper_cover_days": 385,
            "upper_service": _number(upper.get("product_on_due_volume_proxy")),
            "interval_percentage": [
                100 * _number(lower.get("product_on_due_volume_proxy")),
                100 * _number(upper.get("product_on_due_volume_proxy")),
            ],
            "interpolation_allowed": False,
            "interpretation": (
                "La réponse saute par lots entre 384 et 385 jours. Le modèle encadre "
                "93 %, mais ne fournit pas un état exact à 93 %."
            ),
        },
    }


def _collect_unit(root: Path) -> dict[str, Any]:
    comparisons = _read_csv(root / "unit_sensitivity_comparison.csv")
    rows = [
        {
            "state_id": str(row.get("absolute_state_id") or ""),
            "state_label": _state_label(str(row.get("absolute_state_id") or "")),
            "scenario_id": str(row.get("scenario_id") or ""),
            "scenario_label": _scenario_label(str(row.get("scenario_id") or "")),
            "literal_consumption_kg": _number(
                row.get("literal_component_consumption_kg")
            ),
            "divided_ratio_consumption_kg": _number(
                row.get("divided_ratio_component_consumption_kg")
            ),
            "consumption_ratio": _finite_or_none(
                row.get("literal_to_divided_consumption_ratio")
            ),
            "literal_service": _number(row.get("literal_product_on_due")),
            "divided_ratio_service": _number(
                row.get("divided_ratio_product_on_due")
            ),
            "service_delta": _number(
                row.get("product_on_due_delta_divided_minus_literal")
            ),
        }
        for row in comparisons
    ]
    return {
        "status": "unit_to_validate_with_industrial_owner",
        "source_statement": (
            "La BOM déclare une sortie 1000 G décrite ‘ELSSR CONT. 1000 L’ "
            "et une entrée 021081 de 8,94 KG."
        ),
        "tested_interpretations": [
            "ratio exécuté littéralement : 8,94 kg de 021081 par kg de 773474",
            "hypothèse de sensibilité : ratio divisé par 1000",
        ],
        "rows": rows,
        "decision": "inconclusive",
        "why_inconclusive": (
            "Dans l’état observé, le stock masque l’écart d’unité. Dans l’état "
            "conjoint 30 jours, aucune production 773474 n’a lieu et 021081 n’est "
            "pas consommé. L’essai ne peut donc pas arbitrer l’unité correcte."
        ),
        "production_semantics": (
            "28,8 M G proviennent du plan dynamique et 3,2 M G de l’ordre de "
            "production déjà ouvert, soit 32 M G au total. La borne de 28,8 M G "
            "s’applique uniquement à la production dynamique."
        ),
        "correction_claim_allowed": False,
    }


def _collect_drilldown(demasking_root: Path) -> list[dict[str, Any]]:
    scenario_ids = (
        "baseline_observed_order_book",
        "all_021081__usable_yield__0p1",
        "all_021081__delivery_availability__0p25",
        "all_021081__quality_hold__180",
    )
    output: list[dict[str, Any]] = []
    for scenario_id in scenario_ids:
        proof = (
            demasking_root
            / "cases"
            / "observed_all_layers"
            / scenario_id
            / "seed_422081"
            / "proofs"
            / "opening_purchase_order_supplier_risk_audit_021081.csv"
        )
        rows = _read_csv(proof)
        if len(rows) != 23:
            raise FinalPackageError(f"Expected 23 opening-order rows: {proof}")
        order_rows = []
        for row in rows:
            usable_after = _integer(row.get("usable_day_after"), -1)
            order_rows.append(
                {
                    "source_row": str(row.get("source_row") or ""),
                    "supplier_id": str(row.get("supplier_id") or ""),
                    "shipment_id": str(row.get("shipment_id") or ""),
                    "planned_qty_kg": _number(row.get("planned_qty_before")),
                    "usable_qty_after_kg": _number(row.get("usable_qty_after")),
                    "physical_day_before": _integer(
                        row.get("physical_delivery_day_before"), -1
                    ),
                    "physical_day_after": _integer(
                        row.get("physical_delivery_day_after"), -1
                    ),
                    "usable_day_before": _integer(row.get("usable_day_before"), -1),
                    "usable_day_after": usable_after,
                    "risk_types": str(row.get("risk_types") or ""),
                    "horizon_status": (
                        "dans l’horizon" if 0 <= usable_after < 720 else "hors horizon"
                    ),
                }
            )
        output.append(
            {
                "scenario_id": scenario_id,
                "label": _scenario_label(scenario_id),
                "orders": sorted(
                    order_rows,
                    key=lambda row: (
                        row["usable_day_after"],
                        row["supplier_id"],
                        _integer(row["source_row"]),
                    ),
                ),
            }
        )
    return output


def _load_orderbook_summary(root: Path) -> dict[str, Any]:
    summary = _read_json(root / "business_summary.json")
    metrics = _read_csv(root / "screening_metrics.csv")
    baseline_by_key = {
        (str(row.get("state_id") or ""), str(row.get("lane_id") or "")): row
        for row in metrics
        if str(row.get("scenario_id") or "") == "baseline_orderbook_replay"
    }
    lane_summaries: list[dict[str, Any]] = []
    for source in summary.get("lane_state_summaries") or []:
        row = dict(source)
        baseline = baseline_by_key[(str(row["state_id"]), str(row["lane_id"]))]
        row.update(
            {
                "prospective_target_stock_qty": _finite_or_none(
                    baseline.get("target_stock_qty")
                ),
                "simulated_measurement_start_stock_qty": _finite_or_none(
                    baseline.get("measurement_start_stock_qty")
                ),
                "measurement_start_stock_scale": _finite_or_none(
                    baseline.get("measurement_start_stock_scale")
                ),
            }
        )
        lane_summaries.append(row)
    return {
        "mode": summary.get("mode"),
        "evidence_labels": summary.get("evidence_labels"),
        "lane_state_summaries": lane_summaries,
        "causal_rule": summary.get("causal_rule"),
        "source_row_semantics": summary.get("source_row_semantics"),
    }


def _build_summary_markdown(payload: Mapping[str, Any]) -> str:
    observed = payload["observed_2025_order_book"]
    calibration = payload["service_state_calibration"]
    metric = payload["service_metric"]
    unit = payload["bom_unit_sensitivity"]
    lot = payload["paired_causal_lot_proof"]
    seed_proof = payload["orderbook_only_lanes"]["paired_multiseed_confirmation"]
    lower, upper = calibration["target_93"]["interval_percentage"]
    lines = [
        "# Bilan métier final — composant 021081",
        "",
        "## Ce qui est observé",
        "",
        (
            f"Le snapshot ERP du 1er janvier 2025 contient **{observed['order_count']} "
            f"lignes techniques de commandes ouvertes**, soit **{observed['quantity_kg']:,.0f} kg**, "
            f"réparties entre **{len(observed['supplier_rows'])} fournisseurs**. Les dates sont "
            "planifiées : ce n’est ni un historique de livraison ni un OTIF. Les identifiants "
            "affichés ne sont pas des numéros industriels de commande ou de lot."
        ),
        "",
        "## Ce que le modèle met en évidence",
        "",
        (
            "Les incidents 021081 testés modifient les quantités ou les dates des réceptions, "
            "mais les couches de stock et de production absorbent encore leur effet sur le produit. "
            "La retenue qualité hypothétique de 180 jours décale les 23 réceptions ; aucune n’est "
            "consommée dans l’horizon, donc aucun descendant 773474 ou 268967 ni effet client "
            "n’est attribuable à ces réceptions. Cela décrit un masque du modèle, pas une "
            "résilience fournisseur démontrée."
        ),
        "",
        "## Calibrage diagnostique de l’état de stock 773474",
        "",
        (
            f"L’indicateur est la **{metric['label_fr']}** sur **{metric['horizon_label']}**. "
            f"Avec l’hypothèse diagnostique de 300 jours de stock 773474, il vaut "
            f"**{100*calibration['target_80']['achieved_service']:.2f} %**. Entre les hypothèses "
            f"384 et 385 jours, il saute de **{lower:.2f} %** à **{upper:.2f} %** à cause de la "
            "production par lots. Ces niveaux ne sont ni une cible de service, ni une politique "
            "de stock, ni une action recommandée ; aucune interpolation n’est revendiquée."
        ),
        "",
        "## Lots et causalité",
        "",
        (
            f"La retenue qualité de 180 jours touche {lot['affected_opening_po_technical_row_count']} "
            "lignes techniques de snapshot et change leur date simulée de disponibilité. Une "
            "ligne technique n’est ni un numéro de commande ni un numéro de lot industriel. "
            "Aucune de ces réceptions "
            "n’est consommée dans l’horizon : aucun descendant 773474 ou 268967 n’est donc "
            "attribuable à ces réceptions dans ce cas."
        ),
        "",
        (
            "Dans le tableau, « physique » désigne le jour planifié d’arrivée et « disponible » "
            "le jour à partir duquel le moteur autorise la consommation. Le paquet ne démontre "
            "pas que leur écart de référence est un délai qualité observé : c’est une donnée "
            "d’entrée du modèle à valider. La retenue qualité hypothétique ajoute 180 jours à "
            "la disponibilité sans déplacer l’arrivée physique."
        ),
        "",
        "## Confirmation multi-graines ciblée 001848",
        "",
        (
            f"Dix graines appariées ont été exécutées, soit "
            f"{seed_proof['physical_engine_run_count']} simulations physiques sur les états "
            "90 et 30 jours. Les résultats sont comparés incident moins référence à graine "
            "identique. Les parts affichées décrivent uniquement les simulations testées : "
            "elles ne sont ni une fréquence historique ni une probabilité fournisseur."
        ),
        "",
        "## Unité de nomenclature à confirmer",
        "",
        unit["why_inconclusive"],
        "",
        (
            "Les deux lectures de nomenclature testées diffèrent d’un facteur **1 000** sur "
            "la consommation 021081."
        ),
        "",
        unit["production_semantics"],
        "",
        "## Décision industrielle",
        "",
        (
            "Ce dossier 021081 ne démontre ici **aucun effet client, aucun coût et aucune action "
            "corrective**. "
            "Avant d’utiliser ces résultats pour dimensionner un stock ou qualifier un fournisseur, "
            "il faut confirmer les unités de BOM, la part de stock réellement libre, les allocations, "
            "les blocages qualité, la durée de vie et les délais réels par fournisseur."
        ),
        "",
    ]
    return "\n".join(lines)


def _autonomous_html(payload: Mapping[str, Any]) -> str:
    data = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).replace(
        "</", "<\\/"
    )
    title = "021081 — commandes planifiées et effets simulés d’incidents"
    return f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--ink:#10233f;--muted:#5d6d82;--line:#dce5ef;--bg:#f3f7fb;--blue:#1468cc;--red:#d94b3d;--green:#16845b;--amber:#a86800;--card:#fff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.48 Inter,Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(125deg,#102b50,#155fa8);color:white;padding:36px max(24px,calc((100vw - 1180px)/2)) 30px}} header h1{{font-size:clamp(28px,4vw,46px);line-height:1.08;margin:6px 0 12px}} header p{{max-width:900px;margin:0;color:#dcecff;font-size:17px}}
nav{{position:sticky;top:0;z-index:3;background:#fff;border-bottom:1px solid var(--line);padding:10px max(16px,calc((100vw - 1180px)/2));display:flex;gap:8px;overflow:auto}} nav a{{white-space:nowrap;text-decoration:none;color:var(--ink);padding:8px 13px;border:1px solid var(--line);border-radius:999px}}
main{{max-width:1180px;margin:auto;padding:24px}} section{{scroll-margin-top:74px;margin-bottom:26px}} h2{{font-size:26px;margin:0 0 13px}} h3{{margin:0 0 8px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 7px 24px #18334c0d}} .metric{{font-size:29px;font-weight:750;display:block;margin:5px 0}} .tag{{font-size:11px;font-weight:800;letter-spacing:.07em;border-radius:99px;padding:5px 9px;display:inline-block;margin-right:5px}} .observed{{background:#e7f2ff;color:#0758a9}} .simulated{{background:#e8f7f0;color:#08714a}} .hypothesis{{background:#fff1dd;color:#8a5200}} .priority{{background:#eee9ff;color:#5934a5}} .warning{{background:#fff0ee;color:#a82f24}} .plain{{color:var(--muted)}} .alert{{border-left:5px solid var(--red)}} .definition{{border-top:4px solid var(--blue)}}
table{{width:100%;border-collapse:collapse;background:#fff}} th,td{{padding:10px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} th{{font-size:12px;text-transform:uppercase;color:var(--muted);position:sticky;top:52px;background:#f8fafc}} .table-wrap{{max-height:560px;overflow:auto;border:1px solid var(--line);border-radius:14px}} select{{font:inherit;padding:10px 13px;border:1px solid #b9c8d8;border-radius:10px;background:white;min-width:min(100%,420px)}} .bar{{height:10px;border-radius:99px;background:#e5ebf2;overflow:hidden;margin-top:7px}} .bar span{{display:block;height:100%;background:var(--blue)}} .bad{{color:var(--red);font-weight:700}} .good{{color:var(--green);font-weight:700}} .two{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} code{{font-size:12px}} footer{{padding:25px;color:var(--muted);text-align:center}} @media(max-width:760px){{.two{{grid-template-columns:1fr}} main{{padding:16px}} th{{top:50px}}}}
</style></head><body>
<header><span class="tag observed">OBSERVÉ</span><span class="tag simulated">SIMULÉ</span><h1>{html.escape(title)}</h1><p>Une lecture en trois questions : quelles lignes planifiées sont exposées, quelles couches absorbent l’incident, et quelles données doivent être confirmées avant décision.</p></header>
<nav><a href="#synthese">1 · Comprendre le masque</a><a href="#commandes">2 · Voir commandes et lots</a><a href="#unite">3 · Décider et valider</a></nav>
<main>
<section id="synthese"><h2>Ce que l’on peut dire aujourd’hui</h2><div class="grid" id="headline"></div><div class="card alert" style="margin-top:14px"><h3>Conclusion centrale</h3><p>Les incidents testés affectent bien les réceptions 021081. Leur absence d’effet client dans les états testés vient des couches de stock et de production — et parfois de l’absence de consommation de la réception dans l’horizon. Ce n’est pas une preuve que le fournisseur est peu critique.</p><p><b>Dans ce dossier 021081, aucun effet client, aucun coût et aucune action corrective ne sont démontrés.</b></p></div><h3 style="margin-top:18px">Comment lire les étiquettes</h3><div class="grid" id="evidence"></div></section>
<section id="etats"><h2>Où se situe le masque ?</h2><div class="card"><p><b>Pourcentage affiché :</b> part simulée du volume demandé du produit 268967 servie à la date attendue sur J0 à J719 (720 jours).</p><p class="plain">Chaque ligne modifie une couche différente. Le pourcentage est celui de la référence simulée de cet état, avant incident. Il ne mesure ni l’OTIF du fournisseur ni une performance observée.</p><div class="table-wrap"><table><thead><tr><th>État simulé</th><th>268967 servi à date sur 720 j</th><th>021081 consommé</th><th>Production 773474</th><th>Incidents avec effet aval</th></tr></thead><tbody id="states"></tbody></table></div></div><div class="card" style="margin-top:14px"><span class="tag hypothesis">HYPOTHÈSE</span><span class="tag simulated">SIMULÉ</span><h3>Calibrage diagnostique de l’état de stock 773474</h3><div id="calibration"></div></div></section>
<section id="commandes"><h2>Les 23 lignes techniques 021081 avant / après incident</h2><div class="card"><label for="scenario"><b>Référence simulée ou hypothèse d’incident affichée</b></label> <span id="scenarioNature"></span><br><select id="scenario"></select><p><b>Attention :</b> une « ligne technique » est une ligne du snapshot ERP. Ce n’est ni un numéro de commande industrielle ni un numéro de lot industriel.</p><p class="plain"><b>Physique</b> = jour planifié d’arrivée. <b>Disponible</b> = jour à partir duquel le moteur autorise la consommation. Le paquet ne démontre pas que l’écart de référence entre ces deux jours est un délai qualité observé : c’est une donnée d’entrée du modèle à valider. La retenue qualité hypothétique ajoute 180 jours à la disponibilité sans déplacer l’arrivée physique.</p><div class="table-wrap"><table><thead><tr><th>Ligne technique</th><th>Fournisseur</th><th>Quantité prévue / disponible</th><th>Arrivée physique avant → après</th><th>Disponible avant → après</th><th>Horizon</th></tr></thead><tbody id="orders"></tbody></table></div></div><div class="card alert" style="margin-top:14px" id="lots"></div></section>
<section id="unite"><h2>Décider et valider</h2><div class="card"><h3>Unité de nomenclature : l’essai n’arbitre pas</h3><span class="tag priority">SIGNAL DE PRIORITÉ</span><span class="tag warning">À VALIDER AVEC L’INDUSTRIEL</span><p id="unitwhy"></p><p><b>Les deux lectures testées diffèrent d’un facteur 1 000 sur la consommation 021081.</b></p><p class="plain">Les pourcentages ci-dessous ont tous la même définition : part simulée du volume demandé de 268967 servie à la date attendue sur J0 à J719.</p><div class="table-wrap"><table><thead><tr><th>État / scénario</th><th>Consommation littérale</th><th>Hypothèse ÷1000</th><th>268967 à date — littéral</th><th>268967 à date — ÷1000</th></tr></thead><tbody id="unitrows"></tbody></table></div><p class="plain" id="prodsem"></p></div></section>
<section id="autres"><h2>Deux voies visibles uniquement dans le carnet de commandes</h2><div class="card"><p class="plain">Ces lignes complètent le périmètre sans être mélangées au classement des voies dynamiques. Le snapshot 2025 et les hypothèses de couverture réduite restent deux lectures séparées.</p><div id="lanes"></div><div class="card" id="seedproof" style="margin-top:14px"></div></div></section>
<section id="limites"><h2>Ce qu’il faut confirmer avant décision</h2><div class="grid" id="limits"></div></section>
</main><footer>Paquet autonome — aucun appel réseau, aucune ressource externe.</footer>
<script>const P={data};
const pct=v=>(100*Number(v)).toLocaleString('fr-FR',{{minimumFractionDigits:2,maximumFractionDigits:2}})+' %';
const points=v=>(100*Number(v)).toLocaleString('fr-FR',{{minimumFractionDigits:2,maximumFractionDigits:2}})+' point(s)';
const num=(v,d=0)=>Number(v).toLocaleString('fr-FR',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const obs=P.observed_2025_order_book, cal=P.service_state_calibration, lot=P.paired_causal_lot_proof;
document.querySelector('#headline').innerHTML=`<article class="card"><span class="tag observed">OBSERVÉ</span><b class="metric">${{obs.order_count}} lignes · ${{num(obs.quantity_kg)}} kg</b><p>Commandes ouvertes planifiées dans le snapshot 2025, réparties entre ${{obs.supplier_rows.length}} fournisseurs. Ce n’est pas un historique de livraison.</p></article><article class="card"><span class="tag hypothesis">HYPOTHÈSE</span><span class="tag simulated">SIMULÉ</span><b class="metric">${{lot.technical_rows_with_paired_receipt_effect}} / ${{lot.affected_opening_po_technical_row_count}} réceptions</b><p>La retenue qualité de 180 jours décale leur disponibilité ; ${{lot.technical_rows_with_paired_descendant_effect}} descendant aval est modifié dans l’horizon.</p></article><article class="card"><span class="tag priority">SIGNAL DE PRIORITÉ</span><b class="metric">× 1 000</b><p>Écart entre les deux interprétations testées de l’unité de nomenclature 773474–021081. L’unité doit être confirmée avant toute décision.</p></article>`;
const evidence=[['observed','OBSERVÉ',P.evidence_dictionary.observed],['simulated','SIMULÉ',P.evidence_dictionary.simulated],['priority','SIGNAL DE PRIORITÉ',P.evidence_dictionary.priority_signal],['hypothesis','HYPOTHÈSE',P.evidence_dictionary.hypothesis]];
document.querySelector('#evidence').innerHTML=evidence.map(x=>`<article class="card definition"><span class="tag ${{x[0]}}">${{x[1]}}</span><p>${{esc(x[2])}}</p></article>`).join('');
document.querySelector('#states').innerHTML=P.state_layer_analysis.map(r=>`<tr><td><b>${{esc(r.label)}}</b><br><small>${{esc(r.reduced_layers||'toutes les couches du snapshot')}}</small></td><td>${{pct(r.baseline_service)}}<div class="bar"><span style="width:${{100*r.baseline_service}}%"></span></div></td><td>${{num(r.component_021081_consumed_kg)}} kg</td><td>${{num(r.dynamic_production_773474_g/1e6,1)}} M G + ${{num(r.opening_production_order_773474_g/1e6,1)}} M G ouverts</td><td class="${{r.incidents_with_downstream_effect?'bad':'good'}}">${{r.incidents_with_downstream_effect}} / ${{r.tested_incident_count}}</td></tr>`).join('');
document.querySelector('#calibration').innerHTML=`<p><b>Indicateur lu :</b> part simulée du volume demandé du produit 268967 servie à la date attendue sur J0 à J719.</p><p><b>Repère diagnostique proche de 80 % :</b> l’hypothèse de 300 jours de stock 773474 donne ${{pct(cal.target_80.achieved_service)}}.</p><p><b>Repère diagnostique autour de 93 % :</b> 384 jours donnent ${{num(cal.target_93.interval_percentage[0],2)}} %, puis 385 jours ${{num(cal.target_93.interval_percentage[1],2)}} %. La production se fait par lots : aucun 93 % exact n’est inventé.</p><p><b>Ce que cela ne signifie pas :</b> 300, 384 et 385 jours ne sont ni des cibles, ni une politique de stock, ni des actions recommandées. Ils servent uniquement à comprendre la réponse discrète du modèle.</p><p><b>Incidents appariés :</b> dans les trois états, la disponibilité à 25 %, le rendement utilisable à 10 % et la retenue qualité de 180 jours ne changent pas l’indicateur aval. Les réceptions changent, mais 021081 n’est pas consommé dans ces états où seul le stock 773474 est calibré.</p>`;
const sel=document.querySelector('#scenario'); P.drilldown_scenarios.forEach((s,i)=>sel.add(new Option(s.label,String(i))));
function drawOrders(){{const index=Number(sel.value||0),s=P.drilldown_scenarios[index];document.querySelector('#scenarioNature').innerHTML=index===0?'<span class="tag simulated">SIMULÉ</span>':'<span class="tag hypothesis">HYPOTHÈSE</span><span class="tag simulated">SIMULÉ</span>';document.querySelector('#orders').innerHTML=s.orders.map(r=>`<tr><td><code>${{esc(r.source_row)}}</code></td><td>${{esc(r.supplier_id.replace('SDC-',''))}}</td><td>${{num(r.planned_qty_kg)}} / ${{num(r.usable_qty_after_kg)}} kg</td><td>J${{r.physical_day_before}} → J${{r.physical_day_after}}</td><td>J${{r.usable_day_before}} → J${{r.usable_day_after}}</td><td>${{esc(r.horizon_status)}}</td></tr>`).join('')}} sel.addEventListener('change',drawOrders);drawOrders();
document.querySelector('#lots').innerHTML=`<h3>Traçabilité causale disponible — retenue qualité hypothétique de 180 jours</h3><p><b>${{lot.technical_rows_with_paired_receipt_effect}} / ${{lot.affected_opening_po_technical_row_count}}</b> lignes techniques changent de date simulée de disponibilité, mais <b>${{lot.technical_rows_with_paired_descendant_effect}}</b> change un descendant. Les réceptions concernées ne sont pas consommées dans l’horizon : aucun lot 773474 ou 268967 causal et aucun effet client ne doivent être inventés.</p><p class="plain">Cette vue suit des lignes techniques du snapshot, pas de vrais numéros de lot ou de commande. Elle ne démontre ici ni coût ni effet d’une action corrective.</p>`;
document.querySelector('#unitwhy').textContent=P.bom_unit_sensitivity.why_inconclusive;document.querySelector('#prodsem').textContent=P.bom_unit_sensitivity.production_semantics;
document.querySelector('#unitrows').innerHTML=P.bom_unit_sensitivity.rows.map(r=>`<tr><td><b>${{esc(r.state_label)}}</b><br><small>${{esc(r.scenario_label)}}</small></td><td>${{Number.isFinite(r.literal_consumption_kg)?num(r.literal_consumption_kg,3):'—'}} kg</td><td>${{Number.isFinite(r.divided_ratio_consumption_kg)?num(r.divided_ratio_consumption_kg,3):'—'}} kg</td><td>${{pct(r.literal_service)}}</td><td>${{pct(r.divided_ratio_service)}}</td></tr>`).join('');
document.querySelector('#lanes').innerHTML=['snapshot','prospective'].map(k=>{{const block=P.orderbook_only_lanes[k];return `<h3>${{k==='snapshot'?'Référence simulée à partir du snapshot 2025':'Hypothèses prospectives de couverture à 90/30 jours'}}</h3><div class="table-wrap"><table><thead><tr><th>Voie</th><th>Lignes planifiées</th><th>Stock J0 simulé</th><th>Couverture dans le modèle</th><th>Réception touchée</th><th>Descendant simulé touché</th><th>Indicateur client touché</th></tr></thead><tbody>${{block.lane_state_summaries.map(r=>`<tr><td>${{esc(r.supplier_id.replace('SDC-',''))}} → ${{esc(r.destination_id)}} / ${{esc(r.item_id.replace('item:',''))}}<br><small>${{esc(r.state_id)}}</small></td><td>${{r.planned_order_line_count}} ligne(s), ${{num(r.planned_order_qty_standard)}} ${{esc(r.standard_uom)}}</td><td>${{num(r.simulated_measurement_start_stock_qty,1)}} ${{esc(r.standard_uom)}}</td><td>${{num(r.v10_physical_cover_days_before_dynamic_arrivals,1)}} j</td><td>${{r.stress_with_receipt_effect_count}} / ${{r.tested_stress_count}}</td><td>${{r.stress_with_descendant_lot_effect_count}} / ${{r.tested_stress_count}}</td><td>${{r.stress_with_client_effect_count}} / ${{r.tested_stress_count}}</td></tr>`).join('')}}</tbody></table></div>`}}).join('');
const seedProof=P.orderbook_only_lanes.paired_multiseed_confirmation;document.querySelector('#seedproof').innerHTML=`<h3>Confirmation sur dix répétitions comparables</h3><p>${{seedProof.physical_engine_run_count}} simulations couvrent deux hypothèses de stock. Dans chaque comparaison, la référence et l’incident « 25 % de quantité disponible » utilisent les mêmes conditions aléatoires afin d’isoler l’effet de l’incident.</p><div class="table-wrap"><table><thead><tr><th>État</th><th>Répétitions comparées</th><th>Réception touchée</th><th>Généalogie aval touchée</th><th>Indicateur client touché</th><th>Écart moyen du volume 268091 servi à date sur 720 j</th></tr></thead><tbody>${{seedProof.state_summaries.map(r=>`<tr><td>${{esc(r.state_id)}}</td><td>${{r.paired_seed_count}}</td><td>${{r.receipt_effect_seed_count}} / ${{r.paired_seed_count}}</td><td>${{r.descendant_lot_effect_seed_count}} / ${{r.paired_seed_count}}</td><td>${{r.client_effect_seed_count}} / ${{r.paired_seed_count}}</td><td>${{points(r.paired_service_delta_mean)}}</td></tr>`).join('')}}</tbody></table></div><p class="plain">Ces décomptes décrivent seulement les dix répétitions testées. Ils ne mesurent ni une fréquence historique d’incident ni une probabilité fournisseur.</p>`;
document.querySelector('#limits').innerHTML=P.limitations.map((x,i)=>`<article class="card"><span class="tag ${{i<2?'warning':'hypothesis'}}">${{i<2?'À VALIDER':'LIMITE'}}</span><p>${{esc(x)}}</p></article>`).join('');
</script></body></html>'''


def build_package(
    *,
    demasking_dir: Path,
    unit_dir: Path,
    calibration_dir: Path,
    orderbook_snapshot_dir: Path,
    orderbook_prospective_dir: Path,
    orderbook_confirmation_dir: Path,
    causal_proof_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FinalPackageError(f"Final output must be new or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    demasking_manifest, demasking_record = _package_record(
        demasking_dir,
        role="replay_2025_and_state_layer_demasking_v2",
        required_files=(
            "screening_metrics.csv",
            "layer_effect_table.csv",
            "observed_order_book_audit.json",
            "execution_provenance_audit.json",
        ),
        require_v2_suffix=True,
    )
    unit_manifest, unit_record = _package_record(
        unit_dir,
        role="bom_unit_sensitivity_v2",
        required_files=(
            "unit_sensitivity_comparison.csv",
            "unit_sensitivity_metrics.csv",
            "execution_provenance_audit.json",
        ),
        require_v2_suffix=True,
    )
    calibration_manifest, calibration_record = _package_record(
        calibration_dir,
        role="calibration_audited_post_correction_300_384_385_days",
        required_files=(
            "baseline_calibration_metrics.csv",
            "stock_773_state_design.csv",
            "execution_provenance_audit.json",
        ),
        require_v2_suffix=False,
    )
    calibration_record["version_semantics"] = (
        "Calibration auditée après correction, explicitement retenue pour les "
        "états 300/384/385 jours. Le suffixe de dossier est un nom d’artefact et "
        "ne désigne pas l’ancien active-flow/demasking/unité non retenu."
    )
    snapshot_manifest, snapshot_record = _package_record(
        orderbook_snapshot_dir,
        role="orderbook_only_snapshot_v2",
        required_files=(
            "screening_metrics.csv",
            "business_summary.json",
            "execution_provenance_audit.json",
        ),
        require_v2_suffix=True,
    )
    prospective_manifest, prospective_record = _package_record(
        orderbook_prospective_dir,
        role="orderbook_only_prospective_v2",
        required_files=(
            "screening_metrics.csv",
            "business_summary.json",
            "execution_provenance_audit.json",
        ),
        require_v2_suffix=True,
    )
    confirmation_manifest, confirmation_record = _package_record(
        orderbook_confirmation_dir,
        role="orderbook_only_001848_paired_multiseed_summary_v2",
        required_files=(
            "paired_seed_statistical_summary.csv",
            "statistical_summary.json",
        ),
        require_v2_suffix=True,
    )
    confirmation_summary = _read_json(
        orderbook_confirmation_dir / "statistical_summary.json"
    )
    if (
        _integer(confirmation_manifest.get("paired_seed_count_per_state")) != 10
        or _integer(confirmation_manifest.get("physical_engine_run_count")) != 40
        or _integer(confirmation_summary.get("paired_seed_count_per_state")) != 10
        or len(confirmation_summary.get("state_summaries") or []) != 2
    ):
        raise FinalPackageError(
            "001848 paired multi-seed confirmation is incomplete"
        )
    causal_root = causal_proof_dir.resolve()
    if not causal_root.name.lower().endswith("_v2"):
        raise FinalPackageError("Paired causal proof must be a V2 artifact")
    causal_manifest_path = causal_root / "causal_proof_manifest.json"
    causal_summary_path = causal_root / "causal_lot_proof_summary.json"
    causal_rows_path = causal_root / "receipt_paired_causal_comparison.csv"
    if not all(
        path.is_file()
        for path in (causal_manifest_path, causal_summary_path, causal_rows_path)
    ):
        raise FinalPackageError("Missing paired causal lot proof")
    causal_manifest = _read_json(causal_manifest_path)
    if (
        str(causal_manifest.get("status") or "") != "complete"
        or not _truthy(
            causal_manifest.get("source_execution_provenance_reproducible")
        )
        or str(causal_manifest.get("source_campaign_manifest_sha256") or "")
        != demasking_record["manifest_sha256"]
    ):
        raise FinalPackageError(
            "Paired causal proof is not tied to the audited demasking V2 source"
        )
    for name, expected in (causal_manifest.get("output_sha256") or {}).items():
        path = causal_root / str(name)
        if not path.is_file() or _sha(path) != str(expected):
            raise FinalPackageError(f"Causal proof output hash mismatch: {path}")

    observed = _read_json(demasking_dir / "observed_order_book_audit.json")
    if not _truthy(observed.get("validated")) or _integer(observed.get("order_count")) != 23:
        raise FinalPackageError("Observed 021081 order-book audit is not valid")
    states, dashboard_regimes = _collect_demasking(demasking_dir)
    calibration = _collect_calibration(calibration_dir)
    unit = _collect_unit(unit_dir)
    causal_summary = _read_json(causal_summary_path)
    payload: dict[str, Any] = {
        "schema_version": "supplier-021081-final-dashboard.v2",
        "created_at_utc": _utc_now(),
        "title": "021081 — commandes planifiées et effets simulés d’incidents",
        "evidence_dictionary": {
            "observed": (
                "Donnée présente dans le snapshot industriel fourni. Ici, une date "
                "observée est une date planifiée dans le fichier, pas la preuve d’une "
                "livraison réellement exécutée."
            ),
            "simulated": (
                "Résultat calculé par le moteur pour l’état, l’incident et l’horizon "
                "indiqués ; ce n’est pas une performance fournisseur mesurée."
            ),
            "priority_signal": (
                "Point à vérifier en priorité avec les équipes métier ; ce n’est ni "
                "une probabilité d’incident ni une recommandation automatique."
            ),
            "hypothesis": (
                "Incident, unité, couverture de stock ou paramètre introduit pour "
                "tester le système et à valider avec l’industriel."
            ),
        },
        "service_metric": SERVICE_METRIC,
        "observed_2025_order_book": observed,
        "state_layer_analysis": states,
        "state_regime_effects": dashboard_regimes,
        "service_state_calibration": calibration,
        "bom_unit_sensitivity": unit,
        "drilldown_scenarios": _collect_drilldown(demasking_dir),
        "paired_causal_lot_proof": causal_summary,
        "orderbook_only_lanes": {
            "snapshot": _load_orderbook_summary(orderbook_snapshot_dir),
            "prospective": _load_orderbook_summary(orderbook_prospective_dir),
            "paired_multiseed_confirmation": confirmation_summary,
        },
        "intermediate_773474_masking_audit": {
            **MASKING_AUDIT,
            "sources": {
                "demasking_manifest_sha256": demasking_record["manifest_sha256"],
                "calibration_manifest_sha256": calibration_record["manifest_sha256"],
                "source_graph_sha256": demasking_manifest.get("source_graph_sha256"),
            },
            "formulas": {
                "opening_stock_total_g": "9,600,000 G at SDC-1450 + 14,593,000 G at M-1430",
                "approx_horizon_need_g": "29 released 268967 lots × modeled 773474 need per lot",
                "stock_multiple_of_horizon_need": "24,193,000 / 30,182,579.4116",
                "stock_plus_production_multiple_of_horizon_need": "(24,193,000 + 28,800,000) / 30,182,579.4116",
            },
            "interpretation": (
                "Le masque est cumulatif : stock et production 773474, stock 021081 "
                "et carnet 021081. Réduire une seule couche n’est pas une supply globale lean."
            ),
        },
        "limitations": [
            "L’unité KG/G/L de la BOM 773474–021081 reste à confirmer ; aucune branche n’est déclarée correcte.",
            "Dans l’état observé l’unité est masquée par le stock ; dans l’état conjoint 30 jours, 021081 n’est pas consommé.",
            "Les commandes ouvertes et leurs dates planifiées ne sont ni des livraisons réelles ni un historique OTIF.",
            "Une ligne technique du snapshot n’est ni un numéro de commande industrielle ni un numéro de lot industriel.",
            "Le délai entre arrivée physique et disponibilité est une donnée d’entrée du modèle ; ce paquet ne démontre pas qu’il s’agit d’un délai qualité observé.",
            "L’absence d’effet aval signifie absorption par l’état testé ou absence de consommation dans l’horizon, pas résilience acquise.",
            "Les scénarios testés ne mesurent ni fréquence historique d’incident ni probabilité fournisseur.",
            "Ce dossier 021081 ne démontre ici aucun effet client, aucun coût et aucune action corrective.",
            "Valider stock libre/bloqué/alloué/périmé, site et propriétaire, durée de vie, unités et alternatives approuvées.",
        ],
        "scientific_conclusions": {
            "target_80": (
                "Calibrage diagnostique : l’hypothèse de 300 jours de stock 773474 "
                "donne un état discret proche de 80 %. Ce n’est ni une cible ni une action."
            ),
            "target_93": (
                "Calibrage diagnostique : le repère 93 % est encadré par 86,73 % "
                "à 384 jours et 97,07 % à 385 jours ; aucune interpolation n’est "
                "permise et aucun niveau de stock n’est recommandé."
            ),
            "calibrated_incidents": (
                "Les trois incidents 021081 restent absorbés dans les états 300/384/385 ; "
                "les réceptions changent, mais la consommation 021081 y reste nulle."
            ),
            "unit": unit["why_inconclusive"],
            "lots": (
                "Sous la retenue qualité hypothétique de 180 jours, 23 réceptions "
                "changent mais aucune n’a de descendant consommé dans l’horizon ; "
                "aucun effet client, coût ou action n’est démontré."
            ),
        },
    }

    observed_final = {
        **observed,
        "artifact_provenance": {
            "source_package": demasking_record,
            "copied_without_numeric_change": True,
            "interpretation": (
                "Snapshot of planned open orders, not observed actual delivery history."
            ),
        },
    }
    _write_json(output_dir / "observed_order_book_audit.json", observed_final)
    _write_json(output_dir / "future_autonomous_page_payload.json", payload)
    _write_csv(output_dir / "state_layer_effect_summary.csv", states)
    calibrated_flat = [
        {
            "state_id": state["state_id"],
            "cover_days": state["cover_days"],
            "baseline_service": state["baseline_service"],
            "scenario_id": incident["scenario_id"],
            "scenario_label": incident["label"],
            "simulated_replayed_shipped_qty_kg": incident[
                "replayed_shipped_qty_kg"
            ],
            "simulated_service": incident["service"],
            "service_delta_vs_paired_baseline": incident["service_delta"],
            "released_268967_delta_vs_paired_baseline": incident[
                "released_268967_delta"
            ],
            "interpretation": (
                "réception affectée mais aucun effet aval apparié dans cet état; masque, pas résilience"
            ),
        }
        for state in calibration["states"]
        for incident in state["tested_incidents"]
    ]
    _write_csv(
        output_dir / "calibrated_state_incident_effects.csv", calibrated_flat
    )
    by_scenario: dict[str, list[Mapping[str, Any]]] = {}
    for row in calibrated_flat:
        by_scenario.setdefault(str(row["scenario_id"]), []).append(row)
    mechanism_summary = [
        {
            "scenario_id": scenario_id,
            "scenario_label": group[0]["scenario_label"],
            "tested_state_count": len(group),
            "states_with_simulated_downstream_effect": sum(
                abs(_number(row["service_delta_vs_paired_baseline"])) > 1e-12
                or abs(
                    _number(row["released_268967_delta_vs_paired_baseline"])
                )
                > 1e-9
                for row in group
            ),
            "maximum_service_loss_percentage_points": max(
                (
                    -100 * _number(row["service_delta_vs_paired_baseline"])
                    for row in group
                ),
                default=0.0,
            ),
            "evidence_label": "sensibilité aux modes testés",
            "historical_recurrence_claim_allowed": False,
        }
        for scenario_id, group in sorted(by_scenario.items())
    ]
    _write_csv(
        output_dir / "mechanism_sensitivity_summary_021081.csv",
        mechanism_summary,
    )
    _write_csv(
        output_dir / "bom_unit_sensitivity_summary.csv", unit["rows"]
    )
    orderbook_flat = [
        {"mode": mode, **row}
        for mode, block in payload["orderbook_only_lanes"].items()
        for row in block.get("lane_state_summaries", [])
    ]
    _write_csv(output_dir / "orderbook_only_lane_summary.csv", orderbook_flat)
    _write_csv(
        output_dir / "orderbook_only_001848_paired_seed_summary.csv",
        confirmation_summary["state_summaries"],
    )
    (output_dir / "RESUME_METIER_021081_FINAL.md").write_text(
        _build_summary_markdown(payload), encoding="utf-8"
    )
    autonomous_page = _autonomous_html(payload)
    (output_dir / "supplier_021081_final_v3.html").write_text(
        autonomous_page, encoding="utf-8"
    )
    (output_dir / "index.html").write_text(autonomous_page, encoding="utf-8")

    source_packages = [
        demasking_record,
        unit_record,
        calibration_record,
        snapshot_record,
        prospective_record,
        confirmation_record,
        {
            "role": "paired_causal_lot_proof_from_demasking_v2",
            "directory": str(causal_root),
            "status": "complete",
            "manifest_sha256": _sha(causal_manifest_path),
            "proof_builder_sha256": causal_manifest.get("proof_builder_sha256"),
            "source_execution_provenance_reproducible": True,
            "files_sha256": {
                causal_manifest_path.name: _sha(causal_manifest_path),
                causal_summary_path.name: _sha(causal_summary_path),
                causal_rows_path.name: _sha(causal_rows_path),
            },
            "source_campaign_manifest_sha256": demasking_record["manifest_sha256"],
        },
    ]
    manifest: dict[str, Any] = {
        "schema_version": "supplier-021081-final-component-package.v2",
        "status": "complete",
        "created_at_utc": _utc_now(),
        "mode": "audited_v2_reporting_consolidation",
        "reporting_revision": "v3_business_wording",
        "report_builder": str(Path(__file__).resolve()),
        "report_builder_sha256": _sha(Path(__file__).resolve()),
        "simulation_rerun_by_builder": False,
        "previous_outputs_modified": False,
        "source_packages": source_packages,
        "all_execution_packages_audited": True,
        "reproducibility_wording_allowed": True,
        "observed_order_book_audit": observed_final,
        "scientific_scope": {
            "replay": (
                "23 planned opening purchase-order rows replayed from the 2025-01-01 snapshot"
            ),
            "dynamic_clean_reference_coherence": (
                "The clean dynamic reference has zero 021081 opening-order arrival; "
                "the snapshot replay deliberately injects the 23 planned rows."
            ),
            "quantity_unit_provenance": (
                "021081 order-book quantities use the graph standard quantity field in KG."
            ),
            "supplier_claim_boundary": (
                "No historical incident frequency, OTIF or supplier probability is inferred."
            ),
            "lot_trace": (
                "source_row is a technical source line. Exposure and paired causal "
                "downstream effect are reported separately."
            ),
            "critical_bom_unit_validation": unit,
            "intermediate_773474_masking_audit": payload[
                "intermediate_773474_masking_audit"
            ],
        },
        "outputs": {
            "dashboard_payload": "future_autonomous_page_payload.json",
            "observed_order_audit": "observed_order_book_audit.json",
            "autonomous_html": "index.html",
            "autonomous_html_named_copy": "supplier_021081_final_v3.html",
            "business_summary": "RESUME_METIER_021081_FINAL.md",
            "state_layer_effects": "state_layer_effect_summary.csv",
            "calibrated_incident_effects": "calibrated_state_incident_effects.csv",
            "mechanism_sensitivity": "mechanism_sensitivity_summary_021081.csv",
            "unit_sensitivity": "bom_unit_sensitivity_summary.csv",
            "orderbook_only_lanes": "orderbook_only_lane_summary.csv",
            "orderbook_only_001848_paired_seeds": (
                "orderbook_only_001848_paired_seed_summary.csv"
            ),
        },
        "output_sha256": {
            name: _sha(output_dir / name)
            for name in (
                "future_autonomous_page_payload.json",
                "observed_order_book_audit.json",
                "supplier_021081_final_v3.html",
                "index.html",
                "RESUME_METIER_021081_FINAL.md",
                "state_layer_effect_summary.csv",
                "calibrated_state_incident_effects.csv",
                "mechanism_sensitivity_summary_021081.csv",
                "bom_unit_sensitivity_summary.csv",
                "orderbook_only_lane_summary.csv",
                "orderbook_only_001848_paired_seed_summary.csv",
            )
        },
        "input_manifest_statuses": {
            "demasking": demasking_manifest.get("status"),
            "unit": unit_manifest.get("status"),
            "calibration": calibration_manifest.get("status"),
            "orderbook_snapshot": snapshot_manifest.get("status"),
            "orderbook_prospective": prospective_manifest.get("status"),
            "orderbook_confirmation": confirmation_manifest.get("status"),
        },
    }
    _write_json(output_dir / "campaign_manifest.json", manifest)
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demasking-dir", required=True)
    parser.add_argument("--unit-dir", required=True)
    parser.add_argument("--calibration-dir", required=True)
    parser.add_argument("--orderbook-snapshot-dir", required=True)
    parser.add_argument("--orderbook-prospective-dir", required=True)
    parser.add_argument("--orderbook-confirmation-dir", required=True)
    parser.add_argument("--causal-proof-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_package(
        demasking_dir=Path(args.demasking_dir),
        unit_dir=Path(args.unit_dir),
        calibration_dir=Path(args.calibration_dir),
        orderbook_snapshot_dir=Path(args.orderbook_snapshot_dir),
        orderbook_prospective_dir=Path(args.orderbook_prospective_dir),
        orderbook_confirmation_dir=Path(args.orderbook_confirmation_dir),
        causal_proof_dir=Path(args.causal_proof_dir),
        output_dir=Path(args.output_dir),
    )
    print(
        "[OK] final 021081 V3 reporting package (V2 data controls preserved): "
        + str(Path(args.output_dir).resolve())
        + f" ({len(manifest['source_packages'])} signed sources)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
