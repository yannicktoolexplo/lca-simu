from __future__ import annotations

import base64
import gzip
import json
import zipfile
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.portable_demo_package import (
    LAUNCHER_NAME,
    MANIFEST_NAME,
    README_NAME,
    _append_complement_section,
    _polish_resilience_map,
    build_portable_package,
    local_html_reference_issues,
    refresh_scientific_manifest,
    sanitize_internal_paths,
    sha256,
)


def source_package(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    views = source / "views"
    views.mkdir(parents=True)
    (source / "index.html").write_text(
        '<a href="#inside">Interne</a><a href="views/map.html">Carte</a>',
        encoding="utf-8",
    )
    (views / "map.html").write_text(
        '<script src="plotly.js"></script><a href="https://example.test/info">Info</a>',
        encoding="utf-8",
    )
    incident_map = (
        '<button id="modeOps">Run nominal</button>'
        '<button id="scenarioComparisonBtn" class="tableBtn">Comparer scenarios</button>'
    )
    for name in ("carte_qualite_incident_lots.html", "carte_retard_338929_incident_lots.html"):
        (views / name).write_text(incident_map, encoding="utf-8")
    (views / "plotly.js").write_text("window.Plotly = {};", encoding="utf-8")
    (source / "manifest.json").write_text(
        json.dumps({"source": r"C:\source\provenance.csv"}),
        encoding="utf-8",
    )
    return source


def test_build_portable_package_is_relative_complete_and_zipped(tmp_path: Path) -> None:
    source = source_package(tmp_path)
    output = tmp_path / "portable"
    archive = tmp_path / "portable.zip"

    result = build_portable_package(source, output, archive)

    assert (output / LAUNCHER_NAME).read_bytes() == (output / "index.html").read_bytes()
    assert (output / README_NAME).is_file()
    portable_manifest = json.loads((output / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert portable_manifest["requires_internet"] is False
    assert portable_manifest["requires_local_server"] is False
    assert portable_manifest["runtime_reference_issue_count"] == 0
    assert all(not Path(row["path"]).is_absolute() for row in portable_manifest["files"])
    assert local_html_reference_issues(output) == []
    assert result["archive"]["sha256"]
    assert archive.with_suffix(".zip.sha256.txt").is_file()
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    assert f"portable/{LAUNCHER_NAME}" in names
    assert "portable/views/map.html" in names
    incident_document = (output / "views" / "carte_qualite_incident_lots.html").read_text(
        encoding="utf-8"
    )
    assert "Incident sans action" in incident_document
    assert "run nominal" not in incident_document.lower()


def test_existing_targets_are_never_overwritten(tmp_path: Path) -> None:
    source = source_package(tmp_path)
    output = tmp_path / "portable"
    output.mkdir()
    with pytest.raises(FileExistsError):
        build_portable_package(source, output, tmp_path / "portable.zip")


def test_missing_local_reference_is_reported(tmp_path: Path) -> None:
    source = source_package(tmp_path)
    (source / "views" / "map.html").write_text(
        '<script src="missing.js"></script>',
        encoding="utf-8",
    )
    issues = local_html_reference_issues(source)
    assert issues == [
        {
            "page": "views/map.html",
            "reference": "missing.js",
            "reason": "missing_local_target",
        }
    ]


def test_internal_paths_are_neutralized_in_text_and_json(tmp_path: Path) -> None:
    root = tmp_path / "package"
    root.mkdir()
    (root / "data.csv").write_text(
        "source\n" + r"C:\dev\lca-simu-pr40\etudecas\data.csv" + "\n",
        encoding="utf-8",
    )
    (root / "data.json").write_text(
        json.dumps(
            {
                "source": r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\run\file.csv"
            }
        ),
        encoding="utf-8",
    )

    assert sanitize_internal_paths(root) == 2
    combined = (root / "data.csv").read_text(encoding="utf-8") + (root / "data.json").read_text(
        encoding="utf-8"
    )
    assert r"C:\dev" not in combined
    assert "provenance/repository" in combined
    assert "provenance/artifacts" in combined


def test_scientific_manifest_is_refreshed_for_portable_files(tmp_path: Path) -> None:
    root = tmp_path / "portable"
    views = root / "views"
    views.mkdir(parents=True)
    page = views / "page.html"
    page.write_text("portable", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "output_dir": "provenance/artifacts/source",
                "standalone_html": "provenance/artifacts/source/index.html",
                "files": [
                    {
                        "path": "provenance/artifacts/supplier_risk_lot_explorer_20260831_v6/views/page.html",
                        "bytes": 1,
                        "sha256": "old",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    refresh_scientific_manifest(root)

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["output_dir"] == "."
    assert manifest["standalone_html"] == "index.html"
    assert manifest["portable_file_ledger_refreshed"] is True
    assert manifest["files"] == [
        {
            "path": "views/page.html",
            "bytes": 8,
            "sha256": sha256(page),
        }
    ]


def test_resilience_link_opens_dashboard_directly(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<html><main></main></html>", encoding="utf-8")

    _append_complement_section(index, include_control=False)

    document = index.read_text(encoding="utf-8")
    assert 'href="views/resilience_scan_v3.html#resilience-scan"' in document
    assert 'href="product_lever_response_curves.csv"' in document
    assert 'href="supplier_risk_decision_brief.json"' in document
    assert 'href="views/incidents_risques_lots.json"' in document
    assert 'href="portable_manifest.json"' in document


def test_resilience_page_title_and_legacy_note_are_clarified() -> None:
    legacy_note = (
        "Adaptive canonical replay uses a precomputed daily open-loop schedule; "
        "canonical state feedback is not yet implemented."
    )
    encoded = base64.b64encode(gzip.compress(legacy_note.encode("utf-8"), mtime=0)).decode(
        "ascii"
    )
    payload = json.dumps({"scan_dashboard": [encoded]}, separators=(",", ":"))
    source = (
        "<html><head><title>Supply Graph POC - Geocoded Map</title></head>"
        f"<body><script>const DATA_CHUNKED_GZIP_BASE64 = {payload};\n</script></body></html>"
    )

    document = _polish_resilience_map(source)

    assert "<title>RESILIENCE-SCAN V3 — carte et analyses fréquentielles</title>" in document
    marker = "const DATA_CHUNKED_GZIP_BASE64 = "
    start = document.index(marker) + len(marker)
    end = document.index(";\n", start)
    updated_payload = json.loads(document[start:end])
    clarified = gzip.decompress(
        base64.b64decode("".join(updated_payload["scan_dashboard"]))
    ).decode("utf-8")
    assert legacy_note not in clarified
    assert "Historical adaptive replay used a precomputed daily open-loop schedule" in clarified
    assert "This limitation applies to that replay only" in clarified
