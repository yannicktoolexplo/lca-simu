from __future__ import annotations

"""Business validation pack for the Risk Creation Index (RCI)."""

from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .core import safe_float


EXPERT_COLUMNS: tuple[str, ...] = (
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


def _policy_mechanism(policy: str, nervousness: float, expedite: float, rci: float) -> str:
    parts: list[str] = []
    if policy == "reactive_buffer":
        parts.extend(["aggressive order uplift", "buffer accumulation"])
    elif policy == "service_protection":
        parts.append("service-priority response")
    elif policy == "supplier_relief":
        parts.append("supplier pressure relief and order smoothing")
    elif policy == "recovery_damping":
        parts.append("post-crisis order and production damping")
    elif policy == "balanced_robust":
        parts.append("bounded multi-lever response")
    else:
        parts.append("reference MRP response")
    if nervousness > 1.0:
        parts.append("high order-plan nervousness")
    if expedite > 1.0:
        parts.append("sustained expediting")
    if rci > 0.10:
        parts.append("modelled endogenous supplier-risk increase")
    return ", ".join(parts)


def build_rci_business_validation_pack(
    adaptive: pd.DataFrame,
    decisions: pd.DataFrame,
    candidates: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    candidate_rows = _candidate_review_rows(decisions, candidates)
    if candidate_rows.empty:
        return pd.DataFrame(columns=[
            "episode_id", "decision_day", "regime", "candidate_policy", "model_rci", *EXPERT_COLUMNS
        ])
    review_period = max(1, int(config.get("review_period_days", 7)))
    rows: list[dict[str, Any]] = []
    ordered = candidate_rows.sort_values(["day", "robust_score", "policy"]).reset_index(drop=True)
    for index, candidate in ordered.iterrows():
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
        rows.append({
            "episode_id": f"RCI-{index + 1:04d}",
            "decision_day": start,
            "window_end_day": stop - 1,
            "regime": str(candidate.get("regime") or ""),
            "candidate_policy": candidate_policy,
            "selected_policy": selected_policy,
            "is_selected": int(candidate.get("is_selected", 0)),
            "model_rci": model_rci,
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
            "mechanism_to_review": _policy_mechanism(candidate_policy, nervousness, expedite, model_rci),
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
    return result.sort_values(["review_priority", "decision_day"], ascending=[False, True]).reset_index(drop=True)


def _binary(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").where(lambda values: values.isin([0, 1]))


def _f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    tp = float(((y_true == 1) & (y_pred == 1)).sum())
    fp = float(((y_true == 0) & (y_pred == 1)).sum())
    fn = float(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / max(tp + fp, 1.0)
    recall = tp / max(tp + fn, 1.0)
    return 2 * precision * recall / max(precision + recall, 1e-12)


def summarize_completed_business_review(review: pd.DataFrame) -> dict[str, Any]:
    if review.empty:
        return {"status": "pending_business_review", "completed_rows": 0}
    procurement = _binary(review.get("procurement_risk_created_0_1", pd.Series(index=review.index, dtype=float)))
    planning = _binary(review.get("planning_risk_created_0_1", pd.Series(index=review.index, dtype=float)))
    expert = pd.concat([procurement, planning], axis=1).mean(axis=1, skipna=True)
    model_rci = pd.to_numeric(review.get("model_rci"), errors="coerce")
    valid = expert.notna() & model_rci.notna()
    if not valid.any():
        return {
            "status": "pending_business_review",
            "completed_rows": 0,
            "required_fields": ["procurement_risk_created_0_1", "planning_risk_created_0_1"],
        }
    expert_binary = (expert[valid] >= 0.5).astype(int).to_numpy()
    rci = model_rci[valid].to_numpy(dtype=float)
    thresholds = np.unique(np.quantile(rci, np.linspace(0, 1, min(31, max(2, len(rci))))))
    scored = [(float(threshold), _f1(expert_binary, (rci >= threshold).astype(int))) for threshold in thresholds]
    best_threshold, best_f1 = max(scored, key=lambda item: item[1])
    predicted = (rci >= best_threshold).astype(int)
    tp = int(((expert_binary == 1) & (predicted == 1)).sum())
    fp = int(((expert_binary == 0) & (predicted == 1)).sum())
    fn = int(((expert_binary == 1) & (predicted == 0)).sum())
    tn = int(((expert_binary == 0) & (predicted == 0)).sum())
    procurement_score = pd.to_numeric(review.loc[valid].get("procurement_plausibility_1_5"), errors="coerce")
    planning_score = pd.to_numeric(review.loc[valid].get("planning_plausibility_1_5"), errors="coerce")
    plausibility = pd.concat([procurement_score, planning_score], axis=1).mean(axis=1, skipna=True)
    correlation = (
        float(pd.Series(rci).corr(plausibility.reset_index(drop=True), method="spearman"))
        if plausibility.notna().sum() >= 3 else float("nan")
    )
    return {
        "status": "review_available",
        "completed_rows": int(valid.sum()),
        "recommended_rci_threshold": best_threshold,
        "f1": best_f1,
        "precision": tp / max(tp + fp, 1),
        "recall": tp / max(tp + fn, 1),
        "accuracy": (tp + tn) / max(tp + fp + fn + tn, 1),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "spearman_rci_vs_plausibility": correlation,
    }


def write_business_validation_guide(path: Path) -> None:
    text = """# Validation métier du Risk Creation Index

## Objectif

Le Risk Creation Index (RCI) mesure la part de risque fournisseur que la réponse
opérationnelle peut créer ou amplifier par la nervosité des commandes, la pression
au-delà du headroom, l'expediting ou des changements répétés du plan.

## Pourquoi le fichier contient les alternatives non retenues

Le contrôleur tend naturellement à sélectionner les réponses à faible RCI. Une
validation limitée aux seules décisions retenues sous-estimerait donc les épisodes
risqués. Le pack contient chaque playbook candidat, y compris les contre-factuels
agressifs, et indique séparément la politique finalement sélectionnée.

## Atelier recommandé

1. Réunir au minimum un représentant achats/approvisionnement et un représentant
   planification/production.
2. Examiner de préférence `rci_business_review_blind.csv`, sans afficher le RCI,
   afin de limiter le biais de confirmation.
3. Renseigner séparément les colonnes achats et planification avec 0 (non), 1
   (oui) et une plausibilité de 1 à 5.
4. Documenter MOQ, horizon ferme, capacité, contrat, cadence de revue et pratiques
   d'expediting qui expliquent le verdict.
5. Rejoindre le fichier aveugle au modèle par `episode_id`, puis recalculer le
   seuil, la précision, le rappel et la corrélation de plausibilité.

## Limite

Tant que le fichier n'est pas renseigné par les métiers, le RCI reste une hypothèse
quantitative pré-validée par simulation, et non un indicateur industriel certifié.
"""
    path.write_text(text, encoding="utf-8")
