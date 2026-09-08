#!/usr/bin/env python3
"""Compare normal, untreated incident and intervention cascade simulations.

The comparator is deliberately post-processing only.  It reads a completed
``canonical_cascade_campaign`` directory and writes to a separate empty output
directory, so neither simulations nor earlier comparisons can be overwritten.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.canonical_cascade_campaign import (  # noqa: E402
    CascadeCampaignError,
    MANIFEST_SCHEMA_VERSION,
    RUN_COLUMNS,
    customer_daily_series,
    production_daily_series,
)


COMPARISON_SCHEMA_VERSION = "scan.canonical_cascade_comparison.v2"
SUMMARY_SCHEMA_VERSION = "scan.canonical_cascade_summary.v2"

COMPARISON_COLUMNS: tuple[str, ...] = (
    "cascade_id",
    "solution_id",
    "variant_id",
    "seed",
    "lever_fidelity",
    "native_levers",
    "approximation_levers",
    "pairing_status",
    "incident_application_verified",
    "incident_signal_detected",
    "customer_exposure_detected",
    "customer_exposure_status",
    "ranking_eligible",
    "ranking_exclusion_reasons",
    "customer_impact_onset_day_no_action",
    "customer_impact_onset_day_solution",
    "terminal_recovery_day_no_action",
    "terminal_recovery_day_solution",
    "recovery_days_no_action",
    "recovery_days_solution",
    "days_recovered_vs_no_action",
    "recovery_status",
    "shortage_days_no_action",
    "shortage_days_solution",
    "shortage_days_avoided",
    "gross_positive_customer_service_gain_qty",
    "net_customer_service_gain_qty",
    "gross_positive_production_gain_qty",
    "net_production_gain_qty",
    "gross_positive_production_lot_starts",
    "net_production_lot_starts",
    "gross_positive_production_lot_equivalent",
    "gross_additional_mrp_release_qty",
    "net_mrp_release_qty",
    "incremental_decision_total_cost_vs_no_action",
    "incremental_controllable_operating_cost_vs_no_action",
    "incremental_decision_transport_cost_vs_no_action",
    "incremental_external_purchase_cost_vs_no_action",
    "incremental_stock_qty_days",
    "no_action_incremental_customer_backlog_qty_days",
    "remaining_incremental_customer_backlog_qty_days",
    "remaining_customer_impact_ratio",
    "remaining_customer_impact_pct",
    "action_execution_status",
    "expected_action_signature_count",
    "verified_action_signature_count",
    "verified_action_row_count",
    "verified_action_evidence_json",
    "evidence_notes",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise CascadeCampaignError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CascadeCampaignError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise CascadeCampaignError(f"{label} must contain a JSON object.")
    return payload


def _load_json_array(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CascadeCampaignError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CascadeCampaignError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise CascadeCampaignError(f"{label} must contain an array of JSON objects.")
    return payload


def _read_csv(
    path: Path, *, required_columns: Sequence[str] = ()
) -> list[dict[str, str]]:
    if not path.is_file():
        raise CascadeCampaignError(f"Campaign CSV does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = sorted(set(required_columns) - set(reader.fieldnames or ()))
        if missing:
            raise CascadeCampaignError(
                f"Required columns missing from {path}: {', '.join(missing)}"
            )
        return [dict(row) for row in reader]


def _number(row: Mapping[str, Any], field: str, *, context: str) -> float:
    raw = row.get(field)
    if raw in {None, ""}:
        raise CascadeCampaignError(f"Missing numeric {field} in {context}.")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise CascadeCampaignError(
            f"Invalid numeric {field}={raw!r} in {context}."
        ) from exc
    if not math.isfinite(value):
        raise CascadeCampaignError(f"Non-finite numeric {field} in {context}.")
    return value


def _empty_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists() and not resolved.is_dir():
        raise CascadeCampaignError(f"Comparison output is not a directory: {resolved}")
    if resolved.exists() and any(resolved.iterdir()):
        raise CascadeCampaignError(
            f"Refusing to overwrite or mix comparison artifacts: {resolved}"
        )
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _incremental_backlog(
    variant: Mapping[int, Mapping[str, float]],
    normal: Mapping[int, Mapping[str, float]],
    *,
    first_day: int,
) -> dict[int, float]:
    if set(variant) != set(normal):
        raise CascadeCampaignError("Paired customer trajectories have different day coverage.")
    days = sorted(variant)
    return {
        day: max(
            0.0,
            float(variant[day]["backlog"])
            - float(normal[day]["backlog"]),
        )
        for day in days
        if day >= first_day
    }


def _impact_and_terminal_recovery(
    incremental: Mapping[int, float],
    *,
    consecutive_days: int,
    tolerance: float,
) -> tuple[int | None, int | None, int | None]:
    if not incremental:
        return None, None, None
    last_day = max(incremental)
    positive_days = sorted(day for day, value in incremental.items() if value > tolerance)
    if not positive_days:
        return None, None, None
    onset = positive_days[0]
    last_positive = positive_days[-1]
    recovery = last_positive + 1
    if recovery + consecutive_days - 1 > last_day:
        return onset, last_positive, None
    if not all(
        incremental[day] <= tolerance
        for day in range(recovery, recovery + consecutive_days)
    ):
        return onset, last_positive, None
    return onset, last_positive, recovery


def _positive_daily_gain(
    solution: Mapping[int, Mapping[str, float]],
    reference: Mapping[int, Mapping[str, float]],
    *,
    field: str,
    first_day: int,
) -> float:
    if set(solution) != set(reference):
        raise CascadeCampaignError("Paired customer trajectories have different day coverage.")
    return sum(
        max(
            0.0,
            float(solution[day][field])
            - float(reference[day][field]),
        )
        for day in solution
        if day >= first_day
    )


def _signed_daily_gain(
    solution: Mapping[int, Mapping[str, float]],
    reference: Mapping[int, Mapping[str, float]],
    *,
    field: str,
    first_day: int,
) -> float:
    if set(solution) != set(reference):
        raise CascadeCampaignError("Paired customer trajectories have different day coverage.")
    return sum(
        float(solution[day][field]) - float(reference[day][field])
        for day in solution
        if day >= first_day
    )


def _positive_scalar_daily_gain(
    solution: Mapping[int, float],
    reference: Mapping[int, float],
    *,
    first_day: int,
) -> float:
    if set(solution) != set(reference):
        raise CascadeCampaignError("Paired production trajectories have different day coverage.")
    return sum(
        max(0.0, solution[day] - reference[day])
        for day in solution
        if day >= first_day
    )


def _signed_scalar_daily_gain(
    solution: Mapping[int, float],
    reference: Mapping[int, float],
    *,
    first_day: int,
) -> float:
    if set(solution) != set(reference):
        raise CascadeCampaignError("Paired production trajectories have different day coverage.")
    return sum(
        solution[day] - reference[day]
        for day in solution
        if day >= first_day
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(COMPARISON_COLUMNS), extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def _solution_lookup(config: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(cascade["id"]), str(solution["id"])): solution
        for cascade in config.get("cascades", [])
        for solution in cascade.get("solutions", [])
    }


def _cascade_lookup(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(cascade["id"]): cascade for cascade in config.get("cascades", [])}


def _mean(rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    """Return a complete-grid mean, never a silent available-case mean."""

    if not rows:
        return None
    values: list[float] = []
    for row in rows:
        raw = row.get(field)
        if raw in {None, ""}:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise CascadeCampaignError(
                f"Invalid aggregate value {field}={raw!r}."
            ) from exc
        if not math.isfinite(value):
            raise CascadeCampaignError(f"Non-finite aggregate value for {field}.")
        values.append(value)
    return sum(values) / len(values)


def _strict_grid_key(row: Mapping[str, Any], *, context: str) -> tuple[str, str, int]:
    cascade_id = str(row.get("cascade_id") or "").strip()
    variant_id = str(row.get("variant_id") or "").strip()
    raw_seed = row.get("seed")
    if not cascade_id or not variant_id or raw_seed in {None, ""}:
        raise CascadeCampaignError(f"Incomplete cascade/variant/seed key in {context}.")
    try:
        seed_number = float(raw_seed)
    except (TypeError, ValueError) as exc:
        raise CascadeCampaignError(f"Invalid seed {raw_seed!r} in {context}.") from exc
    if not math.isfinite(seed_number) or not seed_number.is_integer() or seed_number < 0:
        raise CascadeCampaignError(f"Invalid seed {raw_seed!r} in {context}.")
    return cascade_id, variant_id, int(seed_number)


def _validate_complete_grid(
    *,
    manifest: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
    commands: Sequence[Mapping[str, Any]],
    manifest_path: Path,
    runs_path: Path,
    commands_path: Path,
    snapshot_path: Path,
) -> None:
    """Require the exact completed campaign grid before causal comparison."""

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise CascadeCampaignError(
            f"Campaign manifest schema must be {MANIFEST_SCHEMA_VERSION!r}."
        )
    if manifest.get("status") != "complete":
        raise CascadeCampaignError(
            f"Campaign manifest status must be complete, got {manifest.get('status')!r}."
        )
    if manifest.get("failure_count") != 0 or manifest.get("skipped_fail_fast_count") != 0:
        raise CascadeCampaignError(
            "Complete campaign manifest must report zero failures and zero skipped runs."
        )

    run_keys = [_strict_grid_key(row, context=str(runs_path)) for row in runs]
    command_keys = [
        _strict_grid_key(row, context=str(commands_path)) for row in commands
    ]
    duplicate_runs = sorted(key for key, count in Counter(run_keys).items() if count > 1)
    duplicate_commands = sorted(
        key for key, count in Counter(command_keys).items() if count > 1
    )
    if duplicate_runs or duplicate_commands:
        raise CascadeCampaignError(
            "Campaign grid contains duplicate cascade/variant/seed rows: "
            f"runs={duplicate_runs[:5]}, commands={duplicate_commands[:5]}."
        )
    if set(run_keys) != set(command_keys):
        raise CascadeCampaignError(
            "Campaign run grid differs from the planned command grid: "
            f"missing_runs={sorted(set(command_keys) - set(run_keys))[:5]}, "
            f"unexpected_runs={sorted(set(run_keys) - set(command_keys))[:5]}."
        )

    manifest_seeds = manifest.get("seeds")
    if not isinstance(manifest_seeds, list) or not manifest_seeds:
        raise CascadeCampaignError("Campaign manifest must declare a non-empty seed list.")
    try:
        normalized_manifest_seeds = [int(value) for value in manifest_seeds]
    except (TypeError, ValueError) as exc:
        raise CascadeCampaignError("Campaign manifest contains an invalid seed.") from exc
    if len(normalized_manifest_seeds) != len(set(normalized_manifest_seeds)):
        raise CascadeCampaignError("Campaign manifest contains duplicate seeds.")
    observed_seeds = sorted({seed for _cascade, _variant, seed in command_keys})
    if sorted(normalized_manifest_seeds) != observed_seeds:
        raise CascadeCampaignError(
            "Campaign manifest seeds differ from the complete command grid."
        )

    observed_cascades = sorted({cascade for cascade, _variant, _seed in command_keys})
    if manifest.get("cascade_ids") != observed_cascades:
        raise CascadeCampaignError(
            "Campaign manifest cascade_ids differ from the complete command grid."
        )
    if manifest.get("run_count") != len(run_keys):
        raise CascadeCampaignError(
            "Campaign manifest run_count differs from the physical run grid."
        )

    variants_by_cascade_seed: dict[tuple[str, int], set[str]] = {}
    for cascade_id, variant_id, seed in command_keys:
        variants_by_cascade_seed.setdefault((cascade_id, seed), set()).add(variant_id)
    cascade_variant_pairs: set[tuple[str, str]] = set()
    for cascade_id in observed_cascades:
        reference_variants: set[str] | None = None
        for seed in observed_seeds:
            variants = variants_by_cascade_seed.get((cascade_id, seed))
            if variants is None:
                raise CascadeCampaignError(
                    f"Campaign grid is missing cascade {cascade_id!r} for seed {seed}."
                )
            if reference_variants is None:
                reference_variants = variants
            elif variants != reference_variants:
                raise CascadeCampaignError(
                    f"Campaign variants differ between seeds for cascade {cascade_id!r}."
                )
        assert reference_variants is not None
        if not {"normal", "incident_no_action"}.issubset(reference_variants):
            raise CascadeCampaignError(
                f"Cascade {cascade_id!r} lacks normal or untreated reference variants."
            )
        if not any(value.startswith("incident_") and value != "incident_no_action" for value in reference_variants):
            raise CascadeCampaignError(
                f"Cascade {cascade_id!r} has no intervention variant."
            )
        cascade_variant_pairs.update((cascade_id, value) for value in reference_variants)

    manifest_variants = manifest.get("variant_ids")
    if not isinstance(manifest_variants, list):
        raise CascadeCampaignError("Campaign manifest variant_ids must be a list.")
    expected_variant_multiset = Counter(
        variant_id for _cascade_id, variant_id in cascade_variant_pairs
    )
    if Counter(str(value) for value in manifest_variants) != expected_variant_multiset:
        raise CascadeCampaignError(
            "Campaign manifest variant_ids differ from the complete command grid."
        )

    output_hashes = manifest.get("output_sha256")
    config_metadata = manifest.get("config")
    if not isinstance(output_hashes, Mapping) or not isinstance(config_metadata, Mapping):
        raise CascadeCampaignError("Campaign manifest is missing artifact hashes.")
    expected_hashes = {
        "runs": _sha256(runs_path),
        "commands": _sha256(commands_path),
        "config_snapshot": _sha256(snapshot_path),
    }
    mismatched = {
        name: {"expected": digest, "manifest": output_hashes.get(name)}
        for name, digest in expected_hashes.items()
        if output_hashes.get(name) != digest
    }
    if config_metadata.get("sha256") != expected_hashes["config_snapshot"]:
        mismatched["config.sha256"] = {
            "expected": expected_hashes["config_snapshot"],
            "manifest": config_metadata.get("sha256"),
        }
    if mismatched:
        raise CascadeCampaignError(
            f"Campaign manifest artifact hashes do not match: {mismatched}."
        )


def compare_campaign(
    *,
    campaign_dir: Path,
    output_dir: Path,
) -> Path:
    """Compare all successful intervention rows against paired references."""

    campaign_root = campaign_dir.resolve()
    manifest_path = campaign_root / "canonical_cascade_manifest.json"
    runs_path = campaign_root / "canonical_cascade_runs.csv"
    commands_path = campaign_root / "canonical_cascade_commands.json"
    snapshot_path = campaign_root / "canonical_cascade_config_snapshot.json"
    manifest = _load_json(manifest_path, label="Cascade campaign manifest")
    config = _load_json(snapshot_path, label="Cascade config snapshot")
    runs = _read_csv(runs_path, required_columns=RUN_COLUMNS)
    commands = _load_json_array(commands_path, label="Cascade campaign commands")
    _validate_complete_grid(
        manifest=manifest,
        runs=runs,
        commands=commands,
        manifest_path=manifest_path,
        runs_path=runs_path,
        commands_path=commands_path,
        snapshot_path=snapshot_path,
    )
    invalid = [row for row in runs if row.get("status") != "ok"]
    if invalid:
        statuses = sorted({str(row.get("status") or "") for row in invalid})
        raise CascadeCampaignError(
            "Comparison requires successful physical runs; found statuses: "
            + ", ".join(statuses)
        )
    output_root = _empty_output_dir(output_dir)
    campaign_config = config.get("campaign")
    if not isinstance(campaign_config, Mapping):
        raise CascadeCampaignError("Cascade config snapshot has no campaign object.")
    expected_days = int(campaign_config.get("days") or 0)
    if expected_days <= 0:
        raise CascadeCampaignError("Cascade config snapshot has invalid campaign.days.")
    guards = config.get("scientific_guards", {})
    if not isinstance(guards, Mapping):
        raise CascadeCampaignError("Cascade config snapshot has invalid scientific_guards.")
    require_positive_customer_exposure = guards.get(
        "require_positive_incremental_customer_backlog", True
    )
    if not isinstance(require_positive_customer_exposure, bool):
        raise CascadeCampaignError(
            "scientific_guards.require_positive_incremental_customer_backlog "
            "must be boolean."
        )
    cascades = _cascade_lookup(config)
    solutions = _solution_lookup(config)
    by_key = {
        (str(row["cascade_id"]), str(row["variant_id"]), int(row["seed"])): row
        for row in runs
    }
    comparison_rows: list[dict[str, Any]] = []
    for run in runs:
        if run.get("case_type") != "incident_with_solution":
            continue
        cascade_id = str(run["cascade_id"])
        solution_id = str(run["solution_id"])
        seed = int(run["seed"])
        cascade = cascades.get(cascade_id)
        solution = solutions.get((cascade_id, solution_id))
        normal = by_key.get((cascade_id, "normal", seed))
        untreated = by_key.get((cascade_id, "incident_no_action", seed))
        if cascade is None or solution is None or normal is None or untreated is None:
            raise CascadeCampaignError(
                f"Missing comparison reference for {cascade_id}/{solution_id}/seed {seed}."
            )
        start_hashes = {
            str(normal.get("measurement_start_state_sha256") or ""),
            str(untreated.get("measurement_start_state_sha256") or ""),
            str(run.get("measurement_start_state_sha256") or ""),
        }
        component_hashes = {
            str(normal.get("measurement_start_component_sha256_json") or ""),
            str(untreated.get("measurement_start_component_sha256_json") or ""),
            str(run.get("measurement_start_component_sha256_json") or ""),
        }
        if (
            len(start_hashes) != 1
            or "" in start_hashes
            or len(component_hashes) != 1
            or "" in component_hashes
        ):
            raise CascadeCampaignError(
                f"Measurement-start state mismatch for {cascade_id}/{solution_id}/seed {seed}; "
                "causal gains are not computed."
            )
        normal_dir = Path(str(normal["result_dir"]))
        untreated_dir = Path(str(untreated["result_dir"]))
        solution_dir = Path(str(run["result_dir"]))
        customer_id = str(cascade["customer_id"])
        item_id = str(cascade["finished_item_id"])
        normal_service = customer_daily_series(
            normal_dir,
            customer_id=customer_id,
            item_id=item_id,
            expected_days=expected_days,
        )
        untreated_service = customer_daily_series(
            untreated_dir,
            customer_id=customer_id,
            item_id=item_id,
            expected_days=expected_days,
        )
        solution_service = customer_daily_series(
            solution_dir,
            customer_id=customer_id,
            item_id=item_id,
            expected_days=expected_days,
        )
        incident_start = int(cascade["incident"]["start_day"])
        tolerance = float(cascade.get("backlog_tolerance_qty", 1e-6))
        consecutive = int(cascade.get("recovery_consecutive_days", 7))
        untreated_incremental = _incremental_backlog(
            untreated_service, normal_service, first_day=incident_start
        )
        solution_incremental = _incremental_backlog(
            solution_service, normal_service, first_day=incident_start
        )
        untreated_area = sum(untreated_incremental.values())
        solution_area = sum(solution_incremental.values())
        incident_signal = untreated_area > tolerance
        configured_event_ids = {
            str(event["event_id"])
            for event in cascade["incident"].get("risk_events", [])
        }
        applied_event_ids = {
            value
            for value in str(
                untreated.get("supplier_risk_applied_event_ids") or ""
            ).split(";")
            if value
        }
        untreated_risk_rows = int(
            round(
                _number(
                    untreated,
                    "supplier_risk_applied_row_count",
                    context=(
                        f"{cascade_id}/incident_no_action/seed {seed}"
                    ),
                )
            )
        )
        incident_application_verified = (
            untreated_risk_rows > 0
            and configured_event_ids.issubset(applied_event_ids)
        )
        if not incident_application_verified:
            raise CascadeCampaignError(
                f"Untreated incident is not physically verified for {cascade_id}/seed {seed}: "
                f"configured={sorted(configured_event_ids)}, "
                f"applied={sorted(applied_event_ids)}, rows={untreated_risk_rows}."
            )
        if not incident_signal and require_positive_customer_exposure:
            raise CascadeCampaignError(
                f"Untreated incident created no positive incremental customer-backlog "
                f"area for {cascade_id}/seed {seed} while the strict positive-exposure "
                "guard is enabled."
            )
        expected_incident_status = (
            "physically_applied_with_customer_exposure"
            if incident_signal
            else "physically_applied_no_customer_exposure"
        )
        if str(untreated.get("incident_validation_status") or "") != expected_incident_status:
            raise CascadeCampaignError(
                f"Untreated incident validation status is inconsistent for "
                f"{cascade_id}/seed {seed}: expected {expected_incident_status!r}, got "
                f"{untreated.get('incident_validation_status')!r}."
            )

        untreated_onset, _untreated_last_positive, untreated_recovery = (
            _impact_and_terminal_recovery(
                untreated_incremental,
                consecutive_days=consecutive,
                tolerance=tolerance,
            )
        )
        solution_onset, _solution_last_positive, solution_recovery = (
            _impact_and_terminal_recovery(
                solution_incremental,
                consecutive_days=consecutive,
                tolerance=tolerance,
            )
        )
        untreated_recovery_days: int | str = (
            ""
            if untreated_recovery is None or untreated_onset is None
            else untreated_recovery - untreated_onset
        )
        solution_recovery_days: int | str = (
            0
            if solution_onset is None
            else ""
            if solution_recovery is None
            else solution_recovery - solution_onset
        )
        if not incident_signal:
            untreated_recovery_days = ""
            solution_recovery_days = ""
            recovery_status = "untreated_incident_absorbed_before_customer"
            days_recovered = ""
        elif solution_onset is None:
            if untreated_recovery is None:
                recovery_status = "solution_prevented_impact_untreated_censored"
                days_recovered: int | str = ""
            else:
                recovery_status = "solution_prevented_impact"
                days_recovered = int(untreated_recovery_days)
        elif untreated_recovery is None and solution_recovery is None:
            recovery_status = "neither_terminal_recovery_observed"
            days_recovered = ""
        elif untreated_recovery is None:
            recovery_status = "solution_recovered_untreated_censored"
            days_recovered = ""
        elif solution_recovery is None:
            recovery_status = "solution_terminal_recovery_not_observed"
            days_recovered = ""
        else:
            recovery_status = "paired_terminal_recovery_observed"
            days_recovered = untreated_recovery - solution_recovery
        shortage_untreated = sum(
            1 for value in untreated_incremental.values() if value > tolerance
        )
        shortage_solution = sum(
            1 for value in solution_incremental.values() if value > tolerance
        )
        gross_customer_gain = _positive_daily_gain(
            solution_service,
            untreated_service,
            field="served",
            first_day=incident_start,
        )
        net_customer_gain = _signed_daily_gain(
            solution_service,
            untreated_service,
            field="served",
            first_day=incident_start,
        )
        production_target = cascade["production_target"]
        untreated_production = production_daily_series(
            untreated_dir,
            node_id=str(production_target["node_id"]),
            item_id=str(production_target["item_id"]),
            expected_days=expected_days,
        )
        solution_production = production_daily_series(
            solution_dir,
            node_id=str(production_target["node_id"]),
            item_id=str(production_target["item_id"]),
            expected_days=expected_days,
        )
        gross_production_gain = _positive_scalar_daily_gain(
            solution_production,
            untreated_production,
            first_day=incident_start,
        )
        net_production_gain = _signed_scalar_daily_gain(
            solution_production,
            untreated_production,
            first_day=incident_start,
        )
        reference_lot_qty = float(cascade["reference_lot_qty"])
        gross_lot_equivalent = (
            gross_production_gain / reference_lot_qty
            if reference_lot_qty > 0
            else 0.0
        )
        context = f"{cascade_id}/{solution_id}/seed {seed}"
        net_lot_starts = (
            _number(run, "production_lot_count", context=context)
            - _number(untreated, "production_lot_count", context=context)
        )
        gross_lot_starts = max(0.0, net_lot_starts)
        net_order_qty = (
            _number(run, "target_order_qty", context=context)
            - _number(untreated, "target_order_qty", context=context)
        )
        gross_order_qty = max(0.0, net_order_qty)
        ratio: float | str = (
            solution_area / untreated_area if untreated_area > tolerance else ""
        )
        action_status = str(run.get("action_execution_status") or "")
        expected_action_count = int(
            round(_number(run, "expected_action_signature_count", context=context))
        )
        verified_action_count = int(
            round(_number(run, "verified_action_signature_count", context=context))
        )
        verified_action_rows = int(
            round(_number(run, "verified_action_row_count", context=context))
        )
        configured_ranking_eligible = bool(solution.get("ranking_eligible", True))
        ranking_reasons: list[str] = []
        if not configured_ranking_eligible:
            ranking_reasons.append(
                str(
                    solution.get("ranking_exclusion_reason")
                    or solution.get("ranking_reason")
                    or "configured as a non-ranking diagnostic variant"
                )
            )
        if action_status != "fully_verified":
            ranking_reasons.append(
                "every configured action signature was not verified with positive physical volume"
            )
        if not incident_signal:
            ranking_reasons.append(
                "untreated incident was physically applied but caused no customer exposure; "
                "customer-recovery metrics are not applicable for this seed"
            )
        if incident_signal and untreated_recovery is None:
            ranking_reasons.append(
                "untreated customer recovery is censored by the simulation horizon"
            )
        if solution_onset is not None and solution_recovery is None:
            ranking_reasons.append(
                "solution customer recovery is censored by the simulation horizon"
            )
        recovery_complete = incident_signal and untreated_recovery is not None and (
            solution_onset is None or solution_recovery is not None
        )
        ranking_eligible = (
            configured_ranking_eligible
            and action_status == "fully_verified"
            and recovery_complete
        )
        notes = [
            str(solution.get("approximation_notes") or "").strip(),
            (
                "gross_positive_production_lot_equivalent is gross positive production "
                "gain divided by the "
                "configured reference lot size; it is an explicit approximation"
            ),
            (
                "gross_additional_mrp_release_qty is additional modeled MRP release quantity, "
                "not a count of individual customer orders"
            ),
            (
                "gross gains sum only positive daily differences; net gains retain both "
                "improvements and losses"
            ),
        ]
        if action_status != "fully_verified":
            notes.append(
                "the intervention is retained for diagnosis but excluded from solution ranking"
            )
        if not incident_signal:
            notes.append(
                "the incident was physically applied and absorbed before the customer; "
                "customer-service and cost values remain unconditional observations, while "
                "days recovered and the remaining-impact ratio are not applicable"
            )
        comparison_rows.append(
            {
                "cascade_id": cascade_id,
                "solution_id": solution_id,
                "variant_id": str(run["variant_id"]),
                "seed": seed,
                "lever_fidelity": str(solution["lever_fidelity"]),
                "native_levers": ";".join(
                    str(value) for value in solution.get("native_levers", [])
                ),
                "approximation_levers": ";".join(
                    str(value) for value in solution.get("approximation_levers", [])
                ),
                "pairing_status": "measurement_start_state_matched",
                "incident_application_verified": incident_application_verified,
                "incident_signal_detected": incident_signal,
                "customer_exposure_detected": incident_signal,
                "customer_exposure_status": (
                    "customer_exposed"
                    if incident_signal
                    else "absorbed_before_customer"
                ),
                "ranking_eligible": ranking_eligible,
                "ranking_exclusion_reasons": " | ".join(
                    reason for reason in ranking_reasons if reason
                ),
                "customer_impact_onset_day_no_action": untreated_onset,
                "customer_impact_onset_day_solution": (
                    "" if solution_onset is None else solution_onset
                ),
                "terminal_recovery_day_no_action": (
                    "" if untreated_recovery is None else untreated_recovery
                ),
                "terminal_recovery_day_solution": (
                    "" if solution_recovery is None else solution_recovery
                ),
                "recovery_days_no_action": untreated_recovery_days,
                "recovery_days_solution": solution_recovery_days,
                "days_recovered_vs_no_action": days_recovered,
                "recovery_status": recovery_status,
                "shortage_days_no_action": shortage_untreated,
                "shortage_days_solution": shortage_solution,
                "shortage_days_avoided": shortage_untreated - shortage_solution,
                "gross_positive_customer_service_gain_qty": gross_customer_gain,
                "net_customer_service_gain_qty": net_customer_gain,
                "gross_positive_production_gain_qty": gross_production_gain,
                "net_production_gain_qty": net_production_gain,
                "gross_positive_production_lot_starts": gross_lot_starts,
                "net_production_lot_starts": net_lot_starts,
                "gross_positive_production_lot_equivalent": gross_lot_equivalent,
                "gross_additional_mrp_release_qty": gross_order_qty,
                "net_mrp_release_qty": net_order_qty,
                "incremental_decision_total_cost_vs_no_action": _number(
                    run, "decision_total_cost", context=context
                )
                - _number(untreated, "decision_total_cost", context=context),
                "incremental_controllable_operating_cost_vs_no_action": _number(
                    run, "controllable_operating_cost", context=context
                )
                - _number(untreated, "controllable_operating_cost", context=context),
                "incremental_decision_transport_cost_vs_no_action": _number(
                    run, "decision_transport_cost", context=context
                )
                - _number(untreated, "decision_transport_cost", context=context),
                "incremental_external_purchase_cost_vs_no_action": _number(
                    run, "external_purchase_cost", context=context
                )
                - _number(untreated, "external_purchase_cost", context=context),
                "incremental_stock_qty_days": _number(
                    run, "target_stock_qty_days", context=context
                )
                - _number(untreated, "target_stock_qty_days", context=context),
                "no_action_incremental_customer_backlog_qty_days": untreated_area,
                "remaining_incremental_customer_backlog_qty_days": solution_area,
                "remaining_customer_impact_ratio": ratio,
                "remaining_customer_impact_pct": (
                    "" if ratio == "" else 100.0 * float(ratio)
                ),
                "action_execution_status": action_status,
                "expected_action_signature_count": expected_action_count,
                "verified_action_signature_count": verified_action_count,
                "verified_action_row_count": verified_action_rows,
                "verified_action_evidence_json": str(
                    run.get("verified_action_evidence_json") or ""
                ),
                "evidence_notes": " | ".join(note for note in notes if note),
            }
        )
    if not comparison_rows:
        raise CascadeCampaignError("No successful incident_with_solution rows were found.")
    comparison_rows.sort(
        key=lambda row: (str(row["cascade_id"]), str(row["solution_id"]), int(row["seed"]))
    )
    comparison_path = output_root / "canonical_cascade_comparison.csv"
    _write_csv(comparison_path, comparison_rows)
    # Keep the three files consumed by the additive HTML/demo layer together.
    # This is a byte-for-byte copy: the campaign directory remains the source
    # of truth and is never modified by comparison generation.
    runs_copy_path = output_root / "canonical_cascade_runs.csv"
    shutil.copy2(runs_path, runs_copy_path)
    aggregates: list[dict[str, Any]] = []
    keys = sorted(
        {(str(row["cascade_id"]), str(row["solution_id"])) for row in comparison_rows}
    )
    for cascade_id, solution_id in keys:
        group = [
            row
            for row in comparison_rows
            if row["cascade_id"] == cascade_id and row["solution_id"] == solution_id
        ]
        exposed_group = [
            row for row in group if row["customer_exposure_detected"] is True
        ]
        exposure_count = len(exposed_group)
        all_exposed_seeds_rankable = bool(exposed_group) and all(
            row["ranking_eligible"] is True for row in exposed_group
        )
        worst_untreated_customer_impact = max(
            float(row["no_action_incremental_customer_backlog_qty_days"])
            for row in group
        )
        worst_remaining_customer_impact = max(
            float(row["remaining_incremental_customer_backlog_qty_days"])
            for row in group
        )
        aggregates.append(
            {
                "cascade_id": cascade_id,
                "solution_id": solution_id,
                "seed_count": len(group),
                "customer_exposure_seed_count": exposure_count,
                "no_customer_exposure_seed_count": len(group) - exposure_count,
                "customer_exposure_frequency": exposure_count / len(group),
                "lever_fidelity": group[0]["lever_fidelity"],
                "ranking_eligible_for_all_seeds": all(
                    row["ranking_eligible"] is True for row in group
                ),
                "ranking_eligible_for_all_exposed_seeds": (
                    all_exposed_seeds_rankable
                ),
                "action_execution_fully_verified_for_all_seeds": all(
                    row["action_execution_status"] == "fully_verified"
                    for row in group
                ),
                "mean_days_recovered_vs_no_action": _mean(
                    exposed_group, "days_recovered_vs_no_action"
                ),
                "mean_shortage_days_avoided": _mean(group, "shortage_days_avoided"),
                "mean_gross_positive_customer_service_gain_qty": _mean(
                    group, "gross_positive_customer_service_gain_qty"
                ),
                "mean_net_customer_service_gain_qty": _mean(
                    group, "net_customer_service_gain_qty"
                ),
                "mean_gross_positive_production_gain_qty": _mean(
                    group, "gross_positive_production_gain_qty"
                ),
                "mean_net_production_gain_qty": _mean(
                    group, "net_production_gain_qty"
                ),
                "mean_gross_positive_production_lot_starts": _mean(
                    group, "gross_positive_production_lot_starts"
                ),
                "mean_net_production_lot_starts": _mean(
                    group, "net_production_lot_starts"
                ),
                "mean_incremental_decision_total_cost_vs_no_action": _mean(
                    group, "incremental_decision_total_cost_vs_no_action"
                ),
                "mean_incremental_stock_qty_days": _mean(
                    group, "incremental_stock_qty_days"
                ),
                "mean_remaining_customer_impact_ratio": _mean(
                    exposed_group, "remaining_customer_impact_ratio"
                ),
                "mean_no_action_incremental_customer_backlog_qty_days_unconditional": _mean(
                    group, "no_action_incremental_customer_backlog_qty_days"
                ),
                "worst_no_action_incremental_customer_backlog_qty_days": (
                    worst_untreated_customer_impact
                ),
                "mean_remaining_incremental_customer_backlog_qty_days_unconditional": _mean(
                    group, "remaining_incremental_customer_backlog_qty_days"
                ),
                "worst_remaining_incremental_customer_backlog_qty_days": (
                    worst_remaining_customer_impact
                ),
            }
        )
    best_by_cascade: dict[str, str] = {}
    for cascade_id in sorted({row["cascade_id"] for row in aggregates}):
        candidates = [
            row
            for row in aggregates
            if row["cascade_id"] == cascade_id
            and row["ranking_eligible_for_all_exposed_seeds"] is True
            and row["action_execution_fully_verified_for_all_seeds"] is True
        ]
        if not candidates:
            best_by_cascade[str(cascade_id)] = ""
            continue
        candidates.sort(
            key=lambda row: (
                float("inf")
                if row["mean_remaining_customer_impact_ratio"] is None
                else float(row["mean_remaining_customer_impact_ratio"]),
                -(
                    float(row["mean_days_recovered_vs_no_action"])
                    if row["mean_days_recovered_vs_no_action"] is not None
                    else -float("inf")
                ),
                float(
                    row["mean_incremental_decision_total_cost_vs_no_action"]
                    or 0.0
                ),
                str(row["solution_id"]),
            )
        )
        best_by_cascade[str(cascade_id)] = str(candidates[0]["solution_id"])
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "path": str(campaign_root),
            "manifest": str(manifest_path),
            "manifest_sha256": _sha256(manifest_path),
            "runs": str(runs_path),
            "runs_sha256": _sha256(runs_path),
            "status": manifest.get("status"),
        },
        "definitions": {
            "days_recovered_vs_no_action": (
                "untreated terminal-recovery calendar day minus solution terminal-recovery "
                "calendar day. Recovery starts only after the last positive incremental "
                "customer backlog and requires the configured complete zero-impact tail"
            ),
            "gross_positive_customer_service_gain_qty": (
                "sum of positive daily served-quantity differences versus untreated incident"
            ),
            "net_customer_service_gain_qty": (
                "signed sum of daily served-quantity differences versus untreated incident"
            ),
            "gross_positive_production_gain_qty": (
                "sum of positive daily production differences versus untreated incident"
            ),
            "net_production_gain_qty": (
                "signed sum of daily production differences versus untreated incident"
            ),
            "gross_positive_production_lot_starts": (
                "positive part of the difference in engine-recorded actual_lot_starts"
            ),
            "gross_positive_production_lot_equivalent": (
                "gross positive production gain divided by configured reference lot size; approximation"
            ),
            "gross_additional_mrp_release_qty": (
                "positive difference in modeled MRP release quantity; not individual customer orders"
            ),
            "remaining_customer_impact_ratio": (
                "solution incremental customer-backlog area divided by untreated "
                "incremental customer-backlog area, each relative to paired normal; "
                "defined only for seeds where the untreated incident reaches the customer"
            ),
            "customer_exposure_frequency": (
                "share of paired seeds where the physically applied untreated incident "
                "creates positive incremental customer-backlog area"
            ),
            "mean_no_action_incremental_customer_backlog_qty_days_unconditional": (
                "mean untreated incremental customer-backlog area across every paired seed, "
                "including zero when upstream and downstream buffers absorb the incident"
            ),
            "worst_no_action_incremental_customer_backlog_qty_days": (
                "largest untreated incremental customer-backlog area observed across all "
                "paired seeds"
            ),
            "decision_total_cost": (
                "base operational supply cost plus external procurement and opening-order "
                "purchase/transport costs; opening transport is not added twice to the base"
            ),
            "controllable_operating_cost": (
                "base operational supply cost plus external procurement purchase and transport"
            ),
            "incremental_stock_qty_days": (
                "solution minus untreated sum of configured cascade stock selectors"
            ),
        },
        "lever_catalog": [
            {
                "cascade_id": cascade_id,
                "solution_id": solution_id,
                "lever_fidelity": solutions[(cascade_id, solution_id)].get("lever_fidelity"),
                "native_levers": solutions[(cascade_id, solution_id)].get("native_levers", []),
                "approximation_levers": solutions[(cascade_id, solution_id)].get(
                    "approximation_levers", []
                ),
                "approximation_notes": solutions[(cascade_id, solution_id)].get(
                    "approximation_notes", ""
                ),
                "ranking_eligible": solutions[(cascade_id, solution_id)].get(
                    "ranking_eligible", True
                ),
                "ranking_exclusion_reason": solutions[(cascade_id, solution_id)].get(
                    "ranking_exclusion_reason",
                    solutions[(cascade_id, solution_id)].get("ranking_reason", ""),
                ),
            }
            for cascade_id, solution_id in keys
        ],
        "aggregates": aggregates,
        "best_solution_by_remaining_customer_impact_then_recovery_and_cost": best_by_cascade,
        "comparison_row_count": len(comparison_rows),
        "outputs": {
            "runs_csv": str(runs_copy_path),
            "runs_csv_sha256": _sha256(runs_copy_path),
            "comparison_csv": str(comparison_path),
            "comparison_csv_sha256": _sha256(comparison_path),
        },
    }
    summary_path = output_root / "canonical_cascade_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = compare_campaign(
            campaign_dir=args.campaign_dir, output_dir=args.output_dir
        )
    except CascadeCampaignError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(f"[OK] Cascade comparison summary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMPARISON_COLUMNS",
    "COMPARISON_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "compare_campaign",
]
