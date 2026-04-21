#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


SIM_ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = SIM_ROOT / "result" / "supplier_risk_proxy_study"
PAIR_CSV = STUDY_DIR / "supplier_material_risk_proxy_table.csv"
SUPPLIER_CSV = STUDY_DIR / "supplier_aggregate_risk_proxy_table.csv"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    pair_df = pd.read_csv(PAIR_CSV)
    supplier_df = pd.read_csv(SUPPLIER_CSV)
    return pair_df, supplier_df


def make_pair_label(row: pd.Series) -> str:
    return f"{row['supplier_id']} | {row['item_id']} | {row['factory_id']}"


def save_top_pair_risk(pair_df: pd.DataFrame) -> Path:
    df = pair_df.sort_values("combined_proxy_risk_score", ascending=False).head(10).copy()
    df["label"] = df.apply(make_pair_label, axis=1)
    df = df.iloc[::-1]

    fig, ax = plt.subplots(figsize=(14, 7))
    colors = ["#c44e52" if bool(v) else "#4c72b0" for v in df["is_assumed_edge"]]
    bars = ax.barh(df["label"], df["combined_proxy_risk_score"], color=colors)
    ax.set_title("Top 10 couples fournisseur-matiere par score proxy combine")
    ax.set_xlabel("Score proxy combine")
    ax.set_ylabel("Couple fournisseur-matiere")
    ax.set_xlim(0, max(df["combined_proxy_risk_score"]) * 1.18)
    ax.grid(axis="x", alpha=0.25)
    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.text(
            bar.get_width() + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"p_svc={row['p_service_hit_30d_proxy']:.3f} | E[backlog]={row['expected_backlog_30d_proxy']:.2f}",
            va="center",
            fontsize=9,
        )
    fig.tight_layout()
    out = STUDY_DIR / "supplier_risk_top_pairs.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def save_probability_vs_impact(pair_df: pd.DataFrame) -> Path:
    df = pair_df.copy()
    fig, ax = plt.subplots(figsize=(11, 8))
    color_map = {"M-1430": "#1f77b4", "M-1810": "#2ca02c"}
    colors = [color_map.get(factory, "#7f7f7f") for factory in df["factory_id"]]
    sizes = 140 + 1400 * df["combined_proxy_risk_score"]
    ax.scatter(df["p_incident_30d_proxy"], df["expected_backlog_30d_proxy"], s=sizes, c=colors, alpha=0.75)
    ax.set_title("Probabilite proxy d'incident vs impact backlog attendu")
    ax.set_xlabel("p_incident_30d_proxy")
    ax.set_ylabel("E[backlog delta 30j] proxy")
    ax.grid(alpha=0.25)
    top = df.sort_values("combined_proxy_risk_score", ascending=False).head(8)
    for _, row in top.iterrows():
        ax.annotate(
            f"{row['supplier_id']} / {row['item_id']}",
            (row["p_incident_30d_proxy"], row["expected_backlog_30d_proxy"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
        )
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, label=factory, markersize=10)
        for factory, color in color_map.items()
    ]
    ax.legend(handles=handles, title="Usine impactee", loc="upper right")
    fig.tight_layout()
    out = STUDY_DIR / "supplier_risk_probability_vs_impact.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def save_impact_breakdown(pair_df: pd.DataFrame) -> Path:
    df = pair_df.sort_values("expected_backlog_30d_proxy", ascending=False).head(8).copy()
    df["label"] = df.apply(lambda r: f"{r['supplier_id']} | {r['item_id']}", axis=1)
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.bar(df["label"], df["outage5d_backlog_delta"], label="Outage 5j", color="#c44e52")
    ax.bar(df["label"], df["delayx3_backlog_delta"], bottom=df["outage5d_backlog_delta"], label="Delai x3", color="#dd8452")
    ax.bar(
        df["label"],
        df["otif50_backlog_delta"],
        bottom=df["outage5d_backlog_delta"] + df["delayx3_backlog_delta"],
        label="OTIF 50%",
        color="#55a868",
    )
    ax.set_title("Decomposition des impacts backlog par scenario de stress")
    ax.set_ylabel("Delta backlog vs baseline")
    ax.set_xlabel("Couple fournisseur-matiere")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    out = STUDY_DIR / "supplier_risk_impact_breakdown.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def save_supplier_aggregate(supplier_df: pd.DataFrame) -> Path:
    df = supplier_df.sort_values("expected_backlog_30d_proxy_sum", ascending=False).head(10).copy()
    df = df.iloc[::-1]
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(df["supplier_id"], df["expected_backlog_30d_proxy_sum"], color="#8172b3")
    ax.set_title("Top fournisseurs par backlog proxy attendu agrege")
    ax.set_xlabel("Somme E[backlog delta 30j] proxy")
    ax.set_ylabel("Fournisseur")
    ax.grid(axis="x", alpha=0.25)
    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"matieres={int(row['material_count'])} | p_svc_moy={row['mean_p_service_hit_30d_proxy']:.3f}",
            va="center",
            fontsize=9,
        )
    fig.tight_layout()
    out = STUDY_DIR / "supplier_risk_supplier_aggregate.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def save_probability_waterfall(pair_df: pd.DataFrame) -> Path:
    df = pair_df.sort_values("p_service_hit_30d_proxy", ascending=False).head(10).copy()
    df["label"] = df.apply(lambda r: f"{r['supplier_id']} | {r['item_id']}", axis=1)
    fig, ax = plt.subplots(figsize=(14, 7))
    x = range(len(df))
    ax.bar(x, df["p_incident_30d_proxy"], color="#4c72b0", alpha=0.40, label="p incident proxy")
    ax.bar(x, df["p_service_hit_30d_proxy"], color="#c44e52", alpha=0.85, label="p choc service proxy")
    ax.set_title("Comparaison probabilite d'incident vs probabilite de choc service")
    ax.set_ylabel("Probabilite proxy a 30 jours")
    ax.set_xlabel("Couple fournisseur-matiere")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["label"], rotation=35, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    for idx, (_, row) in enumerate(df.iterrows()):
        ax.text(idx, row["p_service_hit_30d_proxy"] + 0.002, f"{row['p_service_hit_30d_proxy']:.3f}", ha="center", fontsize=8)
    fig.tight_layout()
    out = STUDY_DIR / "supplier_risk_probability_comparison.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    pair_df, supplier_df = load_data()
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        save_top_pair_risk(pair_df),
        save_probability_vs_impact(pair_df),
        save_impact_breakdown(pair_df),
        save_supplier_aggregate(supplier_df),
        save_probability_waterfall(pair_df),
    ]
    for path in outputs:
        print(f"[OK] {path}")


if __name__ == "__main__":
    main()
