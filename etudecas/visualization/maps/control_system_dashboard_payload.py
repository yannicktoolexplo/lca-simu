"""Build the optional control-system analysis section for RESILIENCE-SCAN.

The renderer is deliberately conservative: numerical properties are presented
as properties of the documented local model, and rejected or undocumented
pole estimates are never promoted to validated system poles.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any, Iterable

from etudecas.visualization.maps.chart_payloads import load_png_payload
from etudecas.visualization.maps.map_data_loader import load_json_dict, read_csv_rows
from etudecas.visualization.maps.map_render import render_data_table


CONTROL_SYSTEM_DASHBOARD_SCHEMA_VERSION = (
    "etudecas.scan_control_system_dashboard.v1"
)
_MANIFEST_NAME = "canonical_control_system_manifest.json"
_REPORT_NAME = "canonical_control_system_report.md"
_NEGATIVE_STATUS_MARKERS = (
    "reject",
    "invalid",
    "explor",
    "not_validated",
    "not validated",
    "non_valid",
    "non valid",
    "unverified",
    "unsupported",
)
_POSITIVE_STATUS_MARKERS = (
    "accepted",
    "validated",
    "validé",
    "valide",
)


def _to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _to_int(value: Any) -> int | None:
    numeric = _to_float(value)
    if numeric is None or not float(numeric).is_integer():
        return None
    return int(numeric)


def _to_bool(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "oui", "validated", "accepted"}:
        return True
    if normalized in {
        "0",
        "false",
        "no",
        "non",
        "rejected",
        "invalid",
        "not_validated",
    }:
        return False
    return None


def _deep_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for name in path:
        if not isinstance(current, dict) or name not in current:
            return None
        current = current[name]
    return current


def _first_value(
    payload: dict[str, Any], paths: Iterable[tuple[str, ...]]
) -> Any:
    for path in paths:
        value = _deep_get(payload, path)
        if value not in (None, ""):
            return value
    return None


def _first_bool(
    payload: dict[str, Any], paths: Iterable[tuple[str, ...]]
) -> bool | None:
    value = _first_value(payload, paths)
    return _to_bool(value)


def _first_int(
    payload: dict[str, Any], paths: Iterable[tuple[str, ...]]
) -> int | None:
    return _to_int(_first_value(payload, paths))


def _metric_card(label: str, value: str, note: str, color: str) -> str:
    return "".join(
        [
            '<div class="scanMetricCard" style="border-top-color:',
            html.escape(color, quote=True),
            '">',
            f'<div class="scanMetricLabel">{html.escape(label)}</div>',
            f'<div class="scanMetricValue">{html.escape(value)}</div>',
            f'<div class="scanMetricNote">{html.escape(note)}</div>',
            "</div>",
        ]
    )


def _png_dimensions(path: Path) -> tuple[int | None, int | None]:
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


def _pole_row_verdict(
    row: dict[str, str],
    *,
    local_model_validated: bool,
    manifest_poles_validated: bool | None,
) -> str:
    """Return a conservative public verdict for one estimated pole."""

    status_fields = (
        "status",
        "validation_status",
        "evidence_status",
        "claim_status",
        "classification",
        "model_status",
    )
    status_text = " ".join(str(row.get(name) or "") for name in status_fields)
    normalized = status_text.strip().lower()
    if (
        _to_bool(row.get("publishable_as_controller_pole")) is True
        or "exact_controller" in normalized
    ):
        return "Exact pour le régulateur; pas un pôle physique"
    explicit_flags = [
        _to_bool(row.get(name))
        for name in ("validated", "accepted", "pole_validated", "is_valid")
        if row.get(name) not in (None, "")
    ]
    if (
        manifest_poles_validated is False
        or any(flag is False for flag in explicit_flags)
        or any(marker in normalized for marker in _NEGATIVE_STATUS_MARKERS)
    ):
        return "Rejeté / non validé"
    explicitly_positive = any(flag is True for flag in explicit_flags) or any(
        marker in normalized for marker in _POSITIVE_STATUS_MARKERS
    )
    if local_model_validated and explicitly_positive:
        return "Validé pour le modèle local documenté"
    return "Exploratoire / validation absente"


def _is_pole_csv(path: Path) -> bool:
    stem = path.stem.lower()
    return "pole" in stem or "eigen" in stem or "valeur_propre" in stem


def _pole_rows_with_verdicts(
    paths: list[Path],
    *,
    local_model_validated: bool,
    manifest_poles_validated: bool | None,
) -> list[tuple[dict[str, str], str]]:
    results: list[tuple[dict[str, str], str]] = []
    for path in paths:
        if not _is_pole_csv(path):
            continue
        for row in read_csv_rows(path):
            results.append(
                (
                    row,
                    _pole_row_verdict(
                        row,
                        local_model_validated=local_model_validated,
                        manifest_poles_validated=manifest_poles_validated,
                    ),
                )
            )
    return results


def _row_value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _pole_table(rows: list[tuple[dict[str, str], str]]) -> str:
    body: list[list[str]] = []
    for index, (row, verdict) in enumerate(rows[:60], start=1):
        body.append(
            [
                _row_value(row, "pole_id", "mode", "index", "name")
                or str(index),
                _row_value(row, "real", "real_part", "pole_real"),
                _row_value(row, "imag", "imaginary", "imag_part", "pole_imag"),
                _row_value(row, "magnitude", "modulus", "abs", "pole_magnitude"),
                _row_value(row, "damping_ratio", "damping", "zeta"),
                _row_value(
                    row,
                    "natural_frequency_cpd",
                    "frequency_cpd",
                    "frequency_hz",
                    "period_days",
                ),
                verdict,
            ]
        )
    return render_data_table(
        [
            "Mode",
            "Partie réelle",
            "Partie imaginaire",
            "Module",
            "Amortissement",
            "Fréquence / période",
            "Statut scientifique",
        ],
        body,
    )


def _friendly_artifact_title(path: Path) -> str:
    suffix = path.stem.removeprefix("canonical_control_system_")
    known = {
        "poles": "Pôles du modèle local",
        "pole_map": "Carte des pôles : régulateur exact et candidat rejeté",
        "eigenvalues": "Valeurs propres du modèle local",
        "controllability": "Contrôlabilité du modèle local",
        "observability": "Observabilité du modèle local",
        "gramians": "Grammiens de contrôlabilité et d’observabilité",
        "hankel_singular_values": "Valeurs singulières de Hankel",
        "step_response": "Réponse indicielle du modèle local",
        "impulse_response": "Réponse impulsionnelle : régulateur exact et candidat rejeté",
        "bode": "Bode du régulateur exact et candidat rejeté",
        "nyquist": "Diagramme de Nyquist du modèle local",
        "root_locus": "Lieu des racines du modèle local",
        "stability_margins": "Marges de stabilité du modèle local",
        "state_space": "Représentation d’état locale",
        "actuator_space_rank": "Degrés de liberté des commandes V3",
        "input_rank": "Indépendance des essais et rang des réponses",
        "controllability_observability": "Contrôlabilité et observabilité",
        "free_run_validation": "Prévision autonome du modèle candidat",
        "operating_point": "Évolution du point de fonctionnement",
        "nyquist_deadzone": "Nyquist du régulateur et zones mortes",
        "probe_composition": "Décision V3, variation d’essai et commande appliquée",
        "physical_state_response": "Réponse des états physiques article par article",
        "states_inputs": "États, entrées et sorties étudiés",
        "zeros": "Zéros du modèle candidat",
        "validation": "Vérification du modèle candidat",
        "dead_zones": "Zones mortes observées",
    }
    return known.get(suffix, suffix.replace("_", " ").strip().capitalize())


def _figure_interpretation(path: Path, local_model_validated: bool) -> str:
    stem = path.stem.lower()
    scope = (
        "Le résultat porte uniquement sur le modèle local documenté et son point "
        "de fonctionnement."
        if local_model_validated
        else "Le modèle local n’est pas validé : cette figure reste exploratoire."
    )
    if "pole" in stem or "eigen" in stem or "root_locus" in stem:
        return (
            "Le point vert est le pôle exact de la mémoire interne du régulateur, "
            "pas un pôle physique de la supply chain. Toute croix rouge est un "
            "candidat rejeté et reste explicitement non validée."
        )
    if "controll" in stem:
        return (
            "Le rang et le conditionnement mesurent la capacité théorique à agir "
            "sur les états du modèle local. "
            + scope
        )
    if "observ" in stem:
        return (
            "Le rang et le conditionnement mesurent la capacité théorique à "
            "reconstruire les états du modèle local depuis les sorties. "
            + scope
        )
    if "probe_composition" in stem:
        return (
            "Les courbes séparent la décision automatique V3, la petite variation "
            "ajoutée pour l’essai et la commande réellement appliquée."
        )
    if "physical_state_response" in stem:
        return (
            "Différences mesurées par rapport à la même boucle V3 sans variation "
            "d’essai. Une barre rouge indique un effet exactement nul."
        )
    if "input_rank" in stem:
        return (
            "Les trois variations d’essai sont indépendantes, mais une seule "
            "direction de réponse physique domine au seuil de 1 %."
        )
    if "actuator_space_rank" in stem:
        return (
            "Dans la branche étudiée, les commandes continues V3 de quantité et de "
            "production évoluent presque sur une seule direction."
        )
    if any(name in stem for name in ("bode", "nyquist", "impulse_response")):
        return (
            "Les courbes exactes concernent la mémoire interne du régulateur. "
            "Le procédé candidat reste rejeté et aucune marge de boucle physique "
            "n’est revendiquée."
        )
    return scope


def _figure_html(path: Path, *, local_model_validated: bool) -> str:
    image = load_png_payload(path)
    if not image:
        return ""
    data = str(image.get("data_b64") or "")
    if not data:
        return ""
    title = _friendly_artifact_title(path)
    width, height = _png_dimensions(path)
    dimensions = (
        f' width="{width}" height="{height}"'
        if width is not None and height is not None
        else ""
    )
    return "".join(
        [
            '<article class="scanFigureCard">',
            f"<h3>{html.escape(title)}</h3>",
            f"<p>{html.escape(_figure_interpretation(path, local_model_validated))}</p>",
            f'<img loading="eager" decoding="async"{dimensions} '
            f'src="data:image/png;base64,{data}" '
            f'alt="{html.escape(title, quote=True)}">',
            "</article>",
        ]
    )


def _generic_csv_table(path: Path, rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0])[:12]
    body = [[row.get(name, "") for name in headers] for row in rows[:60]]
    title = _friendly_artifact_title(path)
    return "".join(
        [
            '<section class="scanDashboardSection">',
            f"<h3>{html.escape(title)}</h3>",
            '<p class="scanSectionNote">Valeurs du modèle local fourni; elles ne '
            "décrivent pas automatiquement le système non linéaire complet.</p>",
            render_data_table(headers, body),
            "</section>",
        ]
    )


def _manifest_limitations(manifest: dict[str, Any]) -> list[str]:
    candidates = [
        manifest.get("limitations"),
        manifest.get("scientific_limitations"),
        _deep_get(manifest, ("scope", "limitations")),
        _deep_get(manifest, ("validation", "limitations")),
    ]
    limitations: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, list):
            limitations.extend(
                str(item).strip() for item in candidate if str(item).strip()
            )
        elif isinstance(candidate, str) and candidate.strip():
            limitations.append(candidate.strip())
    defaults = [
        "Les résultats portent sur un modèle local autour du point de fonctionnement étudié, pas sur toute la dynamique hybride de la supply chain.",
        "Un rang complet peut être numériquement fragile; son conditionnement et les variables retenues doivent être examinés.",
        "Les pôles rejetés, exploratoires ou dépourvus de preuve explicite ne sont pas des pôles validés du système physique.",
    ]
    for item in defaults:
        if item not in limitations:
            limitations.append(item)
    return limitations


def _safe_report_excerpt(
    report_text: str, *, suppress_positive_pole_claims: bool
) -> str:
    """Render an escaped excerpt and suppress contradicted pole claims."""

    lines: list[str] = []
    for line in report_text.strip().splitlines():
        normalized_line = line.lower()
        discusses_poles = any(
            token in normalized_line
            for token in ("pôle", "pole", "eigen", "valeur propre")
        )
        positive_validation_claim = any(
            token in normalized_line
            for token in ("validé", "valide", "validated", "accepted")
        )
        carries_negative_scope = any(
            token in normalized_line
            for token in _NEGATIVE_STATUS_MARKERS
        ) or any(
            token in normalized_line
            for token in ("non valid", "pas valid", "ne sont pas valid")
        )
        if (
            suppress_positive_pole_claims
            and discusses_poles
            and positive_validation_claim
            and not carries_negative_scope
        ):
            lines.append(
                "[Assertion positive sur les pôles masquée : elle contredit "
                "leur statut conservateur dans la carte.]"
            )
        else:
            lines.append(line)
    normalized = "\n".join(lines).strip()
    if len(normalized) > 40000:
        normalized = normalized[:40000].rstrip() + "\n\n[Rapport tronqué dans la carte.]"
    return (
        '<pre class="jsonPanelPre scanControlSystemReport" '
        'style="white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;'
        'max-width:100%;box-sizing:border-box;overflow-x:auto">'
        f"{html.escape(normalized)}</pre>"
    )


def _display_status(raw_status: str, local_model_validated: bool) -> str:
    normalized = raw_status.strip().lower()
    if any(marker in normalized for marker in _NEGATIVE_STATUS_MARKERS):
        return "exploratoire / non validé"
    if "valid" in normalized and not local_model_validated:
        return "analyse disponible — modèle local non validé"
    labels = {
        "complete": "analyse terminée",
        "completed": "analyse terminée",
        "ready": "analyse disponible",
        "exploratory_complete": "analyse exploratoire terminée",
    }
    return labels.get(normalized, raw_status.replace("_", " ") or "non documenté")


def build_control_system_dashboard_section(
    result_root: Path | None,
) -> dict[str, Any]:
    """Return a self-contained optional control-system analysis section."""

    unavailable = {
        "schema_version": CONTROL_SYSTEM_DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": "control_system_results_not_provided",
        "html": "",
        "figure_count": 0,
    }
    if result_root is None:
        return unavailable
    manifest = load_json_dict(result_root / _MANIFEST_NAME)
    report_path = result_root / _REPORT_NAME
    try:
        report_text = report_path.read_text(encoding="utf-8").strip()
    except OSError:
        report_text = ""
    if not result_root.is_dir() or not manifest or not report_text:
        return unavailable

    local_model_validated = (
        _first_bool(
            manifest,
            (
                ("claims", "local_linear_model_validated"),
                ("claims", "state_space_model_validated"),
                ("validation", "local_model_validated"),
                ("local_linear_model", "validated"),
                ("model", "validated"),
                ("local_model_validated",),
            ),
        )
        is True
    )
    manifest_poles_validated = _first_bool(
        manifest,
        (
            ("claims", "poles_validated"),
            ("validation", "poles_validated"),
            ("poles", "validated"),
            ("poles_validated",),
        ),
    )
    state_dimension = _first_int(
        manifest,
        (
            ("dimensions", "states"),
            ("dimensions", "n_states"),
            ("state_space", "n_states"),
            ("model", "n_states"),
            ("metrics", "state_dimension"),
        ),
    )
    input_dimension = _first_int(
        manifest,
        (
            ("dimensions", "inputs"),
            ("dimensions", "n_inputs"),
            ("state_space", "n_inputs"),
            ("model", "n_inputs"),
            ("metrics", "input_dimension"),
        ),
    )
    output_dimension = _first_int(
        manifest,
        (
            ("dimensions", "outputs"),
            ("dimensions", "n_outputs"),
            ("state_space", "n_outputs"),
            ("model", "n_outputs"),
            ("metrics", "output_dimension"),
        ),
    )
    controllability_rank = _first_int(
        manifest,
        (
            ("controllability", "rank"),
            ("metrics", "controllability_rank"),
            ("state_space", "controllability_rank"),
        ),
    )
    observability_rank = _first_int(
        manifest,
        (
            ("observability", "rank"),
            ("metrics", "observability_rank"),
            ("state_space", "observability_rank"),
        ),
    )
    controllability_condition = _to_float(
        _first_value(
            manifest,
            (
                ("controllability", "condition_number"),
                ("metrics", "controllability_condition_number"),
            ),
        )
    )
    observability_condition = _to_float(
        _first_value(
            manifest,
            (
                ("observability", "condition_number"),
                ("metrics", "observability_condition_number"),
            ),
        )
    )
    experimental_input_rank = _first_int(
        manifest,
        (("experimental_actuator_excitation", "rank"),),
    )
    measured_response_rank_1pct = _first_int(
        manifest,
        (
            (
                "experimental_actuator_excitation",
                "measured_response_direction_effective_rank_1pct",
            ),
        ),
    )
    csv_paths = sorted(result_root.rglob("canonical_control_system_*.csv"))
    png_paths = sorted(result_root.rglob("canonical_control_system_*.png"))
    pole_rows = _pole_rows_with_verdicts(
        csv_paths,
        local_model_validated=local_model_validated,
        manifest_poles_validated=manifest_poles_validated,
    )
    validated_pole_count = sum(
        verdict.startswith("Validé") for _, verdict in pole_rows
    )
    rejected_pole_count = sum(
        verdict.startswith("Rejeté") for _, verdict in pole_rows
    )
    exact_controller_pole_count = sum(
        verdict.startswith("Exact pour le régulateur") for _, verdict in pole_rows
    )
    exploratory_pole_count = (
        len(pole_rows)
        - validated_pole_count
        - rejected_pole_count
        - exact_controller_pole_count
    )
    pole_claim_conflict = bool(
        manifest_poles_validated is True
        and any(
            not verdict.startswith(("Validé", "Exact pour le régulateur"))
            for _, verdict in pole_rows
        )
    )
    local_stability_source = _first_bool(
        manifest,
        (
            ("claims", "local_stability_demonstrated"),
            ("claims", "local_stability_validated"),
            ("stability", "locally_stable"),
            ("metrics", "locally_stable"),
        ),
    )
    local_stability_demonstrated = bool(
        local_model_validated
        and local_stability_source is True
        and not pole_claim_conflict
    )
    controllability_full_rank = bool(
        state_dimension is not None
        and controllability_rank is not None
        and controllability_rank == state_dimension
    )
    observability_full_rank = bool(
        state_dimension is not None
        and observability_rank is not None
        and observability_rank == state_dimension
    )
    raw_status = str(manifest.get("status") or "non_documented")
    display_status = _display_status(raw_status, local_model_validated)
    claim_scope = str(
        _first_value(
            manifest,
            (
                ("claim_scope",),
                ("claims", "scope"),
                ("validation", "claim_scope"),
                ("model", "scope"),
            ),
        )
        or "modèle local au point de fonctionnement documenté"
    )
    operating_point = str(
        _first_value(
            manifest,
            (
                ("operating_point", "label"),
                ("operating_condition",),
                ("operating_point",),
            ),
        )
        or "non documenté"
    )
    if operating_point.startswith("{"):
        operating_point = "documenté dans le manifeste"

    dimension_value = " / ".join(
        str(value) if value is not None else "?"
        for value in (state_dimension, input_dimension, output_dimension)
    )
    controllability_value = (
        f"{controllability_rank} / {state_dimension}"
        if controllability_rank is not None and state_dimension is not None
        else "non calculée"
    )
    observability_value = (
        f"{observability_rank} / {state_dimension}"
        if observability_rank is not None and state_dimension is not None
        else "non calculée"
    )
    cards = [
        _metric_card(
            "Statut scientifique",
            display_status,
            "la carte applique une lecture conservatrice des preuves",
            "#be123c" if not local_model_validated else "#0f766e",
        ),
        _metric_card(
            "Dimensions état / entrée / sortie",
            dimension_value,
            "dimensions du modèle local fourni",
            "#2563eb",
        ),
        _metric_card(
            "Contrôlabilité",
            controllability_value,
            (
                "rang complet sur le modèle local validé"
                if controllability_full_rank and local_model_validated
                else "rang calculé; portée exploratoire"
                if controllability_rank is not None
                else "preuve absente"
            ),
            "#0f766e" if controllability_full_rank and local_model_validated else "#d97706",
        ),
        _metric_card(
            "Observabilité",
            observability_value,
            (
                "rang complet sur le modèle local validé"
                if observability_full_rank and local_model_validated
                else "rang calculé; portée exploratoire"
                if observability_rank is not None
                else "preuve absente"
            ),
            "#0f766e" if observability_full_rank and local_model_validated else "#d97706",
        ),
        _metric_card(
            "Pôles acceptés",
            f"{validated_pole_count} / {len(pole_rows)}",
            (
                f"{exact_controller_pole_count} exact(s) pour le régulateur, "
                f"{rejected_pole_count} rejeté(s), "
                f"{exploratory_pole_count} exploratoire(s)"
            ),
            "#0f766e" if validated_pole_count and not pole_claim_conflict else "#be123c",
        ),
        _metric_card(
            "Stabilité locale",
            "démontrée sur le modèle local"
            if local_stability_demonstrated
            else "non démontrée",
            "aucune conclusion de stabilité globale",
            "#0f766e" if local_stability_demonstrated else "#be123c",
        ),
    ]
    if experimental_input_rank is not None:
        cards.append(
            _metric_card(
                "Variations d'essai indépendantes",
                f"{experimental_input_rank} / 3",
                "qualité des entrées; ne prouve pas la contrôlabilité physique",
                "#0f766e" if experimental_input_rank == 3 else "#d97706",
            )
        )
    if measured_response_rank_1pct is not None:
        cards.append(
            _metric_card(
                "Directions physiques significatives",
                f"{measured_response_rank_1pct} / 3",
                "rang descriptif des réponses au seuil de 1 %",
                "#be123c" if measured_response_rank_1pct < 3 else "#0f766e",
            )
        )
    figure_cards = [
        card
        for path in png_paths
        if (card := _figure_html(path, local_model_validated=local_model_validated))
    ]
    figures_html = "".join(figure_cards) or (
        '<div class="panelEmptyState">Aucune figure d’analyse système fournie.</div>'
    )
    other_tables = "".join(
        table
        for path in csv_paths
        if not _is_pole_csv(path)
        if (table := _generic_csv_table(path, read_csv_rows(path)))
    )
    limitations = _manifest_limitations(manifest)
    limitations_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in limitations
    )
    pole_warning = (
        "Le manifeste revendique des pôles validés, mais au moins une ligne "
        "est rejetée ou non vérifiée. La carte refuse donc cette généralisation."
        if pole_claim_conflict
        else "Les pôles rejetés ou exploratoires restent affichés comme non validés."
    )
    pole_section = ""
    if pole_rows:
        pole_section = "".join(
            [
                '<section class="scanDashboardSection">',
                "<h3>Pôles estimés et statut scientifique</h3>",
                f'<p class="scanSectionNote">{html.escape(pole_warning)}</p>',
                _pole_table(pole_rows),
                "</section>",
            ]
        )
    html_payload = "".join(
        [
            '<div class="scanEvidenceBanner">Analyse de régulation au sens des '
            "systèmes dynamiques : modèle d’état local, contrôlabilité, "
            "observabilité, modes et stabilité. Portée : ",
            html.escape(claim_scope),
            ". Aucun résultat local n’est étendu au système hybride complet sans preuve.</div>",
            f'<div class="scanMetricGrid">{"".join(cards)}</div>',
            '<section class="scanDashboardSection">',
            "<h3>Point de fonctionnement et portée</h3>",
            '<div class="dataKvGrid">',
            '<div class="dataKvLabel">Point de fonctionnement</div>',
            f'<div class="dataKvValue">{html.escape(operating_point)}</div>',
            '<div class="dataKvLabel">Portée des conclusions</div>',
            f'<div class="dataKvValue">{html.escape(claim_scope)}</div>',
            '<div class="dataKvLabel">Conditionnement contrôlabilité</div>',
            f'<div class="dataKvValue">{html.escape(str(controllability_condition) if controllability_condition is not None else "non documenté")}</div>',
            '<div class="dataKvLabel">Conditionnement observabilité</div>',
            f'<div class="dataKvValue">{html.escape(str(observability_condition) if observability_condition is not None else "non documenté")}</div>',
            "</div></section>",
            pole_section,
            other_tables,
            '<section class="scanDashboardSection"><h3>Graphiques d’analyse système</h3>',
            f'<div class="scanFigureGrid">{figures_html}</div>',
            "</section>",
            '<section class="scanDashboardSection scanLimitations"><h3>Limites de lecture</h3>',
            f"<ul>{limitations_html}</ul>",
            "</section>",
            '<section class="scanDashboardSection"><h3>Rapport scientifique fourni</h3>',
            '<p class="scanSectionNote">Le statut conservateur affiché ci-dessus '
            "prévaut pour l’interprétation des pôles et de la stabilité.</p>",
            _safe_report_excerpt(
                report_text,
                suppress_positive_pole_claims=(
                    not local_model_validated
                    or pole_claim_conflict
                    or rejected_pole_count > 0
                    or exploratory_pole_count > 0
                ),
            ),
            "</section>",
        ]
    )
    return {
        "schema_version": CONTROL_SYSTEM_DASHBOARD_SCHEMA_VERSION,
        "available": True,
        "status": "ready",
        "metrics": {
            "source_status": raw_status,
            "display_status": display_status,
            "claim_scope": claim_scope,
            "operating_point": operating_point,
            "local_model_validated": local_model_validated,
            "state_dimension": state_dimension,
            "input_dimension": input_dimension,
            "output_dimension": output_dimension,
            "controllability_rank": controllability_rank,
            "controllability_full_rank": controllability_full_rank,
            "controllability_condition_number": controllability_condition,
            "observability_rank": observability_rank,
            "observability_full_rank": observability_full_rank,
            "observability_condition_number": observability_condition,
            "experimental_input_rank": experimental_input_rank,
            "measured_response_direction_effective_rank_1pct": (
                measured_response_rank_1pct
            ),
            "pole_count": len(pole_rows),
            "validated_pole_count": validated_pole_count,
            "rejected_pole_count": rejected_pole_count,
            "exact_controller_pole_count": exact_controller_pole_count,
            "exploratory_pole_count": exploratory_pole_count,
            "pole_claim_conflict": pole_claim_conflict,
            "local_stability_demonstrated": local_stability_demonstrated,
            "csv_count": len(csv_paths),
            "report_available": True,
        },
        "figure_count": len(figure_cards),
        "html": html_payload,
    }


__all__ = [
    "CONTROL_SYSTEM_DASHBOARD_SCHEMA_VERSION",
    "build_control_system_dashboard_section",
]
