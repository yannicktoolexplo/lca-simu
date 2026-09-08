#!/usr/bin/env python3
"""Confirmatory V7 validation of one fixed three-state supplier triplet.

V6 is used only as design provenance.  V7 freezes the already selected
OP100/OP93/OP80 graphs, evaluates them on 150 entirely new common seed blocks,
and permits no candidate selection or retuning.  The runner is additive,
restartable from signed case evidence, retains deterministic compact service
curves, and never decides from the 30/60/90/120-case status checkpoints.

Importing this module never imports or starts the simulation engine.
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
import random
import re
import shutil
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = "etudecas.fixed_triplet_confirmation.v7"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan.v1"
CASE_REGISTRY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_registry.v1"
RUN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.run.v1"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence.v1"
PROGRESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.progress.v1"
CHECKPOINT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.descriptive_checkpoint.v1"
RESULT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.result.v1"
CURVE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.compact_service_curve.v1"
BUNDLE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.retained_engine_bundle.v1"

V6_PLAN_SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v6.plan"
V6_SELECTION_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v6.development_selection"
)
V6_SUCCESS_STATUS = "development_selected_pending_separate_fresh_holdout_protocol"
OFFICIAL_V6_EXECUTION_MODE = "official_v6_additive_execute_candidate"

DEFAULT_ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_V6_PLAN = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_plan_20260905_v6"
)
DEFAULT_V6_RUN = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_run_20260905_v6"
)
DEFAULT_V6_HOLDOUT_RESULT = (
    DEFAULT_ARTIFACT_ROOT
    / "supplier_v6_fresh_holdout_run_20260905"
    / "holdout_result.json"
)
DEFAULT_RNG_AUDIT_DIR = (
    DEFAULT_ARTIFACT_ROOT / "supplier_v6_rng_pairing_audit_20260905_v1"
)
DEFAULT_PLAN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_fixed_triplet_confirmation_plan_20260905_v7"
)
DEFAULT_RUN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_fixed_triplet_confirmation_run_20260905_v7"
)

OFFICIAL_V6_PLAN_SHA256 = (
    "9135763988ac198b8e70edf57025b8967820a550f67b7383fd74271d5debd6c9"
)
OFFICIAL_V6_SELECTION_SHA256 = (
    "163b7a50dd56911a6e135a147fccc38c1395b4f882ced487051a5d4747c07e47"
)
OFFICIAL_V6_HOLDOUT_RESULT_SHA256 = (
    "c972e1cb72759c6dd562182d5a46e5d61e01f08ae4895fa1df1deb29891a579c"
)
OFFICIAL_RNG_AUDIT_MANIFEST_SHA256 = (
    "f6dccd65ec4d4c7bc6610a89fef569b2b1ce91dbd630cc54d5e36fb2aba8d03e"
)
OFFICIAL_RNG_AUDIT_SIGNATURE = (
    "82e9510a7703f6bfaf6f804745e3482897d423572b1588d630ba818fe2252d8a"
)
PINNED_V6_MODULE_SHA256 = {
    "supplier_balanced_product_delay_multiseed_refinement_v6.py": (
        "a12a835d376d17a2fd8fee54bb31bc37aa228a542da5417099bb267f2fe9847c"
    ),
    "supplier_fresh_holdout_v6.py": (
        "bae2589fa99f18cc1237aece1e5db9ae22a25882203b280d41f800c8fab181f2"
    ),
    "tests/test_supplier_balanced_product_delay_multiseed_refinement_v6.py": (
        "d3c039ea25556606cb6e3ff4546daf77ad13f56f51a6f39bb3f310f9be2d47c2"
    ),
    "tests/test_supplier_v6_completion_path.py": (
        "3b43186935c27debbfbe7ea0220fbb312c07f41f8cc1333103f36bd4b61326a2"
    ),
}

V5_V6_DEVELOPMENT_SEEDS = tuple(range(340287, 340317))
V5_V6_HOLDOUT_SEEDS = (
    573960646,
    1871757092,
    1745052434,
    1160236806,
    92478021,
    1394133310,
    1596008569,
    1416403695,
    1492750790,
    1316742469,
    1332985495,
    1408401338,
    1869291112,
    12328805,
    1374528760,
    434799925,
    1796420146,
    55195456,
    1146050562,
    583480470,
    1369666196,
    1545515706,
    43087084,
    1248984977,
    887386588,
    1734584754,
    1775564575,
    508903655,
    546039346,
    466329796,
)
OTHER_PRIOR_RANDOM_SEEDS = (
    340281,
    340282,
    340283,
    340284,
    340285,
    340286,
    900659036,
)
PRIOR_SEEDS = frozenset(
    (*V5_V6_DEVELOPMENT_SEEDS, *V5_V6_HOLDOUT_SEEDS, *OTHER_PRIOR_RANDOM_SEEDS)
)
V7_VALIDATION_SEED_DOMAIN = "ETUDECAS-V7-FIXED-TRIPLET-VALIDATION-20260905"
VALIDATION_SEED_COUNT = 150
MAX_ENGINE_SEED = 2_147_483_646
EXPECTED_CASES = 3 * VALIDATION_SEED_COUNT
MILESTONES = (30, 60, 90, 120, 150)

PRODUCTS = ("268091", "268967")
MEASURES = ("global", *PRODUCTS)
TARGETS = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}
STATE_ORDER = tuple(TARGETS)
SERVICE_DAYS = 720
GLOBAL_BANDS = {"op_93": (91.5, 94.5), "op_80": (78.5, 81.5)}
OP100_MINIMUM_PCT = 98.5
PRODUCT_GAP_MAX_PP = 5.0
BOOTSTRAP_REPLICATES = 50_000
BOOTSTRAP_SEED = 2_026_090_507
GLOBAL_INTERVAL_CONFIDENCE = 0.90
OP100_LOWER_CONFIDENCE = 0.95
ORDER_FAMILY_CONFIDENCE = 0.95
ORDER_COMPARISON_COUNT = 6

OFFICIAL_EXECUTION_MODE = "official_v7_fixed_triplet_fresh_validation"
TEST_ONLY_EXECUTION_MODE = "test_only_v7_injected_executor"
ACCEPTED_STATUS = "accepted_fixed_triplet_confirmation_v7"
REJECTED_STATUS = "rejected_fixed_triplet_confirmation_v7_no_retuning"

INTERPRETATION = (
    "Résultats simulés sous hypothèses; ni performance fournisseur observée, "
    "ni probabilité historique d'incident. V6 fournit le dessin des trois "
    "états, jamais une observation réutilisée comme preuve V7."
)
CRN_LIMIT = (
    "Les trois états partagent chaque graine comme bloc statistique. Les "
    "décisions physiques pouvant diverger, les inventaires d'invocations "
    "peuvent différer: il ne s'agit pas de nombres aléatoires communs exacts "
    "événement par événement."
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_ATTEMPT_DIRECTORY_RE = re.compile(r"attempt-[1-9][0-9]*-[0-9a-f]{32}")
_ENGINE_HEAVY_DIRECTORY_NAMES = frozenset({"data", "plots", "maps", "run"})
_JSON_REPLACE_ATTEMPTS = 8
_JSON_REPLACE_BACKOFF_SECONDS = 0.02

BUNDLE_SPECS = (
    ("data/production_demand_service_daily.csv", True),
    ("data/production_output_products_daily.csv", True),
    ("data/production_input_stocks_daily.csv", True),
    ("data/production_constraint_daily.csv", True),
    ("data/first_simulation_daily.csv", False),
    ("summaries/first_simulation_summary.json", True),
    ("data/production_supplier_shipments_daily.csv", True),
)


class V7ProtocolError(ValueError):
    """The fixed V7 confirmation contract is incomplete or inconsistent."""


@dataclass(frozen=True)
class CandidateSpec:
    key: str
    candidate_id: str
    target_group: str
    offset_days_268091: float
    offset_days_268967: float

    def payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "candidate_id": self.candidate_id,
            "target_group": self.target_group,
            "offset_days_268091": self.offset_days_268091,
            "offset_days_268967": self.offset_days_268967,
            "evidence_mode": "fresh_physical_engine_run_v7",
            "configuration_source": "signed_v6_development_design_only",
            "source_simulation_evidence_accepted": False,
        }


@dataclass(frozen=True)
class ValidatedPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    candidates: tuple[CandidateSpec, ...]


Executor = Callable[..., Mapping[str, Any]]

FIXED_TRIPLET = (
    CandidateSpec("op100_source", "v7_op100_0_0", "op_100", 0.0, 0.0),
    CandidateSpec(
        "op93_v5_8p4_80p6",
        "v7_op93_8p4_80p6",
        "op_93",
        8.4,
        80.6,
    ),
    CandidateSpec(
        "op80_v6_17p5_96p6",
        "v7_op80_17p5_96p6",
        "op_80",
        17.5,
        96.6,
    ),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _signed(unsigned: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**unsigned, field: stable_sha256(unsigned)}


def _verify_signature(payload: Mapping[str, Any], field: str, label: str) -> str:
    unsigned = dict(payload)
    signature = unsigned.pop(field, None)
    if (
        not isinstance(signature, str)
        or not _SHA256_RE.fullmatch(signature)
        or signature != stable_sha256(unsigned)
    ):
        raise V7ProtocolError(f"Invalid signature: {label}")
    return signature


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V7ProtocolError(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V7ProtocolError(f"JSON object expected: {path}")
    return payload


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(_JSON_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt + 1 == _JSON_REPLACE_ATTEMPTS:
                    raise
                time.sleep(_JSON_REPLACE_BACKOFF_SECONDS * (2**attempt))
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, raw)


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _derive_seed_cohort(
    domain: str, count: int, forbidden: set[int]
) -> tuple[int, ...]:
    seeds: list[int] = []
    counter = 0
    while len(seeds) < count:
        digest = hashlib.sha256(f"{domain}:{counter}".encode("ascii")).digest()
        seed = int.from_bytes(digest[:8], "big") % MAX_ENGINE_SEED + 1
        counter += 1
        if seed not in forbidden and seed not in seeds:
            seeds.append(seed)
    return tuple(seeds)


V7_VALIDATION_SEEDS = _derive_seed_cohort(
    V7_VALIDATION_SEED_DOMAIN,
    VALIDATION_SEED_COUNT,
    set(PRIOR_SEEDS),
)


def _assert_seed_contract() -> None:
    seeds = V7_VALIDATION_SEEDS
    if len(seeds) != VALIDATION_SEED_COUNT or len(set(seeds)) != len(seeds):
        raise V7ProtocolError("V7 validation cohort is not 150 unique seeds")
    if set(seeds) & PRIOR_SEEDS:
        raise V7ProtocolError("A V7 validation seed was already used in V5/V6")
    if seeds != _derive_seed_cohort(
        V7_VALIDATION_SEED_DOMAIN,
        VALIDATION_SEED_COUNT,
        set(PRIOR_SEEDS),
    ):
        raise V7ProtocolError("V7 validation cohort is not reproducible")


def _module_inventory() -> list[dict[str, str]]:
    source_root = Path(__file__).resolve().parent
    rows: list[dict[str, str]] = []
    for relative, expected in PINNED_V6_MODULE_SHA256.items():
        path = (source_root / relative).resolve()
        if not path.is_file():
            raise V7ProtocolError(f"Pinned V6 file missing: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise V7ProtocolError(f"Pinned V6 file changed: {relative} ({actual})")
        rows.append({"relative_path": relative, "path": str(path), "sha256": actual})
    return rows


def _validate_runtime_inventory(raw: Any, *, verify_files: bool) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != {
        "schema_version",
        "file_count",
        "files",
        "aggregate_sha256",
    }:
        raise V7ProtocolError("V6 runtime dependency inventory is invalid")
    files = raw.get("files")
    if not isinstance(files, list) or int(raw.get("file_count", -1)) != len(files):
        raise V7ProtocolError("V6 runtime dependency count is invalid")
    unsigned = {
        "schema_version": raw["schema_version"],
        "file_count": len(files),
        "files": files,
    }
    if raw.get("aggregate_sha256") != stable_sha256(unsigned):
        raise V7ProtocolError("V6 runtime dependency aggregate changed")
    paths: list[str] = []
    for row in files:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"}:
            raise V7ProtocolError("Invalid V6 runtime dependency record")
        relative = str(row.get("path") or "")
        digest = str(row.get("sha256") or "")
        if (
            not relative
            or Path(relative).is_absolute()
            or "\\" in relative
            or not _SHA256_RE.fullmatch(digest)
        ):
            raise V7ProtocolError("Unsafe V6 runtime dependency record")
        paths.append(relative)
        if verify_files:
            path = (_repo_root() / relative).resolve()
            if (
                not path.is_relative_to(_repo_root())
                or not path.is_file()
                or sha256_file(path) != digest
            ):
                raise V7ProtocolError(f"Runtime dependency changed: {relative}")
    if len(paths) != len(set(paths)) or paths != sorted(paths):
        raise V7ProtocolError("Runtime dependency paths are duplicate or unsorted")
    return dict(raw)


def _candidate_coordinates(payload: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        payload.get("target_group"),
        payload.get("offset_days_268091"),
        payload.get("offset_days_268967"),
    )


def _validate_v6_holdout_diagnostic(
    path: Path,
    *,
    expected_source_selection_signature: str,
    allow_test_source: bool,
) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise V7ProtocolError("The signed V6 rejected holdout result is missing")
    digest = sha256_file(path)
    if not allow_test_source and digest != OFFICIAL_V6_HOLDOUT_RESULT_SHA256:
        raise V7ProtocolError("The official V6 rejected holdout result changed")
    payload = _read_json(path)
    signature = _verify_signature(payload, "holdout_signature", "V6 holdout result")
    expected_selected = {
        "op_100": "op100_source",
        "op_93": "op93_v5_8p4_80p6",
        "op_80": "op80_v6_17p5_96p6",
    }
    if (
        payload.get("schema_version")
        != "etudecas.multiseed_operating_point_holdout.v6.holdout_result"
        or payload.get("status") != "holdout_rejected_no_retuning"
        or payload.get("accepted") is not False
        or payload.get("publishable") is not True
        or payload.get("execution_mode") != "official_v6_fresh_holdout"
        or payload.get("retuning_after_holdout") is not False
        or payload.get("failure_rule") != "publish_no_go_and_require_new_fresh_cohort"
        or int(payload.get("holdout_evidence_case_count") or -1) != 90
        or payload.get("holdout_seeds") != list(V5_V6_HOLDOUT_SEEDS)
        or payload.get("selected_candidate_keys") != expected_selected
        or payload.get("source_v6_selection_signature")
        != expected_source_selection_signature
        or not _SHA256_RE.fullmatch(
            str(payload.get("holdout_evidence_signature_set_sha256") or "")
        )
    ):
        raise V7ProtocolError("V6 rejected holdout diagnostic contract changed")
    return {
        "path": str(path),
        "sha256": digest,
        "holdout_signature": signature,
        "status": payload["status"],
        "accepted": False,
        "physical_evidence_case_count": 90,
        "used_for_protocol_diagnosis_and_sample_sizing": True,
        "reused_as_v7_acceptance_evidence": False,
        "retuning_after_v6_holdout": False,
    }


def _validate_rng_audit(audit_dir: Path, *, allow_test_source: bool) -> dict[str, Any]:
    audit_dir = audit_dir.resolve()
    manifest_path = audit_dir / "artifact_manifest.json"
    if not manifest_path.is_file():
        raise V7ProtocolError("The signed V6 RNG audit manifest is missing")
    manifest_sha = sha256_file(manifest_path)
    if not allow_test_source and manifest_sha != OFFICIAL_RNG_AUDIT_MANIFEST_SHA256:
        raise V7ProtocolError("The official V6 RNG audit manifest changed")
    manifest = _read_json(manifest_path)
    manifest_signature = _verify_signature(
        manifest, "manifest_signature", "V6 RNG audit manifest"
    )
    files = manifest.get("files")
    if (
        manifest.get("schema_version")
        != "etudecas.supplier_v6_rng_pairing_audit.v1.manifest"
        or manifest.get("conclusion") != "aucun_defaut_rng_prouve"
        or not _SHA256_RE.fullmatch(str(manifest.get("audit_signature") or ""))
        or not _SHA256_RE.fullmatch(str(manifest.get("audit_module_sha256") or ""))
        or not isinstance(files, list)
        or len(files) != 3
    ):
        raise V7ProtocolError("V6 RNG audit manifest contract changed")
    if (
        not allow_test_source
        and manifest.get("audit_signature") != OFFICIAL_RNG_AUDIT_SIGNATURE
    ):
        raise V7ProtocolError("The official V6 RNG audit signature changed")
    expected_names = {
        "supplier_v6_rng_pairing_audit.json",
        "supplier_v6_rng_pairing_seed_summary.csv",
        "RAPPORT_AUDIT_COUPLAGE_ALEATOIRE_V6_FR.md",
    }
    records: list[dict[str, Any]] = []
    for row in files:
        if not isinstance(row, Mapping) or set(row) != {
            "relative_path",
            "sha256",
            "size_bytes",
        }:
            raise V7ProtocolError("Invalid V6 RNG audit file record")
        relative = str(row.get("relative_path") or "")
        path = (audit_dir / relative).resolve()
        if (
            relative not in expected_names
            or not path.is_relative_to(audit_dir)
            or not path.is_file()
            or sha256_file(path) != row.get("sha256")
            or path.stat().st_size != row.get("size_bytes")
        ):
            raise V7ProtocolError("A V6 RNG audit file changed")
        records.append(dict(row))
    if {row["relative_path"] for row in records} != expected_names:
        raise V7ProtocolError("V6 RNG audit file inventory is incomplete")
    audit_path = audit_dir / "supplier_v6_rng_pairing_audit.json"
    audit = _read_json(audit_path)
    audit_signature = _verify_signature(audit, "audit_signature", "V6 RNG audit")
    if (
        audit.get("schema_version") != "etudecas.supplier_v6_rng_pairing_audit.v1.audit"
        or audit.get("conclusion") != "aucun_defaut_rng_prouve"
        or audit_signature != manifest.get("audit_signature")
    ):
        raise V7ProtocolError("V6 RNG audit conclusion/signature changed")
    return {
        "directory": str(audit_dir),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "manifest_signature": manifest_signature,
        "audit_signature": audit_signature,
        "audit_module_sha256": manifest["audit_module_sha256"],
        "conclusion": "aucun_defaut_rng_prouve",
        "files": records,
        "role": "protocol_diagnostic_not_v7_acceptance_evidence",
    }


def _validate_v6_design_source(
    v6_plan_dir: Path,
    v6_run_dir: Path,
    *,
    v6_holdout_result: Path,
    allow_test_source: bool,
    verify_runtime: bool,
) -> dict[str, Any]:
    """Bind V6 design and its rejected holdout as non-acceptance information."""

    plan_dir = v6_plan_dir.resolve()
    run_dir = v6_run_dir.resolve()
    plan_path = plan_dir / "refinement_plan.json"
    selection_path = run_dir / "development_selection.json"
    if not plan_path.is_file() or not selection_path.is_file():
        raise V7ProtocolError("V6 plan or development selection is missing")
    if not allow_test_source and (
        sha256_file(plan_path) != OFFICIAL_V6_PLAN_SHA256
        or sha256_file(selection_path) != OFFICIAL_V6_SELECTION_SHA256
    ):
        raise V7ProtocolError("V7 requires the exact official V6 design artifacts")

    plan = _read_json(plan_path)
    selection = _read_json(selection_path)
    _verify_signature(plan, "plan_signature", "V6 plan")
    _verify_signature(selection, "selection_signature", "V6 development selection")
    allowed_modes = (
        {OFFICIAL_V6_EXECUTION_MODE, "test_only_v6_injected_executor"}
        if allow_test_source
        else {OFFICIAL_V6_EXECUTION_MODE}
    )
    expected_publishable = selection.get("execution_mode") == OFFICIAL_V6_EXECUTION_MODE
    if (
        plan.get("schema_version") != V6_PLAN_SCHEMA_VERSION
        or selection.get("schema_version") != V6_SELECTION_SCHEMA_VERSION
        or selection.get("plan_signature") != plan.get("plan_signature")
        or selection.get("status") != V6_SUCCESS_STATUS
        or selection.get("execution_mode") not in allowed_modes
        or selection.get("publishable") is not expected_publishable
        or int(selection.get("holdout_cases_read") or 0) != 0
        or selection.get("holdout_execution_supported_by_this_module") is not False
        or selection.get("retuning_after_development") is not False
        or tuple(selection.get("development_seeds") or ()) != V5_V6_DEVELOPMENT_SEEDS
        or tuple(selection.get("holdout_seeds_sealed_and_unread") or ())
        != V5_V6_HOLDOUT_SEEDS
    ):
        raise V7ProtocolError("V6 source is not the exact holdout-blind design source")

    expected_selected = {
        "op_100": "op100_source",
        "op_93": "op93_v5_8p4_80p6",
        "op_80": "op80_v6_17p5_96p6",
    }
    if selection.get("selected_candidate_keys") != expected_selected:
        raise V7ProtocolError("The V6 selected triplet changed")
    holdout_diagnostic = _validate_v6_holdout_diagnostic(
        v6_holdout_result,
        expected_source_selection_signature=selection["selection_signature"],
        allow_test_source=allow_test_source,
    )
    summaries = selection.get("candidate_summaries")
    inventory = plan.get("inventory")
    if not isinstance(summaries, Mapping) or not isinstance(inventory, Mapping):
        raise V7ProtocolError("V6 candidate summaries or inventory are missing")

    copied: dict[str, dict[str, Any]] = {}
    for candidate in FIXED_TRIPLET:
        summary = summaries.get(candidate.key)
        item = inventory.get(candidate.key)
        if not isinstance(summary, Mapping) or not isinstance(item, Mapping):
            raise V7ProtocolError(f"Missing V6 design state: {candidate.key}")
        if summary.get("admissible_individually") is not True or _candidate_coordinates(
            summary.get("candidate") or {}
        ) != (
            candidate.target_group,
            candidate.offset_days_268091,
            candidate.offset_days_268967,
        ):
            raise V7ProtocolError(f"V6 design coordinates changed: {candidate.key}")
        graph = (plan_dir / str(item.get("graph_path") or "")).resolve()
        ledger = (plan_dir / str(item.get("ledger_path") or "")).resolve()
        graph_sha = str(item.get("graph_sha256") or "")
        ledger_sha = str(item.get("ledger_sha256") or "")
        if (
            not graph.is_relative_to(plan_dir)
            or not ledger.is_relative_to(plan_dir)
            or not graph.is_file()
            or not ledger.is_file()
            or graph.suffix != ".json"
            or ledger.suffix != ".json"
            or sha256_file(graph) != graph_sha
            or sha256_file(ledger) != ledger_sha
        ):
            raise V7ProtocolError(f"V6 graph/ledger changed: {candidate.key}")
        copied[candidate.key] = {
            "graph_path": str(graph),
            "graph_sha256": graph_sha,
            "ledger_path": str(ledger),
            "ledger_sha256": ledger_sha,
        }

    execution = plan.get("execution_contract")
    runtime = _validate_runtime_inventory(
        plan.get("runtime_dependencies"), verify_files=verify_runtime
    )
    if not isinstance(execution, Mapping):
        raise V7ProtocolError("V6 execution contract is missing")
    engine = Path(str((execution.get("engine") or {}).get("path") or "")).resolve()
    profile = Path(
        str((execution.get("engine_profile") or {}).get("path") or "")
    ).resolve()
    if not allow_test_source and (
        not engine.is_file()
        or not profile.is_file()
        or sha256_file(engine) != (execution.get("engine") or {}).get("sha256")
        or sha256_file(profile) != (execution.get("engine_profile") or {}).get("sha256")
        or execution.get("common_random_numbers") is not True
        or int(execution.get("simulation_days") or -1) != SERVICE_DAYS
        or execution.get("capacity_override") is not False
        or execution.get("quality_incident") is not False
        or execution.get("availability_incident") is not False
        or execution.get("state_dependent_risk") is not False
    ):
        raise V7ProtocolError("V6 execution dependencies/policy changed")

    return {
        "role": "development_design_information_only_not_v7_evidence",
        "plan": str(plan_path),
        "plan_sha256": sha256_file(plan_path),
        "plan_signature": plan["plan_signature"],
        "development_selection": str(selection_path),
        "development_selection_sha256": sha256_file(selection_path),
        "development_selection_signature": selection["selection_signature"],
        "selected_triplet": expected_selected,
        "v6_simulation_evidence_reused": False,
        "v6_holdout_diagnostic": holdout_diagnostic,
        "states": copied,
        "execution_contract": dict(execution),
        "runtime_dependencies": runtime,
    }


def _decision_contract() -> dict[str, Any]:
    return {
        "design": "single_fixed_triplet_confirmatory_validation_no_selection",
        "complete_seed_blocks_required": VALIDATION_SEED_COUNT,
        "complete_physical_cases_required": EXPECTED_CASES,
        "service_days": SERVICE_DAYS,
        "primary_service_estimator": "pooled_ratio_of_summed_on_due_to_demand",
        "bootstrap": {
            "method": "percentile_resampling_of_whole_three_state_seed_blocks",
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
            "global_band_two_sided_confidence": GLOBAL_INTERVAL_CONFIDENCE,
            "op100_lower_one_sided_confidence": OP100_LOWER_CONFIDENCE,
            "adjacent_order_family_one_sided_confidence": ORDER_FAMILY_CONFIDENCE,
            "adjacent_order_bonferroni_comparisons": ORDER_COMPARISON_COUNT,
            "positive_cross_state_correlation_assumed": False,
        },
        "global_service_interval_must_be_inside_pct": {
            key: list(value) for key, value in GLOBAL_BANDS.items()
        },
        "op100_global_and_each_product_lower_bound_pct_minimum": OP100_MINIMUM_PCT,
        "six_adjacent_mean_difference_simultaneous_lower_bounds_pp_strictly_above": 0.0,
        "adjacent_differences": [
            f"{left}_minus_{right}_{measure}"
            for left, right in (("op_100", "op_93"), ("op_93", "op_80"))
            for measure in MEASURES
        ],
        "pooled_product_gap_each_state_maximum_pp": PRODUCT_GAP_MAX_PP,
        "seedwise_monotonicity": "secondary_diagnostic_only_ties_are_not_inversions",
        "ceiling_ties": "allowed_and_not_failures",
        "descriptive_diagnostics": [
            "p10",
            "iqr",
            "mean_of_lowest_10_percent",
            "seedwise_inversion_counts",
        ],
        "interim_seed_block_milestones": list(MILESTONES),
        "interim_decision_allowed": False,
        "retuning_after_any_v7_result": False,
        "failed_validation_rule": "publish_no_go; new version and new seeds required",
    }


def _crn_contract() -> dict[str, Any]:
    return {
        "mode": "common_seed_statistical_blocks",
        "signed_external_v6_rng_audit_required": True,
        "signed_external_v6_rng_audit_conclusion_required": ("aucun_defaut_rng_prouve"),
        "same_seed_used_for_all_three_states": True,
        "exact_event_by_event_common_random_numbers_claimed": False,
        "known_v6_diagnostic": {
            "complete_seed_triplets_checked": 30,
            "triplets_with_identical_paired_rng_invocation_inventory_sha256": 0,
            "interpretation": (
                "Different invocation inventories are compatible with divergent "
                "state-dependent physical decisions; this is not classified as an RNG bug."
            ),
        },
        "v7_required_case_audit_field": (
            "warmup_boundary_paired_rng_invocations_sha256"
        ),
        "inference_unit": "whole_three_state_seed_block",
        "validity_statement": (
            "Paired block differences and whole-block bootstrap do not assume "
            "positive cross-state correlation; exact eventwise variance reduction "
            "is neither required nor claimed."
        ),
        "limit": CRN_LIMIT,
    }


def _retention_contract() -> dict[str, Any]:
    return {
        "capture_timing": "inside_v7_executor_before_canonical_prune",
        "compression": "gzip_mtime_0_compresslevel_9",
        "source_files": [
            {"relative_path": relative, "required": required}
            for relative, required in BUNDLE_SPECS
        ],
        "additional_compact_service_curve_json": True,
        "atomic_write_and_hash_validation": True,
        "overwrite_allowed": False,
        "evidence_commit_timing": "only_after_verified_canonical_prune",
        "orphan_attempt_cleanup": (
            "idempotent_bounded_case_prune_under_run_lock_before_resume"
        ),
        "final_engine_attempt_cleanliness_required": True,
        "supplier_shipment_trace_scope": (
            "complete compact-profile engine CSV; mature-campaign filtered lane "
            "contract is not claimed"
        ),
    }


def _case_registry() -> dict[str, Any]:
    cases = [
        {
            "seed_block_index": index,
            "seed": seed,
            "target_group": candidate.target_group,
            "candidate_key": candidate.key,
            "candidate_id": candidate.candidate_id,
            "graph_path": f"graphs/{candidate.key}.json",
            "evidence_requirement": "new_physical_engine_run_v7",
        }
        for index, seed in enumerate(V7_VALIDATION_SEEDS)
        for candidate in FIXED_TRIPLET
    ]
    unsigned = {
        "schema_version": CASE_REGISTRY_SCHEMA_VERSION,
        "status": "frozen_not_executed",
        "seed_domain": V7_VALIDATION_SEED_DOMAIN,
        "seeds": list(V7_VALIDATION_SEEDS),
        "seed_count": VALIDATION_SEED_COUNT,
        "state_count": len(FIXED_TRIPLET),
        "case_count": len(cases),
        "cases": cases,
        "imported_evidence_case_count": 0,
        "fresh_physical_engine_case_count_required": EXPECTED_CASES,
    }
    return _signed(unsigned, "case_registry_signature")


def _plan_files(plan_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(
        (
            plan_dir / "case_registry.json",
            *tuple((plan_dir / "graphs").glob("*.json")),
            *tuple((plan_dir / "ledgers").glob("*.json")),
        ),
        key=lambda path: path.relative_to(plan_dir).as_posix(),
    )
    return [
        {
            "path": path.relative_to(plan_dir).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    ]


def _assert_plan_surface(plan_dir: Path) -> None:
    forbidden = (
        plan_dir / "evidence",
        plan_dir / "engine_attempts",
        plan_dir / "curves",
        plan_dir / "progress.json",
        plan_dir / "validation_result.json",
    )
    if any(path.exists() for path in forbidden):
        raise V7ProtocolError("A V7 plan directory contains future run evidence")


def prepare_plan(
    output_dir: Path,
    *,
    v6_plan_dir: Path,
    v6_run_dir: Path,
    v6_holdout_result: Path,
    rng_audit_dir: Path,
    reviewed_module_sha256: str,
    allow_test_source: bool = False,
) -> Path:
    """Freeze the reviewed V7 plan; never start a simulation."""

    _assert_seed_contract()
    _module_inventory()
    module_path = Path(__file__).resolve()
    module_sha = sha256_file(module_path)
    if reviewed_module_sha256 != module_sha:
        raise V7ProtocolError(
            "Plan freeze requires the SHA-256 of the exact reviewed V7 module"
        )
    output = output_dir.resolve()
    source_plan = v6_plan_dir.resolve()
    source_run = v6_run_dir.resolve()
    source_holdout = v6_holdout_result.resolve().parent
    source_rng_audit = rng_audit_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite V7 plan: {output}")
    if any(
        _paths_overlap(output, source)
        for source in (
            source_plan,
            source_run,
            source_holdout,
            source_rng_audit,
            _repo_root(),
        )
    ):
        raise V7ProtocolError("V7 plan output overlaps a protected source")
    source = _validate_v6_design_source(
        source_plan,
        source_run,
        v6_holdout_result=v6_holdout_result,
        allow_test_source=allow_test_source,
        verify_runtime=not allow_test_source,
    )
    rng_audit = _validate_rng_audit(rng_audit_dir, allow_test_source=allow_test_source)
    temporary = output.with_name(f".{output.name}.building-{uuid4().hex}")
    try:
        (temporary / "graphs").mkdir(parents=True)
        (temporary / "ledgers").mkdir()
        inventory: dict[str, dict[str, str]] = {}
        for candidate in FIXED_TRIPLET:
            row = source["states"][candidate.key]
            graph_target = temporary / "graphs" / f"{candidate.key}.json"
            ledger_target = temporary / "ledgers" / f"{candidate.key}.json"
            shutil.copyfile(Path(row["graph_path"]), graph_target)
            shutil.copyfile(Path(row["ledger_path"]), ledger_target)
            if (
                sha256_file(graph_target) != row["graph_sha256"]
                or sha256_file(ledger_target) != row["ledger_sha256"]
            ):
                raise V7ProtocolError("A copied V7 design file differs from V6")
            inventory[candidate.key] = {
                "graph_path": graph_target.relative_to(temporary).as_posix(),
                "graph_sha256": row["graph_sha256"],
                "ledger_path": ledger_target.relative_to(temporary).as_posix(),
                "ledger_sha256": row["ledger_sha256"],
            }
        registry = _case_registry()
        _write_json(temporary / "case_registry.json", registry)
        unsigned = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "status": "fixed_triplet_frozen_no_engine_run",
            "created_at_utc": _now(),
            "interpretation": INTERPRETATION,
            "producer": {
                "module": __name__,
                "path": str(module_path),
                "reviewed_sha256": module_sha,
            },
            "v6_design_provenance": source,
            "rng_pairing_audit": rng_audit,
            "pinned_v6_modules": _module_inventory(),
            "fixed_triplet": [candidate.payload() for candidate in FIXED_TRIPLET],
            "inventory": inventory,
            "case_registry": "case_registry.json",
            "cohort": {
                "seed_domain": V7_VALIDATION_SEED_DOMAIN,
                "seeds": list(V7_VALIDATION_SEEDS),
                "seed_count": VALIDATION_SEED_COUNT,
                "state_count": len(FIXED_TRIPLET),
                "case_count": EXPECTED_CASES,
                "prior_seed_set_sha256": stable_sha256(sorted(PRIOR_SEEDS)),
                "seed_set_sha256": stable_sha256(list(V7_VALIDATION_SEEDS)),
                "disjoint_from_v5_v6": True,
            },
            "decision_contract": _decision_contract(),
            "crn_contract": _crn_contract(),
            "retention_contract": _retention_contract(),
            "execution_contract": source["execution_contract"],
            "runtime_dependencies": source["runtime_dependencies"],
            "files": _plan_files(temporary),
            "engine_runs_performed_by_plan_freeze": 0,
        }
        _write_json(
            temporary / "protocol_manifest.json",
            _signed(unsigned, "plan_signature"),
        )
        validate_plan(
            temporary,
            allow_test_source=allow_test_source,
            verify_runtime=not allow_test_source,
        )
        temporary.rename(output)
    except BaseException:
        if temporary.exists() and temporary.parent == output.parent:
            shutil.rmtree(temporary)
        raise
    return output / "protocol_manifest.json"


def validate_plan(
    plan_dir: Path,
    *,
    allow_test_source: bool = False,
    verify_runtime: bool = True,
) -> ValidatedPlan:
    plan_dir = plan_dir.resolve()
    _assert_seed_contract()
    _assert_plan_surface(plan_dir)
    manifest = _read_json(plan_dir / "protocol_manifest.json")
    _verify_signature(manifest, "plan_signature", "V7 plan")
    producer = manifest.get("producer") or {}
    module_path = Path(__file__).resolve()
    if (
        manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "fixed_triplet_frozen_no_engine_run"
        or producer.get("path") != str(module_path)
        or producer.get("reviewed_sha256") != sha256_file(module_path)
        or manifest.get("fixed_triplet")
        != [candidate.payload() for candidate in FIXED_TRIPLET]
        or manifest.get("decision_contract") != _decision_contract()
        or manifest.get("crn_contract") != _crn_contract()
        or manifest.get("retention_contract") != _retention_contract()
        or manifest.get("pinned_v6_modules") != _module_inventory()
        or int(manifest.get("engine_runs_performed_by_plan_freeze", -1)) != 0
    ):
        raise V7ProtocolError("V7 plan-level contract changed")
    cohort = manifest.get("cohort") or {}
    if (
        cohort.get("seeds") != list(V7_VALIDATION_SEEDS)
        or cohort.get("seed_count") != VALIDATION_SEED_COUNT
        or cohort.get("state_count") != 3
        or cohort.get("case_count") != EXPECTED_CASES
        or cohort.get("disjoint_from_v5_v6") is not True
    ):
        raise V7ProtocolError("V7 fresh validation cohort changed")
    source = manifest.get("v6_design_provenance") or {}
    rebuilt = _validate_v6_design_source(
        Path(str(source.get("plan") or "")).parent,
        Path(str(source.get("development_selection") or "")).parent,
        v6_holdout_result=Path(
            str((source.get("v6_holdout_diagnostic") or {}).get("path") or "")
        ),
        allow_test_source=allow_test_source,
        verify_runtime=verify_runtime and not allow_test_source,
    )
    if source != rebuilt:
        raise V7ProtocolError("V6 design provenance changed")
    rng_source = manifest.get("rng_pairing_audit") or {}
    rebuilt_rng = _validate_rng_audit(
        Path(str(rng_source.get("directory") or "")),
        allow_test_source=allow_test_source,
    )
    if rng_source != rebuilt_rng:
        raise V7ProtocolError("V6 RNG audit provenance changed")
    _validate_runtime_inventory(
        manifest.get("runtime_dependencies"),
        verify_files=verify_runtime and not allow_test_source,
    )
    inventory = manifest.get("inventory")
    if not isinstance(inventory, Mapping) or set(inventory) != {
        candidate.key for candidate in FIXED_TRIPLET
    }:
        raise V7ProtocolError("V7 graph inventory changed")
    for candidate in FIXED_TRIPLET:
        item = inventory[candidate.key]
        graph = (plan_dir / str(item.get("graph_path") or "")).resolve()
        ledger = (plan_dir / str(item.get("ledger_path") or "")).resolve()
        if (
            not graph.is_relative_to(plan_dir)
            or not ledger.is_relative_to(plan_dir)
            or not graph.is_file()
            or not ledger.is_file()
            or sha256_file(graph) != item.get("graph_sha256")
            or sha256_file(ledger) != item.get("ledger_sha256")
        ):
            raise V7ProtocolError(f"V7 state file changed: {candidate.key}")
    registry = _read_json(plan_dir / "case_registry.json")
    _verify_signature(registry, "case_registry_signature", "V7 case registry")
    if registry != _case_registry():
        raise V7ProtocolError("V7 case registry changed")
    if manifest.get("files") != _plan_files(plan_dir):
        raise V7ProtocolError("V7 plan inventory changed")
    expected_files = {
        "protocol_manifest.json",
        "case_registry.json",
        *(f"graphs/{candidate.key}.json" for candidate in FIXED_TRIPLET),
        *(f"ledgers/{candidate.key}.json" for candidate in FIXED_TRIPLET),
    }
    actual_files = {
        path.relative_to(plan_dir).as_posix()
        for path in plan_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise V7ProtocolError("Unexpected or missing file in V7 plan")
    return ValidatedPlan(plan_dir, manifest, FIXED_TRIPLET)


def _case_key(candidate: CandidateSpec, seed: int) -> str:
    return f"validation__{candidate.key}__seed_{seed}"


def _evidence_path(run_dir: Path, candidate: CandidateSpec, seed: int) -> Path:
    digest = hashlib.sha256(_case_key(candidate, seed).encode("utf-8")).hexdigest()
    return run_dir / "evidence" / f"{digest[:24]}.json"


def _curve_relative_path(candidate: CandidateSpec, seed: int) -> str:
    return (
        Path("curves")
        / candidate.target_group
        / candidate.candidate_id
        / f"seed_{seed}.json.gz"
    ).as_posix()


def _run_manifest(plan: ValidatedPlan, mode: str) -> dict[str, Any]:
    if mode not in {OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE}:
        raise V7ProtocolError("Unknown V7 execution mode")
    unsigned = {
        "schema_version": RUN_SCHEMA_VERSION,
        "status": "registered_before_first_v7_engine_run",
        "plan_path": str(plan.plan_dir),
        "plan_sha256": sha256_file(plan.plan_dir / "protocol_manifest.json"),
        "plan_signature": plan.manifest["plan_signature"],
        "execution_mode": mode,
        "publishable": mode == OFFICIAL_EXECUTION_MODE,
        "fixed_candidate_count": 3,
        "seed_block_count": VALIDATION_SEED_COUNT,
        "fresh_engine_case_count": EXPECTED_CASES,
        "maximum_workers": 2,
        "selection_or_retuning_supported": False,
        "interim_decision_supported": False,
    }
    return _signed(unsigned, "run_signature")


def _registered_mode(plan: ValidatedPlan, run_dir: Path) -> str:
    payload = _read_json(run_dir / "run_manifest.json")
    for mode in (OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE):
        if payload == _run_manifest(plan, mode):
            return mode
    raise V7ProtocolError("V7 run registration changed")


def _protected_run_sources(plan: ValidatedPlan) -> tuple[Path, ...]:
    source = plan.manifest["v6_design_provenance"]
    return (
        _repo_root(),
        plan.plan_dir,
        Path(source["plan"]).resolve().parent,
        Path(source["development_selection"]).resolve().parent,
        Path(source["v6_holdout_diagnostic"]["path"]).resolve().parent,
        Path(plan.manifest["rng_pairing_audit"]["directory"]).resolve(),
    )


def _register_run(plan: ValidatedPlan, run_dir: Path, mode: str) -> None:
    if any(_paths_overlap(run_dir, source) for source in _protected_run_sources(plan)):
        raise V7ProtocolError("V7 run output overlaps a protected source")
    run_dir.mkdir(parents=True, exist_ok=True)
    allowed = {
        ".v7.lock",
        "run_manifest.json",
        "progress.json",
        "validation_result.json",
        "evidence",
        "engine_attempts",
        "curves",
        "snapshots",
        "checkpoints",
    }
    unexpected = {path.name for path in run_dir.iterdir()} - allowed
    if unexpected:
        raise V7ProtocolError(f"Unexpected V7 run item(s): {sorted(unexpected)}")
    manifest_path = run_dir / "run_manifest.json"
    expected = _run_manifest(plan, mode)
    material = [path for path in run_dir.iterdir() if path.name != ".v7.lock"]
    if material and not manifest_path.is_file():
        raise V7ProtocolError("Refusing an unregistered non-empty V7 run")
    if manifest_path.exists() and _read_json(manifest_path) != expected:
        raise V7ProtocolError("V7 run belongs to another plan or mode")
    if not manifest_path.exists():
        _write_json(manifest_path, expected)


@contextmanager
def _run_lock(run_dir: Path) -> Iterable[None]:
    path = run_dir / ".v7.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise V7ProtocolError("Another V7 process holds the run lock") from exc
        yield
    finally:
        try:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _jobs(plan: ValidatedPlan) -> tuple[tuple[CandidateSpec, int], ...]:
    del plan
    return tuple(
        (candidate, seed) for seed in V7_VALIDATION_SEEDS for candidate in FIXED_TRIPLET
    )


def _finite_service(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise V7ProtocolError(f"Invalid numeric metric: {label}") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise V7ProtocolError(f"Service outside [0,1]: {label}")
    return number


def _finite_nonnegative(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise V7ProtocolError(f"Invalid numeric metric: {label}") from exc
    if not math.isfinite(number) or number < 0.0:
        raise V7ProtocolError(f"Negative or non-finite metric: {label}")
    return number


def _normalize_metrics(raw: Mapping[str, Any]) -> dict[str, float]:
    demand_091 = _finite_nonnegative(raw.get("demand_qty_268091"), "demand 268091")
    demand_967 = _finite_nonnegative(raw.get("demand_qty_268967"), "demand 268967")
    on_due_091 = _finite_nonnegative(raw.get("on_due_qty_268091"), "on due 268091")
    on_due_967 = _finite_nonnegative(raw.get("on_due_qty_268967"), "on due 268967")
    demand_global = _finite_nonnegative(
        raw.get("demand_qty_global", demand_091 + demand_967), "global demand"
    )
    on_due_global = _finite_nonnegative(
        raw.get("on_due_qty_global", on_due_091 + on_due_967), "global on due"
    )
    tolerance = 1e-6
    if (
        demand_091 <= 0.0
        or demand_967 <= 0.0
        or abs(demand_global - demand_091 - demand_967)
        > max(tolerance, tolerance * demand_global)
        or abs(on_due_global - on_due_091 - on_due_967)
        > max(tolerance, tolerance * max(1.0, on_due_global))
        or on_due_091 > demand_091 + tolerance
        or on_due_967 > demand_967 + tolerance
    ):
        raise V7ProtocolError("Service quantity identities are inconsistent")
    computed = {
        "on_due_service_268091": on_due_091 / demand_091,
        "on_due_service_268967": on_due_967 / demand_967,
        "system_on_due_service": on_due_global / demand_global,
    }
    for key, value in computed.items():
        supplied = _finite_service(raw.get(key, value), key)
        if not math.isclose(supplied, value, rel_tol=1e-9, abs_tol=1e-9):
            raise V7ProtocolError(f"Service ratio differs from quantities: {key}")
    return {
        "demand_qty_268091": demand_091,
        "demand_qty_268967": demand_967,
        "demand_qty_global": demand_global,
        "on_due_qty_268091": on_due_091,
        "on_due_qty_268967": on_due_967,
        "on_due_qty_global": on_due_global,
        **computed,
    }


def _curve_payload_from_csv(
    source_csv: Path,
    *,
    plan: ValidatedPlan,
    candidate: CandidateSpec,
    seed: int,
) -> tuple[dict[str, Any], str]:
    raw = source_csv.read_bytes()
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    except UnicodeDecodeError as exc:
        raise V7ProtocolError("Daily service curve is not UTF-8") from exc
    required_columns = {
        "day",
        "node_id",
        "item_id",
        "demand_qty",
        "required_with_backlog_qty",
        "served_qty",
        "backlog_end_qty",
    }
    if not required_columns.issubset(set(reader.fieldnames or ())):
        raise V7ProtocolError("Daily service curve schema changed")
    series = {
        product: {"demand_qty": [], "on_due_qty": [], "backlog_end_qty": []}
        for product in PRODUCTS
    }
    seen: set[tuple[str, int]] = set()
    for row in reader:
        if str(row.get("node_id") or "") != "C-XXXXX":
            continue
        product = str(row.get("item_id") or "").replace("item:", "")
        if product not in series:
            continue
        try:
            day = int(str(row.get("day") or ""))
        except ValueError as exc:
            raise V7ProtocolError("Invalid day in daily service curve") from exc
        if not 0 <= day < SERVICE_DAYS or (product, day) in seen:
            raise V7ProtocolError(
                "Daily service curve day is duplicate/outside horizon"
            )
        seen.add((product, day))
        demand = _finite_nonnegative(row.get("demand_qty"), "curve demand")
        required = _finite_nonnegative(
            row.get("required_with_backlog_qty"), "curve required"
        )
        served = _finite_nonnegative(row.get("served_qty"), "curve served")
        backlog = _finite_nonnegative(row.get("backlog_end_qty"), "curve backlog")
        if required + 1e-7 < demand:
            raise V7ProtocolError("Curve required quantity is below demand")
        starting_backlog = max(0.0, required - demand)
        on_due = min(demand, max(0.0, served - starting_backlog))
        for field, value in (
            ("demand_qty", demand),
            ("on_due_qty", on_due),
            ("backlog_end_qty", backlog),
        ):
            series[product][field].append((day, round(value, 6)))
    expected = {(product, day) for product in PRODUCTS for day in range(SERVICE_DAYS)}
    if seen != expected:
        raise V7ProtocolError("Daily service curve is not exactly 2 x 720 days")
    compact: dict[str, dict[str, list[float]]] = {}
    for product in PRODUCTS:
        compact[product] = {}
        for field, values in series[product].items():
            ordered = sorted(values)
            if [day for day, _value in ordered] != list(range(SERVICE_DAYS)):
                raise V7ProtocolError("Daily curve order is incomplete")
            compact[product][field] = [value for _day, value in ordered]
    unsigned = {
        "schema_version": CURVE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "seed": seed,
        "day_count": SERVICE_DAYS,
        "products": list(PRODUCTS),
        "series": compact,
        "source_csv_sha256": hashlib.sha256(raw).hexdigest(),
        "lossless_for_retained_columns_after_rounding_decimals": 6,
    }
    return _signed(unsigned, "curve_signature"), hashlib.sha256(raw).hexdigest()


def _synthetic_test_curve_payload(
    *,
    plan: ValidatedPlan,
    candidate: CandidateSpec,
    seed: int,
    metrics: Mapping[str, float],
) -> tuple[dict[str, Any], str]:
    series: dict[str, dict[str, list[float]]] = {}
    for product in PRODUCTS:
        demand = metrics[f"demand_qty_{product}"] / SERVICE_DAYS
        on_due = metrics[f"on_due_qty_{product}"] / SERVICE_DAYS
        series[product] = {
            "demand_qty": [round(demand, 6)] * SERVICE_DAYS,
            "on_due_qty": [round(on_due, 6)] * SERVICE_DAYS,
            "backlog_end_qty": [0.0] * SERVICE_DAYS,
        }
    source_sha = stable_sha256(
        {"kind": "synthetic_test_curve", "candidate": candidate.key, "seed": seed}
    )
    unsigned = {
        "schema_version": CURVE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "seed": seed,
        "day_count": SERVICE_DAYS,
        "products": list(PRODUCTS),
        "series": series,
        "source_csv_sha256": source_sha,
        "lossless_for_retained_columns_after_rounding_decimals": 6,
    }
    return _signed(unsigned, "curve_signature"), source_sha


def _curve_bytes(payload: Mapping[str, Any]) -> tuple[bytes, bytes]:
    raw = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return raw, gzip.compress(raw, compresslevel=9, mtime=0)


def _write_curve(
    run_dir: Path,
    *,
    candidate: CandidateSpec,
    seed: int,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    raw, compressed = _curve_bytes(payload)
    relative = _curve_relative_path(candidate, seed)
    output = (run_dir / relative).resolve()
    if not output.is_relative_to(run_dir):
        raise V7ProtocolError("Compact curve path escaped the V7 run")
    if output.exists():
        if output.read_bytes() != compressed:
            raise V7ProtocolError("Existing compact curve differs")
    else:
        _atomic_write_bytes(output, compressed)
    return {
        "relative_path": relative,
        "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
        "curve_signature": payload["curve_signature"],
        "source_csv_sha256": payload["source_csv_sha256"],
        "uncompressed_bytes": len(raw),
        "compression": "gzip_mtime_0_compresslevel_9",
    }


def _validate_curve_reference(
    reference: Any,
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: CandidateSpec,
    seed: int,
    expected_metrics: Mapping[str, float],
) -> dict[str, Any]:
    expected_fields = {
        "relative_path",
        "gzip_sha256",
        "curve_signature",
        "source_csv_sha256",
        "uncompressed_bytes",
        "compression",
    }
    if not isinstance(reference, Mapping) or set(reference) != expected_fields:
        raise V7ProtocolError("Invalid compact curve reference")
    if (
        reference.get("relative_path") != _curve_relative_path(candidate, seed)
        or reference.get("compression") != "gzip_mtime_0_compresslevel_9"
        or not _SHA256_RE.fullmatch(str(reference.get("gzip_sha256") or ""))
        or not _SHA256_RE.fullmatch(str(reference.get("curve_signature") or ""))
        or not _SHA256_RE.fullmatch(str(reference.get("source_csv_sha256") or ""))
        or type(reference.get("uncompressed_bytes")) is not int
        or int(reference["uncompressed_bytes"]) <= 0
    ):
        raise V7ProtocolError("Compact curve reference changed")
    path = (run_dir / str(reference["relative_path"])).resolve()
    if not path.is_relative_to(run_dir) or not path.is_file():
        raise V7ProtocolError("Compact curve is missing or outside the run")
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != reference["gzip_sha256"]:
        raise V7ProtocolError("Compact curve gzip hash changed")
    try:
        raw = gzip.decompress(compressed)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V7ProtocolError("Compact curve cannot be decoded") from exc
    if not isinstance(payload, dict):
        raise V7ProtocolError("Compact curve payload is not an object")
    _verify_signature(payload, "curve_signature", "V7 compact curve")
    if (
        len(raw) != reference["uncompressed_bytes"]
        or payload.get("curve_signature") != reference["curve_signature"]
        or payload.get("source_csv_sha256") != reference["source_csv_sha256"]
        or payload.get("schema_version") != CURVE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or int(payload.get("seed") or -1) != seed
        or int(payload.get("day_count") or -1) != SERVICE_DAYS
        or payload.get("products") != list(PRODUCTS)
    ):
        raise V7ProtocolError("Compact curve identity changed")
    series = payload.get("series")
    if not isinstance(series, Mapping) or set(series) != set(PRODUCTS):
        raise V7ProtocolError("Compact curve product inventory changed")
    for product in PRODUCTS:
        fields = series[product]
        if not isinstance(fields, Mapping) or set(fields) != {
            "demand_qty",
            "on_due_qty",
            "backlog_end_qty",
        }:
            raise V7ProtocolError("Compact curve series fields changed")
        if any(
            not isinstance(fields[field], list) or len(fields[field]) != SERVICE_DAYS
            for field in fields
        ):
            raise V7ProtocolError("Compact curve series length changed")
        for field, values in fields.items():
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0.0
                for value in values
            ):
                raise V7ProtocolError(f"Compact curve has invalid {field} values")
        if any(
            float(on_due) > float(demand) + 1e-6
            for demand, on_due in zip(
                fields["demand_qty"], fields["on_due_qty"], strict=True
            )
        ):
            raise V7ProtocolError("Compact curve on-due quantity exceeds demand")
        # The retained daily series is rounded to six decimals.  Across 720
        # days its worst possible accumulation error is 0.00036 unit.
        for field, metric in (
            ("demand_qty", f"demand_qty_{product}"),
            ("on_due_qty", f"on_due_qty_{product}"),
        ):
            observed = math.fsum(float(value) for value in fields[field])
            expected = float(expected_metrics[metric])
            if not math.isclose(observed, expected, rel_tol=1e-9, abs_tol=0.0004):
                raise V7ProtocolError(
                    f"Compact curve aggregate differs from evidence metrics: {product}/{field}"
                )
    return payload


def _bundle_relative_path(
    candidate: CandidateSpec, seed: int, source_relative: str
) -> str:
    filename = Path(source_relative).name
    return (
        Path("snapshots")
        / candidate.target_group
        / candidate.candidate_id
        / f"seed_{seed}"
        / f"{filename}.gz"
    ).as_posix()


def _capture_bundle_bytes(
    run_dir: Path,
    *,
    plan: ValidatedPlan,
    candidate: CandidateSpec,
    seed: int,
    sources: Mapping[str, bytes],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for source_relative, required in BUNDLE_SPECS:
        raw = sources.get(source_relative)
        if raw is None:
            if required:
                raise V7ProtocolError(
                    f"Required retained source missing: {source_relative}"
                )
            continue
        if not raw:
            raise V7ProtocolError(f"Retained source is empty: {source_relative}")
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        relative = _bundle_relative_path(candidate, seed, source_relative)
        output = (run_dir / relative).resolve()
        if not output.is_relative_to(run_dir):
            raise V7ProtocolError("Retained bundle path escaped the V7 run")
        if output.exists():
            if output.read_bytes() != compressed:
                raise V7ProtocolError("Existing retained V7 snapshot differs")
        else:
            _atomic_write_bytes(output, compressed)
        records.append(
            {
                "source_relative_path": source_relative,
                "relative_path": relative,
                "required": required,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "source_bytes": len(raw),
                "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
                "gzip_bytes": len(compressed),
                "compression": "gzip_mtime_0_compresslevel_9",
            }
        )
    unsigned = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "seed": seed,
        "files": records,
        "required_sidecar_equivalent_daily_outputs_retained": 4,
        "optional_first_simulation_daily_retained": any(
            row["source_relative_path"] == "data/first_simulation_daily.csv"
            for row in records
        ),
        "summary_retained": True,
        "supplier_shipment_trace_retained": True,
        "supplier_shipment_trace_scope": (
            "complete compact-profile engine CSV, gzip; not filtered/relabelled "
            "as a mature-campaign lane contract"
        ),
    }
    return _signed(unsigned, "bundle_signature")


def _capture_bundle_from_case(
    case_dir: Path,
    run_dir: Path,
    *,
    plan: ValidatedPlan,
    candidate: CandidateSpec,
    seed: int,
) -> dict[str, Any]:
    sources: dict[str, bytes] = {}
    for relative, required in BUNDLE_SPECS:
        path = (case_dir / relative).resolve()
        if not path.is_relative_to(case_dir):
            raise V7ProtocolError("Retained source escaped the engine case")
        if path.is_file():
            sources[relative] = path.read_bytes()
        elif required:
            raise V7ProtocolError(f"Engine output required for V7 bundle: {relative}")
    return _capture_bundle_bytes(
        run_dir,
        plan=plan,
        candidate=candidate,
        seed=seed,
        sources=sources,
    )


def _synthetic_test_bundle(
    run_dir: Path,
    *,
    plan: ValidatedPlan,
    candidate: CandidateSpec,
    seed: int,
) -> dict[str, Any]:
    sources = {
        relative: (
            json.dumps(
                {
                    "test_only": True,
                    "source": relative,
                    "candidate": candidate.key,
                    "seed": seed,
                },
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        for relative, _required in BUNDLE_SPECS
    }
    return _capture_bundle_bytes(
        run_dir,
        plan=plan,
        candidate=candidate,
        seed=seed,
        sources=sources,
    )


def _validate_bundle_reference(
    reference: Any,
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: CandidateSpec,
    seed: int,
) -> dict[str, Any]:
    if not isinstance(reference, Mapping):
        raise V7ProtocolError("V7 retained bundle reference is missing")
    _verify_signature(reference, "bundle_signature", "V7 retained engine bundle")
    expected_fields = {
        "schema_version",
        "plan_signature",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "files",
        "required_sidecar_equivalent_daily_outputs_retained",
        "optional_first_simulation_daily_retained",
        "summary_retained",
        "supplier_shipment_trace_retained",
        "supplier_shipment_trace_scope",
        "bundle_signature",
    }
    if (
        set(reference) != expected_fields
        or reference.get("schema_version") != BUNDLE_SCHEMA_VERSION
        or reference.get("plan_signature") != plan.manifest["plan_signature"]
        or reference.get("candidate_key") != candidate.key
        or reference.get("candidate_id") != candidate.candidate_id
        or reference.get("target_group") != candidate.target_group
        or int(reference.get("seed") or -1) != seed
        or reference.get("required_sidecar_equivalent_daily_outputs_retained") != 4
        or reference.get("summary_retained") is not True
        or reference.get("supplier_shipment_trace_retained") is not True
    ):
        raise V7ProtocolError("V7 retained bundle identity changed")
    files = reference.get("files")
    if not isinstance(files, list):
        raise V7ProtocolError("V7 retained bundle file list is missing")
    expected_required = {relative for relative, required in BUNDLE_SPECS if required}
    allowed = {relative for relative, _required in BUNDLE_SPECS}
    actual_sources: set[str] = set()
    for row in files:
        if not isinstance(row, Mapping) or set(row) != {
            "source_relative_path",
            "relative_path",
            "required",
            "source_sha256",
            "source_bytes",
            "gzip_sha256",
            "gzip_bytes",
            "compression",
        }:
            raise V7ProtocolError("Invalid retained V7 bundle record")
        source_relative = str(row.get("source_relative_path") or "")
        if source_relative in actual_sources:
            raise V7ProtocolError("Duplicate retained V7 bundle source")
        actual_sources.add(source_relative)
        expected_required_flag = dict(BUNDLE_SPECS).get(source_relative)
        path = (run_dir / str(row.get("relative_path") or "")).resolve()
        if (
            source_relative not in allowed
            or row.get("required") is not expected_required_flag
            or row.get("relative_path")
            != _bundle_relative_path(candidate, seed, source_relative)
            or not path.is_relative_to(run_dir)
            or not path.is_file()
            or row.get("compression") != "gzip_mtime_0_compresslevel_9"
            or not _SHA256_RE.fullmatch(str(row.get("source_sha256") or ""))
            or not _SHA256_RE.fullmatch(str(row.get("gzip_sha256") or ""))
            or type(row.get("source_bytes")) is not int
            or type(row.get("gzip_bytes")) is not int
            or int(row.get("source_bytes") or 0) <= 0
            or int(row.get("gzip_bytes") or 0) <= 0
        ):
            raise V7ProtocolError("Retained V7 bundle file identity changed")
        compressed = path.read_bytes()
        if (
            len(compressed) != row["gzip_bytes"]
            or hashlib.sha256(compressed).hexdigest() != row["gzip_sha256"]
        ):
            raise V7ProtocolError("Retained V7 bundle gzip changed")
        try:
            raw = gzip.decompress(compressed)
        except OSError as exc:
            raise V7ProtocolError("Retained V7 bundle gzip is invalid") from exc
        if (
            len(raw) != row["source_bytes"]
            or hashlib.sha256(raw).hexdigest() != row["source_sha256"]
        ):
            raise V7ProtocolError("Retained V7 bundle source hash changed")
    if not expected_required.issubset(actual_sources) or not actual_sources.issubset(
        allowed
    ):
        raise V7ProtocolError("Required retained V7 bundle files are missing")
    optional_present = "data/first_simulation_daily.csv" in actual_sources
    if (
        reference.get("optional_first_simulation_daily_retained")
        is not optional_present
    ):
        raise V7ProtocolError("Optional retained V7 daily-file marker changed")
    return dict(reference)


def _v4_adapter(plan: ValidatedPlan) -> tuple[Any, dict[str, Any]]:
    """Build the V4 executor adapter lazily; importing cannot start the engine."""

    import importlib

    v4 = importlib.import_module(
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_balanced_product_delay_multiseed_refinement_v4"
    )
    candidates = tuple(
        v4.Candidate(
            candidate.key,
            candidate.candidate_id,
            candidate.target_group,
            candidate.offset_days_268091,
            candidate.offset_days_268967,
            "execute",
        )
        for candidate in plan.candidates
    )
    # V4's real executor consumes the V6-shaped execution/inventory fields, while
    # its proof validator still expects the older top-level ``source_hashes``
    # alias.  Keep that compatibility view local: the signed V7 manifest is
    # neither mutated nor weakened.
    adapter_manifest = dict(plan.manifest)
    adapter_manifest["source_hashes"] = {
        "engine_sha256": plan.manifest["execution_contract"]["engine"]["sha256"],
        "engine_profile_sha256": plan.manifest["execution_contract"]["engine_profile"][
            "sha256"
        ],
    }
    return v4, {
        "validated_plan": v4.ValidatedPlan(plan.plan_dir, adapter_manifest, candidates),
        "candidate_by_key": {candidate.key: candidate for candidate in candidates},
    }


def _attempt_digest(candidate: CandidateSpec, seed: int) -> str:
    return hashlib.sha256(_case_key(candidate, seed).encode()).hexdigest()[:24]


def _official_attempt_case_dirs(
    plan: ValidatedPlan, run_dir: Path
) -> list[tuple[CandidateSpec, int, Path]]:
    """Discover only the exact bounded V7 engine case layout."""

    run_dir = run_dir.resolve()
    root_path = run_dir / "engine_attempts"
    if not root_path.exists():
        return []
    root = root_path.resolve()
    if root != root_path or root.parent != run_dir or not root.is_dir():
        raise V7ProtocolError("V7 engine-attempt root escaped the run directory")
    expected: dict[str, tuple[CandidateSpec, int]] = {}
    for candidate, seed in _jobs(plan):
        digest = _attempt_digest(candidate, seed)
        if digest in expected:
            raise V7ProtocolError("V7 engine-attempt digest collision")
        expected[digest] = (candidate, seed)

    case_dirs: list[tuple[CandidateSpec, int, Path]] = []
    for digest_path in root.iterdir():
        if (
            digest_path.name not in expected
            or not digest_path.is_dir()
            or digest_path.resolve().parent != root
        ):
            raise V7ProtocolError("Unexpected V7 engine-attempt digest directory")
        candidate, seed = expected[digest_path.name]
        digest_root = digest_path.resolve()
        for attempt_path in digest_root.iterdir():
            if (
                not _ATTEMPT_DIRECTORY_RE.fullmatch(attempt_path.name)
                or not attempt_path.is_dir()
                or attempt_path.resolve().parent != digest_root
            ):
                raise V7ProtocolError("Unexpected V7 engine-attempt directory")
            attempt_root = attempt_path.resolve()
            entries = list(attempt_root.iterdir())
            if any(entry.name != "cases" for entry in entries):
                raise V7ProtocolError("Unexpected item in a V7 engine attempt")
            cases_path = attempt_root / "cases"
            if not cases_path.exists():
                continue
            cases_root = cases_path.resolve()
            if (
                cases_root != cases_path
                or cases_root.parent != attempt_root
                or not cases_root.is_dir()
            ):
                raise V7ProtocolError("V7 engine cases directory escaped its attempt")
            candidate_entries = list(cases_root.iterdir())
            if any(entry.name != candidate.candidate_id for entry in candidate_entries):
                raise V7ProtocolError("Unexpected candidate in a V7 engine attempt")
            candidate_path = cases_root / candidate.candidate_id
            if not candidate_path.exists():
                continue
            candidate_root = candidate_path.resolve()
            if (
                candidate_root != candidate_path
                or candidate_root.parent != cases_root
                or not candidate_root.is_dir()
            ):
                raise V7ProtocolError(
                    "V7 engine candidate directory escaped its attempt"
                )
            expected_seed_name = f"seed_{seed}"
            seed_entries = list(candidate_root.iterdir())
            if any(entry.name != expected_seed_name for entry in seed_entries):
                raise V7ProtocolError("Unexpected seed in a V7 engine attempt")
            case_path = candidate_root / expected_seed_name
            if not case_path.exists():
                continue
            case_dir = case_path.resolve()
            if (
                case_dir != case_path
                or case_dir.parent != candidate_root
                or not case_dir.is_dir()
            ):
                raise V7ProtocolError("V7 engine case directory escaped its attempt")
            case_dirs.append((candidate, seed, case_dir))
    return case_dirs


def _assert_official_case_pruned(case_dir: Path) -> None:
    remaining = [
        name
        for name in sorted(_ENGINE_HEAVY_DIRECTORY_NAMES)
        if (case_dir / name).exists()
    ]
    if remaining:
        raise V7ProtocolError(
            f"V7 engine case still contains canonical heavy directories: {remaining}"
        )


def _prune_official_case(
    v4: Any,
    *,
    proof: Mapping[str, Any],
    run_dir: Path,
    candidate: Any,
    seed: int,
) -> None:
    raw = proof.get("raw_evidence") or {}
    case_dir = v4._coarse_case_dir(raw, run_dir, candidate, seed)  # noqa: SLF001
    v4._prune_real_executor_case(  # noqa: SLF001
        proof,
        run_dir,
        candidate,
        seed,
    )
    _assert_official_case_pruned(case_dir)


def _cleanup_official_attempts(plan: ValidatedPlan, run_dir: Path) -> None:
    """Idempotently prune bounded orphan/completed cases while no worker runs."""

    v4, adapter = _v4_adapter(plan)
    for candidate, seed, case_dir in _official_attempt_case_dirs(plan, run_dir):
        proof = {
            "kind": "coarse_execute_candidate",
            "raw_evidence": {"run_dir": str(case_dir)},
        }
        _prune_official_case(
            v4,
            proof=proof,
            run_dir=run_dir,
            candidate=adapter["candidate_by_key"][candidate.key],
            seed=seed,
        )


def _validate_official_attempt_cleanliness(plan: ValidatedPlan, run_dir: Path) -> None:
    for _candidate, _seed, case_dir in _official_attempt_case_dirs(plan, run_dir):
        _assert_official_case_pruned(case_dir)


def _runtime_preflight(plan: ValidatedPlan) -> None:
    _validate_runtime_inventory(
        plan.manifest["runtime_dependencies"], verify_files=True
    )
    v4, adapter = _v4_adapter(plan)
    try:
        v4._assert_runtime_dependencies_current(adapter["validated_plan"])  # noqa: SLF001
    except Exception as exc:
        raise V7ProtocolError("Pinned V7/V6 execution dependencies changed") from exc


def _crn_audit_from_summary(
    summary_path: Path, *, candidate: CandidateSpec, seed: int
) -> dict[str, Any]:
    summary = _read_json(summary_path)
    policy = summary.get("policy") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    components = warmup.get("component_sha256") or {}
    invocation_hash = str(components.get("paired_rng_invocations") or "")
    global_rng_hash = str(components.get("rng_state") or "")
    core_hash = str(warmup.get("core_state_sha256") or "")
    if (
        int(policy.get("seed") or -1) != seed
        or policy.get("common_random_numbers") is not True
        or not _SHA256_RE.fullmatch(invocation_hash)
        or not _SHA256_RE.fullmatch(global_rng_hash)
        or not _SHA256_RE.fullmatch(core_hash)
    ):
        raise V7ProtocolError(f"Missing V7 common-seed audit: {candidate.key}/{seed}")
    return {
        "common_seed_block": seed,
        "common_random_numbers_requested": True,
        "warmup_boundary_paired_rng_invocations_sha256": invocation_hash,
        "warmup_boundary_global_rng_state_sha256": global_rng_hash,
        "warmup_boundary_core_state_sha256": core_hash,
        "exact_event_by_event_pairing_claimed": False,
    }


def _validate_evidence(
    payload: Mapping[str, Any],
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: CandidateSpec,
    seed: int,
    mode: str,
) -> dict[str, Any]:
    _verify_signature(payload, "evidence_signature", "V7 case evidence")
    expected_fields = {
        "schema_version",
        "plan_signature",
        "stage",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "evidence_mode",
        "graph_sha256",
        "engine_sha256",
        "metrics",
        "executor_proof",
        "compact_curve",
        "retained_bundle",
        "crn_audit",
        "valid",
        "created_at_utc",
        "evidence_signature",
    }
    inventory = plan.manifest["inventory"][candidate.key]
    engine_sha = str(
        plan.manifest["execution_contract"].get("engine", {}).get("sha256") or ""
    )
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("stage") != "validation"
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or int(payload.get("seed") or -1) != seed
        or payload.get("evidence_mode") != "fresh_physical_engine_run_v7"
        or payload.get("graph_sha256") != inventory["graph_sha256"]
        or payload.get("engine_sha256") != engine_sha
        or payload.get("valid") is not True
        or not isinstance(payload.get("created_at_utc"), str)
    ):
        raise V7ProtocolError(f"V7 evidence identity changed: {candidate.key}/{seed}")
    metrics = _normalize_metrics(payload.get("metrics") or {})
    proof = payload.get("executor_proof")
    if not isinstance(proof, Mapping):
        raise V7ProtocolError("V7 evidence lacks executor proof")
    expected_kind = (
        "coarse_execute_candidate"
        if mode == OFFICIAL_EXECUTION_MODE
        else "injected_test_executor"
    )
    if proof.get("kind") != expected_kind:
        raise V7ProtocolError("V7 evidence executor mode changed")
    if mode == OFFICIAL_EXECUTION_MODE:
        v4, adapter = _v4_adapter(plan)
        raw = proof.get("raw_evidence")
        try:
            raw_metrics = v4._validate_coarse_executor_evidence(  # noqa: SLF001
                raw,
                candidate=adapter["candidate_by_key"][candidate.key],
                seed=seed,
                plan=adapter["validated_plan"],
            )
        except Exception as exc:
            raise V7ProtocolError("Underlying V7 executor proof is invalid") from exc
        if _normalize_metrics(raw_metrics) != metrics:
            raise V7ProtocolError("V7 outer and executor metrics differ")
    elif not isinstance(proof.get("raw_payload"), Mapping):
        raise V7ProtocolError("Injected V7 evidence lacks its raw payload")
    _validate_curve_reference(
        payload.get("compact_curve"),
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
        expected_metrics=metrics,
    )
    _validate_bundle_reference(
        payload.get("retained_bundle"),
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
    )
    crn = payload.get("crn_audit")
    if not isinstance(crn, Mapping) or set(crn) != {
        "common_seed_block",
        "common_random_numbers_requested",
        "warmup_boundary_paired_rng_invocations_sha256",
        "warmup_boundary_global_rng_state_sha256",
        "warmup_boundary_core_state_sha256",
        "exact_event_by_event_pairing_claimed",
    }:
        raise V7ProtocolError("V7 common-seed audit fields changed")
    if (
        int(crn.get("common_seed_block") or -1) != seed
        or crn.get("common_random_numbers_requested") is not True
        or crn.get("exact_event_by_event_pairing_claimed") is not False
        or any(
            not _SHA256_RE.fullmatch(str(crn.get(field) or ""))
            for field in (
                "warmup_boundary_paired_rng_invocations_sha256",
                "warmup_boundary_global_rng_state_sha256",
                "warmup_boundary_core_state_sha256",
            )
        )
    ):
        raise V7ProtocolError("V7 common-seed audit is invalid")
    result = dict(payload)
    result["metrics"] = metrics
    return result


def _collect(
    plan: ValidatedPlan, run_dir: Path, mode: str
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    list[tuple[CandidateSpec, int]],
]:
    completed: dict[tuple[str, int], dict[str, Any]] = {}
    missing: list[tuple[CandidateSpec, int]] = []
    jobs = _jobs(plan)
    expected_names = {
        _evidence_path(run_dir, candidate, seed).name for candidate, seed in jobs
    }
    evidence_dir = run_dir / "evidence"
    actual_names = (
        {path.name for path in evidence_dir.glob("*.json")}
        if evidence_dir.exists()
        else set()
    )
    if actual_names - expected_names:
        raise V7ProtocolError("Unexpected evidence file exists in V7 run")
    for candidate, seed in jobs:
        path = _evidence_path(run_dir, candidate, seed)
        if not path.is_file():
            missing.append((candidate, seed))
            continue
        completed[(candidate.key, seed)] = _validate_evidence(
            _read_json(path),
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
            mode=mode,
        )
    return completed, missing


def _validate_curve_inventory(
    plan: ValidatedPlan,
    run_dir: Path,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    require_complete: bool = False,
) -> None:
    expected = {
        (run_dir / row["compact_curve"]["relative_path"]).resolve()
        for row in completed.values()
    }
    root = run_dir / "curves"
    actual = (
        {path.resolve() for path in root.rglob("*.json.gz")} if root.exists() else set()
    )
    all_expected = {
        (run_dir / _curve_relative_path(candidate, seed)).resolve()
        for candidate, seed in _jobs(plan)
    }
    if (
        not expected.issubset(actual)
        or not actual.issubset(all_expected)
        or (require_complete and actual != all_expected)
    ):
        raise V7ProtocolError("V7 compact curve inventory is incomplete or unexpected")


def _validate_bundle_inventory(
    plan: ValidatedPlan,
    run_dir: Path,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    require_complete: bool = False,
) -> None:
    referenced = {
        (run_dir / record["relative_path"]).resolve()
        for evidence in completed.values()
        for record in evidence["retained_bundle"]["files"]
    }
    root = run_dir / "snapshots"
    actual = {path.resolve() for path in root.rglob("*.gz")} if root.exists() else set()
    all_possible = {
        (run_dir / _bundle_relative_path(candidate, seed, relative)).resolve()
        for candidate, seed in _jobs(plan)
        for relative, _required in BUNDLE_SPECS
    }
    if not referenced.issubset(actual) or not actual.issubset(all_possible):
        raise V7ProtocolError(
            "V7 retained bundle inventory is incomplete or unexpected"
        )
    if require_complete and actual != referenced:
        raise V7ProtocolError("Orphan retained snapshot remains at V7 finalization")


def _complete_prefix_blocks(
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> int:
    count = 0
    for seed in V7_VALIDATION_SEEDS:
        if all((candidate.key, seed) in completed for candidate in FIXED_TRIPLET):
            count += 1
        else:
            break
    return count


def _total_complete_blocks(
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> int:
    return sum(
        all((candidate.key, seed) in completed for candidate in FIXED_TRIPLET)
        for seed in V7_VALIDATION_SEEDS
    )


def _progress_payload(
    plan: ValidatedPlan,
    run_dir: Path,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    mode = _registered_mode(plan, run_dir)
    complete_blocks = _total_complete_blocks(completed)
    unsigned = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "run_signature": _run_manifest(plan, mode)["run_signature"],
        "status": status,
        "completed_case_count": len(completed),
        "expected_case_count": EXPECTED_CASES,
        "completed_seed_block_count": complete_blocks,
        "expected_seed_block_count": VALIDATION_SEED_COUNT,
        "complete_prefix_seed_block_count": _complete_prefix_blocks(completed),
        "milestones_published": [
            milestone
            for milestone in MILESTONES
            if (run_dir / "checkpoints" / f"checkpoint_{milestone:03d}.json").is_file()
        ],
        "decision_status": (
            "eligible_for_finalization_only"
            if len(completed) == EXPECTED_CASES
            else "not_evaluated_before_all_450_cases"
        ),
        "execution_mode": mode,
        "publishable": mode == OFFICIAL_EXECUTION_MODE,
        "error": error,
        "updated_at_utc": _now(),
    }
    return _signed(unsigned, "progress_signature")


def _write_progress(
    plan: ValidatedPlan,
    run_dir: Path,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    payload = _progress_payload(plan, run_dir, completed, status=status, error=error)
    _write_json(run_dir / "progress.json", payload)
    return payload


def prepare_run(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[str, Any]:
    """Register the V7 run before any engine case; execute nothing."""

    plan = validate_plan(
        plan_dir,
        allow_test_source=test_only,
        verify_runtime=not test_only,
    )
    run_dir = run_dir.resolve()
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    with _run_lock(run_dir):
        _register_run(plan, run_dir, mode)
        completed, _missing = _collect(plan, run_dir, mode)
        _validate_curve_inventory(plan, run_dir, completed)
        _validate_bundle_inventory(plan, run_dir, completed)
        return {
            "status": (
                "registered_before_first_engine_run"
                if not completed
                else "registered_safe_resume"
            ),
            "plan_signature": plan.manifest["plan_signature"],
            "run_signature": _run_manifest(plan, mode)["run_signature"],
            "completed_case_count": len(completed),
            "new_engine_runs_by_registration": 0,
        }


def _service_pct(row: Mapping[str, Any], measure: str) -> float:
    metrics = row["metrics"]
    field = (
        "system_on_due_service" if measure == "global" else f"on_due_service_{measure}"
    )
    return 100.0 * float(metrics[field])


def _pooled_service_pct(rows: Sequence[Mapping[str, Any]], measure: str) -> float:
    demand_field = (
        "demand_qty_global" if measure == "global" else f"demand_qty_{measure}"
    )
    on_due_field = (
        "on_due_qty_global" if measure == "global" else f"on_due_qty_{measure}"
    )
    demand = sum(float(row["metrics"][demand_field]) for row in rows)
    on_due = sum(float(row["metrics"][on_due_field]) for row in rows)
    if demand <= 0.0:
        raise V7ProtocolError("Pooled service has no positive demand")
    return 100.0 * on_due / demand


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0.0 <= probability <= 1.0:
        raise V7ProtocolError("Invalid quantile request")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution_diagnostics(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise V7ProtocolError("Cannot summarize an empty service distribution")
    ordered = sorted(float(value) for value in values)
    worst_count = max(1, math.ceil(0.10 * len(ordered)))
    q25 = _quantile(ordered, 0.25)
    q75 = _quantile(ordered, 0.75)
    return {
        "mean_pct": mean(ordered),
        "p10_pct": _quantile(ordered, 0.10),
        "q25_pct": q25,
        "median_pct": _quantile(ordered, 0.50),
        "q75_pct": q75,
        "iqr_pp": q75 - q25,
        "mean_lowest_10_percent_pct": mean(ordered[:worst_count]),
        "minimum_pct": ordered[0],
        "maximum_pct": ordered[-1],
    }


def _rows_by_state(
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    seeds: Sequence[int],
) -> dict[str, list[Mapping[str, Any]]]:
    by_group = {candidate.target_group: candidate for candidate in FIXED_TRIPLET}
    return {
        group: [evidence[(candidate.key, seed)] for seed in seeds]
        for group, candidate in by_group.items()
    }


def _seedwise_diagnostics(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    count = len(rows["op_100"])
    measures: dict[str, Any] = {}
    joint_non_increasing = 0
    joint_strict = 0
    for measure in MEASURES:
        strict = 0
        non_increasing = 0
        inversion_100_93 = 0
        inversion_93_80 = 0
        ties_100_93 = 0
        ties_93_80 = 0
        for index in range(count):
            values = [
                _service_pct(rows[group][index], measure) for group in STATE_ORDER
            ]
            if values[0] > values[1] > values[2]:
                strict += 1
            if values[0] >= values[1] >= values[2]:
                non_increasing += 1
            inversion_100_93 += values[0] < values[1]
            inversion_93_80 += values[1] < values[2]
            ties_100_93 += math.isclose(values[0], values[1], abs_tol=1e-12)
            ties_93_80 += math.isclose(values[1], values[2], abs_tol=1e-12)
        measures[measure] = {
            "strictly_decreasing_seed_count": strict,
            "non_increasing_seed_count_ties_allowed": non_increasing,
            "inversion_count_op100_below_op93": inversion_100_93,
            "inversion_count_op93_below_op80": inversion_93_80,
            "tie_count_op100_op93": ties_100_93,
            "tie_count_op93_op80": ties_93_80,
            "acceptance_gate": False,
        }
    for index in range(count):
        all_non_increasing = True
        all_strict = True
        for measure in MEASURES:
            values = [
                _service_pct(rows[group][index], measure) for group in STATE_ORDER
            ]
            all_non_increasing &= values[0] >= values[1] >= values[2]
            all_strict &= values[0] > values[1] > values[2]
        joint_non_increasing += all_non_increasing
        joint_strict += all_strict
    return {
        "seed_block_count": count,
        "by_measure": measures,
        "joint_non_increasing_seed_count_ties_allowed": joint_non_increasing,
        "joint_strictly_decreasing_seed_count": joint_strict,
        "interpretation": "secondary diagnostic only; ties are not inversions",
        "acceptance_gate": False,
    }


def _descriptive_summary(
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    seeds: Sequence[int],
) -> dict[str, Any]:
    rows = _rows_by_state(evidence, seeds)
    states: dict[str, Any] = {}
    for group in STATE_ORDER:
        states[group] = {
            measure: {
                "pooled_service_pct": _pooled_service_pct(rows[group], measure),
                **_distribution_diagnostics(
                    [_service_pct(row, measure) for row in rows[group]]
                ),
            }
            for measure in MEASURES
        }
        states[group]["pooled_product_gap_pp"] = abs(
            states[group]["268091"]["pooled_service_pct"]
            - states[group]["268967"]["pooled_service_pct"]
        )
    return {
        "seed_block_count": len(seeds),
        "states": states,
        "seedwise_monotonicity": _seedwise_diagnostics(rows),
    }


def _checkpoint_payload(
    plan: ValidatedPlan,
    run_dir: Path,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    milestone: int,
) -> dict[str, Any]:
    seeds = V7_VALIDATION_SEEDS[:milestone]
    selected = {key: value for key, value in evidence.items() if key[1] in set(seeds)}
    if len(selected) != 3 * milestone:
        raise V7ProtocolError("A descriptive checkpoint lacks complete seed blocks")
    mode = _registered_mode(plan, run_dir)
    unsigned = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "run_signature": _run_manifest(plan, mode)["run_signature"],
        "status": "descriptive_only_no_early_decision",
        "milestone_seed_block_count": milestone,
        "case_count": 3 * milestone,
        "seed_prefix_sha256": stable_sha256(list(seeds)),
        "evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in selected.values())
        ),
        "summary": _descriptive_summary(selected, seeds),
        "acceptance_criteria_evaluated": False,
        "early_stop_or_decision_authorized": False,
        "created_at_utc": _now(),
    }
    return _signed(unsigned, "checkpoint_signature")


def _checkpoint_fixed_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("created_at_utc", None)
    result.pop("checkpoint_signature", None)
    return result


def _write_due_checkpoints(
    plan: ValidatedPlan,
    run_dir: Path,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    checkpoint_dir = run_dir / "checkpoints"
    actual = (
        {path.name for path in checkpoint_dir.glob("*.json")}
        if checkpoint_dir.exists()
        else set()
    )
    allowed = {f"checkpoint_{milestone:03d}.json" for milestone in MILESTONES}
    if actual - allowed:
        raise V7ProtocolError("Unexpected V7 checkpoint exists")
    prefix = _complete_prefix_blocks(evidence)
    for milestone in MILESTONES:
        if prefix < milestone:
            continue
        path = checkpoint_dir / f"checkpoint_{milestone:03d}.json"
        expected = _checkpoint_payload(plan, run_dir, evidence, milestone)
        if path.exists():
            existing = _read_json(path)
            _verify_signature(existing, "checkpoint_signature", str(path))
            if _checkpoint_fixed_view(existing) != _checkpoint_fixed_view(expected):
                raise V7ProtocolError("Existing descriptive checkpoint changed")
        else:
            _write_json(path, expected)


def _test_crn_audit(candidate: CandidateSpec, seed: int) -> dict[str, Any]:
    return {
        "common_seed_block": seed,
        "common_random_numbers_requested": True,
        "warmup_boundary_paired_rng_invocations_sha256": stable_sha256(
            {"test": "invocations", "candidate": candidate.key, "seed": seed}
        ),
        "warmup_boundary_global_rng_state_sha256": stable_sha256(
            {"test": "global_rng", "seed": seed}
        ),
        "warmup_boundary_core_state_sha256": stable_sha256(
            {"test": "core", "candidate": candidate.key, "seed": seed}
        ),
        "exact_event_by_event_pairing_claimed": False,
    }


def _execute_one(
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: CandidateSpec,
    seed: int,
    mode: str,
    executor: Executor | None,
) -> dict[str, Any]:
    test_only = mode == TEST_ONLY_EXECUTION_MODE
    evidence_path = _evidence_path(run_dir, candidate, seed)
    if evidence_path.exists():
        raise V7ProtocolError("Refusing to overwrite existing V7 case evidence")
    attempt_digest = _attempt_digest(candidate, seed)
    attempt_root = (
        run_dir
        / "engine_attempts"
        / attempt_digest
        / f"attempt-{os.getpid()}-{uuid4().hex}"
    )
    if test_only:
        if executor is None:
            raise V7ProtocolError(
                "Test-only V7 execution requires an injected executor"
            )
        raw = executor(
            candidate=candidate,
            seed=seed,
            stage="validation",
            run_dir=run_dir,
            plan=plan.manifest,
            validated_plan=plan,
            attempt_root=attempt_root,
        )
        if not isinstance(raw, Mapping):
            raise V7ProtocolError("Injected V7 executor must return a mapping")
        metrics = _normalize_metrics(raw.get("metrics") or raw)
        proof: dict[str, Any] = {
            "kind": "injected_test_executor",
            "raw_payload": {"metrics": metrics},
        }
        curve_payload, _source_sha = _synthetic_test_curve_payload(
            plan=plan,
            candidate=candidate,
            seed=seed,
            metrics=metrics,
        )
        retained_bundle = _synthetic_test_bundle(
            run_dir,
            plan=plan,
            candidate=candidate,
            seed=seed,
        )
        crn_audit = _test_crn_audit(candidate, seed)
    else:
        if executor is not None:
            raise V7ProtocolError("An injected executor cannot run in official V7 mode")
        _runtime_preflight(plan)
        v4, adapter = _v4_adapter(plan)
        v4_candidate = adapter["candidate_by_key"][candidate.key]
        raw = v4._real_executor(  # noqa: SLF001
            candidate=v4_candidate,
            seed=seed,
            stage="validation",
            run_dir=run_dir,
            plan=plan.manifest,
            validated_plan=adapter["validated_plan"],
            attempt_root=attempt_root,
        )
        if not isinstance(raw, Mapping):
            raise V7ProtocolError("Official V7 executor must return a mapping")
        metrics_raw, proof = v4._executor_output(  # noqa: SLF001
            raw,
            candidate=v4_candidate,
            seed=seed,
            plan=adapter["validated_plan"],
            injected=False,
        )
        metrics = _normalize_metrics(metrics_raw)
        case_dir = v4._coarse_case_dir(  # noqa: SLF001
            raw, run_dir, v4_candidate, seed
        )
        service_csv = case_dir / "data" / "production_demand_service_daily.csv"
        summary = case_dir / "summaries" / "first_simulation_summary.json"
        curve_payload, source_sha = _curve_payload_from_csv(
            service_csv,
            plan=plan,
            candidate=candidate,
            seed=seed,
        )
        if source_sha != raw.get("service_daily_sha256"):
            raise V7ProtocolError("Compact curve source differs from executor evidence")
        crn_audit = _crn_audit_from_summary(summary, candidate=candidate, seed=seed)
        retained_bundle = _capture_bundle_from_case(
            case_dir,
            run_dir,
            plan=plan,
            candidate=candidate,
            seed=seed,
        )
        _runtime_preflight(plan)

    curve_reference = _write_curve(
        run_dir,
        candidate=candidate,
        seed=seed,
        payload=curve_payload,
    )
    unsigned = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "stage": "validation",
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "seed": seed,
        "evidence_mode": "fresh_physical_engine_run_v7",
        "graph_sha256": plan.manifest["inventory"][candidate.key]["graph_sha256"],
        "engine_sha256": plan.manifest["execution_contract"]["engine"]["sha256"],
        "metrics": metrics,
        "executor_proof": proof,
        "compact_curve": curve_reference,
        "retained_bundle": retained_bundle,
        "crn_audit": crn_audit,
        "valid": True,
        "created_at_utc": _now(),
    }
    evidence = _signed(unsigned, "evidence_signature")
    _validate_evidence(
        evidence,
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
        mode=mode,
    )
    if not test_only:
        _prune_official_case(
            v4,
            proof=proof,
            run_dir=run_dir,
            candidate=adapter["candidate_by_key"][candidate.key],
            seed=seed,
        )
    # Publication is the transaction commit. A crash or failed prune before this
    # point leaves deterministic sidecars/an engine attempt, never a case that
    # the resume logic can mistake for completed evidence.
    if evidence_path.exists():
        raise V7ProtocolError("Refusing to overwrite existing V7 case evidence")
    _write_json(evidence_path, evidence)
    return evidence


def run_validation(
    plan_dir: Path,
    run_dir: Path,
    *,
    executor: Executor | None = None,
    max_workers: int = 2,
    test_only: bool = False,
) -> dict[str, Any]:
    """Execute/resume exactly 450 fixed V7 cases; never decide early."""

    if max_workers not in {1, 2}:
        raise V7ProtocolError("V7 permits one or two workers")
    if test_only is not (executor is not None):
        raise V7ProtocolError("Injected executors require test_only=True")
    plan = validate_plan(
        plan_dir,
        allow_test_source=test_only,
        verify_runtime=not test_only,
    )
    run_dir = run_dir.resolve()
    mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    with _run_lock(run_dir):
        if (run_dir / "validation_result.json").exists():
            raise V7ProtocolError(
                "V7 validation is already finalized; execution/resume is forbidden"
            )
        _register_run(plan, run_dir, mode)
        if not test_only:
            _runtime_preflight(plan)
            _cleanup_official_attempts(plan, run_dir)
            _runtime_preflight(plan)
            _validate_official_attempt_cleanliness(plan, run_dir)
        completed, missing = _collect(plan, run_dir, mode)
        _validate_curve_inventory(plan, run_dir, completed)
        _validate_bundle_inventory(plan, run_dir, completed)
        _write_due_checkpoints(plan, run_dir, completed)
        _write_progress(plan, run_dir, completed, status="running")

        def submit_next(
            pool: ThreadPoolExecutor,
            pending: Any,
            futures: dict[Any, tuple[CandidateSpec, int]],
        ) -> None:
            try:
                candidate, seed = next(pending)
            except StopIteration:
                return
            future = pool.submit(
                _execute_one,
                plan=plan,
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
                mode=mode,
                executor=executor,
            )
            futures[future] = (candidate, seed)

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                pending = iter(missing)
                futures: dict[Any, tuple[CandidateSpec, int]] = {}
                for _ in range(max_workers):
                    submit_next(pool, pending, futures)
                while futures:
                    future = next(as_completed(futures))
                    candidate, seed = futures.pop(future)
                    completed[(candidate.key, seed)] = future.result()
                    _write_due_checkpoints(plan, run_dir, completed)
                    _write_progress(plan, run_dir, completed, status="running")
                    submit_next(pool, pending, futures)
            validate_plan(
                plan.plan_dir,
                allow_test_source=test_only,
                verify_runtime=not test_only,
            )
            if not test_only:
                _validate_official_attempt_cleanliness(plan, run_dir)
        except BaseException as exc:
            completed, _missing = _collect(plan, run_dir, mode)
            _write_due_checkpoints(plan, run_dir, completed)
            _write_progress(
                plan,
                run_dir,
                completed,
                status="failed_resumable",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        if len(completed) != EXPECTED_CASES:
            raise V7ProtocolError("V7 validation matrix is incomplete")
        _validate_curve_inventory(plan, run_dir, completed, require_complete=True)
        _validate_bundle_inventory(plan, run_dir, completed, require_complete=True)
        _write_due_checkpoints(plan, run_dir, completed)
        return _write_progress(
            plan, run_dir, completed, status="complete_pending_finalization"
        )


def validation_status(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[str, Any]:
    """Read-only one-shot monitor; it never starts or finalizes a case."""

    plan = validate_plan(
        plan_dir,
        allow_test_source=test_only,
        verify_runtime=not test_only,
    )
    run_dir = run_dir.resolve()
    mode = _registered_mode(plan, run_dir)
    expected_mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    if mode != expected_mode:
        raise V7ProtocolError("V7 status mode differs from run registration")
    if not test_only:
        _validate_official_attempt_cleanliness(plan, run_dir)
    completed, missing = _collect(plan, run_dir, mode)
    _validate_curve_inventory(plan, run_dir, completed)
    _validate_bundle_inventory(plan, run_dir, completed)
    result_path = run_dir / "validation_result.json"
    return {
        "schema_version": f"{SCHEMA_VERSION}.monitor.v1",
        "status": (
            "finalized"
            if result_path.is_file()
            else "complete_pending_finalization"
            if not missing
            else "running_or_resumable"
        ),
        "completed_case_count": len(completed),
        "missing_case_count": len(missing),
        "expected_case_count": EXPECTED_CASES,
        "completed_seed_block_count": _total_complete_blocks(completed),
        "complete_prefix_seed_block_count": _complete_prefix_blocks(completed),
        "milestones_available": [
            milestone
            for milestone in MILESTONES
            if (run_dir / "checkpoints" / f"checkpoint_{milestone:03d}.json").is_file()
        ],
        "acceptance_decision_available": result_path.is_file(),
        "engine_runs_started_by_monitor": 0,
    }


def _validate_paired_demand(
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    for seed in V7_VALIDATION_SEEDS:
        rows = [evidence[(candidate.key, seed)] for candidate in FIXED_TRIPLET]
        for measure in MEASURES:
            field = (
                "demand_qty_global" if measure == "global" else f"demand_qty_{measure}"
            )
            values = [float(row["metrics"][field]) for row in rows]
            if max(values) - min(values) > max(1e-7, 1e-9 * max(values)):
                raise V7ProtocolError(
                    f"Demand is not paired across states for seed {seed}/{measure}"
                )


def _bootstrap_statistics(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    if replicates != BOOTSTRAP_REPLICATES:
        raise V7ProtocolError("V7 bootstrap replicate count is frozen at 50,000")
    count = VALIDATION_SEED_COUNT
    if any(len(rows[group]) != count for group in STATE_ORDER):
        raise V7ProtocolError("Bootstrap requires all 150 complete seed blocks")
    demand: dict[tuple[str, str], list[float]] = {}
    on_due: dict[tuple[str, str], list[float]] = {}
    service: dict[tuple[str, str], list[float]] = {}
    for group in STATE_ORDER:
        for measure in MEASURES:
            demand_field = (
                "demand_qty_global" if measure == "global" else f"demand_qty_{measure}"
            )
            on_due_field = (
                "on_due_qty_global" if measure == "global" else f"on_due_qty_{measure}"
            )
            demand[group, measure] = [
                float(row["metrics"][demand_field]) for row in rows[group]
            ]
            on_due[group, measure] = [
                float(row["metrics"][on_due_field]) for row in rows[group]
            ]
            service[group, measure] = [
                _service_pct(row, measure) for row in rows[group]
            ]

    global_draws = {"op_93": [], "op_80": []}
    op100_draws = {measure: [] for measure in MEASURES}
    difference_draws = {
        f"{left}_minus_{right}_{measure}": []
        for left, right in (("op_100", "op_93"), ("op_93", "op_80"))
        for measure in MEASURES
    }
    difference_keys = tuple(difference_draws)
    # One block vector and one sampling loop avoid eleven independent passes over
    # the same 150 resampled indexes.  This remains the exact frozen whole-block
    # percentile bootstrap; it only removes Python iterator overhead.
    block_vectors = [
        (
            demand["op_93", "global"][index],
            on_due["op_93", "global"][index],
            demand["op_80", "global"][index],
            on_due["op_80", "global"][index],
            demand["op_100", "global"][index],
            on_due["op_100", "global"][index],
            demand["op_100", "268091"][index],
            on_due["op_100", "268091"][index],
            demand["op_100", "268967"][index],
            on_due["op_100", "268967"][index],
            service["op_100", "global"][index] - service["op_93", "global"][index],
            service["op_100", "268091"][index] - service["op_93", "268091"][index],
            service["op_100", "268967"][index] - service["op_93", "268967"][index],
            service["op_93", "global"][index] - service["op_80", "global"][index],
            service["op_93", "268091"][index] - service["op_80", "268091"][index],
            service["op_93", "268967"][index] - service["op_80", "268967"][index],
        )
        for index in range(count)
    ]
    rng = random.Random(BOOTSTRAP_SEED)
    for _replicate in range(replicates):
        totals = [0.0] * 16
        for _index in range(count):
            vector = block_vectors[rng.randrange(count)]
            for position, value in enumerate(vector):
                totals[position] += value
        global_draws["op_93"].append(100.0 * totals[1] / totals[0])
        global_draws["op_80"].append(100.0 * totals[3] / totals[2])
        op100_draws["global"].append(100.0 * totals[5] / totals[4])
        op100_draws["268091"].append(100.0 * totals[7] / totals[6])
        op100_draws["268967"].append(100.0 * totals[9] / totals[8])
        for position, key in enumerate(difference_keys, start=10):
            difference_draws[key].append(totals[position] / count)

    alpha_global = (1.0 - GLOBAL_INTERVAL_CONFIDENCE) / 2.0
    family_alpha = (1.0 - ORDER_FAMILY_CONFIDENCE) / ORDER_COMPARISON_COUNT
    return {
        "method": "percentile_whole_seed_block_bootstrap",
        "replicates": replicates,
        "seed": BOOTSTRAP_SEED,
        "global_service_ci90_pct": {
            group: {
                "lower_pct": _quantile(values, alpha_global),
                "upper_pct": _quantile(values, 1.0 - alpha_global),
            }
            for group, values in global_draws.items()
        },
        "op100_one_sided_lower95_pct": {
            measure: _quantile(values, 1.0 - OP100_LOWER_CONFIDENCE)
            for measure, values in op100_draws.items()
        },
        "adjacent_difference_simultaneous_one_sided_lower95_pp": {
            key: _quantile(values, family_alpha)
            for key, values in difference_draws.items()
        },
        "bonferroni_per_comparison_alpha": family_alpha,
        "resampling_unit": "whole_common_seed_block_with_all_three_states",
        "positive_cross_state_correlation_assumed": False,
        "exact_eventwise_crn_required": False,
    }


def _crn_diagnostics(
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    invocation_identical = 0
    global_rng_identical = 0
    core_identical = 0
    for seed in V7_VALIDATION_SEEDS:
        audits = [
            evidence[(candidate.key, seed)]["crn_audit"] for candidate in FIXED_TRIPLET
        ]
        invocation_identical += (
            len(
                {row["warmup_boundary_paired_rng_invocations_sha256"] for row in audits}
            )
            == 1
        )
        global_rng_identical += (
            len({row["warmup_boundary_global_rng_state_sha256"] for row in audits}) == 1
        )
        core_identical += (
            len({row["warmup_boundary_core_state_sha256"] for row in audits}) == 1
        )
    return {
        "complete_seed_blocks": VALIDATION_SEED_COUNT,
        "identical_invocation_inventory_hash_triplets": invocation_identical,
        "identical_global_rng_state_hash_triplets": global_rng_identical,
        "identical_core_state_hash_triplets": core_identical,
        "acceptance_gate": False,
        "interpretation": CRN_LIMIT,
    }


def _build_result(
    plan: ValidatedPlan,
    run_dir: Path,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    mode: str,
    completed_at_utc: str,
) -> dict[str, Any]:
    _validate_paired_demand(evidence)
    rows = _rows_by_state(evidence, V7_VALIDATION_SEEDS)
    descriptive = _descriptive_summary(evidence, V7_VALIDATION_SEEDS)
    bootstrap = _bootstrap_statistics(rows)

    band_checks: dict[str, Any] = {}
    for group, (minimum, maximum) in GLOBAL_BANDS.items():
        interval = bootstrap["global_service_ci90_pct"][group]
        passed = interval["lower_pct"] >= minimum and interval["upper_pct"] <= maximum
        band_checks[group] = {
            "required_interval_pct": [minimum, maximum],
            "observed_bootstrap_ci90_pct": interval,
            "passed": passed,
        }
    op100_checks = {
        measure: {
            "required_minimum_pct": OP100_MINIMUM_PCT,
            "observed_one_sided_lower95_pct": lower,
            "passed": lower >= OP100_MINIMUM_PCT,
        }
        for measure, lower in bootstrap["op100_one_sided_lower95_pct"].items()
    }
    ordering_checks = {
        key: {
            "required_strictly_above_pp": 0.0,
            "observed_simultaneous_one_sided_lower95_pp": lower,
            "passed": lower > 0.0,
        }
        for key, lower in bootstrap[
            "adjacent_difference_simultaneous_one_sided_lower95_pp"
        ].items()
    }
    gap_checks = {
        group: {
            "required_maximum_pp": PRODUCT_GAP_MAX_PP,
            "observed_pooled_gap_pp": descriptive["states"][group][
                "pooled_product_gap_pp"
            ],
            "passed": descriptive["states"][group]["pooled_product_gap_pp"]
            <= PRODUCT_GAP_MAX_PP,
        }
        for group in STATE_ORDER
    }
    primary_checks = {
        "op93_op80_global_bootstrap90_inside_bands": all(
            row["passed"] for row in band_checks.values()
        ),
        "op100_global_and_products_lower95_at_least_98p5": all(
            row["passed"] for row in op100_checks.values()
        ),
        "six_simultaneous_adjacent_difference_lower95_above_zero": all(
            row["passed"] for row in ordering_checks.values()
        ),
        "product_gap_at_most_5pp_in_each_state": all(
            row["passed"] for row in gap_checks.values()
        ),
        "all_450_fresh_cases_complete": len(evidence) == EXPECTED_CASES,
        "paired_demand_identity_valid": True,
    }
    accepted = all(primary_checks.values())
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "run_signature": _run_manifest(plan, mode)["run_signature"],
        "status": ACCEPTED_STATUS if accepted else REJECTED_STATUS,
        "accepted": accepted,
        "publishable": mode == OFFICIAL_EXECUTION_MODE,
        "execution_mode": mode,
        "interpretation": INTERPRETATION,
        "fixed_triplet": [candidate.payload() for candidate in FIXED_TRIPLET],
        "validation_seed_count": VALIDATION_SEED_COUNT,
        "fresh_physical_evidence_case_count": len(evidence),
        "v5_v6_acceptance_evidence_reused": False,
        "v6_holdout_used_for_protocol_diagnosis_and_sample_sizing": True,
        "v6_holdout_reused_as_v7_acceptance_evidence": False,
        "evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "decision_contract": plan.manifest["decision_contract"],
        "primary_checks": primary_checks,
        "global_band_checks": band_checks,
        "op100_lower_bound_checks": op100_checks,
        "simultaneous_ordering_checks": ordering_checks,
        "product_gap_checks": gap_checks,
        "bootstrap": bootstrap,
        "descriptive_diagnostics": descriptive,
        "common_seed_diagnostics": _crn_diagnostics(evidence),
        "seedwise_monotonicity_is_acceptance_gate": False,
        "ceiling_ties_are_failures": False,
        "interim_checkpoints_used_for_decision": False,
        "retuning_after_any_v7_result": False,
        "failure_rule": "publish_no_go; new version and new seeds required",
        "completed_at_utc": completed_at_utc,
    }
    return _signed(unsigned, "result_signature")


def finalize_validation(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[str, Any]:
    """Apply the frozen criteria once, and only after all 450 cases exist."""

    plan = validate_plan(
        plan_dir,
        allow_test_source=test_only,
        verify_runtime=not test_only,
    )
    run_dir = run_dir.resolve()
    expected_mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    with _run_lock(run_dir):
        mode = _registered_mode(plan, run_dir)
        if mode != expected_mode:
            raise V7ProtocolError("V7 finalization mode differs from registration")
        if not test_only:
            _validate_official_attempt_cleanliness(plan, run_dir)
        evidence, missing = _collect(plan, run_dir, mode)
        _validate_curve_inventory(plan, run_dir, evidence, require_complete=True)
        _validate_bundle_inventory(plan, run_dir, evidence, require_complete=True)
        progress = _read_json(run_dir / "progress.json")
        _verify_signature(progress, "progress_signature", "V7 progress")
        if (
            missing
            or len(evidence) != EXPECTED_CASES
            or progress.get("status") != "complete_pending_finalization"
            or progress.get("completed_case_count") != EXPECTED_CASES
            or progress.get("completed_seed_block_count") != VALIDATION_SEED_COUNT
            or progress.get("decision_status") != "eligible_for_finalization_only"
        ):
            raise V7ProtocolError("V7 cannot be finalized before 450 complete cases")
        _write_due_checkpoints(plan, run_dir, evidence)
        result = _build_result(
            plan,
            run_dir,
            evidence,
            mode=mode,
            completed_at_utc=str(progress["updated_at_utc"]),
        )
        output = run_dir / "validation_result.json"
        if output.exists():
            existing = _read_json(output)
            _verify_signature(existing, "result_signature", "V7 validation result")
            if existing != result:
                raise V7ProtocolError("Existing V7 validation result differs")
        else:
            _write_json(output, result)
        return result


def validated_evidence(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[tuple[str, int], dict[str, Any]]:
    """Return the complete, validated read-only V7 evidence index."""

    plan = validate_plan(
        plan_dir,
        allow_test_source=test_only,
        verify_runtime=not test_only,
    )
    run_dir = run_dir.resolve()
    expected_mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    mode = _registered_mode(plan, run_dir)
    if mode != expected_mode:
        raise V7ProtocolError("V7 evidence mode differs from run registration")
    if not test_only:
        _validate_official_attempt_cleanliness(plan, run_dir)
    evidence, missing = _collect(plan, run_dir, mode)
    if missing or len(evidence) != EXPECTED_CASES:
        raise V7ProtocolError("V7 evidence index requires all 450 signed cases")
    _validate_curve_inventory(plan, run_dir, evidence, require_complete=True)
    _validate_bundle_inventory(plan, run_dir, evidence, require_complete=True)
    return {key: dict(value) for key, value in evidence.items()}


def validate_result(
    plan_dir: Path, run_dir: Path, *, test_only: bool = False
) -> dict[str, Any]:
    """Rebuild and validate a finalized V7 decision from all signed evidence."""

    plan = validate_plan(
        plan_dir,
        allow_test_source=test_only,
        verify_runtime=not test_only,
    )
    run_dir = run_dir.resolve()
    expected_mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    mode = _registered_mode(plan, run_dir)
    if mode != expected_mode:
        raise V7ProtocolError("V7 result mode differs from run registration")
    if not test_only:
        _validate_official_attempt_cleanliness(plan, run_dir)
    evidence, missing = _collect(plan, run_dir, mode)
    if missing or len(evidence) != EXPECTED_CASES:
        raise V7ProtocolError("A V7 result requires all 450 signed cases")
    _validate_curve_inventory(plan, run_dir, evidence, require_complete=True)
    _validate_bundle_inventory(plan, run_dir, evidence, require_complete=True)
    progress = _read_json(run_dir / "progress.json")
    _verify_signature(progress, "progress_signature", "V7 progress")
    if (
        progress.get("status") != "complete_pending_finalization"
        or progress.get("completed_case_count") != EXPECTED_CASES
        or progress.get("completed_seed_block_count") != VALIDATION_SEED_COUNT
        or progress.get("decision_status") != "eligible_for_finalization_only"
    ):
        raise V7ProtocolError("V7 progress is not eligible for result validation")
    output = run_dir / "validation_result.json"
    if not output.is_file():
        raise V7ProtocolError("V7 validation result is missing")
    observed = _read_json(output)
    _verify_signature(observed, "result_signature", "V7 validation result")
    expected = _build_result(
        plan,
        run_dir,
        evidence,
        mode=mode,
        completed_at_utc=str(progress["updated_at_utc"]),
    )
    if observed != expected:
        raise V7ProtocolError("V7 validation result differs from signed evidence")
    return observed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("prepare-plan", help="freeze reviewed V7 plan; run no engine")
    plan.add_argument("--v6-plan-dir", type=Path, default=DEFAULT_V6_PLAN)
    plan.add_argument("--v6-run-dir", type=Path, default=DEFAULT_V6_RUN)
    plan.add_argument(
        "--v6-holdout-result", type=Path, default=DEFAULT_V6_HOLDOUT_RESULT
    )
    plan.add_argument("--rng-audit-dir", type=Path, default=DEFAULT_RNG_AUDIT_DIR)
    plan.add_argument("--output-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    plan.add_argument("--reviewed-module-sha256", required=True)
    validate = sub.add_parser("validate-plan", help="validate immutable V7 plan")
    validate.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    register = sub.add_parser("prepare-run", help="register run; execute no case")
    register.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    register.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run = sub.add_parser("run-validation", help="execute/resume fixed 450-case matrix")
    run.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run.add_argument("--workers", type=int, choices=(1, 2), default=2)
    status = sub.add_parser("status", help="read-only one-shot progress monitor")
    status.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    status.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    finalize = sub.add_parser("finalize", help="decide only after all 450 cases")
    finalize.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    finalize.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    validate_result_parser = sub.add_parser(
        "validate-result", help="rebuild final decision from all signed evidence"
    )
    validate_result_parser.add_argument(
        "--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT
    )
    validate_result_parser.add_argument(
        "--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare-plan":
            result: Any = {
                "status": "plan_created_no_engine_run",
                "manifest": str(
                    prepare_plan(
                        args.output_dir,
                        v6_plan_dir=args.v6_plan_dir,
                        v6_run_dir=args.v6_run_dir,
                        v6_holdout_result=args.v6_holdout_result,
                        rng_audit_dir=args.rng_audit_dir,
                        reviewed_module_sha256=args.reviewed_module_sha256,
                    )
                ),
            }
        elif args.command == "validate-plan":
            plan = validate_plan(args.plan_dir)
            result = {
                "status": "plan_valid_no_engine_run",
                "plan_signature": plan.manifest["plan_signature"],
            }
        elif args.command == "prepare-run":
            result = prepare_run(args.plan_dir, args.run_dir)
        elif args.command == "run-validation":
            result = run_validation(
                args.plan_dir, args.run_dir, max_workers=args.workers
            )
        elif args.command == "status":
            result = validation_status(args.plan_dir, args.run_dir)
        elif args.command == "finalize":
            result = finalize_validation(args.plan_dir, args.run_dir)
        else:
            result = validate_result(args.plan_dir, args.run_dir)
    except Exception as exc:
        print(f"V7 REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
