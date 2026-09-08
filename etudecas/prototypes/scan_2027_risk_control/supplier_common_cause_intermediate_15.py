#!/usr/bin/env python3
"""Build a scoped 15-simulation common-cause result from atomic evidence only.

The live V3 runner owns all simulations.  This reader never invokes the engine,
never opens a run-directory CSV and never mutates the runner directory.  It
publishes a separate, non-overwritable package only for the exact, predeclared
120-case prefix (two suppliers x four causes x fifteen paired simulations).
"""

from __future__ import annotations

import argparse
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_post_priority_extension_runner as runner,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_post_priority_extensions as planner,
)


SCHEMA_VERSION = "etudecas.supplier_common_cause.intermediate_15.v2"
RESULT_JSON = "resultat_causes_communes_15.json"
RESULT_HTML = "RESULTAT_CAUSES_COMMUNES_15.html"
MANIFEST_JSON = "manifest_causes_communes_15.json"
OUTPUT_FILES = (RESULT_JSON, RESULT_HTML, MANIFEST_JSON)
LEDGER_FILE = "execution_ledger.json"
EXTENSION = "multi_lane_supplier_common_cause"
EXPECTED_RUNNER_SIGNATURE = (
    "5749947757c04c3a42d9870a64cbb9aa2756456e34b999b78d706865977dfac8"
)
EXPECTED_OUTCOME_BUNDLE_SHA256 = (
    "92953a1a592054bbd2fa43ba3ea59761db8aadbd09710bd75f7e6ca33ab14295"
)
EXPECTED_SEEDS = tuple(range(340282, 340297))
EXPECTED_SIMULATION_COUNT = 15
EXPECTED_COMMON_CASE_COUNT = 120
EXPECTED_BASELINE_COUNT = 15
EXPECTED_SIMULATION_DAYS = 720
OUTCOME_SPEC_ID = "full_horizon_J0_J719"
SERVICE_EFFECT_TOLERANCE_POINTS = 1e-9
DELAY_EFFECT_TOLERANCE_DAYS = 1e-9
PRODUCTION_EFFECT_TOLERANCE_UNITS = 1e-6
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CASE_RE = re.compile(
    r"^multi_lane_supplier_common_cause::common__"
    r"(?P<supplier>sdc-vd[0-9a-z]+)__(?P<cause>[a-z_]+)::seed_(?P<seed>[0-9]+)$"
)


@dataclass(frozen=True)
class SupplierScope:
    supplier_id: str
    start_day: int
    end_day: int
    lanes: tuple[runner.LaneSpec, ...]
    products: tuple[str, ...]


SUPPLIER_SCOPES = (
    SupplierScope(
        supplier_id="SDC-VD0519670A",
        start_day=55,
        end_day=234,
        lanes=(
            runner.LaneSpec(
                "sdc_vd0519670a_001848_m_1810",
                "SDC-VD0519670A",
                "item:001848",
                "M-1810",
                "edge:SDC-VD0519670A_TO_M-1810_001848",
                "268091",
            ),
            runner.LaneSpec(
                "sdc_vd0519670a_029313_m_1810",
                "SDC-VD0519670A",
                "item:029313",
                "M-1810",
                "edge:SDC-VD0519670A_TO_M-1810_029313",
                "268091",
            ),
        ),
        products=("268091",),
    ),
    SupplierScope(
        supplier_id="SDC-VD0520132A",
        start_day=60,
        end_day=239,
        lanes=(
            runner.LaneSpec(
                "sdc_vd0520132a_038005_m_1430",
                "SDC-VD0520132A",
                "item:038005",
                "M-1430",
                "edge:SDC-VD0520132A_TO_M-1430_038005",
                "268967",
            ),
            runner.LaneSpec(
                "sdc_vd0520132a_049371_m_1810",
                "SDC-VD0520132A",
                "item:049371",
                "M-1810",
                "edge:SDC-VD0520132A_TO_M-1810_049371",
                "268091",
            ),
        ),
        products=("268091", "268967"),
    ),
)
SCOPE_BY_SUPPLIER = {scope.supplier_id: scope for scope in SUPPLIER_SCOPES}

CAUSE_LABELS = {
    "transport_delay": "Retard d'expédition ou de transport",
    "supply_availability": "Approvisionnement temporairement réduit",
    "quality_hold": "Attente de libération qualité",
    "quality_yield": "Quantité utilisable réduite après contrôle qualité",
}
CAUSE_ORDER = tuple(CAUSE_LABELS)


@dataclass(frozen=True)
class Readiness:
    ready: bool
    completed_expected_cases: int
    common_case_count_in_ledger: int
    expected_case_count: int
    completed_simulation_ids: tuple[int, ...]
    missing_case_count: int
    extra_case_count: int
    message: str


@dataclass(frozen=True)
class EvidenceSnapshot:
    runner_dir: Path
    ledger_sha256: str
    runner_signature: str
    ledger: Mapping[str, Any]
    common_keys: tuple[str, ...]
    baseline_keys: tuple[str, ...]


class NotReadyError(RuntimeError):
    """Raised when the exact 120-case prefix is not complete yet."""

    def __init__(self, readiness: Readiness):
        super().__init__(readiness.message)
        self.readiness = readiness


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé JSON dupliquée: {key}")
        result[key] = value
    return result


def _decode_json(raw: bytes, *, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"JSON invalide ({context}): {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu ({context}).")
    return payload


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _signature(payload: Mapping[str, Any]) -> str:
    compact = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(compact)


def _case_key(supplier_id: str, cause: str, seed: int) -> str:
    case_id = f"common__{supplier_id.lower()}__{cause}"
    return runner._case_key(EXTENSION, case_id, seed)


def _baseline_key(seed: int) -> str:
    case_id = f"baseline_metrics__seed_{seed}"
    return runner._case_key("baseline", case_id, seed)


def _expected_common_keys() -> set[str]:
    return {
        _case_key(scope.supplier_id, cause, seed)
        for scope in SUPPLIER_SCOPES
        for cause in CAUSE_ORDER
        for seed in EXPECTED_SEEDS
    }


def _expected_baseline_keys() -> set[str]:
    return {_baseline_key(seed) for seed in EXPECTED_SEEDS}


def _read_ledger_snapshot(runner_dir: Path) -> EvidenceSnapshot:
    root = runner_dir.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Dossier runner invalide: {root}")
    ledger_path = root / LEDGER_FILE
    if not ledger_path.is_file() or ledger_path.resolve() != ledger_path:
        raise FileNotFoundError("Registre atomique absent ou lien symbolique refusé.")
    raw = ledger_path.read_bytes()
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("Registre atomique anormalement volumineux.")
    ledger = _decode_json(raw, context=LEDGER_FILE)
    signature = str(ledger.get("runner_signature") or "")
    if signature != EXPECTED_RUNNER_SIGNATURE:
        raise ValueError("Signature du runner V3 inattendue.")
    case_files = ledger.get("case_files")
    case_hashes = ledger.get("case_file_sha256")
    if not isinstance(case_files, dict) or not isinstance(case_hashes, dict):
        raise ValueError("Inventaire des preuves absent du registre atomique.")
    if set(case_files) != set(case_hashes):
        raise ValueError(
            "Chemins et empreintes du registre ne portent pas les mêmes cas."
        )
    for case_key, digest in case_hashes.items():
        if not isinstance(case_key, str) or not _SHA256_RE.fullmatch(str(digest)):
            raise ValueError("Identifiant de cas ou empreinte SHA-256 invalide.")
    common_keys = tuple(
        sorted(key for key in case_files if key.startswith(f"{EXTENSION}::"))
    )
    baseline_keys = tuple(
        sorted(key for key in _expected_baseline_keys() if key in case_files)
    )
    return EvidenceSnapshot(
        runner_dir=root,
        ledger_sha256=_sha256_bytes(raw),
        runner_signature=signature,
        ledger=ledger,
        common_keys=common_keys,
        baseline_keys=baseline_keys,
    )


def _readiness(snapshot: EvidenceSnapshot) -> Readiness:
    expected = _expected_common_keys()
    actual = set(snapshot.common_keys)
    matching = actual & expected
    completed_seeds = tuple(
        seed
        for seed in EXPECTED_SEEDS
        if all(
            _case_key(scope.supplier_id, cause, seed) in matching
            for scope in SUPPLIER_SCOPES
            for cause in CAUSE_ORDER
        )
    )
    missing = expected - actual
    extra = actual - expected
    missing_baselines = _expected_baseline_keys() - set(snapshot.baseline_keys)
    ready = (
        actual == expected
        and len(actual) == EXPECTED_COMMON_CASE_COUNT
        and not missing_baselines
        and completed_seeds == EXPECTED_SEEDS
    )
    if ready:
        message = (
            "Les 120 scénarios attendus et leurs 15 références appariées "
            "sont inscrits dans le registre atomique."
        )
    else:
        message = (
            f"Résultat non publiable: {len(matching)}/"
            f"{EXPECTED_COMMON_CASE_COUNT} scénarios attendus finalisés; "
            f"{len(missing)} manquants, {len(extra)} supplémentaires et "
            f"{len(missing_baselines)} références manquantes."
        )
    return Readiness(
        ready=ready,
        completed_expected_cases=len(matching),
        common_case_count_in_ledger=len(actual),
        expected_case_count=EXPECTED_COMMON_CASE_COUNT,
        completed_simulation_ids=completed_seeds,
        missing_case_count=len(missing),
        extra_case_count=len(extra),
        message=message,
    )


def _load_evidence(
    snapshot: EvidenceSnapshot, case_key: str
) -> tuple[runner.CaseEvidence, str, str]:
    case_files = snapshot.ledger["case_files"]
    case_hashes = snapshot.ledger["case_file_sha256"]
    relative = str(case_files.get(case_key) or "")
    expected_hash = str(case_hashes.get(case_key) or "")
    if not relative or not _SHA256_RE.fullmatch(expected_hash):
        raise ValueError(f"Référence de preuve incomplète: {case_key}")
    path = runner._validated_ledger_evidence_path(
        output_dir=snapshot.runner_dir,
        case_key=case_key,
        relative_value=relative,
    )
    if path.suffix.lower() != ".json" or not path.is_file():
        raise FileNotFoundError(f"Preuve JSON finalisée absente: {case_key}")
    raw = path.read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError(f"Preuve JSON anormalement volumineuse: {case_key}")
    actual_hash = _sha256_bytes(raw)
    if actual_hash != expected_hash:
        raise ValueError(f"Empreinte de preuve invalide: {case_key}")
    payload = _decode_json(raw, context=case_key)
    if payload.get("case_key") != case_key:
        raise ValueError(f"Identité de preuve incohérente: {case_key}")
    if payload.get("valid") is not True or payload.get("status") != "executed":
        raise ValueError(f"Preuve non valide ou non exécutée: {case_key}")
    if payload.get("validation_errors") not in ([], None):
        raise ValueError(f"Erreurs de validation présentes: {case_key}")
    # Lot histories can make a traced baseline large, but they are not an
    # input to this aggregate.  Their enclosing evidence file is still read
    # and hash-checked in full; do not retain thousands of unused rows in RAM.
    validation_payload = dict(payload)
    validation_payload["lot_events"] = []
    validation_payload["lot_genealogy"] = []
    evidence = runner._evidence_from_dict(validation_payload)
    # Never let a runner validation fall back to a run-directory CSV.  The
    # finalized compact flow evidence must be sufficient on its own.
    evidence.run_dir = ""
    return evidence, relative, actual_hash


def _baseline_case(seed: int, *, lot_trace_required: bool = True) -> runner.PlannedCase:
    outcome_bundle = planner._full_horizon_outcome_bundle()
    bundle_sha = planner._canonical_signature(outcome_bundle)
    if bundle_sha != EXPECTED_OUTCOME_BUNDLE_SHA256:
        raise RuntimeError("Contrat de mesure V3 modifié; publication refusée.")
    case_id = f"baseline_metrics__seed_{seed}"
    return runner.PlannedCase(
        case_key=_baseline_key(seed),
        extension="baseline",
        case_id=case_id,
        seed=seed,
        pairing_block_id=f"metrics_seed_{seed}",
        paired_baseline_case_id="",
        mechanism_key="baseline",
        risk_type="",
        mechanism_value=1.0,
        mechanism_unit="ratio",
        start_day=0,
        end_day=0,
        lot_trace_required=lot_trace_required,
        lanes=(),
        products=runner.PRODUCTS,
        action="new_run_required",
        simulation_days=EXPECTED_SIMULATION_DAYS,
        outcome_spec_id="baseline_outcome_bundle",
        outcome_start_day=0,
        outcome_end_day=EXPECTED_SIMULATION_DAYS - 1,
        outcome_day_count=EXPECTED_SIMULATION_DAYS,
        outcome_bundle_sha256=bundle_sha,
        outcome_specs=tuple(outcome_bundle["outcome_specs"]),
    )


def _stress_case(
    scope: SupplierScope,
    cause: str,
    seed: int,
    *,
    lot_trace_required: bool = True,
) -> runner.PlannedCase:
    mechanism = runner.network.MECHANISM_BY_KEY[cause]
    case_id = f"common__{scope.supplier_id.lower()}__{cause}"
    return runner.PlannedCase(
        case_key=_case_key(scope.supplier_id, cause, seed),
        extension=EXTENSION,
        case_id=case_id,
        seed=seed,
        pairing_block_id=f"metrics_seed_{seed}",
        paired_baseline_case_id=f"baseline_metrics__seed_{seed}",
        mechanism_key=cause,
        risk_type=mechanism.risk_type,
        mechanism_value=float(mechanism.values[-1]),
        mechanism_unit=mechanism.unit,
        start_day=scope.start_day,
        end_day=scope.end_day,
        lot_trace_required=lot_trace_required,
        lanes=scope.lanes,
        products=scope.products,
        action="new_run_required",
        simulation_days=EXPECTED_SIMULATION_DAYS,
        outcome_spec_id=OUTCOME_SPEC_ID,
        outcome_start_day=0,
        outcome_end_day=EXPECTED_SIMULATION_DAYS - 1,
        outcome_day_count=EXPECTED_SIMULATION_DAYS,
        outcome_bundle_sha256=EXPECTED_OUTCOME_BUNDLE_SHA256,
    )


def _minimal_graph_from_finalized_flows(
    case: runner.PlannedCase, evidence: runner.CaseEvidence
) -> dict[str, Any]:
    expected_lanes = {(lane.chain_id, *lane.key): lane for lane in case.lanes}
    observed: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in evidence.flow_metrics:
        key = (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        if key in observed:
            raise ValueError(f"Flux finalisé dupliqué: {case.case_key}/{key}")
        observed[key] = row
    if set(observed) != set(expected_lanes):
        raise ValueError(f"Périmètre de flux finalisé incomplet: {case.case_key}")
    states: list[dict[str, str]] = []
    for key, row in sorted(observed.items()):
        unit = str(row.get("uom") or "")
        pulled = runner._to_float(row.get("pulled_qty"), math.nan)
        shipped = runner._to_float(row.get("shipped_qty"), math.nan)
        if not unit or not all(
            math.isfinite(value) and value >= 0.0 for value in (pulled, shipped)
        ):
            raise ValueError(f"Flux finalisé invalide: {case.case_key}/{key}")
        states.append({"item_id": key[2], "uom": unit})
    return {
        "nodes": [
            {
                "id": case.lanes[0].supplier_id,
                "inventory": {"states": states},
            }
        ],
        "edges": [],
    }


def _assert_compact_baseline_flows(
    case: runner.PlannedCase, baseline: runner.CaseEvidence
) -> None:
    expected = {(lane.chain_id, *lane.key) for lane in case.lanes}
    matching = {
        (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        for row in baseline.flow_metrics
        if runner._to_int(row.get("baseline_window_start_day"), -1) == case.start_day
        and runner._to_int(row.get("baseline_window_end_day"), -1) == case.end_day
    }
    if matching != expected:
        raise ValueError(
            f"Flux compacts de référence insuffisants; lecture CSV interdite: {case.case_key}"
        )


def _paired_flow_rows(
    case: runner.PlannedCase,
    evidence: runner.CaseEvidence,
    baseline: runner.CaseEvidence,
) -> list[dict[str, Any]]:
    """Return exact per-lane reference/stress quantities for the incident window."""

    expected = {(lane.chain_id, *lane.key): lane for lane in case.lanes}
    baseline_by_key: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in baseline.flow_metrics:
        if (
            runner._to_int(row.get("baseline_window_start_day"), -1) != case.start_day
            or runner._to_int(row.get("baseline_window_end_day"), -1) != case.end_day
        ):
            continue
        key = (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        if key in baseline_by_key:
            raise ValueError(f"Flux de référence dupliqué: {case.case_key}/{key}")
        baseline_by_key[key] = row
    stress_by_key: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in evidence.flow_metrics:
        key = (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        if key in stress_by_key:
            raise ValueError(f"Flux du scénario dupliqué: {case.case_key}/{key}")
        stress_by_key[key] = row
    if set(baseline_by_key) != set(expected) or set(stress_by_key) != set(expected):
        raise ValueError(f"Comparaison physique des flux incomplète: {case.case_key}")

    rows: list[dict[str, Any]] = []
    for key, lane in sorted(expected.items()):
        reference = baseline_by_key[key]
        stress = stress_by_key[key]
        unit = str(reference.get("uom") or "")
        if not unit or str(stress.get("uom") or "") != unit:
            raise ValueError(f"Unité de flux non appariée: {case.case_key}/{key}")
        baseline_pulled = _finite(
            reference.get("pulled_qty"), context=f"flux tiré référence/{case.case_key}"
        )
        stress_pulled = _finite(
            stress.get("pulled_qty"), context=f"flux tiré scénario/{case.case_key}"
        )
        baseline_shipped = _finite(
            reference.get("shipped_qty"),
            context=f"flux expédié référence/{case.case_key}",
        )
        stress_shipped = _finite(
            stress.get("shipped_qty"),
            context=f"flux expédié scénario/{case.case_key}",
        )
        if min(baseline_pulled, stress_pulled, baseline_shipped, stress_shipped) < 0.0:
            raise ValueError(f"Quantité de flux négative: {case.case_key}/{key}")
        if baseline_shipped <= 0.0:
            raise ValueError(f"Flux de référence non positif: {case.case_key}/{key}")
        rows.append(
            {
                "supplier_id": lane.supplier_id,
                "cause": case.mechanism_key,
                "seed": case.seed,
                "chain_id": lane.chain_id,
                "item_id": lane.item_id.removeprefix("item:"),
                "destination": lane.dst_node_id,
                "uom": unit,
                "baseline_pulled_qty": baseline_pulled,
                "stress_pulled_qty": stress_pulled,
                "baseline_shipped_qty": baseline_shipped,
                "stress_shipped_qty": stress_shipped,
                "shipped_delta_percentage": (
                    100.0 * (stress_shipped - baseline_shipped) / baseline_shipped
                ),
            }
        )
    return rows


def _validate_stress_identity(
    case: runner.PlannedCase, evidence: runner.CaseEvidence
) -> None:
    if evidence.case_key != case.case_key or evidence.seed != case.seed:
        raise ValueError(f"Identité/numéro de simulation incohérent: {case.case_key}")
    if evidence.reused_source_case:
        raise ValueError(
            f"Réutilisation inattendue pour un cas commun: {case.case_key}"
        )
    if evidence.simulation_days != EXPECTED_SIMULATION_DAYS:
        raise ValueError(f"Horizon inattendu: {case.case_key}")
    expected_rows = runner._canonical_rows(
        [runner._normalized_risk_row(row) for row in runner._risk_rows(case)]
    )
    actual_rows = runner._canonical_rows(evidence.loaded_event_rows)
    if actual_rows != expected_rows:
        raise ValueError(
            f"Hypothèse fournisseur différente du contrat V3: {case.case_key}"
        )
    products = tuple(
        sorted(
            str(row.get("product_id") or "") for row in evidence.local_product_metrics
        )
    )
    if products != tuple(sorted(case.products)):
        raise ValueError(f"Produits concernés incohérents: {case.case_key}")


def _finite(value: Any, *, context: str) -> float:
    result = runner._to_float(value, math.nan)
    if not math.isfinite(result):
        raise ValueError(f"Mesure non finie: {context}")
    return result


def _hypothesis_label(cause: str) -> str:
    mechanism = runner.network.MECHANISM_BY_KEY[cause]
    value = float(mechanism.values[-1])
    if mechanism.unit == "jours_ajoutes":
        return f"+{value:.0f} jours"
    if mechanism.unit == "part_disponible":
        return f"{100.0 * value:.0f} % disponible"
    if mechanism.unit == "part_utilisable":
        return f"{100.0 * value:.0f} % utilisable"
    raise ValueError(f"Unité d'hypothèse non présentable: {mechanism.unit}")


def _aggregate(values: Sequence[float]) -> dict[str, float]:
    if len(values) != EXPECTED_SIMULATION_COUNT or not all(
        math.isfinite(value) for value in values
    ):
        raise ValueError("Série incomplète ou non finie avant agrégation.")
    return {
        "moyenne": statistics.fmean(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def _has_downstream_effect(row: Mapping[str, Any]) -> bool:
    return (
        abs(float(row["service_delta_percentage_points"]))
        > SERVICE_EFFECT_TOLERANCE_POINTS
        or abs(float(row["delay_equivalent_days"])) > DELAY_EFFECT_TOLERANCE_DAYS
        or abs(float(row["released_production_gap_units"]))
        > PRODUCTION_EFFECT_TOLERANCE_UNITS
    )


def _configured_perturbation(scope: SupplierScope, cause: str) -> dict[str, Any]:
    return {
        "cause": CAUSE_LABELS[cause],
        "hypothese": _hypothesis_label(cause),
        "fenetre_debut_jour": scope.start_day,
        "fenetre_fin_jour": scope.end_day,
        "fenetre": f"J{scope.start_day}–J{scope.end_day}",
        "nombre_flux": len(scope.lanes),
        "flux": [
            {
                "composant": lane.item_id.removeprefix("item:"),
                "destination": lane.dst_node_id,
            }
            for lane in scope.lanes
        ],
    }


def _physical_effect_reading(cause: str) -> str:
    if cause == "transport_delay":
        return (
            "La quantité expédiée peut rester identique : l'effet physique configuré "
            "est le décalage de 120 jours des expéditions concernées."
        )
    if cause == "quality_hold":
        return (
            "La quantité expédiée peut rester identique : le moteur ajoute 90 jours "
            "avant utilisation aux nouvelles expéditions concernées."
        )
    if cause == "quality_yield":
        return (
            "Le réglage de 80 % porte sur la quantité utilisable après contrôle; la "
            "comparaison des flux montre la quantité effectivement obtenue dans le modèle."
        )
    if cause == "supply_availability":
        return (
            "Le réglage de 50 % limite le stock ou la capacité accessibles dans le "
            "moteur. Il ne signifie pas que 50 % de la quantité sera livrée : les "
            "tailles de lot et le besoin peuvent conduire à 0 %, 50 % ou 100 %."
        )
    raise ValueError(f"Cause physique non présentable: {cause}")


def _physical_effect_payload(
    *,
    scope: SupplierScope,
    cause: str,
    flow_rows: Sequence[Mapping[str, Any]],
    applied_seed_count: int,
) -> dict[str, Any]:
    if applied_seed_count != EXPECTED_SIMULATION_COUNT:
        raise ValueError(
            f"Perturbation non appliquée dans les 15 simulations: "
            f"{scope.supplier_id}/{cause}"
        )
    flows: list[dict[str, Any]] = []
    for lane in scope.lanes:
        group = [
            row
            for row in flow_rows
            if row["supplier_id"] == scope.supplier_id
            and row["cause"] == cause
            and row["chain_id"] == lane.chain_id
        ]
        if tuple(sorted(int(row["seed"]) for row in group)) != EXPECTED_SEEDS:
            raise ValueError(
                f"Comparaison de flux incomplète: "
                f"{scope.supplier_id}/{cause}/{lane.chain_id}"
            )
        units = {str(row["uom"]) for row in group}
        if len(units) != 1:
            raise ValueError(
                f"Unité de flux variable: {scope.supplier_id}/{cause}/{lane.chain_id}"
            )
        flows.append(
            {
                "composant": lane.item_id.removeprefix("item:"),
                "destination": lane.dst_node_id,
                "unite": next(iter(units)),
                "quantite_expediee_reference": _aggregate(
                    [float(row["baseline_shipped_qty"]) for row in group]
                ),
                "quantite_expediee_scenario": _aggregate(
                    [float(row["stress_shipped_qty"]) for row in group]
                ),
                "ecart_quantite_expediee_pourcent": _aggregate(
                    [float(row["shipped_delta_percentage"]) for row in group]
                ),
            }
        )
    return {
        "simulations_avec_perturbation_appliquee": applied_seed_count,
        "sur_simulations": EXPECTED_SIMULATION_COUNT,
        "lecture": _physical_effect_reading(cause),
        "flux": flows,
    }


def _validated_result(
    snapshot: EvidenceSnapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    readiness = _readiness(snapshot)
    if not readiness.ready:
        raise NotReadyError(readiness)

    evidence_sources: dict[str, dict[str, str]] = {}
    baselines: dict[int, runner.CaseEvidence] = {}
    for seed in EXPECTED_SEEDS:
        key = _baseline_key(seed)
        evidence, relative, digest = _load_evidence(snapshot, key)
        baseline_case = _baseline_case(
            seed,
            lot_trace_required=evidence.resolved_lot_trace_enabled,
        )
        if evidence.case_key != key or evidence.seed != seed:
            raise ValueError(f"Référence appariée incohérente: {key}")
        runner._validate_baseline_evidence(baseline_case, evidence)
        baselines[seed] = evidence
        evidence_sources[key] = {"relative_path": relative, "sha256": digest}

    raw_rows: list[dict[str, Any]] = []
    raw_flow_rows: list[dict[str, Any]] = []
    applied_seeds: dict[tuple[str, str], set[int]] = {
        (scope.supplier_id, cause): set()
        for scope in SUPPLIER_SCOPES
        for cause in CAUSE_ORDER
    }
    for scope in SUPPLIER_SCOPES:
        for cause in CAUSE_ORDER:
            for seed in EXPECTED_SEEDS:
                case = _stress_case(
                    scope,
                    cause,
                    seed,
                    lot_trace_required=baselines[seed].resolved_lot_trace_enabled,
                )
                evidence, relative, digest = _load_evidence(snapshot, case.case_key)
                baseline = baselines[seed]
                _validate_stress_identity(case, evidence)
                _assert_compact_baseline_flows(case, baseline)
                minimal_graph = _minimal_graph_from_finalized_flows(case, evidence)
                # Reuse the runner's full evidence and pairing validator.  With
                # run_dir cleared and compact flows prechecked, this cannot open CSV.
                runner._validate_stress_evidence(
                    case, evidence, baseline, minimal_graph
                )
                expected_events = {
                    str(row["event_id"]) for row in runner._risk_rows(case)
                }
                if set(evidence.applied_event_ids) != expected_events:
                    raise ValueError(
                        f"Les deux perturbations de flux ne sont pas appliquées: "
                        f"{case.case_key}"
                    )
                applied_seeds[(scope.supplier_id, cause)].add(seed)
                raw_flow_rows.extend(_paired_flow_rows(case, evidence, baseline))
                rows = runner._product_rows(
                    case=case,
                    evidence=evidence,
                    baseline=baseline,
                )
                if {str(row["product_id"]) for row in rows} != set(scope.products):
                    raise ValueError(f"Résultat produit incomplet: {case.case_key}")
                for row in rows:
                    raw_rows.append(
                        {
                            "supplier_id": scope.supplier_id,
                            "cause": cause,
                            "product_id": str(row["product_id"]),
                            "seed": seed,
                            "service_delta_percentage_points": _finite(
                                row["delta_on_due_percentage_points"],
                                context=f"service/{case.case_key}",
                            ),
                            "delay_equivalent_days": _finite(
                                row["delta_backlog_days_per_demand_unit"],
                                context=f"retard/{case.case_key}",
                            ),
                            "released_production_gap_units": -_finite(
                                row["delta_released_qty"],
                                context=f"production/{case.case_key}",
                            ),
                        }
                    )
                evidence_sources[case.case_key] = {
                    "relative_path": relative,
                    "sha256": digest,
                }

    physical_by_group = {
        (scope.supplier_id, cause): _physical_effect_payload(
            scope=scope,
            cause=cause,
            flow_rows=raw_flow_rows,
            applied_seed_count=len(applied_seeds[(scope.supplier_id, cause)]),
        )
        for scope in SUPPLIER_SCOPES
        for cause in CAUSE_ORDER
    }

    result_rows: list[dict[str, Any]] = []
    for scope in SUPPLIER_SCOPES:
        for cause in CAUSE_ORDER:
            for product in scope.products:
                group = [
                    row
                    for row in raw_rows
                    if row["supplier_id"] == scope.supplier_id
                    and row["cause"] == cause
                    and row["product_id"] == product
                ]
                if tuple(sorted(int(row["seed"]) for row in group)) != EXPECTED_SEEDS:
                    raise ValueError(
                        f"15 simulations appariées absentes: {scope.supplier_id}/{cause}/{product}"
                    )
                service = _aggregate(
                    [float(row["service_delta_percentage_points"]) for row in group]
                )
                delay = _aggregate(
                    [float(row["delay_equivalent_days"]) for row in group]
                )
                production = _aggregate(
                    [float(row["released_production_gap_units"]) for row in group]
                )
                downstream_count = sum(_has_downstream_effect(row) for row in group)
                downstream = {
                    "produit": product,
                    "simulations_avec_effet_aval": downstream_count,
                    "sur_simulations": EXPECTED_SIMULATION_COUNT,
                    "ce_nombre_est_une_probabilite": False,
                    "ecart_service_points": service,
                    "retard_cumule_equivalent_jours": delay,
                    "ecart_production_liberee_cumulee_j719_un": production,
                }
                result_rows.append(
                    {
                        "fournisseur": scope.supplier_id,
                        "cause": cause,
                        "cause_libelle": CAUSE_LABELS[cause],
                        "hypothese": _hypothesis_label(cause),
                        "fenetre": f"J{scope.start_day}–J{scope.end_day}",
                        "produit": product,
                        "nombre_simulations": EXPECTED_SIMULATION_COUNT,
                        "perturbation_configuree": _configured_perturbation(
                            scope, cause
                        ),
                        "effet_physique_obtenu_dans_le_modele": physical_by_group[
                            (scope.supplier_id, cause)
                        ],
                        "consequence_aval": downstream,
                        "simulations_avec_effet_aval": downstream_count,
                        "ecart_service_points": service,
                        "retard_cumule_equivalent_jours": delay,
                        "ecart_production_liberee_cumulee_j719_un": production,
                    }
                )

    expected_row_count = sum(len(scope.products) for scope in SUPPLIER_SCOPES) * len(
        CAUSE_ORDER
    )
    expected_flow_row_count = (
        len(SUPPLIER_SCOPES) * len(CAUSE_ORDER) * EXPECTED_SIMULATION_COUNT * 2
    )
    if (
        len(result_rows) != expected_row_count
        or len(raw_rows) != 180
        or len(raw_flow_rows) != expected_flow_row_count
    ):
        raise ValueError("Matrice fournisseur/cause/produit incomplète.")
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "statut": "résultat intermédiaire descriptif complet sur 15 simulations",
        "perimetre": {
            "simulations": list(EXPECTED_SEEDS),
            "nombre_simulations": EXPECTED_SIMULATION_COUNT,
            "nombre_hypotheses_metier": len(SUPPLIER_SCOPES) * len(CAUSE_ORDER),
            "nombre_executions_simulees": EXPECTED_COMMON_CASE_COUNT,
            "fournisseurs": [scope.supplier_id for scope in SUPPLIER_SCOPES],
            "causes": list(CAUSE_ORDER),
            "horizon_jours": EXPECTED_SIMULATION_DAYS,
        },
        "lecture_metier": {
            "trois_niveaux": (
                "Chaque ligne sépare la perturbation configurée, son effet physique "
                "effectivement obtenu sur les flux du modèle, puis sa conséquence aval."
            ),
            "service": (
                "Indicateur simulé en volume des unités servies le jour demandé; ce "
                "n'est pas un OTIF de commandes. L'écart en points vaut scénario moins "
                "fonctionnement de référence sur J0–J719."
            ),
            "retard_cumule": (
                "Écart scénario moins référence du volume restant à servir, cumulé jour "
                "après jour puis ramené au volume demandé; il s'exprime en jours "
                "équivalents et non en délai d'une commande."
            ),
            "ecart_production_liberee_cumulee_j719": (
                "Production libérée cumulée dans la référence moins celle du scénario "
                "sur J0–J719. Zéro signifie seulement que le total est identique à J719; "
                "des décalages temporaires de production restent possibles."
            ),
            "simulations_avec_effet_aval": (
                "Nombre de simulations dans lesquelles au moins un des trois indicateurs "
                "aval diffère de la référence. Ce nombre décrit une sensibilité "
                "conditionnelle du modèle, pas une probabilité d'incident."
            ),
        },
        "limites": [
            (
                "Les résultats décrivent les conséquences si l'hypothèse se produit; "
                "ils n'estiment pas sa fréquence d'occurrence chez le fournisseur."
            ),
            (
                "La plage minimum-maximum décrit les 15 simulations appariées; ce n'est "
                "pas un intervalle de confiance."
            ),
            (
                "Aucun ordre de priorité ni recommandation opérationnelle n'est déduit "
                "de ce résultat intermédiaire."
            ),
            (
                "L'estimation de la vraisemblance future exigera les historiques de "
                "commandes, dates promises, réceptions et contrôles qualité."
            ),
            (
                "Une disponibilité configurée à 50 % limite le stock ou la capacité "
                "accessibles dans le moteur; elle ne signifie pas que 50 % des quantités "
                "seront effectivement livrées. Les tailles de lot peuvent rendre la "
                "réponse non proportionnelle."
            ),
            (
                "L'attente qualité est simplifiée en un délai ajouté aux nouvelles "
                "expéditions concernées. Le modèle ne représente ici ni quarantaine "
                "native, ni capacité laboratoire, ni libération par ressources."
            ),
            (
                "Cette vue ne fournit aucune preuve détaillée sur les lots et ne démontre "
                "ni cascade, ni amplification, ni interaction entre les deux flux."
            ),
            (
                "Un zéro signifie seulement aucun écart sur les trois indicateurs aval "
                "agrégés. Il n'exclut pas une variation temporaire de stock, de production "
                "ou de coût."
            ),
        ],
        "resultats": result_rows,
    }
    return result, evidence_sources


def evaluate_readiness(runner_dir: Path) -> tuple[Readiness, dict[str, Any] | None]:
    snapshot = _read_ledger_snapshot(runner_dir)
    readiness = _readiness(snapshot)
    if not readiness.ready:
        return readiness, None
    result, _sources = _validated_result(snapshot)
    return readiness, result


def _format_number(value: float, digits: int) -> str:
    rendered = f"{value:,.{digits}f}"
    return rendered.replace(",", " ").replace(".", ",")


def _range_cell(values: Mapping[str, float], *, digits: int, suffix: str) -> str:
    mean = _format_number(float(values["moyenne"]), digits)
    low = _format_number(float(values["minimum"]), digits)
    high = _format_number(float(values["maximum"]), digits)
    return f"<strong>{mean}{suffix}</strong><small>plage {low} à {high}{suffix}</small>"


def _flow_effect_html(physical: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for flow in physical["flux"]:
        reference = flow["quantite_expediee_reference"]
        stress = flow["quantite_expediee_scenario"]
        delta = flow["ecart_quantite_expediee_pourcent"]
        unit = html.escape(str(flow["unite"]))
        lines.append(
            "<li>"
            f"<strong>{html.escape(str(flow['composant']))} → "
            f"{html.escape(str(flow['destination']))}</strong> "
            f"{_format_number(float(reference['moyenne']), 0)} → "
            f"{_format_number(float(stress['moyenne']), 0)} {unit} "
            f"({_format_number(float(delta['moyenne']), 1)} %)"
            "</li>"
        )
    return (
        "<strong>15/15 simulations : perturbation appliquée</strong>"
        f"<ul class=flows>{''.join(lines)}</ul>"
        f"<small>{html.escape(str(physical['lecture']))}</small>"
    )


def _render_html(result: Mapping[str, Any]) -> str:
    rows = []
    for row in result["resultats"]:
        configured = row["perturbation_configuree"]
        consequence = row["consequence_aval"]
        affected = int(consequence["simulations_avec_effet_aval"])
        impact_class = "effect" if affected else "absorbed"
        flow_scope = " · ".join(
            f"{lane['composant']} → {lane['destination']}"
            for lane in configured["flux"]
        )
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(str(row['fournisseur']))}</strong><small>"
            f"Fenêtre {html.escape(str(configured['fenetre']))}</small></td>"
            f"<td><strong>{html.escape(str(row['cause_libelle']))}</strong><small>"
            f"Hypothèse {html.escape(str(row['hypothese']))}</small><small>"
            f"{html.escape(flow_scope)}</small></td>"
            f"<td>{_flow_effect_html(row['effet_physique_obtenu_dans_le_modele'])}</td>"
            f"<td><span class='impact {impact_class}'>{affected}/15 simulations "
            "avec effet aval</span>"
            f"<strong class=product>Produit {html.escape(str(row['produit']))}</strong>"
            "<div class=metric><span>Service simulé</span>"
            f"{_range_cell(consequence['ecart_service_points'], digits=2, suffix=' pt')}</div>"
            "<div class=metric><span>Retard cumulé équivalent</span>"
            f"{_range_cell(consequence['retard_cumule_equivalent_jours'], digits=3, suffix=' j')}</div>"
            "<div class=metric><span>Écart de production libérée cumulé à J719</span>"
            f"{_range_cell(consequence['ecart_production_liberee_cumulee_j719_un'], digits=0, suffix=' UN')}</div>"
            "<small>Ce nombre sur 15 décrit la sensibilité du modèle, pas la "
            "probabilité de l'incident.</small></td>"
            "</tr>"
        )
    return (
        """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Perturbations communes fournisseurs — 15 simulations</title>
<style>
:root{color-scheme:light;--ink:#14213d;--muted:#526079;--line:#d9e2ef;--bg:#f4f7fb;--card:#fff;--accent:#155eef;--warn:#fff4df;--good:#e8f7ef;--bad:#ffe9e6}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}main{max-width:1600px;margin:auto;padding:28px}h1{font-size:clamp(1.65rem,3vw,2.5rem);line-height:1.12;margin:.2rem 0 .6rem}h2{margin:1.6rem 0 .65rem}.lead{font-size:1.08rem;color:var(--muted);max-width:90ch}.tag{display:inline-block;padding:.3rem .65rem;border-radius:999px;background:#e8f0ff;color:#1247a8;font-weight:700}.grid,.scope,.definitions{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:22px 0}.scope{grid-template-columns:repeat(2,1fr)}.card,.notice,.table-wrap,.scope article{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}.card strong{display:block;font-size:1.45rem}.card span,small{display:block;color:var(--muted)}.scope strong{font-size:1.06rem}.notice{background:var(--warn);margin:18px 0}.table-wrap{overflow:auto;padding:0}table{border-collapse:collapse;width:100%;min-width:1280px}th,td{padding:14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;background:#edf3fc;font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}td:nth-child(1){width:14%}td:nth-child(2){width:20%}td:nth-child(3){width:31%}td:nth-child(4){width:35%}td strong{white-space:normal}td small{font-size:.78rem;margin-top:.25rem}.flows{margin:.45rem 0;padding-left:1.1rem}.flows li{margin:.25rem 0}.impact{display:inline-block;padding:.25rem .55rem;border-radius:999px;font-weight:750;font-size:.82rem}.impact.effect{background:var(--bad);color:#9b2417}.impact.absorbed{background:var(--good);color:#12643a}.product{display:block;margin:.6rem 0}.metric{display:grid;grid-template-columns:minmax(175px,1fr) minmax(150px,auto);gap:.25rem .8rem;padding:.35rem 0;border-top:1px dashed var(--line)}.metric>span{color:var(--muted)}.metric strong{text-align:right}.metric small{grid-column:2;text-align:right}.definitions article{background:var(--card);border-left:4px solid var(--accent);border-radius:10px;padding:16px}.definitions h3{margin:0 0 .35rem;font-size:1rem}.definitions p{margin:0;color:var(--muted)}footer{color:var(--muted);margin-top:20px;font-size:.88rem}@media(max-width:850px){main{padding:16px}.grid,.scope,.definitions{grid-template-columns:1fr}.metric{grid-template-columns:1fr}.metric strong,.metric small{text-align:left}.metric small{grid-column:1}}
</style></head><body><main>
<span class="tag">Résultat intermédiaire vérifié</span>
<h1>Deux flux d'un même fournisseur soumis à la même perturbation</h1>
<p class="lead">Cette vue sépare ce qui est imposé au modèle, ce qui se produit réellement sur les flux, puis la conséquence mesurée en aval. Chaque valeur centrale est la moyenne de 15 simulations comparées à leur fonctionnement de référence; la plage montre le minimum et le maximum obtenus dans les simulations.</p>
<section class="grid"><article class="card"><strong>2 fournisseurs</strong><span>deux flux modélisés pendant une même période</span></article><article class="card"><strong>4 hypothèses</strong><span>retard, disponibilité, attente qualité, rendement qualité</span></article><article class="card"><strong>15 simulations</strong><span>mêmes aléas internes pour l'incident et sa référence</span></article></section>
<section class="scope"><article><strong>SDC-VD0519670A · J55–J234</strong><span>001848 → M-1810 et 029313 → M-1810 · produit 268091</span></article><article><strong>SDC-VD0520132A · J60–J239</strong><span>038005 → M-1430 et 049371 → M-1810 · produits 268967 et 268091</span></article></section>
<aside class="notice"><strong>Lecture essentielle.</strong> Nous estimons ici les conséquences <em>si</em> l'hypothèse se produit. Nous n'estimons pas encore sa fréquence d'occurrence chez le fournisseur. Cette étape demandera les historiques de commandes, dates promises, réceptions et contrôles qualité. Aucun ordre de priorité ni recommandation n'est produit ici.</aside>
<section class="table-wrap"><table><thead><tr><th>Fournisseur et période</th><th>1 · Perturbation configurée</th><th>2 · Effet physique obtenu sur les flux du modèle</th><th>3 · Conséquence aval mesurée</th></tr></thead><tbody>"""
        + "".join(rows)
        + """</tbody></table></section>
<aside class="notice"><strong>Un résultat nul ne veut pas dire « aucun risque ».</strong> Il signifie seulement qu'aucun écart n'apparaît sur le service client agrégé, le retard client cumulé et le total de production libérée à J719. Une variation temporaire de stock, de production ou de coût peut subsister.</aside>
<section class="definitions"><article><h3>Service simulé en volume</h3><p>Approximation des unités servies le jour demandé sur J0–J719. Ce n'est pas un OTIF calculé commande par commande.</p></article><article><h3>Retard cumulé équivalent</h3><p>Volume restant à servir cumulé jour après jour puis divisé par la demande. Ce n'est pas le retard calendaire d'une commande.</p></article><article><h3>Écart de production libérée à J719</h3><p>Total de la référence moins total du scénario. Zéro autorise encore des baisses puis des rattrapages temporaires.</p></article><article><h3>Disponibilité à 50 %</h3><p>Elle limite le stock ou la capacité accessibles; elle ne garantit pas 50 % livré, notamment à cause des tailles de lot.</p></article><article><h3>Qualité simplifiée</h3><p>L'attente ajoute 90 jours aux nouvelles expéditions concernées. Aucun laboratoire, stock de quarantaine natif ou processus de libération n'est simulé ici.</p></article><article><h3>Lots et cascades</h3><p>Cette vue ne constitue ni une preuve sur les lots, ni une mesure d'amplification ou d'interaction entre les deux flux.</p></article></section>
<footer>Horizon J0 à J719. UN signifie unités. La plage minimum–maximum décrit seulement ces 15 simulations comparées; elle ne constitue ni un intervalle de confiance, ni un pire cas industriel.</footer>
</main></body></html>
"""
    )


def _write_package(
    *,
    output_dir: Path,
    snapshot: EvidenceSnapshot,
    result: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> Path:
    output = output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Dossier de sortie déjà présent: {output}")
    if output == snapshot.runner_dir or snapshot.runner_dir in output.parents:
        raise ValueError("Le résultat intermédiaire doit rester extérieur au runner.")
    parent = output.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"Dossier parent de sortie absent: {parent}")
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=parent))
    try:
        result_bytes = _canonical_json_bytes(result)
        html_bytes = _render_html(result).encode("utf-8")
        (staging / RESULT_JSON).write_bytes(result_bytes)
        (staging / RESULT_HTML).write_bytes(html_bytes)
        asset_manifest = {
            RESULT_JSON: {
                "sha256": _sha256_bytes(result_bytes),
                "size_bytes": len(result_bytes),
            },
            RESULT_HTML: {
                "sha256": _sha256_bytes(html_bytes),
                "size_bytes": len(html_bytes),
            },
        }
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete_scoped_intermediate_15_v2",
            "runner_signature": snapshot.runner_signature,
            "execution_ledger_sha256_at_snapshot": snapshot.ledger_sha256,
            "exact_common_case_count": EXPECTED_COMMON_CASE_COUNT,
            "paired_baseline_count": EXPECTED_BASELINE_COUNT,
            "simulation_ids": list(EXPECTED_SEEDS),
            "source_evidence": dict(sorted(sources.items())),
            "files": asset_manifest,
            "guards": {
                "exact_120_of_120_pass": True,
                "all_evidence_hashes_pass": True,
                "all_evidence_valid_true": True,
                "runner_pairing_validation_pass": True,
                "runner_csv_read_allowed": False,
                "engine_invocation_allowed": False,
                "frequency_occurrence_estimated": False,
                "priority_order_released": False,
                "operational_recommendation_released": False,
                "availability_is_delivered_fraction": False,
                "native_quality_quarantine_modeled": False,
                "lot_or_cascade_proof_released": False,
                "downstream_zero_scope_limited_to_three_aggregates": True,
            },
        }
        manifest["manifest_signature"] = _signature(manifest)
        (staging / MANIFEST_JSON).write_bytes(_canonical_json_bytes(manifest))
        if {path.name for path in staging.iterdir()} != set(OUTPUT_FILES):
            raise RuntimeError("Inventaire de paquet intermédiaire inattendu.")
        os.replace(staging, output)
    except Exception:
        if staging.exists() and staging.parent == parent:
            shutil.rmtree(staging)
        raise
    validate_package(output)
    return output


def build_package(*, runner_dir: Path, output_dir: Path) -> Path:
    snapshot = _read_ledger_snapshot(runner_dir)
    result, sources = _validated_result(snapshot)
    return _write_package(
        output_dir=output_dir,
        snapshot=snapshot,
        result=result,
        sources=sources,
    )


def validate_package(output_dir: Path) -> dict[str, Any]:
    output = output_dir.resolve(strict=True)
    if not output.is_dir():
        raise NotADirectoryError(output)
    names = {path.name for path in output.iterdir()}
    if names != set(OUTPUT_FILES):
        raise ValueError("Inventaire du paquet intermédiaire non exact.")
    manifest = _decode_json(
        (output / MANIFEST_JSON).read_bytes(), context=MANIFEST_JSON
    )
    supplied_signature = str(manifest.get("manifest_signature") or "")
    unsigned = dict(manifest)
    unsigned.pop("manifest_signature", None)
    if supplied_signature != _signature(unsigned):
        raise ValueError("Signature du manifeste intermédiaire invalide.")
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "complete_scoped_intermediate_15_v2"
        or manifest.get("runner_signature") != EXPECTED_RUNNER_SIGNATURE
        or manifest.get("exact_common_case_count") != EXPECTED_COMMON_CASE_COUNT
        or manifest.get("paired_baseline_count") != EXPECTED_BASELINE_COUNT
        or manifest.get("simulation_ids") != list(EXPECTED_SEEDS)
    ):
        raise ValueError("Contrat du manifeste intermédiaire invalide.")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {RESULT_JSON, RESULT_HTML}:
        raise ValueError("Inventaire signé des fichiers invalide.")
    for name, expected in files.items():
        raw = (output / name).read_bytes()
        if _sha256_bytes(raw) != str(expected.get("sha256") or "") or len(
            raw
        ) != expected.get("size_bytes"):
            raise ValueError(f"Fichier intermédiaire altéré: {name}")
    result = _decode_json((output / RESULT_JSON).read_bytes(), context=RESULT_JSON)
    rows = result.get("resultats")
    expected_groups = {
        (scope.supplier_id, cause, product)
        for scope in SUPPLIER_SCOPES
        for cause in CAUSE_ORDER
        for product in scope.products
    }
    if (
        not isinstance(rows, list)
        or {
            (row.get("fournisseur"), row.get("cause"), row.get("produit"))
            for row in rows
        }
        != expected_groups
    ):
        raise ValueError("Matrice de résultats intermédiaires invalide.")
    if any(row.get("nombre_simulations") != EXPECTED_SIMULATION_COUNT for row in rows):
        raise ValueError("Nombre de simulations agrégées invalide.")
    for row in rows:
        scope = SCOPE_BY_SUPPLIER[str(row.get("fournisseur") or "")]
        configured = row.get("perturbation_configuree") or {}
        if (
            configured.get("fenetre") != f"J{scope.start_day}–J{scope.end_day}"
            or configured.get("fenetre_debut_jour") != scope.start_day
            or configured.get("fenetre_fin_jour") != scope.end_day
            or configured.get("nombre_flux") != len(scope.lanes)
        ):
            raise ValueError("Périmètre de perturbation présenté invalide.")
        physical = row.get("effet_physique_obtenu_dans_le_modele") or {}
        if (
            physical.get("simulations_avec_perturbation_appliquee")
            != EXPECTED_SIMULATION_COUNT
            or physical.get("sur_simulations") != EXPECTED_SIMULATION_COUNT
            or len(physical.get("flux") or []) != len(scope.lanes)
        ):
            raise ValueError("Preuve physique présentée incomplète.")
        downstream = row.get("consequence_aval") or {}
        affected = downstream.get("simulations_avec_effet_aval")
        if (
            not isinstance(affected, int)
            or not 0 <= affected <= EXPECTED_SIMULATION_COUNT
            or downstream.get("sur_simulations") != EXPECTED_SIMULATION_COUNT
            or downstream.get("ce_nombre_est_une_probabilite") is not False
            or "ecart_production_liberee_cumulee_j719_un" not in downstream
            or "production_a_rattraper_un" in row
        ):
            raise ValueError("Conséquence aval présentée invalide.")
    guards = manifest.get("guards") or {}
    if guards != {
        "exact_120_of_120_pass": True,
        "all_evidence_hashes_pass": True,
        "all_evidence_valid_true": True,
        "runner_pairing_validation_pass": True,
        "runner_csv_read_allowed": False,
        "engine_invocation_allowed": False,
        "frequency_occurrence_estimated": False,
        "priority_order_released": False,
        "operational_recommendation_released": False,
        "availability_is_delivered_fraction": False,
        "native_quality_quarantine_modeled": False,
        "lot_or_cascade_proof_released": False,
        "downstream_zero_scope_limited_to_three_aggregates": True,
    }:
        raise ValueError("Gardes du résultat intermédiaire invalides.")
    sources = manifest.get("source_evidence")
    if not isinstance(sources, dict) or len(sources) != 135:
        raise ValueError("Inventaire des preuves sources incomplet.")
    page = (output / RESULT_HTML).read_text(encoding="utf-8")
    required_phrases = (
        "J55–J234",
        "J60–J239",
        "Perturbation configurée",
        "Effet physique obtenu sur les flux du modèle",
        "Conséquence aval mesurée",
        "ne garantit pas 50 % livré",
        "Aucun laboratoire, stock de quarantaine natif",
        "ni une preuve sur les lots",
        "maximum obtenus dans les simulations",
    )
    if (
        any(phrase not in page for phrase in required_phrases)
        or "maximum observé" in page
    ):
        raise ValueError("Vocabulaire métier de la page intermédiaire invalide.")
    return manifest


def _readiness_payload(readiness: Readiness) -> dict[str, Any]:
    return {
        "prêt": readiness.ready,
        "scénarios_attendus_finalisés": readiness.completed_expected_cases,
        "scénarios_attendus": readiness.expected_case_count,
        "scénarios_communs_dans_registre": readiness.common_case_count_in_ledger,
        "simulations_entièrement_finalisées": list(readiness.completed_simulation_ids),
        "cas_manquants": readiness.missing_case_count,
        "cas_supplémentaires": readiness.extra_case_count,
        "message": readiness.message,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("readiness", "build", "validate"), required=True
    )
    parser.add_argument("--runner-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode in {"readiness", "build"} and args.runner_dir is None:
        raise SystemExit("--runner-dir est requis pour readiness/build")
    if args.mode in {"build", "validate"} and args.output_dir is None:
        raise SystemExit("--output-dir est requis pour build/validate")
    if args.mode == "readiness":
        readiness, _result = evaluate_readiness(args.runner_dir)
        print(json.dumps(_readiness_payload(readiness), ensure_ascii=False, indent=2))
        return 0
    if args.mode == "validate":
        manifest = validate_package(args.output_dir)
        print(
            json.dumps(
                {
                    "valide": True,
                    "statut": manifest["status"],
                    "dossier": str(args.output_dir.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    try:
        output = build_package(runner_dir=args.runner_dir, output_dir=args.output_dir)
    except NotReadyError as error:
        print(
            json.dumps(
                _readiness_payload(error.readiness), ensure_ascii=False, indent=2
            )
        )
        return 3
    print(
        json.dumps(
            {"créé": True, "dossier": str(output), "page": str(output / RESULT_HTML)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
