#!/usr/bin/env python3
"""Assemble the scientifically bounded supplier-risk demonstration.

The four dynamic inputs are deliberately strict:

* the signed scientific network overlay (legacy promotion aliases neutralised);
* the signed priority-boundary audit tied to the overlay source campaign;
* the audited 021081 component package (V3 business wording on the V2 schema);
* the blocked controllable-action catalogue tied to that same network lineage.

The builder writes to a sibling staging directory, validates every generated
HTML page, and only then renames the staging directory to the requested new
output directory. Existing simulations, cold-start results, maps and HTML
files are never copied, edited or replaced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote, urlsplit

from etudecas.prototypes.scan_2027_risk_control import (
    industrial_supply_bilan_dashboard as meeting_dashboard,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_risk_results_dashboard as network_dashboard,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_extension_interpretation_audit as extension_audit,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_priority_boundary_audit as boundary_audit,
)


SCHEMA_VERSION = "etudecas.industrial_supply_final_package.v1"
MEETING_FILE = "BILAN_SUPPLY_RENDEZ_VOUS_3_VUES.html"
NETWORK_FILE = "RESULTATS_RISQUES_FOURNISSEURS_RESEAU.html"
LAUNCHER_FILE = "OUVRIR_BILAN_SUPPLY_FINAL.html"
MANIFEST_FILE = "package_manifest.json"
MANIFEST_DIGEST_FILE = "package_manifest.sha256.txt"

COMPONENT_SCHEMA = "supplier-021081-final-component-package.v2"
COMPONENT_REPORTING_REVISION = "v3_business_wording"
ACTION_SCHEMA = "etudecas.supplier_v2_controllable_action_selector.v1"
ACTION_SCHEMA_V2 = "etudecas.supplier_v2_controllable_action_selector.v2"
NETWORK_CONSOLIDATION_SCHEMA = (
    "etudecas.supplier_network_post_priority_extension_runner.v1"
)
NETWORK_SCIENTIFIC_OVERLAY_SCHEMA = (
    "etudecas.supplier_network_extension_scientific_overlay.v1"
)
PRIORITY_BOUNDARY_PACKAGE_SCHEMA = (
    "etudecas.supplier_network_priority_boundary_audit_package.v1"
)
PRIORITY_BOUNDARY_RESULT_SCHEMA = "etudecas.supplier_network_priority_boundary_audit.v1"
EXTENSION_AUDIT_PACKAGE_SCHEMA = (
    "etudecas.supplier_network_extension_interpretation_audit_package.v1"
)
EXTENSION_AUDIT_RESULT_SCHEMA = (
    "etudecas.supplier_network_extension_interpretation_audit.v1"
)
PRIORITY_BOUNDARY_BUILDER_SHA256 = (
    "066E6A9046C17325B068641D9803D3857618168CBAA3439732972A41B1BB7F15"
)
EXTENSION_AUDIT_BUILDER_SHA256 = (
    "173FEBFC8EACDA3AF23088F1A3AACD75FDCB3E50884A758C60EA684E229A7C17"
)
SERVICE_SCHEMA = "etudecas.supplier_service_landscape_campaign.v1"
OBSERVED_SCHEMA = "etudecas.observed_2025_supply_bilan.manifest.v1"

ACTION_NETWORK_FILES = {
    "campaign_manifest.json",
    "supplier_sensitivity_ranking.csv",
    "confirmed_top3_stability.csv",
}
ACTION_OUTPUT_FILES = {
    "selected_controllable_action_tests.csv",
    "blocked_action_candidates.csv",
}
OBSERVED_DASHBOARD_FILES = {
    "observed_ca_product_summary_2025.csv",
    "observed_ca_monthly_2025.csv",
    "observed_stock_value_summary_2025.csv",
    "projected_finished_goods_shortage_summary.csv",
    "supplier_risk_prediction_readiness.csv",
}
SCOPE_DASHBOARD_FILES = {
    "supplier_lane_scope.csv",
    "supplier_item_source_coverage.csv",
}
SERVICE_DASHBOARD_FILES = {
    "worst_cases.csv",
    "scenario_summary.csv",
}

EXPECTED_COMPONENT_ROLES = {
    "replay_2025_and_state_layer_demasking_v2",
    "bom_unit_sensitivity_v2",
    "calibration_audited_post_correction_300_384_385_days",
    "orderbook_only_snapshot_v2",
    "orderbook_only_prospective_v2",
    "orderbook_only_001848_paired_multiseed_summary_v2",
    "paired_causal_lot_proof_from_demasking_v2",
}
FORBIDDEN_EXPLORATORY_TOKENS = (
    "active_flow_20260901_v1",
    "state_layer_demasking_20260902_v1",
    "bom_unit_sensitivity_20260902_v1",
    "network_risk_screen_20260902_v1",
    "smoke",
    "pilot",
)
MOJIBAKE_MARKERS = (
    "\ufffd",
    "\u00c3\u00a9",  # Ã©
    "\u00c3\u00a8",  # Ã¨
    "\u00c3\u00a0",  # Ã
    "\u00c3\u00aa",  # Ãª
    "\u00c2\u00ab",  # Â«
    "\u00c2\u00bb",  # Â»
    "\u00e2\u20ac\u2122",  # â€™
    "\u00e2\u20ac\u201c",  # â€“
    "\u00e2\u20ac\u201d",  # â€”
    "\u00c5\u201c",  # Å“
)


class FinalAssemblyError(RuntimeError):
    """Raised when an input or the assembled package is not releasable."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FinalAssemblyError(f"Fichier JSON requis absent : {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FinalAssemblyError(f"JSON UTF-8 invalide : {path}") from error
    if not isinstance(value, dict):
        raise FinalAssemblyError(f"Objet JSON attendu : {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FinalAssemblyError(f"Fichier CSV requis absent : {path}")
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    except UnicodeDecodeError as error:
        raise FinalAssemblyError(f"CSV UTF-8 invalide : {path}") from error


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "oui",
        "pass",
        "passed",
        "complete",
        "completed",
    }


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _safe_child(root: Path, relative: object) -> Path:
    text = str(relative or "").strip().replace("\\", "/")
    if not text or Path(text).is_absolute():
        raise FinalAssemblyError(f"Chemin de sortie relatif invalide : {relative!r}")
    root = root.resolve()
    candidate = (root / text).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise FinalAssemblyError(
            f"Chemin hors du dossier signé : {relative!r}"
        ) from error
    return candidate


def _assert_hash(path: Path, expected: object, *, label: str) -> None:
    expected_text = str(expected or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_text):
        raise FinalAssemblyError(f"Empreinte SHA-256 absente ou invalide ({label}).")
    if not path.is_file() or _sha256(path) != expected_text:
        raise FinalAssemblyError(f"Empreinte SHA-256 incohérente ({label}) : {path}")


def _assert_declared_size(path: Path, expected: object, *, label: str) -> None:
    if expected in (None, ""):
        return
    if _as_int(expected, -1) != path.stat().st_size:
        raise FinalAssemblyError(f"Taille de fichier incohérente ({label}) : {path}")


def _validate_named_hashes(
    root: Path,
    hashes: object,
    *,
    label: str,
    require_nonempty: bool = True,
) -> None:
    if not isinstance(hashes, Mapping) or (require_nonempty and not hashes):
        raise FinalAssemblyError(f"Table d'empreintes absente ({label}).")
    for name, expected in hashes.items():
        path = _safe_child(root, name)
        _assert_hash(path, expected, label=f"{label}/{name}")


def _validate_action_network_hashes(
    root: Path,
    hashes: object,
    *,
    source_network_hashes: Mapping[str, Any] | None,
    label: str,
) -> None:
    """Bind a blocked legacy catalogue to the immutable pre-overlay lineage."""

    if not isinstance(hashes, Mapping) or set(hashes) != ACTION_NETWORK_FILES:
        raise FinalAssemblyError(f"Table d'empreintes absente ou incomplète ({label}).")
    if not isinstance(source_network_hashes, Mapping):
        raise FinalAssemblyError(
            "La lignée neutralisée du réseau manque pour contrôler les leviers."
        )
    for name, expected in hashes.items():
        lineage_hash = str(source_network_hashes.get(name) or "").lower()
        if str(expected or "").lower() != lineage_hash:
            raise FinalAssemblyError(
                f"La sélection de leviers ne correspond pas à la lignée réseau : {name}."
            )
        # The overlay rewrites campaign_manifest.json to neutralise legacy aliases.
        # All other catalogue inputs remain byte-identical to the signed source.
        if name != "campaign_manifest.json":
            _assert_hash(root / name, lineage_hash, label=f"{label}/{name}")


def _contains_forbidden_exploratory_reference(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            _contains_forbidden_exploratory_reference(key)
            or _contains_forbidden_exploratory_reference(child)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_exploratory_reference(child) for child in value)
    text = str(value or "").strip().lower().replace("-", "_")
    return any(token in text for token in FORBIDDEN_EXPLORATORY_TOKENS)


class _HTMLAuditParser(HTMLParser):
    RESOURCE_ATTRIBUTES = {
        "script": ("src",),
        "link": ("href",),
        "img": ("src", "srcset"),
        "iframe": ("src",),
        "source": ("src", "srcset"),
        "video": ("src", "poster"),
        "audio": ("src",),
        "object": ("data",),
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.navigation_hrefs: list[str] = []
        self.resources: list[tuple[str, str, str]] = []
        self.utf8_declared = False
        self.css_fragments: list[str] = []
        self._style_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "style":
            self._style_depth += 1
        if attr_map.get("style"):
            self.css_fragments.append(attr_map["style"])
        identity = attr_map.get("id")
        if identity:
            self.ids.add(identity)
        if tag.lower() == "meta":
            charset = attr_map.get("charset", "").strip().lower().replace("_", "-")
            content = attr_map.get("content", "").lower().replace(" ", "")
            if charset == "utf-8" or "charset=utf-8" in content:
                self.utf8_declared = True
        if tag.lower() == "a" and attr_map.get("href"):
            self.navigation_hrefs.append(attr_map["href"])
        for attribute in self.RESOURCE_ATTRIBUTES.get(tag.lower(), ()):
            value = attr_map.get(attribute)
            if value:
                self.resources.append((tag.lower(), attribute, value))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.css_fragments.append(data)


def _is_remote_reference(value: str) -> bool:
    candidate = value.strip().lower()
    return candidate.startswith(("http://", "https://", "//", "file:", "ftp:"))


def _is_embedded_resource(value: str) -> bool:
    candidate = value.strip().lower()
    return candidate.startswith("data:")


def _read_html_utf8(path: Path) -> tuple[str, _HTMLAuditParser]:
    try:
        document = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise FinalAssemblyError(f"HTML non décodable en UTF-8 : {path}") from error
    marker = next((token for token in MOJIBAKE_MARKERS if token in document), None)
    if marker is not None:
        raise FinalAssemblyError(
            f"Texte corrompu détecté dans {path.name} (marqueur {marker!r})."
        )
    parser = _HTMLAuditParser()
    parser.feed(document)
    parser.close()
    return document, parser


def _resolve_local_href(source: Path, href: str) -> tuple[Path, str]:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        raise FinalAssemblyError(f"Lien non local dans {source.name} : {href}")
    relative = unquote(parsed.path)
    target = source if not relative else (source.parent / relative).resolve()
    return target, unquote(parsed.fragment)


def _validate_html(
    path: Path,
    *,
    validate_navigation: bool,
) -> dict[str, Any]:
    if not path.is_file():
        raise FinalAssemblyError(f"Page HTML absente : {path}")
    document, parser = _read_html_utf8(path)
    if not parser.utf8_declared:
        raise FinalAssemblyError(
            f'Déclaration <meta charset="utf-8"> absente dans {path.name}.'
        )
    remote_resources = [
        f"{tag}[{attribute}]={value}"
        for tag, attribute, value in parser.resources
        if _is_remote_reference(value)
        or re.search(r"(?:https?:)?//", value, flags=re.IGNORECASE)
    ]
    if remote_resources:
        raise FinalAssemblyError(
            f"Ressource distante interdite dans {path.name} : "
            + ", ".join(remote_resources)
        )
    for tag, attribute, value in parser.resources:
        if value.strip() and (
            tag in {"script", "link", "iframe", "object"}
            or not _is_embedded_resource(value)
        ):
            # The generated dashboards must embed their CSS, JS, data and media.
            # Navigation belongs in <a href>, never in a resource attribute.
            raise FinalAssemblyError(
                f"Ressource HTML non embarquée dans {path.name} : "
                f"{tag}[{attribute}]={value}"
            )
    css_document = "\n".join(parser.css_fragments)
    css_resources = re.findall(
        r"url\(\s*['\"]?\s*([^)'\"\s]+)",
        css_document,
        flags=re.IGNORECASE,
    )
    nonembedded_css = [
        value
        for value in css_resources
        if not value.strip().lower().startswith(("data:", "#"))
    ]
    if nonembedded_css:
        raise FinalAssemblyError(
            f"Ressource CSS non embarquée dans {path.name} : {nonembedded_css[0]}"
        )
    if re.search(r"@import\s", css_document, flags=re.IGNORECASE):
        raise FinalAssemblyError(f"Import CSS externe interdit dans {path.name}.")
    checked_links = 0
    if validate_navigation:
        parser_cache: dict[Path, _HTMLAuditParser] = {path.resolve(): parser}
        for href in parser.navigation_hrefs:
            candidate = href.strip()
            if not candidate:
                continue
            if _is_remote_reference(candidate) or candidate.lower().startswith(
                ("javascript:", "mailto:")
            ):
                raise FinalAssemblyError(
                    f"Lien externe ou exécutable interdit dans {path.name} : {href}"
                )
            target, fragment = _resolve_local_href(path, candidate)
            if not target.is_file():
                raise FinalAssemblyError(
                    f"Lien local cassé dans {path.name} : {href} -> {target}"
                )
            checked_links += 1
            if fragment and target.suffix.lower() in {".html", ".htm"}:
                target_resolved = target.resolve()
                target_parser = parser_cache.get(target_resolved)
                if target_parser is None:
                    _, target_parser = _read_html_utf8(target_resolved)
                    parser_cache[target_resolved] = target_parser
                if fragment not in target_parser.ids:
                    raise FinalAssemblyError(
                        f"Ancre locale absente dans {target.name} : #{fragment}"
                    )
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "utf8_valid": True,
        "utf8_declared": True,
        "mojibake_marker_count": 0,
        "external_resource_count": 0,
        "checked_local_navigation_link_count": checked_links,
    }


def _validate_component_package(root: Path) -> tuple[dict[str, Any], Path]:
    root = root.resolve()
    manifest = _read_json(root / "campaign_manifest.json")
    if (
        str(manifest.get("schema_version") or "") != COMPONENT_SCHEMA
        or str(manifest.get("reporting_revision") or "") != COMPONENT_REPORTING_REVISION
        or str(manifest.get("status") or "") != "complete"
        or str(manifest.get("mode") or "") != "audited_v2_reporting_consolidation"
        or not _as_bool(manifest.get("all_execution_packages_audited"))
        or not _as_bool(manifest.get("reproducibility_wording_allowed"))
        or _as_bool(manifest.get("simulation_rerun_by_builder"))
        or _as_bool(manifest.get("previous_outputs_modified"))
    ):
        raise FinalAssemblyError(
            "Le paquet final 021081 avec la révision métier V3 n'est pas libéré."
        )
    source_packages = manifest.get("source_packages")
    if not isinstance(source_packages, list) or len(source_packages) != len(
        EXPECTED_COMPONENT_ROLES
    ):
        raise FinalAssemblyError("Provenance du paquet 021081 incomplète.")
    roles = {
        str(row.get("role") or "")
        for row in source_packages
        if isinstance(row, Mapping)
    }
    if roles != EXPECTED_COMPONENT_ROLES:
        raise FinalAssemblyError(
            "Le paquet 021081 ne contient pas exactement les sept sources auditées attendues."
        )
    if any(
        not isinstance(row, Mapping) or str(row.get("status") or "") != "complete"
        for row in source_packages
    ):
        raise FinalAssemblyError("Une source du paquet 021081 n'est pas complète.")
    if _contains_forbidden_exploratory_reference(manifest):
        raise FinalAssemblyError(
            "Une ancienne campagne exploratoire ou smoke est référencée par le paquet 021081."
        )
    statuses = manifest.get("input_manifest_statuses")
    if (
        not isinstance(statuses, Mapping)
        or not statuses
        or any(str(value or "") != "complete" for value in statuses.values())
    ):
        raise FinalAssemblyError("Statut d'une campagne source 021081 non libéré.")
    outputs = manifest.get("outputs")
    hashes = manifest.get("output_sha256")
    if not isinstance(outputs, Mapping) or not isinstance(hashes, Mapping):
        raise FinalAssemblyError("Sorties signées du paquet 021081 absentes.")
    required_output_keys = {
        "dashboard_payload",
        "observed_order_audit",
        "autonomous_html",
        "autonomous_html_named_copy",
    }
    if not required_output_keys.issubset(outputs):
        raise FinalAssemblyError("Sorties essentielles du paquet 021081 absentes.")
    for name, expected in hashes.items():
        _assert_hash(
            _safe_child(root, name),
            expected,
            label=f"paquet 021081/{name}",
        )
    for key in required_output_keys:
        output_path = _safe_child(root, outputs[key])
        if not output_path.is_file() or output_path.name not in hashes:
            raise FinalAssemblyError(f"Sortie 021081 non signée : {key}")
    payload = _read_json(_safe_child(root, outputs["dashboard_payload"]))
    if str(payload.get("schema_version") or "") != "supplier-021081-final-dashboard.v2":
        raise FinalAssemblyError("Payload métier 021081 autre que V2.")
    service_metric = payload.get("service_metric")
    evidence = payload.get("evidence_dictionary")
    conclusions = payload.get("scientific_conclusions")
    if (
        not isinstance(service_metric, Mapping)
        or str(service_metric.get("metric_id") or "") != "product_on_due_volume_proxy"
        or str(service_metric.get("product_id") or "") != "268967"
        or _as_int(service_metric.get("horizon_days")) != 720
        or "part simulée" not in str(service_metric.get("label_fr") or "").casefold()
        or "ni l’otif"
        not in str(service_metric.get("interpretation_boundary") or "").casefold()
        or not isinstance(evidence, Mapping)
        or set(evidence) != {"observed", "simulated", "priority_signal", "hypothesis"}
        or "date planifiée" not in str(evidence.get("observed") or "").casefold()
        or "performance fournisseur"
        not in str(evidence.get("simulated") or "").casefold()
        or "recommandation automatique"
        not in str(evidence.get("priority_signal") or "").casefold()
        or not isinstance(conclusions, Mapping)
        or "ni une cible ni une action"
        not in str(conclusions.get("target_80") or "").casefold()
        or "aucun niveau de stock n’est recommandé"
        not in str(conclusions.get("target_93") or "").casefold()
        or "aucun effet client, coût ou action n’est démontré"
        not in str(conclusions.get("lots") or "").casefold()
    ):
        raise FinalAssemblyError(
            "Le contrat de vocabulaire métier V3 du paquet 021081 est incomplet."
        )
    component_html = _safe_child(root, outputs["autonomous_html"])
    named_html = _safe_child(root, outputs["autonomous_html_named_copy"])
    if _sha256(component_html) != _sha256(named_html):
        raise FinalAssemblyError("Les deux copies HTML 021081 ne sont pas identiques.")
    _validate_html(component_html, validate_navigation=False)
    component_document = component_html.read_text(encoding="utf-8").casefold()
    required_wording = (
        "commandes planifiées et effets simulés d’incidents",
        "calibrage diagnostique de l’état de stock 773474",
        "unité de nomenclature : l’essai n’arbitre pas",
        "retenue qualité hypothétique de 180 jours",
        "sur 10 simulations appariées testées",
        "ces parts ne sont ni une fréquence historique ni une probabilité fournisseur",
        "ni l’otif d’un fournisseur ni une performance observée",
    )
    if any(phrase not in component_document for phrase in required_wording):
        raise FinalAssemblyError(
            "Une formulation métier obligatoire manque dans la page 021081 V3."
        )
    return manifest, component_html


def _validate_legacy_network_consolidation_unused(root: Path) -> dict[str, Any]:
    raise FinalAssemblyError(
        "Le consolidé historique sans surcouche scientifique n'est plus accepté."
    )
    root = root.resolve()
    campaign = _read_json(root / "campaign_manifest.json")
    consolidation = _read_json(root / "consolidation_manifest.json")
    if (
        str(consolidation.get("schema_version") or "") != NETWORK_CONSOLIDATION_SCHEMA
        or str(consolidation.get("status") or "") != "complete"
        or not str(consolidation.get("consolidation_signature") or "")
        or _as_bool(consolidation.get("large_case_directories_copied"))
        or _as_bool(consolidation.get("source_artifacts_mutated"))
    ):
        raise FinalAssemblyError("La consolidation réseau n'est pas libérée.")
    if (
        str(campaign.get("status") or "") != "complete"
        or str(campaign.get("mode") or "") != "full"
        or not _as_bool(campaign.get("consolidated_additive_artifact"))
        or str(campaign.get("consolidation_signature") or "")
        != str(consolidation.get("consolidation_signature") or "")
        or not _as_bool(campaign.get("source_campaign_complete"))
        or not _as_bool(campaign.get("extension_runner_complete"))
        or _as_bool(campaign.get("previous_artifacts_mutated"))
        or _as_bool(campaign.get("large_case_directories_copied"))
    ):
        raise FinalAssemblyError("Le manifeste réseau consolidé n'est pas libéré.")
    if (
        _contains_forbidden_exploratory_reference(root.name)
        or _contains_forbidden_exploratory_reference(campaign)
        or _contains_forbidden_exploratory_reference(consolidation)
    ):
        raise FinalAssemblyError("Un ancien dossier réseau exploratoire a été fourni.")
    _validate_named_hashes(
        root,
        consolidation.get("source_small_file_hashes"),
        label="réseau/source",
    )
    _validate_named_hashes(
        root,
        consolidation.get("extension_small_file_hashes"),
        label="réseau/extensions",
    )
    extension_manifest_hashes = consolidation.get("extension_manifest_hashes")
    if not isinstance(extension_manifest_hashes, Mapping) or set(
        extension_manifest_hashes
    ) != {
        *network_dashboard.EXTENSIONS,
        "causal_lot_attribution",
    }:
        raise FinalAssemblyError("Empreintes des quatre extensions réseau absentes.")
    extension_manifest_names = {
        key: values[2] for key, values in network_dashboard.EXTENSIONS.items()
    }
    extension_manifest_names["causal_lot_attribution"] = (
        "causal_lot_attribution_manifest.json"
    )
    for key, expected in extension_manifest_hashes.items():
        _assert_hash(
            root / extension_manifest_names[str(key)],
            expected,
            label=f"réseau/manifeste d'extension/{key}",
        )
    return campaign


def _validate_embedded_extension_audit(
    root: Path,
    overlay_manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the signed extension audit embedded in the scientific overlay."""

    manifest = _read_json(root / "extension_interpretation_audit_manifest.json")
    audit = _read_json(root / "scientific_extension_interpretation_audit.json")
    if (
        str(manifest.get("schema_version") or "") != EXTENSION_AUDIT_PACKAGE_SCHEMA
        or str(manifest.get("status") or "") != "complete"
        or str(manifest.get("builder_sha256") or "").upper()
        != EXTENSION_AUDIT_BUILDER_SHA256
        or _as_int(manifest.get("bootstrap_resample_count"), -1) != 10_000
        or _as_bool(manifest.get("previous_artifacts_mutated"))
        or _as_bool(manifest.get("source_artifacts_mutated"))
        or _as_bool(manifest.get("large_case_directories_copied"))
    ):
        raise FinalAssemblyError(
            "Le paquet d'audit scientifique des extensions n'est pas celui validé."
        )
    signature_payload = {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "builder_sha256",
            "source_file_sha256",
            "ledger_case_registry_sha256",
            "artifact_file_sha256",
            "bootstrap_resample_count",
        )
    }
    if str(manifest.get("package_signature") or "") != _canonical_sha256(
        signature_payload
    ) or str(overlay_manifest.get("source_audit_package_signature") or "") != str(
        manifest.get("package_signature") or ""
    ):
        raise FinalAssemblyError(
            "La signature du paquet d'audit des extensions ne correspond pas à la surcouche."
        )
    artifact_hashes = manifest.get("artifact_file_sha256")
    if not isinstance(artifact_hashes, Mapping) or set(artifact_hashes) != set(
        extension_audit.OUTPUT_FILES
    ):
        raise FinalAssemblyError(
            "Inventaire signé de l'audit des extensions incomplet."
        )
    for name, expected in artifact_hashes.items():
        _assert_hash(
            root / str(name),
            expected,
            label=f"audit scientifique des extensions/{name}",
        )
    if (
        str(audit.get("schema_version") or "") != EXTENSION_AUDIT_RESULT_SCHEMA
        or str(audit.get("status") or "") != "complete"
        or _as_int((audit.get("bootstrap") or {}).get("resample_count"), -1) != 10_000
    ):
        raise FinalAssemblyError("Résultat scientifique des extensions invalide.")
    controls = _read_json(root / "scientific_promotion_controls.json")
    required_execution_gates = (
        "execution_integrity_pass",
        "multi_lane_common_cause_execution_integrity_pass",
        "temporal_execution_integrity_pass",
        "four_cause_execution_integrity_pass",
        "causal_lot_pairing_integrity_pass",
    )
    required_false_controls = (
        "global_priority_temporal_robustness_evaluable",
        "global_four_cause_priority_robustness_evaluable",
        "global_network_priority_robustness_evaluable",
        "promotion_allowed",
        "legacy_completion_or_flow_alias_accepted_as_robustness",
        "multi_lane_common_cause_merged_into_one_lane_ranking",
        "multi_lane_common_cause_probability_or_frequency_estimated",
    )
    if (
        str(controls.get("schema_version") or "") != EXTENSION_AUDIT_RESULT_SCHEMA
        or str(controls.get("status") or "") != "scientific_controls_complete"
        or not all(controls.get(field) is True for field in required_execution_gates)
        or not all(controls.get(field) is False for field in required_false_controls)
        or controls.get("network_recovery_metric_status")
        != "excluded_invalid_common_window"
    ):
        raise FinalAssemblyError(
            "Les contrôles scientifiques des extensions ne sont pas fail-closed."
        )
    return audit, controls


def _validate_priority_boundary_audit(
    root: Path,
    *,
    overlay_root: Path,
    overlay_manifest: Mapping[str, Any],
    legacy_consolidation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Validate the boundary package and bind it to the overlaid source campaign."""

    root = root.resolve()
    try:
        boundary_audit.validate_audit_package(root)
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        raise FinalAssemblyError(
            f"Le paquet de frontière statistique est invalide : {error}"
        ) from error
    expected_files = set(boundary_audit.OUTPUT_FILES) | {
        "priority_boundary_audit_manifest.json"
    }
    observed_files = {path.name for path in root.iterdir() if path.is_file()}
    if observed_files != expected_files or any(
        path.is_dir() for path in root.iterdir()
    ):
        raise FinalAssemblyError(
            "Le paquet de frontière statistique contient un fichier non signé ou en omet un."
        )
    manifest = _read_json(root / "priority_boundary_audit_manifest.json")
    audit = _read_json(root / "scientific_priority_boundary_audit.json")
    if (
        str(manifest.get("schema_version") or "") != PRIORITY_BOUNDARY_PACKAGE_SCHEMA
        or str(manifest.get("status") or "") != "complete"
        or str(manifest.get("builder_sha256") or "").upper()
        != PRIORITY_BOUNDARY_BUILDER_SHA256
        or _as_int(manifest.get("bootstrap_resample_count"), -1) != 10_000
        or _as_bool(manifest.get("previous_artifacts_mutated"))
        or _as_bool(manifest.get("source_artifacts_mutated"))
        or _as_bool(manifest.get("large_case_directories_copied"))
    ):
        raise FinalAssemblyError(
            "Le manifeste de frontière statistique n'est pas libéré."
        )
    if (
        str(audit.get("schema_version") or "") != PRIORITY_BOUNDARY_RESULT_SCHEMA
        or str(audit.get("status") or "") != "complete"
        or audit.get("execution_integrity_pass") is not True
        or audit.get("interpretation_prerequisites_pass") is not True
        or audit.get("descriptive_priority_display_inputs_pass") is not True
        or audit.get("scientific_priority_release_inputs_pass") is not False
        or audit.get("industrial_supplier_criticality_claimed") is not False
        or str(audit.get("historical_occurrence_probability") or "") != "not_estimated"
        or str(audit.get("service_priority_scope") or "")
        != boundary_audit.SUPPLIER_ENVELOPE_SCOPE
        or audit.get("scoped_descriptive_priority_set_display_allowed") is not False
        or audit.get("confirmatory_priority_set_release_allowed") is not False
        or audit.get("global_priority_release_allowed") is not False
        or audit.get("action_promotion_allowed") is not False
    ):
        raise FinalAssemblyError(
            "Le résultat de frontière statistique est inexploitable."
        )

    source_hashes = manifest.get("source_file_sha256")
    overlay_source_hashes = overlay_manifest.get("source_consolidated_file_sha256")
    if (
        not isinstance(source_hashes, Mapping)
        or set(source_hashes) != set(boundary_audit.REQUIRED_SOURCE_FILES)
        or not isinstance(overlay_source_hashes, Mapping)
    ):
        raise FinalAssemblyError(
            "Lignée source de la frontière statistique incomplète."
        )
    original_campaign_hash = str(
        legacy_consolidation.get("source_campaign_manifest_sha256") or ""
    ).lower()
    if (
        str(source_hashes.get("campaign_manifest.json") or "").lower()
        != original_campaign_hash
    ):
        raise FinalAssemblyError(
            "La frontière statistique ne provient pas de la campagne source de la surcouche."
        )
    shared_source_names = (
        set(boundary_audit.REQUIRED_SOURCE_FILES) & set(overlay_source_hashes)
    ) - {"campaign_manifest.json", "consolidation_manifest.json"}
    if "confirmation_supplier_sensitivity_ranking.csv" not in shared_source_names:
        raise FinalAssemblyError(
            "La source de classement commune a la surcouche et a la frontiere "
            "statistique n'est pas disponible."
        )
    for name in sorted(shared_source_names):
        expected = str(source_hashes.get(name) or "").lower()
        if expected != str(overlay_source_hashes.get(name) or "").lower():
            raise FinalAssemblyError(
                f"La lignée overlay/frontière diverge pour {name}."
            )
        _assert_hash(
            overlay_root / name,
            expected,
            label=f"lignée overlay/frontière/{name}",
        )

    scoped_release = audit.get("envelope_service_priority_set_release_pass") is True
    scoped_ids = [
        str(value).strip()
        for value in (audit.get("envelope_service_priority_supplier_ids") or [])
        if str(value).strip()
    ]
    service_group = [
        str(value).strip()
        for value in (
            audit.get("envelope_service_nonseparation_group_supplier_ids") or []
        )
        if str(value).strip()
    ]
    universal_group = [
        str(value).strip()
        for value in (
            audit.get("priority_group_supplier_ids_if_no_universal_top3") or []
        )
        if str(value).strip()
    ]
    controls = _read_json(overlay_root / "scientific_promotion_controls.json")
    lineage = controls.get("priority_selection_lineage")
    boundary_lineage_expected = {
        "priority_boundary_package_signature": str(
            manifest.get("package_signature") or ""
        ).lower(),
        "priority_boundary_manifest_sha256": _sha256(
            root / "priority_boundary_audit_manifest.json"
        ),
        "priority_boundary_result_sha256": _sha256(
            root / "scientific_priority_boundary_audit.json"
        ),
        "priority_boundary_ranking_sha256": _sha256(
            root / "supplier_metric_rankings.csv"
        ),
        "priority_boundary_builder_sha256": PRIORITY_BOUNDARY_BUILDER_SHA256.lower(),
        "source_campaign_manifest_sha256": original_campaign_hash,
    }
    boundary_lineage_mismatch = not isinstance(lineage, Mapping) or any(
        str((lineage or {}).get(key) or "").lower() != expected
        for key, expected in boundary_lineage_expected.items()
    )
    invalid_service_group = (
        boundary_lineage_mismatch
        or scoped_release
        or bool(scoped_ids)
        or len(service_group) != 4
        or service_group != sorted(set(service_group))
        or len(universal_group) != 16
        or universal_group != sorted(set(universal_group))
        or not set(service_group) < set(universal_group)
        or service_group != list((lineage or {}).get("follow_up_supplier_ids") or [])
        or service_group
        != list((lineage or {}).get("service_nonseparation_group_supplier_ids") or [])
        or service_group
        != list((lineage or {}).get("selection_candidate_pool_supplier_ids") or [])
        or (lineage or {}).get("follow_up_group_is_unordered") is not True
        or (lineage or {}).get("service_nonseparation_group_fully_followed_up")
        is not True
        or (lineage or {}).get("scoped_descriptive_priority_set_display_allowed")
        is not False
        or (lineage or {}).get("confirmatory_priority_set_release_allowed") is not False
        or (lineage or {}).get("global_priority_release_allowed") is not False
        or (lineage or {}).get("action_promotion_allowed") is not False
    )
    if invalid_service_group:
        raise FinalAssemblyError(
            "Le groupe de quatre dossiers non séparé n'est pas exactement lié "
            "à la frontière statistique vivante."
        )
    return manifest, audit, "service_nonseparation_group_four_follow_up"


def _validate_network_consolidation(
    root: Path,
    priority_boundary_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """Validate the overlay and both audits without trusting legacy release flags."""

    root = root.resolve()
    try:
        extension_audit.validate_scientific_overlay(root)
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        raise FinalAssemblyError(
            f"La surcouche scientifique réseau est invalide : {error}"
        ) from error
    overlay = _read_json(root / "scientific_overlay_manifest.json")
    campaign = _read_json(root / "campaign_manifest.json")
    legacy = _read_json(root / "legacy_consolidation_manifest.json")
    if (
        str(overlay.get("schema_version") or "") != NETWORK_SCIENTIFIC_OVERLAY_SCHEMA
        or str(overlay.get("status") or "") != "complete"
        or str(overlay.get("builder_sha256") or "").upper()
        != EXTENSION_AUDIT_BUILDER_SHA256
        or overlay.get("promotion_allowed") is not False
        or overlay.get("legacy_promotion_aliases_neutralized") is not True
        or _as_bool(overlay.get("source_consolidated_mutated"))
        or _as_bool(overlay.get("source_audit_mutated"))
        or _as_bool(overlay.get("large_files_copied"))
    ):
        raise FinalAssemblyError("La surcouche scientifique réseau n'est pas libérée.")
    overlay_sources = overlay.get("source_consolidated_file_sha256")
    if not isinstance(overlay_sources, Mapping):
        raise FinalAssemblyError("La lignée du consolidé source est absente.")
    _assert_hash(
        root / "legacy_consolidation_manifest.json",
        overlay_sources.get("consolidation_manifest.json"),
        label="surcouche/ancien manifeste de consolidation",
    )
    if (
        str(legacy.get("schema_version") or "") != NETWORK_CONSOLIDATION_SCHEMA
        or str(legacy.get("status") or "") != "complete"
        or str(legacy.get("consolidated_campaign_manifest_sha256") or "").lower()
        != str(overlay_sources.get("campaign_manifest.json") or "").lower()
        or _as_bool(legacy.get("large_case_directories_copied"))
        or _as_bool(legacy.get("source_artifacts_mutated"))
    ):
        raise FinalAssemblyError(
            "La lignée de la consolidation réseau est incohérente."
        )
    if (
        campaign.get("scientific_interpretation_overlay_applied") is not True
        or campaign.get("legacy_runner_promotion_aliases_neutralized") is not True
        or campaign.get("promotion_allowed") is not False
    ):
        raise FinalAssemblyError("Les anciens indicateurs de promotion restent actifs.")
    if (
        _contains_forbidden_exploratory_reference(root.name)
        or _contains_forbidden_exploratory_reference(campaign)
        or _contains_forbidden_exploratory_reference(legacy)
    ):
        raise FinalAssemblyError("Un ancien dossier réseau exploratoire a été fourni.")
    _, controls = _validate_embedded_extension_audit(root, overlay)
    _, boundary, conclusion = _validate_priority_boundary_audit(
        priority_boundary_root,
        overlay_root=root,
        overlay_manifest=overlay,
        legacy_consolidation=legacy,
    )
    return campaign, controls, boundary, conclusion


def _validate_action_selection(
    root: Path,
    network_root: Path,
    *,
    source_network_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / "action_selector_manifest.json")
    status = str(manifest.get("status") or "")
    selection_status = str(manifest.get("selection_status") or "")
    action_catalogue_blocked = bool(
        status == "blocked_network_v2_not_stabilized"
        and selection_status.startswith("blocked_network_v2_")
    )
    if (
        str(manifest.get("schema_version") or "") != ACTION_SCHEMA
        or not action_catalogue_blocked
        or _as_bool(manifest.get("industrial_recommendation_claimed"))
        or not _as_bool(manifest.get("prevention_and_reaction_separated"))
        or _as_bool(manifest.get("sources_mutated"))
        or _as_bool(manifest.get("main_network_ranking_mutated"))
    ):
        raise FinalAssemblyError("La sélection de leviers n'est pas libérée.")
    hard_exclusions = manifest.get("hard_exclusions")
    if (
        not isinstance(hard_exclusions, Mapping)
        or not hard_exclusions
        or not all(_as_bool(value) for value in hard_exclusions.values())
    ):
        raise FinalAssemblyError(
            "Les exclusions opérationnelles des leviers sont incomplètes."
        )
    network_hashes = (
        manifest.get("source_hashes", {}).get("network", {})
        if isinstance(manifest.get("source_hashes"), Mapping)
        else {}
    )
    if (
        not isinstance(network_hashes, Mapping)
        or set(network_hashes) != ACTION_NETWORK_FILES
    ):
        raise FinalAssemblyError(
            "La sélection de leviers n'est pas liée aux trois sorties réseau attendues."
        )
    _validate_action_network_hashes(
        network_root.resolve(),
        network_hashes,
        source_network_hashes=source_network_hashes,
        label="sélection de leviers/réseau",
    )
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or set(map(str, outputs)) != ACTION_OUTPUT_FILES:
        raise FinalAssemblyError("Inventaire des sorties de leviers incomplet.")
    selected = _read_csv(root / "selected_controllable_action_tests.csv")
    blocked_rows = _read_csv(root / "blocked_action_candidates.csv")
    if len(selected) != _as_int(manifest.get("selected_action_test_count"), -1):
        raise FinalAssemblyError("Nombre de leviers prêts incohérent.")
    if len(blocked_rows) != _as_int(manifest.get("blocked_action_candidate_count"), -1):
        raise FinalAssemblyError("Nombre de leviers bloqués incohérent.")
    if selected or _as_int(manifest.get("selected_action_test_count"), -1) != 0:
        raise FinalAssemblyError(
            "Une sélection bloquée ne peut publier aucune ligne comme prête."
        )
    return manifest


def _validate_scientific_action_selection(
    root: Path,
    *,
    network_root: Path,
    boundary_root: Path,
    boundary: Mapping[str, Any],
    network_conclusion: str,
    source_network_hashes: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Accept only a fail-closed action catalogue tied to both signed audits."""

    root = root.resolve()
    manifest = _read_json(root / "action_selector_manifest.json")
    schema = str(manifest.get("schema_version") or "")
    if schema == ACTION_SCHEMA:
        if network_conclusion != "priority_group_not_separated":
            raise FinalAssemblyError(
                "L'ancien catalogue bloqué ne peut pas accompagner un trio sous enveloppe."
            )
        return _validate_action_selection(
            root,
            network_root,
            source_network_hashes=source_network_hashes,
        )
    if schema != ACTION_SCHEMA_V2:
        raise FinalAssemblyError("Version du catalogue de leviers inconnue.")

    v3_service_group = (
        str(manifest.get("status") or "")
        == "blocked_service_nonseparation_group_follow_up"
    )
    scoped = network_conclusion == "envelope_service_top3_scoped"
    if v3_service_group:
        expected_status = "blocked_service_nonseparation_group_follow_up"
        expected_selection_status = "service_nonseparation_group_action_candidates_only"
        expected_candidates = list(
            boundary.get("envelope_service_nonseparation_group_supplier_ids") or []
        )
        controls = _read_json(network_root / "scientific_promotion_controls.json")
        lineage = controls.get("priority_selection_lineage")
        if not isinstance(lineage, Mapping):
            raise FinalAssemblyError("Lignee V3 absente des controles scientifiques.")
        if (
            len(expected_candidates) != 4
            or expected_candidates != list(lineage.get("follow_up_supplier_ids") or [])
            or expected_candidates
            != list(lineage.get("service_nonseparation_group_supplier_ids") or [])
            or expected_candidates
            != list(lineage.get("selection_candidate_pool_supplier_ids") or [])
            or controls.get("execution_integrity_pass") is not True
            or controls.get("promotion_allowed") is not False
            or controls.get("action_promotion_allowed") is not False
            or controls.get("global_network_priority_robustness_evaluable") is not False
            or lineage.get("follow_up_group_is_unordered") is not True
            or lineage.get("service_nonseparation_group_fully_followed_up") is not True
        ):
            raise FinalAssemblyError("Groupe service V3 incoherent dans les actions.")
    else:
        expected_status = (
            "blocked_scoped_priority_not_globally_released"
            if scoped
            else "blocked_priority_boundary_unresolved"
        )
        expected_selection_status = (
            "scoped_envelope_action_candidates_only"
            if scoped
            else "unseparated_priority_group_action_candidates_only"
        )
        expected_candidates = list(
            boundary.get(
                "envelope_service_priority_supplier_ids"
                if scoped
                else "priority_group_supplier_ids_if_no_universal_top3"
            )
            or []
        )
    candidate_ids = list(manifest.get("candidate_supplier_ids") or [])
    if (
        str(manifest.get("status") or "") != expected_status
        or str(manifest.get("selection_status") or "") != expected_selection_status
        or candidate_ids != expected_candidates
        or len(candidate_ids) != len(set(map(str, candidate_ids)))
        or list(manifest.get("selected_supplier_ids") or [])
        or _as_int(manifest.get("selected_action_test_count"), -1) != 0
        or _as_int(manifest.get("blocked_action_candidate_count"), -1) <= 0
        or _as_int(manifest.get("scientific_blocked_candidate_count"), -1)
        != _as_int(manifest.get("blocked_action_candidate_count"), -2)
        or manifest.get("action_readiness_pass") is not False
        or _as_bool(manifest.get("industrial_recommendation_claimed"))
        or not _as_bool(manifest.get("prevention_and_reaction_separated"))
        or _as_bool(manifest.get("sources_mutated"))
        or _as_bool(manifest.get("main_network_ranking_mutated"))
    ):
        raise FinalAssemblyError(
            "Le catalogue scientifique de leviers n'est pas fail-closed."
        )
    if v3_service_group:
        expected_chains = list(lineage.get("follow_up_chain_ids") or [])
        expected_mappings = list(lineage.get("follow_up_driver_mappings") or [])
        if (
            len(expected_chains) != 4
            or len(set(map(str, expected_chains))) != 4
            or list(manifest.get("follow_up_chain_ids") or []) != expected_chains
            or list(manifest.get("follow_up_driver_mappings") or [])
            != expected_mappings
            or manifest.get("follow_up_group_supplier_count") != 4
            or manifest.get("follow_up_group_is_unordered") is not True
            or str(manifest.get("priority_selection_lineage_sha256") or "")
            != str(controls.get("priority_selection_lineage_sha256") or "")
        ):
            raise FinalAssemblyError("Voies ou lignee V3 des actions incoherentes.")
    hard_exclusions = manifest.get("hard_exclusions")
    if (
        not isinstance(hard_exclusions, Mapping)
        or not hard_exclusions
        or not all(_as_bool(value) for value in hard_exclusions.values())
    ):
        raise FinalAssemblyError(
            "Les exclusions opérationnelles des leviers sont incomplètes."
        )

    scientific_hashes = (
        manifest.get("source_hashes", {}).get("scientific", {})
        if isinstance(manifest.get("source_hashes"), Mapping)
        else {}
    )
    if (
        not isinstance(scientific_hashes, Mapping)
        or set(scientific_hashes) != {"network_overlay", "priority_boundary_audit"}
        or not isinstance(scientific_hashes.get("network_overlay"), Mapping)
        or set(scientific_hashes["network_overlay"])
        != {
            "scientific_overlay_manifest.json",
            "scientific_promotion_controls.json",
        }
        or not isinstance(scientific_hashes.get("priority_boundary_audit"), Mapping)
        or set(scientific_hashes["priority_boundary_audit"])
        != {
            "priority_boundary_audit_manifest.json",
            "scientific_priority_boundary_audit.json",
        }
    ):
        raise FinalAssemblyError("Empreintes scientifiques des leviers incomplètes.")
    _validate_named_hashes(
        network_root,
        scientific_hashes["network_overlay"],
        label="leviers/surcouche scientifique",
    )
    _validate_named_hashes(
        boundary_root,
        scientific_hashes["priority_boundary_audit"],
        label="leviers/frontière statistique",
    )
    action_source_hashes = manifest.get("source_hashes") or {}
    if v3_service_group and (
        not re.fullmatch(
            r"[0-9a-f]{64}",
            str(action_source_hashes.get("action_input_manifest_sha256") or ""),
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(action_source_hashes.get("action_input_generation_signature") or ""),
        )
    ):
        raise FinalAssemblyError("Lignee du paquet d'entree action absente.")
    network_hashes = (
        manifest.get("source_hashes", {}).get("network", {})
        if isinstance(manifest.get("source_hashes"), Mapping)
        else {}
    )
    if network_hashes:
        _validate_action_network_hashes(
            network_root,
            network_hashes,
            source_network_hashes=source_network_hashes,
            label="leviers/lignée réseau",
        )

    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or set(map(str, outputs)) != ACTION_OUTPUT_FILES:
        raise FinalAssemblyError("Inventaire des sorties de leviers incomplet.")
    selected_rows = _read_csv(root / "selected_controllable_action_tests.csv")
    blocked_rows = _read_csv(root / "blocked_action_candidates.csv")
    if selected_rows or len(blocked_rows) != _as_int(
        manifest.get("blocked_action_candidate_count"), -1
    ):
        raise FinalAssemblyError("Comptage du catalogue bloqué incohérent.")
    expected_candidate_scope = (
        "boundary_envelope_service_nonseparation_group"
        if v3_service_group
        else (
            "boundary_envelope_service_priority"
            if scoped
            else "unseparated_priority_group"
        )
    )
    operationally_ready_count = 0
    observed_action_suppliers: set[str] = set()
    observed_action_chains: set[str] = set()
    expected_chain_by_supplier = (
        {
            str(row.get("supplier_id") or ""): str(row.get("driver_chain_id") or "")
            for row in lineage.get("follow_up_driver_mappings") or []
        }
        if v3_service_group
        else {}
    )
    explicit_false = {"0", "false", "no", "non"}
    for row in blocked_rows:
        if v3_service_group:
            supplier_id = str(row.get("supplier_id") or "")
            row_chains = {
                value
                for value in str(row.get("network_chain_ids") or "").split("|")
                if value
            }
            if row_chains != {expected_chain_by_supplier.get(supplier_id, "")}:
                raise FinalAssemblyError(
                    "Une action sort des quatre voies V3 approfondies."
                )
            observed_action_suppliers.add(supplier_id)
            observed_action_chains.update(row_chains)
        raw_reasons = str(row.get("blocking_reasons") or "")
        raw_operational_reasons = str(
            row.get("operational_prerequisite_blocking_reasons") or ""
        )
        reasons = {
            reason.strip() for reason in raw_reasons.split("|") if reason.strip()
        }
        operational_reasons = {
            reason.strip()
            for reason in raw_operational_reasons.split("|")
            if reason.strip()
        }
        operational_pass = _as_bool(row.get("operational_prerequisite_gate_pass"))
        operationally_ready_count += int(operational_pass)
        if (
            str(row.get("selector_status") or "") != "blocked"
            or str(row.get("candidate_scope") or "") != expected_candidate_scope
            or str(row.get("scientific_release_gate_pass") or "").strip().lower()
            not in explicit_false
            or str(row.get("scientific_blocking_reason") or "")
            != "scientific_global_priority_not_released"
            or not _as_bool(row.get("future_test_only_not_recommendation"))
            or operational_pass == bool(operational_reasons)
            or reasons
            != operational_reasons | {"scientific_global_priority_not_released"}
            or raw_operational_reasons != "|".join(sorted(operational_reasons))
            or raw_reasons != "|".join(sorted(reasons))
        ):
            raise FinalAssemblyError(
                "Une ligne de levier n'explicite pas son blocage scientifique."
            )
    if operationally_ready_count != _as_int(
        manifest.get("operationally_ready_but_scientifically_blocked_count"), -1
    ):
        raise FinalAssemblyError(
            "Le comptage des leviers prêts mais scientifiquement bloqués est incohérent."
        )
    if v3_service_group and (
        observed_action_suppliers != set(map(str, expected_candidates))
        or observed_action_chains != set(map(str, expected_chains))
    ):
        raise FinalAssemblyError("Couverture des actions V3 incomplete ou elargie.")
    return manifest


def _validate_legacy_network_release_unused(
    root: Path,
    action_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    raise FinalAssemblyError(
        "Les anciens release_gate et priority_set_stabilized ne constituent pas une preuve."
    )
    campaign = _validate_network_consolidation(root)
    action_manifest = _validate_action_selection(action_root, root)
    try:
        data = network_dashboard.load_network_results(
            root,
            action_selection_dir=action_root,
        )
    except (FileNotFoundError, ValueError) as error:
        raise FinalAssemblyError(
            f"Les conditions de publication réseau ne sont pas satisfaites : {error}"
        ) from error
    extension_passes = data.get("extension_passes")
    stable_priority_count = len(data.get("stable_priorities") or [])
    main_physical_release = network_dashboard._main_release_pass(campaign)
    if (
        _as_int(campaign.get("confirmation_seed_count")) != 30
        or not main_physical_release
        or not data.get("ranking")
        or not isinstance(extension_passes, Mapping)
        or set(extension_passes) != set(network_dashboard.EXTENSIONS)
        or not all(_as_bool(value) for value in extension_passes.values())
        or not _as_bool(data.get("causal_released"))
    ):
        raise FinalAssemblyError(
            "Le réseau complet, ses contrôles physiques, ses quatre extensions "
            "ou ses lots causaux ne sont pas libérés."
        )
    actions = data.get("actions") if isinstance(data.get("actions"), Mapping) else {}
    action_status = str(action_manifest.get("status") or "")
    if stable_priority_count == 3:
        if action_status != "prepared" or not _as_bool(actions.get("released")):
            raise FinalAssemblyError(
                "Un top 3 stabilisé exige une sélection de leviers préparée et liée au réseau."
            )
        conclusion = "stable_top3"
    elif stable_priority_count == 0:
        if (
            action_status != "blocked_network_v2_not_stabilized"
            or _as_bool(actions.get("released"))
            or actions.get("selected")
            or actions.get("blocked")
        ):
            raise FinalAssemblyError(
                "Un classement non tranché exige des leviers bloqués et des compteurs masqués."
            )
        conclusion = "priority_group_not_separated"
    else:
        raise FinalAssemblyError(
            "Le réseau ne peut publier ni un top 3 partiel, ni un classement ambigu."
        )
    return campaign, action_manifest, conclusion


def _validate_network_release(
    root: Path,
    priority_boundary_root: Path,
    action_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    campaign, controls, boundary, conclusion = _validate_network_consolidation(
        root, priority_boundary_root
    )
    overlay_manifest = _read_json(root.resolve() / "scientific_overlay_manifest.json")
    source_hashes = overlay_manifest.get("source_consolidated_file_sha256")
    action_manifest = _validate_scientific_action_selection(
        action_root,
        network_root=root,
        boundary_root=priority_boundary_root,
        boundary=boundary,
        network_conclusion=conclusion,
        source_network_hashes=(
            source_hashes if isinstance(source_hashes, Mapping) else None
        ),
    )
    try:
        data = network_dashboard.load_network_results(
            root,
            priority_boundary_audit_dir=priority_boundary_root,
            action_selection_dir=action_root,
        )
    except (FileNotFoundError, TypeError, ValueError) as error:
        raise FinalAssemblyError(
            f"Les conditions de publication réseau ne sont pas satisfaites : {error}"
        ) from error
    stable_priority_count = len(data.get("stable_priorities") or [])
    expected_stable_priority_count = (
        3 if conclusion == "envelope_service_top3_scoped" else 0
    )
    expected_reporting_status = (
        "envelope_service_top3_released"
        if conclusion == "envelope_service_top3_scoped"
        else "priority_group_only"
    )
    expected_priority_group = boundary.get(
        "envelope_service_nonseparation_group_supplier_ids"
    )
    if (
        _as_int((boundary.get("bootstrap") or {}).get("paired_seed_count"), -1) != 30
        or not data.get("ranking")
        or stable_priority_count != expected_stable_priority_count
        or data.get("priority_reporting_status") != expected_reporting_status
        or data.get("input_status") != "signed_scientific_overlay_and_audits_valid"
        or data.get("priority_group_supplier_ids") != expected_priority_group
        or len(data.get("lot_genealogical_detail") or []) == 0
        or data.get("legacy_priority_flags_ignored") is not True
        or data.get("legacy_extension_release_aliases_ignored") is not True
        or controls.get("global_network_priority_robustness_evaluable") is not False
        or controls.get("promotion_allowed") is not False
    ):
        raise FinalAssemblyError(
            "Le réseau ne respecte pas la frontière scientifique signée."
        )
    actions = data.get("actions") if isinstance(data.get("actions"), Mapping) else {}
    if _as_bool(actions.get("released")) or actions.get("selected"):
        raise FinalAssemblyError(
            "Les leviers doivent rester un catalogue bloqué, sans action prête."
        )
    return campaign, controls, action_manifest, conclusion


def _validate_observed(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / "manifest.json")
    if str(manifest.get("schema_version") or "") != OBSERVED_SCHEMA or not _as_bool(
        manifest.get("all_validation_checks_pass")
    ):
        raise FinalAssemblyError("Le bilan observé 2025 n'a pas passé ses contrôles.")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise FinalAssemblyError("Inventaire signé du bilan observé absent.")
    declared_names: set[str] = set()
    for record in files:
        if not isinstance(record, Mapping):
            raise FinalAssemblyError("Inventaire observé invalide.")
        path = _safe_child(root, record.get("name"))
        if path.name in declared_names:
            raise FinalAssemblyError(f"Sortie observée dupliquée : {path.name}")
        declared_names.add(path.name)
        _assert_hash(path, record.get("sha256"), label=f"observé/{path.name}")
        _assert_declared_size(
            path, record.get("size_bytes"), label=f"observé/{path.name}"
        )
    if not OBSERVED_DASHBOARD_FILES.issubset(declared_names):
        raise FinalAssemblyError("Entrées observées du dashboard non toutes signées.")
    return manifest


def _validate_scope(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / "manifest.json")
    required_files = tuple(sorted(SCOPE_DASHBOARD_FILES))
    outputs = manifest.get("outputs")
    if (
        str(manifest.get("schema_version") or "")
        != "etudecas.supplier_network_scope_audit.v1"
        or str(manifest.get("status") or "") != "complete"
        or not _as_bool(manifest.get("not_a_risk_ranking"))
        or _as_int(manifest.get("lane_count")) <= 0
        or any(not (root / name).is_file() for name in required_files)
        or not isinstance(outputs, list)
        or not SCOPE_DASHBOARD_FILES.issubset(set(map(str, outputs)))
        or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("graph_sha256") or ""))
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(manifest.get("order_audit_sha256") or "")
        )
    ):
        raise FinalAssemblyError("L'audit de couverture réseau n'est pas complet.")
    return manifest


def _validate_manifest_outputs(
    root: Path,
    *,
    expected_schema: str,
    required_summary_fields: set[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / "manifest.json")
    if (
        str(manifest.get("schema_version") or "") != expected_schema
        or str(manifest.get("status") or "") != "complete"
    ):
        raise FinalAssemblyError(f"Audit non complet : {root}")
    if required_summary_fields:
        summary = manifest.get("summary")
        if not isinstance(summary, Mapping) or not required_summary_fields.issubset(
            summary
        ):
            raise FinalAssemblyError(f"Résumé d'audit incomplet : {root}")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise FinalAssemblyError(f"Sorties signées absentes : {root}")
    for record in outputs:
        if not isinstance(record, Mapping):
            raise FinalAssemblyError(f"Inventaire de sorties invalide : {root}")
        relative = record.get("name") if "name" in record else record.get("path")
        path = _safe_child(root, relative)
        _assert_hash(path, record.get("sha256"), label=f"audit/{path.name}")
        _assert_declared_size(
            path, record.get("size_bytes"), label=f"audit/{path.name}"
        )
    return manifest


def _validate_service_landscape(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / "campaign_manifest.json")
    seeds = manifest.get("confirmation_seeds")
    guard = manifest.get("baseline_quality_guard")
    required_files = tuple(sorted(SERVICE_DASHBOARD_FILES))
    outputs = manifest.get("outputs")
    required_hashes = (
        "campaign_signature",
        "engine_sha256",
        "engine_profile_sha256",
        "graph_sha256",
        "prepared_supplier_floors_content_sha256",
    )
    if (
        str(manifest.get("schema_version") or "") != SERVICE_SCHEMA
        or str(manifest.get("status") or "") != "complete"
        or str(manifest.get("evidence_class") or "")
        != "exploratory_simulation_hypothesis"
        or not _as_bool(manifest.get("common_random_numbers"))
        or not isinstance(seeds, list)
        or len(seeds) < 10
        or len(set(map(str, seeds))) != len(seeds)
        or _as_int(manifest.get("confirmation_valid_rows")) <= 0
        or _as_bool(manifest.get("graph_mutated"))
        or _as_bool(manifest.get("demand_mutated"))
        or _as_bool(manifest.get("service_mutated"))
        or not isinstance(guard, Mapping)
        or float(guard.get("minimum_product_on_due_proxy") or 0) < 0.95
        or any(not str(manifest.get(key) or "") for key in required_hashes)
        or any(not (root / name).is_file() for name in required_files)
        or not isinstance(outputs, Mapping)
        or {
            Path(str(outputs.get("worst_cases_csv") or "")).name,
            Path(str(outputs.get("scenario_summary_csv") or "")).name,
        }
        != SERVICE_DASHBOARD_FILES
        or _contains_forbidden_exploratory_reference(root.name)
    ):
        raise FinalAssemblyError(
            "La campagne 80/93 n'a pas une provenance complète et appariée."
        )
    rows = _read_csv(root / "worst_cases.csv")
    if not rows or any(_as_int(row.get("n_seeds")) < 10 for row in rows):
        raise FinalAssemblyError(
            "Résultats 80/93 incomplets ou insuffisamment répétés."
        )
    return manifest


def _relative_href(source: Path, target: Path) -> str:
    return Path(os.path.relpath(target.resolve(), source.parent.resolve())).as_posix()


def _record_snapshot(
    snapshot: dict[str, dict[str, Any]],
    *,
    label: str,
    path: Path,
) -> None:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FinalAssemblyError(f"Entrée consommée absente ({label}) : {resolved}")
    snapshot[label] = {
        "path": resolved,
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _collect_consumed_input_snapshot(
    *,
    paths: Mapping[str, Path],
    component_manifest: Mapping[str, Any],
    action_manifest: Mapping[str, Any],
    observed_manifest: Mapping[str, Any],
    scope_manifest: Mapping[str, Any],
    action_audit_manifest: Mapping[str, Any],
    source_audit_manifest: Mapping[str, Any],
    service_root: Path | None,
) -> dict[str, dict[str, Any]]:
    """Hash every compact source that can influence a generated page."""

    snapshot: dict[str, dict[str, Any]] = {}

    def add(label: str, path: Path) -> None:
        _record_snapshot(snapshot, label=label, path=path)

    network_root = paths["network_final"]
    add(
        "network/scientific_overlay_manifest.json",
        network_root / "scientific_overlay_manifest.json",
    )
    overlay_manifest = _read_json(network_root / "scientific_overlay_manifest.json")
    overlay_hashes = overlay_manifest.get("artifact_file_sha256")
    if not isinstance(overlay_hashes, Mapping):
        raise FinalAssemblyError("Inventaire signé de la surcouche réseau absent.")
    for name in overlay_hashes:
        add(f"network/{name}", _safe_child(network_root, name))

    boundary_root = paths["network_boundary_audit"]
    add(
        "network_boundary/priority_boundary_audit_manifest.json",
        boundary_root / "priority_boundary_audit_manifest.json",
    )
    boundary_manifest = _read_json(
        boundary_root / "priority_boundary_audit_manifest.json"
    )
    boundary_hashes = boundary_manifest.get("artifact_file_sha256")
    if not isinstance(boundary_hashes, Mapping):
        raise FinalAssemblyError("Inventaire signé de la frontière statistique absent.")
    for name in boundary_hashes:
        add(f"network_boundary/{name}", _safe_child(boundary_root, name))

    component_root = paths["component_021081_final"]
    add("component/campaign_manifest.json", component_root / "campaign_manifest.json")
    component_hashes = component_manifest.get("output_sha256")
    if isinstance(component_hashes, Mapping):
        for name in component_hashes:
            add(f"component/{name}", _safe_child(component_root, name))

    action_root = paths["action_selection_final"]
    add(
        "actions/action_selector_manifest.json",
        action_root / "action_selector_manifest.json",
    )
    for name in action_manifest.get("outputs", []):
        add(f"actions/{name}", _safe_child(action_root, name))

    observed_root = paths["observed"]
    add("observed/manifest.json", observed_root / "manifest.json")
    for record in observed_manifest.get("files", []):
        if isinstance(record, Mapping):
            name = str(record.get("name") or "")
            if (
                name in OBSERVED_DASHBOARD_FILES
                or name == "component_021081_physical_context.csv"
            ):
                add(f"observed/{name}", _safe_child(observed_root, name))

    scope_root = paths["scope"]
    add("scope/manifest.json", scope_root / "manifest.json")
    for name in scope_manifest.get("outputs", []):
        if (
            str(name) in SCOPE_DASHBOARD_FILES
            or str(name) == "data_quality_findings.csv"
        ):
            add(f"scope/{name}", _safe_child(scope_root, name))

    for prefix, root_key, manifest in (
        ("action_audit", "action_audit", action_audit_manifest),
        ("supplier_source_audit", "supplier_source_audit", source_audit_manifest),
    ):
        root = paths[root_key]
        add(f"{prefix}/manifest.json", root / "manifest.json")
        for record in manifest.get("outputs", []):
            if isinstance(record, Mapping):
                name = record.get("name") if "name" in record else record.get("path")
                add(f"{prefix}/{name}", _safe_child(root, name))

    if service_root is not None:
        add("service/campaign_manifest.json", service_root / "campaign_manifest.json")
        for name in sorted(SERVICE_DASHBOARD_FILES):
            add(f"service/{name}", service_root / name)

    add("network_map/html", paths["network_map"])
    return snapshot


def _assert_snapshot_unchanged(snapshot: Mapping[str, Mapping[str, Any]]) -> None:
    for label, record in snapshot.items():
        path = Path(str(record["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != _as_int(record.get("size_bytes"), -1)
            or _sha256(path) != str(record.get("sha256") or "")
        ):
            raise FinalAssemblyError(
                f"Une entrée a changé pendant l'assemblage : {label}"
            )


def _render_launcher(
    *,
    output: Path,
    meeting_html: Path,
    network_html: Path,
    component_html: Path,
    map_html: Path,
    service_used: bool,
) -> str:
    links = {
        "meeting": _relative_href(output, meeting_html),
        "network": _relative_href(output, network_html),
        "component": _relative_href(output, component_html),
        "map": _relative_href(output, map_html),
    }
    service_note = (
        "Les configurations 80 % et 93 % sont affichées comme simulations "
        "conditionnelles, jamais comme performance observée d'un fournisseur."
        if service_used
        else "Les anciennes cartes 80 % / 93 % ont été masquées faute de preuve suffisante."
    )
    secondary_cards = (
        (
            "network",
            "Voir tous les résultats réseau",
            "Fournisseurs, voies, exposition généalogique et écarts causaux appariés.",
        ),
        (
            "component",
            "Ouvrir le dossier 021081",
            "Lignes planifiées, masquage et limites de traçabilité.",
        ),
        (
            "map",
            "Ouvrir la carte autonome",
            "Carte complète existante, conservée sans modification.",
        ),
    )
    secondary_html = "".join(
        f'<a class="card" href="{html.escape(links[key], quote=True)}">'
        f"<b>{html.escape(title)}</b><span>{html.escape(description)}</span></a>"
        for key, title, description in secondary_cards
    )
    return f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilan supply — accès au rendez-vous</title><style>
:root{{--navy:#123b63;--blue:#276fae;--ink:#15314c;--muted:#60758a;--line:#d7e2ec;--bg:#edf3f8}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Segoe UI,Arial,sans-serif}}main{{max-width:1050px;margin:0 auto;padding:40px 24px 64px}}header{{padding:31px 34px;border-radius:24px;background:linear-gradient(125deg,var(--navy),var(--blue));color:#fff;box-shadow:0 18px 45px #163c6022}}small{{font-weight:800;letter-spacing:.12em}}h1{{margin:8px 0 10px;font-size:clamp(31px,5vw,52px);line-height:1.06}}h2{{margin:28px 0 10px;font-size:21px}}header p{{max-width:760px;margin:0;color:#e1edf7}}.primary{{display:flex;justify-content:space-between;gap:25px;align-items:center;margin-top:20px;padding:24px 27px;border-radius:18px;background:#fff;color:var(--ink);text-decoration:none;border:2px solid #76a5ce;box-shadow:0 10px 28px #173d6114}}.primary b,.primary span{{display:block}}.primary b{{font-size:24px}}.primary span{{margin-top:5px;color:var(--muted)}}.primary em{{font-style:normal;font-weight:800;color:var(--blue);white-space:nowrap}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-top:12px}}.card{{display:block;min-height:145px;padding:23px;border:1px solid var(--line);border-radius:18px;background:#fff;color:var(--ink);text-decoration:none;box-shadow:0 8px 25px #173d6110}}.primary:hover,.card:hover{{border-color:var(--blue);transform:translateY(-2px)}}.card b,.card span{{display:block}}.card b{{font-size:19px}}.card span{{margin-top:9px;color:var(--muted)}}.note,.boundaries{{padding:16px 19px;margin-top:18px;border-radius:10px;background:#fffaf1}}.note{{border-left:5px solid #cf8428}}.boundaries{{border-left:5px solid #6e8498;background:#f8fafc;color:#40566b}}footer{{margin-top:18px;text-align:center;color:var(--muted);font-size:13px}}@media(max-width:720px){{.grid{{grid-template-columns:1fr}}.primary{{display:block}}.primary em{{display:block;margin-top:14px}}main{{padding:18px 14px}}header{{padding:24px}}}}
</style></head><body><main><header><small>PARCOURS INDUSTRIEL AUTONOME</small><h1>Sensibilité conditionnelle aux incidents fournisseurs</h1><p>Un parcours principal de trois vues, du problème à la décision. Il compare les conséquences d’incidents imposés ; il ne prévoit pas leur probabilité. Toutes les pages fonctionnent hors connexion.</p></header><a class="primary" href="{html.escape(links["meeting"], quote=True)}"><span><b>Commencer le rendez-vous</b><span>Vue 1 : 338929 · Vue 2 : cascade qualité et lots · Vue 3 : décisions et bilan 2025.</span></span><em>Ouvrir les 3 vues →</em></a><h2>Approfondir seulement si nécessaire</h2><section class="grid">{secondary_html}</section><p class="note"><b>Règle de lecture.</b> {html.escape(service_note)} Les signaux simulés ne sont ni un OTIF observé, ni une probabilité d'incident, ni une cotation fournisseur.</p><p class="boundaries"><b>Frontières de décision.</b> Les pertes ou valeurs non réalisées 2025 ne sont attribuées à aucun fournisseur. Les anciens essais d’actions sont un audit exploratoire séparé, pas la sélection finale de leviers ; leurs coûts sont des indices du modèle, sans unité monétaire et non comparables aux montants 2025. Un lot exposé par généalogie n’est pas nécessairement causalement modifié : le détail réseau distingue les deux. Dans le dossier 021081 V3, aucun effet aval, client, coût ou action n’est démontré.</p><footer>Nouveau paquet additif : aucune simulation, aucun cold-start et aucun HTML antérieur n'a été remplacé.</footer></main></body></html>'''


def build_final_package(
    *,
    network_final_dir: Path,
    network_boundary_audit_dir: Path,
    component_021081_final_dir: Path,
    action_selection_final_dir: Path,
    observed_dir: Path,
    scope_dir: Path,
    action_audit_dir: Path,
    supplier_source_audit_dir: Path,
    network_map_html: Path,
    output_dir: Path,
    service_landscape_dir: Path | None = None,
    generated_label: str = "le 2 septembre 2026",
) -> dict[str, Any]:
    """Build a new, validated package; never replace an existing directory."""

    paths = {
        "network_final": network_final_dir.resolve(),
        "network_boundary_audit": network_boundary_audit_dir.resolve(),
        "component_021081_final": component_021081_final_dir.resolve(),
        "action_selection_final": action_selection_final_dir.resolve(),
        "observed": observed_dir.resolve(),
        "scope": scope_dir.resolve(),
        "action_audit": action_audit_dir.resolve(),
        "supplier_source_audit": supplier_source_audit_dir.resolve(),
        "network_map": network_map_html.resolve(),
    }
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FinalAssemblyError(
            f"Le dossier final doit être nouveau et ne sera pas remplacé : {output_dir}"
        )
    dynamic_input_keys = (
        "network_final",
        "network_boundary_audit",
        "component_021081_final",
        "action_selection_final",
    )
    if len({paths[key] for key in dynamic_input_keys}) != len(dynamic_input_keys):
        raise FinalAssemblyError("Les trois dossiers finaux doivent être distincts.")
    protected_roots = {
        paths[key]
        for key in (
            "network_final",
            "network_boundary_audit",
            "component_021081_final",
            "action_selection_final",
            "observed",
            "scope",
            "action_audit",
            "supplier_source_audit",
        )
    }
    for protected_root in protected_roots:
        try:
            output_dir.relative_to(protected_root)
        except ValueError:
            continue
        raise FinalAssemblyError(
            "Le nouveau paquet ne peut pas être créé dans un dossier source : "
            f"{protected_root}"
        )

    component_manifest, component_html = _validate_component_package(
        paths["component_021081_final"]
    )
    network_manifest, scientific_controls, action_manifest, network_conclusion = (
        _validate_network_release(
            paths["network_final"],
            paths["network_boundary_audit"],
            paths["action_selection_final"],
        )
    )
    observed_manifest = _validate_observed(paths["observed"])
    scope_manifest = _validate_scope(paths["scope"])
    action_audit_manifest = _validate_manifest_outputs(
        paths["action_audit"],
        expected_schema="etudecas.controllable_action_lever_audit.v1",
    )
    source_audit_manifest = _validate_manifest_outputs(
        paths["supplier_source_audit"],
        expected_schema="etudecas.supplier_source_field_audit.v2",
        required_summary_fields={
            "location_external_account_count",
            "direct_product_fia_external_supplier_count",
            "upstream_021081_fia_external_supplier_count",
            "all_fia_external_supplier_count",
            "all_fia_external_with_location_count",
        },
    )
    map_audit = _validate_html(paths["network_map"], validate_navigation=False)

    service_root: Path | None = None
    service_manifest: dict[str, Any] = {}
    service_omission_reason = "aucun dossier fourni"
    if service_landscape_dir is not None:
        service_root = service_landscape_dir.resolve()
        service_manifest = _validate_service_landscape(service_root)
        service_omission_reason = ""

    input_snapshot = _collect_consumed_input_snapshot(
        paths=paths,
        component_manifest=component_manifest,
        action_manifest=action_manifest,
        observed_manifest=observed_manifest,
        scope_manifest=scope_manifest,
        action_audit_manifest=action_audit_manifest,
        source_audit_manifest=source_audit_manifest,
        service_root=service_root,
    )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-",
            dir=output_dir.parent,
        )
    ).resolve()
    try:
        meeting_html = staging / MEETING_FILE
        network_html = staging / NETWORK_FILE
        launcher_html = staging / LAUNCHER_FILE
        network_result = network_dashboard.build_network_dashboard(
            artifact_dir=paths["network_final"],
            priority_boundary_audit_dir=paths["network_boundary_audit"],
            output_html=network_html,
            meeting_html=meeting_html,
            component_html=component_html,
            map_html=paths["network_map"],
            action_selection_dir=paths["action_selection_final"],
            generated_label=generated_label,
        )
        meeting_result = meeting_dashboard.build_industrial_supply_bilan_dashboard(
            observed_dir=paths["observed"],
            scope_dir=paths["scope"],
            service_landscape_dir=(
                service_root
                if service_root is not None
                else staging / "_SERVICE_MASQUE"
            ),
            output_html=meeting_html,
            component_021081_dir=paths["component_021081_final"],
            network_screen_dir=paths["network_final"],
            network_priority_boundary_audit_dir=paths["network_boundary_audit"],
            network_action_selection_dir=paths["action_selection_final"],
            action_audit_dir=paths["action_audit"],
            supplier_source_audit_dir=paths["supplier_source_audit"],
            sensitivity_html=None,
            component_021081_html=component_html,
            network_risk_html=network_html,
            three_views_html=None,
            network_map_html=paths["network_map"],
            presentation_profile="meeting",
        )
        launcher_html.write_text(
            _render_launcher(
                output=launcher_html,
                meeting_html=meeting_html,
                network_html=network_html,
                component_html=component_html,
                map_html=paths["network_map"],
                service_used=service_root is not None,
            ),
            encoding="utf-8",
        )

        expected_meeting_network_state = (
            meeting_dashboard.NETWORK_ENVELOPE_TRIO_STATE
            if network_conclusion == "envelope_service_top3_scoped"
            else meeting_dashboard.NETWORK_FROZEN_GROUP_STATE
        )
        meeting_input_status = meeting_result.get("input_status", {})
        if (
            meeting_input_status.get("network_screen") != expected_meeting_network_state
            or meeting_input_status.get("network_input_status")
            != meeting_dashboard.FROZEN_NETWORK_INPUT_STATUS
            or meeting_input_status.get("network_priority_reporting_status")
            != expected_meeting_network_state
            or meeting_input_status.get("global_network_priority_robustness_evaluable")
            is not False
            or meeting_input_status.get("network_recovery_metric_status")
            != "excluded_invalid_common_window"
            or _as_int(meeting_input_status.get("actions_ready_count"), -1) != 0
        ):
            raise FinalAssemblyError(
                "Le dashboard rendez-vous n'interprète pas correctement la conclusion réseau."
            )
        if meeting_result.get("input_status", {}).get("component_021081") != "complete":
            raise FinalAssemblyError(
                "Le dashboard rendez-vous n'interprète pas le paquet 021081 comme complet."
            )
        if meeting_result.get("presentation_profile") != "meeting":
            raise FinalAssemblyError(
                "Le profil rendez-vous à trois vues n'a pas été appliqué."
            )
        if _as_int(meeting_result.get("view_count")) != 3:
            raise FinalAssemblyError(
                "Le parcours final ne contient pas exactement trois vues."
            )
        expected_stable_priority_count = (
            3 if network_conclusion == "envelope_service_top3_scoped" else 0
        )
        if _as_int(network_result.get("stable_priority_count")) != (
            expected_stable_priority_count
        ):
            raise FinalAssemblyError(
                "La page réseau ne respecte pas la conclusion statistique attendue."
            )

        expected_reporting_status = (
            "envelope_service_top3_released"
            if network_conclusion == "envelope_service_top3_scoped"
            else "priority_group_only"
        )
        if (
            network_result.get("priority_reporting_status") != expected_reporting_status
            or network_result.get("input_status")
            != "signed_scientific_overlay_and_audits_valid"
            or network_result.get("global_network_priority_robustness_evaluable")
            is not False
            or network_result.get("actions_promoted") is not False
            or _as_int(network_result.get("genealogical_lot_detail_count"), -1)
            <= 0
        ):
            raise FinalAssemblyError(
                "La page réseau ne restitue pas les limites scientifiques attendues."
            )

        html_audits = {}
        for name in (MEETING_FILE, NETWORK_FILE, LAUNCHER_FILE):
            audit = _validate_html(staging / name, validate_navigation=True)
            html_audits[name] = {**audit, "path": name}
        meeting_document = meeting_html.read_text(encoding="utf-8")
        if service_root is not None and not all(
            phrase in meeting_document
            for phrase in (
                "HYPOTHÈSE",
                "SIMULÉ",
                "ne prédit pas",
            )
        ):
            raise FinalAssemblyError(
                "Les configurations 80/93 ne sont pas suffisamment identifiées comme simulées."
            )

        _assert_snapshot_unchanged(input_snapshot)

        source_hashes = {
            "network_campaign_manifest": _sha256(
                paths["network_final"] / "campaign_manifest.json"
            ),
            "network_scientific_overlay_manifest": _sha256(
                paths["network_final"] / "scientific_overlay_manifest.json"
            ),
            "network_extension_audit_manifest": _sha256(
                paths["network_final"] / "extension_interpretation_audit_manifest.json"
            ),
            "network_scientific_promotion_controls": _sha256(
                paths["network_final"] / "scientific_promotion_controls.json"
            ),
            "network_priority_boundary_audit_manifest": _sha256(
                paths["network_boundary_audit"]
                / "priority_boundary_audit_manifest.json"
            ),
            "component_campaign_manifest": _sha256(
                paths["component_021081_final"] / "campaign_manifest.json"
            ),
            "action_selector_manifest": _sha256(
                paths["action_selection_final"] / "action_selector_manifest.json"
            ),
            "observed_manifest": _sha256(paths["observed"] / "manifest.json"),
            "scope_manifest": _sha256(paths["scope"] / "manifest.json"),
            "action_audit_manifest": _sha256(paths["action_audit"] / "manifest.json"),
            "supplier_source_audit_manifest": _sha256(
                paths["supplier_source_audit"] / "manifest.json"
            ),
            "network_map_html": map_audit["sha256"],
        }
        if service_root is not None:
            source_hashes["service_landscape_campaign_manifest"] = _sha256(
                service_root / "campaign_manifest.json"
            )
        output_records = {
            name: {
                "size_bytes": (staging / name).stat().st_size,
                "sha256": _sha256(staging / name),
            }
            for name in (MEETING_FILE, NETWORK_FILE, LAUNCHER_FILE)
        }
        package_manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
            "created_at_utc": _utc_now(),
            "output_directory": str(output_dir),
            "entrypoint": LAUNCHER_FILE,
            "four_dynamic_final_inputs": {
                key: str(paths[key])
                for key in (
                    "network_final",
                    "network_boundary_audit",
                    "component_021081_final",
                    "action_selection_final",
                )
            },
            "source_hashes": source_hashes,
            "consumed_input_files": {
                label: {
                    "size_bytes": record["size_bytes"],
                    "sha256": record["sha256"],
                }
                for label, record in sorted(input_snapshot.items())
            },
            "outputs": output_records,
            "release_checks": {
                "network_conclusion": network_conclusion,
                "network_priority_reporting_status": expected_reporting_status,
                "network_input_status": network_result.get("input_status"),
                "network_stable_priority_count": expected_stable_priority_count,
                "network_scientific_overlay_validated": True,
                "network_priority_boundary_audit_validated": True,
                "network_extension_execution_integrity_pass": (
                    scientific_controls.get("execution_integrity_pass") is True
                ),
                "network_global_temporal_robustness_evaluable": False,
                "network_global_four_cause_robustness_evaluable": False,
                "network_global_priority_robustness_evaluable": False,
                "network_promotion_allowed": False,
                "causal_lot_pairing_integrity_pass": (
                    scientific_controls.get("causal_lot_pairing_integrity_pass") is True
                ),
                "causal_lot_attribution_available": _as_bool(
                    scientific_controls.get("causal_lot_attribution_available")
                ),
                "network_recovery_metric_status": scientific_controls.get(
                    "network_recovery_metric_status"
                ),
                "legacy_release_flags_used_as_evidence": False,
                "action_catalogue_blocked": True,
                "ready_action_count": 0,
                "component_schema": component_manifest.get("schema_version"),
                "component_reporting_revision": component_manifest.get(
                    "reporting_revision"
                ),
                "component_sources_audited": True,
                "action_selection_status": action_manifest.get("selection_status"),
                "observed_2025_validation_pass": _as_bool(
                    observed_manifest.get("all_validation_checks_pass")
                ),
                "scope_status": scope_manifest.get("status"),
                "action_audit_status": action_audit_manifest.get("status"),
                "supplier_source_audit_status": source_audit_manifest.get("status"),
                "service_landscape_used": service_root is not None,
                "service_landscape_omission_reason": service_omission_reason,
                "service_landscape_evidence_class": service_manifest.get(
                    "evidence_class", ""
                ),
                "meeting_profile": meeting_result.get("presentation_profile"),
                "meeting_view_count": meeting_result.get("view_count"),
                "utf8_valid": True,
                "mojibake_marker_count": 0,
                "external_resource_count": 0,
                "all_navigation_links_resolved": True,
                "source_inputs_unchanged_during_build": True,
                "legacy_exploratory_component_or_network_embedded": False,
            },
            "html_audits": html_audits,
            "preservation": {
                "previous_artifacts_mutated": False,
                "cold_start_mutated": False,
                "existing_map_mutated": False,
                "existing_html_mutated": False,
                "large_simulation_outputs_copied": False,
            },
            "interpretation": (
                "Les priorités sont des conséquences simulées conditionnelles. "
                "Elles ne sont ni une probabilité d'incident, ni un OTIF observé, "
                "ni une cotation fournisseur."
            ),
        }
        manifest_path = staging / MANIFEST_FILE
        manifest_path.write_text(
            json.dumps(package_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _read_json(manifest_path)
        _validate_html(launcher_html, validate_navigation=True)
        manifest_digest = _sha256(manifest_path)
        (staging / MANIFEST_DIGEST_FILE).write_text(
            f"{manifest_digest}  {MANIFEST_FILE}\n",
            encoding="ascii",
        )
        _assert_snapshot_unchanged(input_snapshot)
        staging.rename(output_dir)
        return {
            **package_manifest,
            "output_directory": str(output_dir),
            "entrypoint_path": str((output_dir / LAUNCHER_FILE).resolve()),
            "manifest_sha256": manifest_digest,
        }
    except Exception:
        if staging.is_dir():
            shutil.rmtree(staging)
        raise


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-final-dir", type=Path, required=True)
    parser.add_argument("--network-boundary-audit-dir", type=Path, required=True)
    parser.add_argument("--component-021081-final-dir", type=Path, required=True)
    parser.add_argument("--action-selection-final-dir", type=Path, required=True)
    parser.add_argument("--observed-dir", type=Path, required=True)
    parser.add_argument("--scope-dir", type=Path, required=True)
    parser.add_argument("--action-audit-dir", type=Path, required=True)
    parser.add_argument("--supplier-source-audit-dir", type=Path, required=True)
    parser.add_argument("--network-map-html", type=Path, required=True)
    parser.add_argument("--service-landscape-dir", type=Path)
    parser.add_argument("--generated-label", default="le 2 septembre 2026")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_final_package(
        network_final_dir=args.network_final_dir,
        network_boundary_audit_dir=args.network_boundary_audit_dir,
        component_021081_final_dir=args.component_021081_final_dir,
        action_selection_final_dir=args.action_selection_final_dir,
        observed_dir=args.observed_dir,
        scope_dir=args.scope_dir,
        action_audit_dir=args.action_audit_dir,
        supplier_source_audit_dir=args.supplier_source_audit_dir,
        network_map_html=args.network_map_html,
        output_dir=args.output_dir,
        service_landscape_dir=args.service_landscape_dir,
        generated_label=args.generated_label,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
