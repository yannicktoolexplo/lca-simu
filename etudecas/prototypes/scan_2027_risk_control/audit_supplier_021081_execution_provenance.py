#!/usr/bin/env python3
"""Audit case-level provenance for a completed additive 021081 campaign.

The audit is deliberately conservative.  If the orchestrator hash at process
start was not recorded, it never calls the artifact reproducible even when the
engine, graph, profile, normalized engine command and retained case inputs can
all be verified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_active_flow_campaign as campaign,
)


def _last_engine_command(path: Path) -> list[str]:
    if not path.exists():
        return []
    command: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = " COMMAND "
        if marker not in line:
            continue
        payload = line.split(marker, 1)[1]
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            command = value
    return command


def _option_path(command: Sequence[str], option: str) -> Path | None:
    try:
        index = list(command).index(option)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return Path(command[index + 1])


def _hash_if_present(path: Path | None) -> str:
    return campaign.sha256_file(path) if path is not None and path.exists() else ""


def _metric_rows(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in (
        "screening_metrics.csv",
        "confirmation_metrics.csv",
        "unit_sensitivity_metrics.csv",
        "baseline_calibration_metrics.csv",
    ):
        path = root / name
        for row in campaign.read_csv_rows(path):
            row["_provenance_metric_file"] = name
            rows.append(row)
    by_key: dict[tuple[str, str, int], dict[str, str]] = {}
    for row in rows:
        key = (
            str(row.get("state_regime") or ""),
            str(row.get("scenario_id") or ""),
            campaign.to_int(row.get("seed")),
        )
        by_key[key] = row
    return [by_key[key] for key in sorted(by_key)]


def _variant_graph_path(root: Path, metric: Mapping[str, Any]) -> Path | None:
    unit_variant = str(metric.get("unit_variant") or "")
    absolute_state = str(metric.get("absolute_state_id") or "")
    if unit_variant and absolute_state:
        return root / "inputs" / f"graph_{unit_variant}__{absolute_state}.json"
    state = str(metric.get("state_regime") or "")
    candidate = root / "inputs" / f"graph_{state}.json"
    return candidate if candidate.exists() else None


def _expected_case_count(manifest: Mapping[str, Any]) -> int:
    direct = campaign.to_int(manifest.get("case_count"), -1)
    if direct >= 0:
        return direct
    screening = campaign.to_int(manifest.get("screening_case_count"), -1)
    confirmation = campaign.to_int(manifest.get("confirmation_case_count"), -1)
    if screening >= 0 and confirmation >= 0:
        return screening + confirmation
    return -1


def audit_campaign(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = root.resolve()
    manifest_path = root / "campaign_manifest.json"
    manifest = campaign.read_json(manifest_path)
    status = str(manifest.get("status") or "")
    if status not in {"complete", "smoke_complete"}:
        raise RuntimeError(
            f"Refusing provenance audit while campaign status is {status!r}"
        )

    engine = Path(str(manifest.get("engine") or ""))
    graph = Path(str(manifest.get("source_graph") or ""))
    profile = Path(str(manifest.get("profile") or ""))
    expected_engine = str(manifest.get("engine_sha256") or "")
    expected_graph = str(manifest.get("source_graph_sha256") or "")
    expected_profile = str(manifest.get("profile_sha256") or "")
    current_engine = _hash_if_present(engine)
    current_graph = _hash_if_present(graph)
    current_profile = _hash_if_present(profile)
    launch_orchestrator_sha = str(
        manifest.get("orchestrator_sha256_at_process_start") or ""
    )
    orchestrator_path = Path(str(manifest.get("orchestrator") or ""))
    current_orchestrator_sha = _hash_if_present(orchestrator_path)
    orchestrator_known = bool(launch_orchestrator_sha)
    orchestrator_matches_launch = bool(
        launch_orchestrator_sha
        and current_orchestrator_sha
        and launch_orchestrator_sha == current_orchestrator_sha
    )
    state_graph_audits = campaign.read_json(
        root / "production_layer_overlay_audit.json"
    ) if (root / "production_layer_overlay_audit.json").is_file() else {}

    rows: list[dict[str, Any]] = []
    for metric in _metric_rows(root):
        regime = str(metric.get("state_regime") or "")
        state_graph_audit = (
            state_graph_audits.get(regime) or {}
            if isinstance(state_graph_audits, Mapping)
            else {}
        )
        scenario_id = str(metric.get("scenario_id") or "")
        seed = campaign.to_int(metric.get("seed"))
        case_dir = root / "cases" / regime / scenario_id / f"seed_{seed}"
        command = _last_engine_command(case_dir / "campaign_engine.log")
        normalized = campaign.normalized_engine_command(command) if command else []
        graph_overlay = case_dir / "campaign_inputs" / "graph_overlay.json"
        risk_path = _option_path(command, "--supplier-risk-events-csv")
        stock_scale_path = _option_path(
            command, "--measurement-start-stock-scale-csv"
        )
        ledger_path = (
            case_dir / "campaign_inputs" / "observed_order_overlay_ledger.csv"
        )
        overlay_audit_path = case_dir / "campaign_inputs" / "overlay_audit.json"
        command_engine_path = Path(command[1]) if len(command) >= 2 else None
        command_engine_sha = _hash_if_present(command_engine_path)
        source_metric_sha = str(metric.get("source_graph_sha256") or "")
        original_source_metric_sha = str(
            metric.get("source_graph_original_sha256")
            or state_graph_audit.get("source_graph_sha256")
            or source_metric_sha
        )
        variant_metric_sha = str(
            metric.get("variant_graph_sha256")
            or metric.get("state_graph_sha256")
            or state_graph_audit.get("state_graph_sha256")
            or source_metric_sha
        )
        variant_path = _variant_graph_path(root, metric)
        variant_rehashed_sha = _hash_if_present(variant_path)
        variant_required = bool(
            metric.get("variant_graph_sha256")
            or metric.get("state_graph_sha256")
            or state_graph_audit.get("state_graph_sha256")
            or (variant_path is not None and source_metric_sha != expected_graph)
        )
        original_source_matches = bool(
            expected_graph
            and expected_graph == current_graph == original_source_metric_sha
        )
        variant_source_matches = bool(
            variant_metric_sha
            and (
                variant_metric_sha == variant_rehashed_sha
                if variant_required
                else variant_metric_sha == expected_graph
            )
        )
        overlay_metric_sha = str(metric.get("overlay_graph_sha256") or "")
        overlay_rehashed_sha = _hash_if_present(graph_overlay)
        overlay_retained = graph_overlay.exists()
        overlay_matches = bool(
            overlay_metric_sha
            and overlay_rehashed_sha
            and overlay_metric_sha == overlay_rehashed_sha
        )
        ledger_metric_sha = str(metric.get("observed_order_ledger_sha256") or "")
        ledger_rehashed_sha = _hash_if_present(ledger_path)
        ledger_matches = bool(
            ledger_metric_sha
            and ledger_rehashed_sha
            and ledger_metric_sha == ledger_rehashed_sha
        )
        overlay_audit_metric_sha = str(metric.get("overlay_audit_sha256") or "")
        overlay_audit_rehashed_sha = _hash_if_present(overlay_audit_path)
        overlay_audit_matches = bool(
            overlay_audit_metric_sha
            and overlay_audit_rehashed_sha
            and overlay_audit_metric_sha == overlay_audit_rehashed_sha
        )
        stock_scale_metric_sha = str(
            metric.get("measurement_start_stock_scale_csv_sha256") or ""
        )
        stock_scale_rehashed_sha = _hash_if_present(stock_scale_path)
        stock_scale_matches = (
            bool(
                stock_scale_metric_sha
                and stock_scale_rehashed_sha
                and stock_scale_metric_sha == stock_scale_rehashed_sha
            )
            if stock_scale_metric_sha
            else stock_scale_path is None
        )
        risk_metric_sha = str(metric.get("dynamic_risk_csv_sha256") or "")
        risk_rehashed_sha = _hash_if_present(risk_path)
        risk_matches = bool(
            risk_metric_sha
            and risk_rehashed_sha
            and risk_metric_sha == risk_rehashed_sha
        ) if risk_metric_sha else risk_path is None
        # Summary retention deliberately removes the per-case engine graph after
        # recording its hash.  In that mode the exact replay recipe remains
        # auditable through the retained source variant, order ledger, overlay
        # audit and measurement-start state file.  Do not claim that the removed
        # graph was rehashed; distinguish traceability from byte re-verification.
        overlay_replay_recipe_matches = bool(
            not overlay_retained
            and overlay_metric_sha
            and ledger_matches
            and overlay_audit_matches
        )
        overlay_input_traceable = overlay_matches or overlay_replay_recipe_matches
        core_inputs_match = bool(
            command
            and expected_engine
            and expected_engine == current_engine == command_engine_sha
            and original_source_matches
            and variant_source_matches
            and overlay_input_traceable
            and stock_scale_matches
            and risk_matches
            and expected_profile
            and expected_profile == current_profile
        )
        reproducibility_allowed = bool(
            orchestrator_matches_launch and core_inputs_match and normalized
        )
        rows.append(
            {
                "case_key": f"{regime}/{scenario_id}/seed_{seed}",
                "stage": str(metric.get("stage") or ""),
                "state_regime": regime,
                "scenario_id": scenario_id,
                "seed": seed,
                "orchestrator_sha256_at_process_start": launch_orchestrator_sha,
                "orchestrator_sha256_current_audit_time": current_orchestrator_sha,
                "orchestrator_at_launch_known": orchestrator_known,
                "orchestrator_matches_launch": orchestrator_matches_launch,
                "orchestrator_path": str(orchestrator_path),
                "engine_sha256_manifest": expected_engine,
                "engine_sha256_command_path_at_audit": command_engine_sha,
                "engine_sha256_current": current_engine,
                "source_graph_sha256_manifest": expected_graph,
                "source_graph_sha256_metric": source_metric_sha,
                "source_graph_original_sha256_metric": original_source_metric_sha,
                "source_graph_sha256_current": current_graph,
                "variant_graph_path": str(variant_path or ""),
                "variant_graph_sha256_metric": variant_metric_sha,
                "variant_graph_sha256_rehashed": variant_rehashed_sha,
                "variant_source_matches": variant_source_matches,
                "profile_sha256_manifest": expected_profile,
                "profile_sha256_current": current_profile,
                "engine_command_present": bool(command),
                "engine_command_normalized_sha256": (
                    campaign.json_sha256(normalized) if normalized else ""
                ),
                "engine_command_normalized_json": (
                    json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
                    if normalized
                    else ""
                ),
                "overlay_graph_sha256_recorded_before_summary_pruning": str(
                    metric.get("overlay_graph_sha256") or ""
                ),
                "overlay_graph_sha256_rehashed": overlay_rehashed_sha,
                "overlay_graph_matches": overlay_matches,
                "overlay_graph_retained": overlay_retained,
                "overlay_replay_recipe_matches": overlay_replay_recipe_matches,
                "overlay_input_traceable": overlay_input_traceable,
                "overlay_verification_status": (
                    "retained_and_rehashed"
                    if overlay_matches
                    else "pruned_after_hash_recipe_reverified"
                    if overlay_replay_recipe_matches
                    else "missing_or_mismatched"
                ),
                "risk_csv_sha256_metric": risk_metric_sha,
                "risk_csv_sha256_rehashed": risk_rehashed_sha,
                "risk_csv_matches": risk_matches,
                "observed_order_ledger_sha256_metric": ledger_metric_sha,
                "observed_order_ledger_sha256_rehashed": ledger_rehashed_sha,
                "observed_order_ledger_matches": ledger_matches,
                "overlay_audit_sha256_metric": overlay_audit_metric_sha,
                "overlay_audit_sha256_rehashed": overlay_audit_rehashed_sha,
                "overlay_audit_matches": overlay_audit_matches,
                "measurement_start_stock_scale_csv_sha256_metric": (
                    stock_scale_metric_sha
                ),
                "measurement_start_stock_scale_csv_sha256_rehashed": (
                    stock_scale_rehashed_sha
                ),
                "measurement_start_stock_scale_csv_matches": stock_scale_matches,
                "core_engine_graph_profile_match_manifest": core_inputs_match,
                "metric_file": str(metric.get("_provenance_metric_file") or ""),
                "reproducibility_wording_allowed": reproducibility_allowed,
                "provenance_status": (
                    "audited_reproducible_inputs_and_orchestrator"
                    if reproducibility_allowed
                    else "core_inputs_audited_orchestrator_at_launch_unknown"
                    if not orchestrator_known and core_inputs_match
                    else "incomplete_or_mismatched_execution_provenance"
                ),
            }
        )

    summary = {
        "schema_version": "supplier-021081-execution-provenance-audit.v1",
        "campaign_root": str(root),
        "campaign_status": status,
        "case_count": len(rows),
        "expected_case_count_from_manifest": _expected_case_count(manifest),
        "case_count_matches_manifest": (
            _expected_case_count(manifest) < 0
            or len(rows) == _expected_case_count(manifest)
        ),
        "orchestrator_sha256_at_process_start": launch_orchestrator_sha,
        "orchestrator_sha256_current_audit_time": current_orchestrator_sha,
        "orchestrator_at_launch_known": orchestrator_known,
        "orchestrator_matches_launch": orchestrator_matches_launch,
        "orchestrator_path": str(orchestrator_path),
        "engine_graph_profile_match_manifest_for_every_case": bool(rows)
        and all(
            bool(row["core_engine_graph_profile_match_manifest"])
            for row in rows
        ),
        "reproducibility_wording_allowed": bool(rows)
        and (
            _expected_case_count(manifest) < 0
            or len(rows) == _expected_case_count(manifest)
        )
        and all(bool(row["reproducibility_wording_allowed"]) for row in rows),
        "interpretation": (
            "Engine, source/variant graph, profile, normalized command and retained "
            "replay-recipe hashes are audited per case. A summary-pruned engine "
            "overlay is identified explicitly and is not described as rehashed. "
            "If the launch orchestrator hash is absent, the "
            "artifact must not be labelled reproducible and must not be merged into "
            "a homogeneous case CSV with a later orchestrator version."
        ),
    }
    return rows, summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.campaign_root).resolve()
    rows, summary = audit_campaign(root)
    campaign.write_csv(root / "execution_provenance_audit.csv", rows)
    campaign.write_json(root / "execution_provenance_audit.json", summary)
    manifest_path = root / "campaign_manifest.json"
    manifest = campaign.read_json(manifest_path)
    manifest["execution_provenance_audit"] = {
        **summary,
        "csv": "execution_provenance_audit.csv",
        "json": "execution_provenance_audit.json",
    }
    campaign.write_json(manifest_path, manifest)
    print(
        f"[OK] audited {len(rows)} cases; reproducibility wording allowed="
        f"{summary['reproducibility_wording_allowed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
