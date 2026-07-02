"""Generic chart and image payload helpers for map visualizations."""

from __future__ import annotations

import base64
import io
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def png_payload_from_bytes(png_bytes: bytes, filename: str) -> dict[str, Any]:
    return {
        "mime": "image/png",
        "data_b64": base64.b64encode(png_bytes).decode("ascii"),
        "filename": filename,
    }


def load_png_payload(png_path: Path) -> dict[str, Any] | None:
    if not png_path.exists():
        return None
    try:
        return png_payload_from_bytes(png_path.read_bytes(), png_path.name)
    except Exception:
        return None


def resolve_plot_payload(base_dir: Path, relative_path: Path, legacy_name: str) -> dict[str, Any] | None:
    candidates = [
        base_dir / relative_path,
        base_dir / legacy_name,
    ]
    for candidate in candidates:
        payload = load_png_payload(candidate)
        if payload is not None:
            return payload
    return None


def densify_daily_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    if not points:
        return []
    by_day = {int(day): float(value) for day, value in points}
    start_day = min(by_day)
    end_day = max(by_day)
    return [(day, by_day.get(day, 0.0)) for day in range(start_day, end_day + 1)]


def densify_event_spike_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    if not points:
        return []
    by_day: dict[int, float] = defaultdict(float)
    for day, value in points:
        by_day[int(day)] += float(value)
    spike_points: list[tuple[int, float]] = []
    for day, value in sorted(by_day.items()):
        spike_points.extend([(day, 0.0), (day, value), (day, 0.0)])
    return spike_points


def build_line_chart_payload(
    series_map: dict[str, list[tuple[int, float]]],
    *,
    title: str,
    y_label: str,
    filename: str,
) -> dict[str, Any] | None:
    usable = {label: pts for label, pts in series_map.items() if pts}
    if not usable:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    colors = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569"]
    fig, ax = plt.subplots(figsize=(9.8, 4.8))
    for idx, (label, points) in enumerate(usable.items()):
        days = [p[0] for p in points]
        values = [p[1] for p in points]
        ax.plot(
            days,
            values,
            label=label,
            linewidth=2.1,
            color=colors[idx % len(colors)],
        )

    ax.set_title(title, fontsize=12, pad=10)
    ax.set_xlabel("Jour")
    ax.set_ylabel(y_label)
    ax.grid(True, which="major", color="#e2e8f0", linewidth=0.9)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    ax.legend(loc="best", fontsize=8.5, frameon=False)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_line_chart_figure(
    series_map: dict[str, list[tuple[int, float]]],
    *,
    title: str,
    y_label: str,
    step_like: bool = False,
    event_like: bool = False,
    note: str | None = None,
    series_styles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    usable = {
        label: (densify_event_spike_series(pts) if event_like else densify_daily_series(pts) if step_like else pts)
        for label, pts in series_map.items()
        if pts
    }
    if not usable:
        return None
    series_payload = []
    for label, points in usable.items():
        style = series_styles.get(label, {}) if isinstance(series_styles, dict) else {}
        show_markers = bool(style.get("show_markers")) or len(points) <= 2
        series_payload.append(
            {
                "label": label,
                "days": [int(day) for day, _ in points],
                "values": [float(value) for _, value in points],
                "show_markers": show_markers,
                **style,
            }
        )
    return {
        "kind": "line_multi",
        "title": title,
        "y_label": y_label,
        "step_like": step_like and not event_like,
        "note": note or "",
        "series": series_payload,
    }


def build_dual_line_multi_panel_figure(
    *,
    title: str,
    top_title: str,
    top_y_label: str,
    top_series_map: dict[str, list[tuple[int, float]]],
    bottom_title: str,
    bottom_y_label: str,
    bottom_series_map: dict[str, list[tuple[int, float]]],
    top_series_styles: dict[str, dict[str, Any]] | None = None,
    bottom_series_styles: dict[str, dict[str, Any]] | None = None,
    top_step_like: bool = False,
    top_event_like: bool = False,
    bottom_step_like: bool = False,
    bottom_event_like: bool = False,
) -> dict[str, Any] | None:
    top_figure = build_line_chart_figure(
        top_series_map,
        title=top_title,
        y_label=top_y_label,
        step_like=top_step_like,
        event_like=top_event_like,
        series_styles=top_series_styles,
    )
    bottom_figure = build_line_chart_figure(
        bottom_series_map,
        title=bottom_title,
        y_label=bottom_y_label,
        step_like=bottom_step_like,
        event_like=bottom_event_like,
        series_styles=bottom_series_styles,
    )
    if top_figure is None and bottom_figure is None:
        return None
    return {
        "kind": "dual_panel_multi",
        "title": title,
        "top": top_figure,
        "bottom": bottom_figure,
    }


def build_bar_chart_figure(
    value_map: dict[str, float | None],
    *,
    title: str,
    y_label: str,
) -> dict[str, Any] | None:
    usable = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    if not usable:
        return None
    return {
        "kind": "bar",
        "title": title,
        "y_label": y_label,
        "labels": [label for label, _ in usable],
        "values": [float(value) for _, value in usable],
    }


def build_dual_panel_figure(
    *,
    title: str,
    top_title: str,
    top_x_label: str,
    top_y_label: str,
    top_kind: str,
    top_x: list[Any],
    top_y: list[float],
    bottom_title: str,
    bottom_x_label: str,
    bottom_y_label: str,
    bottom_kind: str,
    bottom_x: list[Any],
    bottom_y: list[float],
    top_extra_traces: list[dict[str, Any]] | None = None,
    bottom_extra_traces: list[dict[str, Any]] | None = None,
    show_legend: bool = False,
) -> dict[str, Any] | None:
    if not top_x and not bottom_x:
        return None
    return {
        "kind": "dual_panel",
        "title": title,
        "top": {
            "title": top_title,
            "x_label": top_x_label,
            "y_label": top_y_label,
            "kind": top_kind,
            "x": top_x,
            "y": top_y,
            "extra_traces": top_extra_traces or [],
        },
        "bottom": {
            "title": bottom_title,
            "x_label": bottom_x_label,
            "y_label": bottom_y_label,
            "kind": bottom_kind,
            "x": bottom_x,
            "y": bottom_y,
            "extra_traces": bottom_extra_traces or [],
        },
        "show_legend": show_legend,
    }


def build_bar_chart_payload(
    value_map: dict[str, float | None],
    *,
    title: str,
    y_label: str,
    filename: str,
) -> dict[str, Any] | None:
    usable = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    if not usable:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    labels = [label for label, _ in usable]
    values = [float(value) for _, value in usable]
    colors = []
    for label in labels:
        if label == "Base":
            colors.append("#2563eb")
        elif "-" in label:
            colors.append("#d97706")
        else:
            colors.append("#0f766e")

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    bars = ax.bar(labels, values, color=colors, width=0.62)
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_ylabel(y_label)
    ax.grid(True, axis="y", color="#e2e8f0", linewidth=0.9)
    ax.set_axisbelow(True)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    ax.tick_params(axis="x", labelrotation=18)

    ymax = max(values) if values else 0.0
    ymin = min(values) if values else 0.0
    span = max(abs(ymax - ymin), abs(ymax), 1.0)
    pad = span * 0.08
    ax.set_ylim(ymin - pad, ymax + pad)
    for bar, value in zip(bars, values):
        label = f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (pad * 0.15 if value >= 0 else -pad * 0.4),
            label,
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=8.5,
            color="#0f172a",
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_combo_bar_line_payload(
    value_map: dict[str, float | None],
    delta_series_map: dict[str, list[tuple[int, float]]],
    *,
    bar_title: str,
    bar_y_label: str,
    line_title: str,
    line_y_label: str,
    filename: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    usable_bars = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    usable_lines = {label: pts for label, pts in delta_series_map.items() if pts}
    if not usable_bars and not usable_lines:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(9.2, 7.2), gridspec_kw={"height_ratios": [1.0, 1.15]})
    fig.patch.set_facecolor("#ffffff")
    colors = ["#d97706", "#0f766e", "#dc2626", "#7c3aed", "#475569"]

    ax_bar = axes[0]
    if usable_bars:
        labels = [label for label, _ in usable_bars]
        values = [float(value) for _, value in usable_bars]
        bar_colors = []
        for label in labels:
            if label == "Base":
                bar_colors.append("#2563eb")
            elif any(token in label for token in ["x0.", "x0,", "-"]):
                bar_colors.append("#d97706")
            else:
                bar_colors.append("#0f766e")
        bars = ax_bar.bar(labels, values, color=bar_colors, width=0.62)
        ymax = max(values) if values else 0.0
        ymin = min(values) if values else 0.0
        span = max(abs(ymax - ymin), abs(ymax), 1.0)
        pad = span * 0.10
        ax_bar.set_ylim(ymin - pad, ymax + pad)
        for bar, value in zip(bars, values):
            label = f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                value + (pad * 0.10 if value >= 0 else -pad * 0.35),
                label,
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8.3,
                color="#0f172a",
            )
        ax_bar.set_ylabel(bar_y_label)
        ax_bar.tick_params(axis="x", labelrotation=18)
        ax_bar.grid(True, axis="y", color="#e2e8f0", linewidth=0.9)
        ax_bar.set_axisbelow(True)
    else:
        ax_bar.axis("off")
    ax_bar.set_title(bar_title, fontsize=12, pad=10)
    ax_bar.set_facecolor("#ffffff")

    ax_line = axes[1]
    if usable_lines:
        for idx, (label, points) in enumerate(usable_lines.items()):
            days = [p[0] for p in points]
            values = [p[1] for p in points]
            ax_line.plot(
                days,
                values,
                label=label,
                linewidth=2.1,
                color=colors[idx % len(colors)],
            )
        ax_line.axhline(0.0, color="#94a3b8", linewidth=1.0, linestyle="--")
        ax_line.set_xlabel("Jour")
        ax_line.set_ylabel(line_y_label)
        ax_line.grid(True, which="major", color="#e2e8f0", linewidth=0.9)
        ax_line.legend(loc="best", fontsize=8.2, frameon=False)
    else:
        ax_line.axis("off")
    ax_line.set_title(line_title, fontsize=11, pad=8)
    ax_line.set_facecolor("#ffffff")

    if note:
        fig.text(0.5, 0.012, note, ha="center", va="bottom", fontsize=9.5, color="#475569")

    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_note_payload(title: str, message: str, filename: str) -> dict[str, Any] | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.axis("off")
    ax.text(0.5, 0.68, title, ha="center", va="center", fontsize=13, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.38, message, ha="center", va="center", fontsize=11, color="#475569")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)
