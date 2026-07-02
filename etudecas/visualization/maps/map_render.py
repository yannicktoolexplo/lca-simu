"""HTML rendering helpers for map visualization panels."""

from __future__ import annotations

import html
import json
import math
from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def render_json_panel_html(title: str, description: str, data: Any) -> str:
    pretty = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent jsonPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(title)}</div>",
            f"<div class=\"orderLedgerStatus\">{html.escape(description)}</div>",
            "<div class=\"jsonPanelPreWrap\">",
            f"<pre class=\"jsonPanelPre\">{html.escape(pretty)}</pre>",
            "</div>",
            "</div>",
        ]
    )


def json_html_asset(title: str, description: str, data: Any) -> dict[str, str]:
    return {
        "html": render_json_panel_html(title, description, data),
    }


def render_data_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "<div class=\"panelEmptyState dataEmptyState\">Aucune donnee disponible.</div>"
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(cell if cell is not None else 'n/a'))}</td>" for cell in row)
        + "</tr>"
        for row in rows
    )
    return (
        "<div class=\"dataSummaryTableWrap\">"
        "<table class=\"dataSummaryTable\">"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        "</table>"
        "</div>"
    )


def render_data_kv(rows: list[tuple[str, Any]]) -> str:
    if not rows:
        return ""
    return "".join(
        [
            "<div class=\"dataKvGrid\">",
            *(
                f"<div class=\"dataKvLabel\">{html.escape(str(label))}</div>"
                f"<div class=\"dataKvValue\">{html.escape(str(value if value not in (None, '') else 'n/a'))}</div>"
                for label, value in rows
            ),
            "</div>",
        ]
    )


def html_tooltip_attrs(tooltip: str | None) -> str:
    return f" data-tooltip=\"{html.escape(tooltip, quote=True)}\" tabindex=\"0\"" if tooltip else ""


def html_tooltip_class(base_class: str, tooltip: str | None) -> str:
    base = base_class.strip()
    if not tooltip:
        return base
    return f"{base} riskTooltipHost".strip()


def render_data_panel_html(title: str, subtitle: str, sections: list[tuple[str, str]]) -> str:
    section_parts: list[str] = []
    for section_title, content in sections:
        section_parts.extend(
            [
                "<section class=\"dataSummarySection\">",
                f"<div class=\"dataSummarySectionTitle\">{html.escape(section_title)}</div>",
                content,
                "</section>",
            ]
        )
    section_html = "".join(section_parts)
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent dataSummaryPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(title)}</div>",
            f"<div class=\"orderLedgerStatus\">{html.escape(subtitle)}</div>",
            "<div class=\"dataSummaryScroll\">",
            section_html,
            "</div>",
            "</div>",
        ]
    )


def data_html_asset(title: str, subtitle: str, sections: list[tuple[str, str]]) -> dict[str, str]:
    return {
        "html": render_data_panel_html(title, subtitle, sections),
    }


def metric_label_value(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def metric_section(title: str) -> dict[str, str]:
    return {"label": title, "value": ""}


def fmt_qty(value: Any, digits: int = 1) -> str:
    numeric = _to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    return f"{numeric:,.{digits}f}".replace(",", " ")


def fmt_days(value: Any, digits: int = 1) -> str:
    numeric = _to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    return f"{numeric:.{digits}f} j"


def fmt_pct(value: Any, digits: int = 1) -> str:
    numeric = _to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    return f"{numeric:.{digits}f}%"
