from __future__ import annotations

"""Business validation pack for the Risk Creation Index (RCI)."""

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .core import safe_float


REDUCED_RCI_SCOPE = "scan_reduced_order_policy_model"
REDUCED_RCI_DEFINITION_VERSION = "scan.reduced_risk_creation_area.v1"
REDUCED_RCI_CANONICAL_TRANSFERABILITY = "not_established"
RCI_REVIEW_PACK_SCHEMA_VERSION = "scan.rci_business_review_pack.v2"
RCI_REVIEW_PACK_ID_PREFIX = "RCI-PACK-"
RCI_REVIEW_PACK_HASH_NUMERIC_SIGNIFICANT_DIGITS = 12
RCI_REVIEW_PACK_HASH_NUMERIC_CANONICALIZATION = (
    "finite_numeric_decimal_12_significant_digits"
)
AUTHORITATIVE_MODEL_RCI_SOURCE = "generated_full_review_pack"
REVIEW_PACK_METADATA_COLUMNS: tuple[str, ...] = (
    "review_pack_schema_version",
    "review_pack_id",
    "review_pack_hash",
)


EXPERT_COLUMNS: tuple[str, ...] = (
    "reviewer_id",
    "reviewer_role",
    "expert_risk_created_0_1",
    "expert_plausibility_1_5",
    "supplier_pressure_risk_1_5",
    "planning_nervousness_risk_1_5",
    "operational_feasibility_1_5",
    "procurement_acceptability_1_5",
    "planning_acceptability_1_5",
    "expected_service_impact_m2_p2",
    "expert_confidence_1_5",
    "procurement_risk_created_0_1",
    "planning_risk_created_0_1",
    "procurement_plausibility_1_5",
    "planning_plausibility_1_5",
    "acceptable_order_change_0_1",
    "acceptable_expedite_0_1",
    "preferred_playbook",
    "reviewer",
    "review_date",
    "expert_comment",
)

REQUIRED_COMPLETED_REVIEW_COLUMNS: tuple[str, ...] = (
    "episode_id",
    "reviewer_id",
    "model_rci",
    "expert_risk_created_0_1",
    "expert_plausibility_1_5",
    "supplier_pressure_risk_1_5",
    "planning_nervousness_risk_1_5",
    "operational_feasibility_1_5",
    "procurement_acceptability_1_5",
    "planning_acceptability_1_5",
    "expected_service_impact_m2_p2",
    "expert_confidence_1_5",
    "expert_comment",
)
REQUIRED_EXTERNAL_REVIEW_COLUMNS: tuple[str, ...] = (
    *REVIEW_PACK_METADATA_COLUMNS,
    *(
        column
        for column in REQUIRED_COMPLETED_REVIEW_COLUMNS
        if column != "model_rci"
    ),
)


def _canonical_hash_value(value: Any) -> Any:
    """Return a JSON-stable scalar for a review-pack fingerprint."""

    if value is None or bool(pd.isna(value)):
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer, float, np.floating)):
        numeric = float(value)
        if not np.isfinite(numeric):
            raise ValueError("RCI review-pack model values must be finite.")
        if numeric == 0.0:
            return "0"
        # pandas' default CSV parser and ``float_precision='round_trip'`` can
        # legitimately choose adjacent IEEE-754 values for the same decimal
        # token. Hashing all 17 binary64 digits therefore made a pack reject
        # its own standard CSV round-trip. Canonicalizing integer- and
        # floating-typed values alike also makes benign CSV dtype inference
        # irrelevant. Twelve significant decimal digits
        # preserve the research outputs' useful precision while normalizing
        # parser-only ULP drift. This resolution is part of pack schema v2;
        # material edits at or above it still change the fingerprint.
        return format(
            numeric,
            f".{RCI_REVIEW_PACK_HASH_NUMERIC_SIGNIFICANT_DIGITS}g",
        )
    return str(value)


def _review_pack_hash(review: pd.DataFrame) -> str:
    """Fingerprint the exact episode/model binding, independent of row order."""

    if "episode_id" not in review.columns:
        raise ValueError("RCI review pack requires episode_id.")
    model_columns = sorted(
        column for column in review.columns if column.startswith("model_rci")
    )
    if "model_rci" not in model_columns:
        raise ValueError("RCI review pack requires authoritative model_rci.")

    episodes = review["episode_id"].fillna("").astype(str).str.strip()
    if bool(episodes.eq("").any()):
        raise ValueError("RCI review-pack episode_id values must be non-empty.")
    if bool(episodes.duplicated(keep=False).any()):
        duplicates = sorted(episodes[episodes.duplicated(keep=False)].unique())
        raise ValueError(
            "RCI review-pack episode_id values must be unique: "
            + ", ".join(duplicates)
        )

    canonical = review.assign(episode_id=episodes).sort_values("episode_id")
    payload = {
        "schema_version": RCI_REVIEW_PACK_SCHEMA_VERSION,
        "numeric_canonicalization": (
            RCI_REVIEW_PACK_HASH_NUMERIC_CANONICALIZATION
        ),
        "model_columns": model_columns,
        "episodes": [
            {
                "episode_id": str(row["episode_id"]),
                "model": {
                    column: _canonical_hash_value(row[column])
                    for column in model_columns
                },
            }
            for _, row in canonical.iterrows()
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _review_pack_id(pack_hash: str) -> str:
    return RCI_REVIEW_PACK_ID_PREFIX + pack_hash[:16].upper()


def _is_sha256(value: str) -> bool:
    return (
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _attach_review_pack_identity(review: pd.DataFrame) -> pd.DataFrame:
    """Attach one deterministic identity to the generated full review pack."""

    result = review.copy()
    pack_hash = _review_pack_hash(result)
    pack_id = _review_pack_id(pack_hash)
    result["review_pack_schema_version"] = RCI_REVIEW_PACK_SCHEMA_VERSION
    result["review_pack_id"] = pack_id
    result["review_pack_hash"] = pack_hash
    result.attrs.update({
        "review_pack_schema_version": RCI_REVIEW_PACK_SCHEMA_VERSION,
        "review_pack_id": pack_id,
        "review_pack_hash": pack_hash,
    })
    return result


def _uniform_text_value(
    frame: pd.DataFrame,
    column: str,
    *,
    context: str,
) -> str:
    if column not in frame.columns:
        raise ValueError(f"{context} is missing {column}.")
    values = frame[column].fillna("").astype(str).str.strip().unique().tolist()
    if len(values) != 1 or not values[0]:
        raise ValueError(f"{context} has inconsistent or empty {column} values.")
    return str(values[0])


def _validate_authoritative_review_pack(
    review_pack: pd.DataFrame,
) -> tuple[str, str, str]:
    """Validate the generated pack before it can lend model authority."""

    if review_pack.empty:
        raise ValueError("Cannot bind a completed review to an empty RCI pack.")
    schema = _uniform_text_value(
        review_pack,
        "review_pack_schema_version",
        context="Authoritative RCI review pack",
    )
    pack_id = _uniform_text_value(
        review_pack,
        "review_pack_id",
        context="Authoritative RCI review pack",
    )
    pack_hash = _uniform_text_value(
        review_pack,
        "review_pack_hash",
        context="Authoritative RCI review pack",
    )
    if schema != RCI_REVIEW_PACK_SCHEMA_VERSION:
        raise ValueError(
            "Authoritative RCI review pack uses an unsupported schema version."
        )
    if not _is_sha256(pack_hash):
        raise ValueError(
            "Authoritative RCI review pack hash is not a lower-case SHA-256."
        )
    expected_hash = _review_pack_hash(review_pack)
    if pack_hash != expected_hash:
        raise ValueError(
            "Authoritative RCI review pack hash does not match its "
            "episode/model contents."
        )
    expected_id = _review_pack_id(expected_hash)
    if pack_id != expected_id:
        raise ValueError(
            "Authoritative RCI review pack ID is incoherent with its hash."
        )
    return schema, pack_id, pack_hash


RCI_REVIEW_VARIABLES: tuple[dict[str, str], ...] = (
    {
        "variable": "review_pack_schema_version",
        "role": "required_provenance_key",
        "allowed_values": RCI_REVIEW_PACK_SCHEMA_VERSION,
        "definition": "Schema version that must remain unchanged through blinded review.",
    },
    {
        "variable": "review_pack_id",
        "role": "required_provenance_key",
        "allowed_values": f"{RCI_REVIEW_PACK_ID_PREFIX}<deterministic id>",
        "definition": "Deterministic identifier of the reviewed episode/model pack.",
    },
    {
        "variable": "review_pack_hash",
        "role": "required_provenance_key",
        "allowed_values": "lower-case SHA-256",
        "definition": (
            "Fingerprint binding the reviewed episode IDs to authoritative "
            "model output; finite numeric model values are canonicalized to "
            "12 significant decimal digits so standard pandas CSV parsing "
            "and float_precision=round_trip preserve the same pack identity."
        ),
    },
    {
        "variable": "episode_id",
        "role": "join_key",
        "allowed_values": "non-empty stable identifier",
        "definition": "Identifier used to join blinded ratings back to model output.",
    },
    {
        "variable": "reviewer_id",
        "role": "expert_input",
        "allowed_values": "non-empty pseudonymous identifier",
        "definition": "Stable reviewer identifier used for inter-rater agreement.",
    },
    {
        "variable": "candidate_policy",
        "role": "context",
        "allowed_values": "named SCAN playbook",
        "definition": "Candidate response evaluated for the episode, whether selected or rejected.",
    },
    {
        "variable": "decision_eligible",
        "role": "full_pack_audit_context_blinded",
        "allowed_values": "0 or 1",
        "definition": (
            "Whether the regime rule allowed this playbook to participate in "
            "controller selection. Hidden from the blind workshop file."
        ),
    },
    {
        "variable": "candidate_evaluation_scope",
        "role": "full_pack_audit_context_blinded",
        "allowed_values": (
            "controller_regime_eligible or "
            "rci_aggressive_review_counterfactual"
        ),
        "definition": (
            "Separates decision-eligible candidates from an aggressive "
            "same-scenario counterfactual included only to prevent RCI review "
            "selection bias. Hidden from the blind workshop file."
        ),
    },
    {
        "variable": "model_rci",
        "role": "model_output_blinded",
        "allowed_values": "continuous, higher means more response-created risk",
        "definition": (
            "Reduced-order-model proxy for incremental supplier and planning "
            "risk created by the response; excluded from the blinded workshop "
            "file and not interchangeable with the canonical-engine proxy."
        ),
    },
    {
        "variable": "model_rci_scope",
        "role": "model_output_metadata_blinded",
        "allowed_values": REDUCED_RCI_SCOPE,
        "definition": (
            "Explicit scope of the proxy reviewed by procurement and planning; "
            "excluded from the blinded workshop file."
        ),
    },
    {
        "variable": "model_rci_definition_version",
        "role": "model_output_metadata_blinded",
        "allowed_values": REDUCED_RCI_DEFINITION_VERSION,
        "definition": (
            "Versioned reduced-model formula identifier; it does not validate "
            "the differently defined canonical-engine proxy."
        ),
    },
    {
        "variable": "expert_risk_created_0_1",
        "role": "required_expert_input",
        "allowed_values": "0=no, 1=yes",
        "definition": "Overall expert judgment that the candidate creates or amplifies risk.",
    },
    {
        "variable": "expert_plausibility_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=not plausible … 5=very plausible",
        "definition": "Plausibility of the simulated operational mechanism and consequences.",
    },
    {
        "variable": "supplier_pressure_risk_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=very low … 5=very high",
        "definition": "Risk that the response creates unsustainable supplier pressure.",
    },
    {
        "variable": "planning_nervousness_risk_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=very low … 5=very high",
        "definition": "Risk of avoidable replanning, order volatility or production instability.",
    },
    {
        "variable": "operational_feasibility_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=infeasible … 5=fully feasible",
        "definition": "Operational feasibility under lots, capacity, contracts and lead times.",
    },
    {
        "variable": "procurement_acceptability_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=unacceptable … 5=fully acceptable",
        "definition": "Acceptability from the procurement and supplier-relationship perspective.",
    },
    {
        "variable": "planning_acceptability_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=unacceptable … 5=fully acceptable",
        "definition": "Acceptability from production and supply-planning perspectives.",
    },
    {
        "variable": "expected_service_impact_m2_p2",
        "role": "required_expert_input",
        "allowed_values": "-2=strong harm … 0=neutral … +2=strong benefit",
        "definition": "Expected direction and magnitude of the candidate's service impact.",
    },
    {
        "variable": "expert_confidence_1_5",
        "role": "required_expert_input",
        "allowed_values": "1=very uncertain … 5=very confident",
        "definition": "Reviewer confidence in the submitted judgments.",
    },
    {
        "variable": "expert_comment",
        "role": "required_expert_input",
        "allowed_values": "non-empty free text",
        "definition": "Rationale, constraints, assumptions and evidence supporting the review.",
    },
)


def _candidate_review_rows(decisions: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Keep all candidate actions, not only the selected low-RCI policy.

    Reviewing only the chosen action would create a selection bias: the controller
    is designed to avoid high RCI, so procurement and planning would rarely see
    the aggressive counterexamples needed to validate the index.  The pack
    therefore contains all playbooks considered at each review date and flags the
    one actually selected.
    """

    if decisions.empty or candidates.empty:
        return pd.DataFrame()
    selected = decisions[["day", "selected_policy", "regime", "observability", "controllability"]].copy()
    result = candidates.merge(
        selected,
        on=["day", "regime"],
        how="left",
        suffixes=("_candidate", "_decision"),
    )
    result["is_selected"] = (result["policy"].astype(str) == result["selected_policy"].astype(str)).astype(int)
    return result


def _policy_mechanism(policy: str) -> str:
    """Describe the candidate without interpreting model outcomes."""

    if policy == "reactive_buffer":
        return "order uplift, buffer adjustment and expediting"
    elif policy == "service_protection":
        return "service-priority production and replenishment adjustment"
    elif policy == "supplier_relief":
        return "order smoothing and supplier-relief adjustment"
    elif policy == "recovery_damping":
        return "post-event order and production damping"
    elif policy == "balanced_robust":
        return "bounded multi-lever planning response"
    return "reference MRP response"


def build_rci_business_validation_pack(
    adaptive: pd.DataFrame,
    decisions: pd.DataFrame,
    candidates: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    candidate_rows = _candidate_review_rows(decisions, candidates)
    if candidate_rows.empty:
        return _attach_review_pack_identity(
            pd.DataFrame(columns=[
                "episode_id",
                "decision_day",
                "regime",
                "candidate_policy",
                "is_selected",
                "is_rejected",
                "is_aggressive",
                "review_stratum",
                "model_rci",
                *EXPERT_COLUMNS,
            ])
        )
    review_period = max(1, int(config.get("review_period_days", 7)))
    rows: list[dict[str, Any]] = []
    ordered = candidate_rows.sort_values(["day", "policy"]).reset_index(drop=True)
    for _, candidate in ordered.iterrows():
        start = int(candidate["day"])
        stop = min(len(adaptive), start + review_period)
        selected_window = adaptive.iloc[start:stop]
        model_rci = safe_float(candidate.get("mean_risk_creation"), 0.0)
        p90_rci = safe_float(candidate.get("p90_risk_creation"), model_rci)
        nervousness = safe_float(candidate.get("mean_nervousness"), 0.0)
        expedite = safe_float(candidate.get("mean_expedite"), 0.0)
        service_loss = safe_float(candidate.get("mean_service_loss"), 0.0)
        backlog = safe_float(candidate.get("mean_backlog_area"), 0.0)
        risk_area = safe_float(candidate.get("mean_risk_area"), 0.0)
        action_magnitude = safe_float(candidate.get("mean_action_magnitude"), 0.0)
        severity = (
            3.0 * max(0.0, model_rci)
            + 0.25 * nervousness
            + 0.18 * expedite
            + 0.10 * action_magnitude
        )
        if model_rci >= 0.15 or severity >= 2.0:
            model_class = "high"
        elif model_rci >= 0.03 or severity >= 0.7:
            model_class = "medium"
        else:
            model_class = "low"
        selected_policy = str(candidate.get("selected_policy") or "")
        candidate_policy = str(candidate.get("policy") or "")
        regime = str(candidate.get("regime") or "")
        episode_key = f"{start}|{regime}|{candidate_policy}"
        episode_id = (
            "RCI-"
            + hashlib.sha256(episode_key.encode("utf-8"))
            .hexdigest()[:12]
            .upper()
        )
        is_selected = int(candidate.get("is_selected", 0))
        is_aggressive = int(candidate_policy == "reactive_buffer")
        rows.append({
            "episode_id": episode_id,
            "decision_day": start,
            "window_end_day": stop - 1,
            "regime": regime,
            "candidate_policy": candidate_policy,
            "selected_policy": selected_policy,
            "decision_eligible": int(
                candidate.get("decision_eligible", 1)
            ),
            "candidate_evaluation_scope": str(
                candidate.get(
                    "candidate_evaluation_scope",
                    "controller_regime_eligible",
                )
            ),
            "is_selected": is_selected,
            "is_rejected": 1 - is_selected,
            "is_aggressive": is_aggressive,
            "review_stratum": (
                "selected"
                if is_selected
                else "rejected_aggressive"
                if is_aggressive
                else "rejected"
            ),
            "model_rci": model_rci,
            "model_rci_scope": REDUCED_RCI_SCOPE,
            "model_rci_definition_version": (
                REDUCED_RCI_DEFINITION_VERSION
            ),
            "model_rci_canonical_transferability": (
                REDUCED_RCI_CANONICAL_TRANSFERABILITY
            ),
            "model_rci_p90": p90_rci,
            "model_rci_class": model_class,
            "model_rci_severity_proxy": severity,
            "robust_score": safe_float(candidate.get("robust_score"), 0.0),
            "expected_score": safe_float(candidate.get("expected_score"), 0.0),
            "forecast_service_loss": service_loss,
            "forecast_backlog_area": backlog,
            "forecast_nervousness": nervousness,
            "forecast_expedite": expedite,
            "forecast_supplier_risk_area": risk_area,
            "forecast_action_magnitude": action_magnitude,
            "observability": safe_float(candidate.get("observability"), 0.0),
            "controllability": safe_float(candidate.get("controllability"), 0.0),
            "selected_window_mean_forecast_risk": float(selected_window["base_risk"].mean()) if not selected_window.empty else 0.0,
            "selected_window_mean_realized_risk": float(selected_window["realized_base_risk"].mean()) if not selected_window.empty else 0.0,
            "selected_window_service_loss": float((1.0 - selected_window["service"]).clip(lower=0).sum()) if not selected_window.empty else 0.0,
            "mechanism_to_review": _policy_mechanism(candidate_policy),
            "business_question": (
                "If this candidate playbook were applied in the stated regime, could it create or amplify "
                "supplier stress, future delay, quality loss or planning instability despite its short-term benefit?"
            ),
            "review_priority": float(abs(model_rci) + 0.08 * nervousness + 0.04 * expedite + 0.02 * action_magnitude),
            **{column: "" for column in EXPERT_COLUMNS},
        })
    result = pd.DataFrame(rows)
    # Present high-information counterfactuals first while keeping the episode id
    # stable for joining a blinded review back to model outputs.
    result = result.sort_values(
        ["review_priority", "decision_day"],
        ascending=[False, True],
    ).reset_index(drop=True)
    return _attach_review_pack_identity(result)


_BLIND_EXACT_EXCLUSIONS: frozenset[str] = frozenset({
    "selected_policy",
    "is_selected",
    "is_rejected",
    "is_aggressive",
    "review_stratum",
    "decision_eligible",
    "candidate_evaluation_scope",
    "robust_score",
    "expected_score",
    "review_priority",
})


def build_blinded_rci_review(review: pd.DataFrame) -> pd.DataFrame:
    """Remove model verdict/ranking signals and deterministically shuffle rows.

    The stable ``episode_id`` is retained for the post-workshop join. The order
    is derived only from that identifier and a public protocol salt; it cannot
    encode RCI magnitude, controller selection, or review priority.
    """

    if review.empty:
        return review.copy()
    _validate_authoritative_review_pack(review)
    excluded = {
        column
        for column in review.columns
        if (
            column.startswith("model_rci")
            or column.startswith("selected_window_")
            or column in _BLIND_EXACT_EXCLUSIONS
        )
    }
    blinded = review.drop(columns=sorted(excluded), errors="ignore").copy()
    if "episode_id" not in blinded:
        raise ValueError("RCI blind review requires episode_id.")
    blinded["_blind_order"] = blinded["episode_id"].astype(str).map(
        lambda episode_id: hashlib.sha256(
            f"scan-rci-blind-v1|{episode_id}".encode("utf-8")
        ).hexdigest()
    )
    return (
        blinded.sort_values("_blind_order")
        .drop(columns="_blind_order")
        .reset_index(drop=True)
    )


def bind_completed_business_review(
    authoritative_review_pack: pd.DataFrame,
    completed_review: pd.DataFrame,
) -> pd.DataFrame:
    """Bind human ratings to model output from the generated full pack.

    The completed workshop file is authoritative only for human-entered fields.
    Any externally supplied ``model_rci*`` columns are discarded before a
    many-to-one join to the validated full pack. Pack provenance and episode IDs
    are strict: stale/tampered packs, unknown episodes and duplicate
    reviewer/episode ratings are rejected instead of being partially accepted.
    """

    if completed_review.empty:
        return completed_review.copy()

    expected_schema, expected_id, expected_hash = (
        _validate_authoritative_review_pack(authoritative_review_pack)
    )
    external = completed_review.copy()
    external["episode_id"] = (
        external.get("episode_id", pd.Series(index=external.index, dtype=object))
        .fillna("")
        .astype(str)
        .str.strip()
    )

    supplied_schema = _uniform_text_value(
        external,
        "review_pack_schema_version",
        context="Completed RCI review",
    )
    supplied_id = _uniform_text_value(
        external,
        "review_pack_id",
        context="Completed RCI review",
    )
    supplied_hash = _uniform_text_value(
        external,
        "review_pack_hash",
        context="Completed RCI review",
    )
    if supplied_schema != RCI_REVIEW_PACK_SCHEMA_VERSION:
        raise ValueError(
            "Completed RCI review is stale: unsupported review-pack schema."
        )
    if (
        not _is_sha256(supplied_hash)
        or supplied_id != _review_pack_id(supplied_hash)
    ):
        raise ValueError(
            "Completed RCI review has incoherent review_pack_id/review_pack_hash."
        )
    if supplied_id != expected_id or supplied_hash != expected_hash:
        raise ValueError(
            "Completed RCI review belongs to a stale or different review pack."
        )
    if supplied_schema != expected_schema:
        raise ValueError(
            "Completed RCI review schema does not match the authoritative pack."
        )

    known_episode_ids = set(
        authoritative_review_pack["episode_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    unknown_episode_ids = sorted(
        set(external["episode_id"]) - known_episode_ids
    )
    if unknown_episode_ids:
        raise ValueError(
            "Completed RCI review contains unknown episode_id values: "
            + ", ".join(unknown_episode_ids)
        )

    if "reviewer_id" not in external.columns:
        raise ValueError(
            "Completed RCI review requires reviewer_id for full-panel coverage."
        )
    external["reviewer_id"] = (
        external["reviewer_id"].fillna("").astype(str).str.strip()
    )
    if bool(external["reviewer_id"].eq("").any()):
        raise ValueError(
            "Completed RCI review requires a non-empty reviewer_id on every row."
        )
    duplicate = external.duplicated(
        ["reviewer_id", "episode_id"],
        keep=False,
    )
    if bool(duplicate.any()):
        duplicate_keys = (
            external.loc[duplicate, ["reviewer_id", "episode_id"]]
            .drop_duplicates()
            .sort_values(["reviewer_id", "episode_id"])
            .to_dict(orient="records")
        )
        raise ValueError(
            "Completed RCI review contains duplicate reviewer_id/episode_id "
            f"ratings: {duplicate_keys}"
        )

    # Every participating expert must rate the complete authoritative panel.
    # Otherwise an apparently valid workshop file could silently reintroduce
    # selection bias by omitting difficult, rejected, or aggressive episodes.
    missing_by_reviewer: dict[str, list[str]] = {}
    for reviewer_id, reviewer_rows in external.groupby(
        "reviewer_id",
        sort=True,
    ):
        rated_episode_ids = set(reviewer_rows["episode_id"])
        missing_episode_ids = sorted(
            known_episode_ids - rated_episode_ids
        )
        if missing_episode_ids:
            missing_by_reviewer[str(reviewer_id)] = missing_episode_ids
    if missing_by_reviewer:
        raise ValueError(
            "Completed RCI review has incomplete reviewer-panel coverage: "
            f"{missing_by_reviewer}"
        )

    join_keys = [
        "episode_id",
        "review_pack_schema_version",
        "review_pack_id",
        "review_pack_hash",
    ]
    for column, value in (
        ("review_pack_schema_version", expected_schema),
        ("review_pack_id", expected_id),
        ("review_pack_hash", expected_hash),
    ):
        external[column] = value

    authoritative = authoritative_review_pack.copy()
    authoritative["episode_id"] = (
        authoritative["episode_id"].fillna("").astype(str).str.strip()
    )
    # Human inputs in the template are placeholders, never authoritative.
    authoritative = authoritative.drop(
        columns=list(EXPERT_COLUMNS),
        errors="ignore",
    )

    # Ignore legacy or malicious model values and any copied/tampered context
    # from the blind file. Context and model fields come back from the full pack.
    external_model_columns = [
        column for column in external if column.startswith("model_rci")
    ]
    authoritative_overlaps = [
        column
        for column in external
        if column in authoritative.columns and column not in join_keys
    ]
    external = external.drop(
        columns=sorted(
            set(external_model_columns + authoritative_overlaps)
        ),
        errors="ignore",
    )
    bound = external.merge(
        authoritative,
        on=join_keys,
        how="left",
        sort=False,
        validate="many_to_one",
    )
    if bool(bound["model_rci"].isna().any()):
        raise ValueError(
            "Completed RCI review could not be bound to authoritative model_rci."
        )
    bound["model_rci_source"] = AUTHORITATIVE_MODEL_RCI_SOURCE
    bound["review_pack_binding_status"] = "bound_to_authoritative_pack"
    bound.attrs.update({
        "review_pack_schema_version": expected_schema,
        "review_pack_id": expected_id,
        "review_pack_hash": expected_hash,
        "ignored_external_model_columns": external_model_columns,
    })
    return bound


def _binary(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").where(lambda values: values.isin([0, 1]))


def _pending_review(reason: str, **details: Any) -> dict[str, Any]:
    return {
        "status": "pending_business_review",
        "validated_proxy_scope": REDUCED_RCI_SCOPE,
        "validated_proxy_definition_version": (
            REDUCED_RCI_DEFINITION_VERSION
        ),
        "canonical_proxy_transferability": (
            REDUCED_RCI_CANONICAL_TRANSFERABILITY
        ),
        "completed_rows": int(details.pop("completed_rows", 0)),
        "reason": reason,
        "required_fields": list(REQUIRED_EXTERNAL_REVIEW_COLUMNS),
        "required_external_fields": list(REQUIRED_EXTERNAL_REVIEW_COLUMNS),
        "model_rci_binding": (
            "model_rci is ignored in the external file and restored from the "
            "authoritative full review pack"
        ),
        **details,
    }


def rci_review_variable_dictionary() -> pd.DataFrame:
    """Return the review data dictionary as an exportable table."""

    return pd.DataFrame(RCI_REVIEW_VARIABLES)


def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2.0 * precision * recall / max(precision + recall, 1e-12),
        "accuracy": (tp + tn) / max(tp + fp + fn + tn, 1),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _candidate_thresholds(values: np.ndarray) -> np.ndarray:
    unique = np.unique(np.asarray(values, dtype=float))
    if len(unique) == 0:
        return np.array([], dtype=float)
    if len(unique) == 1:
        return np.array([
            np.nextafter(unique[0], -np.inf),
            unique[0],
            np.nextafter(unique[0], np.inf),
        ])
    midpoints = (unique[:-1] + unique[1:]) / 2.0
    return np.unique(np.concatenate([
        [np.nextafter(unique[0], -np.inf)],
        unique,
        midpoints,
        [np.nextafter(unique[-1], np.inf)],
    ]))


def _spearman_without_scipy(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 2 or len(right) != len(left):
        return None
    left_rank = pd.Series(left, dtype=float).rank(method="average").to_numpy(dtype=float)
    right_rank = pd.Series(right, dtype=float).rank(method="average").to_numpy(dtype=float)
    left_centered = left_rank - left_rank.mean()
    right_centered = right_rank - right_rank.mean()
    denominator = float(np.sqrt(
        np.square(left_centered).sum() * np.square(right_centered).sum()
    ))
    if denominator <= 1e-12:
        return None
    return float(np.dot(left_centered, right_centered) / denominator)


def _cohen_kappa(complete: pd.DataFrame) -> tuple[float | None, str]:
    if len(complete) < 2:
        return None, "insufficient_common_episodes"
    first = complete.iloc[:, 0].to_numpy(dtype=int)
    second = complete.iloc[:, 1].to_numpy(dtype=int)
    observed = float((first == second).mean())
    first_positive = float(first.mean())
    second_positive = float(second.mean())
    expected = (
        first_positive * second_positive
        + (1.0 - first_positive) * (1.0 - second_positive)
    )
    if 1.0 - expected <= 1e-12:
        return None, "insufficient_rating_variation"
    return float((observed - expected) / (1.0 - expected)), "computed"


def _fleiss_kappa(complete: pd.DataFrame) -> tuple[float | None, str]:
    reviewer_count = int(complete.shape[1])
    if reviewer_count <= 2 or len(complete) < 2:
        return None, "insufficient_complete_panel"
    positive = complete.sum(axis=1).to_numpy(dtype=float)
    negative = reviewer_count - positive
    agreement_by_episode = (
        positive * (positive - 1.0) + negative * (negative - 1.0)
    ) / (reviewer_count * (reviewer_count - 1.0))
    observed = float(agreement_by_episode.mean())
    total_ratings = float(len(complete) * reviewer_count)
    positive_share = float(positive.sum() / total_ratings)
    negative_share = 1.0 - positive_share
    expected = positive_share**2 + negative_share**2
    if 1.0 - expected <= 1e-12:
        return None, "insufficient_rating_variation"
    return float((observed - expected) / (1.0 - expected)), "computed"


def _inter_rater_agreement(review: pd.DataFrame) -> dict[str, Any]:
    pivot = review.pivot(
        index="episode_id",
        columns="reviewer_id",
        values="_expert_risk",
    )
    reviewer_count = int(pivot.shape[1])
    result: dict[str, Any] = {
        "reviewer_count": reviewer_count,
        "episodes_available": int(len(pivot)),
        "episodes_used": 0,
        "method": None,
        "value": None,
        "status": "insufficient_reviewers",
    }
    if reviewer_count < 2:
        return result

    complete = pivot.dropna(axis=0, how="any")
    result["episodes_used"] = int(len(complete))
    if reviewer_count == 2:
        value, status = _cohen_kappa(complete)
        result.update({"method": "cohen_kappa", "value": value, "status": status})
        return result

    value, status = _fleiss_kappa(complete)
    result.update({"method": "fleiss_kappa", "value": value, "status": status})
    return result


def _select_rci_threshold(
    rci: np.ndarray,
    labels: np.ndarray,
) -> tuple[float | None, dict[str, Any] | None]:
    thresholds = _candidate_thresholds(rci)
    # A discriminating threshold cannot be estimated from a single outcome
    # class.  Optimizing accuracy in that situation would produce a seemingly
    # strong but scientifically meaningless cut-off.
    if (
        len(thresholds) == 0
        or len(labels) == 0
        or len(np.unique(np.asarray(labels, dtype=int))) < 2
    ):
        return None, None
    scored: list[tuple[float, dict[str, Any]]] = []
    for threshold in thresholds:
        predicted = (rci >= threshold).astype(int)
        scored.append(
            (float(threshold), _classification_metrics(labels, predicted))
        )
    return max(
        scored,
        key=lambda item: (
            float(item[1]["f1"]),
            float(item[1]["accuracy"]),
            float(item[1]["precision"]),
            float(item[0]),
        ),
    )


def _leave_one_episode_out_metrics(
    episode: pd.DataFrame,
) -> tuple[dict[str, Any] | None, list[str], list[str], int, str]:
    """Estimate classification performance without scoring training episodes."""

    if episode.empty:
        return None, [], [], 0, "not_estimable_no_resolved_episodes"
    label_counts = episode["expert_label"].value_counts()
    if len(label_counts) < 2:
        return None, [], [], 0, "not_estimable_single_consensus_class"
    # Every leave-one-out training fold must retain both classes.  Otherwise the
    # evaluated subset would systematically omit the singleton class and yield a
    # biased performance estimate.
    if int(label_counts.min()) < 2:
        return None, [], [], 0, "not_estimable_insufficient_class_replication"

    truths: list[int] = []
    predictions: list[int] = []
    identifiers: list[str] = []
    for held_out_id, held_out in episode.iterrows():
        training = episode.drop(index=held_out_id)
        threshold, _ = _select_rci_threshold(
            training["model_rci"].to_numpy(dtype=float),
            training["expert_label"].to_numpy(dtype=int),
        )
        if threshold is None:
            continue
        truths.append(int(held_out["expert_label"]))
        predictions.append(int(float(held_out["model_rci"]) >= threshold))
        identifiers.append(str(held_out_id))
    if not truths:
        return None, [], [], 0, "not_estimable_no_valid_folds"
    y_true = np.asarray(truths, dtype=int)
    y_pred = np.asarray(predictions, dtype=int)
    metrics = _classification_metrics(y_true, y_pred)
    false_positive_ids = [
        episode_id
        for episode_id, truth, estimate in zip(identifiers, y_true, y_pred)
        if truth == 0 and estimate == 1
    ]
    false_negative_ids = [
        episode_id
        for episode_id, truth, estimate in zip(identifiers, y_true, y_pred)
        if truth == 1 and estimate == 0
    ]
    return metrics, false_positive_ids, false_negative_ids, len(truths), "computed"


def summarize_completed_business_review(review: pd.DataFrame) -> dict[str, Any]:
    if review.empty:
        return _pending_review("no_completed_review_file")

    pack_identity: dict[str, str] = {}
    present_pack_metadata = [
        column for column in REVIEW_PACK_METADATA_COLUMNS
        if column in review.columns
    ]
    if present_pack_metadata:
        missing_pack_metadata = [
            column for column in REVIEW_PACK_METADATA_COLUMNS
            if column not in review.columns
        ]
        if missing_pack_metadata:
            return _pending_review(
                "incomplete_review_pack_provenance",
                missing_columns=missing_pack_metadata,
            )
        try:
            schema = _uniform_text_value(
                review,
                "review_pack_schema_version",
                context="Bound RCI review",
            )
            pack_id = _uniform_text_value(
                review,
                "review_pack_id",
                context="Bound RCI review",
            )
            pack_hash = _uniform_text_value(
                review,
                "review_pack_hash",
                context="Bound RCI review",
            )
        except ValueError as exc:
            return _pending_review(
                "inconsistent_review_pack_provenance",
                provenance_error=str(exc),
            )
        if (
            schema != RCI_REVIEW_PACK_SCHEMA_VERSION
            or not _is_sha256(pack_hash)
            or pack_id != _review_pack_id(pack_hash)
        ):
            return _pending_review(
                "incoherent_review_pack_provenance",
                review_pack_schema_version=schema,
                review_pack_id=pack_id,
            )
        model_sources = (
            review["model_rci_source"].fillna("").astype(str).str.strip().unique()
            if "model_rci_source" in review.columns
            else []
        )
        if (
            len(model_sources) != 1
            or model_sources[0] != AUTHORITATIVE_MODEL_RCI_SOURCE
        ):
            return _pending_review(
                "model_rci_not_bound_to_authoritative_pack",
                review_pack_id=pack_id,
            )
        pack_identity = {
            "review_pack_schema_version": schema,
            "review_pack_id": pack_id,
            "review_pack_hash": pack_hash,
            "model_rci_source": AUTHORITATIVE_MODEL_RCI_SOURCE,
        }

    missing = [
        column for column in REQUIRED_COMPLETED_REVIEW_COLUMNS
        if column not in review.columns
    ]
    if missing:
        return _pending_review("missing_required_columns", missing_columns=missing)

    work = review.copy()
    work["episode_id"] = work["episode_id"].fillna("").astype(str).str.strip()
    work["reviewer_id"] = work["reviewer_id"].fillna("").astype(str).str.strip()
    work["_expert_comment"] = (
        work["expert_comment"].fillna("").astype(str).str.strip()
    )
    work["_model_rci"] = pd.to_numeric(work["model_rci"], errors="coerce")
    work["_expert_risk"] = _binary(work["expert_risk_created_0_1"])
    scored_fields = {
        "_plausibility": ("expert_plausibility_1_5", 1, 5),
        "_supplier_pressure": ("supplier_pressure_risk_1_5", 1, 5),
        "_planning_nervousness": ("planning_nervousness_risk_1_5", 1, 5),
        "_operational_feasibility": ("operational_feasibility_1_5", 1, 5),
        "_procurement_acceptability": (
            "procurement_acceptability_1_5",
            1,
            5,
        ),
        "_planning_acceptability": ("planning_acceptability_1_5", 1, 5),
        "_expected_service_impact": (
            "expected_service_impact_m2_p2",
            -2,
            2,
        ),
        "_expert_confidence": ("expert_confidence_1_5", 1, 5),
    }
    for normalized, (source, lower, upper) in scored_fields.items():
        values = pd.to_numeric(work[source], errors="coerce")
        work[normalized] = values.where(values.between(lower, upper))
    complete = (
        work["episode_id"].ne("")
        & work["reviewer_id"].ne("")
        & work["_model_rci"].notna()
        & np.isfinite(work["_model_rci"])
        & work["_expert_risk"].notna()
        & work["_expert_comment"].ne("")
    )
    for normalized in scored_fields:
        complete &= work[normalized].notna()
    if not bool(complete.all()):
        return _pending_review(
            "incomplete_required_values",
            completed_rows=int(complete.sum()),
            incomplete_rows=int((~complete).sum()),
        )

    duplicate = work.duplicated(["episode_id", "reviewer_id"], keep=False)
    if bool(duplicate.any()):
        return _pending_review(
            "duplicate_reviewer_episode_rows",
            completed_rows=int((~duplicate).sum()),
            duplicate_rows=int(duplicate.sum()),
        )

    rci_ranges = work.groupby("episode_id")["_model_rci"].agg(
        lambda values: float(values.max() - values.min())
    )
    inconsistent = rci_ranges[rci_ranges > 1e-12]
    if not inconsistent.empty:
        return _pending_review(
            "inconsistent_model_rci_within_episode",
            inconsistent_episode_ids=[str(value) for value in inconsistent.index],
        )

    episode = work.groupby("episode_id", sort=True).agg(
        model_rci=("_model_rci", "first"),
        expert_positive_rate=("_expert_risk", "mean"),
        expert_plausibility=("_plausibility", "mean"),
        supplier_pressure_risk=("_supplier_pressure", "mean"),
        planning_nervousness_risk=("_planning_nervousness", "mean"),
        operational_feasibility=("_operational_feasibility", "mean"),
        procurement_acceptability=("_procurement_acceptability", "mean"),
        planning_acceptability=("_planning_acceptability", "mean"),
        expected_service_impact=("_expected_service_impact", "mean"),
        expert_confidence=("_expert_confidence", "mean"),
        reviewer_count=("reviewer_id", "nunique"),
    )
    episode["expert_label"] = np.where(
        episode["expert_positive_rate"] > 0.5,
        1.0,
        np.where(episode["expert_positive_rate"] < 0.5, 0.0, np.nan),
    )
    tied_episode_ids = [
        str(value)
        for value in episode.index[episode["expert_label"].isna()].tolist()
    ]
    resolved = episode.dropna(subset=["expert_label"]).copy()
    resolved["expert_label"] = resolved["expert_label"].astype(int)
    best_threshold, fit_metrics = _select_rci_threshold(
        resolved["model_rci"].to_numpy(dtype=float),
        resolved["expert_label"].to_numpy(dtype=int),
    )
    resolved_class_counts = {
        str(int(label)): int(count)
        for label, count in resolved["expert_label"].value_counts().items()
    }
    if resolved.empty:
        threshold_status = "not_estimable_no_resolved_episodes"
    elif len(resolved_class_counts) < 2:
        threshold_status = "not_estimable_single_consensus_class"
    else:
        threshold_status = "estimated_in_sample_exploratory"
    (
        loo_metrics,
        false_positive_ids,
        false_negative_ids,
        loo_rows,
        loo_status,
    ) = (
        _leave_one_episode_out_metrics(resolved)
    )
    agreement = _inter_rater_agreement(work)
    correlation = _spearman_without_scipy(
        episode["model_rci"].to_numpy(dtype=float),
        episode["expert_plausibility"].to_numpy(dtype=float),
    )
    risk_label_correlation = _spearman_without_scipy(
        episode["model_rci"].to_numpy(dtype=float),
        episode["expert_positive_rate"].to_numpy(dtype=float),
    )
    supplier_pressure_correlation = _spearman_without_scipy(
        episode["model_rci"].to_numpy(dtype=float),
        episode["supplier_pressure_risk"].to_numpy(dtype=float),
    )
    planning_nervousness_correlation = _spearman_without_scipy(
        episode["model_rci"].to_numpy(dtype=float),
        episode["planning_nervousness_risk"].to_numpy(dtype=float),
    )

    def count_flagged_episodes(column: str) -> int | None:
        if column not in work.columns:
            return None
        flag = pd.to_numeric(work[column], errors="coerce").fillna(0)
        return int(work.loc[flag > 0, "episode_id"].nunique())

    selected_episode_count = count_flagged_episodes("is_selected")
    rejected_episode_count = count_flagged_episodes("is_rejected")
    aggressive_episode_count = count_flagged_episodes("is_aggressive")
    performance = loo_metrics or {
        "precision": None,
        "recall": None,
        "f1": None,
        "accuracy": None,
        "confusion_matrix": None,
    }
    return {
        "status": "review_available",
        "validated_proxy_scope": REDUCED_RCI_SCOPE,
        "validated_proxy_definition_version": (
            REDUCED_RCI_DEFINITION_VERSION
        ),
        "canonical_proxy_transferability": (
            REDUCED_RCI_CANONICAL_TRANSFERABILITY
        ),
        "completed_rows": int(len(work)),
        "completed_episodes": int(len(episode)),
        "resolved_consensus_episodes": int(len(resolved)),
        "unresolved_tied_episodes": int(len(tied_episode_ids)),
        "unresolved_tied_episode_ids": tied_episode_ids,
        "reviewer_count": int(work["reviewer_id"].nunique()),
        "recommended_rci_threshold": best_threshold,
        "threshold_estimation_status": threshold_status,
        "threshold_estimation_scope": "all_resolved_episodes_in_sample",
        "resolved_consensus_class_counts": resolved_class_counts,
        "performance_estimation_method": "leave_one_episode_out",
        "performance_evaluated_episodes": int(loo_rows),
        "performance_excluded_episodes": int(len(resolved) - loo_rows),
        "performance_detail_status": loo_status,
        "performance_status": (
            "not_estimable"
            if loo_metrics is None
            else "exploratory_small_sample"
            if loo_rows < 20
            else "estimated"
        ),
        **performance,
        "fit_metrics": fit_metrics,
        "fit_metrics_scope": "in_sample_resolved_episodes",
        "false_positives": int(len(false_positive_ids)),
        "false_negatives": int(len(false_negative_ids)),
        "false_positive_episode_ids": false_positive_ids,
        "false_negative_episode_ids": false_negative_ids,
        "spearman_rci_vs_plausibility": correlation,
        "spearman_rci_vs_expert_risk_positive_rate": risk_label_correlation,
        "spearman_rci_vs_supplier_pressure_risk": supplier_pressure_correlation,
        "spearman_rci_vs_planning_nervousness_risk": (
            planning_nervousness_correlation
        ),
        "agreement_method": agreement["method"],
        "agreement_status": agreement["status"],
        "agreement_value": agreement["value"],
        "inter_rater_agreement": agreement,
        "review_scope": {
            "selected_episode_count": selected_episode_count,
            "rejected_episode_count": rejected_episode_count,
            "aggressive_episode_count": aggressive_episode_count,
        },
        **pack_identity,
    }


def write_business_validation_guide(path: Path) -> None:
    text = """# Validation métier du Risk Creation Index

## Objectif

Le Risk Creation Index (RCI) mesure la part de risque fournisseur que la réponse
opérationnelle peut créer ou amplifier par la nervosité des commandes, la pression
au-delà du headroom, l'expediting ou des changements répétés du plan.

Cet atelier porte uniquement sur le proxy du modèle réduit
`scan.reduced_risk_creation_area.v1`. Le proxy distinct calculé par le replay
canonique multi-produits n'utilise ni la même formule ni la même échelle; aucun
seuil ou classement n'est transférable sans étude d'alignement dédiée.

## Pourquoi le fichier contient les alternatives non retenues

Le contrôleur tend naturellement à sélectionner les réponses à faible RCI. Une
validation limitée aux seules décisions retenues sous-estimerait donc les épisodes
risqués. Le pack contient chaque playbook candidat et garantit une évaluation du
playbook agressif `reactive_buffer`. Lorsque celui-ci n'est pas autorisé par la
règle du régime courant, il est calculé sur les mêmes scénarios uniquement comme
contre-factuel de revue et porte
`candidate_evaluation_scope=rci_aggressive_review_counterfactual`; il ne peut
pas être sélectionné par le contrôleur.

## Atelier recommandé

1. Réunir au minimum deux experts indépendants (par exemple achats et
   planification/production).
2. Examiner de préférence `rci_business_review_blind.csv`, sans afficher le RCI,
   afin de limiter le biais de confirmation. Ce fichier est mélangé de façon
   déterministe et masque aussi la sélection du contrôleur, ses classements et
   les résumés de fenêtre sélectionnée. Ne jamais ajouter ni renseigner
   `model_rci` dans ce fichier.
3. Utiliser un format long : dupliquer chaque `episode_id` une fois par expert,
   renseigner un `reviewer_id` stable et unique, puis compléter tous les champs
   `required_expert_input` du dictionnaire ci-dessous. `reviewer_role` est
   facultatif.
4. Conserver tous les épisodes du fichier aveugle. Les strates sélectionnée,
   rejetée et contre-factuelle agressive restent traçables uniquement dans le
   fichier complet après la revue. Conserver sans modification
   `review_pack_schema_version`, `review_pack_id` et `review_pack_hash`.
5. Documenter MOQ, horizon ferme, capacité, contrat, cadence de revue et pratiques
   d'expediting qui expliquent le verdict.
6. Lier les notes au pack complet validé par `episode_id` et les identifiants du
   pack. Le RCI est toujours repris du pack complet généré; une colonne RCI
   éventuellement fournie par le fichier externe est ignorée. Recalculer ensuite
   le seuil RCI recommandé, précision, rappel, F1, accuracy, faux positifs, faux
   négatifs et corrélation de Spearman avec la plausibilité.

## Accord inter-évaluateurs

Avec exactement deux experts, le résumé calcule le kappa de Cohen. Avec plus de
deux experts, il calcule le kappa de Fleiss sur les épisodes évalués par le panel
complet. Si le nombre d'experts, le recouvrement des épisodes ou la variation des
notes sont insuffisants, l'accord porte un statut `insufficient_*` au lieu d'une
valeur artificielle.

Un vote exactement partagé n'est jamais transformé arbitrairement en vérité
positive ou négative. L'épisode porte le statut de consensus non résolu et doit
être arbitré. Le seuil recommandé est ajusté sur les épisodes résolus; les
performances publiées sont estimées en leave-one-episode-out. Les métriques
d'ajustement sur les mêmes épisodes sont conservées séparément sous `fit_metrics`.

Le résumé reste strictement `pending_business_review` si aucun fichier renseigné
n'est fourni, si une colonne obligatoire manque, ou si une valeur obligatoire est
absente ou invalide. Les anciennes colonnes spécialisées achats/planification
restent dans le modèle de fichier pour compatibilité, mais ne remplacent pas les
champs multi-experts ci-dessus.

## Dictionnaire des variables

## Limite

Tant que le fichier n'est pas renseigné par les métiers, le RCI reste une hypothèse
quantitative pré-validée par simulation, et non un indicateur industriel certifié.
"""
    dictionary = rci_review_variable_dictionary()
    table = [
        "| Variable | Rôle | Valeurs attendues | Définition |",
        "|---|---|---|---|",
    ]
    for row in dictionary.itertuples(index=False):
        table.append(
            f"| `{row.variable}` | {row.role} | {row.allowed_values} | "
            f"{row.definition} |"
        )
    text = text.replace(
        "## Dictionnaire des variables\n",
        "## Dictionnaire des variables\n\n" + "\n".join(table) + "\n",
    )
    path.write_text(text, encoding="utf-8")
