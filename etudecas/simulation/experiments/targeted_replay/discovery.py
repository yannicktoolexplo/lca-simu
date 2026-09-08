"""Discovery of rerunnable scenarios from etudecas run manifests."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .metrics import extract_run_metrics, load_json
from .schema import ScenarioCandidate

REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_path(value: str | Path, *, base_dir: Path, repo_root: Path) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve()
    base_candidate = (base_dir / path).resolve()
    if base_candidate.exists():
        return base_candidate
    return (repo_root / path).resolve()


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_value(command: list[str], flag: str) -> str:
    for index, token in enumerate(command):
        if token.startswith(f"{flag}="):
            return token.split("=", 1)[1]
        if token == flag and index + 1 < len(command):
            return command[index + 1]
    return ""


def _candidate_from_run(
    run_dir: Path,
    *,
    label: str,
    role: str,
    repo_root: Path,
) -> ScenarioCandidate:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing rerun manifest: {manifest_path}")
    manifest = load_json(manifest_path)
    command = [str(value) for value in (manifest.get("simulator_command") or [])]
    if not command:
        raise ValueError(f"No simulator_command recorded in {manifest_path}")
    input_graph = _resolve_path(
        str(manifest.get("input_graph") or ""),
        base_dir=manifest_path.parent,
        repo_root=repo_root,
    )
    scenario_id = str(manifest.get("scenario_id") or "")
    command_scenario_id = _command_value(command, "--scenario-id")
    if command_scenario_id and command_scenario_id != scenario_id:
        raise ValueError(
            f"Scenario identity mismatch in {manifest_path}: "
            f"manifest={scenario_id!r}, command={command_scenario_id!r}"
        )
    return ScenarioCandidate(
        scenario_id=scenario_id,
        label=label,
        source_run_dir=run_dir.resolve(),
        source_manifest=manifest_path.resolve(),
        simulator_command=command,
        metrics=extract_run_metrics(run_dir),
        role=role,
        metadata={
            "input_graph": str(input_graph),
            "input_graph_sha256": _sha256(input_graph),
            "source_manifest_sha256": _sha256(manifest_path),
            "days": manifest.get("days"),
            "output_profile": manifest.get("output_profile"),
            "supplier_state_dependent_risks": manifest.get("supplier_state_dependent_risks"),
        },
    )


@dataclass(frozen=True)
class ReplayCatalog:
    source_run_dir: Path
    baseline: ScenarioCandidate
    candidates: tuple[ScenarioCandidate, ...]


def discover_replay_catalog(
    source_run_dir: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> ReplayCatalog:
    """Discover the nominal and companion scenario runs from one pipeline output."""

    source_dir = Path(source_run_dir).resolve()
    repo = Path(repo_root).resolve() if repo_root else REPO_ROOT
    root_manifest_path = source_dir / "run_manifest.json"
    if not root_manifest_path.exists():
        raise FileNotFoundError(f"Missing root run manifest: {root_manifest_path}")
    root_manifest = load_json(root_manifest_path)
    baseline = _candidate_from_run(
        source_dir,
        label=str(root_manifest.get("baseline") or "Nominal"),
        role="baseline",
        repo_root=repo,
    )

    companion_rows = root_manifest.get("companion_runs") or {}
    if not isinstance(companion_rows, dict):
        raise ValueError(f"companion_runs must be an object in {root_manifest_path}")
    candidates: list[ScenarioCandidate] = []
    seen_scenario_ids = {baseline.scenario_id}
    for key, raw in companion_rows.items():
        if not isinstance(raw, dict):
            continue
        output_value = str(raw.get("output_dir") or "")
        if not output_value:
            continue
        run_dir = _resolve_path(output_value, base_dir=source_dir, repo_root=repo)
        candidate = _candidate_from_run(
            run_dir,
            label=str(raw.get("label") or key),
            role=str(raw.get("role") or "candidate"),
            repo_root=repo,
        )
        expected_scenario_id = str(raw.get("scenario_id") or "")
        if expected_scenario_id and expected_scenario_id != candidate.scenario_id:
            raise ValueError(
                f"Companion scenario mismatch for {key}: "
                f"root={expected_scenario_id!r}, run={candidate.scenario_id!r}"
            )
        if candidate.scenario_id in seen_scenario_ids:
            raise ValueError(f"Duplicate scenario_id in replay catalog: {candidate.scenario_id}")
        seen_scenario_ids.add(candidate.scenario_id)
        baseline_days = baseline.metadata.get("days")
        candidate_days = candidate.metadata.get("days")
        if (
            baseline_days is not None
            and candidate_days is not None
            and int(baseline_days) != int(candidate_days)
        ):
            raise ValueError(
                f"Horizon mismatch for {candidate.scenario_id}: "
                f"baseline={baseline_days}, scenario={candidate_days}"
            )
        candidates.append(candidate)
    if not candidates:
        raise ValueError(f"No rerunnable companion scenario found in {root_manifest_path}")
    return ReplayCatalog(source_run_dir=source_dir, baseline=baseline, candidates=tuple(candidates))
