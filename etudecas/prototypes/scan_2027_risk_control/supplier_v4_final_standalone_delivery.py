#!/usr/bin/env python3
"""Compose the final lightweight, offline V4 supplier-risk delivery.

The composer is presentation-only.  It starts no simulation engine and writes
only a new standalone HTML plus its adjacent integrity manifest.  Every input
is first validated by its owning V4 module; the compact renderer then exposes
three client-facing views: nominal dynamics, supplier-risk priorities, and
signed lot replays (when the non-forced selection contains dossiers).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import importlib
import io
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_aggregator_v4 as curve_aggregator,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4_dashboard as campaign_dashboard,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lot_replay,
)


SCHEMA_VERSION = "etudecas.supplier_v4_final_standalone_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
EXPECTED_STATES = ("op_100", "op_93", "op_80")
EXPECTED_MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
EXPECTED_HORIZON_DAYS = 720
EXPECTED_REPETITIONS = 30
EXPECTED_LANES = 18
EXPECTED_BASELINE_ROWS = 90
EXPECTED_INCIDENT_ROWS = 3240
EXPECTED_CAMPAIGN_ROWS = EXPECTED_BASELINE_ROWS + EXPECTED_INCIDENT_ROWS
MAX_LOT_DOSSIERS = 3
MAX_CHAIN_PREVIEW_ROWS = 120
ALLOWED_ACTION_IDS = {
    "prepositioned_free_stock_j0",
    "future_departures_lead_reduction",
    "active_multisource_reallocation",
}
ACTION_IMPACT_METRIC_IDS = ("service_gain_pp",)
ACTION_STATE_METRIC_IDS = (
    "state_window_service_gain_pp",
    "backlog_qty_days_avoided",
    "production_released_gain_qty",
)
DISPLAY_ACTION_METRICS = {
    "service_gain_pp": (
        "Service récupéré sur la fenêtre d'impact de 360 jours",
        "point",
    ),
    "state_window_service_gain_pp": (
        "Service récupéré sur la fenêtre d'état J0–J719",
        "point",
    ),
    "backlog_qty_days_avoided": (
        "Retard cumulé évité sur la fenêtre d'état J0–J719",
        "unité-jour",
    ),
    "production_released_gain_qty": (
        "Production libérée récupérée sur la fenêtre d'état J0–J719",
        "unité",
    ),
}

CURVE_SELECTION: tuple[tuple[str, str, int, str, str], ...] = (
    (
        "service",
        "on_due_service_ratio",
        28,
        "Service à l'heure — 28 jours",
        "Part de la demande du jour servie à l'heure, calculée sur 28 jours.",
    ),
    (
        "service",
        "backlog_end_qty",
        0,
        "Retard client — brut",
        "Volume restant en retard à la fin de chaque jour.",
    ),
    (
        "service",
        "backlog_end_qty",
        7,
        "Retard client — 7 jours",
        "Moyenne glissante sur 7 jours du volume restant en retard.",
    ),
    (
        "production",
        "released_qty",
        28,
        "Production libérée — 28 jours",
        "Moyenne glissante sur 28 jours des unités rendues disponibles.",
    ),
    (
        "production",
        "wip_end_qty",
        0,
        "Encours — brut",
        "Encours de production à la fin de chaque jour.",
    ),
    (
        "production",
        "wip_end_qty",
        7,
        "Encours — 7 jours",
        "Moyenne glissante sur 7 jours de l'encours.",
    ),
    (
        "production",
        "finished_stock_end_qty",
        0,
        "Stock de sortie — brut",
        "Stock de produit de sortie à la fin de chaque jour.",
    ),
    (
        "production",
        "finished_stock_end_qty",
        7,
        "Stock de sortie — 7 jours",
        "Moyenne glissante sur 7 jours du stock de sortie.",
    ),
    (
        "input_stock",
        "input_stock_end_qty",
        0,
        "Stock entrant — brut",
        "Stock de composant à la fin de chaque jour.",
    ),
    (
        "input_stock",
        "input_stock_end_qty",
        7,
        "Stock entrant — 7 jours",
        "Moyenne glissante sur 7 jours du stock entrant.",
    ),
)
CURVE_SPEC_BY_KEY = {
    (domain, metric, window): {
        "label": label,
        "explanation": explanation,
    }
    for domain, metric, window, label, explanation in CURVE_SELECTION
}
CURVE_ORDER = {
    (domain, metric, window): index
    for index, (domain, metric, window, _label, _explanation) in enumerate(
        CURVE_SELECTION
    )
}
DISPLAY_PRODUCT_NODES = {"268091": "M-1810", "268967": "M-1430"}


def _is_business_curve_entity(
    *, domain: str, metric: str, node: str, item: str
) -> bool:
    """Keep exact daily values only for the compact client demonstration."""

    if domain == "service":
        return node == "C-XXXXX" and item in DISPLAY_PRODUCT_NODES
    if domain == "production":
        return DISPLAY_PRODUCT_NODES.get(item) == node and metric in {
            "released_qty",
            "wip_end_qty",
            "finished_stock_end_qty",
        }
    if domain == "input_stock":
        return item == "338929"
    return False


class FinalDeliveryError(RuntimeError):
    """Raised when a source cannot support the final presentation."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise FinalDeliveryError(f"Fichier illisible : {path}") from exc
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinalDeliveryError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise FinalDeliveryError(f"Objet JSON attendu : {path}")
    return payload


def verify_signature(
    payload: Mapping[str, Any], signature_field: str, *, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise FinalDeliveryError(f"Signature incohérente : {label}")
    return signature


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise FinalDeliveryError(f"CSV illisible : {path}") from exc


def read_gzip_csv(path: Path) -> list[dict[str, str]]:
    try:
        raw = gzip.decompress(path.read_bytes()).decode("utf-8-sig")
        return [dict(row) for row in csv.DictReader(io.StringIO(raw, newline=""))]
    except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
        raise FinalDeliveryError(f"CSV gzip illisible : {path}") from exc


def finite_number(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FinalDeliveryError(f"Valeur numérique absente : {label}") from exc
    if not math.isfinite(number):
        raise FinalDeliveryError(f"Valeur non finie : {label}")
    return number


def integer(value: Any, *, label: str) -> int:
    number = finite_number(value, label=label)
    if not number.is_integer():
        raise FinalDeliveryError(f"Entier attendu : {label}")
    return int(number)


def compact_number(value: float) -> float | int:
    rounded = round(float(value), 6)
    return int(rounded) if rounded.is_integer() else rounded


def safe_json(payload: Any) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _curve_file_from_manifest(
    *, curves_dir: Path, manifest: Mapping[str, Any], domain: str
) -> Path:
    aggregate_root = (curves_dir / curve_aggregator.AGGREGATE_SUBDIRECTORY).resolve()
    matches = [
        row
        for row in manifest.get("files") or []
        if isinstance(row, Mapping) and str(row.get("domain") or "") == domain
    ]
    if len(matches) != 1:
        raise FinalDeliveryError(f"Sortie de courbes {domain} absente ou dupliquée")
    row = matches[0]
    path = Path(str(row.get("path") or "")).resolve()
    expected_name = f"{domain}_quantiles_daily.csv.gz"
    if (
        path.parent != aggregate_root
        or path.name != expected_name
        or not path.is_file()
    ):
        raise FinalDeliveryError(f"Chemin de courbes inattendu : {domain}")
    if sha256_file(path) != str(row.get("sha256") or ""):
        raise FinalDeliveryError(f"Empreinte de courbes incohérente : {domain}")
    return path


def _validated_curve_series(
    rows: Sequence[Mapping[str, str]],
    *,
    domain: str,
) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[str, str, str, str, int, str, str], dict[int, tuple[Any, ...]]
    ] = defaultdict(dict)
    for row in rows:
        metric = str(row.get("metric") or "")
        window = integer(row.get("rolling_window_days"), label="fenêtre de courbe")
        if (domain, metric, window) not in CURVE_SPEC_BY_KEY:
            continue
        state = str(row.get("target_group") or "")
        if state not in EXPECTED_STATES:
            raise FinalDeliveryError(f"État de courbe inattendu : {state}")
        day = integer(row.get("day"), label="jour de courbe")
        if not 0 <= day < EXPECTED_HORIZON_DAYS:
            raise FinalDeliveryError(f"Jour de courbe hors horizon : {day}")
        node = str(row.get("node_id") or "").strip()
        item = str(row.get("item_id") or "").strip().removeprefix("item:")
        candidate = str(row.get("candidate_id") or "").strip()
        unit = str(row.get("unit") or "").strip()
        if not node or not item or not candidate or not unit:
            raise FinalDeliveryError("Identité de série nominale incomplète")
        if not _is_business_curve_entity(
            domain=domain, metric=metric, node=node, item=item
        ):
            continue
        key = (state, candidate, node, item, window, domain, metric)
        if day in grouped[key]:
            raise FinalDeliveryError(f"Jour nominal dupliqué : {key}/J{day}")
        sample_count = integer(row.get("sample_count"), label="nombre de simulations")
        start_day = max(0, window - 1)
        expected_count = EXPECTED_REPETITIONS if day >= start_day else 0
        if sample_count != expected_count:
            raise FinalDeliveryError(
                f"Série nominale incomplète : {key}/J{day} ({sample_count})"
            )
        values: tuple[float, float, float] | None
        if expected_count == 0:
            if any(
                str(row.get(field) or "").strip() for field in ("p10", "median", "p90")
            ):
                raise FinalDeliveryError("Valeurs présentes avant une fenêtre complète")
            values = None
        else:
            p10 = finite_number(row.get("p10"), label="P10 nominal")
            median = finite_number(row.get("median"), label="médiane nominale")
            p90 = finite_number(row.get("p90"), label="P90 nominal")
            if p10 > median + 1e-12 or median > p90 + 1e-12:
                raise FinalDeliveryError("Ordre P10/médiane/P90 incohérent")
            if metric == "on_due_service_ratio" and not (
                -1e-12 <= p10 <= p90 <= 1.0 + 1e-12
            ):
                raise FinalDeliveryError("Service nominal hors intervalle 0–1")
            if metric != "on_due_service_ratio" and p10 < -1e-9:
                raise FinalDeliveryError("Quantité nominale négative")
            values = (p10, median, p90)
        grouped[key][day] = (values, unit)

    series: list[dict[str, Any]] = []
    for key, by_day in sorted(grouped.items()):
        state, candidate, node, item, window, selected_domain, metric = key
        if set(by_day) != set(range(EXPECTED_HORIZON_DAYS)):
            raise FinalDeliveryError(f"Horizon J0–J719 incomplet : {key}")
        start_day = max(0, window - 1)
        selected = [by_day[day] for day in range(start_day, EXPECTED_HORIZON_DAYS)]
        units = {str(value[1]) for value in selected}
        if len(units) != 1 or any(value[0] is None for value in selected):
            raise FinalDeliveryError(f"Série nominale non dense : {key}")
        triples = [value[0] for value in selected]
        assert all(value is not None for value in triples)
        spec = CURVE_SPEC_BY_KEY[(selected_domain, metric, window)]
        series.append(
            {
                "state": state,
                "candidate": candidate,
                "domain": selected_domain,
                "metric": metric,
                "windowDays": window,
                "label": spec["label"],
                "explanation": spec["explanation"],
                "node": node,
                "item": item,
                "unit": next(iter(units)),
                "startDay": start_day,
                "p10": [compact_number(value[0]) for value in triples if value],
                "median": [compact_number(value[1]) for value in triples if value],
                "p90": [compact_number(value[2]) for value in triples if value],
            }
        )
    return series


def load_curve_payload(curves_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    curves = curves_dir.resolve()
    try:
        validation = curve_aggregator.validate_aggregates(curves)
    except Exception as exc:  # owning module defines the authoritative contract
        raise FinalDeliveryError(f"Courbes nominales V4 refusées : {exc}") from exc
    if (
        validation.get("valid") is not True
        or int(validation.get("case_count") or -1) != 90
        or int(validation.get("state_count") or -1) != 3
        or int(validation.get("file_count") or -1) != 4
    ):
        raise FinalDeliveryError("La capture nominale 3 × 30 n'est pas complète")
    aggregate_root = curves / curve_aggregator.AGGREGATE_SUBDIRECTORY
    manifest_path = aggregate_root / "aggregate_manifest.json"
    manifest = read_json(manifest_path)
    manifest_signature = verify_signature(
        manifest, "manifest_signature", label="manifeste de courbes nominales"
    )
    if (
        manifest.get("status") != "complete"
        or int(manifest.get("case_count") or -1) != 90
        or int(manifest.get("state_count") or -1) != 3
        or int(manifest.get("horizon_days") or -1) != EXPECTED_HORIZON_DAYS
        or validation.get("manifest_signature") != manifest_signature
    ):
        raise FinalDeliveryError("Contrat des courbes nominales incomplet")

    selected_series: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []
    for domain in ("service", "production", "input_stock"):
        path = _curve_file_from_manifest(
            curves_dir=curves, manifest=manifest, domain=domain
        )
        declared = next(
            row
            for row in manifest["files"]
            if isinstance(row, Mapping) and row.get("domain") == domain
        )
        source_files.append(
            {
                "domain": domain,
                "path": str(path),
                "sha256": declared["sha256"],
                "row_count": int(declared["row_count"]),
            }
        )
        selected_series.extend(
            _validated_curve_series(read_gzip_csv(path), domain=domain)
        )
    constraint_path = _curve_file_from_manifest(
        curves_dir=curves, manifest=manifest, domain="constraint"
    )
    constraint_declared = next(
        row
        for row in manifest["files"]
        if isinstance(row, Mapping) and row.get("domain") == "constraint"
    )
    source_files.append(
        {
            "domain": "constraint",
            "path": str(constraint_path),
            "sha256": constraint_declared["sha256"],
            "row_count": int(constraint_declared["row_count"]),
        }
    )
    found = {
        (row["domain"], row["metric"], row["windowDays"]) for row in selected_series
    }
    mandatory = {
        key for key in CURVE_SPEC_BY_KEY if key[0] in {"service", "production"}
    }
    missing = sorted(mandatory - found)
    if missing:
        raise FinalDeliveryError(f"Familles de courbes absentes : {missing}")
    input_keys = {key for key in CURVE_SPEC_BY_KEY if key[0] == "input_stock"}
    if found & input_keys and not input_keys.issubset(found):
        raise FinalDeliveryError(
            "Courbes brutes/lissées du composant 338929 incomplètes"
        )
    states = {row["state"] for row in selected_series}
    if states != set(EXPECTED_STATES):
        raise FinalDeliveryError("Les courbes ne couvrent pas les trois états")
    candidates_by_state: dict[str, set[str]] = defaultdict(set)
    for row in selected_series:
        candidates_by_state[row["state"]].add(row["candidate"])
    if any(len(values) != 1 for values in candidates_by_state.values()):
        raise FinalDeliveryError("Plusieurs candidats nominaux sont mélangés")
    states_by_identity: dict[tuple[str, str, int, str, str], set[str]] = defaultdict(
        set
    )
    for row in selected_series:
        states_by_identity[
            (
                row["domain"],
                row["metric"],
                row["windowDays"],
                row["node"],
                row["item"],
            )
        ].add(row["state"])
    if any(value != set(EXPECTED_STATES) for value in states_by_identity.values()):
        raise FinalDeliveryError("Une série métier ne couvre pas les trois états")
    selected_series.sort(
        key=lambda row: (
            EXPECTED_STATES.index(row["state"]),
            CURVE_ORDER[(row["domain"], row["metric"], row["windowDays"])],
            row["node"],
            row["item"],
        )
    )
    payload = {
        "status": "complete_validated",
        "horizonDays": EXPECTED_HORIZON_DAYS,
        "repetitionsPerState": EXPECTED_REPETITIONS,
        "quantiles": [10, 50, 90],
        "series": selected_series,
    }
    binding = {
        "root": str(curves),
        "aggregate_manifest": str(manifest_path.resolve()),
        "aggregate_manifest_sha256": sha256_file(manifest_path),
        "aggregate_manifest_signature": manifest_signature,
        "aggregate_contract_signature": manifest.get("aggregate_contract_signature"),
        "case_count": 90,
        "state_count": 3,
        "horizon_days": EXPECTED_HORIZON_DAYS,
        "series_count": len(selected_series),
        "files": source_files,
    }
    return payload, binding


def load_campaign_payload(
    *,
    campaign_root: Path,
    results_dir: Path,
    target_registry_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = campaign_root.resolve()
    results = results_dir.resolve()
    if not root.is_dir() or not results.is_dir():
        raise FinalDeliveryError("Dossier de campagne ou de résultats absent")
    try:
        payload = campaign_dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=(
                target_registry_path.resolve() if target_registry_path else None
            ),
        )
    except Exception as exc:
        raise FinalDeliveryError(f"Résultats de campagne V4 refusés : {exc}") from exc
    validation_path = results / "campaign_validation.json"
    validation = read_json(validation_path)
    contract = validation.get("expected_contract")
    checks = validation.get("comparability_checks")
    if not isinstance(contract, Mapping) or not isinstance(checks, Mapping):
        raise FinalDeliveryError("Contrat final de campagne absent")
    expected_values = {
        "operating_point_count": 3,
        "lane_count": EXPECTED_LANES,
        "paired_repetition_count": EXPECTED_REPETITIONS,
        "baseline_row_count": EXPECTED_BASELINE_ROWS,
        "incident_row_count": EXPECTED_INCIDENT_ROWS,
    }
    failures = [
        field
        for field, expected in expected_values.items()
        if int(contract.get(field) or -1) != expected
    ]
    if (
        failures
        or checks.get("all_3330_metrics_reconstructed_from_signed_case_evidence")
        is not True
    ):
        raise FinalDeliveryError(
            "La preuve exhaustive des 3 330 résultats n'est pas complète"
        )
    if int(payload.get("repetitions") or -1) != EXPECTED_REPETITIONS:
        raise FinalDeliveryError("Nombre de simulations par combinaison inattendu")
    if int(payload.get("laneCount") or -1) != EXPECTED_LANES:
        raise FinalDeliveryError("Nombre de voies fournisseurs inattendu")
    if {row.get("id") for row in payload.get("states") or []} != set(EXPECTED_STATES):
        raise FinalDeliveryError("États de fonctionnement incomplets")
    if {row.get("id") for row in payload.get("mechanisms") or []} != set(
        EXPECTED_MECHANISMS
    ):
        raise FinalDeliveryError("Hypothèses fournisseurs incomplètes")
    lot_selection_count = int((payload.get("lotReplay") or {}).get("dossierCount") or 0)
    if not 0 <= lot_selection_count <= MAX_LOT_DOSSIERS:
        raise FinalDeliveryError("Sélection de dossiers hors limites")
    reduced = {
        "states": payload["states"],
        "mechanisms": payload["mechanisms"],
        "repetitions": payload["repetitions"],
        "laneCount": payload["laneCount"],
        "supplierCount": payload["supplierCount"],
        "priorities": payload["priorities"],
        "supplierStatistics": payload["supplierStatistics"],
        "laneStatistics": payload["laneStatistics"],
        "stability": payload["stability"],
        "targetRegistry": payload["targetRegistry"],
        "targetLanes": payload["targetLanes"],
        "lotSelection": payload["lotReplay"],
        "evidence": payload["evidence"],
        "modelScope": payload["modelScope"],
        "matrix": {
            "baselineRows": EXPECTED_BASELINE_ROWS,
            "incidentRows": EXPECTED_INCIDENT_ROWS,
            "totalRows": EXPECTED_CAMPAIGN_ROWS,
            "states": 3,
            "lanes": EXPECTED_LANES,
            "mechanisms": 2,
            "repetitionsPerCombination": EXPECTED_REPETITIONS,
        },
    }
    binding = {
        "root": str(root),
        "results_dir": str(results),
        "campaign_validation": str(validation_path.resolve()),
        "campaign_validation_sha256": sha256_file(validation_path),
        "campaign_signature": validation.get("campaign_signature"),
        "engine_sha256": validation.get("engine_sha256"),
        "selected_lot_dossier_count": lot_selection_count,
        "matrix_result_count": EXPECTED_CAMPAIGN_ROWS,
    }
    return reduced, binding


def _inventory_entries(
    replay_root: Path, validation: Mapping[str, Any]
) -> dict[str, Path]:
    expected_inventory = (
        replay_root / "finalized" / "artifact_inventory.csv"
    ).resolve()
    declared_inventory = Path(str(validation.get("artifact_inventory") or "")).resolve()
    if declared_inventory != expected_inventory or not declared_inventory.is_file():
        raise FinalDeliveryError("Inventaire final des replays absent")
    if sha256_file(declared_inventory) != str(
        validation.get("artifact_inventory_sha256") or ""
    ):
        raise FinalDeliveryError("Inventaire final des replays modifié")
    rows = read_csv(declared_inventory)
    entries: dict[str, Path] = {}
    for row in rows:
        relative = Path(str(row.get("relative_path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise FinalDeliveryError("Chemin non portable dans l'inventaire replay")
        portable = relative.as_posix()
        path = (replay_root / relative).resolve()
        if (
            not path.is_relative_to(replay_root)
            or portable in entries
            or not path.is_file()
        ):
            raise FinalDeliveryError("Entrée d'inventaire replay invalide")
        if sha256_file(path) != str(row.get("sha256") or ""):
            raise FinalDeliveryError(f"Sortie replay modifiée : {portable}")
        if path.stat().st_size != integer(row.get("size_bytes"), label="taille replay"):
            raise FinalDeliveryError(f"Taille replay modifiée : {portable}")
        entries[portable] = path
    return entries


def _required_inventory_path(
    entries: Mapping[str, Path], relative: str, *, label: str
) -> Path:
    path = entries.get(relative)
    if path is None:
        raise FinalDeliveryError(f"Sortie replay absente : {label}")
    return path


def _tokens(value: Any) -> set[str]:
    return {
        token.strip() for token in re.split(r"[|;,]", str(value or "")) if token.strip()
    }


def _validate_trace_columns(
    rows: Sequence[Mapping[str, Any]], required: set[str], *, label: str
) -> None:
    if not rows:
        return
    missing = required - set(rows[0])
    if missing:
        raise FinalDeliveryError(
            f"Colonnes de trace absentes ({label}) : {sorted(missing)}"
        )


def _lot_curve_payload(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    required = {
        "day",
        "metric",
        "baseline_value",
        "incident_value",
        "delta_incident_minus_baseline",
    }
    _validate_trace_columns(rows, required, label="courbes appariées")
    grouped: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for row in rows:
        metric = str(row.get("metric") or "")
        day = integer(row.get("day"), label="jour replay")
        baseline = finite_number(
            row.get("baseline_value"), label="replay sans incident"
        )
        incident = finite_number(
            row.get("incident_value"), label="replay avec incident"
        )
        delta = finite_number(
            row.get("delta_incident_minus_baseline"), label="écart replay"
        )
        if not math.isclose(incident - baseline, delta, abs_tol=1e-6, rel_tol=1e-9):
            raise FinalDeliveryError("Écart de courbe replay incohérent")
        grouped[metric].append((day, baseline, incident))
    result = []
    for metric, values in sorted(grouped.items()):
        values.sort()
        days = [row[0] for row in values]
        if len(days) != len(set(days)):
            raise FinalDeliveryError("Jour replay dupliqué")
        result.append(
            {
                "metric": metric,
                "days": days,
                "baseline": [compact_number(row[1]) for row in values],
                "incident": [compact_number(row[2]) for row in values],
            }
        )
    if not result:
        raise FinalDeliveryError("Courbes appariées replay vides")
    return result


def _compact_lags(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(
            {
                "fraction": finite_number(
                    row.get("baseline_volume_fraction"), label="fraction de volume"
                ),
                "quantity": finite_number(
                    row.get("threshold_qty"), label="volume cible"
                ),
                "baselineDay": (
                    integer(row["baseline_reach_day"], label="jour de référence")
                    if str(row.get("baseline_reach_day") or "").strip()
                    else None
                ),
                "incidentDay": (
                    integer(row["incident_reach_day"], label="jour incident")
                    if str(row.get("incident_reach_day") or "").strip()
                    else None
                ),
                "lagDays": (
                    finite_number(row["lag_days"], label="retard de volume")
                    if str(row.get("lag_days") or "").strip()
                    else None
                ),
                "status": str(row.get("status") or ""),
            }
        )
    return result


def _chain_preview(
    shipments: Sequence[Mapping[str, str]],
    consumptions: Sequence[Mapping[str, str]],
    finished: Sequence[Mapping[str, str]],
    clients: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], int]:
    _validate_trace_columns(
        shipments,
        {"shipment_id", "risk_decision_day", "receipt_lot_id", "receipt_item_id"},
        label="expédition vers lot entrant",
    )
    _validate_trace_columns(
        consumptions,
        {"shipment_ids", "material_lot_id", "campaign_id", "batch_id"},
        label="lot entrant vers encours",
    )
    _validate_trace_columns(
        finished,
        {"shipment_ids", "finished_lot_id", "day"},
        label="encours vers lot de sortie",
    )
    _validate_trace_columns(
        clients,
        {"shipment_ids", "client_lot_id", "client_node_id", "day"},
        label="lot de sortie vers client agrégé",
    )
    unexpected_clients = {
        str(row.get("client_node_id") or "")
        for row in clients
        if str(row.get("client_node_id") or "") != "C-XXXXX"
    }
    if unexpected_clients:
        raise FinalDeliveryError("Un replay nomme un client non agrégé")
    result: list[dict[str, Any]] = []
    ordered_shipments = sorted(
        shipments,
        key=lambda row: (
            integer(row.get("risk_decision_day"), label="jour de décision"),
            str(row.get("shipment_id") or ""),
            str(row.get("receipt_lot_id") or ""),
        ),
    )
    for shipment in ordered_shipments:
        shipment_id = str(shipment.get("shipment_id") or "")
        if not shipment_id:
            raise FinalDeliveryError("Identifiant d'expédition absent")
        touched_consumptions = [
            row
            for row in consumptions
            if shipment_id in _tokens(row.get("shipment_ids"))
        ]
        touched_finished = [
            row for row in finished if shipment_id in _tokens(row.get("shipment_ids"))
        ]
        touched_clients = [
            row for row in clients if shipment_id in _tokens(row.get("shipment_ids"))
        ]
        campaigns = sorted(
            {
                "/".join(
                    value
                    for value in (
                        str(row.get("campaign_id") or ""),
                        str(row.get("batch_id") or ""),
                    )
                    if value
                )
                for row in touched_consumptions
                if row.get("campaign_id") or row.get("batch_id")
            }
        )
        result.append(
            {
                "shipment": shipment_id,
                "decisionDay": integer(
                    shipment.get("risk_decision_day"), label="jour de décision"
                ),
                "materialLot": str(shipment.get("receipt_lot_id") or ""),
                "materialItem": str(shipment.get("receipt_item_id") or "").removeprefix(
                    "item:"
                ),
                "campaigns": campaigns,
                "finishedLots": [
                    {
                        "id": str(row.get("finished_lot_id") or ""),
                        "day": integer(row.get("day"), label="jour lot de sortie"),
                    }
                    for row in touched_finished
                ],
                "clientLots": [
                    {
                        "id": str(row.get("client_lot_id") or ""),
                        "node": "C-XXXXX",
                        "day": integer(row.get("day"), label="jour client"),
                    }
                    for row in touched_clients
                ],
            }
        )
    return result[:MAX_CHAIN_PREVIEW_ROWS], len(result)


def load_lot_payload(
    *,
    campaign_root: Path,
    results_dir: Path,
    replay_root: Path | None,
    selected_count: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if selected_count == 0:
        if replay_root is not None:
            raise FinalDeliveryError(
                "Une racine replay a été fournie alors que la sélection signée est vide"
            )
        return {
            "status": "not_selected",
            "dossiers": [],
            "message": (
                "Aucun dossier n'a franchi les règles de sélection non forcée ; "
                "aucun rejeu détaillé n'a donc été lancé."
            ),
        }, None
    if replay_root is None:
        raise FinalDeliveryError(
            f"{selected_count} dossier(s) sont sélectionnés : replay finalisé obligatoire"
        )
    root = replay_root.resolve()
    try:
        plan = lot_replay.load_and_validate_plan(root)
    except Exception as exc:
        raise FinalDeliveryError(f"Plan de replay V4 refusé : {exc}") from exc
    if Path(str(plan.get("campaign_root") or "")).resolve() != campaign_root.resolve():
        raise FinalDeliveryError("Le replay appartient à une autre campagne")
    if Path(str(plan.get("results_dir") or "")).resolve() != results_dir.resolve():
        raise FinalDeliveryError("Le replay appartient à un autre paquet de résultats")
    dossiers = plan.get("dossiers")
    if not isinstance(dossiers, list) or len(dossiers) != selected_count:
        raise FinalDeliveryError(
            "Le nombre de dossiers replay diffère de la sélection signée"
        )

    receipt_path = root / "replay_run_receipt.json"
    receipt = read_json(receipt_path)
    receipt_signature = verify_signature(
        receipt, "run_receipt_signature", label="reçu d'exécution des replays"
    )
    if (
        receipt.get("schema_version") != lot_replay.RUN_RECEIPT_SCHEMA_VERSION
        or receipt.get("status") != "complete_validated"
        or receipt.get("plan_signature") != plan.get("plan_signature")
    ):
        raise FinalDeliveryError("Exécution des replays non complète")

    validation_path = root / "finalized" / "replay_validation.json"
    validation = read_json(validation_path)
    validation_signature = verify_signature(
        validation, "validation_signature", label="validation finale des replays"
    )
    if (
        validation.get("schema_version") != lot_replay.VALIDATION_SCHEMA_VERSION
        or validation.get("status") != "complete_validated"
        or validation.get("plan_signature") != plan.get("plan_signature")
        or validation.get("run_receipt_signature") != receipt_signature
    ):
        raise FinalDeliveryError("Validation finale des replays non complète")
    identity = validation.get("lot_identity_contract")
    if (
        not isinstance(identity, Mapping)
        or identity.get("ids_are_run_local") is not True
        or identity.get("cross_arm_lot_id_matching_allowed") is not False
    ):
        raise FinalDeliveryError("Contrat d'identité des lots incohérent")
    entries = _inventory_entries(root, validation)
    standalone = (root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html").resolve()
    if (
        Path(str(validation.get("standalone_html") or "")).resolve() != standalone
        or validation.get("standalone_html_sha256") != sha256_file(standalone)
        or entries.get("OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html") != standalone
    ):
        raise FinalDeliveryError("Rapport autonome source des replays modifié")
    declared_by_id = {
        str(row.get("dossier_id") or ""): row
        for row in validation.get("dossiers") or []
        if isinstance(row, Mapping)
    }
    if set(declared_by_id) != {str(row.get("dossier_id") or "") for row in dossiers}:
        raise FinalDeliveryError("Dossiers finalisés différents du plan signé")

    report: list[dict[str, Any]] = []
    for dossier in dossiers:
        dossier_id = str(dossier.get("dossier_id") or "")
        declared = declared_by_id[dossier_id]
        counts = declared.get("trace_counts")
        if not isinstance(counts, Mapping):
            raise FinalDeliveryError("Comptes de traçabilité absents")
        prefix = f"finalized/dossiers/{dossier_id}"
        shipments = read_csv(
            _required_inventory_path(
                entries,
                f"{prefix}/shipment_to_mp_lots.csv",
                label="expédition vers lot entrant",
            )
        )
        consumptions = read_csv(
            _required_inventory_path(
                entries,
                f"{prefix}/exposed_consumption_wip.csv",
                label="lot entrant vers encours",
            )
        )
        finished = read_csv(
            _required_inventory_path(
                entries,
                f"{prefix}/exposed_finished_lots.csv",
                label="encours vers lot de sortie",
            )
        )
        clients = read_csv(
            _required_inventory_path(
                entries,
                f"{prefix}/exposed_client_events.csv",
                label="lot de sortie vers client agrégé",
            )
        )
        chain, chain_total = _chain_preview(shipments, consumptions, finished, clients)
        paired_curves = _lot_curve_payload(
            read_csv(
                _required_inventory_path(
                    entries,
                    f"{prefix}/paired_daily_curves.csv",
                    label="courbes replay",
                )
            )
        )
        lags = _compact_lags(
            read_csv(
                _required_inventory_path(
                    entries,
                    f"{prefix}/cumulative_release_lag.csv",
                    label="retards à volume égal",
                )
            )
        )
        kpis_path = _required_inventory_path(
            entries, f"{prefix}/dossier_kpis.json", label="indicateurs replay"
        )
        kpis = read_json(kpis_path)
        priority = dossier.get("priority")
        incident_metric = dossier.get("incident_metric")
        if not isinstance(priority, Mapping) or not isinstance(
            incident_metric, Mapping
        ):
            raise FinalDeliveryError("Métadonnées du dossier replay absentes")
        exercised = integer(
            incident_metric.get("representative_valid_exercised_seed_count"),
            label="simulations physiquement exposées",
        )
        if not 1 <= exercised <= EXPECTED_REPETITIONS:
            raise FinalDeliveryError("Nombre de simulations exposées hors limites")
        trace_counts = {
            key: integer(value, label=f"compte {key}") for key, value in counts.items()
        }
        actual_counts = {
            "shipments": len({row.get("shipment_id") for row in shipments}),
            "material_receipts": len({row.get("receipt_lot_id") for row in shipments}),
            "consumptions": len(consumptions),
            "campaigns": len(
                {
                    row.get("campaign_id")
                    for row in consumptions
                    if row.get("campaign_id")
                }
            ),
            "batches": len(
                {row.get("batch_id") for row in consumptions if row.get("batch_id")}
            ),
            "finished_lots": len(finished),
            "client_events": len(clients),
            "clients": len(
                {
                    row.get("client_node_id")
                    for row in clients
                    if row.get("client_node_id")
                }
            ),
        }
        if any(trace_counts.get(key) != value for key, value in actual_counts.items()):
            raise FinalDeliveryError("Comptes de traçabilité différents des extraits")
        report.append(
            {
                "id": dossier_id,
                "state": str(priority.get("operating_point_id") or ""),
                "mechanism": str(priority.get("mechanism") or ""),
                "supplier": str(priority.get("supplier_id") or ""),
                "lane": str(priority.get("lane_id") or ""),
                "item": str(priority.get("item_id") or "").removeprefix("item:"),
                "destination": str(priority.get("dst_node_id") or ""),
                "targetProduct": str(
                    priority.get("target_product_id") or ""
                ).removeprefix("item:"),
                "seed": integer(dossier.get("seed"), label="graine replay"),
                "exercisedCount": exercised,
                "traceStatus": str(declared.get("status") or ""),
                "traceCounts": trace_counts,
                "chain": chain,
                "chainRowsTotal": chain_total,
                "chainRowsShown": len(chain),
                "curves": paired_curves,
                "lags": lags,
                "kpis": kpis,
            }
        )
    binding = {
        "root": str(root),
        "plan_signature": plan.get("plan_signature"),
        "run_receipt_signature": receipt_signature,
        "validation": str(validation_path.resolve()),
        "validation_sha256": sha256_file(validation_path),
        "validation_signature": validation_signature,
        "artifact_inventory_sha256": validation.get("artifact_inventory_sha256"),
        "dossier_count": len(report),
    }
    return {"status": "complete_validated", "dossiers": report}, binding


def _action_metric_summary(name: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    count = integer(raw.get("count"), label=f"nombre de gains {name}")
    if count == 0:
        if any(
            raw.get(field) is not None for field in ("mean", "median", "p10", "p90")
        ):
            raise FinalDeliveryError(f"Gain {name} annoncé sans simulation exercée")
        return {
            "id": name,
            "label": DISPLAY_ACTION_METRICS[name][0],
            "unit": DISPLAY_ACTION_METRICS[name][1],
            "count": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
            "ciLow": None,
            "ciHigh": None,
        }
    values = {
        "mean": finite_number(raw.get("mean"), label=f"moyenne {name}"),
        "median": finite_number(raw.get("median"), label=f"médiane {name}"),
        "p10": finite_number(raw.get("p10"), label=f"P10 {name}"),
        "p90": finite_number(raw.get("p90"), label=f"P90 {name}"),
        "ciLow": finite_number(raw.get("mean_ci95_low"), label=f"IC bas {name}"),
        "ciHigh": finite_number(raw.get("mean_ci95_high"), label=f"IC haut {name}"),
    }
    if (
        values["p10"] > values["median"] + 1e-12
        or values["median"] > values["p90"] + 1e-12
        or values["ciLow"] > values["ciHigh"] + 1e-12
    ):
        raise FinalDeliveryError(f"Dispersion d'action incohérente : {name}")
    return {
        "id": name,
        "label": DISPLAY_ACTION_METRICS[name][0],
        "unit": DISPLAY_ACTION_METRICS[name][1],
        "count": count,
        **{field: compact_number(value) for field, value in values.items()},
    }


def _validate_action_measurement_windows(
    *,
    summary: Mapping[str, Any],
    validation: Mapping[str, Any],
    status: str,
    selected_dossier_ids: set[str],
) -> tuple[dict[str, Any], set[tuple[str, int]]]:
    windows = summary.get("measurement_windows")
    if not isinstance(windows, Mapping) or windows != validation.get(
        "measurement_windows"
    ):
        raise FinalDeliveryError("Fenêtres de mesure signées absentes ou différentes")
    if set(windows) != {"impact_service", "state"}:
        raise FinalDeliveryError("Contrat des fenêtres de mesure inattendu")
    impact = windows.get("impact_service")
    state = windows.get("state")
    if not isinstance(impact, Mapping) or not isinstance(state, Mapping):
        raise FinalDeliveryError("Fenêtres de mesure incomplètes")
    if (
        set(impact) != {"metric_ids", "day_count", "ranges"}
        or list(impact.get("metric_ids") or []) != list(ACTION_IMPACT_METRIC_IDS)
        or integer(impact.get("day_count"), label="durée de la fenêtre d'impact") != 360
        or set(state) != {"metric_ids", "start_day", "end_day", "day_count"}
        or list(state.get("metric_ids") or []) != list(ACTION_STATE_METRIC_IDS)
        or integer(state.get("start_day"), label="début de la fenêtre d'état") != 0
        or integer(state.get("end_day"), label="fin de la fenêtre d'état") != 719
        or integer(state.get("day_count"), label="durée de la fenêtre d'état") != 720
    ):
        raise FinalDeliveryError("Bornes ou métriques des fenêtres de mesure invalides")
    raw_ranges = impact.get("ranges")
    if not isinstance(raw_ranges, list):
        raise FinalDeliveryError("Plages de la fenêtre d'impact absentes")
    range_keys: list[tuple[str, int]] = []
    for raw in raw_ranges:
        if not isinstance(raw, Mapping) or set(raw) != {
            "dossier_id",
            "seed",
            "start_day",
            "end_day",
            "day_count",
        }:
            raise FinalDeliveryError("Plage de mesure d'impact invalide")
        dossier_id = str(raw.get("dossier_id") or "")
        seed = integer(raw.get("seed"), label="graine de fenêtre d'impact")
        start = integer(raw.get("start_day"), label="début d'impact")
        end = integer(raw.get("end_day"), label="fin d'impact")
        count = integer(raw.get("day_count"), label="durée d'impact")
        if (
            dossier_id not in selected_dossier_ids
            or count != 360
            or start < 0
            or end > 719
            or end - start + 1 != count
        ):
            raise FinalDeliveryError("Plage d'impact hors du contrat signé")
        range_keys.append((dossier_id, seed))
    if range_keys != sorted(range_keys) or len(range_keys) != len(set(range_keys)):
        raise FinalDeliveryError("Plages d'impact non triées ou dupliquées")
    if status == "complete_no_representable_action" and range_keys:
        raise FinalDeliveryError("Plages d'action présentes sans levier représentable")
    if status == "complete_validated" and not range_keys:
        raise FinalDeliveryError("Aucune plage de mesure pour les actions validées")
    return {
        "impactService": {
            "dayCount": 360,
            "startVariesByDossierAndSeed": True,
        },
        "state": {"startDay": 0, "endDay": 719, "dayCount": 720},
    }, set(range_keys)


def load_action_payload(
    *,
    action_results_root: Path | None,
    campaign: Mapping[str, Any],
    campaign_binding: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if action_results_root is None:
        return {
            "status": "not_provided",
            "results": [],
            "refusals": [],
            "message": (
                "Aucun résultat d'action signé n'est joint : les leviers restent des "
                "pistes à tester, sans gain annoncé."
            ),
        }, None
    selected = (campaign.get("lotSelection") or {}).get("dossiers") or []
    if not selected:
        raise FinalDeliveryError(
            "Des résultats d'actions sont fournis sans dossier source sélectionné"
        )
    root = action_results_root.resolve()
    try:
        action_replay = importlib.import_module(
            "etudecas.prototypes.scan_2027_risk_control."
            "supplier_priority_action_replay_v4"
        )
        summary, validation = action_replay.validate_action_results(root)
    except Exception as exc:
        raise FinalDeliveryError(f"Résultats d'actions V4 refusés : {exc}") from exc
    status = str(summary.get("status") or "")
    if (
        summary.get("schema_version") != action_replay.SUMMARY_SCHEMA_VERSION
        or validation.get("schema_version") != action_replay.VALIDATION_SCHEMA_VERSION
        or status not in {"complete_validated", "complete_no_representable_action"}
        or validation.get("status") != status
        or summary.get("campaign_signature")
        != campaign_binding.get("campaign_signature")
        or validation.get("campaign_signature")
        != campaign_binding.get("campaign_signature")
    ):
        raise FinalDeliveryError("Résultats d'actions liés à une autre campagne")
    checks = validation.get("checks")
    required_true = {
        "all_source_hashes_revalidated",
        "all_commands_revalidated",
        "all_planned_arms_validated",
        "signed_reference_triplets_paired_by_seed",
        "only_incident_with_action_arms_executed",
        "demand_identical_within_each_triplet",
        "actions_kept_separate",
        "non_exercised_seeds_excluded_from_gain_statistics",
        "refused_actions_not_simulated",
        "state_dependent_risks_disabled",
        "quality_incident_or_action_absent",
        "capacity_or_availability_not_invented",
        "named_shipment_actuator_absent",
        "unavailable_reference_curve_kpis_are_null",
    }
    if not isinstance(checks, Mapping) or any(
        checks.get(field) is not True for field in required_true
    ):
        raise FinalDeliveryError("Contrôles scientifiques des actions incomplets")
    if (
        checks.get("reference_engine_rerun_count") != 0
        or checks.get("closed_loop_claimed") is not False
        or checks.get("complete_cost_or_roi_claimed") is not False
        or summary.get("reference_mode") != "signed_reference"
        or summary.get("reference_engine_rerun_count") != 0
        or summary.get("executed_engine_arm_type") != "incident_with_action_only"
        or (summary.get("bootstrap") or {}).get("historical_probability") is not False
    ):
        raise FinalDeliveryError("Interprétation des actions hors périmètre")
    selected_by_id = {
        str(row.get("dossierId") or ""): row
        for row in selected
        if isinstance(row, Mapping)
    }
    raw_results = summary.get("action_results") or []
    if not isinstance(raw_results, list):
        raise FinalDeliveryError("Résumé d'actions invalide")
    if status == "complete_validated" and not raw_results:
        raise FinalDeliveryError("Statut d'actions validé sans résultat")
    measurement_windows, measurement_range_keys = _validate_action_measurement_windows(
        summary=summary,
        validation=validation,
        status=status,
        selected_dossier_ids=set(selected_by_id),
    )
    expected_measurement_keys: set[tuple[str, int]] = set()
    results = []
    for raw in raw_results:
        if not isinstance(raw, Mapping):
            raise FinalDeliveryError("Résultat d'action invalide")
        dossier_id = str(raw.get("dossier_id") or "")
        source = selected_by_id.get(dossier_id)
        action_id = str(raw.get("action_id") or "")
        paired_count = integer(
            raw.get("paired_seed_count"), label="simulations d'action"
        )
        raw_paired_seeds = raw.get("paired_seeds")
        if not isinstance(raw_paired_seeds, list):
            raise FinalDeliveryError("Graines appariées des actions absentes")
        paired_seeds = [
            integer(value, label="graine appariée d'action")
            for value in raw_paired_seeds
        ]
        exercised_count = integer(
            raw.get("physically_exercised_seed_count"),
            label="simulations avec action exercée",
        )
        non_exercised_count = integer(
            raw.get("non_exercised_seed_count"),
            label="simulations sans action exercée",
        )
        paired_arms = raw.get("paired_arms")
        expected_identity = {
            "operating_point_id": "state",
            "mechanism": "mechanism",
            "lane_id": "lane",
            "supplier_id": "supplier",
            "item_id": "item",
            "dst_node_id": "destination",
            "target_product_id": "targetProduct",
        }
        if (
            source is None
            or action_id not in ALLOWED_ACTION_IDS
            or raw.get("client_scope") != "C-XXXXX"
            or raw.get("closed_loop") is not False
            or raw.get("recommendation_claimed") is not False
            or not isinstance(paired_arms, Mapping)
            or paired_arms.get("without_incident") != "signed_v4_campaign_reference"
            or paired_arms.get("incident_without_action")
            != "signed_v4_campaign_reference"
            or paired_arms.get("incident_with_action") != "executed_action_arm"
            or paired_arms.get("reference_engine_rerun_count") != 0
            or raw.get("gain_statistics_population")
            != "physically_exercised_paired_seeds_only"
            or not 1 <= paired_count <= EXPECTED_REPETITIONS
            or len(paired_seeds) != paired_count
            or len(set(paired_seeds)) != paired_count
            or exercised_count + non_exercised_count != paired_count
            or any(
                str(raw.get(raw_field) or "").removeprefix("item:")
                != str(source.get(source_field) or "").removeprefix("item:")
                for raw_field, source_field in expected_identity.items()
            )
        ):
            raise FinalDeliveryError("Identité ou périmètre d'une action incohérent")
        expected_measurement_keys.update((dossier_id, seed) for seed in paired_seeds)
        cost = raw.get("cost_interpretation")
        if (
            not isinstance(cost, Mapping)
            or cost.get("complete_intervention_cost") is not False
            or cost.get("roi_calculable") is not False
        ):
            raise FinalDeliveryError("Une action revendique un coût complet ou un ROI")
        gains_raw = raw.get("gain_statistics")
        if not isinstance(gains_raw, Mapping):
            raise FinalDeliveryError("Gains d'action absents")
        if "full_horizon_service_gain_pp" in gains_raw:
            raise FinalDeliveryError(
                "Gain d'action faussement attribué à tout l'horizon"
            )
        gains = [
            _action_metric_summary(name, gains_raw[name])
            for name in DISPLAY_ACTION_METRICS
            if isinstance(gains_raw.get(name), Mapping)
        ]
        action_status = str(raw.get("status") or "")
        if action_status not in {
            "estimated_on_physically_exercised_seeds",
            "non_exercised_no_gain_estimate",
        }:
            raise FinalDeliveryError("Statut d'action inattendu")
        if action_status == "estimated_on_physically_exercised_seeds" and (
            exercised_count == 0
            or not gains
            or any(gain["count"] != exercised_count for gain in gains)
        ):
            raise FinalDeliveryError("Action exercée sans résultat de gain")
        if action_status == "non_exercised_no_gain_estimate" and (
            exercised_count != 0 or non_exercised_count != paired_count or gains_raw
        ):
            raise FinalDeliveryError("Action non testable présentée comme un effet nul")
        results.append(
            {
                "dossierId": dossier_id,
                "state": str(raw.get("operating_point_id") or ""),
                "mechanism": str(raw.get("mechanism") or ""),
                "lane": str(raw.get("lane_id") or ""),
                "supplier": str(raw.get("supplier_id") or ""),
                "item": str(raw.get("item_id") or "").removeprefix("item:"),
                "destination": str(raw.get("dst_node_id") or ""),
                "targetProduct": str(raw.get("target_product_id") or "").removeprefix(
                    "item:"
                ),
                "actionId": action_id,
                "label": str(raw.get("action_label_fr") or ""),
                "parameters": raw.get("action_parameters") or {},
                "physicalScope": raw.get("action_physical_scope") or {},
                "status": action_status,
                "pairedCount": paired_count,
                "exercisedCount": exercised_count,
                "nonExercisedCount": non_exercised_count,
                "gains": gains,
                "limits": str(raw.get("limits_fr") or ""),
                "completeCostAvailable": False,
                "roiAvailable": False,
            }
        )
    if expected_measurement_keys != measurement_range_keys:
        raise FinalDeliveryError(
            "Fenêtres de mesure différentes des actions réellement comparées"
        )
    refusals = []
    raw_refusals = summary.get("refused_actions") or []
    if not isinstance(raw_refusals, list):
        raise FinalDeliveryError("Liste de leviers refusés invalide")
    for raw in raw_refusals:
        if (
            not isinstance(raw, Mapping)
            or raw.get("status") != "refused_not_simulated"
            or raw.get("simulated") is not False
        ):
            raise FinalDeliveryError("Statut de levier refusé invalide")
        dossier_id = str(raw.get("dossier_id") or "")
        if dossier_id not in selected_by_id:
            raise FinalDeliveryError("Levier refusé lié à un dossier inconnu")
        refusals.append(
            {
                "dossierId": dossier_id,
                "actionId": str(raw.get("action_id") or ""),
                "label": str(raw.get("label_fr") or ""),
                "reason": str(raw.get("refusal_reason") or ""),
                "limits": str(raw.get("limits_fr") or ""),
                "status": "refused_not_simulated",
            }
        )
    if int(summary.get("action_summary_count") or 0) != len(results) or int(
        summary.get("refused_action_count") or 0
    ) != len(refusals):
        raise FinalDeliveryError("Comptes du résumé d'actions incohérents")
    summary_path = root / "action_replay_summary.json"
    validation_path = root / "action_replay_validation.json"
    binding = {
        "root": str(root),
        "status": status,
        "campaign_signature": summary.get("campaign_signature"),
        "plan_signature": summary.get("plan_signature"),
        "summary_signature": summary.get("summary_signature"),
        "summary_sha256": sha256_file(summary_path),
        "validation_signature": validation.get("validation_signature"),
        "validation_sha256": sha256_file(validation_path),
        "measurement_windows_sha256": stable_sha256(summary["measurement_windows"]),
        "action_result_count": len(results),
        "refused_action_count": len(refusals),
    }
    action_message = (
        "Les références normale et incident sont relues depuis les preuves signées ; "
        "seuls les scénarios avec action ont été recalculés. La comparaison est faite "
        "graine par graine avec le même incident sans action. Les simulations où le "
        "levier n'agit physiquement pas sont exclues des gains. Deux fenêtres sont "
        "distinguées : le service pendant la fenêtre d'impact de 360 jours, et le "
        "service d'état, le retard cumulé et la production sur J0–J719. Aucun résultat "
        "n'est extrapolé au-delà de sa fenêtre."
        if status == "complete_validated"
        else (
            "Les références normale et incident ont été relues depuis les preuves "
            "signées, mais aucun levier physiquement représentable n'a été trouvé : "
            "aucun scénario avec action n'a été recalculé et aucun effet n'est annoncé."
        )
    )
    return {
        "status": status,
        "results": results,
        "refusals": refusals,
        "historicalProbabilityEstimated": False,
        "completeCostAvailable": False,
        "roiAvailable": False,
        "measurementWindows": measurement_windows,
        "message": action_message,
    }, binding


def _optional_link(
    path: Path | None, *, output_html: Path, label: str
) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = path.resolve()
    if not resolved.is_file() or resolved.suffix.casefold() not in {".html", ".htm"}:
        raise FinalDeliveryError(f"Page liée absente : {label}")
    relative = os.path.relpath(resolved, output_html.parent.resolve()).replace(
        "\\", "/"
    )
    return {
        "label": label,
        "href": relative,
        "source_path": str(resolved),
        "sha256": sha256_file(resolved),
    }


def build_delivery_payload(
    *,
    campaign_root: Path,
    results_dir: Path,
    curves_dir: Path | None,
    replay_root: Path | None,
    output_html: Path,
    target_registry_path: Path | None = None,
    dashboard_html: Path | None = None,
    action_results_root: Path | None = None,
    legacy_risk_html: Path | None = None,
    legacy_control_html: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    campaign, campaign_binding = load_campaign_payload(
        campaign_root=campaign_root,
        results_dir=results_dir,
        target_registry_path=target_registry_path,
    )
    if curves_dir is None:
        curves = {
            "status": "unavailable",
            "horizonDays": 0,
            "repetitionsPerState": 0,
            "quantiles": [],
            "series": [],
            "message": (
                "La capture journalière nominale n'était pas complète au moment de la "
                "livraison. Aucune courbe n'est remplacée ni estimée."
            ),
        }
        curves_binding = None
    else:
        curves, curves_binding = load_curve_payload(curves_dir)
    lot_payload, replay_binding = load_lot_payload(
        campaign_root=campaign_root,
        results_dir=results_dir,
        replay_root=replay_root,
        selected_count=int(campaign_binding["selected_lot_dossier_count"]),
    )
    action_payload, action_binding = load_action_payload(
        action_results_root=action_results_root,
        campaign=campaign,
        campaign_binding=campaign_binding,
    )
    curve_states = {row["state"] for row in curves["series"]}
    campaign_states = {row["id"] for row in campaign["states"]}
    if curve_states and curve_states != campaign_states:
        raise FinalDeliveryError("Les états des courbes et de la campagne diffèrent")
    links = [
        link
        for link in (
            _optional_link(
                dashboard_html,
                output_html=output_html,
                label="Analyse détaillée de la campagne V4",
            ),
            _optional_link(
                legacy_risk_html,
                output_html=output_html,
                label="Ancienne démonstration risques et simulations répétées",
            ),
            _optional_link(
                legacy_control_html,
                output_html=output_html,
                label="Ancienne démonstration du modèle dynamique",
            ),
        )
        if link is not None
    ]
    data_links: list[dict[str, Any]] = []
    if curves_binding:
        data_labels = {
            "service": "CSV.gz complet — service et retards",
            "production": "CSV.gz complet — production, encours et stocks de sortie",
            "input_stock": "CSV.gz complet — stocks entrants",
            "constraint": "CSV.gz complet — contraintes de production",
        }
        data_links = [
            {
                "label": data_labels[row["domain"]],
                "href": os.path.relpath(
                    Path(row["path"]), output_html.parent.resolve()
                ).replace("\\", "/"),
                "rowCount": row["row_count"],
            }
            for row in curves_binding["files"]
        ]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAtUtc": utc_now(),
        "viewCount": 3,
        "definitions": [
            {
                "term": "OBSERVÉ",
                "meaning": (
                    "Valeur lue directement dans une donnée industrielle datée. "
                    "Cette page n'affiche aucune performance fournisseur observée."
                ),
            },
            {
                "term": "SIMULÉ",
                "meaning": (
                    "Résultat produit par le moteur dans les hypothèses affichées ; "
                    "ce n'est pas une mesure du fournisseur."
                ),
            },
            {
                "term": "SIGNAL DE PRIORITÉ",
                "meaning": (
                    "Dossier à examiner en premier parce que son impact simulé ressort ; "
                    "ce n'est ni une note ni une probabilité d'incident."
                ),
            },
            {
                "term": "HYPOTHÈSE",
                "meaning": (
                    "Condition volontairement imposée au modèle pour tester la chaîne ; "
                    "elle doit être validée avec les équipes et les données réelles."
                ),
            },
        ],
        "curves": curves,
        "campaign": campaign,
        "lots": lot_payload,
        "actions": {
            **action_payload,
            "testedInThisDelivery": action_payload["status"] == "complete_validated",
            "automaticRegulationActive": False,
            "testableNow": [
                {
                    "title": "Stock libre ciblé au jour de départ",
                    "text": (
                        "Tester un volume réellement disponible et libéré sur le couple "
                        "site–article. Son achat, son coût et sa mise à disposition restent "
                        "à renseigner par l'industriel."
                    ),
                },
                {
                    "title": "Répartition entre voies déjà actives",
                    "text": (
                        "Tester un déplacement des achats uniquement entre fournisseurs déjà "
                        "présents pour le même besoin. Cela ne crée ni ne valide une nouvelle source."
                    ),
                },
            ],
            "notDemonstrated": [
                "Accélérer une expédition nommée et déjà partie.",
                "Prioriser automatiquement une commande client ou un ordre précis.",
                "Créer, homologuer ou contractualiser une nouvelle source.",
                "Annoncer un gain, un coût ou un délai récupéré avant une simulation d'action dédiée.",
            ],
        },
        "limits": [
            (
                "Les incidents sont des hypothèses externes appliquées une voie à la fois dans "
                "une fenêtre de 42 jours choisie pour être fortement exposée."
            ),
            (
                "Les 30 simulations décrivent la dispersion du modèle conditionnellement à ces "
                "hypothèses ; elles n'estiment pas leur fréquence historique."
            ),
            (
                "Stocks, transits, besoins, production et retard client évoluent jour par jour, "
                "mais aucun pilotage automatique ciblé n'agit dans ces résultats."
            ),
            (
                "Le calcul dynamique détaillé des besoins couvre 3 couples matière–site sur 24 ; "
                "il ne constitue pas encore une boucle de pilotage complète des 18 voies."
            ),
            (
                "Le client C-XXXXX est un nœud agrégé : aucun client réel ni aucune commande "
                "réelle ne sont identifiés."
            ),
        ],
        "links": [{"label": row["label"], "href": row["href"]} for row in links],
        "dataLinks": data_links,
        "sourceProof": {
            "campaignSignature": campaign_binding["campaign_signature"],
            "curveManifestSignature": (
                curves_binding["aggregate_manifest_signature"]
                if curves_binding
                else None
            ),
            "replayValidationSignature": (
                replay_binding["validation_signature"] if replay_binding else None
            ),
            "actionValidationSignature": (
                action_binding["validation_signature"] if action_binding else None
            ),
        },
        "package": {
            "htmlBytes": 0,
            "embeddedCurveSeries": len(curves["series"]),
            "embeddedCurvePoints": sum(len(row["median"]) for row in curves["series"]),
            "embeddedLotDossiers": len(lot_payload["dossiers"]),
            "embeddedActionResults": len(action_payload["results"]),
            "campaignResultCount": EXPECTED_CAMPAIGN_ROWS,
        },
    }
    bindings = {
        "campaign": campaign_binding,
        "curves": curves_binding,
        "replay": replay_binding,
        "actions": action_binding,
        "linked_pages": links,
    }
    return payload, bindings


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>RESILIENCE-SCAN — risques fournisseurs et lots</title>
  <style>
    :root{--navy:#08243f;--blue:#1769e0;--teal:#087e72;--green:#16835c;--amber:#c77a0a;--red:#cb4238;--ink:#142a40;--muted:#61758a;--line:#d7e2ec;--paper:#eef3f8;--card:#fff;--band:#b7d5ff88;--shadow:0 12px 34px #17395512}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.48 Inter,Segoe UI,Arial,sans-serif}button,select{font:inherit}header{padding:27px clamp(18px,4vw,58px);color:white;background:linear-gradient(118deg,#061b31,#124e80 64%,#08786c)}.overline{font-size:11px;font-weight:900;letter-spacing:.15em;color:#93ead8}h1{margin:6px 0 9px;font-size:clamp(29px,4.6vw,52px);line-height:1.04}header p{max-width:1000px;margin:0;color:#dceaf7;font-size:17px}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.chip,.badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:850}.chip{border:1px solid #ffffff42;background:#ffffff12}.badge.sim{background:#e7f0ff;color:#1456ae}.badge.hyp{background:#fff1dd;color:#9a5900}.badge.signal{background:#fff0ee;color:#a52e28}.badge.ok{background:#e5f6ee;color:#116844}.definitions{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#c9d8e6;border-bottom:1px solid #c4d2df}.definition{padding:12px clamp(10px,2vw,22px);background:white;min-height:96px}.definition b{display:block;color:var(--blue);font-size:11px;letter-spacing:.08em}.definition span{display:block;margin-top:4px;color:#52697f;font-size:12.5px}.tabs{position:sticky;top:0;z-index:20;display:flex;justify-content:center;gap:8px;padding:10px;background:#f8fbffed;border-bottom:1px solid var(--line);backdrop-filter:blur(9px)}.tabs button,.seg button{border:1px solid #b9cadb;border-radius:999px;background:white;color:#24445f;padding:8px 13px;font-weight:820;cursor:pointer}.tabs button.active,.seg button.active{background:var(--navy);border-color:var(--navy);color:white}main{max-width:1320px;margin:auto;padding:20px clamp(13px,3vw,32px) 54px}.view{display:none}.view.active{display:block}.intro,.card,.panel,.note{background:white;border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}.intro{padding:16px 18px;border-left:6px solid var(--blue);margin-bottom:14px}.intro h2{font-size:21px;margin:0}.intro p{margin:4px 0 0;color:var(--muted)}.grid{display:grid;gap:11px}.states{grid-template-columns:repeat(3,1fr)}.state,.kpi,.action,.limit{padding:14px;border:1px solid var(--line);border-radius:13px;background:#fff}.state strong,.kpi strong{display:block;font-size:25px;color:var(--navy)}.state small,.kpi small{display:block;color:var(--muted)}.state .offset{font-size:12px;margin-top:7px;color:#4e6579}.panel{padding:17px;margin:14px 0}.panel h3{margin:0 0 4px;font-size:19px}.panel>p{margin:4px 0 12px;color:var(--muted)}.toolbar{display:flex;align-items:end;gap:9px;flex-wrap:wrap;margin:12px 0}.field{display:grid;gap:3px}.field label{font-size:10px;font-weight:900;letter-spacing:.08em;color:var(--muted)}select{max-width:min(520px,92vw);padding:8px 10px;border:1px solid #b9cadb;border-radius:9px;background:white;color:var(--ink)}.chart-wrap{position:relative;overflow:auto;border:1px solid #e0e8f0;border-radius:12px;background:#fbfdff;padding:8px}.chart{display:block;width:100%;min-width:680px;height:auto}.legend{display:flex;gap:15px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin:8px 2px}.swatch{display:inline-block;width:18px;height:4px;vertical-align:middle;margin-right:5px;border-radius:4px}.swatch.band{height:10px;background:var(--band)}.swatch.median{background:var(--blue)}.swatch.base{background:#72859a}.swatch.incident{background:var(--red)}.reading{padding:10px 12px;border-radius:10px;background:#edf5ff;color:#31516e}.matrix{grid-template-columns:repeat(4,1fr)}.matrix .kpi{text-align:center}.matrix .kpi strong{font-size:28px}.seg{display:flex;gap:7px;flex-wrap:wrap}.two{grid-template-columns:1.15fr .85fr}.priority-list{display:grid;gap:8px}.priority{display:grid;grid-template-columns:42px 1fr auto;gap:10px;align-items:center;padding:10px;border:1px solid var(--line);border-radius:11px}.rank{display:grid;place-items:center;width:34px;height:34px;border-radius:50%;background:var(--navy);color:#fff;font-weight:900}.priority b{display:block}.priority small{color:var(--muted)}.priority .value{text-align:right;font-weight:900;color:var(--red)}table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{text-align:left;padding:8px;border-bottom:1px solid #e1e9f0;vertical-align:top}th{color:#52697e;font-size:10px;letter-spacing:.05em;text-transform:uppercase}.scroll{overflow:auto}.empty{padding:22px;text-align:center;color:var(--muted);background:#f7fafc;border:1px dashed #bdccda;border-radius:12px}.lot-tabs{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.lot-tabs button{border:1px solid #b9cadb;background:white;border-radius:9px;padding:8px 10px;cursor:pointer}.lot-tabs button.active{background:var(--teal);border-color:var(--teal);color:white}.lot-head{display:flex;justify-content:space-between;gap:14px;align-items:start;flex-wrap:wrap}.kpis{grid-template-columns:repeat(4,1fr)}.chain-flow{display:grid;grid-template-columns:repeat(5,1fr);gap:18px;align-items:stretch;margin:15px 0}.chain-node{position:relative;padding:13px 9px;border:1px solid #bdd0df;border-radius:12px;background:#f8fbfe;text-align:center}.chain-node:not(:last-child):after{content:"→";position:absolute;right:-18px;top:35%;color:var(--blue);font-size:22px}.chain-node b{display:block;font-size:22px}.actions{grid-template-columns:repeat(2,1fr)}.action.testable{border-left:5px solid var(--green)}.action.pending{border-left:5px solid var(--amber)}.action h4{margin:0 0 4px}.action p,.limit{color:var(--muted)}.limits{grid-template-columns:repeat(2,1fr)}.links a{display:inline-block;margin:5px 7px 0 0;padding:7px 10px;border:1px solid #b9cadb;border-radius:9px;color:#155ca9;text-decoration:none;background:#fff}footer{padding:20px;text-align:center;color:#6c7e90;font-size:12px}@media(max-width:900px){.definitions,.states,.matrix,.two,.kpis,.actions,.limits{grid-template-columns:1fr 1fr}.chain-flow{grid-template-columns:1fr}.chain-node:not(:last-child):after{content:"↓";right:auto;left:49%;top:auto;bottom:-20px}}@media(max-width:580px){.definitions,.states,.matrix,.two,.kpis,.actions,.limits{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}.priority{grid-template-columns:38px 1fr}.priority .value{grid-column:2;text-align:left}}
  </style>
</head>
<body>
  <header>
    <div class="overline">RESILIENCE-SCAN · LIVRAISON AUTONOME</div>
    <h1>Où la chaîne cède, comment l’impact se propage, quels lots regarder</h1>
    <p>Une lecture en trois vues : le fonctionnement quotidien simulé, les voies fournisseurs qui ressortent sous deux incidents distincts, puis la preuve physique jusqu’aux lots et au client agrégé.</p>
    <div class="chips"><span class="chip">J0–J719</span><span class="chip">3 états de service</span><span class="chip">30 simulations par combinaison</span><span class="chip">18 voies fournisseurs</span><span class="chip">fichier autonome</span></div>
  </header>
  <section class="definitions" id="definitions"></section>
  <nav class="tabs" aria-label="Parcours de démonstration">
    <button data-view="nominal" class="active">1. Fonctionnement</button>
    <button data-view="risks">2. Risques fournisseurs</button>
    <button data-view="lots">3. Lots et décisions</button>
  </nav>
  <main>
    <section class="view active" id="view-nominal">
      <div class="intro"><h2>Comment la chaîne fonctionne-t-elle avant incident ?</h2><p>Les bandes P10–P90 montrent la dispersion de 30 simulations indépendantes. La ligne est la médiane. Toutes les courbes de cette vue sont <b>simulées</b>.</p></div>
      <div class="grid states" id="state-cards"></div>
      <article class="panel">
        <h3>Trajectoire nominale</h3>
        <p>Le lissage est adapté au signal : 28 jours pour le service et les flux de production ; brut et 7 jours pour les niveaux de retard, de stock et d’encours.</p>
        <div class="toolbar" id="curve-toolbar">
          <div class="field"><label>ÉTAT SIMULÉ</label><select id="curve-state"></select></div>
          <div class="field"><label>INDICATEUR</label><select id="curve-metric"></select></div>
          <div class="field"><label>NŒUD ET ARTICLE</label><select id="curve-entity"></select></div>
        </div>
        <div class="legend" id="curve-legend"><span><i class="swatch band"></i>P10–P90</span><span><i class="swatch median"></i>Médiane</span></div>
        <div class="chart-wrap" id="curve-chart-wrap"><svg class="chart" id="nominal-chart" viewBox="0 0 1040 390" role="img" aria-label="Courbe nominale simulée"></svg></div>
        <p class="reading" id="curve-reading"></p>
      </article>
    </section>

    <section class="view" id="view-risks">
      <div class="intro"><h2>Les mêmes fournisseurs ressortent-ils quand la chaîne va bien ou mal ?</h2><p>Chaque incident est imposé séparément sur une seule voie. Le classement compare ses conséquences simulées, pas la fréquence réelle d’un problème fournisseur.</p></div>
      <div class="grid matrix" id="matrix-cards"></div>
      <article class="panel">
        <h3>Signaux de priorité et dispersion</h3>
        <p>La moyenne, P10 et P90 viennent de comparaisons appariées entre le fonctionnement sans incident et le même calcul avec incident.</p>
        <div class="toolbar">
          <div class="field"><label>ÉTAT SIMULÉ</label><select id="risk-state"></select></div>
          <div class="field"><label>HYPOTHÈSE FOURNISSEUR</label><select id="risk-mechanism"></select></div>
        </div>
        <p class="reading" id="risk-hypothesis"></p>
        <div class="chart-wrap"><svg class="chart" id="priority-chart" viewBox="0 0 1040 440" role="img" aria-label="Dispersion des impacts fournisseurs"></svg></div>
        <div class="priority-list" id="priority-list"></div>
      </article>
      <article class="panel">
        <h3>Sensibilité au niveau de service de départ</h3>
        <p>Une ligne n’est tracée que si la même voie et le même produit sont comparables dans les trois états. On voit alors si l’impact reste présent ou s’amplifie lorsque la chaîne est déjà tendue.</p>
        <div class="chart-wrap"><svg class="chart" id="sensitivity-chart" viewBox="0 0 1040 420" role="img" aria-label="Sensibilité des fournisseurs aux trois états"></svg></div>
        <p class="reading" id="sensitivity-reading"></p>
      </article>
    </section>

    <section class="view" id="view-lots">
      <div class="intro"><h2>Qu’est-ce qui est touché concrètement et que peut-on décider ?</h2><p>Le rejeu ciblé suit une expédition touchée vers le lot entrant, l’encours et la campagne, le lot de sortie, puis le nœud client agrégé. Les identifiants restent propres à chaque calcul.</p></div>
      <div id="lot-content"></div>
      <article class="panel">
        <h3>Actions : ce que la page prouve et ce qu’elle ne prouve pas</h3>
        <p id="action-intro"></p>
        <div id="action-results"></div>
        <div class="grid actions" id="action-cards"></div>
      </article>
      <article class="panel">
        <h3>Limites à dire au client</h3>
        <div class="grid limits" id="limit-cards"></div>
      </article>
      <article class="panel links"><h3>Paquet autonome</h3><p id="package-summary"></p><div id="data-links"></div></article>
      <article class="panel links" id="links-panel" hidden><h3>Vues complémentaires conservées</h3><p>Ces liens sont relatifs ; les pages historiques restent inchangées.</p><div id="links"></div></article>
    </section>
  </main>
  <footer>RESILIENCE-SCAN · simulation conditionnelle reproductible · aucune source externe requise</footer>
  <script id="delivery-data" type="application/json">__DATA__</script>
  <script>
  (()=>{
    "use strict";
    const D=JSON.parse(document.getElementById("delivery-data").textContent);
    const $=id=>document.getElementById(id);
    const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    const num=value=>{const n=Number(value);return Number.isFinite(n)?n:null};
    const fmt=(value,digits=1)=>{const n=num(value);return n===null?"—":new Intl.NumberFormat("fr-FR",{maximumFractionDigits:digits}).format(n)};
    const stateLabel=id=>({op_100:"Référence proche de 100 %",op_93:"Dégradé proche de 93 %",op_80:"Dégradé proche de 80 %"}[id]||id);
    const mechanism=id=>D.campaign.mechanisms.find(row=>row.id===id)||{label:id,shortLabel:id,hypothesis:""};
    const metricLabel=id=>({component_stock:"Stock composant",production_released:"Production libérée",wip:"Encours",served_on_due:"Service à l'heure",backlog:"Retard client",demand:"Demande"}[id]||id);
    const pct=value=>`${fmt(value,2)} pt`;
    document.querySelectorAll(".tabs button").forEach(button=>button.onclick=()=>{document.querySelectorAll(".tabs button").forEach(row=>row.classList.toggle("active",row===button));document.querySelectorAll(".view").forEach(row=>row.classList.toggle("active",row.id===`view-${button.dataset.view}`));location.hash=button.dataset.view});
    const requested=location.hash.slice(1);if(["nominal","risks","lots"].includes(requested)){document.querySelector(`.tabs button[data-view="${requested}"]`).click()}
    $("definitions").innerHTML=D.definitions.map(row=>`<div class="definition"><b>${esc(row.term)}</b><span>${esc(row.meaning)}</span></div>`).join("");
    $("state-cards").innerHTML=D.campaign.states.map(row=>`<article class="state"><span class="badge sim">SIMULÉ</span><h3>${esc(row.label)}</h3><strong>${fmt(row.globalServicePct,2)} %</strong><small>service global à l'heure · IC95 ${fmt(row.globalCiLowPct,2)}–${fmt(row.globalCiHighPct,2)} %</small><div class="offset">Produits : 268091 ${fmt(row.pf091ServicePct,2)} % · 268967 ${fmt(row.pf967ServicePct,2)} %<br>${row.id==="op_100"?"Référence sans dégradation ajoutée":`Hypothèse de délais planifiés ajoutés : +${fmt(row.offsetDays268091,0)} j / +${fmt(row.offsetDays268967,0)} j`}</div></article>`).join("");
    const curveState=$("curve-state"),curveMetric=$("curve-metric"),curveEntity=$("curve-entity");
    curveState.innerHTML=D.campaign.states.map(row=>`<option value="${esc(row.id)}">${esc(row.label)}</option>`).join("");
    const curveKey=row=>`${row.domain}|${row.metric}|${row.windowDays}`;
    const selectedCurves=()=>D.curves.series.filter(row=>row.state===curveState.value);
    function fillCurveMetrics(){const seen=new Map();selectedCurves().forEach(row=>seen.set(curveKey(row),row.label));curveMetric.innerHTML=[...seen].map(([key,label])=>`<option value="${esc(key)}">${esc(label)}</option>`).join("");curveMetric.disabled=!seen.size;curveEntity.disabled=!seen.size;fillCurveEntities()}
    function fillCurveEntities(){const rows=selectedCurves().filter(row=>curveKey(row)===curveMetric.value);curveEntity.innerHTML=rows.map((row,index)=>`<option value="${index}">${esc(row.node)} · article ${esc(row.item)}</option>`).join("");drawNominal()}
    function svgLine(points,color,width=3){return `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linejoin="round" stroke-linecap="round"/>`}
    function drawNominal(){const rows=selectedCurves().filter(row=>curveKey(row)===curveMetric.value),row=rows[Number(curveEntity.value)||0],svg=$("nominal-chart");if(!row){svg.innerHTML='<text x="520" y="190" text-anchor="middle" fill="#61758a">Capture journalière non disponible — aucune courbe estimée.</text>';$("curve-reading").textContent=D.curves.message||"Courbe absente.";return}const service=row.metric==="on_due_service_ratio",factor=service?100:1,low=row.p10.map(v=>Number(v)*factor),mid=row.median.map(v=>Number(v)*factor),high=row.p90.map(v=>Number(v)*factor),minimum=Math.min(...low),maximum=Math.max(...high),span=Math.max(1e-9,maximum-minimum),lo=service?Math.max(0,minimum-span*.08):Math.max(0,minimum-span*.08),hi=maximum+span*.12+1e-9,W=1040,H=390,p={l:72,r:22,t:20,b:46},x=i=>p.l+(W-p.l-p.r)*i/Math.max(1,mid.length-1),y=v=>p.t+(hi-v)*(H-p.t-p.b)/(hi-lo);let out="";for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4,yy=y(value);out+=`<line x1="${p.l}" y1="${yy}" x2="${W-p.r}" y2="${yy}" stroke="#dfe8f0"/><text x="${p.l-9}" y="${yy+4}" text-anchor="end" fill="#60748a" font-size="11">${fmt(value,service?1:0)}</text>`}const upper=high.map((v,i)=>`${x(i)},${y(v)}`).join(" "),lower=low.map((v,i)=>`${x(low.length-1-i)},${y(low[low.length-1-i])}`).join(" ");out+=`<polygon points="${upper} ${lower}" fill="#b7d5ff88"/>`;out+=svgLine(mid.map((v,i)=>`${x(i)},${y(v)}`).join(" "),"#1769e0",3);[row.startDay,360,719].filter(day=>day>=row.startDay).forEach(day=>{const xx=p.l+(W-p.l-p.r)*(day-row.startDay)/Math.max(1,mid.length-1);out+=`<line x1="${xx}" y1="${H-p.b}" x2="${xx}" y2="${H-p.b+5}" stroke="#70859a"/><text x="${xx}" y="${H-16}" text-anchor="middle" fill="#60748a" font-size="11">J${day}</text>`});out+=`<text x="18" y="18" fill="#60748a" font-size="11">${service?"%":esc(row.unit)}</text>`;svg.innerHTML=out;const last=mid.length-1;$("curve-reading").innerHTML=`<b>${esc(row.label)} · ${esc(row.node)} / ${esc(row.item)}</b><br>${esc(row.explanation)} À J719 : médiane ${fmt(mid[last],service?2:0)}${service?" %":" "+esc(row.unit)}, bande P10–P90 ${fmt(low[last],service?2:0)} à ${fmt(high[last],service?2:0)}.`}
    curveState.onchange=fillCurveMetrics;curveMetric.onchange=fillCurveEntities;curveEntity.onchange=drawNominal;if(D.curves.series.length){fillCurveMetrics()}else{$("curve-toolbar").hidden=true;$("curve-legend").hidden=true;$("curve-chart-wrap").hidden=true;$("curve-reading").className="empty";$("curve-reading").textContent=D.curves.message||"Capture journalière absente : aucune courbe affichée."}
    const M=D.campaign.matrix;$("matrix-cards").innerHTML=[[`<b>${fmt(M.totalRows,0)}</b>`,`résultats contrôlés (${fmt(M.baselineRows,0)} références + ${fmt(M.incidentRows,0)} incidents)`],[`<b>${M.repetitionsPerCombination}</b>`,`simulations indépendantes par combinaison`],[`<b>${M.lanes}</b>`,`voies fournisseurs testées`],[`<b>${M.mechanisms}</b>`,`incidents physiques gardés séparés`]].map(([v,l])=>`<article class="kpi"><strong>${v}</strong><small>${l}</small></article>`).join("");
    const riskState=$("risk-state"),riskMechanism=$("risk-mechanism");riskState.innerHTML=D.campaign.states.map(row=>`<option value="${esc(row.id)}">${esc(row.label)}</option>`).join("");riskMechanism.innerHTML=D.campaign.mechanisms.map(row=>`<option value="${esc(row.id)}">${esc(row.label)}</option>`).join("");
    function priorityRows(){return D.campaign.priorities.filter(row=>row.state===riskState.value&&row.mechanism===riskMechanism.value).sort((a,b)=>(Number(a.position)||999)-(Number(b.position)||999))}
    function drawPriorities(){const rows=priorityRows(),svg=$("priority-chart"),W=1040,H=440,p={l:260,r:75,t:42,b:42},cause=mechanism(riskMechanism.value);$("risk-hypothesis").innerHTML=`<b>Hypothèse testée :</b> ${esc(cause.hypothesis)} Fenêtre de forte exposition, voie par voie — pas un incident moyen.`;if(!rows.length){svg.innerHTML='<text x="520" y="210" text-anchor="middle" fill="#61758a">Aucun signal retenu dans cette combinaison.</text>';$("priority-list").innerHTML='<div class="empty">Aucun dossier n’est forcé : l’absence de signal est conservée.</div>';drawSensitivity();return}const shown=rows.filter(row=>!row.supplementaryBacklogSignal).slice(0,10);if(!shown.length){svg.innerHTML='<text x="520" y="210" text-anchor="middle" fill="#61758a">Aucune perte de service classable ; voir les alertes de retard ci-dessous.</text>'}else{const values=shown.flatMap(row=>[num(row.service.p10)||0,num(row.service.p90)||0,num(row.service.mean)||0]),maximum=Math.max(0.2,...values)*1.15,x=v=>p.l+(W-p.l-p.r)*Number(v||0)/maximum,step=(H-p.t-p.b)/shown.length;let out=`<text x="${p.l}" y="20" fill="#61758a" font-size="11">Perte de service du produit alimenté (points) · P10 — moyenne — P90</text>`;for(let i=0;i<=5;i++){const value=maximum*i/5,xx=x(value);out+=`<line x1="${xx}" y1="${p.t-8}" x2="${xx}" y2="${H-p.b}" stroke="#e0e8f0"/><text x="${xx}" y="${H-15}" text-anchor="middle" fill="#61758a" font-size="10">${fmt(value,1)}</text>`}shown.forEach((row,i)=>{const yy=p.t+step*(i+.5),a=x(row.service.p10),b=x(row.service.p90),m=x(row.service.mean);out+=`<text x="${p.l-12}" y="${yy+4}" text-anchor="end" fill="#142a40" font-size="11">${esc(row.supplier)} · ${esc(row.item)}</text><line x1="${a}" y1="${yy}" x2="${b}" y2="${yy}" stroke="#9db9d5" stroke-width="7" stroke-linecap="round"/><circle cx="${m}" cy="${yy}" r="5" fill="#cb4238"><title>${fmt(row.service.mean,2)} points · voie ${esc(row.lane)}</title></circle>`});svg.innerHTML=out}$("priority-list").innerHTML=rows.map(row=>`<div class="priority"><div class="rank">${fmt(row.position,0)}</div><div><b>${esc(row.supplier)} · ${esc(row.item)} → ${esc(row.destination)}</b><small>Voie ${esc(row.lane)} · produit ${esc(row.targetProduct)} · ${row.supplementaryBacklogSignal?"alerte complémentaire de retard":"signal fondé sur le service"}</small></div><div class="value">${row.supplementaryBacklogSignal?`${fmt(row.backlog.mean,2)} j-demande`:pct(row.service.mean)}<br><small>${row.supplementaryBacklogSignal?"hors classement service":`P10–P90 ${fmt(row.service.p10,2)}–${fmt(row.service.p90,2)}`}</small></div></div>`).join("");drawSensitivity()}
    function drawSensitivity(){const rows=D.campaign.stability.filter(row=>row.mechanism===riskMechanism.value&&row.allStatesComparable&&row.sameExposedLaneAcrossStates&&row.sameTargetProductAcrossStates&&D.campaign.states.every(state=>num(row.effectsByState[state.id])!==null)).sort((a,b)=>Math.max(...Object.values(b.effectsByState).map(Number))-Math.max(...Object.values(a.effectsByState).map(Number))).slice(0,8),svg=$("sensitivity-chart"),W=1040,H=420,xs=[180,520,860];if(!rows.length){svg.innerHTML='<text x="520" y="200" text-anchor="middle" fill="#61758a">Aucune série strictement comparable dans les trois états.</text>';$("sensitivity-reading").textContent="Les états restent lisibles séparément ; aucune stabilité inter-états n’est revendiquée.";return}const maximum=Math.max(.1,...rows.flatMap(row=>Object.values(row.effectsByState).map(Number)))*1.14,y=v=>35+(maximum-Number(v))*(H-105)/maximum,palette=["#1769e0","#087e72","#c77a0a","#7651b7","#cb4238","#2d8caf","#68813a","#9b536e"];let out="";for(let i=0;i<=4;i++){const value=maximum*i/4,yy=y(value);out+=`<line x1="120" y1="${yy}" x2="920" y2="${yy}" stroke="#e0e8f0"/><text x="110" y="${yy+4}" text-anchor="end" fill="#61758a" font-size="10">${fmt(value,1)}</text>`}D.campaign.states.forEach((state,i)=>out+=`<text x="${xs[i]}" y="${H-18}" text-anchor="middle" fill="#52697e" font-size="11">${esc(stateLabel(state.id))}</text>`);rows.forEach((row,i)=>{const color=palette[i%palette.length],points=D.campaign.states.map((state,j)=>`${xs[j]},${y(row.effectsByState[state.id])}`).join(" ");out+=svgLine(points,color,2.7);D.campaign.states.forEach((state,j)=>out+=`<circle cx="${xs[j]}" cy="${y(row.effectsByState[state.id])}" r="4" fill="${color}"><title>${esc(row.supplier)} · ${fmt(row.effectsByState[state.id],2)} points</title></circle>`);out+=`<text x="${xs[2]+9}" y="${y(row.effectsByState.op_80)+4}" fill="${color}" font-size="10">${esc(row.supplier)}</text>`});svg.innerHTML=out;const stable=new Set(rows.filter(row=>row.allStates).map(row=>row.supplier)).size;$("sensitivity-reading").innerHTML=`Le graphique affiche <b>${stable} fournisseur(s) distinct(s)</b> avec une comparaison admissible sur la même voie et le même produit pour cette hypothèse. C’est une sensibilité conditionnelle du modèle, pas une notation fournisseur.`}
    riskState.onchange=drawPriorities;riskMechanism.onchange=drawPriorities;drawPriorities();
    function lotMetricLabel(metric){return metricLabel(metric)}
    function drawLotCurve(dossier,metric){const row=dossier.curves.find(value=>value.metric===metric),svg=$("lot-chart"),W=1040,H=370,p={l:68,r:20,t:22,b:42};if(!row){svg.innerHTML="";return}const values=[...row.baseline,...row.incident].map(Number),lo=Math.min(0,...values),hi=Math.max(1,...values)*1.08,x=i=>p.l+(W-p.l-p.r)*i/Math.max(1,row.days.length-1),y=v=>p.t+(hi-Number(v))*(H-p.t-p.b)/(hi-lo);let out="";for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4,yy=y(value);out+=`<line x1="${p.l}" y1="${yy}" x2="${W-p.r}" y2="${yy}" stroke="#e0e8f0"/><text x="${p.l-9}" y="${yy+4}" text-anchor="end" fill="#61758a" font-size="10">${fmt(value,0)}</text>`}out+=svgLine(row.baseline.map((v,i)=>`${x(i)},${y(v)}`).join(" "),"#72859a",2.5)+svgLine(row.incident.map((v,i)=>`${x(i)},${y(v)}`).join(" "),"#cb4238",2.5);[0,Math.floor(row.days.length/2),row.days.length-1].forEach(i=>out+=`<text x="${x(i)}" y="${H-15}" text-anchor="middle" fill="#61758a" font-size="10">J${row.days[i]}</text>`);svg.innerHTML=out}
    function renderLot(dossier,index){const k=dossier.kpis,t=dossier.traceCounts,mechan=mechanism(dossier.mechanism),fullClient=dossier.traceStatus==="native_trace_to_client";return `<div class="lot-tabs">${D.lots.dossiers.map((row,i)=>`<button data-lot="${i}" class="${i===index?"active":""}">${esc(row.supplier)} · ${esc(mechanism(row.mechanism).shortLabel)}</button>`).join("")}</div><article class="panel"><div class="lot-head"><div><span class="badge signal">SIGNAL DE PRIORITÉ</span> <span class="badge hyp">HYPOTHÈSE</span><h3>${esc(dossier.supplier)} · article ${esc(dossier.item)} → ${esc(dossier.destination)}</h3><p>${esc(mechan.label)} · voie ${esc(dossier.lane)} · produit ${esc(dossier.targetProduct)} · simulation représentative choisie parmi ${dossier.exercisedCount}/30 où la voie a réellement été exposée.</p></div><span class="badge ${fullClient?"ok":"hyp"}">${fullClient?"CHAÎNE JUSQU’AU CLIENT AGRÉGÉ":"CHAÎNE PARTIELLE"}</span></div><div class="grid kpis"><div class="kpi"><strong>${pct(k.service_loss_pp)}</strong><small>service à l’heure perdu</small></div><div class="kpi"><strong>${fmt(k.on_due_units_lost,0)}</strong><small>unités à l’heure perdues</small></div><div class="kpi"><strong>${fmt(k.production_released_loss_qty,0)}</strong><small>unités de production libérée perdues</small></div><div class="kpi"><strong>${k.backlog_recovery_day==null?"non démontré":"J"+fmt(k.backlog_recovery_day,0)}</strong><small>retour au niveau de retard de référence</small></div></div></article><article class="panel"><h3>Cascade d’impact physique dans ce rejeu</h3><div class="chain-flow"><div class="chain-node"><b>${fmt(t.shipments,0)}</b>expéditions touchées</div><div class="chain-node"><b>${fmt(t.material_receipts,0)}</b>lots entrants reçus</div><div class="chain-node"><b>${fmt(t.campaigns,0)} / ${fmt(t.batches,0)}</b>campagnes / lots de fabrication</div><div class="chain-node"><b>${fmt(t.finished_lots,0)}</b>lots de sortie descendants</div><div class="chain-node"><b>${fmt(t.clients,0)}</b>nœuds clients agrégés</div></div><p>Le lien généalogique montre le contact physique. L’écart métier vient de la comparaison appariée des courbes, pas du simple comptage des événements.</p><div class="scroll"><table><thead><tr><th>Expédition / jour</th><th>Lot entrant</th><th>Campagne / lot fabrication</th><th>Lots de sortie</th><th>Client agrégé</th></tr></thead><tbody>${dossier.chain.map(row=>`<tr><td>${esc(row.shipment)} · J${row.decisionDay}</td><td>${esc(row.materialLot)}<br><small>article ${esc(row.materialItem)}</small></td><td>${row.campaigns.length?row.campaigns.map(esc).join("<br>"):"—"}</td><td>${row.finishedLots.length?row.finishedLots.map(value=>`${esc(value.id)} · J${value.day}`).join("<br>"):"—"}</td><td>${row.clientLots.length?row.clientLots.map(value=>`${esc(value.node)} · ${esc(value.id)} · J${value.day}`).join("<br>"):"—"}</td></tr>`).join("")}</tbody></table></div><p class="reading">${dossier.chainRowsShown}/${dossier.chainRowsTotal} chaîne(s) expédition–réception affichée(s). Les extraits complets restent liés par l’inventaire signé du replay.</p></article><article class="panel"><h3>Sans incident / incident sans action</h3><div class="toolbar"><div class="field"><label>INDICATEUR</label><select id="lot-metric">${dossier.curves.map(row=>`<option value="${esc(row.metric)}">${esc(lotMetricLabel(row.metric))}</option>`).join("")}</select></div></div><div class="legend"><span><i class="swatch base"></i>Sans incident</span><span><i class="swatch incident"></i>Incident sans action</span></div><div class="chart-wrap"><svg class="chart" id="lot-chart" viewBox="0 0 1040 370" role="img" aria-label="Courbes appariées du replay"></svg></div><div class="scroll"><table><thead><tr><th>Volume de référence</th><th>Jour sans incident</th><th>Jour avec incident</th><th>Retard</th></tr></thead><tbody>${dossier.lags.map(row=>`<tr><td>${fmt(row.fraction*100,0)} % · ${fmt(row.quantity,0)} unités</td><td>${row.baselineDay==null?"—":"J"+row.baselineDay}</td><td>${row.incidentDay==null?"non atteint":"J"+row.incidentDay}</td><td>${row.lagDays==null?"non calculable":fmt(row.lagDays,0)+" j"}</td></tr>`).join("")}</tbody></table></div></article>`}
    function bindLot(index){const dossier=D.lots.dossiers[index];$("lot-content").innerHTML=renderLot(dossier,index);document.querySelectorAll("[data-lot]").forEach(button=>button.onclick=()=>bindLot(Number(button.dataset.lot)));const select=$("lot-metric");select.onchange=()=>drawLotCurve(dossier,select.value);drawLotCurve(dossier,select.value)}
    if(D.lots.status==="complete_validated"&&D.lots.dossiers.length){bindLot(0)}else{$("lot-content").innerHTML=`<div class="empty"><b>Aucun rejeu détaillé présenté.</b><br>${esc(D.lots.message||"La sélection signée ne contient aucun dossier.")}</div>`}
    const actionGain=value=>value.mean==null?"—":`${fmt(value.mean,value.unit==="point"?2:0)} ${esc(value.unit)}<small>moyenne · P10–P90 ${fmt(value.p10,value.unit==="point"?2:0)}–${fmt(value.p90,value.unit==="point"?2:0)} · ${value.count} simulations</small>`;if(D.actions.status==="complete_validated"||D.actions.status==="complete_no_representable_action"){$("action-intro").innerHTML=`<b>Aucune régulation automatique n’intervient.</b> ${esc(D.actions.message)} Le coût complet et le retour sur investissement ne sont pas calculables.`;$("action-results").innerHTML=D.actions.results.length?D.actions.results.map(row=>`<article class="panel"><span class="badge ${row.status==="estimated_on_physically_exercised_seeds"?"ok":"hyp"}">${row.status==="estimated_on_physically_exercised_seeds"?"ACTION EXERCÉE":"NON TESTABLE SUR CE CAS"}</span><h3>${esc(row.label)}</h3><p>${esc(row.supplier)} · ${esc(row.item)} → ${esc(row.destination)} · ${esc(mechanism(row.mechanism).shortLabel)} · levier actif dans ${row.exercisedCount}/${row.pairedCount} simulations appariées.</p>${row.gains.length?`<div class="grid kpis">${row.gains.map(value=>`<div class="kpi"><strong>${actionGain(value)}</strong><small>${esc(value.label)}</small></div>`).join("")}</div>`:'<div class="empty">Le cas ne présente aucune occurrence où le levier agit physiquement : il n’est pas testable ici et aucun effet n’est estimé.</div>'}<p class="reading">${esc(row.limits)}</p></article>`).join(""):"";const refused=D.actions.refusals.map(row=>`<article class="action pending"><span class="badge hyp">REFUSÉ · NON SIMULÉ</span><h4>${esc(row.label)}</h4><p>${esc(row.reason)} ${esc(row.limits)}</p></article>`);$("action-cards").innerHTML=refused.join("")||'<div class="empty">Aucun levier refusé dans ce paquet.</div>'}else{$("action-intro").innerHTML=`<b>Aucune régulation automatique n’intervient dans les résultats affichés.</b> ${esc(D.actions.message)}`;const tested=D.actions.testableNow.map(row=>`<article class="action testable"><span class="badge ok">SIMULABLE</span><h4>${esc(row.title)}</h4><p>${esc(row.text)}</p></article>`),pending=D.actions.notDemonstrated.map(text=>`<article class="action pending"><span class="badge hyp">NON DÉMONTRÉ ICI</span><p>${esc(text)}</p></article>`);$("action-cards").innerHTML=[...tested,...pending].join("")}$("limit-cards").innerHTML=D.limits.map(text=>`<div class="limit">${esc(text)}</div>`).join("");$("package-summary").innerHTML=`<b>${fmt(D.package.htmlBytes/1048576,2)} Mo</b> · ${fmt(D.package.embeddedCurveSeries,0)} séries / ${fmt(D.package.embeddedCurvePoints,0)} points journaliers embarqués sans sous-échantillonnage · ${fmt(D.package.embeddedLotDossiers,0)} dossier(s) de lots · ${fmt(D.package.embeddedActionResults,0)} résultat(s) d’action · synthèse de ${fmt(D.package.campaignResultCount,0)} résultats de campagne. Le fichier JSON voisin permet de contrôler automatiquement l’intégrité de cette livraison.`;$("data-links").innerHTML=D.dataLinks.length?'<b>Données journalières complètes :</b><br>'+D.dataLinks.map(row=>`<a href="${esc(row.href)}">${esc(row.label)} · ${fmt(row.rowCount,0)} lignes ↗</a>`).join(""):'Les courbes complètes ne sont pas jointes à ce stade.';if(D.links.length){$("links-panel").hidden=false;$("links").innerHTML=D.links.map(row=>`<a href="${esc(row.href)}">${esc(row.label)} ↗</a>`).join("")}
  })();
  </script>
</body>
</html>
"""


def render_html(payload: Mapping[str, Any]) -> str:
    document = HTML_TEMPLATE.replace("__DATA__", safe_json(payload))
    if document.count('class="view') != 3:
        raise FinalDeliveryError("Le document ne contient pas exactement trois vues")
    lowered = document.casefold()
    forbidden_phrases = ("retenue qualité", "incident qualité", "risque qualité")
    if any(phrase in lowered for phrase in forbidden_phrases):
        raise FinalDeliveryError("Vocabulaire hors périmètre dans la page finale")
    return document


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            Path(temporary_name).unlink(missing_ok=True)
        finally:
            raise


def manifest_path_for(output_html: Path) -> Path:
    return output_html.with_suffix(output_html.suffix + ".manifest.json")


def build_delivery(
    *,
    campaign_root: Path,
    results_dir: Path,
    curves_dir: Path | None,
    output_html: Path,
    replay_root: Path | None = None,
    target_registry_path: Path | None = None,
    dashboard_html: Path | None = None,
    action_results_root: Path | None = None,
    legacy_risk_html: Path | None = None,
    legacy_control_html: Path | None = None,
) -> dict[str, Any]:
    output = output_html.resolve()
    manifest_path = manifest_path_for(output)
    if output.exists() or manifest_path.exists():
        raise FileExistsError(f"Refus d'écraser une livraison existante : {output}")
    payload, bindings = build_delivery_payload(
        campaign_root=campaign_root,
        results_dir=results_dir,
        curves_dir=curves_dir,
        replay_root=replay_root,
        output_html=output,
        target_registry_path=target_registry_path,
        dashboard_html=dashboard_html,
        action_results_root=action_results_root,
        legacy_risk_html=legacy_risk_html,
        legacy_control_html=legacy_control_html,
    )
    document = ""
    encoded = b""
    for _ in range(6):
        document = render_html(payload)
        encoded = document.encode("utf-8")
        size = len(encoded)
        if payload["package"]["htmlBytes"] == size:
            break
        payload["package"]["htmlBytes"] = size
    else:  # pragma: no cover - size changes converge once digit width is stable
        raise FinalDeliveryError("Taille du paquet autonome non stabilisée")
    html_sha = hashlib.sha256(encoded).hexdigest()
    unsigned_manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "generated_at_utc": utc_now(),
        "offline_single_file": True,
        "view_count": 3,
        "output_html": output.name,
        "output_html_sha256": html_sha,
        "output_html_bytes": len(encoded),
        "payload_sha256": stable_sha256(payload),
        "generator": str(Path(__file__).resolve()),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
        "source_bindings": bindings,
        "scientific_scope": {
            "campaign_result_count": EXPECTED_CAMPAIGN_ROWS,
            "nominal_curve_days": (
                EXPECTED_HORIZON_DAYS if bindings["curves"] is not None else 0
            ),
            "curve_downsampling_applied": False,
            "simulations_per_state_or_cell": EXPECTED_REPETITIONS,
            "mechanisms_kept_separate": True,
            "historical_incident_probability_estimated": False,
            "automatic_targeted_control_active": False,
            "signed_action_results_included": bindings["actions"] is not None,
            "observed_supplier_performance_displayed": False,
            "forced_top_three": False,
        },
    }
    manifest = {
        **unsigned_manifest,
        "delivery_signature": stable_sha256(unsigned_manifest),
    }
    _atomic_write_text(output, document)
    try:
        _atomic_write_text(
            manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    validate_delivery(output)
    return manifest


def _embedded_payload(document: str) -> dict[str, Any]:
    pattern = re.compile(
        r'<script id="delivery-data" type="application/json">(.*?)</script>',
        re.DOTALL,
    )
    matches = pattern.findall(document)
    if len(matches) != 1:
        raise FinalDeliveryError("Données autonomes absentes ou dupliquées")
    try:
        payload = json.loads(html.unescape(matches[0]))
    except json.JSONDecodeError as exc:
        raise FinalDeliveryError("Données autonomes illisibles") from exc
    if not isinstance(payload, dict):
        raise FinalDeliveryError("Objet de données autonome attendu")
    return payload


def validate_delivery(path: Path) -> dict[str, Any]:
    output = path.resolve()
    manifest_path = manifest_path_for(output)
    if not output.is_file() or not manifest_path.is_file():
        raise FinalDeliveryError("HTML ou manifeste de livraison absent")
    manifest = read_json(manifest_path)
    signature = verify_signature(
        manifest, "delivery_signature", label="manifeste de livraison"
    )
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "complete_validated"
        or manifest.get("offline_single_file") is not True
        or int(manifest.get("view_count") or -1) != 3
        or manifest.get("output_html") != output.name
        or int(manifest.get("output_html_bytes") or -1) != output.stat().st_size
        or manifest.get("output_html_sha256") != sha256_file(output)
    ):
        raise FinalDeliveryError("Manifeste de livraison incohérent")
    try:
        document = output.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FinalDeliveryError("HTML de livraison illisible") from exc
    payload = _embedded_payload(document)
    package = payload.get("package")
    if (
        payload.get("schemaVersion") != SCHEMA_VERSION
        or int(payload.get("viewCount") or -1) != 3
        or not isinstance(package, Mapping)
        or int(package.get("htmlBytes") or -1) != output.stat().st_size
        or int(package.get("campaignResultCount") or -1) != EXPECTED_CAMPAIGN_ROWS
        or stable_sha256(payload) != manifest.get("payload_sha256")
        or document.count('class="view') != 3
        or "https://" in document.casefold()
        or "http://" in document.casefold()
    ):
        raise FinalDeliveryError("Contenu autonome incohérent")
    scope = manifest.get("scientific_scope")
    if (
        not isinstance(scope, Mapping)
        or int(scope.get("campaign_result_count") or -1) != EXPECTED_CAMPAIGN_ROWS
        or scope.get("mechanisms_kept_separate") is not True
        or scope.get("curve_downsampling_applied") is not False
        or scope.get("historical_incident_probability_estimated") is not False
        or scope.get("automatic_targeted_control_active") is not False
        or scope.get("forced_top_three") is not False
    ):
        raise FinalDeliveryError("Périmètre scientifique de livraison incohérent")
    return {
        "valid": True,
        "path": str(output),
        "manifest_path": str(manifest_path),
        "delivery_signature": signature,
        "sha256": manifest["output_html_sha256"],
        "bytes": manifest["output_html_bytes"],
        "view_count": 3,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Construire la livraison autonome")
    build.add_argument("--campaign-root", type=Path, required=True)
    build.add_argument("--results-dir", type=Path, required=True)
    build.add_argument("--curves-dir", type=Path)
    build.add_argument("--lot-replay-root", type=Path)
    build.add_argument("--target-registry", type=Path)
    build.add_argument("--dashboard-html", type=Path)
    build.add_argument("--action-results-root", type=Path)
    build.add_argument("--legacy-risk-html", type=Path)
    build.add_argument("--legacy-control-html", type=Path)
    build.add_argument("--output-html", type=Path, required=True)
    validate = subparsers.add_parser("validate", help="Valider HTML et manifeste")
    validate.add_argument("--path", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "build":
            result = build_delivery(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                curves_dir=args.curves_dir,
                replay_root=args.lot_replay_root,
                target_registry_path=args.target_registry,
                dashboard_html=args.dashboard_html,
                action_results_root=args.action_results_root,
                legacy_risk_html=args.legacy_risk_html,
                legacy_control_html=args.legacy_control_html,
                output_html=args.output_html,
            )
        else:
            result = validate_delivery(args.path)
    except (FinalDeliveryError, FileExistsError) as exc:
        print(f"LIVRAISON V4 NON PRODUITE : {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
