"""Reporting helpers for the additive canonical frequency study."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


_V2_CONTROLLER_SCHEMA_VERSION = "scan.canonical_state_feedback.v2"
_V3_CONTROLLER_SCHEMA_VERSION = "scan.canonical_state_feedback.v3"


def _feedback_publication_terms(
    controller_schema_version: str | None,
) -> dict[str, str | bool]:
    """Return legacy V2 labels or version-neutral feedback labels."""

    schema_version = str(
        controller_schema_version or _V2_CONTROLLER_SCHEMA_VERSION
    )
    legacy_v2 = schema_version == _V2_CONTROLLER_SCHEMA_VERSION
    v3 = schema_version == _V3_CONTROLLER_SCHEMA_VERSION
    if legacy_v2:
        return {
            "legacy_v2": True,
            "schema_version": schema_version,
            "comparison": "V2/MRP",
            "reverse_comparison": "MRP/V2",
            "commands": "commandes V2",
            "section_heading": "Comparaison fréquentielle V2 / MRP",
            "time_frequency_context": "V2",
        }
    return {
        "legacy_v2": False,
        "schema_version": schema_version,
        "comparison": "feedback/MRP",
        "reverse_comparison": "MRP/feedback",
        "commands": "commandes de la régulation adaptative",
        "section_heading": "Comparaison fréquentielle feedback / MRP",
        "time_frequency_context": (
            "régulation adaptative V3" if v3 else "régulation adaptative"
        ),
    }


def _comparison_column(frame: pd.DataFrame, *names: str) -> str | None:
    """Select a version-neutral field first, then its historical alias."""

    return next((name for name in names if name in frame.columns), None)


def _finite_median(frame: pd.DataFrame, field: str) -> float | None:
    if frame.empty or field not in frame:
        return None
    values = pd.to_numeric(frame[field], errors="coerce").dropna()
    values = values[np.isfinite(values.to_numpy(dtype=float))]
    return float(values.median()) if not values.empty else None


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _response_pattern(row: pd.Series) -> str:
    """Return the refined repeated-period class, including legacy artifacts."""

    documented = str(row.get("response_pattern") or "").strip()
    if documented:
        return documented
    try:
        values = [float(value) for value in json.loads(str(row["period_rms_json"]))]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "unclassified"
    floor = 1e-12
    if not values or max(abs(value) for value in values) <= floor:
        return "no_measurable_response"
    if bool(row.get("repeatable_periodic_response", False)):
        return "nonzero_repeatable_response"
    if len(values) >= 2 and all(
        values[index] > values[index - 1] + floor
        for index in range(1, len(values))
    ):
        return "monotonic_growth_detected"
    peak = int(np.argmax(values))
    if 0 < peak < len(values) - 1:
        return "interior_period_peak_transient_or_delay"
    return "other_nonstationary_response"


def _descriptive_phase_reason(row: pd.Series) -> str:
    """Explain why a phase slope remains descriptive instead of local."""

    status = str(row.get("status") or "")
    response_scope = str(row.get("response_regime_scope") or "")
    if "hybrid" in status or "hybrid" in response_scope:
        return "tendance descriptive : changement de régime hybride"
    if (
        "active_set_unverified" in status
        or "active_set_unverified" in response_scope
        or row.get("active_set_invariance_verified") is False
        or row.get("amplitude_sweep_verified") is False
    ):
        return (
            "tendance descriptive à l'amplitude testée : balayage d'amplitude "
            "et invariance des contraintes actives non vérifiés"
        )
    return "tendance descriptive : portée locale non vérifiée"


def write_frequency_report(
    output_root: Path,
    *,
    native_spectra: pd.DataFrame,
    native_bands: pd.DataFrame,
    response: pd.DataFrame,
    closed_loop_comparison: pd.DataFrame,
    resonances: pd.DataFrame,
    stability: pd.DataFrame,
    residual: pd.DataFrame,
    regime_occupancy: pd.DataFrame,
    normalized_config: Mapping[str, Any],
    delays: pd.DataFrame | None = None,
    controller_schema_version: str | None = None,
) -> Path:
    """Write a concise scientific report with explicit claim boundaries."""

    publication_terms = _feedback_publication_terms(controller_schema_version)
    attenuation_field = _comparison_column(
        closed_loop_comparison,
        "feedback_minus_mrp_attenuation_db",
        "v2_minus_mrp_attenuation_db",
    )
    coherence_threshold = float(normalized_config["coherence_threshold"])
    raw_coherent_count = (
        int(
            pd.to_numeric(response["coherence"], errors="coerce")
            .ge(coherence_threshold)
            .sum()
        )
        if not response.empty
        else 0
    )
    valid_mask = (
        _boolean_series(response, "valid_bin")
        if not response.empty
        else pd.Series(False, index=response.index, dtype=bool)
    )
    valid_count = int(valid_mask.sum())
    valid_share = valid_count / len(response) if len(response) else 0.0
    supervisory_mode_compatible_count = (
        int((valid_mask & _regime_compatible_mask(response)).sum())
        if not response.empty
        else 0
    )
    repetition_counts = (
        pd.to_numeric(response["repetition_count"], errors="coerce").dropna()
        if not response.empty and "repetition_count" in response
        else pd.Series(dtype=float)
    )
    retained_period_count = (
        int(repetition_counts.mode().iloc[0])
        if not repetition_counts.empty
        else max(1, int(normalized_config["measured_periods"]) - 1)
    )
    reliable = (
        closed_loop_comparison.loc[closed_loop_comparison["reliable_comparison"].astype(bool)]
        if not closed_loop_comparison.empty
        else pd.DataFrame()
    )
    attenuation = (
        _finite_median(reliable, attenuation_field)
        if attenuation_field is not None
        else None
    )
    attenuated_count = (
        int(reliable["attenuation_observed"].astype(bool).sum())
        if not reliable.empty
        else 0
    )
    dynamic_reliable = (
        reliable.loc[
            reliable["dynamic_feedback_modulation_identified"].astype(bool)
        ]
        if not reliable.empty
        and "dynamic_feedback_modulation_identified" in reliable
        else pd.DataFrame()
    )
    paired_interval_rows = (
        reliable.dropna(
            subset=["paired_attenuation_db_q025", "paired_attenuation_db_q975"]
        )
        if not reliable.empty
        and {
            "paired_attenuation_db_q025",
            "paired_attenuation_db_q975",
        }.issubset(reliable.columns)
        else pd.DataFrame()
    )
    paired_zero_count = (
        int(
            paired_interval_rows.get(
                "zero_db_in_paired_interval",
                pd.Series(False, index=paired_interval_rows.index),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        )
        if not paired_interval_rows.empty
        else 0
    )
    stability_patterns = (
        stability.apply(_response_pattern, axis=1)
        if not stability.empty
        else pd.Series(dtype=str)
    )
    no_response_count = int(stability_patterns.eq("no_measurable_response").sum())
    nonzero_repeatable_count = int(
        stability_patterns.eq("nonzero_repeatable_response").sum()
    )
    monotonic_growth_count = int(
        stability_patterns.eq("monotonic_growth_detected").sum()
    )
    interior_peak_count = int(
        stability_patterns.eq("interior_period_peak_transient_or_delay").sum()
    )
    other_nonstationary_count = int(
        stability_patterns.eq("other_nonstationary_response").sum()
    )
    active_residual = (
        residual.loc[
            pd.to_numeric(residual["designed_output_power"], errors="coerce").gt(1e-30)
        ]
        if not residual.empty and "designed_output_power" in residual
        else pd.DataFrame()
    )
    residual_median = _finite_median(
        active_residual, "residual_to_designed_energy_ratio"
    )

    bullwhip_lines: list[str] = []
    if not native_bands.empty:
        selected = native_bands.loc[
            native_bands["output_signal"].isin(
                ["global_order_qty", "global_production_qty", "global_supplier_shipments_qty"]
            )
        ]
        for _, row in selected.sort_values(["source_run", "output_signal", "period_min_days"]).iterrows():
            spectral_band = native_spectra.loc[
                native_spectra["source_run"].astype(str).eq(str(row["source_run"]))
                & native_spectra["input_signal"].astype(str).eq(
                    str(row["input_signal"])
                )
                & native_spectra["output_signal"].astype(str).eq(
                    str(row["output_signal"])
                )
                & pd.to_numeric(native_spectra["period_days"], errors="coerce").ge(
                    float(row["period_min_days"])
                )
                & pd.to_numeric(native_spectra["period_days"], errors="coerce").lt(
                    float(row["period_max_days"])
                )
            ]
            median_coherence = _finite_median(spectral_band, "coherence")
            bullwhip_lines.append(
                f"- `{row['source_run']}` — `{row['output_signal']}` — {row['band']}: "
                f"{float(row['power_amplification_db']):+.2f} dB de variabilité relative; "
                f"cohérence médiane {_fmt(median_coherence, 3)} "
                "(diagnostic observationnel, pas transfert causal)."
            )
    if not bullwhip_lines:
        bullwhip_lines.append("- Spectres natifs non exécutés dans cette phase.")

    attenuation_lines: list[str] = []
    if not reliable.empty and attenuation_field is not None:
        grouped = reliable.groupby(["condition", "input_signal", "output_signal"], sort=True)
        summaries: list[tuple[float, str]] = []
        for keys, group in grouped:
            median_db = float(group[attenuation_field].median())
            interval_note = (
                f"Intervalle apparié exact "
                f"[{float(group.iloc[0]['paired_attenuation_db_q025']):+.4f}; "
                f"{float(group.iloc[0]['paired_attenuation_db_q975']):+.4f}] dB; "
                "le signe reste non concluant."
                if len(group) == 1
                and {
                    "paired_attenuation_db_q025",
                    "paired_attenuation_db_q975",
                }.issubset(group.columns)
                and pd.notna(group.iloc[0]["paired_attenuation_db_q025"])
                and pd.notna(group.iloc[0]["paired_attenuation_db_q975"])
                else (
                    "Le signe est descriptif et non concluant sans incertitude "
                    "appariée sur la différence."
                )
            )
            summaries.append(
                (
                    abs(median_db),
                    f"- `{keys[0]}` — `{keys[1]} → {keys[2]}`: médiane "
                    f"{publication_terms['comparison']} {median_db:+.2f} dB "
                    f"sur {len(group)} ligne(s) valide(s); interprétation "
                    f"`{group['comparison_interpretation'].mode().iloc[0]}`. "
                    f"{interval_note}",
                )
            )
        attenuation_lines = [line for _, line in sorted(summaries, reverse=True)[:15]]
    else:
        attenuation_lines.append(
            f"- Aucun point {publication_terms['reverse_comparison']} ne satisfait "
            "encore simultanément le seuil de cohérence."
        )

    regime_lines: list[str] = []
    if not regime_occupancy.empty:
        feedback = regime_occupancy.loc[regime_occupancy["policy"].eq("canonical_feedback")]
        for keys, group in feedback.groupby(
            ["condition", "arm", "experiment_input_signal"], sort=True
        ):
            dominant = group.loc[group["day_count"].astype(int).idxmax()]
            regime_lines.append(
                f"- `{keys[0]}` / `{keys[1]}` / `{keys[2]}`: régime dominant `{dominant['confirmed_regime']}` "
                f"({100.0 * float(dominant['day_share']):.1f} % des jours)."
            )
    if not regime_lines:
        regime_lines.append("- Occupation des régimes non disponible dans cette phase.")

    quality_lines: list[str] = []
    if not response.empty and "input_signal" in response:
        for input_signal, group in response.groupby("input_signal", sort=True):
            detected = int(group["response_detected"].astype(bool).sum())
            coherent = int(
                pd.to_numeric(group["coherence"], errors="coerce")
                .ge(coherence_threshold)
                .sum()
            )
            valid = int(group["valid_bin"].astype(bool).sum())
            local = int(
                (
                    _boolean_series(group, "valid_bin")
                    & _regime_compatible_mask(group)
                ).sum()
            )
            quality_lines.append(
                f"- `{input_signal}` : {len(group)} lignes, {detected} lignes de "
                f"sortie numériquement non nulles, {coherent} cohérences brutes ≥ {coherence_threshold:.2f}, "
                f"{valid} lignes numériquement valides, {local} gardant la même "
                "trace du régime superviseur à l'amplitude testée."
            )
    if not quality_lines:
        quality_lines.append("- Aucun probe conçu disponible.")

    delay_frame = delays if delays is not None else pd.DataFrame()
    identified_delays = (
        delay_frame.loc[
            pd.to_numeric(delay_frame["delay_days"], errors="coerce").notna()
        ]
        if not delay_frame.empty and "delay_days" in delay_frame
        else pd.DataFrame()
    )
    delay_lines: list[str] = []
    for _, row in identified_delays.iterrows():
        delay_lines.append(
            f"- `{row['condition']}` / `{row['policy']}` / "
            f"`{row['input_signal']} → {row['output_signal']}` : "
            f"{float(row['delay_days']):.2f} jours, R² pondéré "
            f"{float(row['weighted_r_squared']):.3f}; `{row['status']}`."
        )
    if not delay_lines:
        delay_lines.append("- Aucun délai local identifiable après contrôle du mode hybride.")
    descriptive_phase_trends = (
        delay_frame.loc[
            pd.to_numeric(
                delay_frame.get(
                    "descriptive_phase_slope_days",
                    pd.Series(index=delay_frame.index, dtype=float),
                ),
                errors="coerce",
            ).notna()
            & pd.to_numeric(
                delay_frame.get(
                    "delay_days", pd.Series(index=delay_frame.index, dtype=float)
                ),
                errors="coerce",
            ).isna()
        ]
        if not delay_frame.empty
        else pd.DataFrame()
    )
    hybrid_phase_lines = [
        (
            f"- `{row['condition']}` / `{row['policy']}` / "
            f"`{row['input_signal']} → {row['output_signal']}` : "
            f"{float(row['descriptive_phase_slope_days']):.2f} jours, "
            f"{_descriptive_phase_reason(row)}."
        )
        for _, row in descriptive_phase_trends.iterrows()
    ]
    if not hybrid_phase_lines:
        hybrid_phase_lines.append("- Aucune pente de phase descriptive reclassée.")
    structural_leads = (
        sorted(
            set(
                pd.to_numeric(
                    delay_frame["structural_probe_lead_days"], errors="coerce"
                ).dropna()
            )
        )
        if not delay_frame.empty and "structural_probe_lead_days" in delay_frame
        else []
    )
    lead_alias_bounds = (
        sorted(
            set(
                pd.to_numeric(
                    delay_frame.loc[
                        pd.to_numeric(
                            delay_frame["structural_probe_lead_days"], errors="coerce"
                        ).notna(),
                        "phase_unwrap_abs_delay_bound_days",
                    ],
                    errors="coerce",
                ).dropna()
            )
        )
        if not delay_frame.empty
        and "structural_probe_lead_days" in delay_frame
        and "phase_unwrap_abs_delay_bound_days" in delay_frame
        else []
    )
    alias_contract = (
        "Leads structurels du probe : "
        + ", ".join(f"{float(value):g}" for value in structural_leads)
        + " jours; borne de désambiguïsation de phase : "
        + ", ".join(f"{float(value):g}" for value in lead_alias_bounds)
        + " jours."
        if structural_leads and lead_alias_bounds
        else "Le contrôle d'alias du lead structurel n'est pas documenté."
    )
    comparison_uncertainty_contract = (
        f"Des intervalles appariés exacts sont disponibles pour {len(paired_interval_rows)} "
        f"point(s); {paired_zero_count} contiennent 0 dB. Ils restent descriptifs avec "
        f"seulement {retained_period_count} période(s) retenue(s)."
        if not paired_interval_rows.empty
        else "Avec un seul point fiable et sans incertitude appariée de la différence, "
        "l'écart reste non concluant."
    )
    if bool(publication_terms["legacy_v2"]):
        comparison_explanation = (
            "Une valeur négative signifie seulement que le gain ponctuel V2 est "
            "inférieur au gain MRP sur la même ligne d'excitation. Les lignes de "
            "faible cohérence sont exclues. Lorsque les commandes V2 restent "
            "constantes dans un régime, il s'agit d'un conditionnement par playbook "
            "fixe et non d'une réjection dynamique par feedback; cette distinction "
            "est portée par `comparison_interpretation`."
        )
        stability_explanation = (
            "Le MRP est déjà une boucle fermée sur stock, transit et backlog. Le V2 "
            "est un superviseur hybride à seuils, confirmation, dwell et slew. Dans "
            "un playbook fixe, sa dérivée locale commande/état est souvent nulle ; "
            "aux frontières, elle est discontinue. Une marge de gain ou de phase "
            "globale n'est donc pas définie à partir de ces données."
        )
    else:
        comparison_explanation = (
            "Une valeur négative signifie seulement que le gain ponctuel du feedback "
            "est inférieur au gain MRP sur la même ligne d'excitation. Les lignes de "
            "faible cohérence sont exclues. Lorsque les commandes de la régulation "
            "adaptative restent constantes dans un régime, il s'agit d'un "
            "conditionnement par politique fixe et non d'une réjection dynamique par "
            "feedback; cette distinction est portée par `comparison_interpretation`."
        )
        stability_explanation = (
            "Le MRP est déjà une boucle fermée sur stock, transit et backlog. La "
            "régulation adaptative combine une supervision hybride et une modulation "
            "continue dépendante de l'état. Dans un régime fixe, une dérivée locale "
            "peut exister, mais ce protocole à amplitude finie ne l'identifie pas ; "
            "aux frontières de régime, le comportement reste discontinu. Une marge "
            "de gain ou de phase globale n'est donc pas définie à partir de ces données."
        )

    actuator_application_mode = str(
        normalized_config.get("actuator_application_mode")
        or "open_loop_schedule"
    )
    if actuator_application_mode == "post_feedback_additive":
        actuator_probe_scope = (
            "- Les trois leviers sont testés séparément par une petite variation "
            "ajoutée après la commande calculée par le V3. La commande du régulateur, "
            "la variation d'essai et la commande réellement appliquée sont tracées "
            "séparément. Ces résultats décrivent la réponse de la boucle fermée à "
            "l'amplitude testée; ils ne suffisent pas à isoler la dynamique physique "
            "de la supply chain."
        )
    else:
        actuator_probe_scope = (
            "- Le probe des leviers est un overlay multiplicatif du MRP, pas un "
            "dither additif indépendant du plant."
        )

    report = f"""# RESILIENCE-SCAN — bilan fréquentiel canonique

## Verdict

L'étude sépare les oscillations présentes naturellement dans le cas `etudecas` et les réponses obtenues en imposant des oscillations connues. Le système évolue par pas d'un jour, avec des lots, des délais, un calendrier et des changements de régime : il n'est donc ni linéaire ni constant dans le temps. Chaque essai fait varier une seule entrée à la fois et mesure la réponse de plusieurs sorties. Il s'agit de réponses empiriques à certaines fréquences, pas de la fonction fréquentielle d'un système linéaire isolé. Dans le paquet source historique, `small_signal_local_claim=true` signifiait seulement que le régime superviseur suivait la même séquence à l'amplitude testée. Le paquet audité force ce champ à `false` et conserve séparément cette information de compatibilité. Sans essais réellement distincts à des amplitudes décroissantes, ni vérification que les mêmes contraintes et règles de lot restent actives, aucune réponse locale autour du point de fonctionnement n'est revendiquée.

Le protocole conçu utilise {int(normalized_config['measured_periods'])} périodes mesurées de {int(normalized_config['period_days'])} jours après {int(normalized_config['warmup_days'])} jours de mise en régime physique. Pendant cette mise en régime, le contrôleur n'utilise que les informations déjà disponibles à chaque date. La résolution est {1.0 / int(normalized_config['period_days']):.6f} cycle/jour ; avec un pas quotidien, la fréquence maximale observable est 0,5 cycle/jour.

## Qualité d'identification

- Lignes de réponse empiriques produites : {len(response)}.
- Lignes avec cohérence brute ≥ {coherence_threshold:.2f} : {raw_coherent_count}. La cohérence seule ne suffit pas à valider une ligne.
- Lignes numériquement valides après réponse détectée, cohérence, bornage et répétabilité : {valid_count} ({100.0 * valid_share:.1f} %).
- Parmi elles, lignes compatibles avec la même trace du régime superviseur à l'amplitude testée : {supervisory_mode_compatible_count}. Ce compteur n'est pas encore une preuve petit-signal; les autres lignes sont hybrides et changent de régime.
- Comparaisons {publication_terms['reverse_comparison']} fiables : {len(reliable)}.
- Comparaisons avec modulation dynamique cohérente des {publication_terms['commands']} : {len(dynamic_reliable)}.
- Écart {publication_terms['comparison']} médian sur points fiables : {_fmt(attenuation)} dB ; signe négatif sur {attenuated_count} / {len(reliable)} point(s). Ce décompte de signe est descriptif, pas un taux d'efficacité ni un test de significativité.
- Ratio médian énergie hors lignes / énergie aux lignes conçues : {_fmt(residual_median, 4)} sur {len(active_residual)} diagnostics dont la puissance conçue dépasse le plancher numérique. Il combine non-linéarité, bruit et effets non modélisés ; ce n'est pas un THD pur.
- Diagnostics sans réponse mesurable : {no_response_count} / {len(stability)}; ils ne doivent pas être comptés comme réponses répétables identifiées.
- Réponses non nulles et répétables : {nonzero_repeatable_count} / {len(stability)}.
- Croissances monotones matérielles : {monotonic_growth_count}; pics sur une période intérieure, compatibles avec un transitoire ou un délai non résorbé : {interior_peak_count}; autres non-stationnarités : {other_nonstationary_count}.
- Les quantiles 2,5 %–97,5 % sont des intervalles descriptifs de rééchantillonnage des {retained_period_count} période(s) retenue(s), pas des intervalles de confiance à couverture 95 % calibrée.

## Détail par excitation conçue

{chr(10).join(quality_lines)}

Pour les probes actionneurs, une absence de ligne valide ne signifie pas que la commande n'a pas été appliquée : l'application physique se vérifie séparément dans l'audit d'excitation. Elle signifie que la réponse n'est pas suffisamment détectée, cohérente, bornée et répétable pour être identifiée avec ce protocole.

## Pentes de phase et délais

{chr(10).join(delay_lines)}

Pentes conservées comme tendances descriptives sans identification d'un délai local :

{chr(10).join(hybrid_phase_lines)}

Une pente de phase descriptive ne constitue ni un retard de groupe local ni une preuve du délai de transport physique. {alias_contract} Ces leads structurels servent au contrôle d'alias; ils ne sont pas des estimations fréquentielles.

## Variabilité spectrale native entre échelons

Les ratios ci-dessous utilisent des PSD normalisées par la moyenne absolue de chaque signal. Ils mesurent une amplification de variabilité relative souvent appelée bullwhip, mais la demande naturelle n'est pas une excitation instrumentale indépendante. Une faible cohérence indique notamment que le calendrier, la lotification et les risques endogènes dominent une partie de la puissance.

{chr(10).join(bullwhip_lines)}

## {publication_terms['section_heading']}

{comparison_explanation} {comparison_uncertainty_contract}

{chr(10).join(attenuation_lines)}

## Régimes effectivement visités

{chr(10).join(regime_lines)}

## Stabilité et marges

{stability_explanation}

Les diagnostics publiés sont : cohérence, répétabilité du gain entrée-sortie sur les lignes testées, atténuation {publication_terms['comparison']}, énergie résiduelle, croissance RMS et non-stationnarité entre périodes. Ils peuvent détecter une amplification ou une dérive au fil des périodes, mais ne prouvent pas la stabilité non linéaire globale.

## Portée des preuves

- Les trajectoires natives sont des sorties simulées du cas `etudecas`, pas des mesures industrielles.
- Les multisines sont synthétiques et bornées. Elles sondent des réponses harmoniques à amplitude finie; elles ne suffisent pas à identifier une dérivée locale et peuvent faire changer le régime hybride.
- Les réponses mesurées dépendent des amplitudes et des conditions testées. Une trace de régime identique est une première condition nécessaire, mais ne prouve pas une réponse locale : le calendrier hebdomadaire, les contraintes actives et les règles de lot peuvent encore introduire des transferts ou des discontinuités.
{actuator_probe_scope}
- `global_stability_claimed = false`.
- `industrial_validation_claimed = false`.
"""
    path = Path(output_root) / "canonical_frequency_report.md"
    path.write_text(report, encoding="utf-8")
    return path


def _import_plotting() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(
    fig: Any,
    path: Path,
    plt: Any,
    *,
    layout_rect: tuple[float, float, float, float] = (0, 0.035, 1, 0.97),
) -> Path:
    fig.tight_layout(rect=layout_rect)
    fig.text(
        0.01,
        0.008,
        "RESILIENCE-SCAN — simulation etudecas non industrielle; réponses à l'amplitude testée, aucune dérivée locale ni stabilité globale revendiquée.",
        fontsize=7.5,
        color="#475569",
    )
    fig.savefig(path, dpi=165, bbox_inches="tight")
    plt.close(fig)
    return path


def _line_style(policy: str) -> tuple[str, str]:
    if policy == "canonical_feedback":
        return "#0f766e", "-"
    if policy == "mrp_reference":
        return "#2563eb", "--"
    return "#7c3aed", ":"


_BODE_INPUT_PRIORITY = (
    "supplier_lead_time_multiplier",
    "supplier_availability_multiplier",
    "demand_multiplier",
)

_BODE_INPUT_LABELS = {
    "supplier_lead_time_multiplier": "délai fournisseur",
    "supplier_availability_multiplier": "disponibilité fournisseur",
    "demand_multiplier": "demande",
}

_BODE_OUTPUT_PRIORITY = (
    "probe_destination_arrivals_qty",
    "probe_supplier_shipments_qty",
    "probe_supplier_stock_qty",
    "probe_supplier_utilization",
    "target_production_qty",
    "target_finished_stock_qty",
    "target_backlog_qty",
    "target_service_level",
    "global_inventory_qty",
    "global_backlog_qty",
    "global_order_qty",
    "global_production_qty",
    "global_supplier_shipments_qty",
    "global_service_level",
)

_BODE_OUTPUT_LABELS = {
    "probe_destination_arrivals_qty": "Arrivées composant ciblé",
    "probe_supplier_shipments_qty": "Expéditions fournisseur ciblé",
    "probe_supplier_stock_qty": "Stock fournisseur ciblé",
    "probe_supplier_utilization": "Utilisation fournisseur ciblé",
    "target_production_qty": "Production article cible",
    "target_finished_stock_qty": "Stock article cible",
    "target_backlog_qty": "Backlog article cible",
    "target_service_level": "Service article cible",
    "global_inventory_qty": "Stock global",
    "global_backlog_qty": "Backlog global",
    "global_order_qty": "Commandes globales",
    "global_production_qty": "Production globale",
    "global_supplier_shipments_qty": "Expéditions fournisseurs globales",
    "global_service_level": "Service global",
}


def _boolean_series(frame: pd.DataFrame, field: str) -> pd.Series:
    if field not in frame:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[field]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    return values.map(
        lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"}
        if pd.notna(value)
        else False
    ).astype(bool)


def _designed_disturbance_response(response: pd.DataFrame) -> pd.DataFrame:
    if response.empty:
        return response.copy()
    designed = response.copy()
    if "study_kind" in designed:
        designed = designed.loc[
            designed["study_kind"].astype(str).eq(
                "designed_closed_loop_disturbance_probe"
            )
        ]
    return designed


def _select_bode_input(response: pd.DataFrame) -> str | None:
    """Select an input with valid evidence; never promote an all-invalid demand probe."""

    designed = _designed_disturbance_response(response)
    if designed.empty or "input_signal" not in designed:
        return None
    valid = _boolean_series(designed, "valid_bin")
    counts = (
        designed.assign(_valid=valid)
        .groupby("input_signal", sort=True)["_valid"]
        .sum()
    )
    eligible = {str(name): int(count) for name, count in counts.items() if int(count) > 0}
    if not eligible:
        return None
    for preferred in _BODE_INPUT_PRIORITY:
        if preferred == "supplier_lead_time_multiplier" and preferred in eligible:
            return preferred
    priority = {name: index for index, name in enumerate(_BODE_INPUT_PRIORITY)}
    return min(
        eligible,
        key=lambda name: (-eligible[name], priority.get(name, len(priority)), name),
    )


def _select_bode_outputs(
    response: pd.DataFrame,
    input_signal: str,
    *,
    limit: int = 3,
) -> list[str]:
    designed = _designed_disturbance_response(response)
    if designed.empty or "output_signal" not in designed:
        return []
    selected = designed.loc[designed["input_signal"].astype(str).eq(str(input_signal))].copy()
    if selected.empty:
        return []
    selected["_valid"] = _boolean_series(selected, "valid_bin")
    valid_counts = selected.groupby("output_signal", sort=True)["_valid"].sum()
    priority = {name: index for index, name in enumerate(_BODE_OUTPUT_PRIORITY)}
    candidates = [
        str(name)
        for name, count in valid_counts.items()
        if int(count) > 0 and str(name) in _BODE_OUTPUT_LABELS
    ]
    candidates.sort(
        key=lambda name: (
            priority.get(name, len(priority)),
            -int(valid_counts.get(name, 0)),
            name,
        )
    )
    return candidates[: max(1, int(limit))]


def _regime_compatible_mask(frame: pd.DataFrame) -> pd.Series:
    """Return tested-amplitude regime compatibility, never a locality proof."""

    if "tested_amplitude_regime_trace_compatible" in frame:
        return _boolean_series(frame, "tested_amplitude_regime_trace_compatible")
    if "small_signal_local_claim" in frame:
        return _boolean_series(frame, "small_signal_local_claim")
    if "regime_compatible_for_local_claim" in frame:
        return _boolean_series(frame, "regime_compatible_for_local_claim")
    if "response_regime_scope" in frame:
        return frame["response_regime_scope"].astype(str).isin(
            {
                "local_fixed_supervisory_regime_trace",
                "local_operating_condition_without_supervisory_regime",
                "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified",
                "tested_amplitude_no_supervisory_regime_active_set_unverified",
            }
        )
    return pd.Series(False, index=frame.index, dtype=bool)


def _plot_excitation_response(output_root: Path, trajectories: pd.DataFrame, plt: Any) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    selected_input: str | None = None
    selected_condition: str | None = None
    if trajectories.empty:
        for axis in axes:
            axis.text(0.5, 0.5, "Étape conçue non exécutée", ha="center", va="center")
    else:
        feedback_candidates = trajectories.loc[
            trajectories["policy"].eq("canonical_feedback")
        ].copy()
        candidates = feedback_candidates.loc[
            feedback_candidates["condition"].eq("supplier_stress_capacity")
        ].copy()
        if candidates.empty:
            candidates = feedback_candidates
        if candidates.empty:
            candidates = trajectories.copy()
        preferred_inputs = (
            "supplier_lead_time_multiplier",
            "demand_multiplier",
            "supplier_availability_multiplier",
        )
        selected_input_candidate = next(
            (
                input_name
                for input_name in preferred_inputs
                if candidates["experiment_input_signal"].astype(str).eq(input_name).any()
            ),
            str(candidates.iloc[0]["experiment_input_signal"]),
        )
        first = candidates.loc[
            candidates["experiment_input_signal"]
            .astype(str)
            .eq(selected_input_candidate)
        ].iloc[0]
        selection = candidates.loc[
            candidates["condition"].astype(str).eq(str(first["condition"]))
            & candidates["policy"].astype(str).eq(str(first["policy"]))
            & candidates["experiment_input_signal"]
            .astype(str)
            .eq(str(first["experiment_input_signal"]))
        ].copy()
        selected_input = str(selection["experiment_input_signal"].iloc[0])
        selected_condition = str(selection["condition"].iloc[0])
        excitation_field = f"excitation_fraction__{selected_input}"
        if excitation_field not in selection:
            excitation_field = selected_input
        day = selection["day"].to_numpy(dtype=float)
        axes[0].plot(
            day,
            100.0 * selection[excitation_field],
            label=(
                "Délai fournisseur (fraction autour du point de fonctionnement)"
                if selected_input == "supplier_lead_time_multiplier"
                else selected_input
            ),
            lw=1.1,
            color="#2563eb",
        )
        axes[0].set_ylabel("Excitation [%]")
        axes[0].legend(ncol=3, fontsize=8)
        for field, label, color in (
            ("delta__probe_destination_arrivals_qty", "Δ arrivées ciblées", "#2563eb"),
            ("delta__probe_supplier_shipments_qty", "Δ expéditions ciblées", "#0f766e"),
            ("delta__target_production_qty", "Δ production article cible", "#7c3aed"),
        ):
            if field in selection:
                axes[1].plot(day, selection[field], label=label, lw=0.9, color=color)
        axes[1].set_ylabel("Δ flux [unités/j]")
        axes[1].legend(ncol=3, fontsize=8)
        for field, label, color in (
            ("delta__global_inventory_qty", "Δ stock", "#d97706"),
            ("delta__global_backlog_qty", "Δ backlog", "#be123c"),
        ):
            if field in selection:
                axes[2].plot(day, selection[field], label=label, lw=1.0, color=color)
        axes[2].set_ylabel("Δ état [unités]")
        axes[2].set_xlabel("Jour mesuré")
        axes[2].legend(ncol=2, fontsize=8)
        for axis, fields in (
            (
                axes[1],
                (
                    "delta__probe_destination_arrivals_qty",
                    "delta__probe_supplier_shipments_qty",
                    "delta__target_production_qty",
                ),
            ),
            (
                axes[2],
                ("delta__global_inventory_qty", "delta__global_backlog_qty"),
            ),
        ):
            parts = [
                np.abs(
                    pd.to_numeric(selection[field], errors="coerce")
                    .dropna()
                    .to_numpy(dtype=float)
                )
                for field in fields
                if field in selection
            ]
            if not parts:
                continue
            values = np.concatenate(parts)
            nonzero = values[np.isfinite(values) & (values > 0)]
            if nonzero.size:
                linear_threshold = max(float(np.median(nonzero)), 1.0)
                axis.set_yscale(
                    "symlog", linthresh=linear_threshold, linscale=1.0, base=10
                )
                axis.axhline(0.0, color="#64748b", lw=0.7)
                axis.text(
                    0.995,
                    0.04,
                    f"échelle sym-log · linéaire ±{linear_threshold:.0f}",
                    transform=axis.transAxes,
                    ha="right",
                    va="bottom",
                    fontsize=7,
                    color="#475569",
                )
    for axis in axes:
        axis.grid(alpha=0.25)
    input_clause = {
        "demand_multiplier": "seule la demande varie",
        "supplier_availability_multiplier": (
            "seule la disponibilité fournisseur varie"
        ),
        "supplier_lead_time_multiplier": "seul le délai fournisseur varie",
    }.get(selected_input or "", "l'entrée conçue varie")
    condition_label = {
        "supplier_stress_capacity": "condition fournisseur stressée",
        "nominal_capacity": "condition nominale",
    }.get(selected_condition or "", "condition conçue")
    fig.suptitle(
        f"Essais où {input_clause}, avec comparaison entrée-sortie — "
        f"{condition_label} (pics complets conservés)"
    )
    return _save(fig, output_root / "canonical_frequency_excitation_response.png", plt)


def _plot_bode(output_root: Path, response: pd.DataFrame, plt: Any) -> Path:
    selected_input = _select_bode_input(response)
    outputs = (
        _select_bode_outputs(response, selected_input)
        if selected_input is not None
        else []
    )
    if selected_input is None or not outputs:
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), squeeze=False)
        for axis in axes.flat:
            axis.text(
                0.5,
                0.5,
                "Aucune ligne physique numériquement valide",
                ha="center",
                va="center",
                color="#64748b",
            )
            axis.set_axis_off()
        fig.suptitle(
            "Réponses fréquentielles empiriques non publiables — "
            "aucun Bode principal sélectionné"
        )
        return _save(
            fig,
            output_root / "canonical_frequency_bode_frf.png",
            plt,
        )

    fig, axes = plt.subplots(
        len(outputs), 2, figsize=(13, 3.3 * len(outputs) + 2), sharex="col", squeeze=False
    )
    designed = _designed_disturbance_response(response)
    designed = designed.loc[
        designed["input_signal"].astype(str).eq(selected_input)
    ].copy()
    for row_index, output_signal in enumerate(outputs):
        subset = designed.loc[designed["output_signal"].eq(output_signal)] if not designed.empty else pd.DataFrame()
        grouped = subset.groupby(["condition", "policy"], sort=True) if not subset.empty else []
        for (condition, policy), group in grouped:
            group = group.sort_values("period_days")
            color, style = _line_style(str(policy))
            alpha = 1.0 if str(condition) == "supplier_stress_capacity" else 0.55
            valid_mask = _boolean_series(group, "valid_bin")
            compatible_mask = _regime_compatible_mask(group)
            compatible = group.loc[valid_mask & compatible_mask].copy()
            hybrid = group.loc[valid_mask & ~compatible_mask].copy()
            invalid_detected = group.loc[
                ~valid_mask
                & _boolean_series(group, "response_detected")
                & pd.to_numeric(group["elasticity_db"], errors="coerce").notna()
            ].copy()
            if not compatible.empty:
                axes[row_index, 0].plot(
                    compatible["period_days"], compatible["elasticity_db"],
                    linestyle=style, marker="o", ms=4, color=color, alpha=alpha,
                    label=f"{policy} — {condition} — compatible-régime",
                )
                axes[row_index, 1].plot(
                    compatible["period_days"], compatible["phase_deg"],
                    linestyle=style, marker="o", ms=4, color=color, alpha=alpha,
                    label=f"{policy} — {condition} — compatible-régime",
                )
            if not hybrid.empty:
                axes[row_index, 0].plot(
                    hybrid["period_days"], hybrid["elasticity_db"],
                    linestyle=":", marker="D", ms=4, color=color, alpha=alpha,
                    markerfacecolor="none",
                    label=f"{policy} — {condition} — hybride",
                )
                axes[row_index, 1].plot(
                    hybrid["period_days"], hybrid["phase_deg"],
                    linestyle=":", marker="D", ms=4, color=color, alpha=alpha,
                    markerfacecolor="none",
                    label=f"{policy} — {condition} — hybride",
                )
            if not invalid_detected.empty:
                axes[row_index, 0].scatter(
                    invalid_detected["period_days"], invalid_detected["elasticity_db"],
                    facecolors="none", edgecolors="#94a3b8", s=40, zorder=4,
                    label="réponse détectée, ligne non valide",
                )
                phase_invalid = invalid_detected.loc[
                    pd.to_numeric(invalid_detected["phase_deg"], errors="coerce").notna()
                ]
                axes[row_index, 1].scatter(
                    phase_invalid["period_days"], phase_invalid["phase_deg"],
                    facecolors="none", edgecolors="#94a3b8", s=40, zorder=4,
                )
        valid_mask = _boolean_series(subset, "valid_bin")
        compatible_count = int((valid_mask & _regime_compatible_mask(subset)).sum())
        hybrid_count = int((valid_mask & ~_regime_compatible_mask(subset)).sum())
        valid_count = compatible_count + hybrid_count
        detected_count = (
            int(_boolean_series(subset, "response_detected").sum())
            if not subset.empty and "response_detected" in subset
            else 0
        )
        if valid_count == 0:
            note = (
                f"0 ligne valide · {detected_count} réponse(s) détectée(s)"
                if detected_count
                else "Aucune réponse détectée"
            )
            for axis in axes[row_index, :]:
                axis.text(
                    0.02,
                    0.93,
                    note,
                    transform=axis.transAxes,
                    va="top",
                    fontsize=7.5,
                    color="#64748b",
                )
        else:
            axes[row_index, 0].text(
                0.02,
                0.93,
                f"{compatible_count} compatible-régime · {hybrid_count} hybride(s)",
                transform=axes[row_index, 0].transAxes,
                va="top",
                fontsize=7.5,
                color="#475569",
            )
        output_label = _BODE_OUTPUT_LABELS.get(output_signal, output_signal)
        axes[row_index, 0].set_ylabel(f"{output_label}\nGain relatif [dB]")
        axes[row_index, 1].set_ylabel("Phase [°]")
        axes[row_index, 0].grid(alpha=0.25)
        axes[row_index, 1].grid(alpha=0.25)
        axes[row_index, 0].set_xscale("log")
        axes[row_index, 1].set_xscale("log")
    axes[-1, 0].set_xlabel("Période [jours]")
    axes[-1, 1].set_xlabel("Période [jours]")
    handles: list[Any] = []
    labels: list[str] = []
    for axis in axes.flat:
        axis_handles, axis_labels = axis.get_legend_handles_labels()
        handles.extend(axis_handles)
        labels.extend(axis_labels)
    if handles:
        unique = dict(zip(labels, handles))
        fig.legend(
            unique.values(), unique.keys(), loc="upper center", ncol=2,
            fontsize=8, bbox_to_anchor=(0.5, 0.93),
        )
    input_label = _BODE_INPUT_LABELS.get(selected_input, selected_input)
    fig.suptitle(
        f"Réponses fréquentielles empiriques — {input_label} → sorties physiques\n"
        "● trace du régime superviseur compatible · ◇ réponse hybride · "
        "○ réponse détectée mais non valide",
        y=0.995,
    )
    return _save(
        fig,
        output_root / "canonical_frequency_bode_frf.png",
        plt,
        layout_rect=(0, 0.035, 1, 0.86),
    )


def _plot_coherence(output_root: Path, response: pd.DataFrame, plt: Any) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True, sharey=True)
    outputs = ["global_order_qty", "global_inventory_qty", "global_backlog_qty", "target_service_level"]
    designed = response.loc[
        response.get("study_kind", pd.Series(dtype=str)).eq("designed_closed_loop_disturbance_probe")
    ].copy() if not response.empty else pd.DataFrame()
    selected_condition = "supplier_stress_capacity"
    if not designed.empty:
        if not designed["condition"].eq(selected_condition).any():
            selected_condition = str(designed["condition"].iloc[0])
        designed = designed.loc[designed["condition"].eq(selected_condition)].copy()
    for axis, output_signal in zip(axes.flat, outputs, strict=True):
        subset = designed.loc[designed["output_signal"].eq(output_signal)] if not designed.empty else pd.DataFrame()
        grouped = subset.groupby(["input_signal", "policy"], sort=True) if not subset.empty else []
        for (input_signal, policy), group in grouped:
            color, style = _line_style(str(policy))
            marker = {"demand_multiplier": "o", "supplier_availability_multiplier": "s", "supplier_lead_time_multiplier": "^"}.get(str(input_signal), "o")
            group = group.sort_values("period_days")
            axis.plot(
                group["period_days"], group["coherence"], linestyle=style, marker=marker,
                ms=3, lw=0.9, color=color, alpha=0.75, label=f"{policy} / {input_signal}",
            )
        threshold = float(subset["coherence_threshold"].iloc[0]) if not subset.empty else 0.8
        axis.axhline(threshold, color="#be123c", lw=1.0, ls=":", label=f"seuil {threshold:.2f}")
        axis.set_xscale("log")
        axis.set_ylim(-0.03, 1.03)
        axis.set_title(output_signal)
        axis.grid(alpha=0.25)
    axes[1, 0].set_xlabel("Période [jours]")
    axes[1, 1].set_xlabel("Période [jours]")
    axes[0, 0].set_ylabel("Cohérence γ²")
    axes[1, 0].set_ylabel("Cohérence γ²")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        unique = dict(zip(labels, handles))
        fig.legend(
            unique.values(),
            unique.keys(),
            loc="center left",
            ncol=1,
            fontsize=7,
            bbox_to_anchor=(0.815, 0.50),
            frameon=False,
        )
    fig.suptitle(
        f"Qualité d'identification par ligne fréquentielle — {selected_condition}"
    )
    return _save(
        fig,
        output_root / "canonical_frequency_coherence.png",
        plt,
        layout_rect=(0, 0.035, 0.81, 0.94),
    )


def _plot_resonances(
    output_root: Path,
    native_spectra: pd.DataFrame,
    native_bands: pd.DataFrame,
    resonances: pd.DataFrame,
    plt: Any,
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    if not native_spectra.empty:
        selected = native_spectra.loc[
            native_spectra["source_run"].eq(native_spectra["source_run"].iloc[0])
            & native_spectra["output_signal"].isin(["global_demand_qty", "global_order_qty", "global_production_qty"])
            & native_spectra["period_days"].between(2.0, 400.0)
        ]
        for signal, group in selected.groupby("output_signal", sort=True):
            group = group.sort_values("period_days")
            axes[0].plot(group["period_days"], 10.0 * np.log10(np.maximum(group["output_psd_normalized"], 1e-30)), label=signal, lw=1.0)
        axes[0].set_xscale("log")
        axes[0].set_xlabel("Période [jours]")
        axes[0].set_ylabel("PSD normalisée [dB]")
        axes[0].legend(fontsize=8)
    else:
        axes[0].text(0.5, 0.5, "Spectres natifs non exécutés", ha="center", va="center")
    axes[0].set_title("Spectres natifs sur 5 ans — dominance, pas résonance prouvée")
    axes[0].grid(alpha=0.25)

    if not native_bands.empty:
        bands = native_bands.loc[
            native_bands["source_run"].eq(native_bands["source_run"].iloc[0])
            & native_bands["output_signal"].isin(["global_order_qty", "global_production_qty", "global_supplier_shipments_qty"])
        ].copy()
        pivot = bands.pivot(index="output_signal", columns="band", values="power_amplification_db")
        band_order = [
            "rapid_2_to_6_days",
            "weekly_6_to_10_days",
            "operational_10_to_35_days",
            "planning_35_to_120_days",
            "seasonal_120_to_400_days",
        ]
        pivot = pivot.reindex(columns=[name for name in band_order if name in pivot.columns])
        bound = max(20.0, float(np.nanmax(np.abs(pivot.to_numpy(dtype=float)))))
        image = axes[1].imshow(
            pivot.to_numpy(dtype=float), aspect="auto", cmap="RdBu_r", vmin=-bound, vmax=bound
        )
        axes[1].set_yticks(range(len(pivot.index)), pivot.index)
        axes[1].set_xticks(range(len(pivot.columns)), [str(value).replace("_", "\n") for value in pivot.columns], rotation=25, ha="right", fontsize=7)
        fig.colorbar(image, ax=axes[1], label="Amplification de puissance [dB]")
    else:
        axes[1].text(0.5, 0.5, "Bandes natives non exécutées", ha="center", va="center")
    axes[1].set_title("Bullwhip spectral par bande")
    fig.suptitle("Pics spectraux candidats et amplification de variabilité")
    return _save(fig, output_root / "canonical_frequency_resonances.png", plt)


def _plot_time_frequency(
    output_root: Path,
    trajectories: pd.DataFrame,
    plt: Any,
    controller_schema_version: str | None = None,
) -> Path:
    publication_terms = _feedback_publication_terms(controller_schema_version)
    fig, axis = plt.subplots(figsize=(13, 6))
    if trajectories.empty or "delta__global_order_qty" not in trajectories:
        axis.text(0.5, 0.5, "Trajectoires conçues non exécutées", ha="center", va="center")
    else:
        selection = trajectories.loc[
            trajectories["condition"].eq("supplier_stress_capacity")
            & trajectories["policy"].eq("canonical_feedback")
            & trajectories["experiment_input_signal"].eq("demand_multiplier")
        ]
        if selection.empty:
            selection = trajectories.iloc[: min(576, len(trajectories))]
        values = selection["delta__global_order_qty"].to_numpy(dtype=float)
        window_days = min(96, max(32, len(values) // 4))
        step = max(8, window_days // 4)
        window = np.hanning(window_days)
        spectra: list[np.ndarray] = []
        centers: list[float] = []
        for start in range(0, len(values) - window_days + 1, step):
            segment = values[start : start + window_days]
            transform = np.fft.rfft((segment - segment.mean()) * window)
            spectra.append(10.0 * np.log10(np.maximum(np.abs(transform) ** 2, 1e-30)))
            centers.append(float(selection["day"].iloc[start + window_days // 2]))
        if spectra:
            matrix = np.stack(spectra).T
            frequency = np.fft.rfftfreq(window_days, d=1.0)
            keep = (frequency > 0) & (frequency <= 0.25)
            image = axis.pcolormesh(centers, frequency[keep], matrix[keep], shading="auto", cmap="viridis")
            axis.set_ylabel("Fréquence [cycles/jour]")
            axis.set_xlabel("Jour mesuré")
            fig.colorbar(image, ax=axis, label="Puissance locale Δ commandes [dB]")
    axis.set_title(
        "Évolution du contenu fréquentiel des commandes — demande seule, "
        f"{publication_terms['time_frequency_context']}, fournisseur stressé"
    )
    return _save(fig, output_root / "canonical_frequency_time_frequency.png", plt)


def _plot_stability(
    output_root: Path,
    stability: pd.DataFrame,
    closed_loop_comparison: pd.DataFrame,
    plt: Any,
    controller_schema_version: str | None = None,
) -> Path:
    publication_terms = _feedback_publication_terms(controller_schema_version)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    selected = stability.loc[
        stability.get("study_kind", pd.Series(dtype=str)).eq(
            "designed_closed_loop_disturbance_probe"
        )
    ].copy() if not stability.empty else pd.DataFrame()
    if not selected.empty:
        selected["response_pattern_for_plot"] = selected.apply(
            _response_pattern, axis=1
        )
        pattern_order = [
            "no_measurable_response",
            "nonzero_repeatable_response",
            "interior_period_peak_transient_or_delay",
            "monotonic_growth_detected",
            "other_nonstationary_response",
        ]
        pattern_labels = {
            "no_measurable_response": "Pas de réponse mesurable",
            "nonzero_repeatable_response": "Non nulle et répétable",
            "interior_period_peak_transient_or_delay": "Pic intérieur / transitoire",
            "monotonic_growth_detected": "Croissance monotone",
            "other_nonstationary_response": "Autre non-stationnarité",
        }
        pattern_colors = {
            "no_measurable_response": "#cbd5e1",
            "nonzero_repeatable_response": "#0f766e",
            "interior_period_peak_transient_or_delay": "#d97706",
            "monotonic_growth_detected": "#be123c",
            "other_nonstationary_response": "#7c3aed",
        }
        counts = (
            selected.groupby(["input_signal", "response_pattern_for_plot"], sort=True)
            .size()
            .unstack(fill_value=0)
            .reindex(columns=pattern_order, fill_value=0)
        )
        x = np.arange(len(counts.index))
        bottom = np.zeros(len(counts.index), dtype=float)
        for pattern in pattern_order:
            values = counts[pattern].to_numpy(dtype=float)
            axes[0].bar(
                x,
                values,
                bottom=bottom,
                color=pattern_colors[pattern],
                label=pattern_labels[pattern],
            )
            bottom += values
        short_names = {
            "demand_multiplier": "Demande",
            "supplier_availability_multiplier": "Disponibilité\nfournisseur",
            "supplier_lead_time_multiplier": "Délai\nfournisseur",
        }
        axes[0].set_xticks(
            x,
            [short_names.get(str(value), str(value)) for value in counts.index],
            fontsize=8,
        )
        axes[0].legend(fontsize=7, loc="upper left")
    else:
        axes[0].text(0.5, 0.5, "Diagnostic non exécuté", ha="center", va="center")
    axes[0].set_ylabel("Nombre de diagnostics entrée-sortie")
    axes[0].set_title("Forme des réponses par excitation (diagnostic, pas preuve)")
    axes[0].grid(axis="y", alpha=0.25)

    reliable = closed_loop_comparison.loc[
        closed_loop_comparison.get("reliable_comparison", pd.Series(dtype=bool)).astype(bool)
    ].copy() if not closed_loop_comparison.empty else pd.DataFrame()
    attenuation_field = _comparison_column(
        reliable,
        "feedback_minus_mrp_attenuation_db",
        "v2_minus_mrp_attenuation_db",
    )
    if not reliable.empty and attenuation_field is not None:
        groups = (
            reliable.groupby("output_signal")[attenuation_field]
            .median()
            .sort_values()
        )
        output_labels = {
            "probe_destination_arrivals_qty": "Arrivées probe",
        }
        labels = [output_labels.get(str(value), str(value)) for value in groups.index]
        positions = np.arange(len(groups), dtype=float)
        axes[1].scatter(
            groups.values,
            positions,
            color=["#0f766e" if value < 0 else "#be123c" for value in groups],
            s=55,
            zorder=3,
        )
        axes[1].set_yticks(positions, labels)
        axes[1].axvline(0.0, color="#334155", lw=1.0)
        for position, value in zip(positions, groups.values, strict=True):
            axes[1].text(
                float(value),
                position + 0.12,
                f"{float(value):+.4f} dB",
                va="bottom",
                ha="center",
                fontsize=8,
                color="#334155",
            )
        bound = max(0.10, 2.5 * float(np.nanmax(np.abs(groups.to_numpy(dtype=float)))))
        axes[1].set_xlim(-bound, bound)
        if len(reliable) == 1:
            interval_contains_zero = bool(
                reliable.get(
                    "zero_db_in_paired_interval",
                    pd.Series(False, index=reliable.index),
                ).fillna(False).astype(bool).iloc[0]
            )
            note = (
                "Un point fiable seulement : effet non concluant ; "
                + (
                    "l'intervalle apparié contient 0."
                    if interval_contains_zero
                    else "incertitude appariée requise."
                )
            )
            axes[1].text(
                0.02,
                0.04,
                note,
                transform=axes[1].transAxes,
                fontsize=7.5,
                color="#475569",
            )
    else:
        axes[1].text(0.5, 0.5, "Aucune comparaison cohérente", ha="center", va="center")
    axes[1].set_xlabel(
        f"{publication_terms['comparison'].replace('/', ' − ')} [dB] ; "
        "négatif = atténuation"
    )
    axes[1].set_title(
        f"Comparaison {publication_terms['comparison']} — n={len(reliable)}, "
        "statique et descriptive"
    )
    axes[1].grid(axis="x", alpha=0.25)
    margin_subject = (
        "marges classiques V2 non identifiables"
        if bool(publication_terms["legacy_v2"])
        else "marges classiques globales non identifiables"
    )
    fig.suptitle(
        f"Répétabilité des campagnes et écart {publication_terms['comparison']} "
        f"empirique — {margin_subject}"
    )
    return _save(fig, output_root / "canonical_frequency_stability.png", plt)


def write_frequency_figures(
    output_root: Path,
    *,
    native_spectra: pd.DataFrame,
    native_bands: pd.DataFrame,
    response: pd.DataFrame,
    closed_loop_comparison: pd.DataFrame,
    resonances: pd.DataFrame,
    stability: pd.DataFrame,
    trajectories: pd.DataFrame,
    controller_schema_version: str | None = None,
) -> list[Path]:
    """Write the six dashboard figures expected by the frequency pane."""

    plt = _import_plotting()
    root = Path(output_root)
    return [
        _plot_excitation_response(root, trajectories, plt),
        _plot_bode(root, response, plt),
        _plot_coherence(root, response, plt),
        _plot_resonances(root, native_spectra, native_bands, resonances, plt),
        _plot_time_frequency(
            root,
            trajectories,
            plt,
            controller_schema_version=controller_schema_version,
        ),
        _plot_stability(
            root,
            stability,
            closed_loop_comparison,
            plt,
            controller_schema_version=controller_schema_version,
        ),
    ]


__all__ = ["write_frequency_figures", "write_frequency_report"]
