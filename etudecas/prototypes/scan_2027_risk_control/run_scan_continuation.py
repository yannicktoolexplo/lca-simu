#!/usr/bin/env python3
"""Orchestrate the next RESILIENCE-SCAN validation campaign.

This script is a practical hand-off between the end-2026 validation PoC and the
2027 control work. It can:

1. check the repository and run the prototype tests;
2. optionally rebuild the active 5-year etudecas baseline;
3. run the end-2026 validation on real or synthetic inputs;
4. execute or prepare canonical paired-seed replays;
5. ingest a completed procurement/planning RCI review;
6. generate a concise hand-off report and next-action list.

The canonical engine is invoked through existing public entrypoints. No direct
modification of the engine is performed by this orchestrator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO_ROOT_DEFAULT = HERE.parents[2]
END_2026_RUNNER = HERE / "run_end_2026_validation.py"
ETUDECAS_PIPELINE = REPO_ROOT_DEFAULT / "etudecas" / "run_etudecas_pipeline.py"
TEST_DIR = HERE / "tests"


@dataclass
class StepResult:
    name: str
    status: str
    started_at_utc: str
    finished_at_utc: str
    return_code: int
    command: list[str]
    log_path: str | None = None
    message: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Continue the RESILIENCE-SCAN work: repository checks, real-data "
            "end-2026 validation, canonical paired replays, RCI review and 2027 hand-off."
        )
    )
    parser.add_argument(
        "--stage",
        choices=["check", "refresh", "validate", "business", "handoff", "all"],
        default="all",
        help="Campaign stage to execute. 'all' runs the useful stages in sequence.",
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT_DEFAULT))
    parser.add_argument(
        "--output-root",
        default=str(HERE / "outputs" / "continuation_2026_2027"),
        help="Campaign root. The validation package is written below this directory.",
    )
    parser.add_argument(
        "--config",
        default="",
        help=(
            "Optional calibrated/research configuration forwarded to the "
            "end-2026 runner."
        ),
    )
    parser.add_argument("--baseline-csv", default="auto")
    parser.add_argument("--risk-csv", default="auto")
    parser.add_argument(
        "--regime-annotations-csv",
        default="",
        help=(
            "Optional expert regime labels forwarded to the end-2026 calibration "
            "(day/period, site, item/article, validated_regime, "
            "expert_confidence, comment)."
        ),
    )
    parser.add_argument("--canonical-graph", default="auto")
    parser.add_argument(
        "--canonical-engine-profile",
        default="",
        help=(
            "Optional JSON profile forwarded to the canonical engine replay."
        ),
    )
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--seed", type=int, default=20260)
    parser.add_argument("--paired-seed-count", type=int, default=20)
    parser.add_argument("--confusion-seed-count", type=int, default=10)
    parser.add_argument("--confusion-duration-days", type=int, default=42)
    parser.add_argument(
        "--confusion-alert-response-policy",
        default="balanced_robust",
    )
    parser.add_argument(
        "--confusion-alert-thresholds",
        default="0.40,0.70",
        help="Comma-separated alert thresholds for the FP/FN sensitivity grid.",
    )
    parser.add_argument(
        "--confusion-interval-half-widths",
        default="0.05,0.18",
        help="Comma-separated prediction half-widths for the FP/FN sensitivity grid.",
    )
    parser.add_argument(
        "--confusion-sensitivity-durations",
        default="14,42",
        help="Comma-separated alert durations for the FP/FN sensitivity grid.",
    )
    parser.add_argument(
        "--confusion-sensitivity-seed-count",
        type=int,
        default=1,
        help="Number of paired seeds used by the sensitivity grid; 0 disables it.",
    )
    parser.add_argument("--controller-scenarios", type=int, default=24)
    parser.add_argument("--policy-comparison-scenarios", type=int, default=48)
    parser.add_argument("--controller-horizon-days", type=int, default=28)
    parser.add_argument(
        "--canonical-replay",
        choices=["off", "overlay", "run"],
        default="overlay",
        help=(
            "Use 'run' for full multi-item paired daily-control replays; "
            "'overlay' prepares auditable schedules and compatibility overlays."
        ),
    )
    parser.add_argument("--canonical-days", type=int, default=365)
    parser.add_argument("--canonical-seed-count", type=int, default=5)
    parser.add_argument("--canonical-top-risk-pairs", type=int, default=5)
    parser.add_argument(
        "--mapping-sensitivity-factors",
        default="0.8,1.0,1.2",
        help=(
            "Comma-separated positive factors for prediction-to-physics "
            "coefficient sensitivity."
        ),
    )
    parser.add_argument("--business-review-csv", default="")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument(
        "--rebuild-baseline",
        action="store_true",
        help="Before validation, rebuild the active 5-year etudecas baseline.",
    )
    parser.add_argument("--with-montecarlo", action="store_true")
    parser.add_argument("--montecarlo-runs", type=int, default=60)
    parser.add_argument("--force", action="store_true", help="Rerun completed steps.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=(
            "Continue to the hand-off report even if a command fails; the "
            "campaign still exits non-zero after recording all failed steps."
        ),
    )
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def command_text(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def fingerprint(command: list[str]) -> str:
    raw = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_prototype_test_command(test_dir: Path) -> list[str]:
    """Return the command that executes every unittest- and pytest-style test."""

    return [sys.executable, "-m", "pytest", str(test_dir), "-q"]


def load_campaign_state(path: Path) -> dict[str, Any]:
    state = load_json(path, {})
    return state if isinstance(state, dict) else {}


def save_step_state(state_path: Path, result: StepResult, command_hash: str) -> None:
    state = load_campaign_state(state_path)
    steps = state.setdefault("steps", {})
    record = asdict(result)
    record["command_fingerprint"] = command_hash
    steps[result.name] = record
    state["updated_at_utc"] = utc_now()
    write_json(state_path, state)


def step_is_current(state_path: Path, name: str, command: list[str]) -> bool:
    state = load_campaign_state(state_path)
    record = (state.get("steps") or {}).get(name) or {}
    return record.get("status") == "ok" and record.get("command_fingerprint") == fingerprint(command)


def run_command(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    output_root: Path,
    state_path: Path,
    force: bool,
    dry_run: bool,
) -> StepResult:
    if not force and step_is_current(state_path, name, command):
        now = utc_now()
        result = StepResult(
            name=name,
            status="skipped_current",
            started_at_utc=now,
            finished_at_utc=now,
            return_code=0,
            command=command,
            message="Already completed with the same command. Use --force to rerun.",
        )
        print(f"[SKIP] {name}: already current")
        return result

    log_dir = output_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    started = utc_now()
    print(f"[RUN ] {name}")
    print(f"       {command_text(command)}")

    if dry_run:
        result = StepResult(
            name=name,
            status="dry_run",
            started_at_utc=started,
            finished_at_utc=utc_now(),
            return_code=0,
            command=command,
            log_path=str(log_path),
            message="Command not executed because --dry-run was supplied.",
        )
        save_step_state(state_path, result, fingerprint(command))
        return result

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = process.stdout or ""
    log_path.write_text(output, encoding="utf-8", errors="replace")
    if output.strip():
        tail = "\n".join(output.rstrip().splitlines()[-18:])
        print(tail)
    status = "ok" if process.returncode == 0 else "failed"
    result = StepResult(
        name=name,
        status=status,
        started_at_utc=started,
        finished_at_utc=utc_now(),
        return_code=int(process.returncode),
        command=command,
        log_path=str(log_path),
        message="" if process.returncode == 0 else "See the step log for details.",
    )
    save_step_state(state_path, result, fingerprint(command))
    print(f"[{' OK ' if status == 'ok' else 'FAIL'}] {name} -> {log_path}")
    return result


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def build_validation_command(args: argparse.Namespace, validation_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(END_2026_RUNNER),
        "--repo-root",
        str(Path(args.repo_root).resolve()),
        "--output-dir",
        str(validation_dir),
        "--baseline-csv",
        str(args.baseline_csv),
        "--risk-csv",
        str(args.risk_csv),
        "--days",
        str(max(56, int(args.days))),
        "--seed",
        str(int(args.seed)),
        "--paired-seed-count",
        str(max(1, int(args.paired_seed_count))),
        "--confusion-seed-count",
        str(max(1, int(args.confusion_seed_count))),
        "--confusion-duration-days",
        str(max(7, int(args.confusion_duration_days))),
        "--confusion-alert-response-policy",
        str(args.confusion_alert_response_policy),
        "--confusion-alert-thresholds",
        str(args.confusion_alert_thresholds),
        "--confusion-interval-half-widths",
        str(args.confusion_interval_half_widths),
        "--confusion-sensitivity-durations",
        str(args.confusion_sensitivity_durations),
        "--confusion-sensitivity-seed-count",
        str(max(0, int(args.confusion_sensitivity_seed_count))),
        "--controller-scenarios",
        str(max(2, int(args.controller_scenarios))),
        "--policy-comparison-scenarios",
        str(max(4, int(args.policy_comparison_scenarios))),
        "--controller-horizon-days",
        str(max(7, int(args.controller_horizon_days))),
        "--canonical-replay",
        str(args.canonical_replay),
        "--canonical-graph",
        str(args.canonical_graph),
        "--canonical-days",
        str(max(1, int(args.canonical_days))),
        "--canonical-seed-count",
        str(max(1, int(args.canonical_seed_count))),
        "--canonical-top-risk-pairs",
        str(max(1, int(args.canonical_top_risk_pairs))),
        "--mapping-sensitivity-factors",
        str(args.mapping_sensitivity_factors),
        "--scenario-id",
        str(args.scenario_id),
    ]
    if args.synthetic:
        command.append("--synthetic")
    if args.no_plots:
        command.append("--no-plots")
    if args.config:
        command.extend(["--config", str(Path(args.config).resolve())])
    if getattr(args, "canonical_engine_profile", ""):
        command.extend(
            [
                "--canonical-engine-profile",
                str(Path(args.canonical_engine_profile).resolve()),
            ]
        )
    if args.regime_annotations_csv:
        command.extend(
            [
                "--regime-annotations-csv",
                str(Path(args.regime_annotations_csv).resolve()),
            ]
        )
    if args.business_review_csv:
        command.extend(["--business-review-csv", str(Path(args.business_review_csv).resolve())])
    return command


def run_business_review_only(review_csv: Path, validation_dir: Path) -> dict[str, Any]:
    """Update the RCI status without rerunning the simulation campaign."""
    require_file(review_csv, "Completed business review CSV")
    try:
        import pandas as pd

        from etudecas.prototypes.scan_2027_risk_control.end_2026_reporting import (
            save_rci_business_comparison_plot,
        )
        from etudecas.prototypes.scan_2027_risk_control.rci_validation import (
            bind_completed_business_review,
            summarize_completed_business_review,
        )
    except ImportError as exc:  # pragma: no cover - environment-dependent error path
        raise RuntimeError(
            "The business-review stage needs pandas and the SCAN package importable from the repository root."
        ) from exc

    completed = pd.read_csv(review_csv)
    authoritative_path = (
        validation_dir
        / "data"
        / "rci_business_review_template.csv"
    )
    require_file(
        authoritative_path,
        "Authoritative RCI business review template",
    )
    authoritative_review = pd.read_csv(authoritative_path)
    completed = bind_completed_business_review(
        authoritative_review,
        completed,
    )
    status = summarize_completed_business_review(completed)
    save_rci_business_comparison_plot(validation_dir, completed, status)
    write_json(validation_dir / "rci_business_validation_status.json", status)

    manifest_path = validation_dir / "run_manifest.json"
    manifest = load_json(manifest_path, {})
    if isinstance(manifest, dict):
        manifest["rci_business_validation"] = status
        work = manifest.setdefault("work_package_status", {})
        work["rci_procurement_planning_validation"] = status.get("status", "unknown")
        write_json(manifest_path, manifest)
    return status


def status_value(value: Any, default: str = "unknown") -> str:
    return str(value) if value not in (None, "") else default


def build_next_actions(manifest: dict[str, Any], validation_dir: Path) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    source = manifest.get("source") or {}
    calibration = manifest.get("regime_calibration") or {}
    annotation_metadata = calibration.get("regime_annotations") or {}
    prediction = manifest.get("prediction_to_physics") or {}
    canonical = manifest.get("canonical_replay") or {}
    rci = manifest.get("rci_business_validation") or {}

    if source.get("mode") == "synthetic_fallback" or not source.get("baseline_path"):
        actions.append({
            "priority": "P0",
            "work": (
                "Run the campaign on the canonical etudecas case-study "
                "simulation output"
            ),
            "why": (
                "The current package is still based on synthetic or incomplete "
                "trajectories; case-study simulation evidence is the next "
                "integration gate, not an industrial observation."
            ),
            "evidence": "source.mode / source.baseline_path",
        })

    high = int(calibration.get("high_confidence_thresholds") or 0)
    low = int(calibration.get("low_confidence_thresholds") or 0)
    business_label_days = int(annotation_metadata.get("business_label_days") or 0)
    if business_label_days == 0 or high == 0 or low > 0:
        actions.append({
            "priority": "P0",
            "work": "Label representative regime episodes with supply experts",
            "why": "Pseudo-anchors calibrate thresholds, but expert labels are needed for industrial validation.",
            "evidence": (
                f"business-label days={business_label_days}; "
                f"high-confidence thresholds={high}; low-confidence thresholds={low}"
            ),
        })

    interval_method = status_value(prediction.get("interval_method"))
    if interval_method.startswith("fallback") or int(prediction.get("rows_used") or 0) == 0:
        actions.append({
            "priority": "P0",
            "work": "Provide scored prediction rows and incident outcomes",
            "why": "Prediction intervals and physical severity envelopes otherwise remain hypothesis-driven.",
            "evidence": f"interval_method={interval_method}; rows_used={prediction.get('rows_used', 0)}",
        })

    canonical_status = status_value(canonical.get("status"))
    if canonical_status != "executed":
        actions.append({
            "priority": "P0",
            "work": "Execute paired canonical multi-item replays",
            "why": "Prepared schedules are not equivalent to executed physical evidence on the full MRP engine.",
            "evidence": f"canonical_replay.status={canonical_status}",
        })

    rci_status = status_value(rci.get("status"))
    if rci_status == "pending_business_review":
        actions.append({
            "priority": "P1",
            "work": "Complete the blinded RCI workshop with procurement and planning",
            "why": "The Risk Creation Index must be compared with expert judgments before operational use.",
            "evidence": f"rci.status={rci_status}",
        })
    elif rci_status == "review_available":
        actions.append({
            "priority": "P1",
            "work": "Review RCI metrics and record explicit business sign-off",
            "why": (
                "A completed review supports statistical diagnostics but does "
                "not automatically constitute industrial approval."
            ),
            "evidence": f"rci.status={rci_status}",
        })

    confusion_path = validation_dir / "data" / "forecast_confusion_summary.csv"
    if not confusion_path.exists():
        actions.append({
            "priority": "P1",
            "work": "Run false-positive / false-negative experiments",
            "why": "Decision robustness cannot be assessed without separating forecast and physical truth.",
            "evidence": "forecast_confusion_summary.csv missing",
        })

    if not actions:
        actions.extend([
            {
                "priority": "P1",
                "work": "Freeze the calibrated 2026 benchmark and start Scenario/Tube MPC",
                "why": "The empirical prerequisites for a continuous constrained controller are available.",
                "evidence": "All end-2026 gates satisfied",
            },
            {
                "priority": "P2",
                "work": "Estimate supplier impedance with controlled virtual perturbations",
                "why": "Frequency-dependent supplier sensitivity can improve controller tuning and review periods.",
                "evidence": "2027 research roadmap",
            },
        ])
    return actions


def write_handoff_report(
    *,
    output_root: Path,
    validation_dir: Path,
    state_path: Path,
    args: argparse.Namespace,
) -> Path:
    from etudecas.prototypes.scan_2027_risk_control.reporting import (
        prediction_coverage_report_lines,
    )

    manifest_path = validation_dir / "run_manifest.json"
    manifest = load_json(manifest_path, {})
    if not isinstance(manifest, dict):
        manifest = {}
    actions = build_next_actions(manifest, validation_dir)
    state = load_campaign_state(state_path)

    source = manifest.get("source") or {}
    calibration = manifest.get("regime_calibration") or {}
    annotation_metadata = calibration.get("regime_annotations") or {}
    prediction = manifest.get("prediction_to_physics") or {}
    confusion_sensitivity = manifest.get("forecast_confusion_sensitivity") or {}
    canonical = manifest.get("canonical_replay") or {}
    rci = manifest.get("rci_business_validation") or {}
    work = manifest.get("work_package_status") or {}
    coverage_evidence = prediction_coverage_report_lines(prediction)

    lines = [
        "# RESILIENCE-SCAN — campaign continuation hand-off",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "## Executed scope",
        "",
        f"- Baseline source mode: `{status_value(source.get('mode'))}`",
        f"- Baseline path: `{status_value(source.get('baseline_path'), 'not found')}`",
        f"- Supplier-risk path: `{status_value(source.get('risk_path'), 'not found')}`",
        f"- Horizon: `{source.get('days', args.days)}` days",
        f"- Canonical replay mode: `{args.canonical_replay}`",
        "",
        "## End-2026 work-package status",
        "",
    ]
    if work:
        for key, value in work.items():
            lines.append(f"- **{key}**: `{value}`")
    else:
        lines.append("- No validation manifest is available yet.")

    lines.extend([
        "",
        "## Evidence quality",
        "",
        f"- Regime calibration: high={calibration.get('high_confidence_thresholds', 0)}, "
        f"medium={calibration.get('medium_confidence_thresholds', 0)}, "
        f"low={calibration.get('low_confidence_thresholds', 0)} confidence thresholds.",
        f"- Regime-label provenance: `{status_value(annotation_metadata.get('label_provenance'))}`; "
        f"business-label days={annotation_metadata.get('business_label_days', 0)}; "
        f"coverage={annotation_metadata.get('business_label_coverage_fraction', 0.0)}.",
        f"- Material-cover source: `{status_value(calibration.get('material_cover_source'))}`.",
        f"- Prediction-envelope method: `{status_value(prediction.get('interval_method'))}`; "
        f"rows used={prediction.get('rows_used', 0)}; pairs used={prediction.get('pairs_used', 0)}.",
        *coverage_evidence,
        f"- Prediction exports: scopes={prediction.get('export_scopes', [])}; "
        f"granular rows={prediction.get('granular_interval_rows', 0)}; "
        f"granular pairs={prediction.get('granular_pairs', 0)}; "
        f"controller scope=`{status_value(prediction.get('controller_scope'))}`.",
        f"- Forecast horizon policy: validity={prediction.get('forecast_validity_days')} days; "
        f"prior centre={prediction.get('long_horizon_prior_center')}; "
        f"uncertainty=`{status_value(prediction.get('uncertainty_policy'))}`.",
        f"- Physical-mapping sensitivity: rows={prediction.get('coefficient_sensitivity_rows', 0)}; "
        f"factors={prediction.get('coefficient_sensitivity_factors', [])}.",
        f"- FP/FN sensitivity: `{status_value(confusion_sensitivity.get('status'))}`; "
        f"design=`{status_value(confusion_sensitivity.get('design'))}`; "
        f"rows={confusion_sensitivity.get('rows', 0)}.",
        f"- Canonical status: `{status_value(canonical.get('status'))}`.",
        f"- Canonical runs: expected={canonical.get('expected_runs', 0)}; "
        f"successful={canonical.get('successful_runs', 0)}; "
        f"failed={canonical.get('failed_runs', 0)}.",
        f"- RCI business status: `{status_value(rci.get('status'))}`; completed rows={rci.get('completed_rows', 0)}.",
        "",
        "## Prioritized next actions",
        "",
        "| Priority | Work | Why | Evidence |",
        "|---|---|---|---|",
    ])
    for action in actions:
        lines.append(
            f"| {action['priority']} | {action['work']} | {action['why']} | `{action['evidence']}` |"
        )

    lines.extend([
        "",
        "## Recommended commands",
        "",
        "Prepare and validate on automatically discovered real outputs:",
        "",
        "```powershell",
        "python etudecas/prototypes/scan_2027_risk_control/run_scan_continuation.py `",
        "  --stage all `",
        "  --canonical-replay overlay",
        "```",
        "",
        "Run the full paired canonical campaign after checking overlays:",
        "",
        "```powershell",
        "python etudecas/prototypes/scan_2027_risk_control/run_scan_continuation.py `",
        "  --stage validate `",
        "  --canonical-replay run `",
        "  --canonical-seed-count 5 `",
        "  --force",
        "```",
        "",
        "Update only the RCI status after the workshop:",
        "",
        "```powershell",
        "python etudecas/prototypes/scan_2027_risk_control/run_scan_continuation.py `",
        "  --stage business `",
        "  --business-review-csv <completed_review.csv>",
        "```",
        "",
        "## Campaign files",
        "",
        f"- Validation manifest: `{manifest_path}`",
        f"- Campaign state: `{state_path}`",
        f"- Logs: `{output_root / 'logs'}`",
        f"- RCI blind review: `{validation_dir / 'data' / 'rci_business_review_blind.csv'}`",
        "",
        "## Limits",
        "",
        "- Prediction-to-physics coefficients remain research hypotheses; one-at-a-time sensitivity does not replace incident-based estimation.",
        "- The canonical engine now accepts bounded daily schedules; the adaptive schedule is precomputed, so state-feedback closed loop is not claimed.",
        "- Any canonical `derived_oracle` row is an ex-post best-fixed benchmark copied from an executed run, not another replay or an online oracle policy.",
        "- Canonical `run` mode can be computationally expensive. Start with `overlay`, inspect the schedules and compatibility overlays, then increase seed counts.",
        "- Missing or incomplete expert ratings remain `pending_business_review`; a complete panel becomes `review_available`, which still requires explicit governance sign-off.",
    ])

    report_path = output_root / "SCAN_CONTINUATION_HANDOFF.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    write_json(
        output_root / "next_actions.json",
        {
            "generated_at_utc": utc_now(),
            "validation_manifest": str(manifest_path),
            "campaign_state": state,
            "next_actions": actions,
        },
    )
    return report_path


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_root = Path(args.output_root).resolve()
    validation_dir = output_root / "end_2026_validation"
    state_path = output_root / "campaign_state.json"
    output_root.mkdir(parents=True, exist_ok=True)

    end_runner = repo_root / "etudecas" / "prototypes" / "scan_2027_risk_control" / "run_end_2026_validation.py"
    pipeline = repo_root / "etudecas" / "run_etudecas_pipeline.py"
    test_dir = repo_root / "etudecas" / "prototypes" / "scan_2027_risk_control" / "tests"
    require_file(end_runner, "End-2026 validation runner")

    results: list[StepResult] = []

    def execute(name: str, command: list[str]) -> bool:
        result = run_command(
            name=name,
            command=command,
            cwd=repo_root,
            output_root=output_root,
            state_path=state_path,
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
        results.append(result)
        ok = result.return_code == 0
        if not ok and not args.continue_on_error:
            raise RuntimeError(f"Step failed: {name}. See {result.log_path}")
        return ok

    try:
        if args.stage in {"check", "all"}:
            if not args.skip_tests:
                execute(
                    "prototype_tests",
                    build_prototype_test_command(test_dir),
                )
            if not args.skip_doctor:
                require_file(pipeline, "etudecas pipeline")
                execute("etudecas_doctor", [sys.executable, str(pipeline), "doctor"])

        if args.stage == "refresh" or (args.stage == "all" and args.rebuild_baseline):
            require_file(pipeline, "etudecas pipeline")
            refresh_command = [sys.executable, str(pipeline), "rebuild-map-5y"]
            if args.with_montecarlo:
                refresh_command.extend(["--with-montecarlo", "--montecarlo-runs", str(max(1, args.montecarlo_runs))])
            execute("refresh_5y_baseline", refresh_command)

        if args.stage in {"validate", "all"}:
            command = build_validation_command(args, validation_dir)
            # Use the runner found under the selected repository root rather than
            # the path resolved when this script was authored.
            command[1] = str(end_runner)
            execute("end_2026_validation", command)

        if args.stage == "business":
            if not args.business_review_csv:
                raise ValueError("--business-review-csv is required for --stage business")
            if args.dry_run:
                print(f"[DRY ] business review -> {args.business_review_csv}")
            else:
                status = run_business_review_only(Path(args.business_review_csv).resolve(), validation_dir)
                now = utc_now()
                result = StepResult(
                    name="business_review",
                    status="ok",
                    started_at_utc=now,
                    finished_at_utc=now,
                    return_code=0,
                    command=["business_review", str(Path(args.business_review_csv).resolve())],
                    message=json.dumps(status, ensure_ascii=False),
                )
                save_step_state(state_path, result, fingerprint(result.command))
                results.append(result)
                print(json.dumps(status, indent=2, ensure_ascii=False))

        if args.stage in {"handoff", "all", "business", "validate"}:
            report_path = write_handoff_report(
                output_root=output_root,
                validation_dir=validation_dir,
                state_path=state_path,
                args=args,
            )
            print(f"[ OK ] hand-off report -> {report_path}")

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        if args.continue_on_error:
            report_path = write_handoff_report(
                output_root=output_root,
                validation_dir=validation_dir,
                state_path=state_path,
                args=args,
            )
            print(f"[INFO] partial hand-off report -> {report_path}")
        return 1

    failed_results = [
        result
        for result in results
        if result.return_code != 0 or result.status == "failed"
    ]
    overall_status = "failed" if failed_results else "ok"
    write_json(
        output_root / "last_run_summary.json",
        {
            "generated_at_utc": utc_now(),
            "stage": args.stage,
            "overall_status": overall_status,
            "failed_steps": [result.name for result in failed_results],
            "results": [asdict(result) for result in results],
            "validation_output": str(validation_dir),
        },
    )
    if failed_results:
        failed_names = ", ".join(result.name for result in failed_results)
        print(
            "[ERROR] SCAN continuation completed its requested hand-off but "
            f"one or more steps failed: {failed_names}",
            file=sys.stderr,
        )
        return 1
    print(f"SCAN continuation campaign completed: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
