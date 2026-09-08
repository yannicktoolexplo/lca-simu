"""Build the optional RESILIENCE-SCAN dashboard embedded in the world map."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

from etudecas.visualization.maps.chart_payloads import load_png_payload
from etudecas.visualization.maps.control_system_dashboard_payload import (
    build_control_system_dashboard_section,
)
from etudecas.visualization.maps.frequency_dashboard_payload import (
    build_frequency_dashboard_section,
)
from etudecas.visualization.maps.map_data_loader import load_json_dict, read_csv_rows
from etudecas.visualization.maps.map_render import fmt_qty, render_data_table


SCAN_DASHBOARD_SCHEMA_VERSION = "etudecas.scan_dashboard.v1"


def _to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _to_int(value: Any) -> int:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else 0


def _mean_finite(rows: list[dict[str, str]], field: str) -> float | None:
    values = [
        value
        for row in rows
        if (value := _to_float(row.get(field))) is not None
    ]
    return sum(values) / len(values) if values else None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui"}


def _display_rci_status(value: Any) -> str:
    status = str(value or "unknown")
    return {
        "pending_business_review": "En attente",
        "validated": "Valide",
        "complete": "Termine",
        "unknown": "Inconnu",
    }.get(status, status.replace("_", " "))


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
    return "".join(
        [
            '<article class="scanFigureCard">',
            f"<h3>{html.escape(title)}</h3>",
            f"<p>{html.escape(interpretation)}</p>",
            f'<img loading="lazy" src="data:{mime};base64,{data}" alt="{html.escape(title, quote=True)}">',
            "</article>",
        ]
    )


def _first_existing_path(result_root: Path, names: tuple[str, ...]) -> Path:
    """Return the first existing artifact candidate without exposing its path."""

    for name in names:
        candidate = result_root / name
        if candidate.is_file():
            return candidate
    return result_root / names[0]


def _figure_html_from_candidates(
    result_root: Path,
    relative_paths: tuple[str, ...],
    title: str,
    interpretation: str,
) -> str:
    artifact = _first_existing_path(result_root, relative_paths)
    try:
        relative_path = str(artifact.relative_to(result_root))
    except ValueError:
        return ""
    return _figure_html(result_root, relative_path, title, interpretation)


def _mapping_child(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    return value if isinstance(value, dict) else {}


def _seed_list(payload: dict[str, Any], *names: str) -> list[int]:
    for name in names:
        value = payload.get(name)
        if not isinstance(value, list):
            continue
        parsed: list[int] = []
        for item in value:
            numeric = _to_float(item)
            if numeric is not None and float(numeric).is_integer():
                parsed.append(int(numeric))
        return parsed
    return []


def _policy_table(rows: list[dict[str, str]]) -> str:
    def sort_key(row: dict[str, str]) -> tuple[float, str]:
        score = _to_float(row.get("mean_delta_score"))
        return (score if score is not None else float("inf"), str(row.get("policy") or ""))

    body = []
    for row in sorted(rows, key=sort_key):
        body.append(
            [
                row.get("policy") or "n/a",
                fmt_qty(row.get("mean_delta_service_loss"), 3),
                fmt_qty(row.get("mean_delta_backlog_area"), 2),
                fmt_qty(row.get("mean_delta_nervousness"), 3),
                fmt_qty(row.get("mean_delta_risk_creation"), 3),
                fmt_qty(100.0 * (_to_float(row.get("win_rate_vs_mrp_service_loss")) or 0.0), 1) + "%",
            ]
        )
    return render_data_table(
        [
            "Politique",
            "Delta perte service",
            "Delta aire backlog",
            "Delta nervosite",
            "Delta risque cree",
            "Victoires service vs MRP",
        ],
        body,
    )


def _canonical_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows:
        body.append(
            [
                row.get("policy") or "n/a",
                row.get("run_kind") or "n/a",
                row.get("status") or "n/a",
                fmt_qty(row.get("mean_service"), 4),
                fmt_qty(row.get("service_loss"), 3),
                fmt_qty(row.get("backlog_area_days"), 3),
                fmt_qty(row.get("canonical_risk_creation_proxy"), 3),
                row.get("recovery_status") or "n/a",
            ]
        )
    return render_data_table(
        [
            "Politique",
            "Type",
            "Statut",
            "Service moyen",
            "Perte service",
            "Aire backlog",
            "Proxy risque cree",
            "Recuperation",
        ],
        body,
    )


def _confusion_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in sorted(rows, key=lambda item: str(item.get("case") or "")):
        body.append(
            [
                row.get("case") or "n/a",
                row.get("runs") or "0",
                fmt_qty(row.get("mean_service_loss"), 3),
                fmt_qty(row.get("mean_backlog_area"), 2),
                fmt_qty(row.get("mean_total_cost_proxy"), 2),
                fmt_qty(row.get("response_intensity"), 3),
            ]
        )
    return render_data_table(
        ["Cas", "Runs", "Perte service", "Aire backlog", "Cout total proxy", "Intensite action"],
        body,
    )


def _regime_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows:
        body.append(
            [
                row.get("regime") or "n/a",
                row.get("anchor_count") or "0",
                row.get("confidence") or "n/a",
                row.get("separation") or row.get("median_separation") or "n/a",
                row.get("label_provenance") or "n/a",
            ]
        )
    return render_data_table(
        ["Regime", "Ancrages", "Confiance", "Separation", "Provenance labels"],
        body,
    )


def _closed_loop_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in sorted(rows, key=lambda item: _to_int(item.get("seed"))):
        body.append(
            [
                row.get("seed") or "n/a",
                "oui" if _truthy(row.get("true_state_feedback")) else "non",
                fmt_qty(row.get("delta_vs_mrp_service"), 4),
                fmt_qty(row.get("delta_vs_mrp_backlog_area_days"), 4),
                fmt_qty(row.get("delta_vs_mrp_mean_inventory_days"), 2),
                fmt_qty(row.get("delta_vs_mrp_order_nervousness"), 2),
                fmt_qty(row.get("delta_vs_mrp_supplier_risk_area"), 4),
                fmt_qty(row.get("delta_vs_mrp_total_economic_exposure"), 2),
            ]
        )
    return render_data_table(
        [
            "Graine",
            "Feedback prouve",
            "Delta service",
            "Delta aire backlog",
            "Delta stock (jours)",
            "Delta nervosite ordres",
            "Delta aire risque fournisseur",
            "Delta exposition economique",
        ],
        body,
    )


def _closed_loop_section_html(
    *,
    cards: list[str],
    paired_table: str,
    figure_cards: list[str],
    causal_contract_confirmed: bool,
) -> str:
    figures_html = "".join(figure_cards) or (
        '<div class="panelEmptyState">Aucune courbe de boucle fermee disponible.</div>'
    )
    evidence_banner = (
        "Boucle causale executee dans le moteur canonique : observation en fin "
        "de J, decision auditee, action au plus tot a J+1 et look-ahead nul."
        if causal_contract_confirmed
        else "Resultats de feedback disponibles, mais le contrat causal strict "
        "(claim moteur, J+1 et look-ahead nul) n'est pas confirme."
    )
    return "".join(
        [
            f'<div class="scanEvidenceBanner">{evidence_banner} Une amelioration '
            "dans le simulateur ne constitue pas une preuve causale industrielle.</div>",
            f'<div class="scanMetricGrid">{"".join(cards)}</div>',
            '<section class="scanDashboardSection"><h3>Feedback versus MRP, appariement par graine</h3>',
            '<p class="scanSectionNote">Les signes sont feedback moins MRP. Une valeur nulle '
            'est un resultat, pas une amelioration implicite.</p>',
            paired_table,
            "</section>",
            '<section class="scanDashboardSection"><h3>Trajectoires et commande</h3>',
            f'<div class="scanFigureGrid">{figures_html}</div>',
            "</section>",
            '<section class="scanDashboardSection scanLimitations"><h3>Lecture scientifique</h3>',
            '<ul><li>Le signal de perturbation est un proxy borne de severite physique, '
            'pas une probabilite d incident.</li><li>La politique est une machine a etats '
            'avec confirmation temporelle, dwell et slew limits; elle n est pas encore optimisee.</li>'
            '<li>La campagne teste le modele simule et ne valide ni transfert industriel '
            'ni stabilite frequentielle.</li></ul></section>',
        ]
    )


def _closed_loop_v2_section_html(
    *,
    cards: list[str],
    paired_table: str,
    figure_cards: list[str],
    causal_contract_confirmed: bool,
    protocol_rows: list[list[str]],
) -> str:
    figures_html = "".join(figure_cards) or (
        '<div class="panelEmptyState">Aucune courbe Closed-Loop V2 disponible.</div>'
    )
    evidence_banner = (
        "Closed-Loop V2 confirme par le moteur : etat observe en fin de J, "
        "decision auditee, action au plus tot a J+1 et look-ahead nul."
        if causal_contract_confirmed
        else "Artefacts Closed-Loop V2 disponibles, mais le contrat causal "
        "strict n'est pas confirme par les preuves moteur fournies."
    )
    protocol_html = (
        render_data_table(["Element du protocole V2", "Valeur"], protocol_rows)
        if protocol_rows
        else '<div class="panelEmptyState">Protocole V2 detaille non fourni.</div>'
    )
    return "".join(
        [
            f'<div class="scanEvidenceBanner">{evidence_banner} Le V2 est '
            "une experience additive distincte du cold-start V1 historique.</div>",
            f'<div class="scanMetricGrid">{"".join(cards)}</div>',
            '<section class="scanDashboardSection"><h3>V2 versus MRP, appariement par graine</h3>',
            '<p class="scanSectionNote">Les signes sont V2 moins MRP. Le protocole '
            'd apprentissage et le hold-out ne sont interpretes que lorsqu ils sont documentes.</p>',
            paired_table,
            "</section>",
            '<section class="scanDashboardSection"><h3>Protocole Closed-Loop V2</h3>',
            protocol_html,
            "</section>",
            '<section class="scanDashboardSection"><h3>Trajectoires, etats et commandes V2</h3>',
            f'<div class="scanFigureGrid">{figures_html}</div>',
            "</section>",
            '<section class="scanDashboardSection scanLimitations"><h3>Lecture scientifique</h3>',
            '<ul><li>Le V2 ne remplace ni la campagne V1 ni ses artefacts cold-start.</li>'
            '<li>Un warm-up ou un gate declare doit etre confirme par les preuves du paquet; '
            'sa seule presence dans un fichier de configuration ne suffit pas.</li>'
            '<li>Les resultats restent des preuves de simulation et ne constituent pas une '
            'validation industrielle ou une preuve de stabilite frequentielle.</li></ul></section>',
        ]
    )


def _dashboard_html(
    *,
    cards: list[str],
    evidence_text: str,
    limitations: list[str],
    regime_table: str,
    policy_table: str,
    canonical_table: str,
    confusion_table: str,
    figure_cards: list[str],
    closed_loop_html: str,
    closed_loop_v2_html: str,
    frequency_html: str,
    control_system_html: str,
) -> str:
    limitation_html = "".join(f"<li>{html.escape(item)}</li>" for item in limitations)
    figures_html = "".join(figure_cards) or (
        '<div class="panelEmptyState">Aucune courbe SCAN disponible dans ce paquet.</div>'
    )
    closed_loop_button = (
        '<button class="lotTraceDirectionBtn" type="button" '
        'data-scan-dashboard-tab="closed-loop">Boucle fermee</button>'
        if closed_loop_html
        else ""
    )
    closed_loop_pane = (
        '<div class="scanDashboardPane hidden" data-scan-dashboard-pane="closed-loop">'
        f"{closed_loop_html}</div>"
        if closed_loop_html
        else ""
    )
    closed_loop_v2_button = (
        '<button class="lotTraceDirectionBtn" type="button" '
        'data-scan-dashboard-tab="closed-loop-v2">Closed-Loop V2</button>'
        if closed_loop_v2_html
        else ""
    )
    closed_loop_v2_pane = (
        '<div class="scanDashboardPane hidden" data-scan-dashboard-pane="closed-loop-v2">'
        f"{closed_loop_v2_html}</div>"
        if closed_loop_v2_html
        else ""
    )
    frequency_button = (
        '<button class="lotTraceDirectionBtn" type="button" '
        'data-scan-dashboard-tab="frequency">Analyse fréquentielle</button>'
        if frequency_html
        else ""
    )
    frequency_pane = (
        '<div class="scanDashboardPane hidden" data-scan-dashboard-pane="frequency">'
        f"{frequency_html}</div>"
        if frequency_html
        else ""
    )
    control_system_button = (
        '<button class="lotTraceDirectionBtn" type="button" '
        'data-scan-dashboard-tab="control-system">Analyse système</button>'
        if control_system_html
        else ""
    )
    control_system_pane = (
        '<div class="scanDashboardPane hidden" data-scan-dashboard-pane="control-system">'
        f"{control_system_html}</div>"
        if control_system_html
        else ""
    )
    return "".join(
        [
            '<div class="scanDashboard">',
            '<div class="scanDashboardTabBar">',
            '<div class="lotTraceDirectionTabs" role="tablist" aria-label="Vues RESILIENCE-SCAN">',
            '<button class="lotTraceDirectionBtn active" type="button" data-scan-dashboard-tab="summary">Synthese</button>',
            '<button class="lotTraceDirectionBtn" type="button" data-scan-dashboard-tab="curves">Courbes</button>',
            '<button class="lotTraceDirectionBtn" type="button" data-scan-dashboard-tab="policies">Politiques et cas</button>',
            closed_loop_button,
            closed_loop_v2_button,
            frequency_button,
            control_system_button,
            "</div>",
            '<div class="scanDashboardTabHint">Resultats du paquet fourni a la generation de la map.</div>',
            "</div>",
            '<div class="scanDashboardPane" data-scan-dashboard-pane="summary">',
            f'<div class="scanEvidenceBanner">{html.escape(evidence_text)}</div>',
            f'<div class="scanMetricGrid">{"".join(cards)}</div>',
            '<section class="scanDashboardSection"><h3>Calibration des regimes</h3>',
            regime_table,
            "</section>",
            '<section class="scanDashboardSection scanLimitations"><h3>Limites de lecture</h3>',
            f"<ul>{limitation_html}</ul>",
            "</section>",
            "</div>",
            '<div class="scanDashboardPane hidden" data-scan-dashboard-pane="curves">',
            '<div class="scanFigureGrid">',
            figures_html,
            "</div></div>",
            '<div class="scanDashboardPane hidden" data-scan-dashboard-pane="policies">',
            '<section class="scanDashboardSection"><h3>Comparaison appariee - modele reduit</h3>',
            '<p class="scanSectionNote">Deltas par rapport au MRP sur scenarios communs. Ce tableau ne remplace pas le replay article/BOM canonique.</p>',
            policy_table,
            "</section>",
            '<section class="scanDashboardSection"><h3>Replay canonique</h3>',
            '<p class="scanSectionNote">Integration physique avec schedules journaliers pre-calcules; aucune revendication de boucle fermee.</p>',
            canonical_table,
            "</section>",
            '<section class="scanDashboardSection"><h3>TP / FP / FN / TN</h3>',
            confusion_table,
            "</section>",
            "</div></div>",
            closed_loop_pane,
            closed_loop_v2_pane,
            frequency_pane,
            control_system_pane,
        ]
    )


def build_scan_dashboard_payload(
    result_root: Path,
    closed_loop_root: Path | None = None,
    closed_loop_v2_root: Path | None = None,
    frequency_root: Path | None = None,
    control_system_root: Path | None = None,
) -> dict[str, Any]:
    """Return a self-contained dashboard payload for a SCAN validation package.

    Missing or incomplete packages are represented as unavailable instead of
    failing the map build. Large campaign outputs remain outside Git; only the
    selected summaries and figures are embedded in the generated HTML.
    """

    manifest_path = result_root / "run_manifest.json"
    manifest = load_json_dict(manifest_path)
    if not result_root.exists() or not manifest:
        return {
            "schema_version": SCAN_DASHBOARD_SCHEMA_VERSION,
            "available": False,
            "status": "scan_results_not_provided",
            "html": "",
            "figure_count": 0,
        }

    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    provenance = manifest.get("provenance") if isinstance(manifest.get("provenance"), dict) else {}
    prediction = (
        manifest.get("prediction_to_physics")
        if isinstance(manifest.get("prediction_to_physics"), dict)
        else {}
    )
    canonical = manifest.get("canonical_replay") if isinstance(manifest.get("canonical_replay"), dict) else {}
    rci = (
        manifest.get("rci_business_validation")
        if isinstance(manifest.get("rci_business_validation"), dict)
        else {}
    )

    paired_rows = read_csv_rows(result_root / "data" / "paired_policy_runs.csv")
    paired_summary_rows = read_csv_rows(result_root / "data" / "paired_policy_summary.csv")
    canonical_rows = read_csv_rows(result_root / "data" / "canonical_runs.csv")
    confusion_rows = read_csv_rows(result_root / "data" / "forecast_confusion_summary.csv")
    regime_rows = read_csv_rows(result_root / "data" / "regime_calibration_evidence.csv")
    closed_loop_path = closed_loop_root or Path(
        "__missing_closed_loop_results_package__"
    )
    closed_loop_manifest = load_json_dict(
        closed_loop_path / "canonical_closed_loop_manifest.json"
    )
    closed_loop_rows = read_csv_rows(
        closed_loop_path / "canonical_closed_loop_paired_deltas.csv"
    )
    closed_loop_provider: dict[str, Any] = {}
    closed_loop_seeds = closed_loop_manifest.get("seeds", [])
    if isinstance(closed_loop_seeds, list) and closed_loop_seeds:
        representative_summary = load_json_dict(
            closed_loop_path
            / "canonical_feedback"
            / f"seed_{closed_loop_seeds[0]}"
            / "summaries"
            / "first_simulation_summary.json"
        )
        representative_policy = representative_summary.get("policy")
        if isinstance(representative_policy, dict):
            provider_payload = representative_policy.get("control_provider")
            if isinstance(provider_payload, dict):
                closed_loop_provider = provider_payload

    closed_loop_figure_specs = [
        (
            "canonical_closed_loop_comparison.png",
            "MRP versus feedback canonique",
            "Trajectoires et comparaison appariee; les superpositions exactes sont conservees.",
        ),
        (
            "canonical_closed_loop_control_diagnostics.png",
            "Etats, regimes et commandes J+1",
            "Diagnostic du premier seed: signaux observes, politique choisie, leviers et deltas de trajectoire.",
        ),
    ]
    closed_loop_figure_cards = [
        card
        for relative_path, title, interpretation in closed_loop_figure_specs
        if (
            card := _figure_html(
                closed_loop_path,
                relative_path,
                title,
                interpretation,
            )
        )
    ]
    closed_loop_available = bool(closed_loop_manifest and closed_loop_rows)
    closed_loop_html = ""
    if closed_loop_available:
        paired_count = _to_int(closed_loop_manifest.get("paired_seed_count"))
        true_count = _to_int(
            closed_loop_manifest.get("true_state_feedback_count")
        )
        closed_loop_lookahead = closed_loop_provider.get(
            "controller_observation_forecast_lookahead_days"
        )
        closed_loop_causal_contract_confirmed = bool(
            paired_count > 0
            and true_count == paired_count
            and closed_loop_manifest.get("all_feedback_runs_confirmed_by_engine")
            is True
            and closed_loop_provider.get("closed_loop_claimed") is True
            and closed_loop_provider.get("observation_causal_contract_satisfied")
            is True
            and closed_loop_provider.get("future_realization_access") is False
            and isinstance(closed_loop_lookahead, int)
            and not isinstance(closed_loop_lookahead, bool)
            and closed_loop_lookahead == 0
        )
        mean_service_delta = _mean_finite(
            closed_loop_rows,
            "delta_vs_mrp_service",
        )
        mean_backlog_delta = _mean_finite(
            closed_loop_rows,
            "delta_vs_mrp_backlog_area_days",
        )
        mean_inventory_delta = _mean_finite(
            closed_loop_rows,
            "delta_vs_mrp_mean_inventory_days",
        )
        closed_loop_cards = [
            _metric_card(
                "Claims moteur",
                f"{true_count} / {paired_count}",
                "feedback reel avec action physique",
                "#0f766e",
            ),
            _metric_card(
                "Causalite commande",
                "J vers J+1",
                (
                    "aucun acces aux realisations futures"
                    if closed_loop_causal_contract_confirmed
                    else "contrat futur a verifier"
                ),
                "#2563eb",
            ),
            _metric_card(
                "Actions physiques",
                str(_to_int(closed_loop_provider.get("physically_applied_action_count"))),
                "premiere graine; ledger canonique",
                "#7c3aed",
            ),
            _metric_card(
                "Delta service moyen",
                fmt_qty(mean_service_delta, 4),
                (
                    f"delta backlog {fmt_qty(mean_backlog_delta, 4)}; "
                    f"delta stock {fmt_qty(mean_inventory_delta, 2)} jours"
                ),
                "#d97706",
            ),
        ]
        closed_loop_html = _closed_loop_section_html(
            cards=closed_loop_cards,
            paired_table=_closed_loop_table(closed_loop_rows),
            figure_cards=closed_loop_figure_cards,
            causal_contract_confirmed=closed_loop_causal_contract_confirmed,
        )
    else:
        closed_loop_causal_contract_confirmed = False

    closed_loop_v2_requested = closed_loop_v2_root is not None
    closed_loop_v2_manifest: dict[str, Any] = {}
    closed_loop_v2_protocol: dict[str, Any] = {}
    closed_loop_v2_rows: list[dict[str, str]] = []
    closed_loop_v2_provider: dict[str, Any] = {}
    closed_loop_v2_figure_cards: list[str] = []
    closed_loop_v2_available = False
    closed_loop_v2_causal_contract_confirmed = False
    closed_loop_v2_html = ""
    closed_loop_v2_paired_count = 0
    closed_loop_v2_true_count = 0
    if closed_loop_v2_requested:
        closed_loop_v2_path = Path(closed_loop_v2_root)
        closed_loop_v2_protocol = load_json_dict(
            closed_loop_v2_path / "canonical_closed_loop_v2_protocol.json"
        )
        if not closed_loop_v2_protocol:
            closed_loop_v2_protocol = load_json_dict(
                closed_loop_v2_path.parent
                / "canonical_closed_loop_v2_protocol.json"
            )
        closed_loop_v2_manifest = load_json_dict(
            _first_existing_path(
                closed_loop_v2_path,
                (
                    "canonical_closed_loop_v2_manifest.json",
                    "canonical_closed_loop_manifest.json",
                ),
            )
        )
        if not closed_loop_v2_manifest and closed_loop_v2_protocol:
            protocol_splits = closed_loop_v2_protocol.get("splits")
            protocol_splits = (
                protocol_splits
                if isinstance(protocol_splits, dict)
                else {}
            )
            for split_name in ("validation", "training"):
                split = protocol_splits.get(split_name)
                if not isinstance(split, dict):
                    continue
                split_output = str(split.get("output_dir") or "").strip()
                if not split_output:
                    continue
                candidate_path = Path(split_output)
                candidate_manifest = load_json_dict(
                    _first_existing_path(
                        candidate_path,
                        (
                            "canonical_closed_loop_v2_manifest.json",
                            "canonical_closed_loop_manifest.json",
                        ),
                    )
                )
                if candidate_manifest:
                    closed_loop_v2_path = candidate_path
                    closed_loop_v2_manifest = candidate_manifest
                    break
        closed_loop_v2_rows = read_csv_rows(
            _first_existing_path(
                closed_loop_v2_path,
                (
                    "canonical_closed_loop_v2_paired_deltas.csv",
                    "canonical_closed_loop_paired_deltas.csv",
                ),
            )
        )
        closed_loop_v2_seeds = closed_loop_v2_manifest.get("seeds", [])
        if isinstance(closed_loop_v2_seeds, list) and closed_loop_v2_seeds:
            seed_name = f"seed_{closed_loop_v2_seeds[0]}"
            summary_candidates = [
                closed_loop_v2_path
                / policy_dir
                / seed_name
                / "summaries"
                / "first_simulation_summary.json"
                for policy_dir in ("canonical_feedback_v2", "canonical_feedback")
            ]
            summary_candidates.extend(
                sorted(
                    closed_loop_v2_path.glob(
                        f"*feedback*/{seed_name}/summaries/first_simulation_summary.json"
                    )
                )
            )
            representative_summary: dict[str, Any] = {}
            for summary_candidate in summary_candidates:
                representative_summary = load_json_dict(summary_candidate)
                if representative_summary:
                    break
            representative_policy = representative_summary.get("policy")
            if isinstance(representative_policy, dict):
                provider_payload = representative_policy.get("control_provider")
                if isinstance(provider_payload, dict):
                    closed_loop_v2_provider = provider_payload

        closed_loop_v2_figure_specs = [
            (
                (
                    "canonical_closed_loop_v2_comparison.png",
                    "canonical_closed_loop_comparison.png",
                ),
                "MRP versus Closed-Loop V2",
                "Comparaison appariee du V2; le paquet V1 historique reste distinct.",
            ),
            (
                (
                    "canonical_closed_loop_v2_control_diagnostics.png",
                    "canonical_closed_loop_control_diagnostics.png",
                ),
                "Etats, gates et commandes V2",
                "Diagnostic causal du V2: observation J, decision et action effective J+1.",
            ),
        ]
        closed_loop_v2_figure_cards = [
            card
            for relative_paths, title, interpretation in closed_loop_v2_figure_specs
            if (
                card := _figure_html_from_candidates(
                    closed_loop_v2_path,
                    relative_paths,
                    title,
                    interpretation,
                )
            )
        ]
        closed_loop_v2_available = bool(
            closed_loop_v2_manifest and closed_loop_v2_rows
        )
        if closed_loop_v2_available:
            closed_loop_v2_paired_count = _to_int(
                closed_loop_v2_manifest.get(
                    "v2_paired_seed_count",
                    closed_loop_v2_manifest.get("paired_seed_count"),
                )
            )
            if closed_loop_v2_paired_count <= 0:
                closed_loop_v2_paired_count = len(
                    {
                        str(row.get("seed") or "")
                        for row in closed_loop_v2_rows
                        if str(row.get("seed") or "").strip()
                    }
                )
            closed_loop_v2_true_count = _to_int(
                closed_loop_v2_manifest.get(
                    "v2_true_state_feedback_count",
                    closed_loop_v2_manifest.get("true_state_feedback_count"),
                )
            )
            closed_loop_v2_lookahead = closed_loop_v2_provider.get(
                "controller_observation_forecast_lookahead_days"
            )
            all_v2_feedback_confirmed = closed_loop_v2_manifest.get(
                "all_v2_feedback_runs_confirmed_by_engine",
                closed_loop_v2_manifest.get(
                    "all_feedback_runs_confirmed_by_engine"
                ),
            )
            closed_loop_v2_causal_contract_confirmed = bool(
                closed_loop_v2_paired_count > 0
                and closed_loop_v2_true_count == closed_loop_v2_paired_count
                and all_v2_feedback_confirmed is True
                and closed_loop_v2_provider.get("closed_loop_claimed") is True
                and closed_loop_v2_provider.get(
                    "observation_causal_contract_satisfied"
                )
                is True
                and closed_loop_v2_provider.get("future_realization_access")
                is False
                and isinstance(closed_loop_v2_lookahead, int)
                and not isinstance(closed_loop_v2_lookahead, bool)
                and closed_loop_v2_lookahead == 0
            )

            split_payload = _mapping_child(
                closed_loop_v2_protocol, "seed_split"
            )
            if not split_payload:
                split_payload = _mapping_child(
                    closed_loop_v2_protocol, "seed_protocol"
                )
            training_seeds = _seed_list(
                closed_loop_v2_protocol,
                "train_seeds",
                "training_seeds",
            ) or _seed_list(split_payload, "train", "training")
            validation_seeds = _seed_list(
                closed_loop_v2_protocol,
                "validation_seeds",
                "holdout_seeds",
            ) or _seed_list(split_payload, "validation", "holdout")
            split_disjoint: bool | None = None
            if training_seeds or validation_seeds:
                split_disjoint = bool(
                    training_seeds
                    and validation_seeds
                    and set(training_seeds).isdisjoint(validation_seeds)
                )
            elif type(
                closed_loop_v2_protocol.get("train_validation_disjoint")
            ) is bool:
                split_disjoint = bool(
                    closed_loop_v2_protocol["train_validation_disjoint"]
                )
            elif type(split_payload.get("disjoint")) is bool:
                split_disjoint = bool(split_payload["disjoint"])

            stabilization = _mapping_child(
                closed_loop_v2_protocol, "stabilization"
            )
            if not stabilization:
                stabilization = _mapping_child(
                    closed_loop_v2_protocol, "warm_start_contract"
                )
            warmup_days = _to_float(
                closed_loop_v2_protocol.get(
                    "warmup_days",
                    stabilization.get(
                        "warmup_days",
                        stabilization.get("physical_warmup_days"),
                    ),
                )
            )
            opening_contract = _mapping_child(
                closed_loop_v2_protocol, "opening_state_contract"
            )
            opening_state_match = closed_loop_v2_protocol.get(
                "opening_state_match_all",
                opening_contract.get("all_arms_match"),
            )
            if type(opening_state_match) is not bool:
                executed_split_names = closed_loop_v2_protocol.get(
                    "executed_splits"
                )
                protocol_splits = _mapping_child(
                    closed_loop_v2_protocol, "splits"
                )
                if isinstance(executed_split_names, list):
                    split_match_values = [
                        protocol_splits.get(str(split_name), {}).get(
                            "all_boundary_hashes_match"
                        )
                        for split_name in executed_split_names
                        if isinstance(
                            protocol_splits.get(str(split_name)), dict
                        )
                    ]
                    if split_match_values and all(
                        type(value) is bool for value in split_match_values
                    ):
                        opening_state_match = all(split_match_values)
            gate_contract = _mapping_child(
                closed_loop_v2_protocol, "costly_action_gate"
            )
            if not gate_contract:
                gate_contract = _mapping_child(
                    closed_loop_v2_protocol, "gate_audit"
                )
            gate_violation_count = _to_float(
                closed_loop_v2_protocol.get(
                    "costly_gate_violation_count",
                    gate_contract.get("violation_count"),
                )
            )
            protocol_config = _mapping_child(
                closed_loop_v2_protocol, "config"
            )
            policy_hash = str(
                closed_loop_v2_protocol.get("selected_policy_sha256")
                or protocol_config.get("sha256_frozen_before_execution")
                or closed_loop_v2_manifest.get("selected_policy_sha256")
                or ""
            )
            stability_contract = _mapping_child(
                closed_loop_v2_protocol, "burn_in_stability"
            )
            stability_status = str(
                stability_contract.get("status") or "non documentee"
            )
            protocol_rows: list[list[str]] = []
            if closed_loop_v2_protocol:
                protocol_rows.extend(
                    [
                        [
                            "Phase",
                            str(
                                closed_loop_v2_protocol.get("phase")
                                or closed_loop_v2_protocol.get("status")
                                or "non documentee"
                            ),
                        ],
                        [
                            "Warm-up physique / controleur",
                            (
                                f"{int(warmup_days)} jours"
                                if warmup_days is not None
                                and float(warmup_days).is_integer()
                                else "non documente"
                            ),
                        ],
                        [
                            "Separation train / validation",
                            (
                                f"{len(training_seeds)} / {len(validation_seeds)} graines; "
                                + (
                                    "disjoints"
                                    if split_disjoint is True
                                    else "chevauchement ou preuve absente"
                                )
                            ),
                        ],
                        [
                            "Etat physique initial apparie",
                            (
                                "oui"
                                if opening_state_match is True
                                else "non confirme"
                            ),
                        ],
                        [
                            "Violations gates couteux",
                            (
                                str(int(gate_violation_count))
                                if gate_violation_count is not None
                                and float(gate_violation_count).is_integer()
                                else "non documentees"
                            ),
                        ],
                        [
                            "Politique verrouillee",
                            policy_hash if policy_hash else "SHA-256 non fourni",
                        ],
                        [
                            "Stabilite terminale du burn-in",
                            stability_status,
                        ],
                    ]
                )

            mean_v2_service_delta = _mean_finite(
                closed_loop_v2_rows, "delta_vs_mrp_service"
            )
            mean_v2_backlog_delta = _mean_finite(
                closed_loop_v2_rows, "delta_vs_mrp_backlog_area_days"
            )
            mean_v2_inventory_delta = _mean_finite(
                closed_loop_v2_rows, "delta_vs_mrp_mean_inventory_days"
            )
            split_note = (
                f"train {len(training_seeds)} / validation {len(validation_seeds)}; disjoints"
                if split_disjoint is True
                else "separation train / validation non confirmee"
            )
            closed_loop_v2_cards = [
                _metric_card(
                    "Claims moteur V2",
                    f"{closed_loop_v2_true_count} / {closed_loop_v2_paired_count}",
                    "feedback physique confirme",
                    "#0f766e",
                ),
                _metric_card(
                    "Validation hold-out",
                    str(len(validation_seeds) or closed_loop_v2_paired_count),
                    split_note,
                    "#2563eb",
                ),
                _metric_card(
                    "Warm-up V2",
                    (
                        f"{int(warmup_days)} jours"
                        if warmup_days is not None
                        and float(warmup_days).is_integer()
                        else "non documente"
                    ),
                    "protocole additif; V1 historique conserve",
                    "#7c3aed",
                ),
                _metric_card(
                    "Gates couteux",
                    (
                        str(int(gate_violation_count))
                        if gate_violation_count is not None
                        and float(gate_violation_count).is_integer()
                        else "n/a"
                    ),
                    "violations documentees",
                    "#be123c",
                ),
                _metric_card(
                    "Delta service V2",
                    fmt_qty(mean_v2_service_delta, 4),
                    (
                        f"backlog {fmt_qty(mean_v2_backlog_delta, 4)}; "
                        f"stock {fmt_qty(mean_v2_inventory_delta, 2)} jours"
                    ),
                    "#d97706",
                ),
            ]
            closed_loop_v2_html = _closed_loop_v2_section_html(
                cards=closed_loop_v2_cards,
                paired_table=_closed_loop_table(closed_loop_v2_rows),
                figure_cards=closed_loop_v2_figure_cards,
                causal_contract_confirmed=(
                    closed_loop_v2_causal_contract_confirmed
                ),
                protocol_rows=protocol_rows,
            )
    frequency_requested = frequency_root is not None
    frequency_payload: dict[str, Any] = {}
    frequency_available = False
    frequency_html = ""
    frequency_figure_count = 0
    if frequency_requested:
        frequency_payload = build_frequency_dashboard_section(frequency_root)
        frequency_available = frequency_payload.get("available") is True
        if frequency_available:
            frequency_html = str(frequency_payload.get("html") or "")
            frequency_figure_count = _to_int(
                frequency_payload.get("figure_count")
            )
    control_system_requested = control_system_root is not None
    control_system_payload: dict[str, Any] = {}
    control_system_available = False
    control_system_html = ""
    control_system_figure_count = 0
    if control_system_requested:
        control_system_payload = build_control_system_dashboard_section(
            control_system_root
        )
        control_system_available = (
            control_system_payload.get("available") is True
        )
        if control_system_available:
            control_system_html = str(
                control_system_payload.get("html") or ""
            )
            control_system_figure_count = _to_int(
                control_system_payload.get("figure_count")
            )
    validation_rows: list[dict[str, str]] = []
    for validation_path in sorted(
        (result_root / "canonical_replay").glob(
            "*/seed_*/data/canonical_supplier_risk_event_validation.csv"
        )
    ):
        validation_rows.extend(read_csv_rows(validation_path))
    validated_nonzero = sum(
        1
        for row in validation_rows
        if _truthy(row.get("matched"))
        and _truthy(row.get("applied"))
        and str(row.get("status") or "") == "affected_nonzero_flow"
    )

    paired_seeds = {str(row.get("seed") or "") for row in paired_rows if row.get("seed") not in (None, "")}
    source_mode = str(source.get("mode") or "unknown")
    baseline_origin = str(source.get("baseline_origin") or provenance.get("baseline_origin") or "unknown")
    forecast_origin = str(provenance.get("forecast_origin") or prediction.get("forecast_origin") or "unknown")
    industrial_status = str(source.get("baseline_industrial_status") or "unknown")
    evidence_text = (
        "Preuve exploratoire: baseline de simulation du cas d'etude; forecast synthetique PoC; "
        f"statut {industrial_status.replace('_', ' ')}. "
        "Les coefficients physiques restent des hypotheses de recherche."
    )

    cards = [
        _metric_card(
            "Horizon",
            f"{_to_int(source.get('days'))} jours",
            f"mode {source_mode}",
            "#2563eb",
        ),
        _metric_card(
            "Comparaison appariee",
            f"{len(paired_seeds)} graines / {len(paired_rows)} runs",
            f"{len({str(row.get('policy') or '') for row in paired_rows})} politiques",
            "#0f766e",
        ),
        _metric_card(
            "Replay canonique",
            f"{_to_int(canonical.get('successful_runs'))} / {_to_int(canonical.get('expected_runs'))} runs",
            f"{_to_int(canonical.get('derived_oracle_rows'))} oracle derive; open-loop",
            "#7c3aed",
        ),
        _metric_card(
            "Evenements physiques",
            f"{_to_int(canonical.get('risk_event_count'))} evenements",
            f"{validated_nonzero} / {len(validation_rows)} validations non-zero",
            "#d97706",
        ),
        _metric_card(
            "Prediction vers physique",
            f"{_to_int(prediction.get('granular_pairs'))} couples / {_to_int(prediction.get('granular_physical_rows'))} lignes",
            f"validite {_to_int(prediction.get('forecast_validity_days'))} jours",
            "#0891b2",
        ),
        _metric_card(
            "Revue RCI",
            _display_rci_status(rci.get("status")),
            (
                f"{_to_int(rci.get('pack_episode_count'))} episodes; "
                f"{_to_int(rci.get('selected_episode_count'))} selectionnes; revue metier requise"
            ),
            "#be123c",
        ),
    ]

    figure_specs = [
        (
            "plots/regime_timeline.png",
            "Chronologie des regimes",
            "Sequence des regimes du modele reduit; les labels sont des pseudo-ancrages tant que la revue metier manque.",
        ),
        (
            "plots/end_2026/prediction_interval.png",
            "Enveloppe du score de prediction",
            "Enveloppe operationnelle d'un outcome binaire, pas intervalle de confiance de la probabilite latente.",
        ),
        (
            "plots/end_2026/prediction_to_physical_perturbations.png",
            "Prediction vers perturbations physiques",
            "Transformation monotone et configurable vers disponibilite, capacite, delai, qualite et couts.",
        ),
        (
            "plots/end_2026/paired_policy_comparison.png",
            "Comparaison appariee des politiques",
            "Comparaison a graines communes du modele reduit; les deltas MRP contre lui-meme restent exactement nuls.",
        ),
        (
            "plots/end_2026/forecast_confusion_cases.png",
            "TP, FP, FN et TN",
            "Prevision, verite physique et action sont separees sur scenarios apparies.",
        ),
        (
            "plots/end_2026/canonical_mrp_vs_adaptive_trajectory.png",
            "MRP versus politique adaptative canonique",
            "Smoke d'integration physique a schedule journalier pre-calcule; pas une validation statistique en boucle fermee.",
        ),
        (
            "plots/end_2026/rci_business_review_episodes.png",
            "Episodes de revue RCI",
            "Le pack inclut politiques selectionnees, rejetees et agressives; la validation metier reste en attente.",
        ),
    ]
    figure_cards = [
        card
        for relative_path, title, interpretation in figure_specs
        if (card := _figure_html(result_root, relative_path, title, interpretation))
    ]

    limitations = [str(item) for item in manifest.get("limitations", []) if str(item).strip()]
    if not limitations:
        limitations = [
            "Resultats exploratoires non industriels.",
            (
                "Le replay canonique historique utilise un schedule journalier "
                "pre-calcule; l onglet Boucle fermee presente une campagne "
                "moteur distincte lorsqu elle est fournie."
            ),
            "Le RCI reste pending_business_review.",
        ]

    metrics = {
        "source_mode": source_mode,
        "baseline_origin": baseline_origin,
        "forecast_origin": forecast_origin,
        "industrial_status": industrial_status,
        "days": _to_int(source.get("days")),
        "paired_seed_count": len(paired_seeds),
        "paired_run_count": len(paired_rows),
        "policy_count": len({str(row.get("policy") or "") for row in paired_rows}),
        "canonical_successful_runs": _to_int(canonical.get("successful_runs")),
        "canonical_expected_runs": _to_int(canonical.get("expected_runs")),
        "canonical_event_count": _to_int(canonical.get("risk_event_count")),
        "canonical_validation_count": len(validation_rows),
        "canonical_nonzero_validation_count": validated_nonzero,
        "rci_status": str(rci.get("status") or "unknown"),
        "rci_episode_count": _to_int(rci.get("pack_episode_count")),
        "closed_loop_available": closed_loop_available,
        "closed_loop_paired_seed_count": _to_int(
            closed_loop_manifest.get("paired_seed_count")
        ),
        "closed_loop_true_feedback_count": _to_int(
            closed_loop_manifest.get("true_state_feedback_count")
        ),
        "closed_loop_causal_contract_confirmed": (
            closed_loop_causal_contract_confirmed
        ),
    }
    if closed_loop_v2_requested:
        metrics.update(
            {
                "closed_loop_v2_available": closed_loop_v2_available,
                "closed_loop_v2_paired_seed_count": (
                    closed_loop_v2_paired_count
                ),
                "closed_loop_v2_true_feedback_count": (
                    closed_loop_v2_true_count
                ),
                "closed_loop_v2_causal_contract_confirmed": (
                    closed_loop_v2_causal_contract_confirmed
                ),
                "closed_loop_v2_protocol_available": bool(
                    closed_loop_v2_protocol
                ),
            }
        )
    if frequency_requested:
        frequency_metrics = frequency_payload.get("metrics")
        frequency_metrics = (
            frequency_metrics if isinstance(frequency_metrics, dict) else {}
        )
        metrics.update(
            {
                "frequency_available": frequency_available,
                "frequency_claim_scope": frequency_metrics.get("claim_scope"),
                "frequency_global_stability_claimed": frequency_metrics.get(
                    "global_stability_claimed"
                ),
                "frequency_source_claim_conflict": frequency_metrics.get(
                    "source_claim_conflict"
                ),
            }
        )
    if control_system_requested:
        control_system_metrics = control_system_payload.get("metrics")
        control_system_metrics = (
            control_system_metrics
            if isinstance(control_system_metrics, dict)
            else {}
        )
        metrics.update(
            {
                "control_system_available": control_system_available,
                "control_system_local_model_validated": (
                    control_system_metrics.get("local_model_validated")
                ),
                "control_system_controllability_rank": (
                    control_system_metrics.get("controllability_rank")
                ),
                "control_system_observability_rank": (
                    control_system_metrics.get("observability_rank")
                ),
                "control_system_validated_pole_count": (
                    control_system_metrics.get("validated_pole_count")
                ),
                "control_system_pole_claim_conflict": (
                    control_system_metrics.get("pole_claim_conflict")
                ),
                "control_system_local_stability_demonstrated": (
                    control_system_metrics.get(
                        "local_stability_demonstrated"
                    )
                ),
            }
        )
    return {
        "schema_version": SCAN_DASHBOARD_SCHEMA_VERSION,
        "available": True,
        "status": "ready",
        "metrics": metrics,
        "figure_count": len(figure_cards) + (
            len(closed_loop_figure_cards) if closed_loop_available else 0
        ) + (
            len(closed_loop_v2_figure_cards)
            if closed_loop_v2_available
            else 0
        ) + (frequency_figure_count if frequency_available else 0) + (
            control_system_figure_count if control_system_available else 0
        ),
        "html": _dashboard_html(
            cards=cards,
            evidence_text=evidence_text,
            limitations=limitations,
            regime_table=_regime_table(regime_rows),
            policy_table=_policy_table(paired_summary_rows),
            canonical_table=_canonical_table(canonical_rows),
            confusion_table=_confusion_table(confusion_rows),
            figure_cards=figure_cards,
            closed_loop_html=closed_loop_html,
            closed_loop_v2_html=closed_loop_v2_html,
            frequency_html=frequency_html,
            control_system_html=control_system_html,
        ),
    }


__all__ = ["SCAN_DASHBOARD_SCHEMA_VERSION", "build_scan_dashboard_payload"]
