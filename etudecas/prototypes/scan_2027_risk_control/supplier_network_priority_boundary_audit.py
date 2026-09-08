#!/usr/bin/env python3
"""Fail-closed audit of the supplier-network priority boundary.

This module is additive: it reads a *completed* network campaign and writes a
new compact artifact.  It never edits the campaign it audits.  Its main job is
to prevent deterministic identifier tie-breaks from being mistaken for
evidence: the fixed descriptive set of three is compared with every supplier
outside that set, while the same-30-draw post-selection limitation remains
explicit.  No population-level or action-promotion claim is released.

The audit keeps four consequence readings separate.  It does not manufacture
an opaque weighted score and it does not estimate supplier incident
probabilities:

* mean loss of on-request-date client service over J0--J719;
* loss of the worst rolling 28-day on-request-date service;
* incremental backlog quantity-days divided by requested quantity;
* released-production shortfall ratio.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "etudecas.supplier_network_priority_boundary_audit.v1"
MANIFEST_SCHEMA_VERSION = (
    "etudecas.supplier_network_priority_boundary_audit_package.v1"
)
EXPECTED_CAMPAIGN_SCHEMA_VERSION = (
    "etudecas.supplier_network_risk_screen_campaign.v1"
)
EXPECTED_BASELINE_COUNT = 30
EXPECTED_ACTIVE_LANE_COUNT = 18
EXPECTED_SUPPLIER_COUNT = 16
EXPECTED_CONFIRMED_SCENARIO_COUNT = 36
EXPECTED_STRESS_ROW_COUNT = 1_080
EXPECTED_TOTAL_ROW_COUNT = 1_110
EXPECTED_TARGET_PRODUCTS = frozenset({"268091", "268967"})
BOOTSTRAP_RESAMPLE_COUNT = 10_000
BOOTSTRAP_SEED_BASE = 90_210
NUMERICAL_TOLERANCE_RATIO = 1e-8
MINIMUM_REPORTABLE_RATIO_GAP = 0.001  # 0.1 percentage point
MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP = 0.1
DISPLAY_CLIENT_SERVICE_LOSS_RATIO = 0.001
DISPLAY_CLIENT_BACKLOG_DAYS_PER_REQUESTED_UNIT = 0.1
DISPLAY_PRODUCTION_SHORTFALL_RATIO = 0.001
REQUIRED_TOP3_PRESENCE_COUNT = 29
CONFIRMED_FAILURE_MODES = frozenset(
    {"transport_delay", "supply_availability"}
)
HYPOTHESIS_FAMILY_BY_FAILURE_MODE = {
    "transport_delay": "date_shift",
    "supply_availability": "usable_quantity_loss",
}
SEVERE_HYPOTHESIS_BY_FAILURE_MODE = {
    "transport_delay": (120.0, "jours_ajoutes"),
    "supply_availability": (0.50, "part_disponible"),
}
EXPECTED_STRESS_WINDOW_DAYS = 180
SUPPLIER_ENVELOPE_SCOPE = (
    "supplier_worst_single_lane_scenario_envelope_across_two_hypotheses"
)
BASELINE_SCENARIO_ID = "baseline_nominal"
EFFECT_STATUSES = frozenset(
    {
        "effet_mesure_sur_le_service_client",
        "effet_mesure_sur_la_production_mais_pas_sur_le_service_client",
        "effet_amont_absorbe_avant_le_client",
        "stress_applique_sans_effet_mesurable",
        "voie_non_sollicitee_pendant_la_fenetre_de_stress",
    }
)

REQUIRED_SOURCE_FILES = (
    "campaign_manifest.json",
    "confirmation_metrics.csv",
    "confirmation_selection.json",
    "confirmation_supplier_sensitivity_ranking.csv",
    "scenario_design.csv",
)

OUTPUT_FILES = (
    "scientific_priority_boundary_audit.json",
    "supplier_metric_rankings.csv",
    "conditional_effect_seed_counts.csv",
    "common_random_numbers_provenance.csv",
)
MANIFEST_SIGNED_FIELDS = (
    "schema_version",
    "status",
    "builder_sha256",
    "source_file_sha256",
    "artifact_file_sha256",
    "bootstrap_resample_count",
    "scoped_descriptive_priority_set_display_allowed",
    "displayed_scoped_priority_supplier_ids",
    "confirmatory_priority_set_release_allowed",
    "global_priority_release_allowed",
    "action_promotion_allowed",
    "service_priority_set_release_pass",
    "universal_supplier_top3_release_pass",
    "integrity_digest_not_authenticated_signature",
    "cryptographic_authentication_present",
    "internal_consistency_recomputed_from_source",
    "package_signature_semantics",
    "legacy_priority_release_aliases_neutralized",
)
CAMPAIGN_SIGNATURE_FIELDS = (
    "schema_version",
    "mode",
    "campaign_script_sha256",
    "v4_extraction_core_sha256",
    "graph_sha256",
    "engine_sha256",
    "reference_shipments_sha256",
    "scope_audit_path",
    "scope_audit_csv_sha256",
    "scope_audit_manifest_sha256",
    "reference_summary_sha256",
    "supplier_floor_source_sha256",
    "prepared_supplier_floor_content_sha256",
    "profile_sha256",
    "days",
    "screening_seed",
    "smoke_components_requested",
    "smoke_all_levels_requested",
    "confirmation_seeds",
    "confirmation_top_lanes",
    "confirmation_scope_requirement",
    "confirmation_mathematical_families",
    "planned_run_counts",
    "common_window_start_day",
    "common_window_end_day",
    "lane_specific_stress_duration_days",
    "lane_specific_window_method",
    "active_chain_ids",
    "scenario_ids",
    "reference_open_orders_disabled",
    "network_lot_trace_opt_in",
)


@dataclass(frozen=True)
class ScenarioMeta:
    scenario_id: str
    chain_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    target_product_id: str
    failure_mode: str
    level_code: str
    mechanism_value: float
    mechanism_unit: str
    stress_start_day: int
    stress_end_day: int


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    direction: str
    reportable_gap: float


METRICS = (
    MetricSpec(
        "horizon_on_due_service_delta",
        "Perte moyenne du service à la date demandée sur J0–J719",
        "ratio_and_percentage_points",
        "lower_is_worse",
        MINIMUM_REPORTABLE_RATIO_GAP,
    ),
    MetricSpec(
        "worst_rolling_28d_on_due_delta",
        "Perte du pire service glissant à 28 jours",
        "ratio_and_percentage_points",
        "lower_is_worse",
        MINIMUM_REPORTABLE_RATIO_GAP,
    ),
    MetricSpec(
        "incremental_backlog_days_per_requested_unit",
        "Backlog incrémental normalisé par la demande",
        "UN_day_per_requested_UN",
        "higher_is_worse",
        MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP,
    ),
    MetricSpec(
        "released_production_shortfall_ratio",
        "Manque de production libérée rapporté à la référence",
        "ratio",
        "higher_is_worse",
        MINIMUM_REPORTABLE_RATIO_GAP,
    ),
)
METRIC_BY_KEY = {metric.key: metric for metric in METRICS}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "oui",
        "pass",
    }


def _to_int(value: Any, default: int = -1) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else default
    if isinstance(value, str):
        raw = value.strip()
        if raw and (raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit())):
            return int(raw)
    return default


def _number(value: Any, *, field: str, context: str) -> float:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Valeur {field!r} absente ou invalide ({context}).") from exc
    if not math.isfinite(result):
        raise ValueError(f"Valeur {field!r} non finie ({context}).")
    return result


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Le CSV de sortie ne peut pas être vide: {path.name}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _manifest_signature_payload(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {key: manifest.get(key) for key in MANIFEST_SIGNED_FIELDS}


def _validate_campaign_signature(manifest: Mapping[str, Any]) -> None:
    missing = [key for key in CAMPAIGN_SIGNATURE_FIELDS if key not in manifest]
    if missing:
        raise ValueError(
            "Payload de signature de campagne incomplet: " + ", ".join(missing)
        )
    payload = {key: manifest[key] for key in CAMPAIGN_SIGNATURE_FIELDS}
    expected = _canonical_sha256(payload)
    if str(manifest.get("campaign_signature") or "") != expected:
        raise ValueError("Signature canonique de la campagne source invalide.")


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = min(1.0, max(0.0, quantile)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _bootstrap_indices(seed_count: int, resamples: int) -> tuple[tuple[int, ...], ...]:
    if seed_count <= 0 or resamples <= 0:
        raise ValueError("Le bootstrap exige des graines et des réplications positives.")
    rng = random.Random(
        BOOTSTRAP_SEED_BASE + seed_count * 100_003 + resamples
    )
    return tuple(
        tuple(rng.randrange(seed_count) for _ in range(seed_count))
        for _ in range(resamples)
    )


def _same_number(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-9)


def _load_scenario_meta(
    rows: Sequence[Mapping[str, Any]], selected_scenario_ids: Sequence[str]
) -> dict[str, ScenarioMeta]:
    selected = set(selected_scenario_ids)
    result: dict[str, ScenarioMeta] = {}
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "")
        if scenario_id not in selected:
            continue
        if scenario_id in result:
            raise ValueError(f"Scénario dupliqué dans le plan: {scenario_id}")
        meta = ScenarioMeta(
            scenario_id=scenario_id,
            chain_id=str(row.get("chain_id") or ""),
            supplier_id=str(row.get("supplier_id") or ""),
            item_id=str(row.get("item_id") or ""),
            dst_node_id=str(row.get("dst_node_id") or ""),
            target_product_id=str(row.get("target_product_id") or ""),
            failure_mode=str(row.get("failure_mode") or ""),
            level_code=str(row.get("level_code") or ""),
            mechanism_value=_number(
                row.get("mechanism_value"),
                field="mechanism_value",
                context=f"plan/{scenario_id}",
            ),
            mechanism_unit=str(row.get("mechanism_unit") or ""),
            stress_start_day=_to_int(row.get("stress_start_day")),
            stress_end_day=_to_int(row.get("stress_end_day")),
        )
        if not all(
            (
                meta.chain_id,
                meta.supplier_id,
                meta.item_id,
                meta.dst_node_id,
                meta.target_product_id,
                meta.failure_mode,
                meta.level_code,
                meta.mechanism_unit,
            )
        ):
            raise ValueError(f"Métadonnées incomplètes pour {scenario_id}")
        _validate_scenario_meta_contract(meta)
        result[scenario_id] = meta
    if set(result) != selected:
        missing = sorted(selected - set(result))
        raise ValueError("Scénarios sélectionnés absents du plan: " + ", ".join(missing))
    return result


def _validate_scenario_meta_contract(meta: ScenarioMeta) -> None:
    if meta.failure_mode not in SEVERE_HYPOTHESIS_BY_FAILURE_MODE:
        raise ValueError(f"Famille non prévue pour {meta.scenario_id}.")
    expected_value, expected_unit = SEVERE_HYPOTHESIS_BY_FAILURE_MODE[
        meta.failure_mode
    ]
    if meta.level_code != "severe":
        raise ValueError(f"Niveau non sévère pour {meta.scenario_id}.")
    if not _same_number(meta.mechanism_value, expected_value):
        raise ValueError(f"Amplitude sévère incohérente pour {meta.scenario_id}.")
    if meta.mechanism_unit != expected_unit:
        raise ValueError(f"Unité d'hypothèse incohérente pour {meta.scenario_id}.")
    if (
        meta.stress_start_day < 0
        or meta.stress_end_day < meta.stress_start_day
        or meta.stress_end_day - meta.stress_start_day + 1
        != EXPECTED_STRESS_WINDOW_DAYS
    ):
        raise ValueError(f"Fenêtre de stress non conforme pour {meta.scenario_id}.")


def _resolve_common_random_numbers(
    row: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    identity = {
        "scenario_id": str(row.get("scenario_id") or ""),
        "seed": _to_int(row.get("seed")),
    }
    raw = row.get("resolved_common_random_numbers")
    if str(raw or "").strip():
        declared_seed = _to_int(row.get("resolved_random_seed"))
        resolved = _as_bool(raw) and declared_seed == identity["seed"]
        return resolved, {
            **identity,
            "provenance_source": "confirmation_metrics_embedded_field",
            "summary_path": "",
            "summary_sha256": "",
            "summary_policy_seed": declared_seed,
            "resolved_common_random_numbers": resolved,
        }
    run_dir = str(row.get("run_dir") or "").strip()
    if not run_dir:
        return False, {
            **identity,
            "provenance_source": "missing",
            "summary_path": "",
            "summary_sha256": "",
            "summary_policy_seed": -1,
            "resolved_common_random_numbers": False,
        }
    summary_path = (
        Path(run_dir) / "summaries" / "first_simulation_summary.json"
    ).resolve()
    if not summary_path.is_file():
        return False, {
            **identity,
            "provenance_source": "missing_summary",
            "summary_path": str(summary_path),
            "summary_sha256": "",
            "summary_policy_seed": -1,
            "resolved_common_random_numbers": False,
        }
    summary_hash_before = _sha256(summary_path)
    summary = _read_json(summary_path)
    summary_hash_after = _sha256(summary_path)
    if summary_hash_after != summary_hash_before:
        raise RuntimeError(f"Le résumé CRN a changé pendant sa lecture: {summary_path}")
    policy = summary.get("policy") or {}
    policy_seed = (
        _to_int(policy.get("seed")) if isinstance(policy, Mapping) else -1
    )
    if not isinstance(policy, Mapping) or "common_random_numbers" not in policy:
        resolved = False
    else:
        resolved = bool(
            _as_bool(policy.get("common_random_numbers"))
            and policy_seed == identity["seed"]
        )
    return resolved, {
        **identity,
        "provenance_source": "retained_run_summary",
        "summary_path": str(summary_path),
        "summary_sha256": summary_hash_before,
        "summary_policy_seed": policy_seed,
        "resolved_common_random_numbers": resolved,
    }


def _augment_resolved_pairing(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    augmented: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for row in rows:
        resolved, evidence = _resolve_common_random_numbers(row)
        augmented.append(
            {**dict(row), "resolved_common_random_numbers": resolved}
        )
        provenance.append(evidence)
    return augmented, provenance


def _verify_external_crn_provenance_unchanged(
    provenance: Sequence[Mapping[str, Any]],
) -> None:
    expected_by_path = {
        str(row.get("summary_path") or ""): str(row.get("summary_sha256") or "")
        for row in provenance
        if str(row.get("provenance_source") or "") == "retained_run_summary"
    }
    for raw_path, expected_hash in expected_by_path.items():
        path = Path(raw_path)
        if not path.is_file() or _sha256(path) != expected_hash:
            raise RuntimeError(
                f"Une preuve CRN externe a changé pendant l'audit: {path}"
            )


def _metric_values(
    row: Mapping[str, Any],
    *,
    baseline: Mapping[str, Any],
    meta: ScenarioMeta,
) -> dict[str, float]:
    context = f"{meta.scenario_id}/seed_{row.get('seed')}"
    product = meta.target_product_id
    baseline_demand = _number(
        baseline.get(f"demand_qty_{product}"),
        field=f"demand_qty_{product}",
        context=f"baseline/seed_{row.get('seed')}",
    )
    stress_demand = _number(
        row.get(f"demand_qty_{product}"),
        field=f"demand_qty_{product}",
        context=context,
    )
    target_demand = _number(
        row.get("target_demand_qty"), field="target_demand_qty", context=context
    )
    if baseline_demand <= 0.0 or stress_demand <= 0.0 or target_demand <= 0.0:
        raise ValueError(f"Dénominateur de demande non positif ({context}).")
    if not (
        _same_number(baseline_demand, stress_demand)
        and _same_number(stress_demand, target_demand)
    ):
        raise ValueError(f"Dénominateur de demande non apparié ({context}).")

    service_delta = _number(
        row.get("target_on_due_date_proxy_delta_vs_paired_baseline"),
        field="target_on_due_date_proxy_delta_vs_paired_baseline",
        context=context,
    )
    rolling_delta = _number(
        row.get("target_worst_rolling_28d_on_due_delta_vs_paired_baseline"),
        field="target_worst_rolling_28d_on_due_delta_vs_paired_baseline",
        context=context,
    )
    backlog_delta = _number(
        row.get("incremental_target_backlog_qty_days"),
        field="incremental_target_backlog_qty_days",
        context=context,
    )
    production_ratio = _number(
        row.get("target_production_shortfall_ratio_vs_paired_baseline"),
        field="target_production_shortfall_ratio_vs_paired_baseline",
        context=context,
    )
    if not -1.0 <= service_delta <= 1.0:
        raise ValueError(f"Écart de service hors de [-1, 1] ({context}).")
    if not -1.0 <= rolling_delta <= 1.0:
        raise ValueError(f"Écart glissant hors de [-1, 1] ({context}).")
    if not -NUMERICAL_TOLERANCE_RATIO <= production_ratio <= (
        1.0 + NUMERICAL_TOLERANCE_RATIO
    ):
        raise ValueError(f"Ratio de manque de production hors de [0, 1] ({context}).")

    baseline_on_due = _number(
        baseline.get(f"on_due_volume_proxy_{product}"),
        field=f"on_due_volume_proxy_{product}",
        context=f"baseline/seed_{row.get('seed')}",
    )
    stress_on_due = _number(
        row.get("product_on_due_date_proxy"),
        field="product_on_due_date_proxy",
        context=context,
    )
    declared_paired_on_due = _number(
        row.get("paired_baseline_product_on_due_date_proxy"),
        field="paired_baseline_product_on_due_date_proxy",
        context=context,
    )
    for field, value in (
        ("baseline_product_on_due_date_proxy", baseline_on_due),
        ("product_on_due_date_proxy", stress_on_due),
        ("paired_baseline_product_on_due_date_proxy", declared_paired_on_due),
    ):
        if not -NUMERICAL_TOLERANCE_RATIO <= value <= (
            1.0 + NUMERICAL_TOLERANCE_RATIO
        ):
            raise ValueError(f"Ratio {field!r} hors de [0, 1] ({context}).")
    if not _same_number(baseline_on_due, declared_paired_on_due):
        raise ValueError(f"Service de référence apparié incohérent ({context}).")
    if not _same_number(service_delta, stress_on_due - baseline_on_due):
        raise ValueError(f"Écart de service apparié incohérent ({context}).")

    baseline_rolling = _number(
        baseline.get(f"worst_rolling_28d_on_due_proxy_{product}"),
        field=f"worst_rolling_28d_on_due_proxy_{product}",
        context=f"baseline/seed_{row.get('seed')}",
    )
    stress_rolling = _number(
        row.get("target_worst_rolling_28d_on_due_proxy"),
        field="target_worst_rolling_28d_on_due_proxy",
        context=context,
    )
    declared_paired_rolling = _number(
        row.get("paired_baseline_target_worst_rolling_28d_on_due_proxy"),
        field="paired_baseline_target_worst_rolling_28d_on_due_proxy",
        context=context,
    )
    if any(
        not -NUMERICAL_TOLERANCE_RATIO <= value <= (
            1.0 + NUMERICAL_TOLERANCE_RATIO
        )
        for value in (baseline_rolling, stress_rolling, declared_paired_rolling)
    ):
        raise ValueError(f"Service glissant à 28 jours hors de [0, 1] ({context}).")
    if not _same_number(baseline_rolling, declared_paired_rolling):
        raise ValueError(f"Référence glissante appariée incohérente ({context}).")
    if not _same_number(rolling_delta, stress_rolling - baseline_rolling):
        raise ValueError(f"Écart glissant apparié incohérent ({context}).")

    stress_backlog = _number(
        row.get("target_backlog_qty_days"),
        field="target_backlog_qty_days",
        context=context,
    )
    paired_backlog = _number(
        row.get("paired_baseline_target_backlog_qty_days"),
        field="paired_baseline_target_backlog_qty_days",
        context=context,
    )
    baseline_backlog = _number(
        baseline.get(f"backlog_qty_days_{product}"),
        field=f"backlog_qty_days_{product}",
        context=f"baseline/seed_{row.get('seed')}",
    )
    if stress_backlog < -NUMERICAL_TOLERANCE_RATIO or paired_backlog < (
        -NUMERICAL_TOLERANCE_RATIO
    ):
        raise ValueError(f"Backlog quantité-jours négatif ({context}).")
    if not _same_number(paired_backlog, baseline_backlog):
        raise ValueError(f"Référence de backlog appariée incohérente ({context}).")
    if not _same_number(backlog_delta, stress_backlog - paired_backlog):
        raise ValueError(f"Écart de backlog apparié incohérent ({context}).")

    stress_released = _number(
        row.get("target_released_qty"), field="target_released_qty", context=context
    )
    paired_released = _number(
        row.get("paired_baseline_target_released_qty"),
        field="paired_baseline_target_released_qty",
        context=context,
    )
    baseline_released = _number(
        baseline.get(
            f"baseline_chain__{meta.chain_id}__ops__target_released_qty"
        ),
        field=f"baseline_chain__{meta.chain_id}__ops__target_released_qty",
        context=f"baseline/seed_{row.get('seed')}",
    )
    released_delta = _number(
        row.get("target_released_qty_delta_vs_paired_baseline"),
        field="target_released_qty_delta_vs_paired_baseline",
        context=context,
    )
    declared_shortfall = _number(
        row.get("target_production_shortfall_vs_paired_baseline"),
        field="target_production_shortfall_vs_paired_baseline",
        context=context,
    )
    if stress_released < -NUMERICAL_TOLERANCE_RATIO or paired_released <= 0.0:
        raise ValueError(f"Production libérée de référence non positive ({context}).")
    if not _same_number(paired_released, baseline_released):
        raise ValueError(f"Référence de production appariée incohérente ({context}).")
    expected_delta = stress_released - paired_released
    expected_shortfall = max(0.0, -expected_delta)
    expected_ratio = expected_shortfall / abs(paired_released)
    if not _same_number(released_delta, expected_delta):
        raise ValueError(f"Écart de production libérée apparié incohérent ({context}).")
    if not _same_number(declared_shortfall, expected_shortfall):
        raise ValueError(f"Manque de production apparié incohérent ({context}).")
    if not _same_number(production_ratio, expected_ratio):
        raise ValueError(f"Ratio de manque de production incohérent ({context}).")

    return {
        "horizon_on_due_service_delta": service_delta,
        "worst_rolling_28d_on_due_delta": rolling_delta,
        "incremental_backlog_days_per_requested_unit": (
            backlog_delta / target_demand
        ),
        "released_production_shortfall_ratio": max(0.0, production_ratio),
    }


def _validate_ranking(
    rows: Sequence[Mapping[str, Any]], suppliers: set[str]
) -> tuple[str, ...]:
    if len(rows) != len(suppliers):
        raise ValueError("Le classement fournisseur ne couvre pas le périmètre exact.")
    ordered = sorted(
        rows,
        key=lambda row: _to_int(row.get("supplier_sensitivity_rank")),
    )
    ranks = [_to_int(row.get("supplier_sensitivity_rank")) for row in ordered]
    ids = [str(row.get("supplier_id") or "") for row in ordered]
    if ranks != list(range(1, len(rows) + 1)):
        raise ValueError("Les rangs fournisseur ne sont pas séquentiels.")
    if set(ids) != suppliers or len(set(ids)) != len(ids):
        raise ValueError("Les identifiants fournisseur du classement sont incohérents.")
    if any(
        str(row.get("evidence_stage") or "") != "confirmation_30_realisations"
        for row in ordered
    ):
        raise ValueError("Le classement n'est pas intégralement fondé sur 30 graines.")
    return tuple(ids)


def validate_confirmation_matrix(
    rows: Sequence[Mapping[str, Any]],
    *,
    selected_scenario_ids: Sequence[str],
    scenario_meta: Mapping[str, ScenarioMeta],
    ranking_rows: Sequence[Mapping[str, Any]],
    enforce_industrial_scope: bool = True,
) -> dict[str, Any]:
    """Validate the exact 30 + 36×30 paired confirmation matrix."""

    selected = tuple(sorted(set(selected_scenario_ids)))
    if len(selected) != len(selected_scenario_ids):
        raise ValueError("La sélection contient des scénarios dupliqués.")
    if set(selected) != set(scenario_meta):
        raise ValueError("La sélection et les métadonnées scénario diffèrent.")
    if enforce_industrial_scope and len(selected) != EXPECTED_CONFIRMED_SCENARIO_COUNT:
        raise ValueError("La confirmation finale exige exactement 36 scénarios.")
    if {
        meta.failure_mode for meta in scenario_meta.values()
    } != CONFIRMED_FAILURE_MODES:
        raise ValueError("Les deux familles confirmées attendues ne sont pas exactes.")
    for meta in scenario_meta.values():
        _validate_scenario_meta_contract(meta)
    modes_by_chain: dict[str, set[str]] = defaultdict(set)
    lane_identity_by_chain: dict[
        str, set[tuple[str, str, str, str, int, int]]
    ] = defaultdict(set)
    for meta in scenario_meta.values():
        modes_by_chain[meta.chain_id].add(meta.failure_mode)
        lane_identity_by_chain[meta.chain_id].add(
            (
                meta.supplier_id,
                meta.item_id,
                meta.dst_node_id,
                meta.target_product_id,
                meta.stress_start_day,
                meta.stress_end_day,
            )
        )
    if any(modes != CONFIRMED_FAILURE_MODES for modes in modes_by_chain.values()):
        raise ValueError("Chaque voie doit avoir exactement les deux familles confirmées.")
    if any(len(identities) != 1 for identities in lane_identity_by_chain.values()):
        raise ValueError(
            "L'identité physique d'une voie diffère entre les deux familles."
        )
    if enforce_industrial_scope and len(modes_by_chain) != EXPECTED_ACTIVE_LANE_COUNT:
        raise ValueError("La confirmation finale exige exactement 18 voies actives.")

    keys: list[tuple[str, int]] = []
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "")
        seed = _to_int(row.get("seed"))
        if not scenario_id or seed < 0:
            raise ValueError("Ligne de confirmation sans scénario ou graine valide.")
        if str(row.get("stage") or "") != "confirmation":
            raise ValueError(f"Ligne hors étape confirmation: {scenario_id}/seed_{seed}")
        keys.append((scenario_id, seed))
    if len(set(keys)) != len(keys):
        raise ValueError("La matrice de confirmation contient des clés dupliquées.")

    baseline_rows = [
        row
        for row in rows
        if str(row.get("scenario_id") or "") == BASELINE_SCENARIO_ID
    ]
    seeds = tuple(sorted(_to_int(row.get("seed")) for row in baseline_rows))
    if len(seeds) != EXPECTED_BASELINE_COUNT or len(set(seeds)) != len(seeds):
        raise ValueError("Il faut exactement 30 références, une par graine.")
    expected_keys = {
        (BASELINE_SCENARIO_ID, seed) for seed in seeds
    } | {(scenario_id, seed) for scenario_id in selected for seed in seeds}
    actual_keys = set(keys)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(
            "Matrice de confirmation non exacte: "
            f"manquantes={missing[:4]}, supplémentaires={extra[:4]}"
        )
    expected_count = len(expected_keys)
    if enforce_industrial_scope and expected_count != EXPECTED_TOTAL_ROW_COUNT:
        raise ValueError("Le contrat final exige 1 110 lignes physiques uniques.")
    if len(rows) != expected_count:
        raise ValueError("Le nombre de lignes ne correspond pas à la matrice attendue.")

    by_key = {
        (str(row.get("scenario_id") or ""), _to_int(row.get("seed"))): row
        for row in rows
    }
    baselines = {
        seed: by_key[(BASELINE_SCENARIO_ID, seed)] for seed in seeds
    }
    pairing_j0 = True
    pairing_input = True
    pairing_crn = True
    pairing_valid = all(_as_bool(row.get("valid")) for row in baseline_rows)
    demand_pairing = True
    target_products = sorted(
        {meta.target_product_id for meta in scenario_meta.values()}
    )
    if set(target_products) != EXPECTED_TARGET_PRODUCTS:
        raise ValueError("Le périmètre doit couvrir exactement les deux produits cibles.")
    baseline_service_gate = True
    for seed, baseline in baselines.items():
        for product in target_products:
            baseline_service = _number(
                baseline.get(f"on_due_volume_proxy_{product}"),
                field=f"on_due_volume_proxy_{product}",
                context=f"baseline/seed_{seed}",
            )
            if not 0.0 <= baseline_service <= 1.0 + NUMERICAL_TOLERANCE_RATIO:
                raise ValueError(
                    f"Service de référence hors de [0, 1] (seed_{seed}/{product})."
                )
            baseline_service_gate = (
                baseline_service_gate and baseline_service >= 0.95 - 1e-12
            )
    horizon_gate = all(
        _to_int(row.get("summary_sim_days")) == 720
        and _to_int(row.get("summary_timeline_days")) == 720
        for row in rows
    )
    active_flow_by_chain_seed: dict[
        tuple[str, int], list[tuple[float, float]]
    ] = defaultdict(list)
    metric_values_by_case: dict[tuple[str, int], dict[str, float]] = {}
    for scenario_id in selected:
        meta = scenario_meta[scenario_id]
        for seed in seeds:
            row = by_key[(scenario_id, seed)]
            baseline = baselines[seed]
            if str(row.get("chain_id") or "") != meta.chain_id:
                raise ValueError(f"Voie incohérente ({scenario_id}/seed_{seed}).")
            if str(row.get("target_product_id") or "") != meta.target_product_id:
                raise ValueError(f"Produit incohérent ({scenario_id}/seed_{seed}).")
            row_contract = {
                "mechanism": meta.failure_mode,
                "level_code": meta.level_code,
                "mechanism_unit": meta.mechanism_unit,
            }
            for field, expected in row_contract.items():
                if str(row.get(field) or "") != expected:
                    raise ValueError(
                        f"Contrat {field} incohérent ({scenario_id}/seed_{seed})."
                    )
            if not _same_number(
                _number(
                    row.get("mechanism_value"),
                    field="mechanism_value",
                    context=f"{scenario_id}/seed_{seed}",
                ),
                meta.mechanism_value,
            ):
                raise ValueError(
                    f"Amplitude de stress incohérente ({scenario_id}/seed_{seed})."
                )
            if (
                _to_int(row.get("stress_start_day")) != meta.stress_start_day
                or _to_int(row.get("stress_end_day")) != meta.stress_end_day
            ):
                raise ValueError(
                    f"Fenêtre de stress incohérente ({scenario_id}/seed_{seed})."
                )
            if str(row.get("effect_status") or "") not in EFFECT_STATUSES:
                raise ValueError(
                    f"Statut d'effet inconnu ({scenario_id}/seed_{seed})."
                )
            pairing_valid = pairing_valid and _as_bool(row.get("valid"))
            stress_j0 = str(row.get("j0_state_sha256") or "")
            base_j0 = str(baseline.get("j0_state_sha256") or "")
            pairing_j0 = pairing_j0 and bool(stress_j0) and stress_j0 == base_j0
            stress_input = str(row.get("input_sha256") or "")
            base_input = str(baseline.get("input_sha256") or "")
            pairing_input = (
                pairing_input and bool(stress_input) and stress_input == base_input
            )
            pairing_crn = (
                pairing_crn
                and _as_bool(row.get("resolved_common_random_numbers"))
                and _as_bool(baseline.get("resolved_common_random_numbers"))
            )
            paired_pulled = _number(
                row.get("paired_baseline_active_window_pulled_qty"),
                field="paired_baseline_active_window_pulled_qty",
                context=f"{scenario_id}/seed_{seed}",
            )
            paired_shipped = _number(
                row.get("paired_baseline_active_window_shipped_qty"),
                field="paired_baseline_active_window_shipped_qty",
                context=f"{scenario_id}/seed_{seed}",
            )
            baseline_pulled = _number(
                baseline.get(
                    f"baseline_chain__{meta.chain_id}__active_window_pulled_qty"
                ),
                field=(
                    f"baseline_chain__{meta.chain_id}__active_window_pulled_qty"
                ),
                context=f"baseline/seed_{seed}",
            )
            baseline_shipped = _number(
                baseline.get(
                    f"baseline_chain__{meta.chain_id}__active_window_shipped_qty"
                ),
                field=(
                    f"baseline_chain__{meta.chain_id}__active_window_shipped_qty"
                ),
                context=f"baseline/seed_{seed}",
            )
            if not _same_number(paired_pulled, baseline_pulled) or not _same_number(
                paired_shipped, baseline_shipped
            ):
                raise ValueError(
                    "Flux de référence apparié incohérent avec la baseline "
                    f"({meta.chain_id}/seed_{seed})."
                )
            active_flow_by_chain_seed[(meta.chain_id, seed)].append(
                (paired_pulled, paired_shipped)
            )
            try:
                metric_values_by_case[(scenario_id, seed)] = _metric_values(
                    row, baseline=baseline, meta=meta
                )
            except ValueError:
                demand_pairing = False
                raise
    if not pairing_valid:
        raise ValueError("Au moins une ligne de confirmation n'est pas valide.")
    if not pairing_j0:
        raise ValueError("L'état J0 n'est pas strictement apparié sur toutes les lignes.")
    if not pairing_input:
        raise ValueError("Le graphe d'entrée n'est pas strictement apparié.")
    if not pairing_crn:
        raise ValueError("Les tirages aléatoires communs ne sont pas résolus partout.")
    if len(
        {
            str(row.get("input_sha256") or "")
            for row in rows
            if str(row.get("input_sha256") or "")
        }
    ) != 1:
        raise ValueError("Le graphe d'entrée n'a pas une empreinte unique.")
    if not demand_pairing:
        raise ValueError("La demande servant de dénominateur n'est pas appariée.")
    positive_flow_seeds_by_chain: dict[str, set[int]] = defaultdict(set)
    for chain_id in modes_by_chain:
        for seed in seeds:
            values = active_flow_by_chain_seed.get((chain_id, seed), [])
            if len(values) != len(CONFIRMED_FAILURE_MODES):
                raise ValueError(
                    f"Flux de référence incomplet ({chain_id}/seed_{seed})."
                )
            first_pulled, first_shipped = values[0]
            if any(
                not _same_number(pulled, first_pulled)
                or not _same_number(shipped, first_shipped)
                for pulled, shipped in values[1:]
            ):
                raise ValueError(
                    "Flux de référence apparié incohérent entre familles "
                    f"({chain_id}/seed_{seed})."
                )
            if first_pulled > 1e-12 and first_shipped > 1e-12:
                positive_flow_seeds_by_chain[chain_id].add(seed)
    active_flow_gate = all(
        len(positive_flow_seeds_by_chain.get(chain_id, set()))
        >= REQUIRED_TOP3_PRESENCE_COUNT
        for chain_id in modes_by_chain
    )

    suppliers = {meta.supplier_id for meta in scenario_meta.values()}
    if enforce_industrial_scope and len(suppliers) != EXPECTED_SUPPLIER_COUNT:
        raise ValueError("Le périmètre final exige exactement 16 fournisseurs actifs.")
    ranking_order = _validate_ranking(ranking_rows, suppliers)
    return {
        "seeds": seeds,
        "selected_scenario_ids": selected,
        "by_key": by_key,
        "baselines": baselines,
        "metric_values_by_case": metric_values_by_case,
        "supplier_ids": tuple(sorted(suppliers)),
        "main_ranking_order": ranking_order,
        "confirmation_matrix_exact_pass": True,
        "expected_baseline_row_count": len(seeds),
        "actual_baseline_row_count": len(baseline_rows),
        "expected_stress_scenario_count": len(selected),
        "expected_stress_row_count": len(selected) * len(seeds),
        "actual_stress_row_count": len(rows) - len(baseline_rows),
        "actual_total_row_count": len(rows),
        "all_metric_rows_valid_pass": pairing_valid,
        "j0_state_hash_pairing_all_rows_pass": pairing_j0,
        "input_graph_hash_pairing_all_rows_pass": pairing_input,
        "resolved_common_random_numbers_all_pairs_pass": pairing_crn,
        "horizon_J0_J719_all_rows_pass": horizon_gate,
        "paired_active_window_baseline_identical_between_failure_modes_pass": True,
        "paired_target_demand_identical_and_positive_all_rows_pass": demand_pairing,
        "paired_metric_arithmetic_recomputed_from_physical_baseline_pass": True,
        "baseline_both_products_on_due_at_least_95_all_seeds_pass": (
            baseline_service_gate
        ),
        "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": (
            active_flow_gate
        ),
    }


def _supplier_scenarios(
    scenario_meta: Mapping[str, ScenarioMeta]
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for scenario_id, meta in scenario_meta.items():
        grouped[meta.supplier_id].append(scenario_id)
    return {
        supplier: tuple(sorted(scenarios))
        for supplier, scenarios in sorted(grouped.items())
    }


def _scenario_metric_means(
    *,
    selected_scenarios: Sequence[str],
    seeds: Sequence[int],
    metric_values_by_case: Mapping[tuple[str, int], Mapping[str, float]],
    sample: Sequence[int] | None = None,
) -> dict[str, dict[str, float]]:
    selected_seed_values = (
        [seeds[index] for index in sample] if sample is not None else list(seeds)
    )
    result: dict[str, dict[str, float]] = {}
    for scenario_id in selected_scenarios:
        result[scenario_id] = {}
        for metric in METRICS:
            values = [
                metric_values_by_case[(scenario_id, seed)][metric.key]
                for seed in selected_seed_values
            ]
            result[scenario_id][metric.key] = sum(values) / len(values)
    return result


def _supplier_metric_values(
    scenario_means: Mapping[str, Mapping[str, float]],
    supplier_scenarios: Mapping[str, Sequence[str]],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for supplier, scenario_ids in supplier_scenarios.items():
        result[supplier] = {}
        for metric in METRICS:
            values = [scenario_means[scenario_id][metric.key] for scenario_id in scenario_ids]
            result[supplier][metric.key] = (
                min(values) if metric.direction == "lower_is_worse" else max(values)
            )
    return result


def _supplier_metric_driver_scenario(
    *,
    supplier: str,
    metric: MetricSpec,
    scenario_means: Mapping[str, Mapping[str, float]],
    supplier_scenarios: Mapping[str, Sequence[str]],
) -> str:
    candidates = supplier_scenarios[supplier]
    if metric.direction == "lower_is_worse":
        return min(
            candidates,
            key=lambda scenario_id: (
                scenario_means[scenario_id][metric.key],
                scenario_id,
            ),
        )
    return min(
        candidates,
        key=lambda scenario_id: (
            -scenario_means[scenario_id][metric.key],
            scenario_id,
        ),
    )


def _metric_ranking(
    supplier_values: Mapping[str, Mapping[str, float]], metric: MetricSpec
) -> tuple[str, ...]:
    if metric.direction == "lower_is_worse":
        return tuple(
            sorted(
                supplier_values,
                key=lambda supplier: (supplier_values[supplier][metric.key], supplier),
            )
        )
    return tuple(
        sorted(
            supplier_values,
            key=lambda supplier: (-supplier_values[supplier][metric.key], supplier),
        )
    )


def _metric_presence_counts(
    *,
    metric: MetricSpec,
    fixed_ranking: Sequence[str],
    seeds: Sequence[int],
    metric_values_by_case: Mapping[tuple[str, int], Mapping[str, float]],
    supplier_scenarios: Mapping[str, Sequence[str]],
) -> dict[str, int]:
    counts = {supplier: 0 for supplier in fixed_ranking}
    for seed in seeds:
        values: dict[str, float] = {}
        for supplier, scenario_ids in supplier_scenarios.items():
            candidates = [
                metric_values_by_case[(scenario_id, seed)][metric.key]
                for scenario_id in scenario_ids
            ]
            values[supplier] = (
                min(candidates)
                if metric.direction == "lower_is_worse"
                else max(candidates)
            )
        # A supplier is counted only when it belongs to the first three
        # without any identifier-based tie break.  If an equality straddles
        # the rank-3/rank-4 boundary, neither tied candidate is credited.
        for supplier, value in values.items():
            if metric.direction == "lower_is_worse":
                strictly_more_adverse = sum(
                    other < value - NUMERICAL_TOLERANCE_RATIO
                    for other in values.values()
                )
            else:
                strictly_more_adverse = sum(
                    other > value + NUMERICAL_TOLERANCE_RATIO
                    for other in values.values()
                )
            numerically_tied = sum(
                abs(other - value) <= NUMERICAL_TOLERANCE_RATIO
                for other in values.values()
            )
            if strictly_more_adverse + numerically_tied <= 3:
                counts[supplier] += 1
    return counts


def _gap(metric: MetricSpec, rank3_value: float, rank4_value: float) -> float:
    if metric.direction == "lower_is_worse":
        return rank4_value - rank3_value
    return rank3_value - rank4_value


def _adverse(metric: MetricSpec, value: float) -> float:
    return -value if metric.direction == "lower_is_worse" else value


def _metric_boundary_payload(
    *,
    metric: MetricSpec,
    order: Sequence[str],
    supplier_values: Mapping[str, Mapping[str, float]],
    bootstrap_values: Mapping[str, Sequence[float]],
    presence: Mapping[str, int],
    release_inputs_pass: bool,
) -> dict[str, Any]:
    if len(order) < 4:
        raise ValueError("Quatre fournisseurs sont requis pour auditer la frontière.")
    rank3, rank4 = order[2], order[3]
    rank3_point = supplier_values[rank3][metric.key]
    rank4_point = supplier_values[rank4][metric.key]
    selected_set = tuple(order[:3])
    outsiders = tuple(order[3:])
    displayed_set = tuple(sorted(selected_set))
    adverse_points = {
        supplier: _adverse(metric, supplier_values[supplier][metric.key])
        for supplier in order
    }
    selected_minimum_adverse_point = min(
        adverse_points[supplier] for supplier in selected_set
    )
    outsider_maximum_adverse_point = max(
        adverse_points[supplier] for supplier in outsiders
    )
    point_gap = (
        selected_minimum_adverse_point - outsider_maximum_adverse_point
    )
    bootstrap_count = len(bootstrap_values[selected_set[0]])
    if any(
        len(bootstrap_values[supplier]) != bootstrap_count for supplier in order
    ):
        raise ValueError("Blocs bootstrap incomplets entre fournisseurs.")
    selected_minimum_adverse_samples = [
        min(
            _adverse(metric, bootstrap_values[supplier][index])
            for supplier in selected_set
        )
        for index in range(bootstrap_count)
    ]
    outsider_maximum_adverse_samples = [
        max(
            _adverse(metric, bootstrap_values[supplier][index])
            for supplier in outsiders
        )
        for index in range(bootstrap_count)
    ]
    gap_samples = [
        selected - outsider
        for selected, outsider in zip(
            selected_minimum_adverse_samples,
            outsider_maximum_adverse_samples,
            strict=True,
        )
    ]
    gap_low = _percentile(gap_samples, 0.025)
    gap_high = _percentile(gap_samples, 0.975)
    adverse_low = _percentile(selected_minimum_adverse_samples, 0.025)
    adverse_high = _percentile(selected_minimum_adverse_samples, 0.975)
    membership_pass = all(
        presence[supplier] >= REQUIRED_TOP3_PRESENCE_COUNT
        for supplier in selected_set
    )
    selected_set_reporting_threshold_pass = (
        selected_minimum_adverse_point + 1e-15 >= metric.reportable_gap
    )
    selected_set_numerical_effect_pass = (
        adverse_low > NUMERICAL_TOLERANCE_RATIO
    )
    statistical_gap_pass = gap_low > NUMERICAL_TOLERANCE_RATIO
    reporting_gap_pass = point_gap + 1e-15 >= metric.reportable_gap
    boundary_statistics_pass = bool(
        membership_pass
        and selected_set_reporting_threshold_pass
        and selected_set_numerical_effect_pass
        and statistical_gap_pass
        and reporting_gap_pass
    )
    descriptive_display_allowed = bool(
        release_inputs_pass and boundary_statistics_pass
    )
    nonseparation_group = set(selected_set)
    maximum_allowed_outsider_presence = (
        EXPECTED_BASELINE_COUNT - REQUIRED_TOP3_PRESENCE_COUNT
    )
    for outsider in outsiders:
        outsider_gap_point = (
            selected_minimum_adverse_point - adverse_points[outsider]
        )
        outsider_gap_samples = [
            selected - _adverse(metric, bootstrap_values[outsider][index])
            for index, selected in enumerate(
                selected_minimum_adverse_samples
            )
        ]
        if (
            _percentile(outsider_gap_samples, 0.025)
            <= NUMERICAL_TOLERANCE_RATIO
            or outsider_gap_point + 1e-15 < metric.reportable_gap
            or presence[outsider] > maximum_allowed_outsider_presence
        ):
            nonseparation_group.add(outsider)
    return {
        "metric_key": metric.key,
        "metric_label": metric.label,
        "unit": metric.unit,
        "direction": metric.direction,
        "descriptive_first_three_supplier_ids": list(selected_set),
        "fixed_selected_set_supplier_ids": list(displayed_set),
        "displayed_scoped_priority_supplier_ids": (
            list(displayed_set) if descriptive_display_allowed else []
        ),
        "nonseparation_group_supplier_ids": sorted(nonseparation_group),
        "rank3_supplier_id": rank3,
        "rank4_supplier_id": rank4,
        "rank3_metric_point": rank3_point,
        "rank4_metric_point": rank4_point,
        "rank3_adverse_magnitude_point": _adverse(metric, rank3_point),
        "rank3_rank4_pair_used_as_boundary_gate": False,
        "selected_set_minimum_adverse_magnitude_point": (
            selected_minimum_adverse_point
        ),
        "selected_set_minimum_adverse_magnitude_resampling95_low": (
            adverse_low
        ),
        "selected_set_minimum_adverse_magnitude_resampling95_high": (
            adverse_high
        ),
        "outsiders_maximum_adverse_magnitude_point": (
            outsider_maximum_adverse_point
        ),
        "boundary_gap_definition": (
            "minimum_adverse_magnitude_in_fixed_selected_set_minus_"
            "maximum_adverse_magnitude_among_all_outsiders"
        ),
        "boundary_gap_point": point_gap,
        "boundary_gap_resampling95_low": gap_low,
        "boundary_gap_resampling95_high": gap_high,
        "numerical_tolerance": NUMERICAL_TOLERANCE_RATIO,
        "minimum_reportable_gap": metric.reportable_gap,
        "selected_set_minimum_reporting_threshold": metric.reportable_gap,
        "top3_presence_required_seed_count": REQUIRED_TOP3_PRESENCE_COUNT,
        "top3_presence_seed_counts": {
            supplier: presence[supplier] for supplier in displayed_set
        },
        "fixed_selected_set_presence_rule_pass": membership_pass,
        "top3_membership_stability_pass": False,
        "selected_set_all_above_predeclared_reporting_threshold_pass": (
            selected_set_reporting_threshold_pass
        ),
        "selected_set_numerical_effect_resampling_pass": (
            selected_set_numerical_effect_pass
        ),
        "fixed_selected_set_vs_all_outsiders_resampling_gap_rule_pass": (
            statistical_gap_pass
        ),
        "boundary_statistical_separation_pass": False,
        "boundary_reporting_resolution_pass": reporting_gap_pass,
        "descriptive_boundary_rule_pass": boundary_statistics_pass,
        "descriptive_display_inputs_pass": release_inputs_pass,
        "scientific_release_inputs_pass": False,
        "scoped_descriptive_set_display_allowed": descriptive_display_allowed,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "metric_priority_set_release_pass": False,
        "released_priority_supplier_ids": [],
        "selection_and_assessment_seed_blocks_independent": False,
        "post_selection_inference_correction_applied": False,
        "resampling_interval_is_confirmatory_population_interval": False,
        "resampling_interpretation": (
            "descriptive_same_30_seed_blocks_used_for_selection_and_assessment"
        ),
        "identifier_tie_break_used_as_scientific_evidence": False,
    }


def _display_effect_indicators(
    values: Mapping[str, float],
) -> tuple[bool, bool, bool]:
    client_threshold_exceeded = bool(
        values["horizon_on_due_service_delta"]
        <= -DISPLAY_CLIENT_SERVICE_LOSS_RATIO + 1e-15
        or values["incremental_backlog_days_per_requested_unit"]
        >= DISPLAY_CLIENT_BACKLOG_DAYS_PER_REQUESTED_UNIT - 1e-15
    )
    production_threshold_exceeded = bool(
        values["released_production_shortfall_ratio"]
        >= DISPLAY_PRODUCTION_SHORTFALL_RATIO - 1e-15
    )
    numerical_propagation = any(
        _adverse(metric, values[metric.key]) > NUMERICAL_TOLERANCE_RATIO
        for metric in METRICS
    )
    return (
        client_threshold_exceeded,
        production_threshold_exceeded,
        numerical_propagation,
    )


def _conditional_effect_rows(
    *,
    rows_by_key: Mapping[tuple[str, int], Mapping[str, Any]],
    metric_values_by_case: Mapping[tuple[str, int], Mapping[str, float]],
    seeds: Sequence[int],
    selected_scenarios: Sequence[str],
    scenario_meta: Mapping[str, ScenarioMeta],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    supplier_scenarios = _supplier_scenarios(scenario_meta)
    supplier_lane_counts = {
        supplier: len(
            {scenario_meta[scenario_id].chain_id for scenario_id in scenario_ids}
        )
        for supplier, scenario_ids in supplier_scenarios.items()
    }
    exposure_balanced = len(set(supplier_lane_counts.values())) == 1

    def count_payload(scoped_scenario_ids: Sequence[str]) -> dict[str, Any]:
        display_client = 0
        display_production = 0
        any_numerical = 0
        source_client = 0
        source_production_only = 0
        source_upstream_absorbed = 0
        source_all_no_effect = 0
        source_any_inactive = 0
        for seed in seeds:
            indicators = [
                _display_effect_indicators(
                    metric_values_by_case[(scenario_id, seed)]
                )
                for scenario_id in scoped_scenario_ids
            ]
            display_client += any(value[0] for value in indicators)
            display_production += any(value[1] for value in indicators)
            any_numerical += any(value[2] for value in indicators)
            statuses = {
                str(rows_by_key[(scenario_id, seed)].get("effect_status") or "")
                for scenario_id in scoped_scenario_ids
            }
            source_client += "effet_mesure_sur_le_service_client" in statuses
            source_production_only += (
                "effet_mesure_sur_la_production_mais_pas_sur_le_service_client"
                in statuses
            )
            source_upstream_absorbed += (
                "effet_amont_absorbe_avant_le_client" in statuses
            )
            source_all_no_effect += statuses == {
                "stress_applique_sans_effet_mesurable"
            }
            source_any_inactive += (
                "voie_non_sollicitee_pendant_la_fenetre_de_stress" in statuses
            )
        return {
            "paired_seed_count": len(seeds),
            "display_threshold_exceedance_client_effect_seed_count": (
                display_client
            ),
            "display_threshold_exceedance_production_effect_seed_count": (
                display_production
            ),
            "any_numerical_propagation_seed_count": any_numerical,
            "source_effect_status_client_seed_count": source_client,
            "source_effect_status_production_only_seed_count": (
                source_production_only
            ),
            "source_effect_status_upstream_absorbed_seed_count": (
                source_upstream_absorbed
            ),
            "source_effect_status_all_no_effect_seed_count": source_all_no_effect,
            "source_effect_status_any_inactive_window_seed_count": (
                source_any_inactive
            ),
            "source_effect_status_used_for_display_threshold_counts": False,
            "display_client_service_loss_ratio_threshold": (
                DISPLAY_CLIENT_SERVICE_LOSS_RATIO
            ),
            "display_client_backlog_days_per_requested_unit_threshold": (
                DISPLAY_CLIENT_BACKLOG_DAYS_PER_REQUESTED_UNIT
            ),
            "display_production_shortfall_ratio_threshold": (
                DISPLAY_PRODUCTION_SHORTFALL_RATIO
            ),
            "business_materiality_threshold_validated": False,
            "thresholds_are_model_reporting_conventions": True,
            "interpretation": (
                "count_among_30_conditional_model_draws_not_probability_or_frequency"
            ),
            "historical_occurrence_probability": "not_estimated",
        }

    for scenario_id in selected_scenarios:
        meta = scenario_meta[scenario_id]
        result.append(
            {
                "aggregation_level": "scenario",
                "aggregation_scope": "single_scenario_single_failure_mode",
                "supplier_id": meta.supplier_id,
                "scenario_id": scenario_id,
                "chain_id": meta.chain_id,
                "item_id": meta.item_id,
                "dst_node_id": meta.dst_node_id,
                "failure_mode": meta.failure_mode,
                "hypothesis_family": HYPOTHESIS_FAMILY_BY_FAILURE_MODE[
                    meta.failure_mode
                ],
                "supplier_lane_count": supplier_lane_counts[meta.supplier_id],
                "tested_scenario_count": 1,
                "supplier_any_effect_seed_count_cross_supplier_comparable": True,
                **count_payload((scenario_id,)),
            }
        )

    for supplier, scenario_ids in supplier_scenarios.items():
        scope_definitions = [
            (
                "supplier_failure_mode_specific",
                "failure_mode_specific",
                failure_mode,
                HYPOTHESIS_FAMILY_BY_FAILURE_MODE[failure_mode],
                tuple(
                    scenario_id
                    for scenario_id in scenario_ids
                    if scenario_meta[scenario_id].failure_mode == failure_mode
                ),
            )
            for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
        ] + [
            (
                "supplier_any_confirmed_scenario",
                "any_of_two_predeclared_hypotheses",
                "|".join(sorted(CONFIRMED_FAILURE_MODES)),
                "worst_or_any_of_date_shift_and_usable_quantity_loss",
                tuple(scenario_ids),
            )
        ]
        for (
            aggregation_level,
            aggregation_scope,
            failure_mode,
            hypothesis_family,
            scoped_scenario_ids,
        ) in scope_definitions:
            result.append(
                {
                    "aggregation_level": aggregation_level,
                    "aggregation_scope": aggregation_scope,
                    "supplier_id": supplier,
                    "scenario_id": "",
                    "chain_id": "|".join(
                        sorted(
                            {
                                scenario_meta[item].chain_id
                                for item in scoped_scenario_ids
                            }
                        )
                    ),
                    "item_id": "|".join(
                        sorted(
                            {
                                scenario_meta[item].item_id
                                for item in scoped_scenario_ids
                            }
                        )
                    ),
                    "dst_node_id": "|".join(
                        sorted(
                            {
                                scenario_meta[item].dst_node_id
                                for item in scoped_scenario_ids
                            }
                        )
                    ),
                    "failure_mode": failure_mode,
                    "hypothesis_family": hypothesis_family,
                    "supplier_lane_count": supplier_lane_counts[supplier],
                    "tested_scenario_count": len(scoped_scenario_ids),
                    "supplier_any_effect_seed_count_cross_supplier_comparable": (
                        exposure_balanced
                    ),
                    **count_payload(scoped_scenario_ids),
                }
            )
    return result


def analyze_priority_boundary(
    *,
    confirmation_rows: Sequence[Mapping[str, Any]],
    selected_scenario_ids: Sequence[str],
    scenario_meta: Mapping[str, ScenarioMeta],
    ranking_rows: Sequence[Mapping[str, Any]],
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
    enforce_industrial_scope: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the JSON audit, separate metric rankings and effect seed counts."""

    matrix = validate_confirmation_matrix(
        confirmation_rows,
        selected_scenario_ids=selected_scenario_ids,
        scenario_meta=scenario_meta,
        ranking_rows=ranking_rows,
        enforce_industrial_scope=enforce_industrial_scope,
    )
    execution_integrity_pass = all(
        bool(matrix[field])
        for field in (
            "confirmation_matrix_exact_pass",
            "all_metric_rows_valid_pass",
            "j0_state_hash_pairing_all_rows_pass",
            "input_graph_hash_pairing_all_rows_pass",
            "resolved_common_random_numbers_all_pairs_pass",
            "paired_active_window_baseline_identical_between_failure_modes_pass",
            "paired_target_demand_identical_and_positive_all_rows_pass",
            "paired_metric_arithmetic_recomputed_from_physical_baseline_pass",
            "horizon_J0_J719_all_rows_pass",
        )
    )
    interpretation_prerequisites_pass = all(
        bool(matrix[field])
        for field in (
            "baseline_both_products_on_due_at_least_95_all_seeds_pass",
            "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass",
        )
    )
    scientific_inputs_pass = bool(
        execution_integrity_pass and interpretation_prerequisites_pass
    )
    seeds: tuple[int, ...] = matrix["seeds"]
    selected: tuple[str, ...] = matrix["selected_scenario_ids"]
    supplier_scenarios = _supplier_scenarios(scenario_meta)
    family_supplier_scenarios = {
        failure_mode: {
            supplier: tuple(
                scenario_id
                for scenario_id in scenario_ids
                if scenario_meta[scenario_id].failure_mode == failure_mode
            )
            for supplier, scenario_ids in supplier_scenarios.items()
        }
        for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
    }
    if any(
        not scenario_ids
        for grouped in family_supplier_scenarios.values()
        for scenario_ids in grouped.values()
    ):
        raise ValueError("Chaque fournisseur doit être testé dans chaque famille.")
    aggregate_scenario_means = _scenario_metric_means(
        selected_scenarios=selected,
        seeds=seeds,
        metric_values_by_case=matrix["metric_values_by_case"],
    )
    aggregate_supplier_values = _supplier_metric_values(
        aggregate_scenario_means, supplier_scenarios
    )
    metric_orders = {
        metric.key: _metric_ranking(aggregate_supplier_values, metric)
        for metric in METRICS
    }
    family_supplier_values = {
        failure_mode: _supplier_metric_values(
            aggregate_scenario_means, grouped_scenarios
        )
        for failure_mode, grouped_scenarios in family_supplier_scenarios.items()
    }
    family_metric_orders = {
        failure_mode: {
            metric.key: _metric_ranking(values, metric) for metric in METRICS
        }
        for failure_mode, values in family_supplier_values.items()
    }

    service_values = aggregate_supplier_values
    ranking_by_supplier = {
        str(row.get("supplier_id") or ""): row for row in ranking_rows
    }
    for supplier in matrix["supplier_ids"]:
        declared = _number(
            ranking_by_supplier[supplier].get("worst_service_delta"),
            field="worst_service_delta",
            context=f"classement/{supplier}",
        )
        computed = service_values[supplier]["horizon_on_due_service_delta"]
        if not _same_number(declared, computed):
            raise ValueError(
                f"Le classement source et les lignes physiques divergent pour {supplier}."
            )
    source_service_order = tuple(matrix["main_ranking_order"])
    for more_adverse, less_adverse in zip(
        source_service_order, source_service_order[1:], strict=False
    ):
        if (
            service_values[more_adverse]["horizon_on_due_service_delta"]
            > service_values[less_adverse]["horizon_on_due_service_delta"]
            + NUMERICAL_TOLERANCE_RATIO
        ):
            raise ValueError(
                "Les rangs service du fichier source ne sont pas monotones avec "
                "les différences appariées physiques."
            )

    presence_by_metric = {
        metric.key: _metric_presence_counts(
            metric=metric,
            fixed_ranking=metric_orders[metric.key],
            seeds=seeds,
            metric_values_by_case=matrix["metric_values_by_case"],
            supplier_scenarios=supplier_scenarios,
        )
        for metric in METRICS
    }
    family_presence_by_metric = {
        failure_mode: {
            metric.key: _metric_presence_counts(
                metric=metric,
                fixed_ranking=family_metric_orders[failure_mode][metric.key],
                seeds=seeds,
                metric_values_by_case=matrix["metric_values_by_case"],
                supplier_scenarios=grouped_scenarios,
            )
            for metric in METRICS
        }
        for failure_mode, grouped_scenarios in family_supplier_scenarios.items()
    }

    bootstrap_samples = _bootstrap_indices(len(seeds), resamples)
    bootstrap_supplier_values: dict[str, dict[str, list[float]]] = {
        metric.key: {supplier: [] for supplier in matrix["supplier_ids"]}
        for metric in METRICS
    }
    bootstrap_family_supplier_values = {
        failure_mode: {
            metric.key: {supplier: [] for supplier in matrix["supplier_ids"]}
            for metric in METRICS
        }
        for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
    }
    for sample in bootstrap_samples:
        scenario_means = _scenario_metric_means(
            selected_scenarios=selected,
            seeds=seeds,
            metric_values_by_case=matrix["metric_values_by_case"],
            sample=sample,
        )
        supplier_values = _supplier_metric_values(
            scenario_means, supplier_scenarios
        )
        sampled_family_values = {
            failure_mode: _supplier_metric_values(
                scenario_means, grouped_scenarios
            )
            for failure_mode, grouped_scenarios in (
                family_supplier_scenarios.items()
            )
        }
        for metric in METRICS:
            for supplier in matrix["supplier_ids"]:
                bootstrap_supplier_values[metric.key][supplier].append(
                    supplier_values[supplier][metric.key]
                )
                for failure_mode in sorted(CONFIRMED_FAILURE_MODES):
                    bootstrap_family_supplier_values[failure_mode][metric.key][
                        supplier
                    ].append(
                        sampled_family_values[failure_mode][supplier][metric.key]
                    )

    metric_audits: list[dict[str, Any]] = []
    ranking_output: list[dict[str, Any]] = []
    descriptive_sets: list[set[str]] = []
    metric_display_sets: list[set[str]] = []
    for metric in METRICS:
        order = metric_orders[metric.key]
        presence = presence_by_metric[metric.key]
        metric_audit = _metric_boundary_payload(
            metric=metric,
            order=order,
            supplier_values=aggregate_supplier_values,
            bootstrap_values=bootstrap_supplier_values[metric.key],
            presence=presence,
            release_inputs_pass=scientific_inputs_pass,
        )
        metric_audit["aggregation_scope"] = SUPPLIER_ENVELOPE_SCOPE
        metric_audit["causal_fusion_claimed"] = False
        top3 = tuple(order[:3])
        metric_display_allowed = bool(
            metric_audit["scoped_descriptive_set_display_allowed"]
        )
        descriptive_sets.append(set(top3))
        if metric_display_allowed:
            metric_display_sets.append(set(top3))
        metric_audits.append(metric_audit)
        for rank, supplier in enumerate(order, 1):
            driver_scenario_id = _supplier_metric_driver_scenario(
                supplier=supplier,
                metric=metric,
                scenario_means=aggregate_scenario_means,
                supplier_scenarios=supplier_scenarios,
            )
            supplier_chain_ids = {
                scenario_meta[scenario_id].chain_id
                for scenario_id in supplier_scenarios[supplier]
            }
            ranking_output.append(
                {
                    "aggregation_scope": SUPPLIER_ENVELOPE_SCOPE,
                    "failure_mode": "",
                    "hypothesis_family": (
                        "worst_single_lane_scenario_across_date_shift_and_"
                        "usable_quantity_loss"
                    ),
                    "metric_key": metric.key,
                    "metric_label": metric.label,
                    "metric_unit": metric.unit,
                    "direction": metric.direction,
                    "descriptive_metric_rank": rank,
                    "supplier_id": supplier,
                    "supplier_lane_count": len(supplier_chain_ids),
                    "tested_scenario_count": len(supplier_scenarios[supplier]),
                    "driver_scenario_id": driver_scenario_id,
                    "driver_chain_id": scenario_meta[driver_scenario_id].chain_id,
                    "driver_failure_mode": scenario_meta[
                        driver_scenario_id
                    ].failure_mode,
                    "metric_value": aggregate_supplier_values[supplier][metric.key],
                    "top3_presence_seed_count": presence[supplier],
                    "paired_seed_count": len(seeds),
                    "scoped_descriptive_set_display_allowed": (
                        metric_display_allowed
                    ),
                    "metric_priority_set_release_pass": False,
                    "confirmatory_priority_set_release_allowed": False,
                    "rank_is_descriptive_identifier_tie_break_not_evidence": True,
                    "driver_lane_uniqueness_claimed": False,
                    "driver_selection_rule": (
                        "worst_mean_metric_scenario_then_identifier_tie_break"
                    ),
                    "universal_supplier_criticality_claimed": False,
                    "evidence_class": "conditional_simulation_hypothesis",
                    "historical_occurrence_probability": "not_estimated",
                    "ranking_meaning": (
                        "conditional_model_sensitivity_priority_not_observed_criticality"
                    ),
                }
            )

    family_metric_audits: dict[str, list[dict[str, Any]]] = {}
    family_descriptive_sets: dict[str, list[set[str]]] = {}
    family_metric_display_sets: dict[str, list[set[str]]] = {}
    for failure_mode in sorted(CONFIRMED_FAILURE_MODES):
        hypothesis_family = HYPOTHESIS_FAMILY_BY_FAILURE_MODE[failure_mode]
        family_metric_audits[failure_mode] = []
        family_descriptive_sets[failure_mode] = []
        family_metric_display_sets[failure_mode] = []
        for metric in METRICS:
            order = family_metric_orders[failure_mode][metric.key]
            presence = family_presence_by_metric[failure_mode][metric.key]
            metric_audit = _metric_boundary_payload(
                metric=metric,
                order=order,
                supplier_values=family_supplier_values[failure_mode],
                bootstrap_values=bootstrap_family_supplier_values[failure_mode][
                    metric.key
                ],
                presence=presence,
                release_inputs_pass=scientific_inputs_pass,
            )
            metric_audit["failure_mode"] = failure_mode
            metric_audit["hypothesis_family"] = hypothesis_family
            family_metric_audits[failure_mode].append(metric_audit)
            top3 = set(order[:3])
            family_descriptive_sets[failure_mode].append(top3)
            if metric_audit["scoped_descriptive_set_display_allowed"]:
                family_metric_display_sets[failure_mode].append(top3)
            for rank, supplier in enumerate(order, 1):
                driver_scenario_id = _supplier_metric_driver_scenario(
                    supplier=supplier,
                    metric=metric,
                    scenario_means=aggregate_scenario_means,
                    supplier_scenarios=family_supplier_scenarios[failure_mode],
                )
                supplier_chain_ids = {
                    scenario_meta[scenario_id].chain_id
                    for scenario_id in family_supplier_scenarios[failure_mode][
                        supplier
                    ]
                }
                ranking_output.append(
                    {
                        "aggregation_scope": "failure_mode_specific",
                        "failure_mode": failure_mode,
                        "hypothesis_family": hypothesis_family,
                        "metric_key": metric.key,
                        "metric_label": metric.label,
                        "metric_unit": metric.unit,
                        "direction": metric.direction,
                        "descriptive_metric_rank": rank,
                        "supplier_id": supplier,
                        "supplier_lane_count": len(supplier_chain_ids),
                        "tested_scenario_count": len(
                            family_supplier_scenarios[failure_mode][supplier]
                        ),
                        "driver_scenario_id": driver_scenario_id,
                        "driver_chain_id": scenario_meta[
                            driver_scenario_id
                        ].chain_id,
                        "driver_failure_mode": failure_mode,
                        "metric_value": family_supplier_values[failure_mode][
                            supplier
                        ][metric.key],
                        "top3_presence_seed_count": presence[supplier],
                        "paired_seed_count": len(seeds),
                        "scoped_descriptive_set_display_allowed": metric_audit[
                            "scoped_descriptive_set_display_allowed"
                        ],
                        "metric_priority_set_release_pass": False,
                        "confirmatory_priority_set_release_allowed": False,
                        "rank_is_descriptive_identifier_tie_break_not_evidence": True,
                        "driver_lane_uniqueness_claimed": False,
                        "driver_selection_rule": (
                            "worst_mean_metric_scenario_then_identifier_tie_break"
                        ),
                        "universal_supplier_criticality_claimed": False,
                        "evidence_class": "conditional_simulation_hypothesis",
                        "historical_occurrence_probability": "not_estimated",
                        "ranking_meaning": (
                            "conditional_model_sensitivity_priority_not_observed_criticality"
                        ),
                    }
                )

    metric_audit_by_key = {
        str(row["metric_key"]): row for row in metric_audits
    }
    service_audit = metric_audit_by_key["horizon_on_due_service_delta"]
    cross_metric_same_set = len({frozenset(group) for group in descriptive_sets}) == 1
    all_metric_sets_display_allowed = len(metric_display_sets) == len(METRICS)
    envelope_all_metric_descriptive_display_allowed = bool(
        cross_metric_same_set and all_metric_sets_display_allowed
    )
    family_service_sets = {
        failure_mode: frozenset(
            family_metric_orders[failure_mode][
                "horizon_on_due_service_delta"
            ][:3]
        )
        for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
    }
    family_service_top3_sets_identical = (
        len(set(family_service_sets.values())) == 1
    )
    envelope_and_family_service_top3_sets_identical = (
        len(
            {
                frozenset(metric_orders["horizon_on_due_service_delta"][:3]),
                *family_service_sets.values(),
            }
        )
        == 1
    )
    all_family_service_sets_display_allowed = all(
        next(
            row
            for row in family_metric_audits[failure_mode]
            if row["metric_key"] == "horizon_on_due_service_delta"
        )["scoped_descriptive_set_display_allowed"]
        for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
    )
    all_scope_descriptive_sets = list(descriptive_sets)
    all_scope_display_sets = list(metric_display_sets)
    for failure_mode in sorted(CONFIRMED_FAILURE_MODES):
        all_scope_descriptive_sets.extend(family_descriptive_sets[failure_mode])
        all_scope_display_sets.extend(family_metric_display_sets[failure_mode])
    all_family_metric_sets_display_allowed = all(
        len(family_metric_display_sets[failure_mode]) == len(METRICS)
        for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
    )
    all_scope_top3_sets_identical = (
        len({frozenset(group) for group in all_scope_descriptive_sets}) == 1
    )
    all_scope_descriptive_convergence = bool(
        envelope_all_metric_descriptive_display_allowed
        and all_family_metric_sets_display_allowed
        and all_scope_top3_sets_identical
    )
    consensus = (
        sorted(set.intersection(*all_scope_display_sets))
        if all_scope_display_sets
        else []
    )

    boundary_group: set[str] = set()
    for metric_audit in metric_audits:
        boundary_group.update(metric_audit["nonseparation_group_supplier_ids"])
    for failure_mode in sorted(CONFIRMED_FAILURE_MODES):
        for metric_audit in family_metric_audits[failure_mode]:
            boundary_group.update(
                metric_audit["nonseparation_group_supplier_ids"]
            )

    service_display_allowed = bool(
        service_audit["scoped_descriptive_set_display_allowed"]
    )
    cause_independent_service_descriptive_display_allowed = bool(
        service_display_allowed
        and all_family_service_sets_display_allowed
        and envelope_and_family_service_top3_sets_identical
    )
    service_display_ids = tuple(
        service_audit["displayed_scoped_priority_supplier_ids"]
    )
    service_metric = METRIC_BY_KEY["horizon_on_due_service_delta"]
    service_driver_mappings: list[dict[str, Any]] = []
    for supplier in sorted(matrix["supplier_ids"]):
        driver_scenario_id = _supplier_metric_driver_scenario(
            supplier=supplier,
            metric=service_metric,
            scenario_means=aggregate_scenario_means,
            supplier_scenarios=supplier_scenarios,
        )
        service_driver_mappings.append(
            {
                "supplier_id": supplier,
                "selection_slot": (
                    service_display_ids.index(supplier) + 1
                    if supplier in service_display_ids
                    else None
                ),
                "driver_scenario_id": driver_scenario_id,
                "driver_chain_id": scenario_meta[driver_scenario_id].chain_id,
                "driver_failure_mode": scenario_meta[
                    driver_scenario_id
                ].failure_mode,
                "driver_lane_uniqueness_claimed": False,
                "driver_selection_rule": (
                    "worst_mean_service_scenario_then_identifier_tie_break"
                ),
                "selection_slot_order_has_scientific_meaning": False,
            }
        )
    effect_rows = _conditional_effect_rows(
        rows_by_key=matrix["by_key"],
        metric_values_by_case=matrix["metric_values_by_case"],
        seeds=seeds,
        selected_scenarios=selected,
        scenario_meta=scenario_meta,
    )
    supplier_lane_count_by_id = {
        supplier: len(
            {
                scenario_meta[scenario_id].chain_id
                for scenario_id in supplier_scenarios[supplier]
            }
        )
        for supplier in matrix["supplier_ids"]
    }
    supplier_lane_exposure_balanced = (
        len(set(supplier_lane_count_by_id.values())) == 1
    )
    audit = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "integrity_digest_not_authenticated_signature": True,
        "cryptographic_authentication_present": False,
        "internal_consistency_recomputed_from_source": True,
        "consumer_must_reconstruct_from_pinned_source_before_use": True,
        "evidence_class": "conditional_simulation_hypothesis",
        "historical_occurrence_probability": "not_estimated",
        "industrial_supplier_criticality_claimed": False,
        "ranking_scope": (
            "two_predeclared_severe_mathematical_families_on_all_active_lanes; "
            "one_lane_incident_at_a_time"
        ),
        "supplier_envelope_semantics": (
            "enveloppe = pire scénario voie-unique parmi les voies couvertes et "
            "les deux hypothèses pré-déclarées; ce n'est pas une fusion causale "
            "ni un classement indépendant de la cause"
        ),
        "supplier_lane_count_by_id": supplier_lane_count_by_id,
        "supplier_lane_exposure_balanced": supplier_lane_exposure_balanced,
        "lane_count_normalization_applied": False,
        "supplier_envelope_cross_supplier_exposure_comparable": (
            supplier_lane_exposure_balanced
        ),
        "supplier_signal_interpretation": (
            "conditional_network_vulnerability_not_intrinsic_supplier_reliability"
        ),
        "selection_and_assessment_seed_blocks_independent": False,
        "post_selection_inference_correction_applied": False,
        "confirmatory_population_priority_inference_claimed": False,
        "scoped_priority_set_is_descriptive_post_selection": True,
        "primary_display_metric_key": "horizon_on_due_service_delta",
        "multiple_comparison_correction_applied": False,
        "simultaneous_or_familywise_interval_coverage_claimed": False,
        "uncertainty_sampling_scope": "model_transport_lead_time_draws_only",
        "broad_supply_uncertainty_monte_carlo_claimed": False,
        "historical_recurrence_evaluable": False,
        "supplier_incident_frequency_evaluable": False,
        "demand_uncertainty_included": False,
        "incident_severity_uncertainty_included": False,
        "baseline_configuration_count": 1,
        "baseline_scope": "single_nominal_healthy_baseline_at_least_95_percent",
        "degraded_baseline_service_levels_tested": [],
        "baseline_80_and_93_percent_configurations_evaluated": False,
        "sensitivity_method": "conditional_one_factor_at_a_time_stress_test",
        "global_variance_based_sensitivity_claimed": False,
        "active_window_selection_scope": (
            "lane_specific_180_day_window_selected_for_strongest_baseline_flow"
        ),
        "active_window_calendar_aligned_across_lanes": False,
        "cross_lane_result_mix_load_calendar_horizon_and_vulnerability": True,
        "causal_fusion_performed_or_claimed": False,
        "confirmed_failure_modes": sorted(CONFIRMED_FAILURE_MODES),
        "supplier_wide_common_cause_included_in_ranking": False,
        "execution_integrity_pass": execution_integrity_pass,
        "interpretation_prerequisites_pass": interpretation_prerequisites_pass,
        "descriptive_priority_display_inputs_pass": scientific_inputs_pass,
        "scientific_priority_release_inputs_pass": False,
        "confirmation_matrix": {
            key: value
            for key, value in matrix.items()
            if key
            in {
                "confirmation_matrix_exact_pass",
                "expected_baseline_row_count",
                "actual_baseline_row_count",
                "expected_stress_scenario_count",
                "expected_stress_row_count",
                "actual_stress_row_count",
                "actual_total_row_count",
                "all_metric_rows_valid_pass",
                "j0_state_hash_pairing_all_rows_pass",
                "input_graph_hash_pairing_all_rows_pass",
                "resolved_common_random_numbers_all_pairs_pass",
                "paired_active_window_baseline_identical_between_failure_modes_pass",
                "paired_target_demand_identical_and_positive_all_rows_pass",
                "paired_metric_arithmetic_recomputed_from_physical_baseline_pass",
                "horizon_J0_J719_all_rows_pass",
                "baseline_both_products_on_due_at_least_95_all_seeds_pass",
                "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass",
            }
        },
        "bootstrap": {
            "method": "nonparametric_percentile_bootstrap",
            "pairing_unit": "complete_seed_block_all_confirmed_scenarios",
            "paired_seed_count": len(seeds),
            "resample_count": resamples,
            "deterministic_seed_formula": (
                "90210 + paired_seed_count * 100003 + resample_count"
            ),
            "identifier_tie_break_used_as_scientific_evidence": False,
            "selection_and_assessment_seed_blocks_independent": False,
            "post_selection_inference_correction_applied": False,
            "confirmatory_population_interval_claimed": False,
            "multiple_comparison_correction_applied": False,
            "simultaneous_or_familywise_interval_coverage_claimed": False,
            "interpretation": (
                "marginal_descriptive_resampling_of_the_same_30_model_"
                "transport_lead_time_draw_blocks"
            ),
        },
        "metric_priority_audits": metric_audits,
        "failure_mode_specific_metric_priority_audits": {
            failure_mode: {
                "hypothesis_family": HYPOTHESIS_FAMILY_BY_FAILURE_MODE[
                    failure_mode
                ],
                "metric_priority_audits": family_metric_audits[failure_mode],
            }
            for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
        },
        "service_priority_scope": SUPPLIER_ENVELOPE_SCOPE,
        "scoped_descriptive_priority_set_display_allowed": (
            service_display_allowed
        ),
        "displayed_scoped_priority_supplier_ids": list(service_display_ids),
        "displayed_scoped_priority_supplier_count": len(service_display_ids),
        "envelope_service_nonseparation_group_supplier_ids": service_audit[
            "nonseparation_group_supplier_ids"
        ],
        "envelope_service_driver_mappings": service_driver_mappings,
        "displayed_scoped_priority_driver_mappings": [
            row
            for row in service_driver_mappings
            if row["supplier_id"] in service_display_ids
        ],
        "driver_lane_uniqueness_claimed": False,
        "extension_selection_meaning": (
            "deterministic_post_selection_follow_up_not_unique_worst_lane"
        ),
        "slot_order_has_scientific_meaning": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "legacy_priority_release_aliases_neutralized": True,
        "envelope_service_priority_set_release_pass": False,
        "service_priority_set_release_pass": False,
        "envelope_service_priority_supplier_ids": [],
        "service_priority_supplier_ids": [],
        "separate_metric_top3_sets_identical": cross_metric_same_set,
        "all_four_metric_scoped_descriptive_sets_display_allowed": (
            all_metric_sets_display_allowed
        ),
        "envelope_all_four_metric_descriptive_convergence": (
            envelope_all_metric_descriptive_display_allowed
        ),
        "all_four_metric_boundaries_released": False,
        "envelope_all_four_metric_top3_release_pass": False,
        "family_service_descriptive_first_three_supplier_ids": {
            failure_mode: list(
                family_metric_orders[failure_mode][
                    "horizon_on_due_service_delta"
                ][:3]
            )
            for failure_mode in sorted(CONFIRMED_FAILURE_MODES)
        },
        "family_service_top3_sets_identical": (
            family_service_top3_sets_identical
        ),
        "envelope_and_family_service_top3_sets_identical": (
            envelope_and_family_service_top3_sets_identical
        ),
        "all_failure_mode_specific_service_sets_display_allowed": (
            all_family_service_sets_display_allowed
        ),
        "family_service_divergence_blocks_cause_independent_wording": (
            not envelope_and_family_service_top3_sets_identical
        ),
        "family_service_nonseparation_blocks_cause_independent_wording": (
            not all_family_service_sets_display_allowed
        ),
        "cause_independent_service_descriptive_display_allowed": (
            cause_independent_service_descriptive_display_allowed
        ),
        "cause_independent_service_descriptive_supplier_ids": (
            list(service_display_ids)
            if cause_independent_service_descriptive_display_allowed
            else []
        ),
        "cause_independent_service_priority_release_pass": False,
        "cause_independent_service_priority_supplier_ids": [],
        "all_failure_mode_specific_metric_sets_display_allowed": (
            all_family_metric_sets_display_allowed
        ),
        "all_failure_mode_specific_metric_boundaries_released": False,
        "all_envelope_and_family_metric_top3_sets_identical": (
            all_scope_top3_sets_identical
        ),
        "all_scope_descriptive_set_convergence": (
            all_scope_descriptive_convergence
        ),
        "universal_supplier_top3_release_pass": False,
        "universal_supplier_top3_ids": [],
        "descriptive_envelope_and_family_metric_consensus_supplier_ids": (
            consensus
        ),
        "released_envelope_and_family_metric_consensus_supplier_ids": [],
        "priority_group_supplier_ids_if_no_universal_top3": sorted(
            boundary_group
        ),
        "cross_metric_reading": (
            "descriptive_same_three_under_all_tested_readings_not_universal"
            if all_scope_descriptive_convergence
            else (
                "envelope_signal_may_be_displayed_only_under_its_explicit_scope; "
                "metric_or_hypothesis_family_dependent_result_requires_group_reading"
            )
        ),
        "raw_network_recovery_metric": {
            "status": "excluded_invalid_common_J45_J224_for_lane_specific_windows",
            "used_in_any_ranking_or_gate": False,
            "reason": (
                "target_recovery_day_after_incident is computed against the common "
                "window rather than each lane-specific stress end day"
            ),
        },
        "conditional_effect_count_semantics": (
            "display-threshold exceedance counts among the 30 paired conditional "
            "model transport-lead-time draws; not probability, historical frequency "
            "or supplier forecast"
        ),
        "display_effect_thresholds": {
            "horizon_service_loss_ratio": DISPLAY_CLIENT_SERVICE_LOSS_RATIO,
            "backlog_days_per_requested_unit": (
                DISPLAY_CLIENT_BACKLOG_DAYS_PER_REQUESTED_UNIT
            ),
            "released_production_shortfall_ratio": (
                DISPLAY_PRODUCTION_SHORTFALL_RATIO
            ),
            "business_materiality_threshold_validated": False,
            "thresholds_are_model_reporting_conventions": True,
            "client_count_rule": (
                "horizon_service_loss_or_normalized_backlog_threshold_exceeded"
            ),
            "production_count_rule": (
                "released_production_shortfall_threshold_exceeded"
            ),
            "worst_rolling_28d_used_in_client_count": False,
        },
        "individual_customer_or_order_attribution_evaluable": False,
        "revenue_or_penalty_loss_evaluable": False,
        "target_product_count": len(EXPECTED_TARGET_PRODUCTS),
        "supplier_any_effect_seed_count_cross_supplier_comparable": (
            supplier_lane_exposure_balanced
        ),
        "no_opaque_composite_score": True,
    }
    return audit, ranking_output, effect_rows


def _source_inputs(network_dir: Path) -> dict[str, Path]:
    paths = {name: network_dir / name for name in REQUIRED_SOURCE_FILES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Sources réseau absentes: " + ", ".join(missing))
    return paths


def _compute_source_outputs(
    source_root: Path,
    *,
    resamples: int,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    source_paths = _source_inputs(source_root)
    source_hashes_before = {
        name: _sha256(path) for name, path in sorted(source_paths.items())
    }
    campaign_manifest = _read_json(source_paths["campaign_manifest.json"])
    _validate_campaign_signature(campaign_manifest)
    if (
        str(campaign_manifest.get("schema_version") or "")
        != EXPECTED_CAMPAIGN_SCHEMA_VERSION
    ):
        raise ValueError("Version de campagne source inconnue ou incompatible.")
    if str(campaign_manifest.get("status") or "") != "complete":
        raise ValueError("La campagne source doit être close avant l'audit.")
    if str(campaign_manifest.get("mode") or "") != "full":
        raise ValueError("La campagne source doit être en mode full.")
    if _to_int(campaign_manifest.get("days")) != 720:
        raise ValueError("La campagne source doit couvrir exactement J0–J719.")
    if _to_int(campaign_manifest.get("confirmation_seed_count")) != 30:
        raise ValueError("Le manifeste source doit déclarer 30 graines de confirmation.")
    if _to_int(campaign_manifest.get("active_lane_count")) != EXPECTED_ACTIVE_LANE_COUNT:
        raise ValueError("Le manifeste source doit déclarer 18 voies actives.")
    if _to_int(campaign_manifest.get("distinct_supplier_count")) != EXPECTED_SUPPLIER_COUNT:
        raise ValueError("Le manifeste source doit déclarer 16 fournisseurs actifs.")
    expected_families = {
        "date_shift": "transport_delay",
        "usable_quantity_loss": "supply_availability",
    }
    if (
        _to_int(campaign_manifest.get("confirmation_top_lanes"))
        != EXPECTED_ACTIVE_LANE_COUNT
        or campaign_manifest.get("confirmation_scope_requirement")
        != "all_18_active_lanes"
        or campaign_manifest.get("confirmation_mathematical_families")
        != expected_families
    ):
        raise ValueError(
            "La pré-déclaration de la confirmation réseau est incohérente."
        )
    if (
        campaign_manifest.get("reference_open_orders_disabled") is not True
        or campaign_manifest.get("network_lot_trace_opt_in") is not True
    ):
        raise ValueError("Les options scientifiques de la campagne source diffèrent.")
    if (
        _to_int(campaign_manifest.get("lane_specific_stress_duration_days"))
        != EXPECTED_STRESS_WINDOW_DAYS
        or campaign_manifest.get("lane_specific_window_method")
        != (
            "maximum_reference_shipped_quantity_in_180d_tie_nearest_J45_then_earliest"
        )
    ):
        raise ValueError("La règle de fenêtre propre à chaque voie est incohérente.")

    selection = _read_json(source_paths["confirmation_selection.json"])
    selected_ids = tuple(selection.get("selected_scenario_ids") or ())
    if len(selected_ids) != EXPECTED_CONFIRMED_SCENARIO_COUNT:
        raise ValueError("La sélection source doit contenir exactement 36 scénarios.")
    raw_campaign_scenario_ids = campaign_manifest.get("scenario_ids")
    if not isinstance(raw_campaign_scenario_ids, list):
        raise ValueError("La liste des scénarios pré-déclarés est absente.")
    campaign_scenario_ids = [str(value) for value in raw_campaign_scenario_ids]
    if (
        not all(campaign_scenario_ids)
        or len(campaign_scenario_ids) != len(set(campaign_scenario_ids))
        or BASELINE_SCENARIO_ID not in campaign_scenario_ids
        or not set(selected_ids) <= set(campaign_scenario_ids)
    ):
        raise ValueError(
            "Les scénarios confirmés ne sont pas tous pré-déclarés par la campagne."
        )
    scenario_meta = _load_scenario_meta(
        _read_csv(source_paths["scenario_design.csv"]), selected_ids
    )
    selected_chain_ids = {meta.chain_id for meta in scenario_meta.values()}
    raw_manifest_chain_ids = list(campaign_manifest.get("active_chain_ids") or [])
    manifest_chain_ids = {str(value) for value in raw_manifest_chain_ids}
    raw_selection_chain_ids = list(
        selection.get("confirmed_unique_chain_ids") or []
    )
    selection_chain_ids = {str(value) for value in raw_selection_chain_ids}
    if (
        len(raw_manifest_chain_ids) != EXPECTED_ACTIVE_LANE_COUNT
        or len(manifest_chain_ids) != EXPECTED_ACTIVE_LANE_COUNT
        or len(raw_selection_chain_ids) != EXPECTED_ACTIVE_LANE_COUNT
        or len(selection_chain_ids) != EXPECTED_ACTIVE_LANE_COUNT
        or manifest_chain_ids != selected_chain_ids
        or selection_chain_ids != selected_chain_ids
    ):
        raise ValueError(
            "Les voies confirmées ne correspondent pas exactement aux voies actives."
        )
    if selection.get("mathematical_families") != expected_families:
        raise ValueError("Les deux familles pré-déclarées ne sont pas exactes.")
    confirmation_rows, crn_provenance = _augment_resolved_pairing(
        _read_csv(source_paths["confirmation_metrics.csv"])
    )
    observed_confirmation_seeds = {
        _to_int(row.get("seed")) for row in confirmation_rows
    }
    raw_manifest_confirmation_seeds = list(
        campaign_manifest.get("confirmation_seeds") or []
    )
    manifest_confirmation_seeds = {
        _to_int(value) for value in raw_manifest_confirmation_seeds
    }
    if (
        len(observed_confirmation_seeds) != EXPECTED_BASELINE_COUNT
        or len(raw_manifest_confirmation_seeds) != EXPECTED_BASELINE_COUNT
        or len(manifest_confirmation_seeds) != EXPECTED_BASELINE_COUNT
        or manifest_confirmation_seeds != observed_confirmation_seeds
    ):
        raise ValueError(
            "Les graines physiques ne correspondent pas exactement au manifeste."
        )
    audit, metric_rows, effect_rows = analyze_priority_boundary(
        confirmation_rows=confirmation_rows,
        selected_scenario_ids=selected_ids,
        scenario_meta=scenario_meta,
        ranking_rows=_read_csv(
            source_paths["confirmation_supplier_sensitivity_ranking.csv"]
        ),
        resamples=resamples,
        enforce_industrial_scope=True,
    )
    audit["source_campaign_manifest_sha256"] = source_hashes_before[
        "campaign_manifest.json"
    ]
    audit["source_campaign_signature"] = str(
        campaign_manifest["campaign_signature"]
    )
    audit["common_random_numbers_provenance"] = {
        "registry_row_count": len(crn_provenance),
        "embedded_confirmation_metric_row_count": sum(
            row["provenance_source"] == "confirmation_metrics_embedded_field"
            for row in crn_provenance
        ),
        "retained_run_summary_row_count": sum(
            row["provenance_source"] == "retained_run_summary"
            for row in crn_provenance
        ),
        "unique_retained_run_summary_count": len(
            {
                str(row["summary_path"])
                for row in crn_provenance
                if row["provenance_source"] == "retained_run_summary"
            }
        ),
        "registry_is_hashed_package_artifact": True,
    }
    _verify_external_crn_provenance_unchanged(crn_provenance)
    source_hashes_after = {
        name: _sha256(path) for name, path in sorted(source_paths.items())
    }
    if source_hashes_after != source_hashes_before:
        raise RuntimeError("La campagne source a changé pendant l'audit.")
    return (
        audit,
        metric_rows,
        effect_rows,
        crn_provenance,
        source_hashes_before,
    )


def _reconstructed_artifact_hashes(
    *,
    source_root: Path,
    resamples: int,
) -> tuple[dict[str, str], dict[str, str]]:
    audit, metric_rows, effect_rows, provenance, source_hashes = (
        _compute_source_outputs(source_root, resamples=resamples)
    )
    staging = Path(tempfile.mkdtemp(prefix=".boundary-reconstruction-"))
    try:
        _write_json(staging / "scientific_priority_boundary_audit.json", audit)
        _write_csv(staging / "supplier_metric_rankings.csv", metric_rows)
        _write_csv(staging / "conditional_effect_seed_counts.csv", effect_rows)
        _write_csv(staging / "common_random_numbers_provenance.csv", provenance)
        return (
            {name: _sha256(staging / name) for name in OUTPUT_FILES},
            source_hashes,
        )
    finally:
        shutil.rmtree(staging)


def validate_audit_package(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    manifest_path = root / "priority_boundary_audit_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Manifeste d'audit absent.")
    manifest = _read_json(manifest_path)
    if str(manifest.get("schema_version") or "") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Version de paquet d'audit inconnue.")
    if str(manifest.get("status") or "") != "complete":
        raise ValueError("Le paquet d'audit n'est pas complet.")
    expected_inventory = set(OUTPUT_FILES) | {
        "priority_boundary_audit_manifest.json"
    }
    actual_inventory = {path.name for path in root.iterdir()}
    if actual_inventory != expected_inventory or any(
        not path.is_file() or path.is_symlink() for path in root.iterdir()
    ):
        raise ValueError("Inventaire disque du paquet d'audit non exact.")
    signature_payload = _manifest_signature_payload(manifest)
    if str(manifest.get("package_signature") or "") != _canonical_sha256(
        signature_payload
    ):
        raise ValueError("La signature canonique du paquet est invalide.")
    if _to_int(manifest.get("bootstrap_resample_count")) != (
        BOOTSTRAP_RESAMPLE_COUNT
    ):
        raise ValueError("Le paquet n'utilise pas les 10 000 blocs bootstrap requis.")
    if not isinstance(
        manifest.get("scoped_descriptive_priority_set_display_allowed"), bool
    ) or any(
        manifest.get(field) is not False
        for field in (
            "confirmatory_priority_set_release_allowed",
            "global_priority_release_allowed",
            "action_promotion_allowed",
            "service_priority_set_release_pass",
            "universal_supplier_top3_release_pass",
        )
    ):
        raise ValueError("Types ou aliases de promotion invalides dans le manifeste.")
    if str(manifest.get("builder_sha256") or "") != _sha256(
        Path(__file__).resolve()
    ):
        raise ValueError("Le constructeur boundary attendu n'est pas celui du paquet.")
    source_hashes = manifest.get("source_file_sha256") or {}
    if set(source_hashes) != set(REQUIRED_SOURCE_FILES) or any(
        len(str(value)) != 64
        or any(character not in "0123456789abcdef" for character in str(value))
        for value in source_hashes.values()
    ):
        raise ValueError("Inventaire des sources boundary incomplet.")
    hashes = manifest.get("artifact_file_sha256") or {}
    if set(hashes) != set(OUTPUT_FILES):
        raise ValueError("Inventaire des fichiers d'audit incomplet.")
    for name, expected in hashes.items():
        path = root / str(name)
        if not path.is_file() or _sha256(path) != str(expected):
            raise ValueError(f"Empreinte invalide pour {name}")
    audit = _read_json(root / "scientific_priority_boundary_audit.json")
    if str(audit.get("schema_version") or "") != SCHEMA_VERSION:
        raise ValueError("Version de résultat d'audit inconnue.")
    if str(audit.get("status") or "") != "complete":
        raise ValueError("Le résultat scientifique n'est pas complet.")
    if (
        audit.get("source_campaign_manifest_sha256")
        != source_hashes["campaign_manifest.json"]
        or not str(audit.get("source_campaign_signature") or "")
    ):
        raise ValueError("Lignée vers la campagne source absente ou incohérente.")
    if _to_int((audit.get("bootstrap") or {}).get("resample_count")) != (
        BOOTSTRAP_RESAMPLE_COUNT
    ):
        raise ValueError("Le résultat scientifique n'utilise pas 10 000 blocs.")
    provenance_rows = _read_csv(
        root / "common_random_numbers_provenance.csv"
    )
    provenance_keys = {
        (str(row.get("scenario_id") or ""), _to_int(row.get("seed")))
        for row in provenance_rows
    }
    if (
        len(provenance_rows) != EXPECTED_TOTAL_ROW_COUNT
        or len(provenance_keys) != EXPECTED_TOTAL_ROW_COUNT
    ):
        raise ValueError("Le registre de provenance CRN n'est pas exact.")
    for row in provenance_rows:
        source = str(row.get("provenance_source") or "")
        if source not in {
            "confirmation_metrics_embedded_field",
            "retained_run_summary",
        }:
            raise ValueError("Source CRN absente ou non résolue dans le registre.")
        if not _as_bool(row.get("resolved_common_random_numbers")):
            raise ValueError("Une ligne du registre CRN n'est pas résolue.")
        if _to_int(row.get("summary_policy_seed")) != _to_int(row.get("seed")):
            raise ValueError("La graine du registre CRN n'est pas appariée.")
        if source == "retained_run_summary":
            summary_hash = str(row.get("summary_sha256") or "")
            if len(summary_hash) != 64 or any(
                character not in "0123456789abcdefABCDEF"
                for character in summary_hash
            ):
                raise ValueError("Empreinte de résumé CRN invalide.")
    declared_provenance = audit.get("common_random_numbers_provenance") or {}
    if _to_int(declared_provenance.get("registry_row_count")) != len(
        provenance_rows
    ):
        raise ValueError("Le résultat et le registre CRN divergent.")
    for field in (
        "scoped_descriptive_priority_set_display_allowed",
        "confirmatory_priority_set_release_allowed",
        "global_priority_release_allowed",
        "action_promotion_allowed",
        "service_priority_set_release_pass",
        "universal_supplier_top3_release_pass",
    ):
        if _as_bool(manifest.get(field)) != _as_bool(audit.get(field)):
            raise ValueError(f"Le manifeste et le résultat divergent pour {field}.")
    if manifest.get("displayed_scoped_priority_supplier_ids") != audit.get(
        "displayed_scoped_priority_supplier_ids"
    ):
        raise ValueError(
            "Le manifeste et le résultat divergent pour l'ensemble affiché."
        )
    if not isinstance(
        audit.get("scoped_descriptive_priority_set_display_allowed"), bool
    ):
        raise ValueError("Décision d'affichage boundary non booléenne.")
    display_allowed = audit["scoped_descriptive_priority_set_display_allowed"]
    displayed_ids = audit.get("displayed_scoped_priority_supplier_ids") or []
    if (
        not isinstance(displayed_ids, list)
        or len(displayed_ids) != len(set(displayed_ids))
        or displayed_ids != sorted(displayed_ids)
        or (display_allowed and len(displayed_ids) != 3)
        or (not display_allowed and displayed_ids)
        or _to_int(audit.get("displayed_scoped_priority_supplier_count"))
        != len(displayed_ids)
    ):
        raise ValueError("Ensemble descriptif affichable boundary incohérent.")
    metric_audits = audit.get("metric_priority_audits") or []
    service_metric_audits = [
        row
        for row in metric_audits
        if row.get("metric_key") == "horizon_on_due_service_delta"
    ]
    if len(service_metric_audits) != 1:
        raise ValueError("Audit de frontière service absent ou dupliqué.")
    service_metric_audit = service_metric_audits[0]
    if (
        service_metric_audit.get("scoped_descriptive_set_display_allowed")
        != display_allowed
        or service_metric_audit.get("displayed_scoped_priority_supplier_ids")
        != displayed_ids
        or audit.get("envelope_service_nonseparation_group_supplier_ids")
        != service_metric_audit.get("nonseparation_group_supplier_ids")
    ):
        raise ValueError("Le résultat service et son résumé boundary divergent.")
    fixed_service_set = service_metric_audit.get(
        "fixed_selected_set_supplier_ids"
    ) or []
    service_group = service_metric_audit.get(
        "nonseparation_group_supplier_ids"
    ) or []
    if (
        not isinstance(fixed_service_set, list)
        or len(fixed_service_set) != 3
        or fixed_service_set != sorted(set(fixed_service_set))
        or not isinstance(service_group, list)
        or service_group != sorted(set(service_group))
        or not set(fixed_service_set) <= set(service_group)
        or (display_allowed and displayed_ids != fixed_service_set)
        or (display_allowed and service_group != fixed_service_set)
    ):
        raise ValueError("Groupe de non-séparation service incohérent.")
    all_metric_audits = list(metric_audits)
    for family in (
        audit.get("failure_mode_specific_metric_priority_audits") or {}
    ).values():
        all_metric_audits.extend(family.get("metric_priority_audits") or [])
    if len(all_metric_audits) != len(METRICS) * 3 or any(
        row.get("metric_priority_set_release_pass") is not False
        or row.get("confirmatory_priority_set_release_allowed") is not False
        or row.get("global_priority_release_allowed") is not False
        or row.get("action_promotion_allowed") is not False
        or row.get("rank3_rank4_pair_used_as_boundary_gate") is not False
        or row.get("selection_and_assessment_seed_blocks_independent") is not False
        or row.get("resampling_interval_is_confirmatory_population_interval")
        is not False
        for row in all_metric_audits
    ):
        raise ValueError("Un audit métrique contient un alias de promotion actif.")
    false_claim_fields = (
        "confirmatory_priority_set_release_allowed",
        "global_priority_release_allowed",
        "action_promotion_allowed",
        "service_priority_set_release_pass",
        "envelope_service_priority_set_release_pass",
        "universal_supplier_top3_release_pass",
        "confirmatory_population_priority_inference_claimed",
        "broad_supply_uncertainty_monte_carlo_claimed",
        "historical_recurrence_evaluable",
        "supplier_incident_frequency_evaluable",
        "scientific_priority_release_inputs_pass",
        "multiple_comparison_correction_applied",
        "simultaneous_or_familywise_interval_coverage_claimed",
    )
    if any(audit.get(field) is not False for field in false_claim_fields):
        raise ValueError("Un alias de promotion ou d'inférence globale est actif.")
    declared_thresholds = audit.get("display_effect_thresholds") or {}
    if (
        not _same_number(
            _number(
                declared_thresholds.get("horizon_service_loss_ratio"),
                field="horizon_service_loss_ratio",
                context="display_effect_thresholds",
            ),
            DISPLAY_CLIENT_SERVICE_LOSS_RATIO,
        )
        or not _same_number(
            _number(
                declared_thresholds.get("backlog_days_per_requested_unit"),
                field="backlog_days_per_requested_unit",
                context="display_effect_thresholds",
            ),
            DISPLAY_CLIENT_BACKLOG_DAYS_PER_REQUESTED_UNIT,
        )
        or not _same_number(
            _number(
                declared_thresholds.get(
                    "released_production_shortfall_ratio"
                ),
                field="released_production_shortfall_ratio",
                context="display_effect_thresholds",
            ),
            DISPLAY_PRODUCTION_SHORTFALL_RATIO,
        )
        or declared_thresholds.get("business_materiality_threshold_validated")
        is not False
        or declared_thresholds.get("thresholds_are_model_reporting_conventions")
        is not True
    ):
        raise ValueError("Seuils d'affichage boundary incohérents.")
    if (
        manifest.get("integrity_digest_not_authenticated_signature") is not True
        or manifest.get("cryptographic_authentication_present") is not False
        or manifest.get("internal_consistency_recomputed_from_source") is not True
        or manifest.get("package_signature_semantics")
        != "unkeyed_internal_consistency_digest_not_authentication"
        or manifest.get("legacy_priority_release_aliases_neutralized") is not True
        or audit.get("integrity_digest_not_authenticated_signature") is not True
        or audit.get("cryptographic_authentication_present") is not False
        or audit.get("internal_consistency_recomputed_from_source") is not True
        or audit.get("consumer_must_reconstruct_from_pinned_source_before_use")
        is not True
    ):
        raise ValueError("Sémantique de l'empreinte d'intégrité absente.")
    driver_mappings = audit.get("envelope_service_driver_mappings") or []
    if (
        not isinstance(driver_mappings, list)
        or len(driver_mappings) != EXPECTED_SUPPLIER_COUNT
        or len({row.get("supplier_id") for row in driver_mappings})
        != EXPECTED_SUPPLIER_COUNT
        or any(
            row.get("driver_lane_uniqueness_claimed") is not False
            or not row.get("driver_scenario_id")
            or not row.get("driver_chain_id")
            or not row.get("driver_failure_mode")
            for row in driver_mappings
        )
    ):
        raise ValueError("Mapping fournisseur-vers-voie d'approfondissement invalide.")
    displayed_mappings = audit.get(
        "displayed_scoped_priority_driver_mappings"
    ) or []
    if (
        {row.get("supplier_id") for row in displayed_mappings}
        != set(displayed_ids)
        or sorted(row.get("selection_slot") for row in displayed_mappings)
        != list(range(1, len(displayed_ids) + 1))
        or any(
            row.get("driver_lane_uniqueness_claimed") is not False
            or row.get("selection_slot_order_has_scientific_meaning") is not False
            for row in displayed_mappings
        )
    ):
        raise ValueError("Mapping du sous-ensemble affiché incohérent.")
    slot_by_supplier = {
        row.get("supplier_id"): row.get("selection_slot")
        for row in driver_mappings
    }
    if any(
        slot_by_supplier[supplier]
        != (displayed_ids.index(supplier) + 1 if supplier in displayed_ids else None)
        for supplier in slot_by_supplier
    ):
        raise ValueError("Slots d'exécution boundary incohérents.")
    if audit.get("raw_network_recovery_metric", {}).get(
        "used_in_any_ranking_or_gate"
    ) is not False:
        raise ValueError("La mesure de récupération invalide a été réintroduite.")
    for name in (
        "supplier_metric_rankings.csv",
        "conditional_effect_seed_counts.csv",
    ):
        fields = set(_read_csv(root / name)[0])
        if any("recovery" in field.lower() for field in fields):
            raise ValueError(f"Champ de récupération interdit dans {name}")
    ranking_rows = _read_csv(root / "supplier_metric_rankings.csv")
    if len(ranking_rows) != EXPECTED_SUPPLIER_COUNT * len(METRICS) * 3:
        raise ValueError("Classements métriques incomplets.")
    envelope_service_rows = [
        row
        for row in ranking_rows
        if row.get("aggregation_scope") == SUPPLIER_ENVELOPE_SCOPE
        and row.get("metric_key") == "horizon_on_due_service_delta"
    ]
    ranking_driver_by_supplier = {
        row.get("supplier_id"): (
            row.get("driver_scenario_id"),
            row.get("driver_chain_id"),
            row.get("driver_failure_mode"),
        )
        for row in envelope_service_rows
    }
    audit_driver_by_supplier = {
        row.get("supplier_id"): (
            row.get("driver_scenario_id"),
            row.get("driver_chain_id"),
            row.get("driver_failure_mode"),
        )
        for row in driver_mappings
    }
    if (
        len(envelope_service_rows) != EXPECTED_SUPPLIER_COUNT
        or ranking_driver_by_supplier != audit_driver_by_supplier
        or any(
            _as_bool(row.get("metric_priority_set_release_pass"))
            or _as_bool(row.get("confirmatory_priority_set_release_allowed"))
            or _as_bool(row.get("driver_lane_uniqueness_claimed"))
            for row in ranking_rows
        )
    ):
        raise ValueError("Classement et mapping d'approfondissement divergent.")
    effect_rows = _read_csv(root / "conditional_effect_seed_counts.csv")
    required_effect_fields = {
        "display_threshold_exceedance_client_effect_seed_count",
        "display_threshold_exceedance_production_effect_seed_count",
        "any_numerical_propagation_seed_count",
        "business_materiality_threshold_validated",
        "thresholds_are_model_reporting_conventions",
        "supplier_any_effect_seed_count_cross_supplier_comparable",
    }
    if len(effect_rows) != 84 or not required_effect_fields <= set(effect_rows[0]):
        raise ValueError("Comptages d'effets conditionnels incomplets.")
    if any(
        _as_bool(row.get("business_materiality_threshold_validated"))
        or not _as_bool(row.get("thresholds_are_model_reporting_conventions"))
        or not _same_number(
            _number(
                row.get("display_client_service_loss_ratio_threshold"),
                field="display_client_service_loss_ratio_threshold",
                context="conditional_effect_seed_counts.csv",
            ),
            DISPLAY_CLIENT_SERVICE_LOSS_RATIO,
        )
        or not _same_number(
            _number(
                row.get(
                    "display_client_backlog_days_per_requested_unit_threshold"
                ),
                field=(
                    "display_client_backlog_days_per_requested_unit_threshold"
                ),
                context="conditional_effect_seed_counts.csv",
            ),
            DISPLAY_CLIENT_BACKLOG_DAYS_PER_REQUESTED_UNIT,
        )
        or not _same_number(
            _number(
                row.get("display_production_shortfall_ratio_threshold"),
                field="display_production_shortfall_ratio_threshold",
                context="conditional_effect_seed_counts.csv",
            ),
            DISPLAY_PRODUCTION_SHORTFALL_RATIO,
        )
        for row in effect_rows
    ):
        raise ValueError("Sémantique des seuils d'affichage invalide.")
    source_network_dir = str(manifest.get("source_network_dir") or "").strip()
    if not source_network_dir:
        raise ValueError("Chemin de campagne source absent du manifeste boundary.")
    source_root = Path(source_network_dir).resolve()
    live_source_paths = _source_inputs(source_root)
    live_source_hashes = {
        name: _sha256(path) for name, path in sorted(live_source_paths.items())
    }
    if live_source_hashes != source_hashes:
        raise ValueError("Les sources vivantes divergent du manifeste boundary.")
    reconstructed_hashes, reconstruction_source_hashes = (
        _reconstructed_artifact_hashes(
            source_root=source_root,
            resamples=BOOTSTRAP_RESAMPLE_COUNT,
        )
    )
    if reconstruction_source_hashes != source_hashes:
        raise ValueError(
            "Les sources ont changé entre leur contrôle et la reconstruction."
        )
    if reconstructed_hashes != hashes:
        raise ValueError(
            "Les artefacts boundary ne correspondent pas à la reconstruction "
            "déterministe des sources."
        )
    final_live_source_hashes = {
        name: _sha256(path) for name, path in sorted(live_source_paths.items())
    }
    if final_live_source_hashes != source_hashes:
        raise ValueError("Les sources ont changé pendant la validation boundary.")
    final_artifact_hashes = {
        name: _sha256(root / name) for name in OUTPUT_FILES
    }
    if final_artifact_hashes != hashes:
        raise ValueError("Les artefacts ont changé pendant la validation boundary.")
    return {
        "valid": True,
        "status": "complete",
        "package_signature": str(manifest.get("package_signature") or ""),
        "scoped_descriptive_priority_set_display_allowed": _as_bool(
            audit.get("scoped_descriptive_priority_set_display_allowed")
        ),
        "displayed_scoped_priority_supplier_ids": displayed_ids,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "service_priority_set_release_pass": False,
        "envelope_service_priority_set_release_pass": False,
        "universal_supplier_top3_release_pass": False,
    }


def build_audit_package(
    *,
    network_dir: str | Path,
    output_dir: str | Path,
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
) -> Path:
    """Build one non-overwriting, transactionally published compact package."""

    if resamples != BOOTSTRAP_RESAMPLE_COUNT:
        raise ValueError("Le paquet publiable exige exactement 10 000 blocs bootstrap.")
    source_root = Path(network_dir).resolve()
    destination = Path(output_dir).resolve()
    builder_path = Path(__file__).resolve()
    builder_hash_before = _sha256(builder_path)
    if destination.exists():
        raise FileExistsError(f"Le dossier de sortie existe déjà: {destination}")
    try:
        destination.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError("Le paquet additif doit être écrit hors de la campagne source.")
    audit, metric_rows, effect_rows, crn_provenance, source_hashes_before = (
        _compute_source_outputs(source_root, resamples=resamples)
    )
    source_paths = _source_inputs(source_root)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=destination.parent
        )
    )
    try:
        _write_json(staging / "scientific_priority_boundary_audit.json", audit)
        _write_csv(staging / "supplier_metric_rankings.csv", metric_rows)
        _write_csv(staging / "conditional_effect_seed_counts.csv", effect_rows)
        _write_csv(
            staging / "common_random_numbers_provenance.csv", crn_provenance
        )
        artifact_hashes = {
            name: _sha256(staging / name) for name in OUTPUT_FILES
        }
        signature_payload = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "status": "complete",
            "builder_sha256": builder_hash_before,
            "source_file_sha256": source_hashes_before,
            "artifact_file_sha256": artifact_hashes,
            "bootstrap_resample_count": resamples,
            "scoped_descriptive_priority_set_display_allowed": audit[
                "scoped_descriptive_priority_set_display_allowed"
            ],
            "displayed_scoped_priority_supplier_ids": audit[
                "displayed_scoped_priority_supplier_ids"
            ],
            "confirmatory_priority_set_release_allowed": False,
            "global_priority_release_allowed": False,
            "action_promotion_allowed": False,
            "service_priority_set_release_pass": False,
            "universal_supplier_top3_release_pass": False,
            "integrity_digest_not_authenticated_signature": True,
            "cryptographic_authentication_present": False,
            "internal_consistency_recomputed_from_source": True,
            "package_signature_semantics": (
                "unkeyed_internal_consistency_digest_not_authentication"
            ),
            "legacy_priority_release_aliases_neutralized": True,
        }
        if set(signature_payload) != set(MANIFEST_SIGNED_FIELDS):
            raise RuntimeError("Contrat de l'empreinte du manifeste incomplet.")
        manifest = {
            **signature_payload,
            "package_signature": _canonical_sha256(signature_payload),
            "source_network_dir": str(source_root),
            "output_dir": str(destination),
            "previous_artifacts_mutated": False,
            "source_artifacts_mutated": False,
            "large_case_directories_copied": False,
        }
        _write_json(staging / "priority_boundary_audit_manifest.json", manifest)
        source_hashes_after = {
            name: _sha256(path) for name, path in sorted(source_paths.items())
        }
        if source_hashes_after != source_hashes_before:
            raise RuntimeError("La campagne source a changé pendant l'audit.")
        if _sha256(builder_path) != builder_hash_before:
            raise RuntimeError("Le constructeur boundary a changé pendant l'audit.")
        _verify_external_crn_provenance_unchanged(crn_provenance)
        validate_audit_package(staging)
        staging.replace(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    validate_audit_package(destination)
    return destination


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--validate", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate is not None:
        result = validate_audit_package(args.validate)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.network_dir is None or args.output_dir is None:
        raise ValueError("--network-dir et --output-dir sont requis pour construire l'audit.")
    output = build_audit_package(
        network_dir=args.network_dir,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {"status": "complete", "output_dir": str(output)},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
