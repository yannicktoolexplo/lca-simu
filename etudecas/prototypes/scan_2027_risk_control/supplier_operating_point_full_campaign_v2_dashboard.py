#!/usr/bin/env python3
"""Build the lightweight, offline dashboard for supplier campaign V2.

The builder is deliberately presentation-only: it reads the compact outputs of
``finalize_supplier_operating_point_full_campaign_v2.py`` and never starts the
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
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.dashboard.v2"
STATE_IDS = ("op_100", "op_93", "op_80")
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
RESULT_FILES = {
    "validation": "campaign_validation.json",
    "operating_point_registry": "operating_point_preflight.json",
    "supplier_statistics": "supplier_statistics.csv",
    "lane_statistics": "lane_statistics.csv",
}
PRIORITY_FILE_CANDIDATES = (
    "priority_suppliers_by_cause_state.csv",
    "top3_suppliers_overall_by_state.csv",
)
STABILITY_FILE_CANDIDATES = (
    "supplier_priority_stability_by_cause.csv",
    "top3_supplier_stability_overall.csv",
)
DISPLAYED_PRIORITY_STATUSES = {
    "robust_priority",
    "priority_contender",
    "supplementary_backlog_signal",
}
TARGET_REGISTRY_CANDIDATES = (
    "cross_state_target_registry.json",
    "target_registry.json",
    "campaign_target_registry.json",
)
NUMERIC_TOLERANCE = 1e-12
SIGNED_OPERATING_POINT_STATUS = "holdout_validated_30_seed"


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
    """Read achieved global and product service solely from the signed registry."""

    signature = _verify_embedded_signature(
        registry,
        signature_field="preflight_signature",
        label="registre final des points de fonctionnement",
    )
    if _text(registry.get("campaign_signature")) != campaign_signature:
        raise DashboardInputError(
            "Le registre final des points de fonctionnement appartient à une autre campagne."
        )
    if _text(registry.get("status")) != SIGNED_OPERATING_POINT_STATUS:
        raise DashboardInputError(
            "Le registre final des points de fonctionnement n'est pas validé."
        )
    rows = registry.get("states")
    if not isinstance(rows, list):
        raise DashboardInputError(
            "Le registre final ne contient pas les points de fonctionnement."
        )
    by_state: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise DashboardInputError(
                "Point de fonctionnement illisible dans le registre final."
            )
        state = _text(row.get("operating_point_id"))
        if state in by_state:
            raise DashboardInputError(
                f"Point de fonctionnement dupliqué dans le registre final : {state}."
            )
        by_state[state] = row
    if set(by_state) != set(STATE_IDS):
        raise DashboardInputError(
            "Le registre final signé doit contenir exactement les points 100, 93 et 80."
        )

    result: dict[str, dict[str, float]] = {}
    for state in STATE_IDS:
        row = by_state[state]
        if not _truthy(row.get("accepted")):
            raise DashboardInputError(
                f"Le point {state} n'est pas accepté dans le registre final signé."
            )
        result[state] = {
            "target": _required_percent(
                row.get("target_service_pct"), label=f"cible {state}"
            ),
            "global": _required_percent(
                row.get("service_global_ratio_of_sums_pct"),
                label=f"service global {state}",
            ),
            "268091": _required_percent(
                row.get("service_268091_ratio_of_sums_pct"),
                label=f"service PF091 {state}",
            ),
            "268967": _required_percent(
                row.get("service_268967_ratio_of_sums_pct"),
                label=f"service PF967 {state}",
            ),
        }
    return result, signature


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
            "ciLow": _number(row.get(f"{stem}_ci95_low")),
            "ciHigh": _number(row.get(f"{stem}_ci95_high")),
            "p90": _number(row.get(f"{stem}_p90")),
            "positiveRate": _number(row.get(f"{stem}_positive_effect_rate")),
        }
    return {
        "source": "",
        "mean": None,
        "median": None,
        "ciLow": None,
        "ciHigh": None,
        "p90": None,
        "positiveRate": None,
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
    lane_id = _text(
        row.get("representative_lane_id") if supplier_level else row.get("lane_id")
    )
    return {
        "state": _text(row.get("operating_point_id")),
        "stateServicePct": _service_pct(row.get("operating_point_service_pct")),
        "mechanism": _text(row.get("mechanism")),
        "supplier": _text(row.get("supplier_id")),
        "lane": lane_id,
        "item": _text(row.get("item_id")),
        "destination": _text(row.get("dst_node_id")),
        "targetUom": _text(row.get("target_uom")),
        "pairedCount": _integer(row.get("paired_repetition_count"), 0),
        "exerciseRate": _number(row.get("physical_exercise_rate")),
        "service": service,
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
    if _text(validation.get("status")) != "complete_validated":
        raise DashboardInputError(
            "La page finale exige une campagne marquée complete_validated."
        )
    contract = validation.get("expected_contract")
    if not isinstance(contract, Mapping):
        raise DashboardInputError("Contrat de campagne absent du manifeste final.")
    mechanisms = {_text(value) for value in contract.get("mechanisms", [])}
    if mechanisms != set(MECHANISMS):
        raise DashboardInputError(
            "Les deux hypothèses V2 attendues ne sont pas présentes."
        )
    if _truthy(contract.get("quality_branch_included")) or _truthy(
        contract.get("availability_incident_included")
    ):
        raise DashboardInputError(
            "Le périmètre du paquet ne correspond pas à la campagne V2."
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
    )
    failed = [key for key in required_checks if not _truthy(checks.get(key))]
    if failed:
        raise DashboardInputError(
            "Comparabilité interne incomplète : " + ", ".join(failed)
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
                "état par état, mais la comparaison inter-états n'est pas validée."
            ),
        }
    registry_signature = _text(registry.get("campaign_signature"))
    if campaign_signature and registry_signature != campaign_signature:
        raise DashboardInputError(
            "Le registre de fenêtres appartient à une autre campagne."
        )
    registry_engine = _text(registry.get("engine_sha256"))
    if engine_sha256 and registry_engine and registry_engine != engine_sha256:
        raise DashboardInputError(
            "Le registre de fenêtres appartient à un autre moteur."
        )
    declared_signature = _text(registry.get("registry_signature"))
    if declared_signature:
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
        if declared_signature != computed_signature:
            raise DashboardInputError(
                "La signature du registre de fenêtres est incohérente."
            )
    targets = registry.get("targets")
    coverage = registry.get("coverage")
    lane_contracts = registry.get("lane_contracts")
    if not isinstance(targets, list) or not targets:
        raise DashboardInputError("Le registre de fenêtres ne contient aucune cible.")
    if not (isinstance(coverage, list) and coverage) and not (
        isinstance(lane_contracts, list) and lane_contracts
    ):
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
            f"{valid_lane_count}/{len(lane_ids)} voies disposent d'une fenêtre de "
            f"{window_days} jours "
            "qui atteint le seuil de comparabilité fixé avant l'analyse."
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
        service = dict(stat["service"])
        fixed_effect = _number(source.get("fixed360_effect_mean_pp"))
        if fixed_effect is not None:
            service.update(
                {
                    "source": "fixed360_effect",
                    "mean": fixed_effect,
                    "ciLow": _first_number(
                        source,
                        ("bootstrap_ci95_low", "fixed360_effect_ci95_low"),
                    ),
                    "ciHigh": _first_number(
                        source,
                        ("bootstrap_ci95_high", "fixed360_effect_ci95_high"),
                    ),
                }
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
        result.append(
            {
                "supplier": supplier,
                "mechanism": mechanism,
                "states": states,
                "allStates": len(states) == len(STATE_IDS),
                "allStatesComparable": len(states) == len(STATE_IDS)
                and not insufficient_comparison
                and all(bool(row["comparisonValid"]) for row in supplier_rows),
                "insufficientComparableExposure": insufficient_comparison,
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
    operating_point_registry = _read_json(paths["operating_point_registry"])
    operating_point_services, operating_point_registry_signature = (
        _signed_operating_point_services(
            operating_point_registry,
            campaign_signature=_text(validation.get("campaign_signature")),
        )
    )
    supplier_raw = _read_csv(paths["supplier_statistics"])
    lane_raw = _read_csv(paths["lane_statistics"])
    priority_raw = _read_csv(paths["priority"])
    stability_raw = _read_csv(paths["stability"])
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
        common_columns | {"representative_lane_id"},
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
        services = operating_point_services[state]
        state_rows.append(
            {
                "id": state,
                "label": {
                    "op_100": "Réseau robuste",
                    "op_93": "Réseau sous tension",
                    "op_80": "Réseau fortement dégradé",
                }[state],
                "pointLabel": state.removeprefix("op_"),
                "targetServicePct": services["target"],
                "globalServicePct": services["global"],
                "pf091ServicePct": services["268091"],
                "pf967ServicePct": services["268967"],
                # Compatibility alias used by selectors in earlier V2 dashboards.
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
                "label": "Livraison planifiée reçue à 50 %",
                "shortLabel": "Livraison à 50 %",
                "hypothesis": (
                    "La voie ne reçoit physiquement que 50 % de la quantité planifiée "
                    "dans la fenêtre ciblée."
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
        "lotReplay": {
            "status": "pending",
            "allLotsTraced": False,
            "message": (
                "La campagne compacte suit les expéditions et les effets agrégés. "
                "La généalogie lot par lot sera ajoutée après le replay ciblé."
            ),
        },
        "evidence": {
            "classification": _text(validation.get("evidence_class")),
            "historicalIncidentProbabilityEstimated": False,
            "industrialSupplierRatingClaimed": False,
            "campaignStatus": _text(validation.get("status")),
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
  <title>Campagne fournisseurs V2 — résultats</title>
  <style>
    :root{--navy:#092747;--blue:#1768e5;--sky:#eaf3ff;--green:#11815b;--amber:#c87b0e;--red:#c93b31;--ink:#112a42;--muted:#60748a;--line:#d8e3ee;--paper:#f2f6fa;--card:#fff;--shadow:0 12px 34px #18395913}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}button,select{font:inherit}header{padding:28px clamp(18px,4vw,56px) 24px;background:linear-gradient(118deg,#071e37,#124d7e 66%,#0a746a);color:#fff}.overline{font-size:11px;font-weight:900;letter-spacing:.14em;color:#8ce4d0}h1{margin:7px 0 9px;font-size:clamp(30px,4.5vw,52px);line-height:1.05}header>p{max-width:940px;margin:0;color:#d9e8f6;font-size:17px}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.chip{padding:6px 9px;border:1px solid #ffffff42;border-radius:999px;background:#ffffff12;font-size:12px}.reading{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#cedbe8;border-bottom:1px solid #c2d1df}.definition{padding:12px clamp(12px,2.5vw,24px);background:#fff;min-height:80px}.definition b{display:block;font-size:11px;letter-spacing:.09em;color:var(--blue)}.definition span{display:block;margin-top:3px;color:#52697e;font-size:13px}.tabs{position:sticky;top:0;z-index:10;display:flex;justify-content:center;gap:8px;padding:10px;background:#f8fbffed;border-bottom:1px solid var(--line);backdrop-filter:blur(9px)}.tabs button{border:1px solid #b8cadc;border-radius:999px;background:#fff;color:#234664;padding:9px 14px;font-weight:850;cursor:pointer}.tabs button.active{color:#fff;background:var(--navy);border-color:var(--navy)}main{max-width:1300px;margin:auto;padding:20px clamp(13px,3vw,32px) 55px}.view{display:none}.view.active{display:block}.question,.callout{background:#fff;border:1px solid var(--line);border-left:6px solid var(--blue);border-radius:15px;padding:15px 17px;box-shadow:var(--shadow);margin-bottom:14px}.question b{display:block;font-size:20px}.question p,.callout p{margin:4px 0 0;color:var(--muted)}.callout.good{border-left-color:var(--green);background:#f3fbf7}.callout.warn{border-left-color:var(--amber);background:#fff9ee}.toolbar,.button-group{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.toolbar{margin:13px 0}.toolbar button,.toolbar select{border:1px solid #b8cadc;border-radius:9px;background:#fff;padding:8px 11px;color:var(--ink);font-weight:750}.toolbar button{cursor:pointer}.toolbar button.active{background:var(--blue);border-color:var(--blue);color:#fff}.toolbar-label{font-size:11px;font-weight:900;letter-spacing:.06em;color:var(--muted)}.section{margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:16px;padding:17px;box-shadow:var(--shadow)}.section h2{margin:0 0 4px;font-size:22px}.section>p{margin:0 0 12px;color:var(--muted)}.state-grid,.priority-grid,.cause-grid,.metric-grid,.action-grid{display:grid;gap:11px}.state-grid{grid-template-columns:repeat(3,1fr)}.state-card,.priority-card,.cause-card,.metric,.action{background:#fff;border:1px solid var(--line);border-radius:13px;padding:14px}.state-card{border-top:5px solid var(--blue)}.state-card h3{margin:7px 0 9px;font-size:20px}.state-kicker{font-size:10px;font-weight:900;letter-spacing:.045em;color:#6540a8}.state-global{padding:10px;border-radius:10px;background:var(--sky)}.state-global small{display:block;color:#1552a8;font-weight:850}.state-global strong{display:block;font-size:30px;color:var(--navy)}.state-products{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.state-product{padding:9px;border:1px solid var(--line);border-radius:9px}.state-product strong{display:block;font-size:20px;color:var(--navy)}.state-product small{display:block;color:var(--muted)}.state-source{margin:9px 0 0;color:var(--muted);font-size:11px}.priority-grid{grid-template-columns:repeat(3,1fr)}.priority-card{border-top:5px solid var(--blue);box-shadow:0 8px 22px #17395910}.priority-card.backlog{border-top-color:var(--amber)}.priority-card .rank{display:inline-grid;place-items:center;min-width:27px;height:27px;padding:0 6px;border-radius:14px;background:#e8f1ff;color:#1552a8;font-weight:950}.priority-card h3{display:inline;margin-left:7px;font-size:19px}.path{color:#4e657a;margin:6px 0 10px}.big{font-size:27px;font-weight:950;color:var(--navy);font-variant-numeric:tabular-nums}.label{color:var(--muted);font-size:12px}.bar-track{height:8px;border-radius:8px;background:#e5edf5;overflow:hidden;margin:7px 0}.bar{height:100%;background:linear-gradient(90deg,#f1a11b,#cb3730)}.badge{display:inline-block;border-radius:999px;padding:5px 8px;font-size:10px;font-weight:900;letter-spacing:.045em}.badge.ok{background:#e5f5ee;color:#087052}.badge.no{background:#fff0dd;color:#8b5200}.badge.sim{background:#e8f1ff;color:#1552a8}.badge.pending{background:#f0eafe;color:#6540a8}.plain{color:var(--muted);font-size:13px}.cause-grid{grid-template-columns:repeat(2,1fr)}.cause-card{border-top:5px solid var(--blue)}.cause-card h3{margin:7px 0 2px;font-size:20px}.cause-card>p{margin:4px 0;color:var(--muted)}.metric-grid{grid-template-columns:repeat(4,1fr);margin-top:12px}.metric strong{display:block;font-size:22px;color:var(--navy)}.metric small{display:block;color:var(--muted)}.uncertainty{margin-top:12px;padding:11px;border-radius:10px;background:#edf4fb;color:#274866}.explain{margin-top:10px;border-left:4px solid var(--green);padding:8px 10px;background:#eff9f5;border-radius:8px;color:#285b4d}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:11px}table{border-collapse:collapse;width:100%;min-width:850px}th,td{padding:9px 10px;border-bottom:1px solid #e5edf4;text-align:left}th{background:#edf4fb;color:#173d62;font-size:11px;letter-spacing:.025em}td{font-size:12px}.chain{display:flex;align-items:stretch;gap:7px;overflow:auto;padding:9px 0 14px}.step{min-width:160px;flex:1;border:1px solid #ceddeb;border-radius:11px;background:#f8fbff;padding:12px}.step b{display:block;color:#14518e;margin-bottom:4px}.step.pending{border-style:dashed;background:#faf7ff}.arrow{display:grid;place-items:center;font-size:23px;color:var(--blue)}.target-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:11px}.target-card{padding:14px;border:1px solid var(--line);border-radius:13px;background:#fff}.target-card h3{margin:0 0 5px}.action-grid{grid-template-columns:repeat(3,1fr)}.action{border-top:5px solid #7c55bc}.action h3{margin:7px 0}.action p{color:var(--muted);margin:0}.stop{padding:14px;border:1px solid #e8c28b;background:#fff7e9;border-radius:12px}.stop strong{color:#855000}.empty{padding:20px;border:1px dashed #b8cadc;border-radius:12px;text-align:center;color:var(--muted)}footer{max-width:1300px;margin:0 auto;padding:0 28px 34px;color:#65788b;font-size:12px}.hidden{display:none!important}@media(max-width:950px){.reading,.priority-grid,.metric-grid{grid-template-columns:1fr 1fr}.cause-grid,.target-grid{grid-template-columns:1fr}.action-grid{grid-template-columns:1fr}}@media(max-width:620px){.reading,.state-grid,.priority-grid,.metric-grid{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}.tabs button{white-space:nowrap}}@media print{.tabs{display:none}.view{display:block!important;break-before:page}body{background:#fff}.section,.question{box-shadow:none}}
  </style>
</head>
<body>
  <header>
    <div class="overline">CAMPAGNE FOURNISSEURS V2 · SYNTHÈSE AUTONOME</div>
    <h1>Quels fournisseurs fragilisent le réseau — et pourquoi&nbsp;?</h1>
    <p>Trois états du même réseau, deux incidents déclarés et les mêmes répétitions appariées. Cette page montre où instruire un dossier fournisseur, sans transformer une étude d'impact en note de performance.</p>
    <div class="chips" id="hero-chips"></div>
  </header>
  <div class="reading" aria-label="Cadre de lecture">
    <div class="definition"><b>OBSERVÉ</b><span>Donnée réelle fournie par vos équipes. Aucune performance historique fournisseur n'est chargée ici.</span></div>
    <div class="definition"><b>SIMULÉ</b><span>Conséquence calculée par le moteur lorsqu'une hypothèse est imposée au réseau.</span></div>
    <div class="definition"><b>SIGNAL DE PRIORITÉ</b><span>Dossier fournisseur–article à instruire en premier. Ce n'est ni une note ni une probabilité.</span></div>
    <div class="definition"><b>HYPOTHÈSE</b><span>Incident ou action déclaré dans le modèle et à calibrer avec vos historiques.</span></div>
  </div>
  <nav class="tabs" aria-label="Trois vues">
    <button class="active" data-view="priority" aria-current="page">1 · Priorités</button>
    <button data-view="causes">2 · Causes et effets</button>
    <button data-view="lots">3 · Cascade, lots et actions</button>
  </nav>
  <main>
    <section class="view active" id="view-priority">
      <div class="question"><b>Retrouve-t-on les mêmes fournisseurs quand le réseau se dégrade&nbsp;?</b><p>La comparaison est autorisée voie par voie lorsque la fenêtre commune signée atteint, sur les mêmes répétitions, le seuil de comparabilité défini avant l'analyse.</p></div>
      <div class="state-grid" id="state-cards"></div>
      <div id="comparison-callout" class="callout"></div>
      <div class="section"><h2>Signaux de priorité par état simulé et par cause</h2><p>Les deux incidents ne sont jamais mélangés dans un même rang. Un effet nul n'est pas promu pour compléter artificiellement un trio&nbsp;; un signal fondé seulement sur le retard cumulé est identifié séparément.</p><div class="toolbar"><span class="toolbar-label">ÉTAT</span><div class="button-group" id="priority-state-buttons"></div><span class="toolbar-label">CAUSE</span><div class="button-group" id="priority-mechanism-buttons"></div></div><div class="priority-grid" id="priority-cards"></div></div>
      <div class="section"><h2>Lecture inter-états</h2><p>Cette synthèse sépare la stabilité apparente du signal et la validité physique de la comparaison.</p><div id="stability-reading"></div></div>
    </section>

    <section class="view" id="view-causes">
      <div class="question"><b>Pour un fournisseur donné, quel incident produit réellement l'effet aval&nbsp;?</b><p>Chaque incident est comparé à sa référence avec la même répétition. La moyenne décrit les simulations&nbsp;; l'intervalle montre leur dispersion.</p></div>
      <div class="toolbar"><label for="cause-state">État&nbsp;</label><select id="cause-state"></select><label for="cause-supplier">Fournisseur&nbsp;</label><select id="cause-supplier"></select></div>
      <div class="cause-grid" id="cause-cards"></div>
      <div class="callout warn"><b>Deux tests distincts, pas une échelle commune.</b><p>Le retard de 120 jours et la livraison reçue à 50&nbsp;% ne sont pas calibrés à une même gravité. On classe les fournisseurs à l'intérieur de chaque test&nbsp;; leurs amplitudes brutes ne disent pas qu'un incident est plus probable ou plus grave que l'autre.</p></div>
      <div class="section"><h2>Voies physiques du fournisseur sélectionné</h2><p>Le détail évite d'additionner des articles différents. Chaque ligne reste une voie fournisseur–article–site.</p><div class="table-wrap"><table><thead><tr><th>Voie</th><th>Article → site</th><th>Hypothèse</th><th>Perte de service moyenne</th><th>Retard cumulé normalisé</th><th>Production non libérée</th><th>Comparaison inter-états</th></tr></thead><tbody id="lane-table"></tbody></table></div></div>
      <div class="callout warn"><b>Ce que l'incertitude ne dit pas.</b><p>Le cas défavorable et l'intervalle à 95&nbsp;% décrivent les répétitions du modèle. Ils ne donnent pas la fréquence future d'un incident chez le fournisseur.</p></div>
    </section>

    <section class="view" id="view-lots">
      <div class="question"><b>Peut-on suivre l'incident jusqu'aux lots et décider d'une action&nbsp;?</b><p>La campagne compacte prouve la cible d'expédition et les effets réseau. Elle ne nomme pas encore les lots industriels&nbsp;: cette preuve arrive avec le replay ciblé.</p></div>
      <div class="toolbar"><label for="lot-state">État&nbsp;</label><select id="lot-state"></select><label for="lot-supplier">Signal&nbsp;</label><select id="lot-supplier"></select></div>
      <div class="target-grid" id="target-summary"></div>
      <div class="section"><h2>Chaîne de preuve</h2><p>Les deux dernières liaisons doivent être complétées avec le registre détaillé du replay.</p><div class="chain"><div class="step"><b>1 · Fenêtre ciblée</b><span id="chain-target"></span></div><div class="arrow">→</div><div class="step"><b>2 · Stock et encours</b>Effet physique recalculé jour après jour.</div><div class="arrow">→</div><div class="step"><b>3 · Production</b>Quantité libérée et manque agrégés dans la campagne.</div><div class="arrow">→</div><div class="step pending"><b>4 · Lots finis</b>Identifiants et généalogie à extraire du replay.</div><div class="arrow">→</div><div class="step pending"><b>5 · Clients</b>Commandes nommées à relier après le replay.</div></div></div>
      <div class="section"><h2>Trois actions pilotables à tester lors du replay</h2><p>Aucune efficacité n'est annoncée avant comparaison avec le même incident sans action.</p><div class="action-grid"><article class="action"><span class="badge pending">HYPOTHÈSE À SIMULER</span><h3>Stock ciblé préparé avant l'incident</h3><p>Tester 7, 14 et 28 jours de besoin du composant qualifié, avec une quantité, un site et une date de mise à disposition explicites.</p></article><article class="action"><span class="badge pending">HYPOTHÈSE À SIMULER</span><h3>Expédition de remplacement identifiée</h3><p>N'accélérer qu'une expédition existante, réservée et nommée&nbsp;; mesurer les jours gagnés et le surcoût réel à renseigner.</p></article><article class="action"><span class="badge pending">HYPOTHÈSE À SIMULER</span><h3>Affectation explicite de la matière</h3><p>Prioriser des ordres et commandes nommés, puis rendre visible le retard évité et le retard éventuellement déplacé.</p></article></div></div>
      <div class="stop"><strong>Limite à dire au client :</strong> tant que le replay détaillé n'est pas terminé, la page ne prétend pas savoir quel lot industriel ou quel client nommé est touché. Elle sait déjà sélectionner les dossiers où cette investigation apportera le plus de valeur.</div>
    </section>
  </main>
  <footer>Page autonome hors ligne · résultats conditionnels du simulateur · aucune connexion réseau nécessaire.</footer>
  <script id="campaign-data" type="application/json">__DATA__</script>
  <script>
  (()=>{"use strict";
    const data=JSON.parse(document.getElementById("campaign-data").textContent);
    const $=id=>document.getElementById(id), esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const n=value=>value===null||value===undefined||value===""?null:(Number.isFinite(Number(value))?Number(value):null);
    const fmt=(value,digits=1)=>n(value)==null?"—":Number(value).toLocaleString("fr-FR",{minimumFractionDigits:digits,maximumFractionDigits:digits});
    const pct=value=>n(value)==null?"—":`${fmt(100*n(value),0)} %`;
    const pp=value=>n(value)==null?"—":`${fmt(value,2)} point${Math.abs(Number(value))>1?"s":""}`;
    const state=id=>data.states.find(item=>item.id===id)||data.states[0];
    const mechanism=id=>data.mechanisms.find(item=>item.id===id)||data.mechanisms[0];
    const stateLabel=id=>`${state(id).label} · ${fmt(state(id).globalServicePct,1)} % global`;
    const metricCi=metric=>metric&&n(metric.ciLow)!=null&&n(metric.ciHigh)!=null?`${pp(metric.ciLow)} à ${pp(metric.ciHigh)}`:"non calculé";
    const registryFor=lane=>data.targetLanes[lane]||null;
    const comparisonBadge=value=>{const row=typeof value==="object"?value:null,lane=row?row.lane:value,r=registryFor(lane),valid=Boolean(r&&r.comparisonValid&&(row==null||row.comparisonValid!==false));return valid?`<span class="badge ok">COMPARAISON INTER-ÉTATS VALIDÉE · ${r.validComparisonCount}/${r.comparisonCount} (seuil ${r.requiredComparisonCount})</span>`:`<span class="badge no">COMPARAISON INTER-ÉTATS NON VALIDÉE</span>`};
    const priorityLabel=row=>({robust_priority:"PRIORITÉ ROBUSTE",priority_contender:"PRIORITÉ À CONFIRMER",supplementary_backlog_signal:"SIGNAL BACKLOG COMPLÉMENTAIRE"}[row.priorityGroup]||"SIGNAL DE PRIORITÉ");
    const rankEvidence=row=>{const parts=[];if(n(row.inclusionProbability)!=null)parts.push(`présent dans le groupe de tête dans ${pct(row.inclusionProbability)} des rééchantillonnages`);if(n(row.rankCiLow)!=null&&n(row.rankCiHigh)!=null)parts.push(`rang plausible ${fmt(row.rankCiLow,0)} à ${fmt(row.rankCiHigh,0)}`);return parts.length?`<p class="plain"><b>Stabilité statistique :</b> ${parts.join(" · ")}.</p>`:""};
    const backlogValue=row=>row.backlogMode==="demand_days"?`${fmt(row.backlog.mean,2)} jour(s) de demande`:`${fmt(row.backlog.mean,0)} unités × jours`;
    const productionValue=row=>row.productionMode==="demand_share"?pct(row.production.mean):`${fmt(row.production.mean,0)} ${esc(row.targetUom||"unités")}`;
    const explanation=row=>{const effect=n(row.service.mean)||0, rate=n(row.service.positiveRate);if(effect<=1e-12)return"Aucune perte moyenne mesurable dans ces simulations : ce dossier ne doit pas être présenté comme prioritaire.";if(rate!=null&&rate<.7)return`L'effet existe en moyenne, mais seulement dans ${fmt(100*rate,0)} % des répétitions : il dépend fortement de l'état du réseau.`;if(n(row.maskedByExistingBacklogRate)>0)return"Le retard ou le manque augmente, mais une partie de la perte de service peut être masquée par un retard déjà présent dans la référence.";return"L'incident traverse les stocks et la production jusqu'au service client dans la majorité des répétitions simulées."};
    const setView=(id,updateHash=true)=>{document.querySelectorAll(".view").forEach(node=>node.classList.toggle("active",node.id===`view-${id}`));document.querySelectorAll(".tabs button").forEach(button=>{const active=button.dataset.view===id;button.classList.toggle("active",active);if(active)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current")});if(updateHash)history.replaceState(null,"",`#${id}`);window.scrollTo({top:0,behavior:"smooth"})};
    document.querySelectorAll(".tabs button").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
    $("hero-chips").innerHTML=`<span class="chip">${data.states.length} états simulés</span><span class="chip">${data.laneCount} voies physiques</span><span class="chip">${data.repetitions} répétitions appariées</span><span class="chip">2 hypothèses d'incident</span>`;
    $("state-cards").innerHTML=data.states.map(item=>`<article class="state-card"><div class="state-kicker">HYPOTHÈSE · POINT ${esc(item.pointLabel)} · CIBLE DE CALIBRATION ${fmt(item.targetServicePct,1)} %</div><h3>${esc(item.label)}</h3><div class="state-global"><small>SIMULÉ · TAUX DE SERVICE GLOBAL OBTENU</small><strong>${fmt(item.globalServicePct,1)} %</strong></div><div class="state-products"><div class="state-product"><small>SIMULÉ · PF091 (268091)</small><strong>${fmt(item.pf091ServicePct,1)} %</strong></div><div class="state-product"><small>SIMULÉ · PF967 (268967)</small><strong>${fmt(item.pf967ServicePct,1)} %</strong></div></div><p class="state-source">Valeurs reprises sans recalcul du registre final validé des points de fonctionnement.</p></article>`).join("");
    const reg=data.targetRegistry, comparison=$("comparison-callout");comparison.className=`callout ${reg.allLanesComparable?"good":"warn"}`;comparison.innerHTML=`<b>${reg.allLanesComparable?"Comparaison inter-états entièrement exploitable":"Comparaison inter-états limitée"}</b><p>${esc(reg.message)} ${reg.allLanesComparable?"Les changements de signal entre états peuvent être interprétés pour toutes les voies.":"Chaque badge indique les voies comparables ; les autres doivent être lues séparément dans chaque état."}</p>`;
    let priorityState=data.states[0].id,priorityMechanism=data.mechanisms[0].id;
    const renderPriority=()=>{$("priority-state-buttons").innerHTML=data.states.map(item=>`<button class="${item.id===priorityState?"active":""}" data-state="${esc(item.id)}">${esc(item.label)}</button>`).join("");$("priority-state-buttons").querySelectorAll("button").forEach(button=>button.onclick=()=>{priorityState=button.dataset.state;renderPriority()});$("priority-mechanism-buttons").innerHTML=data.mechanisms.map(item=>`<button class="${item.id===priorityMechanism?"active":""}" data-mechanism="${esc(item.id)}">${esc(item.shortLabel)}</button>`).join("");$("priority-mechanism-buttons").querySelectorAll("button").forEach(button=>button.onclick=()=>{priorityMechanism=button.dataset.mechanism;renderPriority()});const rows=data.priorities.filter(row=>row.state===priorityState&&row.mechanism===priorityMechanism);const max=Math.max(...rows.map(row=>row.supplementaryBacklogSignal?Math.max(0,n(row.backlog.mean)||0):Math.max(0,n(row.service.mean)||0)),1e-9);$("priority-cards").innerHTML=rows.length?rows.map(row=>{const signal=row.supplementaryBacklogSignal?n(row.backlog.mean)||0:n(row.service.mean)||0;const value=row.supplementaryBacklogSignal?backlogValue(row):pp(row.service.mean);const label=row.supplementaryBacklogSignal?"retard cumulé supplémentaire, sans perte de service prouvée":"perte moyenne de service global simulée";const uncertainty=row.supplementaryBacklogSignal?"Ce signal complète l'analyse du service ; il ne prouve pas à lui seul une perte client.":`Intervalle à 95 % : ${metricCi(row.service)} · effet dans ${pct(row.service.positiveRate)} des répétitions.`;return`<article class="priority-card ${row.supplementaryBacklogSignal?"backlog":""}"><span class="rank">${n(row.rankMedian)!=null?fmt(row.rankMedian,0):row.position}</span><h3>${esc(row.supplier)}</h3><p><span class="badge ${row.priorityGroup==="robust_priority"?"ok":row.supplementaryBacklogSignal?"no":"sim"}">${priorityLabel(row)}</span></p><p class="path">Article ${esc(row.item)} → ${esc(row.destination)}<br><small>${esc(mechanism(row.mechanism).shortLabel)}</small></p><div class="big">${value}</div><div class="label">${label}</div><div class="bar-track"><div class="bar" style="width:${Math.min(100,100*Math.max(0,signal)/max)}%"></div></div><p class="plain">${uncertainty}</p>${rankEvidence(row)}${row.horizonDependent?'<p class="plain"><b>Attention :</b> résultat sensible à la durée observée.</p>':""}${comparisonBadge(row)}</article>`}).join(""):`<div class="empty">Aucun signal retenu pour cette cause dans cet état.</div>`;const stable=data.stability.filter(row=>row.mechanism===priorityMechanism&&row.allStates),validated=stable.filter(row=>row.allStatesComparable);$("stability-reading").innerHTML=validated.length?`<div class="callout good"><b>${validated.length} fournisseur(s) restent prioritaires pour ${esc(mechanism(priorityMechanism).shortLabel)} dans les trois états, avec comparaison validée.</b><p>${validated.map(row=>esc(row.supplier)).join(" · ")}. C'est un signal robuste du modèle, pas une note de performance fournisseur.</p></div>`:stable.length?`<div class="callout warn"><b>Le signal apparaît dans les trois états, mais la comparaison physique n'est pas validée partout.</b><p>${stable.map(row=>esc(row.supplier)).join(" · ")}. Il faut lire les états séparément avant toute conclusion de stabilité.</p></div>`:`<div class="callout warn"><b>Le groupe de priorité change selon l'état simulé pour ${esc(mechanism(priorityMechanism).shortLabel)}.</b><p>Le niveau de tension du réseau modifie les fournisseurs qui transmettent le plus d'impact. Il faut donc surveiller le contexte réseau en plus du fournisseur.</p></div>`};renderPriority();
    ["cause-state","lot-state"].forEach(id=>{$(id).innerHTML=data.states.map(item=>`<option value="${esc(item.id)}">${esc(stateLabel(item.id))}</option>`)});
    const suppliersFor=stateId=>[...new Set(data.supplierStatistics.filter(row=>row.state===stateId).map(row=>row.supplier))].sort();
    const prioritySuppliersFor=stateId=>[...new Set(data.priorities.filter(row=>row.state===stateId).sort((a,b)=>a.position-b.position).map(row=>row.supplier))];
    const fillSupplierSelect=(select,stateId,priorityOnly=false)=>{const first=prioritySuppliersFor(stateId),candidates=priorityOnly?first:[...first,...suppliersFor(stateId).filter(value=>!first.includes(value))];select.innerHTML=candidates.map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join("")};
    const causeState=$("cause-state"),causeSupplier=$("cause-supplier");fillSupplierSelect(causeSupplier,causeState.value);
    const renderCauses=()=>{const stateId=causeState.value,supplier=causeSupplier.value,rows=data.supplierStatistics.filter(row=>row.state===stateId&&row.supplier===supplier);$("cause-cards").innerHTML=data.mechanisms.map(m=>{const row=rows.find(item=>item.mechanism===m.id);if(!row)return`<article class="cause-card"><h3>${esc(m.label)}</h3><div class="empty">Résultat absent.</div></article>`;return`<article class="cause-card"><span class="badge sim">HYPOTHÈSE</span><h3>${esc(m.label)}</h3><p>${esc(m.hypothesis)}</p><div class="metric-grid"><div class="metric"><strong>${pp(row.service.mean)}</strong><small>service global perdu</small></div><div class="metric"><strong>${backlogValue(row)}</strong><small>retard cumulé supplémentaire</small></div><div class="metric"><strong>${productionValue(row)}</strong><small>production du produit alimenté non libérée</small></div><div class="metric"><strong>${pct(row.service.positiveRate)}</strong><small>répétitions avec effet positif</small></div></div><div class="uncertainty"><b>Incertitude simulée :</b> moyenne ${pp(row.service.mean)} · intervalle à 95 % ${metricCi(row.service)} · cas défavorable P90 ${pp(row.service.p90)}.</div><div class="explain"><b>Lecture métier :</b> ${esc(explanation(row))}</div></article>`}).join("");const laneRows=data.laneStatistics.filter(row=>row.state===stateId&&row.supplier===supplier).sort((a,b)=>(b.service.mean||0)-(a.service.mean||0));$("lane-table").innerHTML=laneRows.map(row=>`<tr><td>${esc(row.lane)}</td><td>${esc(row.item)} → ${esc(row.destination)}</td><td>${esc(mechanism(row.mechanism).shortLabel)}</td><td>${pp(row.service.mean)}<br><small>95 % : ${metricCi(row.service)}</small></td><td>${backlogValue(row)}</td><td>${productionValue(row)}</td><td>${comparisonBadge(row.lane)}</td></tr>`).join("")};causeState.onchange=()=>{fillSupplierSelect(causeSupplier,causeState.value);renderCauses()};causeSupplier.onchange=renderCauses;renderCauses();
    const lotState=$("lot-state"),lotSupplier=$("lot-supplier");fillSupplierSelect(lotSupplier,lotState.value,true);
    const renderLots=()=>{const stateId=lotState.value,supplier=lotSupplier.value,row=data.priorities.find(item=>item.state===stateId&&item.supplier===supplier),target=row?registryFor(row.lane):null,stateTarget=target&&target.states[stateId];if(!row){$("target-summary").innerHTML='<div class="empty">Aucun signal positif dans cet état.</div>';return}const windowText=stateTarget&&stateTarget.windowStartMin!=null?`Début entre J${stateTarget.windowStartMin} et J${stateTarget.windowStartMax}`:"fenêtre non chargée";const windowDays=target&&target.windowDays?target.windowDays:data.targetRegistry.windowDays;$("target-summary").innerHTML=`<article class="target-card"><span class="badge sim">SIMULÉ</span><h3>${esc(row.supplier)} · ${esc(row.item)} → ${esc(row.destination)}</h3><p>Voie ${esc(row.lane)} · fenêtre de ${esc(windowDays||"—")} jours · ${esc(windowText)}.</p><p><b>Quantité planifiée médiane ciblée :</b> ${stateTarget?fmt(stateTarget.quantityMedian,0):"—"} ${stateTarget?esc(stateTarget.uom||"unités"):""}<br><b>Expéditions médianes regroupées :</b> ${stateTarget?fmt(stateTarget.shipmentCountMedian,0):"—"}</p>${comparisonBadge(row)}</article><article class="target-card"><span class="badge pending">REPLAY À COMPLÉTER</span><h3>Preuves lot et client manquantes</h3><p>À produire : lots fournisseurs reçus, consommations de stock, ordres de production, lots finis, commandes clientes, dates et quantités reliées.</p></article>`;$("chain-target").textContent=`${row.item} vers ${row.destination}, ${windowText.toLowerCase()}.`};lotState.onchange=()=>{fillSupplierSelect(lotSupplier,lotState.value,true);renderLots()};lotSupplier.onchange=renderLots;renderLots();const initialView=location.hash.slice(1);if(["priority","causes","lots"].includes(initialView)&&initialView!=="priority")setView(initialView,false);
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
        help="Dossier compact produit par le finalizer V2.",
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
