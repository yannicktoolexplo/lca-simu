#!/usr/bin/env python3
"""Capture immutable J0 stock evidence before V3 summary retention removes raw data.

The collector is read-only with respect to V2, V3, the graph and the engine.  It
writes a new, separate two-file snapshot.  A 30-seed snapshot can inherit the
signed first 15 seeds from an earlier snapshot and capture only seeds 16--30
while their completed V3 baseline files still exist.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_exploratory_action_runner as action,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_post_priority_extension_runner as post_runner,
)


DEFAULT_OUTPUT_DIR = (
    action.protocol.ARTIFACT_PARENT / "supplier_network_action_j0_snapshot_20260903_v1"
)


def _canonical_row(row: Mapping[str, Any]) -> dict[str, str]:
    result = {
        column: str(row.get(column) or "")
        for column in action.J0_SNAPSHOT_COLUMNS
        if column != "row_signature"
    }
    return {**result, "row_signature": action._stable_sha256(result)}


def _read_snapshot_rows(snapshot_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    root = snapshot_dir.resolve()
    manifest_path = action._required_file(
        root / action.J0_SNAPSHOT_MANIFEST, "base J0 snapshot manifest"
    )
    rows_path = action._required_file(root / action.J0_SNAPSHOT_ROWS, "base J0 rows")
    inventory = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if inventory != {action.J0_SNAPSHOT_MANIFEST, action.J0_SNAPSHOT_ROWS}:
        raise ValueError("Base J0 snapshot inventory is not exact")
    manifest = action._read_json(manifest_path)
    action._validate_signed_payload(
        manifest, "snapshot_signature", label="base J0 snapshot"
    )
    rows = action._read_csv(rows_path)
    if (
        manifest.get("schema_version") != action.J0_SNAPSHOT_SCHEMA_VERSION
        or manifest.get("contract_revision") != action.CONTRACT_REVISION
        or manifest.get("rows_file") != action.J0_SNAPSHOT_ROWS
        or manifest.get("rows_sha256") != action._sha256(rows_path)
        or action._to_int(manifest.get("row_count"), -1) != len(rows)
        or any(set(row) != set(action.J0_SNAPSHOT_COLUMNS) for row in rows)
        or any(
            row.get("row_signature") != action._snapshot_row_signature(row)
            for row in rows
        )
    ):
        raise ValueError("Base J0 snapshot is invalid")
    return manifest, rows


def _load_v3_contract(
    plan: action.ActionPlan,
    post_priority_results_dir: Path,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    root = post_priority_results_dir.resolve()
    manifest_path = action._required_file(
        root / post_runner.RUNNER_MANIFEST, "V3 execution manifest"
    )
    manifest = action._read_json(manifest_path)
    status = str(manifest.get("status") or "")
    plan_manifest_path = (
        plan.post_priority_plan_dir / "post_priority_extensions_plan_manifest.json"
    )
    source_manifest_path = plan.source_dir / "campaign_manifest.json"
    if (
        status not in {"running", "paused_preliminary", "complete"}
        or manifest.get("plan_signature")
        != plan.post_priority_plan_manifest.get("plan_signature")
        or manifest.get("plan_manifest_sha256") != action._sha256(plan_manifest_path)
        or manifest.get("source_campaign_manifest_sha256")
        != action._sha256(source_manifest_path)
        or tuple(
            action._to_int(value, -1)
            for value in manifest.get("signed_full_seed_ids") or []
        )
        != plan.seeds
        or action._as_bool(manifest.get("custom_executor_used"))
    ):
        raise ValueError("V3 execution lineage is not the frozen V5 source")
    ledger_path = action._required_file(root / post_runner.LEDGER_FILE, "V3 ledger")
    ledger = action._read_json(ledger_path)
    files = ledger.get("case_files") or {}
    hashes = ledger.get("case_file_sha256") or {}
    if (
        ledger.get("runner_signature") != manifest.get("runner_signature")
        or not isinstance(files, dict)
        or not isinstance(hashes, dict)
        or set(files) != set(hashes)
    ):
        raise ValueError("V3 live ledger is malformed or unpaired")
    if status == "complete":
        action._validate_completed_v3_ledger(
            manifest=manifest,
            ledger=ledger,
            ledger_path=ledger_path,
        )
    return root, manifest, ledger_path, ledger


def _capture_seed_rows(
    *,
    plan: action.ActionPlan,
    v3_root: Path,
    v3_manifest: Mapping[str, Any],
    v3_ledger: Mapping[str, Any],
    v2_rows: Mapping[tuple[str, int], Mapping[str, str]],
    seed: int,
) -> list[dict[str, str]]:
    baseline_key = action._v3_baseline_key(seed)
    evidence, evidence_hash = action._load_v3_evidence(
        v3_root, v3_ledger, baseline_key
    )
    normal = v2_rows.get(("baseline_nominal", seed))
    if (
        normal is None
        or not action._as_bool(normal.get("valid"))
        or evidence.get("seed") != seed
        or evidence.get("input_sha256") != normal.get("input_sha256")
        or evidence.get("j0_state_sha256") != normal.get("j0_state_sha256")
        or action._to_int(evidence.get("simulation_days"), -1) != action.MEASURED_DAYS
        or evidence.get("valid") is not True
        or evidence.get("configured_event_ids") not in ([], None)
        or evidence.get("applied_event_ids") not in ([], None)
        or evidence.get("resolved_lot_trace_enabled") not in {True, False}
    ):
        raise ValueError(f"V3 baseline is not an exact healthy paired source: {seed}")
    stock_cases_by_chain = {
        case.chain_id: case
        for case in plan.cases
        if case.seed == seed and case.lever_id == "prepositioned_free_stock_14d"
    }
    if len(stock_cases_by_chain) != 4:
        raise ValueError(f"Expected four V5 stock lanes for seed {seed}")
    cutovers = action._baseline_cutover_stock(
        plan=plan,
        v3_root=v3_root,
        baseline_evidence=evidence,
        seed=seed,
        chain_cases=tuple(stock_cases_by_chain.values()),
    )
    run_dir = action._safe_descendant(
        v3_root, evidence.get("run_dir"), "V3 baseline run"
    )
    lot_events_path = action._required_file(
        run_dir / "data" / "production_lot_events.csv", "V3 baseline lot events"
    )
    lot_genealogy_path = action._required_file(
        run_dir / "data" / "production_lot_genealogy.csv",
        "V3 baseline lot genealogy",
    )
    arrivals_path = action._required_file(
        run_dir / "data" / "production_input_replenishment_arrivals_daily.csv",
        "V3 baseline input arrivals",
    )
    arrival_rows = action._read_csv(arrivals_path)
    files = v3_ledger.get("case_files") or {}
    rows: list[dict[str, str]] = []
    for chain, case in sorted(stock_cases_by_chain.items()):
        state = cutovers[chain]
        matching_arrivals = [
            row
            for row in arrival_rows
            if action._to_int(row.get("day"), -1) == 0
            and row.get("node_id") == case.dst_node_id
            and row.get("item_id") == case.item_id
        ]
        if (
            len(matching_arrivals) != 1
            or str(matching_arrivals[0].get("uom") or "") != case.buffer_uom
        ):
            raise ValueError(f"J0 arrival unit is not unique/exact: {chain}/{seed}")
        stock_before = action._to_float(
            state.get("stock_before_production_day0_qty"), math.nan
        )
        arrival = action._to_float(state.get("arrival_day0_qty"), math.nan)
        cutover = action._to_float(
            state.get("cutover_stock_before_day0_flows_qty"), math.nan
        )
        if (
            not all(math.isfinite(value) for value in (stock_before, arrival, cutover))
            or cutover <= action.ZERO_EPS
            or not math.isclose(stock_before - arrival, cutover, abs_tol=1e-6)
        ):
            raise ValueError(f"J0 multiplicative actuator is unavailable: {chain}/{seed}")
        unsigned = {
            "schema_version": action.J0_SNAPSHOT_SCHEMA_VERSION,
            "seed": str(seed),
            "seed_prefix_index": str(plan.seeds.index(seed) + 1),
            "baseline_case_key": baseline_key,
            "baseline_evidence_relative_path": str(files[baseline_key]),
            "baseline_evidence_sha256": evidence_hash,
            "source_runner_signature": str(v3_manifest.get("runner_signature") or ""),
            "chain_id": chain,
            "supplier_id": case.supplier_id,
            "node_id": case.dst_node_id,
            "item_id": case.item_id,
            "uom": case.buffer_uom,
            "stock_before_production_day0_qty": format(stock_before, ".17g"),
            "arrival_day0_qty": format(arrival, ".17g"),
            "cutover_stock_before_day0_flows_qty": format(cutover, ".17g"),
            "reconstruction": "day0_stock_before_production_minus_day0_arrival",
            "summary_sha256": str(state.get("summary_sha256") or ""),
            "stocks_daily_sha256": str(state.get("stocks_daily_sha256") or ""),
            "arrivals_daily_sha256": str(state.get("arrivals_daily_sha256") or ""),
            "lot_events_sha256": action._sha256(lot_events_path),
            "lot_genealogy_sha256": action._sha256(lot_genealogy_path),
            "source_lot_trace_enabled": str(
                evidence.get("resolved_lot_trace_enabled") is True
            ),
            "warmup_core_state_sha256": str(
                state.get("warmup_core_state_sha256") or ""
            ),
            "warmup_component_sha256_json": json.dumps(
                state.get("warmup_component_sha256") or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
        rows.append(_canonical_row(unsigned))
    return rows


def capture_snapshot(
    *,
    plan_dir: Path,
    post_priority_results_dir: Path,
    output_dir: Path,
    expected_seed_count: int,
    base_snapshot_dir: Path | None = None,
    graph: Path = action.protocol.DEFAULT_GRAPH,
    engine: Path = action.protocol.DEFAULT_ENGINE,
    profile: Path = action.protocol.DEFAULT_PROFILE,
) -> dict[str, Any]:
    if expected_seed_count not in {15, 30}:
        raise ValueError("The snapshot must contain exactly the first 15 or all 30 seeds")
    plan = action.load_action_plan(
        plan_dir=plan_dir,
        graph=graph,
        engine=engine,
        profile=profile,
    )
    action._validate_execution_files_unchanged(plan)
    v3_root, v3_manifest, ledger_path, v3_ledger = _load_v3_contract(
        plan, post_priority_results_dir
    )
    target_seeds = plan.seeds[:expected_seed_count]
    inherited_rows: list[dict[str, str]] = []
    inherited_manifest: Mapping[str, Any] = {}
    if base_snapshot_dir is not None:
        inherited_manifest, inherited_rows = _read_snapshot_rows(base_snapshot_dir)
        inherited_seeds = tuple(
            action._to_int(value, -1)
            for value in inherited_manifest.get("captured_seed_ids") or []
        )
        if (
            inherited_manifest.get("V5_protocol_signature")
            != plan.manifest.get("protocol_signature")
            or inherited_manifest.get("V3_plan_signature")
            != plan.post_priority_plan_manifest.get("plan_signature")
            or inherited_manifest.get("source_runner_signature")
            != v3_manifest.get("runner_signature")
            or inherited_manifest.get("signed_final_seed_ids") != list(plan.seeds)
            or inherited_seeds != plan.seeds[: len(inherited_seeds)]
            or len(inherited_seeds) >= expected_seed_count
        ):
            raise ValueError("Base J0 snapshot cannot be extended by this V5 source")
    inherited_by_key = {
        (action._to_int(row.get("seed"), -1), str(row.get("chain_id") or "")): row
        for row in inherited_rows
    }
    v2_rows, _v2_hash = action._index_v2_rows(plan)
    rows = list(inherited_rows)
    for seed in target_seeds:
        expected_keys = {
            (seed, case.chain_id)
            for case in plan.cases
            if case.seed == seed and case.lever_id == "prepositioned_free_stock_14d"
        }
        inherited_keys = expected_keys & set(inherited_by_key)
        if inherited_keys:
            if inherited_keys != expected_keys:
                raise ValueError(f"Base J0 snapshot has a partial seed: {seed}")
            continue
        try:
            rows.extend(
                _capture_seed_rows(
                    plan=plan,
                    v3_root=v3_root,
                    v3_manifest=v3_manifest,
                    v3_ledger=v3_ledger,
                    v2_rows=v2_rows,
                    seed=seed,
                )
            )
        except action.SourcesNotReadyError as exc:
            raise action.SourcesNotReadyError(
                f"V3 baseline seed {seed} is not complete; snapshot not written"
            ) from exc
    rows.sort(key=lambda row: (action._to_int(row["seed"]), row["chain_id"]))
    if (
        len(rows) != expected_seed_count * 4
        or len({(row["seed"], row["chain_id"]) for row in rows}) != len(rows)
    ):
        raise ValueError("J0 snapshot does not contain exactly four lanes per seed")
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite an existing snapshot: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    rows_path = output_dir / action.J0_SNAPSHOT_ROWS
    action._write_csv(rows_path, rows)
    manifest_payload = {
        "schema_version": action.J0_SNAPSHOT_SCHEMA_VERSION,
        "contract_revision": action.CONTRACT_REVISION,
        "status": (
            "complete_30_of_30" if expected_seed_count == 30 else "complete_15_of_30"
        ),
        "V5_protocol_signature": plan.manifest.get("protocol_signature"),
        "V3_plan_signature": plan.post_priority_plan_manifest.get("plan_signature"),
        "V2_campaign_signature": plan.manifest.get("source_campaign_signature"),
        "source_runner_signature": v3_manifest.get("runner_signature"),
        "source_runner_status_at_capture": v3_manifest.get("status"),
        "source_ledger_sha256_at_capture": action._sha256(ledger_path),
        "graph_sha256": action._sha256(plan.graph_path),
        "engine_sha256": action._sha256(plan.engine_path),
        "profile_sha256": action._sha256(plan.profile_path),
        "signed_final_seed_ids": list(plan.seeds),
        "captured_seed_ids": list(target_seeds),
        "seed_count": expected_seed_count,
        "lane_count_per_seed": 4,
        "row_count": len(rows),
        "rows_file": action.J0_SNAPSHOT_ROWS,
        "rows_sha256": action._sha256(rows_path),
        "base_snapshot_signature": inherited_manifest.get("snapshot_signature", ""),
        "source_files_mutated": False,
        "raw_source_files_copied": False,
        "snapshot_contains_quantities_and_source_hashes_only": True,
        "created_at_utc": action._utc_now(),
    }
    manifest = action._signed_payload(manifest_payload, "snapshot_signature")
    action._write_json(output_dir / action.J0_SNAPSHOT_MANIFEST, manifest)
    loaded = action._load_j0_snapshot(
        plan=plan,
        snapshot_dir=output_dir,
        target_seed_ids=target_seeds,
        v3_manifest=v3_manifest,
        v3_ledger=v3_ledger,
    )
    if len(loaded) != len(rows):
        raise ValueError("Written J0 snapshot did not pass exact self-validation")
    return manifest


def validate_snapshot(
    *,
    plan_dir: Path,
    post_priority_results_dir: Path,
    snapshot_dir: Path,
    expected_seed_count: int,
    graph: Path = action.protocol.DEFAULT_GRAPH,
    engine: Path = action.protocol.DEFAULT_ENGINE,
    profile: Path = action.protocol.DEFAULT_PROFILE,
) -> dict[str, Any]:
    plan = action.load_action_plan(
        plan_dir=plan_dir,
        graph=graph,
        engine=engine,
        profile=profile,
    )
    _root, v3_manifest, _ledger_path, v3_ledger = _load_v3_contract(
        plan, post_priority_results_dir
    )
    rows = action._load_j0_snapshot(
        plan=plan,
        snapshot_dir=snapshot_dir,
        target_seed_ids=plan.seeds[:expected_seed_count],
        v3_manifest=v3_manifest,
        v3_ledger=v3_ledger,
    )
    return {
        "status": "valid",
        "seed_count": expected_seed_count,
        "row_count": len(rows),
        "snapshot_dir": str(snapshot_dir.resolve()),
        "source_files_mutated": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("capture", "validate"), default="capture")
    parser.add_argument("--plan-dir", type=Path, default=action.DEFAULT_PROTOCOL_DIR)
    parser.add_argument(
        "--post-priority-results-dir",
        type=Path,
        default=action.DEFAULT_POST_PRIORITY_RESULTS,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--base-snapshot-dir", type=Path)
    parser.add_argument("--expected-seed-count", type=int, choices=(15, 30), default=15)
    parser.add_argument("--wait-for-sources", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--graph", type=Path, default=action.protocol.DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=action.protocol.DEFAULT_ENGINE)
    parser.add_argument("--profile", type=Path, default=action.protocol.DEFAULT_PROFILE)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.poll_seconds < 5.0:
        raise ValueError("--poll-seconds must be at least 5")
    while True:
        try:
            if args.mode == "capture":
                result = capture_snapshot(
                    plan_dir=args.plan_dir,
                    post_priority_results_dir=args.post_priority_results_dir,
                    output_dir=args.output_dir,
                    expected_seed_count=args.expected_seed_count,
                    base_snapshot_dir=args.base_snapshot_dir,
                    graph=args.graph,
                    engine=args.engine,
                    profile=args.profile,
                )
            else:
                result = validate_snapshot(
                    plan_dir=args.plan_dir,
                    post_priority_results_dir=args.post_priority_results_dir,
                    snapshot_dir=args.output_dir,
                    expected_seed_count=args.expected_seed_count,
                    graph=args.graph,
                    engine=args.engine,
                    profile=args.profile,
                )
            break
        except action.SourcesNotReadyError as exc:
            waiting = {
                "status": (
                    "waiting_for_sources"
                    if args.mode == "capture" and args.wait_for_sources
                    else "sources_not_ready"
                ),
                "reason": str(exc),
                "snapshot_written": False,
            }
            print(json.dumps(waiting, ensure_ascii=False), flush=True)
            if args.mode != "capture" or not args.wait_for_sources:
                return 2
            time.sleep(args.poll_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
