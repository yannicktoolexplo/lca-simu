from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


BRIEF_SCHEMA_VERSION = "etudecas.industrial_cascade_brief.v2"
EXPECTED_DEMO_SCHEMA_VERSION = "etudecas.industrial_cascade_demo.v2"
QUALITY_CASCADE_ID = "quality_quarantine_021081_to_268967"
DELAY_CASCADE_ID = "lead_time_delay_338929_to_268091"
REGISTRY_DIR_BY_CASCADE = {
    QUALITY_CASCADE_ID: "risk_registry_01",
    DELAY_CASCADE_ID: "risk_registry_02",
}
FINISHED_ITEM_BY_CASCADE = {
    QUALITY_CASCADE_ID: "item:268967",
    DELAY_CASCADE_ID: "item:268091",
}

# Les fenetres sont choisies par signal, et non appliquees uniformement. Elles
# restent toutes trainantes : aucune valeur future n'entre dans le calcul.
CHART_PRESENTATION = {
    "quality_stock_021081": {
        "window_days": 5,
        "view_days": (0, 480),
        "reason": (
            "Préserver l’alerte amont sur un stock intermittent sans afficher "
            "toute la variabilité quotidienne."
        ),
    },
    "quality_production_268967": {
        "window_days": 7,
        "view_days": (0, 480),
        "reason": (
            "Suivre la cadence hebdomadaire des campagnes sans effacer leurs "
            "décalages de dates."
        ),
    },
    "quality_customer_backlog_268967": {
        "window_days": 14,
        "view_days": (0, 480),
        "reason": (
            "Résumer un retard client persistant tout en conservant son amplitude "
            "et sa chronologie."
        ),
    },
    "delay_stock_338929": {
        "window_days": 14,
        "view_days": (0, 180),
        "reason": (
            "Filtrer le cycle d’approvisionnement sans masquer la tension du "
            "composant."
        ),
    },
    "delay_production_268091": {
        "window_days": 7,
        "view_days": (0, 180),
        "reason": (
            "Respecter le rythme des lots et garder visibles les décalages de "
            "production."
        ),
    },
    "delay_customer_backlog_268091": {
        "window_days": 5,
        "view_days": (0, 180),
        "reason": (
            "Ne pas diluer un retard client bref de dix à dix-sept jours."
        ),
    },
}


@dataclass(frozen=True)
class BriefArtifacts:
    output_dir: Path
    index_path: Path
    results_path: Path
    manifest_path: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _embedded_json(document: str, element_id: str) -> dict[str, Any]:
    pattern = re.compile(
        rf'<script[^>]*id="{re.escape(element_id)}"[^>]*>(.*?)</script>',
        re.DOTALL,
    )
    match = pattern.search(document)
    if match is None:
        raise ValueError(f"Bloc JSON embarque absent: {element_id}")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON embarque attendu: {element_id}")
    return payload


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Valeur numerique attendue: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Valeur finie attendue: {value!r}")
    return number


def _format_number(value: Any, decimals: int = 1) -> str:
    number = _number(value)
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:,.2f} M".replace(",", " ").replace(".", ",")
    if abs(number) >= 10_000:
        return f"{number:,.0f}".replace(",", " ")
    return f"{number:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _format_percent(value: Any) -> str:
    return f"{100.0 * _number(value):.1f} %".replace(".", ",")


def _aggregate(
    demo_data: dict[str, Any], cascade_id: str, solution_id: str
) -> dict[str, Any]:
    matches = [
        row
        for row in demo_data.get("aggregates", [])
        if row.get("cascade_id") == cascade_id
        and row.get("solution_id") == solution_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Agregat unique attendu pour {cascade_id}/{solution_id}: {len(matches)}"
        )
    return matches[0]


def _mean_metric(aggregate: dict[str, Any], metric: str) -> float:
    return _number(aggregate["metrics"][metric]["mean"])


def _max_metric(aggregate: dict[str, Any], metric: str) -> float:
    return _number(aggregate["metrics"][metric]["max"])


def _min_metric(aggregate: dict[str, Any], metric: str) -> float:
    return _number(aggregate["metrics"][metric]["min"])


def _read_registry_csv(
    path: Path,
    *,
    expected_hash: str,
    expected_rows: int,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if _sha256(path) != expected_hash:
        raise ValueError(f"Empreinte du registre incoherente: {path.name}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_rows:
        raise ValueError(f"Nombre de lignes du registre incoherent: {path.name}")
    if any(None in row for row in rows):
        raise ValueError(f"Colonnes surnumeraires dans le registre: {path.name}")
    return rows


def _traceability_summary(
    demo_dir: Path,
    source_manifest: dict[str, Any],
    cascade_id: str,
) -> dict[str, Any]:
    provenance = [
        entry
        for entry in source_manifest.get("risk_registry_provenance", [])
        if entry.get("identity", {}).get("cascade_id") == cascade_id
        and entry.get("identity", {}).get("variant_id") == "incident_no_action"
        and entry.get("identity", {}).get("seed") == 330281
    ]
    if len(provenance) != 1:
        raise ValueError(f"Registre unique attendu pour {cascade_id}")
    entry = provenance[0]
    if entry.get("verification_status") != (
        "campaign_run_verified_and_paired_to_final_campaign"
    ):
        raise ValueError(f"Registre non verifie pour {cascade_id}")
    registry_outputs = entry.get("registry_outputs", {})
    if registry_outputs.get("verified") is not True:
        raise ValueError(f"Sorties du registre non verifiees pour {cascade_id}")

    registry_dir = demo_dir / "data" / REGISTRY_DIR_BY_CASCADE[cascade_id]
    metadata = registry_outputs.get("csv_artifacts", {})

    def rows(artifact_id: str, expected_name: str) -> list[dict[str, str]]:
        artifact = metadata.get(artifact_id, {})
        if artifact.get("filename") != expected_name:
            raise ValueError(
                f"Fichier de registre inattendu pour {cascade_id}/{artifact_id}"
            )
        return _read_registry_csv(
            registry_dir / expected_name,
            expected_hash=str(artifact.get("sha256", "")),
            expected_rows=int(artifact.get("row_count", -1)),
        )

    bundles = rows("bundles", "risk_impact_exposure_bundles.csv")
    entities = rows("entities", "risk_impact_entities.csv")
    client_service = rows("client_service", "risk_impact_client_service.csv")

    bundle_by_id: dict[str, dict[str, str]] = {}
    for row in bundles:
        bundle_id = row.get("exposure_bundle_id", "")
        if not bundle_id or bundle_id in bundle_by_id:
            raise ValueError(f"Bundle de risque duplique ou vide pour {cascade_id}")
        bundle_by_id[bundle_id] = row
    bundle_uoms = {row.get("uom", "") for row in bundle_by_id.values()}
    if len(bundle_uoms) != 1 or "" in bundle_uoms:
        raise ValueError(f"Unite de bundle ambigue pour {cascade_id}")

    production_lots_by_item: dict[str, set[str]] = {}
    for row in entities:
        if row.get("entity_type") != "finished_product_lot":
            continue
        item_id = row.get("item_id", "")
        lot_id = row.get("lot_id", "")
        if not item_id or not lot_id:
            raise ValueError(f"Lot de production incomplet pour {cascade_id}")
        production_lots_by_item.setdefault(item_id, set()).add(lot_id)
    finished_item_id = FINISHED_ITEM_BY_CASCADE[cascade_id]
    finished_lots = production_lots_by_item.get(finished_item_id, set())
    client_lots = {
        row.get("client_lot_id", "")
        for row in client_service
        if row.get("client_lot_id")
    }
    clients = {
        row.get("client_node_id", "")
        for row in client_service
        if row.get("client_node_id")
    }
    if not finished_lots or not client_lots or len(clients) != 1:
        raise ValueError(f"Tracabilite lots/client incomplete pour {cascade_id}")

    return {
        "seed": 330281,
        "variant_id": "incident_no_action",
        "exposure_bundle_count": len(bundle_by_id),
        "exposed_shipped_qty": sum(
            _number(row.get("shipped_qty")) for row in bundle_by_id.values()
        ),
        "exposed_shipped_uom": next(iter(bundle_uoms)),
        "finished_item_id": finished_item_id,
        "finished_lot_count": len(finished_lots),
        "other_production_lot_counts": {
            item_id: len(lot_ids)
            for item_id, lot_ids in sorted(production_lots_by_item.items())
            if item_id != finished_item_id
        },
        "client_lot_count": len(client_lots),
        "client_id": next(iter(clients)),
        "source_hashes": {
            artifact_id: metadata[artifact_id]["sha256"]
            for artifact_id in ("bundles", "entities", "client_service")
        },
    }


def _select_series(
    compact: dict[str, Any],
    *,
    cascade_id: str,
    variant_id: str,
    metric: str,
    node_id: str,
    item_id: str,
) -> dict[str, Any]:
    try:
        rows = compact["cascades"][cascade_id]["variants"][variant_id]["series"]
    except KeyError as exc:
        raise ValueError(
            f"Trajectoire absente: {cascade_id}/{variant_id}"
        ) from exc
    matches = [
        row
        for row in rows
        if row.get("metric") == metric
        and row.get("node_id") == node_id
        and row.get("item_id") == item_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "Serie unique attendue pour "
            f"{cascade_id}/{variant_id}/{metric}/{node_id}/{item_id}: "
            f"{len(matches)}"
        )
    return matches[0]


def _short_axis_number(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f} M".replace(".", ",")
    if abs(value) >= 1_000:
        scaled = value / 1_000
        decimals = 1 if abs(scaled) < 10 else 0
        rendered = f"{scaled:.{decimals}f}"
        if decimals:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered.replace(".", ",") + " k"
    return f"{value:.0f}"


def _trailing_rolling_mean(values: Sequence[Any], window: int) -> list[float]:
    if window < 1:
        raise ValueError("La fenetre glissante doit etre positive")
    numeric_values = [_number(value) for value in values]
    rolling: list[float] = []
    running_sum = 0.0
    for index, value in enumerate(numeric_values):
        running_sum += value
        if index >= window:
            running_sum -= numeric_values[index - window]
        rolling.append(running_sum / min(index + 1, window))
    return rolling


def _svg_chart(
    *,
    title: str,
    subtitle: str,
    days: Sequence[float],
    series: Sequence[dict[str, Any]],
    incident_window: tuple[int, int],
    rolling_window: int,
    smoothing_note: str = "",
    show_bands: bool = False,
    display_window: tuple[int, int] | None = None,
) -> str:
    if len(days) < 2:
        raise ValueError("Au moins deux jours sont requis pour une courbe")
    expected_length = len(days)
    for entry in series:
        row = entry["series"]
        for statistic in ("mean", "min", "max"):
            values = row.get(statistic)
            if not isinstance(values, list) or len(values) != expected_length:
                raise ValueError(
                    f"Longueur invalide pour {title}/{entry['label']}/{statistic}"
                )

    full_rolling_means = [
        _trailing_rolling_mean(entry["series"]["mean"], rolling_window)
        for entry in series
    ]
    if display_window is None:
        plot_indices = list(range(expected_length))
    else:
        display_start, display_end = display_window
        if display_end <= display_start:
            raise ValueError("La vue du graphique doit couvrir au moins deux jours")
        plot_indices = [
            index
            for index, day in enumerate(days)
            if display_start <= _number(day) <= display_end
        ]
        if len(plot_indices) < 2:
            raise ValueError("La vue du graphique ne contient pas assez de jours")
    plot_days = [days[index] for index in plot_indices]
    rolling_means = [
        [values[index] for index in plot_indices] for values in full_rolling_means
    ]

    width, height = 900, 300
    left, right, top, bottom = 72.0, 24.0, 24.0, 48.0
    plot_width = width - left - right
    plot_height = height - top - bottom
    all_values = (
        [
            _number(entry["series"]["max"][index])
            for entry in series
            for index in plot_indices
        ]
        if show_bands
        else [value for values in rolling_means for value in values]
    )
    maximum = max(all_values, default=0.0)
    maximum = maximum if maximum > 1e-12 else 1.0
    maximum *= 1.05
    day_min, day_max = _number(plot_days[0]), _number(plot_days[-1])

    def x_coord(day: float) -> float:
        return left + ((_number(day) - day_min) / (day_max - day_min)) * plot_width

    def y_coord(value: float) -> float:
        return top + plot_height - (_number(value) / maximum) * plot_height

    def line_path(values: Sequence[Any]) -> str:
        return " ".join(
            ("M" if index == 0 else "L")
            + f"{x_coord(plot_days[index]):.2f},{y_coord(_number(value)):.2f}"
            for index, value in enumerate(values)
        )

    grid: list[str] = []
    for tick in range(5):
        value = maximum * tick / 4
        y = y_coord(value)
        grid.append(
            f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{width-right:.1f}" '
            f'y2="{y:.1f}" class="grid"/><text x="{left-9:.1f}" y="{y+4:.1f}" '
            f'class="axis-label" text-anchor="end">{html.escape(_short_axis_number(value))}</text>'
        )
    for day in (day_min, day_min + (day_max - day_min) / 2, day_max):
        x = x_coord(day)
        grid.append(
            f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" '
            f'y2="{height-bottom:.1f}" class="grid vertical"/>'
            f'<text x="{x:.1f}" y="{height-18:.1f}" class="axis-label" '
            f'text-anchor="middle">J{day:.0f}</text>'
        )

    window_start = max(day_min, float(incident_window[0]))
    window_end = min(day_max, float(incident_window[1]))
    window = ""
    if window_end >= window_start:
        window = (
            f'<rect x="{x_coord(window_start):.2f}" y="{top:.2f}" '
            f'width="{max(1.0, x_coord(window_end)-x_coord(window_start)):.2f}" '
            f'height="{plot_height:.2f}" class="incident-window"/>'
        )

    bands: list[str] = []
    lines: list[str] = []
    legend: list[str] = []
    for entry, rolling_mean in zip(series, rolling_means, strict=True):
        row = entry["series"]
        color = entry["color"]
        if show_bands and entry.get("band", False):
            upper = [
                f"{x_coord(plot_days[plot_index]):.2f},"
                f"{y_coord(_number(row['max'][source_index])):.2f}"
                for plot_index, source_index in enumerate(plot_indices)
            ]
            lower = [
                f"{x_coord(plot_days[plot_index]):.2f},"
                f"{y_coord(_number(row['min'][source_index])):.2f}"
                for plot_index, source_index in reversed(
                    list(enumerate(plot_indices))
                )
            ]
            bands.append(
                f'<polygon points="{" ".join(upper + lower)}" '
                f'fill="{html.escape(color)}" opacity="0.09"/>'
            )
        lines.append(
            f'<path d="{line_path(rolling_mean)}" fill="none" '
            f'stroke="{html.escape(color)}" stroke-width="{entry.get("width", 2.2)}" '
            f'stroke-dasharray="{html.escape(str(entry.get("dash", "")))}" '
            f'opacity="{entry.get("opacity", 1.0)}" stroke-linejoin="round" '
            'vector-effect="non-scaling-stroke"/>'
        )
        legend.append(
            '<span><i style="background:'
            + html.escape(color)
            + '"></i>'
            + html.escape(entry["label"])
            + "</span>"
        )

    range_badge = (
        ""
        if display_window is None
        else (
            '<span class="range-label">Vue ciblée '
            f'J{day_min:.0f}–J{day_max:.0f}</span>'
        )
    )
    note = (
        ""
        if not smoothing_note
        else (
            '<p class="chart-note"><strong>Pourquoi cette fenêtre ?</strong> '
            + html.escape(smoothing_note)
            + "</p>"
        )
    )
    return f"""
    <article class="chart-card">
      <div class="chart-head"><div><h3>{html.escape(title)}</h3><p>{html.escape(subtitle)}</p></div><div class="chart-badges"><span class="trend-label">Moyenne glissante {rolling_window} j</span>{range_badge}<span class="window-label">Perturbation fournisseur simulée</span></div></div>
      <svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
        {''.join(grid)}{window}{''.join(bands)}{''.join(lines)}
      </svg>
      <div class="legend">{''.join(legend)}</div>
      {note}
    </article>
    """


def _chart_series(
    compact: dict[str, Any],
    *,
    cascade_id: str,
    variants: Sequence[tuple[str, str, str, bool]],
    metric: str,
    node_id: str,
    item_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            "label": label,
            "color": color,
            "band": band,
            "width": (
                1.6
                if variant_id == "normal"
                else 2.8
                if variant_id == "incident_no_action"
                else 2.6
                if band
                else 2.1
            ),
            "dash": "6 5" if variant_id == "normal" else "",
            "opacity": 0.78 if variant_id == "normal" else 1.0,
            "series": _select_series(
                compact,
                cascade_id=cascade_id,
                variant_id=variant_id,
                metric=metric,
                node_id=node_id,
                item_id=item_id,
            ),
        }
        for variant_id, label, color, band in variants
    ]


def _first_mean_divergence_day(
    compact: dict[str, Any],
    *,
    cascade_id: str,
    metric: str,
    node_id: str,
    item_id: str,
    incident_start_day: int,
) -> int:
    normal = _select_series(
        compact,
        cascade_id=cascade_id,
        variant_id="normal",
        metric=metric,
        node_id=node_id,
        item_id=item_id,
    )["mean"]
    incident = _select_series(
        compact,
        cascade_id=cascade_id,
        variant_id="incident_no_action",
        metric=metric,
        node_id=node_id,
        item_id=item_id,
    )["mean"]
    days = [_number(value) for value in compact["day_axis"]]
    scale = max(
        [abs(_number(value)) for value in normal]
        + [abs(_number(value)) for value in incident]
        + [1.0]
    )
    tolerance = max(1e-9, scale * 1e-6)
    for day, reference, stressed in zip(days, normal, incident, strict=True):
        if day < incident_start_day:
            continue
        if abs(_number(stressed) - _number(reference)) > tolerance:
            return int(day)
    raise ValueError(
        "Aucune divergence moyenne detectee pour "
        f"{cascade_id}/{metric}/{node_id}/{item_id}"
    )


def _conditional_impact_timeline(
    compact: dict[str, Any], cascade_id: str
) -> dict[str, int | str]:
    if cascade_id == QUALITY_CASCADE_ID:
        incident_start_day = 45
        stages = {
            "stock": ("input_stock_end_qty", "SDC-1450", "item:021081"),
            "production": (
                "production_released_qty",
                "M-1430",
                "item:268967",
            ),
            "customer": (
                "customer_backlog_end_qty",
                "C-XXXXX",
                "item:268967",
            ),
        }
    elif cascade_id == DELAY_CASCADE_ID:
        incident_start_day = 0
        stages = {
            "stock": ("input_stock_end_qty", "M-1810", "item:338929"),
            "production": (
                "production_released_qty",
                "M-1810",
                "item:268091",
            ),
            "customer": (
                "customer_backlog_end_qty",
                "C-XXXXX",
                "item:268091",
            ),
        }
    else:
        raise ValueError(f"Cascade inconnue: {cascade_id}")

    divergence_days = {
        stage: _first_mean_divergence_day(
            compact,
            cascade_id=cascade_id,
            metric=identity[0],
            node_id=identity[1],
            item_id=identity[2],
            incident_start_day=incident_start_day,
        )
        for stage, identity in stages.items()
    }
    return {
        "method": "first_material_divergence_of_daily_mean_vs_normal",
        "incident_start_day": incident_start_day,
        "first_stock_effect_day": divergence_days["stock"],
        "first_production_effect_day": divergence_days["production"],
        "first_customer_backlog_day": divergence_days["customer"],
        "stock_to_customer_interval_days": (
            divergence_days["customer"] - divergence_days["stock"]
        ),
        "interpretation": (
            "Intervalle conditionnel du stress test, pas performance mesuree "
            "d'un algorithme de prediction fournisseur."
        ),
    }


def _build_results(
    demo_data: dict[str, Any],
    traceability: dict[str, dict[str, Any]],
    compact: dict[str, Any],
) -> dict[str, Any]:
    quality_combined = _aggregate(demo_data, QUALITY_CASCADE_ID, "combined_response")
    quality_expedited = _aggregate(
        demo_data, QUALITY_CASCADE_ID, "expedited_transport"
    )
    delay_expedited = _aggregate(demo_data, DELAY_CASCADE_ID, "expedited_transport")
    delay_combined = _aggregate(demo_data, DELAY_CASCADE_ID, "combined_response")
    delay_replanning = _aggregate(demo_data, DELAY_CASCADE_ID, "replanning")

    def remaining(aggregate: dict[str, Any]) -> float:
        return _mean_metric(
            aggregate, "remaining_incremental_customer_backlog_qty_days"
        )

    def untreated(aggregate: dict[str, Any]) -> float:
        return _mean_metric(
            aggregate, "no_action_incremental_customer_backlog_qty_days"
        )

    quality_no_action = untreated(quality_combined)
    delay_no_action = untreated(delay_expedited)
    quality_timeline = _conditional_impact_timeline(compact, QUALITY_CASCADE_ID)
    delay_timeline = _conditional_impact_timeline(compact, DELAY_CASCADE_ID)
    return {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "scenario_selection": {
            "mode": "predefined_canonical_demonstrators",
            "ranked_across_network_risks": False,
            "historical_incidents": False,
            "purpose": (
                "Illustrer deux mecanismes complementaires de propagation; "
                "ne pas presenter ces cas comme les risques les plus critiques."
            ),
        },
        "decision_policy": {
            "system_dynamics": "dynamic_state_dependent_supply_simulation",
            "action_mode": "predefined_open_loop_action_windows",
            "closed_loop_regulation_active": False,
            "daily_feedback_redecision": False,
            "interpretation": (
                "Les stocks, encours et retards evoluent dynamiquement, mais les "
                "actions comparees sont programmees a l'avance et ne se recalculent "
                "pas chaque jour a partir de l'etat observe."
            ),
        },
        "supplier_risk_forecast": {
            "primary_subject": True,
            "current_scope": "conditional_supplier_risk_impact_forecast",
            "incident_occurrence_probability_estimated": False,
            "scenario_selected_by_supplier_risk_model": False,
            "calibrated_on_real_supplier_incidents": False,
            "interpretation": (
                "La couche validee ici calcule la propagation conditionnelle "
                "d'un risque fournisseur impose vers les stocks, la production, "
                "les lots et les clients. Elle ne predit pas encore la probabilite "
                "d'apparition de l'incident."
            ),
        },
        "quality": {
            "customer_delay_count": int(quality_combined["customer_exposure_count"]),
            "simulation_count": int(quality_combined["simulation_count"]),
            "conditional_impact_timeline": quality_timeline,
            "traceability_example": traceability[QUALITY_CASCADE_ID],
            "no_action_backlog_qty_days_mean": quality_no_action,
            "no_action_backlog_qty_days_worst": _max_metric(
                quality_combined, "no_action_incremental_customer_backlog_qty_days"
            ),
            "combined": {
                "remaining_backlog_qty_days_mean": remaining(quality_combined),
                "remaining_ratio": remaining(quality_combined) / quality_no_action,
                "days_recovered": _mean_metric(
                    quality_combined, "days_recovered_vs_no_action"
                ),
                "days_recovered_min": _min_metric(
                    quality_combined, "days_recovered_vs_no_action"
                ),
                "days_recovered_max": _max_metric(
                    quality_combined, "days_recovered_vs_no_action"
                ),
                "incremental_cost": _mean_metric(
                    quality_combined,
                    "incremental_decision_total_cost_vs_no_action",
                ),
            },
            "expedited": {
                "remaining_backlog_qty_days_mean": remaining(quality_expedited),
                "remaining_ratio": remaining(quality_expedited) / quality_no_action,
                "days_recovered": _mean_metric(
                    quality_expedited, "days_recovered_vs_no_action"
                ),
                "days_recovered_min": _min_metric(
                    quality_expedited, "days_recovered_vs_no_action"
                ),
                "days_recovered_max": _max_metric(
                    quality_expedited, "days_recovered_vs_no_action"
                ),
                "incremental_cost": _mean_metric(
                    quality_expedited,
                    "incremental_decision_total_cost_vs_no_action",
                ),
            },
        },
        "delay": {
            "customer_delay_count": int(delay_expedited["customer_exposure_count"]),
            "absorbed_count": int(delay_expedited["customer_no_exposure_count"]),
            "simulation_count": int(delay_expedited["simulation_count"]),
            "conditional_impact_timeline": delay_timeline,
            "traceability_example": traceability[DELAY_CASCADE_ID],
            "no_action_backlog_qty_days_mean": delay_no_action,
            "no_action_backlog_qty_days_worst": _max_metric(
                delay_expedited, "no_action_incremental_customer_backlog_qty_days"
            ),
            "expedited": {
                "remaining_backlog_qty_days_mean": remaining(delay_expedited),
                "remaining_ratio": remaining(delay_expedited) / delay_no_action,
                "days_recovered": _mean_metric(
                    delay_expedited, "days_recovered_vs_no_action"
                ),
                "days_recovered_min": _min_metric(
                    delay_expedited, "days_recovered_vs_no_action"
                ),
                "days_recovered_max": _max_metric(
                    delay_expedited, "days_recovered_vs_no_action"
                ),
                "incremental_cost": _mean_metric(
                    delay_expedited,
                    "incremental_decision_total_cost_vs_no_action",
                ),
            },
            "combined": {
                "remaining_backlog_qty_days_mean": remaining(delay_combined),
                "incremental_cost": _mean_metric(
                    delay_combined,
                    "incremental_decision_total_cost_vs_no_action",
                ),
            },
            "replanning": {
                "remaining_backlog_qty_days_mean": remaining(delay_replanning),
                "remaining_ratio": remaining(delay_replanning) / delay_no_action,
                "days_recovered": _mean_metric(
                    delay_replanning, "days_recovered_vs_no_action"
                ),
                "days_recovered_min": _min_metric(
                    delay_replanning, "days_recovered_vs_no_action"
                ),
                "days_recovered_max": _max_metric(
                    delay_replanning, "days_recovered_vs_no_action"
                ),
            },
        },
        "definitions": {
            "backlog_qty_days": (
                "Une unite de demande livree avec un jour de retard vaut une "
                "unite x jour. Ce n'est ni un nombre de commandes, ni du chiffre "
                "d'affaires perdu."
            ),
            "simulation_frequency": (
                "Dix repetitions montrent la variabilite des hypotheses retenues, "
                "pas une probabilite industrielle."
            ),
            "remaining_ratio": (
                "Rapport entre la moyenne du retard avec action et la moyenne du "
                "retard sans action sur dix repetitions; les cas sans retard valent zero."
            ),
            "days_recovered": (
                "Moyenne seulement sur les repetitions ou le scenario sans action "
                "touche le client."
            ),
            "incremental_cost": (
                "Moyenne sur dix repetitions, cas absorbes inclus, en unites "
                "monetaires simulees non calibrees."
            ),
            "paired_state": (
                "Pour chaque graine, les variantes comparees partent du meme etat "
                "physique au jour zero de mesure."
            ),
            "timing_not_volume": (
                "Les solutions deplacent surtout les dates de production et de "
                "service; elles ne creent pratiquement pas de volume net sur l'horizon."
            ),
            "chart_smoothing": (
                "Moyennes glissantes trainantes choisies par graphique: cinq, "
                "sept ou quatorze jours selon la duree du signal. Aucune valeur "
                "future n'entre dans le calcul."
            ),
        },
    }


def _render_html(results: dict[str, Any], compact: dict[str, Any]) -> str:
    days = [_number(value) for value in compact["day_axis"]]
    quality = results["quality"]
    delay = results["delay"]
    quality_timeline = quality["conditional_impact_timeline"]
    delay_timeline = delay["conditional_impact_timeline"]
    quality_trace = quality["traceability_example"]
    delay_trace = delay["traceability_example"]
    quality_intermediate_lots = quality_trace["other_production_lot_counts"].get(
        "item:773474", 0
    )

    quality_variants = (
        ("normal", "Sans incident", "#718096", False),
        ("incident_no_action", "Incident sans action", "#d92d20", True),
        (
            "incident_combined_response",
            "Plan préparé dès J0",
            "#179b67",
            True,
        ),
        ("incident_expedited_transport", "Transport accéléré", "#246bfe", False),
    )
    delay_variants = (
        ("normal", "Sans incident", "#718096", False),
        ("incident_no_action", "Incident sans action", "#d92d20", True),
        ("incident_expedited_transport", "Transport accéléré", "#246bfe", True),
        ("incident_replanning", "Replanification", "#b86b00", False),
    )

    quality_charts = "".join(
        (
            _svg_chart(
                title="Stock du composant 021081",
                subtitle="SDC-1450 — kilogrammes disponibles",
                days=days,
                series=_chart_series(
                    compact,
                    cascade_id=QUALITY_CASCADE_ID,
                    variants=quality_variants,
                    metric="input_stock_end_qty",
                    node_id="SDC-1450",
                    item_id="item:021081",
                ),
                incident_window=(45, 200),
                rolling_window=CHART_PRESENTATION["quality_stock_021081"][
                    "window_days"
                ],
                smoothing_note=CHART_PRESENTATION["quality_stock_021081"][
                    "reason"
                ],
                display_window=CHART_PRESENTATION["quality_stock_021081"][
                    "view_days"
                ],
            ),
            _svg_chart(
                title="Production libérée du produit 268967",
                subtitle="M-1430 — cadence moyenne quotidienne en unités/jour",
                days=days,
                series=_chart_series(
                    compact,
                    cascade_id=QUALITY_CASCADE_ID,
                    variants=quality_variants,
                    metric="production_released_qty",
                    node_id="M-1430",
                    item_id="item:268967",
                ),
                incident_window=(45, 200),
                rolling_window=CHART_PRESENTATION["quality_production_268967"][
                    "window_days"
                ],
                smoothing_note=CHART_PRESENTATION[
                    "quality_production_268967"
                ]["reason"],
                display_window=CHART_PRESENTATION["quality_production_268967"][
                    "view_days"
                ],
            ),
            _svg_chart(
                title="Demande client en retard sur 268967",
                subtitle="Unités en attente — moyenne des dix simulations",
                days=days,
                series=_chart_series(
                    compact,
                    cascade_id=QUALITY_CASCADE_ID,
                    variants=quality_variants,
                    metric="customer_backlog_end_qty",
                    node_id="C-XXXXX",
                    item_id="item:268967",
                ),
                incident_window=(45, 200),
                rolling_window=CHART_PRESENTATION[
                    "quality_customer_backlog_268967"
                ]["window_days"],
                smoothing_note=CHART_PRESENTATION[
                    "quality_customer_backlog_268967"
                ]["reason"],
                display_window=CHART_PRESENTATION[
                    "quality_customer_backlog_268967"
                ]["view_days"],
            ),
        )
    )
    delay_charts = "".join(
        (
            _svg_chart(
                title="Stock du composant 338929",
                subtitle="M-1810 — unités disponibles",
                days=days,
                series=_chart_series(
                    compact,
                    cascade_id=DELAY_CASCADE_ID,
                    variants=delay_variants,
                    metric="input_stock_end_qty",
                    node_id="M-1810",
                    item_id="item:338929",
                ),
                incident_window=(0, 89),
                rolling_window=CHART_PRESENTATION["delay_stock_338929"][
                    "window_days"
                ],
                smoothing_note=CHART_PRESENTATION["delay_stock_338929"][
                    "reason"
                ],
                display_window=CHART_PRESENTATION["delay_stock_338929"][
                    "view_days"
                ],
            ),
            _svg_chart(
                title="Production libérée du produit 268091",
                subtitle="M-1810 — cadence moyenne quotidienne en unités/jour",
                days=days,
                series=_chart_series(
                    compact,
                    cascade_id=DELAY_CASCADE_ID,
                    variants=delay_variants,
                    metric="production_released_qty",
                    node_id="M-1810",
                    item_id="item:268091",
                ),
                incident_window=(0, 89),
                rolling_window=CHART_PRESENTATION["delay_production_268091"][
                    "window_days"
                ],
                smoothing_note=CHART_PRESENTATION["delay_production_268091"][
                    "reason"
                ],
                display_window=CHART_PRESENTATION["delay_production_268091"][
                    "view_days"
                ],
            ),
            _svg_chart(
                title="Demande client en retard sur 268091",
                subtitle="Unités en attente — moyenne des dix simulations",
                days=days,
                series=_chart_series(
                    compact,
                    cascade_id=DELAY_CASCADE_ID,
                    variants=delay_variants,
                    metric="customer_backlog_end_qty",
                    node_id="C-XXXXX",
                    item_id="item:268091",
                ),
                incident_window=(0, 89),
                rolling_window=CHART_PRESENTATION[
                    "delay_customer_backlog_268091"
                ]["window_days"],
                smoothing_note=CHART_PRESENTATION[
                    "delay_customer_backlog_268091"
                ]["reason"],
                display_window=CHART_PRESENTATION[
                    "delay_customer_backlog_268091"
                ]["view_days"],
            ),
        )
    )

    quality_reduction = 1.0 - quality["combined"]["remaining_ratio"]
    quality_expedited_reduction = 1.0 - quality["expedited"]["remaining_ratio"]
    conditional_intervals = (
        int(quality_timeline["stock_to_customer_interval_days"]),
        int(delay_timeline["stock_to_customer_interval_days"]),
    )
    interval_low = min(conditional_intervals)
    interval_high = max(conditional_intervals)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Anticiper la propagation d’un risque fournisseur — synthèse</title>
  <style>
    :root{{--ink:#10233f;--muted:#586a80;--paper:#f4f7fb;--card:#fff;--line:#dbe3ed;--navy:#0b2748;--blue:#246bfe;--green:#11875d;--red:#d92d20;--amber:#a55b00;--shadow:0 16px 42px rgba(18,42,72,.09)}}
    *{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Inter,Segoe UI,Arial,sans-serif}} a{{color:inherit}}
    .hero{{padding:52px max(24px,calc((100vw - 1240px)/2));color:white;background:linear-gradient(125deg,#071a31 0%,#123d70 60%,#0c6f67 100%)}}
    .kicker{{font-size:12px;font-weight:800;letter-spacing:.14em;color:#71e0c8}} h1{{font-size:clamp(38px,5vw,66px);line-height:1.02;max-width:1040px;margin:10px 0 20px}} .hero>p{{font-size:20px;max-width:850px;color:#d7e6f5}}
    .hero-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:32px}} .hero-card{{padding:20px;border:1px solid rgba(255,255,255,.2);border-radius:16px;background:rgba(255,255,255,.09)}} .hero-card strong{{display:block;font-size:34px}} .hero-card span{{color:#d8e5f2}}
    nav{{position:sticky;top:0;z-index:5;display:flex;justify-content:center;gap:10px;overflow:auto;padding:12px;background:rgba(244,247,251,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}} nav a{{white-space:nowrap;text-decoration:none;border:1px solid var(--line);border-radius:999px;background:white;padding:8px 13px;font-size:14px}}
    main{{max-width:1240px;margin:auto;padding:24px 22px 70px}} section{{scroll-margin-top:78px;padding:32px 0;border-bottom:1px solid var(--line)}} h2{{font-size:clamp(29px,3.2vw,42px);line-height:1.12;margin:6px 0 14px}} h3{{margin:0 0 5px}} .eyebrow{{font-size:12px;font-weight:800;letter-spacing:.12em;color:var(--blue)}}
    .lead{{font-size:19px;max-width:970px;color:var(--muted)}} .definition{{border-left:4px solid #7d8b9b;background:white;border-radius:10px;padding:12px 15px;color:var(--muted)}}
    .summary-table{{display:grid;grid-template-columns:1fr 1fr 1fr;background:white;border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}} .summary-table>div{{padding:18px;border-right:1px solid var(--line)}} .summary-table>div:nth-child(3n){{border-right:0}} .summary-table .head{{background:#eaf1f9;font-weight:800}} .summary-table .quality,.summary-table .delay{{border-top:1px solid var(--line)}}
    .chain{{display:flex;align-items:center;gap:8px;overflow:auto;padding:14px;background:white;border:1px solid var(--line);border-radius:14px;margin:18px 0}} .chain span{{white-space:nowrap;background:#edf3ff;border-radius:8px;padding:8px 10px}} .chain b{{color:var(--blue)}}
    .kpis,.decisions,.recommendations,.limits,.risk-flow{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:20px 0}} .kpi,.decision,.recommendations article,.limits article,.risk-flow article{{background:white;border:1px solid var(--line);border-radius:15px;padding:18px;box-shadow:var(--shadow)}} .risk-flow article.current{{border-top:5px solid var(--green)}} .risk-flow .step{{display:block;font-size:12px;font-weight:800;letter-spacing:.1em;color:var(--blue)}} .kpi strong{{display:block;font-size:29px}} .kpi span{{font-size:13px;color:var(--muted)}} .decision.good{{border-top:5px solid var(--green)}} .decision.alt{{border-top:5px solid var(--blue)}} .decision.stop{{border-top:5px solid var(--red)}} .decision .number{{font-size:26px;font-weight:800}}
    .charts{{display:grid;grid-template-columns:1fr;gap:16px;margin-top:22px}} .chart-card{{background:white;border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:var(--shadow)}} .chart-head{{display:flex;justify-content:space-between;gap:20px;align-items:start}} .chart-head p{{margin:0;color:var(--muted)}} .chart-badges{{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}} .window-label,.trend-label,.range-label{{font-size:12px;border-radius:999px;padding:5px 9px;white-space:nowrap}} .window-label{{color:var(--red);background:#fff0ef}} .trend-label{{color:#1355c5;background:#edf3ff}} .range-label{{color:#56677a;background:#edf0f4}} .chart{{display:block;width:100%;height:auto;margin-top:8px}} .grid{{stroke:#dfe5ed;stroke-width:1}} .grid.vertical{{stroke-dasharray:3 5}} .axis-label{{font:12px Segoe UI,Arial;fill:#66778b}} .incident-window{{fill:#f97066;opacity:.09}} .legend{{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted)}} .legend i{{display:inline-block;width:20px;height:3px;vertical-align:middle;margin-right:5px}} .chart-note{{margin:10px 0 0;padding-top:9px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}}
    .callout{{padding:18px;border-radius:14px;background:#eaf7f1;border:1px solid #a9dcc8}} .warning{{padding:18px;border-radius:14px;background:#fff5e9;border:1px solid #edc890}} details{{margin:16px 0;border:1px solid var(--line);border-radius:14px;background:white;padding:13px 16px}} summary{{cursor:pointer;font-weight:800}} details p{{margin:10px 0 0;color:var(--muted)}} footer{{max-width:1240px;margin:auto;padding:26px 22px;color:var(--muted)}}
    @media(max-width:800px){{.hero-grid,.kpis,.decisions,.recommendations,.limits,.risk-flow{{grid-template-columns:1fr}}.summary-table{{grid-template-columns:1fr}}.summary-table>div{{border-right:0;border-top:1px solid var(--line)}}.summary-table .head:first-child{{border-top:0}}.chart-head{{display:block}}}}
  </style>
</head>
<body>
  <header class="hero" id="synthese">
    <div class="kicker">PRÉVISION CONDITIONNELLE DES RISQUES FOURNISSEURS</div>
    <h1>Si un fournisseur se dégrade, quand la production et le client seront-ils touchés ?</h1>
    <p>La démonstration calcule la propagation d’un risque fournisseur imposé vers les stocks, les lots, la production et les clients. Elle ne prédit pas encore la probabilité d’apparition de l’incident.</p>
    <div class="hero-grid">
      <div class="hero-card"><strong>{quality['customer_delay_count']}/{quality['simulation_count']}</strong><span>propagations jusqu’au client si la retenue qualité simulée survient</span></div>
      <div class="hero-card"><strong>{delay['customer_delay_count']}/{delay['simulation_count']}</strong><span>propagations jusqu’au client si le retard simulé de 338929 survient</span></div>
      <div class="hero-card"><strong>{interval_low}–{interval_high} jours</strong><span>entre le premier effet moyen sur le stock et le premier retard client, selon le stress test</span></div>
    </div>
  </header>
  <nav><a href="#synthese">Prévision fournisseur</a><a href="#qualite">Stress test qualité</a><a href="#retard">Stress test 338929</a><a href="#recommandations">Décisions</a><a href="#limites">Limites</a></nav>
  <main>
    <section>
      <div class="eyebrow">RISQUE FOURNISSEUR</div><h2>Ce que nous savons prévoir aujourd’hui — et la prochaine brique à calibrer</h2>
      <div class="risk-flow">
        <article><span class="step">1 — OCCURRENCE</span><h3>Risque fournisseur à 30 / 60 / 90 jours</h3><p><strong>À calibrer avec l’industriel.</strong> Il faut relier OTIF, retards, qualité, commandes ouvertes, capacité et incidents réels pour produire une probabilité exploitable.</p></article>
        <article class="current"><span class="step">2 — PROPAGATION</span><h3>Stocks, production, lots et clients menacés</h3><p><strong>Couche démontrée ici.</strong> Pour un incident donné, le modèle calcule où et quand la perturbation se propage dans le réseau.</p></article>
        <article><span class="step">3 — DÉCISION</span><h3>Action, coût et risque restant</h3><p>Les plans testés comparent transport, achats, stocks et production. Ils sont programmés à l’avance, sans régulation automatique.</p></article>
      </div>
      <p class="callout"><strong>Lecture essentielle :</strong> 9/10 et 2/10 sont des fréquences de propagation conditionnelles à un incident imposé. Ce ne sont pas les probabilités qu’un fournisseur rencontre cet incident.</p>
      <h2>Deux stress tests pour mesurer l’impact si le risque se matérialise</h2>
      <div class="summary-table">
        <div class="head">Stress test fournisseur</div><div class="head">Impact sans action</div><div class="head">Réponse à discuter</div>
        <div class="quality"><strong>Retenue qualité 021081</strong></div><div class="quality">{_format_number(quality['no_action_backlog_qty_days_mean'],0)} unités × jours de retard moyen</div><div class="quality"><strong>Plan préparé dès J0 :</strong> {_format_number(quality['combined']['remaining_backlog_qty_days_mean'],0)}, soit {_format_percent(quality['combined']['remaining_ratio'])} restant</div>
        <div class="delay"><strong>Retard 338929 vers M-1810</strong></div><div class="delay">Le client est touché dans {delay['customer_delay_count']} cas sur {delay['simulation_count']}</div><div class="delay"><strong>Transport accéléré :</strong> retard observé ramené à zéro</div>
      </div>
      <p class="definition"><strong>Pourquoi ces deux stress tests ?</strong> Ils ont été définis à l’avance sur des flux du modèle pour illustrer deux mécanismes complémentaires : une retenue qualité multi-niveaux et un retard composant souvent absorbé. Ils ne sont ni deux incidents historiques observés, ni des risques détectés ou classés par le modèle fournisseur.</p>
      <p class="definition"><strong>Que signifie « solution » ici ?</strong> C’est une option d’action simulée : on repart du même état initial et du même incident, puis on applique un calendrier décidé à l’avance. Le système évolue bien dynamiquement avec ses stocks, encours et retards, mais aucune régulation en boucle fermée ne choisit ou n’ajuste l’action chaque jour dans cette démonstration.</p>
      <details class="solutions-explained"><summary>Concrètement, quelles actions sont présentées ?</summary><p><strong>Transport accéléré :</strong> réduction simulée de 7 jours sur le transport des nouvelles expéditions pendant une fenêtre fixée, avec un surcoût ; aucun transporteur réel n’est sélectionné et le transit déjà engagé n’est pas accéléré.</p><p><strong>Plan préparé dès J0 :</strong> combinaison programmée de stock cible, priorité fournisseur, transport accéléré, achat amont et objectifs de production. C’est le scénario le plus protecteur pour la qualité, mais plusieurs leviers restent approchés.</p><p><strong>Réglage MRP/MPS testé :</strong> modification programmée des quantités commandées et des objectifs de production. Ce n’est pas une replanification APS complète.</p><p>La campagne scientifique teste aussi second fournisseur ou proxy, achat exceptionnel, stock ciblé et priorité fournisseur. Ils sont conservés dans la V6 détaillée mais retirés de cette page pour garder une histoire courte.</p></details>
      <p class="definition"><strong>Comment lire « unités × jours » :</strong> 10 000 unités livrées avec un jour de retard représentent 10 000 unités × jours. Ce n’est ni un nombre de commandes, ni un chiffre d’affaires perdu.</p>
      <p class="definition"><strong>Ce qui change :</strong> les solutions déplacent surtout les dates auxquelles les unités sont produites et servies ; elles ne créent pratiquement pas de volume net supplémentaire sur les 720 jours.</p>
      <details class="method"><summary>Comment les comparaisons et les graphiques sont calculés</summary><p>Pour chaque graine, la référence, l’incident sans action et les actions partent du même état physique au J0 de mesure. Les pourcentages affichés divisent la moyenne du retard avec action par la moyenne du retard sans action sur les dix répétitions, cas sans retard inclus. Les jours récupérés sont moyennés uniquement sur les cas touchés. Les surcoûts sont des moyennes sur dix, en unités monétaires simulées non calibrées — pas en euros.</p><p>Le lissage est traînant et causal : 5 jours pour le stock 021081 et le retard 268091 ; 7 jours pour les deux productions ; 14 jours pour le retard 268967 et le stock 338929. Ces choix limitent le bruit tout en conservant la chronologie propre à chaque signal. Une moyenne de stock positive ne garantit pas que le stock quotidien soit toujours positif à l’intérieur de la fenêtre : les alertes opérationnelles devront donc rester calculées sur les valeurs journalières brutes.</p><p>Les anciennes bandes min–max quotidiennes ont été retirées de cette page : elles mélangeaient une dispersion brute avec des moyennes lissées et écrasaient l’échelle. Les pires cas restent dans les indicateurs, et la dispersion complète reste dans le paquet V6.</p><p>Les vues sont ciblées sur J0–J480 pour le stress qualité et J0–J180 pour le retard 338929. Les 720 jours complets restent disponibles dans le paquet scientifique V6. La moyenne glissante facilite la lecture ; elle n’est pas, à elle seule, un algorithme de prévision.</p></details>
    </section>

    <section id="qualite">
      <div class="eyebrow">STRESS TEST D’IMPACT 1</div><h2>Retenue qualité fournisseur : jusqu’où le risque se propage-t-il ?</h2>
      <p class="lead">Du J45 au J200, les nouveaux lots de 021081 libérés par VD0949099A, VD0960508A et VD0972460A subissent 90 jours supplémentaires avant disponibilité. Le stock existant et la matière déjà en transit ne sont pas retenus ; aucune quantité n’est détruite.</p>
      <p class="definition"><strong>Prévision conditionnelle :</strong> l’effet moyen apparaît d’abord sur le stock au J{quality_timeline['first_stock_effect_day']}, puis sur la production au J{quality_timeline['first_production_effect_day']} et sur le retard client au J{quality_timeline['first_customer_backlog_day']}. Le modèle matérialise ainsi {quality_timeline['stock_to_customer_interval_days']} jours entre le premier effet stock et le premier impact client. Cette fenêtre est simulée ; ce n’est pas encore une avance prédictive mesurée sur des incidents réels.</p>
      <div class="chain"><span>3 sources touchées</span><b>→</b><span>Stock SDC-1450</span><b>→</b><span>Fabrication 773474</span><b>→</b><span>Fabrication 268967</span><b>→</b><span>Client C-XXXXX</span></div>
      <div class="kpis">
        <div class="kpi"><strong>{quality['customer_delay_count']}/{quality['simulation_count']}</strong><span>simulations avec retard client sans action</span></div>
        <div class="kpi"><strong>{_format_number(quality['no_action_backlog_qty_days_mean'],0)}</strong><span>unités × jours de retard moyen sans action</span></div>
        <div class="kpi"><strong>{_format_number(quality['no_action_backlog_qty_days_worst'],0)}</strong><span>unités × jours dans le cas le plus défavorable</span></div>
      </div>
      <div class="decisions">
        <article class="decision good"><h3>Scénario préventif le plus protecteur</h3><p class="number">Plan préparé dès J0</p><p>{_format_number(quality['combined']['remaining_backlog_qty_days_mean'],0)} unités × jours restent, soit une réduction de {_format_percent(quality_reduction)}. {_format_number(quality['combined']['days_recovered'])} jours sont récupérés en moyenne parmi les {quality['customer_delay_count']} cas touchés, avec une plage de {_format_number(quality['combined']['days_recovered_min'])} à {_format_number(quality['combined']['days_recovered_max'])} jours.</p><p><strong>Surcoût moyen simulé :</strong> +{_format_number(quality['combined']['incremental_cost'],0)} unités monétaires.</p></article>
        <article class="decision alt"><h3>Réponse plus légère à recalibrer</h3><p class="number">Transport accéléré</p><p>{_format_number(quality['expedited']['remaining_backlog_qty_days_mean'],0)} unités × jours restent, soit une réduction de {_format_percent(quality_expedited_reduction)}. La moyenne est favorable, mais une répétition touchée est aggravée de {_format_number(abs(quality['expedited']['days_recovered_min']))} jours.</p><p><strong>Surcoût moyen simulé :</strong> +{_format_number(quality['expedited']['incremental_cost'],0)} unités monétaires.</p></article>
        <article class="decision"><h3>Question à poser</h3><p class="number">Combien vaut un jour récupéré ?</p><p>Le plan préparé dès J0 protège davantage, mais il mélange achats, stock, logistique et production, avec plusieurs leviers encore approchés. Les vrais coûts, capacités et contrats doivent trancher.</p></article>
      </div>
      <details class="trace"><summary>Voir un exemple de traçabilité lots / client</summary><p>Répétition détaillée 330281, incident sans action : {quality_trace['exposure_bundle_count']} expéditions amont exposées, soit {_format_number(quality_trace['exposed_shipped_qty'],0)} {quality_trace['exposed_shipped_uom']} comptés une seule fois ; {quality_intermediate_lots} lots intermédiaires 773474, {quality_trace['finished_lot_count']} lots finis 268967 et {quality_trace['client_lot_count']} identifiants de lots servis au client {quality_trace['client_id']}. Cet exemple de généalogie sur une répétition est distinct des moyennes calculées sur dix.</p></details>
      <div class="charts">{quality_charts}</div>
    </section>

    <section id="retard">
      <div class="eyebrow">STRESS TEST D’IMPACT 2</div><h2>Retard fournisseur 338929 : quand la protection cesse-t-elle d’absorber ?</h2>
      <p class="lead">Du J0 au J89, chaque nouvelle expédition de 338929 libérée par SDC-VD0914360C vers M-1810 reçoit 35 jours de transport supplémentaires. La matière déjà en transit n’est pas redatée et les protections existantes absorbent l’incident dans {delay['absorbed_count']} simulations sur {delay['simulation_count']}.</p>
      <p class="definition"><strong>Prévision conditionnelle :</strong> l’effet moyen apparaît sur le stock au J{delay_timeline['first_stock_effect_day']}, sur la production au J{delay_timeline['first_production_effect_day']} et sur le retard client au J{delay_timeline['first_customer_backlog_day']}. Cela laisse {delay_timeline['stock_to_customer_interval_days']} jours simulés entre le premier effet stock et le premier impact client. L’occurrence du retard fournisseur reste imposée, pas prédite.</p>
      <div class="chain"><span>SDC-VD0914360C</span><b>→</b><span>Stock 338929 à M-1810</span><b>→</b><span>Fabrication 268091</span><b>→</b><span>Stock DC-1920</span><b>→</b><span>Client C-XXXXX</span></div>
      <div class="kpis">
        <div class="kpi"><strong>{delay['absorbed_count']}/{delay['simulation_count']}</strong><span>incidents absorbés avant le client</span></div>
        <div class="kpi"><strong>{_format_number(delay['no_action_backlog_qty_days_mean'],0)}</strong><span>unités × jours de retard moyen, cas absorbés inclus</span></div>
        <div class="kpi"><strong>{_format_number(delay['no_action_backlog_qty_days_worst'],0)}</strong><span>unités × jours dans le cas le plus défavorable</span></div>
      </div>
      <div class="decisions">
        <article class="decision good"><h3>Réponse recommandée dans ce test</h3><p class="number">Transport accéléré</p><p>Le réglage retire 7 jours aux nouvelles expéditions. Le retard client observé est ramené à zéro dans les deux cas touchés et {_format_number(delay['expedited']['days_recovered'])} jours sont récupérés en moyenne, avec une plage de {_format_number(delay['expedited']['days_recovered_min'])} à {_format_number(delay['expedited']['days_recovered_max'])} jours.</p><p><strong>Surcoût moyen simulé :</strong> +{_format_number(delay['expedited']['incremental_cost'],0)} unités monétaires.</p></article>
        <article class="decision alt"><h3>Plus cher, sans gain supplémentaire observé</h3><p class="number">Plan combiné</p><p>Il obtient également zéro retard restant, mais son surcoût moyen simulé atteint +{_format_number(delay['combined']['incremental_cost'],0)} unités monétaires.</p></article>
        <article class="decision stop"><h3>Configuration à recalibrer</h3><p class="number">Réglage MRP/MPS testé</p><p>Ce proxy simplifié porte le retard moyen à {_format_number(delay['replanning']['remaining_backlog_qty_days_mean'],0)} unités × jours, soit {_format_percent(delay['replanning']['remaining_ratio'])} du niveau sans action. Cela ne condamne pas une vraie replanification APS.</p></article>
      </div>
      <details class="trace"><summary>Voir un exemple de traçabilité lots / client</summary><p>Répétition détaillée 330281, incident sans action : {delay_trace['exposure_bundle_count']} nouvelles expéditions exposées, soit {_format_number(delay_trace['exposed_shipped_qty'],0)} {delay_trace['exposed_shipped_uom']} comptées une seule fois ; {delay_trace['finished_lot_count']} lots finis 268091 et {delay_trace['client_lot_count']} identifiants de lots servis au client {delay_trace['client_id']}. Cet exemple de généalogie sur une répétition est distinct des moyennes calculées sur dix.</p></details>
      <div class="charts">{delay_charts}</div>
    </section>

    <section id="recommandations">
      <div class="eyebrow">DÉCISIONS</div><h2>Ce que nous proposons de tester avec l’industriel</h2>
      <div class="recommendations">
        <article><h3>1. Construire le signal fournisseur</h3><p>Relier OTIF, retards annoncés, qualité, commandes ouvertes, capacité, dépendance article et couverture projetée.</p></article>
        <article><h3>2. Calibrer la prévision 30 / 60 / 90 jours</h3><p>Rejouer les incidents réels pour mesurer faux positifs, incidents manqués, avance obtenue et qualité des niveaux de risque.</p></article>
        <article><h3>3. Relier chaque alerte à son impact</h3><p>Pour chaque fournisseur à risque, calculer automatiquement les lots, productions et clients exposés, puis comparer les réponses possibles.</p></article>
      </div>
      <p class="callout"><strong>Proposition de collaboration :</strong> partir d’incidents fournisseurs historiques, calibrer le signal d’alerte, valider la physique des lots et les coûts, puis connecter la prévision à la simulation conditionnelle déjà démontrée ici.</p>
    </section>

    <section id="limites">
      <div class="eyebrow">CADRE DE LECTURE</div><h2>Cinq limites à dire clairement</h2>
      <div class="limits">
        <article><h3>Occurrence non encore prédite</h3><p>Les deux perturbations sont imposées. Aucun niveau de risque fournisseur 30 / 60 / 90 jours n’est calculé dans cette page.</p></article>
        <article><h3>Qualité simplifiée</h3><p>La retenue est un délai avant disponibilité, pas encore une quarantaine complète avec inspection, rebut ou retouche.</p></article>
        <article><h3>Coûts non calibrés</h3><p>Les montants sont des unités monétaires du modèle, pas des euros validés.</p></article>
        <article><h3>Leviers partiellement approchés</h3><p>Le plan qualité est préparé dès J0. Le choix réel du transporteur, l’achat direct, le second fournisseur de 338929 et la replanification APS ne sont pas encore représentés complètement.</p></article>
        <article><h3>Actions sans régulation</h3><p>Les calendriers d’action sont fixés à l’avance et ne se corrigent pas selon l’état observé. Les dix répétitions montrent une dispersion, pas une probabilité industrielle.</p></article>
      </div>
      <p class="warning"><strong>Édition légère :</strong> cette page contient les six graphiques utiles et les chiffres de décision. Le CSV scientifique complet de 1,79 Go, les registres détaillés et les anciennes cartes restent dans le paquet V6 séparé.</p>
    </section>
  </main>
  <footer>Page autonome, sans bibliothèque externe et sans accès Internet. Résultats dérivés du paquet scientifique V6 ; aucune simulation n’a été recalculée pour cette édition.</footer>
</body>
</html>
"""


def build_industrial_brief(*, demo_dir: Path, output_dir: Path) -> BriefArtifacts:
    demo_dir = demo_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(output_dir)

    source_manifest_path = demo_dir / "demo_manifest.json"
    source_index_path = demo_dir / "index.html"
    compact_path = demo_dir / "data" / "canonical_cascade_trajectories_compact.json"
    trajectory_manifest_path = (
        demo_dir / "data" / "canonical_cascade_trajectories_manifest.json"
    )
    for path in (
        source_manifest_path,
        source_index_path,
        compact_path,
        trajectory_manifest_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    source_manifest = _load_json(source_manifest_path)
    if source_manifest.get("schema_version") != EXPECTED_DEMO_SCHEMA_VERSION:
        raise ValueError("Version de paquet scientifique inattendue")
    if source_manifest.get("status") != "complete":
        raise ValueError("Le paquet scientifique source n'est pas complet")
    if source_manifest.get("counts", {}).get("cascade_runs") != 180:
        raise ValueError("Les 180 simulations sources sont requises")
    if source_manifest.get("counts", {}).get("minimum_paired_seed_count", 0) < 10:
        raise ValueError("Au moins dix repetitions appariees sont requises")

    trajectory_manifest = _load_json(trajectory_manifest_path)
    compact_hash = _sha256(compact_path)
    if trajectory_manifest.get("outputs", {}).get("compact_json_sha256") != compact_hash:
        raise ValueError("Empreinte du JSON compact incoherente")

    source_document = source_index_path.read_text(encoding="utf-8")
    demo_data = _embedded_json(source_document, "demo-data")
    compact = _load_json(compact_path)
    if len(compact.get("day_axis", [])) != 720:
        raise ValueError("Les 720 jours de trajectoire sont requis")

    traceability = {
        cascade_id: _traceability_summary(demo_dir, source_manifest, cascade_id)
        for cascade_id in (QUALITY_CASCADE_ID, DELAY_CASCADE_ID)
    }
    results = _build_results(demo_data, traceability, compact)
    document = _render_html(results, compact)
    lowered = document.lower()
    if "http://" in lowered or "https://" in lowered or "fetch(" in lowered:
        raise ValueError("La page legere doit etre strictement hors ligne")

    output_dir.mkdir(parents=True, exist_ok=False)
    index_path = output_dir / "index.html"
    results_path = output_dir / "brief_results.json"
    manifest_path = output_dir / "brief_manifest.json"
    index_path.write_text(document, encoding="utf-8")
    results_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "status": "complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": "executive_light_static_svg",
        "source": {
            "demo_package": demo_dir.name,
            "demo_manifest_sha256": _sha256(source_manifest_path),
            "demo_index_sha256": _sha256(source_index_path),
            "trajectory_compact_sha256": compact_hash,
            "traceability_registry_sha256": {
                cascade_id: traceability[cascade_id]["source_hashes"]
                for cascade_id in (QUALITY_CASCADE_ID, DELAY_CASCADE_ID)
            },
        },
        "counts": {
            "source_runs": 180,
            "paired_repetitions_per_cascade": 10,
            "cascades": 2,
            "static_charts": 6,
            "days_per_chart": 720,
        },
        "visualization": {
            "line_transform": "trailing_rolling_mean",
            "charts": {
                chart_id: {
                    "window_days": settings["window_days"],
                    "view_start_day": settings["view_days"][0],
                    "view_end_day": settings["view_days"][1],
                    "selection_reason": settings["reason"],
                }
                for chart_id, settings in CHART_PRESENTATION.items()
            },
            "uses_future_values": False,
            "window_selection": (
                "Per-chart trade-off between roughness reduction, incident-signal "
                "retention and visual delay."
            ),
            "min_max_bands": (
                "excluded_from_light_charts_to_avoid_mixing_unsmoothed_daily_"
                "extrema_with_smoothed_means"
            ),
        },
        "decision_policy": results["decision_policy"],
        "supplier_risk_forecast": results["supplier_risk_forecast"],
        "artifacts": {
            "index": {
                "path": "index.html",
                "sha256": _sha256(index_path),
                "size_bytes": index_path.stat().st_size,
            },
            "results": {
                "path": "brief_results.json",
                "sha256": _sha256(results_path),
                "size_bytes": results_path.stat().st_size,
            },
        },
        "excluded_from_light_pack": [
            "canonical_cascade_trajectories_long.csv",
            "canonical_cascade_trajectories_compact.json",
            "detailed_risk_registry_csv_files",
            "historical_html_dashboards",
            "plotly_runtime",
        ],
        "scientific_scope": (
            "Prevision conditionnelle de propagation derivee des moyennes du "
            "paquet V6; aucune probabilite d'occurrence fournisseur n'est estimee. "
            "Les donnees exhaustives restent dans le paquet scientifique source."
        ),
        "offline": True,
        "no_overwrite": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return BriefArtifacts(
        output_dir=output_dir,
        index_path=index_path,
        results_path=results_path,
        manifest_path=manifest_path,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construit une synthese industrielle autonome et tres legere."
    )
    parser.add_argument("--demo-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifacts = build_industrial_brief(
        demo_dir=args.demo_dir,
        output_dir=args.output_dir,
    )
    print(f"Synthese legere creee: {artifacts.output_dir}")
    print(f"Page principale: {artifacts.index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
