from __future__ import annotations

"""Reporting for the SCAN end-2026 validation work package."""

import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .reporting import prediction_coverage_report_lines, provenance_report_lines


DEFAULT_STABLE_NOMINAL_DAYS = 7
REGIME_RECOVERY_COLUMNS = [
    "episode_id",
    "entry_regime",
    "start_day",
    "last_non_nominal_day",
    "stable_nominal_start_day",
    "confirmation_end_day",
    "recovery_time_days",
    "duration_or_lower_bound_days",
    "observed_follow_up_days",
    "observed_non_nominal_days",
    "provisional_nominal_days",
    "stable_nominal_days_required",
    "right_censored",
    "left_truncated",
    "status",
    "regime_path",
    "measurement_scope",
]


def _save(
    fig: Any,
    path: Path,
    figure_provenance_label: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if figure_provenance_label:
        fig.text(
            0.995,
            0.004,
            figure_provenance_label,
            ha="right",
            va="bottom",
            fontsize=7,
            color="dimgray",
        )
        fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
    else:
        fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _portfolio_scope(frame: pd.DataFrame) -> pd.DataFrame:
    """Select portfolio rows without mutating/export-truncating granular data."""

    if frame.empty or "scope" not in frame:
        return frame
    scope = frame["scope"].astype(str).str.strip().str.lower()
    return frame.loc[scope.eq("portfolio")].copy()


def _executable_threshold_plot_frame(evidence: pd.DataFrame) -> pd.DataFrame:
    """Expand executable threshold maps and omit NOMINAL fallthrough diagnostics."""

    records: list[dict[str, Any]] = []
    for row in evidence.to_dict(orient="records"):
        regime = str(row.get("regime") or "")
        try:
            initial = json.loads(str(row.get("initial_thresholds") or "{}"))
            calibrated = json.loads(
                str(row.get("calibrated_thresholds") or "{}")
            )
        except json.JSONDecodeError:
            initial, calibrated = {}, {}
        if not isinstance(initial, dict) or not isinstance(calibrated, dict):
            initial, calibrated = {}, {}
        for threshold, calibrated_value in calibrated.items():
            if threshold not in initial:
                continue
            records.append({
                "regime": regime,
                "threshold": str(threshold),
                "previous_value": float(initial[threshold]),
                "calibrated_value": float(calibrated_value),
            })
    return pd.DataFrame.from_records(
        records,
        columns=["regime", "threshold", "previous_value", "calibrated_value"],
    )


def derive_regime_recovery_episodes(
    trajectory: pd.DataFrame,
    *,
    stable_nominal_days: int = DEFAULT_STABLE_NOMINAL_DAYS,
) -> pd.DataFrame:
    """Measure off-NOMINAL episodes until a stable observed NOMINAL return.

    An episode starts on the first observed non-NOMINAL day after no active
    episode.  Short NOMINAL spells that do not reach ``stable_nominal_days``
    remain part of the same episode.  Recovery is dated at the first day of the
    first complete, consecutive stable-NOMINAL spell.  If that spell is not
    fully observable before the trajectory ends, the duration is reported only
    as a right-censored lower bound.  An episode already active on the first
    observed day is explicitly marked as left-truncated.

    The episode is grouped by its entry regime.  This is a descriptive measure
    on the reduced adaptive trajectory, not a causal effect of that regime.
    """

    if stable_nominal_days < 1:
        raise ValueError("stable_nominal_days must be at least 1")
    if trajectory.empty:
        return pd.DataFrame(columns=REGIME_RECOVERY_COLUMNS)
    missing = {"day", "regime"}.difference(trajectory.columns)
    if missing:
        raise ValueError(
            "regime recovery requires trajectory columns: "
            + ", ".join(sorted(missing))
        )

    work = trajectory.loc[:, ["day", "regime"]].copy()
    work["day"] = pd.to_numeric(work["day"], errors="coerce")
    if (
        work["day"].isna().any()
        or not np.isfinite(work["day"].to_numpy(dtype=float)).all()
    ):
        raise ValueError("regime recovery requires finite numeric day values")
    work["regime"] = work["regime"].fillna("").astype(str).str.strip().str.upper()
    if work["regime"].eq("").any():
        raise ValueError("regime recovery requires non-empty regime labels")
    work = work.sort_values("day", kind="stable").reset_index(drop=True)
    if work["day"].duplicated().any():
        raise ValueError("regime recovery requires at most one regime per day")

    days = work["day"].to_numpy(dtype=float)
    regimes = work["regime"].to_numpy(dtype=str)
    row_count = len(work)

    def _stable_nominal_start(search_from: int) -> int | None:
        last_start = row_count - stable_nominal_days
        for candidate in range(search_from, last_start + 1):
            end = candidate + stable_nominal_days
            if not bool(np.all(regimes[candidate:end] == "NOMINAL")):
                continue
            if stable_nominal_days == 1 or bool(
                np.allclose(np.diff(days[candidate:end]), 1.0)
            ):
                return candidate
        return None

    rows: list[dict[str, Any]] = []
    cursor = 0
    while cursor < row_count:
        if regimes[cursor] == "NOMINAL":
            cursor += 1
            continue

        start_index = cursor
        recovery_index = _stable_nominal_start(start_index + 1)
        episode_end = recovery_index if recovery_index is not None else row_count
        episode_regimes = regimes[start_index:episode_end]
        episode_days = days[start_index:episode_end]
        non_nominal = episode_regimes != "NOMINAL"
        non_nominal_indices = np.flatnonzero(non_nominal)
        last_non_nominal_day = float(
            episode_days[int(non_nominal_indices[-1])]
        )
        regime_path = " > ".join(
            str(regime)
            for index, regime in enumerate(episode_regimes)
            if index == 0 or regime != episode_regimes[index - 1]
        )
        start_day = float(days[start_index])
        left_truncated = start_index == 0

        if recovery_index is None:
            confirmation_end_day = np.nan
            stable_start_day = np.nan
            recovery_time = np.nan
            observed_follow_up = float(days[-1] - start_day + 1.0)
            duration_or_lower_bound = observed_follow_up
            right_censored = True
            status = "right_censored"
            cursor = row_count
        else:
            stable_start_day = float(days[recovery_index])
            confirmation_end_index = (
                recovery_index + stable_nominal_days - 1
            )
            confirmation_end_day = float(days[confirmation_end_index])
            recovery_time = float(stable_start_day - start_day)
            duration_or_lower_bound = recovery_time
            observed_follow_up = float(
                confirmation_end_day - start_day + 1.0
            )
            right_censored = False
            status = "recovered"
            cursor = recovery_index + stable_nominal_days

        rows.append(
            {
                "episode_id": f"R{len(rows) + 1:03d}",
                "entry_regime": str(regimes[start_index]),
                "start_day": start_day,
                "last_non_nominal_day": last_non_nominal_day,
                "stable_nominal_start_day": stable_start_day,
                "confirmation_end_day": confirmation_end_day,
                "recovery_time_days": recovery_time,
                "duration_or_lower_bound_days": duration_or_lower_bound,
                "observed_follow_up_days": observed_follow_up,
                "observed_non_nominal_days": int(non_nominal.sum()),
                "provisional_nominal_days": int((~non_nominal).sum()),
                "stable_nominal_days_required": int(stable_nominal_days),
                "right_censored": right_censored,
                "left_truncated": left_truncated,
                "status": status,
                "regime_path": regime_path,
                "measurement_scope": "reduced_adaptive_trajectory",
            }
        )

    return pd.DataFrame(rows, columns=REGIME_RECOVERY_COLUMNS)


def summarize_regime_recovery(
    episodes: pd.DataFrame,
    *,
    stable_nominal_days: int = DEFAULT_STABLE_NOMINAL_DAYS,
) -> dict[str, Any]:
    """Return JSON-ready descriptive recovery metadata by entry regime."""

    if stable_nominal_days < 1:
        raise ValueError("stable_nominal_days must be at least 1")
    if episodes.empty:
        return {
            "status": "no_off_nominal_episode_observed",
            "definition": (
                "observed instability episode starting outside NOMINAL and "
                "ending on the first day of "
                f"{stable_nominal_days} consecutive observed NOMINAL days; "
                "shorter NOMINAL spells remain inside the episode"
            ),
            "attribution": "entry_regime_descriptive_not_causal",
            "stable_nominal_days_required": int(stable_nominal_days),
            "episode_count": 0,
            "observed_recoveries": 0,
            "right_censored_episodes": 0,
            "left_truncated_episodes": 0,
            "artifact": "data/regime_recovery_episodes.csv",
            "plot": "plots/end_2026/regime_recovery_time_by_entry_regime.png",
            "by_entry_regime": [],
        }
    required = {
        "entry_regime",
        "recovery_time_days",
        "duration_or_lower_bound_days",
        "right_censored",
        "left_truncated",
    }
    missing = required.difference(episodes.columns)
    if missing:
        raise ValueError(
            "regime recovery summary requires columns: "
            + ", ".join(sorted(missing))
        )

    by_regime: list[dict[str, Any]] = []
    for regime, group in episodes.groupby("entry_regime", sort=True):
        recovered = group.loc[~group["right_censored"].astype(bool)]
        recovery_values = pd.to_numeric(
            recovered["recovery_time_days"], errors="coerce"
        ).dropna()
        lower_bounds = pd.to_numeric(
            group["duration_or_lower_bound_days"], errors="coerce"
        ).dropna()
        by_regime.append(
            {
                "entry_regime": str(regime),
                "episode_count": int(len(group)),
                "observed_recoveries": int(len(recovered)),
                "right_censored_episodes": int(
                    group["right_censored"].astype(bool).sum()
                ),
                "median_observed_recovery_days": (
                    float(recovery_values.median())
                    if not recovery_values.empty
                    else None
                ),
                "maximum_observed_duration_or_lower_bound_days": (
                    float(lower_bounds.max())
                    if not lower_bounds.empty
                    else None
                ),
            }
        )
    return {
        "status": "descriptive_episode_measure_available",
        "definition": (
            "observed instability episode starting outside NOMINAL and ending "
            "on the first day of "
            f"{stable_nominal_days} consecutive observed NOMINAL days; shorter "
            "NOMINAL spells remain inside the episode"
        ),
        "attribution": "entry_regime_descriptive_not_causal",
        "stable_nominal_days_required": int(stable_nominal_days),
        "episode_count": int(len(episodes)),
        "observed_recoveries": int(
            (~episodes["right_censored"].astype(bool)).sum()
        ),
        "right_censored_episodes": int(
            episodes["right_censored"].astype(bool).sum()
        ),
        "left_truncated_episodes": int(
            episodes["left_truncated"].astype(bool).sum()
        ),
        "artifact": "data/regime_recovery_episodes.csv",
        "plot": "plots/end_2026/regime_recovery_time_by_entry_regime.png",
        "by_entry_regime": by_regime,
    }


def save_regime_recovery_plot(
    output_dir: Path,
    episodes: pd.DataFrame,
    figure_provenance_label: str = "",
) -> Path:
    """Plot exact recoveries and censored lower bounds by entry regime."""

    path = (
        output_dir
        / "plots"
        / "end_2026"
        / "regime_recovery_time_by_entry_regime.png"
    )
    fig, ax = plt.subplots(figsize=(11, 6))
    if episodes.empty:
        ax.text(
            0.5,
            0.5,
            "No off-NOMINAL episode observed on this trajectory.",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
    else:
        required = {
            "entry_regime",
            "duration_or_lower_bound_days",
            "right_censored",
            "left_truncated",
        }
        missing = required.difference(episodes.columns)
        if missing:
            raise ValueError(
                "regime recovery plot requires columns: "
                + ", ".join(sorted(missing))
            )
        work = episodes.copy()
        regimes = list(dict.fromkeys(work["entry_regime"].astype(str)))
        positions = {regime: index for index, regime in enumerate(regimes)}
        for regime, group in work.groupby("entry_regime", sort=False):
            group = group.reset_index(drop=True)
            offsets = (
                np.linspace(-0.16, 0.16, len(group))
                if len(group) > 1
                else np.array([0.0])
            )
            base_y = float(positions[str(regime)])
            for offset, row in zip(offsets, group.itertuples()):
                censored = bool(row.right_censored)
                left_truncated = bool(row.left_truncated)
                ax.scatter(
                    float(row.duration_or_lower_bound_days),
                    base_y + float(offset),
                    marker=">" if censored else "o",
                    s=80,
                    facecolors=(
                        "none"
                        if left_truncated
                        else ("tab:orange" if censored else "tab:blue")
                    ),
                    edgecolors="tab:orange" if censored else "tab:blue",
                    linewidths=1.5,
                    zorder=3,
                )
        ax.scatter(
            [],
            [],
            marker="o",
            s=70,
            color="tab:blue",
            label="observed recovery time",
        )
        ax.scatter(
            [],
            [],
            marker=">",
            s=70,
            color="tab:orange",
            label="right-censored lower bound (≥)",
        )
        if bool(work["left_truncated"].astype(bool).any()):
            ax.scatter(
                [],
                [],
                marker="o",
                s=70,
                facecolors="none",
                edgecolors="black",
                label="left-truncated at horizon start",
            )
        ax.set_yticks(
            list(range(len(regimes))),
            regimes,
        )
        ax.set_ylim(-0.5, len(regimes) - 0.5)
        stable_days = int(
            pd.to_numeric(
                work.get(
                    "stable_nominal_days_required",
                    pd.Series([DEFAULT_STABLE_NOMINAL_DAYS]),
                ),
                errors="coerce",
            ).dropna().iloc[0]
        )
        ax.set_xlabel(
            "days from observed episode start to the first of "
            f"{stable_days} consecutive NOMINAL days"
        )
        ax.set_ylabel("regime at episode entry")
        ax.grid(axis="x", alpha=0.25)
        ax.legend(loc="best")
    ax.set_title(
        "Reduced adaptive trajectory: recovery time by entry regime "
        "(exploratory)"
    )
    fig.text(
        0.5,
        0.01,
        "Entry-regime grouping is descriptive; censored episodes are lower "
        "bounds and no causal regime effect is inferred.",
        ha="center",
        fontsize=9,
    )
    _save(fig, path, figure_provenance_label)
    return path


def save_rci_business_comparison_plot(
    output_dir: Path,
    completed_review: pd.DataFrame,
    rci_status: Mapping[str, Any],
    figure_provenance_label: str = "",
) -> Path | None:
    """Plot direct expert ratings against RCI only after a valid review.

    The figure deliberately keeps the four business questions separate.  It
    does not manufacture a composite expert score from incomplete or pending
    ratings.
    """

    if (
        str(rci_status.get("status") or "") != "review_available"
        or completed_review.empty
    ):
        return None
    rating_columns = {
        "expert_risk_created_0_1": (
            "Expert positive rate: response creates risk",
            (-0.05, 1.05),
        ),
        "expert_plausibility_1_5": (
            "Mean expert plausibility (1-5)",
            (0.75, 5.25),
        ),
        "supplier_pressure_risk_1_5": (
            "Mean supplier-pressure risk (1-5)",
            (0.75, 5.25),
        ),
        "planning_nervousness_risk_1_5": (
            "Mean planning-nervousness risk (1-5)",
            (0.75, 5.25),
        ),
    }
    required = {"episode_id", "model_rci", *rating_columns}
    if not required.issubset(completed_review.columns):
        return None

    work = completed_review.loc[:, list(required)].copy()
    work["episode_id"] = (
        work["episode_id"].fillna("").astype(str).str.strip()
    )
    numeric_columns = ["model_rci", *rating_columns]
    for column in numeric_columns:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    finite = work["episode_id"].ne("")
    for column in numeric_columns:
        finite &= work[column].notna() & np.isfinite(work[column])
    if not bool(finite.all()):
        return None

    aggregations: dict[str, tuple[str, str]] = {
        "model_rci": ("model_rci", "first"),
        "reviewer_count": ("episode_id", "size"),
    }
    aggregations.update(
        {
            f"mean_{column}": (column, "mean")
            for column in rating_columns
        }
    )
    episodes = (
        work.groupby("episode_id", sort=True)
        .agg(**aggregations)
        .reset_index()
    )
    if episodes.empty:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    marker_size = 35.0 + 18.0 * episodes["reviewer_count"].to_numpy(
        dtype=float
    )
    for axis, (column, (label, limits)) in zip(
        axes.flat,
        rating_columns.items(),
    ):
        axis.scatter(
            episodes["model_rci"],
            episodes[f"mean_{column}"],
            s=marker_size,
            alpha=0.75,
        )
        axis.set_ylabel(label)
        axis.set_ylim(*limits)
        axis.grid(alpha=0.2)
    for axis in axes[1]:
        axis.set_xlabel("Model Risk Creation Index")
    fig.suptitle(
        "Model RCI versus completed business evaluations "
        "(direct ratings; no composite expert score)"
    )
    path = (
        output_dir
        / "plots"
        / "end_2026"
        / "rci_model_vs_business_evaluations.png"
    )
    _save(fig, path, figure_provenance_label)
    return path


def _canonical_reference_adaptive_pair(
    canonical_runs: pd.DataFrame | None,
) -> tuple[int, Path, Path] | None:
    """Return one successful paired seed for canonical trajectory plots."""

    if canonical_runs is None or canonical_runs.empty:
        return None
    required = {"policy", "seed", "status", "result_dir"}
    if not required.issubset(canonical_runs.columns):
        return None
    physical = canonical_runs.loc[
        canonical_runs["status"].astype(str).eq("ok")
    ].copy()
    if "is_derived" in physical:
        physical = physical.loc[
            pd.to_numeric(
                physical["is_derived"],
                errors="coerce",
            ).fillna(0).eq(0)
        ]
    for seed, group in physical.groupby("seed", sort=True):
        paths = {
            str(row["policy"]): Path(str(row["result_dir"]))
            for _, row in group.iterrows()
        }
        reference = paths.get("mrp_reference")
        adaptive = paths.get("adaptive_daily")
        if reference is not None and adaptive is not None:
            return int(seed), reference, adaptive
    return None


def _canonical_daily_kpis(result_dir: Path) -> pd.DataFrame:
    path = result_dir / "data" / "first_simulation_daily.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeError, pd.errors.ParserError):
        return pd.DataFrame()
    required = {"day", "demand", "served", "backlog_end", "inventory_total"}
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame()
    demand = pd.to_numeric(frame["demand"], errors="coerce").fillna(0.0)
    scale = max(float(demand.replace(0.0, np.nan).median()), 1.0)
    return pd.DataFrame(
        {
            "day": pd.to_numeric(frame["day"], errors="coerce"),
            "service": (
                pd.to_numeric(frame["served"], errors="coerce").fillna(0.0)
                / demand.replace(0.0, np.nan)
            ).fillna(1.0).clip(0.0, 1.0),
            "backlog_days": (
                pd.to_numeric(
                    frame["backlog_end"],
                    errors="coerce",
                ).fillna(0.0)
                / scale
            ),
            "inventory_days": (
                pd.to_numeric(
                    frame["inventory_total"],
                    errors="coerce",
                ).fillna(0.0)
                / scale
            ),
            "demand_scale": scale,
        }
    ).dropna(subset=["day"])


def _canonical_daily_nervousness(
    result_dir: Path,
    *,
    demand_scale: float,
) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    specifications = (
        ("order", "mrp_orders_daily.csv", "release_qty"),
        (
            "production",
            "production_output_products_daily.csv",
            "produced_qty",
        ),
    )
    for name, filename, value_column in specifications:
        path = result_dir / "data" / filename
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except (OSError, UnicodeError, pd.errors.ParserError):
            continue
        if "day" not in frame or value_column not in frame:
            continue
        if name == "order" and "order_type" in frame:
            frame = frame.loc[
                ~frame["order_type"].astype(str).str.startswith("opening_")
            ]
        day = pd.to_numeric(frame["day"], errors="coerce")
        value = pd.to_numeric(
            frame[value_column],
            errors="coerce",
        ).fillna(0.0)
        daily = (
            pd.DataFrame({"day": day, "value": value})
            .dropna(subset=["day"])
            .groupby("day")["value"]
            .sum()
            .sort_index()
        )
        series[f"{name}_nervousness"] = (
            daily.diff().abs().fillna(0.0) / max(float(demand_scale), 1.0)
        )
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).rename_axis("day").reset_index()


def save_end_2026_plots(
    output_dir: Path,
    calibration_frame: pd.DataFrame,
    calibration_evidence: pd.DataFrame,
    prediction_interval: pd.DataFrame,
    physical_envelope: pd.DataFrame,
    paired_summary: pd.DataFrame,
    confusion_summary: pd.DataFrame,
    confusion_regret: pd.DataFrame,
    rci_review: pd.DataFrame,
    canonical_summary: pd.DataFrame | None = None,
    paired_runs: pd.DataFrame | None = None,
    confusion_sensitivity: pd.DataFrame | None = None,
    canonical_runs: pd.DataFrame | None = None,
    completed_business_review: pd.DataFrame | None = None,
    rci_status: Mapping[str, Any] | None = None,
    regime_recovery: pd.DataFrame | None = None,
    figure_provenance_label: str = "",
) -> None:
    plot_dir = output_dir / "plots" / "end_2026"
    plot_dir.mkdir(parents=True, exist_ok=True)
    prediction_portfolio = _portfolio_scope(prediction_interval)
    physical_portfolio = _portfolio_scope(physical_envelope)

    if regime_recovery is not None:
        save_regime_recovery_plot(
            output_dir,
            regime_recovery,
            figure_provenance_label,
        )

    if not calibration_frame.empty:
        regime_order = list(dict.fromkeys(calibration_frame["calibrated_regime"].astype(str)))
        codes = {name: index for index, name in enumerate(regime_order)}
        fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
        axes[0].plot(calibration_frame["day"], calibration_frame["service"], label="service")
        axes[0].plot(calibration_frame["day"], calibration_frame["backlog_days"], label="backlog (demand-days)")
        axes[0].set_title("Canonical trajectory used for regime calibration")
        axes[0].legend()
        axes[1].plot(calibration_frame["day"], calibration_frame["material_cover_days"], label="critical material cover")
        axes[1].plot(calibration_frame["day"], calibration_frame["max_utilization"], label="max utilization")
        axes[1].legend()
        axes[2].step(
            calibration_frame["day"], calibration_frame["calibrated_regime"].map(codes), where="post"
        )
        axes[2].set_yticks(list(codes.values()), list(codes.keys()))
        axes[2].set_xlabel("day")
        axes[2].set_title("Calibrated state-dependent regimes")
        _save(
            fig,
            plot_dir / "regime_calibration_trajectory.png",
            figure_provenance_label,
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        for regime, group in calibration_frame.groupby("calibrated_regime"):
            ax.scatter(
                group["material_cover_days"],
                group["backlog_days"],
                s=18,
                alpha=0.65,
                label=str(regime),
            )
        ax.set_xlabel("critical material cover (demand-days)")
        ax.set_ylabel("backlog (demand-days)")
        ax.set_title("Exploratory separation of trajectory pseudo-regimes")
        ax.legend(fontsize=8, ncol=2)
        _save(
            fig,
            plot_dir / "regime_separation_map.png",
            figure_provenance_label,
        )

    if not calibration_evidence.empty:
        ordered = _executable_threshold_plot_frame(calibration_evidence)
    else:
        ordered = pd.DataFrame()
    if not ordered.empty:
        x = np.arange(len(ordered))
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(x - 0.18, ordered["previous_value"], width=0.36, label="initial threshold")
        ax.bar(x + 0.18, ordered["calibrated_value"], width=0.36, label="calibrated threshold")
        ax.set_xticks(x, ordered["threshold"], rotation=30, ha="right")
        ax.set_title("Executable regime thresholds: initial vs calibrated hypotheses")
        ax.legend()
        _save(
            fig,
            plot_dir / "regime_threshold_comparison.png",
            figure_provenance_label,
        )

    if not prediction_portfolio.empty:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.fill_between(
            prediction_portfolio["day"], prediction_portfolio["risk_lower"], prediction_portfolio["risk_upper"],
            alpha=0.25,
            label="binary-outcome score envelope",
        )
        ax.plot(
            prediction_portfolio["day"],
            prediction_portfolio["risk_center"],
            label="forecast probability score",
        )
        ax.set_ylim(0, 1)
        ax.set_xlabel("day")
        ax.set_ylabel("binary incident score / probability input [0-1]")
        ax.set_title(
            "Operational binary-outcome score envelope "
            "(not a latent-probability confidence interval)"
        )
        ax.legend()
        _save(
            fig,
            plot_dir / "prediction_interval.png",
            figure_provenance_label,
        )

    if not physical_portfolio.empty:
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
        for suffix, style in [("lower", ":"), ("center", "-"), ("upper", "--")]:
            axes[0, 0].plot(physical_portfolio["day"], physical_portfolio[f"availability_multiplier_{suffix}"], linestyle=style, label=suffix)
            axes[0, 1].plot(physical_portfolio["day"], physical_portfolio[f"capacity_multiplier_{suffix}"], linestyle=style)
            axes[1, 0].plot(physical_portfolio["day"], physical_portfolio[f"lead_time_extra_days_{suffix}"], linestyle=style)
            axes[1, 1].plot(physical_portfolio["day"], physical_portfolio[f"quality_yield_multiplier_{suffix}"], linestyle=style)
        axes[0, 0].set_title("Availability multiplier")
        axes[0, 1].set_title("Capacity multiplier")
        axes[1, 0].set_title("Additional lead time (days)")
        axes[1, 1].set_title("Quality-yield multiplier")
        axes[0, 0].legend(title="interval side")
        axes[1, 0].set_xlabel("day")
        axes[1, 1].set_xlabel("day")
        fig.suptitle(
            "Configurable physical perturbation hypotheses mapped from "
            "the operational score envelope"
        )
        _save(
            fig,
            plot_dir / "prediction_to_physical_perturbations.png",
            figure_provenance_label,
        )

        for metric, ylabel, filename in [
            (
                "availability_multiplier",
                "supplier availability multiplier",
                "physical_availability_fan_chart.png",
            ),
            (
                "capacity_multiplier",
                "supplier capacity multiplier",
                "physical_capacity_fan_chart.png",
            ),
        ]:
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.fill_between(
                physical_portfolio["day"],
                physical_portfolio[f"{metric}_lower"],
                physical_portfolio[f"{metric}_upper"],
                alpha=0.25,
                label="physical uncertainty envelope",
            )
            ax.plot(
                physical_portfolio["day"],
                physical_portfolio[f"{metric}_center"],
                label="central physical mapping",
            )
            ax.set_xlabel("day")
            ax.set_ylabel(ylabel)
            ax.set_title(
                f"{ylabel.capitalize()} induced by supplier-risk uncertainty"
            )
            ax.legend()
            _save(fig, plot_dir / filename, figure_provenance_label)

    if not paired_summary.empty:
        ordered = paired_summary.sort_values("mean_delta_score")
        x = np.arange(len(ordered))
        lower = ordered["mean_delta_score"] - ordered["ci95_low_delta_score"]
        upper = ordered["ci95_high_delta_score"] - ordered["mean_delta_score"]
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(x, ordered["mean_delta_score"], yerr=np.vstack([lower.clip(lower=0), upper.clip(lower=0)]), capsize=4)
        ax.axhline(0, linewidth=0.8)
        ax.set_xticks(x, ordered["policy"], rotation=25, ha="right")
        ax.set_ylabel("paired score delta vs MRP (lower is better)")
        ax.set_title("Policy comparison with common random numbers")
        _save(
            fig,
            plot_dir / "paired_policy_comparison.png",
            figure_provenance_label,
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        y = np.arange(len(ordered))
        ax.errorbar(
            ordered["mean_delta_score"],
            y,
            xerr=np.vstack([lower.clip(lower=0), upper.clip(lower=0)]),
            fmt="o",
            capsize=4,
        )
        ax.axvline(0, linewidth=0.8, color="black")
        ax.set_yticks(y, ordered["policy"])
        ax.set_xlabel("paired objective delta vs MRP, 95% CI (lower is better)")
        ax.set_title("Forest plot of paired policy effects")
        _save(
            fig,
            plot_dir / "paired_policy_forest_plot.png",
            figure_provenance_label,
        )

        service_column = "mean_delta_mean_service"
        stock_column = "mean_delta_mean_inventory"
        nervousness_column = "mean_delta_nervousness"
        risk_column = "mean_delta_risk_creation"
        if all(
            column in ordered
            for column in [
                service_column,
                stock_column,
                nervousness_column,
                risk_column,
            ]
        ):
            fig, ax = plt.subplots(figsize=(10, 6))
            size = 40.0 + 100.0 * ordered[nervousness_column].abs()
            points = ax.scatter(
                ordered[stock_column],
                ordered[service_column],
                s=size,
                c=ordered[risk_column],
                cmap="coolwarm",
                alpha=0.8,
            )
            for row in ordered.itertuples():
                ax.annotate(
                    row.policy,
                    (
                        getattr(row, stock_column),
                        getattr(row, service_column),
                    ),
                    fontsize=8,
                )
            ax.axhline(0, linewidth=0.6, color="black")
            ax.axvline(0, linewidth=0.6, color="black")
            ax.set_xlabel("mean stock delta vs MRP (demand-days)")
            ax.set_ylabel("mean service delta vs MRP")
            ax.set_title(
                "Service-stock frontier; marker size=nervousness, colour=created risk"
            )
            fig.colorbar(points, ax=ax, label="RCI delta vs MRP")
            _save(
                fig,
                plot_dir / "service_stock_nervousness_risk_frontier.png",
                figure_provenance_label,
            )

    if paired_runs is not None and not paired_runs.empty and "score" in paired_runs:
        fig, ax = plt.subplots(figsize=(11, 6))
        reference = (
            paired_runs.loc[paired_runs["policy"] == "mrp_reference"]
            .set_index("seed")["score"]
        )
        for policy, group in paired_runs.groupby("policy", sort=False):
            aligned = group.sort_values("seed").copy()
            aligned["delta"] = (
                aligned["score"]
                - aligned["seed"].map(reference)
            )
            values = aligned["delta"].to_numpy(dtype=float)
            count = np.arange(1, len(values) + 1)
            cumulative_mean = np.cumsum(values) / count
            cumulative_square = np.cumsum(values ** 2)
            variance = np.maximum(
                0.0,
                (cumulative_square / count) - cumulative_mean ** 2,
            )
            half_width = 1.96 * np.sqrt(variance) / np.sqrt(count)
            ax.plot(count, cumulative_mean, label=str(policy))
            ax.fill_between(
                count,
                cumulative_mean - half_width,
                cumulative_mean + half_width,
                alpha=0.08,
            )
        ax.axhline(0, linewidth=0.8, color="black")
        ax.set_xlabel("paired seeds included")
        ax.set_ylabel("cumulative mean objective delta vs MRP")
        ax.set_title("Convergence of paired-policy uncertainty intervals")
        ax.legend(fontsize=8, ncol=2)
        _save(
            fig,
            plot_dir / "paired_interval_convergence.png",
            figure_provenance_label,
        )

    if not confusion_summary.empty:
        order = [case for case in ["TP", "FP", "FN", "TN"] if case in set(confusion_summary["case"])]
        ordered = confusion_summary.set_index("case").loc[order].reset_index()
        x = np.arange(len(ordered))
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
        axes[0].bar(x, ordered["mean_service_loss"])
        axes[0].set_title("Service loss")
        axes[1].bar(x, ordered["mean_nervousness_area"])
        axes[1].set_title("Plan/order nervousness")
        axes[2].bar(x, ordered["mean_risk_creation_area"])
        axes[2].set_title("Risk created by response")
        for ax in axes:
            ax.set_xticks(x, ordered["case"])
        fig.suptitle("Explicit true-positive / false-positive / false-negative / true-negative experiments")
        _save(
            fig,
            plot_dir / "forecast_confusion_cases.png",
            figure_provenance_label,
        )

        if "mean_total_cost_proxy" in ordered:
            cost = ordered["mean_total_cost_proxy"].to_numpy(dtype=float)
            cost_label = "purchase + transport cost proxy"
        else:
            # Backward-compatible fallback for legacy summaries created before
            # explicit monetary proxies were exported.
            cost = (
                ordered["mean_service_loss"]
                + ordered["mean_nervousness_area"]
                + ordered["mean_risk_creation_area"]
            ).to_numpy(dtype=float)
            cost_label = "service + nervousness + RCI proxy"
        matrix = np.full((2, 2), np.nan)
        positions = {"TN": (0, 0), "FP": (0, 1), "FN": (1, 0), "TP": (1, 1)}
        for case, value in zip(ordered["case"], cost):
            matrix[positions[str(case)]] = value
        fig, ax = plt.subplots(figsize=(7, 5))
        image = ax.imshow(matrix, cmap="magma")
        ax.set_xticks([0, 1], ["no alert", "alert"])
        ax.set_yticks([0, 1], ["no incident", "incident"])
        ax.set_xlabel("forecast action")
        ax.set_ylabel("physical truth")
        ax.set_title("Exploratory asymmetric forecast-confusion cost")
        for row in range(2):
            for column in range(2):
                ax.text(
                    column,
                    row,
                    f"{matrix[row, column]:.3g}",
                    ha="center",
                    va="center",
                    color="white",
                )
        fig.colorbar(image, ax=ax, label=cost_label)
        _save(
            fig,
            plot_dir / "forecast_confusion_cost_matrix.png",
            figure_provenance_label,
        )

    if not confusion_regret.empty:
        regret = confusion_regret.groupby("case", as_index=False)[[
            "service_loss_regret", "backlog_regret", "nervousness_regret", "risk_creation_regret"
        ]].mean()
        order = [case for case in ["FP", "FN"] if case in set(regret["case"])]
        if order:
            regret = regret.set_index("case").loc[order]
            fig, ax = plt.subplots(figsize=(10, 5))
            regret.plot(kind="bar", ax=ax)
            ax.axhline(0, linewidth=0.8)
            ax.set_ylabel("regret relative to oracle forecast")
            ax.set_title("Operational cost of forecast errors")
            _save(
                fig,
                plot_dir / "forecast_error_regret.png",
                figure_provenance_label,
            )

    if confusion_sensitivity is not None and not confusion_sensitivity.empty:
        sensitivity_metrics = [
            ("service_loss_regret", "service-loss regret"),
            ("total_cost_regret", "cost-proxy regret"),
            ("risk_creation_regret", "risk-creation regret"),
        ]
        available = [
            item for item in sensitivity_metrics if item[0] in confusion_sensitivity
        ]
        if available:
            fig, axes = plt.subplots(
                1, len(available), figsize=(5.2 * len(available), 4.8), squeeze=False
            )
            for axis, (metric, label) in zip(axes[0], available):
                for case in ("FP", "FN"):
                    group = confusion_sensitivity.loc[
                        confusion_sensitivity["case"].astype(str).eq(case)
                    ]
                    if group.empty:
                        continue
                    marginal = (
                        group.groupby("alert_threshold", as_index=False)[metric]
                        .mean()
                        .sort_values("alert_threshold")
                    )
                    axis.plot(
                        marginal["alert_threshold"],
                        marginal[metric],
                        marker="o",
                        label=case,
                    )
                axis.axhline(0.0, linewidth=0.7, color="black")
                axis.set_xlabel("alert threshold (probability)")
                axis.set_ylabel(label)
                axis.legend(title="forecast error")
            fig.suptitle(
                "Alert-threshold regret, marginal over interval width and duration"
            )
            _save(
                fig,
                plot_dir / "forecast_alert_threshold_regret.png",
                figure_provenance_label,
            )

    if not rci_review.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        scatter = ax.scatter(
            rci_review["forecast_nervousness"], rci_review["model_rci"],
            s=40 + 80 * rci_review["model_rci_severity_proxy"].clip(lower=0),
            c=rci_review["forecast_service_loss"], alpha=0.8,
        )
        ax.set_xlabel("order/plan nervousness over review window")
        ax.set_ylabel("model Risk Creation Index")
        ax.set_title("Episodes prepared for procurement and planning review")
        fig.colorbar(scatter, ax=ax, label="service-loss area")
        _save(
            fig,
            plot_dir / "rci_business_review_episodes.png",
            figure_provenance_label,
        )

    save_rci_business_comparison_plot(
        output_dir,
        (
            completed_business_review
            if completed_business_review is not None
            else pd.DataFrame()
        ),
        rci_status or {},
        figure_provenance_label,
    )

    if canonical_summary is not None and not canonical_summary.empty:
        ordered = canonical_summary.sort_values("mean_delta_service_loss")
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(ordered["policy"], ordered["mean_delta_service_loss"])
        ax.axhline(0, linewidth=0.8)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("paired canonical service-loss delta vs MRP")
        ax.set_title("Full-engine canonical replay with paired seeds")
        _save(
            fig,
            plot_dir / "canonical_paired_replay.png",
            figure_provenance_label,
        )

    canonical_pair = _canonical_reference_adaptive_pair(canonical_runs)
    if canonical_pair is not None:
        seed, reference_dir, adaptive_dir = canonical_pair
        reference_daily = _canonical_daily_kpis(reference_dir)
        adaptive_daily = _canonical_daily_kpis(adaptive_dir)
        if not reference_daily.empty and not adaptive_daily.empty:
            fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
            for label, frame in (
                ("MRP reference", reference_daily),
                ("adaptive daily schedule", adaptive_daily),
            ):
                axes[0].plot(frame["day"], frame["service"], label=label)
                axes[1].plot(frame["day"], frame["backlog_days"], label=label)
                axes[2].plot(
                    frame["day"],
                    frame["inventory_days"],
                    label=label,
                )
            axes[0].set_ylabel("service ratio")
            axes[1].set_ylabel("backlog (demand-days)")
            axes[2].set_ylabel("inventory (demand-days)")
            axes[2].set_xlabel("measured day")
            axes[0].legend()
            fig.suptitle(
                "Canonical MRP versus precomputed adaptive daily schedule "
                f"(paired seed {seed}, exploratory)"
            )
            _save(
                fig,
                plot_dir / "canonical_mrp_vs_adaptive_trajectory.png",
                figure_provenance_label,
            )

            reference_nervousness = _canonical_daily_nervousness(
                reference_dir,
                demand_scale=float(
                    reference_daily["demand_scale"].iloc[0]
                ),
            )
            adaptive_nervousness = _canonical_daily_nervousness(
                adaptive_dir,
                demand_scale=float(
                    adaptive_daily["demand_scale"].iloc[0]
                ),
            )
            if (
                not reference_nervousness.empty
                and not adaptive_nervousness.empty
            ):
                fig, axes = plt.subplots(
                    2,
                    1,
                    figsize=(12, 7),
                    sharex=True,
                )
                for label, frame in (
                    ("MRP reference", reference_nervousness),
                    ("adaptive daily schedule", adaptive_nervousness),
                ):
                    if "order_nervousness" in frame:
                        axes[0].plot(
                            frame["day"],
                            frame["order_nervousness"],
                            label=label,
                        )
                    if "production_nervousness" in frame:
                        axes[1].plot(
                            frame["day"],
                            frame["production_nervousness"],
                            label=label,
                        )
                axes[0].set_ylabel(
                    "absolute order change / median daily demand"
                )
                axes[1].set_ylabel(
                    "absolute production change / median daily demand"
                )
                axes[1].set_xlabel("measured day")
                axes[0].legend()
                fig.suptitle(
                    "Canonical order and production nervousness "
                    f"(paired seed {seed}, exploratory)"
                )
                _save(
                    fig,
                    plot_dir
                    / "canonical_order_production_nervousness.png",
                    figure_provenance_label,
                )


def write_end_2026_report(
    output_dir: Path,
    manifest: Mapping[str, Any],
    calibration_evidence: pd.DataFrame,
    paired_summary: pd.DataFrame,
    confusion_summary: pd.DataFrame,
    rci_status: Mapping[str, Any],
    canonical_summary: pd.DataFrame | None,
    confusion_sensitivity: pd.DataFrame | None = None,
) -> None:
    calibration = manifest.get("regime_calibration", {})
    annotation_metadata = calibration.get("regime_annotations", {})
    nominal_calibration = (
        calibration.get("nominal_parameter_calibration") or {}
    )
    nominal_declared = json.dumps(
        nominal_calibration.get("declared_values") or {},
        sort_keys=True,
    )
    nominal_candidate = json.dumps(
        nominal_calibration.get("aggregate_refit_candidate") or {},
        sort_keys=True,
    )
    nominal_effective = json.dumps(
        nominal_calibration.get("effective_values") or {},
        sort_keys=True,
    )
    prediction = manifest.get("prediction_to_physics", {})
    canonical = manifest.get("canonical_replay", {})
    recovery = manifest.get("regime_recovery", {})
    business_label_days = int(annotation_metadata.get("business_label_days") or 0)
    coverage_statements = prediction_coverage_report_lines(prediction)
    provenance_statements = provenance_report_lines(manifest)
    provenance = manifest.get("provenance", {})
    baseline_origin = str(provenance.get("baseline_origin") or "")
    forecast_origin = str(provenance.get("forecast_origin") or "")
    if baseline_origin == "synthetic_fallback":
        evidence_claim_statement = (
            "- This campaign is synthetic fallback evidence throughout; it is "
            "exploratory, non-industrial and not deployment validation."
        )
    elif forecast_origin == "synthetic_prediction_poc":
        evidence_claim_statement = (
            "- The case-study simulation baseline plus synthetic prediction "
            "PoC form hybrid non-industrial evidence; they must not be "
            "presented as industrial observation or deployment validation."
        )
    else:
        evidence_claim_statement = (
            "- Industrial provenance is not established for the complete "
            "baseline/forecast combination; no industrial-observation or "
            "deployment-validation claim is made."
        )
    confidence_by_regime = {
        str(row.regime): str(row.confidence)
        for row in calibration_evidence.itertuples()
    } if not calibration_evidence.empty else dict(
        calibration.get("confidence_by_regime") or {}
    )
    confidence_counts = {
        level: sum(
            confidence == level for confidence in confidence_by_regime.values()
        )
        for level in ("high", "medium", "low")
    }
    regimes_by_confidence = {
        level: [
            regime
            for regime, confidence in confidence_by_regime.items()
            if confidence == level
        ]
        for level in ("high", "medium", "low")
    }
    rci_state = str(rci_status.get("status") or "not_reported")
    if rci_state == "pending_business_review":
        rci_interpretation = (
            "- The generated CSV is a structured review pack for procurement and "
            "planning. Required ratings are incomplete or absent, so the RCI remains "
            "a simulation-supported research hypothesis, not a certified KPI."
        )
        rci_limitation = (
            "- Business validation of RCI must be completed by procurement and "
            "planning experts."
        )
    elif rci_state == "review_available":
        rci_interpretation = (
            "- Complete ratings are available for analysis. Tied votes remain "
            "unresolved; performance uses leave-one-episode-out estimates and "
            "in-sample fit metrics are reported separately. This is not industrial "
            "certification."
        )
        rci_limitation = (
            "- Business ratings are available but require explicit governance "
            "sign-off before any operational RCI threshold is frozen."
        )
    else:
        rci_interpretation = (
            f"- RCI review status `{rci_state}` is not a recognized validation "
            "outcome; no business-validation claim is made."
        )
        rci_limitation = (
            "- Resolve the RCI review status and obtain explicit procurement and "
            "planning sign-off before operational use."
        )
    lines = [
        "# RESILIENCE-SCAN — validation package for end 2026",
        "",
        "## Purpose",
        "",
        "Close the six end-2026 gaps between the existing etudecas prototype and the 2027 robust-control programme: regime calibration, probabilistic-to-physical risk mapping, canonical action replay, paired policy comparison, explicit forecast-error experiments, and business validation of the Risk Creation Index.",
        "",
        "## Evidence provenance and claim status",
        "",
        *provenance_statements,
        evidence_claim_statement,
        "",
        "## 1. Regime calibration on etudecas trajectories",
        "",
        f"- Source mode: `{calibration.get('source_mode')}`",
        f"- Baseline: `{calibration.get('baseline_path')}`",
        f"- Days used: {calibration.get('days', 0)}",
        f"- Material-cover source: `{calibration.get('material_cover_source', 'unknown')}`",
        (
            "- Regime-calibration risk signal source: "
            f"`{calibration.get('calibration_risk_source', 'not_reported')}`; "
            f"dynamic forecast detected: "
            f"`{bool(calibration.get('forecast_risk_is_dynamic', False))}`. "
            "`forecast_fallback` means canonical state/applied-risk artifacts "
            "did not provide a nonzero trajectory over this calibration slice, "
            "so the forecast proxy—not observed industrial incidents—anchors "
            "the risk signal."
        ),
        f"- High / medium / low confidence regime rules: {confidence_counts['high']} / {confidence_counts['medium']} / {confidence_counts['low']}",
        f"- High-confidence regimes: {regimes_by_confidence['high']}; medium-confidence regimes: {regimes_by_confidence['medium']}; low-confidence regimes: {regimes_by_confidence['low']}.",
        "- Confidence applies to the complete ordered regime-classification rule, not to an isolated scalar threshold.",
        (
            "- NOMINAL is an ordered fallthrough rule with confidence "
            f"`{confidence_by_regime.get('NOMINAL', 'not_reported')}`; its legacy "
            "`supplier_stress` scalar is only an exclusion-boundary diagnostic, "
            "not a high-confidence NOMINAL threshold. SUPPLIER_STRESS is a "
            f"distinct rule with confidence `{confidence_by_regime.get('SUPPLIER_STRESS', 'not_reported')}`."
        ),
        (
            f"- Business-labelled days: {business_label_days}; unresolved days "
            "retain explicit pseudo-label provenance."
            if business_label_days > 0
            else "- Business-labelled days: 0; all regime labels in this run are "
            "trajectory pseudo-labels."
        ),
        (
            "- Reduced-model nominal parameter status: "
            f"`{nominal_calibration.get('status', 'not_reported')}`; aggregate "
            f"refit applied: `{bool(nominal_calibration.get('refit_applied', False))}`; "
            "unit comparability: "
            f"`{nominal_calibration.get('unit_comparability', 'not_reported')}`."
        ),
        f"- Declared nominal parameters: `{nominal_declared}`.",
        f"- Aggregate refit candidate (diagnostic): `{nominal_candidate}`.",
        f"- Effective nominal parameters: `{nominal_effective}`.",
        (
            "- Nominal-parameter interpretation: "
            f"{nominal_calibration.get('interpretation', 'not reported')}"
        ),
        "",
    ]
    if not calibration_evidence.empty:
        lines.extend([
            "| Regime | Classification rule | Initial thresholds | Calibrated thresholds | Anchor days | Confidence | Limitations |",
            "|---|---|---|---|---:|---|---|",
            *[
                "| "
                + " | ".join([
                    str(row.regime).replace("|", "\\|"),
                    str(row.classification_rule).replace("|", "\\|"),
                    f"`{row.initial_thresholds}`",
                    f"`{row.calibrated_thresholds}`",
                    str(int(row.anchor_days)),
                    str(row.confidence),
                    str(row.limitations).replace("|", "\\|"),
                ])
                + " |"
                for row in calibration_evidence.itertuples()
            ],
            "",
        ])
    lines.extend([
        "### Descriptive recovery episodes",
        "",
        (
            f"- Definition: {recovery.get('definition', 'not reported')}; "
            "episodes are grouped by their entry regime."
        ),
        (
            f"- Episodes: {recovery.get('episode_count', 0)}; observed "
            f"recoveries: {recovery.get('observed_recoveries', 0)}; "
            f"right-censored: {recovery.get('right_censored_episodes', 0)}; "
            f"left-truncated: {recovery.get('left_truncated_episodes', 0)}."
        ),
        (
            "- This is an exploratory duration measured on the reduced adaptive "
            "trajectory. Censored values are lower bounds; grouping by entry "
            "regime is descriptive and does not identify a causal regime effect."
        ),
        "",
    ])
    recovery_by_regime = recovery.get("by_entry_regime", [])
    if recovery_by_regime:
        lines.extend([
            "| Entry regime | Episodes | Recovered | Right-censored | Median observed recovery (days) |",
            "|---|---:|---:|---:|---:|",
            *[
                (
                    f"| {row.get('entry_regime')} | "
                    f"{int(row.get('episode_count', 0))} | "
                    f"{int(row.get('observed_recoveries', 0))} | "
                    f"{int(row.get('right_censored_episodes', 0))} | "
                    + (
                        f"{float(row['median_observed_recovery_days']):.4g}"
                        if row.get("median_observed_recovery_days") is not None
                        else "not observed"
                    )
                    + " |"
                )
                for row in recovery_by_regime
            ],
            "",
        ])
    lines.extend([
        "## 2. Supplier-prediction uncertainty mapped to physical disruptions",
        "",
        f"- Prediction file: `{prediction.get('prediction_path')}`",
        f"- Input status / granularity: `{prediction.get('input_status', 'not_reported')}` / `{prediction.get('prediction_granularity', 'not_reported')}`",
        f"- Interval method: `{prediction.get('interval_method')}`",
        *coverage_statements,
        f"- Export scopes: {prediction.get('export_scopes', [])}; granular rows / pairs: {prediction.get('granular_interval_rows', 0)} / {prediction.get('granular_pairs', 0)}.",
        f"- Forecast validity: {prediction.get('forecast_validity_days')} days; long-horizon prior centre: {prediction.get('long_horizon_prior_center')}; uncertainty policy: `{prediction.get('uncertainty_policy', 'not_reported')}`.",
        "- Physical outputs: availability, capacity, lead-time, quality-yield and cost envelopes.",
        f"- One-at-a-time mapping sensitivity: {prediction.get('coefficient_sensitivity_rows', 0)} rows for factors {prediction.get('coefficient_sensitivity_factors', [])}.",
        "- Mapping coefficients remain calibration hypotheses; the sensitivity ledger does not replace incident-based estimation.",
        "",
        "## 3. Policy comparison with paired seeds",
        "",
        "Every fixed policy and the adaptive policy are evaluated on the same physical seeds; the retrospective best-fixed oracle is then derived from those paired results. The common-random-number design isolates policy effects from Monte Carlo noise; exports include means, medians, 95% intervals, p90 deltas, win rates, standardized effects and constraint-violation counts.",
        "",
    ])
    if not paired_summary.empty:
        lines.extend([
            "| Policy | Paired runs | Mean score delta | Service win rate | Non-positive RCI rate |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {row.policy} | {int(row.paired_seed_count)} | {row.mean_delta_score:.4g} | {row.service_win_rate_vs_mrp:.1%} | {row.risk_creation_nonpositive_rate:.1%} |"
                for row in paired_summary.itertuples()
            ],
            "",
        ])
    lines.extend([
        "## 4. False positives and false negatives",
        "",
        (
            "The forecast, physical truth and action are separated. A declared "
            "graded bounded response is applied only during forecast-alert "
            "windows; TP/FP/FN/TN cases therefore measure the operational "
            "consequences of acting on a wrong alert or missing a simulated "
            "physical incident."
        ),
        "",
    ])
    if not confusion_summary.empty:
        lines.extend([
            "| Case | Predicted event | Simulated physical truth | Mean service loss | Mean nervousness | Mean RCI area |",
            "|---|---:|---:|---:|---:|---:|",
            *[
                f"| {row.case} | {int(row.predicted_event)} | {int(row.truth_event)} | {row.mean_service_loss:.4g} | {row.mean_nervousness_area:.4g} | {row.mean_risk_creation_area:.4g} |"
                for row in confusion_summary.itertuples()
            ],
            "",
        ])
    if confusion_sensitivity is not None and not confusion_sensitivity.empty:
        lines.extend([
            (
                "Sensitivity uses a full factorial grid over alert threshold, "
                "forecast-interval half-width and bounded-response duration. "
                "Forecast and "
                "physical-truth probabilities are fixed across the threshold "
                "grid; the conservative interval upper bound grades the bounded "
                "response magnitude. Physical-incident and forecast-signal "
                "durations remain fixed, with scenario fingerprints exported "
                "as pairing evidence. It reports unused stock, over-ordering, "
                "nervousness, expediting, cost, supplier stress and regret versus "
                "both a correct-forecast oracle and MRP."
            ),
            (
                f"- Sensitivity rows: {len(confusion_sensitivity)}; thresholds: "
                f"{sorted(confusion_sensitivity['alert_threshold'].unique().tolist())}; "
                f"half-widths: {sorted(confusion_sensitivity['interval_half_width'].unique().tolist())}; "
                f"response durations: {sorted(confusion_sensitivity['alert_response_duration_days'].unique().tolist())}; "
                f"incident durations: {sorted(confusion_sensitivity['incident_duration_days'].unique().tolist())}; "
                f"forecast-signal durations: {sorted(confusion_sensitivity['forecast_signal_duration_days'].unique().tolist())}."
            ),
            "",
        ])
    lines.extend([
        "## 5. Canonical engine reinjection",
        "",
        f"- Mode: `{canonical.get('mode')}`",
        f"- Graph: `{canonical.get('graph_path')}`",
        f"- Status: `{canonical.get('status')}`",
        f"- Integration: `{canonical.get('integration_mode', 'not_reported')}`",
        "- `overlay` prepares inspectable daily schedules and legacy compatibility graph overlays; it does not execute the physical engine.",
        "- `run` keeps the canonical graph unchanged and applies bounded daily controls after MRP calculation and before canonical constraints and lotification.",
        "- The adaptive schedule is precomputed by the reduced model. It is an open-loop daily replay, not canonical closed-loop feedback.",
        "- A canonical `oracle` row, when present, is derived ex post from already executed fixed-policy rows on the same seed (`run_kind=derived_oracle`); it is neither another engine run nor an online policy.",
        (
            "- Canonical response-created risk is the scoped "
            f"`{canonical.get('risk_creation_proxy', {}).get('definition_version', 'not_reported')}` "
            "six-component engine proxy. It is not the reduced-order proxy "
            "submitted to business review."
        ),
        "",
    ])
    if canonical_summary is not None and not canonical_summary.empty:
        lines.extend([
            "| Policy | Paired seeds | Service-loss delta | Backlog-area delta | Nervousness delta |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {row.policy} | {int(row.paired_seed_count)} | {row.mean_delta_service_loss:.4g} | {row.mean_delta_backlog_area_days:.4g} | {row.mean_delta_order_nervousness:.4g} |"
                for row in canonical_summary.itertuples()
            ],
            "",
        ])
    lines.extend([
        "## 6. Risk Creation Index business validation",
        "",
        f"- Status: `{rci_state}`",
        f"- Completed review rows: {rci_status.get('completed_rows', 0)}",
        (
            "- Generated review episodes: "
            f"{rci_status.get('pack_episode_count', 0)} "
            f"(selected={rci_status.get('selected_episode_count', 0)}, "
            f"rejected={rci_status.get('rejected_episode_count', 0)}, "
            f"aggressive={rci_status.get('aggressive_episode_count', 0)}, "
            "review-only aggressive counterfactuals="
            f"{rci_status.get('review_only_counterfactual_count', 0)})."
        ),
        (
            "- Review scope/version: "
            f"`{rci_status.get('validated_proxy_scope', 'not_reported')}` / "
            f"`{rci_status.get('validated_proxy_definition_version', 'not_reported')}`."
        ),
        (
            "- Transferability to the canonical-engine risk proxy: "
            f"`{rci_status.get('canonical_proxy_transferability', 'not_established')}`."
        ),
        rci_interpretation,
        "",
        "## Main limitations",
        "",
        (
            "- Imported business annotations cover only resolved voted days; all "
            "remaining regime labels are pseudo-labels, and thresholds are not "
            "automatically refitted from the imported labels."
            if business_label_days > 0
            else "- Regime labels are calibrated with pseudo-anchors derived from "
            "operational trajectories; industrial labels remain necessary."
        ),
        "- Prediction-to-physics coefficients are explicit and sensitivity-tested but not yet estimated from incident histories.",
        "- Reduced paired/confusion experiments consume case-study demand and risk paths, but reconstruct their own initial stocks, pipeline and dynamics; they are not replays of article/BOM physical states. The canonical-engine campaign is the distinct physical integration evidence.",
        "- The reduced-order controller is a playbook selector, not yet a constrained MPC.",
        "- Daily canonical controls are executable and traced, but they are not recalculated from canonical state during the run.",
        "- Both reduced and canonical oracle rows are retrospective derived benchmarks; no online oracle policy is claimed.",
        "- Reduced-order and canonical response-created-risk proxies use different formulas and scales; thresholds and rankings are not transferable without a dedicated alignment study.",
        rci_limitation,
    ])
    (output_dir / "end_2026_validation_report.md").write_text("\n".join(lines), encoding="utf-8")
