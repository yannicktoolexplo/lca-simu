"""Build the optional frequency-analysis section for RESILIENCE-SCAN maps."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any, Iterable

from etudecas.visualization.maps.chart_payloads import load_png_payload
from etudecas.visualization.maps.map_data_loader import load_json_dict, read_csv_rows
from etudecas.visualization.maps.map_render import fmt_qty, render_data_table


FREQUENCY_DASHBOARD_SCHEMA_VERSION = "etudecas.scan_frequency_dashboard.v2"
_V2_CONTROLLER_SCHEMA_VERSION = "scan.canonical_state_feedback.v2"
_V3_CONTROLLER_SCHEMA_VERSION = "scan.canonical_state_feedback.v3"

_METADATA_NAMES = (
    "canonical_frequency_protocol.json",
    "canonical_frequency_manifest.json",
)
_FIGURE_SPECS = (
    (
        "canonical_frequency_lead_time_realization.png",
        "Délai demandé et délai réellement appliqué",
        "Le panneau de gauche montre le multiplicateur transmis au moteur et celui de droite le délai entier effectivement utilisé. Une superposition des délais pour deux tailles de variation différentes interdit de conclure à une réponse locale.",
    ),
    (
        "canonical_frequency_excitation_response.png",
        "Perturbation imposée et réaction dans le temps",
        "Variation effectivement appliquée, période analysée, changements de régime et réponses physiques.",
    ),
    (
        "canonical_frequency_bode_frf.png",
        "Réaction des sorties selon la fréquence",
        "Rapport entre la taille de l'entrée et celle de la sortie, retard observé et variation d'un cycle à l'autre. Seules les réponses assez fiables sont affichées.",
    ),
    (
        "canonical_frequency_coherence.png",
        "Qualité du lien entre entrée et sortie",
        "Force du signal imposé, ressemblance entre l'entrée et la sortie, et fréquences suffisamment fiables.",
    ),
    (
        "canonical_frequency_resonances.png",
        "Fréquences où l'amplification est la plus forte",
        "Pics d'amplification et dominance des oscillations lentes. Un pic situé à la limite de la zone observée n'est pas une résonance démontrée.",
    ),
    (
        "canonical_frequency_time_frequency.png",
        "Évolution des oscillations présentes dans les commandes",
        "Cette figure montre comment les fréquences présentes dans les commandes V2 évoluent au fil du temps.",
    ),
    (
        "canonical_frequency_stability.png",
        "Répétabilité et comparaison V2/MRP",
        "Variation de la réponse d'un cycle à l'autre et écart entre V2 et le MRP de référence. Cette figure ne prouve pas la stabilité globale.",
    ),
)


def _to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _to_bool(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "oui"}:
        return True
    if normalized in {"0", "false", "no", "non"}:
        return False
    return None


def _deep_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for name in path:
        if not isinstance(current, dict) or name not in current:
            return None
        current = current[name]
    return current


def _first_value(payload: dict[str, Any], paths: Iterable[tuple[str, ...]]) -> Any:
    for path in paths:
        value = _deep_get(payload, path)
        if value not in (None, ""):
            return value
    return None


def _feedback_publication_terms(metadata: dict[str, Any]) -> dict[str, str]:
    """Resolve visible controller wording from protocol metadata."""

    schema_version = str(
        _first_value(
            metadata,
            (
                ("controller", "schema_version"),
                ("protocol", "controller", "schema_version"),
                ("control_policy", "schema_version"),
            ),
        )
        or _V2_CONTROLLER_SCHEMA_VERSION
    )
    if schema_version == _V2_CONTROLLER_SCHEMA_VERSION:
        return {
            "schema_version": schema_version,
            "comparison": "V2/MRP",
            "commands": "commandes V2",
            "controller_subject": "V2",
            "publication_label": "V2",
        }
    controller_label = (
        "régulation adaptative V3"
        if schema_version == _V3_CONTROLLER_SCHEMA_VERSION
        else "régulation adaptative"
    )
    return {
        "schema_version": schema_version,
        "comparison": "feedback/MRP",
        "commands": f"commandes de la {controller_label}",
        "controller_subject": f"la {controller_label}",
        "publication_label": controller_label,
    }


def _figure_specs(publication_terms: dict[str, str]) -> tuple[tuple[str, str, str], ...]:
    """Keep historical V2 cards while relabelling feedback V3 packages."""

    specs = list(_FIGURE_SPECS)
    specs[-2] = (
        specs[-2][0],
        specs[-2][1],
        "Cette figure montre comment les fréquences présentes dans les "
        f"{publication_terms['commands']} évoluent au fil du temps.",
    )
    specs[-1] = (
        specs[-1][0],
        f"Répétabilité et comparaison {publication_terms['comparison']}",
        "Variation de la réponse d'un cycle à l'autre et écart entre "
        f"{publication_terms['controller_subject']} et le MRP de référence. "
        "Cette figure ne prouve pas la stabilité globale.",
    )
    return tuple(specs)


def _row_value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _stability_pattern(row: dict[str, str]) -> str:
    """Return a five-class response pattern, including legacy packages."""

    documented = _row_value(row, "response_pattern", "audit_classification")
    aliases = {
        "nonzero_repeatable": "nonzero_repeatable_response",
        "interior_peak": "interior_period_peak_transient_or_delay",
        "monotonic_growth": "monotonic_growth_detected",
        "other": "other_nonstationary_response",
    }
    documented = aliases.get(documented, documented)
    if documented:
        return documented
    try:
        values = [float(value) for value in json.loads(row["period_rms_json"])]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        if _to_bool(row.get("repeatable_periodic_response")) is True:
            return (
                "no_measurable_response"
                if _to_bool(row.get("measurable_response")) is False
                else "nonzero_repeatable_response"
            )
        return "unclassified"
    if not values or not all(math.isfinite(value) and value >= 0 for value in values):
        return "unclassified"
    floor = _to_float(row.get("numerical_response_floor")) or 1e-12
    tolerance = _to_float(row.get("growth_tolerance")) or 1.10
    maximum = max(values)
    minimum = min(values)
    if maximum <= floor:
        return "no_measurable_response"
    if minimum > floor and maximum / minimum <= tolerance:
        return "nonzero_repeatable_response"
    if (
        len(values) >= 2
        and all(values[index] >= values[index - 1] - floor for index in range(1, len(values)))
        and values[-1] > max(values[0], floor) * tolerance
    ):
        return "monotonic_growth_detected"
    peak = values.index(maximum)
    if (
        len(values) >= 3
        and 0 < peak < len(values) - 1
        and maximum > max(values[0], values[-1], floor) * tolerance
    ):
        return "interior_period_peak_transient_or_delay"
    return "other_nonstationary_response"


def _load_metadata(result_root: Path) -> tuple[dict[str, Any], str]:
    for name in _METADATA_NAMES:
        payload = load_json_dict(result_root / name)
        if payload:
            return payload, name
    return {}, ""


def _metric_card(label: str, value: str, note: str, color: str) -> str:
    return "".join(
        [
            f'<div class="scanMetricCard" style="border-top-color:{html.escape(color, quote=True)}">',
            f'<div class="scanMetricLabel">{html.escape(label)}</div>',
            f'<div class="scanMetricValue">{html.escape(value)}</div>',
            f'<div class="scanMetricNote">{html.escape(note)}</div>',
            "</div>",
        ]
    )


def _figure_html(
    result_root: Path,
    relative_path: str,
    title: str,
    interpretation: str,
) -> str:
    image = load_png_payload(result_root / relative_path)
    if not image:
        return ""
    mime = html.escape(str(image.get("mime") or "image/png"), quote=True)
    data = str(image.get("data_b64") or "")
    if not data:
        return ""
    width, height = _png_dimensions(result_root / relative_path)
    dimensions = (
        f' width="{width}" height="{height}"'
        if width is not None and height is not None
        else ""
    )
    return "".join(
        [
            '<article class="scanFigureCard">',
            f"<h3>{html.escape(title)}</h3>",
            f"<p>{html.escape(interpretation)}</p>",
            f'<img loading="eager" decoding="async"{dimensions} '
            f'src="data:{mime};base64,{data}" '
            f'alt="{html.escape(title, quote=True)}">',
            "</article>",
        ]
    )


def _png_dimensions(path: Path) -> tuple[int | None, int | None]:
    """Read PNG dimensions from IHDR without decoding the image."""

    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None, None
    if (
        len(header) < 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        return None, None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        return None, None
    return width, height


def _frequency_values(rows: Iterable[dict[str, str]]) -> list[float]:
    return [
        numeric
        for row in rows
        if (
            numeric := _to_float(
                _row_value(
                    row,
                    "frequency_cpd",
                    "frequency_cycle_per_day",
                    "frequency_cycles_per_day",
                )
            )
        )
        is not None
        and numeric > 0
    ]


def _frequency_extent(
    rows: Iterable[dict[str, str]],
) -> tuple[float | None, float | None]:
    frequencies = _frequency_values(rows)
    if not frequencies:
        return None, None
    return min(frequencies), max(frequencies)


def _probed_frequency_band(
    metadata: dict[str, Any], response_rows: list[dict[str, str]]
) -> tuple[float | None, float | None]:
    minimum = _to_float(
        _first_value(
            metadata,
            (
                ("frequency_min_cpd",),
                ("frequency_band", "minimum_cpd"),
                ("frequency_band", "min_cpd"),
                ("identification", "frequency_min_cpd"),
            ),
        )
    )
    maximum = _to_float(
        _first_value(
            metadata,
            (
                ("frequency_max_cpd",),
                ("frequency_band", "maximum_cpd"),
                ("frequency_band", "max_cpd"),
                ("identification", "frequency_max_cpd"),
            ),
        )
    )
    frequencies = _frequency_values(response_rows)
    if minimum is None and frequencies:
        minimum = min(frequencies)
    if maximum is None and frequencies:
        maximum = max(frequencies)
    return minimum, maximum


def _format_frequency_band(
    minimum: float | None, maximum: float | None
) -> str:
    if minimum is None or maximum is None:
        return "non documenté"
    return f"{minimum:.5g} à {maximum:.5g} cycle/j"


def _coherence_quality(
    metadata: dict[str, Any], response_rows: list[dict[str, str]]
) -> tuple[float | None, int, int, int, int]:
    threshold = _to_float(
        _first_value(
            metadata,
            (
                ("coherence_threshold",),
                ("identification", "coherence_threshold"),
                ("quality", "coherence_threshold"),
            ),
        )
    )
    eligible = 0
    threshold_pass = 0
    valid = 0
    local_scope = 0
    for row in response_rows:
        explicit = _to_bool(_row_value(row, "valid_bin", "coherent_bin"))
        coherence = _to_float(
            _row_value(row, "coherence", "coherence_squared", "gamma_squared")
        )
        if explicit is None and coherence is None:
            continue
        eligible += 1
        if coherence is not None and threshold is not None and coherence >= threshold:
            threshold_pass += 1
        is_valid = explicit is True or (
            explicit is None
            and coherence is not None
            and threshold is not None
            and coherence >= threshold
        )
        if is_valid:
            valid += 1
        if is_valid and _regime_trace_compatible(row):
            local_scope += 1
    return threshold, threshold_pass, valid, local_scope, eligible


def _regime_trace_compatible(row: dict[str, str]) -> bool:
    """Test supervisor-trace compatibility without implying local linearity."""

    tested = _to_bool(_row_value(row, "tested_amplitude_regime_trace_compatible"))
    if tested is not None:
        return tested
    legacy = _to_bool(_row_value(row, "small_signal_local_claim"))
    if legacy is not None:
        return legacy
    return _row_value(row, "response_regime_scope") in {
        "local_fixed_supervisory_regime_trace",
        "local_operating_condition_without_supervisory_regime",
        "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified",
        "tested_amplitude_no_supervisory_regime_active_set_unverified",
    }


def _is_native_boundary_peak(row: dict[str, str]) -> bool:
    explicit = _to_bool(_row_value(row, "boundary_peak"))
    if explicit is not None:
        return explicit
    classification = _row_value(row, "peak_classification")
    if classification:
        return classification == "native_low_frequency_boundary_dominance"
    period = _to_float(_row_value(row, "peak_period_days", "period_days"))
    return bool(period is not None and period >= 364.5)


def _resonance_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows[:40]:
        native = _row_value(row, "study_kind").startswith("native_")
        classification = _row_value(row, "peak_classification")
        interpretation = (
            "bord basse frequence"
            if native and _is_native_boundary_peak(row)
            else "pic spectral observationnel"
            if native
            else "pic concu hybride (changement de regime)"
            if classification == "designed_hybrid_line_peak"
            else "pic concu local (trace de regime identique)"
        )
        body.append(
            [
                _row_value(row, "policy", "controller"),
                _row_value(row, "regime", "operating_regime", "condition"),
                _row_value(row, "input_signal", "input"),
                _row_value(row, "output_signal", "output"),
                fmt_qty(
                    _row_value(
                        row,
                        "peak_frequency_cpd",
                        "frequency_cpd",
                        "peak_frequency_cycle_per_day",
                        "peak_frequency_cycles_per_day",
                    ),
                    5,
                ),
                fmt_qty(_row_value(row, "peak_period_days", "period_days"), 2),
                fmt_qty(
                    _row_value(
                        row,
                        "peak_gain_db",
                        "magnitude_db",
                        "gain_db",
                        "peak_magnitude_db",
                        "peak_elasticity_db",
                    ),
                    2,
                ),
                fmt_qty(_row_value(row, "coherence", "peak_coherence"), 3),
                interpretation,
            ]
        )
    return render_data_table(
        [
            "Politique",
            "Regime",
            "Entree",
            "Sortie",
            "Frequence pic (cycle/j)",
            "Periode (j)",
            "Gain pic (dB)",
            "Coherence",
            "Lecture",
        ],
        body,
    )


def _stability_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows[:40]:
        ratio = (
            "∞ (demarrage depuis zero)"
            if _to_bool(_row_value(row, "max_to_min_rms_ratio_unbounded")) is True
            else fmt_qty(_row_value(row, "max_to_min_rms_ratio"), 3)
        )
        body.append(
            [
                _row_value(row, "policy", "controller"),
                _row_value(row, "regime", "operating_regime", "condition"),
                _row_value(row, "input_signal", "input"),
                _row_value(row, "output_signal", "output"),
                _row_value(row, "locally_stable", "stable", "stability_status", "status"),
                ratio,
                _row_value(
                    row,
                    "quality_status",
                    "identification_status",
                    "classical_margin_status",
                ),
            ]
        )
    return render_data_table(
        [
            "Politique",
            "Regime",
            "Entree",
            "Sortie",
            "Diagnostic",
            "RMS max/min",
            "Qualite",
        ],
        body,
    )


def _delay_table(rows: list[dict[str, str]]) -> str:
    identified = [
        row for row in rows if _to_float(_row_value(row, "delay_days")) is not None
    ]
    body = []
    for row in identified[:40]:
        body.append(
            [
                _row_value(row, "condition"),
                _row_value(row, "policy"),
                _row_value(row, "input_signal"),
                _row_value(row, "output_signal"),
                fmt_qty(_row_value(row, "delay_days"), 2),
                fmt_qty(_row_value(row, "weighted_r_squared"), 3),
                _row_value(row, "status"),
            ]
        )
    return render_data_table(
        [
            "Condition",
            "Politique",
            "Entree",
            "Sortie",
            "Pente de phase (j)",
            "R2 pondere",
            "Statut",
        ],
        body,
    )


def build_frequency_dashboard_section(
    result_root: Path | None,
) -> dict[str, Any]:
    """Return an optional, self-contained frequency-analysis section.

    A valid package contains one protocol/manifest JSON and the three tabular
    artifacts from the canonical frequency contract. Figures are optional and
    embedded when present. The map never promotes tested-amplitude evidence to
    a local derivative or a global stability claim.
    """

    if result_root is None:
        return {
            "schema_version": FREQUENCY_DASHBOARD_SCHEMA_VERSION,
            "available": False,
            "status": "frequency_results_not_provided",
            "html": "",
            "figure_count": 0,
            "metrics": {},
        }

    root = Path(result_root)
    metadata, metadata_name = _load_metadata(root)
    response_rows = read_csv_rows(root / "canonical_frequency_response.csv")
    resonance_rows = read_csv_rows(root / "canonical_frequency_resonances.csv")
    stability_rows = read_csv_rows(root / "canonical_frequency_stability.csv")
    delay_rows = read_csv_rows(root / "canonical_frequency_delays.csv")
    comparison_rows = read_csv_rows(
        root / "canonical_frequency_closed_loop_comparison.csv"
    )
    if not (
        root.exists()
        and metadata
        and response_rows
        and resonance_rows
        and stability_rows
    ):
        return {
            "schema_version": FREQUENCY_DASHBOARD_SCHEMA_VERSION,
            "available": False,
            "status": "frequency_results_incomplete",
            "html": "",
            "figure_count": 0,
            "metrics": {},
        }

    publication_terms = _feedback_publication_terms(metadata)
    sample_period_days = _to_float(
        _first_value(
            metadata,
            (
                ("sample_period_days",),
                ("sampling", "sample_interval_days"),
                ("sampling", "period_days"),
                ("identification", "sample_period_days"),
            ),
        )
    )
    measured_days = _to_float(
        _first_value(
            metadata,
            (
                ("measured_days",),
                ("horizon_days",),
                ("sampling", "measured_days"),
                ("protocol", "measured_days"),
                ("identification", "measured_days"),
            ),
        )
    )
    minimum_frequency, maximum_frequency = _probed_frequency_band(
        metadata, response_rows
    )
    valid_response_rows = [
        row
        for row in response_rows
        if _to_bool(_row_value(row, "valid_bin", "coherent_bin")) is True
    ]
    regime_compatible_rows = [
        row
        for row in valid_response_rows
        if _regime_trace_compatible(row)
    ]
    valid_frequency_minimum, valid_frequency_maximum = _frequency_extent(
        valid_response_rows
    )
    regime_frequency_minimum, regime_frequency_maximum = _frequency_extent(
        regime_compatible_rows
    )
    (
        coherence_threshold,
        coherence_threshold_pass_bins,
        valid_bins,
        regime_compatible_bins,
        eligible_bins,
    ) = _coherence_quality(metadata, response_rows)
    source_global_claim = _to_bool(
        _first_value(
            metadata,
            (
                ("global_stability_claimed",),
                ("scientific_claim", "global_stability_claimed"),
                ("claims", "global_stability_claimed"),
                ("stability", "global_stability_claimed"),
            ),
        )
    )
    source_claim_conflict = source_global_claim is True

    figure_cards = [
        card
        for filename, title, interpretation in _figure_specs(publication_terms)
        if (card := _figure_html(root, filename, title, interpretation))
    ]
    figures_html = "".join(figure_cards) or (
        '<div class="panelEmptyState">Aucune figure frequentielle disponible.</div>'
    )

    band_text = _format_frequency_band(minimum_frequency, maximum_frequency)
    valid_support_text = _format_frequency_band(
        valid_frequency_minimum, valid_frequency_maximum
    )
    regime_support_text = _format_frequency_band(
        regime_frequency_minimum, regime_frequency_maximum
    )
    valid_text = (
        f"{valid_bins} / {eligible_bins}" if eligible_bins else "non documente"
    )
    valid_coverage = valid_bins / eligible_bins if eligible_bins else None
    coherence_text = (
        f"{coherence_threshold_pass_bins} / {eligible_bins}"
        if eligible_bins
        else "non documente"
    )
    regime_compatible_text = (
        f"{regime_compatible_bins} / {valid_bins}"
        if valid_bins
        else "non documente"
    )
    identified_delay_rows = [
        row
        for row in delay_rows
        if _to_float(_row_value(row, "delay_days")) is not None
    ]
    identified_delay_count = len(identified_delay_rows)
    hybrid_phase_trend_rows = [
        row
        for row in delay_rows
        if _to_float(_row_value(row, "delay_days")) is None
        and _to_float(_row_value(row, "descriptive_phase_slope_days")) is not None
    ]
    hybrid_phase_trend_count = len(hybrid_phase_trend_rows)
    identified_delays_are_command_outputs = bool(
        identified_delay_rows
        and all(
            _row_value(row, "output_signal").startswith("control_")
            for row in identified_delay_rows
        )
    )
    delay_interpretation = (
        f"{identified_delay_count} décalage(s) estimé(s) sur les commandes; "
        "aucun délai physique de transport identifié"
        if identified_delays_are_command_outputs
        else f"{identified_delay_count} décalage(s) estimé(s); interprétation à expertiser"
        if identified_delay_rows
        else (
            f"aucun retard local; {hybrid_phase_trend_count} décalage(s) observé(s) "
            "pendant des changements de régime, sans interprétation comme délai de transport"
            if hybrid_phase_trend_count
            else "aucun retard temporel identifiable"
        )
    )
    reliable_comparisons = [
        row
        for row in comparison_rows
        if _to_bool(_row_value(row, "reliable_comparison")) is True
    ]
    dynamic_reliable_count = sum(
        _to_bool(_row_value(row, "dynamic_feedback_modulation_identified")) is True
        for row in reliable_comparisons
    )
    reliable_attenuation = [
        value
        for row in reliable_comparisons
        if (
            value := _to_float(
                _row_value(
                    row,
                    "feedback_minus_mrp_attenuation_db",
                    "v2_minus_mrp_attenuation_db",
                )
            )
        )
        is not None
    ]
    reliable_attenuation_median = (
        sorted(reliable_attenuation)[len(reliable_attenuation) // 2]
        if reliable_attenuation
        else None
    )
    native_boundary_peak_count = sum(
        _row_value(row, "study_kind").startswith("native_")
        and _is_native_boundary_peak(row)
        for row in resonance_rows
    )
    stability_patterns = [_stability_pattern(row) for row in stability_rows]
    no_response_count = stability_patterns.count("no_measurable_response")
    repeatable_count = stability_patterns.count("nonzero_repeatable_response")
    interior_peak_count = stability_patterns.count(
        "interior_period_peak_transient_or_delay"
    )
    monotonic_growth_count = stability_patterns.count("monotonic_growth_detected")
    other_nonstationary_count = stability_patterns.count(
        "other_nonstationary_response"
    )
    # Historical three-way status counts remain exposed for compatibility.
    growth_count = sum(
        _row_value(row, "source_status", "status")
        == "period_to_period_growth_detected"
        for row in stability_rows
    )
    nonstationary_count = sum(
        _row_value(row, "source_status", "status")
        == "period_to_period_nonstationarity_detected"
        for row in stability_rows
    )
    resonance_display_count = min(40, len(resonance_rows))
    stability_display_count = min(40, len(stability_rows))
    resonance_display_note = (
        f"Affichage limité aux {resonance_display_count} premières lignes sur "
        f"{len(resonance_rows)}; le CSV canonique contient la table complète."
        if len(resonance_rows) > resonance_display_count
        else f"Les {len(resonance_rows)} lignes disponibles sont affichées."
    )
    stability_display_note = (
        f"Affichage limité aux {stability_display_count} premières lignes sur "
        f"{len(stability_rows)}; le CSV canonique contient la table complète."
        if len(stability_rows) > stability_display_count
        else f"Les {len(stability_rows)} lignes disponibles sont affichées."
    )
    cards = [
        _metric_card(
            "Pas de temps",
            (
                f"{sample_period_days:g} jour"
                if sample_period_days is not None
                else "non documente"
            ),
            (
                f"horizon {measured_days:g} jours"
                if measured_days is not None
                else "horizon non documente"
            ),
            "#2563eb",
        ),
        _metric_card(
            "Fréquences testées",
            band_text,
            "zone couverte par les perturbations; toutes les fréquences ne donnent pas forcément une réponse exploitable",
            "#0f766e",
        ),
        _metric_card(
            "Lien entrée-sortie au-dessus du seuil",
            coherence_text,
            (
                f"seuil {coherence_threshold:g}; le franchir ne suffit pas à valider une réponse"
                if coherence_threshold is not None
                else "seuil non documente"
            ),
            "#7c3aed",
        ),
        _metric_card(
            "Fréquences avec réponse exploitable",
            valid_support_text,
            (
                f"{valid_text} lignes; couverture {valid_coverage:.1%}; "
                "réponse mesurable + lien entrée-sortie suffisant + valeurs bornées + répétabilité"
                if valid_coverage is not None
                else "couverture non documentée"
            ),
            "#334155",
        ),
        _metric_card(
            "Même succession de régimes",
            regime_support_text,
            f"{regime_compatible_text} réponses valides sans changement de la succession des régimes",
            "#0f766e",
        ),
        _metric_card(
            "Pics d'amplification",
            str(len(resonance_rows)),
            f"candidats; {native_boundary_peak_count} pics natifs en bord basse frequence",
            "#d97706",
        ),
        _metric_card(
            "Retards temporels estimables",
            (
                f"{identified_delay_count} sans changement de régime / "
                f"{hybrid_phase_trend_count} avec changement de régime"
                if delay_rows
                else "non documente"
            ),
            delay_interpretation,
            "#475569",
        ),
        _metric_card(
            f"Comparaison {publication_terms['comparison']}",
            (
                f"{len(reliable_comparisons)} / {len(comparison_rows)}"
                if comparison_rows
                else "non documente"
            ),
            (
                f"{reliable_attenuation_median:+.3f} dB; "
                f"{dynamic_reliable_count} effet dynamique fiable; résultat non concluant"
                if reliable_attenuation_median is not None
                else "aucune ligne fiable"
            ),
            "#7c3aed",
        ),
        _metric_card(
            "Réponses non nulles répétables",
            f"{repeatable_count} / {len(stability_rows)}",
            (
                f"{no_response_count} sans réponse mesurable; {monotonic_growth_count} "
                f"croissances monotones; {interior_peak_count} pics intérieurs; "
                "ni stabilité ni marge classique"
            ),
            "#be123c",
        ),
    ]

    source_claim_note = (
        " Le paquet source indiquait une stabilité globale; cette vue ne retient "
        "pas cette conclusion."
        if source_claim_conflict
        else ""
    )
    protocol_table = render_data_table(
        ["Element", "Valeur"],
        [
            ["Fichier de référence", metadata_name],
            ["Format source", str(metadata.get("schema_version") or "non documente")],
            ["Fréquences testées", band_text],
            ["Fréquences avec réponse exploitable", valid_support_text],
            ["Même succession de régimes", regime_support_text],
            [
                "Seuil minimal du lien entrée-sortie",
                (
                    f"{coherence_threshold:g}"
                    if coherence_threshold is not None
                    else "non documente"
                ),
            ],
            [
                "Interprétation autorisée",
                "Réponses empiriques aux variations testées; contraintes physiques actives non vérifiées",
            ],
            ["Stabilité globale démontrée", "non"],
        ],
    )
    section_html = "".join(
        [
            '<div class="scanEvidenceBanner">Cette analyse mesure comment le système '
            "réagit à des oscillations imposées. Les résultats dépendent de l'état, "
            "du régime et de la taille de la variation. Quelques réponses conservent "
            "la même succession de régimes, mais nous n'avons pas vérifié que les mêmes "
            "contraintes physiques restent actives lorsque la variation diminue. Nous "
            "ne présentons donc ni une réponse locale linéaire, ni une preuve de "
            "stabilité globale.",
            html.escape(source_claim_note),
            "</div>",
            f'<div class="scanMetricGrid">{"".join(cards)}</div>',
            '<section class="scanDashboardSection"><h3>Figures frequentielles</h3>',
            f'<div class="scanFigureGrid">{figures_html}</div>',
            "</section>",
            '<section class="scanDashboardSection"><h3>Ce qui a été mesuré</h3>',
            '<p class="scanSectionNote">Les conclusions sont limitées aux fréquences, '
            "entrées, sorties et régimes dont la qualité a été vérifiée.</p>",
            protocol_table,
            "</section>",
            '<section class="scanDashboardSection"><h3>Fréquences où l amplification est forte</h3>',
            '<p class="scanSectionNote">Les pics proches de 365 jours sont situés à la limite des oscillations lentes observables; ils ne démontrent pas une résonance interne.</p>',
            f'<p class="scanSectionNote">{html.escape(resonance_display_note)}</p>',
            _resonance_table(resonance_rows),
            "</section>",
            (
                '<section class="scanDashboardSection"><h3>Retards temporels estimables</h3>'
                f'<p class="scanSectionNote">{html.escape(delay_interpretation)}. '
                f'Affichage de {identified_delay_count} estimation(s) sans changement de régime et '
                f'{hybrid_phase_trend_count} estimation(s) avec changement de régime sur '
                f'{len(delay_rows)} diagnostics. '
                'Un décalage observé entre entrée et sortie ne prouve pas à lui seul le délai de transport physique de la chaîne logistique.</p>'
                + _delay_table(delay_rows)
                + "</section>"
                if delay_rows
                else ""
            ),
            '<section class="scanDashboardSection"><h3>Diagnostics période-à-période</h3>',
            f'<p class="scanSectionNote">{html.escape(stability_display_note)} '
            "Ces résultats ne constituent ni une preuve de stabilité, ni une marge de stabilité classique.</p>",
            _stability_table(stability_rows),
            "</section>",
            '<section class="scanDashboardSection scanLimitations"><h3>Limites de lecture</h3>',
            "<ul><li>Si le lien entre l'entrée et la sortie est trop faible, nous "
            "n'interprétons ni l'amplification ni le retard.</li><li>Une marge de "
            "stabilité classique n'aurait de sens qu'autour d'un seul régime et d'un "
            "modèle local continu.</li><li>Aucune stabilité globale, robustesse "
            "industrielle ou causalité sur données réelles n'est revendiquée.</li>"
            "<li>Le protocole conserve trois cycles après en avoir écarté un et désactive "
            "les délais aléatoires. Il reste à tester d'autres calendriers d'oscillation, "
            "plusieurs entrées simultanées et les transferts entre fréquences.</li>"
            f"<li>La comparaison {publication_terms['comparison']} n'est interprétée "
            "que si les deux réponses sont "
            "fiables, physiquement actives et non nulles.</li></ul></section>",
        ]
    )
    return {
        "schema_version": FREQUENCY_DASHBOARD_SCHEMA_VERSION,
        "available": True,
        "status": "ready",
        "html": section_html,
        "figure_count": len(figure_cards),
        "metrics": {
            "metadata_file": metadata_name,
            "response_row_count": len(response_rows),
            "resonance_row_count": len(resonance_rows),
            "stability_row_count": len(stability_rows),
            "valid_frequency_bin_count": valid_bins,
            "coherence_threshold_pass_bin_count": coherence_threshold_pass_bins,
            "tested_amplitude_regime_compatible_bin_count": regime_compatible_bins,
            "local_small_signal_derivative_bin_count": 0,
            # Deprecated key retained for consumers of schema v1.  Its value is
            # now literal: regime compatibility alone identifies no derivative.
            "local_small_signal_bin_count": 0,
            "eligible_frequency_bin_count": eligible_bins,
            "identified_phase_slope_count": identified_delay_count,
            "hybrid_descriptive_phase_trend_count": hybrid_phase_trend_count,
            "delay_diagnostic_row_count": len(delay_rows),
            "native_boundary_peak_count": native_boundary_peak_count,
            "probed_frequency_band_cpd": {
                "minimum": minimum_frequency,
                "maximum": maximum_frequency,
            },
            "numerically_valid_frequency_support_cpd": {
                "minimum": valid_frequency_minimum,
                "maximum": valid_frequency_maximum,
            },
            "regime_compatible_frequency_support_cpd": {
                "minimum": regime_frequency_minimum,
                "maximum": regime_frequency_maximum,
            },
            "period_to_period_growth_count": growth_count,
            "period_to_period_nonstationarity_count": nonstationary_count,
            "no_measurable_response_count": no_response_count,
            "nonzero_repeatable_response_count": repeatable_count,
            "interior_period_peak_count": interior_peak_count,
            "monotonic_growth_count": monotonic_growth_count,
            "other_nonstationary_response_count": other_nonstationary_count,
            "closed_loop_comparison_row_count": len(comparison_rows),
            "reliable_closed_loop_comparison_count": len(reliable_comparisons),
            "dynamic_reliable_closed_loop_comparison_count": dynamic_reliable_count,
            "feedback_controller_schema_version": publication_terms[
                "schema_version"
            ],
            "feedback_publication_label": publication_terms[
                "publication_label"
            ],
            "claim_scope": "empirical_tested_amplitude_regime_conditioned_active_set_unverified",
            "global_stability_claimed": False,
            "source_global_stability_claimed": source_global_claim,
            "source_claim_conflict": source_claim_conflict,
        },
    }


__all__ = [
    "FREQUENCY_DASHBOARD_SCHEMA_VERSION",
    "build_frequency_dashboard_section",
]
