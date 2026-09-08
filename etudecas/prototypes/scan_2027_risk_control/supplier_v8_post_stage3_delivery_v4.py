#!/usr/bin/env python3
"""Build the additive, three-view, offline supplier-risk delivery V4.

This module is a read-only consumer of a *completed* V8 Stage3 V3 delivery,
its independently reproduced closure report and the separately validated
338929 focus.  It never starts the simulation engine, never changes the
scientific dossier selection and never writes inside an upstream root.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import shutil
import sys
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lot_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_curves as curves_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_post_stage3_focus_338929 as focus_v1,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_delivery as delivery_v3,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_pipeline as pipeline_v3,
)
from etudecas.prototypes.scan_2027_risk_control import (
    verify_supplier_v8_stage3_closure as closure_v1,
)


SCHEMA_VERSION = "etudecas.supplier_v8_post_stage3_delivery_v4.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
OUTPUT_NAME = "OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_FINAL_V4.html"
MANIFEST_NAME = f"{OUTPUT_NAME}.manifest.json"
VIEW_IDS = ("focus", "network", "decisions")
STATE_ORDER = ("op_100", "op_93", "op_80")
MECHANISM_ORDER = ("transport_delay", "planned_delivery_shortfall")
EXPECTED_NOMINAL_SERIES = 108
EXPECTED_NOMINAL_SUBJECTS = 36
EXPECTED_STOCK_SUBJECTS = 18
FOCUS_IDENTITY = {
    "supplier_id": "SDC-VD0914360C",
    "item_id": "338929",
    "dst_node_id": "M-1810",
    "edge_id": "edge:SDC-VD0914360C_TO_M-1810_338929",
    "lane_id": "sdc_vd0914360c_338929_m_1810",
    "target_product_id": "268091",
}

DOMAIN_LABELS = {
    "service": "Service client",
    "production": "Production",
    "stock_entrant": "Stocks d'articles à l'usine",
    "contrainte": "Contraintes de production",
}
METRIC_LABELS = {
    "service_a_l_heure": "Service à l'heure",
    "retard_client": "Retard client agrégé",
    "production_liberee": "Production libérée",
    "production_achevee": "Production achevée",
    "encours": "Encours de production",
    "stock_produit_fini": "Stock de produit fini",
    "stock_entrant": "Stock de l'article à l'usine",
    "ecart_plan_lot": "Écart de production au plan de lots",
    "penurie_entree": "Jours avec manque d'entrée par rapport au plan",
}
FOCUS_CURVE_DEFINITIONS = (
    ("component_stock", "Stock de l'article 338929 à l'usine", "UN", 7),
    ("wip", "Encours du produit 268091", "UN", 7),
    ("production_released", "Production libérée du produit 268091", "UN/jour", 28),
    ("served_on_due", "Service à l'heure du produit 268091", "%", 28),
    ("backlog", "Retard client agrégé du produit 268091", "UN", 7),
)
PRESET_SUBJECTS = {
    ("service", "global", "service_a_l_heure"): 0,
    ("service", "268091", "service_a_l_heure"): 1,
    ("service", "268091", "retard_client"): 2,
    ("stock_entrant", "M-1810|338929", "stock_entrant"): 3,
    ("production", "268091", "encours"): 4,
    ("production", "268091", "production_liberee"): 5,
    ("contrainte", "268091", "ecart_plan_lot"): 6,
    ("contrainte", "268091", "penurie_entree"): 7,
}

_EXTERNAL_URL_RE = re.compile(
    r"(?is)(?:\b(?:src|href|srcset|action)\s*=\s*['\"]\s*(?:https?:|//))"
    r"|(?:\burl\(\s*['\"]?\s*(?:https?:|//))"
    r"|(?:\b@import\s+(?:url\()?\s*['\"]?\s*(?:https?:|//))"
    r"|(?:<meta\b[^>]*http-equiv\s*=\s*['\"]?refresh\b)"
    r"|(?:\bhttps?://[^\s'\"<>]+)"
)
_NETWORK_API_RE = re.compile(
    r"(?i)\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\b"
    r"|navigator\s*\.\s*sendBeacon"
    r"|serviceWorker"
    r"|\bimport\s*\("
)
_WINDOWS_PATH_RE = re.compile(
    r"(?i)(?:\b[a-z]:(?:[\\/]|(?=[^\s<>]))|file\s*://"
    r"|\\\\[A-Za-z0-9_.-]+(?:\\|/)|(?<![:/])//[A-Za-z0-9_.-]+/)"
)
_NETWORK_NAVIGATION_RE = re.compile(
    r"(?is)\b(?:window\s*\.\s*)?location(?:\s*\.\s*href)?\s*=\s*"
    r"['\"]\s*(?:https?:|//)"
)


class DeliveryV4Error(RuntimeError):
    """An upstream proof or the additive delivery violates the V4 contract."""


@dataclass(frozen=True)
class CollectedEvidence:
    """Deterministic presentation payload plus non-embedded source bindings."""

    payload: dict[str, Any]
    sources: list[dict[str, Any]]
    snapshots: dict[Path, bytes]


def _canonical_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalise_item(value: Any) -> str:
    return str(value or "").strip().removeprefix("item:")


def _finite(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DeliveryV4Error(f"Valeur numérique invalide : {label}") from exc
    if not math.isfinite(result):
        raise DeliveryV4Error(f"Valeur non finie : {label}")
    return result


def _source_binding(
    path: Path, role: str, *, signature: str | None = None
) -> dict[str, Any]:
    source = path.resolve()
    if not source.is_file():
        raise DeliveryV4Error(f"Preuve absente : {role}")
    result = {
        "role": role,
        "name": source.name,
        "sha256": common.sha256_file(source),
        "bytes": source.stat().st_size,
    }
    if signature:
        result["signature"] = signature
    return result


def _snapshot(paths: Sequence[Path]) -> dict[Path, bytes]:
    output: dict[Path, bytes] = {}
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file():
            raise DeliveryV4Error(f"Preuve protégée absente : {resolved.name}")
        output[resolved] = resolved.read_bytes()
    return output


def _assert_snapshots_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, expected in snapshots.items():
        if not path.is_file() or path.read_bytes() != expected:
            raise DeliveryV4Error(
                f"Une preuve amont a changé pendant la construction : {path.name}"
            )


def _validate_closure(
    stage3_supervision_dir: Path, closure_report: Path
) -> tuple[closure_v1.FinalContext, dict[str, Any]]:
    context = closure_v1.load_final_context(stage3_supervision_dir.resolve())
    report_path = closure_report.resolve()
    report = common.read_json(report_path)
    try:
        common.verify_signature(report, "closure_signature", "clôture Stage3 V3")
    except Exception as exc:
        raise DeliveryV4Error("Signature du rapport de clôture invalide") from exc
    expected = closure_v1.build_closure_report(context)
    technical = report.get("technical_verdict") or {}
    if (
        report != expected
        or report.get("schema_version") != closure_v1.SCHEMA_VERSION
        or report.get("status") != "complete_audited"
        or technical.get("conforme") is not True
        or report.get("no_simulation_engine_started") is not True
    ):
        raise DeliveryV4Error(
            "La clôture Stage3 n'est pas complète, reproductible et techniquement conforme"
        )
    return context, report


def _expected_nominal_subjects(
    series: Sequence[Mapping[str, Any]],
) -> set[tuple[str, str, str, int]]:
    stock_entities = {
        str(row.get("entity") or "")
        for row in series
        if row.get("domain") == "stock_entrant"
    }
    if (
        len(stock_entities) != EXPECTED_STOCK_SUBJECTS
        or "M-1810|338929" not in stock_entities
    ):
        raise DeliveryV4Error("Le périmètre des 18 stocks entrants est incomplet")
    subjects = {
        ("service", entity, metric, window)
        for entity in ("global", "268091", "268967")
        for metric, window in (
            ("service_a_l_heure", 28),
            ("retard_client", 7),
        )
    }
    subjects.update(
        ("production", entity, metric, window)
        for entity in ("268091", "268967")
        for metric, window in (
            ("production_liberee", 28),
            ("production_achevee", 28),
            ("encours", 7),
            ("stock_produit_fini", 7),
        )
    )
    subjects.update(
        ("stock_entrant", entity, "stock_entrant", 7) for entity in stock_entities
    )
    subjects.update(
        ("contrainte", entity, metric, window)
        for entity in ("268091", "268967")
        for metric, window in (("ecart_plan_lot", 28), ("penurie_entree", 7))
    )
    if len(subjects) != EXPECTED_NOMINAL_SUBJECTS:
        raise DeliveryV4Error("Les 36 sujets nominaux attendus ne sont pas présents")
    return subjects


def _entity_label(domain: str, entity: str) -> str:
    if entity == "global":
        return "Réseau global"
    if domain == "stock_entrant":
        try:
            node, item = entity.split("|", maxsplit=1)
        except ValueError as exc:
            raise DeliveryV4Error("Identité usine–article invalide") from exc
        return f"{node} · article {item} (stock à l'usine)"
    return f"Produit {entity}"


def _prepare_nominal_curves(curve_payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_series = curve_payload.get("series")
    if not isinstance(raw_series, list) or len(raw_series) != EXPECTED_NOMINAL_SERIES:
        raise DeliveryV4Error("Le paquet nominal ne contient pas exactement 108 séries")
    if (curve_payload.get("scope") or {}).get("case_count") != 90:
        raise DeliveryV4Error("Les courbes nominales ne portent pas les 90 références")
    subjects = _expected_nominal_subjects(raw_series)
    actual: set[tuple[str, str, str, str, int]] = set()
    reduced: list[dict[str, Any]] = []
    by_subject: dict[tuple[str, str, str, int], set[str]] = defaultdict(set)
    for row in raw_series:
        if not isinstance(row, Mapping):
            raise DeliveryV4Error("Série nominale non structurée")
        state = str(row.get("state") or "")
        domain = str(row.get("domain") or "")
        entity = str(row.get("entity") or "")
        metric = str(row.get("metric") or "")
        window = int(row.get("rolling_window_days") or -1)
        key = (state, domain, entity, metric, window)
        subject = (domain, entity, metric, window)
        points = row.get("points")
        if (
            key in actual
            or state not in STATE_ORDER
            or subject not in subjects
            or row.get("columns") != ["day", "mean", "p10", "median", "p90"]
            or int(row.get("sample_count") or -1) != 30
            or not isinstance(points, list)
            or len(points) != 720 - window + 1
        ):
            raise DeliveryV4Error("Contrat d'une série nominale invalide")
        actual.add(key)
        by_subject[subject].add(state)
        display_points: list[list[float | int]] = []
        for index, point in enumerate(points):
            expected_day = window - 1 + index
            if (
                not isinstance(point, list)
                or len(point) != 5
                or point[0] != expected_day
            ):
                raise DeliveryV4Error("Horizon nominal quotidien incomplet")
            values = [_finite(value, label="point nominal") for value in point[1:]]
            if not values[1] <= values[2] <= values[3]:
                raise DeliveryV4Error("Quantiles nominaux non ordonnés")
            if index % 7 == 0 or index == len(points) - 1:
                display_points.append([expected_day, *values])
        reduced.append(
            {
                "state": state,
                "domain": domain,
                "entity": entity,
                "metric": metric,
                "unit": str(row.get("unit") or ""),
                "rolling_window_days": window,
                "sample_count": 30,
                "columns": ["day", "mean", "p10", "median", "p90"],
                "points": display_points,
            }
        )
    expected_keys = {(state, *subject) for state in STATE_ORDER for subject in subjects}
    if actual != expected_keys or any(
        states != set(STATE_ORDER) for states in by_subject.values()
    ):
        raise DeliveryV4Error("Inventaire nominal 108/36 incomplet ou dupliqué")

    subject_rows = []
    for domain, entity, metric, window in subjects:
        preset_order = PRESET_SUBJECTS.get((domain, entity, metric))
        subject_rows.append(
            {
                "id": f"{domain}|{entity}|{metric}|{window}",
                "domain": domain,
                "domain_label_fr": DOMAIN_LABELS[domain],
                "entity": entity,
                "entity_label_fr": _entity_label(domain, entity),
                "metric": metric,
                "metric_label_fr": METRIC_LABELS[metric],
                "rolling_window_days": window,
                "is_preset": preset_order is not None,
                "preset_order": preset_order,
            }
        )
    subject_rows.sort(
        key=lambda row: (
            row["preset_order"] is None,
            row["preset_order"] if row["preset_order"] is not None else 999,
            row["domain_label_fr"],
            row["entity_label_fr"],
            row["metric_label_fr"],
        )
    )
    reduced.sort(
        key=lambda row: (
            next(
                index
                for index, subject in enumerate(subject_rows)
                if subject["id"]
                == (
                    f"{row['domain']}|{row['entity']}|{row['metric']}|"
                    f"{row['rolling_window_days']}"
                )
            ),
            STATE_ORDER.index(row["state"]),
        )
    )
    return {
        "source_series_count": EXPECTED_NOMINAL_SERIES,
        "logical_subject_count": EXPECTED_NOMINAL_SUBJECTS,
        "state_count": len(STATE_ORDER),
        "source_horizon_days": 720,
        "source_simulations_per_state": 30,
        "weekly_display_sampling_after_smoothing": True,
        "scientific_acceptance_population": False,
        "interpretation_fr": (
            "Fonctionnement sans incident : moyenne et dispersion de 30 simulations "
            "indépendantes par niveau. Ces courbes ne donnent pas une probabilité "
            "d'incident fournisseur."
        ),
        "subjects": subject_rows,
        "series": reduced,
    }


def _identity_from_priority(priority: Mapping[str, Any]) -> dict[str, str]:
    return {
        "supplier_id": str(priority.get("supplier_id") or ""),
        "item_id": _normalise_item(priority.get("item_id")),
        "dst_node_id": str(priority.get("dst_node_id") or ""),
        "edge_id": str(priority.get("edge_id") or ""),
        "lane_id": str(priority.get("lane_id") or ""),
        "target_product_id": _normalise_item(priority.get("target_product_id")),
    }


def _prepare_focus_curves(
    curve_rows: Sequence[Mapping[str, Any]], *, horizon: int
) -> list[dict[str, Any]]:
    expected_metrics = {
        "component_stock",
        "production_released",
        "wip",
        "demand",
        "served_on_due",
        "backlog",
    }
    by_metric: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in curve_rows:
        by_metric[str(row.get("metric") or "")].append(row)
    if set(by_metric) != expected_metrics:
        raise DeliveryV4Error("Les six séries quotidiennes du focus sont incomplètes")
    dense: dict[str, tuple[list[float], list[float]]] = {}
    for metric in expected_metrics:
        rows = sorted(by_metric[metric], key=lambda row: int(row.get("day") or 0))
        if len(rows) != horizon or [int(row.get("day") or 0) for row in rows] != list(
            range(horizon)
        ):
            raise DeliveryV4Error(f"Horizon focus incomplet : {metric}")
        dense[metric] = (
            [_finite(row.get("baseline_value"), label=metric) for row in rows],
            [_finite(row.get("incident_value"), label=metric) for row in rows],
        )

    output = []
    for metric, label, unit, window in FOCUS_CURVE_DEFINITIONS:
        if metric == "served_on_due":
            baseline, incident = dense[metric]
            baseline_demand, incident_demand = dense["demand"]
            if any(
                not math.isclose(left, right, abs_tol=1e-6, rel_tol=1e-12)
                for left, right in zip(baseline_demand, incident_demand, strict=True)
            ):
                raise DeliveryV4Error("La demande du focus diffère entre les deux bras")
            smooth_baseline = curves_v7.curve_v4.rolling_ratio(
                baseline, baseline_demand, window
            )
            smooth_incident = curves_v7.curve_v4.rolling_ratio(
                incident, incident_demand, window
            )
            raw = [
                [
                    day,
                    100.0 * baseline[day] / baseline_demand[day]
                    if baseline_demand[day] > 0
                    else None,
                    100.0 * incident[day] / incident_demand[day]
                    if incident_demand[day] > 0
                    else None,
                ]
                for day in range(horizon)
            ]
            smooth = [
                [day, 100.0 * smooth_baseline[day], 100.0 * smooth_incident[day]]
                for day in range(horizon)
                if smooth_baseline[day] is not None and smooth_incident[day] is not None
            ]
        else:
            baseline, incident = dense[metric]
            smooth_baseline = curves_v7.curve_v4.rolling_mean(baseline, window)
            smooth_incident = curves_v7.curve_v4.rolling_mean(incident, window)
            raw = [[day, baseline[day], incident[day]] for day in range(horizon)]
            smooth = [
                [day, smooth_baseline[day], smooth_incident[day]]
                for day in range(horizon)
                if smooth_baseline[day] is not None and smooth_incident[day] is not None
            ]
        output.append(
            {
                "metric": metric,
                "label_fr": label,
                "unit": unit,
                "rolling_window_days": window,
                "raw": raw,
                "smooth": smooth,
            }
        )
    return output


def _validate_focus_plan(plan: Mapping[str, Any]) -> None:
    dossiers = plan.get("dossiers")
    contract = plan.get("scientific_contract") or {}
    if (
        plan.get("schema_version") != focus_v1.PLAN_SCHEMA
        or plan.get("selection_basis") != focus_v1.SELECTION_BASIS
        or plan.get("supplier_id") != FOCUS_IDENTITY["supplier_id"]
        or _normalise_item(plan.get("item_id")) != FOCUS_IDENTITY["item_id"]
        or not isinstance(dossiers, list)
        or len(dossiers) != 2
        or contract.get("priority_claimed") is not False
        or contract.get("quality_included") is not False
        or contract.get("state_dependent_risks_enabled") is not False
        or contract.get("capacity_or_availability_modified") is not False
        or contract.get("common_random_numbers") is not True
        or contract.get("seed_selection_uses_outcomes") is not False
    ):
        raise DeliveryV4Error("Le plan du focus 338929 ne respecte pas son contrat")
    seeds = set()
    mechanisms = set()
    windows = set()
    for row in dossiers:
        if not isinstance(row, Mapping) or row.get("mode") not in {
            "reuse_stage3",
            "new_focus",
        }:
            raise DeliveryV4Error("Mode du focus 338929 invalide")
        dossier = row.get("dossier")
        if not isinstance(dossier, Mapping):
            raise DeliveryV4Error("Dossier du focus absent")
        priority = dossier.get("priority") or {}
        risk = dossier.get("risk_row") or {}
        identity = _identity_from_priority(priority)
        mechanism = str(priority.get("mechanism") or "")
        start = int(_finite(risk.get("start_day"), label="début du focus"))
        end = int(_finite(risk.get("end_day"), label="fin du focus"))
        if (
            identity != FOCUS_IDENTITY
            or str(priority.get("operating_point_id") or "") != "op_93"
            or mechanism not in MECHANISM_ORDER
            or end - start + 1 != 42
            or start < 180
            or int(dossier.get("seed") or -1) != int(plan.get("common_seed") or -2)
        ):
            raise DeliveryV4Error("Identité, niveau ou fenêtre du focus invalide")
        seeds.add(int(dossier["seed"]))
        mechanisms.add(mechanism)
        windows.add((start, end))
    if len(seeds) != 1 or mechanisms != set(MECHANISM_ORDER) or len(windows) != 1:
        raise DeliveryV4Error("Les deux hypothèses du focus ne sont pas appariées")


def _prepare_focus(
    plan: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_focus_plan(plan)
    traces = validation.get("dossiers")
    if (
        validation.get("schema_version") != focus_v1.VALIDATION_SCHEMA
        or validation.get("status") != "complete_validated"
        or validation.get("selection_basis") != focus_v1.SELECTION_BASIS
        or not isinstance(traces, list)
        or len(traces) != 2
    ):
        raise DeliveryV4Error("Le focus 338929 n'est pas complètement validé")
    trace_by_id = {str(row.get("dossier_id") or ""): row for row in traces}
    if len(trace_by_id) != 2 or "" in trace_by_id:
        raise DeliveryV4Error("Validation du focus dupliquée ou incomplète")

    details = []
    for position, row in enumerate(plan["dossiers"], start=1):
        dossier = row["dossier"]
        dossier_id = str(dossier.get("dossier_id") or "")
        trace_proof = trace_by_id.get(dossier_id)
        if trace_proof is None or trace_proof.get("mode") != row.get("mode"):
            raise DeliveryV4Error("Trace du focus non rattachée à son dossier")
        try:
            lot_v4._validate_pair(dossier)  # noqa: SLF001
            reducer_dossier = copy.deepcopy(dossier)
            if "incident_metric" not in reducer_dossier:
                provenance = reducer_dossier.get("source_provenance") or {}
                incident_metric = provenance.get("incident_metric")
                if not isinstance(incident_metric, Mapping):
                    raise DeliveryV4Error(
                        "Métrique incidente absente du nouveau dossier focus"
                    )
                reducer_dossier["incident_metric"] = copy.deepcopy(incident_metric)
            curve_rows, lags, kpis = lot_v4._paired_curves_and_kpis(  # noqa: SLF001
                Path(dossier["arms"]["baseline"]["run_dir"]),
                Path(dossier["arms"]["incident"]["run_dir"]),
                dossier=reducer_dossier,
            )
        except Exception as exc:
            raise DeliveryV4Error(
                f"Reconstruction en lecture seule impossible : {dossier_id}"
            ) from exc
        priority = dossier["priority"]
        identity = _identity_from_priority(priority)
        risk = dossier["risk_row"]
        trace = copy.deepcopy(trace_proof.get("trace") or {})
        counts = {key: len(value) for key, value in trace.items()}
        if counts != trace_proof.get("counts"):
            raise DeliveryV4Error("Les comptages de lots du focus ont changé")
        horizon = int(dossier["horizon_days"])
        details.append(
            {
                "trajectory_label_fr": f"Trajectoire {position}",
                "dossier_id": dossier_id,
                "mode": row["mode"],
                "selection_basis": focus_v1.SELECTION_BASIS,
                "operating_point_id": "op_93",
                "mechanism": str(priority["mechanism"]),
                **identity,
                "risk_window_start_day": int(risk["start_day"]),
                "risk_window_end_day": int(risk["end_day"]),
                "impact_window_start_day": int(kpis["impact_window_start_day"]),
                "impact_window_end_day": int(kpis["impact_window_end_day"]),
                "single_trajectory": True,
                "trajectory_selection_uses_service_outcomes": False,
                "trajectory_interpretation_fr": (
                    "Une trajectoire illustrative choisie sur l'exposition physique, "
                    "sans regarder le résultat de service; ce n'est pas la moyenne."
                ),
                "curves": {
                    "horizon_days": horizon,
                    "series": _prepare_focus_curves(curve_rows, horizon=horizon),
                },
                "kpis": copy.deepcopy(kpis),
                "equal_cumulative_volume_lags": copy.deepcopy(lags),
                "trace_completeness": str(trace_proof["trace_completeness"]),
                "trace_counts": counts,
                "trace": trace,
                "cross_arm_lot_matching_used": False,
            }
        )
    details.sort(key=lambda row: MECHANISM_ORDER.index(row["mechanism"]))
    return {
        "selection_basis": focus_v1.SELECTION_BASIS,
        "focus_is_user_requested": True,
        "focus_is_priority_claim": False,
        "identity": dict(FOCUS_IDENTITY),
        "operating_point_id": "op_93",
        "common_seed": int(plan["common_seed"]),
        "plan_signature": str(plan["plan_signature"]),
        "validation_signature": str(validation["validation_signature"]),
        "mechanisms": list(MECHANISM_ORDER),
        "details": details,
        "action_results": [],
        "focus_actions_simulated_by_this_step": False,
        "full_dynamic_cascade_claimed": False,
    }


def _load_complete_focus(
    focus_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use the public focus validator and reject its legitimate plan-only state."""

    validation = focus_v1.validate(focus_root.resolve())
    if validation.get("status") != "complete_validated":
        raise DeliveryV4Error(
            "Le focus 338929 doit être exécuté, finalisé et complètement validé"
        )
    plan = focus_v1.load_plan(focus_root.resolve())
    return plan, validation


def _revalidate_focus_selection(
    context: closure_v1.FinalContext, plan: Mapping[str, Any]
) -> None:
    """Recompute the outcome-blind common seed and complete physical predicate.

    This additive check deliberately complements the public focus validator.  It
    can be removed only after an independently reviewed focus schema makes the
    same recomputation part of its public validation contract.
    """

    campaign = context.paths.campaign_root.resolve()
    manifest_path = campaign / "campaign_manifest.json"
    try:
        manifest = lot_v4._verify_campaign_manifest(manifest_path)  # noqa: SLF001
        _, _, metric_paths = lot_v4._validate_campaign_results(  # noqa: SLF001
            campaign_root=campaign,
            results_dir=context.paths.results_dir,
            manifest_path=manifest_path,
            manifest=manifest,
        )
        metric_rows = lot_v4._load_metric_rows(metric_paths)  # noqa: SLF001
        expected_seed = focus_v1.select_common_seed(metric_rows)
    except Exception as exc:
        raise DeliveryV4Error(
            "Impossible de reproduire la sélection physique du focus"
        ) from exc
    if int(plan.get("common_seed") or -1) != expected_seed:
        raise DeliveryV4Error(
            "La graine commune du focus ne reproduit pas la médiane d'exposition"
        )
    for row in plan.get("dossiers") or []:
        dossier = row.get("dossier") or {}
        priority = dossier.get("priority") or {}
        provenance = dossier.get("source_provenance") or {}
        incident = dossier.get("incident_metric") or provenance.get("incident_metric")
        if not isinstance(incident, Mapping):
            raise DeliveryV4Error("Métrique incidente du focus absente")
        mechanism = str(priority.get("mechanism") or "")
        dose_field = (
            "incident_effective_dose_qty_days"
            if mechanism == "transport_delay"
            else "incident_effective_dose_qty"
        )
        try:
            predicate = (
                str(incident.get("stage") or "") == "incident"
                and str(incident.get("operating_point_id") or "") == "op_93"
                and str(incident.get("mechanism") or "") == mechanism
                and str(incident.get("lane_id") or "") == FOCUS_IDENTITY["lane_id"]
                and int(incident.get("seed") or -1) == expected_seed
                and str(incident.get("status") or "") == "valid"
                and lot_v4._truthy(incident.get("valid"))  # noqa: SLF001
                and lot_v4._truthy(  # noqa: SLF001
                    incident.get("incident_physically_exercised")
                )
                and int(float(incident.get("risk_applied_row_count") or 0)) >= 1
                and int(float(incident.get("risk_applied_event_count") or 0)) >= 1
                and float(incident.get("target_planned_qty") or 0) > 0
                and float(incident.get("target_shipped_qty") or 0) > 0
                and float(incident.get(dose_field) or 0) > 0
                and float(incident.get("baseline_lane_shipped_qty_state_window") or 0)
                > 0
            )
        except (TypeError, ValueError) as exc:
            raise DeliveryV4Error("Prédicat physique du focus illisible") from exc
        if not predicate:
            raise DeliveryV4Error(
                "Le focus ne satisfait pas le prédicat physique complet"
            )


def _validate_stage3_payload(
    payload: Mapping[str, Any], selection: Sequence[Mapping[str, Any]]
) -> None:
    try:
        common.verify_signature(payload, "payload_signature", "payload Stage3 V3")
    except Exception as exc:
        raise DeliveryV4Error("Signature du payload Stage3 invalide") from exc
    selection_ids = [str(row.get("dossier_id") or "") for row in selection]
    details = (payload.get("cascade") or {}).get("detailed_replays") or []
    detail_ids = [str(row.get("dossier_id") or "") for row in details]
    actions = (payload.get("actions") or {}).get("actions") or []
    action_ids = {str(row.get("dossier_id") or "") for row in actions}
    limits = payload.get("limits") or {}
    terms = payload.get("terminology") or {}
    campaign = payload.get("campaign") or {}
    focus = payload.get("focus") or {}
    if (
        payload.get("schema_version") != delivery_v3.SCHEMA_VERSION
        or payload.get("status") != "complete_validated"
        or payload.get("view_count") != 3
        or set(terms) != {"OBSERVÉ", "SIMULÉ", "SIGNAL DE PRIORITÉ", "HYPOTHÈSE"}
        or selection_ids != detail_ids
        or "" in selection_ids
        or len(selection_ids) > 3
        or not action_ids.issubset(set(selection_ids))
        or campaign.get("incident_case_count") != 3_240
        or campaign.get("multiple_incidents_combined") is not False
        or limits.get("quality_incident_included") is not False
        or limits.get("capacity_or_availability_modified") is not False
        or limits.get("automatic_regulation") is not False
        or focus.get("lane_id") != FOCUS_IDENTITY["lane_id"]
        or _normalise_item(focus.get("item_id")) != FOCUS_IDENTITY["item_id"]
    ):
        raise DeliveryV4Error("Portée métier ou sélection Stage3 modifiée")


def _aggregate_focus_rows(stage3_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = (stage3_payload.get("focus") or {}).get("aggregate_incident_results")
    if not isinstance(rows, list) or len(rows) != 6:
        raise DeliveryV4Error("Les six résultats agrégés 338929 sont absents")
    keys = set()
    output = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise DeliveryV4Error("Résultat agrégé 338929 non structuré")
        key = (str(row.get("state") or ""), str(row.get("mechanism") or ""))
        identity = {
            "supplier_id": str(row.get("supplier_id") or ""),
            "item_id": _normalise_item(row.get("item_id")),
            "dst_node_id": str(row.get("dst_node_id") or ""),
            "lane_id": str(row.get("lane_id") or ""),
            "target_product_id": _normalise_item(row.get("target_product_id")),
        }
        expected_identity = {
            key: value for key, value in FOCUS_IDENTITY.items() if key != "edge_id"
        }
        if key in keys or identity != expected_identity:
            raise DeliveryV4Error("Résultat agrégé 338929 mal attribué")
        keys.add(key)
        output.append(copy.deepcopy(dict(row)))
    if keys != {
        (state, mechanism) for state in STATE_ORDER for mechanism in MECHANISM_ORDER
    }:
        raise DeliveryV4Error("Matrice agrégée 338929 incomplète")
    return output


def _matching_focus_actions(
    stage3_payload: Mapping[str, Any], selection: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    selected = {
        str(row.get("dossier_id") or "")
        for row in selection
        if str(row.get("lane_id") or "") == FOCUS_IDENTITY["lane_id"]
        and _normalise_item(row.get("item_id")) == FOCUS_IDENTITY["item_id"]
    }
    output = []
    for action in (stage3_payload.get("actions") or {}).get("actions") or []:
        if (
            str(action.get("dossier_id") or "") in selected
            and str(action.get("lane_id") or "") == FOCUS_IDENTITY["lane_id"]
            and _normalise_item(action.get("item_id")) == FOCUS_IDENTITY["item_id"]
        ):
            output.append(copy.deepcopy(dict(action)))
    return output


def collect_evidence(
    stage3_supervision_dir: Path,
    closure_report: Path,
    focus_root: Path,
) -> CollectedEvidence:
    """Revalidate and reduce existing evidence without starting any engine."""

    context, closure = _validate_closure(stage3_supervision_dir, closure_report)
    paths = context.paths.resolved()
    focus_root = focus_root.resolve()
    v3_manifest_path = Path(str(paths.final_html) + ".manifest.json")
    selection_path = paths.results_dir / "lot_replay_plan.json"
    focus_files = [
        focus_root / "focus_plan.json",
        focus_root / "focus_run_receipt.json",
        focus_root / "focus_validation.json",
    ]
    protected_files = [
        paths.final_html,
        v3_manifest_path,
        paths.supervision_dir / pipeline_v3.CONTRACT_NAME,
        paths.supervision_dir / pipeline_v3.STATUS_NAME,
        closure_report.resolve(),
        selection_path,
        paths.curves_dir / curves_v7.MANIFEST_NAME,
        paths.curves_dir / curves_v7.PAYLOAD_NAME,
        *focus_files,
    ]
    snapshots = _snapshot(protected_files)
    delivery_result = delivery_v3.validate_delivery(paths)
    stage3_payload, stage3_sources = delivery_v3.collect_payload(paths)
    stage3_source_paths: list[Path] = []
    for source in stage3_sources:
        if not isinstance(source, Mapping):
            raise DeliveryV4Error("Liaison source Stage3 non structurée")
        source_path = Path(str(source.get("path") or "")).resolve()
        if not source_path.is_file():
            raise DeliveryV4Error("Une source déclarée par Stage3 est absente")
        stage3_source_paths.append(source_path)
    if len(stage3_source_paths) != len(set(stage3_source_paths)):
        raise DeliveryV4Error("Une source Stage3 est déclarée plusieurs fois")
    snapshots.update(_snapshot(stage3_source_paths))
    stage3_bytes = common.canonical_json_bytes(stage3_payload)

    selection = pipeline_v3._selection(paths.results_dir)  # noqa: SLF001
    _validate_stage3_payload(stage3_payload, selection)
    selection_payload = common.read_json(selection_path)
    try:
        common.verify_signature(
            selection_payload,
            "selection_signature",
            "sélection scientifique Stage3",
        )
    except Exception as exc:
        raise DeliveryV4Error("Signature de la sélection Stage3 invalide") from exc
    if selection_payload.get("selected_dossiers") != list(selection):
        raise DeliveryV4Error("La sélection chargée diffère du plan signé")

    curve_proof = curves_v7.validate_curve_package(
        paths.curves_dir,
        plan_dir=paths.v7_plan_dir,
        run_dir=paths.v7_run_dir,
    )
    curve_payload = curves_v7.load_curve_payload(paths.curves_dir)
    nominal = _prepare_nominal_curves(curve_payload)

    focus_plan, focus_validation = _load_complete_focus(focus_root)
    _revalidate_focus_selection(context, focus_plan)
    arm_files: list[Path] = []
    for row in focus_plan.get("dossiers") or []:
        dossier = row.get("dossier") or {}
        for arm in ("baseline", "incident"):
            run_dir = Path(
                str((dossier.get("arms") or {}).get(arm, {}).get("run_dir") or "")
            )
            try:
                arm_files.extend(lot_v4._required_run_files(run_dir).values())  # noqa: SLF001
            except Exception as exc:
                raise DeliveryV4Error("Fichiers d'un bras focus absents") from exc
    arm_snapshots = _snapshot(arm_files)
    snapshots.update(arm_snapshots)
    focus = _prepare_focus(focus_plan, focus_validation)
    focus["aggregate_results"] = _aggregate_focus_rows(stage3_payload)
    focus_actions = _matching_focus_actions(stage3_payload, selection)
    focus["action_results"] = focus_actions
    focus["focus_actions_simulated_by_this_step"] = False
    focus["focus_has_existing_signed_stage3_action"] = bool(focus_actions)

    if common.canonical_json_bytes(stage3_payload) != stage3_bytes:
        raise DeliveryV4Error("Le payload Stage3 a été modifié en mémoire")
    stage3_copy = copy.deepcopy(stage3_payload)
    selection_copy = copy.deepcopy(list(selection))
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_validated",
        "title": "Risques fournisseurs : du composant 338929 aux décisions prouvées",
        "view_count": 3,
        "terminology": copy.deepcopy(stage3_payload["terminology"]),
        "stage3": stage3_copy,
        "stage3_preservation": {
            "payload_signature": stage3_payload["payload_signature"],
            "canonical_payload_sha256": hashlib.sha256(stage3_bytes).hexdigest(),
            "selection_signature": selection_payload["selection_signature"],
            "selection_sha256": _canonical_sha256(selection_copy),
            "selection": selection_copy,
            "selection_order_preserved": True,
            "selection_modified": False,
            "focus_inserted_into_scientific_selection": False,
            "stage3_html_sha256": delivery_result["html_sha256"],
        },
        "requested_focus_338929": focus,
        "nominal_curves_full": nominal,
        "presentation": {
            "view_order": list(VIEW_IDS),
            "language": "fr",
            "standalone": True,
            "focus_is_user_requested": True,
            "focus_criticality_claimed": False,
            "aggregate_population": 30,
            "detailed_focus_is_single_trajectory": True,
            "network_subject_count": EXPECTED_NOMINAL_SUBJECTS,
            "network_series_count": EXPECTED_NOMINAL_SERIES,
        },
        "limits": {
            "one_incident_at_a_time": True,
            "multiple_or_correlated_incidents_simulated": False,
            "incident_is_exogenous": True,
            "consequences_depend_on_evolving_network_state": True,
            "historical_probability_available": False,
            "supplier_risk_prediction_calibrated": False,
            "quality_incident_included": False,
            "capacity_or_finished_product_availability_modified": False,
            "actions_open_loop": True,
            "automatic_regulation": False,
            "frequency_domain_poles_or_controllability_included": False,
            "full_dynamic_stock_mrp_production_service_cascade_proven": False,
            "action_lot_trace_available": False,
            "customers_are_aggregated": True,
            "lots_are_simulated": True,
            "cross_arm_same_lot_claimed": False,
            "days_recovered_cost_or_roi_claimed": False,
            "observed_2025_supplier_causality_claimed": False,
        },
        "bindings": {
            "closure_signature": closure["closure_signature"],
            "focus_plan_signature": focus_plan["plan_signature"],
            "focus_validation_signature": focus_validation["validation_signature"],
            "curve_manifest_signature": curve_proof["manifest_signature"],
            "nominal_curve_payload_signature": curve_proof["payload_signature"],
        },
    }
    payload = common.signed(unsigned, "payload_signature")
    if common.canonical_json_bytes(stage3_payload) != stage3_bytes:
        raise DeliveryV4Error("Le payload Stage3 a été altéré par la réduction V4")

    sources = [
        _source_binding(Path(__file__), "producteur_html_v4"),
        _source_binding(
            paths.final_html,
            "html_stage3_v3_intact",
            signature=stage3_payload["payload_signature"],
        ),
        _source_binding(v3_manifest_path, "manifeste_html_stage3_v3"),
        _source_binding(
            closure_report,
            "cloture_stage3_reproduite",
            signature=closure["closure_signature"],
        ),
        _source_binding(
            selection_path,
            "selection_scientifique_stage3_intacte",
            signature=selection_payload["selection_signature"],
        ),
        _source_binding(
            paths.curves_dir / curves_v7.MANIFEST_NAME,
            "manifeste_108_courbes_nominales",
            signature=curve_proof["manifest_signature"],
        ),
        _source_binding(
            paths.curves_dir / curves_v7.PAYLOAD_NAME,
            "donnees_108_courbes_nominales",
            signature=curve_proof["payload_signature"],
        ),
        _source_binding(
            focus_files[0],
            "plan_focus_338929",
            signature=focus_plan["plan_signature"],
        ),
        _source_binding(focus_files[1], "recu_focus_338929"),
        _source_binding(
            focus_files[2],
            "validation_focus_338929",
            signature=focus_validation["validation_signature"],
        ),
    ]
    for source in stage3_sources:
        if not isinstance(source, Mapping):
            raise DeliveryV4Error("Liaison source Stage3 non structurée")
        source_path = Path(str(source.get("path") or ""))
        if not source_path.is_file():
            raise DeliveryV4Error("Une source déclarée par Stage3 est absente")
        reduced_source = {
            "role": f"stage3::{source.get('role')}",
            "name": source_path.name,
            "sha256": str(source.get("sha256") or common.sha256_file(source_path)),
            "bytes": source_path.stat().st_size,
        }
        if source.get("signature"):
            reduced_source["signature"] = str(source["signature"])
        if reduced_source["sha256"] != common.sha256_file(source_path):
            raise DeliveryV4Error(
                "Une source Stage3 ne correspond plus à son empreinte"
            )
        sources.append(reduced_source)
    _assert_snapshots_unchanged(snapshots)
    return CollectedEvidence(payload=payload, sources=sources, snapshots=snapshots)


def _safe_json(payload: Mapping[str, Any]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>Risques fournisseurs — démonstration autonome finale</title>
<style>
:root{--navy:#092a4a;--blue:#1769d2;--teal:#087c68;--red:#d64232;--amber:#b56a00;--ink:#132b42;--muted:#607389;--line:#d5e1ec;--paper:#eef3f8;--card:#fff}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Segoe UI",Arial,sans-serif}header{padding:25px clamp(18px,4vw,58px);background:linear-gradient(120deg,#071d35,#164e7c 66%,#08776e);color:white}h1{font-size:clamp(28px,4vw,46px);line-height:1.08;margin:3px 0 9px}h2,h3{margin-top:0}header p{max-width:1020px;color:#dfedf7}.scope,.legend,.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pill,.badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:750}.pill{border:1px solid #ffffff55}.badge.obs{background:#e4f4ec;color:#07674f}.badge.sim{background:#e8f1ff;color:#174e96}.badge.hyp{background:#fff0dc;color:#784a00}.badge.focus{background:#fff0dc;color:#784a00;border:1px solid #e8b96f}.definitions{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#cbd9e6}.definition{background:white;padding:11px 16px}.definition b{display:block;color:var(--blue);font-size:11px}.definition span{font-size:12px;color:var(--muted)}.tabs{position:sticky;top:0;z-index:5;display:flex;justify-content:center;gap:8px;padding:10px;background:#f8fbfff2;border-bottom:1px solid var(--line)}button,select{font:inherit}.tabs button,.controls button,.controls select{border:1px solid #b6c9da;border-radius:999px;background:white;padding:8px 12px;color:var(--ink);cursor:pointer}.tabs button.active,.controls button.active{background:var(--navy);color:white;border-color:var(--navy)}main{max-width:1280px;margin:auto;padding:18px clamp(12px,3vw,30px) 48px}.view{display:none}.view.active{display:block}.panel,.question,.callout,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px;margin:12px 0;box-shadow:0 9px 25px #16334f0d}.question{border-left:6px solid var(--blue)}.callout{border-left:5px solid var(--amber);background:#fffaf0}.callout.good{border-left-color:var(--teal);background:#f2fbf7}.grid{display:grid;gap:10px}.three{grid-template-columns:repeat(3,1fr)}.four{grid-template-columns:repeat(4,1fr)}.two{grid-template-columns:repeat(2,1fr)}.metric b,.big{display:block;font-size:24px;color:var(--navy)}.muted,.small{color:var(--muted)}.small{font-size:11px}.chart{display:block;width:100%;height:330px;border:1px solid var(--line);border-radius:11px;background:#fbfdff}.table{overflow:auto;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;min-width:760px}th,td{padding:8px 9px;text-align:left;border-bottom:1px solid #e3ebf2;font-size:12px}th{background:#edf4fa;color:#244969}.chain{display:flex;gap:7px;overflow:auto}.step{flex:1;min-width:145px;border:1px solid var(--line);border-radius:10px;padding:10px;background:#f8fbff}.step.ok{background:#f2fbf7;border-color:#66ad94}.step.no{border-style:dashed;color:var(--muted)}.arrow{display:grid;place-items:center;color:var(--blue);font-size:20px}.pager{display:flex;gap:8px;align-items:center;margin-top:9px}details{margin-top:10px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}footer{max-width:1280px;margin:auto;padding:0 26px 35px;color:var(--muted);font-size:12px}@media(max-width:900px){.definitions,.three,.four{grid-template-columns:1fr 1fr}}@media(max-width:620px){.definitions,.three,.four,.two{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}.tabs button{white-space:nowrap}}@media print{.tabs{display:none}.view{display:block!important;break-before:page}.panel,.question,.callout{box-shadow:none}}
</style></head><body>
<header><span class="badge focus">FOCUS DEMANDÉ — PAS UN CLASSEMENT FOURNISSEUR</span><h1>Risques fournisseurs : du composant 338929 aux décisions prouvées</h1><p>Une démonstration en trois vues : l'incident imposé et ses lots simulés, la robustesse du réseau selon son niveau de service, puis les actions réellement testées.</p><div class="scope"><span class="pill">3 niveaux de fonctionnement</span><span class="pill">30 simulations par situation fournisseur</span><span class="pill">2 hypothèses testées séparément</span><span class="pill">108 courbes nominales · 36 sujets métier</span></div></header>
<div class="definitions"><div class="definition"><b>OBSERVÉ</b><span>Valeurs lues directement dans les fichiers industriels 2025.</span></div><div class="definition"><b>SIMULÉ</b><span>Résultat calculé pour un fonctionnement ou un incident imposé.</span></div><div class="definition"><b>SIGNAL DE PRIORITÉ</b><span>Dossier à examiner, pas une note fournisseur ni une probabilité.</span></div><div class="definition"><b>HYPOTHÈSE</b><span>Incident, action ou paramètre à confirmer avec les données réelles.</span></div></div>
<nav class="tabs" aria-label="Parcours de démonstration"><button class="active" data-tab="focus">1 · 338929 et ses lots</button><button data-tab="network">2 · Robustesse du réseau</button><button data-tab="decisions">3 · Décisions et limites</button></nav>
<main>
<section class="view active" id="focus"><div class="question"><h2>Que devient la chaîne si l'approvisionnement 338929 est perturbé ?</h2><p>Le fournisseur SDC-VD0914360C alimente l'article 338929 vers M-1810 pour le produit 268091. Ce focus a été demandé pour la démonstration : il n'a pas été ajouté au classement scientifique.</p></div><div class="grid two" id="focusHypotheses"></div><div class="callout"><b>Deux stress-tests unitaires, pas plusieurs risques en cascade.</b><p>Le retard de transport et la réduction de quantité sont calculés séparément. Ils ne sont ni des incidents observés ni une fréquence historique.</p></div><div class="panel"><h2>Effet agrégé sur 30 simulations</h2><p>Moyenne et intervalle central P10–P90. P10–P90 décrit la dispersion des résultats simulés, pas la probabilité d'occurrence de l'incident.</p><div class="table"><table><thead><tr><th>Niveau du réseau</th><th>Hypothèse</th><th>Écart moyen de service</th><th>P10–P90</th><th>Flux réellement touché</th><th>Lecture</th></tr></thead><tbody id="focusAggregate"></tbody></table></div></div><div class="panel"><h2>Une trajectoire physique détaillée par hypothèse</h2><div class="callout good"><b>Une trajectoire illustrative, pas la moyenne.</b><p>Le cas détaillé est choisi sur l'exposition physique sans regarder le résultat de service. Les lots du calcul normal et du calcul avec incident ont des identifiants distincts.</p></div><div class="controls"><select id="focusDetail"></select><select id="focusMetric"></select><button id="focusRaw">Voir les valeurs brutes</button></div><div id="focusIdentity"></div><canvas class="chart" id="focusChart" width="1160" height="330"></canvas><div class="legend"><span><i class="dot" style="background:#70839a"></i>sans incident</span><span><i class="dot" style="background:#d64232"></i>incident sans action</span><span>zone orangée = fenêtre d'incident</span></div><div class="grid four" id="focusKpis"></div><div id="focusChain"></div><div class="controls"><select id="traceStage"></select></div><div class="table"><table><thead><tr><th>Étape</th><th>Jour</th><th>Expédition</th><th>Lot matière</th><th>Campagne / batch</th><th>Lot fini ou client agrégé</th><th>Quantité</th></tr></thead><tbody id="traceRows"></tbody></table></div><div class="pager"><button id="tracePrev">←</button><span id="traceCount"></span><button id="traceNext">→</button></div><details><summary>Retards à volume cumulé égal</summary><div id="focusLags"></div><p class="small">Cette comparaison porte sur un volume cumulé, jamais sur le « même lot » entre deux simulations.</p></details></div></section>
<section class="view" id="network"><div class="question"><h2>Retrouve-t-on les mêmes fragilités quand le réseau fonctionne mieux ou moins bien ?</h2><p>Les trois configurations sont obtenues par des hypothèses de délais fournisseurs planifiés. Aucune capacité ni disponibilité de produit fini n'est inventée.</p></div><div class="grid three" id="stateCards"></div><div class="panel"><h2>Fournisseurs récurrents ou dépendants du niveau</h2><p>Tout le portefeuille signé est conservé. Aucun « top 3 » n'est forcé et le focus 338929 reste distinct.</p><div class="controls"><select id="portfolioMechanism"></select></div><div id="portfolioTable"></div></div><div class="panel"><h2>Sensibilité d'une même voie dans les trois configurations</h2><p>Les écarts appariés et leur IC95 indiquent si la conséquence simulée change avec l'état du réseau. Ce n'est pas une probabilité fournisseur.</p><div class="controls"><select id="laneSelect"></select><select id="laneMechanism"></select></div><div id="laneIdentity"></div><canvas class="chart" id="laneChart" width="1160" height="320"></canvas></div><div class="panel"><h2>Les dossiers scientifiques retenus sans modification</h2><div id="scientificSelection"></div></div><div class="panel"><h2>Fonctionnement sans incident : 108 courbes, 36 sujets métier</h2><p>Chaque sujet superpose les trois configurations. MM28 est utilisée pour le service et les flux ; MM7 pour les stocks, encours, retards et jours avec manque d'entrée.</p><div class="controls"><select id="nominalDomain"></select><select id="nominalEntity"></select><select id="nominalMetric"></select></div><div id="nominalMeaning"></div><canvas class="chart" id="nominalChart" width="1160" height="340"></canvas><div class="legend"><span><i class="dot" style="background:#1969df"></i>référence</span><span><i class="dot" style="background:#9461bd"></i>niveau proche de 93 %</span><span><i class="dot" style="background:#d64232"></i>niveau proche de 80 %</span><span>zone claire = P10–P90</span></div></div></section>
<section class="view" id="decisions"><div class="question"><h2>Quelles actions ont réellement été testées ?</h2><p>Seules les actions signées des dossiers scientifiques Stage3 sont affichées. Elles sont fixées avant le calcul : il ne s'agit pas d'une régulation automatique.</p></div><div id="focusActionNotice"></div><div id="actionArea"></div><div class="panel"><h2>Actions refusées ou non démontrées</h2><div id="refusals"></div></div><div class="callout"><b>Ce que cette démonstration ne promet pas.</b><p>Pas d'incident qualité, pas de capacité ou disponibilité fournisseur inventée, pas de combinaison de risques, pas de boucle fermée, pas d'étude fréquentielle des pôles ou de contrôlabilité, pas de coût complet, de ROI, de lot sauvé ou de jours récupérés sans preuve dédiée.</p><p>La propagation observée est un contact physique natif. Elle ne démontre pas à elle seule toute la causalité dynamique stock–MRP–production–service.</p></div><details class="panel"><summary>Contexte observé 2025</summary><div id="observed"></div><p class="small">Ces valeurs ne permettent pas d'attribuer une perte de chiffre d'affaires ou un stock à un fournisseur, une commande, un lot ou une cause. La devise n'est pas renseignée.</p></details></section>
</main><footer>Incidents exogènes · conséquences dépendantes de l'état évolutif du réseau · un incident à la fois · actions en boucle ouverte · clients agrégés · lots simulés. La prévision de probabilité fournisseur reste à calibrer avec les commandes promises et reçues réelles.</footer>
<script>
const D=__DATA__,S=D.stage3,F=D.requested_focus_338929,N=D.nominal_curves_full;
document.querySelector('#focus .callout').innerHTML='<b>Un incident fournisseur à la fois, puis sa cascade d’effets physiques.</b><p>Le suivi va de l’expédition au stock entrant et au lot, puis à la consommation et aux encours, au lot fini et au client agrégé. Les incidents simultanés ou corrélés ne sont pas testés.</p>';
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),num=(v,d=2)=>v==null?'—':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:d}).format(Number(v)),stateLabel=s=>({op_100:'Référence',op_93:'Niveau proche de 93 %',op_80:'Niveau proche de 80 %'}[s]||s),mechanism=id=>(S.campaign.mechanisms.find(x=>x.id===id)||{label:id,hypothesis:''}),status=s=>({robust_priority:'signal robuste dans cette configuration',dossier_to_investigate:'dossier à examiner',global_only_not_confirmed_within_target_product:'signal global non confirmé pour ce produit',supplementary_backlog_signal:'signal de retard séparé',insufficient_comparable_exposure:'comparaison entre configurations non conclue',robust_priority_all_states:'signal robuste dans les trois configurations',priority_all_states:'signal à examiner dans les trois configurations',state_specific_priority:'signal dépendant de la configuration',detected_lower_priority:'effet détecté, priorité plus basse',no_detected_effect:'effet non détecté'}[s]||s||'aucun signal qualifié');
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab));window.scrollTo(0,0)});
function canvas(c){const x=c.getContext('2d'),W=c.width,H=c.height;x.clearRect(0,0,W,H);return{x,W,H}}function axes(ctx,min,max){const{x,W,H}=ctx,span=Math.max(1e-9,max-min),y=v=>H-45-(Number(v)-min)*(H-75)/span;x.strokeStyle='#dbe5ef';x.fillStyle='#607389';x.font='12px Segoe UI';for(let i=0;i<5;i++){const yy=20+(H-65)*i/4;x.beginPath();x.moveTo(50,yy);x.lineTo(W-18,yy);x.stroke();x.fillText(num(max-(max-min)*i/4,1),4,yy+4)}return y}
function drawLines(id,groups,range){const c=$(id),ctx=canvas(c),all=groups.flatMap(g=>g.points.flatMap(p=>p.slice(1))).filter(Number.isFinite),min=range?.min??Math.min(0,...all),max=range?.max??Math.max(1,...all),y=axes(ctx,min,max),X=day=>50+(day-range.start)*(ctx.W-70)/Math.max(1,range.end-range.start);if(range.riskStart!=null){ctx.x.fillStyle='#ffe4dbaa';ctx.x.fillRect(X(range.riskStart),20,Math.max(2,X(range.riskEnd)-X(range.riskStart)),ctx.H-65)}groups.forEach(g=>{ctx.x.strokeStyle=g.color;ctx.x.lineWidth=g.width||2;ctx.x.beginPath();g.points.forEach((p,i)=>i?ctx.x.lineTo(X(p[0]),y(p[1])):ctx.x.moveTo(X(p[0]),y(p[1])));ctx.x.stroke()});ctx.x.fillStyle='#607389';ctx.x.fillText(`J${range.start}`,50,ctx.H-14);ctx.x.fillText(`J${range.end}`,ctx.W-56,ctx.H-14)}
function drawBandLines(id,rows){const c=$(id),ctx=canvas(c),all=rows.flatMap(s=>s.points.flatMap(p=>[p[1],p[2],p[4]])),min=Math.min(0,...all),max=Math.max(1,...all),y=axes(ctx,min,max),start=Math.min(...rows.map(s=>s.points[0][0])),end=Math.max(...rows.map(s=>s.points.at(-1)[0])),X=day=>50+(day-start)*(ctx.W-70)/Math.max(1,end-start),colors={op_100:'#1969df',op_93:'#9461bd',op_80:'#d64232'};rows.forEach(s=>{const col=colors[s.state];ctx.x.fillStyle=col+'20';ctx.x.beginPath();s.points.forEach((p,i)=>i?ctx.x.lineTo(X(p[0]),y(p[4])):ctx.x.moveTo(X(p[0]),y(p[4])));[...s.points].reverse().forEach(p=>ctx.x.lineTo(X(p[0]),y(p[2])));ctx.x.closePath();ctx.x.fill();ctx.x.strokeStyle=col;ctx.x.lineWidth=2;ctx.x.beginPath();s.points.forEach((p,i)=>i?ctx.x.lineTo(X(p[0]),y(p[1])):ctx.x.moveTo(X(p[0]),y(p[1])));ctx.x.stroke()});ctx.x.fillStyle='#607389';ctx.x.fillText(`J${start}`,50,ctx.H-14);ctx.x.fillText(`J${end}`,ctx.W-56,ctx.H-14)}
$('focusHypotheses').innerHTML=S.campaign.mechanisms.map(m=>`<article class="card"><span class="badge hyp">HYPOTHÈSE CONDITIONNELLE</span><h3>${esc(m.label)}</h3><p>${esc(m.hypothesis)}</p></article>`).join('');
$('focusAggregate').innerHTML=F.aggregate_results.sort((a,b)=>STATE(a.state)-STATE(b.state)||a.mechanism.localeCompare(b.mechanism)).map(r=>{const e=r.signed_baseline_minus_incident_service_pp;return`<tr><td>${esc(stateLabel(r.state))}</td><td>${esc(mechanism(r.mechanism).label)}</td><td>${num(e.mean)} point(s)</td><td>${num(e.p10)} à ${num(e.p90)} points</td><td>${r.physically_exercised_seed_count}/30</td><td>${esc(status(r.priority_status))}</td></tr>`}).join('');function STATE(s){return ['op_100','op_93','op_80'].indexOf(s)}
let focusRaw=false,tracePage=0;const TRACE_PAGE=25,traceLabels={shipment_to_mp_lots:'Expédition → lot entrant',exposed_consumption_wip:'Consommation et encours',exposed_finished_lots:'Lot fini descendant',exposed_client_events:'Contact client agrégé'};
$('focusDetail').innerHTML=F.details.map((d,i)=>`<option value="${i}">${esc(mechanism(d.mechanism).label)}</option>`).join('');function detail(){return F.details[Number($('focusDetail').value)||0]}function traceRows(d){return d.trace[$('traceStage').value]||[]}
function traceValue(r,...keys){for(const key of keys){if(r[key]!==undefined&&r[key]!==null&&r[key]!=='')return r[key]}return'—'}function traceUnit(r){return r.uom||((r.child_qty!==undefined&&r.child_qty!=='')?'UN':'')}function renderTrace(){const d=detail(),rows=traceRows(d),start=tracePage*TRACE_PAGE,shown=rows.slice(start,start+TRACE_PAGE);$('traceRows').innerHTML=shown.map(r=>`<tr><td>${esc(traceLabels[$('traceStage').value])}</td><td>${esc(traceValue(r,'day','risk_decision_day'))}</td><td>${esc(traceValue(r,'shipment_id','shipment_ids'))}</td><td>${esc(traceValue(r,'receipt_lot_id','material_lot_id','source_lot_id'))}</td><td>${esc(traceValue(r,'campaign_id'))} / ${esc(traceValue(r,'batch_id'))}</td><td>${esc(traceValue(r,'finished_lot_id','released_lot_id_same_day','client_node_id','client_lot_id'))}</td><td>${esc(traceValue(r,'child_qty','consumed_qty','released_qty','service_event_qty_on_contacted_lot'))} ${esc(traceUnit(r))}</td></tr>`).join('')||'<tr><td colspan="7">Aucune ligne native pour cette étape.</td></tr>';$('traceCount').textContent=`${rows.length?start+1:0}–${Math.min(start+TRACE_PAGE,rows.length)} sur ${rows.length}`;$('tracePrev').disabled=tracePage===0;$('traceNext').disabled=start+TRACE_PAGE>=rows.length}
function renderFocus(){const d=detail();$('focusMetric').innerHTML=d.curves.series.map((s,i)=>`<option value="${i}">${esc(s.label_fr)} · MM${s.rolling_window_days}</option>`).join('');$('traceStage').innerHTML=Object.keys(d.trace).map(k=>`<option value="${esc(k)}">${esc(traceLabels[k]||k)} · ${d.trace[k].length}</option>`).join('');$('focusIdentity').innerHTML=`<p><b>${esc(d.supplier_id)}</b> → article ${esc(d.item_id)} → ${esc(d.dst_node_id)} → produit ${esc(d.target_product_id)}. Incident de J${d.risk_window_start_day} à J${d.risk_window_end_day}; observation des effets de J${d.impact_window_start_day} à J${d.impact_window_end_day}.</p>`;const k=d.kpis;$('focusKpis').innerHTML=`<article class="card metric"><b>${num(k.service_loss_pp)} pt</b>écart de service</article><article class="card metric"><b>${num(k.on_due_units_lost,0)} UN</b>unités à l'heure en moins</article><article class="card metric"><b>${num(k.production_released_loss_qty,0)} UN</b>production libérée en moins</article><article class="card metric"><b>${k.backlog_recovery_day==null?'Non démontré':'J'+k.backlog_recovery_day}</b>retour du retard au niveau de référence dans la fenêtre</article>`;const steps=[['shipment_to_mp_lots','1 · Expédition'],['shipment_to_mp_lots','2 · Lot entrant'],['exposed_consumption_wip','3 · Consommation / encours'],['exposed_finished_lots','4 · Lot fini'],['exposed_client_events','5 · Client agrégé']];$('focusChain').innerHTML=`<div class="chain">${steps.map(([key,label],i)=>`${i?'<div class="arrow">→</div>':''}<div class="step ${d.trace[key].length?'ok':'no'}"><b>${label}</b><br>${d.trace[key].length?'trace native disponible':'étape non prouvée'}</div>`).join('')}</div><p class="small">Un contact généalogique n'est pas à lui seul une preuve de perte causale complète.</p>`;$('focusLags').innerHTML=`<div class="table"><table><thead><tr><th>Volume de référence</th><th>Jour sans incident</th><th>Jour avec incident</th><th>Décalage</th></tr></thead><tbody>${d.equal_cumulative_volume_lags.map(r=>`<tr><td>${Math.round(r.baseline_volume_fraction*100)} %</td><td>${r.baseline_reach_day??'—'}</td><td>${r.incident_reach_day??'non atteint'}</td><td>${r.status==='not_calculable_zero_reference_volume'?'non calculable':r.lag_days===''?'censuré':r.lag_days+' j'}</td></tr>`).join('')}</tbody></table></div>`;tracePage=0;drawFocus();renderTrace()}
function drawFocus(){const d=detail(),s=d.curves.series[Number($('focusMetric').value)||0],points=focusRaw?s.raw:s.smooth,clean=points.filter(p=>p[1]!=null&&p[2]!=null),vals=clean.flatMap(p=>[p[1],p[2]]),min=Math.min(0,...vals),max=Math.max(1,...vals);drawLines('focusChart',[{points:clean.map(p=>[p[0],p[1]]),color:'#70839a'},{points:clean.map(p=>[p[0],p[2]]),color:'#d64232'}],{start:0,end:d.curves.horizon_days-1,min,max,riskStart:d.risk_window_start_day,riskEnd:d.risk_window_end_day});$('focusRaw').textContent=focusRaw?'Revenir à la moyenne glissante':'Voir les valeurs brutes'}
$('focusDetail').onchange=renderFocus;$('focusMetric').onchange=drawFocus;$('focusRaw').onclick=()=>{focusRaw=!focusRaw;drawFocus()};$('traceStage').onchange=()=>{tracePage=0;renderTrace()};$('tracePrev').onclick=()=>{tracePage=Math.max(0,tracePage-1);renderTrace()};$('traceNext').onclick=()=>{tracePage++;renderTrace()};renderFocus();
function measure(state){return Object.fromEntries(state.measures.map(m=>[m.id,m]))}$('stateCards').innerHTML=S.validation.states.map(s=>{const m=measure(s);return`<article class="card"><span class="badge sim">SIMULÉ · 150 SIMULATIONS</span><h3>${esc(stateLabel(s.id||s.state||s.operating_point_id))}</h3><div class="big">${num(m.global.service_pct)} %</div><p>Service global<br>268091 : <b>${num(m['268091'].service_pct)} %</b><br>268967 : <b>${num(m['268967'].service_pct)} %</b></p><p class="small">Délais planifiés ajoutés : ${num(s.planned_lead_offset_days['268091'],1)} j vers 268091 · ${num(s.planned_lead_offset_days['268967'],1)} j vers 268967</p></article>`}).join('');
$('portfolioMechanism').innerHTML=S.campaign.mechanisms.map(m=>`<option value="${esc(m.id)}">${esc(m.label)}</option>`).join('');function renderPortfolio(){const mechanismId=$('portfolioMechanism').value,rows=S.supplier_stability.filter(r=>r.mechanism===mechanismId);$('portfolioTable').innerHTML=`<div class="table"><table><thead><tr><th>Fournisseur</th><th>Référence</th><th>Proche de 93 %</th><th>Proche de 80 %</th><th>Lecture globale</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.supplier_id)}<br><span class="small">${r.same_dominant_lane?'même voie dominante':'voie dominante variable'}</span></td>${['op_100','op_93','op_80'].map(s=>`<td>${esc(status(r.states[s].priority_status))}</td>`).join('')}<td>${esc(status(r.stability_status))}</td></tr>`).join('')}</tbody></table></div>`}$('portfolioMechanism').onchange=renderPortfolio;renderPortfolio();
const laneIds=[...new Set(S.lane_sensitivity.map(r=>r.lane_id))];$('laneSelect').innerHTML=laneIds.map(id=>`<option value="${esc(id)}" ${id===F.identity.lane_id?'selected':''}>${esc(id)}</option>`).join('');$('laneMechanism').innerHTML=S.campaign.mechanisms.map(m=>`<option value="${esc(m.id)}">${esc(m.label)}</option>`).join('');function drawStatePoints(points,withCi){const c=$('laneChart'),ctx=canvas(c),values=points.flatMap(p=>withCi?[p.mean,p.low,p.high]:[p.mean]).filter(Number.isFinite),min=Math.min(0,...values)-1,max=Math.max(1,...values)+1,y=axes(ctx,min,max),labels=['100 %','93 %','80 %'],X=i=>90+i*(ctx.W-180)/2;points.forEach((p,i)=>{const x=X(i);if(withCi&&Number.isFinite(p.low)&&Number.isFinite(p.high)){ctx.x.strokeStyle='#1969df';ctx.x.lineWidth=2;ctx.x.beginPath();ctx.x.moveTo(x,y(p.low));ctx.x.lineTo(x,y(p.high));ctx.x.moveTo(x-7,y(p.low));ctx.x.lineTo(x+7,y(p.low));ctx.x.moveTo(x-7,y(p.high));ctx.x.lineTo(x+7,y(p.high));ctx.x.stroke()}ctx.x.fillStyle=withCi?'#1969df':'#8b98a7';ctx.x.beginPath();ctx.x.arc(x,y(p.mean),5,0,Math.PI*2);ctx.x.fill();ctx.x.fillStyle='#607389';ctx.x.fillText(labels[i],x-14,ctx.H-14)})}function drawLane(){const row=S.lane_sensitivity.find(r=>r.lane_id===$('laneSelect').value&&r.mechanism===$('laneMechanism').value);if(!row)return;const points=['op_100','op_93','op_80'].map(state=>{const source=row.state_comparison_valid?row.paired_changes_vs_reference_pp[state]:row.states[state];return{mean:Number(row.state_comparison_valid?source.mean:source.effect_mean_pp),low:Number(source.ci95_low),high:Number(source.ci95_high)}});drawStatePoints(points,row.state_comparison_valid);$('laneIdentity').innerHTML=`<p><b>${esc(row.supplier_id)}</b> · ${esc(row.lane_id)} · produit ${esc(row.target_product_id)} · ${esc(mechanism(row.mechanism).label)}</p><div class="callout ${row.state_comparison_valid?'good':''}"><b>${row.state_comparison_valid?'Comparaison appariée admissible':'Lecture descriptive seulement'}</b><p>${esc(row.interpretation_fr)} ${row.comparable_seed_count} simulations comparables.</p></div>`}$('laneSelect').onchange=drawLane;$('laneMechanism').onchange=drawLane;drawLane();
const selected=D.stage3_preservation.selection;$('scientificSelection').innerHTML=selected.length?`<div class="table"><table><thead><tr><th>Dossier scientifique</th><th>Fournisseur</th><th>Article / site</th><th>Configuration</th><th>Hypothèse</th><th>Signal</th></tr></thead><tbody>${selected.map((r,i)=>`<tr><td>${i+1}</td><td>${esc(r.supplier_id)}</td><td>${esc(r.item_id)} → ${esc(r.dst_node_id)}</td><td>${esc(stateLabel(r.operating_point_id))}</td><td>${esc(mechanism(r.mechanism).label)}</td><td>${esc(status(r.priority_status))}</td></tr>`).join('')}</tbody></table></div>`:'<div class="callout">Aucun dossier n’a satisfait le protocole scientifique; aucun dossier n’est forcé.</div>';
function subjectId(s){return`${s.domain}|${s.entity}|${s.metric}|${s.rolling_window_days}`}function fillDomains(){const domains=[...new Set(N.subjects.map(s=>s.domain))];$('nominalDomain').innerHTML=domains.map(d=>`<option value="${esc(d)}">${esc(N.subjects.find(s=>s.domain===d).domain_label_fr)}</option>`).join('');$('nominalDomain').value=N.subjects[0].domain;fillEntities()}function fillEntities(){const domain=$('nominalDomain').value,rows=N.subjects.filter(s=>s.domain===domain),entities=[...new Set(rows.map(s=>s.entity))];$('nominalEntity').innerHTML=entities.map(e=>`<option value="${esc(e)}">${esc(rows.find(s=>s.entity===e).entity_label_fr)}</option>`).join('');fillMetrics()}function fillMetrics(){const rows=N.subjects.filter(s=>s.domain===$('nominalDomain').value&&s.entity===$('nominalEntity').value);$('nominalMetric').innerHTML=rows.map(s=>`<option value="${esc(subjectId(s))}">${esc(s.metric_label_fr)} · MM${s.rolling_window_days}</option>`).join('');drawNominal()}function drawNominal(){const id=$('nominalMetric').value,subject=N.subjects.find(s=>subjectId(s)===id);if(!subject)return;const rows=N.series.filter(s=>`${s.domain}|${s.entity}|${s.metric}|${s.rolling_window_days}`===id);$('nominalMeaning').innerHTML=subject.metric==='penurie_entree'?'<div class="callout"><b>Lecture exacte.</b><p>Part des jours simulés avec un manque d’entrée par rapport au plan. Ce n’est ni la disponibilité du fournisseur ni une probabilité.</p></div>':`<p>${esc(subject.entity_label_fr)} · ${esc(subject.metric_label_fr)} · ${esc(rows[0].unit)}</p>`;drawBandLines('nominalChart',rows)}$('nominalDomain').onchange=fillEntities;$('nominalEntity').onchange=fillMetrics;$('nominalMetric').onchange=drawNominal;fillDomains();
const actions=S.actions.actions||[];$('focusActionNotice').innerHTML=F.focus_has_existing_signed_stage3_action?'<div class="callout good"><b>Une action Stage3 porte exactement sur 338929.</b><p>Elle reste issue de la sélection scientifique et n’a pas été ajoutée par le focus.</p></div>':'<div class="callout"><b>Aucun levier simulé spécifiquement pour le focus 338929.</b><p>Les actions ci-dessous peuvent concerner d’autres dossiers signés; aucun gain ne leur est emprunté.</p></div>';
function renderActions(){if(!actions.length){$('actionArea').innerHTML='<div class="callout">Aucune action représentable pour les dossiers scientifiques signés.</div>';return}$('actionArea').innerHTML=`<div class="controls"><select id="actionSelect">${actions.map((a,i)=>`<option value="${i}">${esc(a.label_fr)} · ${esc(a.supplier_id)} · article ${esc(a.item_id)}</option>`).join('')}</select></div><div id="actionDetail"></div>`;function draw(){const a=actions[Number($('actionSelect').value)],metrics=a.metrics||[],params=(a.parameter_lines_fr||[]).map(esc).join('<br>')||'aucun paramètre publié',scope=(a.scope_lines_fr||[]).map(esc).join('<br>')||'périmètre non détaillé';$('actionDetail').innerHTML=`<article class="panel"><span class="badge sim">SIMULÉ · BOUCLE OUVERTE</span><h2>${esc(a.label_fr)}</h2><p>Dossier ${esc(a.dossier_id)} · ${esc(a.supplier_id)} · article ${esc(a.item_id)} · ${esc(stateLabel(a.state))}. Action réellement exercée dans ${a.physically_exercised_seed_count} simulations sur ${a.paired_seed_count}.</p><p><b>Paramètres :</b><br>${params}<br><b>Périmètre :</b><br>${scope}</p><div class="table"><table><thead><tr><th>Indicateur</th><th>Sans incident</th><th>Incident sans action</th><th>Incident avec action</th><th>Effet signé de l'action</th></tr></thead><tbody>${metrics.map(m=>m.available?`<tr><td>${esc(m.label)} (${esc(m.unit)})</td><td>${num(m.baseline.mean)}<br><span class="small">P10–P90 ${num(m.baseline.p10)} à ${num(m.baseline.p90)}</span></td><td>${num(m.incident_without_action.mean)}<br><span class="small">P10–P90 ${num(m.incident_without_action.p10)} à ${num(m.incident_without_action.p90)}</span></td><td>${num(m.incident_with_action.mean)}<br><span class="small">P10–P90 ${num(m.incident_with_action.p10)} à ${num(m.incident_with_action.p90)}</span></td><td>${num(m.signed_action_effect.mean)}<br><span class="small">positif = amélioration</span></td></tr>`:`<tr><td>${esc(m.label)}</td><td colspan="4">${esc(m.reason_fr||'Indicateur indisponible')}</td></tr>`).join('')}</tbody></table></div><details><summary>Limite opérationnelle</summary><p>${esc(a.limits_fr)}</p></details></article>`}$('actionSelect').onchange=draw;draw()}renderActions();
const refusals=S.actions.refusals||[];$('refusals').innerHTML=refusals.length?`<ul>${refusals.map(r=>`<li><b>${esc(r.label_fr)}</b> — dossier ${esc(r.dossier_id)} : ${esc(r.reason)}</li>`).join('')}</ul>`:'<p>Aucun refus supplémentaire publié.</p>';
function renderObserved(){const o=S.observed_2025;if(!o){$('observed').innerHTML='<p>Contexte observé 2025 non fourni.</p>';return}const products=(o.products||[]).map(p=>`<li><b>Produit ${esc(p.product_id)}</b> : valeur brute de CA perdu déclarée ${num(p.lost_revenue_raw_source_value)}; part du potentiel financier brut ${num(p.lost_share_of_raw_potential_pct)} %.</li>`).join(''),stocks=(o.stocks||[]).map(s=>`<li><b>${esc(s.series_id)}</b> : valeur comptable moyenne ${num(s.mean_accounting_value_source)}, dernière valeur ${num(s.last_accounting_value_source)}.</li>`).join('');$('observed').innerHTML=`<span class="badge obs">OBSERVÉ 2025</span><h3>Valeurs disponibles dans les fichiers</h3><ul>${products}${stocks}</ul>`}renderObserved();
</script></body></html>"""


def _assert_no_local_paths_in_payload(payload: Mapping[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if _WINDOWS_PATH_RE.search(raw):
        raise DeliveryV4Error("Un chemin local serait embarqué dans le HTML")


def render_html(payload: Mapping[str, Any]) -> str:
    _assert_no_local_paths_in_payload(payload)
    document = HTML_TEMPLATE.replace("__DATA__", _safe_json(payload))
    validate_document(document)
    return document


def validate_document(document: str) -> None:
    if document.count('class="view') != len(VIEW_IDS):
        raise DeliveryV4Error("Le HTML doit contenir exactement trois vues")
    section_ids = re.findall(
        r'<section\s+class="view(?: active)?"\s+id="([^"]+)"', document
    )
    tab_ids = re.findall(
        r'<button(?:\s+class="active")?\s+data-tab="([^"]+)"', document
    )
    if tuple(section_ids) != VIEW_IDS or tuple(tab_ids) != VIEW_IDS:
        raise DeliveryV4Error("Les trois onglets ne correspondent pas aux trois vues")
    if (
        '<html lang="fr">' not in document
        or '<meta charset="utf-8">' not in document
        or "connect-src 'none'" not in document
        or "default-src 'none'" not in document
        or _EXTERNAL_URL_RE.search(document)
        or _NETWORK_API_RE.search(document)
        or _NETWORK_NAVIGATION_RE.search(document)
        or _WINDOWS_PATH_RE.search(document)
        or "__DATA__" in document
        or re.search(r"(?<![A-Za-z])(NaN|Infinity)(?![A-Za-z])", document)
    ):
        raise DeliveryV4Error("Le HTML n'est pas autonome, sûr et hors ligne")
    required = (
        "FOCUS DEMANDÉ — PAS UN CLASSEMENT FOURNISSEUR",
        "Une trajectoire illustrative, pas la moyenne",
        "P10–P90 décrit la dispersion",
        "Un incident fournisseur à la fois, puis sa cascade d’effets physiques",
        "Les incidents simultanés ou corrélés ne sont pas testés",
        "Aucune capacité ni disponibilité de produit fini n'est inventée",
        "108 courbes, 36 sujets métier",
        "pas une probabilité fournisseur",
        "boucle ouverte",
        "pas d'étude fréquentielle des pôles ou de contrôlabilité",
        "causalité dynamique stock–MRP–production–service",
        "clients agrégés",
        "lots simulés",
        "prévision de probabilité fournisseur reste à calibrer",
    )
    if any(text.casefold() not in document.casefold() for text in required):
        raise DeliveryV4Error("Une limite métier obligatoire n'est pas visible")


def _manifest_payload(
    *,
    output_root: Path,
    payload: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    document: str,
) -> dict[str, Any]:
    raw = document.encode("utf-8")
    preserved = payload["stage3_preservation"]
    unsigned = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "output_html": OUTPUT_NAME,
        "html_sha256": hashlib.sha256(raw).hexdigest(),
        "html_bytes": len(raw),
        "payload_signature": payload["payload_signature"],
        "view_count": len(VIEW_IDS),
        "view_ids": list(VIEW_IDS),
        "standalone": True,
        "external_dependency_count": 0,
        "engine_runs_performed": 0,
        "nominal_series_count": EXPECTED_NOMINAL_SERIES,
        "nominal_subject_count": EXPECTED_NOMINAL_SUBJECTS,
        "stage3_preservation": copy.deepcopy(preserved),
        "source_bindings": [dict(row) for row in sources],
        "scientific_contract": {
            "stage3_payload_modified": False,
            "stage3_selection_modified": False,
            "focus_inserted_into_scientific_selection": False,
            "focus_selection_basis": focus_v1.SELECTION_BASIS,
            "focus_is_priority_claim": False,
            "focus_operating_point": "op_93",
            "focus_mechanisms_kept_separate": True,
            "focus_detail_is_single_trajectory": True,
            "aggregate_focus_repetitions": 30,
            "quality_incident_included": False,
            "capacity_or_availability_invented": False,
            "historical_probability_available": False,
            "actions_open_loop": True,
            "automatic_regulation": False,
            "multiple_incidents_combined": False,
            "full_dynamic_cascade_claimed": False,
            "action_lot_trace_available": False,
            "cross_arm_same_lot_claimed": False,
            "days_recovered_cost_or_roi_claimed": False,
            "customers_aggregated": True,
            "lots_simulated": True,
            "frequency_domain_analysis_included": False,
            "observed_2025_supplier_causality_claimed": False,
        },
    }
    return common.signed(unsigned, "manifest_signature")


def _protected_roots(
    paths: common.Stage2Paths, closure_report: Path, focus_root: Path
) -> tuple[Path, ...]:
    return tuple(
        path.resolve()
        for path in (
            paths.repo,
            paths.v7_plan_dir,
            paths.v7_run_dir,
            paths.trace_package_dir,
            paths.bridge_json,
            paths.campaign_root,
            paths.results_dir,
            paths.stage1_supervision_dir,
            paths.observed_2025_dir,
            paths.lot_replay_root,
            paths.qualification_dir,
            paths.action_replay_root,
            paths.curves_dir,
            paths.registry_dir,
            paths.final_html,
            paths.supervision_dir,
            closure_report.resolve().parent,
            focus_root.resolve(),
        )
        if path is not None
    )


def _validate_output_separation(
    output_root: Path,
    *,
    stage3_supervision_dir: Path,
    closure_report: Path,
    focus_root: Path,
) -> None:
    context = closure_v1.load_final_context(stage3_supervision_dir.resolve())
    output = output_root.resolve()
    if any(
        common.paths_overlap(output, protected)
        for protected in _protected_roots(context.paths, closure_report, focus_root)
    ):
        raise DeliveryV4Error("La racine V4 chevauche une preuve ou une sortie Stage3")


def _write_staged(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _publish_root_new_or_identical(
    output_root: Path, document: str, manifest: Mapping[str, Any]
) -> bool:
    output = output_root.resolve()
    html_raw = document.encode("utf-8")
    manifest_raw = (
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    if output.exists():
        expected_names = {OUTPUT_NAME, MANIFEST_NAME}
        if (
            not output.is_dir()
            or {path.name for path in output.iterdir()} != expected_names
            or (output / OUTPUT_NAME).read_bytes() != html_raw
            or (output / MANIFEST_NAME).read_bytes() != manifest_raw
        ):
            raise DeliveryV4Error("Sortie V4 existante différente ; écrasement refusé")
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".{output.name}.staging.{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        _write_staged(staging / OUTPUT_NAME, html_raw)
        _write_staged(staging / MANIFEST_NAME, manifest_raw)
        try:
            os.replace(staging, output)
            return True
        except FileExistsError:
            if (
                not output.is_dir()
                or (output / OUTPUT_NAME).read_bytes() != html_raw
                or (output / MANIFEST_NAME).read_bytes() != manifest_raw
            ):
                raise DeliveryV4Error(
                    "Publication concurrente différente ; écrasement refusé"
                )
            return False
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)


def _quarantine_just_published(
    output_root: Path, document: str, manifest: Mapping[str, Any]
) -> Path:
    output = output_root.resolve()
    html_raw = document.encode("utf-8")
    manifest_raw = (
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    expected_names = {OUTPUT_NAME, MANIFEST_NAME}
    if (
        not output.is_dir()
        or {path.name for path in output.iterdir()} != expected_names
        or (output / OUTPUT_NAME).read_bytes() != html_raw
        or (output / MANIFEST_NAME).read_bytes() != manifest_raw
    ):
        raise DeliveryV4Error(
            "Publication V4 devenue ambiguë ; quarantaine automatique refusée"
        )
    quarantine = output.parent / f".{output.name}.rejected.{uuid.uuid4().hex}"
    os.replace(output, quarantine)
    return quarantine


def validate_delivery(
    stage3_supervision_dir: Path,
    closure_report: Path,
    focus_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    output = output_root.resolve()
    _validate_output_separation(
        output,
        stage3_supervision_dir=stage3_supervision_dir,
        closure_report=closure_report,
        focus_root=focus_root,
    )
    if not output.is_dir() or {path.name for path in output.iterdir()} != {
        OUTPUT_NAME,
        MANIFEST_NAME,
    }:
        raise DeliveryV4Error("Paquet V4 absent, incomplet ou non exclusif")
    evidence = collect_evidence(stage3_supervision_dir, closure_report, focus_root)
    document = render_html(evidence.payload)
    expected_manifest = _manifest_payload(
        output_root=output,
        payload=evidence.payload,
        sources=evidence.sources,
        document=document,
    )
    actual_document = (output / OUTPUT_NAME).read_text(encoding="utf-8")
    actual_manifest = common.read_json(output / MANIFEST_NAME)
    try:
        common.verify_signature(
            actual_manifest, "manifest_signature", "manifeste HTML final V4"
        )
    except Exception as exc:
        raise DeliveryV4Error("Signature du manifeste V4 invalide") from exc
    if actual_document != document or actual_manifest != expected_manifest:
        raise DeliveryV4Error("Le paquet V4 ne reproduit plus ses preuves")
    validate_document(actual_document)
    _assert_snapshots_unchanged(evidence.snapshots)
    return {
        "valid": True,
        "html": str(output / OUTPUT_NAME),
        "html_sha256": actual_manifest["html_sha256"],
        "html_bytes": actual_manifest["html_bytes"],
        "manifest": str(output / MANIFEST_NAME),
        "manifest_signature": actual_manifest["manifest_signature"],
        "view_count": len(VIEW_IDS),
        "nominal_series_count": EXPECTED_NOMINAL_SERIES,
        "nominal_subject_count": EXPECTED_NOMINAL_SUBJECTS,
        "focus_detail_count": len(
            evidence.payload["requested_focus_338929"]["details"]
        ),
        "stage3_selection_count": len(
            evidence.payload["stage3_preservation"]["selection"]
        ),
        "engine_runs_performed": 0,
    }


def build_delivery(
    stage3_supervision_dir: Path,
    closure_report: Path,
    focus_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    output = output_root.resolve()
    _validate_output_separation(
        output,
        stage3_supervision_dir=stage3_supervision_dir,
        closure_report=closure_report,
        focus_root=focus_root,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / f".{output.name}.delivery_v4.lock"
    with common.exclusive_lock(lock):
        if output.exists():
            return validate_delivery(
                stage3_supervision_dir, closure_report, focus_root, output
            )
        evidence = collect_evidence(stage3_supervision_dir, closure_report, focus_root)
        document = render_html(evidence.payload)
        manifest = _manifest_payload(
            output_root=output,
            payload=evidence.payload,
            sources=evidence.sources,
            document=document,
        )
        _assert_snapshots_unchanged(evidence.snapshots)
        created_here = _publish_root_new_or_identical(output, document, manifest)
        try:
            _assert_snapshots_unchanged(evidence.snapshots)
        except Exception:
            if created_here:
                _quarantine_just_published(output, document, manifest)
            raise
    return validate_delivery(stage3_supervision_dir, closure_report, focus_root, output)


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stage3-supervision-dir", type=Path, required=True)
    parser.add_argument("--closure-report", type=Path, required=True)
    parser.add_argument("--focus-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "validate"):
        _add_arguments(subparsers.add_parser(command))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    operation = build_delivery if args.command == "build" else validate_delivery
    try:
        result = operation(
            args.stage3_supervision_dir,
            args.closure_report,
            args.focus_root,
            args.output_root,
        )
    except Exception as exc:
        print(f"LIVRAISON V4 REFUSÉE : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
