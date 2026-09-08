#!/usr/bin/env python3
"""Build the additive V8 three-view, standalone French client delivery.

The mature V7 presentation reducers are reused, but every V8 read is guarded by
the signed V8 result overlay and the V8 finalizer context.  The delivery starts
with the 338929 lane, then broadens to cross-state supplier cascades and finally
to physically representable actions.  It never runs the simulation engine and
never writes into V4 or V7 artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_delivery as delivery_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as common,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage2_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
FOCUS_LANE_ID = delivery_v7.FOCUS_LANE_ID
FOCUS_ITEM_ID = "338929"
EXPECTED_MECHANISMS = {"transport_delay", "planned_delivery_shortfall"}


class Stage2DeliveryError(common.Stage2Error):
    """A source or client-facing claim does not satisfy the V8 contract."""


class _V8DashboardReader:
    """Expose the mature dashboard loader only inside validated V8 contexts."""

    def __init__(self, campaign_root: Path) -> None:
        self.campaign_root = campaign_root.resolve()

    def load_dashboard_data(
        self, *, results_dir: Path, target_registry_path: Path | None = None
    ) -> dict[str, Any]:
        results = results_dir.resolve()
        with finalizer_v8.patched_v8_context():
            overlay = finalizer_v8.validate_v8_overlay(self.campaign_root, results)
            with dashboard_v7.patched_v7_context():
                payload = dashboard_v7.implementation_v4.load_dashboard_data(
                    results_dir=results,
                    target_registry_path=target_registry_path,
                )
        if (
            overlay.get("status") != "complete_validated_v8_overlay"
            or overlay.get("v8_comparability_checks", {}).get(
                "complete_3330_case_matrix_reconstructed"
            )
            is not True
            or overlay.get("v8_comparability_checks", {}).get(
                "quality_capacity_availability_stock_or_state_risk_incident_count"
            )
            != 0
        ):
            raise Stage2DeliveryError("La preuve finale V8 ne permet pas l'affichage.")
        return payload


@contextmanager
def _v8_reducer_binding(paths: common.Stage2Paths) -> Iterator[None]:
    """Bind V7 reducers to V8 contracts for one read, then restore them."""

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline_v7,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_pipeline as pipeline_v8,
    )

    previous_delivery = {
        "common": delivery_v7.common,
        "dashboard_v7": delivery_v7.dashboard_v7,
        "finalizer_v7": delivery_v7.finalizer_v7,
    }
    previous_pipeline = {
        "common": pipeline_v7.common,
        "SCHEMA_VERSION": pipeline_v7.SCHEMA_VERSION,
        "UPSTREAM_NAME": pipeline_v7.UPSTREAM_NAME,
        "_contract_payload": pipeline_v7._contract_payload,  # noqa: SLF001
    }
    delivery_v7.common = common
    delivery_v7.dashboard_v7 = _V8DashboardReader(paths.campaign_root)
    delivery_v7.finalizer_v7 = SimpleNamespace(
        V7_RESULT_OVERLAY_NAME=finalizer_v8.V8_RESULT_OVERLAY_NAME
    )
    pipeline_v7.common = common
    pipeline_v7.SCHEMA_VERSION = pipeline_v8.SCHEMA_VERSION
    pipeline_v7.UPSTREAM_NAME = pipeline_v8.UPSTREAM_NAME
    pipeline_v7._contract_payload = pipeline_v8._contract_payload_v8  # noqa: SLF001
    try:
        yield
    finally:
        for name, value in previous_pipeline.items():
            setattr(pipeline_v7, name, value)
        for name, value in previous_delivery.items():
            setattr(delivery_v7, name, value)


def _adapt_payload(
    base: Mapping[str, Any], overlay: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply only V8 provenance and the three-view narrative; copy no result."""

    unsigned = {key: value for key, value in base.items() if key != "payload_signature"}
    payload = dict(unsigned)
    payload["schema_version"] = SCHEMA_VERSION
    payload["title"] = "338929 : du risque fournisseur aux décisions"

    campaign = payload.get("campaign")
    focus = payload.get("focus")
    limits = payload.get("limits")
    bindings = payload.get("bindings")
    terminology = payload.get("terminology")
    if not all(
        isinstance(value, Mapping)
        for value in (campaign, focus, limits, bindings, terminology)
    ):
        raise Stage2DeliveryError("Structure de présentation V8 incomplète.")
    mechanisms = {str(row.get("id") or "") for row in campaign.get("mechanisms") or []}
    if mechanisms != EXPECTED_MECHANISMS:
        raise Stage2DeliveryError("Les deux hypothèses fournisseurs V8 ont changé.")
    if (
        focus.get("lane_id") != FOCUS_LANE_ID
        or focus.get("item_id") != FOCUS_ITEM_ID
        or focus.get("requested_338929_present") is not True
    ):
        raise Stage2DeliveryError("La voie 338929 n'est pas disponible dans V8.")
    if (
        limits.get("quality_incident_included") is not False
        or limits.get("capacity_or_availability_modified") is not False
        or campaign.get("multiple_incidents_combined") is not False
    ):
        raise Stage2DeliveryError("La portée des incidents V8 a changé.")
    expected_terms = {"OBSERVÉ", "SIMULÉ", "SIGNAL DE PRIORITÉ", "HYPOTHÈSE"}
    if set(terminology) != expected_terms:
        raise Stage2DeliveryError("Le vocabulaire client V8 est incomplet.")

    payload["nominal_curves"] = {
        **dict(payload.get("nominal_curves") or {}),
        "population": (
            "30 situations normales signées V7, réutilisées par V8 avec les mêmes "
            "identifiants pour comparer chaque incident à son fonctionnement normal"
        ),
    }
    payload["presentation"] = {
        "view_order": ["focus_338929", "network_cascades", "decisions"],
        "focus_item_id": FOCUS_ITEM_ID,
        "focus_lane_id": FOCUS_LANE_ID,
        "numbers_are_loaded_from_signed_results": True,
        "future_or_placeholder_results_displayed": False,
    }
    payload["bindings"] = {
        **dict(bindings),
        "v8_result_overlay_signature": overlay["overlay_signature"],
    }
    return common.signed(payload, "payload_signature")


def collect_payload(
    paths: common.Stage2Paths,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Revalidate V7 state proof and the complete V8 campaign before rendering."""

    paths = paths.resolved()
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_pipeline as pipeline_v8,
    )

    pipeline_v8.validate_bound_contract(paths)
    with finalizer_v8.patched_v8_context():
        overlay = finalizer_v8.validate_v8_overlay(
            paths.campaign_root, paths.results_dir
        )
    with _v8_reducer_binding(paths):
        base, sources = delivery_v7.collect_payload(paths)
    payload = _adapt_payload(base, overlay)
    updated_sources = []
    for source in sources:
        row = dict(source)
        if row.get("role") == "surcouche_resultats_v7":
            row["role"] = "surcouche_resultats_v8"
            row["signature"] = overlay["overlay_signature"]
        updated_sources.append(row)
    overlay_path = paths.results_dir / finalizer_v8.V8_RESULT_OVERLAY_NAME
    if not any(
        Path(str(row.get("path") or "")).resolve() == overlay_path.resolve()
        for row in updated_sources
    ):
        raise Stage2DeliveryError("La preuve V8 n'est pas liée au livrable.")
    return payload, updated_sources


def _v8_html_template() -> str:
    """Reorder the mature page: 338929, network cascades, decisions."""

    template = delivery_v7.HTML_TEMPLATE
    replacements = {
        "<title>Risques fournisseurs — démonstration V7</title>": (
            "<title>338929 et risques fournisseurs — démonstration V8</title>"
        ),
        (
            '<header><div class="small" style="color:#9ee8d8;font-weight:800">'
            "DÉMONSTRATION AUTONOME · RISQUES FOURNISSEURS</div><h1>Risques "
            "fournisseurs : où la supply devient-elle fragile&nbsp;?</h1><p>Trois "
            "niveaux de fonctionnement validés, deux incidents hypothétiques séparés, "
            "jusqu'à trois analyses détaillées des lots et seulement des leviers "
            "réellement représentables.</p>"
        ): (
            '<header><div class="small" style="color:#9ee8d8;font-weight:800">'
            "DÉMONSTRATION AUTONOME V8 · RISQUES FOURNISSEURS</div><h1>338929 : "
            "du risque fournisseur aux décisions</h1><p>Le parcours commence par "
            "la voie 338929, montre les propagations et les lots réellement tracés, "
            "puis élargit aux fournisseurs récurrents et aux leviers effectivement "
            "simulés.</p>"
        ),
        (
            '<nav class="tabs"><button class="active" data-tab="states">1 · Fragilité et fournisseurs</button>'
            '<button data-tab="cascade">2 · Incident et lots</button>'
            '<button data-tab="actions">3 · Leviers pilotables</button></nav>'
        ): (
            '<nav class="tabs"><button class="active" data-tab="cascade">1 · 338929 et lots</button>'
            '<button data-tab="states">2 · Cascades et fournisseurs</button>'
            '<button data-tab="actions">3 · Décisions et limites</button></nav>'
        ),
        '<section class="view active" id="states">': '<section class="view" id="states">',
        '<section class="view" id="cascade">': '<section class="view active" id="cascade">',
        "Scénarios unitaires, pas cascade de plusieurs incidents.": (
            "Une cause fournisseur à la fois, des conséquences qui se propagent."
        ),
        "Pas de généalogie V7 détaillée disponible.": (
            "Pas de généalogie V8 détaillée disponible."
        ),
    }
    for source, replacement in replacements.items():
        if template.count(source) != 1:
            raise Stage2DeliveryError(
                "Le gabarit V7 mature a changé ; adaptation V8 refusée."
            )
        template = template.replace(source, replacement)
    return template


HTML_TEMPLATE = _v8_html_template()


def render_html(payload: Mapping[str, Any]) -> str:
    document = HTML_TEMPLATE.replace("__DATA__", delivery_v7._safe_json(payload))  # noqa: SLF001
    if document.count('class="view') != 3:
        raise Stage2DeliveryError("Le livrable V8 doit contenir exactement trois vues.")
    visible = document.split("<script>", 1)[0]
    for term in ("OBSERVÉ", "SIMULÉ", "SIGNAL DE PRIORITÉ", "HYPOTHÈSE"):
        if term not in json.dumps(payload.get("terminology") or {}, ensure_ascii=False):
            raise Stage2DeliveryError(f"Vocabulaire client absent : {term}")
    if "338929" not in visible or 'class="view active" id="cascade"' not in visible:
        raise Stage2DeliveryError("Le parcours V8 ne commence pas par 338929.")
    return document


def _manifest_payload(
    paths: common.Stage2Paths,
    payload: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    document: str,
) -> dict[str, Any]:
    raw = document.encode("utf-8")
    unsigned = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "output_html": str(paths.final_html),
        "html_sha256": hashlib.sha256(raw).hexdigest(),
        "html_bytes": len(raw),
        "payload_signature": payload["payload_signature"],
        "view_count": 3,
        "standalone": True,
        "external_dependency_count": 0,
        "source_bindings": list(sources),
        "scientific_contract": {
            "state_validation_source": "accepted_official_v7_fixed_triplet",
            "campaign_result_overlay": "complete_validated_v8_overlay",
            "validation_cases": 450,
            "campaign_rows": 3330,
            "incident_rows": 3240,
            "focus_lane": FOCUS_LANE_ID,
            "maximum_detailed_dossiers": 3,
            "forced_top3": False,
            "quality": False,
            "capacity_or_availability_invented": False,
            "historical_probability": False,
            "actions_open_loop": True,
            "automatic_regulation": False,
            "clients_aggregated": True,
            "cost_or_roi_claimed": False,
            "future_or_placeholder_results_displayed": False,
        },
    }
    return common.signed(unsigned, "manifest_signature")


def validate_delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    paths = paths.resolved()
    manifest_path = Path(str(paths.final_html) + ".manifest.json")
    manifest = common.read_json(manifest_path)
    common.verify_signature(manifest, "manifest_signature", "manifeste HTML V8")
    payload, sources = collect_payload(paths)
    document = render_html(payload)
    expected = _manifest_payload(paths, payload, sources, document)
    actual = paths.final_html.read_text(encoding="utf-8")
    contract = manifest.get("scientific_contract") or {}
    if (
        manifest != expected
        or actual != document
        or actual.count('class="view') != 3
        or "https://" in actual
        or "http://" in actual
        or "€" in actual
        or payload.get("presentation", {}).get(
            "future_or_placeholder_results_displayed"
        )
        is not False
        or payload.get("focus", {}).get("lane_id") != FOCUS_LANE_ID
        or contract.get("campaign_result_overlay") != "complete_validated_v8_overlay"
        or contract.get("quality") is not False
        or contract.get("automatic_regulation") is not False
    ):
        raise Stage2DeliveryError(
            "Le livrable autonome V8 ne reproduit plus ses preuves."
        )
    folded = actual.casefold()
    for text in (
        "aucune probabilité historique",
        "boucle ouverte",
        "aucun incident qualité",
        "aucune capacité/disponibilité modifiée",
        "clients agrégés",
        "lots simulés",
        "devise non renseignée",
    ):
        if text not in folded:
            raise Stage2DeliveryError(f"Limite métier V8 non visible : {text}")
    return {
        "valid": True,
        "html": str(paths.final_html),
        "html_sha256": manifest["html_sha256"],
        "html_bytes": manifest["html_bytes"],
        "manifest": str(manifest_path),
        "manifest_signature": manifest["manifest_signature"],
        "view_count": 3,
        "focus_lane": FOCUS_LANE_ID,
        "detailed_dossier_count": len(payload["cascade"]["detailed_replays"]),
        "action_result_count": len(payload["actions"]["actions"]),
    }


def build_delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    paths = paths.resolved()
    paths.validate_separation()
    manifest_path = Path(str(paths.final_html) + ".manifest.json")
    if paths.final_html.exists() and manifest_path.exists():
        return validate_delivery(paths)
    if manifest_path.exists():
        raise Stage2DeliveryError("Manifeste HTML V8 orphelin ; écrasement refusé.")
    payload, sources = collect_payload(paths)
    document = render_html(payload)
    manifest = _manifest_payload(paths, payload, sources, document)
    common.publish_new_or_identical(paths.final_html, document.encode("utf-8"))
    common.publish_new_or_identical(
        manifest_path,
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return validate_delivery(paths)


def _parser() -> argparse.ArgumentParser:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_pipeline as pipeline,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    pipeline.add_path_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_pipeline as pipeline,
    )

    args = _parser().parse_args(argv)
    try:
        result = build_delivery(pipeline.paths_from_args(args))
    except Exception as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
