"""Non-invasive capture of compact daily curves from the V4 holdout.

The V4 calibration deliberately prunes large engine outputs after extracting its
signed evidence.  This sidecar is an *external* reader: it never imports itself
into the calibrated execution closure and never writes below the plan or run
directories.  It must be started before the holdout.

Polling cannot provide a transactional guarantee against a producer that may
create and delete a file between two directory scans.  The implementation makes
the remaining race small and fail-closed by keeping structurally complete,
double-read snapshots, refreshing them while the source changes, and accepting a
case only after the engine summary confirms the seed, graph and 720-day horizon.
On Windows, the safest non-invasive deployment is to run this watcher before the
holdout with a 20--50 ms interval.  ``ReadDirectoryChangesW`` can reduce wake-up
latency, but only a producer-side pre-prune acknowledgement would make capture
strictly lossless; changing that pinned producer is intentionally out of scope.
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
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "etudecas.supplier_holdout_curve_sidecar.v4"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
SNAPSHOT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.snapshot.v1"
CASE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case.v1"
PROGRESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.progress.v1"
INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.inventory.v1"

EXPECTED_TARGET_GROUPS = ("op_100", "op_93", "op_80")
EXPECTED_PRODUCTS = {
    "268091": "M-1810",
    "268967": "M-1430",
}
DEFAULT_HORIZON = 720
DEFAULT_POLL_SECONDS = 0.025
DEFAULT_STABILITY_SECONDS = 0.012
MAX_REPLACE_ATTEMPTS = 8
SEED_DIRECTORY_PATTERN = re.compile(r"^seed_(\d+)$")


class CurveSidecarError(RuntimeError):
    """Raised when a capture cannot satisfy the frozen sidecar contract."""


@dataclass(frozen=True)
class ExpectedCase:
    target_group: str
    candidate_key: str
    candidate_id: str
    seed: int
    graph_sha256: str

    @property
    def identity(self) -> tuple[str, int]:
        return self.candidate_id, self.seed


@dataclass(frozen=True)
class CsvSpec:
    filename: str
    required: bool
    columns: tuple[str, ...]
    key_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...]
    dense_by_key: bool


CSV_SPECS: tuple[CsvSpec, ...] = (
    CsvSpec(
        filename="production_demand_service_daily.csv",
        required=True,
        columns=(
            "day",
            "node_id",
            "item_id",
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
            "available_before_service_qty",
        ),
        key_columns=("node_id", "item_id"),
        numeric_columns=(
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
            "available_before_service_qty",
        ),
        dense_by_key=True,
    ),
    CsvSpec(
        filename="production_output_products_daily.csv",
        required=True,
        columns=(
            "day",
            "node_id",
            "item_id",
            "produced_qty",
            "executed_qty",
            "released_qty",
            "wip_end_qty",
            "cum_produced_qty",
            "stock_end_of_day",
        ),
        key_columns=("node_id", "item_id"),
        numeric_columns=(
            "produced_qty",
            "executed_qty",
            "released_qty",
            "wip_end_qty",
            "cum_produced_qty",
            "stock_end_of_day",
        ),
        dense_by_key=True,
    ),
    CsvSpec(
        filename="production_input_stocks_daily.csv",
        required=True,
        columns=(
            "day",
            "node_id",
            "item_id",
            "stock_before_production",
            "stock_end_of_day",
        ),
        key_columns=("node_id", "item_id"),
        numeric_columns=("stock_before_production", "stock_end_of_day"),
        dense_by_key=True,
    ),
    CsvSpec(
        filename="production_constraint_daily.csv",
        required=True,
        columns=(
            "day",
            "node_id",
            "output_item_id",
            "desired_qty",
            "planned_qty_after_lot_rule",
            "actual_qty",
            "cap_qty",
            "capacity_limit_mode",
            "max_from_inputs_qty",
            "binding_cause",
            "binding_input_item_id",
            "shortfall_vs_desired_qty",
            "shortfall_vs_lot_plan_qty",
            "lot_policy_mode",
            "lot_fixed_qty",
            "lot_min_qty",
            "lot_max_qty",
            "lot_multiple_qty",
            "max_lots_per_week",
            "started_lots_this_week",
            "requested_lot_starts",
            "actual_lot_starts",
            "campaign_requested_qty",
            "campaign_started_qty",
            "campaign_remaining_start_qty",
            "campaign_remaining_end_qty",
        ),
        key_columns=("node_id", "output_item_id"),
        numeric_columns=(
            "desired_qty",
            "planned_qty_after_lot_rule",
            "actual_qty",
            "cap_qty",
            "shortfall_vs_desired_qty",
            "shortfall_vs_lot_plan_qty",
            "campaign_requested_qty",
            "campaign_started_qty",
            "campaign_remaining_start_qty",
            "campaign_remaining_end_qty",
        ),
        # Constraint rows are intentionally sparse: no row means no production
        # decision to diagnose on that day.
        dense_by_key=False,
    ),
    CsvSpec(
        filename="first_simulation_daily.csv",
        required=False,
        columns=(
            "day",
            "demand",
            "served",
            "backlog_end",
            "arrivals_qty",
            "produced_qty",
            "shipped_qty",
            "inventory_total",
            "holding_cost_day",
            "warehouse_operating_cost_day",
            "inventory_risk_cost_day",
            "legacy_raw_holding_cost_day",
            "transport_cost_day",
            "opening_open_order_transport_cost_day",
            "external_procurement_transport_cost_day",
            "operational_transport_cost_day",
            "purchase_cost_day",
            "opening_open_order_purchase_cost_day",
            "external_procurement_purchase_cost_day",
            "operational_purchase_cost_day",
            "external_procured_ordered_qty",
            "external_procured_arrived_qty",
            "external_procured_rejected_qty",
            "estimated_source_ordered_qty",
            "estimated_source_arrived_qty",
            "estimated_source_rejected_qty",
            "supplier_capacity_binding_qty",
            "production_cost_day",
            "total_supply_cost_day",
        ),
        key_columns=(),
        numeric_columns=(
            "demand",
            "served",
            "backlog_end",
            "arrivals_qty",
            "produced_qty",
            "shipped_qty",
            "inventory_total",
        ),
        dense_by_key=True,
    ),
)
SPEC_BY_FILENAME = {spec.filename: spec for spec in CSV_SPECS}
SUMMARY_RELATIVE_PATH = Path("summaries") / "first_simulation_summary.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(MAX_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt + 1 == MAX_REPLACE_ATTEMPTS:
                    raise
                time.sleep(0.02 * (2**attempt))
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, raw)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurveSidecarError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise CurveSidecarError(f"Objet JSON attendu : {path}")
    return payload


def _verify_signature(payload: Mapping[str, Any], field: str, label: str) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise CurveSidecarError(f"Signature invalide : {label}")
    return signature


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _case_relative_dir(case: ExpectedCase) -> Path:
    return (
        Path("snapshots") / case.target_group / case.candidate_id / f"seed_{case.seed}"
    )


def _snapshot_paths(
    output_dir: Path, case: ExpectedCase, filename: str
) -> tuple[Path, Path]:
    base = output_dir / _case_relative_dir(case)
    return base / f"{filename}.gz", base / f"{filename}.meta.json"


def _summary_paths(output_dir: Path, case: ExpectedCase) -> tuple[Path, Path]:
    base = output_dir / _case_relative_dir(case)
    return (
        base / "first_simulation_summary.json.gz",
        base / "first_simulation_summary.json.meta.json",
    )


def _case_manifest_path(output_dir: Path, case: ExpectedCase) -> Path:
    return output_dir / _case_relative_dir(case) / "case_manifest.json"


def _validate_candidate_component(value: str, label: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value:
        raise CurveSidecarError(f"{label} ne peut pas former un chemin sûr")
    return value


def load_official_cases(plan_dir: Path, run_dir: Path) -> tuple[ExpectedCase, ...]:
    """Load the frozen 3 x 30 holdout identity through the V4 validator."""

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v4 as refinement,
    )

    plan = refinement.validate_plan(
        plan_dir.resolve(), verify_runtime_dependencies=True
    )
    jobs = refinement._stage_jobs(plan, run_dir.resolve(), "holdout")
    cases = tuple(
        ExpectedCase(
            target_group=candidate.target_group,
            candidate_key=candidate.key,
            candidate_id=_validate_candidate_component(
                candidate.candidate_id, "candidate_id"
            ),
            seed=int(seed),
            graph_sha256=str(plan.manifest["inventory"][candidate.key]["graph_sha256"]),
        )
        for candidate, seed in jobs
    )
    if (
        len(cases) != 90
        or {case.target_group for case in cases} != set(EXPECTED_TARGET_GROUPS)
        or any(
            sum(case.target_group == group for case in cases) != 30
            for group in EXPECTED_TARGET_GROUPS
        )
        or len({case.identity for case in cases}) != len(cases)
    ):
        raise CurveSidecarError("Le holdout attendu n'est pas exactement 3 x 30 cas")
    return cases


def build_contract(
    *,
    plan_dir: Path,
    run_dir: Path,
    output_dir: Path,
    cases: Sequence[ExpectedCase],
    horizon: int = DEFAULT_HORIZON,
) -> dict[str, Any]:
    plan_dir = plan_dir.resolve()
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    if horizon < 1:
        raise CurveSidecarError("L'horizon doit être positif")
    if _paths_overlap(output_dir, plan_dir) or _paths_overlap(output_dir, run_dir):
        raise CurveSidecarError(
            "La sortie sidecar doit être extérieure au plan et au run V4"
        )
    plan_path = plan_dir / "refinement_plan.json"
    run_manifest_path = run_dir / "run_manifest.json"
    if not plan_path.is_file() or not run_manifest_path.is_file():
        raise CurveSidecarError("Plan ou manifeste de run V4 manquant")
    identities = [case.identity for case in cases]
    if not cases or len(set(identities)) != len(identities):
        raise CurveSidecarError("Identités candidate/graine absentes ou dupliquées")
    unsigned: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "created_at_utc": _now(),
        "interpretation": (
            "Courbes de simulations nominales; elles ne mesurent ni une "
            "performance fournisseur observée ni une probabilité historique."
        ),
        "capture_guarantee": {
            "strictly_lossless": False,
            "reason": (
                "Aucun acquittement transactionnel n'existe entre le producteur "
                "épinglé et ce lecteur externe avant l'élagage."
            ),
            "fail_closed": True,
            "windows_recommendation": (
                "Démarrer avant le holdout, scruter toutes les 20 à 50 ms; "
                "ReadDirectoryChangesW peut réduire la latence mais seule une "
                "barrière pré-élagage côté producteur garantirait zéro perte."
            ),
        },
        "plan": {
            "directory": str(plan_dir),
            "manifest_path": str(plan_path),
            "manifest_sha256": sha256_file(plan_path),
        },
        "run": {
            "directory": str(run_dir),
            "manifest_path": str(run_manifest_path),
            "manifest_sha256": sha256_file(run_manifest_path),
            "watched_relative_root": "engine_attempts/holdout",
        },
        "output_directory": str(output_dir),
        "horizon_days": horizon,
        "required_file_count_per_case": sum(spec.required for spec in CSV_SPECS),
        "csv_specs": [
            {
                **asdict(spec),
                "columns": list(spec.columns),
                "key_columns": list(spec.key_columns),
                "numeric_columns": list(spec.numeric_columns),
            }
            for spec in CSV_SPECS
        ],
        "expected_case_count": len(cases),
        "cases": [asdict(case) for case in cases],
    }
    return {**unsigned, "contract_signature": stable_sha256(unsigned)}


def _contract_fixed_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("created_at_utc", None)
    result.pop("contract_signature", None)
    return result


def register_contract(output_dir: Path, contract: Mapping[str, Any]) -> None:
    output_dir = output_dir.resolve()
    path = output_dir / "capture_contract.json"
    if path.exists():
        existing = _read_json(path)
        _verify_signature(existing, "contract_signature", "contrat sidecar existant")
        if _contract_fixed_view(existing) != _contract_fixed_view(contract):
            raise CurveSidecarError("La sortie appartient à un autre contrat sidecar")
        return
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CurveSidecarError(
            "Refus d'utiliser une sortie non vide et non enregistrée"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, contract)


def _finite_nonnegative(raw: str, label: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise CurveSidecarError(f"Valeur non numérique pour {label}") from exc
    if not math.isfinite(value) or value < -1e-7:
        raise CurveSidecarError(f"Valeur non finie ou négative pour {label}")
    return value


def validate_csv_bytes(raw: bytes, spec: CsvSpec, horizon: int) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CurveSidecarError(f"CSV non UTF-8 : {spec.filename}") from exc
    if raw and not raw.endswith((b"\n", b"\r")):
        raise CurveSidecarError(f"Dernière ligne incomplète : {spec.filename}")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != spec.columns:
        raise CurveSidecarError(f"Schéma CSV inattendu : {spec.filename}")
    expected_days = set(range(horizon))
    days: set[int] = set()
    series_days: dict[tuple[str, ...], set[int]] = {}
    seen_rows: set[tuple[int, tuple[str, ...]]] = set()
    row_count = 0
    for row in reader:
        try:
            day = int(str(row.get("day", "")))
        except ValueError as exc:
            raise CurveSidecarError(f"Jour invalide : {spec.filename}") from exc
        if day not in expected_days:
            raise CurveSidecarError(f"Jour hors horizon : {spec.filename}")
        key = tuple(str(row.get(column, "")) for column in spec.key_columns)
        if any(not part for part in key):
            raise CurveSidecarError(f"Clé de série vide : {spec.filename}")
        row_key = (day, key)
        if row_key in seen_rows:
            raise CurveSidecarError(f"Ligne journalière dupliquée : {spec.filename}")
        seen_rows.add(row_key)
        days.add(day)
        series_days.setdefault(key, set()).add(day)
        for column in spec.numeric_columns:
            _finite_nonnegative(str(row.get(column, "")), f"{spec.filename}/{column}")
        row_count += 1
    if row_count == 0:
        raise CurveSidecarError(f"CSV vide : {spec.filename}")
    if spec.dense_by_key:
        if days != expected_days or any(
            series != expected_days for series in series_days.values()
        ):
            raise CurveSidecarError(f"Série journalière incomplète : {spec.filename}")
    elif not days.issubset(expected_days):
        raise CurveSidecarError(f"Jours épars invalides : {spec.filename}")

    keys = set(series_days)
    if spec.filename == "production_demand_service_daily.csv":
        required = {("C-XXXXX", f"item:{product}") for product in EXPECTED_PRODUCTS}
        if not required.issubset(keys):
            raise CurveSidecarError("Les deux produits finis manquent au service")
    elif spec.filename == "production_output_products_daily.csv":
        required = {
            (factory, f"item:{product}")
            for product, factory in EXPECTED_PRODUCTS.items()
        }
        if not required.issubset(keys):
            raise CurveSidecarError("Les deux couples usine/produit manquent")
    elif spec.filename == "production_constraint_daily.csv":
        required = {
            (factory, f"item:{product}")
            for product, factory in EXPECTED_PRODUCTS.items()
        }
        if not required.issubset(keys):
            raise CurveSidecarError("Les contraintes des deux produits manquent")

    return {
        "row_count": row_count,
        "day_count": len(days),
        "minimum_day": min(days),
        "maximum_day": max(days),
        "series_count": len(series_days),
        "columns": list(spec.columns),
    }


def validate_summary_bytes(
    raw: bytes, *, case: ExpectedCase, horizon: int
) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurveSidecarError("Résumé moteur incomplet ou illisible") from exc
    if not isinstance(payload, dict):
        raise CurveSidecarError("Résumé moteur non objet")
    policy = payload.get("policy") or {}
    if (
        int(payload.get("sim_days") or -1) != horizon
        or payload.get("scenario_id") != "scn:BASE"
        or int(policy.get("seed") or -1) != case.seed
        or payload.get("input_sha256") != case.graph_sha256
    ):
        raise CurveSidecarError(
            "Résumé moteur incohérent avec graine/graphe/scénario/horizon"
        )
    return {
        "sim_days": horizon,
        "scenario_id": "scn:BASE",
        "seed": case.seed,
        "input_sha256": case.graph_sha256,
    }


@dataclass(frozen=True)
class StableRead:
    raw: bytes
    source_size: int
    source_mtime_ns: int
    source_sha256: str


def _one_stable_read(path: Path) -> StableRead:
    before = path.stat()
    with path.open("rb") as stream:
        raw = stream.read()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != after.st_size
    ):
        raise CurveSidecarError("Source modifiée pendant la lecture")
    return StableRead(
        raw=raw,
        source_size=after.st_size,
        source_mtime_ns=after.st_mtime_ns,
        source_sha256=sha256_bytes(raw),
    )


def stable_double_read(path: Path, stability_seconds: float) -> StableRead:
    """Read the same closed-looking source twice; never accept one observation."""

    first = _one_stable_read(path)
    if stability_seconds > 0:
        time.sleep(stability_seconds)
    second = _one_stable_read(path)
    if (
        first.source_size != second.source_size
        or first.source_mtime_ns != second.source_mtime_ns
        or first.source_sha256 != second.source_sha256
    ):
        raise CurveSidecarError("Source non stabilisée entre deux lectures")
    return second


def _snapshot_metadata(
    *,
    case: ExpectedCase,
    source: Path,
    destination: Path,
    read: StableRead,
    validation: Mapping[str, Any],
    kind: str,
) -> tuple[bytes, dict[str, Any]]:
    compressed = gzip.compress(read.raw, compresslevel=9, mtime=0)
    unsigned: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "kind": kind,
        "target_group": case.target_group,
        "candidate_key": case.candidate_key,
        "candidate_id": case.candidate_id,
        "seed": case.seed,
        "graph_sha256": case.graph_sha256,
        "source_path": str(source.resolve()),
        "source_size": read.source_size,
        "source_mtime_ns": read.source_mtime_ns,
        "source_sha256": read.source_sha256,
        "snapshot_path": str(destination.resolve()),
        "snapshot_gzip_sha256": sha256_bytes(compressed),
        "snapshot_uncompressed_bytes": len(read.raw),
        "compression": "gzip_mtime_0_compresslevel_9",
        "validation": dict(validation),
        "captured_at_utc": _now(),
    }
    return compressed, {**unsigned, "snapshot_signature": stable_sha256(unsigned)}


def _validate_stored_snapshot(data_path: Path, meta_path: Path) -> dict[str, Any]:
    if data_path.is_file() != meta_path.is_file():
        raise CurveSidecarError(f"Instantané partiel : {data_path}")
    if not data_path.is_file():
        raise FileNotFoundError(data_path)
    metadata = _read_json(meta_path)
    _verify_signature(metadata, "snapshot_signature", str(meta_path))
    if (
        metadata.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
        or Path(str(metadata.get("snapshot_path") or "")).resolve()
        != data_path.resolve()
        or sha256_file(data_path) != metadata.get("snapshot_gzip_sha256")
    ):
        raise CurveSidecarError(f"Instantané altéré : {data_path}")
    try:
        raw = gzip.decompress(data_path.read_bytes())
    except (OSError, EOFError) as exc:
        raise CurveSidecarError(f"Gzip invalide : {data_path}") from exc
    if len(raw) != int(
        metadata.get("snapshot_uncompressed_bytes") or -1
    ) or sha256_bytes(raw) != metadata.get("source_sha256"):
        raise CurveSidecarError(f"Contenu décompressé altéré : {data_path}")
    return metadata


def _capture_file(
    *,
    source: Path,
    data_path: Path,
    meta_path: Path,
    case: ExpectedCase,
    horizon: int,
    stability_seconds: float,
    spec: CsvSpec | None,
) -> dict[str, Any]:
    read = stable_double_read(source, stability_seconds)
    if spec is None:
        validation = validate_summary_bytes(read.raw, case=case, horizon=horizon)
        kind = "engine_summary"
    else:
        validation = validate_csv_bytes(read.raw, spec, horizon)
        kind = "daily_csv"
    compressed, metadata = _snapshot_metadata(
        case=case,
        source=source,
        destination=data_path,
        read=read,
        validation=validation,
        kind=kind,
    )
    _atomic_write_bytes(data_path, compressed)
    _atomic_write_json(meta_path, metadata)
    return _validate_stored_snapshot(data_path, meta_path)


def _source_case_dir(data_dir: Path) -> Path:
    return data_dir.parent


def _parse_source_identity(data_dir: Path) -> tuple[str, int]:
    seed_name = data_dir.parent.name
    match = SEED_DIRECTORY_PATTERN.fullmatch(seed_name)
    if match is None:
        raise CurveSidecarError(f"Répertoire graine invalide : {data_dir}")
    candidate_id = data_dir.parent.parent.name
    _validate_candidate_component(candidate_id, "candidate_id source")
    return candidate_id, int(match.group(1))


def _discover_data_dirs(run_dir: Path) -> tuple[Path, ...]:
    root = (run_dir / "engine_attempts" / "holdout").resolve()
    if not root.exists():
        return ()
    paths: list[Path] = []
    for path in root.glob("*/*/cases/*/seed_*/data"):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise CurveSidecarError("Un chemin source sort du holdout")
        if resolved.is_dir():
            paths.append(resolved)
    return tuple(sorted(set(paths), key=str))


def _load_meta_if_present(data_path: Path, meta_path: Path) -> dict[str, Any] | None:
    if not data_path.exists() and not meta_path.exists():
        return None
    # An interrupted atomic pair publication may leave exactly one of the two
    # files.  It is not evidence and can be safely replaced from the source.
    if data_path.is_file() != meta_path.is_file():
        return None
    return _validate_stored_snapshot(data_path, meta_path)


def _metadata_matches_source(metadata: Mapping[str, Any], source: Path) -> bool:
    try:
        stat = source.stat()
    except FileNotFoundError:
        return True
    return (
        int(metadata.get("source_size") or -1) == stat.st_size
        and int(metadata.get("source_mtime_ns") or -1) == stat.st_mtime_ns
    )


def _case_manifest(
    *,
    contract_signature: str,
    output_dir: Path,
    case: ExpectedCase,
) -> dict[str, Any] | None:
    summary_data, summary_meta = _summary_paths(output_dir, case)
    try:
        summary = _validate_stored_snapshot(summary_data, summary_meta)
    except FileNotFoundError:
        return None
    files: list[dict[str, Any]] = []
    missing_required: list[str] = []
    for spec in CSV_SPECS:
        data_path, meta_path = _snapshot_paths(output_dir, case, spec.filename)
        try:
            metadata = _validate_stored_snapshot(data_path, meta_path)
        except FileNotFoundError:
            if spec.required:
                missing_required.append(spec.filename)
            continue
        files.append(
            {
                "filename": spec.filename,
                "required": spec.required,
                "snapshot_path": str(data_path.resolve()),
                "snapshot_gzip_sha256": metadata["snapshot_gzip_sha256"],
                "source_sha256": metadata["source_sha256"],
                "row_count": metadata["validation"]["row_count"],
            }
        )
    if missing_required:
        return None
    unsigned: dict[str, Any] = {
        "schema_version": CASE_SCHEMA_VERSION,
        "contract_signature": contract_signature,
        **asdict(case),
        "summary": {
            "snapshot_path": str(summary_data.resolve()),
            "snapshot_gzip_sha256": summary["snapshot_gzip_sha256"],
            "source_sha256": summary["source_sha256"],
        },
        "files": sorted(files, key=lambda item: item["filename"]),
        "required_files_complete": True,
        "completed_at_utc": _now(),
    }
    return {**unsigned, "case_signature": stable_sha256(unsigned)}


def _validate_existing_case_manifest(
    path: Path, *, contract_signature: str, case: ExpectedCase
) -> dict[str, Any]:
    payload = _read_json(path)
    _verify_signature(payload, "case_signature", str(path))
    if (
        payload.get("schema_version") != CASE_SCHEMA_VERSION
        or payload.get("contract_signature") != contract_signature
        or payload.get("target_group") != case.target_group
        or payload.get("candidate_key") != case.candidate_key
        or payload.get("candidate_id") != case.candidate_id
        or int(payload.get("seed") or -1) != case.seed
        or payload.get("graph_sha256") != case.graph_sha256
        or payload.get("required_files_complete") is not True
    ):
        raise CurveSidecarError(f"Manifeste de cas incohérent : {path}")
    return payload


class CurveCaptureWatcher:
    """Restartable, fail-closed watcher for one frozen holdout contract."""

    def __init__(
        self,
        *,
        contract: Mapping[str, Any],
        output_dir: Path,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        stability_seconds: float = DEFAULT_STABILITY_SECONDS,
    ) -> None:
        _verify_signature(contract, "contract_signature", "contrat sidecar")
        if poll_seconds <= 0 or stability_seconds < 0:
            raise CurveSidecarError("Intervalles de surveillance invalides")
        self.contract = dict(contract)
        self.contract_signature = str(contract["contract_signature"])
        self.output_dir = output_dir.resolve()
        self.run_dir = Path(str(contract["run"]["directory"])).resolve()
        self.horizon = int(contract["horizon_days"])
        self.poll_seconds = poll_seconds
        self.stability_seconds = stability_seconds
        self.cases = tuple(ExpectedCase(**item) for item in contract["cases"])
        self.expected = {case.identity: case for case in self.cases}
        if len(self.expected) != len(self.cases):
            raise CurveSidecarError("Cas attendus dupliqués")
        self.last_errors: dict[str, str] = {}

    def _capture_source_case(self, data_dir: Path, case: ExpectedCase) -> None:
        source_case = _source_case_dir(data_dir)
        summary_source = source_case / SUMMARY_RELATIVE_PATH
        summary_data, summary_meta = _summary_paths(self.output_dir, case)
        if summary_source.is_file():
            existing = _load_meta_if_present(summary_data, summary_meta)
            if existing is None or not _metadata_matches_source(
                existing, summary_source
            ):
                _capture_file(
                    source=summary_source,
                    data_path=summary_data,
                    meta_path=summary_meta,
                    case=case,
                    horizon=self.horizon,
                    stability_seconds=self.stability_seconds,
                    spec=None,
                )

        for spec in CSV_SPECS:
            source = data_dir / spec.filename
            if not source.is_file():
                continue
            data_path, meta_path = _snapshot_paths(self.output_dir, case, spec.filename)
            existing = _load_meta_if_present(data_path, meta_path)
            if existing is None or not _metadata_matches_source(existing, source):
                _capture_file(
                    source=source,
                    data_path=data_path,
                    meta_path=meta_path,
                    case=case,
                    horizon=self.horizon,
                    stability_seconds=self.stability_seconds,
                    spec=spec,
                )

        manifest_path = _case_manifest_path(self.output_dir, case)
        if not manifest_path.exists():
            manifest = _case_manifest(
                contract_signature=self.contract_signature,
                output_dir=self.output_dir,
                case=case,
            )
            if manifest is not None:
                _atomic_write_json(manifest_path, manifest)

    def _completed_cases(self) -> dict[tuple[str, int], dict[str, Any]]:
        completed: dict[tuple[str, int], dict[str, Any]] = {}
        for case in self.cases:
            path = _case_manifest_path(self.output_dir, case)
            if path.exists():
                completed[case.identity] = _validate_existing_case_manifest(
                    path,
                    contract_signature=self.contract_signature,
                    case=case,
                )
        return completed

    def scan_once(self) -> int:
        discovered: dict[tuple[str, int], list[Path]] = {}
        for data_dir in _discover_data_dirs(self.run_dir):
            identity = _parse_source_identity(data_dir)
            if identity not in self.expected:
                raise CurveSidecarError(
                    f"Cas holdout inattendu dans engine_attempts : {identity}"
                )
            discovered.setdefault(identity, []).append(data_dir)

        completed = self._completed_cases()
        for identity, data_dirs in discovered.items():
            if identity in completed:
                continue
            case = self.expected[identity]
            for data_dir in data_dirs:
                try:
                    self._capture_source_case(data_dir, case)
                except (FileNotFoundError, PermissionError, CurveSidecarError) as exc:
                    # A writer or pruner may win this individual observation.  A
                    # later poll retries; structural conflicts remain visible in
                    # progress and become fatal at timeout/finalization.
                    self.last_errors[f"{case.candidate_id}/seed_{case.seed}"] = str(exc)
        completed = self._completed_cases()
        self._write_progress(len(completed), len(discovered))
        return len(completed)

    def _write_progress(self, completed: int, discovered: int) -> None:
        unsigned: dict[str, Any] = {
            "schema_version": PROGRESS_SCHEMA_VERSION,
            "contract_signature": self.contract_signature,
            "status": "completed" if completed == len(self.cases) else "watching",
            "expected_cases": len(self.cases),
            "completed_cases": completed,
            "remaining_cases": len(self.cases) - completed,
            "currently_discovered_source_cases": discovered,
            "last_transient_errors": dict(sorted(self.last_errors.items())),
            "updated_at_utc": _now(),
        }
        _atomic_write_json(
            self.output_dir / "capture_progress.json",
            {**unsigned, "progress_signature": stable_sha256(unsigned)},
        )

    def watch(self, *, timeout_seconds: float | None = None) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            completed = self.scan_once()
            if completed == len(self.cases):
                return finalize_capture(self.contract, self.output_dir)
            if (
                timeout_seconds is not None
                and time.monotonic() - started >= timeout_seconds
            ):
                raise CurveSidecarError(
                    f"Délai dépassé : {completed}/{len(self.cases)} cas capturés"
                )
            time.sleep(self.poll_seconds)


def finalize_capture(contract: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    """Verify all snapshots and write one immutable compact inventory."""

    signature = _verify_signature(contract, "contract_signature", "contrat sidecar")
    output_dir = output_dir.resolve()
    cases = tuple(ExpectedCase(**item) for item in contract["cases"])
    rows: list[dict[str, Any]] = []
    for case in cases:
        path = _case_manifest_path(output_dir, case)
        if not path.is_file():
            raise CurveSidecarError(
                f"Capture incomplète : {case.candidate_id}/seed_{case.seed}"
            )
        manifest = _validate_existing_case_manifest(
            path, contract_signature=signature, case=case
        )
        summary_data, summary_meta = _summary_paths(output_dir, case)
        _validate_stored_snapshot(summary_data, summary_meta)
        for file_row in manifest["files"]:
            data_path, meta_path = _snapshot_paths(
                output_dir, case, file_row["filename"]
            )
            metadata = _validate_stored_snapshot(data_path, meta_path)
            if (
                metadata["snapshot_gzip_sha256"] != file_row["snapshot_gzip_sha256"]
                or metadata["source_sha256"] != file_row["source_sha256"]
            ):
                raise CurveSidecarError("Inventaire de cas et instantané divergent")
        rows.append(
            {
                "target_group": case.target_group,
                "candidate_key": case.candidate_key,
                "candidate_id": case.candidate_id,
                "seed": case.seed,
                "case_manifest_path": str(path.resolve()),
                "case_manifest_sha256": sha256_file(path),
                "case_signature": manifest["case_signature"],
                "captured_csv_count": len(manifest["files"]),
            }
        )
    if len(rows) != int(contract["expected_case_count"]):
        raise CurveSidecarError("Nombre final de cas incohérent")
    unsigned: dict[str, Any] = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "contract_signature": signature,
        "status": "complete",
        "interpretation": contract["interpretation"],
        "capture_guarantee": contract["capture_guarantee"],
        "case_count": len(rows),
        "cases": sorted(rows, key=lambda row: (row["target_group"], row["seed"])),
        "completed_at_utc": _now(),
    }
    payload = {**unsigned, "inventory_signature": stable_sha256(unsigned)}
    path = output_dir / "capture_inventory.json"
    if path.exists():
        existing = _read_json(path)
        _verify_signature(existing, "inventory_signature", "inventaire sidecar")
        comparable_existing = dict(existing)
        comparable_payload = dict(payload)
        comparable_existing.pop("completed_at_utc", None)
        comparable_payload.pop("completed_at_utc", None)
        comparable_existing.pop("inventory_signature", None)
        comparable_payload.pop("inventory_signature", None)
        if comparable_existing != comparable_payload:
            raise CurveSidecarError("Un inventaire final différent existe déjà")
        return existing
    _atomic_write_json(path, payload)
    return payload


def _wait_for_cases(
    plan_dir: Path,
    run_dir: Path,
    *,
    timeout_seconds: float | None,
) -> tuple[ExpectedCase, ...]:
    started = time.monotonic()
    selection_path = run_dir.resolve() / "development_selection.json"
    while not selection_path.is_file():
        if (
            timeout_seconds is not None
            and time.monotonic() - started >= timeout_seconds
        ):
            raise CurveSidecarError(
                "La sélection de développement n'est pas devenue disponible"
            )
        # Do not repeatedly hash the 44 pinned dependencies while development
        # is still running.  The atomic selection file is the readiness marker;
        # the full scientific validation is performed once it exists.
        time.sleep(1.0)
    try:
        return load_official_cases(plan_dir, run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise CurveSidecarError(
            "La sélection V4 existe mais ne valide pas le holdout 3 x 30"
        ) from exc


def run_watcher(
    *,
    plan_dir: Path,
    run_dir: Path,
    output_dir: Path,
    poll_seconds: float,
    stability_seconds: float,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    cases = _wait_for_cases(plan_dir, run_dir, timeout_seconds=timeout_seconds)
    contract = build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        cases=cases,
    )
    register_contract(output_dir, contract)
    registered = _read_json(output_dir / "capture_contract.json")
    watcher = CurveCaptureWatcher(
        contract=registered,
        output_dir=output_dir,
        poll_seconds=poll_seconds,
        stability_seconds=stability_seconds,
    )
    return watcher.watch(timeout_seconds=timeout_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    watch = subparsers.add_parser("watch")
    watch.add_argument("--plan-dir", type=Path, required=True)
    watch.add_argument("--run-dir", type=Path, required=True)
    watch.add_argument("--output-dir", type=Path, required=True)
    watch.add_argument("--poll-ms", type=float, default=DEFAULT_POLL_SECONDS * 1000)
    watch.add_argument(
        "--stability-ms", type=float, default=DEFAULT_STABILITY_SECONDS * 1000
    )
    watch.add_argument(
        "--timeout-seconds",
        type=float,
        default=0.0,
        help="0 = attente illimitée",
    )
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "watch":
        result = run_watcher(
            plan_dir=args.plan_dir,
            run_dir=args.run_dir,
            output_dir=args.output_dir,
            poll_seconds=args.poll_ms / 1000.0,
            stability_seconds=args.stability_ms / 1000.0,
            timeout_seconds=(
                None if args.timeout_seconds == 0 else args.timeout_seconds
            ),
        )
    elif args.command == "finalize":
        contract = _read_json(args.output_dir / "capture_contract.json")
        result = finalize_capture(contract, args.output_dir)
    else:  # pragma: no cover - argparse enforces the command set.
        raise CurveSidecarError("Commande inconnue")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
