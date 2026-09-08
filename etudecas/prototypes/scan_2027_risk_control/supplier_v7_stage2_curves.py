#!/usr/bin/env python3
"""Build lightweight nominal curves from the first 30 accepted V7 seed blocks.

All four daily CSV families are read from the retained V7 bundles.  Both the
gzip and decompressed CSV hashes are checked.  The curves describe the
campaign-pairing subset, never the 150-seed scientific acceptance population.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_aggregator_v4 as curve_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as traces_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_common as common,
)


SCHEMA_VERSION = "etudecas.supplier_v7_stage2_curves.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
PAYLOAD_NAME = "courbes_nominales_v7_stage2.json.gz"
MANIFEST_NAME = "courbes_nominales_v7_stage2.manifest.json"
HORIZON_DAYS = 720
SERVICE_WINDOW = 28
FLOW_WINDOW = 28
LEVEL_WINDOW = 7
EXPECTED_SERIES_COUNT = 108
SMOOTHING_CONTRACT = {
    "service_days": SERVICE_WINDOW,
    "production_flow_days": FLOW_WINDOW,
    "stock_wip_backlog_days": LEVEL_WINDOW,
    "lot_plan_gap_days": FLOW_WINDOW,
    "input_shortage_signal_days": LEVEL_WINDOW,
    "complete_windows_only": True,
    "daily_raw_sources_retained_upstream": True,
}
DAILY_SOURCES = (
    "data/production_demand_service_daily.csv",
    "data/production_output_products_daily.csv",
    "data/production_input_stocks_daily.csv",
    "data/production_constraint_daily.csv",
)
PRODUCTS = ("268091", "268967")


class Stage2CurveError(common.Stage2Error):
    """Retained V7 daily data cannot support the nominal-curve package."""


def _expected_series_keys(
    stock_pairs: set[tuple[str, str]],
) -> set[tuple[str, str, str, str, int]]:
    per_state = {
        ("service", product, metric, window)
        for product in (*PRODUCTS, "global")
        for metric, window in (
            ("service_a_l_heure", SERVICE_WINDOW),
            ("retard_client", LEVEL_WINDOW),
        )
    }
    per_state.update(
        ("production", product, metric, window)
        for product in PRODUCTS
        for metric, window in (
            ("production_liberee", FLOW_WINDOW),
            ("production_achevee", FLOW_WINDOW),
            ("encours", LEVEL_WINDOW),
            ("stock_produit_fini", LEVEL_WINDOW),
        )
    )
    per_state.update(
        ("stock_entrant", f"{node}|{item}", "stock_entrant", LEVEL_WINDOW)
        for node, item in stock_pairs
    )
    per_state.update(
        ("contrainte", product, "ecart_plan_lot", FLOW_WINDOW) for product in PRODUCTS
    )
    per_state.update(
        ("contrainte", product, "penurie_entree", LEVEL_WINDOW) for product in PRODUCTS
    )
    return {
        (state, domain, entity, metric, window)
        for state in common.EXPECTED_STATES
        for domain, entity, metric, window in per_state
    }


def _normalise_item(value: Any) -> str:
    return str(value or "").strip().removeprefix("item:")


def _as_day(value: Any, *, label: str) -> int:
    number = common.finite_number(value, label=label)
    day = int(number)
    if number != day or not 0 <= day < HORIZON_DAYS:
        raise Stage2CurveError(f"Jour hors horizon : {label}")
    return day


def _bundle_csv(
    *, run_dir: Path, evidence: Mapping[str, Any], source: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    matches = [
        dict(row)
        for row in (evidence.get("retained_bundle") or {}).get("files") or []
        if isinstance(row, Mapping) and row.get("source_relative_path") == source
    ]
    if len(matches) != 1:
        raise Stage2CurveError(f"Source quotidienne V7 non unique : {source}")
    reference = matches[0]
    path = (run_dir / str(reference.get("relative_path") or "")).resolve()
    if not path.is_relative_to(run_dir) or not path.is_file():
        raise Stage2CurveError(f"Source quotidienne V7 absente : {source}")
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != reference.get("gzip_sha256") or len(
        compressed
    ) != int(reference.get("gzip_bytes") or -1):
        raise Stage2CurveError(f"Empreinte gzip modifiée : {source}")
    try:
        raw = gzip.decompress(compressed)
        text = raw.decode("utf-8-sig")
        rows = [dict(row) for row in csv.DictReader(io.StringIO(text, newline=""))]
    except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
        raise Stage2CurveError(f"CSV quotidien V7 illisible : {source}") from exc
    if (
        not rows
        or hashlib.sha256(raw).hexdigest() != reference.get("source_sha256")
        or len(raw) != int(reference.get("source_bytes") or -1)
    ):
        raise Stage2CurveError(f"Empreinte CSV décompressée modifiée : {source}")
    return rows, {
        "source_relative_path": source,
        "retained_relative_path": str(reference["relative_path"]),
        "gzip_sha256": str(reference["gzip_sha256"]),
        "source_sha256": str(reference["source_sha256"]),
        "gzip_bytes": int(reference["gzip_bytes"]),
        "source_bytes": int(reference["source_bytes"]),
    }


def _require_columns(
    rows: Sequence[Mapping[str, Any]], fields: set[str], label: str
) -> None:
    if not rows or not fields.issubset(rows[0]):
        raise Stage2CurveError(f"Colonnes quotidiennes absentes : {label}")


def _dense_values(
    rows: Sequence[Mapping[str, Any]],
    *,
    entity_field: str,
    value_field: str,
    allowed_entities: set[str],
    sparse: bool = False,
    indicator: bool = False,
) -> dict[str, list[float]]:
    output = {
        entity: [0.0 for _day in range(HORIZON_DAYS)]
        for entity in sorted(allowed_entities)
    }
    seen: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        entity = _normalise_item(row.get(entity_field))
        if entity not in allowed_entities:
            continue
        day = _as_day(row.get("day"), label=f"{entity}/{value_field}")
        if not sparse and day in seen[entity]:
            raise Stage2CurveError(
                f"Série quotidienne dupliquée : {entity}/{value_field}/J{day}"
            )
        if indicator:
            value = (
                1.0 if str(row.get("binding_cause") or "") == "input_shortage" else 0.0
            )
            output[entity][day] = max(output[entity][day], value)
        else:
            value = common.finite_number(
                row.get(value_field), label=f"{entity}/{value_field}/J{day}"
            )
            if value < 0.0:
                raise Stage2CurveError(
                    f"Valeur quotidienne négative : {entity}/{value_field}"
                )
            output[entity][day] += value
        seen[entity].add(day)
    if not sparse and any(
        seen.get(entity, set()) != set(range(HORIZON_DAYS))
        for entity in allowed_entities
    ):
        raise Stage2CurveError(f"Série quotidienne incomplète : {value_field}")
    return output


def _input_stock_values(
    rows: Sequence[Mapping[str, Any]], pairs: set[tuple[str, str]]
) -> dict[str, list[float]]:
    output = {f"{node}|{item}": [0.0] * HORIZON_DAYS for node, item in sorted(pairs)}
    seen: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        pair = (str(row.get("node_id") or ""), _normalise_item(row.get("item_id")))
        if pair not in pairs:
            continue
        key = f"{pair[0]}|{pair[1]}"
        day = _as_day(row.get("day"), label=f"{key}/stock")
        value = common.finite_number(
            row.get("stock_end_of_day"), label=f"{key}/stock/J{day}"
        )
        if value < 0.0 or day in seen[key]:
            raise Stage2CurveError(f"Stock entrant quotidien invalide : {key}/J{day}")
        output[key][day] = value
        seen[key].add(day)
    if any(seen.get(key, set()) != set(range(HORIZON_DAYS)) for key in output):
        raise Stage2CurveError("Une série de stock entrant est incomplète")
    return output


def _service_case(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, int], list[float]]:
    _require_columns(
        rows,
        {
            "day",
            "node_id",
            "item_id",
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
        },
        "service",
    )
    client_rows = [row for row in rows if str(row.get("node_id") or "") == "C-XXXXX"]
    if not client_rows or len(client_rows) != len(rows):
        raise Stage2CurveError(
            "Les courbes de service doivent viser exclusivement le client agrégé C-XXXXX"
        )
    demand = _dense_values(
        client_rows,
        entity_field="item_id",
        value_field="demand_qty",
        allowed_entities=set(PRODUCTS),
    )
    required = _dense_values(
        client_rows,
        entity_field="item_id",
        value_field="required_with_backlog_qty",
        allowed_entities=set(PRODUCTS),
    )
    served = _dense_values(
        client_rows,
        entity_field="item_id",
        value_field="served_qty",
        allowed_entities=set(PRODUCTS),
    )
    backlog = _dense_values(
        client_rows,
        entity_field="item_id",
        value_field="backlog_end_qty",
        allowed_entities=set(PRODUCTS),
    )
    output: dict[tuple[str, str, int], list[float]] = {}
    for product in PRODUCTS:
        on_due = [
            min(raw_demand, max(0.0, raw_served - max(0.0, raw_required - raw_demand)))
            for raw_demand, raw_required, raw_served in zip(
                demand[product],
                required[product],
                served[product],
                strict=True,
            )
        ]
        output[(product, "service_a_l_heure", SERVICE_WINDOW)] = curve_v4.rolling_ratio(
            on_due, demand[product], SERVICE_WINDOW
        )
        output[(product, "retard_client", LEVEL_WINDOW)] = curve_v4.rolling_mean(
            backlog[product], LEVEL_WINDOW
        )
    global_demand = [
        sum(demand[product][day] for product in PRODUCTS) for day in range(HORIZON_DAYS)
    ]
    global_on_due = []
    global_backlog = []
    for day in range(HORIZON_DAYS):
        total_on_due = 0.0
        total_backlog = 0.0
        for product in PRODUCTS:
            previous_backlog = max(0.0, required[product][day] - demand[product][day])
            total_on_due += min(
                demand[product][day],
                max(0.0, served[product][day] - previous_backlog),
            )
            total_backlog += backlog[product][day]
        global_on_due.append(total_on_due)
        global_backlog.append(total_backlog)
    output[("global", "service_a_l_heure", SERVICE_WINDOW)] = curve_v4.rolling_ratio(
        global_on_due, global_demand, SERVICE_WINDOW
    )
    output[("global", "retard_client", LEVEL_WINDOW)] = curve_v4.rolling_mean(
        global_backlog, LEVEL_WINDOW
    )
    return output


def _case_series(
    source_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    stock_pairs: set[tuple[str, str]],
) -> dict[tuple[str, str, str, int], list[float | None]]:
    output: dict[tuple[str, str, str, int], list[float | None]] = {}
    service = _service_case(source_rows[DAILY_SOURCES[0]])
    for (entity, metric, window), values in service.items():
        output[("service", entity, metric, window)] = values

    production_rows = source_rows[DAILY_SOURCES[1]]
    _require_columns(
        production_rows,
        {
            "day",
            "item_id",
            "released_qty",
            "produced_qty",
            "wip_end_qty",
            "stock_end_of_day",
        },
        "production",
    )
    for field, metric, window in (
        ("released_qty", "production_liberee", FLOW_WINDOW),
        ("produced_qty", "production_achevee", FLOW_WINDOW),
        ("wip_end_qty", "encours", LEVEL_WINDOW),
        ("stock_end_of_day", "stock_produit_fini", LEVEL_WINDOW),
    ):
        raw = _dense_values(
            production_rows,
            entity_field="item_id",
            value_field=field,
            allowed_entities=set(PRODUCTS),
        )
        for product, values in raw.items():
            output[("production", product, metric, window)] = curve_v4.rolling_mean(
                values, window
            )

    stock_rows = source_rows[DAILY_SOURCES[2]]
    _require_columns(
        stock_rows, {"day", "node_id", "item_id", "stock_end_of_day"}, "stocks entrants"
    )
    for entity, values in _input_stock_values(stock_rows, stock_pairs).items():
        output[("stock_entrant", entity, "stock_entrant", LEVEL_WINDOW)] = (
            curve_v4.rolling_mean(values, LEVEL_WINDOW)
        )

    constraint_rows = source_rows[DAILY_SOURCES[3]]
    _require_columns(
        constraint_rows,
        {"day", "output_item_id", "shortfall_vs_lot_plan_qty", "binding_cause"},
        "contraintes",
    )
    shortfall = _dense_values(
        constraint_rows,
        entity_field="output_item_id",
        value_field="shortfall_vs_lot_plan_qty",
        allowed_entities=set(PRODUCTS),
        sparse=True,
    )
    shortage = _dense_values(
        constraint_rows,
        entity_field="output_item_id",
        value_field="shortfall_vs_lot_plan_qty",
        allowed_entities=set(PRODUCTS),
        sparse=True,
        indicator=True,
    )
    for product in PRODUCTS:
        output[("contrainte", product, "ecart_plan_lot", FLOW_WINDOW)] = (
            curve_v4.rolling_mean(shortfall[product], FLOW_WINDOW)
        )
        output[("contrainte", product, "penurie_entree", LEVEL_WINDOW)] = (
            curve_v4.rolling_mean(shortage[product], LEVEL_WINDOW)
        )
    return output


def _aggregate(
    samples: Mapping[tuple[str, str, str, str, int], Sequence[Sequence[float | None]]],
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    units = {
        "service_a_l_heure": "%",
        "retard_client": "UN",
        "production_liberee": "UN/jour",
        "production_achevee": "UN/jour",
        "encours": "UN",
        "stock_produit_fini": "UN",
        "stock_entrant": "UN",
        "ecart_plan_lot": "UN/jour",
        "penurie_entree": "part_de_jours",
    }
    for (state, domain, entity, metric, window), cohort in sorted(samples.items()):
        if len(cohort) != common.EXPECTED_CAMPAIGN_SEEDS:
            raise Stage2CurveError(
                f"Cohorte courbe incomplète : {state}/{entity}/{metric}"
            )
        points = []
        for day in range(HORIZON_DAYS):
            values = [float(row[day]) for row in cohort if row[day] is not None]
            if not values:
                continue
            if len(values) != common.EXPECTED_CAMPAIGN_SEEDS:
                raise Stage2CurveError("Nombre de graines variable dans une courbe")
            factor = 100.0 if metric == "service_a_l_heure" else 1.0
            scaled = [factor * value for value in values]
            points.append(
                [
                    day,
                    sum(scaled) / len(scaled),
                    curve_v4.linear_quantile(scaled, 0.10),
                    curve_v4.linear_quantile(scaled, 0.50),
                    curve_v4.linear_quantile(scaled, 0.90),
                ]
            )
        if (
            not points
            or points[0][0] != window - 1
            or points[-1][0] != HORIZON_DAYS - 1
        ):
            raise Stage2CurveError("Fenêtre glissante ou horizon de courbe incohérent")
        series.append(
            {
                "state": state,
                "domain": domain,
                "entity": entity,
                "metric": metric,
                "unit": units[metric],
                "rolling_window_days": window,
                "sample_count": common.EXPECTED_CAMPAIGN_SEEDS,
                "columns": ["day", "mean", "p10", "median", "p90"],
                "points": points,
            }
        )
    return series


def _source_contract(
    *,
    plan_dir: Path,
    run_dir: Path,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    trace_manifest: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_cases = []
    source_files = []
    for spec in protocol_v7.FIXED_TRIPLET:
        for seed in traces_v7.CAMPAIGN_SEEDS:
            row = evidence[(spec.key, seed)]
            bundle = row.get("retained_bundle") or {}
            selected_files = [
                dict(item)
                for item in bundle.get("files") or []
                if isinstance(item, Mapping)
                and item.get("source_relative_path") in DAILY_SOURCES
            ]
            if {item.get("source_relative_path") for item in selected_files} != set(
                DAILY_SOURCES
            ):
                raise Stage2CurveError(
                    "Les quatre fichiers quotidiens V7 ne sont pas tous retenus"
                )
            source_cases.append(
                {
                    "state": spec.target_group,
                    "candidate_key": spec.key,
                    "candidate_id": spec.candidate_id,
                    "seed": seed,
                    "evidence_signature": row["evidence_signature"],
                    "bundle_signature": bundle["bundle_signature"],
                }
            )
            for item in sorted(
                selected_files, key=lambda value: str(value["source_relative_path"])
            ):
                source_files.append(
                    {
                        "state": spec.target_group,
                        "seed": seed,
                        "source_relative_path": item["source_relative_path"],
                        "retained_relative_path": item["relative_path"],
                        "gzip_sha256": item["gzip_sha256"],
                        "source_sha256": item["source_sha256"],
                        "gzip_bytes": item["gzip_bytes"],
                        "source_bytes": item["source_bytes"],
                    }
                )
    if len(source_cases) != 90 or len(source_files) != 360:
        raise Stage2CurveError("Inventaire de courbes V7 différent de 90 × 4")
    if trace_manifest.get("campaign_cohort", {}).get("seeds") != list(
        traces_v7.CAMPAIGN_SEEDS
    ):
        raise Stage2CurveError(
            "Les graines du paquet de traces et des courbes diffèrent"
        )
    return source_cases, source_files


def _build_payload(
    plan_dir: Path, run_dir: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_dir = plan_dir.resolve()
    run_dir = run_dir.resolve()
    result = protocol_v7.validate_result(plan_dir, run_dir)
    if result.get("accepted") is not True or result.get("publishable") is not True:
        raise Stage2CurveError("Les courbes exigent une confirmation V7 acceptée")
    evidence = protocol_v7.validated_evidence(plan_dir, run_dir)
    plan = protocol_v7.validate_plan(plan_dir, verify_runtime=True)
    lanes = traces_v7._campaign_lanes(plan)  # noqa: SLF001
    stock_pairs = {
        (str(row.get("dst_node_id") or ""), _normalise_item(row.get("item_id")))
        for row in lanes
    }
    if not stock_pairs or ("M-1810", "338929") not in stock_pairs:
        raise Stage2CurveError("Le périmètre signé des stocks entrants est incomplet")
    samples: dict[tuple[str, str, str, str, int], list[list[float | None]]] = (
        defaultdict(list)
    )
    source_cases: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []
    for spec in protocol_v7.FIXED_TRIPLET:
        for seed in traces_v7.CAMPAIGN_SEEDS:
            case = evidence[(spec.key, seed)]
            rows_by_source: dict[str, list[dict[str, str]]] = {}
            file_records = []
            for source in sorted(DAILY_SOURCES):
                rows, record = _bundle_csv(
                    run_dir=run_dir, evidence=case, source=source
                )
                rows_by_source[source] = rows
                file_records.append(record)
            case_series = _case_series(rows_by_source, stock_pairs=stock_pairs)
            for (domain, entity, metric, window), values in case_series.items():
                samples[(spec.target_group, domain, entity, metric, window)].append(
                    values
                )
            source_cases.append(
                {
                    "state": spec.target_group,
                    "candidate_key": spec.key,
                    "candidate_id": spec.candidate_id,
                    "seed": seed,
                    "evidence_signature": case["evidence_signature"],
                    "bundle_signature": case["retained_bundle"]["bundle_signature"],
                }
            )
            source_files.extend(
                {"state": spec.target_group, "seed": seed, **record}
                for record in file_records
            )
    series = _aggregate(samples)
    actual_series_keys = {
        (
            row["state"],
            row["domain"],
            row["entity"],
            row["metric"],
            row["rolling_window_days"],
        )
        for row in series
    }
    if len(actual_series_keys) != len(series) or actual_series_keys != (
        _expected_series_keys(stock_pairs)
    ):
        raise Stage2CurveError("Inventaire des séries nominales incomplet")
    payload_unsigned = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_validated",
        "scope": {
            "states": list(common.EXPECTED_STATES),
            "seed_selection": "first_30_seed_blocks_in_signed_v7_plan_order",
            "seed_count_per_state": common.EXPECTED_CAMPAIGN_SEEDS,
            "case_count": 90,
            "daily_source_count": 360,
            "horizon_days": HORIZON_DAYS,
            "scientific_acceptance_population": False,
            "campaign_pairing_subset_only": True,
        },
        "smoothing": dict(SMOOTHING_CONTRACT),
        "interpretation_fr": (
            "Moyennes glissantes puis dispersion entre les 30 premières graines V7. "
            "Ces courbes décrivent les références appariées de campagne; la validation "
            "scientifique des trois états reste fondée sur 150 graines et 450 cas."
        ),
        "series": series,
    }
    payload = common.signed(payload_unsigned, "payload_signature")
    manifest_unsigned = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "producer": {
            "path": str(Path(__file__).resolve()),
            "sha256": common.sha256_file(Path(__file__).resolve()),
        },
        "v7_source": {
            "plan_dir": str(plan_dir),
            "run_dir": str(run_dir),
            "plan_signature": plan.manifest["plan_signature"],
            "result_signature": result["result_signature"],
            "validation_seed_count": 150,
            "validation_case_count": 450,
        },
        "source_cases": source_cases,
        "source_files": source_files,
        "source_case_signature_set_sha256": common.stable_sha256(
            sorted(row["evidence_signature"] for row in source_cases)
        ),
        "payload": {
            "name": PAYLOAD_NAME,
            "payload_signature": payload["payload_signature"],
        },
        "engine_runs_performed": 0,
    }
    return payload, common.signed(manifest_unsigned, "manifest_signature")


def build_curve_package(
    plan_dir: Path, run_dir: Path, output_dir: Path
) -> dict[str, Any]:
    output = output_dir.resolve()
    for source in (
        plan_dir.resolve(),
        run_dir.resolve(),
        Path(__file__).resolve().parents[3],
    ):
        if common.paths_overlap(output, source):
            raise Stage2CurveError("La sortie courbes chevauche une source protégée")
    if output.exists():
        return validate_curve_package(output, plan_dir=plan_dir, run_dir=run_dir)
    payload, manifest = _build_payload(plan_dir, run_dir)
    payload_raw = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")
    compressed = gzip.compress(payload_raw, compresslevel=9, mtime=0)
    manifest["payload"].update(
        {
            "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
            "gzip_bytes": len(compressed),
            "source_sha256": hashlib.sha256(payload_raw).hexdigest(),
            "source_bytes": len(payload_raw),
        }
    )
    unsigned = dict(manifest)
    unsigned.pop("manifest_signature", None)
    manifest["manifest_signature"] = common.stable_sha256(unsigned)
    stage = output.with_name(f".{output.name}.stage2-{uuid.uuid4().hex}")
    published = False
    try:
        stage.mkdir(parents=True, exist_ok=False)
        (stage / PAYLOAD_NAME).write_bytes(compressed)
        (stage / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(stage, output)
        published = True
        return validate_curve_package(output, plan_dir=plan_dir, run_dir=run_dir)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        if published and output.exists():
            try:
                validate_curve_package(output, plan_dir=plan_dir, run_dir=run_dir)
            except BaseException:
                shutil.rmtree(output)
        raise


def load_curve_payload(output_dir: Path) -> dict[str, Any]:
    root = output_dir.resolve()
    manifest = common.read_json(root / MANIFEST_NAME)
    common.verify_signature(manifest, "manifest_signature", "manifeste courbes V7")
    declaration = manifest.get("payload") or {}
    path = root / PAYLOAD_NAME
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != declaration.get("gzip_sha256") or len(
        compressed
    ) != int(declaration.get("gzip_bytes") or -1):
        raise Stage2CurveError("Paquet gzip de courbes modifié")
    try:
        raw = gzip.decompress(compressed)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2CurveError("Paquet de courbes illisible") from exc
    if (
        not isinstance(payload, dict)
        or hashlib.sha256(raw).hexdigest() != declaration.get("source_sha256")
        or len(raw) != int(declaration.get("source_bytes") or -1)
    ):
        raise Stage2CurveError("Contenu décompressé des courbes modifié")
    common.verify_signature(payload, "payload_signature", "courbes V7")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("status") != "complete_validated"
        or declaration.get("payload_signature") != payload.get("payload_signature")
        or payload.get("scope", {}).get("case_count") != 90
        or payload.get("scope", {}).get("campaign_pairing_subset_only") is not True
        or payload.get("smoothing") != SMOOTHING_CONTRACT
    ):
        raise Stage2CurveError("Contrat des courbes V7 invalide")
    return payload


def _validate_series_inventory(
    payload: Mapping[str, Any], stock_pairs: set[tuple[str, str]]
) -> None:
    series = payload.get("series")
    if not isinstance(series, list):
        raise Stage2CurveError("Inventaire des séries nominales absent")
    actual: set[tuple[str, str, str, str, int]] = set()
    for row in series:
        if not isinstance(row, Mapping):
            raise Stage2CurveError("Série nominale invalide")
        window = int(row.get("rolling_window_days") or -1)
        key = (
            str(row.get("state") or ""),
            str(row.get("domain") or ""),
            str(row.get("entity") or ""),
            str(row.get("metric") or ""),
            window,
        )
        points = row.get("points")
        if (
            key in actual
            or row.get("columns") != ["day", "mean", "p10", "median", "p90"]
            or int(row.get("sample_count") or -1) != common.EXPECTED_CAMPAIGN_SEEDS
            or not isinstance(points, list)
            or len(points) != HORIZON_DAYS - window + 1
        ):
            raise Stage2CurveError("Structure d'une série nominale invalide")
        actual.add(key)
        for expected_day, point in enumerate(points, start=window - 1):
            if (
                not isinstance(point, list)
                or len(point) != 5
                or point[0] != expected_day
                or any(
                    not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in point[1:]
                )
                or not point[2] <= point[3] <= point[4]
            ):
                raise Stage2CurveError("Point de courbe nominale invalide")
    expected = _expected_series_keys(stock_pairs)
    if len(expected) != EXPECTED_SERIES_COUNT or actual != expected:
        raise Stage2CurveError("Le paquet ne contient pas les 108 séries attendues")


def validate_curve_package(
    output_dir: Path, *, plan_dir: Path | None = None, run_dir: Path | None = None
) -> dict[str, Any]:
    root = output_dir.resolve()
    manifest = common.read_json(root / MANIFEST_NAME)
    common.verify_signature(manifest, "manifest_signature", "manifeste courbes V7")
    source = manifest.get("v7_source") or {}
    expected_plan = Path(str(source.get("plan_dir") or "")).resolve()
    expected_run = Path(str(source.get("run_dir") or "")).resolve()
    if plan_dir is not None and expected_plan != plan_dir.resolve():
        raise Stage2CurveError("Le paquet de courbes appartient à un autre plan V7")
    if run_dir is not None and expected_run != run_dir.resolve():
        raise Stage2CurveError("Le paquet de courbes appartient à un autre run V7")
    result = protocol_v7.validate_result(expected_plan, expected_run)
    evidence = protocol_v7.validated_evidence(expected_plan, expected_run)
    plan = protocol_v7.validate_plan(expected_plan, verify_runtime=True)
    lanes = traces_v7._campaign_lanes(plan)  # noqa: SLF001
    stock_pairs = {
        (str(row.get("dst_node_id") or ""), _normalise_item(row.get("item_id")))
        for row in lanes
    }
    trace_manifest = {"campaign_cohort": {"seeds": list(traces_v7.CAMPAIGN_SEEDS)}}
    cases, files = _source_contract(
        plan_dir=expected_plan,
        run_dir=expected_run,
        evidence=evidence,
        trace_manifest=trace_manifest,
    )
    payload = load_curve_payload(root)
    _validate_series_inventory(payload, stock_pairs)
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "complete_validated"
        or source.get("plan_signature") != plan.manifest["plan_signature"]
        or source.get("result_signature") != result["result_signature"]
        or manifest.get("source_cases") != cases
        or manifest.get("source_files") != files
        or manifest.get("engine_runs_performed") != 0
    ):
        raise Stage2CurveError("Le paquet de courbes diffère de ses sources V7")
    return {
        "valid": True,
        "manifest": str(root / MANIFEST_NAME),
        "manifest_signature": manifest["manifest_signature"],
        "payload_signature": payload["payload_signature"],
        "series_count": len(payload["series"]),
        "case_count": 90,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--v7-plan-dir", type=Path, required=True)
    build.add_argument("--v7-run-dir", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_curve_package(
                args.v7_plan_dir, args.v7_run_dir, args.output_dir
            )
        else:
            result = validate_curve_package(args.output_dir)
    except (Stage2CurveError, common.Stage2Error) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
