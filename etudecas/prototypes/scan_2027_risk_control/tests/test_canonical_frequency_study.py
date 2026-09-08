from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import canonical_frequency_study as study
from etudecas.prototypes.scan_2027_risk_control.frequency_analysis import (
    FrequencyAnalysisError,
    estimate_group_delay,
    extract_frequency_signals,
    native_band_amplification,
    normalized_multisine,
    paired_segment_growth,
    periodic_frf,
    periodic_residual_energy,
    validate_orthogonal_bins,
    welch_native_spectra,
)
from etudecas.prototypes.scan_2027_risk_control import frequency_reporting
from etudecas.prototypes.scan_2027_risk_control.frequency_reporting import write_frequency_report
from etudecas.simulation.engine.control_probe import load_control_probe_schedule


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "canonical_frequency_study_config.json"
)
CLOSED_LOOP_ACTUATOR_CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "canonical_frequency_v3_closed_loop_actuator_pilot_config.json"
)


@pytest.mark.parametrize(
    ("schema_version", "expected_flag", "expected_kind"),
    [
        (
            study.V2_CONTROL_POLICY_SCHEMA_VERSION,
            study.V2_CONTROL_FLAG,
            "hybrid_supervisory_state_feedback_v2",
        ),
        (
            study.V3_CONTROL_POLICY_SCHEMA_VERSION,
            study.V3_CONTROL_FLAG,
            "hybrid_supervisory_continuous_state_feedback_v3",
        ),
    ],
)
def test_control_policy_interface_is_selected_from_explicit_schema(
    tmp_path: Path,
    schema_version: str,
    expected_flag: str,
    expected_kind: str,
) -> None:
    policy_path = tmp_path / "control_policy.json"
    policy_path.write_text(
        json.dumps({"schema_version": schema_version}),
        encoding="utf-8",
    )

    selected_schema, selected_flag, selected_kind = (
        study._control_policy_interface(policy_path)
    )

    assert selected_schema == schema_version
    assert selected_flag == expected_flag
    assert selected_kind == expected_kind


@pytest.mark.parametrize("schema_version", [None, "scan.canonical_state_feedback.v4"])
def test_control_policy_interface_rejects_missing_or_unknown_schema(
    tmp_path: Path,
    schema_version: str | None,
) -> None:
    policy_path = tmp_path / "control_policy.json"
    policy_path.write_text(
        json.dumps({"schema_version": schema_version}),
        encoding="utf-8",
    )

    with pytest.raises(
        study.CanonicalFrequencyContractError,
        match="schema_version.*supported",
    ):
        study._control_policy_interface(policy_path)


def test_historical_frequency_config_keeps_exact_v2_interface() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    policy_path = study._resolve_path(
        payload["campaign"]["control_policy_json"],
        repo_root=study.REPO_ROOT,
        relative_to=CONFIG_PATH.parent,
    )

    selected_schema, selected_flag, selected_kind = (
        study._control_policy_interface(policy_path)
    )

    assert selected_schema == study.V2_CONTROL_POLICY_SCHEMA_VERSION
    assert selected_flag == "--control-policy-v2-json"
    assert selected_kind == "hybrid_supervisory_state_feedback_v2"


def test_historical_actuator_probe_defaults_to_open_loop_schedule() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    normalized = study.validate_frequency_config(payload)

    assert normalized["actuator_application_mode"] == (
        study.ACTUATOR_OPEN_LOOP_SCHEDULE
    )
    assert normalized["actuator_condition_name"] == "nominal_capacity"


def test_v3_closed_loop_actuator_pilot_is_slow_separate_and_non_claiming() -> None:
    payload = json.loads(
        CLOSED_LOOP_ACTUATOR_CONFIG_PATH.read_text(encoding="utf-8")
    )

    normalized = study.validate_frequency_config(payload)

    assert normalized["actuator_application_mode"] == (
        study.ACTUATOR_POST_FEEDBACK_ADDITIVE
    )
    assert normalized["actuator_condition_name"] == "supplier_stress_capacity"
    assert [condition["name"] for condition in normalized["conditions"]] == [
        "supplier_stress_capacity"
    ]
    assert normalized["period_days"] == 196
    assert normalized["period_days"] % 14 == 0
    assert normalized["measured_periods"] == 6
    assert normalized["actuator_peak_fraction"] == pytest.approx(0.0025)
    assert max(
        value
        for values in normalized["actuator_bins"].values()
        for value in values
    ) <= 13
    assert payload["claims"]["small_signal_local_derivative_claimed"] is False
    assert payload["claims"]["local_stability_proven"] is False


def test_frequency_config_accepts_one_targeted_operating_condition() -> None:
    payload = json.loads(
        CLOSED_LOOP_ACTUATOR_CONFIG_PATH.read_text(encoding="utf-8")
    )

    normalized = study.validate_frequency_config(payload)

    assert len(normalized["conditions"]) == 1
    assert normalized["conditions"][0]["name"] == "supplier_stress_capacity"

    payload["operating_conditions"] = []
    with pytest.raises(
        study.CanonicalFrequencyContractError,
        match="at least one condition",
    ):
        study.validate_frequency_config(payload)


def test_closed_loop_actuator_probe_rejects_fast_bins_and_unknown_condition() -> None:
    payload = json.loads(
        CLOSED_LOOP_ACTUATOR_CONFIG_PATH.read_text(encoding="utf-8")
    )
    payload["actuator_probe"]["input_bins"]["order_multiplier"][-1] = 15
    with pytest.raises(study.CanonicalFrequencyContractError, match="bins <= 13"):
        study.validate_frequency_config(payload)

    payload = json.loads(
        CLOSED_LOOP_ACTUATOR_CONFIG_PATH.read_text(encoding="utf-8")
    )
    payload["actuator_probe"]["baseline_condition"] = "missing_condition"
    with pytest.raises(
        study.CanonicalFrequencyContractError,
        match="baseline_condition",
    ):
        study.validate_frequency_config(payload)


def test_frequency_config_defaults_to_all_historical_siso_inputs() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert "enabled_input_signals" not in payload["identification"]

    normalized = study.validate_frequency_config(payload)

    assert normalized["enabled_input_signals"] == tuple(
        payload["identification"]["input_bins"]
    )
    assert set(normalized["enabled_input_signals"]) == set(
        study.DESIGNED_INPUT_SIGNALS
    )


def test_frequency_config_accepts_targeted_lead_time_campaign() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["identification"]["enabled_input_signals"] = [
        "supplier_lead_time_multiplier"
    ]

    normalized = study.validate_frequency_config(payload)

    assert normalized["enabled_input_signals"] == (
        "supplier_lead_time_multiplier",
    )
    # All three signal/bin definitions remain available to the hard-coded
    # schedule and trajectory constructors.
    assert set(normalized["input_bins"]) == set(study.DESIGNED_INPUT_SIGNALS)


@pytest.mark.parametrize(
    "enabled",
    (
        None,
        [],
        "supplier_lead_time_multiplier",
        [""],
        [1],
        ["unknown_multiplier"],
        ["supplier_lead_time_multiplier", "supplier_lead_time_multiplier"],
    ),
)
def test_frequency_config_rejects_invalid_enabled_input_subsets(
    enabled: object,
) -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["identification"]["enabled_input_signals"] = enabled

    with pytest.raises(
        study.CanonicalFrequencyContractError,
        match="enabled_input_signals",
    ):
        study.validate_frequency_config(payload)


def test_inactive_lead_input_does_not_apply_its_phase_bound() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["identification"]["enabled_input_signals"] = ["demand_multiplier"]
    payload["supplier_probe"]["nominal_lead_time_days"] = 60.0

    normalized = study.validate_frequency_config(payload)

    assert normalized["enabled_input_signals"] == ("demand_multiplier",)
    assert normalized["require_unaliased_supplier_delay"] is True


def test_frequency_config_is_strict_about_tested_amplitude_scope() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    normalized = study.validate_frequency_config(payload)

    assert normalized["period_days"] == 196
    assert normalized["measured_periods"] >= 4
    assert normalized["warmup_days"] == 60
    assert normalized["period_days"] % 14 == 0
    assert all(
        value % 2 == 1
        for values in normalized["input_bins"].values()
        for value in values
    )
    assert normalized["coherence_threshold"] >= 0.8
    assert normalized["days"] % normalized["period_days"] == 0
    assert normalized["require_unaliased_supplier_delay"] is True
    assert (
        normalized["probe"]["nominal_lead_time_days"]
        * max(
            condition["supplier_lead_time_baseline"]
            for condition in normalized["conditions"]
        )
        < normalized["supplier_delay_phase_unwrap_bound_days"]
    )
    assert payload["claims"]["global_stability_claimed"] is False
    assert payload["claims"]["industrial_validation_claimed"] is False
    assert payload["claims"]["designed_response_scope"] == (
        study.DESIGNED_RESPONSE_SCOPE
    )
    assert payload["claims"]["small_signal_local_derivative_claimed"] is False
    assert payload["claims"]["amplitude_sweep_verified"] is False
    assert payload["claims"]["active_set_invariance_verified"] is False
    assert payload["actuator_probe"]["response_scope"] == (
        study.ACTUATOR_RESPONSE_SCOPE
    )
    assert normalized["designed_response_scope"] == study.DESIGNED_RESPONSE_SCOPE
    assert normalized["actuator_response_scope"] == study.ACTUATOR_RESPONSE_SCOPE
    for name, bins in normalized["input_bins"].items():
        validate_orthogonal_bins({name: bins}, normalized["period_days"])

    invalid = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    invalid["claims"]["global_stability_claimed"] = True
    with pytest.raises(study.CanonicalFrequencyContractError, match="global_stability"):
        study.validate_frequency_config(invalid)

    false_locality = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    false_locality["claims"]["small_signal_local_derivative_claimed"] = True
    with pytest.raises(
        study.CanonicalFrequencyContractError,
        match="small_signal_local_derivative_claimed",
    ):
        study.validate_frequency_config(false_locality)

    ambiguous_scope = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    ambiguous_scope["claims"]["designed_response_scope"] = (
        "local_small_signal_operating_condition_dependent"
    )
    with pytest.raises(
        study.CanonicalFrequencyContractError,
        match="designed_response_scope",
    ):
        study.validate_frequency_config(ambiguous_scope)

    invalid_period = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    invalid_period["identification"]["period_days"] = 335
    with pytest.raises(study.CanonicalFrequencyContractError, match="multiple of 14"):
        study.validate_frequency_config(invalid_period)

    aliased = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    aliased["supplier_probe"]["nominal_lead_time_days"] = 60.0
    with pytest.raises(study.CanonicalFrequencyContractError, match="phase-unwrapping"):
        study.validate_frequency_config(aliased)

    nonuniform_alias = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    nonuniform_alias["identification"]["input_bins"][
        "supplier_lead_time_multiplier"
    ] = [1, 3, 9, 11]
    with pytest.raises(study.CanonicalFrequencyContractError, match="phase-unwrapping"):
        study.validate_frequency_config(nonuniform_alias)

    contaminated = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    contaminated["campaign"]["engine_args"].extend(
        ["--demand-perturbation-csv", "unexpected.csv"]
    )
    with pytest.raises(study.CanonicalFrequencyContractError, match="managed flags"):
        study.validate_frequency_config(contaminated)

    probe_override = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    probe_override["campaign"]["engine_args"].extend(
        ["--control-probe-schedule-csv", "unexpected.csv"]
    )
    with pytest.raises(study.CanonicalFrequencyContractError, match="managed flags"):
        study.validate_frequency_config(probe_override)

    for managed_flag in (study.V2_CONTROL_FLAG, study.V3_CONTROL_FLAG):
        versioned_override = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        versioned_override["campaign"]["engine_args"].extend(
            [managed_flag, "unexpected.json"]
        )
        with pytest.raises(
            study.CanonicalFrequencyContractError,
            match="managed flags",
        ):
            study.validate_frequency_config(versioned_override)


def test_report_distinguishes_raw_coherence_from_fully_valid_lines(
    tmp_path: Path,
) -> None:
    response = pd.DataFrame(
        {
            "coherence": [0.92, 0.85, 0.40],
            "response_detected": [True, True, False],
            "valid_bin": [True, False, False],
            # The second row deliberately keeps the same supervisor trace but
            # is not numerically valid.  It must not be counted "among" the
            # valid rows in the report.
            "small_signal_local_claim": [True, True, False],
            "repetition_count": [9, 9, 9],
            "input_signal": ["demand_multiplier"] * 3,
        }
    )
    report_path = write_frequency_report(
        tmp_path,
        native_spectra=pd.DataFrame(),
        native_bands=pd.DataFrame(),
        response=response,
        closed_loop_comparison=pd.DataFrame(),
        resonances=pd.DataFrame(),
        stability=pd.DataFrame(),
        residual=pd.DataFrame(),
        regime_occupancy=pd.DataFrame(),
        normalized_config={
            "measured_periods": 10,
            "period_days": 196,
            "warmup_days": 60,
            "coherence_threshold": 0.8,
        },
    )

    report = report_path.read_text(encoding="utf-8")
    assert "Lignes avec cohérence brute ≥ 0.80 : 2" in report
    assert "Lignes numériquement valides après réponse détectée, cohérence, bornage et répétabilité : 1" in report
    assert "compatibles avec la même trace du régime superviseur à l'amplitude testée : 1" in report
    assert "rééchantillonnage des 9 période(s) retenue(s)" in report
    assert "Comparaison fréquentielle V2 / MRP" in report
    assert "Le V2 est un superviseur hybride" in report


def test_report_uses_feedback_fields_and_v3_publication_labels(
    tmp_path: Path,
) -> None:
    comparison = pd.DataFrame(
        [
            {
                "condition": "supplier_stress_capacity",
                "input_signal": "demand_multiplier",
                "output_signal": "global_order_qty",
                "reliable_comparison": True,
                "dynamic_feedback_modulation_identified": True,
                "feedback_minus_mrp_attenuation_db": -2.5,
                "attenuation_observed": True,
                "comparison_interpretation": "dynamic_feedback_modulation",
            }
        ]
    )
    delays = pd.DataFrame(
        [
            {
                "condition": "supplier_stress_capacity",
                "policy": "canonical_feedback",
                "input_signal": "demand_multiplier",
                "output_signal": "global_order_qty",
                "delay_days": np.nan,
                "descriptive_phase_slope_days": 4.25,
                "status": (
                    "tested_amplitude_active_set_unverified_"
                    "phase_slope_not_local_delay"
                ),
                "response_regime_scope": (
                    "tested_amplitude_fixed_supervisory_regime_trace_"
                    "active_set_unverified"
                ),
                "active_set_invariance_verified": False,
                "amplitude_sweep_verified": False,
            }
        ]
    )
    report_path = write_frequency_report(
        tmp_path,
        native_spectra=pd.DataFrame(),
        native_bands=pd.DataFrame(),
        response=pd.DataFrame(),
        closed_loop_comparison=comparison,
        resonances=pd.DataFrame(),
        stability=pd.DataFrame(),
        residual=pd.DataFrame(),
        regime_occupancy=pd.DataFrame(),
        normalized_config={
            "measured_periods": 10,
            "period_days": 196,
            "warmup_days": 60,
            "coherence_threshold": 0.8,
            "actuator_application_mode": "post_feedback_additive",
        },
        delays=delays,
        controller_schema_version=study.V3_CONTROL_POLICY_SCHEMA_VERSION,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "Comparaison fréquentielle feedback / MRP" in report
    assert "commandes de la régulation adaptative" in report
    assert "supervision hybride et une modulation continue dépendante de l'état" in report
    assert "Écart feedback/MRP médian sur points fiables : -2.50 dB" in report
    assert "Pentes conservées comme tendances descriptives" in report
    assert "balayage d'amplitude et invariance des contraintes actives non vérifiés" in report
    assert "parce que leurs lignes changent de régime" not in report
    assert "timing de transition hybride non local" not in report
    assert "V2/MRP" not in report
    assert "MRP/V2" not in report
    assert "commandes V2" not in report
    assert "Le V2" not in report
    assert "petite variation ajoutée après la commande calculée par le V3" in report
    assert "commande réellement appliquée sont tracées séparément" in report
    assert "overlay multiplicatif du MRP" not in report


def test_excitation_and_stability_plot_titles_follow_executed_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trajectories = pd.DataFrame(
        {
            "condition": ["nominal_capacity"] * 4,
            "policy": ["canonical_feedback"] * 4,
            "experiment_input_signal": ["demand_multiplier"] * 4,
            "day": [0, 1, 2, 3],
            "excitation_fraction__demand_multiplier": [0.0, 0.01, 0.0, -0.01],
            "delta__probe_destination_arrivals_qty": [0.0, 2.0, 0.0, -2.0],
            "delta__global_inventory_qty": [0.0, 1.0, 0.0, -1.0],
            "delta__global_backlog_qty": [0.0, 0.5, 0.0, -0.5],
        }
    )
    captured: list[str] = []

    def capture_save(fig, path, plt, **kwargs):
        captured.append(
            "\n".join(
                [
                    fig._suptitle.get_text() if fig._suptitle else "",
                    *(axis.get_title() for axis in fig.axes),
                    *(axis.get_xlabel() for axis in fig.axes),
                ]
            )
        )
        plt.close(fig)
        return path

    monkeypatch.setattr(frequency_reporting, "_save", capture_save)
    plt = frequency_reporting._import_plotting()
    frequency_reporting._plot_excitation_response(tmp_path, trajectories, plt)
    frequency_reporting._plot_stability(
        tmp_path,
        pd.DataFrame(),
        pd.DataFrame(),
        plt,
        controller_schema_version=study.V3_CONTROL_POLICY_SCHEMA_VERSION,
    )

    assert "seule la demande varie" in captured[0]
    assert "condition nominale" in captured[0]
    assert "seul le délai fournisseur varie" not in captured[0]
    assert "Comparaison feedback/MRP" in captured[1]
    assert "V2" not in captured[1]


def test_excitation_plot_prefers_stressed_feedback_operating_condition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows: list[dict[str, object]] = []
    for condition in ("nominal_capacity", "supplier_stress_capacity"):
        for day, excitation in enumerate((0.0, 0.01, 0.0, -0.01)):
            rows.append(
                {
                    "condition": condition,
                    "policy": "canonical_feedback",
                    "experiment_input_signal": "demand_multiplier",
                    "day": day,
                    "excitation_fraction__demand_multiplier": excitation,
                    "delta__probe_destination_arrivals_qty": 0.0,
                    "delta__global_inventory_qty": excitation,
                    "delta__global_backlog_qty": 0.0,
                }
            )
    captured: list[str] = []

    def capture_save(fig, path, plt, **kwargs):
        captured.append(fig._suptitle.get_text() if fig._suptitle else "")
        plt.close(fig)
        return path

    monkeypatch.setattr(frequency_reporting, "_save", capture_save)
    frequency_reporting._plot_excitation_response(
        tmp_path,
        pd.DataFrame(rows),
        frequency_reporting._import_plotting(),
    )

    assert "seule la demande varie" in captured[0]
    assert "condition fournisseur stressée" in captured[0]


def test_bode_prioritizes_valid_supplier_lead_and_separates_regime_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows: list[dict[str, object]] = []
    for output_signal in (
        "probe_destination_arrivals_qty",
        "probe_supplier_shipments_qty",
        "probe_supplier_stock_qty",
    ):
        for policy, compatible in (
            ("mrp_reference", True),
            ("canonical_feedback", False),
        ):
            rows.append(
                {
                    "study_kind": "designed_closed_loop_disturbance_probe",
                    "condition": "supplier_stress_capacity",
                    "policy": policy,
                    "input_signal": "supplier_lead_time_multiplier",
                    "output_signal": output_signal,
                    "period_days": 65.0,
                    "elasticity_db": 1.0,
                    "phase_deg": 20.0,
                    "valid_bin": True,
                    "response_detected": True,
                    "small_signal_local_claim": compatible,
                    "response_regime_scope": (
                        "local_fixed_supervisory_regime_trace"
                        if compatible
                        else "hybrid_regime_switching_amplitude_conditioned"
                    ),
                }
            )
    rows.append(
        {
            "study_kind": "designed_closed_loop_disturbance_probe",
            "condition": "supplier_stress_capacity",
            "policy": "mrp_reference",
            "input_signal": "demand_multiplier",
            "output_signal": "global_order_qty",
            "period_days": 28.0,
            "elasticity_db": 3.0,
            "phase_deg": 10.0,
            "valid_bin": False,
            "response_detected": True,
            "small_signal_local_claim": False,
            "response_regime_scope": "hybrid_regime_switching_amplitude_conditioned",
        }
    )
    response = pd.DataFrame(rows)

    assert frequency_reporting._select_bode_input(response) == (
        "supplier_lead_time_multiplier"
    )
    assert frequency_reporting._select_bode_outputs(
        response, "supplier_lead_time_multiplier"
    ) == [
        "probe_destination_arrivals_qty",
        "probe_supplier_shipments_qty",
        "probe_supplier_stock_qty",
    ]

    captured: dict[str, object] = {}

    def capture_save(fig, path, plt, **kwargs):
        captured["title"] = fig._suptitle.get_text()
        labels = []
        for axis in fig.axes:
            labels.extend(axis.get_legend_handles_labels()[1])
        captured["labels"] = labels
        plt.close(fig)
        return path

    monkeypatch.setattr(frequency_reporting, "_save", capture_save)
    plt = frequency_reporting._import_plotting()
    frequency_reporting._plot_bode(tmp_path, response, plt)

    assert "délai fournisseur → sorties physiques" in str(captured["title"])
    assert "demande →" not in str(captured["title"])
    assert any("compatible-régime" in label for label in captured["labels"])
    assert any("hybride" in label for label in captured["labels"])


def test_bode_does_not_promote_an_all_invalid_demand_probe() -> None:
    response = pd.DataFrame(
        {
            "study_kind": ["designed_closed_loop_disturbance_probe"],
            "condition": ["nominal_capacity"],
            "policy": ["mrp_reference"],
            "input_signal": ["demand_multiplier"],
            "output_signal": ["global_order_qty"],
            "valid_bin": [False],
            "response_detected": [True],
        }
    )

    assert frequency_reporting._select_bode_input(response) is None


def test_regime_trace_compatibility_is_not_local_derivative_evidence() -> None:
    fixed = study._regime_pair_metadata(
        study.canonical.FEEDBACK_POLICY,
        tuple((day, "SUPPLIER_STRESS") for day in range(8)),
        tuple((day, "SUPPLIER_STRESS") for day in range(8)),
    )
    switched = study._regime_pair_metadata(
        study.canonical.FEEDBACK_POLICY,
        tuple((day, "NOMINAL") for day in range(8)),
        ((0, "NOMINAL"),)
        + tuple((day, "POST_CRISIS_OVERSTOCK") for day in range(1, 8)),
    )
    misaligned = study._regime_pair_metadata(
        study.canonical.FEEDBACK_POLICY,
        tuple((day, "SUPPLIER_STRESS") for day in range(8)),
        tuple((day + 1, "SUPPLIER_STRESS") for day in range(8)),
    )
    reference = study._regime_pair_metadata(
        study.canonical.REFERENCE_POLICY,
        (),
        (),
    )

    assert fixed["regime_compatible_for_local_claim"] is True
    assert fixed["regime_compatible_for_local_claim_semantics"] == (
        study.LEGACY_REGIME_COMPATIBILITY_SEMANTICS
    )
    assert fixed["tested_amplitude_regime_trace_compatible"] is True
    assert fixed["amplitude_sweep_verified"] is False
    assert fixed["active_set_invariance_verified"] is False
    assert fixed["zero_amplitude_local_derivative_claimed"] is False
    assert fixed["locality_evidence_scope"] == (
        study.TESTED_AMPLITUDE_LOCALITY_SCOPE
    )
    assert fixed["response_regime_scope"] == (
        "tested_amplitude_fixed_supervisory_regime_trace_active_set_unverified"
    )
    assert fixed["regime_trace_mismatch_days"] == 0
    assert switched["regime_compatible_for_local_claim"] is False
    assert switched["tested_amplitude_regime_trace_compatible"] is False
    assert switched["regime_trace_mismatch_days"] == 7
    assert switched["response_regime_scope"] == (
        "tested_amplitude_hybrid_regime_switching_active_set_unverified"
    )
    assert misaligned["regime_compatible_for_local_claim"] is False
    assert misaligned["excited_regime_day_grid_valid"] is False
    assert reference["regime_compatible_for_local_claim"] is True
    assert reference["tested_amplitude_regime_trace_compatible"] is True
    assert reference["zero_amplitude_local_derivative_claimed"] is False
    assert reference["response_regime_scope"] == (
        "tested_amplitude_no_supervisory_regime_active_set_unverified"
    )


def test_unchanged_regime_trace_keeps_historical_field_but_not_local_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    trace = tuple((day, "SUPPLIER_STRESS") for day in range(8))
    monkeypatch.setattr(study, "_regime_trace", lambda _path: trace)
    response = pd.DataFrame(
        {
            "study_kind": ["designed_closed_loop_disturbance_probe"],
            "condition": ["supplier_stress_capacity"],
            "policy": [study.canonical.FEEDBACK_POLICY],
            "input_signal": ["supplier_lead_time_multiplier"],
            "output_signal": ["global_order_qty"],
            "valid_bin": [True],
            "response_kind": ["empirical_diagonal_harmonic_line_response"],
        }
    )
    condition_runs = {
        "supplier_stress_capacity": {
            "baseline_root": tmp_path / "baseline",
            "excited_roots": {
                "supplier_lead_time_multiplier": tmp_path / "excited"
            },
        }
    }

    annotated = study._annotate_response_regime_scope(
        response,
        condition_runs=condition_runs,
        seed=7,
    )
    row = annotated.iloc[0]

    assert bool(row["regime_compatible_for_local_claim"])
    assert bool(row["tested_amplitude_regime_trace_compatible"])
    assert bool(row["tested_amplitude_harmonic_response"])
    assert not bool(row["small_signal_local_claim"])
    assert not bool(row["amplitude_sweep_verified"])
    assert not bool(row["active_set_invariance_verified"])
    assert row["locality_evidence_scope"] == (
        study.TESTED_AMPLITUDE_LOCALITY_SCOPE
    )


def test_actuator_valid_bin_is_tested_amplitude_not_local_derivative() -> None:
    annotated = study._annotate_actuator_response_scope(
        pd.DataFrame({"valid_bin": [True, False]})
    )

    assert annotated["tested_amplitude_harmonic_response"].tolist() == [True, False]
    assert not annotated["small_signal_local_claim"].any()
    assert not annotated["amplitude_sweep_verified"].any()
    assert not annotated["active_set_invariance_verified"].any()
    assert set(annotated["locality_evidence_scope"]) == {
        study.TESTED_AMPLITUDE_LOCALITY_SCOPE
    }
    assert set(annotated["response_regime_scope"]) == {
        "tested_amplitude_open_loop_schedule_no_supervisory_regime_"
        "active_set_unverified"
    }


def test_closed_loop_actuator_valid_bin_is_not_promoted_to_plant_derivative() -> None:
    annotated = study._annotate_actuator_response_scope(
        pd.DataFrame({"valid_bin": [True]}),
        application_mode=study.ACTUATOR_POST_FEEDBACK_ADDITIVE,
    )

    assert bool(annotated.loc[0, "tested_amplitude_harmonic_response"])
    assert not bool(annotated.loc[0, "small_signal_local_claim"])
    assert annotated.loc[0, "response_regime_scope"] == (
        "tested_amplitude_post_feedback_additive_closed_loop_"
        "active_set_unverified"
    )


def test_actuator_phase_slope_passes_scope_gate_and_remains_descriptive() -> None:
    response = pd.DataFrame(
        {
            "study_kind": ["designed_open_loop_actuator_probe"] * 3,
            "condition": ["nominal_capacity"] * 3,
            "policy": ["mrp_reference_schedule_probe"] * 3,
            "input_signal": ["production_target_multiplier"] * 3,
            "output_signal": ["global_production_qty"] * 3,
            "valid_bin": [True] * 3,
            "small_signal_local_claim": [False] * 3,
            "amplitude_sweep_verified": [False] * 3,
            "active_set_invariance_verified": [False] * 3,
            "response_regime_scope": [
                "tested_amplitude_open_loop_schedule_no_supervisory_regime_"
                "active_set_unverified"
            ]
            * 3,
        }
    )
    delays = pd.DataFrame(
        {
            "study_kind": ["designed_open_loop_actuator_probe"],
            "condition": ["nominal_capacity"],
            "policy": ["mrp_reference_schedule_probe"],
            "input_signal": ["production_target_multiplier"],
            "output_signal": ["global_production_qty"],
            "delay_days": [5.0],
            "status": ["local_phase_slope_estimated_not_transport_delay_proof"],
        }
    )

    gated = study._annotate_delay_scope(response, delays).iloc[0]

    assert pd.isna(gated["delay_days"])
    assert gated["descriptive_phase_slope_days"] == pytest.approx(5.0)
    assert gated["supporting_valid_line_count"] == 3
    assert gated["supporting_local_line_count"] == 0
    assert gated["supporting_scope_verified_line_count"] == 0
    assert not bool(gated["local_phase_slope_identified"])
    assert not bool(gated["zero_amplitude_local_delay_claimed"])
    assert gated["phase_slope_scope"] == (
        "tested_amplitude_or_hybrid_descriptive_phase_trend"
    )
    assert gated["status"] == (
        "tested_amplitude_active_set_unverified_phase_slope_not_local_delay"
    )


def test_multisine_uses_only_requested_exact_dft_lines() -> None:
    bins = (1, 5, 11, 19)
    signal = normalized_multisine(96, bins, phase_seed=17)
    spectrum = np.fft.rfft(signal)
    present = {
        index
        for index, amplitude in enumerate(np.abs(spectrum))
        if amplitude > 1e-9
    }

    assert present == set(bins)
    assert abs(float(signal.mean())) < 1e-12
    assert np.max(np.abs(signal)) == pytest.approx(1.0)
    assert np.array_equal(signal, normalized_multisine(96, bins, phase_seed=17))


def test_orthogonal_bin_validation_rejects_alias_and_overlap() -> None:
    with pytest.raises(FrequencyAnalysisError, match="shared"):
        validate_orthogonal_bins({"a": [1, 3], "b": [3, 5]}, 32)
    with pytest.raises(FrequencyAnalysisError, match="invalid"):
        validate_orthogonal_bins({"a": [16]}, 32)


def test_periodic_frf_recovers_known_gain_phase_and_coherence() -> None:
    period = 96
    repetitions = 7
    delay_days = 3
    bins = (1, 5, 11, 19)
    one_period = 0.02 * normalized_multisine(period, bins, phase_seed=23)
    input_signal = np.tile(one_period, repetitions)
    output = 2.5 * np.roll(input_signal, delay_days)

    estimate = periodic_frf(
        input_signal,
        output,
        period_days=period,
        bins=bins,
        response_scale=1.0,
        bootstrap_samples=100,
        coherence_threshold=0.8,
    )

    assert estimate["valid_bin"].all()
    assert np.allclose(estimate["magnitude"], 2.5, atol=1e-10)
    assert np.allclose(estimate["coherence"], 1.0, atol=1e-12)
    expected_phase = np.angle(
        np.exp(-1j * 2.0 * np.pi * estimate["frequency_cycles_per_day"].to_numpy() * delay_days),
        deg=True,
    )
    assert np.allclose(estimate["phase_deg"], expected_phase, atol=1e-9)

    delay = estimate_group_delay(estimate)
    assert delay["status"].startswith("local_phase_slope")
    assert delay["delay_days"] == pytest.approx(delay_days, abs=1e-9)


def test_periodic_frf_rejects_partial_period_and_reports_zero_response() -> None:
    with pytest.raises(FrequencyAnalysisError, match="integer number"):
        periodic_frf(np.ones(100), np.ones(100), period_days=32, bins=[1])

    signal = np.tile(normalized_multisine(32, [1, 3], phase_seed=3), 4)
    estimate = periodic_frf(signal, np.zeros_like(signal), period_days=32, bins=[1, 3])
    assert np.allclose(estimate["magnitude"], 0.0)
    assert np.allclose(estimate["coherence"], 0.0)
    assert not estimate["response_detected"].any()
    assert not estimate["valid_bin"].any()
    assert estimate["phase_deg"].isna().all()


def test_residual_energy_separates_designed_and_unexcited_lines() -> None:
    period = 64
    designed = normalized_multisine(period, [2, 5], phase_seed=4)
    harmonic = 0.2 * np.sin(2 * np.pi * 9 * np.arange(period) / period)
    output = np.tile(designed + harmonic, 5)
    result = periodic_residual_energy(
        {"u": np.tile(designed, 5)},
        output,
        period_days=period,
        excited_bins={"u": [2, 5]},
    )

    assert result["residual_to_designed_energy_ratio"] > 0
    assert result["interpretation"] == "nonlinear_distortion_plus_noise_not_pure_thd"


def test_native_welch_is_observational_and_detects_bullwhip() -> None:
    day = np.arange(5 * 365, dtype=float)
    demand = 100.0 + 10.0 * np.sin(2 * np.pi * day / 7.0) + 5.0 * np.sin(2 * np.pi * day / 365.0)
    orders = 200.0 + 40.0 * np.sin(2 * np.pi * (day - 2) / 7.0) + 10.0 * np.sin(2 * np.pi * day / 365.0)
    spectra = welch_native_spectra(
        {"demand": demand, "orders": orders},
        input_signal="demand",
        segment_days=365,
        overlap_fraction=0.5,
    )
    bands = native_band_amplification(spectra)

    assert not spectra["causal_claimed"].any()
    weekly = bands.loc[
        bands["output_signal"].eq("orders")
        & bands["band"].eq("weekly_6_to_10_days")
    ].iloc[0]
    assert weekly["power_amplification_ratio"] > 1.0
    assert bool(weekly["bullwhip_amplification"])


def test_repeated_period_growth_is_diagnostic_not_stability_proof() -> None:
    base = np.sin(2 * np.pi * np.arange(32) / 32)
    values = np.concatenate([base, 1.05 * base, 1.2 * base])
    result = paired_segment_growth(values, period_days=32, tolerance=1.10)

    assert result["status"] == "period_to_period_growth_detected"
    assert result["local_stability_claimed"] is False
    assert result["global_stability_claimed"] is False


def test_repeated_period_decay_is_rejected_as_nonstationary() -> None:
    base = np.sin(2 * np.pi * np.arange(32) / 32)
    values = np.concatenate([99.0 * base, 10.0 * base, 9.0 * base, 8.0 * base])
    result = paired_segment_growth(
        values,
        period_days=32,
        discard_periods=1,
        tolerance=1.10,
    )

    assert result["status"] == "period_to_period_nonstationarity_detected"
    assert result["bounded_repeated_response"] is True
    assert result["repeatable_periodic_response"] is False
    assert result["max_to_min_rms_ratio"] == pytest.approx(1.25)


def test_repeated_period_zero_to_nonzero_ratio_is_finite_safe() -> None:
    base = np.sin(2 * np.pi * np.arange(32) / 32)
    values = np.concatenate([np.zeros(32), base, base])
    result = paired_segment_growth(values, period_days=32, tolerance=1.10)

    assert result["status"] == "period_to_period_growth_detected"
    assert result["max_to_min_rms_ratio"] is None
    assert result["max_to_min_rms_ratio_unbounded"] is True


def test_repeated_period_dc_state_drift_is_not_hidden_by_ac_centering() -> None:
    period_days = 16
    values = np.repeat([1.0, 2.0, 3.0, 4.0], period_days)
    result = paired_segment_growth(
        values,
        period_days=period_days,
        discard_periods=1,
        tolerance=1.10,
    )

    assert result["status"] == "period_to_period_growth_detected"
    assert result["repeatable_periodic_response"] is False
    assert result["period_mean_drift"] == pytest.approx(2.0)
    assert json.loads(result["period_mean_json"]) == pytest.approx([2.0, 3.0, 4.0])
    assert json.loads(result["period_ac_rms_json"]) == pytest.approx([0.0, 0.0, 0.0])
    assert json.loads(result["period_total_rms_json"]) == pytest.approx([2.0, 3.0, 4.0])
    assert json.loads(result["terminal_state_by_period_json"]) == pytest.approx(
        [2.0, 3.0, 4.0]
    )
    assert result["maximum_absolute_response"] == pytest.approx(4.0)


def test_repeated_period_small_interior_bump_is_not_promoted_to_material_peak() -> None:
    period_days = 8
    values = np.repeat([1.0, 1.15, 1.10], period_days)
    result = paired_segment_growth(
        values,
        period_days=period_days,
        tolerance=1.10,
    )

    assert result["repeatable_periodic_response"] is False
    assert result["interior_period_peak"] is False
    assert result["response_pattern"] == "other_nonstationary_response"


def test_actuator_schedule_excites_only_requested_siso_channel(tmp_path: Path) -> None:
    normalized = study.validate_frequency_config(
        json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    )
    schedule, signals = study._write_actuator_schedule(
        tmp_path / "schedule.csv",
        normalized=normalized,
        input_name="order_multiplier",
    )

    assert set(signals) == {"order_multiplier"}
    assert schedule["order_multiplier"].nunique() > 1
    assert set(schedule["safety_stock_multiplier"]) == {1.0}
    assert set(schedule["production_target_multiplier"]) == {1.0}
    assert set(schedule["capacity_multiplier"]) == {1.0}
    assert set(schedule["lead_time_adjustment_days"]) == {0}


def test_closed_loop_actuator_schedule_declares_only_one_probe_action(
    tmp_path: Path,
) -> None:
    normalized = study.validate_frequency_config(
        json.loads(
            CLOSED_LOOP_ACTUATOR_CONFIG_PATH.read_text(encoding="utf-8")
        )
    )
    schedule_path = tmp_path / "schedule.csv"

    schedule, signals = study._write_actuator_schedule(
        schedule_path,
        normalized=normalized,
        input_name="order_multiplier",
    )

    assert set(signals) == {"order_multiplier"}
    assert schedule["order_multiplier"].nunique() > 1
    assert set(schedule["safety_stock_multiplier"]) == {""}
    assert set(schedule["production_target_multiplier"]) == {""}
    loaded = pd.read_csv(schedule_path)
    assert loaded["safety_stock_multiplier"].isna().all()
    assert loaded["production_target_multiplier"].isna().all()
    probe_schedule = load_control_probe_schedule(schedule_path)
    assert all(
        tuple(row.effective) == ("order_multiplier",)
        for row in probe_schedule.rows
    )


def test_open_loop_actuator_runner_keeps_historical_schedule_interface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    normalized = study.validate_frequency_config(
        json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    )
    output_root = tmp_path / "output"
    (output_root / "inputs").mkdir(parents=True)
    captured: dict[str, list[str]] = {}

    def fake_run_engine(
        command: list[str], *, cwd: Path, result_dir: Path
    ) -> None:
        del cwd
        captured["command"] = command
        (result_dir / "summaries").mkdir(parents=True)
        (result_dir / "summaries" / "first_simulation_summary.json").write_text(
            json.dumps(
                {
                    "policy": {
                        "control_schedule": {
                            "enabled": True,
                            "scheduled_actions": 784,
                            "resolved_actions": 784,
                            "unresolved_actions": 0,
                            "action_ledger_rows": 784,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(study.canonical, "_run_engine", fake_run_engine)
    monkeypatch.setattr(
        study,
        "_actuator_realization_evidence",
        lambda *_args, **_kwargs: {"audited": True},
    )

    result_dir, _, _, metadata = study._run_actuator_probe(
        normalized=normalized,
        root=tmp_path,
        engine_path=tmp_path / "engine.py",
        graph_path=tmp_path / "graph.json",
        risk_path=tmp_path / "risk.csv",
        engine_args=(),
        output_root=output_root,
        input_name="order_multiplier",
    )

    command = captured["command"]
    assert "--control-schedule-csv" in command
    assert "--control-probe-schedule-csv" not in command
    assert study.V2_CONTROL_FLAG not in command
    assert study.V3_CONTROL_FLAG not in command
    assert canonical_result_policy(result_dir) == study.canonical.REFERENCE_POLICY
    assert metadata["application_mode"] == study.ACTUATOR_OPEN_LOOP_SCHEDULE
    assert metadata["control_schedule_enabled"] is True
    assert metadata["control_probe_enabled"] is False


def test_closed_loop_actuator_runner_uses_probe_after_v3_feedback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    normalized = study.validate_frequency_config(
        json.loads(
            CLOSED_LOOP_ACTUATOR_CONFIG_PATH.read_text(encoding="utf-8")
        )
    )
    output_root = tmp_path / "output"
    (output_root / "inputs").mkdir(parents=True)
    captured: dict[str, list[str]] = {}

    def fake_run_engine(
        command: list[str], *, cwd: Path, result_dir: Path
    ) -> None:
        del cwd
        captured["command"] = command
        (result_dir / "summaries").mkdir(parents=True)
        (result_dir / "summaries" / "first_simulation_summary.json").write_text(
            json.dumps(
                {
                    "policy": {
                        "control_schedule": {"enabled": False},
                        "control_probe": {
                            "enabled": True,
                            "composition_mode": "post_feedback_additive",
                            "scheduled_actions": 588,
                            "resolved_actions": 588,
                            "unresolved_actions": 0,
                            "composition_rows": 588,
                            "clipped_action_count": 0,
                            "feedback_command_export_modified": False,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(study.canonical, "_run_engine", fake_run_engine)
    monkeypatch.setattr(
        study,
        "_closed_loop_probe_realization_evidence",
        lambda *_args, **_kwargs: {"feedback_and_probe_separated": True},
    )
    policy_path = tmp_path / "v3.json"

    result_dir, _, _, metadata = study._run_actuator_probe(
        normalized=normalized,
        root=tmp_path,
        engine_path=tmp_path / "engine.py",
        graph_path=tmp_path / "graph.json",
        risk_path=tmp_path / "risk.csv",
        engine_args=(),
        output_root=output_root,
        input_name="order_multiplier",
        application_mode=study.ACTUATOR_POST_FEEDBACK_ADDITIVE,
        control_policy_path=policy_path,
        control_policy_flag=study.V3_CONTROL_FLAG,
    )

    command = captured["command"]
    assert "--control-probe-schedule-csv" in command
    assert "--control-schedule-csv" not in command
    assert study.V3_CONTROL_FLAG in command
    assert command[command.index(study.V3_CONTROL_FLAG) + 1] == str(policy_path)
    assert "--controller-prime-during-warmup" in command
    assert canonical_result_policy(result_dir) == study.canonical.FEEDBACK_POLICY
    assert metadata["application_mode"] == study.ACTUATOR_POST_FEEDBACK_ADDITIVE
    assert metadata["control_schedule_enabled"] is False
    assert metadata["control_probe_enabled"] is True
    assert metadata["feedback_command_export_modified"] is False


def canonical_result_policy(result_dir: Path) -> str:
    """Return the policy directory from a frequency actuator result path."""

    return result_dir.parent.name


def test_actuator_realization_separates_command_from_physical_execution(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "canonical_action_ledger.csv"
    pd.DataFrame(
        [
            {
                "day": day,
                "action": "production_target_multiplier",
                "requested": 1.05 if day % 2 == 0 else 0.95,
                "effective": 1.05 if day % 2 == 0 else 0.95,
                "executed_control_volume_qty": 100.0 if day == 2 else 0.0,
            }
            for day in range(4)
        ]
    ).to_csv(ledger_path, index=False)

    evidence = study._actuator_realization_evidence(
        ledger_path,
        input_name="production_target_multiplier",
        measured_days=4,
    )

    assert evidence["requested_non_neutral_day_count"] == 4
    assert evidence["effective_non_neutral_day_count"] == 4
    assert evidence["realized_positive_volume_day_count"] == 1
    assert evidence["realized_positive_volume_day_share"] == pytest.approx(0.25)
    assert evidence["realized_control_volume_qty"] == pytest.approx(100.0)


def test_closed_loop_probe_realization_uses_composition_sidecar(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            {
                "day": day,
                "action": "order_multiplier",
                "feedback_effective": 0.98,
                "probe_effective": 1.002 if day % 2 == 0 else 0.998,
                "probe_delta": 0.002 if day % 2 == 0 else -0.002,
                "composed_effective": 0.982 if day % 2 == 0 else 0.978,
                "composition_clipped": 1 if day == 3 else 0,
            }
            for day in range(4)
        ]
    ).to_csv(data_dir / "canonical_control_probe_composition.csv", index=False)
    pd.DataFrame(
        [
            {
                "day": day,
                "action": "order_multiplier",
                "requested": 0.982 if day % 2 == 0 else 0.978,
                "effective": 0.982 if day % 2 == 0 else 0.978,
                "executed_control_volume_qty": 25.0 if day == 2 else 0.0,
            }
            for day in range(4)
        ]
    ).to_csv(data_dir / "canonical_action_ledger.csv", index=False)

    evidence = study._closed_loop_probe_realization_evidence(
        tmp_path,
        input_name="order_multiplier",
        measured_days=4,
    )

    assert evidence["composition_mode"] == study.ACTUATOR_POST_FEEDBACK_ADDITIVE
    assert evidence["probe_non_neutral_day_count"] == 4
    assert evidence["composition_clipped_day_count"] == 1
    assert evidence["probe_delta_min"] == pytest.approx(-0.002)
    assert evidence["probe_delta_max"] == pytest.approx(0.002)
    assert evidence["feedback_and_probe_separated"] is True
    assert evidence["physical_action_ledger"][
        "realized_control_volume_qty"
    ] == pytest.approx(25.0)


def test_excitation_audit_contains_only_enabled_designed_inputs(
    tmp_path: Path,
) -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["identification"]["enabled_input_signals"] = [
        "supplier_lead_time_multiplier"
    ]
    normalized = study.validate_frequency_config(payload)
    channel_signals = {
        name: np.zeros(normalized["period_days"], dtype=float)
        for name in normalized["input_bins"]
    }
    channel_signals["supplier_lead_time_multiplier"] = np.linspace(
        -0.01, 0.01, normalized["period_days"]
    )

    audit = study._write_excitation_audit(
        tmp_path / "excitation.csv",
        normalized=normalized,
        channel_signals=channel_signals,
    )

    assert set(audit["experiment_input_signal"]) == {
        "supplier_lead_time_multiplier"
    }
    assert len(audit) == len(normalized["conditions"]) * normalized["days"]
    assert audit["demand_fractional_excitation"].eq(0.0).all()
    assert audit["supplier_availability_fractional_excitation"].eq(0.0).all()
    assert audit["supplier_lead_time_fractional_excitation"].abs().max() > 0.0


def test_closed_loop_comparison_distinguishes_dynamic_and_static_policy() -> None:
    rows: list[dict[str, object]] = []
    for input_signal, dynamic in (
        ("demand_multiplier", True),
        ("supplier_availability_multiplier", False),
    ):
        for policy, magnitude in (
            ("mrp_reference", 2.0),
            ("canonical_feedback", 1.0),
        ):
            rows.append(
                {
                    "study_kind": "designed_closed_loop_disturbance_probe",
                    "condition": "supplier_stress_capacity",
                    "policy": policy,
                    "input_signal": input_signal,
                    "output_signal": "global_order_qty",
                    "frequency_bin": 1,
                    "frequency_cycles_per_day": 1.0 / 168.0,
                    "period_days": 168.0,
                    "elasticity_magnitude": magnitude,
                    "phase_deg": (
                        170.0
                        if input_signal == "demand_multiplier"
                        and policy == "mrp_reference"
                        else -170.0
                        if input_signal == "demand_multiplier"
                        else -10.0
                    ),
                    "coherence": 0.99,
                    "valid_bin": True,
                    "small_signal_local_claim": False,
                    "tested_amplitude_regime_trace_compatible": True,
                }
            )
        if dynamic:
            rows.append(
                {
                    "study_kind": "designed_closed_loop_disturbance_probe",
                    "condition": "supplier_stress_capacity",
                    "policy": "canonical_feedback",
                    "input_signal": input_signal,
                    "output_signal": "control_order_multiplier",
                    "frequency_bin": 1,
                    "frequency_cycles_per_day": 1.0 / 168.0,
                    "period_days": 168.0,
                    "elasticity_magnitude": 0.1,
                    "phase_deg": 0.0,
                    "coherence": 0.99,
                    "valid_bin": True,
                    "small_signal_local_claim": False,
                    "tested_amplitude_regime_trace_compatible": True,
                }
            )
    condition_runs = {
        "supplier_stress_capacity": {
            "feedback_activation": {
                "by_input": {
                    "demand_multiplier": {
                        "all_arms_physically_active": True,
                        "arms": {
                            "baseline": {"physical_action_applied": True},
                            "excited": {"physical_action_applied": True},
                        },
                    },
                    "supplier_availability_multiplier": {
                        "all_arms_physically_active": True,
                        "arms": {
                            "baseline": {"physical_action_applied": True},
                            "excited": {"physical_action_applied": True},
                        },
                    },
                }
            }
        }
    }

    comparison = study._closed_loop_comparison(pd.DataFrame(rows), condition_runs)
    outputs = comparison.loc[comparison["output_signal"].eq("global_order_qty")]
    interpretations = dict(
        zip(outputs["input_signal"], outputs["comparison_interpretation"], strict=True)
    )
    assert interpretations["demand_multiplier"] == "dynamic_feedback_modulation"
    assert (
        interpretations["supplier_availability_multiplier"]
        == "active_static_policy_conditioning"
    )
    assert outputs["baseline_feedback_physically_active"].all()
    assert outputs["excited_feedback_physically_active"].all()
    assert outputs["all_arms_feedback_physically_active"].all()
    demand = outputs.loc[outputs["input_signal"].eq("demand_multiplier")].iloc[0]
    assert demand["phase_difference_deg"] == pytest.approx(20.0)
    for historical, version_neutral in (
        ("v2_elasticity_magnitude", "feedback_elasticity_magnitude"),
        ("v2_over_mrp_magnitude_ratio", "feedback_over_mrp_magnitude_ratio"),
        ("v2_minus_mrp_attenuation_db", "feedback_minus_mrp_attenuation_db"),
        ("v2_phase_deg", "feedback_phase_deg"),
        ("v2_coherence", "feedback_coherence"),
    ):
        pd.testing.assert_series_equal(
            outputs[historical],
            outputs[version_neutral],
            check_names=False,
        )
    assert outputs["tested_amplitude_regime_compatible"].all()
    assert not outputs["small_signal_regime_compatible"].any()
    assert outputs["reliable_comparison"].all()
    assert not outputs["small_signal_local_derivative_claimed"].any()
    assert not outputs["active_set_invariance_verified"].any()
    assert set(outputs["comparison_scope"]) == {
        study.TESTED_AMPLITUDE_LOCALITY_SCOPE
    }


def test_provenance_snapshot_is_self_contained_and_detects_source_drift(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    source = repo / "etudecas" / "source.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()

    metadata = study._write_provenance_snapshot(
        output,
        repo_root=repo,
        sources={"source": source},
    )
    finalized = study._finalize_provenance_snapshot(metadata)
    entry = finalized["entries"][0]
    snapshot = Path(entry["snapshot_path"])
    assert snapshot.read_bytes() == source.read_bytes()
    assert finalized["source_hashes_verified_at_completion"] is True
    assert Path(finalized["manifest_path"]).is_file()
    assert len(finalized["manifest_sha256"]) == 64
    ledger = study._write_artifact_ledger(output)
    ledger_rows = pd.read_csv(ledger["path"])
    assert ledger["row_count"] == len(ledger_rows)
    assert "provenance/source_snapshot_manifest.json" in set(
        ledger_rows["relative_path"]
    )
    assert "canonical_frequency_artifact_ledger.csv" not in set(
        ledger_rows["relative_path"]
    )

    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(study.CanonicalFrequencyContractError, match="changed"):
        study._finalize_provenance_snapshot(metadata)


def test_supplier_reachability_excludes_warmup_and_requires_each_retained_period(
    tmp_path: Path,
) -> None:
    probe = {
        "supplier_id": "S",
        "dst_node_id": "M",
        "item_id": "item:X",
    }

    def write_runs(root: Path, shipment_days: list[int], arrival_days: list[int]) -> None:
        for policy in ("mrp_reference", "canonical_feedback"):
            data = root / policy / "seed_7" / "data"
            data.mkdir(parents=True)
            pd.DataFrame(
                [
                    {
                        "day": day,
                        "src_node_id": "S",
                        "dst_node_id": "M",
                        "item_id": "item:X",
                        "shipped_qty": 1.0,
                    }
                    for day in shipment_days
                ]
            ).to_csv(data / "production_supplier_shipments_daily.csv", index=False)
            pd.DataFrame(
                [
                    {
                        "day": day,
                        "node_id": "M",
                        "item_id": "item:X",
                        "arrived_qty": 1.0,
                    }
                    for day in arrival_days
                ]
            ).to_csv(
                data / "production_input_replenishment_arrivals_daily.csv",
                index=False,
            )

    failed_root = tmp_path / "failed"
    write_runs(failed_root, [-3, 4], [-2, 5])
    with pytest.raises(study.CanonicalFrequencyContractError, match="inactive"):
        study._supplier_probe_reachability_evidence(
            baseline_root=failed_root,
            seed=7,
            probe=probe,
            measured_days=12,
            period_days=4,
            discard_periods=1,
        )

    valid_root = tmp_path / "valid"
    write_runs(valid_root, [-3, 4, 8], [-2, 5, 9])
    evidence = study._supplier_probe_reachability_evidence(
        baseline_root=valid_root,
        seed=7,
        probe=probe,
        measured_days=12,
        period_days=4,
        discard_periods=1,
    )
    assert evidence["analysed_period_indices"] == [1, 2]
    assert evidence["nonzero_shipment_days"] == 2
    assert evidence["all_runs_reachable"] is True


def test_frequency_signal_probe_filters_exact_destination(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pd.DataFrame(
        {
            "day": [0, 1],
            "demand": [1.0, 1.0],
            "served": [1.0, 1.0],
            "backlog_end": [0.0, 0.0],
            "inventory_total": [1.0, 1.0],
            "produced_qty": [0.0, 0.0],
            "total_supply_cost_day": [0.0, 0.0],
        }
    ).to_csv(data / "first_simulation_daily.csv", index=False)
    pd.DataFrame(
        {"day": [0, 1], "planned_release_qty": [0.0, 0.0]}
    ).to_csv(data / "mrp_trace_daily.csv", index=False)
    pd.DataFrame(
        [
            {
                "day": 0,
                "src_node_id": "S",
                "dst_node_id": "M",
                "item_id": "item:X",
                "shipped_qty": 5.0,
            },
            {
                "day": 0,
                "src_node_id": "S",
                "dst_node_id": "OTHER",
                "item_id": "item:X",
                "shipped_qty": 99.0,
            },
        ]
    ).to_csv(data / "production_supplier_shipments_daily.csv", index=False)
    pd.DataFrame(
        columns=["day", "item_id", "demand_qty", "served_qty", "backlog_end_qty"]
    ).to_csv(data / "production_demand_service_daily.csv", index=False)
    pd.DataFrame(
        columns=["day", "item_id", "produced_qty", "stock_end_of_day"]
    ).to_csv(data / "production_output_products_daily.csv", index=False)
    pd.DataFrame(
        columns=["day", "node_id", "item_id", "stock_end_of_day"]
    ).to_csv(data / "production_supplier_stocks_daily.csv", index=False)
    pd.DataFrame(columns=["day", "node_id", "item_id", "utilization"]).to_csv(
        data / "production_supplier_capacity_daily.csv", index=False
    )
    pd.DataFrame(columns=["day", "node_id", "item_id", "arrived_qty"]).to_csv(
        data / "production_input_replenishment_arrivals_daily.csv", index=False
    )

    signals, _ = extract_frequency_signals(
        tmp_path,
        target_finished_item_id="item:FINISHED",
        probe_supplier_id="S",
        probe_item_id="item:X",
        probe_dst_node_id="M",
    )
    assert signals["probe_supplier_shipments_qty"].tolist() == [5.0, 0.0]
    assert signals["global_supplier_shipments_qty"].tolist() == [104.0, 0.0]


def test_supplier_perturbation_application_matches_engine_daily_audit(
    tmp_path: Path,
) -> None:
    roots: dict[str, Path] = {}
    risks: dict[str, dict[str, object]] = {}
    requested = {
        "supplier_availability_multiplier": [0.9, 1.0, 1.1],
        "supplier_lead_time_multiplier": [1.1, 1.2, 1.3],
    }
    for input_name, values in requested.items():
        root = tmp_path / input_name
        roots[input_name] = root
        risk_path = tmp_path / f"{input_name}.csv"
        rows = []
        for day in range(3):
            rows.extend(
                [
                    {
                        "risk_type": "availability",
                        "start_day": day,
                        "multiplier": (
                            values[day]
                            if input_name == "supplier_availability_multiplier"
                            else 0.8
                        ),
                    },
                    {
                        "risk_type": "lead_time",
                        "start_day": day,
                        "multiplier": (
                            values[day]
                            if input_name == "supplier_lead_time_multiplier"
                            else 1.2
                        ),
                    },
                ]
            )
        pd.DataFrame(rows).to_csv(risk_path, index=False)
        risks[input_name] = {"path": str(risk_path)}
        for policy in ("mrp_reference", "canonical_feedback"):
            data = root / policy / "seed_3" / "data"
            data.mkdir(parents=True)
            pd.DataFrame(
                {
                    "day": [0, 1, 2],
                    "supplier_id": ["S"] * 3,
                    "dst_node_id": ["M"] * 3,
                    "item_id": ["item:X"] * 3,
                    "availability_multiplier": (
                        values
                        if input_name == "supplier_availability_multiplier"
                        else [0.8] * 3
                    ),
                    "lead_time_multiplier": (
                        values
                        if input_name == "supplier_lead_time_multiplier"
                        else [1.2] * 3
                    ),
                }
            ).to_csv(data / "supplier_risk_events_applied_daily.csv", index=False)

    evidence = study._supplier_perturbation_application_evidence(
        excited_roots=roots,
        excited_risks=risks,
        seed=3,
        probe={"supplier_id": "S", "dst_node_id": "M", "item_id": "item:X"},
        measured_days=3,
        period_days=1,
        discard_periods=1,
    )
    assert evidence["status"] == (
        "supplier_multisines_scheduled_daily_and_matched_on_all_physical_applications"
    )
    assert set(evidence["experiments"]) == set(requested)

    lead_only = study._supplier_perturbation_application_evidence(
        excited_roots={
            "supplier_lead_time_multiplier": roots[
                "supplier_lead_time_multiplier"
            ]
        },
        excited_risks={
            "supplier_lead_time_multiplier": risks[
                "supplier_lead_time_multiplier"
            ]
        },
        seed=3,
        probe={"supplier_id": "S", "dst_node_id": "M", "item_id": "item:X"},
        measured_days=3,
        period_days=1,
        discard_periods=1,
    )
    assert lead_only["enabled_supplier_input_signals"] == [
        "supplier_lead_time_multiplier"
    ]
    assert set(lead_only["experiments"]) == {
        "supplier_lead_time_multiplier"
    }


def test_graph_and_risk_variants_are_written_below_requested_root(tmp_path: Path) -> None:
    source = tmp_path / "graph.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "0.3",
                "meta": {},
                "nodes": [],
                "edges": [],
                "scenarios": [
                    {
                        "id": "scn:BASE",
                        "demand": [
                            {
                                "node_id": "C",
                                "item_id": "item:X",
                                "profile": [
                                    {
                                        "type": "piecewise",
                                        "repeat_period_days": 365,
                                        "points": [{"t": 0, "value": 10.0}],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    signal = 0.02 * normalized_multisine(32, [1, 3], phase_seed=1)
    destination = tmp_path / "inputs" / "excited.json"
    metadata = study._write_graph_variant(
        source,
        destination,
        period_days=32,
        demand_fraction=signal,
        excited=True,
        demand_scale_by_item={"item:X": 0.5},
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    points = payload["scenarios"][0]["demand"][0]["profile"][0]["points"]
    assert len(points) == 32
    assert metadata["path"] == str(destination)
    assert metadata["original_demand_baselines"]["C|item:X"] == pytest.approx(10.0)
    assert metadata["demand_baselines"]["C|item:X"] == pytest.approx(5.0)
    assert payload["meta"]["scan_frequency_study"]["synthetic_designed_excitation"] is True

    risk_path = tmp_path / "inputs" / "risk.csv"
    risk = study._write_risk_events(
        risk_path,
        condition={
            "supplier_availability_baseline": 0.65,
            "supplier_lead_time_baseline": 1.2,
        },
        probe={
            "supplier_id": "S",
            "item_id": "item:X",
            "dst_node_id": "M",
        },
        warmup_days=64,
        measured_days=96,
        period_days=32,
        availability_fraction=signal,
        lead_time_fraction=signal,
        excited=True,
    )
    rows = pd.read_csv(risk_path)
    assert risk["row_count"] == 2 * (64 + 96)
    assert rows["start_day"].min() == -64
    assert rows["end_day"].max() == 95
    warmup = rows.loc[rows["start_day"].lt(0)]
    measured = rows.loc[rows["start_day"].ge(0)]
    assert set(warmup.loc[warmup["risk_type"].eq("availability"), "multiplier"]) == {0.65}
    assert set(warmup.loc[warmup["risk_type"].eq("lead_time"), "multiplier"]) == {1.2}
    assert measured.loc[
        measured["risk_type"].eq("availability"), "multiplier"
    ].nunique() > 1
    assert measured.loc[
        measured["risk_type"].eq("lead_time"), "multiplier"
    ].nunique() > 1

    demand_path = tmp_path / "inputs" / "demand.csv"
    demand = study._write_demand_perturbation(
        demand_path,
        graph_path=source,
        measured_days=96,
        period_days=32,
        demand_fraction=signal,
    )
    demand_rows = pd.read_csv(demand_path)
    assert demand["row_count"] == 96
    assert demand["day_basis"] == "zero_based_measured_days_only_never_warmup"
    assert list(demand_rows.columns) == [
        "day",
        "node_id",
        "item_id",
        "demand_multiplier",
    ]
    assert demand_rows["day"].min() == 0
    assert demand_rows["day"].max() == 95
    assert demand_rows["demand_multiplier"].between(0.5, 1.5).all()
