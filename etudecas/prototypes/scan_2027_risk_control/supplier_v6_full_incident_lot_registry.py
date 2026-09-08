#!/usr/bin/env python3
"""Publier un registre V6 additif et lié aux preuves d'incidents et de lots.

La campagne fournisseur contient 3 240 tests conditionnels d'incident, sans
journal détaillé des lots. De zéro à trois situations représentatives peuvent
ensuite être rejouées avec ce journal. Le post-traitement sépare les preuves :

* chaque répétition, état, voie et mécanisme reste lié à la métrique signée ;
* les 108 synthèses proviennent de l'agrégat officiel finalisé ;
* chaque ligne de généalogie native reste limitée à son rejeu exact.

Aucun moteur de simulation n'est importé ou exécuté. Les artefacts de campagne,
de rejeu et d'actions ne sont jamais modifiés. La sortie doit être un dossier
neuf et tout écrasement est refusé.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v4 as finalizer_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as replay_v4,
)


SCHEMA_VERSION = "etudecas.supplier_v6_full_incident_lot_registry.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"

EXPOSURE_CSV = "registre_expositions_incidents_3240.csv"
CELL_CSV = "cellules_incidents_108.csv"
GENEALOGY_CSV = "genealogies_rejeux_detaillees.csv"
J0_CSV = "contexte_j0_rejeux.csv"
JSON_FILE = "registre_incidents_lots_v6.json"
HTML_FILE = "OUVRIR_REGISTRE_INCIDENTS_LOTS_V6.html"
MANIFEST_FILE = "registre_incidents_lots_v6.manifest.json"

STATES = ("op_100", "op_93", "op_80")
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
EXPECTED_SEEDS = 30
EXPECTED_SEED_IDS = tuple(finalizer_v4.EXPECTED_SEEDS)
EXPECTED_LANES = 18
EXPECTED_BASELINE_ROWS = 3 * EXPECTED_SEEDS
EXPECTED_INCIDENT_ROWS = 3 * EXPECTED_LANES * len(MECHANISMS) * EXPECTED_SEEDS
EXPECTED_TOTAL_ROWS = EXPECTED_BASELINE_ROWS + EXPECTED_INCIDENT_ROWS
EXPECTED_CELL_ROWS = 3 * EXPECTED_LANES * len(MECHANISMS)
EPS = 1e-9
MECHANISM_CONTRACT = {
    "transport_delay": {
        "risk_type": "lead_time_extra_days",
        "risk_value": 120.0,
        "arrival_delay_days": 120,
    },
    "planned_delivery_shortfall": {
        "risk_type": "reliability",
        "risk_value": 0.5,
        "arrival_delay_days": 0,
    },
}
ACTION_CONTROL_MODE = "boucle ouverte dans les analyses d'actions existantes"
ACTION_EXPLANATION = (
    "Les rejeux statistiques d'actions imposent lot_trace_enabled=false. Aucun gain "
    "d'action ne peut donc être attribué à un lot, une campagne ou un client précis."
)

TRACE_FILES = {
    "shipment_to_material_receipt": "shipment_to_mp_lots.csv",
    "consumption_and_wip": "exposed_consumption_wip.csv",
    "finished_lot_release": "exposed_finished_lots.csv",
    "aggregated_client_contact": "exposed_client_events.csv",
}
EVENT_DAY_KINDS = {
    "shipment_to_material_receipt": (
        "jour de décision d'expédition; le jour de réception n'est pas publié dans cette table"
    ),
    "consumption_and_wip": "jour de consommation et d'encours",
    "finished_lot_release": "jour de libération du lot fini",
    "aggregated_client_contact": "jour de contact avec le nœud client agrégé",
}
EXPECTED_J0_METRICS = frozenset(
    {
        "component_stock",
        "production_released",
        "wip",
        "demand",
        "served_on_due",
        "backlog",
    }
)
J0_MEASUREMENT_KINDS = {
    "component_stock": "niveau de fin de journée",
    "production_released": "flux cumulé sur la journée",
    "wip": "niveau de fin de journée",
    "demand": "flux cumulé sur la journée",
    "served_on_due": "flux cumulé sur la journée",
    "backlog": "niveau de fin de journée",
}
J0_OBSERVATION_CONVENTION = (
    "Valeur de la série quotidienne au premier jour de la fenêtre de risque; "
    "ce n'est pas un instantané pré-incident ni une valeur au début de la journée."
)


class IncidentLotRegistryError(ValueError):
    """The finalized evidence cannot support the requested registry."""


EXPOSURE_SOURCE_FIELDS = (
    "schema_version",
    "campaign_signature",
    "engine_sha256",
    "shard_id",
    "case_key",
    "case_signature",
    "baseline_case_signature",
    "warmup_core_state_sha256",
    "summary_sha256",
    "operating_point_id",
    "operating_point_service_pct",
    "simulation_days",
    "state_evaluation_days",
    "stage",
    "mechanism",
    "seed",
    "status",
    "valid",
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "target_product_id",
    "target_status",
    "target_reference_kind",
    "target_shipment_count",
    "target_window_start_day",
    "target_window_end_day",
    "target_window_days",
    "target_planned_qty",
    "target_expected_delivered_qty",
    "target_uom",
    "state_comparison_valid",
    "seed_cross_state_exposure_comparable",
    "comparable_campaign_seed_count",
    "required_comparable_seed_count",
    "impact_window_start_day",
    "impact_window_end_day",
    "impact_window_days",
    "causal_window_start_day",
    "causal_window_end_day",
    "causal_window_days",
    "causal_window_defined",
    "risk_type",
    "risk_value",
    "risk_start_day",
    "risk_end_day",
    "risk_applied_row_count",
    "risk_applied_event_count",
    "incident_physically_exercised",
    "incident_shipment_count",
    "incident_affected_pulled_qty",
    "incident_affected_shipped_qty",
    "quantity_shortfall_qty",
    "arrival_delay_days",
    "incident_effective_dose_qty",
    "incident_effective_dose_qty_days",
    "baseline_impact_service_268091_pct",
    "baseline_impact_service_268967_pct",
    "baseline_impact_service_global_pct",
    "impact_service_268091_pct",
    "impact_service_268967_pct",
    "impact_service_global_pct",
    "impact_service_loss_268091_pp",
    "impact_service_loss_268967_pp",
    "impact_service_loss_global_pp",
    "impact_service_loss_fed_product_pp",
    "impact_on_due_loss_fed_product_qty",
    "impact_on_due_loss_global_qty",
    "impact_backlog_qty_days_delta",
    "impact_backlog_qty_days_per_demand_unit",
    "impact_max_backlog_qty_delta",
    "impact_production_loss_fed_product_qty",
    "impact_production_loss_fed_product_share_of_demand",
    "causal_service_loss_fed_product_pp",
    "causal_service_loss_global_pp",
    "causal_on_due_loss_fed_product_qty",
    "causal_backlog_qty_days_delta",
    "causal_backlog_qty_days_per_demand_unit",
    "causal_max_backlog_qty_delta",
    "causal_production_loss_fed_product_qty",
    "causal_production_loss_fed_product_share_of_demand",
)

EXPOSURE_BOOLEAN_FIELDS = frozenset(
    {
        "valid",
        "state_comparison_valid",
        "seed_cross_state_exposure_comparable",
        "causal_window_defined",
        "incident_physically_exercised",
    }
)
EXPOSURE_INTEGER_FIELDS = frozenset(
    {
        "simulation_days",
        "state_evaluation_days",
        "seed",
        "target_shipment_count",
        "target_window_start_day",
        "target_window_end_day",
        "target_window_days",
        "comparable_campaign_seed_count",
        "required_comparable_seed_count",
        "impact_window_start_day",
        "impact_window_end_day",
        "impact_window_days",
        "causal_window_start_day",
        "causal_window_end_day",
        "causal_window_days",
        "risk_start_day",
        "risk_end_day",
        "risk_applied_row_count",
        "risk_applied_event_count",
        "incident_shipment_count",
        "arrival_delay_days",
    }
)
EXPOSURE_NUMERIC_FIELDS = frozenset(
    set(EXPOSURE_INTEGER_FIELDS)
    | {
        "operating_point_service_pct",
        "target_planned_qty",
        "target_expected_delivered_qty",
        "risk_value",
        "incident_affected_pulled_qty",
        "incident_affected_shipped_qty",
        "quantity_shortfall_qty",
        "incident_effective_dose_qty",
        "incident_effective_dose_qty_days",
        "baseline_impact_service_268091_pct",
        "baseline_impact_service_268967_pct",
        "baseline_impact_service_global_pct",
        "impact_service_268091_pct",
        "impact_service_268967_pct",
        "impact_service_global_pct",
        "impact_service_loss_268091_pp",
        "impact_service_loss_268967_pp",
        "impact_service_loss_global_pp",
        "impact_service_loss_fed_product_pp",
        "impact_on_due_loss_fed_product_qty",
        "impact_on_due_loss_global_qty",
        "impact_backlog_qty_days_delta",
        "impact_backlog_qty_days_per_demand_unit",
        "impact_max_backlog_qty_delta",
        "impact_production_loss_fed_product_qty",
        "impact_production_loss_fed_product_share_of_demand",
        "causal_service_loss_fed_product_pp",
        "causal_service_loss_global_pp",
        "causal_on_due_loss_fed_product_qty",
        "causal_backlog_qty_days_delta",
        "causal_backlog_qty_days_per_demand_unit",
        "causal_max_backlog_qty_delta",
        "causal_production_loss_fed_product_qty",
        "causal_production_loss_fed_product_share_of_demand",
    }
)

EXPOSURE_PREFIX_FIELDS = (
    "evidence_label",
    "interpretation",
    "mrp_requirement_mode",
    "effective_exposure_dose",
    "effective_exposure_dose_unit",
    "detailed_replay_selected",
    "genealogy_available",
    "descendant_finished_lots_available",
    "aggregated_client_contact_available",
    "detailed_replay_dossier_id",
    "genealogy_scope",
    "action_lot_trace_available",
)
EXPOSURE_OUTPUT_FIELDS = EXPOSURE_PREFIX_FIELDS + EXPOSURE_SOURCE_FIELDS

CELL_REQUIRED_FIELDS = frozenset(
    {
        "operating_point_id",
        "operating_point_service_pct",
        "operating_point_service_268091_pct",
        "operating_point_service_268967_pct",
        "mechanism",
        "target_product_id",
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "paired_repetition_count",
        "physical_exercise_count",
        "physical_exercise_rate",
        "zero_exposure_repetition_count",
        "target_planned_qty_mean",
        "target_shipment_count_mean",
        "impact_service_loss_fed_product_pp_mean",
        "impact_service_loss_fed_product_pp_median",
        "impact_service_loss_fed_product_pp_p10",
        "impact_service_loss_fed_product_pp_p90",
        "impact_service_loss_fed_product_pp_ci95_low",
        "impact_service_loss_fed_product_pp_ci95_high",
        "impact_service_loss_fed_product_pp_positive_effect_count",
        "impact_service_loss_fed_product_pp_positive_effect_rate",
        "impact_service_loss_global_pp_mean",
        "impact_production_loss_fed_product_qty_mean",
        "impact_backlog_qty_days_delta_mean",
        "impact_backlog_qty_days_per_demand_unit_mean",
    }
)

CELL_PREFIX_FIELDS = (
    "evidence_label",
    "mrp_requirement_mode",
    "detailed_replay_selected",
    "genealogy_replay_available",
    "genealogy_available_repetition_count",
    "genealogy_coverage_of_30_repetitions",
    "descendant_finished_lots_available",
    "aggregated_client_contact_available",
    "detailed_replay_dossier_id",
    "action_lot_trace_available",
)

GENEALOGY_FIELDS = (
    "dossier_id",
    "operating_point_id",
    "mechanism",
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "target_product_id",
    "representative_seed",
    "genealogy_stage",
    "source_relative_path",
    "source_row_number",
    "incident_event_id",
    "incident_j0_day",
    "event_day",
    "event_day_kind",
    "days_from_incident_j0",
    "is_simulation_day_zero",
    "is_incident_j0",
    "shipment_id",
    "shipment_ids",
    "risk_decision_day",
    "source_lot_id",
    "source_node_id",
    "source_item_id",
    "receipt_lot_id",
    "receipt_node_id",
    "receipt_item_id",
    "parent_qty",
    "child_qty",
    "material_lot_id",
    "consumption_day",
    "consumed_qty",
    "campaign_id",
    "batch_id",
    "wip_start_qty",
    "wip_end_qty",
    "campaign_wip_qty_end_of_run",
    "campaign_blocked_lot_qty",
    "released_lot_id_same_day",
    "released_qty_same_day",
    "finished_lot_id",
    "release_day",
    "released_qty",
    "exposed_parent_lot_ids",
    "client_lot_id",
    "client_day",
    "client_node_id",
    "service_event_qty_on_contacted_lot",
    "uom",
    "claim",
    "raw_record_json",
)

J0_FIELDS = (
    "dossier_id",
    "operating_point_id",
    "mechanism",
    "lane_id",
    "representative_seed",
    "incident_j0_day",
    "metric",
    "measurement_kind",
    "observation_convention",
    "is_pre_incident_snapshot",
    "baseline_value_at_incident_j0",
    "incident_value_at_incident_j0",
    "delta_incident_minus_baseline_at_incident_j0",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _boolean(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    normalised = _text(value).casefold()
    if normalised in {"1", "true", "yes", "oui"}:
        return True
    if normalised in {"0", "false", "no", "non"}:
        return False
    raise IncidentLotRegistryError(f"Booléen officiel invalide : {label}")


def _is_sha256(value: Any) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", _text(value).casefold()) is not None


def _number(value: Any, *, label: str, optional: bool = False) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if optional:
            return None
        raise IncidentLotRegistryError(f"Valeur numérique absente : {label}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise IncidentLotRegistryError(f"Valeur numérique invalide : {label}") from exc
    if not math.isfinite(result):
        raise IncidentLotRegistryError(f"Valeur non finie : {label}")
    return result


def _integer(value: Any, *, label: str, optional: bool = False) -> int | None:
    number = _number(value, label=label, optional=optional)
    if number is None:
        return None
    rounded = round(number)
    if not math.isclose(number, rounded, rel_tol=0.0, abs_tol=EPS):
        raise IncidentLotRegistryError(f"Entier attendu : {label}")
    return int(rounded)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IncidentLotRegistryError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise IncidentLotRegistryError(f"Objet JSON attendu : {path}")
    return payload


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or ())
            if not fields:
                raise IncidentLotRegistryError(f"CSV sans en-tête : {path}")
            return fields, list(reader)
    except OSError as exc:
        raise IncidentLotRegistryError(f"CSV illisible : {path}") from exc


def _require_fields(
    row: Mapping[str, Any],
    fields: Sequence[str] | set[str] | frozenset[str],
    *,
    label: str,
) -> None:
    missing = sorted(field for field in fields if field not in row)
    if missing:
        raise IncidentLotRegistryError(
            f"Colonnes absentes dans {label} : {', '.join(missing)}"
        )


def _typed_exposure_value(field: str, value: Any) -> Any:
    if field in EXPOSURE_BOOLEAN_FIELDS:
        return _boolean(value, label=field)
    if field in EXPOSURE_INTEGER_FIELDS:
        return _integer(value, label=field)
    if field in EXPOSURE_NUMERIC_FIELDS:
        return _number(
            value,
            label=field,
            optional=field
            in {"incident_effective_dose_qty", "incident_effective_dose_qty_days"},
        )
    return _text(value)


def _typed_aggregate_value(field: str, value: Any) -> Any:
    text = _text(value)
    if text == "":
        return None
    if field in {
        "operating_point_id",
        "mechanism",
        "target_product_id",
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_uom",
        "effective_exposure_dose_unit",
        "priority_status",
    } or field.endswith(("_id", "_sha256", "_unit", "_status", "_criterion")):
        return text
    if text.casefold() in {"true", "false"}:
        return text.casefold() == "true"
    try:
        value_as_number = float(text)
    except ValueError:
        return text
    if not math.isfinite(value_as_number):
        raise IncidentLotRegistryError(f"Agrégat non fini : {field}")
    if value_as_number.is_integer() and any(
        token in field
        for token in ("count", "position", "rank_min", "rank_max", "_days")
    ):
        return int(value_as_number)
    return value_as_number


def _normalise_item(value: Any) -> str:
    return _text(value).removeprefix("item:")


def _identity_value(field: str, value: Any) -> str:
    if field in {"item_id", "target_product_id"}:
        return _normalise_item(value)
    return _text(value)


def _same_identity(field: str, left: Any, right: Any) -> bool:
    return _identity_value(field, left) == _identity_value(field, right)


def _linear_quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered or not 0.0 <= probability <= 1.0:
        raise IncidentLotRegistryError("Quantile non calculable")
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    share = position - lower
    return ordered[lower] * (1.0 - share) + ordered[upper] * share


def _cell_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _text(row.get("operating_point_id")),
        _text(row.get("mechanism")),
        _text(row.get("lane_id")),
    )


def _replay_key(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        _text(row.get("operating_point_id")),
        _text(row.get("mechanism")),
        _text(row.get("lane_id")),
        int(_integer(row.get("representative_seed"), label="representative_seed")),
    )


def _validate_campaign_finalization_contract(validation: Mapping[str, Any]) -> None:
    expected = validation.get("expected_contract")
    checks = validation.get("comparability_checks")
    signed = validation.get("signed_case_evidence")
    statistics = validation.get("statistics")
    required_checks = {
        "complete_3x18x2x30_matrix",
        "same_repetitions_in_every_cell",
        "same_engine_sha256",
        "same_campaign_signature",
        "lane_identity_invariant",
        "baseline_pairing_complete",
        "paired_warmup_state_identical",
        "shipment_set_and_incident_trace_proven",
        "business_360_and_causal_windows_fully_observed",
        "all_3330_metrics_reconstructed_from_signed_case_evidence",
    }
    if (
        validation.get("schema_version") != finalizer_v4.SCHEMA_VERSION
        or validation.get("status") != "complete_validated"
        or not isinstance(expected, Mapping)
        or not isinstance(checks, Mapping)
        or not isinstance(signed, Mapping)
        or not isinstance(statistics, Mapping)
        or not _is_sha256(validation.get("campaign_signature"))
        or _integer(
            expected.get("operating_point_count"), label="operating_point_count"
        )
        != len(STATES)
        or _integer(expected.get("incident_row_count"), label="incident_row_count")
        != EXPECTED_INCIDENT_ROWS
        or _integer(expected.get("baseline_row_count"), label="baseline_row_count")
        != EXPECTED_BASELINE_ROWS
        or _integer(expected.get("lane_count"), label="lane_count") != EXPECTED_LANES
        or _integer(
            expected.get("paired_repetition_count"), label="paired_repetition_count"
        )
        != EXPECTED_SEEDS
        or tuple(expected.get("repetition_ids") or ()) != EXPECTED_SEED_IDS
        or expected.get("mechanisms") != list(MECHANISMS)
        or expected.get("operating_point_degradation_family")
        != "balanced_product_supplier_planned_lead"
        or expected.get("operating_point_degradation_scope")
        != "planned_supplier_lead_offsets_by_finished_product_feed"
        or _integer(
            expected.get("supplier_disruption_window_days"),
            label="supplier_disruption_window_days",
        )
        != 42
        or _integer(expected.get("business_window_days"), label="business_window_days")
        != 360
        or expected.get("adaptive_horizons") is not True
        or _integer(
            expected.get("lot_replay_dossier_maximum"),
            label="lot_replay_dossier_maximum",
        )
        != 3
        or expected.get("lot_replay_forced_top3") is not False
        or expected.get("all_lots_traced_claimed") is not False
        or expected.get("quality_branch_included") is not False
        or expected.get("availability_incident_included") is not False
        or any(checks.get(field) is not True for field in required_checks)
        or checks.get("all_lots_traced") is not False
        or _integer(
            checks.get("quality_or_availability_incident_count"),
            label="quality_or_availability_incident_count",
        )
        != 0
        or signed.get("status") != "complete_reconstructed"
        or _integer(signed.get("case_count"), label="signed case count")
        != EXPECTED_TOTAL_ROWS
        or _integer(signed.get("baseline_case_count"), label="signed baseline count")
        != EXPECTED_BASELINE_ROWS
        or _integer(signed.get("incident_case_count"), label="signed incident count")
        != EXPECTED_INCIDENT_ROWS
        or statistics.get("primary_ranking_metric")
        != "impact_service_loss_fed_product_pp"
        or statistics.get("primary_window") != "fixed_360_day_business_envelope"
        or statistics.get("confidence_interval")
        != "paired non-parametric bootstrap percentile interval"
        or _integer(
            statistics.get("bootstrap_replicates"), label="bootstrap_replicates"
        )
        != 10_000
        or statistics.get("forced_top3") is not False
        or validation.get("historical_incident_probability_estimated") is not False
        or validation.get("industrial_supplier_criticality_claimed") is not False
    ):
        raise IncidentLotRegistryError(
            "La finalisation officielle ne prouve pas la matrice 3×18×2×30 attendue"
        )


def _validated_official_cells(
    *, results_dir: Path, validation: Mapping[str, Any]
) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    path = (results_dir / "lane_statistics.csv").resolve()
    declared = (validation.get("outputs") or {}).get(path.name)
    if not isinstance(declared, Mapping) or not path.is_file():
        raise IncidentLotRegistryError("Agrégat officiel lane_statistics.csv absent")
    digest = sha256_file(path)
    if digest != _text(declared.get("sha256")):
        raise IncidentLotRegistryError("Empreinte lane_statistics.csv différente")
    fields, rows = _read_csv(path)
    if (
        _integer(declared.get("row_count"), label="lane_statistics row_count")
        != len(rows)
        or len(rows) != EXPECTED_CELL_ROWS
    ):
        raise IncidentLotRegistryError("Les 108 cellules officielles sont incomplètes")
    return (
        fields,
        rows,
        {
            "path": str(path),
            "sha256": digest,
            "rowCount": len(rows),
        },
    )


def load_official_campaign(*, campaign_root: Path, results_dir: Path) -> dict[str, Any]:
    """Load finalized campaign data and validate every declared fingerprint."""

    try:
        context = physical_v5._load_campaign_context(  # noqa: SLF001
            campaign_root.resolve(), results_dir.resolve()
        )
        selection = physical_v5.validate_selected_dossiers_physically_exercised(
            campaign_root=campaign_root.resolve(), results_dir=results_dir.resolve()
        )
    except Exception as exc:
        raise IncidentLotRegistryError(
            f"Campagne finalisée officielle refusée : {exc}"
        ) from exc
    _validate_campaign_finalization_contract(context.validation)
    try:
        evidence = finalizer_v4.discover_inputs(
            campaign_root=campaign_root.resolve(),
            manifest_path=context.manifest_path,
            metrics_paths=context.metric_paths,
        )
        signed_context = finalizer_v4._validate_signed_context(  # noqa: SLF001
            evidence, context.manifest
        )
        reconstructed = finalizer_v4.validate_metrics_against_signed_case_evidence(
            campaign_root=campaign_root.resolve(),
            metrics_paths=evidence.metrics_paths,
            manifest=context.manifest,
        )
        paired, paired_validation = finalizer_v4.validate_and_pair(
            finalizer_v4._read_metrics(evidence.metrics_paths),  # noqa: SLF001
            signed_context,
        )
    except Exception as exc:
        raise IncidentLotRegistryError(
            f"Reconstruction des 3 330 preuves signées refusée : {exc}"
        ) from exc
    official_reconstruction = context.validation.get("signed_case_evidence") or {}
    if any(
        reconstructed.get(field) != official_reconstruction.get(field)
        for field in (
            "status",
            "case_count",
            "baseline_case_count",
            "incident_case_count",
            "evidence_index_sha256",
        )
    ) or any(
        paired_validation.get(field) != expected_count
        for field, expected_count in (
            ("baseline_row_count", EXPECTED_BASELINE_ROWS),
            ("incident_row_count", EXPECTED_INCIDENT_ROWS),
            ("total_row_count", EXPECTED_TOTAL_ROWS),
        )
    ):
        raise IncidentLotRegistryError(
            "La reconstruction actuelle des preuves diffère de la finalisation officielle"
        )
    cell_fields, cells, cell_binding = _validated_official_cells(
        results_dir=results_dir.resolve(), validation=context.validation
    )
    incident_rows = paired.to_dict(orient="records")
    if len(incident_rows) != EXPECTED_INCIDENT_ROWS:
        raise IncidentLotRegistryError(
            "Le registre source ne contient pas 3 240 incidents"
        )

    metrics_binding = {
        str(path): {
            "sha256": sha256_file(path),
            "rowCount": len(_read_csv(path)[1]),
        }
        for path in context.metric_paths
    }
    declared_metrics = context.validation.get("inputs", {}).get(
        "metrics_csv_sha256", {}
    )
    if sorted(record["sha256"] for record in metrics_binding.values()) != sorted(
        _text(value) for value in declared_metrics.values()
    ) or sum(record["rowCount"] for record in metrics_binding.values()) != (
        EXPECTED_TOTAL_ROWS
    ):
        raise IncidentLotRegistryError("La liste des empreintes métriques a changé")

    bindings = {
        "campaignManifest": {
            "path": str(context.manifest_path),
            "sha256": sha256_file(context.manifest_path),
            "campaignSignature": context.manifest.get("campaign_signature"),
        },
        "campaignValidation": {
            "path": str(context.validation_path),
            "sha256": sha256_file(context.validation_path),
            "evidenceIndexSha256": context.validation.get(
                "signed_case_evidence", {}
            ).get("evidence_index_sha256"),
        },
        "campaignMetrics": metrics_binding,
        "officialCellAggregate": cell_binding,
        "signedReplaySelection": {
            "path": str(context.selection_path),
            "sha256": sha256_file(context.selection_path),
            "selectionSignature": context.selection.get("selection_signature"),
            "selectedDossierCount": selection["selected_dossier_count"],
        },
    }
    return {
        "context": context,
        "incidentRows": incident_rows,
        "cellFields": cell_fields,
        "cellRows": cells,
        "selection": selection,
        "bindings": bindings,
    }


def _validate_exposure_identity(
    rows: Sequence[Mapping[str, Any]], *, lane_ids: set[str]
) -> None:
    seeds = {_integer(row.get("seed"), label="seed") for row in rows}
    keys = {
        (
            _text(row.get("operating_point_id")),
            _text(row.get("lane_id")),
            _text(row.get("mechanism")),
            _integer(row.get("seed"), label="seed"),
        )
        for row in rows
    }
    expected = {
        (state, lane, mechanism, seed)
        for state in STATES
        for lane in lane_ids
        for mechanism in MECHANISMS
        for seed in EXPECTED_SEED_IDS
    }
    case_keys = [_text(row.get("case_key")) for row in rows]
    case_signatures = [_text(row.get("case_signature")).casefold() for row in rows]
    baseline_by_pair: dict[tuple[str, int], set[str]] = defaultdict(set)
    warmup_by_pair: dict[tuple[str, int], set[str]] = defaultdict(set)
    shards_by_lane: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        pair = (
            _text(row.get("operating_point_id")),
            int(_integer(row.get("seed"), label="seed")),
        )
        baseline_by_pair[pair].add(_text(row.get("baseline_case_signature")).casefold())
        warmup_by_pair[pair].add(_text(row.get("warmup_core_state_sha256")).casefold())
        shards_by_lane[_text(row.get("lane_id"))].add(_text(row.get("shard_id")))
    baseline_signatures = {
        next(iter(signatures))
        for signatures in baseline_by_pair.values()
        if len(signatures) == 1
    }
    if (
        len(rows) != EXPECTED_INCIDENT_ROWS
        or seeds != set(EXPECTED_SEED_IDS)
        or len(keys) != len(rows)
        or keys != expected
        or any(
            _text(row.get("schema_version")) != finalizer_v4.INPUT_METRIC_SCHEMA_VERSION
            for row in rows
        )
        or len(set(case_keys)) != len(rows)
        or "" in case_keys
        or len(set(case_signatures)) != len(rows)
        or any(not _is_sha256(value) for value in case_signatures)
        or any(not _is_sha256(row.get("summary_sha256")) for row in rows)
        or len({_text(row.get("campaign_signature")) for row in rows}) != 1
        or any(not _is_sha256(row.get("campaign_signature")) for row in rows)
        or len({_text(row.get("engine_sha256")).casefold() for row in rows}) != 1
        or any(not _is_sha256(row.get("engine_sha256")) for row in rows)
        or len(baseline_by_pair) != EXPECTED_BASELINE_ROWS
        or any(len(signatures) != 1 for signatures in baseline_by_pair.values())
        or len(baseline_signatures) != EXPECTED_BASELINE_ROWS
        or any(not _is_sha256(value) for value in baseline_signatures)
        or not set(case_signatures).isdisjoint(baseline_signatures)
        or len(warmup_by_pair) != EXPECTED_BASELINE_ROWS
        or any(
            len(signatures) != 1 or not _is_sha256(next(iter(signatures), ""))
            for signatures in warmup_by_pair.values()
        )
        or set(shards_by_lane) != lane_ids
        or any(len(shards) != 1 or "" in shards for shards in shards_by_lane.values())
        or len({next(iter(shards)) for shards in shards_by_lane.values()})
        != EXPECTED_LANES
    ):
        raise IncidentLotRegistryError(
            "Preuves incomplètes : 3 états × 18 voies × 2 mécanismes × 30 répétitions "
            "et 90 références signées sont requis"
        )


def build_exposure_registry(
    *,
    incident_rows: Sequence[Mapping[str, Any]],
    lanes: Sequence[Mapping[str, Any]],
    requirement_modes: Mapping[str, str],
    selected_dossiers: Sequence[Mapping[str, Any]],
    replay_dossiers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build the complete 3,240-row register without inventing lot lineage."""

    lane_by_id = {_text(row.get("lane_id")): row for row in lanes}
    identity_fields = (
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
    )
    lane_identities = {
        tuple(_identity_value(field, row.get(field)) for field in identity_fields)
        for row in lanes
    }
    if (
        len(lanes) != EXPECTED_LANES
        or len(lane_by_id) != EXPECTED_LANES
        or len(lane_identities) != EXPECTED_LANES
        or any(not all(identity) for identity in lane_identities)
    ):
        raise IncidentLotRegistryError(
            "Le référentiel ne contient pas 18 voies uniques"
        )
    if (
        set(requirement_modes) != set(lane_by_id)
        or set(requirement_modes.values()) != {"dynamic_explicit", "static_explicit"}
        or sum(value == "dynamic_explicit" for value in requirement_modes.values()) != 2
        or sum(value == "static_explicit" for value in requirement_modes.values()) != 16
    ):
        raise IncidentLotRegistryError(
            "Les modes de besoin doivent couvrir exactement 2 voies dynamiques et 16 statiques"
        )
    _validate_exposure_identity(incident_rows, lane_ids=set(lane_by_id))
    selected_by_key = {_replay_key(row): row for row in selected_dossiers}
    replay_by_key = {_replay_key(row): row for row in replay_dossiers}
    selected_ids = [_text(row.get("dossier_id")) for row in selected_dossiers]
    replay_ids = [_text(row.get("dossier_id")) for row in replay_dossiers]
    incident_keys = {
        (
            _text(row.get("operating_point_id")),
            _text(row.get("mechanism")),
            _text(row.get("lane_id")),
            int(_integer(row.get("seed"), label="seed")),
        )
        for row in incident_rows
    }
    if (
        len(selected_dossiers) > 3
        or len(replay_dossiers) > 3
        or len(selected_by_key) != len(selected_dossiers)
        or len(replay_by_key) != len(replay_dossiers)
        or len(set(selected_ids)) != len(selected_ids)
        or len(set(replay_ids)) != len(replay_ids)
        or "" in selected_ids
        or "" in replay_ids
        or not set(selected_by_key).issubset(incident_keys)
        or not set(replay_by_key).issubset(incident_keys)
    ):
        raise IncidentLotRegistryError("Dossier de rejeu dupliqué")
    if not set(replay_by_key).issubset(selected_by_key):
        raise IncidentLotRegistryError(
            "Un rejeu disponible n'appartient pas à la sélection"
        )
    for key, replay in replay_by_key.items():
        selected = selected_by_key[key]
        if _text(replay.get("dossier_id")) != _text(selected.get("dossier_id")):
            raise IncidentLotRegistryError(
                "Le rejeu disponible ne porte pas l'identifiant du dossier sélectionné"
            )

    output: list[dict[str, Any]] = []
    for source in incident_rows:
        _require_fields(source, EXPOSURE_SOURCE_FIELDS, label="métrique incident")
        state, mechanism, lane_id = _cell_key(source)
        seed = int(_integer(source.get("seed"), label="seed"))
        if (
            state not in STATES
            or mechanism not in MECHANISMS
            or lane_id not in lane_by_id
        ):
            raise IncidentLotRegistryError("Identité état/voie/mécanisme inconnue")
        lane = lane_by_id[lane_id]
        for field in (
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "target_product_id",
        ):
            if not _same_identity(field, source.get(field), lane.get(field)):
                raise IncidentLotRegistryError(
                    f"Identité physique différente pour {lane_id}/{field}"
                )
        record = {
            field: _typed_exposure_value(field, source.get(field))
            for field in EXPOSURE_SOURCE_FIELDS
        }
        if record["stage"] != "incident" or record["valid"] is not True:
            raise IncidentLotRegistryError(
                "Une ligne non incidente ou invalide est présente"
            )
        mechanism_contract = MECHANISM_CONTRACT[mechanism]
        if (
            record["target_reference_kind"] != finalizer_v4.TARGET_REFERENCE_KIND
            or not record["target_status"].startswith("identified_")
            or record["state_evaluation_days"] != finalizer_v4.STATE_EVALUATION_DAYS
            or record["simulation_days"] < record["state_evaluation_days"]
            or record["target_window_days"] != 42
            or record["target_window_end_day"] - record["target_window_start_day"] + 1
            != 42
            or record["risk_start_day"] != record["target_window_start_day"]
            or record["risk_end_day"] != record["target_window_end_day"]
            or record["impact_window_start_day"] != record["target_window_start_day"]
            or record["impact_window_days"] != 360
            or record["impact_window_end_day"] - record["impact_window_start_day"] + 1
            != 360
            or record["impact_window_end_day"] >= record["simulation_days"]
            or record["causal_window_end_day"] - record["causal_window_start_day"] + 1
            != record["causal_window_days"]
            or record["causal_window_end_day"] >= record["simulation_days"]
            or record["risk_type"] != mechanism_contract["risk_type"]
            or not math.isclose(
                float(record["risk_value"]),
                float(mechanism_contract["risk_value"]),
                abs_tol=EPS,
                rel_tol=1e-9,
            )
            or record["arrival_delay_days"] != mechanism_contract["arrival_delay_days"]
            or record["required_comparable_seed_count"]
            != finalizer_v4.MIN_COMPARABLE_SEEDS
            or not 0 <= record["comparable_campaign_seed_count"] <= EXPECTED_SEEDS
        ):
            raise IncidentLotRegistryError(
                f"Contrat physique ou temporel différent : {state}/{lane_id}/{mechanism}/{seed}"
            )
        exercised = bool(record["incident_physically_exercised"])
        if record["status"] != ("valid" if exercised else "valid_no_exposure"):
            raise IncidentLotRegistryError(
                "Statut et exposition physique sont incohérents"
            )
        if mechanism == "transport_delay":
            dose = record["incident_effective_dose_qty_days"]
            if dose is None or not math.isclose(
                float(dose),
                120.0 * float(record["incident_affected_shipped_qty"]),
                abs_tol=EPS,
                rel_tol=1e-9,
            ):
                raise IncidentLotRegistryError("Dose de retard transport incohérente")
            dose_unit = "unité-jour de retard"
        else:
            dose = record["incident_effective_dose_qty"]
            if dose is None or not math.isclose(
                float(dose),
                float(record["quantity_shortfall_qty"]),
                abs_tol=EPS,
                rel_tol=1e-9,
            ):
                raise IncidentLotRegistryError(
                    "Dose de quantité non livrée incohérente"
                )
            dose_unit = "unité non livrée"
        if (float(dose) > EPS) != exercised:
            raise IncidentLotRegistryError(
                "Dose et drapeau d'exposition sont incohérents"
            )

        replay_key = (state, mechanism, lane_id, seed)
        selected = selected_by_key.get(replay_key)
        replay = replay_by_key.get(replay_key)
        if (selected is not None or replay is not None) and not exercised:
            raise IncidentLotRegistryError(
                "Un dossier détaillé doit correspondre à une répétition physiquement exposée"
            )
        if replay is not None:
            for field in (
                "supplier_id",
                "item_id",
                "dst_node_id",
                "target_product_id",
            ):
                if not _same_identity(field, replay.get(field), lane.get(field)):
                    raise IncidentLotRegistryError(
                        f"Identité du rejeu différente pour {lane_id}/{field}"
                    )
        trace_counts = (
            replay.get("trace_counts") or replay.get("traceCounts") or {}
            if replay
            else {}
        )
        record = {
            "evidence_label": "SIMULÉ",
            "interpretation": "hypothèse conditionnelle comparée à sa référence appariée",
            "mrp_requirement_mode": requirement_modes[lane_id],
            "effective_exposure_dose": float(dose),
            "effective_exposure_dose_unit": dose_unit,
            "detailed_replay_selected": selected is not None,
            "genealogy_available": replay is not None,
            "descendant_finished_lots_available": bool(
                replay and int(trace_counts.get("finished_lots", 0)) > 0
            ),
            "aggregated_client_contact_available": bool(
                replay and int(trace_counts.get("client_events", 0)) > 0
            ),
            "detailed_replay_dossier_id": _text(
                (replay or selected or {}).get("dossier_id")
            ),
            "genealogy_scope": (
                "généalogie native disponible pour ce rejeu exact"
                if replay
                else "aucun lot descendant : ligne de campagne agrégée sans journal détaillé des lots"
            ),
            "action_lot_trace_available": False,
            **record,
        }
        output.append(record)
    state_order = {value: index for index, value in enumerate(STATES)}
    mechanism_order = {value: index for index, value in enumerate(MECHANISMS)}
    return sorted(
        output,
        key=lambda row: (
            state_order[row["operating_point_id"]],
            row["lane_id"],
            mechanism_order[row["mechanism"]],
            row["seed"],
        ),
    )


def build_cell_registry(
    *,
    official_rows: Sequence[Mapping[str, Any]],
    exposures: Sequence[Mapping[str, Any]],
    requirement_modes: Mapping[str, str],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Decorate the 108 official aggregates and reconcile them with 3,240 rows."""

    by_cell: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in exposures:
        by_cell[_cell_key(row)].append(row)
    if len(by_cell) != EXPECTED_CELL_ROWS or any(
        len(rows) != EXPECTED_SEEDS for rows in by_cell.values()
    ):
        raise IncidentLotRegistryError(
            "Les expositions ne forment pas 108 cellules de 30"
        )

    if len(official_rows) != EXPECTED_CELL_ROWS:
        raise IncidentLotRegistryError(
            "Les agrégats officiels ne contiennent pas 108 lignes"
        )
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    official_field_order = list(official_rows[0]) if official_rows else []
    for source in official_rows:
        _require_fields(source, CELL_REQUIRED_FIELDS, label="agrégat officiel")
        key = _cell_key(source)
        if key in seen or key not in by_cell:
            raise IncidentLotRegistryError("Cellule officielle dupliquée ou inconnue")
        seen.add(key)
        rows = by_cell[key]
        first_exposure = rows[0]
        for identity_field in (
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "target_product_id",
        ):
            if not _same_identity(
                identity_field,
                source.get(identity_field),
                first_exposure.get(identity_field),
            ):
                raise IncidentLotRegistryError(
                    f"Identité de l'agrégat différente : {key}/{identity_field}"
                )
        if (
            int(_integer(source.get("paired_repetition_count"), label="paired count"))
            != 30
        ):
            raise IncidentLotRegistryError(
                "Une cellule officielle n'a pas 30 répétitions"
            )
        exercised = sum(bool(row["incident_physically_exercised"]) for row in rows)
        if (
            int(_integer(source.get("physical_exercise_count"), label="exercise count"))
            != exercised
        ):
            raise IncidentLotRegistryError(
                "Comptage d'exposition différent de l'agrégat"
            )
        zero_exposure = int(
            _integer(
                source.get("zero_exposure_repetition_count"),
                label="zero exposure count",
            )
        )
        exercise_rate = float(
            _number(source.get("physical_exercise_rate"), label="exercise rate")
        )
        positive_count = int(
            _integer(
                source.get("impact_service_loss_fed_product_pp_positive_effect_count"),
                label="positive effect count",
            )
        )
        positive_rate = float(
            _number(
                source.get("impact_service_loss_fed_product_pp_positive_effect_rate"),
                label="positive effect rate",
            )
        )
        p10 = float(
            _number(source.get("impact_service_loss_fed_product_pp_p10"), label="P10")
        )
        median = float(
            _number(
                source.get("impact_service_loss_fed_product_pp_median"),
                label="median",
            )
        )
        p90 = float(
            _number(source.get("impact_service_loss_fed_product_pp_p90"), label="P90")
        )
        ci_low = float(
            _number(
                source.get("impact_service_loss_fed_product_pp_ci95_low"),
                label="CI95 low",
            )
        )
        ci_high = float(
            _number(
                source.get("impact_service_loss_fed_product_pp_ci95_high"),
                label="CI95 high",
            )
        )
        service_losses = [
            float(row["impact_service_loss_fed_product_pp"]) for row in rows
        ]
        expected_positive_count = sum(value > EPS for value in service_losses)
        if (
            zero_exposure != EXPECTED_SEEDS - exercised
            or not math.isclose(
                exercise_rate, exercised / EXPECTED_SEEDS, abs_tol=EPS, rel_tol=1e-9
            )
            or positive_count != expected_positive_count
            or not math.isclose(
                positive_rate,
                positive_count / EXPECTED_SEEDS,
                abs_tol=EPS,
                rel_tol=1e-9,
            )
            or not p10 <= median + EPS
            or not median <= p90 + EPS
            or not math.isclose(
                p10,
                _linear_quantile(service_losses, 0.10),
                abs_tol=1e-7,
                rel_tol=1e-9,
            )
            or not math.isclose(
                median,
                _linear_quantile(service_losses, 0.50),
                abs_tol=1e-7,
                rel_tol=1e-9,
            )
            or not math.isclose(
                p90,
                _linear_quantile(service_losses, 0.90),
                abs_tol=1e-7,
                rel_tol=1e-9,
            )
            or ci_low > ci_high + EPS
        ):
            raise IncidentLotRegistryError(
                f"Dispersion ou fréquence officielle incohérente : {key}"
            )
        comparisons = {
            "target_planned_qty_mean": "target_planned_qty",
            "target_shipment_count_mean": "target_shipment_count",
            "impact_service_loss_fed_product_pp_mean": "impact_service_loss_fed_product_pp",
            "impact_service_loss_global_pp_mean": "impact_service_loss_global_pp",
            "impact_production_loss_fed_product_qty_mean": "impact_production_loss_fed_product_qty",
            "impact_backlog_qty_days_delta_mean": "impact_backlog_qty_days_delta",
            "impact_backlog_qty_days_per_demand_unit_mean": (
                "impact_backlog_qty_days_per_demand_unit"
            ),
        }
        for aggregate_field, exposure_field in comparisons.items():
            expected = sum(float(row[exposure_field]) for row in rows) / len(rows)
            actual = float(_number(source.get(aggregate_field), label=aggregate_field))
            if not math.isclose(actual, expected, abs_tol=1e-7, rel_tol=1e-9):
                raise IncidentLotRegistryError(
                    f"Agrégat officiel non réconcilié : {key}/{aggregate_field}"
                )
        replay_rows = [row for row in rows if row["genealogy_available"]]
        if len(replay_rows) > 1:
            raise IncidentLotRegistryError(
                "Plus d'un rejeu généalogique dans une cellule"
            )
        selected_rows = [row for row in rows if row["detailed_replay_selected"]]
        if len(selected_rows) > 1:
            raise IncidentLotRegistryError(
                "Plus d'une répétition sélectionnée dans une situation"
            )
        replay = replay_rows[0] if replay_rows else None
        selected = selected_rows[0] if selected_rows else None
        typed = {
            field: _typed_aggregate_value(field, source.get(field))
            for field in official_field_order
        }
        record = {
            "evidence_label": "SIMULÉ",
            "mrp_requirement_mode": requirement_modes[key[2]],
            "detailed_replay_selected": selected is not None,
            "genealogy_replay_available": replay is not None,
            "genealogy_available_repetition_count": len(replay_rows),
            "genealogy_coverage_of_30_repetitions": len(replay_rows) / 30.0,
            "descendant_finished_lots_available": bool(
                replay and replay["descendant_finished_lots_available"]
            ),
            "aggregated_client_contact_available": bool(
                replay and replay["aggregated_client_contact_available"]
            ),
            "detailed_replay_dossier_id": _text(
                (replay or selected or {}).get("detailed_replay_dossier_id")
            ),
            "action_lot_trace_available": False,
            **typed,
        }
        output.append(record)
    if seen != set(by_cell):
        raise IncidentLotRegistryError(
            "Certaines cellules d'exposition sont sans agrégat"
        )
    state_order = {value: index for index, value in enumerate(STATES)}
    mechanism_order = {value: index for index, value in enumerate(MECHANISMS)}
    output.sort(
        key=lambda row: (
            state_order[row["operating_point_id"]],
            row["lane_id"],
            mechanism_order[row["mechanism"]],
        )
    )
    fields = list(dict.fromkeys((*CELL_PREFIX_FIELDS, *official_field_order)))
    return fields, output


def _event_day(stage: str, row: Mapping[str, Any]) -> int | None:
    field = "risk_decision_day" if stage == "shipment_to_material_receipt" else "day"
    return _integer(row.get(field), label=f"{stage} day", optional=True)


def normalise_genealogy_rows(
    *,
    dossier: Mapping[str, Any],
    source_tables: Mapping[str, Sequence[Mapping[str, Any]]],
    source_paths: Mapping[str, str],
    incident_j0_day: int,
) -> list[dict[str, Any]]:
    """Retain every source genealogy row and expose common lot/business fields."""

    output: list[dict[str, Any]] = []
    for stage in TRACE_FILES:
        rows = source_tables.get(stage, ())
        for ordinal, raw in enumerate(rows, start=2):
            day = _event_day(stage, raw)
            output.append(
                {
                    "dossier_id": _text(dossier.get("dossier_id")),
                    "operating_point_id": _text(dossier.get("operating_point_id")),
                    "mechanism": _text(dossier.get("mechanism")),
                    "lane_id": _text(dossier.get("lane_id")),
                    "supplier_id": _text(dossier.get("supplier_id")),
                    "item_id": _text(dossier.get("item_id")),
                    "dst_node_id": _text(dossier.get("dst_node_id")),
                    "target_product_id": _text(dossier.get("target_product_id")),
                    "representative_seed": int(
                        _integer(dossier.get("representative_seed"), label="seed")
                    ),
                    "genealogy_stage": stage,
                    "source_relative_path": source_paths[stage],
                    "source_row_number": ordinal,
                    "incident_event_id": _text(raw.get("incident_event_id")),
                    "incident_j0_day": incident_j0_day,
                    "event_day": day,
                    "event_day_kind": EVENT_DAY_KINDS[stage],
                    "days_from_incident_j0": (
                        day - incident_j0_day if day is not None else None
                    ),
                    "is_simulation_day_zero": day == 0 if day is not None else False,
                    "is_incident_j0": day == incident_j0_day
                    if day is not None
                    else False,
                    "shipment_id": _text(raw.get("shipment_id")),
                    "shipment_ids": _text(raw.get("shipment_ids")),
                    "risk_decision_day": _integer(
                        raw.get("risk_decision_day"),
                        label="risk_decision_day",
                        optional=True,
                    ),
                    "source_lot_id": _text(raw.get("source_lot_id")),
                    "source_node_id": _text(raw.get("source_node_id")),
                    "source_item_id": _text(raw.get("source_item_id")),
                    "receipt_lot_id": _text(raw.get("receipt_lot_id")),
                    "receipt_node_id": _text(raw.get("receipt_node_id")),
                    "receipt_item_id": _text(raw.get("receipt_item_id")),
                    "parent_qty": _number(
                        raw.get("parent_qty"), label="parent_qty", optional=True
                    ),
                    "child_qty": _number(
                        raw.get("child_qty"), label="child_qty", optional=True
                    ),
                    "material_lot_id": _text(raw.get("material_lot_id")),
                    "consumption_day": day if stage == "consumption_and_wip" else None,
                    "consumed_qty": _number(
                        raw.get("consumed_qty"), label="consumed_qty", optional=True
                    ),
                    "campaign_id": _text(raw.get("campaign_id")),
                    "batch_id": _text(raw.get("batch_id")),
                    "wip_start_qty": _number(
                        raw.get("wip_start_qty"), label="wip_start_qty", optional=True
                    ),
                    "wip_end_qty": _number(
                        raw.get("wip_end_qty"), label="wip_end_qty", optional=True
                    ),
                    "campaign_wip_qty_end_of_run": _number(
                        raw.get("campaign_wip_qty_end_of_run"),
                        label="campaign_wip_qty_end_of_run",
                        optional=True,
                    ),
                    "campaign_blocked_lot_qty": _number(
                        raw.get("campaign_blocked_lot_qty"),
                        label="campaign_blocked_lot_qty",
                        optional=True,
                    ),
                    "released_lot_id_same_day": _text(
                        raw.get("released_lot_id_same_day")
                    ),
                    "released_qty_same_day": _number(
                        raw.get("released_qty_same_day"),
                        label="released_qty_same_day",
                        optional=True,
                    ),
                    "finished_lot_id": _text(raw.get("finished_lot_id")),
                    "release_day": day if stage == "finished_lot_release" else None,
                    "released_qty": _number(
                        raw.get("released_qty"), label="released_qty", optional=True
                    ),
                    "exposed_parent_lot_ids": _text(raw.get("exposed_parent_lot_ids")),
                    "client_lot_id": _text(raw.get("client_lot_id")),
                    "client_day": day if stage == "aggregated_client_contact" else None,
                    "client_node_id": _text(raw.get("client_node_id")),
                    "service_event_qty_on_contacted_lot": _number(
                        raw.get("service_event_qty_on_contacted_lot"),
                        label="service_event_qty_on_contacted_lot",
                        optional=True,
                    ),
                    "uom": _text(raw.get("uom")),
                    "claim": _text(raw.get("claim")),
                    "raw_record_json": json.dumps(
                        dict(raw),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
    expected = sum(len(source_tables.get(stage, ())) for stage in TRACE_FILES)
    if len(output) != expected:
        raise IncidentLotRegistryError("Une ligne de généalogie a été tronquée")
    return output


def _load_j0_context(
    *,
    path: Path,
    dossier: Mapping[str, Any],
    incident_j0_day: int,
) -> list[dict[str, Any]]:
    fields, rows = _read_csv(path)
    required = {
        "day",
        "metric",
        "baseline_value",
        "incident_value",
        "delta_incident_minus_baseline",
    }
    if not required.issubset(fields):
        raise IncidentLotRegistryError("Courbes de rejeu sans schéma J0 complet")
    selected = [
        row
        for row in rows
        if _integer(row.get("day"), label="curve day") == incident_j0_day
    ]
    metrics = {_text(row.get("metric")) for row in selected}
    if metrics != EXPECTED_J0_METRICS or len(selected) != len(EXPECTED_J0_METRICS):
        raise IncidentLotRegistryError("Contexte J0 du rejeu incomplet ou dupliqué")
    if incident_j0_day < 0:
        raise IncidentLotRegistryError("Le premier jour de l'incident est négatif")
    for row in selected:
        baseline = float(_number(row.get("baseline_value"), label="baseline J0"))
        incident = float(_number(row.get("incident_value"), label="incident J0"))
        delta = float(
            _number(
                row.get("delta_incident_minus_baseline"),
                label="delta J0",
            )
        )
        if not math.isclose(delta, incident - baseline, abs_tol=EPS, rel_tol=1e-9):
            raise IncidentLotRegistryError("Écart incident-référence incohérent à J0")
    return [
        {
            "dossier_id": _text(dossier.get("dossier_id")),
            "operating_point_id": _text(dossier.get("operating_point_id")),
            "mechanism": _text(dossier.get("mechanism")),
            "lane_id": _text(dossier.get("lane_id")),
            "representative_seed": int(
                _integer(dossier.get("representative_seed"), label="seed")
            ),
            "incident_j0_day": incident_j0_day,
            "metric": _text(row.get("metric")),
            "measurement_kind": J0_MEASUREMENT_KINDS[_text(row.get("metric"))],
            "observation_convention": J0_OBSERVATION_CONVENTION,
            "is_pre_incident_snapshot": False,
            "baseline_value_at_incident_j0": _number(
                row.get("baseline_value"), label="baseline J0"
            ),
            "incident_value_at_incident_j0": _number(
                row.get("incident_value"), label="incident J0"
            ),
            "delta_incident_minus_baseline_at_incident_j0": _number(
                row.get("delta_incident_minus_baseline"), label="delta J0"
            ),
        }
        for row in sorted(selected, key=lambda value: _text(value.get("metric")))
    ]


def load_available_replays(
    *,
    campaign_root: Path,
    results_dir: Path,
    replay_root: Path | None,
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    """Load zero or all finalized selected replays, preserving every trace row."""

    selected_rows = selection.get("selected_dossiers") or []
    selected_count = int(
        _integer(
            selection.get("selected_dossier_count", 0), label="selected dossier count"
        )
    )
    if (
        not isinstance(selected_rows, list)
        or selected_count != len(selected_rows)
        or not 0 <= selected_count <= 3
    ):
        raise IncidentLotRegistryError(
            "La sélection officielle doit contenir 0 à 3 dossiers"
        )
    if replay_root is None:
        return {
            "dossiers": [],
            "genealogyRows": [],
            "j0Rows": [],
            "binding": {
                "status": "not_supplied",
                "availableDossierCount": 0,
                "selectedDossierCount": selected_count,
            },
        }
    try:
        qualification = physical_v5.validate_replay_dossiers_physically_exercised(
            campaign_root=campaign_root.resolve(),
            results_dir=results_dir.resolve(),
            replay_root=replay_root.resolve(),
        )
    except Exception as exc:
        raise IncidentLotRegistryError(
            f"Rejeu détaillé officiel refusé : {exc}"
        ) from exc
    if qualification["dossier_count"] == 0:
        if selected_count != 0:
            raise IncidentLotRegistryError("Des rejeux sélectionnés sont absents")
        return {
            "dossiers": [],
            "genealogyRows": [],
            "j0Rows": [],
            "binding": {
                "status": "validated_no_dossier",
                "availableDossierCount": 0,
                "selectedDossierCount": selected_count,
            },
        }

    root = replay_root.resolve()
    plan = replay_v4.load_and_validate_plan(root)
    validation_path = root / "finalized" / "replay_validation.json"
    validation = _read_json(validation_path)
    try:
        replay_v4._verify_signed_payload(  # noqa: SLF001
            validation, "validation_signature", "finalized replay validation"
        )
    except Exception as exc:
        raise IncidentLotRegistryError(
            "La signature du rejeu finalisé a changé"
        ) from exc
    if (
        qualification["dossier_count"] != selected_count
        or plan.get("plan_signature") != qualification["plan_signature"]
        or validation.get("validation_signature")
        != qualification["replay_validation_signature"]
        or validation.get("plan_signature") != qualification["plan_signature"]
        or validation.get("run_receipt_signature")
        != qualification["run_receipt_signature"]
        or sha256_file(validation_path) != qualification["replay_validation_sha256"]
    ):
        raise IncidentLotRegistryError(
            "L'empreinte du rejeu a changé pendant la lecture"
        )
    inventory = physical_v5._validate_replay_inventory(  # noqa: SLF001
        replay_root=root, validation=validation
    )
    plan_by_id = {_text(row.get("dossier_id")): row for row in plan["dossiers"]}
    selected_by_id = {_text(row.get("dossier_id")): row for row in selected_rows}

    dossiers: list[dict[str, Any]] = []
    genealogy_rows: list[dict[str, Any]] = []
    j0_rows: list[dict[str, Any]] = []
    for qualified in qualification["dossiers"]:
        dossier_id = _text(qualified.get("dossier_id"))
        planned = plan_by_id.get(dossier_id)
        selected = selected_by_id.get(dossier_id)
        if not isinstance(planned, Mapping) or not isinstance(selected, Mapping):
            raise IncidentLotRegistryError("Identité de rejeu non reliée à la campagne")
        priority = planned.get("priority")
        risk_row = planned.get("risk_row")
        if not isinstance(priority, Mapping) or not isinstance(risk_row, Mapping):
            raise IncidentLotRegistryError("Plan de rejeu sans voie ou incident")
        metadata = {
            "dossier_id": dossier_id,
            "operating_point_id": _text(qualified.get("operating_point_id")),
            "mechanism": _text(qualified.get("mechanism")),
            "lane_id": _text(qualified.get("lane_id")),
            "supplier_id": _text(priority.get("supplier_id")),
            "item_id": _text(priority.get("item_id")),
            "dst_node_id": _text(priority.get("dst_node_id")),
            "target_product_id": _text(priority.get("target_product_id")),
            "representative_seed": int(
                _integer(qualified.get("representative_seed"), label="replay seed")
            ),
        }
        incident_j0 = int(_integer(risk_row.get("start_day"), label="incident J0"))
        source_tables: dict[str, list[dict[str, str]]] = {}
        source_paths: dict[str, str] = {}
        for stage, filename in TRACE_FILES.items():
            relative = f"finalized/dossiers/{dossier_id}/{filename}"
            path = inventory.get(relative)
            if path is None:
                raise IncidentLotRegistryError(
                    f"Fichier de généalogie absent : {relative}"
                )
            source_tables[stage] = _read_csv(path)[1]
            source_paths[stage] = relative
        normalised = normalise_genealogy_rows(
            dossier=metadata,
            source_tables=source_tables,
            source_paths=source_paths,
            incident_j0_day=incident_j0,
        )
        genealogy_rows.extend(normalised)
        curve_relative = f"finalized/dossiers/{dossier_id}/paired_daily_curves.csv"
        curve_path = inventory.get(curve_relative)
        if curve_path is None:
            raise IncidentLotRegistryError(f"Courbes appariées absentes : {dossier_id}")
        dossier_j0 = _load_j0_context(
            path=curve_path, dossier=metadata, incident_j0_day=incident_j0
        )
        j0_rows.extend(dossier_j0)
        kpi_relative = f"finalized/dossiers/{dossier_id}/dossier_kpis.json"
        kpi_path = inventory.get(kpi_relative)
        if kpi_path is None:
            raise IncidentLotRegistryError(f"KPI de rejeu absents : {dossier_id}")
        dossiers.append(
            {
                **metadata,
                "incidentJ0Day": incident_j0,
                "proofLevel": qualified.get("proof_level"),
                "proofScope": qualified.get("proof_scope"),
                "mrpRequirementMode": qualified.get("mrp_requirement_mode"),
                "traceCounts": dict(qualified.get("trace_counts") or {}),
                "missingNativeTraceStages": list(
                    qualified.get("missing_native_trace_stages") or []
                ),
                "fullDynamicCascadeProven": False,
                "signedMrpResponseTraceAvailable": False,
                "kpis": _read_json(kpi_path),
                "j0Context": dossier_j0,
                "sourceTables": source_tables,
                "sourceRowCount": sum(len(rows) for rows in source_tables.values()),
                "normalisedRowCount": len(normalised),
                "sourceRowsTruncated": False,
            }
        )
    if len(dossiers) != qualification["dossier_count"] or len(dossiers) > 3:
        raise IncidentLotRegistryError(
            "Le nombre de rejeux disponibles n'est pas dans 0..3"
        )
    if len(genealogy_rows) != sum(row["sourceRowCount"] for row in dossiers):
        raise IncidentLotRegistryError("Le registre généalogique a tronqué des lignes")
    return {
        "dossiers": sorted(dossiers, key=lambda row: row["dossier_id"]),
        "genealogyRows": genealogy_rows,
        "j0Rows": j0_rows,
        "binding": {
            "status": "complete_validated",
            "root": str(root),
            "availableDossierCount": len(dossiers),
            "selectedDossierCount": selected_count,
            "planSignature": qualification["plan_signature"],
            "runReceiptSignature": qualification["run_receipt_signature"],
            "replayValidationSignature": qualification["replay_validation_signature"],
            "replayValidationSha256": qualification["replay_validation_sha256"],
            "artifactInventorySha256": validation.get("artifact_inventory_sha256"),
        },
    }


def _dossier_identity(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        _text(row.get("operating_point_id")),
        _text(row.get("mechanism")),
        _text(row.get("lane_id")),
        int(_integer(row.get("representative_seed"), label="representative_seed")),
    )


def _trace_counts_from_source_tables(
    source_tables: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, int]:
    shipment_rows = source_tables["shipment_to_material_receipt"]
    consumption_rows = source_tables["consumption_and_wip"]
    finished_rows = source_tables["finished_lot_release"]
    client_rows = source_tables["aggregated_client_contact"]
    return {
        "shipments": len(
            {_text(row.get("shipment_id")) for row in shipment_rows} - {""}
        ),
        "material_receipts": len(
            {_text(row.get("receipt_lot_id")) for row in shipment_rows} - {""}
        ),
        "consumptions": len(consumption_rows),
        "campaigns": len(
            {_text(row.get("campaign_id")) for row in consumption_rows} - {""}
        ),
        "batches": len({_text(row.get("batch_id")) for row in consumption_rows} - {""}),
        "finished_lots": len(finished_rows),
        "client_events": len(client_rows),
        "clients": len(
            {_text(row.get("client_node_id")) for row in client_rows} - {""}
        ),
    }


def _validate_payload_contract(payload: Mapping[str, Any]) -> None:
    """Cross-check JSON scope, matrices and untruncated replay source rows."""

    scope = payload.get("scope")
    exposures = payload.get("exposures")
    cells = payload.get("cells")
    detailed = payload.get("detailedReplays")
    actions = payload.get("actions")
    if (
        payload.get("schemaVersion") != SCHEMA_VERSION
        or payload.get("status") != "complete_validated_postprocessing"
        or not isinstance(scope, Mapping)
        or not isinstance(exposures, list)
        or not isinstance(cells, list)
        or not isinstance(detailed, Mapping)
        or not isinstance(actions, Mapping)
    ):
        raise IncidentLotRegistryError("Structure du registre V6 invalide")
    dossiers = detailed.get("dossiers")
    genealogy = detailed.get("genealogyRows")
    j0_rows = detailed.get("j0Rows")
    if not all(isinstance(value, list) for value in (dossiers, genealogy, j0_rows)):
        raise IncidentLotRegistryError("Tables de rejeu absentes du registre")
    if (
        len(exposures) != EXPECTED_INCIDENT_ROWS
        or len(cells) != EXPECTED_CELL_ROWS
        or scope.get("signedCaseEvidenceRowCount") != EXPECTED_TOTAL_ROWS
        or scope.get("baselineReferenceRowCount") != EXPECTED_BASELINE_ROWS
        or scope.get("incidentExposureRowCount") != len(exposures)
        or scope.get("cellRowCount") != len(cells)
        or scope.get("availableDetailedReplayCount") != len(dossiers)
        or scope.get("genealogySourceRowCount") != len(genealogy)
        or scope.get("j0ContextRowCount") != len(j0_rows)
        or not 0 <= len(dossiers) <= 3
        or scope.get("allSourceGenealogyRowsRetained") is not True
        or scope.get("descendantLotsExistOnlyForDetailedReplays") is not True
        or scope.get("actionLotTraceAvailable") is not False
        or detailed.get("sourceRowsTruncated") is not False
        or actions.get("includedInThisRegistry") is not False
        or actions.get("lotTraceAvailable") is not False
        or actions.get("controlMode") != ACTION_CONTROL_MODE
        or actions.get("explanation") != ACTION_EXPLANATION
    ):
        raise IncidentLotRegistryError("Comptes ou exclusions du registre incohérents")

    exposure_keys = {
        (
            _text(row.get("operating_point_id")),
            _text(row.get("mechanism")),
            _text(row.get("lane_id")),
            _integer(row.get("seed"), label="payload seed"),
        )
        for row in exposures
        if isinstance(row, Mapping)
    }
    cell_keys = {_cell_key(row) for row in cells if isinstance(row, Mapping)}
    if len(exposure_keys) != len(exposures) or len(cell_keys) != len(cells):
        raise IncidentLotRegistryError("Identités JSON dupliquées ou mal formées")
    lane_ids = {_text(row.get("lane_id")) for row in cells}
    if len(lane_ids) != EXPECTED_LANES:
        raise IncidentLotRegistryError("Les 108 cellules ne couvrent pas 18 voies")
    _validate_exposure_identity(exposures, lane_ids=lane_ids)
    for row in exposures:
        selected_flag = row.get("detailed_replay_selected")
        genealogy_flag = row.get("genealogy_available")
        if (
            not isinstance(selected_flag, bool)
            or not isinstance(genealogy_flag, bool)
            or row.get("action_lot_trace_available") is not False
            or (genealogy_flag and not selected_flag)
            or (not selected_flag and _text(row.get("detailed_replay_dossier_id")))
            or (
                not genealogy_flag
                and (
                    row.get("descendant_finished_lots_available") is not False
                    or row.get("aggregated_client_contact_available") is not False
                )
            )
            or row.get("genealogy_scope")
            != (
                "généalogie native disponible pour ce rejeu exact"
                if genealogy_flag
                else "aucun lot descendant : ligne de campagne agrégée sans journal détaillé des lots"
            )
        ):
            raise IncidentLotRegistryError(
                "Drapeaux de preuve lot incohérents dans une exposition"
            )

    selected_exposures = [
        row for row in exposures if row.get("detailed_replay_selected") is True
    ]
    replayed_exposures = [
        row for row in exposures if row.get("genealogy_available") is True
    ]
    selected_cells = [
        row for row in cells if row.get("detailed_replay_selected") is True
    ]
    replayed_cells = [
        row for row in cells if row.get("genealogy_replay_available") is True
    ]
    selected_count = scope.get("selectedDetailedReplayCount")
    if (
        not isinstance(selected_count, int)
        or not 0 <= selected_count <= 3
        or len(selected_exposures) != selected_count
        or len(selected_cells) != selected_count
        or len(replayed_exposures) != len(dossiers)
        or len(replayed_cells) != len(dossiers)
        or scope.get("incidentRowsWithGenealogy") != len(replayed_exposures)
        or scope.get("incidentRowsWithoutGenealogy")
        != len(exposures) - len(replayed_exposures)
    ):
        raise IncidentLotRegistryError("Couverture sélection/rejeu incohérente")
    selected_ids_from_exposures = {
        _text(row.get("detailed_replay_dossier_id")) for row in selected_exposures
    }
    selected_ids_from_cells = {
        _text(row.get("detailed_replay_dossier_id")) for row in selected_cells
    }
    if (
        "" in selected_ids_from_exposures
        or selected_ids_from_exposures != selected_ids_from_cells
        or len(selected_ids_from_exposures) != selected_count
    ):
        raise IncidentLotRegistryError(
            "Identifiants de sélection détaillée incohérents"
        )
    selected_exposure_by_id = {
        _text(row.get("detailed_replay_dossier_id")): row for row in selected_exposures
    }
    selected_cell_by_id = {
        _text(row.get("detailed_replay_dossier_id")): row for row in selected_cells
    }
    if any(
        _cell_key(selected_exposure_by_id[dossier_id])
        != _cell_key(selected_cell_by_id[dossier_id])
        for dossier_id in selected_ids_from_exposures
    ):
        raise IncidentLotRegistryError(
            "Sélection détaillée rattachée à la mauvaise cellule"
        )
    for row in cells:
        count = _integer(
            row.get("genealogy_available_repetition_count"),
            label="genealogy cell count",
        )
        coverage = _number(
            row.get("genealogy_coverage_of_30_repetitions"),
            label="genealogy cell coverage",
        )
        if (
            count not in {0, 1}
            or not math.isclose(
                float(coverage), float(count) / EXPECTED_SEEDS, abs_tol=EPS
            )
            or row.get("genealogy_replay_available") is not bool(count)
            or row.get("action_lot_trace_available") is not False
            or (
                row.get("genealogy_replay_available") is True
                and row.get("detailed_replay_selected") is not True
            )
            or (
                row.get("detailed_replay_selected") is not True
                and _text(row.get("detailed_replay_dossier_id"))
            )
            or (
                row.get("genealogy_replay_available") is not True
                and (
                    row.get("descendant_finished_lots_available") is not False
                    or row.get("aggregated_client_contact_available") is not False
                )
            )
        ):
            raise IncidentLotRegistryError("Couverture lots d'une cellule invalide")

    dossier_by_id = {
        _text(row.get("dossier_id")): row
        for row in dossiers
        if isinstance(row, Mapping)
    }
    if len(dossier_by_id) != len(dossiers) or "" in dossier_by_id:
        raise IncidentLotRegistryError(
            "Dossiers détaillés dupliqués ou sans identifiant"
        )
    replay_ids_from_exposures = {
        _text(row.get("detailed_replay_dossier_id")) for row in replayed_exposures
    }
    if replay_ids_from_exposures != set(dossier_by_id):
        raise IncidentLotRegistryError("Dossiers et drapeaux d'exposition diffèrent")
    exposure_by_identity = {
        (
            _text(row.get("operating_point_id")),
            _text(row.get("mechanism")),
            _text(row.get("lane_id")),
            int(_integer(row.get("seed"), label="payload seed")),
        ): row
        for row in exposures
    }
    cell_by_identity = {_cell_key(row): row for row in cells}
    dossier_identities: set[tuple[str, str, str, int]] = set()
    for dossier_id, dossier in dossier_by_id.items():
        identity = _dossier_identity(dossier)
        if identity in dossier_identities:
            raise IncidentLotRegistryError(
                "Deux dossiers détaillés couvrent la même situation/répétition"
            )
        dossier_identities.add(identity)
        exposure = exposure_by_identity.get(identity)
        cell = cell_by_identity.get(identity[:3])
        if (
            not isinstance(exposure, Mapping)
            or not isinstance(cell, Mapping)
            or exposure.get("incident_physically_exercised") is not True
            or exposure.get("detailed_replay_selected") is not True
            or exposure.get("genealogy_available") is not True
            or _text(exposure.get("detailed_replay_dossier_id")) != dossier_id
            or cell.get("genealogy_replay_available") is not True
            or _text(cell.get("detailed_replay_dossier_id")) != dossier_id
            or dossier.get("mrpRequirementMode") != exposure.get("mrp_requirement_mode")
            or dossier.get("proofScope")
            != "native_lot_contact_trace_to_aggregated_client"
            or dossier.get("proofLevel") not in {"partial", "complete"}
            or dossier.get("fullDynamicCascadeProven") is not False
            or dossier.get("signedMrpResponseTraceAvailable") is not False
        ):
            raise IncidentLotRegistryError(
                f"Dossier détaillé non rattaché à sa preuve exacte : {dossier_id}"
            )
        for field in (
            "supplier_id",
            "item_id",
            "dst_node_id",
            "target_product_id",
        ):
            if not _same_identity(field, dossier.get(field), exposure.get(field)):
                raise IncidentLotRegistryError(
                    f"Identité métier du dossier différente : {dossier_id}/{field}"
                )
        if dossier.get("incidentJ0Day") != exposure.get("risk_start_day"):
            raise IncidentLotRegistryError(
                f"J0 du dossier différent du début de l'incident : {dossier_id}"
            )

    genealogy_by_dossier: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in genealogy:
        if not isinstance(row, Mapping):
            raise IncidentLotRegistryError("Ligne généalogique non structurée")
        _require_fields(row, GENEALOGY_FIELDS, label="généalogie JSON")
        dossier_id = _text(row.get("dossier_id"))
        if dossier_id not in dossier_by_id:
            raise IncidentLotRegistryError("Généalogie sans dossier de rejeu")
        dossier = dossier_by_id[dossier_id]
        if (
            _dossier_identity(row) != _dossier_identity(dossier)
            or row.get("incident_j0_day") != dossier.get("incidentJ0Day")
            or row.get("genealogy_stage") not in TRACE_FILES
            or row.get("event_day_kind")
            != EVENT_DAY_KINDS.get(_text(row.get("genealogy_stage")))
        ):
            raise IncidentLotRegistryError(
                f"Généalogie rattachée au mauvais état/mécanisme/voie : {dossier_id}"
            )
        for field in (
            "supplier_id",
            "item_id",
            "dst_node_id",
            "target_product_id",
        ):
            if not _same_identity(field, row.get(field), dossier.get(field)):
                raise IncidentLotRegistryError(
                    f"Identité de généalogie différente : {dossier_id}/{field}"
                )
        event_day = _integer(row.get("event_day"), label="event day", optional=True)
        expected_delta = (
            event_day - int(dossier["incidentJ0Day"]) if event_day is not None else None
        )
        if (
            row.get("days_from_incident_j0") != expected_delta
            or row.get("is_simulation_day_zero") is not (event_day == 0)
            or row.get("is_incident_j0")
            is not (event_day == dossier.get("incidentJ0Day"))
        ):
            raise IncidentLotRegistryError(
                f"Repères temporels de généalogie incohérents : {dossier_id}"
            )
        genealogy_by_dossier[dossier_id].append(row)

    for dossier_id, dossier in dossier_by_id.items():
        source_tables = dossier.get("sourceTables")
        if (
            dossier.get("sourceRowsTruncated") is not False
            or not isinstance(source_tables, Mapping)
            or set(source_tables) != set(TRACE_FILES)
            or any(not isinstance(source_tables[stage], list) for stage in TRACE_FILES)
        ):
            raise IncidentLotRegistryError(
                f"Tables sources incomplètes ou tronquées : {dossier_id}"
            )
        source_count = sum(len(source_tables[stage]) for stage in TRACE_FILES)
        trace_counts = dossier.get("traceCounts")
        derived_trace_counts = _trace_counts_from_source_tables(source_tables)
        exact_exposure = exposure_by_identity[_dossier_identity(dossier)]
        exact_cell = cell_by_identity[_dossier_identity(dossier)[:3]]
        if (
            not isinstance(trace_counts, Mapping)
            or set(trace_counts) != set(derived_trace_counts)
            or any(
                _integer(trace_counts.get(field), label=f"trace count {field}") != count
                for field, count in derived_trace_counts.items()
            )
            or exact_exposure.get("descendant_finished_lots_available")
            is not bool(derived_trace_counts["finished_lots"])
            or exact_exposure.get("aggregated_client_contact_available")
            is not bool(derived_trace_counts["client_events"])
            or exact_cell.get("descendant_finished_lots_available")
            is not bool(derived_trace_counts["finished_lots"])
            or exact_cell.get("aggregated_client_contact_available")
            is not bool(derived_trace_counts["client_events"])
        ):
            raise IncidentLotRegistryError(
                f"Comptages natifs différents des tables sources : {dossier_id}"
            )
        expected_proof_level, expected_missing = physical_v5._qualify_trace_counts(  # noqa: SLF001
            derived_trace_counts
        )
        if (
            dossier.get("sourceRowCount") != source_count
            or dossier.get("normalisedRowCount") != source_count
            or len(genealogy_by_dossier[dossier_id]) != source_count
            or expected_proof_level == "not_exercised"
            or dossier.get("proofLevel") != expected_proof_level
            or list(dossier.get("missingNativeTraceStages") or []) != expected_missing
        ):
            raise IncidentLotRegistryError(
                f"Nombre de lignes généalogiques différent : {dossier_id}"
            )
        for stage in TRACE_FILES:
            normalized = sorted(
                (
                    row
                    for row in genealogy_by_dossier[dossier_id]
                    if row.get("genealogy_stage") == stage
                ),
                key=lambda row: int(
                    _integer(row.get("source_row_number"), label="source row number")
                ),
            )
            raw_rows = source_tables[stage]
            if len(normalized) != len(raw_rows):
                raise IncidentLotRegistryError(
                    f"Étape généalogique tronquée : {dossier_id}/{stage}"
                )
            for offset, (normalized_row, raw_row) in enumerate(
                zip(normalized, raw_rows, strict=True), start=2
            ):
                try:
                    reconstructed_raw = json.loads(
                        _text(normalized_row.get("raw_record_json"))
                    )
                except json.JSONDecodeError as exc:
                    raise IncidentLotRegistryError(
                        f"Copie brute invalide : {dossier_id}/{stage}/{offset}"
                    ) from exc
                if (
                    normalized_row.get("source_row_number") != offset
                    or normalized_row.get("source_relative_path")
                    != f"finalized/dossiers/{dossier_id}/{TRACE_FILES[stage]}"
                    or reconstructed_raw != dict(raw_row)
                ):
                    raise IncidentLotRegistryError(
                        f"Copie brute différente : {dossier_id}/{stage}/{offset}"
                    )

    j0_by_dossier: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in j0_rows:
        if not isinstance(row, Mapping):
            raise IncidentLotRegistryError("Ligne J0 non structurée")
        _require_fields(row, J0_FIELDS, label="contexte J0 JSON")
        dossier_id = _text(row.get("dossier_id"))
        if dossier_id not in dossier_by_id:
            raise IncidentLotRegistryError("Contexte J0 sans dossier de rejeu")
        dossier = dossier_by_id[dossier_id]
        baseline = float(
            _number(
                row.get("baseline_value_at_incident_j0"),
                label="baseline J0 JSON",
            )
        )
        incident = float(
            _number(
                row.get("incident_value_at_incident_j0"),
                label="incident J0 JSON",
            )
        )
        delta = float(
            _number(
                row.get("delta_incident_minus_baseline_at_incident_j0"),
                label="delta J0 JSON",
            )
        )
        if (
            _dossier_identity(row) != _dossier_identity(dossier)
            or row.get("incident_j0_day") != dossier.get("incidentJ0Day")
            or not math.isclose(delta, incident - baseline, abs_tol=EPS, rel_tol=1e-9)
        ):
            raise IncidentLotRegistryError(
                f"Contexte J0 rattaché au mauvais dossier : {dossier_id}"
            )
        j0_by_dossier[dossier_id].append(row)
    for dossier_id, dossier in dossier_by_id.items():
        rows = j0_by_dossier[dossier_id]
        if (
            len(rows) != len(EXPECTED_J0_METRICS)
            or {_text(row.get("metric")) for row in rows} != EXPECTED_J0_METRICS
            or any(
                row.get("measurement_kind")
                != J0_MEASUREMENT_KINDS[_text(row.get("metric"))]
                or row.get("observation_convention") != J0_OBSERVATION_CONVENTION
                or row.get("is_pre_incident_snapshot") is not False
                or row.get("incident_j0_day") != dossier.get("incidentJ0Day")
                for row in rows
            )
            or dossier.get("j0Context") != rows
        ):
            raise IncidentLotRegistryError(f"Contexte J0 ambigu : {dossier_id}")


def build_payload(
    *,
    incident_rows: Sequence[Mapping[str, Any]],
    official_cell_rows: Sequence[Mapping[str, Any]],
    official_cell_fields: Sequence[str],
    lanes: Sequence[Mapping[str, Any]],
    requirement_modes: Mapping[str, str],
    selection: Mapping[str, Any],
    replay_data: Mapping[str, Any],
    generated_at_utc: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    selected_rows = list(selection.get("selected_dossiers") or [])
    declared_selected_count = _integer(
        selection.get("selected_dossier_count", 0), label="selected dossier count"
    )
    if (
        declared_selected_count != len(selected_rows)
        or not 0 <= len(selected_rows) <= 3
    ):
        raise IncidentLotRegistryError(
            "La sélection détaillée doit contenir 0 à 3 dossiers"
        )
    replay_dossiers = list(replay_data.get("dossiers") or [])
    exposures = build_exposure_registry(
        incident_rows=incident_rows,
        lanes=lanes,
        requirement_modes=requirement_modes,
        selected_dossiers=selected_rows,
        replay_dossiers=replay_dossiers,
    )
    cell_fields, cells = build_cell_registry(
        official_rows=official_cell_rows,
        exposures=exposures,
        requirement_modes=requirement_modes,
    )
    if list(official_cell_fields) != [
        field for field in cell_fields if field not in CELL_PREFIX_FIELDS
    ]:
        raise IncidentLotRegistryError("L'ordre des colonnes de l'agrégat a changé")
    genealogy_rows = list(replay_data.get("genealogyRows") or [])
    j0_rows = list(replay_data.get("j0Rows") or [])
    genealogy_available_count = sum(row["genealogy_available"] for row in exposures)
    if genealogy_available_count != len(replay_dossiers):
        raise IncidentLotRegistryError(
            "Le drapeau de couverture généalogique est incohérent"
        )
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "complete_validated_postprocessing",
        "generatedAtUtc": generated_at_utc or utc_now(),
        "terminology": {
            "OBSERVÉ": (
                "Aucune fréquence historique d'incident fournisseur n'est chargée dans ce registre."
            ),
            "HYPOTHÈSE": (
                "Un retard transport de +120 jours ou une livraison planifiée réduite à 50 %, "
                "testé séparément sur une voie et une fenêtre de 42 jours."
            ),
            "SIMULÉ": (
                "Écart entre l'incident et la référence appariée, pour la même répétition."
            ),
            "SIGNAL DE PRIORITÉ": (
                "Cas à instruire issu des statistiques; ce n'est ni une probabilité d'incident "
                "ni une note fournisseur observée."
            ),
        },
        "scope": {
            "signedCaseEvidenceRowCount": EXPECTED_TOTAL_ROWS,
            "baselineReferenceRowCount": EXPECTED_BASELINE_ROWS,
            "incidentExposureRowCount": len(exposures),
            "cellRowCount": len(cells),
            "stateCount": len(STATES),
            "laneCount": EXPECTED_LANES,
            "mechanismCount": len(MECHANISMS),
            "seedCountPerCell": EXPECTED_SEEDS,
            "selectedDetailedReplayCount": int(
                selection.get("selected_dossier_count", 0)
            ),
            "availableDetailedReplayCount": len(replay_dossiers),
            "incidentRowsWithGenealogy": genealogy_available_count,
            "incidentRowsWithoutGenealogy": len(exposures) - genealogy_available_count,
            "genealogySourceRowCount": len(genealogy_rows),
            "j0ContextRowCount": len(j0_rows),
            "allSourceGenealogyRowsRetained": True,
            "descendantLotsExistOnlyForDetailedReplays": True,
            "actionLotTraceAvailable": False,
        },
        "exposures": exposures,
        "cells": cells,
        "detailedReplays": {
            "dossiers": replay_dossiers,
            "genealogyRows": genealogy_rows,
            "j0Rows": j0_rows,
            "sourceRowsTruncated": False,
            "j0Definition": (
                "J0 incident = premier jour de la fenêtre de risque. Les valeurs publiées "
                "sont celles de la série quotidienne de ce jour : niveaux de fin de journée "
                "pour stock, encours et retard client restant, et flux du jour pour production, "
                "demande et service. "
                "Ce n'est pas un instantané pré-incident; le drapeau simulation J0 désigne "
                "uniquement le jour absolu 0."
            ),
        },
        "actions": {
            "includedInThisRegistry": False,
            "lotTraceAvailable": False,
            "controlMode": ACTION_CONTROL_MODE,
            "explanation": ACTION_EXPLANATION,
        },
        "limits": [
            "Les 3 240 lignes sont des hypothèses simulées, pas 3 240 incidents observés.",
            "Une ligne sans rejeu détaillé n'a aucun lot descendant démontré.",
            "Un rejeu représente une seule répétition de sa situation; sa généalogie ne couvre pas les 29 autres.",
            "Le contexte J0 publié est une lecture des séries du premier jour de risque, pas un état figé juste avant l'incident.",
            "Le contact client est un nœud agrégé, pas un client ni une commande réels.",
            "Une trace native de contact lot ne prouve pas à elle seule une causalité incrémentale.",
            "Deux voies ont un besoin MRP dynamique explicite et seize un besoin statique explicite; aucune trace signée de réponse MRP n'est disponible.",
            "Les mécanismes testés sont séparés, exogènes et hypothétiques; aucune fréquence historique n'est estimée.",
            "Aucune cascade de plusieurs incidents corrélés ou endogènes n'est simulée ici; les rejeux détaillés montrent seulement la propagation physique d'un incident unique.",
            "Les coûts et pertes de chiffre d'affaires ne sont pas validés dans ce registre.",
            "Les actions existantes sont en boucle ouverte et sans traçage lot.",
        ],
    }
    if (
        payload["scope"]["incidentExposureRowCount"] != EXPECTED_INCIDENT_ROWS
        or payload["scope"]["cellRowCount"] != EXPECTED_CELL_ROWS
        or payload["scope"]["availableDetailedReplayCount"] > 3
    ):
        raise IncidentLotRegistryError("Périmètre de publication inattendu")
    _validate_payload_contract(payload)
    return payload, cell_fields


def _csv_bytes(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: (
                    json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else ""
                    if value is None
                    else value
                )
                for field, value in ((field, row.get(field)) for field in fields)
            }
        )
    return stream.getvalue().encode("utf-8-sig")


def _json_for_html(payload: Mapping[str, Any]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registre V6 — incidents et lots</title>
<style>
:root{--ink:#10243e;--muted:#5d7088;--line:#d9e3ed;--blue:#155eef;--navy:#12365d;--bg:#eef3f8;--orange:#b54708;--green:#067647}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.48 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1480px;margin:auto;padding:22px}.hero,.panel,.note{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;margin:12px 0;box-shadow:0 8px 25px #17324f0b}.hero h1{margin:0 0 7px;font-size:29px}.muted{color:var(--muted)}.tabs{display:flex;gap:8px;position:sticky;top:0;z-index:4;background:#eef3f8e8;padding:8px 0;backdrop-filter:blur(8px)}.tabs button{border:1px solid #bed0e2;border-radius:22px;padding:9px 14px;background:#fff;color:var(--navy);cursor:pointer}.tabs button.on{background:var(--navy);color:#fff}.view{display:none}.view.on{display:block}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.kpi{border:1px solid var(--line);border-radius:12px;padding:12px}.kpi b{display:block;font-size:25px}.badge{display:inline-block;border-radius:12px;padding:3px 8px;margin:2px;font-size:12px;font-weight:700}.sim{background:#e8f1ff;color:#1849a9}.hyp{background:#fff0e3;color:#9a3412}.obs{background:#ecfdf3;color:#067647}.signal{background:#f2eafd;color:#6938a8}.warn{border-left:5px solid #f79009}.toolbar{display:flex;flex-wrap:wrap;gap:9px;margin:10px 0}.toolbar input,.toolbar select{min-width:170px;padding:8px;border:1px solid #b9c9d8;border-radius:8px;background:#fff}.scroll{overflow:auto;max-height:610px;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;font-size:12.5px;background:#fff}th,td{padding:7px 8px;border-bottom:1px solid #e7edf3;text-align:left;white-space:nowrap;vertical-align:top}th{position:sticky;top:0;background:#f5f8fb;z-index:1}.pager{display:flex;align-items:center;gap:8px;margin-top:9px}.pager button{padding:6px 10px}.lot{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11.5px}.ok{color:var(--green);font-weight:700}.no{color:#b42318}.limits li{margin:6px 0}@media(max-width:700px){main{padding:10px}.hero h1{font-size:23px}.tabs{overflow:auto}.scroll{max-height:520px}}
</style></head><body><main>
<section class="hero"><div><span class="badge sim">SIMULÉ</span><span class="badge hyp">HYPOTHÈSES</span></div><h1>Tests d'incidents fournisseurs et couverture des lots</h1><p>Le registre sépare ce qui a été calculé sur toute la campagne de ce qui a réellement été retracé au niveau lot. Les 3 240 tests utilisent 90 références appariées, soit 3 330 cas signés. <b>Aucune fréquence historique d'incident fournisseur n'est observée ici.</b> Une absence de généalogie ne signifie pas absence d'impact : elle signifie que cette répétition n'a pas été rejouée avec le journal détaillé des lots.</p><div class="grid" id="headline"></div></section>
<nav class="tabs"><button class="on" data-tab="exposures">1 · 3 240 tests simulés</button><button data-tab="cells">2 · 108 synthèses</button><button data-tab="lots">3 · Lots disponibles</button></nav>
<section id="exposures" class="view on" data-view="1"><article class="panel"><h2>Chaque répétition simulée</h2><p class="muted">Une ligne = une répétition, un état de service, une voie fournisseur et un mécanisme d'incident. L'impact est l'écart avec la référence calculée dans les mêmes conditions.</p><div class="toolbar"><select id="e-state"><option value="">Tous les états</option></select><select id="e-mech"><option value="">Tous les mécanismes</option></select><input id="e-search" placeholder="Fournisseur, voie, article…"></div><p id="e-count"></p><div class="scroll"><table><thead><tr><th>État / répétition</th><th>Voie</th><th>Hypothèse</th><th>Expéditions / quantité planifiée</th><th>Intensité réellement appliquée</th><th>Service produit perdu</th><th>Production perdue</th><th>Retard client cumulé supplémentaire</th><th>Lots</th></tr></thead><tbody id="e-body"></tbody></table></div><div class="pager"><button id="e-prev">←</button><span id="e-page"></span><button id="e-next">→</button></div></article></section>
<section id="cells" class="view" data-view="2"><article class="panel"><h2>Les 108 situations comparables</h2><p class="muted">Une situation regroupe 30 répétitions appariées. P10–P90 contient les 80 % centraux des résultats; l'IC95 décrit l'incertitude de la moyenne simulée, pas une garantie industrielle. La couverture des lots vaut 0/30 ou 1/30.</p><div class="toolbar"><select id="c-state"><option value="">Tous les états</option></select><select id="c-mech"><option value="">Tous les mécanismes</option></select><input id="c-search" placeholder="Fournisseur, voie, article…"></div><p id="c-count"></p><div class="scroll"><table><thead><tr><th>État</th><th>Voie</th><th>Hypothèse</th><th>Répétitions avec flux touché</th><th>Service produit perdu</th><th>80 % centraux (P10–P90)</th><th>IC95 de la moyenne</th><th>Répétitions avec effet</th><th>Production / retard client moyens</th><th>Couverture lots</th></tr></thead><tbody id="c-body"></tbody></table></div></article></section>
<section id="lots" class="view" data-view="3"><article class="panel"><h2>Généalogies natives disponibles, sans troncature</h2><p><b>Les lots descendants ci-dessous n'existent que pour les rejeux détaillés affichés.</b> Ils ne sont jamais extrapolés aux autres répétitions. J0 incident est le premier jour de la fenêtre de risque; il peut être différent du jour absolu 0. Les niveaux J0 sont lus en fin de journée et les flux J0 sur la journée : ce n'est pas un instantané juste avant l'incident. Pour l'étape expédition–lot entrant, le jour affiché est le jour de décision d'expédition; cette table ne publie pas le jour de réception.</p><div class="toolbar"><select id="g-dossier"><option value="">Tous les dossiers</option></select><select id="g-stage"><option value="">Toutes les étapes</option></select><input id="g-search" placeholder="Lot, campagne, batch, client…"></div><div id="j0"></div><p id="g-count"></p><div class="scroll"><table><thead><tr><th>Dossier / étape</th><th>Jour / écart J0</th><th>Expédition</th><th>Lot entrant</th><th>Campagne / batch / encours</th><th>Lot fini / libération</th><th>Client agrégé</th></tr></thead><tbody id="g-body"></tbody></table></div><div class="pager"><button id="g-prev">←</button><span id="g-page"></span><button id="g-next">→</button></div></article><article class="panel warn"><h3>Ce que ce registre ne permet pas d'affirmer</h3><ul class="limits" id="limits"></ul><p><b>Actions :</b> les analyses d'actions existantes sont en boucle ouverte et leur contrat impose <code>lot_trace_enabled=false</code>. Aucun gain d'action n'est attribuable ici à un lot, une campagne ou un client précis.</p></article></section>
</main><script>
const D=__PAYLOAD__;const PAGE=60;const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const n=v=>Number(v??0);const fmt=(v,d=1)=>new Intl.NumberFormat('fr-FR',{maximumFractionDigits:d}).format(n(v));const mech=v=>v==='transport_delay'?'+120 jours de délai transport':'livraison planifiée réduite de 50 %';
document.querySelector('#headline').innerHTML=[['Tests d’incident simulés',fmt(D.scope.incidentExposureRowCount,0)],['Situations de 30 répétitions',fmt(D.scope.cellRowCount,0)],['Rejeux détaillés des lots',fmt(D.scope.availableDetailedReplayCount,0)],['Lignes de généalogie natives',fmt(D.scope.genealogySourceRowCount,0)]].map(x=>`<div class="kpi"><b>${x[1]}</b>${x[0]}</div>`).join('');
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('on',x===b));document.querySelectorAll('.view').forEach(x=>x.classList.toggle('on',x.id===b.dataset.tab))});
function options(id,values){const s=document.querySelector(id);[...new Set(values)].forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o)})}options('#e-state',D.exposures.map(r=>r.operating_point_id));options('#e-mech',D.exposures.map(r=>r.mechanism));options('#c-state',D.cells.map(r=>r.operating_point_id));options('#c-mech',D.cells.map(r=>r.mechanism));options('#g-dossier',D.detailedReplays.genealogyRows.map(r=>r.dossier_id));options('#g-stage',D.detailedReplays.genealogyRows.map(r=>r.genealogy_stage));
let ep=0;function renderE(){const st=document.querySelector('#e-state').value,me=document.querySelector('#e-mech').value,q=document.querySelector('#e-search').value.toLowerCase();const rows=D.exposures.filter(r=>(!st||r.operating_point_id===st)&&(!me||r.mechanism===me)&&(!q||[r.supplier_id,r.lane_id,r.item_id,r.dst_node_id,r.target_product_id].join(' ').toLowerCase().includes(q)));const pages=Math.max(1,Math.ceil(rows.length/PAGE));ep=Math.min(ep,pages-1);document.querySelector('#e-count').textContent=`${rows.length} ligne(s) — toutes présentes dans le fichier autonome`;document.querySelector('#e-page').textContent=`Page ${ep+1}/${pages}`;document.querySelector('#e-body').innerHTML=rows.slice(ep*PAGE,(ep+1)*PAGE).map(r=>`<tr><td>${esc(r.operating_point_id)} / ${r.seed}</td><td><b>${esc(r.supplier_id)}</b><br>${esc(r.lane_id)} · ${esc(r.item_id)} → ${esc(r.dst_node_id)}</td><td>${esc(mech(r.mechanism))}</td><td>${fmt(r.incident_shipment_count,0)} / ${fmt(r.target_planned_qty,0)} ${esc(r.target_uom)}</td><td>${fmt(r.effective_exposure_dose,1)} ${esc(r.effective_exposure_dose_unit)}</td><td>${fmt(r.impact_service_loss_fed_product_pp,2)} pt</td><td>${fmt(r.impact_production_loss_fed_product_qty,0)}</td><td>${fmt(r.impact_backlog_qty_days_delta,0)} unité·jour</td><td class="${r.genealogy_available?'ok':'no'}">${r.genealogy_available?'disponible · '+esc(r.detailed_replay_dossier_id):'non rejoué'}</td></tr>`).join('')};['#e-state','#e-mech','#e-search'].forEach(id=>document.querySelector(id).oninput=()=>{ep=0;renderE()});document.querySelector('#e-prev').onclick=()=>{ep=Math.max(0,ep-1);renderE()};document.querySelector('#e-next').onclick=()=>{ep++;renderE()};renderE();
function renderC(){const st=document.querySelector('#c-state').value,me=document.querySelector('#c-mech').value,q=document.querySelector('#c-search').value.toLowerCase();const rows=D.cells.filter(r=>(!st||r.operating_point_id===st)&&(!me||r.mechanism===me)&&(!q||[r.supplier_id,r.lane_id,r.item_id,r.dst_node_id,r.target_product_id].join(' ').toLowerCase().includes(q)));document.querySelector('#c-count').textContent=`${rows.length} situation(s)`;document.querySelector('#c-body').innerHTML=rows.map(r=>`<tr><td>${esc(r.operating_point_id)}<br>${fmt(r.operating_point_service_pct,1)} % global</td><td><b>${esc(r.supplier_id)}</b><br>${esc(r.lane_id)} · ${esc(r.item_id)} → ${esc(r.dst_node_id)}</td><td>${esc(mech(r.mechanism))}</td><td>${fmt(r.physical_exercise_count,0)}/30</td><td><b>${fmt(r.impact_service_loss_fed_product_pp_mean,2)} pt</b></td><td>${fmt(r.impact_service_loss_fed_product_pp_p10,2)} à ${fmt(r.impact_service_loss_fed_product_pp_p90,2)} pt</td><td>${fmt(r.impact_service_loss_fed_product_pp_ci95_low,2)} à ${fmt(r.impact_service_loss_fed_product_pp_ci95_high,2)} pt</td><td>${fmt(100*r.impact_service_loss_fed_product_pp_positive_effect_rate,0)} %</td><td>${fmt(r.impact_production_loss_fed_product_qty_mean,0)} unités<br>${fmt(r.impact_backlog_qty_days_delta_mean,0)} unité·jour</td><td class="${r.genealogy_replay_available?'ok':'no'}">${r.genealogy_available_repetition_count}/30${r.detailed_replay_dossier_id?'<br>'+esc(r.detailed_replay_dossier_id):''}</td></tr>`).join('')};['#c-state','#c-mech','#c-search'].forEach(id=>document.querySelector(id).oninput=renderC);renderC();
let gp=0;function renderJ0(dossier){const rows=D.detailedReplays.j0Rows.filter(r=>!dossier||r.dossier_id===dossier);if(!rows.length){document.querySelector('#j0').innerHTML='<p class="muted">Aucun contexte J0 de rejeu disponible.</p>';return}document.querySelector('#j0').innerHTML='<div class="grid">'+rows.map(r=>`<div class="kpi"><b>${fmt(r.incident_value_at_incident_j0,1)}</b>${esc(r.dossier_id)} · ${esc(r.metric)}<br><small>J${r.incident_j0_day} · ${esc(r.measurement_kind)} · référence ${fmt(r.baseline_value_at_incident_j0,1)}</small></div>`).join('')+'</div>'}function renderG(){const ds=document.querySelector('#g-dossier').value,st=document.querySelector('#g-stage').value,q=document.querySelector('#g-search').value.toLowerCase();const rows=D.detailedReplays.genealogyRows.filter(r=>(!ds||r.dossier_id===ds)&&(!st||r.genealogy_stage===st)&&(!q||[r.shipment_id,r.shipment_ids,r.source_lot_id,r.receipt_lot_id,r.material_lot_id,r.campaign_id,r.batch_id,r.finished_lot_id,r.client_lot_id,r.client_node_id].join(' ').toLowerCase().includes(q)));const pages=Math.max(1,Math.ceil(rows.length/PAGE));gp=Math.min(gp,pages-1);document.querySelector('#g-count').textContent=`${rows.length} ligne(s) native(s), sans troncature dans ce document`;document.querySelector('#g-page').textContent=`Page ${gp+1}/${pages}`;document.querySelector('#g-body').innerHTML=rows.slice(gp*PAGE,(gp+1)*PAGE).map(r=>`<tr><td><b>${esc(r.dossier_id)}</b><br>${esc(r.genealogy_stage)}</td><td>${r.event_day==null?'—':'J'+r.event_day}<br>${r.days_from_incident_j0==null?'':(r.days_from_incident_j0>=0?'+':'')+r.days_from_incident_j0+' j vs J0'}</td><td class="lot">${esc(r.shipment_id||r.shipment_ids||'—')}</td><td class="lot">${esc(r.receipt_lot_id||r.material_lot_id||r.source_lot_id||'—')}</td><td>${esc(r.campaign_id||'—')} / ${esc(r.batch_id||'—')}<br>encours ${r.wip_start_qty==null?'—':fmt(r.wip_start_qty,1)} → ${r.wip_end_qty==null?'—':fmt(r.wip_end_qty,1)}</td><td class="lot">${esc(r.finished_lot_id||r.released_lot_id_same_day||'—')}<br>${r.released_qty==null&&r.released_qty_same_day==null?'':fmt(r.released_qty??r.released_qty_same_day,1)+' unités'}</td><td>${esc(r.client_node_id||'—')}<br><span class="lot">${esc(r.client_lot_id||'')}</span></td></tr>`).join('');renderJ0(ds)}['#g-dossier','#g-stage','#g-search'].forEach(id=>document.querySelector(id).oninput=()=>{gp=0;renderG()});document.querySelector('#g-prev').onclick=()=>{gp=Math.max(0,gp-1);renderG()};document.querySelector('#g-next').onclick=()=>{gp++;renderG()};renderG();document.querySelector('#limits').innerHTML=D.limits.map(x=>`<li>${esc(x)}</li>`).join('');
</script></body></html>"""


def render_html(payload: Mapping[str, Any]) -> str:
    document = HTML_TEMPLATE.replace("__PAYLOAD__", _json_for_html(payload))
    if (
        document.count('class="view') != 3
        or "https://" in document
        or "http://" in document
        or re.search(
            r"<(?:script|img|iframe|link|source)\b[^>]*\b(?:src|href)\s*=",
            document,
            flags=re.IGNORECASE,
        )
        or re.search(r"(?:@import|url\s*\()", document, flags=re.IGNORECASE)
    ):
        raise IncidentLotRegistryError(
            "Le HTML autonome doit contenir exactement trois vues"
        )
    return document


def _artifact_record(path: Path, *, row_count: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "sha256": sha256_file(path),
        "sizeBytes": path.stat().st_size,
    }
    if row_count is not None:
        result["rowCount"] = row_count
    return result


def write_delivery(
    *,
    output_dir: Path,
    payload: Mapping[str, Any],
    cell_fields: Sequence[str],
    source_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically create a separate package and reject every existing target."""

    destination = output_dir.resolve()
    if destination.exists():
        raise FileExistsError(f"Refus d'écraser le dossier existant : {destination}")
    _validate_payload_contract(payload)
    if not isinstance(source_bindings, Mapping) or not source_bindings:
        raise IncidentLotRegistryError(
            "Les liaisons vers les preuves sources sont absentes"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.with_name(f".{destination.name}.building-{uuid.uuid4().hex}")
    stage.mkdir()
    try:
        exposures = list(payload.get("exposures") or [])
        cells = list(payload.get("cells") or [])
        detailed = payload.get("detailedReplays") or {}
        genealogy = list(detailed.get("genealogyRows") or [])
        j0_rows = list(detailed.get("j0Rows") or [])
        materials = {
            EXPOSURE_CSV: _csv_bytes(exposures, EXPOSURE_OUTPUT_FIELDS),
            CELL_CSV: _csv_bytes(cells, cell_fields),
            GENEALOGY_CSV: _csv_bytes(genealogy, GENEALOGY_FIELDS),
            J0_CSV: _csv_bytes(j0_rows, J0_FIELDS),
            JSON_FILE: json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
            HTML_FILE: render_html(payload).encode("utf-8"),
        }
        for name, content in materials.items():
            (stage / name).write_bytes(content)
        row_counts = {
            EXPOSURE_CSV: len(exposures),
            CELL_CSV: len(cells),
            GENEALOGY_CSV: len(genealogy),
            J0_CSV: len(j0_rows),
        }
        artifacts = {
            name: _artifact_record(stage / name, row_count=row_counts.get(name))
            for name in materials
        }
        unsigned_manifest = {
            "schemaVersion": MANIFEST_SCHEMA_VERSION,
            "status": "complete_validated_postprocessing",
            "createdAtUtc": payload.get("generatedAtUtc"),
            "sourceBindings": dict(source_bindings),
            "contract": {
                "simulationEngineRuns": 0,
                "sourceArtifactsModified": False,
                "overwriteAllowed": False,
                "signedCaseEvidenceRows": EXPECTED_TOTAL_ROWS,
                "baselineReferenceRows": EXPECTED_BASELINE_ROWS,
                "incidentExposureRows": EXPECTED_INCIDENT_ROWS,
                "cellRows": EXPECTED_CELL_ROWS,
                "detailedReplayRange": "0..3",
                "allGenealogySourceRowsRetained": True,
                "descendantLotsOnlyForDetailedReplays": True,
                "actionLotTraceAvailable": False,
                "standaloneHtmlViewCount": 3,
            },
            "artifacts": artifacts,
        }
        manifest = {
            **unsigned_manifest,
            "manifestSignature": stable_sha256(unsigned_manifest),
        }
        (stage / MANIFEST_FILE).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        validate_delivery(stage)
        stage.replace(destination)
    except Exception:
        if stage.exists() and stage.is_dir() and stage.parent == destination.parent:
            shutil.rmtree(stage)
        raise
    return validate_delivery(destination)


def validate_delivery(output_dir: Path) -> dict[str, Any]:
    root = output_dir.resolve()
    manifest = _read_json(root / MANIFEST_FILE)
    unsigned = dict(manifest)
    signature = _text(unsigned.pop("manifestSignature", ""))
    if (
        manifest.get("schemaVersion") != MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "complete_validated_postprocessing"
        or signature != stable_sha256(unsigned)
    ):
        raise IncidentLotRegistryError("Manifest de livraison invalide")
    contract = manifest.get("contract")
    source_bindings = manifest.get("sourceBindings")
    if (
        not isinstance(contract, Mapping)
        or not isinstance(source_bindings, Mapping)
        or not source_bindings
        or contract.get("simulationEngineRuns") != 0
        or contract.get("sourceArtifactsModified") is not False
        or contract.get("overwriteAllowed") is not False
        or contract.get("signedCaseEvidenceRows") != EXPECTED_TOTAL_ROWS
        or contract.get("baselineReferenceRows") != EXPECTED_BASELINE_ROWS
        or contract.get("incidentExposureRows") != EXPECTED_INCIDENT_ROWS
        or contract.get("cellRows") != EXPECTED_CELL_ROWS
        or contract.get("detailedReplayRange") != "0..3"
        or contract.get("allGenealogySourceRowsRetained") is not True
        or contract.get("descendantLotsOnlyForDetailedReplays") is not True
        or contract.get("actionLotTraceAvailable") is not False
        or contract.get("standaloneHtmlViewCount") != 3
    ):
        raise IncidentLotRegistryError("Contrat du manifeste de livraison invalide")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != {
        EXPOSURE_CSV,
        CELL_CSV,
        GENEALOGY_CSV,
        J0_CSV,
        JSON_FILE,
        HTML_FILE,
    }:
        raise IncidentLotRegistryError("Inventaire de livraison incomplet")
    for name, record in artifacts.items():
        path = root / name
        if (
            not path.is_file()
            or sha256_file(path) != _text(record.get("sha256"))
            or path.stat().st_size
            != _integer(record.get("sizeBytes"), label=f"taille {name}")
        ):
            raise IncidentLotRegistryError(f"Artefact modifié : {name}")
        if "rowCount" in record and len(_read_csv(path)[1]) != _integer(
            record.get("rowCount"), label=f"lignes {name}"
        ):
            raise IncidentLotRegistryError(f"Nombre de lignes différent : {name}")
    payload = _read_json(root / JSON_FILE)
    _validate_payload_contract(payload)
    scope = payload.get("scope") or {}
    html_document = (root / HTML_FILE).read_text(encoding="utf-8")
    if (
        payload.get("schemaVersion") != SCHEMA_VERSION
        or scope.get("incidentExposureRowCount") != EXPECTED_INCIDENT_ROWS
        or scope.get("cellRowCount") != EXPECTED_CELL_ROWS
        or scope.get("allSourceGenealogyRowsRetained") is not True
        or scope.get("descendantLotsExistOnlyForDetailedReplays") is not True
        or scope.get("actionLotTraceAvailable") is not False
        or html_document.count('class="view') != 3
        or "https://" in html_document
        or "http://" in html_document
        or html_document != render_html(payload)
    ):
        raise IncidentLotRegistryError("Contrat métier ou HTML de livraison invalide")
    exposure_fields, _ = _read_csv(root / EXPOSURE_CSV)
    cell_fields, _ = _read_csv(root / CELL_CSV)
    genealogy_fields, _ = _read_csv(root / GENEALOGY_CSV)
    j0_fields, _ = _read_csv(root / J0_CSV)
    if (
        exposure_fields != list(EXPOSURE_OUTPUT_FIELDS)
        or genealogy_fields != list(GENEALOGY_FIELDS)
        or j0_fields != list(J0_FIELDS)
        or not (set(CELL_PREFIX_FIELDS) | set(CELL_REQUIRED_FIELDS)).issubset(
            cell_fields
        )
        or (root / EXPOSURE_CSV).read_bytes()
        != _csv_bytes(payload["exposures"], EXPOSURE_OUTPUT_FIELDS)
        or (root / CELL_CSV).read_bytes() != _csv_bytes(payload["cells"], cell_fields)
        or (root / GENEALOGY_CSV).read_bytes()
        != _csv_bytes(payload["detailedReplays"]["genealogyRows"], GENEALOGY_FIELDS)
        or (root / J0_CSV).read_bytes()
        != _csv_bytes(payload["detailedReplays"]["j0Rows"], J0_FIELDS)
    ):
        raise IncidentLotRegistryError("CSV différent du JSON contrôlé")
    return {
        "valid": True,
        "outputDir": str(root),
        "manifest": str(root / MANIFEST_FILE),
        "manifestSha256": sha256_file(root / MANIFEST_FILE),
        "html": str(root / HTML_FILE),
        "htmlSha256": sha256_file(root / HTML_FILE),
        "incidentExposureRowCount": scope["incidentExposureRowCount"],
        "cellRowCount": scope["cellRowCount"],
        "availableDetailedReplayCount": scope["availableDetailedReplayCount"],
        "genealogySourceRowCount": scope["genealogySourceRowCount"],
    }


def _paths_overlap(left: Path, right: Path) -> bool:
    first = left.resolve()
    second = right.resolve()
    return first == second or first in second.parents or second in first.parents


def _validate_output_separation(
    *, output_dir: Path, source_paths: Sequence[Path | None]
) -> None:
    destination = output_dir.resolve()
    overlaps = [
        str(source.resolve())
        for source in source_paths
        if source is not None and _paths_overlap(destination, source)
    ]
    if overlaps:
        raise IncidentLotRegistryError(
            "Le dossier de sortie doit rester séparé des sources officielles : "
            + ", ".join(overlaps)
        )


def build_from_official_sources(
    *,
    campaign_root: Path,
    results_dir: Path,
    replay_root: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    _validate_output_separation(
        output_dir=output_dir,
        source_paths=(campaign_root, results_dir, replay_root),
    )
    campaign = load_official_campaign(
        campaign_root=campaign_root, results_dir=results_dir
    )
    context = campaign["context"]
    replay_data = load_available_replays(
        campaign_root=campaign_root,
        results_dir=results_dir,
        replay_root=replay_root,
        selection=campaign["selection"],
    )
    payload, cell_fields = build_payload(
        incident_rows=campaign["incidentRows"],
        official_cell_rows=campaign["cellRows"],
        official_cell_fields=campaign["cellFields"],
        lanes=context.lanes,
        requirement_modes=context.requirement_modes,
        selection=campaign["selection"],
        replay_data=replay_data,
    )
    bindings = {
        **campaign["bindings"],
        "detailedReplay": replay_data["binding"],
    }
    return write_delivery(
        output_dir=output_dir,
        payload=payload,
        cell_fields=cell_fields,
        source_bindings=bindings,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Construire le registre additif")
    build.add_argument("--campaign-root", type=Path, required=True)
    build.add_argument("--results-dir", type=Path, required=True)
    build.add_argument("--replay-root", type=Path)
    build.add_argument("--output-dir", type=Path, required=True)
    validate = subparsers.add_parser("validate", help="Revalider une livraison")
    validate.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_delivery(args.output_dir)
        else:
            result = build_from_official_sources(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                replay_root=args.replay_root,
                output_dir=args.output_dir,
            )
    except (IncidentLotRegistryError, FileExistsError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
