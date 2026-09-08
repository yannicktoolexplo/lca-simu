#!/usr/bin/env python3
"""Audit reproductible du couplage aléatoire du holdout fournisseur V6.

Ce module est strictement postérieur à la campagne V6. Il ne lance jamais le
moteur et ne modifie aucun artefact V4/V5/V6. Il revalide le plan, les 90
preuves et les traces compactes signées, puis reconstruit les tirages de délai
qui sont effectivement observables dans les traces d'expédition.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as refinement_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_holdout_v6 as holdout_v6,
)


SCHEMA_VERSION = "etudecas.supplier_v6_rng_pairing_audit.v1"
AUDIT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.audit"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest"
CONCLUSION = "aucun_defaut_rng_prouve"
TARGET_PRODUCT = "268967"
HIGH_GROUP = "op_93"
LOW_GROUP = "op_80"
REFERENCE_GROUP = "op_100"
SOURCE_MODE = "lane_release"
INVERSION_SEEDS = (
    1369666196,
    43087084,
    1596008569,
    1416403695,
    1492750790,
    55195456,
)
WITNESS_COUNT = 6

DEFAULT_PLAN_DIR = holdout_v6.DEFAULT_PLAN_OUTPUT
DEFAULT_RUN_DIR = holdout_v6.DEFAULT_RUN_OUTPUT
DEFAULT_OUTPUT_DIR = (
    holdout_v6.DEFAULT_ARTIFACT_ROOT / "supplier_v6_rng_pairing_audit_20260905_v1"
)

AUDIT_JSON = "supplier_v6_rng_pairing_audit.json"
SEED_CSV = "supplier_v6_rng_pairing_seed_summary.csv"
REPORT_MD = "RAPPORT_AUDIT_COUPLAGE_ALEATOIRE_V6_FR.md"
MANIFEST_JSON = "artifact_manifest.json"

CSV_FIELDS = (
    "seed",
    "role",
    "margin_pf268967_pp",
    "service_op93_pf268967_pct",
    "service_op80_pf268967_pct",
    "shipments_op93",
    "shipments_op80",
    "traceable_lane_day_draws_op93",
    "traceable_lane_day_draws_op80",
    "shared_lane_day_identities",
    "union_lane_day_identities",
    "identity_jaccard_pct",
    "op93_only_lane_day_identities",
    "op80_only_lane_day_identities",
    "shared_op80_lead_strictly_longer",
    "shared_equal_lead",
    "shared_op80_lead_shorter",
    "reconstructed_draws_op93",
    "reconstructed_draws_op80",
    "warmup_global_rng_state_equal",
    "warmup_paired_invocation_hash_equal",
    "lot_trace_enabled_op93",
    "lot_trace_enabled_op80",
    "lot_count_op93",
    "lot_count_op80",
)


class PairingAuditError(RuntimeError):
    """La preuve V6 ou sa reconstruction est incomplète ou incohérente."""


@dataclass(frozen=True)
class TraceAudit:
    shipment_count: int
    lane_day_identity_count: int
    reconstructed_draw_count: int
    regular_stream_match_count: int
    annual_stream_only_match_count: int
    mismatch_count: int
    ambiguous_group_count: int
    lead_by_identity: Mapping[tuple[str, int], int]
    trace_signature: str
    trace_gzip_sha256: str


@dataclass(frozen=True)
class SummaryAudit:
    common_random_numbers: bool
    stochastic_lead_times: bool
    lead_time_distribution_mode: str
    supplier_risk_enabled: bool
    state_dependent_risk_enabled: bool
    control_schedule_enabled: bool
    warmup_global_rng_state_sha256: str
    warmup_paired_invocations_sha256: str
    lot_trace_enabled: bool
    lot_count: int
    summary_sha256: str


def stable_sha256(payload: Any) -> str:
    """Hash canonique compatible avec les contrats V4-V6."""

    return holdout_v6.stable_sha256(payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PairingAuditError(f"JSON illisible: {path}") from exc
    if not isinstance(payload, dict):
        raise PairingAuditError(f"Objet JSON attendu: {path}")
    return payload


def _verify_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise PairingAuditError(f"Signature invalide: {label}")
    return signature


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _paired_lead_time_identity(
    *, seed: int, measured_day: int, lane: Mapping[str, Any], source_mode: str
) -> str:
    return "|".join(
        [
            str(int(seed)),
            str(int(measured_day)),
            str(lane["edge_id"]),
            str(lane["supplier_id"]),
            str(lane["dst_node_id"]),
            str(lane["item_id"]),
            source_mode,
        ]
    )


def _paired_lead_time_seed(identity: str, invocation_ordinal: int) -> int:
    digest = hashlib.sha256(
        f"{identity}|{int(invocation_ordinal)}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def expected_erlang_lead_days(
    *,
    seed: int,
    measured_day: int,
    lane: Mapping[str, Any],
    edge: Mapping[str, Any],
    source_mode: str = SOURCE_MODE,
    invocation_ordinal: int = 0,
) -> int:
    """Rejoue exactement le tirage Erlang borné du moteur signé V6."""

    lead = edge.get("lead_time")
    limit = edge.get("delay_step_limit")
    if not isinstance(lead, Mapping) or not isinstance(limit, Mapping):
        raise PairingAuditError(f"Métadonnées lead absentes: {lane['edge_id']}")
    lead_type = str(lead.get("type") or "").lower()
    if "erlang" not in lead_type:
        raise PairingAuditError(f"Distribution non Erlang: {lane['edge_id']}")
    try:
        mean = max(1.0, float(lead["mean"]))
        stages = int(round(max(1.0, float(lead.get("stages", 1.0)))))
        delay_limit = int(round(max(1.0, float(limit["value"]))))
    except (KeyError, TypeError, ValueError) as exc:
        raise PairingAuditError(f"Paramètre lead invalide: {lane['edge_id']}") from exc
    identity = _paired_lead_time_identity(
        seed=seed,
        measured_day=measured_day,
        lane=lane,
        source_mode=source_mode,
    )
    rng = random.Random(_paired_lead_time_seed(identity, invocation_ordinal))
    sampled = rng.gammavariate(stages, mean / stages)
    return min(max(1, math.ceil(sampled)), delay_limit)


def select_quantile_witnesses(
    positive_margins_by_seed: Mapping[int, float], count: int = WITNESS_COUNT
) -> tuple[int, ...]:
    """Choisit des témoins répartis sur toute la distribution positive."""

    ordered = sorted(
        ((float(margin), int(seed)) for seed, margin in positive_margins_by_seed.items()),
        key=lambda item: (item[0], item[1]),
    )
    if count < 2 or len(ordered) < count:
        raise PairingAuditError("Pas assez de marges positives pour les témoins")
    positions = [round(index * (len(ordered) - 1) / (count - 1)) for index in range(count)]
    witnesses = tuple(ordered[position][1] for position in positions)
    if len(set(witnesses)) != count:
        raise PairingAuditError("Sélection de témoins non unique")
    return witnesses


def _edge_index(graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    edges = graph.get("edges")
    if not isinstance(edges, list):
        raise PairingAuditError("Graphe candidat sans arêtes")
    result: dict[str, Mapping[str, Any]] = {}
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise PairingAuditError("Arête de graphe invalide")
        edge_id = str(edge.get("id") or "")
        if not edge_id or edge_id in result:
            raise PairingAuditError("Identifiant d'arête vide ou dupliqué")
        result[edge_id] = edge
    return result


def analyze_trace_payload(
    payload: Mapping[str, Any],
    *,
    lane_by_id: Mapping[str, Mapping[str, Any]],
    graph: Mapping[str, Any],
    target_product: str = TARGET_PRODUCT,
    trace_gzip_sha256: str = "",
) -> TraceAudit:
    """Reconstruit les tirages lane-jour observables d'une trace déjà validée."""

    fields = payload.get("fields")
    raw_rows = payload.get("rows")
    if not isinstance(fields, list) or not isinstance(raw_rows, list):
        raise PairingAuditError("Trace compacte sans champs ou lignes")
    field_index = {str(field): index for index, field in enumerate(fields)}
    required = {
        "lane_id",
        "shipment_id",
        "risk_decision_day",
        "release_day",
        "lead_days",
    }
    if not required.issubset(field_index):
        raise PairingAuditError("Champs requis absents de la trace compacte")
    edge_by_id = _edge_index(graph)
    grouped: dict[tuple[str, int], list[Sequence[Any]]] = defaultdict(list)
    shipment_count = 0
    for raw in raw_rows:
        if not isinstance(raw, list) or len(raw) != len(fields):
            raise PairingAuditError("Ligne de trace compacte invalide")
        lane_id = str(raw[field_index["lane_id"]])
        lane = lane_by_id.get(lane_id)
        if lane is None:
            raise PairingAuditError(f"Lane inconnue dans la trace: {lane_id}")
        if str(lane["target_product_id"]) != target_product:
            continue
        decision_day = int(raw[field_index["risk_decision_day"]])
        grouped[(lane_id, decision_day)].append(raw)
        shipment_count += 1

    reconstructed = 0
    regular_matches = 0
    annual_only_matches = 0
    mismatches = 0
    ambiguous = 0
    lead_by_identity: dict[tuple[str, int], int] = {}
    seed = int(payload["seed"])
    for identity, rows in sorted(grouped.items()):
        lane_id, decision_day = identity
        rows.sort(key=lambda row: str(row[field_index["shipment_id"]]))
        lead_values = {int(row[field_index["lead_days"]]) for row in rows}
        immediate_starts = sum(
            int(row[field_index["release_day"]]) == decision_day for row in rows
        )
        if len(lead_values) != 1 or immediate_starts != 1:
            ambiguous += 1
            continue
        actual = next(iter(lead_values))
        lane = lane_by_id[lane_id]
        edge = edge_by_id.get(str(lane["edge_id"]))
        if edge is None:
            raise PairingAuditError(f"Arête absente du graphe: {lane['edge_id']}")
        expected_regular = expected_erlang_lead_days(
            seed=seed,
            measured_day=decision_day,
            lane=lane,
            edge=edge,
            source_mode=SOURCE_MODE,
        )
        expected_annual = expected_erlang_lead_days(
            seed=seed,
            measured_day=decision_day,
            lane=lane,
            edge=edge,
            source_mode="lane_release_min_annual_lot",
        )
        if actual == expected_regular:
            regular_matches += 1
            reconstructed += 1
            lead_by_identity[identity] = actual
        elif actual == expected_annual:
            annual_only_matches += 1
            reconstructed += 1
            lead_by_identity[identity] = actual
        else:
            mismatches += 1

    return TraceAudit(
        shipment_count=shipment_count,
        lane_day_identity_count=len(grouped),
        reconstructed_draw_count=reconstructed,
        regular_stream_match_count=regular_matches,
        annual_stream_only_match_count=annual_only_matches,
        mismatch_count=mismatches,
        ambiguous_group_count=ambiguous,
        lead_by_identity=lead_by_identity,
        trace_signature=str(payload.get("trace_signature") or ""),
        trace_gzip_sha256=trace_gzip_sha256,
    )


def _load_summary_audit(
    evidence: Mapping[str, Any], *, official_run_dir: Path
) -> SummaryAudit:
    proof = evidence.get("executor_proof")
    raw = proof.get("raw_evidence") if isinstance(proof, Mapping) else None
    if not isinstance(raw, Mapping):
        raise PairingAuditError("Preuve exécuteur officielle absente")
    case_dir = Path(str(raw.get("run_dir") or "")).resolve()
    attempts_root = (official_run_dir / "engine_attempts").resolve()
    if not case_dir.is_relative_to(attempts_root):
        raise PairingAuditError("Répertoire moteur hors du run V6 officiel")
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    expected_sha = str(raw.get("summary_sha256") or "")
    if not summary_path.is_file() or sha256_file(summary_path) != expected_sha:
        raise PairingAuditError("Summary moteur absente ou différente de la preuve signée")
    summary = _read_json(summary_path)
    policy = summary.get("policy")
    tracking = summary.get("production_tracking")
    if not isinstance(policy, Mapping) or not isinstance(tracking, Mapping):
        raise PairingAuditError("Summary moteur incomplète")
    warmup = policy.get("warmup_boundary_audit")
    components = warmup.get("component_sha256") if isinstance(warmup, Mapping) else None
    lot_trace = tracking.get("lot_trace")
    if not isinstance(components, Mapping) or not isinstance(lot_trace, Mapping):
        raise PairingAuditError("Audit warmup ou lot absent du summary")
    control = policy.get("control_schedule")
    supplier_risk = policy.get("supplier_risk")
    state_risk = policy.get("supplier_state_dependent_risk")
    return SummaryAudit(
        common_random_numbers=policy.get("common_random_numbers") is True,
        stochastic_lead_times=policy.get("stochastic_lead_times") is True,
        lead_time_distribution_mode=str(policy.get("lead_time_distribution_mode") or ""),
        supplier_risk_enabled=bool(
            supplier_risk.get("enabled") if isinstance(supplier_risk, Mapping) else True
        ),
        state_dependent_risk_enabled=bool(
            state_risk.get("enabled") if isinstance(state_risk, Mapping) else True
        ),
        control_schedule_enabled=bool(
            control.get("enabled") if isinstance(control, Mapping) else True
        ),
        warmup_global_rng_state_sha256=str(components.get("rng_state") or ""),
        warmup_paired_invocations_sha256=str(
            components.get("paired_rng_invocations") or ""
        ),
        lot_trace_enabled=policy.get("lot_trace_enabled") is True,
        lot_count=int(lot_trace.get("lot_count") or 0),
        summary_sha256=expected_sha,
    )


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise PairingAuditError("Corrélation impossible")
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean) for x, y in zip(left, right)
    )
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    if denominator <= 0.0:
        raise PairingAuditError("Variance nulle pour la corrélation")
    return numerator / denominator


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2.0 + 1.0
        for index in order[cursor:end]:
            result[index] = rank
        cursor = end
    return result


def _correlations(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    margins = [float(row["margin_pf268967_pp"]) for row in rows]
    result: dict[str, dict[str, float]] = {}
    for field in (
        "identity_jaccard_pct",
        "traceable_lane_day_draws_op80",
        "op80_only_lane_day_identities",
        "service_op80_pf268967_pct",
    ):
        values = [float(row[field]) for row in rows]
        result[field] = {
            "pearson": _pearson(margins, values),
            "spearman": _pearson(_average_ranks(margins), _average_ranks(values)),
        }
    return result


def _load_graph(plan: Any, candidate_key: str) -> dict[str, Any]:
    item = plan.manifest["inventory"][candidate_key]
    path = (plan.plan_dir / str(item["graph_path"])).resolve()
    if not path.is_relative_to(plan.plan_dir) or sha256_file(path) != item["graph_sha256"]:
        raise PairingAuditError("Graphe signé absent ou modifié")
    return _read_json(path)


def _source_lane_index(plan: Any) -> dict[str, Mapping[str, Any]]:
    rows = plan.manifest.get("source", {}).get("lanes")
    if not isinstance(rows, list):
        raise PairingAuditError("Contrat de lanes V6 absent")
    result = {str(row["lane_id"]): row for row in rows if isinstance(row, Mapping)}
    if len(result) != len(rows):
        raise PairingAuditError("Contrat de lanes V6 invalide")
    return result


def _validate_holdout_result(
    plan: Any,
    run_dir: Path,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    selection = holdout_v6._load_development_selection(plan, run_dir)  # noqa: SLF001
    mode = holdout_v6._registered_execution_mode(plan, run_dir)  # noqa: SLF001
    if mode != holdout_v6.OFFICIAL_EXECUTION_MODE:
        raise PairingAuditError("Seul le holdout V6 officiel est auditable")
    expected = holdout_v6._build_holdout_result(  # noqa: SLF001
        plan,
        evidence,
        selection,
        execution_mode=mode,
    )
    stored = _read_json(run_dir / "holdout_result.json")
    _verify_signature(stored, "holdout_signature", "résultat holdout V6")
    if stored != expected:
        raise PairingAuditError("Résultat holdout V6 non reproductible")
    return stored


def _candidate_map(plan: Any) -> dict[str, Any]:
    result = {candidate.target_group: candidate for candidate in plan.candidates}
    if set(result) != {REFERENCE_GROUP, HIGH_GROUP, LOW_GROUP}:
        raise PairingAuditError("Triplet V6 sélectionné incomplet")
    return result


def _service_pct(evidence: Mapping[str, Any]) -> float:
    return 100.0 * float(evidence["metrics"]["on_due_service_268967"])


def build_audit_payload(plan_dir: Path, run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Revalide les sources V6 et construit l'audit sans aucune écriture."""

    plan_dir = plan_dir.resolve()
    run_dir = run_dir.resolve()
    plan = holdout_v6.validate_plan(plan_dir)
    evidence = holdout_v6._load_stage_evidence(plan, run_dir, "holdout")  # noqa: SLF001
    result = _validate_holdout_result(plan, run_dir, evidence)
    candidates = _candidate_map(plan)
    high_candidate = candidates[HIGH_GROUP]
    low_candidate = candidates[LOW_GROUP]
    reference_candidate = candidates[REFERENCE_GROUP]
    lanes = _source_lane_index(plan)
    pf_lane_count = sum(
        str(lane["target_product_id"]) == TARGET_PRODUCT for lane in lanes.values()
    )
    if pf_lane_count != 7:
        raise PairingAuditError("Le périmètre PF268967 signé n'est plus de sept lanes")
    graphs = {
        HIGH_GROUP: _load_graph(plan, high_candidate.key),
        LOW_GROUP: _load_graph(plan, low_candidate.key),
    }

    traces: dict[tuple[str, int], TraceAudit] = {}
    summaries: dict[tuple[str, int], SummaryAudit] = {}
    trace_signature_rows: list[str] = []
    for group, candidate in ((HIGH_GROUP, high_candidate), (LOW_GROUP, low_candidate)):
        for seed in holdout_v6.EXPECTED_HOLDOUT_SEEDS:
            trace_payload, _raw, compressed = refinement_v4._load_shipment_trace_file(  # noqa: SLF001
                plan=plan,
                run_dir=run_dir,
                candidate=candidate,
                seed=seed,
            )
            trace = analyze_trace_payload(
                trace_payload,
                lane_by_id=lanes,
                graph=graphs[group],
                trace_gzip_sha256=hashlib.sha256(compressed).hexdigest(),
            )
            traces[(group, seed)] = trace
            trace_signature_rows.append(trace.trace_signature)
            summaries[(group, seed)] = _load_summary_audit(
                evidence[(candidate.key, seed)], official_run_dir=run_dir
            )

    invalid_policy = [
        (group, seed)
        for (group, seed), summary in summaries.items()
        if not (
            summary.common_random_numbers
            and summary.stochastic_lead_times
            and summary.lead_time_distribution_mode == "erlang"
            and not summary.supplier_risk_enabled
            and not summary.state_dependent_risk_enabled
            and not summary.control_schedule_enabled
        )
    ]
    if invalid_policy:
        raise PairingAuditError(f"Politique moteur non comparable: {invalid_policy}")

    margins = {
        seed: _service_pct(evidence[(high_candidate.key, seed)])
        - _service_pct(evidence[(low_candidate.key, seed)])
        for seed in holdout_v6.EXPECTED_HOLDOUT_SEEDS
    }
    inversions = tuple(seed for seed, _ in sorted(margins.items(), key=lambda item: item[1]) if margins[seed] < 0.0)
    if set(inversions) != set(INVERSION_SEEDS) or len(inversions) != len(INVERSION_SEEDS):
        raise PairingAuditError("Les six inversions PF268967 V6 ont changé")
    witnesses = select_quantile_witnesses(
        {seed: margin for seed, margin in margins.items() if margin > 0.0}
    )
    selected = set(inversions) | set(witnesses)

    all_seed_rows: list[dict[str, Any]] = []
    for seed in holdout_v6.EXPECTED_HOLDOUT_SEEDS:
        high = traces[(HIGH_GROUP, seed)]
        low = traces[(LOW_GROUP, seed)]
        shared = set(high.lead_by_identity) & set(low.lead_by_identity)
        union = set(high.lead_by_identity) | set(low.lead_by_identity)
        low_longer = sum(
            low.lead_by_identity[identity] > high.lead_by_identity[identity]
            for identity in shared
        )
        equal = sum(
            low.lead_by_identity[identity] == high.lead_by_identity[identity]
            for identity in shared
        )
        low_shorter = len(shared) - low_longer - equal
        high_summary = summaries[(HIGH_GROUP, seed)]
        low_summary = summaries[(LOW_GROUP, seed)]
        role = "inversion" if seed in inversions else (
            "temoin_quantile" if seed in witnesses else "hors_echantillon_cible"
        )
        all_seed_rows.append(
            {
                "seed": seed,
                "role": role,
                "margin_pf268967_pp": margins[seed],
                "service_op93_pf268967_pct": _service_pct(
                    evidence[(high_candidate.key, seed)]
                ),
                "service_op80_pf268967_pct": _service_pct(
                    evidence[(low_candidate.key, seed)]
                ),
                "shipments_op93": high.shipment_count,
                "shipments_op80": low.shipment_count,
                "traceable_lane_day_draws_op93": high.lane_day_identity_count,
                "traceable_lane_day_draws_op80": low.lane_day_identity_count,
                "shared_lane_day_identities": len(shared),
                "union_lane_day_identities": len(union),
                "identity_jaccard_pct": 100.0 * len(shared) / len(union),
                "op93_only_lane_day_identities": len(
                    set(high.lead_by_identity) - set(low.lead_by_identity)
                ),
                "op80_only_lane_day_identities": len(
                    set(low.lead_by_identity) - set(high.lead_by_identity)
                ),
                "shared_op80_lead_strictly_longer": low_longer,
                "shared_equal_lead": equal,
                "shared_op80_lead_shorter": low_shorter,
                "reconstructed_draws_op93": high.reconstructed_draw_count,
                "reconstructed_draws_op80": low.reconstructed_draw_count,
                "warmup_global_rng_state_equal": (
                    high_summary.warmup_global_rng_state_sha256
                    == low_summary.warmup_global_rng_state_sha256
                ),
                "warmup_paired_invocation_hash_equal": (
                    high_summary.warmup_paired_invocations_sha256
                    == low_summary.warmup_paired_invocations_sha256
                ),
                "lot_trace_enabled_op93": high_summary.lot_trace_enabled,
                "lot_trace_enabled_op80": low_summary.lot_trace_enabled,
                "lot_count_op93": high_summary.lot_count,
                "lot_count_op80": low_summary.lot_count,
            }
        )

    selected_rows = [row for row in all_seed_rows if int(row["seed"]) in selected]
    selected_rows.sort(
        key=lambda row: (
            0 if row["role"] == "inversion" else 1,
            float(row["margin_pf268967_pp"]),
        )
    )
    total_mismatch = sum(
        trace.mismatch_count + trace.ambiguous_group_count for trace in traces.values()
    )
    reconstructed = sum(trace.reconstructed_draw_count for trace in traces.values())
    total_groups = sum(trace.lane_day_identity_count for trace in traces.values())
    shared_selected = sum(int(row["shared_lane_day_identities"]) for row in selected_rows)
    low_longer_selected = sum(
        int(row["shared_op80_lead_strictly_longer"]) for row in selected_rows
    )
    low_shorter_selected = sum(
        int(row["shared_op80_lead_shorter"]) for row in selected_rows
    )
    if total_mismatch or reconstructed != total_groups or low_shorter_selected:
        raise PairingAuditError("Une anomalie de reconstruction RNG est observée")

    seed_order = list(holdout_v6.EXPECTED_HOLDOUT_SEEDS)
    upper_ties = [
        seed
        for seed in seed_order
        if math.isclose(
            _service_pct(evidence[(reference_candidate.key, seed)]),
            _service_pct(evidence[(high_candidate.key, seed)]),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and math.isclose(
            _service_pct(evidence[(reference_candidate.key, seed)]),
            100.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ]
    all_seed_correlations = _correlations(all_seed_rows)
    unsigned = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "conclusion": CONCLUSION,
        "scope": {
            "source": "holdout_V6_officiel_termine",
            "engine_executed_by_this_audit": False,
            "source_artifacts_modified": False,
            "target_product": TARGET_PRODUCT,
            "target_lane_count": pf_lane_count,
            "audited_state_pair": [HIGH_GROUP, LOW_GROUP],
            "audited_seed_count": len(seed_order),
            "focused_seed_count": len(selected_rows),
        },
        "source_provenance": {
            "plan_dir": str(plan_dir),
            "run_dir": str(run_dir),
            "plan_signature": plan.manifest["plan_signature"],
            "holdout_signature": result["holdout_signature"],
            "holdout_result_sha256": sha256_file(run_dir / "holdout_result.json"),
            "holdout_evidence_signature_set_sha256": result[
                "holdout_evidence_signature_set_sha256"
            ],
            "audited_trace_signature_set_sha256": stable_sha256(
                sorted(trace_signature_rows)
            ),
            "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        },
        "holdout_context": {
            "official_status": result["status"],
            "official_accepted": result["accepted"],
            "official_joint_strict_order_count": result[
                "same_seed_joint_strict_order_count"
            ],
            "op93_strictly_above_op80_pf268967_count": sum(
                margin > 0.0 for margin in margins.values()
            ),
            "op100_equals_op93_at_100_pf268967_seeds": upper_ties,
            "op93_below_op80_pf268967_seeds": list(inversions),
        },
        "witness_contract": {
            "method": "six_quantiles_of_positive_pf268967_margin_sorted_by_margin_then_seed",
            "rounding": "python_round_index_i_times_n_minus_1_over_5",
            "selected_seeds": list(witnesses),
        },
        "reconstruction": {
            "method": (
                "signed_lane_and_graph_identity_plus_sha256_seeded_erlang_ordinal_0"
            ),
            "source_mode": SOURCE_MODE,
            "all_30_seed_state_traceable_lane_day_groups": total_groups,
            "all_30_seed_state_reconstructed_draws": reconstructed,
            "all_30_seed_state_mismatch_or_ambiguous_groups": total_mismatch,
            "all_60_summaries_common_random_numbers_true": all(
                summary.common_random_numbers for summary in summaries.values()
            ),
            "all_60_summaries_erlang_stochastic": all(
                summary.stochastic_lead_times
                and summary.lead_time_distribution_mode == "erlang"
                for summary in summaries.values()
            ),
            "warmup_global_rng_state_equal_seed_count": sum(
                row["warmup_global_rng_state_equal"] for row in all_seed_rows
            ),
            "warmup_paired_invocation_hash_equal_seed_count": sum(
                row["warmup_paired_invocation_hash_equal"] for row in all_seed_rows
            ),
            "focused_shared_lane_day_identities": shared_selected,
            "focused_shared_op80_lead_strictly_longer": low_longer_selected,
            "focused_shared_op80_lead_shorter": low_shorter_selected,
        },
        "all_seed_correlations": all_seed_correlations,
        "focused_seed_rows": selected_rows,
        "limitations": {
            "production_lots_observable": False,
            "reason": "lot_trace_enabled_false_and_lot_count_zero_in_all_signed_summaries",
            "shipment_records_are_not_production_lots": True,
            "causal_stock_mrp_production_path_fully_observable": False,
            "scientific_boundary": (
                "the_audit_excludes_a_simple_rng_shift_but_does_not_identify_the_full_"
                "downstream_cause_of_each_service_inversion"
            ),
        },
        "interpretation": {
            "rng_defect_status": "non_prouve",
            "observable_pairing_status": "conforme_sur_tous_les_tirages_tracables",
            "calendar_divergence_status": "observee_et_endogene_aux_etats",
            "service_inversion_attribution": (
                "interaction_dynamique_stocks_mrp_cadencement_a_investiguer_"
                "sans_attribution_au_rng"
            ),
            "engine_correction_recommended_before_v7": False,
        },
    }
    payload = {**unsigned, "audit_signature": stable_sha256(unsigned)}
    return payload, selected_rows


def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(CSV_FIELDS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    return stream.getvalue().encode("utf-8")


def _report_text(audit: Mapping[str, Any]) -> str:
    context = audit["holdout_context"]
    reconstruction = audit["reconstruction"]
    rows = audit["focused_seed_rows"]
    inversions = [row for row in rows if row["role"] == "inversion"]
    witnesses = [row for row in rows if row["role"] == "temoin_quantile"]

    def line(row: Mapping[str, Any]) -> str:
        return (
            f"| {row['seed']} | {row['margin_pf268967_pp']:.3f} | "
            f"{row['shipments_op93']} / {row['shipments_op80']} | "
            f"{row['traceable_lane_day_draws_op93']} / "
            f"{row['traceable_lane_day_draws_op80']} | "
            f"{row['shared_lane_day_identities']} | "
            f"{row['identity_jaccard_pct']:.1f} % |"
        )

    table_header = (
        "| Graine | Marge OP93-OP80 (pp) | Expéditions OP93 / OP80 | "
        "Tirages lane-jour OP93 / OP80 | Identités communes | Recouvrement |\n"
        "|---:|---:|---:|---:|---:|---:|"
    )
    inversion_lines = "\n".join(line(row) for row in inversions)
    witness_lines = "\n".join(line(row) for row in witnesses)
    return f"""# Audit du couplage aléatoire — holdout fournisseur V6

## Conclusion

**{CONCLUSION}**.

Les preuves signées ne montrent aucune dérive du générateur aléatoire entre
OP93 et OP80. Les {reconstruction['all_30_seed_state_reconstructed_draws']}
tirages de délai lane-jour observables ont été reconstruits exactement, sans
écart ni groupe ambigu. Sur les identités communes aux douze graines ciblées,
le délai OP80 est strictement plus long dans
{reconstruction['focused_shared_op80_lead_strictly_longer']} cas sur
{reconstruction['focused_shared_lane_day_identities']}, et jamais plus court.

La faible corrélation des taux de service vient principalement du fait que les
états génèrent des calendriers de commande différents. Une même graine couple
correctement un même fournisseur, un même flux et un même jour, mais elle ne
force pas deux systèmes dynamiques divergents à commander aux mêmes dates.

Le NO-GO V6 reste inchangé : {context['official_joint_strict_order_count']}/30
graines satisfont l'ordre strict simultané. Cet audit explique que ce résultat
ne doit pas être attribué à un bug RNG.

## Six inversions PF268967

{table_header}
{inversion_lines}

## Six témoins répartis sur les marges positives

{table_header}
{witness_lines}

## Ce qui a été vérifié

- plan, 90 preuves, résultat final et traces compactes V6 revalidés ;
- moteur non relancé et sources V4/V5/V6 non modifiées ;
- politique `common_random_numbers` active dans les 60 summaries OP93/OP80 ;
- tirages Erlang reproduits à partir de l'identité physique signée ;
- état du RNG global au cutover warmup identique sur 30/30 graines ;
- compteurs d'invocation différents sur 30/30, cohérents avec des calendriers
  endogènes différents.

## Limite lots

Les expéditions sont observables, mais pas les lots de production. Le traçage
lot était désactivé (`lot_trace_enabled=false`) et les summaries signés portent
`lot_count=0`. Il serait donc incorrect de prétendre expliquer chaque inversion
par un lot particulier avec cette campagne.

## Décision pour V7

Aucune correction du RNG n'est justifiée avant V7. Si l'explication causale
lot par lot devient un critère de validation, elle doit être ajoutée et testée
avant le gel V7 dans une campagne diagnostique distincte.

Signature de l'audit : `{audit['audit_signature']}`
"""


def _assert_no_source_overlap(output_dir: Path, sources: Sequence[Path]) -> None:
    output = output_dir.resolve()
    for source in sources:
        resolved = source.resolve()
        if output == resolved or output.is_relative_to(resolved) or resolved.is_relative_to(output):
            raise PairingAuditError("Le livrable ne doit pas chevaucher les sources V6")


def write_delivery(
    output_dir: Path,
    audit: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    source_dirs: Sequence[Path] = (),
) -> dict[str, Any]:
    """Écrit atomiquement un nouveau livrable et refuse tout écrasement."""

    output_dir = output_dir.resolve()
    if source_dirs:
        _assert_no_source_overlap(output_dir, source_dirs)
    if output_dir.exists():
        raise FileExistsError(f"Refus d'écraser le livrable: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    audit_bytes = _json_bytes(dict(audit))
    csv_bytes = _csv_bytes(rows)
    report_bytes = _report_text(audit).encode("utf-8")
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        contents = {
            AUDIT_JSON: audit_bytes,
            SEED_CSV: csv_bytes,
            REPORT_MD: report_bytes,
        }
        for name, content in contents.items():
            (temporary / name).write_bytes(content)
        unsigned_manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "conclusion": audit["conclusion"],
            "audit_signature": audit["audit_signature"],
            "audit_module_sha256": sha256_file(Path(__file__).resolve()),
            "files": [
                {
                    "relative_path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
                for name, content in sorted(contents.items())
            ],
        }
        manifest = {
            **unsigned_manifest,
            "manifest_signature": stable_sha256(unsigned_manifest),
        }
        (temporary / MANIFEST_JSON).write_bytes(_json_bytes(manifest))
        temporary.rename(output_dir)
    return validate_delivery(output_dir)


def validate_delivery(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    manifest = _read_json(output_dir / MANIFEST_JSON)
    _verify_signature(manifest, "manifest_signature", "manifest d'audit RNG")
    expected_names = {AUDIT_JSON, SEED_CSV, REPORT_MD, MANIFEST_JSON}
    actual_names = {path.name for path in output_dir.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise PairingAuditError("Inventaire du livrable RNG inattendu")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 3:
        raise PairingAuditError("Manifest du livrable RNG incomplet")
    for row in rows:
        if not isinstance(row, Mapping):
            raise PairingAuditError("Entrée de manifest invalide")
        path = output_dir / str(row.get("relative_path") or "")
        if (
            not path.is_file()
            or path.stat().st_size != int(row.get("size_bytes") or -1)
            or sha256_file(path) != row.get("sha256")
        ):
            raise PairingAuditError(f"Fichier livré invalide: {path.name}")
    audit = _read_json(output_dir / AUDIT_JSON)
    _verify_signature(audit, "audit_signature", "audit RNG")
    if (
        audit.get("schema_version") != AUDIT_SCHEMA_VERSION
        or audit.get("conclusion") != CONCLUSION
        or audit.get("audit_signature") != manifest.get("audit_signature")
    ):
        raise PairingAuditError("Contrat scientifique du livrable RNG invalide")
    return manifest


def run_audit(plan_dir: Path, run_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refus d'écraser le livrable: {output_dir}")
    audit, rows = build_audit_payload(plan_dir, run_dir)
    return write_delivery(
        output_dir,
        audit,
        rows,
        source_dirs=(plan_dir.resolve(), run_dir.resolve()),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="Construire le livrable officiel")
    audit.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_DIR)
    audit.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    audit.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    validate = subparsers.add_parser("validate", help="Revalider un livrable existant")
    validate.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "audit":
        manifest = run_audit(args.plan_dir, args.run_dir, args.output_dir)
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    manifest = validate_delivery(args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
