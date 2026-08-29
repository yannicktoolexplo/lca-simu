#!/usr/bin/env python3
"""Local control-system audit for the RESILIENCE-SCAN V3 experiments.

The module deliberately separates two levels of evidence:

* exact algebraic properties of the configured V3 controller;
* an exploratory reduced DMDc fit on periodic actuator probes, including the
  post-feedback additive probes used by the V3 closed-loop campaign.

The actuator campaigns repeat one periodic waveform and have no independent
validation record.  Their fitted modes are therefore exported as rejected
candidates and are never presented as physical supply-chain poles.

Only NumPy, pandas and Matplotlib are required.  The source packages are read
only and the destination must be empty.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


SCHEMA_VERSION = "scan.canonical_control_system_analysis.v1"
CONTROLLER_SCHEMA_VERSION = "scan.canonical_state_feedback.v3"
ACTUATOR_INPUTS = (
    "order_multiplier",
    "safety_stock_multiplier",
    "production_target_multiplier",
)
PHYSICAL_CANDIDATE_MODEL = "actuator_probe_dmdc_candidate"
PHYSICAL_STATE_NAMES = (
    "target_finished_stock_qty",
    "factory_component_stock_qty",
    "supplier_component_stock_qty",
    "lane_pipeline_qty",
)
FIGURE_FILENAMES = (
    "canonical_control_system_operating_point.png",
    "canonical_control_system_actuator_space_rank.png",
    "canonical_control_system_input_rank.png",
    "canonical_control_system_pole_map.png",
    "canonical_control_system_controllability_observability.png",
    "canonical_control_system_free_run_validation.png",
    "canonical_control_system_impulse_response.png",
    "canonical_control_system_bode.png",
    "canonical_control_system_nyquist_deadzone.png",
    "canonical_control_system_probe_composition.png",
    "canonical_control_system_physical_state_response.png",
)


class ControlSystemAnalysisError(ValueError):
    """Raised when an input package cannot support an auditable analysis."""


@dataclass(frozen=True)
class IdentificationSequence:
    """One contiguous state trajectory and its transition-aligned inputs."""

    name: str
    states: np.ndarray
    transition_inputs: np.ndarray


@dataclass
class ReducedDMDcResult:
    """Numerical result and explicit scientific acceptance status."""

    available: bool
    accepted: bool
    rejection_reasons: list[str]
    state_names: list[str]
    active_state_names: list[str]
    input_names: list[str]
    selected_order: int = 0
    state_scale: np.ndarray = field(default_factory=lambda: np.empty(0))
    input_scale: np.ndarray = field(default_factory=lambda: np.empty(0))
    basis: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    a_matrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    b_matrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    c_matrix: np.ndarray = field(default_factory=lambda: np.empty((0, 0)))
    poles: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=complex))
    controllability_singular_values: np.ndarray = field(
        default_factory=lambda: np.empty(0)
    )
    observability_singular_values: np.ndarray = field(
        default_factory=lambda: np.empty(0)
    )
    candidate_metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    validation_metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    predictions: pd.DataFrame = field(default_factory=pd.DataFrame)
    regressor_condition_number: float | None = None
    snapshot_singular_values: np.ndarray = field(default_factory=lambda: np.empty(0))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.floating, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, Path):
        return str(value)
    return value


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ControlSystemAnalysisError(f"{label} must contain a JSON object: {path}")
    return payload


def _prepare_output_dir(destination: Path, sources: Iterable[Path]) -> None:
    resolved = destination.resolve()
    for source in sources:
        source_resolved = source.resolve()
        if resolved == source_resolved or source_resolved in resolved.parents:
            raise ControlSystemAnalysisError(
                "output_dir must be outside the immutable scientific source packages."
            )
    if resolved.exists() and any(resolved.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)


def _numerical_rank(
    singular_values: Sequence[float] | np.ndarray,
    *,
    relative_tolerance: float = 1e-8,
) -> int:
    values = np.asarray(singular_values, dtype=float)
    if values.size == 0 or not np.isfinite(values).all() or values[0] <= 0.0:
        return 0
    return int(np.count_nonzero(values > values[0] * float(relative_tolerance)))


def hankel_singular_values(signal: Sequence[float], *, lags: int = 40) -> np.ndarray:
    """Return singular values of a scalar delay-embedding matrix."""

    values = np.asarray(signal, dtype=float)
    if values.ndim != 1 or len(values) < 4:
        raise ControlSystemAnalysisError("Hankel input signal must contain at least 4 samples.")
    if not np.isfinite(values).all():
        raise ControlSystemAnalysisError("Hankel input signal contains non-finite values.")
    width = min(max(2, int(lags)), len(values) // 2)
    matrix = np.stack(
        [values[offset : len(values) - width + offset + 1] for offset in range(width)]
    )
    return np.linalg.svd(matrix, compute_uv=False)


def controllability_matrix(a_matrix: np.ndarray, b_matrix: np.ndarray) -> np.ndarray:
    """Return the finite n-step controllability matrix."""

    a = np.asarray(a_matrix, dtype=float)
    b = np.asarray(b_matrix, dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or b.ndim != 2 or b.shape[0] != a.shape[0]:
        raise ControlSystemAnalysisError("Incompatible A/B dimensions for controllability.")
    blocks: list[np.ndarray] = []
    power = np.eye(a.shape[0])
    for _ in range(a.shape[0]):
        blocks.append(power @ b)
        power = power @ a
    return np.hstack(blocks)


def observability_matrix(a_matrix: np.ndarray, c_matrix: np.ndarray) -> np.ndarray:
    """Return the finite n-step observability matrix."""

    a = np.asarray(a_matrix, dtype=float)
    c = np.asarray(c_matrix, dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or c.ndim != 2 or c.shape[1] != a.shape[0]:
        raise ControlSystemAnalysisError("Incompatible A/C dimensions for observability.")
    blocks: list[np.ndarray] = []
    power = np.eye(a.shape[0])
    for _ in range(a.shape[0]):
        blocks.append(c @ power)
        power = power @ a
    return np.vstack(blocks)


def _validate_sequences(
    sequences: Sequence[IdentificationSequence],
    *,
    state_count: int,
    input_count: int,
    label: str,
) -> None:
    if not sequences:
        raise ControlSystemAnalysisError(f"{label} sequences must be non-empty.")
    for sequence in sequences:
        states = np.asarray(sequence.states, dtype=float)
        inputs = np.asarray(sequence.transition_inputs, dtype=float)
        if states.ndim != 2 or states.shape[1] != state_count or len(states) < 3:
            raise ControlSystemAnalysisError(
                f"{label} sequence {sequence.name!r} has invalid state dimensions."
            )
        if inputs.shape != (len(states) - 1, input_count):
            raise ControlSystemAnalysisError(
                f"{label} sequence {sequence.name!r} inputs must align with state transitions."
            )
        if not np.isfinite(states).all() or not np.isfinite(inputs).all():
            raise ControlSystemAnalysisError(
                f"{label} sequence {sequence.name!r} contains non-finite values."
            )


def _empty_dmdc(
    *,
    state_names: Sequence[str],
    input_names: Sequence[str],
    reasons: Sequence[str],
) -> ReducedDMDcResult:
    return ReducedDMDcResult(
        available=False,
        accepted=False,
        rejection_reasons=list(dict.fromkeys(str(reason) for reason in reasons)),
        state_names=list(state_names),
        active_state_names=[],
        input_names=list(input_names),
    )


def fit_reduced_dmdc(
    train_sequences: Sequence[IdentificationSequence],
    validation_sequences: Sequence[IdentificationSequence],
    *,
    state_names: Sequence[str],
    input_names: Sequence[str],
    candidate_orders: Sequence[int] | None = None,
    independent_validation: bool,
    maximum_free_run_nrmse: float = 0.5,
    maximum_one_step_nrmse: float = 0.5,
) -> ReducedDMDcResult:
    """Fit a reduced DMDc model and apply conservative acceptance criteria.

    States are paired physical deviations, so zero remains the physical
    reference and no affine intercept is fitted.  The POD basis and all scales
    are learned from estimation records only.
    """

    names = list(state_names)
    inputs = list(input_names)
    _validate_sequences(
        train_sequences, state_count=len(names), input_count=len(inputs), label="training"
    )
    _validate_sequences(
        validation_sequences,
        state_count=len(names),
        input_count=len(inputs),
        label="validation",
    )
    train_states = np.vstack([sequence.states for sequence in train_sequences])
    state_scale_full = np.std(train_states, axis=0)
    state_peak = np.max(np.abs(train_states), axis=0)
    active = (state_scale_full > 1e-12) | (state_peak > 1e-10)
    if not bool(np.any(active)):
        return _empty_dmdc(
            state_names=names,
            input_names=inputs,
            reasons=["no_nonzero_physical_state_response", "physical_actuator_dead_zone"],
        )
    active_names = [name for name, keep in zip(names, active, strict=True) if keep]
    state_scale = state_scale_full[active]
    fallback_scale = np.maximum(state_peak[active], 1.0)
    state_scale = np.where(state_scale > 1e-12, state_scale, fallback_scale)

    train_inputs = np.vstack([sequence.transition_inputs for sequence in train_sequences])
    input_scale = np.std(train_inputs, axis=0)
    dead_inputs = [
        name for name, scale in zip(inputs, input_scale, strict=True) if scale <= 1e-12
    ]
    input_scale = np.where(input_scale > 1e-12, input_scale, 1.0)

    def normalized_pairs(
        sequence_group: Sequence[IdentificationSequence],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        left: list[np.ndarray] = []
        right: list[np.ndarray] = []
        commands: list[np.ndarray] = []
        for sequence in sequence_group:
            scaled = sequence.states[:, active] / state_scale
            left.append(scaled[:-1])
            right.append(scaled[1:])
            commands.append(sequence.transition_inputs / input_scale)
        return np.vstack(left), np.vstack(right), np.vstack(commands)

    x0, x1, u0 = normalized_pairs(train_sequences)
    snapshot = np.vstack([x0, x1])
    _, snapshot_singular, vt = np.linalg.svd(snapshot, full_matrices=False)
    snapshot_rank = _numerical_rank(snapshot_singular)
    maximum_order = min(len(active_names), max(1, snapshot_rank))
    if candidate_orders is None:
        orders = list(range(1, maximum_order + 1))
    else:
        orders = sorted(
            {
                int(order)
                for order in candidate_orders
                if 1 <= int(order) <= maximum_order
            }
        )
    if not orders:
        return _empty_dmdc(
            state_names=names,
            input_names=inputs,
            reasons=["no_admissible_reduced_order"],
        )

    basis_full = vt.T
    candidate_rows: list[dict[str, Any]] = []
    fitted: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float]] = {}
    for order in orders:
        basis = basis_full[:, :order]
        q0 = x0 @ basis
        q1 = x1 @ basis
        regressor = np.hstack([q0, u0])
        singular = np.linalg.svd(regressor, compute_uv=False)
        condition = float(singular[0] / singular[-1]) if singular[-1] > 1e-15 else math.inf
        theta = np.linalg.lstsq(regressor, q1, rcond=1e-10)[0].T
        a_matrix = theta[:, :order]
        b_matrix = theta[:, order:]
        one_errors: list[np.ndarray] = []
        free_errors: list[np.ndarray] = []
        for sequence in validation_sequences:
            scaled = sequence.states[:, active] / state_scale
            commands = sequence.transition_inputs / input_scale
            true_q = scaled @ basis
            one_q = (a_matrix @ true_q[:-1].T + b_matrix @ commands.T).T
            one_states = one_q @ basis.T
            one_errors.append(one_states - scaled[1:])
            q = true_q[0].copy()
            predictions: list[np.ndarray] = []
            for command in commands:
                q = a_matrix @ q + b_matrix @ command
                predictions.append(q @ basis.T)
            free_errors.append(np.asarray(predictions) - scaled[1:])
        one_nrmse = float(np.sqrt(np.mean(np.vstack(one_errors) ** 2)))
        free_nrmse = float(np.sqrt(np.mean(np.vstack(free_errors) ** 2)))
        poles = np.linalg.eigvals(a_matrix)
        spectral_radius = float(np.max(np.abs(poles)))
        candidate_rows.append(
            {
                "order": order,
                "one_step_nrmse": one_nrmse,
                "free_run_nrmse": free_nrmse,
                "spectral_radius": spectral_radius,
                "regressor_condition_number": condition,
                "snapshot_rank": snapshot_rank,
            }
        )
        fitted[order] = (
            basis,
            a_matrix,
            b_matrix,
            one_nrmse,
            free_nrmse,
            condition,
        )

    candidates = pd.DataFrame(candidate_rows).sort_values(
        ["free_run_nrmse", "order"], kind="stable"
    )
    selected_order = int(candidates.iloc[0]["order"])
    basis, a_matrix, b_matrix, one_nrmse, free_nrmse, condition = fitted[selected_order]
    c_matrix = basis.copy()
    poles = np.linalg.eigvals(a_matrix)
    ctrb_singular = np.linalg.svd(
        controllability_matrix(a_matrix, b_matrix), compute_uv=False
    )
    obsv_singular = np.linalg.svd(
        observability_matrix(a_matrix, c_matrix), compute_uv=False
    )
    ctrb_rank = _numerical_rank(ctrb_singular)
    obsv_rank = _numerical_rank(obsv_singular)

    prediction_rows: list[dict[str, Any]] = []
    error_by_state: dict[str, list[float]] = {name: [] for name in active_names}
    true_by_state: dict[str, list[float]] = {name: [] for name in active_names}
    for sequence in validation_sequences:
        scaled = sequence.states[:, active] / state_scale
        commands = sequence.transition_inputs / input_scale
        true_q = scaled @ basis
        q = true_q[0].copy()
        for step, command in enumerate(commands, start=1):
            q = a_matrix @ q + b_matrix @ command
            predicted_scaled = q @ basis.T
            true_scaled = scaled[step]
            for state_index, state_name in enumerate(active_names):
                predicted = float(predicted_scaled[state_index] * state_scale[state_index])
                measured = float(true_scaled[state_index] * state_scale[state_index])
                prediction_rows.append(
                    {
                        "sequence": sequence.name,
                        "validation_step": step,
                        "state": state_name,
                        "measured_delta": measured,
                        "free_run_predicted_delta": predicted,
                    }
                )
                error_by_state[state_name].append(predicted - measured)
                true_by_state[state_name].append(measured)
    validation_rows: list[dict[str, Any]] = []
    for state_name, scale in zip(active_names, state_scale, strict=True):
        errors = np.asarray(error_by_state[state_name], dtype=float)
        measured = np.asarray(true_by_state[state_name], dtype=float)
        validation_rows.append(
            {
                "metric_scope": "state_free_run",
                "state": state_name,
                "rmse": float(np.sqrt(np.mean(errors**2))),
                "nrmse_training_scale": float(np.sqrt(np.mean((errors / scale) ** 2))),
                "measured_standard_deviation": float(np.std(measured)),
            }
        )
    validation_rows.extend(
        [
            {
                "metric_scope": "model",
                "state": "all",
                "metric": "one_step_nrmse",
                "value": one_nrmse,
            },
            {
                "metric_scope": "model",
                "state": "all",
                "metric": "free_run_nrmse",
                "value": free_nrmse,
            },
        ]
    )

    reasons: list[str] = []
    if dead_inputs:
        reasons.append("unexcited_inputs:" + ",".join(dead_inputs))
    for input_index, input_name in enumerate(inputs):
        responsive = False
        for sequence in train_sequences:
            if np.max(np.abs(sequence.transition_inputs[:, input_index])) <= 1e-12:
                continue
            if np.max(np.abs(sequence.states[:, active])) > 1e-9:
                responsive = True
        if not responsive:
            reasons.append(f"physical_dead_zone_for_input:{input_name}")
    if not independent_validation:
        reasons.append("validation_repeats_the_same_periodic_phase")
    if one_nrmse > maximum_one_step_nrmse:
        reasons.append("one_step_prediction_error_too_large")
    if free_nrmse > maximum_free_run_nrmse:
        reasons.append("free_run_prediction_error_too_large")
    if not np.isfinite(condition) or condition > 1e8:
        reasons.append("ill_conditioned_identification_regressor")
    if float(np.max(np.abs(poles))) >= 1.0:
        reasons.append("candidate_model_not_asymptotically_stable")
    if ctrb_rank < selected_order:
        reasons.append("candidate_model_not_numerically_controllable")
    if obsv_rank < selected_order:
        reasons.append("candidate_model_not_numerically_observable")

    return ReducedDMDcResult(
        available=True,
        accepted=not reasons,
        rejection_reasons=list(dict.fromkeys(reasons)),
        state_names=names,
        active_state_names=active_names,
        input_names=inputs,
        selected_order=selected_order,
        state_scale=state_scale,
        input_scale=input_scale,
        basis=basis,
        a_matrix=a_matrix,
        b_matrix=b_matrix,
        c_matrix=c_matrix,
        poles=poles,
        controllability_singular_values=ctrb_singular,
        observability_singular_values=obsv_singular,
        candidate_metrics=pd.DataFrame(candidate_rows),
        validation_metrics=pd.DataFrame(validation_rows),
        predictions=pd.DataFrame(prediction_rows),
        regressor_condition_number=condition,
        snapshot_singular_values=snapshot_singular,
    )


def siso_state_space_zeros(
    a_matrix: np.ndarray,
    b_vector: np.ndarray,
    c_vector: np.ndarray,
    *,
    direct_term: float = 0.0,
    tolerance: float = 1e-8,
) -> np.ndarray:
    """Compute finite SISO zeros by polynomial interpolation using NumPy only."""

    a = np.asarray(a_matrix, dtype=float)
    b = np.asarray(b_vector, dtype=float).reshape(-1, 1)
    c = np.asarray(c_vector, dtype=float).reshape(1, -1)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or b.shape[0] != len(a) or c.shape[1] != len(a):
        raise ControlSystemAnalysisError("Incompatible state-space dimensions for zeros.")
    order = len(a)
    sample_count = order + 1
    angles = 2.0 * math.pi * (np.arange(sample_count) + 0.37) / sample_count
    points = 1.7 * np.exp(1j * angles)
    values: list[complex] = []
    eye = np.eye(order)
    for point in points:
        denominator = np.linalg.det(point * eye - a)
        transfer = complex((c @ np.linalg.solve(point * eye - a, b))[0, 0]) + float(
            direct_term
        )
        values.append(denominator * transfer)
    vandermonde = np.vander(points, N=sample_count, increasing=False)
    coefficients = np.linalg.solve(vandermonde, np.asarray(values, dtype=complex))
    coefficients = np.real_if_close(coefficients, tol=1000)
    threshold = max(float(np.max(np.abs(coefficients))) * tolerance, tolerance)
    first = 0
    while first < len(coefficients) and abs(coefficients[first]) <= threshold:
        first += 1
    if first >= len(coefficients) - 1:
        return np.empty(0, dtype=complex)
    return np.roots(coefficients[first:])


def _resolve_controller_config(v3_root: Path, protocol: Mapping[str, Any]) -> Path:
    controller = protocol.get("controller")
    if not isinstance(controller, Mapping):
        raise ControlSystemAnalysisError("V3 protocol does not describe its controller.")
    schema = str(controller.get("schema_version") or "")
    if schema != CONTROLLER_SCHEMA_VERSION:
        raise ControlSystemAnalysisError(
            f"Expected controller schema {CONTROLLER_SCHEMA_VERSION!r}, got {schema!r}."
        )
    relative = str(controller.get("snapshot_relative_path") or "")
    candidates = [
        v3_root / relative if relative else Path("__missing__"),
        Path(str(controller.get("snapshot_path") or "__missing__")),
        Path(str(controller.get("path") or "__missing__")),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Cannot resolve the V3 controller configuration snapshot.")


def _select_v3_trajectory(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "condition",
        "policy",
        "experiment_input_signal",
        "day",
        "period_index",
        "excitation_fraction__demand_multiplier",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ControlSystemAnalysisError(
            "V3 trajectories are missing columns: " + ", ".join(missing)
        )
    selected = frame.loc[
        frame["condition"].astype(str).str.contains("supplier_stress")
        & frame["policy"].astype(str).str.contains("feedback")
        & frame["experiment_input_signal"].astype(str).eq("demand_multiplier")
    ].copy()
    if selected.empty:
        selected = frame.loc[
            frame["policy"].astype(str).str.contains("feedback")
            & frame["experiment_input_signal"].astype(str).eq("demand_multiplier")
        ].copy()
    if selected.empty:
        raise ControlSystemAnalysisError("No V3 feedback demand trajectory was found.")
    return selected.sort_values("day").drop_duplicates("day", keep="first")


def _find_v3_decisions(v3_root: Path) -> pd.DataFrame:
    candidates = sorted(
        v3_root.glob(
            "runs/supplier_stress_capacity/excited/demand_multiplier/"
            "canonical_feedback/seed_*/data/canonical_closed_loop_decisions.csv"
        )
    )
    if not candidates:
        candidates = sorted(v3_root.rglob("canonical_closed_loop_decisions.csv"))
    for candidate in candidates:
        frame = pd.read_csv(candidate)
        required = {
            "decision_day",
            "control_continuous_requested_order_multiplier",
            "control_continuous_requested_production_target_multiplier",
        }
        if required.issubset(frame.columns):
            return frame
    raise FileNotFoundError("No V3 continuous-decision ledger was found.")


def _controller_and_v3_evidence(
    v3_root: Path,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    protocol_path = v3_root / "canonical_frequency_protocol.json"
    protocol = _read_json(protocol_path, "V3 frequency protocol")
    controller_path = _resolve_controller_config(v3_root, protocol)
    config = _read_json(controller_path, "V3 controller configuration")
    dynamics = config.get("dynamics")
    relief = config.get("continuous_relief")
    if not isinstance(dynamics, Mapping) or not isinstance(relief, Mapping):
        raise ControlSystemAnalysisError("V3 configuration lacks dynamics/continuous_relief.")
    memory = float(dynamics["stress_memory"])
    if not 0.0 < memory < 1.0:
        raise ControlSystemAnalysisError("V3 stress memory must define a stable scalar pole.")
    span = float(relief["stress_span"])
    order_gain = -float(relief["order_relief_gain"]) / span
    production_gain = -float(relief["production_relief_gain"]) / span
    input_gains = np.asarray(
        [
            float(dynamics["nervousness_gain"]),
            float(dynamics["pressure_gain"]),
            float(dynamics["disruption_gain"]),
        ],
        dtype=float,
    )
    output_gains = np.asarray([order_gain, production_gain], dtype=float)
    controller_wc = float(np.sum(input_gains**2) / (1.0 - memory**2))
    controller_wo = float(np.sum(output_gains**2) / (1.0 - memory**2))

    trajectory_path = v3_root / "canonical_frequency_trajectories.csv"
    trajectory = _select_v3_trajectory(pd.read_csv(trajectory_path))
    demand = trajectory["excitation_fraction__demand_multiplier"].to_numpy(dtype=float)
    demand_singular = hankel_singular_values(demand, lags=40)
    demand_rank = _numerical_rank(demand_singular, relative_tolerance=1e-10)

    decisions = _find_v3_decisions(v3_root)
    retained_start = int(trajectory.loc[trajectory["period_index"] >= 1, "day"].min())
    decisions = decisions.loc[
        pd.to_numeric(decisions["decision_day"], errors="coerce") >= retained_start
    ].copy()
    actions = np.column_stack(
        [
            pd.to_numeric(
                decisions["control_continuous_requested_order_multiplier"],
                errors="coerce",
            ).to_numpy(dtype=float)
            - 1.0,
            pd.to_numeric(
                decisions["control_continuous_requested_production_target_multiplier"],
                errors="coerce",
            ).to_numpy(dtype=float)
            - 1.0,
        ]
    )
    actions = actions[np.isfinite(actions).all(axis=1)]
    if not len(actions):
        raise ControlSystemAnalysisError("V3 decision ledger has no finite continuous actions.")
    action_singular = np.linalg.svd(actions, compute_uv=False)
    action_rank = _numerical_rank(action_singular)

    operating_rows: list[dict[str, Any]] = []
    baseline_columns = [
        "baseline__global_inventory_qty",
        "baseline__global_order_qty",
        "baseline__target_finished_stock_qty",
        "baseline__control_order_multiplier",
        "baseline__control_production_target_multiplier",
    ]
    for column in baseline_columns:
        if column not in trajectory.columns:
            continue
        values = pd.to_numeric(trajectory[column], errors="coerce")
        period_means = values.groupby(trajectory["period_index"]).mean()
        retained = period_means.loc[period_means.index >= 1]
        scale = max(float(np.mean(np.abs(retained))), 1e-12) if len(retained) else 1.0
        drift = (
            float(np.max(np.abs(np.diff(retained.to_numpy(dtype=float))))) / scale
            if len(retained) >= 2
            else math.nan
        )
        for period_index, mean in period_means.items():
            operating_rows.append(
                {
                    "signal": column.removeprefix("baseline__"),
                    "period_index": int(period_index),
                    "period_mean": float(mean),
                    "maximum_adjacent_relative_drift": drift,
                    "stationary_under_5_percent_rule": bool(
                        math.isfinite(drift) and drift <= 0.05
                    ),
                }
            )
    operating = pd.DataFrame(operating_rows)

    dead_rows: list[dict[str, Any]] = []
    for column in sorted(name for name in trajectory.columns if name.startswith("delta__")):
        values = pd.to_numeric(trajectory[column], errors="coerce").fillna(0.0).to_numpy()
        retained_values = values[trajectory["period_index"].to_numpy(dtype=int) >= 1]
        maximum = float(np.max(np.abs(retained_values))) if len(retained_values) else 0.0
        standard_deviation = float(np.std(retained_values)) if len(retained_values) else 0.0
        dead_rows.append(
            {
                "source_campaign": "v3_demand_pilot",
                "input": "demand_multiplier",
                "output": column.removeprefix("delta__"),
                "maximum_absolute_paired_response": maximum,
                "paired_response_standard_deviation": standard_deviation,
                "exact_dead_zone": bool(maximum <= 1e-12),
            }
        )
    dead_zones = pd.DataFrame(dead_rows)

    evidence = {
        "protocol_path": protocol_path,
        "controller_config_path": controller_path,
        "controller_config_sha256": _sha256(controller_path),
        "stress_memory_pole": memory,
        "time_constant_days": -1.0 / math.log(memory),
        "half_life_days": math.log(2.0) / -math.log(memory),
        "local_order_gain_per_stress": order_gain,
        "local_production_gain_per_stress": production_gain,
        "controller_input_gains": input_gains,
        "controller_output_gains": output_gains,
        "controller_controllability_gramian": controller_wc,
        "controller_observability_gramian": controller_wo,
        "controller_controllability_rank": 1,
        "controller_observability_rank": 1,
        "demand_hankel_singular_values": demand_singular,
        "demand_hankel_rank": demand_rank,
        "action_singular_values": action_singular,
        "action_rank": action_rank,
        "action_rows": actions,
        "trajectory": trajectory,
        "physical_operating_point_stationary": bool(
            not operating.empty
            and operating.groupby("signal")["stationary_under_5_percent_rule"].first().all()
        ),
    }
    return evidence, operating, dead_zones, trajectory, decisions


def _find_single_directory(pattern: Iterable[Path], label: str) -> Path:
    directories = sorted(path.resolve() for path in pattern if path.is_dir())
    if len(directories) != 1:
        raise ControlSystemAnalysisError(
            f"Expected exactly one {label}, found {len(directories)}."
        )
    return directories[0]


def _daily_filtered_series(
    path: Path,
    *,
    days: int,
    filters: Mapping[str, str],
    value_column: str,
) -> np.ndarray:
    frame = pd.read_csv(path)
    required = {"day", value_column, *filters}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ControlSystemAnalysisError(
            f"{path.name} lacks columns: {', '.join(missing)}"
        )
    selected = frame.copy()
    for column, expected in filters.items():
        selected = selected.loc[selected[column].astype(str).eq(str(expected))]
    values = pd.to_numeric(selected[value_column], errors="coerce")
    grouped = values.groupby(pd.to_numeric(selected["day"], errors="coerce")).sum()
    return grouped.reindex(range(days), fill_value=0.0).to_numpy(dtype=float)


def _lane_pipeline_series(
    path: Path,
    *,
    days: int,
    supplier_id: str,
    item_id: str,
    destination_id: str,
) -> np.ndarray:
    frame = pd.read_csv(path)
    required = {
        "day",
        "item_id",
        "src_node_id",
        "dst_node_id",
        "release_day",
        "arrival_day",
        "planned_receipt_qty",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ControlSystemAnalysisError(
            f"{path.name} lacks pipeline columns: {', '.join(missing)}"
        )
    selected = frame.loc[
        frame["item_id"].astype(str).eq(item_id)
        & frame["src_node_id"].astype(str).eq(supplier_id)
        & frame["dst_node_id"].astype(str).eq(destination_id)
    ].copy()
    pipeline = np.zeros(days, dtype=float)
    for row in selected.itertuples(index=False):
        start_raw = getattr(row, "release_day", getattr(row, "day"))
        end_raw = getattr(row, "actual_receipt_day", math.nan)
        if pd.isna(end_raw):
            end_raw = getattr(row, "arrival_day")
        quantity = float(getattr(row, "planned_receipt_qty"))
        if not math.isfinite(quantity):
            continue
        start = max(0, int(float(start_raw)))
        end = min(days, int(float(end_raw)))
        if end > start:
            pipeline[start:end] += quantity
    return pipeline


def _physical_state_frame(
    data_dir: Path,
    *,
    days: int,
    probe: Mapping[str, Any],
) -> pd.DataFrame:
    supplier = str(probe["supplier_id"])
    component = str(probe["item_id"])
    destination = str(probe["dst_node_id"])
    finished = str(probe["target_finished_item_id"])
    return pd.DataFrame(
        {
            "day": np.arange(days, dtype=int),
            "target_finished_stock_qty": _daily_filtered_series(
                data_dir / "production_output_products_daily.csv",
                days=days,
                filters={"node_id": destination, "item_id": finished},
                value_column="stock_end_of_day",
            ),
            "factory_component_stock_qty": _daily_filtered_series(
                data_dir / "production_input_stocks_daily.csv",
                days=days,
                filters={"node_id": destination, "item_id": component},
                value_column="stock_end_of_day",
            ),
            "supplier_component_stock_qty": _daily_filtered_series(
                data_dir / "production_supplier_stocks_daily.csv",
                days=days,
                filters={"node_id": supplier, "item_id": component},
                value_column="stock_end_of_day",
            ),
            "lane_pipeline_qty": _lane_pipeline_series(
                data_dir / "mrp_orders_daily.csv",
                days=days,
                supplier_id=supplier,
                item_id=component,
                destination_id=destination,
            ),
        }
    )


def _load_actuator_sequences(
    actuator_root: Path,
) -> tuple[
    list[IdentificationSequence],
    list[IdentificationSequence],
    dict[str, Any],
    pd.DataFrame,
]:
    protocol = _read_json(
        actuator_root / "canonical_frequency_protocol.json", "actuator frequency protocol"
    )
    actuator = protocol.get("actuator_probe")
    if not isinstance(actuator, Mapping) or actuator.get("enabled") is not True:
        raise ControlSystemAnalysisError("The actuator package has no enabled actuator probe.")
    probe = protocol.get("supplier_probe")
    if not isinstance(probe, Mapping):
        raise ControlSystemAnalysisError("The actuator protocol lacks supplier_probe metadata.")
    sampling = protocol.get("sampling") if isinstance(protocol.get("sampling"), Mapping) else {}
    days = int(protocol.get("measured_days") or sampling.get("measured_days") or 0)
    period = int(sampling.get("designed_period_days") or 0)
    if days <= 0 or period <= 0 or days < 4 * period:
        raise ControlSystemAnalysisError("Actuator package must contain four complete periods.")
    application_mode = str(actuator.get("application_mode") or "open_loop_schedule")
    closed_loop_probe = application_mode == "post_feedback_additive"
    if closed_loop_probe:
        baseline_condition = str(
            actuator.get("baseline_condition") or "supplier_stress_capacity"
        )
        baseline_policy = str(actuator.get("baseline_policy") or "canonical_feedback")
        boundary_reference = str(actuator.get("boundary_reference_run") or "")
        boundary_candidate = Path(boundary_reference).resolve() if boundary_reference else None
        if boundary_candidate is not None and boundary_candidate.is_dir():
            baseline_dir = boundary_candidate
        else:
            baseline_dir = _find_single_directory(
                actuator_root.glob(
                    f"runs/{baseline_condition}/baseline/{baseline_policy}/seed_*"
                ),
                "closed-loop actuator baseline run",
            )
        source_campaign = "closed_loop_post_feedback_additive_actuator_probe"
    else:
        baseline_condition = "nominal_capacity"
        baseline_policy = "mrp_reference"
        baseline_dir = _find_single_directory(
            actuator_root.glob("runs/nominal_capacity/baseline/mrp_reference/seed_*"),
            "MRP actuator baseline run",
        )
        source_campaign = "historical_mrp_actuator_probe"
    baseline = _physical_state_frame(baseline_dir / "data", days=days, probe=probe)
    trajectories = pd.read_csv(actuator_root / "canonical_frequency_trajectories.csv")

    train_sequences: list[IdentificationSequence] = []
    validation_sequences: list[IdentificationSequence] = []
    state_rows: list[dict[str, Any]] = []
    input_blocks: list[np.ndarray] = []
    state_response_by_input: dict[str, np.ndarray] = {}
    excited_dirs: dict[str, Path] = {}
    for input_index, input_name in enumerate(ACTUATOR_INPUTS):
        experiments = actuator.get("experiments")
        experiment = (
            experiments.get(input_name)
            if isinstance(experiments, Mapping)
            and isinstance(experiments.get(input_name), Mapping)
            else {}
        )
        result_dir = str(experiment.get("result_dir") or "")
        result_candidate = Path(result_dir).resolve() if result_dir else None
        if result_candidate is not None and result_candidate.is_dir():
            excited_dir = result_candidate
        else:
            excited_dir = _find_single_directory(
                actuator_root.glob(
                    f"actuator_probe/excited/{input_name}/{baseline_policy}/seed_*"
                ),
                f"{input_name} excited run",
            )
        excited = _physical_state_frame(excited_dir / "data", days=days, probe=probe)
        excited_dirs[input_name] = excited_dir
        delta = excited[list(PHYSICAL_STATE_NAMES)].to_numpy(dtype=float) - baseline[
            list(PHYSICAL_STATE_NAMES)
        ].to_numpy(dtype=float)
        state_response_by_input[input_name] = delta
        signal_rows = trajectories.loc[
            trajectories["experiment_input_signal"].astype(str).eq(input_name)
        ].sort_values("day")
        signal_column = f"excitation_fraction__{input_name}"
        if len(signal_rows) != days or signal_column not in signal_rows.columns:
            raise ControlSystemAnalysisError(
                f"Actuator trajectory {input_name} is incomplete or lacks {signal_column}."
            )
        daily_input = np.zeros((days, len(ACTUATOR_INPUTS)), dtype=float)
        daily_input[:, input_index] = pd.to_numeric(
            signal_rows[signal_column], errors="raise"
        ).to_numpy(dtype=float)
        input_blocks.append(daily_input)
        train_slice = slice(period, 3 * period)
        validation_slice = slice(3 * period, 4 * period)
        train_x = delta[train_slice]
        validation_x = delta[validation_slice]
        train_u = daily_input[period + 1 : 3 * period]
        validation_u = daily_input[3 * period + 1 : 4 * period]
        train_sequences.append(
            IdentificationSequence(input_name, train_x, train_u)
        )
        validation_sequences.append(
            IdentificationSequence(input_name, validation_x, validation_u)
        )
        for state_index, state_name in enumerate(PHYSICAL_STATE_NAMES):
            values = delta[period:, state_index]
            state_rows.append(
                {
                    "kind": "physical_state",
                    "name": state_name,
                    "source_campaign": source_campaign,
                    "associated_input": input_name,
                    "maximum_absolute_paired_response": float(np.max(np.abs(values))),
                    "paired_response_standard_deviation": float(np.std(values)),
                    "exact_dead_zone": bool(np.max(np.abs(values)) <= 1e-12),
                }
            )
    probe_inputs = np.vstack(input_blocks)
    probe_input_singular_values = np.linalg.svd(probe_inputs, compute_uv=False)
    response_direction_matrix = np.column_stack(
        [state_response_by_input[name].reshape(-1) for name in ACTUATOR_INPUTS]
    )
    response_direction_singular_values = np.linalg.svd(
        response_direction_matrix, compute_uv=False
    )
    response_direction_ratios = (
        response_direction_singular_values / response_direction_singular_values[0]
        if len(response_direction_singular_values)
        and response_direction_singular_values[0] > 0.0
        else response_direction_singular_values
    )
    metadata = {
        "protocol": protocol,
        "protocol_path": actuator_root / "canonical_frequency_protocol.json",
        "days": days,
        "period_days": period,
        "probe": dict(probe),
        "baseline_dir": baseline_dir,
        "baseline_states": baseline,
        "application_mode": application_mode,
        "closed_loop_probe": closed_loop_probe,
        "baseline_condition": baseline_condition,
        "baseline_policy": baseline_policy,
        "source_campaign": source_campaign,
        "probe_input_singular_values": probe_input_singular_values,
        "probe_input_rank": _numerical_rank(probe_input_singular_values),
        "response_direction_singular_values": response_direction_singular_values,
        "response_direction_rank": _numerical_rank(
            response_direction_singular_values
        ),
        "response_direction_effective_rank_1pct": int(
            np.count_nonzero(response_direction_ratios > 0.01)
        ),
        "state_response_by_input": state_response_by_input,
        "excited_dirs": excited_dirs,
    }
    return train_sequences, validation_sequences, metadata, pd.DataFrame(state_rows)


def _pole_characteristics(value: complex, *, sample_days: float = 1.0) -> dict[str, Any]:
    modulus = float(abs(value))
    angle = float(np.angle(value))
    time_constant = (
        -float(sample_days) / math.log(modulus)
        if 0.0 < modulus < 1.0 and not math.isclose(modulus, 1.0)
        else math.nan
    )
    period = (
        2.0 * math.pi * float(sample_days) / abs(angle)
        if abs(angle) > 1e-12
        else math.nan
    )
    logarithm = math.log(modulus) if modulus > 0.0 else -math.inf
    damping = (
        -logarithm / math.sqrt(logarithm**2 + angle**2)
        if math.isfinite(logarithm) and (logarithm != 0.0 or angle != 0.0)
        else math.nan
    )
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "modulus": modulus,
        "angle_rad": angle,
        "time_constant_days": time_constant,
        "oscillation_period_days": period,
        "damping_ratio": damping,
    }


def _controller_tables(evidence: Mapping[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    memory = float(evidence["stress_memory_pole"])
    pole = pd.DataFrame(
        [
            {
                "model": "controller_v3_internal_memory",
                "source": "exact_controller_configuration",
                "claim_status": "exact_controller_property_not_supply_chain_pole",
                "reduced_order": 1,
                "mode_index": 1,
                **_pole_characteristics(complex(memory)),
                "publishable_as_controller_pole": True,
                "publishable_as_physical_supply_chain_pole": False,
            }
        ]
    )
    input_gains = np.asarray(evidence["controller_input_gains"], dtype=float)
    output_gains = np.asarray(evidence["controller_output_gains"], dtype=float)
    controllability = pd.DataFrame(
        [
            {
                "model": "controller_v3_internal_memory",
                "claim_status": "exact_scalar_controller_property",
                "singular_index": 1,
                "singular_value": float(np.linalg.norm(input_gains)),
                "numerical_rank": 1,
                "state_order": 1,
                "finite_or_infinite_horizon_gramian_value": float(
                    evidence["controller_controllability_gramian"]
                ),
                "interpretation": (
                    "La mémoire scalaire est commandable par les signaux internes; "
                    "ce résultat ne mesure pas la commandabilité de la supply chain."
                ),
            }
        ]
    )
    observability = pd.DataFrame(
        [
            {
                "model": "controller_v3_internal_memory",
                "claim_status": "exact_scalar_controller_property",
                "singular_index": 1,
                "singular_value": float(np.linalg.norm(output_gains)),
                "numerical_rank": 1,
                "state_order": 1,
                "finite_or_infinite_horizon_gramian_value": float(
                    evidence["controller_observability_gramian"]
                ),
                "interpretation": (
                    "La mémoire scalaire est observable dans les deux commandes; "
                    "ce résultat ne mesure pas l'observabilité de la supply chain."
                ),
            }
        ]
    )
    return pole, controllability, observability


def _physical_model_tables(
    result: ReducedDMDcResult,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    status = "accepted_local_physical_model" if result.accepted else "rejected_exploratory_model"
    pole_rows: list[dict[str, Any]] = []
    if result.available:
        for index, pole in enumerate(result.poles, start=1):
            pole_rows.append(
                {
                    "model": PHYSICAL_CANDIDATE_MODEL,
                    "source": "periodic_actuator_probe",
                    "claim_status": status,
                    "reduced_order": result.selected_order,
                    "mode_index": index,
                    **_pole_characteristics(complex(pole)),
                    "publishable_as_controller_pole": False,
                    "publishable_as_physical_supply_chain_pole": bool(result.accepted),
                }
            )
    else:
        pole_rows.append(
            {
                "model": PHYSICAL_CANDIDATE_MODEL,
                "source": "periodic_actuator_probe",
                "claim_status": "not_fitted",
                "reduced_order": 0,
                "mode_index": 0,
                "publishable_as_controller_pole": False,
                "publishable_as_physical_supply_chain_pole": False,
            }
        )

    ctrb_rows: list[dict[str, Any]] = []
    for index, singular in enumerate(result.controllability_singular_values, start=1):
        ctrb_rows.append(
            {
                "model": PHYSICAL_CANDIDATE_MODEL,
                "claim_status": status,
                "singular_index": index,
                "singular_value": float(singular),
                "numerical_rank": _numerical_rank(
                    result.controllability_singular_values
                ),
                "state_order": result.selected_order,
                "interpretation": (
                    "Diagnostic du modèle exploratoire rejeté; aucune conclusion physique."
                    if not result.accepted
                    else "Commandabilité numérique du modèle local accepté."
                ),
            }
        )
    obsv_rows: list[dict[str, Any]] = []
    for index, singular in enumerate(result.observability_singular_values, start=1):
        obsv_rows.append(
            {
                "model": PHYSICAL_CANDIDATE_MODEL,
                "claim_status": status,
                "singular_index": index,
                "singular_value": float(singular),
                "numerical_rank": _numerical_rank(
                    result.observability_singular_values
                ),
                "state_order": result.selected_order,
                "interpretation": (
                    "Diagnostic du modèle exploratoire rejeté; aucune conclusion physique."
                    if not result.accepted
                    else "Observabilité numérique du modèle local accepté."
                ),
            }
        )

    zero_rows: list[dict[str, Any]] = []
    if result.available and result.accepted:
        for input_index, input_name in enumerate(result.input_names):
            for output_index, output_name in enumerate(result.active_state_names):
                zeros = siso_state_space_zeros(
                    result.a_matrix,
                    result.b_matrix[:, input_index],
                    result.c_matrix[output_index],
                )
                if not len(zeros):
                    zero_rows.append(
                        {
                            "model": PHYSICAL_CANDIDATE_MODEL,
                            "input": input_name,
                            "output": output_name,
                            "zero_index": 0,
                            "status": "accepted_model_no_finite_zero",
                        }
                    )
                for zero_index, zero in enumerate(zeros, start=1):
                    zero_rows.append(
                        {
                            "model": PHYSICAL_CANDIDATE_MODEL,
                            "input": input_name,
                            "output": output_name,
                            "zero_index": zero_index,
                            "real": float(zero.real),
                            "imag": float(zero.imag),
                            "modulus": float(abs(zero)),
                            "status": "accepted_local_model_zero",
                        }
                    )
    else:
        zero_rows.append(
            {
                "model": PHYSICAL_CANDIDATE_MODEL,
                "input": "all",
                "output": "all",
                "zero_index": 0,
                "status": "not_computed_because_physical_model_is_rejected",
            }
        )
    return (
        pd.DataFrame(pole_rows),
        pd.DataFrame(ctrb_rows),
        pd.DataFrame(obsv_rows),
        pd.DataFrame(zero_rows),
    )


def _states_inputs_table(
    evidence: Mapping[str, Any], actuator_state_rows: pd.DataFrame, result: ReducedDMDcResult
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "kind": "controller_state",
            "name": "supplier_stress_memory",
            "unit": "normalized_stress",
            "source": "configured_V3_internal_state",
            "used_in_dmdc": False,
            "status": "exact_controller_state",
        },
        {
            "kind": "controller_input",
            "name": "nervousness",
            "unit": "normalized",
            "source": "canonical_observation",
            "local_gain": float(evidence["controller_input_gains"][0]),
            "used_in_dmdc": False,
            "status": "piecewise_local_gain",
        },
        {
            "kind": "controller_input",
            "name": "capacity_pressure",
            "unit": "normalized",
            "source": "canonical_observation",
            "local_gain": float(evidence["controller_input_gains"][1]),
            "used_in_dmdc": False,
            "status": "gain_only_above_configured_threshold",
        },
        {
            "kind": "controller_input",
            "name": "supplier_disruption_score",
            "unit": "normalized",
            "source": "canonical_observation",
            "local_gain": float(evidence["controller_input_gains"][2]),
            "used_in_dmdc": False,
            "status": "piecewise_local_gain",
        },
        {
            "kind": "controller_output",
            "name": "order_multiplier",
            "unit": "multiplier",
            "source": "V3_continuous_relief",
            "local_gain": float(evidence["local_order_gain_per_stress"]),
            "used_in_dmdc": False,
            "status": "exact_inside_active_unsaturated_branch",
        },
        {
            "kind": "controller_output",
            "name": "production_target_multiplier",
            "unit": "multiplier",
            "source": "V3_continuous_relief",
            "local_gain": float(evidence["local_production_gain_per_stress"]),
            "used_in_dmdc": False,
            "status": "exact_inside_active_unsaturated_branch",
        },
    ]
    state_summary = (
        actuator_state_rows.groupby("name", as_index=False)
        .agg(
            maximum_absolute_paired_response=(
                "maximum_absolute_paired_response",
                "max",
            ),
            paired_response_standard_deviation=(
                "paired_response_standard_deviation",
                "max",
            ),
            exact_dead_zone=("exact_dead_zone", "all"),
        )
        .set_index("name")
    )
    scale_by_name = dict(zip(result.active_state_names, result.state_scale, strict=False))
    for state_name in PHYSICAL_STATE_NAMES:
        summary = state_summary.loc[state_name] if state_name in state_summary.index else None
        rows.append(
            {
                "kind": "physical_state",
                "name": state_name,
                "unit": "quantity_of_named_item",
                "source": "per_item_engine_exports_and_reconstructed_lane_pipeline",
                "used_in_dmdc": state_name in result.active_state_names,
                "normalization_scale": scale_by_name.get(state_name),
                "maximum_absolute_paired_response": (
                    float(summary["maximum_absolute_paired_response"])
                    if summary is not None
                    else math.nan
                ),
                "exact_dead_zone": (
                    bool(summary["exact_dead_zone"]) if summary is not None else True
                ),
                "status": "exploratory_periodic_probe_state",
            }
        )
    for input_name, scale in zip(result.input_names, result.input_scale, strict=False):
        rows.append(
            {
                "kind": "physical_input",
                "name": input_name,
                "unit": "fraction_from_neutral",
                "source": "periodic_actuator_probe",
                "used_in_dmdc": result.available,
                "normalization_scale": float(scale),
                "status": "periodic_single_phase_excitation",
            }
        )
    return pd.DataFrame(rows)


def _frequency_response(
    a_matrix: np.ndarray,
    b_vector: np.ndarray,
    c_vector: np.ndarray,
    frequencies: np.ndarray,
) -> np.ndarray:
    eye = np.eye(len(a_matrix))
    b = np.asarray(b_vector, dtype=float).reshape(-1, 1)
    c = np.asarray(c_vector, dtype=float).reshape(1, -1)
    result: list[complex] = []
    for frequency in frequencies:
        z_value = np.exp(2j * math.pi * float(frequency))
        result.append(complex((c @ np.linalg.solve(z_value * eye - a_matrix, b))[0, 0]))
    return np.asarray(result, dtype=complex)


def _save_figure(path: Path, figure: plt.Figure) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def _plot_operating_point(
    path: Path, operating: pd.DataFrame, evidence: Mapping[str, Any]
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    if operating.empty:
        axes[0].text(0.5, 0.5, "Aucune statistique exploitable", ha="center", va="center")
    else:
        for signal, group in operating.groupby("signal"):
            values = group.sort_values("period_index")
            first = float(values["period_mean"].iloc[0])
            scale = max(abs(first), 1e-12)
            axes[0].plot(
                values["period_index"],
                values["period_mean"] / scale,
                marker="o",
                label=signal.replace("_", " "),
            )
        axes[0].axhline(1.0, color="black", linewidth=0.8)
        axes[0].set_xlabel("Période de 196 jours")
        axes[0].set_ylabel("Moyenne / première période")
        axes[0].legend(fontsize=7)
    axes[0].set_title("Dérive du point physique")
    stationary = bool(evidence["physical_operating_point_stationary"])
    axes[1].axis("off")
    axes[1].text(
        0.02,
        0.92,
        "Point physique stationnaire : " + ("oui" if stationary else "NON"),
        fontsize=13,
        fontweight="bold",
        color="darkgreen" if stationary else "darkred",
    )
    axes[1].text(
        0.02,
        0.75,
        "Le régime du régulateur peut rester fixe\n"
        "alors que stocks et ordres continuent de dériver.\n\n"
        "Un jeu unique de pôles physiques n'est recevable\n"
        "qu'autour d'un équilibre ou d'une orbite répétable.",
        va="top",
        fontsize=11,
    )
    axes[1].set_title("Conclusion sur le point de fonctionnement")
    _save_figure(path, figure)


def _plot_actuator_rank(path: Path, evidence: Mapping[str, Any]) -> None:
    actions = np.asarray(evidence["action_rows"], dtype=float)
    singular = np.asarray(evidence["action_singular_values"], dtype=float)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(actions[:, 0], actions[:, 1], s=10, alpha=0.45)
    limits = np.asarray([actions[:, 0].min(), actions[:, 0].max()])
    axes[0].plot(limits, 0.5 * limits, color="darkorange", label="production = 0,5 × ordre")
    axes[0].set_xlabel("Écart multiplicateur commande")
    axes[0].set_ylabel("Écart cible production")
    axes[0].legend()
    axes[0].set_title("Espace des commandes V3")
    ratios = singular / singular[0] if singular[0] > 0 else singular
    axes[1].bar(np.arange(1, len(ratios) + 1), ratios, color=["#2878b5", "#d9534f"])
    axes[1].set_yscale("log")
    axes[1].set_xticks(np.arange(1, len(ratios) + 1))
    axes[1].set_xlabel("Direction singulière")
    axes[1].set_ylabel("Valeur / maximum")
    axes[1].set_title(f"Rang numérique = {evidence['action_rank']} : une seule direction")
    _save_figure(path, figure)


def _plot_input_rank(
    path: Path,
    evidence: Mapping[str, Any],
    result: ReducedDMDcResult,
    actuator_metadata: Mapping[str, Any],
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    demand = np.asarray(evidence["demand_hankel_singular_values"], dtype=float)
    demand_ratio = demand / demand[0]
    axes[0].semilogy(np.arange(1, len(demand_ratio) + 1), demand_ratio, marker="o")
    axes[0].axhline(1e-10, color="darkred", linestyle="--", linewidth=1)
    axes[0].set_xlabel("Indice")
    axes[0].set_ylabel("Valeur singulière / maximum")
    axes[0].set_title(f"Hankel de la demande : rang {evidence['demand_hankel_rank']}")
    probe = np.asarray(
        actuator_metadata.get("probe_input_singular_values", []), dtype=float
    )
    if len(probe) and probe[0] > 0:
        axes[1].bar(
            np.arange(1, len(probe) + 1),
            probe / probe[0],
            color=["#2878b5", "#4c9f70", "#e09f3e"],
        )
    axes[1].set_xticks(np.arange(1, len(probe) + 1))
    axes[1].set_xlabel("Direction d'essai")
    axes[1].set_ylabel("Valeur singulière / maximum")
    axes[1].set_title(
        "Sollicitations indépendantes : rang "
        f"{int(actuator_metadata.get('probe_input_rank', 0))}"
    )
    snapshot = np.asarray(result.snapshot_singular_values, dtype=float)
    response_directions = np.asarray(
        actuator_metadata.get("response_direction_singular_values", []), dtype=float
    )
    if len(snapshot) and snapshot[0] > 0:
        axes[2].semilogy(
            np.arange(1, len(snapshot) + 1),
            snapshot / snapshot[0],
            marker="o",
            label="états utilisés pour l'ajustement",
        )
    if len(response_directions) and response_directions[0] > 0:
        axes[2].semilogy(
            np.arange(1, len(response_directions) + 1),
            np.maximum(response_directions / response_directions[0], 1e-15),
            marker="s",
            label="directions de réponse des 3 essais",
        )
    if not len(snapshot) and not len(response_directions):
        axes[2].text(
            0.5,
            0.5,
            "Aucune réponse physique non nulle",
            ha="center",
            va="center",
        )
    axes[2].set_xlabel("Indice")
    axes[2].set_ylabel("Valeur singulière / maximum")
    axes[2].axhline(0.01, color="darkred", linestyle="--", linewidth=1)
    axes[2].legend(fontsize=7)
    axes[2].set_title(
        "Réponses physiques : rang effectif à 1 % = "
        f"{int(actuator_metadata.get('response_direction_effective_rank_1pct', 0))}"
    )
    _save_figure(path, figure)


def _plot_poles(path: Path, evidence: Mapping[str, Any], result: ReducedDMDcResult) -> None:
    figure, axis = plt.subplots(figsize=(6.5, 6.5))
    angle = np.linspace(0.0, 2.0 * math.pi, 500)
    axis.plot(np.cos(angle), np.sin(angle), color="black", linewidth=1.2, label="cercle unité")
    memory = float(evidence["stress_memory_pole"])
    axis.scatter(
        [memory],
        [0.0],
        s=110,
        color="darkgreen",
        marker="o",
        label="z = 0,82 — mémoire du régulateur",
        zorder=4,
    )
    if result.available and len(result.poles):
        axis.scatter(
            result.poles.real,
            result.poles.imag,
            s=90,
            color="darkred",
            marker="x",
            linewidths=2.2,
            label="DMDc candidat — MODÈLE REJETÉ",
            zorder=4,
        )
    axis.axhline(0.0, color="grey", linewidth=0.6)
    axis.axvline(0.0, color="grey", linewidth=0.6)
    axis.set_aspect("equal", adjustable="box")
    extent = max(1.15, float(np.max(np.abs(result.poles))) * 1.1 if len(result.poles) else 1.15)
    extent = min(extent, 4.0)
    axis.set_xlim(-extent, extent)
    axis.set_ylim(-extent, extent)
    axis.set_xlabel("Partie réelle")
    axis.set_ylabel("Partie imaginaire")
    axis.set_title("Plan z — aucune revendication de pôles physiques")
    axis.legend(loc="lower left", fontsize=9)
    _save_figure(path, figure)


def _plot_controllability_observability(
    path: Path, evidence: Mapping[str, Any], result: ReducedDMDcResult
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    ctrb = np.asarray(result.controllability_singular_values, dtype=float)
    obsv = np.asarray(result.observability_singular_values, dtype=float)
    for axis, values, title in (
        (axes[0], ctrb, "Commandabilité"),
        (axes[1], obsv, "Observabilité"),
    ):
        axis.bar([0], [1.0], color="darkgreen", label="mémoire V3 scalaire")
        if len(values) and values[0] > 0:
            axis.plot(
                np.arange(1, len(values) + 1),
                values / values[0],
                marker="x",
                color="darkred",
                label="DMDc candidat rejeté",
            )
        axis.set_yscale("log")
        axis.set_ylim(1e-10, 2.0)
        axis.set_xlabel("Indice singulier")
        axis.set_ylabel("Valeur / maximum")
        axis.set_title(title)
        axis.legend(fontsize=8)
    figure.suptitle(
        "Le rang 1 exact concerne le régulateur, pas la supply chain",
        fontsize=12,
    )
    _save_figure(path, figure)


def _plot_free_run(path: Path, result: ReducedDMDcResult) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    if result.predictions.empty:
        for axis in axes:
            axis.text(0.5, 0.5, "Modèle physique indisponible / zone morte", ha="center", va="center")
            axis.axis("off")
    else:
        states = list(dict.fromkeys(result.predictions["state"]))[:2]
        for axis, state in zip(axes, states, strict=False):
            selected = result.predictions.loc[result.predictions["state"].eq(state)]
            for sequence, group in selected.groupby("sequence"):
                axis.plot(
                    group["validation_step"],
                    group["measured_delta"],
                    linewidth=1.1,
                    label=f"simulation — {_french_signal_name(str(sequence))}",
                )
                axis.plot(
                    group["validation_step"],
                    group["free_run_predicted_delta"],
                    linestyle="--",
                    linewidth=1.1,
                    label=f"modèle rejeté — {_french_signal_name(str(sequence))}",
                )
            axis.set_ylabel(_french_signal_name(str(state)))
            axis.legend(fontsize=7, ncol=2)
        axes[-1].set_xlabel("Jour de validation")
    figure.suptitle("Validation libre : DMDc candidat non utilisable pour conclure")
    _save_figure(path, figure)


def _plot_impulse_response(
    path: Path, evidence: Mapping[str, Any], result: ReducedDMDcResult
) -> None:
    horizon = 100
    days = np.arange(horizon)
    memory = float(evidence["stress_memory_pole"])
    order_gain = float(evidence["local_order_gain_per_stress"])
    production_gain = float(evidence["local_production_gain_per_stress"])
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    # An observation made on J changes the effective command on J+1.  The
    # impulse response is therefore exactly zero at lag 0.
    memory_response = np.zeros(horizon, dtype=float)
    memory_response[1:] = memory ** np.arange(horizon - 1)
    axes[0].plot(days, order_gain * memory_response, label="commande")
    axes[0].plot(days, production_gain * memory_response, label="production")
    axes[0].set_xlabel("Jour après impulsion")
    axes[0].set_ylabel("Écart de multiplicateur")
    axes[0].set_title("Mémoire V3 exacte avec délai causal J→J+1")
    axes[0].legend()
    if result.available and result.selected_order > 0:
        for input_index, input_name in enumerate(result.input_names):
            state = np.zeros(result.selected_order)
            response: list[float] = []
            for day in days:
                command = np.zeros(len(result.input_names))
                if day == 0:
                    command[input_index] = 1.0
                state = result.a_matrix @ state + result.b_matrix @ command
                output = result.c_matrix @ state
                response.append(float(output[0]) if len(output) else 0.0)
            axes[1].plot(days, response, label=_french_signal_name(input_name))
        axes[1].legend(fontsize=8)
    else:
        axes[1].text(0.5, 0.5, "Modèle physique non ajustable", ha="center", va="center")
    axes[1].set_xlabel("Jour après impulsion")
    axes[1].set_ylabel("Premier état normalisé")
    axes[1].set_title("DMDc candidat — MODÈLE REJETÉ")
    _save_figure(path, figure)


def _plot_bode(path: Path, evidence: Mapping[str, Any], result: ReducedDMDcResult) -> None:
    frequencies = np.geomspace(1.0 / 400.0, 0.45, 500)
    z_values = np.exp(2j * math.pi * frequencies)
    memory = float(evidence["stress_memory_pole"])
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for gain, label in (
        (
            float(evidence["local_order_gain_per_stress"]),
            "contrôleur exact (mémoire + J→J+1) → commande",
        ),
        (
            float(evidence["local_production_gain_per_stress"]),
            "contrôleur exact (mémoire + J→J+1) → production",
        ),
    ):
        response = gain / (z_values - memory)
        axes[0].semilogx(frequencies, 20.0 * np.log10(np.maximum(np.abs(response), 1e-15)), label=label)
        axes[1].semilogx(frequencies, np.unwrap(np.angle(response)) * 180.0 / math.pi, label=label)
    if result.available and result.selected_order > 0 and result.b_matrix.shape[1] > 0:
        response = _frequency_response(
            result.a_matrix,
            result.b_matrix[:, 0],
            result.c_matrix[0],
            frequencies,
        )
        axes[0].semilogx(
            frequencies,
            20.0 * np.log10(np.maximum(np.abs(response), 1e-15)),
            color="darkred",
            linestyle="--",
            label="DMDc candidat rejeté",
        )
        axes[1].semilogx(
            frequencies,
            np.unwrap(np.angle(response)) * 180.0 / math.pi,
            color="darkred",
            linestyle="--",
            label="DMDc candidat rejeté",
        )
    axes[0].set_ylabel("Gain (dB)")
    axes[1].set_ylabel("Phase (degrés)")
    axes[1].set_xlabel("Fréquence (cycles/jour)")
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8)
    axes[0].set_title(
        "Bode : contrôleur seul exact; candidat procédé explicitement rejeté"
    )
    _save_figure(path, figure)


def _plot_nyquist_deadzone(
    path: Path, evidence: Mapping[str, Any], dead_zones: pd.DataFrame
) -> None:
    frequencies = np.linspace(1e-5, 0.5, 800)
    z_values = np.exp(2j * math.pi * frequencies)
    response = float(evidence["local_order_gain_per_stress"]) / (
        z_values - float(evidence["stress_memory_pole"])
    )
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].plot(response.real, response.imag, label="fréquences positives")
    axes[0].plot(response.real, -response.imag, color="#2878b5", alpha=0.45)
    axes[0].scatter([-1.0], [0.0], marker="x", color="darkred", s=80, label="point -1")
    axes[0].axhline(0.0, color="grey", linewidth=0.6)
    axes[0].axvline(0.0, color="grey", linewidth=0.6)
    axes[0].set_xlabel("Partie réelle")
    axes[0].set_ylabel("Partie imaginaire")
    axes[0].set_title("Nyquist du contrôleur seul (mémoire + délai J→J+1)")
    axes[0].legend(fontsize=8)
    selected = dead_zones.loc[
        dead_zones["source_campaign"].eq("v3_demand_pilot")
        & dead_zones["output"].isin(
            [
                "target_production_qty",
                "probe_destination_arrivals_qty",
                "target_backlog_qty",
                "target_service_level",
                "global_inventory_qty",
            ]
        )
    ].copy()
    if selected.empty:
        axes[1].text(0.5, 0.5, "Aucune sortie sélectionnée", ha="center", va="center")
    else:
        axes[1].barh(
            selected["output"].map(lambda value: _french_signal_name(str(value))),
            np.maximum(selected["maximum_absolute_paired_response"], 1e-15),
            color=np.where(selected["exact_dead_zone"], "darkred", "#2878b5"),
        )
        axes[1].set_xscale("log")
        axes[1].set_xlabel("Réponse paire maximale (échelle log)")
    axes[1].set_title("Zones mortes observées à l'amplitude testée")
    _save_figure(path, figure)


def _plot_probe_composition(path: Path, actuator_metadata: Mapping[str, Any]) -> None:
    figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    closed_loop_probe = bool(actuator_metadata.get("closed_loop_probe"))
    period = int(actuator_metadata.get("period_days") or 0)
    excited_dirs = actuator_metadata.get("excited_dirs")
    for axis, input_name in zip(axes, ACTUATOR_INPUTS, strict=True):
        excited_dir = (
            Path(excited_dirs[input_name])
            if isinstance(excited_dirs, Mapping) and input_name in excited_dirs
            else None
        )
        composition_path = (
            excited_dir / "data" / "canonical_control_probe_composition.csv"
            if excited_dir is not None
            else None
        )
        if (
            not closed_loop_probe
            or composition_path is None
            or not composition_path.is_file()
        ):
            axis.text(
                0.5,
                0.5,
                "Composition post-régulateur non disponible",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            axis.set_title(_french_signal_name(input_name))
            continue
        frame = pd.read_csv(
            composition_path,
            usecols=[
                "day",
                "action",
                "neutral_value",
                "feedback_effective",
                "probe_delta",
                "composed_effective",
            ],
        )
        frame = frame.loc[frame["action"].astype(str).eq(input_name)].copy()
        for column in (
            "day",
            "neutral_value",
            "feedback_effective",
            "probe_delta",
            "composed_effective",
        ):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        daily = (
            frame.dropna(subset=["day"])
            .groupby("day", as_index=False)[
                [
                    "neutral_value",
                    "feedback_effective",
                    "probe_delta",
                    "composed_effective",
                ]
            ]
            .mean()
            .sort_values("day")
        )
        if period > 0:
            daily = daily.loc[daily["day"] < period]
        day = daily["day"].to_numpy(dtype=float)
        neutral = daily["neutral_value"].to_numpy(dtype=float)
        axis.plot(
            day,
            100.0 * (daily["feedback_effective"].to_numpy(dtype=float) - neutral),
            label="décision du régulateur",
            linewidth=1.5,
        )
        axis.plot(
            day,
            100.0 * daily["probe_delta"].to_numpy(dtype=float),
            label="petite variation d'essai",
            linewidth=1.2,
        )
        axis.plot(
            day,
            100.0 * (daily["composed_effective"].to_numpy(dtype=float) - neutral),
            label="commande réellement appliquée",
            linewidth=1.0,
            alpha=0.85,
        )
        axis.axhline(0.0, color="grey", linewidth=0.6)
        axis.set_ylabel("écart à 1 (%)")
        axis.set_title(_french_signal_name(input_name))
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        axes[0].legend(handles, labels, ncol=3, fontsize=8, loc="upper right")
    axes[-1].set_xlabel("Jour du premier cycle de 196 jours")
    figure.suptitle(
        "Boucle fermée : décision V3 + variation indépendante = commande appliquée"
    )
    _save_figure(path, figure)


def _plot_physical_state_responses(
    path: Path, actuator_metadata: Mapping[str, Any]
) -> None:
    responses = actuator_metadata.get("state_response_by_input")
    period = int(actuator_metadata.get("period_days") or 0)
    figure, axes = plt.subplots(3, 2, figsize=(15, 10))
    colors = ("#2878b5", "#4c9f70", "#e09f3e", "#8e5ea2")
    for row, input_name in enumerate(ACTUATOR_INPUTS):
        values = (
            np.asarray(responses[input_name], dtype=float)
            if isinstance(responses, Mapping) and input_name in responses
            else np.empty((0, len(PHYSICAL_STATE_NAMES)))
        )
        curve_axis = axes[row, 0]
        bar_axis = axes[row, 1]
        if values.ndim != 2 or values.shape[1] != len(PHYSICAL_STATE_NAMES):
            curve_axis.text(0.5, 0.5, "Réponse non disponible", ha="center", va="center")
            bar_axis.text(0.5, 0.5, "Réponse non disponible", ha="center", va="center")
            continue
        start = min(max(period, 0), len(values))
        stop = min(len(values), start + max(2 * period, 1))
        days = np.arange(start, stop)
        selected = values[start:stop]
        maximum = np.max(np.abs(values[start:]), axis=0) if start < len(values) else np.zeros(len(PHYSICAL_STATE_NAMES))
        for state_index, (state_name, color) in enumerate(
            zip(PHYSICAL_STATE_NAMES, colors, strict=True)
        ):
            curve_axis.plot(
                days,
                selected[:, state_index],
                color=color,
                linewidth=1.0,
                label=_french_signal_name(state_name),
            )
        if np.max(np.abs(selected)) > 100.0:
            curve_axis.set_yscale("symlog", linthresh=1.0)
        curve_axis.axhline(0.0, color="grey", linewidth=0.6)
        curve_axis.set_ylabel("écart à la référence")
        curve_axis.set_title(f"Réponse temporelle — {_french_signal_name(input_name)}")
        bar_axis.barh(
            [_french_signal_name(name) for name in PHYSICAL_STATE_NAMES],
            np.maximum(maximum, 1e-12),
            color=["darkred" if value <= 1e-12 else color for value, color in zip(maximum, colors, strict=True)],
        )
        bar_axis.set_xscale("log")
        bar_axis.set_xlabel("écart maximal absolu (log)")
        bar_axis.set_title("Effet physique mesuré; rouge = exactement nul")
    axes[0, 0].legend(ncol=2, fontsize=7, loc="upper right")
    axes[-1, 0].set_xlabel("Jour simulé")
    figure.suptitle(
        "États physiques article par article — différences par rapport à la même boucle V3"
    )
    _save_figure(path, figure)


def _french_signal_name(name: str) -> str:
    """Return a plain-French label for user-visible control signals."""

    labels = {
        "order_multiplier": "commande d'achat",
        "safety_stock_multiplier": "stock de sécurité",
        "production_target_multiplier": "cible de production",
        "control_safety_stock_multiplier": "réglage du stock de sécurité",
        "global_backlog_qty": "retard total",
        "global_production_nervousness": "variabilité de la production",
        "global_production_qty": "production totale",
        "global_service_level": "taux de service global",
        "probe_destination_arrivals_qty": "arrivées du composant à l'usine",
        "probe_supplier_shipments_qty": "expéditions du fournisseur",
        "probe_supplier_stock_qty": "stock du composant chez le fournisseur",
        "probe_supplier_utilization": "utilisation du fournisseur",
        "target_backlog_qty": "retard du produit cible",
        "target_finished_stock_qty": "stock fini du produit cible",
        "target_production_qty": "production du produit cible",
        "target_service_level": "taux de service du produit cible",
        "factory_component_stock_qty": "stock du composant à l'usine",
        "supplier_component_stock_qty": "stock du composant chez le fournisseur",
        "lane_pipeline_qty": "quantité en transport",
        "global_inventory_qty": "stock total agrégé",
    }
    return labels.get(name, name.replace("_", " "))


def _french_rejection_reason(reason: str) -> str:
    translations = {
        "no_nonzero_physical_state_response": (
            "Aucun stock ni pipeline étudié n'a changé de façon mesurable."
        ),
        "physical_actuator_dead_zone": (
            "À cette amplitude, les commandes restent dans une zone sans effet physique."
        ),
        "validation_repeats_the_same_periodic_phase": (
            "La partie utilisée pour vérifier le modèle répète exactement la même "
            "oscillation que celle utilisée pour l'ajuster : ce n'est pas un nouvel "
            "essai indépendant."
        ),
        "one_step_prediction_error_too_large": (
            "Même la prévision du jour suivant est trop imprécise."
        ),
        "free_run_prediction_error_too_large": (
            "Lorsqu'on laisse le modèle prévoir seul, son erreur reste presque aussi "
            "grande que les variations qu'il doit reproduire."
        ),
        "ill_conditioned_identification_regressor": (
            "Les données ne séparent pas assez clairement les effets à estimer."
        ),
        "candidate_model_not_asymptotically_stable": (
            "Le petit modèle ajusté diverge lorsqu'on le laisse évoluer seul."
        ),
        "candidate_model_not_numerically_controllable": (
            "Les essais ne montrent pas que les commandes peuvent agir sur tous les "
            "mouvements du petit modèle."
        ),
        "candidate_model_not_numerically_observable": (
            "Les mesures disponibles ne permettent pas de reconstruire tous les "
            "mouvements du petit modèle."
        ),
    }
    if reason.startswith("physical_dead_zone_for_input:"):
        action = _french_signal_name(reason.split(":", 1)[1])
        return (
            f"La commande « {action} » n'a provoqué aucun changement physique "
            "mesurable dans ces essais."
        )
    if reason.startswith("unexcited_inputs:"):
        actions = ", ".join(
            _french_signal_name(action)
            for action in reason.split(":", 1)[1].split(",")
        )
        return f"Les commandes suivantes n'ont pas été réellement excitées : {actions}."
    return translations.get(reason, reason.replace("_", " ") + ".")


def _write_report(
    path: Path,
    *,
    evidence: Mapping[str, Any],
    result: ReducedDMDcResult,
    dead_zones: pd.DataFrame,
    actuator_metadata: Mapping[str, Any],
) -> None:
    exact_dead = dead_zones.loc[
        dead_zones["source_campaign"].eq("v3_demand_pilot")
        & dead_zones["exact_dead_zone"].astype(bool),
        "output",
    ].astype(str).map(_french_signal_name).tolist()
    candidate_poles = (
        ", ".join(
            f"{pole.real:+.4f}{pole.imag:+.4f}j (|z|={abs(pole):.4f})"
            for pole in result.poles
        )
        if len(result.poles)
        else "aucun ajustement possible"
    )
    reasons = (
        "\n".join(
            f"- {_french_rejection_reason(reason)}"
            for reason in result.rejection_reasons
        )
        or "- Aucune raison de rejet."
    )
    closed_loop_probe = bool(actuator_metadata.get("closed_loop_probe"))
    probe_description = (
        "Les essais périodiques d'actionneurs en boucle fermée"
        if closed_loop_probe
        else "Les anciens essais périodiques d'actionneurs MRP"
    )
    probe_rank = int(actuator_metadata.get("probe_input_rank") or 0)
    response_rank = int(actuator_metadata.get("response_direction_rank") or 0)
    response_effective_rank = int(
        actuator_metadata.get("response_direction_effective_rank_1pct") or 0
    )
    model_controllability_rank = _numerical_rank(
        result.controllability_singular_values
    )
    model_observability_rank = _numerical_rank(result.observability_singular_values)
    report = f"""# Analyse locale de régulation — RESILIENCE-SCAN V3

## Conclusion immédiate

Le seul pôle établi exactement est **z = {float(evidence['stress_memory_pole']):.2f}**, la mémoire interne du régulateur V3. Sa constante de temps vaut {float(evidence['time_constant_days']):.2f} jours et sa demi-vie {float(evidence['half_life_days']):.2f} jours. Ce pôle n'est pas un pôle de la supply chain.

{probe_description} ont permis d'ajuster un petit modèle linéaire d'ordre {result.selected_order}, avec la méthode appelée DMDc. Cette approximation est **{'ACCEPTÉE' if result.accepted else 'REJETÉE'}**. Ses valeurs propres restent visibles pour expliquer le diagnostic, mais elles ne sont pas utilisables pour conclure sur les pôles physiques.

Pôles candidats du modèle exploratoire : {candidate_poles}.

## Ce que fait réellement la V3

- gain local stress → commande : {float(evidence['local_order_gain_per_stress']):.6f} ;
- gain local stress → cible de production : {float(evidence['local_production_gain_per_stress']):.6f} ;
- les réponses exactes Bode, Nyquist et impulsionnelle incluent le délai causal J→J+1 ;
- rang de l'espace des commandes : {int(evidence['action_rank'])} ;
- rang des trois variations expérimentales séparées : {probe_rank} ;
- rang du signal de demande retardé : {int(evidence['demand_hankel_rank'])}.

Commande et production suivent une direction fixe. La V3 possède donc un seul degré de liberté continu dans cette branche, même si elle écrit deux multiplicateurs.

Les trois variations d'essai sont indépendantes lorsque leur rang vaut 3. Cela vérifie la qualité des entrées expérimentales, mais ne prouve pas que les états physiques sont commandables : une commande peut rester dans une zone morte ou déclencher un lot discontinu.

Les réponses physiques observées ont un rang numérique de {response_rank}, mais seulement {response_effective_rank} direction(s) restent significatives au seuil de 1 %. C'est un diagnostic des essais, pas encore un calcul de contrôlabilité du procédé.

## Contrôlabilité et observabilité

- la mémoire interne scalaire du régulateur est exactement contrôlable et observable : rang 1 sur 1 ;
- pour le modèle physique candidat d'ordre {result.selected_order}, la matrice de contrôlabilité a le rang {model_controllability_rank} et la matrice d'observabilité le rang {model_observability_rank} ;
- comme ce modèle est rejeté, ces deux derniers nombres ne démontrent ni la contrôlabilité ni l'observabilité de la supply chain réelle.

## Pourquoi le modèle physique est rejeté

{reasons}

La période réservée à la validation répète la même forme périodique que l'estimation. Elle vérifie la répétabilité mais ne constitue pas une expérience indépendante. La commandabilité et l'observabilité calculées pour le DMDc restent donc des diagnostics du modèle rejeté.

## Point de fonctionnement et zones mortes

Point physique stationnaire selon la règle de dérive à 5 % : **{'oui' if evidence['physical_operating_point_stationary'] else 'non'}**.

Sorties exactement inchangées dans le pilote demande : {', '.join(exact_dead) if exact_dead else 'aucune'}.

Une sortie exactement inchangée ne prouve pas qu'elle est globalement incontrôlable. Elle indique qu'à cette amplitude et avec les règles de lots actives, la dérivée locale observée est nulle.

## Lecture des graphiques

- les points verts représentent des propriétés exactes du régulateur ;
- les croix et pointillés rouges représentent le modèle DMDc candidat rejeté ;
- le cercle unité sert à lire la stabilité discrète ;
- le Nyquist fourni concerne uniquement la mémoire du régulateur, faute de modèle physique accepté ;
- aucune marge de stabilité de la boucle supply chain complète n'est revendiquée.

## Expérience nécessaire pour conclure

Les trois commandes sont désormais excitées séparément. Pour conclure, il faut répéter ces essais avec plusieurs phases et une réalisation totalement mise de côté. Le point physique doit être stabilisé et les essais à 0,25 %, 0,5 % et 1 % doivent produire le même modèle local. Les amplitudes qui franchissent une règle de lot doivent être présentées séparément comme réponses hybrides à amplitude finie.
"""
    path.write_text(report, encoding="utf-8")


def run_control_system_analysis(
    v3_frequency_results_dir: str | Path,
    actuator_frequency_results_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run the read-only control-system audit and create a separate package."""

    v3_root = Path(v3_frequency_results_dir).resolve()
    actuator_root = Path(actuator_frequency_results_dir).resolve()
    destination = Path(output_dir).resolve()
    if not v3_root.is_dir():
        raise FileNotFoundError(f"V3 frequency results directory does not exist: {v3_root}")
    if not actuator_root.is_dir():
        raise FileNotFoundError(
            f"Actuator frequency results directory does not exist: {actuator_root}"
        )
    _prepare_output_dir(destination, (v3_root, actuator_root))

    evidence, operating, v3_dead_zones, trajectory, _ = _controller_and_v3_evidence(
        v3_root
    )
    train, validation, actuator_metadata, actuator_state_rows = _load_actuator_sequences(
        actuator_root
    )
    dmdc = fit_reduced_dmdc(
        train,
        validation,
        state_names=PHYSICAL_STATE_NAMES,
        input_names=ACTUATOR_INPUTS,
        independent_validation=False,
    )
    controller_poles, controller_ctrb, controller_obsv = _controller_tables(evidence)
    physical_poles, physical_ctrb, physical_obsv, zeros = _physical_model_tables(dmdc)
    poles = pd.concat([controller_poles, physical_poles], ignore_index=True, sort=False)
    controllability = pd.concat(
        [controller_ctrb, physical_ctrb], ignore_index=True, sort=False
    )
    observability = pd.concat(
        [controller_obsv, physical_obsv], ignore_index=True, sort=False
    )
    states_inputs = _states_inputs_table(evidence, actuator_state_rows, dmdc)
    actuator_dead_zones = actuator_state_rows.rename(
        columns={"name": "output", "associated_input": "input"}
    ).copy()
    actuator_dead_zones["source_campaign"] = str(
        actuator_metadata["source_campaign"]
    )
    dead_zones = pd.concat(
        [v3_dead_zones, actuator_dead_zones], ignore_index=True, sort=False
    )

    validation_frames: list[pd.DataFrame] = []
    if not dmdc.candidate_metrics.empty:
        candidate = dmdc.candidate_metrics.copy()
        candidate["metric_scope"] = "candidate_order"
        candidate["selected"] = candidate["order"].eq(dmdc.selected_order)
        validation_frames.append(candidate)
    if not dmdc.validation_metrics.empty:
        validation_frames.append(dmdc.validation_metrics.copy())
    validation_table = (
        pd.concat(validation_frames, ignore_index=True, sort=False)
        if validation_frames
        else pd.DataFrame(
            [
                {
                    "metric_scope": "model",
                    "metric": "availability",
                    "value": 0,
                }
            ]
        )
    )
    validation_table["physical_model_accepted"] = bool(dmdc.accepted)
    validation_table["rejection_reasons"] = ";".join(dmdc.rejection_reasons)

    tables = {
        "canonical_control_system_states_inputs.csv": states_inputs,
        "canonical_control_system_poles.csv": poles,
        "canonical_control_system_zeros.csv": zeros,
        "canonical_control_system_controllability.csv": controllability,
        "canonical_control_system_observability.csv": observability,
        "canonical_control_system_validation.csv": validation_table,
        "canonical_control_system_dead_zones.csv": dead_zones,
        "canonical_control_system_operating_point.csv": operating,
    }
    for filename, frame in tables.items():
        frame.to_csv(destination / filename, index=False)

    _plot_operating_point(
        destination / "canonical_control_system_operating_point.png",
        operating,
        evidence,
    )
    _plot_actuator_rank(
        destination / "canonical_control_system_actuator_space_rank.png", evidence
    )
    _plot_input_rank(
        destination / "canonical_control_system_input_rank.png",
        evidence,
        dmdc,
        actuator_metadata,
    )
    _plot_poles(
        destination / "canonical_control_system_pole_map.png", evidence, dmdc
    )
    _plot_controllability_observability(
        destination / "canonical_control_system_controllability_observability.png",
        evidence,
        dmdc,
    )
    _plot_free_run(
        destination / "canonical_control_system_free_run_validation.png", dmdc
    )
    _plot_impulse_response(
        destination / "canonical_control_system_impulse_response.png", evidence, dmdc
    )
    _plot_bode(destination / "canonical_control_system_bode.png", evidence, dmdc)
    _plot_nyquist_deadzone(
        destination / "canonical_control_system_nyquist_deadzone.png",
        evidence,
        dead_zones,
    )
    _plot_probe_composition(
        destination / "canonical_control_system_probe_composition.png",
        actuator_metadata,
    )
    _plot_physical_state_responses(
        destination / "canonical_control_system_physical_state_response.png",
        actuator_metadata,
    )

    report_path = destination / "canonical_control_system_report.md"
    _write_report(
        report_path,
        evidence=evidence,
        result=dmdc,
        dead_zones=dead_zones,
        actuator_metadata=actuator_metadata,
    )

    source_files = list(
        dict.fromkeys(
            [
                Path(evidence["protocol_path"]),
                Path(evidence["controller_config_path"]),
                Path(actuator_metadata["protocol_path"]),
            ]
        )
    )
    manifest_path = destination / "canonical_control_system_manifest.json"
    artifact_hashes = {
        path.name: _sha256(path)
        for path in sorted(destination.iterdir())
        if path.is_file() and path != manifest_path
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete" if dmdc.accepted else "exploratory_complete",
        "claim_scope": (
            "propriétés exactes de la mémoire V3 et modèle physique local accepté"
            if dmdc.accepted
            else "propriétés exactes de la mémoire V3 et tentative physique rejetée"
        ),
        "operating_point": {
            "label": "branche fournisseur stressée; point physique non stationnaire"
            if not evidence["physical_operating_point_stationary"]
            else "branche fournisseur stressée; point physique stationnaire",
            "stationary_under_5_percent_rule": bool(
                evidence["physical_operating_point_stationary"]
            ),
        },
        "source_packages": {
            "v3_frequency_results_dir": str(v3_root),
            "actuator_frequency_results_dir": str(actuator_root),
            "actuator_application_mode": str(
                actuator_metadata["application_mode"]
            ),
            "source_files": [
                {"path": str(path), "sha256": _sha256(path)} for path in source_files
            ],
            "source_packages_modified": False,
        },
        "controller_exact_analysis": {
            "memory_pole": float(evidence["stress_memory_pole"]),
            "time_constant_days": float(evidence["time_constant_days"]),
            "half_life_days": float(evidence["half_life_days"]),
            "local_order_gain_per_stress": float(
                evidence["local_order_gain_per_stress"]
            ),
            "local_production_gain_per_stress": float(
                evidence["local_production_gain_per_stress"]
            ),
            "scalar_controllability_rank": 1,
            "scalar_observability_rank": 1,
            "actuator_space_rank": int(evidence["action_rank"]),
            "demand_hankel_rank": int(evidence["demand_hankel_rank"]),
            "scope": "controller_internal_memory_not_supply_chain",
        },
        "experimental_actuator_excitation": {
            "application_mode": str(actuator_metadata["application_mode"]),
            "closed_loop_probe": bool(actuator_metadata["closed_loop_probe"]),
            "input_names": list(ACTUATOR_INPUTS),
            "rank": int(actuator_metadata["probe_input_rank"]),
            "singular_values": actuator_metadata["probe_input_singular_values"],
            "measured_response_direction_rank": int(
                actuator_metadata["response_direction_rank"]
            ),
            "measured_response_direction_effective_rank_1pct": int(
                actuator_metadata["response_direction_effective_rank_1pct"]
            ),
            "measured_response_direction_singular_values": actuator_metadata[
                "response_direction_singular_values"
            ],
            "scope": "rank_of_applied_test_variations_not_physical_controllability",
        },
        "physical_identification": {
            "method": "reduced_dmdc_numpy_only",
            "available": bool(dmdc.available),
            "accepted": bool(dmdc.accepted),
            "claim_status": (
                "accepted_local_model" if dmdc.accepted else "rejected_exploratory_model"
            ),
            "selected_order": int(dmdc.selected_order),
            "active_state_names": dmdc.active_state_names,
            "input_names": dmdc.input_names,
            "source_campaign": str(actuator_metadata["source_campaign"]),
            "rejection_reasons": dmdc.rejection_reasons,
            "candidate_poles_visible_for_diagnosis": bool(len(dmdc.poles)),
            "candidate_poles_publishable_as_physical_poles": bool(dmdc.accepted),
            "siso_zeros_computed": bool(dmdc.accepted),
            "independent_validation": False,
            "matrices_normalized_coordinates": {
                "A": dmdc.a_matrix,
                "B": dmdc.b_matrix,
                "C": dmdc.c_matrix,
            },
        },
        "dimensions": {
            "states": int(dmdc.selected_order),
            "inputs": len(dmdc.input_names),
            "outputs": len(dmdc.active_state_names),
        },
        "controllability": {
            "rank": _numerical_rank(dmdc.controllability_singular_values),
            "condition_number": (
                float(
                    dmdc.controllability_singular_values[0]
                    / dmdc.controllability_singular_values[-1]
                )
                if len(dmdc.controllability_singular_values)
                and dmdc.controllability_singular_values[-1] > 1e-15
                else None
            ),
            "claim_status": (
                "validated_local_model" if dmdc.accepted else "exploratory_rejected_model"
            ),
        },
        "observability": {
            "rank": _numerical_rank(dmdc.observability_singular_values),
            "condition_number": (
                float(
                    dmdc.observability_singular_values[0]
                    / dmdc.observability_singular_values[-1]
                )
                if len(dmdc.observability_singular_values)
                and dmdc.observability_singular_values[-1] > 1e-15
                else None
            ),
            "claim_status": (
                "validated_local_model" if dmdc.accepted else "exploratory_rejected_model"
            ),
        },
        "claims": {
            "local_linear_model_validated": bool(dmdc.accepted),
            "poles_validated": True if dmdc.accepted else None,
            "local_stability_demonstrated": bool(
                dmdc.accepted and len(dmdc.poles) and np.max(np.abs(dmdc.poles)) < 1.0
            ),
            "controller_internal_pole_identified_exactly": True,
            "supply_chain_physical_poles_identified": bool(dmdc.accepted),
            "supply_chain_controllability_established": bool(dmdc.accepted),
            "supply_chain_observability_established": bool(dmdc.accepted),
            "closed_loop_stability_margin_established": False,
            "nyquist_scope": "controller_internal_memory_only",
            "global_hybrid_stability_claimed": False,
        },
        "limitations": [
            "Le pôle z=0,82 est celui de la mémoire interne du régulateur, pas celui de la supply chain.",
            "Le rang 3 des variations d'essai décrit les entrées appliquées; il ne prouve pas la commandabilité physique.",
            "Les essais actionneurs répètent la même phase périodique et ne fournissent pas de validation indépendante.",
            "Les pôles DMDc candidats sont visibles uniquement pour expliquer le rejet du modèle.",
            "Le Nyquist et le Bode exacts concernent le régulateur seul; aucune marge de boucle physique n'est validée.",
        ],
        "artifacts": artifact_hashes,
    }
    manifest_path.write_text(
        json.dumps(_json_safe(manifest), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": destination,
        "manifest_path": manifest_path,
        "report_path": report_path,
        "manifest": manifest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-frequency-results-dir", required=True, type=Path)
    parser.add_argument("--actuator-frequency-results-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run_control_system_analysis(
        args.v3_frequency_results_dir,
        args.actuator_frequency_results_dir,
        args.output_dir,
    )
    print(result["manifest_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTUATOR_INPUTS",
    "ControlSystemAnalysisError",
    "IdentificationSequence",
    "PHYSICAL_CANDIDATE_MODEL",
    "PHYSICAL_STATE_NAMES",
    "ReducedDMDcResult",
    "SCHEMA_VERSION",
    "controllability_matrix",
    "fit_reduced_dmdc",
    "hankel_singular_values",
    "main",
    "observability_matrix",
    "run_control_system_analysis",
    "siso_state_space_zeros",
]
