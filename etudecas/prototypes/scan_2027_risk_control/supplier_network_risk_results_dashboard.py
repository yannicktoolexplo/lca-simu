#!/usr/bin/env python3
"""Build a light, standalone dashboard from the final supplier-network study.

The document is deliberately self-contained: every displayed result is copied
into the HTML at build time.  It never turns a conditional stress consequence
into an observed supplier probability or an industrial criticality score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_extension_interpretation_audit as extension_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_priority_boundary_audit as boundary_contract,
)


SCHEMA_VERSION = "etudecas.supplier_network_risk_results_dashboard.v1"
EXPECTED_BOUNDARY_BUILDER_SHA256 = (
    "066e6a9046c17325b068641d9803d3857618168cbaa3439732972a41b1bb7f15"
)
EXPECTED_EXTENSION_BUILDER_SHA256 = (
    "173febfc8eacda3af23088f1a3aacd75fdcb3e50884a758c60ea684e229a7c17"
)
MECHANISMS = {
    "transport_delay": "Retard d'expédition ou de transport",
    "supply_availability": "Disponibilité temporairement réduite",
    "quality_hold": "Retenue qualité",
    "quality_yield": "Quantité conforme réduite",
}
EXTENSIONS = {
    "multi_lane_supplier_common_cause": (
        "Incident simultané chez un même fournisseur",
        "multi_lane_supplier_common_cause_summary.csv",
        "multi_lane_supplier_common_cause_manifest.json",
    ),
    "temporal_robustness": (
        "Même incident à plusieurs dates",
        "temporal_robustness_summary.csv",
        "temporal_robustness_manifest.json",
    ),
    "priority_four_business_causes": (
        "Quatre causes métier sur les voies prioritaires",
        "priority_four_business_causes_summary.csv",
        "priority_four_business_causes_manifest.json",
    ),
}
ACTION_LABELS = {
    "future_lane_transport_reduction": (
        "Réduction programmée de 7 jours du délai futur de la voie"
    ),
    "prepositioned_free_stock_14d": (
        "Stock libre prépositionné avant l'incident — couverture de 14 jours"
    ),
    "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d": (
        "Réduction programmée de 7 jours du délai de la voie dans le scénario qualité"
    ),
    "explicit_counterfactual_alternative_source": (
        "Source alternative explicitement qualifiée et capacitaire — actuellement absente"
    ),
}
TECHNICAL_KEY_LABELS = {
    "shipment": "Expédition simulée",
    "production_campaign": "Campagne simulée",
    "source": "Source technique simulée",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui", "pass"}


def _explicit_false(value: object) -> bool:
    if isinstance(value, bool):
        return not value
    return str(value or "").strip().lower() in {"0", "false", "no", "non"}


def _float(value: object, default: float = 0.0) -> float:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _required_number(row: Mapping[str, object], field: str, context: str) -> float:
    raw = row.get(field)
    try:
        result = float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Valeur numérique {field!r} absente ou invalide ({context})."
        ) from exc
    if not math.isfinite(result):
        raise ValueError(f"Valeur numérique {field!r} non finie ({context}).")
    return result


def _int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _fr(value: object, digits: int = 0) -> str:
    number = _float(value)
    rendered = f"{number:,.{digits}f}"
    return rendered.replace(",", "\u202f").replace(".", ",")


def _signed_points(value: object, digits: int = 1) -> str:
    amount = _float(value) * 100.0
    sign = "+" if amount > 1e-12 else ""
    return f"{sign}{_fr(amount, digits)} points de pourcentage"


def _mechanism(value: object) -> str:
    key = str(value or "")
    return MECHANISMS.get(key, key.replace("_", " ") or "Non renseigné")


def _technical_key(value: object) -> str:
    key = str(value or "")
    return TECHNICAL_KEY_LABELS.get(key, key.replace("_", " ") or "Non renseignée")


def _strip_item(value: object) -> str:
    return str(value or "").removeprefix("item:")


def _relative_href(output: Path, target: Path | None) -> str | None:
    if target is None or not target.is_file():
        return None
    import os

    return Path(os.path.relpath(target.resolve(), output.parent.resolve())).as_posix()


def _validate_frozen_contract_modules() -> None:
    if _sha256(Path(boundary_contract.__file__).resolve()) != (
        EXPECTED_BOUNDARY_BUILDER_SHA256
    ):
        raise ValueError("Le contrat figé d'audit de frontière a changé.")
    if _sha256(Path(extension_contract.__file__).resolve()) != (
        EXPECTED_EXTENSION_BUILDER_SHA256
    ):
        raise ValueError("Le contrat figé d'audit des extensions a changé.")


def _validate_embedded_extension_audit(root: Path) -> dict[str, Any]:
    overlay_validation = extension_contract.validate_scientific_overlay(root)
    overlay_manifest = _read_json(root / "scientific_overlay_manifest.json")
    if str(overlay_manifest.get("builder_sha256") or "").lower() != (
        EXPECTED_EXTENSION_BUILDER_SHA256
    ):
        raise ValueError("La surcouche n'a pas été produite par le contrat figé.")

    manifest = _read_json(root / "extension_interpretation_audit_manifest.json")
    signature_payload = {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "builder_sha256",
            "source_file_sha256",
            "ledger_case_registry_sha256",
            "artifact_file_sha256",
            "bootstrap_resample_count",
        )
    }
    hashes = dict(manifest.get("artifact_file_sha256") or {})
    if (
        str(manifest.get("schema_version") or "")
        != extension_contract.MANIFEST_SCHEMA_VERSION
        or str(manifest.get("status") or "") != "complete"
        or str(manifest.get("builder_sha256") or "").lower()
        != EXPECTED_EXTENSION_BUILDER_SHA256
        or _int(manifest.get("bootstrap_resample_count"), -1)
        != extension_contract.BOOTSTRAP_RESAMPLE_COUNT
        or set(hashes) != set(extension_contract.OUTPUT_FILES)
        or str(manifest.get("package_signature") or "")
        != extension_contract._canonical_sha256(signature_payload)
        or str(overlay_manifest.get("source_audit_package_signature") or "")
        != str(manifest.get("package_signature") or "")
    ):
        raise ValueError(
            "Le paquet d'audit des extensions n'est pas signé correctement."
        )
    for name, expected_hash in hashes.items():
        path = root / str(name)
        if not path.is_file() or _sha256(path) != str(expected_hash):
            raise ValueError(f"Empreinte d'audit extension invalide: {name}")

    audit = _read_json(root / "scientific_extension_interpretation_audit.json")
    controls = _read_json(root / "scientific_promotion_controls.json")
    if (
        str(audit.get("schema_version") or "") != extension_contract.SCHEMA_VERSION
        or str(audit.get("status") or "") != "complete"
        or _int((audit.get("bootstrap") or {}).get("resample_count"), -1)
        != extension_contract.BOOTSTRAP_RESAMPLE_COUNT
    ):
        raise ValueError("Résultat scientifique des extensions invalide.")
    if (
        audit.get("scientific_promotion_controls") != controls
        or audit.get("no_opaque_composite_score") is not True
        or controls.get("legacy_aliases_neutralized_in_scientific_controls") is not True
        or controls.get("network_recovery_metric_used_in_any_gate_or_ranking")
        is not False
        or controls.get("industrial_criticality_claimed") is not False
        or controls.get("historical_supplier_probability_estimated") is not False
    ):
        raise ValueError("Les garde-fous scientifiques signés divergent.")
    for field in (
        "global_priority_temporal_robustness_evaluable",
        "global_four_cause_priority_robustness_evaluable",
        "global_network_priority_robustness_evaluable",
        "promotion_allowed",
        "legacy_completion_or_flow_alias_accepted_as_robustness",
    ):
        if controls.get(field) is not False:
            raise ValueError(f"Contrôle scientifique non neutralisé: {field}")
    if (
        controls.get("network_recovery_metric_status")
        != "excluded_invalid_common_window"
        or (audit.get("network_recovery_metric") or {}).get(
            "used_in_any_gate_or_ranking"
        )
        is not False
    ):
        raise ValueError(
            "La mesure réseau de récupération invalide a été réintroduite."
        )

    temporal = _read_csv(root / "temporal_effect_by_lane_window.csv")
    temporal_pairs = _read_csv(root / "temporal_pairwise_difference_audit.csv")
    causes = _read_csv(root / "four_cause_effect_by_lane_cause.csv")
    cause_pairs = _read_csv(root / "four_cause_pairwise_difference_audit.csv")
    expected_metrics = set(extension_contract.METRIC_BY_KEY)
    expected_effect_count = (
        extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT
        * len(extension_contract.CALENDAR_WINDOWS)
        * len(expected_metrics)
    )
    expected_difference_count = (
        extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT
        * math.comb(len(extension_contract.CALENDAR_WINDOWS), 2)
        * len(expected_metrics)
    )
    for label, rows, expected_count in (
        ("temporelle", temporal, expected_effect_count),
        ("comparaisons temporelles", temporal_pairs, expected_difference_count),
        ("causes", causes, expected_effect_count),
        ("comparaisons de causes", cause_pairs, expected_difference_count),
    ):
        if len(rows) != expected_count or any(
            "recovery" in field.lower() for row in rows for field in row
        ):
            raise ValueError(f"Matrice scientifique d'extension invalide: {label}")
    for label, rows in (("temporelle", temporal), ("causes", causes)):
        for row in rows:
            context = f"{label}/{row.get('chain_id') or '?'}"
            count = _int(row.get("paired_seed_count"), -1)
            client_count = _int(row.get("conditional_client_effect_seed_count"), -1)
            production_count = _int(
                row.get("conditional_production_effect_seed_count"), -1
            )
            low = _required_number(row, "effect_ci95_low", context)
            mean = _required_number(row, "effect_mean", context)
            high = _required_number(row, "effect_ci95_high", context)
            if (
                str(row.get("metric") or "") not in expected_metrics
                or count != extension_contract.EXPECTED_PAIRED_SEED_COUNT
                or _int(row.get("count_denominator"), -1) != count
                or not 0 <= client_count <= count
                or not 0 <= production_count <= count
                or not low <= mean <= high
                or _bool(row.get("count_is_probability_or_frequency"))
                or _bool(row.get("historical_occurrence_probability_estimated"))
            ):
                raise ValueError(
                    f"Effet conditionnel d'extension invalide ({context})."
                )
    temporal_keys = {
        (
            _int(row.get("window_index"), -1),
            _int(row.get("selection_slot"), -1),
            str(row.get("metric") or ""),
        )
        for row in temporal
    }
    cause_keys = {
        (
            str(row.get("failure_mode") or ""),
            _int(row.get("selection_slot"), -1),
            str(row.get("metric") or ""),
        )
        for row in causes
    }
    expected_temporal_keys = {
        (window_index, priority_rank, metric)
        for window_index, _start, _end in extension_contract.CALENDAR_WINDOWS
        for priority_rank in range(
            1, extension_contract.EXPECTED_PRIORITY_LANE_COUNT + 1
        )
        for metric in expected_metrics
    }
    expected_cause_keys = {
        (failure_mode, priority_rank, metric)
        for failure_mode in extension_contract.FOUR_CAUSES
        for priority_rank in range(
            1, extension_contract.EXPECTED_PRIORITY_LANE_COUNT + 1
        )
        for metric in expected_metrics
    }
    if temporal_keys != expected_temporal_keys or cause_keys != expected_cause_keys:
        raise ValueError("Une matrice d'extension est incomplète ou dupliquée.")
    for rows in (temporal_pairs, cause_pairs):
        if any(
            _int(row.get("paired_seed_count"), -1)
            != extension_contract.EXPECTED_PAIRED_SEED_COUNT
            for row in rows
        ):
            raise ValueError(
                "Une comparaison d'extension n'est pas appariée sur 30 tirages."
            )
    for label, interpretation in (
        ("temporelle", audit.get("temporal_interpretation")),
        ("quatre causes", audit.get("four_business_cause_interpretation")),
    ):
        if (
            not isinstance(interpretation, Mapping)
            or _int(interpretation.get("follow_up_lane_count"), -1)
            != extension_contract.EXPECTED_PRIORITY_LANE_COUNT
            or _int(interpretation.get("network_lane_count"), -1)
            != extension_contract.EXPECTED_NETWORK_LANE_COUNT
            or interpretation.get("service_nonseparation_group_fully_followed_up")
            is not True
            or interpretation.get("follow_up_group_order_evaluable") is not False
            or interpretation.get("scientific_order_claimed") is not False
            or interpretation.get("slot_order_has_scientific_meaning") is not False
            or interpretation.get("global_network_priority_robustness_evaluable")
            is not False
            or interpretation.get("no_universal_supplier_or_lane_priority_claimed")
            is not True
        ):
            raise ValueError(f"Portée scientifique {label} invalide.")
    return {
        "overlay_validation": overlay_validation,
        "overlay_manifest": overlay_manifest,
        "manifest": manifest,
        "audit": audit,
        "controls": controls,
        "temporal": temporal,
        "temporal_pairs": temporal_pairs,
        "causes": causes,
        "cause_pairs": cause_pairs,
    }


def _validate_priority_boundary_audit(
    boundary_root: Path, *, overlay_root: Path, supplier_ids: set[str]
) -> dict[str, Any]:
    validation = boundary_contract.validate_audit_package(boundary_root)
    manifest = _read_json(boundary_root / "priority_boundary_audit_manifest.json")
    audit = _read_json(boundary_root / "scientific_priority_boundary_audit.json")
    if str(manifest.get("builder_sha256") or "").lower() != (
        EXPECTED_BOUNDARY_BUILDER_SHA256
    ):
        raise ValueError("L'audit de frontière n'utilise pas le contrat figé.")
    overlay_campaign = _read_json(overlay_root / "campaign_manifest.json")
    campaign_signatures = {
        str(overlay_campaign.get("campaign_signature") or ""),
        str(overlay_campaign.get("source_campaign_signature") or ""),
    } - {""}
    if str(audit.get("source_campaign_signature") or "") not in campaign_signatures:
        raise ValueError("L'audit de frontière ne référence pas cette campagne réseau.")
    source_hashes = dict(manifest.get("source_file_sha256") or {})
    ranking_name = "confirmation_supplier_sensitivity_ranking.csv"
    if (
        ranking_name not in source_hashes
        or not (overlay_root / ranking_name).is_file()
        or _sha256(overlay_root / ranking_name) != str(source_hashes[ranking_name])
    ):
        raise ValueError(
            "La frontière et la surcouche ne partagent pas le même classement source."
        )
    if (
        (audit.get("raw_network_recovery_metric") or {}).get(
            "used_in_any_ranking_or_gate"
        )
        is not False
        or audit.get("no_opaque_composite_score") is not True
        or str(audit.get("historical_occurrence_probability") or "") != "not_estimated"
        or audit.get("industrial_supplier_criticality_claimed") is not False
        or audit.get("causal_fusion_performed_or_claimed") is not False
        or audit.get("supplier_wide_common_cause_included_in_ranking") is not False
    ):
        raise ValueError("Les limites scientifiques de la frontière sont invalides.")

    rankings = _read_csv(boundary_root / "supplier_metric_rankings.csv")
    effects = _read_csv(boundary_root / "conditional_effect_seed_counts.csv")
    expected_metrics = set(boundary_contract.METRIC_BY_KEY)
    expected_scopes = {
        boundary_contract.SUPPLIER_ENVELOPE_SCOPE,
        "failure_mode_specific",
    }
    expected_ranking_count = len(supplier_ids) * len(expected_metrics) * 3
    ranking_keys: set[tuple[str, str, str, str]] = set()
    for row in rankings:
        scope = str(row.get("aggregation_scope") or "")
        failure_mode = str(row.get("failure_mode") or "")
        metric = str(row.get("metric_key") or "")
        supplier = str(row.get("supplier_id") or "")
        key = (scope, failure_mode, metric, supplier)
        if (
            scope not in expected_scopes
            or metric not in expected_metrics
            or supplier not in supplier_ids
            or (scope == "failure_mode_specific")
            != (failure_mode in boundary_contract.CONFIRMED_FAILURE_MODES)
            or _int(row.get("paired_seed_count"), -1) != 30
            or _bool(row.get("universal_supplier_criticality_claimed"))
            or str(row.get("historical_occurrence_probability") or "")
            != "not_estimated"
            or key in ranking_keys
        ):
            raise ValueError("Classement métrique de frontière incomplet ou ambigu.")
        _required_number(row, "metric_value", f"frontière/{supplier}/{metric}")
        ranking_keys.add(key)
    if len(rankings) != expected_ranking_count or len(ranking_keys) != (
        expected_ranking_count
    ):
        raise ValueError(
            "Les quatre métriques et les deux familles ne couvrent pas le réseau."
        )

    metric_audits = list(audit.get("metric_priority_audits") or [])
    family_audits = audit.get("failure_mode_specific_metric_priority_audits") or {}
    if (
        {str(row.get("metric_key") or "") for row in metric_audits} != expected_metrics
        or set(family_audits) != set(boundary_contract.CONFIRMED_FAILURE_MODES)
        or any(
            {
                str(row.get("metric_key") or "")
                for row in (payload.get("metric_priority_audits") or [])
            }
            != expected_metrics
            for payload in family_audits.values()
        )
    ):
        raise ValueError(
            "Audits séparés des quatre métriques ou des deux familles absents."
        )
    envelope_audit_by_metric = {
        str(row.get("metric_key") or ""): row for row in metric_audits
    }
    family_audit_by_mode_metric = {
        (failure_mode, str(row.get("metric_key") or "")): row
        for failure_mode, payload in family_audits.items()
        for row in (payload.get("metric_priority_audits") or [])
    }
    grouped_rankings: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
    for row in rankings:
        group_key = (
            str(row.get("aggregation_scope") or ""),
            str(row.get("failure_mode") or ""),
            str(row.get("metric_key") or ""),
        )
        grouped_rankings.setdefault(group_key, []).append(row)
    for (scope, failure_mode, metric), rows in grouped_rankings.items():
        ordered = sorted(
            rows,
            key=lambda row: _int(row.get("descriptive_metric_rank"), 10**6),
        )
        target_audit = (
            envelope_audit_by_metric[metric]
            if scope == boundary_contract.SUPPLIER_ENVELOPE_SCOPE
            else family_audit_by_mode_metric[(failure_mode, metric)]
        )
        released = _bool(target_audit.get("metric_priority_set_release_pass"))
        expected_first_three = [
            str(row.get("supplier_id") or "") for row in ordered[:3]
        ]
        released_ids = [
            str(value)
            for value in (target_audit.get("released_priority_supplier_ids") or [])
        ]
        if (
            [_int(row.get("descriptive_metric_rank"), -1) for row in ordered]
            != list(range(1, len(supplier_ids) + 1))
            or {str(row.get("supplier_id") or "") for row in ordered} != supplier_ids
            or any(
                _bool(row.get("metric_priority_set_release_pass")) != released
                or not _bool(
                    row.get("rank_is_descriptive_identifier_tie_break_not_evidence")
                )
                or not 0 <= _int(row.get("top3_presence_seed_count"), -1) <= 30
                for row in ordered
            )
            or (released and released_ids != expected_first_three)
            or (
                released
                and any(
                    _int(row.get("top3_presence_seed_count"), -1)
                    < boundary_contract.REQUIRED_TOP3_PRESENCE_COUNT
                    for row in ordered[:3]
                )
            )
            or (not released and released_ids)
        ):
            raise ValueError(
                "La conclusion d'une mesure ne correspond pas à son tableau signé."
            )

    expected_effect_count = 36 + len(supplier_ids) * 3
    if len(effects) != expected_effect_count:
        raise ValueError("Comptages conditionnels par graine incomplets.")
    for row in effects:
        count = _int(row.get("paired_seed_count"), -1)
        category_counts = [
            _int(row.get(field), -1)
            for field in (
                "client_effect_seed_count",
                "production_only_effect_seed_count",
                "upstream_absorbed_seed_count",
                "no_measurable_effect_seed_count",
                "inactive_window_seed_count",
            )
        ]
        if (
            count != 30
            or any(not 0 <= value <= count for value in category_counts)
            or str(row.get("historical_occurrence_probability") or "")
            != "not_estimated"
            or "pas_une_probabilite" not in str(row.get("interpretation") or "")
        ):
            raise ValueError(
                "Un comptage par graine est présenté avec une mauvaise portée."
            )

    scenario_effects = [
        row for row in effects if str(row.get("aggregation_level") or "") == "scenario"
    ]
    family_effects = [
        row
        for row in effects
        if str(row.get("aggregation_level") or "") == "supplier_failure_mode_specific"
    ]
    supplier_effects = [
        row
        for row in effects
        if str(row.get("aggregation_level") or "") == "supplier_any_confirmed_scenario"
    ]
    if (
        len(scenario_effects) != 36
        or len({str(row.get("scenario_id") or "") for row in scenario_effects}) != 36
        or len(family_effects) != len(supplier_ids) * 2
        or {
            (
                str(row.get("supplier_id") or ""),
                str(row.get("failure_mode") or ""),
            )
            for row in family_effects
        }
        != {
            (supplier, failure_mode)
            for supplier in supplier_ids
            for failure_mode in boundary_contract.CONFIRMED_FAILURE_MODES
        }
        or len(supplier_effects) != len(supplier_ids)
        or {str(row.get("supplier_id") or "") for row in supplier_effects}
        != supplier_ids
    ):
        raise ValueError("Niveaux de comptage conditionnel incomplets ou dupliqués.")

    envelope_released = _bool(audit.get("envelope_service_priority_set_release_pass"))
    envelope_ids = [
        str(value)
        for value in (audit.get("envelope_service_priority_supplier_ids") or [])
    ]
    service_metric_audit = next(
        row
        for row in metric_audits
        if str(row.get("metric_key")) == "horizon_on_due_service_delta"
    )
    service_released = _bool(
        service_metric_audit.get("metric_priority_set_release_pass")
    )
    service_ids = [
        str(value)
        for value in (service_metric_audit.get("released_priority_supplier_ids") or [])
    ]
    invalid_envelope = bool(
        envelope_released
        and (
            len(envelope_ids) != 3
            or len(set(envelope_ids)) != 3
            or not set(envelope_ids) <= supplier_ids
            or envelope_ids != service_ids
        )
    ) or bool(
        envelope_released != service_released
        or _bool(audit.get("service_priority_set_release_pass")) != envelope_released
        or (not envelope_released and (envelope_ids or service_ids))
    )
    if invalid_envelope:
        raise ValueError("Conclusion de frontière de l'enveloppe incohérente.")
    universal_nonseparation_group = [
        str(value)
        for value in (
            audit.get("priority_group_supplier_ids_if_no_universal_top3") or []
        )
    ]
    service_nonseparation_group = [
        str(value)
        for value in (
            audit.get("envelope_service_nonseparation_group_supplier_ids") or []
        )
    ]
    if not envelope_released and (
        len(service_nonseparation_group)
        != extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT
        or len(service_nonseparation_group) != len(set(service_nonseparation_group))
        or not set(service_nonseparation_group) <= supplier_ids
        or len(universal_nonseparation_group) != len(supplier_ids)
        or set(universal_nonseparation_group) != supplier_ids
    ):
        raise ValueError(
            "Les groupes de non-séparation service et universel sont incohérents."
        )
    return {
        "validation": validation,
        "root": boundary_root,
        "manifest": manifest,
        "audit": audit,
        "rankings": rankings,
        "effects": effects,
        "envelope_released": envelope_released,
        "envelope_supplier_ids": envelope_ids,
        "priority_group_supplier_ids": service_nonseparation_group,
        "universal_nonseparation_group_supplier_ids": universal_nonseparation_group,
    }


def _causal_scientific_release_pass(
    manifest: Mapping[str, Any],
    *,
    controls: Mapping[str, Any],
    causal_interpretation: Mapping[str, Any],
    exposure_rows: Sequence[Mapping[str, object]],
    pair_rows: Sequence[Mapping[str, object]],
    detail_rows: Sequence[Mapping[str, object]],
) -> bool:
    logical = _int(manifest.get("logical_pair_count"), -1)
    evaluated = _int(manifest.get("evaluated_pair_count"), -1)
    matched = _int(manifest.get("unique_matched_technical_key_count"), -1)
    return bool(
        str(manifest.get("schema_version") or "")
        == "etudecas.supplier_network_post_priority_extension_runner.v1"
        and str(manifest.get("extension") or "") == "causal_lot_attribution"
        and str(manifest.get("status") or "") == "complete"
        and str(manifest.get("mode") or "") == "full"
        and manifest.get("release_gate_pass") is False
        and _bool(manifest.get("scientific_execution_integrity_pass"))
        and _bool(manifest.get("causal_lot_attribution_available"))
        and _bool(controls.get("causal_lot_pairing_integrity_pass"))
        and _bool(controls.get("causal_lot_attribution_available"))
        and _bool(causal_interpretation.get("causal_lot_pairing_integrity_pass"))
        and _bool(causal_interpretation.get("causal_lot_attribution_available"))
        and logical > 0
        and evaluated == logical == len(pair_rows)
        and len(exposure_rows) == logical
        and matched > 0
        and matched == len(detail_rows)
        and _bool(manifest.get("all_root_gates_pass"))
        and _bool(manifest.get("all_genealogy_integrity_gates_pass"))
        and _bool(manifest.get("all_pairs_counterfactually_evaluated"))
        and _bool(manifest.get("genealogical_exposure_is_upper_bound"))
        and _bool(manifest.get("quality_hold_quarantine_is_reconstructed_not_native"))
        and _explicit_false(manifest.get("main_ranking_mutated"))
        and _explicit_false(manifest.get("industrial_probability_estimated"))
        and all(
            _bool(row.get("root_gate_pass"))
            and _bool(row.get("genealogy_integrity_pass"))
            and _bool(row.get("paired_counterfactual_evaluated"))
            and _explicit_false(row.get("industrial_lot_number_claimed"))
            for row in pair_rows
        )
        and all(
            _bool(row.get("descendant_quantity_is_upper_bound"))
            and _explicit_false(row.get("causal_delay_or_loss_claimed_from_genealogy"))
            for row in exposure_rows
        )
    )


def _validate_lot_genealogical_detail(
    *,
    exposure_rows: Sequence[Mapping[str, object]],
    detail_rows: Sequence[Mapping[str, object]],
) -> None:
    """Validate the compact, signed inventory rendered for lot drill-down.

    The producer audit already reconstructs the exact breadth-first genealogy
    from the retained engine proofs.  This consumer still checks the fields it
    will publish so a malformed row can never be rendered as an industrial lot
    or as a causal loss.
    """

    summary_by_case = {
        str(row.get("case_id") or "").strip(): row for row in exposure_rows
    }
    if (
        not summary_by_case
        or "" in summary_by_case
        or len(summary_by_case) != len(exposure_rows)
        or not detail_rows
    ):
        raise ValueError("Inventaire détaillé des lots absent ou dupliqué.")

    detail_by_case: dict[str, list[Mapping[str, object]]] = {
        case_id: [] for case_id in summary_by_case
    }
    unique_rows: set[tuple[str, ...]] = set()
    for row in detail_rows:
        case_id = str(row.get("case_id") or "").strip()
        lot_id = str(row.get("lot_id") or "").strip()
        role = str(row.get("exposure_role") or "").strip()
        event_type = str(row.get("event_type") or "").strip()
        uom = str(row.get("uom") or "").strip()
        if case_id not in detail_by_case:
            raise ValueError(f"Lot détaillé hors configuration: {case_id!r}.")
        day = _required_number(row, "day", f"lot {lot_id or '?'}")
        qty = _required_number(row, "qty", f"lot {lot_id or '?'}")
        key = (
            case_id,
            lot_id,
            str(row.get("event_id") or "").strip(),
            event_type,
            str(row.get("node_id") or "").strip(),
            str(row.get("item_id") or "").strip(),
            str(row.get("day") or "").strip(),
            uom,
            str(row.get("shipment_id") or "").strip(),
            str(row.get("production_campaign_id") or "").strip(),
            str(row.get("source_id") or "").strip(),
        )
        summary = summary_by_case[case_id]
        if (
            not lot_id
            or not event_type
            or not uom
            or role
            not in {"risk_tagged_usable_receipt_root", "genealogical_descendant"}
            or day < 0
            or qty < 0
            or key in unique_rows
            or _int(row.get("seed"), -1) != _int(summary.get("seed"), -2)
            or str(row.get("failure_mode") or "")
            != str(summary.get("failure_mode") or "")
            or not _bool(row.get("descendant_quantity_is_exposure_upper_bound"))
            or not _explicit_false(row.get("causal_delay_or_loss_claimed"))
            or not _explicit_false(
                row.get("counterfactual_entity_identity_validated")
            )
            or not _explicit_false(row.get("industrial_lot_number_claimed"))
            or str(row.get("lot_identifier_semantics") or "")
            != "identifiant_technique_simule_pas_numero_lot_industriel"
        ):
            raise ValueError(f"Détail d'exposition lot invalide: {case_id}/{lot_id}.")
        unique_rows.add(key)
        detail_by_case[case_id].append(row)

    for case_id, rows in detail_by_case.items():
        summary = summary_by_case[case_id]
        root_ids = {
            str(row.get("lot_id") or "")
            for row in rows
            if str(row.get("exposure_role") or "")
            == "risk_tagged_usable_receipt_root"
        }
        descendant_ids = {
            str(row.get("lot_id") or "")
            for row in rows
            if str(row.get("exposure_role") or "") == "genealogical_descendant"
        }
        if (
            not rows
            or len(root_ids) != _int(summary.get("root_lot_count"), -1)
            or len(descendant_ids)
            != _int(summary.get("exposed_descendant_lot_count"), -1)
            or len(rows) != _int(summary.get("exposed_row_count"), -1)
        ):
            raise ValueError(
                f"Comptages du détail lot incohérents pour {case_id}."
            )


def load_network_results(
    directory: str | Path,
    *,
    priority_boundary_audit_dir: str | Path | None = None,
    action_selection_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load only the signed scientific overlay and boundary conclusions.

    The inherited campaign flags ``priority_set_stabilized`` and
    ``rank3_rank4_interval_separated`` are intentionally not read here.  The
    old extension ``pass``/``release_gate_pass`` aliases are required to be
    neutralized by the signed overlay before any result is rendered.
    """

    _validate_frozen_contract_modules()
    root = Path(directory).resolve()
    if priority_boundary_audit_dir is None:
        raise ValueError("Le paquet signé d'audit de frontière est requis.")
    boundary_root = Path(priority_boundary_audit_dir).resolve()
    extension = _validate_embedded_extension_audit(root)
    manifest = _read_json(root / "campaign_manifest.json")
    if (
        str(manifest.get("status") or "") != "complete"
        or str(manifest.get("mode") or "") != "full"
        or manifest.get("scientific_interpretation_overlay_applied") is not True
        or manifest.get("legacy_runner_promotion_aliases_neutralized") is not True
        or manifest.get("promotion_allowed") is not False
    ):
        raise ValueError("La surcouche réseau scientifique n'est pas publiable.")
    if (
        str(manifest.get("evidence_class") or "") != "conditional_simulation_hypothesis"
        or str(manifest.get("historical_occurrence_probability") or "")
        != "not_estimated"
        or str(manifest.get("supplier_ranking_meaning") or "")
        != "conditional_model_sensitivity_priority_not_observed_criticality"
    ):
        raise ValueError(
            "Le réseau n'est pas qualifié comme une sensibilité conditionnelle "
            "sans fréquence historique."
        )
    horizon_days = _int(manifest.get("days"), -1)
    confirmation_seed_count = _int(manifest.get("confirmation_seed_count"), -1)
    if horizon_days != 720 or confirmation_seed_count != 30:
        raise ValueError("Le contrat final exige J0–J719 et 30 simulations appariées.")

    ranking = _read_csv(root / "supplier_sensitivity_ranking.csv")
    lanes = _read_csv(root / "lane_sensitivity_ranking.csv")
    modes = _read_csv(root / "failure_mode_sensitivity_summary.csv")
    source_confirmation_ranking = _read_csv(
        root / "confirmation_supplier_sensitivity_ranking.csv"
    )
    if not ranking or not lanes or not modes or not source_confirmation_ranking:
        raise FileNotFoundError(
            "Résultats réseau compacts incomplets dans la surcouche."
        )
    supplier_ids = [str(row.get("supplier_id") or "") for row in ranking]
    lane_ids = [str(row.get("chain_id") or "") for row in lanes]
    supplier_set = set(supplier_ids)
    if (
        len(ranking) != boundary_contract.EXPECTED_SUPPLIER_COUNT
        or len(lanes) != boundary_contract.EXPECTED_ACTIVE_LANE_COUNT
        or any(not value for value in supplier_ids + lane_ids)
        or len(supplier_set) != len(ranking)
        or len(set(lane_ids)) != len(lanes)
        or {str(row.get("supplier_id") or "") for row in lanes} != supplier_set
    ):
        raise ValueError("Périmètre réseau actif incomplet ou dupliqué.")
    expected_stage = "confirmation_30_realisations"
    for row in ranking:
        context = f"fournisseur {row.get('supplier_id') or '?'}"
        delta = _required_number(row, "worst_service_delta", context)
        if (
            not -1.0 <= delta <= 1e-12
            or str(row.get("service_metric_unit") or "")
            != "ratio_and_percentage_points"
            or str(row.get("evidence_stage") or "") != expected_stage
        ):
            raise ValueError(f"Mesure réseau source invalide ({context}).")
    for row in lanes:
        context = f"voie {row.get('chain_id') or '?'}"
        delta = _required_number(row, "worst_service_delta", context)
        if (
            not -1.0 <= delta <= 1e-12
            or str(row.get("service_metric_unit") or "")
            != "ratio_and_percentage_points"
            or str(row.get("evidence_stage") or "") != expected_stage
            or any(
                not str(row.get(field) or "").strip()
                for field in (
                    "supplier_id",
                    "item_id",
                    "dst_node_id",
                    "target_product_id",
                )
            )
        ):
            raise ValueError(f"Voie réseau invalide ({context}).")
    mode_ids = [str(row.get("failure_mode") or "") for row in modes]
    if len(mode_ids) != len(set(mode_ids)) or set(mode_ids) != set(MECHANISMS):
        raise ValueError("Les quatre causes du balayage initial sont incomplètes.")

    boundary = _validate_priority_boundary_audit(
        boundary_root, overlay_root=root, supplier_ids=supplier_set
    )
    extension_audit = extension["audit"]
    priority_lineage = extension_audit.get("priority_selection_lineage") or {}
    follow_up_supplier_ids = [
        str(value) for value in (priority_lineage.get("follow_up_supplier_ids") or [])
    ]
    follow_up_chain_ids = [
        str(value) for value in (priority_lineage.get("follow_up_chain_ids") or [])
    ]
    if (
        sorted(follow_up_supplier_ids)
        != sorted(boundary["priority_group_supplier_ids"])
        or len(follow_up_supplier_ids)
        != extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT
        or len(follow_up_chain_ids)
        != extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT
        or len(set(follow_up_chain_ids)) != len(follow_up_chain_ids)
        or not set(follow_up_chain_ids) <= set(lane_ids)
        or priority_lineage.get("follow_up_group_is_unordered") is not True
        or priority_lineage.get("slot_order_has_scientific_meaning") is not False
        or priority_lineage.get("service_nonseparation_group_fully_followed_up")
        is not True
    ):
        raise ValueError(
            "Le groupe de quatre dossiers approfondis ne correspond pas à la frontière service."
        )
    source_runner_signature = str(extension_audit.get("source_runner_signature") or "")
    if source_runner_signature != str(manifest.get("extension_runner_signature") or ""):
        raise ValueError("L'audit des extensions ne référence pas cette surcouche.")
    plan_signatures = {
        str(_read_json(root / manifest_name).get("plan_signature") or "")
        for _key, (_label, _summary, manifest_name) in EXTENSIONS.items()
    } - {""}
    plan_signatures.add(
        str(
            _read_json(root / "causal_lot_attribution_manifest.json").get(
                "plan_signature"
            )
            or ""
        )
    )
    plan_signatures.discard("")
    if plan_signatures != {str(extension_audit.get("source_plan_signature") or "")}:
        raise ValueError("La signature du plan d'extensions est incohérente.")

    controls = extension["controls"]
    causal_interpretation = extension_audit.get("causal_lot_interpretation") or {}
    causal_manifest = _read_json(root / "causal_lot_attribution_manifest.json")
    lot_exposure = _read_csv(root / "lot_genealogical_exposure_summary.csv")
    lot_genealogical_detail = _read_csv(
        root / "lot_genealogical_exposure_detail.csv"
    )
    causal_pairs = _read_csv(root / "causal_lot_attribution_summary.csv")
    causal_detail = _read_csv(root / "causal_lot_attribution_detail.csv")
    _validate_lot_genealogical_detail(
        exposure_rows=lot_exposure,
        detail_rows=lot_genealogical_detail,
    )
    causal_released = _causal_scientific_release_pass(
        causal_manifest,
        controls=controls,
        causal_interpretation=causal_interpretation,
        exposure_rows=lot_exposure,
        pair_rows=causal_pairs,
        detail_rows=causal_detail,
    )
    if causal_released:
        expected_keys = _int(
            causal_manifest.get("unique_matched_technical_key_count"), -1
        )
        pair_matched = sum(
            _int(row.get("unique_matched_technical_key_count"), -1)
            for row in causal_pairs
        )
        pair_changed = sum(
            _int(row.get("actual_difference_row_count"), -1) for row in causal_pairs
        )
        if expected_keys != len(causal_detail) or pair_matched != expected_keys:
            raise ValueError("Comptages causaux lot par lot incohérents.")
        for row in lot_exposure:
            context = f"exposition {row.get('case_id') or '?'}"
            if (
                _required_number(row, "root_lot_count", context) <= 0
                or _required_number(row, "exposed_descendant_lot_count", context) < 0
                or _required_number(row, "missing_genealogy_lot_count", context) != 0
            ):
                raise ValueError(f"Généalogie invalide ({context}).")
        for row in causal_detail:
            context = f"clé {row.get('technical_key_id') or '?'}"
            values = {
                field: _required_number(row, field, context)
                for field in (
                    "baseline_day",
                    "stress_day",
                    "day_delta",
                    "baseline_qty",
                    "stress_qty",
                    "qty_delta",
                )
            }
            measured = (
                abs(values["day_delta"]) > 1e-12 or abs(values["qty_delta"]) > 1e-12
            )
            if (
                not str(row.get("case_id") or "").strip()
                or _int(row.get("seed"), -1) < 0
                or str(row.get("failure_mode") or "") not in MECHANISMS
                or not str(row.get("technical_key_id") or "").strip()
                or not str(row.get("uom") or "").strip()
                or not math.isclose(
                    values["day_delta"],
                    values["stress_day"] - values["baseline_day"],
                    abs_tol=1e-9,
                )
                or not math.isclose(
                    values["qty_delta"],
                    values["stress_qty"] - values["baseline_qty"],
                    abs_tol=1e-9,
                )
                or not _bool(row.get("pairing_input_sha256_pass"))
                or not _bool(row.get("pairing_j0_state_sha256_pass"))
                or not _explicit_false(row.get("genealogical_exposure_only"))
                or str(row.get("causal_scope") or "")
                != "paired_simulated_counterfactual_not_observed_industrial_causality"
                or _bool(row.get("actual_difference_measured")) != measured
            ):
                raise ValueError(f"Appariement causal invalide ({context}).")
        if (
            sum(_bool(row.get("actual_difference_measured")) for row in causal_detail)
            != pair_changed
        ):
            raise ValueError("Nombre de différences causales incohérent.")

    boundary_rankings = boundary["rankings"]
    envelope_service_rows = sorted(
        (
            row
            for row in boundary_rankings
            if str(row.get("aggregation_scope") or "")
            == boundary_contract.SUPPLIER_ENVELOPE_SCOPE
            and str(row.get("metric_key") or "") == "horizon_on_due_service_delta"
        ),
        key=lambda row: _int(row.get("descriptive_metric_rank"), 10**6),
    )
    priority_by_id = {
        str(row.get("supplier_id") or ""): row for row in envelope_service_rows
    }
    stable_priorities = [
        priority_by_id[supplier] for supplier in boundary["envelope_supplier_ids"]
    ]
    reporting_status = (
        "envelope_service_top3_released"
        if boundary["envelope_released"]
        else "priority_group_only"
    )
    return {
        "root": root,
        "manifest": manifest,
        "ranking": ranking,
        "lanes": lanes,
        "modes": modes,
        "stable_priorities": stable_priorities,
        "priority_group_supplier_ids": boundary["priority_group_supplier_ids"],
        "priority_reporting_status": reporting_status,
        "input_status": "signed_scientific_overlay_and_audits_valid",
        "legacy_priority_flags_ignored": True,
        "legacy_extension_release_aliases_ignored": True,
        "boundary": boundary,
        "extension": extension,
        "extension_repetition_count": extension_contract.EXPECTED_PAIRED_SEED_COUNT,
        "causal_manifest": causal_manifest,
        "causal_released": causal_released,
        "lot_exposure": lot_exposure,
        "lot_genealogical_detail": lot_genealogical_detail,
        "causal_pairs": causal_pairs,
        "causal_detail": causal_detail,
        "actions": {
            "manifest": {},
            "released": False,
            "selected": [],
            "blocked": [],
            "forced_not_promoted": True,
            "input_was_supplied_but_ignored": action_selection_dir is not None,
        },
    }


def _link(label: str, description: str, href: str | None) -> str:
    if href is None:
        return ""
    return (
        f'<a class="link-card" href="{html.escape(href, quote=True)}">'
        f"<b>{html.escape(label)}</b><span>{html.escape(description)}</span></a>"
    )


def _lot_summary(data: Mapping[str, Any]) -> str:
    exposure = data["lot_exposure"]
    causal = data["causal_pairs"]
    root_lots = sum(_int(row.get("root_lot_count")) for row in exposure)
    descendants = sum(_int(row.get("exposed_descendant_lot_count")) for row in exposure)
    matched = sum(_int(row.get("unique_matched_technical_key_count")) for row in causal)
    changed = sum(_int(row.get("actual_difference_row_count")) for row in causal)
    released = bool(data.get("causal_released"))
    exposure_released = _lot_exposure_released(data)
    if not exposure_released:
        return """<p class="warning"><b>Exposition des lots masquée.</b> Les contrôles de traçage et de généalogie ne sont pas tous passés ; aucune quantité ni différence de date n'est publiée.</p>"""
    causal_value = f"{_fr(changed)} / {_fr(matched)}" if released else "Non démontré"
    causal_label = (
        "lignes réellement différentes / appariées dans le modèle"
        if released
        else "attribution causale aux mêmes lots entre les deux simulations"
    )
    return f"""
      <div class="kpis four">
        <article><strong>{_fr(len(exposure))}</strong><span>cas de stress simulés suivis par généalogie</span></article>
        <article><strong>{_fr(root_lots)}</strong><span>occurrences de lots racines reliées au flux stressé</span></article>
        <article><strong>{_fr(descendants)}</strong><span>occurrences de lots descendants exposés — borne haute</span></article>
        <article><strong>{html.escape(causal_value)}</strong><span>{html.escape(causal_label)}</span></article>
      </div>
      <p class="truth"><b>Exposition généalogique contrôlée.</b> Un lot exposé contient une matière passée par la voie stressée. Cela ne prouve pas qu'il a été retardé ou perdu. Les identifiants dynamiques pouvant changer entre les simulations, l'attribution causale lot par lot reste non démontrée.</p>
      <p class="warning"><b>Identifiants simulés :</b> les clés affichées sont des expéditions, campagnes ou sources techniques du moteur. Ce ne sont pas des numéros de lots industriels observés.</p>
    """


def _lot_exposure_released(data: Mapping[str, Any]) -> bool:
    exposure = list(data.get("lot_exposure") or [])
    controls = data["extension"]["controls"]
    return bool(
        _bool(controls.get("causal_lot_execution_integrity_pass"))
        and exposure
        and all(
            _bool(row.get("root_gate_pass"))
            and _bool(row.get("genealogy_integrity_pass"))
            and _bool(row.get("descendant_quantity_is_upper_bound"))
            and _explicit_false(row.get("causal_delay_or_loss_claimed_from_genealogy"))
            for row in exposure
        )
    )


def _lot_quantity_upper_bound(value: object) -> str:
    try:
        quantities = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return "Non disponible"
    if not isinstance(quantities, Mapping) or not quantities:
        return "0"
    return " + ".join(
        f"{_fr(quantity, 2)} {str(unit)}"
        for unit, quantity in sorted(quantities.items(), key=lambda item: str(item[0]))
    )


def _lot_exposure_table(data: Mapping[str, Any]) -> str:
    if not _lot_exposure_released(data):
        return ""
    rows = sorted(
        data["lot_exposure"],
        key=lambda row: (
            str(row.get("failure_mode") or ""),
            str(row.get("case_id") or ""),
            _int(row.get("seed"), -1),
        ),
    )
    body = "".join(
        "<tr>"
        f"<td><b>{html.escape(str(row.get('case_id') or ''))}</b></td>"
        f"<td>{_int(row.get('seed'))}</td>"
        f"<td>{html.escape(_mechanism(row.get('failure_mode')))}</td>"
        f"<td>{_int(row.get('root_lot_count'))}</td>"
        f"<td>{_int(row.get('exposed_descendant_lot_count'))}</td>"
        f"<td>{html.escape(_lot_quantity_upper_bound(row.get('exposed_quantity_upper_bound_by_uom_json')))}</td>"
        "<td>Borne haute d'exposition, pas une perte attribuée</td>"
        "</tr>"
        for row in rows
    )
    return f"""
      <details open><summary>Voir les {len(rows)} configurations avec des lots exposés</summary>
        <div class="table-wrap"><table><thead><tr><th>Configuration</th><th>Simulation</th><th>Cause</th><th>Lots racines</th><th>Lots descendants</th><th>Quantité exposée maximale</th><th>Interprétation</th></tr></thead><tbody>{body}</tbody></table></div>
      </details>
    """


def _lot_genealogy_detail_rows(data: Mapping[str, Any]) -> str:
    rows = sorted(
        data["lot_genealogical_detail"],
        key=lambda row: (
            str(row.get("case_id") or ""),
            _int(row.get("day"), -1),
            _int(row.get("genealogy_depth"), -1),
            str(row.get("lot_id") or ""),
            str(row.get("event_id") or ""),
        ),
    )
    rendered: list[str] = []
    for row in rows:
        role = str(row.get("exposure_role") or "")
        role_label = (
            "Réception utilisable directement reliée à l'incident"
            if role == "risk_tagged_usable_receipt_root"
            else "Lot descendant contenant cette matière"
        )
        depth = str(row.get("genealogy_depth") or "").strip()
        technical_links = " · ".join(
            value
            for value in (
                str(row.get("shipment_id") or "").strip(),
                str(row.get("production_campaign_id") or "").strip(),
                str(row.get("source_id") or "").strip(),
            )
            if value
        )
        rendered.append(
            '<tr class="genealogy-lot-row">'
            f"<td>{html.escape(str(row.get('case_id') or ''))}</td>"
            f"<td>{_int(row.get('seed'))}</td>"
            f"<td>{html.escape(_mechanism(row.get('failure_mode')))}</td>"
            f"<td><b>{html.escape(str(row.get('lot_id') or ''))}</b></td>"
            f"<td>{html.escape(role_label)}</td>"
            f"<td>{html.escape(depth or '0')}</td>"
            f"<td>{_fr(row.get('day'))}</td>"
            f"<td>{html.escape(str(row.get('node_id') or ''))}</td>"
            f"<td>{html.escape(_strip_item(row.get('item_id')))}</td>"
            f"<td>{_fr(row.get('qty'), 2)} {html.escape(str(row.get('uom') or ''))}</td>"
            f"<td>{html.escape(str(row.get('event_type') or ''))}</td>"
            f"<td>{html.escape(technical_links or '—')}</td>"
            "<td>Borne haute d'exposition ; aucun retard ni perte attribué à ce lot</td>"
            "</tr>"
        )
    return "".join(rendered)


def _lot_genealogy_detail_table(data: Mapping[str, Any]) -> str:
    if not _lot_exposure_released(data):
        return ""
    row_count = len(data["lot_genealogical_detail"])
    return f"""
      <details><summary>Explorer les {_fr(row_count)} événements de lots simulés exposés</summary>
        <p class="truth"><b>Comment lire ce tableau :</b> il suit la matière depuis la réception touchée jusqu'aux lots descendants. Une ligne prouve un lien généalogique simulé, pas que le lot a été retardé, perdu ou livré en retard.</p>
        <div class="lot-tools"><label for="genealogy-lot-filter"><b>Rechercher un lot, un article, un nœud ou une configuration</b></label><input id="genealogy-lot-filter" type="search" placeholder="Ex. LOT-, 338929, M-1810"><span class="count" id="genealogy-lot-count">{_fr(row_count)} lignes affichées</span></div>
        <div class="table-wrap"><table id="genealogy-lot-table"><thead><tr><th>Configuration</th><th>Simulation</th><th>Cause</th><th>Lot simulé</th><th>Rôle</th><th>Niveau de descendance</th><th>Jour</th><th>Nœud</th><th>Article</th><th>Quantité</th><th>Événement</th><th>Lien technique</th><th>Interprétation</th></tr></thead><tbody>{_lot_genealogy_detail_rows(data)}</tbody></table></div>
      </details>
    """


def _lot_detail_rows(data: Mapping[str, Any]) -> str:
    rows = data["causal_detail"]
    return "".join(
        '<tr class="lot-row">'
        f"<td>{html.escape(str(row.get('case_id') or ''))}</td>"
        f"<td>{_int(row.get('seed'))}</td>"
        f"<td>{html.escape(_mechanism(row.get('failure_mode')))}</td>"
        f"<td>{html.escape(_technical_key(row.get('technical_key_type')))}</td>"
        f"<td><b>{html.escape(str(row.get('technical_key_id') or ''))}</b></td>"
        f"<td>{html.escape(str(row.get('node_id') or ''))}</td>"
        f"<td>{html.escape(_strip_item(row.get('item_id')))}</td>"
        f"<td>{html.escape(str(row.get('event_type') or ''))}</td>"
        f"<td>{_fr(row.get('baseline_day'))}</td>"
        f"<td>{_fr(row.get('stress_day'))}</td>"
        f"<td><b>{_fr(row.get('day_delta'))} j</b></td>"
        f"<td>{_fr(row.get('qty_delta'), 2)} {html.escape(str(row.get('uom') or ''))}</td>"
        f"<td>{'Oui' if _bool(row.get('actual_difference_measured')) else 'Non'}</td>"
        "</tr>"
        for row in rows
    )


def _lot_delay_svg(rows: Sequence[Mapping[str, object]]) -> str:
    buckets = (
        ("Plus tôt", lambda value: value < 0),
        ("Même jour", lambda value: abs(value) < 1e-12),
        ("+1 à +7 j", lambda value: 1 <= value <= 7),
        ("+8 à +30 j", lambda value: 8 <= value <= 30),
        ("Plus de +30 j", lambda value: value > 30),
    )
    values = [_float(row.get("day_delta")) for row in rows]
    counts = [
        sum(predicate(value) for value in values) for _label, predicate in buckets
    ]
    maximum = max(counts, default=0) or 1
    width, height = 760, 235
    chart_left, chart_width = 145, 540
    parts = [
        f'<svg class="lot-delay-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Répartition des écarts de jour des lignes de lots appariées">'
    ]
    for index, ((label, _predicate), count) in enumerate(
        zip(buckets, counts, strict=True)
    ):
        y = 18 + index * 42
        bar_width = chart_width * count / maximum
        color = "#1f6feb" if index < 2 else "#e44d3a"
        parts.append(
            f'<text x="0" y="{y + 17}" class="svg-label">{html.escape(label)}</text>'
            f'<rect x="{chart_left}" y="{y}" width="{chart_width}" height="24" rx="7" fill="#e8eef4"/>'
            f'<rect x="{chart_left}" y="{y}" width="{bar_width:.2f}" height="24" rx="7" fill="{color}"/>'
            f'<text x="{chart_left + chart_width + 12}" y="{y + 17}" class="svg-value">{count}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


BOUNDARY_METRIC_ORDER = (
    "horizon_on_due_service_delta",
    "worst_rolling_28d_on_due_delta",
    "incremental_backlog_days_per_requested_unit",
    "released_production_shortfall_ratio",
)

EXTENSION_METRIC_ORDER = (
    "horizon_on_due_service_delta",
    "incremental_backlog_days_per_requested_unit",
    "signed_released_production_loss_ratio",
)

HYPOTHESIS_LABELS = {
    "transport_delay": "Décalage de date : retard imposé de 120 jours",
    "supply_availability": "Perte de quantité utile : disponibilité imposée à 50 %",
}


def _scientific_metric_value(metric_key: object, value: object) -> str:
    key = str(metric_key or "")
    number = _float(value)
    if key in {
        "horizon_on_due_service_delta",
        "worst_rolling_28d_on_due_delta",
    }:
        return _signed_points(number, 2)
    if key == "incremental_backlog_days_per_requested_unit":
        sign = "+" if number > 1e-12 else ""
        return f"{sign}{_fr(number, 2)} jours-unités par unité demandée"
    if key in {
        "released_production_shortfall_ratio",
        "signed_released_production_loss_ratio",
    }:
        sign = "+" if number > 1e-12 else ""
        return f"{sign}{_fr(number * 100.0, 2)} % de la production de référence"
    return _fr(number, 3)


def _metric_name(metric_key: object, fallback: object = "") -> str:
    key = str(metric_key or "")
    labels = {
        "horizon_on_due_service_delta": (
            "Variation du service à la date demandée sur J0–J719"
        ),
        "worst_rolling_28d_on_due_delta": (
            "Variation du pire service glissant sur 28 jours"
        ),
        "incremental_backlog_days_per_requested_unit": (
            "Backlog supplémentaire rapporté à la demande"
        ),
        "released_production_shortfall_ratio": (
            "Manque de production libérée rapporté à la référence"
        ),
        "signed_released_production_loss_ratio": (
            "Variation signée de production libérée"
        ),
    }
    return labels.get(key, str(fallback or key).strip())


def _released_supplier_set(metric_audit: Mapping[str, object]) -> set[str]:
    if not _bool(metric_audit.get("metric_priority_set_release_pass")):
        return set()
    return {
        str(value)
        for value in (metric_audit.get("released_priority_supplier_ids") or [])
        if str(value)
    }


def _priority_boundary_section(data: Mapping[str, Any]) -> str:
    stable = list(data["stable_priorities"])
    if stable:
        cards = "".join(
            '<article class="priority-card">'
            "<span>Membre du trio publié</span>"
            f"<h3>{html.escape(str(row.get('supplier_id') or ''))}</h3>"
            f"<p>Voie déterminante : <b>{html.escape(str(row.get('driver_chain_id') or ''))}</b> · "
            f"{html.escape(_mechanism(row.get('driver_failure_mode')))}</p>"
            f"<strong>{html.escape(_scientific_metric_value(row.get('metric_key'), row.get('metric_value')))}</strong>"
            f"<small>Effet conditionnel de l’enveloppe service · présent dans le trio "
            f"{_int(row.get('top3_presence_seed_count'))}/30 simulations appariées.</small>"
            "</article>"
            for row in stable
        )
        heading = "Trio de l’enveloppe service publiable"
        explanation = (
            "Ces trois fournisseurs sont séparés du fournisseur suivant pour la "
            "mesure de service et selon le protocole signé. Leur ordre interne "
            "n’est pas présenté comme démontré."
        )
    else:
        group = list(data["priority_group_supplier_ids"])
        group_badges = "".join(
            f'<span class="supplier-chip">{html.escape(supplier)}</span>'
            for supplier in group
        )
        cards = (
            '<div class="warning"><b>Groupe à instruire, sans trio publié.</b> '
            "L’écart avec le fournisseur suivant n’est pas suffisamment établi "
            "pour isoler trois noms. Aucun rang hérité n’est réutilisé."
            f'<div class="chips">{group_badges}</div></div>'
        )
        heading = "La frontière de priorité n’est pas assez nette"
        explanation = (
            "Le résultat utile est donc un groupe de fournisseurs à examiner, "
            "sans ordre artificiel."
        )
    return f"""
    <section id="priorites"><article class="panel">
      <span class="eyebrow">SIGNAL DE PRIORITÉ SIMULÉ</span>
      <h2>{html.escape(heading)}</h2>
      <p class="lead">{html.escape(explanation)} L’enveloppe retient, pour chaque fournisseur, sa conséquence la plus défavorable parmi une voie unique et deux hypothèses sévères pré-déclarées. Ce n’est ni une note fournisseur observée, ni une causalité commune à toutes les causes.</p>
      <p class="truth"><b>Lecture métier.</b> On répond ici à « si ce stress précis arrive sur cette voie, où le modèle montre-t-il la plus forte conséquence client ? ». On ne répond pas à « quel fournisseur a le plus de chances d’avoir un incident ? ».</p>
      <div class="priority-grid">{cards}</div>
    </article></section>
    """


def _four_metric_sections(data: Mapping[str, Any]) -> str:
    boundary = data["boundary"]
    audits = {
        str(row.get("metric_key") or ""): row
        for row in boundary["audit"].get("metric_priority_audits", [])
    }
    ranking_rows = list(boundary["rankings"])
    sections: list[str] = []
    for metric_key in BOUNDARY_METRIC_ORDER:
        metric_audit = audits[metric_key]
        released = _bool(metric_audit.get("metric_priority_set_release_pass"))
        released_ids = _released_supplier_set(metric_audit)
        status = (
            "Trio séparé du fournisseur suivant"
            if released
            else "Aucun trio publié pour cette mesure"
        )
        badge_class = "pass" if released else "warn"
        rows = sorted(
            (
                row
                for row in ranking_rows
                if str(row.get("aggregation_scope") or "")
                == boundary_contract.SUPPLIER_ENVELOPE_SCOPE
                and str(row.get("metric_key") or "") == metric_key
            ),
            key=lambda row: str(row.get("supplier_id") or ""),
        )
        table_rows = "".join(
            "<tr>"
            f"<td><b>{html.escape(str(row.get('supplier_id') or ''))}</b>"
            + (
                '<span class="mini-pass">dans le trio publié</span>'
                if str(row.get("supplier_id") or "") in released_ids
                else ""
            )
            + "</td>"
            f"<td>{html.escape(_scientific_metric_value(metric_key, row.get('metric_value')))}</td>"
            f"<td>{html.escape(str(row.get('driver_chain_id') or ''))}</td>"
            f"<td>{html.escape(_mechanism(row.get('driver_failure_mode')))}</td>"
            f"<td>{_int(row.get('top3_presence_seed_count'))}/30</td>"
            "</tr>"
            for row in rows
        )
        sections.append(
            '<details class="metric-card" open>'
            f"<summary><span>{html.escape(_metric_name(metric_key, metric_audit.get('metric_label')))}</span>"
            f'<span class="badge {badge_class}">{html.escape(status)}</span></summary>'
            '<p class="small">Les valeurs sont conservées séparément : aucun score pondéré ne mélange service, backlog et production. « x/30 » indique dans combien des 30 simulations appariées le fournisseur appartient au trio descriptif de cette mesure ; ce n’est pas une fréquence d’incident.</p>'
            '<div class="table-wrap"><table><thead><tr><th>Fournisseur</th><th>Conséquence moyenne</th><th>Voie déterminante</th><th>Hypothèse déterminante</th><th>Présence dans le trio descriptif</th></tr></thead>'
            f"<tbody>{table_rows}</tbody></table></div></details>"
        )
    return "".join(sections)


def _family_sections(data: Mapping[str, Any]) -> str:
    families = data["boundary"]["audit"].get(
        "failure_mode_specific_metric_priority_audits", {}
    )
    blocks: list[str] = []
    for failure_mode in ("transport_delay", "supply_availability"):
        payload = families[failure_mode]
        metric_audits = list(payload.get("metric_priority_audits") or [])
        service = next(
            row
            for row in metric_audits
            if str(row.get("metric_key") or "") == "horizon_on_due_service_delta"
        )
        service_released = _bool(service.get("metric_priority_set_release_pass"))
        supplier_ids = list(service.get("released_priority_supplier_ids") or [])
        service_reading = (
            "Trio publiable pour cette hypothèse : "
            + ", ".join(str(value) for value in supplier_ids)
            if service_released
            else "Aucun trio service publiable pour cette hypothèse."
        )
        metric_lines = "".join(
            "<li>"
            f"<b>{html.escape(_metric_name(row.get('metric_key'), row.get('metric_label')))}</b> : "
            + (
                "séparation suffisante"
                if _bool(row.get("metric_priority_set_release_pass"))
                else "groupe non tranché"
            )
            + "</li>"
            for row in sorted(
                metric_audits,
                key=lambda row: BOUNDARY_METRIC_ORDER.index(
                    str(row.get("metric_key") or "")
                ),
            )
        )
        blocks.append(
            '<article class="family-card">'
            f"<h3>{html.escape(HYPOTHESIS_LABELS[failure_mode])}</h3>"
            f'<p class="truth"><b>Service client :</b> {html.escape(service_reading)}</p>'
            f"<ul>{metric_lines}</ul>"
            "</article>"
        )
    return "".join(blocks)


def _seed_effect_table(data: Mapping[str, Any]) -> str:
    rows = sorted(
        (
            row
            for row in data["boundary"]["effects"]
            if str(row.get("aggregation_level") or "")
            == "supplier_any_confirmed_scenario"
        ),
        key=lambda row: str(row.get("supplier_id") or ""),
    )
    return "".join(
        "<tr>"
        f"<td><b>{html.escape(str(row.get('supplier_id') or ''))}</b></td>"
        f"<td>{_int(row.get('client_effect_seed_count'))}/30</td>"
        f"<td>{_int(row.get('production_only_effect_seed_count'))}/30</td>"
        f"<td>{_int(row.get('upstream_absorbed_seed_count'))}/30</td>"
        f"<td>{_int(row.get('no_measurable_effect_seed_count'))}/30</td>"
        f"<td>{_int(row.get('inactive_window_seed_count'))}/30</td>"
        "</tr>"
        for row in rows
    )


def _effect_class_label(value: object) -> str:
    return {
        "adverse": "défavorable",
        "improvement": "favorable dans le modèle",
        "uncertain": "non tranché",
        "negligible": "négligeable",
    }.get(str(value or ""), str(value or "").replace("_", " "))


def _extension_effect_rows(
    rows: Sequence[Mapping[str, object]], *, kind: str, repetition_count: int
) -> str:
    context_key = "window_index" if kind == "temporal" else "failure_mode"
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get(context_key) or ""),
            str(row.get("chain_id") or ""),
            EXTENSION_METRIC_ORDER.index(str(row.get("metric") or "")),
        ),
    )
    rendered: list[str] = []
    for row in ordered:
        context = (
            f"J{_int(row.get('stress_start_day'))}–J{_int(row.get('stress_end_day'))}"
            if kind == "temporal"
            else _mechanism(row.get("failure_mode"))
        )
        rendered.append(
            "<tr>"
            f"<td>{html.escape(context)}</td>"
            f"<td><b>{html.escape(str(row.get('chain_id') or ''))}</b><br>"
            f"{html.escape(str(row.get('supplier_id') or ''))}</td>"
            f"<td>{html.escape(_metric_name(row.get('metric'), row.get('metric_label')))}</td>"
            f"<td><b>{html.escape(_scientific_metric_value(row.get('metric'), row.get('effect_mean')))}</b><br>"
            f"IC 95 % : {html.escape(_scientific_metric_value(row.get('metric'), row.get('effect_ci95_low')))} à "
            f"{html.escape(_scientific_metric_value(row.get('metric'), row.get('effect_ci95_high')))}</td>"
            f"<td>{html.escape(_effect_class_label(row.get('effect_class')))}</td>"
            f"<td>{_int(row.get('conditional_client_effect_seed_count'))}/{repetition_count}</td>"
            f"<td>{_int(row.get('conditional_production_effect_seed_count'))}/{repetition_count}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _state_dependence_reading(interpretation: Mapping[str, object]) -> str:
    if _bool(interpretation.get("within_lane_context_difference_detected")):
        return (
            "La conséquence change selon la période ou la cause testée sur au moins "
            "une même voie. C’est compatible avec un système dynamique où stocks, "
            "encours et retards évoluent, sans suffire à identifier une causalité "
            "propre de l’état."
        )
    return (
        "Aucune différence nette entre les contextes testés n’est détectée sur ces "
        "quatre voies. Cela ne démontre pas une robustesse sur le réseau entier."
    )


def _scientific_extension_section(data: Mapping[str, Any], *, kind: str) -> str:
    extension = data["extension"]
    if kind == "temporal":
        title = "Même incident à quatre périodes de l’horizon"
        rows = extension["temporal"]
        interpretation = extension["audit"].get("temporal_interpretation") or {}
        detail_summary = f"Voir les {_fr(len(rows))} résultats période × voie × mesure"
        first_header = "Période imposée"
        caveat = (
            "Les quatre périodes testent l’état différent du système au moment du "
            "stress ; elles ne prédisent pas la date d’un futur incident."
        )
    else:
        title = "Quatre causes métier sur quatre voies à approfondir"
        rows = extension["causes"]
        interpretation = (
            extension["audit"].get("four_business_cause_interpretation") or {}
        )
        detail_summary = f"Voir les {_fr(len(rows))} résultats cause × voie × mesure"
        first_header = "Cause imposée"
        caveat = (
            "Les amplitudes sont des hypothèses sévères différentes (jours ajoutés ou "
            "part utile). Elles ne sont pas comparables comme un classement des causes."
        )
    reading = _state_dependence_reading(interpretation)
    repetition_count = _int(
        data.get("extension_repetition_count"),
        extension_contract.EXPECTED_PAIRED_SEED_COUNT,
    )
    if repetition_count <= 0:
        raise ValueError("Le nombre de répétitions d'extension doit être positif.")
    order_label = "aucun ordre scientifique entre les quatre dossiers"
    return f"""
    <article class="panel extension-panel">
      <span class="eyebrow">SIMULATIONS APPARIÉES · PÉRIMÈTRE LIMITÉ</span>
      <h2>{html.escape(title)}</h2>
      <p class="truth"><b>Résultat :</b> {html.escape(reading)}</p>
      <p class="lead"><b>Lecture des quatre voies :</b> {html.escape(order_label)}. {html.escape(caveat)}</p>
      <p class="warning"><b>Portée :</b> les 4 voies du groupe service non séparé, sur les 18 voies actives, ont été approfondies ici. Les 14 autres n’ont pas reçu ces extensions ; la robustesse globale du réseau n’est donc pas évaluable.</p>
      <details><summary>{html.escape(detail_summary)}</summary>
        <div class="table-wrap"><table><thead><tr><th>{html.escape(first_header)}</th><th>Voie et fournisseur</th><th>Mesure</th><th>Effet moyen et intervalle</th><th>Classe d’effet</th><th>Effet client</th><th>Effet production</th></tr></thead>
        <tbody>{_extension_effect_rows(rows, kind=kind, repetition_count=repetition_count)}</tbody></table></div>
      </details>
    </article>
    """


def _plain_lane_rows(data: Mapping[str, Any]) -> str:
    return "".join(
        "<tr>"
        f"<td><b>{html.escape(str(row.get('chain_id') or ''))}</b></td>"
        f"<td>{html.escape(str(row.get('supplier_id') or ''))}</td>"
        f"<td>{html.escape(_strip_item(row.get('item_id')))}</td>"
        f"<td>{html.escape(str(row.get('dst_node_id') or ''))}</td>"
        f"<td>{html.escape(str(row.get('target_product_id') or ''))}</td>"
        "</tr>"
        for row in sorted(data["lanes"], key=lambda row: str(row.get("chain_id") or ""))
    )


def render_network_dashboard(
    data: Mapping[str, Any],
    *,
    links: Mapping[str, str | None],
    generated_label: str,
) -> str:
    manifest = data["manifest"]
    horizon_last_day = _int(manifest.get("days"), 720) - 1
    temporal_last_day = max(
        (_int(row.get("simulation_days"), 720) - 1 for row in data["extension"]["temporal"]),
        default=horizon_last_day,
    )
    nav_links = "".join(
        _link(label, description, links.get(key))
        for key, label, description in (
            ("meeting", "Revenir au parcours court", "Les trois vues du rendez-vous"),
            ("component", "Ouvrir la cascade composant", "Composant 338929 et qualité"),
            ("map", "Ouvrir la carte complète", "Réseau, nœuds, flux et lots"),
        )
    )
    causal_released = bool(data.get("causal_released"))
    lot_detail = ""
    if causal_released:
        lot_detail = f"""
        <details><summary>Voir les {_fr(len(data["causal_detail"]))} lignes techniques appariées</summary>
          {_lot_delay_svg(data["causal_detail"])}
          <div class="lot-tools"><label for="lot-filter"><b>Rechercher un identifiant, article ou nœud</b></label><input id="lot-filter" type="search" placeholder="Ex. 338929, M-1810"><span class="count" id="lot-count">{_fr(len(data["causal_detail"]))} lignes affichées</span></div>
          <div class="table-wrap"><table id="lot-table"><thead><tr><th>Configuration</th><th>Simulation appariée</th><th>Cause</th><th>Type</th><th>Identifiant technique</th><th>Nœud</th><th>Article</th><th>Événement</th><th>Jour normal</th><th>Jour incident</th><th>Écart</th><th>Écart quantité</th><th>Différence</th></tr></thead><tbody>{_lot_detail_rows(data)}</tbody></table></div>
        </details>"""
    action_cards = "".join(
        '<article class="action-card">'
        f"<h3>{html.escape(label)}</h3>"
        "<p>Hypothèse d’action à documenter puis à comparer dans une future simulation appariée. Le modèle ne prétend ici cibler ni une expédition ni un lot observé.</p>"
        "</article>"
        for label in ACTION_LABELS.values()
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risques fournisseurs — sensibilité dynamique du réseau</title>
<style>
:root{{--navy:#082640;--blue:#1f6feb;--green:#147d64;--coral:#d74735;--amber:#946000;--ink:#12263a;--muted:#5b7084;--line:#d8e2ec;--paper:#f2f6fa;--panel:#fff}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.52 Inter,Segoe UI,Arial,sans-serif}}a{{color:inherit}}.wrap{{max-width:1440px;margin:auto;padding:0 28px 64px}}.hero{{background:linear-gradient(135deg,#061d34,#114d76 65%,#147d64);color:#fff;padding:44px 0 36px}}.hero h1{{font-size:clamp(2rem,4vw,3.55rem);line-height:1.04;margin:7px 0 13px}}.hero p{{max-width:1080px;color:#d9e8f5;font-size:1.07rem}}.eyebrow,.badge{{display:inline-flex;border-radius:99px;padding:5px 10px;font-size:.72rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase}}.eyebrow{{background:#dbeafe;color:#164e86}}.hero .eyebrow{{background:#dff7ef;color:#075843}}.links{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:22px}}.link-card{{display:flex;flex-direction:column;text-decoration:none;background:#fff;color:var(--navy);padding:13px 15px;border-radius:13px}}.link-card span{{font-size:.82rem;color:var(--muted)}}nav{{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line);overflow:auto;white-space:nowrap}}nav .wrap{{padding-top:9px;padding-bottom:9px}}nav a{{text-decoration:none;margin-right:15px;color:#33516c}}section{{scroll-margin-top:62px;margin-top:26px}}.panel{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:23px;box-shadow:0 10px 28px rgba(19,46,72,.05)}}h2{{font-size:1.6rem;margin:2px 0 8px}}h3{{margin:0 0 8px}}.lead,.small{{color:var(--muted);max-width:1120px}}.small{{font-size:.88rem}}.priority-grid,.family-grid,.action-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:12px;margin-top:16px}}.priority-card,.family-card,.action-card{{border:1px solid var(--line);border-radius:14px;padding:16px;background:#fbfdff}}.priority-card{{border-top:5px solid var(--green)}}.priority-card>span{{font-size:.74rem;text-transform:uppercase;color:var(--green);font-weight:800}}.priority-card strong{{display:block;color:var(--coral);font-size:1.3rem}}.priority-card small{{display:block;color:var(--muted);margin-top:5px}}.truth,.warning{{padding:14px 16px;border-left:5px solid var(--blue);background:#eef6ff;border-radius:10px}}.warning{{border-left-color:#e7a631;background:#fff8e8}}.chips{{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}}.supplier-chip,.mini-pass{{display:inline-block;border-radius:99px;background:#e5edf5;padding:3px 9px;margin:3px;font-size:.78rem}}.mini-pass{{display:block;width:max-content;background:#dcf6eb;color:#09634d;margin:5px 0 0}}.metric-card{{background:#fff;border:1px solid var(--line);border-radius:15px;padding:14px;margin-top:12px}}.metric-card summary{{display:flex;justify-content:space-between;gap:12px;align-items:center;font-weight:800;cursor:pointer}}.badge.pass{{background:#dcf6eb;color:#09634d}}.badge.warn{{background:#fff0d5;color:#825000}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px;margin-top:13px;max-height:620px}}table{{border-collapse:collapse;width:100%;font-size:.84rem;background:#fff}}th,td{{padding:9px 10px;text-align:left;border-bottom:1px solid #e5ecf2;vertical-align:top}}th{{position:sticky;top:0;background:#eaf1f7;color:#27445e;z-index:1}}tbody tr:hover{{background:#f7fbff}}.extension-panel{{margin-top:14px}}details{{margin-top:15px}}summary{{cursor:pointer;font-weight:800}}.lot-tools{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:15px}}input{{border:1px solid #b9c9d7;border-radius:10px;padding:10px 12px;min-width:310px;font:inherit}}.lot-delay-chart{{display:block;width:min(100%,760px);margin:18px auto}}.svg-label{{font:13px Segoe UI,Arial,sans-serif;fill:#415a70}}.svg-value{{font:700 13px Segoe UI,Arial,sans-serif;fill:#12263a}}.footer{{color:var(--muted);font-size:.82rem;margin-top:28px}}@media(max-width:800px){{.links{{grid-template-columns:1fr}}.wrap{{padding-left:14px;padding-right:14px}}th{{position:static}}input{{min-width:100%;width:100%}}.metric-card summary{{align-items:flex-start;flex-direction:column}}}}
</style></head><body>
<header class="hero"><div class="wrap"><span class="eyebrow">SIMULÉ · SENSIBILITÉ CONDITIONNELLE</span><h1>Où un incident fournisseur imposé fragilise-t-il le réseau&nbsp;?</h1><p>Le modèle est dynamique : stocks, commandes, encours, lots, retards, backlog et production évoluent ensemble. L’analyse principale couvre J0–J{horizon_last_day} et l’étude des incidents tardifs prolonge leur suivi jusqu’à J{temporal_last_day}. Les incidents restent exogènes et aucune régulation en boucle fermée n’est active ici. Cette page décrit les conséquences de scénarios testés ; elle ne prévoit pas les incidents fournisseurs.</p><div class="links">{nav_links}</div></div></header>
<nav><div class="wrap"><a href="#lecture">Lecture</a><a href="#priorites">Priorité service</a><a href="#mesures">4 mesures</a><a href="#hypotheses">2 hypothèses</a><a href="#effets">Effets x/30</a><a href="#temps">Temps et état</a><a href="#causes">Causes</a><a href="#voies">18 voies</a><a href="#lots">Lots</a><a href="#actions">Actions</a><a href="#limites">Limites</a></div></nav>
<main class="wrap">
<section id="lecture"><article class="panel"><span class="eyebrow">VOCABULAIRE CLIENT</span><h2>Quatre mots, quatre niveaux de preuve</h2><div class="family-grid"><article class="family-card"><h3>Observé</h3><p>Aucune fréquence ni performance fournisseur historique n’est utilisée dans ce module. Les identifiants de réseau décrivent le périmètre fourni, pas une performance constatée.</p></article><article class="family-card"><h3>Simulé</h3><p>Conséquence calculée par le moteur quand on impose un incident au fonctionnement normal, avec le même état initial et les mêmes tirages.</p></article><article class="family-card"><h3>Signal de priorité</h3><p>Fournisseur ou groupe à examiner en premier sous une mesure et une hypothèse explicites. Ce n’est pas une note absolue de criticité.</p></article><article class="family-card"><h3>Hypothèse</h3><p>Incident ou paramètre volontairement imposé pour comprendre la réaction de la chaîne ; sa plausibilité métier reste à valider.</p></article></div></article></section>
{_priority_boundary_section(data)}
<section id="mesures"><article class="panel"><span class="eyebrow">QUATRE LECTURES SÉPARÉES</span><h2>Service, service glissant, backlog et production</h2><p class="lead">Chaque mesure possède sa propre vérification statistique et sa propre conclusion. Elles ne sont jamais additionnées dans un score opaque.</p>{_four_metric_sections(data)}</article></section>
<section id="hypotheses"><article class="panel"><span class="eyebrow">DEUX FAMILLES PRÉ-DÉCLARÉES</span><h2>Décaler la date n’est pas perdre de la quantité utile</h2><p class="lead">L’analyse principale teste séparément un retard de 120 jours et une disponibilité limitée à 50 %, une voie à la fois. Les conclusions peuvent différer selon l’hypothèse : on ne les transforme pas en criticité universelle.</p><p class="truth"><b>Couverture des dégradations.</b> Les 18 voies sont confirmées avec 30 comparaisons appariées sur ces deux stress sévères seulement. Les quatre causes et les quatre périodes sont approfondies sur les quatre voies du groupe service non séparé. Les niveaux intermédiaires du premier tri reposent sur une seule simulation et ne permettent pas une conclusion robuste sur tout le réseau.</p><div class="family-grid">{_family_sections(data)}</div></article></section>
<section id="effets"><article class="panel"><span class="eyebrow">EFFETS CONDITIONNELS PAR TIRAGE</span><h2>Dans combien des 30 simulations appariées observe-t-on chaque type d’effet&nbsp;?</h2><p class="truth"><b>« x/30 » est un comptage de simulations testées.</b> Ce n’est ni une fréquence historique, ni une probabilité d’incident, ni une prévision fournisseur. Les catégories peuvent se chevaucher lorsqu’un fournisseur possède plusieurs voies ou hypothèses ; elles n’ont donc pas à totaliser 30.</p><div class="table-wrap"><table><thead><tr><th>Fournisseur</th><th>Effet client</th><th>Production seulement</th><th>Absorbé en amont</th><th>Aucun effet mesurable</th><th>Voie inactive dans la fenêtre</th></tr></thead><tbody>{_seed_effect_table(data)}</tbody></table></div></article></section>
<section id="temps">{_scientific_extension_section(data, kind="temporal")}</section>
<section id="causes">{_scientific_extension_section(data, kind="cause")}</section>
<section id="voies"><article class="panel"><span class="eyebrow">PÉRIMÈTRE TESTÉ</span><h2>Les 18 voies actives</h2><p class="lead">Une voie associe un fournisseur, un article, une usine destinataire et un produit. La liste est alphabétique par identifiant de voie : aucun rang hérité n’est affiché.</p><div class="table-wrap"><table><thead><tr><th>Voie</th><th>Fournisseur</th><th>Article</th><th>Usine</th><th>Produit</th></tr></thead><tbody>{_plain_lane_rows(data)}</tbody></table></div></article></section>
<section id="lots"><article class="panel"><span class="eyebrow">LOTS SIMULÉS</span><h2>Lots potentiellement exposés et effet réellement attribuable : deux informations différentes</h2>{_lot_summary(data)}{_lot_exposure_table(data)}{_lot_genealogy_detail_table(data)}{lot_detail}<p class="truth"><b>Périmètre du suivi.</b> Une comparaison appariée est réalisée pour chacune des quatre voies approfondies. Elle montre la propagation généalogique simulée ; elle ne fournit pas encore la variabilité statistique des effets lot par lot ni la traçabilité complète des lots industriels.</p><p class="warning"><b>Retenue qualité :</b> la quarantaine est reconstruite par le scénario à partir des événements du moteur ; elle n’est pas encore un statut qualité natif observé dans l’historique industriel.</p></article></section>
<section id="actions"><article class="panel"><span class="eyebrow">ACTIONS NON PROMUES</span><h2>Quatre hypothèses opérationnelles à instruire, pas des recommandations</h2><p class="warning"><b>Aucune action n’est sélectionnée ni recommandée dans ce paquet.</b> Les quatre dossiers service ont été approfondis, mais les 14 autres voies et les prérequis opérationnels des actions ne permettent pas une recommandation réseau.</p><p class="truth"><b>Aucun des quatre leviers ci-dessous n’a encore été comparé sur les quatre dossiers avec le protocole final.</b> Les chiffres d’anciens essais concernent deux cascades séparées et ne mesurent pas l’efficacité de ces leviers sur les dossiers affichés.</p><div class="action-grid">{action_cards}</div><p class="lead">Le transport est, à ce stade, un réglage calendaire en boucle ouverte appliqué à toute la voie : ce n’est pas le déclenchement d’un transport réel sur une expédition ou un lot identifié. Les autres leviers exigent un stock réellement libre avant l’incident ou une source déjà qualifiée avec capacité engagée. Aucune accélération du laboratoire, aucun stock créé pendant l’incident et aucun fournisseur non qualifié ne sont supposés.</p></article></section>
<section id="limites"><article class="panel"><span class="eyebrow">RÈGLE DE VÉRITÉ</span><h2>Ce que l’on sait aujourd’hui</h2><p class="truth"><b>Évaluable :</b> la sensibilité conditionnelle du réseau aux deux hypothèses principales sur 18 voies, les quatre conséquences séparées, les variations temporelles et quatre causes sur les 4 voies du groupe service, ainsi que leur exposition généalogique de lots.</p><p class="warning"><b>Non évaluable :</b> la robustesse globale de la priorité sur les 18 voies, la probabilité ou la date d’un futur incident, la performance fournisseur observée, une criticité industrielle universelle, l’efficacité d’une action et l’attribution causale aux mêmes lots lorsque leurs identifiants dynamiques changent. La mesure brute de récupération du réseau est exclue car sa fenêtre commune n’est pas valide pour les fenêtres propres à chaque voie.</p><details><summary>Pourquoi des simulations appariées ?</summary><p>Le fonctionnement normal et le scénario d’incident partagent le même état initial et les mêmes tirages aléatoires. Leur différence isole ainsi, dans le modèle, la conséquence du stress imposé. Les 30 répétitions vérifient si cette conséquence dépend d’un tirage particulier ; elles ne mesurent pas la fréquence réelle de l’incident.</p></details></article></section>
<p class="footer">Page autonome générée {html.escape(generated_label)} · résultats scientifiques vérifiés · anciens résultats et cartes non modifiés.</p>
</main><script>(()=>{{const wire=(inputId,rowSelector,countId)=>{{const input=document.getElementById(inputId),rows=[...document.querySelectorAll(rowSelector)],count=document.getElementById(countId);if(!input||!count)return;const render=()=>{{const q=input.value.trim().toLocaleLowerCase('fr');let shown=0;rows.forEach(row=>{{const visible=!q||row.textContent.toLocaleLowerCase('fr').includes(q);row.hidden=!visible;if(visible)shown++;}});count.textContent=new Intl.NumberFormat('fr-FR').format(shown)+' lignes affichées';}};input.addEventListener('input',render);}};wire('genealogy-lot-filter','.genealogy-lot-row','genealogy-lot-count');wire('lot-filter','.lot-row','lot-count');}})();</script></body></html>"""


def build_network_dashboard(
    *,
    artifact_dir: str | Path,
    output_html: str | Path,
    meeting_html: str | Path | None = None,
    component_html: str | Path | None = None,
    map_html: str | Path | None = None,
    priority_boundary_audit_dir: str | Path | None = None,
    action_selection_dir: str | Path | None = None,
    generated_label: str = "le 2 septembre 2026",
) -> dict[str, Any]:
    output = Path(output_html).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data = load_network_results(
        artifact_dir,
        priority_boundary_audit_dir=priority_boundary_audit_dir,
        action_selection_dir=action_selection_dir,
    )
    links = {
        "meeting": _relative_href(output, Path(meeting_html).resolve())
        if meeting_html
        else None,
        "component": _relative_href(output, Path(component_html).resolve())
        if component_html
        else None,
        "map": _relative_href(output, Path(map_html).resolve()) if map_html else None,
    }
    document = render_network_dashboard(
        data, links=links, generated_label=generated_label
    )
    output.write_text(document, encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "output_html": str(output),
        "supplier_count": len(data["ranking"]),
        "lane_count": len(data["lanes"]),
        "causal_detail_count": len(data["causal_detail"]),
        "genealogical_lot_detail_count": len(data["lot_genealogical_detail"]),
        "stable_priority_count": len(data["stable_priorities"]),
        "priority_group_supplier_count": len(data["priority_group_supplier_ids"]),
        "priority_reporting_status": data["priority_reporting_status"],
        "input_status": data["input_status"],
        "global_network_priority_robustness_evaluable": False,
        "actions_promoted": False,
        "size_bytes": output.stat().st_size,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument("--meeting-html", type=Path)
    parser.add_argument("--component-html", type=Path)
    parser.add_argument("--map-html", type=Path)
    parser.add_argument("--priority-boundary-audit-dir", type=Path, required=True)
    parser.add_argument("--action-selection-dir", type=Path)
    parser.add_argument("--generated-label", default="le 2 septembre 2026")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_network_dashboard(
        artifact_dir=args.artifact_dir,
        output_html=args.output_html,
        meeting_html=args.meeting_html,
        component_html=args.component_html,
        map_html=args.map_html,
        priority_boundary_audit_dir=args.priority_boundary_audit_dir,
        action_selection_dir=args.action_selection_dir,
        generated_label=args.generated_label,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
