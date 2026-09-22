"""Bounded subprocess runner for HTTP; historical batch runner remains unchanged."""
from pathlib import Path
import subprocess
import sys
from typing import Any
from etudecas.simulation.analysis_batch_common import (
    load_json, merge_living_initial_state_args, resolve_existing_path, summary_path,
)


def run_simulation_bounded(
    run_script: Path,
    input_json: Path,
    output_dir: Path,
    scenario_id: str,
    days: int = 0,
    skip_map: bool = True,
    skip_plots: bool = True,
    extra_args: list[str] | None = None,
    use_living_initial_state: bool = True,
    *, timeout_seconds: float,
) -> tuple[dict[str, Any], str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(run_script),
        "--input",
        str(input_json),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        str(scenario_id),
    ]
    if days > 0:
        cmd.extend(["--days", str(days)])
    if skip_map:
        cmd.append("--skip-map")
    if skip_plots:
        cmd.append("--skip-plots")
    merged_extra_args = merge_living_initial_state_args(extra_args, enabled=use_living_initial_state)
    if merged_extra_args:
        cmd.extend(merged_extra_args)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        message = "\n".join([part for part in [stdout, stderr] if part]).strip()
        raise RuntimeError(f"Simulation failed for {input_json}:\n{message}")

    summary_file = resolve_existing_path(
        summary_path(output_dir, "first_simulation_summary.json"),
        output_dir / "first_simulation_summary.json",
    )
    summary = load_json(summary_file)
    return summary, proc.stdout
