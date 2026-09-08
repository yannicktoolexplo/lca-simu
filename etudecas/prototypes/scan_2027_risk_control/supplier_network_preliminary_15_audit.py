#!/usr/bin/env python3
"""Build a strictly preliminary, read-only view of checkpoint 15/30.

The module never writes inside the runner, plan, boundary, or source campaign.
It validates the exact signed checkpoint through the runner contract, recomputes
paired effects from the 634 hashed evidence records, and emits a small external
package whose scientific release and action flags are all fail-closed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import shutil
import statistics
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from . import supplier_network_post_priority_extension_runner as runner
    from . import supplier_network_post_priority_extensions as planner
    from . import supplier_network_priority_boundary_audit as boundary_audit
except ImportError:  # pragma: no cover - direct CLI execution
    import supplier_network_post_priority_extension_runner as runner
    import supplier_network_post_priority_extensions as planner
    import supplier_network_priority_boundary_audit as boundary_audit


SCHEMA_VERSION = "etudecas.supplier_network_preliminary_15_of_30_audit.v1"
PACKAGE_SCHEMA_VERSION = (
    "etudecas.supplier_network_preliminary_15_of_30_audit_package.v1"
)
EXPECTED_RUNNER_SHA256 = (
    "3E404A3B92D2A8096A10EC1600110689210B112928C385EA1DB3564618FF9DF5"
)
EXPECTED_PLANNER_SHA256 = (
    "E22D7B923FE4421AAD590458DC9BC9293B77FF5393BD29258D22F23C5F1344C9"
)
EXPECTED_BOUNDARY_BUILDER_SHA256 = (
    "066E6A9046C17325B068641D9803D3857618168CBAA3439732972A41B1BB7F15"
)
EXPECTED_SEED_COUNT = 15
EXPECTED_EVIDENCE_COUNT = 634
EXPECTED_ENGINE_COUNT = 510
EXPECTED_SERVICE_GROUP_COUNT = 4

AUDIT_FILE = "preliminary_15_of_30_audit.json"
EFFECTS_FILE = "preliminary_effects_15.csv"
ACTIVE_EXPOSURE_FILE = "preliminary_active_exposure_15.csv"
LOT_SUMMARY_FILE = "preliminary_lot_illustrations.csv"
LOT_DETAIL_FILE = "preliminary_lot_genealogical_exposure_detail.csv"
BOUNDARY_FILE = "boundary_group4_confirmed.csv"
HTML_FILE = "PRELIMINAIRE_15_SUR_30.html"
OUTPUT_FILES = (
    AUDIT_FILE,
    EFFECTS_FILE,
    ACTIVE_EXPOSURE_FILE,
    LOT_SUMMARY_FILE,
    LOT_DETAIL_FILE,
    BOUNDARY_FILE,
    HTML_FILE,
)
MANIFEST_FILE = "preliminary_15_of_30_manifest.json"
SOURCE_HASH_KEYS = frozenset(
    {
        "runner/post_priority_extension_runner_manifest.json",
        "runner/execution_ledger.json",
        f"runner/{runner.PRELIMINARY_CHECKPOINT_MANIFEST}",
        "plan/post_priority_extensions_plan_manifest.json",
        "boundary/priority_boundary_audit_manifest.json",
        "boundary/scientific_priority_boundary_audit.json",
        "boundary/supplier_metric_rankings.csv",
        "runner/case_evidence_registry_canonical",
        "runner/causal_source_material_hashes_canonical",
    }
)

BOUNDARY_METRIC_KEYS = (
    "horizon_on_due_service_delta",
    "worst_rolling_28d_on_due_delta",
    "incremental_backlog_days_per_requested_unit",
    "released_production_shortfall_ratio",
)

EXTENSION_LABELS = {
    "multi_lane_supplier_common_cause": (
        "Incident simultané sur plusieurs voies du même fournisseur"
    ),
    "temporal_robustness": "Période de survenue de l’incident",
    "priority_four_business_causes": "Type d’incident métier",
    "causal_lot_attribution_subset": "Illustration technique du suivi de lots",
}
FAILURE_MODE_LABELS = {
    "transport_delay": "Retard de transport ou d’expédition",
    "supply_availability": "Part de l’approvisionnement disponible",
    "quality_hold": "Attente avant libération qualité",
    "quality_yield": "Part de la quantité utilisable après contrôle",
}
LOT_ROLE_LABELS = {
    "risk_tagged_usable_receipt_root": "Réception fournisseur à l’origine du suivi",
    "genealogical_descendant": "Lot situé en aval par filiation simulée",
}


class PreliminaryAuditError(RuntimeError):
    """Raised when preliminary evidence is incomplete or inconsistent."""


@dataclass(frozen=True)
class PreliminarySource:
    runner_dir: Path
    plan_dir: Path
    boundary_dir: Path
    runner_manifest: dict[str, Any]
    plan_manifest: dict[str, Any]
    checkpoint: dict[str, Any]
    lineage: dict[str, Any]
    completed_seed_ids: tuple[int, ...]
    product_rows: tuple[dict[str, Any], ...]
    flow_rows: tuple[dict[str, Any], ...]
    lot_rows: tuple[dict[str, Any], ...]
    lot_detail_rows: tuple[dict[str, Any], ...]
    boundary_rows: tuple[dict[str, Any], ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise PreliminaryAuditError(f"Objet JSON attendu: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise PreliminaryAuditError(f"Aucune ligne à écrire: {path.name}")
    fields = list(rows[0])
    if any(list(row) != fields for row in rows):
        raise PreliminaryAuditError(f"Colonnes CSV incohérentes: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _assert_external_destination(destination: Path, protected: Iterable[Path]) -> None:
    resolved = destination.resolve()
    for source in protected:
        source_resolved = source.resolve()
        if resolved == source_resolved or _is_relative_to(resolved, source_resolved):
            raise PreliminaryAuditError(
                "Le paquet préliminaire doit être écrit dans un dossier externe."
            )


def _finite(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise PreliminaryAuditError(f"Valeur numérique invalide: {label}") from error
    if not math.isfinite(result):
        raise PreliminaryAuditError(f"Valeur non finie: {label}")
    return result


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise PreliminaryAuditError("Agrégat préliminaire vide.")
    return statistics.fmean(values)


def _sample_sd(values: Sequence[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _text_preserving_zero(value: Any) -> str:
    return "" if value is None else str(value)


def _source_hashes(
    runner_dir: Path,
    plan_dir: Path,
    boundary_dir: Path,
    checkpoint: Mapping[str, Any],
    runner_manifest: Mapping[str, Any],
) -> dict[str, str]:
    registry = checkpoint.get("case_evidence_file_sha256")
    if not isinstance(registry, Mapping):
        raise PreliminaryAuditError("Registre des 634 preuves absent.")
    causal_source_hashes = runner_manifest.get("causal_source_material_hashes")
    if not isinstance(causal_source_hashes, Mapping) or not causal_source_hashes:
        raise PreliminaryAuditError("Empreintes des preuves lots source absentes.")
    return {
        "runner/post_priority_extension_runner_manifest.json": _sha256(
            runner_dir / runner.RUNNER_MANIFEST
        ),
        "runner/execution_ledger.json": _sha256(runner_dir / runner.LEDGER_FILE),
        f"runner/{runner.PRELIMINARY_CHECKPOINT_MANIFEST}": _sha256(
            runner_dir / runner.PRELIMINARY_CHECKPOINT_MANIFEST
        ),
        "plan/post_priority_extensions_plan_manifest.json": _sha256(
            plan_dir / "post_priority_extensions_plan_manifest.json"
        ),
        "boundary/priority_boundary_audit_manifest.json": _sha256(
            boundary_dir / "priority_boundary_audit_manifest.json"
        ),
        "boundary/scientific_priority_boundary_audit.json": _sha256(
            boundary_dir / "scientific_priority_boundary_audit.json"
        ),
        "boundary/supplier_metric_rankings.csv": _sha256(
            boundary_dir / "supplier_metric_rankings.csv"
        ),
        "runner/case_evidence_registry_canonical": _canonical_sha256(registry),
        "runner/causal_source_material_hashes_canonical": _canonical_sha256(
            causal_source_hashes
        ),
    }


def _validate_boundary(
    boundary_dir: Path,
    lineage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if _sha256(Path(boundary_audit.__file__).resolve()).upper() != (
        EXPECTED_BOUNDARY_BUILDER_SHA256
    ):
        raise PreliminaryAuditError("Version du constructeur boundary inattendue.")
    try:
        boundary_audit.validate_audit_package(boundary_dir)
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        raise PreliminaryAuditError(f"Paquet boundary invalide: {error}") from error
    expected = set(boundary_audit.OUTPUT_FILES) | {
        "priority_boundary_audit_manifest.json"
    }
    observed = {path.name for path in boundary_dir.iterdir() if path.is_file()}
    if observed != expected or any(path.is_dir() for path in boundary_dir.iterdir()):
        raise PreliminaryAuditError("Inventaire boundary non exact.")
    manifest_path = boundary_dir / "priority_boundary_audit_manifest.json"
    result_path = boundary_dir / "scientific_priority_boundary_audit.json"
    ranking_path = boundary_dir / "supplier_metric_rankings.csv"
    manifest = _read_json(manifest_path)
    result = _read_json(result_path)
    service_group = result.get(
        "envelope_service_nonseparation_group_supplier_ids"
    )
    if (
        manifest.get("status") != "complete"
        or str(manifest.get("builder_sha256") or "").upper()
        != EXPECTED_BOUNDARY_BUILDER_SHA256
        or result.get("scoped_descriptive_priority_set_display_allowed") is not False
        or result.get("confirmatory_priority_set_release_allowed") is not False
        or result.get("global_priority_release_allowed") is not False
        or result.get("action_promotion_allowed") is not False
        or not isinstance(service_group, list)
        or len(service_group) != EXPECTED_SERVICE_GROUP_COUNT
        or service_group != sorted(set(service_group))
        or service_group != lineage.get("follow_up_supplier_ids")
        or service_group != lineage.get("service_nonseparation_group_supplier_ids")
        or lineage.get("follow_up_group_is_unordered") is not True
    ):
        raise PreliminaryAuditError("Groupe service boundary/plan incohérent.")
    lineage_hashes = {
        "priority_boundary_package_signature": str(
            manifest.get("package_signature") or ""
        ),
        "priority_boundary_manifest_sha256": _sha256(manifest_path),
        "priority_boundary_result_sha256": _sha256(result_path),
        "priority_boundary_ranking_sha256": _sha256(ranking_path),
        "priority_boundary_builder_sha256": EXPECTED_BOUNDARY_BUILDER_SHA256.lower(),
    }
    if any(
        str(lineage.get(key) or "").lower() != expected.lower()
        for key, expected in lineage_hashes.items()
    ):
        raise PreliminaryAuditError("Lignée plan/boundary vivante incohérente.")
    ranking_rows = _read_csv(ranking_path)
    selected = [
        row
        for row in ranking_rows
        if row.get("aggregation_scope") == boundary_audit.SUPPLIER_ENVELOPE_SCOPE
        and row.get("supplier_id") in service_group
        and row.get("metric_key") in BOUNDARY_METRIC_KEYS
    ]
    if len(selected) != EXPECTED_SERVICE_GROUP_COUNT * len(BOUNDARY_METRIC_KEYS):
        raise PreliminaryAuditError("Matrice des résultats boundary groupe4 incomplète.")
    if {
        (row["supplier_id"], row["metric_key"]) for row in selected
    } != {
        (supplier, metric)
        for supplier in service_group
        for metric in BOUNDARY_METRIC_KEYS
    }:
        raise PreliminaryAuditError("Doublon ou absence dans le tableau boundary groupe4.")
    return result, selected


def _load_checkpoint_evidence(
    *,
    runner_dir: Path,
    checkpoint: Mapping[str, Any],
) -> dict[str, runner.CaseEvidence]:
    registry = checkpoint.get("case_evidence_file_sha256")
    if not isinstance(registry, Mapping) or len(registry) != EXPECTED_EVIDENCE_COUNT:
        raise PreliminaryAuditError("Registre préliminaire incomplet.")
    evidence: dict[str, runner.CaseEvidence] = {}
    for case_key, reference in registry.items():
        if not isinstance(reference, Mapping):
            raise PreliminaryAuditError(f"Référence invalide: {case_key}")
        path = runner._validated_ledger_evidence_path(
            output_dir=runner_dir,
            case_key=str(case_key),
            relative_value=reference.get("relative_path"),
        )
        if _sha256(path) != str(reference.get("sha256") or ""):
            raise PreliminaryAuditError(f"Preuve altérée: {case_key}")
        payload = _read_json(path)
        if payload.get("case_key") != case_key:
            raise PreliminaryAuditError(f"Identité de preuve incohérente: {case_key}")
        evidence[str(case_key)] = runner._evidence_from_dict(payload)
    return evidence


def load_preliminary_source(
    *,
    runner_dir: Path,
    plan_dir: Path,
    boundary_dir: Path,
) -> PreliminarySource:
    """Validate and recompute the exact checkpoint without mutating it."""

    runner_dir = runner_dir.resolve()
    plan_dir = plan_dir.resolve()
    boundary_dir = boundary_dir.resolve()
    if _sha256(Path(runner.__file__).resolve()).upper() != EXPECTED_RUNNER_SHA256:
        raise PreliminaryAuditError("Version du runner inattendue.")
    if _sha256(Path(planner.__file__).resolve()).upper() != EXPECTED_PLANNER_SHA256:
        raise PreliminaryAuditError("Version du planificateur inattendue.")
    plan_manifest, baselines, stress_cases = runner.load_signed_plan(
        plan_dir,
        require_boundary_lineage=True,
    )
    plan_manifest_path = plan_dir / "post_priority_extensions_plan_manifest.json"
    plan_manifest_sha256 = _sha256(plan_manifest_path)
    runner_manifest = _read_json(runner_dir / runner.RUNNER_MANIFEST)
    status = str(runner_manifest.get("status") or "")
    if status not in {"paused_preliminary", "complete"}:
        raise PreliminaryAuditError(
            "Le runner doit être arrêté au jalon 15/30 ou terminé."
        )
    if (
        str(runner_manifest.get("runner_script_sha256") or "").upper()
        != EXPECTED_RUNNER_SHA256
        or str(runner_manifest.get("planner_script_sha256") or "").upper()
        != EXPECTED_PLANNER_SHA256
        or str(runner_manifest.get("plan_manifest_sha256") or "")
        != plan_manifest_sha256
    ):
        raise PreliminaryAuditError("Lignée runner/plan incompatible.")
    declared_causal_source_hashes = runner_manifest.get(
        "causal_source_material_hashes"
    )
    if (
        not isinstance(declared_causal_source_hashes, Mapping)
        or not declared_causal_source_hashes
        or runner._causal_source_material_hashes(plan_dir)
        != dict(declared_causal_source_hashes)
    ):
        raise PreliminaryAuditError(
            "Les preuves lots source ne correspondent plus aux empreintes du runner."
        )
    lineage = plan_manifest.get("priority_selection_lineage")
    if not isinstance(lineage, dict):
        raise PreliminaryAuditError("Lignée de sélection absente du plan.")
    lineage_digest = str(plan_manifest.get("priority_selection_lineage_sha256") or "")
    if (
        lineage.get("priority_selection_lineage_sha256") != lineage_digest
        or runner_manifest.get("priority_selection_lineage_sha256") != lineage_digest
    ):
        raise PreliminaryAuditError("Empreinte de lignée non propagée.")
    _validate_boundary(boundary_dir, lineage)

    selected_baselines, selected_stress = runner._selected_cases(
        "full", baselines, stress_cases
    )
    signed_seed_ids = runner._signed_full_seed_ids(
        plan_manifest=plan_manifest,
        stress_cases=selected_stress,
    )
    completed_seed_ids = tuple(signed_seed_ids[:EXPECTED_SEED_COUNT])
    seed_set = set(completed_seed_ids)
    prefix_baselines = [case for case in selected_baselines if case.seed in seed_set]
    prefix_stress = [case for case in selected_stress if case.seed in seed_set]
    owners, owner_by_logical = runner._baseline_materialization_plan(
        selected_baselines
    )
    prefix_owner_keys = {owner_by_logical[case.case_key] for case in prefix_baselines}
    prefix_owners = [case for case in owners if case.case_key in prefix_owner_keys]
    expected_keys = {case.case_key for case in [*prefix_owners, *prefix_stress]}
    if len(expected_keys) != EXPECTED_EVIDENCE_COUNT:
        raise PreliminaryAuditError("Univers attendu du jalon différent de 634 preuves.")
    try:
        checkpoint = runner._validate_preliminary_checkpoint(
            output_dir=runner_dir,
            runner_signature=str(runner_manifest.get("runner_signature") or ""),
            plan_manifest_sha256=plan_manifest_sha256,
            require_live_ledger_match=status == "paused_preliminary",
            expected_signed_seed_ids=signed_seed_ids,
            expected_evidence_keys=expected_keys,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise PreliminaryAuditError(f"Jalon 15/30 invalide: {error}") from error
    if checkpoint is None:
        raise PreliminaryAuditError("Manifeste du jalon 15/30 absent.")
    if (
        checkpoint.get("completed_seed_ids") != list(completed_seed_ids)
        or checkpoint.get("executed_engine_physical_run_count")
        != EXPECTED_ENGINE_COUNT
        or checkpoint.get("ledger_evidence_case_count")
        != EXPECTED_EVIDENCE_COUNT
        or checkpoint.get("preliminary_not_final") is not True
        or checkpoint.get("promotion_allowed") is not False
    ):
        raise PreliminaryAuditError("Compteurs ou gardes du jalon invalides.")
    if status == "paused_preliminary" and any(
        path.exists() for path in runner._canonical_result_paths(runner_dir)
    ):
        raise PreliminaryAuditError(
            "Des résultats finaux coexistent avec un runner annoncé en pause."
        )

    evidence = _load_checkpoint_evidence(
        runner_dir=runner_dir,
        checkpoint=checkpoint,
    )
    graph_path, _, _ = runner._verify_configuration_paths(
        plan_manifest,
        graph_path=runner.network.DEFAULT_GRAPH,
        engine_path=runner.network.DEFAULT_ENGINE,
        profile_path=runner.network.DEFAULT_PROFILE,
    )
    graph = _read_json(graph_path)
    for case in prefix_owners:
        runner._validate_baseline_evidence(case, evidence[case.case_key])
    baseline_by_id = {
        case.case_id: evidence[owner_by_logical[case.case_key]]
        for case in prefix_baselines
    }
    product_rows: list[dict[str, Any]] = []
    flow_rows: list[dict[str, Any]] = []
    lot_rows: list[dict[str, Any]] = []
    lot_detail_rows: list[dict[str, Any]] = []
    for case in prefix_stress:
        stress = evidence[case.case_key]
        baseline = baseline_by_id[case.paired_baseline_case_id]
        runner._validate_stress_evidence(case, stress, baseline, graph)
        rows = runner._product_rows(case=case, evidence=stress, baseline=baseline)
        if not rows:
            raise PreliminaryAuditError(f"Effet produit absent: {case.case_key}")
        product_rows.extend(rows)
        baseline_flow = runner._baseline_flow_for_case(
            case=case,
            baseline=baseline,
            graph=graph,
        )
        flow_rows.extend(
            runner._flow_rows(
                case=case,
                evidence=stress,
                baseline_flow=baseline_flow,
            )
        )
        if case.extension == "causal_lot_attribution_subset":
            summary, exposed = runner._genealogical_exposure(
                case=case,
                evidence=stress,
            )
            root_count = int(summary.get("root_lot_count", 0))
            descendant_count = int(
                summary.get("exposed_descendant_lot_count", 0)
            )
            case_details = runner._lot_genealogical_exposure_detail_rows(
                case=case,
                exposed_rows=exposed,
            )
            if (
                not summary.get("published_exposure_is_exact_bfs_closure")
                or len(case_details) != int(summary.get("exposed_row_count", -1))
                or sum(
                    row.get("exposure_role")
                    == "risk_tagged_usable_receipt_root"
                    for row in case_details
                )
                != root_count
                or sum(
                    row.get("exposure_role") == "genealogical_descendant"
                    for row in case_details
                )
                != descendant_count
                or any(
                    row.get("descendant_quantity_is_exposure_upper_bound") is not True
                    or row.get("causal_delay_or_loss_claimed") is not False
                    or row.get("counterfactual_entity_identity_validated") is not False
                    or row.get("industrial_lot_number_claimed") is not False
                    for row in case_details
                )
            ):
                raise PreliminaryAuditError(
                    f"Détail généalogique lot invalide: {case.case_key}"
                )
            lot_detail_rows.extend(case_details)
            lot_rows.append(
                {
                    "case_key": case.case_key,
                    "supplier_id": case.lanes[0].supplier_id,
                    "chain_id": case.lanes[0].chain_id,
                    "item_id": case.lanes[0].item_id,
                    "target_product_id": case.products[0],
                    "seed": case.seed,
                    "root_lot_count": root_count,
                    "exposed_descendant_lot_count": descendant_count,
                    "genealogical_exposed_lot_count": (
                        root_count + descendant_count
                    ),
                    "genealogical_exposure_quantity_by_uom": summary.get(
                        "exposed_quantity_upper_bound_by_uom_json", "{}"
                    ),
                    "genealogical_exposure_is_upper_bound": True,
                    "counterfactual_entity_identity_validated": False,
                    "causal_lot_attribution_available": False,
                    "interpretation": (
                        "exemple_technique_sur_une_simulation_non_causal"
                    ),
                }
            )
    _, boundary_rows = _validate_boundary(boundary_dir, lineage)
    return PreliminarySource(
        runner_dir=runner_dir,
        plan_dir=plan_dir,
        boundary_dir=boundary_dir,
        runner_manifest=runner_manifest,
        plan_manifest=plan_manifest,
        checkpoint=checkpoint,
        lineage=lineage,
        completed_seed_ids=completed_seed_ids,
        product_rows=tuple(product_rows),
        flow_rows=tuple(flow_rows),
        lot_rows=tuple(lot_rows),
        lot_detail_rows=tuple(lot_detail_rows),
        boundary_rows=tuple(boundary_rows),
    )


def aggregate_effect_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(
            _text_preserving_zero(row.get(field))
            for field in (
                "extension",
                "case_id",
                "failure_mode",
                "mechanism_value",
                "mechanism_unit",
                "stress_start_day",
                "stress_end_day",
                "outcome_spec_id",
                "outcome_start_day",
                "outcome_end_day",
                "product_id",
                "product_uom",
            )
        )
        grouped[key].append(row)
    result: list[dict[str, Any]] = []
    for key, cell in sorted(grouped.items()):
        extension = key[0]
        expected = 1 if extension == "causal_lot_attribution_subset" else 15
        seeds = sorted({int(row["seed"]) for row in cell})
        if len(cell) != expected or len(seeds) != expected:
            raise PreliminaryAuditError(
                f"Cellule préliminaire incomplète: {key[1]} ({len(cell)}/{expected})."
            )
        on_due = [
            _finite(row.get("delta_on_due_percentage_points"), label="service")
            for row in cell
        ]
        backlog = [
            _finite(
                row.get("delta_backlog_days_per_demand_unit"),
                label="backlog normalisé",
            )
            for row in cell
        ]
        backlog_end = [
            _finite(row.get("delta_backlog_end_qty"), label="backlog final")
            for row in cell
        ]
        production = [
            _finite(
                row.get("signed_production_shortfall_ratio"),
                label="production libérée",
            )
            for row in cell
        ]
        result.append(
            {
                "extension": extension,
                "case_id": key[1],
                "failure_mode": key[2],
                "mechanism_value": key[3],
                "mechanism_unit": key[4],
                "stress_start_day": key[5],
                "stress_end_day": key[6],
                "outcome_spec_id": key[7],
                "outcome_start_day": key[8],
                "outcome_end_day": key[9],
                "product_id": key[10],
                "product_uom": key[11],
                "paired_seed_count": len(seeds),
                "expected_paired_seed_count": expected,
                "preliminary_cell_complete": True,
                "mean_service_delta_percentage_points": _mean(on_due),
                "sample_sd_service_delta_percentage_points": _sample_sd(on_due),
                "min_service_delta_percentage_points": min(on_due),
                "max_service_delta_percentage_points": max(on_due),
                "mean_backlog_delta_days_per_demand_unit": _mean(backlog),
                "sample_sd_backlog_delta_days_per_demand_unit": _sample_sd(backlog),
                "mean_end_backlog_delta_qty": _mean(backlog_end),
                "mean_released_production_shortfall_ratio": _mean(production),
                "interval_is_confirmatory": False,
                "preliminary_not_final": True,
                "action_promotion_allowed": False,
            }
        )
    return result


def aggregate_exposure_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(
            _text_preserving_zero(row.get(field))
            for field in (
                "extension",
                "case_id",
                "failure_mode",
                "stress_start_day",
                "stress_end_day",
                "chain_id",
                "supplier_id",
                "item_id",
                "dst_node_id",
                "uom",
            )
        )
        grouped[key].append(row)
    result: list[dict[str, Any]] = []
    for key, cell in sorted(grouped.items()):
        extension = key[0]
        expected = 1 if extension == "causal_lot_attribution_subset" else 15
        seeds = {int(row["seed"]) for row in cell}
        if len(cell) != expected or len(seeds) != expected:
            raise PreliminaryAuditError(f"Exposition incomplète: {key[1]}/{key[5]}")
        baseline_active = sum(row.get("baseline_flow_exercised") is True for row in cell)
        risk_applied = sum(row.get("risk_event_applied_on_lane") is True for row in cell)
        joint_active = sum(
            row.get("baseline_flow_exercised") is True
            and row.get("risk_event_applied_on_lane") is True
            for row in cell
        )
        result.append(
            {
                "extension": extension,
                "case_id": key[1],
                "failure_mode": key[2],
                "stress_start_day": key[3],
                "stress_end_day": key[4],
                "chain_id": key[5],
                "supplier_id": key[6],
                "item_id": key[7],
                "dst_node_id": key[8],
                "uom": key[9],
                "paired_seed_count": len(seeds),
                "baseline_active_seed_count": baseline_active,
                "risk_applied_seed_count": risk_applied,
                "joint_active_exposure_seed_count": joint_active,
                "active_exposure_interpretation_complete_15": joint_active == expected,
                "zero_effect_means_no_risk": False,
                "preliminary_not_final": True,
            }
        )
    return result


def boundary_group_rows(
    rows: Sequence[Mapping[str, Any]],
    lineage: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mappings = {
        str(item.get("supplier_id") or ""): item
        for item in lineage.get("follow_up_driver_mappings") or []
    }
    indexed = {
        (str(row["supplier_id"]), str(row["metric_key"])): row for row in rows
    }
    result: list[dict[str, Any]] = []
    for supplier in lineage["follow_up_supplier_ids"]:
        mapping = mappings.get(str(supplier))
        if not isinstance(mapping, Mapping):
            raise PreliminaryAuditError(f"Mapping driver absent: {supplier}")
        metrics = {
            metric: _finite(indexed[(str(supplier), metric)]["metric_value"], label=metric)
            for metric in BOUNDARY_METRIC_KEYS
        }
        result.append(
            {
                "supplier_id": supplier,
                "driver_chain_id": mapping.get("driver_chain_id"),
                "driver_scenario_id": mapping.get("driver_scenario_id"),
                "driver_failure_mode": mapping.get("driver_failure_mode"),
                "horizon_service_delta_percentage_points": (
                    100.0 * metrics["horizon_on_due_service_delta"]
                ),
                "worst_rolling_28d_service_delta_percentage_points": (
                    100.0 * metrics["worst_rolling_28d_on_due_delta"]
                ),
                "backlog_delta_days_per_demand_unit": metrics[
                    "incremental_backlog_days_per_requested_unit"
                ],
                "released_production_shortfall_percent": (
                    100.0 * metrics["released_production_shortfall_ratio"]
                ),
                "paired_seed_count": 30,
                "group_is_unordered": True,
                "universal_supplier_ranking_claimed": False,
                "historical_probability_estimated": False,
            }
        )
    return result


def _fmt(value: Any, digits: int = 2) -> str:
    number = _finite(value, label="affichage")
    return f"{number:.{digits}f}".replace(".", ",")


def _service_range_label(row: Mapping[str, Any]) -> str:
    if int(row["paired_seed_count"]) == 1:
        return "non applicable (1 simulation)"
    return (
        f"{_fmt(row['min_service_delta_percentage_points'])} à "
        f"{_fmt(row['max_service_delta_percentage_points'])} pt"
    )


def _chain_business_label(chain_id: Any, supplier_id: Any = "") -> str:
    value = str(chain_id or "")
    match = re.search(
        r"sdc_vd(?P<supplier>[0-9a-z]+)_(?P<item>[0-9]{6})_m_(?P<site>[0-9]+)",
        value,
        flags=re.IGNORECASE,
    )
    if match:
        return (
            f"article {match.group('item')} vers M-{match.group('site')} "
            f"(fournisseur VD{match.group('supplier').upper()})"
        )
    supplier = str(supplier_id or "").removeprefix("SDC-")
    return f"fournisseur {supplier}" if supplier else "dossier fournisseur"


def _mechanism_business_label(row: Mapping[str, Any]) -> str:
    failure_mode = str(row.get("failure_mode") or "")
    label = FAILURE_MODE_LABELS.get(failure_mode, "Incident testé")
    value = _finite(row.get("mechanism_value"), label="intensité de l’incident")
    unit = str(row.get("mechanism_unit") or "")
    if unit == "jours_ajoutes":
        detail = f"{_fmt(value, 0)} jours"
    elif unit in {"part_disponible", "part_utilisable"}:
        detail = f"{_fmt(100.0 * value, 0)} %"
    else:
        detail = f"{_fmt(value)} {unit}".strip()
    return f"{label} ({detail})"


def _effect_business_label(row: Mapping[str, Any]) -> str:
    case_id = str(row.get("case_id") or "")
    chain = _chain_business_label(case_id)
    if chain == "dossier fournisseur":
        common = re.search(
            r"common__sdc-vd(?P<supplier>[0-9a-z]+)__",
            case_id,
            flags=re.IGNORECASE,
        )
        if common:
            chain = (
                f"plusieurs articles du fournisseur "
                f"VD{common.group('supplier').upper()}"
            )
    start = int(_finite(row.get("stress_start_day"), label="début incident"))
    end = int(_finite(row.get("stress_end_day"), label="fin incident"))
    return f"{chain} — {_mechanism_business_label(row)} — J{start} à J{end}"


def _boundary_service_chart(rows: Sequence[Mapping[str, Any]]) -> str:
    if len(rows) != EXPECTED_SERVICE_GROUP_COUNT:
        raise PreliminaryAuditError(
            "Le graphique consolidé exige exactement quatre dossiers."
        )
    values = [
        _finite(row["horizon_service_delta_percentage_points"], label="service")
        for row in rows
    ]
    scale = max((abs(value) for value in values), default=0.0) or 1.0
    body = "".join(
        "<div class='bar-row'>"
        f"<div>{html.escape(_chain_business_label(row.get('driver_chain_id'), row.get('supplier_id')))}</div>"
        "<div class='bar-track' aria-hidden='true'>"
        f"<span class='bar-loss' style='width:{100.0 * abs(value) / scale:.4f}%'></span>"
        "</div>"
        f"<strong>{_fmt(value)} pt</strong>"
        "</div>"
        for row, value in sorted(
            zip(rows, values, strict=True),
            key=lambda pair: str(pair[0].get("supplier_id") or ""),
        )
    )
    return (
        "<div class='chart' role='img' aria-label='Impact moyen simulé sur le "
        "service à la date demandée pour les quatre dossiers'>"
        f"{body}</div><p class='chart-note'>Barre plus longue = baisse plus forte. "
        "Les valeurs exactes sont en points de pourcentage; l’ordre est "
        "alphabétique et ne constitue pas un classement.</p>"
    )


def _focus_338929_range_chart(rows: Sequence[Mapping[str, Any]]) -> str:
    selected = [
        row
        for row in rows
        if row.get("extension") == "priority_four_business_causes"
        and "_338929_" in str(row.get("case_id") or "")
        and int(row.get("paired_seed_count") or 0) == EXPECTED_SEED_COUNT
    ]
    failure_modes = {str(row.get("failure_mode") or "") for row in selected}
    if len(selected) != 4 or failure_modes != set(FAILURE_MODE_LABELS):
        return (
            "<p class='chart-note'>Graphique 338929 non affiché : les quatre "
            "types d’incident ne sont pas tous disponibles sur 15 simulations.</p>"
        )
    for row in selected:
        low = _finite(row["min_service_delta_percentage_points"], label="minimum")
        mean = _finite(row["mean_service_delta_percentage_points"], label="moyenne")
        high = _finite(row["max_service_delta_percentage_points"], label="maximum")
        if low > mean or mean > high:
            raise PreliminaryAuditError(
                "Moyenne de service hors de la plage constatée pour 338929."
            )
    minimum = min(
        0.0,
        *(
            _finite(row["min_service_delta_percentage_points"], label="minimum")
            for row in selected
        ),
    )
    maximum = max(
        0.0,
        *(
            _finite(row["max_service_delta_percentage_points"], label="maximum")
            for row in selected
        ),
    )
    span = maximum - minimum
    if span <= 0.0:
        return "<p class='chart-note'>Aucune variation de service à représenter.</p>"

    def position(value: Any) -> float:
        return 100.0 * (_finite(value, label="graphique") - minimum) / span

    order = tuple(FAILURE_MODE_LABELS)
    selected.sort(key=lambda row: order.index(str(row["failure_mode"])))
    zero_position = position(0.0)
    body = "".join(
        "<div class='range-row'>"
        f"<div>{html.escape(FAILURE_MODE_LABELS[str(row['failure_mode'])])}</div>"
        "<div class='range-track' aria-hidden='true'>"
        f"<span class='zero-line' style='left:{zero_position:.4f}%'></span>"
        f"<span class='range-line' style='left:{position(row['min_service_delta_percentage_points']):.4f}%;width:{position(row['max_service_delta_percentage_points']) - position(row['min_service_delta_percentage_points']):.4f}%'></span>"
        f"<span class='mean-dot' style='left:{position(row['mean_service_delta_percentage_points']):.4f}%'></span>"
        "</div>"
        f"<strong>{_fmt(row['mean_service_delta_percentage_points'])} pt</strong>"
        f"<small>{_service_range_label(row)}</small>"
        "</div>"
        for row in selected
    )
    return (
        "<div class='chart' role='img' aria-label='Moyenne et plage de l’impact "
        "sur le service pour quatre incidents de l’article 338929'>"
        f"{body}</div><p class='chart-note'><span class='legend-range'></span> "
        "plage constatée parmi les 15 simulations; <span class='legend-dot'></span> "
        "moyenne. Axe commun de "
        f"{_fmt(minimum)} à {_fmt(maximum)} points de pourcentage. "
        "Cette dispersion est descriptive, pas une probabilité.</p>"
    )


def render_html(
    *,
    boundary_rows: Sequence[Mapping[str, Any]],
    effect_rows: Sequence[Mapping[str, Any]],
    exposure_rows: Sequence[Mapping[str, Any]],
    lot_rows: Sequence[Mapping[str, Any]],
    lot_detail_rows: Sequence[Mapping[str, Any]] = (),
) -> str:
    boundary_chart = _boundary_service_chart(boundary_rows)
    focus_range_chart = _focus_338929_range_chart(effect_rows)
    boundary_body = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['supplier_id']))}</td>"
        f"<td>{html.escape(_chain_business_label(row['driver_chain_id'], row['supplier_id']))}</td>"
        f"<td>{_fmt(row['horizon_service_delta_percentage_points'])} pt</td>"
        f"<td>{_fmt(row['worst_rolling_28d_service_delta_percentage_points'])} pt</td>"
        f"<td>+{_fmt(row['backlog_delta_days_per_demand_unit'])}</td>"
        f"<td>{_fmt(row['released_production_shortfall_percent'])} %</td>"
        "</tr>"
        for row in sorted(
            boundary_rows,
            key=lambda item: str(item["supplier_id"]),
        )
    )
    effect_body = "".join(
        "<tr>"
        f"<td>{html.escape(EXTENSION_LABELS.get(str(row['extension']), 'Analyse complémentaire'))}</td>"
        f"<td>{html.escape(_effect_business_label(row))}</td>"
        f"<td>{html.escape(str(row['product_id']))}</td>"
        f"<td>{int(row['paired_seed_count'])}</td>"
        f"<td>{_fmt(row['mean_service_delta_percentage_points'])} pt</td>"
        f"<td>{_service_range_label(row)}</td>"
        f"<td>{_fmt(row['mean_backlog_delta_days_per_demand_unit'])}</td>"
        f"<td>{_fmt(100.0 * float(row['mean_released_production_shortfall_ratio']))} %</td>"
        "</tr>"
        for row in effect_rows
    )
    lot_body = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['supplier_id']))}</td>"
        f"<td>{html.escape(str(row['item_id']))}</td>"
        f"<td>{html.escape(str(row['target_product_id']))}</td>"
        f"<td>{int(row['root_lot_count'])}</td>"
        f"<td>{int(row['genealogical_exposed_lot_count'])}</td>"
        "</tr>"
        for row in lot_rows
    )
    lot_detail_body = "".join(
        "<tr class='lot-detail-row'>"
        f"<td>{html.escape(str(row['supplier_ids']))}</td>"
        f"<td><code>{html.escape(str(row['lot_id']))}</code></td>"
        f"<td>{html.escape(LOT_ROLE_LABELS.get(str(row['exposure_role']), 'Rôle technique à vérifier'))}</td>"
        f"<td>{html.escape(str(row.get('genealogy_depth', '')))}</td>"
        f"<td>{html.escape(str(row.get('node_id', '')))}</td>"
        f"<td>{html.escape(str(row.get('item_id', '')))}</td>"
        f"<td>{html.escape(str(row.get('day', '')))}</td>"
        f"<td>{_fmt(row['qty'])} {html.escape(str(row['uom']))}</td>"
        "</tr>"
        for row in lot_detail_rows
    )
    exposure_complete = sum(
        row["active_exposure_interpretation_complete_15"] is True
        for row in exposure_rows
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Préliminaire réseau fournisseurs — 15/30</title>
<style>
body{{font:15px/1.45 system-ui,sans-serif;margin:0;background:#f3f6fa;color:#14243a}}main{{max-width:1500px;margin:auto;padding:24px}}section{{background:white;border:1px solid #d9e2ee;border-radius:14px;padding:20px;margin:16px 0}}.warn{{background:#fff2cc;border:2px solid #d88b00}}h1,h2{{margin-top:0}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #dde5ee;text-align:left}}th{{background:#edf3f9;position:sticky;top:0}}.scroll{{overflow:auto;max-height:520px}}code{{font-size:11px}}.tag{{display:inline-block;padding:4px 8px;border-radius:12px;background:#e9eef5;margin-right:6px}}.definitions{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}}.definition{{border-left:4px solid #2670ca;padding:8px 12px;background:#f6f9fc}}.chart{{border:1px solid #dde5ee;border-radius:12px;padding:14px;overflow:auto}}.bar-row{{display:grid;grid-template-columns:minmax(260px,1.5fr) minmax(180px,3fr) 90px;gap:10px;align-items:center;margin:9px 0}}.bar-track,.range-track{{height:18px;background:#edf2f7;border-radius:9px;position:relative;overflow:hidden}}.bar-track{{display:flex;justify-content:flex-end}}.bar-loss{{display:block;background:#d64036;border-radius:9px}}.range-row{{display:grid;grid-template-columns:minmax(220px,1.5fr) minmax(230px,3fr) 80px 180px;gap:10px;align-items:center;margin:12px 0}}.range-line{{position:absolute;top:7px;height:4px;background:#3b82c4}}.mean-dot{{position:absolute;top:3px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:#0b5cab;border:2px solid white;box-sizing:border-box}}.zero-line{{position:absolute;top:0;bottom:0;width:1px;background:#68798d}}.chart-note{{color:#52657b;font-size:13px}}.legend-range{{display:inline-block;width:26px;border-top:4px solid #3b82c4;vertical-align:middle}}.legend-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#0b5cab;vertical-align:middle}}@media(max-width:850px){{.bar-row,.range-row{{grid-template-columns:1fr}}.bar-track,.range-track{{min-width:280px}}}}
</style></head><body><main>
<section class="warn"><h1>PRÉLIMINAIRE — 15 simulations sur 30</h1>
<p><strong>Ces analyses complémentaires ne sont qu’à mi-parcours.</strong> Elles montrent les conséquences possibles des incidents choisis. Elles ne permettent ni de prédire leur survenue, ni de classer tous les fournisseurs, ni de recommander une action. Les 30 simulations et leur vérification restent nécessaires.</p>
<p><span class="tag">aucune action recommandée</span><span class="tag">aucun classement général</span><span class="tag">pas de conclusion statistique finale</span></p></section>
<section><h2>Comment lire les indicateurs</h2><div class="definitions"><div class="definition"><strong>Service à la date demandée</strong><br>Part du volume demandé qui est disponible au plus tard à la date attendue. L’impact est exprimé en points de pourcentage par rapport à la situation sans incident.</div><div class="definition"><strong>Pire période de 28 jours</strong><br>Plus forte baisse du service constatée sur 28 jours consécutifs. Cette durée lisse les pics quotidiens sans masquer un mois difficile.</div><div class="definition"><strong>Retard cumulé ramené à la demande</strong><br>Accumulation des quantités en attente, divisée par le volume demandé. Le résultat se lit comme un nombre de jours équivalents de retard.</div><div class="definition"><strong>Rattrapage de production</strong><br>Part de la production libérée qui manque encore à la fin des 720 jours. Zéro signifie que la quantité a été rattrapée, pas qu’elle a été livrée à temps.</div></div></section>
<section><h2>Point déjà consolidé avant ce jalon — 30/30</h2>
<p>La campagne principale distingue un <strong>groupe de quatre dossiers que les simulations ne permettent pas d’ordonner de façon fiable</strong>. L’ordre ci-dessous est uniquement alphabétique. Les chiffres décrivent les conséquences d’incidents hypothétiques dans le modèle, pas la fiabilité intrinsèque ni la probabilité de défaillance d’un fournisseur.</p>
<h3>Impact moyen sur le service à la date demandée</h3>{boundary_chart}
<div class="scroll"><table><thead><tr><th>Fournisseur</th><th>Voie examinée</th><th>Impact moyen sur le service à la date demandée<br>(720 jours)</th><th>Pire période de 28 jours<br>(impact moyen)</th><th>Retard cumulé ramené à la demande<br>(jours équivalents)</th><th>Production restant à rattraper à J719</th></tr></thead><tbody>{boundary_body}</tbody></table></div>
<p><strong>Lecture métier :</strong> les dossiers les plus exposés peuvent cumuler un fort défaut de ponctualité et du retard de commandes, tout en rattrapant la quantité produite avant la fin de l’horizon. Cela ne doit pas être présenté comme une perte de production.</p></section>
<section><h2>Article 338929 — comparaison provisoire de quatre types d’incident</h2>{focus_range_chart}</section>
<section><h2>Analyses complémentaires en cours — 15 premières simulations</h2>
<p>{len(effect_rows)} résultats produit ont été calculés; {exposure_complete}/{len(exposure_rows)} situations fournisseur montrent à la fois un flux utilisé en situation normale et l’incident effectivement appliqué dans les 15 simulations disponibles. Les variations affichées restent descriptives et ne constituent pas une conclusion statistique finale.</p>
<div class="scroll"><table><thead><tr><th>Question analysée</th><th>Situation simulée</th><th>Produit</th><th>Nombre de simulations</th><th>Impact moyen sur le service à la date demandée</th><th>Valeur la plus basse à la plus haute</th><th>Retard cumulé moyen<br>(jours équivalents)</th><th>Production restant à rattraper à J719</th></tr></thead><tbody>{effect_body}</tbody></table></div></section>
<section><h2>Lots — quatre illustrations techniques</h2>
<p>Une seule comparaison technique est examinée par dossier. Les lots situés en aval représentent une <strong>exposition maximale par filiation</strong>. Les identifiants simulés ne permettent pas d’affirmer qu’un identifiant représente exactement le même lot dans les deux situations comparées; ils ne prouvent ni une causalité industrielle ni la variabilité des lots.</p>
<div class="scroll"><table><thead><tr><th>Fournisseur</th><th>Article</th><th>Produit</th><th>Réceptions à l’origine du suivi</th><th>Lots exposés par filiation simulée</th></tr></thead><tbody>{lot_body}</tbody></table></div>
<h3>Liste consultable des {len(lot_detail_rows)} lots techniques simulés</h3>
<p>Cette liste permet de suivre les identifiants techniques, le site, l’article, le jour et la quantité. Ce ne sont pas des numéros de lots industriels et chaque quantité descendante reste une exposition maximale, pas une perte attribuée à l’incident.</p>
<p><label>Rechercher un fournisseur, lot, site ou article&nbsp;: <input id="lot-filter" type="search" oninput="filterLots()"></label> <a href="{LOT_DETAIL_FILE}">Ouvrir le fichier détaillé</a></p>
<div class="scroll"><table id="lot-detail"><thead><tr><th>Fournisseur</th><th>Lot technique simulé</th><th>Rôle</th><th>Niveau</th><th>Site</th><th>Article</th><th>Jour</th><th>Quantité</th></tr></thead><tbody>{lot_detail_body}</tbody></table></div></section>
<section><h2>Ce qui reste à faire</h2><p>Terminer les 30 simulations, vérifier que les simulations déjà terminées sont réutilisées sans nouveau calcul, puis contrôler les résultats finaux et tester séparément les leviers envisagés. Aucun des quatre leviers opérationnels n’est testé ni recommandé à ce stade. L’ancien indicateur de « jour de récupération » est exclu : aucun nombre de jours récupérés n’est calculé ici.</p></section>
</main><script>function filterLots(){{const q=document.getElementById('lot-filter').value.toLocaleLowerCase('fr');document.querySelectorAll('.lot-detail-row').forEach((row)=>{{row.hidden=!row.textContent.toLocaleLowerCase('fr').includes(q);}});}}</script></body></html>"""


def _audit_payload(
    source: PreliminarySource,
    *,
    effect_rows: Sequence[Mapping[str, Any]],
    exposure_rows: Sequence[Mapping[str, Any]],
    lot_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "preliminary_15_of_30_complete_not_final",
        "created_at_utc": _utc_now(),
        "completed_seed_count": EXPECTED_SEED_COUNT,
        "signed_full_seed_count": 30,
        "completed_seed_ids": list(source.completed_seed_ids),
        "checkpoint_evidence_case_count": EXPECTED_EVIDENCE_COUNT,
        "executed_engine_physical_run_count": EXPECTED_ENGINE_COUNT,
        "remaining_engine_physical_run_count": EXPECTED_ENGINE_COUNT,
        "effect_cell_count": len(effect_rows),
        "active_exposure_cell_count": len(exposure_rows),
        "lot_illustration_count": len(lot_rows),
        "lot_genealogical_exposure_detail_count": len(source.lot_detail_rows),
        "service_nonseparation_group_supplier_ids": source.lineage[
            "follow_up_supplier_ids"
        ],
        "service_nonseparation_group_supplier_count": 4,
        "service_nonseparation_group_is_unordered": True,
        "checkpoint_prefix_reuse_must_be_verified_in_final": True,
        "preliminary_not_final": True,
        "preliminary_results_publishable_as_final": False,
        "supplier_ranking_allowed": False,
        "historical_probability_estimated": False,
        "confirmatory_interval_claimed": False,
        "global_network_priority_robustness_evaluable": False,
        "action_effectiveness_evaluated": False,
        "action_promotion_allowed": False,
        "promotion_allowed": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "days_recovered_claimed": False,
        "lot_genealogical_exposure_is_upper_bound": True,
        "causal_lot_attribution_available": False,
        "counterfactual_entity_identity_validated": False,
        "checkpoint_signature": source.checkpoint["checkpoint_signature"],
        "runner_signature": source.runner_manifest["runner_signature"],
        "plan_signature": source.plan_manifest["plan_signature"],
        "priority_selection_lineage_sha256": source.plan_manifest[
            "priority_selection_lineage_sha256"
        ],
    }


def build_preliminary_package(
    *,
    runner_dir: Path,
    plan_dir: Path,
    boundary_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _assert_external_destination(
        output_dir,
        (runner_dir, plan_dir, boundary_dir),
    )
    if output_dir.exists():
        raise PreliminaryAuditError(f"Destination déjà existante: {output_dir}")
    source = load_preliminary_source(
        runner_dir=runner_dir,
        plan_dir=plan_dir,
        boundary_dir=boundary_dir,
    )
    effects = aggregate_effect_rows(source.product_rows)
    exposures = aggregate_exposure_rows(source.flow_rows)
    confirmed = boundary_group_rows(source.boundary_rows, source.lineage)
    lots = list(source.lot_rows)
    lot_details = list(source.lot_detail_rows)
    if len(lots) != EXPECTED_SERVICE_GROUP_COUNT:
        raise PreliminaryAuditError("Les quatre illustrations lots sont incomplètes.")
    if not lot_details:
        raise PreliminaryAuditError("Le détail des lots exposés est vide.")
    audit = _audit_payload(
        source,
        effect_rows=effects,
        exposure_rows=exposures,
        lot_rows=lots,
    )
    source_hashes = _source_hashes(
        source.runner_dir,
        source.plan_dir,
        source.boundary_dir,
        source.checkpoint,
        source.runner_manifest,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        _write_json(staging / AUDIT_FILE, audit)
        _write_csv(staging / EFFECTS_FILE, effects)
        _write_csv(staging / ACTIVE_EXPOSURE_FILE, exposures)
        _write_csv(staging / LOT_SUMMARY_FILE, lots)
        _write_csv(staging / LOT_DETAIL_FILE, lot_details)
        _write_csv(staging / BOUNDARY_FILE, confirmed)
        (staging / HTML_FILE).write_text(
            render_html(
                boundary_rows=confirmed,
                effect_rows=effects,
                exposure_rows=exposures,
                lot_rows=lots,
                lot_detail_rows=lot_details,
            ),
            encoding="utf-8",
        )
        artifact_hashes = {name: _sha256(staging / name) for name in OUTPUT_FILES}
        signature_payload = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "status": "complete_preliminary_not_final",
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "source_file_sha256": source_hashes,
            "artifact_file_sha256": artifact_hashes,
            "checkpoint_signature": source.checkpoint["checkpoint_signature"],
            "runner_signature": source.runner_manifest["runner_signature"],
            "plan_signature": source.plan_manifest["plan_signature"],
            "completed_seed_count": EXPECTED_SEED_COUNT,
            "signed_full_seed_count": 30,
            "preliminary_not_final": True,
            "promotion_allowed": False,
            "action_promotion_allowed": False,
        }
        manifest = {
            **signature_payload,
            "package_signature": _canonical_sha256(signature_payload),
            "package_signature_semantics": (
                "unkeyed_internal_consistency_digest_not_authentication"
            ),
            "cryptographic_authentication_present": False,
            "sources_mutated": False,
            "runner_output_mutated": False,
            "large_case_directories_copied": False,
            "output_dir": str(output_dir),
        }
        _write_json(staging / MANIFEST_FILE, manifest)
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    validate_preliminary_package(output_dir)
    return manifest


def validate_preliminary_package(root: Path) -> dict[str, Any]:
    root = root.resolve()
    expected = set(OUTPUT_FILES) | {MANIFEST_FILE}
    observed = {path.name for path in root.iterdir() if path.is_file()}
    if observed != expected or any(path.is_dir() for path in root.iterdir()):
        raise PreliminaryAuditError("Inventaire du paquet préliminaire non exact.")
    manifest = _read_json(root / MANIFEST_FILE)
    signature_payload = {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "status",
            "builder_sha256",
            "source_file_sha256",
            "artifact_file_sha256",
            "checkpoint_signature",
            "runner_signature",
            "plan_signature",
            "completed_seed_count",
            "signed_full_seed_count",
            "preliminary_not_final",
            "promotion_allowed",
            "action_promotion_allowed",
        )
    }
    artifacts = manifest.get("artifact_file_sha256")
    sources = manifest.get("source_file_sha256")
    if (
        manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION
        or manifest.get("status") != "complete_preliminary_not_final"
        or manifest.get("completed_seed_count") != EXPECTED_SEED_COUNT
        or manifest.get("signed_full_seed_count") != 30
        or manifest.get("preliminary_not_final") is not True
        or manifest.get("promotion_allowed") is not False
        or manifest.get("action_promotion_allowed") is not False
        or manifest.get("cryptographic_authentication_present") is not False
        or manifest.get("sources_mutated") is not False
        or manifest.get("runner_output_mutated") is not False
        or manifest.get("large_case_directories_copied") is not False
        or str(manifest.get("builder_sha256") or "")
        != _sha256(Path(__file__).resolve())
        or not isinstance(sources, Mapping)
        or set(sources) != SOURCE_HASH_KEYS
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value.lower())
            for value in sources.values()
        )
        or not isinstance(artifacts, Mapping)
        or set(artifacts) != set(OUTPUT_FILES)
        or manifest.get("package_signature") != _canonical_sha256(signature_payload)
    ):
        raise PreliminaryAuditError("Manifeste préliminaire invalide.")
    for name, expected_hash in artifacts.items():
        if _sha256(root / str(name)) != str(expected_hash):
            raise PreliminaryAuditError(f"Artefact préliminaire altéré: {name}")
    audit = _read_json(root / AUDIT_FILE)
    required_false = (
        "preliminary_results_publishable_as_final",
        "supplier_ranking_allowed",
        "historical_probability_estimated",
        "confirmatory_interval_claimed",
        "global_network_priority_robustness_evaluable",
        "action_effectiveness_evaluated",
        "action_promotion_allowed",
        "promotion_allowed",
        "days_recovered_claimed",
        "causal_lot_attribution_available",
        "counterfactual_entity_identity_validated",
    )
    if (
        audit.get("schema_version") != SCHEMA_VERSION
        or audit.get("status") != "preliminary_15_of_30_complete_not_final"
        or audit.get("completed_seed_count") != EXPECTED_SEED_COUNT
        or audit.get("checkpoint_evidence_case_count") != EXPECTED_EVIDENCE_COUNT
        or audit.get("preliminary_not_final") is not True
        or not all(audit.get(field) is False for field in required_false)
        or audit.get("network_recovery_metric_status")
        != "excluded_invalid_common_window"
        or audit.get("service_nonseparation_group_is_unordered") is not True
        or audit.get("service_nonseparation_group_supplier_count") != 4
        or int(audit.get("lot_genealogical_exposure_detail_count") or 0) <= 0
        or audit.get("lot_genealogical_exposure_is_upper_bound") is not True
    ):
        raise PreliminaryAuditError("Gardes scientifiques préliminaires invalides.")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-dir", type=Path)
    parser.add_argument("--plan-dir", type=Path)
    parser.add_argument("--boundary-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_only:
        validate_preliminary_package(args.output_dir)
        print(json.dumps({"status": "valid", "output_dir": str(args.output_dir)}))
        return 0
    missing = [
        name
        for name, value in (
            ("--runner-dir", args.runner_dir),
            ("--plan-dir", args.plan_dir),
            ("--boundary-dir", args.boundary_dir),
        )
        if value is None
    ]
    if missing:
        parser.error("arguments requis: " + ", ".join(missing))
    manifest = build_preliminary_package(
        runner_dir=args.runner_dir,
        plan_dir=args.plan_dir,
        boundary_dir=args.boundary_dir,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output_dir": str(args.output_dir.resolve()),
                "package_signature": manifest["package_signature"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
