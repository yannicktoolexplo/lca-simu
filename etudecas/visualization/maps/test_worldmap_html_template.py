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
    assert 'id="scanDashboardBtn"' in html
    assert 'id="scanDashboardModal"' in html
    assert 'id="scanDashboardContent"' in html
    assert "const SCAN_DASHBOARD = DATA.scan_dashboard" in html
    assert "function renderScanDashboard()" in html
    assert 'window.location.hash === "#resilience-scan"' in html


def test_scan_dashboard_mobile_tabs_wrap_without_scrolling_the_modal() -> None:
    html = html_template("Supply Map", '{"nodes": []}', "", 0, "")

    assert ".scanDashboardTabBar .lotTraceDirectionTabs" in html
    assert "flex-wrap: wrap;" in html
    assert ".scanDashboardModalBody {" in html
    assert "overflow-x: hidden;" in html
    assert ".scanEvidenceBanner code" in html
    assert "overflow-wrap: anywhere;" in html
