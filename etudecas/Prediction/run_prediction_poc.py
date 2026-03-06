#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parent
SIM_RESULT_DIR = ROOT.parent / "simulation" / "result" / "supplier_risk_proxy_study"
PAIR_TABLE = SIM_RESULT_DIR / "supplier_material_risk_proxy_table.csv"
RESULT_DIR = ROOT / "result"
DATA_DIR = ROOT / "data"
RANDOM_SEED = 42
N_WEEKS = 104


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def load_pair_table() -> pd.DataFrame:
    df = pd.read_csv(PAIR_TABLE)
    return df.copy()


def generate_synthetic_history(pair_df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    supplier_quality = {
        supplier: float(rng.normal(0.0, 0.7))
        for supplier in sorted(pair_df["supplier_id"].unique())
    }
    rows = []
    base_date = pd.Timestamp("2024-01-01")

    for _, pair in pair_df.iterrows():
        structural = float(pair["structural_proxy_score"])
        impact = float(pair["impact_proxy_score"])
        uncertainty = float(pair["uncertainty_penalty"])
        demand_exposure = float(pair["demand_exposure_norm"])
        lead_risk = float(pair["lead_time_risk_norm"])
        cover_risk = float(pair["cover_risk_norm"])
        volume_exposure = float(pair["volume_exposure_norm"])
        criticality = float(pair["criticality_norm"])
        mono = float(pair["mono_source_risk"])
        supplier_bias = supplier_quality[str(pair["supplier_id"])]
        persistent_shock = float(rng.normal(0.0, 0.4))

        recent_incident_memory = 0.0
        for week in range(N_WEEKS):
            season_sin = math.sin(2.0 * math.pi * week / 52.0)
            season_cos = math.cos(2.0 * math.pi * week / 52.0)
            persistent_shock = 0.72 * persistent_shock + float(rng.normal(0.0, 0.35))
            demand_pressure = np.clip(
                0.35 + 0.55 * demand_exposure + 0.12 * season_sin + float(rng.normal(0.0, 0.07)),
                0.0,
                1.4,
            )
            lead_delay_ratio = max(
                0.0,
                0.12
                + 0.38 * lead_risk
                + 0.16 * structural
                + 0.10 * demand_pressure
                + 0.12 * persistent_shock
                + float(rng.normal(0.0, 0.06)),
            )
            short_ship_rate = np.clip(
                0.01
                + 0.12 * structural
                + 0.12 * demand_pressure
                + 0.14 * max(0.0, persistent_shock)
                + 0.06 * uncertainty
                + float(rng.normal(0.0, 0.03)),
                0.0,
                0.95,
            )
            recent_otif_4w = np.clip(
                0.985
                - 0.08 * structural
                - 0.06 * demand_pressure
                - 0.10 * max(0.0, persistent_shock)
                - 0.08 * short_ship_rate
                + float(rng.normal(0.0, 0.015)),
                0.45,
                1.0,
            )
            quality_issue_rate = np.clip(
                0.005
                + 0.02 * structural
                + 0.04 * uncertainty
                + 0.03 * max(0.0, persistent_shock)
                + float(rng.normal(0.0, 0.01)),
                0.0,
                0.6,
            )
            recent_quality_incidents_12w = int(
                np.clip(
                    round(
                        12
                        * (
                            quality_issue_rate
                            + 0.05 * max(0.0, supplier_bias)
                            + float(rng.normal(0.0, 0.02))
                        )
                    ),
                    0,
                    12,
                )
            )
            order_count_8w = max(
                1,
                int(
                    round(
                        2
                        + 7 * demand_exposure
                        + 4 * volume_exposure
                        + 2 * mono
                        + float(rng.normal(0.0, 1.2))
                    )
                ),
            )
            open_po_count = max(
                0,
                int(
                    round(
                        1
                        + 4 * demand_pressure
                        + 3 * lead_risk
                        + 2 * max(0.0, persistent_shock)
                        + float(rng.normal(0.0, 1.0))
                    )
                ),
            )

            logit = (
                -4.8
                + 1.8 * structural
                + 1.2 * impact
                + 1.0 * short_ship_rate
                + 0.8 * lead_delay_ratio
                + 0.5 * demand_pressure
                + 0.4 * uncertainty
                + 0.12 * recent_quality_incidents_12w
                + 0.35 * max(0.0, supplier_bias)
                + 0.45 * max(0.0, persistent_shock)
                + 0.4 * recent_incident_memory
            )
            true_incident_probability_30d = float(np.clip(sigmoid(logit), 0.01, 0.97))
            incident_next_30d = int(rng.uniform() < true_incident_probability_30d)
            severe_incident_next_30d = int(
                incident_next_30d
                and rng.uniform()
                < np.clip(
                    0.15 + 0.5 * impact + 0.2 * uncertainty + 0.12 * max(0.0, persistent_shock),
                    0.05,
                    0.95,
                )
            )
            recent_incident_memory = 0.55 * recent_incident_memory + 0.75 * incident_next_30d

            rows.append(
                {
                    "week_index": week + 1,
                    "snapshot_date": (base_date + pd.Timedelta(days=7 * week)).strftime("%Y-%m-%d"),
                    "pair_key": pair["pair_key"],
                    "supplier_id": pair["supplier_id"],
                    "factory_id": pair["factory_id"],
                    "item_id": pair["item_id"],
                    "supplier_count_for_item": pair["supplier_count_for_item"],
                    "structural_proxy_score": structural,
                    "impact_proxy_score": impact,
                    "combined_proxy_risk_score": float(pair["combined_proxy_risk_score"]),
                    "criticality_norm": criticality,
                    "demand_exposure_norm": demand_exposure,
                    "volume_exposure_norm": volume_exposure,
                    "cover_risk_norm": cover_risk,
                    "lead_time_risk_norm": lead_risk,
                    "mono_source_risk": mono,
                    "uncertainty_penalty": uncertainty,
                    "lead_mean_days": float(pair["lead_mean_days"]),
                    "conditional_expected_backlog_if_incident": float(pair["expected_backlog_delta_proxy"]),
                    "conditional_expected_fill_loss_if_incident": float(pair["expected_fill_loss_proxy"]),
                    "recent_otif_4w": recent_otif_4w,
                    "recent_delay_ratio_4w": lead_delay_ratio,
                    "recent_short_ship_rate_8w": short_ship_rate,
                    "recent_quality_incidents_12w": recent_quality_incidents_12w,
                    "open_po_count": open_po_count,
                    "order_count_8w": order_count_8w,
                    "demand_pressure_norm": demand_pressure,
                    "supplier_latent_shock": persistent_shock,
                    "season_sin": season_sin,
                    "season_cos": season_cos,
                    "true_incident_probability_30d": true_incident_probability_30d,
                    "incident_next_30d": incident_next_30d,
                    "severe_incident_next_30d": severe_incident_next_30d,
                }
            )

    return pd.DataFrame(rows)


def temporal_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df["week_index"] <= 72].copy()
    calib = df[(df["week_index"] >= 73) & (df["week_index"] <= 88)].copy()
    test = df[df["week_index"] >= 89].copy()
    return train, calib, test


def top_decile_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    threshold = np.quantile(y_prob, 0.90)
    y_pred_top = (y_prob >= threshold).astype(int)
    return {
        "top_decile_precision": float(precision_score(y_true, y_pred_top, zero_division=0)),
        "top_decile_recall": float(recall_score(y_true, y_pred_top, zero_division=0)),
    }


def train_and_evaluate(history_df: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame, Pipeline]:
    feature_cols = [
        "supplier_count_for_item",
        "structural_proxy_score",
        "impact_proxy_score",
        "criticality_norm",
        "demand_exposure_norm",
        "volume_exposure_norm",
        "cover_risk_norm",
        "lead_time_risk_norm",
        "mono_source_risk",
        "uncertainty_penalty",
        "lead_mean_days",
        "recent_otif_4w",
        "recent_delay_ratio_4w",
        "recent_short_ship_rate_8w",
        "recent_quality_incidents_12w",
        "open_po_count",
        "order_count_8w",
        "demand_pressure_norm",
        "season_sin",
        "season_cos",
    ]

    train_df, calib_df, test_df = temporal_split(history_df)
    x_train = train_df[feature_cols].to_numpy()
    y_train = train_df["incident_next_30d"].to_numpy()
    x_calib = calib_df[feature_cols].to_numpy()
    y_calib = calib_df["incident_next_30d"].to_numpy()
    x_test = test_df[feature_cols].to_numpy()
    y_test = test_df["incident_next_30d"].to_numpy()

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", random_state=RANDOM_SEED)),
        ]
    )
    model.fit(x_train, y_train)

    calib_raw = model.predict_proba(x_calib)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(calib_raw, y_calib)
    test_raw = model.predict_proba(x_test)[:, 1]
    test_prob = calibrator.transform(test_raw)

    metrics = {
        "train_rows": int(len(train_df)),
        "calibration_rows": int(len(calib_df)),
        "test_rows": int(len(test_df)),
        "test_incident_rate": float(np.mean(y_test)),
        "roc_auc": float(roc_auc_score(y_test, test_prob)),
        "pr_auc": float(average_precision_score(y_test, test_prob)),
        "brier_score": float(brier_score_loss(y_test, test_prob)),
    }
    metrics.update(top_decile_metrics(y_test, test_prob))

    coef = model.named_steps["clf"].coef_[0]
    feature_importance_df = pd.DataFrame(
        {
            "feature": feature_cols,
            "coefficient": coef,
            "abs_coefficient": np.abs(coef),
        }
    ).sort_values("abs_coefficient", ascending=False)

    pred_df = test_df.copy()
    pred_df["predicted_incident_probability_30d"] = test_prob
    pred_df["predicted_incident_probability_30d_raw"] = test_raw
    return metrics, pred_df, feature_importance_df, model


def score_latest_pairs(history_df: pd.DataFrame, model: Pipeline, feature_importance_df: pd.DataFrame) -> pd.DataFrame:
    feature_cols = feature_importance_df["feature"].tolist()
    calib_df = history_df[(history_df["week_index"] >= 73) & (history_df["week_index"] <= 88)].copy()
    test_df = history_df[history_df["week_index"] >= 89].copy()
    x_calib = calib_df[feature_cols].to_numpy()
    y_calib = calib_df["incident_next_30d"].to_numpy()
    x_latest = (
        history_df.sort_values(["pair_key", "week_index"])
        .groupby("pair_key", as_index=False)
        .tail(1)
        .copy()
    )
    raw_calib = model.predict_proba(x_calib)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_calib, y_calib)
    raw_latest = model.predict_proba(x_latest[feature_cols].to_numpy())[:, 1]
    x_latest["predicted_incident_probability_30d"] = calibrator.transform(raw_latest)
    x_latest["predicted_incident_probability_30d_raw"] = raw_latest
    x_latest["predicted_expected_backlog_risk_30d"] = (
        x_latest["predicted_incident_probability_30d"] * x_latest["conditional_expected_backlog_if_incident"]
    )
    x_latest["predicted_expected_fill_loss_risk_30d"] = (
        x_latest["predicted_incident_probability_30d"] * x_latest["conditional_expected_fill_loss_if_incident"]
    )
    x_latest["predicted_priority_score"] = (
        0.45 * x_latest["predicted_incident_probability_30d"]
        + 0.55 * np.clip(x_latest["conditional_expected_backlog_if_incident"] / 30.0, 0.0, 1.0)
    )
    x_latest = x_latest.sort_values(
        ["predicted_expected_backlog_risk_30d", "predicted_incident_probability_30d"],
        ascending=False,
    )
    return x_latest


def aggregate_suppliers(latest_df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        latest_df.groupby(["supplier_id"], as_index=False)
        .agg(
            supplier_pair_count=("pair_key", "count"),
            mean_predicted_incident_probability_30d=("predicted_incident_probability_30d", "mean"),
            max_predicted_incident_probability_30d=("predicted_incident_probability_30d", "max"),
            predicted_expected_backlog_risk_30d_sum=("predicted_expected_backlog_risk_30d", "sum"),
            predicted_expected_fill_loss_risk_30d_sum=("predicted_expected_fill_loss_risk_30d", "sum"),
        )
    )
    materials = latest_df.groupby("supplier_id")["item_id"].apply(lambda s: ", ".join(sorted(set(s)))).reset_index()
    agg = agg.merge(materials, on="supplier_id", how="left")
    return agg.sort_values("predicted_expected_backlog_risk_30d_sum", ascending=False)


def save_plots(pred_df: pd.DataFrame, latest_df: pd.DataFrame, supplier_df: pd.DataFrame, feature_importance_df: pd.DataFrame) -> list[Path]:
    outputs: list[Path] = []

    y_true = pred_df["incident_next_30d"].to_numpy()
    y_prob = pred_df["predicted_incident_probability_30d"].to_numpy()
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], "--", color="gray")
    ax.plot(mean_pred, frac_pos, marker="o", color="#1f77b4")
    ax.set_title("Calibration du modele sur jeu de test")
    ax.set_xlabel("Probabilite predite")
    ax.set_ylabel("Frequence observee")
    ax.grid(alpha=0.25)
    path = RESULT_DIR / "calibration_curve.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    outputs.append(path)

    top_pairs = latest_df.head(10).iloc[::-1].copy()
    top_pairs["label"] = top_pairs["supplier_id"] + " | " + top_pairs["item_id"] + " | " + top_pairs["factory_id"]
    fig, ax = plt.subplots(figsize=(13, 7))
    bars = ax.barh(top_pairs["label"], top_pairs["predicted_expected_backlog_risk_30d"], color="#c44e52")
    ax.set_title("Top 10 couples fournisseur-matiere par risque backlog predit")
    ax.set_xlabel("E[delta backlog 30j]")
    ax.grid(axis="x", alpha=0.25)
    for bar, (_, row) in zip(bars, top_pairs.iterrows()):
        ax.text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"p={row['predicted_incident_probability_30d']:.3f}",
            va="center",
            fontsize=9,
        )
    path = RESULT_DIR / "top_pair_predicted_risk.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    outputs.append(path)

    fig, ax = plt.subplots(figsize=(10, 7))
    sizes = 200 + 2400 * latest_df["predicted_priority_score"]
    ax.scatter(
        latest_df["predicted_incident_probability_30d"],
        latest_df["conditional_expected_backlog_if_incident"],
        s=sizes,
        alpha=0.70,
        c=np.where(latest_df["factory_id"] == "M-1810", "#2ca02c", "#1f77b4"),
    )
    ax.set_title("Probabilite predite vs impact conditionnel si incident")
    ax.set_xlabel("Probabilite predite incident 30j")
    ax.set_ylabel("Delta backlog conditionnel si incident")
    ax.grid(alpha=0.25)
    for _, row in latest_df.head(8).iterrows():
        ax.annotate(
            f"{row['supplier_id']} / {row['item_id']}",
            (row["predicted_incident_probability_30d"], row["conditional_expected_backlog_if_incident"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
        )
    path = RESULT_DIR / "predicted_probability_vs_conditional_impact.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    outputs.append(path)

    top_suppliers = supplier_df.head(10).iloc[::-1].copy()
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(top_suppliers["supplier_id"], top_suppliers["predicted_expected_backlog_risk_30d_sum"], color="#8172b3")
    ax.set_title("Top fournisseurs par risque backlog predit agrege")
    ax.set_xlabel("Somme E[delta backlog 30j]")
    ax.grid(axis="x", alpha=0.25)
    for bar, (_, row) in zip(bars, top_suppliers.iterrows()):
        ax.text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"pairs={int(row['supplier_pair_count'])} | pmax={row['max_predicted_incident_probability_30d']:.3f}",
            va="center",
            fontsize=9,
        )
    path = RESULT_DIR / "top_supplier_predicted_risk.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    outputs.append(path)

    top_feat = feature_importance_df.head(12).iloc[::-1].copy()
    colors = ["#55a868" if coef > 0 else "#c44e52" for coef in top_feat["coefficient"]]
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(top_feat["feature"], top_feat["coefficient"], color=colors)
    ax.set_title("Principales variables du modele probabiliste")
    ax.set_xlabel("Coefficient logistique")
    ax.grid(axis="x", alpha=0.25)
    path = RESULT_DIR / "model_feature_coefficients.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    outputs.append(path)

    return outputs


def build_report(metrics: dict[str, float], latest_df: pd.DataFrame, supplier_df: pd.DataFrame, feature_importance_df: pd.DataFrame) -> str:
    top_pairs = latest_df.head(12).copy()
    top_suppliers = supplier_df.head(10).copy()
    top_features = feature_importance_df.head(12).copy()

    def md_table(df: pd.DataFrame) -> str:
        cols = list(df.columns)
        out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, row in df.iterrows():
            vals = []
            for col in cols:
                value = row[col]
                if isinstance(value, (float, np.floating)):
                    vals.append(f"{value:.6f}")
                else:
                    vals.append(str(value))
            out.append("| " + " | ".join(vals) + " |")
        return "\n".join(out)

    top_pairs_view = top_pairs[
        [
            "supplier_id",
            "factory_id",
            "item_id",
            "predicted_incident_probability_30d",
            "conditional_expected_backlog_if_incident",
            "predicted_expected_backlog_risk_30d",
            "conditional_expected_fill_loss_if_incident",
            "predicted_expected_fill_loss_risk_30d",
        ]
    ]
    top_suppliers_view = top_suppliers[
        [
            "supplier_id",
            "supplier_pair_count",
            "mean_predicted_incident_probability_30d",
            "max_predicted_incident_probability_30d",
            "predicted_expected_backlog_risk_30d_sum",
            "item_id",
        ]
    ]
    top_features_view = top_features[["feature", "coefficient", "abs_coefficient"]]

    report = f"""# Prediction POC de risque fournisseur-matiere

## Statut
Ce dossier contient un **proof of concept** complet.

Important:
- les **labels** et une partie des variables temporelles sont **synthetiques**
- les **impacts supply** reuses viennent de l'etude de simulation existante
- donc ce POC montre **comment** faire de la prediction, pas une calibration industrielle finale

## Pipeline implemente
1. Chargement des couples fournisseur-matiere depuis l'etude proxy existante.
2. Generation d'un historique synthetique hebdomadaire sur **{N_WEEKS} semaines** par couple.
3. Creation d'un label `incident_next_30d`.
4. Split temporel:
   - train: semaines 1-72
   - calibration: semaines 73-88
   - test: semaines 89-104
5. Entrainement d'un modele probabiliste:
   - `LogisticRegression`
   - `StandardScaler`
   - calibration isotonic sur jeu intermediaire
6. Calcul du risque final:
   - `probabilite predite d'incident`
   - x `impact conditionnel si incident`

## Metriques de validation
- train_rows: **{metrics['train_rows']}**
- calibration_rows: **{metrics['calibration_rows']}**
- test_rows: **{metrics['test_rows']}**
- test_incident_rate: **{metrics['test_incident_rate']:.6f}**
- roc_auc: **{metrics['roc_auc']:.6f}**
- pr_auc: **{metrics['pr_auc']:.6f}**
- brier_score: **{metrics['brier_score']:.6f}**
- top_decile_precision: **{metrics['top_decile_precision']:.6f}**
- top_decile_recall: **{metrics['top_decile_recall']:.6f}**

## Top couples predits
{md_table(top_pairs_view)}

## Top fournisseurs predits
{md_table(top_suppliers_view)}

## Variables dominantes du modele
{md_table(top_features_view)}

## Fichiers utiles
- `data/synthetic_supplier_item_history.csv`
- `result/predicted_supplier_item_risk.csv`
- `result/predicted_supplier_risk.csv`
- `result/evaluation_metrics.json`
- `result/prediction_poc_report.md`
- `result/calibration_curve.png`
- `result/top_pair_predicted_risk.png`
- `result/predicted_probability_vs_conditional_impact.png`
- `result/top_supplier_predicted_risk.png`
- `result/model_feature_coefficients.png`

## Lecture correcte
- Ce POC valide l'architecture:
  - **proba predite**
  - **impact supply**
  - **risque attendu**
- Pour passer en vrai industriel, il suffit de remplacer:
  - l'historique synthetique
  - par des donnees reelles ERP / OTIF / qualite / retard
"""
    return report


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    pair_df = load_pair_table()
    history_df = generate_synthetic_history(pair_df)
    history_df.to_csv(DATA_DIR / "synthetic_supplier_item_history.csv", index=False)

    metrics, pred_test_df, feature_importance_df, model = train_and_evaluate(history_df)
    latest_df = score_latest_pairs(history_df, model, feature_importance_df)
    supplier_df = aggregate_suppliers(latest_df)

    pred_test_df.to_csv(RESULT_DIR / "prediction_test_scored_rows.csv", index=False)
    latest_df.to_csv(RESULT_DIR / "predicted_supplier_item_risk.csv", index=False)
    supplier_df.to_csv(RESULT_DIR / "predicted_supplier_risk.csv", index=False)
    feature_importance_df.to_csv(RESULT_DIR / "model_feature_coefficients.csv", index=False)
    (RESULT_DIR / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plots = save_plots(pred_test_df, latest_df, supplier_df, feature_importance_df)
    report = build_report(metrics, latest_df, supplier_df, feature_importance_df)
    (RESULT_DIR / "prediction_poc_report.md").write_text(report, encoding="utf-8")

    manifest = {
        "data_history": str((DATA_DIR / "synthetic_supplier_item_history.csv").resolve()),
        "predicted_pairs": str((RESULT_DIR / "predicted_supplier_item_risk.csv").resolve()),
        "predicted_suppliers": str((RESULT_DIR / "predicted_supplier_risk.csv").resolve()),
        "metrics": str((RESULT_DIR / "evaluation_metrics.json").resolve()),
        "report": str((RESULT_DIR / "prediction_poc_report.md").resolve()),
        "plots": [str(path.resolve()) for path in plots],
    }
    (RESULT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[OK] History: {(DATA_DIR / 'synthetic_supplier_item_history.csv').resolve()}")
    print(f"[OK] Predicted pairs: {(RESULT_DIR / 'predicted_supplier_item_risk.csv').resolve()}")
    print(f"[OK] Predicted suppliers: {(RESULT_DIR / 'predicted_supplier_risk.csv').resolve()}")
    print(f"[OK] Metrics: {(RESULT_DIR / 'evaluation_metrics.json').resolve()}")
    print(f"[OK] Report: {(RESULT_DIR / 'prediction_poc_report.md').resolve()}")


if __name__ == "__main__":
    main()
