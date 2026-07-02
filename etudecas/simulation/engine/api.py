"""Programmatic simulation engine API.

This module is the stable boundary for callers that want to run the simulation
without knowing about the historical CLI script. The first implementation still
delegates to the existing engine entrypoint, but all inputs and outputs are
structured so the internals can later move to an in-memory engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from etudecas.simulation.analysis_batch_common import (
    apply_scales,
    load_json,
    numeric_kpis,
    run_simulation,
    safe_name,
    write_json,
)


SimulationOutputProfile = Literal["minimal", "diagnostic", "lot_trace", "full_debug"]


@dataclass(frozen=True)
class SimulationOverrides:
    """Structured parameter changes applied before a simulation run."""

    factors: dict[str, float] = field(default_factory=dict)
    demand_item_scale: dict[str, float] = field(default_factory=dict)
    capacity_node_scale: dict[str, float] = field(default_factory=dict)
    supplier_node_scale: dict[str, float] = field(default_factory=dict)
    supplier_capacity_node_scale: dict[str, float] = field(default_factory=dict)
    edge_src_lead_time_scale: dict[str, float] = field(default_factory=dict)
    edge_src_reliability_scale: dict[str, float] = field(default_factory=dict)
    scenario_flags: dict[str, bool] = field(default_factory=dict)
    engine_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulationRequest:
    """Complete request for one simulation run.

    Provide either `input_graph` or `input_path`. `output_dir` is optional; when
    omitted, a deterministic API run folder is created under
    `etudecas/simulation/result/_api_runs`.
    """

    input_graph: dict[str, Any] | None = None
    input_path: Path | str | None = None
    scenario_id: str = "scn:BASE"
    days: int = 0
    output_profile: SimulationOutputProfile = "diagnostic"
    overrides: SimulationOverrides = field(default_factory=SimulationOverrides)
    output_dir: Path | str | None = None
    run_id: str | None = None
    run_script: Path | str = Path("etudecas/simulation/run_first_simulation.py")
    skip_map: bool = True
    skip_plots: bool = True
    run_lot_audit: bool = False


@dataclass(frozen=True)
class SimulationResult:
    """Structured result returned by the simulation API."""

    run_id: str
    scenario_id: str
    output_dir: Path
    input_path: Path
    summary: dict[str, Any]
    kpis: dict[str, float]
    stdout: str
    output_profile: SimulationOutputProfile

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "output_dir": str(self.output_dir),
            "input_path": str(self.input_path),
            "summary": self.summary,
            "kpis": self.kpis,
            "output_profile": self.output_profile,
        }


def load_request_graph(request: SimulationRequest) -> dict[str, Any]:
    if request.input_graph is not None:
        return json.loads(json.dumps(request.input_graph))
    if request.input_path is None:
        raise ValueError("SimulationRequest requires either input_graph or input_path.")
    return load_json(Path(request.input_path))


def apply_scenario_flags(data: dict[str, Any], scenario_id: str, flags: dict[str, bool]) -> None:
    if not flags:
        return
    scenarios = data.get("scenarios") or []
    scenario = next((scn for scn in scenarios if str(scn.get("id")) == scenario_id), None)
    if scenario is None:
        scenario = scenarios[0] if scenarios else None
    if scenario is None:
        return
    economic_policy = scenario.get("economic_policy")
    if not isinstance(economic_policy, dict):
        economic_policy = {}
    for key, value in flags.items():
        economic_policy[str(key)] = bool(value)
    scenario["economic_policy"] = economic_policy


def apply_overrides(data: dict[str, Any], scenario_id: str, overrides: SimulationOverrides) -> dict[str, Any]:
    mutated = apply_scales(
        base_data=data,
        scenario_id=scenario_id,
        factors=overrides.factors,
        demand_item_scale=overrides.demand_item_scale,
        capacity_node_scale=overrides.capacity_node_scale,
        supplier_node_scale=overrides.supplier_node_scale,
        supplier_capacity_node_scale=overrides.supplier_capacity_node_scale,
        edge_src_lead_time_scale=overrides.edge_src_lead_time_scale,
        edge_src_reliability_scale=overrides.edge_src_reliability_scale,
    )
    apply_scenario_flags(mutated, scenario_id, overrides.scenario_flags)
    return mutated


def _float_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {str(k): float(v) for k, v in value.items()}


def _bool_mapping(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {str(k): bool(v) for k, v in value.items()}


def overrides_from_dict(payload: dict[str, Any] | None) -> SimulationOverrides:
    payload = payload or {}
    engine_args = payload.get("engine_args") or ()
    if isinstance(engine_args, str):
        engine_args = (engine_args,)
    return SimulationOverrides(
        factors=_float_mapping(payload.get("factors")),
        demand_item_scale=_float_mapping(payload.get("demand_item_scale")),
        capacity_node_scale=_float_mapping(payload.get("capacity_node_scale")),
        supplier_node_scale=_float_mapping(payload.get("supplier_node_scale")),
        supplier_capacity_node_scale=_float_mapping(payload.get("supplier_capacity_node_scale")),
        edge_src_lead_time_scale=_float_mapping(payload.get("edge_src_lead_time_scale")),
        edge_src_reliability_scale=_float_mapping(payload.get("edge_src_reliability_scale")),
        scenario_flags=_bool_mapping(payload.get("scenario_flags")),
        engine_args=tuple(str(arg) for arg in engine_args),
    )


def request_from_dict(payload: dict[str, Any]) -> SimulationRequest:
    return SimulationRequest(
        input_graph=payload.get("input_graph"),
        input_path=payload.get("input_path"),
        scenario_id=str(payload.get("scenario_id") or "scn:BASE"),
        days=int(payload.get("days") or 0),
        output_profile=payload.get("output_profile") or "diagnostic",
        overrides=overrides_from_dict(payload.get("overrides")),
        output_dir=payload.get("output_dir"),
        run_id=payload.get("run_id"),
        run_script=payload.get("run_script") or Path("etudecas/simulation/run_first_simulation.py"),
        skip_map=bool(payload.get("skip_map", True)),
        skip_plots=bool(payload.get("skip_plots", True)),
        run_lot_audit=bool(payload.get("run_lot_audit", False)),
    )


def default_run_id(scenario_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{safe_name(scenario_id)}_{uuid4().hex[:8]}"


def default_output_dir(run_id: str) -> Path:
    return Path("etudecas/simulation/result/_api_runs") / run_id


def profile_engine_args(profile: SimulationOutputProfile, *, run_lot_audit: bool) -> list[str]:
    if profile == "minimal":
        args = ["--output-profile", "compact", "--no-lot-trace", "--skip-lot-audit"]
    elif profile == "diagnostic":
        args = ["--output-profile", "compact", "--no-lot-trace", "--skip-lot-audit"]
    elif profile == "lot_trace":
        args = ["--output-profile", "compact", "--lot-trace"]
        if not run_lot_audit:
            args.append("--skip-lot-audit")
    elif profile == "full_debug":
        args = ["--output-profile", "full", "--lot-trace"]
        if not run_lot_audit:
            args.append("--skip-lot-audit")
    else:
        raise ValueError(f"Unsupported output profile: {profile}")
    return args


def simulate(request: SimulationRequest) -> SimulationResult:
    """Run one simulation from structured inputs and return structured outputs."""

    run_id = request.run_id or default_run_id(request.scenario_id)
    output_dir = Path(request.output_dir) if request.output_dir is not None else default_output_dir(run_id)
    input_path = output_dir / "inputs" / "simulation_input.json"

    base_graph = load_request_graph(request)
    graph = apply_overrides(base_graph, request.scenario_id, request.overrides)
    write_json(input_path, graph)

    extra_args = profile_engine_args(request.output_profile, run_lot_audit=request.run_lot_audit)
    extra_args.extend(str(arg) for arg in request.overrides.engine_args)

    summary, stdout = run_simulation(
        run_script=Path(request.run_script),
        input_json=input_path,
        output_dir=output_dir,
        scenario_id=request.scenario_id,
        days=request.days,
        skip_map=request.skip_map,
        skip_plots=request.skip_plots,
        extra_args=extra_args,
    )
    return SimulationResult(
        run_id=run_id,
        scenario_id=request.scenario_id,
        output_dir=output_dir,
        input_path=input_path,
        summary=summary,
        kpis=numeric_kpis(summary),
        stdout=stdout,
        output_profile=request.output_profile,
    )


__all__ = [
    "SimulationOutputProfile",
    "SimulationOverrides",
    "SimulationRequest",
    "SimulationResult",
    "apply_overrides",
    "overrides_from_dict",
    "request_from_dict",
    "simulate",
]
