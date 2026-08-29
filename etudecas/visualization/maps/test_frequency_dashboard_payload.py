import csv
import json
from pathlib import Path

from etudecas.visualization.maps.frequency_dashboard_payload import (
    FREQUENCY_DASHBOARD_SCHEMA_VERSION,
    build_frequency_dashboard_section,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _png_header(width: int = 320, height: int = 180) -> bytes:
    """Return enough of a PNG IHDR for payload dimension inspection."""

    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def _write_complete_package(
    root: Path,
    *,
    metadata_name: str = "canonical_frequency_protocol.json",
    global_stability_claimed: bool = False,
    controller_schema_version: str | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": "scan.canonical_frequency_protocol.v1",
        "sample_period_days": 1,
        "measured_days": 720,
        "frequency_band": {
            "minimum_cpd": 1 / 180,
            "maximum_cpd": 0.25,
        },
        "identification": {"coherence_threshold": 0.7},
        "scientific_claim": {
            "scope": "local_regime_dependent",
            "global_stability_claimed": global_stability_claimed,
        },
    }
    if controller_schema_version is not None:
        metadata["controller"] = {"schema_version": controller_schema_version}
    (root / metadata_name).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    feedback_policy = (
        "canonical_feedback"
        if controller_schema_version == "scan.canonical_state_feedback.v3"
        else "canonical_feedback_v2"
    )
    _write_csv(
        root / "canonical_frequency_response.csv",
        [
            {
                "policy": "mrp_reference",
                "regime": "NOMINAL",
                "input_signal": "demand_probe",
                "output_signal": "orders",
                "frequency_cpd": 0.05,
                "magnitude_db": 2.0,
                "phase_deg": -20.0,
                "coherence": 0.91,
                "valid_bin": "true",
                "small_signal_local_claim": "true",
            },
            {
                "policy": feedback_policy,
                "regime": "NOMINAL",
                "input_signal": "demand_probe",
                "output_signal": "orders",
                "frequency_cpd": 0.10,
                "magnitude_db": -1.0,
                "phase_deg": -35.0,
                "coherence": 0.82,
                "valid_bin": "false",
                "small_signal_local_claim": "false",
            },
        ],
    )
    _write_csv(
        root / "canonical_frequency_resonances.csv",
        [
            {
                "policy": "mrp_reference",
                "regime": "NOMINAL",
                "input_signal": "demand_probe",
                "output_signal": "orders",
                "peak_frequency_cpd": 0.05,
                "peak_period_days": 20,
                "peak_gain_db": 2.0,
                "peak_coherence": 0.91,
                "peak_classification": "designed_hybrid_line_peak",
            }
        ],
    )
    _write_csv(
        root / "canonical_frequency_stability.csv",
        [
            {
                "policy": feedback_policy,
                "regime": "NOMINAL",
                "spectral_radius": 0.83,
                "locally_stable": "true",
                "gain_margin_db": 8.2,
                "phase_margin_deg": 47,
                "repeatable_periodic_response": "true",
                "status": "bounded_repeatable_response_observed",
                "source_status": "period_to_period_growth_detected",
                "quality_status": "identified",
            }
        ],
    )
    _write_csv(
        root / "canonical_frequency_delays.csv",
        [
            {
                "condition": "nominal_capacity",
                "policy": feedback_policy,
                "input_signal": "supplier_lead_time_multiplier",
                "output_signal": "control_order_multiplier",
                "delay_days": 18.0,
                "weighted_r_squared": 0.84,
                "status": "local_phase_slope_estimated_not_transport_delay_proof",
            },
            {
                "condition": "nominal_capacity",
                "policy": feedback_policy,
                "input_signal": "demand_multiplier",
                "output_signal": "orders",
                "delay_days": "",
                "weighted_r_squared": "",
                "status": "not_identifiable",
            },
        ],
    )
    _write_csv(
        root / "canonical_frequency_closed_loop_comparison.csv",
        [
            {
                "reliable_comparison": "true",
                "dynamic_feedback_modulation_identified": "false",
                "v2_minus_mrp_attenuation_db": -0.04,
            },
            {
                "reliable_comparison": "false",
                "dynamic_feedback_modulation_identified": "true",
                "v2_minus_mrp_attenuation_db": 646.7,
            },
        ],
    )


def test_frequency_dashboard_is_unavailable_without_complete_contract(
    tmp_path: Path,
) -> None:
    missing = build_frequency_dashboard_section(None)
    incomplete = build_frequency_dashboard_section(tmp_path)

    assert missing == {
        "schema_version": FREQUENCY_DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": "frequency_results_not_provided",
        "html": "",
        "figure_count": 0,
        "metrics": {},
    }
    assert incomplete["available"] is False
    assert incomplete["status"] == "frequency_results_incomplete"
    assert incomplete["html"] == ""


def test_frequency_dashboard_embeds_tested_amplitude_evidence_and_curated_figures(
    tmp_path: Path,
) -> None:
    _write_complete_package(tmp_path)
    for figure_name in (
        "canonical_frequency_excitation_response.png",
        "canonical_frequency_bode_frf.png",
        "canonical_frequency_coherence.png",
        "canonical_frequency_resonances.png",
        "canonical_frequency_time_frequency.png",
        "canonical_frequency_stability.png",
    ):
        (tmp_path / figure_name).write_bytes(_png_header())

    payload = build_frequency_dashboard_section(tmp_path)

    assert payload["available"] is True
    assert payload["status"] == "ready"
    assert payload["figure_count"] == 6
    assert payload["metrics"]["response_row_count"] == 2
    assert payload["metrics"]["valid_frequency_bin_count"] == 1
    assert payload["metrics"]["coherence_threshold_pass_bin_count"] == 2
    assert payload["metrics"]["local_small_signal_bin_count"] == 0
    assert payload["metrics"]["local_small_signal_derivative_bin_count"] == 0
    assert payload["metrics"]["tested_amplitude_regime_compatible_bin_count"] == 1
    assert payload["metrics"]["eligible_frequency_bin_count"] == 2
    assert payload["metrics"]["identified_phase_slope_count"] == 1
    assert payload["metrics"]["delay_diagnostic_row_count"] == 2
    assert payload["metrics"]["probed_frequency_band_cpd"] == {
        "minimum": 1 / 180,
        "maximum": 0.25,
    }
    assert payload["metrics"]["numerically_valid_frequency_support_cpd"] == {
        "minimum": 0.05,
        "maximum": 0.05,
    }
    assert payload["metrics"]["regime_compatible_frequency_support_cpd"] == {
        "minimum": 0.05,
        "maximum": 0.05,
    }
    assert payload["metrics"]["closed_loop_comparison_row_count"] == 2
    assert payload["metrics"]["reliable_closed_loop_comparison_count"] == 1
    assert payload["metrics"]["dynamic_reliable_closed_loop_comparison_count"] == 0
    assert payload["metrics"]["no_measurable_response_count"] == 0
    assert payload["metrics"]["nonzero_repeatable_response_count"] == 1
    assert payload["metrics"]["period_to_period_growth_count"] == 1
    assert payload["metrics"]["claim_scope"] == (
        "empirical_tested_amplitude_regime_conditioned_active_set_unverified"
    )
    assert payload["metrics"]["global_stability_claimed"] is False
    assert payload["metrics"]["source_claim_conflict"] is False
    assert "ni une réponse locale linéaire, ni une preuve de stabilité globale" in payload["html"]
    assert "global_stability_claimed" not in payload["html"]
    assert "empirical_tested_amplitude" not in payload["html"]
    assert "Fréquences testées" in payload["html"]
    assert "Fréquences avec réponse exploitable" in payload["html"]
    assert "Même succession de régimes" in payload["html"]
    assert "Réponses non nulles répétables" in payload["html"]
    assert "Retards temporels estimables" in payload["html"]
    assert "aucun délai physique de transport identifié" in payload["html"]
    assert "Lien entrée-sortie au-dessus du seuil" in payload["html"]
    assert "1 / 2" in payload["html"]
    assert "-0.040 dB" in payload["html"]
    assert "Comparaison V2/MRP" in payload["html"]
    assert "commandes V2" in payload["html"]
    assert payload["metrics"]["feedback_controller_schema_version"] == (
        "scan.canonical_state_feedback.v2"
    )
    assert "646.7" not in payload["html"]
    assert "pic concu hybride (changement de regime)" in payload["html"]
    assert "data:image/png;base64," in payload["html"]
    assert 'loading="eager"' in payload["html"]
    assert 'decoding="async"' in payload["html"]
    assert 'width="320" height="180"' in payload["html"]
    assert 'loading="lazy"' not in payload["html"]
    assert payload["html"].index("Figures frequentielles") < payload[
        "html"
    ].index("Fréquences où l amplification est forte")
    assert str(tmp_path) not in payload["html"]


def test_frequency_dashboard_uses_v3_feedback_labels_and_neutral_column(
    tmp_path: Path,
) -> None:
    _write_complete_package(
        tmp_path,
        controller_schema_version="scan.canonical_state_feedback.v3",
    )
    _write_csv(
        tmp_path / "canonical_frequency_closed_loop_comparison.csv",
        [
            {
                "reliable_comparison": "true",
                "dynamic_feedback_modulation_identified": "true",
                "feedback_minus_mrp_attenuation_db": -1.25,
            },
            {
                "reliable_comparison": "false",
                "dynamic_feedback_modulation_identified": "false",
                "feedback_minus_mrp_attenuation_db": 646.7,
            },
        ],
    )
    for figure_name in (
        "canonical_frequency_time_frequency.png",
        "canonical_frequency_stability.png",
    ):
        (tmp_path / figure_name).write_bytes(_png_header())

    payload = build_frequency_dashboard_section(tmp_path)

    assert payload["schema_version"] == FREQUENCY_DASHBOARD_SCHEMA_VERSION
    assert payload["metrics"]["feedback_controller_schema_version"] == (
        "scan.canonical_state_feedback.v3"
    )
    assert payload["metrics"]["feedback_publication_label"] == (
        "régulation adaptative V3"
    )
    assert "Comparaison feedback/MRP" in payload["html"]
    assert "commandes de la régulation adaptative V3" in payload["html"]
    assert "la régulation adaptative V3 et le MRP" in payload["html"]
    assert "-1.250 dB" in payload["html"]
    assert "646.7" not in payload["html"]
    assert "Comparaison V2/MRP" not in payload["html"]
    assert "commandes V2" not in payload["html"]


def test_frequency_dashboard_optionally_embeds_realized_lead_time_figure(
    tmp_path: Path,
) -> None:
    _write_complete_package(tmp_path)
    (tmp_path / "canonical_frequency_lead_time_realization.png").write_bytes(
        _png_header()
    )

    payload = build_frequency_dashboard_section(tmp_path)

    assert payload["available"] is True
    assert payload["figure_count"] == 1
    assert "Délai demandé et délai réellement appliqué" in payload["html"]
    assert "interdit de conclure à une réponse locale" in payload["html"]


def test_frequency_dashboard_discloses_table_truncation(tmp_path: Path) -> None:
    _write_complete_package(tmp_path)
    _write_csv(
        tmp_path / "canonical_frequency_resonances.csv",
        [
            {
                "policy": "mrp_reference",
                "regime": "NOMINAL",
                "input_signal": "demand_probe",
                "output_signal": f"orders_{index}",
                "peak_frequency_cpd": 0.05,
                "peak_period_days": 20,
                "peak_gain_db": 2.0,
                "peak_coherence": 0.91,
                "peak_classification": "designed_hybrid_line_peak",
            }
            for index in range(43)
        ],
    )
    _write_csv(
        tmp_path / "canonical_frequency_stability.csv",
        [
            {
                "policy": "canonical_feedback_v2",
                "regime": "NOMINAL",
                "input_signal": "demand_multiplier",
                "output_signal": f"orders_{index}",
                "repeatable_periodic_response": "true",
                "status": "bounded_repeatable_response_observed",
                "quality_status": "diagnostic_only",
            }
            for index in range(45)
        ],
    )

    payload = build_frequency_dashboard_section(tmp_path)

    assert "Affichage limité aux 40 premières lignes sur 43" in payload["html"]
    assert "Affichage limité aux 40 premières lignes sur 45" in payload["html"]
    assert payload["html"].count("orders_42") == 0
    assert payload["html"].count("orders_39") == 2


def test_frequency_dashboard_accepts_manifest_name_and_refuses_global_claim(
    tmp_path: Path,
) -> None:
    _write_complete_package(
        tmp_path,
        metadata_name="canonical_frequency_manifest.json",
        global_stability_claimed=True,
    )

    payload = build_frequency_dashboard_section(tmp_path)

    assert payload["available"] is True
    assert payload["metrics"]["metadata_file"] == ("canonical_frequency_manifest.json")
    assert payload["metrics"]["source_global_stability_claimed"] is True
    assert payload["metrics"]["source_claim_conflict"] is True
    assert payload["metrics"]["global_stability_claimed"] is False
    assert "Le paquet source indiquait une stabilité globale" in payload["html"]
    assert "cette vue ne retient pas cette conclusion" in payload["html"]
