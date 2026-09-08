from __future__ import annotations

import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_industrial_supply_preliminary_complete_v3 as subject,
)


def _embedded_payloads(document: str) -> tuple[dict[str, object], dict[str, object]]:
    match = re.search(
        r"const\s+DATA_CHUNKED_GZIP_BASE64\s*=\s*(\{.*?\});\s*"
        r"const\s+DATA_CHUNKED_MANIFEST\s*=\s*(\{.*?\});",
        document,
        flags=re.DOTALL,
    )
    assert match is not None
    chunks = json.loads(match.group(1))
    manifest = json.loads(match.group(2))
    payloads: dict[str, object] = {}
    for key, encoded_parts in chunks.items():
        compressed = base64.b64decode("".join(encoded_parts), validate=True)
        raw = gzip.decompress(compressed)
        assert manifest[key]["raw_bytes"] == len(raw)
        assert manifest[key]["compressed_bytes"] == len(compressed)
        payloads[key] = json.loads(raw)
    return payloads, chunks


def _assert_no_embedded_quality_branch(value: object, path: str = "payload") -> None:
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
    branch_value = re.compile(
        r"(?:^|[_\s:/-])(?:quality|qualit(?:e|\u00e9))(?:$|[_\s:/-])",
        flags=re.IGNORECASE,
    )
    branch_text = re.compile(
        r"quality[_ -]?(?:hold|yield|release)|"
        r"(?:release|retenue|quarantaine)[ _-]?qualit(?:e|\u00e9)|"
        r"qualit(?:e|\u00e9)\s*/\s*release|"
        r"fiabilit(?:e|\u00e9)\s*/\s*qualit(?:e|\u00e9)",
        flags=re.IGNORECASE,
    )
    if isinstance(value, dict):
        for key, item in value.items():
            folded_key = str(key).strip().casefold()
            assert folded_key not in {"quality", "qualite", "qualit\u00e9"}, path
            if folded_key in branch_fields and isinstance(item, str):
                assert item.strip().casefold() not in {
                    "quality",
                    "qualite",
                    "qualit\u00e9",
                }, f"{path}.{key}"
            if folded_key in identity_fields and isinstance(item, str):
                assert branch_value.search(item) is None, f"{path}.{key}"
            if folded_key == "families" and isinstance(item, list):
                assert not any(
                    isinstance(family, str) and branch_value.search(family)
                    for family in item
                ), f"{path}.{key}"
            _assert_no_embedded_quality_branch(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_embedded_quality_branch(item, f"{path}[{index}]")
    elif isinstance(value, str):
        assert branch_text.search(value) is None, path


def _compressed_map(payloads: dict[str, object], body: str = "") -> str:
    chunks: dict[str, list[str]] = {}
    manifest: dict[str, dict[str, object]] = {}
    for key, payload in payloads.items():
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        compressed = gzip.compress(raw, mtime=0)
        chunks[key] = [base64.b64encode(compressed).decode("ascii")]
        manifest[key] = {
            "group": "test",
            "raw_bytes": len(raw),
            "compressed_bytes": len(compressed),
        }
    return (
        "<!doctype html><html><head></head><body>"
        + body
        + "<script>const DATA_CHUNKED_GZIP_BASE64 = "
        + json.dumps(chunks, separators=(",", ":"))
        + ";\nconst DATA_CHUNKED_MANIFEST = "
        + json.dumps(manifest, separators=(",", ":"))
        + ";</script></body></html>"
    )


def test_clean_map_removes_dormant_excluded_theme(tmp_path: Path) -> None:
    source = tmp_path / "map.html"
    source.write_text(
        """<!doctype html>
<select><option value="quality">Qualite</option><option value="risk">Risque</option></select>
<script>
const labels = {
  quality: "Qualite",
  risk: "Risque"
};
</script>
""",
        encoding="utf-8",
    )

    cleaned = subject._clean_map(source)

    assert '<option value="risk">Risque</option>' in cleaned
    assert 'risk: "Risque"' in cleaned
    assert '<option value="quality">' not in cleaned
    assert 'quality: "Qualite"' not in cleaned


def test_clean_map_purges_quality_scenarios_from_compressed_payloads(
    tmp_path: Path,
) -> None:
    source = tmp_path / "map.html"
    source.write_text(
        _compressed_map(
            {
                "scenario_comparison": {
                    "available": True,
                    "families": ["lead", "quality", "stock"],
                    "scenarios": [
                        {
                            "id": "supplier_quality_release",
                            "family": "quality",
                            "label": "Qualite / release",
                        },
                        {
                            "id": "supplier_lead_delay",
                            "family": "lead",
                            "label": "Delai fournisseur",
                        },
                    ],
                },
                "model_panel": {
                    "html": "<table><tr><td>Fiabilite / qualite</td>"
                    "<td>simuler pertes, retours, release qualite et quantite utile"
                    "</td></tr></table>"
                },
                "unrelated": {"family": "stock", "value": 17},
            },
            body="""
<script>
if (mode === "lead_time") { selectLead(); }
else if (mode === "quality") {
  scenarioComparisonSelectedIds = withNominal(
    scenarios.filter(s => familyIncludes(s, "quality"))
  );
} else if (mode === "transport") { selectTransport(); }
</script>
""",
        ),
        encoding="utf-8",
    )
    _original_payloads, original_chunks = _embedded_payloads(
        source.read_text(encoding="utf-8")
    )

    cleaned = subject._clean_map(source)
    payloads, cleaned_chunks = _embedded_payloads(cleaned)

    assert payloads["scenario_comparison"]["families"] == ["lead", "stock"]
    assert payloads["scenario_comparison"]["scenarios"] == [
        {
            "id": "supplier_lead_delay",
            "family": "lead",
            "label": "Delai fournisseur",
        }
    ]
    assert payloads["model_panel"]["html"] == (
        "<table><tr><td>Fiabilite fournisseur</td>"
        "<td>simuler pertes, retours et quantite utile expediee</td></tr></table>"
    )
    assert payloads["unrelated"] == {"family": "stock", "value": 17}
    assert cleaned_chunks["unrelated"] == original_chunks["unrelated"]
    assert re.search(r'mode\s*===\s*["\']quality["\']', cleaned) is None
    for key, payload in payloads.items():
        _assert_no_embedded_quality_branch(payload, f"payload.{key}")


def test_clean_map_rebuilds_real_supplier_campaign_without_quality_branch() -> None:
    if not subject.DEFAULT_MAP_FILE.is_file():
        pytest.skip("La carte source auditee n'est pas disponible.")
    if not subject.DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR.is_dir():
        pytest.skip("La campagne fournisseur source n'est pas disponible.")
    source_hash = hashlib.sha256(subject.DEFAULT_MAP_FILE.read_bytes()).hexdigest()
    original_document = subject.DEFAULT_MAP_FILE.read_text(encoding="utf-8")
    _original_payloads, original_chunks = _embedded_payloads(original_document)

    cleaned = subject._clean_map(subject.DEFAULT_MAP_FILE)
    payloads, cleaned_chunks = _embedded_payloads(cleaned)
    campaign = payloads["supplier_risk_campaign"]

    assert campaign["global"]["supplier_count"] == 29
    assert campaign["global"]["case_count"] == 175
    assert campaign["global"]["stress_case_count"] == 174
    assert campaign["global"]["families"] == [
        "capacity",
        "stock",
        "lead",
        "reliability",
        "upstream",
        "cost",
    ]
    assert campaign["nodes"]["SDC-VD0910216A"]["driver_family"] == "lead"
    assert campaign["nodes"]["SDC-VD0910216A"][
        "score_decisionnel_pct"
    ] == pytest.approx(0.2974)
    assert all(node["tested_family_count"] == 6 for node in campaign["nodes"].values())
    assert cleaned_chunks["nodes"] == original_chunks["nodes"]
    assert cleaned_chunks["edges"] == original_chunks["edges"]
    assert re.search(r'mode\s*===\s*["\']quality["\']', cleaned) is None
    for key, payload in payloads.items():
        _assert_no_embedded_quality_branch(payload, f"payload.{key}")
    assert (
        hashlib.sha256(subject.DEFAULT_MAP_FILE.read_bytes()).hexdigest() == source_hash
    )


def test_clean_map_clarifies_legacy_map_scope_on_copy(tmp_path: Path) -> None:
    source = tmp_path / "map.html"
    source.write_text(
        "<!doctype html><html><head></head><body><p>"
        + subject.LEGACY_MAP_PRIORITY_TEXT
        + "</p></body></html>",
        encoding="utf-8",
    )

    cleaned = subject._clean_map(source)

    assert subject.LEGACY_MAP_PRIORITY_TEXT not in cleaned
    assert subject.CURRENT_MAP_SCOPE_TEXT in cleaned
    assert subject.MAP_SCOPE_BANNER_TEXT in cleaned
    assert cleaned.count(subject.MAP_SCOPE_BANNER_MARKER) == 1


def test_clean_map_labels_legacy_supplier_stress_table_as_exploratory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "map.html"
    source.write_text(
        "<!doctype html><html><head></head><body>"
        + subject.LEGACY_MAP_STRESS_TITLE_HTML
        + "<table><thead><tr>"
        + subject.LEGACY_MAP_RANK_HEADER
        + subject.LEGACY_MAP_DECISION_SCORE_HEADER
        + "</tr></thead></table></body></html>",
        encoding="utf-8",
    )

    cleaned = subject._clean_map(source)

    assert subject.CURRENT_MAP_STRESS_SCOPE_HTML in cleaned
    assert subject.CURRENT_MAP_RANK_HEADER in cleaned
    assert subject.CURRENT_MAP_DECISION_SCORE_HEADER in cleaned
    assert subject.LEGACY_MAP_RANK_HEADER not in cleaned
    assert subject.LEGACY_MAP_DECISION_SCORE_HEADER not in cleaned


def test_plotly_geo_guard_detects_dynamic_cdn_world_download() -> None:
    document = """<!doctype html><html><head></head><body>
<script>
const trace = {type: "scattergeo"};
Plotly.newPlot(document.body, [trace], {geo: {scope: "world"}}, {});
</script></body></html>"""

    with pytest.raises(
        subject.CompletePreliminaryDeliveryError,
        match=r"cdn\.plot\.ly/world_110m\.json",
    ):
        subject._assert_plotly_geo_offline(document)


def test_embed_plotly_world_topology_preloads_before_first_plot() -> None:
    document = """<!doctype html><html><head>
<script>window.Plotly = {setPlotConfig: function() {}};</script>
</head><body><script>
const trace = {type: "scattergeo"};
Plotly.newPlot(document.body, [trace], {geo: {scope: "world"}}, {});
</script></body></html>"""
    topology = {
        "type": "Topology",
        "objects": {"countries": {}, "land": {}},
        "arcs": [[[0, 0], [1, 1]]],
    }

    embedded = subject._embed_plotly_world_topology(document, topology)

    assert embedded.count(subject.OFFLINE_WORLD_TOPOLOGY_MARKER) == 1
    assert 'Plotly.setPlotConfig({topojsonURL:"./"})' in embedded
    assert embedded.index(subject.OFFLINE_WORLD_TOPOLOGY_ASSIGNMENT) < embedded.index(
        "Plotly.newPlot"
    )
    assert '"type":"Topology"' in embedded
    subject._assert_plotly_geo_offline(embedded)


@pytest.mark.parametrize(
    "excluded_text",
    (
        "quality_hold",
        "quality_yield",
        "Retenue qualité",
        "Quarantaine fournisseur",
    ),
)
def test_clean_map_rejects_excluded_business_branch(
    tmp_path: Path, excluded_text: str
) -> None:
    source = tmp_path / "map.html"
    source.write_text(f"<!doctype html><p>{excluded_text}</p>", encoding="utf-8")

    with pytest.raises(subject.CompletePreliminaryDeliveryError):
        subject._clean_map(source)


def test_generated_v3_contract_when_audited_sources_are_available() -> None:
    if not subject.DEFAULT_OUTPUT_DIR.is_dir():
        pytest.skip(
            "Le paquet audité externe n'est pas disponible dans cet environnement."
        )

    manifest = subject.validate_delivery(subject.DEFAULT_OUTPUT_DIR)
    page = (subject.DEFAULT_OUTPUT_DIR / subject.ENTRYPOINT).read_text(encoding="utf-8")

    assert manifest["view_count"] == 3
    assert manifest["network_campaign_run_count"] == 1255
    assert manifest["in_scope_unique_run_count"] == 1513
    assert manifest["excluded_out_of_scope_unique_run_count"] == 252
    assert manifest["lot_case_key_present"] is True
    assert manifest["current_action_results_available"] is False
    assert manifest["physical_supply_poles_identified"] is False
    assert manifest["supplier_priority_order_validated"] is False
    assert manifest["priority_boundary_audit_included"] is True
    assert manifest["nonseparation_group_count"] == 4
    assert manifest["network_supplier_state_dependent_risk_enabled"] is False
    assert manifest["network_dynamic_requirement_pair_count"] == 3
    assert manifest["prepared_dynamic_requirement_pair_count"] == 24
    assert manifest["map_world_topology_embedded"] is True
    assert manifest["map_world_topology_key"] == "world_110m"
    assert manifest["map_world_topology_sha256"] == subject.WORLD_TOPOJSON_SHA256
    assert manifest["map_plotly_geo_remote_fetch_prevented"] is True
    assert manifest["nominal_run_curves_available"] is True
    assert manifest["nominal_run_curves_chain_count"] == 2
    assert manifest["nominal_run_curves_horizon_days"] == 720
    assert manifest["nominal_run_curves_single_realization"] is True
    assert manifest["nominal_run_supplier_incident_enabled"] is False
    assert manifest["nominal_run_supplier_state_dependent_risk_enabled"] is False
    assert manifest["existing_map_tabs_preserved"] is True
    assert "boundary/scientific_audit" in manifest["source_file_sha256"]
    assert "map/world_topojson" in manifest["source_file_sha256"]
    assert subject.FORBIDDEN_DELIVERY_TEXT.search(page) is None
    assert "https://" not in page
    assert page.count('class="view') == 3
    assert "Bilan consolidé du périmètre retenu" in page
    assert "Aucun ordre de priorité fournisseur n'est validé" in page
    assert "intervalle bootstrap descriptif 2,5–97,5 %" in page
    assert "supplier_state_dependent_risk.enabled=false" in page
    assert "1 331 identifiants d'arête" in page
    assert "ce que la généalogie technique permet de suivre" in page
    assert "ce que les lots prouvent réellement" not in page
    assert "Carte du réseau enrichie par le run nominal actuel" in page
    assert "lissages adaptés 7/28 jours" in page
    assert "classement" not in page.casefold()
    assert "dossier robuste" not in page.casefold()
    lot_rows = subject._read_csv(subject.DEFAULT_OUTPUT_DIR / subject.LOT_DETAIL_CSV)
    assert lot_rows and all(row["case_key"] for row in lot_rows)
    dc1910_edges = [row for row in lot_rows if "DC-1910" in row["source_id"]]
    assert len(dc1910_edges) == 1331
    assert sum(row["node_id"] == "DC-1920" for row in dc1910_edges) == 664
    assert sum(row["node_id"] == "C-XXXXX" for row in dc1910_edges) == 667
    map_document = (subject.DEFAULT_OUTPUT_DIR / subject.MAP_ASSET).read_text(
        encoding="utf-8"
    )
    assert map_document.count(subject.nominal_run_curves.INJECTION_MARKER) == 4
    assert subject.nominal_run_curves.BUTTON_ID in map_document
    assert subject.nominal_run_curves.MODAL_ID in map_document
    assert "une seule réalisation nominale illustrative" in map_document
    assert subject.MAP_SCOPE_BANNER_TEXT in map_document
    assert subject.CURRENT_MAP_SCOPE_TEXT in map_document
    assert subject.LEGACY_MAP_PRIORITY_TEXT not in map_document
    assert subject.CURRENT_MAP_STRESS_SCOPE_HTML in map_document
    assert subject.CURRENT_MAP_RANK_HEADER in map_document
    assert subject.CURRENT_MAP_DECISION_SCORE_HEADER in map_document
    assert subject.LEGACY_MAP_RANK_HEADER not in map_document
    assert subject.LEGACY_MAP_DECISION_SCORE_HEADER not in map_document
    subject._assert_plotly_geo_offline(map_document)
    payloads, _chunks = _embedded_payloads(map_document)
    campaign = payloads["supplier_risk_campaign"]
    assert campaign["global"]["families"] == [
        "capacity",
        "stock",
        "lead",
        "reliability",
        "upstream",
        "cost",
    ]
    assert campaign["global"]["stress_case_count"] == 174
    assert campaign["nodes"]["SDC-VD0910216A"]["driver_family"] == "lead"
    for key, payload in payloads.items():
        _assert_no_embedded_quality_branch(payload, f"payload.{key}")
    assert re.search(r'mode\s*===\s*["\']quality["\']', map_document) is None


def test_generated_map_renders_from_file_without_network() -> None:
    if not subject.DEFAULT_OUTPUT_DIR.is_dir():
        pytest.skip("Le paquet V3 externe n'est pas disponible.")
    browser_candidates = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    )
    executable = next((path for path in browser_candidates if path.is_file()), None)
    if executable is None:
        pytest.skip("Aucun navigateur Edge/Chromium install\u00e9.")
    playwright_api = pytest.importorskip("playwright.sync_api")

    map_path = subject.DEFAULT_OUTPUT_DIR / subject.MAP_ASSET
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(executable),
            headless=True,
        )
        context = browser.new_context()
        context.set_offline(True)
        page = context.new_page()
        external_requests: list[str] = []
        page_errors: list[str] = []
        page.on(
            "request",
            lambda request: (
                external_requests.append(request.url)
                if request.url.lower().startswith(
                    ("http://", "https://", "ws://", "wss://")
                )
                else None
            ),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        page.goto(map_path.as_uri(), wait_until="load", timeout=60_000)
        page.wait_for_function(
            """() => {
              const chart = document.getElementById("chart");
              return Boolean(
                chart && chart.data && chart.data.length &&
                document.querySelectorAll("#chart .geolayer path").length
              );
            }""",
            timeout=60_000,
        )
        page.locator(f"#{subject.nominal_run_curves.BUTTON_ID}").click()
        page.wait_for_function(
            """() => document.querySelectorAll(
              '#nominalRunCurvesModal .js-plotly-plot'
            ).length === 4""",
            timeout=60_000,
        )
        state = page.evaluate(
            """() => ({
              topologyLoaded: Boolean(
                window.PlotlyGeoAssets &&
                window.PlotlyGeoAssets.topojson &&
                window.PlotlyGeoAssets.topojson.world_110m
              ),
              geoPathCount: document.querySelectorAll("#chart .geolayer path").length,
              scopeBannerVisible: Boolean(
                document.querySelector("[data-v3-map-scope-warning]") &&
                document.querySelector("[data-v3-map-scope-warning]")
                  .getBoundingClientRect().height
              ),
              nominalModalVisible: document
                .getElementById("nominalRunCurvesModal")
                .classList.contains("visible"),
              nominalPlotCount: document.querySelectorAll(
                '#nominalRunCurvesModal .js-plotly-plot'
              ).length,
              nominalChainCount: NOMINAL_RUN_CURVES.chains.length,
              nominalHorizon: NOMINAL_RUN_CURVES.horizon_days,
              nominalIncidentEnabled: NOMINAL_RUN_CURVES.supplier_incident_enabled,
              nominalStateRiskEnabled:
                NOMINAL_RUN_CURVES.supplier_state_dependent_risk_enabled,
              existingModeCount: document.querySelectorAll('.modeBtn').length
            })"""
        )
        browser.close()

    assert external_requests == []
    assert page_errors == []
    assert state["topologyLoaded"] is True
    assert state["geoPathCount"] > 0
    assert state["scopeBannerVisible"] is True
    assert state["nominalModalVisible"] is True
    assert state["nominalPlotCount"] == 4
    assert state["nominalChainCount"] == 2
    assert state["nominalHorizon"] == 720
    assert state["nominalIncidentEnabled"] is False
    assert state["nominalStateRiskEnabled"] is False
    assert state["existingModeCount"] >= 10
