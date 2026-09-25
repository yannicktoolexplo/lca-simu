"""Narrow request boundary for the local HTTP service, independent of HTTP I/O."""
from dataclasses import replace
import json
import math
from pathlib import Path
from uuid import uuid4

from etudecas.knowledge_graph.schema import validate_graph_contract
from .api import request_from_dict

REPO_ROOT = Path(__file__).resolve().parents[3]
ENGINE = REPO_ROOT / "etudecas/simulation/engine/run_first_simulation.py"
HTTP_FIELDS = frozenset({
    "input_graph", "input_path", "scenario_id", "days", "output_profile", "overrides",
    "run_lot_audit", "seed", "common_random_numbers", "control_schedule_csv",
    "control_policy_json", "demand_perturbation_csv",
    "skip_map", "skip_plots",
})


def confined_file(value, root: Path, suffix: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Input path must be a non-empty string")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix.lower() != suffix or not path.is_file():
        raise ValueError("Input file is outside the allowed root, missing, or has the wrong extension")
    return path


def reject_nonfinite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite JSON numbers are forbidden")
    if isinstance(value, dict):
        for child in value.values():
            reject_nonfinite(child)
    elif isinstance(value, list):
        for child in value:
            reject_nonfinite(child)


def request_from_http(payload, *, input_root: Path, output_root: Path, max_days: int = 3660):
    if not isinstance(payload, dict) or set(payload) - HTTP_FIELDS:
        raise ValueError("Unknown or forbidden HTTP request fields")
    clean = dict(payload)
    for name in ("skip_map", "skip_plots"):
        if name in clean and clean[name] is not True:
            raise ValueError(f"HTTP requires {name}=true")
    overrides = clean.get("overrides")
    if overrides is not None:
        if not isinstance(overrides, dict) or overrides.get("engine_args") not in (None, []):
            raise ValueError("HTTP engine_args are forbidden")
        clean["overrides"] = {k: v for k, v in overrides.items() if k != "engine_args"}
    request = request_from_dict(clean)
    if not 1 <= request.days <= max_days:
        raise ValueError(f"HTTP days must be between 1 and {max_days}")
    if request.control_schedule_csv and request.control_policy_json:
        raise ValueError("Choose schedule or feedback policy, not both")
    if request.input_path is not None:
        path = confined_file(request.input_path, input_root, ".json")
        graph = json.loads(path.read_text(encoding="utf-8"))
    else:
        graph = request.input_graph
    reject_nonfinite(graph)
    issues = [issue for issue in validate_graph_contract(graph) if issue["level"] == "error"]
    if issues:
        raise ValueError(f"Invalid input graph: {issues[:5]}")
    if not any(scenario.get("id") == request.scenario_id for scenario in graph["scenarios"]):
        raise ValueError("Requested scenario is absent from the graph")
    paths = {}
    for name, suffix in (("control_schedule_csv", ".csv"), ("demand_perturbation_csv", ".csv"), ("control_policy_json", ".json")):
        value = getattr(request, name)
        if value is not None:
            paths[name] = confined_file(value, input_root, suffix)
    run_id = "http_" + uuid4().hex
    output = (output_root.resolve() / run_id).resolve()
    if not output.is_relative_to(output_root.resolve()) or output.exists():
        raise ValueError("Invalid output directory")
    return replace(request, input_graph=graph, input_path=None, run_script=ENGINE,
                   run_id=run_id, output_dir=output, skip_map=True, skip_plots=True, **paths)
