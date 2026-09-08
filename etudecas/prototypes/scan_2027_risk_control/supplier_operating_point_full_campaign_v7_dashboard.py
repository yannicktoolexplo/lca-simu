#!/usr/bin/env python3
"""Seed-aware V7 adapter for the frozen V4 campaign dashboard reader.

The V4 reader is reused byte for byte.  This adapter changes only its expected
campaign cohort while a read/build call is active, then restores the historical
V4 cohort.  It does not run a simulation and does not modify prior results.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4_dashboard as implementation_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


EXPECTED_V4_DASHBOARD_SHA256 = (
    "7f159384e1609465469ff0263d635600d4dd06d71e7e3df90c8cedf9bebec601"
)
DashboardInputError = implementation_v4.DashboardInputError


def _v7_html_template() -> str:
    """Rebrand only the three visible V4 provenance statements, fail closed."""

    replacements = {
        "<title>Campagne fournisseurs V4 — résultats</title>": (
            "<title>Campagne fournisseurs V7 — résultats</title>"
        ),
        '<div class="overline">CAMPAGNE FOURNISSEURS V4 · SYNTHÈSE AUTONOME</div>': (
            '<div class="overline">CAMPAGNE FOURNISSEURS V7 · SYNTHÈSE AUTONOME</div>'
        ),
        (
            "<p>Trois états simulés du même réseau, deux incidents imposés et les "
            "mêmes 30 répétitions appariées. Cette page montre où instruire un "
            "dossier fournisseur. Elle ne mesure ni la performance historique ni "
            "la probabilité future d'un incident.</p>"
        ): (
            "<p>Le triplet V7 a été confirmé sur 150 graines, soit 450 simulations "
            "physiques nouvelles. La campagne d'incidents utilise ensuite les 30 "
            "premières graines, soit 90 situations normales appariées aux incidents. "
            "Cette page montre où instruire un dossier fournisseur ; elle ne mesure "
            "ni la performance historique ni la probabilité future d'un incident.</p>"
        ),
        "Ces valeurs viennent du holdout V4 signé.": (
            "Ces valeurs décrivent les 30 premières graines V7 réservées à "
            "l'appariement de campagne ; elles ne constituent pas la décision "
            "scientifique V7 sur 150 graines et 450 simulations."
        ),
    }
    template = implementation_v4.HTML_TEMPLATE
    for source, replacement in replacements.items():
        if template.count(source) != 1:
            raise DashboardInputError(
                "Le texte visible du dashboard mature a changé ; rebranding V7 refusé."
            )
        template = template.replace(source, replacement)
    if "Campagne fournisseurs V4" in template or "holdout V4" in template:
        raise DashboardInputError(
            "Une provenance V4 visible subsiste dans le dashboard V7."
        )
    return template


def validate_frozen_implementation() -> Path:
    trace_package.validate_frozen_v7_protocol()
    path = Path(implementation_v4.__file__).resolve()
    digest = trace_package.campaign_contract.sha256_file(path)
    if digest != EXPECTED_V4_DASHBOARD_SHA256:
        raise DashboardInputError(f"Frozen V4 dashboard changed: {digest}")
    return path


@contextmanager
def patched_v7_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_seeds: Any = implementation_v4.v4_contract.CAMPAIGN_SEEDS
    previous_template: Any = implementation_v4.HTML_TEMPLATE
    implementation_v4.v4_contract.CAMPAIGN_SEEDS = trace_package.CAMPAIGN_SEEDS
    implementation_v4.HTML_TEMPLATE = _v7_html_template()
    try:
        yield
    finally:
        implementation_v4.v4_contract.CAMPAIGN_SEEDS = previous_seeds
        implementation_v4.HTML_TEMPLATE = previous_template


def _validate_v7_binding(results_dir: Path) -> dict[str, Any]:
    path = results_dir.resolve() / "state_validation_binding.json"
    binding = implementation_v4._read_json(path)  # noqa: SLF001
    implementation_v4._verify_embedded_signature(  # noqa: SLF001
        binding,
        signature_field="binding_signature",
        label="registre V7 des points de fonctionnement",
    )
    provenance = binding.get("scientific_provenance_v7")
    interpretation = str(binding.get("interpretation") or "")
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("scientific_authorization")
        != "accepted_official_v7_fixed_triplet_confirmation"
        or provenance.get("validation_seed_count") != 150
        or provenance.get("fresh_validation_case_count") != 450
        or provenance.get("campaign_baseline_seed_count") != 30
        or provenance.get("campaign_baseline_trace_count") != 90
        or provenance.get("campaign_baseline_subset_is_acceptance_gate") is not False
        or provenance.get("same_30_seeds_for_baseline_and_incidents") is not True
        or provenance.get("retuning_after_v7") is not False
        or provenance.get("prior_version_simulation_evidence_reused") is not False
        or binding.get("campaign_seeds") != list(trace_package.CAMPAIGN_SEEDS)
        or provenance.get("v7_plan_signature") != binding.get("v7_plan_signature")
        or provenance.get("v7_result_signature")
        != binding.get("v7_validation_result_signature")
        or binding.get("v7_plan_signature") != binding.get("v4_plan_signature")
        or binding.get("v7_validation_result_signature")
        != binding.get("v4_holdout_signature")
        or binding.get("v7_campaign_trace_index_signature")
        != binding.get("v4_trace_index_signature")
        or binding.get("legacy_v4_named_signature_fields_are_compatibility_aliases")
        is not True
        or "accepted official V7" not in interpretation
        or "accepted fresh V4 holdout" in interpretation
    ):
        raise DashboardInputError(
            "La provenance scientifique V7 du registre final est absente ou ambiguë."
        )
    return binding


def load_dashboard_data(
    *, results_dir: Path, target_registry_path: Path | None = None
) -> dict[str, Any]:
    with patched_v7_context():
        payload = implementation_v4.load_dashboard_data(
            results_dir=results_dir,
            target_registry_path=target_registry_path,
        )
    _validate_v7_binding(results_dir)
    return payload


def build_dashboard(
    *,
    results_dir: Path,
    output_html: Path,
    target_registry_path: Path | None = None,
) -> dict[str, Any]:
    _validate_v7_binding(results_dir)
    with patched_v7_context():
        result: Mapping[str, Any] = implementation_v4.build_dashboard(
            results_dir=results_dir,
            output_html=output_html,
            target_registry_path=target_registry_path,
        )
    return dict(result)


def main(argv: Sequence[str] | None = None) -> int:
    args = implementation_v4.parse_args(argv)
    try:
        result = build_dashboard(
            results_dir=args.results_dir,
            output_html=args.output_html,
            target_registry_path=args.target_registry,
        )
    except (DashboardInputError, FileExistsError) as exc:
        print(f"DASHBOARD V7 NON PRODUIT : {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
