"""Build compact, descriptive daily curves from a completed V4 sidecar capture.

Rolling values are computed independently inside each simulation before the
P10/median/P90 envelope is calculated across seeds.  The envelopes describe
simulation dispersion.  They are not observed supplier probabilities or
statistical confidence intervals.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture,
)


SCHEMA_VERSION = "etudecas.supplier_holdout_curve_aggregator.v4"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
OUTPUT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.daily_quantiles.v1"
AGGREGATE_SUBDIRECTORY = "curve_aggregates_v1"
QUANTILES = (0.10, 0.50, 0.90)
OUTPUT_COLUMNS = (
    "target_group",
    "candidate_id",
    "day",
    "node_id",
    "item_id",
    "metric",
    "unit",
    "rolling_window_days",
    "sample_count",
    "p10",
    "median",
    "p90",
)


class CurveAggregationError(RuntimeError):
    """Raised when captured inputs or aggregate outputs are inconsistent."""


@dataclass(frozen=True)
class MetricDefinition:
    domain: str
    metric: str
    unit: str
    rolling_window_days: int
    calculation_fr: str


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        "service",
        "on_due_service_ratio",
        "ratio_0_1",
        0,
        "service du jour hors rattrapage des retards antérieurs",
    ),
    MetricDefinition(
        "service",
        "on_due_service_ratio",
        "ratio_0_1",
        28,
        "somme servie à l'heure / somme demandée sur 28 jours complets",
    ),
    MetricDefinition("service", "demand_qty", "UN_par_jour", 0, "demande brute"),
    MetricDefinition(
        "service", "on_due_qty", "UN_par_jour", 0, "volume servi à l'heure"
    ),
    MetricDefinition(
        "service", "backlog_end_qty", "UN", 0, "retard client en fin de jour"
    ),
    MetricDefinition(
        "service",
        "backlog_end_qty",
        "UN",
        7,
        "moyenne du retard client sur 7 jours complets",
    ),
    MetricDefinition(
        "production", "released_qty", "UN_par_jour", 0, "production libérée brute"
    ),
    MetricDefinition(
        "production",
        "released_qty",
        "UN_par_jour",
        28,
        "moyenne de la production libérée sur 28 jours complets",
    ),
    MetricDefinition(
        "production", "produced_qty", "UN_par_jour", 0, "production achevée brute"
    ),
    MetricDefinition(
        "production",
        "produced_qty",
        "UN_par_jour",
        28,
        "moyenne de la production achevée sur 28 jours complets",
    ),
    MetricDefinition("production", "wip_end_qty", "UN", 0, "encours en fin de jour"),
    MetricDefinition(
        "production",
        "wip_end_qty",
        "UN",
        7,
        "moyenne de l'encours sur 7 jours complets",
    ),
    MetricDefinition(
        "production",
        "finished_stock_end_qty",
        "UN",
        0,
        "stock de produit de sortie en fin de jour",
    ),
    MetricDefinition(
        "production",
        "finished_stock_end_qty",
        "UN",
        7,
        "moyenne du stock de sortie sur 7 jours complets",
    ),
    MetricDefinition(
        "input_stock", "input_stock_end_qty", "UN", 0, "stock entrant brut"
    ),
    MetricDefinition(
        "input_stock",
        "input_stock_end_qty",
        "UN",
        7,
        "moyenne du stock entrant sur 7 jours complets",
    ),
    MetricDefinition(
        "constraint",
        "lot_plan_shortfall_qty",
        "UN_par_jour",
        0,
        "écart brut entre plan de lot et quantité réalisée; zéro sans décision",
    ),
    MetricDefinition(
        "constraint",
        "input_shortage_indicator",
        "indicateur_0_1",
        0,
        "1 si une pénurie d'entrée est la contrainte du jour, sinon 0",
    ),
)
DEFINITION_BY_KEY = {
    (definition.domain, definition.metric, definition.rolling_window_days): definition
    for definition in METRIC_DEFINITIONS
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurveAggregationError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise CurveAggregationError(f"Objet JSON attendu : {path}")
    return payload


def _verify_signature(payload: Mapping[str, Any], field: str, label: str) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(field, ""))
    if len(signature) != 64 or signature != capture.stable_sha256(unsigned):
        raise CurveAggregationError(f"Signature invalide : {label}")
    return signature


def _decompressed_snapshot(
    output_dir: Path, case: capture.ExpectedCase, filename: str, horizon: int
) -> list[dict[str, str]]:
    data_path, meta_path = capture._snapshot_paths(output_dir, case, filename)
    try:
        capture._validate_stored_snapshot(data_path, meta_path)
        raw = gzip.decompress(data_path.read_bytes())
        spec = capture.SPEC_BY_FILENAME[filename]
        capture.validate_csv_bytes(raw, spec, horizon)
    except (OSError, EOFError, capture.CurveSidecarError) as exc:
        raise CurveAggregationError(f"Instantané CSV invalide : {data_path}") from exc
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    return [dict(row) for row in reader]


def _to_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CurveAggregationError(f"Valeur non numérique : {label}") from exc
    if not math.isfinite(result):
        raise CurveAggregationError(f"Valeur non finie : {label}")
    return result


def linear_quantile(values: Sequence[float], quantile: float) -> float:
    """Return the deterministic type-7/linear empirical quantile."""

    if not values or not 0.0 <= quantile <= 1.0:
        raise CurveAggregationError("Quantile impossible")
    ordered = sorted(_to_float(value, "quantile") for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def rolling_mean(values: Sequence[float], window: int) -> list[float | None]:
    if window < 1:
        raise CurveAggregationError("Fenêtre glissante invalide")
    result: list[float | None] = []
    running = 0.0
    for index, raw in enumerate(values):
        value = _to_float(raw, "moyenne glissante")
        running += value
        if index >= window:
            running -= float(values[index - window])
        result.append(running / window if index + 1 >= window else None)
    return result


def rolling_ratio(
    numerators: Sequence[float], denominators: Sequence[float], window: int
) -> list[float | None]:
    if len(numerators) != len(denominators) or window < 1:
        raise CurveAggregationError("Ratio glissant invalide")
    result: list[float | None] = []
    numerator_sum = 0.0
    denominator_sum = 0.0
    for index, (raw_numerator, raw_denominator) in enumerate(
        zip(numerators, denominators, strict=True)
    ):
        numerator_sum += _to_float(raw_numerator, "numérateur glissant")
        denominator_sum += _to_float(raw_denominator, "dénominateur glissant")
        if index >= window:
            numerator_sum -= float(numerators[index - window])
            denominator_sum -= float(denominators[index - window])
        result.append(
            numerator_sum / denominator_sum
            if index + 1 >= window and denominator_sum > 0
            else None
        )
    return result


def _dense_series(
    rows: Iterable[Mapping[str, str]],
    *,
    horizon: int,
    item_column: str,
    value: Callable[[Mapping[str, str]], float],
) -> dict[tuple[str, str], list[float]]:
    series: dict[tuple[str, str], list[float | None]] = {}
    for row in rows:
        key = (str(row["node_id"]), str(row[item_column]))
        values = series.setdefault(key, [None] * horizon)
        day = int(row["day"])
        if values[day] is not None:
            raise CurveAggregationError(f"Jour dupliqué dans la série {key}")
        values[day] = value(row)
    if not series or any(
        any(value is None for value in values) for values in series.values()
    ):
        raise CurveAggregationError("Série dense incomplète pendant l'agrégation")
    return {
        key: [float(value) for value in values if value is not None]
        for key, values in series.items()
    }


SampleKey = tuple[str, str, int, str, str, str, int]


def _add_values(
    samples: dict[SampleKey, list[float]],
    definitions: set[tuple[str, str, str, int]],
    *,
    target_group: str,
    candidate_id: str,
    node_id: str,
    item_id: str,
    domain: str,
    metric: str,
    window: int,
    values: Sequence[float | None],
) -> None:
    if (domain, metric, window) not in DEFINITION_BY_KEY:
        raise CurveAggregationError("Définition de métrique absente")
    definitions.add((node_id, item_id, metric, window))
    for day, value in enumerate(values):
        if value is None:
            continue
        samples[
            (
                target_group,
                candidate_id,
                day,
                node_id,
                item_id,
                metric,
                window,
            )
        ].append(_to_float(value, metric))


def _add_service_case(
    samples: dict[SampleKey, list[float]],
    definitions: set[tuple[str, str, str, int]],
    case: capture.ExpectedCase,
    rows: Sequence[Mapping[str, str]],
    horizon: int,
) -> None:
    demand = _dense_series(
        rows,
        horizon=horizon,
        item_column="item_id",
        value=lambda row: _to_float(row["demand_qty"], "demande"),
    )
    on_due = _dense_series(
        rows,
        horizon=horizon,
        item_column="item_id",
        value=lambda row: min(
            _to_float(row["demand_qty"], "demande"),
            max(
                0.0,
                _to_float(row["served_qty"], "servi")
                - max(
                    0.0,
                    _to_float(row["required_with_backlog_qty"], "requis")
                    - _to_float(row["demand_qty"], "demande"),
                ),
            ),
        ),
    )
    backlog = _dense_series(
        rows,
        horizon=horizon,
        item_column="item_id",
        value=lambda row: _to_float(row["backlog_end_qty"], "retard"),
    )
    for key in sorted(demand):
        node_id, item_id = key
        if key not in on_due or key not in backlog:
            raise CurveAggregationError("Clés service non concordantes")
        daily_ratio = [
            numerator / denominator if denominator > 0 else 1.0
            for numerator, denominator in zip(on_due[key], demand[key], strict=True)
        ]
        for metric, window, values in (
            ("demand_qty", 0, demand[key]),
            ("on_due_qty", 0, on_due[key]),
            ("on_due_service_ratio", 0, daily_ratio),
            (
                "on_due_service_ratio",
                28,
                rolling_ratio(on_due[key], demand[key], 28),
            ),
            ("backlog_end_qty", 0, backlog[key]),
            ("backlog_end_qty", 7, rolling_mean(backlog[key], 7)),
        ):
            _add_values(
                samples,
                definitions,
                target_group=case.target_group,
                candidate_id=case.candidate_id,
                node_id=node_id,
                item_id=item_id,
                domain="service",
                metric=metric,
                window=window,
                values=values,
            )


def _add_production_case(
    samples: dict[SampleKey, list[float]],
    definitions: set[tuple[str, str, str, int]],
    case: capture.ExpectedCase,
    rows: Sequence[Mapping[str, str]],
    horizon: int,
) -> None:
    field_metrics = (
        ("released_qty", "released_qty", 28),
        ("produced_qty", "produced_qty", 28),
        ("wip_end_qty", "wip_end_qty", 7),
        ("stock_end_of_day", "finished_stock_end_qty", 7),
    )
    for field, metric, window in field_metrics:
        series = _dense_series(
            rows,
            horizon=horizon,
            item_column="item_id",
            value=lambda row, selected=field: _to_float(row[selected], selected),
        )
        for (node_id, item_id), values in sorted(series.items()):
            for applied_window, output in (
                (0, values),
                (window, rolling_mean(values, window)),
            ):
                _add_values(
                    samples,
                    definitions,
                    target_group=case.target_group,
                    candidate_id=case.candidate_id,
                    node_id=node_id,
                    item_id=item_id,
                    domain="production",
                    metric=metric,
                    window=applied_window,
                    values=output,
                )


def _add_input_stock_case(
    samples: dict[SampleKey, list[float]],
    definitions: set[tuple[str, str, str, int]],
    case: capture.ExpectedCase,
    rows: Sequence[Mapping[str, str]],
    horizon: int,
) -> None:
    series = _dense_series(
        rows,
        horizon=horizon,
        item_column="item_id",
        value=lambda row: _to_float(row["stock_end_of_day"], "stock entrant"),
    )
    for (node_id, item_id), values in sorted(series.items()):
        for window, output in ((0, values), (7, rolling_mean(values, 7))):
            _add_values(
                samples,
                definitions,
                target_group=case.target_group,
                candidate_id=case.candidate_id,
                node_id=node_id,
                item_id=item_id,
                domain="input_stock",
                metric="input_stock_end_qty",
                window=window,
                values=output,
            )


def _add_constraint_case(
    samples: dict[SampleKey, list[float]],
    definitions: set[tuple[str, str, str, int]],
    case: capture.ExpectedCase,
    rows: Sequence[Mapping[str, str]],
    horizon: int,
) -> None:
    required_keys = {
        (factory, f"item:{product}")
        for product, factory in capture.EXPECTED_PRODUCTS.items()
    }
    shortfall = {key: [0.0] * horizon for key in required_keys}
    input_shortage = {key: [0.0] * horizon for key in required_keys}
    for row in rows:
        key = (str(row["node_id"]), str(row["output_item_id"]))
        if key not in required_keys:
            continue
        day = int(row["day"])
        shortfall[key][day] = _to_float(
            row["shortfall_vs_lot_plan_qty"], "écart au plan de lot"
        )
        input_shortage[key][day] = (
            1.0 if str(row["binding_cause"]) == "input_shortage" else 0.0
        )
    for key in sorted(required_keys):
        node_id, item_id = key
        for metric, values in (
            ("lot_plan_shortfall_qty", shortfall[key]),
            ("input_shortage_indicator", input_shortage[key]),
        ):
            _add_values(
                samples,
                definitions,
                target_group=case.target_group,
                candidate_id=case.candidate_id,
                node_id=node_id,
                item_id=item_id,
                domain="constraint",
                metric=metric,
                window=0,
                values=values,
            )


def _rows_for_domain(
    *,
    target_group: str,
    candidate_id: str,
    domain: str,
    samples: Mapping[SampleKey, Sequence[float]],
    definitions: set[tuple[str, str, str, int]],
    horizon: int,
    expected_sample_count: int,
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    selected = sorted(
        definition
        for definition in definitions
        if DEFINITION_BY_KEY[(domain, definition[2], definition[3])].domain == domain
    )
    for node_id, item_id, metric, window in selected:
        definition = DEFINITION_BY_KEY[(domain, metric, window)]
        for day in range(horizon):
            values = list(
                samples.get(
                    (
                        target_group,
                        candidate_id,
                        day,
                        node_id,
                        item_id,
                        metric,
                        window,
                    ),
                    (),
                )
            )
            expected = 0 if window and day + 1 < window else expected_sample_count
            if len(values) != expected:
                raise CurveAggregationError(
                    f"Échantillon incomplet {domain}/{metric}/J{day}: "
                    f"{len(values)} != {expected}"
                )
            quantiles: tuple[str | float, str | float, str | float]
            if not values:
                quantiles = ("", "", "")
            else:
                quantiles = tuple(linear_quantile(values, q) for q in QUANTILES)  # type: ignore[assignment]
            rows.append(
                (
                    target_group,
                    candidate_id,
                    day,
                    node_id,
                    item_id,
                    metric,
                    definition.unit,
                    window,
                    len(values),
                    *quantiles,
                )
            )
    return rows


def _encode_output(rows: Sequence[tuple[Any, ...]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(OUTPUT_COLUMNS)
    writer.writerows(rows)
    return gzip.compress(stream.getvalue().encode("utf-8"), compresslevel=9, mtime=0)


def _write_output(path: Path, rows: Sequence[tuple[Any, ...]]) -> dict[str, Any]:
    compressed = _encode_output(rows)
    if path.exists() and capture.sha256_file(path) != capture.sha256_bytes(compressed):
        raise CurveAggregationError(f"Agrégat existant différent : {path}")
    if not path.exists():
        capture._atomic_write_bytes(path, compressed)
    return {
        "path": str(path.resolve()),
        "sha256": capture.sha256_file(path),
        "row_count": len(rows),
        "columns": list(OUTPUT_COLUMNS),
        "compression": "gzip_mtime_0_compresslevel_9",
    }


def _registered_inputs(output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = output_dir / "capture_contract.json"
    inventory_path = output_dir / "capture_inventory.json"
    contract = _read_json(contract_path)
    inventory = _read_json(inventory_path)
    contract_signature = _verify_signature(
        contract, "contract_signature", "contrat de capture"
    )
    _verify_signature(inventory, "inventory_signature", "inventaire de capture")
    if (
        inventory.get("status") != "complete"
        or inventory.get("contract_signature") != contract_signature
        or int(inventory.get("case_count") or -1)
        != int(contract.get("expected_case_count") or -2)
    ):
        raise CurveAggregationError("Capture complète non démontrée")
    # Revalidates every gzip, hash and per-case manifest before aggregation.
    capture.finalize_capture(contract, output_dir)
    return contract, inventory


def aggregate_capture(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    contract, inventory = _registered_inputs(output_dir)
    aggregate_dir = output_dir / AGGREGATE_SUBDIRECTORY
    aggregate_dir.mkdir(parents=True, exist_ok=True)
    aggregate_contract_unsigned: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "capture_contract_signature": contract["contract_signature"],
        "capture_inventory_signature": inventory["inventory_signature"],
        "capture_inventory_sha256": capture.sha256_file(
            output_dir / "capture_inventory.json"
        ),
        "horizon_days": int(contract["horizon_days"]),
        "quantile_method": "linear_type_7",
        "quantiles": list(QUANTILES),
        "rolling_contract": {
            "service_and_production_days": 28,
            "stock_backlog_wip_days": 7,
            "complete_windows_only": True,
            "order": "rolling_within_each_seed_then_quantiles_across_seeds",
        },
        "interpretation": (
            "Dispersion descriptive de simulations nominales indépendantes; "
            "ni probabilité fournisseur observée, ni intervalle de confiance."
        ),
    }
    aggregate_contract = {
        **aggregate_contract_unsigned,
        "aggregate_contract_signature": capture.stable_sha256(
            aggregate_contract_unsigned
        ),
    }
    aggregate_contract_path = aggregate_dir / "aggregate_contract.json"
    if aggregate_contract_path.exists():
        existing = _read_json(aggregate_contract_path)
        _verify_signature(
            existing, "aggregate_contract_signature", "contrat d'agrégation"
        )
        if existing != aggregate_contract:
            raise CurveAggregationError("Un autre contrat d'agrégation existe")
    else:
        if any(aggregate_dir.iterdir()):
            raise CurveAggregationError("Répertoire d'agrégation non enregistré")
        capture._atomic_write_json(aggregate_contract_path, aggregate_contract)

    cases = tuple(capture.ExpectedCase(**item) for item in contract["cases"])
    horizon = int(contract["horizon_days"])
    cases_by_group: dict[str, list[capture.ExpectedCase]] = defaultdict(list)
    for case in cases:
        cases_by_group[case.target_group].append(case)
    all_rows: dict[str, list[tuple[Any, ...]]] = {
        domain: [] for domain in ("service", "production", "input_stock", "constraint")
    }
    for target_group in sorted(cases_by_group):
        group_cases = sorted(cases_by_group[target_group], key=lambda case: case.seed)
        candidate_ids = {case.candidate_id for case in group_cases}
        if len(candidate_ids) != 1 or len({case.seed for case in group_cases}) != len(
            group_cases
        ):
            raise CurveAggregationError("État, candidat ou graines incohérents")
        candidate_id = next(iter(candidate_ids))
        samples: dict[SampleKey, list[float]] = defaultdict(list)
        definitions_by_domain: dict[str, set[tuple[str, str, str, int]]] = {
            domain: set()
            for domain in ("service", "production", "input_stock", "constraint")
        }
        for case in group_cases:
            service = _decompressed_snapshot(
                output_dir,
                case,
                "production_demand_service_daily.csv",
                horizon,
            )
            production = _decompressed_snapshot(
                output_dir,
                case,
                "production_output_products_daily.csv",
                horizon,
            )
            stocks = _decompressed_snapshot(
                output_dir,
                case,
                "production_input_stocks_daily.csv",
                horizon,
            )
            constraints = _decompressed_snapshot(
                output_dir,
                case,
                "production_constraint_daily.csv",
                horizon,
            )
            _add_service_case(
                samples,
                definitions_by_domain["service"],
                case,
                service,
                horizon,
            )
            _add_production_case(
                samples,
                definitions_by_domain["production"],
                case,
                production,
                horizon,
            )
            _add_input_stock_case(
                samples,
                definitions_by_domain["input_stock"],
                case,
                stocks,
                horizon,
            )
            _add_constraint_case(
                samples,
                definitions_by_domain["constraint"],
                case,
                constraints,
                horizon,
            )
        for domain in all_rows:
            all_rows[domain].extend(
                _rows_for_domain(
                    target_group=target_group,
                    candidate_id=candidate_id,
                    domain=domain,
                    samples=samples,
                    definitions=definitions_by_domain[domain],
                    horizon=horizon,
                    expected_sample_count=len(group_cases),
                )
            )

    files = []
    for domain, rows in sorted(all_rows.items()):
        path = aggregate_dir / f"{domain}_quantiles_daily.csv.gz"
        files.append({"domain": domain, **_write_output(path, rows)})
    unsigned: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "aggregate_contract_signature": aggregate_contract[
            "aggregate_contract_signature"
        ],
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "status": "complete",
        "state_count": len(cases_by_group),
        "case_count": len(cases),
        "horizon_days": horizon,
        "files": files,
        "metric_definitions": [
            {
                "domain": definition.domain,
                "metric": definition.metric,
                "unit": definition.unit,
                "rolling_window_days": definition.rolling_window_days,
                "calculation_fr": definition.calculation_fr,
            }
            for definition in METRIC_DEFINITIONS
        ],
        "interpretation": aggregate_contract["interpretation"],
    }
    manifest = {**unsigned, "manifest_signature": capture.stable_sha256(unsigned)}
    path = aggregate_dir / "aggregate_manifest.json"
    if path.exists():
        existing = _read_json(path)
        _verify_signature(existing, "manifest_signature", "manifeste d'agrégation")
        if existing != manifest:
            raise CurveAggregationError("Un manifeste d'agrégation différent existe")
        return existing
    capture._atomic_write_json(path, manifest)
    return manifest


def validate_aggregates(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _registered_inputs(output_dir)
    aggregate_dir = output_dir / AGGREGATE_SUBDIRECTORY
    contract = _read_json(aggregate_dir / "aggregate_contract.json")
    manifest = _read_json(aggregate_dir / "aggregate_manifest.json")
    contract_signature = _verify_signature(
        contract, "aggregate_contract_signature", "contrat d'agrégation"
    )
    _verify_signature(manifest, "manifest_signature", "manifeste d'agrégation")
    if (
        manifest.get("status") != "complete"
        or manifest.get("aggregate_contract_signature") != contract_signature
    ):
        raise CurveAggregationError("Agrégation non complète")
    for row in manifest.get("files") or []:
        path = Path(str(row.get("path") or "")).resolve()
        if (
            not path.is_relative_to(aggregate_dir.resolve())
            or not path.is_file()
            or capture.sha256_file(path) != row.get("sha256")
        ):
            raise CurveAggregationError(f"Sortie agrégée invalide : {path}")
        try:
            raw = gzip.decompress(path.read_bytes()).decode("utf-8")
        except (OSError, EOFError, UnicodeDecodeError) as exc:
            raise CurveAggregationError(f"Gzip agrégé invalide : {path}") from exc
        reader = csv.reader(io.StringIO(raw, newline=""))
        header = next(reader, None)
        rows = sum(1 for _ in reader)
        if tuple(header or ()) != OUTPUT_COLUMNS or rows != int(row["row_count"]):
            raise CurveAggregationError(f"Schéma/compte agrégé invalide : {path}")
    return {
        "valid": True,
        "manifest_path": str((aggregate_dir / "aggregate_manifest.json").resolve()),
        "manifest_signature": manifest["manifest_signature"],
        "case_count": manifest["case_count"],
        "state_count": manifest["state_count"],
        "file_count": len(manifest["files"]),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("aggregate", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "aggregate":
        result = aggregate_capture(args.output_dir)
    elif args.command == "validate":
        result = validate_aggregates(args.output_dir)
    else:  # pragma: no cover
        raise CurveAggregationError("Commande inconnue")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
