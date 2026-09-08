from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import standalone_single_html
from etudecas.prototypes.scan_2027_risk_control.standalone_single_html import (
    FRAGMENT_TOKEN,
    INVENTORY_PATH,
    PLOTLY_TOKEN,
    build_single_html,
    rewrite_local_links,
    validate_single_html,
)


def fixture_package(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    views = root / "views"
    views.mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html><html><head><title>Demo</title></head><body>"
        '<a href="#inside">Section</a>'
        '<a href="views/map.html#panel" target="_blank">Carte</a>'
        '<a href="data.csv">Données</a>'
        "</body></html>",
        encoding="utf-8",
    )
    (views / "map.html").write_text(
        "<!doctype html><html><head><title>Carte test</title>"
        '<script src="plotly-2.32.0.min.js"></script></head><body>'
        '<img src="../image.png"><a href="../index.html#inside">Retour</a>'
        "<script>if(location.protocol==='file:'){window.offlineTopo=true;}</script>"
        "</body></html>",
        encoding="utf-8",
    )
    (views / "plotly-2.32.0.min.js").write_text(
        "window.Plotly={version:'fixture'};",
        encoding="utf-8",
    )
    (root / "image.png").write_bytes(b"fixture-png")
    (root / "data.csv").write_text("day,value\n1,2\n", encoding="utf-8")
    (root / "unlinked.txt").write_text("proof", encoding="utf-8")
    return root


def embedded_files(document: str) -> dict[str, dict[str, object]]:
    marker = "const files = "
    start = document.index(marker) + len(marker)
    end = document.index(";\n  const plotlyBundle", start)
    return json.loads(document[start:end])


def decoded(entry: dict[str, object]) -> bytes:
    return gzip.decompress(base64.b64decode(str(entry["gzip_base64"])))


def replace_assignment(document: str, marker: str, value: object) -> str:
    start = document.index(marker) + len(marker)
    source = document[start:].lstrip()
    _old, end = json.JSONDecoder().raw_decode(source)
    value_start = len(document[start:]) - len(source) + start
    return (
        document[:value_start]
        + standalone_single_html._script_json(value)
        + document[value_start + end :]
    )


def test_builds_one_html_with_isolated_views_and_all_evidence(tmp_path: Path) -> None:
    source = fixture_package(tmp_path)
    original_map = (source / "views" / "map.html").read_bytes()
    output = tmp_path / "single.html"

    result = build_single_html(source, output)

    document = output.read_text(encoding="utf-8")
    entries = embedded_files(document)
    assert result["view_count"] == 1
    assert result["embedded_entry_count"] == 5
    assert set(entries) == {
        INVENTORY_PATH,
        "data.csv",
        "image.png",
        "unlinked.txt",
        "views/map.html",
    }
    assert 'data-standalone-view="views/map.html"' in document
    assert 'data-standalone-fragment="#panel"' in document
    assert 'data-standalone-download="data.csv"' in document
    assert '<a href="#inside">Section</a>' in document
    assert "DecompressionStream" in document
    assert "iframe" in document
    assert '() => "<script>" + values[1] + "<\\/script>"' in document
    assert "views/plotly-2.32.0.min.js" not in entries

    map_document = decoded(entries["views/map.html"]).decode("utf-8")
    assert PLOTLY_TOKEN in map_document
    assert "if(true)" in map_document
    assert "data:image/png;base64," in map_document
    assert 'data-standalone-close="1"' in map_document
    assert FRAGMENT_TOKEN in map_document
    assert (source / "views" / "map.html").read_bytes() == original_map

    inventory = decoded(entries[INVENTORY_PATH]).decode("utf-8")
    assert "unlinked.txt" in inventory
    assert 'data-standalone-download="unlinked.txt"' in inventory

    expected_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    assert result["output_sha256"] == expected_hash
    assert output.with_suffix(".html.sha256.txt").read_text(encoding="ascii") == (
        f"{expected_hash}  single.html\n"
    )


def test_never_overwrites_existing_output(tmp_path: Path) -> None:
    source = fixture_package(tmp_path)
    output = tmp_path / "single.html"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_single_html(source, output)

    assert output.read_text(encoding="utf-8") == "keep"


def test_external_runtime_link_is_rejected() -> None:
    with pytest.raises(ValueError, match="External reference"):
        rewrite_local_links(
            '<a href="https://example.test/result">Result</a>',
            "index.html",
            set(),
        )


def test_plotly_is_optional_when_no_embedded_view_uses_it(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Résumé</title></head>"
        "<body><p>Données légères.</p></body></html>",
        encoding="utf-8",
    )
    output = tmp_path / "single.html"

    result = build_single_html(source, output)
    validated = validate_single_html(output)

    assert result["plotly_embedded"] is False
    assert result["plotly_source_sha256"] == ""
    assert validated["embedded_entry_count"] == 1
    assert "Données légères" in output.read_text(encoding="utf-8")


def test_existing_single_html_is_embedded_unchanged_as_an_opaque_view(
    tmp_path: Path,
) -> None:
    inner_source = tmp_path / "inner-source"
    inner_source.mkdir()
    (inner_source / "index.html").write_text(
        "<!doctype html><html><head><title>Carte autonome</title></head>"
        "<body><p>Vue autonome imbriquée.</p></body></html>",
        encoding="utf-8",
    )
    inner_output = tmp_path / "inner.html"
    build_single_html(inner_source, inner_output)
    inner_bytes = inner_output.read_bytes()

    outer_source = tmp_path / "outer-source"
    views = outer_source / "views"
    views.mkdir(parents=True)
    (outer_source / "index.html").write_text(
        "<!doctype html><html><head><title>Livraison</title></head><body>"
        '<a href="views/carte.html">Carte</a></body></html>',
        encoding="utf-8",
    )
    (views / "carte.html").write_bytes(inner_bytes)
    outer_output = tmp_path / "outer.html"

    result = build_single_html(outer_source, outer_output)
    entries = embedded_files(outer_output.read_text(encoding="utf-8"))

    assert result["opaque_standalone_view_count"] == 1
    assert entries["views/carte.html"]["opaque_standalone"] is True
    assert decoded(entries["views/carte.html"]) == inner_bytes
    assert entries["views/carte.html"]["source_sha256"] == entries[
        "views/carte.html"
    ]["embedded_sha256"]


def test_explicit_index_alias_is_not_embedded_as_a_duplicate_view(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    index = (
        "<!doctype html><html><head><title>Demo</title></head><body>"
        '<a href="OUVRIR_BILAN.html">Accueil</a></body></html>'
    )
    (source / "index.html").write_text(index, encoding="utf-8")
    (source / "OUVRIR_BILAN.html").write_text(index, encoding="utf-8")
    output = tmp_path / "single.html"

    result = build_single_html(
        source,
        output,
        index_aliases=("OUVRIR_BILAN.html",),
    )
    entries = embedded_files(output.read_text(encoding="utf-8"))

    assert result["index_aliases"] == ["OUVRIR_BILAN.html"]
    assert "OUVRIR_BILAN.html" not in entries
    assert 'data-standalone-close="1"' in output.read_text(encoding="utf-8")


def test_plotly_remains_required_when_a_view_declares_the_bundle(
    tmp_path: Path,
) -> None:
    source = fixture_package(tmp_path)
    (source / "views" / "plotly-2.32.0.min.js").unlink()

    with pytest.raises(FileNotFoundError, match="Local Plotly bundle"):
        build_single_html(source, tmp_path / "single.html")


def test_runtime_json_escapes_script_breakout_and_validator_rejects_raw_json(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    views = source / "views"
    views.mkdir(parents=True)
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Accueil</title></head><body>"
        '<a href="views/risk.html">Risque</a></body></html>',
        encoding="utf-8",
    )
    breakout = "</script><script>window.injected=true</script>&\u2028\u2029"
    (views / "risk.html").write_text(
        f"<!doctype html><html><head><title>{breakout}</title></head>"
        "<body><p>Fixture</p></body></html>",
        encoding="utf-8",
    )
    output = tmp_path / "single.html"

    build_single_html(source, output)

    document = output.read_text(encoding="utf-8")
    assert breakout not in document
    assert r"\u003c/script\u003e\u003cscript\u003e" in document
    assert r"\u0026" in document
    assert r"\u2028\u2029" in standalone_single_html._script_json(
        {"unicode_separators": "\u2028\u2029"}
    )
    tampered = document.replace(r"\u003c/script\u003e", "</script>", 1)
    tampered_output = tmp_path / "tampered.html"
    tampered_output.write_text(tampered, encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe or non-canonical"):
        validate_single_html(tampered_output)


def test_index_local_image_is_inlined_and_no_local_source_survives(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Image</title></head>"
        '<body><img src="picture.png"></body></html>',
        encoding="utf-8",
    )
    (source / "picture.png").write_bytes(b"small-png-fixture")
    output = tmp_path / "single.html"

    build_single_html(source, output)

    document = output.read_text(encoding="utf-8")
    assert 'src="data:image/png;base64,' in document
    assert 'src="picture.png"' not in document
    validate_single_html(output)


@pytest.mark.parametrize(
    ("location", "markup", "message"),
    [
        ("index", '<link rel="stylesheet" href="style.css">', "Only anchor"),
        ("child", '<link rel="stylesheet" href="style.css">', "Only anchor"),
        ("index", '<img srcset="a.png 1x">', "Unsupported URL-bearing"),
        ("child", '<video poster="poster.png"></video>', "Unsupported URL-bearing"),
        ("index", '<object data="report.pdf"></object>', "Unsupported URL-bearing"),
        ("child", '<form action="submit"><button>OK</button></form>', "Unsupported URL-bearing"),
        ("index", '<style>body{background:url(https://x.test/a)}</style>', "CSS url"),
        ("child", '<meta http-equiv="refresh" content="0;url=https://x.test">', "Meta refresh"),
    ],
)
def test_unsupported_url_surfaces_are_rejected_fail_closed(
    tmp_path: Path,
    location: str,
    markup: str,
    message: str,
) -> None:
    source = tmp_path / "source"
    views = source / "views"
    views.mkdir(parents=True)
    index_markup = markup if location == "index" else '<a href="views/view.html">Vue</a>'
    child_markup = markup if location == "child" else "<p>Vue</p>"
    (source / "index.html").write_text(
        f"<!doctype html><html><head><title>Test</title>{index_markup}</head>"
        "<body></body></html>",
        encoding="utf-8",
    )
    (views / "view.html").write_text(
        f"<!doctype html><html><head><title>Vue</title>{child_markup}</head>"
        "<body></body></html>",
        encoding="utf-8",
    )
    for name in ("style.css", "a.png", "poster.png", "report.pdf"):
        (source / name).write_bytes(b"fixture")

    with pytest.raises(ValueError, match=message):
        build_single_html(source, tmp_path / "single.html")


def test_javascript_and_dynamic_network_apis_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Unsafe</title></head><body>"
        '<a href="javascript:parent.document.body.remove()">Action</a>'
        '<script>fetch("https://example.test/leak")</script>'
        "</body></html>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Dynamic network API|External reference"):
        build_single_html(source, tmp_path / "single.html")


def test_hardened_output_declares_csp_and_sandbox(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Secure</title></head>"
        "<body><p>Hors ligne</p></body></html>",
        encoding="utf-8",
    )
    output = tmp_path / "single.html"

    result = build_single_html(source, output)

    document = output.read_text(encoding="utf-8")
    assert result["security_profile"] == standalone_single_html.SECURITY_PROFILE
    assert "connect-src &#x27;none&#x27;" in document
    assert 'sandbox="allow-scripts allow-downloads"' in document
    assert "allow-same-origin" not in document


def test_pseudo_opaque_and_cryptographically_tampered_opaque_are_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    views = source / "views"
    views.mkdir(parents=True)
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Outer</title></head><body>"
        '<a href="views/fake.html">Fake</a></body></html>',
        encoding="utf-8",
    )
    (views / "fake.html").write_text(
        "<!doctype html><html><head><title>Fake</title></head><body>"
        '<script>const files = {}; const metadata = {"schema_version":'
        '"etudecas.single_html_industrial_demo.v1"}; '
        "window.ETUDECAS_SINGLE_HTML={};</script></body></html>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Runtime assignment|metadata fields"):
        build_single_html(source, tmp_path / "pseudo.html")

    inner_source = tmp_path / "inner-source"
    inner_source.mkdir()
    (inner_source / "index.html").write_text(
        "<!doctype html><html><head><title>Inner</title></head>"
        "<body><p>Inner</p></body></html>",
        encoding="utf-8",
    )
    inner = tmp_path / "inner.html"
    build_single_html(inner_source, inner)
    inner_document = inner.read_text(encoding="utf-8")
    entries = standalone_single_html._runtime_json_assignment(
        inner_document,
        "const files = ",
    )
    entries[INVENTORY_PATH]["embedded_sha256"] = "0" * 64
    (views / "fake.html").write_text(
        replace_assignment(inner_document, "const files = ", entries),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_single_html(source, tmp_path / "tampered-opaque.html")


@pytest.mark.parametrize(
    "marker",
    [FRAGMENT_TOKEN, PLOTLY_TOKEN, "const files = ", "singleHtmlRuntime"],
)
def test_reserved_runtime_marker_in_normal_source_is_rejected(
    tmp_path: Path,
    marker: str,
) -> None:
    source = tmp_path / "source"
    views = source / "views"
    views.mkdir(parents=True)
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Index</title></head><body>"
        '<a href="views/view.html">Vue</a></body></html>',
        encoding="utf-8",
    )
    (views / "view.html").write_text(
        "<!doctype html><html><head><title>Vue</title></head>"
        f"<body><!-- {marker} --></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Reserved standalone marker"):
        build_single_html(source, tmp_path / "single.html")


def test_reserved_inventory_source_and_nonidentical_alias_are_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    index = "<!doctype html><html><head><title>Index</title></head><body></body></html>"
    (source / "index.html").write_text(index, encoding="utf-8")
    (source / INVENTORY_PATH).write_text("collision", encoding="utf-8")
    with pytest.raises(ValueError, match="Reserved inventory"):
        build_single_html(source, tmp_path / "inventory.html")

    (source / INVENTORY_PATH).unlink()
    (source / "OPEN.html").write_text(index + "different", encoding="utf-8")
    with pytest.raises(ValueError, match="differs from index"):
        build_single_html(
            source,
            tmp_path / "alias.html",
            index_aliases=("OPEN.html",),
        )


def test_existing_hash_sidecar_blocks_build_without_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Index</title></head><body></body></html>",
        encoding="utf-8",
    )
    output = tmp_path / "single.html"
    sidecar = output.with_suffix(".html.sha256.txt")
    sidecar.write_text("keep", encoding="ascii")

    with pytest.raises(FileExistsError, match="already exists"):
        build_single_html(source, output)

    assert not output.exists()
    assert sidecar.read_text(encoding="ascii") == "keep"


def test_validation_failure_rolls_back_html_sidecar_and_temporaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Index</title></head><body></body></html>",
        encoding="utf-8",
    )
    output = tmp_path / "single.html"

    def fail_validation(_path: Path) -> dict[str, object]:
        raise ValueError("forced validation failure")

    monkeypatch.setattr(
        standalone_single_html,
        "validate_single_html",
        fail_validation,
    )
    with pytest.raises(ValueError, match="forced validation failure"):
        build_single_html(source, output)

    assert not output.exists()
    assert not output.with_suffix(".html.sha256.txt").exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_duplicate_download_basenames_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "a").mkdir(parents=True)
    (source / "b").mkdir()
    (source / "index.html").write_text(
        "<!doctype html><html><head><title>Index</title></head><body></body></html>",
        encoding="utf-8",
    )
    (source / "a" / "report.csv").write_text("a", encoding="utf-8")
    (source / "b" / "REPORT.csv").write_text("b", encoding="utf-8")

    with pytest.raises(ValueError, match="Ambiguous downloadable basename"):
        build_single_html(source, tmp_path / "single.html")


def test_opaque_nesting_depth_is_bounded(tmp_path: Path) -> None:
    inner_source = tmp_path / "inner-source"
    inner_source.mkdir()
    (inner_source / "index.html").write_text(
        "<!doctype html><html><head><title>Inner</title></head>"
        "<body><p>Inner</p></body></html>",
        encoding="utf-8",
    )
    inner = tmp_path / "inner.html"
    build_single_html(inner_source, inner)

    middle_source = tmp_path / "middle-source"
    (middle_source / "views").mkdir(parents=True)
    (middle_source / "index.html").write_text(
        "<!doctype html><html><head><title>Middle</title></head><body>"
        '<a href="views/inner.html">Inner</a></body></html>',
        encoding="utf-8",
    )
    (middle_source / "views" / "inner.html").write_bytes(inner.read_bytes())
    middle = tmp_path / "middle.html"
    build_single_html(middle_source, middle)

    outer_source = tmp_path / "outer-source"
    (outer_source / "views").mkdir(parents=True)
    (outer_source / "index.html").write_text(
        "<!doctype html><html><head><title>Outer</title></head><body>"
        '<a href="views/middle.html">Middle</a></body></html>',
        encoding="utf-8",
    )
    (outer_source / "views" / "middle.html").write_bytes(middle.read_bytes())

    with pytest.raises(ValueError, match="nesting is too deep"):
        build_single_html(outer_source, tmp_path / "outer.html")


def test_validator_rejects_unsafe_entry_key_extra_field_and_inventory_tamper(
    tmp_path: Path,
) -> None:
    source = fixture_package(tmp_path)
    output = tmp_path / "single.html"
    build_single_html(source, output)
    document = output.read_text(encoding="utf-8")
    entries = standalone_single_html._runtime_json_assignment(
        document,
        "const files = ",
    )

    unsafe_entries = dict(entries)
    unsafe_entries["../escape.csv"] = unsafe_entries.pop("data.csv")
    unsafe = tmp_path / "unsafe-key.html"
    unsafe.write_text(
        replace_assignment(document, "const files = ", unsafe_entries),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsafe embedded entry path"):
        validate_single_html(unsafe)

    extra_entries = json.loads(json.dumps(entries))
    extra_entries["data.csv"]["unexpected"] = True
    extra = tmp_path / "extra-field.html"
    extra.write_text(
        replace_assignment(document, "const files = ", extra_entries),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unexpected embedded entry fields"):
        validate_single_html(extra)

    inventory_entries = json.loads(json.dumps(entries))
    inventory_entry = inventory_entries[INVENTORY_PATH]
    modified_inventory = decoded(inventory_entry) + b"<!-- forged -->"
    compressed = gzip.compress(modified_inventory, compresslevel=9, mtime=0)
    digest = hashlib.sha256(modified_inventory).hexdigest()
    inventory_entry.update(
        {
            "source_bytes": len(modified_inventory),
            "embedded_bytes": len(modified_inventory),
            "source_sha256": digest,
            "embedded_sha256": digest,
            "gzip_base64": base64.b64encode(compressed).decode("ascii"),
        }
    )
    forged_inventory = tmp_path / "forged-inventory.html"
    forged_inventory.write_text(
        replace_assignment(document, "const files = ", inventory_entries),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inventory content is not exact"):
        validate_single_html(forged_inventory)


def test_validator_rejects_local_outer_resource_and_oversized_declaration(
    tmp_path: Path,
) -> None:
    source = fixture_package(tmp_path)
    output = tmp_path / "single.html"
    build_single_html(source, output)
    document = output.read_text(encoding="utf-8")
    local = tmp_path / "local-ref.html"
    local.write_text(
        document.replace("</body>", '<img src="neighbour.png"></body>', 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="retains a local source"):
        validate_single_html(local)

    entries = standalone_single_html._runtime_json_assignment(
        document,
        "const files = ",
    )
    entries["data.csv"]["embedded_bytes"] = standalone_single_html.MAX_ENTRY_BYTES + 1
    oversized = tmp_path / "oversized.html"
    oversized.write_text(
        replace_assignment(document, "const files = ", entries),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid bounded integer"):
        validate_single_html(oversized)


def test_small_single_html_browser_smoke_navigation_download_and_return(
    tmp_path: Path,
) -> None:
    browser_candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    )
    executable = next((path for path in browser_candidates if path.is_file()), None)
    if executable is None:
        pytest.skip("No installed Edge/Chromium executable")
    playwright_api = pytest.importorskip("playwright.sync_api")

    inner_source = tmp_path / "inner-source"
    inner_source.mkdir()
    (inner_source / "index.html").write_text(
        "<!doctype html><html><head><title>Opaque</title></head>"
        '<body><p id="opaque-ready">Carte opaque prête</p>'
        '<iframe id="legacy-srcdoc"></iframe>'
        "<script>document.getElementById('legacy-srcdoc').srcdoc="
        "'<p id=\"legacy-ready\">Sous-vue ancienne prête</p>';</script>"
        "</body></html>",
        encoding="utf-8",
    )
    inner = tmp_path / "inner.html"
    build_single_html(inner_source, inner)

    outer_source = tmp_path / "outer-source"
    views = outer_source / "views"
    views.mkdir(parents=True)
    (outer_source / "index.html").write_text(
        "<!doctype html><html><head><title>Smoke</title></head><body>"
        '<a id="open-opaque" href="views/opaque.html">Carte</a>'
        '<a id="download-proof" href="proof.txt">Preuve</a>'
        "</body></html>",
        encoding="utf-8",
    )
    (views / "opaque.html").write_bytes(inner.read_bytes())
    (outer_source / "proof.txt").write_text("preuve UTF-8 — ok", encoding="utf-8")
    output = tmp_path / "browser-smoke.html"
    build_single_html(outer_source, output)

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable),
            headless=True,
        )
        page = browser.new_page(accept_downloads=True)
        browser_errors: list[str] = []
        external_requests: list[str] = []
        page.on("console", lambda message: browser_errors.append(message.text))
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if request.url.lower().startswith(("http://", "https://", "ws://", "wss://"))
            else None,
        )
        page.goto(output.as_uri(), wait_until="load")
        page.locator("#open-opaque").click()
        try:
            page.frame_locator("#standaloneFrame").locator("#opaque-ready").wait_for(
                state="visible",
                timeout=15_000,
            )
        except Exception:
            frame_documents = [frame.content()[:500] for frame in page.frames]
            runtime_state = page.evaluate(
                """async () => ({
                  decompression: "DecompressionStream" in window,
                  crypto: Boolean(window.crypto && window.crypto.subtle),
                  loadingHidden: document.getElementById("standaloneLoading").hidden,
                  direct: await Promise.race([
                    window.ETUDECAS_SINGLE_HTML.openView("views/opaque.html")
                      .then(() => "resolved", (error) => String(error)),
                    new Promise((resolve) => setTimeout(() => resolve("timeout"), 2000))
                  ]),
                  srcdocLength: document.getElementById("standaloneFrame").srcdoc.length,
                  srcdocStart: document.getElementById("standaloneFrame").srcdoc.slice(0, 80)
                })"""
            )
            pytest.fail(
                "Browser smoke failed: "
                f"errors={browser_errors}, frames={frame_documents}, "
                f"viewer={page.locator('#standaloneViewer').get_attribute('aria-hidden')}, "
                f"runtime={runtime_state}"
            )
        page.frame_locator("#standaloneFrame").frame_locator(
            "#legacy-srcdoc"
        ).locator("#legacy-ready").wait_for(state="visible", timeout=15_000)
        opaque_frame = page.frame_locator("#standaloneFrame")
        assert (
            opaque_frame.locator("body").evaluate(
                "() => typeof window.ETUDECAS_SINGLE_HTML"
            )
            == "object"
        )
        opaque_frame.locator(
            '[data-standalone-view="__contenu_embarque__.html"]'
        ).click()
        opaque_frame.frame_locator("#standaloneFrame").locator(
            "h1", has_text="Contenu embarqué"
        ).wait_for(state="visible", timeout=15_000)
        opaque_frame.locator("#standaloneCloseBtn").click()
        page.locator("#standaloneCloseBtn").click()
        assert page.locator("#standaloneViewer").get_attribute("aria-hidden") == "true"
        page.locator("#open-opaque").click()
        page.frame_locator("#standaloneFrame").locator("#opaque-ready").wait_for(
            state="visible",
            timeout=15_000,
        )
        page.locator("#standaloneCloseBtn").click()
        with page.expect_download(timeout=15_000) as download_info:
            page.locator("#download-proof").click()
        assert download_info.value.suggested_filename == "proof.txt"
        assert browser_errors == []
        assert external_requests == []
        browser.close()
