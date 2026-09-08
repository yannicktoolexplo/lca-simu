from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import math
import re
import shutil
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence


DEMO_SCHEMA_VERSION = "etudecas.industrial_cascade_demo.v2"
CASCADE_SUMMARY_SCHEMA_VERSION = "scan.canonical_cascade_summary.v2"
CAMPAIGN_MANIFEST_SCHEMA_VERSION = "scan.canonical_cascade_manifest.v2"
TRAJECTORY_SCHEMA_VERSION = "scan.canonical_cascade_trajectory_envelopes.v1"
TRAJECTORY_MANIFEST_SCHEMA_VERSION = "scan.canonical_cascade_trajectory_manifest.v1"
RISK_PROVENANCE_SCHEMA_VERSION = "risk-lot-impact-provenance/1.0"
TRAJECTORY_LONG_NAME = "canonical_cascade_trajectories_long.csv"
PLOTLY_CDN_URL = "https://cdn.plot.ly/plotly-2.32.0.min.js"
PLOTLY_VERSION = "2.32.0"
PLOTLY_SHA256 = "0a17719a72751704861215da0e5c5cdb3f9a8d50eff5cb84cb6f8b80786682b0"
PLOTLY_MIN_BYTES = 3_000_000
PLOTLY_MAX_BYTES = 4_500_000
WORLD_TOPOJSON_NAME = "world_110m.json"
WORLD_TOPOJSON_SHA256 = (
    "d75915eaa31c870df6b972c9e5bb86910197825f33dcfef740f3b2f68cffe843"
)
WORLD_TOPOJSON_MIN_BYTES = 100_000

RISK_REGISTRY_CSV_FILENAMES = {
    "incidents": "risk_impact_incidents.csv",
    "bundles": "risk_impact_exposure_bundles.csv",
    "bundle_events": "risk_impact_bundle_events.csv",
    "entities": "risk_impact_entities.csv",
    "edges": "risk_impact_edges.csv",
    "client_service": "risk_impact_client_service.csv",
    "costs": "risk_impact_costs.csv",
}

CASCADE_RUN_FIELDS = {
    "cascade_id",
    "variant_id",
    "case_type",
    "solution_id",
    "seed",
    "status",
    "result_dir",
    "customer_id",
    "finished_item_id",
    "customer_shortage_days",
    "customer_backlog_qty_days",
    "recovery_day",
    "customer_demand_qty",
    "customer_served_qty",
    "production_qty",
    "production_lot_count",
    "target_stock_qty_days",
    "base_operational_supply_cost",
    "controllable_operating_cost",
    "decision_total_cost",
    "decision_transport_cost",
    "external_purchase_cost",
    "supplier_risk_applied_row_count",
    "supplier_risk_applied_event_ids",
    "action_execution_status",
    "measurement_start_state_sha256",
    "measurement_start_component_sha256_json",
    "risk_events_sha256",
    "graph_sha256",
    "engine_profile_sha256",
    "pairing_status",
    "incident_validation_status",
}

CASCADE_COMPARISON_FIELDS = {
    "cascade_id",
    "solution_id",
    "variant_id",
    "seed",
    "lever_fidelity",
    "pairing_status",
    "incident_application_verified",
    "incident_signal_detected",
    "customer_exposure_detected",
    "customer_exposure_status",
    "ranking_eligible",
    "ranking_exclusion_reasons",
    "days_recovered_vs_no_action",
    "recovery_status",
    "shortage_days_avoided",
    "gross_positive_customer_service_gain_qty",
    "net_customer_service_gain_qty",
    "gross_positive_production_gain_qty",
    "net_production_gain_qty",
    "gross_positive_production_lot_equivalent",
    "gross_additional_mrp_release_qty",
    "net_mrp_release_qty",
    "incremental_decision_total_cost_vs_no_action",
    "incremental_controllable_operating_cost_vs_no_action",
    "incremental_decision_transport_cost_vs_no_action",
    "incremental_external_purchase_cost_vs_no_action",
    "incremental_stock_qty_days",
    "no_action_incremental_customer_backlog_qty_days",
    "remaining_customer_impact_ratio",
    "remaining_incremental_customer_backlog_qty_days",
    "action_execution_status",
    "evidence_notes",
}

METRICS = (
    "days_recovered_vs_no_action",
    "shortage_days_avoided",
    "gross_positive_customer_service_gain_qty",
    "net_customer_service_gain_qty",
    "gross_positive_production_gain_qty",
    "net_production_gain_qty",
    "gross_positive_production_lot_equivalent",
    "gross_additional_mrp_release_qty",
    "net_mrp_release_qty",
    "incremental_decision_total_cost_vs_no_action",
    "incremental_controllable_operating_cost_vs_no_action",
    "incremental_decision_transport_cost_vs_no_action",
    "incremental_external_purchase_cost_vs_no_action",
    "incremental_stock_qty_days",
    "no_action_incremental_customer_backlog_qty_days",
    "remaining_customer_impact_ratio",
    "remaining_incremental_customer_backlog_qty_days",
)


@dataclass(frozen=True)
class IndustrialDemoArtifacts:
    output_dir: Path
    index_path: Path
    manifest_path: Path
    copied_assets: tuple[Path, ...]


@dataclass(frozen=True)
class RiskRegistryEvidence:
    source: str
    directory: Path
    incidents: tuple[dict[str, str], ...]
    entities: tuple[dict[str, str], ...]
    client_service: tuple[dict[str, str], ...]
    costs: tuple[dict[str, str], ...]
    bundle_events: tuple[dict[str, str], ...]
    quality: dict[str, Any]
    provenance: dict[str, Any]
    output_integrity: dict[str, Any]


def _prepare_output(path: Path) -> Path:
    output = path.resolve()
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(
                f"La sortie existe deja et n'est pas un dossier: {output}"
            )
        if any(output.iterdir()):
            raise FileExistsError(f"Refus d'ecraser un dossier non vide: {output}")
    else:
        output.mkdir(parents=True, exist_ok=False)
    return output


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(
        not isinstance(row, dict) for row in payload
    ):
        raise ValueError(f"Tableau d'objets JSON attendu: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_mapping(
    parent: dict[str, Any], key: str, *, context: str
) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Objet {key!r} absent ou invalide dans {context}")
    return value


def _require_declared_path(
    metadata: dict[str, Any],
    key: str,
    expected: Path,
    *,
    context: str,
) -> None:
    raw = str(metadata.get(key) or "").strip()
    if not raw:
        raise ValueError(f"Chemin {key!r} absent dans {context}")
    declared = Path(raw).resolve()
    resolved_expected = expected.resolve()
    if declared != resolved_expected:
        raise ValueError(
            f"Chemin {key!r} incohérent dans {context}: "
            f"{declared} au lieu de {resolved_expected}"
        )


def _require_declared_hash(
    metadata: dict[str, Any],
    key: str,
    artifact: Path,
    *,
    context: str,
) -> str:
    declared = str(metadata.get(key) or "").strip()
    if not declared:
        raise ValueError(f"Empreinte {key!r} absente dans {context}")
    observed = _sha256(artifact)
    if declared != observed:
        raise ValueError(
            f"Empreinte {key!r} incohérente dans {context}: "
            f"déclarée={declared}, observée={observed}"
        )
    return observed


def _strict_nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Entier non negatif attendu pour {label}: {value!r}")
    try:
        number = float(value)
        parsed = int(number)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Entier non negatif attendu pour {label}: {value!r}") from exc
    if not math.isfinite(number) or number != parsed or parsed < 0:
        raise ValueError(f"Entier non negatif attendu pour {label}: {value!r}")
    return parsed


def _strict_sha256(value: Any, *, label: str) -> str:
    digest = str(value or "").strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError(f"Empreinte SHA-256 invalide pour {label}: {value!r}")
    return digest


def _csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _row in csv.DictReader(handle))


def _component_hashes(value: Any, *, label: str) -> dict[str, str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Objet JSON invalide pour {label}") from exc
    else:
        parsed = value
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError(f"Empreintes composantes absentes ou invalides pour {label}")
    return {
        str(name): _strict_sha256(digest, label=f"{label}.{name}")
        for name, digest in sorted(parsed.items())
    }


_PROFILE_DEPENDENT_TRACE_COMPONENTS = frozenset({"lot_ledger", "lot_arrivals_pipeline"})


def _validate_measurement_start_pairing(
    *,
    registry_source: str,
    provenance_state_hash: str,
    trace_state_hash: str,
    final_state_hash: str,
    provenance_components: dict[str, str],
    trace_components: dict[str, str],
    final_components: dict[str, str],
    trace_artifact_profile: str,
    final_artifact_profile: str,
    trace_row: Mapping[str, Any],
    final_row: Mapping[str, Any],
) -> dict[str, Any]:
    if provenance_state_hash != trace_state_hash:
        raise ValueError(f"Etat J0 non apparie pour {registry_source}")
    if provenance_components != trace_components:
        raise ValueError(
            f"Composantes de l'etat J0 non appariees pour {registry_source}"
        )
    if trace_state_hash == final_state_hash and trace_components == final_components:
        return {
            "mode": "exact_full_state_hash",
            "full_trace_state_sha256": trace_state_hash,
            "final_state_sha256": final_state_hash,
            "core_component_sha256": trace_components,
            "profile_dependent_components": {},
        }

    if trace_artifact_profile != "full" or final_artifact_profile != "compact":
        raise ValueError(f"Etat J0 non apparie pour {registry_source}")
    if set(trace_components) != set(final_components):
        raise ValueError(
            f"Composantes de l'etat J0 non appariees pour {registry_source}"
        )
    mismatched_components = {
        name
        for name in trace_components
        if trace_components[name] != final_components[name]
    }
    if not mismatched_components or not mismatched_components.issubset(
        _PROFILE_DEPENDENT_TRACE_COMPONENTS
    ):
        raise ValueError(
            f"Composantes de l'etat J0 non appariees pour {registry_source}"
        )
    core_components = {
        name: digest
        for name, digest in trace_components.items()
        if name not in _PROFILE_DEPENDENT_TRACE_COMPONENTS
    }
    if not core_components:
        raise ValueError(
            f"Composantes de l'etat J0 non appariees pour {registry_source}"
        )

    allowed_row_differences = {
        "result_dir",
        "measurement_start_state_sha256",
        "measurement_start_component_sha256_json",
    }
    outcome_differences = {
        field
        for field in set(trace_row) | set(final_row)
        if field not in allowed_row_differences
        and str(trace_row.get(field) or "") != str(final_row.get(field) or "")
    }
    if outcome_differences:
        raise ValueError(
            f"Resultats full-trace et compacts non apparies pour {registry_source}: "
            f"{sorted(outcome_differences)}"
        )

    return {
        "mode": "same_physical_core_across_full_and_compact_profiles",
        "full_trace_state_sha256": trace_state_hash,
        "final_state_sha256": final_state_hash,
        "core_component_sha256": core_components,
        "profile_dependent_components": {
            name: {
                "full_trace_sha256": trace_components[name],
                "compact_sha256": final_components[name],
            }
            for name in sorted(mismatched_components)
        },
    }


def _verified_metadata_file(
    metadata: dict[str, Any],
    *,
    expected: Path,
    context: str,
) -> str:
    _require_declared_path(metadata, "path", expected, context=context)
    return _require_declared_hash(metadata, "sha256", expected, context=context)


def _manifest_dependency_hash(
    manifest: dict[str, Any],
    key: str,
    *,
    context: str,
) -> str:
    metadata = _required_mapping(manifest, key, context=context)
    digest = _strict_sha256(metadata.get("sha256"), label=f"{context}.{key}")
    path_value = (
        metadata.get("source_path") or metadata.get("path")
        if key == "engine_profile"
        else metadata.get("path")
    )
    raw_path = str(path_value or "").strip()
    if not raw_path:
        raise ValueError(f"Chemin absent pour {context}.{key}")
    path = Path(raw_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = _sha256(path)
    if observed != digest:
        raise ValueError(
            f"Empreinte incoherente pour {context}.{key}: declaree={digest}, observee={observed}"
        )
    return observed


def _validate_cascade_and_campaign_integrity(
    *,
    cascade_dir: Path,
    runs_path: Path,
    comparisons_path: Path,
    runs: Sequence[dict[str, str]],
    comparisons: Sequence[dict[str, str]],
    summary: dict[str, Any],
) -> tuple[Path, Path, dict[str, Any]]:
    """Recheck every hash/status emitted by the campaign and comparator."""

    if summary.get("schema_version") != CASCADE_SUMMARY_SCHEMA_VERSION:
        raise ValueError(
            "Version du résumé de comparaison inattendue: "
            f"{summary.get('schema_version')!r}"
        )
    if summary.get("comparison_row_count") != len(comparisons):
        raise ValueError(
            "Nombre de comparaisons incohérent dans le résumé: "
            f"{summary.get('comparison_row_count')!r} au lieu de {len(comparisons)}"
        )

    summary_outputs = _required_mapping(summary, "outputs", context=str(cascade_dir))
    _require_declared_path(
        summary_outputs,
        "runs_csv",
        runs_path,
        context="le résumé de comparaison",
    )
    summary_runs_hash = _require_declared_hash(
        summary_outputs,
        "runs_csv_sha256",
        runs_path,
        context="le résumé de comparaison",
    )
    _require_declared_path(
        summary_outputs,
        "comparison_csv",
        comparisons_path,
        context="le résumé de comparaison",
    )
    comparison_hash = _require_declared_hash(
        summary_outputs,
        "comparison_csv_sha256",
        comparisons_path,
        context="le résumé de comparaison",
    )

    campaign_metadata = _required_mapping(
        summary, "campaign", context="le résumé de comparaison"
    )
    campaign_raw = str(campaign_metadata.get("path") or "").strip()
    if not campaign_raw:
        raise ValueError("Le résumé ne référence pas la campagne physique source")
    campaign_source = Path(campaign_raw).resolve()
    if not campaign_source.is_dir():
        raise FileNotFoundError(campaign_source)
    manifest_path = campaign_source / "canonical_cascade_manifest.json"
    campaign_runs_path = campaign_source / "canonical_cascade_runs.csv"
    commands_path = campaign_source / "canonical_cascade_commands.json"
    config_snapshot_path = campaign_source / "canonical_cascade_config_snapshot.json"

    _require_declared_path(
        campaign_metadata,
        "manifest",
        manifest_path,
        context="le résumé de comparaison",
    )
    manifest_hash = _require_declared_hash(
        campaign_metadata,
        "manifest_sha256",
        manifest_path,
        context="le résumé de comparaison",
    )
    _require_declared_path(
        campaign_metadata,
        "runs",
        campaign_runs_path,
        context="le résumé de comparaison",
    )
    campaign_runs_hash = _require_declared_hash(
        campaign_metadata,
        "runs_sha256",
        campaign_runs_path,
        context="le résumé de comparaison",
    )
    if summary_runs_hash != campaign_runs_hash:
        raise ValueError(
            "La copie des simulations comparées n'est plus identique aux simulations de campagne"
        )
    if campaign_metadata.get("status") != "complete":
        raise ValueError(
            "Le résumé référence une campagne non terminée: "
            f"{campaign_metadata.get('status')!r}"
        )

    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != CAMPAIGN_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "Version du manifeste de campagne inattendue: "
            f"{manifest.get('schema_version')!r}"
        )
    if manifest.get("status") != "complete":
        raise ValueError(
            f"Campagne non terminée dans le manifeste: {manifest.get('status')!r}"
        )
    if manifest.get("failure_count") != 0:
        raise ValueError(
            "La campagne contient des échecs: "
            f"failure_count={manifest.get('failure_count')!r}"
        )
    if manifest.get("skipped_fail_fast_count") != 0:
        raise ValueError(
            "La campagne contient des simulations non lancées après échec: "
            f"skipped_fail_fast_count={manifest.get('skipped_fail_fast_count')!r}"
        )

    manifest_outputs = _required_mapping(
        manifest, "outputs", context="le manifeste de campagne"
    )
    for key, artifact in (
        ("runs", campaign_runs_path),
        ("commands", commands_path),
        ("config_snapshot", config_snapshot_path),
    ):
        _require_declared_path(
            manifest_outputs,
            key,
            artifact,
            context="le manifeste de campagne",
        )
    output_hashes = _required_mapping(
        manifest, "output_sha256", context="le manifeste de campagne"
    )
    campaign_artifact_hashes = {
        key: _require_declared_hash(
            output_hashes,
            key,
            artifact,
            context="le manifeste de campagne",
        )
        for key, artifact in (
            ("runs", campaign_runs_path),
            ("commands", commands_path),
            ("config_snapshot", config_snapshot_path),
        )
    }
    config_metadata = _required_mapping(
        manifest, "config", context="le manifeste de campagne"
    )
    _require_declared_path(
        config_metadata,
        "snapshot",
        config_snapshot_path,
        context="le manifeste de campagne",
    )
    _require_declared_hash(
        config_metadata,
        "sha256",
        config_snapshot_path,
        context="le manifeste de campagne",
    )

    campaign_runs = _read_csv(campaign_runs_path)
    commands = _read_json_array(commands_path)
    if manifest.get("run_count") != len(campaign_runs) or len(commands) != len(
        campaign_runs
    ):
        raise ValueError(
            "Nombre de simulations incohérent entre manifeste, commandes et résultats: "
            f"manifeste={manifest.get('run_count')!r}, commandes={len(commands)}, "
            f"résultats={len(campaign_runs)}"
        )
    invalid_statuses = sorted(
        {
            str(row.get("status") or "")
            for row in campaign_runs
            if row.get("status") != "ok"
        }
    )
    if invalid_statuses:
        raise ValueError(
            "La campagne contient des simulations physiques non valides: "
            + ", ".join(invalid_statuses)
        )
    if len(campaign_runs) != len(runs):
        raise ValueError(
            "La comparaison ne contient pas toutes les simulations de la campagne: "
            f"{len(runs)} sur {len(campaign_runs)}"
        )

    return (
        campaign_source,
        config_snapshot_path,
        {
            "cascade_summary_verified": True,
            "campaign_manifest_verified": True,
            "campaign_manifest_sha256": manifest_hash,
            "campaign_runs_sha256": campaign_artifact_hashes["runs"],
            "campaign_commands_sha256": campaign_artifact_hashes["commands"],
            "campaign_config_snapshot_sha256": campaign_artifact_hashes[
                "config_snapshot"
            ],
            "comparison_csv_sha256": comparison_hash,
        },
    )


def _cascade_contracts(config_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_cascades = config_snapshot.get("cascades")
    if not isinstance(raw_cascades, list) or not raw_cascades:
        raise ValueError("Le snapshot de configuration ne contient aucune cascade")
    contracts: dict[str, dict[str, Any]] = {}
    for raw in raw_cascades:
        if not isinstance(raw, dict):
            raise ValueError("Définition de cascade invalide dans le snapshot")
        cascade_id = str(raw.get("id") or "").strip()
        if not cascade_id:
            raise ValueError("Identifiant de cascade absent du snapshot")
        if cascade_id in contracts:
            raise ValueError(f"Cascade dupliquée dans le snapshot: {cascade_id}")
        solutions = raw.get("solutions")
        if not isinstance(solutions, list) or not solutions:
            raise ValueError(f"Aucune solution configurée pour {cascade_id}")
        solution_ids = [
            str(solution.get("id") or "").strip()
            for solution in solutions
            if isinstance(solution, dict)
        ]
        if (
            len(solution_ids) != len(solutions)
            or any(not solution_id for solution_id in solution_ids)
            or len(solution_ids) != len(set(solution_ids))
        ):
            raise ValueError(f"Solutions invalides ou dupliquées pour {cascade_id}")
        customer_id = str(raw.get("customer_id") or "").strip()
        finished_item_id = str(raw.get("finished_item_id") or "").strip()
        incident = raw.get("incident")
        risk_events = (
            incident.get("risk_events") if isinstance(incident, dict) else None
        )
        if not customer_id or not finished_item_id:
            raise ValueError(f"Client ou produit fini absent pour {cascade_id}")
        if not isinstance(risk_events, list) or not risk_events:
            raise ValueError(f"Incident sans événement de risque pour {cascade_id}")
        contracts[cascade_id] = raw
    return contracts


def _require_columns(
    rows: list[dict[str, str]], required: set[str], source: Path
) -> None:
    if not rows:
        raise ValueError(f"Table vide: {source}")
    missing = sorted(required.difference(rows[0]))
    if missing:
        raise ValueError(f"Colonnes manquantes dans {source}: {', '.join(missing)}")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "n/a", "na"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "oui",
        "verified",
        "verifie",
    }


def _strict_bool(value: Any, *, label: str) -> bool:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "oui"}:
        return True
    if normalized in {"0", "false", "no", "non"}:
        return False
    raise ValueError(f"Booléen invalide pour {label}: {value!r}")


def _validate_campaign_evidence(
    runs: Sequence[dict[str, str]],
    comparisons: Sequence[dict[str, str]],
    *,
    minimum_seed_count: int,
    expected_solution_ids: dict[str, set[str]],
    require_positive_customer_exposure: bool = True,
) -> dict[str, Any]:
    if minimum_seed_count < 1:
        raise ValueError("minimum_seed_count doit être positif")
    run_keys: set[tuple[str, str, str]] = set()
    solution_runs: dict[tuple[str, str, str], dict[str, str]] = {}
    hashes: dict[tuple[str, str], set[str]] = defaultdict(set)
    normal_counts: dict[tuple[str, str], int] = defaultdict(int)
    no_action_counts: dict[tuple[str, str], int] = defaultdict(int)
    no_action_runs: dict[tuple[str, str], dict[str, str]] = {}
    solution_roles: dict[tuple[str, str], set[str]] = defaultdict(set)
    seeds_by_cascade: dict[str, set[str]] = defaultdict(set)
    healthy_normal_run_count = 0
    for row in runs:
        key = (
            str(row.get("cascade_id") or ""),
            str(row.get("variant_id") or ""),
            str(row.get("seed") or ""),
        )
        if key in run_keys:
            raise ValueError(f"Simulation dupliquée: {key}")
        run_keys.add(key)
        if str(row.get("status") or "") != "ok":
            raise ValueError(
                f"Simulation incomplète interdite dans la démonstration: {key}"
            )
        cascade_id, _, seed = key
        if cascade_id not in expected_solution_ids:
            raise ValueError(f"Simulation hors configuration: {key}")
        if not key[1] or not seed:
            raise ValueError(f"Identifiant de variante ou graine absent: {key}")
        try:
            normalized_seed = int(seed)
        except ValueError as exc:
            raise ValueError(f"Graine invalide: {key}") from exc
        if normalized_seed < 0 or str(normalized_seed) != seed:
            raise ValueError(f"Graine invalide: {key}")
        seeds_by_cascade[cascade_id].add(seed)
        case_type = str(row.get("case_type") or "")
        pair = (cascade_id, seed)
        if case_type == "normal":
            normal_counts[pair] += 1
        elif case_type == "incident_no_action":
            no_action_counts[pair] += 1
            no_action_runs[pair] = row
        elif case_type == "incident_with_solution":
            solution_id = str(row.get("solution_id") or "").strip()
            if solution_id not in expected_solution_ids[cascade_id]:
                raise ValueError(
                    f"Solution simulée absente de la configuration: {cascade_id}/{solution_id}/{seed}"
                )
            solution_key = (cascade_id, solution_id, seed)
            if solution_key in solution_runs:
                raise ValueError(f"Simulation de solution dupliquée: {solution_key}")
            solution_runs[solution_key] = row
            solution_roles[pair].add(solution_id)
        else:
            raise ValueError(
                f"Type de cas inconnu dans la campagne: {key}, {case_type!r}"
            )
        state_hash = str(row.get("measurement_start_state_sha256") or "").strip()
        if not state_hash:
            raise ValueError(f"Empreinte J0 absente: {key}")
        hashes[(cascade_id, seed)].add(state_hash)
        if str(row.get("pairing_status") or "") != "measurement_start_state_matched":
            raise ValueError(f"État J0 non apparié: {key}")
        if str(row.get("case_type") or "") == "normal":
            shortage_days = _to_float(row.get("customer_shortage_days"))
            backlog_qty_days = _to_float(row.get("customer_backlog_qty_days"))
            demand_qty = _to_float(row.get("customer_demand_qty"))
            served_qty = _to_float(row.get("customer_served_qty"))
            if None in {shortage_days, backlog_qty_days, demand_qty, served_qty}:
                raise ValueError(f"Santé du fonctionnement normal non mesurable: {key}")
            if (
                shortage_days > 1e-9
                or backlog_qty_days > 1e-6
                or demand_qty <= 0.0
                or served_qty + 1e-6 < demand_qty
            ):
                raise ValueError(
                    "Fonctionnement normal déjà dégradé: "
                    f"{key}, jours de rupture={shortage_days}, "
                    f"retard cumulé={backlog_qty_days}, servi={served_qty}/{demand_qty}"
                )
            healthy_normal_run_count += 1
    for pair, values in hashes.items():
        if len(values) != 1:
            raise ValueError(f"États J0 différents pour {pair}: {sorted(values)}")
    if set(seeds_by_cascade) != set(expected_solution_ids):
        raise ValueError(
            "Les cascades simulées diffèrent du snapshot: "
            f"{sorted(seeds_by_cascade)} vs {sorted(expected_solution_ids)}"
        )
    for cascade_id, seeds in seeds_by_cascade.items():
        if len(seeds) < minimum_seed_count:
            raise ValueError(
                f"{cascade_id}: {len(seeds)} répétitions, minimum requis {minimum_seed_count}"
            )
        for seed in seeds:
            pair = (cascade_id, seed)
            if normal_counts[pair] != 1 or no_action_counts[pair] != 1:
                raise ValueError(
                    f"Référence normale ou incident sans action non unique pour "
                    f"{cascade_id}/graine {seed}"
                )
            if solution_roles[pair] != expected_solution_ids[cascade_id]:
                raise ValueError(
                    f"Grille de solutions incomplète pour {cascade_id}/graine {seed}: "
                    f"{sorted(solution_roles[pair])} vs "
                    f"{sorted(expected_solution_ids[cascade_id])}"
                )

    comparison_keys: set[tuple[str, str, str]] = set()
    for row in comparisons:
        cascade_id = str(row.get("cascade_id") or "")
        solution_id = str(row.get("solution_id") or "")
        seed = str(row.get("seed") or "")
        key = (cascade_id, solution_id, seed)
        if key in comparison_keys:
            raise ValueError(f"Comparaison dupliquée: {key}")
        comparison_keys.add(key)
        source_run = solution_runs.get(key)
        if source_run is None:
            raise ValueError(
                f"Comparaison sans simulation de solution correspondante: {key}"
            )
        if str(row.get("variant_id") or "") != str(source_run.get("variant_id") or ""):
            raise ValueError(f"Variante de comparaison incohérente: {key}")
        if str(row.get("pairing_status") or "") != "measurement_start_state_matched":
            raise ValueError(
                f"Comparaison sans preuve J0: {cascade_id}/{solution_id}/{seed}"
            )
        if not _truthy(row.get("incident_application_verified")):
            raise ValueError(
                f"Incident non appliqué: {cascade_id}/{solution_id}/{seed}"
            )
        incident_signal = _strict_bool(
            row.get("incident_signal_detected"),
            label=f"incident_signal_detected {key}",
        )
        customer_exposure = _strict_bool(
            row.get("customer_exposure_detected"),
            label=f"customer_exposure_detected {key}",
        )
        if incident_signal != customer_exposure:
            raise ValueError(f"Indicateurs d'exposition client incohérents: {key}")
        expected_exposure_status = (
            "customer_exposed" if customer_exposure else "absorbed_before_customer"
        )
        if str(row.get("customer_exposure_status") or "") != expected_exposure_status:
            raise ValueError(f"Statut d'exposition client incohérent: {key}")
        untreated = no_action_runs.get((cascade_id, seed))
        expected_incident_status = (
            "physically_applied_with_customer_exposure"
            if customer_exposure
            else "physically_applied_no_customer_exposure"
        )
        if (
            untreated is None
            or str(untreated.get("incident_validation_status") or "")
            != expected_incident_status
        ):
            raise ValueError(f"Preuve campagne de l'exposition incohérente: {key}")
        if not customer_exposure and require_positive_customer_exposure:
            raise ValueError(
                f"Effet client non détecté: {cascade_id}/{solution_id}/{seed}"
            )
        if not customer_exposure:
            if _truthy(row.get("ranking_eligible")):
                raise ValueError(f"Cas sans exposition client classé à tort: {key}")
            if _to_float(row.get("days_recovered_vs_no_action")) is not None:
                raise ValueError(
                    f"Jours récupérés inventés sans exposition client: {key}"
                )
            if str(row.get("recovery_status") or "") != (
                "untreated_incident_absorbed_before_customer"
            ):
                raise ValueError(
                    f"Statut de récupération incohérent sans exposition: {key}"
                )
        if _truthy(row.get("ranking_eligible")):
            missing_metrics = [
                field for field in METRICS if _to_float(row.get(field)) is None
            ]
            if missing_metrics:
                raise ValueError(
                    f"Solution classable avec métriques absentes pour {key}: "
                    + ", ".join(missing_metrics)
                )
    if comparison_keys != set(solution_runs):
        missing = sorted(set(solution_runs) - comparison_keys)
        unexpected = sorted(comparison_keys - set(solution_runs))
        raise ValueError(
            "Grille de comparaisons différente des simulations de solution: "
            f"manquantes={missing[:5]}, inattendues={unexpected[:5]}"
        )
    return {
        "cascade_count": len(seeds_by_cascade),
        "minimum_seed_count": min(len(values) for values in seeds_by_cascade.values()),
        "seed_count_by_cascade": {
            cascade_id: len(seeds)
            for cascade_id, seeds in sorted(seeds_by_cascade.items())
        },
        "j0_pair_count": len(hashes),
        "j0_identical": True,
        "healthy_normal_run_count": healthy_normal_run_count,
        "normal_operation_healthy": True,
        "customer_exposure_count_by_cascade": {
            cascade_id: sum(
                1
                for row in comparisons
                if str(row.get("cascade_id") or "") == cascade_id
                and str(row.get("solution_id") or "")
                == sorted(expected_solution_ids[cascade_id])[0]
                and _strict_bool(
                    row.get("customer_exposure_detected"),
                    label="customer_exposure_detected",
                )
            )
            for cascade_id in sorted(seeds_by_cascade)
        },
    }


def _load_trajectory_payload(
    trajectory_dir: Path,
) -> tuple[dict[str, Any], Path, Path, dict[str, Any]]:
    directory = trajectory_dir.resolve()
    compact_path = directory / "canonical_cascade_trajectories_compact.json"
    manifest_path = directory / "canonical_cascade_trajectories_manifest.json"
    payload = _read_json(compact_path)
    if payload.get("schema_version") != TRAJECTORY_SCHEMA_VERSION:
        raise ValueError(
            f"Version de trajectoires inattendue: {payload.get('schema_version')!r}"
        )
    if not isinstance(payload.get("day_axis"), list) or not payload["day_axis"]:
        raise ValueError("Axe journalier des trajectoires absent")
    if not isinstance(payload.get("cascades"), dict) or not payload["cascades"]:
        raise ValueError("Trajectoires de cascade absentes")
    manifest = _read_json(manifest_path)
    return payload, compact_path, manifest_path, manifest


def _validate_trajectory_integrity(
    *,
    trajectory_dir: Path,
    payload: dict[str, Any],
    compact_path: Path,
    manifest: dict[str, Any],
    config_snapshot_path: Path,
    campaign_runs_path: Path,
    expected_run_count: int,
    expected_cascade_ids: set[str],
) -> dict[str, Any]:
    """Verify the trajectory export against its source campaign and output files."""

    if manifest.get("schema_version") != TRAJECTORY_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "Version du manifeste de trajectoires inattendue: "
            f"{manifest.get('schema_version')!r}"
        )
    if manifest.get("status") != "complete":
        raise ValueError(
            f"Export de trajectoires non terminé: {manifest.get('status')!r}"
        )
    if manifest.get("run_count") != expected_run_count:
        raise ValueError(
            "Nombre de simulations incohérent dans le manifeste de trajectoires: "
            f"{manifest.get('run_count')!r} au lieu de {expected_run_count}"
        )
    if manifest.get("days") != len(payload["day_axis"]):
        raise ValueError(
            "Nombre de jours incohérent dans le manifeste de trajectoires: "
            f"{manifest.get('days')!r} au lieu de {len(payload['day_axis'])}"
        )
    if manifest.get("cascade_ids") != sorted(expected_cascade_ids):
        raise ValueError(
            "Cascades incohérentes dans le manifeste de trajectoires: "
            f"{manifest.get('cascade_ids')!r} au lieu de {sorted(expected_cascade_ids)}"
        )

    config_metadata = _required_mapping(
        manifest, "config_snapshot", context="le manifeste de trajectoires"
    )
    _require_declared_path(
        config_metadata,
        "path",
        config_snapshot_path,
        context="le manifeste de trajectoires",
    )
    config_hash = _require_declared_hash(
        config_metadata,
        "sha256",
        config_snapshot_path,
        context="le manifeste de trajectoires",
    )
    runs_metadata = _required_mapping(
        manifest, "runs_csv", context="le manifeste de trajectoires"
    )
    _require_declared_path(
        runs_metadata,
        "path",
        campaign_runs_path,
        context="le manifeste de trajectoires",
    )
    runs_hash = _require_declared_hash(
        runs_metadata,
        "sha256",
        campaign_runs_path,
        context="le manifeste de trajectoires",
    )

    resolved_trajectory_dir = trajectory_dir.resolve()
    long_path = resolved_trajectory_dir / TRAJECTORY_LONG_NAME
    outputs = _required_mapping(
        manifest, "outputs", context="le manifeste de trajectoires"
    )
    _require_declared_path(
        outputs,
        "long_csv",
        long_path,
        context="le manifeste de trajectoires",
    )
    long_hash = _require_declared_hash(
        outputs,
        "long_csv_sha256",
        long_path,
        context="le manifeste de trajectoires",
    )
    long_row_count = _csv_row_count(long_path)
    declared_long_row_count = _strict_nonnegative_int(
        manifest.get("long_row_count"),
        label="le manifeste de trajectoires.long_row_count",
    )
    if declared_long_row_count != long_row_count:
        raise ValueError(
            "Nombre de lignes incoherent pour les trajectoires longues: "
            f"declare={declared_long_row_count}, observe={long_row_count}"
        )
    _require_declared_path(
        outputs,
        "compact_json",
        compact_path,
        context="le manifeste de trajectoires",
    )
    compact_hash = _require_declared_hash(
        outputs,
        "compact_json_sha256",
        compact_path,
        context="le manifeste de trajectoires",
    )
    return {
        "trajectory_manifest_verified": True,
        "trajectory_config_snapshot_sha256": config_hash,
        "trajectory_runs_sha256": runs_hash,
        "trajectory_long_csv_sha256": long_hash,
        "trajectory_long_csv_row_count": long_row_count,
        "trajectory_long_csv_source": str(long_path),
        "trajectory_compact_json_sha256": compact_hash,
    }


def _validate_trajectory_contract(
    payload: dict[str, Any],
    *,
    cascade_contracts: dict[str, dict[str, Any]],
    expected_solution_ids: dict[str, set[str]],
    expected_seed_counts: dict[str, int],
) -> None:
    day_axis = payload.get("day_axis")
    if day_axis != list(range(len(day_axis))):
        raise ValueError(
            "L’axe des trajectoires doit couvrir chaque jour depuis J0 sans trou"
        )
    cascades = payload["cascades"]
    if set(cascades) != set(cascade_contracts):
        raise ValueError(
            "Les cascades des trajectoires diffèrent du snapshot: "
            f"{sorted(cascades)} vs {sorted(cascade_contracts)}"
        )
    for cascade_id, cascade_payload in cascades.items():
        if not isinstance(cascade_payload, dict):
            raise ValueError(f"Trajectoire de cascade invalide: {cascade_id}")
        contract = cascade_contracts[cascade_id]
        if str(cascade_payload.get("customer_id") or "") != str(
            contract.get("customer_id") or ""
        ):
            raise ValueError(f"Client incohérent dans les trajectoires: {cascade_id}")
        if str(cascade_payload.get("finished_item_id") or "") != str(
            contract.get("finished_item_id") or ""
        ):
            raise ValueError(
                f"Produit fini incohérent dans les trajectoires: {cascade_id}"
            )
        variants = cascade_payload.get("variants")
        if not isinstance(variants, dict) or not variants:
            raise ValueError(f"Trajectoires sans variantes: {cascade_id}")
        by_role: dict[str, dict[str, Any]] = {}
        for variant_id, variant in variants.items():
            if not isinstance(variant, dict):
                raise ValueError(
                    f"Variante de trajectoire invalide: {cascade_id}/{variant_id}"
                )
            role = str(variant.get("variant_role") or "")
            if not role or role in by_role:
                raise ValueError(
                    f"Rôle de trajectoire absent ou dupliqué: {cascade_id}/{role}"
                )
            by_role[role] = variant
        expected_roles = {"normal", "no_action"} | {
            f"solution:{solution_id}"
            for solution_id in expected_solution_ids[cascade_id]
        }
        if set(by_role) != expected_roles:
            raise ValueError(
                f"Variantes de trajectoires incomplètes pour {cascade_id}: "
                f"{sorted(by_role)} vs {sorted(expected_roles)}"
            )
        for role, variant in by_role.items():
            try:
                seed_count = int(variant.get("seed_count") or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Nombre de répétitions invalide pour {cascade_id}/{role}"
                ) from exc
            if seed_count != expected_seed_counts[cascade_id]:
                raise ValueError(
                    f"Répétitions de trajectoires incomplètes pour {cascade_id}/{role}: "
                    f"{seed_count} sur {expected_seed_counts[cascade_id]}"
                )
            series_rows = variant.get("series")
            if not isinstance(series_rows, list) or not series_rows:
                raise ValueError(f"Aucune série pour {cascade_id}/{role}")
            seen_series: set[tuple[str, str, str, str, int, str]] = set()
            for series_index, series in enumerate(series_rows):
                if not isinstance(series, dict):
                    raise ValueError(
                        f"Série invalide pour {cascade_id}/{role}/{series_index}"
                    )
                core_signature = tuple(
                    str(series.get(field) or "")
                    for field in ("metric", "node_id", "item_id", "uom")
                )
                if any(not value for value in core_signature):
                    raise ValueError(
                        f"Identité de série incomplète pour {cascade_id}/{role}/{series_index}"
                    )
                try:
                    path_stage_index = int(series.get("path_stage_index"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Étape de série invalide pour {cascade_id}/{role}/{series_index}"
                    ) from exc
                path_stage_kind = str(series.get("path_stage_kind") or "")
                if path_stage_index < 0 or not path_stage_kind:
                    raise ValueError(
                        f"Étape de série incomplète pour {cascade_id}/{role}/{series_index}"
                    )
                signature = (
                    *core_signature,
                    path_stage_index,
                    path_stage_kind,
                )
                if signature in seen_series:
                    raise ValueError(
                        f"Série ambiguë ou dupliquée pour {cascade_id}/{role}: {signature}"
                    )
                seen_series.add(signature)
                arrays: dict[str, list[float]] = {}
                for statistic in ("mean", "min", "max"):
                    values = series.get(statistic)
                    if not isinstance(values, list) or len(values) != len(day_axis):
                        raise ValueError(
                            f"Couverture journalière invalide pour "
                            f"{cascade_id}/{role}/{signature}/{statistic}"
                        )
                    normalized: list[float] = []
                    for value in values:
                        if isinstance(value, bool):
                            raise ValueError(
                                f"Valeur de trajectoire invalide pour {cascade_id}/{role}"
                            )
                        try:
                            number = float(value)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"Valeur de trajectoire invalide pour {cascade_id}/{role}"
                            ) from exc
                        if not math.isfinite(number):
                            raise ValueError(
                                f"Valeur de trajectoire non finie pour {cascade_id}/{role}"
                            )
                        normalized.append(number)
                    arrays[statistic] = normalized
                for day, (minimum, average, maximum) in enumerate(
                    zip(arrays["min"], arrays["mean"], arrays["max"], strict=True)
                ):
                    if minimum > average + 1e-9 or average > maximum + 1e-9:
                        raise ValueError(
                            f"Enveloppe min/moyenne/max incohérente pour "
                            f"{cascade_id}/{role}/{signature}/jour {day}"
                        )


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, probability)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _metric_summary(
    rows: Sequence[dict[str, str]], field: str
) -> dict[str, float | int | None]:
    values = [value for row in rows if (value := _to_float(row.get(field))) is not None]
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "p10": None,
            "p90": None,
        }
    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
        "p10": _quantile(values, 0.10),
        "p90": _quantile(values, 0.90),
    }


def _format_number(value: Any, decimals: int = 1) -> str:
    number = _to_float(value)
    if number is None:
        return "non disponible"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:,.2f} M".replace(",", " ").replace(".", ",")
    if abs(number) >= 10_000:
        return f"{number:,.0f}".replace(",", " ")
    return f"{number:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _format_percent(value: Any, decimals: int = 1) -> str:
    number = _to_float(value)
    if number is None:
        return "non disponible"
    return f"{100.0 * number:.{decimals}f} %".replace(".", ",")


def _remaining_backlog_ratio_of_means(metrics: Mapping[str, Any]) -> float | None:
    untreated = _to_float(
        metrics["no_action_incremental_customer_backlog_qty_days"]["mean"]
    )
    remaining = _to_float(
        metrics["remaining_incremental_customer_backlog_qty_days"]["mean"]
    )
    if untreated is None or remaining is None or untreated <= 1e-12:
        return None
    return remaining / untreated


def _cascade_label(cascade_id: str) -> str:
    lowered = cascade_id.lower()
    if "021081" in lowered or "quality" in lowered or "qualit" in lowered:
        return (
            "Retenue de libération qualité simulée sur une chaîne multi-étages "
            "— composant 021081"
        )
    if "338929" in lowered or "delay" in lowered or "retard" in lowered:
        return "Retard fournisseur — composant 338929 vers M-1810"
    return cascade_id.replace("_", " ").strip().capitalize()


def _solution_label(solution_id: str, cascade_id: str = "") -> str:
    lowered = solution_id.lower()
    quality = "021081" in cascade_id or "quality" in cascade_id
    if lowered == "expedited_transport":
        return (
            "Transport accéléré sur les nouvelles expéditions — retenue qualité inchangée"
            if quality
            else "Transport accéléré sur les nouvelles expéditions"
        )
    if lowered == "second_supplier":
        return "Bascule concentrée vers un fournisseur alternatif déjà présent"
    if lowered == "second_supplier_proxy":
        return "Hypothèse de second fournisseur — non présente dans le réseau"
    if lowered == "emergency_purchase":
        return "Achat exceptionnel amont — capacité chez un fournisseur existant"
    if lowered == "targeted_stock":
        return (
            "Hausse de la cible de stock après l’alerte"
            if quality
            else "Stock ciblé constitué avant l’incident"
        )
    if lowered == "supplier_priority":
        return (
            "Répartition renforcée entre les fournisseurs disponibles"
            if quality
            else "Test de priorité sur une branche mono-source"
        )
    if lowered == "replanning":
        return "Révision des besoins et objectifs de production — sans APS"
    if lowered == "combined_response":
        return "Plan combiné — effets à confirmer séparément"
    labels = (
        (("expedite", "acceler", "express"), "Transport accéléré"),
        (("alternate", "second", "dual", "source"), "Second fournisseur"),
        (
            ("external", "emergency", "exception", "purchase", "procurement"),
            "Achat exceptionnel",
        ),
        (("buffer", "safety", "stock"), "Stock ciblé"),
        (("priority", "allocation", "priorit"), "Priorisation"),
        (("replan", "reschedul", "planification"), "Replanification"),
        (("combined", "combine", "global"), "Plan d'actions combiné"),
        (("none", "no_action", "sans_action"), "Sans action"),
    )
    for needles, label in labels:
        if any(needle in lowered for needle in needles):
            return label
    return solution_id.replace("_", " ").strip().capitalize()


def _solution_scope_note(solution_id: str, cascade_id: str) -> str:
    quality = "021081" in cascade_id or "quality" in cascade_id
    return {
        "expedited_transport": (
            "Réduit le transport des nouveaux mouvements ; la retenue qualité de "
            "90 jours reste inchangée, aucun transporteur réel n’est sélectionné et "
            "les flux déjà en transit ne sont pas accélérés."
            if quality
            else "Réduit le délai des nouveaux mouvements ; aucun transporteur réel "
            "n’est sélectionné et les flux déjà en transit ne sont pas accélérés."
        ),
        "second_supplier": (
            "Réalloue les besoins vers une source alternative déjà présente dans le "
            "réseau simulé ; ce n’est pas une étude de qualification fournisseur."
        ),
        "second_supplier_proxy": (
            "Ajoute de l’approvisionnement externe chez le fournisseur existant : "
            "aucun second fournisseur ni nouvelle liaison n’est créé."
        ),
        "emergency_purchase": (
            "Augmente la capacité d’approvisionnement amont chez un fournisseur "
            "existant ; ce n’est pas un achat spot livré directement à l’usine."
        ),
        "targeted_stock": (
            "Augmente une cible de stock via les ordres exécutables du moteur ; le "
            "nombre de simulations où toutes les fenêtres ont réellement agi est "
            "indiqué ci-dessous."
        ),
        "supplier_priority": (
            "Modifie la répartition entre les liaisons fournisseurs existantes ; ce "
            "n’est pas une priorité de commande client."
            if quality
            else "Test témoin : 338929 étant mono-source, aucune répartition relative "
            "entre fournisseurs n’est physiquement possible."
        ),
        "replanning": (
            "Modifie les cibles quotidiennes MRP et de production ; ne redate pas les "
            "ordres fermes et ne résout pas un ordonnancement APS à capacité finie."
        ),
        "combined_response": (
            "Combine plusieurs leviers ; les approximations du transport, de l’achat "
            "exceptionnel, du second fournisseur et de la replanification restent "
            "présentes et doivent être isolées avant recommandation."
        ),
    }.get(solution_id, "Périmètre à confirmer avec les règles opérationnelles.")


def _is_approximated_fidelity(value: str) -> bool:
    """Return whether a configured lever includes a business approximation."""

    normalized = value.strip().lower()
    return normalized in {
        "native_simplified",
        "mixed",
        "approximation",
        "approximated",
        "proxy",
    }


def _aggregate_comparisons(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        cascade_id = str(row.get("cascade_id") or "")
        solution_id = str(row.get("solution_id") or "")
        seed = str(row.get("seed") or "")
        key = (cascade_id, solution_id, seed)
        if key in seen:
            raise ValueError(
                "Comparaison dupliquée pour "
                f"cascade={cascade_id}, solution={solution_id}, graine={seed}"
            )
        seen.add(key)
        grouped[(cascade_id, solution_id)].append(row)

    aggregates: list[dict[str, Any]] = []
    for (cascade_id, solution_id), group in sorted(grouped.items()):
        exposed = [
            row
            for row in group
            if _strict_bool(
                row.get("customer_exposure_detected"),
                label=(
                    f"customer_exposure_detected {cascade_id}/{solution_id}/"
                    f"{row.get('seed')}"
                ),
            )
        ]
        days = [
            value
            for row in group
            if (value := _to_float(row.get("days_recovered_vs_no_action"))) is not None
        ]
        verified = sum(
            1
            for row in group
            if str(row.get("action_execution_status") or "") == "fully_verified"
        )
        eligible = bool(exposed) and all(
            _truthy(row.get("ranking_eligible")) for row in exposed
        )
        incident_verified = all(
            _truthy(row.get("incident_application_verified")) for row in group
        )
        paired = all(
            str(row.get("pairing_status") or "") == "measurement_start_state_matched"
            for row in group
        )
        fidelities = sorted(
            {str(row.get("lever_fidelity") or "non_precise") for row in group}
        )
        notes = sorted(
            {
                str(row.get("evidence_notes") or "").strip()
                for row in group
                if str(row.get("evidence_notes") or "").strip()
            }
        )
        exclusion_reasons = sorted(
            {
                str(row.get("ranking_exclusion_reasons") or "").strip()
                for row in group
                if str(row.get("ranking_exclusion_reasons") or "").strip()
            }
        )
        aggregates.append(
            {
                "cascade_id": cascade_id,
                "cascade_label": _cascade_label(cascade_id),
                "solution_id": solution_id,
                "solution_label": _solution_label(solution_id, cascade_id),
                "solution_scope_note": _solution_scope_note(solution_id, cascade_id),
                "simulation_count": len(group),
                "customer_exposure_count": len(exposed),
                "customer_no_exposure_count": len(group) - len(exposed),
                "customer_exposure_frequency": len(exposed) / len(group),
                "favorable_count": sum(1 for value in days if value > 1e-9),
                "verified_count": verified,
                "eligible": (
                    eligible and incident_verified and paired and verified == len(group)
                ),
                "incident_verified": incident_verified,
                "paired": paired,
                "exclusion_reasons": exclusion_reasons,
                "fidelity": " / ".join(fidelities),
                "approximation": any(
                    _is_approximated_fidelity(value) for value in fidelities
                ),
                "notes": notes,
                "metrics": {field: _metric_summary(group, field) for field in METRICS},
            }
        )
    return aggregates


def _risk_rows(
    registry_dirs: Sequence[Path],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, Any]],
    list[RiskRegistryEvidence],
]:
    incidents: list[dict[str, str]] = []
    entities: list[dict[str, str]] = []
    client_service: list[dict[str, str]] = []
    costs: list[dict[str, str]] = []
    quality: list[dict[str, Any]] = []
    registries: list[RiskRegistryEvidence] = []
    for registry_index, registry_dir in enumerate(registry_dirs, start=1):
        directory = registry_dir.resolve()
        table_paths = {
            name: directory / filename
            for name, filename in RISK_REGISTRY_CSV_FILENAMES.items()
        }
        quality_path = directory / "risk_impact_quality.json"
        source = f"registre_{registry_index:02d}"
        table_rows = {name: _read_csv(path) for name, path in table_paths.items()}
        incident_rows = table_rows["incidents"]
        entity_rows = table_rows["entities"]
        edge_rows = table_rows["edges"]
        client_rows = table_rows["client_service"]
        cost_rows = table_rows["costs"]
        bundle_event_rows = table_rows["bundle_events"]
        _require_columns(
            incident_rows,
            {
                "incident_id",
                "causality_level",
                "supplier_id",
                "dst_node_id",
                "item_id",
                "edge_id",
            },
            table_paths["incidents"],
        )
        _require_columns(
            entity_rows,
            {
                "incident_id",
                "entity_type",
                "entity_id",
                "item_id",
                "node_id",
                "causality_level",
            },
            table_paths["entities"],
        )
        _require_columns(
            edge_rows,
            {
                "incident_id",
                "edge_id",
                "source_uom",
                "target_uom",
            },
            table_paths["edges"],
        )
        incomplete_edge_units = [
            row
            for row in edge_rows
            if not str(row.get("source_uom") or "").strip()
            or not str(row.get("target_uom") or "").strip()
        ]
        if incomplete_edge_units:
            raise ValueError(
                f"Unités source/cible absentes sur {len(incomplete_edge_units)} "
                f"liens de {table_paths['edges']}"
            )
        _require_columns(
            client_rows,
            {
                "incident_id",
                "client_node_id",
                "item_id",
                "served_exposed_qty_lower",
                "served_exposed_qty_upper",
                "uom",
                "causality_level",
            },
            table_paths["client_service"],
        )
        _require_columns(
            cost_rows,
            {"exposure_bundle_id", "incremental_total_cost_status"},
            table_paths["costs"],
        )
        _require_columns(
            bundle_event_rows,
            {"incident_id", "exposure_bundle_id", "causality_level"},
            table_paths["bundle_events"],
        )
        quality_payload = _read_json(quality_path)
        provenance = _required_mapping(
            quality_payload,
            "provenance",
            context=str(quality_path),
        )
        if provenance.get("schema_version") != RISK_PROVENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"Version de provenance de registre inattendue dans {quality_path}: "
                f"{provenance.get('schema_version')!r}"
            )
        if provenance.get("verification_status") != "campaign_run_verified":
            raise ValueError(
                f"Registre sans campagne source verifiee dans {quality_path}: "
                f"{provenance.get('verification_status')!r}"
            )
        if (
            not isinstance(provenance.get("source_files"), dict)
            or not provenance["source_files"]
        ):
            raise ValueError(
                f"Sources physiques absentes de la provenance: {quality_path}"
            )
        output_integrity = _validate_registry_output_integrity(
            directory=directory,
            quality=quality_payload,
            table_paths=table_paths,
            table_rows=table_rows,
        )
        sourced_incidents = tuple(
            {**row, "_registry_source": source} for row in incident_rows
        )
        sourced_entities = tuple(
            {**row, "_registry_source": source} for row in entity_rows
        )
        sourced_clients = tuple(
            {**row, "_registry_source": source} for row in client_rows
        )
        sourced_costs = tuple({**row, "_registry_source": source} for row in cost_rows)
        incidents.extend(sourced_incidents)
        entities.extend(sourced_entities)
        client_service.extend(sourced_clients)
        costs.extend(sourced_costs)
        registries.append(
            RiskRegistryEvidence(
                source=source,
                directory=directory,
                incidents=sourced_incidents,
                entities=sourced_entities,
                client_service=sourced_clients,
                costs=sourced_costs,
                bundle_events=tuple(bundle_event_rows),
                quality=quality_payload,
                provenance=provenance,
                output_integrity=output_integrity,
            )
        )
        quality.append(quality_payload)
    return incidents, entities, client_service, costs, quality, registries


def _validate_registry_output_integrity(
    *,
    directory: Path,
    quality: dict[str, Any],
    table_paths: dict[str, Path],
    table_rows: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    outputs = _required_mapping(quality, "registry_outputs", context=str(directory))
    _require_declared_path(
        outputs,
        "output_dir",
        directory,
        context=f"les sorties du registre {directory}",
    )
    artifacts = _required_mapping(
        outputs,
        "csv_artifacts",
        context=f"les sorties du registre {directory}",
    )
    if set(artifacts) != set(RISK_REGISTRY_CSV_FILENAMES):
        raise ValueError(
            f"Liste des sept CSV de registre incoherente dans {directory}: "
            f"{sorted(artifacts)}"
        )
    proof: dict[str, Any] = {}
    for table_name, filename in RISK_REGISTRY_CSV_FILENAMES.items():
        metadata = _required_mapping(
            artifacts,
            table_name,
            context=f"les sorties du registre {directory}",
        )
        if str(metadata.get("filename") or "") != filename:
            raise ValueError(
                f"Nom de fichier incoherent pour {directory}/{table_name}: "
                f"{metadata.get('filename')!r}"
            )
        path = table_paths[table_name]
        declared_hash = _strict_sha256(
            metadata.get("sha256"),
            label=f"{directory}/{table_name}",
        )
        observed_hash = _sha256(path)
        if declared_hash != observed_hash:
            raise ValueError(
                f"Empreinte de registre incoherente pour {path}: "
                f"declaree={declared_hash}, observee={observed_hash}"
            )
        declared_rows = _strict_nonnegative_int(
            metadata.get("row_count"),
            label=f"{directory}/{table_name}.row_count",
        )
        observed_rows = len(table_rows[table_name])
        if declared_rows != observed_rows:
            raise ValueError(
                f"Nombre de lignes de registre incoherent pour {path}: "
                f"declare={declared_rows}, observe={observed_rows}"
            )
        declared_size = _strict_nonnegative_int(
            metadata.get("size_bytes"),
            label=f"{directory}/{table_name}.size_bytes",
        )
        if declared_size != path.stat().st_size:
            raise ValueError(f"Taille de registre incoherente pour {path}")
        proof[table_name] = {
            "filename": filename,
            "sha256": observed_hash,
            "row_count": observed_rows,
            "size_bytes": declared_size,
        }
    quality_metadata = _required_mapping(
        outputs,
        "quality_json",
        context=f"les sorties du registre {directory}",
    )
    if (
        quality_metadata.get("filename") != "risk_impact_quality.json"
        or quality_metadata.get("sha256") is not None
        or quality_metadata.get("self_hash_status")
        != "intentionally_excluded_to_avoid_recursive_self_hash"
    ):
        raise ValueError(f"Contrat d'auto-empreinte JSON invalide pour {directory}")
    return {
        "verified": True,
        "csv_artifacts": proof,
        "quality_json": {
            "filename": "risk_impact_quality.json",
            "self_hash_status": quality_metadata["self_hash_status"],
        },
    }


def _single_campaign_run(
    rows: Sequence[dict[str, str]],
    *,
    cascade_id: str,
    variant_id: str,
    seed: int,
    context: str,
) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if str(row.get("cascade_id") or "") == cascade_id
        and str(row.get("variant_id") or "") == variant_id
        and _strict_nonnegative_int(row.get("seed"), label=f"{context}.seed") == seed
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Run de campagne absent ou duplique dans {context}: "
            f"{cascade_id}/{variant_id}/graine {seed}"
        )
    return matches[0]


def _validate_registry_campaign_pairing(
    registry: RiskRegistryEvidence,
    *,
    registry_cascade_id: str,
    final_campaign_source: Path,
    final_runs: Sequence[dict[str, str]],
) -> dict[str, Any]:
    provenance = registry.provenance
    identity = _required_mapping(
        provenance,
        "identity",
        context=f"la provenance {registry.source}",
    )
    cascade_id = str(identity.get("cascade_id") or "").strip()
    variant_id = str(identity.get("variant_id") or "").strip()
    case_type = str(identity.get("case_type") or "").strip()
    seed = _strict_nonnegative_int(
        identity.get("seed"),
        label=f"la provenance {registry.source}.identity.seed",
    )
    if cascade_id != registry_cascade_id:
        raise ValueError(
            f"Cascade de provenance incoherente pour {registry.source}: "
            f"{cascade_id!r} au lieu de {registry_cascade_id!r}"
        )
    if variant_id != "incident_no_action" or case_type != "incident_no_action":
        raise ValueError(
            f"Le registre {registry.source} doit provenir de incident_no_action, "
            f"pas de {variant_id!r}/{case_type!r}"
        )
    if identity.get("solution_id") not in {None, ""}:
        raise ValueError(
            f"Le registre sans action {registry.source} declare une solution"
        )

    critical = _required_mapping(
        provenance,
        "critical_hashes",
        context=f"la provenance {registry.source}",
    )
    parent_campaign = _required_mapping(
        provenance,
        "parent_campaign",
        context=f"la provenance {registry.source}",
    )
    if parent_campaign.get("detected") is not True:
        raise ValueError(f"Campagne parent non detectee pour {registry.source}")
    trace_root_raw = str(parent_campaign.get("root") or "").strip()
    if not trace_root_raw:
        raise ValueError(f"Racine de campagne parent absente pour {registry.source}")
    trace_root = Path(trace_root_raw).resolve()
    if not trace_root.is_dir():
        raise FileNotFoundError(trace_root)

    source_artifacts = {
        "manifest": (
            trace_root / "canonical_cascade_manifest.json",
            "campaign_manifest_sha256",
        ),
        "runs": (
            trace_root / "canonical_cascade_runs.csv",
            "campaign_runs_sha256",
        ),
        "commands": (
            trace_root / "canonical_cascade_commands.json",
            "campaign_commands_sha256",
        ),
        "config_snapshot": (
            trace_root / "canonical_cascade_config_snapshot.json",
            "campaign_config_snapshot_sha256",
        ),
    }
    source_hashes: dict[str, str] = {}
    for artifact_name, (path, critical_key) in source_artifacts.items():
        metadata = _required_mapping(
            parent_campaign,
            artifact_name,
            context=f"la campagne parent de {registry.source}",
        )
        observed = _verified_metadata_file(
            metadata,
            expected=path,
            context=f"la campagne parent de {registry.source}",
        )
        critical_digest = _strict_sha256(
            critical.get(critical_key),
            label=f"{registry.source}.{critical_key}",
        )
        if observed != critical_digest:
            raise ValueError(
                f"Empreinte critique incoherente pour {registry.source}/{artifact_name}"
            )
        source_hashes[critical_key] = observed

    trace_manifest = _read_json(source_artifacts["manifest"][0])
    if (
        trace_manifest.get("schema_version") != CAMPAIGN_MANIFEST_SCHEMA_VERSION
        or trace_manifest.get("status") != "complete"
        or trace_manifest.get("failure_count") != 0
        or trace_manifest.get("skipped_fail_fast_count") != 0
        or trace_manifest.get("artifact_profile") != "full"
    ):
        raise ValueError(
            f"Campagne full-trace incomplete ou invalide pour {registry.source}"
        )
    trace_outputs = _required_mapping(
        trace_manifest,
        "outputs",
        context=f"le manifeste full-trace {registry.source}",
    )
    trace_output_hashes = _required_mapping(
        trace_manifest,
        "output_sha256",
        context=f"le manifeste full-trace {registry.source}",
    )
    for artifact_name in ("runs", "commands", "config_snapshot"):
        path = source_artifacts[artifact_name][0]
        _require_declared_path(
            trace_outputs,
            artifact_name,
            path,
            context=f"le manifeste full-trace {registry.source}",
        )
        _require_declared_hash(
            trace_output_hashes,
            artifact_name,
            path,
            context=f"le manifeste full-trace {registry.source}",
        )

    trace_runs = _read_csv(source_artifacts["runs"][0])
    declared_trace_run_count = _strict_nonnegative_int(
        trace_manifest.get("run_count"),
        label=f"le manifeste full-trace {registry.source}.run_count",
    )
    provenance_run_count = _strict_nonnegative_int(
        parent_campaign["runs"].get("row_count"),
        label=f"la provenance {registry.source}.parent_campaign.runs.row_count",
    )
    if declared_trace_run_count != len(trace_runs) or provenance_run_count != len(
        trace_runs
    ):
        raise ValueError(f"Nombre de runs full-trace incoherent pour {registry.source}")
    trace_commands = _read_json_array(source_artifacts["commands"][0])
    provenance_command_count = _strict_nonnegative_int(
        parent_campaign["commands"].get("entry_count"),
        label=f"la provenance {registry.source}.parent_campaign.commands.entry_count",
    )
    if len(trace_commands) != len(trace_runs) or provenance_command_count != len(
        trace_commands
    ):
        raise ValueError(
            f"Grille de commandes full-trace incoherente pour {registry.source}"
        )
    trace_row = _single_campaign_run(
        trace_runs,
        cascade_id=cascade_id,
        variant_id=variant_id,
        seed=seed,
        context=f"la campagne full-trace {registry.source}",
    )
    final_row = _single_campaign_run(
        final_runs,
        cascade_id=cascade_id,
        variant_id=variant_id,
        seed=seed,
        context="la campagne finale",
    )
    for label, row in (("full-trace", trace_row), ("final", final_row)):
        if (
            row.get("status") != "ok"
            or row.get("case_type") != "incident_no_action"
            or str(row.get("solution_id") or "")
        ):
            raise ValueError(
                f"Run incident sans action invalide dans la campagne {label}: "
                f"{cascade_id}/graine {seed}"
            )

    final_manifest_path = final_campaign_source / "canonical_cascade_manifest.json"
    final_manifest = _read_json(final_manifest_path)
    final_config_path = final_campaign_source / "canonical_cascade_config_snapshot.json"
    final_config_hash = _sha256(final_config_path)
    if source_hashes["campaign_config_snapshot_sha256"] != final_config_hash:
        raise ValueError(
            f"Configuration full-trace differente de la campagne finale pour {registry.source}"
        )

    dependency_hashes: dict[str, str] = {}
    for dependency in ("graph", "engine", "engine_profile"):
        trace_digest = _manifest_dependency_hash(
            trace_manifest,
            dependency,
            context=f"le manifeste full-trace {registry.source}",
        )
        final_digest = _manifest_dependency_hash(
            final_manifest,
            dependency,
            context="le manifeste de campagne finale",
        )
        if trace_digest != final_digest:
            raise ValueError(
                f"{dependency} different entre full-trace et campagne finale pour "
                f"{registry.source}"
            )
        dependency_hashes[f"{dependency}_sha256"] = trace_digest

    risk_hash = _strict_sha256(
        critical.get("risk_events_sha256"),
        label=f"{registry.source}.risk_events_sha256",
    )
    trace_risk_hash = _strict_sha256(
        trace_row.get("risk_events_sha256"),
        label=f"{registry.source}.trace.risk_events_sha256",
    )
    final_risk_hash = _strict_sha256(
        final_row.get("risk_events_sha256"),
        label=f"{registry.source}.final.risk_events_sha256",
    )
    if len({risk_hash, trace_risk_hash, final_risk_hash}) != 1:
        raise ValueError(f"Risque non apparie pour {registry.source}")

    state_hash = _strict_sha256(
        critical.get("measurement_start_state_sha256"),
        label=f"{registry.source}.measurement_start_state_sha256",
    )
    trace_state_hash = _strict_sha256(
        trace_row.get("measurement_start_state_sha256"),
        label=f"{registry.source}.trace.measurement_start_state_sha256",
    )
    final_state_hash = _strict_sha256(
        final_row.get("measurement_start_state_sha256"),
        label=f"{registry.source}.final.measurement_start_state_sha256",
    )
    parent_run = _required_mapping(
        provenance,
        "parent_run",
        context=f"la provenance {registry.source}",
    )
    provenance_components = _component_hashes(
        parent_run.get("measurement_start_component_sha256"),
        label=f"{registry.source}.parent_run.measurement_start_component_sha256",
    )
    trace_components = _component_hashes(
        trace_row.get("measurement_start_component_sha256_json"),
        label=f"{registry.source}.trace.measurement_start_component_sha256_json",
    )
    final_components = _component_hashes(
        final_row.get("measurement_start_component_sha256_json"),
        label=f"{registry.source}.final.measurement_start_component_sha256_json",
    )
    measurement_start_pairing = _validate_measurement_start_pairing(
        registry_source=registry.source,
        provenance_state_hash=state_hash,
        trace_state_hash=trace_state_hash,
        final_state_hash=final_state_hash,
        provenance_components=provenance_components,
        trace_components=trace_components,
        final_components=final_components,
        trace_artifact_profile=str(trace_manifest.get("artifact_profile") or ""),
        final_artifact_profile=str(final_manifest.get("artifact_profile") or ""),
        trace_row=trace_row,
        final_row=final_row,
    )

    graph_hash = dependency_hashes["graph_sha256"]
    profile_hash = dependency_hashes["engine_profile_sha256"]
    for label, row in (("full-trace", trace_row), ("final", final_row)):
        if (
            _strict_sha256(
                row.get("graph_sha256"), label=f"{registry.source}.{label}.graph_sha256"
            )
            != graph_hash
        ):
            raise ValueError(f"Graphe du run {label} incoherent pour {registry.source}")
        if (
            _strict_sha256(
                row.get("engine_profile_sha256"),
                label=f"{registry.source}.{label}.engine_profile_sha256",
            )
            != profile_hash
        ):
            raise ValueError(f"Profil moteur {label} incoherent pour {registry.source}")

    return {
        "registry_source": registry.source,
        "verification_status": "campaign_run_verified_and_paired_to_final_campaign",
        "identity": {
            "cascade_id": cascade_id,
            "variant_id": variant_id,
            "case_type": case_type,
            "seed": seed,
        },
        "critical_hashes": {
            **source_hashes,
            **dependency_hashes,
            "risk_events_sha256": risk_hash,
            "measurement_start_pairing": measurement_start_pairing,
        },
        "registry_outputs": registry.output_integrity,
        "final_campaign_seed_verified": True,
    }


def _validate_risk_registry_contract(
    registries: Sequence[RiskRegistryEvidence],
    *,
    cascade_contracts: dict[str, dict[str, Any]],
    final_campaign_source: Path,
    final_runs: Sequence[dict[str, str]],
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    configured_events: dict[str, tuple[str, dict[str, Any]]] = {}
    for cascade_id, cascade in cascade_contracts.items():
        incident = cascade.get("incident")
        events = incident.get("risk_events") if isinstance(incident, dict) else None
        if not isinstance(events, list) or not events:
            raise ValueError(f"Incident sans événement de risque pour {cascade_id}")
        for event in events:
            if not isinstance(event, dict):
                raise ValueError(f"Événement de risque invalide pour {cascade_id}")
            event_id = str(event.get("event_id") or "").strip()
            if not event_id:
                raise ValueError(f"Événement sans identifiant pour {cascade_id}")
            if event_id in configured_events:
                raise ValueError(f"Identifiant d’événement dupliqué: {event_id}")
            configured_events[event_id] = (cascade_id, event)

    matched_cascades: dict[str, set[str]] = defaultdict(set)
    provenance_proofs: list[dict[str, Any]] = []
    for registry in registries:
        registry_native_count = 0
        registry_cascade_ids: set[str] = set()
        for incident_row in registry.incidents:
            incident_id = str(incident_row.get("incident_id") or "").strip()
            configured = configured_events.get(incident_id)
            if configured is None:
                raise ValueError(
                    f"Incident de registre hors périmètre: {registry.source}/{incident_id}"
                )
            cascade_id, event = configured
            registry_cascade_ids.add(cascade_id)
            for field in ("supplier_id", "dst_node_id", "item_id", "edge_id"):
                expected = str(event.get(field) or "").strip()
                observed = str(incident_row.get(field) or "").strip()
                if expected and observed != expected:
                    raise ValueError(
                        f"Périmètre de risque incohérent pour {registry.source}/{incident_id}: "
                        f"{field}={observed!r}, attendu={expected!r}"
                    )
            if str(incident_row.get("causality_level") or "") != "native_transaction":
                continue
            registry_native_count += 1
            matched_cascades[cascade_id].add(registry.source)
            cascade = cascade_contracts[cascade_id]
            finished_item_id = str(cascade.get("finished_item_id") or "")
            customer_id = str(cascade.get("customer_id") or "")
            finished_entities = [
                row
                for row in registry.entities
                if str(row.get("incident_id") or "") == incident_id
                and str(row.get("item_id") or "") == finished_item_id
                and str(row.get("causality_level") or "")
                in {"native_transaction", "physical_genealogy"}
            ]
            if not finished_entities:
                raise ValueError(
                    f"Aucune relation native vers le produit fini pour "
                    f"{registry.source}/{cascade_id}/{incident_id}"
                )
            customer_rows = [
                row
                for row in registry.client_service
                if str(row.get("incident_id") or "") == incident_id
                and str(row.get("client_node_id") or "") == customer_id
                and str(row.get("item_id") or "") == finished_item_id
                and str(row.get("causality_level") or "")
                in {"native_transaction", "physical_genealogy"}
                and str(row.get("uom") or "").strip()
                and (_to_float(row.get("served_exposed_qty_upper")) or 0.0) > 0.0
            ]
            if not customer_rows:
                raise ValueError(
                    f"Aucune relation native vers le client pour "
                    f"{registry.source}/{cascade_id}/{incident_id}"
                )
            bundle_ids = {
                str(row.get("exposure_bundle_id") or "")
                for row in registry.bundle_events
                if str(row.get("incident_id") or "") == incident_id
                and str(row.get("causality_level") or "") == "native_transaction"
                and str(row.get("exposure_bundle_id") or "")
            }
            cost_bundle_ids = {
                str(row.get("exposure_bundle_id") or "")
                for row in registry.costs
                if str(row.get("exposure_bundle_id") or "")
            }
            if not bundle_ids.intersection(cost_bundle_ids):
                raise ValueError(
                    f"Aucune relation native vers les coûts pour "
                    f"{registry.source}/{cascade_id}/{incident_id}"
                )
        if registry_native_count == 0:
            raise ValueError(
                f"Registre sans transaction de risque native: {registry.source}"
            )
        if len(registry_cascade_ids) != 1:
            raise ValueError(
                f"Le registre {registry.source} doit documenter exactement une cascade: "
                f"{sorted(registry_cascade_ids)}"
            )
        provenance_proofs.append(
            _validate_registry_campaign_pairing(
                registry,
                registry_cascade_id=next(iter(registry_cascade_ids)),
                final_campaign_source=final_campaign_source,
                final_runs=final_runs,
            )
        )
    missing_cascades = sorted(set(cascade_contracts) - set(matched_cascades))
    if missing_cascades:
        raise ValueError(
            "Cascade sans registre de risque natif correspondant: "
            + ", ".join(missing_cascades)
        )
    return (
        {
            cascade_id: sorted(sources)
            for cascade_id, sources in sorted(matched_cascades.items())
        },
        provenance_proofs,
    )


def _safe_script_json(payload: Any) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _asset_copy(source: Path, destination_dir: Path, destination_name: str) -> Path:
    resolved = source.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    target = destination_dir / destination_name
    if target.exists():
        raise FileExistsError(target)
    shutil.copy2(resolved, target)
    return target


def _validate_plotly_distribution(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    size = resolved.stat().st_size
    if not PLOTLY_MIN_BYTES <= size <= PLOTLY_MAX_BYTES:
        raise ValueError(
            f"Distribution Plotly de taille inattendue: {size} octets dans {resolved}"
        )
    with resolved.open("rb") as stream:
        header = stream.read(512).decode("utf-8", errors="replace")
    if f"plotly.js v{PLOTLY_VERSION}" not in header:
        raise ValueError(f"Signature Plotly {PLOTLY_VERSION} absente: {resolved}")
    if _sha256(resolved) != PLOTLY_SHA256:
        raise ValueError(
            f"Empreinte Plotly {PLOTLY_VERSION} non officielle: {resolved}"
        )
    return resolved


def _validate_world_topojson(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if resolved.stat().st_size < WORLD_TOPOJSON_MIN_BYTES:
        raise ValueError(f"Fond géographique Plotly incomplet: {resolved}")
    if _sha256(resolved) != WORLD_TOPOJSON_SHA256:
        raise ValueError(f"Empreinte world_110m.json non officielle: {resolved}")
    payload = _read_json(resolved)
    objects = payload.get("objects")
    arcs = payload.get("arcs")
    if (
        payload.get("type") != "Topology"
        or not isinstance(objects, dict)
        or not {"countries", "land"}.issubset(objects)
        or not isinstance(arcs, list)
        or not arcs
    ):
        raise ValueError(f"Contrat TopoJSON mondial invalide: {resolved}")
    return resolved


def _assert_offline_html(path: Path) -> None:
    document = path.read_text(encoding="utf-8")
    remote = re.findall(
        r"<(?:script|link|img)\b[^>]*(?:src|href)=[\"']https?://[^\"']+",
        document,
        flags=re.IGNORECASE,
    )
    if remote:
        raise ValueError(f"Dépendance réseau interdite dans {path}: {remote[:3]}")


def _offline_network_map_copy(
    source: Path,
    destination_dir: Path,
    destination_name: str,
    *,
    topojson: Path,
) -> Path:
    resolved = source.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    document = resolved.read_text(encoding="utf-8")
    if document.count(PLOTLY_CDN_URL) != 1:
        raise ValueError(
            "La carte attendue doit référencer une seule fois Plotly 2.32.0 contrôlé"
        )
    document = document.replace(PLOTLY_CDN_URL, "plotly-2.32.0.min.js")
    local_script = '<script src="plotly-2.32.0.min.js"></script>'
    if local_script not in document:
        raise ValueError(
            "Balise Plotly contrôlée introuvable après localisation de la carte"
        )
    encoded_topology = base64.b64encode(topojson.read_bytes()).decode("ascii")
    offline_config = (
        "<script>Plotly.setPlotConfig({topojsonURL:'./'});"
        "if(location.protocol==='file:'){Plotly.setPlotConfig({topojsonURL:"
        f"'data:application/json;base64,{encoded_topology}#'"
        "});}</script>"
    )
    document = document.replace(
        local_script,
        local_script + "\n  " + offline_config,
        1,
    )
    target = destination_dir / destination_name
    if target.exists():
        raise FileExistsError(target)
    target.write_text(document, encoding="utf-8")
    _assert_offline_html(target)
    return target


def _solution_cards(aggregates: Sequence[dict[str, Any]]) -> str:
    cards: list[str] = []
    for aggregate in aggregates:
        metrics = aggregate["metrics"]
        days = metrics["days_recovered_vs_no_action"]["mean"]
        worst_days = metrics["days_recovered_vs_no_action"]["min"]
        served_earlier = metrics["gross_positive_customer_service_gain_qty"]["mean"]
        net_served = metrics["net_customer_service_gain_qty"]["mean"]
        cost = metrics["incremental_decision_total_cost_vs_no_action"]["mean"]
        untreated_impact = metrics["no_action_incremental_customer_backlog_qty_days"]
        remaining_impact = metrics[
            "remaining_incremental_customer_backlog_qty_days"
        ]
        remaining = _remaining_backlog_ratio_of_means(metrics)
        exposure_frequency = aggregate["customer_exposure_frequency"]
        approximation = (
            '<span class="badge warn">partiellement approché</span>'
            if aggregate["approximation"]
            else '<span class="badge ok">levier natif vérifié</span>'
        )
        ranking = (
            '<span class="badge ok">classable parmi les cas avec retard client</span>'
            if aggregate["eligible"]
            else '<span class="badge stop">ne pas classer : preuve insuffisante</span>'
        )
        exclusions = " ; ".join(
            _ranking_exclusion_label(value) for value in aggregate["exclusion_reasons"]
        )
        days_number = _to_float(days)
        remaining_number = _to_float(remaining)
        if days_number is not None and days_number < -1e-9:
            effect_reading = (
                f"Attention : dans les cas avec retard client, cette action prolonge "
                f"le retour à la normale de {html.escape(_format_number(abs(days_number)))} "
                "jours en moyenne."
            )
            effect_class = "warning-text"
        elif remaining_number is not None and remaining_number > 1.0 + 1e-9:
            effect_reading = (
                "Attention : sur l’ensemble des répétitions, le retard cumulé moyen "
                "devient "
                f"{html.escape(_format_number(remaining_number, 2))} fois celui du cas "
                "sans action."
            )
            effect_class = "warning-text"
        elif remaining_number is not None and remaining_number <= 1e-9:
            effect_reading = (
                "Sur l’ensemble des répétitions, aucun retard client moyen résiduel "
                "n’est observé après cette action."
            )
            effect_class = ""
        elif remaining_number is not None and remaining_number < 1.0 - 1e-9:
            effect_reading = (
                "Sur l’ensemble des répétitions, le retard cumulé moyen est "
                f"réduit de {html.escape(_format_percent(1.0 - remaining_number))}."
            )
            effect_class = ""
        else:
            effect_reading = (
                "Aucune réduction du retard client cumulé n’est observée avec ce "
                "réglage."
            )
            effect_class = "warning-text"
        exposure_word = (
            "simulation"
            if aggregate["customer_exposure_count"] == 1
            else "simulations"
        )
        worst_day_number = _to_float(worst_days)
        worst_day_word = (
            "jour"
            if worst_day_number is not None
            and math.isclose(abs(worst_day_number), 1.0, abs_tol=1e-9)
            else "jours"
        )
        cards.append(
            f"""
            <article class="solution-card">
              <div class="eyebrow">{html.escape(aggregate["cascade_label"])}</div>
              <h3>{html.escape(aggregate["solution_label"])}</h3>
              <p>{html.escape(aggregate["solution_scope_note"])}</p>
              <div>{approximation} {ranking}</div>
              <div class="metric-grid">
                <div><strong>{html.escape(_format_percent(exposure_frequency))}</strong><span>part des simulations avec retard client</span></div>
                <div><strong>{html.escape(_format_number(days))}</strong><span>jours gagnés en moyenne parmi les cas avec retard client</span></div>
                <div><strong>{html.escape(_format_number(untreated_impact["mean"], 0))}</strong><span>retard client cumulé moyen sans action, cas absorbés inclus</span></div>
                <div><strong>{html.escape(_format_number(remaining_impact["mean"], 0))}</strong><span>retard client cumulé moyen restant avec cette action</span></div>
                <div><strong>{html.escape(_format_number(cost, 0))}</strong><span>surcoût réseau, unités monétaires du modèle</span></div>
                <div><strong>{html.escape(_format_percent(remaining))}</strong><span>part du retard moyen qui reste, rapport entre les deux moyennes</span></div>
              </div>
              <p class="{effect_class}"><strong>{effect_reading}</strong></p>
              <p>Un retard client apparaît dans {aggregate["customer_exposure_count"]} {exposure_word} sur {aggregate["simulation_count"]} ; l’incident est absorbé avant de dégrader le service dans {aggregate["customer_no_exposure_count"]} cas. Parmi les cas avec retard client, le gain le moins favorable est {html.escape(_format_number(worst_days))} {worst_day_word}. L’action est réellement exécutée dans {aggregate["verified_count"]} simulations. Elle sert {html.escape(_format_number(served_earlier, 0))} unités plus tôt certains jours, pour un solde de {html.escape(_format_number(net_served, 0))} unités sur toute la période.</p>
              {f'<p class="warning-text">{html.escape(exclusions)}</p>' if exclusions else ""}
            </article>
            """
        )
    return "".join(cards)


def _solution_table(aggregates: Sequence[dict[str, Any]]) -> str:
    rows: list[str] = []
    for aggregate in aggregates:
        metrics = aggregate["metrics"]
        days = metrics["days_recovered_vs_no_action"]
        remaining_impact = metrics[
            "remaining_incremental_customer_backlog_qty_days"
        ]
        remaining_ratio = _remaining_backlog_ratio_of_means(metrics)
        rows.append(
            "<tr>"
            f"<td>{html.escape(aggregate['cascade_label'])}</td>"
            f"<td>{html.escape(aggregate['solution_label'])}</td>"
            f"<td>{html.escape(_format_percent(aggregate['customer_exposure_frequency']))}</td>"
            f"<td>{html.escape(_format_number(days['mean']))}</td>"
            f"<td>{html.escape(_format_number(days['p10']))} à {html.escape(_format_number(days['p90']))}</td>"
            f"<td>{html.escape(_format_number(days['min']))}</td>"
            f"<td>{html.escape(_format_number(remaining_impact['mean'], 0))}</td>"
            f"<td>{html.escape(_format_number(remaining_impact['max'], 0))}</td>"
            f"<td>{html.escape(_format_number(metrics['shortage_days_avoided']['mean']))}</td>"
            f"<td>{html.escape(_format_number(metrics['gross_positive_customer_service_gain_qty']['mean'], 0))}</td>"
            f"<td>{html.escape(_format_number(metrics['net_customer_service_gain_qty']['mean'], 0))}</td>"
            f"<td>{html.escape(_format_number(metrics['incremental_decision_total_cost_vs_no_action']['mean'], 0))}</td>"
            f"<td>{html.escape(_format_number(metrics['incremental_stock_qty_days']['mean'], 0))}</td>"
            f"<td>{html.escape(_format_percent(remaining_ratio))}</td>"
            f"<td>{'Oui' if aggregate['eligible'] else 'Non'}</td>"
            f"<td>{'Approché' if aggregate['approximation'] else 'Natif'}</td>"
            "</tr>"
        )
    return "".join(rows)


def _tradeoff_svg(cascade_id: str, rows: Sequence[dict[str, Any]]) -> str:
    points: list[tuple[float, float, str, bool]] = []
    for row in rows:
        if row["cascade_id"] != cascade_id:
            continue
        if not row["eligible"]:
            continue
        cost = _to_float(
            row["metrics"]["incremental_decision_total_cost_vs_no_action"]["mean"]
        )
        days = _to_float(row["metrics"]["days_recovered_vs_no_action"]["mean"])
        if cost is None or days is None:
            continue
        points.append((cost, days, row["solution_label"], bool(row["approximation"])))
    if not points:
        return '<p class="empty">Données d’arbitrage non disponibles.</p>'

    width, height = 760, 330
    left, right, top, bottom = 82, 30, 30, 68
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_min, x_max = min(xs + [0.0]), max(xs + [0.0])
    y_min, y_max = min(ys + [0.0]), max(ys + [0.0])
    if abs(x_max - x_min) < 1e-9:
        x_min -= 1.0
        x_max += 1.0
    if abs(y_max - y_min) < 1e-9:
        y_min -= 1.0
        y_max += 1.0

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * (width - left - right)

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * (height - top - bottom)

    elements = [
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" class="axis"/>',
        f'<line x1="{sx(0):.1f}" y1="{top}" x2="{sx(0):.1f}" y2="{height - bottom}" class="zero"/>',
        f'<line x1="{left}" y1="{sy(0):.1f}" x2="{width - right}" y2="{sy(0):.1f}" class="zero"/>',
        f'<text x="{width / 2}" y="{height - 16}" text-anchor="middle">Surcoût réseau — unités monétaires du modèle</text>',
        f'<text x="18" y="{height / 2}" text-anchor="middle" transform="rotate(-90 18 {height / 2})">Jours gagnés</text>',
    ]
    for cost, days, label, approximation in points:
        color = "#f59e0b" if approximation else "#22c55e"
        elements.append(
            f'<circle cx="{sx(cost):.1f}" cy="{sy(days):.1f}" r="7" fill="{color}"/>'
        )
        elements.append(
            f'<text x="{sx(cost) + 10:.1f}" y="{sy(days) - 8:.1f}" class="point-label">{html.escape(label)}</text>'
        )
    return f'<svg class="tradeoff" viewBox="0 0 {width} {height}" role="img">{"".join(elements)}</svg>'


def _cascade_story(cascade_id: str, cascade_config: dict[str, Any]) -> dict[str, str]:
    incident = cascade_config.get("incident") or {}
    events = incident.get("risk_events") or []
    event = events[0] if events and isinstance(events[0], dict) else {}
    start = int(incident.get("start_day") or 0)
    end = int(incident.get("end_day") or 0)
    suppliers = sorted(
        {
            str(candidate.get("supplier_id"))
            for candidate in events
            if isinstance(candidate, dict) and candidate.get("supplier_id")
        }
    )
    destinations = sorted(
        {
            str(candidate.get("dst_node_id"))
            for candidate in events
            if isinstance(candidate, dict) and candidate.get("dst_node_id")
        }
    )

    def french_list(values: Sequence[str], fallback: str) -> str:
        if not values:
            return fallback
        if len(values) == 1:
            return values[0]
        return ", ".join(values[:-1]) + " et " + values[-1]

    supplier = french_list(suppliers, "le fournisseur ciblé")
    destination = french_list(destinations, "le site destinataire")
    item = str(event.get("item_id") or "le composant").replace("item:", "")
    duration = _format_number(event.get("multiplier"), 0)
    if "021081" in cascade_id or "quality" in cascade_id:
        return {
            "incident": (
                "Dans ce scénario, une hypothèse de défaut commun à un sous-tier "
                f"affecte trois sources approuvées. Pour les besoins de {item} lancés "
                f"du jour {start} au jour {end} "
                f"auprès de {supplier} vers {destination}, la date de disponibilité "
                f"est repoussée de {duration} jours. La décision de retenue reste attachée "
                "au mouvement jusqu’à sa libération et sa réception. La matière n’est pas "
                "détruite ; le stock déjà présent et les expéditions déjà en transit ne "
                "sont pas requalifiés rétroactivement."
            ),
            "path": (
                "021081 → SDC-1450 → fabrication de 773474 → M-1430 → "
                "fabrication de 268967 → DC-1920 → client"
            ),
            "lot": (
                "268967 : lot fixe de référence de 107 800 unités. "
                "773474 : règle de 3 200 000 g à confirmer avec l’industriel."
            ),
        }
    return {
        "incident": (
            f"Pour les besoins de {item} lancés du jour {start} au jour {end} "
            f"auprès de {supplier} vers {destination}, {duration} jours de transport "
            "sont ajoutés. L’effet décidé pendant cette fenêtre reste attaché au "
            "mouvement jusqu’à sa libération et sa réception ; les expéditions déjà "
            "en transit au moment de la décision ne sont pas redatées."
        ),
        "path": "SDC-VD0914360C → 338929 → M-1810 → fabrication de 268091 → DC-1920 → client",
        "lot": (
            "338929 est mono-source dans le réseau actuel. Pour 268091, 14 400 unités "
            "sont le minimum et le multiple, pas une taille fixe ; une campagne peut "
            "atteindre 142 485 unités."
        ),
    }


def _entity_label(value: str) -> str:
    return {
        "supplier_source_lot": "Allocation FIFO simulée du stock source fournisseur",
        "finished_product_lot": "Lot de produit fini libéré",
        "opening_stock_lot": "Lot du stock d’ouverture",
        "customer_receipt_lot": "Lot reçu par le client",
        "distribution_receipt_lot": "Lot reçu en distribution",
        "plant_material_lot": "Lot matière en usine",
        "supplier_material_lot": "Lot matière fournisseur",
        "physical_lot": "Lot physique",
        "production_campaign": "Campagne de fabrication",
    }.get(value, value.replace("_", " "))


def _causality_label(value: str) -> str:
    return {
        "native_transaction": (
            "Rattaché à l’expédition/réception qui porte l’identifiant de risque"
        ),
        "physical_genealogy": "Propagation par généalogie de lots simulée",
        "scope_day_association": "Association de périmètre et de date",
        "temporal_association": "Association temporelle uniquement",
    }.get(value, value or "non précisé")


def _attribution_method_label(value: str) -> str:
    return {
        "shipment_source_lot_fifo_reconstruction": (
            "Allocation FIFO simulée du stock source"
        ),
        "same_item_transport_mass_balance": (
            "Réconciliation quantitative de l’expédition à la réception"
        ),
        "risk_exposed_receipt_seed": "Réception issue d’un mouvement identifié",
        "component_mix_union_bounds": "Bornes d’union après mélange de composants",
        "campaign_output_lot_aggregation:component_mix_union_bounds": (
            "Agrégation de campagne puis bornes après mélange"
        ),
    }.get(value, value.replace("_", " ") if value else "non précisée")


def _ranking_exclusion_label(value: str) -> str:
    translations = {
        "This is not a graph-native second supplier and must not compete with physically identified business options.": (
            "Ce second fournisseur n’existe pas dans le réseau actuel : ce test ne doit "
            "pas être classé avec les solutions physiquement identifiées."
        ),
        "Declared negative control: a relative supplier priority has no alternative lane on 338929.": (
            "Test témoin : prioriser un fournisseur ne peut pas déplacer le flux 338929 "
            "car aucune autre liaison fournisseur n’existe."
        ),
        "every configured action signature was not verified with positive physical volume": (
            "Toutes les actions prévues n’ont pas été observées avec un volume physique positif."
        ),
        "untreated customer recovery is censored by the simulation horizon": (
            "Le retour à la normale sans action dépasse la fin de la simulation."
        ),
        "solution customer recovery is censored by the simulation horizon": (
            "Le retour à la normale avec cette solution dépasse la fin de la simulation."
        ),
        (
            "untreated incident was physically applied but caused no customer exposure; "
            "customer-recovery metrics are not applicable for this seed"
        ): (
            "L’incident a bien été appliqué, mais il a été absorbé avant le client pour "
            "cette répétition ; aucun délai de récupération client n’est calculé."
        ),
    }
    parts = [part.strip() for part in value.split("|") if part.strip()]
    return " ; ".join(translations.get(part, part) for part in parts)


def _cost_status_label(value: str) -> str:
    return {
        "not_identified_without_matched_counterfactual": (
            "Non identifié dans la seule généalogie : utiliser la comparaison avec le "
            "même cas sans incident."
        )
    }.get(value, value or "non identifié")


def _cost_rule_label(value: str) -> str:
    return {
        "bundle costs count once; event-level incident summaries overlap": (
            "Compter chaque ensemble exposé une seule fois ; les incidents d’un même "
            "ensemble se chevauchent."
        )
    }.get(value, value)


def _cost_note_label(value: str) -> str:
    return {
        "Actual exposed transaction cost is not the causal cost of the incident. Downstream stock, production and service costs require a paired counterfactual.": (
            "Le coût observé sur l’expédition exposée n’est pas, à lui seul, le surcoût "
            "causé par l’incident. Les effets sur le stock, la production et le service "
            "viennent de la comparaison appariée."
        )
    }.get(value, value)


def _incident_summaries(
    runs: Sequence[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in runs:
        if str(row.get("case_type") or "") == "incident_no_action":
            grouped[str(row.get("cascade_id") or "")].append(row)
    summaries: dict[str, dict[str, Any]] = {}
    for cascade_id, rows in grouped.items():
        backlog = [
            _to_float(row.get("customer_backlog_qty_days")) or 0.0 for row in rows
        ]
        delayed_count = sum(value > 1e-9 for value in backlog)
        fully_served_count = sum(
            abs(
                (_to_float(row.get("customer_demand_qty")) or 0.0)
                - (_to_float(row.get("customer_served_qty")) or 0.0)
            )
            <= 1e-6
            for row in rows
        )
        summaries[cascade_id] = {
            "simulation_count": len(rows),
            "delayed_count": delayed_count,
            "absorbed_count": len(rows) - delayed_count,
            "fully_served_count": fully_served_count,
            "backlog_qty_days": _metric_summary(rows, "customer_backlog_qty_days"),
            "shortage_days": _metric_summary(rows, "customer_shortage_days"),
        }
    return summaries


def _cascade_sections(
    aggregates: Sequence[dict[str, Any]],
    cascade_contracts: dict[str, dict[str, Any]],
    incident_summaries: dict[str, dict[str, Any]],
) -> str:
    cascade_ids = sorted({row["cascade_id"] for row in aggregates})
    sections: list[str] = []
    for cascade_id in cascade_ids:
        group = [row for row in aggregates if row["cascade_id"] == cascade_id]
        eligible = [row for row in group if row["eligible"]]

        def rank_key(row: dict[str, Any]) -> tuple[float, float, float]:
            remaining = _to_float(
                row["metrics"]["remaining_incremental_customer_backlog_qty_days"][
                    "mean"
                ]
            )
            days = _to_float(row["metrics"]["days_recovered_vs_no_action"]["mean"])
            cost = _to_float(
                row["metrics"]["incremental_decision_total_cost_vs_no_action"]["mean"]
            )
            return (
                remaining if remaining is not None else math.inf,
                -(days if days is not None else -math.inf),
                cost if cost is not None else math.inf,
            )

        eligible.sort(key=rank_key)
        best = eligible[0] if eligible else None
        best_solution_id = (
            str(best["solution_id"]) if best else str(group[0]["solution_id"])
        )
        if best:
            best_days = best["metrics"]["days_recovered_vs_no_action"]["mean"]
            served = best["metrics"]["gross_positive_customer_service_gain_qty"]["mean"]
            untreated_impact = best["metrics"][
                "no_action_incremental_customer_backlog_qty_days"
            ]["mean"]
            remaining_impact = best["metrics"][
                "remaining_incremental_customer_backlog_qty_days"
            ]["mean"]
            remaining = _remaining_backlog_ratio_of_means(best["metrics"])
            headline = (
                "Meilleure performance simulée classable : "
                f"<strong>{html.escape(best['solution_label'])}</strong>, "
                f"{html.escape(_format_number(best_days))} jours gagnés en moyenne et "
                f"{html.escape(_format_number(served, 0))} unités servies plus tôt certains jours. "
                f"Un retard client apparaît dans {best['customer_exposure_count']} cas sur "
                f"{best['simulation_count']}."
            )
            meaning = (
                "Sur les dix répétitions, cas absorbés inclus, le retard client cumulé "
                f"moyen passe de {html.escape(_format_number(untreated_impact, 0))} à "
                f"{html.escape(_format_number(remaining_impact, 0))} unités·jours : "
                f"{html.escape(_format_percent(remaining))} reste. Cette performance "
                "reste à recalibrer avec les règles et coûts industriels."
            )
        elif all(row["customer_exposure_count"] == 0 for row in group):
            headline = (
                "L’incident est physiquement appliqué, mais les stocks et capacités "
                "protègent le client dans toutes les répétitions observées."
            )
            meaning = (
                "Il n’y a aucun jour client à récupérer : afficher un gain de délai serait "
                "artificiel. Les perturbations de production et les coûts des actions restent "
                "visibles, mais les solutions ne sont pas classées sur le service client."
            )
        else:
            headline = (
                "Aucune solution ne possède encore toutes les preuves nécessaires pour "
                "être classée. Les résultats restent visibles à titre de diagnostic."
            )
            meaning = "Ne pas recommander une action tant que la preuve physique ou la récupération est incomplète."
        story = _cascade_story(cascade_id, cascade_contracts[cascade_id])
        incident_summary = incident_summaries[cascade_id]
        untreated_backlog = incident_summary["backlog_qty_days"]
        untreated_days = incident_summary["shortage_days"]
        options = "".join(
            (
                f'<option value="{html.escape(str(row["solution_id"]))}"'
                f"{' selected' if row['solution_id'] == best_solution_id else ''}>"
                f"{html.escape(row['solution_label'])}"
                "</option>"
            )
            for row in group
        )
        section_id = "cascade-" + "".join(
            character if character.isalnum() else "-"
            for character in cascade_id.lower()
        )
        sections.append(
            f"""
            <section class="tab-panel" id="{html.escape(section_id)}">
              <div class="section-head"><span class="kicker">CASCADE MÉTIER</span><h2>{html.escape(_cascade_label(cascade_id))}</h2></div>
              <div class="causal-chain">
                <span>Incident</span><b>→</b><span>Expédition touchée</span><b>→</b><span>Stock critique</span><b>→</b><span>Encours et lot libéré</span><b>→</b><span>Retard client</span><b>→</b><span>Action</span>
              </div>
              <article class="incident-box"><h3>Incident simulé</h3><p>{html.escape(story["incident"])}</p><p><strong>Chemin suivi :</strong> {html.escape(story["path"])}</p><p><strong>Règle de lot :</strong> {html.escape(story["lot"])}</p></article>
              <div class="case-triad">
                <article><span class="case-dot normal"></span><h3>Référence sans incident</h3><p>Même état initial simulé et mêmes nombres aléatoires.</p></article>
                <article><span class="case-dot incident"></span><h3>Incident sans action</h3><p>Mesure la perturbation attribuable à l’incident.</p></article>
                <article><span class="case-dot solution"></span><h3>Incident avec action</h3><p>Mesure les gains, pertes, coûts et effets de report.</p></article>
              </div>
              <div class="incident-kpis">
                <article><strong>{incident_summary["delayed_count"]}/{incident_summary["simulation_count"]}</strong><span>simulations avec retard client sans action</span></article>
                <article><strong>{html.escape(_format_number(untreated_backlog["mean"], 0))}</strong><span>unités·jours de retard en moyenne, cas absorbés inclus</span></article>
                <article><strong>{html.escape(_format_number(untreated_backlog["max"], 0))}</strong><span>unités·jours dans le cas le plus défavorable observé</span></article>
                <article><strong>{html.escape(_format_number(untreated_days["mean"]))} / {html.escape(_format_number(untreated_days["max"]))}</strong><span>jours avec retard : moyenne / maximum</span></article>
              </div>
              <p class="definition-note"><strong>Comment lire « unités·jours » :</strong> 10 000 unités en retard pendant un jour valent 10 000 unités·jours. Ce n’est ni un nombre de commandes, ni une vente perdue, ni un chiffre d’affaires. La demande est finalement servie dans {incident_summary["fully_served_count"]} cas sur {incident_summary["simulation_count"]}.</p>
              <div class="panel-grid">
                <article class="narrative"><h3>Ce que l’on observe</h3><p>{headline}</p></article>
                <article class="narrative"><h3>Ce que cela signifie</h3><p>{meaning}</p></article>
                <article class="narrative"><h3>Décision possible</h3><p>Comparer le délai récupéré au coût, au stock créé et à la fidélité du levier. Les actions marquées « approché » doivent être validées avec les règles opérationnelles de l’industriel.</p></article>
              </div>
              <div class="trajectory-head"><div><h3>Courbes quotidiennes</h3><p>Moyenne et enveloppe minimum–maximum des répétitions appariées.</p></div><label>Action affichée<select class="trajectory-solution" data-cascade="{html.escape(cascade_id)}">{options}</select></label></div>
              <div class="trajectory-grid" data-cascade-charts="{html.escape(cascade_id)}"></div>
              <h3>Arbitrage délai / coût</h3>
              {_tradeoff_svg(cascade_id, group)}
              <div class="cards">{_solution_cards(group)}</div>
            </section>
            """
        )
    return "".join(sections)


_ENTITY_BUSINESS_STAGE_ORDER = {
    "physical_lot": 0,
    "plant_material_lot": 1,
    "production_campaign": 2,
    "finished_product_lot": 3,
    "distribution_receipt_lot": 4,
    "customer_receipt_lot": 5,
    "opening_stock_lot": 6,
    "supplier_material_lot": 7,
    "supplier_source_lot": 8,
}


def _business_entity_preview(
    rows: Sequence[dict[str, str]], limit: int
) -> list[dict[str, str]]:
    """Return a deterministic, stage-balanced preview for the HTML table.

    Supplier stock can be reconstructed into hundreds of FIFO fragments. A direct
    slice would hide the much smaller receipt, production and customer stages. The
    complete, original-order table remains available in the packaged CSV.
    """

    if limit < 1:
        return []
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        entity_type = str(
            row.get("entity_type")
            or row.get("entity_kind")
            or row.get("stage")
            or "entity"
        )
        key = (str(row.get("_registry_source") or ""), entity_type)
        groups.setdefault(key, []).append(row)
    ordered_keys = sorted(
        groups,
        key=lambda key: (
            _ENTITY_BUSINESS_STAGE_ORDER.get(key[1], 99),
            key[0],
            key[1],
        ),
    )
    for key in ordered_keys:
        groups[key].sort(
            key=lambda row: (
                _to_float(row.get("day"))
                if _to_float(row.get("day")) is not None
                else math.inf,
                str(row.get("entity_id") or row.get("lot_id") or ""),
                str(row.get("incident_id") or ""),
            )
        )
    preview: list[dict[str, str]] = []
    cursor = {key: 0 for key in ordered_keys}
    while len(preview) < min(limit, len(rows)):
        added = False
        for key in ordered_keys:
            position = cursor[key]
            if position >= len(groups[key]):
                continue
            preview.append(groups[key][position])
            cursor[key] = position + 1
            added = True
            if len(preview) >= limit:
                break
        if not added:
            break
    return preview


def _risk_entity_table(rows: Sequence[dict[str, str]], limit: int = 120) -> str:
    if not rows:
        return '<tr><td colspan="12">Aucune entité d’impact chargée.</td></tr>'
    rendered: list[str] = []
    for row in _business_entity_preview(rows, limit):
        entity_type = (
            row.get("entity_type")
            or row.get("entity_kind")
            or row.get("stage")
            or "entité"
        )
        entity_id = (
            row.get("entity_id")
            or row.get("lot_id")
            or row.get("campaign_id")
            or row.get("customer_id")
            or ""
        )
        lower = (
            row.get("attributed_qty_lower")
            or row.get("lower_qty")
            or row.get("qty_lower")
            or ""
        )
        upper = (
            row.get("attributed_qty_upper")
            or row.get("upper_qty")
            or row.get("qty_upper")
            or ""
        )
        rendered.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('_registry_source') or ''))}</td>"
            f"<td>{html.escape(str(row.get('incident_id') or ''))}</td>"
            f"<td>{html.escape(_entity_label(str(entity_type)))}</td>"
            f"<td>{html.escape(str(entity_id))}</td>"
            f"<td>{html.escape(str(row.get('item_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('node_id') or row.get('customer_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('day') or ''))}</td>"
            f"<td>{html.escape(_format_number(lower, 1))}</td>"
            f"<td>{html.escape(_format_number(upper, 1))}</td>"
            f"<td>{html.escape(str(row.get('uom') or ''))}</td>"
            f"<td>{html.escape(_attribution_method_label(str(row.get('attribution_method') or '')))}</td>"
            f"<td>{html.escape(_causality_label(str(row.get('causality_level') or '')))}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _risk_client_table(rows: Sequence[dict[str, str]], limit: int = 120) -> str:
    if not rows:
        return '<tr><td colspan="10">Aucune relation client chargée.</td></tr>'
    rendered: list[str] = []
    for row in rows[:limit]:
        rendered.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('_registry_source') or ''))}</td>"
            f"<td>{html.escape(str(row.get('incident_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('client_lot_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('day') or ''))}</td>"
            f"<td>{html.escape(str(row.get('client_node_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('item_id') or ''))}</td>"
            f"<td>{html.escape(_format_number(row.get('served_exposed_qty_lower'), 1))}</td>"
            f"<td>{html.escape(_format_number(row.get('served_exposed_qty_upper'), 1))}</td>"
            f"<td>{html.escape(str(row.get('uom') or ''))}</td>"
            f"<td>{html.escape(_causality_label(str(row.get('causality_level') or '')))}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _risk_cost_table(rows: Sequence[dict[str, str]], limit: int = 120) -> str:
    if not rows:
        return '<tr><td colspan="8">Aucune relation de coût chargée.</td></tr>'
    rendered: list[str] = []
    for row in rows[:limit]:
        rendered.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('_registry_source') or ''))}</td>"
            f"<td>{html.escape(str(row.get('exposure_bundle_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('shipment_id') or ''))}</td>"
            f"<td>{html.escape(_format_number(row.get('transport_cost_actual_exposed'), 2))}</td>"
            f"<td>{html.escape(_format_number(row.get('purchase_cost_actual_exposed'), 2))}</td>"
            f"<td>{html.escape(_cost_status_label(str(row.get('incremental_total_cost_status') or '')))}</td>"
            f"<td>{html.escape(_cost_rule_label(str(row.get('cost_aggregation_rule') or '')))}</td>"
            f"<td>{html.escape(_cost_note_label(str(row.get('notes') or '')))}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _table_truncation_notice(
    rows: Sequence[dict[str, str]],
    *,
    limit: int,
    csv_filename: str,
) -> str:
    if limit < 1:
        raise ValueError("La limite d'affichage d'un tableau doit être positive")
    total = len(rows)
    if total <= limit:
        return ""
    return (
        '<p class="table-note"><strong>'
        f"{limit} lignes affichées sur {total}.</strong> "
        "Le ou les CSV complets sont inclus dans "
        f"<code>data/risk_registry_XX/{html.escape(csv_filename)}</code>."
        "</p>"
    )


def _render_document(
    *,
    runs: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    aggregates: list[dict[str, Any]],
    incidents: list[dict[str, str]],
    entities: list[dict[str, str]],
    client_service: list[dict[str, str]],
    costs: list[dict[str, str]],
    quality: list[dict[str, Any]],
    trajectory_payload: dict[str, Any],
    evidence: dict[str, Any],
    config_snapshot: dict[str, Any],
    asset_links: dict[str, str],
) -> str:
    cascade_ids = sorted(
        {row.get("cascade_id", "") for row in runs if row.get("cascade_id")}
    )
    solution_ids = {
        (row.get("cascade_id"), row.get("solution_id")) for row in comparisons
    }
    incident_ids = {
        row.get("incident_id") for row in incidents if row.get("incident_id")
    }
    native_incidents = {
        row.get("incident_id")
        for row in incidents
        if row.get("incident_id")
        and str(row.get("causality_level") or "") == "native_transaction"
    }
    approximate_rows = sum(1 for row in aggregates if row["approximation"])
    approximation_phrase = (
        f"{approximate_rows} comparaison utilise"
        if approximate_rows == 1
        else f"{approximate_rows} comparaisons utilisent"
    )
    repeated_seed_count = int(evidence.get("minimum_seed_count") or 0)
    upstream_integrity = evidence.get("upstream_integrity", {})
    trajectory_long_rows = int(
        upstream_integrity.get("trajectory_long_csv_copy_row_count") or 0
    )
    trajectory_long_hash = str(
        upstream_integrity.get("trajectory_long_csv_copy_sha256") or ""
    )
    trajectory_long_pack_path = str(
        upstream_integrity.get("trajectory_long_csv_pack_path") or ""
    )
    registry_seeds = sorted(
        {
            int(proof["identity"]["seed"])
            for proof in evidence.get("risk_registry_provenance", [])
            if isinstance(proof, dict)
            and isinstance(proof.get("identity"), dict)
            and proof["identity"].get("seed") is not None
        }
    )
    registry_seed_text = ", ".join(str(seed) for seed in registry_seeds)
    cascade_contracts = {
        str(cascade.get("id") or ""): cascade
        for cascade in config_snapshot.get("cascades", [])
        if isinstance(cascade, dict) and cascade.get("id")
    }
    if set(cascade_ids) - set(cascade_contracts):
        raise ValueError("Configuration de cascade absente du snapshot")
    incident_summaries = _incident_summaries(runs)
    if set(incident_summaries) != set(cascade_ids):
        raise ValueError("Synthèse des incidents sans action incomplète")
    tabs = [
        ("overview", "Vue d’ensemble"),
        *(
            (
                "cascade-"
                + "".join(
                    character if character.isalnum() else "-"
                    for character in cascade_id.lower()
                ),
                _cascade_label(cascade_id),
            )
            for cascade_id in cascade_ids
        ),
        ("solutions", "Comparer les solutions"),
        ("lots-clients", "Lots et livraisons"),
        ("pilotage", "MRP et pilotage"),
        ("limits", "Hypothèses et limites"),
    ]
    nav = "".join(
        f'<button class="tab-button{" active" if index == 0 else ""}" data-tab="{html.escape(tab_id)}">{html.escape(label)}</button>'
        for index, (tab_id, label) in enumerate(tabs)
    )
    assets = "".join(
        f'<a class="asset-link" href="{html.escape(path)}">{html.escape(label)}</a>'
        for label, path in asset_links.items()
    )
    embedded = _safe_script_json(
        {
            "schema_version": DEMO_SCHEMA_VERSION,
            "aggregates": aggregates,
            "quality": quality,
            "evidence": evidence,
            "cascade_contracts": {
                cascade_id: {
                    "incident_start_day": int(
                        cascade_contracts[cascade_id]["incident"]["start_day"]
                    ),
                    "incident_end_day": int(
                        cascade_contracts[cascade_id]["incident"]["end_day"]
                    ),
                }
                for cascade_id in cascade_ids
            },
            "client_service_relation_count": len(client_service),
            "risk_cost_relation_count": len(costs),
        }
    )
    embedded_trajectories = _safe_script_json(trajectory_payload)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Du risque fournisseur à la décision — démonstration supply chain</title>
  <style>
    :root{{--ink:#122033;--muted:#58677b;--paper:#f5f7fb;--card:#fff;--line:#dbe2ea;--blue:#155eef;--navy:#0b1f3a;--green:#16845b;--amber:#b86b00;--red:#b42318;--shadow:0 18px 50px rgba(20,38,65,.10)}}
    *{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Inter,Segoe UI,Arial,sans-serif}} a{{color:inherit}}
    .hero{{background:linear-gradient(125deg,#07192f 0%,#123a69 62%,#0d6b67 100%);color:white;padding:42px max(28px,calc((100vw - 1420px)/2));}}
    .hero h1{{font-size:clamp(30px,4vw,56px);line-height:1.05;margin:8px 0 16px;max-width:1000px}} .hero p{{font-size:18px;max-width:900px;color:#d9e8f8}}
    .hero .kicker{{letter-spacing:.14em;font-weight:700;color:#84e1cc}}
    .hero-metrics{{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:12px;margin-top:28px;max-width:1050px}}
    .hero-metrics div{{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:16px}} .hero-metrics strong{{display:block;font-size:27px}} .hero-metrics span{{color:#cfe0f2}}
    .notice{{margin:20px auto 0;max-width:1420px;background:#fff7e8;border:1px solid #f3d39b;border-radius:12px;padding:14px 18px;color:#714500}}
    .nav-wrap{{position:sticky;top:0;z-index:10;background:rgba(245,247,251,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}}
    nav{{max-width:1420px;margin:auto;display:flex;gap:8px;overflow:auto;padding:12px 18px}} .tab-button{{border:1px solid var(--line);background:white;border-radius:999px;padding:9px 14px;white-space:nowrap;cursor:pointer;color:var(--ink)}} .tab-button.active{{background:var(--navy);color:white;border-color:var(--navy)}}
    main{{max-width:1420px;margin:0 auto;padding:26px 20px 70px}} .tab-panel{{display:none;scroll-margin-top:96px}} .tab-panel.active{{display:block}}
    .section-head{{margin:10px 0 22px}} .section-head h2{{font-size:32px;line-height:1.15;margin:4px 0}} .kicker,.eyebrow{{font-size:12px;font-weight:800;letter-spacing:.12em;color:var(--blue)}}
    .journey{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:24px 0}} .journey article{{background:white;border:1px solid var(--line);border-radius:15px;padding:17px;box-shadow:var(--shadow)}} .journey b{{color:var(--blue);font-size:20px}}
    .causal-chain{{display:flex;gap:9px;align-items:center;overflow:auto;background:white;border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:18px}} .causal-chain span{{background:#edf3ff;border-radius:9px;padding:8px 11px;white-space:nowrap}} .causal-chain b{{color:var(--blue)}}
    .panel-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}} .narrative,.solution-card,.data-card{{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:18px;box-shadow:var(--shadow)}} .narrative h3,.solution-card h3{{margin-top:0}}
    .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:20px 0}} .solution-card h3{{font-size:22px}}
    .metric-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0}} .metric-grid div{{background:#f6f8fb;border-radius:10px;padding:10px}} .metric-grid strong{{display:block;font-size:20px}} .metric-grid span{{display:block;color:var(--muted);font-size:12px}}
    .badge{{display:inline-block;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:700;margin:2px}} .badge.ok{{background:#e8f7f0;color:#08734d}} .badge.warn{{background:#fff2dc;color:#8c5100}} .badge.stop{{background:#feeceb;color:#9f261d}} .warning-text{{color:var(--red);font-size:13px}}
    .incident-box{{background:#eef5ff;border:1px solid #bdd2f4;border-left:6px solid var(--blue);border-radius:14px;padding:16px 20px;margin:16px 0}} .incident-box h3{{margin:0 0 6px}}
    .case-triad{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}} .case-triad article{{background:white;border:1px solid var(--line);border-radius:14px;padding:16px}} .case-triad h3{{margin:4px 0}} .case-dot{{width:12px;height:12px;border-radius:50%;display:inline-block}} .case-dot.normal{{background:#7b8794}} .case-dot.incident{{background:#d92d20}} .case-dot.solution{{background:#179b67}}
    .incident-kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 10px}} .incident-kpis article{{background:#fff;border:1px solid var(--line);border-top:4px solid var(--red);border-radius:14px;padding:15px}} .incident-kpis strong{{display:block;font-size:25px}} .incident-kpis span{{display:block;color:var(--muted);font-size:12px}} .definition-note{{background:#f8fafc;border-left:4px solid #7b8794;border-radius:8px;padding:11px 14px;color:var(--muted)}}
    .trajectory-head{{display:flex;justify-content:space-between;gap:20px;align-items:end;margin:26px 0 12px}} .trajectory-head h3,.trajectory-head p{{margin:0}} .trajectory-head label{{font-weight:700}} .trajectory-head select{{display:block;max-width:520px;margin-top:5px;padding:9px;border:1px solid var(--line);border-radius:9px;background:white}}
    .trajectory-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:28px}} .chart-card{{background:white;border:1px solid var(--line);border-radius:14px;padding:14px;min-width:0}} .chart-card h4{{margin:0 0 2px}} .chart-card p{{color:var(--muted);margin:0 0 8px;font-size:12px}} .daily-chart{{width:100%;height:auto;display:block}} .chart-axis{{stroke:#9aa6b2;stroke-width:1}} .chart-grid{{stroke:#e5e9ef;stroke-width:1}} .band-normal{{fill:#7b8794;opacity:.10}} .band-incident{{fill:#d92d20;opacity:.11}} .band-solution{{fill:#179b67;opacity:.12}} .line-normal{{fill:none;stroke:#6b7785;stroke-width:1.8}} .line-incident{{fill:none;stroke:#d92d20;stroke-width:2}} .line-solution{{fill:none;stroke:#179b67;stroke-width:2}} .incident-window{{fill:#f97066;opacity:.10}} .chart-legend{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px}} .legend-line{{display:inline-block;width:20px;height:3px;vertical-align:middle;margin-right:4px}} 
    .tradeoff{{width:100%;max-width:900px;background:white;border:1px solid var(--line);border-radius:14px}} .tradeoff text{{font:13px Segoe UI,Arial;fill:var(--muted)}} .tradeoff .point-label{{font-size:12px;fill:var(--ink)}} .axis{{stroke:#617086;stroke-width:1.2}} .zero{{stroke:#b6c0cc;stroke-dasharray:4 4}}
    .table-wrap{{overflow:auto;background:white;border:1px solid var(--line);border-radius:14px}} table{{border-collapse:collapse;width:100%;min-width:1100px}} th,td{{padding:11px 12px;text-align:left;border-bottom:1px solid #e6ebf1;vertical-align:top}} th{{background:#eef3f8;position:sticky;top:0}} td{{font-variant-numeric:tabular-nums}} .table-note{{margin:14px 0 8px;padding:10px 13px;background:#eef5ff;border-left:4px solid var(--blue);border-radius:8px}}
    .asset-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}} .asset-link{{display:block;text-decoration:none;background:white;border:1px solid var(--line);border-radius:14px;padding:20px;font-size:18px;font-weight:700;box-shadow:var(--shadow)}} .asset-link:hover{{border-color:var(--blue);transform:translateY(-1px)}}
    .limits{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .limits article{{background:white;border:1px solid var(--line);border-radius:14px;padding:18px}} .limits li{{margin:7px 0}}
    footer{{max-width:1420px;margin:auto;padding:25px;color:var(--muted);border-top:1px solid var(--line)}} .empty{{color:var(--muted)}}
    @media(max-width:900px){{.hero-metrics,.panel-grid,.limits,.incident-kpis{{grid-template-columns:1fr 1fr}}.journey{{grid-template-columns:repeat(2,1fr)}}.trajectory-grid{{grid-template-columns:1fr}}}}
    @media(max-width:600px){{.hero-metrics,.panel-grid,.limits,.metric-grid,.case-triad,.incident-kpis{{grid-template-columns:1fr}}.journey{{grid-template-columns:1fr}}.trajectory-head{{display:block}}}}
  </style>
</head>
<body>
  <header class="hero">
    <div class="kicker">DÉMONSTRATION SUPPLY CHAIN — ÉTUDE DE CAS</div>
    <h1>Du risque fournisseur à la décision opérationnelle</h1>
    <p>Identifier les expéditions touchées, suivre leur ascendance dans les lots de fabrication et mesurer séparément la dégradation du service client, puis comparer les solutions selon le délai récupéré, le coût, le stock créé et le retard restant.</p>
    <div class="hero-metrics">
      <div><strong>{len(cascade_ids)}</strong><span>cascades métier</span></div>
      <div><strong>{repeated_seed_count}</strong><span>répétitions appariées par cas</span></div>
      <div><strong>{len(solution_ids)}</strong><span>scénarios d’action comparés</span></div>
      <div><strong>{len(incident_ids)}</strong><span>événements de risque reliés aux expéditions, dont {len(native_incidents)} identifiés sur le mouvement</span></div>
    </div>
  </header>
  <div class="notice"><strong>Lecture correcte :</strong> les résultats proviennent d’un scénario de tension volontairement allégé, préparé pendant 240 jours, et non d’une reproduction du stock historique réel. Toutes les variantes partent néanmoins du même état au jour 0. Les actions marquées « approché » ne reproduisent pas encore toutes les règles d’exécution d’un système industriel. {approximation_phrase} au moins une approximation déclarée.</div>
  <div class="nav-wrap"><nav>{nav}</nav></div>
  <main>
    <section class="tab-panel active" id="overview">
      <div class="section-head"><span class="kicker">LECTURE EN SIX ÉTAPES</span><h2>Une chaîne causale compréhensible par le métier</h2></div>
      <div class="journey">
        <article><b>1</b><h3>Incident</h3><p>Retenue de libération qualité simulée, retard, indisponibilité ou perte de capacité.</p></article>
        <article><b>2</b><h3>Flux touché</h3><p>Expédition et réception réellement exposées.</p></article>
        <article><b>3</b><h3>Stock critique</h3><p>Composant disponible et date de rupture.</p></article>
        <article><b>4</b><h3>Production</h3><p>Campagnes, lots de fabrication, encours et dates de libération perturbés.</p></article>
        <article><b>5</b><h3>Client</h3><p>Lots reçus, quantités servies et jours de retard.</p></article>
        <article><b>6</b><h3>Décision</h3><p>Jours gagnés, coût, stock et retard client restant.</p></article>
      </div>
      <div class="panel-grid">
        <article class="narrative"><h3>État au jour 0 identique</h3><p>{evidence.get("j0_pair_count", 0)} comparaisons de départ contrôlées ; les stocks, encours, commandes, transports et nombres aléatoires sont appariés.</p></article>
        <article class="narrative"><h3>Référence sans incident et sans retard client</h3><p>Les {evidence.get("healthy_normal_run_count", 0)} fonctionnements de référence servent toute la demande client, à partir du même état initial volontairement stressé ; l’amont peut donc rester contraint. La page refuse de se construire si le risque configuré ne produit aucun effet physique. Une simulation sans retard client signifie que les stocks et capacités ont absorbé l’incident, pas que l’incident a été ignoré.</p></article>
        <article class="narrative"><h3>Dispersion visible</h3><p>La part des simulations avec retard client, la moyenne incluant les cas absorbés, l’intervalle central et le pire cas sont calculés sur {repeated_seed_count} répétitions appariées. Les jours récupérés ne sont calculés que lorsqu’un retard client apparaît réellement.</p></article>
      </div>
      <div class="incident-box"><h3>Trajectoires scientifiques complètes incluses</h3><p>Le fichier <code>{html.escape(trajectory_long_pack_path)}</code> contient les {trajectory_long_rows} lignes quotidiennes vérifiées, sans troncature scientifique. Son empreinte SHA-256 est <code>{html.escape(trajectory_long_hash)}</code>.</p></div>
    </section>
    {_cascade_sections(aggregates, cascade_contracts, incident_summaries)}
    <section class="tab-panel" id="solutions">
      <div class="section-head"><span class="kicker">ARBITRAGE MULTICRITÈRE</span><h2>Comparer toutes les solutions</h2></div>
      <p class="definition-note"><strong>Lecture du retard restant :</strong> les deux colonnes de retard décrivent le résultat après application de la solution. La part restante est le rapport entre le retard moyen avec cette action et le retard moyen sans action, calculés sur les dix répétitions, cas absorbés inclus.</p>
      <div class="table-wrap"><table><thead><tr><th>Cascade</th><th>Solution</th><th>Part des simulations avec retard client</th><th>Jours gagnés moyens parmi les cas avec retard client</th><th>Intervalle central 10–90 %</th><th>Cas avec retard le moins favorable</th><th>Retard cumulé restant moyen, zéros inclus</th><th>Pire retard cumulé restant observé</th><th>Jours avec retard évités</th><th>Volume servi plus tôt certains jours</th><th>Solde servi sur toute la période</th><th>Surcoût réseau</th><th>Stock supplémentaire × jours</th><th>Part du retard moyen restante</th><th>Classable parmi les cas avec retard</th><th>Fidélité</th></tr></thead><tbody>{_solution_table(aggregates)}</tbody></table></div>
      <div class="panel-grid">
        <article class="narrative"><h3>Ce que l’on observe</h3><p>Une action rapide peut récupérer davantage de jours tout en coûtant plus cher. Une action moins coûteuse peut laisser davantage de retard client.</p></article>
        <article class="narrative"><h3>Ce que cela signifie</h3><p>Il n’existe pas une solution universelle : l’arbitrage dépend de la marge, de la priorité client, du stock accepté et des actions réellement autorisées.</p></article>
        <article class="narrative"><h3>Décision possible</h3><p>Retenir une solution principale et une solution de secours, puis les recalibrer avec les coûts, capacités et contrats de l’industriel.</p></article>
      </div>
    </section>
    <section class="tab-panel" id="lots-clients">
      <div class="section-head"><span class="kicker">TRAÇABILITÉ</span><h2>Des flux touchés aux lots livrés</h2></div>
      <p>{len(entities)} relations vers des matières, campagnes ou lots, {len(client_service)} relations de lots livrés avec ascendance exposée et {len(costs)} relations de coût sont chargées pour {len(incident_ids)} événements de risque. Cette ascendance ne signifie pas nécessairement un retard client. Les bornes basse et haute évitent de présenter comme certaine une attribution qui dépend d’un mélange de lots ou d’une origine antérieure à la période.</p>
      <div class="incident-box"><h3>Périmètre de la preuve détaillée</h3><p>Les moyennes et dispersions viennent des dix répétitions compactes. Les identifiants de lots et leur généalogie détaillée viennent uniquement des exécutions complètes de la graine {html.escape(registry_seed_text)} ; ils illustrent ces réalisations et ne constituent pas une traçabilité exhaustive des dix répétitions.</p></div>
      <p class="table-note"><strong>Aperçu métier équilibré par étage.</strong> Les réceptions, fabrications, distributions et livraisons restent visibles même lorsque l’allocation FIFO simulée du stock source produit de nombreux fragments. Les CSV inclus conservent toutes les lignes.</p>
      {_table_truncation_notice(entities, limit=120, csv_filename="risk_impact_entities.csv")}
      <div class="table-wrap"><table><thead><tr><th>Simulation source</th><th>Incident</th><th>Type d’entité</th><th>Identifiant</th><th>Article</th><th>Nœud / client</th><th>Jour</th><th>Quantité basse</th><th>Quantité haute</th><th>Unité</th><th>Méthode d’attribution</th><th>Niveau de preuve</th></tr></thead><tbody>{_risk_entity_table(entities)}</tbody></table></div>
      <h3>Lots reçus et volumes livrés avec ascendance exposée</h3>
      {_table_truncation_notice(client_service, limit=120, csv_filename="risk_impact_client_service.csv")}
      <div class="table-wrap"><table><thead><tr><th>Simulation source</th><th>Incident</th><th>Lot reçu</th><th>Jour</th><th>Client</th><th>Article</th><th>Volume livré issu du flux touché, borne basse</th><th>Volume livré issu du flux touché, borne haute</th><th>Unité</th><th>Niveau de preuve</th></tr></thead><tbody>{_risk_client_table(client_service)}</tbody></table></div>
      <h3>Coûts portés par les mouvements exposés</h3>
      <p>Ces montants décrivent les transactions exposées. Ils ne mesurent pas à eux seuls le surcoût causé par l’incident ; ce surcoût vient de la comparaison appariée.</p>
      {_table_truncation_notice(costs, limit=120, csv_filename="risk_impact_costs.csv")}
      <div class="table-wrap"><table><thead><tr><th>Simulation source</th><th>Ensemble exposé</th><th>Expédition</th><th>Transport observé, unités monétaires du modèle</th><th>Achat observé, unités monétaires du modèle</th><th>Statut du coût causal</th><th>Règle d’agrégation</th><th>Note</th></tr></thead><tbody>{_risk_cost_table(costs)}</tbody></table></div>
      <div class="panel-grid">
        <article class="narrative"><h3>Directement tracé à la réception</h3><p>L’identifiant du risque est porté par l’expédition et sa réception fournisseur. Les transformations suivantes sont reliées par la généalogie physique simulée. Le coût causal, lui, vient de la comparaison avec le même cas sans incident.</p></article>
        <article class="narrative"><h3>Propagation après mélange</h3><p>Les liens lot-parent vers lot-enfant simulés sont explicites. Après mélange de composants, l’exposition au risque est propagée par bornes : ce n’est pas une attribution exacte d’une expédition source à une commande client. Chaque lien conserve l’unité de son entrée et de sa sortie ; les kg, g et unités de différents étages ne sont jamais additionnés.</p></article>
        <article class="narrative"><h3>Association temporelle</h3><p>Pour les anciens résultats non enrichis, la proximité de date et de périmètre reste une indication, jamais une causalité affirmée.</p></article>
      </div>
    </section>
    <section class="tab-panel" id="pilotage">
      <div class="section-head"><span class="kicker">EXPLORER LES PREUVES</span><h2>Résultats MRP, pilotage dynamique et réseau</h2></div>
      <p>Ces trois vues sont des analyses historiques complémentaires. Elles ne sont pas les résultats des deux campagnes d’incident présentées dans cette page.</p>
      <div class="asset-grid">{assets}</div>
      <div class="panel-grid">
        <article class="narrative"><h3>Tableau exécutif</h3><p>Comprendre les arbitrages de service, stock, coûts, contraintes et tensions fournisseurs.</p></article>
        <article class="narrative"><h3>Comparaison du réseau</h3><p>Descendre jusqu’au fournisseur, article, usine, client ou liaison et consulter les trajectoires quotidiennes.</p></article>
        <article class="narrative"><h3>Carte détaillée</h3><p>Explorer le réseau et les traces unitaires sans modifier les anciennes cartes.</p></article>
      </div>
    </section>
    <section class="tab-panel" id="limits">
      <div class="section-head"><span class="kicker">TRANSPARENCE</span><h2>Hypothèses, limites et données à calibrer</h2></div>
      <div class="limits">
        <article><h3>Ce que cette page ne prétend pas</h3><ul>
          <li>Les solutions comparées sont des plans d'action fixés avant la simulation ; elles ne constituent pas encore un pilotage adaptatif en boucle fermée.</li>
          <li>L’état initial est un scénario de tension ciblé : après 240 jours de préparation communs, seules les paires nœud–article documentées sont ajustées une fois, juste avant le jour 0. Cette hypothèse est identique dans les trois cas comparés, mais ce n’est pas encore un stock J0 calibré chez l’industriel.</li>
          <li>Les autres risques fournisseurs dépendants de l'état sont neutralisés dans cette campagne afin d'isoler l'incident étudié. Les stocks, flux, commandes, transports, encours et fabrications restent dynamiques.</li>
          <li>La retenue de libération qualité simulée porte sur les nouvelles expéditions identifiées pendant la fenêtre d'incident ; le stock déjà présent n'est pas requalifié rétroactivement.</li>
          <li>Cette retenue est modélisée par un délai avant disponibilité. Ce n'est pas encore une gestion qualité locale avec statuts « en attente », « libéré » ou « rejeté », ni une simulation d'inspection, de rebut, de reprise ou de rappel.</li>
          <li><code>tau_process</code> reste une couverture de planification ; ce n’est pas un délai physique de maturation après fabrication.</li>
          <li>Les risques simulés ne sont pas des probabilités d’incident observées.</li>
          <li>Les coûts ne sont pas des euros validés tant que l’industriel ne fournit pas ses barèmes.</li>
          <li>Le coût complet additionne le coût opérationnel de base, les achats et transports d’ouverture comptés une seule fois, puis les achats et transports externes.</li>
          <li>Une action approchée n’est pas une exécution industrielle garantie.</li>
          <li>Les « équivalents de lots » sont une quantité de production divisée par la taille de lot de référence ; ils ne remplacent pas les identifiants des lots réels.</li>
          <li>Les « unités servies plus tôt » additionnent les gains journaliers positifs par rapport au cas sans action ; ce ne sont pas des commandes individuelles identifiées.</li>
          <li>Le « retard client restant » est le retard cumulé après action divisé par celui du cas sans action. Ce n'est ni une probabilité d'incident ni une note fournisseur.</li>
          <li>La stabilité globale de toute la supply chain n’est pas démontrée.</li>
        </ul></article>
        <article><h3>Données nécessaires pour industrialiser</h3><ul>
          <li>Règles de lot de fabrication, fractionnement, encours et libération qualité.</li>
          <li>Ordres d’achat et de fabrication, généalogie MES/WMS et statuts qualité.</li>
          <li>Fournisseurs alternatifs, contrats, capacités et délais d’urgence.</li>
          <li>Coûts de stock, transport accéléré, achat exceptionnel et pénalités client.</li>
          <li>Priorités clients, substitutions et actions réellement autorisées.</li>
        </ul></article>
      </div>
    </section>
  </main>
  <footer>Fichier autonome et utilisable hors ligne. Les sources historiques n’ont pas été modifiées ; leurs copies locales embarquent seulement les dépendances nécessaires à l’ouverture sans Internet.</footer>
  <script id="demo-data" type="application/json">{embedded}</script>
  <script id="trajectory-data" type="application/json">{embedded_trajectories}</script>
  <script>
    (() => {{
      const demoData = JSON.parse(document.getElementById('demo-data').textContent);
      const trajectoryData = JSON.parse(document.getElementById('trajectory-data').textContent);
      const buttons = [...document.querySelectorAll('.tab-button')];
      const panels = [...document.querySelectorAll('.tab-panel')];
      function show(id) {{
        buttons.forEach(button => button.classList.toggle('active', button.dataset.tab === id));
        panels.forEach(panel => panel.classList.toggle('active', panel.id === id));
        history.replaceState(null, '', '#' + id);
        window.scrollTo({{top: document.querySelector('.nav-wrap').offsetTop, behavior: 'smooth'}});
      }}
      buttons.forEach(button => button.addEventListener('click', () => show(button.dataset.tab)));
      const requested = location.hash.slice(1);
      if (requested && panels.some(panel => panel.id === requested)) show(requested);

      const chartSpecs = {{
        quality: [
          ['Réceptions de 021081 à SDC-1450', 'input_replenishment_arrival_qty', 'SDC-1450', 'item:021081'],
          ['Stock disponible de 021081 à SDC-1450', 'input_stock_end_qty', 'SDC-1450', 'item:021081'],
          ['Encours de 773474 à SDC-1450', 'production_wip_end_qty', 'SDC-1450', 'item:773474'],
          ['Production libérée de 268967 à M-1430', 'production_released_qty', 'M-1430', 'item:268967'],
          ['Retard client sur 268967', 'customer_backlog_end_qty', 'C-XXXXX', 'item:268967']
        ],
        delay: [
          ['Départs de 338929 vers M-1810', 'transport_shipment_qty', 'SDC-VD0914360C', 'item:338929'],
          ['Arrivées de 338929 à M-1810', 'transport_arrival_qty', 'M-1810', 'item:338929'],
          ['Stock disponible de 338929 à M-1810', 'input_stock_end_qty', 'M-1810', 'item:338929'],
          ['Encours de 268091 à M-1810', 'production_wip_end_qty', 'M-1810', 'item:268091'],
          ['Production libérée de 268091 à M-1810', 'production_released_qty', 'M-1810', 'item:268091'],
          ['Retard client sur 268091', 'customer_backlog_end_qty', 'C-XXXXX', 'item:268091']
        ]
      }};

      const esc = value => String(value).replace(/[&<>"']/g, character => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }})[character]);
      function variant(cascade, role) {{
        return Object.values(cascade.variants).find(value => value.variant_role === role);
      }}
      function series(value, spec) {{
        return value && value.series.find(item =>
          item.metric === spec[1] && item.node_id === spec[2] && item.item_id === spec[3]
        );
      }}
      function points(values, sx, sy) {{
        return values.map((value, index) => `${{sx(index).toFixed(1)}},${{sy(value).toFixed(1)}}`).join(' ');
      }}
      function band(item, sx, sy) {{
        return points(item.min, sx, sy) + ' ' + points([...item.max].reverse(), index => sx(item.max.length - 1 - index), sy);
      }}
      function formatValue(value) {{
        if (!Number.isFinite(value)) return 'n.d.';
        if (Math.abs(value) >= 1e6) return (value / 1e6).toFixed(1).replace('.', ',') + ' M';
        return Math.round(value).toLocaleString('fr-FR');
      }}
      function drawChart(cascadeId, solutionId, spec) {{
        const cascade = trajectoryData.cascades[cascadeId];
        const normal = series(variant(cascade, 'normal'), spec);
        const incident = series(variant(cascade, 'no_action'), spec);
        const action = series(variant(cascade, 'solution:' + solutionId), spec);
        if (!normal || !incident || !action) return '';
        const all = [normal, incident, action].flatMap(item => [...item.min, ...item.max]);
        let min = Math.min(...all), max = Math.max(...all);
        if (Math.abs(max - min) < 1e-9) {{ min -= 1; max += 1; }}
        const width = 720, height = 270, left = 65, right = 18, top = 20, bottom = 40;
        const n = trajectoryData.day_axis.length;
        const sx = index => left + index / Math.max(1, n - 1) * (width - left - right);
        const sy = value => top + (max - value) / (max - min) * (height - top - bottom);
        const contract = demoData.cascade_contracts[cascadeId];
        const windowStart = contract.incident_start_day, windowEnd = contract.incident_end_day;
        const windowX = sx(windowStart), windowWidth = Math.max(2, sx(windowEnd) - windowX);
        return `<article class="chart-card"><h4>${{esc(spec[0])}}</h4><p>${{esc(normal.uom)}} — moyenne et étendue minimum–maximum</p>
          <svg class="daily-chart" viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="${{esc(spec[0])}}">
            <rect x="${{windowX.toFixed(1)}}" y="${{top}}" width="${{windowWidth.toFixed(1)}}" height="${{height-top-bottom}}" class="incident-window"/>
            <line x1="${{left}}" y1="${{top}}" x2="${{left}}" y2="${{height-bottom}}" class="chart-axis"/><line x1="${{left}}" y1="${{height-bottom}}" x2="${{width-right}}" y2="${{height-bottom}}" class="chart-axis"/>
            <line x1="${{left}}" y1="${{sy(max).toFixed(1)}}" x2="${{width-right}}" y2="${{sy(max).toFixed(1)}}" class="chart-grid"/><line x1="${{left}}" y1="${{sy(min).toFixed(1)}}" x2="${{width-right}}" y2="${{sy(min).toFixed(1)}}" class="chart-grid"/>
            <polygon points="${{band(normal,sx,sy)}}" class="band-normal"/><polygon points="${{band(incident,sx,sy)}}" class="band-incident"/><polygon points="${{band(action,sx,sy)}}" class="band-solution"/>
            <polyline points="${{points(normal.mean,sx,sy)}}" class="line-normal"/><polyline points="${{points(incident.mean,sx,sy)}}" class="line-incident"/><polyline points="${{points(action.mean,sx,sy)}}" class="line-solution"/>
            <text x="8" y="${{top+5}}">${{esc(formatValue(max))}}</text><text x="8" y="${{height-bottom}}">${{esc(formatValue(min))}}</text><text x="${{left}}" y="${{height-12}}">J0</text><text x="${{width-right-50}}" y="${{height-12}}">J${{n-1}}</text>
          </svg><div class="chart-legend"><span><i class="legend-line" style="background:#6b7785"></i>Référence</span><span><i class="legend-line" style="background:#d92d20"></i>Incident sans action</span><span><i class="legend-line" style="background:#179b67"></i>Avec action</span><span>zone rose : incident</span></div></article>`;
      }}
      function renderCascade(cascadeId, solutionId) {{
        const target = document.querySelector(`[data-cascade-charts="${{cascadeId}}"]`);
        const quality = cascadeId.includes('021081') || cascadeId.includes('quality');
        target.innerHTML = chartSpecs[quality ? 'quality' : 'delay']
          .map(spec => drawChart(cascadeId, solutionId, spec)).filter(Boolean).join('');
        if (!target.innerHTML) target.innerHTML = '<p class="empty">Aucune série compatible disponible.</p>';
      }}
      document.querySelectorAll('.trajectory-solution').forEach(select => {{
        renderCascade(select.dataset.cascade, select.value);
        select.addEventListener('change', () => renderCascade(select.dataset.cascade, select.value));
      }});
    }})();
  </script>
</body>
</html>
"""


def build_industrial_demo_pack(
    *,
    cascade_dir: Path,
    trajectory_dir: Path,
    risk_registry_dirs: Sequence[Path],
    output_dir: Path,
    industrial_dashboard: Path,
    node_dashboard: Path,
    network_map: Path,
    plotly_js: Path,
    plotly_topojson: Path,
    minimum_seed_count: int = 10,
) -> IndustrialDemoArtifacts:
    cascade = cascade_dir.resolve()
    runs_path = cascade / "canonical_cascade_runs.csv"
    comparisons_path = cascade / "canonical_cascade_comparison.csv"
    summary_path = cascade / "canonical_cascade_summary.json"

    runs = _read_csv(runs_path)
    comparisons = _read_csv(comparisons_path)
    _require_columns(runs, CASCADE_RUN_FIELDS, runs_path)
    _require_columns(comparisons, CASCADE_COMPARISON_FIELDS, comparisons_path)
    if len({row.get("cascade_id") for row in runs}) < 2:
        raise ValueError(
            "La demonstration industrielle exige au moins deux cascades metier"
        )
    if not summary_path.is_file():
        raise FileNotFoundError(summary_path)
    summary = _read_json(summary_path)
    campaign_source, config_snapshot_path, upstream_integrity = (
        _validate_cascade_and_campaign_integrity(
            cascade_dir=cascade,
            runs_path=runs_path,
            comparisons_path=comparisons_path,
            runs=runs,
            comparisons=comparisons,
            summary=summary,
        )
    )
    config_snapshot = _read_json(config_snapshot_path)
    scientific_guards = config_snapshot.get("scientific_guards", {})
    if not isinstance(scientific_guards, dict):
        raise ValueError("scientific_guards invalide dans le snapshot de campagne")
    require_positive_customer_exposure = scientific_guards.get(
        "require_positive_incremental_customer_backlog", True
    )
    if not isinstance(require_positive_customer_exposure, bool):
        raise ValueError(
            "scientific_guards.require_positive_incremental_customer_backlog "
            "doit être booléen"
        )
    cascade_contracts = _cascade_contracts(config_snapshot)
    expected_solution_ids = {
        cascade_id: {
            str(solution["id"])
            for solution in contract["solutions"]
            if isinstance(solution, dict)
        }
        for cascade_id, contract in cascade_contracts.items()
    }
    evidence = _validate_campaign_evidence(
        runs,
        comparisons,
        minimum_seed_count=minimum_seed_count,
        expected_solution_ids=expected_solution_ids,
        require_positive_customer_exposure=require_positive_customer_exposure,
    )
    evidence["upstream_integrity"] = upstream_integrity
    (
        trajectory_payload,
        trajectory_path,
        trajectory_manifest_path,
        trajectory_manifest,
    ) = _load_trajectory_payload(trajectory_dir)
    evidence["upstream_integrity"].update(
        _validate_trajectory_integrity(
            trajectory_dir=trajectory_dir,
            payload=trajectory_payload,
            compact_path=trajectory_path,
            manifest=trajectory_manifest,
            config_snapshot_path=config_snapshot_path,
            campaign_runs_path=campaign_source / "canonical_cascade_runs.csv",
            expected_run_count=len(runs),
            expected_cascade_ids=set(cascade_contracts),
        )
    )
    _validate_trajectory_contract(
        trajectory_payload,
        cascade_contracts=cascade_contracts,
        expected_solution_ids=expected_solution_ids,
        expected_seed_counts={
            cascade_id: int(count)
            for cascade_id, count in evidence["seed_count_by_cascade"].items()
        },
    )
    incidents, entities, client_service, costs, quality, registries = _risk_rows(
        risk_registry_dirs
    )
    registry_cascade_map, registry_provenance_proofs = _validate_risk_registry_contract(
        registries,
        cascade_contracts=cascade_contracts,
        final_campaign_source=campaign_source,
        final_runs=runs,
    )
    evidence["risk_registry_provenance"] = registry_provenance_proofs
    aggregates = _aggregate_comparisons(comparisons)
    validated_plotly = _validate_plotly_distribution(plotly_js)
    validated_topojson = _validate_world_topojson(plotly_topojson)
    output = _prepare_output(output_dir)
    assets_dir = output / "assets"
    data_dir = output / "data"
    assets_dir.mkdir()
    data_dir.mkdir()

    copied_industrial_dashboard = _asset_copy(
        industrial_dashboard, assets_dir, "resultats_mrp_v3.html"
    )
    copied_node_dashboard = _asset_copy(
        node_dashboard, assets_dir, "comparaison_reseau.html"
    )
    copied_plotly = _asset_copy(validated_plotly, assets_dir, "plotly-2.32.0.min.js")
    copied_topojson = _asset_copy(
        validated_topojson,
        assets_dir,
        WORLD_TOPOJSON_NAME,
    )
    copied_network_map = _offline_network_map_copy(
        network_map,
        assets_dir,
        "carte_reseau.html",
        topojson=validated_topojson,
    )
    _assert_offline_html(copied_industrial_dashboard)
    _assert_offline_html(copied_node_dashboard)
    copied_assets = (
        copied_industrial_dashboard,
        copied_node_dashboard,
        copied_network_map,
        copied_plotly,
        copied_topojson,
    )
    shutil.copy2(runs_path, data_dir / runs_path.name)
    shutil.copy2(comparisons_path, data_dir / comparisons_path.name)
    shutil.copy2(summary_path, data_dir / summary_path.name)
    shutil.copy2(config_snapshot_path, data_dir / config_snapshot_path.name)
    shutil.copy2(trajectory_path, data_dir / trajectory_path.name)
    shutil.copy2(trajectory_manifest_path, data_dir / trajectory_manifest_path.name)
    trajectory_long_source = Path(
        str(evidence["upstream_integrity"]["trajectory_long_csv_source"])
    )
    trajectory_long_copy = data_dir / TRAJECTORY_LONG_NAME
    shutil.copy2(trajectory_long_source, trajectory_long_copy)
    copied_long_hash = _sha256(trajectory_long_copy)
    copied_long_rows = _csv_row_count(trajectory_long_copy)
    if (
        copied_long_hash != evidence["upstream_integrity"]["trajectory_long_csv_sha256"]
        or copied_long_rows
        != evidence["upstream_integrity"]["trajectory_long_csv_row_count"]
    ):
        raise ValueError("La copie complete des trajectoires longues est incoherente")
    evidence["upstream_integrity"].update(
        {
            "trajectory_long_csv_copied": True,
            "trajectory_long_csv_pack_path": f"data/{TRAJECTORY_LONG_NAME}",
            "trajectory_long_csv_copy_sha256": copied_long_hash,
            "trajectory_long_csv_copy_row_count": copied_long_rows,
            "trajectory_long_csv_scientific_truncation": False,
        }
    )
    for index, registry_dir in enumerate(risk_registry_dirs, start=1):
        target = data_dir / f"risk_registry_{index:02d}"
        target.mkdir()
        for filename in (
            *RISK_REGISTRY_CSV_FILENAMES.values(),
            "risk_impact_quality.json",
        ):
            source = registry_dir.resolve() / filename
            shutil.copy2(source, target / filename)

    document = _render_document(
        runs=runs,
        comparisons=comparisons,
        aggregates=aggregates,
        incidents=incidents,
        entities=entities,
        client_service=client_service,
        costs=costs,
        quality=quality,
        trajectory_payload=trajectory_payload,
        evidence=evidence,
        config_snapshot=config_snapshot,
        asset_links={
            "Analyse historique complémentaire MRP / pilotage V3": "assets/resultats_mrp_v3.html",
            "Comparaison historique complémentaire du réseau": "assets/comparaison_reseau.html",
            "Carte historique détaillée — contenu métier préservé, dépendances embarquées": "assets/carte_reseau.html",
        },
    )
    index_path = output / "index.html"
    index_path.write_text(document, encoding="utf-8")
    _assert_offline_html(index_path)
    manifest = {
        "schema_version": DEMO_SCHEMA_VERSION,
        "status": "complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "cascade_dir": str(cascade),
            "trajectory_dir": str(trajectory_dir.resolve()),
            "campaign_source_dir": str(campaign_source),
            "config_snapshot": str(config_snapshot_path),
            "risk_registry_dirs": [str(path.resolve()) for path in risk_registry_dirs],
            "industrial_dashboard": str(industrial_dashboard.resolve()),
            "node_dashboard": str(node_dashboard.resolve()),
            "network_map": str(network_map.resolve()),
            "plotly_js": str(plotly_js.resolve()),
            "plotly_topojson": str(plotly_topojson.resolve()),
        },
        "counts": {
            "cascade_runs": len(runs),
            "comparison_rows": len(comparisons),
            "solution_aggregates": len(aggregates),
            "risk_incidents": len(incidents),
            "risk_entities": len(entities),
            "risk_client_service": len(client_service),
            "risk_cost_relations": len(costs),
            "minimum_paired_seed_count": evidence["minimum_seed_count"],
            "trajectory_long_rows": copied_long_rows,
        },
        "cascade_summary": summary,
        "scientific_evidence": evidence,
        "risk_registry_cascade_map": registry_cascade_map,
        "risk_registry_provenance": registry_provenance_proofs,
        "offline_dependencies": {
            "plotly_version": PLOTLY_VERSION,
            "plotly_sha256": PLOTLY_SHA256,
            "world_topojson_name": WORLD_TOPOJSON_NAME,
            "world_topojson_sha256": WORLD_TOPOJSON_SHA256,
            "file_protocol_topology_fallback_embedded": True,
        },
        "artifacts": {
            "index": str(index_path),
            "assets": [str(path) for path in copied_assets],
            "trajectory_long_csv": {
                "path": f"data/{TRAJECTORY_LONG_NAME}",
                "sha256": copied_long_hash,
                "row_count": copied_long_rows,
                "complete_without_scientific_truncation": True,
            },
        },
        "no_overwrite": True,
        "offline": True,
    }
    manifest_path = output / "demo_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return IndustrialDemoArtifacts(
        output_dir=output,
        index_path=index_path,
        manifest_path=manifest_path,
        copied_assets=copied_assets,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construit la page industrielle autonome des cascades supply chain."
    )
    parser.add_argument("--cascade-dir", required=True)
    parser.add_argument("--trajectory-dir", required=True)
    parser.add_argument("--risk-registry-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--industrial-dashboard", required=True)
    parser.add_argument("--node-dashboard", required=True)
    parser.add_argument("--network-map", required=True)
    parser.add_argument("--plotly-js", required=True)
    parser.add_argument("--plotly-topojson", required=True)
    parser.add_argument("--minimum-seed-count", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = build_industrial_demo_pack(
        cascade_dir=Path(args.cascade_dir),
        trajectory_dir=Path(args.trajectory_dir),
        risk_registry_dirs=[Path(path) for path in args.risk_registry_dir],
        output_dir=Path(args.output_dir),
        industrial_dashboard=Path(args.industrial_dashboard),
        node_dashboard=Path(args.node_dashboard),
        network_map=Path(args.network_map),
        plotly_js=Path(args.plotly_js),
        plotly_topojson=Path(args.plotly_topojson),
        minimum_seed_count=args.minimum_seed_count,
    )
    print(f"Paquet de demonstration cree: {artifacts.output_dir}")
    print(f"Page principale: {artifacts.index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
