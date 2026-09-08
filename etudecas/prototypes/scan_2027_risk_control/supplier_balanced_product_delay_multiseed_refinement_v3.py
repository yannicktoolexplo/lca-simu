#!/usr/bin/env python3
"""Minimal, additive V3 refinement after the signed V2 NO-GO.

V3 revalidates the complete V1/V2 provenance chain and all 65 V2 evidence
records, then adds exactly three preregistered op80 candidates on the five
calibration seeds.  Holdout seeds remain sealed and unread.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v2 as v2,
)

SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v3"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selection"
POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selected_operating_points"
SELECTION_PASS_STATUS = "five_seed_loo_screen_v3_passed_pending_holdout"
SELECTION_FAIL_STATUS = "five_seed_loo_screen_v3_failed_no_holdout"
POINTS_STATUS = "selected_on_five_seed_refinement_v3_pending_30_seed_holdout"
DESIGN_SEEDS = v2.DESIGN_SEEDS
CALIBRATION_SEEDS = v2.CALIBRATION_SEEDS
HOLDOUT_SEEDS = v2.HOLDOUT_SEEDS
SERVICE_WINDOW = dict(v2.SERVICE_WINDOW)
TARGETS = dict(v2.TARGETS)
ARTIFACT_PARENT = v2.ARTIFACT_PARENT
DEFAULT_V1_PLAN = v2.DEFAULT_SOURCE_PLAN
DEFAULT_V1_RUN = v2.DEFAULT_SOURCE_RUN
DEFAULT_V2_PLAN = v2.DEFAULT_PLAN_OUTPUT
DEFAULT_V2_RUN = ARTIFACT_PARENT / "supplier_delay_multiseed_refinement_run_20260904_v2"
DEFAULT_PLAN_OUTPUT = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_refinement_plan_20260904_v3"
)
DEFAULT_RUN_OUTPUT = (
    ARTIFACT_PARENT / "supplier_delay_multiseed_refinement_run_20260904_v3"
)
INTERPRETATION = v2.INTERPRETATION
RawExecutor = Callable[
    [coarse.Candidate, coarse.ValidatedPlan, Path, int], dict[str, Any]
]


@dataclass(frozen=True)
class CandidateSpec:
    key: str
    offset_days_268091: float
    offset_days_268967: float
    target_group: str
    evidence_mode: str

    @property
    def candidate(self) -> coarse.Candidate:
        return coarse.Candidate(
            candidate_id=coarse._candidate_id(
                self.offset_days_268091, self.offset_days_268967
            ),
            offset_days_268091=self.offset_days_268091,
            offset_days_268967=self.offset_days_268967,
        )


OP80_REFINEMENT_WAVE = (
    CandidateSpec("op80_refine_v3_16p5_94", 16.5, 94.0, "op_80", "execute"),
    CandidateSpec("op80_refine_v3_16p5_94p5", 16.5, 94.5, "op_80", "execute"),
    CandidateSpec("op80_refine_v3_16p5_95", 16.5, 95.0, "op_80", "execute"),
)
FIXED_REFERENCE_KEY = "op100_reference"
FIXED_OP93_KEY = "op93_refine_7_81"


@dataclass(frozen=True)
class RefinementPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    source_plan: v2.RefinementPlan
    specs: tuple[CandidateSpec, ...]
    inventory: dict[str, dict[str, Any]]


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    coarse.campaign_core.write_json_atomic(path, payload)


def _sha(path: Path) -> str:
    return coarse.protocol.sha256_file(path)


def _stable(payload: Any) -> str:
    return coarse.protocol.stable_sha256(payload)


def _case_key(key: str, seed: int) -> str:
    return f"{key}__seed_{seed}"


def _evidence_path(directory: Path, case_key: str) -> Path:
    digest = hashlib.sha256(case_key.encode()).hexdigest()[:24]
    return directory / "evidence" / f"{digest}.json"


def _assert_disjoint(path: Path, *sources: Path) -> None:
    resolved = path.resolve()
    for source in sources:
        source = source.resolve()
        if (
            resolved == source
            or resolved.is_relative_to(source)
            or source.is_relative_to(resolved)
        ):
            raise ValueError(f"V3 destination overlaps immutable source: {source}")


def _v2_source(
    plan_dir: Path, run_dir: Path
) -> tuple[v2.RefinementPlan, dict[str, dict[str, Any]], dict[str, Any]]:
    plan = v2.validate_plan(plan_dir.resolve())
    run_dir = run_dir.resolve()
    if _read(run_dir / "run_manifest.json") != v2._run_manifest(plan):
        raise ValueError("V2 run manifest is not canonical")
    progress = _read(run_dir / "progress.json")
    if (
        progress.get("schema_version") != f"{v2.SCHEMA_VERSION}.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("status") != "complete"
        or progress.get("completed_case_count") != 65
        or progress.get("expected_case_count") != 65
        or progress.get("holdout_case_count") != 0
        or progress.get("error") not in (None, "")
    ):
        raise ValueError("V2 run is not a complete 65-proof NO-GO source")
    if (run_dir / ".multiseed_refinement_v2.lock").exists():
        raise ValueError("V2 run is locked")
    evidence = v2._load_evidence(plan, run_dir)
    if len(evidence) != 65:
        raise ValueError("V2 source must contain exactly 65 valid proofs")
    expected_selection, selected = v2._select(plan, evidence)
    actual_selection = _read(run_dir / "selection.json")
    if actual_selection != expected_selection or selected is not None:
        raise ValueError("V2 NO-GO is not reproducible from its evidence")
    if (
        actual_selection.get("status") != "five_seed_loo_screen_failed_no_holdout"
        or actual_selection.get("eligible_pairs") != []
        or actual_selection.get("selected_pair") is not None
        or actual_selection.get("holdout_launch_permitted") is not False
        or actual_selection.get("fallback_required") is not True
        or actual_selection.get("holdout_cases_read") != 0
        or (run_dir / "selected_operating_points.json").exists()
    ):
        raise ValueError("V2 source is not the required signed NO-GO")
    v1_source = v2._validated_v1_source(
        Path(plan.manifest["source"]["v1_plan_dir"]),
        Path(plan.manifest["source"]["v1_run_dir"]),
    )
    hashes = {
        "v1_plan_manifest_sha256": _sha(
            v1_source.plan.plan_dir / "calibration_plan.json"
        ),
        "v1_run_manifest_sha256": _sha(v1_source.run_dir / "run_manifest.json"),
        "v1_selection_sha256": _sha(v1_source.run_dir / "selection.json"),
        "v1_selected_points_sha256": _sha(
            v1_source.run_dir / "selected_operating_points.json"
        ),
        "v2_plan_manifest_sha256": _sha(plan.plan_dir / "refinement_plan.json"),
        "v2_run_manifest_sha256": _sha(run_dir / "run_manifest.json"),
        "v2_progress_sha256": _sha(run_dir / "progress.json"),
        "v2_selection_sha256": _sha(run_dir / "selection.json"),
        "v2_evidence_sha256": {
            key: _sha(_evidence_path(run_dir, key)) for key in sorted(evidence)
        },
    }
    return plan, evidence, hashes


def _spec_payload(spec: CandidateSpec) -> dict[str, Any]:
    return {**asdict(spec), "candidate_id": spec.candidate.candidate_id}


def _selection_contract() -> dict[str, Any]:
    contract = dict(v2._selection_contract())
    contract.update(
        {
            "fixed_op100_candidate_key": FIXED_REFERENCE_KEY,
            "fixed_op93_candidate_key": FIXED_OP93_KEY,
            "eligible_op80_candidate_keys": [s.key for s in OP80_REFINEMENT_WAVE],
            "v2_core_criteria_and_tie_break_unchanged": True,
        }
    )
    return contract


def _holdout_contract() -> dict[str, Any]:
    contract = dict(v2._holdout_contract())
    contract["selected_output_status"] = POINTS_STATUS
    return contract


def _manifest_unsigned(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "status",
            "interpretation",
            "source",
            "source_hashes",
            "cohorts",
            "candidates",
            "candidate_design",
            "inventory",
            "cases",
            "expected_case_count",
            "new_case_count",
            "reused_case_count",
            "selection_contract",
            "holdout_contract",
            "execution_contract",
        )
    }


def _reused_specs(plan: v2.RefinementPlan) -> tuple[CandidateSpec, ...]:
    return tuple(
        CandidateSpec(
            spec.key,
            spec.offset_days_268091,
            spec.offset_days_268967,
            spec.target_group,
            "reuse_v2",
        )
        for spec in plan.specs
    )


def prepare_plan(
    output_dir: Path,
    *,
    v1_plan_dir: Path = DEFAULT_V1_PLAN,
    v1_run_dir: Path = DEFAULT_V1_RUN,
    v2_plan_dir: Path = DEFAULT_V2_PLAN,
    v2_run_dir: Path = DEFAULT_V2_RUN,
) -> Path:
    output_dir = output_dir.resolve()
    _assert_disjoint(
        output_dir,
        v1_plan_dir,
        v1_run_dir,
        v2_plan_dir,
        v2_run_dir,
    )
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite V3 plan: {output_dir}")
    source, source_evidence, artifact_hashes = _v2_source(v2_plan_dir, v2_run_dir)
    if (
        Path(source.manifest["source"]["v1_plan_dir"]).resolve()
        != v1_plan_dir.resolve()
        or Path(source.manifest["source"]["v1_run_dir"]).resolve()
        != v1_run_dir.resolve()
    ):
        raise ValueError("V2 does not reference the requested V1 source")
    specs = _reused_specs(source) + OP80_REFINEMENT_WAVE
    if len(specs) != 16 or len({s.key for s in specs}) != 16:
        raise ValueError("V3 design must contain 13 reused and 3 new candidates")
    output_dir.mkdir(parents=True)
    base = v2._base_plan(source.source_plan)
    source_graph = coarse._read_json(base.source_graph)
    inventory: dict[str, dict[str, Any]] = {}
    for spec in specs:
        graph, changes = coarse.apply_product_delays(
            source_graph,
            base.lanes_by_product,
            offset_days_268091=spec.offset_days_268091,
            offset_days_268967=spec.offset_days_268967,
        )
        graph_path = output_dir / "graphs" / f"{spec.key}.json"
        _write(graph_path, graph)
        inventory[spec.key] = {
            "graph_path": graph_path.relative_to(output_dir).as_posix(),
            "graph_sha256": _sha(graph_path),
            "changes": changes,
        }
    proposal = {
        "schema_version": f"{SCHEMA_VERSION}.candidate_design",
        "status": "pre_registered_before_v3_execution",
        "candidates": [_spec_payload(s) for s in OP80_REFINEMENT_WAVE],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_cases_read": 0,
    }
    proposal["artifact_signature"] = _stable(proposal)
    _write(output_dir / "op80_refinement_candidates.json", proposal)
    cases = [
        {
            "case_key": _case_key(spec.key, seed),
            "candidate_key": spec.key,
            "seed": seed,
            "evidence_mode": spec.evidence_mode,
        }
        for spec in specs
        for seed in CALIBRATION_SEEDS
    ]
    source_hashes = dict(source.manifest["source_hashes"])
    source_hashes.update(
        {
            "v2_driver_sha256": _sha(Path(v2.__file__)),
            "v3_driver_sha256": _sha(Path(__file__)),
        }
    )
    manifest: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": "frozen_before_v3_execution",
        "interpretation": INTERPRETATION,
        "source": {
            "v1_plan_dir": str(v1_plan_dir.resolve()),
            "v1_run_dir": str(v1_run_dir.resolve()),
            "v2_plan_dir": str(source.plan_dir),
            "v2_run_dir": str(v2_run_dir.resolve()),
            "v2_plan_signature": source.manifest["plan_signature"],
            "v2_no_go_status": "five_seed_loo_screen_failed_no_holdout",
            "artifact_hashes": artifact_hashes,
        },
        "source_hashes": source_hashes,
        "cohorts": source.manifest["cohorts"],
        "candidates": [_spec_payload(s) for s in specs],
        "candidate_design": {
            "fixed_op100_candidate_key": FIXED_REFERENCE_KEY,
            "fixed_op93_candidate_key": FIXED_OP93_KEY,
            "new_op80_candidates": [_spec_payload(s) for s in OP80_REFINEMENT_WAVE],
            "proposal_file": "op80_refinement_candidates.json",
            "proposal_sha256": _sha(output_dir / "op80_refinement_candidates.json"),
        },
        "inventory": inventory,
        "cases": cases,
        "expected_case_count": 80,
        "new_case_count": 15,
        "reused_case_count": 65,
        "selection_contract": _selection_contract(),
        "holdout_contract": _holdout_contract(),
        "execution_contract": {
            **source.manifest["execution_contract"],
            "maximum_workers": 2,
            "v2_evidence_is_read_only": True,
        },
    }
    manifest["plan_signature"] = _stable(_manifest_unsigned(manifest))
    _write(output_dir / "refinement_plan.json", manifest)
    # Prove all source evidence was read before the frozen plan was emitted.
    if len(source_evidence) != 65:
        raise AssertionError("unreachable")
    return output_dir


def validate_plan(plan_dir: Path) -> RefinementPlan:
    plan_dir = plan_dir.resolve()
    manifest = _read(plan_dir / "refinement_plan.json")
    signature = manifest.get("plan_signature")
    if manifest.get("schema_version") != PLAN_SCHEMA_VERSION or signature != _stable(
        _manifest_unsigned(manifest)
    ):
        raise ValueError("Invalid V3 plan signature")
    if set(manifest) != set(_manifest_unsigned(manifest)) | {"plan_signature"}:
        raise ValueError("Unexpected field in signed V3 plan")
    source = manifest.get("source", {})
    _assert_disjoint(
        plan_dir,
        Path(source["v1_plan_dir"]),
        Path(source["v1_run_dir"]),
        Path(source["v2_plan_dir"]),
        Path(source["v2_run_dir"]),
    )
    v2_plan, evidence, hashes = _v2_source(
        Path(source["v2_plan_dir"]), Path(source["v2_run_dir"])
    )
    expected_source = {
        "v1_plan_dir": str(Path(v2_plan.manifest["source"]["v1_plan_dir"]).resolve()),
        "v1_run_dir": str(Path(v2_plan.manifest["source"]["v1_run_dir"]).resolve()),
        "v2_plan_dir": str(v2_plan.plan_dir),
        "v2_run_dir": str(Path(source["v2_run_dir"]).resolve()),
        "v2_plan_signature": v2_plan.manifest["plan_signature"],
        "v2_no_go_status": "five_seed_loo_screen_failed_no_holdout",
        "artifact_hashes": hashes,
    }
    if (
        source != expected_source
        or len(evidence) != 65
        or Path(source["v1_plan_dir"]).resolve()
        != Path(v2_plan.manifest["source"]["v1_plan_dir"]).resolve()
        or Path(source["v1_run_dir"]).resolve()
        != Path(v2_plan.manifest["source"]["v1_run_dir"]).resolve()
    ):
        raise ValueError("V3 source provenance changed")
    expected_source_hashes = dict(v2_plan.manifest["source_hashes"])
    expected_source_hashes.update(
        {
            "v2_driver_sha256": _sha(Path(v2.__file__)),
            "v3_driver_sha256": _sha(Path(__file__)),
        }
    )
    expected_execution = {
        **v2_plan.manifest["execution_contract"],
        "maximum_workers": 2,
        "v2_evidence_is_read_only": True,
    }
    if (
        manifest.get("status") != "frozen_before_v3_execution"
        or manifest.get("interpretation") != INTERPRETATION
        or manifest.get("source_hashes") != expected_source_hashes
        or manifest.get("cohorts") != v2_plan.manifest["cohorts"]
        or manifest.get("holdout_contract") != _holdout_contract()
        or manifest.get("execution_contract") != expected_execution
    ):
        raise ValueError("V3 signed contracts are not canonical")
    specs = tuple(
        CandidateSpec(**{k: row[k] for k in asdict(OP80_REFINEMENT_WAVE[0])})
        for row in manifest["candidates"]
    )
    if specs != _reused_specs(v2_plan) + OP80_REFINEMENT_WAVE:
        raise ValueError("V3 candidates changed")
    if (
        manifest.get("expected_case_count"),
        manifest.get("new_case_count"),
        manifest.get("reused_case_count"),
    ) != (80, 15, 65):
        raise ValueError("V3 case counts changed")
    expected_cases = [
        {
            "case_key": _case_key(s.key, seed),
            "candidate_key": s.key,
            "seed": seed,
            "evidence_mode": s.evidence_mode,
        }
        for s in specs
        for seed in CALIBRATION_SEEDS
    ]
    if (
        manifest.get("cases") != expected_cases
        or manifest.get("selection_contract") != _selection_contract()
    ):
        raise ValueError("V3 cases or selection contract changed")
    proposal_path = plan_dir / "op80_refinement_candidates.json"
    proposal = _read(proposal_path)
    unsigned = dict(proposal)
    proposal_signature = unsigned.pop("artifact_signature", "")
    if (
        proposal_signature != _stable(unsigned)
        or set(proposal)
        != {
            "schema_version",
            "status",
            "candidates",
            "calibration_seeds",
            "holdout_cases_read",
            "artifact_signature",
        }
        or proposal.get("schema_version") != f"{SCHEMA_VERSION}.candidate_design"
        or proposal.get("status") != "pre_registered_before_v3_execution"
        or proposal.get("candidates")
        != [_spec_payload(s) for s in OP80_REFINEMENT_WAVE]
        or proposal.get("calibration_seeds") != list(CALIBRATION_SEEDS)
        or proposal.get("holdout_cases_read") != 0
        or manifest["candidate_design"]["proposal_sha256"] != _sha(proposal_path)
    ):
        raise ValueError("V3 preregistered candidate design changed")
    expected_design = {
        "fixed_op100_candidate_key": FIXED_REFERENCE_KEY,
        "fixed_op93_candidate_key": FIXED_OP93_KEY,
        "new_op80_candidates": [_spec_payload(s) for s in OP80_REFINEMENT_WAVE],
        "proposal_file": "op80_refinement_candidates.json",
        "proposal_sha256": _sha(proposal_path),
    }
    if manifest.get("candidate_design") != expected_design:
        raise ValueError("V3 candidate design contract changed")
    inventory = manifest.get("inventory")
    if not isinstance(inventory, dict) or set(inventory) != {s.key for s in specs}:
        raise ValueError("Invalid V3 graph inventory")
    base = v2._base_plan(v2_plan.source_plan)
    source_graph = coarse._read_json(base.source_graph)
    for spec in specs:
        graph = plan_dir / inventory[spec.key]["graph_path"]
        expected_graph, expected_changes = coarse.apply_product_delays(
            source_graph,
            base.lanes_by_product,
            offset_days_268091=spec.offset_days_268091,
            offset_days_268967=spec.offset_days_268967,
        )
        expected_item = {
            "graph_path": f"graphs/{spec.key}.json",
            "graph_sha256": _sha(graph) if graph.is_file() else "",
            "changes": expected_changes,
        }
        if (
            not graph.is_file()
            or _read(graph) != expected_graph
            or inventory[spec.key] != expected_item
        ):
            raise ValueError(f"V3 graph changed: {spec.key}")
    return RefinementPlan(plan_dir, manifest, v2_plan, specs, inventory)


def _spec(plan: RefinementPlan, key: str) -> CandidateSpec:
    return next(spec for spec in plan.specs if spec.key == key)


def _adapter(plan: RefinementPlan, spec: CandidateSpec) -> coarse.ValidatedPlan:
    base = v2._base_plan(plan.source_plan.source_plan)
    candidate = spec.candidate
    item = plan.inventory[spec.key]
    return coarse.ValidatedPlan(
        plan_dir=plan.plan_dir,
        manifest={
            "plan_signature": plan.manifest["plan_signature"],
            "targets": [0.93, 0.80],
            "target_tolerance": 0.015,
        },
        candidates=(candidate,),
        source_graph=base.source_graph,
        engine=base.engine,
        profile=base.profile,
        inventory={
            candidate.candidate_id: {
                **asdict(candidate),
                "graph_path": item["graph_path"],
                "graph_sha256": item["graph_sha256"],
            }
        },
        lanes_by_product=base.lanes_by_product,
    )


def _wrap(
    plan: RefinementPlan,
    spec: CandidateSpec,
    seed: int,
    raw: Mapping[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "case_key": _case_key(spec.key, seed),
        "candidate_key": spec.key,
        "candidate_id": spec.candidate.candidate_id,
        "target_group": spec.target_group,
        "offset_days_268091": spec.offset_days_268091,
        "offset_days_268967": spec.offset_days_268967,
        "seed": seed,
        "source_kind": source_kind,
        "evidence_mode": spec.evidence_mode,
        "source_evidence": dict(raw),
        "source_evidence_signature": raw["evidence_signature"],
        "metrics": dict(raw["metrics"]),
        "graph_sha256": plan.inventory[spec.key]["graph_sha256"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "valid": raw.get("valid") is True,
    }
    payload["evidence_signature"] = _stable(payload)
    return payload


def _validate_evidence(plan: RefinementPlan, payload: Mapping[str, Any]) -> None:
    unsigned = dict(payload)
    signature = unsigned.pop("evidence_signature", "")
    key = str(payload.get("candidate_key"))
    seed = int(payload.get("seed", -1))
    spec = _spec(plan, key)
    raw = payload.get("source_evidence")
    expected_fields = {
        "schema_version",
        "plan_signature",
        "case_key",
        "candidate_key",
        "candidate_id",
        "target_group",
        "offset_days_268091",
        "offset_days_268967",
        "seed",
        "source_kind",
        "evidence_mode",
        "source_evidence",
        "source_evidence_signature",
        "metrics",
        "graph_sha256",
        "engine_sha256",
        "valid",
        "evidence_signature",
    }
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or signature != _stable(unsigned)
        or seed not in CALIBRATION_SEEDS
        or payload.get("case_key") != _case_key(key, seed)
        or payload.get("candidate_id") != spec.candidate.candidate_id
        or payload.get("target_group") != spec.target_group
        or payload.get("evidence_mode") != spec.evidence_mode
        or float(payload.get("offset_days_268091", "nan")) != spec.offset_days_268091
        or float(payload.get("offset_days_268967", "nan")) != spec.offset_days_268967
        or not isinstance(raw, Mapping)
        or payload.get("source_evidence_signature") != raw.get("evidence_signature")
        or payload.get("metrics") != raw.get("metrics")
        or payload.get("graph_sha256") != plan.inventory[key]["graph_sha256"]
        or payload.get("graph_sha256") != raw.get("graph_sha256")
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("engine_sha256") != raw.get("engine_sha256")
        or payload.get("valid") is not True
    ):
        raise ValueError("Invalid V3 evidence/signature")
    if spec.evidence_mode == "reuse_v2":
        v2._validate_evidence(raw, plan.source_plan)
        expected = v2._evidence_path(
            Path(plan.manifest["source"]["v2_run_dir"]), _case_key(key, seed)
        )
        expected_hash = plan.manifest["source"]["artifact_hashes"][
            "v2_evidence_sha256"
        ][_case_key(key, seed)]
        if (
            _sha(expected) != expected_hash
            or dict(raw) != _read(expected)
            or payload.get("source_kind") != "reused_v2_refinement_evidence"
        ):
            raise ValueError("Reused V2 evidence provenance changed")
    else:
        coarse._validate_evidence(raw, spec.candidate, _adapter(plan, spec), seed)
        if payload.get("source_kind") != "canonical_v3_refinement_execution":
            raise ValueError("Invalid V3 execution provenance")


def _load_evidence(plan: RefinementPlan, output_dir: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    expected_paths = {
        _evidence_path(output_dir, str(case["case_key"])).resolve()
        for case in plan.manifest["cases"]
    }
    evidence_dir = output_dir / "evidence"
    if evidence_dir.is_dir():
        extras = {
            path.resolve() for path in evidence_dir.glob("*.json")
        } - expected_paths
        if extras:
            raise ValueError("Unexpected JSON evidence outside the V3 inventory")
    for case in plan.manifest["cases"]:
        path = _evidence_path(output_dir, case["case_key"])
        if path.is_file():
            payload = _read(path)
            _validate_evidence(plan, payload)
            loaded[case["case_key"]] = payload
    return loaded


def _select(
    plan: RefinementPlan, evidence: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rows_by_key = {
        spec.key: [evidence[_case_key(spec.key, seed)] for seed in CALIBRATION_SEEDS]
        for spec in plan.specs
    }
    v2._validate_comparable_demand(plan, evidence)
    summaries = {
        key: v2._candidate_summary(_spec(plan, key), rows)
        for key, rows in rows_by_key.items()
    }
    reference = summaries[FIXED_REFERENCE_KEY]
    high = summaries[FIXED_OP93_KEY]
    eligible: list[dict[str, Any]] = []
    for low_spec in OP80_REFINEMENT_WAVE:
        low = summaries[low_spec.key]
        offsets_monotone = (
            _spec(plan, FIXED_REFERENCE_KEY).offset_days_268091
            < _spec(plan, FIXED_OP93_KEY).offset_days_268091
            < low_spec.offset_days_268091
            and _spec(plan, FIXED_REFERENCE_KEY).offset_days_268967
            < _spec(plan, FIXED_OP93_KEY).offset_days_268967
            < low_spec.offset_days_268967
        )
        pooled_order = all(
            reference["pooled_ratio_of_sums"][field]
            > high["pooled_ratio_of_sums"][field]
            > low["pooled_ratio_of_sums"][field]
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            )
        )
        joint = 0
        for seed in CALIBRATION_SEEDS:
            r, h, lo = (
                next(row for row in rows_by_key[key] if int(row["seed"]) == seed)
                for key in (FIXED_REFERENCE_KEY, FIXED_OP93_KEY, low_spec.key)
            )
            if all(
                float(r["metrics"][f])
                > float(h["metrics"][f])
                > float(lo["metrics"][f])
                for f in (
                    "system_on_due_service",
                    "on_due_service_268091",
                    "on_due_service_268967",
                )
            ):
                joint += 1
        if (
            reference["admissible_individually"]
            and high["admissible_individually"]
            and low["admissible_individually"]
            and offsets_monotone
            and pooled_order
            and joint >= 4
        ):
            eligible.append(
                {
                    "op93_candidate_key": FIXED_OP93_KEY,
                    "op80_candidate_key": low_spec.key,
                    "same_seed_joint_strict_order_count": joint,
                    "score": list(v2._pair_score(high, low)),
                }
            )
    eligible.sort(key=lambda row: tuple(row["score"]))
    winner = eligible[0] if eligible else None
    status = SELECTION_PASS_STATUS if winner else SELECTION_FAIL_STATUS
    selection: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": status,
        "plan_signature": plan.manifest["plan_signature"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_sealed_and_unread": list(HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "selection_contract": plan.manifest["selection_contract"],
        "holdout_contract": plan.manifest["holdout_contract"],
        "candidate_summaries": summaries,
        "eligible_pairs": eligible,
        "selected_pair": winner,
        "holdout_launch_permitted": winner is not None,
        "fallback_required": winner is None,
    }
    selection["selection_signature"] = _stable(selection)
    if winner is None:
        return selection, None
    chosen = {
        "op_100": FIXED_REFERENCE_KEY,
        "op_93": FIXED_OP93_KEY,
        "op_80": winner["op80_candidate_key"],
    }
    points: dict[str, Any] = {
        "schema_version": POINTS_SCHEMA_VERSION,
        "status": POINTS_STATUS,
        "simulation_hypotheses_not_observed_performance": True,
        "target_labels_apply_to_global_service_only": True,
        "holdout_validated": False,
        "holdout_cases_read": 0,
        "plan": {
            "path": str(plan.plan_dir),
            "plan_signature": plan.manifest["plan_signature"],
        },
        "selection": {
            "relative_path": "selection.json",
            "schema_version": SELECTION_SCHEMA_VERSION,
            "selection_signature": selection["selection_signature"],
        },
        "selection_signature": selection["selection_signature"],
        "source_hashes": plan.manifest["source_hashes"],
        "cohorts": plan.manifest["cohorts"],
        "holdout_contract": plan.manifest["holdout_contract"],
        "service_evaluation_window": SERVICE_WINDOW,
        "operating_points": [],
    }
    for point_id, key in chosen.items():
        spec, summary = _spec(plan, key), summaries[key]
        points["operating_points"].append(
            {
                "operating_point_id": point_id,
                "target_service": TARGETS[point_id],
                "candidate_key": key,
                "candidate_id": spec.candidate.candidate_id,
                "offset_days_268091": spec.offset_days_268091,
                "offset_days_268967": spec.offset_days_268967,
                "graph": str(
                    (plan.plan_dir / plan.inventory[key]["graph_path"]).resolve()
                ),
                "graph_sha256": plan.inventory[key]["graph_sha256"],
                "calibration_pooled_service": summary["pooled_ratio_of_sums"][
                    "system_on_due_service"
                ],
                "calibration_median_service": summary["individual_seed_metrics"][
                    "system_on_due_service"
                ]["median"],
                "calibration_product_268091_service": summary["pooled_ratio_of_sums"][
                    "on_due_service_268091"
                ],
                "calibration_product_268967_service": summary["pooled_ratio_of_sums"][
                    "on_due_service_268967"
                ],
                "maximum_global_target_error_over_pool_median_and_leave_one_out": summary[
                    "maximum_absolute_global_target_error"
                ],
            }
        )
    points["artifact_signature"] = _stable(points)
    return selection, points


def _run_manifest(plan: RefinementPlan) -> dict[str, Any]:
    return {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_signature": plan.manifest["plan_signature"],
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "holdout_seeds_excluded": list(HOLDOUT_SEEDS),
        "holdout_case_count": 0,
        "expected_case_count": 80,
        "new_case_count": 15,
        "reused_case_count": 65,
    }


def _progress(
    plan: RefinementPlan, output: Path, status: str, error: str | None = None
) -> None:
    completed = len(_load_evidence(plan, output))
    _write(
        output / "progress.json",
        {
            "schema_version": f"{SCHEMA_VERSION}.progress",
            "plan_signature": plan.manifest["plan_signature"],
            "status": status,
            "completed_case_count": completed,
            "expected_case_count": 80,
            "holdout_case_count": 0,
            "error": error,
        },
    )


@contextmanager
def _lock(output: Path):
    path = output / ".multiseed_refinement_v3.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another process owns {path}") from exc
    try:
        os.write(fd, f"pid={os.getpid()}\n".encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def finalize(
    plan: RefinementPlan, output: Path, evidence: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    if len(evidence) != 80:
        raise ValueError(f"V3 refinement incomplete: {len(evidence)}/80")
    selection, points = _select(plan, evidence)
    _write(output / "selection.json", selection)
    destination = output / "selected_operating_points.json"
    if points is not None:
        _write(destination, points)
    elif destination.exists():
        raise RuntimeError("Refusing stale selected points after failed V3 selection")
    return {"selection": selection, "selected_operating_points": points}


def run(
    plan_dir: Path,
    output_dir: Path,
    *,
    executor: RawExecutor = coarse.execute_candidate,
    max_workers: int = 2,
) -> dict[str, Any]:
    if max_workers not in (1, 2):
        raise ValueError("Use one or two workers to bound memory use")
    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    _assert_disjoint(
        output_dir,
        plan.plan_dir,
        Path(plan.manifest["source"]["v1_plan_dir"]),
        Path(plan.manifest["source"]["v1_run_dir"]),
        Path(plan.manifest["source"]["v2_plan_dir"]),
        Path(plan.manifest["source"]["v2_run_dir"]),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "run_manifest.json"
    expected_manifest = _run_manifest(plan)
    if manifest_path.exists():
        if _read(manifest_path) != expected_manifest:
            raise ValueError("Output directory belongs to another V3 run")
    elif any(output_dir.iterdir()):
        raise ValueError("Refusing a non-empty unregistered V3 output")
    else:
        _write(manifest_path, expected_manifest)
    with _lock(output_dir):
        evidence = _load_evidence(plan, output_dir)
        _, source_evidence, _ = _v2_source(
            Path(plan.manifest["source"]["v2_plan_dir"]),
            Path(plan.manifest["source"]["v2_run_dir"]),
        )
        for spec in plan.specs:
            if spec.evidence_mode != "reuse_v2":
                continue
            for seed in CALIBRATION_SEEDS:
                key = _case_key(spec.key, seed)
                if key not in evidence:
                    wrapped = _wrap(
                        plan,
                        spec,
                        seed,
                        source_evidence[key],
                        "reused_v2_refinement_evidence",
                    )
                    _write(_evidence_path(output_dir, key), wrapped)
                    evidence[key] = wrapped
        _progress(plan, output_dir, "running")
        missing = [
            (spec, seed)
            for spec in OP80_REFINEMENT_WAVE
            for seed in CALIBRATION_SEEDS
            if _case_key(spec.key, seed) not in evidence
        ]
        try:
            with ThreadPoolExecutor(max_workers=min(max_workers, 2)) as pool:
                futures = {
                    pool.submit(
                        executor, spec.candidate, _adapter(plan, spec), output_dir, seed
                    ): (spec, seed)
                    for spec, seed in missing
                }
                for future in as_completed(futures):
                    spec, seed = futures[future]
                    wrapped = _wrap(
                        plan,
                        spec,
                        seed,
                        future.result(),
                        "canonical_v3_refinement_execution",
                    )
                    _validate_evidence(plan, wrapped)
                    _write(
                        _evidence_path(output_dir, _case_key(spec.key, seed)), wrapped
                    )
                    evidence[_case_key(spec.key, seed)] = wrapped
                    _progress(plan, output_dir, "running")
        except Exception as exc:
            _progress(plan, output_dir, "failed", str(exc))
            raise
        evidence = _load_evidence(plan, output_dir)
        result = finalize(plan, output_dir, evidence)
        _progress(plan, output_dir, "complete")
        return result


def validate_selected_operating_points(path: Path) -> dict[str, Any]:
    path = path.resolve()
    payload = _read(path)
    unsigned = dict(payload)
    signature = unsigned.pop("artifact_signature", "")
    if (
        payload.get("schema_version") != POINTS_SCHEMA_VERSION
        or payload.get("status") != POINTS_STATUS
        or signature != _stable(unsigned)
        or payload.get("holdout_cases_read") != 0
    ):
        raise ValueError("Invalid V3 selected operating-point artifact/signature")
    plan = validate_plan(Path(payload["plan"]["path"]))
    if payload["plan"]["plan_signature"] != plan.manifest["plan_signature"]:
        raise ValueError("V3 selected points do not match plan")
    output = path.parent
    _assert_disjoint(
        output,
        plan.plan_dir,
        Path(plan.manifest["source"]["v1_plan_dir"]),
        Path(plan.manifest["source"]["v1_run_dir"]),
        Path(plan.manifest["source"]["v2_plan_dir"]),
        Path(plan.manifest["source"]["v2_run_dir"]),
    )
    if _read(output / "run_manifest.json") != _run_manifest(plan):
        raise ValueError("V3 run manifest changed")
    progress = _read(output / "progress.json")
    if (
        progress.get("schema_version") != f"{SCHEMA_VERSION}.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("status") != "complete"
        or progress.get("completed_case_count") != 80
        or progress.get("expected_case_count") != 80
        or progress.get("holdout_case_count") != 0
        or progress.get("error") not in (None, "")
        or (output / ".multiseed_refinement_v3.lock").exists()
    ):
        raise ValueError("V3 run is incomplete")
    evidence = _load_evidence(plan, output)
    selection, reproduced = _select(plan, evidence)
    if _read(output / "selection.json") != selection or reproduced != payload:
        raise ValueError("V3 selected points are not reproducible from 80 proofs")
    return payload


def validate_run(plan_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Validate a complete V3 run, including a legitimate signed NO-GO."""
    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    _assert_disjoint(
        output_dir,
        plan.plan_dir,
        Path(plan.manifest["source"]["v1_plan_dir"]),
        Path(plan.manifest["source"]["v1_run_dir"]),
        Path(plan.manifest["source"]["v2_plan_dir"]),
        Path(plan.manifest["source"]["v2_run_dir"]),
    )
    if _read(output_dir / "run_manifest.json") != _run_manifest(plan):
        raise ValueError("V3 run manifest changed")
    progress = _read(output_dir / "progress.json")
    if (
        progress.get("schema_version") != f"{SCHEMA_VERSION}.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("status") != "complete"
        or progress.get("completed_case_count") != 80
        or progress.get("expected_case_count") != 80
        or progress.get("holdout_case_count") != 0
        or progress.get("error") not in (None, "")
        or (output_dir / ".multiseed_refinement_v3.lock").exists()
    ):
        raise ValueError("V3 run is incomplete")
    evidence = _load_evidence(plan, output_dir)
    if len(evidence) != 80:
        raise ValueError("V3 run does not contain exactly 80 valid proofs")
    selection, points = _select(plan, evidence)
    if _read(output_dir / "selection.json") != selection:
        raise ValueError("V3 selection is not reproducible from 80 proofs")
    points_path = output_dir / "selected_operating_points.json"
    if points is None:
        if points_path.exists():
            raise ValueError("Unexpected selected points after V3 NO-GO")
    elif not points_path.is_file() or _read(points_path) != points:
        raise ValueError("V3 selected points are missing or changed")
    return {"selection": selection, "selected_operating_points": points}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "run", "validate"))
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--selected", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "prepare":
        prepare_plan(args.plan)
    elif args.mode == "run":
        run(args.plan, args.output)
    else:
        selected = args.selected or args.output / "selected_operating_points.json"
        if args.selected is not None or selected.is_file():
            validate_selected_operating_points(selected)
        else:
            validate_run(args.plan, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
