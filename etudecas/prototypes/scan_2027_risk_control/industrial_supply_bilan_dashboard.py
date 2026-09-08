#!/usr/bin/env python3
"""Build the compact, offline, three-view industrial supply assessment.

The generated page embeds only small, derived values and SVG charts.  It does
not load data at display time, does not call a network resource and does not
change any existing simulation, launcher or HTML artefact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_risk_results_dashboard as network_results,
)


SCHEMA_VERSION = "etudecas.industrial_supply_bilan_dashboard.v1"
MAX_HTML_BYTES = 2 * 1024 * 1024

MECHANISM_LABELS = {
    "transport_delay": "retard d'expédition ou de transport",
    "delivery_delay": "retard de livraison",
    "lead_extra": "allongement du délai fournisseur",
    "intermittent_delay": "retards intermittents",
    "quality_delay": "mise à disposition retardée par la qualité",
    "quality_hold": "retenue qualité",
    "quality_yield": "quantité reçue non utilisable",
    "reliability": "quantité expédiée incomplète",
    "supply_availability": "indisponibilité temporaire",
    "availability": "indisponibilité temporaire",
    "capacity": "capacité fournisseur insuffisante",
}

STATUS_LABELS = {
    "complete": "Terminé",
    "in_progress": "En cours",
    "not_concluded": "Non conclu",
    "unavailable": "Non disponible",
    "preselection": "Présélection",
    "groupe_prioritaire": "Groupe prioritaire",
    "priorites_simulees_stabilisees_30": "Priorités simulées stabilisées",
    "exploratory_complete": "Étude exploratoire complète",
    "scope_audited": "Périmètre audité",
    "envelope_service_top3_released": "Trio sous enveloppe",
    "priority_group_only": "Groupe non ordonné",
}

NETWORK_STABILIZED_STATE = "priorites_simulees_stabilisees_30"
NETWORK_PRESELECTION_STATE = "preselection"
NETWORK_PRIORITY_GROUP_STATE = "groupe_prioritaire"
NETWORK_ENVELOPE_TRIO_STATE = "envelope_service_top3_released"
NETWORK_FROZEN_GROUP_STATE = "priority_group_only"
FROZEN_NETWORK_INPUT_STATUS = "signed_scientific_overlay_and_audits_valid"
FROZEN_NETWORK_METRICS = (
    "horizon_on_due_service_delta",
    "worst_rolling_28d_on_due_delta",
    "incremental_backlog_days_per_requested_unit",
    "released_production_shortfall_ratio",
)
FROZEN_NETWORK_HYPOTHESES = ("transport_delay", "supply_availability")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key): "" if value is None else str(value) for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def _optional_csv(directory: Path | None, name: str) -> list[dict[str, str]]:
    path = directory / name if directory else None
    return _read_csv(path) if path and path.is_file() else []


def _optional_json(directory: Path | None, name: str) -> dict[str, Any]:
    path = directory / name if directory else None
    return _read_json(path) if path and path.is_file() else {}


def _number(value: object, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else default
    text = str(value).strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    if not text or text.lower() in {"nan", "none", "null"}:
        return default
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        number = float(text.rstrip("%"))
    except ValueError:
        return default
    if text.endswith("%"):
        number /= 100.0
    return number if math.isfinite(number) else default


def _integer(value: object, default: int = 0) -> int:
    return int(round(_number(value, float(default))))


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "oui"}


def _fr(value: object, digits: int = 0) -> str:
    number = _number(value, math.nan)
    if not math.isfinite(number):
        return "non disponible"
    rendered = f"{number:,.{digits}f}"
    return rendered.replace(",", "\u202f").replace(".", ",")


def _compact(value: object, digits: int = 1) -> str:
    number = _number(value, math.nan)
    if not math.isfinite(number):
        return "non disponible"
    absolute = abs(number)
    if absolute >= 1_000_000:
        return f"{_fr(number / 1_000_000, digits)} M"
    if absolute >= 1_000:
        return f"{_fr(number / 1_000, digits)} k"
    return _fr(number, digits if absolute < 100 else 0)


def _percent(value: object, digits: int = 1) -> str:
    return f"{_fr(_number(value) * 100.0, digits)} %"


def _points(value: object, digits: int = 1) -> str:
    return f"{_fr(abs(_number(value)) * 100.0, digits)} points"


def _supplier_label(value: object) -> str:
    text = str(value or "").strip()
    return text[4:] if text.startswith("SDC-") else text


def _mechanism_label(value: object) -> str:
    key = str(value or "").strip()
    return MECHANISM_LABELS.get(key, key.replace("_", " ") or "stress non précisé")


def _status_badge(state: str, detail: str = "") -> str:
    label = STATUS_LABELS.get(state, state)
    title = f' title="{html.escape(detail, quote=True)}"' if detail else ""
    return f'<span class="status status-{state}"{title}>{html.escape(label)}</span>'


def _nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: object = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def _network_rank_rows(directory: Path) -> list[dict[str, str]]:
    ranking = _optional_csv(directory, "supplier_sensitivity_ranking.csv")
    return sorted(
        ranking,
        key=lambda row: _integer(row.get("supplier_sensitivity_rank"), 999),
    )


def _network_presence_pass(
    manifest: Mapping[str, Any],
    ranking: Sequence[Mapping[str, object]],
    directory: Path,
) -> bool:
    """Require three distinct, ranking-consistent priorities in 29/30 seeds."""

    stability = _optional_csv(directory, "confirmed_top3_stability.csv")
    if not stability:
        # Legacy manifests remain readable as a priority group, but a declared
        # aggregate minimum is not enough to promote three named suppliers.
        return False
    stable_rows = sorted(
        [
            row
            for row in stability
            if _integer(row.get("aggregate_confirmation_rank"), 999) in {1, 2, 3}
        ],
        key=lambda row: _integer(row.get("aggregate_confirmation_rank"), 999),
    )
    ranked_rows = sorted(
        [
            row
            for row in ranking
            if _integer(row.get("supplier_sensitivity_rank"), 999) in {1, 2, 3}
        ],
        key=lambda row: _integer(row.get("supplier_sensitivity_rank"), 999),
    )
    if len(stable_rows) != 3 or len(ranked_rows) != 3:
        return False
    stable_ranks = {
        _integer(row.get("aggregate_confirmation_rank"), 999) for row in stable_rows
    }
    ranked_ranks = {
        _integer(row.get("supplier_sensitivity_rank"), 999) for row in ranked_rows
    }
    stable_ids = [str(row.get("supplier_id") or "").strip() for row in stable_rows]
    ranked_ids = [str(row.get("supplier_id") or "").strip() for row in ranked_rows]
    if (
        stable_ranks != {1, 2, 3}
        or ranked_ranks != {1, 2, 3}
        or any(not supplier_id for supplier_id in stable_ids + ranked_ids)
        or len(set(stable_ids)) != 3
        or len(set(ranked_ids)) != 3
        or stable_ids != ranked_ids
    ):
        return False
    return all(
        _integer(row.get("top3_presence_seed_count"), -1) >= 29
        and _integer(
            row.get("confirmation_seed_count"),
            _integer(manifest.get("confirmation_seed_count")),
        )
        == 30
        for row in stable_rows
    )


def _extension_completion_pass(value: object) -> bool:
    """An extension is releasable only when execution and gate both passed."""

    if not isinstance(value, Mapping):
        return False
    return _completion_pass(value.get("pass")) and _completion_pass(
        value.get("complete")
    )


def _network_rank_separation_pass(manifest: Mapping[str, Any]) -> bool:
    candidates = (
        manifest.get("rank3_rank4_interval_separated"),
        manifest.get("rank3_rank4_ci_separated"),
        manifest.get("rank3_rank4_separation_pass"),
        _nested_mapping(manifest, "top3_validation").get(
            "rank3_rank4_separation_pass"
        ),
        _nested_mapping(manifest, "statistical_validation").get(
            "rank3_rank4_separation_pass"
        ),
    )
    return next((_truthy(value) for value in candidates if value is not None), False)


def _completion_pass(value: object) -> bool:
    if isinstance(value, Mapping):
        for key in ("pass", "passed", "complete", "status", "state", "result"):
            if key in value:
                return _completion_pass(value.get(key))
        return False
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "oui",
        "pass",
        "passed",
        "complete",
        "completed",
    }


def _network_release_gates(
    manifest: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """Require physical, pairing and extension evidence before a stable label."""

    release = _nested_mapping(manifest, "scientific_release_gates")
    extensions = _nested_mapping(manifest, "extensions_required")
    missing: list[str] = []

    baseline = (
        _completion_pass(
            release.get("baseline_both_products_on_due_at_least_95_all_seeds_pass")
        )
        if release
        else _completion_pass(
            manifest.get("baseline_service_gate_pass")
            or manifest.get("baseline_two_products_ge95_all_seeds_pass")
        )
    )
    if not baseline:
        missing.append("service de référence ≥ 95 % pour les deux produits à chaque graine")

    if release:
        metric_rows = _completion_pass(release.get("all_metric_rows_valid_pass"))
        j0_pairing = _completion_pass(release.get("j0_state_hash_pairing_100pct_pass"))
        input_pairing = _completion_pass(
            release.get("input_graph_hash_pairing_100pct_pass")
        )
        all_release = _completion_pass(release.get("all_release_gates_pass"))
        if not metric_rows:
            missing.append("validité de toutes les lignes de métriques")
        pairing = j0_pairing and input_pairing
        if not all_release:
            missing.append("validation conjointe des conditions de publication")
    else:
        pairing = _completion_pass(
            manifest.get("pairing_integrity_gate_pass")
            or manifest.get("paired_inputs_j0_pass")
        )
    if not pairing:
        missing.append("même état initial et mêmes entrées dans les deux scénarios comparés")

    active_flow = (
        _completion_pass(
            release.get(
                "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass"
            )
        )
        if release
        else _completion_pass(
            manifest.get("active_lane_flow_gate_pass")
            or manifest.get("active_flow_ge29_of_30_pass")
        )
    )
    if not active_flow:
        missing.append("flux actif sur au moins 29 graines sur 30 pour chaque voie")

    extension_checks = (
        (
            "multi_lane_supplier_common_cause",
            "chocs communs simultanés sur plusieurs voies d'un fournisseur",
        ),
        ("temporal_robustness", "robustesse à plusieurs fenêtres temporelles"),
        (
            "four_business_cause_confirmation",
            "confirmation des quatre causes métier sur les voies prioritaires",
        ),
        (
            "causal_lot_attribution",
            "preuve causale des lots touchés, au-delà de leur seule généalogie",
        ),
    )
    for key, label in extension_checks:
        if not _extension_completion_pass(extensions.get(key)):
            missing.append(label)
    return not missing, missing


def _network_conclusion_state(
    *, manifest: Mapping[str, Any], ranking: Sequence[Mapping[str, object]], directory: Path
) -> tuple[str, str]:
    seeds = _integer(manifest.get("confirmation_seed_count"))
    release_pass, missing_release_evidence = _network_release_gates(manifest)
    if (
        seeds == 30
        and _network_presence_pass(manifest, ranking, directory)
        and _network_rank_separation_pass(manifest)
        and release_pass
    ):
        return (
            NETWORK_STABILIZED_STATE,
            "30 répétitions simulées comparables, présence d'au moins 29 sur 30, "
            "séparation statistique entre les rangs 3 et 4 et toutes les "
            "conditions physiques et extensions scientifiques validées.",
        )
    if 0 < seeds <= 10:
        return (
            NETWORK_PRESELECTION_STATE,
            "Dix répétitions simulées constituent une présélection, jamais un top 3 final, "
            "même si un ancien manifeste l'affirme.",
        )
    missing_detail = (
        " Éléments manquants : " + "; ".join(missing_release_evidence) + "."
        if missing_release_evidence
        else ""
    )
    return (
        NETWORK_PRIORITY_GROUP_STATE,
        "Priorités du test voie-par-voie à confirmer : les preuves disponibles "
        "ne satisfont pas toutes les conditions statistiques et physiques."
        + missing_detail,
    )


def _campaign_state(
    directory: Path | None,
    *,
    kind: str,
) -> dict[str, Any]:
    if directory is None or not directory.is_dir():
        return {
            "state": "unavailable",
            "detail": "Aucun résultat final n'a été fourni à cette page.",
            "manifest": {},
            "directory": directory,
        }
    manifest = _optional_json(directory, "campaign_manifest.json")
    if not manifest:
        manifest = _optional_json(directory, "manifest.json")
    raw = str(manifest.get("status") or "").strip().lower()
    if raw in {"running", "planned", "prepared", "preparing", "pending"}:
        return {
            "state": "in_progress",
            "detail": "Les calculs ne sont pas terminés; aucune conclusion n'est affichée.",
            "manifest": manifest,
            "directory": directory,
        }
    if kind == "network":
        has_ranking = (directory / "supplier_sensitivity_ranking.csv").is_file()
        if raw != "complete" or str(manifest.get("mode") or "") != "full" or not has_ranking:
            return {
                "state": "not_concluded",
                "detail": "Le test disponible n'est pas la confirmation finale multi-réalisations.",
                "manifest": manifest,
                "directory": directory,
            }
        state, detail = _network_conclusion_state(
            manifest=manifest,
            ranking=_network_rank_rows(directory),
            directory=directory,
        )
        return {
            "state": state,
            "detail": detail,
            "manifest": manifest,
            "directory": directory,
        }
    elif kind == "021081":
        complete_statuses = {"complete", "exploratory_complete", "complete_exploratory"}
        if raw not in complete_statuses or not (directory / "future_autonomous_page_payload.json").is_file():
            state = "not_concluded" if raw in complete_statuses | {"smoke_complete"} else "in_progress"
            return {
                "state": state,
                "detail": "La campagne complète et son bilan métier ne sont pas encore disponibles.",
                "manifest": manifest,
                "directory": directory,
            }
    elif kind == "service":
        if raw != "complete" or not (directory / "worst_cases.csv").is_file():
            return {
                "state": "not_concluded",
                "detail": "La campagne ciblée n'est pas complète.",
                "manifest": manifest,
                "directory": directory,
            }
    elif kind == "action_audit":
        if raw != "complete" or not (directory / "controllable_action_lever_audit.csv").is_file():
            return {
                "state": "not_concluded",
                "detail": "L'audit des leviers n'est pas complet; aucun résultat n'en est repris.",
                "manifest": manifest,
                "directory": directory,
            }
    elif kind == "supplier_source_audit":
        summary = manifest.get("summary") if isinstance(manifest.get("summary"), Mapping) else {}
        required_summary_fields = {
            "location_external_account_count",
            "direct_product_fia_external_supplier_count",
            "upstream_021081_fia_external_supplier_count",
            "all_fia_external_supplier_count",
            "all_fia_external_with_location_count",
        }
        if raw != "complete" or not required_summary_fields.issubset(summary):
            return {
                "state": "not_concluded",
                "detail": "L'audit des sources fournisseur n'est pas complet; ses nombres restent masqués.",
                "manifest": manifest,
                "directory": directory,
            }
    return {
        "state": "complete",
        "detail": "Résultat complet pour le périmètre et les hypothèses affichés.",
        "manifest": manifest,
        "directory": directory,
    }


def _load_frozen_network_state(
    *,
    overlay_dir: Path,
    priority_boundary_audit_dir: Path,
    action_selection_dir: Path | None,
) -> dict[str, Any]:
    """Consume the frozen network only through its public fail-closed API."""

    payload = network_results.load_network_results(
        overlay_dir,
        priority_boundary_audit_dir=priority_boundary_audit_dir,
        action_selection_dir=action_selection_dir,
    )
    if (
        payload.get("input_status") != FROZEN_NETWORK_INPUT_STATUS
        or payload.get("legacy_priority_flags_ignored") is not True
        or payload.get("legacy_extension_release_aliases_ignored") is not True
    ):
        raise ValueError("Le contrat public du réseau gelé n'est pas valide.")

    extension = payload.get("extension")
    controls = (
        extension.get("controls")
        if isinstance(extension, Mapping)
        and isinstance(extension.get("controls"), Mapping)
        else {}
    )
    required_true_controls = (
        "execution_integrity_pass",
        "multi_lane_common_cause_execution_integrity_pass",
        "temporal_execution_integrity_pass",
        "four_cause_execution_integrity_pass",
        "causal_lot_pairing_integrity_pass",
    )
    required_false_controls = (
        "global_priority_temporal_robustness_evaluable",
        "global_four_cause_priority_robustness_evaluable",
        "global_network_priority_robustness_evaluable",
        "network_recovery_metric_used_in_any_gate_or_ranking",
        "promotion_allowed",
    )
    if (
        not all(controls.get(key) is True for key in required_true_controls)
        or not all(controls.get(key) is False for key in required_false_controls)
        or controls.get("network_recovery_metric_status")
        != "excluded_invalid_common_window"
    ):
        raise ValueError("Les limites scientifiques du réseau gelé sont incomplètes.")

    reporting_status = str(payload.get("priority_reporting_status") or "")
    stable_priorities = payload.get("stable_priorities")
    priority_group = payload.get("priority_group_supplier_ids")
    if not isinstance(stable_priorities, list) or not isinstance(priority_group, list):
        raise ValueError("La conclusion de priorité du réseau gelé est absente.")
    if reporting_status == NETWORK_ENVELOPE_TRIO_STATE:
        if len(stable_priorities) != 3 or len(
            {str(row.get("supplier_id") or "") for row in stable_priorities}
        ) != 3:
            raise ValueError("Le trio sous enveloppe n'est pas exactement défini.")
        detail = (
            "Trois priorités simulées sont publiables uniquement sous l'enveloppe "
            "du pire des deux tests voie-par-voie; leur ordre interne n'est pas conclu."
        )
    elif reporting_status == NETWORK_FROZEN_GROUP_STATE:
        if stable_priorities or len({str(value) for value in priority_group if value}) < 3:
            raise ValueError("Le groupe de priorité non ordonné n'est pas défini.")
        detail = (
            "La frontière entre fournisseurs n'est pas assez nette; seul un groupe "
            "non ordonné est publiable."
        )
    else:
        raise ValueError("Conclusion réseau gelée inconnue.")

    boundary = payload.get("boundary")
    boundary_audit = (
        boundary.get("audit")
        if isinstance(boundary, Mapping)
        and isinstance(boundary.get("audit"), Mapping)
        else {}
    )
    metric_audits = boundary_audit.get("metric_priority_audits")
    family_audits = boundary_audit.get(
        "failure_mode_specific_metric_priority_audits"
    )
    effects = boundary.get("effects") if isinstance(boundary, Mapping) else None
    rankings = boundary.get("rankings") if isinstance(boundary, Mapping) else None
    if (
        not isinstance(metric_audits, list)
        or {str(row.get("metric_key") or "") for row in metric_audits}
        != set(FROZEN_NETWORK_METRICS)
        or not isinstance(family_audits, Mapping)
        or set(family_audits) != set(FROZEN_NETWORK_HYPOTHESES)
        or not isinstance(effects, list)
        or not isinstance(rankings, list)
    ):
        raise ValueError("Les quatre lectures ou les deux hypothèses réseau sont incomplètes.")

    actions = payload.get("actions")
    if (
        not isinstance(actions, Mapping)
        or actions.get("released") is not False
        or list(actions.get("selected") or [])
        or actions.get("forced_not_promoted") is not True
    ):
        raise ValueError("Une action réseau a été promue alors que le contrat l'interdit.")

    return {
        "state": reporting_status,
        "detail": detail,
        "manifest": payload.get("manifest")
        if isinstance(payload.get("manifest"), Mapping)
        else {},
        "directory": overlay_dir,
        "source_contract": "frozen_overlay_boundary_api",
        "input_status": FROZEN_NETWORK_INPUT_STATUS,
        "priority_reporting_status": reporting_status,
        "stable_priorities": stable_priorities,
        "priority_group_supplier_ids": priority_group,
        "global_network_priority_robustness_evaluable": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "actions_promoted": False,
        "payload": payload,
        "ranking": payload.get("ranking")
        if isinstance(payload.get("ranking"), list)
        else [],
        "failure_modes": payload.get("modes")
        if isinstance(payload.get("modes"), list)
        else [],
    }


def load_industrial_supply_bilan_inputs(
    *,
    observed_dir: Path,
    scope_dir: Path,
    service_landscape_dir: Path,
    component_021081_dir: Path | None = None,
    network_screen_dir: Path | None = None,
    network_priority_boundary_audit_dir: Path | None = None,
    network_action_selection_dir: Path | None = None,
    action_audit_dir: Path | None = None,
    supplier_source_audit_dir: Path | None = None,
) -> dict[str, Any]:
    """Load only the compact inputs needed by the autonomous page."""

    required = {
        observed_dir / "manifest.json",
        observed_dir / "observed_ca_product_summary_2025.csv",
        observed_dir / "observed_ca_monthly_2025.csv",
        observed_dir / "observed_stock_value_summary_2025.csv",
        observed_dir / "projected_finished_goods_shortage_summary.csv",
        observed_dir / "supplier_risk_prediction_readiness.csv",
        scope_dir / "manifest.json",
        scope_dir / "supplier_lane_scope.csv",
        scope_dir / "supplier_item_source_coverage.csv",
    }
    missing = sorted(path for path in required if not path.is_file())
    if missing:
        raise FileNotFoundError("Missing dashboard input(s): " + ", ".join(map(str, missing)))

    observed_manifest = _read_json(observed_dir / "manifest.json")
    scope_manifest = _read_json(scope_dir / "manifest.json")
    service_state = _campaign_state(service_landscape_dir, kind="service")
    component_state = _campaign_state(component_021081_dir, kind="021081")
    if network_priority_boundary_audit_dir is not None:
        if network_screen_dir is None:
            raise ValueError("La surcouche réseau est requise avec son audit de frontière.")
        network_state = _load_frozen_network_state(
            overlay_dir=network_screen_dir,
            priority_boundary_audit_dir=network_priority_boundary_audit_dir,
            action_selection_dir=network_action_selection_dir,
        )
    else:
        if network_action_selection_dir is not None:
            raise ValueError(
                "Le catalogue d'actions réseau exige la surcouche et son audit de frontière."
            )
        network_state = _campaign_state(network_screen_dir, kind="network")
    action_audit_state = _campaign_state(action_audit_dir, kind="action_audit")
    supplier_source_audit_state = _campaign_state(
        supplier_source_audit_dir, kind="supplier_source_audit"
    )

    return {
        "observed": {
            "manifest": observed_manifest,
            "ca": _read_csv(observed_dir / "observed_ca_product_summary_2025.csv"),
            "ca_monthly": _read_csv(observed_dir / "observed_ca_monthly_2025.csv"),
            "stock": _read_csv(observed_dir / "observed_stock_value_summary_2025.csv"),
            "shortages": _read_csv(observed_dir / "projected_finished_goods_shortage_summary.csv"),
            "readiness": _read_csv(observed_dir / "supplier_risk_prediction_readiness.csv"),
            "component_context": _optional_csv(observed_dir, "component_021081_physical_context.csv"),
        },
        "scope": {
            "manifest": scope_manifest,
            "artifact_name": scope_dir.name,
            "lanes": _read_csv(scope_dir / "supplier_lane_scope.csv"),
            "sources": _read_csv(scope_dir / "supplier_item_source_coverage.csv"),
            "findings": _optional_csv(scope_dir, "data_quality_findings.csv"),
        },
        "service": {
            **service_state,
            "worst_cases": _optional_csv(service_landscape_dir, "worst_cases.csv"),
            "summary": _optional_csv(service_landscape_dir, "scenario_summary.csv"),
        },
        "component_021081": {
            **component_state,
            "payload": _optional_json(component_021081_dir, "future_autonomous_page_payload.json"),
            "observed_order_audit": _optional_json(component_021081_dir, "observed_order_book_audit.json"),
        },
        "network": (
            network_state
            if network_state.get("source_contract") == "frozen_overlay_boundary_api"
            else {
                **network_state,
                "ranking": _optional_csv(
                    network_screen_dir, "supplier_sensitivity_ranking.csv"
                ),
                "failure_modes": _optional_csv(
                    network_screen_dir, "failure_mode_sensitivity_summary.csv"
                ),
            }
        ),
        "action_audit": {
            **action_audit_state,
            "rows": _optional_csv(action_audit_dir, "controllable_action_lever_audit.csv"),
        },
        "supplier_source_audit": supplier_source_audit_state,
    }


def _monthly_service_svg(rows: Sequence[Mapping[str, object]]) -> str:
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("product_code") or "")].append(
            (str(row.get("month") or ""), _number(row.get("delivered_share_of_raw_potential")))
        )
    colors = {"268091": "#ef5a45", "268967": "#2b7de9"}
    width, height = 760, 260
    left, right, top, bottom = 58, 20, 24, 42
    plot_w, plot_h = width - left - right, height - top - bottom
    y_min, y_max = 0.75, 1.0
    elements: list[str] = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Part mensuelle de valeur livrée dans la valeur potentielle source">',
        "<title>Part mensuelle de valeur livrée, par produit</title>",
    ]
    for value in (0.75, 0.80, 0.90, 1.0):
        y = top + (y_max - value) / (y_max - y_min) * plot_h
        elements.append(f'<line x1="{left}" x2="{width-right}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        elements.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="axis">{int(value*100)} %</text>')
    month_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    for index, label in enumerate(month_labels):
        x = left + index * plot_w / 11
        elements.append(f'<text x="{x:.1f}" y="{height-15}" text-anchor="middle" class="axis">{label}</text>')
    for product, values in sorted(grouped.items()):
        values.sort(key=lambda item: item[0])
        points = []
        for index, (_, value) in enumerate(values[:12]):
            x = left + index * plot_w / max(1, len(values[:12]) - 1)
            clipped = min(y_max, max(y_min, value))
            y = top + (y_max - clipped) / (y_max - y_min) * plot_h
            points.append(f"{x:.1f},{y:.1f}")
        color = colors.get(product, "#5f6f86")
        elements.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
        for point in points:
            x, y = point.split(",")
            elements.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>')
    elements.append('<g transform="translate(520 15)"><circle cx="0" cy="0" r="5" fill="#ef5a45"/><text x="11" y="4" class="legend">268091</text><circle cx="86" cy="0" r="5" fill="#2b7de9"/><text x="97" y="4" class="legend">268967</text></g>')
    elements.append("</svg>")
    return "".join(elements)


def _stock_range_svg(rows: Sequence[Mapping[str, object]]) -> str:
    selected = list(rows)[:6]
    width = 760
    row_h = 43
    height = 58 + row_h * len(selected)
    left, right = 205, 28
    maximum = max((_number(row.get("maximum_stock_value_source")) for row in selected), default=1.0) or 1.0
    labels = {
        "component_stock_cos": "Composants – Cos",
        "component_stock_pharma": "Composants – Pharma",
        "finished_goods_stock_268091": "Produit fini 268091",
        "finished_goods_stock_268967": "Produit fini 268967",
    }
    elements = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Étendue des valeurs comptables de stock 2025">',
        "<title>Valeurs comptables de stock : minimum, moyenne et maximum observés</title>",
        f'<line x1="{left}" x2="{width-right}" y1="25" y2="25" class="axis-line"/>',
        f'<text x="{left}" y="17" class="axis">0</text>',
        f'<text x="{width-right}" y="17" text-anchor="end" class="axis">{html.escape(_compact(maximum))}</text>',
    ]
    scale = (width - left - right) / maximum
    for index, row in enumerate(selected):
        y = 54 + index * row_h
        minimum = _number(row.get("minimum_stock_value_source"))
        mean = _number(row.get("mean_stock_value_source"))
        maximum_row = _number(row.get("maximum_stock_value_source"))
        last = _number(row.get("last_stock_value_source"))
        label = labels.get(str(row.get("series_id") or ""), str(row.get("series_id") or "Stock"))
        elements.extend(
            [
                f'<text x="{left-12}" y="{y+4}" text-anchor="end" class="label">{html.escape(label)}</text>',
                f'<line x1="{left+minimum*scale:.1f}" x2="{left+maximum_row*scale:.1f}" y1="{y}" y2="{y}" stroke="#a9bbcf" stroke-width="9" stroke-linecap="round"/>',
                f'<circle cx="{left+mean*scale:.1f}" cy="{y}" r="6" fill="#173f6d"><title>Moyenne : {_fr(mean,0)}</title></circle>',
                f'<path d="M {left+last*scale:.1f} {y-8} l 7 8 l -7 8 l -7 -8 z" fill="#f39b3d"><title>Dernier instantané : {_fr(last,0)}</title></path>',
            ]
        )
    elements.append(f'<g transform="translate({left} {height-10})"><circle cx="0" cy="0" r="5" fill="#173f6d"/><text x="10" y="4" class="legend">moyenne</text><path d="M 98 -7 l 7 7 l -7 7 l -7 -7 z" fill="#f39b3d"/><text x="110" y="4" class="legend">dernier instantané</text></g>')
    elements.append("</svg>")
    return "".join(elements)


def _scope_svg(counts: Mapping[str, object]) -> str:
    parts = [
        ("simulated_and_orderbook", "Simulation + carnet", "#2478d4"),
        ("simulated_only", "Simulation seule", "#41a37a"),
        ("orderbook_only", "Carnet seul", "#f2a541"),
        ("unexercised", "Non exercée", "#c9d2de"),
    ]
    total = sum(_integer(counts.get(key)) for key, _, _ in parts) or 1
    width, height = 760, 150
    x, bar_y, bar_w, bar_h = 25.0, 35, 710.0, 42
    elements = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Couverture des voies fournisseurs du réseau">',
        "<title>33 voies structurelles réparties selon les preuves disponibles</title>",
    ]
    cursor = x
    for key, label, color in parts:
        count = _integer(counts.get(key))
        segment = bar_w * count / total
        elements.append(f'<rect x="{cursor:.1f}" y="{bar_y}" width="{segment:.1f}" height="{bar_h}" fill="{color}"/>')
        if segment >= 42:
            elements.append(f'<text x="{cursor+segment/2:.1f}" y="{bar_y+27}" text-anchor="middle" class="bar-value">{count}</text>')
        cursor += segment
    legend_x = 25
    for index, (key, label, color) in enumerate(parts):
        col = index % 2
        row = index // 2
        lx = legend_x + col * 350
        ly = 105 + row * 25
        count = _integer(counts.get(key))
        elements.append(f'<rect x="{lx}" y="{ly-11}" width="13" height="13" rx="3" fill="{color}"/><text x="{lx+21}" y="{ly}" class="legend">{html.escape(label)} : {count}</text>')
    elements.append("</svg>")
    return "".join(elements)


def _stress_svg(rows: Sequence[Mapping[str, object]]) -> str:
    selected = list(rows)[:4]
    width, height = 760, 75 + max(1, len(selected)) * 56
    left, right = 225, 35
    plot_w = width - left - right
    elements = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Part de demande servie à la date attendue dans le modèle">',
        "<title>Part de la demande servie à la date attendue dans le modèle</title>",
    ]
    for tick in (0.0, 0.5, 0.8, 1.0):
        x = left + tick * plot_w
        elements.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="25" y2="{height-30}" class="grid"/><text x="{x:.1f}" y="{height-11}" text-anchor="middle" class="axis">{int(tick*100)} %</text>')
    for index, row in enumerate(selected):
        y = 42 + index * 56
        mean = max(0.0, min(1.0, _number(row.get("product_on_due_date_proxy_mean"))))
        seed_count = _integer(row.get("n_seeds"))
        publish_p05 = seed_count >= 100 and str(
            row.get("product_on_due_date_proxy_p05") or ""
        ).strip()
        low = max(
            0.0,
            min(1.0, _number(row.get("product_on_due_date_proxy_p05"), mean)),
        )
        chain = str(row.get("chain_id") or "").split("_")
        component = chain[0] if chain else "voie"
        product = str(row.get("target_product_id") or (chain[-1] if chain else ""))
        label = f"{component} → {product}"
        elements.extend(
            [
                f'<text x="{left-12}" y="{y+4}" text-anchor="end" class="label">{html.escape(label)}</text>',
                f'<rect x="{left}" y="{y-13}" width="{mean*plot_w:.1f}" height="26" rx="7" fill="#ef6a57"/>',
                f'<text x="{left+mean*plot_w+9:.1f}" y="{y+5}" class="bar-text">{_percent(mean)}</text>',
            ]
        )
        if publish_p05:
            elements.append(
                f'<line x1="{left+low*plot_w:.1f}" x2="{left+low*plot_w:.1f}" '
                f'y1="{y-17}" y2="{y+17}" stroke="#7e2430" stroke-width="3">'
                f'<title>5e percentile sur {seed_count} répétitions simulées : {_percent(low)}</title></line>'
            )
    elements.append("</svg>")
    return "".join(elements)


def _orderbook_svg(audit: Mapping[str, object]) -> str:
    rows = audit.get("supplier_rows") if isinstance(audit.get("supplier_rows"), list) else []
    selected = [row for row in rows if isinstance(row, Mapping)]
    width, height = 760, 54 + max(1, len(selected)) * 50
    left, right = 185, 90
    maximum = max((_number(row.get("quantity_kg")) for row in selected), default=1.0) or 1.0
    plot_w = width - left - right
    elements = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Quantité planifiée ouverte de 021081 par fournisseur">',
        "<title>Quantité du carnet ouvert 021081 au 1er janvier 2025</title>",
    ]
    for index, row in enumerate(selected):
        y = 30 + index * 50
        quantity = _number(row.get("quantity_kg"))
        supplier = _supplier_label(row.get("supplier_id"))
        count = _integer(row.get("order_count"))
        bar_width = quantity / maximum * plot_w
        if bar_width > plot_w * 0.66:
            value_x = left + bar_width - 9
            value_anchor = "end"
            value_class = "bar-value"
        else:
            value_x = left + bar_width + 8
            value_anchor = "start"
            value_class = "bar-text"
        elements.extend(
            [
                f'<text x="{left-12}" y="{y+4}" text-anchor="end" class="label">{html.escape(supplier)}</text>',
                f'<rect x="{left}" y="{y-12}" width="{bar_width:.1f}" height="25" rx="6" fill="#2877c7"/>',
                f'<text x="{value_x:.1f}" y="{y+5}" text-anchor="{value_anchor}" class="{value_class}">{_fr(quantity,0)} kg · {count} lignes</text>',
            ]
        )
    elements.append("</svg>")
    return "".join(elements)


def _regime_svg(rows: Sequence[Mapping[str, object]]) -> str:
    selected = list(rows)
    width, height = 980, 76 + max(1, len(selected)) * 47
    left, right = 455, 70
    maximum = max((_integer(row.get("tested_stress_configurations")) for row in selected), default=1) or 1
    plot_w = width - left - right
    elements = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Configurations de stress 021081 atteignant le produit selon le stock initial">',
        "<title>Nombre de configurations testées qui atteignent le produit aval</title>",
    ]
    for index, row in enumerate(selected):
        y = 35 + index * 47
        tested = _integer(row.get("tested_stress_configurations"))
        impacted = _integer(row.get("configurations_with_simulated_downstream_product_effect"))
        regime = str(row.get("state_regime") or "")
        cover = row.get("target_cover_days")
        labels = {
            "observed_2025": "Référence simulée · état du snapshot 2025",
            "observed_all_layers": "Référence simulée · état du snapshot 2025",
            "component_only_90d": "Hypothèse · stock 021081 seul réduit à 90 j",
            "component_only_30d": "Hypothèse · stock 021081 seul réduit à 30 j",
            "intermediate_stock_only_90d": "Hypothèse · stock 773474 seul réduit à 90 j",
            "intermediate_stock_only_30d": "Hypothèse · stock 773474 seul réduit à 30 j",
            "intermediate_production_only_90d": "Hypothèse · production 773474 seule limitée à 90 j",
            "intermediate_production_only_30d": "Hypothèse · production 773474 seule limitée à 30 j",
            "joint_90d": "Hypothèse · 021081 + stock et production 773474 à 90 j",
            "joint_30d": "Hypothèse · 021081 + stock et production 773474 à 30 j",
        }
        label = labels.get(
            regime,
            f"Hypothèse · {regime.replace('_', ' ') or 'état à valider'} · {_fr(cover,0)} j",
        )
        elements.extend(
            [
                f'<text x="{left-12}" y="{y+4}" text-anchor="end" class="label">{html.escape(label)}</text>',
                f'<rect x="{left}" y="{y-11}" width="{tested/maximum*plot_w:.1f}" height="23" rx="6" fill="#d7e1eb"/>',
                f'<rect x="{left}" y="{y-11}" width="{impacted/maximum*plot_w:.1f}" height="23" rx="6" fill="#e85f4b"/>',
                f'<text x="{left+tested/maximum*plot_w+8:.1f}" y="{y+5}" class="bar-text">{impacted} sur {tested}</text>',
            ]
        )
    elements.append(f'<g transform="translate({left} {height-17})"><rect x="0" y="-11" width="14" height="14" rx="3" fill="#e85f4b"/><text x="21" y="0" class="legend">effet aval simulé</text><rect x="174" y="-11" width="14" height="14" rx="3" fill="#d7e1eb"/><text x="195" y="0" class="legend">configurations testées</text></g>')
    elements.append("</svg>")
    return "".join(elements)


def _relative_href(output_html: Path, target: Path | None) -> str | None:
    if target is None:
        return None
    return Path(os.path.relpath(target.resolve(), output_html.parent.resolve())).as_posix()


def _link_card(label: str, description: str, href: str | None) -> str:
    if not href:
        return f'<div class="link-card disabled"><span>{html.escape(label)}</span><small>{html.escape(description)} · lien non fourni</small></div>'
    return f'<a class="link-card" href="{html.escape(href, quote=True)}"><span>{html.escape(label)} <b aria-hidden="true">→</b></span><small>{html.escape(description)}</small></a>'


def _view_observed(data: Mapping[str, Any]) -> str:
    observed = data["observed"]
    ca = observed["ca"]
    stock = observed["stock"]
    shortages = sorted(
        observed["shortages"],
        key=lambda row: (str(row.get("product_code") or ""), _integer(row.get("snapshot_year"))),
    )
    readiness = observed["readiness"]
    delivered = sum(_number(row.get("ca_delivered_source_value")) for row in ca)
    lost = sum(_number(row.get("ca_lost_positive_only_source_value")) for row in ca)
    potential = delivered + lost
    share = delivered / potential if potential else 0.0
    observed_valid = _truthy(observed["manifest"].get("all_validation_checks_pass"))
    product_cards = []
    for row in ca:
        product = str(row.get("product_code") or "")
        product_cards.append(
            f'''<article class="metric-card">
              <span class="eyebrow evidence-observed">OBSERVÉ</span>
              <h3>Produit {html.escape(product)}</h3>
              <strong>{_compact(row.get("ca_lost_positive_only_source_value"))}</strong>
              <span>valeur positive signalée comme non réalisée</span>
              <p>{_integer(row.get("days_with_lost_signal"))} jours comportent une valeur positive signalée comme non réalisée dans le fichier source. La part financière livrée vaut {_percent(row.get("delivered_share_of_raw_potential"))}; ce n'est pas un OTIF ni une attribution fournisseur.</p>
            </article>'''
        )
    shortage_cards = []
    for row in shortages:
        product = str(row.get("product_code") or "")
        year = _integer(row.get("snapshot_year"))
        snapshot_count = _integer(row.get("snapshot_count"))
        nonzero_count = _integer(row.get("nonzero_snapshot_count"))
        maximum = _number(row.get("maximum_projected_shortage_weeks"))
        if maximum <= 0:
            reading = (
                f"aucune alerte non nulle dans les {snapshot_count} photos disponibles"
                if snapshot_count
                else "aucune semaine de rupture projetée dans les photos disponibles"
            )
        else:
            first_week = str(row.get("first_nonzero_year_week") or "")
            last_week = str(row.get("last_nonzero_year_week") or "")
            period = f", de {first_week} à {last_week}" if first_week and last_week else ""
            reading = (
                f"{nonzero_count} photos sur {snapshot_count} portent une alerte, jusqu'à "
                f"{_fr(maximum,0)} semaines projetées dans une même photo{period}"
            )
        shortage_cards.append(
            f'<li><b>{html.escape(product)} · {year}</b> : {html.escape(reading)}.</li>'
        )
    missing_fields = sum(
        "MISSING" in str(row.get("availability_in_current_2025_bundle") or "").upper()
        or "NOT_LINKED" in str(row.get("availability_in_current_2025_bundle") or "").upper()
        for row in readiness
    )
    return f'''
    <section id="view-observed" class="view active" aria-labelledby="tab-observed">
      <header class="view-head">
        <div><span class="view-number">1</span><p class="kicker">Point de départ</p><h2>Ce que disent réellement les données 2025</h2></div>
        {_status_badge("complete" if observed_valid else "not_concluded", "Contrôles du bilan observé")}
      </header>
      <div class="hero-grid">
        <article class="hero-card blue"><span class="eyebrow evidence-observed">OBSERVÉ</span><strong>{_compact(delivered)}</strong><span>valeur livrée dans les fichiers source</span></article>
        <article class="hero-card coral"><span class="eyebrow evidence-observed">OBSERVÉ</span><strong>{_compact(lost)}</strong><span>valeur positive signalée comme non réalisée</span></article>
        <article class="hero-card navy"><span class="eyebrow evidence-observed">OBSERVÉ</span><strong>{_percent(share)}</strong><span>part financière livrée, tous produits confondus</span></article>
      </div>
      <p class="plain-summary"><b>Lecture métier.</b> Les fichiers 2025 montrent une valeur livrée importante et des valeurs positives signalées comme non réalisées sur les deux produits. La source ne fournit pas de devise : aucune conversion en euros n'est faite. Ces montants signalent un enjeu financier potentiel; ils ne sont attribués ni à un fournisseur, ni à une cause, ni à un lot, et ne sont pas comparables aux indices de coût du modèle.</p>

      <div class="two-col">
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow evidence-observed">OBSERVÉ</span><h3>Évolution mensuelle de la part financière livrée</h3></div></div>
          {_monthly_service_svg(observed["ca_monthly"])}
          <p class="plain-summary"><b>Ce que l'on voit.</b> La performance financière varie selon les mois et diffère entre 268091 et 268967. Elle sert à repérer des périodes à expliquer; sans commandes, dates promises et réceptions reliées, elle ne mesure pas la ponctualité fournisseur.</p>
        </article>
        <div class="card-stack">{''.join(product_cards)}</div>
      </div>

      <article class="panel">
        <div class="panel-title"><div><span class="eyebrow evidence-observed">OBSERVÉ</span><h3>Valeur comptable des stocks immobilisés</h3></div><span class="mini-note">52 instantanés par série</span></div>
        {_stock_range_svg(stock)}
        <p class="plain-summary"><b>Ce que cela signifie.</b> Le graphe compare des valeurs comptables, pas des quantités physiques. Une hausse peut venir du volume, du prix ou du mix. Il faut les quantités, sites, statuts et lots pour convertir ces courbes en couverture de risque opérationnelle.</p>
      </article>

      <div class="two-col lower">
        <article class="panel compact-panel">
          <span class="eyebrow evidence-projected">PROJETÉ</span><h3>Alertes du planning disponibles</h3>
          <ul class="reading-list">{''.join(shortage_cards)}</ul>
          <p class="plain-summary"><b>Usage.</b> Chaque ligne décrit une photo du planning, pas une rupture réalisée. Les photos successives peuvent montrer plusieurs fois le même besoin futur : elles ne sont donc pas sommables. Elles ne sont pas non plus attribuées à un fournisseur.</p>
        </article>
        <article class="panel compact-panel warning-panel">
          <span class="eyebrow evidence-gap">DONNÉES À RELIER</span><h3>Prévision du risque fournisseur : pas encore entraînable</h3>
          <strong class="big-number">{missing_fields} champs minimum</strong>
          <p>Le bundle CA/stock/pertes ne relie pas encore l'identité fournisseur, la ligne de commande, les dates demandée/promise/réelle, la quantité reçue, la qualité, les causes et les actions.</p>
          <p class="plain-summary"><b>Conséquence.</b> Nous pouvons aujourd'hui simuler « que se passerait-il si… ». Nous ne pouvons pas encore annoncer « ce fournisseur a telle chance d'être en retard » à partir de l'historique 2025.</p>
        </article>
      </div>
    </section>'''


def _network_conclusion(data: Mapping[str, Any]) -> str:
    network = data["network"]
    badge = _status_badge(network["state"], network["detail"])
    ranking_available = bool(network["ranking"])
    if network["state"] in {"in_progress", "not_concluded", "unavailable"} or not ranking_available:
        return f'''<article class="panel pending-panel">
          <div class="panel-title"><div><span class="eyebrow evidence-simulated">SIMULÉ</span><h3>Analyse de sensibilité de tout le réseau</h3></div>{badge}</div>
          <p>{html.escape(network["detail"])}</p>
          <p class="plain-summary"><b>Lecture correcte.</b> Tant que les répétitions finales ne stabilisent pas les mêmes fournisseurs, cette page ne publie pas de « top 3 ». Un test technique ou une seule répétition simulée ne suffit pas.</p>
        </article>'''
    stable = network["state"] == NETWORK_STABILIZED_STATE
    displayed_count = 3 if stable else 5
    ranking = sorted(
        network["ranking"], key=lambda row: _integer(row.get("supplier_sensitivity_rank"), 999)
    )[:displayed_count]
    rows = []
    for row in ranking:
        rows.append(
            f'''<tr><td><b>{html.escape(_supplier_label(row.get("supplier_id")))}</b></td>
            <td>{html.escape(str(row.get("worst_item_id") or "").replace("item:", ""))} → {html.escape(str(row.get("worst_target_product_id") or ""))}</td>
            <td>{html.escape(_mechanism_label(row.get("worst_failure_mode")))}</td>
            <td><b>−{_points(row.get("worst_service_delta"))}</b></td></tr>'''
        )
    modes = sorted(
        network["failure_modes"], key=lambda row: _integer(row.get("failure_mode_sensitivity_rank"), 999)
    )[:3]
    mode_text = ", ".join(
        f"{_mechanism_label(row.get('failure_mode'))} (jusqu'à −{_points(row.get('worst_service_delta'))})"
        for row in modes
    )
    manifest = network["manifest"]
    seeds = _integer(manifest.get("confirmation_seed_count"))
    mode_evidence_stage = str(manifest.get("failure_mode_summary_evidence_stage") or "")
    if mode_evidence_stage == "screening_1_realisation":
        mode_reading = (
            "Premier passage exploratoire : 18 voies × 4 modes × 2 intensités, avec une seule "
            "réalisation par cas. Ce n'est ni un classement confirmé des causes, ni une mesure de "
            "leur fréquence historique."
        )
    else:
        mode_reading = (
            "Lecture exploratoire non confirmée : ces écarts ne classent pas la fréquence réelle "
            "des causes."
        )
    if stable:
        title = "Trois priorités simulées stabilisées"
        reading = (
            "Le manifeste porte 30 répétitions simulées comparables; chaque priorité apparaît "
            "au moins 29 fois sur 30, l'incertitude sépare les rangs 3 et 4, "
            "la référence physique et l'appariement sont valides, et les extensions "
            "multi-voies, temporelles et causales sur les lots sont terminées. "
            "Ce sont des priorités sous les stress testés : elles ne prédisent pas la "
            "survenue d'une panne et ne constituent pas une note fournisseur finale."
        )
    else:
        title = (
            "Groupe prioritaire à approfondir"
            if network["state"] == NETWORK_PRESELECTION_STATE
            else "Priorités du test voie-par-voie à confirmer"
        )
        reading = (
            f"Le tableau présente jusqu'à cinq dossiers issus de {seeds or 'quelques'} "
            "répétitions simulées. Dix répétitions ne forment qu'une présélection : un ancien "
            "artefact marqué « top 3 confirmé » reste compatible en lecture, mais n'est "
            "jamais repris comme conclusion finale."
        )
    return f'''<article class="panel">
      <div class="panel-title"><div><span class="eyebrow evidence-signal">SIGNAL DE PRIORITÉ</span><h3>{html.escape(title)}</h3></div>{badge}</div>
      <div class="table-wrap"><table><thead><tr><th>Fournisseur</th><th>Voie aval</th><th>Stress le plus pénalisant testé</th><th>Écart simulé du volume produit servi à la date attendue (points)</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
      <p class="plain-summary"><b>Lecture correcte.</b> {html.escape(reading)}</p>
      <p class="minor">La mesure porte sur le volume de produit servi à la date attendue dans l'horizon simulé. Ce n'est pas l'OTIF fournisseur observé.</p>
      <p class="minor"><b>Modes les plus pénalisants au premier passage :</b> {html.escape(mode_text) if mode_text else 'non disponible'}. {html.escape(mode_reading)}</p>
    </article>'''


def _has_frozen_network(data: Mapping[str, Any]) -> bool:
    network = data.get("network")
    return bool(
        isinstance(network, Mapping)
        and network.get("source_contract") == "frozen_overlay_boundary_api"
    )


def _frozen_metric_label(metric_key: str) -> tuple[str, str]:
    labels = {
        "horizon_on_due_service_delta": (
            "Service sur tout l'horizon",
            "Écart du volume servi à la date attendue sur J0–J719, en points.",
        ),
        "worst_rolling_28d_on_due_delta": (
            "Pire période glissante de 28 jours",
            "Écart du niveau de service le plus faible dans une fenêtre de 28 jours, en points.",
        ),
        "incremental_backlog_days_per_requested_unit": (
            "Retard cumulé rapporté à la demande",
            "Jours-unités de retard supplémentaires par unité demandée (UN·j/UN).",
        ),
        "released_production_shortfall_ratio": (
            "Production libérée manquante",
            "Part de production libérée manquante par rapport au fonctionnement normal.",
        ),
    }
    return labels[metric_key]


def _frozen_metric_value(metric_key: str, value: object) -> str:
    number = _number(value, math.nan)
    if not math.isfinite(number):
        return "non disponible"
    if metric_key in {
        "horizon_on_due_service_delta",
        "worst_rolling_28d_on_due_delta",
    }:
        sign = "−" if number < -1e-12 else "+" if number > 1e-12 else ""
        return f"{sign}{_fr(abs(number) * 100.0, 2)} points"
    if metric_key == "incremental_backlog_days_per_requested_unit":
        sign = "+" if number > 1e-12 else "−" if number < -1e-12 else ""
        return f"{sign}{_fr(abs(number), 2)} UN·j/UN"
    if metric_key == "released_production_shortfall_ratio":
        sign = "+" if number > 1e-12 else "−" if number < -1e-12 else ""
        return f"{sign}{_fr(abs(number) * 100.0, 2)} %"
    return _fr(number, 3)


def _frozen_metric_cards(network: Mapping[str, Any]) -> str:
    payload = network["payload"]
    boundary = payload["boundary"]
    audit_rows = {
        str(row.get("metric_key") or ""): row
        for row in boundary["audit"]["metric_priority_audits"]
    }
    scope = network_results.boundary_contract.SUPPLIER_ENVELOPE_SCOPE
    ranking_rows = list(boundary["rankings"])
    cards: list[str] = []
    for metric_key in FROZEN_NETWORK_METRICS:
        title, definition = _frozen_metric_label(metric_key)
        audit = audit_rows[metric_key]
        released = _truthy(audit.get("metric_priority_set_release_pass"))
        rows = [
            row
            for row in ranking_rows
            if str(row.get("aggregation_scope") or "") == scope
            and str(row.get("metric_key") or "") == metric_key
        ]
        values = sorted(
            _number(row.get("metric_value"), math.nan)
            for row in rows
            if math.isfinite(_number(row.get("metric_value"), math.nan))
        )
        value_range = "non disponible"
        if values:
            value_range = _frozen_metric_value(metric_key, values[0])
            if not math.isclose(values[0], values[-1], abs_tol=1e-12):
                value_range += " à " + _frozen_metric_value(metric_key, values[-1])
        conclusion = (
            "trio distinct du fournisseur suivant pour cette lecture"
            if released
            else "groupe non tranché pour cette lecture"
        )
        cards.append(
            f'''<article class="frozen-metric"><h3>{html.escape(title)}</h3>
            <strong>{html.escape(value_range)}</strong><p>{html.escape(definition)}</p>
            <small>{html.escape(conclusion)}.</small></article>'''
        )
    return "".join(cards)


def _frozen_hypothesis_cards(network: Mapping[str, Any]) -> str:
    payload = network["payload"]
    families = payload["boundary"]["audit"][
        "failure_mode_specific_metric_priority_audits"
    ]
    definitions = {
        "transport_delay": (
            "Décalage de date",
            "Un retard de 120 jours est imposé; la quantité utile n'est pas réduite.",
        ),
        "supply_availability": (
            "Perte de quantité utile",
            "La quantité utilisable est limitée à 50 %; la date n'est pas le seul mécanisme.",
        ),
    }
    cards: list[str] = []
    for failure_mode in FROZEN_NETWORK_HYPOTHESES:
        title, definition = definitions[failure_mode]
        service = next(
            row
            for row in families[failure_mode]["metric_priority_audits"]
            if str(row.get("metric_key") or "")
            == "horizon_on_due_service_delta"
        )
        released = _truthy(service.get("metric_priority_set_release_pass"))
        supplier_ids = sorted(
            str(value)
            for value in service.get("released_priority_supplier_ids", [])
            if str(value)
        )
        conclusion = (
            "Trio distinct pour le service : " + ", ".join(supplier_ids)
            if released
            else "Groupe non tranché pour le service."
        )
        cards.append(
            f'''<article class="frozen-hypothesis"><span class="eyebrow evidence-hypothesis">HYPOTHÈSE</span>
            <h3>{html.escape(title)}</h3><p>{html.escape(definition)}</p>
            <small>{html.escape(conclusion)}</small></article>'''
        )
    return "".join(cards)


def _frozen_effect_rows(network: Mapping[str, Any]) -> str:
    payload = network["payload"]
    target_ids = {
        str(row.get("supplier_id") or "")
        for row in network["stable_priorities"]
        if str(row.get("supplier_id") or "")
    } or {str(value) for value in network["priority_group_supplier_ids"] if value}
    rows = sorted(
        (
            row
            for row in payload["boundary"]["effects"]
            if str(row.get("aggregation_level") or "")
            == "supplier_any_confirmed_scenario"
            and str(row.get("supplier_id") or "") in target_ids
        ),
        key=lambda row: str(row.get("supplier_id") or ""),
    )
    return "".join(
        f'''<tr><td><b>{html.escape(str(row.get("supplier_id") or ""))}</b></td>
        <td>{_integer(row.get("client_effect_seed_count"))}/30</td>
        <td>{_integer(row.get("production_only_effect_seed_count"))}/30</td>
        <td>{_integer(row.get("upstream_absorbed_seed_count"))}/30</td>
        <td>{_integer(row.get("no_measurable_effect_seed_count"))}/30</td>
        <td>{_integer(row.get("inactive_window_seed_count"))}/30</td></tr>'''
        for row in rows
    )


def _legacy_338929_details(data: Mapping[str, Any]) -> str:
    rows = [
        row
        for row in data["service"].get("worst_cases", [])
        if data["service"].get("state") == "complete"
        and str(row.get("chain_id") or "") == "338929_m1810_268091"
        and _integer(row.get("n_seeds")) > 0
    ]
    if not rows:
        return ""
    row = min(
        rows,
        key=lambda item: _number(item.get("product_on_due_date_proxy_mean"), 1.0),
    )
    return f'''<details class="method-note frozen-legacy"><summary>Ancien cas 338929 — étude ciblée séparée</summary>
      <p>Cette étude plus ancienne aboutit à {_percent(row.get("product_on_due_date_proxy_mean"))} de demande servie à la date attendue dans l'état testé, sur {_integer(row.get("n_seeds"))} répétitions simulées. Elle n'est utilisée ni pour former le trio ou le groupe réseau, ni pour choisir une action.</p>
    </details>'''


def _view_frozen_network_meeting(
    data: Mapping[str, Any], links: Mapping[str, str | None]
) -> str:
    network = data["network"]
    stable = list(network["stable_priorities"])
    if stable:
        priority_title = (
            "Trio de priorités simulées sous enveloppe du pire des deux tests "
            "voie-par-voie"
        )
        priority_cards = "".join(
            f'''<article class="frozen-priority"><span>Membre du trio non ordonné</span>
            <h3>{html.escape(str(row.get("supplier_id") or ""))}</h3>
            <strong>{html.escape(_frozen_metric_value("horizon_on_due_service_delta", row.get("metric_value")))}</strong>
            <p>{html.escape(str(row.get("driver_chain_id") or "voie non précisée"))} · {html.escape(_mechanism_label(row.get("driver_failure_mode")))}</p>
            <small>{_integer(row.get("top3_presence_seed_count"))}/30 simulations où ce fournisseur appartient au trio descriptif du service.</small></article>'''
            for row in sorted(stable, key=lambda item: str(item.get("supplier_id") or ""))
        )
        priority_reading = (
            "Ces trois noms se distinguent du fournisseur suivant pour la mesure de "
            "service sous cette enveloppe précise. Aucun ordre interne n'est affirmé."
        )
    else:
        priority_title = (
            "Groupe de priorités simulées sous enveloppe du pire des deux tests "
            "voie-par-voie"
        )
        chips = "".join(
            f'<span class="supplier-chip">{html.escape(str(value))}</span>'
            for value in sorted(network["priority_group_supplier_ids"])
        )
        priority_cards = (
            '<article class="frozen-group"><b>Groupe non ordonné à instruire</b>'
            f'<div class="chips">{chips}</div></article>'
        )
        priority_reading = (
            "L'écart avec le fournisseur suivant n'est pas assez net pour isoler trois "
            "noms. Aucun rang artificiel n'est affiché."
        )

    network_link = (
        _link_card(
            "Ouvrir l'analyse réseau détaillée",
            "18 voies, quatre conséquences, deux hypothèses et détails lot par lot",
            links.get("network_risk"),
        )
        if links.get("network_risk")
        else ""
    )
    return f'''
    <section id="view-vulnerability" class="view active" aria-labelledby="tab-vulnerability">
      <header class="view-head"><div><span class="view-number">1</span><p class="kicker">Priorités fournisseurs conditionnelles</p><h2>Où le réseau est-il le plus sensible sous les tests imposés ?</h2></div>{_status_badge(network["state"], network["detail"])}</header>
      <article class="panel frozen-priority-panel">
        <span class="eyebrow evidence-signal">SIGNAL DE PRIORITÉ SIMULÉ</span><h3>{html.escape(priority_title)}</h3>
        <p class="plain-summary"><b>Lecture client.</b> {html.escape(priority_reading)} L'enveloppe retient, pour chaque fournisseur, sa conséquence la plus défavorable entre un retard de date et une perte de quantité utile. Ce n'est ni une probabilité d'incident, ni une note de criticité observée.</p>
        <div class="frozen-priority-grid">{priority_cards}</div>
      </article>
      <article class="panel">
        <div class="panel-title"><div><span class="eyebrow evidence-simulated">SIMULÉ</span><h3>Quatre conséquences séparées — aucun score unique</h3></div><span class="mini-note">J0–J719 · 30 simulations</span></div>
        <div class="frozen-metric-grid">{_frozen_metric_cards(network)}</div>
      </article>
      <div class="two-col lower frozen-two-col">
        <article class="panel"><span class="eyebrow evidence-hypothesis">DEUX HYPOTHÈSES SÉVÈRES</span><h3>Deux mécanismes, jamais confondus</h3><div class="frozen-hypothesis-grid">{_frozen_hypothesis_cards(network)}</div><p class="plain-summary"><b>Couverture des dégradations.</b> Les 18 voies sont confirmées avec 30 comparaisons appariées sur le retard de 120 jours et la quantité utile limitée à 50 % seulement. Les quatre causes et les quatre périodes ne sont approfondies que sur trois voies. Les niveaux intermédiaires du premier tri reposent sur une seule simulation et ne permettent pas une conclusion robuste sur tout le réseau.</p></article>
        <article class="panel warning-panel"><span class="eyebrow evidence-gap">LIMITE</span><h3>Robustesse sur les 18 voies : non évaluable</h3><p>Les essais complémentaires dans le temps et sur d'autres causes ne portent que sur 3 voies présélectionnées. Ils ne permettent pas de dire que le trio ou le groupe resterait le même sur tout le réseau.</p><p class="plain-summary"><b>Retour à la normale.</b> Aucun délai de récupération du réseau n'est affiché ni utilisé : les fenêtres de calcul ne sont pas comparables entre les voies.</p></article>
      </div>
      <article class="panel frozen-effects"><span class="eyebrow evidence-simulated">EFFETS CONDITIONNELS</span><h3>Que s'est-il passé dans les 30 simulations testées ?</h3>
        <p class="plain-summary"><b>« x/30 » est un comptage de simulations.</b> Ce n'est ni une probabilité, ni une fréquence historique, ni une prévision fournisseur. Les catégories peuvent se chevaucher et ne doivent pas être additionnées.</p>
        <div class="table-wrap"><table><thead><tr><th>Fournisseur</th><th>Effet client</th><th>Production seulement</th><th>Absorbé en amont</th><th>Aucun effet mesurable</th><th>Voie inactive</th></tr></thead><tbody>{_frozen_effect_rows(network)}</tbody></table></div>
      </article>
      {_legacy_338929_details(data)}
      {network_link}
    </section>'''


def _supplier_source_audit_note(data: Mapping[str, Any]) -> str:
    audit = (
        data.get("supplier_source_audit")
        if isinstance(data.get("supplier_source_audit"), Mapping)
        else {}
    )
    if audit.get("state") != "complete":
        return '''<p class="plain-summary"><b>Limite des données fournisseur.</b> Le réseau ne remplace pas la cotation interne de l'industriel. Pour évaluer les fournisseurs, il faut encore relier criticité, OTIF, qualité, capacité et délais réellement observés.</p>'''
    manifest = audit.get("manifest") if isinstance(audit.get("manifest"), Mapping) else {}
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), Mapping) else {}
    located_external = _integer(summary.get("location_external_account_count"))
    direct_fia_external = _integer(summary.get("direct_product_fia_external_supplier_count"))
    upstream_external = _integer(summary.get("upstream_021081_fia_external_supplier_count"))
    all_fia_external = _integer(summary.get("all_fia_external_supplier_count"))
    exact_location_matches = _integer(summary.get("all_fia_external_with_location_count"))
    if min(
        located_external,
        direct_fia_external,
        upstream_external,
        all_fia_external,
        exact_location_matches,
    ) <= 0:
        return '''<p class="plain-summary"><b>Limite des données fournisseur.</b> Le réseau ne remplace pas la cotation interne de l'industriel. Pour évaluer les fournisseurs, il faut encore relier criticité, OTIF, qualité, capacité et délais réellement observés.</p>'''
    return f'''<p class="plain-summary"><b>Ce que les sources fournisseur apportent.</b> L'annuaire localise {located_external} comptes externes. Les FIA de 268091/268967 en décrivent {direct_fia_external}; celle de 773474 ajoute {upstream_external} sources de 021081 et porte l'ensemble à {all_fia_external} fournisseurs externes. La jointure exacte avec la localisation couvre {exact_location_matches}/{all_fia_external} fournisseurs. Ces fichiers ne contiennent aucune criticité, aucun OTIF, aucun historique qualité et aucune capacité observée. Les délais FIA sont prévisionnels, pas des délais réellement constatés.</p>'''


def _view_vulnerability(
    data: Mapping[str, Any], links: Mapping[str, str | None]
) -> str:
    scope = data["scope"]
    manifest = scope["manifest"]
    artifact_name = str(scope.get("artifact_name") or "")
    artifact_version = next(
        (
            token
            for token in reversed(artifact_name.split("_"))
            if token.startswith("v") and token[1:].isdigit()
        ),
        "version non indiquée",
    )
    lanes = scope["lanes"]
    counts = manifest.get("counts_by_evidence_status") if isinstance(manifest.get("counts_by_evidence_status"), Mapping) else Counter(str(row.get("evidence_status")) for row in lanes)
    supplier_count = len({str(row.get("supplier_id") or "") for row in lanes if row.get("supplier_id")})
    lane_count = _integer(manifest.get("lane_count"), len(lanes))
    priority_count = _integer(manifest.get("priority_lane_count"))
    unexercised = _integer(counts.get("unexercised"))
    single = _integer(manifest.get("single_source_item_site_count"))
    item_sites = _integer(manifest.get("item_site_count"))
    multi = _integer(manifest.get("multisource_item_site_count"))
    weak_multi = _integer(manifest.get("multisource_only_one_supplier_evidenced_count")) + _integer(manifest.get("multisource_no_supplier_evidenced_count"))
    excluded = _integer(manifest.get("purchase_order_rows_excluded_from_exact_lanes"))
    retained = _integer(manifest.get("observed_order_row_count"))
    excluded_suppliers = _integer(manifest.get("purchase_order_suppliers_excluded_from_exact_lanes"))
    excluded_items = _integer(manifest.get("purchase_order_items_excluded_from_exact_lanes"))
    unmapped_division = _integer(manifest.get("purchase_order_rows_with_unmapped_division"))
    normalized_uom = _integer(manifest.get("purchase_order_rows_uom_normalized"))
    active_lanes = [row for row in lanes if _truthy(row.get("baseline_positive_flow"))]
    active_sole_source = sum(_truthy(row.get("is_sole_structural_source")) for row in active_lanes)
    active_by_product = Counter(
        product.strip()
        for row in active_lanes
        for product in str(row.get("downstream_products") or "").split("|")
        if product.strip()
    )
    active_supplier_count = len(
        {str(row.get("supplier_id") or "") for row in active_lanes if row.get("supplier_id")}
    )
    network_risk_link = (
        f'''<div class="network-detail-link">{_link_card(
            f"Ouvrir l'analyse détaillée des {len(active_lanes)} voies actives",
            f"sensibilité des {active_supplier_count} fournisseurs du réseau actif",
            links.get("network_risk"),
        )}</div>'''
        if links.get("network_risk")
        else ""
    )

    service = data["service"]
    worst_by_chain: dict[str, Mapping[str, object]] = {}
    if service["state"] == "complete":
        for row in service["worst_cases"]:
            chain = str(row.get("chain_id") or "")
            rank = _integer(row.get("worst_rank_within_chain"), 999)
            if chain and (chain not in worst_by_chain or rank < _integer(worst_by_chain[chain].get("worst_rank_within_chain"), 999)):
                worst_by_chain[chain] = row
    stress_rows = list(worst_by_chain.values())
    stress_cards = []
    for row in stress_rows:
        chain = str(row.get("chain_id") or "")
        component = chain.split("_")[0] if chain else "voie"
        product = str(row.get("target_product_id") or chain.split("_")[-1])
        mechanism = _mechanism_label(row.get("mechanism"))
        value = _fr(row.get("mechanism_value"), 0)
        n = _integer(row.get("n_seeds"))
        tail_reading = (
            f"5e percentile sur {n} répétitions simulées : "
            f"{_percent(row.get('product_on_due_date_proxy_p05'))}."
            if n >= 100
            and str(row.get("product_on_due_date_proxy_p05") or "").strip()
            else (
                f"Avec seulement {n} répétitions simulées, aucun cas défavorable chiffré "
                "n'est publié; la moyenne reste une indication exploratoire."
            )
        )
        stress_cards.append(
            f'''<article class="metric-card"><span class="eyebrow evidence-hypothesis">HYPOTHÈSE</span><h3>{html.escape(component)} → {html.escape(product)}</h3><strong>{_percent(row.get("product_on_due_date_proxy_mean"))}</strong><span>de la demande servie à la date attendue dans le modèle</span><p>{html.escape(mechanism.capitalize())} de {value} jours, moyenne de {n} répétitions simulées. {html.escape(tail_reading)}</p></article>'''
        )
    focused = (
        f'''<article class="panel">
          <div class="panel-title"><div><span class="eyebrow evidence-simulated">SIMULÉ</span><h3>Deux voies explorées sous stress sévère</h3></div>{_status_badge("exploratory_complete", service["detail"])}</div>
          {_stress_svg(stress_rows)}
          <div class="card-stack horizontal">{''.join(stress_cards)}</div>
          <p class="plain-summary"><b>Ce que l'on apprend.</b> 338929 vers 268091 et 344135 vers 268967 transmettent fortement certains retards longs au client dans le modèle. Ces scénarios extrêmes encadrent des zones de bascule; ils ne calibrent pas exactement un niveau de service à 80 % ou 93 %, et ne prédisent pas qu'un retard de 180 jours va se produire.</p>
          <p class="plain-summary protocol"><b>Ne pas compter deux fois la même réponse.</b> Dans le moteur actuel, retard transport et attente qualité peuvent avoir le même effet s'ils repoussent uniquement la date d'utilisabilité. Disponibilité et rendement qualité peuvent aussi coïncider sur la quantité utile. Les causes métier restent différentes, mais des courbes identiques ne sont pas des confirmations indépendantes.</p>
        </article>'''
        if stress_rows
        else f'''<article class="panel pending-panel"><div class="panel-title"><h3>Deux voies ciblées</h3>{_status_badge(service["state"], service["detail"])}</div><p>{html.escape(service["detail"])}</p></article>'''
    )
    return f'''
    <section id="view-vulnerability" class="view" aria-labelledby="tab-vulnerability" hidden>
      <header class="view-head"><div><span class="view-number">2</span><p class="kicker">Réseau et scénarios</p><h2>Où la supply est physiquement vulnérable</h2></div>{_status_badge("scope_audited", f"Audit de couverture réseau {artifact_version}")}</header>
      <div class="hero-grid four">
        <article class="hero-card blue"><span class="eyebrow evidence-observed">STRUCTURE</span><strong>{supplier_count}</strong><span>fournisseurs dans le graphe</span></article>
        <article class="hero-card navy"><span class="eyebrow evidence-observed">STRUCTURE</span><strong>{lane_count}</strong><span>voies fournisseur–article–site</span></article>
        <article class="hero-card green"><span class="eyebrow evidence-simulated">ÉTAYÉ</span><strong>{priority_count}</strong><span>voies vues en simulation ou dans le carnet</span></article>
        <article class="hero-card gray"><span class="eyebrow evidence-gap">À TESTER</span><strong>{unexercised}</strong><span>voies encore non exercées</span></article>
      </div>
      <p class="plain-summary protocol"><b>Ce que calcule le moteur.</b> La supply reste dynamique : les stocks, les backlogs, la production et le MRP évoluent avec l'état du système. Pour isoler la sensibilité, les incidents fournisseurs sont toutefois injectés comme des hypothèses exogènes; les risques endogènes dépendant de l'état et le pilotage automatique en boucle fermée sont désactivés. Cette campagne ne prédit donc pas la survenue des incidents et ne constitue pas une prévision fournisseur.</p>
      <p class="plain-summary"><b>Lecture métier.</b> « Non exercée » signifie que la voie existe dans le réseau mais n'apparaît ni dans le flux dynamique de référence ni dans les commandes ouvertes exactement raccordées. Cela ne veut pas dire que le fournisseur n'a jamais livré.</p>
      {_supplier_source_audit_note(data)}
      {network_risk_link}

      <div class="two-col">
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow evidence-observed">COUVERTURE</span><h3>Ce qui est effectivement étayé</h3></div></div>
          {_scope_svg(counts)}
          <p class="plain-summary"><b>Ce que le graphique distingue.</b> {priority_count} voies ont au moins une preuve d'activité dans les données utilisées; {unexercised} restent un angle mort. Les {retained} lignes de carnet retenues correspondent exactement au graphe; {normalized_uom} ont été converties dans l'unité du réseau en conservant quantité et unité sources.</p>
          <p class="plain-summary alert"><b>Angle mort à raccorder.</b> {excluded} autres lignes sur les {retained + excluded} de l'audit achat concernent {excluded_suppliers} fournisseurs et {excluded_items} articles; {unmapped_division} relèvent notamment de la division 1820, absente du graphe. Elles ne valent ni « zéro flux » ni « fournisseur non critique » : elles sont hors périmètre du modèle actuel.</p>
        </article>
        <article class="panel source-panel">
          <span class="eyebrow evidence-signal">POINT DE VIGILANCE</span><h3>Une deuxième source dessinée n'est pas encore un secours</h3>
          <div class="source-numbers"><div><strong>{single}/{item_sites}</strong><span>articles-sites structurellement mono-source</span></div><div><strong>{weak_multi}/{multi}</strong><span>multisources avec au plus une source étayée</span></div></div>
          <p><b>Sur les flux actifs :</b> {len(active_lanes)} voies chez {active_supplier_count} fournisseurs, dont {active_by_product.get('268091', 0)} vers 268091 et {active_by_product.get('268967', 0)} vers 268967. {active_sole_source}/{len(active_lanes)} sont structurellement mono-source. Les trois multisources actives (001848, 001893 et 055703) n'ont pas encore de secours qualifié et capacitaire confirmé.</p>
          <p class="plain-summary"><b>Conséquence opérationnelle.</b> Avant de compter sur une alternative, il faut confirmer sa qualification, sa capacité disponible, son délai réel, son minimum de commande, son stock et l'accord qualité. Le graphe seul ne prouve rien de tout cela.</p>
        </article>
      </div>
      {focused}
      {_network_conclusion(data)}
    </section>'''


def _component_masking_evidence(component: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = component.get("payload") if isinstance(component.get("payload"), Mapping) else {}
    evidence = payload.get("intermediate_773474_masking_audit")
    return evidence if isinstance(evidence, Mapping) else {}


def _component_has_exploratory_provenance(component: Mapping[str, Any]) -> bool:
    """Recognise explicit limitations without hiding otherwise auditable values."""

    def visit(value: object, key: str = "") -> bool:
        if isinstance(value, Mapping):
            return any(visit(child, str(child_key)) for child_key, child in value.items())
        if isinstance(value, list):
            return any(visit(child, key) for child in value)
        normalized_key = key.strip().lower().replace("-", "_")
        normalized_value = str(value or "").strip().lower().replace("-", "_")
        if normalized_value in {"", "0", "false", "none", "null", "not_applicable"}:
            return False
        combined = f"{normalized_key}_{normalized_value}"
        if normalized_key == "exploratory":
            return _truthy(value) or "exploratory" in normalized_value
        if "exploratory" in normalized_value:
            return True
        if "orchestrator_sha_at_launch_unknown" in combined:
            return True
        if "unit_validation_pending" in combined:
            return True
        return (
            "provenance" in combined
            and "consolid" in combined
            and ("multi" in combined or "multiple" in combined)
        )

    return visit(component.get("manifest")) or visit(component.get("payload"))


def _component_provenance_presentation(
    component: Mapping[str, Any],
) -> tuple[str, str]:
    exploratory = _component_has_exploratory_provenance(component)
    if exploratory and component.get("state") == "complete":
        badge = _status_badge(
            "exploratory_complete",
            "Calcul terminé, mais unité ou provenance encore à consolider.",
        )
    else:
        badge = _status_badge(
            str(component.get("state") or "unavailable"),
            str(component.get("detail") or ""),
        )
    note = (
        '''<p class="plain-summary protocol"><b>Portée de l'étude.</b> Étude exploratoire complète : les calculs et chiffres auditables restent visibles, mais la provenance ou l'unité doit encore être consolidée. Ce niveau de preuve ne vaut pas validation industrielle définitive.</p>'''
        if exploratory
        else ""
    )
    return badge, note


def _component_methodology_block(component: Mapping[str, Any]) -> str:
    masking = _component_masking_evidence(component)
    released_lots = _number(masking.get("released_268967_lot_count"), math.nan)
    need_g = _number(masking.get("approx_horizon_need_g"), math.nan)
    stock_g = _number(masking.get("opening_stock_total_g"), math.nan)
    production_g = _number(masking.get("horizon_773474_production_g"), math.nan)
    stock_share = _number(masking.get("stock_multiple_of_horizon_need"), math.nan)
    combined_multiple = _number(
        masking.get("stock_plus_production_multiple_of_horizon_need"), math.nan
    )
    stock_021_multiple = _number(
        masking.get("021081_stock_multiple_of_horizon_intermediate_consumption"),
        math.nan,
    )
    orderbook_021_multiple = _number(
        masking.get("021081_order_book_multiple_of_horizon_intermediate_consumption"),
        math.nan,
    )
    if not math.isfinite(stock_share) and need_g > 0 and math.isfinite(stock_g):
        stock_share = stock_g / need_g
    if (
        not math.isfinite(combined_multiple)
        and need_g > 0
        and math.isfinite(stock_g)
        and math.isfinite(production_g)
    ):
        combined_multiple = (stock_g + production_g) / need_g
    values = (
        released_lots,
        need_g,
        stock_g,
        production_g,
        stock_share,
        combined_multiple,
        stock_021_multiple,
        orderbook_021_multiple,
    )
    if all(math.isfinite(value) for value in values):
        masking_block = f'''<div class="masking-grid">
          <div><b>{_fr(released_lots,0)} lots simulés</b><span>de 268967 libérés dans l'horizon</span></div>
          <div><b>{_fr(need_g / 1_000_000,6)} M G</b><span>besoin correspondant de 773474</span></div>
          <div><b>{_fr(stock_g / 1_000_000,3)} M G · {_percent(stock_share,2)}</b><span>stock initial 773474 / besoin horizon</span></div>
          <div><b>{_fr(production_g / 1_000_000,1)} M G</b><span>production de 773474 dans l'horizon</span></div>
          <div><b>{_fr(combined_multiple,3)}×</b><span>stock plus production 773474 / besoin</span></div>
          <div><b>{_fr(stock_021_multiple,3)}× · {_fr(orderbook_021_multiple,3)}×</b><span>stock 021081 puis carnet / consommation intermédiaire</span></div>
        </div><p class="plain-summary"><b>Lecture du masquage.</b> L'absorption vient du cumul des couches 773474 et 021081. Réduire seulement le stock 021081 ne représente pas une supply globalement allégée.</p>'''
    else:
        masking_block = '''<p class="plain-summary alert"><b>Masquage à rechiffrer.</b> Cet artefact ne fournit pas encore ensemble le nombre de lots libérés, le besoin et la production de 773474, puis les multiples de stock et de carnet 021081. Aucun ancien ratio n'est substitué et aucun nombre manquant n'est inventé.</p>'''
    return f'''<article class="panel warning-panel component-methodology">
      <span class="eyebrow evidence-gap">UNITÉ NOMENCLATURE À VALIDER</span><h3>Deux branches d'hypothèse, aucune correction silencieuse</h3>
      <p>La source <b>773474.xlsx</b> déclare une sortie de <b>1 000 G</b>, la décrit comme <b>CONT. 1 000 L</b> et associe <b>8,94 KG</b> de 021081. L'interprétation littérale du graphe et l'interprétation alternative diffèrent donc d'un facteur 1 000; les données disponibles ne permettent pas de dire laquelle est correcte.</p>
      <p class="plain-summary"><b>Règle scientifique.</b> Tester séparément le ratio littéral et le ratio divisé par 1 000, tous deux étiquetés comme hypothèses. La source reste inchangée tant que l'industriel n'a pas confirmé l'unité et la base physique.</p>
      {masking_block}
    </article>'''


def _component_status_block(data: Mapping[str, Any]) -> tuple[str, Mapping[str, object]]:
    component = data["component_021081"]
    audit = component["observed_order_audit"]
    if not audit:
        manifest_audit = component["manifest"].get("observed_order_book_audit")
        audit = manifest_audit if isinstance(manifest_audit, Mapping) else {}
    badge, provenance_note = _component_provenance_presentation(component)
    methodology = _component_methodology_block(component)
    audit_available = _observed_order_audit_complete(audit)
    order_count = _integer(audit.get("order_count")) if audit_available else 0
    observed_context = (
        "Le carnet et le stock d'ouverture sont des faits du snapshot fourni."
        if audit_available
        else "Le carnet 021081 n'est pas fourni à cette page; aucun fait chiffré n'en est repris."
    )
    replay_reading = (
        f"Ce rejeu historique réinjecte volontairement les {order_count} lignes "
        "planifiées et calcule leurs réceptions simulées."
        if audit_available
        else "Le rejeu historique ne peut réinjecter le carnet planifié que lorsqu'un audit source complet est fourni."
    )
    completed_replay_reading = (
        f"Le rejeu historique réinjecte les {order_count} lignes planifiées du snapshot; "
        f"chacune devient une réception technique simulée, pas une réception observée après coup. "
        "Aucun numéro de commande ou de lot industriel n'est reconstitué."
        if audit_available
        else "Aucun nombre de commandes ou de réceptions n'est repris sans audit source complet du carnet."
    )
    if component["state"] != "complete":
        return (
            f'''<article class="panel pending-panel"><div class="panel-title"><div><span class="eyebrow evidence-simulated">SIMULÉ</span><h3>Propagation 021081 vers les lots aval</h3></div>{badge}</div><p>{html.escape(component["detail"])}</p>{provenance_note}<p class="plain-summary"><b>Ce qui est déjà utilisable.</b> {html.escape(observed_context)} Les effets aval ne seront publiés qu'après la campagne complète; les résultats partiels restent volontairement masqués.</p><p class="plain-summary protocol"><b>Deux protocoles, pas une contradiction.</b> La référence dynamique propre désactive les commandes d'ouverture et ne mesure donc aucune arrivée 021081. {html.escape(replay_reading)}</p></article>{methodology}''',
            audit,
        )
    payload = component["payload"]
    regimes = payload.get("state_regime_effects") if isinstance(payload.get("state_regime_effects"), list) else []
    valid_regimes = [row for row in regimes if isinstance(row, Mapping)]
    tested_configurations = sum(
        _integer(row.get("tested_stress_configurations")) for row in valid_regimes
    )
    downstream_effect_configurations = sum(
        _integer(row.get("configurations_with_simulated_downstream_product_effect"))
        for row in valid_regimes
    )
    if tested_configurations > 0 and downstream_effect_configurations == 0:
        effect_title = "Aucun effet aval démontré de 021081 vers 268967"
        effect_reading = (
            f"Dans les {tested_configurations} configurations testées, l'incident n'a modifié "
            "aucun volume de 268967 à la date attendue. Les stocks, le carnet et la production "
            "intermédiaire du modèle ont masqué l'incident dans ce protocole. Cela ne prouve pas "
            "une résilience industrielle générale; aucun effet client, coût ou action n'est "
            "démontré ici."
        )
    elif tested_configurations > 0:
        effect_title = "Effet aval simulé de 021081 vers 268967"
        effect_reading = (
            f"{downstream_effect_configurations} configurations sur {tested_configurations} ont "
            "modifié le volume de 268967 à la date attendue. Elles identifient des états du "
            "modèle à approfondir; elles ne prouvent ni un risque observé, ni un effet client, "
            "ni qu'une modification du seul stock 021081 serait une action adaptée."
        )
    else:
        effect_title = "Propagation 021081 vers le produit 268967"
        effect_reading = (
            "Aucune configuration interprétable n'est fournie; aucun effet aval n'est conclu."
        )
    return (
        f'''<article class="panel"><div class="panel-title"><div><span class="eyebrow evidence-simulated">SIMULÉ</span><h3>{html.escape(effect_title)}</h3></div>{badge}</div>{provenance_note}{_regime_svg(regimes)}<p class="plain-summary"><b>Ce que l'on apprend.</b> {html.escape(effect_reading)}</p><p class="plain-summary protocol"><b>Deux protocoles, pas une contradiction.</b> La référence dynamique propre désactive les commandes d'ouverture et ne mesure donc aucune arrivée 021081. {html.escape(completed_replay_reading)}</p></article>{methodology}''',
        audit,
    )


def _find_action_row(
    rows: Sequence[Mapping[str, object]], failure_mode: str, lever_id: str
) -> Mapping[str, object] | None:
    return next(
        (
            row
            for row in rows
            if str(row.get("record_type") or "") == "tested_lever"
            and str(row.get("failure_mode") or "") == failure_mode
            and str(row.get("lever_id") or "") == lever_id
        ),
        None,
    )


def _tested_action_card(
    *,
    title: str,
    row: Mapping[str, object],
    conclusion: str,
    tone: str,
) -> str:
    exposed = _integer(row.get("customer_exposure_seeds"))
    total = _integer(row.get("total_seeds"))
    recovery = _number(row.get("mean_days_recovered_exposed"))
    remaining = _number(row.get("mean_remaining_impact_pct_exposed"))
    cost = _number(row.get("mean_incremental_cost_model_units"))
    if recovery < -1e-9:
        recovery_reading = f"{_fr(abs(recovery),1)} jours perdus en moyenne dans ces essais"
    elif recovery > 1e-9:
        recovery_reading = f"{_fr(recovery,1)} jours gagnés en moyenne dans ces essais"
    else:
        recovery_reading = "aucun jour gagné dans ces essais"
    return f'''<article class="audit-result {html.escape(tone)}">
      <h4>{html.escape(title)}</h4>
      <div class="audit-metrics"><span><b>{exposed}/{total}</b> essais où l'incident sans action atteint le client simulé</span><span><b>{html.escape(recovery_reading)}</b></span><span><b>{_fr(remaining,1)} %</b> de l'impact client simulé restant dans les cas exposés</span><span><b>{_fr(cost,0)}</b> indice de coût du modèle, sans unité monétaire, en moyenne sur les {total} essais</span></div>
      <p>{html.escape(conclusion)}</p>
    </article>'''


def _action_audit_block(data: Mapping[str, Any]) -> str:
    audit = data.get("action_audit") if isinstance(data.get("action_audit"), Mapping) else {}
    if audit.get("state") != "complete":
        return ""
    rows = audit.get("rows") if isinstance(audit.get("rows"), list) else []
    delay_expedite = _find_action_row(rows, "transport_delay", "expedited_transport")
    delay_replan = _find_action_row(rows, "transport_delay", "replanning")
    quality_expedite = _find_action_row(rows, "quality_hold", "expedited_transport")
    quality_bundle = _find_action_row(rows, "quality_hold", "combined_response")
    tested_cards: list[str] = []
    if delay_expedite:
        tested_cards.append(
            _tested_action_card(
                title="338929 · transport accéléré ciblé",
                row=delay_expedite,
                conclusion=(
                    "Effet favorable dans cet ancien scénario lorsque la perturbation est bien "
                    "un retard physique sur une expédition actionnable. Ce résultat ne valide "
                    "aucun transporteur, itinéraire ou service réellement disponible."
                ),
                tone="positive",
            )
        )
    if quality_expedite:
        tested_cards.append(
            _tested_action_card(
                title="021081 · transport accéléré après libération qualité",
                row=quality_expedite,
                conclusion=(
                    "Le transport aide à récupérer après la libération du lot; il ne raccourcit "
                    "jamais la retenue qualité et ne suppose aucun contournement."
                ),
                tone="partial",
            )
        )
    if delay_replan:
        tested_cards.append(
            _tested_action_card(
                title="338929 · multiplicateurs de replanification",
                row=delay_replan,
                conclusion=(
                    "Configuration à rejeter : cette approximation a retardé la récupération et "
                    "aggravé l'impact. Elle ne représente pas un APS à capacité finie."
                ),
                tone="negative",
            )
        )
    if quality_bundle:
        tested_cards.append(
            _tested_action_card(
                title="021081 · plan combiné",
                row=quality_bundle,
                conclusion=(
                    "Effet simulé intéressant, mais plan non prêt à déployer : il mélange des "
                    "actions natives avec des approximations d'achat exceptionnel et de replanification."
                ),
                tone="caution",
            )
        )

    mode_rows = {
        str(row.get("failure_mode") or "")
        for row in rows
        if str(row.get("record_type") or "") == "mode_recommendation"
    }
    realistic = {
        "transport_delay": (
            "Retard logistique",
            "Accélérer une expédition identifiée seulement si la matière existe et si le trajet est encore actionnable.",
            "Statut d'expédition, route, capacité transport, douane, coût daté et stock libre.",
        ),
        "supply_unavailability": (
            "Indisponibilité matière",
            "Allouer le stock réellement libre; activer uniquement une source déjà qualifiée avec capacité confirmée; sinon replanifier les ordres réels.",
            "Stock par site et statut, qualification, capacité, MOQ, délai, contrat et priorités clients.",
        ),
        "quality_hold": (
            "Attente qualité",
            "Contenir le lot; utiliser un lot déjà libéré ou une alternative approuvée; appliquer la disposition qualité; accélérer seulement après libération.",
            "Décision qualité, généalogie, lot libéré, durée de vie, source approuvée et capacité.",
        ),
        "quality_yield_loss": (
            "Perte de rendement",
            "Employer un lot de remplacement ou une alternative approuvée; envisager rework ou salvage uniquement si la qualité l'autorise.",
            "Quantité rejetée, cause, disposition, équivalence matière, rendement et capacité vérifiés.",
        ),
    }
    realistic_cards = []
    for mode in ("transport_delay", "supply_unavailability", "quality_hold", "quality_yield_loss"):
        if mode not in mode_rows:
            continue
        title, action, prerequisite = realistic[mode]
        evidence_note = (
            "Le passage au réel reste à valider malgré un test simplifié."
            if mode in {"transport_delay", "quality_hold"}
            else "Aucune action dédiée n'a encore été confirmée par la campagne existante."
        )
        realistic_cards.append(
            f'''<article class="real-action"><h4>{html.escape(title)}</h4><p>{html.escape(action)}</p><small><b>Avant de promettre :</b> {html.escape(prerequisite)}</small><em>{html.escape(evidence_note)}</em></article>'''
        )
    if not tested_cards and not realistic_cards:
        return ""
    ineffective_count = sum(
        str(row.get("record_type") or "") == "tested_lever"
        and (
            str(row.get("result_class") or "").startswith("ineffective")
            or str(row.get("result_class") or "").startswith("invalid")
        )
        for row in rows
    )
    return f'''<div class="action-audit-split" aria-label="Séparation entre anciens essais simulés et familles d'actions à vérifier">
      <article class="panel tested-actions">
        <div class="panel-title"><div><span class="eyebrow evidence-simulated">ANCIENS ESSAIS SIMULÉS — AUCUNE ACTION VALIDÉE</span><h3>Ce que dix essais sur leurs états initiaux ont montré</h3></div>{_status_badge("complete", "Audit historique séparé; aucune nouvelle simulation")}</div>
        <p class="audit-intro"><b>Bloc historique séparé.</b> Ces chiffres proviennent de deux anciens scénarios de cascade, pas de l'analyse réseau finale ni du rejeu des 23 lignes planifiées 021081. Dans chaque essai, la situation sans action et la situation avec action partent du même état initial. « 2 sur 10 » ou « 9 sur 10 » indique seulement dans combien d'essais l'incident atteint le client simulé; ce n'est pas une fréquence industrielle. Aucun levier n'est déclaré disponible ou validé opérationnellement par ce bloc.</p>
        <div class="audit-result-grid">{''.join(tested_cards)}</div>
        <p class="plain-summary"><b>Résultats négatifs conservés.</b> {ineffective_count} configurations testées sont classées inopérantes ou non recevables dans leur représentation actuelle. Un levier natif peut rester sans effet; une approximation favorable ne devient pas pour autant une solution disponible.</p>
        <p class="plain-summary"><b>Coûts.</b> Les valeurs affichées sont des indices sans unité monétaire. Elles ne sont ni des devis, ni comparables aux valeurs livrées ou non réalisées de 2025.</p>
      </article>
      <article class="panel realistic-actions">
        <div class="panel-title"><div><span class="eyebrow evidence-hypothesis">FAMILLES D'ACTIONS À VÉRIFIER AVEC LES ÉQUIPES</span><h3>Prérequis à confirmer avant toute recommandation</h3></div><span class="status status-not_concluded">À valider</span></div>
        <div class="real-action-grid">{''.join(realistic_cards)}</div>
        <p class="plain-summary"><b>Règle.</b> Cette liste fixe des questions à instruire, pas une sélection finale. Une action devient recommandable seulement après confirmation de sa disponibilité, de son délai, de sa capacité, de son coût et de son statut qualité, puis après un essai sur le dossier fournisseur concerné.</p>
      </article>
    </div>'''


def _observed_order_audit_complete(audit: Mapping[str, object]) -> bool:
    required = (
        "order_count",
        "quantity_kg",
        "physical_delivery_day_min",
        "physical_delivery_day_max",
        "usable_day_min",
        "usable_day_max",
    )
    values_present = all(
        key in audit and str(audit.get(key) if audit.get(key) is not None else "").strip()
        for key in required
    )
    supplier_rows = audit.get("supplier_rows")
    return bool(
        values_present
        and _integer(audit.get("order_count")) > 0
        and _number(audit.get("quantity_kg")) > 0
        and isinstance(supplier_rows, list)
        and supplier_rows
    )


def _frozen_network_lot_block(data: Mapping[str, Any]) -> str:
    """Explain the frozen network lot result without confusing exposure and cause."""

    if not _has_frozen_network(data):
        return ""
    payload = data["network"]["payload"]
    if payload.get("causal_released") is not True:
        return '''<article class="panel pending-panel frozen-network-lots">
          <span class="eyebrow evidence-gap">RÉSULTAT CAUSAL NON PUBLIÉ</span><h3>Lots réseau : nombres masqués</h3>
          <p class="plain-summary">La comparaison entre fonctionnement normal et incident n'est pas publiable. L'exposition généalogique ne suffit pas à affirmer qu'un lot a été retardé ou perdu.</p>
        </article>'''

    exposure_rows = payload.get("lot_exposure")
    causal_rows = payload.get("causal_pairs")
    if not isinstance(exposure_rows, list) or not isinstance(causal_rows, list):
        raise ValueError("Les résultats lot du réseau gelé sont incomplets.")
    root_lots = sum(_integer(row.get("root_lot_count")) for row in exposure_rows)
    descendants = sum(
        _integer(row.get("exposed_descendant_lot_count")) for row in exposure_rows
    )
    matched_rows = sum(
        _integer(row.get("unique_matched_technical_key_count")) for row in causal_rows
    )
    changed_rows = sum(
        _integer(row.get("actual_difference_row_count")) for row in causal_rows
    )
    return f'''<article class="panel frozen-network-lots">
      <div class="panel-title"><div><span class="eyebrow evidence-simulated">LOTS SIMULÉS</span><h3>Exposition et effet causal : deux informations différentes</h3></div><span class="mini-note">réseau · fonctionnement normal comparé à l'incident</span></div>
      <div class="frozen-lot-grid">
        <div><strong>{len(exposure_rows)}</strong><span>cas fournisseur–voie examinés</span></div>
        <div><strong>{root_lots}</strong><span>occurrences de lots à l'origine des chaînes</span></div>
        <div><strong>{descendants}</strong><span>occurrences aval exposées, borne haute</span></div>
        <div><strong>{changed_rows}/{matched_rows}</strong><span>lignes techniques modifiées / comparables</span></div>
      </div>
      <p class="plain-summary"><b>Exposition.</b> La généalogie repère les lots simulés qui partagent une chaîne avec la réception. C'est une borne haute : être exposé ne signifie pas avoir été retardé, perdu ou causé par l'incident.</p>
      <p class="plain-summary"><b>Effet causal.</b> Un écart n'est attribué à l'incident que si la même ligne technique peut être comparée entre le fonctionnement normal et l'incident, partis du même état initial. Une ligne technique reste un identifiant du modèle, jamais un numéro de lot ou de commande industriel.</p>
      <p class="plain-summary"><b>Périmètre du détail causal.</b> Il porte sur une seule comparaison appariée pour chacune des trois voies approfondies. Il montre un mécanisme simulé, pas la variabilité statistique des effets lot par lot ni la traçabilité complète des lots industriels.</p>
      <p class="plain-summary protocol"><b>Qualité et retour à la normale.</b> La retenue qualité est un scénario reconstruit, pas un statut qualité observé. Aucun délai de récupération du réseau n'est affiché ni utilisé, car les fenêtres de comparaison entre voies ne sont pas compatibles.</p>
    </article>'''


def _decision_conditions_block() -> str:
    return '''<article class="panel decisions">
        <div class="panel-title"><div><span class="eyebrow evidence-signal">CONDITIONS DE DÉCISION</span><h3>Ce qu'il faut vérifier avant d'envisager une action</h3></div><span class="mini-note">aucun contournement qualité</span></div>
        <div class="table-wrap"><table><thead><tr><th>Cause constatée</th><th>Famille d'action potentiellement pilotable</th><th>Condition avant de la promettre</th></tr></thead><tbody>
          <tr><td>Expédition partie mais transport retardé</td><td>Basculer une expédition identifiée vers un mode ou itinéraire réservé; fractionner si le conditionnement l'autorise.</td><td>Créneau, capacité transport, coût, douane et date de départ confirmés.</td></tr>
          <tr><td>Fournisseur incapable d'expédier</td><td>Allouer le stock disponible aux ordres clients prioritaires; replanifier; activer une source ou matière déjà qualifiée.</td><td>Stock libre et généalogie fiables; alternative déjà approuvée avec capacité confirmée.</td></tr>
          <tr><td>Lot en retenue qualité</td><td>Isoler le lot, utiliser un lot déjà libéré, déclencher la procédure de disposition et replanifier autour du lot bloqué.</td><td>Aucune libération accélérée supposée; décision qualité selon procédure et preuves.</td></tr>
          <tr><td>Risque durable de capacité</td><td>Qualifier une seconde source, négocier une capacité réservée, ajuster lot minimum et constituer un stock ciblé avant la période à risque.</td><td>Qualification, délai de montée en charge, durée de vie, coût et engagement contractuel.</td></tr>
        </tbody></table></div>
        <p class="plain-summary"><b>Comment utiliser la simulation.</b> Une fois ses prérequis confirmés, comparer pour chaque cause la référence, l'incident sans action et chaque action effectivement disponible. La décision se juge sur les jours de service récupérés, les lots/clients protégés, le coût supplémentaire et le risque restant — jamais sur un score unique.</p>
      </article>'''


def _view_lots(
    data: Mapping[str, Any],
    links: Mapping[str, str | None],
    *,
    include_action_sections: bool = True,
) -> str:
    component_block, audit = _component_status_block(data)
    audit_available = _observed_order_audit_complete(audit)
    supplier_rows = (
        audit.get("supplier_rows")
        if audit_available and isinstance(audit.get("supplier_rows"), list)
        else []
    )
    order_count = _integer(audit.get("order_count")) if audit_available else 0
    quantity = _number(audit.get("quantity_kg")) if audit_available else math.nan
    supplier_count = len(supplier_rows) if audit_available else 0
    physical_min = _integer(audit.get("physical_delivery_day_min")) if audit_available else 0
    physical_max = _integer(audit.get("physical_delivery_day_max")) if audit_available else 0
    usable_min = _integer(audit.get("usable_day_min")) if audit_available else 0
    usable_max = _integer(audit.get("usable_day_max")) if audit_available else 0
    order_count_label = str(order_count) if audit_available else "non disponible"
    supplier_count_label = str(supplier_count) if audit_available else "non disponible"
    quantity_label = f"{_compact(quantity)} kg planifiés" if audit_available else "quantité non disponible"
    orderbook_panel = (
        f'''<article class="panel">
          <div class="panel-title"><div><span class="eyebrow evidence-observed">OBSERVÉ DANS LE SNAPSHOT AU 01/01/2025</span><h3>Carnet ouvert du composant 021081</h3></div></div>
          {_orderbook_svg(audit)}
          <p class="plain-summary"><b>Lecture métier.</b> {order_count} lignes représentent {_compact(quantity)} kg planifiés chez {supplier_count} fournisseurs. Les réceptions physiques sont prévues entre J{physical_min} et J{physical_max}. Le moteur place la disponibilité entre J{usable_min} et J{usable_max}; faute de définition vérifiable dans la source, ce décalage physique-vers-disponible est un paramètre du modèle à valider, pas un délai qualité observé. Ces dates ne prouvent ni des réceptions réelles ni une performance OTIF.</p>
        </article>'''
        if audit_available
        else '''<article class="panel pending-panel">
          <div class="panel-title"><div><span class="eyebrow evidence-gap">DONNÉE OBSERVÉE NON FOURNIE</span><h3>Carnet ouvert du composant 021081</h3></div><span class="status status-unavailable">Non disponible</span></div>
          <p class="plain-summary"><b>Carnet 021081 non fourni à cette page ; aucun nombre observé n'est affiché.</b> Les lignes, quantités, fournisseurs et dates restent masqués jusqu'à réception d'un audit source complet.</p>
        </article>'''
    )
    graph_link_cards = [
        _link_card("Analyse de sensibilité détaillée", "courbes et hypothèses par mécanisme", links.get("sensitivity")),
    ]
    if links.get("component_021081"):
        graph_link_cards.append(
            _link_card(
                (
                    f"Rejeu détaillé des {order_count} lignes planifiées 021081"
                    if audit_available
                    else "Rejeu détaillé des lignes planifiées 021081"
                ),
                "avant-après, limites et causalité simulée",
                links.get("component_021081"),
            )
        )
    graph_link_cards.extend(
        [
            _link_card("Parcours incidents et lots", "les trois vues de démonstration", links.get("three_views")),
            _link_card("Carte complète du réseau", "navigation sur tous les nœuds et flux", links.get("map")),
        ]
    )
    graph_links = "".join(graph_link_cards)
    action_sections = (
        _action_audit_block(data) + _decision_conditions_block()
        if include_action_sections
        else ""
    )
    return f'''
    <section id="view-lots" class="view" aria-labelledby="tab-lots" hidden>
      <header class="view-head"><div><span class="view-number">3</span><p class="kicker">Commandes, lots et causalité</p><h2>Ce que le modèle relie, et ce qu'il reste à vérifier</h2></div></header>
      <article class="panel chain-panel">
        <div class="panel-title"><div><span class="eyebrow evidence-observed">CHAÎNE CIBLE</span><h3>021081 → 773474 → 268967</h3></div></div>
        <svg class="chain-svg" viewBox="0 0 930 170" role="img" aria-label="Les fournisseurs alimentent le composant 021081, puis 773474 et le produit 268967">
          <title>Chaîne physique du composant 021081 au produit 268967</title>
          <defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7d93"/></marker></defs>
          <g class="node suppliers"><rect x="20" y="25" width="180" height="120" rx="18"/><text x="110" y="64" text-anchor="middle">{supplier_count_label} fournisseurs</text><text x="110" y="89" text-anchor="middle">{order_count_label} lignes ouvertes</text><text x="110" y="114" text-anchor="middle">{quantity_label}</text></g>
          <line x1="205" x2="290" y1="85" y2="85" marker-end="url(#arrow)"/>
          <g class="node component"><rect x="300" y="43" width="155" height="84" rx="18"/><text x="377" y="79" text-anchor="middle">Composant</text><text x="377" y="104" text-anchor="middle">021081</text></g>
          <line x1="460" x2="540" y1="85" y2="85" marker-end="url(#arrow)"/>
          <g class="node intermediate"><rect x="550" y="43" width="155" height="84" rx="18"/><text x="627" y="79" text-anchor="middle">Intermédiaire</text><text x="627" y="104" text-anchor="middle">773474</text></g>
          <line x1="710" x2="785" y1="85" y2="85" marker-end="url(#arrow)"/>
          <g class="node product"><rect x="795" y="43" width="115" height="84" rx="18"/><text x="852" y="79" text-anchor="middle">Produit</text><text x="852" y="104" text-anchor="middle">268967</text></g>
        </svg>
        <p class="plain-summary"><b>Ce que le modèle sait relier.</b> Le moteur conserve l'identité fournisseur et la ligne ERP source, puis reconstruit les descendants simulés jusqu'aux consommations aval. C'est une <b>exposition généalogique</b> : elle indique quels lots partagent une chaîne avec la réception. Un lot exposé n'est pas nécessairement modifié par l'incident. Pour conclure à un effet causal, il faut constater un écart entre les scénarios sans et avec incident partis du même état initial. La ligne technique ne devient jamais un numéro de lot industriel réel.</p>
      </article>

      {_frozen_network_lot_block(data)}

      <div class="two-col">
        {orderbook_panel}
        <article class="panel lot-truth">
          <span class="eyebrow evidence-gap">LIMITE DE TRAÇABILITÉ</span><h3>Ce que « lot » veut dire aujourd'hui</h3>
          <div class="truth-row yes"><b>Disponible</b><span>ligne planifiée du snapshot, fournisseur, article, quantité, dates planifiées, réception simulée directement marquée et descendants reconstruits lorsqu'ils existent.</span></div>
          <div class="truth-row no"><b>Manquant</b><span>numéro de commande/ligne métier stable, lot fournisseur, lot de réception, lot qualité, lot de production réel et affectation client.</span></div>
          <p class="plain-summary"><b>Règle de présentation.</b> On peut montrer l'exposition généalogique de <i>lots simulés dérivés des lignes planifiées 2025</i>. La quantité complète d'un descendant est une borne haute d'exposition, jamais la quantité causée, perdue ou retardée. Seule la comparaison des scénarios partis du même état initial mesure l'écart causé par l'incident. Ces lots ne sont pas des lots industriels observés.</p>
          <p class="plain-summary protocol"><b>Retenue qualité.</b> Le rejeu crée aujourd'hui le lot à sa date utilisable. La période de quarantaine est reconstruite à partir des dates et de l'incident; ce n'est pas encore un statut natif du lot au fil du temps.</p>
        </article>
      </div>

      {component_block}

      {action_sections}

      <div class="two-col">
        <article class="panel request-panel">
          <span class="eyebrow evidence-signal">À DEMANDER À L'INDUSTRIEL</span><h3>Le jeu de données qui ferme la boucle</h3>
          <ol class="request-list"><li><b>Commande :</b> fournisseur, article, site, n° commande et ligne, dates demandée, promise initiale, re-promesses, expédition et réception réelle.</li><li><b>Quantité et qualité :</b> commandée, confirmée, reçue, rejetée, statut libre/bloqué/alloué/périmé, motif et date de libération.</li><li><b>Généalogie :</b> lot fournisseur, réception, contrôle qualité, lot 773474, lot 268967, consommations et clients affectés.</li><li><b>Capacité et actions :</b> engagement daté, minimum de commande, calendrier, relance, fractionnement, alternative et coût.</li><li><b>Grille interne fournisseur :</b> criticité achats/qualité, statut d'homologation, incidents, PPM ou rejets, OTIF avec sa définition, audits, dépendance commerciale et plans d'actions — avec historique daté et règles de calcul.</li></ol>
          <p class="plain-summary"><b>Gain immédiat.</b> Ces clés permettent d'apprendre quels incidents sont réellement fréquents, d'attribuer les pertes à leur cause et de comparer la prédiction aux faits.</p>
        </article>
        <article class="panel navigation-panel"><span class="eyebrow">POUR ALLER AU DÉTAIL</span><h3>Ouvrir les vues existantes</h3><div class="link-grid">{graph_links}</div><p class="plain-summary"><b>Criticité fournisseur.</b> Les scores visibles dans certaines vues existantes sont des signaux calculés par le modèle, pas la cotation achats ou qualité interne de l'industriel. Il faut demander sa grille réelle et ses règles de décision avant toute comparaison.</p></article>
      </div>
    </section>'''


CSS = r"""
.network-detail-link{margin-top:12px}.network-detail-link .link-card{border-color:#93b9d8;background:#f4faff}
.meeting-opening{border-top:5px solid var(--coral);background:linear-gradient(145deg,#fff,#fff8f6)}.meeting-chain{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:14px 0;padding:13px 15px;border-radius:12px;background:#eef5fb;color:var(--navy)}.meeting-chain span{color:#7790a8}.meeting-chain b{white-space:nowrap}.meeting-decisions{border-top:5px solid var(--green);background:linear-gradient(145deg,#fff,#f7fcfa)}.decision-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:13px}.decision-grid>div{padding:12px 14px;border:1px solid #cfe1da;border-radius:12px;background:#fff}.decision-grid b,.decision-grid span{display:block}.decision-grid span{margin-top:4px;color:var(--muted);font-size:13px}
.frozen-priority-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:11px;margin-top:14px}.frozen-priority,.frozen-group,.frozen-metric,.frozen-hypothesis{border:1px solid var(--line);border-radius:14px;background:#fbfdff;padding:14px}.frozen-priority{border-top:4px solid var(--green)}.frozen-priority>span{color:var(--green);font-size:11px;font-weight:800;text-transform:uppercase}.frozen-priority h3{font-size:20px}.frozen-priority strong{display:block;color:var(--coral);font-size:21px}.frozen-priority p,.frozen-priority small,.frozen-metric p,.frozen-metric small,.frozen-hypothesis small{display:block;color:var(--muted);font-size:12px}.frozen-group{grid-column:1/-1}.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}.supplier-chip{display:inline-block;background:#e5edf5;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:800}.frozen-metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:13px}.frozen-metric strong{display:block;color:var(--navy);font-size:18px}.frozen-hypothesis-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.frozen-effects table{min-width:850px}.frozen-lot-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.frozen-lot-grid>div{padding:13px;background:#eef5fa;border-radius:12px}.frozen-lot-grid strong,.frozen-lot-grid span{display:block}.frozen-lot-grid strong{font-size:24px;color:var(--navy)}.frozen-lot-grid span{font-size:12px;color:var(--muted)}.frozen-actions .ready-zero{color:var(--coral);font-size:29px;margin-right:5px}.blocked-action{border-left:4px solid var(--amber)!important}.frozen-historical-actions>.action-audit-split{margin-top:13px}.frozen-legacy{border-color:#cad8e5;background:#f8fbfd}
:root{--ink:#102943;--muted:#61738a;--line:#d9e2ec;--bg:#edf3f8;--paper:#fff;--blue:#2877c7;--navy:#173f6d;--coral:#e85f4b;--green:#2f9974;--amber:#c97916;--shadow:0 14px 42px rgba(32,63,94,.10)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.48 Inter,Segoe UI,Arial,sans-serif}button,a{font:inherit}.shell{max-width:1480px;margin:auto;padding:28px 28px 60px}.masthead{background:linear-gradient(120deg,#0f3155,#1e6194);color:#fff;border-radius:26px;padding:30px 34px;box-shadow:var(--shadow)}.masthead-top{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}.masthead h1{font-size:clamp(27px,3vw,44px);line-height:1.08;margin:4px 0 11px;letter-spacing:-.025em}.masthead p{max-width:920px;margin:0;color:#dceaf6;font-size:16px}.date{white-space:nowrap;color:#bcd4e6;font-size:13px}.legend-strip{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}.legend-item{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.22);border-radius:11px;padding:8px 11px;font-size:12px}.legend-item b{color:#fff}.tabs{position:sticky;top:0;z-index:9;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;background:rgba(237,243,248,.94);backdrop-filter:blur(9px);padding:14px 0}.tab{border:1px solid #cdd9e5;background:#fff;color:var(--ink);padding:12px 14px;border-radius:13px;font-weight:700;cursor:pointer}.tab[aria-selected=true]{background:var(--navy);border-color:var(--navy);color:#fff}.view{display:block}.view[hidden]{display:none}.view-head{display:flex;justify-content:space-between;gap:22px;align-items:center;margin:22px 0 15px}.view-head>div:first-child{position:relative;padding-left:61px}.view-number{position:absolute;left:0;top:2px;display:grid;place-items:center;width:45px;height:45px;border-radius:14px;background:#dbe9f6;color:var(--navy);font-size:21px;font-weight:800}.kicker{color:var(--blue);text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-size:11px;margin:0}.view-head h2{font-size:clamp(24px,2.5vw,35px);line-height:1.15;margin:1px 0}.status{display:inline-flex;align-items:center;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:800;white-space:nowrap}.status-complete,.status-scope_audited,.status-priorites_simulees_stabilisees_30{background:#ddf5e9;color:#176344}.status-in_progress,.status-preselection,.status-exploratory_complete{background:#fff0cf;color:#825200}.status-groupe_prioritaire{background:#e7f0fa;color:#285b86}.status-not_concluded,.status-unavailable{background:#f6e5e2;color:#88372d}.hero-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:13px}.hero-grid.four{grid-template-columns:repeat(4,1fr)}.hero-card{background:var(--paper);border:1px solid var(--line);border-top:4px solid var(--blue);border-radius:17px;padding:17px 19px;box-shadow:0 7px 23px rgba(32,63,94,.06)}.hero-card.coral{border-top-color:var(--coral)}.hero-card.navy{border-top-color:var(--navy)}.hero-card.green{border-top-color:var(--green)}.hero-card.gray{border-top-color:#9daabc}.hero-card strong{display:block;font-size:31px;line-height:1.15;margin:6px 0 1px}.hero-card>span:last-child{color:var(--muted)}.eyebrow{display:inline-block;color:#496278;font-size:10px;font-weight:850;letter-spacing:.11em;text-transform:uppercase}.evidence-observed{color:#17618f}.evidence-projected{color:#9a6411}.evidence-simulated{color:#8d3f76}.evidence-hypothesis{color:#a24927}.evidence-signal{color:#1f7557}.evidence-gap{color:#a24236}.plain-summary{margin:13px 0 0;background:#f2f6fa;border-left:4px solid #8da7c0;border-radius:7px;padding:11px 13px;color:#344d65}.plain-summary b{color:var(--ink)}.two-col{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.8fr);gap:15px;margin-top:15px}.two-col.lower{grid-template-columns:1fr 1fr}.panel{background:var(--paper);border:1px solid var(--line);border-radius:19px;padding:19px 21px;box-shadow:0 8px 27px rgba(32,63,94,.06);margin-top:15px;overflow:hidden}.two-col>.panel{margin-top:0}.panel h3,.metric-card h3{margin:4px 0 8px;font-size:19px;line-height:1.22}.panel-title{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}.mini-note{font-size:12px;color:var(--muted);white-space:nowrap}.chart{display:block;width:100%;height:auto;margin:8px 0 2px}.grid{stroke:#dce5ee;stroke-width:1}.axis-line{stroke:#a9b9c9;stroke-width:1}.axis,.legend{font-size:11px;fill:#63758b}.label{font-size:12px;fill:#2c4359;font-weight:650}.bar-value{font-size:14px;fill:#fff;font-weight:800}.bar-text{font-size:12px;fill:#334b62;font-weight:700}.card-stack{display:grid;gap:12px}.card-stack.horizontal{grid-template-columns:repeat(2,1fr);margin-top:10px}.metric-card{background:#fff;border:1px solid var(--line);border-radius:17px;padding:16px 17px}.metric-card strong{display:block;color:var(--navy);font-size:27px;line-height:1.15}.metric-card>span:not(.eyebrow){color:var(--muted)}.metric-card p{margin:9px 0 0;color:#435b71;font-size:13px}.compact-panel{padding:20px}.reading-list{padding-left:19px;margin:10px 0}.reading-list li{margin:7px 0}.warning-panel{border-color:#edc9c2;background:#fffaf8}.big-number{display:block;color:var(--coral);font-size:30px;margin-top:7px}.source-panel{background:linear-gradient(145deg,#fff,#f4f9fc)}.source-numbers{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:22px}.source-numbers>div{padding:15px;background:#edf4f8;border-radius:14px}.source-numbers strong{display:block;font-size:30px}.source-numbers span{color:var(--muted);font-size:13px}.pending-panel{border-style:dashed;background:#fffcf6}.minor{font-size:13px;color:var(--muted);margin:12px 0 0}.table-wrap{overflow:auto;margin-top:10px}table{width:100%;border-collapse:collapse}th{text-align:left;background:#edf3f8;color:#415a72;font-size:11px;text-transform:uppercase;letter-spacing:.05em}th,td{padding:11px 10px;border-bottom:1px solid #e2e9f0;vertical-align:top}td{font-size:13px}.chain-svg{display:block;width:100%;max-height:205px}.chain-svg line{stroke:#6b7d93;stroke-width:3}.chain-svg .node rect{stroke-width:2}.chain-svg .node text{fill:#17324e;font-weight:700}.chain-svg .suppliers rect{fill:#e2f0fb;stroke:#2877c7}.chain-svg .component rect{fill:#e9f5ef;stroke:#389475}.chain-svg .intermediate rect{fill:#fff2db;stroke:#d8902e}.chain-svg .product rect{fill:#fde8e4;stroke:#df624e}.lot-truth{background:linear-gradient(150deg,#fff,#f8fafc)}.truth-row{display:grid;grid-template-columns:95px 1fr;gap:12px;padding:13px;margin-top:10px;border-radius:11px}.truth-row.yes{background:#e8f6ef}.truth-row.no{background:#fff0ed}.masking-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:14px}.masking-grid>div{background:#fff;border:1px solid #edd6cf;border-radius:12px;padding:11px}.masking-grid b{display:block;color:#74372d;font-size:17px}.masking-grid span{display:block;color:#5c6f84;font-size:11px;margin-top:4px}.decisions .table-wrap{border:1px solid var(--line);border-radius:13px}.request-list{padding-left:21px}.request-list li{margin:10px 0}.link-grid{display:grid;gap:10px;margin-top:13px}.link-card{display:block;border:1px solid #bfd0df;border-radius:13px;padding:13px;text-decoration:none;color:var(--ink);background:#f7fbfe}.link-card:hover{border-color:var(--blue);transform:translateY(-1px)}.link-card span{display:flex;justify-content:space-between;font-weight:800}.link-card small{display:block;color:var(--muted);margin-top:3px}.link-card.disabled{opacity:.58}.action-audit-split{display:grid;grid-template-columns:1.15fr .85fr;gap:15px;margin-top:15px}.action-audit-split>.panel{margin-top:0}.tested-actions{border-top:4px solid #8d3f76}.realistic-actions{border:2px dashed #d79b4a;background:#fffdf8}.audit-intro{color:#435a70;background:#f6eff5;border-radius:11px;padding:10px 12px}.audit-result-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.audit-result{border:1px solid var(--line);border-left:5px solid #7189a3;border-radius:13px;padding:12px;background:#fff}.audit-result.positive{border-left-color:#2f9974}.audit-result.partial{border-left-color:#2877c7}.audit-result.negative{border-left-color:#d04e42;background:#fff9f8}.audit-result.caution{border-left-color:#d18a2c;background:#fffdf8}.audit-result h4,.real-action h4{margin:0 0 7px;font-size:15px}.audit-result p{font-size:12px;color:#4a6074;margin:8px 0 0}.audit-metrics{display:grid;gap:4px}.audit-metrics span{font-size:11px;color:#5c6f84}.audit-metrics b{color:var(--ink)}.real-action-grid{display:grid;gap:9px}.real-action{border:1px solid #ead6b7;background:#fff;border-radius:13px;padding:12px}.real-action p{margin:5px 0 8px;font-size:13px}.real-action small{display:block;color:#596c7f}.real-action em{display:block;margin-top:7px;color:#976019;font-size:11px;font-style:normal;font-weight:700}.footer{margin:20px 0 0;color:#63758a;font-size:12px;text-align:center}.method-note{background:#fff;border:1px solid var(--line);border-radius:15px;padding:13px 16px;margin-top:12px;color:#4a6075}.method-note summary{font-weight:800;cursor:pointer}.method-note p{margin:9px 0 0}
@media(max-width:900px){.shell{padding:15px}.masthead{padding:23px}.masthead-top{display:block}.date{margin-top:10px}.tabs{grid-template-columns:1fr;position:static}.hero-grid,.hero-grid.four,.two-col,.two-col.lower,.card-stack.horizontal,.action-audit-split,.audit-result-grid,.masking-grid,.decision-grid,.frozen-priority-grid,.frozen-metric-grid,.frozen-hypothesis-grid,.frozen-lot-grid{grid-template-columns:1fr}.view-head{align-items:flex-start}.source-numbers{grid-template-columns:1fr}.panel{padding:16px}.chart{min-width:650px}.panel{overflow-x:auto}}
@media print{body{background:#fff}.shell{max-width:none;padding:0}.tabs{display:none}.masthead{box-shadow:none}.view[hidden]{display:block}.view{break-before:page}.view:first-of-type{break-before:auto}.panel,.hero-card{box-shadow:none;break-inside:avoid}.link-card{color:#000}.status{border:1px solid currentColor}}
"""


JAVASCRIPT = r"""
(() => {
  const tabs = [...document.querySelectorAll('.tab')];
  const views = [...document.querySelectorAll('.view')];
  function show(id, focus = false) {
    tabs.forEach(tab => tab.setAttribute('aria-selected', String(tab.dataset.view === id)));
    views.forEach(view => { view.hidden = view.id !== id; view.classList.toggle('active', view.id === id); });
    if (focus) document.getElementById(id)?.focus({preventScroll:true});
    history.replaceState(null, '', '#' + id);
    window.scrollTo({top: document.querySelector('.tabs').offsetTop, behavior: 'smooth'});
  }
  tabs.forEach(tab => tab.addEventListener('click', () => show(tab.dataset.view)));
  const requested = location.hash.slice(1);
  if (views.some(view => view.id === requested)) show(requested);
})();
"""


PRESENTATION_PROFILES = ("assessment", "meeting")


def _meeting_opening_block(
    data: Mapping[str, Any], links: Mapping[str, str | None]
) -> str:
    """Build the first business message of the meeting sequence.

    The focused 338929 result remains a conditional simulation.  The helper
    deliberately prefers the new network confirmation when it is available
    and otherwise falls back to the older, explicitly exploratory service
    landscape.
    """

    network_rows = [
        row
        for row in data["network"].get("ranking", [])
        if data["network"].get("state") == NETWORK_STABILIZED_STATE
        and _supplier_label(row.get("supplier_id")) == "VD0914360C"
        and str(row.get("worst_item_id") or "").replace("item:", "") == "338929"
        and str(row.get("worst_dst_node_id") or "").replace("facility:", "")
        == "M-1810"
        and str(row.get("worst_target_product_id") or "") == "268091"
        and str(row.get("worst_service_delta") or "").strip()
    ]
    network_row = min(
        network_rows,
        key=lambda row: _integer(row.get("supplier_sensitivity_rank"), 999),
        default={},
    )
    service_rows = [
        row
        for row in data["service"].get("worst_cases", [])
        if data["service"].get("state") == "complete"
        and str(row.get("chain_id") or "") == "338929_m1810_268091"
        and _integer(row.get("n_seeds")) > 0
        and str(row.get("product_on_due_date_proxy_mean") or "").strip()
    ]
    service_row = min(
        service_rows,
        key=lambda row: _number(row.get("product_on_due_date_proxy_mean"), 1.0),
        default={},
    )
    if network_row:
        result = (
            f"baisse moyenne de {_points(network_row.get('worst_service_delta'))} "
            "du volume de 268091 servi à la date attendue"
        )
        evidence = (
            "résultat simulé stabilisé dans le protocole réseau — "
            "30 répétitions simulées comparables"
        )
    elif service_row:
        result = (
            f"{_percent(service_row.get('product_on_due_date_proxy_mean'))} de la "
            "demande servie à la date attendue dans l'état testé"
        )
        evidence = (
            "ancienne étude ciblée exploratoire, distincte du classement réseau final — "
            f"{_integer(service_row.get('n_seeds'))} répétitions simulées"
        )
    else:
        result = "résultat chiffré masqué jusqu'à la fermeture des calculs"
        evidence = "calcul en cours — résultat chiffré masqué"
    detail_link = (
        _link_card(
            "Ouvrir le détail 338929 : exposition et effets causaux",
            "carte, exposition généalogique et écarts causaux dans une page séparée",
            links.get("network_risk"),
        )
        if links.get("network_risk")
        else ""
    )
    return f'''<article class="panel meeting-opening">
      <div class="panel-title"><div><span class="eyebrow evidence-hypothesis">HYPOTHÈSE D'INCIDENT</span><h3>338929 : un retard fournisseur atteint-il 268091 ?</h3></div><span class="mini-note">{html.escape(evidence)}</span></div>
      <div class="meeting-chain"><b>SDC-VD0914360C</b><span>→</span><b>338929</b><span>→</span><b>M-1810</b><span>→</span><b>268091</b><span>→</span><b>client</b></div>
      <p class="plain-summary"><b>Résultat du modèle.</b> {html.escape(result)}. Cela montre une sensibilité physique si le retard testé survient; cela ne mesure ni sa probabilité, ni l'OTIF réel du fournisseur.</p>
      {detail_link}
    </article>'''


def _meeting_decision_block(data: Mapping[str, Any]) -> str:
    """Keep the third view action-oriented without asserting recommendations."""

    if _has_frozen_network(data):
        candidate_cards = "".join(
            f'''<div class="blocked-action"><b>{html.escape(label)}</b><span>Bloquée pour recommandation : disponibilité, délai, capacité, coût et statut qualité restent à prouver sur le dossier concerné.</span></div>'''
            for label in network_results.ACTION_LABELS.values()
        )
        return f'''<article class="panel meeting-decisions frozen-actions">
          <div class="panel-title"><div><span class="eyebrow evidence-signal">ACTIONS CANDIDATES</span><h3><span class="ready-zero">0</span> action prête à recommander</h3></div><span class="status status-not_concluded">4 candidates bloquées</span></div>
          <p class="plain-summary"><b>« Bloquée » ne veut pas dire impossible.</b> Cela signifie que le paquet actuel ne démontre ni l'efficacité de l'action sur les 18 voies, ni sa disponibilité opérationnelle. Les essais complémentaires ne couvrent que 3 voies sur 18.</p>
          <p class="plain-summary"><b>Aucun des quatre leviers ci-dessous n'a été simulé dans la campagne réseau finale, pas même sur les trois voies approfondies.</b> Les chiffres de l'ancien audit concernent uniquement deux cascades séparées et ne mesurent pas l'efficacité de ces leviers sur les dossiers affichés.</p>
          <div class="decision-grid">{candidate_cards}</div>
          <p class="plain-summary"><b>Prochaine décision utile.</b> Pour chaque dossier fournisseur choisi, confirmer que l'action existe réellement, puis comparer dans le modèle le fonctionnement normal, l'incident sans action et l'incident avec cette action. Sans cette preuve appariée et la validation des équipes, aucune sélection ni recommandation n'est publiée.</p>
        </article>'''

    return '''<article class="panel meeting-decisions">
      <div class="panel-title"><div><span class="eyebrow evidence-hypothesis">HYPOTHÈSES D'ACTION</span><h3>Quatre familles d'actions à vérifier</h3></div><span class="mini-note">aucune action validée ici</span></div>
      <div class="decision-grid">
        <div><b>Transport ciblé</b><span>Après un retard observé, sur une expédition nommée, avec capacité, jours gagnés et coût confirmés.</span></div>
        <div><b>Stock libre préparé</b><span>Présent et libéré avant l'incident, avec quantité, unité, durée de vie et financement validés.</span></div>
        <div><b>Transport après libération qualité</b><span>Accélérer le transport du lot seulement après la décision qualité; ne jamais raccourcir artificiellement la quarantaine.</span></div>
        <div><b>Source alternative prête</b><span>Déjà active, qualifiée, approuvée et dotée d'une capacité réellement engagée.</span></div>
      </div>
      <p class="plain-summary"><b>Décision attendue au rendez-vous.</b> Choisir les preuves, les responsables et les dossiers fournisseurs sur lesquels tester ces familles d'actions. Après clôture de l'analyse réseau, chacune devra être simulée sur le cas concerné puis vérifiée avec les équipes. Sans ces preuves, ce ne sont pas des recommandations.</p>
    </article>'''


def _meeting_historical_action_details(data: Mapping[str, Any]) -> str:
    """Move old cascade experiments away from the frozen action decision."""

    if not _has_frozen_network(data):
        return ""
    block = _action_audit_block(data)
    if not block:
        return ""
    return f'''<details class="method-note frozen-historical-actions">
      <summary>Ancien audit simulé — séparé du choix final</summary>
      <p>Ces anciens essais sur deux cascades restent utiles pour comprendre le comportement du modèle, mais ils ne sélectionnent aucune action pour l'analyse réseau finale. Leurs coûts sont des indices sans unité monétaire, non comparables aux valeurs 2025.</p>
      {block}
    </details>'''


def _prepare_meeting_section(
    section: str,
    *,
    section_id: str,
    original_number: int,
    meeting_number: int,
    active: bool,
    opening_block: str = "",
) -> str:
    """Relabel and reorder one already-rendered section without changing it."""

    original_open = (
        f'<section id="{section_id}" class="view active"'
        if section_id == "view-observed"
        else f'<section id="{section_id}" class="view"'
    )
    replacement_open = (
        f'<section id="{section_id}" class="view active"'
        if active
        else f'<section id="{section_id}" class="view"'
    )
    section = section.replace(original_open, replacement_open, 1)
    if active:
        section = section.replace(" hidden>", ">", 1)
    elif " hidden>" not in section.split("</header>", 1)[0]:
        section = section.replace(
            f'<section id="{section_id}" class="view"',
            f'<section id="{section_id}" class="view" hidden',
            1,
        )
    section = section.replace(
        f'<span class="view-number">{original_number}</span>',
        f'<span class="view-number">{meeting_number}</span>',
        1,
    )
    if opening_block:
        section = section.replace("</header>", "</header>" + opening_block, 1)
    return section


def render_industrial_supply_bilan(
    data: Mapping[str, Any],
    *,
    links: Mapping[str, str | None] | None = None,
    generated_label: str = "2 septembre 2026",
    presentation_profile: str = "assessment",
) -> str:
    if presentation_profile not in PRESENTATION_PROFILES:
        raise ValueError(
            f"Unknown presentation profile {presentation_profile!r}; "
            f"expected one of {PRESENTATION_PROFILES}"
        )
    links = links or {}
    observed_status = "validé" if _truthy(data["observed"]["manifest"].get("all_validation_checks_pass")) else "à contrôler"
    scope_status = str(data["scope"]["manifest"].get("status") or "non renseigné")
    frozen_meeting = presentation_profile == "meeting" and _has_frozen_network(data)
    observed_section = _view_observed(data)
    vulnerability_section = (
        _view_frozen_network_meeting(data, links)
        if frozen_meeting
        else _view_vulnerability(data, links)
    )
    lots_section = _view_lots(
        data,
        links,
        include_action_sections=not frozen_meeting,
    )
    if presentation_profile == "meeting":
        if not frozen_meeting:
            vulnerability_section = _prepare_meeting_section(
                vulnerability_section,
                section_id="view-vulnerability",
                original_number=2,
                meeting_number=1,
                active=True,
                opening_block=_meeting_opening_block(data, links),
            )
        lots_section = _prepare_meeting_section(
            lots_section,
            section_id="view-lots",
            original_number=3,
            meeting_number=2,
            active=False,
        )
        observed_section = _prepare_meeting_section(
            observed_section,
            section_id="view-observed",
            original_number=1,
            meeting_number=3,
            active=False,
            opening_block=(
                _meeting_decision_block(data)
                + _meeting_historical_action_details(data)
            ),
        )
        title = "Du risque fournisseur aux lots et à la décision"
        if frozen_meeting:
            subtitle = (
                "Trois vues pour le rendez-vous : priorités conditionnelles du réseau, "
                "effets sur les lots et la qualité, puis actions à instruire et faits 2025."
            )
            tabs = '''<button id="tab-vulnerability" class="tab" data-view="view-vulnerability" aria-selected="true">1 · Priorités réseau conditionnelles</button><button id="tab-lots" class="tab" data-view="view-lots" aria-selected="false">2 · Lots et cascade qualité</button><button id="tab-observed" class="tab" data-view="view-observed" aria-selected="false">3 · Actions et bilan 2025</button>'''
        else:
            subtitle = (
                "Trois vues pour le rendez-vous : sensibilité conditionnelle au retard 338929, "
                "cascade qualité 021081 simulée, puis faits 2025 et actions à vérifier."
            )
            tabs = '''<button id="tab-vulnerability" class="tab" data-view="view-vulnerability" aria-selected="true">1 · Retard 338929 et réseau</button><button id="tab-lots" class="tab" data-view="view-lots" aria-selected="false">2 · Cascade qualité simulée et lots</button><button id="tab-observed" class="tab" data-view="view-observed" aria-selected="false">3 · Décisions et bilan 2025</button>'''
        sections = vulnerability_section + lots_section + observed_section
    else:
        title = "Bilan supply : ce que l'on sait, ce qui fragilise, quoi décider"
        subtitle = (
            "Une lecture unique des données 2025, des scénarios physiques et de la "
            "traçabilité lots — sans confondre faits, projections et hypothèses."
        )
        tabs = '''<button id="tab-observed" class="tab" data-view="view-observed" aria-selected="true">1 · Données 2025</button><button id="tab-vulnerability" class="tab" data-view="view-vulnerability" aria-selected="false">2 · Vulnérabilités</button><button id="tab-lots" class="tab" data-view="view-lots" aria-selected="false">3 · Lots et décisions</button>'''
        sections = observed_section + vulnerability_section + lots_section
    document = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bilan supply industriel — données, vulnérabilités et décisions</title><style>{CSS}</style></head>
<body><main class="shell">
  <header class="masthead"><div class="masthead-top"><div><p class="kicker">Préparation du rendez-vous industriel</p><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div><span class="date">Généré le {html.escape(generated_label)}</span></div>
    <div class="legend-strip"><span class="legend-item"><b>OBSERVÉ</b> = présent dans un fichier industriel 2025</span><span class="legend-item"><b>PROJETÉ</b> = alerte d'une photo du planning</span><span class="legend-item"><b>SIMULÉ</b> = réponse calculée à un scénario</span><span class="legend-item"><b>HYPOTHÈSE</b> = incident, état ou action à valider</span><span class="legend-item"><b>SIGNAL DE PRIORITÉ</b> = dossier à vérifier d'abord; il ne prédit pas un incident</span></div>
  </header>
  <nav class="tabs" aria-label="Trois vues du bilan">{tabs}</nav>
  {sections}
  <details class="method-note"><summary>Périmètre et règle de vérité</summary><p>Bilan observé : {observed_status}. Audit de couverture réseau : {html.escape(scope_status)}. Les campagnes facultatives incomplètes sont signalées et leurs résultats partiels ne sont pas utilisés pour conclure. Aucun score composite ni fréquence d'incident n'est inventé.</p></details>
  <footer class="footer">Page autonome : styles, graphiques et valeurs sont embarqués; aucune connexion n'est requise.</footer>
</main><script>{JAVASCRIPT}</script></body></html>'''
    encoded = document.encode("utf-8")
    if len(encoded) >= MAX_HTML_BYTES:
        raise ValueError(f"Generated HTML is {len(encoded)} bytes; limit is {MAX_HTML_BYTES}")
    return document


def build_industrial_supply_bilan_dashboard(
    *,
    observed_dir: Path,
    scope_dir: Path,
    service_landscape_dir: Path,
    output_html: Path,
    component_021081_dir: Path | None = None,
    network_screen_dir: Path | None = None,
    network_priority_boundary_audit_dir: Path | None = None,
    network_action_selection_dir: Path | None = None,
    action_audit_dir: Path | None = None,
    supplier_source_audit_dir: Path | None = None,
    sensitivity_html: Path | None = None,
    component_021081_html: Path | None = None,
    network_risk_html: Path | None = None,
    three_views_html: Path | None = None,
    network_map_html: Path | None = None,
    presentation_profile: str = "assessment",
    force: bool = False,
) -> dict[str, Any]:
    if output_html.exists() and not force:
        raise FileExistsError(f"Refusing to replace existing dashboard without --force: {output_html}")
    data = load_industrial_supply_bilan_inputs(
        observed_dir=observed_dir,
        scope_dir=scope_dir,
        service_landscape_dir=service_landscape_dir,
        component_021081_dir=component_021081_dir,
        network_screen_dir=network_screen_dir,
        network_priority_boundary_audit_dir=network_priority_boundary_audit_dir,
        network_action_selection_dir=network_action_selection_dir,
        action_audit_dir=action_audit_dir,
        supplier_source_audit_dir=supplier_source_audit_dir,
    )
    links = {
        "sensitivity": _relative_href(output_html, sensitivity_html),
        "component_021081": (
            _relative_href(output_html, component_021081_html)
            if component_021081_html is not None and component_021081_html.is_file()
            else None
        ),
        "network_risk": (
            _relative_href(output_html, network_risk_html)
            if network_risk_html is not None and network_risk_html.is_file()
            else None
        ),
        "three_views": _relative_href(output_html, three_views_html),
        "map": _relative_href(output_html, network_map_html),
    }
    document = render_industrial_supply_bilan(
        data,
        links=links,
        presentation_profile=presentation_profile,
    )
    output_html.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_html.with_name(output_html.name + ".tmp")
    temporary.write_text(document, encoding="utf-8")
    temporary.replace(output_html)
    digest = hashlib.sha256(output_html.read_bytes()).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "output_html": str(output_html.resolve()),
        "size_bytes": output_html.stat().st_size,
        "sha256": digest,
        "input_status": {
            "observed_validation_pass": _truthy(data["observed"]["manifest"].get("all_validation_checks_pass")),
            "scope": str(data["scope"]["manifest"].get("status") or ""),
            "targeted_service": data["service"]["state"],
            "component_021081": data["component_021081"]["state"],
            "network_screen": data["network"]["state"],
            "action_audit": data["action_audit"]["state"],
            "supplier_source_audit": data["supplier_source_audit"]["state"],
            "network_input_status": data["network"].get("input_status"),
            "network_priority_reporting_status": data["network"].get(
                "priority_reporting_status"
            ),
            "global_network_priority_robustness_evaluable": data["network"].get(
                "global_network_priority_robustness_evaluable"
            ),
            "network_recovery_metric_status": data["network"].get(
                "network_recovery_metric_status"
            ),
            "actions_ready_count": (
                0 if _has_frozen_network(data) else None
            ),
        },
        "previous_artifacts_mutated": False,
        "external_resources": 0,
        "view_count": 3,
        "presentation_profile": presentation_profile,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed-dir", type=Path, required=True)
    parser.add_argument("--scope-dir", type=Path, required=True)
    parser.add_argument("--service-landscape-dir", type=Path, required=True)
    parser.add_argument("--component-021081-dir", type=Path)
    parser.add_argument("--network-screen-dir", type=Path)
    parser.add_argument("--network-priority-boundary-audit-dir", type=Path)
    parser.add_argument("--network-action-selection-dir", type=Path)
    parser.add_argument("--action-audit-dir", type=Path)
    parser.add_argument("--supplier-source-audit-dir", type=Path)
    parser.add_argument("--sensitivity-html", type=Path)
    parser.add_argument("--component-021081-html", type=Path)
    parser.add_argument("--network-risk-html", type=Path)
    parser.add_argument("--three-views-html", type=Path)
    parser.add_argument("--network-map-html", type=Path)
    parser.add_argument(
        "--presentation-profile",
        choices=PRESENTATION_PROFILES,
        default="assessment",
    )
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_industrial_supply_bilan_dashboard(
        observed_dir=args.observed_dir,
        scope_dir=args.scope_dir,
        service_landscape_dir=args.service_landscape_dir,
        output_html=args.output_html,
        component_021081_dir=args.component_021081_dir,
        network_screen_dir=args.network_screen_dir,
        network_priority_boundary_audit_dir=(
            args.network_priority_boundary_audit_dir
        ),
        network_action_selection_dir=args.network_action_selection_dir,
        action_audit_dir=args.action_audit_dir,
        supplier_source_audit_dir=args.supplier_source_audit_dir,
        sensitivity_html=args.sensitivity_html,
        component_021081_html=args.component_021081_html,
        network_risk_html=args.network_risk_html,
        three_views_html=args.three_views_html,
        network_map_html=args.network_map_html,
        presentation_profile=args.presentation_profile,
        force=args.force,
    )
    manifest_output = args.manifest_output
    if manifest_output:
        if manifest_output.exists() and not args.force:
            raise FileExistsError(f"Refusing to replace manifest without --force: {manifest_output}")
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        manifest_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
