from etudecas.visualization.maps.worldmap_html_template import html_template


def _fragment(document: str, start: str, end: str) -> str:
    assert start in document
    assert end in document
    return document.split(start, 1)[1].split(end, 1)[0]


def test_html_template_keeps_data_marker_and_interpolates_inputs() -> None:
    html = html_template(
        "Supply < Map",
        '{"nodes": []}',
        '<tr><td>MAT-1</td></tr>',
        1,
        '<tr><td>equation</td></tr>',
    )

    assert "<title>Supply &lt; Map</title>" in html
    assert '<div class="title">Supply &lt; Map</div>' in html
    assert 'const DATA = {"nodes": []};' in html
    assert "<div id=\"materialTableMeta\" class=\"tableModalMeta\">1 lignes</div>" in html
    assert "<tr><td>MAT-1</td></tr>" in html
    assert "<tr><td>equation</td></tr>" in html
    assert 'id="scanDashboardBtn"' in html
    assert 'id="scanDashboardModal"' in html
    assert 'id="scanDashboardContent"' in html
    assert "const SCAN_DASHBOARD = DATA.scan_dashboard" in html
    assert "function renderScanDashboard()" in html
    assert 'window.location.hash === "#resilience-scan"' in html
    assert "function simulatedRiskCascadeLotImpact(row)" in html
    assert 'id="simRiskCascadeLotSelect"' in html
    assert "Lots contenant une matière exposée" in html
    assert "Voir le lot et la cascade" in html
    assert "aucun classement par rang n'est utilisé ici" in html
    assert "is_scenario_aggregate: true" in html
    assert "Les lots communs ne sont comptes qu'une fois" in html
    assert ".riskCascadeExplorer {\n      position: relative;\n      z-index: 2;" in html
    assert "function selectedLotTraceDemandContributionQty(snapshot, row)" in html
    assert "parsed && parsed[rootOrderId]" in html
    assert "customerAllocationQty += selectedLotTraceDemandContributionQty(snapshot, row);" in html
    assert "renderLotTraceEventsTable(snapshot.events, 14, snapshot)" in html
    assert "renderLotTraceEventsTable(selected.events, selected.events.length, snapshot)" in html
    assert "traces / ${rawQtyText} lot client" in html
    assert 'id="supplierAuditSelect"' in html
    assert "function initSupplierAuditControls()" in html
    assert 'setPanelMode("risk");' in html
    assert "selectedAuditSupplier" in html
    assert 'figure.kind === "radar"' in html
    assert 'type: "scatterpolar"' in html
    assert "Audit à renseigner" in html


def test_scan_dashboard_mobile_tabs_wrap_without_scrolling_the_modal() -> None:
    html = html_template("Supply Map", '{"nodes": []}', "", 0, "")

    assert ".scanDashboardTabBar .lotTraceDirectionTabs" in html
    assert "flex-wrap: wrap;" in html
    assert ".scanDashboardModalBody {" in html
    assert "overflow-x: hidden;" in html
    assert ".scanEvidenceBanner code" in html
    assert "overflow-wrap: anywhere;" in html


def test_incident_lot_link_requires_an_intersection_and_traceable_lots() -> None:
    html = html_template("Supply Map", '{"nodes": []}', "", 0, "")
    impact = _fragment(
        html,
        "function simulatedRiskCascadeLotImpact(row)",
        "function selectedSimulatedRiskCascadeLotImpact()",
    )
    lot_section = _fragment(
        html,
        "function simulatedRiskCascadeLotsHtml(row)",
        "function simulatedRiskCascadePathSignature(row)",
    )

    assert "outputItemIds" in impact
    assert "routeNodeIds" in impact
    assert "routeEdgeIds" in impact
    assert "businessPathKey" in impact
    assert "finishedProductItemIds" in impact
    assert "traceableLotRows = lotRows.filter" in impact
    assert (
        "Boolean(eventIds.length && directLotIds.size && traceableLotRows.length)"
        in impact
    )
    assert "!LOT_TRACE.available" in lot_section
    assert (
        "simulatedRiskCascadeKeyForRow(row) !== selectedSimulatedRiskCascadeKey"
        in lot_section
    )
    assert 'if (!impact.available) return "";' in lot_section
    assert "impact.traceableLotRows.map" in lot_section
    assert "impact.lotRows.map" not in lot_section
    assert "Lots finis aval" in lot_section
    assert "Lecture aval" in lot_section
    assert "le diagnostic de flux s'arrête" in lot_section
    assert "Lots traçables proposés" in lot_section
    assert "Lots de provenance directement marqués" in lot_section
    assert "peut dépasser le registre d'attribution quantitative" in lot_section

    event_ids = _fragment(
        html,
        "function simulatedRiskCascadeEventIds(row)",
        "function simulatedRiskCascadeLotImpact(row)",
    )
    assert "Array.isArray(row.event_ids)" in event_ids
    assert "values.push(row.event_id)" not in event_ids


def test_incident_lot_open_keeps_risk_mode_and_draws_both_paths() -> None:
    html = html_template("Supply Map", '{"nodes": []}', "", 0, "")
    open_handler = _fragment(
        html,
        'const cascadeLotOpenBtn = document.getElementById("simRiskCascadeLotOpenBtn")',
        "function simulatedRiskNodeImpactAsset(nodeId)",
    )
    lot_overlay = _fragment(
        html,
        "function buildLotTraceOverlayTraces()",
        "function simulatedRiskCascadeRouteClosure(row)",
    )
    build_traces = _fragment(
        html,
        "function buildTraces()",
        "function hideFactoryPanel()",
    )

    assert 'currentPanelMode !== "simulated_risk"' in open_handler
    assert "impact.traceableLotIds.includes(lotId)" in open_handler
    assert 'setPanelMode("ops")' not in open_handler
    assert "setSelectedLot(lotId)" in open_handler
    assert "lotTraceOverlayEnabledForCurrentMode()" in lot_overlay
    assert 'const lineColor = riskCascadeMode ? "#2563eb" : "#f97316"' in lot_overlay
    assert (
        "const lotOverlayNodes = lotTraceOverlayEnabledForCurrentMode()"
        in build_traces
    )
    assert build_traces.index("buildSimulatedRiskCascadeOverlayTraces()") < (
        build_traces.index("buildLotTraceOverlayTraces()")
    )
    assert "lotTraceOverlayEnabledForCurrentMode() ? ` | lot" in build_traces

    # Historical modes and the nominal lot toolbar keep their existing entry points.
    assert 'document.getElementById("modeOps").addEventListener' in html
    assert 'document.getElementById("modeSimulatedRisk").addEventListener' in html
    assert 'const visible = currentPanelMode === "ops"' in html
