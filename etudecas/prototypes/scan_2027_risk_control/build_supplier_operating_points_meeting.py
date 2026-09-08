#!/usr/bin/env python3
"""Build one offline meeting HTML for supplier robustness across operating points.

The input is a compact per-run CSV.  The page deliberately focuses on one
decision question: do the same supplier lanes remain vulnerable, for the same
physical incident, when the overall supply service moves from fluid to tense
and degraded conditions?

Nothing is inferred from an absent run.  The builder requires a complete
supplier x incident x operating-point matrix; each cell exposes its own number
of repetitions so a one-pass exploratory screen cannot look statistically
confirmed.  The full network map is embedded as a deferred ``srcdoc`` payload
so the output remains a single, offline HTML without changing the source map.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "etudecas.supplier_operating_points_meeting.v1"
DEFAULT_RESULTS_FILE = "supplier_operating_point_comparison.csv"
EXPECTED_POINT_IDS = ("op_100", "op_93", "op_80")
EXPECTED_CHAIN_COUNT = 18
EXPECTED_MECHANISMS = {"delay": 120.0, "availability": 0.5}
EXPECTED_ROW_COUNT = len(EXPECTED_POINT_IDS) * EXPECTED_CHAIN_COUNT * len(EXPECTED_MECHANISMS)
EXPOSURE_TIE_TOLERANCE_PP = 0.005
FORBIDDEN_BUSINESS_BRANCHES = (
    "quality_hold",
    "quality delay",
    "quality_delay",
    "quarantine",
    "retenue qualite",
    "retenue qualité",
    "release qualite",
    "release qualité",
    'mode === "quality"',
    "mode === 'quality'",
    "mode==='quality'",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _float(value: Any, *, field: str) -> float:
    try:
        result = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite numeric value for {field}: {value!r}")
    return result


def _optional_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _float(text, field="optional metric")


def _first(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def _rate(value: Any, *, field: str) -> float:
    result = _float(value, field=field)
    if result > 1.0 + 1e-9:
        result /= 100.0
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"Rate outside [0, 1] for {field}: {value!r}")
    return result


def _truthy(value: Any, *, default: bool = False) -> bool:
    text = str(value or "").strip().casefold()
    if not text:
        return default
    if text in {"true", "1", "yes", "oui"}:
        return True
    if text in {"false", "0", "no", "non"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_mechanism(value: str) -> tuple[str, str]:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    labels = {
        "transport_delay": "Retard d'approvisionnement (+120 jours)",
        "lead_time": "Retard d'approvisionnement (+120 jours)",
        "lead_time_extra_days": "Retard d'approvisionnement (+120 jours)",
        "delay": "Retard d'approvisionnement (+120 jours)",
        "supply_availability": "Disponibilité fournisseur réduite de moitié",
        "availability": "Disponibilité fournisseur réduite de moitié",
        "availability_multiplier": "Disponibilité fournisseur réduite de moitié",
    }
    if key not in labels:
        raise ValueError(f"Unsupported incident mechanism: {value!r}")
    canonical = "delay" if key in {"transport_delay", "lead_time", "lead_time_extra_days", "delay"} else "availability"
    return canonical, labels[key]


def _normalise_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        raw_text = json.dumps(row, ensure_ascii=False).lower()
        if any(term in raw_text for term in FORBIDDEN_BUSINESS_BRANCHES):
            raise ValueError(f"Excluded business branch found at CSV row {index}")
        point_id = _first(row, "operating_point_id", "regime_id", "state_id")
        point_label = _first(row, "operating_point_label", "regime_label", "state_label")
        supplier_id = _first(row, "supplier_id", "supplier")
        item_id = _first(row, "item_id", "component_id", "article_id")
        factory_id = _first(row, "factory_id", "dst_node_id", "destination_id")
        product_id = _first(row, "product_id", "target_product_id")
        chain_id = _first(row, "chain_id", "lane_id") or "|".join(
            (supplier_id, item_id, factory_id)
        )
        seed_text = _first(row, "seed", "random_seed")
        mechanism_raw = _first(row, "incident_mechanism", "mechanism", "risk_type")
        if not all((point_id, point_label, supplier_id, item_id, factory_id, product_id, seed_text, mechanism_raw)):
            raise ValueError(f"Missing identity field at CSV row {index}")
        mechanism, mechanism_label = _normalise_mechanism(mechanism_raw)
        incident_value_text = _first(row, "incident_value", "mechanism_value")
        if not incident_value_text:
            raise ValueError(f"Missing incident_value at CSV row {index}")
        incident_value = _float(incident_value_text, field="incident_value")
        expected_incident_value = EXPECTED_MECHANISMS[mechanism]
        if not math.isclose(
            incident_value,
            expected_incident_value,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"Unexpected {mechanism} incident value at CSV row {index}: "
                f"expected {expected_incident_value}, found {incident_value}"
            )
        exercised_value = row.get("incident_physically_exercised")
        if exercised_value is None or not str(exercised_value).strip():
            raise ValueError(
                "Missing incident_physically_exercised trace field "
                f"at CSV row {index}"
            )
        baseline_service = _rate(
            _first(row, "baseline_service", "baseline_target_service", "paired_baseline_service"),
            field="baseline_service",
        )
        incident_service = _rate(
            _first(row, "incident_service", "target_service", "stress_service"),
            field="incident_service",
        )
        global_service = _rate(
            _first(row, "realized_global_on_due", "global_on_due", "operating_point_service"),
            field="realized_global_on_due",
        )
        loss_value = _optional_float(_first(row, "service_loss_pp", "target_service_loss_pp"))
        signed_service_loss_pp = (
            loss_value
            if loss_value is not None
            else (baseline_service - incident_service) * 100.0
        )
        service_loss_pp = max(0.0, signed_service_loss_pp)
        baseline_global_service = _optional_float(row.get("baseline_global_service"))
        if baseline_global_service is None:
            baseline_global_service = global_service
        elif baseline_global_service > 1.0 + 1e-9:
            baseline_global_service /= 100.0
        incident_global_service = _optional_float(row.get("incident_global_service"))
        if incident_global_service is not None and incident_global_service > 1.0 + 1e-9:
            incident_global_service /= 100.0
        global_loss_value = _optional_float(row.get("global_service_loss_pp"))
        signed_global_service_loss_pp = (
            global_loss_value
            if global_loss_value is not None
            else (
                (baseline_global_service - incident_global_service) * 100.0
                if incident_global_service is not None
                else signed_service_loss_pp
            )
        )
        global_service_loss_pp = max(0.0, signed_global_service_loss_pp)
        normalised.append(
            {
                "operating_point_id": point_id,
                "operating_point_label": point_label,
                "realized_global_on_due": global_service,
                "realized_268091_on_due": _optional_float(row.get("realized_268091_on_due")),
                "realized_268967_on_due": _optional_float(row.get("realized_268967_on_due")),
                "degradation_family": _first(row, "degradation_family", "operating_point_family"),
                "degradation_value": _first(row, "degradation_value", "operating_point_value"),
                "supplier_id": supplier_id,
                "chain_id": chain_id,
                "item_id": item_id,
                "factory_id": factory_id,
                "product_id": product_id,
                "incident_mechanism": mechanism,
                "incident_label": mechanism_label,
                "incident_value": incident_value,
                "seed": int(seed_text),
                "baseline_service": baseline_service,
                "incident_service": incident_service,
                "service_loss_pp": service_loss_pp,
                "signed_service_loss_pp": signed_service_loss_pp,
                "baseline_global_service": baseline_global_service,
                "incident_global_service": incident_global_service,
                "global_service_loss_pp": global_service_loss_pp,
                "signed_global_service_loss_pp": signed_global_service_loss_pp,
                "risk_applied_row_count": int(
                    _optional_float(row.get("risk_applied_row_count")) or 0
                ),
                "risk_applied_event_count": int(
                    _optional_float(row.get("risk_applied_event_count")) or 0
                ),
                "incident_physically_exercised": _truthy(exercised_value),
                "backlog_qty_days_delta": _optional_float(row.get("backlog_qty_days_delta")),
                "production_delta": _optional_float(row.get("production_delta")),
                "status": _first(row, "status") or "executed",
            }
        )
    return normalised


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return statistics.fmean(clean) if clean else None


def _degradation_description(family: str, value: str) -> str:
    labels = {
        "baseline": "Référence simulée sans mise en tension supplémentaire",
        "supplier_planned_lead": "Délai nominal ajouté à toutes les voies fournisseurs",
        "supplier_nominal_delivery_reliability": "Fiabilité nominale commune des voies fournisseurs",
        "supplier_capacity_identified": "Capacité des deux voies fournisseurs quantifiées",
        "finished_factory_capacity": "Capacité disponible dans les usines de produits finis",
        "customer_demand_load": "Niveau de demande client appliqué au réseau",
    }
    label = labels.get(family, family.replace("_", " ") or "Référence simulée")
    return f"{label} · réglage {value}" if value else label


def _sensitivity_cliff(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    rows = _read_csv(path.resolve())
    family_labels = {
        "supplier_capacity_identified": "capacité des deux voies fournisseurs quantifiées",
        "supplier_planned_lead": "délai nominal commun des voies fournisseurs",
        "supplier_nominal_delivery_reliability": "fiabilité nominale des livraisons fournisseurs",
        "finished_factory_capacity": "capacité des usines de produits finis",
        "customer_demand_load": "charge de demande client",
    }
    candidates: list[dict[str, Any]] = []
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        family = _first(row, "family", "degradation_family")
        value = _optional_float(_first(row, "parameter_value", "degradation_value"))
        service = _optional_float(_first(row, "system_on_due_service", "realized_global_on_due"))
        if family and value is not None and service is not None:
            by_family[family].append(
                {
                    "family": family,
                    "value": value,
                    "service": service,
                    "service_268091": _optional_float(row.get("on_due_service_268091")),
                    "service_268967": _optional_float(row.get("on_due_service_268967")),
                }
            )
    for family, family_rows in by_family.items():
        ordered = sorted(family_rows, key=lambda row: float(row["value"]), reverse=True)
        for first, second in zip(ordered, ordered[1:]):
            width = abs(float(first["value"]) - float(second["value"]))
            drop = abs(float(first["service"]) - float(second["service"]))
            if width > 1e-12 and drop > 1e-12:
                candidates.append(
                    {
                        "family": family,
                        "family_label": family_labels.get(
                            family, family.replace("_", " ")
                        ),
                        "from_value": first["value"],
                        "to_value": second["value"],
                        "from_service": first["service"],
                        "to_service": second["service"],
                        "to_service_268091": second["service_268091"],
                        "to_service_268967": second["service_268967"],
                        "local_slope": drop / width,
                    }
                )
    return max(candidates, key=lambda row: float(row["local_slope"])) if candidates else None


def _summarise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("Comparison CSV is empty")
    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            "The meeting screen requires exactly "
            f"{EXPECTED_ROW_COUNT} rows (3 operating points x 18 lanes x 2 incidents); "
            f"found {len(rows)}"
        )
    point_order: list[str] = []
    point_meta: dict[str, dict[str, Any]] = {}
    chains: dict[str, dict[str, str]] = {}
    mechanisms: dict[str, str] = {}
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    unique_run_keys: set[tuple[str, str, str, int]] = set()
    for row in rows:
        point_id = str(row["operating_point_id"])
        if point_id not in point_meta:
            point_order.append(point_id)
            point_meta[point_id] = {
                "id": point_id,
                "label": row["operating_point_label"],
                "global_service": {},
                "service_268091": {},
                "service_268967": {},
                "degradation_family": row["degradation_family"],
                "degradation_value": row["degradation_value"],
            }
        seed = int(row["seed"])
        for field, value in (
            ("global_service", row["realized_global_on_due"]),
            ("service_268091", row["realized_268091_on_due"]),
            ("service_268967", row["realized_268967_on_due"]),
        ):
            previous = point_meta[point_id][field].get(seed)
            if previous is not None and value is not None and abs(float(previous) - float(value)) > 1e-9:
                raise ValueError(
                    f"Inconsistent {field} for operating point {point_id}, seed {seed}"
                )
            if previous is None or value is not None:
                point_meta[point_id][field][seed] = value
        chain_id = str(row["chain_id"])
        chain_identity = {
            "chain_id": chain_id,
            "supplier_id": str(row["supplier_id"]),
            "item_id": str(row["item_id"]),
            "factory_id": str(row["factory_id"]),
            "product_id": str(row["product_id"]),
        }
        if chain_id in chains and chains[chain_id] != chain_identity:
            raise ValueError(f"Inconsistent physical identity for lane {chain_id}")
        chains[chain_id] = chain_identity
        mechanisms[str(row["incident_mechanism"])] = str(row["incident_label"])
        run_key = (
            point_id,
            chain_id,
            str(row["incident_mechanism"]),
            int(row["seed"]),
        )
        if run_key in unique_run_keys:
            raise ValueError(f"Duplicate operating-point incident row: {run_key}")
        unique_run_keys.add(run_key)
        groups[(point_id, chain_id, str(row["incident_mechanism"]))].append(row)

    if set(point_order) != set(EXPECTED_POINT_IDS):
        raise ValueError(
            "Expected operating points "
            f"{list(EXPECTED_POINT_IDS)}, found {sorted(point_order)}"
        )
    if len(chains) != EXPECTED_CHAIN_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_CHAIN_COUNT} distinct supplier lanes, found {len(chains)}"
        )
    if set(mechanisms) != set(EXPECTED_MECHANISMS):
        raise ValueError(
            "Expected exactly the delay and availability incident mechanisms; "
            f"found {sorted(mechanisms)}"
        )
    expected = {
        (point, supplier, mechanism)
        for point in EXPECTED_POINT_IDS
        for supplier in chains
        for mechanism in EXPECTED_MECHANISMS
    }
    missing = sorted(expected.difference(groups))
    extra = sorted(set(groups).difference(expected))
    if missing or extra:
        raise ValueError(
            "Incomplete operating-point matrix; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    seed_sets = {
        key: {int(row["seed"]) for row in group}
        for key, group in groups.items()
    }
    reference_seed_set = seed_sets[next(iter(sorted(seed_sets)))]
    mismatched_seed_sets = [
        key for key, seed_set in seed_sets.items() if seed_set != reference_seed_set
    ]
    if mismatched_seed_sets:
        raise ValueError(
            "All 108 cells must use the same paired seed set; mismatches include "
            f"{sorted(mismatched_seed_sets)[:5]}"
        )
    if len(reference_seed_set) != 1:
        raise ValueError(
            "The 108-row preliminary screen requires exactly one common seed per cell; "
            f"found {sorted(reference_seed_set)}"
        )

    points = []
    for point_id in point_order:
        meta = point_meta[point_id]
        points.append(
            {
                "id": point_id,
                "label": meta["label"],
                "global_service": _mean(meta["global_service"].values()),
                "service_268091": _mean(meta["service_268091"].values()),
                "service_268967": _mean(meta["service_268967"].values()),
                "degradation_family": meta["degradation_family"],
                "degradation_value": meta["degradation_value"],
                "degradation_description": _degradation_description(
                    str(meta["degradation_family"]), str(meta["degradation_value"])
                ),
            }
        )
    points.sort(key=lambda point: float(point["global_service"]), reverse=True)
    for point in points:
        service = float(point["global_service"])
        point["label"] = (
            "Réseau fluide"
            if service >= 0.98
            else "Réseau sous tension"
            if service >= 0.85
            else "Réseau fragile"
        )
        product_values = [
            float(value)
            for value in (point["service_268091"], point["service_268967"])
            if value is not None
        ]
        point["product_gap_pp"] = (
            (max(product_values) - min(product_values)) * 100.0
            if len(product_values) == 2
            else None
        )
    point_order = [str(point["id"]) for point in points]

    cells: list[dict[str, Any]] = []
    for key, group in groups.items():
        point_id, chain_id, mechanism = key
        exercised = [row for row in group if bool(row["incident_physically_exercised"])]
        losses = [float(row["service_loss_pp"]) for row in exercised]
        global_losses = [float(row["global_service_loss_pp"]) for row in exercised]
        cells.append(
            {
                **chains[chain_id],
                "operating_point_id": point_id,
                "incident_mechanism": mechanism,
                "incident_label": mechanisms[mechanism],
                "run_count": len(group),
                "seed_count": len({int(row["seed"]) for row in group}),
                "exercised_seed_count": len({int(row["seed"]) for row in exercised}),
                "incident_physically_exercised": bool(exercised),
                "mean_service_loss_pp": statistics.fmean(losses) if losses else None,
                "median_service_loss_pp": statistics.median(losses) if losses else None,
                "min_service_loss_pp": min(losses) if losses else None,
                "max_service_loss_pp": max(losses) if losses else None,
                "mean_global_service_loss_pp": statistics.fmean(global_losses) if global_losses else None,
                "min_global_service_loss_pp": min(global_losses) if global_losses else None,
                "max_global_service_loss_pp": max(global_losses) if global_losses else None,
                "mean_baseline_service": _mean(float(row["baseline_service"]) for row in exercised),
                "mean_incident_service": _mean(float(row["incident_service"]) for row in exercised),
                "mean_baseline_global_service": _mean(float(row["baseline_global_service"]) for row in exercised),
                "mean_incident_global_service": _mean(row["incident_global_service"] for row in exercised),
                "mean_backlog_qty_days_delta": _mean(row["backlog_qty_days_delta"] for row in exercised),
                "mean_production_delta": _mean(row["production_delta"] for row in exercised),
                "non_exercised_seed_count": len(group) - len(exercised),
            }
        )

    aggregate: dict[tuple[str, str], float | None] = {}
    for point_id in point_order:
        for chain_id in chains:
            values = [
                float(cell["mean_service_loss_pp"])
                for cell in cells
                if cell["operating_point_id"] == point_id and cell["chain_id"] == chain_id
                and cell["mean_service_loss_pp"] is not None
            ]
            # "Toutes les hypothèses" means the worst measured effect among the
            # two controlled stresses, not an average or an occurrence probability.
            aggregate[(point_id, chain_id)] = max(values) if values else None
    ranks: dict[tuple[str, str], int] = {}
    for point_id in point_order:
        ordered = sorted(
            (
                chain
                for chain in chains
                if aggregate[(point_id, chain)] is not None
                and float(aggregate[(point_id, chain)]) > 1e-9
            ),
            key=lambda chain: (-float(aggregate[(point_id, chain)]), chain),
        )
        previous: float | None = None
        position = 0
        for index, chain in enumerate(ordered, start=1):
            value = float(aggregate[(point_id, chain)])
            if previous is None or abs(previous - value) > EXPOSURE_TIE_TOLERANCE_PP:
                position = index
            ranks[(point_id, chain)] = position
            previous = value
    for cell in cells:
        cell["chain_exposure_position_in_state"] = ranks.get(
            (cell["operating_point_id"], cell["chain_id"])
        )

    top3_by_point = {
        point_id: [
            chain
            for chain in sorted(
                chains,
                key=lambda item: (ranks.get((point_id, item), 999), item),
            )
            if ranks.get((point_id, chain), 999) <= 3
        ]
        for point_id in point_order
    }
    stable_top3 = sorted(set.intersection(*(set(value) for value in top3_by_point.values())))
    dominant: dict[tuple[str, str], str] = {}
    for point_id in point_order:
        for chain in chains:
            subset = [
                cell for cell in cells
                if cell["operating_point_id"] == point_id and cell["chain_id"] == chain
                and cell["mean_service_loss_pp"] is not None
                and float(cell["mean_service_loss_pp"]) > 1e-9
            ]
            if not subset:
                dominant[(point_id, chain)] = "none"
                continue
            best = max(float(cell["mean_service_loss_pp"]) for cell in subset)
            winners = [
                cell
                for cell in subset
                if abs(float(cell["mean_service_loss_pp"]) - best)
                <= EXPOSURE_TIE_TOLERANCE_PP
            ]
            dominant[(point_id, chain)] = (
                str(winners[0]["incident_mechanism"])
                if len(winners) == 1
                else "tie"
            )
    stable_cause = {
        chain: (
            not {"not_exercised", "none", "tie"}.intersection(
                {dominant[(point, chain)] for point in point_order}
            )
            and len({dominant[(point, chain)] for point in point_order}) == 1
        )
        for chain in chains
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "operating_points": points,
        "chains": list(chains.values()),
        "supplier_count": len({chain["supplier_id"] for chain in chains.values()}),
        "mechanisms": [{"id": key, "label": value} for key, value in mechanisms.items()],
        "cells": cells,
        "paired_seed_ids": sorted(reference_seed_set),
        "top3_by_operating_point": top3_by_point,
        "stable_top3": stable_top3,
        "stable_cause": stable_cause,
        "dominant_cause": {f"{point}|{chain}": value for (point, chain), value in dominant.items()},
    }


def _json_for_script(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _load_state_cascade_summary(cascade_html: Path) -> dict[str, Any]:
    """Load and validate the published four-trajectory cascade paired with the HTML."""

    summary_path = cascade_html.parent / "state_cascade_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(
            f"The cascade HTML must be accompanied by {summary_path.name}: {cascade_html}"
        )
    source = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if source.get("status") != "complete":
        raise ValueError("The state-dependent cascade summary is not complete")
    expected_cases = {
        "state_off_nominal": False,
        "delay_only_state_off": False,
        "state_only": True,
        "state_plus_delay": True,
    }
    metrics = source.get("metrics")
    metrics_path: Path | None = None
    if not isinstance(metrics, list):
        files = source.get("files")
        metrics_reference = files.get("metrics") if isinstance(files, Mapping) else None
        if not metrics_reference:
            raise ValueError("The state-dependent cascade summary has no metrics source")
        metrics_path = (cascade_html.parent / str(metrics_reference)).resolve()
        try:
            metrics_path.relative_to(cascade_html.parent.resolve())
        except ValueError as exc:
            raise ValueError("Cascade metrics must stay inside the cascade package") from exc
        if not metrics_path.is_file():
            raise FileNotFoundError(metrics_path)
        metrics = _read_csv(metrics_path)
    by_case = {
        str(row.get("case")): row
        for row in metrics
        if isinstance(row, Mapping) and row.get("case")
    }
    if set(by_case) != set(expected_cases):
        raise ValueError(
            "The meeting cascade must contain exactly the four expected trajectories; "
            f"found {sorted(by_case)}"
        )
    seeds = {int(row["seed"]) for row in by_case.values()}
    if len(seeds) != 1:
        raise ValueError(f"The four cascade trajectories are not paired: seeds={sorted(seeds)}")
    for case, state_enabled in expected_cases.items():
        if _truthy(by_case[case].get("state_dependent_rules_enabled")) is not state_enabled:
            raise ValueError(f"Unexpected dynamic-rule state for cascade case {case}")

    pair_results = source.get("pair_results")
    if not isinstance(pair_results, Mapping):
        raise ValueError("The state-dependent cascade summary has no pair_results")
    required = (
        "service_loss_points_state_off",
        "service_loss_points_state_on",
        "service_loss_amplification_points",
        "backlog_amplification_qty_days",
        "production_loss_amplification_qty",
        "finished_product_lots_with_primary_or_incremental_signal_ancestry",
    )
    values: dict[str, float | int] = {}
    for field in required:
        value = pair_results.get(field)
        if value is None:
            raise ValueError(f"Missing cascade metric: {field}")
        numeric = _float(value, field=field)
        values[field] = (
            int(numeric)
            if field == "finished_product_lots_with_primary_or_incremental_signal_ancestry"
            else numeric
        )
    expected_amplification = (
        float(values["service_loss_points_state_on"])
        - float(values["service_loss_points_state_off"])
    )
    if not math.isclose(
        float(values["service_loss_amplification_points"]),
        expected_amplification,
        rel_tol=0.0,
        abs_tol=1e-5,
    ):
        raise ValueError("Inconsistent service amplification in cascade summary")
    return {
        "source_file": summary_path.name,
        "source_sha256": _sha256(summary_path),
        "metrics_source_file": (
            str(metrics_path.relative_to(cascade_html.parent.resolve()))
            if metrics_path is not None
            else "inline"
        ),
        "metrics_source_sha256": _sha256(metrics_path) if metrics_path is not None else None,
        "seed": next(iter(seeds)),
        **values,
    }


def _validate_current_campaign_manifest(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    *,
    paired_seed_ids: Sequence[int],
) -> None:
    """Fail closed unless the published matrix proves one comparable engine generation."""

    if not manifest_path.is_file():
        raise FileNotFoundError(
            "A complete campaign_manifest.json is required beside the 108-row matrix"
        )
    if manifest.get("status") != "complete":
        raise ValueError("The operating-point campaign manifest is not complete")
    if manifest.get("same_engine_for_all_108_rows") is not True:
        raise ValueError(
            "Refusing a three-state comparison without "
            "same_engine_for_all_108_rows=true"
        )
    if int(manifest.get("detail_row_count") or -1) != EXPECTED_ROW_COUNT:
        raise ValueError("Campaign manifest does not certify exactly 108 detail rows")
    if int(manifest.get("lane_count") or -1) != EXPECTED_CHAIN_COUNT:
        raise ValueError("Campaign manifest does not certify exactly 18 supplier lanes")
    counts = manifest.get("row_count_by_operating_point")
    expected_per_point = EXPECTED_CHAIN_COUNT * len(EXPECTED_MECHANISMS)
    if not isinstance(counts, Mapping) or {
        str(key): int(value) for key, value in counts.items()
    } != {point: expected_per_point for point in EXPECTED_POINT_IDS}:
        raise ValueError("Campaign manifest has an invalid 36/36/36 point breakdown")
    raw_mechanisms = manifest.get("incident_mechanisms")
    if not isinstance(raw_mechanisms, list):
        raise ValueError("Campaign manifest does not list the two incident mechanisms")
    canonical_mechanisms = {
        _normalise_mechanism(str(mechanism))[0] for mechanism in raw_mechanisms
    }
    if canonical_mechanisms != set(EXPECTED_MECHANISMS):
        raise ValueError("Campaign manifest does not certify delay and availability")
    if [int(seed) for seed in manifest.get("seed_ids") or []] != list(paired_seed_ids):
        raise ValueError("Campaign manifest seed list does not match every matrix cell")
    if manifest.get("quality_branch_included") is not False:
        raise ValueError("Campaign manifest must explicitly exclude the quality branch")
    engine_sha = str(manifest.get("engine_sha256") or "")
    if len(engine_sha) != 64 or any(character not in "0123456789abcdefABCDEF" for character in engine_sha):
        raise ValueError("Campaign manifest has no valid engine SHA-256")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RESILIENCE-SCAN — démonstration fournisseurs</title>
<style>
:root{--navy:#092747;--blue:#1768e5;--sky:#eaf3ff;--green:#16845b;--amber:#d78114;--red:#cb372d;--ink:#12273d;--muted:#60748a;--line:#d9e4ef;--paper:#f5f8fc;--shadow:0 10px 34px #17375e16}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif}header{background:linear-gradient(115deg,#082643,#114a7b);color:#fff;padding:22px clamp(18px,4vw,54px)}header .overline{font-size:12px;font-weight:900;letter-spacing:.13em;color:#9fd2ff}header h1{font-size:clamp(28px,4vw,48px);line-height:1.05;margin:7px 0 9px}header p{max-width:1050px;margin:0;color:#d8e9f8;font-size:17px;line-height:1.5}.meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.meta span{padding:6px 9px;border:1px solid #ffffff45;border-radius:999px;font-size:12px;background:#ffffff12}.route{position:sticky;top:0;z-index:20;display:flex;gap:8px;padding:10px clamp(18px,4vw,54px);background:#f8fbffec;backdrop-filter:blur(9px);border-bottom:1px solid var(--line)}.route button{border:1px solid #b8cbe0;border-radius:999px;background:#fff;padding:10px 15px;font-weight:850;color:#21425f;cursor:pointer}.route button.active{background:var(--navy);border-color:var(--navy);color:#fff}main{max-width:1320px;margin:auto;padding:20px clamp(14px,3vw,34px) 54px}.view{display:none}.view.active{display:block}.question{background:#fff;border:1px solid var(--line);border-left:7px solid var(--blue);border-radius:16px;padding:17px 19px;box-shadow:var(--shadow);margin:0 0 15px}.question b{display:block;font-size:20px;margin-bottom:5px}.plain-grid,.point-grid,.cause-grid,.metric-grid{display:grid;gap:12px}.plain-grid{grid-template-columns:repeat(4,1fr)}.plain,.point,.cause,.metric{background:#fff;border:1px solid var(--line);border-radius:14px;padding:15px;box-shadow:var(--shadow)}.plain b{display:block;font-size:12px;color:var(--blue);letter-spacing:.07em;margin-bottom:5px}.plain p,.point p,.cause p{margin:0;color:var(--muted);line-height:1.4}.point-grid{grid-template-columns:repeat(3,1fr);margin:15px 0}.point .rate{font-size:35px;font-weight:950;color:var(--navy)}.point h3{margin:5px 0}.point small{display:block;margin-top:8px;color:var(--muted)}section{margin:15px 0;background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow)}section h2{margin:0 0 5px;font-size:23px}section>p{margin:0 0 13px;color:var(--muted);line-height:1.45}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.toolbar button,.toolbar select{border:1px solid #b9cbe0;border-radius:9px;background:#fff;padding:8px 11px;color:var(--ink);font-weight:750}.toolbar button.active{background:var(--blue);color:#fff;border-color:var(--blue)}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px}table{border-collapse:collapse;width:100%;min-width:900px}th,td{padding:10px 11px;border-bottom:1px solid #e4ebf2;text-align:left;vertical-align:middle}th{background:#edf4fb;color:#173b60;font-size:12px;position:sticky;top:0}td{font-size:13px}.rank{display:inline-grid;place-items:center;width:25px;height:25px;border-radius:50%;background:#e7f0ff;color:#1555ad;font-weight:900}.loss{font-weight:900;font-variant-numeric:tabular-nums}.bar-track{width:130px;height:8px;border-radius:9px;background:#e5edf5;overflow:hidden;margin-top:4px}.bar{height:100%;background:linear-gradient(90deg,#f2a01d,#c8302b)}.yes{color:var(--green);font-weight:900}.no{color:var(--amber);font-weight:900}.finding{padding:15px;border-radius:13px;background:#ecf8f3;border:1px solid #acd9c6;line-height:1.45}.finding.warn{background:#fff6e8;border-color:#ebc382}.cause-grid{grid-template-columns:repeat(2,1fr)}.cause{border-top:5px solid var(--blue)}.cause h3{margin:0 0 7px}.chain{display:flex;gap:8px;align-items:stretch;overflow:auto;padding:8px 0 15px}.step{min-width:155px;flex:1;background:#f7faff;border:1px solid #cfdeed;border-radius:12px;padding:13px}.step b{display:block;color:#114c87;margin-bottom:4px}.arrow{display:grid;place-items:center;color:var(--blue);font-size:24px}.metric-grid{grid-template-columns:repeat(4,1fr)}.metric strong{display:block;font-size:25px;color:var(--navy)}.metric span{font-size:12px;color:var(--muted)}.map-shell{height:72vh;min-height:560px;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#eaf1f8;position:relative}.map-shell iframe{width:100%;height:100%;border:0;background:#fff}.map-loading{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted);font-weight:800}.map-guide{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.map-guide span{background:#eaf3ff;color:#155197;border-radius:999px;padding:7px 10px;font-weight:800;font-size:12px}.limits{font-size:13px;color:#5c6d7e}.footer{margin-top:20px;color:#60748a;font-size:12px}.hidden{display:none!important}@media(max-width:900px){.plain-grid,.point-grid,.metric-grid{grid-template-columns:1fr 1fr}.cause-grid{grid-template-columns:1fr}}@media(max-width:590px){.plain-grid,.point-grid,.metric-grid{grid-template-columns:1fr}.route{overflow:auto}.route button{white-space:nowrap}}@media print{.route{display:none}.view{display:block!important;break-before:page}.map-shell{height:600px}body{background:#fff}}
.rank-chart{width:100%;height:auto;min-height:330px;background:#fbfdff;border:1px solid #dbe6f0;border-radius:12px;margin:8px 0 14px}
</style></head><body>
<header><div class="overline">RESILIENCE-SCAN · DÉMONSTRATION INDUSTRIELLE</div><h1>Les mêmes chaînes fournisseur ressortent-elles quand le réseau se dégrade ?</h1><p>Les mêmes chaînes et les mêmes hypothèses d'incident sont rejouées dans trois états simulés du réseau. Le résultat décrit l'exposition calculée dans le modèle ; il reste à confirmer par des répétitions et par l'historique fournisseur.</p><div class="meta"><span id="run-meta"></span><span>Horizon : 720 jours simulés</span><span>Même demande et même état initial dans chaque comparaison</span><span>Document autonome et hors ligne</span></div></header>
<nav class="route" aria-label="Parcours de démonstration"><button class="active" data-view="v1">1 · Quelles chaînes ressortent ?</button><button data-view="v2">2 · Pourquoi et avec quels effets ?</button><button data-view="v3">3 · Explorer le simulateur complet</button></nav>
<main>
<div id="v1" class="view active">
  <div class="question"><b>Question posée au simulateur</b>Si le niveau de service global passe d'un fonctionnement fluide à environ 93 %, puis 80 %, est-ce que les mêmes chaînes fournisseur ressortent — et est-ce pour la même cause physique ?</div>
  <div class="plain-grid"><article class="plain"><b>OBSERVÉ</b><p>Ce sont les données industrielles 2025 utilisées pour décrire le réseau, les articles, les stocks et les flux. Ce tableau ne prétend pas être un historique d'incidents.</p></article><article class="plain"><b>HYPOTHÈSE TESTÉE</b><p>On impose exactement le même retard ou la même baisse de disponibilité à chaque fournisseur candidat.</p></article><article class="plain"><b>CALCUL SIMULÉ</b><p>Le moteur propage l'incident vers le stock usine, la production, le retard client et le service.</p></article><article class="plain"><b>SIGNAL À INSTRUIRE</b><p>Un fournisseur qui ressort dans plusieurs états mérite une analyse achats et planification ; ce n'est pas une probabilité d'incident.</p></article></div>
  <div id="point-grid" class="point-grid"></div><div id="point-balance-warning" class="finding warn hidden"></div><div id="sensitivity-cliff" class="finding hidden"></div><div id="healthy-validation" class="finding hidden"></div>
  <section><h2>Comparaison descriptive à conditions identiques</h2><p>Le premier angle mesure la perte de service sur l'ensemble des deux produits, pondérée par la demande. Le second montre la perte du produit directement touché. En mode « toutes hypothèses », la page retient le pire effet parmi les deux hypothèses testées ; elle ne calcule ni leur fréquence ni une moyenne de risque.</p><div class="toolbar" id="metric-buttons"></div><div class="toolbar" id="mechanism-buttons"></div><svg id="rank-chart" class="rank-chart" viewBox="0 0 1040 430" role="img" aria-label="Ordre descriptif d'exposition des chaînes selon l'état du réseau"></svg><div class="table-wrap"><table><thead id="matrix-head"></thead><tbody id="matrix-body"></tbody></table></div></section>
  <section><h2>Réponse synthétique</h2><div id="stability-finding" class="finding"></div><p class="limits" id="sample-limit"></p></section>
  <section><h2>Analyse des risques fournisseurs : ce que cela signifie</h2><div class="cause-grid"><article class="cause"><h3>Déjà calculable</h3><p>Si un retard ou un manque survient, le simulateur estime dans le modèle où, quand et avec quelle ampleur il atteint les stocks, la production et le service client. C'est une estimation conditionnelle des conséquences.</p></article><article class="cause"><h3>À calibrer avec l'historique fournisseur</h3><p>La probabilité d'apparition et le délai d'alerte nécessitent les dates promises et reçues, les quantités confirmées et livrées, ainsi que les incidents réellement constatés. La page ne transforme pas une hypothèse en probabilité.</p></article></div></section>
</div>
<div id="v2" class="view">
  <div class="question"><b>Lecture métier</b>Le simulateur ne s'arrête pas à un score fournisseur : il montre par quelle chaîne physique l'écart atteint — ou n'atteint pas — le client.</div>
  <section><h2>Choisir une chaîne fournisseur</h2><div class="toolbar"><label for="supplier-select">Fournisseur / composant :</label><select id="supplier-select"></select></div><div id="chain" class="chain"></div><div class="cause-grid" id="cause-grid"></div></section>
  <section><h2>Effet selon l'état initial du réseau</h2><p>Une même perturbation peut être absorbée par les stocks dans un état fluide, puis devenir pénalisante lorsque les marges sont déjà consommées.</p><div class="table-wrap"><table><thead><tr><th>État du réseau avant incident</th><th>Hypothèse imposée</th><th>Service avant</th><th>Service après</th><th>Perte mesurée</th><th>Répétitions communes</th><th>Retard client cumulé ajouté</th><th>Production perdue</th></tr></thead><tbody id="detail-body"></tbody></table></div><p class="limits"><b>Retard client cumulé :</b> somme, jour après jour, des unités de commandes encore en retard ; plus ce nombre augmente, plus le manque est à la fois volumineux et durable.</p></section>
  <section><h2>Ce que cela permet concrètement</h2><div class="metric-grid"><article class="metric"><strong>1</strong><span>isoler le maillon qui transforme un incident en manque client</span></article><article class="metric"><strong>2</strong><span>séparer retard d'approvisionnement et quantité indisponible</span></article><article class="metric"><strong>3</strong><span>tester la robustesse du diagnostic à plusieurs niveaux de service</span></article><article class="metric"><strong>4</strong><span>préparer ensuite des actions pilotables sur les chaînes réellement exposées</span></article></div></section>
  <section id="cascade-section" class="hidden"><h2>Le réseau réagit à son propre état</h2><p>La démonstration V3 compare quatre trajectoires calculées avec la même demande et le même état initial : règles dépendantes de l'état activées ou désactivées, retard 338929 présent ou absent. Elle mesure séparément l'effet direct du retard et l'écart associé aux réactions dynamiques du modèle dans cette unique répétition.</p><div id="cascade-metrics" class="metric-grid"></div><p class="limits">Ces valeurs décrivent une répétition simulée. Les règles dynamiques sont des hypothèses à valider avec les équipes opérationnelles ; l'écart mesuré n'est ni une fréquence future ni une moyenne industrielle.</p><div class="toolbar"><button id="cascade-load">Afficher les quatre trajectoires de la cascade 338929</button></div><div id="cascade-shell" class="map-shell hidden"><div id="cascade-loading" class="map-loading">Chargement de la démonstration de cascade…</div><iframe id="cascade-frame" title="Cascade de risques dépendante de l'état"></iframe></div></section>
</div>
<div id="v3" class="view">
  <div class="question"><b>Parcours conseillé pendant la réunion</b>Ouvrir le fournisseur 338929, suivre sa chaîne vers M-1810 et le produit 268091, puis afficher les courbes de la simulation de référence et les hypothèses d'incident fournisseur.</div>
  <div class="map-guide"><span>1. Cliquer 338929</span><span>2. Ouvrir « Courbes du run nominal actuel »</span><span>3. Comparer stock, réceptions, production et commandes en retard</span><span>4. Ouvrir les risques simulés et la filiation des lots</span></div>
  <div class="map-shell"><div id="map-loading" class="map-loading">La carte complète sera chargée à l'ouverture de cette vue…</div><iframe id="map-frame" title="Carte complète autonome RESILIENCE-SCAN"></iframe></div>
  <p class="footer">La carte source a été copiée dans ce document ; ses onglets existants ne sont ni remplacés ni réécrits. Les nouvelles courbes sont additives.</p>
</div>
<p class="footer" id="provenance"></p>
</main>
<script id="meeting-data" type="application/json">__DATA__</script>
<script id="embedded-map" type="text/plain">__MAP_BASE64__</script>
<script id="embedded-cascade" type="text/plain">__CASCADE_BASE64__</script>
<script>
const data=JSON.parse(document.getElementById('meeting-data').textContent);let selectedMechanism='all',selectedMetric='global',mapLoaded=false,cascadeLoaded=false;
const EXPOSURE_TIE_TOLERANCE_PP=0.005;
const fmtPct=v=>v==null?'—':new Intl.NumberFormat('fr-FR',{minimumFractionDigits:1,maximumFractionDigits:2}).format(v*100)+' %';
const fmtPP=v=>v==null?'—':new Intl.NumberFormat('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v)+' pts';
const fmtQty=v=>v==null?'—':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}).format(v);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.getElementById('run-meta').textContent=`${data.paired_seed_ids.length} répétition commune à chaque cas · ${data.supplier_count} fournisseurs / ${data.chains.length} voies · ${data.mechanisms.length} hypothèses`;
document.getElementById('provenance').textContent=`Généré le ${new Date(data.generated_at_utc).toLocaleString('fr-FR')} · Résultats et carte intégrés dans ce fichier hors ligne`;
function pointCards(){document.getElementById('point-grid').innerHTML=data.operating_points.map(p=>`<article class="point"><div class="rate">${fmtPct(p.global_service)}</div><h3>${esc(p.label)}</h3><p>Part des unités rendues disponibles à la date demandée, avant l'hypothèse d'incident fournisseur.</p><small>${esc(p.degradation_description||'Référence simulée')} · Produit 268091 ${fmtPct(p.service_268091)} · Produit 268967 ${fmtPct(p.service_268967)}</small></article>`).join('');const uneven=data.operating_points.filter(p=>p.product_gap_pp>5);const warning=document.getElementById('point-balance-warning');warning.classList.toggle('hidden',!uneven.length);if(uneven.length)warning.innerHTML=`<b>Important :</b> ${uneven.map(p=>`${esc(p.label)} : écart ${fmtPP(p.product_gap_pp)} entre les deux produits`).join(' ; ')}. Le pourcentage global est une moyenne pondérée : cet état simulé n'est pas une disponibilité uniforme de chaque produit.`;const cliff=data.sensitivity_cliff,cliffNode=document.getElementById('sensitivity-cliff');cliffNode.classList.toggle('hidden',!cliff);if(cliff)cliffNode.innerHTML=`<b>Point de vigilance issu d'une simulation de sensibilité :</b> sur l'axe « ${esc(cliff.family_label)} », le réglage ${cliff.from_value} → ${cliff.to_value} accompagne un passage du service global de ${fmtPct(cliff.from_service)} à ${fmtPct(cliff.to_service)}. Cette discontinuité simulée doit être répétée et expliquée avant d'être considérée comme un seuil opérationnel.`;const hv=data.healthy_validation,hvNode=document.getElementById('healthy-validation');hvNode.classList.toggle('hidden',!hv);if(hv)hvNode.innerHTML=`<b>Contrôle complémentaire sur le réseau fluide :</b> ${hv.repetition_count} répétitions avaient fait ressortir un groupe d'exposition de ${hv.priority_group_supplier_ids.length} fournisseurs (${hv.priority_group_supplier_ids.map(esc).join(', ')}), sans confirmer un trio exact.${hv.same_engine_as_current===false?' Ce contrôle utilise une version antérieure du moteur : il reste séparé de la matrice à trois états.':''} La matrice ci-dessous utilise une seule version certifiée du moteur.`}
function mechanismButtons(){const root=document.getElementById('mechanism-buttons');root.innerHTML=`<b>Hypothèse :</b><button class="active" data-mech="all">Pire effet parmi les deux hypothèses</button>`+data.mechanisms.map(m=>`<button data-mech="${esc(m.id)}">${esc(m.label)}</button>`).join('');root.querySelectorAll('button').forEach(button=>button.onclick=()=>{selectedMechanism=button.dataset.mech;root.querySelectorAll('button').forEach(n=>n.classList.toggle('active',n===button));matrix()})}
function metricButtons(){const root=document.getElementById('metric-buttons');root.innerHTML='<b>Angle de décision :</b><button class="active" data-metric="global">Impact réseau pondéré</button><button data-metric="product">Impact sur le produit touché</button>';root.querySelectorAll('button').forEach(button=>button.onclick=()=>{selectedMetric=button.dataset.metric;root.querySelectorAll('button').forEach(n=>n.classList.toggle('active',n===button));matrix()})}
function cellFor(point,chain,mechanism){
  const rows=data.cells.filter(c=>c.operating_point_id===point&&c.chain_id===chain&&(mechanism==='all'||c.incident_mechanism===mechanism));
  const field=selectedMetric==='global'?'mean_global_service_loss_pp':'mean_service_loss_pp',minField=selectedMetric==='global'?'min_global_service_loss_pp':'min_service_loss_pp',maxField=selectedMetric==='global'?'max_global_service_loss_pp':'max_service_loss_pp';
  const valid=rows.filter(c=>c.incident_physically_exercised&&c[field]!=null);
  if(!valid.length)return {loss:null,min:null,max:null,n:0,total:rows[0]?.run_count??0,dominant:'not_exercised',dominantLabel:"Hypothèse non appliquée selon la trace moteur"};
  if(mechanism!=='all'){const chosen=valid[0];return {loss:chosen[field],min:chosen[minField],max:chosen[maxField],n:chosen.exercised_seed_count,total:chosen.run_count,dominant:chosen.incident_mechanism,dominantLabel:chosen.incident_label}}
  const best=Math.max(...valid.map(row=>row[field])),winners=valid.filter(row=>Math.abs(row[field]-best)<=EXPOSURE_TIE_TOLERANCE_PP),chosen=winners[0];
  const noLoss=best<=1e-9,tied=!noLoss&&winners.length>1;
  return {loss:best,min:chosen[minField],max:chosen[maxField],n:chosen.exercised_seed_count,total:chosen.run_count,dominant:noLoss?'none':tied?'tie':chosen.incident_mechanism,dominantLabel:noLoss?'Aucune perte mesurée':tied?'Effet indissociable des deux hypothèses':chosen.incident_label}
}
function drawRankChart(positionByPoint){
  const svg=document.getElementById('rank-chart'),colors=['#1768e5','#d43b31','#13875e','#8b5cf6','#d78114','#1d91b8'];
  const best=chain=>Math.min(...data.operating_points.map(p=>positionByPoint[p.id][chain]??999));
  const shown=[...data.chains].filter(c=>best(c.chain_id)<999).sort((a,b)=>best(a.chain_id)-best(b.chain_id)||a.chain_id.localeCompare(b.chain_id)).slice(0,6);
  const xs=data.operating_points.map((p,i)=>150+i*(620/Math.max(1,data.operating_points.length-1))),y=position=>70+(Math.min(7,position)-1)*45;
  let out='<rect width="1040" height="430" fill="#fbfdff"/>';
  data.operating_points.forEach((p,i)=>{out+=`<line x1="${xs[i]}" x2="${xs[i]}" y1="55" y2="350" stroke="#d8e3ee" stroke-dasharray="4 5"/><text x="${xs[i]}" y="31" text-anchor="middle" font-size="15" font-weight="800" fill="#173b60">${esc(p.label)}</text><text x="${xs[i]}" y="49" text-anchor="middle" font-size="12" fill="#60748a">${fmtPct(p.global_service)}</text>`});
  for(let position=1;position<=6;position++)out+=`<text x="92" y="${y(position)+5}" text-anchor="end" font-size="12" fill="#718398">position ${position}</text><line x1="105" x2="800" y1="${y(position)}" y2="${y(position)}" stroke="#edf1f6"/>`;
  shown.forEach((s,i)=>{const points=data.operating_points.map(p=>{const position=positionByPoint[p.id][s.chain_id];return position==null||position>6?y(7):y(position)}),poly=data.operating_points.map((p,j)=>`${xs[j]},${points[j]}`).join(' '),color=colors[i%colors.length];out+=`<polyline points="${poly}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>`;data.operating_points.forEach((p,j)=>out+=`<circle cx="${xs[j]}" cy="${points[j]}" r="5" fill="${color}"/>`);out+=`<line x1="830" x2="850" y1="${75+i*47}" y2="${75+i*47}" stroke="${color}" stroke-width="4"/><text x="860" y="${80+i*47}" font-size="13" font-weight="800" fill="#203b55">${esc(s.supplier_id)} · ${esc(s.item_id)}</text>`});
  out+='<text x="92" y="380" font-size="12" fill="#718398">Ordre descriptif d’une répétition ; les égalités à 0,01 point affiché partagent la même position.</text>';svg.innerHTML=out;
}
function matrix(){
  document.getElementById('matrix-head').innerHTML='<tr><th>Chaîne testée</th>'+data.operating_points.map(p=>`<th>${esc(p.label)}<br>${fmtPct(p.global_service)}</th>`).join('')+'<th>Dans les 3 premières positions partout ?</th><th>Même hypothèse la plus pénalisante ?</th></tr>';
  const numericLoss=value=>value==null?Number.NEGATIVE_INFINITY:value;
  const available=data.cells.map(c=>selectedMetric==='global'?c.mean_global_service_loss_pp:c.mean_service_loss_pp).filter(v=>v!=null);
  const max=Math.max(.01,...available),positionByPoint={};
  data.operating_points.forEach(p=>{
    positionByPoint[p.id]={};
    const ordered=[...data.chains].sort((a,b)=>numericLoss(cellFor(p.id,b.chain_id,selectedMechanism).loss)-numericLoss(cellFor(p.id,a.chain_id,selectedMechanism).loss)||a.chain_id.localeCompare(b.chain_id));
    let previous=null,position=0,validIndex=0;
    ordered.forEach(s=>{
      const loss=cellFor(p.id,s.chain_id,selectedMechanism).loss;
      if(loss==null||loss<=1e-9){positionByPoint[p.id][s.chain_id]=null;return}
      validIndex+=1;
      if(previous===null||Math.abs(loss-previous)>EXPOSURE_TIE_TOLERANCE_PP)position=validIndex;
      positionByPoint[p.id][s.chain_id]=position;previous=loss;
    });
  });
  drawRankChart(positionByPoint);
  const bestPosition=chain=>Math.min(...data.operating_points.map(p=>positionByPoint[p.id][chain]??999));
  const positionSum=chain=>data.operating_points.reduce((sum,p)=>sum+(positionByPoint[p.id][chain]??999),0);
  const orderedChains=[...data.chains].sort((a,b)=>bestPosition(a.chain_id)-bestPosition(b.chain_id)||positionSum(a.chain_id)-positionSum(b.chain_id)||a.chain_id.localeCompare(b.chain_id));
  document.getElementById('matrix-body').innerHTML=orderedChains.map(s=>{
    const values=data.operating_points.map(p=>({...cellFor(p.id,s.chain_id,selectedMechanism),position:positionByPoint[p.id][s.chain_id]}));
    const positions=values.map(v=>v.position),allMeasured=positions.every(value=>value!=null),inTopEverywhere=allMeasured&&positions.every(value=>value<=3),causes=values.map(v=>v.dominant),undetermined=causes.some(value=>['not_exercised','none','tie'].includes(value)),stableCause=!undetermined&&new Set(causes).size===1;
    const cells=values.map(v=>v.loss==null?'<td><span class="no">Non appliquée</span><br><small>Aucun événement d’incident appliqué selon la trace moteur ; cas hors de l’ordre descriptif.</small></td>':`<td><span class="rank">${v.position??'—'}</span> <span class="loss">${fmtPP(v.loss)}</span><div class="bar-track"><div class="bar" style="width:${Math.min(100,100*v.loss/max)}%"></div></div><small>${selectedMechanism==='all'?esc(v.dominantLabel)+' · ':''}${v.n}/${v.total} répétition(s) avec incident appliqué</small></td>`).join('');
    const topText=!allMeasured?'Comparaison incomplète':inTopEverywhere?'Oui':'Non · positions '+positions.join(' → '),causeText=selectedMechanism!=='all'?'Une seule hypothèse affichée':stableCause?'Oui':undetermined?'Non déterminée':'Non';
    return `<tr><td><b>${esc(s.supplier_id)}</b> · composant ${esc(s.item_id)}<br><small>${esc(s.factory_id)} → produit ${esc(s.product_id)}</small></td>${cells}<td class="${inTopEverywhere?'yes':'no'}">${topText}</td><td class="${stableCause?'yes':'no'}">${causeText}</td></tr>`;
  }).join('');
  finding(positionByPoint);
}
function finding(positionByPoint){
  const exposureGroups=data.operating_points.map(p=>[...data.chains].filter(c=>(positionByPoint[p.id][c.chain_id]??999)<=3).sort((a,b)=>positionByPoint[p.id][a.chain_id]-positionByPoint[p.id][b.chain_id]||a.chain_id.localeCompare(b.chain_id)));
  const exposureSets=exposureGroups.map(rows=>new Set(rows.map(c=>c.chain_id))),sameGroup=exposureSets.every(set=>set.size===exposureSets[0].size&&[...set].every(id=>exposureSets[0].has(id))),common=[...exposureSets[0]].filter(id=>exposureSets.every(set=>set.has(id))),union=[...new Set(exposureGroups.flat().map(c=>c.chain_id))],label=id=>{const s=data.chains.find(c=>c.chain_id===id);return s?`${s.supplier_id} (${s.item_id})`:id},causeProfiles=union.map(id=>({id,causes:data.operating_points.map(p=>cellFor(p.id,id,'all').dominant)})),undeterminedCause=causeProfiles.filter(x=>x.causes.some(value=>['not_exercised','none','tie'].includes(value))),determinedCause=causeProfiles.filter(x=>!x.causes.some(value=>['not_exercised','none','tie'].includes(value))),sameCause=determinedCause.filter(x=>new Set(x.causes).size===1),changedCause=determinedCause.filter(x=>new Set(x.causes).size>1),root=document.getElementById('stability-finding'),lists=data.operating_points.map((p,i)=>`<li><b>${esc(p.label)} :</b> ${exposureGroups[i].length?exposureGroups[i].map(c=>esc(label(c.chain_id))).join(' ; '):'aucune perte de service positive mesurée'}</li>`).join('');
  root.className='finding'+(sameGroup?'':' warn');
  const exposureText=sameGroup?`le même groupe ressort dans les trois premières positions d’exposition : ${exposureGroups[0].map(c=>esc(label(c.chain_id))).join(', ')}.`:`le groupe des trois premières positions change selon l’état. Chaîne(s) présente(s) dans les trois états : ${common.length?common.map(id=>esc(label(id))).join(', '):'aucune'}.`;
  const causeText=selectedMechanism==='all'?`<b>La raison reste-t-elle la même ?</b> Parmi les ${union.length} chaînes apparues dans ce groupe, ${sameCause.length} gardent une même hypothèse la plus pénalisante, ${changedCause.length} en changent et ${undeterminedCause.length} restent indéterminées faute d'effet positif unique ou de trace appliquée dans au moins un état.`:'<b>Cause affichée :</b> une seule hypothèse est sélectionnée ; aucune comparaison entre causes n’est faite.';
  root.innerHTML=`<b>Résultat exploratoire — ${selectedMetric==='global'?'impact réseau':'impact produit'} :</b> ${exposureText}<ul>${lists}</ul>${causeText}`;
  document.getElementById('sample-limit').textContent=`Lecture prudente : les 108 cas utilisent une seule répétition commune à conditions identiques. Ils donnent un ordre descriptif d’exposition à confirmer, pas un ordre statistique ni une probabilité d’incident. Les hypothèses ne sont pas des incidents historiques attribués aux fournisseurs.`
}
function supplierSelector(){const select=document.getElementById('supplier-select');select.innerHTML=data.chains.map(s=>`<option value="${esc(s.chain_id)}">${esc(s.supplier_id)} · ${esc(s.item_id)} · ${esc(s.factory_id)} → ${esc(s.product_id)}</option>`).join('');const preferred=data.chains.find(s=>s.item_id==='338929');if(preferred)select.value=preferred.chain_id;select.onchange=detail;detail()}
function detail(){const supplier=data.chains.find(s=>s.chain_id===document.getElementById('supplier-select').value);document.getElementById('chain').innerHTML=[['Fournisseur',supplier.supplier_id],['Composant',supplier.item_id],['Usine',supplier.factory_id],['Produit fini',supplier.product_id],['Client','service à date']].map((x,i)=>`${i?'<div class="arrow">→</div>':''}<div class="step"><b>${esc(x[0])}</b>${esc(x[1])}</div>`).join('');document.getElementById('cause-grid').innerHTML=data.mechanisms.map(m=>`<article class="cause"><h3>${esc(m.label)}</h3><p>${m.id==='delay'?"Le composant existe, mais arrive trop tard. On mesure si le stock et les commandes en transit absorbent le décalage avant qu'il atteigne la production.":"Un coefficient de disponibilité de 0,5 est imposé à la source. La quantité effectivement touchée dépend ensuite des flux rencontrés pendant la fenêtre simulée."}</p></article>`).join('');const rows=data.cells.filter(c=>c.chain_id===supplier.chain_id).sort((a,b)=>data.operating_points.findIndex(p=>p.id===a.operating_point_id)-data.operating_points.findIndex(p=>p.id===b.operating_point_id)||a.incident_mechanism.localeCompare(b.incident_mechanism));document.getElementById('detail-body').innerHTML=rows.map(c=>{const point=data.operating_points.find(p=>p.id===c.operating_point_id);if(!c.incident_physically_exercised)return `<tr><td><b>${esc(point.label)}</b><br>${fmtPct(point.global_service)} global</td><td>${esc(c.incident_label)}</td><td colspan="6"><span class="no">Aucun événement d’incident appliqué selon la trace moteur pendant la fenêtre ; ce cas n’entre pas dans l’ordre descriptif.</span></td></tr>`;const repetitions=c.exercised_seed_count===1?'1 simulation commune':`${fmtPP(c.min_service_loss_pp)} à ${fmtPP(c.max_service_loss_pp)} · ${c.exercised_seed_count} simulations`;const productionLoss=c.mean_production_delta==null?null:Math.max(0,-c.mean_production_delta);return `<tr><td><b>${esc(point.label)}</b><br>${fmtPct(point.global_service)} global</td><td>${esc(c.incident_label)}</td><td>${fmtPct(c.mean_baseline_service)}</td><td>${fmtPct(c.mean_incident_service)}</td><td class="loss">${fmtPP(c.mean_service_loss_pp)}</td><td>${repetitions}</td><td>${fmtQty(c.mean_backlog_qty_days_delta)} unités × jours</td><td>${fmtQty(productionLoss)} unités</td></tr>`}).join('')}
function decodeEmbedded(id){const encoded=document.getElementById(id).textContent.trim(),binary=atob(encoded),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);return new TextDecoder('utf-8').decode(bytes)}
function loadEmbeddedFrame(frameId,payloadId,loadingId){const frame=document.getElementById(frameId),loading=document.getElementById(loadingId);loading.classList.remove('hidden');loading.textContent='Chargement en cours…';frame.addEventListener('load',()=>loading.classList.add('hidden'),{once:true});try{frame.srcdoc=decodeEmbedded(payloadId)}catch(error){loading.textContent=`Chargement impossible : ${error.message}`;throw error}}
function loadMap(){if(mapLoaded)return;mapLoaded=true;loadEmbeddedFrame('map-frame','embedded-map','map-loading')}
function prepareCascade(){const section=document.getElementById('cascade-section'),cascade=data.state_cascade;section.classList.toggle('hidden',!cascade);if(!cascade)return;document.getElementById('cascade-metrics').innerHTML=`<article class="metric"><strong>${fmtPP(cascade.service_loss_points_state_off)}</strong><span>perte de service due au retard, règles dynamiques désactivées</span></article><article class="metric"><strong>${fmtPP(cascade.service_loss_points_state_on)}</strong><span>perte de service due au retard, règles dynamiques activées</span></article><article class="metric"><strong>${fmtPP(cascade.service_loss_amplification_points)} supplémentaires</strong><span>écart de service associé aux règles dynamiques dans cette répétition</span></article><article class="metric"><strong>+${fmtQty(cascade.backlog_amplification_qty_days)}</strong><span>unités × jours de retard client supplémentaires. C’est la somme, jour après jour, des unités de commandes encore en retard ; plus ce nombre augmente, plus le manque est volumineux et durable.</span></article><article class="metric"><strong>${fmtQty(cascade.production_loss_amplification_qty)}</strong><span>unités de produit 268091 non rattrapées à J719</span></article><article class="metric"><strong>${fmtQty(cascade.finished_product_lots_with_primary_or_incremental_signal_ancestry)}</strong><span>lots finis dont la généalogie simulée rencontre le choc initial ou un signal secondaire, sans dire qu’ils sont tous livrés en retard</span></article>`;document.getElementById('cascade-load').onclick=()=>{document.getElementById('cascade-shell').classList.remove('hidden');if(!cascadeLoaded){cascadeLoaded=true;loadEmbeddedFrame('cascade-frame','embedded-cascade','cascade-loading')}document.getElementById('cascade-shell').scrollIntoView({behavior:'smooth',block:'start'})}}
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{document.querySelectorAll('[data-view]').forEach(n=>n.classList.toggle('active',n===button));document.querySelectorAll('.view').forEach(view=>view.classList.toggle('active',view.id===button.dataset.view));if(button.dataset.view==='v3')loadMap();scrollTo({top:0,behavior:'smooth'})});pointCards();metricButtons();mechanismButtons();matrix();supplierSelector();
prepareCascade();
</script></body></html>'''


def build_meeting_html(
    *,
    results_csv: Path,
    map_html: Path,
    output_html: Path,
    calibration_csv: Path | None = None,
    cascade_html: Path | None = None,
    healthy_validation_json: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    results_csv = results_csv.resolve()
    map_html = map_html.resolve()
    output_html = output_html.resolve()
    if not results_csv.is_file():
        raise FileNotFoundError(results_csv)
    if not map_html.is_file():
        raise FileNotFoundError(map_html)
    if cascade_html is not None:
        cascade_html = cascade_html.resolve()
        if not cascade_html.is_file():
            raise FileNotFoundError(cascade_html)
    if healthy_validation_json is not None:
        healthy_validation_json = healthy_validation_json.resolve()
        if not healthy_validation_json.is_file():
            raise FileNotFoundError(healthy_validation_json)
    if output_html.exists() and not overwrite:
        raise FileExistsError(output_html)
    rows = _normalise_rows(_read_csv(results_csv))
    payload = _summarise(rows)
    payload["sensitivity_cliff"] = _sensitivity_cliff(calibration_csv)
    payload["has_state_dependent_cascade"] = cascade_html is not None
    current_manifest_path = results_csv.parent / "campaign_manifest.json"
    current_manifest = (
        json.loads(current_manifest_path.read_text(encoding="utf-8-sig"))
        if current_manifest_path.is_file()
        else {}
    )
    _validate_current_campaign_manifest(
        current_manifest_path,
        current_manifest,
        paired_seed_ids=payload["paired_seed_ids"],
    )
    payload["current_matrix_three_point_comparable"] = True
    payload["state_cascade"] = (
        _load_state_cascade_summary(cascade_html)
        if cascade_html is not None
        else None
    )
    if healthy_validation_json is not None:
        healthy_source = json.loads(
            healthy_validation_json.read_text(encoding="utf-8-sig")
        )
        healthy_manifest_path = healthy_validation_json.parent / "campaign_manifest.json"
        healthy_manifest = (
            json.loads(healthy_manifest_path.read_text(encoding="utf-8-sig"))
            if healthy_manifest_path.is_file()
            else {}
        )
        healthy_engine = str(healthy_manifest.get("engine_sha256") or "")
        current_engine = str(current_manifest.get("engine_sha256") or "")
        payload["healthy_validation"] = {
            "repetition_count": int(
                healthy_source.get("confirmation_seed_count") or 0
            ),
            "priority_group_supplier_ids": list(
                healthy_source.get("priority_group_top5_supplier_ids") or []
            ),
            "exact_top3_validated": bool(
                healthy_source.get("top3_set_validated")
            ),
            "same_engine_as_current": (
                healthy_engine == current_engine
                if healthy_engine and current_engine
                else None
            ),
        }
    else:
        payload["healthy_validation"] = None
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["sources"] = {
        "results_file": results_csv.name,
        "results_sha256": _sha256(results_csv),
        "map_file": map_html.name,
        "map_sha256": _sha256(map_html),
        **(
            {
                "calibration_file": calibration_csv.resolve().name,
                "calibration_sha256": _sha256(calibration_csv.resolve()),
            }
            if calibration_csv is not None
            else {}
        ),
        **(
            {
                "cascade_file": cascade_html.name,
                "cascade_sha256": _sha256(cascade_html),
                "cascade_summary_file": payload["state_cascade"]["source_file"],
                "cascade_summary_sha256": payload["state_cascade"]["source_sha256"],
            }
            if cascade_html is not None
            else {}
        ),
        **(
            {
                "healthy_validation_file": healthy_validation_json.name,
                "healthy_validation_sha256": _sha256(healthy_validation_json),
            }
            if healthy_validation_json is not None
            else {}
        ),
    }
    map_document = map_html.read_bytes()
    map_text = map_document.decode("utf-8", errors="replace").lower()
    for term in FORBIDDEN_BUSINESS_BRANCHES:
        if term in map_text:
            raise ValueError(f"Excluded business branch found in source map: {term}")
    cascade_document = cascade_html.read_bytes() if cascade_html is not None else b""
    cascade_text = cascade_document.decode("utf-8", errors="replace").lower()
    for term in FORBIDDEN_BUSINESS_BRANCHES:
        if term in cascade_text:
            raise ValueError(f"Excluded business branch found in cascade page: {term}")
    document = HTML_TEMPLATE.replace("__DATA__", _json_for_script(payload)).replace(
        "__MAP_BASE64__", base64.b64encode(map_document).decode("ascii")
    ).replace("__CASCADE_BASE64__", base64.b64encode(cascade_document).decode("ascii"))
    lowered = document.lower()
    for term in FORBIDDEN_BUSINESS_BRANCHES:
        # The embedded map is base64 and therefore cannot create a false match.
        if term in lowered:
            raise ValueError(f"Excluded business branch leaked into meeting HTML: {term}")
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(document, encoding="utf-8")
    manifest = {
        **payload,
        "output_html": str(output_html),
        "output_size_bytes": output_html.stat().st_size,
        "output_sha256": _sha256(output_html),
        "view_count": 3,
        "offline_single_file": True,
        "source_map_unchanged": _sha256(map_html) == payload["sources"]["map_sha256"],
    }
    manifest_path = output_html.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-csv", type=Path, required=True)
    parser.add_argument("--map-html", type=Path, required=True)
    parser.add_argument("--calibration-csv", type=Path)
    parser.add_argument("--cascade-html", type=Path)
    parser.add_argument("--healthy-validation-json", type=Path)
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_meeting_html(
        results_csv=args.results_csv,
        map_html=args.map_html,
        output_html=args.output_html,
        calibration_csv=args.calibration_csv,
        cascade_html=args.cascade_html,
        healthy_validation_json=args.healthy_validation_json,
        overwrite=args.overwrite,
    )
    print(f"[OK] Demonstration: {manifest['output_html']}")
    print(f"[OK] Operating points: {len(manifest['operating_points'])}")
    print(f"[OK] Suppliers / lanes: {manifest['supplier_count']} / {len(manifest['chains'])}")
    print(f"[OK] Paired seeds: {len(manifest['paired_seed_ids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
