from etudecas.visualization.maps.worldmap_html_template import html_template


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
