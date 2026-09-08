#!/usr/bin/env python3
"""Build the additive, offline, three-view supplier-risk preliminary V3.

This module only reads already-produced evidence.  It never invokes the
simulation engine and never mutates an earlier delivery or source artifact.
"""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from . import build_industrial_supply_preliminary_transport_delivery_v2 as v2
    from . import nominal_run_curves
except ImportError:  # pragma: no cover - direct CLI execution
    import build_industrial_supply_preliminary_transport_delivery_v2 as v2
    import nominal_run_curves

ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
SCHEMA_VERSION = "etudecas.industrial_supply_preliminary_complete.v3"
ENTRYPOINT = "OUVRIR_BILAN_SUPPLY_PRELIMINAIRE_COMPLET.html"
MANIFEST_FILE = "manifest_bilan_supply_preliminaire_complet_v3.json"
MAP_ASSET = "assets/carte_reseau_existante_hors_ligne.html"
DATA_DIR = "assets/data"
DEFAULT_OUTPUT_DIR = (
    ARTIFACT_ROOT / "industrial_supply_preliminary_consolidated_20260904_v4"
)


class CompletePreliminaryDeliveryError(RuntimeError):
    """Raised when the V3 evidence or delivery contract is not satisfied."""


DEFAULT_NETWORK_DIR = ARTIFACT_ROOT / "supplier_network_risk_screen_20260902_v2"
DEFAULT_PRIORITY_BOUNDARY_DIR = (
    ARTIFACT_ROOT / "supplier_network_priority_boundary_audit_20260903_v1"
)
DEFAULT_PRELIMINARY_DIR = (
    ARTIFACT_ROOT / "supplier_network_preliminary_15_of_30_20260904_v1"
)
DEFAULT_EXTENSION_RUNNER_DIR = (
    ARTIFACT_ROOT / "supplier_network_post_priority_extensions_20260903_v1"
)
DEFAULT_SERVICE_LANDSCAPE_DIR = ARTIFACT_ROOT / "supplier_service_landscape_20260831_v4"
DEFAULT_REGIME_PLAN_DIR = (
    ARTIFACT_ROOT / "supplier_service_regime_calibration_plan_20260903_v2"
)
DEFAULT_STOCK_AUDIT_DIR = (
    ARTIFACT_ROOT / "supplier_stock_signal_calibration_audit_20260903_v3"
)
DEFAULT_OBSERVED_DIR = ARTIFACT_ROOT / "observed_2025_supply_bilan_20260901_v1"
DEFAULT_ACTION_PROTOCOL_DIR = (
    ARTIFACT_ROOT / "supplier_network_exploratory_action_protocol_20260903_v5"
)
DEFAULT_LEGACY_ACTION_DIR = (
    ARTIFACT_ROOT / "industrial_cascade_comparison_10seeds_20260828_v1"
)
DEFAULT_DYNAMIC_PROTOCOL_DIR = (
    ARTIFACT_ROOT / "supplier_dynamic_requirement_reference_protocol_20260904_v3"
)
DEFAULT_CAPACITY_AUDIT_DIR = (
    ARTIFACT_ROOT / "supplier_dynamic_capacity_coupling_audit_20260904_v3"
)
DEFAULT_FREQUENCY_DIR = (
    ARTIFACT_ROOT / "canonical_frequency_v3_closed_loop_actuator_pilot_20260827_run5"
)
DEFAULT_HISTORICAL_FREQUENCY_DIR = (
    ARTIFACT_ROOT / "canonical_frequency_dashboard_audited_20260826_v6"
)
DEFAULT_CONTROL_DIR = (
    ARTIFACT_ROOT / "canonical_control_system_analysis_v3_closed_loop_20260827_v5"
)
DEFAULT_NOMINAL_REPLAY_DIR = (
    ARTIFACT_ROOT / "supplier_network_nominal_trajectory_replay_20260904_v1"
)
DEFAULT_MAP_FILE = (
    ARTIFACT_ROOT
    / "industrial_supply_preliminary_delivery_15_of_30_20260904_v2_sans_qualite"
    / "assets"
    / "network_map_autonomous.html"
)
DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "sensibility"
    / "supplier_risk_campaign_multisource_result"
)
DEFAULT_WORLD_TOPOJSON_FILE = (
    ARTIFACT_ROOT
    / "demo_supply_chain_autonome_complete_20260831_v5"
    / "views"
    / "world_110m.json"
)
WORLD_TOPOJSON_KEY = "world_110m"
WORLD_TOPOJSON_SHA256 = (
    "d75915eaa31c870df6b972c9e5bb86910197825f33dcfef740f3b2f68cffe843"
)
OFFLINE_WORLD_TOPOLOGY_MARKER = 'data-v3-embedded-world-topology="world_110m"'
OFFLINE_WORLD_TOPOLOGY_ASSIGNMENT = "window.PlotlyGeoAssets.topojson.world_110m="
LEGACY_MAP_PRIORITY_TEXT = (
    "Lecture principale supplier-first: les fournisseurs sont prioritaires pour "
    "la decision. Les usines restent visibles comme controles modele et validation "
    "scientifique."
)
CURRENT_MAP_SCOPE_TEXT = (
    "Lecture de cette vue topologique : fournisseurs et usines sont affich\u00e9s "
    "sans ordre de priorit\u00e9 valid\u00e9 par la campagne actuelle."
)
MAP_SCOPE_BANNER_TEXT = (
    "VUE TOPOLOGIQUE EXISTANTE ENRICHIE \u2014 Les courbes du run nominal actuel sont "
    "accessibles dans l'onglet Run nominal. Les cascades actuelles et le suivi "
    "causal des lots ne sont pas encore int\u00e9gr\u00e9s \u00e0 la carte ; utiliser aussi "
    "les trois vues du bilan."
)
MAP_SCOPE_BANNER_MARKER = "data-v3-map-scope-warning"
LEGACY_MAP_STRESS_TITLE_HTML = '<div class="orderLedgerTextHeader">Risques simules - stress tests fournisseurs</div>'
CURRENT_MAP_STRESS_SCOPE_HTML = LEGACY_MAP_STRESS_TITLE_HTML + (
    '<div class="orderLedgerStatus" style="border:2px solid #d97706;'
    'background:#fff4ce;color:#713f12;padding:10px">'
    "<strong>ANCIEN ÉCRAN EXPLORATOIRE.</strong> Les positions et indices ci-dessous "
    "ne constituent ni le résultat de la campagne actuelle ni un ordre fournisseur "
    "validé.</div>"
)
LEGACY_MAP_RANK_HEADER = '<th class="num">Rang</th>'
CURRENT_MAP_RANK_HEADER = '<th class="num">Position descriptive ancienne</th>'
LEGACY_MAP_DECISION_SCORE_HEADER = '<th class="num">Score decisionnel</th>'
CURRENT_MAP_DECISION_SCORE_HEADER = '<th class="num">Indice interne ancien</th>'

NETWORK_SUMMARY_CSV = f"{DATA_DIR}/confirmation_retard_disponibilite_30.csv"
NETWORK_DISTRIBUTION_CSV = f"{DATA_DIR}/distribution_30_simulations.csv"
RANKING_CSV = f"{DATA_DIR}/tri_descriptif_conditionnel_16_fournisseurs.csv"
EXTENSION_CSV = f"{DATA_DIR}/extensions_34_cellules.csv"
LANDSCAPE_CSV = f"{DATA_DIR}/paysage_service_hors_incident.csv"
LOT_SUMMARY_CSV = f"{DATA_DIR}/synthese_exposition_lots.csv"
LOT_DETAIL_CSV = f"{DATA_DIR}/detail_exposition_lots.csv"
STOCK_CALIBRATION_CSV = f"{DATA_DIR}/calibrage_stock_besoins_24_matieres.csv"
OBSERVED_CA_CSV = f"{DATA_DIR}/observe_2025_ca_mensuel.csv"
OBSERVED_STOCK_CSV = f"{DATA_DIR}/observe_2025_stock_hebdomadaire.csv"
OBSERVED_SHORTAGE_CSV = f"{DATA_DIR}/observe_2025_projections_rupture.csv"
ACTION_CSV = f"{DATA_DIR}/ancien_test_actions_338929.csv"
DECISION_MATRIX_CSV = f"{DATA_DIR}/matrice_statut_travaux.csv"
NOMINAL_TRAJECTORY_CSV = f"{DATA_DIR}/trajectoires_run_nominal_actuel.csv"

IN_SCOPE_MECHANISMS = {"transport_delay", "supply_availability"}
LANDSCAPE_MECHANISMS = {
    "baseline",
    "capacity",
    "lead_extra",
    "reliability",
    "availability",
    "intermittent_delay",
}
FORBIDDEN_DELIVERY_TEXT = re.compile(
    r"quality_hold|quality_yield|quality[_ -]?release|"
    r"release\s+qualit|qualit[eÃ©]\s*/\s*release|"
    r"retenue\s+qualit|quarantaine|"
    r"mode\s*===\s*[\"']quality[\"']",
    flags=re.IGNORECASE,
)
EXPECTED_DESCRIPTIVE_EFFECTS = {
    "SDC-VD0993480A": (-33.13890341230428, 30),
    "SDC-VD0914360C": (-30.291994163212455, 30),
    "SDC-VD0519670A": (-5.443912878098055, 11),
    "SDC-VD0514881A": (-1.7960369433528724, 5),
}
EXPECTED_NONSEPARATION_GROUP = {
    "SDC-VD0514881A",
    "SDC-VD0519670A",
    "SDC-VD0914360C",
    "SDC-VD0993480A",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CompletePreliminaryDeliveryError(
            f"Source JSON invalide: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise CompletePreliminaryDeliveryError(f"Objet JSON attendu: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, UnicodeError, csv.Error) as error:
        raise CompletePreliminaryDeliveryError(
            f"Source CSV invalide: {path}"
        ) from error


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise CompletePreliminaryDeliveryError(f"Table vide: {path.name}")
    fields = list(rows[0])
    if any(list(row) != fields for row in rows):
        raise CompletePreliminaryDeliveryError(f"Colonnes incohérentes: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _float(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise CompletePreliminaryDeliveryError(f"Valeur invalide: {label}") from error
    if not math.isfinite(result):
        raise CompletePreliminaryDeliveryError(f"Valeur non finie: {label}")
    return result


def _optional_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _close(actual: Any, expected: float, *, tolerance: float = 1e-10) -> bool:
    return math.isclose(
        _float(actual, label="contrôle numérique"),
        expected,
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def _item(value: Any) -> str:
    return str(value or "").strip().removeprefix("item:")


def _fmt(value: Any, digits: int = 2) -> str:
    return f"{_float(value, label='affichage'):.{digits}f}".replace(".", ",")


def _qty(value: Any, digits: int = 0) -> str:
    rendered = f"{_float(value, label='quantité'):,.{digits}f}"
    return rendered.replace(",", " ").replace(".", ",")


def _clean_map(
    source: Path,
    *,
    supplier_risk_campaign_dir: Path = DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR,
) -> str:
    try:
        document = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CompletePreliminaryDeliveryError(
            "Carte hors ligne absente ou invalide."
        ) from error

    chunked_match = re.search(
        r"(?P<chunks_prefix>const\s+DATA_CHUNKED_GZIP_BASE64\s*=\s*)"
        r"(?P<chunks>\{.*?\})"
        r"(?P<manifest_prefix>;\s*const\s+DATA_CHUNKED_MANIFEST\s*=\s*)"
        r"(?P<manifest>\{.*?\})(?P<suffix>;)",
        document,
        flags=re.DOTALL,
    )
    if chunked_match:
        try:
            encoded_chunks = json.loads(chunked_match.group("chunks"))
            chunk_manifest = json.loads(chunked_match.group("manifest"))
        except json.JSONDecodeError as error:
            raise CompletePreliminaryDeliveryError(
                "Index des donnees compressees de la carte invalide."
            ) from error
        if not isinstance(encoded_chunks, dict) or not isinstance(chunk_manifest, dict):
            raise CompletePreliminaryDeliveryError(
                "Index des donnees compressees de la carte invalide."
            )

        decoded_payloads: dict[str, Any] = {}
        raw_payloads: dict[str, bytes] = {}
        for payload_key, chunks in encoded_chunks.items():
            if not isinstance(chunks, list) or not all(
                isinstance(chunk, str) for chunk in chunks
            ):
                raise CompletePreliminaryDeliveryError(
                    f"Bloc compresse invalide: {payload_key}"
                )
            try:
                compressed = base64.b64decode("".join(chunks), validate=True)
                raw = gzip.decompress(compressed)
                payload = json.loads(raw)
            except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
                raise CompletePreliminaryDeliveryError(
                    f"Bloc compresse illisible: {payload_key}"
                ) from error
            entry = chunk_manifest.get(payload_key)
            if not isinstance(entry, dict):
                raise CompletePreliminaryDeliveryError(
                    f"Manifeste absent pour le bloc compresse: {payload_key}"
                )
            if entry.get("raw_bytes") != len(raw) or entry.get(
                "compressed_bytes"
            ) != len(compressed):
                raise CompletePreliminaryDeliveryError(
                    f"Tailles incoherentes pour le bloc compresse: {payload_key}"
                )
            decoded_payloads[payload_key] = payload
            raw_payloads[payload_key] = raw

        if "supplier_risk_campaign" in decoded_payloads:
            from etudecas.simulation.sensibility.run_supplier_risk_campaign import (
                summarize_by_supplier,
            )
            from etudecas.visualization.maps.risk_payload import (
                build_supplier_risk_campaign_payload,
            )

            summary_json = (
                supplier_risk_campaign_dir / "supplier_risk_campaign_summary.json"
            )
            summary_csv = (
                supplier_risk_campaign_dir / "supplier_risk_campaign_summary.csv"
            )
            cases_csv = supplier_risk_campaign_dir / "supplier_risk_campaign_cases.csv"
            previous_campaign = decoded_payloads["supplier_risk_campaign"]
            source_campaign = build_supplier_risk_campaign_payload(
                summary_json,
                summary_csv,
                cases_csv,
            )
            if source_campaign != previous_campaign:
                raise CompletePreliminaryDeliveryError(
                    "La campagne fournisseur source ne correspond pas au bloc "
                    "embarque dans la carte."
                )
            metadata = dict(_read_json(summary_json).get("metadata") or {})
            case_rows = _read_csv(cases_csv)
            filtered_cases = [
                row
                for row in case_rows
                if str(row.get("risk_family") or "").strip().casefold() != "quality"
            ]
            if not filtered_cases or len(filtered_cases) == len(case_rows):
                raise CompletePreliminaryDeliveryError(
                    "La campagne source ne permet pas d'isoler la branche qualite."
                )
            summary_rows = summarize_by_supplier(filtered_cases)
            if not summary_rows:
                raise CompletePreliminaryDeliveryError(
                    "La campagne fournisseur sans branche qualite est vide."
                )
            metadata["families"] = [
                family
                for family in metadata.get("families", [])
                if str(family).strip().casefold() != "quality"
            ]
            definitions = metadata.get("risk_family_definitions")
            if isinstance(definitions, dict):
                metadata["risk_family_definitions"] = {
                    key: value
                    for key, value in definitions.items()
                    if str(key).strip().casefold() != "quality"
                }
            metadata["case_count"] = len(filtered_cases)
            metadata["supplier_count"] = len(summary_rows)
            with tempfile.TemporaryDirectory(
                prefix="etudecas_supplier_risk_without_quality_"
            ) as temp_name:
                temp_dir = Path(temp_name)
                filtered_summary_json = temp_dir / "supplier_risk_campaign_summary.json"
                filtered_summary_csv = temp_dir / "supplier_risk_campaign_summary.csv"
                filtered_cases_csv = temp_dir / "supplier_risk_campaign_cases.csv"
                filtered_summary_json.write_text(
                    json.dumps(
                        {"metadata": metadata},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    encoding="utf-8",
                )
                _write_csv(filtered_summary_csv, summary_rows)
                _write_csv(filtered_cases_csv, filtered_cases)
                filtered_campaign = build_supplier_risk_campaign_payload(
                    filtered_summary_json,
                    filtered_summary_csv,
                    filtered_cases_csv,
                )
            previous_nodes = (
                previous_campaign.get("nodes", {})
                if isinstance(previous_campaign, dict)
                else {}
            )
            filtered_nodes = filtered_campaign.get("nodes", {})
            if set(previous_nodes) != set(filtered_nodes):
                raise CompletePreliminaryDeliveryError(
                    "La purge qualite modifierait le perimetre des fournisseurs."
                )
            decoded_payloads["supplier_risk_campaign"] = filtered_campaign

        drop_payload_item = object()
        branch_value = re.compile(
            r"(?:^|[_\s:/-])(?:quality|qualit(?:e|\u00e9))"
            r"(?:$|[_\s:/-])",
            flags=re.IGNORECASE,
        )
        branch_text = re.compile(
            r"quality[_ -]?(?:hold|yield|release)|"
            r"(?:release|retenue|quarantaine)[ _-]?qualit(?:e|\u00e9)|"
            r"qualit(?:e|\u00e9)\s*/\s*release|"
            r"fiabilit(?:e|\u00e9)\s*/\s*qualit(?:e|\u00e9)",
            flags=re.IGNORECASE,
        )
        branch_fields = {
            "family",
            "driver_family",
            "risk_family",
            "scenario_family",
            "mode",
        }
        identity_fields = {
            "id",
            "scenario_id",
            "type",
            "risk_type",
            "label",
            "driver_label",
            "risk_family_label",
        }

        def is_branch_value(value: Any, *, identity: bool = False) -> bool:
            if not isinstance(value, str):
                return False
            plain = html.unescape(value).strip()
            if branch_text.search(plain):
                return True
            if identity:
                return bool(branch_value.search(plain))
            return plain.casefold() in {"quality", "qualite", "qualit\u00e9"}

        def clean_embedded_text(value: str) -> str:
            cleaned = re.sub(
                r"fiabilit(?:e|\u00e9)\s*/\s*qualit(?:e|\u00e9)",
                "Fiabilite fournisseur",
                value,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"simuler\s+pertes,\s*retours,\s*release\s+qualit(?:e|\u00e9)\s+et\s+quantite\s+utile",
                "simuler pertes, retours et quantite utile expediee",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"donnees\s+qualit(?:e|\u00e9)\s+limitees",
                "donnees de conformite non disponibles",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"controle\s+qualit(?:e|\u00e9)\s+renforce",
                "controle fournisseur renforce",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                r"<tr\b[^>]*>(?:(?!</tr>).)*?(?:"
                r"quality[_ -]?(?:hold|yield|release)|"
                r"(?:release|retenue|quarantaine)[ _-]?qualit(?:e|\u00e9)|"
                r"qualit(?:e|\u00e9)\s*/\s*release)"
                r"(?:(?!</tr>).)*?</tr>",
                "",
                cleaned,
                flags=re.IGNORECASE | re.DOTALL,
            )
            return cleaned

        def purge_embedded_branch(value: Any) -> Any:
            if isinstance(value, dict):
                for key, item in value.items():
                    folded_key = str(key).strip().casefold()
                    if folded_key in branch_fields and is_branch_value(item):
                        return drop_payload_item
                    if folded_key in identity_fields and is_branch_value(
                        item, identity=True
                    ):
                        return drop_payload_item
                cleaned_mapping: dict[str, Any] = {}
                for key, item in value.items():
                    folded_key = str(key).strip().casefold()
                    if folded_key in {"quality", "qualite", "qualit\u00e9"}:
                        continue
                    if folded_key == "families" and isinstance(item, list):
                        item = [
                            family for family in item if not is_branch_value(family)
                        ]
                    cleaned_item = purge_embedded_branch(item)
                    if cleaned_item is not drop_payload_item:
                        cleaned_mapping[key] = cleaned_item
                return cleaned_mapping
            if isinstance(value, list):
                cleaned_list = []
                for item in value:
                    cleaned_item = purge_embedded_branch(item)
                    if cleaned_item is not drop_payload_item:
                        cleaned_list.append(cleaned_item)
                return cleaned_list
            if isinstance(value, str):
                return clean_embedded_text(value)
            return value

        for payload_key, payload in tuple(decoded_payloads.items()):
            cleaned_payload = purge_embedded_branch(payload)
            if cleaned_payload is drop_payload_item:
                cleaned_payload = None
            decoded_payloads[payload_key] = cleaned_payload

        def assert_no_embedded_branch(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    folded_key = str(key).strip().casefold()
                    if folded_key in {"quality", "qualite", "qualit\u00e9"}:
                        raise CompletePreliminaryDeliveryError(
                            f"Branche qualite residuelle dans {path}.{key}."
                        )
                    if folded_key in branch_fields and is_branch_value(item):
                        raise CompletePreliminaryDeliveryError(
                            f"Famille qualite residuelle dans {path}.{key}."
                        )
                    if folded_key in identity_fields and is_branch_value(
                        item, identity=True
                    ):
                        raise CompletePreliminaryDeliveryError(
                            f"Identifiant qualite residuel dans {path}.{key}."
                        )
                    if (
                        folded_key == "families"
                        and isinstance(item, list)
                        and any(is_branch_value(family) for family in item)
                    ):
                        raise CompletePreliminaryDeliveryError(
                            f"Liste de familles qualite residuelle dans {path}.{key}."
                        )
                    assert_no_embedded_branch(item, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    assert_no_embedded_branch(item, f"{path}[{index}]")
            elif isinstance(value, str) and branch_text.search(html.unescape(value)):
                raise CompletePreliminaryDeliveryError(
                    f"Texte de branche qualite residuel dans {path}."
                )

        for payload_key, payload in decoded_payloads.items():
            assert_no_embedded_branch(payload, f"payload.{payload_key}")
            raw = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if raw == raw_payloads[payload_key]:
                continue
            compressed = gzip.compress(raw, mtime=0)
            encoded = base64.b64encode(compressed).decode("ascii")
            previous_chunks = encoded_chunks[payload_key]
            chunk_length = max(
                (len(chunk) for chunk in previous_chunks),
                default=len(encoded),
            )
            encoded_chunks[payload_key] = [
                encoded[start : start + chunk_length]
                for start in range(0, len(encoded), chunk_length)
            ] or [""]
            chunk_manifest[payload_key]["raw_bytes"] = len(raw)
            chunk_manifest[payload_key]["compressed_bytes"] = len(compressed)

        replacement = "".join(
            [
                chunked_match.group("chunks_prefix"),
                json.dumps(encoded_chunks, separators=(",", ":")),
                chunked_match.group("manifest_prefix"),
                json.dumps(chunk_manifest, separators=(",", ":")),
                chunked_match.group("suffix"),
            ]
        )
        document = (
            document[: chunked_match.start()]
            + replacement
            + document[chunked_match.end() :]
        )

    document = re.sub(
        r"(?m)^\s*quality\s*:\s*[\"']Qualite[\"']\s*,?\s*$",
        "",
        document,
    )
    document = re.sub(
        r'<option\s+value=["\']quality["\']>\s*Qualite\s*</option>',
        "",
        document,
        flags=re.IGNORECASE,
    )
    document = re.sub(
        r"\s*else\s+if\s*\(mode\s*===\s*[\"']quality[\"']\)\s*\{\s*"
        r"scenarioComparisonSelectedIds\s*=\s*withNominal\("
        r"\s*scenarios\.filter\(s\s*=>\s*familyIncludes\(s,\s*[\"']quality[\"']\)\)"
        r"\s*\);\s*\}",
        "",
        document,
        flags=re.IGNORECASE,
    )
    document = document.replace(LEGACY_MAP_PRIORITY_TEXT, CURRENT_MAP_SCOPE_TEXT)
    document = document.replace(
        LEGACY_MAP_STRESS_TITLE_HTML,
        CURRENT_MAP_STRESS_SCOPE_HTML,
    )
    document = document.replace(LEGACY_MAP_RANK_HEADER, CURRENT_MAP_RANK_HEADER)
    document = document.replace(
        LEGACY_MAP_DECISION_SCORE_HEADER,
        CURRENT_MAP_DECISION_SCORE_HEADER,
    )
    if "<body>" in document and MAP_SCOPE_BANNER_MARKER not in document:
        banner = (
            f'<div {MAP_SCOPE_BANNER_MARKER} role="note" '
            'style="position:relative;z-index:100000;padding:10px 18px;'
            "background:#fff4ce;border-bottom:2px solid #d97706;color:#713f12;"
            'font:700 14px/1.45 Segoe UI,Arial,sans-serif;text-align:center">'
            f"{MAP_SCOPE_BANNER_TEXT}</div>"
        )
        document = document.replace("<body>", "<body>\n  " + banner, 1)
    if FORBIDDEN_DELIVERY_TEXT.search(document):
        raise CompletePreliminaryDeliveryError(
            "La copie de carte contient un thème exclu."
        )
    return document


def _load_world_topojson(source: Path) -> dict[str, Any]:
    """Load the audited Plotly world topology used by the embedded geo map."""

    try:
        raw = source.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CompletePreliminaryDeliveryError(
            "Fond g\u00e9ographique Plotly hors ligne absent ou invalide."
        ) from error
    digest = hashlib.sha256(raw).hexdigest()
    objects = payload.get("objects") if isinstance(payload, dict) else None
    if (
        digest != WORLD_TOPOJSON_SHA256
        or payload.get("type") != "Topology"
        or not isinstance(objects, dict)
        or not {"countries", "land"}.issubset(objects)
        or not isinstance(payload.get("arcs"), list)
        or not payload["arcs"]
    ):
        raise CompletePreliminaryDeliveryError(
            "Le fond world_110m.json ne correspond pas au fond Plotly audit\u00e9."
        )
    return payload


def _embed_plotly_world_topology(document: str, topology: Mapping[str, Any]) -> str:
    """Preload Plotly's geo cache so ``file://`` never performs a topojson XHR."""

    if OFFLINE_WORLD_TOPOLOGY_MARKER in document:
        raise CompletePreliminaryDeliveryError(
            "Le fond Plotly hors ligne est d\u00e9j\u00e0 embarqu\u00e9 dans la carte."
        )
    if "</head>" not in document or "Plotly" not in document:
        raise CompletePreliminaryDeliveryError(
            "Point d'insertion Plotly introuvable dans la carte."
        )
    serialized = json.dumps(
        topology,
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    preload = f"""
  <script {OFFLINE_WORLD_TOPOLOGY_MARKER}>
    window.PlotlyGeoAssets = window.PlotlyGeoAssets || {{}};
    window.PlotlyGeoAssets.topojson = window.PlotlyGeoAssets.topojson || {{}};
    {OFFLINE_WORLD_TOPOLOGY_ASSIGNMENT}{serialized};
    Plotly.setPlotConfig({{topojsonURL:"./"}});
  </script>
"""
    embedded = document.replace("</head>", preload + "</head>", 1)
    _assert_plotly_geo_offline(embedded)
    return embedded


def _assert_plotly_geo_offline(document: str) -> None:
    """Reject maps whose Plotly geo layer can fall back to the CDN at runtime."""

    has_geo_trace = bool(
        re.search(r"type\s*:\s*[\"']scattergeo[\"']", document)
        or re.search(r"[\"']type[\"']\s*:\s*[\"']scattergeo[\"']", document)
    )
    if not has_geo_trace:
        return
    marker_index = document.find(OFFLINE_WORLD_TOPOLOGY_MARKER)
    assignment_index = document.find(OFFLINE_WORLD_TOPOLOGY_ASSIGNMENT)
    config_index = document.find('Plotly.setPlotConfig({topojsonURL:"./"})')
    head_end_index = document.find("</head>")
    application_plot_indices = [
        document.find(token, head_end_index + len("</head>"))
        for token in ("Plotly.newPlot", "Plotly.react")
    ]
    if (
        document.count(OFFLINE_WORLD_TOPOLOGY_MARKER) != 1
        or marker_index < 0
        or assignment_index < marker_index
        or config_index < assignment_index
        or head_end_index < 0
        or config_index > head_end_index
        or not any(index >= 0 for index in application_plot_indices)
    ):
        raise CompletePreliminaryDeliveryError(
            "La carte Plotly geo pourrait encore demander "
            "https://cdn.plot.ly/world_110m.json au chargement."
        )


def _priority_boundary_data(boundary_dir: Path) -> dict[str, Any]:
    manifest = _read_json(boundary_dir / "priority_boundary_audit_manifest.json")
    audit = _read_json(boundary_dir / "scientific_priority_boundary_audit.json")
    group = set(audit.get("envelope_service_nonseparation_group_supplier_ids", []))
    if (
        manifest.get("status") != "complete"
        or manifest.get("global_priority_release_allowed") is not False
        or manifest.get("confirmatory_priority_set_release_allowed") is not False
        or manifest.get("scoped_descriptive_priority_set_display_allowed") is not False
        or audit.get("scientific_priority_release_inputs_pass") is not False
        or audit.get("selection_and_assessment_seed_blocks_independent") is not False
        or audit.get("multiple_comparison_correction_applied") is not False
        or audit.get("post_selection_inference_correction_applied") is not False
        or group != EXPECTED_NONSEPARATION_GROUP
    ):
        raise CompletePreliminaryDeliveryError(
            "L'audit de frontière descriptive ne permet pas un ordre fournisseur."
        )
    return {"manifest": manifest, "audit": audit, "group": group}


def _network_data(network_dir: Path) -> dict[str, Any]:
    manifest = _read_json(network_dir / "campaign_manifest.json")
    final_decision = _read_json(network_dir / "final_top3_decision.json")
    state_evidence_path = (
        network_dir
        / "cases"
        / "sdc_vd0993480a_344135_m_1430__transport_delay__120"
        / "seed_340282"
        / "summaries"
        / "first_simulation_summary.json"
    )
    state_evidence = _read_json(state_evidence_path)
    rankings_raw = _read_csv(
        network_dir / "confirmation_supplier_sensitivity_ranking.csv"
    )
    summaries_raw = _read_csv(network_dir / "confirmation_summary.csv")
    metrics_raw = _read_csv(network_dir / "confirmation_metrics.csv")
    lanes = _read_csv(network_dir / "active_lane_reference.csv")
    if (
        manifest.get("executed_or_reextracted_run_count") != 1255
        or manifest.get("active_lane_count") != 18
        or manifest.get("distinct_supplier_count") != 16
        or manifest.get("confirmation_seed_count") != 30
        or len(rankings_raw) != 16
        or len(lanes) != 18
        or final_decision.get("top3_set_validated") is not False
        or state_evidence.get("policy", {})
        .get("supplier_state_dependent_risk", {})
        .get("enabled")
        is not False
        or len(
            state_evidence.get("policy", {})
            .get("initialization_policy", {})
            .get("mrp_dynamic_requirement_pairs", [])
        )
        != 3
    ):
        raise CompletePreliminaryDeliveryError("Contrat de campagne réseau inattendu.")

    rankings: list[dict[str, Any]] = []
    for row in sorted(
        rankings_raw, key=lambda item: int(item["supplier_sensitivity_rank"])
    ):
        rank = int(row["supplier_sensitivity_rank"])
        effect_points = 100.0 * _float(row["worst_service_delta"], label="tri")
        presence = int(row["top3_presence_seed_count"])
        if rank <= 2:
            status = (
                "une des deux plus fortes baisses descriptives; "
                "membre du groupe non séparé"
            )
        elif row["supplier_id"] in EXPECTED_NONSEPARATION_GROUP:
            status = "membre du groupe non séparé par l'audit"
        else:
            status = "autre résultat descriptif de cette configuration"
        rankings.append(
            {
                "position_descriptive_moyenne": rank,
                "fournisseur": row["supplier_id"],
                "article": _item(row["worst_item_id"]),
                "site": row["worst_dst_node_id"],
                "produit": row["worst_target_product_id"],
                "mecanisme_le_plus_penalisant": row["worst_failure_mode"],
                "variation_service_points": effect_points,
                "presence_parmi_3_plus_fortes_baisses_sur_30": presence,
                "statut": status,
            }
        )
    for supplier, (effect, presence) in EXPECTED_DESCRIPTIVE_EFFECTS.items():
        row = next(item for item in rankings if item["fournisseur"] == supplier)
        if not _close(row["variation_service_points"], effect) or (
            row["presence_parmi_3_plus_fortes_baisses_sur_30"] != presence
        ):
            raise CompletePreliminaryDeliveryError(
                f"Effet descriptif inattendu pour {supplier}."
            )

    summaries: list[dict[str, Any]] = []
    for row in summaries_raw:
        if row.get("failure_mode") not in IN_SCOPE_MECHANISMS:
            continue
        summaries.append(
            {
                "scenario": row["scenario_id"],
                "voie": row["chain_id"],
                "fournisseur": row["supplier_id"],
                "article": _item(row["item_id"]),
                "site": row["dst_node_id"],
                "produit": row["target_product_id"],
                "mecanisme": row["failure_mode"],
                "niveau": row["mechanism_value"],
                "unite_niveau": row["mechanism_unit"],
                "debut": row["stress_start_day"],
                "fin": row["stress_end_day"],
                "simulations": int(row["n_seeds"]),
                "variation_service_moyenne_points": 100
                * _float(
                    row["target_on_due_date_proxy_delta_vs_paired_baseline_mean"],
                    label="effet moyen",
                ),
                "ecart_type_points": 100
                * _float(
                    row["target_on_due_date_proxy_delta_vs_paired_baseline_sample_std"],
                    label="écart-type",
                ),
                "bootstrap_descriptif_2p5_points": 100
                * _float(
                    row[
                        "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_low"
                    ],
                    label="borne basse",
                ),
                "bootstrap_descriptif_97p5_points": 100
                * _float(
                    row[
                        "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_high"
                    ],
                    label="borne haute",
                ),
                "minimum_points": 100
                * _float(
                    row["target_on_due_date_proxy_delta_vs_paired_baseline_min"],
                    label="minimum",
                ),
                "maximum_points": 100
                * _float(
                    row["target_on_due_date_proxy_delta_vs_paired_baseline_max"],
                    label="maximum",
                ),
                "retard_cumule_moyen_un_jours": _float(
                    row["incremental_target_backlog_qty_days_mean"],
                    label="retard cumulé",
                ),
                "statut_effet": row["effect_status"],
            }
        )
    if (
        len(summaries) != 36
        or sum(item["mecanisme"] == "transport_delay" for item in summaries) != 18
        or any(item["simulations"] != 30 for item in summaries)
    ):
        raise CompletePreliminaryDeliveryError("Résumé de confirmation incomplet.")

    distribution: list[dict[str, Any]] = []
    lane_by_chain = {row["chain_id"]: row for row in lanes}
    for row in metrics_raw:
        if row.get("mechanism") not in IN_SCOPE_MECHANISMS:
            continue
        lane = lane_by_chain.get(row.get("chain_id", ""))
        if lane is None:
            raise CompletePreliminaryDeliveryError("Voie absente du référentiel actif.")
        distribution.append(
            {
                "scenario": row["scenario_id"],
                "graine": int(row["seed"]),
                "voie": row["chain_id"],
                "fournisseur": lane["supplier_id"],
                "article": _item(lane["item_id"]),
                "site": lane["dst_node_id"],
                "produit": lane["target_product_id"],
                "mecanisme": row["mechanism"],
                "variation_service_points": 100
                * _float(
                    row["target_on_due_date_proxy_delta_vs_paired_baseline"],
                    label="distribution service",
                ),
                "retard_cumule_un_jours": _float(
                    row["incremental_target_backlog_qty_days"],
                    label="distribution retard",
                ),
                "calcul_valide": row["valid"],
            }
        )
    if len(distribution) != 1080:
        raise CompletePreliminaryDeliveryError("Distribution 18×2×30 incomplète.")
    return {
        "manifest": manifest,
        "decision": final_decision,
        "state_evidence_path": state_evidence_path,
        "state_evidence": state_evidence,
        "rankings": rankings,
        "summaries": summaries,
        "distribution": distribution,
        "lanes": lanes,
    }


def _extension_and_lot_data(
    preliminary_dir: Path,
    extension_runner_dir: Path,
) -> dict[str, Any]:
    try:
        _, transport_effects, lot_summaries, lot_details, _ = (
            v2._validate_and_load_preliminary(preliminary_dir)
        )
        incidents = v2._build_incident_rows(
            transport_effects,
            lot_summaries,
            lot_details,
        )
    except Exception as error:
        raise CompletePreliminaryDeliveryError(
            f"Preuve préliminaire lots invalide: {error}"
        ) from error
    all_effects = _read_csv(preliminary_dir / "preliminary_effects_15.csv")
    selected = [
        row for row in all_effects if row.get("failure_mode") in IN_SCOPE_MECHANISMS
    ]
    checkpoint = _read_json(
        extension_runner_dir / "preliminary_checkpoint_15_manifest.json"
    )
    if (
        len(selected) != 34
        or checkpoint.get("completed_seed_count") != 15
        or checkpoint.get("signed_full_seed_count") != 30
        or checkpoint.get("executed_engine_physical_run_count") != 510
        or checkpoint.get("reused_source_stress_case_count") != 124
        or checkpoint.get("ledger_evidence_case_count") != 634
        or checkpoint.get("remaining_engine_physical_run_count") != 510
    ):
        raise CompletePreliminaryDeliveryError("Point d'arrêt 15/30 inattendu.")

    lane_pattern = re.compile(r"(sdc_vd[0-9a-z]+_[0-9]{6}_m_[0-9]+)")
    compact: list[dict[str, Any]] = []
    for row in selected:
        match = lane_pattern.search(row["case_id"])
        compact.append(
            {
                "famille_analyse": row["extension"],
                "cas": row["case_id"],
                "voie": match.group(1) if match else "plusieurs_voies",
                "mecanisme": row["failure_mode"],
                "produit": row["product_id"],
                "debut": int(row["stress_start_day"]),
                "fin": int(row["stress_end_day"]),
                "simulations": int(row["paired_seed_count"]),
                "variation_service_moyenne_points": _float(
                    row["mean_service_delta_percentage_points"],
                    label="effet extension",
                ),
                "ecart_type_points": _float(
                    row["sample_sd_service_delta_percentage_points"],
                    label="dispersion extension",
                ),
                "minimum_points": _float(
                    row["min_service_delta_percentage_points"],
                    label="minimum extension",
                ),
                "maximum_points": _float(
                    row["max_service_delta_percentage_points"],
                    label="maximum extension",
                ),
                "retard_moyen_jours_par_unite_demandee": _float(
                    row["mean_backlog_delta_days_per_demand_unit"],
                    label="retard extension",
                ),
                "preliminaire": True,
            }
        )
    availability = [row for row in compact if row["mecanisme"] == "supply_availability"]
    if not availability or any(
        not _close(row["variation_service_moyenne_points"], 0.0) for row in availability
    ):
        raise CompletePreliminaryDeliveryError(
            "Le contrôle de disponibilité masqué a changé."
        )
    dc1910_edges = [
        row for row in lot_details if "DC-1910" in str(row.get("source_id", ""))
    ]
    dc1920_rows = sum(row.get("node_id") == "DC-1920" for row in dc1910_edges)
    generic_client_rows = sum(row.get("node_id") == "C-XXXXX" for row in dc1910_edges)
    if len(dc1910_edges) != 1331 or dc1920_rows != 664 or generic_client_rows != 667:
        raise CompletePreliminaryDeliveryError(
            "Anomalie de référentiel lots inattendue."
        )
    return {
        "checkpoint": checkpoint,
        "effects": compact,
        "incidents": incidents,
        "lot_details": lot_details,
        "lot_reference_anomaly": {
            "dc1910_edge_identifier_rows": len(dc1910_edges),
            "dc1920_destination_rows": dc1920_rows,
            "generic_client_destination_rows": generic_client_rows,
        },
    }


def _landscape_data(service_dir: Path) -> list[dict[str, Any]]:
    manifest = _read_json(service_dir / "campaign_manifest.json")
    rows = _read_csv(service_dir / "scenario_summary.csv")
    selected: list[dict[str, Any]] = []
    for row in rows:
        if row.get("mechanism") not in LANDSCAPE_MECHANISMS:
            continue
        mean_service = _optional_float(row["product_on_due_date_proxy_mean"])
        delta = _optional_float(
            row["target_on_due_date_proxy_delta_vs_paired_baseline_mean"]
        )
        selected.append(
            {
                "chaine": row["chain_id"],
                "mecanisme": row["mechanism"],
                "niveau": row["level_code"],
                "valeur": row["mechanism_value"],
                "unite": row["mechanism_unit"],
                "produit": row["target_product_id"],
                "simulations": int(row["n_seeds"]),
                "service_moyen_pourcent": (
                    "" if mean_service is None else 100.0 * mean_service
                ),
                "variation_service_points": "" if delta is None else 100.0 * delta,
                "selection_confirmation": row["confirmation_selected"],
            }
        )
    if manifest.get("status") != "complete" or len(selected) != 106:
        raise CompletePreliminaryDeliveryError("Paysage de service incomplet.")
    return selected


def _stock_calibration_data(stock_dir: Path) -> dict[str, Any]:
    manifest = _read_json(stock_dir / "manifest_audit_calibration_stock_signal.json")
    audit = _read_json(stock_dir / "audit_calibration_stock_signal.json")
    rows = _read_csv(stock_dir / "materiaux_calibration_synthese.csv")
    selected: list[dict[str, Any]] = []
    for row in rows:
        selected.append(
            {
                "site": row["node_id"],
                "article": _item(row["item_id"]),
                "unite": row["uom"],
                "simulations": int(row["simulation_count"]),
                "besoin_reference_par_jour": _float(
                    row["mrp_reference_demand_qty_per_day_mean"],
                    label="besoin référence",
                ),
                "consommation_physique_par_jour": _float(
                    row["physical_consumption_avg_qty_per_calendar_day_mean"],
                    label="consommation physique",
                ),
                "rapport_besoin_sur_flux": _float(
                    row["mrp_reference_to_physical_rate_ratio_mean"],
                    label="rapport besoin flux",
                ),
                "stock_j0": _float(
                    row["stock_j0_before_production_qty_mean"], label="stock J0"
                ),
                "couverture_stock_j0_jours": _float(
                    row["stock_j0_cover_physical_days_mean"],
                    label="couverture J0",
                ),
                "statut_calibrage": row["calibration_status"],
            }
        )
    status = audit.get("status_counts", {})
    focus = {row["article"]: row for row in selected}
    if (
        manifest.get("engine_invoked") is not False
        or len(selected) != 24
        or status.get("ecart_majeur_de_calibration") != 21
        or not _close(focus["338929"]["rapport_besoin_sur_flux"], 1.000828)
        or not _close(focus["338929"]["couverture_stock_j0_jours"], 16.208135)
        or not _close(focus["344135"]["rapport_besoin_sur_flux"], 1.947126)
        or not _close(focus["344135"]["couverture_stock_j0_jours"], 88.531764)
    ):
        raise CompletePreliminaryDeliveryError("Audit stock/besoins inattendu.")
    return {"rows": selected, "status": status, "focus": focus}


def _observed_data(observed_dir: Path) -> dict[str, Any]:
    manifest = _read_json(observed_dir / "manifest.json")
    ca_summary = _read_csv(observed_dir / "observed_ca_product_summary_2025.csv")
    ca_monthly_raw = _read_csv(observed_dir / "observed_ca_monthly_2025.csv")
    stock_summary = _read_csv(observed_dir / "observed_stock_value_summary_2025.csv")
    stock_weekly_raw = _read_csv(
        observed_dir / "observed_stock_value_snapshots_2025.csv"
    )
    shortages_raw = _read_csv(
        observed_dir / "projected_finished_goods_shortage_summary.csv"
    )
    ca_monthly = [
        {
            "produit": row["product_code"],
            "mois": row["month"],
            "valeur_livree_source": row["ca_delivered_source_value"],
            "valeur_non_livree_brute_source": row["ca_lost_raw_source_value"],
            "part_livree_pourcent": 100
            * _float(row["delivered_share_of_raw_potential"], label="part mensuelle"),
            "signaux": row["lost_signal_count"],
        }
        for row in ca_monthly_raw
    ]
    stock_weekly = [
        {
            "serie": row["series_id"],
            "date": row["snapshot_date"],
            "valeur_source": row["stock_value_source"],
            "quantite_physique_disponible": False,
        }
        for row in stock_weekly_raw
    ]
    shortages = [
        {
            "produit": row["product_code"],
            "annee_releve": row["snapshot_year"],
            "releves": row["snapshot_count"],
            "releves_avec_projection": row["nonzero_snapshot_count"],
            "maximum_semaines_projetees": row["maximum_projected_shortage_weeks"],
            "premiere_semaine": row["first_nonzero_year_week"],
            "derniere_semaine": row["last_nonzero_year_week"],
        }
        for row in shortages_raw
    ]
    if (
        manifest.get("all_validation_checks_pass") is not True
        or len(ca_summary) != 2
        or len(ca_monthly) != 24
        or len(stock_summary) != 4
        or len(stock_weekly) != 208
        or len(shortages) != 4
    ):
        raise CompletePreliminaryDeliveryError("Bilan observé 2025 incomplet.")
    return {
        "manifest": manifest,
        "ca_summary": ca_summary,
        "ca_monthly": ca_monthly,
        "stock_summary": stock_summary,
        "stock_weekly": stock_weekly,
        "shortages": shortages,
    }


def _action_data(action_protocol_dir: Path, legacy_dir: Path) -> dict[str, Any]:
    protocol = _read_json(
        action_protocol_dir / "exploratory_action_protocol_manifest.json"
    )
    legacy = _read_json(legacy_dir / "canonical_cascade_summary.json")
    rows: list[dict[str, Any]] = []
    for row in legacy["aggregates"]:
        if row.get("cascade_id") != "lead_time_delay_338929_to_268091":
            continue
        rows.append(
            {
                "solution": (
                    "relative_supplier_allocation"
                    if row["solution_id"] == "supplier_priority"
                    else row["solution_id"]
                ),
                "simulations": row["seed_count"],
                "simulations_avec_effet_client_sans_action": row[
                    "customer_exposure_seed_count"
                ],
                "fidelite_du_levier": row["lever_fidelity"],
                "execution_verifiee": row[
                    "action_execution_fully_verified_for_all_seeds"
                ],
                "jours_recuperes_moyens_si_effet_client": row[
                    "mean_days_recovered_vs_no_action"
                ],
                "jours_de_penurie_evites_moyens": row["mean_shortage_days_avoided"],
                "cout_incremental_unites_modele": row[
                    "mean_incremental_decision_total_cost_vs_no_action"
                ],
                "part_retard_client_cumule_restante": row[
                    "mean_remaining_customer_impact_ratio"
                ],
            }
        )
    by_id = {row["solution"]: row for row in rows}
    expedite = by_id["expedited_transport"]
    replanning = by_id["replanning"]
    if (
        protocol.get("status") != "planned_not_executed"
        or protocol.get("engine_execution_enabled") is not False
        or len(rows) != 7
        or expedite["simulations"] != 10
        or expedite["simulations_avec_effet_client_sans_action"] != 2
        or not _close(expedite["jours_recuperes_moyens_si_effet_client"], 16.0)
        or not _close(expedite["cout_incremental_unites_modele"], 33531.94739993811)
        or not _close(
            replanning["part_retard_client_cumule_restante"], 4.422853154644835
        )
    ):
        raise CompletePreliminaryDeliveryError("Preuves d'action inattendues.")
    return {"protocol": protocol, "rows": rows, "by_id": by_id}


def _technical_status(
    dynamic_dir: Path,
    capacity_dir: Path,
    frequency_dir: Path,
    historical_frequency_dir: Path,
    control_dir: Path,
) -> dict[str, Any]:
    dynamic = _read_json(dynamic_dir / "comparison_protocol.json")
    profile = _read_json(dynamic_dir / "profile_change_audit.json")
    capacity = _read_json(capacity_dir / "capacity_coupling_audit.json")
    frequency = _read_json(frequency_dir / "canonical_frequency_manifest.json")
    historical_frequency = _read_json(
        historical_frequency_dir / "canonical_frequency_manifest.json"
    )
    control = _read_json(control_dir / "canonical_control_system_manifest.json")
    response_rows = _read_csv(frequency_dir / "canonical_frequency_response.csv")
    valid_frequency = sum(
        str(row["valid_bin"]).lower() == "true" for row in response_rows
    )
    coherent_frequency = sum(
        (_optional_float(row["coherence"]) or 0.0) >= 0.8 for row in response_rows
    )
    historical_counts = historical_frequency.get("evidence_counts", {})
    if (
        dynamic.get("status") != "planned_not_executed"
        or profile.get("new_explicit_dynamic_pair_count_after_managed_arguments") != 24
        or len(profile.get("old_explicit_dynamic_pairs_after_managed_arguments", []))
        != 3
        or capacity.get("counts", {}).get(
            "changed_requirement_pairs_with_supplier_lanes"
        )
        != 19
        or len(response_rows) != 304
        or valid_frequency != 0
        or coherent_frequency != 0
        or historical_counts.get("designed_frf_rows") != 1104
        or historical_counts.get("numerically_valid_designed_rows") != 22
        or control.get("physical_identification", {}).get("accepted") is not False
        or not _close(
            control["controller_exact_analysis"]["memory_pole"],
            0.82,
        )
    ):
        raise CompletePreliminaryDeliveryError(
            "Statut dynamique/fréquentiel inattendu."
        )
    return {
        "dynamic": dynamic,
        "profile": profile,
        "capacity": capacity,
        "frequency": frequency,
        "historical_frequency": historical_frequency,
        "control": control,
        "response_count": len(response_rows),
        "valid_frequency": valid_frequency,
        "coherent_frequency": coherent_frequency,
        "historical_response_count": 1104,
        "historical_numerically_valid_count": 22,
    }


def _descriptive_tri_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    width = 980
    left = 205
    plot_width = 650
    row_height = 29
    height = 70 + row_height * len(rows)
    scale = plot_width / 36.0
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Tri descriptif conditionnel de seize fournisseurs sous deux stress imposés">',
        '<text x="205" y="24" class="axis-title">Baisse moyenne du service, points</text>',
    ]
    for tick in (0, 10, 20, 30):
        x = left + tick * scale
        parts.append(
            f'<line x1="{x:.1f}" y1="38" x2="{x:.1f}" y2="{height - 18}" '
            'class="grid-line"/>'
            f'<text x="{x:.1f}" y="52" text-anchor="middle" class="axis">−{tick}</text>'
        )
    for index, row in enumerate(rows):
        y = 65 + index * row_height
        magnitude = min(36.0, abs(float(row["variation_service_points"])))
        bar_width = magnitude * scale
        rank = int(row["position_descriptive_moyenne"])
        color = "#155b9f" if rank <= 2 else "#8298b0"
        label = f"{rank}. {row['fournisseur']} · {row['article']}"
        parts.extend(
            (
                f'<text x="{left - 10}" y="{y + 15}" text-anchor="end" class="label">'
                f"{html.escape(label)}</text>",
                f'<rect x="{left}" y="{y}" width="{max(bar_width, 1):.1f}" '
                f'height="18" rx="4" fill="{color}"/>',
                f'<text x="{left + bar_width + 7:.1f}" y="{y + 14}" class="value">'
                f"{_fmt(row['variation_service_points'])}</text>",
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def _interval_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    selected = [
        row
        for row in rows
        if row["mecanisme"] == "transport_delay"
        and abs(float(row["variation_service_moyenne_points"])) > 0.001
    ]
    selected.sort(key=lambda row: float(row["variation_service_moyenne_points"]))
    width = 980
    left = 210
    plot_width = 680
    row_height = 58
    height = 80 + len(selected) * row_height

    def xpos(value: float) -> float:
        return left + (value + 55.0) / 55.0 * plot_width

    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Dispersion sur trente simulations des retards transport">',
        '<text x="210" y="24" class="axis-title">Variation du service, points</text>',
    ]
    for tick in (-50, -40, -30, -20, -10, 0):
        x = xpos(float(tick))
        parts.append(
            f'<line x1="{x:.1f}" y1="38" x2="{x:.1f}" y2="{height - 20}" '
            'class="grid-line"/>'
            f'<text x="{x:.1f}" y="52" text-anchor="middle" class="axis">{tick}</text>'
        )
    for index, row in enumerate(selected):
        y = 72 + index * row_height
        low = float(row["minimum_points"])
        high = float(row["maximum_points"])
        ci_low = float(row["bootstrap_descriptif_2p5_points"])
        ci_high = float(row["bootstrap_descriptif_97p5_points"])
        mean = float(row["variation_service_moyenne_points"])
        label = f"{row['article']} · {row['fournisseur']}"
        parts.extend(
            (
                f'<text x="{left - 10}" y="{y + 6}" text-anchor="end" class="label">'
                f"{html.escape(label)}</text>",
                f'<line x1="{xpos(low):.1f}" y1="{y}" x2="{xpos(high):.1f}" '
                f'y2="{y}" stroke="#94a3b8" stroke-width="4"/>',
                f'<line x1="{xpos(ci_low):.1f}" y1="{y}" x2="{xpos(ci_high):.1f}" '
                f'y2="{y}" stroke="#2563eb" stroke-width="10" stroke-linecap="round"/>',
                f'<circle cx="{xpos(mean):.1f}" cy="{y}" r="7" fill="#0f172a"/>',
                f'<text x="{xpos(mean):.1f}" y="{y + 25}" text-anchor="middle" '
                f'class="value">{_fmt(mean)}</text>',
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def _temporal_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    temporal = [row for row in rows if row["famille_analyse"] == "temporal_robustness"]
    by_item: dict[str, dict[int, Mapping[str, Any]]] = defaultdict(dict)
    for row in temporal:
        match = re.search(r"_([0-9]{6})_", str(row["cas"]))
        window = int(row["debut"]) // 180 + 1
        if match:
            by_item[match.group(1)][window] = row
    if set(by_item) != set(v2.EXPECTED_ITEMS):
        raise CompletePreliminaryDeliveryError("Matrice temporelle incomplète.")
    width, height = 940, 350
    left, top, cell_w, cell_h = 190, 70, 170, 58
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Effet du moment du retard sur quatre voies">',
        '<text x="190" y="26" class="axis-title">Baisse moyenne du service, points</text>',
    ]
    for col, window in enumerate((1, 2, 3, 4)):
        parts.append(
            f'<text x="{left + col * cell_w + cell_w / 2}" y="54" '
            f'text-anchor="middle" class="label">J{(window - 1) * 180}–J{window * 180 - 1}</text>'
        )
    for row_index, item in enumerate(("016332", "029313", "338929", "344135")):
        y = top + row_index * cell_h
        parts.append(
            f'<text x="{left - 15}" y="{y + 35}" text-anchor="end" class="label">'
            f"{item}</text>"
        )
        for col, window in enumerate((1, 2, 3, 4)):
            value = float(by_item[item][window]["variation_service_moyenne_points"])
            intensity = min(1.0, abs(value) / 50.0)
            red = int(250 - 92 * intensity)
            green = int(245 - 205 * intensity)
            blue = int(240 - 200 * intensity)
            x = left + col * cell_w
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 8}" '
                f'rx="8" fill="rgb({red},{green},{blue})"/>'
                f'<text x="{x + (cell_w - 8) / 2}" y="{y + 31}" text-anchor="middle" '
                f'class="heat-value">{_fmt(value)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _landscape_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    labels = {
        "capacity": "Capacité",
        "lead_extra": "Délai",
        "reliability": "Fiabilité",
        "availability": "Disponibilité",
        "intermittent_delay": "Retard intermittent",
    }
    chains = ("338929_m1810_268091", "344135_m1430_268967", "021081_sdc1450_268967")
    values: dict[tuple[str, str], float] = {}
    for chain in chains:
        for mechanism in labels:
            candidates = [
                _optional_float(row["service_moyen_pourcent"])
                for row in rows
                if row["chaine"] == chain and row["mecanisme"] == mechanism
            ]
            finite = [value for value in candidates if value is not None]
            values[(chain, mechanism)] = min(finite) if finite else 100.0
    width, height = 980, 330
    left, top, group_w, bar_w = 170, 55, 255, 36
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Minimum de service dans le paysage exploratoire">',
        '<text x="170" y="24" class="axis-title">Service minimum rencontré parmi les niveaux testés</text>',
    ]
    for tick in (0, 25, 50, 75, 100):
        y = top + 200 - 2 * tick
        parts.append(
            f'<line x1="{left}" y1="{y}" x2="{left + 3 * group_w}" y2="{y}" '
            'class="grid-line"/>'
            f'<text x="{left - 12}" y="{y + 4}" text-anchor="end" class="axis">{tick}%</text>'
        )
    for chain_index, chain in enumerate(chains):
        base_x = left + chain_index * group_w + 22
        for mech_index, mechanism in enumerate(labels):
            value = values[(chain, mechanism)]
            x = base_x + mech_index * (bar_w + 8)
            y = top + 200 - 2 * value
            parts.append(
                f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{2 * value:.1f}" '
                'rx="4" fill="#2563eb"/>'
                f'<text x="{x + bar_w / 2}" y="{y - 5:.1f}" text-anchor="middle" '
                f'class="value">{_fmt(value, 0)}</text>'
            )
        parts.append(
            f'<text x="{base_x + 100}" y="{top + 225}" text-anchor="middle" '
            f'class="label">{html.escape(chain)}</text>'
        )
    legend = " · ".join(
        f"{index + 1} {label}" for index, label in enumerate(labels.values())
    )
    parts.append(
        f'<text x="{left}" y="{height - 18}" class="axis">{legend}</text></svg>'
    )
    return "".join(parts)


def _line_chart(
    series: Mapping[str, Sequence[float]],
    *,
    minimum: float,
    maximum: float,
    y_label: str,
) -> str:
    width, height = 980, 300
    left, top, plot_w, plot_h = 70, 45, 840, 190

    def x(index: int, count: int) -> float:
        return left + (index / max(1, count - 1)) * plot_w

    def y(value: float) -> float:
        return top + (maximum - value) / max(1e-12, maximum - minimum) * plot_h

    colors = ("#2563eb", "#dc2626", "#059669", "#7c3aed")
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(y_label)}">',
        f'<text x="{left}" y="24" class="axis-title">{html.escape(y_label)}</text>',
    ]
    for fraction in (0.0, 0.5, 1.0):
        value = minimum + fraction * (maximum - minimum)
        yy = y(value)
        parts.append(
            f'<line x1="{left}" y1="{yy:.1f}" x2="{left + plot_w}" y2="{yy:.1f}" '
            'class="grid-line"/>'
            f'<text x="{left - 8}" y="{yy + 4:.1f}" text-anchor="end" '
            f'class="axis">{_qty(value)}</text>'
        )
    for index, (label, values) in enumerate(series.items()):
        points = " ".join(
            f"{x(point_index, len(values)):.1f},{y(float(value)):.1f}"
            for point_index, value in enumerate(values)
        )
        color = colors[index % len(colors)]
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            'stroke-width="3"/>'
            f'<line x1="{left + index * 210}" y1="{height - 28}" '
            f'x2="{left + index * 210 + 24}" y2="{height - 28}" stroke="{color}" '
            'stroke-width="4"/>'
            f'<text x="{left + index * 210 + 31}" y="{height - 23}" class="axis">'
            f"{html.escape(label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _render_html(
    *,
    network: Mapping[str, Any],
    boundary: Mapping[str, Any],
    extensions: Mapping[str, Any],
    landscape: Sequence[Mapping[str, Any]],
    regime_plan: Mapping[str, Any],
    regime_audit: Mapping[str, Any],
    stock: Mapping[str, Any],
    observed: Mapping[str, Any],
    actions: Mapping[str, Any],
    technical: Mapping[str, Any],
    nominal_payload: Mapping[str, Any],
) -> str:
    rankings = network["rankings"]
    summaries = network["summaries"]
    supplier_to_article = {
        row["fournisseur"]: row["article"] for row in network["rankings"]
    }
    nonseparation_articles = ", ".join(
        sorted(supplier_to_article[supplier] for supplier in boundary["group"])
    )
    top = {
        row["article"]: row
        for row in summaries
        if row["mecanisme"] == "transport_delay"
    }
    ranking_rows = "".join(
        "<tr>"
        f"<td>{row['position_descriptive_moyenne']}</td>"
        f"<td><strong>{html.escape(str(row['fournisseur']))}</strong></td>"
        f"<td>{html.escape(str(row['article']))} → {html.escape(str(row['site']))}</td>"
        f"<td>{html.escape(str(row['produit']))}</td>"
        f"<td>{_fmt(row['variation_service_points'])}</td>"
        f"<td>{row['presence_parmi_3_plus_fortes_baisses_sur_30']}/30</td>"
        f"<td>{html.escape(str(row['statut']))}</td>"
        "</tr>"
        for row in rankings
    )
    temporal_rows = [
        row
        for row in extensions["effects"]
        if row["famille_analyse"] == "temporal_robustness"
    ]
    temporal_table = "".join(
        "<tr>"
        f"<td>{re.search(r'_([0-9]{6})_', str(row['cas'])).group(1)}</td>"
        f"<td>J{row['debut']}–J{row['fin']}</td>"
        f"<td>{_fmt(row['variation_service_moyenne_points'])}</td>"
        f"<td>{_fmt(row['ecart_type_points'])}</td>"
        f"<td>{_fmt(row['minimum_points'])} à {_fmt(row['maximum_points'])}</td>"
        "</tr>"
        for row in temporal_rows
    )
    lot_cards = "".join(
        f"<article class='lot-card' data-lot='{row['item_id']}'>"
        f"<h3>{row['item_id']} → {row['destination']} → {row['target_product_id']}</h3>"
        "<div class='chain'>"
        f"<span><b>{row['root_receipt_record_count']}</b> réception(s)<small>"
        f"{_qty(row['root_quantity'])} {row['root_uom']}</small></span><i>→</i>"
        f"<span><b>{row['production_descendant_count']}</b> enregistrements<small>production</small></span><i>→</i>"
        f"<span><b>{row['platform_descendant_count']}</b> enregistrements<small>plateforme</small></span><i>→</i>"
        f"<span><b>{row['generic_client_descendant_count']}</b> enregistrements<small>client générique</small></span>"
        "</div>"
        f"<p>Service simulé : <strong>{_fmt(row['mean_service_change_percentage_points'])} points</strong> en moyenne sur 15 simulations. La filiation détaillée provient d'une illustration technique.</p>"
        "</article>"
        for row in extensions["incidents"]
    )
    stock_focus = stock["focus"]
    ca_cards = "".join(
        f"<article class='metric-card'><span>Produit {row['product_code']}</span>"
        f"<strong>{_fmt(100 * float(row['delivered_share_of_raw_potential']))} %</strong>"
        f"<small>part financière livrée</small>"
        f"<p>Valeur livrée : {_qty(row['ca_delivered_source_value'])}<br>"
        f"Non livrée brute : {_qty(row['ca_lost_raw_source_value'])}<br>"
        f"Non livrée positive : {_qty(row['ca_lost_positive_only_source_value'])}</p></article>"
        for row in observed["ca_summary"]
    )
    stock_cards = "".join(
        f"<article class='metric-card'><span>{html.escape(row['series_id'])}</span>"
        f"<strong>{_qty(row['mean_stock_value_source'])}</strong>"
        f"<small>valeur moyenne 2025</small>"
        f"<p>Minimum {_qty(row['minimum_stock_value_source'])} · maximum {_qty(row['maximum_stock_value_source'])} · 52 relevés</p></article>"
        for row in observed["stock_summary"]
    )
    shortage_rows = "".join(
        "<tr>"
        f"<td>{row['produit']}</td><td>{row['annee_releve']}</td>"
        f"<td>{row['releves_avec_projection']}/{row['releves']}</td>"
        f"<td>{_fmt(row['maximum_semaines_projetees'], 0)}</td>"
        f"<td>{row['premiere_semaine'] or '—'} à {row['derniere_semaine'] or '—'}</td>"
        "</tr>"
        for row in observed["shortages"]
    )
    action_labels = {
        "combined_response": "Réponse combinée",
        "emergency_purchase": "Achat exceptionnel (approximation)",
        "expedited_transport": "Transport accéléré",
        "replanning": "Replanification multiplicative",
        "second_supplier_proxy": "Seconde source (approximation)",
        "relative_supplier_allocation": "Allocation relative fournisseur (ancien essai)",
        "targeted_stock": "Stock ciblé",
    }
    action_rows = "".join(
        "<tr>"
        f"<td><strong>{action_labels[row['solution']]}</strong></td>"
        f"<td>{row['simulations_avec_effet_client_sans_action']}/{row['simulations']}</td>"
        f"<td>{_fmt(row['jours_recuperes_moyens_si_effet_client'])}</td>"
        f"<td>{_qty(row['cout_incremental_unites_modele'])}</td>"
        f"<td>{_fmt(100 * float(row['part_retard_client_cumule_restante']))} %</td>"
        "</tr>"
        for row in actions["rows"]
    )
    ca_series: dict[str, list[float]] = defaultdict(list)
    for row in observed["ca_monthly"]:
        ca_series[f"Produit {row['produit']}"].append(
            float(row["part_livree_pourcent"])
        )
    stock_series: dict[str, list[float]] = defaultdict(list)
    for row in observed["stock_weekly"]:
        stock_series[row["serie"]].append(float(row["valeur_source"]))
    legacy_combined = regime_audit["legacy_combined_campaign"]
    legacy_stock = regime_audit["legacy_stock_773474_campaign"]
    exact_controller = technical["control"]["controller_exact_analysis"]
    physical = technical["control"]["physical_identification"]

    document = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilan consolidé du périmètre retenu</title>
<style>
:root{{--ink:#10233f;--blue:#1769c2;--pale:#eef4fa;--line:#d7e2ee;--red:#b42318;--amber:#a15c00;--green:#087a55}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f7;color:var(--ink);font:15px/1.5 Inter,system-ui,sans-serif}}
header{{background:linear-gradient(120deg,#0b2344,#155b9f);color:#fff;padding:28px max(20px,calc((100vw - 1450px)/2)) 22px}}
header h1{{margin:0 0 7px;font-size:clamp(1.7rem,3vw,2.8rem)}}header p{{margin:3px 0;max-width:1100px}}
.legend{{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}}.pill{{border:1px solid #ffffff55;border-radius:999px;padding:5px 10px}}
nav{{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);display:flex;gap:8px;padding:10px max(15px,calc((100vw - 1450px)/2))}}
nav button{{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;padding:10px 16px;cursor:pointer;font-weight:700}}
nav button.active{{background:var(--blue);color:#fff;border-color:var(--blue)}}main{{max-width:1450px;margin:auto;padding:18px}}
.view{{display:none}}.view.active{{display:block}}section,.card{{background:#fff;border:1px solid var(--line);border-radius:15px;padding:18px;margin:14px 0;box-shadow:0 5px 18px #17375e0a}}
.hero{{border-left:7px solid var(--blue)}}.warning{{background:#fff8e8;border-color:#efbd67}}.danger{{background:#fff1ef;border-color:#e59a91}}.success{{background:#ecf9f3;border-color:#83ccb2}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.metric-card{{background:#f8fbff;border:1px solid var(--line);border-radius:12px;padding:14px}}
.metric-card span,.metric-card small{{display:block;color:#55677c}}.metric-card strong{{display:block;font-size:1.8rem;margin:5px 0}}h2{{margin-top:0}}h3{{margin-bottom:5px}}.muted{{color:#596b80}}.small{{font-size:13px}}
.chart{{display:block;width:100%;min-width:720px;height:auto;background:#fbfdff;border:1px solid var(--line);border-radius:12px}}.chart-wrap{{overflow:auto}}.grid-line{{stroke:#dce5ef;stroke-width:1}}.axis{{font-size:12px;fill:#617187}}.axis-title{{font-size:14px;font-weight:700;fill:#203b5e}}.label{{font-size:12px;fill:#203b5e}}.value{{font-size:11px;font-weight:700;fill:#203b5e}}.heat-value{{font-size:15px;font-weight:800;fill:#10233f}}
.table-wrap{{overflow:auto;max-height:540px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:8px 9px;border-bottom:1px solid #e1e8f0;text-align:left;vertical-align:top}}th{{background:#edf4fb;position:sticky;top:0;z-index:1}}
a.button{{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;border-radius:9px;padding:9px 13px;margin:4px 4px 4px 0}}a.secondary{{background:#e7f0fa;color:#184876}}
.chain{{display:flex;align-items:stretch;gap:8px;overflow:auto;padding:8px 0}}.chain span{{min-width:150px;flex:1;border:1px solid #bfd1e5;background:#f4f9ff;border-radius:10px;padding:12px;text-align:center}}.chain b,.chain small{{display:block}}.chain b{{font-size:1.35rem}}.chain i{{align-self:center;font-size:1.4rem}}.lot-card{{display:none}}.lot-card.active{{display:block}}
.lot-picker button{{padding:7px 11px;border:1px solid var(--line);background:#fff;border-radius:8px;margin:3px;cursor:pointer}}.lot-picker button.active{{background:#10233f;color:#fff}}
.status-table td:first-child{{font-weight:800}}details{{border-top:1px solid var(--line);padding:10px 0}}summary{{cursor:pointer;font-weight:700}}
@media(max-width:760px){{nav{{overflow:auto;white-space:nowrap}}main{{padding:10px}}section{{padding:14px}}.chain i{{display:none}}}}
@media print{{nav{{display:none}}.view{{display:block!important;break-before:page}}body{{background:#fff}}section{{box-shadow:none}}}}
</style></head><body>
<header><h1>Bilan consolidé du périmètre retenu</h1>
<p><strong>Objet :</strong> montrer où le réseau simulé est vulnérable, comment un retard peut se propager jusqu'aux lots et quelles décisions sont réellement étayées aujourd'hui.</p>
<div class="legend"><span class="pill"><b>OBSERVÉ</b> : extrait des fichiers industriels 2025</span><span class="pill"><b>SIMULÉ</b> : réponse du modèle à une hypothèse</span><span class="pill"><b>ORDRE FOURNISSEUR</b> : non validé</span><span class="pill"><b>HYPOTHÈSE</b> : paramètre ou action à valider</span></div></header>
<nav aria-label="Trois vues"><button class="active" data-view="vue1">1. Vulnérabilités réseau</button><button data-view="vue2">2. Incidents, états et lots</button><button data-view="vue3">3. Décisions et preuves</button></nav>
<main>
<div id="vue1" class="view active">
<section class="hero"><h2>Deux baisses descriptives se détachent, sans ordre fournisseur validé</h2><div class="grid"><article class="metric-card"><span>Résultats réseau</span><strong>1 255</strong><small>exécutés ou réextraits ; ce ne sont pas 1 255 nouvelles exécutions</small></article><article class="metric-card"><span>Périmètre actif</span><strong>16 / 18</strong><small>fournisseurs / voies</small></article><article class="metric-card"><span>Tirages comparables</span><strong>30</strong><small>mêmes conditions aléatoires pour comparer l'incident et la référence</small></article><article class="metric-card"><span>Conclusion</span><strong>Aucun ordre</strong><small>fournisseur validé</small></article></div>
<p><strong>Transparence du périmètre :</strong> 1 765 exécutions uniques sont inventoriées dans les deux campagnes ; 1 513 appartiennent aux branches retenues ici et 252 ont été explicitement écartées du périmètre demandé.</p>
<p>Dans ce <strong>tri descriptif conditionnel sous deux stress imposés</strong>, <strong>344135 → M-1430 → 268967</strong> ({_fmt(top["344135"]["variation_service_moyenne_points"])} points en moyenne) et <strong>338929 → M-1810 → 268091</strong> ({_fmt(top["338929"]["variation_service_moyenne_points"])} points) présentent les deux plus fortes baisses moyennes. <strong>Aucun ordre de priorité fournisseur n'est validé</strong> et ces résultats n'établissent pas une criticité observée.</p>
<p>Pour 344135, l'intervalle bootstrap descriptif 2,5–97,5 % sur les mêmes 30 tirages est [{_fmt(top["344135"]["bootstrap_descriptif_2p5_points"])} ; {_fmt(top["344135"]["bootstrap_descriptif_97p5_points"])}] points ; pour 338929, [{_fmt(top["338929"]["bootstrap_descriptif_2p5_points"])} ; {_fmt(top["338929"]["bootstrap_descriptif_97p5_points"])}]. Ces intervalles sont non confirmatoires : les mêmes tirages servent au tri et à l'évaluation, sans correction de sélection ni des comparaisons multiples.</p>
<p>L'audit de frontière ne sépare pas le groupe <strong>{nonseparation_articles.replace(", 344135", " et 344135")}</strong>. Aucun ensemble de fournisseurs à traiter en premier n'est validé.</p></section>
<section><h2>Tri descriptif conditionnel par baisse moyenne sous deux stress imposés</h2><div class="chart-wrap">{_descriptive_tri_svg(rankings)}</div><p class="small muted">Chaque ligne retient la plus forte baisse moyenne de la voie entre les deux stress imposés. Un zéro signifie « effet non mesuré dans cette configuration », pas « risque nul ». La position est descriptive et ne constitue pas un ordre fournisseur.</p><div class="table-wrap"><table><thead><tr><th>Position descriptive</th><th>Fournisseur</th><th>Voie</th><th>Produit</th><th>Variation service (pt)</th><th>Présence parmi les 3 plus fortes baisses</th><th>Lecture</th></tr></thead><tbody>{ranking_rows}</tbody></table></div><a class="button secondary" href="{RANKING_CSV}">Télécharger le tri descriptif</a></section>
<section><h2>Dispersion des 30 tirages</h2><div class="chart-wrap">{_interval_svg(summaries)}</div><p><span style="color:#94a3b8">Trait gris</span> : minimum–maximum ; <span style="color:#2563eb">trait bleu</span> : intervalle bootstrap descriptif 2,5–97,5 % de la moyenne sur les mêmes 30 tirages ; point noir : moyenne. Ces intervalles sont non confirmatoires et ne corrigent ni la sélection ni les comparaisons multiples. Le fichier détaillé contient les 1 080 réponses individuelles des 18 voies × 2 mécanismes × 30 tirages.</p><a class="button secondary" href="{NETWORK_SUMMARY_CSV}">Résumé des 36 cas</a><a class="button secondary" href="{NETWORK_DISTRIBUTION_CSV}">1 080 réponses individuelles</a></section>
<section class="warning"><h2>Carte du réseau enrichie par le run nominal actuel</h2><p>La carte topologique hors ligne conserve ses anciens onglets. Dans <strong>Run nominal</strong>, le nouveau bouton <strong>Courbes du run nominal actuel</strong> affiche {nominal_payload["chain_count"]} chaînes sur {nominal_payload["horizon_days"]} jours : stocks composants, expéditions, réceptions, production libérée, stock produit fini, demande, service et retard client. Il s'agit d'une seule réalisation simulée sans incident ; la coloration par les résultats de risque actuels et les cascades ne sont pas encore intégrées.</p><a class="button" href="{MAP_ASSET}">Ouvrir la carte autonome</a><a class="button secondary" href="{NOMINAL_TRAJECTORY_CSV}">Données quotidiennes compactes</a></section>
</div>

<div id="vue2" class="view">
<section class="hero"><h2>Le moment de l'incident change fortement le résultat</h2><div class="grid"><article class="metric-card"><span>Point d'arrêt</span><strong>15 / 30</strong><small>préliminaire, non final</small></article><article class="metric-card"><span>Nouveaux calculs</span><strong>510</strong><small>au point d'arrêt</small></article><article class="metric-card"><span>Résultats réutilisés</span><strong>124</strong><small>traçabilité conservée</small></article><article class="metric-card"><span>Cellules présentées</span><strong>34</strong><small>retard et disponibilité</small></article></div><p>Cette extension répond à une question métier simple : « le même incident fait-il les mêmes dégâts toute l'année ? » La réponse est non. Les résultats ci-dessous sont provisoires à 15 simulations sur 30.</p></section>
<section><h2>Quatre fenêtres calendaires pour quatre voies</h2><div class="chart-wrap">{_temporal_svg(extensions["effects"])}</div><p><strong>338929</strong> reste pénalisant en moyenne dans les quatre fenêtres (−32,36 ; −46,85 ; −27,09 ; −48,36 points). <strong>344135</strong> est défavorable en moyenne dans les quatre fenêtres, de −28,99 à −6,00 points, mais certains tirages donnent zéro dans les fenêtres 2 et 4. <strong>029313</strong> ne présente un effet moyen que sur J180–J359. <strong>016332</strong> est intermittent et atteint −10,42 points dans sa fenêtre la plus sensible. Cela illustre une réponse dépendante de l'état simulé : stocks, encours, calendrier et lots présents au début du choc changent la propagation.</p><details><summary>Voir les 16 cellules et leur dispersion</summary><div class="table-wrap"><table><thead><tr><th>Article</th><th>Fenêtre</th><th>Moyenne (pt)</th><th>Écart-type</th><th>Min–max</th></tr></thead><tbody>{temporal_table}</tbody></table></div></details><a class="button secondary" href="{EXTENSION_CSV}">Télécharger les 34 cellules</a></section>
<section><h2>Incident commun et disponibilité : deux diagnostics importants</h2><div class="grid"><article class="metric-card"><span>Retard simultané · VD0519670A</span><strong>−5,01 pt</strong><small>effet dans 5 simulations sur 15</small><p>Dans ce cas et cette fenêtre seulement, le résultat est identique à la voie 029313 seule : <strong>aucune amplification supplémentaire n'est mesurée</strong>.</p></article><article class="metric-card"><span>Retard simultané · VD0520132A</span><strong>0,00 pt</strong><small>deux produits suivis</small><p>Aucun effet client mesuré dans la configuration testée.</p></article><article class="metric-card"><span>Disponibilité temporaire à 50 %</span><strong>0,00 pt</strong><small>sur les cellules présentées</small><p>Le mécanisme est <strong>masqué ou mal calibré</strong>. Ce zéro n'est pas une preuve de robustesse.</p></article></div></section>
<section><h2>Paysage exploratoire du service</h2><div class="chart-wrap">{_landscape_svg(landscape)}</div><p>Le graphique montre, pour trois chaînes et cinq familles de paramètres, le service minimum rencontré parmi les niveaux testés. Les niveaux n'ont pas tous le même nombre de simulations : cette vue localise des seuils et ne fournit pas une moyenne industrielle.</p><a class="button secondary" href="{LANDSCAPE_CSV}">Ouvrir les 106 points</a></section>
<section class="warning"><h2>Repères 93 % et 80 % : indices anciens, nouvelle campagne non exécutée</h2><p><strong>Ancien indice combiné, 10 simulations :</strong> produit 268091 à {_fmt(100 * legacy_combined["mean_fill_268091"])} % en moyenne (plage {_fmt(100 * legacy_combined["min_fill_268091"])}–{_fmt(100 * legacy_combined["max_fill_268091"])} %) et produit 268967 à {_fmt(100 * legacy_combined["mean_fill_268967"])} %. Trois familles avaient été changées ensemble, sur 365 jours, avec une ancienne définition du service : ces chiffres <strong>ne constituent pas deux régimes globaux validés</strong>.</p><p><strong>Ancien indice stock, une seule simulation :</strong> {_fmt(100 * legacy_stock["cover_300d_proxy"])} % à 300 jours de couverture, {_fmt(100 * legacy_stock["cover_384d_proxy"])} % à 384 jours et {_fmt(100 * legacy_stock["cover_385d_proxy"])} % à 385 jours. La discontinuité de lot saute le voisinage de 93 %.</p><p><strong>Nouveau plan :</strong> {regime_plan["screening_candidate_count"]} configurations prévues, aucune exécutée. Les cibles 93/80 restent à calculer avec la définition sur date promise, sans rattrapage tardif compté à l'heure.</p></section>
<section><h2>Hypothèse heuristique à tester : stock et besoin de référence</h2><div class="grid"><article class="metric-card"><span>Audit des 24 matières</span><strong>21 / 24</strong><small>présentent un écart majeur de calibrage</small><p>Le réglage ressort comme une piste explicative possible, sans démonstration causale.</p></article><article class="metric-card"><span>338929</span><strong>{_fmt(stock_focus["338929"]["rapport_besoin_sur_flux"], 3)}×</strong><small>besoin de référence / flux physique</small><p>Couverture J0 moyenne : {_fmt(stock_focus["338929"]["couverture_stock_j0_jours"])} jours.</p></article><article class="metric-card"><span>344135</span><strong>{_fmt(stock_focus["344135"]["rapport_besoin_sur_flux"], 3)}×</strong><small>besoin de référence / flux physique</small><p>Couverture J0 moyenne : {_fmt(stock_focus["344135"]["couverture_stock_j0_jours"])} jours.</p></article></div><p>338929 est proche du flux effectivement consommé. Pour 344135, le besoin de référence est presque deux fois le flux et la couverture J0 dépasse 88 jours. Cette lecture reste une <strong>hypothèse heuristique</strong> : aucun nouveau calcul avec calibrage corrigé n'a été exécuté, aucune causalité n'est établie et ce réglage n'est pas présenté comme l'unique verrou. Les seuils de l'audit ne sont pas calibrés sur l'historique industriel.</p><a class="button secondary" href="{STOCK_CALIBRATION_CSV}">Voir les 24 matières</a></section>
<section><h2>Du composant au client : ce que les lots prouvent réellement</h2><div class="lot-picker" role="group" aria-label="Choisir un article">{"".join(f'<button data-lot-choice="{item}" class="{"active" if item == "338929" else ""}">{item}</button>' for item in ("338929", "344135", "029313", "016332"))}</div>{lot_cards}<p class="warning"><strong>Limite essentielle :</strong> les 2 231 lignes sont des enregistrements de filiation technique provenant de quatre illustrations, pas 2 231 lots physiques perdus ou retardés. Un descendant est relié à une réception exposée ; la causalité individuelle et l'identité d'un même lot entre deux simulations ne sont pas établies. Les quantités aval répètent le flux à plusieurs étapes et ne doivent pas être additionnées.</p><p><strong>Anomalie exacte à arbitrer :</strong> 1 331 identifiants d'arête contiennent DC-1910 ; parmi ces lignes, 664 aboutissent au nœud DC-1920 et 667 à un client générique. Les identifiants de lots sont générés par le moteur. Cette discordance interdit une attribution industrielle avant correction du référentiel.</p><a class="button secondary" href="{LOT_SUMMARY_CSV}">Synthèse des quatre chaînes</a><a class="button secondary" href="{LOT_DETAIL_CSV}">Détail des 2 231 enregistrements</a></section>
</div>

<div id="vue3" class="view">
<section class="hero"><h2>Les données 2025 donnent un contexte réel, pas encore une probabilité fournisseur</h2><div class="grid">{ca_cards}</div><p>Ces ratios décrivent la part de valeur source livrée sur la valeur potentielle. Ils ne sont ni un OTIF ni un taux de service en unités. La source ne déclare pas sa devise ; les montants sont donc affichés en <strong>unités monétaires de la source</strong>. Pour 268091, la valeur brute non livrée est 1 611 174 et la somme des valeurs positives 1 611 220 ; l'écart de −45,86 correspond à une correction négative non documentée.</p></section>
<section><h2>Évolution mensuelle de la part financière livrée</h2><div class="chart-wrap">{_line_chart(ca_series, minimum=70, maximum=100, y_label="Part financière livrée (%)")}</div><a class="button secondary" href="{OBSERVED_CA_CSV}">Données mensuelles 2025</a></section>
<section><h2>Stocks observés 2025 — valeurs comptables hebdomadaires</h2><div class="grid">{stock_cards}</div><div class="chart-wrap">{_line_chart(stock_series, minimum=0, maximum=max(max(values) for values in stock_series.values()) * 1.05, y_label="Valeur comptable agrégée, devise à confirmer")}</div><p>Ces séries ne contiennent ni quantité physique, ni unité, ni article composant, ni site, ni statut de disponibilité, ni lot. Le lien Cos/Pharma vers les produits finis est contradictoire entre anciens référentiels et doit être confirmé.</p><a class="button secondary" href="{OBSERVED_STOCK_CSV}">208 relevés hebdomadaires</a></section>
<section><h2>Projections de rupture présentes dans les données</h2><div class="table-wrap"><table><thead><tr><th>Produit</th><th>Année du relevé</th><th>Relevés avec signal</th><th>Maximum projeté (semaines)</th><th>Période</th></tr></thead><tbody>{shortage_rows}</tbody></table></div><p>Ce sont des projections prises à plusieurs dates, pas des ruptures réalisées. Les additionner compterait potentiellement plusieurs fois le même événement futur.</p><a class="button secondary" href="{OBSERVED_SHORTAGE_CSV}">Détail compact</a></section>
<section class="warning"><h2>Leviers d'action : nouveau protocole préparé, aucun nouveau résultat</h2><p>Le protocole actuel prévoit transport planifié, stock déjà présent à J0 et alternative fournisseur explicitement documentée. Il est au statut <strong>préparé, non exécuté</strong>. Aucun coût industriel, aucun jour récupéré et aucune recommandation ne peuvent encore être tirés de ce protocole.</p><h3>Ancien essai séparé sur 338929 — à ne pas transférer au scénario actuel</h3><p>Ce test antérieur porte sur 10 simulations, un ajout de <strong>35 jours</strong> pour les départs libérés entre J0 et J89, avec un état initial et un protocole différents du retard de 120 jours de la campagne réseau actuelle.</p><div class="table-wrap"><table><thead><tr><th>Solution ancienne</th><th>Cas exposés</th><th>Jours récupérés</th><th>Coût, unités modèle</th><th>Part du retard client cumulé restant</th></tr></thead><tbody>{action_rows}</tbody></table></div><p><strong>Lecture honnête :</strong> le transport accéléré récupère 16 jours dans les 2 simulations exposées sur 10, pour 33 532 unités de coût du modèle — <strong>pas des euros</strong>. Pour cette métrique, 0 % signifie 0 UN·jour additionnel restant dans ces 2 cas exposés, pas l'absence de tout impact sur le réseau. La replanification multiplicative est contre-productive dans cet essai : récupération −11,5 jours et part du retard client cumulé restante 442 %. Le stock ciblé et l'approximation de seconde source ne réduisent pas cette métrique ; ils ne sont pas concluants.</p><a class="button secondary" href="{ACTION_CSV}">Résultats anciens filtrés</a></section>
<section><h2>Dynamique, boucle fermée et fréquentiel : preuves et limites</h2><p class="warning"><strong>Frontière essentielle :</strong> les flux physiques et le MRP évoluent avec les stocks, le transit et le backlog, mais les incidents fournisseurs de cette campagne sont des chocs exogènes imposés. Dans les exécutions réseau utilisées, le générateur de risque fournisseur dépendant de l'état est désactivé (<code>supplier_state_dependent_risk.enabled=false</code>). Seules 3 paires sur 24 utilisent déjà un besoin dynamique ; la variante 24/24 est préparée mais non exécutée. Le modèle ne fournit donc ni probabilité de risque fournisseur endogène ni prévision historique.</p><div class="grid"><article class="metric-card"><span>Variante besoins dynamiques</span><strong>24 / 24</strong><small>préparée, non exécutée ; réseau actuel 3 / 24</small><p>Elle remplace 21 couples encore statiques mais modifie aussi des capacités/politiques amont ; elle n'isole donc pas le seul calcul du besoin.</p></article><article class="metric-card"><span>Couplage analytique</span><strong>19 couples</strong><small>27 voies fournisseur</small><p>22 capacités directes et 21 capacités amont seraient modifiées selon les formules ; ce ne sont pas des résultats simulés.</p></article><article class="metric-card"><span>Dernier pilote en boucle fermée</span><strong>{technical["valid_frequency"]} / {technical["response_count"]}</strong><small>réponses numériquement fiables</small><p>Aucune cohérence ≥ 0,80 ; aucun délai local, Bode supply ou marge de stabilité fiable.</p></article><article class="metric-card"><span>Audit historique plus large</span><strong>{technical["historical_numerically_valid_count"]} / {technical["historical_response_count"]}</strong><small>réponses numériquement exploitables</small><p>Ces 22 réponses ne constituent pas une preuve physique acceptée du réseau.</p></article><article class="metric-card"><span>Pôle exact</span><strong>z = {_fmt(exact_controller["memory_pole"], 2)}</strong><small>mémoire interne du régulateur</small><p>Constante de temps {_fmt(exact_controller["time_constant_days"])} jours, demi-vie {_fmt(exact_controller["half_life_days"])} jours. Ce n'est pas un pôle physique de la supply.</p></article></div><p>Le modèle DMDc exploratoire d'ordre {physical["selected_order"]} propose z = {_fmt(physical["matrices_normalized_coordinates"]["A"][0][0], 4)}, mais il est <strong>rejeté</strong> : zone morte sur la cible de production et validation non indépendante. La mémoire scalaire du contrôleur est commandable et observable (rang 1/1), mais la contrôlabilité et l'observabilité globales de la supply ne sont pas établies. Aucun Nyquist de la boucle physique complète n'est revendiqué.</p></section>
<section><h2>Ce bilan n'est pas encore la validation industrielle complète demandée</h2><p>La distinction ci-dessous est volontairement stricte : un protocole codé mais non exécuté n'est pas présenté comme un résultat.</p><div class="table-wrap"><table class="status-table"><thead><tr><th>Sujet</th><th>Statut exact</th><th>Ce que l'on peut dire aujourd'hui</th></tr></thead><tbody>
<tr><td>Vulnérabilité du réseau</td><td style="color:var(--green)">CALCULÉ</td><td>16 fournisseurs, 18 voies, 2 stress imposés et 30 tirages comparables sur 720 jours. Il s'agit d'une sensibilité conditionnelle, pas d'une probabilité historique ni d'un ordre fournisseur validé.</td></tr>
<tr><td>Influence de la date de l'incident</td><td style="color:var(--amber)">PRÉLIMINAIRE 15/30</td><td>Quatre fenêtres sont comparées sur quatre voies ; les 15 réalisations restantes des branches retenues ne sont pas terminées.</td></tr>
<tr><td>Données industrielles 2025</td><td style="color:var(--green)">OBSERVÉ, AGRÉGÉ</td><td>Valeurs de stock, part financière livrée et projections de rupture sont présentes, sans rattachement fiable à un fournisseur, un lot physique ou une commande.</td></tr>
<tr><td>Suivi des lots</td><td style="color:var(--amber)">GÉNÉALOGIE TECHNIQUE</td><td>Les chaînes d'exposition peuvent être explorées, mais la perte et le retard de chaque lot ne sont pas encore attribuables causalement.</td></tr>
<tr><td>Références de service 93 % et 80 %</td><td style="color:var(--amber)">PRÉPARÉ, NON EXÉCUTÉ</td><td>36 configurations sont prévues ; aucune campagne actuelle n'établit encore ces deux niveaux avec la définition retenue du service.</td></tr>
<tr><td>Leviers opérationnels actuels</td><td style="color:var(--amber)">PRÉPARÉ, NON EXÉCUTÉ</td><td>Le protocole existe. Le seul chiffre disponible vient d'un ancien essai différent sur 10 simulations et ne permet pas de recommander une action pour le stress actuel.</td></tr>
<tr><td>Dynamique complète des besoins</td><td style="color:var(--amber)">PARTIEL 3/24</td><td>La variante 24/24 est préparée mais non exécutée ; son effet sur les résultats n'est donc pas mesuré.</td></tr>
<tr><td>Risque fournisseur dépendant de l'état</td><td style="color:var(--red)">DÉSACTIVÉ DANS CETTE CAMPAGNE</td><td>Les incidents présentés sont des chocs imposés. Cette campagne ne produit pas une probabilité endogène de risque fournisseur.</td></tr>
<tr><td>Sensibilité globale et Monte-Carlo multifactoriel</td><td style="color:var(--red)">NON RÉALISÉ</td><td>Les 30 tirages ne font varier que l'aléa de délai du modèle, à demande et sévérité fixes. Ils ne couvrent pas toute l'incertitude de la supply.</td></tr>
<tr><td>Prévision fournisseur et erreurs d'alerte</td><td style="color:var(--red)">DONNÉES MANQUANTES</td><td>Sans historique commande–date promise–réception–incident, les probabilités, faux positifs et faux négatifs ne sont pas estimables sur ce cas industriel.</td></tr>
<tr><td>Socle transactionnel fournisseurs et lots</td><td style="color:var(--red)">DONNÉES MANQUANTES</td><td>Les dates promises et reçues par ligne, incidents, coûts, stocks libres et identifiants de lots industriels ne sont pas reliés dans une table exploitable.</td></tr>
<tr><td>Conversion prévision → perturbation physique</td><td style="color:var(--red)">NON CALIBRÉ SUR CE CAS</td><td>Les enveloppes de délai, capacité et quantité utilisable restent des hypothèses de simulation ; elles ne sont pas encore reliées à des intervalles de prévision fournisseur mesurés.</td></tr>
<tr><td>Régimes dynamiques de la supply</td><td style="color:var(--red)">NON CALIBRÉ MÉTIER</td><td>Le POC de classification existe, mais les seuils et transitions ne sont pas validés sur des journées annotées par les équipes industrielles.</td></tr>
<tr><td>Boucle fermée, pôles et fréquentiel physique</td><td style="color:var(--red)">NON VALIDÉ</td><td>Le dernier test ne fournit aucune réponse fiable sur 304. Le pôle z = 0,82 décrit seulement la mémoire interne du régulateur, pas la supply.</td></tr>
<tr><td>Courbes journalières à tous les nœuds</td><td style="color:var(--amber)">PARTIEL — 2 CHAÎNES</td><td>Les trajectoires nominales 338929 → 268091 et 344135 → 268967 sont maintenant visibles avec lissages adaptés 7/28 jours et mode brut. Tous les nœuds et les scénarios perturbés ne sont pas encore consolidés.</td></tr>
<tr><td>Carte enrichie et suivi des lots dans la carte</td><td style="color:var(--amber)">PARTIEL</td><td>Le run nominal actuel est intégré sans remplacer les anciens onglets. La carte ne colore pas encore le réseau avec les résultats de risque actuels et son ancien filtre de lots n'est pas alimenté par une attribution causale.</td></tr>
<tr><td>Coûts réels et validation métier du risque créé</td><td style="color:var(--red)">EN ATTENTE MÉTIER</td><td>Les coûts réels, alternatives approuvées et évaluations achats/planification ne sont pas disponibles ; aucun gain financier ne peut être promis.</td></tr>
</tbody></table></div><p>La matrice de calibrage établit seulement que <strong>21 matières sur 24 présentent un écart majeur</strong> selon les seuils heuristiques ; elle ne démontre ni biais causal ni verrou unique.</p><a class="button secondary" href="{DECISION_MATRIX_CSV}">Télécharger cette matrice de statut</a></section>
<section class="success"><h2>Suite recommandée</h2><ol><li>Figer les résultats actuels comme provisoires et ne pas lancer aveuglément les 15 réalisations restantes.</li><li>Valider d'abord les stocks J0, unités, statuts, besoins, pipeline et capacités ; tester les 21 écarts majeurs de calibrage dans un calcul dédié.</li><li>Exécuter ensuite la référence dynamique 24/24 et la calibration 93/80 sur 720 jours, une famille structurelle à la fois.</li><li>Sur la référence corrigée, reprendre la sensibilité multifactorielle puis comparer les leviers par conditions aléatoires identiques, avec coûts documentés.</li><li>Collecter l'historique commandes–promesses–réceptions–incidents–lots afin de rendre possible une prévision fournisseur mesurable et son contrôle FP/FN.</li></ol></section>
</div></main>
<script>
const tabs=[...document.querySelectorAll('[data-view]')];const views=[...document.querySelectorAll('.view')];
function showView(id){{views.forEach(v=>v.classList.toggle('active',v.id===id));tabs.forEach(b=>b.classList.toggle('active',b.dataset.view===id));history.replaceState(null,'','#'+id);window.scrollTo(0,0)}}
tabs.forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));
const requested=location.hash.slice(1);if(views.some(v=>v.id===requested))showView(requested);
const lotButtons=[...document.querySelectorAll('[data-lot-choice]')];const lotCards=[...document.querySelectorAll('[data-lot]')];
function showLot(item){{lotButtons.forEach(b=>b.classList.toggle('active',b.dataset.lotChoice===item));lotCards.forEach(c=>c.classList.toggle('active',c.dataset.lot===item))}}
lotButtons.forEach(button=>button.addEventListener('click',()=>showLot(button.dataset.lotChoice)));showLot('338929');
</script></body></html>"""
    return document.replace(
        "Du composant au client : ce que les lots prouvent réellement",
        "Du composant au client : ce que la généalogie technique permet de suivre",
    )


def _source_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: _sha256(path) for name, path in sorted(paths.items())}


def _assert_output_text(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".csv"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError as error:
            raise CompletePreliminaryDeliveryError(
                f"Fichier non UTF-8: {path.relative_to(root)}"
            ) from error
        if "\ufffd" in text:
            raise CompletePreliminaryDeliveryError(
                f"Caractère de remplacement UTF-8: {path.relative_to(root)}"
            )
        if FORBIDDEN_DELIVERY_TEXT.search(text):
            raise CompletePreliminaryDeliveryError(
                f"Thème exclu présent: {path.relative_to(root)}"
            )


def build_delivery(
    *,
    network_dir: Path,
    priority_boundary_dir: Path,
    preliminary_dir: Path,
    extension_runner_dir: Path,
    service_landscape_dir: Path,
    regime_plan_dir: Path,
    stock_audit_dir: Path,
    observed_dir: Path,
    action_protocol_dir: Path,
    legacy_action_dir: Path,
    dynamic_protocol_dir: Path,
    capacity_audit_dir: Path,
    frequency_dir: Path,
    historical_frequency_dir: Path,
    control_dir: Path,
    nominal_replay_dir: Path,
    map_file: Path,
    map_topojson_file: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source_roots = (
        network_dir,
        priority_boundary_dir,
        preliminary_dir,
        extension_runner_dir,
        service_landscape_dir,
        regime_plan_dir,
        stock_audit_dir,
        observed_dir,
        action_protocol_dir,
        legacy_action_dir,
        dynamic_protocol_dir,
        capacity_audit_dir,
        frequency_dir,
        historical_frequency_dir,
        control_dir,
        nominal_replay_dir,
        map_file,
        map_topojson_file,
    )
    output_dir = output_dir.resolve()
    try:
        v2.base._assert_external_output(
            output_dir, [Path(path) for path in source_roots]
        )
    except Exception as error:
        raise CompletePreliminaryDeliveryError(str(error)) from error
    if output_dir.exists():
        raise CompletePreliminaryDeliveryError(
            f"Destination déjà existante: {output_dir}"
        )

    network = _network_data(network_dir)
    boundary = _priority_boundary_data(priority_boundary_dir)
    extensions = _extension_and_lot_data(preliminary_dir, extension_runner_dir)
    landscape = _landscape_data(service_landscape_dir)
    try:
        regime_plan = v2.base._validate_regime_plan(regime_plan_dir)
    except Exception as error:
        raise CompletePreliminaryDeliveryError(
            f"Plan 93/80 invalide: {error}"
        ) from error
    regime_audit = _read_json(regime_plan_dir / "existing_results_audit.json")
    stock = _stock_calibration_data(stock_audit_dir)
    observed = _observed_data(observed_dir)
    actions = _action_data(action_protocol_dir, legacy_action_dir)
    technical = _technical_status(
        dynamic_protocol_dir,
        capacity_audit_dir,
        frequency_dir,
        historical_frequency_dir,
        control_dir,
    )
    nominal_payload = nominal_run_curves.build_nominal_run_curves_payload(
        nominal_replay_dir,
        expected_summary_path=(
            network_dir
            / "cases"
            / "baseline_nominal"
            / f"seed_{nominal_run_curves.EXPECTED_SEED}"
            / "summaries"
            / "first_simulation_summary.json"
        ),
    )
    map_document = _embed_plotly_world_topology(
        _clean_map(map_file),
        _load_world_topojson(map_topojson_file),
    )
    map_document = nominal_run_curves.inject_nominal_run_curves(
        map_document,
        nominal_payload,
    )

    source_files = {
        "network/manifest": network_dir / "campaign_manifest.json",
        "network/ranking": network_dir
        / "confirmation_supplier_sensitivity_ranking.csv",
        "network/summary": network_dir / "confirmation_summary.csv",
        "network/distribution": network_dir / "confirmation_metrics.csv",
        "network/decision": network_dir / "final_top3_decision.json",
        "network/state_evidence": network["state_evidence_path"],
        "boundary/manifest": priority_boundary_dir
        / "priority_boundary_audit_manifest.json",
        "boundary/scientific_audit": priority_boundary_dir
        / "scientific_priority_boundary_audit.json",
        "extension/manifest": preliminary_dir / "preliminary_15_of_30_manifest.json",
        "extension/effects": preliminary_dir / "preliminary_effects_15.csv",
        "extension/checkpoint": extension_runner_dir
        / "preliminary_checkpoint_15_manifest.json",
        "lots/summary": preliminary_dir / "preliminary_lot_illustrations.csv",
        "lots/detail": preliminary_dir
        / "preliminary_lot_genealogical_exposure_detail.csv",
        "landscape/manifest": service_landscape_dir / "campaign_manifest.json",
        "landscape/summary": service_landscape_dir / "scenario_summary.csv",
        "regime/plan": regime_plan_dir / "calibration_plan.json",
        "regime/legacy_audit": regime_plan_dir / "existing_results_audit.json",
        "stock/manifest": stock_audit_dir
        / "manifest_audit_calibration_stock_signal.json",
        "stock/summary": stock_audit_dir / "materiaux_calibration_synthese.csv",
        "observed/manifest": observed_dir / "manifest.json",
        "observed/ca_summary": observed_dir / "observed_ca_product_summary_2025.csv",
        "observed/ca_monthly": observed_dir / "observed_ca_monthly_2025.csv",
        "observed/stock_summary": observed_dir
        / "observed_stock_value_summary_2025.csv",
        "observed/stock_weekly": observed_dir
        / "observed_stock_value_snapshots_2025.csv",
        "observed/shortages": observed_dir
        / "projected_finished_goods_shortage_summary.csv",
        "actions/current_protocol": action_protocol_dir
        / "exploratory_action_protocol_manifest.json",
        "actions/legacy_summary": legacy_action_dir / "canonical_cascade_summary.json",
        "dynamic/protocol": dynamic_protocol_dir / "comparison_protocol.json",
        "dynamic/profile_audit": dynamic_protocol_dir / "profile_change_audit.json",
        "dynamic/capacity_audit": capacity_audit_dir / "capacity_coupling_audit.json",
        "frequency/manifest": frequency_dir / "canonical_frequency_manifest.json",
        "frequency/responses": frequency_dir / "canonical_frequency_response.csv",
        "frequency/historical_audit_manifest": historical_frequency_dir
        / "canonical_frequency_manifest.json",
        "control/manifest": control_dir / "canonical_control_system_manifest.json",
        "nominal/replay_summary": nominal_replay_dir
        / "summaries"
        / "first_simulation_summary.json",
        "nominal/input_stocks": nominal_replay_dir
        / "data"
        / "production_input_stocks_daily.csv",
        "nominal/input_arrivals": nominal_replay_dir
        / "data"
        / "production_input_replenishment_arrivals_daily.csv",
        "nominal/supplier_shipments": nominal_replay_dir
        / "data"
        / "production_supplier_shipments_daily.csv",
        "nominal/output_products": nominal_replay_dir
        / "data"
        / "production_output_products_daily.csv",
        "nominal/demand_service": nominal_replay_dir
        / "data"
        / "production_demand_service_daily.csv",
        "map/source": map_file,
        "map/world_topojson": map_topojson_file,
    }
    source_hashes = _source_hashes(source_files)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        map_target = staging / MAP_ASSET
        map_target.parent.mkdir(parents=True, exist_ok=True)
        map_target.write_text(map_document, encoding="utf-8")
        _write_csv(staging / RANKING_CSV, network["rankings"])
        _write_csv(staging / NETWORK_SUMMARY_CSV, network["summaries"])
        _write_csv(staging / NETWORK_DISTRIBUTION_CSV, network["distribution"])
        _write_csv(staging / EXTENSION_CSV, extensions["effects"])
        _write_csv(staging / LANDSCAPE_CSV, landscape)
        _write_csv(staging / LOT_SUMMARY_CSV, extensions["incidents"])
        _write_csv(staging / LOT_DETAIL_CSV, extensions["lot_details"])
        _write_csv(staging / STOCK_CALIBRATION_CSV, stock["rows"])
        _write_csv(staging / OBSERVED_CA_CSV, observed["ca_monthly"])
        _write_csv(staging / OBSERVED_STOCK_CSV, observed["stock_weekly"])
        _write_csv(staging / OBSERVED_SHORTAGE_CSV, observed["shortages"])
        _write_csv(staging / ACTION_CSV, actions["rows"])
        _write_csv(
            staging / NOMINAL_TRAJECTORY_CSV,
            nominal_run_curves.compact_trajectory_rows(nominal_payload),
        )
        decision_matrix = [
            {
                "statut": "calcule",
                "element": "vulnerabilite_reseau_30_simulations",
                "portee": "16_fournisseurs_18_voies",
                "limite": "conditionnel_pas_probabilite_historique",
            },
            {
                "statut": "calcule_preliminaire",
                "element": "dependance_temporelle",
                "portee": "4_voies_4_fenetres_15_simulations_sur_30",
                "limite": "15_simulations_restantes_non_executees",
            },
            {
                "statut": "observe",
                "element": "ca_stocks_et_projections_2025",
                "portee": "agregats_disponibles",
                "limite": "pas_attribution_fournisseur_ni_quantite_stock",
            },
            {
                "statut": "genealogie_technique",
                "element": "suivi_lots",
                "portee": "4_illustrations_2231_enregistrements",
                "limite": "pas_attribution_causale_par_lot_physique",
            },
            {
                "statut": "prepare_non_execute",
                "element": "references_service_93_80",
                "portee": "36_configurations_prevues",
                "limite": "aucune_configuration_actuelle_executee",
            },
            {
                "statut": "prepare_non_execute",
                "element": "leviers_operationnels_actuels",
                "portee": "protocole",
                "limite": "ancien_essai_distinct_non_transferable",
            },
            {
                "statut": "partiel_prepare_non_execute",
                "element": "besoins_dynamiques",
                "portee": "reseau_actuel_3_sur_24_variante_preparee_24_sur_24",
                "limite": "variante_complete_non_executee",
            },
            {
                "statut": "desactive_dans_campagne",
                "element": "risque_fournisseur_dependant_etat",
                "portee": "incidents_exogenes_imposes",
                "limite": "aucune_probabilite_endogene",
            },
            {
                "statut": "non_realise",
                "element": "sensibilite_globale_monte_carlo_multifactoriel",
                "portee": "aucune_campagne_globale_valide",
                "limite": "30_tirages_delai_demande_et_severite_fixes",
            },
            {
                "statut": "donnees_manquantes",
                "element": "prevision_fournisseur_fp_fn",
                "portee": "cas_industriel",
                "limite": "historique_promis_recu_incident_absent",
            },
            {
                "statut": "non_calibre_sur_cas",
                "element": "conversion_prevision_perturbation_physique",
                "portee": "delai_capacite_quantite_utilisable",
                "limite": "hypotheses_non_relies_intervalles_mesures",
            },
            {
                "statut": "non_calibre_metier",
                "element": "regimes_dynamiques_supply",
                "portee": "poc_classification_existant",
                "limite": "seuils_transitions_non_valides_sur_jours_annotes",
            },
            {
                "statut": "non_valide",
                "element": "boucle_fermee_poles_frequentiel_physique",
                "portee": "dernier_pilote_0_sur_304_reponses_fiables",
                "limite": "pole_0p82_memoire_regulateur_uniquement",
            },
            {
                "statut": "partiel_deux_chaines",
                "element": "courbes_journalieres_tous_noeuds",
                "portee": "nominal_338929_268091_et_344135_268967_720_jours",
                "limite": "une_realisation_pas_tous_noeuds_ni_scenarios_perturbes",
            },
            {
                "statut": "partiel_nominal_integre",
                "element": "carte_enrichie_et_suivi_lots_dans_carte",
                "portee": "carte_topologique_existante",
                "limite": "pas_coloration_risque_actuelle_ni_attribution_causale_lots",
            },
            {
                "statut": "attente_metier",
                "element": "couts_reels_et_validation_risque_cree",
                "portee": "achats_et_planification",
                "limite": "aucun_gain_financier_promissible",
            },
            {
                "statut": "donnees_manquantes",
                "element": "historique_promis_recu_couts_stocks_libres_par_lot",
                "portee": "donnees_industrielles",
                "limite": "probabilite_et_gain_financier_non_estimables",
            },
        ]
        _write_csv(staging / DECISION_MATRIX_CSV, decision_matrix)
        page = _render_html(
            network=network,
            boundary=boundary,
            extensions=extensions,
            landscape=landscape,
            regime_plan=regime_plan,
            regime_audit=regime_audit,
            stock=stock,
            observed=observed,
            actions=actions,
            technical=technical,
            nominal_payload=nominal_payload,
        )
        (staging / ENTRYPOINT).write_text(page, encoding="utf-8")
        map_audit = v2.base.final_package._validate_html(
            map_target,
            validate_navigation=False,
        )
        entry_audit = v2.base.final_package._validate_html(
            staging / ENTRYPOINT,
            validate_navigation=False,
        )
        artifact_hashes = {
            name: _sha256(staging / name)
            for name in sorted(v2.base._relative_files(staging))
        }
        signature_payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete_preliminary_not_final",
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "source_file_sha256": source_hashes,
            "artifact_file_sha256": artifact_hashes,
            "entrypoint": ENTRYPOINT,
            "view_count": 3,
            "network_campaign_run_count": 1255,
            "network_supplier_count": 16,
            "network_lane_count": 18,
            "network_confirmation_seed_count": 30,
            "extension_completed_seed_count": 15,
            "extension_final_seed_count": 30,
            "extension_new_run_count": 510,
            "extension_reused_result_count": 124,
            "extension_in_scope_cell_count": 34,
            "lot_detail_record_count": 2231,
            "lot_case_key_present": True,
            "two_campaign_unique_run_count": 1765,
            "in_scope_unique_run_count": 1513,
            "excluded_out_of_scope_unique_run_count": 252,
            "map_external_resource_count": int(map_audit["external_resource_count"]),
            "map_world_topology_embedded": True,
            "map_world_topology_key": WORLD_TOPOJSON_KEY,
            "map_world_topology_sha256": WORLD_TOPOJSON_SHA256,
            "map_plotly_geo_remote_fetch_prevented": True,
            "entry_external_resource_count": int(
                entry_audit["external_resource_count"]
            ),
            "preliminary_not_final": True,
            "supplier_priority_order_validated": False,
            "strongest_descriptive_decrease_case_count": 2,
            "nonseparation_group_count": len(boundary["group"]),
            "priority_boundary_audit_included": True,
            "network_supplier_state_dependent_risk_enabled": False,
            "network_dynamic_requirement_pair_count": 3,
            "prepared_dynamic_requirement_pair_count": 24,
            "historical_probability_estimated": False,
            "current_action_results_available": False,
            "current_industrial_cost_claimed": False,
            "physical_supply_poles_identified": False,
            "latest_closed_loop_frequency_response_count": 304,
            "latest_closed_loop_frequency_valid_count": 0,
            "historical_frequency_response_count": 1104,
            "historical_frequency_numerically_valid_count": 22,
            "nominal_run_curves_available": True,
            "nominal_run_curves_chain_count": int(nominal_payload["chain_count"]),
            "nominal_run_curves_horizon_days": int(nominal_payload["horizon_days"]),
            "nominal_run_curves_single_realization": True,
            "nominal_run_supplier_incident_enabled": False,
            "nominal_run_supplier_state_dependent_risk_enabled": False,
            "existing_map_tabs_preserved": True,
            "engine_executed_by_builder": False,
        }
        manifest = {
            **signature_payload,
            "package_signature": v2.base._canonical_sha256(signature_payload),
            "source_artifacts_mutated": False,
            "previous_artifacts_mutated": False,
            "cryptographic_authentication_present": False,
        }
        v2.base._write_json(staging / MANIFEST_FILE, manifest)
        _assert_output_text(staging)
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    validate_delivery(output_dir)
    return manifest


def validate_delivery(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / MANIFEST_FILE)
    artifacts = manifest.get("artifact_file_sha256")
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise CompletePreliminaryDeliveryError("Empreintes du livrable absentes.")
    if v2.base._relative_files(root) != set(artifacts) | {MANIFEST_FILE}:
        raise CompletePreliminaryDeliveryError("Inventaire du livrable V3 non exact.")
    required = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_preliminary_not_final",
        "entrypoint": ENTRYPOINT,
        "view_count": 3,
        "network_campaign_run_count": 1255,
        "network_supplier_count": 16,
        "network_lane_count": 18,
        "network_confirmation_seed_count": 30,
        "extension_completed_seed_count": 15,
        "extension_final_seed_count": 30,
        "extension_new_run_count": 510,
        "extension_reused_result_count": 124,
        "extension_in_scope_cell_count": 34,
        "lot_detail_record_count": 2231,
        "lot_case_key_present": True,
        "two_campaign_unique_run_count": 1765,
        "in_scope_unique_run_count": 1513,
        "excluded_out_of_scope_unique_run_count": 252,
        "map_external_resource_count": 0,
        "map_world_topology_embedded": True,
        "map_world_topology_key": WORLD_TOPOJSON_KEY,
        "map_world_topology_sha256": WORLD_TOPOJSON_SHA256,
        "map_plotly_geo_remote_fetch_prevented": True,
        "entry_external_resource_count": 0,
        "preliminary_not_final": True,
        "supplier_priority_order_validated": False,
        "strongest_descriptive_decrease_case_count": 2,
        "nonseparation_group_count": 4,
        "priority_boundary_audit_included": True,
        "network_supplier_state_dependent_risk_enabled": False,
        "network_dynamic_requirement_pair_count": 3,
        "prepared_dynamic_requirement_pair_count": 24,
        "historical_probability_estimated": False,
        "current_action_results_available": False,
        "current_industrial_cost_claimed": False,
        "physical_supply_poles_identified": False,
        "latest_closed_loop_frequency_response_count": 304,
        "latest_closed_loop_frequency_valid_count": 0,
        "historical_frequency_response_count": 1104,
        "historical_frequency_numerically_valid_count": 22,
        "nominal_run_curves_available": True,
        "nominal_run_curves_chain_count": 2,
        "nominal_run_curves_horizon_days": 720,
        "nominal_run_curves_single_realization": True,
        "nominal_run_supplier_incident_enabled": False,
        "nominal_run_supplier_state_dependent_risk_enabled": False,
        "existing_map_tabs_preserved": True,
        "engine_executed_by_builder": False,
        "source_artifacts_mutated": False,
        "previous_artifacts_mutated": False,
        "cryptographic_authentication_present": False,
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise CompletePreliminaryDeliveryError("Manifeste V3 incohérent.")
    if manifest.get("builder_sha256") != _sha256(Path(__file__).resolve()):
        raise CompletePreliminaryDeliveryError(
            "Le builder ne correspond plus au manifeste."
        )
    signature_keys = [
        key
        for key in manifest
        if key
        not in {
            "package_signature",
            "source_artifacts_mutated",
            "previous_artifacts_mutated",
            "cryptographic_authentication_present",
        }
    ]
    signature_payload = {key: manifest[key] for key in signature_keys}
    if manifest.get("package_signature") != v2.base._canonical_sha256(
        signature_payload
    ):
        raise CompletePreliminaryDeliveryError("Signature interne V3 invalide.")
    for name, expected in artifacts.items():
        path = root / str(name)
        if not path.is_file() or _sha256(path) != expected:
            raise CompletePreliminaryDeliveryError(f"Artefact altéré: {name}")
    page = (root / ENTRYPOINT).read_text(encoding="utf-8")
    if page.count('class="view') != 3 or page.count("data-view=") != 3:
        raise CompletePreliminaryDeliveryError(
            "Le parcours ne contient pas trois vues."
        )
    entry_audit = v2.base.final_package._validate_html(
        root / ENTRYPOINT,
        validate_navigation=False,
    )
    map_audit = v2.base.final_package._validate_html(
        root / MAP_ASSET,
        validate_navigation=False,
    )
    map_document = (root / MAP_ASSET).read_text(encoding="utf-8")
    _assert_plotly_geo_offline(map_document)
    if (
        map_document.count(nominal_run_curves.INJECTION_MARKER) != 4
        or nominal_run_curves.BUTTON_ID not in map_document
        or nominal_run_curves.MODAL_ID not in map_document
    ):
        raise CompletePreliminaryDeliveryError(
            "Courbes du run nominal absentes de la carte."
        )
    if entry_audit["external_resource_count"] or map_audit["external_resource_count"]:
        raise CompletePreliminaryDeliveryError(
            "Le livrable requiert une ressource distante."
        )
    expected_counts = {
        RANKING_CSV: 16,
        NETWORK_SUMMARY_CSV: 36,
        NETWORK_DISTRIBUTION_CSV: 1080,
        EXTENSION_CSV: 34,
        LANDSCAPE_CSV: 106,
        LOT_SUMMARY_CSV: 4,
        LOT_DETAIL_CSV: 2231,
        STOCK_CALIBRATION_CSV: 24,
        OBSERVED_CA_CSV: 24,
        OBSERVED_STOCK_CSV: 208,
        OBSERVED_SHORTAGE_CSV: 4,
        ACTION_CSV: 7,
        NOMINAL_TRAJECTORY_CSV: 1440,
        DECISION_MATRIX_CSV: 17,
    }
    for name, expected in expected_counts.items():
        if len(_read_csv(root / name)) != expected:
            raise CompletePreliminaryDeliveryError(
                f"Nombre de lignes inattendu: {name}"
            )
    if any(not row.get("case_key") for row in _read_csv(root / LOT_DETAIL_CSV)):
        raise CompletePreliminaryDeliveryError(
            "La clé de scénario manque dans le détail des lots."
        )
    _assert_output_text(root)
    return manifest


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-dir", type=Path, default=DEFAULT_NETWORK_DIR)
    parser.add_argument(
        "--priority-boundary-dir", type=Path, default=DEFAULT_PRIORITY_BOUNDARY_DIR
    )
    parser.add_argument("--preliminary-dir", type=Path, default=DEFAULT_PRELIMINARY_DIR)
    parser.add_argument(
        "--extension-runner-dir", type=Path, default=DEFAULT_EXTENSION_RUNNER_DIR
    )
    parser.add_argument(
        "--service-landscape-dir", type=Path, default=DEFAULT_SERVICE_LANDSCAPE_DIR
    )
    parser.add_argument("--regime-plan-dir", type=Path, default=DEFAULT_REGIME_PLAN_DIR)
    parser.add_argument("--stock-audit-dir", type=Path, default=DEFAULT_STOCK_AUDIT_DIR)
    parser.add_argument("--observed-dir", type=Path, default=DEFAULT_OBSERVED_DIR)
    parser.add_argument(
        "--action-protocol-dir", type=Path, default=DEFAULT_ACTION_PROTOCOL_DIR
    )
    parser.add_argument(
        "--legacy-action-dir", type=Path, default=DEFAULT_LEGACY_ACTION_DIR
    )
    parser.add_argument(
        "--dynamic-protocol-dir", type=Path, default=DEFAULT_DYNAMIC_PROTOCOL_DIR
    )
    parser.add_argument(
        "--capacity-audit-dir", type=Path, default=DEFAULT_CAPACITY_AUDIT_DIR
    )
    parser.add_argument("--frequency-dir", type=Path, default=DEFAULT_FREQUENCY_DIR)
    parser.add_argument(
        "--historical-frequency-dir",
        type=Path,
        default=DEFAULT_HISTORICAL_FREQUENCY_DIR,
    )
    parser.add_argument("--control-dir", type=Path, default=DEFAULT_CONTROL_DIR)
    parser.add_argument(
        "--nominal-replay-dir",
        type=Path,
        default=DEFAULT_NOMINAL_REPLAY_DIR,
    )
    parser.add_argument("--map-file", type=Path, default=DEFAULT_MAP_FILE)
    parser.add_argument(
        "--map-topojson-file",
        type=Path,
        default=DEFAULT_WORLD_TOPOJSON_FILE,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_only:
        manifest = validate_delivery(args.output_dir)
    else:
        manifest = build_delivery(
            network_dir=args.network_dir,
            priority_boundary_dir=args.priority_boundary_dir,
            preliminary_dir=args.preliminary_dir,
            extension_runner_dir=args.extension_runner_dir,
            service_landscape_dir=args.service_landscape_dir,
            regime_plan_dir=args.regime_plan_dir,
            stock_audit_dir=args.stock_audit_dir,
            observed_dir=args.observed_dir,
            action_protocol_dir=args.action_protocol_dir,
            legacy_action_dir=args.legacy_action_dir,
            dynamic_protocol_dir=args.dynamic_protocol_dir,
            capacity_audit_dir=args.capacity_audit_dir,
            frequency_dir=args.frequency_dir,
            historical_frequency_dir=args.historical_frequency_dir,
            control_dir=args.control_dir,
            nominal_replay_dir=args.nominal_replay_dir,
            map_file=args.map_file,
            map_topojson_file=args.map_topojson_file,
            output_dir=args.output_dir,
        )
    print(
        json.dumps(
            {
                "status": "valid",
                "entrypoint": str((args.output_dir / ENTRYPOINT).resolve()),
                "package_signature": manifest["package_signature"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
