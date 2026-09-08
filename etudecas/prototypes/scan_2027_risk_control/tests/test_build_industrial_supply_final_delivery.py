from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_industrial_supply_final_delivery as delivery,
)
from etudecas.prototypes.scan_2027_risk_control import standalone_single_html


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_html(path: Path, body: str, *, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body>{body}</body></html>",
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> dict[str, object]:
    source = tmp_path / "canonical"
    dependencies = tmp_path / "dependencies"
    source.mkdir()
    dependencies.mkdir()
    entrypoint = source / "OPEN.html"
    meeting = source / "meeting.html"
    network = source / "network.html"
    component = dependencies / "component.html"
    map_source = dependencies / "map-source"
    map_source.mkdir()
    opaque_map = dependencies / "map.html"
    evidence = source / "package_manifest.json"

    _write_html(
        entrypoint,
        '<a href="meeting.html">Synthèse</a>'
        '<a href="network.html#ranking">Réseau</a>'
        '<a href="../dependencies/component.html">Composant</a>'
        '<a href="../dependencies/map.html">Carte</a>',
        title="Accès final",
    )
    _write_html(
        meeting,
        '<a href="network.html">Réseau</a>'
        '<a href="../dependencies/component.html#lots">Lots</a>'
        '<a href="OPEN.html">Retour</a>',
        title="Synthèse industrielle",
    )
    _write_html(
        network,
        '<section id="ranking">Priorités simulées</section>'
        '<a href="meeting.html">Synthèse</a>'
        '<a href="../dependencies/map.html">Carte</a>',
        title="Réseau fournisseurs",
    )
    _write_html(
        component,
        '<section id="lots">Lots exposés — données légères</section>',
        title="Composant",
    )
    _write_html(
        map_source / "index.html",
        "<p>Carte complète autonome.</p>",
        title="Carte complète",
    )
    standalone_single_html.build_single_html(map_source, opaque_map)
    evidence.write_text(
        json.dumps({"schema_version": "fixture.final.v1", "status": "complete"}),
        encoding="utf-8",
    )
    html_assets = [
        delivery.HtmlAsset(meeting, "views/meeting.html"),
        delivery.HtmlAsset(network, "views/network.html"),
        delivery.HtmlAsset(component, "views/component.html"),
        delivery.HtmlAsset(opaque_map, "views/map.html", opaque=True),
    ]
    evidence_assets = [
        delivery.EvidenceAsset(evidence, "evidence/package_manifest.json")
    ]
    return {
        "entrypoint": entrypoint,
        "html_assets": html_assets,
        "evidence_assets": evidence_assets,
        "sources": [
            entrypoint,
            meeting,
            network,
            component,
            opaque_map,
            evidence,
        ],
    }


def _build(tmp_path: Path, fixture: dict[str, object], *, suffix: str = "v1"):
    output = tmp_path / f"portable-{suffix}"
    archive = tmp_path / f"portable-{suffix}.zip"
    single = tmp_path / f"portable-{suffix}.html"
    result = delivery.build_delivery(
        entrypoint_source=fixture["entrypoint"],
        html_assets=fixture["html_assets"],
        evidence_assets=fixture["evidence_assets"],
        output_dir=output,
        archive=archive,
        single_html=single,
        launcher_name="OPEN_PORTABLE.html",
    )
    return result, output, archive, single


def test_builds_signed_portable_folder_zip_and_single_html(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    before = {path: _sha256(path) for path in fixture["sources"]}

    result, output, archive, single = _build(tmp_path, fixture)

    assert {path: _sha256(path) for path in fixture["sources"]} == before
    manifest = delivery.validate_delivery_package(output)
    assert manifest["entrypoint"] == "index.html"
    assert manifest["lightweight_launcher"] == "OPEN_PORTABLE.html"
    assert (output / "index.html").read_bytes() == (
        output / "OPEN_PORTABLE.html"
    ).read_bytes()
    index = (output / "index.html").read_text(encoding="utf-8")
    assert 'href="views/meeting.html"' in index
    assert 'href="views/network.html#ranking"' in index
    meeting = (output / "views" / "meeting.html").read_text(encoding="utf-8")
    assert 'href="component.html#lots"' in meeting
    assert 'href="../index.html"' in meeting
    assert "connect-src &#x27;none&#x27;" in meeting
    assert (output / "views" / "map.html").read_bytes() == Path(
        fixture["html_assets"][-1].source
    ).read_bytes()
    assert "Aucun serveur et aucun accès Internet" in (
        output / delivery.README_FILE
    ).read_text(encoding="utf-8")
    assert delivery._reference_issues(output) == []

    archive_digest = archive.with_suffix(".zip.sha256.txt")
    assert archive_digest.read_text(encoding="ascii") == (
        f"{_sha256(archive)}  {archive.name}\n"
    )
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert f"{output.name}/OPEN_PORTABLE.html" in names
        assert f"{output.name}/views/map.html" in names
        assert bundle.testzip() is None

    single_result = standalone_single_html.validate_single_html(single)
    assert single_result["plotly_embedded"] is False
    assert single_result["opaque_standalone_view_count"] == 1
    assert single_result["embedded_entry_count"] >= 7
    assert single.with_suffix(".html.sha256.txt").read_text(encoding="ascii") == (
        f"{_sha256(single)}  {single.name}\n"
    )
    document = single.read_text(encoding="utf-8")
    entries = standalone_single_html._runtime_json_assignment(
        document,
        "const files = ",
    )
    map_entry = entries["views/map.html"]
    assert map_entry["opaque_standalone"] is True
    assert standalone_single_html._decoded_entry(
        map_entry,
        label="views/map.html",
    ) == Path(fixture["html_assets"][-1].source).read_bytes()
    assert result["source_artifacts_mutated"] is False


@pytest.mark.parametrize(
    "collision",
    ["folder", "archive", "archive_hash", "single", "single_hash"],
)
def test_refuses_any_existing_delivery_target(
    tmp_path: Path,
    collision: str,
) -> None:
    fixture = _fixture(tmp_path)
    output = tmp_path / "portable"
    archive = tmp_path / "portable.zip"
    single = tmp_path / "portable.html"
    targets = {
        "folder": output,
        "archive": archive,
        "archive_hash": archive.with_suffix(".zip.sha256.txt"),
        "single": single,
        "single_hash": single.with_suffix(".html.sha256.txt"),
    }
    target = targets[collision]
    if collision == "folder":
        target.mkdir()
    else:
        target.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exist"):
        delivery.build_delivery(
            entrypoint_source=fixture["entrypoint"],
            html_assets=fixture["html_assets"],
            evidence_assets=fixture["evidence_assets"],
            output_dir=output,
            archive=archive,
            single_html=single,
        )

    assert target.exists()
    if collision != "folder":
        assert target.read_text(encoding="utf-8") == "keep"


def test_rejects_http_reference_without_leaving_outputs(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    meeting = fixture["html_assets"][0].source
    _write_html(
        meeting,
        '<a href="https://example.test/result">Externe</a>',
        title="Invalide",
    )
    output = tmp_path / "portable"
    archive = tmp_path / "portable.zip"
    single = tmp_path / "portable.html"

    with pytest.raises(ValueError, match="External reference is forbidden"):
        delivery.build_delivery(
            entrypoint_source=fixture["entrypoint"],
            html_assets=fixture["html_assets"],
            evidence_assets=fixture["evidence_assets"],
            output_dir=output,
            archive=archive,
            single_html=single,
        )

    assert not output.exists()
    assert not archive.exists()
    assert not single.exists()


@pytest.mark.parametrize(
    "unsafe_markup",
    [
        '<a href="javascript:parent.document.body.remove()">Unsafe</a>',
        '<script>fetch("https://example.test/leak")</script>',
        '<link rel="stylesheet" href="theme.css">',
        '<img srcset="one.png 1x, two.png 2x">',
        '<form action="https://example.test/submit"></form>',
        '<style>body{background:url(https://example.test/pixel)}</style>',
    ],
)
def test_delivery_rejects_unsupported_or_network_capable_markup(
    tmp_path: Path,
    unsafe_markup: str,
) -> None:
    fixture = _fixture(tmp_path)
    meeting = fixture["html_assets"][0].source
    _write_html(meeting, unsafe_markup, title="Invalide")

    with pytest.raises(ValueError):
        _build(tmp_path, fixture)


def test_rejects_unmapped_or_escaping_link(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    network = fixture["html_assets"][1].source
    _write_html(
        network,
        '<a href="../unmapped.html">Sortie non déclarée</a>',
        title="Invalide",
    )

    with pytest.raises(FileNotFoundError, match="no explicit delivery mapping"):
        _build(tmp_path, fixture)


def test_rejects_case_insensitive_portable_collision(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    duplicate_source = tmp_path / "dependencies" / "duplicate.html"
    _write_html(duplicate_source, "<p>Collision</p>", title="Collision")
    fixture["html_assets"].append(
        delivery.HtmlAsset(duplicate_source, "VIEWS/MEETING.HTML")
    )

    with pytest.raises(ValueError, match="duplicated or reserved"):
        _build(tmp_path, fixture)


def test_signed_output_tampering_is_detected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _result, output, _archive, _single = _build(tmp_path, fixture)
    (output / "views" / "meeting.html").write_text("altéré", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        delivery.validate_delivery_package(output)


def test_optional_plotly_resource_is_mapped_and_embedded(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    meeting = fixture["html_assets"][0].source
    plotly = meeting.parent / "plotly-2.32.0.min.js"
    plotly.write_text("window.Plotly = {};", encoding="utf-8")
    _write_html(
        meeting,
        '<script src="plotly-2.32.0.min.js"></script>'
        "<script>if(location.protocol==='file:'){window.offline=true;}</script>"
        '<a href="network.html">Réseau</a>',
        title="Synthèse avec courbe",
    )
    fixture["evidence_assets"].append(
        delivery.EvidenceAsset(plotly, "views/plotly-2.32.0.min.js")
    )

    _result, output, _archive, single = _build(tmp_path, fixture)

    assert 'src="plotly-2.32.0.min.js"' in (
        output / "views" / "meeting.html"
    ).read_text(encoding="utf-8")
    single_result = standalone_single_html.validate_single_html(single)
    assert single_result["plotly_embedded"] is True
    assert single_result["plotly_source_sha256"] == _sha256(plotly)


def test_cli_mappings_are_explicit_and_safe() -> None:
    args = delivery.parse_args(
        [
            "--entrypoint-html",
            "entry.html",
            "--html-map",
            "meeting.html=views/meeting.html",
            "--opaque-html-map",
            "map.html=views/map.html",
            "--file-map",
            "manifest.json=evidence/manifest.json",
            "--output-dir",
            "portable",
            "--archive",
            "portable.zip",
            "--single-html",
            "portable.html",
        ]
    )

    assert args.html_assets == [
        delivery.HtmlAsset(Path("meeting.html"), "views/meeting.html"),
        delivery.HtmlAsset(Path("map.html"), "views/map.html", opaque=True),
    ]
    assert args.evidence_assets == [
        delivery.EvidenceAsset(Path("manifest.json"), "evidence/manifest.json")
    ]
    with pytest.raises(ValueError, match="safe relative path"):
        delivery._portable_path("../escape.html", suffix=".html")


@pytest.mark.parametrize(
    "unsafe",
    [
        "C:/drive.html",
        "views/name:stream.html",
        "views/bad?.html",
        "views/bad*.html",
        "views/bad<name>.html",
        "views/trailing.",
        "views/trailing ",
        "CON.html",
        "views/aux.txt",
        "views/COM1.json",
        "views/control\x01.html",
        " views/leading.html",
        "views/double//slash.html",
    ],
)
def test_portable_path_rejects_windows_unsafe_names(unsafe: str) -> None:
    with pytest.raises(ValueError, match="safe relative path"):
        delivery._portable_path(unsafe)


def test_unicode_casefold_destination_collision_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    extra = tmp_path / "dependencies" / "extra.html"
    _write_html(extra, "<p>Extra</p>", title="Extra")
    fixture["html_assets"].extend(
        [
            delivery.HtmlAsset(extra, "views/cafe\u0301.html"),
            delivery.HtmlAsset(
                fixture["html_assets"][0].source,
                "VIEWS/CAFÉ.HTML",
            ),
        ]
    )

    with pytest.raises(ValueError, match="duplicated or reserved"):
        _build(tmp_path, fixture)


def test_reserved_single_html_inventory_destination_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    extra = tmp_path / "dependencies" / "reserved.html"
    _write_html(extra, "<p>Reserved</p>", title="Reserved")
    fixture["html_assets"].append(
        delivery.HtmlAsset(extra, standalone_single_html.INVENTORY_PATH)
    )

    with pytest.raises(ValueError, match="duplicated or reserved"):
        _build(tmp_path, fixture)


def test_delivery_final_targets_must_be_distinct(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    same = tmp_path / "same.zip"

    with pytest.raises(ValueError, match="must all be distinct"):
        delivery.build_delivery(
            entrypoint_source=fixture["entrypoint"],
            html_assets=fixture["html_assets"],
            evidence_assets=fixture["evidence_assets"],
            output_dir=same,
            archive=same,
            single_html=tmp_path / "single.html",
        )
