"""Execution and manifest generation for targeted lot-trace replays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

from .comparison import write_lot_delta_report
from .discovery import ReplayCatalog
from .metrics import extract_run_metrics, lot_trace_evidence
from .ranking import RankedScenario
from .schema import KpiSpec, ScenarioCandidate

SCHEMA_VERSION = "etudecas.targeted_lot_replay.v1"
REPO_ROOT = Path(__file__).resolve().parents[4]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "scenario"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _remove_flag(command: list[str], flag: str, *, takes_value: bool = False) -> list[str]:
    result: list[str] = []
    index = 0
    while index < len(command):
        token = command[index]
        if token.startswith(f"{flag}="):
            index += 1
            continue
        if token == flag:
            index += 2 if takes_value and index + 1 < len(command) else 1
            continue
        result.append(token)
        index += 1
    return result


def _set_value_flag(command: list[str], flag: str, value: str) -> list[str]:
    updated = list(command)
    for index, token in enumerate(updated):
        if token.startswith(f"{flag}="):
            updated[index] = f"{flag}={value}"
            return updated
    if flag in updated:
        index = updated.index(flag)
        if index + 1 >= len(updated):
            raise ValueError(f"Recorded command has no value after {flag}")
        updated[index + 1] = value
        return updated
    updated.extend([flag, value])
    return updated


def build_replay_command(
    candidate: ScenarioCandidate,
    output_dir: Path,
    *,
    python_executable: str | None = None,
    days: int | None = None,
) -> list[str]:
    """Rebuild a recorded simulator command and force lot-level outputs."""

    command = list(candidate.simulator_command)
    if not command:
        raise ValueError(f"Scenario {candidate.scenario_id} has no simulator command.")
    executable_name = Path(command[0]).name.lower()
    if executable_name in {"python", "python.exe", "python3", "python3.exe"}:
        command[0] = python_executable or sys.executable
    command = _set_value_flag(command, "--output-dir", str(output_dir))
    if days is not None and days > 0:
        command = _set_value_flag(command, "--days", str(days))
    command = _remove_flag(command, "--no-lot-trace")
    if "--lot-trace" not in command:
        command.append("--lot-trace")
    if "--skip-map" not in command:
        command.append("--skip-map")
    if "--skip-plots" not in command:
        command.append("--skip-plots")
    return command


@dataclass
class ReplayJob:
    candidate: ScenarioCandidate
    output_dir: Path
    command: list[str]
    role: str
    rank: int | None = None
    score: float | None = None
    metric_details: dict[str, dict[str, Any]] | None = None


class TargetedReplayRunner:
    """Select and execute a nominal plus top-K scenario replay suite."""

    def __init__(
        self,
        *,
        catalog: ReplayCatalog,
        ranking: Iterable[RankedScenario],
        specs: Iterable[KpiSpec],
        output_dir: str | Path,
        top_k: int,
        days: int | None = None,
        python_executable: str | None = None,
    ) -> None:
        self.catalog = catalog
        self.ranking = list(ranking)
        self.specs = list(specs)
        self.output_dir = Path(output_dir).resolve()
        self.top_k = max(1, int(top_k))
        self.days = days
        self.python_executable = python_executable

    def jobs(self) -> list[ReplayJob]:
        jobs = [
            ReplayJob(
                candidate=self.catalog.baseline,
                output_dir=self.output_dir / "replays" / "baseline",
                command=build_replay_command(
                    self.catalog.baseline,
                    self.output_dir / "replays" / "baseline",
                    python_executable=self.python_executable,
                    days=self.days,
                ),
                role="baseline",
            )
        ]
        selected_count = 0
        for ranked in self.ranking:
            if ranked.score <= 0.0:
                continue
            if selected_count >= self.top_k:
                break
            output = self.output_dir / "replays" / f"{ranked.rank:03d}_{_slug(ranked.candidate.label)}"
            jobs.append(
                ReplayJob(
                    candidate=ranked.candidate,
                    output_dir=output,
                    command=build_replay_command(
                        ranked.candidate,
                        output,
                        python_executable=self.python_executable,
                        days=self.days,
                    ),
                    role="selected_scenario",
                    rank=ranked.rank,
                    score=ranked.score,
                    metric_details=ranked.metric_details,
                )
            )
            selected_count += 1
        return jobs

    def selection_manifest(self) -> dict[str, Any]:
        jobs = self.jobs()
        return {
            "schema_version": SCHEMA_VERSION,
            "manifest_kind": "selection",
            "generated_at_utc": _utc_now(),
            "source_run_dir": str(self.catalog.source_run_dir),
            "top_k": self.top_k,
            "selected_influential_scenario_count": max(0, len(jobs) - 1),
            "kpis": [spec.to_dict() for spec in self.specs],
            "ranking": [row.to_dict() for row in self.ranking],
            "selected_jobs": [
                {
                    "role": job.role,
                    "rank": job.rank,
                    "score": job.score,
                    "scenario_id": job.candidate.scenario_id,
                    "label": job.candidate.label,
                    "source_run_dir": str(job.candidate.source_run_dir),
                    "replay_output_dir": str(job.output_dir),
                    "command": job.command,
                }
                for job in jobs
            ],
        }

    def _execute_job(self, job: ReplayJob) -> dict[str, Any]:
        if job.output_dir.exists() and any(job.output_dir.iterdir()):
            raise FileExistsError(
                f"Replay output is not empty: {job.output_dir}. Use a new suite output directory."
            )
        job.output_dir.mkdir(parents=True, exist_ok=True)
        started = _utc_now()
        stdout_path = job.output_dir / "targeted_replay.stdout.log"
        stderr_path = job.output_dir / "targeted_replay.stderr.log"
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            completed = subprocess.run(
                job.command,
                cwd=REPO_ROOT,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                check=False,
            )
        stdout_tail = stdout_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        result: dict[str, Any] = {
            "role": job.role,
            "rank": job.rank,
            "selection_score": job.score,
            "scenario_id": job.candidate.scenario_id,
            "label": job.candidate.label,
            "source_run_dir": str(job.candidate.source_run_dir),
            "source_metrics": job.candidate.metrics,
            "replay_output_dir": str(job.output_dir),
            "command": job.command,
            "started_at_utc": started,
            "completed_at_utc": _utc_now(),
            "return_code": completed.returncode,
            "status": "completed" if completed.returncode == 0 else "failed",
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "selection_metric_details": job.metric_details or {},
        }
        if completed.returncode != 0:
            return result
        result["replay_metrics"] = extract_run_metrics(job.output_dir)
        result["lot_trace"] = lot_trace_evidence(job.output_dir)
        if not result["lot_trace"]["valid"]:
            result["status"] = "invalid_lot_trace"
        return result

    def _inspect_existing_job(self, job: ReplayJob) -> dict[str, Any]:
        if not job.output_dir.exists():
            return {
                "role": job.role,
                "rank": job.rank,
                "selection_score": job.score,
                "scenario_id": job.candidate.scenario_id,
                "label": job.candidate.label,
                "source_run_dir": str(job.candidate.source_run_dir),
                "replay_output_dir": str(job.output_dir),
                "command": job.command,
                "status": "missing_replay_output",
                "selection_metric_details": job.metric_details or {},
            }
        result: dict[str, Any] = {
            "role": job.role,
            "rank": job.rank,
            "selection_score": job.score,
            "scenario_id": job.candidate.scenario_id,
            "label": job.candidate.label,
            "source_run_dir": str(job.candidate.source_run_dir),
            "source_metrics": job.candidate.metrics,
            "replay_output_dir": str(job.output_dir),
            "command": job.command,
            "status": "completed",
            "result_source": "existing_replay_output",
            "inspected_at_utc": _utc_now(),
            "selection_metric_details": job.metric_details or {},
        }
        try:
            result["replay_metrics"] = extract_run_metrics(job.output_dir)
            result["lot_trace"] = lot_trace_evidence(job.output_dir)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            result["status"] = "invalid_replay_output"
            result["validation_error"] = str(exc)
            return result
        if not result["lot_trace"]["valid"]:
            result["status"] = "invalid_lot_trace"
        return result

    def _finalize_results(
        self,
        *,
        selection: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        baseline_result = next(
            (result for result in results if result.get("role") == "baseline"),
            None,
        )
        baseline_metrics = (baseline_result or {}).get("replay_metrics") or {}
        for result in results:
            replay_metrics = result.get("replay_metrics") or {}
            result["delta_vs_replayed_baseline"] = {
                name: (
                    replay_metrics[name] - baseline_metrics[name]
                    if replay_metrics.get(name) is not None and baseline_metrics.get(name) is not None
                    else None
                )
                for name in sorted(set(replay_metrics) | set(baseline_metrics))
            }
            if (
                result.get("role") == "selected_scenario"
                and result.get("status") == "completed"
                and baseline_result
                and baseline_result.get("status") == "completed"
            ):
                result["lot_delta_report"] = write_lot_delta_report(
                    baseline_run_dir=Path(str(baseline_result["replay_output_dir"])),
                    scenario_run_dir=Path(str(result["replay_output_dir"])),
                    scenario_id=str(result.get("scenario_id") or ""),
                    output_dir=self.output_dir / "reports",
                )

        completed = all(result.get("status") == "completed" for result in results)
        comparison = {
            **selection,
            "manifest_kind": "comparison",
            "generated_at_utc": _utc_now(),
            "execution_status": "completed" if completed else "failed",
            "replays": results,
        }
        _write_json(self.output_dir / "comparison_manifest.json", comparison)
        return comparison

    def run(self, *, execute: bool, reuse_existing: bool = False) -> dict[str, Any]:
        if execute and reuse_existing:
            raise ValueError("execute and reuse_existing are mutually exclusive")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        selection = self.selection_manifest()
        _write_json(self.output_dir / "selection_manifest.json", selection)
        if reuse_existing:
            return self._finalize_results(
                selection=selection,
                results=[self._inspect_existing_job(job) for job in self.jobs()],
            )
        if not execute:
            comparison = {
                **selection,
                "manifest_kind": "comparison",
                "execution_status": "planned",
                "replays": [],
            }
            _write_json(self.output_dir / "comparison_manifest.json", comparison)
            return comparison

        results: list[dict[str, Any]] = []
        for job in self.jobs():
            result = self._execute_job(job)
            results.append(result)
        return self._finalize_results(selection=selection, results=results)
