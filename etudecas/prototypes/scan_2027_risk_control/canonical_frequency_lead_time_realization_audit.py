#!/usr/bin/env python3
"""Audit requested lead-time amplitudes against realized integer lead days.

The frequency campaign requests a continuous multiplier, while the simulation
engine realizes transport delays on a daily grid.  This post-processing audit
keeps the source artifacts immutable, reconstructs the realized delay observed
on every perturbed shipment, and compares cells that share the same phase.

Realized-input distinctness is a necessary condition for an amplitude-based
local analysis; it is not, by itself, evidence of a local derivative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


SCHEMA_VERSION = "scan.canonical_frequency_lead_time_realization_audit.v1"
TARGET_INPUT_SIGNAL = "supplier_lead_time_multiplier"
DETAIL_FILENAME = "canonical_frequency_lead_time_realization_observations.csv"
CELL_FILENAME = "canonical_frequency_lead_time_realization_cells.csv"
COMPARISON_FILENAME = "canonical_frequency_lead_time_realization_comparisons.csv"
JSON_FILENAME = "canonical_frequency_lead_time_realization_audit.json"
FIGURE_FILENAME = "canonical_frequency_lead_time_realization.png"
REPORT_FILENAME = "canonical_frequency_lead_time_realization_report.md"


class LeadTimeRealizationAuditError(ValueError):
    """Raised when source artifacts cannot support an unambiguous audit."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LeadTimeRealizationAuditError(f"Invalid {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LeadTimeRealizationAuditError(f"{label} must be a JSON object: {path}")
    return payload


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise LeadTimeRealizationAuditError(
            f"{label} is missing required columns: {', '.join(missing)}"
        )


def _strict_number(value: Any, label: str, *, lower: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise LeadTimeRealizationAuditError(f"{label} must be numeric.") from exc
    if not math.isfinite(parsed) or parsed < lower:
        raise LeadTimeRealizationAuditError(
            f"{label} must be finite and at least {lower}."
        )
    return parsed


def _artifact_cell_id(artifact_dir: Path, config: Mapping[str, Any]) -> str:
    request_path = artifact_dir.parent / "execution_request.json"
    if request_path.is_file():
        request = _read_json_object(request_path, "execution request")
        cell_id = str(request.get("cell_id") or "").strip()
        if cell_id:
            return cell_id
    if artifact_dir.parent.parent.name == "attempts":
        return artifact_dir.parents[2].name
    configured_name = str(config.get("name") or "").strip()
    if configured_name:
        return configured_name
    raise LeadTimeRealizationAuditError(
        f"Cannot determine a cell identifier for artifact directory: {artifact_dir}"
    )


def _config_snapshot_path(
    artifact_dir: Path,
    protocol: Mapping[str, Any],
) -> Path:
    config_meta = protocol.get("config")
    if not isinstance(config_meta, Mapping):
        raise LeadTimeRealizationAuditError("Protocol config metadata is missing.")
    relative = str(config_meta.get("snapshot_relative_path") or "").strip()
    if not relative:
        raise LeadTimeRealizationAuditError(
            "Protocol config.snapshot_relative_path is required for immutable auditing."
        )
    candidate = (artifact_dir / Path(relative)).resolve()
    try:
        candidate.relative_to(artifact_dir)
    except ValueError as exc:
        raise LeadTimeRealizationAuditError(
            f"Config snapshot escapes the artifact directory: {candidate}"
        ) from exc
    if not candidate.is_file():
        raise LeadTimeRealizationAuditError(f"Config snapshot is missing: {candidate}")
    expected = str(config_meta.get("sha256") or "").strip()
    if expected and _sha256(candidate) != expected:
        raise LeadTimeRealizationAuditError(
            f"Config snapshot checksum does not match the protocol: {candidate}"
        )
    return candidate


def _operating_condition_baselines(config: Mapping[str, Any]) -> dict[str, float]:
    raw_conditions = config.get("operating_conditions")
    if not isinstance(raw_conditions, list) or not raw_conditions:
        raise LeadTimeRealizationAuditError(
            "Frequency config operating_conditions must be a non-empty list."
        )
    baselines: dict[str, float] = {}
    for index, raw in enumerate(raw_conditions):
        if not isinstance(raw, Mapping):
            raise LeadTimeRealizationAuditError(
                f"operating_conditions[{index}] must be an object."
            )
        name = str(raw.get("name") or "").strip()
        if not name or name in baselines:
            raise LeadTimeRealizationAuditError(
                "Operating-condition names must be non-empty and unique."
            )
        baselines[name] = _strict_number(
            raw.get("supplier_lead_time_baseline", 1.0),
            f"operating_conditions[{index}].supplier_lead_time_baseline",
            lower=0.05,
        )
    return baselines


def _load_cell_metadata(artifact_dir: Path) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    protocol_path = artifact_dir / "canonical_frequency_protocol.json"
    manifest_path = artifact_dir / "canonical_frequency_manifest.json"
    if not protocol_path.is_file() or not manifest_path.is_file():
        raise LeadTimeRealizationAuditError(
            f"Protocol or manifest is missing from artifact directory: {artifact_dir}"
        )
    protocol = _read_json_object(protocol_path, "frequency protocol")
    manifest = _read_json_object(manifest_path, "frequency manifest")
    if protocol != manifest:
        raise LeadTimeRealizationAuditError(
            f"Protocol and manifest differ: {artifact_dir}"
        )
    if protocol.get("status") != "complete_designed":
        raise LeadTimeRealizationAuditError(
            f"Artifact is not a complete designed study: {artifact_dir}"
        )
    config_path = _config_snapshot_path(artifact_dir, protocol)
    config = _read_json_object(config_path, "frequency config snapshot")
    identification = config.get("identification")
    if not isinstance(identification, Mapping):
        raise LeadTimeRealizationAuditError("Frequency config identification is missing.")
    enabled = identification.get("enabled_input_signals")
    if not isinstance(enabled, list) or TARGET_INPUT_SIGNAL not in enabled:
        raise LeadTimeRealizationAuditError(
            f"Artifact does not enable {TARGET_INPUT_SIGNAL}: {artifact_dir}"
        )
    peak_fraction = identification.get("peak_fraction")
    if not isinstance(peak_fraction, Mapping):
        raise LeadTimeRealizationAuditError(
            "Frequency config identification.peak_fraction is missing."
        )
    requested_fraction = _strict_number(
        peak_fraction.get(TARGET_INPUT_SIGNAL),
        f"identification.peak_fraction.{TARGET_INPUT_SIGNAL}",
    )
    phase_seed = int(
        _strict_number(identification.get("phase_seed"), "identification.phase_seed")
    )
    campaign = config.get("campaign")
    if not isinstance(campaign, Mapping):
        raise LeadTimeRealizationAuditError("Frequency config campaign is missing.")
    simulation_seed = int(_strict_number(campaign.get("seed"), "campaign.seed"))
    return {
        "artifact_dir": artifact_dir,
        "protocol_path": protocol_path,
        "manifest_path": manifest_path,
        "config_path": config_path,
        "config": config,
        "cell_id": _artifact_cell_id(artifact_dir, config),
        "requested_peak_fraction": requested_fraction,
        "requested_amplitude_percent": requested_fraction * 100.0,
        "phase_seed": phase_seed,
        "simulation_seed": simulation_seed,
        "operating_baselines": _operating_condition_baselines(config),
    }


def discover_artifact_dirs(campaign_dir: str | Path) -> list[Path]:
    """Discover complete designed artifact directories below a campaign root."""

    root = Path(campaign_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Campaign directory does not exist: {root}")
    discovered: list[Path] = []
    for protocol_path in sorted(root.rglob("canonical_frequency_protocol.json")):
        artifact_dir = protocol_path.parent
        if not (
            artifact_dir
            / "runs"
        ).is_dir() or not list(
            artifact_dir.glob(
                f"runs/*/excited/{TARGET_INPUT_SIGNAL}/*/seed_*/data"
            )
        ):
            continue
        protocol = _read_json_object(protocol_path, "frequency protocol")
        if protocol.get("status") == "complete_designed":
            discovered.append(artifact_dir)
    if not discovered:
        raise LeadTimeRealizationAuditError(
            f"No complete {TARGET_INPUT_SIGNAL} artifact was found below: {root}"
        )
    by_cell: dict[str, list[Path]] = {}
    for artifact_dir in discovered:
        metadata = _load_cell_metadata(artifact_dir)
        by_cell.setdefault(str(metadata["cell_id"]), []).append(artifact_dir)
    ambiguous = {cell: paths for cell, paths in by_cell.items() if len(paths) > 1}
    if ambiguous:
        formatted = "; ".join(
            f"{cell}: {', '.join(str(path) for path in paths)}"
            for cell, paths in sorted(ambiguous.items())
        )
        raise LeadTimeRealizationAuditError(
            "Multiple complete attempts exist for the same cell; pass explicit "
            f"--artifact-dir values instead. {formatted}"
        )
    return discovered


def _unique_numeric_by_key(
    frame: pd.DataFrame,
    *,
    key: str,
    value: str,
    label: str,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for raw_key, group in frame.groupby(key, dropna=False):
        values = pd.to_numeric(group[value], errors="coerce").dropna().unique()
        if len(values) != 1:
            raise LeadTimeRealizationAuditError(
                f"{label} must have one {value} value per {key}; got {raw_key!r}."
            )
        result[str(raw_key)] = float(values[0])
    return result


def _run_observations(
    metadata: Mapping[str, Any],
    data_dir: Path,
) -> tuple[list[dict[str, Any]], list[Path]]:
    artifact_dir = Path(metadata["artifact_dir"])
    relative = data_dir.relative_to(artifact_dir)
    parts = relative.parts
    # runs / condition / excited / input / policy / seed_N / data
    if len(parts) != 7 or parts[0] != "runs" or parts[2] != "excited":
        raise LeadTimeRealizationAuditError(f"Unexpected run layout: {data_dir}")
    condition, input_signal, policy = parts[1], parts[3], parts[4]
    if input_signal != TARGET_INPUT_SIGNAL:
        raise LeadTimeRealizationAuditError(f"Unexpected input run: {data_dir}")
    try:
        seed = int(parts[5].removeprefix("seed_"))
    except ValueError as exc:
        raise LeadTimeRealizationAuditError(f"Invalid seed directory: {data_dir}") from exc
    if seed != int(metadata["simulation_seed"]):
        raise LeadTimeRealizationAuditError(
            "Run seed differs from the simulation seed declared in the campaign: "
            f"run={seed}, campaign={metadata['simulation_seed']}: {data_dir}"
        )
    operating_baselines = metadata["operating_baselines"]
    if condition not in operating_baselines:
        raise LeadTimeRealizationAuditError(
            f"Run condition {condition!r} is absent from the frequency config."
        )

    risk_path = data_dir / "supplier_risk_events_applied_daily.csv"
    shipment_path = data_dir / "production_supplier_shipments_daily.csv"
    nominal_path = data_dir / "supplier_nominal_parameters.csv"
    for path in (risk_path, shipment_path, nominal_path):
        if not path.is_file():
            raise LeadTimeRealizationAuditError(f"Required realization source is missing: {path}")

    risk = pd.read_csv(risk_path)
    shipments = pd.read_csv(shipment_path)
    nominal = pd.read_csv(nominal_path)
    _require_columns(
        risk,
        (
            "day",
            "supplier_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "event_ids",
            "lead_time_multiplier",
            "lead_time_extra_days",
            "quality_delay_days",
        ),
        str(risk_path),
    )
    _require_columns(
        shipments,
        (
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "shipped_qty",
            "lead_days",
        ),
        str(shipment_path),
    )
    _require_columns(
        nominal,
        ("edge_id", "planned_lead_time_days"),
        str(nominal_path),
    )
    risk = risk[
        risk["event_ids"].astype(str).str.contains("frequency_lead_time", regex=False)
    ].copy()
    if risk.empty:
        raise LeadTimeRealizationAuditError(
            f"No designed lead-time risk record was found in: {risk_path}"
        )

    risk_keys = ["day", "supplier_id", "dst_node_id", "item_id", "edge_id"]
    duplicate_risk = risk.duplicated(risk_keys, keep=False)
    if duplicate_risk.any():
        raise LeadTimeRealizationAuditError(
            f"Designed lead-time risk rows are duplicated in: {risk_path}"
        )
    nominal_by_edge = _unique_numeric_by_key(
        nominal,
        key="edge_id",
        value="planned_lead_time_days",
        label=str(nominal_path),
    )

    shipment_join_keys = ["day", "supplier_id", "dst_node_id", "item_id"]
    if risk.duplicated(shipment_join_keys, keep=False).any():
        raise LeadTimeRealizationAuditError(
            "Several designed edges map to the same shipment key in: "
            f"{risk_path}"
        )
    selected_shipments = shipments.rename(
        columns={"src_node_id": "supplier_id"}
    ).merge(
        risk[shipment_join_keys].drop_duplicates(),
        on=shipment_join_keys,
        how="inner",
        validate="many_to_one",
    )
    grouped_shipments = []
    for group_key, group in selected_shipments.groupby(shipment_join_keys, dropna=False):
        lead_values = sorted(
            set(pd.to_numeric(group["lead_days"], errors="coerce").dropna().astype(int))
        )
        if len(lead_values) != 1:
            raise LeadTimeRealizationAuditError(
                "A perturbed lane/day must have one realized lead_days value; "
                f"got {lead_values} for {group_key!r} in {shipment_path}."
            )
        grouped_shipments.append(
            {
                "day": group_key[0],
                "supplier_id": group_key[1],
                "dst_node_id": group_key[2],
                "item_id": group_key[3],
                "realized_lead_days": int(lead_values[0]),
                "shipment_row_count": int(len(group)),
                "shipped_qty": float(
                    pd.to_numeric(group["shipped_qty"], errors="coerce").fillna(0.0).sum()
                ),
            }
        )
    shipment_summary = pd.DataFrame(
        grouped_shipments,
        columns=[
            *shipment_join_keys,
            "realized_lead_days",
            "shipment_row_count",
            "shipped_qty",
        ],
    )
    joined = risk.merge(
        shipment_summary,
        on=shipment_join_keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing_shipments = joined[joined["_merge"] != "both"]
    if not missing_shipments.empty:
        missing_days = ", ".join(str(value) for value in missing_shipments["day"].head(8))
        raise LeadTimeRealizationAuditError(
            "Designed lead-time records lack a matching realized shipment on days: "
            f"{missing_days} ({data_dir})."
        )

    baseline_multiplier = float(operating_baselines[condition])
    observations: list[dict[str, Any]] = []
    for source in joined.to_dict(orient="records"):
        edge_id = str(source["edge_id"])
        if edge_id not in nominal_by_edge:
            raise LeadTimeRealizationAuditError(
                f"Nominal lead time is unavailable for edge {edge_id}: {nominal_path}"
            )
        nominal_days = nominal_by_edge[edge_id]
        applied_multiplier = _strict_number(
            source["lead_time_multiplier"], "lead_time_multiplier", lower=0.05
        )
        extra_days = _strict_number(source["lead_time_extra_days"], "lead_time_extra_days")
        quality_delay_days = _strict_number(
            source["quality_delay_days"], "quality_delay_days"
        )
        ceil_days = max(
            1,
            int(math.ceil(nominal_days * applied_multiplier + extra_days + quality_delay_days)),
        )
        realized_days = int(source["realized_lead_days"])
        observations.append(
            {
                "cell_id": metadata["cell_id"],
                "requested_amplitude_percent": metadata["requested_amplitude_percent"],
                "requested_peak_fraction": metadata["requested_peak_fraction"],
                "phase_seed": metadata["phase_seed"],
                "condition": condition,
                "policy": policy,
                "seed": seed,
                "day": int(source["day"]),
                "supplier_id": str(source["supplier_id"]),
                "dst_node_id": str(source["dst_node_id"]),
                "item_id": str(source["item_id"]),
                "edge_id": edge_id,
                "nominal_lead_days": nominal_days,
                "operating_lead_time_baseline_multiplier": baseline_multiplier,
                "applied_lead_time_multiplier": applied_multiplier,
                "applied_fractional_excitation": (
                    applied_multiplier / baseline_multiplier - 1.0
                ),
                "lead_time_extra_days": extra_days,
                "quality_delay_days": quality_delay_days,
                "ceil_lead_days_before_lane_control": ceil_days,
                "realized_lead_days": realized_days,
                "realized_minus_nominal_days": realized_days - nominal_days,
                "ceil_rule_matches_realized": realized_days == ceil_days,
                "shipment_row_count": int(source["shipment_row_count"]),
                "shipped_qty": float(source["shipped_qty"]),
            }
        )
    return observations, [risk_path, shipment_path, nominal_path]


def _cell_summaries(observations: pd.DataFrame) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for cell_id, group in observations.groupby("cell_id", sort=True):
        realized_counts = {
            str(int(day)): int(count)
            for day, count in group["realized_lead_days"].value_counts().sort_index().items()
        }
        summaries.append(
            {
                "cell_id": str(cell_id),
                "requested_amplitude_percent": float(
                    group["requested_amplitude_percent"].iloc[0]
                ),
                "requested_peak_fraction": float(group["requested_peak_fraction"].iloc[0]),
                "phase_seed": int(group["phase_seed"].iloc[0]),
                "run_count": int(group[["condition", "policy", "seed"]].drop_duplicates().shape[0]),
                "observation_count": int(len(group)),
                "applied_multiplier_minimum": float(group["applied_lead_time_multiplier"].min()),
                "applied_multiplier_maximum": float(group["applied_lead_time_multiplier"].max()),
                "nominal_lead_days_values": sorted(
                    set(float(value) for value in group["nominal_lead_days"])
                ),
                "realized_lead_days_values": sorted(int(value) for value in realized_counts),
                "realized_lead_days_counts": realized_counts,
                "ceil_rule_matches_every_observation": bool(
                    group["ceil_rule_matches_realized"].astype(bool).all()
                ),
            }
        )
    return summaries


def _realization_comparisons(observations: pd.DataFrame) -> list[dict[str, Any]]:
    keys = [
        "condition",
        "policy",
        "seed",
        "day",
        "supplier_id",
        "dst_node_id",
        "item_id",
        "edge_id",
    ]
    comparisons: list[dict[str, Any]] = []
    cells = (
        observations[["cell_id", "requested_amplitude_percent", "phase_seed"]]
        .drop_duplicates()
        .sort_values(["phase_seed", "requested_amplitude_percent", "cell_id"])
        .to_dict(orient="records")
    )
    for left_index, left_meta in enumerate(cells):
        for right_meta in cells[left_index + 1 :]:
            if int(left_meta["phase_seed"]) != int(right_meta["phase_seed"]):
                continue
            left_amplitude = float(left_meta["requested_amplitude_percent"])
            right_amplitude = float(right_meta["requested_amplitude_percent"])
            if math.isclose(left_amplitude, right_amplitude, rel_tol=0.0, abs_tol=1e-12):
                continue
            left = observations[observations["cell_id"] == left_meta["cell_id"]]
            right = observations[observations["cell_id"] == right_meta["cell_id"]]
            if left.duplicated(keys).any() or right.duplicated(keys).any():
                raise LeadTimeRealizationAuditError(
                    "Each cell must have one realization observation per comparison key."
                )
            value_columns = [
                *keys,
                "applied_lead_time_multiplier",
                "ceil_lead_days_before_lane_control",
                "realized_lead_days",
            ]
            merged = left[value_columns].merge(
                right[value_columns],
                on=keys,
                how="outer",
                suffixes=("_left", "_right"),
                indicator=True,
                validate="one_to_one",
            )
            overlap = merged[merged["_merge"] == "both"].copy()
            realized_equal = (
                overlap["realized_lead_days_left"]
                == overlap["realized_lead_days_right"]
            )
            requested_multiplier_equal = (
                overlap["applied_lead_time_multiplier_left"]
                == overlap["applied_lead_time_multiplier_right"]
            )
            overlap_count = int(len(overlap))
            realized_mismatch_count = int((~realized_equal).sum())
            equivalent_on_overlap = overlap_count > 0 and realized_mismatch_count == 0
            same_keys = bool((merged["_merge"] == "both").all())
            comparisons.append(
                {
                    "phase_seed": int(left_meta["phase_seed"]),
                    "left_cell_id": str(left_meta["cell_id"]),
                    "left_requested_amplitude_percent": left_amplitude,
                    "right_cell_id": str(right_meta["cell_id"]),
                    "right_requested_amplitude_percent": right_amplitude,
                    "requested_amplitudes_distinct": True,
                    "left_observation_count": int(len(left)),
                    "right_observation_count": int(len(right)),
                    "overlap_observation_count": overlap_count,
                    "left_only_observation_count": int((merged["_merge"] == "left_only").sum()),
                    "right_only_observation_count": int((merged["_merge"] == "right_only").sum()),
                    "observation_keys_identical": same_keys,
                    "requested_multiplier_difference_observation_count": int(
                        (~requested_multiplier_equal).sum()
                    ),
                    "realized_lead_days_equal_observation_count": int(realized_equal.sum()),
                    "realized_lead_days_mismatch_observation_count": realized_mismatch_count,
                    "realized_input_equivalent_on_overlap": equivalent_on_overlap,
                    "realized_input_fully_equivalent": bool(
                        same_keys and equivalent_on_overlap
                    ),
                    "local_amplitude_conclusion_blocked": equivalent_on_overlap,
                    "blocking_reason": (
                        "distinct_requested_amplitudes_produced_identical_realized_lead_days_on_all_shared_observations"
                        if equivalent_on_overlap
                        else "realized_lead_days_differ_on_shared_observations"
                    ),
                }
            )
    return comparisons


def analyze_lead_time_realization(
    artifact_dirs: Sequence[str | Path],
) -> dict[str, Any]:
    """Read complete frequency cells and return realization evidence in memory."""

    resolved = [Path(value).resolve() for value in artifact_dirs]
    if not resolved:
        raise LeadTimeRealizationAuditError("At least one artifact directory is required.")
    if len(set(resolved)) != len(resolved):
        raise LeadTimeRealizationAuditError("Artifact directories must be unique.")

    observations: list[dict[str, Any]] = []
    source_paths: set[Path] = set()
    sources: list[dict[str, Any]] = []
    seen_cells: set[str] = set()
    for artifact_dir in resolved:
        metadata = _load_cell_metadata(artifact_dir)
        cell_id = str(metadata["cell_id"])
        if cell_id in seen_cells:
            raise LeadTimeRealizationAuditError(
                f"More than one artifact was supplied for cell {cell_id}."
            )
        seen_cells.add(cell_id)
        run_dirs = sorted(
            artifact_dir.glob(
                f"runs/*/excited/{TARGET_INPUT_SIGNAL}/*/seed_*/data"
            )
        )
        if not run_dirs:
            raise LeadTimeRealizationAuditError(
                f"No excited {TARGET_INPUT_SIGNAL} run exists in: {artifact_dir}"
            )
        cell_observations: list[dict[str, Any]] = []
        cell_sources = {
            Path(metadata["protocol_path"]),
            Path(metadata["manifest_path"]),
            Path(metadata["config_path"]),
        }
        for data_dir in run_dirs:
            run_observations, run_sources = _run_observations(metadata, data_dir)
            cell_observations.extend(run_observations)
            cell_sources.update(run_sources)
        if not cell_observations:
            raise LeadTimeRealizationAuditError(
                f"No realization observation was reconstructed for: {artifact_dir}"
            )
        observations.extend(cell_observations)
        source_paths.update(cell_sources)
        sources.append(
            {
                "cell_id": cell_id,
                "artifact_dir": str(artifact_dir),
                "requested_amplitude_percent": metadata["requested_amplitude_percent"],
                "phase_seed": metadata["phase_seed"],
                "source_file_count": len(cell_sources),
            }
        )

    detail_frame = pd.DataFrame(observations).sort_values(
        ["phase_seed", "requested_amplitude_percent", "cell_id", "condition", "policy", "day"]
    )
    cell_rows = _cell_summaries(detail_frame)
    comparison_rows = _realization_comparisons(detail_frame)
    comparable_count = len(comparison_rows)
    equivalent_count = sum(
        bool(row["realized_input_equivalent_on_overlap"])
        for row in comparison_rows
    )
    necessary_condition_met = comparable_count > 0 and equivalent_count == 0
    if equivalent_count:
        reason = (
            "Deux tailles de variation demandées ont produit exactement les mêmes "
            "délais entiers sur toutes les observations communes ; l'analyse locale "
            "est donc bloquée."
        )
    elif comparable_count == 0:
        reason = (
            "Aucune paire d'essais utilisant le même calendrier d'oscillation et deux "
            "tailles de variation différentes n'est disponible ; on ne peut donc pas "
            "vérifier que les entrées réellement appliquées sont distinctes."
        )
    else:
        reason = (
            "Les tailles de variation comparées ont produit des délais entiers différents. "
            "Cette condition est nécessaire, mais ne démontre pas à elle seule une "
            "relation locale entre une petite variation d'entrée et la réponse du système."
        )
    source_hashes = {str(path): _sha256(path) for path in sorted(source_paths)}
    return {
        "schema_version": SCHEMA_VERSION,
        "target_input_signal": TARGET_INPUT_SIGNAL,
        "realization_rule": (
            "ceil(nominal_lead_days * applied_lead_time_multiplier + "
            "lead_time_extra_days + quality_delay_days), before optional lane control"
        ),
        "comparison_scope": (
            "cells with equal phase_seed and distinct requested amplitude; equality is "
            "evaluated on shared condition/policy/seed/day/lane observations"
        ),
        "coverage": {
            "cell_count": len(cell_rows),
            "observation_count": int(len(detail_frame)),
            "comparable_distinct_amplitude_pair_count": comparable_count,
            "equivalent_realized_input_pair_count": equivalent_count,
        },
        "claims": {
            "source_artifacts_modified": False,
            "requested_amplitudes_realized_as_distinct_inputs": necessary_condition_met,
            "local_derivative_conclusion_blocked": not necessary_condition_met,
            "local_derivative_conclusion_blocked_by_identical_realized_input": bool(
                equivalent_count
            ),
            "local_derivative_claimed": False,
            "realized_input_distinctness_is_only_a_necessary_condition": True,
            "reason": reason,
        },
        "sources": sources,
        "source_file_sha256": source_hashes,
        "observations": detail_frame.to_dict(orient="records"),
        "cells": cell_rows,
        "comparisons": comparison_rows,
    }


_FIGURE_COMPARISON_KEYS = [
    "condition",
    "policy",
    "seed",
    "day",
    "supplier_id",
    "dst_node_id",
    "item_id",
    "edge_id",
]


def _select_figure_observations(
    observations: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Select one phase and the observations shared by its amplitude cells."""

    required = {
        "cell_id",
        "requested_amplitude_percent",
        "phase_seed",
        "condition",
        "policy",
        "day",
        "applied_lead_time_multiplier",
        "realized_lead_days",
        *_FIGURE_COMPARISON_KEYS,
    }
    _require_columns(observations, required, "lead-time realization figure input")
    if observations.empty:
        raise LeadTimeRealizationAuditError(
            "The lead-time realization figure requires at least one observation."
        )
    cells = observations[
        ["cell_id", "requested_amplitude_percent", "phase_seed"]
    ].drop_duplicates()
    phase_candidates = []
    for phase_seed, group in cells.groupby("phase_seed", sort=True):
        phase_candidates.append(
            {
                "phase_seed": int(phase_seed),
                "amplitude_count": int(group["requested_amplitude_percent"].nunique()),
                "cell_count": int(len(group)),
            }
        )
    chosen = sorted(
        phase_candidates,
        key=lambda row: (-row["amplitude_count"], -row["cell_count"], row["phase_seed"]),
    )[0]
    selected_cells = cells[cells["phase_seed"].eq(chosen["phase_seed"])].sort_values(
        ["requested_amplitude_percent", "cell_id"]
    )
    selected_ids = [str(value) for value in selected_cells["cell_id"]]
    selected = observations[observations["cell_id"].isin(selected_ids)].copy()

    common_index: pd.MultiIndex | None = None
    for cell_id in selected_ids:
        cell_index = pd.MultiIndex.from_frame(
            selected.loc[
                selected["cell_id"].eq(cell_id), _FIGURE_COMPARISON_KEYS
            ].drop_duplicates()
        )
        common_index = cell_index if common_index is None else common_index.intersection(cell_index)
    shared_key_count = len(common_index) if common_index is not None else 0
    common_scope_used = len(selected_ids) >= 2 and shared_key_count > 0
    if common_scope_used:
        common_keys = common_index.to_frame(index=False)
        common_keys.columns = _FIGURE_COMPARISON_KEYS
        selected = selected.merge(
            common_keys,
            on=_FIGURE_COMPARISON_KEYS,
            how="inner",
            validate="many_to_one",
        )

    conditions = sorted(str(value) for value in selected["condition"].unique())
    policies = sorted(str(value) for value in selected["policy"].unique())
    amplitudes = sorted(
        float(value) for value in selected["requested_amplitude_percent"].unique()
    )
    series: list[dict[str, Any]] = []
    for (condition, policy, cell_id), group in selected.groupby(
        ["condition", "policy", "cell_id"], sort=True
    ):
        series.append(
            {
                "condition": str(condition),
                "policy": str(policy),
                "cell_id": str(cell_id),
                "requested_amplitude_percent": float(
                    group["requested_amplitude_percent"].iloc[0]
                ),
                "observation_count": int(len(group)),
                "requested_multiplier_minimum": float(
                    group["applied_lead_time_multiplier"].min()
                ),
                "requested_multiplier_maximum": float(
                    group["applied_lead_time_multiplier"].max()
                ),
                "realized_lead_days_values": sorted(
                    int(value) for value in group["realized_lead_days"].unique()
                ),
            }
        )
    return selected.sort_values(
        ["condition", "policy", "requested_amplitude_percent", "day"]
    ), {
        "phase_seed": int(chosen["phase_seed"]),
        "source_cell_ids": selected_ids,
        "requested_amplitudes_percent": amplitudes,
        "conditions": conditions,
        "policies": policies,
        "comparison_uses_shared_observations": common_scope_used,
        "shared_observation_key_count_per_cell": int(shared_key_count),
        "plotted_observation_count": int(len(selected)),
        "metrics": ["applied_lead_time_multiplier", "realized_lead_days"],
        "requested_multiplier_source": (
            "supplier_risk_events_applied_daily.lead_time_multiplier"
        ),
        "series": series,
    }


def _condition_label(value: str) -> str:
    return {
        "nominal_capacity": "Capacité nominale",
        "supplier_stress_capacity": "Fournisseur sous tension",
    }.get(value, value.replace("_", " "))


def _policy_label(value: str) -> str:
    return {
        "canonical_feedback": "Boucle fermée V2",
        "mrp_reference": "MRP de référence",
    }.get(value, value.replace("_", " "))


def write_lead_time_realization_figure(
    observations: pd.DataFrame,
    path: str | Path,
) -> dict[str, Any]:
    """Write a readable requested-versus-realized PNG and return its semantics."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    selected, metadata = _select_figure_observations(observations)
    conditions = list(metadata["conditions"])
    amplitudes = list(metadata["requested_amplitudes_percent"])
    policies = list(metadata["policies"])
    colors = {
        amplitude: plt.get_cmap("tab10")(index % 10)
        for index, amplitude in enumerate(amplitudes)
    }
    markers = ("o", "x", "s", "^", "D", "v")
    marker_by_amplitude = {
        amplitude: markers[index % len(markers)]
        for index, amplitude in enumerate(amplitudes)
    }
    line_style_by_policy = {
        policy: ("-" if index == 0 else "--" if index == 1 else ":")
        for index, policy in enumerate(policies)
    }
    fig, axes = plt.subplots(
        len(conditions),
        2,
        figsize=(14.0, max(4.7, 3.9 * len(conditions))),
        squeeze=False,
        sharex="col",
    )
    for row_index, condition in enumerate(conditions):
        condition_frame = selected[selected["condition"].eq(condition)]
        multiplier_axis = axes[row_index, 0]
        lead_axis = axes[row_index, 1]
        for (amplitude, policy), group in condition_frame.groupby(
            ["requested_amplitude_percent", "policy"], sort=True
        ):
            amplitude = float(amplitude)
            policy = str(policy)
            group = group.sort_values("day")
            marker_every = max(1, int(math.ceil(len(group) / 32)))
            label = f"variation {amplitude:g} % · {_policy_label(policy)}"
            common_style = {
                "color": colors[amplitude],
                "linestyle": line_style_by_policy[policy],
                "linewidth": 1.15,
                "marker": marker_by_amplitude[amplitude],
                "markersize": 3.8,
                "markevery": marker_every,
                "alpha": 0.86,
                "label": label,
            }
            multiplier_axis.plot(
                group["day"],
                group["applied_lead_time_multiplier"],
                **common_style,
            )
            lead_axis.plot(
                group["day"],
                group["realized_lead_days"],
                drawstyle="steps-mid",
                **common_style,
            )
        condition_title = _condition_label(condition)
        multiplier_axis.set_title(
            f"{condition_title} — multiplicateur demandé au moteur"
        )
        lead_axis.set_title(f"{condition_title} — délai entier réalisé")
        multiplier_axis.set_ylabel("multiplicateur ×")
        lead_axis.set_ylabel("jours")
        lead_axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        for axis in (multiplier_axis, lead_axis):
            axis.set_xlabel("jour simulé")
            axis.grid(True, alpha=0.22, linewidth=0.7)
            axis.legend(loc="best", frameon=False, fontsize=8)
    scope = (
        "observations communes : "
        f"{metadata['shared_observation_key_count_per_cell']} pour chaque taille de variation"
        if metadata["comparison_uses_shared_observations"]
        else "toutes les observations disponibles"
    )
    fig.suptitle(
        "Délai fournisseur : multiplicateur continu, résultat en jours entiers\n"
        f"même calendrier d'oscillation (identifiant {metadata['phase_seed']}) · {scope}",
        fontsize=13,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.008,
        "Les points sont les expéditions perturbées. Une superposition à droite "
        "signifie que deux tailles de variation demandées deviennent le même délai entier.",
        fontsize=8,
        color="#475569",
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0.0, 0.035, 1.0, 0.94))
    fig.savefig(destination, dpi=170, bbox_inches="tight")
    plt.close(fig)
    metadata["filename"] = destination.name
    metadata["title"] = (
        "Délai fournisseur : multiplicateur continu, résultat en jours entiers"
    )
    return metadata


def _write_markdown_report(payload: Mapping[str, Any], path: Path) -> Path:
    claims = payload["claims"]
    figure = payload["figure"]
    comparisons = payload["comparisons"]
    amplitudes = ", ".join(
        f"{float(value):g} %" for value in figure["requested_amplitudes_percent"]
    )
    condition_lines = []
    for condition in figure["conditions"]:
        matching = [
            row for row in figure["series"] if row["condition"] == condition
        ]
        realized = sorted(
            {
                int(day)
                for row in matching
                for day in row["realized_lead_days_values"]
            }
        )
        condition_lines.append(
            f"- **{_condition_label(str(condition))}** : délais réalisés "
            + ", ".join(f"{value} j" for value in realized)
            + "."
        )
    comparison_lines = []
    for row in comparisons:
        decision = (
            "conclusion locale bloquée"
            if row["local_amplitude_conclusion_blocked"]
            else "entrées réalisées différentes, condition nécessaire seulement"
        )
        comparison_lines.append(
            "| "
            f"{float(row['left_requested_amplitude_percent']):g} % | "
            f"{float(row['right_requested_amplitude_percent']):g} % | "
            f"{int(row['overlap_observation_count'])} | "
            f"{int(row['realized_lead_days_mismatch_observation_count'])} | "
            f"{decision} |"
        )
    if not comparison_lines:
        comparison_lines.append("| — | — | 0 | — | comparaison indisponible |")
    if claims["local_derivative_conclusion_blocked_by_identical_realized_input"]:
        verdict = (
            "**Conclusion : l'analyse locale est bloquée.** Des tailles de variation "
            "demandées "
            "différentes ont produit exactement les mêmes délais entiers sur toutes "
            "les observations communes."
        )
    elif claims["local_derivative_conclusion_blocked"]:
        verdict = (
            "**Conclusion : l'analyse locale reste bloquée.** Il manque deux "
            "tailles de variation comparables utilisant le même calendrier d'oscillation."
        )
    else:
        verdict = (
            "**Conclusion : les entrées réalisées sont différentes.** Cette condition "
            "nécessaire est satisfaite, mais elle ne démontre pas à elle seule une "
            "relation locale entre l'entrée et la réponse du système."
        )
    report = f"""# Réalisation du délai fournisseur

Cet audit vérifie que deux tailles de variation demandées produisent bien des délais réellement différents dans le moteur, qui exprime les délais en jours entiers. Les fichiers de simulation sont lus sans être modifiés.

![Multiplicateur demandé et délai entier réalisé]({figure['filename']})

## Ce qui est comparé

- Tailles maximales des variations demandées : {amplitudes}.
- Même calendrier d'oscillation pour les deux essais (identifiant interne : {int(figure['phase_seed'])}).
- Mesures : multiplicateur transmis au moteur et délai entier observé sur les expéditions communes.

{chr(10).join(condition_lines)}

## Résultat de la comparaison

| Variation maximale 1 | Variation maximale 2 | Observations communes | Délais différents | Décision |
|---:|---:|---:|---:|---|
{chr(10).join(comparison_lines)}

{verdict}

Même lorsque les délais réalisés diffèrent, cet audit ne suffit pas à démontrer une relation locale entre une petite variation d'entrée et la réponse du système : il vérifie seulement une condition nécessaire.
"""
    path.write_text(report, encoding="utf-8")
    return path


def run_lead_time_realization_audit(
    artifact_dirs: Sequence[str | Path],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write a separate audit package without altering source artifacts."""

    resolved_sources = [Path(value).resolve() for value in artifact_dirs]
    destination = Path(output_dir).resolve()
    for source in resolved_sources:
        if destination == source or source in destination.parents:
            raise ValueError("output_dir must be outside every immutable source package.")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output: {destination}")

    result = analyze_lead_time_realization(resolved_sources)
    before_hashes = dict(result["source_file_sha256"])
    destination.mkdir(parents=True, exist_ok=True)
    detail_frame = pd.DataFrame(result.pop("observations"))
    cell_frame = pd.DataFrame(result["cells"])
    for column in (
        "nominal_lead_days_values",
        "realized_lead_days_values",
        "realized_lead_days_counts",
    ):
        cell_frame[column] = cell_frame[column].map(
            lambda value: json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    comparison_frame = pd.DataFrame(result["comparisons"])
    detail_path = destination / DETAIL_FILENAME
    cell_path = destination / CELL_FILENAME
    comparison_path = destination / COMPARISON_FILENAME
    json_path = destination / JSON_FILENAME
    figure_path = destination / FIGURE_FILENAME
    report_path = destination / REPORT_FILENAME
    detail_frame.to_csv(detail_path, index=False)
    cell_frame.to_csv(cell_path, index=False)
    comparison_frame.to_csv(comparison_path, index=False)
    result["figure"] = write_lead_time_realization_figure(detail_frame, figure_path)
    result["outputs"] = {
        "observations_csv": detail_path.name,
        "cells_csv": cell_path.name,
        "comparisons_csv": comparison_path.name,
        "figure_png": figure_path.name,
        "report_markdown": report_path.name,
    }
    _write_markdown_report(result, report_path)
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    after_hashes = {path: _sha256(Path(path)) for path in before_hashes}
    if after_hashes != before_hashes:
        raise LeadTimeRealizationAuditError(
            "A source file changed while the realization audit was being written."
        )
    return {
        "json_path": json_path,
        "observations_csv_path": detail_path,
        "cells_csv_path": cell_path,
        "comparisons_csv_path": comparison_path,
        "figure_path": figure_path,
        "report_path": report_path,
        "payload": result,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--campaign-dir",
        type=Path,
        help="Discover complete lead-time frequency cells below this directory.",
    )
    source.add_argument(
        "--artifact-dir",
        action="append",
        type=Path,
        help="Complete cell artifact directory; repeat for amplitude comparison.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dirs = (
        discover_artifact_dirs(args.campaign_dir)
        if args.campaign_dir is not None
        else list(args.artifact_dir or ())
    )
    result = run_lead_time_realization_audit(artifact_dirs, args.output_dir)
    print(result["json_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CELL_FILENAME",
    "COMPARISON_FILENAME",
    "DETAIL_FILENAME",
    "FIGURE_FILENAME",
    "JSON_FILENAME",
    "LeadTimeRealizationAuditError",
    "REPORT_FILENAME",
    "SCHEMA_VERSION",
    "TARGET_INPUT_SIGNAL",
    "analyze_lead_time_realization",
    "discover_artifact_dirs",
    "run_lead_time_realization_audit",
    "write_lead_time_realization_figure",
]
