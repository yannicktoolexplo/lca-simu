#!/usr/bin/env python3
"""Build a business-facing evidence pack from one paired MRP/V3 campaign.

The pack is deliberately derived from already completed physical runs.  It does
not rerun or alter the engine, and it refuses a non-empty output directory.  Its
figures focus on operational mechanisms that aggregate KPI alone cannot show:
causal propagation, horizon deferral, lot-size amplification, risk relocation
and service-buffer erosion.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


SCHEMA_VERSION = "scan.canonical_industrial_results.v1"
REFERENCE_POLICY = "mrp_reference"
FEEDBACK_POLICY = "canonical_feedback"
TOLERANCE = 1e-6

MRP_COLOR = "#718096"
V3_COLOR = "#117c78"
POSITIVE_COLOR = "#c4574f"
FAVORABLE_COLOR = "#23866d"
NEUTRAL_COLOR = "#aab4c3"
INK = "#172033"


@dataclass(frozen=True)
class IndustrialResultArtifacts:
    """Files written by :func:`build_canonical_industrial_results`."""

    output_dir: Path
    dashboard_path: Path
    report_path: Path
    manifest_path: Path
    key_results_path: Path
    figure_paths: tuple[Path, ...]


def _prepare_output(path: Path) -> Path:
    output = path.resolve()
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise FileExistsError(
                "Refusing to overwrite a non-empty industrial-results "
                f"directory: {output}"
            )
    else:
        output.mkdir(parents=True, exist_ok=False)
    return output


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(f"Missing non-empty evidence table: {path}")
    return pd.read_csv(path)


def _data_path(run_dir: Path, filename: str) -> Path:
    for candidate in (run_dir / "data" / filename, run_dir / filename):
        if candidate.is_file():
            return candidate
    return run_dir / "data" / filename


def _truthy(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def _percentage_change(reference: float, feedback: float) -> float:
    if not math.isfinite(reference) or abs(reference) <= TOLERANCE:
        return math.nan
    return 100.0 * (feedback - reference) / abs(reference)


def _fmt_number(value: float, decimals: int = 0) -> str:
    if not math.isfinite(float(value)):
        return "n.d."
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def _fmt_pct(value: float, decimals: int = 2) -> str:
    if not math.isfinite(float(value)):
        return "n.d."
    return f"{float(value):+.{decimals}f} %".replace(".", ",")


def _load_pair(
    paired_results_dir: Path,
    seed: int | None,
) -> tuple[int, Path, Path, pd.Series, pd.Series, int]:
    runs_path = paired_results_dir / "canonical_closed_loop_runs.csv"
    runs = _read_csv(runs_path)
    required = {"policy", "seed", "status", "result_dir", "days"}
    missing = sorted(required - set(runs.columns))
    if missing:
        raise ValueError("Paired run table is missing columns: " + ", ".join(missing))
    runs = runs.loc[runs["status"].astype(str).eq("ok")].copy()
    runs["seed"] = pd.to_numeric(runs["seed"], errors="raise").astype(int)
    available = []
    for candidate, group in runs.groupby("seed", sort=True):
        if {REFERENCE_POLICY, FEEDBACK_POLICY}.issubset(set(group["policy"])):
            available.append(int(candidate))
    if not available:
        raise ValueError("No complete MRP/V3 pair is available.")
    selected = int(seed) if seed is not None else available[0]
    if selected not in available:
        raise ValueError(f"Seed {selected} is unavailable; choices: {available}")
    pair = runs.loc[runs["seed"].eq(selected)]
    pairing_columns = {
        "scenario_id",
        "engine_artifact_profile",
        "engine_artifact_contract_status",
        "common_random_numbers",
        "state_dependent_risks",
        "graph_sha256",
        "risk_events_sha256",
        "engine_profile_sha256",
    }
    missing_pairing = sorted(pairing_columns - set(pair.columns))
    if missing_pairing:
        raise ValueError(
            "Paired run table is missing evidence columns: "
            + ", ".join(missing_pairing)
        )
    if not _truthy(pair["common_random_numbers"]).all():
        raise ValueError("Common-random-number pairing is not confirmed.")
    if not _truthy(pair["state_dependent_risks"]).all():
        raise ValueError("State-dependent supplier penalties are not enabled.")
    for column in (
        "scenario_id",
        "graph_sha256",
        "engine_profile_sha256",
        "risk_events_sha256",
    ):
        values = pair[column].fillna("").astype(str).unique().tolist()
        if len(values) != 1 or (column != "risk_events_sha256" and not values[0]):
            raise ValueError(f"Paired runs disagree on {column}: {values}")
    if not pair["engine_artifact_profile"].astype(str).eq("full").all():
        raise ValueError("Industrial results require the full artifact profile.")
    if (
        not pair["engine_artifact_contract_status"]
        .astype(str)
        .eq("validated_full")
        .all()
    ):
        raise ValueError("Full-artifact validation is not confirmed for both arms.")
    mrp = pair.loc[pair["policy"].eq(REFERENCE_POLICY)].iloc[0]
    v3 = pair.loc[pair["policy"].eq(FEEDBACK_POLICY)].iloc[0]
    mrp_dir = Path(str(mrp["result_dir"])).resolve()
    v3_dir = Path(str(v3["result_dir"])).resolve()
    if not mrp_dir.is_dir() or not v3_dir.is_dir():
        raise FileNotFoundError(
            f"Paired result directory missing: MRP={mrp_dir}; V3={v3_dir}"
        )
    days = int(pd.to_numeric(pd.Series([mrp["days"]]), errors="raise").iloc[0])
    if int(v3["days"]) != days:
        raise ValueError("MRP and V3 horizons differ.")

    campaign_manifest_path = paired_results_dir / "canonical_closed_loop_manifest.json"
    if not campaign_manifest_path.is_file():
        raise FileNotFoundError(
            f"Missing paired campaign manifest: {campaign_manifest_path}"
        )
    campaign = json.loads(campaign_manifest_path.read_text(encoding="utf-8"))
    if not bool(campaign.get("common_random_numbers")):
        raise ValueError("Campaign manifest does not confirm common random numbers.")
    if not bool(campaign.get("state_dependent_risks")):
        raise ValueError("Campaign manifest does not enable state-dependent penalties.")
    if selected not in [int(value) for value in campaign.get("seeds", [])]:
        raise ValueError("Selected seed is absent from the campaign manifest.")
    manifest_checks = {
        "scenario_id": campaign.get("scenario_id"),
        "days": campaign.get("days"),
        "graph_sha256": campaign.get("graph", {}).get("sha256"),
        "engine_profile_sha256": campaign.get("engine_profile", {}).get("sha256"),
        "engine_artifact_profile": campaign.get("engine_artifact_profile"),
        "engine_artifact_contract_status": campaign.get(
            "engine_artifact_contract", {}
        ).get("status"),
    }
    expected_checks = {
        "scenario_id": str(mrp["scenario_id"]),
        "days": days,
        "graph_sha256": str(mrp["graph_sha256"]),
        "engine_profile_sha256": str(mrp["engine_profile_sha256"]),
        "engine_artifact_profile": "full",
        "engine_artifact_contract_status": "validated_full",
    }
    if manifest_checks != expected_checks:
        raise ValueError(
            "Campaign manifest pairing evidence disagrees with run rows: "
            f"manifest={manifest_checks}; expected={expected_checks}"
        )

    def warmup_state_hash(run_dir: Path) -> str:
        summary_path = run_dir / "summaries" / "first_simulation_summary.json"
        if not summary_path.is_file():
            raise FileNotFoundError(f"Missing warmup evidence: {summary_path}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        audit = summary.get("policy", {}).get("warmup_boundary_audit", {})
        if audit.get("method") != "deterministic_paired_burn_in_replay":
            raise ValueError(f"Unexpected warmup method in {summary_path}")
        value = str(audit.get("core_state_sha256", ""))
        if not value:
            raise ValueError(f"Missing warmup core-state digest in {summary_path}")
        return value

    mrp_state_hash = warmup_state_hash(mrp_dir)
    v3_state_hash = warmup_state_hash(v3_dir)
    if mrp_state_hash != v3_state_hash:
        raise ValueError("MRP and V3 measured-period initial physical states differ.")
    return selected, mrp_dir, v3_dir, mrp, v3, days


def _validate_comparison(
    comparison_dir: Path,
    *,
    paired_results_dir: Path,
    seed: int,
) -> tuple[pd.DataFrame, Path]:
    manifest_path = comparison_dir / "canonical_node_comparison_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing node-comparison manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_seed = int(manifest.get("pairing_contract", {}).get("seed", -1))
    if manifest_seed != seed:
        raise ValueError(
            f"Comparison seed {manifest_seed} does not match paired seed {seed}."
        )
    source = Path(
        str(manifest.get("source", {}).get("paired_results_dir", ""))
    ).resolve()
    if source != paired_results_dir.resolve():
        raise ValueError(
            "Node comparison does not refer to the requested paired campaign."
        )
    summary = _read_csv(comparison_dir / "canonical_node_comparison_summary.csv")
    summary["has_difference"] = _truthy(summary["has_difference"])
    tables_dir = comparison_dir / "tables_by_family"
    if not tables_dir.is_dir():
        raise FileNotFoundError(f"Missing paired family tables: {tables_dir}")
    return summary, tables_dir


def _save_figure(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _tradeoff_frame(mrp: pd.Series, v3: pd.Series) -> pd.DataFrame:
    definitions = (
        ("Service moyen", "mean_service", "stable", "ratio"),
        (
            "Score de perturbations fournisseur calculées",
            "supplier_risk_area",
            "lower",
            "indice",
        ),
        ("Contraintes détectées", "constraint_violations", "lower", "compte"),
        (
            "Coût total de la période",
            "total_economic_exposure",
            "lower",
            "monnaie",
        ),
    )
    rows = []
    for label, column, preference, unit in definitions:
        reference = float(mrp[column])
        feedback = float(v3[column])
        rows.append(
            {
                "indicator": label,
                "source_column": column,
                "mrp": reference,
                "v3": feedback,
                "delta": feedback - reference,
                "delta_pct": _percentage_change(reference, feedback),
                "preference": preference,
                "unit": unit,
            }
        )
    return pd.DataFrame(rows)


def _cost_bridge_frame(mrp_dir: Path, v3_dir: Path) -> pd.DataFrame:
    def load(run_dir: Path) -> Mapping[str, Any]:
        path = run_dir / "run" / "kpis.json"
        if not path.is_file():
            raise FileNotFoundError(f"Missing economic KPI file: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    mrp = load(mrp_dir)
    v3 = load(v3_dir)
    definitions = (
        ("Achats", ("total_purchase_cost",)),
        ("Transport", ("total_transport_cost",)),
        (
            "Stock : possession, entrepôt, risque",
            (
                "total_holding_cost",
                "total_warehouse_operating_cost",
                "total_inventory_risk_cost",
            ),
        ),
        ("Production", ("total_production_cost",)),
    )
    rows = []
    for label, columns in definitions:
        reference = sum(float(mrp[column]) for column in columns)
        feedback = sum(float(v3[column]) for column in columns)
        rows.append(
            {
                "component": label,
                "mrp": reference,
                "v3": feedback,
                "delta": feedback - reference,
            }
        )
    total_delta = float(v3["total_cost"]) - float(mrp["total_cost"])
    component_delta = sum(float(row["delta"]) for row in rows)
    if abs(total_delta - component_delta) > 0.01:
        raise ValueError(
            "Economic cost bridge does not reconcile with total_cost: "
            f"components={component_delta}; total={total_delta}"
        )
    return pd.DataFrame(rows)


def _plot_tradeoffs(
    tradeoffs: pd.DataFrame,
    costs: pd.DataFrame,
    *,
    mrp: pd.Series,
    v3: pd.Series,
    output: Path,
) -> Path:
    path = output / "01_arbitrages_executifs.png"
    frame = tradeoffs.iloc[::-1].copy()
    values = frame["delta_pct"].fillna(0.0).to_numpy(dtype=float)
    colors = []
    for row in frame.itertuples():
        if abs(float(row.delta_pct)) <= 1e-12:
            colors.append(NEUTRAL_COLOR)
        elif row.preference == "lower" and row.delta_pct < 0:
            colors.append(FAVORABLE_COLOR)
        else:
            colors.append(POSITIVE_COLOR)
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15.0, 7.2),
        gridspec_kw={"width_ratios": [1.0, 1.12]},
    )
    axis = axes[0]
    positions = np.arange(len(frame))
    axis.barh(positions, values, color=colors, height=0.62)
    axis.axvline(0.0, color=INK, linewidth=1.0)
    axis.set_yticks(positions, frame["indicator"].tolist(), fontsize=10)
    axis.set_xlabel("variation V3 par rapport au MRP (%)")
    axis.set_title("Ce qui s'améliore et ce qui se dégrade", fontsize=12, weight="bold")
    axis.grid(axis="x", alpha=0.2)
    left = min(-12.0, float(np.nanmin(values)) - 1.0)
    right = max(2.0, float(np.nanmax(values)) + 1.0)
    axis.set_xlim(left, right)
    for position, value in zip(positions, values):
        if value < -0.8:
            x_position, alignment, color = value + 0.28, "left", "white"
        elif value > 0.8:
            x_position, alignment, color = value - 0.18, "right", "white"
        else:
            x_position, alignment, color = 0.18, "left", INK
        axis.text(
            x_position,
            position,
            _fmt_pct(value, 3 if abs(value) < 0.1 else 2),
            ha=alignment,
            va="center",
            fontsize=9,
            weight="bold",
            color=color,
        )

    cost_axis = axes[1]
    cost_plot = costs.iloc[::-1].copy()
    cost_positions = np.arange(len(cost_plot))
    cost_values = cost_plot["delta"].to_numpy(dtype=float)
    cost_colors = [
        FAVORABLE_COLOR if value < 0 else POSITIVE_COLOR for value in cost_values
    ]
    cost_axis.barh(
        cost_positions,
        cost_values,
        color=cost_colors,
        height=0.62,
    )
    cost_axis.axvline(0.0, color=INK, linewidth=1.0)
    cost_axis.set_yticks(cost_positions, cost_plot["component"].tolist(), fontsize=9)
    cost_axis.set_xlabel("écart sur 365 jours (unité monétaire du modèle)")
    cost_axis.set_title("D'où vient la différence de coût", fontsize=12, weight="bold")
    cost_axis.grid(axis="x", alpha=0.2)
    maximum_cost = max(abs(cost_values).max(), 1.0)
    for position, value in zip(cost_positions, cost_values):
        if value < -0.12 * maximum_cost:
            x_position = value + 0.035 * maximum_cost
            alignment = "left"
            color = "white"
        elif value > 0.12 * maximum_cost:
            x_position = value - 0.035 * maximum_cost
            alignment = "right"
            color = "white"
        elif value < 0:
            x_position = value - 0.035 * maximum_cost
            alignment = "right"
            color = INK
        else:
            x_position = value + 0.035 * maximum_cost
            alignment = "left"
            color = INK
        cost_axis.text(
            x_position,
            position,
            f"{value:+,.2f}".replace(",", " "),
            ha=alignment,
            va="center",
            fontsize=9,
            weight="bold",
            color=color,
        )
    mrp_constraints = float(mrp["constraint_violations"])
    v3_constraints = float(v3["constraint_violations"])
    total_cost_delta = float(
        tradeoffs.loc[
            tradeoffs["source_column"].eq("total_economic_exposure"), "delta"
        ].iloc[0]
    )
    risk_delta_pct = float(
        tradeoffs.loc[
            tradeoffs["source_column"].eq("supplier_risk_area"), "delta_pct"
        ].iloc[0]
    )
    fig.suptitle(
        (
            "V3 réduit les perturbations fournisseur calculées de "
            f"{_fmt_number(abs(risk_delta_pct), 2)} %, mais le coût du stock "
            "dépasse la baisse des achats"
        ),
        fontsize=15,
        weight="bold",
        y=1.01,
    )
    fig.text(
        0.07,
        0.02,
        (
            "Vert = amélioration ou économie ; rouge = contrepartie. "
            f"Contraintes détectées : {_fmt_number(mrp_constraints)} → "
            f"{_fmt_number(v3_constraints)} ; coût total sur 365 jours : "
            f"{'+' if total_cost_delta >= 0 else '-'}"
            f"{_fmt_number(abs(total_cost_delta), 2)}. Une seule réalisation simulée."
        ),
        fontsize=9,
        color="#49566b",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _save_figure(fig, path)
    return path


def _entity_coverage(
    summary: pd.DataFrame,
    *,
    family: str,
    metrics: Sequence[str],
) -> tuple[int, int]:
    selected = summary.loc[
        summary["family"].eq(family) & summary["metric"].isin(metrics)
    ]
    if selected.empty:
        raise ValueError(f"No comparison rows for {family}/{list(metrics)}")
    changed = selected.groupby("entity_id")["has_difference"].any()
    return int(changed.sum()), int(len(changed))


def _propagation_frame(summary: pd.DataFrame) -> pd.DataFrame:
    definitions = (
        ("Calculs MRP locaux", "mrp_state", ("control_order_multiplier",)),
        ("Flux de commande", "mrp_orders", ("release_qty",)),
        ("Liaisons expédiées", "supplier_shipments", ("shipped_qty",)),
        ("Arrivées de composants", "plant_input_arrivals", ("arrived_qty",)),
        (
            "Calendriers de consommation",
            "plant_input_consumption",
            ("consumed_qty",),
        ),
        ("Calendriers de production", "plant_output", ("produced_qty",)),
        (
            "Service ou commandes client en attente",
            "customer_service",
            ("served_qty", "backlog_end_qty"),
        ),
    )
    rows = []
    for label, family, metrics in definitions:
        changed, total = _entity_coverage(summary, family=family, metrics=metrics)
        rows.append(
            {
                "stage": label,
                "family": family,
                "changed": changed,
                "total": total,
                "changed_pct": 100.0 * changed / total if total else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _plot_propagation(frame: pd.DataFrame, output: Path) -> Path:
    path = output / "02_couverture_des_differences.png"
    plot = frame.iloc[::-1].copy()
    positions = np.arange(len(plot))
    fig, axis = plt.subplots(figsize=(12.5, 7.2))
    axis.barh(positions, [100.0] * len(plot), color="#e3e8ef", height=0.64)
    axis.barh(
        positions,
        plot["changed_pct"],
        color=V3_COLOR,
        height=0.64,
    )
    axis.set_yticks(positions, plot["stage"].tolist(), fontsize=10)
    axis.set_xlim(0, 108)
    axis.set_xlabel("part des éléments qui changent (%)")
    axis.set_title(
        "Part des éléments qui changent dans chaque domaine",
        fontsize=15,
        weight="bold",
        pad=16,
    )
    axis.grid(axis="x", alpha=0.2)
    for position, row in enumerate(plot.itertuples()):
        axis.text(
            min(float(row.changed_pct) + 1.3, 101.0),
            position,
            f"{row.changed}/{row.total}",
            va="center",
            fontsize=10,
            weight="bold",
        )
    fig.text(
        0.1,
        0.02,
        (
            "Chaque ligne compte des objets différents : commandes, routes, composants "
            "ou produits. Cette vue indique où se trouvent les changements ; elle ne "
            "signifie pas qu'une ligne provoque la suivante."
        ),
        fontsize=9,
        color="#49566b",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _save_figure(fig, path)
    return path


def _shipment_sums(frame: pd.DataFrame, days: int) -> pd.DataFrame:
    keys = ["src_node_id", "dst_node_id", "item_id", "uom"]
    work = frame.copy()
    work["day"] = pd.to_numeric(work["day"], errors="raise").astype(int)
    work["shipped_qty"] = pd.to_numeric(work["shipped_qty"], errors="coerce").fillna(
        0.0
    )
    all_horizon = work.groupby(keys, as_index=False)["shipped_qty"].sum()
    all_horizon = all_horizon.rename(columns={"shipped_qty": "all_qty"})
    measured = work.loc[work["day"].between(0, days - 1)]
    measured = measured.groupby(keys, as_index=False)["shipped_qty"].sum()
    measured = measured.rename(columns={"shipped_qty": "measured_qty"})
    return all_horizon.merge(measured, on=keys, how="outer").fillna(0.0)


def _horizon_deferral_frame(
    mrp_dir: Path,
    v3_dir: Path,
    days: int,
) -> pd.DataFrame:
    filename = "production_supplier_shipments_daily.csv"
    mrp = _shipment_sums(_read_csv(_data_path(mrp_dir, filename)), days)
    v3 = _shipment_sums(_read_csv(_data_path(v3_dir, filename)), days)
    keys = ["src_node_id", "dst_node_id", "item_id", "uom"]
    paired = mrp.merge(v3, on=keys, how="outer", suffixes=("_mrp", "_v3"))
    paired = paired.fillna(0.0)
    paired["delta_measured"] = paired["measured_qty_v3"] - paired["measured_qty_mrp"]
    paired["delta_all"] = paired["all_qty_v3"] - paired["all_qty_mrp"]
    deferred = paired.loc[
        paired["dst_node_id"].astype(str).str.startswith("M-")
        & paired["delta_measured"].abs().gt(TOLERANCE)
        & paired["delta_all"].abs().le(TOLERANCE)
    ].copy()
    deferred["lane"] = (
        deferred["src_node_id"].astype(str)
        + " → "
        + deferred["dst_node_id"].astype(str)
        + "\n"
        + deferred["item_id"].astype(str).str.replace("item:", "article ")
        + " ("
        + deferred["uom"].astype(str)
        + ")"
    )
    return deferred.sort_values(["uom", "src_node_id", "item_id"])


def _plot_horizon_deferral(frame: pd.DataFrame, output: Path, days: int) -> Path:
    if frame.empty:
        raise ValueError("No end-of-horizon shipment deferral was detected.")
    path = output / "03_report_apres_horizon.png"
    fig, axis = plt.subplots(figsize=(14.5, 6.0))
    axis.axis("off")
    rows = []
    for row in frame.itertuples():
        unit = str(row.uom)
        after_horizon = float(row.delta_all) - float(row.delta_measured)
        rows.append(
            [
                (
                    f"{row.src_node_id} → {row.dst_node_id}\n"
                    f"{str(row.item_id).replace('item:', 'article ')} ({unit})"
                ),
                f"{_fmt_number(float(row.delta_measured))} {unit}",
                f"+{_fmt_number(after_horizon)} {unit}",
                f"{_fmt_number(float(row.delta_all))} {unit}",
            ]
        )
    table = axis.table(
        cellText=rows,
        colLabels=(
            "Flux fournisseur / article",
            f"Écart à la fin de J{days - 1}",
            f"Compensation après J{days - 1}",
            "Écart avec les livraisons futures",
        ),
        cellLoc="center",
        colLoc="center",
        loc="center",
        colWidths=[0.38, 0.2, 0.23, 0.19],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 2.15)
    for (row_index, column_index), cell in table.get_celld().items():
        if row_index == 0:
            cell.set_facecolor(INK)
            cell.set_text_props(weight="bold", color="white")
        elif column_index == 1:
            cell.set_facecolor("#f5d8d5")
            cell.set_text_props(weight="bold", color=POSITIVE_COLOR)
        elif column_index == 2:
            cell.set_facecolor("#dcece7")
            cell.set_text_props(weight="bold", color=FAVORABLE_COLOR)
        elif column_index == 3:
            cell.set_facecolor("#cce5dc")
            cell.set_text_props(weight="bold", color=FAVORABLE_COLOR)
        elif row_index % 2 == 0:
            cell.set_facecolor("#f4f6f9")
    fig.suptitle(
        "Quatre baisses apparentes sont exactement compensées après la date de fin",
        fontsize=15,
        weight="bold",
        y=0.96,
    )
    fig.text(
        0.08,
        0.05,
        (
            "Décision métier : toujours inclure les livraisons prévues après "
            "la date de fin, sinon un report peut être confondu avec une économie. "
            "Chaque ligne conserve sa propre unité ; aucune quantité hétérogène "
            "n'est additionnée ni comparée par une longueur de barre."
        ),
        fontsize=9,
        color="#49566b",
    )
    fig.tight_layout(rect=(0.04, 0.09, 0.96, 0.9))
    _save_figure(fig, path)
    return path


def _lot_amplification_frame(
    summary: pd.DataFrame,
    tables_dir: Path,
    mrp_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    candidates = summary.loc[
        summary["family"].eq("plant_output")
        & summary["metric"].eq("produced_qty")
        & summary["has_difference"]
        & pd.to_numeric(summary["delta"], errors="coerce").abs().le(TOLERANCE)
    ].copy()
    if candidates.empty:
        raise ValueError("No equal-total shifted production lot was found.")
    candidates["amplitude"] = pd.to_numeric(
        candidates["max_abs_daily_delta"], errors="coerce"
    ).abs()
    selected = candidates.sort_values("amplitude", ascending=False).iloc[0]
    node_id = str(selected["node_id"])
    item_id = str(selected["item_id"])
    output = _read_csv(tables_dir / "plant_output_paired.csv")
    output = output.loc[
        output["node_id"].astype(str).eq(node_id)
        & output["item_id"].astype(str).eq(item_id)
    ].copy()
    output["day"] = pd.to_numeric(output["day"], errors="raise").astype(int)
    output["produced_qty_delta"] = pd.to_numeric(
        output["produced_qty_delta"], errors="coerce"
    ).fillna(0.0)
    changed = output.loc[output["produced_qty_delta"].abs().gt(TOLERANCE)]
    if changed.empty:
        raise ValueError("Selected lot has no changed production day.")
    negative_days = changed.loc[changed["produced_qty_delta"].lt(0), "day"]
    positive_days = changed.loc[changed["produced_qty_delta"].gt(0), "day"]
    start_day = int(negative_days.min())
    end_day = int(positive_days.max())
    lot_qty = float(changed["produced_qty_delta"].abs().max())

    stocks = _read_csv(tables_dir / "plant_input_stock_paired.csv")
    stocks = stocks.loc[stocks["node_id"].astype(str).eq(node_id)].copy()
    stocks["day"] = pd.to_numeric(stocks["day"], errors="raise").astype(int)
    stocks["stock_end_of_day_delta"] = pd.to_numeric(
        stocks["stock_end_of_day_delta"], errors="coerce"
    ).fillna(0.0)
    uom = _read_csv(_data_path(mrp_dir, "production_input_consumption_daily.csv"))[
        ["node_id", "item_id", "uom"]
    ].drop_duplicates()
    stock_rows = []
    for component, group in stocks.groupby("item_id", sort=True):
        maximum_index = group["stock_end_of_day_delta"].idxmax()
        maximum = float(group.loc[maximum_index, "stock_end_of_day_delta"])
        if maximum <= TOLERANCE:
            continue
        final = group.sort_values("day").iloc[-1]
        unit_rows = uom.loc[
            uom["node_id"].astype(str).eq(node_id)
            & uom["item_id"].astype(str).eq(str(component)),
            "uom",
        ]
        unit = str(unit_rows.iloc[0]) if not unit_rows.empty else ""
        stock_rows.append(
            {
                "node_id": node_id,
                "item_id": str(component),
                "max_temporary_excess": maximum,
                "max_day": int(group.loc[maximum_index, "day"]),
                "uom": unit,
                "final_delta": float(final["stock_end_of_day_delta"]),
            }
        )
    components = pd.DataFrame(stock_rows).sort_values(["uom", "item_id"])
    context = {
        "node_id": node_id,
        "item_id": item_id,
        "mrp_day": start_day,
        "v3_day": end_day,
        "shift_days": end_day - start_day,
        "lot_qty": lot_qty,
    }
    return output, components, context


def _display_quantity(value: float, unit: str) -> tuple[float, str]:
    if unit.upper() == "G" and abs(value) >= 1000.0:
        return value / 1000.0, "kg équiv."
    return value, unit


def _plot_lot_amplification(
    production: pd.DataFrame,
    components: pd.DataFrame,
    context: Mapping[str, Any],
    output: Path,
) -> Path:
    path = output / "04_amplification_par_lotification.png"
    start = int(context["mrp_day"]) - 8
    end = int(context["v3_day"]) + 8
    zoom = production.loc[production["day"].between(start, end)].copy()
    fig = plt.figure(figsize=(14.0, 9.2))
    grid = fig.add_gridspec(2, 1, height_ratios=[1.25, 1.0], hspace=0.25)
    axis = fig.add_subplot(grid[0])
    axis.step(
        zoom["day"],
        zoom["produced_qty_mrp"],
        where="mid",
        color=MRP_COLOR,
        linewidth=2.2,
        label="MRP",
    )
    axis.step(
        zoom["day"],
        zoom["produced_qty_v3"],
        where="mid",
        color=V3_COLOR,
        linewidth=2.2,
        label="V3",
    )
    common_lots = zoom.loc[
        pd.to_numeric(zoom["produced_qty_mrp"], errors="coerce").gt(TOLERANCE)
        & pd.to_numeric(zoom["produced_qty_mrp"], errors="coerce")
        .sub(pd.to_numeric(zoom["produced_qty_v3"], errors="coerce"))
        .abs()
        .le(TOLERANCE)
    ]
    axis.scatter(
        common_lots["day"],
        common_lots["produced_qty_mrp"],
        marker="D",
        s=54,
        facecolor="white",
        edgecolor=INK,
        linewidth=1.4,
        zorder=5,
        label="lot commun MRP / V3",
    )
    axis.axvspan(
        int(context["mrp_day"]),
        int(context["v3_day"]),
        color="#f0b45b",
        alpha=0.18,
    )
    axis.annotate(
        (
            f"lot de {_fmt_number(float(context['lot_qty']))} décalé de "
            f"{context['shift_days']} jours"
        ),
        xy=(int(context["v3_day"]), float(context["lot_qty"])),
        xytext=(int(context["mrp_day"]) - 5, float(context["lot_qty"]) * 1.18),
        arrowprops={"arrowstyle": "->", "color": INK},
        fontsize=10,
        weight="bold",
    )
    axis.set_ylabel("production journalière (UN)")
    axis.set_xlabel("jour")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False)
    axis.set_title(
        (
            f"{context['node_id']} / {str(context['item_id']).replace('item:', 'article ')} : "
            "un changement de date, pas de volume total"
        ),
        fontsize=12,
        weight="bold",
    )

    table_axis = fig.add_subplot(grid[1])
    table_axis.axis("off")
    shown = components.head(8).copy()
    cell_text = []
    for row in shown.itertuples():
        display, display_unit = _display_quantity(
            float(row.max_temporary_excess), str(row.uom)
        )
        final_display, final_unit = _display_quantity(
            float(row.final_delta), str(row.uom)
        )
        cell_text.append(
            [
                str(row.item_id).replace("item:", ""),
                f"+{_fmt_number(display, 1)} {display_unit}",
                f"J{row.max_day}",
                f"{_fmt_number(final_display, 1)} {final_unit}",
            ]
        )
    table = table_axis.table(
        cellText=cell_text,
        colLabels=(
            "Composant",
            "Surstock temporaire maximal",
            "Pic",
            "Écart à J364",
        ),
        cellLoc="center",
        colLoc="center",
        loc="center",
        colWidths=[0.16, 0.34, 0.14, 0.24],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.55)
    for (row, _column), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#dce8e7")
            cell.set_text_props(weight="bold", color=INK)
        elif row % 2 == 0:
            cell.set_facecolor("#f4f6f9")
    table_axis.set_title(
        "Conséquence cachée : des composants restent immobilisés pendant le report",
        fontsize=12,
        weight="bold",
        pad=10,
    )
    fig.suptitle(
        "La production par lots transforme un petit décalage en un effet stock très visible",
        fontsize=15,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.08,
        0.01,
        (
            "Les unités propres aux articles sont conservées et ne doivent pas être "
            "additionnées. L'effet est temporaire pour la plupart des composants."
        ),
        fontsize=9,
        color="#49566b",
    )
    _save_figure(fig, path)
    return path


def _risk_redistribution_frame(mrp_dir: Path, v3_dir: Path) -> pd.DataFrame:
    filename = "supplier_risk_events_applied_daily.csv"
    keys = ["supplier_id", "dst_node_id", "item_id", "edge_id"]

    def sums(run_dir: Path, suffix: str) -> pd.DataFrame:
        frame = _read_csv(_data_path(run_dir, filename))
        frame["lead_time_extra_days"] = pd.to_numeric(
            frame["lead_time_extra_days"], errors="coerce"
        ).fillna(0.0)
        result = frame.groupby(keys, as_index=False)["lead_time_extra_days"].sum()
        return result.rename(
            columns={"lead_time_extra_days": f"lead_time_extra_days_{suffix}"}
        )

    paired = (
        sums(mrp_dir, "mrp").merge(sums(v3_dir, "v3"), on=keys, how="outer").fillna(0.0)
    )
    paired["delta"] = (
        paired["lead_time_extra_days_v3"] - paired["lead_time_extra_days_mrp"]
    )
    paired = paired.loc[paired["delta"].abs().gt(TOLERANCE)].copy()

    def label(row: pd.Series) -> str:
        item = str(row["item_id"]).replace("item:", "article ")
        if str(row["supplier_id"]) == str(row["dst_node_id"]):
            return f"Amont {row['supplier_id']}\n{item}"
        return f"{row['supplier_id']} → {row['dst_node_id']}\n{item}"

    paired["scope_label"] = paired.apply(label, axis=1)
    return paired.sort_values("delta")


def _risk_episode_frame(
    mrp_dir: Path,
    v3_dir: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    events_filename = "supplier_state_dependent_risk_events.csv"
    daily_filename = "supplier_risk_events_applied_daily.csv"

    def event_groups(run_dir: Path) -> pd.DataFrame:
        frame = _read_csv(_data_path(run_dir, events_filename))
        frame = frame.loc[
            frame["risk_type"].astype(str).eq("lead_time_extra_days")
        ].copy()
        for column in (
            "trigger_day",
            "start_day",
            "end_day",
            "multiplier",
            "trigger_value",
        ):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        keys = [
            "supplier_id",
            "item_id",
            "trigger_day",
            "start_day",
            "end_day",
        ]
        grouped = frame.groupby(keys, as_index=False).agg(
            extra_days=("multiplier", "sum"),
            trigger_value=("trigger_value", "max"),
            event_ids=("event_id", lambda values: "|".join(map(str, values))),
        )
        grouped["burden"] = grouped["extra_days"] * (
            grouped["end_day"] - grouped["start_day"] + 1
        )
        return grouped

    mrp_events = event_groups(mrp_dir)
    v3_events = event_groups(v3_dir)
    v3_keys = set(
        zip(
            v3_events["supplier_id"].astype(str),
            v3_events["item_id"].astype(str),
            v3_events["trigger_day"].astype(int),
        )
    )
    mrp_only = pd.Series(
        [
            (str(row.supplier_id), str(row.item_id), int(row.trigger_day))
            not in v3_keys
            for row in mrp_events.itertuples()
        ],
        index=mrp_events.index,
    )
    candidates = mrp_events.loc[mrp_events["trigger_day"].ge(35) & mrp_only].copy()
    if candidates.empty:
        raise ValueError("No illustrative state-dependent risk episode was found.")
    selected = candidates.sort_values(
        ["burden", "trigger_day"], ascending=[False, True]
    ).iloc[0]
    supplier_id = str(selected["supplier_id"])
    item_id = str(selected["item_id"])
    later_v3 = v3_events.loc[
        v3_events["supplier_id"].astype(str).eq(supplier_id)
        & v3_events["item_id"].astype(str).eq(item_id)
        & v3_events["trigger_day"].gt(float(selected["trigger_day"]))
    ].sort_values("trigger_day")
    comparison = later_v3.iloc[0] if not later_v3.empty else None

    mrp_daily_raw = _read_csv(_data_path(mrp_dir, daily_filename))
    selected_event_ids = str(selected["event_ids"]).split("|")
    matching = mrp_daily_raw.loc[
        mrp_daily_raw["supplier_id"].astype(str).eq(supplier_id)
        & mrp_daily_raw["item_id"].astype(str).eq(item_id)
        & mrp_daily_raw["event_ids"]
        .astype(str)
        .map(lambda value: any(event_id in value for event_id in selected_event_ids))
    ]
    if matching.empty:
        raise ValueError("Selected risk episode has no physically applied row.")
    scope = (
        matching.groupby(["dst_node_id", "edge_id"], as_index=False)
        .size()
        .sort_values("size", ascending=False)
        .iloc[0]
    )
    dst_node_id = str(scope["dst_node_id"])
    edge_id = str(scope["edge_id"])

    def daily(run_dir: Path, suffix: str) -> pd.DataFrame:
        frame = _read_csv(_data_path(run_dir, daily_filename))
        frame = frame.loc[
            frame["supplier_id"].astype(str).eq(supplier_id)
            & frame["item_id"].astype(str).eq(item_id)
            & frame["dst_node_id"].astype(str).eq(dst_node_id)
            & frame["edge_id"].astype(str).eq(edge_id)
        ].copy()
        frame["day"] = pd.to_numeric(frame["day"], errors="raise").astype(int)
        frame["lead_time_extra_days"] = pd.to_numeric(
            frame["lead_time_extra_days"], errors="coerce"
        ).fillna(0.0)
        return (
            frame.groupby("day", as_index=False)["lead_time_extra_days"]
            .max()
            .rename(columns={"lead_time_extra_days": f"extra_days_{suffix}"})
        )

    mrp_daily = daily(mrp_dir, "mrp")
    v3_daily = daily(v3_dir, "v3")
    last_comparison_day = (
        int(comparison["end_day"])
        if comparison is not None
        else int(selected["end_day"])
    )
    first_day = max(0, int(selected["trigger_day"]) - 12)
    last_day = last_comparison_day + 10
    frame = pd.DataFrame({"day": range(first_day, last_day + 1)})
    frame = (
        frame.merge(mrp_daily, on="day", how="left")
        .merge(v3_daily, on="day", how="left")
        .fillna(0.0)
    )
    context = {
        "supplier_id": supplier_id,
        "dst_node_id": dst_node_id,
        "item_id": item_id,
        "mrp_trigger_day": int(selected["trigger_day"]),
        "mrp_start_day": int(selected["start_day"]),
        "mrp_end_day": int(selected["end_day"]),
        "mrp_trigger_ratio": float(selected["trigger_value"]),
        "mrp_extra_days": float(selected["extra_days"]),
        "mrp_scope_cumulative": float(mrp_daily["extra_days_mrp"].sum()),
        "v3_scope_cumulative": float(v3_daily["extra_days_v3"].sum()),
    }
    if comparison is not None:
        context.update(
            {
                "v3_trigger_day": int(comparison["trigger_day"]),
                "v3_start_day": int(comparison["start_day"]),
                "v3_end_day": int(comparison["end_day"]),
                "v3_trigger_ratio": float(comparison["trigger_value"]),
                "v3_extra_days": float(comparison["extra_days"]),
                "trigger_shift_days": int(comparison["trigger_day"])
                - int(selected["trigger_day"]),
            }
        )
    return frame, context


def _plot_risk_redistribution(
    frame: pd.DataFrame,
    episode: pd.DataFrame,
    episode_context: Mapping[str, Any],
    *,
    risk_change_pct: float,
    output: Path,
) -> Path:
    if frame.empty:
        raise ValueError("No supplier-risk redistribution was detected.")
    path = output / "05_redistribution_du_risque.png"
    positions = np.arange(len(frame))
    width = 0.36
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15.0, 7.0),
        gridspec_kw={"width_ratios": [1.05, 1.0]},
    )
    episode_axis = axes[0]
    episode_axis.step(
        episode["day"],
        episode["extra_days_mrp"],
        where="post",
        color=MRP_COLOR,
        linewidth=2.2,
        label="MRP",
    )
    episode_axis.step(
        episode["day"],
        episode["extra_days_v3"],
        where="post",
        color=V3_COLOR,
        linewidth=2.2,
        label="V3",
    )
    episode_axis.axvline(
        int(episode_context["mrp_trigger_day"]),
        color=MRP_COLOR,
        linestyle="--",
        linewidth=1.2,
    )
    if "v3_trigger_day" in episode_context:
        episode_axis.axvline(
            int(episode_context["v3_trigger_day"]),
            color=V3_COLOR,
            linestyle="--",
            linewidth=1.2,
        )
        episode_axis.annotate(
            f"déclenchement décalé de {episode_context['trigger_shift_days']} jours",
            xy=(
                int(episode_context["v3_trigger_day"]),
                float(episode_context["v3_extra_days"]),
            ),
            xytext=(int(episode_context["mrp_trigger_day"]) - 5, 9.2),
            arrowprops={"arrowstyle": "->", "color": INK},
            fontsize=9,
            weight="bold",
        )
    episode_axis.set_title(
        (
            f"{episode_context['supplier_id']} → {episode_context['dst_node_id']}\n"
            f"{str(episode_context['item_id']).replace('item:', 'article ')}"
        ),
        fontsize=11,
        weight="bold",
    )
    episode_axis.set_xlabel("jour")
    episode_axis.set_ylabel("retard ajouté par le modèle (jours)")
    episode_axis.set_ylim(-0.4, 10.2)
    episode_axis.grid(alpha=0.2)
    episode_axis.legend(frameon=False)

    axis = axes[1]
    axis.barh(
        positions - width / 2,
        frame["lead_time_extra_days_mrp"],
        height=width,
        color=MRP_COLOR,
        label="MRP",
    )
    axis.barh(
        positions + width / 2,
        frame["lead_time_extra_days_v3"],
        height=width,
        color=V3_COLOR,
        label="V3",
    )
    axis.set_yticks(positions, frame["scope_label"].tolist(), fontsize=9)
    axis.set_xlabel("somme des jours de délai supplémentaire appliqués")
    axis.set_title("Retard ajouté cumulé par flux", fontsize=11, weight="bold")
    axis.grid(axis="x", alpha=0.2)
    axis.legend(frameon=False)
    maximum = max(
        float(frame["lead_time_extra_days_mrp"].max()),
        float(frame["lead_time_extra_days_v3"].max()),
    )
    for position, row in enumerate(frame.itertuples()):
        axis.text(
            max(row.lead_time_extra_days_mrp, row.lead_time_extra_days_v3)
            + maximum * 0.025,
            position,
            f"écart {row.delta:+.0f}",
            va="center",
            fontsize=9,
            color=FAVORABLE_COLOR if row.delta < 0 else POSITIVE_COLOR,
            weight="bold",
        )
    fig.suptitle(
        ("V3 décale une période de retard fournisseur et réduit le total simulé"),
        fontsize=15,
        weight="bold",
        y=1.01,
    )
    fig.text(
        0.06,
        0.02,
        (
            "Score global de perturbations fournisseur calculées : "
            f"{_fmt_pct(risk_change_pct)}. Les retards sont recalculés à partir des "
            "stocks, commandes et capacités simulés ; ils ne sont pas fixés à l'avance. "
            "Il ne s'agit pas d'une probabilité d'incident réel."
        ),
        fontsize=9,
        color="#49566b",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _save_figure(fig, path)
    return path


def _daily_change_counts(
    frame: pd.DataFrame,
    metrics: Sequence[str],
    days: int,
    *,
    include_presence: bool = False,
) -> np.ndarray:
    work = frame.copy()
    work["day"] = pd.to_numeric(work["day"], errors="coerce")
    work = work.loc[work["day"].between(0, days - 1)].copy()
    changed = pd.Series(False, index=work.index)
    for metric in metrics:
        if metric in work:
            changed |= pd.to_numeric(work[metric], errors="coerce").abs().gt(TOLERANCE)
    if include_presence and "_merge" in work:
        changed |= work["_merge"].astype(str).ne("both")
    counts = (
        work.loc[changed]
        .groupby(work.loc[changed, "day"].astype(int))
        .size()
        .reindex(range(days), fill_value=0)
    )
    return counts.to_numpy(dtype=float)


def _timeline_frame(
    tables_dir: Path,
    v3_dir: Path,
    days: int,
) -> tuple[pd.DataFrame, list[str], np.ndarray]:
    commands = _read_csv(_data_path(v3_dir, "canonical_closed_loop_commands.csv"))
    commands["effective_day"] = pd.to_numeric(
        commands["effective_day"], errors="coerce"
    )
    for column in (
        "control_continuous_requested_order_multiplier",
        "control_continuous_requested_production_target_multiplier",
        "active",
    ):
        commands[column] = pd.to_numeric(commands[column], errors="coerce")
    commands = commands.loc[commands["effective_day"].between(0, days - 1)]
    command_daily = commands.groupby(commands["effective_day"].astype(int)).agg(
        order_multiplier=("control_continuous_requested_order_multiplier", "min"),
        production_multiplier=(
            "control_continuous_requested_production_target_multiplier",
            "min",
        ),
        active=("active", "max"),
    )
    command_daily = command_daily.reindex(range(days))
    command_daily["order_multiplier"] = pd.to_numeric(
        command_daily["order_multiplier"], errors="coerce"
    ).fillna(1.0)
    command_daily["production_multiplier"] = pd.to_numeric(
        command_daily["production_multiplier"], errors="coerce"
    ).fillna(1.0)
    command_daily["active"] = pd.to_numeric(
        command_daily["active"], errors="coerce"
    ).fillna(0.0)
    command_daily["day"] = range(days)
    command_daily["order_reduction_pct"] = 100.0 * (
        1.0 - command_daily["order_multiplier"]
    )
    command_daily["production_reduction_pct"] = 100.0 * (
        1.0 - command_daily["production_multiplier"]
    )

    definitions = (
        (
            "Commandes MRP",
            "mrp_orders_paired.csv",
            ("release_qty_delta",),
            False,
        ),
        (
            "Expéditions",
            "supplier_shipments_paired.csv",
            ("shipped_qty_delta",),
            True,
        ),
        (
            "Arrivées usine",
            "plant_input_arrivals_paired.csv",
            ("arrived_qty_delta",),
            False,
        ),
        (
            "Consommations",
            "plant_input_consumption_paired.csv",
            ("consumed_qty_delta",),
            False,
        ),
        (
            "Productions",
            "plant_output_paired.csv",
            ("produced_qty_delta",),
            False,
        ),
        (
            "Perturbations fournisseur calculées",
            "supplier_risk_paired.csv",
            (
                "lead_time_extra_days_delta",
                "availability_multiplier_delta",
                "capacity_multiplier_delta",
            ),
            True,
        ),
        (
            "Service / commandes client en attente",
            "customer_service_paired.csv",
            ("served_qty_delta", "backlog_end_qty_delta"),
            False,
        ),
    )
    labels = []
    rows = []
    for label, filename, metrics, presence in definitions:
        frame = _read_csv(tables_dir / filename)
        counts = _daily_change_counts(frame, metrics, days, include_presence=presence)
        nonzero = np.flatnonzero(counts > 0)
        first = f"J{int(nonzero[0])}" if len(nonzero) else "aucun"
        labels.append(f"{label} ({first})")
        rows.append(counts)
        command_daily[f"changed_{filename.removesuffix('_paired.csv')}"] = counts
    return command_daily.reset_index(drop=True), labels, np.vstack(rows)


def _plot_causal_timeline(
    daily: pd.DataFrame,
    labels: Sequence[str],
    matrix: np.ndarray,
    output: Path,
) -> Path:
    path = output / "06_chronologie_des_divergences.png"
    fig = plt.figure(figsize=(15.0, 8.3))
    grid = fig.add_gridspec(2, 1, height_ratios=[0.9, 1.7], hspace=0.18)
    top = fig.add_subplot(grid[0])
    top.plot(
        daily["day"],
        daily["order_reduction_pct"],
        color="#d7793f",
        linewidth=1.8,
        label="réduction demandée sur les commandes",
    )
    top.plot(
        daily["day"],
        daily["production_reduction_pct"],
        color="#6f5aa8",
        linewidth=1.6,
        label="réduction demandée sur la cible de production",
    )
    top.fill_between(
        daily["day"],
        0,
        daily["order_reduction_pct"],
        color="#d7793f",
        alpha=0.12,
    )
    top.set_ylabel("correction V3 (%)")
    top.set_xlim(0, int(daily["day"].max()))
    top.grid(alpha=0.2)
    top.legend(frameon=False, ncol=2, loc="upper left")
    top.set_title(
        "Commande calculée au jour J, appliquée au moteur au jour J+1",
        fontsize=11,
        weight="bold",
    )

    heat = fig.add_subplot(grid[1], sharex=top)
    transformed = np.log1p(matrix)
    vmax = max(float(transformed.max()), 1.0)
    image = heat.imshow(
        transformed,
        aspect="auto",
        interpolation="nearest",
        cmap="YlGnBu",
        vmin=0.0,
        vmax=vmax,
        extent=(0, int(daily["day"].max()), len(labels) - 0.5, -0.5),
    )
    heat.set_yticks(np.arange(len(labels)), labels, fontsize=9)
    heat.set_xlabel("jour de simulation")
    heat.set_ylabel("étape physique")
    colorbar = fig.colorbar(image, ax=heat, pad=0.015)
    colorbar.set_label("nombre de lignes différentes (couleurs compressées)")
    fig.suptitle(
        "Quand les premières différences apparaissent entre MRP et V3",
        fontsize=15,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.08,
        0.01,
        (
            "Premières différences observées par domaine, sans les attribuer à une "
            "action unique. Les couleurs comptent des lignes et ne peuvent pas être "
            "comparées directement d'un domaine à l'autre. Le service et les commandes "
            "client en attente restent identiques."
        ),
        fontsize=9,
        color="#49566b",
    )
    _save_figure(fig, path)
    return path


def _service_buffer_frame(mrp_dir: Path, v3_dir: Path) -> pd.DataFrame:
    filename = "production_demand_service_daily.csv"

    def aggregate(run_dir: Path, suffix: str) -> pd.DataFrame:
        frame = _read_csv(_data_path(run_dir, filename))
        for column in (
            "demand_qty",
            "served_qty",
            "backlog_end_qty",
            "available_before_service_qty",
        ):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        result = frame.groupby(["node_id", "item_id"], as_index=False).agg(
            demand_qty=("demand_qty", "sum"),
            served_qty=("served_qty", "sum"),
            max_backlog=("backlog_end_qty", "max"),
            mean_available=("available_before_service_qty", "mean"),
        )
        return result.rename(
            columns={
                column: f"{column}_{suffix}"
                for column in (
                    "demand_qty",
                    "served_qty",
                    "max_backlog",
                    "mean_available",
                )
            }
        )

    paired = aggregate(mrp_dir, "mrp").merge(
        aggregate(v3_dir, "v3"), on=["node_id", "item_id"], how="outer"
    )
    for metric in ("demand_qty", "served_qty", "max_backlog", "mean_available"):
        paired[f"delta_{metric}"] = paired[f"{metric}_v3"] - paired[f"{metric}_mrp"]
    return paired


def _plot_service_buffer(frame: pd.DataFrame, output: Path) -> Path:
    path = output / "08_service_et_tampon_disponible.png"
    labels = frame["item_id"].astype(str).str.replace("item:", "article ")
    positions = np.arange(len(frame))
    width = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 6.2))
    axes[0].bar(
        positions - width / 2,
        frame["mean_available_mrp"],
        width,
        color=MRP_COLOR,
        label="MRP",
    )
    axes[0].bar(
        positions + width / 2,
        frame["mean_available_v3"],
        width,
        color=V3_COLOR,
        label="V3",
    )
    axes[0].set_xticks(positions, labels, rotation=0)
    axes[0].set_ylabel("quantité disponible moyenne avant service (UN)")
    axes[0].set_title("La réserve disponible diminue", weight="bold")
    axes[0].grid(axis="y", alpha=0.2)
    axes[0].legend(frameon=False)
    for position, row in enumerate(frame.itertuples()):
        axes[0].text(
            position,
            max(row.mean_available_mrp, row.mean_available_v3) * 1.015,
            f"{row.delta_mean_available:+.1f} UN",
            ha="center",
            fontsize=9,
            color=POSITIVE_COLOR,
            weight="bold",
        )

    axes[1].axis("off")
    served_delta = float(frame["delta_served_qty"].sum())
    backlog_delta = float(frame["delta_max_backlog"].abs().max())
    cards = (
        ("Quantité servie", f"écart {_fmt_number(served_delta, 3)} UN"),
        (
            "Commandes client en attente au maximum",
            f"écart {_fmt_number(backlog_delta, 3)} UN",
        ),
        (
            "Lecture métier",
            "service inchangé, mais marge de sécurité plus faible",
        ),
    )
    y = 0.82
    for title, value in cards:
        axes[1].text(
            0.05,
            y,
            title,
            fontsize=11,
            weight="bold",
            color=INK,
            transform=axes[1].transAxes,
        )
        axes[1].text(
            0.05,
            y - 0.1,
            value,
            fontsize=12,
            color=V3_COLOR if "inchangé" not in value else POSITIVE_COLOR,
            transform=axes[1].transAxes,
            wrap=True,
        )
        y -= 0.27
    fig.suptitle(
        "Un service identique peut masquer une petite baisse de la réserve",
        fontsize=15,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.08,
        0.02,
        (
            "La quantité disponible avant de servir le client peut diminuer avant que "
            "les livraisons ne se dégradent. L'effet reste faible dans cet essai."
        ),
        fontsize=9,
        color="#49566b",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    _save_figure(fig, path)
    return path


def _crisis_response_frame(
    v3_dir: Path,
    days: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    service = _read_csv(_data_path(v3_dir, "production_demand_service_daily.csv"))
    for column in (
        "day",
        "demand_qty",
        "served_qty",
        "backlog_end_qty",
    ):
        service[column] = pd.to_numeric(service[column], errors="coerce")
    item_summary = service.groupby(["item_id"], as_index=False).agg(
        max_backlog=("backlog_end_qty", "max")
    )
    selected = item_summary.sort_values("max_backlog", ascending=False).iloc[0]
    item_id = str(selected["item_id"])
    uom = "UN"
    service = service.loc[service["item_id"].astype(str).eq(item_id)]
    service = service.groupby("day", as_index=False).agg(
        demand_qty=("demand_qty", "sum"),
        served_qty=("served_qty", "sum"),
        backlog_end_qty=("backlog_end_qty", "sum"),
    )

    observations = _read_csv(
        _data_path(v3_dir, "canonical_closed_loop_observations.csv")
    )
    observations["day"] = pd.to_numeric(observations["day"], errors="coerce").astype(
        "Int64"
    )
    observations = observations[["day", "confirmed_regime"]]
    commands = _read_csv(_data_path(v3_dir, "canonical_closed_loop_commands.csv"))
    commands["effective_day"] = pd.to_numeric(
        commands["effective_day"], errors="coerce"
    ).astype("Int64")
    commands["active"] = pd.to_numeric(commands["active"], errors="coerce").fillna(0.0)
    commands = commands.groupby("effective_day", as_index=False)["active"].max()

    positive_backlog = service.loc[service["backlog_end_qty"].gt(TOLERANCE)]
    if positive_backlog.empty:
        raise ValueError("No client crisis was found for the crisis-response figure.")
    backlog_start = int(positive_backlog["day"].min())
    backlog_end = int(positive_backlog["day"].max())
    peak = positive_backlog.loc[positive_backlog["backlog_end_qty"].idxmax()]
    crisis_days = observations.loc[
        observations["confirmed_regime"].astype(str).eq("CRISIS"), "day"
    ].dropna()
    crisis_recognition_day = int(crisis_days.min())
    active_days = commands.loc[commands["active"].gt(0.0), "effective_day"].dropna()
    first_active_day = int(active_days.min())
    last_day = min(days - 1, max(first_active_day + 12, backlog_end + 12))
    frame = pd.DataFrame({"day": range(0, last_day + 1)})
    frame = frame.merge(service, on="day", how="left")
    frame = frame.merge(observations, on="day", how="left")
    frame = frame.merge(commands, left_on="day", right_on="effective_day", how="left")
    frame["active"] = frame["active"].fillna(0.0)
    frame["crisis_detected"] = (
        frame["confirmed_regime"].astype(str).eq("CRISIS").astype(float)
    )
    context = {
        "item_id": item_id,
        "uom": uom,
        "backlog_start_day": backlog_start,
        "backlog_end_day": backlog_end,
        "backlog_peak_day": int(peak["day"]),
        "backlog_peak_qty": float(peak["backlog_end_qty"]),
        "crisis_recognition_day": crisis_recognition_day,
        "first_active_effective_day": first_active_day,
        "zero_service_days": int(
            (
                service["demand_qty"].gt(TOLERANCE)
                & service["served_qty"].le(TOLERANCE)
            ).sum()
        ),
        "active_during_backlog_days": int(
            commands.loc[
                commands["effective_day"].between(backlog_start, backlog_end)
                & commands["active"].gt(0.0)
            ].shape[0]
        ),
    }
    return frame, context


def _plot_crisis_response(
    frame: pd.DataFrame,
    context: Mapping[str, Any],
    output: Path,
) -> Path:
    path = output / "07_reponse_a_la_crise.png"
    fig = plt.figure(figsize=(14.5, 8.0))
    grid = fig.add_gridspec(2, 1, height_ratios=[1.5, 0.55], hspace=0.18)
    axis = fig.add_subplot(grid[0])
    axis.bar(
        frame["day"],
        frame["demand_qty"],
        color="#d9dee7",
        width=0.85,
        label="demande du jour",
    )
    axis.plot(
        frame["day"],
        frame["served_qty"],
        color=V3_COLOR,
        linewidth=2.1,
        marker="o",
        markersize=3.5,
        label="quantité servie",
    )
    backlog_axis = axis.twinx()
    backlog_axis.fill_between(
        frame["day"],
        0,
        frame["backlog_end_qty"],
        color=POSITIVE_COLOR,
        alpha=0.22,
        label="commandes en attente en fin de jour",
    )
    backlog_axis.plot(
        frame["day"],
        frame["backlog_end_qty"],
        color=POSITIVE_COLOR,
        linewidth=1.7,
    )
    axis.set_ylabel(f"demande / servi ({context['uom']})")
    backlog_axis.set_ylabel(
        f"commandes en attente ({context['uom']})", color=POSITIVE_COLOR
    )
    axis.grid(alpha=0.2)
    handles, labels = axis.get_legend_handles_labels()
    backlog_handles, backlog_labels = backlog_axis.get_legend_handles_labels()
    axis.legend(handles + backlog_handles, labels + backlog_labels, frameon=False)
    backlog_axis.annotate(
        (
            f"pic : {_fmt_number(float(context['backlog_peak_qty']), 1)} "
            f"{context['uom']} à J{context['backlog_peak_day']}"
        ),
        xy=(
            int(context["backlog_peak_day"]),
            float(context["backlog_peak_qty"]),
        ),
        xytext=(4, float(context["backlog_peak_qty"]) * 0.62),
        arrowprops={"arrowstyle": "->", "color": INK},
        fontsize=9,
        weight="bold",
    )

    status = fig.add_subplot(grid[1], sharex=axis)
    status.fill_between(
        frame["day"],
        0.56,
        0.9,
        where=frame["crisis_detected"].gt(0.0),
        step="mid",
        color="#e3a33a",
        alpha=0.85,
        label="crise reconnue",
    )
    status.fill_between(
        frame["day"],
        0.08,
        0.42,
        where=frame["active"].gt(0.0),
        step="mid",
        color=FAVORABLE_COLOR,
        alpha=0.9,
        label="décision V3 différente du MRP",
    )
    status.set_yticks([0.25, 0.73], ["commande", "détection"])
    status.set_ylim(0, 1)
    status.set_xlabel("jour")
    status.grid(axis="x", alpha=0.2)
    status.axvline(
        int(context["crisis_recognition_day"]),
        color="#9b6414",
        linestyle="--",
        linewidth=1.2,
    )
    status.axvline(
        int(context["first_active_effective_day"]),
        color=FAVORABLE_COLOR,
        linestyle="--",
        linewidth=1.2,
    )
    status.text(
        int(context["crisis_recognition_day"]),
        0.96,
        f"crise vue J{context['crisis_recognition_day']}",
        ha="center",
        va="bottom",
        fontsize=9,
        color="#9b6414",
        weight="bold",
    )
    status.text(
        int(context["first_active_effective_day"]),
        0.48,
        f"1er changement J{context['first_active_effective_day']}",
        ha="center",
        va="bottom",
        fontsize=9,
        color=FAVORABLE_COLOR,
        weight="bold",
    )
    fig.suptitle(
        (
            f"La crise est détectée à J{context['crisis_recognition_day']}, "
            "mais la première décision différente est appliquée à "
            f"J{context['first_active_effective_day']}, après la fin des commandes "
            "en attente à "
            f"J{context['backlog_end_day']}"
        ),
        fontsize=15,
        weight="bold",
        y=0.99,
    )
    fig.text(
        0.07,
        0.01,
        (
            "Résultat actionnable : le réglage actuel ne change aucune décision "
            "pendant que des commandes client sont en attente. J36 n'est pas un délai "
            "de récupération ; c'est seulement le premier changement observé ensuite."
        ),
        fontsize=9,
        color="#49566b",
    )
    _save_figure(fig, path)
    return path


def _key_results(
    *,
    tradeoffs: pd.DataFrame,
    propagation: pd.DataFrame,
    deferrals: pd.DataFrame,
    lot_context: Mapping[str, Any],
    components: pd.DataFrame,
    risks: pd.DataFrame,
    risk_episode_context: Mapping[str, Any],
    crisis_context: Mapping[str, Any],
    service: pd.DataFrame,
    mrp: pd.Series,
    v3: pd.Series,
) -> pd.DataFrame:
    trade = tradeoffs.set_index("source_column")
    unit_components = components.loc[components["uom"].astype(str).eq("UN")]
    top_component = unit_components.loc[
        unit_components["max_temporary_excess"].idxmax()
    ]
    return pd.DataFrame(
        [
            {
                "result": "service_mean_delta",
                "value": float(trade.loc["mean_service", "delta"]),
                "unit": "ratio",
                "business_reading": "service moyen identique",
            },
            {
                "result": "simulated_supplier_penalty_index_delta_pct",
                "value": float(trade.loc["supplier_risk_area", "delta_pct"]),
                "unit": "%",
                "business_reading": (
                    "indice simulé de pénalités fournisseur réduit ; "
                    "ce n'est pas une probabilité observée"
                ),
            },
            {
                "result": "constraint_violation_delta",
                "value": float(v3["constraint_violations"])
                - float(mrp["constraint_violations"]),
                "unit": "violations",
                "business_reading": "contrepartie opérationnelle",
            },
            {
                "result": "economic_exposure_delta",
                "value": float(trade.loc["total_economic_exposure", "delta"]),
                "unit": "monnaie",
                "business_reading": "surcoût modélisé",
            },
            {
                "result": "deferred_scope_count",
                "value": float(len(deferrals)),
                "unit": "corridors/article",
                "business_reading": "baisses apparentes avant J364",
            },
            {
                "result": "deferred_scope_count_reconciled",
                "value": float(deferrals["delta_all"].abs().le(TOLERANCE).sum()),
                "unit": "corridors/article",
                "business_reading": "pipeline futur exactement réconcilié",
            },
            {
                "result": "shifted_lot_qty",
                "value": float(lot_context["lot_qty"]),
                "unit": "UN",
                "business_reading": (
                    f"lot décalé de {lot_context['shift_days']} jours"
                ),
            },
            {
                "result": "largest_temporary_un_component_excess",
                "value": float(top_component["max_temporary_excess"]),
                "unit": str(top_component["uom"]),
                "business_reading": (
                    "maximum parmi les composants exprimés en UN : article "
                    f"{str(top_component['item_id']).replace('item:', '')}"
                ),
            },
            {
                "result": "supplier_penalty_scope_count_changed",
                "value": float(len(risks)),
                "unit": "périmètres",
                "business_reading": "redistribution locale des pénalités simulées",
            },
            {
                "result": "illustrative_risk_trigger_shift_days",
                "value": float(risk_episode_context["trigger_shift_days"]),
                "unit": "jours",
                "business_reading": "épisode endogène déclenché plus tard",
            },
            {
                "result": "illustrative_risk_scope_burden_delta",
                "value": float(risk_episode_context["v3_scope_cumulative"])
                - float(risk_episode_context["mrp_scope_cumulative"]),
                "unit": "jours de délai cumulés",
                "business_reading": "charge annuelle du périmètre illustratif",
            },
            {
                "result": "crisis_active_command_days",
                "value": float(crisis_context["active_during_backlog_days"]),
                "unit": "jours",
                "business_reading": "aucune commande non neutre pendant le backlog",
            },
            {
                "result": "days_between_detection_and_first_active_command",
                "value": float(crisis_context["first_active_effective_day"])
                - float(crisis_context["crisis_recognition_day"]),
                "unit": "jours",
                "business_reading": (
                    "écart descriptif, non interprété comme délai de réponse"
                ),
            },
            {
                "result": "client_pairs_service_or_backlog_changed",
                "value": float(
                    (
                        service["delta_served_qty"].abs().gt(TOLERANCE)
                        | service["delta_max_backlog"].abs().gt(TOLERANCE)
                    ).sum()
                ),
                "unit": "couples client/article",
                "business_reading": "aucun effet sur service/backlog",
            },
            {
                "result": "mrp_order_flows_changed",
                "value": float(
                    propagation.loc[
                        propagation["family"].eq("mrp_orders"), "changed"
                    ].iloc[0]
                ),
                "unit": "flux",
                "business_reading": "flux de commande réellement modifiés",
            },
        ]
    )


def _write_report(
    output: Path,
    *,
    seed: int,
    days: int,
    tradeoffs: pd.DataFrame,
    costs: pd.DataFrame,
    deferrals: pd.DataFrame,
    lot_context: Mapping[str, Any],
    components: pd.DataFrame,
    risks: pd.DataFrame,
    risk_episode_context: Mapping[str, Any],
    crisis_context: Mapping[str, Any],
    service: pd.DataFrame,
    figures: Sequence[Path],
    mrp: pd.Series,
    v3: pd.Series,
) -> Path:
    path = output / "canonical_industrial_results_report_fr.md"
    trade = tradeoffs.set_index("source_column")
    risk_pct = float(trade.loc["supplier_risk_area", "delta_pct"])
    cost_delta = float(trade.loc["total_economic_exposure", "delta"])
    unit_components = components.loc[components["uom"].astype(str).eq("UN")]
    top_component = unit_components.loc[
        unit_components["max_temporary_excess"].idxmax()
    ]
    buffer_lines = []
    for row in service.itertuples():
        buffer_lines.append(
            f"- {str(row.item_id).replace('item:', 'article ')} : "
            f"{row.delta_mean_available:+.2f} UN disponibles en moyenne, "
            "sans changement de quantité servie ni de backlog maximal."
        )
    risk_lines = []
    for row in risks.itertuples():
        risk_lines.append(
            f"- {row.scope_label.replace(chr(10), ' / ')} : "
            f"{row.lead_time_extra_days_mrp:.0f} → "
            f"{row.lead_time_extra_days_v3:.0f} jours cumulés "
            f"({row.delta:+.0f})."
        )
    deferral_lines = []
    for row in deferrals.itertuples():
        deferral_lines.append(
            f"- {row.src_node_id} → {row.dst_node_id}, "
            f"{str(row.item_id).replace('item:', 'article ')} : "
            f"{_fmt_number(abs(float(row.delta_measured)))} {row.uom} "
            "reportés après J364 ; écart final du pipeline = 0."
        )
    cost_lines = []
    for row in costs.itertuples():
        value = float(row.delta)
        cost_lines.append(
            f"- {row.component} : {'+' if value >= 0 else '-'}"
            f"{_fmt_number(abs(value), 2)} unités monétaires."
        )
    lines = [
        "# Pack de résultats industriels — MRP versus régulation dynamique V3",
        "",
        "## Ce que cette simulation montre",
        "",
        (
            f"Les deux variantes partent du même état physique mesuré et utilisent "
            f"les mêmes entrées exogènes sur {days} jours (graine {seed}). Les "
            "pénalités dépendantes de l'état restent libres de diverger après "
            "l'intervention. La différence est un contrefactuel simulé de V3, pas "
            "une comparaison entre deux années différentes."
        ),
        "",
        (
            f"- indice simulé de pénalités fournisseur : {_fmt_pct(risk_pct)} ; "
            "service moyen : inchangé ;"
        ),
        (
            f"- contraintes : {_fmt_number(float(mrp['constraint_violations']))} → "
            f"{_fmt_number(float(v3['constraint_violations']))} ; exposition économique : "
            f"+{_fmt_number(cost_delta, 2)} ;"
        ),
        (
            f"- {len(deferrals)} corridors/article semblent diminuer avant J364, "
            "mais chacun retrouve exactement la même quantité lorsque le pipeline "
            "futur est inclus ;"
        ),
        (
            f"- un lot de {_fmt_number(float(lot_context['lot_qty']))} unités est "
            f"décalé de {lot_context['shift_days']} jours ; le composant "
            f"{str(top_component['item_id']).replace('item:', '')} atteint un surstock "
            f"temporaire de {_fmt_number(float(top_component['max_temporary_excess']), 1)} "
            f"{top_component['uom']}."
        ),
        (
            f"- sur {risk_episode_context['supplier_id']} / "
            f"{str(risk_episode_context['item_id']).replace('item:', 'article ')}, "
            f"un épisode de pénalité est déclenché {risk_episode_context['trigger_shift_days']} "
            "jours plus tard dans V3."
        ),
        (
            f"- crise client {str(crisis_context['item_id']).replace('item:', 'article ')} : "
            f"backlog de J{crisis_context['backlog_start_day']} à "
            f"J{crisis_context['backlog_end_day']}, détecté à "
            f"J{crisis_context['crisis_recognition_day']}, mais aucune commande non "
            "neutre pendant le backlog."
        ),
        "",
        "## Résultats visuels",
        "",
    ]
    titles = (
        "1. Arbitrages exécutifs",
        "2. Couverture des différences par famille",
        "3. Reports après l'horizon",
        "4. Amplification par la lotification",
        "5. Pénalités fournisseur dépendantes de l'état",
        "6. Chronologie des divergences",
        "7. Réponse à la crise",
        "8. Service et tampon disponible",
    )
    for title, figure in zip(titles, figures):
        lines.extend([f"### {title}", "", f"![{title}]({figure.name})", ""])
    lines.extend(
        [
            "## Redistribution locale des pénalités fournisseur simulées",
            "",
            *risk_lines,
            "",
            "## Reports de fin d'horizon, sans mélange d'unités",
            "",
            *deferral_lines,
            "",
            "## Décomposition économique sur la fenêtre de 365 jours",
            "",
            *cost_lines,
            "",
            "## Signal avancé côté client",
            "",
            *buffer_lines,
            "",
            "## Décisions métier rendues possibles",
            "",
            (
                "- achats : distinguer une baisse d'expédition dans la fenêtre d'un "
                "simple report d'expédition après l'horizon ;"
            ),
            (
                "- planification : visualiser quels lots déplacent des millions "
                "d'unités de composants et pendant combien de jours ;"
            ),
            (
                "- opérations : dater séparément les premières différences de commande, "
                "d'expédition, d'arrivée, de consommation et de production ;"
            ),
            (
                "- direction supply chain : arbitrer explicitement indice de pénalités, "
                "stock, coût et contraintes, au lieu de regarder seulement le service."
            ),
            "",
            "## Limites",
            "",
            (
                "Ces résultats concernent une seule réalisation simulée. Ils documentent "
                "les mécanismes dans le modèle, pas encore leur fréquence industrielle. "
                "L'indice de pénalités fournisseur est un proxy du modèle, pas une "
                "probabilité d'incident observée. "
                "Les quantités de composants de différentes unités ne sont jamais "
                "additionnées. Le coût complet n'est pas encore ventilé par "
                "nœud/article/jour."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_dashboard(
    output: Path,
    *,
    seed: int,
    days: int,
    figures: Sequence[Path],
    tradeoffs: pd.DataFrame,
    costs: pd.DataFrame,
    propagation: pd.DataFrame,
    deferrals: pd.DataFrame,
    production: pd.DataFrame,
    lot_context: Mapping[str, Any],
    components: pd.DataFrame,
    risks: pd.DataFrame,
    risk_episode_context: Mapping[str, Any],
    timeline_labels: Sequence[str],
    crisis_context: Mapping[str, Any],
    service: pd.DataFrame,
    mrp: pd.Series,
    v3: pd.Series,
) -> Path:
    path = output / "canonical_industrial_results_dashboard.html"
    encoded = {
        figure.name: base64.b64encode(figure.read_bytes()).decode("ascii")
        for figure in figures
    }

    def signed_number(value: float, decimals: int = 2) -> str:
        sign = "+" if value >= 0 else "−"
        return sign + _fmt_number(abs(value), decimals)

    trade = tradeoffs.set_index("source_column")
    risk_pct = float(trade.loc["supplier_risk_area", "delta_pct"])
    cost_delta = float(trade.loc["total_economic_exposure", "delta"])
    cost_pct = float(trade.loc["total_economic_exposure", "delta_pct"])
    cost_index = costs.set_index("component")
    purchase_delta = float(cost_index.loc["Achats", "delta"])
    transport_delta = float(cost_index.loc["Transport", "delta"])
    production_cost_delta = float(cost_index.loc["Production", "delta"])
    stock_cost_delta = float(
        costs.loc[costs["component"].astype(str).str.startswith("Stock"), "delta"].iloc[
            0
        ]
    )
    backlog_days = (
        int(crisis_context["backlog_end_day"])
        - int(crisis_context["backlog_start_day"])
        + 1
    )
    card_data = (
        (
            _fmt_pct(risk_pct),
            "Perturbations fournisseur calculées",
            (
                "Le score qui résume chaque jour les retards, pertes de capacité, "
                "de disponibilité et de qualité fournisseur passe de "
                f"{_fmt_number(float(mrp['supplier_risk_area']), 3)} avec MRP à "
                f"{_fmt_number(float(v3['supplier_risk_area']), 3)} avec V3."
            ),
            (
                "V3 conduit le réseau vers une situation globalement moins exposée "
                "aux perturbations fournisseur calculées par le modèle, sans réduire "
                "les quantités livrées aux clients. Ce chiffre ne signifie pas que le "
                "risque réel de panne fournisseur baisse de "
                f"{_fmt_number(abs(risk_pct), 2)} %."
            ),
        ),
        (
            f"{len(deferrals)} flux",
            "Flux fournisseur–usine reportés",
            (
                f"Pour {len(deferrals)} flux fournisseur–usine, les expéditions visibles "
                f"à J{days - 1} "
                "sont plus faibles avec V3. Toutes les quantités manquantes sont déjà "
                f"planifiées après J{days - 1} : l'écart final est exactement nul."
            ),
            (
                "Il n'y a ni annulation de besoin ni économie durable sur ces flux. "
                "V3 a seulement déplacé des livraisons après la date de clôture. Les "
                "achats et la finance doivent donc inclure les livraisons encore "
                "planifiées après la fin du rapport."
            ),
        ),
        (
            f"{_fmt_number(float(lot_context['lot_qty']))} unités",
            f"Lot fabriqué {int(lot_context['shift_days'])} jours plus tard",
            (
                f"À l'usine {lot_context['node_id']}, un lot de "
                f"{_fmt_number(float(lot_context['lot_qty']))} unités de l'article "
                f"{str(lot_context['item_id']).replace('item:', '')} est produit à "
                f"J{lot_context['v3_day']} avec V3 au lieu de J{lot_context['mrp_day']} "
                "avec MRP. Le volume total produit sur l'année reste identique."
            ),
            (
                "Un décalage de dix jours peut immobiliser beaucoup de composants. "
                "Ils restent plus longtemps en stock avant d'être consommés, ce qui "
                "peut augmenter l'espace nécessaire et la trésorerie immobilisée, même "
                "si la production annuelle ne change pas."
            ),
        ),
        (
            f"0 jour sur {backlog_days}",
            "Aucun changement de décision pendant la crise client",
            (
                f"Pour l'article {str(crisis_context['item_id']).replace('item:', '')}, "
                f"des commandes client restent en attente de J{crisis_context['backlog_start_day']} "
                f"à J{crisis_context['backlog_end_day']}. La crise est reconnue à "
                f"J{crisis_context['crisis_recognition_day']}, mais V3 ne change aucune "
                "décision pendant cette période."
            ),
            (
                "La détection fonctionne, mais le réglage actuel ne contribue pas à "
                "résoudre cette crise. Les règles d'action doivent être revues pour "
                "intervenir pendant que le retard client augmente, et non après son "
                "absorption par le fonctionnement habituel."
            ),
        ),
    )
    cards = [
        (
            '<article class="card"><strong>'
            + html.escape(value)
            + "</strong><h2>"
            + html.escape(title)
            + '</h2><div class="card-copy"><h3>Ce qu’on observe</h3><p>'
            + html.escape(observation)
            + "</p><h3>Ce que cela signifie pour le métier</h3><p>"
            + html.escape(business_meaning)
            + "</p></div></article>"
        )
        for value, title, observation, business_meaning in card_data
    ]

    coverage = propagation.set_index("family")

    def coverage_text(family: str) -> str:
        row = coverage.loc[family]
        return f"{int(row['changed'])} sur {int(row['total'])}"

    deferred_details = "; ".join(
        (
            f"article {str(row.item_id).replace('item:', '')} : "
            f"{_fmt_number(abs(float(row.delta_measured)))} {row.uom}"
        )
        for row in deferrals.itertuples()
    )
    annual_production = float(
        pd.to_numeric(production["produced_qty_mrp"], errors="coerce").sum()
    )
    unit_components = components.loc[components["uom"].astype(str).eq("UN")]
    highlighted_component = unit_components.loc[
        unit_components["max_temporary_excess"].idxmax()
    ]
    lot_service = service.loc[
        service["item_id"].astype(str).eq(str(lot_context["item_id"]))
    ].iloc[0]
    worsening = risks.loc[pd.to_numeric(risks["delta"], errors="coerce").gt(0)]
    if worsening.empty:
        worsening_text = "aucun flux local ne se dégrade"
    else:
        row = worsening.sort_values("delta", ascending=False).iloc[0]
        worsening_text = (
            f"{str(row['scope_label']).replace(chr(10), ' / ')} passe de "
            f"{_fmt_number(float(row['lead_time_extra_days_mrp']))} à "
            f"{_fmt_number(float(row['lead_time_extra_days_v3']))} jours de retard "
            "ajoutés cumulés"
        )
    timeline_text = "; ".join(
        label.replace(" (", " : ").rstrip(")") for label in timeline_labels
    )
    service_details = []
    for row in service.itertuples():
        relative = _percentage_change(
            float(row.mean_available_mrp), float(row.mean_available_v3)
        )
        service_details.append(
            f"{str(row.item_id).replace('item:', 'article ')} : "
            f"{signed_number(float(row.delta_mean_available), 1)} unités "
            f"({_fmt_pct(relative)})"
        )

    section_data = (
        (
            "01_arbitrages_executifs.png",
            "Ce que V3 améliore — et ce que cela coûte",
            (
                "Le service client reste identique et le score de perturbations "
                f"fournisseur baisse de {_fmt_number(abs(risk_pct), 2)} %. Les achats "
                f"diminuent de {_fmt_number(abs(purchase_delta), 2)} unités monétaires "
                f"et le transport de {_fmt_number(abs(transport_delta), 2)}. En revanche, "
                f"les coûts de stock augmentent de {_fmt_number(stock_cost_delta, 2)}, "
                f"ceux de production de {_fmt_number(production_cost_delta, 2)} et le "
                f"nombre de contraintes détectées passe de "
                f"{_fmt_number(float(mrp['constraint_violations']))} à "
                f"{_fmt_number(float(v3['constraint_violations']))}. Le bilan total "
                f"augmente ainsi de {_fmt_number(cost_delta, 2)} unités monétaires, "
                f"soit {_fmt_number(cost_pct, 4)} %."
            ),
            (
                "V3 n'apporte pas un gain gratuit. Il réduit les achats réalisés avant "
                "la fin de l'année et l'exposition aux perturbations fournisseur, mais "
                "conserve davantage de composants en stock. La direction peut voir ce "
                "qu'elle gagne, ce qu'elle paie et régler la stratégie selon ses "
                "priorités : risque fournisseur, trésorerie, stock ou contraintes "
                "opérationnelles."
            ),
        ),
        (
            "02_couverture_des_differences.png",
            "Jusqu'où les décisions changent le réseau",
            (
                "Les calculs de planification changent dans "
                f"{coverage_text('mrp_state')} cas sur le réseau, mais les effets "
                f"physiques restent sélectifs : {coverage_text('mrp_orders')} flux de "
                f"commande, {coverage_text('supplier_shipments')} routes d'expédition "
                f"et {coverage_text('plant_input_arrivals')} arrivées de composants sont "
                "modifiés. Les dates de consommation changent pour "
                f"{coverage_text('plant_input_consumption')} composants et les dates de "
                f"production pour {coverage_text('plant_output')} produits. Les quantités "
                "servies et les commandes client en attente restent identiques."
            ),
            (
                "Une modification du calcul ne déplace pas automatiquement tout le "
                "réseau. Les stocks, les délais et les règles de production par lots "
                "absorbent certaines corrections et en amplifient d'autres. Les fractions "
                "de chaque ligne comptent des objets différents : elles servent à "
                "localiser les changements, pas à former une cascade de volumes."
            ),
        ),
        (
            "03_report_apres_horizon.png",
            "Des baisses d'expédition qui ne sont pas des économies",
            (
                f"À la fin de J{days - 1}, {len(deferrals)} livraisons sont plus faibles "
                "avec V3 : "
                f"{deferred_details}. Lorsque l'on ajoute les livraisons déjà prévues "
                "après cette date, l'écart redevient exactement nul pour chacun des "
                f"{len(deferrals)} flux."
            ),
            (
                "Une baisse constatée à la date de clôture peut être un simple décalage "
                "de calendrier. Sans les expéditions futures, elle pourrait être présentée "
                "à tort comme une économie d'achat, de transport ou de stock. Le suivi "
                "industriel doit toujours afficher les livraisons encore planifiées "
                "après la date de fin."
            ),
        ),
        (
            "04_amplification_par_lotification.png",
            "L'effet d'un déplacement de lot sur les composants",
            (
                f"À {lot_context['node_id']}, la production annuelle de "
                f"{str(lot_context['item_id']).replace('item:', 'article ')} reste à "
                f"{_fmt_number(annual_production)} unités. Un lot de "
                f"{_fmt_number(float(lot_context['lot_qty']))} unités passe de J"
                f"{lot_context['mrp_day']} à J{lot_context['v3_day']}. Le client reçoit "
                f"toujours {_fmt_number(float(lot_service.served_qty_v3))} unités et le "
                f"retard maximal reste à {_fmt_number(float(lot_service.max_backlog_v3))}. "
                f"Pendant ce décalage, l'article "
                f"{str(highlighted_component['item_id']).replace('item:', '')} atteint "
                f"un surplus temporaire de "
                f"{_fmt_number(float(highlighted_component['max_temporary_excess']), 1)} "
                "unités."
            ),
            (
                "La production par lots transforme une petite correction de calendrier "
                "en un effet stock très important. Ce graphique permet d'anticiper "
                "l'occupation d'entrepôt, la trésorerie immobilisée et le risque "
                "d'obsolescence. Les composants étant exprimés dans des unités "
                "différentes, leurs quantités doivent être évaluées séparément."
            ),
        ),
        (
            "05_redistribution_du_risque.png",
            "Où les perturbations fournisseur diminuent — et où elles augmentent",
            (
                f"Pour {risk_episode_context['supplier_id']} vers "
                f"{risk_episode_context['dst_node_id']}, article "
                f"{str(risk_episode_context['item_id']).replace('item:', '')}, une "
                f"période de retard comparable commence à J"
                f"{risk_episode_context['v3_start_day']} avec V3 au lieu de J"
                f"{risk_episode_context['mrp_start_day']} avec MRP, soit "
                f"{risk_episode_context['trigger_shift_days']} jours plus tard. Sur "
                f"l'année, la somme des jours de retard ajoutés "
                f"passe de {_fmt_number(float(risk_episode_context['mrp_scope_cumulative']))} "
                f"à {_fmt_number(float(risk_episode_context['v3_scope_cumulative']))}."
            ),
            (
                "L'amélioration globale n'est pas répartie uniformément. V3 soulage "
                "nettement un fournisseur et un article, mais "
                f"{worsening_text}. Le pilotage doit donc suivre les résultats par "
                "fournisseur, usine et article, avec des limites locales pour éviter "
                "de déplacer un problème au lieu de le résoudre."
            ),
        ),
        (
            "06_chronologie_des_divergences.png",
            "Quand les décisions atteignent réellement les opérations",
            (
                f"Les premières différences sont datées ainsi : {timeline_text}. Les "
                "commandes et certaines expéditions changent rapidement, alors que les "
                "arrivées usine, consommations, productions et tensions fournisseur ne "
                "se distinguent parfois que plusieurs mois plus tard."
            ),
            (
                "La chaîne logistique réagit à plusieurs vitesses. Une décision prise "
                "aujourd'hui peut modifier un ordre immédiatement mais n'atteindre "
                "l'usine ou le fournisseur que bien plus tard. Le graphique aide à "
                "choisir les bons délais de surveillance ; il ne relie pas chaque effet "
                "à une commande unique."
            ),
        ),
        (
            "07_reponse_a_la_crise.png",
            "Réaction de V3 pendant la crise client",
            (
                f"Pour {str(crisis_context['item_id']).replace('item:', 'article ')}, les "
                f"commandes client en attente commencent à "
                f"J{crisis_context['backlog_start_day']}, atteignent "
                f"{_fmt_number(float(crisis_context['backlog_peak_qty']), 1)} unités et "
                f"restent présentes jusqu'à J{crisis_context['backlog_end_day']}. "
                f"V3 reconnaît la crise à J{crisis_context['crisis_recognition_day']}, "
                "mais ne change aucune décision pendant cette période. Le fonctionnement "
                f"habituel résorbe les commandes en attente à J"
                f"{int(crisis_context['backlog_end_day']) + 1}."
            ),
            (
                "V3 sait identifier la crise, mais ses règles actuelles ne déclenchent "
                "pas d'action utile au moment où le client est en difficulté. La première "
                f"décision différente n'apparaît qu'à "
                f"J{crisis_context['first_active_effective_day']}. La priorité est de "
                "revoir ces règles afin de sécuriser les approvisionnements ou la "
                "production pendant la montée du retard client."
            ),
        ),
        (
            "08_service_et_tampon_disponible.png",
            "Même service, mais une marge de sécurité légèrement plus faible",
            (
                "La quantité livrée et le retard maximal restent strictement identiques. "
                "La quantité moyenne disponible juste avant de servir le client baisse "
                + " ; ".join(service_details)
                + "."
            ),
            (
                "Le client ne voit aucune différence sur cette période, mais V3 utilise "
                "une petite partie de la réserve disponible. L'effet est faible et ne "
                "prouve pas à lui seul une fragilité industrielle. Cette réserve doit "
                "néanmoins être surveillée en complément du taux de service, car elle "
                "peut avertir plus tôt d'une fragilisation."
            ),
        ),
    )
    sections = []
    for filename, title, observation, business_meaning in section_data:
        sections.append(
            "<section><h2>"
            + html.escape(title)
            + f'</h2><img src="data:image/png;base64,{encoded[filename]}" '
            + f'alt="{html.escape(title)}"><div class="explanation">'
            + "<div><h3>Ce qu’on observe</h3><p>"
            + html.escape(observation)
            + "</p></div><div><h3>Ce que cela signifie pour le métier</h3><p>"
            + html.escape(business_meaning)
            + "</p></div></div></section>"
        )
    document = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RESILIENCE-SCAN — Pack industriel MRP / V3</title>
<style>
:root{{--ink:#172033;--muted:#5d697c;--paper:#f3f6f9;--panel:#fff;--accent:#117c78;--line:#d8e0e9}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);font-family:Inter,Segoe UI,Arial,sans-serif;color:var(--ink)}}
header{{padding:34px 5vw;background:linear-gradient(120deg,#12324a,#117c78);color:white}}header h1{{margin:0 0 8px;font-size:30px}}header p{{margin:0;opacity:.9}}
main{{max-width:1500px;margin:auto;padding:24px 4vw 60px}}.cards{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:22px}}
.card,section,.notice{{background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 3px 12px #18324a14}}
.card{{padding:20px}}.card strong{{display:block;font-size:28px;color:var(--accent)}}.card h2{{margin:5px 0 14px;font-size:18px}}.card h3{{margin:13px 0 5px;font-size:14px;color:var(--accent)}}.card p{{margin:0;color:var(--muted);line-height:1.5}}
.notice{{padding:18px 22px;margin-bottom:22px;border-left:5px solid #e3a33a;line-height:1.5}}section{{padding:24px;margin:0 0 24px}}section h2{{margin:0 0 15px}}section img{{display:block;width:100%;height:auto;border-radius:8px}}
.explanation{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px;padding-top:18px;border-top:1px solid var(--line)}}.explanation div{{background:#f7f9fb;border-radius:10px;padding:16px}}.explanation h3{{margin:0 0 8px;font-size:16px;color:var(--accent)}}.explanation p{{margin:0;color:var(--muted);line-height:1.55}}
footer{{color:var(--muted);font-size:13px;padding-top:12px}}@media(max-width:900px){{.cards,.explanation{{grid-template-columns:1fr}}}} 
</style></head><body><header><h1>RESILIENCE-SCAN — résultats industriels MRP / V3</h1><p>Comparaison sur {days} jours : fonctionnement MRP seul et MRP avec régulation V3</p></header>
<main><div class="notice"><b>À garder en tête :</b> ces chiffres décrivent un seul essai numérique de {days} jours, pas un gain moyen garanti. MRP et V3 partent des mêmes stocks et reçoivent les mêmes demandes et perturbations extérieures. Les perturbations fournisseur affichées sont calculées par le modèle, et non mesurées chez un fournisseur réel. Il faudra répéter l'essai sur de nombreuses situations avant de généraliser les résultats.</div><div class="cards">{"".join(cards)}</div>
{"".join(sections)}<footer>Simulation technique n° {seed}. Fichier autonome, sans connexion Internet. Les simulations sources n'ont pas été modifiées.</footer></main></body></html>"""
    path.write_text(document, encoding="utf-8")
    return path


def build_canonical_industrial_results(
    *,
    paired_results_dir: Path,
    comparison_dir: Path,
    output_dir: Path,
    seed: int | None = None,
) -> IndustrialResultArtifacts:
    """Create the standalone industrial evidence pack."""

    paired_root = paired_results_dir.resolve()
    comparison_root = comparison_dir.resolve()
    output = _prepare_output(output_dir)
    selected_seed, mrp_dir, v3_dir, mrp, v3, days = _load_pair(paired_root, seed)
    summary, tables_dir = _validate_comparison(
        comparison_root,
        paired_results_dir=paired_root,
        seed=selected_seed,
    )

    tradeoffs = _tradeoff_frame(mrp, v3)
    costs = _cost_bridge_frame(mrp_dir, v3_dir)
    propagation = _propagation_frame(summary)
    deferrals = _horizon_deferral_frame(mrp_dir, v3_dir, days)
    production, components, lot_context = _lot_amplification_frame(
        summary, tables_dir, mrp_dir
    )
    risks = _risk_redistribution_frame(mrp_dir, v3_dir)
    risk_episode, risk_episode_context = _risk_episode_frame(mrp_dir, v3_dir)
    timeline_daily, timeline_labels, timeline_matrix = _timeline_frame(
        tables_dir, v3_dir, days
    )
    service = _service_buffer_frame(mrp_dir, v3_dir)
    crisis, crisis_context = _crisis_response_frame(v3_dir, days)
    risk_change_pct = float(
        tradeoffs.loc[
            tradeoffs["source_column"].eq("supplier_risk_area"), "delta_pct"
        ].iloc[0]
    )

    figures = (
        _plot_tradeoffs(tradeoffs, costs, mrp=mrp, v3=v3, output=output),
        _plot_propagation(propagation, output),
        _plot_horizon_deferral(deferrals, output, days),
        _plot_lot_amplification(production, components, lot_context, output),
        _plot_risk_redistribution(
            risks,
            risk_episode,
            risk_episode_context,
            risk_change_pct=risk_change_pct,
            output=output,
        ),
        _plot_causal_timeline(timeline_daily, timeline_labels, timeline_matrix, output),
        _plot_crisis_response(crisis, crisis_context, output),
        _plot_service_buffer(service, output),
    )

    tradeoffs.to_csv(output / "canonical_industrial_tradeoffs.csv", index=False)
    costs.to_csv(output / "canonical_industrial_cost_bridge.csv", index=False)
    propagation.to_csv(output / "canonical_industrial_propagation.csv", index=False)
    deferrals.to_csv(output / "canonical_industrial_horizon_deferrals.csv", index=False)
    components.to_csv(
        output / "canonical_industrial_lot_amplification.csv", index=False
    )
    risks.to_csv(output / "canonical_industrial_risk_redistribution.csv", index=False)
    risk_episode.to_csv(output / "canonical_industrial_risk_episode.csv", index=False)
    timeline_daily.to_csv(output / "canonical_industrial_timeline.csv", index=False)
    crisis.to_csv(output / "canonical_industrial_crisis_response.csv", index=False)
    service.to_csv(output / "canonical_industrial_service_buffer.csv", index=False)
    key_results = _key_results(
        tradeoffs=tradeoffs,
        propagation=propagation,
        deferrals=deferrals,
        lot_context=lot_context,
        components=components,
        risks=risks,
        risk_episode_context=risk_episode_context,
        crisis_context=crisis_context,
        service=service,
        mrp=mrp,
        v3=v3,
    )
    key_results_path = output / "canonical_industrial_key_results.csv"
    key_results.to_csv(key_results_path, index=False)

    report_path = _write_report(
        output,
        seed=selected_seed,
        days=days,
        tradeoffs=tradeoffs,
        costs=costs,
        deferrals=deferrals,
        lot_context=lot_context,
        components=components,
        risks=risks,
        risk_episode_context=risk_episode_context,
        crisis_context=crisis_context,
        service=service,
        figures=figures,
        mrp=mrp,
        v3=v3,
    )
    dashboard_path = _write_dashboard(
        output,
        seed=selected_seed,
        days=days,
        figures=figures,
        tradeoffs=tradeoffs,
        costs=costs,
        propagation=propagation,
        deferrals=deferrals,
        production=production,
        lot_context=lot_context,
        components=components,
        risks=risks,
        risk_episode_context=risk_episode_context,
        timeline_labels=timeline_labels,
        crisis_context=crisis_context,
        service=service,
        mrp=mrp,
        v3=v3,
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": selected_seed,
        "days": days,
        "source": {
            "paired_results_dir": str(paired_root),
            "comparison_dir": str(comparison_root),
            "mrp_run": str(mrp_dir),
            "v3_run": str(v3_dir),
        },
        "scientific_scope": {
            "same_exogenous_random_inputs_validated": True,
            "same_measured_period_initial_physical_state_validated": True,
            "same_scenario_graph_engine_profile_and_horizon_validated": True,
            "full_artifact_contract_validated_for_both_arms": True,
            "endogenous_state_penalties_allowed_to_diverge": True,
            "simulated_counterfactual": True,
            "industrial_frequency_validated": False,
            "replication_count": 1,
            "mixed_component_units_summed": False,
        },
        "lot_shift": lot_context,
        "illustrative_risk_episode": risk_episode_context,
        "crisis_response": crisis_context,
        "outputs": {
            "dashboard": str(dashboard_path),
            "report": str(report_path),
            "key_results": str(key_results_path),
            "figures": [str(path) for path in figures],
        },
    }
    manifest_path = output / "canonical_industrial_results_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return IndustrialResultArtifacts(
        output_dir=output,
        dashboard_path=dashboard_path,
        report_path=report_path,
        manifest_path=manifest_path,
        key_results_path=key_results_path,
        figure_paths=figures,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a standalone business-facing evidence pack from a completed "
            "paired MRP/V3 campaign and its node comparison."
        )
    )
    parser.add_argument("--paired-results-dir", required=True)
    parser.add_argument("--comparison-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = build_canonical_industrial_results(
        paired_results_dir=Path(args.paired_results_dir),
        comparison_dir=Path(args.comparison_dir),
        output_dir=Path(args.output_dir),
        seed=args.seed,
    )
    print(f"Industrial results pack completed: {artifacts.output_dir}")
    print(f"Dashboard: {artifacts.dashboard_path}")
    print(f"Report: {artifacts.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
