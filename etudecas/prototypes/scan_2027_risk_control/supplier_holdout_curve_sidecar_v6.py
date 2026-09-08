#!/usr/bin/env python3
"""V6 orchestration around the proven V4/V5 loss-tolerant capture core.

The snapshot/parsing core is reused byte-pinned.  V6 additively hardens the
single-watcher lock, pre-engine ready handshake, source separation, final deep
inventory validation, producer provenance and schema binding.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_holdout_v6 as holdout_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v5 as implementation_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_v4_calibration as process_helper_v4,
)


SCHEMA_VERSION = "etudecas.supplier_holdout_curve_sidecar.v6"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
READY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.watcher_ready.v1"
INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.inventory.v1"
EXPECTED_TARGET_GROUPS = implementation_v5.EXPECTED_TARGET_GROUPS
EXPECTED_CASES_PER_GROUP = implementation_v5.EXPECTED_CASES_PER_GROUP
EXPECTED_CASE_COUNT = implementation_v5.EXPECTED_CASE_COUNT
DEFAULT_HORIZON = implementation_v5.DEFAULT_HORIZON
EXPECTED_V5_IMPLEMENTATION_SHA256 = (
    "cdb5c110c847e39a189d87b93a2aca08295913b593c039307b7006b1341ded8a"
)
EXPECTED_V4_CAPTURE_CORE_SHA256 = (
    "f6198f12f8d81b8280df781155a31173a90f6344d1f47878aaebbc4321290f3b"
)
EXPECTED_V4_PROCESS_HELPER_SHA256 = (
    "9a7e7762599138a950202f02794ef52034fc1e3c396060eb91fa1006c6e5a18d"
)
COMPATIBILITY_INVENTORY_FILENAME = "capture_inventory_v5.json"

CurveSidecarError = implementation_v5.CurveSidecarError
ExpectedCase = implementation_v5.ExpectedCase
capture_v4 = implementation_v5.capture_v4
_V5_BUILD_CONTRACT = implementation_v5.build_contract
_V5_VALIDATE_CONTRACT = implementation_v5.validate_contract


def validate_frozen_implementation() -> Path:
    path = Path(implementation_v5.__file__).resolve()
    core_path = Path(capture_v4.__file__).resolve()
    helper_path = Path(process_helper_v4.__file__).resolve()
    if (
        capture_v4.sha256_file(path) != EXPECTED_V5_IMPLEMENTATION_SHA256
        or capture_v4.sha256_file(core_path) != EXPECTED_V4_CAPTURE_CORE_SHA256
        or capture_v4.sha256_file(helper_path) != EXPECTED_V4_PROCESS_HELPER_SHA256
    ):
        raise CurveSidecarError("Frozen V4/V5 curve-capture implementation changed")
    return path


def _producer_provenance() -> dict[str, str]:
    reused_path = validate_frozen_implementation()
    adapter_path = Path(__file__).resolve()
    core_path = Path(capture_v4.__file__).resolve()
    helper_path = Path(process_helper_v4.__file__).resolve()
    return {
        "v6_adapter_path": str(adapter_path),
        "v6_adapter_sha256": capture_v4.sha256_file(adapter_path),
        "reused_v5_path": str(reused_path),
        "reused_v5_sha256": EXPECTED_V5_IMPLEMENTATION_SHA256,
        "capture_core_v4_path": str(core_path),
        "capture_core_v4_sha256": EXPECTED_V4_CAPTURE_CORE_SHA256,
        "process_helper_v4_path": str(helper_path),
        "process_helper_v4_sha256": EXPECTED_V4_PROCESS_HELPER_SHA256,
    }


def _write_v6_inventory(
    *,
    output_dir: Path,
    contract: Mapping[str, Any],
    base_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish V6 provenance using the compatibility filename consumed downstream."""

    base_path = output_dir / "capture_inventory.json"
    unsigned = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "created_at_utc": implementation_v5._now(),  # noqa: SLF001
        "status": "complete",
        "contract_signature": contract["contract_signature"],
        "case_count": int(base_inventory["case_count"]),
        "base_inventory_path": str(base_path.resolve()),
        "base_inventory_sha256": capture_v4.sha256_file(base_path),
        "base_inventory_signature": base_inventory["inventory_signature"],
        "interpretation": (
            "Courbes descriptives de 90 simulations de holdout V6 fraîches; "
            "ni observations fournisseurs, ni probabilités historiques."
        ),
        "compatibility_filename": COMPATIBILITY_INVENTORY_FILENAME,
        "producer": _producer_provenance(),
    }
    payload = {**unsigned, "inventory_signature": capture_v4.stable_sha256(unsigned)}
    path = output_dir / COMPATIBILITY_INVENTORY_FILENAME
    if path.exists():
        existing = capture_v4._read_json(path)  # noqa: SLF001
        capture_v4._verify_signature(  # noqa: SLF001
            existing, "inventory_signature", "inventaire V6"
        )
        comparable_existing = dict(existing)
        comparable_payload = dict(payload)
        for candidate in (comparable_existing, comparable_payload):
            candidate.pop("created_at_utc", None)
            candidate.pop("inventory_signature", None)
        if comparable_existing != comparable_payload:
            raise CurveSidecarError("A different V6 inventory already exists")
        return existing
    capture_v4._atomic_write_json(path, payload)  # noqa: SLF001
    return payload


def validate_inventory(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    path = output_dir / COMPATIBILITY_INVENTORY_FILENAME
    payload = capture_v4._read_json(path)  # noqa: SLF001
    capture_v4._verify_signature(  # noqa: SLF001
        payload, "inventory_signature", "inventaire V6"
    )
    producer = payload.get("producer") or {}
    contract_path = output_dir / "capture_contract.json"
    ready_path = output_dir / "watcher_ready.json"
    base_path = output_dir / "capture_inventory.json"
    contract = validate_contract(capture_v4._read_json(contract_path))  # noqa: SLF001
    ready = validate_ready(ready_path, expected_output_dir=output_dir)
    base = capture_v4._read_json(base_path)  # noqa: SLF001
    capture_v4._verify_signature(  # noqa: SLF001
        base, "inventory_signature", "inventaire de base V6"
    )
    plan_dir = Path(str((contract.get("plan") or {}).get("directory") or ""))
    run_dir = Path(str((contract.get("run") or {}).get("directory") or ""))
    plan_binding = contract.get("plan") or {}
    run_binding = contract.get("run") or {}
    plan_manifest = plan_dir.resolve() / "refinement_plan.json"
    run_manifest = run_dir.resolve() / "run_manifest.json"
    expected_cases = load_official_cases(plan_dir, run_dir)
    expected_rows = [asdict(case) for case in expected_cases]
    captured_rows = base.get("cases")
    if (
        payload.get("schema_version") != INVENTORY_SCHEMA_VERSION
        or payload.get("status") != "complete"
        or int(payload.get("case_count") or -1) != EXPECTED_CASE_COUNT
        or payload.get("compatibility_filename") != COMPATIBILITY_INVENTORY_FILENAME
        or producer != _producer_provenance()
        or payload.get("contract_signature") != contract.get("contract_signature")
        or payload.get("base_inventory_path") != str(base_path.resolve())
        or payload.get("base_inventory_sha256") != capture_v4.sha256_file(base_path)
        or payload.get("base_inventory_signature") != base.get("inventory_signature")
        or ready.get("contract_signature") != contract.get("contract_signature")
        or contract.get("cases") != expected_rows
        or not isinstance(captured_rows, list)
        or len(captured_rows) != EXPECTED_CASE_COUNT
        or base.get("schema_version") != capture_v4.INVENTORY_SCHEMA_VERSION
        or base.get("status") != "complete"
        or int(base.get("case_count") or -1) != EXPECTED_CASE_COUNT
        or base.get("contract_signature") != contract.get("contract_signature")
        or Path(str(contract.get("output_directory") or "")).resolve()
        != output_dir
        or Path(str(plan_binding.get("manifest_path") or "")).resolve()
        != plan_manifest
        or plan_binding.get("manifest_sha256")
        != capture_v4.sha256_file(plan_manifest)
        or Path(str(run_binding.get("manifest_path") or "")).resolve()
        != run_manifest
        or run_binding.get("manifest_sha256")
        != capture_v4.sha256_file(run_manifest)
    ):
        raise CurveSidecarError("Final V6 curve inventory is inconsistent")
    expected_by_identity = {case.identity: case for case in expected_cases}
    if len(expected_by_identity) != EXPECTED_CASE_COUNT:
        raise CurveSidecarError("Duplicate expected V6 sidecar identities")
    try:
        captured_identities = {
            (str(row["candidate_id"]), int(row["seed"]))
            for row in captured_rows
            if isinstance(row, Mapping)
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise CurveSidecarError("Invalid V6 sidecar identities") from exc
    if (
        len(captured_identities) != EXPECTED_CASE_COUNT
        or captured_identities != set(expected_by_identity)
    ):
        raise CurveSidecarError("V6 sidecar identities are not exhaustive and unique")
    required_filenames = {spec.filename for spec in capture_v4.CSV_SPECS if spec.required}
    allowed_filenames = {spec.filename for spec in capture_v4.CSV_SPECS}
    for row in captured_rows:
        if not isinstance(row, Mapping):
            raise CurveSidecarError("Invalid V6 sidecar case row")
        identity = (str(row.get("candidate_id") or ""), int(row.get("seed") or -1))
        case = expected_by_identity.get(identity)
        if case is None or any(
            row.get(field) != getattr(case, field)
            for field in ("target_group", "candidate_key", "candidate_id", "seed")
        ):
            raise CurveSidecarError("Unexpected V6 sidecar case identity")
        manifest_path = Path(str(row.get("case_manifest_path") or "")).resolve()
        if (
            not manifest_path.is_file()
            or not manifest_path.is_relative_to(output_dir)
            or row.get("case_manifest_sha256")
            != capture_v4.sha256_file(manifest_path)
        ):
            raise CurveSidecarError("Missing or altered V6 sidecar case manifest")
        manifest = capture_v4._validate_existing_case_manifest(  # noqa: SLF001
            manifest_path,
            contract_signature=str(contract["contract_signature"]),
            case=case,
        )
        files = manifest.get("files")
        if not isinstance(files, list) or any(
            not isinstance(file_row, Mapping) for file_row in files
        ):
            raise CurveSidecarError("Invalid V6 sidecar snapshot list")
        filenames = {str(file_row.get("filename") or "") for file_row in files}
        if (
            row.get("case_signature") != manifest.get("case_signature")
            or int(row.get("captured_csv_count") or -1) != len(files)
            or not required_filenames.issubset(filenames)
            or not filenames.issubset(allowed_filenames)
        ):
            raise CurveSidecarError("V6 sidecar inventory and manifest differ")
        summary_data, summary_meta = capture_v4._summary_paths(  # noqa: SLF001
            output_dir, case
        )
        summary = capture_v4._validate_stored_snapshot(  # noqa: SLF001
            summary_data, summary_meta
        )
        summary_binding = manifest.get("summary") or {}
        if (
            Path(str(summary_binding.get("snapshot_path") or "")).resolve()
            != summary_data.resolve()
            or summary_binding.get("snapshot_gzip_sha256")
            != summary.get("snapshot_gzip_sha256")
            or summary_binding.get("source_sha256") != summary.get("source_sha256")
        ):
            raise CurveSidecarError("Altered V6 sidecar summary snapshot")
        for file_row in files:
            data_path, meta_path = capture_v4._snapshot_paths(  # noqa: SLF001
                output_dir, case, str(file_row["filename"])
            )
            metadata = capture_v4._validate_stored_snapshot(  # noqa: SLF001
                data_path, meta_path
            )
            if (
                Path(str(file_row.get("snapshot_path") or "")).resolve()
                != data_path.resolve()
                or file_row.get("snapshot_gzip_sha256")
                != metadata.get("snapshot_gzip_sha256")
                or file_row.get("source_sha256") != metadata.get("source_sha256")
            ):
                raise CurveSidecarError("Altered V6 sidecar CSV snapshot")
    return payload


@contextmanager
def _v6_binding() -> Iterator[None]:
    validate_frozen_implementation()
    names = {
        "refinement": holdout_v6,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "CONTRACT_SCHEMA_VERSION": CONTRACT_SCHEMA_VERSION,
        "READY_SCHEMA_VERSION": READY_SCHEMA_VERSION,
        "INVENTORY_SCHEMA_VERSION": INVENTORY_SCHEMA_VERSION,
        "build_contract": build_contract,
        "validate_contract": validate_contract,
        "_write_v5_inventory": _write_v6_inventory,
    }
    previous = {name: getattr(implementation_v5, name) for name in names}
    try:
        for name, value in names.items():
            setattr(implementation_v5, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(implementation_v5, name, value)


def load_official_cases(plan_dir: Path, run_dir: Path) -> tuple[ExpectedCase, ...]:
    with _v6_binding():
        return implementation_v5.load_official_cases(plan_dir, run_dir)


def _assert_output_separate_from_all_sources(
    plan_dir: Path, run_dir: Path, output_dir: Path
) -> None:
    plan = holdout_v6.validate_plan(plan_dir, verify_runtime_dependencies=True)
    source = plan.manifest["v6_development_source"]
    development_plan = holdout_v6.development_v6.validate_plan(
        Path(source["plan_dir"]), verify_runtime_dependencies=True
    )
    v5_source = development_plan.manifest["v5_no_go_source"]
    v5_plan = holdout_v6.development_v6.v5.validate_plan(
        Path(v5_source["plan_dir"]), verify_runtime_dependencies=True
    )
    protected = (
        plan.plan_dir,
        run_dir.resolve(),
        Path(source["plan_dir"]).resolve(),
        Path(source["run_dir"]).resolve(),
        Path(v5_source["plan_dir"]).resolve(),
        Path(v5_source["run_dir"]).resolve(),
        Path(v5_source["holdout_non_use_audit"]["sidecar_root"]).resolve(),
        *holdout_v6.development_v6.v5._protected_source_directories(  # noqa: SLF001
            v5_plan, v5_source
        ),
    )
    output_dir = output_dir.resolve()
    if any(holdout_v6._paths_overlap(output_dir, path) for path in protected):  # noqa: SLF001
        raise CurveSidecarError("V6 sidecar output overlaps an immutable source")


def build_contract(
    *,
    plan_dir: Path,
    run_dir: Path,
    output_dir: Path,
    cases: Sequence[ExpectedCase],
    horizon: int = DEFAULT_HORIZON,
) -> dict[str, Any]:
    _assert_output_separate_from_all_sources(plan_dir, run_dir, output_dir)
    with _v6_binding():
        payload = _V5_BUILD_CONTRACT(
            plan_dir=plan_dir,
            run_dir=run_dir,
            output_dir=output_dir,
            cases=cases,
            horizon=horizon,
        )
    unsigned = dict(payload)
    unsigned.pop("contract_signature", None)
    unsigned["producer"] = _producer_provenance()
    return {**unsigned, "contract_signature": capture_v4.stable_sha256(unsigned)}


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    with _v6_binding():
        payload = _V5_VALIDATE_CONTRACT(contract)
    if payload.get("producer") != _producer_provenance():
        raise CurveSidecarError("V6 sidecar producer provenance changed")
    return payload


def validate_ready(
    path: Path,
    *,
    expected_output_dir: Path | None = None,
    expected_watcher_pid: int | None = None,
) -> dict[str, Any]:
    payload = capture_v4._read_json(path)  # noqa: SLF001
    return validate_ready_payload(
        payload,
        expected_output_dir=expected_output_dir,
        expected_watcher_pid=expected_watcher_pid,
    )


def validate_ready_payload(
    payload: Mapping[str, Any],
    *,
    expected_output_dir: Path | None = None,
    expected_watcher_pid: int | None = None,
) -> dict[str, Any]:
    with _v6_binding():
        result = dict(payload)
        capture_v4._verify_signature(  # noqa: SLF001
            result, "ready_signature", "accusé watcher V6"
        )
        if (
            result.get("schema_version") != READY_SCHEMA_VERSION
            or result.get("status") != "ready_before_holdout"
            or int(result.get("expected_case_count") or -1) != EXPECTED_CASE_COUNT
            or int(result.get("holdout_seed_count") or -1)
            != len(holdout_v6.EXPECTED_HOLDOUT_SEEDS)
            or int(result.get("watcher_pid") or -1) <= 0
        ):
            raise CurveSidecarError("V6 watcher ready acknowledgement is inconsistent")
        if (
            expected_output_dir is not None
            and Path(str(result.get("output_directory") or "")).resolve()
            != expected_output_dir.resolve()
        ):
            raise CurveSidecarError("V6 watcher ready output directory differs")
        if expected_watcher_pid is not None and int(
            result.get("watcher_pid") or -1
        ) != int(expected_watcher_pid):
            raise CurveSidecarError("V6 watcher ready PID differs")
        return result


@contextmanager
def _watcher_lock(output_dir: Path) -> Iterator[None]:
    """Hold an OS-backed single-watcher lock that is released after a hard exit."""

    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    path = output_dir.parent / f".{output_dir.name}.v6-sidecar.lock"
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
            raise CurveSidecarError("Another V6 curve watcher is already active") from exc
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


def assert_watcher_lease_active(output_dir: Path) -> Path:
    """Prove that another process still owns the V6 watcher OS lease."""

    output_dir = output_dir.resolve()
    path = output_dir.parent / f".{output_dir.name}.v6-sidecar.lock"
    if not path.is_file():
        raise CurveSidecarError("V6 watcher lease does not exist")
    handle = path.open("r+b")
    acquired = False
    try:
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            return path
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
    raise CurveSidecarError("No active V6 watcher owns the OS lease")


def run_watcher(
    *,
    plan_dir: Path,
    run_dir: Path,
    output_dir: Path,
    poll_seconds: float,
    stability_seconds: float,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    if (
        poll_seconds <= 0
        or stability_seconds < 0
        or (timeout_seconds is not None and timeout_seconds <= 0)
    ):
        raise CurveSidecarError("Invalid V6 watcher timing configuration")
    cases = load_official_cases(plan_dir, run_dir)
    contract = build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        cases=cases,
    )
    output_dir = output_dir.resolve()
    with _watcher_lock(output_dir):
        capture_v4.register_contract(output_dir, contract)
        registered = validate_contract(
            capture_v4._read_json(output_dir / "capture_contract.json")  # noqa: SLF001
        )
        with _v6_binding():
            watcher = implementation_v5.V5CurveCaptureWatcher(
                contract=registered,
                output_dir=output_dir,
                poll_seconds=poll_seconds,
                stability_seconds=stability_seconds,
            )
            # Constructor and an initial scan must succeed before authorization.
            watcher.scan_once()
            ready = implementation_v5._ready_payload(  # noqa: SLF001
                registered, output_dir=output_dir
            )
            ready_path = output_dir / "watcher_ready.json"
            if ready_path.exists():
                existing = validate_ready(ready_path, expected_output_dir=output_dir)
                if existing.get("contract_signature") != registered.get(
                    "contract_signature"
                ):
                    raise CurveSidecarError(
                        "Existing V6 watcher acknowledgement targets another contract"
                    )
                if int(existing["watcher_pid"]) != os.getpid():
                    capture_v4._atomic_write_json(ready_path, ready)  # noqa: SLF001
            else:
                capture_v4._atomic_write_json(ready_path, ready)  # noqa: SLF001
            result = watcher.watch(timeout_seconds=timeout_seconds)
        validate_inventory(output_dir)
        return result


def main(argv: Sequence[str] | None = None) -> int:
    args = implementation_v5._parser().parse_args(argv)  # noqa: SLF001
    if args.command == "watch":
        result = run_watcher(
            plan_dir=args.plan_dir,
            run_dir=args.run_dir,
            output_dir=args.output_dir,
            poll_seconds=args.poll_ms / 1000.0,
            stability_seconds=args.stability_ms / 1000.0,
            timeout_seconds=(args.timeout_seconds or None),
        )
    elif args.command == "finalize":
        contract = validate_contract(
            capture_v4._read_json(  # noqa: SLF001
                args.output_dir / "capture_contract.json"
            )
        )
        base_inventory = capture_v4.finalize_capture(contract, args.output_dir)
        result = _write_v6_inventory(
            output_dir=args.output_dir.resolve(),
            contract=contract,
            base_inventory=base_inventory,
        )
        validate_inventory(args.output_dir)
    else:
        result = validate_ready(
            args.output_dir / "watcher_ready.json",
            expected_output_dir=args.output_dir,
            expected_watcher_pid=args.watcher_pid,
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
