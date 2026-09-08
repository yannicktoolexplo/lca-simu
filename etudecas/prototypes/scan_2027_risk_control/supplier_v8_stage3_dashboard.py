#!/usr/bin/env python3
"""Native V8 registry reader for the additive Stage2 V3 delivery.

The statistical result directory deliberately remains V4-shaped because the
frozen finalizer owns the mature reducers.  The exposure registry does not: V8
selects one lane-specific 42-day window from the 90 signed V7 baseline traces,
requires all 30 paired seeds in all three states, and has no ``design_seed``.
This adapter validates that native contract before temporarily supplying only
the registry reduction hook expected by the mature dashboard reader.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v8 as campaign_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as traces_v7,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage3_dashboard.v1"
EXPECTED_STATES = tuple(campaign_v8.implementation_v4.OPERATING_POINT_IDS)
EXPECTED_SEEDS = tuple(traces_v7.CAMPAIGN_SEEDS)
EXPECTED_LANE_COUNT = 18
EXPECTED_TARGET_COUNT = 3 * 30 * EXPECTED_LANE_COUNT
EXPECTED_WINDOW_DAYS = campaign_v8.implementation_v4.INCIDENT_DISRUPTION_DAYS
FORBIDDEN_DESIGN_SEED_KEYS = frozenset(
    {
        "designseed",
        "designseedexcluded",
        "designseedinacceptancestatistics",
        "designseedincampaignstatistics",
    }
)

implementation_v4 = dashboard_v7.implementation_v4


class V8DashboardInputError(dashboard_v7.DashboardInputError):
    """A V8 source cannot support the requested client-facing reduction."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V8DashboardInputError(f"JSON V8 illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise V8DashboardInputError(f"Objet JSON V8 attendu : {path}")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_signature(payload: Mapping[str, Any], signature_key: str) -> str:
    unsigned = {key: value for key, value in payload.items() if key != signature_key}
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _normalise_key(value: Any) -> str:
    return "".join(
        character for character in str(value).casefold() if character.isalnum()
    )


def _assert_no_design_seed_aliases(payload: Any, *, label: str) -> None:
    if isinstance(payload, Mapping):
        forbidden = [
            str(key)
            for key in payload
            if _normalise_key(key) in FORBIDDEN_DESIGN_SEED_KEYS
        ]
        if forbidden:
            raise V8DashboardInputError(
                f"{label} contient un alias de graine de conception interdit : "
                + ", ".join(sorted(forbidden))
            )
        for key, value in payload.items():
            _assert_no_design_seed_aliases(value, label=f"{label}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _assert_no_design_seed_aliases(value, label=f"{label}[{index}]")


def _lane_identity(manifest: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    rows = manifest.get("lanes")
    if not isinstance(rows, list) or len(rows) != EXPECTED_LANE_COUNT:
        raise V8DashboardInputError("Le manifeste V8 ne porte pas ses 18 voies.")
    identities: dict[str, tuple[str, ...]] = {}
    fields = (
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
    )
    for row in rows:
        if not isinstance(row, Mapping):
            raise V8DashboardInputError("Identité de voie V8 invalide.")
        lane_id = str(row.get("lane_id") or "")
        identity = tuple(str(row.get(field) or "") for field in fields)
        if not lane_id or lane_id in identities or not all(identity):
            raise V8DashboardInputError("Identité de voie V8 absente ou dupliquée.")
        identities[lane_id] = identity
    return identities


def validate_registry_file(
    campaign_root: Path,
    registry_path: Path,
    *,
    replay_source_traces: bool = False,
) -> dict[str, Any]:
    """Validate a native V8 registry, optionally replaying its signed traces."""

    root = campaign_root.resolve()
    path = registry_path.resolve()
    manifest_path = root / "campaign_manifest.json"
    if not manifest_path.is_file() or not path.is_file():
        raise V8DashboardInputError("Manifeste ou registre d'exposition V8 absent.")
    manifest = _read_json(manifest_path)
    registry = _read_json(path)
    try:
        finalizer_v8.validate_frozen_implementation()
        finalizer_v8.implementation_v4._verify_manifest_signature(manifest)  # noqa: SLF001
    except Exception as exc:
        raise V8DashboardInputError("Le manifeste V8 signé est invalide.") from exc
    digest = _sha256_file(path)
    signature = str(registry.get("registry_signature") or "")
    if (
        digest != manifest.get("target_registry_sha256")
        or signature != manifest.get("target_registry_signature")
        or signature != _canonical_signature(registry, "registry_signature")
    ):
        raise V8DashboardInputError(
            "Le registre V8 ne correspond pas au registre signé du manifeste."
        )
    _assert_no_design_seed_aliases(registry, label="registre V8")
    identities = _lane_identity(manifest)
    try:
        if replay_source_traces:
            replay = finalizer_v8._validate_v8_registry(  # noqa: SLF001
                registry,
                manifest=manifest,
                lane_identity=identities,
            )
        else:
            replay = campaign_v8.validate_v8_target_registry_payload(
                registry,
                manifest=manifest,
                lanes=[SimpleNamespace(lane_id=lane) for lane in identities],
            )
    except Exception as exc:
        raise V8DashboardInputError(
            "Le registre V8 ne se reconstruit pas depuis les 90 traces normales signées."
        ) from exc
    if (
        replay.get("target_cell_count") != EXPECTED_TARGET_COUNT
        or replay.get("required_comparable_seed_count") != len(EXPECTED_SEEDS)
        or replay.get("target_selection_engine_runs") != 0
        or replay.get("incident_outcomes_used") is not False
    ):
        raise V8DashboardInputError("Le contrat d'exposition V8 reconstruit a changé.")
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "registry_schema_version": registry["schema_version"],
        "registry_signature": signature,
        "registry_sha256": digest,
        "target_selection_revision": registry["target_selection_revision"],
        "target_cell_count": registry["target_cell_count"],
        "lane_count": len(identities),
        "state_count": len(EXPECTED_STATES),
        "seed_count": len(EXPECTED_SEEDS),
        "required_comparable_seed_count": registry["required_comparable_seed_count"],
        "same_lane_window_across_all_states_and_seeds": True,
        "incident_outcomes_used": False,
        "target_selection_engine_runs": 0,
        "source_trace_replay_performed": replay_source_traces,
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _native_registry_summary(
    registry: Mapping[str, Any] | None,
    *,
    campaign_signature: str,
    engine_sha256: str,
    lane_ids: set[str],
    expected_registry_signature: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Reduce only a genuine 30×3×18 V8 registry; never emulate V4 fields."""

    if registry is None:
        raise V8DashboardInputError("Le dashboard V8 exige son registre d'exposition.")
    _assert_no_design_seed_aliases(registry, label="registre dashboard V8")
    signature = str(registry.get("registry_signature") or "")
    targets = registry.get("targets")
    lane_contracts = registry.get("lane_contracts")
    registered_lanes = registry.get("lanes")
    if (
        registry.get("schema_version") != campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION
        or registry.get("target_selection_revision")
        != campaign_v8.TARGET_SELECTION_REVISION
        or registry.get("campaign_signature") != campaign_signature
        or registry.get("engine_sha256") != engine_sha256
        or signature != expected_registry_signature
        or signature != _canonical_signature(registry, "registry_signature")
        or registry.get("states") != list(EXPECTED_STATES)
        or registry.get("seeds") != list(EXPECTED_SEEDS)
        or registry.get("campaign_seeds") != list(EXPECTED_SEEDS)
        or not isinstance(registered_lanes, list)
        or len(registered_lanes) != EXPECTED_LANE_COUNT
        or len(set(map(str, registered_lanes))) != EXPECTED_LANE_COUNT
        or set(map(str, registered_lanes)) != lane_ids
        or registry.get("target_cell_count") != EXPECTED_TARGET_COUNT
        or registry.get("required_comparable_seed_count") != len(EXPECTED_SEEDS)
        or registry.get("all_lane_windows_comparable") is not True
        or registry.get("campaign_exposure_gate_passed") is not True
        or registry.get("exposure_gate_failures") != []
        or registry.get("incident_outcomes_used") is not False
        or registry.get("incident_probes_started") is not False
        or registry.get("target_selection_engine_runs") != 0
        or registry.get("disruption_window_days") != EXPECTED_WINDOW_DAYS
        or not isinstance(targets, list)
        or len(targets) != EXPECTED_TARGET_COUNT
        or not isinstance(lane_contracts, list)
        or len(lane_contracts) != EXPECTED_LANE_COUNT
    ):
        raise V8DashboardInputError(
            "Le contrat natif du registre dashboard V8 a changé."
        )

    contracts: dict[str, Mapping[str, Any]] = {}
    for raw in lane_contracts:
        if not isinstance(raw, Mapping):
            raise V8DashboardInputError("Contrat de voie V8 non structuré.")
        lane = str(raw.get("lane_id") or "")
        start = raw.get("fixed_window_start_day")
        end = raw.get("fixed_window_end_day")
        if (
            lane not in lane_ids
            or lane in contracts
            or not isinstance(start, int)
            or not isinstance(end, int)
            or end != start + EXPECTED_WINDOW_DAYS - 1
            or raw.get("disruption_window_days") != EXPECTED_WINDOW_DAYS
            or raw.get("comparable_campaign_seed_count") != len(EXPECTED_SEEDS)
            or raw.get("required_comparable_seed_count") != len(EXPECTED_SEEDS)
            or raw.get("state_comparison_valid") is not True
            or raw.get("selected_start_is_earliest_eligible") is not True
            or raw.get("target_selection_engine_runs") != 0
            or raw.get("incident_outcomes_used") is not False
        ):
            raise V8DashboardInputError(f"Contrat natif de voie V8 invalide : {lane}")
        contracts[lane] = raw
    if set(contracts) != lane_ids:
        raise V8DashboardInputError("Les 18 contrats de voie V8 ne sont pas complets.")

    by_key: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    by_lane: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for raw in targets:
        if not isinstance(raw, Mapping):
            raise V8DashboardInputError("Cible V8 non structurée.")
        state = str(raw.get("operating_point_id") or "")
        lane = str(raw.get("lane_id") or "")
        try:
            seed = int(raw.get("seed"))
        except (TypeError, ValueError) as exc:
            raise V8DashboardInputError(
                "Identifiant de répétition V8 invalide."
            ) from exc
        key = (state, seed, lane)
        contract = contracts.get(lane)
        if (
            key in by_key
            or state not in EXPECTED_STATES
            or seed not in EXPECTED_SEEDS
            or contract is None
            or raw.get("target_window_start_day")
            != contract.get("fixed_window_start_day")
            or raw.get("target_window_end_day") != contract.get("fixed_window_end_day")
            or raw.get("target_window_days") != EXPECTED_WINDOW_DAYS
            or raw.get("required_comparable_seed_count") != len(EXPECTED_SEEDS)
            or raw.get("comparable_campaign_seed_count") != len(EXPECTED_SEEDS)
            or raw.get("state_comparison_valid") is not True
            or raw.get("seed_cross_state_exposure_comparable") is not True
        ):
            raise V8DashboardInputError(
                f"Cellule V8 absente, dupliquée ou incohérente : {key}"
            )
        by_key[key] = raw
        by_lane[lane].append(raw)
    expected_keys = {
        (state, seed, lane)
        for state in EXPECTED_STATES
        for seed in EXPECTED_SEEDS
        for lane in lane_ids
    }
    if set(by_key) != expected_keys:
        raise V8DashboardInputError("La matrice native V8 3 × 30 × 18 est incomplète.")

    summaries: dict[str, dict[str, Any]] = {}
    for lane in sorted(lane_ids):
        contract = contracts[lane]
        rows = by_lane[lane]
        state_summaries: dict[str, dict[str, Any]] = {}
        for state in EXPECTED_STATES:
            state_rows = [
                row for row in rows if str(row.get("operating_point_id")) == state
            ]
            quantities = [
                float(row["target_expected_delivered_qty"])
                for row in state_rows
                if row.get("target_expected_delivered_qty") is not None
            ]
            shipments = [
                float(row["target_shipment_count"])
                for row in state_rows
                if row.get("target_shipment_count") is not None
            ]
            state_summaries[state] = {
                "targetCount": len(state_rows),
                "quantityMedian": _median(quantities),
                "quantityMeaning": "normally_deliverable_quantity",
                "shipmentCountMedian": _median(shipments),
                "windowStartMin": contract["fixed_window_start_day"],
                "windowStartMax": contract["fixed_window_start_day"],
                "item": str(contract.get("item_id") or ""),
                "destination": str(contract.get("dst_node_id") or ""),
                "uom": next(
                    (str(row.get("target_uom") or "") for row in state_rows), ""
                ),
            }
        summaries[lane] = {
            "lane": lane,
            "comparisonValid": True,
            "validComparisonCount": len(EXPECTED_SEEDS),
            "comparisonCount": len(EXPECTED_SEEDS),
            "requiredComparisonCount": len(EXPECTED_SEEDS),
            "windowDays": EXPECTED_WINDOW_DAYS,
            "fixedWindowStartDay": contract["fixed_window_start_day"],
            "fixedWindowEndDay": contract["fixed_window_end_day"],
            "states": state_summaries,
        }
    return summaries, {
        "available": True,
        "schemaVersion": campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION,
        "selectionRevision": campaign_v8.TARGET_SELECTION_REVISION,
        "allLanesComparable": True,
        "validLaneCount": EXPECTED_LANE_COUNT,
        "laneCount": EXPECTED_LANE_COUNT,
        "windowDays": EXPECTED_WINDOW_DAYS,
        "targetCellCount": EXPECTED_TARGET_COUNT,
        "requiredComparableSeedCount": len(EXPECTED_SEEDS),
        "incidentOutcomesUsed": False,
        "targetSelectionEngineRuns": 0,
        "message": (
            "18/18 voies sont comparables sur les 30/30 répétitions et les trois "
            "niveaux. Pour chaque voie, une même fenêtre de 42 jours est choisie "
            "sur les traces normales signées, à partir de J180, sans utiliser les "
            "résultats d'incident et sans simulation supplémentaire. Ce choix ne "
            "mesure ni la fréquence ni la probabilité d'un incident fournisseur."
        ),
    }


@contextmanager
def _patched_native_registry_summary(
    expected_registry_signature: str,
) -> Iterator[None]:
    previous = implementation_v4._target_registry_summary  # noqa: SLF001

    def reducer(
        registry: Mapping[str, Any] | None,
        *,
        campaign_signature: str,
        engine_sha256: str,
        lane_ids: set[str],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        return _native_registry_summary(
            registry,
            campaign_signature=campaign_signature,
            engine_sha256=engine_sha256,
            lane_ids=lane_ids,
            expected_registry_signature=expected_registry_signature,
        )

    implementation_v4._target_registry_summary = reducer  # noqa: SLF001
    try:
        yield
    finally:
        implementation_v4._target_registry_summary = previous  # noqa: SLF001


def load_dashboard_data(
    *,
    campaign_root: Path,
    results_dir: Path,
    target_registry_path: Path | None = None,
) -> dict[str, Any]:
    """Load mature statistics with a native, replayed V8 registry contract."""

    root = campaign_root.resolve()
    results = results_dir.resolve()
    registry_path = (
        target_registry_path.resolve()
        if target_registry_path is not None
        else results / "cross_state_target_registry.json"
    )
    try:
        overlay = finalizer_v8.validate_v8_overlay(root, results)
    except Exception as exc:
        raise V8DashboardInputError("La surcouche finale V8 est invalide.") from exc
    # The signed V8 overlay binds the result package produced after the deep
    # source-trace replay.  Here the native reader independently verifies the
    # complete registry structure without repeating that expensive replay on
    # every Stage2 guard and delivery read.
    evidence = validate_registry_file(root, registry_path)
    overlay_registry = overlay.get("target_registry") or {}
    if (
        Path(str(overlay_registry.get("path") or "")).resolve() != registry_path
        or overlay_registry.get("sha256") != evidence["registry_sha256"]
        or overlay_registry.get("registry_signature") != evidence["registry_signature"]
    ):
        raise V8DashboardInputError(
            "Le dashboard ne lit pas la copie de registre liée à la surcouche V8."
        )
    with _patched_native_registry_summary(evidence["registry_signature"]):
        payload = dashboard_v7.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry_path,
        )
    target_status = payload.get("targetRegistry") or {}
    if (
        payload.get("repetitions") != len(EXPECTED_SEEDS)
        or payload.get("laneCount") != EXPECTED_LANE_COUNT
        or target_status.get("schemaVersion")
        != campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION
        or target_status.get("targetCellCount") != EXPECTED_TARGET_COUNT
        or target_status.get("incidentOutcomesUsed") is not False
        or target_status.get("targetSelectionEngineRuns") != 0
    ):
        raise V8DashboardInputError("La réduction dashboard V8 est incomplète.")
    output = dict(payload)
    output["schemaVersion"] = SCHEMA_VERSION
    output["nativeV8RegistryEvidence"] = evidence
    output["evidence"] = {
        **dict(payload.get("evidence") or {}),
        "nativeV8TargetRegistryValidated": True,
        "obsoleteDesignSeedProjectionUsed": False,
        "incidentOutcomesUsedForWindowSelection": False,
        "targetSelectionEngineRuns": 0,
    }
    return output


class NativeV8DashboardReader:
    """Object-shaped facade accepted by the mature Stage2 reducer."""

    def __init__(self, campaign_root: Path) -> None:
        self.campaign_root = campaign_root.resolve()
        self.last_evidence: dict[str, Any] | None = None

    def load_dashboard_data(
        self, *, results_dir: Path, target_registry_path: Path | None = None
    ) -> dict[str, Any]:
        payload = load_dashboard_data(
            campaign_root=self.campaign_root,
            results_dir=results_dir,
            target_registry_path=target_registry_path,
        )
        self.last_evidence = dict(payload["nativeV8RegistryEvidence"])
        return payload
