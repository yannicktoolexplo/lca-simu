"""HTTP compatibility entry point for the shared batch subprocess runner."""
from pathlib import Path
# Preserve the shared module attribute for callers patching subprocess.run here.
import subprocess
from typing import Any
from etudecas.simulation.analysis_batch_common import run_simulation


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
    return run_simulation(
        run_script, input_json, output_dir, scenario_id,
        days=days, skip_map=skip_map, skip_plots=skip_plots,
        extra_args=extra_args, use_living_initial_state=use_living_initial_state,
        timeout_seconds=timeout_seconds,
    )
