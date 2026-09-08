#!/usr/bin/env python3
"""Create a copyable, offline ZIP from an existing industrial demo package.

The source package is never modified.  The generated manifest only uses
relative paths, while the copied scientific manifest is refreshed for the
portable files.  HTML links are checked after the copy so the package can be moved
to another Windows machine and opened directly with ``file://``.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import html
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = "etudecas.portable_industrial_demo.v1"
LAUNCHER_NAME = "OUVRIR_LA_DEMONSTRATION.html"
README_NAME = "LISEZ_MOI.txt"
MANIFEST_NAME = "portable_manifest.json"
REFERENCE_RE = re.compile(r"(?:href|src)\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
PLOTLY_CDN_URL = "https://cdn.plot.ly/plotly-2.32.0.min.js"
INTERNAL_PATH_ALIASES = (
    (
        r"C:\dev\lca-simu-pr40-validation-artifacts-20260726",
        "provenance/artifacts",
    ),
    (r"C:\dev\lca-simu-pr40", "provenance/repository"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--mrp-v3-dashboard", type=Path)
    parser.add_argument("--network-comparison", type=Path)
    parser.add_argument("--resilience-map", type=Path)
    parser.add_argument("--control-analysis-dir", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_files(root: Path, *, include_manifest: bool = True) -> list[Path]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if include_manifest:
        return files
    return [path for path in files if path.name != MANIFEST_NAME]


def local_html_reference_issues(root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    root_resolved = root.resolve()
    for page in sorted(root.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        for raw_reference in REFERENCE_RE.findall(text):
            reference = html.unescape(raw_reference.strip())
            if not reference or reference.startswith("#"):
                continue
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme.lower() in {
                    "data",
                    "blob",
                    "javascript",
                    "mailto",
                    "http",
                    "https",
                }:
                    continue
                issues.append(
                    {
                        "page": page.relative_to(root).as_posix(),
                        "reference": reference,
                        "reason": "unsupported_scheme",
                    }
                )
                continue
            relative_target = unquote(parsed.path)
            if not relative_target:
                continue
            target = (page.parent / relative_target).resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError:
                issues.append(
                    {
                        "page": page.relative_to(root).as_posix(),
                        "reference": reference,
                        "reason": "outside_package",
                    }
                )
                continue
            if not target.exists():
                issues.append(
                    {
                        "page": page.relative_to(root).as_posix(),
                        "reference": reference,
                        "reason": "missing_local_target",
                    }
                )
    return issues


def _add_return_link(document: str, href: str = "../index.html#complements") -> str:
    if "</body>" not in document:
        raise ValueError("HTML page has no closing body tag")
    snippet = f"""
    <style>
      .portableReturn {{ position:fixed; right:18px; bottom:18px; z-index:99999;
        padding:10px 15px; border-radius:999px; color:#fff; background:#123e70;
        font:700 13px Segoe UI,Arial,sans-serif; text-decoration:none;
        box-shadow:0 8px 24px rgba(15,23,42,.25); }}
    </style>
    <a class="portableReturn" href="{html.escape(href, quote=True)}">Retour à la synthèse</a>
    """
    return document.replace("</body>", snippet + "</body>", 1)


def _localize_plotly_map(document: str, topojson: Path) -> str:
    document = document.replace(PLOTLY_CDN_URL, "plotly-2.32.0.min.js")
    local_script = '<script src="plotly-2.32.0.min.js"></script>'
    if local_script not in document:
        raise ValueError("Local Plotly script tag not found after localization")
    if "Plotly.setPlotConfig({topojsonURL:" not in document:
        encoded_topology = base64.b64encode(topojson.read_bytes()).decode("ascii")
        offline_config = (
            "<script>Plotly.setPlotConfig({topojsonURL:'./'});"
            "if(location.protocol==='file:'){Plotly.setPlotConfig({topojsonURL:"
            f"'data:application/json;base64,{encoded_topology}#'"
            "});}</script>"
        )
        document = document.replace(local_script, local_script + offline_config, 1)
    return document


def _copy_html_view(source: Path, destination: Path, *, map_page: bool = False) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Extra HTML view not found: {source}")
    document = source.read_text(encoding="utf-8")
    if map_page:
        document = _localize_plotly_map(document, destination.parent / "world_110m.json")
        document = _polish_resilience_map(document)
    document = _add_return_link(document)
    destination.write_text(document, encoding="utf-8")


def _polish_resilience_map(document: str) -> str:
    """Clarify the portable RESILIENCE-SCAN entry point and its legacy replay note."""

    generic_title = "<title>Supply Graph POC - Geocoded Map</title>"
    if generic_title not in document:
        raise ValueError("Expected generic RESILIENCE-SCAN title not found")
    document = document.replace(
        generic_title,
        "<title>RESILIENCE-SCAN V3 — carte et analyses fréquentielles</title>",
        1,
    )
    legacy_note = (
        "Adaptive canonical replay uses a precomputed daily open-loop schedule; "
        "canonical state feedback is not yet implemented."
    )
    clarified_note = (
        "Historical adaptive replay used a precomputed daily open-loop schedule. "
        "This limitation applies to that replay only; the separate V3 closed-loop "
        "controller shown in this package is implemented and evaluated under its stated limits."
    )
    marker = "const DATA_CHUNKED_GZIP_BASE64 = "
    payload_start = document.find(marker)
    if payload_start < 0:
        raise ValueError("RESILIENCE-SCAN compressed payload not found")
    json_start = payload_start + len(marker)
    json_end = document.find(";\n", json_start)
    if json_end < 0:
        raise ValueError("RESILIENCE-SCAN compressed payload terminator not found")
    payload = json.loads(document[json_start:json_end])
    replacement_count = 0
    for key, chunks in payload.items():
        if not isinstance(chunks, list) or not chunks:
            continue
        try:
            decoded = gzip.decompress(base64.b64decode("".join(chunks))).decode("utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        occurrences = decoded.count(legacy_note)
        if not occurrences:
            continue
        replacement_count += occurrences
        decoded = decoded.replace(legacy_note, clarified_note)
        encoded = base64.b64encode(
            gzip.compress(decoded.encode("utf-8"), compresslevel=9, mtime=0)
        ).decode("ascii")
        payload[key] = [encoded[index : index + 65536] for index in range(0, len(encoded), 65536)]
    if replacement_count != 1:
        raise ValueError(
            f"Expected one legacy RESILIENCE-SCAN replay note, found {replacement_count}"
        )
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return document[:json_start] + serialized + document[json_end:]


def _patch_incident_map_labels(root: Path) -> None:
    for name in (
        "carte_qualite_incident_lots.html",
        "carte_retard_338929_incident_lots.html",
    ):
        path = root / "views" / name
        document = path.read_text(encoding="utf-8")
        nominal = '>Run nominal</button>'
        comparison = 'id="scenarioComparisonBtn" class="tableBtn"'
        if nominal not in document or comparison not in document:
            raise ValueError(f"Expected incident-map controls not found in {path}")
        document = document.replace("Run nominal", "Incident sans action")
        document = document.replace("run nominal", "scénario incident sans action")
        document = document.replace(
            comparison,
            'id="scenarioComparisonBtn" class="tableBtn" style="display:none" aria-hidden="true"',
            1,
        )
        path.write_text(document, encoding="utf-8")


def _control_analysis_html(analysis_dir_name: str) -> str:
    images = (
        ("Point de fonctionnement", "canonical_control_system_operating_point.png"),
        ("Carte des pôles", "canonical_control_system_pole_map.png"),
        ("Bode du régulateur", "canonical_control_system_bode.png"),
        ("Nyquist et zone morte", "canonical_control_system_nyquist_deadzone.png"),
        ("Contrôlabilité et observabilité", "canonical_control_system_controllability_observability.png"),
        ("Rang de l'espace des actionneurs", "canonical_control_system_actuator_space_rank.png"),
        ("Réponse des états physiques", "canonical_control_system_physical_state_response.png"),
        ("Composition des essais", "canonical_control_system_probe_composition.png"),
    )
    cards = "".join(
        f'<figure><img src="../annexes/{analysis_dir_name}/{filename}" alt="{html.escape(title)}">'
        f"<figcaption>{html.escape(title)}</figcaption></figure>"
        for title, filename in images
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Annexe — dynamique, pôles et contrôlabilité</title><style>
body{{margin:0;background:#eef3f8;color:#102a45;font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.55}}
main{{max-width:1250px;margin:auto;padding:28px}}.hero,.panel{{background:#fff;border:1px solid #d8e2ec;border-radius:18px;padding:24px;margin-bottom:18px}}
.hero{{background:linear-gradient(135deg,#081f3b,#0f766e);color:#fff}}h1{{margin:0 0 10px}}h2{{margin-top:0}}
.warning{{border-left:5px solid #f59e0b;background:#fffbeb;padding:14px;border-radius:9px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}}figure{{margin:0;background:#fff;border:1px solid #d8e2ec;border-radius:14px;padding:12px}}
img{{width:100%;height:auto;display:block}}figcaption{{font-weight:700;margin-top:8px}}a{{color:#075985}}ul{{padding-left:20px}}
</style></head><body><main>
<section class="hero"><h1>Dynamique, pôles et contrôlabilité</h1><p>Annexe technique de RESILIENCE-SCAN V3 — résultats locaux et limites scientifiques.</p></section>
<section class="panel"><h2>Conclusion à retenir</h2><ul>
<li>Le seul pôle établi exactement est <strong>z = 0,82</strong> : il décrit la mémoire interne du régulateur, pas la supply chain physique.</li>
<li>Le petit modèle physique DMDc exploratoire est <strong>rejeté</strong>. Ses pôles candidats ne doivent pas être présentés comme des pôles industriels.</li>
<li>La mémoire interne du régulateur est contrôlable et observable. Cela ne démontre pas encore la contrôlabilité de toute la supply chain.</li>
<li>À l'amplitude testée, la cible de production est restée dans une zone morte physique ou calendaire.</li>
</ul><div class="warning"><strong>Lecture correcte :</strong> ces graphiques documentent le diagnostic et les limites. Aucune marge de stabilité de la boucle supply chain complète n'est revendiquée.</div>
<p><a href="../annexes/{analysis_dir_name}/canonical_control_system_report.md">Rapport technique complet</a> · <a href="../annexes/{analysis_dir_name}/canonical_control_system_poles.csv">Pôles</a> · <a href="../annexes/{analysis_dir_name}/canonical_control_system_controllability.csv">Contrôlabilité</a> · <a href="../annexes/{analysis_dir_name}/canonical_control_system_validation.csv">Validation</a></p></section>
<section class="grid">{cards}</section>
</main></body></html>"""


def _append_complement_section(index_path: Path, *, include_control: bool) -> None:
    document = index_path.read_text(encoding="utf-8")
    if "</main>" not in document:
        raise ValueError("Industrial index has no closing main tag")
    control_card = ""
    if include_control:
        control_card = """<article class="launch-card"><span class="badge hypothesis">Annexe technique</span><h3>Dynamique, pôles et contrôlabilité</h3><p>Voir les résultats établis, le modèle physique rejeté et les limites à présenter sans surinterprétation.</p><a class="launch-button secondary" href="views/annexe_dynamique_frequentielle.html" target="_blank" rel="noopener">Ouvrir l'annexe technique</a></article>"""
    section = f"""
    <section id="complements"><div class="panel"><h2>Modèle dynamique et dossiers de preuve</h2>
      <p class="lead">Compléments autonomes du travail : comparaison avec l'ancienne simulation, RESILIENCE-SCAN V3 et fichiers de preuve légers.</p>
      <div class="launch-grid">
        <article class="launch-card"><span class="badge simulated">Comparaison complète</span><h3>MRP historique versus modèle V3</h3><p>Comparer service, stocks, production, reports, coûts et réaction aux perturbations.</p><a class="launch-button primary" href="views/comparaison_mrp_v3.html" target="_blank" rel="noopener">Ouvrir les résultats MRP / V3</a></article>
        <article class="launch-card"><span class="badge simulated">Tous les nœuds</span><h3>Comparaison du réseau</h3><p>Explorer les écarts MRP / V3 aux différents nœuds et pour les principaux indicateurs.</p><a class="launch-button secondary" href="views/comparaison_reseau_mrp_v3.html" target="_blank" rel="noopener">Ouvrir la comparaison réseau</a></article>
        <article class="launch-card"><span class="badge proxy">RESILIENCE-SCAN V3</span><h3>Régulation et analyses fréquentielles</h3><p>Carte technique avec les courbes, validations et limites du modèle en boucle fermée.</p><a class="launch-button secondary" href="views/resilience_scan_v3.html#resilience-scan" target="_blank" rel="noopener">Ouvrir RESILIENCE-SCAN</a></article>
        {control_card}
      </div>
      <h3>Télécharger les données légères et hypothèses</h3>
      <p><a href="observed_2025.csv">Données observées 2025</a> · <a href="calibration_hypotheses.csv">Hypothèses de calibration</a> · <a href="paired_replays_v2.csv">Simulations appariées</a> · <a href="lever_sensitivity_ranking.csv">Sensibilité des leviers</a> · <a href="product_lever_response_curves.csv">Courbes de réponse</a> · <a href="supplier_priority_two_axes.csv">Priorités fournisseurs</a> · <a href="evidence_register.csv">Registre des preuves</a> · <a href="supplier_risk_decision_brief.md">Rapport Markdown</a> · <a href="supplier_risk_decision_brief.json">Rapport JSON</a> · <a href="views/incidents_risques_lots.json">Incidents et lots JSON</a> · <a href="manifest.json">Manifeste scientifique</a> · <a href="portable_manifest.json">Manifeste portable</a></p>
    </div></section>
    """
    index_path.write_text(document.replace("</main>", section + "</main>", 1), encoding="utf-8")


def sanitize_internal_paths(root: Path) -> int:
    replacement_count = 0
    suffixes = {".csv", ".html", ".json", ".md", ".txt"}
    for path in package_files(root):
        if path.suffix.lower() not in suffixes or path.name == "plotly-2.32.0.min.js":
            continue
        try:
            document = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        original = document
        for internal_prefix, alias in INTERNAL_PATH_ALIASES:
            variants = (
                internal_prefix,
                internal_prefix.replace("\\", "\\\\"),
                internal_prefix.replace("\\", "/"),
            )
            for variant in variants:
                replacement_count += document.lower().count(variant.lower())
                document = re.sub(re.escape(variant), alias, document, flags=re.IGNORECASE)
        if document != original:
            path.write_text(document, encoding="utf-8")
    return replacement_count


def refresh_scientific_manifest(root: Path) -> None:
    """Turn the copied build manifest into a valid ledger for the portable files."""

    path = root / "manifest.json"
    if not path.is_file():
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    rows = manifest.get("files")
    refreshed_rows: list[dict[str, object]] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            original = str(row.get("path") or "").replace("\\", "/")
            marker = "supplier_risk_lot_explorer_20260831_v6/"
            relative = original.split(marker, 1)[1] if marker in original else ""
            candidate = root / Path(relative) if relative else None
            if candidate is None or not candidate.is_file():
                matches = list(root.rglob(Path(original).name))
                candidate = matches[0] if len(matches) == 1 else None
            if candidate is None or not candidate.is_file():
                continue
            refreshed = dict(row)
            refreshed["path"] = candidate.relative_to(root).as_posix()
            refreshed["bytes"] = candidate.stat().st_size
            refreshed["sha256"] = sha256(candidate)
            refreshed_rows.append(refreshed)
        manifest["files"] = refreshed_rows
        manifest["total_generated_bytes_excluding_manifest"] = sum(
            int(row["bytes"]) for row in refreshed_rows
        )
    manifest["output_dir"] = "."
    manifest["standalone_html"] = "index.html"
    manifest["portable_copy"] = True
    manifest["portable_file_ledger_refreshed"] = True
    manifest["external_input_paths_are_provenance_only"] = True
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def repair_utf8_mojibake(path: Path) -> bool:
    document = path.read_text(encoding="utf-8")
    if "Ã" not in document and "â" not in document:
        return False
    try:
        repaired = document.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False
    path.write_text(repaired, encoding="utf-8")
    return True


def readme_text() -> str:
    return """DEMONSTRATION SUPPLY CHAIN - VERSION AUTONOME

1. Extraire completement le fichier ZIP dans un dossier local.
2. Double-cliquer sur OUVRIR_LA_DEMONSTRATION.html.
3. Utiliser de preference Microsoft Edge, Google Chrome ou Firefox recent.

Le paquet fonctionne hors ligne : aucun serveur, compte ou acces Internet
n'est necessaire. Ne pas ouvrir le fichier HTML directement depuis l'aperçu
interne du ZIP ; il faut d'abord extraire tout le dossier afin de conserver le
sous-dossier views a cote du lanceur.

Contenu :
- synthese industrielle et donnees 2025 ;
- carte de la quarantaine qualite et suivi des lots ;
- carte du retard du composant 338929 et suivi des lots ;
- comparaison fonctionnement normal / incident / solution (estimation) ;
- courbes des stress tests ;
- carte historique complete et ses onglets existants ;
- comparaison complete MRP historique / modele dynamique V3 ;
- RESILIENCE-SCAN V3 et annexe technique poles/controllabilite ;
- resultats structures CSV, JSON et Markdown.

Les references de provenance ont ete rendues relatives. Aucune page ne charge
de ressource externe pendant la demonstration.
"""


def build_portable_package(
    source_dir: Path,
    output_dir: Path,
    archive: Path,
    *,
    mrp_v3_dashboard: Path | None = None,
    network_comparison: Path | None = None,
    resilience_map: Path | None = None,
    control_analysis_dir: Path | None = None,
) -> dict[str, object]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    archive = archive.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source package not found: {source_dir}")
    if not (source_dir / "index.html").is_file():
        raise FileNotFoundError(f"Missing source launcher: {source_dir / 'index.html'}")
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    if archive.exists():
        raise FileExistsError(f"Archive already exists: {archive}")
    if output_dir == source_dir or source_dir in output_dir.parents:
        raise ValueError("Output directory must not be the source or one of its children")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, output_dir)
    views_dir = output_dir / "views"
    required_extras = {
        "mrp_v3_dashboard": mrp_v3_dashboard,
        "network_comparison": network_comparison,
        "resilience_map": resilience_map,
    }
    if any(path is not None for path in required_extras.values()) and not all(
        path is not None for path in required_extras.values()
    ):
        raise ValueError("MRP/V3 dashboard, network comparison and resilience map must be supplied together")
    if mrp_v3_dashboard is not None:
        assert network_comparison is not None and resilience_map is not None
        _copy_html_view(mrp_v3_dashboard, views_dir / "comparaison_mrp_v3.html")
        _copy_html_view(network_comparison, views_dir / "comparaison_reseau_mrp_v3.html")
        _copy_html_view(resilience_map, views_dir / "resilience_scan_v3.html", map_page=True)
    if control_analysis_dir is not None:
        if not control_analysis_dir.is_dir():
            raise FileNotFoundError(f"Control analysis directory not found: {control_analysis_dir}")
        analysis_dir_name = "analyse_dynamique_frequentielle"
        analysis_output = output_dir / "annexes" / analysis_dir_name
        shutil.copytree(control_analysis_dir, analysis_output)
        repair_utf8_mojibake(analysis_output / "canonical_control_system_report.md")
        (views_dir / "annexe_dynamique_frequentielle.html").write_text(
            _add_return_link(_control_analysis_html(analysis_dir_name)),
            encoding="utf-8",
        )
    if mrp_v3_dashboard is not None:
        _append_complement_section(
            output_dir / "index.html",
            include_control=control_analysis_dir is not None,
        )
    _patch_incident_map_labels(output_dir)
    sanitized_internal_path_count = sanitize_internal_paths(output_dir)
    refresh_scientific_manifest(output_dir)
    shutil.copyfile(output_dir / "index.html", output_dir / LAUNCHER_NAME)
    (output_dir / README_NAME).write_text(readme_text(), encoding="utf-8")
    # The launcher links to this file.  Create it before validating local
    # references, then replace the placeholder with the complete ledger below.
    (output_dir / MANIFEST_NAME).write_text("{}\n", encoding="utf-8")

    reference_issues = local_html_reference_issues(output_dir)
    if reference_issues:
        raise RuntimeError(
            "Portable package contains invalid local HTML references: "
            + json.dumps(reference_issues, ensure_ascii=False)
        )

    rows = []
    for path in package_files(output_dir, include_manifest=False):
        rows.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "launcher": LAUNCHER_NAME,
        "offline": True,
        "portable": True,
        "requires_local_server": False,
        "requires_internet": False,
        "runtime_reference_issue_count": 0,
        "sanitized_internal_path_count": sanitized_internal_path_count,
        "scientific_manifest": "manifest.json",
        "scientific_manifest_external_paths_are_provenance_only": True,
        "files": rows,
        "total_bytes_excluding_portable_manifest": sum(int(row["bytes"]) for row in rows),
    }
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    root_name = output_dir.name
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in package_files(output_dir):
            bundle.write(path, (Path(root_name) / path.relative_to(output_dir)).as_posix())
    archive_hash = sha256(archive)
    archive.with_suffix(archive.suffix + ".sha256.txt").write_text(
        f"{archive_hash}  {archive.name}\n",
        encoding="ascii",
    )
    manifest["archive"] = {
        "path": str(archive),
        "bytes": archive.stat().st_size,
        "sha256": archive_hash,
    }
    return manifest


def main() -> None:
    args = parse_args()
    result = build_portable_package(
        args.source_dir,
        args.output_dir,
        args.archive,
        mrp_v3_dashboard=args.mrp_v3_dashboard,
        network_comparison=args.network_comparison,
        resilience_map=args.resilience_map,
        control_analysis_dir=args.control_analysis_dir,
    )
    archive = result["archive"]
    assert isinstance(archive, dict)
    print(f"[OK] Portable folder: {args.output_dir.resolve()}")
    print(f"[OK] Launcher: {(args.output_dir / LAUNCHER_NAME).resolve()}")
    print(f"[OK] ZIP: {archive['path']}")
    print(f"[OK] ZIP bytes: {archive['bytes']}")
    print(f"[OK] ZIP SHA-256: {archive['sha256']}")


if __name__ == "__main__":
    main()
