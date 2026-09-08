#!/usr/bin/env python3
"""Build additive descriptive V8 checkpoints for one state at 10/20/30 seeds.

This adapter generalises the frozen op_100 10/30 checkpoint without modifying
it.  It accepts exactly one signed operating state and the first 10, 20 or 30
campaign seeds.  Readiness is the default, read-only mode.  ``--mode build`` is
the only mode that publishes a new-or-byte-identical package outside the source
campaign; it never starts the simulation engine.

Even a 30/30 package is complete only for the selected state.  Cross-state
persistence, sensitivity, lot replays and action evaluation remain outside this
descriptive checkpoint.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_op100_checkpoint_10 as legacy,
)


DEFAULT_CAMPAIGN_ROOT = (
    Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
    / "supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
)
PROTECTED_LEGACY_OUTPUT = (
    Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
    / "supplier_v8_op100_checkpoint_10_20260906_v1"
)
EXPECTED_CAMPAIGN_SIGNATURE = (
    "fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598"
)
EXPECTED_LEGACY_SHA256 = (
    "4c8a672869073cd9193357c0bfd4086f224f7f215c8d6d8818eae194ae9199c8"
)
OPERATING_POINTS = ("op_100", "op_93", "op_80")
SIMULATION_COUNTS = (10, 20, 30)
SEEDS_PER_SHARD = 5
LANE_COUNT = 18
MECHANISMS = legacy.MECHANISMS
ROWS_PER_SHARD = 185
SUPPLIER_STAT_FIELDS = (
    *legacy.SUPPLIER_STAT_FIELDS[:12],
    "service_loss_median_pp",
    *legacy.SUPPLIER_STAT_FIELDS[12:],
)


class StateCheckpointError(legacy.CheckpointError):
    """Raised when a state checkpoint cannot be proved without ambiguity."""


class StateCheckpointNotReady(StateCheckpointError):
    """Raised while one of the requested signed shards is incomplete."""


@dataclass(frozen=True)
class CheckpointConfig:
    operating_point_id: str
    simulation_count: int
    expected_campaign_signature: str
    target_blocks: tuple[int, ...]
    target_shards: tuple[str, ...]
    expected_seeds: tuple[int, ...]
    baseline_count: int
    incident_count: int
    total_count: int
    risk_file_count: int
    schema_version: str
    package_schema_version: str
    result_schema_version: str
    evidence_index_schema_version: str
    html_name: str
    result_name: str
    metrics_name: str
    lane_stats_name: str
    supplier_stats_name: str
    evidence_index_name: str
    manifest_name: str
    package_files: frozenset[str]
    source_metadata_paths: tuple[str, ...]
    business_label_fr: str


_ORIGINALS = {
    "evaluate_readiness": legacy.evaluate_readiness,
    "validate_complete_shard_metadata": legacy._validate_complete_shard_metadata,  # noqa: SLF001
    "expected_case_keys": legacy._expected_case_keys,  # noqa: SLF001
    "partial_validation_constants": legacy._partial_validation_constants,  # noqa: SLF001
    "descriptive_statistics": legacy._descriptive_statistics,  # noqa: SLF001
    "render_html": legacy.render_html,
    "result_payload": legacy._result_payload,  # noqa: SLF001
    "builder_sources": legacy._builder_sources,  # noqa: SLF001
    "validate_html": legacy._validate_html,  # noqa: SLF001
    "validate_package": legacy.validate_package,
}


def make_config(
    operating_point_id: str,
    simulation_count: int,
    *,
    expected_campaign_signature: str = EXPECTED_CAMPAIGN_SIGNATURE,
) -> CheckpointConfig:
    if operating_point_id not in OPERATING_POINTS:
        raise StateCheckpointError(
            "État attendu : op_100, op_93 ou op_80."
        )
    if simulation_count not in SIMULATION_COUNTS:
        raise StateCheckpointError("Jalon attendu : 10, 20 ou 30 simulations.")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_campaign_signature):
        raise StateCheckpointError("Signature de campagne attendue invalide.")
    block_count = simulation_count // SEEDS_PER_SHARD
    blocks = tuple(range(1, block_count + 1))
    shards = tuple(
        f"{operating_point_id}__seed_block_{block:02d}" for block in blocks
    )
    seeds = tuple(legacy.trace_package.CAMPAIGN_SEEDS[:simulation_count])
    baseline_count = simulation_count
    incident_count = simulation_count * LANE_COUNT * len(MECHANISMS)
    total_count = baseline_count + incident_count
    slug = f"{operating_point_id}_{simulation_count}_sur_30"
    schema = f"etudecas.supplier_v8.state_checkpoint.{slug}.v1"
    html_name = f"OUVRIR_BILAN_PROVISOIRE_{slug.upper()}.html"
    result_name = f"bilan_provisoire_{slug}.json"
    metrics_name = f"mesures_simulees_{total_count}_{slug}.csv"
    lane_name = f"resultats_descriptifs_par_voie_{slug}.csv"
    supplier_name = f"vue_descriptive_fournisseurs_{slug}.csv"
    evidence_name = f"index_preuves_sources_{slug}.json"
    manifest_name = f"manifest_paquet_{slug}.json"
    names = frozenset(
        {
            html_name,
            result_name,
            metrics_name,
            lane_name,
            supplier_name,
            evidence_name,
            manifest_name,
        }
    )
    labels = {
        "op_100": "état simulé proche du niveau de service 100 %",
        "op_93": "état simulé proche du niveau de service 93 %",
        "op_80": "état simulé proche du niveau de service 80 %",
    }
    metadata_paths = (
        "campaign_manifest.json",
        *(f"shards/{shard}/progress.json" for shard in shards),
        *(f"shards/{shard}/shard_manifest.json" for shard in shards),
    )
    return CheckpointConfig(
        operating_point_id=operating_point_id,
        simulation_count=simulation_count,
        expected_campaign_signature=expected_campaign_signature,
        target_blocks=blocks,
        target_shards=shards,
        expected_seeds=seeds,
        baseline_count=baseline_count,
        incident_count=incident_count,
        total_count=total_count,
        risk_file_count=incident_count,
        schema_version=schema,
        package_schema_version=f"{schema}.package.v1",
        result_schema_version=f"{schema}.result.v1",
        evidence_index_schema_version=f"{schema}.evidence_index.v1",
        html_name=html_name,
        result_name=result_name,
        metrics_name=metrics_name,
        lane_stats_name=lane_name,
        supplier_stats_name=supplier_name,
        evidence_index_name=evidence_name,
        manifest_name=manifest_name,
        package_files=names,
        source_metadata_paths=metadata_paths,
        business_label_fr=labels[operating_point_id],
    )


def validate_frozen_legacy() -> Path:
    path = Path(legacy.__file__).resolve()
    digest = legacy._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_LEGACY_SHA256:
        raise StateCheckpointError(
            "Le générateur historique 10/30 a changé; adaptation refusée : " + digest
        )
    return path


def _expected_seed_map(
    manifest: Mapping[str, Any], config: CheckpointConfig
) -> dict[str, tuple[int, ...]]:
    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise StateCheckpointError("Définitions de blocs absentes du manifeste.")
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in shards:
        if not isinstance(row, Mapping):
            continue
        shard_id = str(row.get("shard_id") or "")
        if shard_id in by_id:
            raise StateCheckpointError("Identifiant de bloc dupliqué dans le manifeste.")
        by_id[shard_id] = row
    result: dict[str, tuple[int, ...]] = {}
    for shard_id, block in zip(
        config.target_shards, config.target_blocks, strict=True
    ):
        row = by_id.get(shard_id)
        if row is None:
            raise StateCheckpointError(f"Bloc non déclaré : {shard_id}.")
        try:
            seeds = tuple(int(value) for value in row.get("seed_ids") or ())
            row_block = int(row.get("seed_block", -1))
        except (TypeError, ValueError) as exc:
            raise StateCheckpointError(f"Graines invalides : {shard_id}.") from exc
        if (
            row.get("operating_point_id") != config.operating_point_id
            or row_block != block
            or len(seeds) != SEEDS_PER_SHARD
            or len(set(seeds)) != SEEDS_PER_SHARD
        ):
            raise StateCheckpointError(f"Contrat de bloc incohérent : {shard_id}.")
        result[shard_id] = seeds
    combined = tuple(seed for shard in config.target_shards for seed in result[shard])
    if combined != config.expected_seeds:
        raise StateCheckpointError(
            "Les blocs ne couvrent pas exactement les premières graines signées."
        )
    return result


def _validate_complete_shard_metadata(
    config: CheckpointConfig,
    *,
    manifest: Mapping[str, Any],
    shard_id: str,
    block_number: int,
    seeds: Sequence[int],
    progress: Mapping[str, Any],
    shard_manifest: Mapping[str, Any],
) -> None:
    campaign_signature = str(manifest.get("campaign_signature") or "")
    shard_index = OPERATING_POINTS.index(config.operating_point_id) * 6 + block_number
    if (
        campaign_signature != config.expected_campaign_signature
        or progress.get("schema_version") != legacy.campaign_v4.PROGRESS_SCHEMA_VERSION
        or progress.get("campaign_signature") != campaign_signature
        or progress.get("shard_id") != shard_id
        or int(progress.get("shard_index", -1)) != shard_index
        or progress.get("operating_point_id") != config.operating_point_id
        or int(progress.get("seed_block", -1)) != block_number
        or progress.get("seed_ids") != list(seeds)
        or progress.get("status") != "complete"
        or int(progress.get("planned_case_count", -1)) != ROWS_PER_SHARD
        or int(progress.get("completed_case_count", -1)) != ROWS_PER_SHARD
        or int(progress.get("failed_case_count", -1)) != 0
        or progress.get("running_case_keys") != []
        or progress.get("errors") != []
    ):
        raise StateCheckpointNotReady(f"Bloc incomplet ou en erreur : {shard_id}.")

    unsigned = dict(shard_manifest)
    for field in (
        "completed_case_count",
        "valid_case_count",
        "invalid_or_not_applicable_case_count",
        "runtime_failure_count",
        "completed_at_utc",
    ):
        unsigned.pop(field, None)
    signature = str(unsigned.pop("shard_signature", ""))
    unsigned["status"] = "planned"
    expected_lanes = [str(row.get("lane_id") or "") for row in manifest["lanes"]]
    if (
        shard_manifest.get("schema_version")
        != f"{legacy.campaign_v4.SCHEMA_VERSION}.shard.v1"
        or shard_manifest.get("campaign_signature") != campaign_signature
        or shard_manifest.get("shard_id") != shard_id
        or int(shard_manifest.get("shard_index", -1)) != shard_index
        or shard_manifest.get("operating_point_id") != config.operating_point_id
        or int(shard_manifest.get("seed_block", -1)) != block_number
        or shard_manifest.get("seed_ids") != list(seeds)
        or shard_manifest.get("lane_ids") != expected_lanes
        or shard_manifest.get("mechanisms") != list(MECHANISMS)
        or shard_manifest.get("execution_scope") != "campaign_shard"
        or shard_manifest.get("adaptive_horizon") is not True
        or shard_manifest.get("status") != "complete"
        or int(shard_manifest.get("planned_case_count", -1)) != ROWS_PER_SHARD
        or int(shard_manifest.get("completed_case_count", -1)) != ROWS_PER_SHARD
        or int(shard_manifest.get("valid_case_count", -1)) != ROWS_PER_SHARD
        or int(shard_manifest.get("invalid_or_not_applicable_case_count", -1)) != 0
        or int(shard_manifest.get("runtime_failure_count", -1)) != 0
        or not re.fullmatch(r"[0-9a-f]{64}", signature)
        or signature
        != legacy.campaign_v4._stable_sha256(unsigned)  # noqa: SLF001
    ):
        raise StateCheckpointError(f"Contrat final invalide : {shard_id}.")


def _expected_case_keys(
    config: CheckpointConfig,
    *,
    shard_id: str,
    seeds: Sequence[int],
    lane_ids: Sequence[str],
) -> set[str]:
    if shard_id not in config.target_shards:
        raise StateCheckpointError(f"Bloc hors périmètre : {shard_id}.")
    point = config.operating_point_id
    keys = {f"{point}__baseline__seed_{seed}" for seed in seeds}
    keys.update(
        f"{point}__{lane_id}__{mechanism}__seed_{seed}"
        for seed in seeds
        for lane_id in lane_ids
        for mechanism in MECHANISMS
    )
    return keys


@contextmanager
def _partial_validation_constants(config: CheckpointConfig) -> Iterator[None]:
    finalizer = legacy.finalizer_v4
    names = (
        "OPERATING_POINTS",
        "EXPECTED_SEEDS",
        "EXPECTED_REPETITION_COUNT",
        "EXPECTED_BASELINE_COUNT",
        "EXPECTED_INCIDENT_COUNT",
        "EXPECTED_TOTAL_COUNT",
    )
    previous = {name: getattr(finalizer, name) for name in names}
    finalizer.OPERATING_POINTS = (config.operating_point_id,)
    finalizer.EXPECTED_SEEDS = config.expected_seeds
    finalizer.EXPECTED_REPETITION_COUNT = config.simulation_count
    finalizer.EXPECTED_BASELINE_COUNT = config.baseline_count
    finalizer.EXPECTED_INCIDENT_COUNT = config.incident_count
    finalizer.EXPECTED_TOTAL_COUNT = config.total_count
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(finalizer, name, value)


def _evaluate_readiness(
    campaign_root: Path,
    *,
    config: CheckpointConfig,
    scanner: legacy.ProcessScanner,
) -> dict[str, Any]:
    root = campaign_root.resolve(strict=False)
    active = legacy._active_targets(root, scanner=scanner)  # noqa: SLF001
    if active:
        return {
            "schema_version": f"{config.schema_version}.readiness.v1",
            "status": "running_target_shards",
            "ready": False,
            "campaign_files_read": False,
            "active_processes": active,
            "message_fr": "Les blocs demandés travaillent encore; aucun fichier de campagne n'a été lu.",
        }
    try:
        manifest, manifest_raw = legacy._read_json_shared(  # noqa: SLF001
            root / "campaign_manifest.json"
        )
        if manifest.get("campaign_signature") != config.expected_campaign_signature:
            raise StateCheckpointError("Signature de campagne inattendue.")
        seed_map = _expected_seed_map(manifest, config)
        metadata: dict[str, Any] = {
            "campaign_manifest.json": {
                "sha256": legacy._sha256_bytes(manifest_raw),  # noqa: SLF001
                "size_bytes": len(manifest_raw),
            }
        }
        completed_at: list[str] = []
        for shard_id, block in zip(
            config.target_shards, config.target_blocks, strict=True
        ):
            shard_dir = root / "shards" / shard_id
            progress, progress_raw = legacy._read_json_shared(  # noqa: SLF001
                shard_dir / "progress.json"
            )
            shard_manifest, shard_raw = legacy._read_json_shared(  # noqa: SLF001
                shard_dir / "shard_manifest.json"
            )
            _validate_complete_shard_metadata(
                config,
                manifest=manifest,
                shard_id=shard_id,
                block_number=block,
                seeds=seed_map[shard_id],
                progress=progress,
                shard_manifest=shard_manifest,
            )
            for name, raw in (
                (f"shards/{shard_id}/progress.json", progress_raw),
                (f"shards/{shard_id}/shard_manifest.json", shard_raw),
            ):
                metadata[name] = {
                    "sha256": legacy._sha256_bytes(raw),  # noqa: SLF001
                    "size_bytes": len(raw),
                }
            completed_at.append(str(shard_manifest.get("completed_at_utc") or ""))
    except (
        legacy.CheckpointError,
        FileNotFoundError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        return {
            "schema_version": f"{config.schema_version}.readiness.v1",
            "status": "not_ready",
            "ready": False,
            "campaign_files_read": True,
            "active_processes": [],
            "message_fr": str(exc),
        }
    active_after = legacy._active_targets(root, scanner=scanner)  # noqa: SLF001
    if active_after:
        return {
            "schema_version": f"{config.schema_version}.readiness.v1",
            "status": "activity_race_detected",
            "ready": False,
            "campaign_files_read": True,
            "active_processes": active_after,
            "message_fr": "Une activité est apparue pendant le contrôle; publication refusée.",
        }
    return {
        "schema_version": f"{config.schema_version}.readiness.v1",
        "status": "ready_complete_selected_shards",
        "ready": True,
        "campaign_files_read": True,
        "active_processes": [],
        "campaign_signature": manifest["campaign_signature"],
        "operating_point_id": config.operating_point_id,
        "simulation_count": config.simulation_count,
        "shard_ids": list(config.target_shards),
        "seed_ids": list(config.expected_seeds),
        "baseline_case_count": config.baseline_count,
        "incident_case_count": config.incident_count,
        "completed_case_count": config.total_count,
        "failed_case_count": 0,
        "completed_at_utc": max(completed_at),
        "source_metadata": metadata,
        "message_fr": (
            f"{len(config.target_shards)} blocs terminés sans erreur; "
            f"le bilan {config.simulation_count}/30 de {config.operating_point_id} peut être construit."
        ),
    }


def _descriptive_statistics(
    paired: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lane_rows, supplier_rows = _ORIGINALS["descriptive_statistics"](paired)
    medians = {
        (row["mechanism"], row["lane_id"]): row["service_loss_median_pp"]
        for row in lane_rows
    }
    enriched: list[dict[str, Any]] = []
    for source in supplier_rows:
        row = dict(source)
        row["service_loss_median_pp"] = medians[
            (row["mechanism"], row["representative_lane_id"])
        ]
        enriched.append(row)
    return lane_rows, enriched


def _fr(value: Any, digits: int = 2) -> str:
    return f"{float(value):,.{digits}f}".replace(",", " ").replace(".", ",")


def _supplier_table(
    rows: Sequence[Mapping[str, Any]], mechanism: str, simulation_count: int
) -> str:
    body: list[str] = []
    for row in rows:
        if row["mechanism"] != mechanism:
            continue
        item = str(row["item_id"]).removeprefix("item:")
        body.append(
            "<tr>"
            f"<td>{int(row['descriptive_order'])}</td>"
            f"<td><strong>{html.escape(str(row['supplier_id']))}</strong><br>"
            f"<small>{html.escape(item)} vers {html.escape(str(row['dst_node_id']))}, "
            f"produit {html.escape(str(row['target_product_id']))}</small></td>"
            f"<td>{_fr(row['service_loss_mean_pp'])}</td>"
            f"<td>{_fr(row['service_loss_median_pp'])}</td>"
            f"<td>{_fr(row['service_loss_p10_pp'])} – {_fr(row['service_loss_p90_pp'])}</td>"
            f"<td>{int(row['positive_service_effect_count'])}/{simulation_count}</td>"
            f"<td>{int(row['physical_exercise_count'])}/{simulation_count}</td>"
            f"<td>{_fr(row['on_due_units_lost_mean'], 0)}</td>"
            f"<td>{_fr(row['production_not_released_mean_qty'], 0)}</td>"
            "</tr>"
        )
    return "".join(body)


def _render_html(result: Mapping[str, Any], config: CheckpointConfig) -> str:
    sections: list[str] = []
    for mechanism in MECHANISMS:
        sections.append(
            f"""
<section><span class="tag">HYPOTHÈSE SIMULÉE</span>
<h2>{html.escape(legacy._mechanism_label(mechanism))}</h2>
<p>Chaque ligne représente la voie la plus sensible observée pour ce fournisseur dans ce seul état simulé.
L'ordre est descriptif et peut changer avec les autres états.</p>
<div class="scroll"><table><thead><tr><th>Ordre descriptif</th><th>Flux représentatif</th>
<th>Baisse moyenne<br>(points)</th><th>Médiane<br>(points)</th><th>P10 – P90<br>(points)</th>
<th>Effet positif</th><th>Incident exercé</th><th>Unités à l'heure perdues<br>moyenne</th>
<th>Production non libérée<br>moyenne</th></tr></thead><tbody>
{_supplier_table(result['supplier_view'], mechanism, config.simulation_count)}
</tbody></table></div></section>"""
        )
    state_completion = (
        "Les 30 répétitions prévues sont disponibles pour cet état. La campagne inter-états reste incomplète."
        if config.simulation_count == 30
        else f"{config.simulation_count} répétitions sur les 30 prévues sont disponibles pour cet état."
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilan provisoire — {html.escape(config.operating_point_id)} — {config.simulation_count}/30</title>
<style>
:root{{--ink:#13263d;--muted:#586b80;--line:#d7e1ec;--bg:#eef3f8;--card:#fff;--blue:#175ec7;--amber:#fff1ca}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px}}section{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin:16px 0}}
h1,h2{{margin-top:0}}.lead{{font-size:1.08rem;color:var(--muted);max-width:95ch}}.warn{{background:var(--amber);border:2px solid #c98500}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metric{{background:white;border:1px solid var(--line);border-radius:13px;padding:16px}}
.metric strong{{font-size:1.55rem;display:block}}small,.metric small{{color:var(--muted)}}.tag{{display:inline-block;background:#e6efff;color:#124caa;border-radius:999px;padding:4px 9px;font-weight:750}}
.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:1350px}}th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:#edf3fa;font-size:.76rem;text-transform:uppercase}}
.definitions{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.definitions article{{border-left:4px solid var(--blue);padding:10px 14px;background:#f6f9fd}}
@media(max-width:850px){{main{{padding:14px}}.grid,.definitions{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="warn"><span class="tag">RÉSULTAT PROVISOIRE — UN SEUL ÉTAT</span>
<h1>Bilan de {html.escape(config.business_label_fr)}</h1><p class="lead"><strong>{state_completion}</strong>
Ce document décrit des conséquences conditionnelles simulées. Il ne constitue pas une évaluation historique des fournisseurs ni un classement final.</p></section>
<section class="grid">
<article class="metric"><strong>{config.simulation_count}/30</strong><small>répétitions stochastiques appariées</small></article>
<article class="metric"><strong>{config.incident_count}</strong><small>incidents simulés et appariés</small></article>
<article class="metric"><strong>{LANE_COUNT}</strong><small>voies physiques testées</small></article>
<article class="metric"><strong>0</strong><small>échec dans les blocs retenus</small></article>
</section>
<section><h2>Comment lire ces chiffres</h2><div class="definitions">
<article><strong>HYPOTHÈSE</strong><p>L'incident est imposé pendant 42 jours; il ne décrit pas un événement historique.</p></article>
<article><strong>SIMULÉ</strong><p>Chaque incident est comparé à sa référence appariée avec la même graine et un protocole de nombres aléatoires communs.</p></article>
<article><strong>Effet positif x/{config.simulation_count}</strong><p>Nombre de répétitions où l'incident diminue le service. Ce n'est pas une fréquence réelle.</p></article>
<article><strong>Incident exercé x/{config.simulation_count}</strong><p>Nombre de répétitions où une expédition a effectivement rencontré l'incident.</p></article>
</div></section>
{''.join(sections)}
<section><h2>Limite de ce point d'étape</h2><p>Ce paquet couvre uniquement {html.escape(config.operating_point_id)}.
Il ne permet pas encore d'établir la persistance d'un signal lorsque l'état global du réseau change.</p></section>
</main></body></html>"""


def _result_payload(
    *,
    snapshot: legacy.SourceSnapshot,
    lane_rows: Sequence[Mapping[str, Any]],
    supplier_rows: Sequence[Mapping[str, Any]],
    config: CheckpointConfig,
) -> dict[str, Any]:
    status = (
        "complete_selected_state_not_cross_state_final"
        if config.simulation_count == 30
        else "complete_provisional_state_checkpoint_not_final"
    )
    unsigned = {
        "schema_version": config.result_schema_version,
        "status": status,
        "evidence_class": "conditional_simulation_descriptive_single_state_checkpoint",
        "scope": {
            "operating_point_id": config.operating_point_id,
            "business_label_fr": config.business_label_fr,
            "completed_simulation_count": config.simulation_count,
            "planned_simulation_count": len(legacy.trace_package.CAMPAIGN_SEEDS),
            "baseline_case_count": config.baseline_count,
            "incident_case_count": config.incident_count,
            "total_case_count": config.total_count,
            "lane_count": LANE_COUNT,
            "mechanisms": list(MECHANISMS),
            "incident_window_days": snapshot.context.disruption_window_days,
            "business_effect_window_days": legacy.finalizer_v4.BUSINESS_WINDOW_DAYS,
        },
        "interpretation": {
            "descriptive_only": True,
            "selected_state_complete": config.simulation_count == 30,
            "full_three_state_campaign_complete": False,
            "final_supplier_classification_allowed": False,
            "cross_state_comparison_available": False,
            "cross_state_persistence_available": False,
            "sensitivity_available": False,
            "lot_trace_available": False,
            "actions_evaluated": False,
            "historical_frequency_estimated": False,
            "bootstrap_or_inferential_interval_published": False,
            "engine_runs_started_by_builder": 0,
        },
        "seed_ids": list(snapshot.seeds),
        "lane_statistics": list(lane_rows),
        "supplier_view": list(supplier_rows),
    }
    return legacy._signed(legacy._json_safe(unsigned), "result_signature")  # noqa: SLF001


def _builder_sources() -> dict[str, dict[str, Any]]:
    sources = dict(_ORIGINALS["builder_sources"]())
    path = Path(__file__).resolve()
    sources[str(path)] = {
        "sha256": legacy._sha256_file(path),  # noqa: SLF001
        "size_bytes": path.stat().st_size,
    }
    return sources


def _validate_html(page: str, config: CheckpointConfig) -> None:
    if "�" in page:
        raise StateCheckpointError("Caractère de remplacement dans la page HTML.")
    folded = re.sub(r"\s+", " ", page.casefold())
    required = (
        "résultat provisoire — un seul état",
        f"{config.simulation_count}/30",
        config.operating_point_id,
        f"effet positif x/{config.simulation_count}",
        f"incident exercé x/{config.simulation_count}",
        "médiane",
        "p10 – p90",
        "ne constitue pas une évaluation historique",
    )
    if any(fragment.casefold() not in folded for fragment in required):
        raise StateCheckpointError("Les avertissements dynamiques manquent dans la page.")
    forbidden = (r"\btop\s*-?\s*3\b", r"\bcriticité\b")
    if any(re.search(pattern, folded) for pattern in forbidden):
        raise StateCheckpointError("Conclusion prématurée dans le bilan d'état.")
    if any(
        fragment in folded
        for fragment in (
            "http://",
            "https://",
            "<script src=",
            "<link rel=",
            "fetch(",
        )
    ):
        raise StateCheckpointError("La page HTML n'est pas autonome.")


def _validate_package(output_dir: Path, config: CheckpointConfig) -> dict[str, Any]:
    root = output_dir.resolve(strict=True)
    if not root.is_dir():
        raise StateCheckpointError(f"Dossier attendu : {root}")
    names = {path.name for path in root.iterdir() if path.is_file()}
    if names != config.package_files:
        raise StateCheckpointError("Contenu inattendu dans le paquet d'état.")
    manifest = legacy._decode_json(  # noqa: SLF001
        (root / config.manifest_name).read_bytes(), label=config.manifest_name
    )
    legacy._verify_signature(manifest, "package_signature", label="paquet")  # noqa: SLF001
    if (
        manifest.get("schema_version") != config.package_schema_version
        or manifest.get("status") != "complete_provisional_new_or_identical"
        or manifest.get("campaign_signature") != config.expected_campaign_signature
        or manifest.get("shard_ids") != list(config.target_shards)
        or manifest.get("seed_ids") != list(config.expected_seeds)
        or manifest.get("source_case_count") != config.total_count
        or manifest.get("source_failure_count") != 0
        or manifest.get("engine_runs_started_by_builder") != 0
    ):
        raise StateCheckpointError("Contrat du paquet d'état invalide.")
    outputs = manifest.get("outputs")
    expected_outputs = config.package_files - {config.manifest_name}
    if not isinstance(outputs, Mapping) or set(outputs) != expected_outputs:
        raise StateCheckpointError("Index de sorties incomplet.")
    for name, reference in outputs.items():
        path = root / name
        if (
            not isinstance(reference, Mapping)
            or reference.get("sha256") != legacy._sha256_file(path)  # noqa: SLF001
            or int(reference.get("size_bytes", -1)) != path.stat().st_size
        ):
            raise StateCheckpointError(f"Sortie altérée : {name}.")

    result = legacy._decode_json(  # noqa: SLF001
        (root / config.result_name).read_bytes(), label=config.result_name
    )
    legacy._verify_signature(result, "result_signature", label="résultat")  # noqa: SLF001
    scope = result.get("scope")
    interpretation = result.get("interpretation")
    expected_status = (
        "complete_selected_state_not_cross_state_final"
        if config.simulation_count == 30
        else "complete_provisional_state_checkpoint_not_final"
    )
    if (
        result.get("schema_version") != config.result_schema_version
        or result.get("status") != expected_status
        or not isinstance(scope, Mapping)
        or scope.get("operating_point_id") != config.operating_point_id
        or scope.get("completed_simulation_count") != config.simulation_count
        or scope.get("baseline_case_count") != config.baseline_count
        or scope.get("incident_case_count") != config.incident_count
        or scope.get("total_case_count") != config.total_count
        or not isinstance(interpretation, Mapping)
        or interpretation.get("descriptive_only") is not True
        or interpretation.get("selected_state_complete")
        is not (config.simulation_count == 30)
        or interpretation.get("full_three_state_campaign_complete") is not False
        or interpretation.get("final_supplier_classification_allowed") is not False
        or interpretation.get("cross_state_comparison_available") is not False
        or interpretation.get("cross_state_persistence_available") is not False
        or interpretation.get("sensitivity_available") is not False
        or interpretation.get("lot_trace_available") is not False
        or interpretation.get("actions_evaluated") is not False
        or interpretation.get("engine_runs_started_by_builder") != 0
        or result.get("seed_ids") != list(config.expected_seeds)
        or len(result.get("lane_statistics") or [])
        != LANE_COUNT * len(MECHANISMS)
    ):
        raise StateCheckpointError("Résultat descriptif d'état incohérent.")
    if any(
        set(row) != set(legacy.LANE_STAT_FIELDS)
        or row.get("simulation_count") != config.simulation_count
        for row in result["lane_statistics"]
    ):
        raise StateCheckpointError("Statistiques par voie incomplètes.")
    if any(
        set(row) != set(SUPPLIER_STAT_FIELDS)
        or row.get("simulation_count") != config.simulation_count
        for row in result["supplier_view"]
    ):
        raise StateCheckpointError("Vue descriptive fournisseurs incomplète.")

    evidence = legacy._decode_json(  # noqa: SLF001
        (root / config.evidence_index_name).read_bytes(),
        label=config.evidence_index_name,
    )
    legacy._verify_signature(  # noqa: SLF001
        evidence, "evidence_index_signature", label="preuves"
    )
    if (
        evidence.get("schema_version") != config.evidence_index_schema_version
        or evidence.get("status") != "complete_reconstructed_from_signed_sources"
        or evidence.get("campaign_signature") != config.expected_campaign_signature
        or evidence.get("case_count") != config.total_count
        or evidence.get("baseline_case_count") != config.baseline_count
        or evidence.get("incident_case_count") != config.incident_count
        or evidence.get("risk_file_count") != config.risk_file_count
        or len(evidence.get("entries") or []) != config.total_count
    ):
        raise StateCheckpointError("Index des preuves incomplet.")
    entries = evidence["entries"]
    evidence_keys: list[str] = []
    risk_keys: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise StateCheckpointError("Entrée de preuve invalide.")
        key = str(entry.get("case_key") or "")
        stage = entry.get("stage")
        fields = {
            "case_key",
            "shard_id",
            "stage",
            "mechanism",
            "evidence_relative_path",
            "evidence_sha256",
        }
        if stage == "incident":
            fields.update({"risk_relative_path", "risk_sha256"})
            risk_keys.append(key)
        elif stage != "baseline":
            raise StateCheckpointError(f"Étape de preuve invalide : {key}.")
        if (
            set(entry) != fields
            or not key.startswith(config.operating_point_id + "__")
            or entry.get("shard_id") not in config.target_shards
            or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("evidence_sha256") or ""))
            or (
                stage == "incident"
                and not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("risk_sha256") or ""))
            )
        ):
            raise StateCheckpointError(f"Référence de preuve invalide : {key}.")
        evidence_keys.append(key)
    if (
        len(set(evidence_keys)) != config.total_count
        or len(set(risk_keys)) != config.risk_file_count
    ):
        raise StateCheckpointError("Références de preuves dupliquées ou incomplètes.")

    metric_rows = legacy._csv_rows(  # noqa: SLF001
        (root / config.metrics_name).read_bytes(),
        expected_fields=legacy.campaign_v4.METRIC_FIELDS,
        label=config.metrics_name,
    )
    lane_rows = legacy._csv_rows(  # noqa: SLF001
        (root / config.lane_stats_name).read_bytes(),
        expected_fields=legacy.LANE_STAT_FIELDS,
        label=config.lane_stats_name,
    )
    supplier_rows = legacy._csv_rows(  # noqa: SLF001
        (root / config.supplier_stats_name).read_bytes(),
        expected_fields=SUPPLIER_STAT_FIELDS,
        label=config.supplier_stats_name,
    )
    if (
        len(metric_rows) != config.total_count
        or len(lane_rows) != LANE_COUNT * len(MECHANISMS)
        or len(supplier_rows) != len(result["supplier_view"])
        or any(
            row.get("operating_point_id") != config.operating_point_id
            or int(float(row.get("seed") or -1)) not in config.expected_seeds
            for row in metric_rows
        )
    ):
        raise StateCheckpointError("Comptage ou identité des tableaux invalide.")
    expected_row_counts = {
        config.metrics_name: len(metric_rows),
        config.lane_stats_name: len(lane_rows),
        config.supplier_stats_name: len(supplier_rows),
    }
    if any(
        outputs[name].get("row_count") != count
        for name, count in expected_row_counts.items()
    ):
        raise StateCheckpointError("Comptage signé des tableaux invalide.")
    metric_keys = [str(row.get("case_key") or "") for row in metric_rows]
    if (
        len(set(metric_keys)) != config.total_count
        or set(metric_keys) != set(evidence_keys)
    ):
        raise StateCheckpointError("Mesures et preuves ne couvrent pas les mêmes cas.")
    _validate_html((root / config.html_name).read_text(encoding="utf-8"), config)
    return manifest


@contextmanager
def patched_checkpoint_context(config: CheckpointConfig) -> Iterator[None]:
    """Patch only the disposable adapter call, then restore the legacy module."""

    validate_frozen_legacy()
    values: dict[str, Any] = {
        "SCHEMA_VERSION": config.schema_version,
        "PACKAGE_SCHEMA_VERSION": config.package_schema_version,
        "RESULT_SCHEMA_VERSION": config.result_schema_version,
        "EVIDENCE_INDEX_SCHEMA_VERSION": config.evidence_index_schema_version,
        "TARGET_SHARDS": config.target_shards,
        "TARGET_BLOCKS": config.target_blocks,
        "EXPECTED_SEEDS": config.expected_seeds,
        "EXPECTED_SEEDS_PER_SHARD": SEEDS_PER_SHARD,
        "EXPECTED_LANE_COUNT": LANE_COUNT,
        "EXPECTED_ROWS_PER_SHARD": ROWS_PER_SHARD,
        "EXPECTED_BASELINE_COUNT": config.baseline_count,
        "EXPECTED_INCIDENT_COUNT": config.incident_count,
        "EXPECTED_TOTAL_COUNT": config.total_count,
        "EXPECTED_RISK_FILE_COUNT": config.risk_file_count,
        "HTML_NAME": config.html_name,
        "RESULT_NAME": config.result_name,
        "METRICS_NAME": config.metrics_name,
        "LANE_STATS_NAME": config.lane_stats_name,
        "SUPPLIER_STATS_NAME": config.supplier_stats_name,
        "EVIDENCE_INDEX_NAME": config.evidence_index_name,
        "MANIFEST_NAME": config.manifest_name,
        "PACKAGE_FILES": config.package_files,
        "SOURCE_METADATA_PATHS": config.source_metadata_paths,
        "SUPPLIER_STAT_FIELDS": SUPPLIER_STAT_FIELDS,
        "evaluate_readiness": lambda root, scanner=legacy.supervisor.scan_processes: _evaluate_readiness(
            root, config=config, scanner=scanner
        ),
        "_validate_complete_shard_metadata": lambda **kwargs: _validate_complete_shard_metadata(
            config, **kwargs
        ),
        "_expected_case_keys": lambda **kwargs: _expected_case_keys(config, **kwargs),
        "_partial_validation_constants": lambda: _partial_validation_constants(config),
        "_descriptive_statistics": _descriptive_statistics,
        "render_html": lambda result: _render_html(result, config),
        "_result_payload": lambda **kwargs: _result_payload(config=config, **kwargs),
        "_builder_sources": _builder_sources,
        "_validate_html": lambda page: _validate_html(page, config),
        "validate_package": lambda output: _validate_package(Path(output), config),
    }
    previous = {name: getattr(legacy, name) for name in values}
    for name, value in values.items():
        setattr(legacy, name, value)
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(legacy, name, value)


def evaluate_readiness(
    campaign_root: Path,
    *,
    config: CheckpointConfig,
    scanner: legacy.ProcessScanner = legacy.supervisor.scan_processes,
) -> dict[str, Any]:
    with patched_checkpoint_context(config):
        return _evaluate_readiness(campaign_root, config=config, scanner=scanner)


def build_checkpoint(
    *,
    campaign_root: Path,
    output_dir: Path,
    config: CheckpointConfig,
    scanner: legacy.ProcessScanner = legacy.supervisor.scan_processes,
) -> dict[str, Any]:
    destination = output_dir.resolve(strict=False)
    protected = PROTECTED_LEGACY_OUTPUT.resolve(strict=False)
    if destination == protected or protected in destination.parents:
        raise StateCheckpointError(
            "Le bilan historique 10/30 est protégé; choisir un nouveau dossier."
        )
    with patched_checkpoint_context(config):
        try:
            result = legacy.build_checkpoint(
                campaign_root=campaign_root,
                output_dir=output_dir,
                scanner=scanner,
            )
        except legacy.CheckpointNotReady as exc:
            raise StateCheckpointNotReady(str(exc)) from exc
        result.update(
            {
                "operating_point_id": config.operating_point_id,
                "simulation_count": config.simulation_count,
                "entrypoint": str(destination / config.html_name),
            }
        )
        return result


def validate_package(
    output_dir: Path, *, config: CheckpointConfig
) -> dict[str, Any]:
    with patched_checkpoint_context(config):
        return _validate_package(output_dir, config)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("readiness", "build", "validate"), default="readiness"
    )
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--operating-point-id", choices=OPERATING_POINTS, required=True)
    parser.add_argument(
        "--simulation-count", type=int, choices=SIMULATION_COUNTS, required=True
    )
    parser.add_argument(
        "--expected-campaign-signature", default=EXPECTED_CAMPAIGN_SIGNATURE
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode in {"build", "validate"} and args.output_dir is None:
        raise SystemExit("--output-dir est requis pour build/validate")
    try:
        config = make_config(
            args.operating_point_id,
            args.simulation_count,
            expected_campaign_signature=args.expected_campaign_signature,
        )
        if args.mode == "readiness":
            result = evaluate_readiness(args.campaign_root, config=config)
            result["filesystem_mutation_performed"] = False
            result["engine_runs_started"] = 0
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0 if result["ready"] else 2
        if args.mode == "validate":
            manifest = validate_package(args.output_dir, config=config)
            result = {
                "status": "valid",
                "mode": "validate",
                "output_dir": str(args.output_dir.resolve()),
                "package_signature": manifest["package_signature"],
                "filesystem_mutation_performed": False,
                "engine_runs_started": 0,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0
        result = build_checkpoint(
            campaign_root=args.campaign_root,
            output_dir=args.output_dir,
            config=config,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    except StateCheckpointNotReady as exc:
        print(
            json.dumps(
                {"status": "not_ready", "message_fr": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 2
    except (legacy.CheckpointError, FileNotFoundError, OSError) as exc:
        print(
            json.dumps(
                {"status": "failed_closed", "message_fr": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
