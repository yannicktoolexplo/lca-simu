#!/usr/bin/env python3
"""Run the six RESILIENCE-SCAN validation work packages targeted for end 2026."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.calibration import calibrate_from_context
from etudecas.prototypes.scan_2027_risk_control.canonical_replay import (
    CANONICAL_KPI_NAMES,
    discover_canonical_graph,
    load_canonical_engine_profile,
    prepare_canonical_overlay_package,
    run_canonical_replays,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    DEFAULT_ACTIONS,
    build_input_context,
    first_existing_column,
    load_config,
    safety_filter,
)
from etudecas.prototypes.scan_2027_risk_control.decision import (
    adaptive_summary,
    regime_transition_matrix,
    run_adaptive_controller,
    simulate_fixed_policy_scenarios,
)
from etudecas.prototypes.scan_2027_risk_control.end_2026_reporting import (
    DEFAULT_STABLE_NOMINAL_DAYS,
    derive_regime_recovery_episodes,
    save_end_2026_plots,
    summarize_regime_recovery,
    write_end_2026_report,
)
from etudecas.prototypes.scan_2027_risk_control.experiments import (
    forecast_confusion_experiment,
    forecast_confusion_sensitivity_experiment,
    paired_policy_experiment,
)
from etudecas.prototypes.scan_2027_risk_control.model import (
    derive_adaptive_state_space,
    derive_constraint_activity,
    estimate_supplier_impedance,
)
from etudecas.prototypes.scan_2027_risk_control.rci_validation import (
    bind_completed_business_review,
    build_blinded_rci_review,
    build_rci_business_validation_pack,
    rci_review_variable_dictionary,
    summarize_completed_business_review,
    write_business_validation_guide,
)
from etudecas.prototypes.scan_2027_risk_control.reporting import save_plots, write_json, write_report
from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_canonical_risk_events,
    build_granular_prediction_interval_envelope,
    build_prediction_interval_envelope,
    combine_portfolio_and_granular_envelopes,
    load_canonical_lane_activity,
    map_prediction_interval_to_physical,
    physical_mapping_coefficient_sensitivity,
    select_top_prediction_pairs,
)


def _float_grid(value: str) -> tuple[float, ...]:
    try:
        result = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected a comma-separated list of numbers"
        ) from exc
    if not result:
        raise argparse.ArgumentTypeError("the sensitivity grid cannot be empty")
    if any(not math.isfinite(item) for item in result):
        raise argparse.ArgumentTypeError(
            "the sensitivity grid must contain finite numbers"
        )
    return result


def _int_grid(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected a comma-separated list of integers"
        ) from exc
    if not result or any(item <= 0 for item in result):
        raise argparse.ArgumentTypeError(
            "the duration grid must contain positive integers"
        )
    return result


def _probability_grid(value: str) -> tuple[float, ...]:
    result = _float_grid(value)
    if any(item <= 0.0 or item >= 1.0 for item in result):
        raise argparse.ArgumentTypeError(
            "alert thresholds must be strictly between 0 and 1"
        )
    return result


def _half_width_grid(value: str) -> tuple[float, ...]:
    result = _float_grid(value)
    if any(item < 0.0 or item >= 0.5 for item in result):
        raise argparse.ArgumentTypeError(
            "interval half-widths must be within [0, 0.5)"
        )
    return result


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Run regime calibration, prediction-to-physics mapping, paired comparisons, forecast-error tests and RCI review pack."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--baseline-csv", default="auto")
    parser.add_argument("--risk-csv", default="auto")
    parser.add_argument("--config", default=str(here / "config" / "default_config.json"))
    parser.add_argument("--output-dir", default=str(here / "outputs" / "end_2026_validation"))
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--seed", type=int, default=20260)
    parser.add_argument("--paired-seed-count", type=int, default=12)
    parser.add_argument("--confusion-seed-count", type=int, default=6)
    parser.add_argument("--confusion-duration-days", type=int, default=42)
    parser.add_argument(
        "--confusion-alert-response-policy",
        default="balanced_robust",
        help=(
            "Bounded policy applied only while a forecast alert is active in "
            "TP/FP/FN/TN experiments."
        ),
    )
    parser.add_argument(
        "--confusion-alert-thresholds",
        type=_probability_grid,
        default=(0.40, 0.70),
        help="Comma-separated alert thresholds for the FP/FN sensitivity grid.",
    )
    parser.add_argument(
        "--confusion-interval-half-widths",
        type=_half_width_grid,
        default=(0.05, 0.18),
        help="Comma-separated forecast interval half-widths for sensitivity.",
    )
    parser.add_argument(
        "--confusion-sensitivity-durations",
        type=_int_grid,
        default=(14, 42),
        help=(
            "Comma-separated bounded-response durations in days; physical "
            "incident and forecast-signal durations remain fixed."
        ),
    )
    parser.add_argument(
        "--confusion-sensitivity-seed-count",
        type=int,
        default=1,
        help="Seeds used by the full-factorial sensitivity grid; 0 disables it.",
    )
    parser.add_argument("--controller-scenarios", type=int, default=12)
    parser.add_argument("--policy-comparison-scenarios", type=int, default=24)
    parser.add_argument("--controller-horizon-days", type=int, default=21)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--canonical-replay", choices=["off", "overlay", "run"], default="overlay")
    parser.add_argument("--canonical-graph", default="auto")
    parser.add_argument(
        "--canonical-engine-profile",
        default="",
        help=(
            "Optional JSON profile of additional canonical-engine arguments. "
            "Run identity, randomness, controls and risk-event flags cannot be "
            "overridden."
        ),
    )
    parser.add_argument("--canonical-days", type=int, default=365)
    parser.add_argument("--canonical-seed-count", type=int, default=3)
    parser.add_argument("--canonical-top-risk-pairs", type=int, default=3)
    parser.add_argument(
        "--mapping-sensitivity-factors",
        default="0.8,1.0,1.2",
        help=(
            "Comma-separated positive multipliers for one-at-a-time "
            "prediction-to-physics coefficient sensitivity."
        ),
    )
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--business-review-csv", default="")
    parser.add_argument(
        "--regime-annotations-csv",
        default="",
        help=(
            "Optional expert regime annotations with day/period, site, "
            "item/article, validated_regime, expert_confidence and comment."
        ),
    )
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def _jsonable_record(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records")) if not frame.empty else []


def _file_sha256(path: Path | None) -> str | None:
    """Return a byte-level source fingerprint, or ``None`` when unavailable."""

    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _git_snapshot_metadata(repo_root: Path) -> dict[str, Any]:
    def run_git(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()

    head = run_git("rev-parse", "HEAD")
    branch = run_git("branch", "--show-current")
    status = run_git("status", "--porcelain", "--untracked-files=all")
    return {
        "available": head is not None,
        "head": head,
        "branch": branch or None,
        "dirty": bool(status) if status is not None else None,
    }


def _code_snapshot_metadata(repo_root: Path) -> dict[str, Any]:
    """Hash all Python sources executed by the SCAN/canonical campaign."""

    package_root = (
        repo_root / "etudecas" / "prototypes" / "scan_2027_risk_control"
    )
    engine_root = repo_root / "etudecas" / "simulation" / "engine"
    candidates = [
        *(
            package_root.rglob("*.py")
            if package_root.exists()
            else ()
        ),
        *(
            engine_root.rglob("*.py")
            if engine_root.exists()
            else ()
        ),
        repo_root / "etudecas" / "run_etudecas_pipeline.py",
        (
            repo_root
            / "etudecas"
            / "visualization"
            / "maps"
            / "sensitivity_payload.py"
        ),
    ]
    files = sorted(
        {
            path
            for path in candidates
            if path.is_file()
            and "__pycache__" not in path.parts
            and "outputs" not in path.parts
        },
        key=lambda path: path.relative_to(repo_root).as_posix(),
    )
    digest = hashlib.sha256()
    hashed_files = 0
    for path in files:
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        relative = path.relative_to(repo_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        hashed_files += 1
    return {
        "sha256": digest.hexdigest() if hashed_files else None,
        "scope": "scan_package_canonical_engine_and_execution_adapters",
        "scope_patterns": [
            "etudecas/prototypes/scan_2027_risk_control/**/*.py",
            "etudecas/simulation/engine/**/*.py",
            "etudecas/run_etudecas_pipeline.py",
            "etudecas/visualization/maps/sensitivity_payload.py",
        ],
        "file_count": hashed_files,
        "git": _git_snapshot_metadata(repo_root),
    }


def _forecast_provenance(
    prediction_path: Path | None,
    calibration_path: Path | None,
) -> dict[str, Any]:
    """Detect the prediction PoC's synthetic lineage from sibling evidence."""

    manifest_path = (
        prediction_path.parent / "manifest.json" if prediction_path else None
    )
    report_path = (
        prediction_path.parent / "prediction_poc_report.md"
        if prediction_path
        else None
    )
    sibling_manifest: dict[str, Any] = {}
    if manifest_path is not None and manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            sibling_manifest = loaded if isinstance(loaded, dict) else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            sibling_manifest = {}
    report_text = ""
    if report_path is not None and report_path.exists():
        try:
            report_text = report_path.read_text(encoding="utf-8").casefold()
        except (OSError, UnicodeDecodeError):
            report_text = ""
    report_lines = report_text.splitlines()
    history_reference = str(sibling_manifest.get("data_history") or "")
    history_synthetic = "synth" in history_reference.casefold() or any(
        "histor" in line and "synth" in line for line in report_lines
    )
    labels_synthetic = any(
        "label" in line and "synth" in line for line in report_lines
    )
    temporal_features_synthetic = any(
        ("temporel" in line or "temporal" in line) and "synth" in line
        for line in report_lines
    )
    synthetic_prediction_poc = bool(
        history_synthetic or labels_synthetic or temporal_features_synthetic
    )
    return {
        "origin": (
            "synthetic_prediction_poc"
            if synthetic_prediction_poc
            else "undetermined_prediction_output"
        ),
        "industrial_status": (
            "non_industrial" if synthetic_prediction_poc else "not_established"
        ),
        "history_origin": "synthetic" if history_synthetic else "not_established",
        "label_origin": "synthetic" if labels_synthetic else "not_established",
        "temporal_feature_origin": (
            "partly_synthetic"
            if temporal_features_synthetic
            else "not_established"
        ),
        "evaluation_status": (
            "retrospective_synthetic_non_deployment"
            if synthetic_prediction_poc
            else "retrospective_non_deployment"
        ),
        "source_path": str(prediction_path) if prediction_path else None,
        "source_sha256": _file_sha256(prediction_path),
        "calibration_path": str(calibration_path) if calibration_path else None,
        "calibration_sha256": _file_sha256(calibration_path),
        "detection": {
            "manifest_path": (
                str(manifest_path)
                if manifest_path is not None and manifest_path.exists()
                else None
            ),
            "report_path": (
                str(report_path)
                if report_path is not None and report_path.exists()
                else None
            ),
            "manifest_history_reference": history_reference or None,
            "history_synthetic_detected": history_synthetic,
            "labels_synthetic_detected": labels_synthetic,
            "temporal_features_synthetic_detected": (
                temporal_features_synthetic
            ),
        },
    }


def _build_run_provenance(
    repo_root: Path,
    context: Any,
    prediction_metadata: dict[str, Any],
) -> dict[str, Any]:
    baseline_path = Path(context.baseline_path) if context.baseline_path else None
    prediction_path = Path(context.risk_path) if context.risk_path else None
    calibration_value = prediction_metadata.get("calibration_path")
    calibration_path = Path(calibration_value) if calibration_value else None
    baseline_origin = (
        "etudecas_case_simulation_output"
        if str(context.source_mode) == "etudecas_baseline"
        else "synthetic_fallback"
    )
    forecast = _forecast_provenance(prediction_path, calibration_path)
    if (
        str(context.source_mode) == "synthetic_fallback"
        and prediction_path is None
        and bool(prediction_metadata.get("fallback_used"))
    ):
        forecast.update({
            "origin": "synthetic_risk_series_fallback",
            "industrial_status": "non_industrial",
            "history_origin": "synthetic_generator",
            "label_origin": "not_applicable_no_prediction_labels",
            "temporal_feature_origin": "synthetic_generator",
            "evaluation_status": "synthetic_experiment_non_deployment",
        })
        forecast.setdefault("detection", {})[
            "synthetic_fallback_context"
        ] = True
    return {
        "schema_version": "scan.evidence_provenance.v1",
        "baseline_origin": baseline_origin,
        "forecast_origin": forecast["origin"],
        "baseline": {
            "origin": baseline_origin,
            "industrial_status": "non_industrial",
            "source_path": str(baseline_path) if baseline_path else None,
            "source_sha256": _file_sha256(baseline_path),
        },
        "forecast": forecast,
        "code_snapshot": _code_snapshot_metadata(repo_root),
    }


def _refresh_prediction_mapping(
    context: Any,
    config: dict[str, Any],
    days: int,
) -> tuple[Any, pd.DataFrame, pd.DataFrame]:
    prediction_path = Path(context.risk_path) if context.risk_path else None
    interval, metadata = build_prediction_interval_envelope(
        prediction_path,
        days,
        fallback_center=context.input_series["base_risk"].to_numpy(dtype=float),
        fallback_uncertainty=context.input_series["risk_uncertainty"].to_numpy(dtype=float),
        mapping_config=config.get("physical_risk_mapping", {}),
    )
    physical = map_prediction_interval_to_physical(interval, config.get("physical_risk_mapping", {}))
    granular_interval = build_granular_prediction_interval_envelope(
        prediction_path,
        days,
        fallback_uncertainty=context.input_series["risk_uncertainty"].to_numpy(
            dtype=float
        ),
        mapping_config=config.get("physical_risk_mapping", {}),
    )
    granular_physical = map_prediction_interval_to_physical(
        granular_interval,
        config.get("physical_risk_mapping", {}),
    ) if not granular_interval.empty else pd.DataFrame()
    input_series = context.input_series.head(days).copy().reset_index(drop=True)
    input_series["base_risk"] = interval["risk_center"].to_numpy(dtype=float)
    input_series["risk_uncertainty"] = (
        interval["risk_upper"].to_numpy(dtype=float) - interval["risk_lower"].to_numpy(dtype=float)
    ) / 2.0
    refreshed = replace(
        context,
        input_series=input_series,
        prediction_interval=interval,
        physical_risk_envelope=physical,
        prediction_interval_metadata=metadata.__dict__,
    )
    return refreshed, granular_interval, granular_physical


def _parse_sensitivity_factors(raw: str) -> tuple[float, ...]:
    try:
        factors = tuple(float(value.strip()) for value in raw.split(",") if value.strip())
    except ValueError as exc:
        raise ValueError(
            "--mapping-sensitivity-factors must be comma-separated numbers."
        ) from exc
    if not factors or any(
        not math.isfinite(value) or value <= 0.0 for value in factors
    ):
        raise ValueError(
            "--mapping-sensitivity-factors must contain positive finite values."
        )
    return factors


def _write_frames(data_dir: Path, frames: dict[str, pd.DataFrame]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(data_dir / name, index=False)


def _canonical_execution_metadata(
    runs: pd.DataFrame,
    *,
    expected_runs: int,
    expected_policies: Sequence[str] | None = None,
    expected_seeds: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Summarize physical replays without counting the derived oracle as a run."""

    if runs.empty:
        physical = pd.DataFrame()
        derived_count = 0
    else:
        if "is_derived" in runs:
            derived_mask = (
                pd.to_numeric(runs["is_derived"], errors="coerce")
                .fillna(0)
                .astype(int)
                .eq(1)
            )
        elif "run_kind" in runs:
            derived_mask = runs["run_kind"].astype(str).eq("derived_oracle")
        else:
            derived_mask = pd.Series(False, index=runs.index)
        physical = runs.loc[~derived_mask].copy()
        derived_count = int(derived_mask.sum())

    recorded = int(len(physical))
    identity_validation = (
        expected_policies is not None or expected_seeds is not None
    )
    if (expected_policies is None) != (expected_seeds is None):
        raise ValueError(
            "expected_policies and expected_seeds must be provided together."
        )

    missing_identities: list[dict[str, Any]] = []
    unexpected_identities: list[dict[str, Any]] = []
    duplicate_identities: list[dict[str, Any]] = []
    if identity_validation:
        expected_identities = {
            (str(policy), int(seed))
            for policy in expected_policies or ()
            for seed in expected_seeds or ()
        }
        if len(expected_identities) != int(expected_runs):
            raise ValueError(
                "expected_runs must equal the number of unique expected "
                "policy-by-seed identities."
            )
        identity_rows: dict[tuple[str, int | None], list[pd.Series]] = {}
        for _, row in physical.iterrows():
            seed_value = pd.to_numeric(
                pd.Series([row.get("seed")]),
                errors="coerce",
            ).iloc[0]
            identity = (
                str(row.get("policy") or ""),
                int(seed_value) if pd.notna(seed_value) else None,
            )
            identity_rows.setdefault(identity, []).append(row)

        successful = 0
        for policy, seed in sorted(expected_identities):
            rows_for_identity = identity_rows.get((policy, seed), [])
            if not rows_for_identity:
                missing_identities.append(
                    {"policy": policy, "seed": int(seed)}
                )
                continue
            if len(rows_for_identity) > 1:
                duplicate_identities.append(
                    {
                        "policy": policy,
                        "seed": int(seed),
                        "row_count": len(rows_for_identity),
                    }
                )
                continue
            if str(rows_for_identity[0].get("status") or "") == "ok":
                successful += 1

        for (policy, seed), identity_group in sorted(
            identity_rows.items(),
            key=lambda item: (
                item[0][0],
                -1 if item[0][1] is None else item[0][1],
            ),
        ):
            if seed is None or (policy, seed) not in expected_identities:
                unexpected_identities.append(
                    {
                        "policy": policy,
                        "seed": seed,
                        "row_count": len(identity_group),
                    }
                )
        missing = len(missing_identities)
        unexpected = sum(
            max(0, int(item["row_count"]) - 1)
            for item in duplicate_identities
        ) + sum(
            int(item["row_count"]) for item in unexpected_identities
        )
    else:
        successful = (
            int(physical["status"].astype(str).eq("ok").sum())
            if not physical.empty and "status" in physical
            else 0
        )
        missing = max(0, int(expected_runs) - recorded)
        unexpected = max(0, recorded - int(expected_runs))

    failed = max(0, int(expected_runs) - successful) + unexpected
    if expected_runs > 0 and successful == expected_runs and recorded == expected_runs:
        status = "executed"
    elif successful == 0:
        status = "execution_failed"
    else:
        status = "partial_failure"

    errors: list[dict[str, Any]] = []
    if not physical.empty and "status" in physical:
        for _, row in physical.loc[
            ~physical["status"].astype(str).eq("ok")
        ].iterrows():
            errors.append(
                {
                    "policy": str(row.get("policy") or ""),
                    "seed": (
                        int(row["seed"])
                        if pd.notna(row.get("seed"))
                        else None
                    ),
                    "status": str(row.get("status") or "failed"),
                    "returncode": (
                        int(row["returncode"])
                        if pd.notna(row.get("returncode"))
                        else None
                    ),
                    "error": str(row.get("error") or ""),
                    "result_dir": str(row.get("result_dir") or ""),
                }
            )
    if missing:
        errors.append(
            {
                "status": (
                    "missing_replay_identities"
                    if identity_validation
                    else "missing_replay_rows"
                ),
                "missing_runs": missing,
                "identities": missing_identities,
                "error": (
                    f"Expected {expected_runs} physical policy×seed runs but "
                    f"recorded {recorded}."
                ),
            }
        )
    if unexpected:
        errors.append(
            {
                "status": (
                    "unexpected_or_duplicate_replay_identities"
                    if identity_validation
                    else "unexpected_replay_rows"
                ),
                "unexpected_runs": unexpected,
                "unexpected_identities": unexpected_identities,
                "duplicate_identities": duplicate_identities,
                "error": (
                    f"Expected {expected_runs} physical policy×seed runs but "
                    f"recorded {recorded}."
                ),
            }
        )
    return {
        "status": status,
        "expected_runs": int(expected_runs),
        "physical_runs_recorded": recorded,
        "successful_runs": successful,
        "failed_runs": failed,
        "missing_runs": missing,
        "unexpected_runs": unexpected,
        "missing_identities": missing_identities,
        "unexpected_identities": unexpected_identities,
        "duplicate_identities": duplicate_identities,
        "derived_oracle_rows": derived_count,
        "errors": errors,
    }


def _canonical_risk_artifact_metadata(output_root: Path) -> dict[str, int]:
    """Summarize only the risk events produced by the current replay."""

    risk_path = output_root / "canonical_supplier_risk_events.csv"
    if not risk_path.exists() or risk_path.stat().st_size <= 0:
        return {"risk_event_count": 0, "risk_pairs": 0}
    try:
        events = pd.read_csv(risk_path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError):
        return {"risk_event_count": 0, "risk_pairs": 0}
    pair_columns = ["supplier_id", "item_id", "dst_node_id"]
    risk_pairs = (
        int(events[pair_columns].drop_duplicates().shape[0])
        if not events.empty and all(name in events for name in pair_columns)
        else 0
    )
    return {
        "risk_event_count": int(len(events)),
        "risk_pairs": risk_pairs,
    }


def _clear_legacy_overlay_artifacts_for_daily_replay(
    output_root: Path,
) -> None:
    """Remove exact legacy artifacts that can contradict a reused run folder."""

    output_root.mkdir(parents=True, exist_ok=True)
    legacy_adaptive = output_root / "adaptive_weighted_replay"
    if legacy_adaptive.is_dir():
        shutil.rmtree(legacy_adaptive)
    elif legacy_adaptive.exists():
        legacy_adaptive.unlink()
    for name in (
        "canonical_control_overlays.csv",
        "canonical_supplier_risk_events.csv",
        "canonical_risk_mapping_ledger.csv",
        "canonical_risk_lane_selection.csv",
        "canonical_baseline_lane_activity.csv",
        "canonical_prediction_active_lanes.csv",
    ):
        stale = output_root / name
        if stale.exists():
            stale.unlink()


def _materialize_selected_prediction_lanes(
    prediction_path: Path | None,
    selected_pairs: pd.DataFrame,
    output_path: Path,
) -> Path | None:
    """Write only preselected lanes while retaining the predictor's raw schema."""

    if (
        prediction_path is None
        or not prediction_path.exists()
        or prediction_path.stat().st_size <= 0
    ):
        return prediction_path
    try:
        source = pd.read_csv(prediction_path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError):
        return prediction_path
    supplier_column = first_existing_column(
        source, ["supplier_id", "supplier", "src_node_id"]
    )
    item_column = first_existing_column(
        source, ["item_id", "material_id", "component_id"]
    )
    destination_column = first_existing_column(
        source,
        ["factory_id", "dst_node_id", "destination_node_id", "site_id"],
    )
    if not all((supplier_column, item_column, destination_column)):
        return prediction_path
    selected_keys = {
        (
            str(row["supplier_id"]),
            str(row["item_id"]),
            str(row["dst_node_id"]),
        )
        for _, row in selected_pairs.iterrows()
    }
    source_keys = zip(
        source[str(supplier_column)]
        .astype("string")
        .fillna("")
        .str.strip()
        .astype(str),
        source[str(item_column)]
        .astype("string")
        .fillna("")
        .str.strip()
        .astype(str),
        source[str(destination_column)]
        .astype("string")
        .fillna("")
        .str.strip()
        .astype(str),
    )
    filtered = source.loc[
        [key in selected_keys for key in source_keys]
    ].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output_path, index=False)
    return output_path


def _prepare_canonical_activity_selection(
    *,
    graph_path: Path,
    baseline_path: Path | None,
    prediction_path: Path | None,
    physical_risk_envelope: pd.DataFrame,
    output_root: Path,
    days: int,
    risk_top_pairs: int,
    prediction_horizon_days: int,
) -> tuple[
    Path | None,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    """Freeze graph-compatible active lanes before the canonical subprocesses."""

    horizon = min(
        max(0, int(days)),
        max(1, int(prediction_horizon_days)),
    )
    canonical_graph = json.loads(graph_path.read_text(encoding="utf-8"))
    activity, activity_metadata = load_canonical_lane_activity(
        baseline_path,
        horizon_days=horizon,
    )
    selected_pairs = select_top_prediction_pairs(
        prediction_path,
        top_pairs=int(risk_top_pairs),
        canonical_graph=canonical_graph,
        canonical_activity=activity,
        canonical_activity_metadata=activity_metadata,
        canonical_horizon_days=horizon,
    )
    selection_audit = pd.DataFrame(
        selected_pairs.attrs.get("selection_audit", [])
    )
    selection_export = pd.concat(
        [selected_pairs, selection_audit],
        ignore_index=True,
        sort=False,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    selection_export.to_csv(
        output_root / "canonical_risk_lane_selection.csv",
        index=False,
    )
    if activity is not None:
        activity.to_csv(
            output_root / "canonical_baseline_lane_activity.csv",
            index=False,
        )
        replay_prediction_path = _materialize_selected_prediction_lanes(
            prediction_path,
            selected_pairs,
            output_root / "canonical_prediction_active_lanes.csv",
        )
    else:
        replay_prediction_path = prediction_path

    expected_events, expected_ledger = build_canonical_risk_events(
        prediction_path,
        physical_risk_envelope,
        days=int(days),
        top_pairs=int(risk_top_pairs),
        prediction_horizon_days=int(prediction_horizon_days),
        conservative=True,
        canonical_graph=canonical_graph,
        canonical_activity=activity,
        canonical_activity_metadata=activity_metadata,
    )
    selection_metadata = {
        **activity_metadata,
        "activity_filter_applied": activity is not None,
        "requested_pair_count": int(risk_top_pairs),
        "selected_pair_count": int(len(selected_pairs)),
        "rejected_pair_count": int(len(selection_audit)),
        "selected_pairs": [
            {
                "supplier_id": str(row["supplier_id"]),
                "item_id": str(row["item_id"]),
                "dst_node_id": str(row["dst_node_id"]),
                "canonical_activity_qty": (
                    float(row["canonical_activity_qty"])
                    if pd.notna(row["canonical_activity_qty"])
                    else None
                ),
                "canonical_activity_row_count": int(
                    row["canonical_activity_row_count"]
                ),
                "selection_status": str(row["selection_status"]),
            }
            for _, row in selected_pairs.iterrows()
        ],
        "selection_artifact": str(
            output_root / "canonical_risk_lane_selection.csv"
        ),
        "activity_artifact": (
            str(output_root / "canonical_baseline_lane_activity.csv")
            if activity is not None
            else ""
        ),
        "replay_prediction_path": (
            str(replay_prediction_path) if replay_prediction_path else ""
        ),
        "fallback_statement": (
            ""
            if activity is not None
            else (
                "No usable canonical flow evidence was supplied; selected "
                "lanes are graph-compatible but activity-unverified."
            )
        ),
    }
    return (
        replay_prediction_path,
        expected_events,
        expected_ledger,
        selection_metadata,
    )


def _reconcile_canonical_activity_selection(
    *,
    output_root: Path,
    expected_events: pd.DataFrame,
    expected_ledger: pd.DataFrame,
) -> None:
    """Prove replay inputs match the frozen active-lane selection exactly."""

    event_path = output_root / "canonical_supplier_risk_events.csv"
    if expected_events.empty:
        if event_path.exists():
            try:
                actual_events = pd.read_csv(event_path)
            except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
                raise RuntimeError(
                    f"Canonical risk-event artifact is unreadable: {exc}"
                ) from exc
            if not actual_events.empty:
                raise RuntimeError(
                    "Canonical replay rebuilt risk events although the frozen "
                    "active-lane selection was empty."
                )
    else:
        if not event_path.exists() or event_path.stat().st_size <= 0:
            raise RuntimeError(
                "Canonical replay did not materialize the frozen active-lane "
                "risk events."
            )
        actual_events = pd.read_csv(event_path)
        try:
            pd.testing.assert_frame_equal(
                actual_events.reset_index(drop=True),
                expected_events.reset_index(drop=True),
                check_dtype=False,
                check_like=False,
            )
        except AssertionError as exc:
            raise RuntimeError(
                "Canonical replay reconstructed different risk lanes/events "
                "than the frozen activity-aware selection."
            ) from exc
    ledger_path = output_root / "canonical_risk_mapping_ledger.csv"
    if expected_ledger.empty:
        if ledger_path.exists():
            ledger_path.unlink()
    else:
        expected_ledger.to_csv(ledger_path, index=False)


def _run_canonical_stage(
    *,
    mode: str,
    repo_root: Path,
    graph_path: Path | None,
    decisions: pd.DataFrame,
    actions: Sequence[Any],
    output_root: Path,
    days: int,
    scenario_id: str,
    seed: int,
    seed_count: int,
    prediction_path: Path | None,
    physical_risk_envelope: pd.DataFrame,
    risk_top_pairs: int,
    engine_extra_args: Sequence[str],
    engine_profile: dict[str, Any],
    baseline_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run exactly one canonical integration mode and describe its artifacts."""

    if mode not in {"off", "overlay", "run"}:
        raise ValueError(f"Unsupported canonical replay mode: {mode}")

    requested_integration_mode = {
        "off": "off",
        "overlay": "legacy_fixed_overlay_prepared",
        "run": "daily_open_loop_schedule",
    }[mode]
    expected_runs = (
        (len(actions) + 1) * max(1, int(seed_count))
        if mode == "run"
        else 0
    )
    metadata: dict[str, Any] = {
        "mode": mode,
        "graph_path": str(graph_path) if graph_path else None,
        "status": "disabled" if mode == "off" else "graph_not_found",
        "requested_integration_mode": requested_integration_mode,
        "integration_mode": "off" if mode == "off" else "not_executed",
        "closed_loop_claimed": False,
        "risk_creation_proxy": {
            "column": "canonical_risk_creation_proxy",
            "legacy_alias": "risk_creation_index",
            "scope": "canonical_multi_product_engine_replay",
            "definition_version": (
                "scan.canonical_weighted_six_component_rci.v1"
            ),
            "business_validation": (
                "not_covered_by_reduced_model_business_review"
            ),
        },
        "engine_profile": engine_profile,
        "expected_runs": expected_runs,
        "successful_runs": 0,
        "failed_runs": (
            expected_runs if mode == "run" and graph_path is None else 0
        ),
        "risk_event_count": 0,
        "risk_pairs": 0,
        "errors": (
            []
            if mode == "off" or graph_path is not None
            else [
                {
                    "status": "graph_not_found",
                    "error": (
                        "Canonical replay was requested but no canonical graph "
                        "could be discovered."
                    ),
                }
            ]
        ),
    }
    run_columns = [
        "policy",
        "seed",
        "status",
        "returncode",
        "error",
        "result_dir",
        "run_kind",
        "is_derived",
        "integration_mode",
        *CANONICAL_KPI_NAMES,
        "recovery_status",
        "recovery_episode_detected",
        "recovery_episode_basis",
        *[
            column
            for metric in CANONICAL_KPI_NAMES
            for column in (
                f"mrp_reference_{metric}",
                f"delta_vs_mrp_{metric}",
            )
        ],
        "delta_vs_mrp_recovery_time_status",
    ]
    summary_columns = [
        "policy",
        "paired_seed_count",
        *[
            column
            for metric in CANONICAL_KPI_NAMES
            for column in (
                f"mean_delta_{metric}",
                f"paired_observed_count_{metric}",
                f"median_delta_{metric}",
                f"p90_delta_{metric}",
                f"ci95_low_delta_{metric}",
                f"ci95_high_delta_{metric}",
                f"ci95_status_delta_{metric}",
                f"standardized_effect_{metric}",
                f"standardized_effect_status_{metric}",
                f"win_rate_{metric}",
            )
        ],
    ]
    empty_runs = pd.DataFrame(columns=run_columns)
    empty_summary = pd.DataFrame(columns=summary_columns)
    empty_overlays = pd.DataFrame(
        columns=["policy", "integration_mode"]
    )
    if mode == "off" or graph_path is None:
        return empty_runs, empty_summary, empty_overlays, metadata

    if mode == "overlay":
        _, overlays = prepare_canonical_overlay_package(
            graph_path=graph_path,
            decisions=decisions,
            actions=actions,
            output_root=output_root,
            days=days,
            scenario_id=scenario_id,
        )
        output_root.mkdir(parents=True, exist_ok=True)
        overlays.to_csv(
            output_root / "canonical_control_overlays.csv",
            index=False,
        )
        metadata.update(
            {
                "status": "overlays_prepared",
                "integration_mode": "legacy_fixed_overlay_prepared",
                "overlay_rows": int(len(overlays)),
            }
        )
        return empty_runs, empty_summary, overlays, metadata

    _clear_legacy_overlay_artifacts_for_daily_replay(output_root)
    (
        replay_prediction_path,
        expected_risk_events,
        expected_risk_ledger,
        risk_lane_activity_metadata,
    ) = _prepare_canonical_activity_selection(
        graph_path=graph_path,
        baseline_path=baseline_path,
        prediction_path=prediction_path,
        physical_risk_envelope=physical_risk_envelope,
        output_root=output_root,
        days=days,
        risk_top_pairs=int(risk_top_pairs),
        prediction_horizon_days=30,
    )
    canonical_seeds = list(
        range(
            int(seed) + 90_000,
            int(seed) + 90_000 + max(1, int(seed_count)),
        )
    )
    runs, summary, overlays = run_canonical_replays(
        repo_root=repo_root,
        graph_path=graph_path,
        decisions=decisions,
        actions=actions,
        seeds=canonical_seeds,
        output_root=output_root,
        days=days,
        scenario_id=scenario_id,
        prediction_path=replay_prediction_path,
        physical_risk_envelope=physical_risk_envelope,
        risk_top_pairs=int(risk_top_pairs),
        prediction_horizon_days=30,
        enable_state_dependent_risks=True,
        engine_extra_args=engine_extra_args,
        engine_profile_metadata=engine_profile,
    )
    _reconcile_canonical_activity_selection(
        output_root=output_root,
        expected_events=expected_risk_events,
        expected_ledger=expected_risk_ledger,
    )
    if not overlays.empty:
        if "policy" not in overlays or "integration_mode" not in overlays:
            raise RuntimeError(
                "Daily canonical replay returned an incomplete overlay audit."
            )
        if overlays["policy"].astype(str).eq(
            "adaptive_weighted_replay"
        ).any():
            raise RuntimeError(
                "Daily canonical replay returned a legacy adaptive overlay."
            )
        invalid_modes = overlays.loc[
            ~overlays["integration_mode"]
            .astype(str)
            .eq("daily_open_loop_schedule")
        ]
        if not invalid_modes.empty:
            raise RuntimeError(
                "Daily canonical replay returned non-daily integration rows."
            )
    overlays.to_csv(
        output_root / "canonical_control_overlays.csv",
        index=False,
    )

    expected_policies = [
        *(str(action.name) for action in actions),
        "adaptive_daily",
    ]
    execution_metadata = _canonical_execution_metadata(
        runs,
        expected_runs=len(expected_policies) * len(canonical_seeds),
        expected_policies=expected_policies,
        expected_seeds=canonical_seeds,
    )
    paired_seed_count = 0
    if (
        not summary.empty
        and "policy" in summary
        and "paired_seed_count" in summary
    ):
        reference_rows = summary.loc[
            summary["policy"].astype(str).eq("mrp_reference"),
            "paired_seed_count",
        ]
        if not reference_rows.empty:
            paired_seed_count = int(reference_rows.iloc[0])
    metadata.update(
        {
            "integration_mode": "daily_open_loop_schedule",
            "overlay_rows": int(len(overlays)),
            "paired_seed_count_requested": int(seed_count),
            "paired_seed_count": paired_seed_count,
            "risk_lane_activity": risk_lane_activity_metadata,
            **_canonical_risk_artifact_metadata(output_root),
            **execution_metadata,
        }
    )
    return runs, summary, overlays, metadata


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    config_dir = output_dir / "config"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(args.config).resolve()
    base_config = load_config(config_path if config_path.exists() else None)
    # The end-2026 runner uses a tractable validation profile by default; the
    # original higher-fidelity counts remain available through CLI overrides.
    base_config["controller_scenarios"] = max(2, int(args.controller_scenarios))
    base_config["policy_comparison_scenarios"] = max(4, int(args.policy_comparison_scenarios))
    base_config["controller_horizon_days"] = max(7, int(args.controller_horizon_days))
    context = build_input_context(
        repo_root,
        args.baseline_csv,
        args.risk_csv,
        max(56, int(args.days)),
        int(args.seed),
        bool(args.synthetic),
        mapping_config=base_config.get("physical_risk_mapping", {}),
    )
    context, granular_interval, granular_physical = _refresh_prediction_mapping(
        context, base_config, len(context.input_series)
    )
    prediction_interval_export = combine_portfolio_and_granular_envelopes(
        context.prediction_interval
        if context.prediction_interval is not None
        else pd.DataFrame(),
        granular_interval,
    )
    physical_risk_export = combine_portfolio_and_granular_envelopes(
        context.physical_risk_envelope
        if context.physical_risk_envelope is not None
        else pd.DataFrame(),
        granular_physical,
    )
    sensitivity_factors = _parse_sensitivity_factors(
        args.mapping_sensitivity_factors
    )
    mapping_sensitivity = physical_mapping_coefficient_sensitivity(
        context.prediction_interval
        if context.prediction_interval is not None
        else pd.DataFrame(),
        base_config.get("physical_risk_mapping", {}),
        factors=sensitivity_factors,
    )

    # 1. Calibrate regime rules and audit whether nominal reduced-model scales
    # can be refitted without mixing incompatible item/BOM units.
    regime_annotations_path = (
        Path(args.regime_annotations_csv).resolve()
        if args.regime_annotations_csv
        else None
    )
    calibration = calibrate_from_context(
        context,
        base_config,
        regime_annotations_path=regime_annotations_path,
    )
    config = calibration.config
    actions = tuple(safety_filter(action, config) for action in DEFAULT_ACTIONS)
    write_json(config_dir / "calibrated_config.json", config)

    # 2. Run the calibrated adaptive layer and standard policy comparison.
    adaptive, decisions, candidates = run_adaptive_controller(context, config, actions, int(args.seed))
    policy_comparison, fixed_trajectories = simulate_fixed_policy_scenarios(
        context, config, actions, int(args.seed)
    )
    transitions = regime_transition_matrix(adaptive)
    regime_recovery = derive_regime_recovery_episodes(
        adaptive,
        stable_nominal_days=DEFAULT_STABLE_NOMINAL_DAYS,
    )
    regime_recovery_metadata = summarize_regime_recovery(
        regime_recovery,
        stable_nominal_days=DEFAULT_STABLE_NOMINAL_DAYS,
    )
    constraints = derive_constraint_activity(adaptive, config)
    adaptive_space = derive_adaptive_state_space(adaptive)
    impedance, impedance_summary = estimate_supplier_impedance(adaptive)

    # 3. Paired policy experiment with common random numbers.
    paired_seeds = list(range(int(args.seed), int(args.seed) + max(1, int(args.paired_seed_count))))
    paired_runs, paired_summary = paired_policy_experiment(context, config, actions, paired_seeds)

    # 4. Explicit false-positive / false-negative experiments.
    confusion_seeds = list(range(
        int(args.seed) + 50_000,
        int(args.seed) + 50_000 + max(1, int(args.confusion_seed_count)),
    ))
    confusion_runs, confusion_summary, confusion_regret = forecast_confusion_experiment(
        context,
        config,
        actions,
        confusion_seeds,
        duration_days=min(int(args.confusion_duration_days), max(7, len(context.input_series) // 2)),
        alert_response_policy=args.confusion_alert_response_policy,
    )
    sensitivity_seed_count = max(
        0, min(int(args.confusion_sensitivity_seed_count), len(confusion_seeds))
    )
    sensitivity_durations = tuple(
        sorted({
            min(int(value), max(7, len(context.input_series) // 2))
            for value in args.confusion_sensitivity_durations
        })
    )
    confusion_sensitivity = (
        forecast_confusion_sensitivity_experiment(
            context,
            config,
            actions,
            confusion_seeds[:sensitivity_seed_count],
            alert_thresholds=args.confusion_alert_thresholds,
            interval_half_widths=args.confusion_interval_half_widths,
            alert_durations_days=sensitivity_durations,
            alert_response_policy=args.confusion_alert_response_policy,
        )
        if sensitivity_seed_count > 0
        else pd.DataFrame()
    )

    # 5. RCI business review pack. Human validation is explicitly pending unless
    # a completed review file is provided.
    rci_review = build_rci_business_validation_pack(adaptive, decisions, candidates, config)
    rci_review.to_csv(data_dir / "rci_business_review_template.csv", index=False)
    build_blinded_rci_review(rci_review).to_csv(
        data_dir / "rci_business_review_blind.csv",
        index=False,
    )
    rci_review_variable_dictionary().to_csv(
        data_dir / "rci_business_variable_dictionary.csv", index=False
    )
    write_business_validation_guide(output_dir / "rci_business_validation_guide.md")
    if args.business_review_csv:
        completed_path = Path(args.business_review_csv).resolve()
        completed_review = pd.read_csv(completed_path) if completed_path.exists() else pd.DataFrame()
    else:
        completed_review = pd.DataFrame()
    completed_review = bind_completed_business_review(
        rci_review,
        completed_review,
    )
    rci_status = summarize_completed_business_review(completed_review)
    rci_status = {
        **rci_status,
        "review_pack_schema_version": (
            str(rci_review["review_pack_schema_version"].iloc[0])
            if not rci_review.empty
            else None
        ),
        "review_pack_id": (
            str(rci_review["review_pack_id"].iloc[0])
            if not rci_review.empty
            else None
        ),
        "review_pack_hash": (
            str(rci_review["review_pack_hash"].iloc[0])
            if not rci_review.empty
            else None
        ),
        "pack_episode_count": int(len(rci_review)),
        "selected_episode_count": int(
            pd.to_numeric(
                rci_review.get(
                    "is_selected",
                    pd.Series(dtype=float),
                ),
                errors="coerce",
            ).fillna(0).sum()
        ),
        "rejected_episode_count": int(
            pd.to_numeric(
                rci_review.get(
                    "is_rejected",
                    pd.Series(dtype=float),
                ),
                errors="coerce",
            ).fillna(0).sum()
        ),
        "aggressive_episode_count": int(
            pd.to_numeric(
                rci_review.get(
                    "is_aggressive",
                    pd.Series(dtype=float),
                ),
                errors="coerce",
            ).fillna(0).sum()
        ),
        "review_only_counterfactual_count": int(
            pd.to_numeric(
                rci_review.get(
                    "decision_eligible",
                    pd.Series(dtype=float),
                ),
                errors="coerce",
            ).fillna(1).eq(0).sum()
        ),
    }
    write_json(output_dir / "rci_business_validation_status.json", rci_status)

    # 6. Canonical engine stage-1 reinjection.
    canonical_runs = pd.DataFrame()
    canonical_summary = pd.DataFrame()
    canonical_overlays = pd.DataFrame()
    graph_path = discover_canonical_graph(repo_root, args.canonical_graph)
    (
        canonical_engine_args,
        canonical_engine_profile,
    ) = load_canonical_engine_profile(
        repo_root,
        (
            args.canonical_engine_profile
            if args.canonical_replay == "run"
            else ""
        ),
    )
    canonical_root = output_dir / "canonical_replay"
    (
        canonical_runs,
        canonical_summary,
        canonical_overlays,
        canonical_metadata,
    ) = _run_canonical_stage(
        mode=args.canonical_replay,
        repo_root=repo_root,
        graph_path=graph_path,
        decisions=decisions,
        actions=actions,
        output_root=canonical_root,
        days=min(int(args.canonical_days), len(context.input_series)),
        scenario_id=args.scenario_id,
        seed=int(args.seed),
        seed_count=int(args.canonical_seed_count),
        prediction_path=(
            Path(context.risk_path) if context.risk_path else None
        ),
        physical_risk_envelope=physical_risk_export,
        risk_top_pairs=int(args.canonical_top_risk_pairs),
        engine_extra_args=canonical_engine_args,
        engine_profile=canonical_engine_profile,
        baseline_path=(
            Path(context.baseline_path)
            if context.baseline_path
            else None
        ),
    )

    _write_frames(data_dir, {
        "input_series.csv": context.input_series,
        "prediction_interval_envelope.csv": prediction_interval_export,
        "physical_risk_envelope.csv": physical_risk_export,
        "portfolio_prediction_interval_envelope.csv": context.prediction_interval if context.prediction_interval is not None else pd.DataFrame(),
        "portfolio_physical_risk_envelope.csv": context.physical_risk_envelope if context.physical_risk_envelope is not None else pd.DataFrame(),
        "physical_mapping_coefficient_sensitivity.csv": mapping_sensitivity,
        "regime_calibration_frame.csv": calibration.frame,
        "regime_calibration_evidence.csv": calibration.evidence,
        "regime_thresholds_before_after.csv": calibration.evidence,
        "adaptive_state_trajectory.csv": adaptive,
        "policy_decisions.csv": decisions,
        "candidate_policy_evaluations.csv": candidates,
        "fixed_policy_comparison.csv": policy_comparison,
        "fixed_policy_trajectories.csv": fixed_trajectories,
        "regime_transition_matrix.csv": transitions.reset_index(names="from_regime"),
        "regime_recovery_episodes.csv": regime_recovery,
        "active_constraints.csv": constraints,
        "adaptive_state_space.csv": adaptive_space,
        "supplier_impedance_spectrum.csv": impedance,
        "paired_policy_runs.csv": paired_runs,
        "paired_policy_summary.csv": paired_summary,
        "forecast_confusion_runs.csv": confusion_runs,
        "forecast_confusion_summary.csv": confusion_summary,
        "forecast_confusion_regret.csv": confusion_regret,
        "forecast_confusion_sensitivity.csv": confusion_sensitivity,
        "canonical_runs.csv": canonical_runs,
        "canonical_paired_summary.csv": canonical_summary,
        "canonical_control_overlays.csv": canonical_overlays,
    })

    prediction_meta = dict(context.prediction_interval_metadata or {})
    provenance = _build_run_provenance(repo_root, context, prediction_meta)
    forecast_provenance = dict(provenance.get("forecast") or {})
    overlap_keys = list(prediction_meta.get("overlap_key_columns") or [])
    excluded_overlap_rows = int(
        prediction_meta.get("excluded_overlap_rows") or 0
    )
    if overlap_keys:
        overlap_status = (
            "detected_and_excluded_from_calibration"
            if excluded_overlap_rows > 0
            else "evaluated_no_exact_overlap_detected"
        )
    else:
        overlap_status = "not_evaluable_exact_temporal_lane_keys_unavailable"
    prediction_meta.update({
        "overlap_status": overlap_status,
        "forecast_origin": forecast_provenance.get("origin"),
        "forecast_history_origin": forecast_provenance.get("history_origin"),
        "forecast_label_origin": forecast_provenance.get("label_origin"),
        "forecast_temporal_feature_origin": forecast_provenance.get(
            "temporal_feature_origin"
        ),
        "calibration_use_status": forecast_provenance.get(
            "evaluation_status", "retrospective_non_deployment"
        ),
    })
    regime_confidence_by_regime = {
        str(row.regime): str(row.confidence)
        for row in calibration.evidence.itertuples()
    }
    manifest: dict[str, Any] = {
        "schema_version": "scan.end_2026.validation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": provenance,
        "source": {
            "mode": context.source_mode,
            "baseline_path": context.baseline_path,
            "risk_path": context.risk_path,
            "days": int(len(context.input_series)),
            "baseline_ingestion": dict(context.baseline_ingestion_metadata or {}),
            "baseline_origin": provenance.get("baseline_origin"),
            "baseline_industrial_status": (
                provenance.get("baseline", {}).get("industrial_status")
            ),
        },
        "regime_calibration": {
            **calibration.metadata,
            "confidence_scope": "regime_classification_rule",
            "confidence_by_regime": regime_confidence_by_regime,
        },
        "regime_recovery": regime_recovery_metadata,
        "prediction_to_physics": {
            "prediction_path": context.risk_path,
            **prediction_meta,
            "physical_fields": [
                "availability", "capacity", "lead_time", "quality_yield",
                "purchase_cost", "transport_cost",
            ],
            "controller_scope": "portfolio",
            "export_scopes": [
                "portfolio",
                "supplier_item_destination",
            ],
            "granular_interval_rows": int(len(granular_interval)),
            "granular_physical_rows": int(len(granular_physical)),
            "granular_pairs": int(
                granular_interval[
                    ["supplier_id", "item_id", "dst_node_id"]
                ].drop_duplicates().shape[0]
            ) if not granular_interval.empty else 0,
            "coefficient_sensitivity_factors": list(sensitivity_factors),
            "coefficient_sensitivity_rows": int(len(mapping_sensitivity)),
        },
        "adaptive": adaptive_summary(adaptive),
        "regime_counts": {str(key): int(value) for key, value in adaptive["regime"].value_counts().items()},
        "policy_selection_counts": {str(key): int(value) for key, value in decisions["selected_policy"].value_counts().items()}
        if not decisions.empty else {},
        "paired_policy_summary": _jsonable_record(paired_summary),
        "forecast_confusion_summary": _jsonable_record(confusion_summary),
        "forecast_confusion_sensitivity": {
            "status": (
                "executed" if not confusion_sensitivity.empty else "disabled"
            ),
            "design": (
                "fixed_truth_threshold_x_interval_width_x_response_duration"
            ),
            "rows": int(len(confusion_sensitivity)),
            "seed_count": sensitivity_seed_count,
            "alert_thresholds": [
                float(value) for value in args.confusion_alert_thresholds
            ],
            "interval_half_widths": [
                float(value) for value in args.confusion_interval_half_widths
            ],
            "alert_durations_days": [
                int(value) for value in sensitivity_durations
            ],
            "response_durations_days": [
                int(value) for value in sensitivity_durations
            ],
            "incident_duration_days": (
                sorted(
                    confusion_sensitivity[
                        "incident_duration_days"
                    ].astype(int).unique().tolist()
                )
                if not confusion_sensitivity.empty
                else []
            ),
            "forecast_signal_duration_days": (
                sorted(
                    confusion_sensitivity[
                        "forecast_signal_duration_days"
                    ].astype(int).unique().tolist()
                )
                if not confusion_sensitivity.empty
                else []
            ),
            "physical_pairing_evidence": (
                "physical_scenario_set_fingerprint"
            ),
            "artifact": "data/forecast_confusion_sensitivity.csv",
            "alert_response_policy": args.confusion_alert_response_policy,
        },
        "canonical_replay": canonical_metadata,
        "rci_business_validation": rci_status,
        "supplier_impedance": impedance_summary,
        "work_package_status": {
            "regime_calibration": (
                "implemented_with_business_annotations_and_pseudo_fallback"
                if calibration.metadata["regime_annotations"]["business_label_days"] > 0
                else "implemented_with_trajectory_pseudo_anchors"
            ),
            "prediction_intervals_to_physical_disruptions": "implemented_research_mapping",
            "canonical_action_reinjection": canonical_metadata["status"],
            "paired_seed_policy_comparison": "implemented",
            "false_positive_false_negative_study": (
                "implemented_with_configurable_sensitivity_grid"
                if not confusion_sensitivity.empty
                else "implemented_without_sensitivity_grid"
            ),
            "rci_procurement_planning_validation": rci_status.get("status", "pending_business_review"),
        },
        "limitations": [
            (
                "Imported industrial regime annotations are applied only on "
                "resolved voted days; all other days retain explicit pseudo-labels."
                if calibration.metadata["regime_annotations"]["business_label_days"] > 0
                else "Industrial labels are still required to confirm calibrated regimes."
            ),
            (
                "Reduced-model nominal parameters remain declared research "
                "hypotheses because unit comparability across items and "
                "bill-of-material levels is not established; the aggregate "
                "refit candidate is diagnostic only."
                if not calibration.metadata[
                    "nominal_parameter_calibration"
                ]["refit_applied"]
                else "The nominal-parameter refit uses only normalized "
                "synthetic reduced-model series and is not an industrial "
                "estimate."
            ),
            (
                "Reduced paired and confusion experiments consume simulated "
                "case-study demand and risk paths but reconstruct initial "
                "stocks, pipeline and dynamics; they are not article/BOM state "
                "replays. Canonical runs are the separate physical-integration "
                "evidence."
            ),
            "Prediction-to-physics coefficients are explicit research hypotheses.",
            (
                "Adaptive canonical replay uses a precomputed daily open-loop "
                "schedule; canonical state feedback is not yet implemented."
            ),
            (
                "The canonical oracle is an ex-post best-fixed-policy row "
                "derived from completed physical replays; it is not an online "
                "policy or an additional engine run."
            ),
            (
                "RCI business validation remains pending until procurement and "
                "planning complete the review CSV."
                if rci_status.get("status") == "pending_business_review"
                else "Completed business ratings are available; RCI performance "
                "is reported with unresolved ties excluded and leave-one-episode-"
                "out estimates, without claiming industrial certification."
            ),
        ],
    }
    write_json(output_dir / "run_manifest.json", manifest)
    write_report(
        output_dir, context, adaptive, decisions, policy_comparison,
        constraints, impedance_summary, manifest,
    )
    write_end_2026_report(
        output_dir,
        manifest,
        calibration.evidence,
        paired_summary,
        confusion_summary,
        rci_status,
        canonical_summary,
        confusion_sensitivity,
    )
    if not args.no_plots:
        if context.source_mode == "synthetic_fallback":
            figure_provenance_label = (
                "Evidence: synthetic fallback experiment; exploratory, "
                "non-industrial"
            )
        elif (
            provenance.get("forecast", {}).get("origin")
            == "synthetic_prediction_poc"
        ):
            figure_provenance_label = (
                "Evidence: etudecas case-study simulation + synthetic "
                "prediction PoC; exploratory, non-industrial"
            )
        else:
            figure_provenance_label = (
                "Evidence: etudecas case-study simulation; exploratory, "
                "non-industrial"
            )
        save_plots(
            output_dir, adaptive, decisions, policy_comparison, fixed_trajectories,
            transitions, constraints, adaptive_space, impedance,
            figure_provenance_label,
        )
        save_end_2026_plots(
            output_dir,
            calibration.frame,
            calibration.evidence,
            context.prediction_interval if context.prediction_interval is not None else pd.DataFrame(),
            context.physical_risk_envelope if context.physical_risk_envelope is not None else pd.DataFrame(),
            paired_summary,
            confusion_summary,
            confusion_regret,
            rci_review,
            canonical_summary,
            paired_runs,
            confusion_sensitivity,
            canonical_runs,
            completed_review,
            rci_status,
            regime_recovery,
            figure_provenance_label,
        )

    print(f"SCAN end-2026 validation package completed: {output_dir}")
    print(f"Source mode: {context.source_mode}")
    print(f"Calibrated regimes: {calibration.metadata['regime_counts']}")
    print(f"Canonical replay: {canonical_metadata['status']}")
    print(f"RCI business validation: {rci_status.get('status')}")
    if (
        args.canonical_replay != "off"
        and canonical_metadata["status"] not in {"overlays_prepared", "executed"}
    ):
        print(
            "Canonical replay did not complete successfully; see "
            "run_manifest.json and data/canonical_runs.csv.",
            file=sys.stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
