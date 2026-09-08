#!/usr/bin/env python3
"""Build the lightweight, offline dashboard for supplier campaign V4.

The builder is deliberately presentation-only: it reads the compact outputs of
``finalize_supplier_operating_point_full_campaign_v4.py`` and never starts the
simulation engine.  It writes one new HTML file and never mutates the source
campaign, a previous dashboard, or a network map.

The dashboard keeps three business views only:

1. supplier priority signals by simulated operating state;
2. the two declared disruption hypotheses and their simulated consequences;
3. what the compact campaign proves, and what the targeted lot replay must add.

Cross-state comparisons are enabled lane by lane only when the signed common
window registry meets its preregistered exposure-comparability threshold.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as v4_contract,
)


SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.dashboard.v4"
FINALIZER_SCHEMA_VERSION = (
    "etudecas.supplier_operating_point_full_campaign.v4.finalizer.v1"
)
CAMPAIGN_SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v4"
STATE_IDS = ("op_100", "op_93", "op_80")
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
RESULT_FILES = {
    "validation": "campaign_validation.json",
    "operating_point_registry": "state_validation_binding.json",
    "achieved_services": "operating_point_achieved_services.csv",
    "supplier_statistics": "supplier_statistics.csv",
    "lane_statistics": "lane_statistics.csv",
    "lot_replay_plan": "lot_replay_plan.json",
}
PRIORITY_FILE_CANDIDATES = (
    "priority_suppliers_by_cause_state.csv",
)
STABILITY_FILE_CANDIDATES = (
    "supplier_priority_stability_by_cause.csv",
)
DISPLAYED_PRIORITY_STATUSES = {
    "robust_priority",
    "dossier_to_investigate",
    "supplementary_backlog_signal",
}
TARGET_REGISTRY_CANDIDATES = (
    "cross_state_target_registry.json",
    "target_registry.json",
    "campaign_target_registry.json",
)
NUMERIC_TOLERANCE = 1e-12
SIGNED_OPERATING_POINT_STATUS = "accepted_v4_holdout_bound_no_rerun"


class DashboardInputError(ValueError):
    """Raised when the source package cannot support the displayed claims."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardInputError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise DashboardInputError(f"Objet JSON attendu : {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise DashboardInputError(f"CSV illisible : {path}") from exc
    if not rows:
        raise DashboardInputError(f"CSV vide : {path}")
    return rows


def _require_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise DashboardInputError(f"Fichier requis absent : {resolved}")
    return resolved


def _first_existing(root: Path, names: Sequence[str], *, label: str) -> Path:
    for name in names:
        path = root / name
        if path.is_file():
            return path.resolve()
    raise DashboardInputError(f"Fichier {label} absent (attendu : {', '.join(names)}).")


def _text(value: Any) -> str:
    if value is None:
        return ""
    result = str(value).strip()
    return "" if result.casefold() in {"nan", "none", "null"} else result


def _number(value: Any, default: float | None = None) -> float | None:
    raw = _text(value).replace("\u202f", "").replace(" ", "").replace(",", ".")
    if not raw:
        return default
    if raw.endswith("%"):
        raw = raw[:-1]
    try:
        result = float(raw)
    except ValueError:
        return default
    return result if math.isfinite(result) else default


def _integer(value: Any, default: int | None = None) -> int | None:
    number = _number(value)
    if number is None or not float(number).is_integer():
        return default
    return int(number)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).casefold() in {"1", "true", "yes", "oui", "vrai"}


def _service_pct(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return 100.0 * number if -1e-12 <= number <= 1.0 + 1e-12 else number


def _stable_payload_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    text = _text(value).casefold()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _verify_embedded_signature(
    payload: Mapping[str, Any], *, signature_field: str, label: str
) -> str:
    declared = _text(payload.get(signature_field))
    if not declared:
        raise DashboardInputError(f"{label} non signé : {signature_field} absent.")
    unsigned = {key: value for key, value in payload.items() if key != signature_field}
    if declared != _stable_payload_sha256(unsigned):
        raise DashboardInputError(f"La signature du {label} est incohérente.")
    return declared


def _required_percent(value: Any, *, label: str) -> float:
    result = _number(value)
    if result is None or not -NUMERIC_TOLERANCE <= result <= 100 + NUMERIC_TOLERANCE:
        raise DashboardInputError(f"Pourcentage absent ou hors limites : {label}.")
    return float(result)


def _signed_operating_point_services(
    registry: Mapping[str, Any], *, campaign_signature: str
) -> tuple[dict[str, dict[str, float]], str]:
    """Read achieved service solely from the accepted signed V4 binding."""

    signature = _verify_embedded_signature(
        registry,
        signature_field="binding_signature",
        label="registre final des points de fonctionnement",
    )
    if _text(registry.get("campaign_signature")) != campaign_signature:
        raise DashboardInputError(
            "Le registre final des points de fonctionnement appartient à une autre campagne."
        )
    if (
        _text(registry.get("schema_version"))
        != f"{CAMPAIGN_SCHEMA_VERSION}.state_validation_binding.v1"
        or _text(registry.get("status")) != SIGNED_OPERATING_POINT_STATUS
        or _integer(registry.get("campaign_seed_count"), -1) != 30
        or registry.get("campaign_seeds") != list(v4_contract.CAMPAIGN_SEEDS)
        or _integer(registry.get("design_seed"), -1) != 900659036
    ):
        raise DashboardInputError(
            "Le registre final des points de fonctionnement n'est pas validé."
        )
    if (
        _integer(registry.get("state_validation_engine_runs_in_campaign"), -1) != 0
        or _integer(registry.get("imported_official_service_proof_count"), -1)
        != 90
        or _integer(registry.get("imported_official_shipment_trace_count"), -1)
        != 90
        or registry.get("retuning_after_holdout") is not False
    ):
        raise DashboardInputError(
            "Le registre V4 ne prouve plus l'import exact des 90 cas sans recalage."
        )
    rows = registry.get("states")
    if not isinstance(rows, Mapping):
        raise DashboardInputError(
            "Le registre final ne contient pas les points de fonctionnement."
        )
    if set(rows) != set(STATE_IDS):
        raise DashboardInputError(
            "Le registre final signé doit contenir exactement les points 100, 93 et 80."
        )

    result: dict[str, dict[str, float]] = {}
    targets = {"op_100": 100.0, "op_93": 93.0, "op_80": 80.0}
    for state in STATE_IDS:
        row = rows[state]
        pooled = row.get("pooled") if isinstance(row, Mapping) else None
        if not isinstance(pooled, Mapping):
            raise DashboardInputError(
                f"Synthèse signée absente pour le point {state}."
            )
        result[state] = {
            "target": targets[state],
            "global": _required_percent(
                _service_pct(pooled.get("system_on_due_service")),
                label=f"service global {state}",
            ),
            "268091": _required_percent(
                _service_pct(pooled.get("on_due_service_268091")),
                label=f"service PF091 {state}",
            ),
            "268967": _required_percent(
                _service_pct(pooled.get("on_due_service_268967")),
                label=f"service PF967 {state}",
            ),
        }
    return result, signature


def _validated_achieved_services(
    rows: Sequence[Mapping[str, Any]],
    *,
    signed_services: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, Any]]:
    """Validate the compact service/provenance table against the signed binding."""

    required = {
        "operating_point_id",
        "target_service_pct",
        "achieved_global_service_pct",
        "achieved_service_268091_pct",
        "achieved_service_268967_pct",
        "global_service_bootstrap_ci95_low_pct",
        "global_service_bootstrap_ci95_high_pct",
        "degradation_family",
        "degradation_unit",
        "offset_days_268091",
        "offset_days_268967",
        "campaign_seed_count",
    }
    _required_columns(rows, required, label=RESULT_FILES["achieved_services"])
    if len(rows) != len(STATE_IDS):
        raise DashboardInputError(
            "La table des services obtenus doit contenir exactement trois états."
        )
    by_state = {_text(row.get("operating_point_id")): row for row in rows}
    if set(by_state) != set(STATE_IDS) or len(by_state) != len(rows):
        raise DashboardInputError(
            "La table des services obtenus ne porte pas les trois états attendus."
        )
    targets = {"op_100": 100.0, "op_93": 93.0, "op_80": 80.0}
    families = {
        "op_100": "baseline",
        "op_93": "balanced_product_supplier_planned_lead",
        "op_80": "balanced_product_supplier_planned_lead",
    }
    expected_unit = "planned_lead_days_added_by_finished_product_feed"
    result: dict[str, dict[str, Any]] = {}
    for state in STATE_IDS:
        row = by_state[state]
        values = {
            "target": _number(row.get("target_service_pct")),
            "global": _number(row.get("achieved_global_service_pct")),
            "268091": _number(row.get("achieved_service_268091_pct")),
            "268967": _number(row.get("achieved_service_268967_pct")),
            "ciLow": _number(row.get("global_service_bootstrap_ci95_low_pct")),
            "ciHigh": _number(row.get("global_service_bootstrap_ci95_high_pct")),
            "offset268091": _number(row.get("offset_days_268091")),
            "offset268967": _number(row.get("offset_days_268967")),
        }
        if any(value is None or not math.isfinite(float(value)) for value in values.values()):
            raise DashboardInputError(f"Valeurs de service/provenance absentes pour {state}.")
        if (
            not math.isclose(float(values["target"]), targets[state], abs_tol=NUMERIC_TOLERANCE)
            or _integer(row.get("campaign_seed_count"), -1) != 30
            or _text(row.get("degradation_family")) != families[state]
            or _text(row.get("degradation_unit")) != expected_unit
            or not 0.0 <= float(values["ciLow"]) <= float(values["ciHigh"]) <= 100.0
            or float(values["offset268091"]) < 0.0
            or float(values["offset268967"]) < 0.0
        ):
            raise DashboardInputError(f"Contrat du point de fonctionnement {state} incohérent.")
        if state == "op_100" and (
            abs(float(values["offset268091"])) > NUMERIC_TOLERANCE
            or abs(float(values["offset268967"])) > NUMERIC_TOLERANCE
        ):
            raise DashboardInputError("L'état de référence op_100 ne doit pas être dégradé.")
        for field in ("global", "268091", "268967"):
            if not math.isclose(
                float(values[field]),
                float(signed_services[state][field]),
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise DashboardInputError(
                    f"Le service publié pour {state}/{field} contredit le registre signé."
                )
        result[state] = {
            **values,
            "degradationFamily": families[state],
            "degradationUnit": expected_unit,
        }
    return result


def _median(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return float(statistics.median(clean)) if clean else None


def _required_columns(
    rows: Sequence[Mapping[str, Any]], required: set[str], *, label: str
) -> None:
    present = set(rows[0]) if rows else set()
    missing = sorted(required - present)
    if missing:
        raise DashboardInputError(
            f"Colonnes absentes dans {label} : {', '.join(missing)}"
        )


def _first_number(row: Mapping[str, Any], names: Sequence[str]) -> float | None:
    for name in names:
        value = _number(row.get(name))
        if value is not None:
            return value
    return None


def _metric_payload(
    row: Mapping[str, Any], stems: Sequence[str]
) -> dict[str, float | str | None]:
    for stem in stems:
        mean = _number(row.get(f"{stem}_mean"))
        if mean is None:
            continue
        return {
            "source": stem,
            "mean": mean,
            "median": _number(row.get(f"{stem}_median")),
            "p10": _number(row.get(f"{stem}_p10")),
            "ciLow": _number(row.get(f"{stem}_ci95_low")),
            "ciHigh": _number(row.get(f"{stem}_ci95_high")),
            "p90": _number(row.get(f"{stem}_p90")),
            "positiveRate": _number(row.get(f"{stem}_positive_effect_rate")),
        }
    return {
        "source": "",
        "mean": None,
        "median": None,
        "p10": None,
        "ciLow": None,
        "ciHigh": None,
        "p90": None,
        "positiveRate": None,
    }


def _dose_normalised_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Read the ratio-of-sums effect per 1,000 units of physical exposure."""

    stem = "impact_service_loss_fed_product_pp_per_1000_effective_dose"
    return {
        "value": _number(row.get(stem)),
        "ciLow": _number(row.get(f"{stem}_ci95_low")),
        "ciHigh": _number(row.get(f"{stem}_ci95_high")),
        "doseSum": _number(row.get("effective_exposure_dose_sum")),
        "doseUnit": _text(row.get("effective_exposure_dose_unit")),
    }


def _normalise_stat_row(
    row: Mapping[str, Any], *, supplier_level: bool
) -> dict[str, Any]:
    service = _metric_payload(
        row,
        (
            "envelope_global_service_loss_pp",
            "causal_global_service_loss_pp",
            "global_service_loss_pp",
        ),
    )
    backlog = _metric_payload(
        row,
        (
            "envelope_backlog_qty_days_per_demand_unit",
            "backlog_qty_days_per_demand_unit",
        ),
    )
    backlog_mode = "demand_days"
    if backlog["mean"] is None:
        backlog = _metric_payload(
            row, ("envelope_backlog_qty_days_delta", "backlog_qty_days_delta")
        )
        backlog_mode = "quantity_days"
    production = _metric_payload(row, ("fed_product_production_loss_share_of_demand",))
    production_mode = "demand_share"
    if production["mean"] is None:
        production = _metric_payload(row, ("fed_product_production_loss_qty",))
        production_mode = "quantity"
    fed_product_service = _metric_payload(
        row, ("impact_service_loss_fed_product_pp",)
    )
    lane_id = _text(
        (
            row.get("representative_lane_id")
            or row.get("exposed_lane_id")
            if supplier_level
            else row.get("lane_id")
        )
    )
    return {
        "state": _text(row.get("operating_point_id")),
        "stateServicePct": _service_pct(row.get("operating_point_service_pct")),
        "mechanism": _text(row.get("mechanism")),
        "supplier": _text(row.get("supplier_id")),
        "lane": lane_id,
        "item": _text(row.get("item_id")),
        "destination": _text(row.get("dst_node_id")),
        "targetProduct": _text(row.get("target_product_id")),
        "targetUom": _text(row.get("target_uom")),
        "pairedCount": _integer(row.get("paired_repetition_count"), 0),
        "exerciseRate": _number(row.get("physical_exercise_rate")),
        "service": service,
        "fedProductService": fed_product_service,
        "doseNormalisedService": _dose_normalised_payload(row),
        "backlog": backlog,
        "backlogMode": backlog_mode,
        "production": production,
        "productionMode": production_mode,
        "targetQtyMean": _number(row.get("target_planned_qty_mean")),
        "targetShipmentCountMean": _number(row.get("target_shipment_count_mean")),
        "maskedByExistingBacklogRate": _first_number(
            row,
            (
                "impact_masked_by_existing_backlog_rate",
                "baseline_saturation_rate",
                "service_loss_masked_by_existing_backlog_rate",
            ),
        ),
    }


def _locate_target_registry(results_dir: Path) -> Path | None:
    roots = (results_dir, results_dir.parent)
    for root in roots:
        for filename in TARGET_REGISTRY_CANDIDATES:
            candidate = root / filename
            if candidate.is_file():
                return candidate.resolve()
    return None


def _validate_campaign_manifest(validation: Mapping[str, Any]) -> None:
    if (
        _text(validation.get("schema_version")) != FINALIZER_SCHEMA_VERSION
        or _text(validation.get("status")) != "complete_validated"
    ):
        raise DashboardInputError(
            "La page finale exige un paquet V4 marqué complete_validated."
        )
    contract = validation.get("expected_contract")
    if not isinstance(contract, Mapping):
        raise DashboardInputError("Contrat de campagne absent du manifeste final.")
    mechanisms = {_text(value) for value in contract.get("mechanisms", [])}
    if mechanisms != set(MECHANISMS):
        raise DashboardInputError(
            "Les deux hypothèses V4 attendues ne sont pas présentes."
        )
    if _truthy(contract.get("quality_branch_included")) or _truthy(
        contract.get("availability_incident_included")
    ):
        raise DashboardInputError(
            "Le périmètre du paquet ne correspond pas à la campagne V4."
        )
    if _truthy(validation.get("historical_incident_probability_estimated")):
        raise DashboardInputError(
            "Cette page n'accepte pas une probabilité historique non séparée des simulations."
        )
    checks = validation.get("comparability_checks")
    if not isinstance(checks, Mapping):
        raise DashboardInputError("Contrôles de comparabilité absents.")
    required_checks = (
        "complete_3x18x2x30_matrix",
        "same_repetitions_in_every_cell",
        "same_engine_sha256",
        "same_campaign_signature",
        "lane_identity_invariant",
        "baseline_pairing_complete",
        "paired_warmup_state_identical",
        "shipment_set_and_incident_trace_proven",
        "v4_holdout_state_binding_signed_and_accepted",
        "v4_holdout_shipment_traces_reused_without_rerun",
        "mandatory_non_reusable_op93_smoke_validated",
    )
    failed = [key for key in required_checks if not _truthy(checks.get(key))]
    if failed:
        raise DashboardInputError(
            "Comparabilité interne incomplète : " + ", ".join(failed)
        )
    if (
        _integer(checks.get("operating_point_validation_engine_runs_in_campaign"), -1)
        != 0
    ):
        raise DashboardInputError(
            "Le paquet V4 ne conserve plus le contrat zéro rejeu des 90 cas de validation."
        )


def _target_registry_summary(
    registry: Mapping[str, Any] | None,
    *,
    campaign_signature: str,
    engine_sha256: str,
    lane_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if registry is None:
        return {}, {
            "available": False,
            "allLanesComparable": False,
            "validLaneCount": 0,
            "laneCount": len(lane_ids),
            "windowDays": None,
            "message": (
                "Registre de fenêtres communes absent : les résultats restent lisibles "
                "état par état, mais l'exposition comparable entre états n'est pas établie."
            ),
        }
    registry_campaign_signature = _text(registry.get("campaign_signature"))
    if (
        _text(registry.get("schema_version"))
        != f"{CAMPAIGN_SCHEMA_VERSION}.target_registry.v1"
        or not campaign_signature
        or registry_campaign_signature != campaign_signature
    ):
        raise DashboardInputError(
            "Le registre de fenêtres n'est pas le registre V4 signé de cette campagne."
        )
    registry_engine = _text(registry.get("engine_sha256"))
    if not engine_sha256 or registry_engine != engine_sha256:
        raise DashboardInputError(
            "Le registre de fenêtres appartient à un autre moteur."
        )
    declared_signature = _text(registry.get("registry_signature"))
    unsigned = {
        key: value for key, value in registry.items() if key != "registry_signature"
    }
    computed_signature = hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if not _is_sha256(declared_signature) or declared_signature != computed_signature:
        raise DashboardInputError(
            "La signature du registre de fenêtres est absente ou incohérente."
        )
    targets = registry.get("targets")
    coverage = registry.get("coverage")
    lane_contracts = registry.get("lane_contracts")
    if (
        registry.get("design_seed") != v4_contract.INCIDENT_DESIGN_SEED
        or registry.get("campaign_seeds") != list(v4_contract.CAMPAIGN_SEEDS)
        or registry.get("seeds") != list(v4_contract.CAMPAIGN_SEEDS)
        or registry.get("states") != list(STATE_IDS)
        or registry.get("campaign_exposure_gate_passed") is not True
    ):
        raise DashboardInputError("Le contrat scientifique du registre V4 a changé.")
    registered_lanes = registry.get("lanes")
    if (
        not isinstance(registered_lanes, list)
        or len(registered_lanes) != 18
        or len(set(map(_text, registered_lanes))) != 18
        or set(map(_text, registered_lanes)) != lane_ids
    ):
        raise DashboardInputError("Le registre V4 doit contenir exactement les 18 voies affichées.")
    if not isinstance(targets, list) or len(targets) != 3 * 30 * 18:
        raise DashboardInputError("Le registre de fenêtres ne contient aucune cible.")
    expected_target_keys = {
        (state, seed, lane)
        for state in STATE_IDS
        for seed in v4_contract.CAMPAIGN_SEEDS
        for lane in lane_ids
    }
    target_keys = {
        (
            _text(row.get("operating_point_id")),
            _integer(row.get("seed"), -1),
            _text(row.get("lane_id")),
        )
        for row in targets
        if isinstance(row, Mapping)
    }
    if target_keys != expected_target_keys or len(target_keys) != len(targets):
        raise DashboardInputError("La matrice 3 × 30 × 18 du registre V4 est incomplète.")
    if not isinstance(lane_contracts, list) or len(lane_contracts) != 18:
        raise DashboardInputError(
            "Le registre de fenêtres ne contient aucun contrôle de comparabilité."
        )
    target_windows = {
        _integer(row.get("target_window_days"), -1)
        for row in targets
        if isinstance(row, Mapping)
    }
    declared_window = _integer(registry.get("disruption_window_days"))
    if len(target_windows) != 1 or next(iter(target_windows), -1) <= 0:
        raise DashboardInputError(
            "Le registre ne porte pas une durée de fenêtre unique et positive."
        )
    window_days = next(iter(target_windows))
    if declared_window is not None and declared_window != window_days:
        raise DashboardInputError(
            "La durée déclarée du registre contredit celle de ses cibles."
        )
    comparison_by_lane: dict[str, dict[str, Any]] = {}
    if isinstance(lane_contracts, list) and lane_contracts:
        seed_count = len(registry.get("campaign_seeds", registry.get("seeds", [])))
        for source in lane_contracts:
            if not isinstance(source, Mapping):
                continue
            lane = _text(source.get("lane_id"))
            if not lane:
                continue
            comparison_by_lane[lane] = {
                "valid": _truthy(source.get("state_comparison_valid")),
                "validCount": _integer(source.get("comparable_campaign_seed_count"), 0),
                "totalCount": seed_count,
                "requiredCount": _integer(
                    source.get("required_comparable_seed_count"), 0
                ),
            }
    else:
        coverage_by_lane: dict[str, list[bool]] = defaultdict(list)
        assert isinstance(coverage, list)
        for source in coverage:
            if not isinstance(source, Mapping):
                continue
            lane = _text(source.get("lane_id"))
            if lane:
                coverage_by_lane[lane].append(
                    _truthy(source.get("state_comparison_valid"))
                )
        comparison_by_lane = {
            lane: {
                "valid": bool(values) and all(values),
                "validCount": sum(values),
                "totalCount": len(values),
                "requiredCount": len(values),
            }
            for lane, values in coverage_by_lane.items()
        }
    target_by_lane: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for source in targets:
        if not isinstance(source, Mapping):
            continue
        lane = _text(source.get("lane_id"))
        if lane:
            target_by_lane[lane].append(source)
    missing_lanes = sorted(lane_ids - set(target_by_lane))
    if missing_lanes:
        raise DashboardInputError(
            "Voies absentes du registre de fenêtres : " + ", ".join(missing_lanes)
        )
    summaries: dict[str, dict[str, Any]] = {}
    for lane in sorted(lane_ids):
        rows = target_by_lane[lane]
        comparison = comparison_by_lane.get(lane, {})
        valid_count = int(comparison.get("validCount") or 0)
        target_states: dict[str, dict[str, Any]] = {}
        for state in STATE_IDS:
            state_rows = [
                row for row in rows if _text(row.get("operating_point_id")) == state
            ]
            target_states[state] = {
                "targetCount": len(state_rows),
                "quantityMedian": _median(
                    _number(row.get("target_planned_qty")) for row in state_rows
                ),
                "shipmentCountMedian": _median(
                    _number(row.get("target_shipment_count")) for row in state_rows
                ),
                "windowStartMin": min(
                    (
                        value
                        for value in (
                            _integer(row.get("target_window_start_day"))
                            for row in state_rows
                        )
                        if value is not None
                    ),
                    default=None,
                ),
                "windowStartMax": max(
                    (
                        value
                        for value in (
                            _integer(row.get("target_window_start_day"))
                            for row in state_rows
                        )
                        if value is not None
                    ),
                    default=None,
                ),
                "item": next((_text(row.get("item_id")) for row in state_rows), ""),
                "destination": next(
                    (_text(row.get("dst_node_id")) for row in state_rows), ""
                ),
                "uom": next((_text(row.get("target_uom")) for row in state_rows), ""),
            }
        summaries[lane] = {
            "lane": lane,
            "comparisonValid": bool(comparison.get("valid")),
            "validComparisonCount": valid_count,
            "comparisonCount": int(comparison.get("totalCount") or 0),
            "requiredComparisonCount": int(comparison.get("requiredCount") or 0),
            "windowDays": window_days,
            "states": target_states,
        }
    valid_lane_count = sum(row["comparisonValid"] for row in summaries.values())
    return summaries, {
        "available": True,
        "allLanesComparable": valid_lane_count == len(lane_ids),
        "validLaneCount": valid_lane_count,
        "laneCount": len(lane_ids),
        "windowDays": window_days,
        "message": (
            f"{valid_lane_count}/{len(lane_ids)} voies atteignent le seuil d'exposition "
            f"comparable sur une fenêtre de {window_days} jours. Cette fenêtre de forte "
            "exposition est choisie voie par voie avec la graine de conception ; sa saison "
            "simulée et sa position ne représentent pas une fréquence annuelle d'incident."
        ),
    }


def _lot_replay_payload(
    plan: Mapping[str, Any],
    *,
    validation: Mapping[str, Any],
    plan_path: Path,
) -> dict[str, Any]:
    signature = _verify_embedded_signature(
        plan,
        signature_field="selection_signature",
        label="plan de rejeu ciblé des lots",
    )
    declared = validation.get("lot_replay_plan")
    output_entry = (validation.get("outputs") or {}).get("lot_replay_plan.json")
    if not isinstance(declared, Mapping) or not isinstance(output_entry, Mapping):
        raise DashboardInputError("Le manifeste final ne lie pas le plan de rejeu des lots.")
    actual_sha = _sha256_file(plan_path)
    if (
        _text(plan.get("schema_version"))
        != "etudecas.supplier_operating_point_full_campaign.v4.lot_replay_selection.v1"
        or _text(plan.get("status")) != "complete_selected"
        or _text(plan.get("campaign_signature"))
        != _text(validation.get("campaign_signature"))
        or _text(plan.get("engine_sha256")) != _text(validation.get("engine_sha256"))
        or _text(declared.get("path")) != plan_path.name
        or _text(declared.get("sha256")) != actual_sha
        or _text(declared.get("selection_signature")) != signature
        or _text(output_entry.get("sha256")) != actual_sha
        or _text(output_entry.get("selection_signature")) != signature
    ):
        raise DashboardInputError("Le plan V4 de rejeu des lots n'est pas lié au paquet final.")
    contract = plan.get("selection_contract")
    dossiers = plan.get("selected_dossiers")
    if (
        not isinstance(contract, Mapping)
        or contract.get("forced_top3") is not False
        or contract.get("one_dossier_per_cause_if_available") is not True
        or contract.get("mechanisms_kept_separate") is not True
        or contract.get("risk_paths_relative_to_campaign_root") is not True
        or contract.get("replay_executes_simulation") is not False
        or contract.get("quality_included") is not False
        or not isinstance(dossiers, list)
        or len(dossiers) > 3
        or _integer(declared.get("row_count"), -1) != len(dossiers)
        or _integer(output_entry.get("row_count"), -1) != len(dossiers)
    ):
        raise DashboardInputError("Le contrat de sélection des replays V4 a changé.")
    required = {
        "dossier_id",
        "operating_point_id",
        "mechanism",
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "target_product_id",
        "priority_status",
        "representative_seed",
        "representative_effect_pp",
        "cell_median_effect_pp",
        "valid_exercised_seed_count",
        "incident_evidence_path",
        "incident_evidence_sha256",
        "baseline_evidence_path",
        "baseline_evidence_sha256",
        "risk_csv_path",
        "risk_csv_sha256",
    }
    reduced: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in dossiers:
        if not isinstance(row, Mapping) or not required.issubset(row):
            raise DashboardInputError("Dossier de rejeu V4 incomplet.")
        dossier_id = _text(row.get("dossier_id"))
        exercised_seed_count = _integer(row.get("valid_exercised_seed_count"), -1)
        if (
            not dossier_id
            or dossier_id in seen
            or _text(row.get("operating_point_id")) not in STATE_IDS
            or _text(row.get("mechanism")) not in MECHANISMS
            or _text(row.get("priority_status"))
            not in {"robust_priority", "dossier_to_investigate"}
            or exercised_seed_count is None
            or not 1 <= exercised_seed_count <= 30
            or any(
                not _is_sha256(row.get(field))
                for field in (
                    "incident_evidence_sha256",
                    "baseline_evidence_sha256",
                    "risk_csv_sha256",
                )
            )
        ):
            raise DashboardInputError("Identité de dossier de rejeu V4 invalide.")
        for field in (
            "incident_evidence_path",
            "baseline_evidence_path",
            "risk_csv_path",
        ):
            relative = PurePosixPath(_text(row.get(field)))
            if not str(relative) or relative.is_absolute() or ".." in relative.parts:
                raise DashboardInputError("Chemin de preuve de rejeu V4 non portable.")
        seen.add(dossier_id)
        reduced.append(
            {
                "dossierId": dossier_id,
                "state": _text(row.get("operating_point_id")),
                "mechanism": _text(row.get("mechanism")),
                "lane": _text(row.get("lane_id")),
                "supplier": _text(row.get("supplier_id")),
                "item": _text(row.get("item_id")),
                "destination": _text(row.get("dst_node_id")),
                "targetProduct": _text(row.get("target_product_id")),
                "priorityStatus": _text(row.get("priority_status")),
                "representativeSeed": _integer(row.get("representative_seed")),
                "representativeEffectPp": _number(row.get("representative_effect_pp")),
                "cellMedianEffectPp": _number(row.get("cell_median_effect_pp")),
                "exercisedSeedCount": exercised_seed_count,
            }
        )
    return {
        "status": "selected_not_executed",
        "allLotsTraced": False,
        "dossierCount": len(reduced),
        "selectionSignature": signature,
        "dossiers": reduced,
        "message": (
            f"{len(reduced)} dossier(s) représentatif(s) sont sélectionnés et audités. "
            "Le rejeu détaillé avec registre de lots reste une étape séparée."
        ),
    }


def _priority_rows(
    raw_priority: Sequence[Mapping[str, Any]],
    supplier_rows: Sequence[Mapping[str, Any]],
    registry_by_lane: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    stats_by_key = {
        (row["state"], row["supplier"], row["mechanism"]): row for row in supplier_rows
    }
    priorities: list[dict[str, Any]] = []
    for source in raw_priority:
        state = _text(source.get("operating_point_id"))
        supplier = _text(source.get("supplier_id"))
        mechanism = _text(source.get("mechanism"))
        if state not in STATE_IDS or mechanism not in MECHANISMS or not supplier:
            continue
        stat = stats_by_key.get((state, supplier, mechanism))
        if stat is None:
            continue
        priority_status = _text(source.get("priority_status"))
        supplementary_backlog = priority_status == "supplementary_backlog_signal"
        if priority_status:
            if priority_status not in DISPLAYED_PRIORITY_STATUSES:
                continue
            if (
                not supplementary_backlog
                and source.get("model_effect_detected") is not None
                and not _truthy(source.get("model_effect_detected"))
            ):
                continue
        # Supplier ranks are defined by the fixed-360-day loss for the product
        # fed by the exposed lane.  Keep the complete metric family together;
        # mixing its mean/CI with global-service median/P90 would be invalid.
        service = dict(stat["fedProductService"])
        if service["mean"] is None:
            raise DashboardInputError(
                "La métrique produit qui fonde le classement V4 est absente."
            )
        alias_values = {
            "mean": _number(source.get("fixed360_effect_mean_pp")),
            "ciLow": _number(source.get("bootstrap_ci95_low")),
            "ciHigh": _number(source.get("bootstrap_ci95_high")),
        }
        for field, alias in alias_values.items():
            canonical = _number(service.get(field))
            if alias is not None and (
                canonical is None
                or not math.isclose(
                    alias, canonical, rel_tol=0.0, abs_tol=NUMERIC_TOLERANCE
                )
            ):
                raise DashboardInputError(
                    "Le classement V4 contredit sa métrique produit signée."
                )
        mean_effect = service["mean"]
        explicitly_positive = source.get("positive_mean_effect")
        if not priority_status:
            if explicitly_positive is not None and not _truthy(explicitly_positive):
                continue
            if mean_effect is None or float(mean_effect) <= NUMERIC_TOLERANCE:
                continue
        lane = _text(source.get("exposed_lane_id")) or stat["lane"]
        comparison = registry_by_lane.get(lane, {})
        registry_comparison_valid = bool(comparison.get("comparisonValid"))
        declared_comparison = source.get("state_comparison_valid")
        comparison_valid = registry_comparison_valid and (
            declared_comparison is None or _truthy(declared_comparison)
        )
        priorities.append(
            {
                **stat,
                "lane": lane,
                "service": service,
                "position": _integer(source.get("position")),
                "rankMedian": _first_number(source, ("rank_median", "position")),
                "priorityGroup": priority_status
                or _text(
                    source.get("priority_group") or source.get("selection_status")
                ),
                "supplementaryBacklogSignal": supplementary_backlog,
                "inclusionProbability": _first_number(
                    source,
                    (
                        "bootstrap_top3_inclusion_probability",
                        "top3_inclusion_probability",
                        "inclusion_probability",
                    ),
                ),
                "unambiguousTop3Probability": _first_number(
                    source,
                    (
                        "bootstrap_unambiguous_top3_probability",
                        "within_target_product_bootstrap_unambiguous_top3_probability",
                    ),
                ),
                "rankCiLow": _first_number(
                    source, ("bootstrap_rank_ci95_low", "rank_ci95_low", "rank_ci_low")
                ),
                "rankCiHigh": _first_number(
                    source,
                    ("bootstrap_rank_ci95_high", "rank_ci95_high", "rank_ci_high"),
                ),
                "comparisonValid": comparison_valid,
                "comparisonValidCount": comparison.get("validComparisonCount", 0),
                "comparisonCount": comparison.get("comparisonCount", 0),
                "horizonDependent": _truthy(source.get("horizon_dependent")),
                "maskedByExistingBacklog": _truthy(
                    source.get("impact_masked_by_existing_backlog")
                ),
            }
        )
    position_fallback: dict[tuple[str, str], int] = defaultdict(int)
    priorities.sort(
        key=lambda row: (
            STATE_IDS.index(row["state"]),
            MECHANISMS.index(row["mechanism"]),
            row["position"] if row["position"] is not None else 10**6,
            -float(row["service"]["mean"] or 0.0),
            row["supplier"],
        )
    )
    for row in priorities:
        if row["position"] is None:
            fallback_key = (str(row["state"]), str(row["mechanism"]))
            position_fallback[fallback_key] += 1
            row["position"] = position_fallback[fallback_key]
    return priorities


def _stability_payload(
    rows: Sequence[Mapping[str, Any]], priorities: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    raw_by_key = {
        (_text(row.get("mechanism")), _text(row.get("supplier_id"))): row
        for row in rows
    }
    result: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in priorities:
        grouped[(str(row["mechanism"]), str(row["supplier"]))].append(row)
    for (mechanism, supplier), supplier_rows in sorted(grouped.items()):
        source = raw_by_key.get((mechanism, supplier), {})
        states = sorted(
            {str(row["state"]) for row in supplier_rows}, key=STATE_IDS.index
        )
        if not source and not states:
            continue
        if source and any(f"in_top3_{state}" in source for state in STATE_IDS):
            states = [
                state for state in STATE_IDS if _truthy(source.get(f"in_top3_{state}"))
            ]
        insufficient_comparison = (
            _truthy(source.get("insufficient_comparable_exposure"))
            or _text(source.get("priority_status"))
            == "insufficient_comparable_exposure"
        )
        same_lane = _truthy(source.get("same_exposed_lane_across_states"))
        same_product = _truthy(
            source.get("same_target_product_for_exposed_lane_across_states")
        )
        comparison_valid = (
            _truthy(source.get("state_comparison_valid"))
            and same_lane
            and same_product
            and not insufficient_comparison
        )
        effects_by_state = {
            state: _number(source.get(f"fixed360_effect_mean_pp_{state}"))
            for state in STATE_IDS
        }
        result.append(
            {
                "supplier": supplier,
                "mechanism": mechanism,
                "states": states,
                "allStates": len(states) == len(STATE_IDS),
                "allStatesComparable": len(states) == len(STATE_IDS)
                and comparison_valid
                and all(bool(row["comparisonValid"]) for row in supplier_rows),
                "insufficientComparableExposure": insufficient_comparison,
                "sameExposedLaneAcrossStates": same_lane,
                "sameTargetProductAcrossStates": same_product,
                "comparisonLane": _text(source.get("comparison_lane_id")),
                "targetProduct": _text(
                    source.get("target_product_id_for_comparison_lane")
                ),
                "comparableSeedCount": _integer(
                    source.get("comparable_seed_count"), 0
                ),
                "requiredComparableSeedCount": _integer(
                    source.get("required_comparable_seed_count"), 0
                ),
                "effectsByState": effects_by_state,
            }
        )
    return result


def load_dashboard_data(
    *, results_dir: Path, target_registry_path: Path | None = None
) -> dict[str, Any]:
    """Load and reduce finalizer outputs into a presentation-safe payload."""

    results = results_dir.resolve()
    if not results.is_dir():
        raise DashboardInputError(f"Dossier de résultats absent : {results}")
    paths = {
        key: _require_file(results / filename) for key, filename in RESULT_FILES.items()
    }
    paths["priority"] = _first_existing(
        results, PRIORITY_FILE_CANDIDATES, label="de signaux de priorité"
    )
    paths["stability"] = _first_existing(
        results, STABILITY_FILE_CANDIDATES, label="de stabilité"
    )
    validation = _read_json(paths["validation"])
    _validate_campaign_manifest(validation)
    declared_outputs = validation.get("outputs")
    if not isinstance(declared_outputs, Mapping):
        raise DashboardInputError("Inventaire des sorties V4 absent.")
    for key in (
        "operating_point_registry",
        "achieved_services",
        "supplier_statistics",
        "lane_statistics",
        "priority",
        "stability",
        "lot_replay_plan",
    ):
        path = paths[key]
        declared = declared_outputs.get(path.name)
        if (
            not isinstance(declared, Mapping)
            or _text(declared.get("sha256")) != _sha256_file(path)
        ):
            raise DashboardInputError(f"La sortie V4 a changé : {path.name}.")
    declared_inputs = validation.get("inputs")
    if (
        not isinstance(declared_inputs, Mapping)
        or _text(declared_inputs.get("state_validation_binding_sha256"))
        != _sha256_file(paths["operating_point_registry"])
    ):
        raise DashboardInputError(
            "La copie du registre signé des points de fonctionnement a changé."
        )
    operating_point_registry = _read_json(paths["operating_point_registry"])
    operating_point_services, operating_point_registry_signature = (
        _signed_operating_point_services(
            operating_point_registry,
            campaign_signature=_text(validation.get("campaign_signature")),
        )
    )
    achieved_raw = _read_csv(paths["achieved_services"])
    achieved_services = _validated_achieved_services(
        achieved_raw,
        signed_services=operating_point_services,
    )
    supplier_raw = _read_csv(paths["supplier_statistics"])
    lane_raw = _read_csv(paths["lane_statistics"])
    priority_raw = _read_csv(paths["priority"])
    stability_raw = _read_csv(paths["stability"])
    lot_replay_plan = _read_json(paths["lot_replay_plan"])
    common_columns = {
        "operating_point_id",
        "operating_point_service_pct",
        "mechanism",
        "supplier_id",
        "item_id",
        "dst_node_id",
    }
    _required_columns(
        supplier_raw,
        common_columns | {"exposed_lane_id"},
        label=RESULT_FILES["supplier_statistics"],
    )
    _required_columns(
        lane_raw,
        common_columns | {"lane_id"},
        label=RESULT_FILES["lane_statistics"],
    )
    _required_columns(
        priority_raw,
        {"operating_point_id", "mechanism", "supplier_id"},
        label=paths["priority"].name,
    )
    mechanisms = {_text(row.get("mechanism")) for row in supplier_raw + lane_raw}
    if mechanisms != set(MECHANISMS):
        raise DashboardInputError(
            "Mécanismes inattendus dans les statistiques finales."
        )
    states = {_text(row.get("operating_point_id")) for row in supplier_raw + lane_raw}
    if states != set(STATE_IDS):
        raise DashboardInputError(
            "Les trois états simulés attendus ne sont pas complets."
        )
    suppliers = [_normalise_stat_row(row, supplier_level=True) for row in supplier_raw]
    lanes = [_normalise_stat_row(row, supplier_level=False) for row in lane_raw]
    lane_ids = {row["lane"] for row in lanes if row["lane"]}
    registry_path = (
        _require_file(target_registry_path)
        if target_registry_path is not None
        else _locate_target_registry(results)
    )
    if registry_path is not None:
        registry_sha = _sha256_file(registry_path)
        registry_output = declared_outputs.get(registry_path.name)
        if (
            _text(declared_inputs.get("target_registry_sha256")) != registry_sha
            or (
                registry_path.parent == results
                and (
                    not isinstance(registry_output, Mapping)
                    or _text(registry_output.get("sha256")) != registry_sha
                )
            )
        ):
            raise DashboardInputError(
                "Le registre V4 de fenêtres n'est plus celui validé par le finaliseur."
            )
    registry = _read_json(registry_path) if registry_path is not None else None
    registry_by_lane, registry_status = _target_registry_summary(
        registry,
        campaign_signature=_text(validation.get("campaign_signature")),
        engine_sha256=_text(validation.get("engine_sha256")),
        lane_ids=lane_ids,
    )
    priorities = _priority_rows(priority_raw, suppliers, registry_by_lane)
    state_rows = []
    for state in STATE_IDS:
        services = achieved_services[state]
        state_rows.append(
            {
                "id": state,
                "label": {
                    "op_100": "État de référence proche de 100 %",
                    "op_93": "État dégradé proche de 93 %",
                    "op_80": "État dégradé proche de 80 %",
                }[state],
                "pointLabel": state.removeprefix("op_"),
                "targetServicePct": services["target"],
                "globalServicePct": services["global"],
                "pf091ServicePct": services["268091"],
                "pf967ServicePct": services["268967"],
                "globalCiLowPct": services["ciLow"],
                "globalCiHighPct": services["ciHigh"],
                "degradationFamily": services["degradationFamily"],
                "degradationUnit": services["degradationUnit"],
                "offsetDays268091": services["offset268091"],
                "offsetDays268967": services["offset268967"],
                # Compatibility alias used by the compact view selectors.
                "servicePct": services["global"],
            }
        )
    repetitions = _integer(
        validation.get("expected_contract", {}).get("paired_repetition_count"), 0
    )
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAtUtc": _utc_now(),
        "states": state_rows,
        "mechanisms": [
            {
                "id": "transport_delay",
                "label": "Retard de transport de 120 jours",
                "shortLabel": "Retard +120 j",
                "hypothesis": (
                    "Les expéditions planifiées dans la fenêtre ciblée arrivent "
                    "120 jours plus tard."
                ),
            },
            {
                "id": "planned_delivery_shortfall",
                "label": "Baisse de 50 % de la quantité normalement livrable",
                "shortLabel": "Livrable × 50 %",
                "hypothesis": (
                    "Pendant la fenêtre ciblée, le moteur divise par deux la quantité "
                    "normalement livrable : quantité planifiée × fiabilité de référence × 50 %."
                ),
            },
        ],
        "repetitions": repetitions,
        "laneCount": len(lane_ids),
        "supplierCount": len({row["supplier"] for row in suppliers}),
        "priorities": priorities,
        "supplierStatistics": suppliers,
        "laneStatistics": lanes,
        "stability": _stability_payload(stability_raw, priorities),
        "targetRegistry": registry_status,
        "targetLanes": registry_by_lane,
        "operatingPointRegistry": {
            "validated": True,
            "sourceFile": paths["operating_point_registry"].name,
            "signature": operating_point_registry_signature,
        },
        "lotReplay": _lot_replay_payload(
            lot_replay_plan,
            validation=validation,
            plan_path=paths["lot_replay_plan"],
        ),
        "evidence": {
            "classification": _text(validation.get("evidence_class")),
            "historicalIncidentProbabilityEstimated": False,
            "industrialSupplierRatingClaimed": False,
            "campaignStatus": _text(validation.get("status")),
        },
        "modelScope": {
            "dynamicMrpPairs": 3,
            "totalMaterialSitePairs": 24,
            "customerNodesAggregated": True,
            "targetedClosedLoopAvailable": False,
        },
    }
    return payload


def _safe_json(payload: Mapping[str, Any]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Campagne fournisseurs V4 — résultats</title>
  <style>
    :root{--navy:#092747;--blue:#1768e5;--sky:#eaf3ff;--green:#11815b;--amber:#c87b0e;--red:#c93b31;--ink:#112a42;--muted:#60748a;--line:#d8e3ee;--paper:#f2f6fa;--card:#fff;--shadow:0 12px 34px #18395913}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}button,select{font:inherit}header{padding:28px clamp(18px,4vw,56px) 24px;background:linear-gradient(118deg,#071e37,#124d7e 66%,#0a746a);color:#fff}.overline{font-size:11px;font-weight:900;letter-spacing:.14em;color:#8ce4d0}h1{margin:7px 0 9px;font-size:clamp(30px,4.5vw,52px);line-height:1.05}header>p{max-width:940px;margin:0;color:#d9e8f6;font-size:17px}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.chip{padding:6px 9px;border:1px solid #ffffff42;border-radius:999px;background:#ffffff12;font-size:12px}.reading{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#cedbe8;border-bottom:1px solid #c2d1df}.definition{padding:12px clamp(12px,2.5vw,24px);background:#fff;min-height:80px}.definition b{display:block;font-size:11px;letter-spacing:.09em;color:var(--blue)}.definition span{display:block;margin-top:3px;color:#52697e;font-size:13px}.tabs{position:sticky;top:0;z-index:10;display:flex;justify-content:center;gap:8px;padding:10px;background:#f8fbffed;border-bottom:1px solid var(--line);backdrop-filter:blur(9px)}.tabs button{border:1px solid #b8cadc;border-radius:999px;background:#fff;color:#234664;padding:9px 14px;font-weight:850;cursor:pointer}.tabs button.active{color:#fff;background:var(--navy);border-color:var(--navy)}main{max-width:1300px;margin:auto;padding:20px clamp(13px,3vw,32px) 55px}.view{display:none}.view.active{display:block}.question,.callout{background:#fff;border:1px solid var(--line);border-left:6px solid var(--blue);border-radius:15px;padding:15px 17px;box-shadow:var(--shadow);margin-bottom:14px}.question b{display:block;font-size:20px}.question p,.callout p{margin:4px 0 0;color:var(--muted)}.callout.good{border-left-color:var(--green);background:#f3fbf7}.callout.warn{border-left-color:var(--amber);background:#fff9ee}.toolbar,.button-group{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.toolbar{margin:13px 0}.toolbar button,.toolbar select{border:1px solid #b8cadc;border-radius:9px;background:#fff;padding:8px 11px;color:var(--ink);font-weight:750}.toolbar button{cursor:pointer}.toolbar button.active{background:var(--blue);border-color:var(--blue);color:#fff}.toolbar-label{font-size:11px;font-weight:900;letter-spacing:.06em;color:var(--muted)}.section{margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:16px;padding:17px;box-shadow:var(--shadow)}.section h2{margin:0 0 4px;font-size:22px}.section>p{margin:0 0 12px;color:var(--muted)}.state-grid,.priority-grid,.cause-grid,.metric-grid,.action-grid{display:grid;gap:11px}.state-grid{grid-template-columns:repeat(3,1fr)}.state-card,.priority-card,.cause-card,.metric,.action{background:#fff;border:1px solid var(--line);border-radius:13px;padding:14px}.state-card{border-top:5px solid var(--blue)}.state-card h3{margin:7px 0 9px;font-size:20px}.state-kicker{font-size:10px;font-weight:900;letter-spacing:.045em;color:#6540a8}.state-global{padding:10px;border-radius:10px;background:var(--sky)}.state-global small{display:block;color:#1552a8;font-weight:850}.state-global strong{display:block;font-size:30px;color:var(--navy)}.state-products{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.state-product{padding:9px;border:1px solid var(--line);border-radius:9px}.state-product strong{display:block;font-size:20px;color:var(--navy)}.state-product small{display:block;color:var(--muted)}.state-source{margin:9px 0 0;color:var(--muted);font-size:11px}.priority-grid{grid-template-columns:repeat(3,1fr)}.priority-card{border-top:5px solid var(--blue);box-shadow:0 8px 22px #17395910}.priority-card.backlog{border-top-color:var(--amber)}.priority-card .rank{display:inline-grid;place-items:center;min-width:27px;height:27px;padding:0 6px;border-radius:14px;background:#e8f1ff;color:#1552a8;font-weight:950}.priority-card h3{display:inline;margin-left:7px;font-size:19px}.path{color:#4e657a;margin:6px 0 10px}.big{font-size:27px;font-weight:950;color:var(--navy);font-variant-numeric:tabular-nums}.label{color:var(--muted);font-size:12px}.bar-track{height:8px;border-radius:8px;background:#e5edf5;overflow:hidden;margin:7px 0}.bar{height:100%;background:linear-gradient(90deg,#f1a11b,#cb3730)}.badge{display:inline-block;border-radius:999px;padding:5px 8px;font-size:10px;font-weight:900;letter-spacing:.045em}.badge.ok{background:#e5f5ee;color:#087052}.badge.no{background:#fff0dd;color:#8b5200}.badge.sim{background:#e8f1ff;color:#1552a8}.badge.pending{background:#f0eafe;color:#6540a8}.plain{color:var(--muted);font-size:13px}.cause-grid{grid-template-columns:repeat(2,1fr)}.cause-card{border-top:5px solid var(--blue)}.cause-card h3{margin:7px 0 2px;font-size:20px}.cause-card>p{margin:4px 0;color:var(--muted)}.metric-grid{grid-template-columns:repeat(4,1fr);margin-top:12px}.metric strong{display:block;font-size:22px;color:var(--navy)}.metric small{display:block;color:var(--muted)}.uncertainty{margin-top:12px;padding:11px;border-radius:10px;background:#edf4fb;color:#274866}.explain{margin-top:10px;border-left:4px solid var(--green);padding:8px 10px;background:#eff9f5;border-radius:8px;color:#285b4d}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:11px}table{border-collapse:collapse;width:100%;min-width:850px}th,td{padding:9px 10px;border-bottom:1px solid #e5edf4;text-align:left}th{background:#edf4fb;color:#173d62;font-size:11px;letter-spacing:.025em}td{font-size:12px}.chart{display:block;width:100%;height:auto;min-height:260px;border:1px solid var(--line);border-radius:12px;background:#fbfdff}.chart text{font-family:Inter,Segoe UI,Arial,sans-serif}.chart-note{margin:8px 0 0;color:var(--muted);font-size:12px}.chart-legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px}.chart-legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}.chain{display:flex;align-items:stretch;gap:7px;overflow:auto;padding:9px 0 14px}.step{min-width:160px;flex:1;border:1px solid #ceddeb;border-radius:11px;background:#f8fbff;padding:12px}.step b{display:block;color:#14518e;margin-bottom:4px}.step.pending{border-style:dashed;background:#faf7ff}.arrow{display:grid;place-items:center;font-size:23px;color:var(--blue)}.target-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:11px}.target-card{padding:14px;border:1px solid var(--line);border-radius:13px;background:#fff}.target-card h3{margin:0 0 5px}.action-grid{grid-template-columns:repeat(3,1fr)}.action{border-top:5px solid #7c55bc}.action h3{margin:7px 0}.action p{color:var(--muted);margin:0}.stop{padding:14px;border:1px solid #e8c28b;background:#fff7e9;border-radius:12px}.stop strong{color:#855000}.empty{padding:20px;border:1px dashed #b8cadc;border-radius:12px;text-align:center;color:var(--muted)}footer{max-width:1300px;margin:0 auto;padding:0 28px 34px;color:#65788b;font-size:12px}.hidden{display:none!important}@media(max-width:950px){.reading,.priority-grid,.metric-grid{grid-template-columns:1fr 1fr}.cause-grid,.target-grid{grid-template-columns:1fr}.action-grid{grid-template-columns:1fr}}@media(max-width:620px){.reading,.state-grid,.priority-grid,.metric-grid{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}.tabs button{white-space:nowrap}}@media print{.tabs{display:none}.view{display:block!important;break-before:page}body{background:#fff}.section,.question{box-shadow:none}}
  </style>
</head>
<body>
  <header>
    <div class="overline">CAMPAGNE FOURNISSEURS V4 · SYNTHÈSE AUTONOME</div>
    <h1>Quels fournisseurs fragilisent le réseau — et pourquoi&nbsp;?</h1>
    <p>Trois états simulés du même réseau, deux incidents imposés et les mêmes 30 répétitions appariées. Cette page montre où instruire un dossier fournisseur. Elle ne mesure ni la performance historique ni la probabilité future d'un incident.</p>
    <div class="chips" id="hero-chips"></div>
  </header>
  <div class="reading" aria-label="Cadre de lecture">
    <div class="definition"><b>OBSERVÉ</b><span>Donnée réelle fournie par vos équipes. Aucune performance historique fournisseur n'est chargée ici.</span></div>
    <div class="definition"><b>SIMULÉ</b><span>Conséquence conditionnelle calculée lorsque l'incident décrit est imposé au réseau.</span></div>
    <div class="definition"><b>SIGNAL DE PRIORITÉ</b><span>Dossier fournisseur–article à instruire en premier. Ce n'est ni une note fournisseur ni une probabilité d'incident.</span></div>
    <div class="definition"><b>HYPOTHÈSE</b><span>Incident ou action déclaré dans le modèle et à calibrer avec vos historiques.</span></div>
  </div>
  <nav class="tabs" aria-label="Trois vues">
    <button class="active" data-view="priority" aria-current="page">1 · Priorités</button>
    <button data-view="causes">2 · Causes et effets</button>
    <button data-view="lots">3 · Propagation, lots et actions</button>
  </nav>
  <main>
    <section class="view active" id="view-priority">
      <div class="question"><b>Retrouve-t-on les mêmes fournisseurs quand le réseau se dégrade&nbsp;?</b><p>La lecture inter-états reste conditionnelle : elle n'est affichée que pour la même voie et le même produit, sur les répétitions qui atteignent le seuil d'exposition comparable défini avant l'analyse.</p></div>
      <div class="state-grid" id="state-cards"></div>
      <div class="section"><h2>Services obtenus et incertitude de simulation</h2><p>Le point représente le service agrégé sur 30 répétitions. La barre verticale est l'intervalle bootstrap à 95&nbsp;% du service global ; les deux produits finis sont montrés séparément.</p><svg id="service-chart" class="chart" viewBox="0 0 960 330" role="img" aria-label="Services simulés des trois états avec intervalles"></svg><div class="chart-legend"><span><i style="background:#1768e5"></i>Global</span><span><i style="background:#11815b"></i>Produit 268091</span><span><i style="background:#c87b0e"></i>Produit 268967</span></div></div>
      <div id="comparison-callout" class="callout"></div>
      <div class="section"><h2>Signaux de priorité par état simulé et par cause</h2><p>Les deux incidents ne sont jamais mélangés dans un même rang. Un effet nul n'est pas promu pour compléter artificiellement un trio&nbsp;; un signal fondé seulement sur le retard cumulé est identifié séparément.</p><div class="toolbar"><span class="toolbar-label">ÉTAT</span><div class="button-group" id="priority-state-buttons"></div><span class="toolbar-label">CAUSE</span><div class="button-group" id="priority-mechanism-buttons"></div></div><div class="priority-grid" id="priority-cards"></div></div>
      <div class="section"><h2>Dispersion des principaux signaux</h2><p>Moyenne, P10–P90 et intervalle bootstrap à 95&nbsp;% de la perte de service du produit alimenté. Le pourcentage « groupe de tête » décrit les rééchantillonnages statistiques, jamais la probabilité de l'incident.</p><svg id="forest-chart" class="chart" viewBox="0 0 960 390" role="img" aria-label="Forest plot des principaux signaux fournisseurs"></svg></div>
      <div class="section"><h2>Lecture conditionnelle sur les trois états</h2><p>Une ligne n'est tracée que si la voie exposée et le produit alimenté sont identiques dans les trois états. Les deux causes restent séparées. Cette lecture est admissible selon le seuil d'exposition, mais les doses ne sont pas identiques&nbsp;: il s'agit d'une sensibilité conditionnelle du modèle, pas d'une comparaison industrielle validée.</p><svg id="slope-chart" class="chart" viewBox="0 0 1040 430" role="img" aria-label="Évolution conditionnelle des signaux entre états, séparée par cause"></svg><div id="stability-reading"></div></div>
    </section>

    <section class="view" id="view-causes">
      <div class="question"><b>Pour un fournisseur donné, quel incident propage un effet vers l'aval&nbsp;?</b><p>Chaque incident imposé est comparé à sa référence avec la même répétition. L'impact total sur 360 jours et l'intensité rapportée à la dose physique sont affichés séparément.</p></div>
      <div class="toolbar"><label for="cause-state">État&nbsp;</label><select id="cause-state"></select><label for="cause-supplier">Fournisseur&nbsp;</label><select id="cause-supplier"></select></div>
      <div class="cause-grid" id="cause-cards"></div>
      <div class="callout warn"><b>Deux tests distincts, pas une échelle commune.</b><p>Le retard de 120 jours et la baisse de 50&nbsp;% de la quantité normalement livrable (plan × fiabilité) ne sont pas calibrés à une même gravité. On classe les fournisseurs à l'intérieur de chaque test&nbsp;; leurs amplitudes brutes ne disent pas qu'un incident est plus probable ou plus grave que l'autre.</p></div>
      <div class="section"><h2>Voies physiques du fournisseur sélectionné</h2><p>Le détail évite d'additionner des articles différents. Chaque ligne reste une voie fournisseur–article–site ; l'intensité par dose ne remplace pas l'impact total.</p><div class="table-wrap"><table><thead><tr><th>Voie</th><th>Article → site</th><th>Hypothèse</th><th>Impact total produit</th><th>Impact / 1&nbsp;000 unités de dose</th><th>Retard cumulé normalisé</th><th>Production non libérée</th><th>Exposition inter-états</th></tr></thead><tbody id="lane-table"></tbody></table></div></div>
      <div class="callout warn"><b>Ce que l'incertitude ne dit pas.</b><p>Le cas défavorable et l'intervalle à 95&nbsp;% décrivent les répétitions du modèle. Ils ne donnent pas la fréquence future d'un incident chez le fournisseur.</p></div>
    </section>

    <section class="view" id="view-lots">
      <div class="question"><b>Peut-on suivre la propagation aval jusqu'aux lots et décider d'une action&nbsp;?</b><p>La campagne compacte prouve la cible d'expédition et les effets réseau. Ce n'est pas une cascade de risques endogènes&nbsp;: un incident exogène unique se propage dans les stocks, encours, production et service.</p></div>
      <div id="replay-selection-callout" class="callout"></div>
      <div class="toolbar"><label for="lot-state">État&nbsp;</label><select id="lot-state"></select><label for="lot-supplier">Signal&nbsp;</label><select id="lot-supplier"></select></div>
      <div class="target-grid" id="target-summary"></div>
      <div class="callout warn"><b>Périmètre dynamique actuel</b><p>Stocks, transits, encours et retards évoluent jour après jour. Le besoin MRP lié explicitement à la demande ne couvre toutefois que 3 couples matière–site sur 24&nbsp;; les 21 autres couples ne doivent pas être présentés comme une chaîne MRP dynamique complète.</p></div>
      <div class="section"><h2>Chaîne de preuve de propagation</h2><p>Le replay ajoute la généalogie des lots. Les sorties clients restent des nœuds agrégés C-XXXXX&nbsp;: aucun client réel ni aucune commande réelle n'est identifié.</p><div class="chain"><div class="step"><b>1 · Fenêtre ciblée</b><span id="chain-target"></span></div><div class="arrow">→</div><div class="step"><b>2 · Stock et encours</b>Effet physique recalculé jour après jour.</div><div class="arrow">→</div><div class="step"><b>3 · Production</b>Quantité libérée et manque agrégés dans la campagne.</div><div class="arrow">→</div><div class="step pending"><b>4 · Lots finis</b>Identifiants et généalogie à extraire du replay.</div><div class="arrow">→</div><div class="step pending"><b>5 · Nœuds clients</b>C-XXXXX agrégés, sans identité de client réel.</div></div></div>
      <div class="section"><h2>Actionneurs réellement disponibles ou à préparer</h2><p>Aucune efficacité n'est annoncée avant une comparaison appariée avec le même incident sans action.</p><div class="action-grid"><article class="action"><span class="badge ok">NATIF · J0 UNIQUEMENT</span><h3>Stock ciblé initial</h3><p>Le moteur sait ajouter un stock libre à J0 sur un article et un site définis. Cela représente une protection préparée avant l'incident, pas un réapprovisionnement décidé en cours de simulation.</p></article><article class="action"><span class="badge pending">BOUCLE OUVERTE</span><h3>Réduire le délai des futurs départs</h3><p>L'action de transport modifie le délai des expéditions qui partiront après son activation. Elle n'accélère pas magiquement une expédition déjà en transit et son calendrier est fixé à l'avance.</p></article><article class="action"><span class="badge no">MULTISOURCING SEULEMENT</span><h3>Poids de priorité d'achat</h3><p><code>priority_weight</code> arbitre les achats entre voies actives d'un même besoin multisourcé. Il ne priorise ni ordre de fabrication ni commande client et n'est pas une seconde source fictive.</p></article></div></div>
      <div class="stop"><strong>Limites à dire au client :</strong> le pilotage ciblé en boucle fermée n'est pas disponible dans cette campagne. Tant que le replay détaillé n'est pas terminé, la page ne nomme aucun lot industriel ; même après replay, les clients restent des nœuds agrégés C-XXXXX. Elle sélectionne les dossiers où cette investigation apporte le plus de valeur.</div>
    </section>
  </main>
  <footer>Page autonome hors ligne · résultats conditionnels du simulateur · aucune connexion réseau nécessaire.</footer>
  <script id="campaign-data" type="application/json">__DATA__</script>
  <script>
  (()=>{"use strict";
    const data=JSON.parse(document.getElementById("campaign-data").textContent);
    const $=id=>document.getElementById(id);
    const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const n=value=>value===null||value===undefined||value===""?null:(Number.isFinite(Number(value))?Number(value):null);
    const fmt=(value,digits=1)=>n(value)==null?"—":Number(value).toLocaleString("fr-FR",{minimumFractionDigits:digits,maximumFractionDigits:digits});
    const pct=value=>n(value)==null?"—":`${fmt(100*n(value),0)} %`;
    const pp=value=>n(value)==null?"—":`${fmt(value,2)} point${Math.abs(Number(value))>1?"s":""}`;
    const state=id=>data.states.find(item=>item.id===id)||data.states[0];
    const mechanism=id=>data.mechanisms.find(item=>item.id===id)||data.mechanisms[0];
    const stateLabel=id=>`${state(id).label} · ${fmt(state(id).globalServicePct,1)} % global`;
    const metricCi=metric=>metric&&n(metric.ciLow)!=null&&n(metric.ciHigh)!=null?`${pp(metric.ciLow)} à ${pp(metric.ciHigh)}`:"non calculé";
    const registryFor=lane=>data.targetLanes[lane]||null;
    const comparisonBadge=value=>{const row=typeof value==="object"?value:null,lane=row?row.lane:value,r=registryFor(lane),valid=Boolean(r&&r.comparisonValid&&(row==null||row.comparisonValid!==false));return valid?`<span class="badge ok">LECTURE ADMISSIBLE, DOSES NON IDENTIQUES · ${r.validComparisonCount}/${r.comparisonCount} (seuil ${r.requiredComparisonCount})</span>`:`<span class="badge no">LECTURE INTER-ÉTATS NON ADMISSIBLE</span>`};
    const priorityLabel=row=>({robust_priority:"PRIORITÉ ROBUSTE",dossier_to_investigate:"DOSSIER À INSTRUIRE",supplementary_backlog_signal:"SIGNAL BACKLOG COMPLÉMENTAIRE"}[row.priorityGroup]||"SIGNAL DE PRIORITÉ");
    const rankEvidence=row=>{const parts=[];if(n(row.inclusionProbability)!=null)parts.push(`groupe de tête dans ${pct(row.inclusionProbability)} des rééchantillonnages — pas une probabilité d'incident`);if(n(row.rankCiLow)!=null&&n(row.rankCiHigh)!=null)parts.push(`rang plausible ${fmt(row.rankCiLow,0)} à ${fmt(row.rankCiHigh,0)}`);return parts.length?`<p class="plain"><b>Stabilité statistique :</b> ${parts.join(" · ")}.</p>`:""};
    const backlogValue=row=>row.backlogMode==="demand_days"?`${fmt(row.backlog.mean,2)} jour(s) de demande`:`${fmt(row.backlog.mean,0)} unités × jours`;
    const productionValue=row=>row.productionMode==="demand_share"?pct(row.production.mean):`${fmt(row.production.mean,0)} ${esc(row.targetUom||"unités")}`;
    const doseUnit=unit=>unit==="unite_jour_de_retard"?"unités·jour de retard":unit==="unite_non_livree"?"unités non livrées":"unités de dose";
    const doseValue=row=>n(row.doseNormalisedService.value)==null?"non calculé":`${pp(row.doseNormalisedService.value)} / 1 000 ${doseUnit(row.doseNormalisedService.doseUnit)}`;
    const explanation=row=>{const metric=row.fedProductService||row.service,effect=n(metric.mean)||0,rate=n(metric.positiveRate);if(effect<=1e-12)return"Aucune perte moyenne mesurable dans ces simulations : ce dossier ne doit pas être présenté comme prioritaire.";if(rate!=null&&rate<.7)return`L'effet existe en moyenne, mais seulement dans ${fmt(100*rate,0)} % des répétitions : il dépend fortement de l'état du réseau.`;if(n(row.maskedByExistingBacklogRate)>0)return"Le retard ou le manque augmente, mais une partie de la perte de service peut être masquée par un retard déjà présent dans la référence.";return"L'incident imposé se propage dans les stocks et la production jusqu'au service du nœud client agrégé dans la majorité des répétitions simulées."};
    const svgEmpty=(svg,text)=>{svg.innerHTML=`<text x="50%" y="50%" text-anchor="middle" fill="#60748a" font-size="14">${esc(text)}</text>`};
    const renderServiceChart=()=>{const svg=$("service-chart"),W=960,H=330,left=75,right=25,top=30,bottom=82,values=data.states.flatMap(row=>[row.globalCiLowPct,row.globalCiHighPct,row.globalServicePct,row.pf091ServicePct,row.pf967ServicePct].map(n).filter(value=>value!=null));if(!values.length){svgEmpty(svg,"Services non disponibles");return}let ymin=Math.max(0,Math.floor((Math.min(...values)-2)/5)*5),ymax=Math.min(100,Math.ceil((Math.max(...values)+1)/5)*5);if(ymax-ymin<5)ymin=Math.max(0,ymax-5);const y=value=>top+(ymax-value)*(H-top-bottom)/(ymax-ymin),x=index=>left+(index+.5)*(W-left-right)/data.states.length;let out="";for(let i=0;i<=5;i++){const value=ymin+(ymax-ymin)*i/5,yy=y(value);out+=`<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" stroke="#d8e3ee"/><text x="${left-10}" y="${yy+4}" text-anchor="end" fill="#60748a" font-size="11">${fmt(value,1)} %</text>`}data.states.forEach((row,index)=>{const xx=x(index),low=n(row.globalCiLowPct),high=n(row.globalCiHighPct);out+=`<text x="${xx}" y="${H-50}" text-anchor="middle" fill="#112a42" font-size="12" font-weight="700">${esc(row.pointLabel)} %</text>`;out+=`<text x="${xx}" y="${H-31}" text-anchor="middle" fill="#60748a" font-size="10">${row.degradationFamily==="baseline"?"référence":`+${fmt(row.offsetDays268091,0)} j PF091 · +${fmt(row.offsetDays268967,0)} j PF967`}</text>`;if(low!=null&&high!=null)out+=`<line x1="${xx-14}" y1="${y(low)}" x2="${xx-14}" y2="${y(high)}" stroke="#1768e5" stroke-width="4" stroke-linecap="round"/>`;[[row.globalServicePct,-14,"#1768e5"],[row.pf091ServicePct,0,"#11815b"],[row.pf967ServicePct,14,"#c87b0e"]].forEach(([value,dx,color])=>{if(n(value)!=null)out+=`<circle cx="${xx+dx}" cy="${y(n(value))}" r="6" fill="${color}"><title>${esc(row.label)} : ${fmt(value,2)} %</title></circle>`})});svg.innerHTML=out};
    const renderSlopeChart=()=>{const svg=$("slope-chart"),W=1040,H=430,facetW=520,palette=["#1768e5","#11815b","#c87b0e","#7c55bc","#c93b31","#3889a8"];let out="";data.mechanisms.forEach((m,facet)=>{const x0=facet*facetW,rows=data.stability.filter(row=>row.mechanism===m.id&&row.allStatesComparable&&row.sameExposedLaneAcrossStates&&row.sameTargetProductAcrossStates&&data.states.every(s=>n(row.effectsByState[s.id])!=null)).sort((a,b)=>Math.max(...Object.values(b.effectsByState).map(Number))-Math.max(...Object.values(a.effectsByState).map(Number))).slice(0,6);out+=`<text x="${x0+facetW/2}" y="24" text-anchor="middle" fill="#112a42" font-size="14" font-weight="800">${esc(m.shortLabel)}</text>`;if(!rows.length){out+=`<text x="${x0+facetW/2}" y="205" text-anchor="middle" fill="#60748a" font-size="12">Aucune série même voie + même produit admissible</text>`;return}const maximum=Math.max(0.01,...rows.flatMap(row=>Object.values(row.effectsByState).map(value=>Number(value)||0)))*1.12,xs=[x0+90,x0+250,x0+410],y=value=>55+(maximum-value)*285/maximum;for(let i=0;i<=4;i++){const value=maximum*i/4,yy=y(value);out+=`<line x1="${x0+62}" y1="${yy}" x2="${x0+438}" y2="${yy}" stroke="#e1e9f1"/><text x="${x0+55}" y="${yy+4}" text-anchor="end" fill="#60748a" font-size="10">${fmt(value,1)}</text>`}data.states.forEach((s,i)=>out+=`<text x="${xs[i]}" y="365" text-anchor="middle" fill="#60748a" font-size="10">${esc(s.pointLabel)} %</text>`);rows.forEach((row,index)=>{const color=palette[index%palette.length],points=data.states.map((s,i)=>`${xs[i]},${y(Number(row.effectsByState[s.id]))}`).join(" "),label=String(row.supplier).slice(0,15);out+=`<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5" opacity=".9"><title>${esc(row.supplier)} · ${esc(row.comparisonLane)} · produit ${esc(row.targetProduct)} · ${row.comparableSeedCount}/30 répétitions comparables</title></polyline>`;data.states.forEach((s,i)=>out+=`<circle cx="${xs[i]}" cy="${y(Number(row.effectsByState[s.id]))}" r="4" fill="${color}"/>`);out+=`<text x="${x0+416}" y="${y(Number(row.effectsByState.op_80))-6}" fill="${color}" font-size="9">${esc(label)}</text>`});out+=`<text x="${x0+250}" y="397" text-anchor="middle" fill="#60748a" font-size="10">Perte de service produit (points) · même voie et même produit</text>`});out+=`<line x1="520" y1="8" x2="520" y2="410" stroke="#cbd8e5"/>`;svg.innerHTML=out};
    const renderForestChart=()=>{const svg=$("forest-chart"),W=960,H=390,left=235,right=105,top=46,bottom=45,rows=data.priorities.filter(row=>row.state===priorityState&&row.mechanism===priorityMechanism&&!row.supplementaryBacklogSignal&&n(row.service.mean)!=null).sort((a,b)=>(a.position??999)-(b.position??999)||(n(b.service.mean)||0)-(n(a.service.mean)||0)).slice(0,8);if(!rows.length){svgEmpty(svg,"Aucun signal de service à représenter");return}const values=rows.flatMap(row=>[row.service.p10,row.service.p90,row.service.ciLow,row.service.ciHigh,row.service.mean].map(n).filter(value=>value!=null)),xmin=Math.min(0,...values),xmax=Math.max(.01,...values)*1.08,x=value=>left+(value-xmin)*(W-left-right)/(xmax-xmin),gap=(H-top-bottom)/rows.length;let out=`<text x="${left}" y="22" fill="#112a42" font-size="12" font-weight="800">P10–P90 (fin) · IC95 (épais) · moyenne (point)</text><text x="${W-98}" y="22" fill="#112a42" font-size="11" font-weight="800">Groupe de tête*</text>`;for(let i=0;i<=5;i++){const value=xmin+(xmax-xmin)*i/5,xx=x(value);out+=`<line x1="${xx}" y1="${top-8}" x2="${xx}" y2="${H-bottom}" stroke="#e1e9f1"/><text x="${xx}" y="${H-20}" text-anchor="middle" fill="#60748a" font-size="10">${fmt(value,1)}</text>`}rows.forEach((row,index)=>{const yy=top+gap*(index+.5),metric=row.service,p10=n(metric.p10)??n(metric.mean),p90=n(metric.p90)??n(metric.mean),low=n(metric.ciLow)??n(metric.mean),high=n(metric.ciHigh)??n(metric.mean),mean=n(metric.mean);out+=`<text x="${left-10}" y="${yy+4}" text-anchor="end" fill="#112a42" font-size="11">${esc(String(row.supplier).slice(0,24))} · ${esc(row.targetProduct||row.item)}</text><line x1="${x(p10)}" y1="${yy}" x2="${x(p90)}" y2="${yy}" stroke="#60748a" stroke-width="2"/><line x1="${x(low)}" y1="${yy}" x2="${x(high)}" y2="${yy}" stroke="#1768e5" stroke-width="7" stroke-linecap="round" opacity=".42"/><circle cx="${x(mean)}" cy="${yy}" r="5" fill="#092747"><title>Moyenne ${fmt(mean,3)} · P10 ${fmt(p10,3)} · P90 ${fmt(p90,3)} · IC95 ${fmt(low,3)} à ${fmt(high,3)}</title></circle><text x="${W-52}" y="${yy+4}" text-anchor="middle" fill="#112a42" font-size="10">${pct(row.inclusionProbability)}</text>`});out+=`<text x="${W-10}" y="${H-6}" text-anchor="end" fill="#60748a" font-size="9">* fréquence de classement au bootstrap, pas probabilité d'incident</text>`;svg.innerHTML=out};
    const setView=(id,updateHash=true)=>{document.querySelectorAll(".view").forEach(node=>node.classList.toggle("active",node.id===`view-${id}`));document.querySelectorAll(".tabs button").forEach(button=>{const active=button.dataset.view===id;button.classList.toggle("active",active);if(active)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current")});if(updateHash)history.replaceState(null,"",`#${id}`);window.scrollTo({top:0,behavior:"smooth"})};
    document.querySelectorAll(".tabs button").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
    $("hero-chips").innerHTML=`<span class="chip">${data.states.length} états simulés</span><span class="chip">${data.laneCount} voies physiques</span><span class="chip">${data.repetitions} répétitions appariées</span><span class="chip">2 incidents hypothétiques</span><span class="chip">aucune probabilité d'incident estimée</span>`;
    const degradationText=item=>item.degradationFamily==="baseline"?"Référence sans dégradation ajoutée":`Délais fournisseurs planifiés ajoutés : +${fmt(item.offsetDays268091,0)} j vers PF091 · +${fmt(item.offsetDays268967,0)} j vers PF967`;
    $("state-cards").innerHTML=data.states.map(item=>`<article class="state-card"><div class="state-kicker">HYPOTHÈSE · POINT ${esc(item.pointLabel)} · CIBLE DE CALIBRATION ${fmt(item.targetServicePct,1)} %</div><h3>${esc(item.label)}</h3><div class="state-global"><small>SIMULÉ · TAUX DE SERVICE GLOBAL OBTENU</small><strong>${fmt(item.globalServicePct,1)} %</strong><small>IC bootstrap 95 % : ${fmt(item.globalCiLowPct,1)} à ${fmt(item.globalCiHighPct,1)} %</small></div><div class="state-products"><div class="state-product"><small>SIMULÉ · PF091 (268091)</small><strong>${fmt(item.pf091ServicePct,1)} %</strong></div><div class="state-product"><small>SIMULÉ · PF967 (268967)</small><strong>${fmt(item.pf967ServicePct,1)} %</strong></div></div><p class="state-source"><b>${esc(degradationText(item))}.</b> Famille de configuration : ${esc(item.degradationFamily)}. Ces valeurs viennent du holdout V4 signé.</p></article>`).join("");
    renderServiceChart();renderSlopeChart();
    const reg=data.targetRegistry,comparison=$("comparison-callout");comparison.className=`callout ${reg.allLanesComparable?"good":"warn"}`;comparison.innerHTML=`<b>${reg.allLanesComparable?"Lecture inter-états admissible sur les 18 voies":"Lecture inter-états non admissible sur certaines voies"}</b><p>${esc(reg.message)} Les doses physiques ne sont pas rendues identiques entre états : l'impact total et l'impact normalisé par dose restent donc deux lectures séparées. Ce n'est ni une validation sur historique industriel ni une fréquence d'incident.</p>`;
    let priorityState=data.states[0].id,priorityMechanism=data.mechanisms[0].id;
    const renderPriority=()=>{$("priority-state-buttons").innerHTML=data.states.map(item=>`<button class="${item.id===priorityState?"active":""}" data-state="${esc(item.id)}">${esc(item.label)}</button>`).join("");$("priority-state-buttons").querySelectorAll("button").forEach(button=>button.onclick=()=>{priorityState=button.dataset.state;renderPriority()});$("priority-mechanism-buttons").innerHTML=data.mechanisms.map(item=>`<button class="${item.id===priorityMechanism?"active":""}" data-mechanism="${esc(item.id)}">${esc(item.shortLabel)}</button>`).join("");$("priority-mechanism-buttons").querySelectorAll("button").forEach(button=>button.onclick=()=>{priorityMechanism=button.dataset.mechanism;renderPriority()});const rows=data.priorities.filter(row=>row.state===priorityState&&row.mechanism===priorityMechanism);const max=Math.max(...rows.map(row=>row.supplementaryBacklogSignal?Math.max(0,n(row.backlog.mean)||0):Math.max(0,n(row.service.mean)||0)),1e-9);$("priority-cards").innerHTML=rows.length?rows.map(row=>{const signal=row.supplementaryBacklogSignal?n(row.backlog.mean)||0:n(row.service.mean)||0,value=row.supplementaryBacklogSignal?backlogValue(row):pp(row.service.mean),label=row.supplementaryBacklogSignal?"retard cumulé supplémentaire, sans perte de service prouvée":"impact total moyen sur le service du produit alimenté (360 j)",uncertainty=row.supplementaryBacklogSignal?"Ce signal complète l'analyse du service ; il ne prouve pas à lui seul une perte client.":`P10–P90 : ${pp(row.service.p10)} à ${pp(row.service.p90)} · IC95 : ${metricCi(row.service)}.`;return`<article class="priority-card ${row.supplementaryBacklogSignal?"backlog":""}"><span class="rank">${n(row.rankMedian)!=null?fmt(row.rankMedian,0):row.position}</span><h3>${esc(row.supplier)}</h3><p><span class="badge ${row.priorityGroup==="robust_priority"?"ok":row.supplementaryBacklogSignal?"no":"sim"}">${priorityLabel(row)}</span></p><p class="path">Voie ${esc(row.lane)} · article ${esc(row.item)} → ${esc(row.destination)} · produit cible ${esc(row.targetProduct||"—")}<br><small>${esc(mechanism(row.mechanism).shortLabel)}</small></p><div class="big">${value}</div><div class="label">${label}</div><div class="bar-track"><div class="bar" style="width:${Math.min(100,100*Math.max(0,signal)/max)}%"></div></div><p class="plain">${uncertainty}</p>${rankEvidence(row)}${row.horizonDependent?'<p class="plain"><b>Attention :</b> résultat sensible à la durée observée.</p>':""}${comparisonBadge(row)}</article>`}).join(""):`<div class="empty">Aucun signal retenu pour cette cause dans cet état.</div>`;const stable=data.stability.filter(row=>row.mechanism===priorityMechanism&&row.allStates),qualified=stable.filter(row=>row.allStatesComparable);$("stability-reading").innerHTML=qualified.length?`<div class="callout good"><b>${qualified.length} fournisseur(s) gardent un signal dans les trois états sur la même voie et le même produit.</b><p>${qualified.map(row=>`${esc(row.supplier)} (${esc(row.comparisonLane)}, produit ${esc(row.targetProduct)}, ${row.comparableSeedCount}/30 répétitions comparables)`).join(" · ")}. C'est une stabilité conditionnelle du modèle, pas une note fournisseur.</p></div>`:stable.length?`<div class="callout warn"><b>Le signal apparaît dans les trois états, mais les conditions même voie + même produit + exposition comparable ne sont pas toutes réunies.</b><p>Les états doivent rester présentés séparément.</p></div>`:`<div class="callout warn"><b>Le groupe de priorité change selon l'état simulé pour ${esc(mechanism(priorityMechanism).shortLabel)}.</b><p>Le contexte du réseau modifie la transmission de l'impact.</p></div>`;renderForestChart()};renderPriority();
    ["cause-state","lot-state"].forEach(id=>{$(id).innerHTML=data.states.map(item=>`<option value="${esc(item.id)}">${esc(stateLabel(item.id))}</option>`)});
    const suppliersFor=stateId=>[...new Set(data.supplierStatistics.filter(row=>row.state===stateId).map(row=>row.supplier))].sort();
    const prioritySuppliersFor=stateId=>[...new Set(data.priorities.filter(row=>row.state===stateId).sort((a,b)=>a.position-b.position).map(row=>row.supplier))];
    const fillSupplierSelect=(select,stateId,priorityOnly=false)=>{const first=prioritySuppliersFor(stateId),candidates=priorityOnly?first:[...first,...suppliersFor(stateId).filter(value=>!first.includes(value))];select.innerHTML=candidates.map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join("")};
    const causeState=$("cause-state"),causeSupplier=$("cause-supplier");fillSupplierSelect(causeSupplier,causeState.value);
    const renderCauses=()=>{const stateId=causeState.value,supplier=causeSupplier.value,rows=data.supplierStatistics.filter(row=>row.state===stateId&&row.supplier===supplier);$("cause-cards").innerHTML=data.mechanisms.map(m=>{const row=rows.find(item=>item.mechanism===m.id);if(!row)return`<article class="cause-card"><h3>${esc(m.label)}</h3><div class="empty">Résultat absent.</div></article>`;const exercised=Math.round((n(row.exerciseRate)||0)*(n(row.pairedCount)||0));return`<article class="cause-card"><span class="badge sim">HYPOTHÈSE CONDITIONNELLE</span><h3>${esc(m.label)}</h3><p>${esc(m.hypothesis)}</p><div class="metric-grid"><div class="metric"><strong>${pp(row.fedProductService.mean)}</strong><small>impact total moyen sur le service du produit ${esc(row.targetProduct)}</small></div><div class="metric"><strong>${doseValue(row)}</strong><small>intensité normalisée par dose physique</small></div><div class="metric"><strong>${backlogValue(row)}</strong><small>retard cumulé / demande</small></div><div class="metric"><strong>${productionValue(row)}</strong><small>production du produit non libérée</small></div></div><div class="uncertainty"><b>Dispersion de l'impact total :</b> P10 ${pp(row.fedProductService.p10)} · P90 ${pp(row.fedProductService.p90)} · IC95 ${metricCi(row.fedProductService)} · incident physiquement exercé dans ${exercised}/${row.pairedCount} répétitions.</div><div class="explain"><b>Lecture métier :</b> ${esc(explanation(row))}</div></article>`}).join("");const laneRows=data.laneStatistics.filter(row=>row.state===stateId&&row.supplier===supplier).sort((a,b)=>(n(b.fedProductService.mean)||0)-(n(a.fedProductService.mean)||0));$("lane-table").innerHTML=laneRows.map(row=>`<tr><td>${esc(row.lane)}</td><td>${esc(row.item)} → ${esc(row.destination)}<br><small>produit ${esc(row.targetProduct)}</small></td><td>${esc(mechanism(row.mechanism).shortLabel)}</td><td>${pp(row.fedProductService.mean)}<br><small>P10–P90 : ${pp(row.fedProductService.p10)} à ${pp(row.fedProductService.p90)} · IC95 : ${metricCi(row.fedProductService)}</small></td><td>${doseValue(row)}</td><td>${backlogValue(row)}</td><td>${productionValue(row)}</td><td>${comparisonBadge(row.lane)}</td></tr>`).join("")};causeState.onchange=()=>{fillSupplierSelect(causeSupplier,causeState.value);renderCauses()};causeSupplier.onchange=renderCauses;renderCauses();
    const lotState=$("lot-state"),lotSupplier=$("lot-supplier");fillSupplierSelect(lotSupplier,lotState.value,true);
    const replayCallout=$("replay-selection-callout");replayCallout.className=`callout ${data.lotReplay.dossierCount?"good":"warn"}`;replayCallout.innerHTML=`<b>${data.lotReplay.dossierCount?`${data.lotReplay.dossierCount} dossier(s) de rejeu sélectionné(s) et signé(s)`:"Aucun dossier n'est forcé sans signal statistique admissible"}</b><p>${esc(data.lotReplay.message)}</p>${data.lotReplay.dossiers.length?`<p>${data.lotReplay.dossiers.map(item=>`${esc(item.supplier)} · ${esc(mechanism(item.mechanism).shortLabel)} · ${esc(item.lane)} · représentant choisi parmi ${item.exercisedSeedCount}/30 répétitions physiquement exposées`).join("<br>")}</p>`:""}`;
    const renderLots=()=>{const stateId=lotState.value,supplier=lotSupplier.value,row=data.priorities.find(item=>item.state===stateId&&item.supplier===supplier),target=row?registryFor(row.lane):null,stateTarget=target&&target.states[stateId],dossier=data.lotReplay.dossiers.find(item=>item.state===stateId&&item.supplier===supplier);if(!row){$("target-summary").innerHTML='<div class="empty">Aucun signal positif dans cet état.</div>';return}const windowText=stateTarget&&stateTarget.windowStartMin!=null?`début entre J${stateTarget.windowStartMin} et J${stateTarget.windowStartMax} selon la répétition`:"fenêtre non chargée",windowDays=target&&target.windowDays?target.windowDays:data.targetRegistry.windowDays;$("target-summary").innerHTML=`<article class="target-card"><span class="badge sim">SIMULÉ · CONDITIONNEL</span><h3>${esc(row.supplier)} · ${esc(row.item)} → ${esc(row.destination)}</h3><p>Voie ${esc(row.lane)} · fenêtre de ${esc(windowDays||"—")} jours · ${esc(windowText)}.</p><p>Cette fenêtre de forte exposition a été repérée voie par voie avec la graine de conception. Elle dépend de la saison simulée et ne mesure pas la fréquence d'un incident.</p><p><b>Quantité planifiée médiane ciblée :</b> ${stateTarget?fmt(stateTarget.quantityMedian,0):"—"} ${stateTarget?esc(stateTarget.uom||"unités"):""}<br><b>Expéditions médianes regroupées :</b> ${stateTarget?fmt(stateTarget.shipmentCountMedian,0):"—"}</p>${comparisonBadge(row)}</article><article class="target-card"><span class="badge pending">${dossier?"REPLAY SÉLECTIONNÉ":"REPLAY À COMPLÉTER"}</span><h3>Preuve de lots ciblée</h3><p>${dossier?`Le représentant est choisi parmi ${dossier.exercisedSeedCount}/30 répétitions où la voie a été physiquement exposée.`:"La campagne agrégée ne nomme pas encore les lots : il faut exécuter le replay ciblé."}</p><p>Le replay peut relier réceptions matière, consommations, ordres et lots finis. Les sorties C-XXXXX restent des nœuds clients agrégés, jamais des clients réels nommés.</p></article>`;$("chain-target").textContent=`${row.item} vers ${row.destination}, ${windowText}.`};lotState.onchange=()=>{fillSupplierSelect(lotSupplier,lotState.value,true);renderLots()};lotSupplier.onchange=renderLots;renderLots();
    const initialView=location.hash.slice(1);if(["priority","causes","lots"].includes(initialView)&&initialView!=="priority")setView(initialView,false);
  })();
  </script>
</body>
</html>
"""


def render_dashboard(payload: Mapping[str, Any]) -> str:
    """Render a dependency-free, single-file HTML document."""

    return HTML_TEMPLATE.replace("__DATA__", _safe_json(payload))


def build_dashboard(
    *,
    results_dir: Path,
    output_html: Path,
    target_registry_path: Path | None = None,
) -> dict[str, Any]:
    """Build one new dashboard and return a compact construction manifest."""

    output = output_html.resolve()
    if output.exists():
        raise FileExistsError(f"Refus d'écraser le fichier existant : {output}")
    payload = load_dashboard_data(
        results_dir=results_dir, target_registry_path=target_registry_path
    )
    document = render_dashboard(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8", newline="\n")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "output_html": str(output),
        "offline_single_file": True,
        "view_count": 3,
        "byte_count": output.stat().st_size,
        "supplier_count": payload["supplierCount"],
        "lane_count": payload["laneCount"],
        "repetition_count": payload["repetitions"],
        "target_registry_available": payload["targetRegistry"]["available"],
        "all_lanes_cross_state_comparable": payload["targetRegistry"][
            "allLanesComparable"
        ],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        required=True,
        help="Dossier compact produit par le finalizer V4.",
    )
    parser.add_argument(
        "--target-registry",
        type=Path,
        help="Registre signé des fenêtres cibles communes.",
    )
    parser.add_argument("--output-html", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = build_dashboard(
            results_dir=args.results_dir,
            output_html=args.output_html,
            target_registry_path=args.target_registry,
        )
    except (DashboardInputError, FileExistsError) as exc:
        print(f"DASHBOARD NON PRODUIT : {exc}")
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
