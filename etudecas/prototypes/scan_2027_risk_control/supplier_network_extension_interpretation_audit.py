#!/usr/bin/env python3
"""Fail-closed interpretation audit for the post-priority extensions.

The extension runner intentionally keeps its results outside the main supplier
ranking.  Its historical ``release_gate_pass`` fields only certify that a full
matrix was produced and that baseline flow was exercised.  They do *not*
establish temporal robustness, robustness to four business causes, or a global
supplier priority.

This additive module reads one closed runner package and its signed plan,
revalidates the physical paired evidence, and produces a compact scientific
interpretation package.  It never edits the runner, the plan, or the main
network campaign.  All effect counts are conditional counts among the 30
paired simulations; they are not incident frequencies or probabilities.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import shutil
import statistics
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_post_priority_extensions as planner,
)


SCHEMA_VERSION = "etudecas.supplier_network_extension_interpretation_audit.v1"
MANIFEST_SCHEMA_VERSION = (
    "etudecas.supplier_network_extension_interpretation_audit_package.v1"
)
OVERLAY_SCHEMA_VERSION = "etudecas.supplier_network_extension_scientific_overlay.v1"
RUNNER_SCHEMA_VERSION = "etudecas.supplier_network_post_priority_extension_runner.v1"
PRELIMINARY_CHECKPOINT_SCHEMA_VERSION = (
    "etudecas.supplier_network_post_priority_extension_runner_checkpoint.v1"
)
PRELIMINARY_CHECKPOINT_FILE = "preliminary_checkpoint_15_manifest.json"
PRELIMINARY_CHECKPOINT_SEED_COUNT = 15
PRELIMINARY_CHECKPOINT_EVIDENCE_COUNT = 634
PRELIMINARY_CHECKPOINT_ENGINE_RUN_COUNT = 510
EXPECTED_PAIRED_SEED_COUNT = 30
EXPECTED_FOLLOW_UP_LANE_COUNT = 4
# Compatibility for consumers that still import the old constant name.  It is
# a cardinality only; neither the slots nor this alias encode a scientific rank.
EXPECTED_PRIORITY_LANE_COUNT = EXPECTED_FOLLOW_UP_LANE_COUNT
EXPECTED_NETWORK_LANE_COUNT = 18
EXPECTED_TEMPORAL_CASE_COUNT = 480
EXPECTED_FOUR_CAUSE_CASE_COUNT = 480
EXPECTED_COMMON_CAUSE_CASE_COUNT = 240
EXPECTED_CAUSAL_CASE_COUNT = 4
EXPECTED_TARGET_PRODUCTS = frozenset({"268091", "268967"})
BOOTSTRAP_RESAMPLE_COUNT = 10_000
BOOTSTRAP_SEED_BASE = 73_190
NUMERICAL_TOLERANCE = 1e-9
MINIMUM_REPORTABLE_RATIO_GAP = 0.001
MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP = 0.1
MINIMUM_ACTIVE_FLOW_SEED_COUNT = 29
EXPECTED_PLANNER_BUILDER_SHA256 = (
    "E22D7B923FE4421AAD590458DC9BC9293B77FF5393BD29258D22F23C5F1344C9".lower()
)
EXPECTED_RUNNER_BUILDER_SHA256 = (
    "3E404A3B92D2A8096A10EC1600110689210B112928C385EA1DB3564618FF9DF5".lower()
)

CALENDAR_WINDOWS = (
    (1, 0, 179),
    (2, 180, 359),
    (3, 360, 539),
    (4, 540, 719),
)
FOUR_CAUSES = (
    "transport_delay",
    "supply_availability",
    "quality_hold",
    "quality_yield",
)
CAUSE_FAMILY = {
    "transport_delay": "date_shift",
    "quality_hold": "date_shift",
    "supply_availability": "usable_quantity_loss",
    "quality_yield": "usable_quantity_loss",
}
RISK_TYPE = {
    "transport_delay": "lead_time_extra_days",
    "supply_availability": "availability",
    "quality_hold": "quality_delay",
    "quality_yield": "quality_yield",
}
SEVERE_CAUSE = {
    "transport_delay": (120.0, "jours_ajoutes"),
    "supply_availability": (0.50, "part_disponible"),
    "quality_hold": (90.0, "jours_ajoutes"),
    "quality_yield": (0.80, "part_utilisable"),
}
EXPECTED_MULTI_LANE_SUPPLIERS = (
    "SDC-VD0519670A",
    "SDC-VD0520132A",
)

PLAN_FILES = (
    "paired_baseline_design.csv",
    "multi_lane_supplier_common_cause_design.csv",
    "temporal_robustness_design.csv",
    "priority_four_business_causes_design.csv",
    "causal_lot_attribution_design.csv",
    "promotion_controls.json",
    "post_priority_extensions_plan_manifest.json",
    "PLAN.md",
)
RUNNER_FILES = (
    "post_priority_extension_runner_manifest.json",
    "execution_ledger.json",
    "execution_case_reference.csv",
    "promotion_controls.json",
    "multi_lane_supplier_common_cause_metrics.csv",
    "multi_lane_supplier_common_cause_flow_metrics.csv",
    "multi_lane_supplier_common_cause_summary.csv",
    "multi_lane_supplier_common_cause_manifest.json",
    "temporal_robustness_metrics.csv",
    "temporal_robustness_flow_metrics.csv",
    "temporal_robustness_summary.csv",
    "temporal_robustness_manifest.json",
    "priority_four_business_causes_metrics.csv",
    "priority_four_business_causes_flow_metrics.csv",
    "priority_four_business_causes_summary.csv",
    "priority_four_business_causes_manifest.json",
    "lot_genealogical_exposure_summary.csv",
    "lot_genealogical_exposure_detail.csv",
    "causal_lot_attribution_summary.csv",
    "causal_lot_attribution_detail.csv",
    "causal_lot_attribution_manifest.json",
)
CONSOLIDATED_SMALL_SOURCE_FILES = (
    "supplier_sensitivity_ranking.csv",
    "failure_mode_sensitivity_summary.csv",
    "confirmed_top3_stability.csv",
    "confirmation_supplier_sensitivity_ranking.csv",
    "confirmation_lane_sensitivity_ranking.csv",
    "lane_sensitivity_ranking.csv",
    "lane_priority_membership_stability.csv",
    "lane_evidence_status.csv",
    "confirmation_mathematical_family_summary.csv",
    "active_window_flow_release_gate_by_lane.csv",
)
REQUIRED_CONSOLIDATED_SOURCE_FILES = frozenset(
    {
        "supplier_sensitivity_ranking.csv",
        "failure_mode_sensitivity_summary.csv",
        "confirmed_top3_stability.csv",
    }
)
CONSOLIDATED_SMALL_EXTENSION_FILES = (
    "multi_lane_supplier_common_cause_summary.csv",
    "multi_lane_supplier_common_cause_manifest.json",
    "temporal_robustness_summary.csv",
    "temporal_robustness_manifest.json",
    "priority_four_business_causes_summary.csv",
    "priority_four_business_causes_manifest.json",
    "lot_genealogical_exposure_summary.csv",
    "lot_genealogical_exposure_detail.csv",
    "causal_lot_attribution_summary.csv",
    "causal_lot_attribution_detail.csv",
    "causal_lot_attribution_manifest.json",
    "post_priority_extension_runner_manifest.json",
)
CONSOLIDATED_EXTENSION_MANIFEST_FILES = {
    "multi_lane_supplier_common_cause": (
        "multi_lane_supplier_common_cause_manifest.json"
    ),
    "temporal_robustness": "temporal_robustness_manifest.json",
    "four_business_cause_confirmation": ("priority_four_business_causes_manifest.json"),
    "causal_lot_attribution": "causal_lot_attribution_manifest.json",
}
NEUTRALIZED_CONSOLIDATED_MANIFEST_FILES = frozenset(
    {
        *CONSOLIDATED_EXTENSION_MANIFEST_FILES.values(),
        "post_priority_extension_runner_manifest.json",
    }
)
LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED = (
    "confirmed_top3_stability.csv",
    "confirmation_lane_sensitivity_ranking.csv",
    "confirmation_mathematical_family_summary.csv",
    "confirmation_supplier_sensitivity_ranking.csv",
    "failure_mode_sensitivity_summary.csv",
    "lane_priority_membership_stability.csv",
    "lane_sensitivity_ranking.csv",
    "supplier_sensitivity_ranking.csv",
)
OUTPUT_FILES = (
    "scientific_extension_interpretation_audit.json",
    "temporal_effect_by_lane_window.csv",
    "temporal_pairwise_difference_audit.csv",
    "four_cause_effect_by_lane_cause.csv",
    "four_cause_pairwise_difference_audit.csv",
    "common_cause_effect_by_supplier_cause.csv",
    "scientific_promotion_controls.json",
)


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
        "Variation du service a la date demandee sur J0-J719",
        "ratio_and_percentage_points",
        "lower_is_worse",
        MINIMUM_REPORTABLE_RATIO_GAP,
    ),
    MetricSpec(
        "incremental_backlog_days_per_requested_unit",
        "Variation du backlog normalisee par la demande",
        "UN_day_per_requested_UN",
        "higher_is_worse",
        MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP,
    ),
    MetricSpec(
        "signed_released_production_loss_ratio",
        "Variation signee de production liberee (positive=manque, negative=surplus)",
        "ratio",
        "higher_is_worse",
        MINIMUM_REPORTABLE_RATIO_GAP,
    ),
)
METRIC_BY_KEY = {metric.key: metric for metric in METRICS}


@dataclass(frozen=True)
class Lane:
    chain_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    edge_id: str
    target_product_id: str

    @property
    def flow_key(self) -> tuple[str, str, str, str]:
        return self.chain_id, self.supplier_id, self.item_id, self.dst_node_id


@dataclass(frozen=True)
class CaseSpec:
    extension: str
    case_id: str
    case_key: str
    seed: int
    pairing_block_id: str
    paired_baseline_case_id: str
    failure_mode: str
    risk_type: str
    mechanism_value: float
    mechanism_unit: str
    start_day: int
    end_day: int
    lot_trace_required: bool
    lanes: tuple[Lane, ...]
    products: tuple[str, ...]
    selection_slot: int
    window_index: int
    mathematical_family: str
    simulation_days: int
    outcome_spec_id: str
    outcome_start_day: int
    outcome_end_day: int
    outcome_day_count: int
    outcome_bundle_sha256: str
    preincident_snapshot_day: int


@dataclass(frozen=True)
class PairedEffect:
    extension: str
    case_id: str
    case_key: str
    chain_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    product_id: str
    selection_slot: int
    window_index: int
    failure_mode: str
    mathematical_family: str
    mechanism_value: float
    mechanism_unit: str
    stress_start_day: int
    stress_end_day: int
    simulation_days: int
    outcome_spec_id: str
    outcome_start_day: int
    outcome_end_day: int
    outcome_day_count: int
    preincident_snapshot_day: int
    seed: int
    demand_qty: float
    baseline_released_qty: float
    service_delta: float
    backlog_delta_per_requested_unit: float
    outcome_end_backlog_delta_per_requested_unit: float
    signed_production_loss_ratio: float
    client_effect: bool
    production_effect: bool


@dataclass
class LoadedRunner:
    runner_dir: Path
    plan_dir: Path
    runner_manifest: dict[str, Any]
    plan_manifest: dict[str, Any]
    seeds: tuple[int, ...]
    designs: dict[str, list[dict[str, str]]]
    cases: dict[str, list[CaseSpec]]
    metrics: dict[str, list[dict[str, str]]]
    flows: dict[str, list[dict[str, str]]]
    summaries: dict[str, list[dict[str, str]]]
    extension_manifests: dict[str, dict[str, Any]]
    evidence: dict[str, dict[str, Any]]
    baseline_owner_by_logical_key: dict[str, str]
    source_file_sha256: dict[str, str]
    ledger_case_registry_sha256: str
    preliminary_checkpoint: dict[str, Any] | None
    causal_lot_material_by_case: dict[str, CausalLotMaterial]


@dataclass(frozen=True)
class CausalLotMaterial:
    """Lot rows used by the runner, independently rebound to their sources."""

    baseline_events: list[dict[str, Any]]
    stress_events: list[dict[str, Any]]
    stress_genealogy: list[dict[str, Any]]
    baseline_evidence_format: str


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


def _same_number(left: float, right: float) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-10,
        abs_tol=NUMERICAL_TOLERANCE,
    )


def _risk_event_tokens(rows: Any, *, context: str) -> set[str]:
    if not isinstance(rows, list):
        raise ValueError(f"Lignes d'application risque invalides: {context}.")
    tokens: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"Ligne d'application risque invalide: {context}.")
        for field in ("event_ids", "risk_event_ids"):
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            values = [value.strip() for value in re.split(r"[|,]", raw)]
            if any(not value for value in values) or len(values) != len(set(values)):
                raise ValueError(
                    f"Identifiant risque vide ou duplique dans {field}: {context}."
                )
            tokens.update(values)
    return tokens


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Le CSV de sortie ne peut pas etre vide: {path.name}")
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


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("Percentile impossible sur une liste vide.")
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


def _bootstrap_mean_ci(
    values: Sequence[float],
    *,
    salt: str,
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
) -> tuple[float, float]:
    if len(values) != EXPECTED_PAIRED_SEED_COUNT:
        raise ValueError("Le bootstrap publiable exige exactement 30 blocs apparies.")
    if resamples != BOOTSTRAP_RESAMPLE_COUNT:
        raise ValueError("Le paquet publiable exige exactement 10 000 bootstrap.")
    if all(_same_number(value, values[0]) for value in values[1:]):
        return float(values[0]), float(values[0])
    salt_seed = int(hashlib.sha256(salt.encode("utf-8")).hexdigest()[:12], 16)
    generator = random.Random(BOOTSTRAP_SEED_BASE + salt_seed)
    size = len(values)
    draws: list[float] = []
    for _ in range(resamples):
        draws.append(
            sum(values[generator.randrange(size)] for _index in range(size)) / size
        )
    return _percentile(draws, 0.025), _percentile(draws, 0.975)


def _metric_value(effect: PairedEffect, metric: MetricSpec) -> float:
    if metric.key == "horizon_on_due_service_delta":
        return effect.service_delta
    if metric.key == "incremental_backlog_days_per_requested_unit":
        return effect.backlog_delta_per_requested_unit
    if metric.key == "signed_released_production_loss_ratio":
        return effect.signed_production_loss_ratio
    raise KeyError(metric.key)


def _adverse_amplitude(value: float, metric: MetricSpec) -> float:
    return -value if metric.direction == "lower_is_worse" else value


def _effect_class(
    *,
    mean_value: float,
    ci_low: float,
    ci_high: float,
    metric: MetricSpec,
) -> str:
    adverse_mean = _adverse_amplitude(mean_value, metric)
    if metric.direction == "lower_is_worse":
        adverse_ci_low, adverse_ci_high = -ci_high, -ci_low
    else:
        adverse_ci_low, adverse_ci_high = ci_low, ci_high
    if adverse_mean >= metric.reportable_gap and adverse_ci_low > 0.0:
        return "adverse"
    if adverse_mean <= -metric.reportable_gap and adverse_ci_high < 0.0:
        return "improvement"
    return "uncertain"


def _context_key(effect: PairedEffect, kind: str) -> tuple[Any, ...]:
    if kind == "temporal":
        return (effect.window_index,)
    if kind == "four_cause":
        return (effect.failure_mode, effect.mathematical_family)
    raise KeyError(kind)


def analyze_selected_lane_effects(
    effects: Sequence[PairedEffect],
    *,
    kind: str,
    expected_seeds: Sequence[int],
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Characterize the complete, non-ordered four-lane follow-up group."""

    expected_seed_set = set(expected_seeds)
    if len(expected_seed_set) != EXPECTED_PAIRED_SEED_COUNT:
        raise ValueError(
            "La liste de graines doit contenir exactement 30 valeurs uniques."
        )
    if kind not in {"temporal", "four_cause"}:
        raise ValueError(f"Type d'interpretation inconnu: {kind}")
    contexts = sorted({_context_key(effect, kind) for effect in effects})
    expected_contexts: set[tuple[Any, ...]]
    if kind == "temporal":
        expected_contexts = {(index,) for index, _start, _end in CALENDAR_WINDOWS}
    else:
        expected_contexts = {(cause, CAUSE_FAMILY[cause]) for cause in FOUR_CAUSES}
    if set(contexts) != expected_contexts:
        raise ValueError(
            f"Contextes {kind} incomplets: attendu={sorted(expected_contexts)}, "
            f"obtenu={contexts}"
        )

    by_context_lane: dict[tuple[tuple[Any, ...], int], list[PairedEffect]] = (
        defaultdict(list)
    )
    for effect in effects:
        by_context_lane[(_context_key(effect, kind), effect.selection_slot)].append(
            effect
        )
    expected_groups = {
        (context, slot)
        for context in expected_contexts
        for slot in range(1, EXPECTED_FOLLOW_UP_LANE_COUNT + 1)
    }
    if set(by_context_lane) != expected_groups:
        raise ValueError(f"Matrice {kind} voie/contexte incomplete.")

    effect_rows: list[dict[str, Any]] = []
    indexed: dict[tuple[tuple[Any, ...], int], dict[int, PairedEffect]] = {}
    for group_key, group in sorted(by_context_lane.items()):
        seed_index = {effect.seed: effect for effect in group}
        if len(seed_index) != len(group) or set(seed_index) != expected_seed_set:
            raise ValueError(
                f"Blocs de graines incomplets ou dupliques pour {kind}/{group_key}."
            )
        indexed[group_key] = seed_index
        exemplar = group[0]
        identity = {
            (
                effect.chain_id,
                effect.supplier_id,
                effect.item_id,
                effect.dst_node_id,
                effect.product_id,
                effect.failure_mode,
                effect.mathematical_family,
                effect.mechanism_value,
                effect.mechanism_unit,
                effect.stress_start_day,
                effect.stress_end_day,
                effect.simulation_days,
                effect.outcome_spec_id,
                effect.outcome_start_day,
                effect.outcome_end_day,
                effect.outcome_day_count,
                effect.preincident_snapshot_day,
            )
            for effect in group
        }
        if len(identity) != 1:
            raise ValueError(f"L'identite change dans un bloc {kind}/{group_key}.")
        context, slot = group_key
        residual_values = [
            seed_index[seed].outcome_end_backlog_delta_per_requested_unit
            for seed in expected_seeds
        ]
        residual_mean = sum(residual_values) / len(residual_values)
        residual_ci_low, residual_ci_high = _bootstrap_mean_ci(
            residual_values,
            salt=f"{kind}|{context}|{exemplar.chain_id}|outcome_end_residual",
            resamples=resamples,
        )
        for metric in METRICS:
            values = [
                _metric_value(seed_index[seed], metric) for seed in expected_seeds
            ]
            mean_value = sum(values) / len(values)
            ci_low, ci_high = _bootstrap_mean_ci(
                values,
                salt=f"{kind}|{context}|{exemplar.chain_id}|{metric.key}",
                resamples=resamples,
            )
            effect_rows.append(
                {
                    "extension": exemplar.extension,
                    "case_id": exemplar.case_id,
                    "context_kind": kind,
                    "window_index": exemplar.window_index if kind == "temporal" else "",
                    "stress_start_day": exemplar.stress_start_day,
                    "stress_end_day": exemplar.stress_end_day,
                    "simulation_days": exemplar.simulation_days,
                    "outcome_spec_id": exemplar.outcome_spec_id,
                    "outcome_start_day": exemplar.outcome_start_day,
                    "outcome_end_day": exemplar.outcome_end_day,
                    "outcome_day_count": exemplar.outcome_day_count,
                    "preincident_snapshot_day": exemplar.preincident_snapshot_day,
                    "failure_mode": exemplar.failure_mode,
                    "mathematical_family": exemplar.mathematical_family,
                    "mechanism_value": exemplar.mechanism_value,
                    "mechanism_unit": exemplar.mechanism_unit,
                    "selection_slot": slot,
                    "chain_id": exemplar.chain_id,
                    "supplier_id": exemplar.supplier_id,
                    "item_id": exemplar.item_id,
                    "dst_node_id": exemplar.dst_node_id,
                    "product_id": exemplar.product_id,
                    "metric": metric.key,
                    "metric_label": (
                        metric.label.replace(
                            "sur J0-J719", "sur la fenetre outcome locale"
                        )
                        if kind == "temporal"
                        else metric.label
                    ),
                    "metric_unit": metric.unit,
                    "paired_seed_count": len(values),
                    "effect_mean": mean_value,
                    "effect_ci95_low": ci_low,
                    "effect_ci95_high": ci_high,
                    "adverse_amplitude_mean": _adverse_amplitude(mean_value, metric),
                    "effect_class": _effect_class(
                        mean_value=mean_value,
                        ci_low=ci_low,
                        ci_high=ci_high,
                        metric=metric,
                    ),
                    "conditional_client_effect_seed_count": sum(
                        effect.client_effect for effect in group
                    ),
                    "conditional_production_effect_seed_count": sum(
                        effect.production_effect for effect in group
                    ),
                    "client_service_display_threshold_ratio": (
                        MINIMUM_REPORTABLE_RATIO_GAP
                    ),
                    "client_backlog_display_threshold_days_per_requested_unit": (
                        MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP
                    ),
                    "production_display_threshold_ratio": (
                        MINIMUM_REPORTABLE_RATIO_GAP
                    ),
                    "business_materiality_threshold_validated": False,
                    "thresholds_are_model_reporting_conventions": True,
                    "count_denominator": EXPECTED_PAIRED_SEED_COUNT,
                    "count_is_probability_or_frequency": False,
                    "historical_occurrence_probability_estimated": False,
                    "marginal_interval_only": True,
                    "multiple_comparison_correction_applied": False,
                    "outcome_end_residual_backlog_delta_per_requested_unit_mean": (
                        residual_mean if kind == "temporal" else ""
                    ),
                    "outcome_end_residual_backlog_delta_per_requested_unit_ci95_low": (
                        residual_ci_low if kind == "temporal" else ""
                    ),
                    "outcome_end_residual_backlog_delta_per_requested_unit_ci95_high": (
                        residual_ci_high if kind == "temporal" else ""
                    ),
                    "outcome_end_residual_is_loss_claimed": False,
                    "right_censoring_possible": kind == "temporal",
                }
            )

    difference_rows: list[dict[str, Any]] = []
    ordered_contexts = sorted(expected_contexts)
    for slot in range(1, EXPECTED_FOLLOW_UP_LANE_COUNT + 1):
        for metric in METRICS:
            for left_index, context_a in enumerate(ordered_contexts[:-1]):
                for context_b in ordered_contexts[left_index + 1 :]:
                    context_a_seed = indexed[(context_a, slot)]
                    context_b_seed = indexed[(context_b, slot)]
                    gaps = [
                        _adverse_amplitude(
                            _metric_value(context_a_seed[seed], metric), metric
                        )
                        - _adverse_amplitude(
                            _metric_value(context_b_seed[seed], metric), metric
                        )
                        for seed in expected_seeds
                    ]
                    mean_gap = sum(gaps) / len(gaps)
                    exemplar_a = next(iter(context_a_seed.values()))
                    exemplar_b = next(iter(context_b_seed.values()))
                    ci_low, ci_high = _bootstrap_mean_ci(
                        gaps,
                        salt=(
                            f"{kind}|{exemplar_a.chain_id}|{metric.key}|"
                            f"{context_a}|{context_b}"
                        ),
                        resamples=resamples,
                    )
                    same_lane = bool(
                        exemplar_a.chain_id == exemplar_b.chain_id
                        and exemplar_a.supplier_id == exemplar_b.supplier_id
                        and exemplar_a.item_id == exemplar_b.item_id
                        and exemplar_a.dst_node_id == exemplar_b.dst_node_id
                        and exemplar_a.product_id == exemplar_b.product_id
                    )
                    if not same_lane:
                        raise ValueError(
                            f"La voie change entre deux contextes {kind}/slot{slot}."
                        )
                    if exemplar_a.outcome_day_count != exemplar_b.outcome_day_count:
                        raise ValueError(
                            f"Les outcomes compares n'ont pas la meme duree {kind}/slot{slot}."
                        )
                    difference_detected = bool(
                        abs(mean_gap) >= metric.reportable_gap
                        and (ci_low > 0.0 or ci_high < 0.0)
                    )
                    difference_rows.append(
                        {
                            "context_kind": kind,
                            "context_a_case_id": exemplar_a.case_id,
                            "context_b_case_id": exemplar_b.case_id,
                            "comparison_scope": (
                                "within_lane_between_predeclared_windows"
                                if kind == "temporal"
                                else "within_lane_between_predeclared_cause_hypotheses"
                            ),
                            "metric": metric.key,
                            "selection_slot": slot,
                            "chain_id": exemplar_a.chain_id,
                            "supplier_id": exemplar_a.supplier_id,
                            "item_id": exemplar_a.item_id,
                            "dst_node_id": exemplar_a.dst_node_id,
                            "product_id": exemplar_a.product_id,
                            "context_a_window_index": (
                                context_a[0] if kind == "temporal" else ""
                            ),
                            "context_b_window_index": (
                                context_b[0] if kind == "temporal" else ""
                            ),
                            "context_a_failure_mode": exemplar_a.failure_mode,
                            "context_b_failure_mode": exemplar_b.failure_mode,
                            "context_a_mathematical_family": (
                                exemplar_a.mathematical_family
                            ),
                            "context_b_mathematical_family": (
                                exemplar_b.mathematical_family
                            ),
                            "context_a_mechanism_value": (exemplar_a.mechanism_value),
                            "context_b_mechanism_value": (exemplar_b.mechanism_value),
                            "context_a_mechanism_unit": exemplar_a.mechanism_unit,
                            "context_b_mechanism_unit": exemplar_b.mechanism_unit,
                            "context_a_stress_start_day": (exemplar_a.stress_start_day),
                            "context_a_stress_end_day": exemplar_a.stress_end_day,
                            "context_b_stress_start_day": (exemplar_b.stress_start_day),
                            "context_b_stress_end_day": exemplar_b.stress_end_day,
                            "context_a_outcome_spec_id": exemplar_a.outcome_spec_id,
                            "context_b_outcome_spec_id": exemplar_b.outcome_spec_id,
                            "context_a_outcome_start_day": exemplar_a.outcome_start_day,
                            "context_a_outcome_end_day": exemplar_a.outcome_end_day,
                            "context_b_outcome_start_day": exemplar_b.outcome_start_day,
                            "context_b_outcome_end_day": exemplar_b.outcome_end_day,
                            "context_a_outcome_day_count": exemplar_a.outcome_day_count,
                            "context_b_outcome_day_count": exemplar_b.outcome_day_count,
                            "equal_fixed_followup_day_count": bool(
                                exemplar_a.outcome_day_count
                                == exemplar_b.outcome_day_count
                            ),
                            "paired_seed_count": EXPECTED_PAIRED_SEED_COUNT,
                            "signed_adverse_amplitude_difference_a_minus_b_mean": (
                                mean_gap
                            ),
                            "difference_ci95_low": ci_low,
                            "difference_ci95_high": ci_high,
                            "display_reporting_threshold": metric.reportable_gap,
                            "difference_exceeds_descriptive_reporting_rule": (
                                difference_detected
                            ),
                            "business_materiality_threshold_validated": False,
                            "thresholds_are_model_reporting_conventions": True,
                            "comparison_orientation": (
                                "canonical_context_identifier_only"
                            ),
                            "comparison_is_descriptive_only": True,
                            "comparison_used_for_selection": False,
                            "cause_importance_comparison_evaluable": False,
                            "marginal_interval_only": True,
                            "multiple_comparison_correction_applied": False,
                            "causal_state_dependence_claimed": False,
                        }
                    )

    effect_classes_by_lane_metric: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in effect_rows:
        effect_classes_by_lane_metric[(str(row["chain_id"]), str(row["metric"]))].add(
            str(row["effect_class"])
        )
    effect_class_variations = [
        {
            "chain_id": chain_id,
            "metric": metric_key,
            "simulated_effect_classes": sorted(classes),
        }
        for (chain_id, metric_key), classes in sorted(
            effect_classes_by_lane_metric.items()
        )
        if len(classes) > 1
    ]
    group_ids = sorted({effect.chain_id for effect in effects})
    supplier_ids = sorted({effect.supplier_id for effect in effects})
    if (
        len(group_ids) != EXPECTED_FOLLOW_UP_LANE_COUNT
        or len(supplier_ids) != EXPECTED_FOLLOW_UP_LANE_COUNT
    ):
        raise ValueError(
            "Le groupe complet de quatre voies/fournisseurs n'est pas exact."
        )
    descriptive_difference_detected = any(
        row["difference_exceeds_descriptive_reporting_rule"] for row in difference_rows
    )
    interpretation = {
        "follow_up_lane_count": len(group_ids),
        "network_lane_count": EXPECTED_NETWORK_LANE_COUNT,
        "follow_up_group_chain_ids": group_ids,
        "follow_up_group_status": "complete_nonseparated_service_group_nonordered",
        "service_nonseparation_group_fully_followed_up": True,
        "follow_up_group_order_evaluable": False,
        "scientific_order_claimed": False,
        "slot_order_has_scientific_meaning": False,
        "within_lane_context_difference_detected": (descriptive_difference_detected),
        "effect_class_variations_by_lane_metric": effect_class_variations,
        "within_lane_pairwise_difference_count": len(difference_rows),
        "pairwise_differences_used_for_ordering": False,
        "pairwise_intervals_are_marginal_descriptive": True,
        "multiple_comparison_correction_applied": False,
        "temporal_state_dependence_causally_identified": False,
        "context_variation_is_not_supplier_priority_evidence": True,
        "follow_up_group_effect_matrix_complete": True,
        "global_network_priority_robustness_evaluable": False,
        "global_reason": (
            "only_4_service_nonseparation_follow_up_lanes_tested_out_of_18_"
            "active_network_lanes_and_universal_nonseparation_group_has_16_suppliers"
        ),
        "no_universal_supplier_or_lane_priority_claimed": True,
    }
    return effect_rows, difference_rows, interpretation


def analyze_common_cause_effects(
    effects: Sequence[PairedEffect],
    *,
    cases: Sequence[CaseSpec],
    expected_seeds: Sequence[int],
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aggregate each simultaneous two-lane case once per supplier/cause/seed."""

    expected_seed_set = set(expected_seeds)
    if len(expected_seed_set) != EXPECTED_PAIRED_SEED_COUNT:
        raise ValueError("La cause commune exige exactement 30 graines uniques.")
    case_by_key = {case.case_key: case for case in cases}
    if len(case_by_key) != len(cases):
        raise ValueError("Cas cause commune dupliques.")
    by_supplier_cause_seed: dict[tuple[str, str, int], list[PairedEffect]] = (
        defaultdict(list)
    )
    case_key_by_group: dict[tuple[str, str, int], str] = {}
    for effect in effects:
        case = case_by_key.get(effect.case_key)
        if case is None or len(case.lanes) != 2:
            raise ValueError("Effet cause commune sans cas multi-voies signe.")
        supplier_ids = {lane.supplier_id for lane in case.lanes}
        if len(supplier_ids) != 1:
            raise ValueError("Un cas cause commune melange des fournisseurs.")
        supplier = next(iter(supplier_ids))
        if (
            effect.seed != case.seed
            or effect.failure_mode != case.failure_mode
            or effect.supplier_id != supplier
            or effect.product_id not in case.products
        ):
            raise ValueError("Identite effet/cas cause commune divergente.")
        key = (supplier, case.failure_mode, case.seed)
        if key in case_key_by_group and case_key_by_group[key] != case.case_key:
            raise ValueError(
                "Plusieurs cas physiques creditent le meme bloc cause commune."
            )
        case_key_by_group[key] = case.case_key
        by_supplier_cause_seed[key].append(effect)

    expected_groups = {
        (supplier, cause, seed)
        for supplier in EXPECTED_MULTI_LANE_SUPPLIERS
        for cause in FOUR_CAUSES
        for seed in expected_seed_set
    }
    if set(by_supplier_cause_seed) != expected_groups:
        raise ValueError("Matrice fournisseur/cause/graine commune incomplete.")

    aggregate_by_supplier_cause: dict[tuple[str, str], dict[int, dict[str, float]]] = (
        defaultdict(dict)
    )
    identity_by_supplier_cause: dict[tuple[str, str], CaseSpec] = {}
    for (supplier, cause, seed), group in sorted(by_supplier_cause_seed.items()):
        products = [effect.product_id for effect in group]
        case = case_by_key[case_key_by_group[(supplier, cause, seed)]]
        if len(products) != len(set(products)) or set(products) != set(case.products):
            raise ValueError(
                "Produits inexacts ou dupliques dans un bloc cause commune."
            )
        demand = sum(effect.demand_qty for effect in group)
        released = sum(effect.baseline_released_qty for effect in group)
        if demand <= 0.0 or released <= 0.0:
            raise ValueError("Denominateur commun non strictement positif.")
        aggregate_by_supplier_cause[(supplier, cause)][seed] = {
            "horizon_on_due_service_delta": sum(
                effect.service_delta * effect.demand_qty for effect in group
            )
            / demand,
            "incremental_backlog_days_per_requested_unit": sum(
                effect.backlog_delta_per_requested_unit * effect.demand_qty
                for effect in group
            )
            / demand,
            "signed_released_production_loss_ratio": sum(
                effect.signed_production_loss_ratio * effect.baseline_released_qty
                for effect in group
            )
            / released,
        }
        identity_by_supplier_cause[(supplier, cause)] = case_by_key[
            case_key_by_group[(supplier, cause, seed)]
        ]

    rows: list[dict[str, Any]] = []
    for supplier_cause in sorted(aggregate_by_supplier_cause):
        supplier, cause = supplier_cause
        seed_index = aggregate_by_supplier_cause[supplier_cause]
        if set(seed_index) != expected_seed_set:
            raise ValueError(f"Graines cause commune incompletes: {supplier}/{cause}.")
        case = identity_by_supplier_cause[supplier_cause]
        affected_chain_ids = sorted(lane.chain_id for lane in case.lanes)
        affected_products = sorted({lane.target_product_id for lane in case.lanes})
        for metric in METRICS:
            values = [seed_index[seed][metric.key] for seed in expected_seeds]
            mean_value = sum(values) / len(values)
            ci_low, ci_high = _bootstrap_mean_ci(
                values,
                salt=f"common_cause|{supplier}|{cause}|{metric.key}",
                resamples=resamples,
            )
            exceedance_count = sum(
                _adverse_amplitude(value, metric) >= metric.reportable_gap
                for value in values
            )
            rows.append(
                {
                    "extension": "multi_lane_supplier_common_cause",
                    "case_id": case.case_id,
                    "supplier_id": supplier,
                    "failure_mode": cause,
                    "mathematical_family": CAUSE_FAMILY[cause],
                    "mechanism_value": case.mechanism_value,
                    "mechanism_unit": case.mechanism_unit,
                    "affected_lane_count": len(affected_chain_ids),
                    "affected_chain_ids": "|".join(affected_chain_ids),
                    "affected_products": "|".join(affected_products),
                    "metric": metric.key,
                    "metric_label": metric.label,
                    "metric_unit": metric.unit,
                    "paired_seed_count": EXPECTED_PAIRED_SEED_COUNT,
                    "effect_mean": mean_value,
                    "effect_ci95_low": ci_low,
                    "effect_ci95_high": ci_high,
                    "adverse_amplitude_mean": _adverse_amplitude(mean_value, metric),
                    "effect_class": _effect_class(
                        mean_value=mean_value,
                        ci_low=ci_low,
                        ci_high=ci_high,
                        metric=metric,
                    ),
                    "display_threshold_exceedance_seed_count": exceedance_count,
                    "count_denominator": EXPECTED_PAIRED_SEED_COUNT,
                    "count_is_probability_or_frequency": False,
                    "supplier_cause_seed_is_single_bootstrap_block": True,
                    "lane_rows_not_treated_as_independent_replicates": True,
                    "joint_multi_lane_conditional_effect_evaluable": True,
                    "multi_lane_interaction_or_synergy_evaluable": False,
                    "cascade_amplification_claimed": False,
                    "raw_cross_uom_aggregation_allowed": False,
                    "marginal_interval_only": True,
                    "multiple_comparison_correction_applied": False,
                    "business_materiality_threshold_validated": False,
                }
            )
    interpretation = {
        "supplier_count": len(EXPECTED_MULTI_LANE_SUPPLIERS),
        "cause_count": len(FOUR_CAUSES),
        "paired_seed_count_per_supplier_cause": EXPECTED_PAIRED_SEED_COUNT,
        "effect_row_count": len(rows),
        "joint_multi_lane_conditional_effect_evaluable": True,
        "multi_lane_interaction_or_synergy_evaluable": False,
        "cascade_amplification_claimed": False,
        "single_lane_counterfactual_components_available": False,
        "merged_with_one_lane_supplier_priority": False,
        "supplier_or_cause_ranking_allowed": False,
        "probability_or_frequency_estimated": False,
        "marginal_intervals_only_without_multiplicity_correction": True,
    }
    return rows, interpretation


def _lane_from_descriptor(value: str) -> Lane:
    parts = tuple(part.strip() for part in str(value).split("|"))
    if len(parts) != 6 or not all(parts):
        raise ValueError(f"Descripteur de voie invalide: {value!r}")
    return Lane(*parts)


def _case_key(extension: str, case_id: str, seed: int) -> str:
    return f"{extension}::{case_id}::seed_{seed}"


def _baseline_case_key(case_id: str, seed: int) -> str:
    return _case_key("baseline", case_id, seed)


def _parse_case(row: Mapping[str, Any], expected_extension: str) -> CaseSpec:
    extension = str(row.get("extension") or "").strip()
    if extension != expected_extension:
        raise ValueError(
            f"Extension inattendue: {extension!r}, attendu {expected_extension!r}."
        )
    case_id = str(row.get("case_id") or "").strip()
    seed = _to_int(row.get("seed"))
    pairing_block_id = str(row.get("pairing_block_id") or "").strip()
    paired_baseline_case_id = str(row.get("paired_baseline_case_id") or "").strip()
    failure_mode = str(row.get("failure_mode") or "").strip()
    risk_type = str(row.get("risk_type") or "").strip()
    mechanism_value = _number(
        row.get("mechanism_value"), field="mechanism_value", context=case_id
    )
    mechanism_unit = str(row.get("mechanism_unit") or "").strip()
    start_day = _to_int(row.get("stress_start_day"))
    end_day = _to_int(row.get("stress_end_day"))
    if (
        not case_id
        or seed < 0
        or not pairing_block_id
        or not paired_baseline_case_id
        or failure_mode not in FOUR_CAUSES
        or risk_type != RISK_TYPE.get(failure_mode)
        or not mechanism_unit
        or start_day < 0
        or end_day < start_day
    ):
        raise ValueError(f"Cas planifie incomplet ou invalide: {case_id!r}.")
    if end_day - start_day + 1 != 180:
        raise ValueError(
            f"La fenetre du cas {case_id} ne couvre pas exactement 180 jours."
        )
    expected_value, expected_unit = SEVERE_CAUSE[failure_mode]
    if (
        not _same_number(mechanism_value, expected_value)
        or mechanism_unit != expected_unit
    ):
        raise ValueError(
            f"Hypothese severe inattendue pour {case_id}: "
            f"{mechanism_value} {mechanism_unit}."
        )
    if str(row.get("tested_level") or "") != "severe":
        raise ValueError(f"Le niveau du cas {case_id} n'est pas severe.")
    if str(row.get("historical_occurrence_probability") or "") != "not_estimated":
        raise ValueError(
            f"Le cas {case_id} revendique une probabilite historique non etablie."
        )
    affected_lanes = str(row.get("affected_lanes") or "").strip()
    if affected_lanes:
        lanes = tuple(
            _lane_from_descriptor(value) for value in affected_lanes.split(";")
        )
        products = tuple(
            sorted(
                product.strip()
                for product in str(row.get("affected_products") or "").split("|")
                if product.strip()
            )
        )
        declared_supplier = str(row.get("supplier_id") or "").strip()
        declared_chains = {
            value.strip()
            for value in str(row.get("affected_chain_ids") or "").split("|")
            if value.strip()
        }
        if (
            _to_int(row.get("affected_lane_count")) != 2
            or {lane.supplier_id for lane in lanes} != {declared_supplier}
            or declared_chains != {lane.chain_id for lane in lanes}
        ):
            raise ValueError(f"Perimetre multi-voies incoherent pour {case_id}.")
    else:
        lane = Lane(
            chain_id=str(row.get("chain_id") or "").strip(),
            supplier_id=str(row.get("supplier_id") or "").strip(),
            item_id=str(row.get("item_id") or "").strip(),
            dst_node_id=str(row.get("dst_node_id") or "").strip(),
            edge_id=str(row.get("edge_id") or "").strip(),
            target_product_id=str(row.get("target_product_id") or "").strip(),
        )
        if not all(
            (
                lane.chain_id,
                lane.supplier_id,
                lane.item_id,
                lane.dst_node_id,
                lane.edge_id,
                lane.target_product_id,
            )
        ):
            raise ValueError(f"Identite de voie incomplete pour {case_id}.")
        lanes = (lane,)
        products = (lane.target_product_id,)
    if len(set(lane.flow_key for lane in lanes)) != len(lanes):
        raise ValueError(f"Voie dupliquee dans {case_id}.")
    if not products or set(products) != {lane.target_product_id for lane in lanes}:
        raise ValueError(f"Produits affectes incoherents pour {case_id}.")
    family = str(row.get("mathematical_family") or CAUSE_FAMILY[failure_mode])
    if family != CAUSE_FAMILY[failure_mode]:
        raise ValueError(f"Famille mathematique incoherente pour {case_id}.")
    selection_slot = _to_int(row.get("selection_slot"))
    priority_selection_slot = _to_int(row.get("priority_selection_slot"))
    if len(lanes) == 1 and (
        selection_slot not in range(1, EXPECTED_FOLLOW_UP_LANE_COUNT + 1)
        or selection_slot != priority_selection_slot
        or _as_bool(row.get("slot_order_has_scientific_meaning"))
    ):
        raise ValueError(f"Alias de slot incoherent pour {case_id}.")
    if len(lanes) > 1 and (selection_slot >= 0 or priority_selection_slot >= 0):
        raise ValueError(f"Un cas multi-voies ne doit pas porter de slot: {case_id}.")
    simulation_days = _to_int(row.get("simulation_days"))
    outcome_spec_id = str(row.get("outcome_spec_id") or "").strip()
    outcome_start_day = _to_int(row.get("outcome_start_day"))
    outcome_end_day = _to_int(row.get("outcome_end_day"))
    outcome_day_count = _to_int(row.get("outcome_day_count"))
    outcome_bundle_sha256 = str(row.get("outcome_bundle_sha256") or "").strip()
    if (
        simulation_days <= 0
        or not outcome_spec_id
        or outcome_start_day < 0
        or outcome_end_day < outcome_start_day
        or outcome_end_day >= simulation_days
        or outcome_day_count != outcome_end_day - outcome_start_day + 1
        or len(outcome_bundle_sha256) != 64
    ):
        raise ValueError(f"Horizon/outcome invalide pour {case_id}.")
    return CaseSpec(
        extension=extension,
        case_id=case_id,
        case_key=_case_key(extension, case_id, seed),
        seed=seed,
        pairing_block_id=pairing_block_id,
        paired_baseline_case_id=paired_baseline_case_id,
        failure_mode=failure_mode,
        risk_type=risk_type,
        mechanism_value=mechanism_value,
        mechanism_unit=mechanism_unit,
        start_day=start_day,
        end_day=end_day,
        lot_trace_required=_as_bool(row.get("lot_trace_required")),
        lanes=lanes,
        products=products,
        selection_slot=selection_slot,
        window_index=_to_int(row.get("window_index")),
        mathematical_family=family,
        simulation_days=simulation_days,
        outcome_spec_id=outcome_spec_id,
        outcome_start_day=outcome_start_day,
        outcome_end_day=outcome_end_day,
        outcome_day_count=outcome_day_count,
        outcome_bundle_sha256=outcome_bundle_sha256,
        preincident_snapshot_day=_to_int(row.get("preincident_snapshot_day")),
    )


_DESIGN_INTEGER_FIELDS = frozenset(
    {
        "seed",
        "new_run_count",
        "affected_lane_count",
        "selection_slot",
        "priority_selection_slot",
        "window_index",
        "stress_start_day",
        "stress_end_day",
        "simulation_days",
        "outcome_start_day",
        "outcome_end_day",
        "outcome_day_count",
        "preincident_snapshot_day",
    }
)
_DESIGN_FLOAT_FIELDS = frozenset({"mechanism_value"})
_DESIGN_BOOLEAN_FIELDS = frozenset(
    {
        "lot_trace_required",
        "baseline_lot_trace_required",
        "slot_order_has_scientific_meaning",
    }
)


def _normalized_signed_design_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        converted: dict[str, Any] = {}
        for field, value in row.items():
            if field in _DESIGN_INTEGER_FIELDS:
                converted[field] = _to_int(value)
            elif field in _DESIGN_FLOAT_FIELDS:
                converted[field] = _number(
                    value, field=field, context="signed_plan_design"
                )
            elif field in _DESIGN_BOOLEAN_FIELDS:
                converted[field] = _as_bool(value)
            else:
                converted[field] = str(value)
        normalized.append(converted)
    return normalized


def _recomputed_plan_design_hashes(plan_dir: Path) -> dict[str, str]:
    design_files = {
        "paired_baseline_design": "paired_baseline_design.csv",
        "multi_lane_common_cause_design": (
            "multi_lane_supplier_common_cause_design.csv"
        ),
        "temporal_robustness_design": "temporal_robustness_design.csv",
        "priority_four_business_causes_design": (
            "priority_four_business_causes_design.csv"
        ),
        "causal_lot_attribution_design": "causal_lot_attribution_design.csv",
    }
    result = {
        key: _sha256(plan_dir / filename) for key, filename in design_files.items()
    }
    result["promotion_controls"] = _sha256(plan_dir / "promotion_controls.json")
    result["plan_readme_sha256"] = _sha256(plan_dir / "PLAN.md")
    return result


def _priority_selection_lineage_digest(lineage: Mapping[str, Any]) -> str:
    return _canonical_sha256(
        {
            key: value
            for key, value in lineage.items()
            if key != "priority_selection_lineage_sha256"
        }
    )


def _strict_sorted_unique_strings(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Liste de lignee absente ou invalide: {field}.")
    strings = [str(item).strip() for item in value]
    if any(not item for item in strings) or strings != sorted(set(strings)):
        raise ValueError(f"Liste de lignee non canonique: {field}.")
    return strings


def _strict_unique_strings(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Liste de lignee absente ou invalide: {field}.")
    strings = [str(item).strip() for item in value]
    if any(not item for item in strings) or len(strings) != len(set(strings)):
        raise ValueError(f"Liste de lignee incomplete ou dupliquee: {field}.")
    return strings


def _validate_priority_selection_lineage(
    lineage: Any,
    *,
    declared_digest: Any,
) -> tuple[tuple[str, ...], dict[str, int]]:
    if not isinstance(lineage, dict):
        raise ValueError("Lignee boundary absente du plan publiable.")
    if str(lineage.get("schema_version") or "") != (
        "etudecas.supplier_network_priority_selection_lineage.v1"
    ):
        raise ValueError("Version de lignee boundary inconnue.")
    if str(lineage.get("contract_revision") or "") != (
        "setwise_descriptive_postselection_lineage_2026_09"
    ):
        raise ValueError("Revision de lignee boundary inconnue.")
    digest = _priority_selection_lineage_digest(lineage)
    if (
        str(lineage.get("priority_selection_lineage_sha256") or "") != digest
        or str(declared_digest or "") != digest
    ):
        raise ValueError("Digest de lignee boundary invalide.")

    status = str(lineage.get("priority_selection_status") or "")
    if status != "complete_service_nonseparation_group_follow_up":
        raise ValueError(
            "L'audit final exige le suivi complet du groupe service non separe."
        )
    if (
        lineage.get("scoped_descriptive_priority_set_display_allowed") is not False
        or lineage.get("confirmatory_priority_set_release_allowed") is not False
        or lineage.get("global_priority_release_allowed") is not False
        or lineage.get("action_promotion_allowed") is not False
        or lineage.get("envelope_service_priority_set_release_pass") is not False
    ):
        raise ValueError("La lignee revendique indument une liberation ou promotion.")

    candidate_ids = _strict_sorted_unique_strings(
        lineage.get("selection_candidate_pool_supplier_ids"),
        field="selection_candidate_pool_supplier_ids",
    )
    service_ids = _strict_sorted_unique_strings(
        lineage.get("service_nonseparation_group_supplier_ids"),
        field="service_nonseparation_group_supplier_ids",
    )
    follow_up_ids = _strict_sorted_unique_strings(
        lineage.get("follow_up_supplier_ids"), field="follow_up_supplier_ids"
    )
    priority_ids = _strict_sorted_unique_strings(
        lineage.get("priority_supplier_ids"), field="priority_supplier_ids"
    )
    universal_ids = _strict_sorted_unique_strings(
        lineage.get("boundary_universal_nonseparation_group_supplier_ids"),
        field="boundary_universal_nonseparation_group_supplier_ids",
    )
    if not (
        candidate_ids == service_ids == follow_up_ids == priority_ids
        and len(follow_up_ids) == EXPECTED_FOLLOW_UP_LANE_COUNT
        and len(universal_ids) == 16
        and set(follow_up_ids) < set(universal_ids)
    ):
        raise ValueError(
            "Le groupe service complet de quatre fournisseurs n'est pas exact."
        )

    follow_up_chains = _strict_unique_strings(
        lineage.get("follow_up_chain_ids"), field="follow_up_chain_ids"
    )
    priority_chains = _strict_unique_strings(
        lineage.get("priority_chain_ids"), field="priority_chain_ids"
    )
    if (
        follow_up_chains != priority_chains
        or len(follow_up_chains) != EXPECTED_FOLLOW_UP_LANE_COUNT
    ):
        raise ValueError("Les quatre voies de suivi boundary ne sont pas exactes.")

    mappings = lineage.get("follow_up_driver_mappings")
    legacy_mappings = lineage.get("priority_driver_mappings")
    if not isinstance(mappings, list) or mappings != legacy_mappings:
        raise ValueError("Mappings de suivi boundary absents ou divergents.")
    expected_slots = set(range(1, EXPECTED_FOLLOW_UP_LANE_COUNT + 1))
    slot_by_chain: dict[str, int] = {}
    mapped_suppliers: list[str] = []
    for raw in mappings:
        if not isinstance(raw, dict):
            raise ValueError("Mapping de suivi boundary invalide.")
        slot = _to_int(raw.get("selection_slot"))
        supplier = str(raw.get("supplier_id") or "").strip()
        chain = str(raw.get("driver_chain_id") or "").strip()
        if (
            slot not in expected_slots
            or not supplier
            or not chain
            or chain in slot_by_chain
            or _as_bool(raw.get("driver_lane_uniqueness_claimed"))
            or str(raw.get("driver_selection_rule") or "")
            != "worst_mean_service_scenario_then_identifier_tie_break"
            or not str(raw.get("driver_scenario_id") or "").strip()
            or str(raw.get("driver_failure_mode") or "") not in FOUR_CAUSES
        ):
            raise ValueError("Mapping de suivi boundary incomplet ou trompeur.")
        slot_by_chain[chain] = slot
        mapped_suppliers.append(supplier)
    if (
        set(slot_by_chain.values()) != expected_slots
        or set(slot_by_chain) != set(follow_up_chains)
        or [
            chain
            for chain, _slot in sorted(slot_by_chain.items(), key=lambda item: item[1])
        ]
        != follow_up_chains
        or sorted(mapped_suppliers) != follow_up_ids
    ):
        raise ValueError("Mappings et groupe de suivi boundary divergent.")

    required_true = (
        "follow_up_group_is_unordered",
        "priority_fields_are_legacy_compatibility_aliases",
        "selected_subset_covers_candidate_pool",
        "selected_subset_covers_service_nonseparation_group",
        "service_nonseparation_group_fully_followed_up",
        "extension_is_post_selection_characterization_not_confirmation",
        "independent_confirmation_required_for_confirmatory_top3",
        "lane_specific_peak_flow_window_selection",
        "integrity_digest_not_authenticated_signature",
        "internal_consistency_recomputed_from_source",
    )
    required_false = (
        "slot_order_has_scientific_meaning",
        "scientific_order_claimed",
        "selected_subset_covers_boundary_universal_group",
        "driver_lane_uniqueness_claimed",
        "selection_and_assessment_seed_blocks_independent",
        "post_selection_confirmatory_inference_evaluable",
        "population_or_out_of_sample_top3_claimed",
        "extension_seed_blocks_independent_of_priority_selection",
        "cross_baseline_service_level_priority_robustness_evaluable",
        "cross_lane_same_calendar_comparison",
        "intrinsic_supplier_reliability_claimed",
        "lane_count_normalization_applied",
        "cryptographic_authentication_present",
        "broad_supply_uncertainty_monte_carlo_claimed",
        "historical_recurrence_evaluable",
        "global_variance_based_sensitivity_evaluable",
        "action_lever_influence_ranking_evaluable",
        "risk_to_risk_cascade_evaluable",
        "network_contagion_probability_evaluable",
        "individual_customer_or_order_attribution_evaluable",
        "revenue_or_penalty_loss_evaluable",
        "counterfactual_entity_identity_validated",
        "network_wide_lot_effect_evaluable",
        "multi_lane_common_cause_lot_effect_evaluable",
        "four_cause_lot_effect_evaluable",
        "temporal_lot_effect_variability_evaluable",
        "lot_effect_recurrence_evaluable",
    )
    if any(lineage.get(field) is not True for field in required_true):
        raise ValueError("Une garde vraie obligatoire manque dans la lignee boundary.")
    if any(lineage.get(field) is not False for field in required_false):
        raise ValueError("Une garde fail-closed manque dans la lignee boundary.")
    if (
        str(lineage.get("quality_hold_event_anchor") or "") != "shipment_decision_day"
        or lineage.get("opening_or_preexisting_in_transit_receipts_affected")
        is not False
        or lineage.get("native_quarantine_inventory_modeled") is not False
        or lineage.get("laboratory_release_process_modeled") is not False
    ):
        raise ValueError("Semantique qualite/quarantaine invalide dans la lignee.")
    if (
        _to_int(lineage.get("causal_lot_pair_count")) != EXPECTED_FOLLOW_UP_LANE_COUNT
        or _to_int(lineage.get("paired_seed_count_per_causal_lot_lane")) != 1
    ):
        raise ValueError("Contrat des illustrations techniques lots invalide.")
    lane_counts_raw = lineage.get("supplier_lane_count_by_id")
    if not isinstance(lane_counts_raw, dict):
        raise ValueError("Comptage de voies fournisseur absent de la lignee.")
    lane_counts = {
        str(supplier): _to_int(count) for supplier, count in lane_counts_raw.items()
    }
    if (
        set(lane_counts) != set(universal_ids)
        or any(count <= 0 for count in lane_counts.values())
        or sum(lane_counts.values()) != EXPECTED_NETWORK_LANE_COUNT
    ):
        raise ValueError(
            "Comptage de voies fournisseur incoherent avec le reseau actif."
        )
    multi_lane_ids = _strict_sorted_unique_strings(
        lineage.get("all_multi_lane_supplier_ids"),
        field="all_multi_lane_supplier_ids",
    )
    multi_lane_chains = lineage.get("all_multi_lane_supplier_active_chain_ids_by_id")
    if (
        tuple(multi_lane_ids) != tuple(sorted(EXPECTED_MULTI_LANE_SUPPLIERS))
        or not isinstance(multi_lane_chains, dict)
        or set(multi_lane_chains) != set(multi_lane_ids)
        or lineage.get("multi_lane_common_cause_scope_complete") is not True
    ):
        raise ValueError("Perimetre des fournisseurs multi-voies non exact.")
    for supplier in multi_lane_ids:
        chains = _strict_sorted_unique_strings(
            multi_lane_chains.get(supplier),
            field=f"all_multi_lane_supplier_active_chain_ids_by_id/{supplier}",
        )
        if len(chains) != lane_counts[supplier] or len(chains) != 2:
            raise ValueError(f"Voies multi-fournisseur non exactes: {supplier}.")
    for field in (
        "priority_boundary_package_signature",
        "priority_boundary_manifest_sha256",
        "priority_boundary_result_sha256",
        "priority_boundary_ranking_sha256",
        "priority_boundary_builder_sha256",
        "source_campaign_manifest_sha256",
        "source_campaign_signature",
    ):
        if len(str(lineage.get(field) or "")) != 64:
            raise ValueError(f"Empreinte de lignee absente ou invalide: {field}.")
    return tuple(follow_up_chains), slot_by_chain


def _validate_live_boundary_from_lineage(lineage: Mapping[str, Any]) -> None:
    boundary_dir = Path(str(lineage.get("priority_boundary_dir") or "")).resolve()
    filenames = {
        "scientific_priority_boundary_audit.json",
        "supplier_metric_rankings.csv",
        "conditional_effect_seed_counts.csv",
        "common_random_numbers_provenance.csv",
        "priority_boundary_audit_manifest.json",
    }
    if (
        not boundary_dir.is_dir()
        or {path.name for path in boundary_dir.iterdir() if path.is_file()} != filenames
        or any(path.is_dir() or path.is_symlink() for path in boundary_dir.iterdir())
    ):
        raise ValueError("Paquet boundary vivant incomplet ou excessif.")
    manifest_path = boundary_dir / "priority_boundary_audit_manifest.json"
    result_path = boundary_dir / "scientific_priority_boundary_audit.json"
    ranking_path = boundary_dir / "supplier_metric_rankings.csv"
    if (
        _sha256(manifest_path)
        != str(lineage.get("priority_boundary_manifest_sha256") or "")
        or _sha256(result_path)
        != str(lineage.get("priority_boundary_result_sha256") or "")
        or _sha256(ranking_path)
        != str(lineage.get("priority_boundary_ranking_sha256") or "")
    ):
        raise ValueError("Le paquet boundary vivant diverge de la lignee.")
    manifest = _read_json(manifest_path)
    signed_fields = (
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
    if (
        str(manifest.get("schema_version") or "")
        != "etudecas.supplier_network_priority_boundary_audit_package.v1"
        or str(manifest.get("status") or "") != "complete"
        or str(manifest.get("package_signature") or "")
        != _canonical_sha256({field: manifest.get(field) for field in signed_fields})
        or str(manifest.get("package_signature") or "")
        != str(lineage.get("priority_boundary_package_signature") or "")
        or str(manifest.get("builder_sha256") or "")
        != str(lineage.get("priority_boundary_builder_sha256") or "")
        or _to_int(manifest.get("bootstrap_resample_count")) != BOOTSTRAP_RESAMPLE_COUNT
        or manifest.get("scoped_descriptive_priority_set_display_allowed") is not False
        or manifest.get("confirmatory_priority_set_release_allowed") is not False
        or manifest.get("global_priority_release_allowed") is not False
        or manifest.get("action_promotion_allowed") is not False
        or manifest.get("integrity_digest_not_authenticated_signature") is not True
        or manifest.get("cryptographic_authentication_present") is not False
        or manifest.get("internal_consistency_recomputed_from_source") is not True
    ):
        raise ValueError("Manifeste boundary vivant invalide ou promotionnel.")
    artifact_hashes = manifest.get("artifact_file_sha256")
    expected_artifacts = filenames - {"priority_boundary_audit_manifest.json"}
    if (
        not isinstance(artifact_hashes, dict)
        or set(artifact_hashes) != expected_artifacts
    ):
        raise ValueError("Inventaire scientifique boundary invalide.")
    if any(
        _sha256(boundary_dir / name) != str(expected)
        for name, expected in artifact_hashes.items()
    ):
        raise ValueError("Empreinte scientifique boundary invalide.")
    source_hashes = manifest.get("source_file_sha256") or {}
    if str(source_hashes.get("campaign_manifest.json") or "") != str(
        lineage.get("source_campaign_manifest_sha256") or ""
    ):
        raise ValueError("Campagne source boundary divergente de la lignee.")
    result = _read_json(result_path)
    boundary_mappings = {
        str(row.get("supplier_id") or ""): row
        for row in result.get("envelope_service_driver_mappings") or []
        if isinstance(row, dict)
    }
    follow_up_mappings = {
        str(row.get("supplier_id") or ""): row
        for row in lineage.get("follow_up_driver_mappings") or []
        if isinstance(row, dict)
    }
    if (
        result.get("scoped_descriptive_priority_set_display_allowed") is not False
        or sorted(result.get("envelope_service_nonseparation_group_supplier_ids") or [])
        != list(lineage.get("service_nonseparation_group_supplier_ids") or [])
        or sorted(result.get("priority_group_supplier_ids_if_no_universal_top3") or [])
        != list(
            lineage.get("boundary_universal_nonseparation_group_supplier_ids") or []
        )
        or result.get("confirmatory_priority_set_release_allowed") is not False
        or result.get("global_priority_release_allowed") is not False
        or result.get("action_promotion_allowed") is not False
    ):
        raise ValueError("Resultat boundary vivant divergent ou promotionnel.")
    for supplier, mapping in follow_up_mappings.items():
        boundary_mapping = boundary_mappings.get(supplier)
        if boundary_mapping is None or any(
            str(boundary_mapping.get(field) or "") != str(mapping.get(field) or "")
            for field in (
                "supplier_id",
                "driver_chain_id",
                "driver_scenario_id",
                "driver_failure_mode",
                "driver_selection_rule",
            )
        ):
            raise ValueError(f"Mapping driver boundary vivant divergent: {supplier}.")


def _validate_plan_manifest(plan_dir: Path) -> dict[str, Any]:
    # Rebuild the plan independently from its closed campaign and live boundary
    # before relying on any self-declared digest.  This is the authenticated-by-
    # recomputation step; the JSON SHA fields alone are only integrity digests.
    planner_validation = planner.validate_plan_artifact(
        plan_dir,
        require_boundary_lineage=True,
    )
    if (
        planner_validation.get("valid") is not True
        or planner_validation.get("final_eligible") is not True
        or planner_validation.get("priority_boundary_lineage_present") is not True
    ):
        raise ValueError("Le plan ne passe pas sa reconstruction boundary publiee.")
    plan_entries = list(plan_dir.iterdir())
    observed = {path.name for path in plan_entries if path.is_file()}
    if observed != set(PLAN_FILES) or any(
        path.is_dir() or path.is_symlink() for path in plan_entries
    ):
        raise ValueError("Inventaire disque du plan signe incomplet ou excessif.")
    manifest = _read_json(plan_dir / "post_priority_extensions_plan_manifest.json")
    if (
        str(manifest.get("schema_version") or "")
        != "etudecas.supplier_network_post_priority_extensions.plan.v1"
    ):
        raise ValueError("Version du plan signe inconnue.")
    if str(manifest.get("status") or "") != "planned_not_executed":
        raise ValueError("Le plan signe a un statut inattendu.")
    if _as_bool(manifest.get("execution_enabled")):
        raise ValueError("Le plan signe ne doit pas activer l'execution.")
    expected_hashed_files = set(PLAN_FILES) - {
        "post_priority_extensions_plan_manifest.json"
    }
    declared_hashes = dict(manifest.get("plan_file_hashes") or {})
    if set(declared_hashes) != expected_hashed_files:
        raise ValueError("Inventaire des empreintes du plan incomplet ou excessif.")
    for name, expected in declared_hashes.items():
        if _sha256(plan_dir / name) != str(expected):
            raise ValueError(f"Empreinte du plan invalide: {name}")
    signature_payload = manifest.get("signature_payload")
    if not isinstance(signature_payload, dict):
        raise ValueError("Charge utile de signature du plan absente.")
    if str(manifest.get("plan_signature") or "") != _canonical_sha256(
        signature_payload
    ):
        raise ValueError("Signature canonique du plan invalide.")
    if signature_payload.get("execution_enabled") is not False:
        raise ValueError("La signature du plan n'est pas fail-closed.")
    if signature_payload.get("calendar_windows") != [
        [start, end] for _index, start, end in CALENDAR_WINDOWS
    ]:
        raise ValueError("Les quatre fenetres temporelles signees ne sont pas exactes.")
    seeds = tuple(
        _to_int(value) for value in signature_payload.get("confirmation_seeds") or []
    )
    if len(seeds) != EXPECTED_PAIRED_SEED_COUNT or len(set(seeds)) != len(seeds):
        raise ValueError("Le plan ne signe pas exactement 30 graines uniques.")
    lineage = signature_payload.get("priority_selection_lineage")
    follow_up_chain_ids, _slot_by_chain = _validate_priority_selection_lineage(
        lineage,
        declared_digest=signature_payload.get("priority_selection_lineage_sha256"),
    )
    _validate_live_boundary_from_lineage(lineage)
    if (
        manifest.get("priority_selection_lineage") != lineage
        or manifest.get("priority_selection_lineage_sha256")
        != signature_payload.get("priority_selection_lineage_sha256")
        or list(signature_payload.get("priority_chain_ids") or [])
        != list(follow_up_chain_ids)
        or manifest.get("priority_chain_ids")
        != signature_payload.get("priority_chain_ids")
        or str(signature_payload.get("source_campaign_signature") or "")
        != str(lineage.get("source_campaign_signature") or "")
    ):
        raise ValueError("Lignee de suivi top-level et payload signe divergente.")
    if tuple(signature_payload.get("multi_lane_supplier_ids") or ()) != (
        EXPECTED_MULTI_LANE_SUPPLIERS
    ):
        raise ValueError("Les deux fournisseurs multi-voies signes ne sont pas exacts.")
    if list(signature_payload.get("all_multi_lane_supplier_ids") or []) != list(
        lineage.get("all_multi_lane_supplier_ids") or []
    ) or dict(
        signature_payload.get("all_multi_lane_supplier_active_chain_ids_by_id") or {}
    ) != dict(lineage.get("all_multi_lane_supplier_active_chain_ids_by_id") or {}):
        raise ValueError("Perimetre multi-voies top-level et lignee divergent.")
    lock = signature_payload.get("execution_configuration_lock") or {}
    for field in (
        "graph_sha256",
        "profile_sha256",
        "engine_sha256",
        "v4_extraction_core_sha256",
    ):
        value = str(lock.get(field) or "")
        if len(value) != 64:
            raise ValueError(f"Verrou de configuration absent ou invalide: {field}")
    if str(lock.get("scenario_id") or "") != "scn:BASE":
        raise ValueError("Le scenario verrouille du plan doit etre scn:BASE.")
    design_hashes = signature_payload.get("design_hashes") or {}
    if set(design_hashes) != {
        "paired_baseline_design",
        "multi_lane_common_cause_design",
        "temporal_robustness_design",
        "priority_four_business_causes_design",
        "causal_lot_attribution_design",
        "promotion_controls",
        "plan_readme_sha256",
    }:
        raise ValueError("Inventaire des signatures de conception incomplet.")
    recomputed_design_hashes = _recomputed_plan_design_hashes(plan_dir)
    if design_hashes != recomputed_design_hashes:
        raise ValueError(
            "Les design_hashes signes ne correspondent pas aux artefacts du plan."
        )
    if manifest.get("execution_configuration_lock") != signature_payload.get(
        "execution_configuration_lock"
    ):
        raise ValueError(
            "Le verrou de configuration top-level diverge de la signature."
        )
    if manifest.get("planned_case_counts") != signature_payload.get(
        "planned_case_counts"
    ):
        raise ValueError("Les compteurs top-level du plan divergent de la signature.")
    mirrored_fields = (
        "contract_revision",
        "planner_builder_sha256",
        "source_campaign_signature",
        "confirmation_seeds",
        "calendar_windows",
        "multi_lane_supplier_ids",
        "all_multi_lane_supplier_ids",
        "all_multi_lane_supplier_active_chain_ids_by_id",
        "temporal_horizon_contract",
        "design_hashes",
        "planned_case_counts",
        "execution_configuration_lock",
        "execution_enabled",
    )
    if any(
        manifest.get(field) != signature_payload.get(field) for field in mirrored_fields
    ):
        raise ValueError("Le manifeste et son payload signe divergent.")
    planner_builder = str(signature_payload.get("planner_builder_sha256") or "")
    if (
        planner_builder != EXPECTED_PLANNER_BUILDER_SHA256
        or _sha256(Path(planner.__file__).resolve()) != EXPECTED_PLANNER_BUILDER_SHA256
    ):
        raise ValueError("Version du planner publie non autorisee par cet audit.")
    if str(signature_payload.get("contract_revision") or "") != (
        "setwise_descriptive_postselection_lineage_2026_09"
    ):
        raise ValueError("Revision du contrat plan inconnue.")
    if dict(signature_payload.get("source_file_hashes") or {}) != dict(
        manifest.get("source_artifact_file_hashes") or {}
    ):
        raise ValueError("Empreintes source top-level et payload signe divergentes.")
    temporal_horizon = signature_payload.get("temporal_horizon_contract")
    if not isinstance(temporal_horizon, dict):
        raise ValueError("Contrat d'horizon temporel absent.")
    outcome_specs = temporal_horizon.get("outcome_specs")
    if not isinstance(outcome_specs, list) or len(outcome_specs) != len(
        CALENDAR_WINDOWS
    ):
        raise ValueError("Les quatre outcomes temporels ne sont pas signes.")
    simulation_days = _to_int(temporal_horizon.get("simulation_days"))
    tail = _to_int(temporal_horizon.get("local_outcome_tail_after_incident_end_days"))
    for (index, stress_start, stress_end), spec in zip(CALENDAR_WINDOWS, outcome_specs):
        if (
            not isinstance(spec, dict)
            or str(spec.get("outcome_spec_id") or "")
            != f"calendar_window_{index}_fixed_followup"
            or _to_int(spec.get("incident_start_day")) != stress_start
            or _to_int(spec.get("incident_end_day")) != stress_end
            or _to_int(spec.get("outcome_start_day")) != stress_start
            or _to_int(spec.get("outcome_end_day")) != stress_end + tail
            or _to_int(spec.get("outcome_day_count"))
            != stress_end + tail - stress_start + 1
            or _to_int(spec.get("outcome_end_day")) >= simulation_days
        ):
            raise ValueError("Outcome temporel local incoherent avec sa fenetre.")
    if (
        simulation_days <= 720
        or tail <= 0
        or temporal_horizon.get("extended_horizon_input_support_pass") is not True
        or temporal_horizon.get("right_censoring_possible") is not True
        or temporal_horizon.get("late_arrival_residual_must_be_reported") is not True
        or temporal_horizon.get("period_specific_conditional_effects_described")
        is not True
        or temporal_horizon.get("temporal_effect_causal_state_dependence_evaluable")
        is not False
        or temporal_horizon.get("preincident_complete_engine_checkpoint_available")
        is not False
        or str(temporal_horizon.get("network_recovery_metric_status") or "")
        != "excluded_invalid_common_window"
    ):
        raise ValueError("Gardes scientifiques de l'horizon temporel invalides.")
    counts = signature_payload.get("planned_case_counts") or {}
    expected_counts = {
        "follow_up_lane_count": EXPECTED_FOLLOW_UP_LANE_COUNT,
        "multi_lane_common_cause_stress_cases": EXPECTED_COMMON_CAUSE_CASE_COUNT,
        "temporal_robustness_stress_cases": EXPECTED_TEMPORAL_CASE_COUNT,
        "priority_four_business_causes_stress_cases": EXPECTED_FOUR_CAUSE_CASE_COUNT,
        "causal_lot_stress_cases": EXPECTED_CAUSAL_CASE_COUNT,
    }
    if any(_to_int(counts.get(key)) != value for key, value in expected_counts.items()):
        raise ValueError(
            "Compteurs d'extension signes incompatibles avec le groupe de quatre."
        )
    return manifest


def _baseline_contract(
    baseline_rows: Sequence[Mapping[str, Any]],
    seeds: Sequence[int],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[tuple[int, int, bool, str], str],
]:
    by_id: dict[str, dict[str, Any]] = {}
    expected_seeds = set(seeds)
    metric_seed_seen: dict[str, set[int]] = defaultdict(set)
    first_owner_by_fingerprint: dict[tuple[int, int, bool, str], str] = {}
    for raw in baseline_rows:
        case_id = str(raw.get("baseline_case_id") or "").strip()
        seed = _to_int(raw.get("seed"))
        trace = _as_bool(raw.get("lot_trace_required"))
        pairing = str(raw.get("pairing_block_id") or "").strip()
        simulation_days = _to_int(raw.get("simulation_days"))
        bundle_sha = str(raw.get("outcome_bundle_sha256") or "").strip()
        raw_specs = str(raw.get("outcome_specs_json") or "").strip()
        try:
            specs = json.loads(raw_specs)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Bundle outcome baseline invalide: {case_id}.") from exc
        spec_ids = (
            [
                str(spec.get("outcome_spec_id") or "").strip()
                for spec in specs
                if isinstance(spec, dict)
            ]
            if isinstance(specs, list)
            else []
        )
        if (
            not case_id
            or seed not in expected_seeds
            or not pairing
            or simulation_days <= 0
            or len(bundle_sha) != 64
            or not isinstance(specs, list)
            or not specs
            or len(spec_ids) != len(specs)
            or len(spec_ids) != len(set(spec_ids))
            or _canonical_sha256({"outcome_specs": specs}) != bundle_sha
        ):
            raise ValueError("Reference planifiee incomplete.")
        for spec in specs:
            if not isinstance(spec, dict):
                raise ValueError(f"Outcome baseline invalide: {case_id}.")
            start = _to_int(spec.get("outcome_start_day"))
            end = _to_int(spec.get("outcome_end_day"))
            if (
                not str(spec.get("outcome_spec_id") or "").strip()
                or start < 0
                or end < start
                or end >= simulation_days
                or _to_int(spec.get("outcome_day_count")) != end - start + 1
            ):
                raise ValueError(f"Outcome baseline hors horizon: {case_id}.")
        if case_id in by_id:
            raise ValueError(f"Identifiant de reference duplique: {case_id}")
        logical_key = _baseline_case_key(case_id, seed)
        row = dict(raw)
        row["_logical_case_key"] = logical_key
        row["_seed"] = seed
        row["_trace"] = trace
        row["_simulation_days"] = simulation_days
        row["_outcome_bundle_sha256"] = bundle_sha
        row["_outcome_specs"] = specs
        by_id[case_id] = row
        first_owner_by_fingerprint.setdefault(
            (seed, simulation_days, trace, bundle_sha), logical_key
        )
        scope = str(raw.get("paired_scope") or "")
        if scope not in {
            "common_cause|four_business_causes",
            "temporal_period_characterization",
            "causal_lot_attribution_subset",
        }:
            raise ValueError(f"Portee baseline inconnue: {scope!r}.")
        if scope in {
            "common_cause|four_business_causes",
            "temporal_period_characterization",
        }:
            if seed in metric_seed_seen[scope]:
                raise ValueError(
                    f"Reference metrique dupliquee pour {scope}/graine {seed}."
                )
            metric_seed_seen[scope].add(seed)
    for scope in (
        "common_cause|four_business_causes",
        "temporal_period_characterization",
    ):
        if metric_seed_seen[scope] != expected_seeds:
            raise ValueError(f"Les 30 references {scope} ne sont pas exactes.")
    return by_id, first_owner_by_fingerprint


def _validate_design_matrices(
    *,
    plan_manifest: Mapping[str, Any],
    baseline_rows: Sequence[Mapping[str, Any]],
    design_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[
    tuple[int, ...],
    dict[str, list[CaseSpec]],
    dict[str, dict[str, Any]],
    dict[tuple[int, int, bool, str], str],
]:
    signature = plan_manifest.get("signature_payload") or {}
    seeds = tuple(_to_int(value) for value in signature.get("confirmation_seeds") or [])
    expected_seed_set = set(seeds)
    lineage = signature.get("priority_selection_lineage")
    follow_up_chain_ids, expected_slot_by_chain = _validate_priority_selection_lineage(
        lineage,
        declared_digest=signature.get("priority_selection_lineage_sha256"),
    )
    mapping_by_chain = {
        str(row["driver_chain_id"]): dict(row)
        for row in lineage["follow_up_driver_mappings"]
    }
    baseline_by_id, first_owner = _baseline_contract(baseline_rows, seeds)
    cases: dict[str, list[CaseSpec]] = {}
    for extension, rows in design_rows.items():
        parsed = [_parse_case(row, extension) for row in rows]
        keys = [case.case_key for case in parsed]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Cas dupliques dans la conception {extension}.")
        for raw, case in zip(rows, parsed):
            if "priority_rank_from_main_lane_test" in raw:
                raise ValueError("Un ancien rang de voie subsiste dans le plan final.")
            if extension in {
                "temporal_robustness",
                "priority_four_business_causes",
            } and (
                raw.get("slot_order_has_scientific_meaning") is not False
                and str(raw.get("slot_order_has_scientific_meaning") or "").lower()
                != "false"
            ):
                raise ValueError(
                    f"Le slot revendique un ordre scientifique: {case.case_key}."
                )
            if extension == "multi_lane_supplier_common_cause" and (
                not _as_bool(raw.get("joint_multi_lane_conditional_effect_evaluable"))
                or _as_bool(raw.get("multi_lane_interaction_or_synergy_evaluable"))
                or _as_bool(raw.get("cascade_amplification_claimed"))
            ):
                raise ValueError(f"Semantique cause commune invalide: {case.case_key}.")
            if extension in {
                "temporal_robustness",
                "priority_four_business_causes",
            } and not _as_bool(
                raw.get("extension_is_post_selection_characterization_not_confirmation")
            ):
                raise ValueError(f"Garde post-selection absente: {case.case_key}.")
            if extension == "causal_lot_attribution_subset" and (
                raw.get("counterfactual_entity_identity_validated") is not False
                and str(
                    raw.get("counterfactual_entity_identity_validated") or ""
                ).lower()
                != "false"
                or raw.get("causal_lot_attribution_available") is not False
                and str(raw.get("causal_lot_attribution_available") or "").lower()
                != "false"
                or not _as_bool(raw.get("heuristic_comparison_display_allowed"))
            ):
                raise ValueError(f"Garde heuristique lot invalide: {case.case_key}.")
            baseline = baseline_by_id.get(case.paired_baseline_case_id)
            if baseline is None:
                raise ValueError(f"Reference absente pour {case.case_key}.")
            if baseline["_seed"] != case.seed:
                raise ValueError(
                    f"Graine de reference non appariee pour {case.case_key}."
                )
            if str(baseline.get("pairing_block_id") or "") != case.pairing_block_id:
                raise ValueError(f"Bloc d'appariement incoherent pour {case.case_key}.")
            if baseline["_trace"] != case.lot_trace_required:
                raise ValueError(f"Tracage lots non apparie pour {case.case_key}.")
            if (
                baseline["_simulation_days"] != case.simulation_days
                or baseline["_outcome_bundle_sha256"] != case.outcome_bundle_sha256
            ):
                raise ValueError(f"Horizon/bundle non apparie pour {case.case_key}.")
            matching_specs = [
                spec
                for spec in baseline["_outcome_specs"]
                if str(spec.get("outcome_spec_id") or "") == case.outcome_spec_id
            ]
            if len(matching_specs) != 1:
                raise ValueError(
                    f"Outcome absent ou duplique dans la reference: {case.case_key}."
                )
            spec = matching_specs[0]
            if (
                _to_int(spec.get("outcome_start_day")) != case.outcome_start_day
                or _to_int(spec.get("outcome_end_day")) != case.outcome_end_day
                or _to_int(spec.get("outcome_day_count")) != case.outcome_day_count
            ):
                raise ValueError(f"Outcome non apparie pour {case.case_key}.")
        cases[extension] = parsed

    referenced_baseline_ids = {
        case.paired_baseline_case_id
        for extension_cases in cases.values()
        for case in extension_cases
    }
    if set(baseline_by_id) != referenced_baseline_ids:
        raise ValueError(
            "Les references baseline contiennent des lignes inutilisees ou en manquent."
        )
    full_horizon_specs = [
        {
            "outcome_spec_id": "full_horizon_J0_J719",
            "outcome_start_day": 0,
            "outcome_end_day": 719,
            "outcome_day_count": 720,
        }
    ]
    temporal_horizon = signature.get("temporal_horizon_contract") or {}
    temporal_specs = temporal_horizon.get("outcome_specs") or []
    for baseline in baseline_by_id.values():
        scope = str(baseline.get("paired_scope") or "")
        expected_specs = (
            temporal_specs
            if scope == "temporal_period_characterization"
            else full_horizon_specs
        )
        expected_days = (
            _to_int(temporal_horizon.get("simulation_days"))
            if scope == "temporal_period_characterization"
            else 720
        )
        if (
            baseline["_outcome_specs"] != expected_specs
            or baseline["_simulation_days"] != expected_days
            or baseline["_outcome_bundle_sha256"]
            != _canonical_sha256({"outcome_specs": expected_specs})
        ):
            raise ValueError(
                f"Bundle baseline non canonique pour {scope}/"
                f"{baseline.get('baseline_case_id')}."
            )

    temporal = cases["temporal_robustness"]
    if len(temporal) != EXPECTED_TEMPORAL_CASE_COUNT:
        raise ValueError("La matrice temporelle ne contient pas exactement 480 cas.")
    temporal_groups: dict[tuple[str, int], list[CaseSpec]] = defaultdict(list)
    temporal_slot_by_chain: dict[str, set[int]] = defaultdict(set)
    temporal_cause_by_chain: dict[str, set[str]] = defaultdict(set)
    temporal_lane_by_chain: dict[str, set[Lane]] = defaultdict(set)
    for case in temporal:
        if len(case.lanes) != 1 or len(case.products) != 1:
            raise ValueError(
                f"Cas temporel non mono-voie/mono-produit: {case.case_key}"
            )
        lane = case.lanes[0]
        if (
            lane.chain_id not in follow_up_chain_ids
            or case.selection_slot != expected_slot_by_chain.get(lane.chain_id)
            or lane.supplier_id
            != str(mapping_by_chain.get(lane.chain_id, {}).get("supplier_id") or "")
        ):
            raise ValueError(f"Voie/slot temporel hors plan: {case.case_key}")
        expected_window = {
            index: (start, end) for index, start, end in CALENDAR_WINDOWS
        }.get(case.window_index)
        if expected_window != (case.start_day, case.end_day):
            raise ValueError(f"Fenetre temporelle invalide: {case.case_key}")
        horizon = signature.get("temporal_horizon_contract") or {}
        outcome_specs = {
            str(spec.get("outcome_spec_id") or ""): spec
            for spec in horizon.get("outcome_specs") or []
        }
        expected_outcome_id = f"calendar_window_{case.window_index}_fixed_followup"
        expected_outcome = outcome_specs.get(expected_outcome_id)
        if (
            expected_outcome is None
            or case.simulation_days != _to_int(horizon.get("simulation_days"))
            or case.outcome_bundle_sha256
            != str(horizon.get("outcome_bundle_sha256") or "")
            or case.outcome_spec_id != expected_outcome_id
            or case.outcome_start_day
            != _to_int(expected_outcome.get("outcome_start_day"))
            or case.outcome_end_day != _to_int(expected_outcome.get("outcome_end_day"))
            or case.outcome_day_count
            != _to_int(expected_outcome.get("outcome_day_count"))
            or case.preincident_snapshot_day != case.start_day - 1
            or case.lot_trace_required
        ):
            raise ValueError(f"Contrat outcome temporel invalide: {case.case_key}")
        temporal_groups[(lane.chain_id, case.window_index)].append(case)
        temporal_slot_by_chain[lane.chain_id].add(case.selection_slot)
        temporal_cause_by_chain[lane.chain_id].add(case.failure_mode)
        temporal_lane_by_chain[lane.chain_id].add(lane)
    expected_temporal_groups = {
        (chain, index)
        for chain in follow_up_chain_ids
        for index, _start, _end in CALENDAR_WINDOWS
    }
    if set(temporal_groups) != expected_temporal_groups:
        raise ValueError("Les 4 voies x 4 fenetres temporelles ne sont pas exactes.")
    for key, group in temporal_groups.items():
        if {case.seed for case in group} != expected_seed_set or len(group) != len(
            seeds
        ):
            raise ValueError(f"Graines temporelles incompletes pour {key}.")
    if any(len(values) != 1 for values in temporal_slot_by_chain.values()):
        raise ValueError("Un slot temporel varie selon les fenetres ou graines.")
    if {next(iter(values)) for values in temporal_slot_by_chain.values()} != set(
        range(1, EXPECTED_FOLLOW_UP_LANE_COUNT + 1)
    ):
        raise ValueError("Les quatre slots temporels d'execution ne sont pas exacts.")
    if any(len(values) != 1 for values in temporal_cause_by_chain.values()):
        raise ValueError("La cause severe retenue varie entre les fenetres.")
    if any(
        next(iter(temporal_cause_by_chain[chain]))
        != str(mapping_by_chain[chain].get("driver_failure_mode") or "")
        for chain in follow_up_chain_ids
    ):
        raise ValueError("La cause temporelle ne reprend pas le driver boundary signe.")
    if any(len(values) != 1 for values in temporal_lane_by_chain.values()):
        raise ValueError(
            "L'identite physique d'une voie varie dans la matrice temporelle."
        )

    four = cases["priority_four_business_causes"]
    if len(four) != EXPECTED_FOUR_CAUSE_CASE_COUNT:
        raise ValueError("La matrice quatre causes ne contient pas exactement 480 cas.")
    four_groups: dict[tuple[str, str], list[CaseSpec]] = defaultdict(list)
    four_slot_by_chain: dict[str, set[int]] = defaultdict(set)
    four_lane_by_chain: dict[str, set[Lane]] = defaultdict(set)
    four_window_by_chain: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for case in four:
        if len(case.lanes) != 1 or len(case.products) != 1:
            raise ValueError(f"Cas quatre causes non mono-voie: {case.case_key}")
        lane = case.lanes[0]
        if (
            lane.chain_id not in follow_up_chain_ids
            or case.selection_slot != expected_slot_by_chain.get(lane.chain_id)
            or lane.supplier_id
            != str(mapping_by_chain.get(lane.chain_id, {}).get("supplier_id") or "")
        ):
            raise ValueError(f"Voie/slot quatre causes hors plan: {case.case_key}")
        full_horizon_spec = {
            "outcome_specs": [
                {
                    "outcome_spec_id": "full_horizon_J0_J719",
                    "outcome_start_day": 0,
                    "outcome_end_day": 719,
                    "outcome_day_count": 720,
                }
            ]
        }
        if (
            case.simulation_days != 720
            or case.outcome_spec_id != "full_horizon_J0_J719"
            or (case.outcome_start_day, case.outcome_end_day, case.outcome_day_count)
            != (0, 719, 720)
            or case.outcome_bundle_sha256 != _canonical_sha256(full_horizon_spec)
        ):
            raise ValueError(f"Horizon quatre-causes invalide: {case.case_key}")
        four_groups[(lane.chain_id, case.failure_mode)].append(case)
        four_slot_by_chain[lane.chain_id].add(case.selection_slot)
        four_lane_by_chain[lane.chain_id].add(lane)
        four_window_by_chain[lane.chain_id].add((case.start_day, case.end_day))
    expected_four_groups = {
        (chain, cause) for chain in follow_up_chain_ids for cause in FOUR_CAUSES
    }
    if set(four_groups) != expected_four_groups:
        raise ValueError("Les 4 voies x 4 causes ne sont pas exactes.")
    for key, group in four_groups.items():
        if {case.seed for case in group} != expected_seed_set or len(group) != len(
            seeds
        ):
            raise ValueError(f"Graines quatre causes incompletes pour {key}.")
    if any(len(values) != 1 for values in four_slot_by_chain.values()):
        raise ValueError("Un slot quatre-causes varie selon les causes ou graines.")
    if {next(iter(values)) for values in four_slot_by_chain.values()} != set(
        range(1, EXPECTED_FOLLOW_UP_LANE_COUNT + 1)
    ):
        raise ValueError("Les quatre slots quatre-causes ne sont pas exacts.")
    if any(len(values) != 1 for values in four_lane_by_chain.values()):
        raise ValueError(
            "L'identite physique d'une voie varie entre les quatre causes."
        )
    if any(len(values) != 1 for values in four_window_by_chain.values()):
        raise ValueError("La fenetre active d'une voie varie entre les quatre causes.")
    if any(
        four_lane_by_chain[chain] != temporal_lane_by_chain[chain]
        for chain in follow_up_chain_ids
    ):
        raise ValueError(
            "Les voies temporelles et quatre-causes ne sont pas identiques."
        )

    common = cases["multi_lane_supplier_common_cause"]
    if len(common) != EXPECTED_COMMON_CAUSE_CASE_COUNT:
        raise ValueError("La matrice cause commune ne contient pas exactement 240 cas.")
    common_groups: dict[tuple[str, str], list[CaseSpec]] = defaultdict(list)
    common_lanes_by_supplier: dict[str, set[tuple[Lane, ...]]] = defaultdict(set)
    common_windows_by_supplier: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for case in common:
        suppliers = {lane.supplier_id for lane in case.lanes}
        if (
            len(case.lanes) != 2
            or len(suppliers) != 1
            or next(iter(suppliers)) not in EXPECTED_MULTI_LANE_SUPPLIERS
        ):
            raise ValueError(f"Cas cause commune non conforme: {case.case_key}")
        supplier = next(iter(suppliers))
        full_horizon_spec = {
            "outcome_specs": [
                {
                    "outcome_spec_id": "full_horizon_J0_J719",
                    "outcome_start_day": 0,
                    "outcome_end_day": 719,
                    "outcome_day_count": 720,
                }
            ]
        }
        if (
            str(case.lanes[0].supplier_id) != supplier
            or case.selection_slot >= 0
            or case.simulation_days != 720
            or case.outcome_spec_id != "full_horizon_J0_J719"
            or (case.outcome_start_day, case.outcome_end_day, case.outcome_day_count)
            != (0, 719, 720)
            or case.outcome_bundle_sha256 != _canonical_sha256(full_horizon_spec)
        ):
            raise ValueError(
                f"Fournisseur/horizon cause commune incoherent: {case.case_key}"
            )
        common_groups[(supplier, case.failure_mode)].append(case)
        common_lanes_by_supplier[supplier].add(
            tuple(sorted(case.lanes, key=lambda lane: lane.chain_id))
        )
        common_windows_by_supplier[supplier].add((case.start_day, case.end_day))
    expected_common_groups = {
        (supplier, cause)
        for supplier in EXPECTED_MULTI_LANE_SUPPLIERS
        for cause in FOUR_CAUSES
    }
    if set(common_groups) != expected_common_groups:
        raise ValueError("Les 2 fournisseurs x 4 causes communes ne sont pas exacts.")
    for key, group in common_groups.items():
        if {case.seed for case in group} != expected_seed_set or len(group) != len(
            seeds
        ):
            raise ValueError(f"Graines cause commune incompletes pour {key}.")
    if any(len(values) != 1 for values in common_lanes_by_supplier.values()):
        raise ValueError(
            "Les deux voies d'un fournisseur commun varient entre les cas."
        )
    if any(len(values) != 1 for values in common_windows_by_supplier.values()):
        raise ValueError("La fenetre commune varie selon la cause ou la graine.")

    causal = cases["causal_lot_attribution_subset"]
    if len(causal) != EXPECTED_CAUSAL_CASE_COUNT:
        raise ValueError("Le sous-ensemble lot ne contient pas exactement quatre cas.")
    if (
        {case.lanes[0].chain_id for case in causal} != set(follow_up_chain_ids)
        or len({case.case_key for case in causal}) != EXPECTED_CAUSAL_CASE_COUNT
        or len({case.seed for case in causal}) != 1
        or {case.seed for case in causal} != {min(seeds)}
    ):
        raise ValueError(
            "Les illustrations lots ne reprennent pas le groupe signe a une graine."
        )
    for case in causal:
        lane = case.lanes[0]
        if (
            len(case.lanes) != 1
            or len(case.products) != 1
            or not case.lot_trace_required
            or case.selection_slot != expected_slot_by_chain[lane.chain_id]
            or lane.supplier_id
            != str(mapping_by_chain[lane.chain_id].get("supplier_id") or "")
            or {lane} != temporal_lane_by_chain[lane.chain_id]
            or case.failure_mode != next(iter(temporal_cause_by_chain[lane.chain_id]))
            or (case.start_day, case.end_day)
            != next(iter(four_window_by_chain[lane.chain_id]))
            or case.simulation_days != 720
            or case.outcome_spec_id != "full_horizon_J0_J719"
            or (case.outcome_start_day, case.outcome_end_day, case.outcome_day_count)
            != (0, 719, 720)
            or case.outcome_bundle_sha256
            != _canonical_sha256(
                {
                    "outcome_specs": [
                        {
                            "outcome_spec_id": "full_horizon_J0_J719",
                            "outcome_start_day": 0,
                            "outcome_end_day": 719,
                            "outcome_day_count": 720,
                        }
                    ]
                }
            )
        ):
            raise ValueError(
                "Les illustrations lots ne reprennent pas exactement les voies suivies."
            )
    expected_follow_up_suppliers = set(lineage.get("follow_up_supplier_ids") or [])
    observed_follow_up_suppliers = {
        case.lanes[0].supplier_id
        for extension in (
            "temporal_robustness",
            "priority_four_business_causes",
            "causal_lot_attribution_subset",
        )
        for case in cases[extension]
    }
    if observed_follow_up_suppliers != expected_follow_up_suppliers:
        raise ValueError(
            "Les fournisseurs des matrices divergent de la lignee boundary."
        )
    return seeds, cases, baseline_by_id, first_owner


def _safe_relative_file(root: Path, relative: Any, *, context: str) -> Path:
    value = str(relative or "").strip()
    if not value or Path(value).is_absolute():
        raise ValueError(f"Chemin relatif invalide ({context}): {value!r}")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Chemin hors du paquet ({context}): {value!r}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"Preuve absente ({context}): {path}")
    return path


def _load_ledger_evidence(
    *,
    runner_dir: Path,
    runner_manifest: Mapping[str, Any],
    ledger: Mapping[str, Any],
    expected_stress_case_keys: set[str],
    expected_owner_keys: set[str],
) -> tuple[dict[str, dict[str, Any]], str]:
    runner_signature = str(runner_manifest.get("runner_signature") or "")
    if str(ledger.get("runner_signature") or "") != runner_signature:
        raise ValueError("Le registre appartient a un autre runner.")
    case_files = dict(ledger.get("case_files") or {})
    case_hashes = dict(ledger.get("case_file_sha256") or {})
    if set(case_files) != set(case_hashes):
        raise ValueError(
            "Registre de preuves incomplet: fichiers et empreintes divergent."
        )
    expected_keys = expected_stress_case_keys | expected_owner_keys
    if set(case_files) != expected_keys:
        missing = sorted(expected_keys - set(case_files))
        extra = sorted(set(case_files) - expected_keys)
        raise ValueError(
            "Jeu exact de preuves du registre invalide: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    paths_seen: set[Path] = set()
    evidence: dict[str, dict[str, Any]] = {}
    for case_key in sorted(case_files):
        expected_relative = (
            Path("ledger_cases")
            / f"{hashlib.sha256(case_key.encode('utf-8')).hexdigest()[:20]}.json"
        )
        declared_relative = Path(str(case_files[case_key] or ""))
        if declared_relative.as_posix() != expected_relative.as_posix():
            raise ValueError(
                f"Chemin de preuve non canonique dans le registre: {case_key}"
            )
        path = _safe_relative_file(
            runner_dir, case_files[case_key], context=f"ledger/{case_key}"
        )
        if path in paths_seen:
            raise ValueError(f"Deux cas pointent vers la meme preuve physique: {path}")
        paths_seen.add(path)
        actual_hash = _sha256(path)
        if actual_hash != str(case_hashes[case_key]):
            raise ValueError(f"Empreinte de preuve invalide: {case_key}")
        payload = _read_json(path)
        if str(payload.get("case_key") or "") != case_key:
            raise ValueError(f"La preuve ne porte pas sa cle de registre: {case_key}")
        evidence[case_key] = payload
    ledger_case_dir = (runner_dir / "ledger_cases").resolve()
    observed_case_files = (
        {path.resolve() for path in ledger_case_dir.iterdir() if path.is_file()}
        if ledger_case_dir.is_dir()
        else set()
    )
    if observed_case_files != paths_seen or any(
        path.is_dir() or path.is_symlink() for path in ledger_case_dir.iterdir()
    ):
        raise ValueError(
            "Inventaire disque ledger_cases incomplet, excessif ou non regulier."
        )
    registry_hash = _canonical_sha256(
        {"case_file_sha256": dict(sorted(case_hashes.items()))}
    )
    return evidence, registry_hash


def _product_metric_index(
    payload: Mapping[str, Any],
    *,
    case_key: str,
    outcome_spec_id: str,
    required_products: set[str],
    allowed_products: set[str],
    exact: bool,
) -> dict[str, Mapping[str, Any]]:
    rows = payload.get("local_product_metrics") or []
    if not isinstance(rows, list):
        raise ValueError(f"Metriques produit invalides dans {case_key}.")
    index: dict[str, Mapping[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError(f"Ligne produit invalide dans {case_key}.")
        if str(raw.get("outcome_spec_id") or "") != outcome_spec_id:
            continue
        product = str(raw.get("product_id") or "").strip()
        if not product or product in index:
            raise ValueError(f"Produit absent ou duplique dans {case_key}: {product!r}")
        uom = str(raw.get("uom") or "").strip()
        if uom != "UN":
            raise ValueError(
                f"Unite produit attendue UN dans {case_key}/{product}, obtenu {uom!r}."
            )
        demand = _number(
            raw.get("demand_qty_denominator"),
            field="demand_qty_denominator",
            context=f"{case_key}/{product}",
        )
        required = _number(
            raw.get("required_qty_denominator"),
            field="required_qty_denominator",
            context=f"{case_key}/{product}",
        )
        served_total = _number(
            raw.get("served_qty_numerator"),
            field="served_qty_numerator",
            context=f"{case_key}/{product}",
        )
        fill_rate = _number(
            raw.get("fill_rate"), field="fill_rate", context=f"{case_key}/{product}"
        )
        served_on_due = _number(
            raw.get("served_on_due_qty_numerator"),
            field="served_on_due_qty_numerator",
            context=f"{case_key}/{product}",
        )
        on_due = _number(
            raw.get("on_due_ratio"),
            field="on_due_ratio",
            context=f"{case_key}/{product}",
        )
        backlog_days = _number(
            raw.get("backlog_qty_days_numerator"),
            field="backlog_qty_days_numerator",
            context=f"{case_key}/{product}",
        )
        backlog_end = _number(
            raw.get("backlog_end_qty"),
            field="backlog_end_qty",
            context=f"{case_key}/{product}",
        )
        released = _number(
            raw.get("released_qty_numerator"),
            field="released_qty_numerator",
            context=f"{case_key}/{product}",
        )
        normalized_backlog = _number(
            raw.get("normalized_backlog_days_per_demand_unit"),
            field="normalized_backlog_days_per_demand_unit",
            context=f"{case_key}/{product}",
        )
        if demand <= 0.0 or required <= 0.0:
            raise ValueError(
                f"Demande non strictement positive dans {case_key}/{product}."
            )
        if served_total < 0.0 or served_on_due < 0.0:
            raise ValueError(f"Service negatif dans {case_key}/{product}.")
        if not (0.0 <= fill_rate <= 1.0) or not (0.0 <= on_due <= 1.0):
            raise ValueError(f"Ratio de service hors [0,1] dans {case_key}/{product}.")
        if backlog_days < 0.0 or backlog_end < 0.0 or released < 0.0:
            raise ValueError(f"Quantite physique negative dans {case_key}/{product}.")
        if (
            not _same_number(served_total / required, fill_rate)
            or not _same_number(served_on_due / demand, on_due)
            or not _same_number(backlog_days / demand, normalized_backlog)
            or _to_int(raw.get("series_day_count"))
            != _to_int(raw.get("outcome_day_count"))
            or not _as_bool(raw.get("series_complete"))
            or str(raw.get("recovery_metric_status") or "") != "excluded_not_redefined"
        ):
            raise ValueError(
                f"Composantes de metrique locale non recomposables dans "
                f"{case_key}/{product}."
            )
        index[product] = raw
    observed_products = set(index)
    valid_set = (
        observed_products == required_products
        if exact
        else required_products <= observed_products <= allowed_products
    )
    if not valid_set:
        raise ValueError(
            f"Jeu exact de produits invalide dans {case_key}: "
            f"requis={sorted(required_products)}, autorise={sorted(allowed_products)}, "
            f"obtenu={sorted(index)}"
        )
    return index


def _flow_metric_index(
    payload: Mapping[str, Any],
    *,
    case_key: str,
    compact_baseline: bool,
) -> dict[tuple[str, str, str, str, int, int], Mapping[str, Any]]:
    rows = payload.get("flow_metrics") or []
    if not isinstance(rows, list):
        raise ValueError(f"Metriques de flux invalides dans {case_key}.")
    index: dict[tuple[str, str, str, str, int, int], Mapping[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError(f"Ligne de flux invalide dans {case_key}.")
        start = (
            _to_int(raw.get("baseline_window_start_day")) if compact_baseline else -1
        )
        end = _to_int(raw.get("baseline_window_end_day")) if compact_baseline else -1
        key = (
            str(raw.get("chain_id") or "").strip(),
            str(raw.get("supplier_id") or "").strip(),
            str(raw.get("item_id") or "").strip(),
            str(raw.get("dst_node_id") or "").strip(),
            start,
            end,
        )
        if not all(key[:4]) or key in index:
            raise ValueError(f"Flux absent ou duplique dans {case_key}: {key}")
        uom = str(raw.get("uom") or "").strip()
        pulled = _number(
            raw.get("pulled_qty"), field="pulled_qty", context=f"{case_key}/{key}"
        )
        shipped = _number(
            raw.get("shipped_qty"), field="shipped_qty", context=f"{case_key}/{key}"
        )
        if not uom or pulled < 0.0 or shipped < 0.0:
            raise ValueError(f"Flux/unite physique invalide dans {case_key}/{key}.")
        if compact_baseline and (start < 0 or end < start):
            raise ValueError(
                f"Fenetre de flux baseline invalide dans {case_key}/{key}."
            )
        index[key] = raw
    return index


def _validate_evidence_pair(
    *,
    case: CaseSpec,
    stress: Mapping[str, Any],
    baseline: Mapping[str, Any],
    expected_products: set[str],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    for payload, label in ((baseline, "reference"), (stress, "incident")):
        if not _as_bool(payload.get("valid")) or payload.get("validation_errors"):
            raise ValueError(f"Preuve {label} invalide pour {case.case_key}.")
        if not str(payload.get("input_sha256") or "") or not str(
            payload.get("j0_state_sha256") or ""
        ):
            raise ValueError(f"Empreinte input/J0 absente ({label}/{case.case_key}).")
        if (
            _to_int(payload.get("simulation_days")) != case.simulation_days
            or str(payload.get("outcome_bundle_sha256") or "")
            != case.outcome_bundle_sha256
        ):
            raise ValueError(
                f"Horizon/bundle de preuve invalide ({label}/{case.case_key})."
            )
        expected_policy = (
            "explicit_annual_cycle_repeat_from_365_day_observed_demand_profile"
            if case.simulation_days > 720
            else "not_applicable_fixed_J0_J719"
        )
        if (
            payload.get("extended_horizon_input_support_pass") is not True
            or str(payload.get("post_J719_extrapolation_policy") or "")
            != expected_policy
        ):
            raise ValueError(f"Support d'horizon invalide ({label}/{case.case_key}).")
    if (
        _to_int(stress.get("seed")) != case.seed
        or _to_int(baseline.get("seed")) != case.seed
    ):
        raise ValueError(f"Graine de preuve non appariee pour {case.case_key}.")
    if str(stress.get("input_sha256")) != str(baseline.get("input_sha256")):
        raise ValueError(f"Entree non appariee pour {case.case_key}.")
    if str(stress.get("j0_state_sha256")) != str(baseline.get("j0_state_sha256")):
        raise ValueError(f"Etat J0 non apparie pour {case.case_key}.")
    if _as_bool(stress.get("resolved_lot_trace_enabled")) != case.lot_trace_required:
        raise ValueError(f"Tracage lots incident non conforme pour {case.case_key}.")
    if _as_bool(baseline.get("resolved_lot_trace_enabled")) != case.lot_trace_required:
        raise ValueError(f"Tracage lots reference non conforme pour {case.case_key}.")
    if (
        baseline.get("configured_event_ids")
        or baseline.get("loaded_event_rows")
        or baseline.get("applied_event_ids")
        or baseline.get("risk_application_rows")
        or baseline.get("risk_load_warnings")
    ):
        raise ValueError(f"La reference n'est pas neutre pour {case.case_key}.")

    expected_event_semantics = sorted(
        (
            case.risk_type,
            lane.supplier_id,
            lane.item_id,
            lane.dst_node_id,
            lane.edge_id,
            case.start_day,
            case.end_day,
            case.mechanism_value,
        )
        for lane in case.lanes
    )
    loaded_rows = stress.get("loaded_event_rows") or []
    if not isinstance(loaded_rows, list):
        raise ValueError(f"Configuration risque invalide pour {case.case_key}.")
    loaded_semantics: list[tuple[Any, ...]] = []
    loaded_ids: list[str] = []
    for raw in loaded_rows:
        if not isinstance(raw, dict):
            raise ValueError(f"Configuration risque invalide pour {case.case_key}.")
        event_id = str(raw.get("event_id") or "").strip()
        if not event_id:
            raise ValueError(f"Identifiant risque vide pour {case.case_key}.")
        loaded_ids.append(event_id)
        loaded_semantics.append(
            (
                str(raw.get("risk_type") or ""),
                str(raw.get("supplier_id") or ""),
                str(raw.get("item_id") or ""),
                str(raw.get("dst_node_id") or ""),
                str(raw.get("edge_id") or ""),
                _to_int(raw.get("start_day")),
                _to_int(raw.get("end_day")),
                _number(
                    raw.get("multiplier"), field="multiplier", context=case.case_key
                ),
            )
        )
    if (
        len(loaded_ids) != len(set(loaded_ids))
        or sorted(loaded_semantics) != expected_event_semantics
        or sorted(str(value) for value in stress.get("configured_event_ids") or [])
        != sorted(loaded_ids)
        or stress.get("risk_load_warnings")
        or len(str(stress.get("risk_input_sha256") or "")) != 64
    ):
        raise ValueError(f"Configuration risque non conforme au plan: {case.case_key}.")
    applied_id_values = [
        str(value).strip() for value in stress.get("applied_event_ids") or []
    ]
    applied_ids = set(applied_id_values)
    application_tokens = _risk_event_tokens(
        stress.get("risk_application_rows") or [], context=case.case_key
    )
    if (
        any(not value for value in applied_id_values)
        or len(applied_id_values) != len(applied_ids)
        or not applied_ids <= set(loaded_ids)
        or application_tokens != applied_ids
    ):
        raise ValueError(f"Evenement risque applique hors plan: {case.case_key}.")
    stress_products = _product_metric_index(
        stress,
        case_key=case.case_key,
        outcome_spec_id=case.outcome_spec_id,
        required_products=set(case.products),
        allowed_products=expected_products,
        exact=True,
    )
    baseline_products = _product_metric_index(
        baseline,
        case_key=f"baseline_for::{case.case_key}",
        outcome_spec_id=case.outcome_spec_id,
        required_products=expected_products,
        allowed_products=expected_products,
        exact=True,
    )
    for product in stress_products:
        incident = stress_products[product]
        reference = baseline_products[product]
        if str(incident.get("uom")) != str(reference.get("uom")):
            raise ValueError(
                f"Unite produit non appariee pour {case.case_key}/{product}."
            )
        incident_demand = _number(
            incident.get("demand_qty_denominator"),
            field="demand_qty_denominator",
            context=f"stress/{case.case_key}/{product}",
        )
        baseline_demand = _number(
            reference.get("demand_qty_denominator"),
            field="demand_qty_denominator",
            context=f"baseline/{case.case_key}/{product}",
        )
        if not _same_number(incident_demand, baseline_demand):
            raise ValueError(f"Demande non appariee pour {case.case_key}/{product}.")
        for payload, label in ((incident, "incident"), (reference, "reference")):
            if (
                _to_int(payload.get("outcome_start_day")) != case.outcome_start_day
                or _to_int(payload.get("outcome_end_day")) != case.outcome_end_day
                or _to_int(payload.get("outcome_day_count")) != case.outcome_day_count
                or not _as_bool(payload.get("series_complete"))
            ):
                raise ValueError(
                    f"Outcome local incomplet ({label}/{case.case_key}/{product})."
                )
    if case.extension == "temporal_robustness":

        def _snapshot_index(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
            rows = payload.get("preincident_state_snapshots") or []
            if not isinstance(rows, list):
                raise ValueError(f"Snapshots preincident invalides: {case.case_key}.")
            indexed: dict[str, Mapping[str, Any]] = {}
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"Snapshot preincident invalide: {case.case_key}.")
                key = str(row.get("outcome_spec_id") or "")
                if not key or key in indexed:
                    raise ValueError(
                        f"Snapshot preincident absent ou duplique: {case.case_key}."
                    )
                payload_value = row.get("payload")
                if not isinstance(payload_value, dict) or str(
                    row.get("preincident_state_sha256") or ""
                ) != _canonical_sha256(payload_value):
                    raise ValueError(
                        f"Empreinte snapshot invalide: {case.case_key}/{key}."
                    )
                indexed[key] = row
            return indexed

        stress_snapshots = _snapshot_index(stress)
        baseline_snapshots = _snapshot_index(baseline)
        if case.outcome_spec_id.startswith("calendar_window_"):
            expected_baseline_snapshot_ids = {
                f"calendar_window_{index}_fixed_followup"
                for index, _start, _end in CALENDAR_WINDOWS
            }
            if (
                set(stress_snapshots) != {case.outcome_spec_id}
                or set(baseline_snapshots) != expected_baseline_snapshot_ids
            ):
                raise ValueError(
                    f"Matrice de snapshots preincident incomplete: {case.case_key}."
                )
        stress_snapshot = stress_snapshots.get(case.outcome_spec_id)
        baseline_snapshot = baseline_snapshots.get(case.outcome_spec_id)
        if (
            stress_snapshot is None
            or baseline_snapshot is None
            or _to_int(stress_snapshot.get("snapshot_day"))
            != case.preincident_snapshot_day
            or _to_int(baseline_snapshot.get("snapshot_day"))
            != case.preincident_snapshot_day
            or str(stress_snapshot.get("preincident_state_sha256") or "")
            != str(baseline_snapshot.get("preincident_state_sha256") or "")
        ):
            raise ValueError(f"Etat preincident non apparie: {case.case_key}.")
    elif stress.get("preincident_state_snapshots") or baseline.get(
        "preincident_state_snapshots"
    ):
        raise ValueError(
            f"Snapshot preincident inattendu hors temporal: {case.case_key}."
        )
    return stress_products, baseline_products


def _validate_metric_rows(
    *,
    extension: str,
    cases: Sequence[CaseSpec],
    rows: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    baseline_owner_by_logical_key: Mapping[str, str],
    expected_products: set[str],
) -> tuple[
    list[PairedEffect],
    dict[str, tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]],
]:
    row_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("case_key") or "").strip(),
            str(row.get("product_id") or "").strip(),
        )
        if not all(key) or key in row_index:
            raise ValueError(
                f"Ligne metrique absente ou dupliquee ({extension}): {key}"
            )
        row_index[key] = row
    expected_keys = {
        (case.case_key, product) for case in cases for product in case.products
    }
    if set(row_index) != expected_keys:
        missing = sorted(expected_keys - set(row_index))
        extra = sorted(set(row_index) - expected_keys)
        raise ValueError(
            f"Matrice de metriques exacte invalide ({extension}): "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    effects: list[PairedEffect] = []
    pair_products: dict[
        str, tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]
    ] = {}
    for case in cases:
        logical_baseline = _baseline_case_key(case.paired_baseline_case_id, case.seed)
        owner_key = baseline_owner_by_logical_key.get(logical_baseline)
        if owner_key is None or owner_key not in evidence:
            raise ValueError(f"Owner de reference absent pour {case.case_key}.")
        stress = evidence[case.case_key]
        baseline = evidence[owner_key]
        stress_products, baseline_products = _validate_evidence_pair(
            case=case,
            stress=stress,
            baseline=baseline,
            expected_products=expected_products,
        )
        pair_products[case.case_key] = (stress_products, baseline_products)
        for product in case.products:
            row = row_index[(case.case_key, product)]
            if (
                str(row.get("extension") or "") != extension
                or str(row.get("case_id") or "") != case.case_id
                or _to_int(row.get("seed")) != case.seed
                or str(row.get("pairing_block_id") or "") != case.pairing_block_id
                or str(row.get("failure_mode") or "") != case.failure_mode
                or _to_int(row.get("stress_start_day")) != case.start_day
                or _to_int(row.get("stress_end_day")) != case.end_day
                or _to_int(row.get("simulation_days")) != case.simulation_days
                or str(row.get("outcome_spec_id") or "") != case.outcome_spec_id
                or _to_int(row.get("outcome_start_day")) != case.outcome_start_day
                or _to_int(row.get("outcome_end_day")) != case.outcome_end_day
                or _to_int(row.get("outcome_day_count")) != case.outcome_day_count
                or str(row.get("outcome_bundle_sha256") or "")
                != case.outcome_bundle_sha256
                or not _as_bool(row.get("pairing_valid"))
            ):
                raise ValueError(
                    f"Identite de ligne metrique invalide: {case.case_key}/{product}"
                )
            if (
                not _same_number(
                    _number(
                        row.get("mechanism_value"),
                        field="mechanism_value",
                        context=case.case_key,
                    ),
                    case.mechanism_value,
                )
                or str(row.get("mechanism_unit") or "") != case.mechanism_unit
            ):
                raise ValueError(
                    f"Mecanisme de ligne metrique invalide: {case.case_key}"
                )
            incident = stress_products[product]
            reference = baseline_products[product]
            product_uom = str(incident.get("uom") or "")
            if (
                str(row.get("product_uom") or "") != product_uom
                or str(row.get("service_unit") or "") != "ratio_and_percentage_points"
                or str(row.get("backlog_unit") or "") != f"{product_uom}_day"
                or str(row.get("production_unit") or "") != product_uom
            ):
                raise ValueError(
                    f"Unite de ligne metrique invalide: {case.case_key}/{product}"
                )
            evidence_fields = {
                "fill_rate": "fill_rate",
                "on_due_ratio": "on_due_ratio",
                "backlog_qty_days": "backlog_qty_days_numerator",
                "backlog_end_qty": "backlog_end_qty",
                "released_qty": "released_qty_numerator",
            }
            for field, evidence_field in evidence_fields.items():
                base_value = _number(
                    reference.get(evidence_field),
                    field=evidence_field,
                    context=f"baseline/{case.case_key}",
                )
                stress_value = _number(
                    incident.get(evidence_field),
                    field=evidence_field,
                    context=f"stress/{case.case_key}",
                )
                csv_base = _number(
                    row.get(f"baseline_{field}"),
                    field=f"baseline_{field}",
                    context=case.case_key,
                )
                csv_stress = _number(
                    row.get(f"stress_{field}"),
                    field=f"stress_{field}",
                    context=case.case_key,
                )
                csv_delta = _number(
                    row.get(f"delta_{field}"),
                    field=f"delta_{field}",
                    context=case.case_key,
                )
                if not (
                    _same_number(csv_base, base_value)
                    and _same_number(csv_stress, stress_value)
                    and _same_number(csv_delta, stress_value - base_value)
                ):
                    raise ValueError(
                        f"Metrique ou delta non recomposable: {case.case_key}/{product}/{field}"
                    )
            service_delta = _number(
                row.get("delta_on_due_ratio"),
                field="delta_on_due_ratio",
                context=case.case_key,
            )
            delta_pp = _number(
                row.get("delta_on_due_percentage_points"),
                field="delta_on_due_percentage_points",
                context=case.case_key,
            )
            if not _same_number(delta_pp, 100.0 * service_delta):
                raise ValueError(
                    f"Conversion points de service invalide: {case.case_key}"
                )
            demand = _number(
                reference.get("demand_qty_denominator"),
                field="demand_qty_denominator",
                context=f"baseline/{case.case_key}/{product}",
            )
            baseline_released = _number(
                reference.get("released_qty_numerator"),
                field="released_qty_numerator",
                context=f"baseline/{case.case_key}/{product}",
            )
            if baseline_released <= 0.0:
                raise ValueError(
                    f"Production reference non positive pour normalisation: {case.case_key}/{product}"
                )
            backlog_normalized = (
                _number(
                    row.get("delta_backlog_qty_days"),
                    field="delta_backlog_qty_days",
                    context=case.case_key,
                )
                / demand
            )
            outcome_end_backlog_normalized = (
                _number(
                    row.get("delta_backlog_end_qty"),
                    field="delta_backlog_end_qty",
                    context=case.case_key,
                )
                / demand
            )
            signed_production_loss = (
                -_number(
                    row.get("delta_released_qty"),
                    field="delta_released_qty",
                    context=case.case_key,
                )
                / baseline_released
            )
            if not _same_number(
                _number(
                    row.get("delta_backlog_days_per_demand_unit"),
                    field="delta_backlog_days_per_demand_unit",
                    context=case.case_key,
                ),
                backlog_normalized,
            ) or not _same_number(
                _number(
                    row.get("signed_production_shortfall_ratio"),
                    field="signed_production_shortfall_ratio",
                    context=case.case_key,
                ),
                signed_production_loss,
            ):
                raise ValueError(f"Normalisation CSV non recomposable: {case.case_key}")
            lane = case.lanes[0]
            effects.append(
                PairedEffect(
                    extension=extension,
                    case_id=case.case_id,
                    case_key=case.case_key,
                    chain_id=lane.chain_id,
                    supplier_id=lane.supplier_id,
                    item_id=lane.item_id,
                    dst_node_id=lane.dst_node_id,
                    product_id=product,
                    selection_slot=case.selection_slot,
                    window_index=case.window_index,
                    failure_mode=case.failure_mode,
                    mathematical_family=case.mathematical_family,
                    mechanism_value=case.mechanism_value,
                    mechanism_unit=case.mechanism_unit,
                    stress_start_day=case.start_day,
                    stress_end_day=case.end_day,
                    simulation_days=case.simulation_days,
                    outcome_spec_id=case.outcome_spec_id,
                    outcome_start_day=case.outcome_start_day,
                    outcome_end_day=case.outcome_end_day,
                    outcome_day_count=case.outcome_day_count,
                    preincident_snapshot_day=case.preincident_snapshot_day,
                    seed=case.seed,
                    demand_qty=demand,
                    baseline_released_qty=baseline_released,
                    service_delta=service_delta,
                    backlog_delta_per_requested_unit=backlog_normalized,
                    outcome_end_backlog_delta_per_requested_unit=(
                        outcome_end_backlog_normalized
                    ),
                    signed_production_loss_ratio=signed_production_loss,
                    client_effect=(
                        service_delta <= -MINIMUM_REPORTABLE_RATIO_GAP
                        or backlog_normalized >= MINIMUM_REPORTABLE_BACKLOG_DAYS_GAP
                    ),
                    production_effect=(
                        signed_production_loss >= MINIMUM_REPORTABLE_RATIO_GAP
                    ),
                )
            )
    return effects, pair_products


def _validate_baseline_compact_flow_contract(
    *,
    cases: Sequence[CaseSpec],
    evidence: Mapping[str, Mapping[str, Any]],
    baseline_owner_by_logical_key: Mapping[str, str],
) -> None:
    expected_by_owner: dict[str, set[tuple[str, str, str, str, int, int]]] = (
        defaultdict(set)
    )
    for case in cases:
        logical = _baseline_case_key(case.paired_baseline_case_id, case.seed)
        owner = baseline_owner_by_logical_key[logical]
        for lane in case.lanes:
            expected_by_owner[owner].add((*lane.flow_key, case.start_day, case.end_day))
    for owner, expected in expected_by_owner.items():
        observed = _flow_metric_index(
            evidence[owner], case_key=owner, compact_baseline=True
        )
        if set(observed) != expected:
            missing = sorted(expected - set(observed))
            extra = sorted(set(observed) - expected)
            raise ValueError(
                f"Flux baseline compacts inexacts pour {owner}: "
                f"missing={missing[:3]}, extra={extra[:3]}"
            )


def _validate_flow_rows(
    *,
    extension: str,
    cases: Sequence[CaseSpec],
    rows: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    baseline_owner_by_logical_key: Mapping[str, str],
) -> dict[str, Any]:
    row_index: dict[tuple[str, str, str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("case_key") or "").strip(),
            str(row.get("chain_id") or "").strip(),
            str(row.get("supplier_id") or "").strip(),
            str(row.get("item_id") or "").strip(),
            str(row.get("dst_node_id") or "").strip(),
        )
        if not all(key) or key in row_index:
            raise ValueError(f"Ligne de flux absente ou dupliquee ({extension}): {key}")
        row_index[key] = row
    expected_keys = {
        (case.case_key, *lane.flow_key) for case in cases for lane in case.lanes
    }
    if set(row_index) != expected_keys:
        missing = sorted(expected_keys - set(row_index))
        extra = sorted(set(row_index) - expected_keys)
        raise ValueError(
            f"Matrice de flux exacte invalide ({extension}): "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    flow_evidence_by_group: dict[tuple[str, str, str, str, str], set[int]] = (
        defaultdict(set)
    )
    flow_exercised_by_group: dict[tuple[str, str, str, str, str], set[int]] = (
        defaultdict(set)
    )
    risk_applied_by_group: dict[tuple[str, str, str, str, str], set[int]] = defaultdict(
        set
    )
    joint_active_exposure_by_group: dict[tuple[str, str, str, str, str], set[int]] = (
        defaultdict(set)
    )
    expected_seed_by_group: dict[tuple[str, str, str, str, str], set[int]] = (
        defaultdict(set)
    )
    expected_lane_groups_by_case_supplier: dict[
        tuple[str, str], set[tuple[str, str, str, str, str]]
    ] = defaultdict(set)
    for case in cases:
        stress_evidence = evidence[case.case_key]
        stress_index = _flow_metric_index(
            stress_evidence, case_key=case.case_key, compact_baseline=False
        )
        expected_stress_keys = {(*lane.flow_key, -1, -1) for lane in case.lanes}
        if set(stress_index) != expected_stress_keys:
            raise ValueError(f"Flux incident exact invalide pour {case.case_key}.")
        logical = _baseline_case_key(case.paired_baseline_case_id, case.seed)
        owner = baseline_owner_by_logical_key[logical]
        baseline_index = _flow_metric_index(
            evidence[owner], case_key=owner, compact_baseline=True
        )
        event_ids_by_lane: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for event in stress_evidence.get("loaded_event_rows") or []:
            if not isinstance(event, dict):
                raise ValueError(f"Evenement risque invalide: {case.case_key}.")
            lane_key = (
                str(event.get("supplier_id") or ""),
                str(event.get("item_id") or ""),
                str(event.get("dst_node_id") or ""),
            )
            event_id = str(event.get("event_id") or "")
            if all(lane_key) and event_id:
                event_ids_by_lane[lane_key].add(event_id)
        applied_event_ids = {
            str(value) for value in stress_evidence.get("applied_event_ids") or []
        }
        for lane in case.lanes:
            csv_row = row_index[(case.case_key, *lane.flow_key)]
            baseline_key = (*lane.flow_key, case.start_day, case.end_day)
            stress_key = (*lane.flow_key, -1, -1)
            if baseline_key not in baseline_index or stress_key not in stress_index:
                raise ValueError(
                    f"Flux apparie absent pour {case.case_key}/{lane.flow_key}."
                )
            reference = baseline_index[baseline_key]
            incident = stress_index[stress_key]
            if (
                str(csv_row.get("extension") or "") != extension
                or str(csv_row.get("case_id") or "") != case.case_id
                or _to_int(csv_row.get("seed")) != case.seed
                or str(csv_row.get("failure_mode") or "") != case.failure_mode
                or _to_int(csv_row.get("stress_start_day")) != case.start_day
                or _to_int(csv_row.get("stress_end_day")) != case.end_day
                or _to_int(csv_row.get("simulation_days")) != case.simulation_days
                or str(csv_row.get("outcome_spec_id") or "") != case.outcome_spec_id
                or str(csv_row.get("outcome_bundle_sha256") or "")
                != case.outcome_bundle_sha256
            ):
                raise ValueError(f"Identite de ligne flux invalide: {case.case_key}")
            reference_uom = str(reference.get("uom") or "")
            incident_uom = str(incident.get("uom") or "")
            if (
                not reference_uom
                or incident_uom != reference_uom
                or str(csv_row.get("uom") or "") != reference_uom
            ):
                raise ValueError(f"Unite de flux non appariee pour {case.case_key}.")
            baseline_pulled = _number(
                reference.get("pulled_qty"),
                field="pulled_qty",
                context=f"baseline/{case.case_key}",
            )
            baseline_shipped = _number(
                reference.get("shipped_qty"),
                field="shipped_qty",
                context=f"baseline/{case.case_key}",
            )
            stress_pulled = _number(
                incident.get("pulled_qty"),
                field="pulled_qty",
                context=f"stress/{case.case_key}",
            )
            stress_shipped = _number(
                incident.get("shipped_qty"),
                field="shipped_qty",
                context=f"stress/{case.case_key}",
            )
            expected_values = {
                "baseline_pulled_qty": baseline_pulled,
                "baseline_shipped_qty": baseline_shipped,
                "stress_pulled_qty": stress_pulled,
                "stress_shipped_qty": stress_shipped,
            }
            for field, expected in expected_values.items():
                observed = _number(
                    csv_row.get(field), field=field, context=case.case_key
                )
                if not _same_number(observed, expected):
                    raise ValueError(
                        f"Flux CSV non recomposable: {case.case_key}/{field}"
                    )
            exercised = baseline_pulled > NUMERICAL_TOLERANCE and baseline_shipped > (
                NUMERICAL_TOLERANCE
            )
            if not _as_bool(csv_row.get("baseline_flow_evidence_available")):
                raise ValueError(f"Preuve flux baseline niee dans {case.case_key}.")
            if _as_bool(csv_row.get("baseline_flow_exercised")) != exercised:
                raise ValueError(f"Indicateur de flux exerce invalide: {case.case_key}")
            if _as_bool(csv_row.get("raw_cross_uom_aggregation_allowed")):
                raise ValueError(f"Agregation inter-unites interdite: {case.case_key}")
            expected_applied = bool(
                event_ids_by_lane.get(
                    (lane.supplier_id, lane.item_id, lane.dst_node_id), set()
                )
                & applied_event_ids
            )
            if (
                _as_bool(csv_row.get("risk_configuration_loaded"))
                != bool(stress_evidence.get("configured_event_ids"))
                or _as_bool(csv_row.get("risk_event_applied_on_lane"))
                != expected_applied
            ):
                raise ValueError(
                    f"Application risque de flux invalide: {case.case_key}"
                )
            coverage_raw = str(csv_row.get("shipped_coverage_ratio") or "").strip()
            if baseline_shipped > NUMERICAL_TOLERANCE:
                expected_coverage = min(
                    1.0, max(0.0, stress_shipped) / baseline_shipped
                )
                coverage = _number(
                    coverage_raw,
                    field="shipped_coverage_ratio",
                    context=case.case_key,
                )
                if not _same_number(coverage, expected_coverage):
                    raise ValueError(f"Couverture expediee invalide: {case.case_key}")
            elif coverage_raw:
                raise ValueError(
                    f"Couverture definie sans flux baseline: {case.case_key}"
                )
            group = (case.case_id, *lane.flow_key)
            expected_seed_by_group[group].add(case.seed)
            expected_lane_groups_by_case_supplier[(case.case_id, lane.supplier_id)].add(
                group
            )
            flow_evidence_by_group[group].add(case.seed)
            if exercised:
                flow_exercised_by_group[group].add(case.seed)
            if expected_applied:
                risk_applied_by_group[group].add(case.seed)
            if exercised and expected_applied:
                joint_active_exposure_by_group[group].add(case.seed)
    gate_rows: list[dict[str, Any]] = []
    for group in sorted(expected_seed_by_group):
        expected_count = len(expected_seed_by_group[group])
        evidence_count = len(flow_evidence_by_group[group])
        exercised_count = len(flow_exercised_by_group[group])
        risk_applied_count = len(risk_applied_by_group[group])
        joint_active_exposure_count = len(joint_active_exposure_by_group[group])
        required = min(MINIMUM_ACTIVE_FLOW_SEED_COUNT, expected_count)
        baseline_active_flow_pass = bool(
            required and evidence_count >= required and exercised_count >= required
        )
        risk_application_exposure_pass = bool(
            required and risk_applied_count >= required
        )
        active_exposure_pass = bool(
            baseline_active_flow_pass
            and risk_application_exposure_pass
            and joint_active_exposure_count >= required
        )
        gate_rows.append(
            {
                "case_id": group[0],
                "supplier_id": group[2],
                "item_id": group[3],
                "dst_node_id": group[4],
                "paired_seed_count": expected_count,
                "expected_paired_seed_count": expected_count,
                "baseline_flow_evidence_seed_count": evidence_count,
                "baseline_flow_exercised_seed_count": exercised_count,
                "distinct_risk_applied_seed_count": risk_applied_count,
                "distinct_joint_active_exposure_seed_count": (
                    joint_active_exposure_count
                ),
                "minimum_required_seed_count": required,
                "baseline_active_flow_pass": baseline_active_flow_pass,
                "risk_application_exposure_pass": (risk_application_exposure_pass),
                "active_exposure_interpretability_pass": active_exposure_pass,
                "pass": active_exposure_pass,
            }
        )
    all_lanes_joint_gate_rows: list[dict[str, Any]] = []
    for key, lane_groups in sorted(expected_lane_groups_by_case_supplier.items()):
        lane_seed_sets = [
            joint_active_exposure_by_group.get(group, set())
            for group in sorted(lane_groups)
        ]
        all_lanes_joint_seed_ids = (
            set.intersection(*lane_seed_sets) if lane_seed_sets else set()
        )
        expected_seed_ids = set().union(
            *(expected_seed_by_group.get(group, set()) for group in lane_groups)
        )
        required = min(MINIMUM_ACTIVE_FLOW_SEED_COUNT, len(expected_seed_ids))
        all_lanes_joint_gate_rows.append(
            {
                "case_id": key[0],
                "supplier_id": key[1],
                "expected_affected_lane_count": len(lane_groups),
                "expected_paired_seed_count": len(expected_seed_ids),
                "distinct_all_lanes_joint_active_exposure_seed_count": len(
                    all_lanes_joint_seed_ids
                ),
                "minimum_required_seed_count": required,
                "pass": bool(required and len(all_lanes_joint_seed_ids) >= required),
            }
        )
    baseline_active_flow_pass = bool(gate_rows) and all(
        row["baseline_active_flow_pass"] for row in gate_rows
    )
    risk_application_exposure_pass = bool(gate_rows) and all(
        row["risk_application_exposure_pass"] for row in gate_rows
    )
    active_exposure_pass = bool(
        gate_rows
        and all(row["active_exposure_interpretability_pass"] for row in gate_rows)
        and all_lanes_joint_gate_rows
        and all(row["pass"] for row in all_lanes_joint_gate_rows)
    )
    return {
        "extension": extension,
        "flow_group_count": len(gate_rows),
        "all_exact_flow_rows_recomputed": True,
        "active_flow_gate_pass": baseline_active_flow_pass,
        "baseline_active_flow_pass": baseline_active_flow_pass,
        "risk_application_exposure_pass": risk_application_exposure_pass,
        "active_exposure_interpretability_pass": active_exposure_pass,
        "active_flow_gate_by_case_lane": gate_rows,
        "all_lanes_joint_active_exposure_gate_by_case_supplier": (
            all_lanes_joint_gate_rows
        ),
        "all_lanes_joint_active_exposure_pass": bool(
            all_lanes_joint_gate_rows
            and all(row["pass"] for row in all_lanes_joint_gate_rows)
        ),
        "active_flow_count_semantics": (
            "distinct paired seeds with physically exercised baseline flow; not probability"
        ),
    }


def _validate_runner_summary(
    *,
    extension: str,
    metric_rows: Sequence[Mapping[str, Any]],
    summary_rows: Sequence[Mapping[str, Any]],
) -> None:
    metric_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in metric_rows:
        metric_groups[
            (
                str(row.get("case_id") or ""),
                str(row.get("product_id") or ""),
            )
        ].append(row)
    summary_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in summary_rows:
        key = (
            str(row.get("case_id") or ""),
            str(row.get("product_id") or ""),
        )
        if not all(key) or key in summary_index:
            raise ValueError(f"Resume absent ou duplique ({extension}): {key}")
        summary_index[key] = row
    if set(summary_index) != set(metric_groups):
        raise ValueError(f"Resume et metriques divergent pour {extension}.")
    for key, group in metric_groups.items():
        summary = summary_index[key]
        seeds = {_to_int(row.get("seed")) for row in group}
        if len(group) != len(seeds) or len(seeds) != EXPECTED_PAIRED_SEED_COUNT:
            raise ValueError(f"Resume sans 30 graines uniques pour {extension}/{key}.")
        if str(summary.get("extension") or "") != extension:
            raise ValueError(f"Extension du resume invalide: {extension}/{key}.")
        if _to_int(summary.get("paired_realization_count")) != len(seeds):
            raise ValueError(f"Compteur de resume invalide: {extension}/{key}.")
        first = group[0]
        identity_fields = (
            "failure_mode",
            "mechanism_unit",
            "stress_start_day",
            "stress_end_day",
            "product_uom",
            "backlog_unit",
            "production_unit",
        )
        for field in identity_fields:
            expected_identity = str(first.get(field) or "")
            if (
                not expected_identity
                or any(str(row.get(field) or "") != expected_identity for row in group)
                or str(summary.get(field) or "") != expected_identity
            ):
                raise ValueError(
                    f"Identite/unite de resume invalide: {extension}/{key}/{field}"
                )
        mechanism_value = _number(
            first.get("mechanism_value"),
            field="mechanism_value",
            context=f"{extension}/{key}",
        )
        if any(
            not _same_number(
                _number(
                    row.get("mechanism_value"),
                    field="mechanism_value",
                    context=f"{extension}/{key}",
                ),
                mechanism_value,
            )
            for row in group
        ) or not _same_number(
            _number(
                summary.get("mechanism_value"),
                field="mechanism_value",
                context=f"summary/{extension}/{key}",
            ),
            mechanism_value,
        ):
            raise ValueError(f"Mecanisme de resume invalide: {extension}/{key}.")
        expected_new = sum(
            str(row.get("case_origin") or "") == "new_run" for row in group
        )
        expected_reused = sum(
            str(row.get("case_origin") or "") == "reused_exact_source_case"
            for row in group
        )
        if (
            expected_new + expected_reused != len(group)
            or _to_int(summary.get("new_run_row_count")) != expected_new
            or _to_int(summary.get("reused_source_row_count")) != expected_reused
        ):
            raise ValueError(
                f"Origine des lignes du resume invalide: {extension}/{key}."
            )
        on_due_values = [
            _number(
                row.get("delta_on_due_percentage_points"),
                field="delta_on_due_percentage_points",
                context=str(key),
            )
            for row in group
        ]
        checks = {
            "on_due_delta_percentage_points_mean": sum(on_due_values) / len(group),
            "on_due_delta_percentage_points_sample_std": statistics.stdev(
                on_due_values
            ),
            "on_due_delta_percentage_points_min": min(on_due_values),
            "on_due_delta_percentage_points_max": max(on_due_values),
            "backlog_delta_qty_days_mean": sum(
                _number(
                    row.get("delta_backlog_qty_days"),
                    field="delta_backlog_qty_days",
                    context=str(key),
                )
                for row in group
            )
            / len(group),
            "released_qty_delta_mean": sum(
                _number(
                    row.get("delta_released_qty"),
                    field="delta_released_qty",
                    context=str(key),
                )
                for row in group
            )
            / len(group),
        }
        for field, expected in checks.items():
            observed = _number(summary.get(field), field=field, context=str(key))
            if not _same_number(observed, expected):
                raise ValueError(f"Resume non recomposable: {extension}/{key}/{field}")
        if _as_bool(summary.get("lower_tail_percentile_reported")):
            raise ValueError(
                f"Percentile de queue interdit avec n=30: {extension}/{key}"
            )
        if _as_bool(summary.get("industrial_probability_estimated")):
            raise ValueError(f"Probabilite industrielle indue: {extension}/{key}")


def _validated_causal_lot_material(
    *,
    cases: Sequence[CaseSpec],
    design_rows: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    baseline_owner_by_logical_key: Mapping[str, str],
    runner_manifest: Mapping[str, Any],
) -> dict[str, CausalLotMaterial]:
    """Rebind reused causal rows to the exact, live, plan-hashed source files.

    Reused source-case evidence deliberately keeps only compact metrics in its
    ledger JSON.  The runner reads retained lot exports through ``run_dir`` when
    it creates its lot tables.  The scientific audit must therefore read and
    hash those same files independently; treating an empty inline ``lot_events``
    array as the source would make the audit either fail spuriously or trust an
    output table it cannot reproduce.
    """

    design_index: dict[tuple[str, int], Mapping[str, Any]] = {}
    for row in design_rows:
        key = (str(row.get("case_id") or "").strip(), _to_int(row.get("seed")))
        if not key[0] or key[1] < 0 or key in design_index:
            raise ValueError(f"Ligne de conception lot absente ou dupliquee: {key}.")
        design_index[key] = row
    expected_design_keys = {(case.case_id, case.seed) for case in cases}
    if set(design_index) != expected_design_keys:
        raise ValueError("La conception lot et ses quatre cas divergent.")

    declared_hashes_raw = runner_manifest.get("causal_source_material_hashes")
    if not isinstance(declared_hashes_raw, dict):
        raise ValueError("Empreintes des materiaux lots source absentes du runner.")
    declared_hashes = {
        str(key): str(value) for key, value in declared_hashes_raw.items()
    }
    recomputed_hashes: dict[str, str] = {}
    result: dict[str, CausalLotMaterial] = {}

    for case in cases:
        row = design_index[(case.case_id, case.seed)]
        stress = evidence.get(case.case_key)
        logical_baseline = _baseline_case_key(case.paired_baseline_case_id, case.seed)
        owner_key = baseline_owner_by_logical_key.get(logical_baseline)
        baseline = evidence.get(owner_key or "")
        if stress is None or baseline is None:
            raise ValueError(
                f"Preuve lot incidente/reference absente: {case.case_key}."
            )

        baseline_events = baseline.get("lot_events")
        baseline_genealogy = baseline.get("lot_genealogy")
        if (
            not isinstance(baseline_events, list)
            or not baseline_events
            or not isinstance(baseline_genealogy, list)
        ):
            raise ValueError(
                f"Exports lots de la reference tracee absents: {case.case_key}."
            )
        if (
            str(row.get("source_baseline_case_key") or "").strip()
            or str(row.get("source_baseline_lot_events_sha256") or "").strip()
            or str(row.get("source_baseline_lot_genealogy_sha256") or "").strip()
        ):
            raise ValueError(
                f"La reference lot V3 doit etre materialisee dans le runner: {case.case_key}."
            )

        source_value = str(row.get("source_incident_case_key") or "").strip()
        source_format = str(row.get("source_incident_evidence_format") or "").strip()
        run_dir_value = str(stress.get("run_dir") or "").strip()
        if (
            not source_value
            or not run_dir_value
            or not _as_bool(stress.get("reused_source_case"))
            or stress.get("lot_events")
            or stress.get("lot_genealogy")
        ):
            raise ValueError(
                f"Provenance du cas lot source reutilise invalide: {case.case_key}."
            )
        source_dir = Path(source_value).resolve()
        if Path(run_dir_value).resolve() != source_dir or not source_dir.is_dir():
            raise ValueError(
                f"Repertoire du cas lot source divergent: {case.case_key}."
            )

        if source_format == "raw_lot_exports":
            file_contract = (
                (
                    "data/production_lot_events.csv",
                    "source_incident_lot_events_sha256",
                ),
                (
                    "data/production_lot_genealogy.csv",
                    "source_incident_lot_genealogy_sha256",
                ),
            )
        elif source_format == "retained_genealogical_proof_exports":
            file_contract = (
                (
                    "proofs/impacted_receipt_lots.csv",
                    "source_incident_impacted_receipts_sha256",
                ),
                (
                    "proofs/impacted_descendant_lots.csv",
                    "source_incident_impacted_descendants_sha256",
                ),
                (
                    "proofs/impacted_genealogy.csv",
                    "source_incident_impacted_genealogy_sha256",
                ),
            )
        else:
            raise ValueError(
                f"Format de materiau lot source inconnu: {case.case_key}/{source_format!r}."
            )

        paths: dict[str, Path] = {}
        for relative, hash_field in file_contract:
            expected_hash = str(row.get(hash_field) or "").strip().lower()
            path = source_dir / Path(relative)
            if (
                not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or not path.is_file()
                or path.is_symlink()
            ):
                raise ValueError(
                    f"Materiau lot source absent/non regulier: {case.case_key}/{relative}."
                )
            actual_hash = _sha256(path)
            if actual_hash != expected_hash:
                raise ValueError(
                    f"Empreinte du materiau lot source invalide: {case.case_key}/{relative}."
                )
            paths[relative] = path
            recomputed_hashes[f"{case.case_id}::{relative}"] = actual_hash

        optional_hash = (
            str(row.get("source_incident_impacted_client_deliveries_sha256") or "")
            .strip()
            .lower()
        )
        optional_relative = "proofs/impacted_client_deliveries.csv"
        optional_path = source_dir / optional_relative
        if source_format == "retained_genealogical_proof_exports":
            if bool(optional_hash) != optional_path.is_file():
                raise ValueError(
                    f"Presence de la preuve client source divergente: {case.case_key}."
                )
            if optional_hash:
                if (
                    not re.fullmatch(r"[0-9a-f]{64}", optional_hash)
                    or optional_path.is_symlink()
                    or _sha256(optional_path) != optional_hash
                ):
                    raise ValueError(
                        f"Empreinte de la preuve client source invalide: {case.case_key}."
                    )
                recomputed_hashes[f"{case.case_id}::{optional_relative}"] = (
                    optional_hash
                )
        elif optional_hash or optional_path.is_file():
            raise ValueError(
                f"Preuve client inattendue pour des exports lots bruts: {case.case_key}."
            )

        if source_format == "raw_lot_exports":
            stress_events = _read_csv(paths["data/production_lot_events.csv"])
            stress_genealogy = _read_csv(paths["data/production_lot_genealogy.csv"])
        else:
            stress_events = [
                {**item, "_proof_role": "direct_exposed_receipt"}
                for item in _read_csv(paths["proofs/impacted_receipt_lots.csv"])
            ]
            stress_events.extend(
                {**item, "_proof_role": "exposed_descendant"}
                for item in _read_csv(paths["proofs/impacted_descendant_lots.csv"])
            )
            stress_genealogy = _read_csv(paths["proofs/impacted_genealogy.csv"])
        if not stress_events:
            raise ValueError(f"Materiau lot source vide: {case.case_key}.")
        result[case.case_key] = CausalLotMaterial(
            baseline_events=[dict(item) for item in baseline_events],
            stress_events=[dict(item) for item in stress_events],
            stress_genealogy=[dict(item) for item in stress_genealogy],
            baseline_evidence_format="runner_case_raw_exports",
        )

    if dict(sorted(recomputed_hashes.items())) != dict(sorted(declared_hashes.items())):
        raise ValueError(
            "Les empreintes runner des materiaux lots source ne sont pas exhaustives."
        )
    return result


def _validate_causal_outputs(
    *,
    cases: Sequence[CaseSpec],
    summary_rows: Sequence[Mapping[str, Any]],
    detail_rows: Sequence[Mapping[str, Any]],
    exposure_rows: Sequence[Mapping[str, Any]],
    exposure_detail_rows: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    baseline_owner_by_logical_key: Mapping[str, str],
    expected_products: set[str],
    lot_material_by_case: Mapping[str, CausalLotMaterial],
) -> dict[str, Any]:
    case_by_key = {case.case_key: case for case in cases}
    summary_index: dict[str, Mapping[str, Any]] = {}
    for row in summary_rows:
        key = str(row.get("case_key") or "").strip()
        if not key or key in summary_index:
            raise ValueError(f"Resume causal absent ou duplique: {key!r}")
        summary_index[key] = row
    exposure_index: dict[str, Mapping[str, Any]] = {}
    for row in exposure_rows:
        key = str(row.get("case_key") or "").strip()
        if not key or key in exposure_index:
            raise ValueError(f"Exposition genealogique absente ou dupliquee: {key!r}")
        exposure_index[key] = row
    if set(summary_index) != set(case_by_key) or set(exposure_index) != set(
        case_by_key
    ):
        raise ValueError("Le groupe lot, ses resumes et ses expositions divergent.")

    exposure_details_by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in exposure_detail_rows:
        case_key = str(row.get("case_key") or "").strip()
        if case_key not in case_by_key:
            raise ValueError(f"Detail d'exposition lot hors plan: {case_key!r}")
        exposure_details_by_case[case_key].append(row)

    details_by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    detail_keys: set[tuple[str, str, str, str, str, str, str]] = set()
    for row in detail_rows:
        case_key = str(row.get("case_key") or "").strip()
        if case_key not in case_by_key:
            raise ValueError(f"Detail causal hors plan: {case_key!r}")
        technical_key = (
            case_key,
            str(row.get("technical_key_type") or "").strip(),
            str(row.get("technical_key_id") or "").strip(),
            str(row.get("node_id") or "").strip(),
            str(row.get("item_id") or "").strip(),
            str(row.get("event_type") or "").strip(),
            str(row.get("uom") or "").strip(),
        )
        if not all(technical_key) or technical_key in detail_keys:
            raise ValueError(
                f"Cle technique causale absente ou dupliquee: {technical_key}"
            )
        detail_keys.add(technical_key)
        planned_case = case_by_key[case_key]
        if (
            str(row.get("case_id") or "") != planned_case.case_id
            or _to_int(row.get("seed")) != planned_case.seed
            or str(row.get("failure_mode") or "") != planned_case.failure_mode
            or not str(row.get("baseline_evidence_format") or "").strip()
        ):
            raise ValueError(f"Identite de detail causal invalide: {technical_key}")
        baseline_day = _to_int(row.get("baseline_day"))
        stress_day = _to_int(row.get("stress_day"))
        day_delta = _to_int(row.get("day_delta"), default=-(10**9))
        baseline_qty = _number(
            row.get("baseline_qty"), field="baseline_qty", context=case_key
        )
        stress_qty = _number(
            row.get("stress_qty"), field="stress_qty", context=case_key
        )
        qty_delta = _number(row.get("qty_delta"), field="qty_delta", context=case_key)
        if baseline_day < 0 or stress_day < 0 or baseline_qty < 0.0 or stress_qty < 0.0:
            raise ValueError(f"Date ou quantite causale invalide: {technical_key}")
        if day_delta != stress_day - baseline_day or not _same_number(
            qty_delta, stress_qty - baseline_qty
        ):
            raise ValueError(f"Difference causale non recomposable: {technical_key}")
        actual = day_delta != 0 or abs(qty_delta) > NUMERICAL_TOLERANCE
        if _as_bool(row.get("actual_difference_measured")) != actual:
            raise ValueError(f"Drapeau de difference causale invalide: {technical_key}")
        if (
            not _as_bool(row.get("pairing_input_sha256_pass"))
            or not _as_bool(row.get("pairing_j0_state_sha256_pass"))
            or _as_bool(row.get("genealogical_exposure_only"))
        ):
            raise ValueError(f"Appariement causal invalide: {technical_key}")
        if (
            str(row.get("causal_scope") or "")
            != "technical_event_heuristic_not_causal_lot_identity"
            or _as_bool(row.get("counterfactual_entity_identity_validated"))
            or str(row.get("pairing_method") or "")
            != (
                "heuristic_global_engine_counter_or_campaign_identifier; may shift "
                "between counterfactual runs"
            )
        ):
            raise ValueError(f"Portee heuristique invalide: {technical_key}")
        details_by_case[case_key].append(row)

    def _risk_tokens(value: Any) -> set[str]:
        return {token.strip() for token in str(value or "").split("|") if token.strip()}

    def _stable_key(row: Mapping[str, Any]) -> tuple[str, ...] | None:
        key_type = ""
        key_id = ""
        for field, label in (
            ("shipment_id", "shipment"),
            ("production_campaign_id", "production_campaign"),
            ("source_id", "source"),
        ):
            value = str(row.get(field) or "").strip()
            if value:
                key_type, key_id = label, value
                break
        uom = str(row.get("uom") or "").strip()
        if not key_id or not uom:
            return None
        return (
            key_type,
            key_id,
            str(row.get("node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("event_type") or row.get("lot_role") or ""),
            uom,
        )

    all_pairing_integrity = True
    all_comparisons_evaluable = True
    difference_by_case: dict[str, bool] = {}
    root_and_genealogy_pass = True
    all_root_gates_pass = True
    all_genealogy_integrity_gates_pass = True
    all_heuristic_comparisons_evaluated = True
    unique_matched_technical_key_count = 0
    coverage_by_case: dict[str, dict[str, int | bool]] = {}
    for case in cases:
        logical = _baseline_case_key(case.paired_baseline_case_id, case.seed)
        owner_key = baseline_owner_by_logical_key.get(logical)
        if owner_key is None:
            raise ValueError(f"Reference causale absente: {case.case_key}")
        _validate_evidence_pair(
            case=case,
            stress=evidence[case.case_key],
            baseline=evidence[owner_key],
            expected_products=expected_products,
        )
        details = details_by_case.get(case.case_key, [])
        summary = summary_index[case.case_key]
        exposure = exposure_index[case.case_key]
        stress_evidence = evidence[case.case_key]
        lot_material = lot_material_by_case.get(case.case_key)
        if lot_material is None:
            raise ValueError(f"Materiau lot valide absent: {case.case_key}.")
        stress_events = lot_material.stress_events
        stress_genealogy = lot_material.stress_genealogy
        baseline_events = lot_material.baseline_events

        lane_receipts = {(lane.item_id, lane.dst_node_id) for lane in case.lanes}
        expected_event_ids = {
            str(value) for value in stress_evidence.get("configured_event_ids") or []
        }
        applied_event_ids = {
            str(value) for value in stress_evidence.get("applied_event_ids") or []
        }
        proof_roots = [
            row
            for row in stress_events
            if isinstance(row, dict)
            and str(row.get("_proof_role") or "") == "direct_exposed_receipt"
            and (str(row.get("item_id") or ""), str(row.get("node_id") or ""))
            in lane_receipts
            and bool(_risk_tokens(row.get("risk_event_ids")) & applied_event_ids)
        ]
        raw_roots = [
            row
            for row in stress_events
            if isinstance(row, dict)
            and str(row.get("event_type") or row.get("source_type") or "")
            == "lane_receipt"
            and (str(row.get("item_id") or ""), str(row.get("node_id") or ""))
            in lane_receipts
            and bool(_risk_tokens(row.get("risk_event_ids")) & applied_event_ids)
        ]
        if proof_roots:
            proof_root_ids = [
                str(row.get("lot_id") or "").strip() for row in proof_roots
            ]
            raw_root_ids = [str(row.get("lot_id") or "").strip() for row in raw_roots]
            if len(proof_root_ids) != len(raw_root_ids) or sorted(
                proof_root_ids
            ) != sorted(raw_root_ids):
                raise ValueError(
                    f"Racines proof et receptions brutes divergent: {case.case_key}"
                )
        roots = proof_roots or raw_roots
        if any(
            not _risk_tokens(row.get("risk_event_ids"))
            or not _risk_tokens(row.get("risk_event_ids")) <= applied_event_ids
            for row in roots
        ):
            raise ValueError(
                f"Racine lot taguee par un evenement hors plan: {case.case_key}"
            )
        root_ids_raw = [str(row.get("lot_id") or "").strip() for row in roots]
        root_ids = set(root_ids_raw) - {""}
        all_event_lot_ids = {
            str(row.get("lot_id") or "")
            for row in stress_events
            if isinstance(row, dict) and str(row.get("lot_id") or "")
        }
        if not root_ids or len(root_ids_raw) != len(root_ids):
            raise ValueError(f"Racines lots absentes ou dupliquees: {case.case_key}")
        children: dict[str, set[str]] = defaultdict(set)
        missing_genealogy_ids: set[str] = set()
        genealogy_edges: set[tuple[str, str]] = set()
        for link in stress_genealogy:
            if not isinstance(link, dict):
                raise ValueError(f"Lien genealogique invalide: {case.case_key}")
            parent = str(link.get("parent_lot_id") or "").strip()
            child = str(link.get("child_lot_id") or "").strip()
            if not parent or not child:
                raise ValueError(f"Lien genealogique incomplet: {case.case_key}")
            edge = (parent, child)
            if edge in genealogy_edges:
                raise ValueError(f"Lien genealogique duplique: {case.case_key}/{edge}")
            genealogy_edges.add(edge)
            children[parent].add(child)
            if parent not in all_event_lot_ids:
                missing_genealogy_ids.add(parent)
            if child not in all_event_lot_ids:
                missing_genealogy_ids.add(child)
        exposed_ids = set(root_ids)
        queue = list(sorted(root_ids))
        while queue:
            parent = queue.pop(0)
            for child in sorted(children.get(parent, set())):
                if child not in exposed_ids:
                    exposed_ids.add(child)
                    queue.append(child)
        visiting: set[str] = set()
        visited: set[str] = set()

        def _has_cycle(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(_has_cycle(child) for child in children.get(node, set())):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        cycle = any(_has_cycle(node) for node in sorted(exposed_ids))
        exposed_rows = [
            row
            for row in stress_events
            if isinstance(row, dict) and str(row.get("lot_id") or "") in exposed_ids
        ]

        expected_chain_ids = "|".join(sorted(lane.chain_id for lane in case.lanes))
        expected_supplier_ids = "|".join(
            sorted({lane.supplier_id for lane in case.lanes})
        )

        def _exposure_detail_key(row: Mapping[str, Any]) -> tuple[str, ...]:
            return (
                str(row.get("lot_id") or "").strip(),
                str(row.get("event_id") or "").strip(),
                str(
                    row.get("event_type")
                    or row.get("source_type")
                    or row.get("lot_role")
                    or ""
                ).strip(),
                str(row.get("node_id") or "").strip(),
                str(row.get("item_id") or "").strip(),
                str(row.get("day") or "").strip(),
                str(row.get("uom") or "").strip(),
                str(row.get("shipment_id") or "").strip(),
                str(row.get("production_campaign_id") or "").strip(),
                str(row.get("source_id") or "").strip(),
            )

        expected_exposure_detail: dict[tuple[str, ...], Mapping[str, Any]] = {}
        for raw in exposed_rows:
            key = _exposure_detail_key(raw)
            if (
                not all((key[0], key[2], key[5], key[6]))
                or key in expected_exposure_detail
            ):
                raise ValueError(
                    f"Cle de detail d'exposition absente ou dupliquee: {case.case_key}/{key}"
                )
            expected_exposure_detail[key] = raw
        observed_exposure_detail: dict[tuple[str, ...], Mapping[str, Any]] = {}
        for row in exposure_details_by_case.get(case.case_key, []):
            key = _exposure_detail_key(row)
            if (
                not all((key[0], key[2], key[5], key[6]))
                or key in observed_exposure_detail
            ):
                raise ValueError(
                    f"Cle publiee de detail lot absente ou dupliquee: {case.case_key}/{key}"
                )
            observed_exposure_detail[key] = row
        if set(observed_exposure_detail) != set(expected_exposure_detail):
            raise ValueError(
                f"Inventaire du detail d'exposition lot non exhaustif: {case.case_key}"
            )
        for key, raw in expected_exposure_detail.items():
            row = observed_exposure_detail[key]
            lot_id = str(raw.get("lot_id") or "").strip()
            expected_role = (
                "risk_tagged_usable_receipt_root"
                if lot_id in root_ids
                else "genealogical_descendant"
            )
            raw_qty = _number(raw.get("qty"), field="qty", context=case.case_key)
            published_qty = _number(row.get("qty"), field="qty", context=case.case_key)
            if (
                str(row.get("extension") or "") != case.extension
                or str(row.get("case_id") or "") != case.case_id
                or _to_int(row.get("seed")) != case.seed
                or str(row.get("failure_mode") or "") != case.failure_mode
                or _to_int(row.get("stress_start_day")) != case.start_day
                or _to_int(row.get("stress_end_day")) != case.end_day
                or str(row.get("chain_ids") or "") != expected_chain_ids
                or str(row.get("supplier_ids") or "") != expected_supplier_ids
                or str(row.get("exposure_role") or "") != expected_role
                or str(row.get("genealogy_depth") or "")
                != str(raw.get("genealogy_depth") or "")
                or not _same_number(published_qty, raw_qty)
                or raw_qty < 0.0
                or str(row.get("risk_event_ids") or "")
                != str(raw.get("risk_event_ids") or "")
                or str(row.get("source_type") or "")
                != str(raw.get("source_type") or "")
                or not _as_bool(row.get("descendant_quantity_is_exposure_upper_bound"))
                or _as_bool(row.get("causal_delay_or_loss_claimed"))
                or _as_bool(row.get("counterfactual_entity_identity_validated"))
                or _as_bool(row.get("industrial_lot_number_claimed"))
                or str(row.get("lot_identifier_semantics") or "")
                != "identifiant_technique_simule_pas_numero_lot_industriel"
            ):
                raise ValueError(
                    f"Detail d'exposition lot non recomposable: {case.case_key}/{key}"
                )
        declared_proof_ids = {
            str(row.get("lot_id") or "")
            for row in stress_events
            if isinstance(row, dict)
            and str(row.get("_proof_role") or "")
            in {"direct_exposed_receipt", "exposed_descendant"}
            and str(row.get("lot_id") or "")
        }
        unreachable_proof_ids = declared_proof_ids - exposed_ids
        genealogy_integrity = bool(
            not missing_genealogy_ids and not unreachable_proof_ids and not cycle
        )
        quantity_by_uom: dict[str, float] = defaultdict(float)
        for row in exposed_rows:
            uom = str(row.get("uom") or "").strip()
            quantity = _number(row.get("qty"), field="qty", context=case.case_key)
            if not uom or quantity < 0.0:
                raise ValueError(
                    f"Unite/quantite d'exposition invalide: {case.case_key}."
                )
            quantity_by_uom[uom] += quantity
        expected_quantity_json = json.dumps(
            dict(sorted(quantity_by_uom.items())),
            ensure_ascii=False,
            sort_keys=True,
        )
        expected_event_text = "|".join(sorted(expected_event_ids))
        applied_event_text = "|".join(sorted(expected_event_ids & applied_event_ids))
        if (
            str(exposure.get("case_id") or "") != case.case_id
            or _to_int(exposure.get("seed")) != case.seed
            or str(exposure.get("failure_mode") or "") != case.failure_mode
            or _to_int(exposure.get("root_lot_count")) != len(root_ids)
            or _to_int(exposure.get("exposed_descendant_lot_count"))
            != len(exposed_ids) - len(root_ids)
            or _to_int(exposure.get("exposed_row_count")) != len(exposed_rows)
            or str(exposure.get("exposed_quantity_upper_bound_by_uom_json") or "")
            != expected_quantity_json
            or not _as_bool(exposure.get("descendant_quantity_is_upper_bound"))
            or _as_bool(exposure.get("causal_delay_or_loss_claimed_from_genealogy"))
            or not _as_bool(exposure.get("root_gate_pass"))
            or _to_int(exposure.get("duplicate_root_lot_id_count")) != 0
            or _as_bool(exposure.get("genealogy_integrity_pass")) != genealogy_integrity
            or _to_int(exposure.get("missing_genealogy_lot_count"))
            != len(missing_genealogy_ids)
            or _to_int(exposure.get("unreachable_declared_proof_lot_count"))
            != len(unreachable_proof_ids)
            or _as_bool(exposure.get("genealogy_cycle_detected")) != cycle
            or _as_bool(exposure.get("published_exposure_is_exact_bfs_closure"))
            != (not unreachable_proof_ids)
            or str(exposure.get("expected_risk_event_ids") or "") != expected_event_text
            or str(exposure.get("applied_expected_risk_event_ids") or "")
            != applied_event_text
            or not _as_bool(
                exposure.get("root_eligibility_requires_effective_risk_application")
            )
        ):
            raise ValueError(
                f"Exposition genealogique non recomposable: {case.case_key}"
            )

        baseline_by_key: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(
            list
        )
        stress_by_key: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(
            list
        )
        for row in baseline_events:
            if isinstance(row, dict):
                key = _stable_key(row)
                if key is not None:
                    baseline_by_key[key].append(row)
        for row in exposed_rows:
            key = _stable_key(row)
            if key is not None:
                stress_by_key[key].append(row)
        baseline_unique = {
            key for key, values in baseline_by_key.items() if len(values) == 1
        }
        stress_unique = {
            key for key, values in stress_by_key.items() if len(values) == 1
        }
        matched = baseline_unique & stress_unique
        ambiguous = {
            key
            for key in set(baseline_by_key) | set(stress_by_key)
            if len(baseline_by_key.get(key, ())) > 1
            or len(stress_by_key.get(key, ())) > 1
        }
        expected_coverage: dict[str, int | bool] = {
            "eligible_baseline_technical_key_count": len(baseline_by_key),
            "eligible_stress_technical_key_count": len(stress_by_key),
            "matched_unique_technical_key_count": len(matched),
            "ambiguous_technical_key_count": len(ambiguous),
            "baseline_only_unique_technical_key_count": len(
                baseline_unique - stress_unique
            ),
            "stress_only_unique_technical_key_count": len(
                stress_unique - baseline_unique
            ),
            "technical_event_heuristic_pairing_integrity_pass": not ambiguous,
            "heuristic_comparison_display_allowed": bool(matched) and not ambiguous,
        }
        coverage_by_case[case.case_key] = expected_coverage
        for field, expected_value in expected_coverage.items():
            observed_value: Any = (
                _as_bool(summary.get(field))
                if isinstance(expected_value, bool)
                else _to_int(summary.get(field))
            )
            if observed_value != expected_value:
                raise ValueError(
                    f"Couverture technique non recomposable: {case.case_key}/{field}"
                )

        expected_details: dict[tuple[str, ...], dict[str, Any]] = {}
        for key in matched:
            reference = baseline_by_key[key][0]
            incident = stress_by_key[key][0]
            baseline_day = _to_int(reference.get("day"))
            stress_day = _to_int(incident.get("day"))
            baseline_qty = _number(
                reference.get("qty"), field="qty", context=case.case_key
            )
            stress_qty = _number(
                incident.get("qty"), field="qty", context=case.case_key
            )
            expected_details[key] = {
                "baseline_day": baseline_day,
                "stress_day": stress_day,
                "day_delta": stress_day - baseline_day,
                "baseline_qty": baseline_qty,
                "stress_qty": stress_qty,
                "qty_delta": stress_qty - baseline_qty,
                "actual_difference_measured": bool(
                    stress_day != baseline_day
                    or abs(stress_qty - baseline_qty) > NUMERICAL_TOLERANCE
                ),
            }
        observed_detail_by_key = {
            (
                str(row.get("technical_key_type") or ""),
                str(row.get("technical_key_id") or ""),
                str(row.get("node_id") or ""),
                str(row.get("item_id") or ""),
                str(row.get("event_type") or ""),
                str(row.get("uom") or ""),
            ): row
            for row in details
        }
        if set(observed_detail_by_key) != set(expected_details):
            raise ValueError(f"Details techniques non exhaustifs: {case.case_key}")
        for key, expected_detail in expected_details.items():
            row = observed_detail_by_key[key]
            if str(row.get("baseline_evidence_format") or "") != (
                lot_material.baseline_evidence_format
            ):
                raise ValueError(
                    f"Format de preuve reference divergent: {case.case_key}."
                )
            for field, expected_value in expected_detail.items():
                observed_value = (
                    _as_bool(row.get(field))
                    if isinstance(expected_value, bool)
                    else (
                        _to_int(row.get(field), -(10**9))
                        if isinstance(expected_value, int)
                        else _number(row.get(field), field=field, context=case.case_key)
                    )
                )
                if isinstance(expected_value, float):
                    if not _same_number(observed_value, expected_value):
                        raise ValueError(
                            f"Detail technique non recomposable: {case.case_key}/{field}"
                        )
                elif observed_value != expected_value:
                    raise ValueError(
                        f"Detail technique non recomposable: {case.case_key}/{field}"
                    )
        actual_count = sum(
            _as_bool(row.get("actual_difference_measured")) for row in details
        )
        if (
            str(summary.get("case_id") or "") != case.case_id
            or _to_int(summary.get("seed")) != case.seed
            or str(summary.get("failure_mode") or "") != case.failure_mode
            or not _as_bool(summary.get("root_gate_pass"))
            or _as_bool(summary.get("genealogy_integrity_pass")) != genealogy_integrity
            or _to_int(summary.get("unique_matched_technical_key_count"))
            != len(details)
            or _to_int(summary.get("actual_difference_row_count")) != actual_count
            or _as_bool(summary.get("heuristic_technical_event_comparison_evaluated"))
            != bool(details)
            or _as_bool(summary.get("paired_counterfactual_evaluated"))
            or not _as_bool(summary.get("genealogical_exposure_is_upper_bound"))
            or _as_bool(summary.get("industrial_lot_number_claimed"))
            or _as_bool(summary.get("counterfactual_entity_identity_validated"))
            or _as_bool(summary.get("causal_lot_attribution_available"))
        ):
            raise ValueError(f"Resume causal non recomposable: {case.case_key}")
        if not _as_bool(exposure.get("descendant_quantity_is_upper_bound")) or _as_bool(
            exposure.get("causal_delay_or_loss_claimed_from_genealogy")
        ):
            raise ValueError(
                f"La genealogie n'est pas bornee correctement: {case.case_key}"
            )
        pair_valid = bool(not ambiguous)
        comparison_evaluable = bool(matched) and not ambiguous
        unique_matched_technical_key_count += len(details)
        all_root_gates_pass = bool(all_root_gates_pass and root_ids)
        all_genealogy_integrity_gates_pass = bool(
            all_genealogy_integrity_gates_pass and genealogy_integrity
        )
        all_heuristic_comparisons_evaluated = bool(
            all_heuristic_comparisons_evaluated and details
        )
        all_pairing_integrity = all_pairing_integrity and pair_valid
        all_comparisons_evaluable = all_comparisons_evaluable and comparison_evaluable
        difference_by_case[case.case_key] = actual_count > 0
        root_and_genealogy_pass = bool(
            root_and_genealogy_pass
            and root_ids
            and not (len(root_ids_raw) != len(root_ids))
            and genealogy_integrity
        )
    return {
        # A correctly executed/recomposed illustration remains technically
        # intact when the heuristic key is ambiguous.  Ambiguity limits the
        # comparison below; it is not evidence that the engine or ledger ran
        # incorrectly.
        "causal_lot_execution_integrity_pass": bool(root_and_genealogy_pass),
        "technical_event_heuristic_pairing_integrity_pass": all_pairing_integrity,
        "heuristic_comparison_evaluable_pass": all_comparisons_evaluable,
        "causal_comparison_evaluable_pass": False,
        "heuristic_comparison_display_allowed": all_comparisons_evaluable,
        "unique_matched_technical_key_count": (unique_matched_technical_key_count),
        "all_root_gates_pass": all_root_gates_pass,
        "all_genealogy_integrity_gates_pass": (all_genealogy_integrity_gates_pass),
        "all_pairs_heuristic_technical_event_comparison_evaluated": (
            all_heuristic_comparisons_evaluated
        ),
        "all_pairs_counterfactually_evaluated": False,
        "any_heuristic_difference_detected": any(difference_by_case.values()),
        "difference_detected_by_case": difference_by_case,
        "technical_pairing_coverage_by_case": coverage_by_case,
        "counterfactual_entity_identity_validated": False,
        "causal_lot_attribution_available": False,
        "all_root_and_genealogy_integrity_gates_pass": root_and_genealogy_pass,
        "genealogical_exposure_is_upper_bound": True,
        "industrial_lot_number_claimed": False,
        "comparison_scope": "heuristically_paired_technical_event_differences",
        "illustration_count": EXPECTED_CAUSAL_CASE_COUNT,
        "paired_seed_count_per_lane": 1,
        "lot_effect_distribution_evaluable": False,
        "network_wide_lot_effect_evaluable": False,
        "multi_lane_common_cause_lot_effect_evaluable": False,
        "four_cause_lot_effect_evaluable": False,
        "temporal_lot_effect_variability_evaluable": False,
        "lot_effect_recurrence_evaluable": False,
        "unmatched_technical_keys_are_not_proof_of_no_effect": True,
        "heuristic_key_ambiguity_does_not_invalidate_execution": True,
        "quality_hold_event_anchor": "shipment_decision_day",
        "opening_or_preexisting_in_transit_receipts_affected": False,
        "native_quarantine_inventory_modeled": False,
        "laboratory_release_process_modeled": False,
        "quality_hold_is_added_usability_delay_not_native_quarantine": True,
    }


def _validate_extension_manifest(
    *,
    path: Path,
    expected_extension: str | None,
    runner_manifest: Mapping[str, Any],
    plan_manifest: Mapping[str, Any],
    source_manifest_sha256: str,
    plan_manifest_sha256: str,
) -> dict[str, Any]:
    payload = _read_json(path)
    if str(payload.get("schema_version") or "") != (
        "etudecas.supplier_network_post_priority_extension_runner.v1"
    ):
        raise ValueError(f"Version de manifeste runner inconnue: {path.name}")
    if (
        str(payload.get("status") or "") != "complete"
        or str(payload.get("mode") or "") != "full"
    ):
        raise ValueError(f"Extension non close en mode full: {path.name}")
    if expected_extension is not None and str(payload.get("extension") or "") != (
        expected_extension
    ):
        raise ValueError(f"Nom d'extension invalide dans {path.name}.")
    if str(payload.get("runner_signature") or "") != str(
        runner_manifest.get("runner_signature") or ""
    ):
        raise ValueError(f"Signature runner incoherente: {path.name}")
    if str(payload.get("plan_signature") or "") != str(
        plan_manifest.get("plan_signature") or ""
    ):
        raise ValueError(f"Signature plan incoherente: {path.name}")
    if str(payload.get("plan_manifest_sha256") or "") != plan_manifest_sha256:
        raise ValueError(f"Empreinte du manifeste plan incoherente: {path.name}")
    if str(payload.get("source_campaign_manifest_sha256") or "") != (
        source_manifest_sha256
    ):
        raise ValueError(f"Lignee campagne incoherente: {path.name}")
    expected_lineage = plan_manifest.get("priority_selection_lineage")
    expected_lineage_digest = str(
        plan_manifest.get("priority_selection_lineage_sha256") or ""
    )
    if (
        payload.get("priority_selection_lineage") != expected_lineage
        or str(payload.get("priority_selection_lineage_sha256") or "")
        != expected_lineage_digest
        or str(payload.get("contract_revision") or "")
        != str(plan_manifest.get("contract_revision") or "")
    ):
        raise ValueError(f"Lignee boundary non propagee exactement: {path.name}")
    if _as_bool(payload.get("industrial_probability_estimated")):
        raise ValueError(f"Probabilite industrielle indue: {path.name}")
    if _as_bool(payload.get("main_ranking_mutated")):
        raise ValueError(f"Classement principal marque comme modifie: {path.name}")
    if payload.get("release_gate_pass") is not False:
        raise ValueError(f"Alias de liberation non neutralise: {path.name}")
    if expected_extension is not None:
        if (
            payload.get("execution_integrity_pass") is not True
            or payload.get("interpretation_robustness_release_pass") is not False
            or payload.get(
                "extension_is_post_selection_characterization_not_confirmation"
            )
            is not True
            or payload.get("extension_seed_blocks_independent_of_priority_selection")
            is not False
            or payload.get("global_priority_robustness_evaluable") is not False
        ):
            raise ValueError(
                f"Gardes d'integrite/interpretation invalides: {path.name}"
            )
    else:
        lot_detail_path = path.with_name("lot_genealogical_exposure_detail.csv")
        if (
            payload.get("causal_lot_execution_integrity_pass") is not True
            or payload.get("counterfactual_entity_identity_validated") is not False
            or payload.get("causal_lot_attribution_available") is not False
            or payload.get("genealogical_exposure_is_upper_bound") is not True
            or payload.get("quality_hold_quarantine_is_reconstructed_not_native")
            is not True
            or payload.get("causal_comparison_evaluable_pass") is not False
            or payload.get("all_pairs_counterfactually_evaluated") is not False
            or str(payload.get("lot_genealogical_exposure_detail_file") or "")
            != lot_detail_path.name
            or _to_int(payload.get("lot_genealogical_exposure_detail_row_count")) <= 0
            or not lot_detail_path.is_file()
            or str(payload.get("lot_genealogical_exposure_detail_sha256") or "")
            != _sha256(lot_detail_path)
            or payload.get("lot_genealogical_exposure_detail_is_bfs_closure")
            is not True
        ):
            raise ValueError(f"Gardes lots invalides: {path.name}")
    return payload


def _validate_retained_preliminary_checkpoint(
    *,
    runner_dir: Path,
    runner_manifest: Mapping[str, Any],
    plan_manifest: Mapping[str, Any],
    plan_manifest_sha256: str,
    seeds: Sequence[int],
    cases: Mapping[str, Sequence[CaseSpec]],
    physical_owner_keys: set[str],
    evidence: Mapping[str, Mapping[str, Any]],
    ledger: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Validate an optional retained 15/30 checkpoint inside a final runner.

    The checkpoint is not a second result package.  It is immutable evidence
    that the first signed seed prefix was reused when the same runner directory
    was completed to 30 seeds.  Its claims remain explicitly preliminary and
    non-promotable.
    """

    path = runner_dir / PRELIMINARY_CHECKPOINT_FILE
    history = runner_manifest.get("checkpoint_history") or []
    declared_name = str(runner_manifest.get("preliminary_checkpoint_manifest") or "")
    declared_hash = str(
        runner_manifest.get("preliminary_checkpoint_manifest_sha256") or ""
    )
    if not path.exists():
        if history or declared_name or declared_hash:
            raise ValueError("Le runner final declare un jalon preliminaire absent.")
        return None
    if not path.is_file() or path.is_symlink():
        raise ValueError("Le jalon preliminaire retenu n'est pas un fichier regulier.")
    if (
        declared_name != PRELIMINARY_CHECKPOINT_FILE
        or declared_hash != _sha256(path)
        or not re.fullmatch(r"[0-9a-f]{64}", declared_hash)
    ):
        raise ValueError("Empreinte du jalon preliminaire retenu invalide.")

    payload = _read_json(path)
    signature = str(payload.get("checkpoint_signature") or "")
    unsigned = dict(payload)
    unsigned.pop("checkpoint_signature", None)
    prefix = list(seeds[:PRELIMINARY_CHECKPOINT_SEED_COUNT])
    expected_extension_counts = {
        "multi_lane_supplier_common_cause": 120,
        "temporal_robustness": 240,
        "priority_four_business_causes": 240,
        "causal_lot_attribution_subset": EXPECTED_CAUSAL_CASE_COUNT,
    }
    exact_false_flags = (
        "full_universe_complete",
        "canonical_results_written",
        "consolidation_written",
        "finalization_eligible",
        "publishable_execution_contract_pass",
        "scoped_descriptive_priority_set_display_allowed",
        "confirmatory_priority_set_release_allowed",
        "global_priority_release_allowed",
        "action_promotion_allowed",
        "promotion_allowed",
    )
    if (
        payload.get("schema_version") != PRELIMINARY_CHECKPOINT_SCHEMA_VERSION
        or payload.get("status") != "paused_preliminary"
        or not signature
        or _canonical_sha256(unsigned) != signature
        or str(payload.get("runner_signature") or "")
        != str(runner_manifest.get("runner_signature") or "")
        or str(payload.get("runner_builder_sha256") or "")
        != EXPECTED_RUNNER_BUILDER_SHA256
        or str(payload.get("planner_builder_sha256") or "")
        != EXPECTED_PLANNER_BUILDER_SHA256
        or str(payload.get("plan_signature") or "")
        != str(plan_manifest.get("plan_signature") or "")
        or str(payload.get("plan_manifest_sha256") or "") != plan_manifest_sha256
        or str(payload.get("priority_selection_lineage_sha256") or "")
        != str(plan_manifest.get("priority_selection_lineage_sha256") or "")
        or str(payload.get("seed_scheduling_policy") or "")
        != "cumulative_signed_seed_prefix_v1"
        or _to_int(payload.get("signed_full_seed_count")) != EXPECTED_PAIRED_SEED_COUNT
        or list(payload.get("signed_full_seed_ids") or []) != list(seeds)
        or _to_int(payload.get("completed_seed_count"))
        != PRELIMINARY_CHECKPOINT_SEED_COUNT
        or list(payload.get("completed_seed_ids") or []) != prefix
        or payload.get("logical_stress_case_count_by_extension")
        != expected_extension_counts
        or _to_int(payload.get("logical_baseline_reference_count")) != 31
        or _to_int(payload.get("physical_baseline_owner_count")) != 30
        or _to_int(payload.get("logical_stress_case_count")) != 604
        or _to_int(payload.get("reused_source_stress_case_count")) != 124
        or _to_int(payload.get("executed_engine_physical_run_count"))
        != PRELIMINARY_CHECKPOINT_ENGINE_RUN_COUNT
        or _to_int(payload.get("full_expected_engine_physical_run_count")) != 1020
        or _to_int(payload.get("remaining_engine_physical_run_count")) != 510
        or _to_int(payload.get("ledger_evidence_case_count"))
        != PRELIMINARY_CHECKPOINT_EVIDENCE_COUNT
        or payload.get("all_target_seed_jobs_complete") is not True
        or payload.get("no_future_seed_job_active") is not True
        or payload.get("preliminary_not_final") is not True
        or any(payload.get(field) is not False for field in exact_false_flags)
        or str(payload.get("checkpoint_signature_semantics") or "")
        != "internal_integrity_digest_not_authenticated_signature"
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(payload.get("execution_ledger_sha256_at_checkpoint") or ""),
        )
    ):
        raise ValueError("Contrat exact du jalon preliminaire 15/30 invalide.")

    if not isinstance(history, list) or len(history) != 1:
        raise ValueError("Historique du jalon preliminaire final invalide.")
    record = history[0]
    if not isinstance(record, dict) or (
        _to_int(record.get("completed_seed_count")) != PRELIMINARY_CHECKPOINT_SEED_COUNT
        or list(record.get("completed_seed_ids") or []) != prefix
        or str(record.get("checkpoint_manifest") or "") != PRELIMINARY_CHECKPOINT_FILE
        or str(record.get("checkpoint_signature") or "") != signature
        or str(record.get("checkpoint_at_utc") or "")
        != str(payload.get("checkpoint_at_utc") or "")
    ):
        raise ValueError("L'historique final ne correspond pas au jalon 15/30.")

    expected_stress_keys = {
        case.case_key
        for extension, extension_cases in cases.items()
        for case in extension_cases
        if (extension == "causal_lot_attribution_subset" or case.seed in set(prefix))
    }
    expected_owner_keys = {
        key
        for key in physical_owner_keys
        if _to_int((evidence.get(key) or {}).get("seed")) in set(prefix)
    }
    expected_keys = expected_stress_keys | expected_owner_keys
    if (
        len(expected_stress_keys) != 604
        or len(expected_owner_keys) != 30
        or len(expected_keys) != PRELIMINARY_CHECKPOINT_EVIDENCE_COUNT
    ):
        raise ValueError("Univers de preuves attendu au jalon 15/30 incoherent.")

    checkpoint_files = payload.get("case_evidence_file_sha256")
    ledger_files = ledger.get("case_files")
    ledger_hashes = ledger.get("case_file_sha256")
    if (
        not isinstance(checkpoint_files, dict)
        or set(checkpoint_files) != expected_keys
        or not isinstance(ledger_files, dict)
        or not isinstance(ledger_hashes, dict)
    ):
        raise ValueError("Inventaire des preuves retenues au jalon 15/30 invalide.")
    observed_paths: set[str] = set()
    for case_key in sorted(expected_keys):
        item = checkpoint_files.get(case_key)
        if not isinstance(item, dict):
            raise ValueError(f"Preuve de jalon invalide: {case_key}.")
        digest = hashlib.sha256(case_key.encode("utf-8")).hexdigest()[:20]
        expected_relative = (Path("ledger_cases") / f"{digest}.json").as_posix()
        relative = Path(str(item.get("relative_path") or "")).as_posix()
        expected_hash = str(item.get("sha256") or "")
        if (
            relative != expected_relative
            or relative in observed_paths
            or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            or str(ledger_files.get(case_key) or "") != expected_relative
            or str(ledger_hashes.get(case_key) or "") != expected_hash
        ):
            raise ValueError(
                f"Preuve du jalon non reutilisee a l'identique: {case_key}."
            )
        observed_paths.add(relative)
    return payload


def load_closed_runner(runner_dir: str | Path) -> LoadedRunner:
    """Load and independently validate one closed compact runner package."""

    root = Path(runner_dir).resolve()
    root_entries = list(root.iterdir())
    observed_root_files = {path.name for path in root_entries if path.is_file()}
    retained_checkpoint = PRELIMINARY_CHECKPOINT_FILE in observed_root_files
    expected_root_files = set(RUNNER_FILES)
    if retained_checkpoint:
        expected_root_files.add(PRELIMINARY_CHECKPOINT_FILE)
    if observed_root_files != expected_root_files or any(
        path.is_symlink() for path in root_entries
    ):
        missing_runner = sorted(expected_root_files - observed_root_files)
        extra_runner = sorted(observed_root_files - expected_root_files)
        raise ValueError(
            "Inventaire racine du runner incomplet ou excessif: "
            f"missing={missing_runner[:3]}, extra={extra_runner[:3]}"
        )
    runner_manifest_path = root / "post_priority_extension_runner_manifest.json"
    runner_manifest = _read_json(runner_manifest_path)
    if str(runner_manifest.get("schema_version") or "") != (
        "etudecas.supplier_network_post_priority_extension_runner.v1"
    ):
        raise ValueError("Version du runner inconnue.")
    if (
        str(runner_manifest.get("status") or "") != "complete"
        or str(runner_manifest.get("mode") or "") != "full"
    ):
        raise ValueError("Le runner doit etre clos en mode full.")
    if str(runner_manifest.get("retention") or "") != "summary":
        raise ValueError("Le paquet compact doit avoir la retention summary.")
    if (
        runner_manifest.get("custom_executor_used") is not False
        or str(runner_manifest.get("executor_contract") or "")
        != "builtin_execute_engine_case"
        or str(runner_manifest.get("scenario_id") or "") != "scn:BASE"
        or runner_manifest.get("publishable_execution_contract_pass") is not True
    ):
        raise ValueError(
            "Le runner full n'a pas utilise l'executeur publiable verrouille."
        )
    if (
        runner_manifest.get("promotion_allowed") is not False
        or runner_manifest.get("confirmatory_priority_set_release_allowed") is not False
        or runner_manifest.get("global_priority_release_allowed") is not False
        or runner_manifest.get("action_promotion_allowed") is not False
    ):
        raise ValueError("Le runner revendique une liberation scientifique indue.")
    if (
        _as_bool(runner_manifest.get("source_artifact_mutated"))
        or _as_bool(runner_manifest.get("plan_artifact_mutated"))
        or _as_bool(runner_manifest.get("main_ranking_mutated"))
    ):
        raise ValueError("Le runner revendique une mutation d'un artefact amont.")
    plan_dir = Path(str(runner_manifest.get("plan_dir") or "")).resolve()
    if not plan_dir.is_dir():
        raise FileNotFoundError(f"Plan signe du runner absent: {plan_dir}")
    plan_manifest = _validate_plan_manifest(plan_dir)
    plan_manifest_sha256 = _sha256(
        plan_dir / "post_priority_extensions_plan_manifest.json"
    )
    if str(runner_manifest.get("plan_signature") or "") != str(
        plan_manifest.get("plan_signature") or ""
    ):
        raise ValueError("Le runner et le plan ont des signatures differentes.")
    if (
        runner_manifest.get("priority_selection_lineage")
        != plan_manifest.get("priority_selection_lineage")
        or str(runner_manifest.get("priority_selection_lineage_sha256") or "")
        != str(plan_manifest.get("priority_selection_lineage_sha256") or "")
        or str(runner_manifest.get("contract_revision") or "")
        != str(plan_manifest.get("contract_revision") or "")
        or str(runner_manifest.get("plan_manifest_sha256") or "")
        != plan_manifest_sha256
    ):
        raise ValueError("Le runner ne propage pas exactement la lignee boundary.")
    source_manifest_sha256 = str(
        runner_manifest.get("source_campaign_manifest_sha256") or ""
    )
    if len(source_manifest_sha256) != 64:
        raise ValueError("Empreinte du manifeste campagne source absente du runner.")
    lineage = plan_manifest.get("priority_selection_lineage") or {}
    if source_manifest_sha256 != str(
        lineage.get("source_campaign_manifest_sha256") or ""
    ):
        raise ValueError("La campagne source du runner diverge de la lignee boundary.")

    runner_paths = {
        name: root / name
        for name in (
            *RUNNER_FILES,
            *((PRELIMINARY_CHECKPOINT_FILE,) if retained_checkpoint else ()),
        )
    }
    plan_paths = {name: plan_dir / name for name in PLAN_FILES}
    source_hashes = {
        **{
            f"runner/{name}": _sha256(path)
            for name, path in sorted(runner_paths.items())
        },
        **{f"plan/{name}": _sha256(path) for name, path in sorted(plan_paths.items())},
    }
    ledger_path = root / "execution_ledger.json"
    if str(runner_manifest.get("execution_ledger_sha256") or "") != _sha256(
        ledger_path
    ):
        raise ValueError("Empreinte du registre d'execution invalide.")

    baseline_rows = _read_csv(plan_dir / "paired_baseline_design.csv")
    designs = {
        "multi_lane_supplier_common_cause": _read_csv(
            plan_dir / "multi_lane_supplier_common_cause_design.csv"
        ),
        "temporal_robustness": _read_csv(plan_dir / "temporal_robustness_design.csv"),
        "priority_four_business_causes": _read_csv(
            plan_dir / "priority_four_business_causes_design.csv"
        ),
        "causal_lot_attribution_subset": _read_csv(
            plan_dir / "causal_lot_attribution_design.csv"
        ),
    }
    seeds, cases, baseline_by_id, expected_first_owner = _validate_design_matrices(
        plan_manifest=plan_manifest,
        baseline_rows=baseline_rows,
        design_rows=designs,
    )
    all_products = {
        product
        for group in cases.values()
        for case in group
        for product in case.products
    }
    if all_products != set(EXPECTED_TARGET_PRODUCTS):
        raise ValueError(
            f"Produits cibles inattendus: attendu={sorted(EXPECTED_TARGET_PRODUCTS)}, "
            f"obtenu={sorted(all_products)}"
        )
    expected_stress_count = sum(len(group) for group in cases.values())
    if expected_stress_count != (
        EXPECTED_COMMON_CAUSE_CASE_COUNT
        + EXPECTED_TEMPORAL_CASE_COUNT
        + EXPECTED_FOUR_CAUSE_CASE_COUNT
        + EXPECTED_CAUSAL_CASE_COUNT
    ):
        raise ValueError("Nombre total de comparaisons de stress invalide.")
    if _to_int(
        runner_manifest.get("selected_stress_case_count")
    ) != expected_stress_count or _to_int(
        runner_manifest.get("selected_baseline_case_count")
    ) != len(baseline_by_id):
        raise ValueError("Compteurs de selection du runner invalides.")

    materialization = runner_manifest.get("baseline_materialization") or {}
    owner_map = {
        str(key): str(value)
        for key, value in (
            materialization.get("logical_case_to_physical_owner") or {}
        ).items()
    }
    expected_owner_map = {
        str(row["_logical_case_key"]): expected_first_owner[
            (
                int(row["_seed"]),
                int(row["_simulation_days"]),
                bool(row["_trace"]),
                str(row["_outcome_bundle_sha256"]),
            )
        ]
        for row in baseline_by_id.values()
    }
    if owner_map != expected_owner_map:
        raise ValueError("Resolution logical_case_to_physical_owner invalide.")
    physical_owner_key_list = [
        str(value) for value in materialization.get("physical_owner_case_keys") or []
    ]
    physical_owner_keys = set(physical_owner_key_list)
    if (
        not physical_owner_key_list
        or len(physical_owner_key_list) != len(physical_owner_keys)
        or "" in physical_owner_keys
    ):
        raise ValueError("Liste des references physiques vide ou dupliquee.")
    if physical_owner_keys != set(expected_owner_map.values()):
        raise ValueError("Jeu des references physiques materialisees invalide.")
    if str(materialization.get("policy") or "") != (
        "one_runner_generated_baseline_per_seed_horizon_trace_engine_input_and_"
        "outcome_bundle_with_compact_exact_window_flows_v2"
    ):
        raise ValueError("Politique de materialisation des references inconnue.")

    runner_script_sha = str(runner_manifest.get("runner_script_sha256") or "")
    planner_script_sha = str(runner_manifest.get("planner_script_sha256") or "")
    runner_builder_path = (
        Path(__file__)
        .resolve()
        .with_name("supplier_network_post_priority_extension_runner.py")
    )
    if (
        runner_script_sha != EXPECTED_RUNNER_BUILDER_SHA256
        or planner_script_sha != EXPECTED_PLANNER_BUILDER_SHA256
        or not runner_builder_path.is_file()
        or _sha256(runner_builder_path) != EXPECTED_RUNNER_BUILDER_SHA256
        or _sha256(Path(planner.__file__).resolve()) != EXPECTED_PLANNER_BUILDER_SHA256
        or planner_script_sha != str(plan_manifest.get("planner_builder_sha256") or "")
    ):
        raise ValueError("Empreintes planner/runner invalides ou divergentes.")
    baseline_case_keys = [
        _baseline_case_key(
            str(row.get("baseline_case_id") or ""), _to_int(row.get("seed"))
        )
        for row in baseline_rows
    ]
    stress_case_sequence = [
        case
        for extension in (
            "multi_lane_supplier_common_cause",
            "temporal_robustness",
            "priority_four_business_causes",
            "causal_lot_attribution_subset",
        )
        for case in cases[extension]
    ]
    case_simulation_days = {
        **{
            _baseline_case_key(
                str(row.get("baseline_case_id") or ""), _to_int(row.get("seed"))
            ): _to_int(row.get("simulation_days"))
            for row in baseline_rows
        },
        **{case.case_key: case.simulation_days for case in stress_case_sequence},
    }
    case_outcome_bundles = {
        **{
            _baseline_case_key(
                str(row.get("baseline_case_id") or ""), _to_int(row.get("seed"))
            ): str(row.get("outcome_bundle_sha256") or "")
            for row in baseline_rows
        },
        **{case.case_key: case.outcome_bundle_sha256 for case in stress_case_sequence},
    }
    runner_signature_payload = {
        "schema_version": "etudecas.supplier_network_post_priority_extension_runner.v1",
        "runner_script_sha256": runner_script_sha,
        "planner_script_sha256": planner_script_sha,
        "plan_signature": str(plan_manifest.get("plan_signature") or ""),
        "plan_manifest_sha256": plan_manifest_sha256,
        "mode": "full",
        "scenario_id": str(runner_manifest.get("scenario_id") or ""),
        "days": 720,
        "retention": "summary",
        "executor_contract": "builtin_execute_engine_case",
        "custom_executor_used": False,
        "seed_scheduling_policy": "cumulative_signed_seed_prefix_v1",
        "signed_full_seed_ids": list(seeds),
        "priority_selection_lineage": plan_manifest.get("priority_selection_lineage"),
        "priority_selection_lineage_sha256": plan_manifest.get(
            "priority_selection_lineage_sha256"
        ),
        "case_simulation_days": case_simulation_days,
        "case_outcome_bundle_sha256": case_outcome_bundles,
        "selected_baseline_case_keys": baseline_case_keys,
        "selected_stress_case_keys": [case.case_key for case in stress_case_sequence],
        "baseline_materialization": materialization,
        "causal_source_material_hashes": dict(
            runner_manifest.get("causal_source_material_hashes") or {}
        ),
        "execution_configuration_lock": plan_manifest.get(
            "execution_configuration_lock"
        ),
    }
    if str(runner_manifest.get("runner_signature") or "") != _canonical_sha256(
        runner_signature_payload
    ):
        raise ValueError("Signature canonique du runner non recomposable.")

    expected_stress_keys = {case.case_key for group in cases.values() for case in group}
    ledger = _read_json(ledger_path)
    evidence, registry_hash = _load_ledger_evidence(
        runner_dir=root,
        runner_manifest=runner_manifest,
        ledger=ledger,
        expected_stress_case_keys=expected_stress_keys,
        expected_owner_keys=physical_owner_keys,
    )
    preliminary_checkpoint = _validate_retained_preliminary_checkpoint(
        runner_dir=root,
        runner_manifest=runner_manifest,
        plan_manifest=plan_manifest,
        plan_manifest_sha256=plan_manifest_sha256,
        seeds=seeds,
        cases=cases,
        physical_owner_keys=physical_owner_keys,
        evidence=evidence,
        ledger=ledger,
    )
    locked_graph_sha256 = str(
        (plan_manifest.get("execution_configuration_lock") or {}).get("graph_sha256")
        or ""
    )
    if any(
        str(payload.get("input_sha256") or "") != locked_graph_sha256
        for payload in evidence.values()
    ):
        raise ValueError(
            "Une preuve runner n'utilise pas le graphe verrouille du plan."
        )
    if _to_int(runner_manifest.get("ledger_case_count")) != len(evidence):
        raise ValueError("Compteur de preuves du runner invalide.")
    if _to_int(runner_manifest.get("ledger_case_file_sha256_count")) != len(evidence):
        raise ValueError("Compteur d'empreintes de preuves du runner invalide.")

    reference_rows = _read_csv(root / "execution_case_reference.csv")
    reference_keys = [str(row.get("case_key") or "") for row in reference_rows]
    expected_reference_keys = expected_stress_keys | set(expected_owner_map)
    if len(reference_keys) != len(set(reference_keys)) or set(reference_keys) != (
        expected_reference_keys
    ):
        raise ValueError("Registre de cas logiques incomplet, excessif ou duplique.")
    if any(_as_bool(row.get("main_ranking_mutated")) for row in reference_rows):
        raise ValueError(
            "Un cas runner revendique une mutation du classement principal."
        )
    case_by_key = {case.case_key: case for group in cases.values() for case in group}
    baseline_by_logical_key = {
        str(row["_logical_case_key"]): row for row in baseline_by_id.values()
    }
    for row in reference_rows:
        key = str(row.get("case_key") or "")
        if key in case_by_key:
            case = case_by_key[key]
            if (
                str(row.get("extension") or "") != case.extension
                or str(row.get("case_id") or "") != case.case_id
                or _to_int(row.get("seed")) != case.seed
                or str(row.get("pairing_block_id") or "") != case.pairing_block_id
                or str(row.get("paired_baseline_case_id") or "")
                != case.paired_baseline_case_id
                or _as_bool(row.get("lot_trace_required")) != case.lot_trace_required
                or _to_int(row.get("simulation_days")) != case.simulation_days
                or str(row.get("outcome_spec_id") or "") != case.outcome_spec_id
                or _to_int(row.get("outcome_start_day")) != case.outcome_start_day
                or _to_int(row.get("outcome_end_day")) != case.outcome_end_day
                or _to_int(row.get("outcome_day_count")) != case.outcome_day_count
                or str(row.get("outcome_bundle_sha256") or "")
                != case.outcome_bundle_sha256
            ):
                raise ValueError(f"Reference de cas runner invalide: {key}.")
        else:
            baseline = baseline_by_logical_key.get(key)
            if baseline is None:
                raise ValueError(f"Reference baseline runner inconnue: {key}.")
            expected_signed_action = (
                "new_run_required"
                if _to_int(baseline.get("new_run_count")) == 1
                else "reuse_exact_source_case"
            )
            expected_runtime_action = (
                "materialize_runner_baseline"
                if owner_map[key] == key
                else "reuse_runner_materialized_baseline"
            )
            simulation_days = int(baseline["_simulation_days"])
            if (
                str(row.get("extension") or "") != "baseline"
                or str(row.get("case_id") or "")
                != str(baseline.get("baseline_case_id") or "")
                or _to_int(row.get("seed")) != int(baseline["_seed"])
                or str(row.get("pairing_block_id") or "")
                != str(baseline.get("pairing_block_id") or "")
                or str(row.get("paired_baseline_case_id") or "")
                or str(row.get("signed_plan_action") or "") != expected_signed_action
                or str(row.get("action") or "") != expected_runtime_action
                or str(row.get("physical_baseline_owner_case_key") or "")
                != owner_map[key]
                or str(row.get("source_case_key") or "")
                != str(baseline.get("source_case_key") or "")
                or _as_bool(row.get("lot_trace_required")) != bool(baseline["_trace"])
                or _to_int(row.get("simulation_days")) != simulation_days
                or str(row.get("outcome_spec_id") or "") != "baseline_outcome_bundle"
                or (
                    _to_int(row.get("outcome_start_day")),
                    _to_int(row.get("outcome_end_day")),
                )
                != (0, simulation_days - 1)
                or _to_int(row.get("outcome_day_count")) != simulation_days
                or str(row.get("outcome_bundle_sha256") or "")
                != str(baseline["_outcome_bundle_sha256"])
                or _to_int(row.get("preincident_snapshot_day")) != -1
                or (
                    _to_int(row.get("stress_start_day")),
                    _to_int(row.get("stress_end_day")),
                )
                != (0, 0)
                or str(row.get("failure_mode") or "") != "baseline"
            ):
                raise ValueError(f"Reference baseline runner invalide: {key}.")

    extension_manifests = {
        "multi_lane_supplier_common_cause": _validate_extension_manifest(
            path=root / "multi_lane_supplier_common_cause_manifest.json",
            expected_extension="multi_lane_supplier_common_cause",
            runner_manifest=runner_manifest,
            plan_manifest=plan_manifest,
            source_manifest_sha256=source_manifest_sha256,
            plan_manifest_sha256=plan_manifest_sha256,
        ),
        "temporal_robustness": _validate_extension_manifest(
            path=root / "temporal_robustness_manifest.json",
            expected_extension="temporal_robustness",
            runner_manifest=runner_manifest,
            plan_manifest=plan_manifest,
            source_manifest_sha256=source_manifest_sha256,
            plan_manifest_sha256=plan_manifest_sha256,
        ),
        "priority_four_business_causes": _validate_extension_manifest(
            path=root / "priority_four_business_causes_manifest.json",
            expected_extension="priority_four_business_causes",
            runner_manifest=runner_manifest,
            plan_manifest=plan_manifest,
            source_manifest_sha256=source_manifest_sha256,
            plan_manifest_sha256=plan_manifest_sha256,
        ),
        "causal_lot_attribution_subset": _validate_extension_manifest(
            path=root / "causal_lot_attribution_manifest.json",
            expected_extension=None,
            runner_manifest=runner_manifest,
            plan_manifest=plan_manifest,
            source_manifest_sha256=source_manifest_sha256,
            plan_manifest_sha256=plan_manifest_sha256,
        ),
    }
    expected_counts = {
        "multi_lane_supplier_common_cause": EXPECTED_COMMON_CAUSE_CASE_COUNT,
        "temporal_robustness": EXPECTED_TEMPORAL_CASE_COUNT,
        "priority_four_business_causes": EXPECTED_FOUR_CAUSE_CASE_COUNT,
    }
    for extension, expected_count in expected_counts.items():
        manifest = extension_manifests[extension]
        if (
            _to_int(manifest.get("logical_case_count")) != expected_count
            or _to_int(manifest.get("executed_or_reused_case_count")) != expected_count
        ):
            raise ValueError(f"Compteurs d'extension invalides: {extension}")
    causal_manifest = extension_manifests["causal_lot_attribution_subset"]
    if (
        _to_int(causal_manifest.get("logical_pair_count")) != EXPECTED_CAUSAL_CASE_COUNT
        or _to_int(causal_manifest.get("evaluated_pair_count"))
        != EXPECTED_CAUSAL_CASE_COUNT
        or not _as_bool(causal_manifest.get("genealogical_exposure_is_upper_bound"))
    ):
        raise ValueError("Compteurs ou semantique du manifeste causal invalides.")

    metrics = {
        "multi_lane_supplier_common_cause": _read_csv(
            root / "multi_lane_supplier_common_cause_metrics.csv"
        ),
        "temporal_robustness": _read_csv(root / "temporal_robustness_metrics.csv"),
        "priority_four_business_causes": _read_csv(
            root / "priority_four_business_causes_metrics.csv"
        ),
    }
    flows = {
        "multi_lane_supplier_common_cause": _read_csv(
            root / "multi_lane_supplier_common_cause_flow_metrics.csv"
        ),
        "temporal_robustness": _read_csv(root / "temporal_robustness_flow_metrics.csv"),
        "priority_four_business_causes": _read_csv(
            root / "priority_four_business_causes_flow_metrics.csv"
        ),
    }
    summaries = {
        "multi_lane_supplier_common_cause": _read_csv(
            root / "multi_lane_supplier_common_cause_summary.csv"
        ),
        "temporal_robustness": _read_csv(root / "temporal_robustness_summary.csv"),
        "priority_four_business_causes": _read_csv(
            root / "priority_four_business_causes_summary.csv"
        ),
    }
    causal_lot_material_by_case = _validated_causal_lot_material(
        cases=cases["causal_lot_attribution_subset"],
        design_rows=designs["causal_lot_attribution_subset"],
        evidence=evidence,
        baseline_owner_by_logical_key=owner_map,
        runner_manifest=runner_manifest,
    )
    return LoadedRunner(
        runner_dir=root,
        plan_dir=plan_dir,
        runner_manifest=runner_manifest,
        plan_manifest=plan_manifest,
        seeds=seeds,
        designs={"paired_baseline": baseline_rows, **designs},
        cases=cases,
        metrics=metrics,
        flows=flows,
        summaries=summaries,
        extension_manifests=extension_manifests,
        evidence=evidence,
        baseline_owner_by_logical_key=owner_map,
        source_file_sha256=source_hashes,
        ledger_case_registry_sha256=registry_hash,
        preliminary_checkpoint=preliminary_checkpoint,
        causal_lot_material_by_case=causal_lot_material_by_case,
    )


def analyze_closed_runner(
    loaded: LoadedRunner,
    *,
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    if resamples != BOOTSTRAP_RESAMPLE_COUNT:
        raise ValueError("Le paquet publiable exige exactement 10 000 bootstrap.")
    all_cases = [case for group in loaded.cases.values() for case in group]
    _validate_baseline_compact_flow_contract(
        cases=all_cases,
        evidence=loaded.evidence,
        baseline_owner_by_logical_key=loaded.baseline_owner_by_logical_key,
    )

    effects_by_extension: dict[str, list[PairedEffect]] = {}
    flow_controls: dict[str, dict[str, Any]] = {}
    for extension in (
        "multi_lane_supplier_common_cause",
        "temporal_robustness",
        "priority_four_business_causes",
    ):
        effects, _paired_products = _validate_metric_rows(
            extension=extension,
            cases=loaded.cases[extension],
            rows=loaded.metrics[extension],
            evidence=loaded.evidence,
            baseline_owner_by_logical_key=loaded.baseline_owner_by_logical_key,
            expected_products=set(EXPECTED_TARGET_PRODUCTS),
        )
        effects_by_extension[extension] = effects
        flow_controls[extension] = _validate_flow_rows(
            extension=extension,
            cases=loaded.cases[extension],
            rows=loaded.flows[extension],
            evidence=loaded.evidence,
            baseline_owner_by_logical_key=loaded.baseline_owner_by_logical_key,
        )
        _validate_runner_summary(
            extension=extension,
            metric_rows=loaded.metrics[extension],
            summary_rows=loaded.summaries[extension],
        )

    causal = _validate_causal_outputs(
        cases=loaded.cases["causal_lot_attribution_subset"],
        summary_rows=_read_csv(
            loaded.runner_dir / "causal_lot_attribution_summary.csv"
        ),
        detail_rows=_read_csv(loaded.runner_dir / "causal_lot_attribution_detail.csv"),
        exposure_rows=_read_csv(
            loaded.runner_dir / "lot_genealogical_exposure_summary.csv"
        ),
        exposure_detail_rows=_read_csv(
            loaded.runner_dir / "lot_genealogical_exposure_detail.csv"
        ),
        evidence=loaded.evidence,
        baseline_owner_by_logical_key=loaded.baseline_owner_by_logical_key,
        expected_products=set(EXPECTED_TARGET_PRODUCTS),
        lot_material_by_case=loaded.causal_lot_material_by_case,
    )

    temporal_effect_rows, temporal_pair_rows, temporal_interpretation = (
        analyze_selected_lane_effects(
            effects_by_extension["temporal_robustness"],
            kind="temporal",
            expected_seeds=loaded.seeds,
            resamples=resamples,
        )
    )
    four_effect_rows, four_pair_rows, four_interpretation = (
        analyze_selected_lane_effects(
            effects_by_extension["priority_four_business_causes"],
            kind="four_cause",
            expected_seeds=loaded.seeds,
            resamples=resamples,
        )
    )
    common_effect_rows, common_interpretation = analyze_common_cause_effects(
        effects_by_extension["multi_lane_supplier_common_cause"],
        cases=loaded.cases["multi_lane_supplier_common_cause"],
        expected_seeds=loaded.seeds,
        resamples=resamples,
    )

    def _single_lane_gate(
        extension: str,
        *,
        case_id: Any,
        supplier_id: Any,
        item_id: Any,
        dst_node_id: Any,
    ) -> Mapping[str, Any]:
        matches = [
            row
            for row in flow_controls[extension]["active_flow_gate_by_case_lane"]
            if str(row.get("case_id") or "") == str(case_id or "")
            and str(row.get("supplier_id") or "") == str(supplier_id or "")
            and str(row.get("item_id") or "") == str(item_id or "")
            and str(row.get("dst_node_id") or "") == str(dst_node_id or "")
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Controle d'exposition absent ou duplique: {extension}/{case_id}."
            )
        return matches[0]

    def _attach_effect_exposure(rows: Sequence[dict[str, Any]], extension: str) -> None:
        for row in rows:
            gate = _single_lane_gate(
                extension,
                case_id=row.get("case_id"),
                supplier_id=row.get("supplier_id"),
                item_id=row.get("item_id"),
                dst_node_id=row.get("dst_node_id"),
            )
            row.update(
                {
                    "baseline_active_flow_pass": bool(
                        gate["baseline_active_flow_pass"]
                    ),
                    "risk_application_exposure_pass": bool(
                        gate["risk_application_exposure_pass"]
                    ),
                    "active_exposure_interpretability_pass": bool(
                        gate["active_exposure_interpretability_pass"]
                    ),
                    "distinct_joint_active_exposure_seed_count": int(
                        gate["distinct_joint_active_exposure_seed_count"]
                    ),
                }
            )

    _attach_effect_exposure(temporal_effect_rows, "temporal_robustness")
    _attach_effect_exposure(four_effect_rows, "priority_four_business_causes")
    for row in temporal_pair_rows:
        gate_a = _single_lane_gate(
            "temporal_robustness",
            case_id=row.get("context_a_case_id"),
            supplier_id=row.get("supplier_id"),
            item_id=row.get("item_id"),
            dst_node_id=row.get("dst_node_id"),
        )
        gate_b = _single_lane_gate(
            "temporal_robustness",
            case_id=row.get("context_b_case_id"),
            supplier_id=row.get("supplier_id"),
            item_id=row.get("item_id"),
            dst_node_id=row.get("dst_node_id"),
        )
        row.update(
            {
                "context_a_active_exposure_interpretability_pass": bool(
                    gate_a["active_exposure_interpretability_pass"]
                ),
                "context_b_active_exposure_interpretability_pass": bool(
                    gate_b["active_exposure_interpretability_pass"]
                ),
                "pairwise_exposure_interpretability_pass": bool(
                    gate_a["active_exposure_interpretability_pass"]
                    and gate_b["active_exposure_interpretability_pass"]
                ),
            }
        )
    for row in four_pair_rows:
        gate_a = _single_lane_gate(
            "priority_four_business_causes",
            case_id=row.get("context_a_case_id"),
            supplier_id=row.get("supplier_id"),
            item_id=row.get("item_id"),
            dst_node_id=row.get("dst_node_id"),
        )
        gate_b = _single_lane_gate(
            "priority_four_business_causes",
            case_id=row.get("context_b_case_id"),
            supplier_id=row.get("supplier_id"),
            item_id=row.get("item_id"),
            dst_node_id=row.get("dst_node_id"),
        )
        row.update(
            {
                "context_a_active_exposure_interpretability_pass": bool(
                    gate_a["active_exposure_interpretability_pass"]
                ),
                "context_b_active_exposure_interpretability_pass": bool(
                    gate_b["active_exposure_interpretability_pass"]
                ),
                "pairwise_exposure_interpretability_pass": bool(
                    gate_a["active_exposure_interpretability_pass"]
                    and gate_b["active_exposure_interpretability_pass"]
                ),
            }
        )
    common_gates = flow_controls["multi_lane_supplier_common_cause"][
        "active_flow_gate_by_case_lane"
    ]
    common_all_lanes_gates = flow_controls["multi_lane_supplier_common_cause"][
        "all_lanes_joint_active_exposure_gate_by_case_supplier"
    ]
    for row in common_effect_rows:
        matches = [
            gate
            for gate in common_gates
            if str(gate.get("case_id") or "") == str(row.get("case_id") or "")
            and str(gate.get("supplier_id") or "") == str(row.get("supplier_id") or "")
        ]
        if len(matches) != 2:
            raise ValueError(
                f"Controles d'exposition cause commune inexacts: {row.get('case_id')}."
            )
        joint_matches = [
            gate
            for gate in common_all_lanes_gates
            if str(gate.get("case_id") or "") == str(row.get("case_id") or "")
            and str(gate.get("supplier_id") or "") == str(row.get("supplier_id") or "")
        ]
        if len(joint_matches) != 1:
            raise ValueError(
                "Controle d'exposition conjointe cause commune absent ou "
                f"duplique: {row.get('case_id')}."
            )
        joint_gate = joint_matches[0]
        row.update(
            {
                "baseline_active_flow_pass": all(
                    gate["baseline_active_flow_pass"] for gate in matches
                ),
                "risk_application_exposure_pass": all(
                    gate["risk_application_exposure_pass"] for gate in matches
                ),
                "active_exposure_interpretability_pass": bool(joint_gate["pass"]),
                "distinct_all_lanes_joint_active_exposure_seed_count": int(
                    joint_gate["distinct_all_lanes_joint_active_exposure_seed_count"]
                ),
                "minimum_required_joint_active_exposure_seed_count": int(
                    joint_gate["minimum_required_seed_count"]
                ),
            }
        )
        row["joint_multi_lane_conditional_effect_evaluable"] = bool(
            row["active_exposure_interpretability_pass"]
        )

    manifest_execution = {
        extension: _as_bool(manifest.get("execution_integrity_pass"))
        for extension, manifest in loaded.extension_manifests.items()
        if extension != "causal_lot_attribution_subset"
    }
    if set(manifest_execution) != {
        "multi_lane_supplier_common_cause",
        "temporal_robustness",
        "priority_four_business_causes",
    } or not all(manifest_execution.values()):
        raise ValueError("Les manifestes ne confirment pas l'integrite d'execution.")
    temporal_execution = manifest_execution["temporal_robustness"]
    four_execution = manifest_execution["priority_four_business_causes"]
    common_execution = manifest_execution["multi_lane_supplier_common_cause"]
    temporal_exposure = bool(
        flow_controls["temporal_robustness"]["active_exposure_interpretability_pass"]
    )
    four_exposure = bool(
        flow_controls["priority_four_business_causes"][
            "active_exposure_interpretability_pass"
        ]
    )
    common_exposure = bool(
        flow_controls["multi_lane_supplier_common_cause"][
            "active_exposure_interpretability_pass"
        ]
    )
    recomputed_exposure = {
        "multi_lane_supplier_common_cause": common_exposure,
        "temporal_robustness": temporal_exposure,
        "priority_four_business_causes": four_exposure,
    }
    for extension, value in recomputed_exposure.items():
        manifest = loaded.extension_manifests[extension]
        if (
            _as_bool(manifest.get("active_flow_gate_pass"))
            != bool(flow_controls[extension]["baseline_active_flow_pass"])
            or _as_bool(manifest.get("baseline_active_flow_pass"))
            != bool(flow_controls[extension]["baseline_active_flow_pass"])
            or _as_bool(manifest.get("risk_application_exposure_pass"))
            != bool(flow_controls[extension]["risk_application_exposure_pass"])
            or _as_bool(manifest.get("active_exposure_interpretability_pass")) != value
            or manifest.get("active_flow_gate_by_case_lane")
            != flow_controls[extension]["active_flow_gate_by_case_lane"]
            or manifest.get("all_lanes_joint_active_exposure_gate_by_case_supplier")
            != flow_controls[extension][
                "all_lanes_joint_active_exposure_gate_by_case_supplier"
            ]
            or _as_bool(manifest.get("all_lanes_joint_active_exposure_pass"))
            != bool(flow_controls[extension]["all_lanes_joint_active_exposure_pass"])
        ):
            raise ValueError(f"Exposition active non recomposable: {extension}.")
    runner_execution_gates = dict(
        loaded.runner_manifest.get("extension_execution_integrity_gates") or {}
    )
    runner_exposure_gates = dict(
        loaded.runner_manifest.get("extension_active_exposure_interpretability_gates")
        or {}
    )
    if (
        runner_execution_gates != manifest_execution
        or {str(key): _as_bool(value) for key, value in runner_exposure_gates.items()}
        != recomputed_exposure
    ):
        raise ValueError("Les controles runner ne correspondent pas aux extensions.")
    temporal_interpretation.update(
        {
            "execution_integrity_pass": temporal_execution,
            "active_exposure_interpretability_pass": temporal_exposure,
            "period_specific_conditional_effects_described": True,
            "temporal_effect_causal_state_dependence_evaluable": False,
            "temporal_effect_causal_state_dependence_claimed": False,
            "calendar_load_preincident_state_and_right_censoring_confounding_present": True,
            "preincident_observable_state_snapshots_paired": True,
            "preincident_complete_engine_checkpoint_available": False,
            "global_priority_temporal_robustness_evaluable": False,
            "follow_up_group_effect_characterization_interpretable": bool(
                temporal_execution and temporal_exposure
            ),
        }
    )
    four_interpretation.update(
        {
            "execution_integrity_pass": four_execution,
            "active_exposure_interpretability_pass": four_exposure,
            "global_four_cause_priority_robustness_evaluable": False,
            "cause_amplitudes_are_not_commensurable": True,
            "cross_cause_importance_ranking_allowed": False,
            "follow_up_group_effect_characterization_interpretable": bool(
                four_execution and four_exposure
            ),
        }
    )
    common_interpretation.update(
        {
            "execution_integrity_pass": common_execution,
            "active_exposure_interpretability_pass": common_exposure,
            "joint_multi_lane_conditional_effect_evaluable": bool(
                common_execution and common_exposure
            ),
        }
    )

    legacy_controls = _read_json(loaded.runner_dir / "promotion_controls.json")
    legacy_alias_values = {
        field: _as_bool(legacy_controls.get(field))
        for field in (
            "common_cause_pass",
            "temporal_robustness_pass",
            "four_business_causes_pass",
            "all_required_controls_pass",
            "promotion_allowed",
        )
    }
    if (
        legacy_controls.get("promotion_allowed") is not False
        or legacy_controls.get("confirmatory_priority_set_release_allowed") is not False
        or legacy_controls.get("global_priority_release_allowed") is not False
        or legacy_controls.get("action_promotion_allowed") is not False
        or legacy_controls.get("counterfactual_entity_identity_validated") is not False
        or legacy_controls.get("causal_lot_attribution_available") is not False
    ):
        raise ValueError("Les controles runner revendiquent une promotion indue.")
    execution_integrity = bool(
        common_execution
        and temporal_execution
        and four_execution
        and causal["causal_lot_execution_integrity_pass"]
    )
    causal_manifest = loaded.extension_manifests["causal_lot_attribution_subset"]
    if (
        _as_bool(causal_manifest.get("causal_lot_execution_integrity_pass"))
        != causal["causal_lot_execution_integrity_pass"]
        or _as_bool(
            causal_manifest.get("technical_event_heuristic_pairing_integrity_pass")
        )
        != causal["technical_event_heuristic_pairing_integrity_pass"]
        or _as_bool(causal_manifest.get("heuristic_comparison_evaluable_pass"))
        != causal["heuristic_comparison_evaluable_pass"]
        or _as_bool(causal_manifest.get("heuristic_comparison_display_allowed"))
        != causal["heuristic_comparison_display_allowed"]
        or causal_manifest.get("causal_comparison_evaluable_pass") is not False
        or causal_manifest.get("all_pairs_counterfactually_evaluated") is not False
        or _as_bool(causal_manifest.get("all_root_gates_pass"))
        != causal["all_root_gates_pass"]
        or _as_bool(causal_manifest.get("all_genealogy_integrity_gates_pass"))
        != causal["all_genealogy_integrity_gates_pass"]
        or _as_bool(
            causal_manifest.get(
                "all_pairs_heuristic_technical_event_comparison_evaluated"
            )
        )
        != causal["all_pairs_heuristic_technical_event_comparison_evaluated"]
        or _to_int(causal_manifest.get("unique_matched_technical_key_count"))
        != causal["unique_matched_technical_key_count"]
        or _as_bool(loaded.runner_manifest.get("causal_lot_execution_integrity_pass"))
        != causal["causal_lot_execution_integrity_pass"]
    ):
        raise ValueError("Integrite lots non recomposable depuis les preuves.")
    lineage = loaded.plan_manifest.get("priority_selection_lineage") or {}
    lineage_digest = str(
        loaded.plan_manifest.get("priority_selection_lineage_sha256") or ""
    )
    checkpoint = loaded.preliminary_checkpoint
    controls = {
        "schema_version": SCHEMA_VERSION,
        "status": "scientific_controls_complete",
        "priority_selection_lineage": lineage,
        "priority_selection_lineage_sha256": lineage_digest,
        "priority_boundary_lineage_integrity_pass": True,
        "follow_up_group_supplier_count": EXPECTED_FOLLOW_UP_LANE_COUNT,
        "follow_up_group_chain_ids": list(lineage.get("follow_up_chain_ids") or []),
        "follow_up_group_is_unordered": True,
        "slot_order_has_scientific_meaning": False,
        "execution_integrity_pass": execution_integrity,
        "preliminary_checkpoint_status": (
            "validated_15_of_30_prefix_reused_unchanged"
            if checkpoint is not None
            else "not_applicable_direct_full_execution"
        ),
        "preliminary_checkpoint_retained": checkpoint is not None,
        "preliminary_checkpoint_reuse_integrity_pass": checkpoint is not None,
        "preliminary_checkpoint_used_as_final_or_confirmatory_result": False,
        "preliminary_checkpoint_completed_seed_count": (
            _to_int(checkpoint.get("completed_seed_count"))
            if checkpoint is not None
            else 0
        ),
        "multi_lane_common_cause_execution_integrity_pass": common_execution,
        "multi_lane_common_cause_active_exposure_interpretability_pass": common_exposure,
        "multi_lane_common_cause_interpretation_scope": (
            "execution_of_2_supplier_x_4_cause_x_30_seed_conditional_cases_only"
        ),
        "multi_lane_common_cause_interaction_or_synergy_evaluable": False,
        "cascade_amplification_claimed": False,
        "multi_lane_common_cause_merged_into_one_lane_ranking": False,
        "multi_lane_common_cause_probability_or_frequency_estimated": False,
        "temporal_execution_integrity_pass": temporal_execution,
        "temporal_active_exposure_interpretability_pass": temporal_exposure,
        "temporal_follow_up_group_effect_characterization_pass": bool(
            temporal_execution and temporal_exposure
        ),
        "temporal_state_dependence_causally_identified": False,
        "global_priority_temporal_robustness_evaluable": False,
        "four_cause_execution_integrity_pass": four_execution,
        "four_cause_active_exposure_interpretability_pass": four_exposure,
        "four_cause_follow_up_group_effect_characterization_pass": bool(
            four_execution and four_exposure
        ),
        "global_four_cause_priority_robustness_evaluable": False,
        "causal_lot_execution_integrity_pass": causal[
            "causal_lot_execution_integrity_pass"
        ],
        "technical_event_heuristic_pairing_integrity_pass": causal[
            "technical_event_heuristic_pairing_integrity_pass"
        ],
        "heuristic_comparison_evaluable_pass": causal[
            "heuristic_comparison_evaluable_pass"
        ],
        "causal_comparison_evaluable_pass": False,
        "counterfactual_entity_identity_validated": False,
        "causal_lot_attribution_available": False,
        "causal_genealogy_quantity_status": "upper_bound_only",
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "network_recovery_metric_used_in_any_gate_or_ranking": False,
        "legacy_runner_release_gate_aliases": legacy_alias_values,
        "legacy_completion_or_flow_alias_accepted_as_robustness": False,
        "legacy_aliases_neutralized_in_scientific_controls": True,
        "legacy_source_artifacts_not_scientifically_released": list(
            CONSOLIDATED_SMALL_SOURCE_FILES
        ),
        "legacy_ranking_artifacts_not_scientifically_released": list(
            LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
        ),
        "legacy_ranking_display_allowed": False,
        "legacy_ranking_used_for_extension_interpretation": False,
        "global_network_priority_robustness_evaluable": False,
        "promotion_allowed": False,
        "promotion_block_reason": (
            "extensions characterize the complete four-lane service nonseparation "
            "group but not the other 14 active lanes or historical incident probabilities"
        ),
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "industrial_criticality_claimed": False,
        "historical_supplier_probability_estimated": False,
        "broad_supply_uncertainty_monte_carlo_claimed": False,
    }
    audit = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "source_runner_signature": str(
            loaded.runner_manifest.get("runner_signature") or ""
        ),
        "source_plan_signature": str(loaded.plan_manifest.get("plan_signature") or ""),
        "source_file_sha256": dict(loaded.source_file_sha256),
        "ledger_case_registry_sha256": loaded.ledger_case_registry_sha256,
        "priority_selection_lineage": lineage,
        "priority_selection_lineage_sha256": lineage_digest,
        "priority_boundary_lineage_integrity_pass": True,
        "bootstrap": {
            "method": "deterministic_paired_complete_seed_block_bootstrap",
            "paired_seed_count": EXPECTED_PAIRED_SEED_COUNT,
            "resample_count": resamples,
            "confidence_interval": "percentile_95_percent",
        },
        "matrix_contract": {
            "temporal": "4_unordered_follow_up_lanes_x_4_windows_x_30_paired_seeds",
            "four_business_causes": "4_unordered_follow_up_lanes_x_4_causes_x_30_paired_seeds",
            "multi_lane_common_cause": (
                "2_multi_lane_suppliers_x_4_causes_x_30_paired_seeds"
            ),
            "causal_lot": "4_unordered_follow_up_lanes_x_1_paired_seed",
        },
        "execution_integrity": {
            "all_signed_matrices_exact": True,
            "ledger_case_hashes_and_paths_valid": True,
            "input_j0_seed_trace_and_demand_pairing_valid": True,
            "metric_rows_recomputed_from_physical_evidence": True,
            "flow_rows_recomputed_without_duplicate_seed_credit": True,
            "runner_summaries_recomputed": True,
            "common_cause": flow_controls["multi_lane_supplier_common_cause"],
            "temporal": flow_controls["temporal_robustness"],
            "four_business_causes": flow_controls["priority_four_business_causes"],
            "causal_lot": causal,
            "execution_integrity_pass": execution_integrity,
        },
        "temporal_interpretation": temporal_interpretation,
        "four_business_cause_interpretation": four_interpretation,
        "multi_lane_common_cause_interpretation": {
            **common_interpretation,
            "merged_with_one_lane_priority": False,
            "probability_or_frequency_estimated": False,
        },
        "causal_lot_interpretation": causal,
        "scientific_promotion_controls": controls,
        "effect_count_semantics": (
            "display-threshold exceedance counts among 30 paired model draws; neither "
            "historical frequency, business materiality, nor supplier incident probability"
        ),
        "cause_effect_semantics": (
            "consequence under each predeclared severe hypothesis; cause amplitudes "
            "are not comparable as probabilities or per-unit sensitivities"
        ),
        "no_opaque_composite_score": True,
        "follow_up_scope": {
            "status": "complete_service_nonseparation_group_follow_up",
            "supplier_count": EXPECTED_FOLLOW_UP_LANE_COUNT,
            "lane_count": EXPECTED_FOLLOW_UP_LANE_COUNT,
            "group_is_unordered": True,
            "service_nonseparation_group_fully_followed_up": True,
            "universal_nonseparation_group_supplier_count": 16,
            "global_network_priority_evaluable": False,
        },
        "post_selection_scope": {
            "same_seed_blocks_used_for_selection_and_characterization": True,
            "confirmatory_inference_evaluable": False,
            "out_of_sample_validation_present": False,
        },
        "network_recovery_metric": {
            "status": "excluded_invalid_common_window",
            "used_in_any_gate_or_ranking": False,
            "reason": (
                "the raw recovery field uses a common window instead of each exact "
                "lane and extension incident window"
            ),
        },
    }
    return (
        audit,
        temporal_effect_rows,
        temporal_pair_rows,
        four_effect_rows,
        four_pair_rows,
        common_effect_rows,
        controls,
    )


def validate_audit_package(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    manifest_path = root / "extension_interpretation_audit_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Manifeste d'audit des extensions absent.")
    manifest = _read_json(manifest_path)
    if str(manifest.get("schema_version") or "") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("Version du paquet d'audit des extensions inconnue.")
    if str(manifest.get("status") or "") != "complete":
        raise ValueError("Le paquet d'audit des extensions n'est pas complet.")
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
    if str(manifest.get("package_signature") or "") != _canonical_sha256(
        signature_payload
    ):
        raise ValueError("Signature canonique du paquet d'extensions invalide.")
    if str(manifest.get("builder_sha256") or "") != _sha256(Path(__file__).resolve()):
        raise ValueError(
            "Le paquet n'a pas ete produit par le builder d'audit courant."
        )
    if _to_int(manifest.get("bootstrap_resample_count")) != BOOTSTRAP_RESAMPLE_COUNT:
        raise ValueError("Le paquet ne contient pas les 10 000 bootstrap requis.")
    hashes = dict(manifest.get("artifact_file_sha256") or {})
    if set(hashes) != set(OUTPUT_FILES):
        raise ValueError("Inventaire des fichiers d'audit des extensions invalide.")
    observed_files = {path.name for path in root.iterdir() if path.is_file()}
    expected_files = set(OUTPUT_FILES) | {
        "extension_interpretation_audit_manifest.json"
    }
    if observed_files != expected_files or any(
        path.is_dir() or path.is_symlink() for path in root.iterdir()
    ):
        raise ValueError(
            "Inventaire disque du paquet d'audit incomplet, excessif ou non regulier."
        )
    for name, expected in hashes.items():
        path = root / name
        if not path.is_file() or _sha256(path) != str(expected):
            raise ValueError(f"Empreinte de sortie invalide: {name}")

    audit = _read_json(root / "scientific_extension_interpretation_audit.json")
    controls = _read_json(root / "scientific_promotion_controls.json")
    if (
        str(audit.get("schema_version") or "") != SCHEMA_VERSION
        or str(audit.get("status") or "") != "complete"
        or str(controls.get("schema_version") or "") != SCHEMA_VERSION
        or str(controls.get("status") or "") != "scientific_controls_complete"
    ):
        raise ValueError("Resultat scientifique d'extensions invalide.")
    expected_source_keys = {
        *(f"runner/{name}" for name in RUNNER_FILES),
        *(f"plan/{name}" for name in PLAN_FILES),
    }
    source_hashes = manifest.get("source_file_sha256") or {}
    if (
        not isinstance(source_hashes, dict)
        or set(source_hashes) != expected_source_keys
        or audit.get("source_file_sha256") != source_hashes
        or audit.get("ledger_case_registry_sha256")
        != manifest.get("ledger_case_registry_sha256")
        or audit.get("scientific_promotion_controls") != controls
        or any(len(str(value)) != 64 for value in source_hashes.values())
    ):
        raise ValueError("Lignee physique audit/manifeste/controles incoherente.")
    if _to_int((audit.get("bootstrap") or {}).get("resample_count")) != (
        BOOTSTRAP_RESAMPLE_COUNT
    ):
        raise ValueError("Resultat scientifique sans 10 000 bootstrap.")
    for field in (
        "global_priority_temporal_robustness_evaluable",
        "global_four_cause_priority_robustness_evaluable",
        "global_network_priority_robustness_evaluable",
        "promotion_allowed",
        "legacy_completion_or_flow_alias_accepted_as_robustness",
    ):
        if controls.get(field) is not False:
            raise ValueError(f"Controle fail-closed invalide: {field}")
    if (
        controls.get("execution_integrity_pass") is not True
        or controls.get("priority_boundary_lineage_integrity_pass") is not True
        or controls.get("follow_up_group_supplier_count")
        != EXPECTED_FOLLOW_UP_LANE_COUNT
        or controls.get("follow_up_group_is_unordered") is not True
        or controls.get("slot_order_has_scientific_meaning") is not False
        or controls.get("counterfactual_entity_identity_validated") is not False
        or controls.get("causal_lot_attribution_available") is not False
        or controls.get("confirmatory_priority_set_release_allowed") is not False
        or controls.get("global_priority_release_allowed") is not False
        or controls.get("action_promotion_allowed") is not False
        or controls.get("legacy_source_artifacts_not_scientifically_released")
        != list(CONSOLIDATED_SMALL_SOURCE_FILES)
        or controls.get("legacy_ranking_artifacts_not_scientifically_released")
        != list(LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED)
        or controls.get("legacy_ranking_display_allowed") is not False
        or controls.get("legacy_ranking_used_for_extension_interpretation") is not False
    ):
        raise ValueError("Controles de lignee/groupe/integrite invalides.")
    lineage = controls.get("priority_selection_lineage")
    follow_up_chain_ids, slot_by_chain = _validate_priority_selection_lineage(
        lineage,
        declared_digest=controls.get("priority_selection_lineage_sha256"),
    )
    if (
        audit.get("priority_selection_lineage") != lineage
        or audit.get("priority_selection_lineage_sha256")
        != controls.get("priority_selection_lineage_sha256")
        or audit.get("priority_boundary_lineage_integrity_pass") is not True
    ):
        raise ValueError("Lignee boundary divergente entre audit et controles.")
    if controls.get("network_recovery_metric_status") != (
        "excluded_invalid_common_window"
    ):
        raise ValueError("Statut d'exclusion de la recuperation reseau invalide.")
    if audit.get("network_recovery_metric", {}).get(
        "used_in_any_gate_or_ranking"
    ) is not (False):
        raise ValueError("La metrique de recuperation invalide a ete reintroduite.")
    expected_row_counts = {
        "temporal_effect_by_lane_window.csv": 48,
        "temporal_pairwise_difference_audit.csv": 72,
        "four_cause_effect_by_lane_cause.csv": 48,
        "four_cause_pairwise_difference_audit.csv": 72,
        "common_cause_effect_by_supplier_cause.csv": 24,
    }
    for name, expected_count in expected_row_counts.items():
        rows = _read_csv(root / name)
        if len(rows) != expected_count:
            raise ValueError(f"Nombre de lignes scientifique invalide pour {name}.")
        if any("recovery" in field.lower() for row in rows for field in row):
            raise ValueError(f"Champ de recuperation interdit dans {name}.")
        forbidden_tokens = ("rank", "order", "inversion", "top3", "selected_three")
        if any(
            any(token in field.lower() for token in forbidden_tokens)
            for row in rows
            for field in row
        ):
            raise ValueError(f"Champ de classement interdit dans {name}.")
    expected_metrics = {metric.key for metric in METRICS}
    supplier_by_chain = {
        str(row.get("driver_chain_id") or ""): str(row.get("supplier_id") or "")
        for row in lineage.get("follow_up_driver_mappings") or []
    }
    temporal_rows = _read_csv(root / "temporal_effect_by_lane_window.csv")
    temporal_keys = [
        (
            str(row.get("chain_id") or ""),
            _to_int(row.get("window_index")),
            str(row.get("metric") or ""),
        )
        for row in temporal_rows
    ]
    expected_temporal_keys = {
        (chain, window_index, metric)
        for chain in follow_up_chain_ids
        for window_index, _start, _end in CALENDAR_WINDOWS
        for metric in expected_metrics
    }
    if (
        len(temporal_keys) != len(set(temporal_keys))
        or set(temporal_keys) != expected_temporal_keys
        or any(
            str(row.get("supplier_id") or "")
            != supplier_by_chain.get(str(row.get("chain_id") or ""))
            or _to_int(row.get("selection_slot"))
            != slot_by_chain.get(str(row.get("chain_id") or ""))
            or not str(
                row.get("outcome_end_residual_backlog_delta_per_requested_unit_mean")
                or ""
            )
            or _as_bool(row.get("outcome_end_residual_is_loss_claimed"))
            or not _as_bool(row.get("right_censoring_possible"))
            for row in temporal_rows
        )
    ):
        raise ValueError("Matrice scientifique temporelle non exacte.")
    four_rows = _read_csv(root / "four_cause_effect_by_lane_cause.csv")
    four_keys = [
        (
            str(row.get("chain_id") or ""),
            str(row.get("failure_mode") or ""),
            str(row.get("metric") or ""),
        )
        for row in four_rows
    ]
    expected_four_keys = {
        (chain, cause, metric)
        for chain in follow_up_chain_ids
        for cause in FOUR_CAUSES
        for metric in expected_metrics
    }
    if (
        len(four_keys) != len(set(four_keys))
        or set(four_keys) != expected_four_keys
        or any(
            str(row.get("supplier_id") or "")
            != supplier_by_chain.get(str(row.get("chain_id") or ""))
            for row in four_rows
        )
    ):
        raise ValueError("Matrice scientifique quatre-causes non exacte.")
    for name in (
        "temporal_effect_by_lane_window.csv",
        "four_cause_effect_by_lane_cause.csv",
        "common_cause_effect_by_supplier_cause.csv",
    ):
        rows = _read_csv(root / name)
        if any(
            _to_int(row.get("paired_seed_count")) != EXPECTED_PAIRED_SEED_COUNT
            or _as_bool(row.get("count_is_probability_or_frequency"))
            or _as_bool(row.get("historical_occurrence_probability_estimated"))
            for row in rows
        ):
            raise ValueError(f"Semantique de comptage invalide dans {name}.")
    temporal_differences = _read_csv(root / "temporal_pairwise_difference_audit.csv")
    four_differences = _read_csv(root / "four_cause_pairwise_difference_audit.csv")
    temporal_difference_keys = [
        (
            str(row.get("chain_id") or ""),
            _to_int(row.get("context_a_window_index")),
            _to_int(row.get("context_b_window_index")),
            str(row.get("metric") or ""),
        )
        for row in temporal_differences
    ]
    expected_temporal_difference_keys = {
        (chain, left, right, metric)
        for chain in follow_up_chain_ids
        for left in range(1, len(CALENDAR_WINDOWS) + 1)
        for right in range(left + 1, len(CALENDAR_WINDOWS) + 1)
        for metric in expected_metrics
    }
    ordered_causes = sorted(FOUR_CAUSES)
    four_difference_keys = [
        (
            str(row.get("chain_id") or ""),
            str(row.get("context_a_failure_mode") or ""),
            str(row.get("context_b_failure_mode") or ""),
            str(row.get("metric") or ""),
        )
        for row in four_differences
    ]
    expected_four_difference_keys = {
        (chain, ordered_causes[left], ordered_causes[right], metric)
        for chain in follow_up_chain_ids
        for left in range(len(ordered_causes) - 1)
        for right in range(left + 1, len(ordered_causes))
        for metric in expected_metrics
    }
    if any(
        not _as_bool(row.get("comparison_is_descriptive_only"))
        or _as_bool(row.get("comparison_used_for_selection"))
        or _as_bool(row.get("cause_importance_comparison_evaluable"))
        or str(row.get("comparison_orientation") or "")
        != "canonical_context_identifier_only"
        or _to_int(row.get("paired_seed_count")) != EXPECTED_PAIRED_SEED_COUNT
        for row in (*temporal_differences, *four_differences)
    ) or (
        len(temporal_difference_keys) != len(set(temporal_difference_keys))
        or set(temporal_difference_keys) != expected_temporal_difference_keys
        or len(four_difference_keys) != len(set(four_difference_keys))
        or set(four_difference_keys) != expected_four_difference_keys
    ):
        raise ValueError(
            "Les contrastes descriptifs sont presentes comme un classement."
        )
    common_rows = _read_csv(root / "common_cause_effect_by_supplier_cause.csv")
    common_keys = [
        (
            str(row.get("supplier_id") or ""),
            str(row.get("failure_mode") or ""),
            str(row.get("metric") or ""),
        )
        for row in common_rows
    ]
    expected_common_keys = {
        (supplier, cause, metric)
        for supplier in EXPECTED_MULTI_LANE_SUPPLIERS
        for cause in FOUR_CAUSES
        for metric in expected_metrics
    }
    expected_multi_lane_chains = dict(
        lineage.get("all_multi_lane_supplier_active_chain_ids_by_id") or {}
    )
    if (
        len(common_keys) != len(set(common_keys))
        or set(common_keys) != expected_common_keys
        or any(
            _to_int(row.get("affected_lane_count")) != 2
            or str(row.get("affected_chain_ids") or "")
            != "|".join(
                expected_multi_lane_chains.get(str(row.get("supplier_id") or ""), [])
            )
            or not _as_bool(row.get("supplier_cause_seed_is_single_bootstrap_block"))
            or not _as_bool(row.get("lane_rows_not_treated_as_independent_replicates"))
            or _to_int(row.get("minimum_required_joint_active_exposure_seed_count"))
            != MINIMUM_ACTIVE_FLOW_SEED_COUNT
            or not 0
            <= _to_int(row.get("distinct_all_lanes_joint_active_exposure_seed_count"))
            <= EXPECTED_PAIRED_SEED_COUNT
            or _as_bool(row.get("active_exposure_interpretability_pass"))
            != (
                _as_bool(row.get("baseline_active_flow_pass"))
                and _as_bool(row.get("risk_application_exposure_pass"))
                and _to_int(
                    row.get("distinct_all_lanes_joint_active_exposure_seed_count")
                )
                >= MINIMUM_ACTIVE_FLOW_SEED_COUNT
            )
            or _as_bool(row.get("joint_multi_lane_conditional_effect_evaluable"))
            != _as_bool(row.get("active_exposure_interpretability_pass"))
            or _as_bool(row.get("multi_lane_interaction_or_synergy_evaluable"))
            or _as_bool(row.get("cascade_amplification_claimed"))
            for row in common_rows
        )
    ):
        raise ValueError("Agregation scientifique cause commune invalide.")
    return {
        "valid": True,
        "status": "complete",
        "package_signature": str(manifest.get("package_signature") or ""),
        "execution_integrity_pass": _as_bool(controls.get("execution_integrity_pass")),
        "follow_up_group_supplier_count": _to_int(
            controls.get("follow_up_group_supplier_count")
        ),
        "follow_up_group_is_unordered": _as_bool(
            controls.get("follow_up_group_is_unordered")
        ),
        "promotion_allowed": False,
    }


def build_audit_package(
    *,
    runner_dir: str | Path,
    output_dir: str | Path,
    resamples: int = BOOTSTRAP_RESAMPLE_COUNT,
) -> Path:
    if resamples != BOOTSTRAP_RESAMPLE_COUNT:
        raise ValueError("Le paquet publiable exige exactement 10 000 bootstrap.")
    source_root = Path(runner_dir).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"Le dossier de sortie existe deja: {destination}")
    loaded = load_closed_runner(source_root)
    lineage = loaded.plan_manifest.get("priority_selection_lineage") or {}
    protected_roots = (
        loaded.runner_dir,
        loaded.plan_dir,
        Path(str(loaded.plan_manifest.get("source_artifact") or "")).resolve(),
        Path(str(lineage.get("priority_boundary_dir") or "")).resolve(),
    )
    for protected in protected_roots:
        try:
            destination.relative_to(protected)
        except ValueError:
            pass
        else:
            raise ValueError("Le paquet additif doit rester hors du runner et du plan.")
    source_hashes_before = dict(loaded.source_file_sha256)
    registry_hash_before = loaded.ledger_case_registry_sha256
    (
        audit,
        temporal_effect_rows,
        temporal_pair_rows,
        four_effect_rows,
        four_pair_rows,
        common_effect_rows,
        controls,
    ) = analyze_closed_runner(loaded, resamples=resamples)
    audit["source_file_sha256"] = source_hashes_before
    audit["ledger_case_registry_sha256"] = registry_hash_before

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    try:
        _write_json(staging / "scientific_extension_interpretation_audit.json", audit)
        _write_csv(staging / "temporal_effect_by_lane_window.csv", temporal_effect_rows)
        _write_csv(
            staging / "temporal_pairwise_difference_audit.csv", temporal_pair_rows
        )
        _write_csv(staging / "four_cause_effect_by_lane_cause.csv", four_effect_rows)
        _write_csv(staging / "four_cause_pairwise_difference_audit.csv", four_pair_rows)
        _write_csv(
            staging / "common_cause_effect_by_supplier_cause.csv",
            common_effect_rows,
        )
        _write_json(staging / "scientific_promotion_controls.json", controls)
        artifact_hashes = {name: _sha256(staging / name) for name in OUTPUT_FILES}
        signature_payload = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "source_file_sha256": source_hashes_before,
            "ledger_case_registry_sha256": registry_hash_before,
            "artifact_file_sha256": artifact_hashes,
            "bootstrap_resample_count": resamples,
        }
        manifest = {
            **signature_payload,
            "status": "complete",
            "package_signature": _canonical_sha256(signature_payload),
            "source_runner_dir": str(loaded.runner_dir),
            "source_plan_dir": str(loaded.plan_dir),
            "output_dir": str(destination),
            "source_runner_mutated": False,
            "source_plan_mutated": False,
            "main_network_campaign_opened_or_mutated": False,
            "large_case_directories_copied": False,
            "promotion_allowed": False,
            "global_network_priority_robustness_evaluable": False,
        }
        _write_json(staging / "extension_interpretation_audit_manifest.json", manifest)
        reloaded = load_closed_runner(source_root)
        if (
            reloaded.source_file_sha256 != source_hashes_before
            or reloaded.ledger_case_registry_sha256 != registry_hash_before
        ):
            raise RuntimeError("Le runner ou son plan ont change pendant l'audit.")
        validate_audit_package(staging)
        staging.replace(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    validate_audit_package(destination)
    return destination


def _validated_consolidation_manifest_payload(
    payload: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    if (
        str(payload.get("schema_version") or "") != RUNNER_SCHEMA_VERSION
        or str(payload.get("status") or "") != "complete"
    ):
        raise ValueError("Manifeste de consolidation source incomplet ou incompatible.")
    source_hashes = dict(payload.get("source_small_file_hashes") or {})
    extension_hashes = dict(payload.get("extension_small_file_hashes") or {})
    extension_manifest_hashes = dict(payload.get("extension_manifest_hashes") or {})
    if (
        not REQUIRED_CONSOLIDATED_SOURCE_FILES <= set(source_hashes)
        or not set(source_hashes) <= set(CONSOLIDATED_SMALL_SOURCE_FILES)
        or set(extension_hashes) != set(CONSOLIDATED_SMALL_EXTENSION_FILES)
        or set(extension_manifest_hashes) != set(CONSOLIDATED_EXTENSION_MANIFEST_FILES)
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(value))
            for mapping in (
                source_hashes,
                extension_hashes,
                extension_manifest_hashes,
            )
            for value in mapping.values()
        )
    ):
        raise ValueError("Inventaire signe du consolide source invalide.")
    signature_payload = {
        key: payload.get(key)
        for key in (
            "schema_version",
            "source_campaign_manifest_sha256",
            "source_small_file_hashes",
            "extension_small_file_hashes",
            "runner_manifest_sha256",
            "extension_manifest_hashes",
        )
    }
    if (
        not re.fullmatch(
            r"[0-9a-f]{64}",
            str(payload.get("source_campaign_manifest_sha256") or ""),
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(payload.get("runner_manifest_sha256") or "")
        )
        or str(payload.get("consolidation_signature") or "")
        != _canonical_sha256(signature_payload)
        or payload.get("confirmatory_priority_set_release_allowed") is not False
        or payload.get("global_priority_release_allowed") is not False
        or payload.get("action_promotion_allowed") is not False
        or payload.get("source_artifacts_mutated") is not False
        or payload.get("large_case_directories_copied") is not False
        or str(
            extension_hashes.get("post_priority_extension_runner_manifest.json") or ""
        )
        != str(payload.get("runner_manifest_sha256") or "")
        or any(
            str(extension_hashes.get(filename) or "")
            != str(extension_manifest_hashes.get(extension) or "")
            for extension, filename in CONSOLIDATED_EXTENSION_MANIFEST_FILES.items()
        )
    ):
        raise ValueError("Signature ou garde scientifique du consolide invalide.")
    return source_hashes, extension_hashes, extension_manifest_hashes


def _validate_consolidated_source(root: Path) -> dict[str, Any]:
    """Revalidate a runner consolidation before any scientific overlay copy."""

    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError("Dossier consolide source absent.")
    entries = list(root.iterdir())
    if any(path.is_dir() or path.is_symlink() for path in entries):
        raise ValueError("Le consolide source contient un dossier ou lien interdit.")
    manifest_path = root / "consolidation_manifest.json"
    campaign_path = root / "campaign_manifest.json"
    if not manifest_path.is_file() or not campaign_path.is_file():
        raise FileNotFoundError("Manifestes du consolide source absents.")
    manifest = _read_json(manifest_path)
    (
        source_hashes,
        extension_hashes,
        extension_manifest_hashes,
    ) = _validated_consolidation_manifest_payload(manifest)
    expected_files = (
        set(source_hashes)
        | set(extension_hashes)
        | {"campaign_manifest.json", "consolidation_manifest.json"}
    )
    observed_files = {path.name for path in entries if path.is_file()}
    if observed_files != expected_files:
        raise ValueError("Inventaire disque exact du consolide source invalide.")
    for name, expected in {**source_hashes, **extension_hashes}.items():
        if _sha256(root / name) != expected:
            raise ValueError(f"Empreinte du consolide source invalide: {name}")
    if _sha256(campaign_path) != str(
        manifest.get("consolidated_campaign_manifest_sha256") or ""
    ) or _sha256(root / "post_priority_extension_runner_manifest.json") != str(
        manifest.get("runner_manifest_sha256") or ""
    ):
        raise ValueError("Manifeste campagne ou runner du consolide altere.")
    for extension, name in CONSOLIDATED_EXTENSION_MANIFEST_FILES.items():
        if _sha256(root / name) != extension_manifest_hashes[extension]:
            raise ValueError(f"Manifeste extension du consolide altere: {extension}")

    campaign = _read_json(campaign_path)
    runner_manifest = _read_json(root / "post_priority_extension_runner_manifest.json")
    states = manifest.get("extensions_required")
    if (
        str(campaign.get("status") or "") != "complete"
        or str(campaign.get("mode") or "") != "full"
        or str(campaign.get("consolidation_signature") or "")
        != str(manifest.get("consolidation_signature") or "")
        or campaign.get("extensions_required") != states
        or _to_int(campaign.get("consolidated_small_file_count")) != len(source_hashes)
        or _to_int(campaign.get("consolidated_extension_file_count"))
        != len(extension_hashes)
        or campaign.get("source_campaign_complete") is not True
        or campaign.get("extension_runner_complete") is not True
        or campaign.get("previous_artifacts_mutated") is not False
        or campaign.get("large_case_directories_copied") is not False
        or not isinstance(states, dict)
        or set(states) != set(CONSOLIDATED_EXTENSION_MANIFEST_FILES)
        or any(
            not isinstance(state, dict)
            or state.get("pass") is not False
            or str(state.get("source_manifest_sha256") or "")
            != extension_manifest_hashes[name]
            for name, state in states.items()
        )
    ):
        raise ValueError("Etat consolide campagne/extensions non recomposable.")
    lineage = runner_manifest.get("priority_selection_lineage")
    lineage_digest = str(runner_manifest.get("priority_selection_lineage_sha256") or "")
    _validate_priority_selection_lineage(lineage, declared_digest=lineage_digest)
    if (
        str(runner_manifest.get("schema_version") or "") != RUNNER_SCHEMA_VERSION
        or str(runner_manifest.get("status") or "") != "complete"
        or str(runner_manifest.get("mode") or "") != "full"
        or runner_manifest.get("promotion_allowed") is not False
        or campaign.get("priority_selection_lineage") != lineage
        or str(campaign.get("priority_selection_lineage_sha256") or "")
        != lineage_digest
        or str(manifest.get("priority_selection_lineage_sha256") or "")
        != lineage_digest
        or str(runner_manifest.get("source_campaign_manifest_sha256") or "")
        != str(manifest.get("source_campaign_manifest_sha256") or "")
        or str(campaign.get("extension_runner_signature") or "")
        != str(runner_manifest.get("runner_signature") or "")
        or str(campaign.get("source_campaign_signature") or "")
        != str(lineage.get("source_campaign_signature") or "")
    ):
        raise ValueError("Lignee campagne/runner du consolide divergente.")
    for extension, name in CONSOLIDATED_EXTENSION_MANIFEST_FILES.items():
        extension_manifest = _read_json(root / name)
        if (
            str(extension_manifest.get("runner_signature") or "")
            != str(runner_manifest.get("runner_signature") or "")
            or str(extension_manifest.get("plan_signature") or "")
            != str(runner_manifest.get("plan_signature") or "")
            or str(extension_manifest.get("source_campaign_manifest_sha256") or "")
            != str(manifest.get("source_campaign_manifest_sha256") or "")
        ):
            raise ValueError(f"Lignee du manifeste extension divergente: {extension}")
    return {
        "manifest": manifest,
        "campaign": campaign,
        "runner_manifest": runner_manifest,
        "source_small_file_hashes": source_hashes,
        "extension_small_file_hashes": extension_hashes,
        "extension_manifest_hashes": extension_manifest_hashes,
    }


def _neutralized_campaign_manifest(
    source: Mapping[str, Any], controls: Mapping[str, Any]
) -> dict[str, Any]:
    payload = dict(source)
    legacy_top_level = {
        field: payload.get(field)
        for field in (
            "temporal_robustness_pass",
            "four_business_causes_pass",
            "common_cause_pass",
            "causal_lot_attribution_pass",
            "promotion_allowed",
        )
        if field in payload
    }
    for field in legacy_top_level:
        payload[field] = False
    states = payload.get("extensions_required")
    legacy_nested: dict[str, Any] = {}
    if isinstance(states, dict):
        new_states: dict[str, Any] = {}
        control_map = {
            "multi_lane_supplier_common_cause": (
                "multi_lane_common_cause_execution_integrity_pass"
            ),
            "temporal_robustness": "temporal_execution_integrity_pass",
            "four_business_cause_confirmation": "four_cause_execution_integrity_pass",
            "priority_four_business_causes": "four_cause_execution_integrity_pass",
            "causal_lot_attribution": "causal_lot_execution_integrity_pass",
        }
        for name, raw in states.items():
            state = dict(raw) if isinstance(raw, dict) else {"legacy_value": raw}
            legacy_nested[name] = state.get("pass")
            state["legacy_runner_release_gate_value"] = state.get("pass")
            state["pass"] = False
            state["pass_semantics"] = "neutralized_completion_or_flow_alias"
            control_field = control_map.get(str(name))
            if control_field:
                state["execution_integrity_pass"] = _as_bool(
                    controls.get(control_field)
                )
            if name == "temporal_robustness":
                state["global_robustness_evaluable"] = False
            if name in {
                "four_business_cause_confirmation",
                "priority_four_business_causes",
            }:
                state["global_robustness_evaluable"] = False
            new_states[str(name)] = state
        payload["extensions_required"] = new_states
    payload.update(
        {
            "scientific_interpretation_overlay_applied": True,
            "legacy_runner_promotion_aliases_neutralized": True,
            "legacy_top_level_promotion_alias_values": legacy_top_level,
            "legacy_nested_extension_pass_values": legacy_nested,
            "legacy_source_artifacts_not_scientifically_released": list(
                CONSOLIDATED_SMALL_SOURCE_FILES
            ),
            "legacy_ranking_artifacts_not_scientifically_released": list(
                LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
            ),
            "legacy_ranking_display_allowed": False,
            "legacy_ranking_used_for_extension_interpretation": False,
            "scientific_execution_integrity_pass": _as_bool(
                controls.get("execution_integrity_pass")
            ),
            "global_priority_temporal_robustness_evaluable": False,
            "global_four_cause_priority_robustness_evaluable": False,
            "global_network_priority_robustness_evaluable": False,
            "network_recovery_metric_status": "excluded_invalid_common_window",
            "promotion_allowed": False,
            "industrial_criticality_claimed": False,
            "historical_supplier_probability_estimated": False,
        }
    )
    return payload


def _neutralized_runner_manifest_copy(
    name: str,
    source: Mapping[str, Any],
    controls: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(source)
    extension_control = {
        "multi_lane_supplier_common_cause_manifest.json": (
            "multi_lane_common_cause_execution_integrity_pass"
        ),
        "temporal_robustness_manifest.json": "temporal_execution_integrity_pass",
        "priority_four_business_causes_manifest.json": (
            "four_cause_execution_integrity_pass"
        ),
        "causal_lot_attribution_manifest.json": "causal_lot_execution_integrity_pass",
    }
    if name in extension_control:
        payload["legacy_runner_release_gate_value"] = payload.get("release_gate_pass")
        payload["release_gate_pass"] = False
        payload["release_gate_semantics"] = (
            "completion_and_flow_only_not_scientific_robustness"
        )
        payload["scientific_execution_integrity_pass"] = _as_bool(
            controls.get(extension_control[name])
        )
        if name == "temporal_robustness_manifest.json":
            payload["follow_up_group_effect_characterization_pass"] = _as_bool(
                controls.get("temporal_follow_up_group_effect_characterization_pass")
            )
            payload["follow_up_group_is_unordered"] = True
            payload["global_priority_temporal_robustness_evaluable"] = False
        elif name == "priority_four_business_causes_manifest.json":
            payload["follow_up_group_effect_characterization_pass"] = _as_bool(
                controls.get("four_cause_follow_up_group_effect_characterization_pass")
            )
            payload["follow_up_group_is_unordered"] = True
            payload["global_four_cause_priority_robustness_evaluable"] = False
        elif name == "causal_lot_attribution_manifest.json":
            payload["counterfactual_entity_identity_validated"] = False
            payload["causal_lot_attribution_available"] = False
            payload["technical_event_heuristic_pairing_integrity_pass"] = _as_bool(
                controls.get("technical_event_heuristic_pairing_integrity_pass")
            )
    elif name == "post_priority_extension_runner_manifest.json":
        legacy_gates = dict(payload.get("extension_release_gates") or {})
        payload["legacy_extension_release_gate_values"] = legacy_gates
        payload["extension_release_gates"] = {key: False for key in legacy_gates}
        payload["legacy_causal_lot_release_gate_value"] = payload.get(
            "causal_lot_release_gate_pass"
        )
        payload["causal_lot_release_gate_pass"] = False
        payload["legacy_promotion_allowed_value"] = payload.get("promotion_allowed")
        payload["promotion_allowed"] = False
        payload["release_gate_semantics"] = (
            "completion_and_flow_only_not_scientific_robustness"
        )
        payload["scientific_execution_integrity_pass"] = _as_bool(
            controls.get("execution_integrity_pass")
        )
        payload["global_network_priority_robustness_evaluable"] = False
    return payload


def _validate_overlay_lineage_contract(
    *,
    campaign: Mapping[str, Any],
    consolidation: Mapping[str, Any],
    runner_manifest: Mapping[str, Any],
    audit_manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
    controls: Mapping[str, Any],
    source_runner_manifest_sha256: str,
) -> None:
    audit_signature_payload = {
        key: audit_manifest.get(key)
        for key in (
            "schema_version",
            "builder_sha256",
            "source_file_sha256",
            "ledger_case_registry_sha256",
            "artifact_file_sha256",
            "bootstrap_resample_count",
        )
    }
    if (
        str(audit_manifest.get("schema_version") or "") != MANIFEST_SCHEMA_VERSION
        or str(audit_manifest.get("status") or "") != "complete"
        or str(audit_manifest.get("package_signature") or "")
        != _canonical_sha256(audit_signature_payload)
        or str(audit_manifest.get("builder_sha256") or "")
        != _sha256(Path(__file__).resolve())
        or _to_int(audit_manifest.get("bootstrap_resample_count"))
        != BOOTSTRAP_RESAMPLE_COUNT
    ):
        raise ValueError("Manifeste audit embarque invalide.")
    source_hashes = audit_manifest.get("source_file_sha256") or {}
    if (
        not isinstance(source_hashes, dict)
        or str(
            source_hashes.get("runner/post_priority_extension_runner_manifest.json")
            or ""
        )
        != source_runner_manifest_sha256
        or audit.get("source_file_sha256") != source_hashes
        or audit.get("ledger_case_registry_sha256")
        != audit_manifest.get("ledger_case_registry_sha256")
        or audit.get("scientific_promotion_controls") != controls
    ):
        raise ValueError("Sources de l'audit et du consolide non apparentees.")
    lineage = audit.get("priority_selection_lineage")
    digest = str(audit.get("priority_selection_lineage_sha256") or "")
    _validate_priority_selection_lineage(lineage, declared_digest=digest)
    if (
        controls.get("priority_selection_lineage") != lineage
        or str(controls.get("priority_selection_lineage_sha256") or "") != digest
        or campaign.get("priority_selection_lineage") != lineage
        or str(campaign.get("priority_selection_lineage_sha256") or "") != digest
        or runner_manifest.get("priority_selection_lineage") != lineage
        or str(runner_manifest.get("priority_selection_lineage_sha256") or "") != digest
        or str(consolidation.get("priority_selection_lineage_sha256") or "") != digest
    ):
        raise ValueError("Lignee boundary divergente dans la surcouche.")
    runner_signature = str(runner_manifest.get("runner_signature") or "")
    plan_signature = str(runner_manifest.get("plan_signature") or "")
    if (
        not runner_signature
        or str(campaign.get("extension_runner_signature") or "") != runner_signature
        or str(consolidation.get("runner_manifest_sha256") or "")
        != source_runner_manifest_sha256
        or str(audit.get("source_runner_signature") or "") != runner_signature
        or not plan_signature
        or str(audit.get("source_plan_signature") or "") != plan_signature
        or str(
            source_hashes.get("plan/post_priority_extensions_plan_manifest.json") or ""
        )
        != str(runner_manifest.get("plan_manifest_sha256") or "")
        or str(consolidation.get("source_campaign_manifest_sha256") or "")
        != str(lineage.get("source_campaign_manifest_sha256") or "")
        or str(runner_manifest.get("source_campaign_manifest_sha256") or "")
        != str(lineage.get("source_campaign_manifest_sha256") or "")
    ):
        raise ValueError("Signatures plan/runner/campagne non apparentees.")
    if any(
        payload.get("promotion_allowed") is not False
        for payload in (runner_manifest, audit_manifest, controls)
    ):
        raise ValueError("Une source de surcouche revendique une promotion.")
    expected_legacy_sources = list(CONSOLIDATED_SMALL_SOURCE_FILES)
    expected_legacy_rankings = list(
        LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
    )
    if (
        controls.get("legacy_source_artifacts_not_scientifically_released")
        != expected_legacy_sources
        or controls.get("legacy_ranking_artifacts_not_scientifically_released")
        != expected_legacy_rankings
        or controls.get("legacy_ranking_display_allowed") is not False
        or controls.get("legacy_ranking_used_for_extension_interpretation") is not False
    ):
        raise ValueError("Les anciens classements ne sont pas neutralises.")


def validate_scientific_overlay(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).resolve()
    manifest_path = root / "scientific_overlay_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Manifeste de surcouche scientifique absent.")
    manifest = _read_json(manifest_path)
    if str(manifest.get("schema_version") or "") != OVERLAY_SCHEMA_VERSION:
        raise ValueError("Version de surcouche scientifique inconnue.")
    if str(manifest.get("status") or "") != "complete":
        raise ValueError("La surcouche scientifique n'est pas complete.")
    signature_payload = {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "builder_sha256",
            "source_consolidated_file_sha256",
            "source_audit_package_signature",
            "artifact_file_sha256",
            "legacy_source_artifacts_not_scientifically_released",
            "legacy_ranking_artifacts_not_scientifically_released",
            "legacy_ranking_display_allowed",
        )
    }
    if str(manifest.get("overlay_signature") or "") != _canonical_sha256(
        signature_payload
    ):
        raise ValueError("Signature canonique de surcouche invalide.")
    if str(manifest.get("builder_sha256") or "") != _sha256(Path(__file__).resolve()):
        raise ValueError("La surcouche ne vient pas du builder scientifique courant.")
    hashes = dict(manifest.get("artifact_file_sha256") or {})
    if (
        not hashes
        or "campaign_manifest.json" not in hashes
        or ("scientific_promotion_controls.json" not in hashes)
    ):
        raise ValueError("Inventaire de surcouche incomplet.")
    observed_files = {path.name for path in root.iterdir() if path.is_file()}
    expected_files = set(hashes) | {"scientific_overlay_manifest.json"}
    if observed_files != expected_files or any(
        path.is_dir() or path.is_symlink() for path in root.iterdir()
    ):
        raise ValueError(
            "Inventaire disque de la surcouche incomplet, excessif ou non regulier."
        )
    for name, expected in hashes.items():
        path = root / name
        if not path.is_file() or _sha256(path) != str(expected):
            raise ValueError(f"Empreinte de surcouche invalide: {name}")
    campaign = _read_json(root / "campaign_manifest.json")
    controls = _read_json(root / "scientific_promotion_controls.json")
    embedded_audit_manifest = _read_json(
        root / "extension_interpretation_audit_manifest.json"
    )
    embedded_audit = _read_json(root / "scientific_extension_interpretation_audit.json")
    embedded_artifact_hashes = embedded_audit_manifest.get("artifact_file_sha256") or {}
    if (
        str(manifest.get("source_audit_package_signature") or "")
        != str(embedded_audit_manifest.get("package_signature") or "")
        or set(embedded_artifact_hashes) != set(OUTPUT_FILES)
        or any(
            _sha256(root / str(name)) != str(expected)
            for name, expected in embedded_artifact_hashes.items()
        )
    ):
        raise ValueError("Paquet d'audit embarque divergent de la surcouche.")
    legacy_consolidation = _read_json(root / "legacy_consolidation_manifest.json")
    runner_manifest_for_lineage = _read_json(
        root / "post_priority_extension_runner_manifest.json"
    )
    source_consolidated_hashes = manifest.get("source_consolidated_file_sha256") or {}
    (
        legacy_source_hashes,
        legacy_extension_hashes,
        _legacy_extension_manifest_hashes,
    ) = _validated_consolidation_manifest_payload(legacy_consolidation)
    expected_original_names = (
        set(legacy_source_hashes)
        | set(legacy_extension_hashes)
        | {"campaign_manifest.json", "consolidation_manifest.json"}
    )
    if (
        not isinstance(source_consolidated_hashes, dict)
        or set(source_consolidated_hashes) != expected_original_names
        or _sha256(root / "legacy_consolidation_manifest.json")
        != str(source_consolidated_hashes.get("consolidation_manifest.json") or "")
        or str(source_consolidated_hashes.get("campaign_manifest.json") or "")
        != str(legacy_consolidation.get("consolidated_campaign_manifest_sha256") or "")
        or any(
            str(source_consolidated_hashes.get(name) or "") != str(expected)
            for name, expected in {
                **legacy_source_hashes,
                **legacy_extension_hashes,
            }.items()
        )
    ):
        raise ValueError("Manifeste de consolidation source non apparente.")
    unchanged_names = set(legacy_source_hashes) | (
        set(legacy_extension_hashes) - set(NEUTRALIZED_CONSOLIDATED_MANIFEST_FILES)
    )
    if any(
        not (root / name).is_file()
        or _sha256(root / name) != str(source_consolidated_hashes.get(name) or "")
        for name in unchanged_names
    ):
        raise ValueError("Un fichier consolide non neutralise a ete modifie.")
    _validate_overlay_lineage_contract(
        campaign=campaign,
        consolidation=legacy_consolidation,
        runner_manifest=runner_manifest_for_lineage,
        audit_manifest=embedded_audit_manifest,
        audit=embedded_audit,
        controls=controls,
        source_runner_manifest_sha256=str(
            source_consolidated_hashes.get(
                "post_priority_extension_runner_manifest.json"
            )
            or ""
        ),
    )
    if (
        campaign.get("scientific_interpretation_overlay_applied") is not True
        or campaign.get("legacy_runner_promotion_aliases_neutralized") is not True
        or campaign.get("promotion_allowed") is not False
        or campaign.get("legacy_source_artifacts_not_scientifically_released")
        != list(CONSOLIDATED_SMALL_SOURCE_FILES)
        or campaign.get("legacy_ranking_artifacts_not_scientifically_released")
        != list(LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED)
        or campaign.get("legacy_ranking_display_allowed") is not False
        or campaign.get("legacy_ranking_used_for_extension_interpretation") is not False
        or manifest.get("legacy_source_artifacts_not_scientifically_released")
        != list(CONSOLIDATED_SMALL_SOURCE_FILES)
        or manifest.get("legacy_ranking_artifacts_not_scientifically_released")
        != list(LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED)
        or manifest.get("legacy_ranking_display_allowed") is not False
    ):
        raise ValueError("Le manifeste consolide n'a pas neutralise les anciens alias.")
    states = campaign.get("extensions_required") or {}
    if any(
        isinstance(state, dict) and state.get("pass") is not False
        for state in states.values()
    ):
        raise ValueError("Un ancien alias extension.pass reste actif.")
    for field in (
        "global_priority_temporal_robustness_evaluable",
        "global_four_cause_priority_robustness_evaluable",
        "global_network_priority_robustness_evaluable",
        "promotion_allowed",
    ):
        if controls.get(field) is not False:
            raise ValueError(f"Controle de surcouche non fail-closed: {field}")
    if campaign.get("network_recovery_metric_status") != (
        "excluded_invalid_common_window"
    ):
        raise ValueError("La surcouche n'exclut pas la recuperation reseau invalide.")
    extension_manifest_names = (
        "multi_lane_supplier_common_cause_manifest.json",
        "temporal_robustness_manifest.json",
        "priority_four_business_causes_manifest.json",
        "causal_lot_attribution_manifest.json",
    )
    for name in extension_manifest_names:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"Manifeste canonique d'extension absent: {name}")
        payload = _read_json(path)
        if (
            payload.get("release_gate_pass") is not False
            or "legacy_runner_release_gate_value" not in payload
            or payload.get("release_gate_semantics")
            != "completion_and_flow_only_not_scientific_robustness"
        ):
            raise ValueError(f"Alias release_gate_pass non neutralise dans {name}.")
    runner_manifest_path = root / "post_priority_extension_runner_manifest.json"
    if not runner_manifest_path.is_file():
        raise FileNotFoundError("Copie scientifique du manifeste runner absente.")
    runner_manifest = _read_json(runner_manifest_path)
    if (
        runner_manifest.get("promotion_allowed") is not False
        or runner_manifest.get("causal_lot_release_gate_pass") is not False
        or any(
            value is not False
            for value in (runner_manifest.get("extension_release_gates") or {}).values()
        )
    ):
        raise ValueError("Les aliases du manifeste runner ne sont pas neutralises.")
    return {
        "valid": True,
        "status": "complete",
        "overlay_signature": str(manifest.get("overlay_signature") or ""),
        "promotion_allowed": False,
    }


def build_scientific_overlay(
    *,
    consolidated_dir: str | Path,
    audit_dir: str | Path,
    output_dir: str | Path,
) -> Path:
    """Create a corrected copy of a compact consolidation without mutating it."""

    source_root = Path(consolidated_dir).resolve()
    audit_root = Path(audit_dir).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"Le dossier de surcouche existe deja: {destination}")
    validate_audit_package(audit_root)
    validated_source = _validate_consolidated_source(source_root)
    campaign_path = source_root / "campaign_manifest.json"
    consolidation_path = source_root / "consolidation_manifest.json"
    runner_manifest_path = source_root / "post_priority_extension_runner_manifest.json"
    if (
        not campaign_path.is_file()
        or not consolidation_path.is_file()
        or not runner_manifest_path.is_file()
    ):
        raise FileNotFoundError(
            "Le consolide source doit contenir campaign_manifest.json et "
            "consolidation_manifest.json."
        )
    for protected in (source_root, audit_root):
        try:
            destination.relative_to(protected)
        except ValueError:
            pass
        else:
            raise ValueError("La surcouche doit etre publiee hors de ses sources.")
    source_files = {path.name: path for path in source_root.iterdir() if path.is_file()}
    oversized = [
        name
        for name, path in source_files.items()
        if path.stat().st_size > 25 * 1024 * 1024
    ]
    if oversized:
        raise ValueError(
            "Fichier trop volumineux pour la surcouche: " + ", ".join(oversized)
        )
    source_hashes_before = {
        name: _sha256(path) for name, path in sorted(source_files.items())
    }
    audit_manifest = _read_json(
        audit_root / "extension_interpretation_audit_manifest.json"
    )
    audit_payload = _read_json(
        audit_root / "scientific_extension_interpretation_audit.json"
    )
    controls = _read_json(audit_root / "scientific_promotion_controls.json")
    source_campaign = validated_source["campaign"]
    source_consolidation = validated_source["manifest"]
    source_runner_manifest = validated_source["runner_manifest"]
    _validate_overlay_lineage_contract(
        campaign=source_campaign,
        consolidation=source_consolidation,
        runner_manifest=source_runner_manifest,
        audit_manifest=audit_manifest,
        audit=audit_payload,
        controls=controls,
        source_runner_manifest_sha256=_sha256(runner_manifest_path),
    )
    campaign = _neutralized_campaign_manifest(source_campaign, controls)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    try:
        for name, path in source_files.items():
            if name in {"campaign_manifest.json", "consolidation_manifest.json"}:
                continue
            if name in {
                "multi_lane_supplier_common_cause_manifest.json",
                "temporal_robustness_manifest.json",
                "priority_four_business_causes_manifest.json",
                "causal_lot_attribution_manifest.json",
                "post_priority_extension_runner_manifest.json",
            }:
                _write_json(
                    staging / name,
                    _neutralized_runner_manifest_copy(name, _read_json(path), controls),
                )
            else:
                shutil.copy2(path, staging / name)
        shutil.copy2(consolidation_path, staging / "legacy_consolidation_manifest.json")
        for name in (*OUTPUT_FILES, "extension_interpretation_audit_manifest.json"):
            shutil.copy2(audit_root / name, staging / name)
        _write_json(staging / "campaign_manifest.json", campaign)
        _write_json(staging / "scientific_promotion_controls.json", controls)
        artifact_names = sorted(
            path.name for path in staging.iterdir() if path.is_file()
        )
        artifact_hashes = {name: _sha256(staging / name) for name in artifact_names}
        signature_payload = {
            "schema_version": OVERLAY_SCHEMA_VERSION,
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "source_consolidated_file_sha256": source_hashes_before,
            "source_audit_package_signature": str(
                audit_manifest.get("package_signature") or ""
            ),
            "artifact_file_sha256": artifact_hashes,
            "legacy_source_artifacts_not_scientifically_released": list(
                CONSOLIDATED_SMALL_SOURCE_FILES
            ),
            "legacy_ranking_artifacts_not_scientifically_released": list(
                LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
            ),
            "legacy_ranking_display_allowed": False,
        }
        manifest = {
            **signature_payload,
            "status": "complete",
            "overlay_signature": _canonical_sha256(signature_payload),
            "source_consolidated_dir": str(source_root),
            "source_audit_dir": str(audit_root),
            "output_dir": str(destination),
            "source_consolidated_mutated": False,
            "source_audit_mutated": False,
            "legacy_promotion_aliases_neutralized": True,
            "promotion_allowed": False,
            "large_files_copied": False,
        }
        _write_json(staging / "scientific_overlay_manifest.json", manifest)
        source_hashes_after = {
            name: _sha256(path) for name, path in sorted(source_files.items())
        }
        if source_hashes_after != source_hashes_before:
            raise RuntimeError("Le consolide source a change pendant la surcouche.")
        validate_audit_package(audit_root)
        validate_scientific_overlay(staging)
        staging.replace(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    validate_scientific_overlay(destination)
    return destination


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--validate", type=Path, default=None)
    parser.add_argument("--consolidated-dir", type=Path, default=None)
    parser.add_argument("--audit-dir", type=Path, default=None)
    parser.add_argument("--validate-overlay", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate is not None:
        result = validate_audit_package(args.validate)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.validate_overlay is not None:
        result = validate_scientific_overlay(args.validate_overlay)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.consolidated_dir is not None or args.audit_dir is not None:
        if (
            args.consolidated_dir is None
            or args.audit_dir is None
            or args.output_dir is None
        ):
            raise ValueError(
                "--consolidated-dir, --audit-dir et --output-dir sont requis ensemble."
            )
        output = build_scientific_overlay(
            consolidated_dir=args.consolidated_dir,
            audit_dir=args.audit_dir,
            output_dir=args.output_dir,
        )
        print(
            json.dumps(
                {"status": "complete", "overlay_dir": str(output)},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0
    if args.runner_dir is None or args.output_dir is None:
        raise ValueError(
            "--runner-dir et --output-dir sont requis pour construire l'audit."
        )
    output = build_audit_package(
        runner_dir=args.runner_dir,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {"status": "complete", "audit_dir": str(output)},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
