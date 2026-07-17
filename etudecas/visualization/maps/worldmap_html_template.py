"""HTML template for the interactive supply-chain world map."""

from __future__ import annotations

import html

DEBUG_PANEL_ENABLED = False


def html_template(
    title: str,
    data_json: str,
    material_table_html: str,
    material_table_count: int,
    global_model_equations_html: str,
) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .title {{
      font-weight: 700;
      font-size: 14px;
      margin-right: 8px;
    }}
    .meta {{
      font-size: 12px;
      color: #475569;
      margin-right: 14px;
    }}
    .box {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .modeTabs {{
      display: inline-flex;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      overflow: hidden;
      background: #f8fafc;
    }}
    .modeBtn {{
      border: 0;
      background: transparent;
      color: #334155;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 12px;
      cursor: pointer;
    }}
    .modeBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    .modeBtn.hidden {{
      display: none;
    }}
    .debugOnly {{
      display: none !important;
    }}
    body.showDebugTools .debugOnly {{
      display: inline-flex !important;
    }}
    body.showDebugTools .debugUnavailable {{
      display: none !important;
    }}
    .debugToggleLabel {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 700;
      color: #334155;
      white-space: nowrap;
    }}
    .sensitivityTop3Box,
    .simulatedRiskControlsBox,
    .lotTraceControlsBox,
    .uncertaintyMonteCarloBox,
    .uncertaintyControlsBox {{
      display: none;
    }}
    .sensitivityTop3Box.visible,
    .simulatedRiskControlsBox.visible,
    .lotTraceControlsBox.visible,
    .uncertaintyMonteCarloBox.visible,
    .uncertaintyControlsBox.visible {{
      display: flex;
    }}
    .simulatedRiskControlsBox,
    .lotTraceControlsBox,
    .uncertaintyControlsBox {{
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .simulatedRiskControlsBox label,
    .simulatedRiskModeLabel,
    .lotTraceControlsBox label,
    .uncertaintyControlsBox label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #334155;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .simulatedRiskControlsBox select,
    .lotTraceControlsBox select,
    .uncertaintyControlsBox select {{
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      background: #ffffff;
      color: #0f172a;
      font-size: 12px;
      font-weight: 700;
      padding: 5px 8px;
    }}
    .lotTraceControlsBox select {{
      min-width: 260px;
      max-width: min(520px, 52vw);
    }}
    .uncertaintyControlsBox input[type="range"] {{
      width: 112px;
    }}
    .simulatedRiskViewValue,
    .uncertaintyIntensityValue {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      min-width: 34px;
    }}
    #typeFilters label {{
      margin-right: 8px;
      font-size: 12px;
      white-space: nowrap;
    }}
    .timelineWindowBox {{
      display: none;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .timelineWindowBox.visible {{
      display: flex;
    }}
    .timelineWindowBox label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #334155;
      white-space: nowrap;
    }}
    .timelineWindowBox input[type="range"] {{
      width: 108px;
      accent-color: #2563eb;
    }}
    .timelineWindowValue {{
      font-size: 12px;
      font-weight: 700;
      color: #0f172a;
      white-space: nowrap;
    }}
    #chart {{
      width: 100%;
      height: calc(100vh - 64px);
    }}
    #sensitivityLegend,
    #simulatedRiskLegend,
    #riskLegend,
    #uncertaintyLegend {{
      position: fixed;
      left: 16px;
      bottom: 16px;
      z-index: 9;
      display: none;
      max-width: min(520px, calc(100vw - 32px));
      padding: 10px 12px;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
      font-size: 11px;
      color: #334155;
    }}
    #sensitivityLegend.visible,
    #simulatedRiskLegend.visible,
    #riskLegend.visible,
    #uncertaintyLegend.visible {{
      display: block;
    }}
    .sensitivityLegendTitle {{
      font-weight: 800;
      color: #0f172a;
      margin-bottom: 6px;
    }}
    .sensitivityLegendRows {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px 10px;
      align-items: center;
    }}
    .simulatedRiskGlobalSummary {{
      margin-top: 8px;
      padding-top: 7px;
      border-top: 1px solid #e2e8f0;
      color: #475569;
      line-height: 1.35;
    }}
    .sensitivityLegendItem {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      white-space: nowrap;
    }}
    .sensitivityLegendDot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
      border: 1px solid rgba(15, 23, 42, 0.18);
    }}
    .lotTracePanel {{
      position: fixed;
      right: 16px;
      bottom: 16px;
      z-index: 8;
      display: none;
      width: min(560px, calc(100vw - 32px));
      max-height: min(620px, calc(100vh - 118px));
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.96);
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
      overflow: hidden;
    }}
    .lotTracePanel.visible {{
      display: flex;
      flex-direction: column;
    }}
    .lotTracePanelHeader {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }}
    .lotTracePanelTitle {{
      color: #0f172a;
      font-size: 13px;
      font-weight: 900;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .lotTracePanelMeta {{
      margin-top: 2px;
      color: #475569;
      font-size: 11px;
      font-weight: 600;
      line-height: 1.3;
    }}
    .lotTracePanelBody {{
      padding: 10px 12px 12px;
      overflow: auto;
      min-height: 0;
    }}
    .lotTraceSummaryGrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }}
    .lotTraceMetric {{
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 7px 8px;
      background: #ffffff;
      min-width: 0;
    }}
    .lotTraceMetricLabel {{
      color: #64748b;
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .lotTraceMetricValue {{
      margin-top: 3px;
      color: #0f172a;
      font-size: 12px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }}
    .lotTraceSectionTitle {{
      margin: 10px 0 5px;
      color: #334155;
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }}
    .lotTraceTable {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 10.5px;
    }}
    .lotTraceTable th,
    .lotTraceTable td {{
      padding: 5px 6px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .lotTraceTable th {{
      color: #475569;
      background: #f8fafc;
      font-weight: 900;
    }}
    .lotTraceTable .num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .lotTraceStatusPill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 10px;
      font-weight: 900;
      white-space: nowrap;
    }}
    .lotTraceStatusPill.completed {{
      color: #166534;
      background: #dcfce7;
      border: 1px solid #86efac;
    }}
    .lotTraceStatusPill.blocked {{
      color: #991b1b;
      background: #fee2e2;
      border: 1px solid #fecaca;
    }}
    .lotTraceEmpty {{
      padding: 8px;
      color: #64748b;
      font-size: 11px;
      border: 1px dashed #cbd5e1;
      border-radius: 8px;
      background: #f8fafc;
    }}
    .lotTraceMatch {{
      background: #fff7ed !important;
      box-shadow: inset 3px 0 0 #f97316;
    }}
    .lotTraceControlsBox option.pfStatusStock,
    .lotTraceModalControls option.pfStatusStock {{
      color: #15803d;
      font-weight: 800;
    }}
    .lotTraceControlsBox option.pfStatusAvailable,
    .lotTraceModalControls option.pfStatusAvailable {{
      color: #c2410c;
      font-weight: 800;
    }}
    .lotTraceControlsBox option.pfStatusShortage,
    .lotTraceModalControls option.pfStatusShortage {{
      color: #b91c1c;
      font-weight: 800;
    }}
    .lotTraceControlsBox option.deferredOrder,
    .lotTraceModalControls option.deferredOrder,
    .lotTraceControlsBox option.deferredOrderBlocked,
    .lotTraceModalControls option.deferredOrderBlocked {{
      color: #991b1b;
      font-weight: 900;
    }}
    .lotTraceControlsBox option.deferredOrderCompleted,
    .lotTraceModalControls option.deferredOrderCompleted {{
      color: #7c3aed;
      font-weight: 900;
    }}
    .lotTraceModalBody {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 0;
    }}
    .lotTraceModalControls {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding: 10px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #f8fafc;
    }}
    .lotTraceModalControls label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #334155;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }}
    .lotTraceModalControls select {{
      min-width: min(620px, 58vw);
      max-width: 72vw;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      background: #ffffff;
      color: #0f172a;
      font-size: 12px;
      font-weight: 700;
      padding: 6px 9px;
    }}
    .lotTraceDirectionTabs {{
      display: inline-flex;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      overflow: hidden;
      background: #ffffff;
    }}
    .lotTraceDirectionBtn {{
      border: 0;
      background: transparent;
      color: #334155;
      font-size: 12px;
      font-weight: 800;
      padding: 6px 10px;
      cursor: pointer;
    }}
    .lotTraceDirectionBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    .lotTraceOrderDetailsBtn.hidden {{
      display: none;
    }}
    .lotTraceOrderDetailsBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    .lotTraceGraphWrap {{
      min-height: 380px;
      max-height: 620px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #ffffff;
      overflow: auto;
    }}
    .lotTraceGraphSvg {{
      display: block;
      min-width: 980px;
      min-height: 380px;
    }}
    .lotTraceGraphLink {{
      stroke: #cbd5e1;
      stroke-width: 2;
      fill: none;
      marker-end: url(#lotTraceArrow);
    }}
    .lotTraceGraphLink.transport {{
      stroke: #f97316;
    }}
    .lotTraceGraphLink.production {{
      stroke: #2563eb;
    }}
    .lotTraceGraphLink.deferred {{
      stroke: #991b1b;
      stroke-width: 2.4;
    }}
    .lotTraceGraphLink.deferredDone {{
      stroke: #16a34a;
      stroke-width: 2.4;
    }}
    .lotTraceGraphNode rect {{
      fill: #ffffff;
      stroke: #94a3b8;
      stroke-width: 1.2;
      rx: 8;
    }}
    .lotTraceGraphNode.root rect {{
      stroke: #f97316;
      stroke-width: 2.4;
      fill: #fff7ed;
    }}
    .lotTraceGraphNode.mixed rect {{
      stroke-dasharray: 5 3;
    }}
    .lotTraceGraphNode.pfStatusStock rect {{
      stroke: #16a34a;
      stroke-width: 2.4;
      fill: #dcfce7;
    }}
    .lotTraceGraphNode.pfStatusAvailable rect {{
      stroke: #ea580c;
      stroke-width: 2.4;
      fill: #ffedd5;
    }}
    .lotTraceGraphNode.pfStatusShortage rect {{
      stroke: #dc2626;
      stroke-width: 2.4;
      fill: #fee2e2;
    }}
    .lotTraceGraphNode.operation rect {{
      fill: #f8fafc;
      stroke: #64748b;
      stroke-width: 1.2;
      rx: 6;
    }}
    .lotTraceGraphNode.operation.production rect {{
      fill: #eff6ff;
      stroke: #2563eb;
    }}
    .lotTraceGraphNode.operation.transport rect {{
      fill: #fff7ed;
      stroke: #f97316;
    }}
    .lotTraceGraphNode.operation.stockState rect {{
      fill: #f0fdf4;
      stroke: #16a34a;
    }}
    .lotTraceGraphNode.operation.deferredOrder rect {{
      fill: #f8fafc;
      stroke: #64748b;
    }}
    .lotTraceGraphNode.operation.deferredDelay rect {{
      fill: #fee2e2;
      stroke: #dc2626;
      stroke-width: 2;
    }}
    .lotTraceGraphNode.operation.deferredReceipt rect {{
      fill: #ffedd5;
      stroke: #ea580c;
      stroke-width: 1.8;
    }}
    .lotTraceGraphNode.operation.deferredDone rect {{
      fill: #dcfce7;
      stroke: #16a34a;
      stroke-width: 2;
    }}
    .lotTraceGraphNode.operation.deferredBlocked rect {{
      fill: #fee2e2;
      stroke: #991b1b;
      stroke-width: 2;
    }}
    .lotTraceGraphNode text {{
      fill: #0f172a;
      font-size: 11px;
      font-weight: 700;
      pointer-events: none;
    }}
    .lotTraceGraphNode .muted {{
      fill: #64748b;
      font-size: 10px;
      font-weight: 600;
    }}
    .lotTraceGraphEmpty {{
      padding: 24px;
      color: #64748b;
      font-size: 12px;
    }}
    .lotTraceGraphTimelineText {{
      fill: #334155;
      font-size: 10px;
      font-weight: 700;
    }}
    .riskSummaryCard {{
      border: 1px solid #cbd5e1;
      border-left: 5px solid #64748b;
      border-radius: 10px;
      background: #f8fafc;
      padding: 12px 14px;
      margin: 10px 0;
    }}
    .riskSummaryHeader {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(260px, 0.9fr);
      gap: 12px;
      align-items: start;
    }}
    .riskSummaryPill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      background: #e2e8f0;
      color: #0f172a;
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }}
    .riskSummaryTitle {{
      margin-top: 8px;
      color: #0f172a;
      font-size: 17px;
      font-weight: 900;
    }}
    .riskSummaryText {{
      margin-top: 6px;
      color: #334155;
      font-size: 13px;
      line-height: 1.45;
    }}
    .riskSummaryGrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .riskFactCard {{
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      background: rgba(255,255,255,0.78);
      padding: 8px 10px;
      min-width: 0;
    }}
    .riskFactLabel {{
      color: #64748b;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .riskFactValue {{
      margin-top: 3px;
      color: #0f172a;
      font-size: 13px;
      font-weight: 900;
      overflow-wrap: anywhere;
    }}
    .riskScenarioSection {{
      margin: 12px 0 6px;
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
    }}
    .riskScenarioCards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 8px;
      margin: 8px 0 12px;
    }}
    .riskScenarioCard {{
      border: 1px solid #cbd5e1;
      border-left: 4px solid #64748b;
      border-radius: 8px;
      background: #ffffff;
      padding: 9px 10px;
      min-width: 0;
    }}
    .riskScenarioCardTitle {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      margin-bottom: 4px;
    }}
    .riskScenarioCardText {{
      color: #475569;
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .riskScenarioMuted {{
      color: #64748b;
      font-size: 11px;
      line-height: 1.4;
      margin: 6px 0 10px;
    }}
    .riskCascadeDiagram {{
      border: 1px solid #dbeafe;
      border-radius: 8px;
      background: #f8fafc;
      padding: 8px;
      margin: 8px 0 12px;
      overflow-x: auto;
    }}
    .riskCascadeDiagram svg {{
      display: block;
      min-width: 1480px;
      width: 100%;
      height: auto;
    }}
    .riskCascadeDiagram .cascadeBox {{
      fill: #ffffff;
      stroke: #cbd5e1;
      stroke-width: 1.2;
    }}
    .riskCascadeDiagram .cascadeBox.trigger {{
      fill: #eff6ff;
      stroke: #2563eb;
    }}
    .riskCascadeDiagram .cascadeBox.local {{
      fill: #f0fdfa;
      stroke: #0f766e;
    }}
    .riskCascadeDiagram .cascadeBox.route {{
      fill: #fff7ed;
      stroke: #f97316;
    }}
    .riskCascadeDiagram .cascadeBox.effect {{
      fill: #fef2f2;
      stroke-width: 2;
    }}
    .riskCascadeDiagram .cascadeArrow {{
      stroke: #64748b;
      stroke-width: 1.6;
      fill: none;
      marker-end: url(#riskCascadeArrow);
    }}
    .riskCascadeDiagram .cascadeTitle {{
      fill: #0f172a;
      font-size: 12px;
      font-weight: 900;
    }}
    .riskCascadeDiagram .cascadeText {{
      fill: #334155;
      font-size: 10.5px;
      font-weight: 700;
    }}
    .riskCascadeDiagram .cascadeMuted {{
      fill: #64748b;
      font-size: 10px;
      font-weight: 700;
    }}
    .riskCascadeExplorer {{
      border: 1px solid #dbeafe;
      border-radius: 10px;
      background: #f8fafc;
      padding: 10px;
      margin: 10px 0 14px;
    }}
    .riskCascadeExplorerControls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 8px;
    }}
    .riskCascadeExplorerControls select,
    .riskCascadeExplorerControls input {{
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      background: #ffffff;
      color: #0f172a;
      font-size: 12px;
      font-weight: 700;
      padding: 6px 9px;
    }}
    .riskCascadeExplorerGrid {{
      display: grid;
      grid-template-columns: minmax(260px, 0.95fr) minmax(360px, 1.55fr);
      gap: 10px;
    }}
    .riskCascadeList {{
      max-height: 360px;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .riskCascadeListItem {{
      text-align: left;
      border: 1px solid #cbd5e1;
      border-left: 4px solid #64748b;
      border-radius: 8px;
      background: #ffffff;
      color: #0f172a;
      padding: 8px;
      cursor: pointer;
    }}
    .riskCascadeListItem.active {{
      outline: 2px solid #2563eb;
      background: #eff6ff;
    }}
    .riskCascadeListTitle {{
      font-size: 12px;
      font-weight: 900;
      margin-bottom: 3px;
    }}
    .riskCascadeListText,
    .riskCascadeTimelineText {{
      color: #475569;
      font-size: 11px;
      line-height: 1.35;
    }}
    .riskCascadeListMeta {{
      color: #0f172a;
      font-size: 11px;
      font-weight: 800;
      line-height: 1.35;
      margin-top: 4px;
    }}
    .riskCascadeChips {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 6px;
    }}
    .riskCascadeChip {{
      display: inline-flex;
      align-items: center;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      background: #f8fafc;
      color: #334155;
      font-size: 10px;
      font-weight: 800;
      padding: 2px 6px;
      max-width: 100%;
      overflow-wrap: anywhere;
    }}
    .riskCascadeDetail {{
      border: 1px solid #dbeafe;
      border-radius: 8px;
      background: #ffffff;
      padding: 10px;
      min-height: 160px;
    }}
    .riskCascadeContextGrid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin: 8px 0 10px;
    }}
    .riskCascadeContextItem {{
      border: 1px solid #dbeafe;
      border-radius: 8px;
      background: #f8fafc;
      padding: 8px;
    }}
    .riskCascadeContextLabel {{
      color: #64748b;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      margin-bottom: 3px;
    }}
    .riskCascadeContextValue {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 850;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .riskCascadeTimeline {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
      margin: 8px 0 10px;
    }}
    .riskCascadeTimelineStep {{
      border: 1px solid #dbeafe;
      border-radius: 8px;
      background: #f8fafc;
      padding: 8px;
    }}
    .riskCascadeTimelineDay {{
      color: #2563eb;
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }}
    .riskCascadeTimelineLabel {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      margin: 3px 0;
    }}
    @media (max-width: 920px) {{
      .riskCascadeExplorerGrid {{
        grid-template-columns: 1fr;
      }}
    }}
    .riskDiagnosticList {{
      margin: 6px 0 12px;
      padding-left: 18px;
      color: #334155;
      font-size: 12px;
      line-height: 1.45;
    }}
    .riskDiagnosticList li {{
      margin: 4px 0;
    }}
    .riskGlobalDiagnosticContent .kpiFormulaTableWrap {{
      margin-bottom: 12px;
    }}
    .scenarioComparisonControls {{
      border: 1px solid #dbeafe;
      border-radius: 8px;
      background: #f8fafc;
      padding: 9px 10px;
      margin: 10px 0 12px;
    }}
    .scenarioComparisonActions {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .scenarioComparisonSelectionMeta {{
      color: #475569;
      font-size: 12px;
      font-weight: 800;
    }}
    .scenarioComparisonChecks {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 6px 10px;
    }}
    .scenarioComparisonCheck {{
      display: flex;
      align-items: center;
      gap: 7px;
      min-width: 0;
      color: #0f172a;
      font-size: 12px;
      font-weight: 800;
    }}
    .scenarioComparisonCheck span {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .scenarioComparisonCheck small {{
      color: #64748b;
      font-size: 10px;
      font-weight: 800;
      white-space: nowrap;
    }}
    .scenarioComparisonTable tr.scenarioCurrentRow td {{
      background: #fff7ed;
      color: #0f172a;
      font-weight: 800;
    }}
    .scenarioComparisonTable tr.scenarioComparisonHidden {{
      display: none;
    }}
    .scenarioComparisonContent .riskDiagnosticChart {{
      min-height: 320px;
    }}
    .riskDiagnosticChartGrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 8px 0 12px;
    }}
    .riskDiagnosticChart {{
      min-width: 0;
      height: 300px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
    }}
    .riskScenarioNativeDetails {{
      margin-top: 10px;
      border: 1px dashed #cbd5e1;
      border-radius: 8px;
      background: #f8fafc;
      padding: 8px 10px;
    }}
    .riskScenarioNativeDetails summary {{
      cursor: pointer;
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
    }}
    .riskScenarioNativeDetails[open] summary {{
      margin-bottom: 8px;
    }}
    @media (max-width: 760px) {{
      .riskSummaryHeader {{
        grid-template-columns: 1fr;
      }}
      .riskSummaryGrid {{
        grid-template-columns: 1fr;
      }}
      .riskDiagnosticChartGrid {{
        grid-template-columns: 1fr;
      }}
    }}
    #factoryHoverPanel {{
      position: fixed;
      right: 16px;
      top: 88px;
      width: min(900px, calc(100vw - 32px));
      max-height: calc(100vh - 110px);
      background: rgba(255,255,255,0.98);
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
      z-index: 20;
      box-sizing: border-box;
      overflow-x: hidden;
      overflow-y: auto;
      display: none;
      padding: 10px;
    }}
    #factoryHoverPanel.visible {{
      display: block;
    }}
    #factoryHoverPanel.hoverPreview {{
      pointer-events: auto;
    }}
    .panelHeader {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }}
    #factoryHoverTitle {{
      font-size: 13px;
      font-weight: 700;
      margin: 0;
      color: #0f172a;
      min-width: 0;
      overflow-wrap: anywhere;
    }}
    .panelHeaderRight {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }}
    .panelStatePill {{
      display: none;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      background: #e2e8f0;
      color: #0f172a;
    }}
    .panelStatePill.visible {{
      display: inline-flex;
    }}
    .panelClearBtn {{
      display: none;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 600;
      padding: 5px 8px;
      border-radius: 8px;
      cursor: pointer;
    }}
    .panelClearBtn.visible {{
      display: inline-flex;
    }}
    .factoryHoverGrid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
      min-width: 0;
      max-width: 100%;
    }}
    .businessSummary {{
      border: 1px solid #cbd5e1;
      border-left-width: 6px;
      border-radius: 10px;
      background: #ffffff;
      padding: 10px 12px;
      box-shadow: 0 1px 0 rgba(15, 23, 42, 0.04);
    }}
    .businessSummary.businessOk {{
      border-left-color: #16a34a;
      background: #f0fdf4;
    }}
    .businessSummary.businessWarn {{
      border-left-color: #d97706;
      background: #fffbeb;
    }}
    .businessSummary.businessAlert {{
      border-left-color: #dc2626;
      background: #fef2f2;
    }}
    .businessSummary.businessInfo {{
      border-left-color: #2563eb;
      background: #eff6ff;
    }}
    .businessSummaryTop {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      margin-bottom: 4px;
    }}
    .businessSummaryPill {{
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 3px 8px;
      background: rgba(15, 23, 42, 0.08);
      color: #0f172a;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }}
    .businessSummaryTitle {{
      min-width: 0;
      color: #0f172a;
      font-size: 13px;
      font-weight: 900;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .businessSummaryText {{
      color: #334155;
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .panelMeta {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #f8fafc;
      padding: 10px 12px;
    }}
    .panelMetaTitle {{
      font-size: 11px;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    .panelMetaGrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px 12px;
      min-width: 0;
    }}
    .panelMetaRow {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      color: #334155;
      min-width: 0;
    }}
    .panelMetaLabel {{
      color: #64748b;
      min-width: 0;
    }}
    .panelMetaValue {{
      font-weight: 600;
      color: #0f172a;
      text-align: right;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      min-width: 0;
    }}
    .panelMetaRow.multiline {{
      grid-column: 1 / span 2;
      display: block;
      min-width: 0;
    }}
    .panelMetaRow.multiline .panelMetaLabel {{
      margin-bottom: 4px;
      color: #0f172a;
      font-weight: 700;
    }}
    .panelMetaRow.multiline .panelMetaValue {{
      display: block;
      max-width: 100%;
      overflow-x: scroll;
      overflow-y: hidden;
      padding-bottom: 4px;
      text-align: left;
      white-space: pre;
      overflow-wrap: normal;
      scrollbar-gutter: stable both-edges;
      font-family: Consolas, "Courier New", monospace;
      font-weight: 500;
    }}
    .panelDetailControls {{
      display: none;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      border: 1px dashed #cbd5e1;
      border-radius: 10px;
      background: #f8fafc;
      padding: 8px 10px;
      min-width: 0;
    }}
    .panelDetailControls.visible {{
      display: flex;
    }}
    .panelDetailHint {{
      color: #475569;
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .panelAdvancedBlock.isCollapsed {{
      display: none !important;
    }}
    .factoryPlotBlock {{
      display: block;
      min-width: 0;
      max-width: 100%;
    }}
    .factoryPlotLabel {{
      font-size: 11px;
      color: #334155;
      margin: 0 0 4px 2px;
      font-weight: 600;
    }}
    .panelSubTabs {{
      display: none;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0 0 8px 2px;
    }}
    .panelSubTab {{
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 999px;
      cursor: pointer;
    }}
    .panelSubTab.active {{
      background: #dbeafe;
      border-color: #93c5fd;
      color: #1d4ed8;
    }}
    .panelSubTab.secondary {{
      font-size: 10.5px;
      background: #f8fafc;
    }}
    .panelSubTab.secondary.active {{
      background: #ecfeff;
      border-color: #67e8f9;
      color: #0e7490;
    }}
    .panelSubTabSeparator {{
      flex-basis: 100%;
      height: 0;
    }}
    .factoryPlotHelp {{
      display: none;
      font-size: 11px;
      color: #475569;
      margin: 0 0 8px 2px;
      line-height: 1.45;
    }}
    .tableBtn {{
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #0f172a;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 10px;
      border-radius: 999px;
      cursor: pointer;
    }}
    .tableBtn.active {{
      background: #0f172a;
      border-color: #0f172a;
      color: #ffffff;
    }}
    .tableModal {{
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.45);
      z-index: 30;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .tableModal.visible {{
      display: flex;
    }}
    .tableModalCard {{
      width: min(1280px, calc(100vw - 48px));
      max-height: calc(100vh - 48px);
      overflow: hidden;
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 20px 50px rgba(15, 23, 42, 0.28);
      border: 1px solid #cbd5e1;
      display: flex;
      flex-direction: column;
    }}
    .tableModalHeader {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }}
    .tableModalTitle {{
      font-size: 14px;
      font-weight: 700;
      color: #0f172a;
    }}
    .tableModalMeta {{
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
    }}
    .tableModalBody {{
      overflow: auto;
      padding: 0;
    }}
    .sensitivityTop3ModalBody,
    .monteCarloModalBody {{
      background: #f8fafc;
    }}
    .monteCarloTabBar {{
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 14px;
      border-bottom: 1px solid #e2e8f0;
      background: #ffffff;
    }}
    .monteCarloTabHint {{
      color: #475569;
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .monteCarloPane {{
      min-width: 0;
      padding: 12px 14px;
    }}
    .monteCarloPane.hidden {{
      display: none;
    }}
    #sensitivityTop3Content .factoryHtmlPanelContent,
    #monteCarloContent .factoryHtmlPanelContent {{
      height: auto;
      min-height: 0;
      background: transparent;
    }}
    #sensitivityTop3Content .dataSummaryScroll,
    #monteCarloContent .dataSummaryScroll {{
      overflow: visible;
    }}
    .materialTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .materialTable th,
    .materialTable td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    .materialTable thead th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      z-index: 1;
      color: #334155;
    }}
    .materialTable .num {{
      text-align: right;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}
    .modelEquationPanel {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      background: #ffffff;
    }}
    .modelEquationIntro {{
      margin: 0;
      padding: 12px 14px;
      border: 1px solid #dbeafe;
      border-radius: 12px;
      background: #eff6ff;
      color: #1e3a8a;
      font-size: 13px;
      line-height: 1.45;
    }}
    .modelEquationSection {{
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      overflow: hidden;
      background: #ffffff;
    }}
    .modelEquationSection h3 {{
      margin: 0;
      padding: 10px 12px;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      color: #0f172a;
      font-size: 13px;
    }}
    .modelEquationTableWrap {{
      overflow-x: auto;
    }}
    .modelEquationTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .modelEquationTable th,
    .modelEquationTable td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    .modelEquationTable th {{
      background: #f8fafc;
      color: #334155;
      font-weight: 800;
    }}
    .modelEquationTable td:first-child {{
      width: 160px;
      color: #0f172a;
      font-weight: 700;
    }}
    .modelEquationTable code {{
      color: #0f172a;
      font-family: Consolas, "Courier New", monospace;
      white-space: nowrap;
    }}
    .scopeBadge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 8px;
      background: #e2e8f0;
      color: #0f172a;
      font-size: 11px;
      font-weight: 700;
    }}
    .scopeBadge.scopeFinal {{
      background: #dbeafe;
      color: #1d4ed8;
    }}
    .scopeBadge.scopeIntermediate {{
      background: #dcfce7;
      color: #166534;
    }}
    .factoryPlot {{
      width: 100%;
      height: 380px;
      object-fit: contain;
      object-position: center top;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
    }}
    .factoryPlotOutgoing {{
      height: 320px;
    }}
    .factoryPlotThird {{
      height: 320px;
    }}
    .factoryPlotFourth {{
      height: 320px;
    }}
    .factoryPlotFigure {{
      display: none;
      width: 100%;
      max-width: 100%;
      height: 380px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      box-sizing: border-box;
      min-width: 0;
    }}
    .factoryPlotFigure .plot-container,
    .factoryPlotFigure .svg-container {{
      width: 100% !important;
      max-width: 100% !important;
    }}
    .factoryPlotInner {{
      width: 100%;
      height: 100%;
    }}
    .factoryPlotFigure.factoryPlotOutgoing {{
      height: 320px;
    }}
    .factoryPlotFigure.factoryPlotThird {{
      height: 320px;
    }}
    .factoryPlotFigure.factoryPlotFourth {{
      height: 320px;
    }}
    .factoryPlotFigure.factoryHtmlPanel {{
      overflow: hidden;
    }}
    .factoryPlotFigure.factoryTallHtmlPanel {{
      height: auto;
      min-height: 320px;
      overflow: visible;
    }}
    .factoryPlotFigure.factoryTallHtmlPanel .factoryHtmlPanelContent {{
      height: auto;
      min-height: 320px;
      max-width: 100%;
    }}
    .factoryPlotFigure.factoryOrderLedgerPanel {{
      height: auto;
      min-height: 320px;
      overflow: hidden;
    }}
    .factoryPlotFigure.factoryOrderLedgerPanel .factoryHtmlPanelContent {{
      height: auto;
      min-height: 320px;
      max-width: 100%;
    }}
    .jsonPanelContent {{
      min-height: 100%;
    }}
    .jsonPanelPreWrap {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 0 12px 12px;
      scrollbar-gutter: stable both-edges;
    }}
    .jsonPanelPre {{
      margin: 0;
      padding: 10px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #f8fafc;
      color: #0f172a;
      font-family: Consolas, "Courier New", monospace;
      font-size: 11px;
      line-height: 1.45;
      white-space: pre;
    }}
    .dataSummaryPanelContent {{
      min-height: 100%;
      background: #ffffff;
    }}
    .dataSummaryScroll {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 0 12px 12px;
      scrollbar-gutter: stable both-edges;
    }}
    .dataSummarySection {{
      margin-bottom: 12px;
    }}
    .dataSummarySectionTitle {{
      font-size: 12px;
      font-weight: 800;
      color: #0f172a;
      margin: 4px 0 6px;
    }}
    details.dataSummarySection {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 8px 10px 10px;
      background: #ffffff;
    }}
    details.dataSummarySection > summary.dataSummarySectionTitle {{
      cursor: pointer;
      list-style-position: inside;
      margin: 0;
    }}
    details.dataSummarySection[open] > summary.dataSummarySectionTitle {{
      margin-bottom: 8px;
      padding-bottom: 7px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .dataKvGrid {{
      display: grid;
      grid-template-columns: minmax(120px, 0.42fr) 1fr;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      overflow: hidden;
      background: #ffffff;
      font-size: 11px;
    }}
    .dataKvLabel,
    .dataKvValue {{
      padding: 7px 9px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .dataKvLabel {{
      background: #f8fafc;
      color: #475569;
      font-weight: 800;
    }}
    .dataKvValue {{
      color: #0f172a;
      overflow-wrap: anywhere;
    }}
    .dataKvLabel:nth-last-child(2),
    .dataKvValue:last-child {{
      border-bottom: 0;
    }}
    .dataSummaryTableWrap {{
      max-width: 100%;
      overflow-x: auto;
      overflow-y: auto;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #ffffff;
      scrollbar-gutter: stable both-edges;
    }}
    .dataSummaryTable {{
      width: max-content;
      min-width: 1420px;
      border-collapse: collapse;
      font-size: 11px;
      table-layout: auto;
    }}
    .dataSummaryTable th,
    .dataSummaryTable td {{
      padding: 7px 8px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
      overflow-wrap: normal;
      word-break: normal;
    }}
    .dataSummaryTable th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      color: #334155;
      font-weight: 800;
      z-index: 1;
    }}
    .dataSummaryTable th:first-child,
    .dataSummaryTable td:first-child {{
      position: sticky;
      left: 0;
      min-width: 150px;
      max-width: 220px;
      white-space: normal;
      background: #ffffff;
      z-index: 2;
      box-shadow: 1px 0 0 #e2e8f0;
    }}
    .dataSummaryTable th:first-child {{
      background: #f8fafc;
      z-index: 3;
    }}
    .dataSummaryTable td:nth-child(3),
    .dataSummaryTable td:nth-child(4),
    .dataSummaryTable td:nth-child(5) {{
      min-width: 170px;
      max-width: 260px;
      white-space: normal;
      overflow-wrap: break-word;
    }}
    .dataSummaryTable tbody tr:last-child td {{
      border-bottom: 0;
    }}
    .dataEmptyState {{
      min-height: 80px;
      border: 1px dashed #cbd5e1;
      border-radius: 10px;
      background: #f8fafc;
    }}
    .decisionMatrix {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .decisionMatrixCell {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      background: #ffffff;
      padding: 9px 10px;
    }}
    .decisionMatrixCell.current {{
      box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.22);
      border-color: #93c5fd;
    }}
    .decisionMatrixCell.ok {{
      border-left-color: #16a34a;
    }}
    .decisionMatrixCell.watch {{
      border-left-color: #d97706;
    }}
    .decisionMatrixCell.alert {{
      border-left-color: #dc2626;
    }}
    .decisionMatrixCellTitle {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      line-height: 1.25;
      margin-bottom: 4px;
    }}
    .decisionMatrixCellText {{
      color: #334155;
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .decisionMatrixCellAction {{
      margin-top: 5px;
      color: #0f172a;
      font-size: 11px;
      font-weight: 800;
      line-height: 1.35;
    }}
    .sensitivityDashboard {{
      border: 1px solid #e2e8f0;
      border-left-width: 6px;
      border-radius: 12px;
      background: #ffffff;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .sensitivityHero {{
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(240px, 0.85fr);
      gap: 10px;
      align-items: stretch;
    }}
    .sensitivityHeroMain {{
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 5px;
    }}
    .sensitivityHeroTitle {{
      color: #0f172a;
      font-size: 16px;
      font-weight: 900;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .sensitivityHeroText {{
      color: #334155;
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .sensitivityHeroFacts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
    }}
    .sensitivityHeroFacts div {{
      min-width: 0;
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 9px;
      background: rgba(255, 255, 255, 0.7);
      padding: 7px 8px;
    }}
    .sensitivityHeroFacts span {{
      display: block;
      color: #64748b;
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      margin-bottom: 2px;
    }}
    .sensitivityHeroFacts b {{
      display: block;
      color: #0f172a;
      font-size: 11px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .sensitivityMetricGrid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .sensitivityMetricCard {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      background: #ffffff;
      padding: 8px;
    }}
    .sensitivityMetricLabel {{
      color: #64748b;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      margin-bottom: 3px;
    }}
    .sensitivityMetricValue {{
      color: #0f172a;
      font-size: 15px;
      font-weight: 900;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .sensitivityMetricNote {{
      color: #475569;
      font-size: 10px;
      line-height: 1.25;
      margin-top: 3px;
      overflow-wrap: anywhere;
    }}
    .sensitivityRecommendation {{
      border: 1px solid #dbeafe;
      border-radius: 10px;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .sensitivityCompareDashboard {{
      border: 1px solid #dbeafe;
      border-left: 6px solid #2563eb;
      border-radius: 12px;
      background: #f8fbff;
      padding: 12px 14px;
    }}
    .sensitivityCompareHeader {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(220px, 0.8fr);
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }}
    .sensitivityCompareEyebrow {{
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      color: #2563eb;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
    }}
    .sensitivityCompareHeading {{
      font-size: 15px;
      font-weight: 900;
      color: #0f172a;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .sensitivityCompareNote {{
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      background: rgba(255,255,255,0.82);
      color: #334155;
      font-size: 12px;
      line-height: 1.35;
      padding: 9px 10px;
    }}
    .sensitivityCompareGrid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .sensitivityCompareCard {{
      position: relative;
      overflow: hidden;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      background: #ffffff;
      padding: 12px;
      min-width: 0;
      box-shadow: 0 1px 0 rgba(15, 23, 42, 0.04);
    }}
    .sensitivityCompareAccent {{
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 5px;
    }}
    .sensitivityCompareTop {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      padding-left: 2px;
    }}
    .sensitivityCompareRank {{
      font-size: 11px;
      font-weight: 900;
      color: #64748b;
    }}
    .sensitivityCompareFamily {{
      font-size: 11px;
      font-weight: 900;
      color: #475569;
      text-transform: uppercase;
      margin-bottom: 4px;
      padding-left: 2px;
    }}
    .sensitivityCompareContext {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 6px;
      padding-left: 2px;
      overflow-wrap: anywhere;
    }}
    .sensitivityCompareTitle {{
      font-size: 14px;
      line-height: 1.25;
      font-weight: 900;
      color: #0f172a;
      overflow-wrap: anywhere;
      margin-bottom: 8px;
      padding-left: 2px;
    }}
    .sensitivityCompareText {{
      color: #334155;
      font-size: 12px;
      line-height: 1.35;
      margin-bottom: 10px;
      padding-left: 2px;
    }}
    .sensitivityCompareKpis {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }}
    .sensitivityCompareKpis div {{
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #f8fafc;
      padding: 7px 8px;
      min-width: 0;
    }}
    .sensitivityCompareKpis span {{
      display: block;
      font-size: 9px;
      color: #64748b;
      font-weight: 900;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }}
    .sensitivityCompareKpis b {{
      display: block;
      margin-top: 2px;
      font-size: 13px;
      color: #0f172a;
      overflow-wrap: anywhere;
    }}
    .sensitivityCompareReason {{
      margin-top: 9px;
      border-radius: 8px;
      background: #eff6ff;
      color: #1e3a8a;
      font-size: 12px;
      line-height: 1.35;
      padding: 8px 9px;
      overflow-wrap: anywhere;
    }}
    .uncertaintyDashboard {{
      margin: 8px 16px 10px;
      border: 1px solid #e2e8f0;
      border-left-width: 6px;
      border-radius: 12px;
      background: #ffffff;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .panelMeta .uncertaintyDashboard {{
      margin: 0;
    }}
    .panelMetaUncertainty {{
      grid-column: 1 / span 2;
      min-width: 0;
    }}
    .uncertaintyHero {{
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(220px, 0.85fr);
      gap: 10px;
      align-items: stretch;
    }}
    .uncertaintyHeroTitle {{
      color: #0f172a;
      font-size: 15px;
      font-weight: 900;
      line-height: 1.15;
      overflow-wrap: anywhere;
      margin-top: 3px;
    }}
    .uncertaintyHeroText {{
      color: #334155;
      font-size: 12px;
      line-height: 1.35;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }}
    .uncertaintyHeroFacts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
    }}
    .uncertaintyHeroFacts div {{
      min-width: 0;
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 9px;
      background: rgba(255, 255, 255, 0.72);
      padding: 7px 8px;
    }}
    .uncertaintyHeroFacts span {{
      display: block;
      color: #64748b;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      margin-bottom: 2px;
    }}
    .uncertaintyHeroFacts b {{
      display: block;
      color: #0f172a;
      font-size: 11px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .uncertaintyCardGrid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .uncertaintyCard {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      background: #ffffff;
      padding: 8px;
    }}
    .uncertaintyCardLabel {{
      color: #64748b;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      margin-bottom: 3px;
    }}
    .uncertaintyCardValue {{
      color: #0f172a;
      font-size: 14px;
      font-weight: 900;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }}
    .uncertaintyCardNote {{
      color: #475569;
      font-size: 10px;
      line-height: 1.25;
      margin-top: 3px;
      overflow-wrap: anywhere;
    }}
    .riskSummaryDashboard {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 6px;
      border-radius: 12px;
      background: #ffffff;
      padding: 10px;
    }}
    .riskSummaryHero {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(260px, 0.95fr);
      gap: 10px;
      align-items: stretch;
    }}
    .riskSummaryMain {{
      min-width: 0;
    }}
    .riskSummaryTitle {{
      color: #0f172a;
      font-size: 15px;
      font-weight: 900;
      line-height: 1.15;
      overflow-wrap: anywhere;
      margin-top: 3px;
    }}
    .riskSummaryText {{
      color: #334155;
      font-size: 12px;
      line-height: 1.35;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .riskSummaryFacts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
    }}
    .riskSummaryFacts div {{
      min-width: 0;
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 9px;
      background: rgba(255, 255, 255, 0.72);
      padding: 7px 8px;
    }}
    .riskSummaryFacts span {{
      display: block;
      color: #64748b;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      margin-bottom: 2px;
    }}
    .riskSummaryFacts b {{
      display: block;
      color: #0f172a;
      font-size: 11px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .riskTooltipHost {{
      position: relative;
      cursor: help;
      outline: none;
    }}
    .riskTooltipPortal {{
      position: fixed;
      left: 0;
      top: 0;
      width: min(420px, calc(100vw - 20px));
      max-width: calc(100vw - 20px);
      white-space: pre-line;
      background: #0f172a;
      color: #ffffff;
      border-radius: 10px;
      padding: 11px 12px;
      font-size: 11px;
      line-height: 1.35;
      font-weight: 650;
      text-transform: none;
      letter-spacing: 0;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.22);
      opacity: 0;
      pointer-events: none;
      transform: translateY(4px);
      transition: opacity 120ms ease, transform 120ms ease;
      z-index: 2147483000;
    }}
    .riskTooltipPortal.visible {{
      opacity: 1;
      transform: translateY(0);
    }}
    .riskIndicatorStack {{
      display: grid;
      gap: 8px;
    }}
    .riskDriverGrid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .riskDriverCard {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      background: #ffffff;
      padding: 9px 10px;
    }}
    .riskDriverRank {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 7px;
      background: rgba(15, 23, 42, 0.08);
      color: #334155;
      font-size: 10px;
      font-weight: 900;
      margin-bottom: 5px;
    }}
    .riskDriverTitle {{
      color: #0f172a;
      font-size: 13px;
      font-weight: 900;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .riskDriverValue {{
      color: #0f172a;
      font-size: 20px;
      font-weight: 900;
      line-height: 1.05;
      margin-top: 4px;
    }}
    .riskDriverMeta {{
      color: #334155;
      font-size: 11px;
      font-weight: 800;
      line-height: 1.3;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }}
    .riskDriverNote {{
      color: #475569;
      font-size: 11px;
      line-height: 1.3;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .riskMethodStack {{
      display: grid;
      gap: 10px;
      margin-top: 8px;
    }}
    .riskMethodNote {{
      border: 1px solid #dbeafe;
      border-radius: 10px;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .riskMethodSubTitle {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      line-height: 1.25;
      margin-top: 2px;
      overflow-wrap: anywhere;
    }}
    .riskMethodDetails > summary {{
      font-weight: 900;
    }}
    .riskSignalFrame {{
      min-width: 0;
      border: 1px solid #fed7aa;
      border-left: 6px solid #d97706;
      border-radius: 14px;
      background: #fff7ed;
      padding: 12px;
      display: grid;
      gap: 10px;
    }}
    .riskSignalHero {{
      min-width: 0;
    }}
    .riskSignalCompositionHead {{
      display: grid;
      gap: 2px;
      padding-top: 2px;
    }}
    .riskSignalCompositionTitle {{
      color: #7c2d12;
      font-size: 12px;
      font-weight: 900;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .riskSignalCompositionText {{
      color: #475569;
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .riskIndicatorSection {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: rgba(248, 250, 252, 0.72);
      padding: 9px;
      display: grid;
      gap: 8px;
    }}
    .riskIndicatorSectionHead {{
      display: grid;
      gap: 2px;
    }}
    .riskIndicatorSectionTitle {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .riskIndicatorSectionNote {{
      color: #475569;
      font-size: 11px;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }}
    .riskIndicatorSection .riskExplanationGrid {{
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}
    .riskExplanationGrid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .riskExplanationCard {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      background: #ffffff;
      padding: 9px 10px;
    }}
    .riskExplanationLabel {{
      color: #475569;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .riskExplanationValue {{
      color: #0f172a;
      font-size: 17px;
      font-weight: 900;
      line-height: 1.1;
      margin-top: 5px;
    }}
    .riskExplanationFormula {{
      color: #0f172a;
      font-size: 11px;
      font-weight: 800;
      line-height: 1.3;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .riskExplanationBreakdown {{
      display: grid;
      gap: 4px;
      margin-top: 7px;
    }}
    .riskExplanationBreakdown div {{
      min-width: 0;
      border: 1px solid rgba(148, 163, 184, 0.28);
      border-radius: 7px;
      background: rgba(255, 255, 255, 0.62);
      padding: 5px 6px;
    }}
    .riskExplanationBreakdown span {{
      display: block;
      color: #64748b;
      font-size: 9px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      margin-bottom: 2px;
    }}
    .riskExplanationBreakdown b {{
      display: block;
      color: #0f172a;
      font-size: 10px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .riskExplanationNote {{
      color: #475569;
      font-size: 11px;
      line-height: 1.3;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .riskComponentGrid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .riskComponentCard {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      background: #ffffff;
      padding: 9px 10px;
    }}
    .riskComponentTop {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
    }}
    .riskComponentLabel {{
      color: #475569;
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .riskComponentWeight {{
      color: #64748b;
      font-size: 10px;
      font-weight: 800;
      white-space: nowrap;
    }}
    .riskComponentValue {{
      color: #0f172a;
      font-size: 18px;
      font-weight: 900;
      line-height: 1.1;
      margin-top: 5px;
    }}
    .riskComponentBarTrack {{
      height: 5px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.10);
      margin-top: 6px;
      overflow: hidden;
    }}
    .riskComponentBar {{
      height: 100%;
      border-radius: 999px;
      background: currentColor;
      opacity: 0.75;
    }}
    .riskComponentContribution {{
      color: #0f172a;
      font-size: 10px;
      font-weight: 800;
      line-height: 1.25;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .riskComponentNote {{
      color: #334155;
      font-size: 11px;
      line-height: 1.3;
      margin-top: 6px;
      overflow-wrap: anywhere;
    }}
    .riskDetailBlock {{
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }}
    .riskDetailTitle {{
      color: #334155;
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }}
    .uncertaintyEnvelope,
    .uncertaintyQualityGrid {{
      margin: 0 16px 10px;
    }}
    .uncertaintyEnvelope .kpiFormulaTable {{
      width: 100%;
    }}
    .uncertaintyQualityGrid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .uncertaintyQualityCell {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #ffffff;
      padding: 8px;
    }}
    .uncertaintyQualityTitle {{
      color: #0f172a;
      font-size: 11px;
      font-weight: 900;
      margin-bottom: 3px;
    }}
    .uncertaintyQualityValue {{
      color: #334155;
      font-size: 11px;
      font-weight: 800;
      margin-bottom: 3px;
    }}
    .uncertaintyQualityNote {{
      color: #64748b;
      font-size: 10px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .sensitivityStatusBanner {{
      border: 1px solid #e2e8f0;
      border-left-width: 6px;
      border-radius: 10px;
      background: #ffffff;
      padding: 10px 12px;
      line-height: 1.35;
    }}
    .sensitivityStatus-robust {{
      border-left-color: #16a34a;
      background: #f0fdf4;
    }}
    .sensitivityStatus-watch {{
      border-left-color: #d97706;
      background: #fffbeb;
    }}
    .sensitivityStatus-sensitive {{
      border-left-color: #dc2626;
      background: #fef2f2;
    }}
    .sensitivityStatus-not_local {{
      border-left-color: #64748b;
      background: #f8fafc;
    }}
    .sensitivityStatus-robust .riskComponentBar {{
      background: #16a34a;
    }}
    .sensitivityStatus-watch .riskComponentBar {{
      background: #d97706;
    }}
    .sensitivityStatus-sensitive .riskComponentBar {{
      background: #dc2626;
    }}
    .sensitivityStatus-not_local .riskComponentBar {{
      background: #64748b;
    }}
    .riskPrimaryCard {{
      border-left-color: #2563eb !important;
      border-color: #bfdbfe !important;
      background: rgba(255, 255, 255, 0.82) !important;
      box-shadow: 0 1px 0 rgba(37, 99, 235, 0.12);
      padding: 12px 14px;
    }}
    .riskPrimaryCard .riskExplanationLabel {{
      color: #1d4ed8;
      font-size: 11px;
    }}
    .riskPrimaryCard .riskExplanationValue {{
      font-size: 28px;
      line-height: 1;
      margin-top: 7px;
    }}
    .riskPrimaryCard .riskExplanationFormula {{
      color: #64748b;
      font-size: 11px;
      font-weight: 800;
      margin-top: 5px;
    }}
    .riskPrimaryCard .riskExplanationBreakdown div {{
      border-color: rgba(96, 165, 250, 0.38);
      background: rgba(255, 255, 255, 0.74);
    }}
    .sensitivityStatusPill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 8px;
      background: rgba(15, 23, 42, 0.08);
      color: #0f172a;
      font-size: 11px;
      font-weight: 800;
      margin-bottom: 5px;
    }}
    .sensitivityStatusTitle {{
      color: #0f172a;
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 3px;
    }}
    .sensitivityStatusText {{
      color: #334155;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .sensitivityMatrix {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
    }}
    .sensitivityMatrixCell {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-left-width: 5px;
      border-radius: 10px;
      padding: 8px;
      background: #ffffff;
    }}
    .sensitivityMatrixLabel {{
      color: #0f172a;
      font-size: 11px;
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .sensitivityMatrixStatus {{
      color: #334155;
      font-size: 11px;
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .sensitivityMatrixBand,
    .sensitivityMatrixDetail {{
      color: #475569;
      font-size: 10px;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }}
    .sensitivityTornado {{
      display: flex;
      flex-direction: column;
      gap: 9px;
    }}
    .sensitivityTornadoRow {{
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #ffffff;
      padding: 8px;
    }}
    .sensitivityTornadoHead {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: flex-start;
      margin-bottom: 6px;
    }}
    .sensitivityTornadoLabel {{
      min-width: 0;
      color: #0f172a;
      font-size: 11px;
      font-weight: 900;
      overflow-wrap: anywhere;
    }}
    .sensitivityTornadoMeta {{
      flex: 0 0 auto;
      border: 1px solid rgba(15, 23, 42, 0.08);
      border-radius: 999px;
      padding: 2px 7px;
      color: #334155;
      font-size: 10px;
      font-weight: 800;
      white-space: nowrap;
    }}
    .sensitivityTornadoTrack {{
      width: 100%;
      height: 9px;
      border-radius: 999px;
      background: #e2e8f0;
      overflow: hidden;
    }}
    .sensitivityTornadoBar {{
      height: 100%;
      border-radius: 999px;
    }}
    .sensitivityTornadoFoot {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 5px;
      color: #475569;
      font-size: 10px;
      line-height: 1.25;
    }}
    .sensitivityDetails {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #ffffff;
      margin-bottom: 8px;
      overflow: hidden;
    }}
    .sensitivityDetails summary {{
      cursor: pointer;
      padding: 9px 10px;
      background: #f8fafc;
      color: #0f172a;
      font-size: 12px;
      font-weight: 900;
      user-select: none;
    }}
    .sensitivityDetails > .dataSummaryTableWrap,
    .sensitivityDetails > .dataKvGrid {{
      border: 0;
      border-radius: 0;
    }}
    @media (max-width: 820px) {{
      .sensitivityHero {{
        grid-template-columns: minmax(0, 1fr);
      }}
      .sensitivityMetricGrid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .sensitivityCompareHeader {{
        grid-template-columns: minmax(0, 1fr);
      }}
      .sensitivityCompareGrid {{
        grid-template-columns: minmax(0, 1fr);
      }}
      .uncertaintyHero,
      .riskSummaryHero,
      .uncertaintyCardGrid,
      .riskDriverGrid,
      .riskExplanationGrid,
      .riskComponentGrid,
      .uncertaintyQualityGrid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .sensitivityMatrix {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    .factoryPlotFigure.factoryKpiTreePanel {{
      height: auto;
      min-height: 680px;
      overflow: visible;
      border: 0;
      background: transparent;
    }}
    .kpiTreePanel {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 660px;
      padding: 10px;
      overflow: visible;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
    }}
    .kpiTreeHeader {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 8px;
    }}
    .kpiTreeTitle {{
      font-size: 13px;
      font-weight: 800;
      color: #0f172a;
    }}
    .kpiTreeSubtitle {{
      font-size: 11px;
      color: #64748b;
      margin-top: 2px;
    }}
    .kpiTreeControls {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
      color: #475569;
      font-size: 11px;
      font-weight: 700;
    }}
    .kpiTreeSmoothBtn {{
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 700;
      padding: 5px 9px;
      cursor: pointer;
    }}
    .kpiTreeSmoothBtn.active {{
      background: #dbeafe;
      border-color: #93c5fd;
      color: #1d4ed8;
    }}
    .kpiTreeControlGroup {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-left: 8px;
    }}
    .kpiTreeViewTabs {{
      display: inline-flex;
      align-self: flex-start;
      gap: 6px;
      padding: 3px;
      border: 1px solid #dbe4ef;
      border-radius: 999px;
      background: #f8fafc;
    }}
    .kpiTreeViewBtn {{
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: #334155;
      font-size: 11px;
      font-weight: 800;
      padding: 6px 12px;
      cursor: pointer;
    }}
    .kpiTreeViewBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    .kpiTreeView {{
      display: none;
    }}
    .kpiTreeView.active {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .kpiTreeCards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .kpiTreeCard {{
      border: 1px solid #dbe4ef;
      border-radius: 12px;
      padding: 9px 10px;
      background: #f8fafc;
      cursor: pointer;
      text-align: left;
    }}
    .kpiTreeCard.active {{
      border-color: #2563eb;
      background: #eff6ff;
      box-shadow: inset 0 0 0 1px #bfdbfe;
    }}
    .kpiTreeCardTitle {{
      font-size: 12px;
      font-weight: 800;
      color: #0f172a;
    }}
    .kpiTreeCardObjective {{
      margin-top: 4px;
      color: #64748b;
      font-size: 10.5px;
      line-height: 1.25;
    }}
    .kpiTreeCardMeta {{
      margin-top: 6px;
      color: #0f172a;
      font-size: 10.5px;
      font-weight: 800;
      line-height: 1.25;
    }}
    .kpiTreeChart {{
      min-height: 230px;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: #ffffff;
    }}
    .kpiTreeEmptyChart {{
      min-height: 230px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 18px;
      color: #64748b;
      font-size: 12px;
      font-weight: 700;
      text-align: center;
    }}
    .kpiTreeDetail {{
      display: grid;
      grid-template-columns: 0.9fr 1.7fr;
      gap: 10px;
      min-height: 295px;
      overflow: visible;
    }}
    .kpiTreeSummary {{
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: #f8fafc;
      padding: 10px;
      overflow: auto;
    }}
    .kpiTreeSummaryRow {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 7px 0;
      border-bottom: 1px solid #e2e8f0;
      font-size: 11px;
    }}
    .kpiTreeSummaryRow:last-child {{
      border-bottom: none;
    }}
    .kpiTreeSummaryLabel {{
      color: #64748b;
      font-weight: 600;
    }}
    .kpiTreeSummaryValue {{
      color: #0f172a;
      font-weight: 800;
      text-align: right;
    }}
    .kpiPhysicsGrid {{
      display: grid;
      grid-template-columns: 0.8fr 1.2fr;
      gap: 10px;
    }}
    .kpiPhysicsStack {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .kpiFormulaIntro {{
      color: #475569;
      font-size: 12px;
      line-height: 1.45;
      padding: 2px 4px;
    }}
    .kpiFormulaTableWrap {{
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      overflow: auto;
      background: #ffffff;
      max-height: 560px;
    }}
    .kpiFormulaTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
    }}
    .kpiFormulaTable th,
    .kpiFormulaTable td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    .kpiFormulaTable thead th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #334155;
      font-weight: 800;
    }}
    .kpiFormulaTable td:nth-child(4) {{
      font-family: Consolas, "Courier New", monospace;
      color: #0f172a;
    }}
    .kpiFormulaTerms {{
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px dashed #cbd5e1;
      color: #475569;
      font-family: inherit;
      line-height: 1.35;
    }}
    .kpiFormulaTermsLabel {{
      color: #0f172a;
      font-weight: 800;
    }}
    .kpiFormulaFamily {{
      font-weight: 800;
      color: #0f172a;
      white-space: nowrap;
    }}
    .kpiFormulaLevel {{
      display: inline-flex;
      border-radius: 999px;
      padding: 3px 7px;
      background: #e2e8f0;
      color: #334155;
      font-weight: 800;
      white-space: nowrap;
    }}
    .factoryPlotFigure.factoryFigureStackContainer {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      height: auto;
      border: 0;
      background: transparent;
      overflow: visible;
    }}
    .factoryFigureStackItem {{
      width: 100%;
      height: 360px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
    }}
    .factoryHtmlPanelContent {{
      display: flex;
      flex-direction: column;
      height: 100%;
      width: 100%;
      min-height: 0;
      min-width: 0;
      background: #ffffff;
    }}
    .panelEmptyState {{
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      padding: 16px;
      color: #475569;
      font-size: 12px;
      text-align: center;
    }}
    .orderLedgerMetaBar {{
      padding: 10px 12px 8px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
      color: #475569;
      font-size: 11px;
      font-weight: 600;
      flex: 0 0 auto;
    }}
    .orderLedgerFrame {{
      flex: 0 0 auto;
      min-width: 0;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      border-top: 1px solid #e2e8f0;
      background: #ffffff;
      overflow: hidden;
    }}
    .orderLedgerTableWrap {{
      min-height: 128px;
      max-height: 260px;
      min-width: 0;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      overflow-y: auto;
      overflow-x: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable both-edges;
    }}
    .orderLedgerTable {{
      width: 1805px;
      min-width: 1805px;
      border-collapse: collapse;
      font-size: 11px;
      table-layout: fixed;
    }}
    .orderLedgerWideTable {{
      min-width: 1805px;
      max-width: none;
    }}
    .orderLedgerTable th,
    .orderLedgerTable td {{
      padding: 7px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .orderLedgerTable thead th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #475569;
    }}
    .orderLedgerTable .num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .orderLedgerSliceSeparator td {{
      background: #f1f5f9;
      color: #334155;
      font-weight: 800;
      text-align: center;
      white-space: normal;
    }}
    .orderLedgerTextHeader {{
      padding: 16px 16px 8px;
      color: #1e293b;
      font-size: 14px;
      font-weight: 700;
      flex: 0 0 auto;
    }}
    .orderLedgerStatus {{
      padding: 0 16px 8px;
      color: #475569;
      font-size: 12px;
      flex: 0 0 auto;
      min-width: 0;
      max-width: 100%;
      box-sizing: border-box;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
      line-height: 1.35;
    }}
    .orderLedgerSectionTitle {{
      padding: 10px 16px 4px;
      color: #475569;
      font-size: 12px;
      font-weight: 600;
      flex: 0 0 auto;
    }}
    .orderLedgerTextWrap {{
      flex: 1 1 auto;
      min-height: 0;
      min-width: 0;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      overflow-y: scroll;
      overflow-x: auto;
      padding: 0 16px 16px;
      scrollbar-gutter: stable both-edges;
    }}
    .orderLedgerLines {{
      margin: 0;
      display: block;
      width: max-content;
      min-width: 100%;
      color: #475569;
      font-size: 11px;
      line-height: 1.55;
      white-space: pre;
      font-family: Consolas, "Courier New", monospace;
    }}
    #factoryHoverNoImage {{
      font-size: 12px;
      color: #475569;
      padding: 8px 2px;
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div class="title">{html.escape(title)}</div>
    <div class="meta" id="stats"></div>
    <div class="box">
      <div class="modeTabs">
        <button id="modeOps" class="modeBtn active" type="button" title="Question metier: que s'est-il passe dans le run nominal ?">Run nominal</button>
        <button id="modeSensitivity" class="modeBtn" type="button" title="Question metier: a partir de quel niveau un parametre fournisseur degrade-t-il la performance ?">Sensibilite</button>
        <button id="modeSimulatedRisk" class="modeBtn" type="button" title="Question metier: quels evenements ou scenarios de risque fournisseur degradent la supply ?">Risques simules</button>
        <button id="modeRisk" class="modeBtn" type="button" title="Question metier: quel fournisseur est critique et merite une action ou une surveillance ?">Criticite fournisseurs</button>
        <button id="modeUncertainty" class="modeBtn" type="button" title="Question metier: peut-on faire confiance a cette lecture ?">Incertitude</button>
        <button id="modeStructural" class="modeBtn" type="button" title="Question metier: ou le reseau est-il fragile par construction ?">Structurel</button>
        <button id="modeData" class="modeBtn debugOnly" type="button">Audit donnees</button>
        <button id="modeModel" class="modeBtn debugOnly" type="button">Regles modele</button>
        <button id="modeJson" class="modeBtn debugOnly{'' if DEBUG_PANEL_ENABLED else ' debugUnavailable'}" type="button">JSON</button>
      </div>
    </div>
    <div class="box">
      <label class="debugToggleLabel"><input type="checkbox" id="showDebugTools"> Debug</label>
    </div>
    <div class="box">
      <label id="showEdgesLabel"><input type="checkbox" id="showEdges" checked> <span id="showEdgesText">Afficher flux</span></label>
    </div>
    <div class="box">
      <label id="edgeInteractionLabel" title="Active le survol et le clic sur les flux affiches, dans tous les onglets.">
        <input type="checkbox" id="edgeInteraction"> <span id="edgeInteractionText">Flux cliquables</span>
      </label>
    </div>
    <div class="box">
      <button id="materialTableBtn" class="tableBtn" type="button">Tableau demande / stock / securite</button>
    </div>
    <div class="box">
      <button id="kpiTreeBtn" class="tableBtn" type="button" title="Question metier: comment les KPI se degradent-ils ensemble dans le temps ?">Arbres KPI</button>
    </div>
    <div class="box lotTraceControlsBox" id="lotTraceControlsBox">
      <label title="Selectionne un lot PF, PFI ou MP trace par la simulation.">
        Lot
        <select id="lotTraceSelect">
          <option value="">Aucun lot</option>
        </select>
      </label>
      <button id="lotTraceFocusBtn" class="tableBtn" type="button">Voir lot</button>
      <button id="lotTraceOpenBtn" class="tableBtn" type="button">Suivi de lots</button>
      <button id="lotTraceOrdersBtn" class="tableBtn" type="button" title="Affiche les ordres de production reportes par manque d'intrants.">Ordres reportes</button>
      <button id="lotTraceClearBtn" class="tableBtn" type="button">Effacer lot</button>
    </div>
    <div class="box sensitivityTop3Box" id="sensitivityTop3Box">
      <button id="sensitivityTop3Btn" class="tableBtn" type="button" title="Vue globale sans selectionner de noeud: parametres qui degradent le plus disponibilite produit, taux de replanification ou cout de stockage.">Priorites KPI</button>
    </div>
    <div class="box simulatedRiskControlsBox" id="simulatedRiskControlsBox">
      <span class="simulatedRiskModeLabel" title="Cette vue distingue les evenements injectes dans le run et les scenarios contrefactuels de risque fournisseur.">Vue</span>
      <span class="simulatedRiskViewValue" id="simulatedRiskViewValue">scenario injecte</span>
      <button id="simulatedRiskStateBtn" class="tableBtn" type="button" title="Affiche les evenements state-dependent ou scenarios effectivement injectes dans le run courant.">Scenario injecte</button>
      <button id="simulatedRiskGlobalBtn" class="tableBtn" type="button" title="Vue globale du scenario injecte/state-dependent: disponibilite produit, production, approvisionnement, couts et actions recommandees.">Bilan scenario injecte</button>
      <button id="supplierStressCampaignBtn" class="tableBtn" type="button" title="Compare des scenarios contrefactuels ou un fournisseur est degrade pour mesurer les impacts supply.">Stress tests fournisseurs</button>
      <button id="scenarioComparisonBtn" class="tableBtn" type="button" title="Compare les runs disponibles: nominal, risques injectes, state-dependent et mitigations.">Comparer scenarios</button>
      <label title="Selectionne une cascade dynamique pour surligner les noeuds et flux concernes.">
        Cascade
        <select id="simulatedRiskCascadeSelect">
          <option value="">Toutes</option>
        </select>
      </label>
      <label title="Filtre les cascades par impact observe.">
        Impact
        <select id="simulatedRiskCascadeStageFilter">
          <option value="all">Tous</option>
          <option value="service_client">Client atteint</option>
          <option value="production">Production reportee</option>
          <option value="cost">Surcout</option>
          <option value="local_absorbed">Absorbe localement</option>
          <option value="configured_only">Sans effet</option>
        </select>
      </label>
      <label title="Filtre les cascades par famille de risque.">
        Famille
        <select id="simulatedRiskCascadeFamilyFilter">
          <option value="all">Toutes</option>
          <option value="stock">Stock</option>
          <option value="lead">Delai</option>
          <option value="upstream">Appro amont</option>
          <option value="quality">Qualite</option>
          <option value="capacity">Capacite</option>
          <option value="availability">Disponibilite</option>
          <option value="cost">Cout</option>
        </select>
      </label>
      <button id="simulatedRiskCascadeClearBtn" class="tableBtn" type="button">Effacer cascade</button>
    </div>
    <div class="box uncertaintyMonteCarloBox" id="uncertaintyMonteCarloBox">
      <button id="monteCarloBtn" class="tableBtn" type="button" title="Vue globale sans selectionner de noeud: trajectoires Monte Carlo, enveloppes et distributions des KPI metier.">Courbes globales</button>
    </div>
    <div class="box uncertaintyControlsBox" id="uncertaintyControlsBox">
      <label title="Choisit la lecture generale de la carte Incertitude.">
        Vue carte
        <select id="uncertaintyDisplaySelect">
          <option value="dominant_type">Types dominants fournisseur</option>
          <option value="global_impact">Intensite globale</option>
          <option value="detail_type">Detail par type</option>
        </select>
      </label>
      <label id="uncertaintyDetailModeLabel" title="Disponible en vue Detail par type: colore l'intensite Monte Carlo d'une seule famille d'incertitude.">
        Type detail
        <select id="uncertaintyModeSelect">
          <option value="capacity">Capacite fournisseur</option>
          <option value="stock">Stock fournisseur</option>
          <option value="lead">Delai fournisseur</option>
          <option value="reliability">Fiabilite fournisseur</option>
          <option value="factory_capacity">Capacite usine (controle)</option>
        </select>
      </label>
      <span class="uncertaintyIntensityValue" id="uncertaintyIntensityValue">types dominants</span>
    </div>
    <div class="box debugOnly">
      <button id="modelEquationsBtn" class="tableBtn" type="button">Equations modele</button>
    </div>
    <div class="box timelineWindowBox" id="timelineWindowBox">
      <label>Debut
        <input type="range" id="yearStart" min="1" max="1" value="1" step="1">
      </label>
      <label>Fin
        <input type="range" id="yearEnd" min="1" max="1" value="1" step="1">
      </label>
      <div class="meta timelineWindowValue" id="yearWindowValue">annee 1 -> 1</div>
    </div>
    <div class="box" id="typeFilters"></div>
  </div>
  <div id="chart"></div>
  <div id="sensitivityLegend">
    <div class="sensitivityLegendTitle">Mode Sensibilite</div>
    <div class="sensitivityLegendRows">
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#d97706"></span>Capacite</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#0f766e"></span>Stock</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#7c3aed"></span>Delai</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#2563eb"></span>Fiabilite</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#be123c"></span>Appro amont</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#475569"></span>Scenario combine</span>
      <span class="sensitivityLegendItem">Taille du point: plus le noeud est sensible, plus il est grand.</span>
    </div>
  </div>
  <div id="simulatedRiskLegend">
    <div class="sensitivityLegendTitle">Mode Risques simules</div>
    <div class="sensitivityLegendRows">
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#d97706"></span>Capacite</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#0f766e"></span>Stock</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#7c3aed"></span>Delai</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#2563eb"></span>Fiabilite</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#be123c"></span>Appro amont</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#0891b2"></span>Qualite</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#475569"></span>Cout appro fournisseur</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#dc2626"></span>Impact disponibilite / delai fort</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#f97316"></span>Production ou flux retarde</span>
      <span class="sensitivityLegendItem" id="simulatedRiskLegendHint">Scenario injecte: couleur = impact reel observe quand disponible, sinon famille appliquee dominante. Edges colores = delais transport impactants.</span>
    </div>
    <div class="simulatedRiskGlobalSummary" id="simulatedRiskGlobalSummary"></div>
  </div>
  <div id="riskLegend">
    <div class="sensitivityLegendTitle">Mode Criticite fournisseurs</div>
    <div class="sensitivityLegendRows">
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#0f766e"></span>Faible</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#f59e0b"></span>Modere</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#d97706"></span>Eleve</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#dc2626"></span>Critique</span>
      <span class="sensitivityLegendItem">Criticite = menace fournisseur x importance supply x sensibilite ; couverture donnees = completude des champs utiles ; incertitude = marge de prudence du scoring.</span>
    </div>
  </div>
  <div id="uncertaintyLegend">
    <div class="sensitivityLegendTitle">Mode Incertitude</div>
    <div class="sensitivityLegendRows">
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#d97706"></span>Capacite fournisseur</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#0f766e"></span>Stock fournisseur</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#7c3aed"></span>Delai fournisseur</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#2563eb"></span>Fiabilite fournisseur</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#be123c"></span>Capacite usine (controle/recherche)</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#22c55e"></span>Impact faible</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#f59e0b"></span>Impact moyen</span>
      <span class="sensitivityLegendItem"><span class="sensitivityLegendDot" style="background:#dc2626"></span>Impact fort</span>
      <span class="sensitivityLegendItem">Lecture principale supplier-first: les fournisseurs sont prioritaires pour la decision. Les usines restent visibles comme controles modele et validation scientifique.</span>
    </div>
  </div>

  <div id="lotTracePanel" class="lotTracePanel">
    <div class="lotTracePanelHeader">
      <div>
        <div id="lotTracePanelTitle" class="lotTracePanelTitle">Lot</div>
        <div id="lotTracePanelMeta" class="lotTracePanelMeta"></div>
      </div>
      <button id="lotTracePanelCloseBtn" class="tableBtn" type="button">Fermer</button>
    </div>
    <div id="lotTracePanelBody" class="lotTracePanelBody"></div>
  </div>

  <div id="lotTraceModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Suivi de lots</div>
          <div id="lotTraceModalMeta" class="tableModalMeta">Ascendants et descendants du lot selectionne</div>
        </div>
        <button id="lotTraceModalCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody lotTraceModalBody">
        <div class="lotTraceModalControls">
          <label>
            Lot trace
            <select id="lotTraceModalSelect">
              <option value="">Aucun lot</option>
            </select>
          </label>
          <div class="lotTraceDirectionTabs">
            <button class="lotTraceDirectionBtn active" type="button" data-lot-trace-direction="both">Chaine complete</button>
            <button class="lotTraceDirectionBtn" type="button" data-lot-trace-direction="downstream">Aval</button>
            <button class="lotTraceDirectionBtn" type="button" data-lot-trace-direction="upstream">Amont</button>
          </div>
          <button id="lotTraceOrderDetailsBtn" class="tableBtn lotTraceOrderDetailsBtn hidden" type="button">Details</button>
        </div>
        <div id="lotTraceGraphWrap" class="lotTraceGraphWrap"></div>
        <div id="lotTraceModalTables"></div>
      </div>
    </div>
  </div>

  <div id="materialTableModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Tableau demande / stock / securite</div>
          <div id="materialTableMeta" class="tableModalMeta">{material_table_count} lignes</div>
        </div>
        <button id="materialTableCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody">
        <table class="materialTable">
          <thead>
            <tr>
              <th>Type</th>
              <th>Item</th>
              <th>Noeud</th>
              <th>Demande / besoin prévu</th>
              <th>Demande moy. / j</th>
              <th>Delai secu. j</th>
              <th>Stock equiv. delai</th>
              <th>Stock initial</th>
              <th>Livré / servi</th>
              <th>Consommé simulé</th>
              <th>Ecart vs besoin</th>
              <th>Unité</th>
              <th>Diagnostic</th>
            </tr>
          </thead>
          <tbody>{material_table_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div id="sensitivityTop3Modal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle" id="sensitivityTop3ModalTitle">Sensibilite - Priorites KPI</div>
          <div class="tableModalMeta" id="sensitivityTop3ModalMeta">Vue globale sans selectionner de noeud</div>
        </div>
        <button id="sensitivityTop3CloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody sensitivityTop3ModalBody">
        <div id="sensitivityTop3Content"></div>
      </div>
    </div>
  </div>

  <div id="simulatedRiskGlobalModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Risques simules - Bilan scenario</div>
          <div class="tableModalMeta">Vue globale du run courant</div>
        </div>
        <button id="simulatedRiskGlobalCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody sensitivityTop3ModalBody">
        <div id="simulatedRiskGlobalContent"></div>
      </div>
    </div>
  </div>

  <div id="scenarioComparisonModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Risques simules - Comparaison scenarios</div>
          <div class="tableModalMeta">Nominal, risques et mitigations disponibles</div>
        </div>
        <button id="scenarioComparisonCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody sensitivityTop3ModalBody">
        <div id="scenarioComparisonContent"></div>
      </div>
    </div>
  </div>

  <div id="monteCarloModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Incertitude - Monte Carlo</div>
          <div class="tableModalMeta">Courbes globales separees des donnees d'incertitude, priorites et details modele</div>
        </div>
        <button id="monteCarloCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody monteCarloModalBody">
        <div id="monteCarloContent"></div>
      </div>
    </div>
  </div>

  <div id="kpiTreeModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Arbres KPI supply</div>
          <div class="tableModalMeta">Vue globale du scénario courant</div>
        </div>
        <button id="kpiTreeCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody">
        <div id="globalKpiTreeFigure"></div>
      </div>
    </div>
  </div>

  <div id="modelEquationsModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Equations du modele complet</div>
          <div class="tableModalMeta">Vue globale: demande -> production -> BOM -> MRP -> fournisseur -> stock</div>
        </div>
        <button id="modelEquationsCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody">
        {global_model_equations_html}
      </div>
    </div>
  </div>

  <div id="factoryHoverPanel">
    <div class="panelHeader">
      <div id="factoryHoverTitle"></div>
      <div class="panelHeaderRight">
        <div id="factoryHoverState" class="panelStatePill"></div>
        <button id="factoryHoverClearSelection" class="panelClearBtn" type="button">Effacer</button>
      </div>
    </div>
    <div class="factoryHoverGrid">
      <div id="businessSummary" class="businessSummary" style="display:none;">
        <div class="businessSummaryTop">
          <span id="businessSummaryPill" class="businessSummaryPill">Lecture</span>
          <div id="businessSummaryTitle" class="businessSummaryTitle"></div>
        </div>
        <div id="businessSummaryText" class="businessSummaryText"></div>
      </div>
      <div id="panelMeta" class="panelMeta" style="display:none;">
        <div id="panelMetaTitle" class="panelMetaTitle">Synthese site</div>
        <div id="panelMetaGrid" class="panelMetaGrid"></div>
      </div>
      <div id="panelDetailControls" class="panelDetailControls">
        <span id="panelDetailHint" class="panelDetailHint">Vue resume: les blocs d'audit sont replies.</span>
        <button id="panelDetailsToggle" class="tableBtn" type="button">Afficher details</button>
      </div>
      <div id="incomingBlock" class="factoryPlotBlock">
        <div id="incomingLabel" class="factoryPlotLabel">Stock matieres premieres (entree)</div>
        <div id="incomingTabs" class="panelSubTabs"></div>
        <img id="factoryIncomingImage" class="factoryPlot" alt="Node incoming chart"/>
        <div id="factoryIncomingFigure" class="factoryPlotFigure"></div>
      </div>
      <div id="outgoingBlock" class="factoryPlotBlock">
        <div id="outgoingLabel" class="factoryPlotLabel">Production produits finis (sortie)</div>
        <div id="outgoingTabs" class="panelSubTabs"></div>
        <img id="factoryOutgoingImage" class="factoryPlot factoryPlotOutgoing" alt="Node outgoing chart"/>
        <div id="factoryOutgoingFigure" class="factoryPlotFigure factoryPlotOutgoing"></div>
      </div>
      <div id="thirdBlock" class="factoryPlotBlock">
        <div id="thirdLabel" class="factoryPlotLabel">Analyse complementaire</div>
        <div id="thirdTabs" class="panelSubTabs"></div>
        <img id="factoryThirdImage" class="factoryPlot factoryPlotThird" alt="Node additional chart"/>
        <div id="factoryThirdFigure" class="factoryPlotFigure factoryPlotThird"></div>
      </div>
      <div id="fourthBlock" class="factoryPlotBlock">
        <div id="fourthLabel" class="factoryPlotLabel">MRP / risque</div>
        <div id="fourthHelp" class="factoryPlotHelp">Synthese en haut. Puis lis : stock, flux aval. Le bloc pilotage sert a l'analyse : reappro amont, carnet, risque, details MRP.</div>
        <div id="fourthTabs" class="panelSubTabs"></div>
        <img id="factoryFourthImage" class="factoryPlot factoryPlotFourth" alt="Node fourth chart"/>
        <div id="factoryFourthFigure" class="factoryPlotFigure factoryPlotFourth"></div>
      </div>
      <div id="factoryHoverNoImage" style="display:none;">Aucun PNG disponible pour ce noeud.</div>
    </div>
  </div>

  <script>
    const DATA = {data_json};
    const STYLES = DATA.node_type_styles || {{}};
    const FACTORY_HOVER_IMAGES = DATA.factory_hover_images || {{}};
    const SUPPLIER_HOVER_IMAGES = DATA.supplier_hover_images || {{}};
    const DC_HOVER_IMAGES = DATA.distribution_center_hover_images || {{}};
    const CUSTOMER_HOVER_IMAGES = DATA.customer_hover_images || {{}};
    const FACTORY_SENSITIVITY_HOVER_IMAGES = DATA.factory_sensitivity_hover_images || {{}};
    const SUPPLIER_SENSITIVITY_HOVER_IMAGES = DATA.supplier_sensitivity_hover_images || {{}};
    const DC_SENSITIVITY_HOVER_IMAGES = DATA.distribution_center_sensitivity_hover_images || {{}};
    const FACTORY_RISK_HOVER_IMAGES = DATA.factory_supplier_risk_hover_images || {{}};
    const SUPPLIER_RISK_HOVER_IMAGES = DATA.supplier_risk_hover_images || {{}};
    const DC_RISK_HOVER_IMAGES = DATA.distribution_center_supplier_risk_hover_images || {{}};
    const FACTORY_STRUCTURAL_HOVER_IMAGES = DATA.factory_structural_hover_images || {{}};
    const SUPPLIER_STRUCTURAL_HOVER_IMAGES = DATA.supplier_structural_hover_images || {{}};
    const DC_STRUCTURAL_HOVER_IMAGES = DATA.distribution_center_structural_hover_images || {{}};
    const FACTORY_CURRENT_METRICS = DATA.factory_current_metrics || {{}};
    const SUPPLIER_LOCAL_METRICS = DATA.supplier_local_metrics || {{}};
    const CUSTOMER_CURRENT_METRICS = DATA.customer_current_metrics || {{}};
    const GLOBAL_KPI_TREE = DATA.global_kpi_tree || null;
    const MATERIAL_BALANCE_ROWS = DATA.material_balance_rows || [];
    const LOT_TRACE = DATA.lot_trace || {{ available: false, lots: {{}}, lot_options: [], events: [], genealogy: [], plan_events: [], deferred_orders: [] }};
    const MODEL_PANEL = DATA.model_panel || {{ nodes: {{}}, edges: {{}} }};
    const SIMULATED_RISK_CAMPAIGN_METRICS = (
      DATA.supplier_risk_campaign && DATA.supplier_risk_campaign.available
        ? DATA.supplier_risk_campaign
        : {{ available: false, nodes: {{}}, global: {{}} }}
    );
    const DATA_SIMULATED_RISK_STATE_METRICS = DATA.simulated_risk_metrics || {{ nodes: {{}}, global: {{}} }};
    const MODEL_SIMULATED_RISK_STATE_METRICS = MODEL_PANEL.simulated_risk_metrics || {{ nodes: {{}}, global: {{}} }};
    const SIMULATED_RISK_STATE_METRICS = (
      Object.keys((DATA_SIMULATED_RISK_STATE_METRICS && DATA_SIMULATED_RISK_STATE_METRICS.nodes) || {{}}).length > 0
        ? DATA_SIMULATED_RISK_STATE_METRICS
        : MODEL_SIMULATED_RISK_STATE_METRICS
    );
    const SIMULATED_RISK_GLOBAL_DIAGNOSTIC = DATA.simulated_risk_global_diagnostic || {{ available: false, html: "" }};
    const SIMULATED_RISK_NODE_IMPACTS = SIMULATED_RISK_GLOBAL_DIAGNOSTIC.node_impacts || {{}};
    const SIMULATED_RISK_EDGE_IMPACTS = SIMULATED_RISK_GLOBAL_DIAGNOSTIC.edge_impacts || {{}};
    const SCENARIO_COMPARISON = DATA.scenario_comparison || {{ available: false, html: "", figures: {{}}, scenarios: [] }};
    const UNCERTAINTY_METRICS = MODEL_PANEL.uncertainty_metrics || DATA.uncertainty_metrics || {{ nodes: {{}}, edges: {{}} }};
    const DATA_PANEL = DATA.data_panel || {{ nodes: {{}}, edges: {{}} }};
    const JSON_PANEL = DATA.json_panel || {{ nodes: {{}}, edges: {{}} }};
    const TIMELINE_HORIZON_DAYS = Number(DATA.timeline_horizon_days || 0);
    const SIMULATION_DIAGNOSTICS = DATA.simulation_diagnostics || {{ available: false, nodes: {{}}, edges: {{}} }};
    const EDGE_BY_ID = Object.fromEntries((DATA.edges || []).map(e => [e.id, e]));
    const FACTORY_LIKE_NODE_IDS = new Set(DATA.factory_like_node_ids || []);
    const REALISTIC_SENSITIVITY = DATA.realistic_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const THRESHOLD_SENSITIVITY = DATA.threshold_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const SUPPLIER_PARAMETER_SENSITIVITY_NODES = DATA.supplier_parameter_sensitivity_nodes || {{}};
    const SUPPLIER_RISK_METRICS = DATA.supplier_risk_metrics || {{ nodes: {{}}, global: {{}} }};
    const MONTECARLO_UNCERTAINTY = DATA.montecarlo_uncertainty || {{ available: false, html: "" }};
    let scenarioComparisonSelectedIds = new Set();
    function objectHasPayload(obj) {{
      return Boolean(obj && typeof obj === "object" && Object.keys(obj).length);
    }}
    function hasStructuralPayload() {{
      return objectHasPayload(FACTORY_STRUCTURAL_HOVER_IMAGES)
        || objectHasPayload(SUPPLIER_STRUCTURAL_HOVER_IMAGES)
        || objectHasPayload(DC_STRUCTURAL_HOVER_IMAGES);
    }}
    const nodeById = Object.fromEntries((DATA.nodes || []).map(n => [n.id, n]));
    const defaultPalette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"];
    const STANDARD_PLOT_MARGIN = {{ l: 64, r: 24, t: 48, b: 92 }};
    const GANTT_PLOT_MARGIN = {{ l: 128, r: 24, t: 54, b: 92 }};
    const STANDARD_LEGEND = {{ orientation: "h", y: -0.34 }};
    const PLOTLY_PANEL_CONFIG = {{ displayModeBar: false, responsive: false, scrollZoom: true }};
    const PLOTLY_RESPONSIVE_CONFIG = {{ displayModeBar: false, responsive: true, scrollZoom: true }};
    const PLOTLY_MAP_CONFIG = {{ displayModeBar: true, responsive: true, scrollZoom: true }};
    let currentFactoryHoverId = null;
    let currentFactoryHoverType = null;
    let currentHoveredPanelId = null;
    let currentHoveredPanelType = null;
    let selectedPanelNodeId = null;
    let selectedPanelNodeType = null;
    let panelAnchorClientX = null;
    let panelAnchorClientY = null;
    let currentPanelMode = "ops";
    let debugToolsVisible = false;
    let pendingPanelPlotRenderToken = 0;
    let lastFactoryPanelRenderKey = "";
    let hoverHandlersBound = false;
    let panelPointerInside = false;
    let hoverClearTimeout = null;
    let simulatedRiskViewMode = "state";
    let selectedSimulatedRiskCascadeKey = "";
    let simulatedRiskCascadeStageFilter = "all";
    let simulatedRiskCascadeFamilyFilter = "all";
    let simulatedRiskCascadeTextFilter = "";
    let uncertaintyMode = "capacity";
    let uncertaintyDisplayMode = "dominant_type";
    let selectedUncertaintyDriver = null;
    let selectedLotId = "";
    let lotTraceDirection = "both";
    let lotTraceShowDetails = false;
    let panelDetailsExpanded = false;
    let panelDetailsKey = "";
    const SIMULATED_RISK_VIEW_LABELS = {{
      campaign: "stress tests fournisseurs",
      state: "scenario injecte",
    }};
    const SIMULATED_RISK_FAMILY_LABELS = {{
      capacity: "Capacite",
      stock: "Stock",
      lead: "Delai",
      reliability: "Fiabilite",
      upstream: "Appro amont",
      quality: "Qualite",
      cost: "Cout appro fournisseur",
      availability: "Disponibilite",
      other: "Autre",
    }};
    const UNCERTAINTY_MODE_LABELS = {{
      capacity: "capacite fournisseur",
      stock: "stock fournisseur",
      lead: "delai fournisseur",
      reliability: "fiabilite fournisseur",
      factory_capacity: "capacite usine (controle)",
    }};
    const UNCERTAINTY_VIEW_LABELS = {{
      dominant_type: "types dominants fournisseur",
      global_impact: "intensite globale",
      detail_type: "detail par type",
    }};
    const panelBundleSelection = {{}};
    let selectedYearStart = 1;
    let selectedYearEnd = 1;
    let globalKpiTreeState = {{ selectedId: null, smoothingMode: "month", viewMode: "graphs" }};

    function installCtrlScrollZoomGate(plotNode) {{
      if (!plotNode || plotNode.__ctrlScrollZoomGateInstalled) return;
      plotNode.__ctrlScrollZoomGateInstalled = true;
      plotNode.addEventListener("wheel", (ev) => {{
        if (ev.ctrlKey) return;
        ev.stopImmediatePropagation();
      }}, true);
    }}

    function visitTimelineFigures(payload, visitor) {{
      if (!payload || typeof payload !== "object") return;
      Object.values(payload).forEach((panel) => {{
        if (!panel || typeof panel !== "object") return;
        Object.values(panel).forEach((asset) => {{
          if (!asset || typeof asset !== "object") return;
          const figure = asset.figure || null;
          if (!figure || typeof figure !== "object") return;
          visitor(figure);
          if (figure.tabs && typeof figure.tabs === "object") {{
            Object.values(figure.tabs).forEach((tabFigure) => {{
              if (tabFigure && typeof tabFigure === "object") visitor(tabFigure);
            }});
          }}
        }});
      }});
    }}

    function extractFigureMaxDay(figure) {{
      if (!figure || typeof figure !== "object") return 0;
      let maxDay = 0;
      if (figure.kind === "line_multi") {{
        (figure.series || []).forEach((series) => {{
          (series.days || []).forEach((day) => {{
            const value = Number(day);
            if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
          }});
        }});
      }} else if (figure.kind === "dual_panel_multi") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel || panel.kind !== "line_multi") return;
          (panel.series || []).forEach((series) => {{
            (series.days || []).forEach((day) => {{
              const value = Number(day);
              if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
            }});
          }});
        }});
      }} else if (figure.kind === "dual_panel") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel) return;
          (panel.x || []).forEach((day) => {{
            const value = Number(day);
            if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
          }});
        }});
      }} else if (figure.kind === "gantt") {{
        (figure.rows || []).forEach((row) => {{
          const value = Number(row.end || row.start || 0);
          if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
        }});
      }}
      return maxDay;
    }}

    function extractFigureMinDay(figure) {{
      if (!figure || typeof figure !== "object") return 0;
      let minDay = 0;
      function inspectValue(rawValue) {{
        const value = Number(rawValue);
        if (Number.isFinite(value)) minDay = Math.min(minDay, value);
      }}
      if (figure.kind === "line_multi") {{
        (figure.series || []).forEach((series) => {{
          (series.days || []).forEach(inspectValue);
        }});
      }} else if (figure.kind === "dual_panel_multi") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel || panel.kind !== "line_multi") return;
          (panel.series || []).forEach((series) => {{
            (series.days || []).forEach(inspectValue);
          }});
        }});
      }} else if (figure.kind === "dual_panel") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel) return;
          (panel.x || []).forEach(inspectValue);
        }});
      }} else if (figure.kind === "gantt") {{
        (figure.rows || []).forEach((row) => {{
          inspectValue(row.start || 0);
        }});
      }}
      return minDay;
    }}

    function computeTimelineMaxYear() {{
      if (Number.isFinite(TIMELINE_HORIZON_DAYS) && TIMELINE_HORIZON_DAYS > 0) {{
        return Math.max(1, Math.ceil(TIMELINE_HORIZON_DAYS / 365));
      }}
      let maxDay = 0;
      [FACTORY_HOVER_IMAGES, SUPPLIER_HOVER_IMAGES, DC_HOVER_IMAGES, CUSTOMER_HOVER_IMAGES].forEach((payload) => {{
        visitTimelineFigures(payload, (figure) => {{
          maxDay = Math.max(maxDay, extractFigureMaxDay(figure));
        }});
      }});
      return Math.max(1, Math.ceil((maxDay + 1) / 365));
    }}

    function computeTimelineMinDay() {{
      let minDay = 0;
      [FACTORY_HOVER_IMAGES, SUPPLIER_HOVER_IMAGES, DC_HOVER_IMAGES, CUSTOMER_HOVER_IMAGES].forEach((payload) => {{
        visitTimelineFigures(payload, (figure) => {{
          minDay = Math.min(minDay, extractFigureMinDay(figure));
        }});
      }});
      return Math.min(0, minDay);
    }}

    const timelineMaxYear = computeTimelineMaxYear();
    const timelineMinDay = computeTimelineMinDay();
    selectedYearEnd = timelineMaxYear;

    function syncYearInputs() {{
      const yearStartInput = document.getElementById("yearStart");
      const yearEndInput = document.getElementById("yearEnd");
      if (!yearStartInput || !yearEndInput) return;
      yearStartInput.max = String(timelineMaxYear);
      yearEndInput.max = String(timelineMaxYear);
      selectedYearStart = Math.min(Math.max(1, selectedYearStart), timelineMaxYear);
      selectedYearEnd = Math.min(Math.max(1, selectedYearEnd), timelineMaxYear);
      if (selectedYearStart > selectedYearEnd) {{
        selectedYearEnd = selectedYearStart;
      }}
      yearStartInput.value = String(selectedYearStart);
      yearEndInput.value = String(selectedYearEnd);
    }}

    function updateTimelineWindowLabel() {{
      const valueEl = document.getElementById("yearWindowValue");
      if (!valueEl) return;
      valueEl.textContent = selectedTimelineWindowLabel();
    }}

    function selectedTimelineWindowLabel() {{
      return timelineMaxYear > 1
        ? `annee ${{selectedYearStart}} -> ${{selectedYearEnd}}`
        : "run complet";
    }}

    function applyTimelineWindowUi() {{
      const box = document.getElementById("timelineWindowBox");
      if (!box) return;
      const visible = currentPanelMode === "ops" && timelineMaxYear > 1;
      box.classList.toggle("visible", visible);
    }}

    function currentTimelineDayRange() {{
      const startDay = selectedYearStart <= 1
        ? Math.min(0, timelineMinDay)
        : (selectedYearStart - 1) * 365;
      let endDay = (selectedYearEnd * 365) - 1;
      if (Number.isFinite(TIMELINE_HORIZON_DAYS) && TIMELINE_HORIZON_DAYS > 0) {{
        endDay = Math.min(endDay, Math.max(0, TIMELINE_HORIZON_DAYS - 1));
      }}
      return {{
        startDay: Math.min(startDay, endDay),
        endDay,
      }};
    }}

    function dayAxisTickStep(spanDays) {{
      const span = Math.max(1, Number(spanDays) || 1);
      if (span <= 31) return 5;
      if (span <= 90) return 10;
      if (span <= 200) return 25;
      if (span <= 450) return 50;
      if (span <= 900) return 100;
      if (span <= 2200) return 200;
      return 500;
    }}

    function dayAxisLayout(title = "Jour", extra = {{}}) {{
      const range = currentTimelineDayRange();
      const startDay = Number(range.startDay) || 0;
      const endDay = Math.max(startDay, Number(range.endDay) || 0);
      const visualPaddingDays = Math.max(5, (endDay - startDay) * 0.02);
      const axisStart = startDay - visualPaddingDays;
      const axisEnd = endDay + visualPaddingDays;
      const step = dayAxisTickStep(endDay - startDay);
      const firstTick = Math.ceil(startDay / step) * step;
      const tickvals = [];
      const ticktext = [];
      for (let day = firstTick; day <= endDay; day += step) {{
        tickvals.push(day);
        ticktext.push(day < 0 ? `J${{day}}` : String(day));
      }}
      if (startDay < 0 && endDay >= 0 && !tickvals.includes(0)) {{
        tickvals.push(0);
        ticktext.push("0");
      }}
      if (!tickvals.length) {{
        tickvals.push(startDay);
        ticktext.push(String(startDay));
      }}
      return {{
        title,
        gridcolor: "#e2e8f0",
        range: [axisStart, axisEnd],
        tickmode: "array",
        tickvals,
        ticktext,
        ...extra,
      }};
    }}

    function filterSeriesByTimeline(days, values, forceWindow = false) {{
      if ((!forceWindow && currentPanelMode !== "ops") || timelineMaxYear <= 1) {{
        return {{
          days: (days || []).slice(),
          values: (values || []).slice(),
        }};
      }}
      const {{ startDay, endDay }} = currentTimelineDayRange();
      const filteredDays = [];
      const filteredValues = [];
      const inputDays = days || [];
      const inputValues = values || [];
      for (let idx = 0; idx < inputDays.length; idx += 1) {{
        const day = Number(inputDays[idx]);
        if (!Number.isFinite(day)) continue;
        if (day < startDay || day > endDay) continue;
        filteredDays.push(day);
        filteredValues.push(inputValues[idx]);
      }}
      return {{ days: filteredDays, values: filteredValues }};
    }}

    function filterXYByTimeline(x, y) {{
      if (currentPanelMode !== "ops" || timelineMaxYear <= 1) {{
        return {{
          x: (x || []).slice(),
          y: (y || []).slice(),
        }};
      }}
      const {{ startDay, endDay }} = currentTimelineDayRange();
      const filteredX = [];
      const filteredY = [];
      const inputX = x || [];
      const inputY = y || [];
      for (let idx = 0; idx < inputX.length; idx += 1) {{
        const value = Number(inputX[idx]);
        if (!Number.isFinite(value)) {{
          filteredX.push(inputX[idx]);
          filteredY.push(inputY[idx]);
          continue;
        }}
        if (value < startDay || value > endDay) continue;
        filteredX.push(inputX[idx]);
        filteredY.push(inputY[idx]);
      }}
      return {{ x: filteredX, y: filteredY }};
    }}

    function fmtPanelQty(value, digits = 1) {{
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return "n/a";
      return numeric.toLocaleString("fr-FR", {{
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }});
    }}

    function fmtMultiplierPercent(value, digits = 0) {{
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return "n/a";
      const percent = numeric * 100;
      const rounded = Math.round(percent);
      const finalDigits = Math.abs(percent - rounded) < 1e-9 ? 0 : digits;
      return `${{percent.toLocaleString("fr-FR", {{
        minimumFractionDigits: finalDigits,
        maximumFractionDigits: finalDigits,
      }})}}%`;
    }}

    function escapeTableHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }}[ch]));
    }}

    function lotTraceDay(row) {{
      const value = Number(row && row.day);
      return Number.isFinite(value) ? value : null;
    }}

    function lotTraceQtyText(value, digits = 1) {{
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return "";
      return numeric.toLocaleString("fr-FR", {{
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }});
    }}

    const LOT_TRACE_CONFIG = LOT_TRACE.config || {{}};

    function lotTraceConfigMap(key) {{
      const value = LOT_TRACE_CONFIG[key];
      return value && typeof value === "object" && !Array.isArray(value) ? value : {{}};
    }}

    function lotTraceConfigList(key) {{
      const value = LOT_TRACE_CONFIG[key];
      return Array.isArray(value) ? value.map(item => String(item)) : [];
    }}

    function lotTraceCanonicalNodeId(nodeId) {{
      const raw = String(nodeId || "");
      const aliases = lotTraceConfigMap("node_aliases");
      return aliases[raw] || raw;
    }}

    function lotTraceDisplayNodeId(nodeId) {{
      const raw = lotTraceCanonicalNodeId(nodeId);
      const labels = lotTraceConfigMap("node_display_labels");
      return labels[raw] || raw || "n/a";
    }}

    function lotTraceIsUpstreamInternalSite(nodeId) {{
      const canonical = lotTraceCanonicalNodeId(nodeId);
      return lotTraceConfigList("upstream_internal_site_ids").includes(canonical);
    }}

    function lotTraceStockContextLookup(nodeId, itemId, day) {{
      const dayNum = Number(day);
      if (!Number.isFinite(dayNum)) return null;
      const rawNode = String(nodeId || "");
      const canonicalNode = lotTraceCanonicalNodeId(rawNode);
      const item = String(itemId || "");
      const contexts = LOT_TRACE.stock_context || {{}};
      return contexts[`${{canonicalNode}}|${{item}}|${{Math.round(dayNum)}}`]
        || contexts[`${{rawNode}}|${{item}}|${{Math.round(dayNum)}}`]
        || null;
    }}

    function lotTraceStockContextDisplay(context) {{
      if (!context) return "";
      const before = Number(context.before_qty);
      const after = Number(context.after_qty);
      const delta = Number(context.delta_qty);
      const hasBeforeAfter = Number.isFinite(before) && Number.isFinite(after);
      const base = hasBeforeAfter
        ? `${{lotTraceQtyText(before)}} -> ${{lotTraceQtyText(after)}}`
        : (Number.isFinite(after) ? `apres ${{lotTraceQtyText(after)}}` : "");
      if (!base) return "";
      const deltaText = Number.isFinite(delta) && Math.abs(delta) > 1e-9
        ? ` (${{delta > 0 ? "+" : ""}}${{lotTraceQtyText(delta)}})`
        : "";
      return `${{context.label || "stock"}}: ${{base}}${{deltaText}}`;
    }}

    function lotTraceEventStockText(row) {{
      const context = lotTraceStockContextLookup(row.node_id, row.item_id, lotTraceDay(row));
      const stockText = lotTraceStockContextDisplay(context);
      if (stockText) return stockText;
      if (row.qty_after !== undefined && row.qty_after !== "") {{
        return `stock lot apres evenement: ${{lotTraceQtyText(row.qty_after)}}`;
      }}
      return "";
    }}

    const LOT_TRACE_LOGISTICS_ASSUMPTIONS = lotTraceConfigMap("logistics_assumptions");

    function lotTraceNormalizeItemId(itemId) {{
      const text = String(itemId || "").trim();
      if (!text) return "";
      return text.startsWith("item:") ? text : `item:${{text}}`;
    }}

    function lotTraceLogisticsEstimate(itemId, qty) {{
      const policy = LOT_TRACE_LOGISTICS_ASSUMPTIONS[lotTraceNormalizeItemId(itemId)];
      const quantity = Number(qty);
      if (!policy || !Number.isFinite(quantity) || quantity <= 0) return null;
      const casesExact = quantity / policy.unitsPerCase;
      const cases = Math.max(1, Math.ceil(casesExact));
      const centralPallets = Math.max(1, Math.ceil(casesExact / policy.centralCasesPerPallet));
      const minPallets = Math.max(1, Math.ceil(casesExact / policy.maxCasesPerPallet));
      const maxPallets = Math.max(1, Math.ceil(casesExact / policy.minCasesPerPallet));
      const trucks = Math.max(1, Math.ceil(centralPallets / policy.truckPalletSlots));
      const minTrucks = Math.max(1, Math.ceil(minPallets / policy.truckPalletSlots));
      const maxTrucks = Math.max(1, Math.ceil(maxPallets / policy.truckPalletSlots));
      return {{
        cases,
        centralPallets,
        minPallets,
        maxPallets,
        trucks,
        minTrucks,
        maxTrucks,
        volumeM3: centralPallets * policy.palletEnvelopeM3,
        identifiableMassKg: quantity * policy.identifiableMassKgPerUnit,
      }};
    }}

    function lotTracePalletRangeText(estimate) {{
      if (!estimate) return "";
      const range = estimate.minPallets === estimate.maxPallets
        ? `${{estimate.centralPallets}} pal`
        : `${{estimate.centralPallets}} pal (${{estimate.minPallets}}-${{estimate.maxPallets}})`;
      const trucks = estimate.minTrucks === estimate.maxTrucks
        ? `${{estimate.trucks}} cam`
        : `${{estimate.trucks}} cam (${{estimate.minTrucks}}-${{estimate.maxTrucks}})`;
      return `${{range}}, ${{trucks}}`;
    }}

    function lotTraceLogisticsShortText(itemId, qty) {{
      const estimate = lotTraceLogisticsEstimate(itemId, qty);
      const text = lotTracePalletRangeText(estimate);
      return text ? `hyp. ~${{text}}` : "";
    }}

    function lotTraceLogisticsDetailText(itemId, qty) {{
      const estimate = lotTraceLogisticsEstimate(itemId, qty);
      if (!estimate) return "";
      const pallets = lotTracePalletRangeText(estimate);
      const tons = estimate.identifiableMassKg / 1000;
      const policy = LOT_TRACE_LOGISTICS_ASSUMPTIONS[lotTraceNormalizeItemId(itemId)] || {{}};
      const unitLabel = policy.unitLabel ? String(policy.unitLabel) : "unites";
      const caseText = policy.unitsPerCase
        ? ` (${{policy.unitsPerCase}} ${{unitLabel}}/caisse)`
        : "";
      return `hyp. ~${{estimate.cases.toLocaleString("fr-FR")}} caisses${{caseText}}; ${{pallets}}; ${{lotTraceQtyText(estimate.volumeM3, 1)}} m3; ${{lotTraceQtyText(tons, 2)}} t ident.`;
    }}

    function lotTraceEventLabel(eventType) {{
      const labels = {{
        opening_stock: "Stock initial",
        production_output: "Produit",
        production_consume: "Consomme",
        lane_ship: "Expedie",
        lane_receipt: "Recu stock",
        demand_service: "Servi client",
        external_procurement_receipt: "Appro fournisseur",
        estimated_source_receipt: "Source estimee",
        estimated_capacity_receipt: "Capacite estimee",
        supplier_writeoff: "Ecart fournisseur",
        start_campaign: "Debut campagne",
        run_campaign_complete: "Campagne terminee",
        partial_run_input_shortage: "Rupture input",
        delay_input_shortage: "Report rupture input",
        delay_capacity: "Report capacite",
        partial_run_capacity: "Production limitee capacite",
        delay_lot_campaign_blocked: "Campagne bloquee",
        delay_weekly_lot_limit: "Limite lots semaine",
      }};
      const raw = String(eventType || "");
      return labels[raw] || raw || "n/a";
    }}

    function lotTraceAddMapEntry(map, key, value) {{
      if (!key) return;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(value);
    }}

    function lotTraceAddSetValue(set, value) {{
      const text = String(value || "").trim();
      if (text) set.add(text);
    }}

    function lotTraceSourceEdgeId(value) {{
      const source = String(value || "");
      return source.startsWith("edge:") ? source : "";
    }}

    function lotTraceDeferredOrders() {{
      return Array.isArray(LOT_TRACE.deferred_orders) ? LOT_TRACE.deferred_orders : [];
    }}

    function lotTraceDeferredOrderValue(campaignId) {{
      return `order:${{campaignId}}`;
    }}

    function lotTraceDeferredOrderCampaignId(value) {{
      const text = String(value || "");
      return text.startsWith("order:") ? text.slice(6) : "";
    }}

    function selectedDeferredOrder(value = selectedLotId) {{
      const campaignId = lotTraceDeferredOrderCampaignId(value);
      if (!campaignId) return null;
      return lotTraceDeferredOrders().find(row => String(row.campaign_id || "") === campaignId) || null;
    }}

    function deferredOrderDays(order) {{
      if (!order) return [];
      const days = new Set();
      [order.first_delay_day, order.last_delay_day, order.completed_day].forEach(value => {{
        const day = Number(value);
        if (Number.isFinite(day)) days.add(day);
      }});
      (order.next_expected_receipt_days || []).forEach(value => {{
        const day = Number(value);
        if (Number.isFinite(day)) days.add(day);
      }});
      return Array.from(days).sort((a, b) => a - b);
    }}

    function buildLotTraceIndexes() {{
      const indexes = {{
        eventsByLot: new Map(),
        parentsByChild: new Map(),
        childrenByParent: new Map(),
        planByCampaign: new Map(),
        nodeIdsByLot: new Map(),
        edgeIdsByLot: new Map(),
        campaignsByLot: new Map(),
      }};
      (LOT_TRACE.events || []).forEach((row) => {{
        const lotId = String(row.lot_id || "");
        if (!lotId) return;
        lotTraceAddMapEntry(indexes.eventsByLot, lotId, row);
        lotTraceAddMapEntry(indexes.nodeIdsByLot, lotId, String(row.node_id || ""));
        const edgeId = lotTraceSourceEdgeId(row.source_id);
        if (edgeId) lotTraceAddMapEntry(indexes.edgeIdsByLot, lotId, edgeId);
        if (row.production_campaign_id) {{
          lotTraceAddMapEntry(indexes.campaignsByLot, lotId, String(row.production_campaign_id || ""));
        }}
      }});
      (LOT_TRACE.genealogy || []).forEach((row) => {{
        const parentLot = String(row.parent_lot_id || "");
        const childLot = String(row.child_lot_id || "");
        if (parentLot && childLot) {{
          lotTraceAddMapEntry(indexes.parentsByChild, childLot, row);
          lotTraceAddMapEntry(indexes.childrenByParent, parentLot, row);
        }}
        if (parentLot) {{
          lotTraceAddMapEntry(indexes.nodeIdsByLot, parentLot, String(row.parent_node_id || ""));
          if (row.production_campaign_id) lotTraceAddMapEntry(indexes.campaignsByLot, parentLot, String(row.production_campaign_id || ""));
        }}
        if (childLot) {{
          lotTraceAddMapEntry(indexes.nodeIdsByLot, childLot, String(row.child_node_id || ""));
          if (row.production_campaign_id) lotTraceAddMapEntry(indexes.campaignsByLot, childLot, String(row.production_campaign_id || ""));
        }}
        const edgeId = lotTraceSourceEdgeId(row.source_id);
        if (edgeId) {{
          if (parentLot) lotTraceAddMapEntry(indexes.edgeIdsByLot, parentLot, edgeId);
          if (childLot) lotTraceAddMapEntry(indexes.edgeIdsByLot, childLot, edgeId);
        }}
      }});
      (LOT_TRACE.plan_events || []).forEach((row) => {{
        const campaignId = String(row.campaign_id || "");
        if (campaignId) lotTraceAddMapEntry(indexes.planByCampaign, campaignId, row);
      }});
      return indexes;
    }}

    const lotTraceIndexes = buildLotTraceIndexes();

    function lotTraceIsValidViewModel(model, lotId) {{
      if (!model || typeof model !== "object") return false;
      if (Number(model.version) !== 1) return false;
      if (String(model.lot_id || "") !== String(lotId || "")) return false;
      if (!model.snapshot || typeof model.snapshot !== "object") return false;
      if (!Array.isArray(model.snapshot.lot_ids)) return false;
      if (!Array.isArray(model.nodes)) return false;
      if (!Array.isArray(model.links)) return false;
      return true;
    }}

    function lotTraceViewModelForLot(lotId) {{
      const id = String(lotId || "");
      const models = LOT_TRACE.view_models && typeof LOT_TRACE.view_models === "object" && !Array.isArray(LOT_TRACE.view_models)
        ? LOT_TRACE.view_models
        : {{}};
      if (lotTraceIsValidViewModel(models[id], id)) return models[id];
      if (lotTraceIsValidViewModel(LOT_TRACE.default_view_model, id)) return LOT_TRACE.default_view_model;
      return null;
    }}

    function lotTraceSnapshotFromViewModel(lotId) {{
      const model = lotTraceViewModelForLot(lotId);
      if (!model) return null;
      try {{
        const modelSnapshot = model.snapshot || {{}};
        const relatedLots = Array.isArray(modelSnapshot.lot_ids) ? modelSnapshot.lot_ids.map(lot => String(lot)) : [];
        const upstreamLots = Array.isArray(modelSnapshot.upstream_lot_ids) ? modelSnapshot.upstream_lot_ids.map(lot => String(lot)) : [];
        const downstreamLots = Array.isArray(modelSnapshot.downstream_lot_ids) ? modelSnapshot.downstream_lot_ids.map(lot => String(lot)) : [];
        const eventIds = new Set(Array.isArray(modelSnapshot.event_ids) ? modelSnapshot.event_ids.map(id => String(id)) : []);
        const events = eventIds.size
          ? (LOT_TRACE.events || [])
              .filter(row => eventIds.has(String(row.event_id || "")))
              .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0) || String(a.lot_id || "").localeCompare(String(b.lot_id || "")))
          : relatedLots
              .flatMap(lot => lotTraceIndexes.eventsByLot.get(lot) || [])
              .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0) || String(a.lot_id || "").localeCompare(String(b.lot_id || "")));
        const links = (Array.isArray(model.links) ? model.links : [])
          .map(row => ({{ ...row }}))
          .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0));
        const upstreamLotSet = new Set(upstreamLots);
        const downstreamLotSet = new Set(downstreamLots);
        const rootLotId = String(lotId || "");
        const upstreamLinks = links.filter(row => {{
          const parent = String(row.parent_lot_id || "");
          const child = String(row.child_lot_id || "");
          return upstreamLotSet.has(parent) || upstreamLotSet.has(child) || child === rootLotId;
        }});
        const downstreamLinks = links.filter(row => {{
          const parent = String(row.parent_lot_id || "");
          const child = String(row.child_lot_id || "");
          return downstreamLotSet.has(parent) || downstreamLotSet.has(child) || parent === rootLotId;
        }});
        const nodeIds = new Set(Array.isArray(modelSnapshot.node_ids) ? modelSnapshot.node_ids.map(id => String(id)) : []);
        const edgeIds = new Set(Array.isArray(modelSnapshot.edge_ids) ? modelSnapshot.edge_ids.map(id => String(id)) : []);
        const campaigns = new Set(Array.isArray(modelSnapshot.campaign_ids) ? modelSnapshot.campaign_ids.map(id => String(id)) : []);
        events.forEach((row) => {{
          lotTraceAddSetValue(nodeIds, row.node_id);
          lotTraceAddSetValue(campaigns, row.production_campaign_id);
          lotTraceAddSetValue(edgeIds, lotTraceSourceEdgeId(row.source_id));
        }});
        links.forEach((row) => {{
          lotTraceAddSetValue(nodeIds, row.parent_node_id);
          lotTraceAddSetValue(nodeIds, row.child_node_id);
          lotTraceAddSetValue(campaigns, row.production_campaign_id);
          lotTraceAddSetValue(edgeIds, lotTraceSourceEdgeId(row.source_id));
        }});
        const planEvents = Array.from(campaigns)
          .flatMap(campaign => lotTraceIndexes.planByCampaign.get(campaign) || [])
          .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0) || String(a.campaign_id || "").localeCompare(String(b.campaign_id || "")));
        const days = new Set(Array.isArray(modelSnapshot.days) ? modelSnapshot.days.map(day => Number(day)).filter(day => Number.isFinite(day)) : []);
        events.forEach(row => {{
          const day = lotTraceDay(row);
          if (day !== null) days.add(day);
        }});
        planEvents.forEach(row => {{
          const day = lotTraceDay(row);
          if (day !== null) days.add(day);
        }});
        return {{
          lotId: rootLotId,
          rootLot: model.root_lot || (LOT_TRACE.lots || {{}})[rootLotId] || null,
          relatedLots,
          upstreamLots,
          downstreamLots,
          events,
          links,
          upstreamLinks,
          downstreamLinks,
          planEvents,
          nodeIds: Array.from(nodeIds).filter(Boolean),
          edgeIds: Array.from(edgeIds).filter(Boolean),
          campaigns: Array.from(campaigns).filter(Boolean),
          days: Array.from(days).sort((a, b) => a - b),
          viewModel: model,
        }};
      }} catch (error) {{
        if (typeof DEBUG !== "undefined" && DEBUG) console.warn("lot trace view model fallback", error);
        return null;
      }}
    }}

    function selectedLotTraceSnapshot(lotId = selectedLotId) {{
      if (selectedDeferredOrder(lotId)) return null;
      if (!LOT_TRACE.available || !lotId) return null;
      const viewModelSnapshot = lotTraceSnapshotFromViewModel(lotId);
      if (viewModelSnapshot) return viewModelSnapshot;
      const related = new Set([lotId]);
      const traceLinks = [];
      const upstreamLinks = [];
      const downstreamLinks = [];
      const upstreamLots = new Set();
      const downstreamLots = new Set();
      const seenLinks = new Set();
      function linkIdentity(row) {{
        return [
          row.day || "",
          row.link_type || "",
          row.parent_lot_id || "",
          row.child_lot_id || "",
          row.source_id || "",
          row.production_campaign_id || "",
        ].join("|");
      }}
      function rememberTraceLink(row, direction) {{
        const key = linkIdentity(row);
        if (!seenLinks.has(key)) {{
          seenLinks.add(key);
          traceLinks.push(row);
        }}
        if (direction === "upstream") upstreamLinks.push(row);
        if (direction === "downstream") downstreamLinks.push(row);
      }}

      const upstreamQueue = [lotId];
      const visitedUpstream = new Set();
      while (upstreamQueue.length && related.size < 5000) {{
        const current = upstreamQueue.shift();
        if (visitedUpstream.has(current)) continue;
        visitedUpstream.add(current);
        (lotTraceIndexes.parentsByChild.get(current) || []).forEach((link) => {{
          const parent = String(link.parent_lot_id || "");
          if (parent) {{
            related.add(parent);
            upstreamLots.add(parent);
            rememberTraceLink(link, "upstream");
            upstreamQueue.push(parent);
          }}
        }});
      }}

      const downstreamQueue = [lotId];
      const visitedDownstream = new Set();
      while (downstreamQueue.length && related.size < 5000) {{
        const current = downstreamQueue.shift();
        if (visitedDownstream.has(current)) continue;
        visitedDownstream.add(current);
        (lotTraceIndexes.childrenByParent.get(current) || []).forEach((link) => {{
          const child = String(link.child_lot_id || "");
          if (child) {{
            related.add(child);
            downstreamLots.add(child);
            rememberTraceLink(link, "downstream");
            downstreamQueue.push(child);
          }}
        }});
      }}
      const relatedLots = Array.from(related);
      const events = relatedLots
        .flatMap(lot => lotTraceIndexes.eventsByLot.get(lot) || [])
        .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0) || String(a.lot_id || "").localeCompare(String(b.lot_id || "")));
      const links = traceLinks
        .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0));
      const nodeIds = new Set();
      const edgeIds = new Set();
      const campaigns = new Set();
      events.forEach((row) => {{
        lotTraceAddSetValue(nodeIds, row.node_id);
        lotTraceAddSetValue(campaigns, row.production_campaign_id);
        lotTraceAddSetValue(edgeIds, lotTraceSourceEdgeId(row.source_id));
      }});
      links.forEach((row) => {{
        lotTraceAddSetValue(nodeIds, row.parent_node_id);
        lotTraceAddSetValue(nodeIds, row.child_node_id);
        lotTraceAddSetValue(campaigns, row.production_campaign_id);
        lotTraceAddSetValue(edgeIds, lotTraceSourceEdgeId(row.source_id));
      }});
      relatedLots.forEach((lot) => {{
        (lotTraceIndexes.nodeIdsByLot.get(lot) || []).forEach(value => lotTraceAddSetValue(nodeIds, value));
        (lotTraceIndexes.edgeIdsByLot.get(lot) || []).forEach(value => lotTraceAddSetValue(edgeIds, value));
        (lotTraceIndexes.campaignsByLot.get(lot) || []).forEach(value => lotTraceAddSetValue(campaigns, value));
      }});
      const planEvents = Array.from(campaigns)
        .flatMap(campaign => lotTraceIndexes.planByCampaign.get(campaign) || [])
        .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0) || String(a.campaign_id || "").localeCompare(String(b.campaign_id || "")));
      const days = new Set();
      events.forEach(row => {{
        const day = lotTraceDay(row);
        if (day !== null) days.add(day);
      }});
      planEvents.forEach(row => {{
        const day = lotTraceDay(row);
        if (day !== null) days.add(day);
      }});
      return {{
        lotId,
        rootLot: (LOT_TRACE.lots || {{}})[lotId] || null,
        relatedLots,
        upstreamLots: Array.from(upstreamLots),
        downstreamLots: Array.from(downstreamLots),
        events,
        links,
        upstreamLinks,
        downstreamLinks,
        planEvents,
        nodeIds: Array.from(nodeIds),
        edgeIds: Array.from(edgeIds),
        campaigns: Array.from(campaigns),
        days: Array.from(days).sort((a, b) => a - b),
      }};
    }}

    function selectedLotTraceDays() {{
      const order = selectedDeferredOrder();
      if (order) {{
        const range = currentTimelineDayRange();
        return deferredOrderDays(order).filter(day => day >= range.startDay && day <= range.endDay);
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot) return [];
      const range = currentTimelineDayRange();
      return snapshot.days.filter(day => Number.isFinite(day) && day >= range.startDay && day <= range.endDay);
    }}

    function selectedLotTraceDaysForContext(contextNodeId = "", contextNodeType = "") {{
      const order = selectedDeferredOrder();
      if (order && contextNodeType !== "edge") {{
        const nodeId = String(order.node_id || "");
        if (nodeId && String(contextNodeId || "") === nodeId) {{
          const range = currentTimelineDayRange();
          return deferredOrderDays(order)
            .filter(day => Number.isFinite(day) && day >= range.startDay && day <= range.endDay)
            .sort((a, b) => a - b);
        }}
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot || !contextNodeId) return [];
      const days = new Set();
      const rootLotId = String(snapshot.lotId || "");
      const downstreamLotSet = new Set(snapshot.downstreamLots || []);
      function eventBelongsToFocusedPath(row) {{
        const lotId = String(row.lot_id || "");
        const eventType = String(row.event_type || "");
        if (lotId === rootLotId) return true;
        if (eventType === "demand_service" && downstreamLotSet.has(lotId)) return true;
        return false;
      }}
      if (contextNodeType === "edge") {{
        snapshot.events.forEach((row) => {{
          if (eventBelongsToFocusedPath(row) && lotTraceSourceEdgeId(row.source_id) === contextNodeId) {{
            const day = lotTraceDay(row);
            if (day !== null) days.add(day);
          }}
        }});
        snapshot.links.forEach((row) => {{
          if (lotTraceSourceEdgeId(row.source_id) === contextNodeId) {{
            const day = lotTraceDay(row);
            if (day !== null) days.add(day);
          }}
        }});
      }} else {{
        snapshot.events.forEach((row) => {{
          if (eventBelongsToFocusedPath(row) && String(row.node_id || "") === contextNodeId) {{
            const day = lotTraceDay(row);
            if (day !== null) days.add(day);
          }}
        }});
        snapshot.links.forEach((row) => {{
          if (String(row.parent_node_id || "") === contextNodeId || String(row.child_node_id || "") === contextNodeId) {{
            const day = lotTraceDay(row);
            if (day !== null) days.add(day);
          }}
        }});
        snapshot.planEvents.forEach((row) => {{
          if (String(row.node_id || "") === contextNodeId) {{
            const day = lotTraceDay(row);
            if (day !== null) days.add(day);
          }}
        }});
      }}
      const range = currentTimelineDayRange();
      return Array.from(days)
        .filter(day => Number.isFinite(day) && day >= range.startDay && day <= range.endDay)
        .sort((a, b) => a - b);
    }}

    function selectedLotRootProductionDaysForContext(contextNodeId = "", contextNodeType = "") {{
      if (contextNodeType === "edge") return [];
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot || !contextNodeId) return [];
      const rootLotId = String(snapshot.lotId || "");
      const range = currentTimelineDayRange();
      const days = new Set();
      (snapshot.events || []).forEach((row) => {{
        if (String(row.lot_id || "") !== rootLotId) return;
        if (String(row.event_type || "") !== "production_output") return;
        if (String(row.node_id || "") !== String(contextNodeId || "")) return;
        const day = lotTraceDay(row);
        if (day !== null && day >= range.startDay && day <= range.endDay) days.add(day);
      }});
      return Array.from(days).sort((a, b) => a - b);
    }}

    function lotTracePlotCategory(plotlyFigure, contextNodeType = "") {{
      const explicitCategory = String((((plotlyFigure || {{}}).layout || {{}}).meta || {{}}).lot_trace_category || "");
      if (explicitCategory) return explicitCategory;
      const title = plotlyFigureTitleText(plotlyFigure).toLowerCase();
      if (contextNodeType === "edge") {{
        return title.includes("envois et receptions physiques") ? "transport" : "none";
      }}
      if (title.includes("planning production lots")) return "production";
      if (
        title.includes("stock intrant") ||
        title.includes("stocks intrants") ||
        title.includes("receptions intrants") ||
        title.includes("arrivages intrants") ||
        title.includes("stock physique et cible physique") ||
        title.includes("stock physique et seuil mrp") ||
        title.includes("stock physique vs consigne physique") ||
        title.includes("besoins intrants") ||
        title.includes("pilotage mrp") ||
        title.includes("receptions physiques intrants")
      ) return "factory_input";
      if (
        title.includes("stock produits finis") ||
        title.includes("stock pfi") ||
        title.includes("expeditions pfi")
      ) return "factory_output";
      if (title.includes("stock fournisseur") || title.includes("entrees et sorties de stock fournisseur")) return "supplier_stock";
      if (
        title.includes("executions physiques") ||
        title.includes("receptions aval") ||
        title.includes("expeditions prevues") ||
        title.includes("envois physiques et receptions previsionnelles")
      ) return "supplier_send";
      if (title.includes("stock dc")) return "dc_stock";
      if (title.includes("receptions journalieres") || title.includes("receptions client")) return "receipt";
      if (title.includes("expeditions journalieres")) return "shipment";
      if (title.includes("servi et backlog") || title.includes("demande dans le temps")) return "customer_service";
      return "none";
    }}

    function lotTracePlotCategoryLabel(category) {{
      return {{
        production: "jalons production / consommation",
        factory_input: "jalons intrants usine",
        factory_output: "jalons stock PF usine",
        supplier_stock: "jalons stock fournisseur",
        supplier_send: "jalons execution fournisseur",
        dc_stock: "jalons stock DC",
        receipt: "jalons reception",
        shipment: "jalons expedition",
        customer_service: "disponibilite client du lot",
        transport: "jalons transport",
      }}[category] || "trace lot";
    }}

    function lotTraceMarkerStyle(kind) {{
      return {{
        production: {{ label: "production", color: "#16a34a", dash: "solid", width: 2.4, symbol: "diamond" }},
        consume: {{ label: "consommation BOM", color: "#2563eb", dash: "solid", width: 2.0, symbol: "circle" }},
        shipment: {{ label: "expedition", color: "#f97316", dash: "dash", width: 1.6, symbol: "triangle-right" }},
        receipt: {{ label: "reception", color: "#0ea5e9", dash: "dash", width: 1.6, symbol: "triangle-left" }},
        transport: {{ label: "transport", color: "#f59e0b", dash: "dash", width: 1.6, symbol: "square" }},
        service: {{ label: "client servi", color: "#a855f7", dash: "dot", width: 1.4, symbol: "triangle-up" }},
        stock: {{ label: "stock initial", color: "#64748b", dash: "dot", width: 1.3, symbol: "circle-open" }},
        delay: {{ label: "report", color: "#dc2626", dash: "dashdot", width: 2.2, symbol: "x" }},
      }}[kind] || {{ label: String(kind || "jalon"), color: "#f97316", dash: "dot", width: 1.3, symbol: "circle" }};
    }}

    function lotTraceCompactMarkers(markers, maxMarkers = 140) {{
      if (!Array.isArray(markers) || markers.length <= maxMarkers) return {{ markers: markers || [], hidden: 0 }};
      const priority = {{ production: 0, delay: 1, consume: 2, shipment: 3, receipt: 4, transport: 5, service: 6, stock: 7 }};
      const sorted = markers.slice().sort((a, b) => {{
        const pa = priority[a.kind] ?? 99;
        const pb = priority[b.kind] ?? 99;
        return pa - pb || a.day - b.day;
      }});
      return {{
        markers: sorted.slice(0, maxMarkers).sort((a, b) => a.day - b.day),
        hidden: Math.max(0, markers.length - maxMarkers),
      }};
    }}

    function lotTraceMarkerSummaryText(markers, hidden = 0) {{
      if (!markers || !markers.length) return "";
      const counts = new Map();
      markers.forEach((marker) => {{
        const style = lotTraceMarkerStyle(marker.kind);
        counts.set(style.label, (counts.get(style.label) || 0) + 1);
      }});
      const parts = Array.from(counts.entries())
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 5)
        .map(([label, count]) => `${{label}}: ${{count}}`);
      if (hidden > 0) parts.push(`${{hidden}} masques`);
      return parts.join(" | ");
    }}

    function selectedLotTraceMarkersForPlot(plotlyFigure, contextNodeId = "", contextNodeType = "") {{
      const category = lotTracePlotCategory(plotlyFigure, contextNodeType);
      if (category === "none") return [];
      const order = selectedDeferredOrder();
      if (order && contextNodeType !== "edge") {{
        const nodeId = String(order.node_id || "");
        if (nodeId && String(contextNodeId || "") === nodeId && category === "production") {{
          const range = currentTimelineDayRange();
          return deferredOrderDays(order)
            .filter(day => Number.isFinite(day) && day >= range.startDay && day <= range.endDay)
            .map(day => ({{ day, label: "ordre reporte", kind: "delay", category, count: 1, qty: 0, lots: [], eventTypes: ["delay"] }}));
        }}
        return [];
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot || !contextNodeId) return [];
      const relatedLots = new Set(snapshot.relatedLots || [snapshot.lotId]);
      const contextId = String(contextNodeId || "");
      const range = currentTimelineDayRange();
      const markersByKey = new Map();
      function addMarker(day, label, kind, qty = null, lotId = "", eventType = "", itemId = "") {{
        if (!Number.isFinite(day) || day < range.startDay || day > range.endDay) return;
        const markerKind = kind || category;
        const key = `${{day}}|${{markerKind}}`;
        if (!markersByKey.has(key)) {{
          markersByKey.set(key, {{
            day,
            labels: new Set(),
            kind: markerKind,
            category,
            count: 0,
            qty: 0,
            lots: new Set(),
            eventTypes: new Set(),
            itemIds: new Set(),
          }});
        }}
        const marker = markersByKey.get(key);
        marker.labels.add(label);
        marker.count += 1;
        const numericQty = Number(qty);
        if (Number.isFinite(numericQty) && numericQty > 0) marker.qty += numericQty;
        if (lotId) marker.lots.add(String(lotId));
        if (eventType) marker.eventTypes.add(String(eventType));
        if (itemId) marker.itemIds.add(String(itemId));
      }}
      function addEvent(row, label, kind) {{
        const day = lotTraceDay(row);
        if (day === null) return;
        addMarker(day, label, kind, row.qty, row.lot_id, row.event_type, row.item_id);
      }}
      function eventLotIsRelated(row) {{
        return relatedLots.has(String(row.lot_id || ""));
      }}
      function eventAtContext(row) {{
        return eventLotIsRelated(row) && String(row.node_id || "") === contextId;
      }}
      function linkLotIsRelated(row) {{
        return relatedLots.has(String(row.parent_lot_id || "")) || relatedLots.has(String(row.child_lot_id || ""));
      }}
      function qtyKey(value) {{
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric.toFixed(6) : String(value || "");
      }}
      function productionParentKeyFromLink(row) {{
        return [
          lotTraceDay(row) ?? "",
          row.parent_lot_id || "",
          row.parent_node_id || "",
          row.parent_item_id || "",
          row.source_id || "",
          row.production_campaign_id || "",
        ].join("|");
      }}
      function productionChildKeyFromLink(row) {{
        return [
          lotTraceDay(row) ?? "",
          row.child_lot_id || "",
          row.child_node_id || "",
          row.child_item_id || "",
          row.source_id || "",
          row.production_campaign_id || "",
        ].join("|");
      }}
      function productionEventKey(row) {{
        return [
          lotTraceDay(row) ?? "",
          row.lot_id || "",
          row.node_id || "",
          row.item_id || "",
          row.source_id || "",
          row.production_campaign_id || "",
        ].join("|");
      }}
      function transportParentKeyFromLink(row) {{
        return [
          row.parent_lot_id || "",
          row.source_id || "",
          qtyKey(row.parent_qty),
        ].join("|");
      }}
      function transportChildKeyFromLink(row) {{
        return [
          lotTraceDay(row) ?? "",
          row.child_lot_id || "",
          row.child_node_id || "",
          row.child_item_id || "",
          row.source_id || "",
          qtyKey(row.child_qty),
        ].join("|");
      }}
      function transportShipEventKey(row) {{
        return [
          row.lot_id || "",
          row.source_id || "",
          qtyKey(row.qty),
        ].join("|");
      }}
      function transportReceiptEventKey(row) {{
        return [
          lotTraceDay(row) ?? "",
          row.lot_id || "",
          row.node_id || "",
          row.item_id || "",
          row.source_id || "",
          qtyKey(row.qty),
        ].join("|");
      }}
      const productionConsumeKeys = new Set();
      const productionOutputKeys = new Set();
      const transportShipKeys = new Set();
      const transportReceiptKeys = new Set();
      (snapshot.links || []).forEach((row) => {{
        if (!linkLotIsRelated(row)) return;
        const linkType = String(row.link_type || "");
        if (linkType === "production") {{
          productionConsumeKeys.add(productionParentKeyFromLink(row));
          productionOutputKeys.add(productionChildKeyFromLink(row));
        }}
        if (linkType === "transport") {{
          transportShipKeys.add(transportParentKeyFromLink(row));
          transportReceiptKeys.add(transportChildKeyFromLink(row));
        }}
      }});
      function productionConsumeBelongsToTrace(row) {{
        return productionConsumeKeys.has(productionEventKey(row));
      }}
      function productionOutputBelongsToTrace(row) {{
        return productionOutputKeys.has(productionEventKey(row));
      }}
      function transportShipBelongsToTrace(row) {{
        return transportShipKeys.has(transportShipEventKey(row));
      }}
      function transportReceiptBelongsToTrace(row) {{
        return transportReceiptKeys.has(transportReceiptEventKey(row));
      }}
      if (category === "transport") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventLotIsRelated(row)) return;
          if (String(row.event_type || "") !== "lane_ship") return;
          if (!transportShipBelongsToTrace(row)) return;
          if (lotTraceSourceEdgeId(row.source_id) !== contextId) return;
          addEvent(row, "expedition transport", "transport");
        }});
        (snapshot.links || []).forEach((row) => {{
          if (!linkLotIsRelated(row)) return;
          if (String(row.link_type || "") !== "transport") return;
          if (lotTraceSourceEdgeId(row.source_id) !== contextId) return;
          const day = lotTraceDay(row);
          if (day !== null) addMarker(day, "reception transport", "receipt", row.child_qty || row.parent_qty, row.child_lot_id, row.link_type, row.child_item_id || row.parent_item_id);
        }});
      }} else if (category === "production") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "production_output" && productionOutputBelongsToTrace(row)) addEvent(row, "production du lot", "production");
          if (eventType === "production_consume" && productionConsumeBelongsToTrace(row)) addEvent(row, "utilisation composant", "consume");
        }});
      }} else if (category === "factory_input") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "lane_receipt" && transportReceiptBelongsToTrace(row)) addEvent(row, "reception intrant", "receipt");
          if (eventType === "external_procurement_receipt") addEvent(row, "reception intrant", "receipt");
          if (eventType === "production_consume" && productionConsumeBelongsToTrace(row)) addEvent(row, "consommation production", "consume");
          if (eventType === "opening_stock") addEvent(row, "stock initial", "stock");
        }});
      }} else if (category === "factory_output") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "production_output" && productionOutputBelongsToTrace(row)) addEvent(row, "production du lot", "production");
          if (eventType === "lane_ship" && transportShipBelongsToTrace(row)) addEvent(row, "expedition produit", "shipment");
          if (eventType === "opening_stock") addEvent(row, "stock initial", "stock");
        }});
      }} else if (category === "supplier_stock") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "external_procurement_receipt") addEvent(row, "entree stock fournisseur", "receipt");
          if (eventType === "lane_ship" && transportShipBelongsToTrace(row)) addEvent(row, "envoi fournisseur", "shipment");
          if (eventType === "opening_stock") addEvent(row, "stock initial fournisseur", "stock");
        }});
      }} else if (category === "supplier_send") {{
        (snapshot.events || []).forEach((row) => {{
          if (eventAtContext(row) && String(row.event_type || "") === "lane_ship" && transportShipBelongsToTrace(row)) addEvent(row, "envoi fournisseur", "shipment");
        }});
      }} else if (category === "dc_stock") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "lane_receipt" && transportReceiptBelongsToTrace(row)) addEvent(row, "reception DC", "receipt");
          if (eventType === "lane_ship" && transportShipBelongsToTrace(row)) addEvent(row, "expedition DC", "shipment");
          if (eventType === "opening_stock") addEvent(row, "stock initial DC", "stock");
        }});
      }} else if (category === "receipt") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "lane_receipt" && transportReceiptBelongsToTrace(row)) addEvent(row, "reception du lot", "receipt");
          if (eventType === "external_procurement_receipt") addEvent(row, "reception du lot", "receipt");
        }});
      }} else if (category === "shipment") {{
        (snapshot.events || []).forEach((row) => {{
          if (eventAtContext(row) && String(row.event_type || "") === "lane_ship" && transportShipBelongsToTrace(row)) addEvent(row, "expedition du lot", "shipment");
        }});
      }} else if (category === "customer_service") {{
        (snapshot.events || []).forEach((row) => {{
          if (!eventAtContext(row)) return;
          const eventType = String(row.event_type || "");
          if (eventType === "demand_service") addEvent(row, "client servi", "service");
          if (eventType === "lane_receipt" && transportReceiptBelongsToTrace(row)) addEvent(row, "reception client", "receipt");
        }});
      }}
      return Array.from(markersByKey.values())
        .map((marker) => {{
          return {{
            day: marker.day,
            label: Array.from(marker.labels).join(" / "),
            kind: marker.kind,
            category: marker.category,
            count: marker.count,
            qty: marker.qty,
            lots: Array.from(marker.lots),
            eventTypes: Array.from(marker.eventTypes),
            itemIds: Array.from(marker.itemIds),
          }};
        }})
        .sort((a, b) => a.day - b.day || String(a.kind).localeCompare(String(b.kind)));
    }}

    function selectedLotTraceDownstreamContributionByLot(snapshot) {{
      const contributions = new Map();
      const quantities = selectedLotTraceDownstreamContributionQtyByLot(snapshot);
      quantities.forEach((qty, lotId) => {{
        const total = lotTraceLotTotalQty(lotId);
        if (total > 0) {{
          contributions.set(lotId, Math.max(0, Math.min(1, qty / total)));
        }}
      }});
      return contributions;
    }}

    function lotTraceNumericValue(value) {{
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    }}

    function lotTraceLotTotalQty(lotId) {{
      const info = lotTraceLotInfo(lotId);
      const infoQty = lotTraceNumericValue(info && info.qty);
      if (infoQty > 0) return infoQty;
      const rows = lotTraceIndexes.eventsByLot.get(String(lotId || "")) || [];
      const creation = rows.find(row => {{
        const eventType = String(row.event_type || "");
        return ["production_output", "lane_receipt", "external_procurement_receipt", "estimated_source_receipt", "estimated_capacity_receipt", "opening_stock"].includes(eventType);
      }}) || rows[0] || {{}};
      return lotTraceNumericValue(creation.qty);
    }}

    function selectedLotTraceDownstreamContributionQtyByLot(snapshot) {{
      const rootLotId = String((snapshot || {{}}).lotId || "");
      const contributions = new Map();
      if (!rootLotId) return contributions;
      const rootQty = lotTraceLotTotalQty(rootLotId);
      if (rootQty > 0) contributions.set(rootLotId, rootQty);
      const linksByParent = new Map();
      (snapshot.downstreamLinks || []).forEach((link) => {{
        if (String(link.link_type || "") !== "transport") return;
        const parent = String(link.parent_lot_id || "");
        const child = String(link.child_lot_id || "");
        if (!parent || !child) return;
        if (!linksByParent.has(parent)) linksByParent.set(parent, []);
        linksByParent.get(parent).push(link);
      }});
      const queue = [rootLotId];
      let guard = 0;
      while (queue.length && guard < 10000) {{
        guard += 1;
        const parent = queue.shift();
        const parentContribution = contributions.get(parent) || 0;
        if (parentContribution <= 0) continue;
        const parentTotalQty = lotTraceLotTotalQty(parent);
        const parentShare = parentTotalQty > 0 ? Math.max(0, Math.min(1, parentContribution / parentTotalQty)) : 1;
        (linksByParent.get(parent) || []).forEach((link) => {{
          const child = String(link.child_lot_id || "");
          if (!child) return;
          const linkQty = lotTraceNumericValue(link.parent_qty) || lotTraceNumericValue(link.child_qty);
          if (linkQty <= 0) return;
          const tracedLinkQty = linkQty * parentShare;
          if (tracedLinkQty <= 0) return;
          const oldContribution = contributions.get(child) || 0;
          const totalQty = lotTraceLotTotalQty(child);
          const mergedContribution = totalQty > 0
            ? Math.min(totalQty, oldContribution + tracedLinkQty)
            : oldContribution + tracedLinkQty;
          if (mergedContribution > oldContribution + 1e-9) {{
            contributions.set(child, mergedContribution);
            queue.push(child);
          }}
        }});
      }}
      return contributions;
    }}

    function selectedLotTraceContributionInfo(snapshot, lotId) {{
      const lot = String(lotId || "");
      const quantities = selectedLotTraceDownstreamContributionQtyByLot(snapshot);
      const contributionQty = quantities.get(lot) || (lot === String((snapshot || {{}}).lotId || "") ? lotTraceLotTotalQty(lot) : 0);
      const totalQty = lotTraceLotTotalQty(lot);
      const otherQty = Math.max(0, totalQty - contributionQty);
      const share = totalQty > 0 ? Math.max(0, Math.min(1, contributionQty / totalQty)) : 0;
      const parentLinks = lotTraceIndexes.parentsByChild.get(lot) || [];
      return {{
        lotId: lot,
        contributionQty,
        totalQty,
        otherQty,
        share,
        parentCount: parentLinks.length,
        isMixedWithOtherOrigin: otherQty > 1e-6,
        isMergedFromSeveralSelectedLots: otherQty <= 1e-6 && parentLinks.length > 1,
      }};
    }}

    function selectedLotTraceCustomerDemandOverlay(plotlyFigure, contextNodeId = "", contextNodeType = "") {{
      if (lotTracePlotCategory(plotlyFigure, contextNodeType) !== "customer_service") return null;
      if (String(contextNodeType || "") !== "customer") return null;
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot || !contextNodeId) return null;
      const rootInfo = lotTraceLotInfo(snapshot.lotId);
      const rootItem = String(rootInfo.item_id || "");
      if (!rootItem) return null;
      const contextId = String(contextNodeId || "");
      const contributions = selectedLotTraceDownstreamContributionByLot(snapshot);
      const range = currentTimelineDayRange();
      const byDay = new Map();
      (snapshot.events || []).forEach((row) => {{
        if (String(row.node_id || "") !== contextId) return;
        if (String(row.event_type || "") !== "demand_service") return;
        if (String(row.item_id || "") !== rootItem) return;
        const factor = contributions.get(String(row.lot_id || "")) || 0;
        if (factor <= 0) return;
        const day = lotTraceDay(row);
        if (day === null || day < range.startDay || day > range.endDay) return;
        const qty = Number(row.qty);
        if (!Number.isFinite(qty) || qty <= 0) return;
        byDay.set(day, (byDay.get(day) || 0) + qty * factor);
      }});
      const days = Array.from(byDay.keys()).sort((a, b) => a - b);
      if (!days.length) return null;
      const values = days.map(day => byDay.get(day) || 0);
      return {{
        days,
        values,
        total: values.reduce((acc, value) => acc + value, 0),
      }};
    }}

    function selectedLotMapNodes() {{
      const order = selectedDeferredOrder();
      if (order) {{
        const node = nodeById[String(order.node_id || "")];
        return node && Number.isFinite(node.lat) && Number.isFinite(node.lon) ? [node] : [];
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot) return [];
      const seen = new Set();
      return snapshot.nodeIds
        .map(nodeId => nodeById[nodeId])
        .filter((node) => {{
          if (!node || seen.has(node.id)) return false;
          if (!Number.isFinite(node.lat) || !Number.isFinite(node.lon)) return false;
          seen.add(node.id);
          return true;
        }});
    }}

    function selectedLotHighlightTokens() {{
      const order = selectedDeferredOrder();
      if (order) {{
        const tokens = new Set();
        lotTraceAddSetValue(tokens, order.campaign_id);
        lotTraceAddSetValue(tokens, order.node_id);
        lotTraceAddSetValue(tokens, order.output_item_id);
        (order.blocking_input_item_ids || []).forEach(token => lotTraceAddSetValue(tokens, token));
        lotTraceAddSetValue(tokens, order.completed_lot_id);
        return Array.from(tokens).filter(token => String(token || "").length >= 4).slice(0, 80);
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot) return [];
      const tokens = new Set(snapshot.relatedLots);
      snapshot.campaigns.forEach(token => lotTraceAddSetValue(tokens, token));
      snapshot.edgeIds.forEach(token => lotTraceAddSetValue(tokens, token));
      snapshot.nodeIds.forEach(token => lotTraceAddSetValue(tokens, token));
      if (snapshot.rootLot) {{
        lotTraceAddSetValue(tokens, snapshot.rootLot.item_id);
        lotTraceAddSetValue(tokens, snapshot.rootLot.source_id);
      }}
      return Array.from(tokens)
        .filter(token => String(token || "").length >= 4)
        .slice(0, 80);
    }}

    function lotTraceMetricHtml(label, value) {{
      return `
        <div class="lotTraceMetric">
          <div class="lotTraceMetricLabel">${{escapeTableHtml(label)}}</div>
          <div class="lotTraceMetricValue">${{escapeTableHtml(value || "n/a")}}</div>
        </div>
      `;
    }}

    function renderLotTraceEventsTable(rows, limit = 14) {{
      if (!rows.length) return '<div class="lotTraceEmpty">Aucun evenement lot dans la genealogie selectionnee.</div>';
      const visibleRows = rows.slice(0, limit);
      const overflow = rows.length > limit ? `<div class="lotTracePanelMeta">${{rows.length - limit}} lignes supplementaires masquees.</div>` : "";
      return `
        <table class="lotTraceTable">
          <thead><tr><th>J</th><th>Type</th><th>Lot</th><th>Noeud</th><th>Item</th><th class="num">Qte</th><th>Stock contexte</th></tr></thead>
          <tbody>
            ${{visibleRows.map(row => {{
              const stockText = lotTraceEventStockText(row);
              return `
                <tr>
                  <td>${{escapeTableHtml(lotTraceDay(row) ?? "")}}</td>
                  <td>${{escapeTableHtml(lotTraceEventLabel(row.event_type))}}</td>
                  <td>${{escapeTableHtml(row.lot_id || "")}}</td>
                  <td>${{escapeTableHtml(row.node_id || "")}}</td>
                  <td>${{escapeTableHtml(row.item_id || "")}}</td>
                  <td class="num">${{escapeTableHtml(lotTraceQtyText(row.qty))}}</td>
                  <td>${{escapeTableHtml(stockText)}}</td>
                </tr>
              `;
            }}).join("")}}
          </tbody>
        </table>
        ${{overflow}}
      `;
    }}

    function renderLotTraceLinksTable(rows, limit = 10) {{
      if (!rows.length) return '<div class="lotTraceEmpty">Aucun lien parent/enfant pour ce lot.</div>';
      const visibleRows = rows.slice(0, limit);
      const overflow = rows.length > limit ? `<div class="lotTracePanelMeta">${{rows.length - limit}} liens supplementaires masques.</div>` : "";
      return `
        <table class="lotTraceTable">
          <thead><tr><th>J</th><th>Type</th><th>Parent</th><th>Enfant</th><th class="num">Qte parent</th><th class="num">Qte enfant</th><th>Logistique</th></tr></thead>
          <tbody>
            ${{visibleRows.map(row => {{
              const logistics = String(row.link_type || "") === "transport"
                ? lotTraceLogisticsDetailText(row.parent_item_id || row.child_item_id, row.parent_qty || row.child_qty)
                : "";
              return `
                <tr>
                  <td>${{escapeTableHtml(lotTraceDay(row) ?? "")}}</td>
                  <td>${{escapeTableHtml(row.link_type || "")}}</td>
                  <td>${{escapeTableHtml(row.parent_lot_id || "")}}</td>
                  <td>${{escapeTableHtml(row.child_lot_id || "")}}</td>
                  <td class="num">${{escapeTableHtml(lotTraceQtyText(row.parent_qty))}}</td>
                  <td class="num">${{escapeTableHtml(lotTraceQtyText(row.child_qty))}}</td>
                  <td>${{escapeTableHtml(logistics)}}</td>
                </tr>
              `;
            }}).join("")}}
          </tbody>
        </table>
        ${{overflow}}
      `;
    }}

    function lotTraceOtherTransportParentsText(childLotId, currentParentLotId, uom = "") {{
      const parentLinks = lotTraceIndexes.parentsByChild.get(String(childLotId || "")) || [];
      const parts = parentLinks
        .filter(link =>
          String(link.link_type || "") === "transport" &&
          String(link.parent_lot_id || "") !== String(currentParentLotId || "")
        )
        .map(link => {{
          const qty = Number(link.parent_qty || link.child_qty || 0);
          const parentLot = String(link.parent_lot_id || "");
          if (!parentLot || !Number.isFinite(qty) || qty <= 0) return "";
          return `${{lotTraceQtyText(qty)}} ${{uom}} via ${{parentLot}}`.trim();
        }})
        .filter(Boolean);
      return parts.length ? `autre part: ${{parts.join(" + ")}}` : "";
    }}

    function renderLotTraceTransportLinksTable(rows, limit = 40) {{
      const transportRows = (rows || []).filter(row => String(row.link_type || "") === "transport");
      if (!transportRows.length) return '<div class="lotTraceEmpty">Aucun transport visible pour la direction selectionnee.</div>';
      const visibleRows = transportRows.slice(0, limit);
      const overflow = transportRows.length > limit ? `<div class="lotTracePanelMeta">${{transportRows.length - limit}} transports supplementaires masques.</div>` : "";
      return `
        <table class="lotTraceTable">
          <thead><tr><th>J</th><th>Route</th><th>Lot source</th><th>Lot recu</th><th class="num">Part tracee</th><th class="num">Total lot recu</th><th>Lecture lot mixte</th></tr></thead>
          <tbody>
            ${{visibleRows.map(row => {{
              const childLot = String(row.child_lot_id || "");
              const parentLot = String(row.parent_lot_id || "");
              const childInfo = lotTraceLotInfo(childLot);
              const parentInfo = lotTraceLotInfo(parentLot);
              const uom = childInfo.uom || parentInfo.uom || "";
              const tracedQty = Number(row.parent_qty || row.child_qty || 0);
              const totalQty = lotTraceLotTotalQty(childLot) || Number(row.child_qty || tracedQty || 0);
              const otherText = totalQty > tracedQty + 1e-6
                ? lotTraceOtherTransportParentsText(childLot, parentLot, uom)
                : "";
              return `
                <tr>
                  <td>${{escapeTableHtml(lotTraceDay(row) ?? "")}}</td>
                  <td>${{escapeTableHtml(`${{row.parent_node_id || "n/a"}} -> ${{row.child_node_id || "n/a"}} / ${{row.parent_item_id || row.child_item_id || ""}}`)}}</td>
                  <td>${{escapeTableHtml(parentLot)}}</td>
                  <td>${{escapeTableHtml(childLot)}}</td>
                  <td class="num">${{escapeTableHtml(`${{lotTraceQtyText(tracedQty)}} ${{uom}}`)}}</td>
                  <td class="num">${{escapeTableHtml(`${{lotTraceQtyText(totalQty)}} ${{uom}}`)}}</td>
                  <td>${{escapeTableHtml(otherText || "lot non mixte sur ce lien")}}</td>
                </tr>
              `;
            }}).join("")}}
          </tbody>
        </table>
        ${{overflow}}
      `;
    }}

    function lotTraceMixedLotRows(snapshot, selected) {{
      if (!snapshot || !selected) return [];
      const selectedLotSet = new Set(selected.lots || []);
      return (selected.lots || [])
        .map((lotId) => {{
          const info = lotTraceLotInfo(lotId);
          const contribution = selectedLotTraceContributionInfo(snapshot, lotId);
          if (!contribution.isMixedWithOtherOrigin) return null;
          const parentLinks = lotTraceIndexes.parentsByChild.get(String(lotId || "")) || [];
          const otherParents = parentLinks
            .map(link => String(link.parent_lot_id || ""))
            .filter(parentLot => parentLot && !selectedLotSet.has(parentLot));
          return {{
            lotId,
            nodeId: info.node_id || "",
            itemId: info.item_id || "",
            uom: info.uom || "",
            contributionQty: contribution.contributionQty,
            totalQty: contribution.totalQty,
            otherQty: contribution.otherQty,
            share: contribution.share,
            otherParents,
          }};
        }})
        .filter(Boolean)
        .sort((a, b) => String(a.lotId).localeCompare(String(b.lotId)));
    }}

    function renderLotTraceMixedLotsTable(rows, limit = 12) {{
      if (!rows.length) return '<div class="lotTraceEmpty">Aucun lot mixte dans le chemin visible.</div>';
      const visibleRows = rows.slice(0, limit);
      const overflow = rows.length > limit ? `<div class="lotTracePanelMeta">${{rows.length - limit}} lots mixtes masques.</div>` : "";
      return `
        <table class="lotTraceTable">
          <thead><tr><th>Lot aval mixte</th><th>Noeud / item</th><th class="num">Part tracee</th><th class="num">Total lot</th><th class="num">Autre origine</th><th>Origines hors lot selectionne</th></tr></thead>
          <tbody>
            ${{visibleRows.map(row => {{
              const uom = String(row.uom || "");
              const otherParents = (row.otherParents || []).length
                ? row.otherParents.join(", ")
                : "autre lot dans le graphe";
              return `
                <tr>
                  <td>${{escapeTableHtml(row.lotId || "")}}</td>
                  <td>${{escapeTableHtml(`${{row.nodeId || "n/a"}} / ${{row.itemId || "n/a"}}`)}}</td>
                  <td class="num">${{escapeTableHtml(`${{lotTraceQtyText(row.contributionQty)}} ${{uom}} (${{lotTraceQtyText(row.share * 100, 1)}}%)`)}}</td>
                  <td class="num">${{escapeTableHtml(`${{lotTraceQtyText(row.totalQty)}} ${{uom}}`)}}</td>
                  <td class="num">${{escapeTableHtml(`${{lotTraceQtyText(row.otherQty)}} ${{uom}}`)}}</td>
                  <td>${{escapeTableHtml(otherParents)}}</td>
                </tr>
              `;
            }}).join("")}}
          </tbody>
        </table>
        ${{overflow}}
      `;
    }}

    function renderLotTracePlanTable(rows, limit = 8) {{
      if (!rows.length) return '<div class="lotTraceEmpty">Aucun evenement de planification associe.</div>';
      const visibleRows = rows.slice(0, limit);
      const overflow = rows.length > limit ? `<div class="lotTracePanelMeta">${{rows.length - limit}} evenements de plan masques.</div>` : "";
      return `
        <table class="lotTraceTable">
          <thead><tr><th>J</th><th>Evenement</th><th>Campagne</th><th>Raison</th><th class="num">Reel</th><th>Input bloquant</th></tr></thead>
          <tbody>
            ${{visibleRows.map(row => `
              <tr>
                <td>${{escapeTableHtml(lotTraceDay(row) ?? "")}}</td>
                <td>${{escapeTableHtml(lotTraceEventLabel(row.event_type))}}</td>
                <td>${{escapeTableHtml(row.campaign_id || "")}}</td>
                <td>${{escapeTableHtml(row.reason || "")}}</td>
                <td class="num">${{escapeTableHtml(lotTraceQtyText(row.actual_qty))}}</td>
                <td>${{escapeTableHtml(row.binding_input_item_id || "")}}</td>
              </tr>
            `).join("")}}
          </tbody>
        </table>
        ${{overflow}}
      `;
    }}

    function renderDeferredProductionOrdersTable(rows, limit = 18) {{
      if (!rows.length) return '<div class="lotTraceEmpty">Aucun ordre de production reporte sur les PF/PFI visibles.</div>';
      const visibleRows = rows.slice(0, limit);
      const overflow = rows.length > limit ? `<div class="lotTracePanelMeta">${{rows.length - limit}} ordres reportes masques.</div>` : "";
      return `
        <table class="lotTraceTable">
          <thead><tr><th>Statut</th><th>Campagne</th><th>Blocage</th><th>Input</th><th class="num">Lot vise</th><th>Reception</th><th>Lot produit</th></tr></thead>
          <tbody>
            ${{visibleRows.map(row => {{
              const status = String(row.status || "");
              const statusClass = status === "completed_after_delay" ? "completed" : "blocked";
              const delayText = `J${{row.first_delay_day ?? ""}}` + (row.last_delay_day !== row.first_delay_day ? `-J${{row.last_delay_day ?? ""}}` : "");
              const inputText = (row.blocking_input_item_ids || []).join(", ") || "n/a";
              const receiptText = (row.next_expected_receipt_days || []).length ? (row.next_expected_receipt_days || []).map(day => `J${{day}}`).join(", ") : "n/a";
              const completedText = row.completed_lot_id
                ? `${{row.completed_lot_id}} J${{row.completed_day}}`
                : "non produit";
              return `
                <tr>
                  <td><span class="lotTraceStatusPill ${{statusClass}}">${{escapeTableHtml(row.status_label || status || "reporte")}}</span></td>
                  <td>${{escapeTableHtml(row.campaign_id || "")}}</td>
                  <td>${{escapeTableHtml(delayText)}}<br><span class="muted">${{escapeTableHtml(`${{row.delay_days || 0}} j`)}}</span></td>
                  <td>${{escapeTableHtml(inputText)}}</td>
                  <td class="num">${{escapeTableHtml(lotTraceQtyText(row.planned_qty))}}</td>
                  <td>${{escapeTableHtml(receiptText)}}</td>
                  <td>${{escapeTableHtml(completedText)}}</td>
                </tr>
              `;
            }}).join("")}}
          </tbody>
        </table>
        ${{overflow}}
      `;
    }}

    function deferredOrderPlanEvents(order) {{
      if (!order || !order.campaign_id) return [];
      return (lotTraceIndexes.planByCampaign.get(String(order.campaign_id || "")) || [])
        .slice()
        .sort((a, b) => (lotTraceDay(a) ?? 0) - (lotTraceDay(b) ?? 0));
    }}

    function renderDeferredProductionOrderDetail(order) {{
      if (!order) return '<div class="lotTraceEmpty">Aucun ordre reporte selectionne.</div>';
      const inputText = (order.blocking_input_item_ids || []).join(", ") || "n/a";
      const receiptText = (order.next_expected_receipt_days || []).length
        ? (order.next_expected_receipt_days || []).map(day => `J${{day}}`).join(", ")
        : "n/a";
      const completedText = order.completed_lot_id
        ? `${{order.completed_lot_id}} J${{order.completed_day}} - ${{lotTraceQtyText(order.completed_lot_qty)}}`
        : "non produit dans l'horizon";
      const blockedText = `J${{order.first_delay_day ?? ""}}` + (order.last_delay_day !== order.first_delay_day ? `-J${{order.last_delay_day ?? ""}}` : "");
      return `
        <div class="lotTraceSummaryGrid">
          ${{lotTraceMetricHtml("Statut", order.status_label || "reporte")}}
          ${{lotTraceMetricHtml("Campagne", order.campaign_id || "n/a")}}
          ${{lotTraceMetricHtml("Noeud / item", `${{order.node_id || "n/a"}} / ${{order.output_item_id || "n/a"}}`)}}
          ${{lotTraceMetricHtml("Lot vise", lotTraceQtyText(order.planned_qty) || "n/a")}}
          ${{lotTraceMetricHtml("Report", `${{blockedText}} (${{order.delay_days || 0}} j)`)}}
          ${{lotTraceMetricHtml("Input bloquant", inputText)}}
          ${{lotTraceMetricHtml("Reception attendue", receiptText)}}
          ${{lotTraceMetricHtml("Lot produit", completedText)}}
        </div>
        <div class="lotTraceSectionTitle">Evenements de planification de l'ordre</div>
        ${{renderLotTracePlanTable(deferredOrderPlanEvents(order), 18)}}
      `;
    }}

    function renderDeferredProductionOrderGraph(order) {{
      const graphWrap = document.getElementById("lotTraceGraphWrap");
      if (!graphWrap) return;
      if (!order) {{
        graphWrap.innerHTML = '<div class="lotTraceGraphEmpty">Aucun ordre reporte selectionne.</div>';
        return;
      }}
      const events = deferredOrderPlanEvents(order);
      const delayEvents = events.filter(row => String(row.event_type || "").startsWith("delay"));
      const allEventDays = events.map(row => lotTraceDay(row)).filter(day => Number.isFinite(day));
      const receiptDays = (order.next_expected_receipt_days || [])
        .map(value => Number(value))
        .filter(day => Number.isFinite(day));
      const firstDelayDay = Number(order.first_delay_day);
      const lastDelayDay = Number(order.last_delay_day);
      const completedDay = Number(order.completed_day);
      const plannedDay = allEventDays.length
        ? Math.min(...allEventDays)
        : (Number.isFinite(firstDelayDay) ? firstDelayDay : 0);
      const endDayCandidates = [lastDelayDay, completedDay, ...receiptDays, ...allEventDays].filter(day => Number.isFinite(day));
      const endDay = endDayCandidates.length ? Math.max(...endDayCandidates) : plannedDay;
      const inputText = (order.blocking_input_item_ids || []).join(", ") || "input non identifie";
      const receiptText = receiptDays.length ? receiptDays.map(day => `J${{day}}`).join(", ") : "aucune reception identifiee";
      const qtyText = lotTraceQtyText(order.planned_qty) || "n/a";
      const completed = Boolean(order.completed_lot_id);
      const nodes = [
        {{
          id: "order",
          cls: "operation deferredOrder",
          x: 36,
          y: 92,
          w: 214,
          h: 72,
          title: "Ordre planifie",
          line2: `J${{plannedDay}} - ${{order.node_id || "n/a"}}`,
          line3: `${{order.output_item_id || "n/a"}} - lot vise ${{qtyText}}`,
        }},
        {{
          id: "delay",
          cls: "operation deferredDelay",
          x: 300,
          y: 92,
          w: 236,
          h: 72,
          title: "Report rupture input",
          line2: `J${{order.first_delay_day ?? ""}} -> J${{order.last_delay_day ?? ""}} (${{order.delay_days || 0}} j)`,
          line3: `Manque: ${{inputText}}`,
        }},
        {{
          id: "receipt",
          cls: "operation deferredReceipt",
          x: 588,
          y: 92,
          w: 226,
          h: 72,
          title: "Reception input attendue",
          line2: receiptText,
          line3: `Input: ${{inputText}}`,
        }},
        completed
          ? {{
              id: "production",
              cls: "operation deferredDone",
              x: 866,
              y: 92,
              w: 218,
              h: 72,
              title: "Production debloquee",
              line2: `J${{order.completed_day}} - lot complet`,
              line3: `${{lotTraceQtyText(order.completed_lot_qty)}} produit`,
            }}
          : {{
              id: "production",
              cls: "operation deferredBlocked",
              x: 866,
              y: 92,
              w: 218,
              h: 72,
              title: "Toujours bloque",
              line2: "Aucun lot dans l'horizon",
              line3: `Dernier report J${{order.last_delay_day ?? ""}}`,
            }},
        {{
          id: "lot",
          cls: completed ? "root pfStatusStock" : "operation deferredBlocked",
          x: 1136,
          y: 92,
          w: 226,
          h: 72,
          title: completed ? String(order.completed_lot_id || "Lot produit") : "Lot non cree",
          line2: completed ? "Lot PF/PFI cree apres report" : "Pas de lot physique",
          line3: completed
            ? `J${{order.completed_day}} - ${{order.output_item_id || ""}}`
            : "Ordre encore non execute",
        }},
      ];
      const edgePairs = [
        ["order", "delay", "deferred"],
        ["delay", "receipt", "deferred"],
        ["receipt", "production", completed ? "deferredDone" : "deferred"],
        ["production", "lot", completed ? "deferredDone" : "deferred"],
      ];
      const posById = new Map(nodes.map(node => [node.id, node]));
      const edgeSvg = edgePairs.map(([from, to, cls]) => {{
        const a = posById.get(from);
        const b = posById.get(to);
        if (!a || !b) return "";
        const x1 = a.x + a.w;
        const y1 = a.y + a.h / 2;
        const x2 = b.x;
        const y2 = b.y + b.h / 2;
        const mid = Math.max(x1 + 24, (x1 + x2) / 2);
        return `<path class="lotTraceGraphLink ${{cls}}" d="M ${{x1}} ${{y1}} C ${{mid}} ${{y1}}, ${{mid}} ${{y2}}, ${{x2}} ${{y2}}"></path>`;
      }}).join("");
      const nodeSvg = nodes.map(node => `
        <g class="lotTraceGraphNode ${{node.cls}}" transform="translate(${{node.x}},${{node.y}})">
          <rect width="${{node.w}}" height="${{node.h}}"></rect>
          <text x="10" y="20">${{escapeTableHtml(node.title)}}</text>
          <text class="muted" x="10" y="40">${{escapeTableHtml(node.line2)}}</text>
          <text class="muted" x="10" y="58">${{escapeTableHtml(node.line3)}}</text>
        </g>
      `).join("");

      const timelineX = 300;
      const timelineY = 226;
      const timelineW = 784;
      const timelineStart = Math.min(plannedDay, Number.isFinite(firstDelayDay) ? firstDelayDay : plannedDay);
      const timelineEnd = Math.max(timelineStart + 1, endDay);
      const dayToX = (day) => timelineX + ((day - timelineStart) / Math.max(1, timelineEnd - timelineStart)) * timelineW;
      const delayDays = Array.from(new Set(delayEvents.map(row => lotTraceDay(row)).filter(day => Number.isFinite(day)))).sort((a, b) => a - b);
      const delayTickSvg = delayDays.map(day => {{
        const x = dayToX(day);
        return `<line x1="${{x}}" y1="${{timelineY - 20}}" x2="${{x}}" y2="${{timelineY + 20}}" stroke="#dc2626" stroke-width="2"><title>Report J${{day}}</title></line>`;
      }}).join("");
      const receiptTickSvg = receiptDays.map(day => {{
        const x = dayToX(day);
        return `<line x1="${{x}}" y1="${{timelineY - 24}}" x2="${{x}}" y2="${{timelineY + 24}}" stroke="#ea580c" stroke-width="3"><title>Reception attendue J${{day}}</title></line>`;
      }}).join("");
      const completedTickSvg = completed && Number.isFinite(completedDay)
        ? `<line x1="${{dayToX(completedDay)}}" y1="${{timelineY - 28}}" x2="${{dayToX(completedDay)}}" y2="${{timelineY + 28}}" stroke="#16a34a" stroke-width="4"><title>Production J${{completedDay}}</title></line>`
        : "";
      const delayBand = Number.isFinite(firstDelayDay) && Number.isFinite(lastDelayDay)
        ? `<rect x="${{dayToX(firstDelayDay)}}" y="${{timelineY - 8}}" width="${{Math.max(2, dayToX(lastDelayDay) - dayToX(firstDelayDay))}}" height="16" fill="#fee2e2" stroke="#dc2626" stroke-width="1"></rect>`
        : "";
      const switchText = completed
        ? `<div class="lotTracePanelMeta">Le lot physique cree apres report est <strong>${{escapeTableHtml(order.completed_lot_id || "")}}</strong>. Selectionne-le dans la liste pour voir sa genealogie complete amont/aval.</div>`
        : '<div class="lotTracePanelMeta">Aucun lot physique n est cree tant que cet ordre reste reporte.</div>';
      graphWrap.innerHTML = `
        <svg class="lotTraceGraphSvg" width="1410" height="330" viewBox="0 0 1410 330">
          <defs>
            <marker id="lotTraceArrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="#64748b"></path>
            </marker>
          </defs>
          ${{edgeSvg}}
          ${{nodeSvg}}
          <line x1="${{timelineX}}" y1="${{timelineY}}" x2="${{timelineX + timelineW}}" y2="${{timelineY}}" stroke="#94a3b8" stroke-width="1.5"></line>
          ${{delayBand}}
          ${{delayTickSvg}}
          ${{receiptTickSvg}}
          ${{completedTickSvg}}
          <text class="lotTraceGraphTimelineText" x="${{timelineX}}" y="${{timelineY + 44}}">J${{timelineStart}}</text>
          <text class="lotTraceGraphTimelineText" x="${{timelineX + timelineW - 42}}" y="${{timelineY + 44}}">J${{timelineEnd}}</text>
          <text class="lotTraceGraphTimelineText" x="${{timelineX}}" y="${{timelineY - 34}}">Historique du report: traits rouges = jours reportes, orange = reception input, vert = production</text>
        </svg>
        ${{switchText}}
      `;
    }}

    function renderLotTracePanel() {{
      const panel = document.getElementById("lotTracePanel");
      const title = document.getElementById("lotTracePanelTitle");
      const meta = document.getElementById("lotTracePanelMeta");
      const body = document.getElementById("lotTracePanelBody");
      if (!panel || !title || !meta || !body) return;
      const hasTraceSelection = Boolean(LOT_TRACE.available || lotTraceDeferredOrders().length);
      if (!hasTraceSelection || !selectedLotId || currentPanelMode !== "ops") {{
        panel.classList.remove("visible");
        return;
      }}
      const selectedOrder = selectedDeferredOrder();
      if (selectedOrder) {{
        title.textContent = `${{selectedOrder.campaign_id}} - ordre reporte`;
        meta.textContent = `${{selectedOrder.status_label || "Ordre reporte"}} - ${{selectedOrder.delay_days || 0}} jours de report`;
        body.innerHTML = renderDeferredProductionOrderDetail(selectedOrder);
        panel.classList.add("visible");
        return;
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot) {{
        panel.classList.remove("visible");
        return;
      }}
      const root = snapshot.rootLot || {{}};
      title.textContent = `${{selectedLotId}} - ${{lotTraceEventLabel(root.created_event_type)}}`;
      meta.textContent = `${{snapshot.relatedLots.length}} lots relies, ${{snapshot.events.length}} evenements, ${{snapshot.links.length}} liens, ${{snapshot.planEvents.length}} evenements de plan`;
      const creationQty = root.qty !== "" ? `${{lotTraceQtyText(root.qty)}} ${{root.uom || ""}}`.trim() : "n/a";
      const downstreamText = `${{root.downstream_lot_count || 0}} lots, ${{root.downstream_node_count || 0}} noeuds, ${{root.downstream_finished_product_lot_count || 0}} PF`;
      const viewModel = lotTraceViewModelForLot(selectedLotId);
      const viewSummary = (viewModel && viewModel.summary) || {{}};
      const panelSelectedRows = lotTraceRowsForDirection(snapshot);
      const panelMixedLotCount = lotTraceMixedLotRows(snapshot, panelSelectedRows).length;
      const openingStockNote = lotTraceContainsOpeningStock(snapshot.events)
        ? '<div class="lotTraceEmpty">Note: les lots en stock initial demarrent la genealogie a J0; leur origine amont avant J0 n est pas reconstruite dans ce run.</div>'
        : "";
      body.innerHTML = `
        <div class="lotTraceSummaryGrid">
          ${{lotTraceMetricHtml("Type de lot", lotTraceScopeLabel(root))}}
          ${{lotTraceMetricHtml("Parcours aval", downstreamText)}}
          ${{lotTraceMetricHtml("Creation", `J${{root.created_day ?? "n/a"}} - ${{lotTraceEventLabel(root.created_event_type)}}`)}}
          ${{lotTraceMetricHtml("Noeud / item", `${{root.node_id || "n/a"}} / ${{root.item_id || "n/a"}}`)}}
          ${{lotTraceMetricHtml("Quantite initiale", creationQty)}}
          ${{lotTraceMetricHtml("Campagne", root.production_campaign_id || "n/a")}}
          ${{lotTraceMetricHtml("Statut PF", root.pf_availability_status_label || "n/a")}}
          ${{lotTraceMetricHtml("Stock PF restant", root.pf_remaining_stock_qty ? lotTraceQtyText(root.pf_remaining_stock_qty) : "0,0")}}
          ${{lotTraceMetricHtml("Input bloquant", (root.pf_blocking_input_item_ids || []).join(", ") || "aucun")}}
          ${{lotTraceMetricHtml("Transports physiques", Number(viewSummary.transport_group_count || 0) ? `${{viewSummary.transport_group_count}} groupe(s)` : "aucun")}}
          ${{lotTraceMetricHtml("Composants BOM", Number(viewSummary.component_group_count || 0) ? `${{viewSummary.component_group_count}} groupe(s)` : "aucun")}}
          ${{lotTraceMetricHtml("Lots mixtes clients", panelMixedLotCount ? String(panelMixedLotCount) : "aucun")}}
        </div>
        ${{openingStockNote}}
        <div class="lotTraceSectionTitle">Evenements du lot et de sa genealogie</div>
        ${{renderLotTraceEventsTable(snapshot.events)}}
        <div class="lotTraceSectionTitle">Genealogie parent / enfant</div>
        ${{renderLotTraceLinksTable(snapshot.links)}}
        <div class="lotTraceSectionTitle">Replanification associee</div>
        ${{renderLotTracePlanTable(snapshot.planEvents)}}
      `;
      panel.classList.add("visible");
    }}

    function lotTraceRowsForDirection(snapshot) {{
      if (!snapshot) return {{ lots: [], links: [], events: [] }};
      let lotSet = new Set([snapshot.lotId]);
      let links = [];
      if (lotTraceDirection === "upstream") {{
        (snapshot.upstreamLots || []).forEach(lot => lotSet.add(lot));
        links = snapshot.upstreamLinks || [];
      }} else if (lotTraceDirection === "downstream") {{
        (snapshot.downstreamLots || []).forEach(lot => lotSet.add(lot));
        links = snapshot.downstreamLinks || [];
      }} else {{
        (snapshot.upstreamLots || []).forEach(lot => lotSet.add(lot));
        (snapshot.downstreamLots || []).forEach(lot => lotSet.add(lot));
        links = snapshot.links || [];
      }}
      const lots = Array.from(lotSet);
      function eventMatchesDirection(row) {{
        if (lotTraceDirection !== "upstream" && lotTraceDirection !== "downstream") return true;
        function routePartsFromSource(sourceId) {{
          const raw = String(sourceId || "");
          if (!raw.startsWith("edge:")) return {{ src: "", dst: "" }};
          const body = raw.slice(5);
          const marker = "_TO_";
          const markerIdx = body.indexOf(marker);
          if (markerIdx <= 0) return {{ src: "", dst: "" }};
          const src = lotTraceCanonicalNodeId(body.slice(0, markerIdx));
          const rest = body.slice(markerIdx + marker.length);
          const itemSep = rest.lastIndexOf("_");
          const dst = lotTraceCanonicalNodeId(itemSep > 0 ? rest.slice(0, itemSep) : rest);
          return {{ src, dst }};
        }}
        const rootNode = lotTraceCanonicalNodeId((snapshot.rootLot || {{}}).node_id);
        const route = routePartsFromSource(row.source_id);
        const src = lotTraceCanonicalNodeId(route.src || row.node_id || "");
        const dst = lotTraceCanonicalNodeId(route.dst || "");
        if (lotTraceDirection === "upstream" && src === rootNode && dst && dst !== rootNode) return false;
        if (lotTraceDirection === "downstream" && dst === rootNode && src && src !== rootNode) return false;
        return true;
      }}
      const events = (snapshot.events || []).filter(row => lotSet.has(String(row.lot_id || "")) && eventMatchesDirection(row));
      return {{ lots, links, events }};
    }}

    function lotTraceLotInfo(lotId) {{
      const configured = (LOT_TRACE.lots || {{}})[lotId] || null;
      if (configured) return configured;
      const rows = lotTraceIndexes.eventsByLot.get(lotId) || [];
      const first = rows[0] || {{}};
      return {{
        lot_id: lotId,
        trace_scope_label: "Lot stock",
        created_day: lotTraceDay(first) ?? "",
        created_event_type: first.event_type || "",
        node_id: first.node_id || "",
        item_id: first.item_id || "",
        qty: first.qty || "",
        uom: first.uom || "",
      }};
    }}

    function lotTraceScopeLabel(info) {{
      const eventType = String(info && info.created_event_type || "");
      if (eventType === "opening_stock") {{
        return "Stock initial - origine pre-J0 non tracee";
      }}
      return (info && info.trace_scope_label) || lotTraceEventLabel(eventType);
    }}

    function lotTracePfStatusClass(info) {{
      const status = String((info && info.pf_availability_status) || "");
      if (status === "in_finished_stock") return "pfStatusStock";
      if (status === "inputs_available") return "pfStatusAvailable";
      if (status === "input_shortage") return "pfStatusShortage";
      return "";
    }}

    function lotTracePfStatusColor(info) {{
      const status = String((info && info.pf_availability_status) || "");
      if (status === "in_finished_stock") return "#15803d";
      if (status === "inputs_available") return "#c2410c";
      if (status === "input_shortage") return "#b91c1c";
      return "";
    }}

    function lotTracePfStatusShortLabel(info) {{
      const status = String((info && info.pf_availability_status) || "");
      if (status === "in_finished_stock") return "VERT - stock PF";
      if (status === "inputs_available") return "ORANGE - inputs OK";
      if (status === "input_shortage") return "ROUGE - input insuffisant";
      return "";
    }}

    function lotTraceContainsOpeningStock(rows) {{
      return (rows || []).some(row => String(row.event_type || "") === "opening_stock");
    }}

    function lotTraceGraphLevels(snapshot, links, lots) {{
      const levels = new Map([[snapshot.lotId, 0]]);
      let changed = true;
      let guard = 0;
      while (changed && guard < 200) {{
        changed = false;
        guard += 1;
        links.forEach((link) => {{
          const parent = String(link.parent_lot_id || "");
          const child = String(link.child_lot_id || "");
          if (!parent || !child) return;
          if (levels.has(child) && !levels.has(parent)) {{
            levels.set(parent, Number(levels.get(child)) - 1);
            changed = true;
          }}
          if (levels.has(parent) && !levels.has(child)) {{
            levels.set(child, Number(levels.get(parent)) + 1);
            changed = true;
          }}
        }});
      }}
      lots.forEach(lot => {{
        if (!levels.has(lot)) levels.set(lot, 0);
      }});
      const minLevel = Math.min(...Array.from(levels.values()));
      const normalized = new Map();
      levels.forEach((level, lot) => {{
        normalized.set(lot, level - minLevel);
      }});
      return normalized;
    }}

    function renderLotTraceGraph(snapshot) {{
      const graphWrap = document.getElementById("lotTraceGraphWrap");
      if (!graphWrap) return;
      graphWrap.innerHTML = "";
      if (!snapshot) {{
        graphWrap.innerHTML = '<div class="lotTraceGraphEmpty">Selectionne un lot PF, PFI ou MP trace pour afficher son graphe.</div>';
        return;
      }}
      const selected = lotTraceRowsForDirection(snapshot);
      if (selected.lots.length <= 1 && !selected.links.length) {{
        graphWrap.innerHTML = '<div class="lotTraceGraphEmpty">Ce lot n a pas de relation amont/aval dans la direction choisie.</div>';
        return;
      }}
      const maxGraphLots = 140;
      const visibleLots = selected.lots.slice(0, maxGraphLots);
      const visibleLotSet = new Set(visibleLots);
      const visibleLinks = selected.links.filter(link =>
        visibleLotSet.has(String(link.parent_lot_id || "")) && visibleLotSet.has(String(link.child_lot_id || ""))
      );
      const lotLevels = lotTraceGraphLevels(snapshot, visibleLinks, visibleLots);
      const visualNodes = [];
      const visualNodeById = new Map();
      function rememberVisualNode(node) {{
        if (!node || !node.id || visualNodeById.has(node.id)) return;
        visualNodeById.set(node.id, node);
        visualNodes.push(node);
      }}
      visibleLots.forEach((lotId) => {{
        rememberVisualNode({{
          id: `lot:${{lotId}}`,
          kind: "lot",
          lotId,
          level: Number(lotLevels.get(lotId) || 0) * 2,
        }});
      }});
      function lotTraceOperationLabel(link) {{
        const type = String(link.link_type || "");
        if (type === "production") return "Production";
        if (type === "transport") {{
          return lotTraceTransportKind(link.parent_node_id, link.child_node_id, link.parent_item_id);
        }}
        return lotTraceEventLabel(type);
      }}
      function lotTraceOperationDetail(link) {{
        const type = String(link.link_type || "");
        if (type === "production") {{
          return `${{lotTraceDisplayNodeId(link.parent_node_id)}} - ${{link.parent_item_id || "n/a"}} -> ${{link.child_item_id || "n/a"}}`;
        }}
        if (type === "transport") {{
          return `${{lotTraceDisplayNodeId(link.parent_node_id)}} -> ${{lotTraceDisplayNodeId(link.child_node_id)}} - ${{link.parent_item_id || "n/a"}}`;
        }}
        return `${{lotTraceDisplayNodeId(link.parent_node_id)}} -> ${{lotTraceDisplayNodeId(link.child_node_id)}}`;
      }}
      function lotTraceCompactItemId(itemId) {{
        return String(itemId || "n/a").replace(/^item:/, "");
      }}
      function lotTraceGroupedProductionSummary(links, fallbackLink) {{
        const linkRows = Array.isArray(links) && links.length ? links : [fallbackLink || {{}}];
        const childQty = lotTraceQtyText((fallbackLink || {{}}).child_qty);
        const childItem = lotTraceCompactItemId((fallbackLink || {{}}).child_item_id);
        const childNode = lotTraceDisplayNodeId((fallbackLink || {{}}).child_node_id);
        const byItem = new Map();
        linkRows.forEach((row) => {{
          const item = lotTraceCompactItemId(row.parent_item_id);
          const lot = String(row.parent_lot_id || "");
          const qty = Number(row.parent_qty || 0);
          if (!byItem.has(item)) byItem.set(item, {{ item, lots: new Set(), qty: 0 }});
          const acc = byItem.get(item);
          if (lot) acc.lots.add(lot);
          if (Number.isFinite(qty)) acc.qty += qty;
        }});
        const rows = Array.from(byItem.values()).sort((a, b) => String(a.item).localeCompare(String(b.item)));
        const componentText = rows
          .map(row => `${{row.item}}: ${{lotTraceQtyText(row.qty)}} (${{row.lots.size}} lot${{row.lots.size > 1 ? "s" : ""}})`)
          .join("; ");
        const detail = `${{childNode}} - ${{childItem}}`;
        const qty = `${{linkRows.length}} lot${{linkRows.length > 1 ? "s" : ""}} / ${{rows.length}} ref -> ${{childQty || "n/a"}}`;
        return {{ detail, qty, componentText }};
      }}
      function lotTraceNodeType(nodeId) {{
        return String(((nodeById[lotTraceCanonicalNodeId(nodeId)] || {{}}).type) || "");
      }}
      function lotTraceRoutePartsFromSource(sourceId) {{
        const raw = String(sourceId || "");
        if (!raw.startsWith("edge:")) return {{ src: "", dst: "" }};
        const body = raw.slice(5);
        const marker = "_TO_";
        const markerIdx = body.indexOf(marker);
        if (markerIdx <= 0) return {{ src: "", dst: "" }};
        const src = lotTraceCanonicalNodeId(body.slice(0, markerIdx));
        const rest = body.slice(markerIdx + marker.length);
        const itemSep = rest.lastIndexOf("_");
        const dst = lotTraceCanonicalNodeId(itemSep > 0 ? rest.slice(0, itemSep) : rest);
        return {{ src, dst }};
      }}
      function lotTraceTransportKind(srcId, dstId, itemId = "") {{
        const srcType = lotTraceNodeType(srcId);
        const dstType = lotTraceNodeType(dstId);
        const src = lotTraceCanonicalNodeId(srcId);
        const dst = lotTraceCanonicalNodeId(dstId);
        if (srcType === "supplier_dc" && dstType === "factory") {{
          return lotTraceIsUpstreamInternalSite(dst) ? "Transport fournisseur -> site semi-fini" : "Transport fournisseur -> usine";
        }}
        if (srcType === "factory" && dstType === "factory") {{
          return lotTraceIsUpstreamInternalSite(src) || lotTraceIsUpstreamInternalSite(dst)
            ? "Transport semi-fini -> usine"
            : "Transport inter-usines";
        }}
        if (srcType === "factory" && dstType === "distribution_center") return "Transport usine -> DC";
        if (srcType === "distribution_center" && dstType === "customer") return "Transport DC -> client";
        if (srcType === "supplier_dc") return "Transport fournisseur";
        return "Transport logistique";
      }}
      function lotTraceRouteFromSource(sourceId, fallbackNodeId = "") {{
        const raw = String(sourceId || "");
        if (raw.startsWith("edge:")) {{
          const route = lotTraceRoutePartsFromSource(raw);
          if (route.src || route.dst) return `${{lotTraceDisplayNodeId(route.src)}} -> ${{lotTraceDisplayNodeId(route.dst)}}`;
          const body = raw.slice(5);
          return body;
        }}
        return fallbackNodeId || raw || "flux inconnu";
      }}
      function lotTraceStockContext(nodeId, itemId, day) {{
        const dayNum = Number(day);
        if (!Number.isFinite(dayNum)) return null;
        const rawNode = String(nodeId || "");
        const canonicalNode = lotTraceCanonicalNodeId(rawNode);
        const item = String(itemId || "");
        const contexts = LOT_TRACE.stock_context || {{}};
        return contexts[`${{canonicalNode}}|${{item}}|${{Math.round(dayNum)}}`]
          || contexts[`${{rawNode}}|${{item}}|${{Math.round(dayNum)}}`]
          || null;
      }}
      function lotTraceStockContextText(context) {{
        if (!context) return "";
        const before = Number(context.before_qty);
        const after = Number(context.after_qty);
        const delta = Number(context.delta_qty);
        const hasBeforeAfter = Number.isFinite(before) && Number.isFinite(after);
        const base = hasBeforeAfter
          ? `${{lotTraceQtyText(before)}} -> ${{lotTraceQtyText(after)}}`
          : (Number.isFinite(after) ? `apres ${{lotTraceQtyText(after)}}` : "");
        const deltaText = Number.isFinite(delta) && Math.abs(delta) > 1e-9
          ? ` (${{delta > 0 ? "+" : ""}}${{lotTraceQtyText(delta)}})`
          : "";
        return base ? `${{context.label || "stock"}}: ${{base}}${{deltaText}}` : "";
      }}
      function lotTraceTransportDayText(row) {{
        const shipStart = row.shipFirstDay;
        const shipEnd = row.shipLastDay;
        const receiptStart = row.receiptFirstDay;
        const receiptEnd = row.receiptLastDay;
        function rangeText(label, start, end) {{
          if (!Number.isFinite(Number(start))) return "";
          return start === end ? `${{label}} J${{start}}` : `${{label}} J${{start}}-${{end}}`;
        }}
        const parts = [
          rangeText("depart", shipStart, shipEnd),
          rangeText("arrivee", receiptStart, receiptEnd),
        ].filter(Boolean);
        if (parts.length) return parts.join(" / ");
        return row.firstDay === row.lastDay ? `J${{row.firstDay ?? ""}}` : `J${{row.firstDay ?? ""}}-${{row.lastDay ?? ""}}`;
      }}
      function lotTraceEndpointLabel(row) {{
        const dstType = lotTraceNodeType(row.dst);
        const dst = lotTraceDisplayNodeId(row.dst);
        if (dstType === "distribution_center") return `${{dst}} - stock DC`;
        if (dstType === "customer") return `${{dst}} - client`;
        if (dstType === "factory") return `${{dst}} - stock usine`;
        if (dstType === "supplier_dc") return `${{dst}} - stock fournisseur`;
        return `${{dst}} - stock`;
      }}
      function lotTraceSourceLabel(row) {{
        const srcType = lotTraceNodeType(row.src);
        const src = lotTraceDisplayNodeId(row.src);
        if (srcType === "supplier_dc") return `${{src}} - fournisseur`;
        if (srcType === "factory") return `${{src}} - stock amont usine`;
        if (srcType === "distribution_center") return `${{src}} - stock DC`;
        return `${{src}} - source amont`;
      }}
      function lotTraceSourceStockText(row) {{
        const day = Number.isFinite(Number(row.shipFirstDay)) ? row.shipFirstDay : row.firstDay;
        const context = lotTraceStockContext(row.src, row.item, day);
        const stockText = lotTraceStockContextText(context);
        if (stockText) return stockText;
        const shipped = Number(row.shippedQty || row.receivedQty || 0);
        if (Number.isFinite(shipped) && shipped > 0) {{
          return `sortie lot: ${{lotTraceQtyText(shipped)}} ${{row.uom || ""}}`.trim();
        }}
        return "stock source n/a";
      }}
      function lotTraceEndpointStockText(row) {{
        const day = Number.isFinite(Number(row.receiptLastDay)) ? row.receiptLastDay : row.lastDay;
        const context = lotTraceStockContext(row.dst, row.item, day);
        const stockText = lotTraceStockContextText(context);
        if (stockText) return stockText;
        const qtyText = lotTraceTransportQtySummary(row);
        return qtyText ? `lot recu: ${{qtyText}}` : "";
      }}
      function lotTraceEndpointServiceText(row) {{
        const dstType = lotTraceNodeType(row.dst);
        const childLots = Array.from(row.childLotIds || []);
        if (dstType !== "customer" || !childLots.length) return "";
        const serviceDays = [];
        let servedQty = 0;
        childLots.forEach((lotId) => {{
          const factorInfo = selectedLotTraceContributionInfo(snapshot, lotId);
          const factor = factorInfo.totalQty > 0 ? factorInfo.contributionQty / factorInfo.totalQty : 1;
          (lotTraceIndexes.eventsByLot.get(lotId) || []).forEach((event) => {{
            if (String(event.event_type || "") !== "demand_service") return;
            const day = lotTraceDay(event);
            if (day !== null) serviceDays.push(day);
            const qty = Number(event.qty);
            if (Number.isFinite(qty)) servedQty += qty * factor;
          }});
        }});
        if (!serviceDays.length) return "client pas encore servi";
        const minDay = Math.min(...serviceDays);
        const maxDay = Math.max(...serviceDays);
        const dayText = minDay === maxDay ? `J${{minDay}}` : `J${{minDay}}-${{maxDay}}`;
        return `client servi ${{dayText}}: ${{lotTraceQtyText(servedQty)}}`;
      }}
      function lotTraceTransportSummaryRows(selected) {{
        const groups = new Map();
        const contributionQtyByLot = selectedLotTraceDownstreamContributionQtyByLot(snapshot);
        function transportLinkIdentity(link) {{
          return [
            lotTraceDay(link) ?? "",
            link.parent_lot_id || "",
            link.child_lot_id || "",
            link.source_id || "",
          ].join("|");
        }}
        const upstreamTransportLinks = new Set(
          (snapshot.upstreamLinks || [])
            .filter(link => String(link.link_type || "") === "transport")
            .map(transportLinkIdentity)
        );
        const downstreamTransportLinks = new Set(
          (snapshot.downstreamLinks || [])
            .filter(link => String(link.link_type || "") === "transport")
            .map(transportLinkIdentity)
        );
        function transportLinkSide(link) {{
          const identity = transportLinkIdentity(link);
          const isUpstream = upstreamTransportLinks.has(identity);
          const isDownstream = downstreamTransportLinks.has(identity);
          if (isUpstream && !isDownstream) return "upstream";
          if (isDownstream && !isUpstream) return "downstream";
          return "context";
        }}
        function transportEventSide(src, dst) {{
          const rootNode = lotTraceCanonicalNodeId((snapshot.rootLot || {{}}).node_id);
          if (lotTraceCanonicalNodeId(dst) === rootNode && lotTraceCanonicalNodeId(src) !== rootNode) return "upstream";
          if (lotTraceCanonicalNodeId(src) === rootNode && lotTraceCanonicalNodeId(dst) !== rootNode) return "downstream";
          return "context";
        }}
        function remember(keyParts, update) {{
          const key = keyParts.join("|");
          if (!groups.has(key)) {{
            groups.set(key, {{
              category: keyParts[0],
              src: keyParts[1],
              dst: keyParts[2],
              item: keyParts[3],
              shippedCount: 0,
              receivedCount: 0,
              shippedQty: 0,
              receivedQty: 0,
              lotIds: new Set(),
              childLotIds: new Set(),
              childContributionByLot: new Map(),
              childTotalByLot: new Map(),
              uom: "",
              firstDay: null,
              lastDay: null,
              shipFirstDay: null,
              shipLastDay: null,
              receiptFirstDay: null,
              receiptLastDay: null,
              sideCounts: {{ upstream: 0, downstream: 0, context: 0 }},
            }});
          }}
          const row = groups.get(key);
          update(row);
        }}
        function rememberDay(row, day) {{
          if (day === null) return;
          row.firstDay = row.firstDay === null ? day : Math.min(row.firstDay, day);
          row.lastDay = row.lastDay === null ? day : Math.max(row.lastDay, day);
        }}
        function rememberRange(row, prefix, day) {{
          if (day === null) return;
          const firstKey = `${{prefix}}FirstDay`;
          const lastKey = `${{prefix}}LastDay`;
          row[firstKey] = row[firstKey] === null ? day : Math.min(row[firstKey], day);
          row[lastKey] = row[lastKey] === null ? day : Math.max(row[lastKey], day);
        }}
        (selected.links || []).forEach((link) => {{
          if (String(link.link_type || "") !== "transport") return;
          const src = String(link.parent_node_id || "");
          const dst = String(link.child_node_id || "");
          const item = String(link.parent_item_id || link.child_item_id || "");
          const category = lotTraceTransportKind(src, dst, item);
          remember([category, src, dst, item], (row) => {{
            row.receivedCount += 1;
            row.sideCounts[transportLinkSide(link)] += 1;
            [link.parent_lot_id, link.child_lot_id].forEach(lotId => {{
              const text = String(lotId || "");
              if (!text) return;
              row.lotIds.add(text);
              const lotInfo = lotTraceLotInfo(text);
              if (!row.uom && lotInfo.uom) row.uom = lotInfo.uom;
            }});
            const qty = Number(link.parent_qty);
            if (Number.isFinite(qty)) row.receivedQty += qty;
            const childLotId = String(link.child_lot_id || "");
            if (childLotId) {{
              row.childLotIds.add(childLotId);
              const childContributionQty = Number(link.parent_qty || link.child_qty || 0);
              const existingContribution = row.childContributionByLot.get(childLotId) || 0;
              if (Number.isFinite(childContributionQty) && childContributionQty > 0) {{
                row.childContributionByLot.set(childLotId, existingContribution + childContributionQty);
              }} else if (contributionQtyByLot.has(childLotId)) {{
                row.childContributionByLot.set(childLotId, Math.max(existingContribution, contributionQtyByLot.get(childLotId) || 0));
              }}
              const totalQty = lotTraceLotTotalQty(childLotId);
              if (totalQty > 0) row.childTotalByLot.set(childLotId, totalQty);
            }}
            rememberDay(row, lotTraceDay(link));
            rememberRange(row, "receipt", lotTraceDay(link));
          }});
        }});
        (selected.events || []).forEach((event) => {{
          if (String(event.event_type || "") !== "lane_ship") return;
          const route = lotTraceRoutePartsFromSource(event.source_id);
          const src = route.src || String(event.node_id || "");
          const dst = route.dst || "";
          const item = String(event.item_id || "");
          const category = lotTraceTransportKind(src, dst, item);
          remember([category, src, dst, item], (row) => {{
            row.shippedCount += 1;
            row.sideCounts[transportEventSide(src, dst)] += 1;
            const lotId = String(event.lot_id || "");
            if (lotId) {{
              row.lotIds.add(lotId);
              const lotInfo = lotTraceLotInfo(lotId);
              if (!row.uom && lotInfo.uom) row.uom = lotInfo.uom;
            }}
            const qty = Number(event.qty);
            if (Number.isFinite(qty)) row.shippedQty += qty;
            rememberDay(row, lotTraceDay(event));
            rememberRange(row, "ship", lotTraceDay(event));
          }});
        }});
        return Array.from(groups.values()).map(row => {{
          const counts = row.sideCounts || {{ upstream: 0, downstream: 0, context: 0 }};
          row.side = counts.upstream >= counts.downstream && counts.upstream > 0
            ? "upstream"
            : (counts.downstream > 0 ? "downstream" : "context");
          const childLots = Array.from(row.childLotIds || []);
          row.childLotCount = childLots.length;
          row.childContributionQty = childLots.reduce((acc, lotId) => acc + (row.childContributionByLot.get(lotId) || 0), 0);
          row.childTotalQty = childLots.reduce((acc, lotId) => acc + (row.childTotalByLot.get(lotId) || 0), 0);
          row.mixedLotIds = childLots.filter(lotId => {{
            const total = row.childTotalByLot.get(lotId) || 0;
            const contribution = row.childContributionByLot.get(lotId) || 0;
            return total > contribution + 1e-6;
          }});
          row.mergedLotIds = childLots.filter(lotId => {{
            const total = row.childTotalByLot.get(lotId) || 0;
            const contribution = row.childContributionByLot.get(lotId) || 0;
            const parentLinks = lotTraceIndexes.parentsByChild.get(lotId) || [];
            return total <= contribution + 1e-6 && parentLinks.length > 1;
          }});
          const lotIds = Array.from(row.lotIds || []);
          row.lotText = lotIds.length <= 2
            ? lotIds.join(", ")
            : `${{lotIds.slice(0, 2).join(", ")}} +${{lotIds.length - 2}} lots`;
          return row;
        }}).sort((a, b) =>
          String(a.category).localeCompare(String(b.category)) ||
          String(a.src).localeCompare(String(b.src)) ||
          String(a.dst).localeCompare(String(b.dst)) ||
          String(a.item).localeCompare(String(b.item))
        );
      }}
      function lotTraceTransportRowStartsFromRoot(row, snapshot) {{
        const rootNode = lotTraceCanonicalNodeId(((snapshot || {{}}).rootLot || {{}}).node_id);
        return Boolean(rootNode) && lotTraceCanonicalNodeId(row.src) === rootNode && lotTraceCanonicalNodeId(row.dst) !== rootNode;
      }}
      function lotTraceTransportRowArrivesAtRoot(row, snapshot) {{
        const rootNode = lotTraceCanonicalNodeId(((snapshot || {{}}).rootLot || {{}}).node_id);
        return Boolean(rootNode) && lotTraceCanonicalNodeId(row.dst) === rootNode && lotTraceCanonicalNodeId(row.src) !== rootNode;
      }}
      function lotTraceIsUpstreamTransportRow(row, snapshot) {{
        if (row.side === "upstream") return true;
        if (row.side === "downstream") return false;
        if (lotTraceTransportRowStartsFromRoot(row, snapshot)) return false;
        if (lotTraceTransportRowArrivesAtRoot(row, snapshot)) return true;
        return true;
      }}
      function lotTraceIsDownstreamTransportRow(row, snapshot) {{
        if (row.side === "downstream") return true;
        if (row.side === "upstream") return false;
        if (lotTraceTransportRowStartsFromRoot(row, snapshot)) return true;
        if (lotTraceTransportRowArrivesAtRoot(row, snapshot)) return false;
        return true;
      }}
      function lotTraceTransportRowsForDirection(rows, snapshot, direction) {{
        if (direction === "upstream") return (rows || []).filter(row => lotTraceIsUpstreamTransportRow(row, snapshot));
        if (direction === "downstream") return (rows || []).filter(row => lotTraceIsDownstreamTransportRow(row, snapshot));
        return rows || [];
      }}
      function lotTraceTransportLinkToIndividualRow(link) {{
        const src = String(link.parent_node_id || "");
        const dst = String(link.child_node_id || "");
        const item = String(link.parent_item_id || link.child_item_id || "");
        const parentLotId = String(link.parent_lot_id || "");
        const childLotId = String(link.child_lot_id || "");
        const day = lotTraceDay(link);
        const contributionQty = Number(link.parent_qty || link.child_qty || 0);
        const childTotalQty = lotTraceLotTotalQty(childLotId);
        const parentInfo = lotTraceLotInfo(parentLotId);
        const childInfo = lotTraceLotInfo(childLotId);
        const uom = childInfo.uom || parentInfo.uom || "";
        const otherParts = (lotTraceIndexes.parentsByChild.get(childLotId) || [])
          .filter(parentLink =>
            String(parentLink.link_type || "") === "transport" &&
            String(parentLink.parent_lot_id || "") !== parentLotId
          )
          .map(parentLink => {{
            const qty = Number(parentLink.parent_qty || parentLink.child_qty || 0);
            return {{
              lotId: String(parentLink.parent_lot_id || ""),
              qty: Number.isFinite(qty) ? qty : 0,
            }};
          }})
          .filter(part => part.lotId && part.qty > 1e-9);
        const otherText = otherParts.length
          ? `autre part: ${{otherParts.map(part => `${{lotTraceQtyText(part.qty)}} ${{uom}} via ${{part.lotId}}`).join(" + ")}}`
          : "";
        const row = {{
          individualLink: true,
          category: lotTraceTransportKind(src, dst, item),
          src,
          dst,
          item,
          parentLotId,
          childLotId,
          shippedCount: 0,
          receivedCount: 1,
          shippedQty: 0,
          receivedQty: Number.isFinite(contributionQty) ? contributionQty : 0,
          lotIds: new Set([parentLotId, childLotId].filter(Boolean)),
          childLotIds: new Set([childLotId].filter(Boolean)),
          childContributionByLot: new Map(),
          childTotalByLot: new Map(),
          uom,
          firstDay: day,
          lastDay: day,
          shipFirstDay: null,
          shipLastDay: null,
          receiptFirstDay: day,
          receiptLastDay: day,
          side: "downstream",
          mixedOtherText: otherText,
        }};
        if (childLotId) {{
          row.childContributionByLot.set(childLotId, Number.isFinite(contributionQty) ? contributionQty : 0);
          if (childTotalQty > 0) row.childTotalByLot.set(childLotId, childTotalQty);
        }}
        row.childLotCount = childLotId ? 1 : 0;
        row.childContributionQty = Number.isFinite(contributionQty) ? contributionQty : 0;
        row.childTotalQty = childTotalQty > 0 ? childTotalQty : row.childContributionQty;
        row.mixedLotIds = childTotalQty > row.childContributionQty + 1e-6 ? [childLotId] : [];
        row.mergedLotIds = [];
        row.lotText = parentLotId && childLotId ? `${{parentLotId}} -> ${{childLotId}}` : (childLotId || parentLotId || "");
        return row;
      }}
      function lotTraceDownstreamIndividualTransportRows(snapshot) {{
        const rows = (snapshot.downstreamLinks || [])
          .filter(link => String(link.link_type || "") === "transport")
          .map(lotTraceTransportLinkToIndividualRow)
        return lotTraceConsolidatePhysicalTransportRows(rows)
          .sort((a, b) =>
            Number(a.firstDay ?? 0) - Number(b.firstDay ?? 0) ||
            String(a.parentLotId || "").localeCompare(String(b.parentLotId || "")) ||
            String(a.childLotId || "").localeCompare(String(b.childLotId || ""))
          );
      }}
      function lotTraceTransportPhysicalGroupKey(row) {{
        return [
          row.category || "",
          lotTraceCanonicalNodeId(row.src),
          lotTraceCanonicalNodeId(row.dst),
          row.item || "",
          Number.isFinite(Number(row.firstDay)) ? Number(row.firstDay) : "",
        ].join("|");
      }}
      function lotTraceCanConsolidatePhysicalTransport(rows) {{
        if (!Array.isArray(rows) || rows.length < 2) return false;
        const first = rows[0] || {{}};
        const totalQty = rows.reduce((acc, row) => acc + Math.max(0, Number(row.receivedQty || row.childContributionQty || 0) || 0), 0);
        const estimate = lotTraceLogisticsEstimate(first.item, totalQty);
        return Boolean(estimate && estimate.maxTrucks <= 1);
      }}
      function lotTraceBuildPhysicalTransportGroup(rows) {{
        const childRows = (rows || []).slice().sort((a, b) =>
          String(a.parentLotId || "").localeCompare(String(b.parentLotId || "")) ||
          String(a.childLotId || "").localeCompare(String(b.childLotId || ""))
        );
        if (childRows.length <= 1) return childRows[0] || null;
        const first = childRows[0] || {{}};
        const lotIds = new Set();
        const parentLotIds = new Set();
        const childLotIds = new Set();
        const childContributionByLot = new Map();
        const childTotalByLot = new Map();
        let receivedQty = 0;
        let shippedQty = 0;
        let firstDay = null;
        let lastDay = null;
        let receiptFirstDay = null;
        let receiptLastDay = null;
        let shipFirstDay = null;
        let shipLastDay = null;
        let uom = first.uom || "";
        childRows.forEach((row) => {{
          [row.parentLotId, row.childLotId].forEach(lotId => {{
            const text = String(lotId || "");
            if (text) lotIds.add(text);
          }});
          if (row.parentLotId) parentLotIds.add(String(row.parentLotId));
          if (row.childLotId) childLotIds.add(String(row.childLotId));
          if (!uom && row.uom) uom = row.uom;
          const qty = Number(row.receivedQty || row.childContributionQty || 0);
          if (Number.isFinite(qty)) receivedQty += qty;
          const shipQty = Number(row.shippedQty || 0);
          if (Number.isFinite(shipQty)) shippedQty += shipQty;
          const childLotId = String(row.childLotId || "");
          if (childLotId) {{
            const contribution = Number(row.childContributionQty || row.receivedQty || 0);
            const total = Number(row.childTotalQty || contribution || 0);
            childContributionByLot.set(childLotId, (childContributionByLot.get(childLotId) || 0) + (Number.isFinite(contribution) ? contribution : 0));
            if (Number.isFinite(total) && total > 0) childTotalByLot.set(childLotId, total);
          }}
          [row.firstDay, row.lastDay].forEach(dayValue => {{
            const day = Number(dayValue);
            if (!Number.isFinite(day)) return;
            firstDay = firstDay === null ? day : Math.min(firstDay, day);
            lastDay = lastDay === null ? day : Math.max(lastDay, day);
          }});
          [row.receiptFirstDay, row.receiptLastDay].forEach(dayValue => {{
            const day = Number(dayValue);
            if (!Number.isFinite(day)) return;
            receiptFirstDay = receiptFirstDay === null ? day : Math.min(receiptFirstDay, day);
            receiptLastDay = receiptLastDay === null ? day : Math.max(receiptLastDay, day);
          }});
          [row.shipFirstDay, row.shipLastDay].forEach(dayValue => {{
            const day = Number(dayValue);
            if (!Number.isFinite(day)) return;
            shipFirstDay = shipFirstDay === null ? day : Math.min(shipFirstDay, day);
            shipLastDay = shipLastDay === null ? day : Math.max(shipLastDay, day);
          }});
        }});
        const childLots = Array.from(childLotIds);
        const parentLots = Array.from(parentLotIds);
        const childContributionQty = childLots.reduce((acc, lotId) => acc + (childContributionByLot.get(lotId) || 0), 0);
        const childTotalQty = childLots.reduce((acc, lotId) => acc + (childTotalByLot.get(lotId) || 0), 0);
        const mixedLotIds = childLots.filter(lotId => {{
          const total = childTotalByLot.get(lotId) || 0;
          const contribution = childContributionByLot.get(lotId) || 0;
          return total > contribution + 1e-6;
        }});
        return {{
          ...first,
          physicalTransportGroup: true,
          individualLink: true,
          childRows,
          category: first.category,
          src: first.src,
          dst: first.dst,
          item: first.item,
          parentLotId: parentLots.length === 1 ? parentLots[0] : "",
          parentLotIds: parentLots,
          childLotId: "",
          childLotIds,
          lotIds,
          childContributionByLot,
          childTotalByLot,
          receivedCount: childRows.length,
          shippedCount: childRows.reduce((acc, row) => acc + Number(row.shippedCount || 0), 0),
          receivedQty,
          shippedQty,
          uom,
          firstDay,
          lastDay,
          receiptFirstDay,
          receiptLastDay,
          shipFirstDay,
          shipLastDay,
          side: "downstream",
          childLotCount: childLots.length,
          childContributionQty,
          childTotalQty,
          mixedLotIds,
          mergedLotIds: [],
          lotText: `${{childRows.length}} lots recus`,
        }};
      }}
      function lotTraceConsolidatePhysicalTransportRows(rows) {{
        const groups = new Map();
        (rows || []).forEach((row) => {{
          const key = lotTraceTransportPhysicalGroupKey(row);
          if (!groups.has(key)) groups.set(key, []);
          groups.get(key).push(row);
        }});
        const result = [];
        groups.forEach((groupRows) => {{
          if (lotTraceCanConsolidatePhysicalTransport(groupRows)) {{
            const grouped = lotTraceBuildPhysicalTransportGroup(groupRows);
            if (grouped) result.push(grouped);
          }} else {{
            result.push(...groupRows);
          }}
        }});
        return result;
      }}
      function lotTraceTransportQtySummary(row) {{
        const uom = String(row.uom || "").trim();
        const allocated = Number(row.receivedQty || row.childContributionQty || row.shippedQty || 0);
        const total = Number(row.childTotalQty || 0);
        const hasMixed = total > allocated + 1e-6;
        if (hasMixed) {{
          return `${{lotTraceQtyText(allocated)}} / ${{lotTraceQtyText(total)}} ${{uom}}`.trim();
        }}
        const qty = allocated || Number(row.shippedQty || 0);
        return `${{lotTraceQtyText(qty)}} ${{uom}}`.trim();
      }}
      function lotTraceTransportMixSummary(row) {{
        const parts = [];
        const mixedCount = (row.mixedLotIds || []).length;
        const mergedCount = (row.mergedLotIds || []).length;
        if (mixedCount) parts.push(`${{mixedCount}} lot${{mixedCount > 1 ? "s" : ""}} mixte${{mixedCount > 1 ? "s" : ""}}`);
        if (mergedCount) parts.push(`${{mergedCount}} lot${{mergedCount > 1 ? "s" : ""}} fusionne${{mergedCount > 1 ? "s" : ""}}`);
        if (row.receivedCount > 1) parts.push(`${{row.receivedCount}} receptions techniques`);
        if (row.shippedCount > 1) parts.push(`${{row.shippedCount}} sorties techniques`);
        return parts.join(" - ");
      }}
      function renderLotTraceTransportSummaryTable(rows, limit = 18) {{
        if (!rows.length) return '<div class="lotTraceEmpty">Aucun transport visible pour la direction selectionnee.</div>';
        const visibleRows = rows.slice(0, limit);
        const overflow = rows.length > limit ? `<div class="lotTracePanelMeta">${{rows.length - limit}} flux logistiques masques.</div>` : "";
        return `
          <table class="lotTraceTable">
            <thead><tr><th>Flux</th><th>Route</th><th>Item</th><th>Jours</th><th class="num">Quantite trace / total</th><th>Lecture</th><th>Logistique</th></tr></thead>
            <tbody>
              ${{visibleRows.map(row => {{
                const dayText = lotTraceTransportDayText(row);
                const route = `${{lotTraceDisplayNodeId(row.src)}} -> ${{lotTraceDisplayNodeId(row.dst)}}`;
                const qtyText = lotTraceTransportQtySummary(row);
                const mixText = row.individualLink
                  ? `${{row.childLotId ? `lot recu ${{row.childLotId}}` : "reception aval"}}${{row.mixedOtherText ? " - " + row.mixedOtherText : ""}}`
                  : (lotTraceTransportMixSummary(row) || "flux non melange");
                const logistics = lotTraceLogisticsDetailText(row.item, row.receivedQty || row.shippedQty);
                return `
                  <tr>
                    <td>${{escapeTableHtml(row.category)}}</td>
                    <td>${{escapeTableHtml(route)}}</td>
                    <td>${{escapeTableHtml(row.item || "")}}</td>
                    <td>${{escapeTableHtml(dayText)}}</td>
                    <td class="num">${{escapeTableHtml(qtyText)}}</td>
                    <td>${{escapeTableHtml(mixText)}}</td>
                    <td>${{escapeTableHtml(logistics)}}</td>
                  </tr>
                `;
              }}).join("")}}
            </tbody>
          </table>
          ${{overflow}}
        `;
      }}
      function renderLotTraceGroupedGraphIfNeeded() {{
        const transportLinkCount = (selected.links || []).filter(link => String(link.link_type || "") === "transport").length;
        const transportRows = lotTraceTransportSummaryRows(selected);
        const root = snapshot.rootLot || {{}};
        const isFinishedProductionRoot = String(root.created_event_type || "") === "production_output";
        const productionLinksToRoot = (selected.links || []).filter(link =>
          String(link.link_type || "") === "production" && String(link.child_lot_id || "") === String(snapshot.lotId || "")
        );
        const keepDetailedLotGraph = !isFinishedProductionRoot && selected.lots.length <= 45 && selected.links.length <= 55;
        if (keepDetailedLotGraph) return false;
        if (!transportRows.length && !productionLinksToRoot.length) return false;
        if (!isFinishedProductionRoot && transportLinkCount < 20 && !productionLinksToRoot.length) return false;
        const leftRowsAll = lotTraceDirection === "downstream"
          ? []
          : transportRows.filter(row => lotTraceIsUpstreamTransportRow(row, snapshot));
        const rightRowsAll = lotTraceDirection === "upstream"
          ? []
          : transportRows.filter(row => lotTraceIsDownstreamTransportRow(row, snapshot));
        function orderTransportRowsAsSupplyChain(rows) {{
          const remaining = (rows || []).slice();
          const ordered = [];
          let currentNode = lotTraceCanonicalNodeId(root.node_id);
          let guard = 0;
          while (remaining.length && guard < 100) {{
            guard += 1;
            let idx = remaining.findIndex(row => lotTraceCanonicalNodeId(row.src) === currentNode);
            if (idx < 0) idx = remaining.findIndex(row => ordered.some(prev => lotTraceCanonicalNodeId(prev.dst) === lotTraceCanonicalNodeId(row.src)));
            if (idx < 0) break;
            const row = remaining.splice(idx, 1)[0];
            ordered.push(row);
            currentNode = lotTraceCanonicalNodeId(row.dst);
          }}
          remaining.sort((a, b) =>
            Number(a.firstDay ?? 0) - Number(b.firstDay ?? 0) ||
            String(a.src).localeCompare(String(b.src)) ||
            String(a.dst).localeCompare(String(b.dst))
          );
          return [...ordered, ...remaining];
        }}
        const useIndividualDownstreamRows = isFinishedProductionRoot && lotTraceDirection !== "upstream";
        const individualRightRowsAll = useIndividualDownstreamRows
          ? lotTraceDownstreamIndividualTransportRows(snapshot)
          : [];
        const orderedRightRowsAll = useIndividualDownstreamRows
          ? individualRightRowsAll
          : (isFinishedProductionRoot ? orderTransportRowsAsSupplyChain(rightRowsAll) : rightRowsAll);
        const graphRowLimit = (lotTraceShowDetails || lotTraceDirection === "both") ? Number.POSITIVE_INFINITY : 40;
        const rightRowLimit = (lotTraceShowDetails || lotTraceDirection === "both") ? Number.POSITIVE_INFINITY : 18;
        const rightRows = orderedRightRowsAll.slice(0, rightRowLimit);
        const componentCount = new Set(
          productionLinksToRoot.map(link => String(link.parent_item_id || link.parent_lot_id || "")).filter(Boolean)
        ).size;
        const componentGroups = new Map();
        productionLinksToRoot.forEach((link) => {{
          const key = [
            link.parent_node_id || "",
            link.parent_item_id || "",
          ].join("|");
          if (!componentGroups.has(key)) {{
            componentGroups.set(key, {{
              kind: "component",
              node: link.parent_node_id || "",
              item: link.parent_item_id || "",
              lotIds: new Set(),
              lotCount: 0,
              qty: 0,
              uom: "",
              firstDay: null,
              lastDay: null,
            }});
          }}
          const row = componentGroups.get(key);
          const parentLotId = String(link.parent_lot_id || "");
          if (parentLotId) {{
            row.lotIds.add(parentLotId);
            const parentInfo = lotTraceLotInfo(parentLotId);
            if (!row.uom && parentInfo.uom) row.uom = parentInfo.uom;
          }}
          row.lotCount += 1;
          const qty = Number(link.parent_qty);
          if (Number.isFinite(qty)) row.qty += qty;
          const linkDay = lotTraceDay(link);
          if (linkDay !== null) {{
            row.firstDay = row.firstDay === null ? linkDay : Math.min(row.firstDay, linkDay);
            row.lastDay = row.lastDay === null ? linkDay : Math.max(row.lastDay, linkDay);
          }}
        }});
        const componentRowsAll = lotTraceDirection === "downstream"
          ? []
          : Array.from(componentGroups.values()).sort((a, b) =>
              String(a.node).localeCompare(String(b.node)) ||
              String(a.item).localeCompare(String(b.item))
            );
        const upstreamTransportVisualRows = leftRowsAll.map(row => ({{ ...row, kind: "transport" }}));
        const leftVisualRowsAll = [
          ...upstreamTransportVisualRows,
          ...componentRowsAll,
        ];
        const leftVisualRows = leftVisualRowsAll.slice(0, graphRowLimit);
        const hasUpstreamTransportRows = leftRowsAll.length > 0 && lotTraceDirection !== "downstream";
        const useUpstreamSupplyLayout = hasUpstreamTransportRows;
        const hasProductionHub = Boolean(componentCount || leftVisualRows.length);
        function lotTraceRightRowSpan(row) {{
          return row && row.physicalTransportGroup
            ? Math.max(1, row.childLotCount || (row.childRows || []).length)
            : 1;
        }}
        const rightVisualSlotCount = rightRows.reduce((acc, row) => acc + lotTraceRightRowSpan(row), 0);
        const rowHeight = 104;
        const maxRows = Math.max(leftVisualRows.length, rightVisualSlotCount, 1);
        const nodeWidth = 250;
        const opWidth = 260;
        const stateWidth = 270;
        const nodeHeight = 78;
        const layoutBoth = lotTraceDirection === "both";
        const hasRightState = rightRows.length > 0;
        const height = Math.max(380, maxRows * rowHeight + 130);
        const upstreamSourceX = 40;
        const upstreamTransportX = useUpstreamSupplyLayout ? 340 : 40;
        const upstreamStateX = useUpstreamSupplyLayout ? 640 : 40;
        const leftOpX = useUpstreamSupplyLayout ? upstreamStateX : 40;
        const productionX = layoutBoth
          ? (useUpstreamSupplyLayout ? 950 : 360)
          : (useUpstreamSupplyLayout ? 930 : 330);
        const rootX = lotTraceDirection === "downstream"
          ? 40
          : (layoutBoth
              ? (useUpstreamSupplyLayout ? 1240 : 650)
              : (useUpstreamSupplyLayout ? 1220 : 620));
        const rightOpX = layoutBoth
          ? (useUpstreamSupplyLayout ? rootX + nodeWidth + 70 : 940)
          : (useUpstreamSupplyLayout ? rootX + nodeWidth + 70 : 330);
        const rightStateX = rightOpX + opWidth + 40;
        const useSupplyChainLayout = isFinishedProductionRoot && !useIndividualDownstreamRows && lotTraceDirection !== "upstream" && rightRows.length > 0;
        const chainFirstTransportX = rootX + nodeWidth + 70;
        const chainStepX = opWidth + stateWidth + 110;
        function chainTransportX(idx) {{
          return chainFirstTransportX + idx * chainStepX;
        }}
        function chainStateX(idx) {{
          return chainTransportX(idx) + opWidth + 42;
        }}
        const chainEndX = useSupplyChainLayout
          ? chainStateX(rightRows.length - 1) + stateWidth + 50
          : 0;
        const upstreamEndX = useUpstreamSupplyLayout ? rootX + nodeWidth + 80 : 0;
        const individualRightEndX = useIndividualDownstreamRows && rightRows.length
          ? rightOpX + opWidth + 40 + stateWidth + 40 + opWidth + 40 + stateWidth + 60
          : 0;
        const width = Math.max(
          layoutBoth ? (hasRightState ? 1540 : 1240) : (hasRightState ? 1220 : 920),
          chainEndX,
          upstreamEndX,
          individualRightEndX
        );
        const rootY = Math.max(42, height / 2 - 34);
        const productionY = rootY;
        const rootQty = root.qty !== "" ? `${{lotTraceQtyText(root.qty)}} ${{root.uom || ""}}`.trim() : "";
        const rootDetail = `J${{root.created_day ?? ""}} - ${{root.node_id || "n/a"}} / ${{root.item_id || "n/a"}}${{rootQty ? " - " + rootQty : ""}}`;
        const rootProductionEvent = (snapshot.events || []).find(row =>
          String(row.lot_id || "") === String(snapshot.lotId || "") && String(row.event_type || "") === "production_output"
        ) || {{}};
        const rootAfterProduction = rootProductionEvent.qty_after !== undefined && rootProductionEvent.qty_after !== ""
          ? `stock lot apres production: ${{lotTraceQtyText(rootProductionEvent.qty_after)}} ${{root.uom || ""}}`.trim()
          : "";
        const rootStatusClass = lotTracePfStatusClass(root);
        const rootStatusLabel = lotTracePfStatusShortLabel(root);
        const rootClass = ["lotTraceGraphNode", "root", rootStatusClass].filter(Boolean).join(" ");
        const productionNode = hasProductionHub
          ? `
            <g class="lotTraceGraphNode operation production" transform="translate(${{productionX}},${{productionY}})">
              <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
              <text x="10" y="19">${{escapeTableHtml(`${{lotTraceDisplayNodeId(root.node_id)}} - production`)}}</text>
              <text class="muted" x="10" y="38">${{escapeTableHtml(`BOM -> ${{root.item_id || "n/a"}}`)}}</text>
              <text class="muted" x="10" y="55">${{escapeTableHtml(`${{componentCount || "n/a"}} composants -> ${{lotTraceQtyText(root.qty)}}`)}}</text>
            </g>
          `
          : "";
        const rootNode = `
          <g class="${{rootClass}}" transform="translate(${{rootX}},${{rootY}})">
            <rect width="${{nodeWidth}}" height="${{nodeHeight}}"></rect>
            <text x="10" y="19">${{escapeTableHtml(snapshot.lotId || "")}}</text>
            <text class="muted" x="10" y="38">${{escapeTableHtml(rootStatusLabel || `Racine selectionnee - ${{lotTraceScopeLabel(root)}}`)}}</text>
            <text class="muted" x="10" y="55">${{escapeTableHtml(rootDetail)}}</text>
            ${{rootAfterProduction ? `<text class="muted" x="10" y="65">${{escapeTableHtml(rootAfterProduction)}}</text>` : ""}}
          </g>
        `;
        const paths = [];
        const nodes = [];
        function graphRowY(idx) {{
          return useSupplyChainLayout ? rootY : 42 + idx * rowHeight;
        }}
        const individualSharedSourceByLot = new Map();
        if (useIndividualDownstreamRows) {{
          let slotIndex = 0;
          rightRows.forEach((row) => {{
            if (row.individualLink) {{
              const childRows = row.physicalTransportGroup ? (row.childRows || []) : [row];
              childRows.forEach((childRow, childIdx) => {{
                const parentLotId = String(childRow.parentLotId || "");
                const childLotId = String(childRow.childLotId || "");
                if (!childLotId || parentLotId !== String(snapshot.lotId || "")) return;
                const y = graphRowY(slotIndex + childIdx);
                individualSharedSourceByLot.set(childLotId, {{
                  x: rightOpX + opWidth + 40,
                  y,
                  yMid: y + nodeHeight / 2,
                }});
              }});
            }}
            slotIndex += lotTraceRightRowSpan(row);
          }});
        }}
        function curvedPath(x1, y1, x2, y2, cls, title) {{
          const mid = Math.max(Math.min(x1, x2) + 28, (x1 + x2) / 2);
          return `<path class="lotTraceGraphLink ${{cls}}" d="M ${{x1}} ${{y1}} C ${{mid}} ${{y1}}, ${{mid}} ${{y2}}, ${{x2}} ${{y2}}"><title>${{escapeTableHtml(title || "")}}</title></path>`;
        }}
        function upstreamVisualRowNode(row, idx) {{
          const y = 42 + idx * rowHeight;
          if (row.kind === "component") {{
          const dayText = row.firstDay === row.lastDay ? `${{row.firstDay ?? ""}}` : `${{row.firstDay ?? ""}}-${{row.lastDay ?? ""}}`;
            const lotIds = Array.from(row.lotIds || []);
            const lotText = lotIds.length === 1
              ? lotIds[0]
              : `${{lotIds.length}} lots${{lotIds.length ? ` (${{lotIds.slice(0, 2).join(", ")}}${{lotIds.length > 2 ? ", ..." : ""}})` : ""}}`;
            const qtyText = `${{lotTraceQtyText(row.qty)}} ${{row.uom || ""}}`.trim();
            const yMid = y + nodeHeight / 2;
            const targetX = hasProductionHub ? productionX : rootX;
            const targetY = hasProductionHub ? productionY + nodeHeight / 2 : rootY + nodeHeight / 2;
            paths.push(curvedPath(leftOpX + opWidth, yMid, targetX, targetY, "production", "Composant BOM consomme"));
            nodes.push(`
              <g class="lotTraceGraphNode operation production" transform="translate(${{leftOpX}},${{y}})">
                <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(`Composant BOM J${{dayText}}`)}}</text>
                <text class="muted" x="10" y="38">${{escapeTableHtml(`${{lotTraceDisplayNodeId(row.node)}} - ${{row.item || ""}}`)}}</text>
                <text class="muted" x="10" y="55">${{escapeTableHtml(`${{qtyText}} consomme - ${{lotText}}`)}}</text>
              </g>
            `);
            return;
          }}
          const dayText = row.firstDay === row.lastDay ? `${{row.firstDay ?? ""}}` : `${{row.firstDay ?? ""}}-${{row.lastDay ?? ""}}`;
          const route = `${{lotTraceDisplayNodeId(row.src)}} -> ${{lotTraceDisplayNodeId(row.dst)}}`;
          const lotSuffix = row.lotText ? ` - ${{row.lotText}}` : "";
          const logisticsText = lotTraceLogisticsShortText(row.item, row.receivedQty || row.shippedQty);
          const logisticsSuffix = logisticsText ? ` | ${{logisticsText}}` : "";
          const qtyText = lotTraceTransportQtySummary(row);
          const mixText = lotTraceTransportMixSummary(row);
          const mixSuffix = mixText ? ` | ${{mixText}}` : "";
          const yMid = y + nodeHeight / 2;
          const targetX = hasProductionHub ? productionX : rootX;
          const targetY = hasProductionHub ? productionY + nodeHeight / 2 : rootY + nodeHeight / 2;
          if (useUpstreamSupplyLayout) {{
            const sourceTitle = lotTraceSourceLabel(row);
            const sourceLine2 = `${{lotTraceDisplayNodeId(row.src)}} - ${{row.item || ""}}`;
            const sourceLine3 = lotTraceSourceStockText(row);
            const endpointTitle = lotTraceEndpointLabel(row);
            const endpointStock = lotTraceEndpointStockText(row);
            const endpointLine2 = `${{lotTraceDisplayNodeId(row.dst)}} - ${{row.item || ""}}`;
            const endpointLine3 = endpointStock || qtyText || "etat stock n/a";
            paths.push(curvedPath(upstreamSourceX + stateWidth, yMid, upstreamTransportX, yMid, "transport", `${{row.category || "Transport amont"}} - ${{route}}`));
            paths.push(curvedPath(upstreamTransportX + opWidth, yMid, upstreamStateX, yMid, "transport", endpointTitle));
            paths.push(curvedPath(upstreamStateX + stateWidth, yMid, targetX, targetY, "production", "Stock amont disponible pour production"));
            nodes.push(`
              <g class="lotTraceGraphNode operation stockState" transform="translate(${{upstreamSourceX}},${{y}})">
                <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(sourceTitle)}}</text>
                <text class="muted" x="10" y="36">${{escapeTableHtml(sourceLine2)}}</text>
                <text class="muted" x="10" y="52">${{escapeTableHtml(sourceLine3)}}</text>
              </g>
            `);
            nodes.push(`
              <g class="lotTraceGraphNode operation transport" transform="translate(${{upstreamTransportX}},${{y}})">
                <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(`${{row.category || "Transport"}} J${{dayText}}`)}}</text>
                <text class="muted" x="10" y="38">${{escapeTableHtml(`${{route}} - ${{row.item || ""}}`)}}</text>
                <text class="muted" x="10" y="55">${{escapeTableHtml(`${{qtyText || "flux n/a"}}${{mixSuffix}}${{logisticsSuffix}}${{lotSuffix}}`)}}</text>
              </g>
            `);
            nodes.push(`
              <g class="lotTraceGraphNode operation stockState" transform="translate(${{upstreamStateX}},${{y}})">
                <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(endpointTitle)}}</text>
                <text class="muted" x="10" y="36">${{escapeTableHtml(endpointLine2)}}</text>
                <text class="muted" x="10" y="52">${{escapeTableHtml(endpointLine3)}}</text>
              </g>
            `);
            return;
          }}
          paths.push(curvedPath(leftOpX + opWidth, yMid, targetX, targetY, "transport", qtyText || "Flux amont"));
          nodes.push(`
            <g class="lotTraceGraphNode operation transport" transform="translate(${{leftOpX}},${{y}})">
                <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(`${{row.category || "Transport"}} J${{dayText}}`)}}</text>
                <text class="muted" x="10" y="38">${{escapeTableHtml(`${{route}} - ${{row.item || ""}}`)}}</text>
                <text class="muted" x="10" y="55">${{escapeTableHtml(`${{qtyText || "flux n/a"}}${{mixSuffix}}${{logisticsSuffix}}${{lotSuffix}}`)}}</text>
              </g>
            `);
        }}
        function downstreamRowNode(row, idx) {{
          const y = graphRowY(idx);
          const dayText = lotTraceTransportDayText(row);
          const route = `${{lotTraceDisplayNodeId(row.src)}} -> ${{lotTraceDisplayNodeId(row.dst)}}`;
          const lotSuffix = row.lotText ? ` - ${{row.lotText}}` : "";
          const logisticsText = lotTraceLogisticsShortText(row.item, row.receivedQty || row.shippedQty);
          const logisticsSuffix = logisticsText ? ` | ${{logisticsText}}` : "";
          const qtyText = lotTraceTransportQtySummary(row);
          const mixText = lotTraceTransportMixSummary(row);
          const mixSuffix = mixText ? ` | ${{mixText}}` : "";
          const yMid = y + nodeHeight / 2;
          if (row.individualLink) {{
            if (row.physicalTransportGroup) {{
              const childRows = row.childRows || [];
              const groupSpan = lotTraceRightRowSpan(row);
              const transportY = graphRowY(idx) + ((groupSpan - 1) * rowHeight) / 2;
              const transportYMid = transportY + nodeHeight / 2;
              const sourceRefs = new Map();
              childRows.forEach((childRow, childIdx) => {{
                const parentLotId = String(childRow.parentLotId || "");
                if (!parentLotId) return;
                if (sourceRefs.has(parentLotId)) return;
                if (parentLotId === String(snapshot.lotId || "")) {{
                  sourceRefs.set(parentLotId, {{
                    x: rootX + nodeWidth,
                    yMid: rootY + nodeHeight / 2,
                    needsNode: false,
                  }});
                  return;
                }}
                const sharedSource = individualSharedSourceByLot.get(parentLotId);
                if (sharedSource) {{
                  sourceRefs.set(parentLotId, {{
                    x: sharedSource.x + stateWidth,
                    yMid: sharedSource.yMid,
                    needsNode: false,
                  }});
                  return;
                }}
                const sourceY = graphRowY(idx + childIdx);
                sourceRefs.set(parentLotId, {{
                  x: rightOpX + stateWidth,
                  y: sourceY,
                  yMid: sourceY + nodeHeight / 2,
                  needsNode: true,
                  row: childRow,
                }});
              }});
              const hasNonRootSource = Array.from(sourceRefs.keys()).some(parentLotId => parentLotId !== String(snapshot.lotId || ""));
              const transportX = hasNonRootSource
                ? Math.max(...Array.from(sourceRefs.values()).map(ref => ref.x + 40), rightOpX + stateWidth + 40)
                : rightOpX;
              const stateX = transportX + opWidth + 40;
              sourceRefs.forEach((ref, parentLotId) => {{
                if (ref.needsNode) {{
                  const sourceRow = ref.row || row;
                  nodes.push(`
                    <g class="lotTraceGraphNode operation stockState" transform="translate(${{rightOpX}},${{ref.y}})">
                      <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
                      <text x="10" y="19">${{escapeTableHtml(parentLotId)}}</text>
                      <text class="muted" x="10" y="36">${{escapeTableHtml(`${{lotTraceDisplayNodeId(sourceRow.src)}} / ${{sourceRow.item || ""}}`)}}</text>
                      <text class="muted" x="10" y="52">${{escapeTableHtml(`lot source: ${{lotTraceQtyText(sourceRow.receivedQty)}} ${{sourceRow.uom || ""}}`.trim())}}</text>
                    </g>
                  `);
                }}
                paths.push(curvedPath(ref.x, ref.yMid, transportX, transportYMid, "transport", `${{row.category || "Transport aval"}} - ${{route}}`));
              }});
              const groupedQtyText = lotTraceTransportQtySummary(row);
              const groupedLogisticsText = lotTraceLogisticsShortText(row.item, row.receivedQty || row.childContributionQty);
              const groupedLogisticsSuffix = groupedLogisticsText ? ` | ${{groupedLogisticsText}}` : "";
              nodes.push(`
                <g class="lotTraceGraphNode operation transport" transform="translate(${{transportX}},${{transportY}})">
                  <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
                  <text x="10" y="19">${{escapeTableHtml(`${{row.category || "Transport"}} J${{row.firstDay ?? ""}}`)}}</text>
                  <text class="muted" x="10" y="38">${{escapeTableHtml(`${{route}} - ${{row.item || ""}}`)}}</text>
                  <text class="muted" x="10" y="55">${{escapeTableHtml(`${{groupedQtyText || "flux n/a"}}${{groupedLogisticsSuffix}} | ${{childRows.length}} lots`)}}</text>
                </g>
              `);
              const endpointsByChild = new Map();
              childRows.forEach((childRow) => {{
                const childLotId = String(childRow.childLotId || "");
                if (!childLotId) return;
                if (!endpointsByChild.has(childLotId)) {{
                  endpointsByChild.set(childLotId, {{
                    ...childRow,
                    receivedQty: 0,
                    childContributionQty: 0,
                    childTotalQty: lotTraceLotTotalQty(childLotId) || 0,
                    parentLotIds: new Set(),
                    childLotIds: new Set([childLotId]),
                    childContributionByLot: new Map(),
                    childTotalByLot: new Map(),
                    mixedOtherText: "",
                  }});
                }}
                const endpoint = endpointsByChild.get(childLotId);
                const qty = Number(childRow.receivedQty || childRow.childContributionQty || 0);
                if (Number.isFinite(qty)) {{
                  endpoint.receivedQty += qty;
                  endpoint.childContributionQty += qty;
                }}
                if (childRow.parentLotId) endpoint.parentLotIds.add(String(childRow.parentLotId));
                endpoint.childContributionByLot.set(childLotId, endpoint.childContributionQty);
                if (endpoint.childTotalQty > 0) endpoint.childTotalByLot.set(childLotId, endpoint.childTotalQty);
              }});
              Array.from(endpointsByChild.values()).forEach((endpointRow, childIdx) => {{
                const childY = graphRowY(idx + childIdx);
                const childYMid = childY + nodeHeight / 2;
                const childLotId = String(endpointRow.childLotId || "");
                const parentSet = endpointRow.parentLotIds || new Set();
                const otherParts = (lotTraceIndexes.parentsByChild.get(childLotId) || [])
                  .filter(parentLink =>
                    String(parentLink.link_type || "") === "transport" &&
                    !parentSet.has(String(parentLink.parent_lot_id || ""))
                  )
                  .map(parentLink => {{
                    const qty = Number(parentLink.parent_qty || parentLink.child_qty || 0);
                    return {{
                      lotId: String(parentLink.parent_lot_id || ""),
                      qty: Number.isFinite(qty) ? qty : 0,
                    }};
                  }})
                  .filter(part => part.lotId && part.qty > 1e-9);
                endpointRow.mixedOtherText = otherParts.length
                  ? `autre part: ${{otherParts.map(part => `${{lotTraceQtyText(part.qty)}} ${{endpointRow.uom || ""}} via ${{part.lotId}}`).join(" + ")}}`
                  : "";
                paths.push(curvedPath(transportX + opWidth, transportYMid, stateX, childYMid, "transport", childLotId || lotTraceEndpointLabel(endpointRow)));
                const endpointService = lotTraceEndpointServiceText(endpointRow);
                const endpointStock = lotTraceEndpointStockText(endpointRow);
                const endpointTitle = childLotId || lotTraceEndpointLabel(endpointRow);
                const endpointLine2 = `${{lotTraceDisplayNodeId(endpointRow.dst)}} / ${{endpointRow.item || ""}}`;
                const endpointLine3 = `part tracee: ${{lotTraceTransportQtySummary(endpointRow) || "n/a"}}`;
                const endpointLine4 = endpointRow.mixedOtherText || endpointService || endpointStock || "";
                nodes.push(`
                  <g class="lotTraceGraphNode operation stockState ${{endpointRow.mixedOtherText ? "mixed" : ""}}" transform="translate(${{stateX}},${{childY}})">
                    <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
                    <text x="10" y="19">${{escapeTableHtml(endpointTitle)}}</text>
                    <text class="muted" x="10" y="36">${{escapeTableHtml(endpointLine2)}}</text>
                    <text class="muted" x="10" y="52">${{escapeTableHtml(endpointLine3)}}</text>
                    ${{endpointLine4 ? `<text class="muted" x="10" y="65">${{escapeTableHtml(endpointLine4)}}</text>` : ""}}
                  </g>
                `);
              }});
              return;
            }}
            const rootLotId = String(snapshot.lotId || "");
            const parentLotId = String(row.parentLotId || "");
            const childLotId = String(row.childLotId || "");
            const hasSourceLotNode = parentLotId && parentLotId !== rootLotId;
            const sharedSource = hasSourceLotNode ? individualSharedSourceByLot.get(parentLotId) : null;
            const sourceX = sharedSource ? sharedSource.x : rightOpX;
            const sourceY = sharedSource ? sharedSource.y : y;
            const transportX = hasSourceLotNode
              ? (sharedSource ? sharedSource.x + stateWidth + 40 : rightOpX + stateWidth + 40)
              : rightOpX;
            const stateX = transportX + opWidth + 40;
            const startX = hasSourceLotNode
              ? (sharedSource ? sharedSource.x + stateWidth : sourceX + stateWidth)
              : rootX + nodeWidth;
            const startY = hasSourceLotNode
              ? (sharedSource ? sharedSource.yMid : sourceY + nodeHeight / 2)
              : rootY + nodeHeight / 2;
            if (hasSourceLotNode && !sharedSource) {{
              nodes.push(`
                <g class="lotTraceGraphNode operation stockState" transform="translate(${{sourceX}},${{y}})">
                  <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
                  <text x="10" y="19">${{escapeTableHtml(parentLotId)}}</text>
                  <text class="muted" x="10" y="36">${{escapeTableHtml(`${{lotTraceDisplayNodeId(row.src)}} / ${{row.item || ""}}`)}}</text>
                  <text class="muted" x="10" y="52">${{escapeTableHtml(`lot source: ${{lotTraceQtyText(row.receivedQty)}} ${{row.uom || ""}}`.trim())}}</text>
                </g>
              `);
            }}
            paths.push(curvedPath(startX, startY, transportX, yMid, "transport", `${{row.category || "Transport aval"}} - ${{route}}`));
            paths.push(curvedPath(transportX + opWidth, yMid, stateX, yMid, "transport", childLotId || lotTraceEndpointLabel(row)));
            nodes.push(`
              <g class="lotTraceGraphNode operation transport" transform="translate(${{transportX}},${{y}})">
                <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(`${{row.category || "Transport"}} J${{row.firstDay ?? ""}}`)}}</text>
                <text class="muted" x="10" y="38">${{escapeTableHtml(`${{route}} - ${{row.item || ""}}`)}}</text>
                <text class="muted" x="10" y="55">${{escapeTableHtml(`${{qtyText || "flux n/a"}}${{logisticsSuffix}}`)}}</text>
              </g>
            `);
            const endpointService = lotTraceEndpointServiceText(row);
            const endpointStock = lotTraceEndpointStockText(row);
            const endpointTitle = childLotId || lotTraceEndpointLabel(row);
            const endpointLine2 = `${{lotTraceDisplayNodeId(row.dst)}} / ${{row.item || ""}}`;
            const endpointLine3 = `part tracee: ${{qtyText || "n/a"}}`;
            const endpointLine4 = row.mixedOtherText || endpointService || endpointStock || "";
            nodes.push(`
              <g class="lotTraceGraphNode operation stockState ${{row.mixedOtherText ? "mixed" : ""}}" transform="translate(${{stateX}},${{y}})">
                <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
                <text x="10" y="19">${{escapeTableHtml(endpointTitle)}}</text>
                <text class="muted" x="10" y="36">${{escapeTableHtml(endpointLine2)}}</text>
                <text class="muted" x="10" y="52">${{escapeTableHtml(endpointLine3)}}</text>
                ${{endpointLine4 ? `<text class="muted" x="10" y="65">${{escapeTableHtml(endpointLine4)}}</text>` : ""}}
              </g>
            `);
            return;
          }}
          const transportX = useSupplyChainLayout ? chainTransportX(idx) : rightOpX;
          const stateX = useSupplyChainLayout ? chainStateX(idx) : rightStateX;
          const startX = useSupplyChainLayout && idx > 0
            ? chainStateX(idx - 1) + stateWidth
            : rootX + nodeWidth;
          const startY = useSupplyChainLayout ? yMid : rootY + nodeHeight / 2;
          paths.push(curvedPath(startX, startY, transportX, yMid, "transport", `${{row.category || "Transport aval"}} - ${{route}}`));
          paths.push(curvedPath(transportX + opWidth, yMid, stateX, yMid, "transport", lotTraceEndpointLabel(row)));
          nodes.push(`
            <g class="lotTraceGraphNode operation transport" transform="translate(${{transportX}},${{y}})">
              <rect width="${{opWidth}}" height="${{nodeHeight}}"></rect>
              <text x="10" y="19">${{escapeTableHtml(row.category || "Transport")}}</text>
              <text class="muted" x="10" y="38">${{escapeTableHtml(`${{route}} - ${{dayText}}`)}}</text>
              <text class="muted" x="10" y="55">${{escapeTableHtml(`${{qtyText || "flux n/a"}}${{mixSuffix}}${{logisticsSuffix}}${{lotSuffix}}`)}}</text>
            </g>
          `);
          const endpointTitle = lotTraceEndpointLabel(row);
          const endpointQty = lotTraceTransportQtySummary(row);
          const endpointStock = lotTraceEndpointStockText(row);
          const endpointService = lotTraceEndpointServiceText(row);
          const endpointLine2 = `${{lotTraceDisplayNodeId(row.dst)}} - ${{row.item || ""}}`;
          const endpointLine3 = endpointService || endpointStock || endpointQty || "etat stock n/a";
          const endpointLine4 = endpointService && endpointStock ? endpointStock : endpointQty;
          nodes.push(`
            <g class="lotTraceGraphNode operation stockState" transform="translate(${{stateX}},${{y}})">
              <rect width="${{stateWidth}}" height="${{nodeHeight}}"></rect>
              <text x="10" y="19">${{escapeTableHtml(endpointTitle)}}</text>
              <text class="muted" x="10" y="36">${{escapeTableHtml(endpointLine2)}}</text>
              <text class="muted" x="10" y="52">${{escapeTableHtml(endpointLine3)}}</text>
              ${{endpointLine4 && endpointLine4 !== endpointLine3 ? `<text class="muted" x="10" y="65">${{escapeTableHtml(endpointLine4)}}</text>` : ""}}
            </g>
          `);
        }}
        leftVisualRows.forEach(upstreamVisualRowNode);
        let rightSlotIndex = 0;
        rightRows.forEach((row) => {{
          downstreamRowNode(row, rightSlotIndex);
          rightSlotIndex += lotTraceRightRowSpan(row);
        }});
        if (hasProductionHub) {{
          paths.push(curvedPath(productionX + opWidth, productionY + nodeHeight / 2, rootX, rootY + nodeHeight / 2, "production", "Production vers lot PF selectionne"));
        }}
        const omittedFluxCount = Math.max(0, leftVisualRowsAll.length - leftVisualRows.length) + Math.max(0, orderedRightRowsAll.length - rightRows.length);
        const omittedFlux = omittedFluxCount
          ? `<div class="lotTracePanelMeta">${{omittedFluxCount}} elements supplementaires masques dans ce graphe groupe. Active Details pour afficher la chaine complete et les tables completes.</div>`
          : "";
        const nonTransportLinks = Math.max(0, (selected.links || []).length - transportLinkCount);
        const remainingNonTransportLinks = Math.max(0, nonTransportLinks - productionLinksToRoot.length);
        const extraNote = nonTransportLinks
          ? (remainingNonTransportLinks ? ` ${{remainingNonTransportLinks}} liens non-transport restent detailles dans les tables.` : "")
          : "";
        const layoutHint = lotTraceDirection === "both"
          ? "Amont a gauche, production et lot selectionne au centre, aval a droite."
          : (lotTraceDirection === "upstream" ? "Amont a gauche, lot selectionne a droite." : "Lot selectionne a gauche, aval a droite.");
        const upstreamHeaderSvg = leftVisualRows.length
          ? (useUpstreamSupplyLayout
              ? `
                <text class="lotTraceGraphTimelineText" x="${{upstreamSourceX}}" y="24">Source amont</text>
                <text class="lotTraceGraphTimelineText" x="${{upstreamTransportX}}" y="24">Transport amont</text>
                <text class="lotTraceGraphTimelineText" x="${{upstreamStateX}}" y="24">Stock arrivee</text>
              `
              : `<text class="lotTraceGraphTimelineText" x="${{leftOpX}}" y="24">Amont</text>`)
          : "";
        const headerSvg = `
          ${{upstreamHeaderSvg}}
          ${{hasProductionHub ? `<text class="lotTraceGraphTimelineText" x="${{productionX}}" y="24">Production</text>` : ""}}
          <text class="lotTraceGraphTimelineText" x="${{rootX}}" y="24">Lot selectionne</text>
          ${{rightRows.length ? `<text class="lotTraceGraphTimelineText" x="${{useSupplyChainLayout ? chainFirstTransportX : rightOpX}}" y="24">${{useIndividualDownstreamRows ? "Transports physiques / receptions aval" : "Chaine supply aval"}}</text>` : ""}}
          ${{rightRows.length && !useSupplyChainLayout && !useIndividualDownstreamRows ? `<text class="lotTraceGraphTimelineText" x="${{rightStateX}}" y="24">Etat apres arrivee</text>` : ""}}
        `;
        graphWrap.innerHTML = `
          <div class="lotTracePanelMeta">Graphe metier: les sites supply sont affiches dans la chaine physique. Orange = transport, vert = lot/noeud supply avec stock ou client servi apres arrivee, bleu = production/BOM. ${{layoutHint}}${{extraNote}}</div>
          ${{omittedFlux}}
          <svg class="lotTraceGraphSvg" width="${{width}}" height="${{height}}" viewBox="0 0 ${{width}} ${{height}}">
            <defs>
              <marker id="lotTraceArrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#64748b"></path>
              </marker>
            </defs>
            ${{headerSvg}}
            ${{paths.join("")}}
            ${{productionNode}}
            ${{rootNode}}
            ${{nodes.join("")}}
          </svg>
        `;
        requestAnimationFrame(() => {{
          graphWrap.scrollLeft = 0;
          graphWrap.scrollTop = 0;
        }});
        return true;
      }}
      if (renderLotTraceGroupedGraphIfNeeded()) return;
      const visualLinks = [];
      const productionGroups = new Map();
      visibleLinks.forEach((link, idx) => {{
        const parent = String(link.parent_lot_id || "");
        const child = String(link.child_lot_id || "");
        if (!parent || !child) return;
        const linkType = String(link.link_type || "");
        if (linkType === "production") {{
          const groupKey = [
            lotTraceDay(link) ?? "",
            link.production_campaign_id || "",
            child,
            link.child_node_id || "",
            link.child_item_id || "",
            link.source_id || "",
          ].join("|");
          if (!productionGroups.has(groupKey)) {{
            productionGroups.set(groupKey, {{
              id: `op:production:${{productionGroups.size}}:${{child}}`,
              link,
              links: [],
              parentLots: new Set(),
              childLot: child,
            }});
          }}
          const group = productionGroups.get(groupKey);
          group.links.push(link);
          group.parentLots.add(parent);
          return;
        }}
        const parentLevel = Number(lotLevels.get(parent) || 0) * 2;
        const childLevel = Number(lotLevels.get(child) || parentLevel + 2) * 2;
        const opLevel = Math.max(parentLevel + 1, Math.min(parentLevel + 1, childLevel - 1));
        const cleanType = String(link.link_type || "operation").replace(/[^a-zA-Z0-9_-]/g, "");
        const opId = `op:${{idx}}:${{parent}}:${{child}}:${{cleanType}}`;
        rememberVisualNode({{
          id: opId,
          kind: "operation",
          link,
          level: opLevel,
          opClass: cleanType,
        }});
        visualLinks.push({{ from: `lot:${{parent}}`, to: opId, link }});
        visualLinks.push({{ from: opId, to: `lot:${{child}}`, link }});
      }});
      productionGroups.forEach((group) => {{
        const link = group.link || {{}};
        const child = String(group.childLot || link.child_lot_id || "");
        if (!child) return;
        const parents = Array.from(group.parentLots || []).filter(parent => visibleLotSet.has(parent));
        const fallbackParent = String(link.parent_lot_id || "");
        const parentLevels = (parents.length ? parents : [fallbackParent])
          .filter(Boolean)
          .map(parent => Number(lotLevels.get(parent) || 0) * 2);
        const parentLevel = parentLevels.length ? Math.max(...parentLevels) : 0;
        const childLevel = Number(lotLevels.get(child) || parentLevel + 2) * 2;
        const opLevel = Math.max(parentLevel + 1, Math.min(parentLevel + 1, childLevel - 1));
        rememberVisualNode({{
          id: group.id,
          kind: "operation",
          link,
          links: group.links || [],
          level: opLevel,
          opClass: "production",
        }});
        parents.forEach((parent) => {{
          const parentLink = (group.links || []).find(row => String(row.parent_lot_id || "") === parent) || link;
          visualLinks.push({{ from: `lot:${{parent}}`, to: group.id, link: parentLink }});
        }});
        visualLinks.push({{ from: group.id, to: `lot:${{child}}`, link }});
      }});
      const groups = new Map();
      visualNodes.forEach((node) => {{
        const level = Number(node.level || 0);
        if (!groups.has(level)) groups.set(level, []);
        groups.get(level).push(node);
      }});
      const sortedLevels = Array.from(groups.keys()).sort((a, b) => a - b);
      sortedLevels.forEach(level => groups.get(level).sort((a, b) => String(a.id).localeCompare(String(b.id))));
      const maxRows = Math.max(1, ...Array.from(groups.values()).map(group => group.length));
      const columnWidth = 260;
      const rowHeight = 92;
      const nodeWidth = 220;
      const nodeHeight = 62;
      const operationWidth = 178;
      const operationHeight = 58;
      function visualNodeSize(node) {{
        return node && node.kind === "operation"
          ? {{ width: operationWidth, height: operationHeight }}
          : {{ width: nodeWidth, height: nodeHeight }};
      }}
      const width = Math.max(980, sortedLevels.length * columnWidth + 120);
      const height = Math.max(380, maxRows * rowHeight + 90);
      const positions = new Map();
      sortedLevels.forEach((level, colIdx) => {{
        const group = groups.get(level) || [];
        const columnHeight = group.length * rowHeight;
        const yStart = Math.max(38, (height - columnHeight) / 2);
        group.forEach((node, rowIdx) => {{
          const size = visualNodeSize(node);
          positions.set(node.id, {{
            x: 40 + colIdx * columnWidth,
            y: yStart + rowIdx * rowHeight,
            width: size.width,
            height: size.height,
          }});
        }});
      }});

      const linkSvg = visualLinks.map((edge) => {{
        const link = edge.link || {{}};
        const a = positions.get(edge.from);
        const b = positions.get(edge.to);
        if (!a || !b) return "";
        const x1 = a.x + a.width;
        const y1 = a.y + a.height / 2;
        const x2 = b.x;
        const y2 = b.y + b.height / 2;
        const mid = Math.max(x1 + 24, (x1 + x2) / 2);
        const linkClass = String(link.link_type || "").replace(/[^a-zA-Z0-9_-]/g, "");
        const logisticsTitle = String(link.link_type || "") === "transport"
          ? lotTraceLogisticsDetailText(link.parent_item_id || link.child_item_id, link.parent_qty || link.child_qty)
          : "";
        const title = `${{link.link_type || "lien"}} J${{lotTraceDay(link) ?? ""}} ${{link.parent_lot_id || ""}} -> ${{link.child_lot_id || ""}}${{logisticsTitle ? " | " + logisticsTitle : ""}}`;
        return `<path class="lotTraceGraphLink ${{linkClass}}" d="M ${{x1}} ${{y1}} C ${{mid}} ${{y1}}, ${{mid}} ${{y2}}, ${{x2}} ${{y2}}"><title>${{escapeTableHtml(title)}}</title></path>`;
      }}).join("");

      const nodeSvg = visualNodes.map((node) => {{
        const pos = positions.get(node.id) || {{ x: 40, y: 40, width: nodeWidth, height: nodeHeight }};
        if (node.kind === "operation") {{
          const link = node.link || {{}};
          const links = Array.isArray(node.links) && node.links.length ? node.links : [link];
          const groupedProduction = String(link.link_type || "") === "production" && links.length > 1;
          const groupedSummary = groupedProduction ? lotTraceGroupedProductionSummary(links, link) : null;
          const label = groupedProduction ? "Production BOM" : lotTraceOperationLabel(link);
          const detail = groupedProduction
            ? groupedSummary.detail
            : lotTraceOperationDetail(link);
          const parentQty = lotTraceQtyText(link.parent_qty);
          const childQty = lotTraceQtyText(link.child_qty);
          const qty = groupedProduction
            ? groupedSummary.qty
            : (parentQty || childQty ? `${{parentQty || "n/a"}} -> ${{childQty || "n/a"}}` : "");
          const logisticsTitle = String(link.link_type || "") === "transport"
            ? lotTraceLogisticsDetailText(link.parent_item_id || link.child_item_id, link.parent_qty || link.child_qty)
            : "";
          const componentTitle = groupedSummary && groupedSummary.componentText ? ` | composants: ${{groupedSummary.componentText}}` : "";
          const opTitle = `${{label}} J${{lotTraceDay(link) ?? ""}}${{componentTitle}}${{logisticsTitle ? " | " + logisticsTitle : ""}}`;
          const cls = `lotTraceGraphNode operation ${{node.opClass || ""}}`.trim();
          return `
            <g class="${{cls}}" transform="translate(${{pos.x}},${{pos.y}})">
              <title>${{escapeTableHtml(opTitle)}}</title>
              <rect width="${{pos.width}}" height="${{pos.height}}"></rect>
              <text x="10" y="17">${{escapeTableHtml(`${{label}} J${{lotTraceDay(link) ?? ""}}`)}}</text>
              <text class="muted" x="10" y="34">${{escapeTableHtml(detail)}}</text>
              <text class="muted" x="10" y="49">${{escapeTableHtml(qty)}}</text>
            </g>
          `;
        }}
        const lotId = node.lotId;
        const info = lotTraceLotInfo(lotId);
        const contributionInfo = selectedLotTraceContributionInfo(snapshot, lotId);
        const scopeLabel = lotTraceScopeLabel(info);
        const nodeLine = `${{info.node_id || "n/a"}} / ${{info.item_id || "n/a"}}`;
        const qty = info.qty !== "" ? `${{lotTraceQtyText(info.qty)}} ${{info.uom || ""}}`.trim() : "";
        const roleLabel = lotId === snapshot.lotId
          ? "Racine selectionnee"
          : ((snapshot.upstreamLots || []).includes(lotId) ? "Ascendant amont" : "Descendant aval");
        const baseCls = lotId === snapshot.lotId ? "lotTraceGraphNode root" : "lotTraceGraphNode";
        const statusClass = lotTracePfStatusClass(info);
        const statusLabel = lotTracePfStatusShortLabel(info);
        const mixedClass = contributionInfo.isMixedWithOtherOrigin ? "mixed" : "";
        const cls = [baseCls, statusClass, mixedClass].filter(Boolean).join(" ");
        const contributionLine = contributionInfo.isMixedWithOtherOrigin
          ? `part tracee ${{lotTraceQtyText(contributionInfo.contributionQty)}} / ${{lotTraceQtyText(contributionInfo.totalQty)}} ${{info.uom || ""}}`.trim()
          : (contributionInfo.isMergedFromSeveralSelectedLots
              ? `fusion interne ${{contributionInfo.parentCount}} parents - ${{qty}}`
              : `J${{info.created_day ?? ""}} - ${{nodeLine}}${{qty ? " - " + qty : ""}}`);
        const roleLine = contributionInfo.isMixedWithOtherOrigin
          ? `${{roleLabel}} - lot mixte ${{lotTraceQtyText(contributionInfo.share * 100, 1)}}%`
          : (statusLabel || `${{roleLabel}} - ${{scopeLabel}}`);
        return `
          <g class="${{cls}}" transform="translate(${{pos.x}},${{pos.y}})">
            <rect width="${{pos.width}}" height="${{pos.height}}"></rect>
            <text x="10" y="18">${{escapeTableHtml(lotId)}}</text>
            <text class="muted" x="10" y="35">${{escapeTableHtml(roleLine)}}</text>
            <text class="muted" x="10" y="50">${{escapeTableHtml(contributionLine)}}</text>
          </g>
        `;
      }}).join("");

      const truncated = selected.lots.length > maxGraphLots
        ? `<div class="lotTracePanelMeta">Graphe tronque a ${{maxGraphLots}} lots sur ${{selected.lots.length}} pour garder la page lisible.</div>`
        : "";
      graphWrap.innerHTML = `
        ${{truncated}}
        <svg class="lotTraceGraphSvg" width="${{width}}" height="${{height}}" viewBox="0 0 ${{width}} ${{height}}">
          <defs>
            <marker id="lotTraceArrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="#64748b"></path>
            </marker>
          </defs>
          ${{linkSvg}}
          ${{nodeSvg}}
        </svg>
      `;
    }}

    function renderLotTraceModal() {{
      const modal = document.getElementById("lotTraceModal");
      if (!modal || !modal.classList.contains("visible")) return;
      const meta = document.getElementById("lotTraceModalMeta");
      const tables = document.getElementById("lotTraceModalTables");
      const selectedOrder = selectedDeferredOrder();
      const snapshot = selectedLotTraceSnapshot();
      const selected = lotTraceRowsForDirection(snapshot);
      document.querySelectorAll(".lotTraceDirectionBtn").forEach(btn => {{
        btn.classList.toggle("active", String(btn.dataset.lotTraceDirection || "both") === lotTraceDirection);
      }});
      const modalSelect = document.getElementById("lotTraceModalSelect");
      if (modalSelect && modalSelect.value !== selectedLotId) modalSelect.value = selectedLotId || "";
      const deferredOrders = lotTraceDeferredOrders();
      const orderDetailsBtn = document.getElementById("lotTraceOrderDetailsBtn");
      if (orderDetailsBtn) {{
        const hasDetails = Boolean(selectedOrder || snapshot);
        orderDetailsBtn.classList.toggle("hidden", !hasDetails);
        orderDetailsBtn.classList.toggle("active", Boolean(hasDetails && lotTraceShowDetails));
        orderDetailsBtn.disabled = !hasDetails;
        orderDetailsBtn.textContent = lotTraceShowDetails ? "Masquer details" : "Details";
      }}
      if (selectedOrder) {{
        if (meta) {{
          meta.textContent = `Ordre reporte - ${{selectedOrder.status_label || "reporte"}} - ${{selectedOrder.delay_days || 0}} jours de report.`;
        }}
        renderDeferredProductionOrderGraph(selectedOrder);
        if (tables) {{
          tables.innerHTML = lotTraceShowDetails
            ? `
              <div class="lotTraceSectionTitle">Details de l'ordre</div>
              ${{renderDeferredProductionOrderDetail(selectedOrder)}}
              <div class="lotTraceSectionTitle">Tous les ordres reportes</div>
              ${{renderDeferredProductionOrdersTable(deferredOrders, deferredOrders.length)}}
            `
            : "";
        }}
        return;
      }}
      if (meta) {{
        const directionLabel = lotTraceDirection === "upstream"
          ? "Ascendants amont du lot selectionne"
          : (lotTraceDirection === "downstream" ? "Descendants aval du lot selectionne" : "Graphe complet du lot selectionne");
        meta.textContent = snapshot
          ? `${{directionLabel}} - ${{selected.lots.length}} lots - ${{selected.links.length}} liens - ${{selected.events.length}} evenements. Fleches: parent vers enfant.`
          : "Selectionne un lot PF/PFI/MP ou un ordre reporte";
      }}
      renderLotTraceGraph(snapshot);
      if (tables) {{
        const openingStockNote = snapshot && lotTraceContainsOpeningStock(selected.events)
          ? '<div class="lotTraceEmpty">Note: certains lots visibles sont du stock initial; leur provenance avant J0 n est pas tracee par la simulation.</div>'
          : "";
        const mixedLotRows = snapshot ? lotTraceMixedLotRows(snapshot, selected) : [];
        tables.innerHTML = snapshot && lotTraceShowDetails
          ? `
            ${{openingStockNote}}
            <div class="lotTraceSectionTitle">Receptions / transports visibles</div>
            ${{renderLotTraceTransportLinksTable(selected.links, selected.links.length)}}
            <div class="lotTraceSectionTitle">Lots mixtes visibles</div>
            ${{renderLotTraceMixedLotsTable(mixedLotRows, mixedLotRows.length)}}
            <div class="lotTraceSectionTitle">Evenements visibles dans le graphe</div>
            ${{renderLotTraceEventsTable(selected.events, selected.events.length)}}
            <div class="lotTraceSectionTitle">Liens visibles dans le graphe</div>
            ${{renderLotTraceLinksTable(selected.links, selected.links.length)}}
          `
          : "";
      }}
    }}

    function updateLotTraceControls() {{
      const box = document.getElementById("lotTraceControlsBox");
      const select = document.getElementById("lotTraceSelect");
      const modalSelect = document.getElementById("lotTraceModalSelect");
      const focusBtn = document.getElementById("lotTraceFocusBtn");
      const openBtn = document.getElementById("lotTraceOpenBtn");
      const ordersBtn = document.getElementById("lotTraceOrdersBtn");
      const clearBtn = document.getElementById("lotTraceClearBtn");
      const hasDeferredOrders = lotTraceDeferredOrders().length > 0;
      const visible = currentPanelMode === "ops" && Boolean(LOT_TRACE.available || hasDeferredOrders);
      if (box) box.classList.toggle("visible", visible);
      if (select) {{
        select.disabled = !visible;
        if (select.value !== selectedLotId) select.value = selectedLotId || "";
      }}
      if (modalSelect) {{
        modalSelect.disabled = !visible;
        if (modalSelect.value !== selectedLotId) modalSelect.value = selectedLotId || "";
      }}
      if (focusBtn) focusBtn.disabled = !selectedLotId;
      if (openBtn) openBtn.disabled = !visible;
      if (ordersBtn) {{
        ordersBtn.disabled = !visible || !hasDeferredOrders;
        ordersBtn.style.display = hasDeferredOrders ? "inline-flex" : "none";
      }}
      if (clearBtn) clearBtn.disabled = !selectedLotId;
      renderLotTracePanel();
      renderLotTraceModal();
    }}

    function initLotTraceControls() {{
      const select = document.getElementById("lotTraceSelect");
      const modalSelect = document.getElementById("lotTraceModalSelect");
      function lotTraceDefaultSelection(preferOrders = false) {{
        const deferredOrders = lotTraceDeferredOrders();
        const options = Array.isArray(LOT_TRACE.lot_options) ? LOT_TRACE.lot_options : Object.values(LOT_TRACE.lots || {{}});
        if (preferOrders && deferredOrders.length) {{
          return lotTraceDeferredOrderValue(String(deferredOrders[0].campaign_id || ""));
        }}
        if (LOT_TRACE.default_lot) return LOT_TRACE.default_lot;
        if (options.length && options[0] && options[0].lot_id) return String(options[0].lot_id || "");
        if (deferredOrders.length) return lotTraceDeferredOrderValue(String(deferredOrders[0].campaign_id || ""));
        return "";
      }}
      function appendDeferredOrderOptions(target, deferredOrders) {{
        if (!target || !deferredOrders.length) return;
        const orderGroup = document.createElement("optgroup");
        orderGroup.label = "Ordres reportes";
        deferredOrders.forEach((order) => {{
          const opt = document.createElement("option");
          opt.value = lotTraceDeferredOrderValue(String(order.campaign_id || ""));
          const isCompletedAfterDelay = String(order.status || "") === "completed_after_delay";
          const status = isCompletedAfterDelay ? "rattrapage produit" : "toujours bloque";
          const delayText = `J${{order.first_delay_day ?? ""}}` + (order.last_delay_day !== order.first_delay_day ? `-J${{order.last_delay_day ?? ""}}` : "");
          const inputText = (order.blocking_input_item_ids || []).join(", ") || "input inconnu";
          const completionText = order.completed_lot_id ? ` -> ${{order.completed_lot_id}} J${{order.completed_day}}` : "";
          const prefix = isCompletedAfterDelay ? "[VIOLET - RATTRAPAGE]" : "[ROUGE - ORDRE REPORTE]";
          opt.textContent = `${{prefix}} ${{delayText}} | ${{order.output_item_id || ""}} | manque ${{inputText}} | ${{status}}${{completionText}}`;
          opt.className = isCompletedAfterDelay ? "deferredOrderCompleted" : "deferredOrderBlocked";
          opt.style.color = isCompletedAfterDelay ? "#7c3aed" : "#991b1b";
          opt.style.fontWeight = "900";
          opt.title = order.campaign_id || "";
          orderGroup.appendChild(opt);
        }});
        target.appendChild(orderGroup);
      }}
      function populateSelect(target, includeDeferredOrders = false) {{
        if (!target) return;
        target.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = (LOT_TRACE.available || lotTraceDeferredOrders().length) ? "Selection" : "Aucun lot ou ordre traceable";
        target.appendChild(empty);
        const deferredOrders = lotTraceDeferredOrders();
        const options = Array.isArray(LOT_TRACE.lot_options) ? LOT_TRACE.lot_options : [];
        if (options.length) {{
          const groups = new Map();
          options.forEach((lot) => {{
            const groupLabel = lot.trace_scope_label || "Lots traceables";
            if (!groups.has(groupLabel)) {{
              const group = document.createElement("optgroup");
              group.label = groupLabel;
              groups.set(groupLabel, group);
            }}
            const opt = document.createElement("option");
            opt.value = String(lot.lot_id || "");
            const statusPrefix = lotTracePfStatusShortLabel(lot);
            opt.textContent = statusPrefix ? `[${{statusPrefix}}] ${{lot.label || String(lot.lot_id || "")}}` : (lot.label || String(lot.lot_id || ""));
            const statusClass = lotTracePfStatusClass(lot);
            const statusColor = lotTracePfStatusColor(lot);
            if (statusClass) {{
              opt.className = statusClass;
              opt.style.color = statusColor;
              opt.style.fontWeight = "800";
              opt.title = lot.pf_availability_status_label || "";
            }}
            groups.get(groupLabel).appendChild(opt);
          }});
          groups.forEach(group => target.appendChild(group));
        }}
        if (includeDeferredOrders) appendDeferredOrderOptions(target, deferredOrders);
      }}
      populateSelect(select, false);
      populateSelect(modalSelect, true);
      if (!select && !modalSelect) return;
      const onLotChange = (ev) => setSelectedLot(String(ev.target.value || ""));
      if (select) select.addEventListener("change", onLotChange);
      if (modalSelect) modalSelect.addEventListener("change", onLotChange);
      if (!selectedLotId) selectedLotId = lotTraceDefaultSelection(false);
      if (selectedLotId) lotTraceDirection = lotTracePreferredDirection(selectedLotId);
      const focusBtn = document.getElementById("lotTraceFocusBtn");
      if (focusBtn) focusBtn.addEventListener("click", () => focusSelectedLot());
      const openBtn = document.getElementById("lotTraceOpenBtn");
      const ordersBtn = document.getElementById("lotTraceOrdersBtn");
      const modal = document.getElementById("lotTraceModal");
      if (openBtn && modal) openBtn.addEventListener("click", () => {{
        if (!selectedLotId) selectedLotId = lotTraceDefaultSelection(false);
        modal.classList.add("visible");
        updateLotTraceControls();
      }});
      if (ordersBtn && modal) ordersBtn.addEventListener("click", () => {{
        const orderSelection = lotTraceDefaultSelection(true);
        if (orderSelection) {{
          selectedLotId = orderSelection;
          lotTraceDirection = "both";
          lotTraceShowDetails = true;
        }}
        modal.classList.add("visible");
        updateLotTraceControls();
      }});
      const clearBtn = document.getElementById("lotTraceClearBtn");
      if (clearBtn) clearBtn.addEventListener("click", () => setSelectedLot(""));
      const closeBtn = document.getElementById("lotTracePanelCloseBtn");
      if (closeBtn) closeBtn.addEventListener("click", () => {{
        const panel = document.getElementById("lotTracePanel");
        if (panel) panel.classList.remove("visible");
      }});
      const modalCloseBtn = document.getElementById("lotTraceModalCloseBtn");
      if (modalCloseBtn && modal) modalCloseBtn.addEventListener("click", () => {{
        modal.classList.remove("visible");
      }});
      if (modal) modal.addEventListener("click", (ev) => {{
        if (ev.target === modal) modal.classList.remove("visible");
      }});
      document.querySelectorAll(".lotTraceDirectionBtn").forEach(btn => {{
        btn.addEventListener("click", () => {{
          lotTraceDirection = String(btn.dataset.lotTraceDirection || "both");
          renderLotTraceModal();
        }});
      }});
      const orderDetailsBtn = document.getElementById("lotTraceOrderDetailsBtn");
      if (orderDetailsBtn) orderDetailsBtn.addEventListener("click", () => {{
        lotTraceShowDetails = !lotTraceShowDetails;
        renderLotTraceModal();
      }});
    }}

    function setSelectedLot(lotId) {{
      selectedLotId = lotId || "";
      lotTraceShowDetails = false;
      if (selectedLotId) lotTraceDirection = lotTracePreferredDirection(selectedLotId);
      lastFactoryPanelRenderKey = "";
      updateLotTraceControls();
      renderGlobalKpiTreeIfVisible();
      draw();
    }}

    function lotTracePreferredDirection(lotId) {{
      if (selectedDeferredOrder(lotId)) return "both";
      const info = (LOT_TRACE.lots || {{}})[lotId] || {{}};
      const scope = String(info.trace_scope || "");
      if (scope === "finished_product" || scope === "finished_product_opening") return "upstream";
      if (scope === "supplier_material" || scope === "raw_material_opening") return "downstream";
      return "both";
    }}

    function focusSelectedLot() {{
      const order = selectedDeferredOrder();
      if (order) {{
        const node = nodeById[String(order.node_id || "")];
        if (node) {{
          selectedPanelNodeId = node.id;
          selectedPanelNodeType = node.type;
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          centerViewOnPoints([node], 1.35);
          refreshFactoryPanel();
          draw();
        }}
        return;
      }}
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot) return;
      const focusNode = snapshot.nodeIds.map(nodeId => nodeById[nodeId]).find(Boolean);
      if (!focusNode) {{
        draw();
        return;
      }}
      selectedPanelNodeId = focusNode.id;
      selectedPanelNodeType = focusNode.type;
      currentHoveredPanelId = null;
      currentHoveredPanelType = null;
      panelAnchorClientX = null;
      panelAnchorClientY = null;
      draw();
    }}

    function applyLotTraceHtmlHighlight(rootEl) {{
      if (!rootEl) return;
      rootEl.querySelectorAll(".lotTraceMatch").forEach(el => el.classList.remove("lotTraceMatch"));
      if (!selectedLotId || currentPanelMode !== "ops") return;
      const tokens = selectedLotHighlightTokens();
      if (!tokens.length) return;
      const targets = Array.from(rootEl.querySelectorAll("tr, .orderLedgerLines"));
      targets.forEach((el) => {{
        const text = el.textContent || "";
        if (tokens.some(token => text.includes(token))) {{
          el.classList.add("lotTraceMatch");
        }}
      }});
    }}

    function plotlyFigureTitleText(plotlyFigure) {{
      const title = ((plotlyFigure || {{}}).layout || {{}}).title;
      if (typeof title === "string") return title;
      if (title && typeof title.text === "string") return title.text;
      return "";
    }}

    function applyLotTracePlotOverlay(plotlyFigure, contextNodeId = "", contextNodeType = "") {{
      if (!plotlyFigure || !selectedLotId || currentPanelMode !== "ops") return plotlyFigure;
      const numericTrace = (plotlyFigure.data || []).some(trace =>
        (trace.x || []).some(value => Number.isFinite(Number(value)))
      );
      if (!numericTrace) return plotlyFigure;
      const customerDemandOverlay = selectedLotTraceCustomerDemandOverlay(plotlyFigure, contextNodeId, contextNodeType);
      let markers = selectedLotTraceMarkersForPlot(plotlyFigure, contextNodeId, contextNodeType);
      if (customerDemandOverlay) {{
        markers = markers.filter(marker => marker.kind !== "service");
      }}
      const compactedMarkers = lotTraceCompactMarkers(markers, 140);
      markers = compactedMarkers.markers;
      if (!markers.length && !customerDemandOverlay) return plotlyFigure;
      const data = (plotlyFigure.data || []).slice();
      const layout = {{ ...(plotlyFigure.layout || {{}}) }};
      if (customerDemandOverlay) {{
        data.push({{
          type: "bar",
          name: `${{selectedLotId}} - demande servie`,
          x: customerDemandOverlay.days,
          y: customerDemandOverlay.values,
          marker: {{ color: "#f97316", opacity: 0.42 }},
          hovertemplate: "J%{{x}}<br>Demande servie par le lot=%{{y:,.1f}}<extra></extra>",
        }});
        layout.barmode = "overlay";
      }}
      const axisRefs = Array.from(new Set(data
        .map(trace => String(trace.xaxis || "x"))
        .filter(axisName => axisName && axisName !== "undefined")));
      if (!axisRefs.length) axisRefs.push("x");
      layout.shapes = Array.isArray(layout.shapes) ? layout.shapes.slice() : [];
      markers.forEach((marker) => {{
        const day = marker.day;
        const style = lotTraceMarkerStyle(marker.kind);
        const isMajorMarker = marker.kind === "production" || marker.kind === "delay";
        axisRefs.forEach((xref) => {{
          layout.shapes.push({{
            type: "line",
            xref,
            yref: "paper",
            x0: day,
            x1: day,
            y0: isMajorMarker ? 0 : 0.90,
            y1: 1,
            line: {{
              color: style.color,
              width: style.width,
              dash: style.dash,
            }},
            opacity: isMajorMarker ? 0.82 : 0.72,
          }});
        }});
      }});
      function markerAxisStats(axisName = "y") {{
        const values = [];
        data.forEach((trace) => {{
          const traceAxis = String(trace.yaxis || "y");
          if (traceAxis !== axisName) return;
          (trace.y || []).forEach((value) => {{
            const numeric = Number(value);
            if (Number.isFinite(numeric)) values.push(numeric);
          }});
        }});
        if (!values.length) return {{ min: 0, max: 1, range: 1 }};
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = Math.max(1, max - min);
        return {{ min, max, range }};
      }}
      const markerGroups = new Map();
      markers.forEach((marker) => {{
        const kind = marker.kind || "event";
        if (!markerGroups.has(kind)) markerGroups.set(kind, []);
        markerGroups.get(kind).push(marker);
      }});
      const axisStats = markerAxisStats("y");
      Array.from(markerGroups.entries()).forEach(([kind, group], groupIdx) => {{
        const style = lotTraceMarkerStyle(kind);
        const markerY = axisStats.min + axisStats.range * Math.max(0.74, 0.96 - groupIdx * 0.035);
        data.push({{
          type: "scatter",
          mode: "markers",
          name: `${{selectedLotId}} - ${{style.label}}`,
          x: group.map(marker => marker.day),
          y: group.map(() => markerY),
          marker: {{
            color: style.color,
            symbol: style.symbol,
            size: 8,
            line: {{ color: "#ffffff", width: 1 }},
          }},
          customdata: group.map(marker => [
            marker.label || style.label,
            marker.qty || 0,
            marker.count || 1,
            (marker.lots || []).slice(0, 4).join(", "),
            (marker.itemIds || []).slice(0, 4).join(", "),
          ]),
          hovertemplate: "J%{{x}}<br>%{{customdata[0]}}<br>qte tracee=%{{customdata[1]:,.1f}}<br>evenements=%{{customdata[2]}}<br>lots=%{{customdata[3]}}<br>items=%{{customdata[4]}}<extra></extra>",
        }});
      }});
      layout.annotations = Array.isArray(layout.annotations) ? layout.annotations.slice() : [];
      const categories = Array.from(new Set(markers.map(marker => marker.category).filter(Boolean)));
      const markerLabel = categories.length === 1
        ? lotTracePlotCategoryLabel(categories[0])
        : (customerDemandOverlay ? "disponibilite client du lot" : "trace lot contextuelle");
      const customerDemandText = customerDemandOverlay
        ? ` | demande servie par lot: ${{fmtPanelQty(customerDemandOverlay.total)}}`
        : "";
      const markerSummary = lotTraceMarkerSummaryText(markers, compactedMarkers.hidden);
      const markerSummaryText = markerSummary ? ` | ${{markerSummary}}` : "";
      layout.annotations.push({{
        text: `${{selectedLotId}} - ${{markerLabel}}${{markerSummaryText}}${{customerDemandText}}`,
        xref: "paper",
        yref: "paper",
        x: 1,
        y: 1.08,
        xanchor: "right",
        yanchor: "bottom",
        showarrow: false,
        font: {{ size: 10, color: "#c2410c" }},
      }});
      return {{ data, layout }};
    }}

    function scopeBadgeClass(scope) {{
      if (scope === "pf") return "scopeBadge scopeFinal";
      if (scope === "pfi") return "scopeBadge scopeIntermediate";
      return "scopeBadge";
    }}

    function selectedMaterialYears() {{
      const start = Math.max(1, Math.min(selectedYearStart, selectedYearEnd));
      const end = Math.max(start, Math.max(selectedYearStart, selectedYearEnd));
      const years = [];
      for (let year = start; year <= end; year += 1) {{
        years.push(year);
      }}
      return years;
    }}

    function aggregateMaterialRow(row) {{
      const years = selectedMaterialYears();
      const yearly = row.yearly || {{}};
      let days = 0;
      let planned = 0;
      let delivered = 0;
      let consumed = 0;
      let initial = null;
      let finalStock = 0;
      let foundYear = false;
      years.forEach((year) => {{
        const bucket = yearly[String(year)];
        if (!bucket) return;
        foundYear = true;
        days += Number(bucket.days) || 0;
        planned += Number(bucket.planned_qty) || 0;
        delivered += Number(bucket.delivered_qty) || 0;
        consumed += Number(bucket.consumed_qty) || 0;
        const bucketInitial = Number(bucket.initial_qty);
        if (initial === null && Number.isFinite(bucketInitial)) {{
          initial = bucketInitial;
        }}
        const bucketFinal = Number(bucket.final_stock_qty);
        if (Number.isFinite(bucketFinal)) {{
          finalStock = bucketFinal;
        }}
      }});
      if (!foundYear) {{
        days = Math.max(1, Number(row.days) || 0);
        planned = Number(row.planned_qty) || 0;
        delivered = Number(row.delivered_qty) || 0;
        consumed = Number(row.consumed_qty) || 0;
        initial = Number(row.initial_qty) || 0;
        finalStock = Number(row.final_stock_qty) || 0;
      }}
      if (row.scope === "pfi") {{
        planned = Math.max(consumed, delivered);
      }}
      const safetyDays = Math.max(0, Number(row.safety_time_days) || 0);
      const avgDaily = days > 0 ? planned / days : Math.max(0, Number(row.avg_daily_need_qty) || 0);
      const stockEquivSafety = avgDaily * safetyDays;
      let gap = consumed - planned;
      if (row.scope === "pf") {{
        gap = delivered - planned;
      }} else if (row.scope === "pfi") {{
        gap = delivered - Math.max(consumed, delivered);
      }}
      let diagnostic = row.diagnostic || "";
      const tol = Math.max(1, Math.abs(planned) * 0.01);
      if (row.scope === "pf") {{
        diagnostic = Math.abs(gap) <= tol ? "demande servie sur la fenetre" : "ecart service sur la fenetre";
      }} else if (row.scope === "material") {{
        if (consumed <= 1e-9 && delivered <= 1e-9 && (initial || 0) > 0) {{
          diagnostic = "coherent dormant sur la fenetre";
        }} else if (delivered > 0 || consumed > 0) {{
          diagnostic = "actif sur la fenetre";
        }} else {{
          diagnostic = "inactif sur la fenetre";
        }}
      }} else if (row.scope === "pfi") {{
        diagnostic = (delivered > 0 || consumed > 0) ? "PFI actif sur la fenetre" : "PFI inactif sur la fenetre";
      }}
      return {{
        ...row,
        planned_qty: planned,
        avg_daily_need_qty: avgDaily,
        stock_equiv_safety_time_qty: stockEquivSafety,
        initial_qty: initial === null ? 0 : initial,
        delivered_qty: delivered,
        consumed_qty: consumed,
        final_stock_qty: finalStock,
        gap_vs_need_qty: gap,
        diagnostic,
        selected_days: days,
      }};
    }}

    function renderMaterialTable() {{
      const tbody = document.querySelector("#materialTableModal .materialTable tbody");
      const meta = document.getElementById("materialTableMeta");
      if (!tbody || !meta || !Array.isArray(MATERIAL_BALANCE_ROWS) || !MATERIAL_BALANCE_ROWS.length) return;
      const rows = MATERIAL_BALANCE_ROWS.map(aggregateMaterialRow);
      tbody.innerHTML = rows.map((row) => `
        <tr>
          <td><span class="${{scopeBadgeClass(row.scope)}}">${{escapeTableHtml(row.scope_label || "")}}</span></td>
          <td>${{escapeTableHtml(String(row.item_id || "").replace(/^item:/, ""))}}</td>
          <td>${{escapeTableHtml(row.node_label || "")}}</td>
          <td class="num">${{fmtPanelQty(row.planned_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.avg_daily_need_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.safety_time_days, 1)}}</td>
          <td class="num">${{fmtPanelQty(row.stock_equiv_safety_time_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.initial_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.delivered_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.consumed_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.gap_vs_need_qty, 3)}}</td>
          <td>${{escapeTableHtml(row.unit || "")}}</td>
          <td>${{escapeTableHtml(row.diagnostic || "")}}</td>
        </tr>
      `).join("");
      const years = selectedMaterialYears();
      const totalDays = rows.reduce((maxDays, row) => Math.max(maxDays, Number(row.selected_days) || 0), 0);
      meta.textContent = `${{rows.length}} lignes - annee ${{years[0]}} -> ${{years[years.length - 1]}} - ${{totalDays}} j`;
    }}

    function buildFactoryWindowSummaryLines(metrics) {{
      if (!metrics || !Array.isArray(metrics.daily_metrics) || !metrics.daily_metrics.length) {{
        return (metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : [];
      }}
      const range = currentTimelineDayRange();
      const rows = (currentPanelMode === "ops")
        ? metrics.daily_metrics.filter((row) => Number(row.day) >= range.startDay && Number(row.day) <= range.endDay)
        : metrics.daily_metrics.slice();
      if (!rows.length) {{
        return (metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : [];
      }}
      const totalDesired = rows.reduce((sum, row) => sum + (Number(row.desired_qty) || 0), 0);
      const totalActual = rows.reduce((sum, row) => sum + (Number(row.actual_qty) || 0), 0);
      const totalShortfall = rows.reduce((sum, row) => sum + (Number(row.shortfall_qty) || 0), 0);
      const peakShortfall = rows.reduce((peak, row) => Math.max(peak, Number(row.shortfall_qty) || 0), 0);
      const capacityDays = rows.reduce((count, row) => count + ((Number(row.capacity_binding) || 0) > 0 ? 1 : 0), 0);
      const leadDays = Number(metrics.avg_inbound_lead_days);
      const windowLabel = timelineMaxYear > 1
        ? `annee ${{selectedYearStart}} -> ${{selectedYearEnd}}`
        : `jours ${{rows[0].day}} -> ${{rows[rows.length - 1].day}}`;
      return [
        {{ label: "Fenetre analysee", value: windowLabel }},
        {{ label: "Production demandee cumulee", value: fmtPanelQty(totalDesired, 1) }},
        {{ label: "Production reelle cumulee", value: fmtPanelQty(totalActual, 1) }},
        {{ label: "Manque de production cumule", value: fmtPanelQty(totalShortfall, 1) }},
        {{ label: "Pic de manque de production", value: fmtPanelQty(peakShortfall, 1) }},
        {{ label: "Jours contraints capacite", value: String(capacityDays) }},
        {{ label: "Lead time entrant moyen", value: Number.isFinite(leadDays) ? `${{leadDays.toFixed(1)}} j` : "n/a" }},
      ];
    }}

    function styleForType(nodeType, idx) {{
      const s = STYLES[nodeType] || {{}};
      return {{
        name: s.name || nodeType,
        color: s.color || defaultPalette[idx % defaultPalette.length],
        symbol: s.symbol || "circle",
      }};
    }}

    function supplierStressCampaignMeta(nodeId) {{
      return ((SIMULATED_RISK_CAMPAIGN_METRICS.nodes || {{}})[nodeId]) || null;
    }}

    function nodeSensitivityMeta(nodeId) {{
      const meta = SUPPLIER_PARAMETER_SENSITIVITY_NODES[nodeId] || null;
      if (meta) return meta;
      return null;
    }}

    function simulatedRiskStateHasNodes() {{
      if (Object.keys(SIMULATED_RISK_NODE_IMPACTS || {{}}).length > 0) return true;
      if (Object.keys(SIMULATED_RISK_EDGE_IMPACTS || {{}}).length > 0) return true;
      const nodes = (SIMULATED_RISK_STATE_METRICS && SIMULATED_RISK_STATE_METRICS.nodes) || {{}};
      return Object.values(nodes).some((meta) => {{
        if (!meta || typeof meta !== "object") return false;
        if (Number(meta.applied_event_count || 0) > 0) return true;
        if (Number(meta.applied_case_count || 0) > 0) return true;
        const families = meta.applied_family_counts || {{}};
        return Object.values(families).some((value) => Number(value || 0) > 0);
      }});
    }}

    function simulatedRiskCampaignHasNodes() {{
      return Object.keys((SIMULATED_RISK_CAMPAIGN_METRICS && SIMULATED_RISK_CAMPAIGN_METRICS.nodes) || {{}}).length > 0;
    }}

    function simulatedRiskVisibleMode() {{
      normalizeSimulatedRiskViewMode();
      if (simulatedRiskViewMode === "campaign" && simulatedRiskCampaignHasNodes()) return "campaign";
      if (simulatedRiskViewMode === "state" && simulatedRiskStateHasNodes()) return "state";
      if (simulatedRiskStateHasNodes()) return "state";
      if (simulatedRiskCampaignHasNodes()) return "campaign";
      return "empty";
    }}

    function normalizeSimulatedRiskViewMode() {{
      if (simulatedRiskViewMode === "campaign" && simulatedRiskCampaignHasNodes()) return;
      if (simulatedRiskViewMode === "state" && simulatedRiskStateHasNodes()) return;
      simulatedRiskViewMode = simulatedRiskStateHasNodes()
        ? "state"
        : (simulatedRiskCampaignHasNodes() ? "campaign" : "state");
    }}

    function selectedSimulatedRiskMetrics() {{
      normalizeSimulatedRiskViewMode();
      if (simulatedRiskVisibleMode() === "state" && simulatedRiskStateHasNodes()) {{
        return SIMULATED_RISK_STATE_METRICS || {{ nodes: {{}}, global: {{}} }};
      }}
      if (simulatedRiskVisibleMode() === "campaign" && simulatedRiskCampaignHasNodes()) {{
        return {{
          nodes: (SIMULATED_RISK_CAMPAIGN_METRICS && SIMULATED_RISK_CAMPAIGN_METRICS.nodes) || {{}},
          global: (SIMULATED_RISK_CAMPAIGN_METRICS && SIMULATED_RISK_CAMPAIGN_METRICS.global) || {{}},
        }};
      }}
      return SIMULATED_RISK_STATE_METRICS || {{ nodes: {{}}, global: {{}} }};
    }}

    function nodeSimulatedRiskMeta(nodeId) {{
      return (selectedSimulatedRiskMetrics().nodes || {{}})[nodeId] || null;
    }}

    function simulatedRiskNodeImpact(nodeId) {{
      if (simulatedRiskVisibleMode() !== "state") return null;
      const row = selectedSimulatedRiskCascade();
      const globalImpact = SIMULATED_RISK_NODE_IMPACTS[nodeId] || null;
      if (row) {{
        if (!selectedSimulatedRiskCascadeIncludesNode(nodeId)) return null;
        const color = simulatedRiskCascadeStageColor(row.stage);
        return {{
          ...(globalImpact || {{}}),
          selected_cascade: true,
          color,
          score: Math.max(Number((globalImpact || {{}}).score) || 0, 0.82),
          stage: row.stage || (globalImpact || {{}}).stage || "",
          stage_label: row.stage_label || simulatedRiskCascadeStageLabel(row),
          status_label: row.absorption_label || row.stage_label || simulatedRiskCascadeStageLabel(row),
          primary_trigger: row.trigger || row.trigger_metric || row.root_cause_label || (globalImpact || {{}}).primary_trigger || "cascade selectionnee",
          period: row.period || simulatedRiskCascadePeriodText(row) || (globalImpact || {{}}).period || "n/a",
          supplier_id: row.supplier_id || (globalImpact || {{}}).supplier_id || "",
          supplier_label: row.supplier_label || (globalImpact || {{}}).supplier_label || "",
          item_id: row.item_id || (globalImpact || {{}}).item_id || "",
          item_label: row.item_label || (globalImpact || {{}}).item_label || "",
          production_delay_count: row.production_delay_count ?? (globalImpact || {{}}).production_delay_count ?? 0,
          production_shortfall_qty: row.production_shortfall_qty ?? (globalImpact || {{}}).production_shortfall_qty ?? 0,
          customer_backlog_max_qty: row.customer_backlog_max_qty ?? (globalImpact || {{}}).customer_backlog_max_qty ?? 0,
          root_count: row.root_count ?? (globalImpact || {{}}).root_count ?? 1,
          effective_root_count: row.effective_root_count ?? (globalImpact || {{}}).effective_root_count ?? 1,
        }};
      }}
      return globalImpact;
    }}

    function simulatedRiskEdgeImpact(edgeId) {{
      if (simulatedRiskVisibleMode() !== "state") return null;
      const row = selectedSimulatedRiskCascade();
      const globalImpact = SIMULATED_RISK_EDGE_IMPACTS[edgeId] || null;
      if (row) {{
        if (!selectedSimulatedRiskCascadeIncludesEdge(edgeId)) return null;
        const edge = EDGE_BY_ID[edgeId] || {{}};
        const duration = simulatedRiskCascadeDuration(row);
        const itemIds = new Set([
          row.item_id,
          ...(Array.isArray(row.impacted_output_items) ? row.impacted_output_items : []),
          ...(Array.isArray(edge.items) ? edge.items : []),
        ].map(value => String(value || "")).filter(Boolean));
        return {{
          ...(globalImpact || {{}}),
          selected_cascade: true,
          color: simulatedRiskCascadeStageColor(row.stage),
          score: Math.max(Number((globalImpact || {{}}).score) || 0, 0.82),
          status_label: row.stage_label || simulatedRiskCascadeStageLabel(row),
          period: row.period || simulatedRiskCascadePeriodText(row) || (globalImpact || {{}}).period || "n/a",
          active_day_count: duration ?? (globalImpact || {{}}).active_day_count ?? 0,
          delay_row_count: row.applied_event_count ?? (globalImpact || {{}}).delay_row_count ?? 0,
          max_extra_days: (globalImpact || {{}}).max_extra_days ?? 0,
          max_multiplier: (globalImpact || {{}}).max_multiplier ?? 1,
          item_ids: [...itemIds],
          event_examples: [row.root_cause_label || row.trigger || "cascade selectionnee"].filter(Boolean),
        }};
      }}
      return globalImpact;
    }}

    function simulatedRiskImpactLines(impact) {{
      if (!impact) return [];
      const lines = [];
      if (impact.stage_label) lines.push(`Impact reel: ${{impact.stage_label}}`);
      if (impact.status_label) lines.push(`Statut: ${{impact.status_label}}`);
      if (impact.primary_trigger) lines.push(`Declencheur: ${{impact.primary_trigger}}`);
      if (impact.period) lines.push(`Periode: ${{impact.period}}`);
      if (Number.isFinite(Number(impact.effective_root_count)) || Number.isFinite(Number(impact.root_count))) {{
        lines.push(`Causes supply actives: ${{impact.effective_root_count || 0}} / ${{impact.root_count || 0}}`);
      }}
      if (Number(impact.production_delay_count || 0) > 0) {{
        lines.push(`Replanification production: ${{impact.production_delay_count}} lignes ; volume associe=${{fmtPanelQty(Number(impact.production_shortfall_qty) || 0, 0)}}`);
      }}
      if (Number(impact.customer_backlog_max_qty || 0) > 0) {{
        lines.push(`Backlog client max: ${{fmtPanelQty(Number(impact.customer_backlog_max_qty) || 0, 0)}}`);
      }}
      if (impact.supplier_label || impact.item_label) {{
        lines.push(`Origine: ${{impact.supplier_label || impact.supplier_id || "n/a"}} / ${{impact.item_label || impact.item_id || "n/a"}}`);
      }}
      return lines;
    }}

    function simulatedRiskEdgeImpactLines(impact) {{
      if (!impact) return [];
      const itemText = Array.isArray(impact.item_ids) && impact.item_ids.length ? impact.item_ids.join(", ") : "n/a";
      const events = Array.isArray(impact.event_examples) && impact.event_examples.length ? impact.event_examples.join(", ") : "n/a";
      return [
        `Risque flux: ${{impact.status_label || "Delai transport impacte"}}`,
        `Periode: ${{impact.period || "n/a"}}`,
        `Jours touches: ${{impact.active_day_count || 0}} ; lignes appliquees: ${{impact.delay_row_count || 0}}`,
        `Delai ajoute max: ${{fmtPanelQty(Number(impact.max_extra_days) || 0, 1)}} j`,
        `Multiplicateur lead max: ${{fmtMultiplierPercent(Number(impact.max_multiplier) || 1)}}`,
        `Articles: ${{itemText}}`,
        `Evenements: ${{events}}`,
      ];
    }}

    function simulatedRiskEdgeAsset(edgeId) {{
      const impact = simulatedRiskEdgeImpact(edgeId);
      if (!impact) return null;
      const rows = simulatedRiskEdgeImpactLines(impact).map(line => {{
        const parts = line.split(":");
        const label = parts.length > 1 ? parts.shift() : "Lecture";
        const value = parts.join(":").trim() || line;
        return `<tr><td>${{escapeHtmlText(label)}}</td><td>${{escapeHtmlText(value)}}</td></tr>`;
      }}).join("");
      return {{
        html: `
          <div class="factoryHtmlPanelContent sensitivityHtmlPanelContent">
            <div class="orderLedgerTextHeader">${{escapeHtmlText(edgeId)}} - delai transport impacte</div>
            <div class="orderLedgerStatus">Lecture metier: ce flux a subi un evenement de delai dans le scenario applique. Les lignes grises restent les flux non retardes.</div>
            <div class="kpiFormulaTableWrap"><table class="kpiFormulaTable"><tbody>${{rows}}</tbody></table></div>
          </div>
        `
      }};
    }}

    function simulatedRiskCascadeRows() {{
      const groupedRows = Array.isArray(SIMULATED_RISK_GLOBAL_DIAGNOSTIC.cascade_path_groups)
        ? SIMULATED_RISK_GLOBAL_DIAGNOSTIC.cascade_path_groups
        : [];
      const rootRows = Array.isArray(SIMULATED_RISK_GLOBAL_DIAGNOSTIC.cascade_roots)
        ? SIMULATED_RISK_GLOBAL_DIAGNOSTIC.cascade_roots
        : [];
      const rows = groupedRows.length ? groupedRows : rootRows;
      return rows.slice().sort((a, b) => Number(b.impact_score || 0) - Number(a.impact_score || 0));
    }}

    function simulatedRiskCascadeKey(row, idx = 0) {{
      if (!row) return "";
      return String(row.business_path_key || row.root_key || row.event_id || `${{row.stage || "cascade"}}|${{row.supplier_id || ""}}|${{row.item_id || ""}}|${{row.root_day ?? idx}}`);
    }}

    function simulatedRiskCascadeKeyForRow(row) {{
      const rows = simulatedRiskCascadeRows();
      const idx = rows.indexOf(row);
      return simulatedRiskCascadeKey(row, idx >= 0 ? idx : 0);
    }}

    function simulatedRiskCascadeFamilies(row) {{
      const values = [];
      if (Array.isArray(row && row.risk_families)) values.push(...row.risk_families);
      if (row && row.risk_family) values.push(row.risk_family);
      return [...new Set(values.map(value => String(value || "")).filter(Boolean))];
    }}

    function simulatedRiskCascadeStageColor(stage) {{
      const key = String(stage || "");
      if (key === "service_client") return "#dc2626";
      if (key === "production") return "#d97706";
      if (key === "cost") return "#475569";
      if (key === "local_absorbed") return "#0f766e";
      if (key === "configured_only") return "#94a3b8";
      return "#64748b";
    }}

    function simulatedRiskCascadeStageLabel(row) {{
      const stage = String((row && row.stage) || "");
      if (row && row.absorption_label) return row.absorption_label;
      if (row && row.stage_label) return row.stage_label;
      if (stage === "service_client") return "Client atteint";
      if (stage === "production") return "Production reportee";
      if (stage === "cost") return "Surcout";
      if (stage === "local_absorbed") return "Absorbe localement";
      if (stage === "configured_only") return "Sans effet";
      return "Impact supply";
    }}

    function simulatedRiskCascadeMatchesFilters(row) {{
      if (!row) return false;
      if (simulatedRiskCascadeStageFilter !== "all" && String(row.stage || "") !== simulatedRiskCascadeStageFilter) return false;
      if (simulatedRiskCascadeFamilyFilter !== "all") {{
        const families = simulatedRiskCascadeFamilies(row);
        if (!families.includes(simulatedRiskCascadeFamilyFilter)) return false;
      }}
      const text = String(simulatedRiskCascadeTextFilter || "").trim().toLowerCase();
      if (text) {{
        const haystack = [
          row.root_cause_label,
          row.label,
          row.supplier_label,
          row.item_label,
          row.supplier_id,
          row.item_id,
          row.stage_label,
          row.absorption_label,
          row.reading,
          row.period,
          row.business_path_label,
          row.route_text,
          row.worst_period,
          ...(Array.isArray(row.affected_factory_labels) ? row.affected_factory_labels : []),
          ...(Array.isArray(row.affected_customer_labels) ? row.affected_customer_labels : []),
          ...(Array.isArray(row.impacted_output_item_labels) ? row.impacted_output_item_labels : []),
          ...(Array.isArray(row.affected_factory_nodes) ? row.affected_factory_nodes : []),
          ...(Array.isArray(row.affected_customer_nodes) ? row.affected_customer_nodes : []),
          ...(Array.isArray(row.impacted_output_items) ? row.impacted_output_items : []),
          ...(Array.isArray(row.highlight_edge_ids) ? row.highlight_edge_ids : []),
          ...(Array.isArray(row.route_edge_ids) ? row.route_edge_ids : []),
          ...(Array.isArray(row.route_edge_labels) ? row.route_edge_labels : []),
        ].map(value => String(value || "").toLowerCase()).join(" ");
        if (!haystack.includes(text)) return false;
      }}
      return true;
    }}

    function filteredSimulatedRiskCascadeRows() {{
      return simulatedRiskCascadeRows().filter(simulatedRiskCascadeMatchesFilters);
    }}

    function selectedSimulatedRiskCascade() {{
      if (!selectedSimulatedRiskCascadeKey) return null;
      return simulatedRiskCascadeRows().find((row, idx) => simulatedRiskCascadeKey(row, idx) === selectedSimulatedRiskCascadeKey) || null;
    }}

    function simulatedRiskCascadeNodeIds(row) {{
      if (!row) return [];
      const ids = [];
      if (Array.isArray(row.route_node_ids)) ids.push(...row.route_node_ids);
      if (Array.isArray(row.highlight_node_ids)) ids.push(...row.highlight_node_ids);
      if (row.supplier_id) ids.push(row.supplier_id);
      if (Array.isArray(row.affected_factory_nodes)) ids.push(...row.affected_factory_nodes);
      if (Array.isArray(row.affected_customer_nodes)) ids.push(...row.affected_customer_nodes);
      if (Array.isArray(row.impacted_nodes)) ids.push(...row.impacted_nodes.map(node => node && node.node_id));
      return [...new Set(ids.map(value => String(value || "")).filter(Boolean))];
    }}

    function simulatedRiskCascadeEdgeIds(row) {{
      if (!row) return [];
      const ids = [];
      if (Array.isArray(row.route_edge_ids)) ids.push(...row.route_edge_ids);
      if (Array.isArray(row.highlight_edge_ids)) ids.push(...row.highlight_edge_ids);
      if (Array.isArray(row.impacted_edges)) ids.push(...row.impacted_edges.map(edge => edge && edge.edge_id));
      return [...new Set(ids.map(value => String(value || "")).filter(Boolean))];
    }}

    function simulatedRiskCascadePathSignature(row) {{
      const nodes = simulatedRiskCascadeNodeIds(row).join(">");
      const edges = simulatedRiskCascadeEdgeIds(row).join(">");
      return `${{nodes}}|${{edges}}`;
    }}

    function diversifiedSimulatedRiskCascadeRows(rows, limit = 120) {{
      const input = Array.isArray(rows) ? rows : [];
      const seenPaths = new Set();
      const diversified = [];
      const repeated = [];
      input.forEach(row => {{
        const signature = simulatedRiskCascadePathSignature(row);
        if (signature && !seenPaths.has(signature)) {{
          seenPaths.add(signature);
          diversified.push(row);
        }} else {{
          repeated.push(row);
        }}
      }});
      return [...diversified, ...repeated].slice(0, limit);
    }}

    function simulatedRiskCascadeRouteText(row) {{
      if (!row) return "n/a";
      if (row.route_text) return String(row.route_text);
      if (row.business_path_label) return String(row.business_path_label);
      const supplier = row.supplier_id || "origine";
      const factories = Array.isArray(row.affected_factory_nodes) && row.affected_factory_nodes.length
        ? row.affected_factory_nodes.join(",")
        : "";
      const customers = Array.isArray(row.affected_customer_nodes) && row.affected_customer_nodes.length
        ? row.affected_customer_nodes.join(",")
        : "";
      const route = [supplier, factories, customers].filter(Boolean).join(" -> ");
      const item = row.item_id || "item n/a";
      const edgeCount = simulatedRiskCascadeEdgeIds(row).length;
      const suffix = edgeCount ? `${{edgeCount}} flux` : "flux non localise";
      return `${{route || supplier}} | ${{item}} | ${{suffix}}`;
    }}

    function selectedSimulatedRiskCascadeNodeIdSet() {{
      const row = selectedSimulatedRiskCascade();
      return new Set(simulatedRiskCascadeNodeIds(row));
    }}

    function selectedSimulatedRiskCascadeEdgeIdSet() {{
      const row = selectedSimulatedRiskCascade();
      if (!row) return new Set();
      const directIds = simulatedRiskCascadeEdgeIds(row);
      const derivedIds = selectedSimulatedRiskCascadeMapEdges().map(edge => String(edge.id || ""));
      return new Set([...directIds, ...derivedIds].filter(Boolean));
    }}

    function selectedSimulatedRiskCascadeIncludesNode(nodeId) {{
      if (!selectedSimulatedRiskCascadeKey) return false;
      return selectedSimulatedRiskCascadeNodeIdSet().has(String(nodeId || ""));
    }}

    function selectedSimulatedRiskCascadeIncludesEdge(edgeId) {{
      if (!selectedSimulatedRiskCascadeKey) return false;
      return selectedSimulatedRiskCascadeEdgeIdSet().has(String(edgeId || ""));
    }}

    function setSelectedSimulatedRiskCascade(key, shouldDraw = true) {{
      selectedSimulatedRiskCascadeKey = String(key || "");
      const selected = selectedSimulatedRiskCascade();
      if (selectedSimulatedRiskCascadeKey && !selected) selectedSimulatedRiskCascadeKey = "";
      updateSimulatedRiskControls();
      if (shouldDraw) draw();
      const modal = document.getElementById("simulatedRiskGlobalModal");
      if (modal && modal.classList.contains("visible")) {{
        renderSimulatedRiskGlobalDiagnostic();
      }}
    }}

    function simulatedRiskCascadeShortText(value, limit = 46) {{
      const text = String(value || "n/a").replace(/\s+/g, " ").trim();
      if (text.length <= limit) return text;
      return text.slice(0, Math.max(0, limit - 1)).trimEnd() + "...";
    }}

    function simulatedRiskCascadeNodeLabel(nodeId) {{
      const id = String(nodeId || "");
      const node = nodeById[id] || {{}};
      const name = String(node.name || node.label || "").trim();
      return name && name !== id ? `${{id}} - ${{name}}` : (id || "n/a");
    }}

    function simulatedRiskCascadeItemLabel(itemId) {{
      const raw = String(itemId || "").trim();
      if (!raw) return "n/a";
      return raw.replace(/^item:/, "");
    }}

    function simulatedRiskCascadeListText(values, limit = 3) {{
      const list = Array.isArray(values) ? values.map(value => String(value || "").trim()).filter(Boolean) : [];
      if (!list.length) return "n/a";
      const visible = list.slice(0, limit).join(", ");
      return list.length > limit ? `${{visible}} +${{list.length - limit}}` : visible;
    }}

    function simulatedRiskCascadeRoleLabel(role) {{
      const value = String(role || "");
      const labels = {{
        origin_supplier: "Fournisseur origine",
        local_destination: "Reception locale",
        affected_factory: "Usine touchee",
        affected_customer: "Client touche",
        supplier_flow: "Flux fournisseur",
        local_supply_flow: "Flux fournisseur",
        downstream_route: "Flux aval",
        route: "Flux de route",
        route_node: "Noeud de route",
      }};
      return labels[value] || value || "n/a";
    }}

    function simulatedRiskCascadeEdgeLabel(edgeId) {{
      const id = String(edgeId || "");
      const edge = EDGE_BY_ID[id] || {{}};
      if (edge && (edge.from || edge.to)) {{
        const itemText = Array.isArray(edge.items) && edge.items.length ? ` / ${{edge.items.slice(0, 2).join(", ")}}` : "";
        return `${{edge.from || "?"}} -> ${{edge.to || "?"}}${{itemText}}`;
      }}
      return id || "n/a";
    }}

    function simulatedRiskCascadeValueText(value, digits = 2) {{
      const number = Number(value);
      if (!Number.isFinite(number)) return String(value ?? "n/a");
      const adaptiveDigits = Math.abs(number) > 0 && Math.abs(number) < 1 ? Math.max(digits, 3) : digits;
      return fmtPanelQty(number, adaptiveDigits);
    }}

    function simulatedRiskCascadeTriggerDetail(row) {{
      const metric = String((row && (row.trigger_metric || row.trigger)) || "").trim();
      const value = row ? row.trigger_value : null;
      const threshold = row ? row.threshold : null;
      const consecutive = row ? row.consecutive_days : null;
      const parts = [];
      if (metric) parts.push(metric);
      if (value !== null && value !== undefined && String(value) !== "") parts.push(`valeur ${{simulatedRiskCascadeValueText(value, 2)}}`);
      if (threshold !== null && threshold !== undefined && String(threshold) !== "") parts.push(`seuil ${{simulatedRiskCascadeValueText(threshold, 2)}}`);
      if (consecutive !== null && consecutive !== undefined && String(consecutive) !== "") parts.push(`${{simulatedRiskCascadeValueText(consecutive, 0)}} j consecutifs`);
      return parts.join(" | ") || "signal state-dependent";
    }}

    function simulatedRiskCascadeLocalLines(row) {{
      const app = (row && row.local_application) || {{}};
      const first = app.first_day;
      const last = app.last_day;
      const dayCount = Number(app.day_count || 0);
      const factors = Array.isArray(app.factor_labels) ? app.factor_labels : [];
      const routes = Array.isArray(app.route_labels) ? app.route_labels : [];
      const destinations = Array.isArray(app.destination_labels) ? app.destination_labels : [];
      const period = first !== null && first !== undefined
        ? `J${{first}} -> J${{last ?? first}}${{dayCount ? ` (${{dayCount}} j)` : ""}}`
        : simulatedRiskCascadePeriodText(row);
      return [
        app.summary || row.local_effect || "n/a",
        row.configured_effect ? `Effet: ${{row.configured_effect}}` : `Famille: ${{SIMULATED_RISK_FAMILY_LABELS[row.risk_family] || row.risk_family || "n/a"}}`,
        `Application: ${{period}}`,
        `Facteurs: ${{simulatedRiskCascadeListText(factors, 2)}}`,
        `Route locale: ${{simulatedRiskCascadeListText(routes, 1)}}`,
        `Destination: ${{simulatedRiskCascadeListText(destinations, 1)}}`,
      ];
    }}

    function simulatedRiskCascadePropagationLines(row, itemLabel, outputLabels, factoryLabels, customerLabels, edgeLabels) {{
      const prop = (row && row.propagation_summary) || {{}};
      const serviceWindow = prop.service_window_end_day ? `fenetre aval jusqu'a J${{prop.service_window_end_day}}` : "fenetre aval n/a";
      const productionText = Number(row.production_delay_count || 0) > 0
        ? `Production: ${{row.production_delay_count}} report(s), ${{fmtPanelQty(Number(row.production_shortfall_qty) || 0, 0)}}`
        : "Production: pas de report usine observe";
      const clientText = Number(row.customer_backlog_max_qty || 0) > 0
        ? `Client: backlog max ${{fmtPanelQty(Number(row.customer_backlog_max_qty) || 0, 0)}}`
        : "Client: pas de backlog observe";
      const touchedProduct = outputLabels.length ? simulatedRiskCascadeListText(outputLabels, 2) : itemLabel;
      return [
        serviceWindow,
        productionText,
        `Site: ${{factoryLabels.length ? simulatedRiskCascadeListText(factoryLabels, 1) : "aucun site bloque"}}`,
        `Produit aval: ${{touchedProduct}}`,
        `Flux: ${{simulatedRiskCascadeListText(edgeLabels, 1)}}`,
        clientText,
      ];
    }}

    function simulatedRiskCascadeImpactLines(row) {{
      const absorption = row.absorption_label || simulatedRiskCascadeStageLabel(row);
      const reports = Number(row.production_delay_count || 0);
      const backlog = Number(row.customer_backlog_max_qty || 0);
      const volume = Number(row.production_shortfall_qty || 0);
      const conclusion = reports > 0
        ? "Conclusion: intrant bloque la production"
        : (backlog > 0
          ? "Conclusion: service client touche"
          : (row.stage === "cost" ? "Conclusion: effet economique" : "Conclusion: absorbe avant aval"));
      return [
        absorption,
        simulatedRiskCascadeShortText(row.reading || "n/a", 70),
        `Replanification: ${{reports}} lignes | Volume associe: ${{fmtPanelQty(volume, 0)}}`,
        `Backlog max: ${{fmtPanelQty(backlog, 0)}}`,
        conclusion,
      ];
    }}

    function simulatedRiskCascadeDuration(row) {{
      const explicit = Number(row && row.duration_days);
      if (Number.isFinite(explicit) && explicit > 0) return explicit;
      const start = Number(row && row.start_day);
      const end = Number(row && row.end_day);
      if (Number.isFinite(start) && Number.isFinite(end)) return Math.max(0, Math.round(end - start + 1));
      return null;
    }}

    function simulatedRiskCascadePeriodText(row) {{
      const period = String((row && row.period) || "").trim();
      const duration = simulatedRiskCascadeDuration(row);
      if (period && duration !== null) return `${{period}} (${{duration}} j)`;
      if (period) return period;
      return duration !== null ? `${{duration}} j` : "n/a";
    }}

    function simulatedRiskCascadeRowsForNode(nodeId) {{
      const id = String(nodeId || "");
      if (!id) return [];
      const containsNode = (values) => Array.isArray(values) && values.map(value => String(value || "")).includes(id);
      return simulatedRiskCascadeRows()
        .filter(row =>
          String(row.supplier_id || "") === id ||
          containsNode(row.route_node_ids) ||
          containsNode(row.affected_factory_nodes) ||
          containsNode(row.affected_customer_nodes)
        )
        .sort((a, b) => Number(b.impact_score || 0) - Number(a.impact_score || 0));
    }}

    function simulatedRiskCascadeDiagramHtml(rows, title = "Cascades dynamiques fournisseur") {{
      const selected = (Array.isArray(rows) ? rows : []).slice(0, 4);
      if (!selected.length) return "";
      const width = 1480;
      const rowHeight = 158;
      const top = 34;
      const boxW = 326;
      const boxH = 124;
      const xs = [20, 390, 760, 1130];
      const height = top + rowHeight * selected.length + 16;
      const textBlock = (x, y, titleText, lines) => {{
        const safeTitle = escapeHtmlText(simulatedRiskCascadeShortText(titleText, 46));
        const lineHtml = (lines || []).slice(0, 6).map((line, idx) => {{
          const klass = idx === 0 ? "cascadeText" : "cascadeMuted";
          return `<text class="${{klass}}" x="${{x + 12}}" y="${{y + 34 + idx * 14}}">${{escapeHtmlText(simulatedRiskCascadeShortText(line, 58))}}</text>`;
        }}).join("");
        return `<text class="cascadeTitle" x="${{x + 12}}" y="${{y + 20}}">${{safeTitle}}</text>${{lineHtml}}`;
      }};
      const svg = [
        `<div class="riskScenarioSection">${{escapeHtmlText(title)}}</div>`,
        '<div class="riskCascadeDiagram">',
        `<svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="${{escapeHtmlText(title)}}">`,
        '<defs><marker id="riskCascadeArrowNode" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#64748b"/></marker></defs>',
        '<text class="cascadeMuted" x="20" y="18">Cause supply</text>',
        '<text class="cascadeMuted" x="390" y="18">Effet local applique</text>',
        '<text class="cascadeMuted" x="760" y="18">Propagation aval observee</text>',
        '<text class="cascadeMuted" x="1130" y="18">Impact / absorption</text>',
      ];
      selected.forEach((row, idx) => {{
        const y = top + idx * rowHeight;
        const effectColor = row.impact_color || row.color || simulatedRiskCascadeStageColor(row.stage);
        const family = row.risk_family || (Array.isArray(row.risk_families) ? row.risk_families[0] : "") || "signal";
        const familyLabel = SIMULATED_RISK_FAMILY_LABELS[family] || family;
        const factories = Array.isArray(row.affected_factory_nodes) ? row.affected_factory_nodes : [];
        const customers = Array.isArray(row.affected_customer_nodes) ? row.affected_customer_nodes : [];
        const outputs = Array.isArray(row.impacted_output_items) ? row.impacted_output_items : [];
        const factoryLabels = Array.isArray(row.affected_factory_labels) && row.affected_factory_labels.length
          ? row.affected_factory_labels
          : factories.map(simulatedRiskCascadeNodeLabel);
        const customerLabels = Array.isArray(row.affected_customer_labels) && row.affected_customer_labels.length
          ? row.affected_customer_labels
          : customers.map(simulatedRiskCascadeNodeLabel);
        const outputLabels = Array.isArray(row.impacted_output_item_labels) && row.impacted_output_item_labels.length
          ? row.impacted_output_item_labels
          : outputs.map(simulatedRiskCascadeItemLabel);
        const supplierLabel = row.supplier_label || simulatedRiskCascadeNodeLabel(row.supplier_id);
        const itemLabel = row.item_label || simulatedRiskCascadeItemLabel(row.item_id);
        const edgeLabels = Array.isArray(row.impacted_edge_labels) && row.impacted_edge_labels.length
          ? row.impacted_edge_labels.map(simulatedRiskCascadeEdgeLabel)
          : (Array.isArray(row.route_edge_labels) && row.route_edge_labels.length
            ? row.route_edge_labels
            : (Array.isArray(row.highlight_edge_ids) ? row.highlight_edge_ids.map(simulatedRiskCascadeEdgeLabel) : []));
        const localLines = simulatedRiskCascadeLocalLines(row);
        const routeLines = simulatedRiskCascadePropagationLines(row, itemLabel, outputLabels, factoryLabels, customerLabels, edgeLabels);
        const impactLines = simulatedRiskCascadeImpactLines(row);
        const midY = y + boxH / 2;
        svg.push(`
          <rect class="cascadeBox trigger" x="${{xs[0]}}" y="${{y}}" width="${{boxW}}" height="${{boxH}}" rx="7"/>
          ${{textBlock(xs[0], y, `J${{row.root_day ?? row.start_day ?? "n/a"}} - ${{familyLabel}}`, [
            supplierLabel,
            `Article: ${{itemLabel}}`,
            `Signal: ${{row.trigger || row.primary_trigger || "n/a"}}`,
            simulatedRiskCascadeTriggerDetail(row),
            `Declenche: J${{row.root_day ?? row.start_day ?? "n/a"}}`,
          ])}}
          <line class="cascadeArrow" marker-end="url(#riskCascadeArrowNode)" x1="${{xs[0] + boxW + 10}}" y1="${{midY}}" x2="${{xs[1] - 12}}" y2="${{midY}}"/>
          <rect class="cascadeBox local" x="${{xs[1]}}" y="${{y}}" width="${{boxW}}" height="${{boxH}}" rx="7"/>
          ${{textBlock(xs[1], y, "Effet local", localLines)}}
          <line class="cascadeArrow" marker-end="url(#riskCascadeArrowNode)" x1="${{xs[1] + boxW + 10}}" y1="${{midY}}" x2="${{xs[2] - 12}}" y2="${{midY}}"/>
          <rect class="cascadeBox route" x="${{xs[2]}}" y="${{y}}" width="${{boxW}}" height="${{boxH}}" rx="7"/>
          ${{textBlock(xs[2], y, "Propagation aval", routeLines)}}
          <line class="cascadeArrow" marker-end="url(#riskCascadeArrowNode)" x1="${{xs[2] + boxW + 10}}" y1="${{midY}}" x2="${{xs[3] - 12}}" y2="${{midY}}"/>
          <rect class="cascadeBox effect" style="stroke:${{escapeHtmlText(effectColor)}}" x="${{xs[3]}}" y="${{y}}" width="${{boxW}}" height="${{boxH}}" rx="7"/>
          ${{textBlock(xs[3], y, simulatedRiskCascadeStageLabel(row), impactLines)}}
        `);
      }});
      svg.push("</svg>", "</div>");
      return svg.join("");
    }}

    function simulatedRiskCascadeTimelineHtml(row) {{
      const steps = Array.isArray(row && row.timeline_steps) ? row.timeline_steps : [];
      if (!steps.length) return '<div class="panelEmptyState">Chronologie non disponible.</div>';
      return `
        <div class="riskCascadeTimeline">
          ${{steps.map(step => `
            <div class="riskCascadeTimelineStep">
              <div class="riskCascadeTimelineDay">J${{escapeHtmlText(String(step.day ?? "n/a"))}}</div>
              <div class="riskCascadeTimelineLabel">${{escapeHtmlText(step.label || step.step || "Etape")}}</div>
              <div class="riskCascadeTimelineText">${{escapeHtmlText(step.detail || "")}}</div>
            </div>
          `).join("")}}
        </div>
      `;
    }}

    function simulatedRiskCascadeDetailHtml(row) {{
      if (!row) return '<div class="panelEmptyState">Selectionner une cascade pour lire la cause, la propagation et l action recommandee.</div>';
      const action = row.action || {{}};
      const families = simulatedRiskCascadeFamilies(row).map(family => SIMULATED_RISK_FAMILY_LABELS[family] || family).join(", ") || "n/a";
      const nodeCount = simulatedRiskCascadeNodeIds(row).length;
      const edgeCount = simulatedRiskCascadeEdgeIds(row).length;
      const color = simulatedRiskCascadeStageColor(row.stage);
      const supplierLabel = row.supplier_label || simulatedRiskCascadeNodeLabel(row.supplier_id);
      const itemLabel = row.item_label || simulatedRiskCascadeItemLabel(row.item_id);
      const factoryLabels = Array.isArray(row.affected_factory_labels) && row.affected_factory_labels.length
        ? row.affected_factory_labels
        : (Array.isArray(row.affected_factory_nodes) ? row.affected_factory_nodes.map(simulatedRiskCascadeNodeLabel) : []);
      const customerLabels = Array.isArray(row.affected_customer_labels) && row.affected_customer_labels.length
        ? row.affected_customer_labels
        : (Array.isArray(row.affected_customer_nodes) ? row.affected_customer_nodes.map(simulatedRiskCascadeNodeLabel) : []);
      const outputLabels = Array.isArray(row.impacted_output_item_labels) && row.impacted_output_item_labels.length
        ? row.impacted_output_item_labels
        : (Array.isArray(row.impacted_output_items) ? row.impacted_output_items.map(simulatedRiskCascadeItemLabel) : []);
      const edgeLabels = Array.isArray(row.impacted_edge_labels) && row.impacted_edge_labels.length
        ? row.impacted_edge_labels.map(simulatedRiskCascadeEdgeLabel)
        : (Array.isArray(row.route_edge_labels) && row.route_edge_labels.length
          ? row.route_edge_labels
          : simulatedRiskCascadeEdgeIds(row).map(simulatedRiskCascadeEdgeLabel));
      const localApplication = row.local_application || {{}};
      const duration = simulatedRiskCascadeDuration(row);
      const periodText = simulatedRiskCascadePeriodText(row);
      const contextItems = [
        ["Origine", supplierLabel],
        ["Article declencheur", itemLabel],
        ["Periode / duree", duration !== null ? `${{periodText}}` : periodText],
        ["Occurrences consolidees", row.occurrence_count ? `${{row.occurrence_count}} occurrence(s), pire periode ${{row.worst_period || row.period || "n/a"}}` : "n/a"],
        ["Signal declencheur", simulatedRiskCascadeTriggerDetail(row)],
        ["Effet configure", row.configured_effect || row.local_effect || "n/a"],
        ["Facteurs appliques", simulatedRiskCascadeListText(localApplication.factor_labels || [], 4)],
        ["Route locale", simulatedRiskCascadeListText(localApplication.route_labels || [], 2)],
        ["Site(s) impactes", simulatedRiskCascadeListText(factoryLabels, 4)],
        ["PF/PFI touche(s)", simulatedRiskCascadeListText(outputLabels, 4)],
        ["Client(s) touches", simulatedRiskCascadeListText(customerLabels, 3)],
        ["Flux concernes", simulatedRiskCascadeListText(edgeLabels, 3)],
      ];
      const contextHtml = contextItems.map(([label, value]) => `
        <div class="riskCascadeContextItem">
          <div class="riskCascadeContextLabel">${{escapeHtmlText(label)}}</div>
          <div class="riskCascadeContextValue">${{escapeHtmlText(value || "n/a")}}</div>
        </div>
      `).join("");
      const impactedNodes = Array.isArray(row.impacted_nodes) ? row.impacted_nodes : [];
      const impactedEdges = Array.isArray(row.impacted_edges) ? row.impacted_edges : [];
      const nodeRows = impactedNodes.length ? impactedNodes.map(node => `
        <tr>
          <td>${{escapeHtmlText(simulatedRiskCascadeRoleLabel(node.role))}}</td>
          <td>${{escapeHtmlText(node.label || simulatedRiskCascadeNodeLabel(node.node_id))}}</td>
          <td class="num">J${{escapeHtmlText(String(node.first_day ?? "n/a"))}}</td>
        </tr>
      `).join("") : '<tr><td colspan="3">Aucun noeud detaille.</td></tr>';
      const edgeRows = impactedEdges.length ? impactedEdges.map(edge => `
        <tr>
          <td>${{escapeHtmlText(simulatedRiskCascadeRoleLabel(edge.role))}}</td>
          <td>${{escapeHtmlText(simulatedRiskCascadeEdgeLabel(edge.edge_id))}}</td>
          <td class="num">J${{escapeHtmlText(String(edge.first_day ?? "n/a"))}}</td>
        </tr>
      `).join("") : '<tr><td colspan="3">Aucun flux detaille.</td></tr>';
      return `
        <div class="riskCascadeDetail">
          <div class="riskScenarioCards">
            <div class="riskScenarioCard" style="border-left-color:${{escapeHtmlText(color)}}">
              <div class="riskScenarioCardTitle">Cause supply avec impact</div>
              <div class="riskScenarioCardText"><strong>${{escapeHtmlText(row.business_path_label || row.root_cause_label || row.label || "n/a")}}</strong><br>${{escapeHtmlText(families)}} ; ${{escapeHtmlText(periodText)}}</div>
            </div>
            <div class="riskScenarioCard" style="border-left-color:#0f766e">
              <div class="riskScenarioCardTitle">Propagation aval</div>
              <div class="riskScenarioCardText"><strong>${{escapeHtmlText(simulatedRiskCascadeStageLabel(row))}}</strong><br>${{escapeHtmlText(row.reading || "n/a")}}</div>
            </div>
            <div class="riskScenarioCard" style="border-left-color:#2563eb">
              <div class="riskScenarioCardTitle">Action supply recommandee</div>
              <div class="riskScenarioCardText"><strong>${{escapeHtmlText(action.label || "n/a")}}</strong><br>${{escapeHtmlText(action.rationale || "")}}</div>
            </div>
            <div class="riskScenarioCard" style="border-left-color:#64748b">
              <div class="riskScenarioCardTitle">Carte</div>
              <div class="riskScenarioCardText"><strong>${{nodeCount}} noeud(s), ${{edgeCount}} flux</strong><br>selection = surlignage carte si donnees disponibles</div>
            </div>
          </div>
          <div class="riskScenarioSection">Contexte metier</div>
          <div class="riskCascadeContextGrid">${{contextHtml}}</div>
          <div class="riskScenarioSection">Chronologie</div>
          ${{simulatedRiskCascadeTimelineHtml(row)}}
          ${{simulatedRiskCascadeDiagramHtml([row], "Lecture de la cascade selectionnee")}}
          <details class="riskDetailsBlock" open>
            <summary>Noeuds et flux concernes</summary>
            <div class="riskScenarioMuted">Lecture: ces lignes expliquent ou la cascade est localisee et quels arcs de la carte peuvent etre surlignes.</div>
            <table class="materialTable">
              <thead><tr><th>Role</th><th>Noeud</th><th class="num">Premier jour</th></tr></thead>
              <tbody>${{nodeRows}}</tbody>
            </table>
            <table class="materialTable">
              <thead><tr><th>Role</th><th>Flux</th><th class="num">Premier jour</th></tr></thead>
              <tbody>${{edgeRows}}</tbody>
            </table>
          </details>
        </div>
      `;
    }}

    function simulatedRiskCascadeListItemHtml(row, idx) {{
      const key = simulatedRiskCascadeKeyForRow(row);
      const active = key && key === selectedSimulatedRiskCascadeKey;
      const color = simulatedRiskCascadeStageColor(row.stage);
      const supplierLabel = row.supplier_label || simulatedRiskCascadeNodeLabel(row.supplier_id);
      const itemLabel = row.item_label || simulatedRiskCascadeItemLabel(row.item_id);
      const factoryLabels = Array.isArray(row.affected_factory_labels) && row.affected_factory_labels.length
        ? row.affected_factory_labels
        : (Array.isArray(row.affected_factory_nodes) ? row.affected_factory_nodes.map(simulatedRiskCascadeNodeLabel) : []);
      const outputLabels = Array.isArray(row.impacted_output_item_labels) && row.impacted_output_item_labels.length
        ? row.impacted_output_item_labels
        : (Array.isArray(row.impacted_output_items) ? row.impacted_output_items.map(simulatedRiskCascadeItemLabel) : []);
      const edgeCount = simulatedRiskCascadeEdgeIds(row).length;
      const duration = simulatedRiskCascadeDuration(row);
      const title = `${{supplierLabel}} / article ${{itemLabel}}`;
      const metric = row.stage === "service_client"
        ? `backlog max ${{fmtPanelQty(Number(row.customer_backlog_max_qty) || 0, 0)}}`
        : (row.stage === "production"
          ? `${{row.production_delay_count || 0}} report(s), ${{fmtPanelQty(Number(row.production_shortfall_qty) || 0, 0)}}`
          : (row.stage === "cost"
            ? `cout add. ${{fmtPanelQty(Number(row.cost_impact_qty) || 0, 0)}}`
            : (row.reading || "effet observe")));
      const routeText = simulatedRiskCascadeRouteText(row);
      const chips = [
        simulatedRiskCascadeStageLabel(row),
        duration !== null ? `${{duration}} j` : "",
        row.occurrence_count ? `${{row.occurrence_count}} occurrence(s)` : "",
        factoryLabels.length ? `Site: ${{simulatedRiskCascadeListText(factoryLabels, 1)}}` : "",
        outputLabels.length ? `Produit: ${{simulatedRiskCascadeListText(outputLabels, 2)}}` : "",
        edgeCount ? `${{edgeCount}} flux` : "",
      ].filter(Boolean).map(value => `<span class="riskCascadeChip">${{escapeHtmlText(value)}}</span>`).join("");
      return `
        <button class="riskCascadeListItem${{active ? " active" : ""}}" type="button" data-cascade-key="${{escapeHtmlText(key)}}" style="border-left-color:${{escapeHtmlText(color)}}">
          <div class="riskCascadeListTitle">${{escapeHtmlText(simulatedRiskCascadeShortText(title, 90))}}</div>
          <div class="riskCascadeListText">${{escapeHtmlText(routeText)}} - ${{escapeHtmlText(simulatedRiskCascadePeriodText(row))}}</div>
          <div class="riskCascadeListMeta">${{escapeHtmlText(metric)}}</div>
          <div class="riskCascadeChips">${{chips}}</div>
        </button>
      `;
    }}

    function renderSimulatedRiskCascadeExplorer(root) {{
      const container = root || document.getElementById("simulatedRiskGlobalContent");
      if (!container) return;
      const previous = container.querySelector("#simRiskCascadeExplorerHost");
      if (previous) previous.remove();
      const rows = filteredSimulatedRiskCascadeRows();
      const selected = selectedSimulatedRiskCascade();
      const detailRow = selected || rows[0] || null;
      const listHtml = diversifiedSimulatedRiskCascadeRows(rows, 80).map(simulatedRiskCascadeListItemHtml).join("");
      const html = `
        <div id="simRiskCascadeExplorerHost" class="riskCascadeExplorer">
          <div class="riskScenarioSection">Explorateur de cascades dynamiques fournisseur</div>
          <div class="riskScenarioMuted">Lecture: selectionner une cascade pour voir la cause supply, l'effet local, la propagation aval, l'action recommandee et le surlignage carte.</div>
          <div class="riskCascadeExplorerControls">
            <select id="simRiskCascadeExplorerStageFilter">
              <option value="all">Tous impacts</option>
              <option value="service_client">Client atteint</option>
              <option value="production">Production reportee</option>
              <option value="cost">Surcout</option>
              <option value="local_absorbed">Absorbe localement</option>
              <option value="configured_only">Sans effet</option>
            </select>
            <select id="simRiskCascadeExplorerFamilyFilter">
              <option value="all">Toutes familles</option>
              <option value="stock">Stock</option>
              <option value="lead">Delai</option>
              <option value="upstream">Appro amont</option>
              <option value="quality">Qualite</option>
              <option value="capacity">Capacite</option>
              <option value="availability">Disponibilite</option>
              <option value="cost">Cout</option>
            </select>
            <input id="simRiskCascadeExplorerTextFilter" type="search" placeholder="Filtrer fournisseur, article, site..." value="${{escapeHtmlText(simulatedRiskCascadeTextFilter)}}"/>
            <button id="simRiskCascadeExplorerClearBtn" class="tableBtn" type="button">Effacer selection</button>
          </div>
          <div class="riskCascadeExplorerGrid">
            <div class="riskCascadeList">${{listHtml || '<div class="panelEmptyState">Aucune cascade pour ces filtres.</div>'}}</div>
            ${{simulatedRiskCascadeDetailHtml(detailRow)}}
          </div>
        </div>
      `;
      container.insertAdjacentHTML("afterbegin", html);
      const stageFilter = document.getElementById("simRiskCascadeExplorerStageFilter");
      const familyFilter = document.getElementById("simRiskCascadeExplorerFamilyFilter");
      const textFilter = document.getElementById("simRiskCascadeExplorerTextFilter");
      if (stageFilter) {{
        stageFilter.value = simulatedRiskCascadeStageFilter;
        stageFilter.addEventListener("change", (ev) => {{
          simulatedRiskCascadeStageFilter = String(ev.target.value || "all");
          selectedSimulatedRiskCascadeKey = "";
          updateSimulatedRiskControls();
          renderSimulatedRiskGlobalDiagnostic();
          draw();
        }});
      }}
      if (familyFilter) {{
        familyFilter.value = simulatedRiskCascadeFamilyFilter;
        familyFilter.addEventListener("change", (ev) => {{
          simulatedRiskCascadeFamilyFilter = String(ev.target.value || "all");
          selectedSimulatedRiskCascadeKey = "";
          updateSimulatedRiskControls();
          renderSimulatedRiskGlobalDiagnostic();
          draw();
        }});
      }}
      if (textFilter) {{
        textFilter.addEventListener("input", (ev) => {{
          simulatedRiskCascadeTextFilter = String(ev.target.value || "");
          selectedSimulatedRiskCascadeKey = "";
          updateSimulatedRiskControls();
          renderSimulatedRiskGlobalDiagnostic();
          draw();
        }});
      }}
      const clearBtn = document.getElementById("simRiskCascadeExplorerClearBtn");
      if (clearBtn) clearBtn.addEventListener("click", () => setSelectedSimulatedRiskCascade(""));
      container.querySelectorAll(".riskCascadeListItem[data-cascade-key]").forEach(btn => {{
        btn.addEventListener("click", () => setSelectedSimulatedRiskCascade(btn.getAttribute("data-cascade-key") || ""));
      }});
    }}

    function simulatedRiskNodeImpactAsset(nodeId) {{
      const impact = simulatedRiskNodeImpact(nodeId);
      if (!impact) return null;
      const stageColor = impact.color || "#64748b";
      const roleLabels = {{
        origin_supplier: "fournisseur origine du probleme",
        affected_factory: "site industriel impacte",
        affected_customer: "client impacte",
      }};
      const roleLabel = roleLabels[impact.role] || impact.role || "noeud impacte";
      const rows = [
        ["Impact observe", impact.stage_label || "n/a"],
        ["Role dans la carte", roleLabel],
        ["Origine diagnostiquee", `${{impact.supplier_label || impact.supplier_id || "n/a"}} / ${{impact.item_label || impact.item_id || "n/a"}}`],
        ["Declencheur principal", impact.primary_trigger || "n/a"],
        ["Periode", impact.period || "n/a"],
        ["Causes supply actives", `${{impact.effective_root_count || 0}} / ${{impact.root_count || 0}}`],
        ["Volume replanifie", String(impact.production_delay_count || 0)],
        ["Volume reporte", fmtPanelQty(Number(impact.production_shortfall_qty) || 0, 0)],
        ["Backlog client max", fmtPanelQty(Number(impact.customer_backlog_max_qty) || 0, 0)],
      ].map(([label, value]) => `
        <tr>
          <td>${{escapeHtmlText(label)}}</td>
          <td>${{escapeHtmlText(String(value || "n/a"))}}</td>
        </tr>
      `).join("");
      const cascadeHtml = simulatedRiskCascadeDiagramHtml(
        simulatedRiskCascadeRowsForNode(nodeId),
        "Cascades passant par ce noeud"
      );
      return {{
        html: `
          <div class="factoryHtmlPanelContent sensitivityHtmlPanelContent">
            <div class="orderLedgerTextHeader">${{escapeHtmlText(nodeId)}} - impact reel du scenario</div>
            <div class="orderLedgerStatus">Lecture metier: cette fiche vient du diagnostic global des cascades. Une cause supply active est un couple fournisseur/article ou un flux qui a cree un effet observable: report production, backlog client, surcout ou retard transport.</div>
            <div class="riskScenarioCards">
              <div class="riskScenarioCard" style="border-left-color:${{escapeHtmlText(stageColor)}}">
                <div class="riskScenarioCardTitle">Impact dominant</div>
                <div class="riskScenarioCardText"><strong>${{escapeHtmlText(impact.stage_label || "n/a")}}</strong><br>${{escapeHtmlText(roleLabel)}}</div>
              </div>
              <div class="riskScenarioCard" style="border-left-color:#475569">
                <div class="riskScenarioCardTitle">Declencheur principal</div>
                <div class="riskScenarioCardText"><strong>${{escapeHtmlText(impact.primary_trigger || "n/a")}}</strong><br>${{escapeHtmlText(impact.period || "n/a")}}</div>
              </div>
            </div>
            ${{cascadeHtml}}
            <div class="riskScenarioSection">Impact observe</div>
            <div class="kpiFormulaTableWrap"><table class="kpiFormulaTable"><tbody>${{rows}}</tbody></table></div>
          </div>
        `
      }};
    }}

    function simulatedRiskMetaAsset(meta, nodeId) {{
      if (!meta) return null;
      const lines = Array.isArray(meta.summary_lines) ? meta.summary_lines : [];
      const rows = lines.map(entry => `
        <tr>
          <td>${{escapeHtmlText(entry.label || "")}}</td>
          <td>${{escapeHtmlText(entry.value || "")}}</td>
        </tr>
      `).join("");
      const families = meta.applied_family_counts || meta.configured_family_counts || {{}};
      const familyRows = Object.entries(families).map(([family, count]) => `
        <tr>
          <td>${{escapeHtmlText(SIMULATED_RISK_FAMILY_LABELS[family] || family)}}</td>
          <td class="num">${{escapeHtmlText(String(count || 0))}}</td>
        </tr>
      `).join("");
      const examples = Array.isArray(meta.event_examples) ? meta.event_examples.join(", ") : "";
      return {{
        html: `
          <div class="factoryHtmlPanelContent sensitivityHtmlPanelContent">
            <div class="orderLedgerTextHeader">${{escapeHtmlText(nodeId)}} - risques state-dependent</div>
            <div class="orderLedgerStatus">Lecture metier: evenements de risque qui se sont declenches pendant le run dynamique et qui ont modifie localement stock, capacite, delai, disponibilite ou approvisionnement.</div>
            <div class="riskScenarioCards">
              <div class="riskScenarioCard" style="border-left-color:${{escapeHtmlText(meta.driver_color || "#64748b")}}">
                <div class="riskScenarioCardTitle">Statut</div>
                <div class="riskScenarioCardText"><strong>${{escapeHtmlText(meta.status_label || "n/a")}}</strong><br>${{escapeHtmlText(meta.driver_label || "n/a")}} ; periode ${{escapeHtmlText(meta.period || "n/a")}}</div>
              </div>
              <div class="riskScenarioCard" style="border-left-color:#0f766e">
                <div class="riskScenarioCardTitle">Application</div>
                <div class="riskScenarioCardText"><strong>${{escapeHtmlText(String(meta.applied_event_count || 0))}} / ${{escapeHtmlText(String(meta.configured_event_count || 0))}}</strong><br>evenements appliques / configures</div>
              </div>
            </div>
            <div class="riskScenarioSection">Synthese locale</div>
            <div class="kpiFormulaTableWrap"><table class="kpiFormulaTable"><tbody>${{rows || '<tr><td colspan="2">Aucun detail disponible.</td></tr>'}}</tbody></table></div>
            <div class="riskScenarioSection">Familles touchees</div>
            <div class="kpiFormulaTableWrap"><table class="kpiFormulaTable"><tbody>${{familyRows || '<tr><td colspan="2">Aucune famille appliquee.</td></tr>'}}</tbody></table></div>
            <div class="orderLedgerStatus">Exemples: ${{escapeHtmlText(examples || "aucun")}}</div>
          </div>
        `
      }};
    }}

    function nodeRiskMeta(nodeId) {{
      return (SUPPLIER_RISK_METRICS.nodes || {{}})[nodeId] || null;
    }}

    function nodeUncertaintyMeta(nodeId, nodeType = "node") {{
      if (nodeType === "edge") return null;
      const monteCarloNode = ((MONTECARLO_UNCERTAINTY.nodes || {{}})[nodeId]) || null;
      return monteCarloNode;
    }}

    function uncertaintyStatusForScore(score) {{
      if (score >= 0.20) return {{ status: "sensitive", status_label: "Impact fort dans Monte Carlo", business_class: "businessAlert" }};
      if (score >= 0.08) return {{ status: "watch", status_label: "Impact a surveiller dans Monte Carlo", business_class: "businessWarn" }};
      return {{ status: "robust", status_label: "Impact faible dans Monte Carlo", business_class: "businessOk" }};
    }}

    function bestUncertaintyDriver(rows) {{
      return rows.reduce((best, row) => {{
        const rowScore = Number(row && row.score) || 0;
        const bestScore = best ? (Number(best.score) || 0) : -1;
        if (rowScore > bestScore) return row;
        if (rowScore === bestScore && (Math.abs(Number(row && row.fill_corr) || 0) > Math.abs(Number(best && best.fill_corr) || 0))) return row;
        return best;
      }}, null);
    }}

    function buildUncertaintyImpact(selected, score, view, title, extra = {{}}) {{
      if (!selected) return null;
      const status = uncertaintyStatusForScore(score);
      const family = selected.family || "";
      return {{
        ...status,
        ...extra,
        source: "montecarlo",
        view,
        mode: family,
        title,
        score,
        color: selected.color || "#64748b",
        dominant_dimension: selected.label || UNCERTAINTY_MODE_LABELS[family] || "n/a",
        driver_family: family,
        driver_factor: selected.factor || "",
        fill_rate_correlation: selected.fill_corr,
        backlog_correlation: selected.backlog_corr,
        cost_correlation: selected.cost_corr,
      }};
    }}

    function selectedUncertaintyImpact(meta) {{
      if (!meta) return null;
      const drivers = (Array.isArray(meta.drivers) ? meta.drivers : [])
        .filter((row) => row && Number.isFinite(Number(row.score)));
      if (!drivers.length) return null;

      if (uncertaintyDisplayMode === "global_impact") {{
        const bestByFamily = {{}};
        drivers.forEach((row) => {{
          const family = row.family || "other";
          const current = bestByFamily[family];
          if (!current || (Number(row.score) || 0) > (Number(current.score) || 0)) {{
            bestByFamily[family] = row;
          }}
        }});
        const familyRows = Object.values(bestByFamily);
        const strongest = bestUncertaintyDriver(familyRows);
        const score = familyRows.reduce((sum, row) => sum + (Number(row.score) || 0), 0) / Math.max(1, familyRows.length);
        return buildUncertaintyImpact(
          strongest,
          score,
          "global_impact",
          "Intensite globale Monte Carlo",
          {{
            component_count: familyRows.length,
            dominant_type_label: UNCERTAINTY_MODE_LABELS[strongest && strongest.family] || (strongest && strongest.family) || "n/a",
          }}
        );
      }}

      if (uncertaintyDisplayMode === "detail_type") {{
        const candidates = drivers.filter((row) => row.family === uncertaintyMode);
        const selected = bestUncertaintyDriver(candidates);
        if (!selected) return null;
        const score = Number(selected.score) || 0;
        return buildUncertaintyImpact(
          selected,
          score,
          "detail_type",
          `Detail Monte Carlo - ${{UNCERTAINTY_MODE_LABELS[uncertaintyMode] || uncertaintyMode}}`
        );
      }}

      const selected = bestUncertaintyDriver(drivers);
      const score = Number(selected && selected.score) || 0;
      const familyLabel = UNCERTAINTY_MODE_LABELS[selected && selected.family] || (selected && selected.family) || "n/a";
      return buildUncertaintyImpact(
        selected,
        score,
        "dominant_type",
        `Type dominant - ${{familyLabel}}`,
        {{ dominant_type_label: familyLabel }}
      );
    }}

    function uncertaintyDriverNodeIds(driver) {{
      if (!driver) return [];
      const ids = [];
      if (Array.isArray(driver.highlight_node_ids)) ids.push(...driver.highlight_node_ids);
      if (driver.node_id) ids.push(driver.node_id);
      const factor = String(driver.factor || "");
      [
        "supplier_stock_node::",
        "supplier_capacity_node::",
        "supplier_lead_node::",
        "supplier_reliability_node::",
        "capacity_node::",
      ].forEach(prefix => {{
        if (factor.startsWith(prefix)) ids.push(factor.slice(prefix.length));
      }});
      return [...new Set(ids.map(value => String(value || "")).filter(Boolean))];
    }}

    function selectedUncertaintyDriverMapNodes() {{
      if (currentPanelMode !== "uncertainty" || !selectedUncertaintyDriver) return [];
      return uncertaintyDriverNodeIds(selectedUncertaintyDriver)
        .map(nodeId => nodeById[nodeId])
        .filter(node => node && Number.isFinite(node.lat) && Number.isFinite(node.lon));
    }}

    function selectedUncertaintyDriverMapEdges() {{
      if (currentPanelMode !== "uncertainty" || !selectedUncertaintyDriver) return [];
      const nodeIds = new Set(uncertaintyDriverNodeIds(selectedUncertaintyDriver));
      if (!nodeIds.size) return [];
      return (DATA.edges || []).filter(edge =>
        nodeIds.has(String(edge.from || "")) || nodeIds.has(String(edge.to || ""))
      );
    }}

    function buildUncertaintyDriverOverlayTraces() {{
      if (currentPanelMode !== "uncertainty" || !selectedUncertaintyDriver) return [];
      const traces = [];
      const color = selectedUncertaintyDriver.line_color || selectedUncertaintyDriver.color || "#0f766e";
      const label = selectedUncertaintyDriver.label || "Driver Monte Carlo";
      selectedUncertaintyDriverMapEdges().forEach(edge => {{
        const src = nodeById[edge.from];
        const dst = nodeById[edge.to];
        if (!src || !dst) return;
        if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) return;
        if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) return;
        traces.push({{
          type: "scattergeo",
          mode: "lines",
          name: "Driver incertitude",
          showlegend: false,
          lon: [src.lon, dst.lon],
          lat: [src.lat, dst.lat],
          line: {{ width: 6, color }},
          opacity: 0.76,
          hovertemplate: `${{escapeHtmlText(label)}}<br>${{edge.from}} -> ${{edge.to}}<extra></extra>`,
        }});
      }});
      const nodes = selectedUncertaintyDriverMapNodes();
      if (nodes.length) {{
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: "Driver incertitude",
          lon: nodes.map(n => n.lon),
          lat: nodes.map(n => n.lat),
          text: nodes.map(n => `${{escapeHtmlText(label)}}<br>${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}`),
          customdata: nodes.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 24,
            color,
            opacity: 0.96,
            symbol: "circle",
            line: {{ width: 3, color: "#0f172a" }},
          }},
        }});
      }}
      return traces;
    }}

    function selectUncertaintyDriver(driver) {{
      if (!driver) return;
      selectedUncertaintyDriver = driver;
      const nodeIds = uncertaintyDriverNodeIds(driver);
      const firstNode = nodeIds.map(nodeId => nodeById[nodeId]).find(Boolean);
      if (driver.family && UNCERTAINTY_MODE_LABELS[driver.family]) {{
        uncertaintyDisplayMode = "detail_type";
        uncertaintyMode = driver.family;
      }}
      currentPanelMode = "uncertainty";
      if (firstNode) {{
        selectedPanelNodeId = firstNode.id;
        selectedPanelNodeType = firstNode.type;
      }}
      applyModeUi();
      draw();
    }}

    function uncertaintyImpactIntensityColor(score) {{
      const value = Math.max(0, Math.min(1, Number(score) || 0));
      if (value >= 0.20) return "#dc2626";
      if (value >= 0.12) return "#f97316";
      if (value >= 0.06) return "#f59e0b";
      if (value > 0) return "#22c55e";
      return "#94a3b8";
    }}

    function summaryLineValue(meta, label) {{
      if (!meta || !Array.isArray(meta.summary_lines)) return null;
      const labels = Array.isArray(label) ? label : [label];
      const row = meta.summary_lines.find((entry) => entry && labels.includes(entry.label));
      return row ? row.value : null;
    }}

    function parsePercentText(value) {{
      const match = String(value ?? "").replace(",", ".").match(/-?\\d+(?:\\.\\d+)?/);
      if (!match) return 0;
      const numeric = Number(match[0]);
      return Number.isFinite(numeric) ? Math.max(0, Math.min(1, numeric / 100)) : 0;
    }}

    function riskPredictionUncertainty(meta) {{
      if (!meta) return 0;
      const risk = parsePercentText(summaryLineValue(meta, ["Score menace fournisseur", "Score menace max", "Risque estime max"]));
      const high = parsePercentText(summaryLineValue(meta, ["Menace haute", "Menace haute max", "Borne haute prudente", "Borne prudente", "Estimation prudente"]));
      return Math.max(0, Math.min(1, high - risk));
    }}

    function riskPredictionUncertaintyColor(meta) {{
      const spread = riskPredictionUncertainty(meta);
      if (spread >= 0.20) return "#7c3aed";
      if (spread >= 0.10) return "#2563eb";
      return "#38bdf8";
    }}

    function nodeMarkerColor(n, style) {{
      if (currentPanelMode === "uncertainty") {{
        const uncertaintyMeta = nodeUncertaintyMeta(n.id, n.type);
        const uncertaintyImpact = selectedUncertaintyImpact(uncertaintyMeta);
        if (uncertaintyImpact && uncertaintyDisplayMode !== "dominant_type") return uncertaintyImpactIntensityColor(uncertaintyImpact.score);
        if (uncertaintyImpact && uncertaintyImpact.color) return uncertaintyImpact.color;
        return "#94a3b8";
      }}
      if (currentPanelMode === "risk") {{
        const riskMeta = nodeRiskMeta(n.id);
        return (riskMeta && riskMeta.zone_color) ? riskMeta.zone_color : style.color;
      }}
      if (currentPanelMode === "simulated_risk") {{
        const impact = simulatedRiskNodeImpact(n.id);
        if (impact && impact.color) return impact.color;
        if (selectedSimulatedRiskCascadeKey) return "#cbd5e1";
        const simulatedMeta = nodeSimulatedRiskMeta(n.id);
        return (simulatedMeta && simulatedMeta.driver_color) ? simulatedMeta.driver_color : "#94a3b8";
      }}
      const meta = currentPanelMode === "sensitivity" ? nodeSensitivityMeta(n.id) : null;
      return (meta && meta.driver_color) ? meta.driver_color : style.color;
    }}

    function nodeMarkerSize(n) {{
      if (currentPanelMode === "uncertainty") {{
        const uncertaintyMeta = nodeUncertaintyMeta(n.id, n.type);
        const uncertaintyImpact = selectedUncertaintyImpact(uncertaintyMeta);
        const score = uncertaintyImpact ? (Number(uncertaintyImpact.score) || 0) : 0;
        return Math.max(8, Math.min(16, 9 + score * 7));
      }}
      if (currentPanelMode === "risk") {{
        const riskMeta = nodeRiskMeta(n.id);
        if (!riskMeta) return 8;
        const score = Number(riskMeta.action_priority_score) || 0;
        const rank = Number(riskMeta.zone_rank) || 0;
        return Math.max(9, Math.min(16, 9 + rank * 1.6 + score * 5));
      }}
      if (currentPanelMode === "simulated_risk") {{
        const impact = simulatedRiskNodeImpact(n.id);
        if (impact) {{
          const score = Number(impact.score) || 0;
          const roots = Number(impact.effective_root_count) || 0;
          return Math.max(10, Math.min(20, 10 + score * 7 + Math.min(roots, 4)));
        }}
        if (selectedSimulatedRiskCascadeKey) return 7;
        const simulatedMeta = nodeSimulatedRiskMeta(n.id);
        if (!simulatedMeta) return 8;
        const score = Number(simulatedMeta.score) || 0;
        const applied = Number(simulatedMeta.applied_event_count) || 0;
        return Math.max(9, Math.min(17, 9 + score * 6 + Math.min(applied, 4)));
      }}
      const meta = currentPanelMode === "sensitivity" ? nodeSensitivityMeta(n.id) : null;
      if (!meta) return 9;
      if (meta.status === "sensitive") return 13;
      if (meta.status === "watch") return 11;
      if (meta.status === "not_local") return 8;
      return 9;
    }}

    function nodeMarkerOpacity(n) {{
      if (currentPanelMode === "uncertainty") {{
        const meta = nodeUncertaintyMeta(n.id, n.type);
        return selectedUncertaintyImpact(meta) ? 0.96 : 0.32;
      }}
      if (currentPanelMode === "risk") {{
        return nodeRiskMeta(n.id) ? 0.96 : 0.48;
      }}
      if (currentPanelMode === "simulated_risk") {{
        const impact = simulatedRiskNodeImpact(n.id);
        if (impact) return 0.98;
        if (selectedSimulatedRiskCascadeKey) return 0.16;
        const simulatedMeta = nodeSimulatedRiskMeta(n.id);
        if (!simulatedMeta) return 0.34;
        if (simulatedMeta.source === "supplier_risk_campaign") return 0.96;
        return simulatedMeta.status === "applied" ? 0.96 : 0.58;
      }}
      const meta = currentPanelMode === "sensitivity" ? nodeSensitivityMeta(n.id) : null;
      if (!meta) return 0.92;
      if (meta.status === "not_local") return 0.62;
      return 0.95;
    }}

    function nodeSensitivityText(n) {{
      const meta = nodeSensitivityMeta(n.id);
      if (!meta || currentPanelMode !== "sensitivity") return "";
      return [
        `Statut sensibilite: ${{meta.status_label || "n/a"}}`,
        `Parametre teste prioritaire: ${{meta.driver_family_label || "n/a"}} - ${{meta.driver_label || "n/a"}}`,
        `Premier niveau qui degrade les KPI: ${{meta.first_unacceptable || "n/a"}}`,
        `Impact KPI: ${{meta.reason || "n/a"}}`,
      ].join("<br>");
    }}

    function nodeRiskText(n) {{
      const meta = nodeRiskMeta(n.id);
      if (!meta || currentPanelMode !== "risk") return "";
      const lines = Array.isArray(meta.summary_lines) ? meta.summary_lines : [];
      const selected = lines.filter(entry => ["Niveau de criticite", "Score criticite fournisseur", "Criticite fournisseur", "Action prudente", "Marge incertitude scoring", "Marge incertitude", "Niveau de risque"].includes(entry.label));
      if (!selected.length) return "";
      return selected.map(entry => `${{entry.label}}: ${{entry.value || "n/a"}}`).join("<br>");
    }}

    function nodeSimulatedRiskText(n) {{
      const impact = simulatedRiskNodeImpact(n.id);
      if (impact && currentPanelMode === "simulated_risk") {{
        const impactLines = simulatedRiskImpactLines(impact);
        if (impactLines.length) return impactLines.join("<br>");
      }}
      if (currentPanelMode === "simulated_risk" && selectedSimulatedRiskCascadeKey) {{
        return "Hors cascade selectionnee";
      }}
      const meta = nodeSimulatedRiskMeta(n.id);
      if (!meta || currentPanelMode !== "simulated_risk") return "";
      if (meta.source === "supplier_risk_campaign") {{
        return [
          `Stress test fournisseur: ${{meta.status_label || "n/a"}}`,
          `Pire famille testee: ${{meta.driver_label || "n/a"}}`,
          `Cas testes: ${{meta.configured_event_count || meta.tested_case_count || 0}}`,
          `Impact metier: ${{meta.impact_metier_delta || meta.impact_metier_lecture || "n/a"}}`,
          `Lecture: resultats contrefactuels, pas des evenements observes dans le run`,
        ].join("<br>");
      }}
      return [
        `Statut risques simules: ${{meta.status_label || "n/a"}}`,
        `Type principal: ${{meta.driver_label || "n/a"}}`,
        `Evenements appliques: ${{meta.applied_event_count || 0}} / configures: ${{meta.configured_event_count || 0}}`,
        `Periode: ${{meta.period || "n/a"}}`,
        `Exemples: ${{(meta.event_examples || []).join(", ") || "aucun"}}`,
      ].join("<br>");
    }}

    function nodeUncertaintyText(n) {{
      if (currentPanelMode !== "uncertainty") return "";
      const general = nodeUncertaintyMeta(n.id, n.type);
      const lines = [];
      if (general) {{
        const impact = selectedUncertaintyImpact(general);
        if (general.source === "montecarlo" && impact) {{
          lines.push(`Monte Carlo: ${{impact.status_label || "n/a"}}`);
          lines.push(`Vue carte: ${{UNCERTAINTY_VIEW_LABELS[uncertaintyDisplayMode] || uncertaintyDisplayMode}}`);
          if (uncertaintyDisplayMode === "detail_type") {{
            lines.push(`Type detail: ${{UNCERTAINTY_MODE_LABELS[uncertaintyMode] || uncertaintyMode}}`);
          }}
          lines.push(`${{impact.title || "Impact"}}: ${{fmtPanelQty((Number(impact.score) || 0) * 100, 1)}}%`);
          lines.push(`Driver principal: ${{impact.dominant_dimension || "n/a"}}`);
          if (Number.isFinite(Number(impact.fill_rate_correlation))) {{
            lines.push(`Corr. disponibilite: ${{Number(impact.fill_rate_correlation).toFixed(2)}}`);
          }}
        }} else if (general.source === "montecarlo") {{
          lines.push(`Monte Carlo: pas d'impact local pour cette vue`);
          lines.push(`Vue carte: ${{UNCERTAINTY_VIEW_LABELS[uncertaintyDisplayMode] || uncertaintyDisplayMode}}`);
          if (uncertaintyDisplayMode === "detail_type") {{
            lines.push(`Type detail: ${{UNCERTAINTY_MODE_LABELS[uncertaintyMode] || uncertaintyMode}}`);
          }}
        }} else {{
          lines.push(`Confiance lecture: ${{general.status_label || "n/a"}}`);
          lines.push(`Score dispersion: ${{fmtPanelQty((Number(general.score) || 0) * 100, 1)}}%`);
          lines.push(`Point le moins lisible: ${{general.dominant_dimension || "n/a"}}`);
        }}
      }}
      return lines.join("<br>");
    }}

    function initFilters() {{
      const container = document.getElementById("typeFilters");
      container.innerHTML = "<strong style='font-size:12px;'>Types:</strong>";
      (DATA.node_types || []).forEach((t, idx) => {{
        const style = styleForType(t, idx);
        const lbl = document.createElement("label");
        lbl.innerHTML = `<input class="typeChk" type="checkbox" value="${{t}}" checked> ${{style.name}}`;
        container.appendChild(lbl);
      }});
    }}

    function selectedTypes() {{
      return new Set(Array.from(document.querySelectorAll(".typeChk"))
        .filter(x => x.checked)
        .map(x => x.value));
    }}

    function nodeText(n) {{
      const loc = n.location_ID ? n.location_ID : "n/a";
      const country = n.country ? n.country : "n/a";
      const customerMetrics = CUSTOMER_CURRENT_METRICS[n.id] || null;
      const extra = [];
      if (customerMetrics && Array.isArray(customerMetrics.summary_lines)) {{
        customerMetrics.summary_lines.slice(0, 3).forEach((entry) => {{
          extra.push(`${{entry.label}}: ${{entry.value}}`);
        }});
      }}
      const extraHtml = extra.length ? `<br>${{extra.join("<br>")}}` : "";
      const sensitivityHtml = nodeSensitivityText(n);
      const simulatedRiskHtml = nodeSimulatedRiskText(n);
      const riskHtml = nodeRiskText(n);
      const uncertaintyHtml = nodeUncertaintyText(n);
      return `${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}<br>Country: ${{country}}<br>Location: ${{loc}}${{extraHtml}}${{sensitivityHtml ? `<br>${{sensitivityHtml}}` : ""}}${{simulatedRiskHtml ? `<br>${{simulatedRiskHtml}}` : ""}}${{riskHtml ? `<br>${{riskHtml}}` : ""}}${{uncertaintyHtml ? `<br>${{uncertaintyHtml}}` : ""}}`;
    }}

    function edgeLeadColor(e) {{
      const m = e.edge_metrics || {{}};
      const lead = Number.isFinite(m.avg_lead_days) ? m.avg_lead_days : (Number.isFinite(e.planned_lead_days) ? e.planned_lead_days : 1);
      if (lead <= 14) return "#2ca02c";
      if (lead <= 30) return "#ffb000";
      if (lead <= 60) return "#ff7f0e";
      return "#d62728";
    }}

    function edgeText(e) {{
      const itemCount = Array.isArray(e.items) ? e.items.length : 0;
      const itemPreview = itemCount ? e.items.join(", ") : "n/a";
      const m = e.edge_metrics || null;
      const riskImpact = currentPanelMode === "simulated_risk" ? simulatedRiskEdgeImpact(e.id) : null;
      const riskLines = simulatedRiskEdgeImpactLines(riskImpact);
      if (!m) {{
        return [
          `Edge: ${{e.id}}`,
          `${{e.from}} -> ${{e.to}}`,
          `Items (${{itemCount}}): ${{itemPreview}}`,
          ...riskLines,
        ].join("<br>");
      }}
      const qtyBehavior = m.qty_constant_flag ? "quantite tres constante" : `${{m.distinct_shipped_qty}} niveaux de quantite`;
      return [
        `Edge: ${{e.id}}`,
        `${{e.from}} -> ${{e.to}}`,
        `Items (${{itemCount}}): ${{itemPreview}}`,
        `Transit planifie envoi-reception: ${{e.planned_lead_days ?? 'n/a'}} j`,
        `Transit observe moyen: ${{m.avg_lead_days}} j`,
        `Transit observe min-max: ${{m.min_lead_days}} - ${{m.max_lead_days}} j`,
        `Transit observe p50 / p90: ${{m.lead_p50_days}} / ${{m.lead_p90_days}} j`,
        `Variabilite transit (ecart-type): ${{m.lead_std_days}} j`,
        `Safety time destination: ${{m.safety_time_days}} j`,
        `Transit + safety moyen: ${{m.effective_lead_days}} j`,
        `Lignes d'expedition observees: ${{m.shipment_rows}}`,
        `Profil quantite: ${{qtyBehavior}}`,
        ...riskLines,
      ].join("<br>");
    }}

    function toRad(deg) {{
      return deg * Math.PI / 180.0;
    }}

    function toDeg(rad) {{
      return rad * 180.0 / Math.PI;
    }}

    function edgeSelectionPoints(src, dst) {{
      const lonDelta = Math.abs(dst.lon - src.lon);
      const wrappedLonDelta = Math.min(lonDelta, 360 - lonDelta);
      const approxDeg = Math.hypot(dst.lat - src.lat, wrappedLonDelta);
      const steps = Math.max(96, Math.min(720, Math.ceil(approxDeg * 8)));
      const europeCountries = new Set([
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark",
        "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy",
        "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal",
        "Romania", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "United Kingdom",
      ]);
      const srcCountry = String(src.country || "");
      const dstCountry = String(dst.country || "");
      const isUsToEurope = srcCountry === "United States" && europeCountries.has(dstCountry);
      const startFrac = isUsToEurope ? 0.02 : 0.08;
      const endFrac = isUsToEurope ? 0.98 : 0.92;
      const lat1 = toRad(src.lat);
      const lon1 = toRad(src.lon);
      const lat2 = toRad(dst.lat);
      const lon2 = toRad(dst.lon);
      const p1 = [
        Math.cos(lat1) * Math.cos(lon1),
        Math.cos(lat1) * Math.sin(lon1),
        Math.sin(lat1),
      ];
      const p2 = [
        Math.cos(lat2) * Math.cos(lon2),
        Math.cos(lat2) * Math.sin(lon2),
        Math.sin(lat2),
      ];
      const dot = Math.min(1, Math.max(-1, p1[0] * p2[0] + p1[1] * p2[1] + p1[2] * p2[2]));
      const omega = Math.acos(dot);
      const pts = [];
      for (let i = 0; i < steps; i += 1) {{
        const t = startFrac + ((endFrac - startFrac) * i / (steps - 1));
        let x, y, z;
        if (Math.abs(omega) < 1e-9) {{
          x = p1[0] + t * (p2[0] - p1[0]);
          y = p1[1] + t * (p2[1] - p1[1]);
          z = p1[2] + t * (p2[2] - p1[2]);
        }} else {{
          const sinOmega = Math.sin(omega);
          const a = Math.sin((1 - t) * omega) / sinOmega;
          const b = Math.sin(t * omega) / sinOmega;
          x = a * p1[0] + b * p2[0];
          y = a * p1[1] + b * p2[1];
          z = a * p1[2] + b * p2[2];
        }}
        const norm = Math.sqrt(x * x + y * y + z * z) || 1;
        x /= norm;
        y /= norm;
        z /= norm;
        pts.push({{
          lon: toDeg(Math.atan2(y, x)),
          lat: toDeg(Math.atan2(z, Math.sqrt(x * x + y * y))),
        }});
      }}
      return pts;
    }}

    function clamp(value, min, max) {{
      return Math.min(Math.max(value, min), max);
    }}

    function computeGeoView(visibleNodes) {{
      if (!visibleNodes.length) {{
        return {{ scale: 1 }};
      }}
      const lats = visibleNodes.map(n => n.lat);
      const lons = visibleNodes.map(n => n.lon);

      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLon = Math.min(...lons);
      let maxLon = Math.max(...lons);

      const latSpan = Math.max(maxLat - minLat, 0.5);
      const lonSpan = Math.max(maxLon - minLon, 0.5);
      const padLat = Math.max(latSpan * 0.25, 2.0);
      const padLon = Math.max(lonSpan * 0.25, 2.0);

      minLat = clamp(minLat - padLat, -85, 85);
      maxLat = clamp(maxLat + padLat, -85, 85);
      minLon = clamp(minLon - padLon, -180, 180);
      maxLon = clamp(maxLon + padLon, -180, 180);

      const spanLat = Math.max(maxLat - minLat, 1);
      const spanLon = Math.max(maxLon - minLon, 1);
      const effectiveSpan = Math.max(spanLat, spanLon * 0.55);
      const scale = clamp(120 / effectiveSpan, 1.1, 25);

      return {{
        scale: scale,
        center: {{
          lat: (minLat + maxLat) / 2,
          lon: (minLon + maxLon) / 2,
        }}
      }};
    }}

    function edgesInteractiveForCurrentMode() {{
      const showEdgesInput = document.getElementById("showEdges");
      const edgeInteractionInput = document.getElementById("edgeInteraction");
      return Boolean(showEdgesInput && showEdgesInput.checked && edgeInteractionInput && edgeInteractionInput.checked);
    }}

    function buildLotTraceOverlayTraces() {{
      const snapshot = selectedLotTraceSnapshot();
      if (!snapshot || currentPanelMode !== "ops") return [];
      const traces = [];
      const highlightedEdges = snapshot.edgeIds
        .map(edgeId => EDGE_BY_ID[edgeId])
        .filter(Boolean);
      highlightedEdges.forEach((edge) => {{
        const src = nodeById[edge.from];
        const dst = nodeById[edge.to];
        if (!src || !dst) return;
        if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) return;
        if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) return;
        traces.push({{
          type: "scattergeo",
          mode: "lines",
          name: "Flux du lot",
          showlegend: false,
          lon: [src.lon, dst.lon],
          lat: [src.lat, dst.lat],
          line: {{ width: 5, color: "#f97316" }},
          opacity: 0.82,
          hovertemplate: `${{selectedLotId}}<br>${{edge.from}} -> ${{edge.to}}<extra></extra>`,
        }});
      }});
      const nodes = selectedLotMapNodes();
      if (nodes.length) {{
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: "Lot selectionne",
          lon: nodes.map(n => n.lon),
          lat: nodes.map(n => n.lat),
          text: nodes.map(n => `${{selectedLotId}}<br>${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}`),
          customdata: nodes.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 18,
            color: "#f97316",
            opacity: 0.98,
            symbol: "circle",
            line: {{ width: 2.4, color: "#7c2d12" }},
          }},
        }});
      }}
      return traces;
    }}

    function simulatedRiskCascadeRouteClosure(row) {{
      if (!row) return {{ nodeIds: new Set(), edgeIds: new Set() }};
      const edgeIds = new Set(simulatedRiskCascadeEdgeIds(row));
      const nodeIds = new Set(simulatedRiskCascadeNodeIds(row));
      const itemIds = new Set([
        row.item_id,
        ...(Array.isArray(row.impacted_output_items) ? row.impacted_output_items : []),
      ].map(value => String(value || "")).filter(Boolean));

      function edgeItems(edge) {{
        return Array.isArray(edge && edge.items) ? edge.items.map(value => String(value || "")) : [];
      }}

      function edgeMatchesItems(edge, allowedItems) {{
        if (!allowedItems || !allowedItems.size) return true;
        return edgeItems(edge).some(item => allowedItems.has(item));
      }}

      function addEdge(edge) {{
        if (!edge || !edge.id) return;
        edgeIds.add(String(edge.id));
        if (edge.from) nodeIds.add(String(edge.from));
        if (edge.to) nodeIds.add(String(edge.to));
      }}

      for (const edge of (DATA.edges || [])) {{
        if (!nodeIds.has(String(edge.from || "")) || !nodeIds.has(String(edge.to || ""))) continue;
        if (edgeMatchesItems(edge, itemIds)) addEdge(edge);
      }}

      const outputItemIds = new Set(
        (Array.isArray(row.impacted_output_items) ? row.impacted_output_items : [])
          .map(value => String(value || ""))
          .filter(Boolean)
      );
      const factoryNodes = new Set([
        ...(Array.isArray(row.affected_factory_nodes) ? row.affected_factory_nodes : []),
        ...Array.from(nodeIds).filter(nodeId => isFactoryLikeNode(nodeId, String((nodeById[nodeId] || {{}}).type || ""))),
      ].map(value => String(value || "")).filter(Boolean));
      const customerNodes = new Set(
        (Array.isArray(row.affected_customer_nodes) ? row.affected_customer_nodes : [])
          .map(value => String(value || ""))
          .filter(Boolean)
      );

      if (factoryNodes.size && customerNodes.size && outputItemIds.size) {{
        const edges = DATA.edges || [];
        const byFrom = new Map();
        edges.forEach(edge => {{
          const from = String(edge.from || "");
          if (!from) return;
          if (!byFrom.has(from)) byFrom.set(from, []);
          byFrom.get(from).push(edge);
        }});
        const maxDepth = 3;
        factoryNodes.forEach(factoryId => {{
          const queue = [{{ nodeId: factoryId, path: [], seen: new Set([factoryId]) }}];
          while (queue.length) {{
            const current = queue.shift();
            if (!current || current.path.length >= maxDepth) continue;
            (byFrom.get(current.nodeId) || []).forEach(edge => {{
              if (!edgeMatchesItems(edge, outputItemIds)) return;
              const nextNode = String(edge.to || "");
              if (!nextNode || current.seen.has(nextNode)) return;
              const nextPath = [...current.path, edge];
              if (customerNodes.has(nextNode)) {{
                nextPath.forEach(addEdge);
                return;
              }}
              const nextSeen = new Set(current.seen);
              nextSeen.add(nextNode);
              queue.push({{ nodeId: nextNode, path: nextPath, seen: nextSeen }});
            }});
          }}
        }});
      }}

      return {{ nodeIds, edgeIds }};
    }}

    function selectedSimulatedRiskCascadeMapNodes() {{
      if (currentPanelMode !== "simulated_risk" || simulatedRiskVisibleMode() !== "state") return [];
      const row = selectedSimulatedRiskCascade();
      if (!row) return [];
      const closure = simulatedRiskCascadeRouteClosure(row);
      return [...closure.nodeIds]
        .map(nodeId => nodeById[nodeId])
        .filter(node => node && Number.isFinite(node.lat) && Number.isFinite(node.lon));
    }}

    function selectedSimulatedRiskCascadeMapEdges() {{
      if (currentPanelMode !== "simulated_risk" || simulatedRiskVisibleMode() !== "state") return [];
      const row = selectedSimulatedRiskCascade();
      if (!row) return [];
      const closure = simulatedRiskCascadeRouteClosure(row);
      return [...closure.edgeIds].map(edgeId => EDGE_BY_ID[edgeId]).filter(Boolean);
    }}

    function buildSimulatedRiskCascadeOverlayTraces() {{
      const row = selectedSimulatedRiskCascade();
      if (!row || currentPanelMode !== "simulated_risk" || simulatedRiskVisibleMode() !== "state") return [];
      const traces = [];
      const color = simulatedRiskCascadeStageColor(row.stage);
      selectedSimulatedRiskCascadeMapEdges().forEach(edge => {{
        const src = nodeById[edge.from];
        const dst = nodeById[edge.to];
        if (!src || !dst) return;
        if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) return;
        if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) return;
        traces.push({{
          type: "scattergeo",
          mode: "lines",
          name: "Cascade risque",
          showlegend: false,
          lon: [src.lon, dst.lon],
          lat: [src.lat, dst.lat],
          line: {{ width: 6, color }},
          opacity: 0.86,
          hovertemplate: `${{escapeHtmlText(row.root_cause_label || "Cascade risque")}}<br>${{edge.from}} -> ${{edge.to}}<extra></extra>`,
        }});
      }});
      const nodes = selectedSimulatedRiskCascadeMapNodes();
      if (nodes.length) {{
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: "Noeuds cascade",
          lon: nodes.map(n => n.lon),
          lat: nodes.map(n => n.lat),
          text: nodes.map(n => `${{simulatedRiskCascadeShortText(row.root_cause_label || "Cascade risque", 90)}}<br>${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}`),
          customdata: nodes.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 22,
            color,
            opacity: 0.96,
            symbol: "circle",
            line: {{ width: 2.8, color: "#0f172a" }},
          }},
        }});
      }}
      return traces;
    }}

    function buildTraces() {{
      const traces = [];
      const visibleTypes = selectedTypes();
      const edgesInteractive = edgesInteractiveForCurrentMode();
      const showEdges = document.getElementById("showEdges").checked;

      const visibleNodes = (DATA.nodes || []).filter(n =>
        visibleTypes.has(n.type) &&
        Number.isFinite(n.lat) &&
        Number.isFinite(n.lon)
      );
      const lotOverlayNodes = selectedLotMapNodes();
      const cascadeOverlayNodes = selectedSimulatedRiskCascadeMapNodes();
      const uncertaintyOverlayNodes = selectedUncertaintyDriverMapNodes();
      const visibleNodeIds = new Set([...visibleNodes, ...lotOverlayNodes, ...cascadeOverlayNodes, ...uncertaintyOverlayNodes].map(n => n.id));

      (DATA.node_types || []).forEach((nodeType, idx) => {{
        if (!visibleTypes.has(nodeType)) return;
        const style = styleForType(nodeType, idx);
        const subset = visibleNodes.filter(n => n.type === nodeType);
        if (!subset.length) return;
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: style.name,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          text: subset.map(nodeText),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: subset.map(nodeMarkerSize),
            color: subset.map(n => nodeMarkerColor(n, style)),
            opacity: subset.map(nodeMarkerOpacity),
            symbol: style.symbol,
            line: {{ width: 0.6, color: "#111827" }}
          }}
        }});
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          showlegend: false,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hoverinfo: "none",
          marker: {{
            size: 24,
            color: "#111827",
            opacity: 0.001,
            line: {{ width: 0 }}
          }}
        }});
      }});

      let drawnEdges = 0;
      if (showEdges) {{
        for (const e of (DATA.edges || [])) {{
          const src = nodeById[e.from];
          const dst = nodeById[e.to];
          if (!src || !dst) continue;
          if (!visibleNodeIds.has(src.id) || !visibleNodeIds.has(dst.id)) continue;
          if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) continue;
          if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) continue;
          const itemCount = Array.isArray(e.items) ? e.items.length : 0;
          let width = 1 + Math.min(itemCount, 4);
          const mutedEdgeMode = currentPanelMode === "sensitivity" || currentPanelMode === "simulated_risk" || currentPanelMode === "risk" || currentPanelMode === "uncertainty";
          const riskEdgeImpact = currentPanelMode === "simulated_risk" ? simulatedRiskEdgeImpact(e.id) : null;
          const simulatedRiskCascadeFocus = currentPanelMode === "simulated_risk" && Boolean(selectedSimulatedRiskCascadeKey);
          let lineColor = mutedEdgeMode ? "#94a3b8" : edgeLeadColor(e);
          let lineOpacity = mutedEdgeMode ? 0.24 : 0.65;
          if (simulatedRiskCascadeFocus && !riskEdgeImpact) {{
            lineColor = "#cbd5e1";
            lineOpacity = 0.08;
            width = 1.15;
          }}
          if (riskEdgeImpact) {{
            const impactScore = Number(riskEdgeImpact.score) || 0;
            lineColor = riskEdgeImpact.color || "#f97316";
            lineOpacity = 0.92;
            width = Math.max(width, 3.2 + impactScore * 3.2);
          }}
          traces.push({{
            type: "scattergeo",
            mode: "lines",
            showlegend: false,
            lon: [src.lon, dst.lon],
            lat: [src.lat, dst.lat],
            line: {{ width, color: lineColor }},
            opacity: lineOpacity,
            hoverinfo: "skip",
          }});
          if (edgesInteractive) {{
            const selectionPts = edgeSelectionPoints(src, dst);
            traces.push({{
              type: "scattergeo",
              mode: "markers",
              showlegend: false,
              lon: selectionPts.map(p => p.lon),
              lat: selectionPts.map(p => p.lat),
              text: selectionPts.map(() => edgeText(e)),
              customdata: selectionPts.map(() => [e.id, "edge", `${{e.from}} -> ${{e.to}}`]),
              marker: {{
                size: 1,
                color: "#111827",
                opacity: 0.001,
                line: {{ width: 0 }},
              }},
              hovertemplate: "%{{text}}<extra></extra>",
            }});
          }}
          drawnEdges += 1;
        }}
      }}

      buildLotTraceOverlayTraces().forEach(trace => traces.push(trace));
      buildSimulatedRiskCascadeOverlayTraces().forEach(trace => traces.push(trace));
      buildUncertaintyDriverOverlayTraces().forEach(trace => traces.push(trace));
      document.getElementById("stats").textContent =
        `${{visibleNodes.length}} nodes visibles / ${{(DATA.nodes || []).length}} | ` +
        `${{showEdges ? drawnEdges : 0}} flux affiches / ${{(DATA.edges || []).length}}` +
        `${{edgesInteractive ? " (flux interactifs)" : " (flux non interactifs)"}}` +
        `${{selectedLotId ? ` | lot ${{selectedLotId}}` : ""}}` +
        `${{selectedSimulatedRiskCascadeKey ? " | cascade risque selectionnee" : ""}}` +
        `${{selectedUncertaintyDriver ? " | driver incertitude selectionne" : ""}}`;
      const visibleWithLot = [...visibleNodes];
      const seenVisible = new Set(visibleNodes.map(n => n.id));
      lotOverlayNodes.forEach((node) => {{
        if (!seenVisible.has(node.id)) visibleWithLot.push(node);
      }});
      cascadeOverlayNodes.forEach((node) => {{
        if (!seenVisible.has(node.id)) {{
          visibleWithLot.push(node);
          seenVisible.add(node.id);
        }}
      }});
      uncertaintyOverlayNodes.forEach((node) => {{
        if (!seenVisible.has(node.id)) {{
          visibleWithLot.push(node);
          seenVisible.add(node.id);
        }}
      }});
      return {{ traces, visibleNodes: visibleWithLot }};
    }}

    function hideFactoryPanel() {{
      pendingPanelPlotRenderToken += 1;
      function purgePlotlyNode(node) {{
        if (!window.Plotly || !node) return;
        const plots = node.matches && node.matches(".js-plotly-plot")
          ? [node, ...Array.from(node.querySelectorAll(".js-plotly-plot"))]
          : Array.from(node.querySelectorAll(".js-plotly-plot"));
        plots.forEach((plotNode) => {{
          try {{ Plotly.purge(plotNode); }} catch (e) {{}}
        }});
      }}
      const panel = document.getElementById("factoryHoverPanel");
      const incomingBlock = document.getElementById("incomingBlock");
      const outgoingBlock = document.getElementById("outgoingBlock");
      const thirdBlock = document.getElementById("thirdBlock");
      const fourthBlock = document.getElementById("fourthBlock");
      const metaBlock = document.getElementById("panelMeta");
      const metaGrid = document.getElementById("panelMetaGrid");
      const incomingLabel = document.getElementById("incomingLabel");
      const outgoingLabel = document.getElementById("outgoingLabel");
      const thirdLabel = document.getElementById("thirdLabel");
      const fourthLabel = document.getElementById("fourthLabel");
      const incomingTabs = document.getElementById("incomingTabs");
      const outgoingTabs = document.getElementById("outgoingTabs");
      const thirdTabs = document.getElementById("thirdTabs");
      const fourthTabs = document.getElementById("fourthTabs");
      const incomingImg = document.getElementById("factoryIncomingImage");
      const outgoingImg = document.getElementById("factoryOutgoingImage");
      const thirdImg = document.getElementById("factoryThirdImage");
      const fourthImg = document.getElementById("factoryFourthImage");
      const incomingFigure = document.getElementById("factoryIncomingFigure");
      const outgoingFigure = document.getElementById("factoryOutgoingFigure");
      const thirdFigure = document.getElementById("factoryThirdFigure");
      const fourthFigure = document.getElementById("factoryFourthFigure");
      const fourthHelp = document.getElementById("fourthHelp");
      const noImg = document.getElementById("factoryHoverNoImage");
      const statePill = document.getElementById("factoryHoverState");
      const clearBtn = document.getElementById("factoryHoverClearSelection");
      const detailControls = document.getElementById("panelDetailControls");
      incomingBlock.style.display = "block";
      outgoingBlock.style.display = "block";
      thirdBlock.style.display = "none";
      if (fourthBlock) {{
        fourthBlock.style.display = "none";
        fourthBlock.classList.remove("panelAdvancedBlock");
        fourthBlock.classList.remove("isCollapsed");
      }}
      incomingLabel.textContent = "Stock matieres premieres (entree)";
      outgoingLabel.textContent = "Production produits finis (sortie)";
      thirdLabel.textContent = "Analyse complementaire";
      if (fourthLabel) fourthLabel.textContent = "MRP / risque";
      incomingTabs.innerHTML = "";
      incomingTabs.style.display = "none";
      outgoingTabs.innerHTML = "";
      outgoingTabs.style.display = "none";
      thirdTabs.innerHTML = "";
      thirdTabs.style.display = "none";
      if (fourthTabs) {{
        fourthTabs.innerHTML = "";
        fourthTabs.style.display = "none";
      }}
      incomingImg.removeAttribute("src");
      incomingImg.style.display = "none";
      outgoingImg.removeAttribute("src");
      outgoingImg.style.display = "none";
      thirdImg.removeAttribute("src");
      thirdImg.style.display = "none";
      if (fourthImg) {{
        fourthImg.removeAttribute("src");
        fourthImg.style.display = "none";
      }}
      purgePlotlyNode(incomingFigure);
      purgePlotlyNode(outgoingFigure);
      purgePlotlyNode(thirdFigure);
      if (fourthFigure) purgePlotlyNode(fourthFigure);
      incomingFigure.innerHTML = "";
      outgoingFigure.innerHTML = "";
      thirdFigure.innerHTML = "";
      if (fourthFigure) fourthFigure.innerHTML = "";
      incomingFigure.style.display = "none";
      outgoingFigure.style.display = "none";
      thirdFigure.style.display = "none";
      if (fourthFigure) fourthFigure.style.display = "none";
      incomingFigure.classList.remove("factoryFigureStackContainer");
      outgoingFigure.classList.remove("factoryFigureStackContainer");
      thirdFigure.classList.remove("factoryFigureStackContainer");
      if (fourthFigure) fourthFigure.classList.remove("factoryFigureStackContainer");
      fourthHelp.style.display = "block";
      if (detailControls) detailControls.classList.remove("visible");
      panelDetailsExpanded = false;
      panelDetailsKey = "";
      metaGrid.innerHTML = "";
      metaBlock.style.display = "none";
      noImg.style.display = "none";
      statePill.textContent = "";
      statePill.classList.remove("visible");
      clearBtn.classList.remove("visible");
      panel.classList.remove("visible");
      panel.classList.remove("hoverPreview");
      panel.style.left = "";
      panel.style.right = "";
      panel.style.top = "";
      panel.style.maxHeight = "";
      currentFactoryHoverId = null;
      currentFactoryHoverType = null;
      lastFactoryPanelRenderKey = "";
    }}

    function isFactoryLikeNode(nodeId, nodeType) {{
      return nodeType === "factory" || (nodeType === "supplier_dc" && FACTORY_LIKE_NODE_IDS.has(nodeId));
    }}

    function isPanelSelectableType(nodeType) {{
      if (nodeType === "edge") return edgesInteractiveForCurrentMode();
      return nodeType === "factory" || nodeType === "supplier_dc" || nodeType === "distribution_center" || nodeType === "customer" || nodeType === "edge";
    }}

    function currentPanelTarget() {{
      if (selectedPanelNodeId && selectedPanelNodeType) {{
        return {{
          nodeId: selectedPanelNodeId,
          nodeType: selectedPanelNodeType,
          state: "Selection",
        }};
      }}
      if (currentHoveredPanelId && currentHoveredPanelType) {{
        return {{
          nodeId: currentHoveredPanelId,
          nodeType: currentHoveredPanelType,
          state: "Survol",
        }};
      }}
      return null;
    }}

    function selectablePointFromEvent(ev) {{
      const points = ev && Array.isArray(ev.points) ? ev.points : [];
      for (const point of points) {{
        if (!Array.isArray(point.customdata)) continue;
        const nodeType = point.customdata[1];
        if (!isPanelSelectableType(nodeType)) continue;
        return point;
      }}
      return null;
    }}

    function refreshFactoryPanel() {{
      const target = currentPanelTarget();
      if (!target) {{
        hideFactoryPanel();
        return;
      }}
      showFactoryPanel(target.nodeId, target.nodeType, target.state);
    }}

    function clearPanelSelection() {{
      selectedPanelNodeId = null;
      selectedPanelNodeType = null;
      refreshFactoryPanel();
    }}

    function updatePanelAnchorFromEvent(ev) {{
      const source = ev && ev.event ? ev.event : null;
      if (!source) return;
      const x = Number(source.clientX);
      const y = Number(source.clientY);
      if (Number.isFinite(x)) panelAnchorClientX = x;
      if (Number.isFinite(y)) panelAnchorClientY = y;
    }}

    function positionFactoryPanel() {{
      const panel = document.getElementById("factoryHoverPanel");
      if (!panel || !panel.classList.contains("visible")) return;
      const margin = 14;
      const gap = 18;
      const defaultTop = 88;
      const panelWidth = Math.min(panel.offsetWidth || 760, Math.max(320, window.innerWidth - margin * 2));
      const anchorX = Number.isFinite(panelAnchorClientX) ? panelAnchorClientX : null;
      let left = window.innerWidth - panelWidth - margin;
      if (anchorX !== null) {{
        const rightCandidate = anchorX + gap;
        const leftCandidate = anchorX - panelWidth - gap;
        const fitsRight = rightCandidate + panelWidth <= window.innerWidth - margin;
        const fitsLeft = leftCandidate >= margin;
        if (fitsRight && (!fitsLeft || anchorX < window.innerWidth / 2)) {{
          left = rightCandidate;
        }} else if (fitsLeft) {{
          left = leftCandidate;
        }} else if (anchorX > window.innerWidth / 2) {{
          left = margin;
        }}
      }}
      left = clamp(left, margin, Math.max(margin, window.innerWidth - panelWidth - margin));
      const top = clamp(defaultTop, margin, Math.max(margin, window.innerHeight - 260));
      panel.style.left = `${{left}}px`;
      panel.style.right = "auto";
      panel.style.top = `${{top}}px`;
      panel.style.maxHeight = `${{Math.max(260, window.innerHeight - top - margin)}}px`;
    }}

    function placeAndResizeFactoryPanel() {{
      positionFactoryPanel();
    }}

    function syncPanelStateWithVisibleNodes(visibleNodes) {{
      const visibleNodeIds = new Set((visibleNodes || []).map(n => n.id));
      if (selectedPanelNodeId && !visibleNodeIds.has(selectedPanelNodeId)) {{
        selectedPanelNodeId = null;
        selectedPanelNodeType = null;
      }}
      if (currentHoveredPanelId && !visibleNodeIds.has(currentHoveredPanelId)) {{
        currentHoveredPanelId = null;
        currentHoveredPanelType = null;
      }}
    }}

    function appendPanelMetaEntry(metaGrid, entry) {{
      const row = document.createElement("div");
      row.className = "panelMetaRow";
      const label = document.createElement("div");
      label.className = "panelMetaLabel";
      label.textContent = (entry && entry.label) || "";
      const value = document.createElement("div");
      value.className = "panelMetaValue";
      const rawValue = (entry && entry.value !== undefined && entry.value !== null)
        ? String(entry.value)
        : "";
      value.textContent = rawValue;
      if (!rawValue) {{
        row.style.gridColumn = "1 / span 2";
        label.style.fontWeight = "700";
        label.style.color = "#0f172a";
        value.style.display = "none";
      }} else if (rawValue.includes("\\n") || rawValue.length > 120) {{
        row.classList.add("multiline");
      }}
      row.appendChild(label);
      row.appendChild(value);
      metaGrid.appendChild(row);
    }}

    function riskZoneBusinessClass(zone) {{
      const value = String(zone || "").toLowerCase();
      if (value.includes("rouge") || value.includes("red") || value.includes("critique")) return "businessAlert";
      if (value.includes("orange")) return "businessAlert";
      if (value.includes("jaune") || value.includes("amber")) return "businessWarn";
      if (value.includes("vert") || value.includes("green")) return "businessOk";
      return "businessInfo";
    }}

    function simulationDiagnosticPayload(nodeId, nodeType) {{
      if (currentPanelMode !== "ops") return null;
      if (nodeType === "edge") {{
        return ((SIMULATION_DIAGNOSTICS.edges || {{}})[nodeId]) || null;
      }}
      return ((SIMULATION_DIAGNOSTICS.nodes || {{}})[nodeId]) || null;
    }}

    function businessSummaryPayload(nodeId, nodeType) {{
      const nodeLabel = nodeType === "edge"
        ? ((EDGE_BY_ID[nodeId] || {{}}).from || "n/a") + " -> " + ((EDGE_BY_ID[nodeId] || {{}}).to || "n/a")
        : ((nodeById[nodeId] || {{}}).name || nodeId);
      const simulationDiagnostic = simulationDiagnosticPayload(nodeId, nodeType);
      if (simulationDiagnostic) {{
        return {{
          pill: simulationDiagnostic.pill || "Diagnostic",
          title: simulationDiagnostic.title || `${{nodeLabel}} - diagnostic simulation`,
          text: simulationDiagnostic.text || "",
          cls: simulationDiagnostic.cls || "businessInfo",
        }};
      }}
      if (currentPanelMode === "sensitivity") {{
        const meta = nodeSensitivityMeta(nodeId);
        if (meta) {{
          const cls = meta.status === "sensitive" ? "businessAlert" : (meta.status === "watch" ? "businessWarn" : "businessOk");
          return {{
            pill: "Sensibilite",
            title: `${{meta.status_label || "Statut sensibilite"}} - ${{nodeLabel}}`,
            text: `Question metier: quel parametre degrade disponibilite produit, taux de replanification ou cout de stockage ? Parametre prioritaire: ${{meta.driver_family_label || "un point faible"}} - ${{meta.driver_label || "n/a"}}. Premier niveau qui degrade les KPI dans la grille: ${{meta.first_unacceptable || "n/a"}}. Utiliser Priorites KPI pour comparer les seuils les plus critiques.`,
            cls,
          }};
        }}
        return {{
          pill: "Sensibilite",
          title: `${{nodeLabel}} - pas de rupture locale identifiee`,
          text: "Question metier: quel parametre degrade disponibilite produit, taux de replanification ou cout de stockage ? Aucun seuil local exploitable dans l'etude courante. Lire les panneaux seulement si le noeud fait partie du perimetre teste.",
          cls: "businessInfo",
        }};
      }}
      if (currentPanelMode === "simulated_risk") {{
        if (simulatedRiskVisibleMode() === "campaign") {{
          const campaign = supplierStressCampaignMeta(nodeId);
          if (campaign) {{
            const cls = campaign.status === "sensitive" ? "businessAlert" : (campaign.status === "watch" ? "businessWarn" : "businessOk");
            const impact = campaign.impact_metier_delta || campaign.impact_metier_kpi || campaign.impact_pct || "n/a";
            return {{
              pill: "Risques simules",
              title: `Stress test fournisseur - ${{nodeLabel}}`,
              text: `Question metier: si ce fournisseur est degrade dans un scenario contrefactuel, quel KPI supply bouge ? Pire famille testee: ${{campaign.driver_label || "n/a"}}. Impact metier: ${{impact}}. Lecture: ${{campaign.impact_metier_lecture || campaign.impact_explanation || "aucune degradation KPI visible"}}.`,
              cls,
            }};
          }}
          return {{
            pill: "Risques simules",
            title: `${{nodeLabel}} - pas de stress test fournisseur local`,
            text: "Question metier: si un fournisseur est degrade, quel impact supply observe-t-on ? Aucun stress test fournisseur local n'est disponible pour ce noeud.",
            cls: "businessInfo",
          }};
        }}
        if (nodeType === "edge") {{
          const impact = simulatedRiskEdgeImpact(nodeId);
          if (impact) {{
            const extraDays = fmtPanelQty(Number(impact.max_extra_days) || 0, 1);
            const multiplier = fmtMultiplierPercent(Number(impact.max_multiplier) || 1);
            return {{
              pill: "Risques simules",
              title: `Delai transport impacte - ${{nodeLabel}}`,
              text: `Question metier: ce flux est-il un vecteur de perturbation ? Oui: ${{impact.delay_row_count || 0}} effet(s) de delai applique(s) sur ${{impact.active_day_count || 0}} jour(s), periode ${{impact.period || "n/a"}}, delai ajoute max ${{extraDays}} j, multiplicateur max ${{multiplier}}.`,
              cls: "businessWarn",
            }};
          }}
          return {{
            pill: "Risques simules",
            title: `${{nodeLabel}} - flux non retarde dans ce scenario`,
            text: "Question metier: ce flux est-il un vecteur de perturbation ? Aucun effet de delai applique n'est observe sur ce flux dans le scenario courant.",
            cls: "businessInfo",
          }};
        }}
        const impact = simulatedRiskNodeImpact(nodeId);
        if (impact) {{
          const cls = impact.stage === "service_client" ? "businessAlert" : (impact.stage === "production" || impact.stage === "cost" ? "businessWarn" : "businessOk");
          return {{
            pill: "Risques simules",
            title: `${{impact.stage_label || "Impact reel"}} - ${{nodeLabel}}`,
            text: `Question metier: ou le scenario a-t-il vraiment pese ? Role carte: ${{impact.role || "noeud impacte"}}. Origine: ${{impact.supplier_label || impact.supplier_id || "n/a"}} / ${{impact.item_label || impact.item_id || "n/a"}}. Declencheur: ${{impact.primary_trigger || "n/a"}}. Periode: ${{impact.period || "n/a"}}. Volume replanifie: ${{impact.production_delay_count || 0}} lignes.`,
            cls,
          }};
        }}
        if (selectedSimulatedRiskCascadeKey) {{
          return {{
            pill: "Risques simules",
            title: `${{nodeLabel}} - hors cascade selectionnee`,
            text: "Question metier: ce noeud participe-t-il au cas selectionne ? Non. Les noeuds et flux du cas choisi restent surlignes sur la carte.",
            cls: "businessInfo",
          }};
        }}
        const meta = nodeSimulatedRiskMeta(nodeId);
        if (meta) {{
          const cls = meta.status === "applied" ? "businessWarn" : (meta.status === "configured" ? "businessInfo" : "businessOk");
          return {{
            pill: "Risques simules",
            title: `${{meta.status_label || "Scenario"}} - ${{nodeLabel}}`,
            text: `Question metier: quels aleas ont vraiment pese sur ce noeud ? Famille appliquee dominante: ${{meta.applied_event_count ? (meta.driver_label || "n/a") : "aucune"}}. Evenements ayant modifie le run: ${{meta.applied_event_count || 0}}. Periode: ${{meta.period || "n/a"}}.`,
            cls,
          }};
        }}
        return {{
          pill: "Risques simules",
          title: `${{nodeLabel}} - aucun evenement local`,
          text: "Question metier: quels aleas ont vraiment pese sur ce noeud ? Aucun evenement fournisseur n'est configure ou applique localement. Les stress tests fournisseurs sont disponibles dans cette vue via le bouton dedie.",
          cls: "businessInfo",
        }};
      }}
      if (currentPanelMode === "risk") {{
        const meta = nodeRiskMeta(nodeId);
        if (meta) {{
          const zone = summaryLineValue(meta, ["Niveau de criticite", "Niveau de risque"]) || meta.decision_zone || "n/a";
          const criticity = summaryLineValue(meta, ["Score criticite fournisseur", "Criticite fournisseur", "Score priorite action", "Priorite d'action"]) || "n/a";
          const uncertainty = summaryLineValue(meta, ["Marge incertitude scoring", "Marge incertitude"]) || "n/a";
          const action = summaryLineValue(meta, "Action prudente") || "n/a";
          const riskScore = Math.max(Number(meta.risk_probability) || 0, Number(meta.action_priority_score) || 0);
          const uncertaintyScore = Number(meta.prediction_uncertainty) || riskPredictionUncertainty(meta);
          const matrixCell = riskScore >= 0.35
            ? (uncertaintyScore >= 0.20 ? "menace forte + incertitude forte" : "menace forte + incertitude faible")
            : (uncertaintyScore >= 0.20 ? "menace faible + incertitude forte" : "menace faible + incertitude faible");
          return {{
            pill: "Criticite",
            title: `Criticite ${{zone}} - ${{nodeLabel}}`,
            text: `Question metier: quel fournisseur merite une action ou une surveillance ? Score criticite fournisseur ${{criticity}}. Classe ${{zone}}. Action metier: ${{action}}. Marge d'incertitude scoring ${{uncertainty}} dans les details de confiance.`,
            cls: riskZoneBusinessClass(zone),
          }};
        }}
        return {{
          pill: "Criticite",
          title: `${{nodeLabel}} - pas de fiche criticite fournisseur`,
          text: "Question metier: quel fournisseur est critique et merite une action ou une surveillance ? Aucune criticite fournisseur locale n'est disponible pour ce noeud dans le run courant.",
          cls: "businessInfo",
        }};
      }}
      if (currentPanelMode === "uncertainty") {{
        const general = nodeUncertaintyMeta(nodeId, nodeType);
        if (general) {{
          if (general && general.source === "montecarlo") {{
            const impactMeta = selectedUncertaintyImpact(general) || general;
            if (!selectedUncertaintyImpact(general)) {{
              return {{
                pill: "Monte Carlo",
                title: `${{nodeLabel}} - aucun impact pour cette vue`,
                text: `Question metier: comment ce noeud contribue-t-il aux ecarts observes dans les runs Monte Carlo ? Aucun impact local detecte pour la vue choisie.`,
                cls: "businessInfo",
              }};
            }}
            const cls = impactMeta.status === "sensitive" ? "businessAlert" : (impactMeta.status === "watch" ? "businessWarn" : "businessOk");
            const impact = `${{fmtPanelQty((Number(impactMeta.score) || 0) * 100, 1)}}%`;
            const driver = impactMeta.dominant_dimension || "n/a";
            const viewLabel = UNCERTAINTY_VIEW_LABELS[uncertaintyDisplayMode] || uncertaintyDisplayMode;
            const detailLabel = uncertaintyDisplayMode === "detail_type" ? ` Type detail: ${{UNCERTAINTY_MODE_LABELS[uncertaintyMode] || uncertaintyMode}}.` : "";
            const corr = Number.isFinite(Number(impactMeta.fill_rate_correlation)) ? Number(impactMeta.fill_rate_correlation).toFixed(2) : "n/a";
            return {{
              pill: "Monte Carlo",
              title: `${{impactMeta.status_label || "Lecture Monte Carlo"}} - ${{nodeLabel}}`,
              text: `Question metier: comment ce noeud contribue-t-il aux ecarts observes quand on rejoue la baseline avec aleas ? Vue carte: ${{viewLabel}}.${{detailLabel}} Lecture: ${{impactMeta.title || "impact Monte Carlo"}}. Impact noeud ${{impact}}. Driver principal: ${{driver}}. Correlation avec disponibilite produit: ${{corr}}.`,
              cls,
            }};
          }}
        }}
        return {{
          pill: "Monte Carlo",
          title: `${{nodeLabel}} - pas d'impact Monte Carlo local`,
          text: "Question metier: comment ce noeud contribue-t-il aux ecarts observes dans les runs Monte Carlo ? Aucun driver Monte Carlo local n'est disponible pour ce noeud.",
          cls: "businessInfo",
        }};
      }}
      if (currentPanelMode === "structural") {{
        return {{
          pill: "Structurel",
          title: `${{nodeLabel}} - fragilite structurelle`,
          text: "Question metier: ou le reseau est-il fragile par construction ? Lecture reseau: dependances amont/aval, exposition multi-sites, alternatives et concentration des flux.",
          cls: "businessInfo",
        }};
      }}
      if (currentPanelMode === "data" || currentPanelMode === "model" || currentPanelMode === "json") {{
        return {{
          pill: "Debug",
          title: `${{nodeLabel}} - audit technique`,
          text: "Vue reservee a l'audit: sources, champs, JSON, regles et equations. Elle sert a expliquer ou verifier, pas a piloter directement le run.",
          cls: "businessInfo",
        }};
      }}
      if (nodeType === "edge") {{
        const edge = EDGE_BY_ID[nodeId] || {{}};
        const m = edge.edge_metrics || {{}};
        const planned = Number.isFinite(edge.planned_lead_days) ? `${{edge.planned_lead_days}} j` : "n/a";
        const observed = Number.isFinite(m.avg_lead_days) ? `${{m.avg_lead_days}} j` : "n/a";
        return {{
          pill: "Run nominal",
          title: `${{nodeLabel}} - flux physique simule`,
          text: `Question metier: que s'est-il passe dans le run nominal ? Lire les envois, receptions et carnet sur ce flux. Delai prevu ${{planned}}, delai observe moyen ${{observed}}.`,
          cls: "businessInfo",
        }};
      }}
      if (nodeType === "customer") {{
        return {{
          pill: "Run nominal",
          title: `${{nodeLabel}} - disponibilite produit du run`,
          text: "Question metier: que s'est-il passe dans le run nominal ? Lecture factuelle: demande, quantite servie, backlog et receptions aval. Pas de prediction dans cet onglet.",
          cls: "businessOk",
        }};
      }}
      if (nodeType === "supplier_dc") {{
        return {{
          pill: "Run nominal",
          title: `${{nodeLabel}} - fournisseur dans le run courant`,
          text: "Question metier: que s'est-il passe dans le run nominal ? Lecture factuelle: commandes recues, envois physiques, stock fournisseur, capacite et carnet MRP. Les risques et incertitudes sont dans leurs onglets dedies.",
          cls: "businessInfo",
        }};
      }}
      if (isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          pill: "Run nominal",
          title: `${{nodeLabel}} - execution industrielle du run`,
          text: "Question metier: que s'est-il passe dans le run nominal ? Lecture factuelle: stocks intrants, ordres fournisseurs, receptions entree usine, production et pilotage MRP.",
          cls: "businessInfo",
        }};
      }}
      return {{
        pill: "Run nominal",
        title: `${{nodeLabel}} - lecture du run courant`,
        text: "Question metier: que s'est-il passe dans le run nominal ? Lecture factuelle des flux, stocks, ordres et KPI disponibles pour ce noeud.",
        cls: "businessInfo",
      }};
    }}

    function renderBusinessSummary(nodeId, nodeType) {{
      const summary = document.getElementById("businessSummary");
      const pill = document.getElementById("businessSummaryPill");
      const title = document.getElementById("businessSummaryTitle");
      const text = document.getElementById("businessSummaryText");
      if (!summary || !pill || !title || !text) return false;
      const payload = businessSummaryPayload(nodeId, nodeType);
      if (!payload || !payload.title) {{
        summary.style.display = "none";
        return false;
      }}
      summary.className = `businessSummary ${{payload.cls || "businessInfo"}}`;
      pill.textContent = payload.pill || "Lecture";
      title.textContent = payload.title;
      text.textContent = payload.text || "";
      summary.style.display = "block";
      return true;
    }}

    function monteCarloCorrText(value) {{
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric.toFixed(2) : "n/a";
    }}

    function renderUncertaintyPanelSummaryHtml(generalMetrics) {{
      const impactMeta = selectedUncertaintyImpact(generalMetrics) || generalMetrics || {{}};
      const rawStatus = impactMeta.status || generalMetrics.status || "robust";
      const status = ["robust", "watch", "sensitive", "not_local"].includes(rawStatus) ? rawStatus : "robust";
      const statusLabel = impactMeta.status_label || generalMetrics.status_label || "Lecture Monte Carlo";
      const score = Number(impactMeta.score ?? generalMetrics.score) || 0;
      const scoreLabel = `${{fmtPanelQty(score * 100, 1)}}%`;
      const driver = impactMeta.dominant_dimension || generalMetrics.driver_label || generalMetrics.dominant_dimension || "n/a";
      const runs = generalMetrics.runs || "n/a";
      const horizon = generalMetrics.days ? `${{generalMetrics.days}} j` : "n/a";
      const profile = generalMetrics.profile || "n/a";
      const fillCorr = monteCarloCorrText(impactMeta.fill_rate_correlation ?? generalMetrics.fill_rate_correlation);
      const backlogCorr = monteCarloCorrText(impactMeta.backlog_correlation ?? generalMetrics.backlog_correlation);
      const costCorr = monteCarloCorrText(impactMeta.cost_correlation ?? generalMetrics.cost_correlation);
      return `
        <div class="panelMetaUncertainty">
          <div class="uncertaintyDashboard sensitivityStatus-${{escapeHtmlText(status)}}">
            <div class="uncertaintyHero">
              <div>
                <div class="sensitivityStatusPill">${{escapeHtmlText(statusLabel)}}</div>
                <div class="uncertaintyHeroTitle">${{escapeHtmlText(generalMetrics.title || "Impact Monte Carlo")}}</div>
                <div class="uncertaintyHeroText">Lecture: impact observe sur les runs Monte Carlo. Le score sert a orienter le diagnostic; ce n'est pas une probabilite historique fournisseur.</div>
              </div>
              <div class="uncertaintyHeroFacts">
                <div><span>Impact noeud</span><b>${{escapeHtmlText(scoreLabel)}}</b></div>
                <div><span>Driver</span><b>${{escapeHtmlText(driver)}}</b></div>
                <div><span>Runs</span><b>${{escapeHtmlText(String(runs))}}</b></div>
                <div><span>Horizon</span><b>${{escapeHtmlText(horizon)}}</b></div>
              </div>
            </div>
            <div class="uncertaintyCardGrid">
              <div class="uncertaintyCard">
                <div class="uncertaintyCardLabel">Corr. disponibilite</div>
                <div class="uncertaintyCardValue">${{escapeHtmlText(fillCorr)}}</div>
                <div class="uncertaintyCardNote">lien avec la disponibilite produit</div>
              </div>
              <div class="uncertaintyCard">
                <div class="uncertaintyCardLabel">Corr. backlog</div>
                <div class="uncertaintyCardValue">${{escapeHtmlText(backlogCorr)}}</div>
                <div class="uncertaintyCardNote">lien avec le backlog</div>
              </div>
              <div class="uncertaintyCard">
                <div class="uncertaintyCardLabel">Corr. cout</div>
                <div class="uncertaintyCardValue">${{escapeHtmlText(costCorr)}}</div>
                <div class="uncertaintyCardNote">lien avec le cout total</div>
              </div>
              <div class="uncertaintyCard">
                <div class="uncertaintyCardLabel">Profil teste</div>
                <div class="uncertaintyCardValue">${{escapeHtmlText(profile)}}</div>
                <div class="uncertaintyCardNote">profil Monte Carlo actif</div>
              </div>
            </div>
          </div>
        </div>
      `;
    }}

    function renderPanelMeta(nodeId, nodeType) {{
      const metaBlock = document.getElementById("panelMeta");
      const metaTitle = document.getElementById("panelMetaTitle");
      const metaGrid = document.getElementById("panelMetaGrid");
      metaGrid.innerHTML = "";
      if (currentPanelMode === "data") {{
        const details = nodeType === "edge"
          ? (((DATA_PANEL.edges || {{}})[nodeId]) || null)
          : (((DATA_PANEL.nodes || {{}})[nodeId]) || null);
        const lines = details && Array.isArray(details.summary_lines) ? details.summary_lines : [];
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = (details && details.title) || "Donnees";
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "json") {{
        const details = nodeType === "edge"
          ? (((JSON_PANEL.edges || {{}})[nodeId]) || null)
          : (((JSON_PANEL.nodes || {{}})[nodeId]) || null);
        const lines = details && Array.isArray(details.summary_lines) ? details.summary_lines : [];
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = (details && details.title) || "JSON";
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "model") {{
        const details = nodeType === "edge"
          ? (((MODEL_PANEL.edges || {{}})[nodeId]) || null)
          : (((MODEL_PANEL.nodes || {{}})[nodeId]) || null);
        const lines = details && Array.isArray(details.summary_lines) ? details.summary_lines : [];
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = (details && details.title) || "Modele";
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "sensitivity") {{
        const thresholdNodeMetrics = (THRESHOLD_SENSITIVITY.nodes || {{}})[nodeId] || null;
        const thresholdMetrics = thresholdNodeMetrics || null;
        const realisticNodeMetrics = (REALISTIC_SENSITIVITY.nodes || {{}})[nodeId] || null;
        const realisticMetrics = realisticNodeMetrics || null;
        const thresholdLines = (thresholdMetrics && Array.isArray(thresholdMetrics.summary_lines)) ? thresholdMetrics.summary_lines : [];
        const realisticLines = (realisticMetrics && Array.isArray(realisticMetrics.summary_lines)) ? realisticMetrics.summary_lines : [];
        if (!thresholdLines.length && !realisticLines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent =
          (thresholdMetrics && thresholdMetrics.title) ||
          (realisticMetrics && realisticMetrics.title) ||
          "Sensibilite";
        const entries = [];
        if (thresholdLines.length) {{
          entries.push({{ label: "Analyse seuil", value: "" }});
          thresholdLines.forEach((entry) => entries.push(entry));
        }}
        if (realisticLines.length) {{
          entries.push({{ label: "Analyse locale", value: "" }});
          realisticLines.forEach((entry) => entries.push(entry));
        }}
        entries.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "simulated_risk") {{
        let lines = [];
        if (nodeType === "edge") {{
          const impact = simulatedRiskEdgeImpact(nodeId);
          if (impact) {{
            lines = [
              {{ label: "Lecture", value: "delai transport impacte dans le scenario" }},
              {{ label: "Periode", value: impact.period || "n/a" }},
              {{ label: "Jours touches", value: String(impact.active_day_count || 0) }},
              {{ label: "Lignes appliquees", value: String(impact.delay_row_count || 0) }},
              {{ label: "Delai ajoute max", value: `${{fmtPanelQty(Number(impact.max_extra_days) || 0, 1)}} j` }},
              {{ label: "Multiplicateur lead max", value: fmtMultiplierPercent(Number(impact.max_multiplier) || 1) }},
              {{ label: "Articles", value: Array.isArray(impact.item_ids) ? impact.item_ids.join(", ") : "n/a" }},
            ];
          }}
        }} else {{
          const impact = simulatedRiskNodeImpact(nodeId);
          if (impact) {{
            lines = [
              {{ label: "Impact reel", value: impact.stage_label || "n/a" }},
              {{ label: "Role carte", value: impact.role || "n/a" }},
              {{ label: "Origine", value: `${{impact.supplier_label || impact.supplier_id || "n/a"}} / ${{impact.item_label || impact.item_id || "n/a"}}` }},
              {{ label: "Declencheur", value: impact.primary_trigger || "n/a" }},
              {{ label: "Periode", value: impact.period || "n/a" }},
              {{ label: "Causes supply actives", value: `${{impact.effective_root_count || 0}} / ${{impact.root_count || 0}}` }},
              {{ label: "Volume replanifie", value: String(impact.production_delay_count || 0) }},
              {{ label: "Volume reporte", value: fmtPanelQty(Number(impact.production_shortfall_qty) || 0, 0) }},
              {{ label: "Backlog max", value: fmtPanelQty(Number(impact.customer_backlog_max_qty) || 0, 0) }},
            ];
          }} else if (selectedSimulatedRiskCascadeKey) {{
            lines = [];
          }} else {{
            const meta = nodeSimulatedRiskMeta(nodeId);
            lines = meta && Array.isArray(meta.summary_lines) ? meta.summary_lines : [];
          }}
        }}
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = nodeType === "edge" ? "Impact flux risque simule" : "Impact noeud risque simule";
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "risk") {{
        metaBlock.style.display = "none";
        return false;
      }}
      if (currentPanelMode === "uncertainty") {{
        const generalMetrics = nodeUncertaintyMeta(nodeId, nodeType) || null;
        const generalLines = (generalMetrics && Array.isArray(generalMetrics.summary_lines)) ? generalMetrics.summary_lines : [];
        if (generalMetrics) {{
          metaTitle.textContent = "Synthese Monte Carlo";
          metaGrid.innerHTML = renderUncertaintyPanelSummaryHtml(generalMetrics);
          metaBlock.style.display = "block";
          return true;
        }}
        if (!generalLines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = "Incertitude";
        generalLines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      const metrics = isFactoryLikeNode(nodeId, nodeType)
        ? (FACTORY_CURRENT_METRICS[nodeId] || null)
        : (nodeType === "supplier_dc"
            ? (SUPPLIER_LOCAL_METRICS[nodeId] || null)
            : (nodeType === "customer"
                ? (CUSTOMER_CURRENT_METRICS[nodeId] || null)
                : (nodeType === "edge" ? (EDGE_BY_ID[nodeId] || null) : null)));
      const simulationDiagnostic = simulationDiagnosticPayload(nodeId, nodeType);
      if (simulationDiagnostic && Array.isArray(simulationDiagnostic.summary_lines) && simulationDiagnostic.summary_lines.length) {{
        metaTitle.textContent = "Diagnostic operationnel";
        simulationDiagnostic.summary_lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        const currentLines = (isFactoryLikeNode(nodeId, nodeType) && currentPanelMode === "ops")
          ? buildFactoryWindowSummaryLines(metrics)
          : ((metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : []);
        if (currentLines.length && nodeType !== "edge") {{
          appendPanelMetaEntry(metaGrid, {{ label: "Indicateurs courants", value: "" }});
          currentLines.slice(0, 6).forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        }}
        metaBlock.style.display = "block";
        return true;
      }}
      if (nodeType === "edge") {{
        const edge = EDGE_BY_ID[nodeId] || null;
        const edgeMetrics = edge && edge.edge_metrics ? edge.edge_metrics : null;
        if (!edge || !edgeMetrics) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = "Flux et transits observes";
        const edgeSummary = [
          {{ label: "Flux", value: `${{edge.from}} -> ${{edge.to}}` }},
          {{ label: "Items", value: Array.isArray(edge.items) ? edge.items.join(", ") : "n/a" }},
          {{ label: "Transit planifie", value: `${{edge.planned_lead_days ?? 'n/a'}} j` }},
          {{ label: "Transit moyen observe", value: `${{edgeMetrics.avg_lead_days}} j` }},
          {{ label: "Transit min-max", value: `${{edgeMetrics.min_lead_days}} - ${{edgeMetrics.max_lead_days}} j` }},
          {{ label: "Transit p50 / p90", value: `${{edgeMetrics.lead_p50_days}} / ${{edgeMetrics.lead_p90_days}} j` }},
          {{ label: "Ecart-type transit", value: `${{edgeMetrics.lead_std_days}} j` }},
          {{ label: "Safety time destination", value: `${{edgeMetrics.safety_time_days}} j` }},
          {{ label: "Transit + safety moyen", value: `${{edgeMetrics.effective_lead_days}} j` }},
          {{ label: "Lignes d'expedition", value: `${{edgeMetrics.shipment_rows}}` }},
          {{ label: "Quantites distinctes", value: `${{edgeMetrics.distinct_shipped_qty}}` }},
        ];
        edgeSummary.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      const summaryLines = (isFactoryLikeNode(nodeId, nodeType) && currentPanelMode === "ops")
        ? buildFactoryWindowSummaryLines(metrics)
        : ((metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : []);
      if (!summaryLines.length) {{
        metaBlock.style.display = "none";
        return false;
      }}
      metaTitle.textContent = nodeType === "customer"
        ? "Demande client courante"
        : (isFactoryLikeNode(nodeId, nodeType) ? "Performance industrielle courante" : "Synthese fournisseur");
      summaryLines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
      metaBlock.style.display = "block";
      return true;
    }}

    function panelLabels(nodeId, nodeType) {{
      if (currentPanelMode === "data") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "Fiche flux",
            outgoing: "Source / destination",
            third: "Items transportes",
            fourth: "Couts et delais"
          }};
        }}
        return {{
          incoming: "Fiche noeud",
          outgoing: "Stocks / processus",
          third: "Flux connectes",
          fourth: "Items references"
        }};
      }}
      if (currentPanelMode === "json") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "JSON flux brut",
            outgoing: "JSON source / destination",
            third: "JSON items du flux",
            fourth: "JSON complet"
          }};
        }}
        return {{
          incoming: "JSON noeud brut",
          outgoing: "JSON stocks / processus",
          third: "JSON flux connectes",
          fourth: "JSON complet"
        }};
      }}
      if (currentPanelMode === "model") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "Modele du flux",
            outgoing: "Caracteristiques du flux",
            third: "KPI du flux",
            fourth: "Source / destination"
          }};
        }}
        return {{
          incoming: "Modele du noeud",
          outgoing: "Caracteristiques du noeud",
          third: "KPI du noeud",
          fourth: "MRP / risque"
        }};
      }}
      if (currentPanelMode === "sensitivity") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "Flux - envois / receptions",
            outgoing: "Flux - delais matiere",
            third: "Flux - statuts carnet",
            fourth: "Flux - sensibilite / incertitude"
          }};
        }}
        if (nodeType === "supplier_dc") {{
          return {{
            incoming: "Fournisseur - synthese KPI",
            outgoing: "Fournisseur - courbes KPI",
            third: "Fournisseur - details techniques",
            fourth: "Fournisseur - methode / garde-fous"
          }};
        }}
        if (nodeType === "factory") {{
          return {{
            incoming: "Usine - synthese KPI",
            outgoing: "Usine - courbes KPI",
            third: "Usine - details techniques",
            fourth: "Usine - methode / garde-fous"
          }};
        }}
        if (nodeType === "distribution_center") {{
          return {{
            incoming: "DC - synthese KPI",
            outgoing: "DC - courbes KPI",
            third: "DC - details techniques",
            fourth: "DC - methode / garde-fous"
          }};
        }}
        if (nodeType === "customer") {{
          return {{
            incoming: "Client - synthese sensibilite",
            outgoing: "Client - demande courante"
          }};
        }}
        return {{
          incoming: "Courbe KPI metier",
          outgoing: "Courbe cout / details"
        }};
      }}
      if (currentPanelMode === "risk") {{
        if (nodeType === "supplier_dc") {{
          return {{
            incoming: "Fournisseur - synthese criticite",
            outgoing: "Fournisseur - evolution criticite",
            third: "Fournisseur - couples article-site",
            fourth: "Fournisseur - action recommandee"
          }};
        }}
        if (nodeType === "factory" || nodeType === "distribution_center") {{
          return {{
            incoming: "Site - criticites fournisseurs entrantes",
            outgoing: "Site - evolution des criticites entrantes",
            third: "Site - fournisseurs / articles exposes",
            fourth: "Site - action recommandee"
          }};
        }}
        return {{
          incoming: "Criticite fournisseurs",
          outgoing: "Evolution criticite",
          third: "Couples exposes",
          fourth: "Action recommandee"
        }};
      }}
      if (currentPanelMode === "simulated_risk") {{
        if (simulatedRiskVisibleMode() === "campaign") {{
          if (nodeType === "supplier_dc") {{
            return {{
              incoming: "Stress test fournisseur",
              outgoing: "Stock / reference fournisseur",
              third: "Ordres / envois de reference",
              fourth: "Parametres nominaux"
            }};
          }}
          return {{
            incoming: "Stress tests fournisseurs",
            outgoing: "Reference locale",
            third: "Flux concernes",
            fourth: "Parametres nominaux"
          }};
        }}
        if (nodeType === "edge") {{
          return {{
            incoming: "Delai transport impacte",
            outgoing: "Delais du flux",
            third: "Flux concernes",
            fourth: "Source / destination"
          }};
        }}
        if (nodeType === "supplier_dc") {{
          return {{
            incoming: "Effets appliques",
            outgoing: "Effet sur stock fournisseur",
            third: "Ordres / envois concernes",
            fourth: "References fournisseur"
          }};
        }}
        return {{
          incoming: "Effets appliques",
          outgoing: "Effet local",
          third: "Flux concernes",
          fourth: "References"
        }};
      }}
      if (currentPanelMode === "uncertainty") {{
        if (nodeType === "supplier_dc") {{
          return {{
            incoming: "Drivers locaux Monte Carlo",
            outgoing: "Reference nominale",
            third: "Arbre KPI global",
            fourth: "Sources / limites"
          }};
        }}
        if (nodeType === "factory" || nodeType === "distribution_center") {{
          return {{
            incoming: "Drivers locaux Monte Carlo",
            outgoing: "Reference nominale",
            third: "Arbre KPI global",
            fourth: "Sources / limites"
          }};
        }}
        if (nodeType === "edge") {{
          return {{
            incoming: "Incertitude du flux",
            outgoing: "Donnees flux",
            third: "Delais / carnet",
            fourth: "Source / destination"
          }};
        }}
        return {{
          incoming: "Drivers locaux Monte Carlo",
          outgoing: "Sources / limites",
          third: "Arbre KPI global",
          fourth: "Analyse complementaire"
        }};
      }}
      if (currentPanelMode === "structural") {{
        return {{
          incoming: "Dependances reseau - impact",
          outgoing: "Dependances reseau - impact"
        }};
      }}
      if (lotTraceIsUpstreamInternalSite(nodeId) && isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          incoming: "Stocks intrants et PFI",
          outgoing: "Production et stock PFI",
          third: "Planning lots",
          fourth: "Details MRP"
        }};
      }}
      if (nodeType === "supplier_dc") {{
        return {{
          incoming: "Pilotage / execution",
          outgoing: "Stock fournisseur",
          third: "Details fournisseur",
          fourth: "Details MRP"
        }};
      }}
      if (isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          incoming: "Stocks composants / arrivages",
          outgoing: "Production et stock produits",
          third: "Planning lots",
          fourth: "Details MRP"
        }};
      }}
      if (nodeType === "distribution_center") {{
        return {{
          incoming: "Stock physique DC",
          outgoing: "Receptions DC",
          third: "Expeditions DC",
          fourth: "Details MRP"
        }};
      }}
      if (nodeType === "customer") {{
        return {{
          incoming: "Demande client",
          outgoing: "Servi et backlog",
          third: "Receptions client",
          fourth: "Details MRP"
        }};
      }}
      if (nodeType === "edge") {{
        return {{
          incoming: "Envois / receptions",
          outgoing: "Delais du flux",
          third: "Statuts carnet",
          fourth: "Flux - MRP / carnet"
        }};
      }}
      return {{
        incoming: "Stock matieres",
        outgoing: "Flux aval",
        third: "Capacite",
        fourth: "MRP / risque"
      }};
    }}

    function bundleAssetEntries(entries) {{
      const usable = entries.filter(entry => entry && entry.asset);
      if (!usable.length) return null;
      if (usable.length === 1) return usable[0].asset;
      return {{ bundle: usable }};
    }}

    function panelImages(nodeId, nodeType) {{
      if (currentPanelMode === "data") {{
        const details = nodeType === "edge"
          ? (((DATA_PANEL.edges || {{}})[nodeId]) || null)
          : (((DATA_PANEL.nodes || {{}})[nodeId]) || null);
        if (!details) return null;
        return {{
          incoming: details.incoming || null,
          outgoing: details.outgoing || null,
          third: details.third || null,
          fourth: details.fourth || null,
        }};
      }}
      if (currentPanelMode === "json") {{
        const details = nodeType === "edge"
          ? (((JSON_PANEL.edges || {{}})[nodeId]) || null)
          : (((JSON_PANEL.nodes || {{}})[nodeId]) || null);
        if (!details) return null;
        return {{
          incoming: details.incoming || null,
          outgoing: details.outgoing || null,
          third: details.third || null,
          fourth: details.fourth || null,
        }};
      }}
      if (currentPanelMode === "model") {{
        return null;
      }}
      if (currentPanelMode === "sensitivity") {{
        const payload = nodeType === "factory"
          ? (FACTORY_SENSITIVITY_HOVER_IMAGES[nodeId] || null)
          : (nodeType === "supplier_dc"
              ? (SUPPLIER_SENSITIVITY_HOVER_IMAGES[nodeId] || null)
              : (nodeType === "distribution_center" ? (DC_SENSITIVITY_HOVER_IMAGES[nodeId] || null) : null));
        if (payload) return payload;
        if (nodeType === "edge") {{
          return null;
        }}
        return null;
      }}
      if (currentPanelMode === "risk") {{
        if (nodeType === "factory") return FACTORY_RISK_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "supplier_dc") return SUPPLIER_RISK_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "distribution_center") return DC_RISK_HOVER_IMAGES[nodeId] || null;
        return null;
      }}
      if (currentPanelMode === "simulated_risk") {{
        if (nodeType === "edge") {{
          const edge = EDGE_BY_ID[nodeId] || null;
          const modelDetails = ((MODEL_PANEL.edges || {{}})[nodeId]) || null;
          const riskAsset = simulatedRiskEdgeAsset(nodeId);
          if (!riskAsset && !modelDetails) return null;
          return {{
            incoming: riskAsset,
            outgoing: modelDetails ? (modelDetails.lead_time || modelDetails.nominal || null) : null,
            third: modelDetails ? (modelDetails.order_flow || modelDetails.stock_flow || null) : null,
            fourth: edge ? {{
              html: `
                <div class="factoryHtmlPanelContent sensitivityHtmlPanelContent">
                  <div class="orderLedgerTextHeader">${{escapeHtmlText(nodeId)}} - flux</div>
                  <div class="orderLedgerStatus">${{escapeHtmlText((edge.from || "n/a") + " -> " + (edge.to || "n/a"))}}</div>
                </div>
              `
            }} : null,
          }};
        }}
        const simulatedMeta = nodeSimulatedRiskMeta(nodeId);
        const campaignMeta = supplierStressCampaignMeta(nodeId);
        const modelDetails = ((MODEL_PANEL.nodes || {{}})[nodeId]) || null;
        const impactAsset = simulatedRiskNodeImpactAsset(nodeId);
        if (impactAsset && simulatedRiskVisibleMode() === "state") {{
          const localStateAsset = simulatedMeta
            ? simulatedRiskMetaAsset(simulatedMeta, nodeId)
            : (modelDetails ? (modelDetails.simulated_risks || null) : null);
          return {{
            incoming: impactAsset,
            outgoing: modelDetails ? (modelDetails.stock_flow || null) : null,
            third: modelDetails ? (modelDetails.supplier_order_send || localStateAsset || null) : localStateAsset,
            fourth: localStateAsset || (modelDetails ? (modelDetails.nominal || modelDetails.capacity_nominal || null) : null),
          }};
        }}
        if (simulatedRiskVisibleMode() === "campaign" && campaignMeta && campaignMeta.asset) {{
          return {{
            incoming: campaignMeta.asset,
            outgoing: modelDetails ? (modelDetails.stock_flow || null) : null,
            third: modelDetails ? (modelDetails.supplier_order_send || null) : null,
            fourth: modelDetails ? (modelDetails.nominal || modelDetails.capacity_nominal || null) : null,
          }};
        }}
        if (simulatedMeta && simulatedRiskVisibleMode() === "state") {{
          const stateAsset = (modelDetails && modelDetails.simulated_risks)
            ? modelDetails.simulated_risks
            : simulatedRiskMetaAsset(simulatedMeta, nodeId);
          return {{
            incoming: stateAsset,
            outgoing: modelDetails ? (modelDetails.stock_flow || null) : null,
            third: modelDetails ? (modelDetails.supplier_order_send || null) : null,
            fourth: modelDetails ? (modelDetails.nominal || modelDetails.capacity_nominal || null) : null,
          }};
        }}
        if (!modelDetails || (!simulatedMeta && !modelDetails.simulated_risks)) return null;
        if (nodeType === "supplier_dc") {{
          return {{
            incoming: modelDetails.simulated_risks || null,
            outgoing: modelDetails.stock_flow || null,
            third: modelDetails.supplier_order_send || null,
            fourth: modelDetails.nominal || modelDetails.capacity_nominal || null,
          }};
        }}
        return {{
          incoming: modelDetails.simulated_risks || null,
          outgoing: null,
          third: null,
          fourth: null,
        }};
      }}
      if (currentPanelMode === "uncertainty") {{
        const modelDetails = nodeType === "edge"
          ? (((MODEL_PANEL.edges || {{}})[nodeId]) || null)
          : (((MODEL_PANEL.nodes || {{}})[nodeId]) || null);
        const monteCarloDetails = ((MONTECARLO_UNCERTAINTY.node_assets || {{}})[nodeId]) || null;
        if (monteCarloDetails && nodeType !== "edge") {{
          const kpiTreeAsset = (GLOBAL_KPI_TREE && GLOBAL_KPI_TREE.kind === "kpi_tree") ? GLOBAL_KPI_TREE : null;
          const detailAsset = bundleAssetEntries([
            {{ label: "Reference nominale", asset: modelDetails ? (modelDetails.nominal || modelDetails.capacity_nominal || null) : null }},
          ]);
          return {{
            incoming: monteCarloDetails,
            outgoing: detailAsset,
            third: kpiTreeAsset,
            fourth: null,
          }};
        }}
        return null;
      }}
      if (currentPanelMode === "structural") {{
        if (nodeType === "factory") return FACTORY_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "supplier_dc") return SUPPLIER_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "distribution_center") return DC_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        return null;
      }}
      const modelDetails = nodeType === "edge"
        ? (((MODEL_PANEL.edges || {{}})[nodeId]) || null)
        : (((MODEL_PANEL.nodes || {{}})[nodeId]) || null);
      if (nodeType === "supplier_dc") {{
        const supplierBase = SUPPLIER_HOVER_IMAGES[nodeId] || {{}};
        const supplierFlowTop = (modelDetails && modelDetails.supplier_order_send) || supplierBase.outgoing || supplierBase.incoming || null;
        const supplierStockTop = supplierFlowTop === supplierBase.incoming
          ? null
          : (supplierBase.incoming || null);
        const supplierDetailEntries = modelDetails ? [
          {{ label: "Bilan stock fournisseur", asset: modelDetails.stock_flow || null }},
          {{ label: "References fournisseur", asset: modelDetails.nominal || null }},
          {{ label: "Reference capacite", asset: modelDetails.capacity_nominal || null }},
        ] : [];
        const supplierDetailBundle = {{
          bundle: supplierDetailEntries.filter(entry => !!entry.asset)
        }};
        const supplierMrpEntries = modelDetails ? [
          {{ label: "Carnet", asset: modelDetails.third || null }},
          {{ label: "Flux MRP", asset: modelDetails.outgoing || null }},
          {{ label: "Risques MRP", asset: modelDetails.risk || null }},
          {{ label: "Detail calcul MRP", asset: modelDetails.incoming || null }},
        ] : [];
        const supplierMrpBundle = {{
          bundle: supplierMrpEntries.filter(entry => !!entry.asset)
        }};
        const supplierMrpFourth = supplierMrpBundle.bundle.length ? supplierMrpBundle : null;
        return {{
          ...supplierBase,
          incoming: supplierFlowTop,
          outgoing: supplierStockTop,
          third: supplierDetailBundle.bundle.length ? supplierDetailBundle : null,
          fourth: supplierMrpFourth
        }};
      }}
      const modelBundleEntries = modelDetails ? [
        {{ label: "Reference capacite", asset: modelDetails.capacity_nominal || null }},
        {{ label: "Carnet", asset: modelDetails.third || null }},
        {{ label: nodeType === "factory" ? "Ordres fournisseurs / receptions" : "Flux MRP", asset: modelDetails.outgoing || null }},
        {{ label: "Risques MRP", asset: modelDetails.risk || null }},
        {{ label: "Detail calcul MRP", asset: modelDetails.incoming || null }},
      ] : [];
      if (nodeType !== "supplier_dc" && nodeType !== "customer") {{
        modelBundleEntries.unshift({{ label: "Reappro amont", asset: modelDetails ? (modelDetails.fourth || null) : null }});
      }}
      const modelBundle = modelDetails ? {{
        bundle: modelBundleEntries.filter(entry => !!entry.asset)
      }} : null;
      const modelFourth = modelBundle && modelBundle.bundle.length ? modelBundle : null;
      if (isFactoryLikeNode(nodeId, nodeType)) {{
        return {{ ...(FACTORY_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (nodeType === "distribution_center") {{
        return {{ ...(DC_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (nodeType === "customer") {{
        return {{ ...(CUSTOMER_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (nodeType === "edge") {{
        if (!modelDetails) return null;
        return {{
          incoming: modelDetails.incoming || null,
          outgoing: modelDetails.outgoing || null,
          third: modelDetails.third || null,
          fourth: modelDetails.fourth || null,
        }};
      }}
      return modelFourth ? {{ fourth: modelFourth }} : null;
    }}

    function isDebugPanelMode(mode) {{
      return mode === "data" || mode === "model" || mode === "json";
    }}

    function setSimulatedRiskViewMode(mode) {{
      simulatedRiskViewMode = mode === "campaign" ? "campaign" : "state";
      normalizeSimulatedRiskViewMode();
      updateSimulatedRiskControls();
      lastFactoryPanelRenderKey = "";
      draw();
    }}

    function updateSimulatedRiskControls() {{
      normalizeSimulatedRiskViewMode();
      const hasState = simulatedRiskStateHasNodes();
      const hasCampaign = simulatedRiskCampaignHasNodes();
      const visibleMode = simulatedRiskVisibleMode();
      const value = document.getElementById("simulatedRiskViewValue");
      if (value) {{
        value.textContent = visibleMode === "state"
          ? "scenario injecte actif"
          : (visibleMode === "campaign" ? "stress tests fournisseurs" : "aucun evenement injecte");
      }}
      const stateBtn = document.getElementById("simulatedRiskStateBtn");
      if (stateBtn) {{
        stateBtn.disabled = !hasState;
        stateBtn.classList.toggle("active", visibleMode === "state");
      }}
      const campaignBtn = document.getElementById("supplierStressCampaignBtn");
      if (campaignBtn) {{
        campaignBtn.disabled = !hasCampaign;
        campaignBtn.classList.toggle("active", visibleMode === "campaign");
      }}
      const legend = document.getElementById("simulatedRiskLegend");
      if (legend) {{
        const hint = visibleMode === "state"
          ? "Risques simules: evenements scenario metier et declenchements state-dependent appliques dans le run courant."
          : "Risques simules: stress tests fournisseurs contrefactuels disponibles pour comparer les vulnerabilites locales.";
        legend.setAttribute("title", hint);
      }}
      const legendHint = document.getElementById("simulatedRiskLegendHint");
      if (legendHint) {{
        legendHint.textContent = visibleMode === "state"
          ? "Scenario injecte: couleur = impact supply reel quand disponible; sinon famille appliquee dominante. Les flux rouges/oranges sont les delais transport impactants."
          : "Stress tests fournisseurs: couleur = pire famille testee. Taille = intensite du stress test. Ces resultats sont contrefactuels, pas des evenements observes.";
      }}
      const globalSummary = document.getElementById("simulatedRiskGlobalSummary");
      if (globalSummary) {{
        const metrics = selectedSimulatedRiskMetrics();
        const global = metrics.global || {{}};
        if (visibleMode === "campaign") {{
          const stressCases = Number(global.stress_case_count || global.case_count || 0);
          const suppliers = Number(global.supplier_count || Object.keys(metrics.nodes || {{}}).length || 0);
          const dominant = global.dominant_label || SIMULATED_RISK_FAMILY_LABELS[global.dominant_family] || global.dominant_family || "n/a";
          const maxImpact = Number(global.max_impact_metier_pct || global.max_impact_pct || 0);
          globalSummary.textContent = `Stress tests fournisseurs: ${{stressCases}} cas simules sur ${{suppliers}} fournisseurs. Famille dominante: ${{dominant}}. Impact metier max: ${{fmtPanelQty(maxImpact, 1)}}%.`;
        }} else {{
          const counts = global.applied_family_counts || global.family_counts || {{}};
          const families = Object.entries(counts)
            .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
            .slice(0, 5)
            .map(([family, count]) => `${{SIMULATED_RISK_FAMILY_LABELS[family] || family}}: ${{count}}`);
          const applied = Number(global.applied_event_count || 0);
          const nodes = Number(global.applied_node_count || global.node_count || 0);
          const diagnostic = SIMULATED_RISK_GLOBAL_DIAGNOSTIC.summary || {{}};
          const impactedEdges = Number(diagnostic.edge_delay_impact_count || 0);
          const impactedNodes = Number(diagnostic.node_impact_count || 0);
          const modeLabel = "Scenario injecte";
          globalSummary.textContent = families.length
            ? `${{modeLabel}}: ${{applied}} evenements ont modifie le run sur ${{nodes}} noeuds. Impacts supply colores: ${{impactedNodes}} noeuds, ${{impactedEdges}} flux retardes. Familles touchees: ${{families.join(" ; ")}}.`
            : `${{modeLabel}}: aucun evenement fournisseur configure ou applique dans ce run.`;
        }}
      }}
      const cascadeSelect = document.getElementById("simulatedRiskCascadeSelect");
      const stageFilter = document.getElementById("simulatedRiskCascadeStageFilter");
      const familyFilter = document.getElementById("simulatedRiskCascadeFamilyFilter");
      const clearCascadeBtn = document.getElementById("simulatedRiskCascadeClearBtn");
      if (stageFilter) stageFilter.value = simulatedRiskCascadeStageFilter;
      if (familyFilter) familyFilter.value = simulatedRiskCascadeFamilyFilter;
      const filteredCascades = hasState ? filteredSimulatedRiskCascadeRows() : [];
      const filteredKeys = new Set(filteredCascades.map(row => simulatedRiskCascadeKeyForRow(row)));
      if (selectedSimulatedRiskCascadeKey && !filteredKeys.has(selectedSimulatedRiskCascadeKey)) {{
        selectedSimulatedRiskCascadeKey = "";
      }}
      if (cascadeSelect) {{
        const options = ['<option value="">Toutes les cascades</option>'];
        diversifiedSimulatedRiskCascadeRows(filteredCascades, 120).forEach((row) => {{
          const key = simulatedRiskCascadeKeyForRow(row);
          const title = row.root_cause_label || row.label || key;
          const stage = simulatedRiskCascadeStageLabel(row);
          const route = simulatedRiskCascadeRouteText(row);
          options.push(`<option value="${{escapeHtmlText(key)}}">${{escapeHtmlText(simulatedRiskCascadeShortText(`[${{stage}}] ${{route}} | ${{title}}`, 140))}}</option>`);
        }});
        cascadeSelect.innerHTML = options.join("");
        cascadeSelect.value = selectedSimulatedRiskCascadeKey || "";
        cascadeSelect.disabled = !filteredCascades.length;
      }}
      if (stageFilter) stageFilter.disabled = !hasState;
      if (familyFilter) familyFilter.disabled = !hasState;
      if (clearCascadeBtn) clearCascadeBtn.disabled = !hasState || !selectedSimulatedRiskCascadeKey;
    }}

    function updateUncertaintyControls() {{
      const modeSelect = document.getElementById("uncertaintyModeSelect");
      if (modeSelect) modeSelect.value = uncertaintyMode;
      const displaySelect = document.getElementById("uncertaintyDisplaySelect");
      if (displaySelect) displaySelect.value = uncertaintyDisplayMode;
      const detailLabel = document.getElementById("uncertaintyDetailModeLabel");
      if (detailLabel) detailLabel.style.display = uncertaintyDisplayMode === "detail_type" ? "inline-flex" : "none";
      const value = document.getElementById("uncertaintyIntensityValue");
      if (value) {{
        if (uncertaintyDisplayMode === "detail_type") {{
          value.textContent = `detail ${{UNCERTAINTY_MODE_LABELS[uncertaintyMode] || uncertaintyMode}}`;
        }} else {{
          value.textContent = UNCERTAINTY_VIEW_LABELS[uncertaintyDisplayMode] || "types dominants";
        }}
      }}
    }}

    function applyModeUi() {{
      document.body.classList.toggle("showDebugTools", debugToolsVisible);
      const debugToggle = document.getElementById("showDebugTools");
      if (debugToggle) debugToggle.checked = debugToolsVisible;
      document.getElementById("modeOps").classList.toggle("active", currentPanelMode === "ops");
      document.getElementById("modeData").classList.toggle("active", currentPanelMode === "data");
      document.getElementById("modeModel").classList.toggle("active", currentPanelMode === "model");
      document.getElementById("modeJson").classList.toggle("active", currentPanelMode === "json");
      document.getElementById("modeSensitivity").classList.toggle("active", currentPanelMode === "sensitivity");
      document.getElementById("modeSimulatedRisk").classList.toggle("active", currentPanelMode === "simulated_risk");
      document.getElementById("modeRisk").classList.toggle("active", currentPanelMode === "risk");
      document.getElementById("modeUncertainty").classList.toggle("active", currentPanelMode === "uncertainty");
      const structuralBtn = document.getElementById("modeStructural");
      const structuralAvailable = hasStructuralPayload();
      if (structuralBtn) {{
        structuralBtn.classList.toggle("active", currentPanelMode === "structural");
        structuralBtn.classList.toggle("hidden", !structuralAvailable);
        structuralBtn.disabled = !structuralAvailable;
      }}
      const sensitivityLegend = document.getElementById("sensitivityLegend");
      if (sensitivityLegend) {{
        sensitivityLegend.classList.toggle("visible", currentPanelMode === "sensitivity");
      }}
      const simulatedRiskLegend = document.getElementById("simulatedRiskLegend");
      if (simulatedRiskLegend) {{
        simulatedRiskLegend.classList.toggle("visible", currentPanelMode === "simulated_risk");
      }}
      const riskLegend = document.getElementById("riskLegend");
      if (riskLegend) {{
        riskLegend.classList.toggle("visible", currentPanelMode === "risk");
      }}
      const uncertaintyLegend = document.getElementById("uncertaintyLegend");
      if (uncertaintyLegend) {{
        uncertaintyLegend.classList.toggle("visible", currentPanelMode === "uncertainty");
      }}
      const sensitivityTop3Box = document.getElementById("sensitivityTop3Box");
      if (sensitivityTop3Box) {{
        sensitivityTop3Box.classList.toggle("visible", currentPanelMode === "sensitivity");
      }}
      const simulatedRiskControlsBox = document.getElementById("simulatedRiskControlsBox");
      if (simulatedRiskControlsBox) {{
        simulatedRiskControlsBox.classList.toggle("visible", currentPanelMode === "simulated_risk");
      }}
      const uncertaintyMonteCarloBox = document.getElementById("uncertaintyMonteCarloBox");
      if (uncertaintyMonteCarloBox) {{
        uncertaintyMonteCarloBox.classList.toggle("visible", currentPanelMode === "uncertainty");
      }}
      const uncertaintyControlsBox = document.getElementById("uncertaintyControlsBox");
      if (uncertaintyControlsBox) {{
        uncertaintyControlsBox.classList.toggle("visible", currentPanelMode === "uncertainty");
      }}
      updateSimulatedRiskControls();
      updateUncertaintyControls();
      updateLotTraceControls();
      const showEdgesInput = document.getElementById("showEdges");
      const showEdgesLabel = document.getElementById("showEdgesLabel");
      const showEdgesText = document.getElementById("showEdgesText");
      const edgeInteractionInput = document.getElementById("edgeInteraction");
      const edgeInteractionLabel = document.getElementById("edgeInteractionLabel");
      const edgeInteractionText = document.getElementById("edgeInteractionText");
      const edgesInteractive = edgesInteractiveForCurrentMode();
      const showEdges = showEdgesInput ? Boolean(showEdgesInput.checked) : true;
      if (showEdgesInput) {{
        showEdgesInput.disabled = false;
      }}
      if (showEdgesLabel) {{
        showEdgesLabel.title = "Afficher ou masquer les flux.";
        showEdgesLabel.style.opacity = "1";
      }}
      if (showEdgesText) {{
        showEdgesText.textContent = "Afficher flux";
      }}
      if (edgeInteractionInput) {{
        edgeInteractionInput.disabled = !showEdges;
      }}
      if (edgeInteractionLabel) {{
        edgeInteractionLabel.title = showEdges
          ? "Active le survol et le clic sur les flux affiches, dans tous les onglets."
          : "Active d'abord l'affichage des flux pour pouvoir les rendre cliquables.";
        edgeInteractionLabel.style.opacity = showEdges ? "1" : "0.55";
      }}
      if (edgeInteractionText) {{
        edgeInteractionText.textContent = edgesInteractive ? "Flux cliquables actifs" : "Flux cliquables";
      }}
      applyTimelineWindowUi();
    }}

    function setPanelMode(mode) {{
      if (isDebugPanelMode(mode) && !debugToolsVisible) {{
        debugToolsVisible = true;
      }}
      if (mode === "structural" && !hasStructuralPayload()) {{
        return;
      }}
      currentPanelMode = mode;
      lastFactoryPanelRenderKey = "";
      applyModeUi();
      draw();
    }}

    function isAdvancedPanelSlot(slot, nodeId, nodeType) {{
      if (isDebugPanelMode(currentPanelMode)) return false;
      if (currentPanelMode === "ops") {{
        if (isFactoryLikeNode(nodeId, nodeType)) return slot === "third" || slot === "fourth";
        if (nodeType === "supplier_dc") return slot === "third" || slot === "fourth";
        if (nodeType === "customer") return slot === "third" || slot === "fourth";
        if (nodeType === "edge") return slot === "third" || slot === "fourth";
        return slot === "fourth";
      }}
      if (currentPanelMode === "sensitivity") {{
        return slot === "third" || slot === "fourth";
      }}
      if (currentPanelMode === "simulated_risk") {{
        return slot === "outgoing" || slot === "third" || slot === "fourth";
      }}
      if (currentPanelMode === "risk") {{
        return slot === "outgoing" || slot === "third";
      }}
      if (currentPanelMode === "uncertainty") {{
        return slot === "third" || slot === "fourth";
      }}
      return false;
    }}

    function applyPanelDetailVisibility(nodeId, nodeType) {{
      const controls = document.getElementById("panelDetailControls");
      const toggle = document.getElementById("panelDetailsToggle");
      const hint = document.getElementById("panelDetailHint");
      const blocks = [
        {{ slot: "incoming", el: document.getElementById("incomingBlock"), label: document.getElementById("incomingLabel") }},
        {{ slot: "outgoing", el: document.getElementById("outgoingBlock"), label: document.getElementById("outgoingLabel") }},
        {{ slot: "third", el: document.getElementById("thirdBlock"), label: document.getElementById("thirdLabel") }},
        {{ slot: "fourth", el: document.getElementById("fourthBlock"), label: document.getElementById("fourthLabel") }},
      ];
      const advanced = blocks.filter(block =>
        block.el &&
        block.el.style.display !== "none" &&
        isAdvancedPanelSlot(block.slot, nodeId, nodeType)
      );
      blocks.forEach(block => {{
        if (block.el) {{
          block.el.classList.remove("panelAdvancedBlock");
          block.el.classList.remove("isCollapsed");
        }}
      }});
      if (!advanced.length) {{
        if (controls) controls.classList.remove("visible");
        return;
      }}
      advanced.forEach(block => {{
        block.el.classList.add("panelAdvancedBlock");
        block.el.classList.toggle("isCollapsed", !panelDetailsExpanded);
      }});
      const labels = advanced
        .map(block => (block.label ? String(block.label.textContent || "").trim() : "details"))
        .filter(Boolean);
      if (controls) controls.classList.add("visible");
      if (toggle) {{
        toggle.textContent = panelDetailsExpanded
          ? "Masquer details"
          : `Afficher details (${{advanced.length}})`;
      }}
      if (hint) {{
        hint.textContent = panelDetailsExpanded
          ? "Vue complete: les blocs d'audit et de details sont affiches."
          : `Vue resume: masque ${{labels.join(" / ")}}.`;
      }}
    }}

    function showFactoryPanel(nodeId, nodeType, panelState) {{
      const images = panelImages(nodeId, nodeType) || {{}};

      const panel = document.getElementById("factoryHoverPanel");
      const renderKey = [
        currentPanelMode,
        nodeType,
        nodeId,
        panelState || "",
        selectedYearStart,
        selectedYearEnd,
        simulatedRiskViewMode,
        uncertaintyMode,
        uncertaintyDisplayMode,
        selectedLotId,
      ].join("|");
      if (panel.classList.contains("visible") && lastFactoryPanelRenderKey === renderKey) {{
        positionFactoryPanel();
        return;
      }}
      if (panelDetailsKey !== renderKey) {{
        panelDetailsExpanded = false;
        panelDetailsKey = renderKey;
      }}
      lastFactoryPanelRenderKey = renderKey;
      const title = document.getElementById("factoryHoverTitle");
      const incomingBlock = document.getElementById("incomingBlock");
      const outgoingBlock = document.getElementById("outgoingBlock");
      const thirdBlock = document.getElementById("thirdBlock");
      const fourthBlock = document.getElementById("fourthBlock");
      const incomingLabel = document.getElementById("incomingLabel");
      const outgoingLabel = document.getElementById("outgoingLabel");
      const thirdLabel = document.getElementById("thirdLabel");
      const fourthLabel = document.getElementById("fourthLabel");
      const fourthHelp = document.getElementById("fourthHelp");
      const incomingTabs = document.getElementById("incomingTabs");
      const outgoingTabs = document.getElementById("outgoingTabs");
      const thirdTabs = document.getElementById("thirdTabs");
      const incomingImg = document.getElementById("factoryIncomingImage");
      const outgoingImg = document.getElementById("factoryOutgoingImage");
      const thirdImg = document.getElementById("factoryThirdImage");
      const fourthImg = document.getElementById("factoryFourthImage");
      const incomingFigure = document.getElementById("factoryIncomingFigure");
      const outgoingFigure = document.getElementById("factoryOutgoingFigure");
      const thirdFigure = document.getElementById("factoryThirdFigure");
      const fourthFigure = document.getElementById("factoryFourthFigure");
      const fourthTabs = document.getElementById("fourthTabs");
      const noImg = document.getElementById("factoryHoverNoImage");
      const statePill = document.getElementById("factoryHoverState");
      const clearBtn = document.getElementById("factoryHoverClearSelection");
      const nodeInfo = nodeType === "edge" ? (EDGE_BY_ID[nodeId] || {{}}) : (nodeById[nodeId] || {{}});
      const displayNodeId = lotTraceDisplayNodeId(nodeId);
      const nodeName = lotTraceIsUpstreamInternalSite(nodeId)
        ? displayNodeId
        : (nodeType === "edge"
        ? `${{nodeInfo.from || "n/a"}} -> ${{nodeInfo.to || "n/a"}}`
        : (nodeInfo.name || nodeId));
      const nodeTitle = lotTraceIsUpstreamInternalSite(nodeId) ? "Internal PFI Site" :
        (isFactoryLikeNode(nodeId, nodeType) ? "Industrial Site" :
        (nodeType === "supplier_dc" ? "Supplier" :
        (nodeType === "distribution_center" ? "Distribution Center" : (nodeType === "factory" ? "Factory" : (nodeType === "customer" ? "Customer" : "Edge")))));
      const modeTitles = {{
        ops: "Run nominal",
        data: "Donnees",
        model: "Modele",
        json: "DEBUG",
        sensitivity: "Sensibilite",
        simulated_risk: "Risques simules",
        risk: "Criticite fournisseurs",
        uncertainty: "Incertitude",
        structural: "Structurel",
      }};
      const modeTitle = modeTitles[currentPanelMode] || "Run nominal";
      title.textContent = `${{nodeTitle}}: ${{nodeName}} (${{displayNodeId}}) | ${{modeTitle}}`;
      if (panelState) {{
        statePill.textContent = panelState;
        statePill.classList.add("visible");
      }} else {{
        statePill.textContent = "";
        statePill.classList.remove("visible");
      }}
      clearBtn.classList.toggle("visible", !!selectedPanelNodeId);

      const labels = panelLabels(nodeId, nodeType);
      incomingLabel.textContent = labels.incoming;
      outgoingLabel.textContent = labels.outgoing;
      thirdLabel.textContent = labels.third || "Analyse complementaire";
      fourthLabel.textContent = labels.fourth || "Analyse MRP";
      const hasBusinessSummary = renderBusinessSummary(nodeId, nodeType);
      const hasMeta = renderPanelMeta(nodeId, nodeType);

      const incomingImageInfo = images.incoming || null;
      const outgoingImageInfo = images.outgoing || null;
      const thirdImageInfo = images.third || null;
      const fourthImageInfo = images.fourth || null;
      fourthHelp.textContent = currentPanelMode === "json"
        ? "DEBUG: donnees brutes du scenario, enrichies avec items et flux connectes pour faciliter l'audit."
        : (currentPanelMode === "data"
          ? "Audit donnees: sources, champs et corrections. Cette vue sert a verifier les donnees, pas a piloter la decision."
          : (currentPanelMode === "simulated_risk"
            ? "Risques simules: scenario injecte dans le run courant. La carte montre les evenements fournisseurs configures ou declenches qui ont vraiment pese localement."
          : (currentPanelMode === "risk"
            ? "Criticite fournisseurs: lecture structurelle des fournisseurs importants, de la menace estimee, de l'incertitude et de l'action recommandee."
            : (currentPanelMode === "uncertainty"
              ? "Incertitude: la fiche locale mesure les drivers Monte Carlo du noeud selectionne. Les trajectoires et enveloppes globales du run sont dans le bouton Courbes globales."
              : "Run nominal: les premiers panneaux sont la lecture metier. Details MRP regroupe le carnet, les flux planifies et les details de calcul."))));
      fourthHelp.style.display = fourthImageInfo ? "block" : "none";

      incomingBlock.style.display = incomingImageInfo ? "block" : "none";
      outgoingBlock.style.display = outgoingImageInfo ? "block" : "none";
      thirdBlock.style.display = thirdImageInfo ? "block" : "none";
      fourthBlock.style.display = fourthImageInfo ? "block" : "none";

      function buildPlotlyFigure(figure) {{
        if (!figure || !figure.kind) return null;
        if (figure.kind === "line_multi") {{
          if (figure.scenario_tube) {{
            return buildScenarioTubePlotlyFigure(figure, ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569"]);
          }}
          const palette = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569"];
          return {{
            data: (figure.series || []).map((series, idx) => {{
              const filtered = filterSeriesByTimeline(series.days || [], series.values || []);
              const showMarkers = Boolean(series.show_markers) || (filtered.days || []).length <= 2;
              const trace = {{
                type: "scatter",
                mode: showMarkers ? "lines+markers" : "lines",
                name: series.label || `Serie ${{idx + 1}}`,
                x: filtered.days,
                y: filtered.values,
                line: {{
                  width: Number(series.width || 2.2),
                  color: series.color || palette[idx % palette.length],
                  dash: series.dash || "solid",
                  shape: figure.step_like ? "hv" : "linear",
                }},
              }};
              if (showMarkers) {{
                trace.marker = {{
                  size: Number(series.marker_size || 7),
                  color: series.color || palette[idx % palette.length],
                }};
              }}
              return trace;
            }}),
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              meta: {{ lot_trace_category: figure.lot_trace_category || "" }},
              margin: STANDARD_PLOT_MARGIN,
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              xaxis: dayAxisLayout(figure.x_label || "Jour"),
              yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
              legend: STANDARD_LEGEND,
              annotations: figure.note ? [{{
                text: figure.note,
                xref: "paper",
                yref: "paper",
                x: 0,
                y: 1.12,
                xanchor: "left",
                yanchor: "bottom",
                showarrow: false,
                font: {{ size: 10, color: "#475569" }},
                align: "left",
              }}] : [],
            }},
          }};
        }}
        if (figure.kind === "bar") {{
          return {{
            data: [{{
              type: "bar",
              x: figure.labels || [],
              y: figure.values || [],
              marker: {{ color: "#2563eb" }},
            }}],
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: STANDARD_PLOT_MARGIN,
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              xaxis: {{ tickangle: -20 }},
              yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
            }},
          }};
        }}
        if (figure.kind === "production_execution") {{
          const traces = [];
          const addBarSeries = (series, axisSuffix) => {{
            const points = Array.isArray(series.points) ? series.points : [];
            const filtered = filterSeriesByTimeline(
              points.map(point => Number(point.day) || 0),
              points.map(point => Number(point.value) || 0)
            );
            if (!filtered.days.length) return;
            traces.push({{
              type: "bar",
              name: series.label || "Quantite",
              x: filtered.days,
              y: filtered.values,
              xaxis: axisSuffix ? `x${{axisSuffix}}` : "x",
              yaxis: axisSuffix ? `y${{axisSuffix}}` : "y",
              marker: {{
                color: series.color || "#0f766e",
                opacity: Number(series.opacity || 0.78),
              }},
              hovertemplate: "J%{{x}}<br>%{{fullData.name}}: %{{y:,.1f}}<extra></extra>",
            }});
          }};
          const addLineSeries = (series, axisSuffix) => {{
            const points = Array.isArray(series.points) ? series.points : [];
            const filtered = filterSeriesByTimeline(
              points.map(point => Number(point.day) || 0),
              points.map(point => Number(point.value) || 0)
            );
            if (!filtered.days.length) return;
            traces.push({{
              type: "scatter",
              mode: "lines",
              name: series.label || "Repere",
              x: filtered.days,
              y: filtered.values,
              xaxis: axisSuffix ? `x${{axisSuffix}}` : "x",
              yaxis: axisSuffix ? `y${{axisSuffix}}` : "y",
              line: {{
                width: Number(series.width || 1.9),
                color: series.color || "#475569",
                dash: series.dash || "solid",
              }},
              hovertemplate: "J%{{x}}<br>%{{fullData.name}}: %{{y:,.1f}}<extra></extra>",
            }});
          }};
          (figure.top_bars || figure.bars || []).forEach(series => addBarSeries(series, ""));
          (figure.top_lines || []).forEach(series => addLineSeries(series, ""));
          (figure.bottom_bars || []).forEach(series => addBarSeries(series, "2"));
          (figure.bottom_lines || figure.lines || []).forEach(series => addLineSeries(series, "2"));
          return {{
            data: traces,
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              meta: {{ lot_trace_category: figure.lot_trace_category || "" }},
              margin: {{ l: 64, r: 24, t: 72, b: 86 }},
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              barmode: "overlay",
              bargap: 0.16,
              xaxis: {{ ...dayAxisLayout(""), domain: [0, 1], anchor: "y", showticklabels: false }},
              yaxis: {{
                title: figure.top_y_label || "Quantite lot",
                domain: [0.45, 1],
                anchor: "x",
                gridcolor: "#e2e8f0",
              }},
              xaxis2: {{ ...dayAxisLayout(figure.x_label || "Jour"), domain: [0, 1], anchor: "y2" }},
              yaxis2: {{
                title: figure.bottom_y_label || "Quantite / jour",
                domain: [0, 0.32],
                anchor: "x2",
                gridcolor: "#e2e8f0",
              }},
              legend: STANDARD_LEGEND,
              annotations: [
                {{
                  text: figure.top_title || "Lots physiques produits ou reportes",
                  xref: "paper",
                  yref: "paper",
                  x: 0,
                  y: 1.04,
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 10, color: "#334155" }},
                  align: "left",
                }},
                {{
                  text: figure.bottom_title || "Besoin quotidien avant lotification",
                  xref: "paper",
                  yref: "paper",
                  x: 0,
                  y: 0.35,
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 10, color: "#334155" }},
                  align: "left",
                }},
                ...(figure.note ? [{{
                  text: figure.note,
                  xref: "paper",
                  yref: "paper",
                  x: 0,
                  y: 1.17,
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 10, color: "#475569" }},
                  align: "left",
                }}] : []),
              ],
            }},
          }};
        }}
        if (figure.kind === "gantt") {{
          const palette = ["#0f766e", "#2563eb", "#d97706", "#7c3aed", "#0891b2", "#be123c"];
          const range = currentTimelineDayRange();
          const rows = (figure.rows || []).filter((row) => {{
            const start = Number(row.start) || 0;
            const end = Number(row.end) || start + Math.max(1, Number(row.duration) || 1);
            if (currentPanelMode !== "ops" || timelineMaxYear <= 1) return true;
            return end >= range.startDay && start <= range.endDay;
          }});
          const grouped = new Map();
          rows.forEach((row) => {{
            const lane = row.lane || row.item_label || row.item_id || "Lot";
            if (!grouped.has(lane)) grouped.set(lane, []);
            grouped.get(lane).push(row);
          }});
          const laneLabels = Array.from(grouped.keys()).reverse();
          const traces = Array.from(grouped.entries()).map(([lane, laneRows], idx) => {{
            return {{
              type: "bar",
              orientation: "h",
              name: lane,
              y: laneRows.map(() => lane),
              x: laneRows.map(row => Math.max(0.2, Number(row.duration) || Math.max(1, (Number(row.end) || 0) - (Number(row.start) || 0)))),
              base: laneRows.map(row => Number(row.start) || 0),
              marker: {{ color: palette[idx % palette.length], opacity: 0.82 }},
              customdata: laneRows.map(row => [
                Number(row.start) || 0,
                Number(row.duration) || 0,
                Number(row.qty) || 0,
                Number(row.lots) || 0,
                row.lot_policy || "",
                row.binding_cause || "none",
                row.duration_basis || "",
                row.capacity_mode || "",
                Number(row.cap_qty) || 0,
                Number(row.tau_process) || 0,
              ]),
              hovertemplate: `${{lane}}<br>lancement=J%{{customdata[0]}}<br>duree visuelle=%{{customdata[1]:.1f}} j<br>quantite=%{{customdata[2]:,.0f}}<br>lots=%{{customdata[3]:.2f}}<br>base duree=%{{customdata[6]}}<br>mode capacite=%{{customdata[7]}}<br>capacite/j=%{{customdata[8]:,.0f}}<br>tau_process info=%{{customdata[9]:.1f}} j<br>politique=%{{customdata[4]}}<br>contrainte=%{{customdata[5]}}<extra></extra>`,
            }};
          }});
          return {{
            data: traces,
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              meta: {{ lot_trace_category: figure.lot_trace_category || "" }},
              margin: GANTT_PLOT_MARGIN,
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              barmode: "overlay",
              bargap: 0.32,
              xaxis: dayAxisLayout(figure.x_label || "Jour"),
              yaxis: {{
                title: figure.y_label || "",
                categoryorder: "array",
                categoryarray: laneLabels,
                gridcolor: "#f1f5f9",
              }},
              legend: STANDARD_LEGEND,
              annotations: figure.note ? [{{
                text: figure.note,
                xref: "paper",
                yref: "paper",
                x: 0,
                y: 1.12,
                xanchor: "left",
                yanchor: "bottom",
                showarrow: false,
                font: {{ size: 10, color: "#475569" }},
                align: "left",
              }}] : [],
            }},
          }};
        }}
        if (figure.kind === "dual_panel") {{
          const top = figure.top || {{}};
          const bottom = figure.bottom || {{}};
          const isParameterSweep = figure.x_axis_kind === "parameter_sweep";
          const topFiltered = top.kind === "line" && !isParameterSweep ? filterXYByTimeline(top.x || [], top.y || []) : {{ x: top.x || [], y: top.y || [] }};
          const bottomFiltered = bottom.kind === "line" && !isParameterSweep ? filterXYByTimeline(bottom.x || [], bottom.y || []) : {{ x: bottom.x || [], y: bottom.y || [] }};
          const parameterAxisLayout = (label) => ({{
            title: label || "",
            type: "category",
            categoryorder: "array",
            categoryarray: top.x || bottom.x || [],
            gridcolor: "#e2e8f0",
            automargin: true,
          }});
          const topXAxis = top.kind === "line"
            ? (isParameterSweep ? parameterAxisLayout("") : dayAxisLayout(""))
            : {{ title: top.x_label || "", gridcolor: "#e2e8f0" }};
          const bottomXAxis = bottom.kind === "line"
            ? (isParameterSweep ? parameterAxisLayout(bottom.x_label || "") : dayAxisLayout(bottom.x_label || ""))
            : {{ title: bottom.x_label || "", tickangle: -20, gridcolor: "#e2e8f0" }};
          const showLegend = Boolean(figure.show_legend);
          const primaryMode = isParameterSweep ? "lines+markers" : "lines";
          const panelHoverTemplate = (panel) => panel && panel.y_unit === "percent"
            ? "%{{fullData.name}}<br>%{{x}}<br>%{{y:.2f}}%<extra></extra>"
            : "%{{fullData.name}}<br>%{{x}}<br>%{{y:,.2f}}<extra></extra>";
          const panelYAxisLayout = (panel) => {{
            const axis = {{ title: panel.y_label || "", gridcolor: "#e2e8f0" }};
            if (panel.y_unit === "percent") axis.ticksuffix = "%";
            return axis;
          }};
          const traces = [];
          traces.push(top.kind === "bar"
            ? {{
                type: "bar",
                x: top.x || [],
                y: top.y || [],
                marker: {{ color: "#dc2626" }},
                xaxis: "x",
                yaxis: "y",
                name: top.title || "Panel 1",
                showlegend: showLegend,
                hovertemplate: panelHoverTemplate(top),
              }}
            : {{
                type: "scatter",
                mode: primaryMode,
                x: topFiltered.x,
                y: topFiltered.y,
                line: {{ width: 2.2, color: "#dc2626" }},
                marker: {{ size: 7, color: "#dc2626" }},
                xaxis: "x",
                yaxis: "y",
                name: top.title || "Panel 1",
                showlegend: showLegend,
                hovertemplate: panelHoverTemplate(top),
              }});
          traces.push(bottom.kind === "line"
            ? {{
                type: "scatter",
                mode: primaryMode,
                x: bottomFiltered.x,
                y: bottomFiltered.y,
                line: {{ width: 2.2, color: "#2563eb" }},
                marker: {{ size: 7, color: "#2563eb" }},
                xaxis: "x2",
                yaxis: "y2",
                name: bottom.title || "Panel 2",
                showlegend: showLegend,
                hovertemplate: panelHoverTemplate(bottom),
              }}
            : {{
                type: "bar",
                x: bottom.x || [],
                y: bottom.y || [],
                marker: {{ color: "#2563eb" }},
                xaxis: "x2",
                yaxis: "y2",
                name: bottom.title || "Panel 2",
                showlegend: showLegend,
                hovertemplate: panelHoverTemplate(bottom),
              }});
          (top.extra_traces || []).forEach((trace) => {{
            traces.push({{
              ...trace,
              xaxis: "x",
              yaxis: "y",
              hovertemplate: trace.hovertemplate || panelHoverTemplate(top),
            }});
          }});
          (bottom.extra_traces || []).forEach((trace) => {{
            traces.push({{
              ...trace,
              xaxis: "x2",
              yaxis: "y2",
              hovertemplate: trace.hovertemplate || panelHoverTemplate(bottom),
            }});
          }});
          return {{
            data: traces,
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              meta: {{ lot_trace_category: figure.lot_trace_category || "" }},
              margin: {{ l: 60, r: 20, t: 48, b: 46 }},
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              grid: {{ rows: 2, columns: 1, pattern: "independent", roworder: "top to bottom" }},
              xaxis: topXAxis,
              yaxis: panelYAxisLayout(top),
              xaxis2: bottomXAxis,
              yaxis2: panelYAxisLayout(bottom),
              annotations: [
                {{
                  text: top.title || "",
                  x: 0,
                  xref: "paper",
                  y: 1.0,
                  yref: "paper",
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 11, color: "#0f172a" }},
                }},
                {{
                  text: bottom.title || "",
                  x: 0,
                  xref: "paper",
                  y: 0.44,
                  yref: "paper",
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 11, color: "#0f172a" }},
                }},
              ],
              showlegend: showLegend,
              legend: {{ orientation: "h", y: -0.24 }},
            }},
          }};
        }}
        return null;
      }}

      function renderKpiTreeAsset(asset, figureEl) {{
        if (!asset || asset.kind !== "kpi_tree" || !window.Plotly) return false;
        const groups = asset.groups || [];
        const main = asset.main || {{}};
        if (!groups.length || !(main.series || []).length) return false;
        figureEl.style.display = "block";
        figureEl.classList.add("factoryKpiTreePanel");
        figureEl.innerHTML = `
          <div class="kpiTreePanel">
            <div class="kpiTreeHeader">
              <div>
                <div class="kpiTreeTitle">${{asset.title || "Arborescence KPI"}}</div>
                <div class="kpiTreeSubtitle">Question metier: comment les KPI se degradent-ils ensemble dans le temps ? Lecture: performance globale, contributions et ecarts aux cibles.</div>
              </div>
            </div>
            <div class="kpiTreeCards"></div>
            <div class="kpiTreeChart kpiTreeMainChart"></div>
            <div class="kpiTreeDetail">
              <div class="kpiTreeSummary"></div>
              <div class="kpiTreeChart kpiTreeSecondaryChart"></div>
            </div>
          </div>
        `;
        const cardsEl = figureEl.querySelector(".kpiTreeCards");
        const mainChartEl = figureEl.querySelector(".kpiTreeMainChart");
        const summaryEl = figureEl.querySelector(".kpiTreeSummary");
        const secondaryChartEl = figureEl.querySelector(".kpiTreeSecondaryChart");
        let selectedId = groups[0].id;

        function groupById(groupId) {{
          return groups.find(group => group.id === groupId) || groups[0];
        }}
        function renderCards() {{
          cardsEl.innerHTML = "";
          groups.forEach(group => {{
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = group.id === selectedId ? "kpiTreeCard active" : "kpiTreeCard";
            btn.innerHTML = `
              <div class="kpiTreeCardTitle">${{group.label || group.id}}</div>
              <div class="kpiTreeCardObjective">${{group.objective || ""}}</div>
            `;
            btn.onclick = () => {{
              selectedId = group.id;
              renderCards();
              renderSecondary();
            }};
            cardsEl.appendChild(btn);
          }});
        }}
        function renderMain() {{
          const palette = ["#0f766e", "#2563eb", "#d97706"];
          const traces = (main.series || []).map((series, idx) => {{
            const filtered = filterSeriesByTimeline(main.days || [], series.values || []);
            return {{
              type: "scatter",
              mode: "lines",
              name: series.label || series.id,
              x: filtered.days,
              y: filtered.values,
              customdata: (filtered.days || []).map(() => series.id),
              line: {{ width: 2.6, color: series.color || palette[idx % palette.length] }},
              hovertemplate: `${{series.label || series.id}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
            }};
          }});
          installCtrlScrollZoomGate(mainChartEl);
          Plotly.react(mainChartEl, traces, {{
            title: {{ text: "KPI principaux - vue management", font: {{ size: 12 }} }},
            margin: {{ l: 54, r: 18, t: 42, b: 42 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: dayAxisLayout("Jour"),
            yaxis: {{ title: main.y_label || "Score / indice", gridcolor: "#e2e8f0" }},
            legend: {{ orientation: "h", y: -0.22 }},
          }}, PLOTLY_RESPONSIVE_CONFIG);
          mainChartEl.on("plotly_click", (ev) => {{
            const point = ev && ev.points && ev.points[0];
            const groupId = point && point.customdata;
            if (groupId) {{
              selectedId = groupId;
              renderCards();
              renderSecondary();
            }}
          }});
        }}
        function renderSecondary() {{
          const group = groupById(selectedId);
          summaryEl.innerHTML = "";
          (group.summary || []).forEach(row => {{
            const div = document.createElement("div");
            div.className = "kpiTreeSummaryRow";
            div.innerHTML = `<span class="kpiTreeSummaryLabel">${{row.label || ""}}</span><span class="kpiTreeSummaryValue">${{row.value || ""}}</span>`;
            summaryEl.appendChild(div);
          }});
          const traces = (group.secondary || []).map(series => {{
            const filtered = filterSeriesByTimeline(series.days || [], series.values || []);
            return {{
              type: "scatter",
              mode: "lines",
              name: series.label || "KPI secondaire",
              x: filtered.days,
              y: filtered.values,
              line: {{ width: 2.2, color: series.color || "#2563eb", dash: series.dash || "solid" }},
            }};
          }});
          installCtrlScrollZoomGate(secondaryChartEl);
          Plotly.react(secondaryChartEl, traces, {{
            title: {{ text: `KPI secondaires - ${{group.label || selectedId}}`, font: {{ size: 12 }} }},
            margin: {{ l: 58, r: 18, t: 42, b: 42 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: dayAxisLayout("Jour"),
            yaxis: {{ title: group.secondary_y_label || "Valeur", gridcolor: "#e2e8f0" }},
            legend: {{ orientation: "h", y: -0.24 }},
          }}, PLOTLY_RESPONSIVE_CONFIG);
        }}
        renderCards();
        renderMain();
        renderSecondary();
        return true;
      }}

      const plotRenderJobs = [];

      function runQueuedPanelPlotRenderJobs() {{
        const jobs = plotRenderJobs.splice(0, plotRenderJobs.length);
        jobs.forEach((renderJob) => {{
          try {{ renderJob(); }} catch (e) {{}}
        }});
      }}

      function renderAsset(asset, imgEl, figureEl, tabsEl, bundleKey) {{
        function purgePlotlyNode(node) {{
          if (!window.Plotly || !node) return;
          const plots = node.matches && node.matches(".js-plotly-plot")
            ? [node, ...Array.from(node.querySelectorAll(".js-plotly-plot"))]
            : Array.from(node.querySelectorAll(".js-plotly-plot"));
          plots.forEach((plotNode) => {{
            try {{ Plotly.purge(plotNode); }} catch (e) {{}}
          }});
        }}

        function sizedPlotlyLayout(layout, targetEl) {{
          const panel = document.getElementById("factoryHoverPanel");
          const holder = (targetEl.classList && targetEl.classList.contains("factoryFigureStackItem"))
            ? targetEl
            : (targetEl.closest(".factoryFigureStackItem") || targetEl.closest(".factoryPlotFigure") || targetEl.parentElement || targetEl);
          const panelWidth = panel ? panel.clientWidth : 900;
          const width = Math.max(320, Math.min(840, Math.floor((panelWidth || 900) - 28)));
          const isStackItem = holder.classList && holder.classList.contains("factoryFigureStackItem");
          const isCompactFigure = holder.classList && (
            holder.classList.contains("factoryPlotOutgoing") ||
            holder.classList.contains("factoryPlotThird") ||
            holder.classList.contains("factoryPlotFourth")
          );
          const height = isStackItem ? 360 : (isCompactFigure ? 320 : 380);
          return {{
            ...(layout || {{}}),
            autosize: false,
            width,
            height,
            showlegend: (layout || {{}}).showlegend ?? true,
          }};
        }}

        imgEl.removeAttribute("src");
        imgEl.style.display = "none";
        figureEl.innerHTML = "";
        figureEl.style.display = "none";
        figureEl.classList.remove("factoryHtmlPanel");
        figureEl.classList.remove("factoryOrderLedgerPanel");
        figureEl.classList.remove("factoryTallHtmlPanel");
        figureEl.classList.remove("factoryKpiTreePanel");
        figureEl.classList.remove("factoryFigureStackContainer");
        if (tabsEl) {{
          tabsEl.innerHTML = "";
          tabsEl.style.display = "none";
        }}
        purgePlotlyNode(figureEl);
        if (!asset) return false;
        if (Array.isArray(asset.bundle) && asset.bundle.length) {{
          const entries = asset.bundle.filter(entry => entry && entry.asset);
          if (!entries.length) return false;
          const selectionKey = bundleKey || "bundle";
          const hasSavedSelection = Object.prototype.hasOwnProperty.call(panelBundleSelection, selectionKey);
          let selectedIdx = panelBundleSelection[selectionKey] ?? 0;
          if (!hasSavedSelection && selectionKey.includes(":supplier_dc:")) {{
            const graphIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "graph stock fournisseur");
            const physicalFlowIdx = entries.findIndex(entry =>
              ((entry.label || "").toLowerCase().includes("execution") ||
               (entry.label || "").toLowerCase().includes("envois physiques"))
            );
            const carnetIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "carnet");
            const nominalIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "nominal fournisseur");
            const preferredIdx = selectionKey.endsWith(":incoming")
              ? (physicalFlowIdx >= 0 ? physicalFlowIdx : (graphIdx >= 0 ? graphIdx : 0))
              : (selectionKey.endsWith(":fourth") ? (carnetIdx >= 0 ? carnetIdx : 0) : (nominalIdx >= 0 ? nominalIdx : 0));
            if (preferredIdx >= 0) {{
              selectedIdx = preferredIdx;
              panelBundleSelection[selectionKey] = preferredIdx;
            }}
          }} else if (!hasSavedSelection && selectionKey.includes(":factory:")) {{
            const capacityIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "nominal capacite");
            if (capacityIdx >= 0) {{
              selectedIdx = capacityIdx;
              panelBundleSelection[selectionKey] = capacityIdx;
            }}
          }}
          if (selectedIdx >= entries.length) selectedIdx = 0;
          const selectedEntry = entries[selectedIdx] || entries[0];
          const selectedAsset = selectedEntry.asset;
          if (tabsEl && entries.length > 1) {{
            tabsEl.style.display = "flex";
            entries.forEach((entry, idx) => {{
              const btn = document.createElement("button");
              btn.type = "button";
              btn.className = idx === selectedIdx ? "panelSubTab active" : "panelSubTab";
              btn.textContent = entry.label || `Vue ${{idx + 1}}`;
              btn.onclick = () => {{
                panelBundleSelection[selectionKey] = idx;
                renderAsset(asset, imgEl, figureEl, tabsEl, selectionKey);
                requestAnimationFrame(() => {{
                  placeAndResizeFactoryPanel();
                  requestAnimationFrame(runQueuedPanelPlotRenderJobs);
                }});
              }};
              tabsEl.appendChild(btn);
            }});
          }}
          if (selectedAsset && Array.isArray(selectedAsset.bundle) && selectedAsset.bundle.length) {{
            const nestedEntries = selectedAsset.bundle.filter(entry => entry && entry.asset);
            if (!nestedEntries.length) return false;
            const nestedKey = `${{selectionKey}}:${{selectedEntry.label || selectedIdx}}`;
            let nestedIdx = panelBundleSelection[nestedKey] ?? 0;
            if (nestedIdx >= nestedEntries.length) nestedIdx = 0;
            if (tabsEl && nestedEntries.length > 1) {{
              if (entries.length > 1) {{
                const separator = document.createElement("span");
                separator.className = "panelSubTabSeparator";
                tabsEl.appendChild(separator);
              }}
              nestedEntries.forEach((entry, idx) => {{
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = idx === nestedIdx ? "panelSubTab secondary active" : "panelSubTab secondary";
                btn.textContent = entry.label || `Vue ${{idx + 1}}`;
                btn.onclick = () => {{
                  panelBundleSelection[nestedKey] = idx;
                  renderAsset(asset, imgEl, figureEl, tabsEl, selectionKey);
                  requestAnimationFrame(() => {{
                    placeAndResizeFactoryPanel();
                    requestAnimationFrame(runQueuedPanelPlotRenderJobs);
                  }});
                }};
                tabsEl.appendChild(btn);
              }});
            }}
            return renderAsset(nestedEntries[nestedIdx].asset, imgEl, figureEl, null, nestedKey);
          }}
          return renderAsset(selectedAsset, imgEl, figureEl, null, selectionKey);
        }}
        if (asset.data_b64) {{
          imgEl.src = `data:${{asset.mime || "image/png"}};base64,${{asset.data_b64}}`;
          imgEl.style.display = "block";
          return true;
        }}
        if (asset.html) {{
          figureEl.style.display = "block";
          figureEl.classList.add("factoryHtmlPanel");
          figureEl.innerHTML = asset.html;
          if (figureEl.querySelector(".orderLedgerPanelContent")) {{
            figureEl.classList.add("factoryOrderLedgerPanel");
          }}
          if (figureEl.querySelector(".sensitivityHtmlPanelContent")) {{
            figureEl.classList.add("factoryTallHtmlPanel");
          }}
          applyLotTraceHtmlHighlight(figureEl);
          return true;
        }}
        if (asset.kind === "kpi_tree") {{
          return renderKpiTreeAsset(asset, figureEl);
        }}
        if (asset.figure && asset.figure.kind === "dual_panel_multi" && window.Plotly) {{
          const panels = [asset.figure.top || null, asset.figure.bottom || null].filter(Boolean);
          if (!panels.length) return false;
          figureEl.style.display = "flex";
          figureEl.classList.add("factoryFigureStackContainer");
          panels.forEach((panelFigure) => {{
            const child = document.createElement("div");
            child.className = "factoryFigureStackItem";
            figureEl.appendChild(child);
            const plotlyFigure = applyLotTracePlotOverlay(buildPlotlyFigure(panelFigure), nodeId, nodeType);
            if (plotlyFigure) {{
              plotRenderJobs.push(() => {{
                installCtrlScrollZoomGate(child);
                Plotly.react(child, plotlyFigure.data, sizedPlotlyLayout(plotlyFigure.layout, child), PLOTLY_PANEL_CONFIG);
              }});
            }}
          }});
          return true;
        }}
        const plotlyFigure = applyLotTracePlotOverlay(buildPlotlyFigure(asset.figure || null), nodeId, nodeType);
        if (plotlyFigure && window.Plotly) {{
          figureEl.style.display = "block";
          const plotHost = document.createElement("div");
          plotHost.className = "factoryPlotInner";
          figureEl.appendChild(plotHost);
          plotRenderJobs.push(() => {{
            installCtrlScrollZoomGate(plotHost);
            Plotly.react(plotHost, plotlyFigure.data, sizedPlotlyLayout(plotlyFigure.layout, plotHost), PLOTLY_PANEL_CONFIG);
          }});
          return true;
        }}
        return false;
      }}

      panel.classList.add("visible");
      panel.classList.toggle("hoverPreview", panelState === "Survol");
      positionFactoryPanel();

      let visibleCount = 0;
      if (renderAsset(incomingImageInfo, incomingImg, incomingFigure, incomingTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:incoming`)) visibleCount += 1;
      if (renderAsset(outgoingImageInfo, outgoingImg, outgoingFigure, outgoingTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:outgoing`)) visibleCount += 1;
      if (renderAsset(thirdImageInfo, thirdImg, thirdFigure, thirdTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:third`)) visibleCount += 1;
      if (renderAsset(fourthImageInfo, fourthImg, fourthFigure, fourthTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:fourth`)) visibleCount += 1;
      applyPanelDetailVisibility(nodeId, nodeType);

      if (!visibleCount && !hasMeta && !hasBusinessSummary) {{
        hideFactoryPanel();
        return;
      }}
      if (!visibleCount && !hasMeta && !hasBusinessSummary) {{
        if (
          currentPanelMode === "sensitivity" &&
          nodeType === "supplier_dc" &&
          Array.isArray(REALISTIC_SENSITIVITY.selected_suppliers) &&
          !REALISTIC_SENSITIVITY.selected_suppliers.includes(nodeId)
        ) {{
          noImg.textContent = "Pas de courbe locale: fournisseur hors perimetre top actifs de l'etude.";
        }} else if (currentPanelMode === "risk") {{
          noImg.textContent = "Aucune fiche criticite fournisseur disponible pour ce noeud.";
        }} else if (currentPanelMode === "uncertainty") {{
          noImg.textContent = "Aucune fiche incertitude disponible pour ce noeud.";
        }} else {{
          noImg.textContent = "Aucun PNG disponible pour ce noeud.";
        }}
      }}
      noImg.style.display = (visibleCount || hasMeta || hasBusinessSummary) ? "none" : "block";
      currentFactoryHoverId = nodeId;
      currentFactoryHoverType = nodeType;
      const panelRenderToken = ++pendingPanelPlotRenderToken;
      requestAnimationFrame(() => {{
        if (panelRenderToken !== pendingPanelPlotRenderToken) return;
        placeAndResizeFactoryPanel();
        requestAnimationFrame(() => {{
          if (panelRenderToken !== pendingPanelPlotRenderToken) return;
          if (!panel.classList.contains("visible")) return;
          runQueuedPanelPlotRenderJobs();
        }});
      }});
    }}

    function bindHoverHandlers() {{
      if (hoverHandlersBound) return;
      const gd = document.getElementById("chart");
      gd.on("plotly_hover", (ev) => {{
        if (hoverClearTimeout) {{
          clearTimeout(hoverClearTimeout);
          hoverClearTimeout = null;
        }}
        const p = selectablePointFromEvent(ev);
        if (!p) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (!isPanelSelectableType(nodeType)) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
          return;
        }}
        if (!selectedPanelNodeId) {{
          updatePanelAnchorFromEvent(ev);
        }}
        currentHoveredPanelId = nodeId;
        currentHoveredPanelType = nodeType;
        refreshFactoryPanel();
      }});
      gd.on("plotly_unhover", () => {{
        if (hoverClearTimeout) clearTimeout(hoverClearTimeout);
        hoverClearTimeout = setTimeout(() => {{
          hoverClearTimeout = null;
          if (panelPointerInside || selectedPanelNodeId) return;
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
        }}, 180);
      }});
      gd.on("plotly_click", (ev) => {{
        const p = selectablePointFromEvent(ev);
        if (!p) {{
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (!isPanelSelectableType(nodeType)) {{
          return;
        }}
        updatePanelAnchorFromEvent(ev);
        if (selectedPanelNodeId === nodeId && selectedPanelNodeType === nodeType) {{
          selectedPanelNodeId = null;
          selectedPanelNodeType = null;
        }} else {{
          selectedPanelNodeId = nodeId;
          selectedPanelNodeType = nodeType;
        }}
        refreshFactoryPanel();
      }});
      hoverHandlersBound = true;
    }}

    function draw() {{
      const {{ traces, visibleNodes }} = buildTraces();
      syncPanelStateWithVisibleNodes(visibleNodes);
      const geoView = computeGeoView(visibleNodes);
      const geoLayout = {{
        scope: "world",
        projection: {{type: "natural earth", scale: geoView.scale || 1}},
        showland: true,
        landcolor: "#eef2f7",
        showcountries: true,
        countrycolor: "#cbd5e1",
        showocean: true,
        oceancolor: "#f8fbff"
      }};
      if (geoView.center) {{
        geoLayout.center = geoView.center;
      }}

      const layout = {{
        margin: {{l: 0, r: 0, t: 0, b: 0}},
        showlegend: true,
        legend: {{orientation: "h"}},
        hoverdistance: 1,
        spikedistance: -1,
        uirevision: "supply-map-view",
        geo: geoLayout
      }};

      const chartEl = document.getElementById("chart");
      if (chartEl.data) {{
        Plotly.react(chartEl, traces, layout, PLOTLY_MAP_CONFIG);
      }} else {{
        Plotly.newPlot(chartEl, traces, layout, PLOTLY_MAP_CONFIG);
      }}
      bindHoverHandlers();
      refreshFactoryPanel();
    }}

    function renderGlobalKpiTree() {{
      const figureEl = document.getElementById("globalKpiTreeFigure");
      if (!figureEl) return false;
      figureEl.innerHTML = "";
      if (!GLOBAL_KPI_TREE || GLOBAL_KPI_TREE.kind !== "kpi_tree" || !window.Plotly) {{
        figureEl.innerHTML = '<div class="panelEmptyState">Aucun arbre KPI global disponible pour ce run.</div>';
        return false;
      }}
      const asset = GLOBAL_KPI_TREE;
      const groups = asset.groups || [];
      const main = asset.main || {{}};
      if (!groups.length || !(main.series || []).length) {{
        figureEl.innerHTML = '<div class="panelEmptyState">Arbre KPI incomplet.</div>';
        return false;
      }}
      figureEl.className = "factoryPlotFigure factoryKpiTreePanel";
      figureEl.style.display = "block";
      figureEl.innerHTML = `
        <div class="kpiTreePanel">
          <div class="kpiTreeHeader">
            <div>
              <div class="kpiTreeTitle">${{asset.title || "Arborescence KPI"}}</div>
              <div class="kpiTreeSubtitle">Question metier: comment les KPI se degradent-ils ensemble dans le temps ? Lecture: performance globale, contributions et ecarts aux cibles.</div>
              <div class="kpiTreeSubtitle">Fenetre: ${{selectedTimelineWindowLabel()}}</div>
            </div>
            <div class="kpiTreeControls">
              <span class="kpiTreeControlGroup">
                <span>Lissage</span>
                <button type="button" class="kpiTreeSmoothBtn" data-smooth="none">Sans</button>
                <button type="button" class="kpiTreeSmoothBtn" data-smooth="week">7 j</button>
                <button type="button" class="kpiTreeSmoothBtn active" data-smooth="month">30 j</button>
              </span>
            </div>
          </div>
          <div class="kpiTreeViewTabs">
            <button type="button" class="kpiTreeViewBtn active" data-kpi-view="graphs">Graphes</button>
            <button type="button" class="kpiTreeViewBtn" data-kpi-view="formulas">Formules</button>
            <button type="button" class="kpiTreeViewBtn" data-kpi-view="physics">Physics of Decision</button>
          </div>
          <div class="kpiTreeView kpiTreeGraphView active">
            <div class="kpiTreeCards"></div>
            <div class="kpiTreeChart kpiTreeMainChart"></div>
            <div class="kpiTreeDetail">
              <div class="kpiTreeSummary"></div>
              <div class="kpiTreeChart kpiTreeSecondaryChart"></div>
            </div>
          </div>
          <div class="kpiTreeView kpiTreeFormulaView">
            <div class="kpiFormulaIntro">
              Tableau de reference des KPI. Objectif atelier: valider les definitions, les seuils metier et les donnees manquantes avant de recalibrer le modele.
            </div>
            <details class="sensitivityDetails">
              <summary>Glossaire KPI atelier</summary>
              <div class="kpiFormulaIntro">
                <b>Disponibilite produit</b>: part de la demande servie et capacite a tenir le besoin produit dans le temps. <b>Backlog</b>: demande non servie restante.
                <b>Adherence ligne</b>: stabilite entre plan et execution industrielle. <b>Cout stock</b>: cout ou estimation de cout d'immobilisation. <b>Signal MP usine zero</b>: diagnostic technique dans nos stocks usine, pas rupture client ni rupture fournisseur.
                <b>Retard matiere</b>: ecart arrivee effective moins arrivee prevue. <b>Sensibilite</b>: effet observe quand on stresse un parametre. <b>Criticite fournisseur</b>: score de decision, pas probabilite historique.
                <b>Incertitude</b>: confiance dans la lecture, pas danger fournisseur.
              </div>
            </details>
            <div class="kpiFormulaTableWrap">
              <table class="kpiFormulaTable">
                <thead>
                  <tr>
                    <th>Famille</th>
                    <th>Niveau</th>
                    <th>KPI</th>
                    <th>Formule</th>
                    <th>Definition / lecture</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
          <div class="kpiTreeView kpiTreePhysicsView">
            <div class="kpiFormulaIntro">
              Surcouche independante inspiree de la Physics of Decision: chaque KPI est converti en distance normalisee a sa cible, puis les distances sont agregees par norme euclidienne ponderee.
            </div>
            <div class="kpiPhysicsGrid">
              <div class="kpiPhysicsStack">
                <div class="kpiTreeSummary kpiPhysicsSummary"></div>
                <div class="kpiTreeChart kpiPhysicsContributionChart"></div>
              </div>
              <div class="kpiPhysicsStack">
                <div class="kpiTreeChart kpiPhysicsScoreChart"></div>
                <div class="kpiTreeChart kpiPhysicsDistanceChart"></div>
              </div>
            </div>
          </div>
        </div>
      `;
      const cardsEl = figureEl.querySelector(".kpiTreeCards");
      const mainChartEl = figureEl.querySelector(".kpiTreeMainChart");
      const summaryEl = figureEl.querySelector(".kpiTreeSummary");
      const secondaryChartEl = figureEl.querySelector(".kpiTreeSecondaryChart");
      const graphViewEl = figureEl.querySelector(".kpiTreeGraphView");
      const formulaViewEl = figureEl.querySelector(".kpiTreeFormulaView");
      const physicsViewEl = figureEl.querySelector(".kpiTreePhysicsView");
      const formulaBodyEl = figureEl.querySelector(".kpiFormulaTable tbody");
      const physicsSummaryEl = figureEl.querySelector(".kpiPhysicsSummary");
      const physicsScoreChartEl = figureEl.querySelector(".kpiPhysicsScoreChart");
      const physicsDistanceChartEl = figureEl.querySelector(".kpiPhysicsDistanceChart");
      const physicsContributionChartEl = figureEl.querySelector(".kpiPhysicsContributionChart");
      const viewButtons = Array.from(figureEl.querySelectorAll("[data-kpi-view]"));
      const smoothButtons = Array.from(figureEl.querySelectorAll(".kpiTreeSmoothBtn"));
      let selectedId = globalKpiTreeState.selectedId && groups.some(group => group.id === globalKpiTreeState.selectedId)
        ? globalKpiTreeState.selectedId
        : groups[0].id;
      let smoothingMode = globalKpiTreeState.smoothingMode || "month";
      let viewMode = globalKpiTreeState.viewMode || "graphs";

      function groupById(groupId) {{
        return groups.find(group => group.id === groupId) || groups[0];
      }}
      function escapeKpiHtml(value) {{
        return String(value ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }}
      function renderFormulaTable() {{
        if (!formulaBodyEl) return;
        const definitions = asset.definitions || [];
        formulaBodyEl.innerHTML = definitions.map(row => `
          <tr>
            <td><span class="kpiFormulaFamily">${{escapeKpiHtml(row.family || "")}}</span></td>
            <td><span class="kpiFormulaLevel">${{escapeKpiHtml(row.level || "")}}</span></td>
            <td>${{escapeKpiHtml(row.name || "")}}</td>
            <td>
              <div>${{escapeKpiHtml(row.formula || "")}}</div>
              ${{row.terms ? `<div class="kpiFormulaTerms"><span class="kpiFormulaTermsLabel">Termes:</span> ${{escapeKpiHtml(row.terms)}}</div>` : ""}}
            </td>
            <td>${{escapeKpiHtml(row.interpretation || "")}}</td>
          </tr>
        `).join("") || '<tr><td colspan="5">Definitions KPI non disponibles.</td></tr>';
      }}
      function renderKpiView() {{
        viewButtons.forEach(btn => btn.classList.toggle("active", (btn.dataset.kpiView || "graphs") === viewMode));
        if (graphViewEl) graphViewEl.classList.toggle("active", viewMode === "graphs");
        if (formulaViewEl) formulaViewEl.classList.toggle("active", viewMode === "formulas");
        if (physicsViewEl) physicsViewEl.classList.toggle("active", viewMode === "physics");
        if (viewMode === "graphs") {{
          renderMain();
          renderSecondary();
        }} else if (viewMode === "formulas") {{
          renderFormulaTable();
        }} else {{
          renderPhysicsView();
        }}
      }}
      function smoothingWindow() {{
        if (smoothingMode === "week") return 7;
        if (smoothingMode === "month") return 30;
        return 1;
      }}
      function smoothingSuffix() {{
        if (smoothingMode === "week") return " - moy. 7 j";
        if (smoothingMode === "month") return " - moy. 30 j";
        return "";
      }}
      function startupCutoffDay() {{
        return null;
      }}
      function startupSuffix() {{
        return "";
      }}
      function smoothValues(values) {{
        const windowSize = smoothingWindow();
        const numeric = (values || []).map(value => {{
          const num = Number(value);
          return Number.isFinite(num) ? num : 0;
        }});
        if (windowSize <= 1) return numeric;
        return numeric.map((_, idx) => {{
          const start = Math.max(0, idx - windowSize + 1);
          const slice = numeric.slice(start, idx + 1);
          const sum = slice.reduce((acc, value) => acc + value, 0);
          return slice.length ? sum / slice.length : 0;
        }});
      }}
      function filterStartupAndTimeline(days, values) {{
        const cutoff = startupCutoffDay();
        const filteredDays = [];
        const filteredValues = [];
        (days || []).forEach((day, idx) => {{
          const dayNum = Number(day);
          if (cutoff !== null && Number.isFinite(dayNum) && dayNum < cutoff) return;
          filteredDays.push(day);
          filteredValues.push((values || [])[idx] ?? 0);
        }});
        return filterSeriesByTimeline(filteredDays, filteredValues, true);
      }}
      function finiteValues(values) {{
        return (values || [])
          .map(value => Number(value))
          .filter(value => Number.isFinite(value));
      }}
      function sumValues(values) {{
        return finiteValues(values).reduce((acc, value) => acc + value, 0);
      }}
      function averageValues(values) {{
        const numeric = finiteValues(values);
        return numeric.length ? numeric.reduce((acc, value) => acc + value, 0) / numeric.length : 0;
      }}
      function maxValue(values) {{
        const numeric = finiteValues(values);
        return numeric.length ? Math.max(...numeric) : 0;
      }}
      function countPositive(values) {{
        return finiteValues(values).filter(value => value > 1e-9).length;
      }}
      function pctText(value) {{
        return `${{fmtPanelQty(value, 1)}}%`;
      }}
      function qtyText(value, digits = 1) {{
        return fmtPanelQty(value, digits);
      }}
      function findSeries(seriesList, expectedLabel) {{
        const expected = String(expectedLabel || "").toLowerCase();
        return (seriesList || []).find(series => String(series.label || "").toLowerCase() === expected) || null;
      }}
      function traceHasVisibleData(trace) {{
        const x = trace && Array.isArray(trace.x) ? trace.x : [];
        const y = trace && Array.isArray(trace.y) ? trace.y : [];
        if (!x.length || !y.length) return false;
        return y.some(value => Number.isFinite(Number(value)));
      }}
      function purgeKpiPlot(targetEl) {{
        if (!window.Plotly || !targetEl) return;
        try {{ Plotly.purge(targetEl); }} catch (e) {{}}
      }}
      function renderKpiPlotOrEmpty(targetEl, traces, layout, config, emptyMessage) {{
        if (!targetEl) return false;
        const hasData = (traces || []).some(traceHasVisibleData);
        if (!hasData) {{
          purgeKpiPlot(targetEl);
          targetEl.innerHTML = `<div class="kpiTreeEmptyChart">${{escapeKpiHtml(emptyMessage || "Aucune donnee disponible dans la fenetre selectionnee.")}}</div>`;
          return false;
        }}
        if (targetEl.querySelector && targetEl.querySelector(".kpiTreeEmptyChart")) {{
          targetEl.innerHTML = "";
        }}
        installCtrlScrollZoomGate(targetEl);
        Plotly.react(targetEl, traces, layout, config);
        return true;
      }}
      function groupDataMeta(group) {{
        const series = group.secondary || [];
        const seriesCount = series.length;
        const maxPoints = Math.max(0, ...series.map(row => (row.values || []).length));
        if (group.id === "cost") {{
          const totalRow = (group.summary || []).find(row => String(row.label || "").toLowerCase() === "cout operationnel total");
          if (totalRow && totalRow.value) return `Total: ${{totalRow.value}} - ${{seriesCount}} courbes - ${{maxPoints}} jours`;
        }}
        const firstSummary = (group.summary || [])[0] || null;
        if (firstSummary && firstSummary.label && firstSummary.value) {{
          return `${{firstSummary.label}}: ${{firstSummary.value}}`;
        }}
        return `${{seriesCount}} courbes - ${{maxPoints}} jours`;
      }}
      function seriesWindowValues(series, smooth = false) {{
        if (!series) return [];
        const values = smooth ? smoothValues(series.values || []) : (series.values || []);
        return filterStartupAndTimeline(series.days || [], values).values;
      }}
      function seriesWindowValuesByPrefix(seriesList, prefix, smooth = false) {{
        const expected = String(prefix || "").toLowerCase();
        return (seriesList || [])
          .filter(series => String(series.label || "").toLowerCase().startsWith(expected))
          .flatMap(series => seriesWindowValues(series, smooth));
      }}
      function summaryEntry(label, value) {{
        return {{ label, value }};
      }}
      function buildWindowSummary(group) {{
        const secondary = group.secondary || [];
        if (group.id === "availability") {{
          const demand = seriesWindowValues(findSeries(secondary, "Demande"));
          const required = seriesWindowValues(findSeries(secondary, "Besoin avec backlog"));
          const served = seriesWindowValues(findSeries(secondary, "Servi"));
          const backlog = seriesWindowValues(findSeries(secondary, "Backlog fin de jour"));
          const totalDemand = sumValues(demand);
          const totalRequired = sumValues(required);
          const totalServed = sumValues(served);
          return [
            summaryEntry("Fenetre", selectedTimelineWindowLabel()),
            summaryEntry("Disponibilite produit cumulee", pctText(totalDemand ? 100 * totalServed / totalDemand : 100)),
            summaryEntry("Disponibilite besoin+backlog", pctText(totalRequired ? 100 * totalServed / totalRequired : 100)),
            summaryEntry("Jours avec backlog", String(countPositive(backlog))),
            summaryEntry("Backlog max", qtyText(maxValue(backlog), 1)),
            summaryEntry("Besoin cumule", qtyText(totalRequired, 1)),
          ];
        }}
        if (group.id === "production") {{
          return [
            summaryEntry("Fenetre", selectedTimelineWindowLabel()),
            summaryEntry("Adherence lignes mensuelle", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Adherence lignes mensuelle (%)"), true)))),
            summaryEntry("Adherence plan lotifie", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Adherence plan lotifie mensuelle (%)"), true)))),
            summaryEntry("Couverture demande horizon 30j", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Couverture demande horizon 30j (%)"), true)))),
            summaryEntry("Rattrapage retard net 30j", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Taux de rattrapage retard net 30j (%)"), true)))),
            summaryEntry("Retard/deficit moyen lignes", pctText(averageValues(seriesWindowValuesByPrefix(secondary, "Retard/deficit production", true)))),
            summaryEntry("Avance/exces moyen lignes", pctText(averageValues(seriesWindowValuesByPrefix(secondary, "Avance/exces production", true)))),
            summaryEntry("Contraintes sur ligne", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Contraintes sur ligne capacite / input / lots semaine (%)"), true)))),
          ];
        }}
        if (group.id === "cost") {{
          const total = sumValues(seriesWindowValues(findSeries(secondary, "Cout operationnel total")));
          const purchase = sumValues(seriesWindowValues(findSeries(secondary, "Cout d'achat matiere")));
          const production = sumValues(seriesWindowValues(findSeries(secondary, "Cout de production")));
          const inventory = sumValues(seriesWindowValues(findSeries(secondary, "Cout stock")));
          const transport = sumValues(seriesWindowValues(findSeries(secondary, "Cout de transport pilotable")));
          const share = (value) => total > 1e-9 ? pctText(100 * value / total) : "0,0%";
          return [
            summaryEntry("Fenetre", selectedTimelineWindowLabel()),
            summaryEntry("Cout operationnel total", qtyText(total, 1)),
            summaryEntry("Cout d'achat matiere", `${{qtyText(purchase, 1)}} (${{share(purchase)}})`),
            summaryEntry("Cout de production", `${{qtyText(production, 1)}} (${{share(production)}})`),
            summaryEntry("Cout stock", `${{qtyText(inventory, 1)}} (${{share(inventory)}})`),
            summaryEntry("Cout de transport pilotable", `${{qtyText(transport, 1)}} (${{share(transport)}})`),
          ];
        }}
        return group.summary || [];
      }}
      function physicsWindowValues(values, smooth = true) {{
        const physics = asset.physics || {{}};
        const sourceValues = smooth ? smoothValues(values || []) : (values || []);
        return filterPhysicsSeriesByTimeline(physics.days || [], sourceValues).values;
      }}
      function physicsWindowDays(values, smooth = true) {{
        const physics = asset.physics || {{}};
        const sourceValues = smooth ? smoothValues(values || []) : (values || []);
        return filterPhysicsSeriesByTimeline(physics.days || [], sourceValues).days;
      }}
      function filterPhysicsSeriesByTimeline(days, values) {{
        const physics = asset.physics || {{}};
        const cutoff = Number(physics.startup_cutoff_day);
        const shouldFilterStartup = Number.isFinite(cutoff) && cutoff > 0;
        const filteredDays = [];
        const filteredValues = [];
        (days || []).forEach((day, idx) => {{
          const dayNum = Number(day);
          if (shouldFilterStartup && Number.isFinite(dayNum) && dayNum < cutoff) return;
          filteredDays.push(day);
          filteredValues.push((values || [])[idx] ?? 0);
        }});
        return filterSeriesByTimeline(filteredDays, filteredValues, true);
      }}
      function renderPhysicsSummary(physics) {{
        if (!physicsSummaryEl) return;
        const scoreSeries = ((physics.main || {{}}).series || []).find(series => series.id === "global_score") || null;
        const scoreValues = scoreSeries ? physicsWindowValues(scoreSeries.values || [], true) : [];
        const impactRows = (physics.weighted_term_series || []).map(series => {{
          const values = physicsWindowValues(series.values || [], false);
          return {{
            label: series.label || series.id,
            total: sumValues(values),
          }};
        }}).sort((a, b) => b.total - a.total);
        const totalImpact = impactRows.reduce((acc, row) => acc + row.total, 0);
        const summaryRows = [
          summaryEntry("Fenetre", selectedTimelineWindowLabel()),
          summaryEntry("Jours exclus", Number.isFinite(Number(physics.startup_cutoff_day)) && Number(physics.startup_cutoff_day) > 0 ? `J0 -> J${{Number(physics.startup_cutoff_day) - 1}}` : "aucun"),
          summaryEntry("Score derive moyen", averageValues(scoreValues).toFixed(3)),
          summaryEntry("Score derive max", maxValue(scoreValues).toFixed(3)),
          summaryEntry("Lecture", "0=cible ; 1=catastrophe"),
          summaryEntry("CSV derive", physics.csv_path ? String(physics.csv_path).split(/[\\\\/]/).pop() : "n/a"),
        ];
        impactRows.slice(0, 5).forEach((row, idx) => {{
          const share = totalImpact > 1e-12 ? 100 * row.total / totalImpact : 0;
          summaryRows.push(summaryEntry(`Impact ${{idx + 1}}`, `${{row.label}} - ${{fmtPanelQty(share, 1)}}% cumule`));
        }});
        physicsSummaryEl.innerHTML = "";
        summaryRows.forEach(row => {{
          const div = document.createElement("div");
          div.className = "kpiTreeSummaryRow";
          div.innerHTML = `<span class="kpiTreeSummaryLabel">${{row.label || ""}}</span><span class="kpiTreeSummaryValue">${{row.value || ""}}</span>`;
          physicsSummaryEl.appendChild(div);
        }});
      }}
      function renderPhysicsChart(targetEl, seriesList, title, yLabel, yRange = null) {{
        if (!targetEl) return;
        const palette = ["#111827", "#0f766e", "#2563eb", "#d97706", "#7c3aed", "#dc2626", "#0891b2", "#be123c"];
        const traces = (seriesList || []).map((series, idx) => {{
          const values = smoothValues(series.values || []);
          const filtered = filterPhysicsSeriesByTimeline((asset.physics || {{}}).days || [], values);
          return {{
            type: "scatter",
            mode: "lines",
            name: `${{series.label || series.id}}${{smoothingSuffix()}}`,
            x: filtered.days,
            y: filtered.values,
            line: {{
              width: idx === 0 ? 2.8 : 2.0,
              color: series.color || palette[idx % palette.length],
              dash: series.dash || "solid",
            }},
            hovertemplate: `${{series.label || series.id}}<br>Jour=%{{x}}<br>Valeur=%{{y:.3f}}<extra></extra>`,
          }};
        }});
        const layout = {{
          title: {{ text: `${{title}} (${{selectedTimelineWindowLabel()}})`, font: {{ size: 12 }} }},
          margin: {{ l: 58, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout("Jour"),
          yaxis: {{ title: yLabel, gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.25 }},
        }};
        if (Array.isArray(yRange)) {{
          layout.yaxis.range = yRange;
        }}
        installCtrlScrollZoomGate(targetEl);
        Plotly.react(targetEl, traces, layout, PLOTLY_RESPONSIVE_CONFIG);
      }}
      function renderPhysicsView() {{
        const physics = asset.physics || null;
        if (!physics || physics.kind !== "physics_kpi") {{
          if (physicsSummaryEl) physicsSummaryEl.innerHTML = '<div class="panelEmptyState">Vue Physics of Decision non disponible pour ce run.</div>';
          return;
        }}
        renderPhysicsSummary(physics);
        renderPhysicsChart(
          physicsScoreChartEl,
          ((physics.main || {{}}).series || []),
          "Trajectoire du score global",
          "Score 0 cible / 1 catastrophe",
          [0, 1]
        );
        renderPhysicsChart(
          physicsDistanceChartEl,
          physics.distance_series || [],
          "Distances normalisees par KPI",
          "Distance normalisee",
          [0, 1]
        );
        renderPhysicsChart(
          physicsContributionChartEl,
          physics.contribution_series || [],
          "Parts journalieres de derive",
          "Contribution (%)",
          [0, 100]
        );
      }}
      function syncSmoothingButtons() {{
        smoothButtons.filter(btn => btn.dataset.smooth).forEach(btn => {{
          btn.classList.toggle("active", (btn.dataset.smooth || "none") === smoothingMode);
        }});
      }}
      function bindSmoothingControls() {{
        viewButtons.forEach(btn => {{
          btn.onclick = () => {{
            viewMode = btn.dataset.kpiView || "graphs";
            globalKpiTreeState.viewMode = viewMode;
            renderKpiView();
          }};
        }});
        smoothButtons.filter(btn => btn.dataset.smooth).forEach(btn => {{
          btn.onclick = () => {{
            smoothingMode = btn.dataset.smooth || "none";
            globalKpiTreeState.smoothingMode = smoothingMode;
            syncSmoothingButtons();
            if (viewMode === "physics") {{
              renderPhysicsView();
            }} else {{
              renderMain();
              renderSecondary();
            }}
          }};
        }});
        syncSmoothingButtons();
      }}
      function renderCards() {{
        cardsEl.innerHTML = "";
        groups.forEach(group => {{
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = group.id === selectedId ? "kpiTreeCard active" : "kpiTreeCard";
          btn.innerHTML = `
            <div class="kpiTreeCardTitle">${{group.label || group.id}}</div>
            <div class="kpiTreeCardObjective">${{group.objective || ""}}</div>
            <div class="kpiTreeCardMeta">${{escapeKpiHtml(groupDataMeta(group))}}</div>
          `;
          btn.onclick = () => {{
            selectedId = group.id;
            globalKpiTreeState.selectedId = selectedId;
            renderCards();
            renderSecondary();
          }};
          cardsEl.appendChild(btn);
        }});
      }}
      function renderMain() {{
        const palette = ["#0f766e", "#2563eb", "#d97706"];
        const traces = (main.series || []).map((series, idx) => {{
          const values = smoothValues(series.values || []);
          const filtered = filterStartupAndTimeline(main.days || [], values);
          const label = `${{series.label || series.id}}${{smoothingSuffix()}}${{startupSuffix()}}`;
          return {{
            type: "scatter",
            mode: "lines",
            name: label,
            x: filtered.days,
            y: filtered.values,
            customdata: (filtered.days || []).map(() => series.id),
            line: {{ width: 2.6, color: series.color || palette[idx % palette.length] }},
            hovertemplate: `${{label}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
          }};
        }});
        const mainRendered = renderKpiPlotOrEmpty(mainChartEl, traces, {{
            title: {{ text: `KPI principaux - vue management (${{selectedTimelineWindowLabel()}})`, font: {{ size: 12 }} }},
          margin: {{ l: 54, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout("Jour"),
          yaxis: {{ title: main.y_label || "Score / indice", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.22 }},
        }}, PLOTLY_RESPONSIVE_CONFIG, "Aucun KPI principal disponible dans la fenetre selectionnee.");
        if (!mainRendered || !mainChartEl.on) return;
        mainChartEl.on("plotly_click", (ev) => {{
          const point = ev && ev.points && ev.points[0];
          const groupId = point && point.customdata;
          if (groupId) {{
            selectedId = groupId;
            globalKpiTreeState.selectedId = selectedId;
            renderCards();
            renderSecondary();
          }}
        }});
      }}
      function renderSecondary() {{
        const group = groupById(selectedId);
        summaryEl.innerHTML = "";
        buildWindowSummary(group).forEach(row => {{
          const div = document.createElement("div");
          div.className = "kpiTreeSummaryRow";
          div.innerHTML = `<span class="kpiTreeSummaryLabel">${{row.label || ""}}</span><span class="kpiTreeSummaryValue">${{row.value || ""}}</span>`;
          summaryEl.appendChild(div);
        }});
        const traces = (group.secondary || []).map(series => {{
          const values = smoothValues(series.values || []);
          const filtered = filterStartupAndTimeline(series.days || [], values);
          const label = `${{series.label || "KPI secondaire"}}${{smoothingSuffix()}}${{startupSuffix()}}`;
          return {{
            type: "scatter",
            mode: "lines",
            name: label,
            x: filtered.days,
            y: filtered.values,
            line: {{ width: 2.2, color: series.color || "#2563eb", dash: series.dash || "solid" }},
          }};
        }});
        renderKpiPlotOrEmpty(secondaryChartEl, traces, {{
          title: {{ text: `KPI secondaires - ${{group.label || selectedId}} (${{selectedTimelineWindowLabel()}})`, font: {{ size: 12 }} }},
          margin: {{ l: 58, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout("Jour"),
          yaxis: {{ title: group.secondary_y_label || "Valeur", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.24 }},
        }}, PLOTLY_RESPONSIVE_CONFIG, `Aucune courbe secondaire disponible pour ${{group.label || selectedId}} dans la fenetre selectionnee.`);
      }}
      bindSmoothingControls();
      renderCards();
      renderFormulaTable();
      renderKpiView();
      return true;
    }}

    function renderGlobalKpiTreeIfVisible() {{
      const modal = document.getElementById("kpiTreeModal");
      if (modal && modal.classList.contains("visible")) {{
        renderGlobalKpiTree();
      }}
    }}

    function renderSimulatedRiskGlobalIfVisible() {{
      const modal = document.getElementById("simulatedRiskGlobalModal");
      if (modal && modal.classList.contains("visible")) {{
        renderSimulatedRiskGlobalDiagnostic();
      }}
    }}

    function renderScenarioComparisonIfVisible() {{
      const modal = document.getElementById("scenarioComparisonModal");
      if (modal && modal.classList.contains("visible")) {{
        renderScenarioComparison();
      }}
    }}

    function initRiskTooltipPortal() {{
      let tooltip = document.getElementById("riskTooltipPortal");
      if (!tooltip) {{
        tooltip = document.createElement("div");
        tooltip.id = "riskTooltipPortal";
        tooltip.className = "riskTooltipPortal";
        tooltip.setAttribute("role", "tooltip");
        document.body.appendChild(tooltip);
      }}
      let activeHost = null;
      const margin = 10;
      const gap = 12;

      function hideTooltip() {{
        activeHost = null;
        tooltip.classList.remove("visible");
        tooltip.textContent = "";
      }}

      function positionTooltip(host, ev) {{
        if (!host || !tooltip.textContent) return;
        const rect = host.getBoundingClientRect();
        const maxWidth = Math.max(220, Math.min(420, window.innerWidth - margin * 2));
        tooltip.style.width = `${{maxWidth}}px`;
        tooltip.style.left = "-9999px";
        tooltip.style.top = "-9999px";
        const tooltipRect = tooltip.getBoundingClientRect();
        const pointerX = ev && Number.isFinite(ev.clientX) ? ev.clientX : rect.left + Math.min(24, rect.width / 2);
        const pointerY = ev && Number.isFinite(ev.clientY) ? ev.clientY : rect.top;
        let left = pointerX + gap;
        let top = pointerY + gap;
        if (left + tooltipRect.width > window.innerWidth - margin) {{
          left = pointerX - tooltipRect.width - gap;
        }}
        if (top + tooltipRect.height > window.innerHeight - margin) {{
          top = pointerY - tooltipRect.height - gap;
        }}
        if (top < margin) {{
          top = Math.min(window.innerHeight - tooltipRect.height - margin, rect.bottom + gap);
        }}
        left = clamp(left, margin, Math.max(margin, window.innerWidth - tooltipRect.width - margin));
        top = clamp(top, margin, Math.max(margin, window.innerHeight - tooltipRect.height - margin));
        tooltip.style.left = `${{left}}px`;
        tooltip.style.top = `${{top}}px`;
      }}

      function showTooltip(host, ev) {{
        const text = host && host.getAttribute("data-tooltip");
        if (!text) {{
          hideTooltip();
          return;
        }}
        activeHost = host;
        tooltip.textContent = text;
        tooltip.classList.add("visible");
        positionTooltip(host, ev || null);
      }}

      document.addEventListener("mouseover", (ev) => {{
        const host = ev.target && ev.target.closest ? ev.target.closest(".riskTooltipHost[data-tooltip]") : null;
        if (!host || host === activeHost) return;
        showTooltip(host, ev);
      }});
      document.addEventListener("mousemove", (ev) => {{
        if (!activeHost) return;
        positionTooltip(activeHost, ev);
      }});
      document.addEventListener("mouseout", (ev) => {{
        if (!activeHost) return;
        const related = ev.relatedTarget;
        if (related && activeHost.contains(related)) return;
        hideTooltip();
      }});
      document.addEventListener("focusin", (ev) => {{
        const host = ev.target && ev.target.closest ? ev.target.closest(".riskTooltipHost[data-tooltip]") : null;
        if (host) showTooltip(host, null);
      }});
      document.addEventListener("focusout", (ev) => {{
        if (activeHost && ev.target && activeHost.contains(ev.target)) hideTooltip();
      }});
      document.addEventListener("keydown", (ev) => {{
        if (ev.key === "Escape") hideTooltip();
      }});
      window.addEventListener("resize", hideTooltip);
      window.addEventListener("scroll", () => {{
        if (activeHost) positionTooltip(activeHost, null);
      }}, true);
    }}

    function renderGlobalSensitivityTop3() {{
      const content = document.getElementById("sensitivityTop3Content");
      if (!content) return false;
      const title = document.getElementById("sensitivityTop3ModalTitle");
      const meta = document.getElementById("sensitivityTop3ModalMeta");
      if (title) title.textContent = "Sensibilite - Priorites KPI";
      if (meta) meta.textContent = "Disponibilite produit, taux de replanification et cout de stockage";
      const asset = (SUPPLIER_PARAMETER_SENSITIVITY_NODES || {{}})._global_top3 || null;
      if (asset && asset.html) {{
        content.innerHTML = asset.html;
        return true;
      }}
      content.innerHTML = '<div class="panelEmptyState">Aucune priorite KPI de sensibilite disponible pour ce run.</div>';
      return false;
    }}

    function escapeHtmlText(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }}[ch] || ch));
    }}

    function scenarioTubePercentile(values, pct) {{
      const nums = (values || []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
      if (!nums.length) return null;
      if (nums.length === 1) return nums[0];
      const pos = (nums.length - 1) * pct;
      const lo = Math.floor(pos);
      const hi = Math.ceil(pos);
      if (lo === hi) return nums[lo];
      return nums[lo] + (nums[hi] - nums[lo]) * (pos - lo);
    }}

    function scenarioTubeSeriesMap(series) {{
      const map = new Map();
      const days = Array.isArray(series.days) ? series.days : [];
      const values = Array.isArray(series.values) ? series.values : [];
      days.forEach((dayRaw, idx) => {{
        const day = Number(dayRaw);
        const value = Number(values[idx]);
        if (!Number.isFinite(day) || !Number.isFinite(value)) return;
        const key = Math.round(day);
        const previous = map.has(key) ? Number(map.get(key)) : null;
        if (previous === null || Math.abs(value) > Math.abs(previous)) {{
          map.set(key, value);
        }}
      }});
      return map;
    }}

    function buildScenarioTubePlotlyFigure(figure, palette) {{
      const rawSeries = Array.isArray(figure.series) ? figure.series : [];
      if (!rawSeries.length) return null;
      const seriesMaps = rawSeries.map(series => ({{ series, valuesByDay: scenarioTubeSeriesMap(series) }}));
      const daySet = new Set();
      seriesMaps.forEach(item => item.valuesByDay.forEach((_value, day) => daySet.add(day)));
      let days = [...daySet].filter(Number.isFinite).sort((a, b) => a - b);
      if (!days.length) return null;
      const minDay = Math.min(...days);
      const maxDay = Math.max(...days);
      const preserveSparseDays = Boolean(figure.preserve_sparse_days) ||
        (Array.isArray(figure.fan_band_days) && figure.fan_band_days.length > 0);
      if (!preserveSparseDays && maxDay - minDay <= 5000) {{
        days = [];
        for (let day = minDay; day <= maxDay; day += 1) days.push(day);
      }}
      const median = [];
      let medianDays = days;
      const zeroFloorTube = Boolean(figure.tube_zero_floor);
      const upperPctRaw = Number(figure.tube_upper_percentile);
      const upperPct = Number.isFinite(upperPctRaw) ? Math.max(0, Math.min(1, upperPctRaw)) : 0.90;
      const valuesByDay = [];
      days.forEach(day => {{
        const vals = seriesMaps.map(item => Number(item.valuesByDay.get(day) || 0)).filter(Number.isFinite);
        valuesByDay.push(vals);
        median.push(scenarioTubePercentile(vals, 0.50));
      }});
      const traces = [];
      const fanBandsEnabled = Boolean(figure.fan_bands);
      if (fanBandsEnabled) {{
        const precomputedBandDays = Array.isArray(figure.fan_band_days) && figure.fan_band_days.length
          ? figure.fan_band_days.map(Number).filter(Number.isFinite)
          : [];
        const precomputedBands = Array.isArray(figure.fan_band_values)
          ? figure.fan_band_values.filter(band => Array.isArray(band.low) && Array.isArray(band.high) && band.low.length && band.high.length)
          : [];
        const rawBands = Array.isArray(figure.fan_band_percentiles) && figure.fan_band_percentiles.length
          ? figure.fan_band_percentiles
          : [[0.05, 0.95], [0.10, 0.90], [0.25, 0.75]];
        const fanColors = Array.isArray(figure.fan_band_colors) && figure.fan_band_colors.length
          ? figure.fan_band_colors
          : ["rgba(15,118,110,0.06)", "rgba(15,118,110,0.10)", "rgba(15,118,110,0.18)"];
        const bands = precomputedBands.length
          ? precomputedBands.map((band, idx) => ({{
              precomputed: true,
              label: band.label || `zone ${{idx + 1}}`,
              x: precomputedBandDays.length ? precomputedBandDays : days,
              low: band.low.map(Number),
              high: band.high.map(Number),
            }}))
          : rawBands
              .map(pair => {{
                const lo = Math.max(0, Math.min(1, Number((pair || [])[0])));
                const hi = Math.max(0, Math.min(1, Number((pair || [])[1])));
                return {{ lo, hi }};
              }})
              .filter(band => Number.isFinite(band.lo) && Number.isFinite(band.hi) && band.hi > band.lo)
              .sort((a, b) => (b.hi - b.lo) - (a.hi - a.lo));
        bands.forEach((band, idx) => {{
          const bandX = band.precomputed ? band.x : days;
          const bandLow = band.precomputed ? band.low : valuesByDay.map(vals => scenarioTubePercentile(vals, band.lo));
          const bandHigh = band.precomputed ? band.high : valuesByDay.map(vals => scenarioTubePercentile(vals, band.hi));
          const pctLabel = band.precomputed ? band.label : `${{Math.round(band.lo * 100)}}-${{Math.round(band.hi * 100)}}%`;
          traces.push({{
            type: "scatter",
            mode: "lines",
            name: `borne basse ${{pctLabel}}`,
            x: bandX,
            y: bandLow,
            line: {{ width: 0, color: "rgba(15,118,110,0)" }},
            hoverinfo: "skip",
            showlegend: false,
            legendgroup: `fan-${{idx}}`,
          }});
          traces.push({{
            type: "scatter",
            mode: "lines",
            name: `${{figure.tube_label || "Zone incertitude"}} ${{pctLabel}}`,
            x: bandX,
            y: bandHigh,
            fill: "tonexty",
            fillcolor: fanColors[Math.min(idx, fanColors.length - 1)],
            line: {{ width: 0, color: "rgba(15,118,110,0)" }},
            hovertemplate: `${{pctLabel}}<br>Jour=%{{x}}<br>Borne haute=%{{y:.2f}}<extra></extra>`,
            legendgroup: `fan-${{idx}}`,
          }});
        }});
        if (Array.isArray(figure.fan_median_values) && figure.fan_median_values.length) {{
          median.splice(0, median.length, ...figure.fan_median_values.map(Number));
          if (precomputedBandDays.length) medianDays = precomputedBandDays;
        }}
      }} else {{
        const low = valuesByDay.map(vals => zeroFloorTube ? 0 : scenarioTubePercentile(vals, 0.10));
        const high = valuesByDay.map(vals => scenarioTubePercentile(vals, upperPct));
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: "borne basse",
          x: days,
          y: low,
          line: {{ width: 0, color: "rgba(37,99,235,0)" }},
          hoverinfo: "skip",
          showlegend: false,
        }});
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: figure.tube_label || "Enveloppe scenarios",
          x: days,
          y: high,
          fill: "tonexty",
          fillcolor: "rgba(37,99,235,0.16)",
          line: {{ width: 0, color: "rgba(37,99,235,0)" }},
          hovertemplate: "Jour=%{{x}}<br>Enveloppe haute=%{{y:.2f}}<extra></extra>",
        }});
      }}
      const namedScenarioTrajectories = Boolean(figure.named_scenario_trajectories);
      rawSeries.forEach((series, idx) => {{
        const map = seriesMaps[idx].valuesByDay;
        const y = days.map(day => {{
          const value = Number(map.get(day));
          return Number.isFinite(value) ? value : null;
        }});
        const isNominalSeries = Boolean(series.is_nominal);
        const isCurrentSeries = Boolean(series.is_current);
        const isMaxImpactSeries = Boolean(series.is_max_impact);
        const namedColor = isNominalSeries ? "#111827" : isCurrentSeries ? "#d97706" : isMaxImpactSeries ? "#be123c" : (series.color || palette[idx % palette.length]);
        const namedWidth = isNominalSeries ? 2.3 : isCurrentSeries || isMaxImpactSeries ? 2.5 : 1.7;
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: namedScenarioTrajectories ? (series.label || `Scenario ${{idx + 1}}`) : (idx === 0 ? (figure.trajectory_label || "Trajectoires scenarios") : "trajectoire scenario"),
          x: days,
          y,
          line: {{
            width: namedScenarioTrajectories ? namedWidth : (fanBandsEnabled ? 0.35 : 0.60),
            color: namedScenarioTrajectories ? namedColor : (fanBandsEnabled ? "rgba(100,116,139,0.34)" : "rgba(100,116,139,0.48)"),
            dash: namedScenarioTrajectories ? (series.dash || "solid") : "solid",
            shape: figure.step_like ? "hv" : "linear",
          }},
          opacity: namedScenarioTrajectories ? 0.92 : 1.0,
          hoverinfo: namedScenarioTrajectories ? undefined : "skip",
          hovertemplate: namedScenarioTrajectories ? `${{series.label || "Scenario"}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>` : undefined,
          showlegend: namedScenarioTrajectories ? true : idx === 0,
          legendgroup: namedScenarioTrajectories ? `scenario-${{series.scenario_id || idx}}` : "all-trajectories",
        }});
      }});
      traces.push({{
        type: "scatter",
        mode: "lines",
        name: "mediane scenarios",
        x: medianDays,
        y: median,
        line: {{
          width: 1.8,
          color: "rgba(37,99,235,0.72)",
          dash: "dot",
          shape: figure.step_like ? "hv" : "linear",
        }},
        hovertemplate: "Mediane<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>",
      }});
      const highlightSeries = namedScenarioTrajectories ? [] : rawSeries.filter(series => (
        Boolean(series.is_nominal) || Boolean(series.is_current) || Boolean(series.is_max_impact)
      ));
      highlightSeries.forEach((series) => {{
        const map = scenarioTubeSeriesMap(series);
        const y = days.map(day => {{
          const value = Number(map.get(day));
          return Number.isFinite(value) ? value : null;
        }});
        const isNominal = Boolean(series.is_nominal);
        const isCurrent = Boolean(series.is_current);
        const isMaxImpact = Boolean(series.is_max_impact);
        const color = isNominal ? "#111827" : isCurrent ? "#d97706" : isMaxImpact ? "#be123c" : (series.color || palette[0]);
        const namePrefix = isNominal ? "nominal" : isCurrent ? "run courant" : isMaxImpact ? "plus perturbateur" : "scenario";
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: `${{namePrefix}} - ${{series.label || ""}}`,
          x: days,
          y,
          line: {{
            width: isNominal ? 2.0 : (isCurrent || isMaxImpact ? 3.0 : 2.6),
            color,
            dash: isNominal ? "solid" : "solid",
            shape: figure.step_like ? "hv" : "linear",
          }},
          hovertemplate: `${{series.label || "Scenario"}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
        }});
      }});
      const shapes = [];
      const referenceValue = Number(figure.reference_line_value);
      if (Number.isFinite(referenceValue)) {{
        shapes.push({{
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          yref: "y",
          y0: referenceValue,
          y1: referenceValue,
          line: {{ color: "#2563eb", width: 1.4, dash: "dash" }},
        }});
      }}
      const annotations = figure.note ? [{{
        text: figure.note,
        xref: "paper",
        yref: "paper",
        x: 0,
        y: 1.17,
        xanchor: "left",
        yanchor: "bottom",
        showarrow: false,
        font: {{ size: 10, color: "#475569" }},
        align: "left",
      }}] : [];
      if (Number.isFinite(referenceValue) && figure.reference_line_label) {{
        annotations.push({{
          text: figure.reference_line_label,
          xref: "paper",
          yref: "y",
          x: 1,
          y: referenceValue,
          xanchor: "right",
          yanchor: "bottom",
          showarrow: false,
          font: {{ size: 10, color: "#2563eb" }},
        }});
      }}
      return {{
        data: traces,
        layout: {{
          title: {{ text: figure.title || "", font: {{ size: 12 }} }},
          margin: {{ l: 54, r: 18, t: figure.note ? 66 : 46, b: 64 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout(figure.x_label || "Jour"),
          yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0", rangemode: "tozero" }},
          legend: {{ orientation: "h", y: -0.28, font: {{ size: 10 }} }},
          shapes,
          annotations,
        }},
      }};
    }}

    function buildFactorTubePlotlyFigure(figure, palette) {{
      const days = Array.isArray(figure.days) ? figure.days.map(Number).filter(Number.isFinite) : [];
      const bands = Array.isArray(figure.bands) ? figure.bands : [];
      if (!days.length || !bands.length) return null;
      const traces = [];
      bands.forEach((band, idx) => {{
        const lineColor = band.line_color || palette[idx % palette.length];
        const fillColor = band.fillcolor || "rgba(15,118,110,0.16)";
        const lowFiltered = filterSeriesByTimeline(days, band.low || []);
        const highFiltered = filterSeriesByTimeline(days, band.high || []);
        if (!lowFiltered.days.length || !highFiltered.days.length) return;
        const label = band.label || `Input ${{idx + 1}}`;
        const aggregationLabel = band.aggregation_label || band.aggregation || "agregation de groupe";
        const inputLow = Number(band.low_input);
        const inputHigh = Number(band.high_input);
        const inputText = Number.isFinite(inputLow) && Number.isFinite(inputHigh)
          ? `input bas ${{inputLow.toFixed(2)}} / haut ${{inputHigh.toFixed(2)}}`
          : "input bas / haut";
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: `borne basse - ${{label}}`,
          x: lowFiltered.days,
          y: lowFiltered.values,
          customdata: lowFiltered.days.map(() => ({{
            factor: band.factor || "",
            label,
            family: band.family || "",
            node_id: band.node_id || "",
            highlight_node_ids: band.highlight_node_ids || [],
            line_color: lineColor,
          }})),
          line: {{ width: 0.8, color: lineColor, shape: figure.step_like ? "hv" : "linear" }},
          opacity: 0.32,
          hoverinfo: "skip",
          showlegend: false,
          legendgroup: `factor-tube-${{idx}}`,
        }});
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: label,
          x: highFiltered.days,
          y: highFiltered.values,
          customdata: highFiltered.days.map(() => ({{
            factor: band.factor || "",
            label,
            family: band.family || "",
            node_id: band.node_id || "",
            highlight_node_ids: band.highlight_node_ids || [],
            line_color: lineColor,
          }})),
          fill: "tonexty",
          fillcolor: fillColor,
          line: {{ width: 1.1, color: lineColor, shape: figure.step_like ? "hv" : "linear" }},
          opacity: 0.95,
          legendgroup: `factor-tube-${{idx}}`,
          hovertemplate: `${{label}}<br>${{aggregationLabel}}<br>${{inputText}}<br>Jour=%{{x}}<br>Borne haute=%{{y:.2f}}<extra></extra>`,
        }});
      }});
      const nominal = figure.nominal || null;
      if (nominal && Array.isArray(nominal.values) && nominal.values.length) {{
        const nominalFiltered = filterSeriesByTimeline(days, nominal.values);
        traces.push({{
          type: "scatter",
          mode: "lines",
          name: nominal.label || "Nominal",
          x: nominalFiltered.days,
          y: nominalFiltered.values,
          line: {{ width: 2.2, color: "#111827", shape: figure.step_like ? "hv" : "linear" }},
          hovertemplate: `${{nominal.label || "Nominal"}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
        }});
      }}
      return {{
        data: traces,
        layout: {{
          title: {{ text: figure.title || "", font: {{ size: 12 }} }},
          margin: {{ l: 58, r: 18, t: figure.note ? 70 : 46, b: 76 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout(figure.x_label || "Jour"),
          yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0", zerolinecolor: "#cbd5e1" }},
          legend: {{ orientation: "h", y: -0.32, font: {{ size: 10 }} }},
          annotations: figure.note ? [{{
            text: figure.note,
            xref: "paper",
            yref: "paper",
            x: 0,
            y: 1.19,
            xanchor: "left",
            yanchor: "bottom",
            showarrow: false,
            font: {{ size: 10, color: "#475569" }},
            align: "left",
          }}] : [],
        }},
      }};
    }}

    function buildSimulatedRiskDiagnosticPlotlyFigure(figure) {{
      if (!figure) return null;
      const palette = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569", "#0891b2"];
      if (figure.kind === "bar") {{
        return {{
          data: [{{
            type: "bar",
            name: figure.y_label || "Valeur",
            x: figure.labels || [],
            y: figure.values || [],
            marker: {{ color: figure.colors || palette[0] }},
            hovertemplate: "%{{x}}<br>%{{y:.2f}}<extra></extra>",
          }}],
          layout: {{
            title: {{ text: figure.title || "", font: {{ size: 12 }} }},
            margin: {{ l: 64, r: 18, t: 46, b: 92 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: "", tickangle: -18, automargin: true }},
            yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
            showlegend: false,
          }},
        }};
      }}
      if (figure.kind === "factor_tubes") {{
        return buildFactorTubePlotlyFigure(figure, palette);
      }}
      if (figure.kind !== "line_multi") return null;
      if (figure.scenario_tube) {{
        return buildScenarioTubePlotlyFigure(figure, palette);
      }}
      return {{
        data: (figure.series || []).map((series, idx) => {{
          const filtered = filterSeriesByTimeline(series.days || [], series.values || []);
          const showMarkers = Boolean(series.show_markers) || (filtered.days || []).length <= 2;
          const trace = {{
            type: "scatter",
            mode: showMarkers ? "lines+markers" : "lines",
            name: series.label || `Serie ${{idx + 1}}`,
            x: filtered.days,
            y: filtered.values,
            line: {{
              width: Number(series.width || 2.2),
              color: series.color || palette[idx % palette.length],
              dash: series.dash || "solid",
              shape: figure.step_like ? "hv" : "linear",
            }},
            hovertemplate: `${{series.label || "Serie"}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
          }};
          if (showMarkers) {{
            trace.marker = {{
              size: Number(series.marker_size || 6),
              color: series.color || palette[idx % palette.length],
            }};
          }}
          return trace;
        }}),
        layout: {{
          title: {{ text: figure.title || "", font: {{ size: 12 }} }},
          margin: {{ l: 54, r: 18, t: figure.note ? 66 : 46, b: 58 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout(figure.x_label || "Jour"),
          yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.26, font: {{ size: 10 }} }},
          annotations: figure.note ? [{{
            text: figure.note,
            xref: "paper",
            yref: "paper",
            x: 0,
            y: 1.17,
            xanchor: "left",
            yanchor: "bottom",
            showarrow: false,
            font: {{ size: 10, color: "#475569" }},
            align: "left",
          }}] : [],
        }},
      }};
    }}

    function renderDiagnosticFigureSlots(figures, slots) {{
      if (!window.Plotly || !figures) return;
      const purgeDiagnosticPlot = (node) => {{
        if (!node) return;
        const plots = node.matches && node.matches(".js-plotly-plot")
          ? [node, ...Array.from(node.querySelectorAll(".js-plotly-plot"))]
          : Array.from(node.querySelectorAll(".js-plotly-plot"));
        plots.forEach((plotNode) => {{
          try {{ Plotly.purge(plotNode); }} catch (e) {{}}
        }});
      }};
      const sizeDiagnosticLayout = (layout, targetEl) => {{
        const rect = targetEl.getBoundingClientRect();
        return {{
          ...(layout || {{}}),
          autosize: false,
          width: Math.max(320, Math.floor(rect.width || targetEl.clientWidth || 680)),
          height: Math.max(260, Math.floor(rect.height || targetEl.clientHeight || 300)),
          showlegend: (layout || {{}}).showlegend ?? true,
        }};
      }};
      slots.forEach(([key, elementId]) => {{
        const el = document.getElementById(elementId);
        if (!el) return;
        purgeDiagnosticPlot(el);
        const plotlyFigure = buildSimulatedRiskDiagnosticPlotlyFigure(figures[key] || null);
        if (!plotlyFigure) {{
          el.innerHTML = '<div class="panelEmptyState">Courbe non disponible.</div>';
          return;
        }}
        el.innerHTML = "";
        installCtrlScrollZoomGate(el);
        Plotly.react(el, plotlyFigure.data, sizeDiagnosticLayout(plotlyFigure.layout, el), PLOTLY_RESPONSIVE_CONFIG);
        if ((figures[key] || {{}}).kind === "factor_tubes") {{
          if (typeof el.removeAllListeners === "function") {{
            el.removeAllListeners("plotly_click");
          }}
          el.on("plotly_click", (ev) => {{
            const point = ev && ev.points && ev.points[0];
            const driver = point && point.customdata;
            if (driver && typeof driver === "object") {{
              selectUncertaintyDriver(driver);
            }}
          }});
        }}
      }});
    }}

    function renderSimulatedRiskGlobalDiagnosticFigures() {{
      if (!window.Plotly || !SIMULATED_RISK_GLOBAL_DIAGNOSTIC) return;
      const figures = SIMULATED_RISK_GLOBAL_DIAGNOSTIC.figures || {{}};
      const slots = [
        ["risk_intensity", "simRiskChartRisk"],
        ["risk_breadth", "simRiskChartBreadth"],
        ["production_events", "simRiskChartProduction"],
        ["customer_service", "simRiskChartService"],
      ];
      renderDiagnosticFigureSlots(figures, slots);
    }}

    function renderSimulatedRiskGlobalDiagnostic() {{
      const content = document.getElementById("simulatedRiskGlobalContent");
      if (!content) return false;
      if (simulatedRiskVisibleMode() === "campaign") {{
        const global = (SIMULATED_RISK_CAMPAIGN_METRICS && SIMULATED_RISK_CAMPAIGN_METRICS.global) || {{}};
        const nodes = Object.entries((SIMULATED_RISK_CAMPAIGN_METRICS && SIMULATED_RISK_CAMPAIGN_METRICS.nodes) || {{}})
          .sort((a, b) => Number((b[1] || {{}}).score || 0) - Number((a[1] || {{}}).score || 0));
        if (!nodes.length) {{
          content.innerHTML = '<div class="panelEmptyState">Aucun stress test fournisseur disponible pour ce run.</div>';
          return false;
        }}
        const topRows = nodes.slice(0, 15).map(([supplierId, row], idx) => {{
          const color = row.driver_color || "#64748b";
          const score = Number(row.score_decisionnel_pct || row.impact_pct || 0);
          const metier = Number(row.impact_metier_pct || 0);
          return `
            <tr>
              <td class="num">${{idx + 1}}</td>
              <td><span class="sensitivityLegendDot" style="background:${{escapeHtmlText(color)}}"></span> ${{escapeHtmlText(supplierId)}}</td>
              <td>${{escapeHtmlText(row.status_label || "n/a")}}</td>
              <td>${{escapeHtmlText(row.driver_label || "n/a")}}</td>
              <td class="num">${{fmtPanelQty(score, 1)}}%</td>
              <td>${{escapeHtmlText(row.impact_metier_kpi || "n/a")}}</td>
              <td>${{escapeHtmlText(row.impact_metier_delta || "n/a")}}</td>
              <td class="num">${{fmtPanelQty(metier, 1)}}%</td>
              <td>${{escapeHtmlText(row.impact_metier_lecture || row.impact_explanation || "aucune degradation KPI visible")}}</td>
            </tr>
          `;
        }}).join("");
        content.innerHTML = `
          <div class="factoryHtmlPanelContent sensitivityHtmlPanelContent">
            <div class="orderLedgerTextHeader">Risques simules - stress tests fournisseurs</div>
            <div class="orderLedgerStatus">Cette vue affiche les stress tests contrefactuels disponibles: ${{Number(global.stress_case_count || global.case_count || 0)}} cas sur ${{nodes.length}} fournisseurs. Le mode scenario injecte reste accessible avec le bouton dedie quand des evenements state-dependent existent.</div>
            <div class="orderLedgerStatus">Lecture metier: chaque ligne degrade un fournisseur dans une simulation separee et mesure les KPI qui bougent vraiment. Ce n'est pas un evenement observe dans la trajectoire nominale.</div>
            <table class="materialTable">
              <thead>
                <tr>
                  <th class="num">Rang</th>
                  <th>Fournisseur</th>
                  <th>Statut</th>
                  <th>Pire famille testee</th>
                  <th class="num">Score decisionnel</th>
                  <th>KPI metier</th>
                  <th>Delta KPI</th>
                  <th class="num">Intensite metier</th>
                  <th>Lecture</th>
                </tr>
              </thead>
              <tbody>${{topRows}}</tbody>
            </table>
          </div>
        `;
        return true;
      }}
      if (SIMULATED_RISK_GLOBAL_DIAGNOSTIC && SIMULATED_RISK_GLOBAL_DIAGNOSTIC.html) {{
        content.innerHTML = SIMULATED_RISK_GLOBAL_DIAGNOSTIC.html;
        renderSimulatedRiskCascadeExplorer(content);
        requestAnimationFrame(renderSimulatedRiskGlobalDiagnosticFigures);
        return true;
      }}
      content.innerHTML = '<div class="panelEmptyState">Aucun bilan de scenario risque disponible pour ce run.</div>';
      return false;
    }}

    function scenarioComparisonScenarios() {{
      return Array.isArray(SCENARIO_COMPARISON.scenarios) ? SCENARIO_COMPARISON.scenarios : [];
    }}

    function ensureScenarioComparisonSelection() {{
      const scenarios = scenarioComparisonScenarios();
      const validIds = new Set(scenarios.map(s => String(s.id || "")));
      if (!scenarioComparisonSelectedIds.size) {{
        scenarioComparisonSelectedIds = new Set(
          (SCENARIO_COMPARISON.default_selected_ids || scenarios.map(s => s.id)).map(String).filter(id => validIds.has(id))
        );
      }} else {{
        scenarioComparisonSelectedIds = new Set([...scenarioComparisonSelectedIds].filter(id => validIds.has(id)));
      }}
      if (!scenarioComparisonSelectedIds.size && scenarios.length) {{
        scenarioComparisonSelectedIds.add(String(scenarios[0].id || ""));
      }}
    }}

    function scenarioComparisonSelectedScenarioList() {{
      ensureScenarioComparisonSelection();
      const selected = scenarioComparisonSelectedIds;
      return scenarioComparisonScenarios().filter(s => selected.has(String(s.id || "")));
    }}

    function scenarioComparisonCard(title, value, text, color) {{
      return `
        <div class="riskScenarioCard" style="border-left-color:${{escapeHtmlText(color || "#64748b")}}">
          <div class="riskScenarioCardTitle">${{escapeHtmlText(title)}}</div>
          <div class="riskScenarioCardText"><strong>${{escapeHtmlText(value)}}</strong><br>${{escapeHtmlText(text)}}</div>
        </div>
      `;
    }}

    function scenarioComparisonDelta(value, base, digits = 0) {{
      const diff = Number(value || 0) - Number(base || 0);
      if (Math.abs(diff) <= 1e-9) return "0";
      return `${{diff > 0 ? "+" : ""}}${{fmtPanelQty(diff, digits)}}`;
    }}

    function scenarioComparisonCardsHtml() {{
      const scenarios = scenarioComparisonSelectedScenarioList();
      const allScenarios = scenarioComparisonScenarios();
      if (!scenarios.length) {{
        return '<div class="panelEmptyState">Aucun scenario selectionne.</div>';
      }}
      const scenarioReplanningText = (kpis) => {{
        const rate = Number(kpis.production_replanning_rate);
        const volume = Number(kpis.input_delay_volume || 0);
        const count = Number(kpis.production_replanning_count ?? kpis.input_delay_count ?? 0);
        if (Number.isFinite(rate)) {{
          return `taux replanification ${{fmtPanelQty(rate * 100, 1)}}% ; volume associe ${{fmtPanelQty(volume, 0)}}.`;
        }}
        return `taux replanification n/a ; volume associe ${{fmtPanelQty(volume, 0)}} ; ${{fmtPanelQty(count, 0)}} lignes.`;
      }};
      const nominal = allScenarios.find(s => ["_codex_lot_trace_5y_safe", "baseline_nominal"].includes(String(s.id || ""))) || allScenarios[0] || scenarios[0];
      const nominalKpis = (nominal && nominal.kpis) || {{}};
      const bestCost = scenarios.reduce((best, item) => Number((item.kpis || {{}}).total_cost || Infinity) < Number((best.kpis || {{}}).total_cost || Infinity) ? item : best, scenarios[0]);
      const bestProduction = scenarios.reduce((best, item) => {{
        const a = item.kpis || {{}};
        const b = best.kpis || {{}};
        const aRate = Number.isFinite(Number(a.production_replanning_rate)) ? Number(a.production_replanning_rate) : Infinity;
        const bRate = Number.isFinite(Number(b.production_replanning_rate)) ? Number(b.production_replanning_rate) : Infinity;
        const aKey = [aRate, Number(a.production_replanning_count ?? a.input_delay_count ?? 0), Number(a.input_delay_volume || 0)];
        const bKey = [bRate, Number(b.production_replanning_count ?? b.input_delay_count ?? 0), Number(b.input_delay_volume || 0)];
        return (aKey[0] < bKey[0] || (aKey[0] === bKey[0] && aKey[1] < bKey[1])) ? item : best;
      }}, scenarios[0]);
      const mostRisk = scenarios.reduce((best, item) => {{
        const a = item.kpis || {{}};
        const b = best.kpis || {{}};
        return Number(a.impact_score || a.risk_event_count || 0) > Number(b.impact_score || b.risk_event_count || 0) ? item : best;
      }}, scenarios[0]);
      const refText = `Base de comparaison: disponibilite produit ${{fmtPanelQty(Number(nominalKpis.fill_rate || 0) * 100, 1)}}% ; cout total ${{fmtPanelQty(nominalKpis.total_cost || 0, 0)}}. Amorcage client: ${{Number(nominalKpis.startup_backlog_days || 0)}} j, pic ${{fmtPanelQty(nominalKpis.startup_backlog_peak || 0, 0)}}.`;
      const bestCostKpis = bestCost.kpis || {{}};
      const bestProductionKpis = bestProduction.kpis || {{}};
      const mostRiskKpis = mostRisk.kpis || {{}};
      return [
        scenarioComparisonCard("Reference", nominal.label || "Reference", refText, "#2563eb"),
        scenarioComparisonCard(
          "Cout total le plus bas",
          bestCost.label || "n/a",
          `Cout total ${{fmtPanelQty(bestCostKpis.total_cost || 0, 0)}} ; delta vs reference ${{scenarioComparisonDelta(bestCostKpis.total_cost || 0, nominalKpis.total_cost || 0, 0)}}.`,
          "#0f766e"
        ),
        scenarioComparisonCard(
          "Production la moins reportee",
          bestProduction.label || "n/a",
          scenarioReplanningText(bestProductionKpis),
          "#d97706"
        ),
        scenarioComparisonCard(
          "Scenario le plus perturbateur",
          mostRisk.label || "n/a",
          `Score ${{fmtPanelQty(mostRiskKpis.impact_score || 0, 1)}} ; disponibilite produit ${{fmtPanelQty(Number(mostRiskKpis.fill_rate || 0) * 100, 1)}}% ; backlog max ${{fmtPanelQty(mostRiskKpis.max_backlog || 0, 0)}}.`,
          "#be123c"
        ),
      ].join("");
    }}

    function filterScenarioComparisonFigure(figure) {{
      ensureScenarioComparisonSelection();
      const selected = scenarioComparisonSelectedIds;
      if (!figure) return null;
      if (figure.kind === "line_multi") {{
        const filteredSeries = (figure.series || []).filter(series => {{
          const id = String(series.scenario_id || "");
          return selected.has(id);
        }});
        if (!filteredSeries.length) return null;
        return {{ ...figure, series: filteredSeries }};
      }}
      if (figure.kind === "bar") {{
        const ids = figure.ids || [];
        const labels = [];
        const values = [];
        const colors = [];
        ids.forEach((id, idx) => {{
          if (!selected.has(String(id || ""))) return;
          labels.push((figure.labels || [])[idx]);
          values.push((figure.values || [])[idx]);
          colors.push((figure.colors || [])[idx] || "#2563eb");
        }});
        if (!labels.length) return null;
        return {{ ...figure, ids: ids.filter(id => selected.has(String(id || ""))), labels, values, colors }};
      }}
      return figure;
    }}

    function renderScenarioComparisonFigures() {{
      if (!window.Plotly || !SCENARIO_COMPARISON) return;
      const sourceFigures = SCENARIO_COMPARISON.figures || {{}};
      const filteredFigures = {{
        backlog: filterScenarioComparisonFigure(sourceFigures.backlog || null),
        service_rate: filterScenarioComparisonFigure(sourceFigures.service_rate || null),
        production_delays: filterScenarioComparisonFigure(sourceFigures.production_delays || null),
        production_starts: filterScenarioComparisonFigure(sourceFigures.production_starts || null),
        risk_rows: filterScenarioComparisonFigure(sourceFigures.risk_rows || null),
        cost: filterScenarioComparisonFigure(sourceFigures.cost || null),
      }};
      renderDiagnosticFigureSlots(filteredFigures, [
        ["backlog", "scenarioCmpBacklog"],
        ["service_rate", "scenarioCmpService"],
        ["production_delays", "scenarioCmpProduction"],
        ["production_starts", "scenarioCmpStarts"],
        ["risk_rows", "scenarioCmpRisk"],
        ["cost", "scenarioCmpCost"],
      ]);
    }}

    function applyScenarioComparisonFilter() {{
      ensureScenarioComparisonSelection();
      const selected = scenarioComparisonSelectedIds;
      const total = scenarioComparisonScenarios().length;
      document.querySelectorAll(".scenarioComparisonChk").forEach(chk => {{
        chk.checked = selected.has(String(chk.value || ""));
      }});
      document.querySelectorAll(".scenarioComparisonTable tbody tr[data-scenario-id]").forEach(row => {{
        row.classList.toggle("scenarioComparisonHidden", !selected.has(String(row.getAttribute("data-scenario-id") || "")));
      }});
      const meta = document.getElementById("scenarioComparisonSelectionMeta");
      if (meta) meta.textContent = `${{selected.size}} / ${{total}} scenario(s) affiches`;
      const cards = document.getElementById("scenarioComparisonCards");
      if (cards) cards.innerHTML = scenarioComparisonCardsHtml();
      requestAnimationFrame(renderScenarioComparisonFigures);
    }}

    function bindScenarioComparisonControls() {{
      ensureScenarioComparisonSelection();
      document.querySelectorAll(".scenarioComparisonChk").forEach(chk => {{
        chk.checked = scenarioComparisonSelectedIds.has(String(chk.value || ""));
        chk.addEventListener("change", () => {{
          const id = String(chk.value || "");
          if (chk.checked) scenarioComparisonSelectedIds.add(id);
          else scenarioComparisonSelectedIds.delete(id);
          applyScenarioComparisonFilter();
        }});
      }});
      document.querySelectorAll("[data-scenario-select]").forEach(btn => {{
        btn.addEventListener("click", () => {{
          const mode = String(btn.getAttribute("data-scenario-select") || "");
          const scenarios = scenarioComparisonScenarios();
          const nominal = scenarios.find(s => ["_codex_lot_trace_5y_safe", "baseline_nominal"].includes(String(s.id || "")));
          const withNominal = (items) => {{
            const ids = [];
            if (nominal) ids.push(String(nominal.id || ""));
            items.forEach(item => {{
              const id = String(item.id || "");
              if (id && !ids.includes(id)) ids.push(id);
            }});
            return new Set(ids);
          }};
          const familyIncludes = (scenario, key) => String(scenario.family || scenario.kind || "").toLowerCase().includes(key);
          if (mode === "all") {{
            scenarioComparisonSelectedIds = new Set(scenarios.map(s => String(s.id || "")));
          }} else if (mode === "top") {{
            const ranked = [...scenarios]
              .filter(s => !["_codex_lot_trace_5y_safe", "baseline_nominal"].includes(String(s.id || "")))
              .sort((a, b) => Number((b.kpis || {{}}).impact_score || 0) - Number((a.kpis || {{}}).impact_score || 0))
              .slice(0, 8);
            scenarioComparisonSelectedIds = withNominal(ranked);
          }} else if (mode === "service") {{
            const service = scenarios.filter(s => {{
              const k = s.kpis || {{}};
              return Number(k.fill_rate || 1) < 0.999 || Number(k.max_backlog || 0) > 0;
            }});
            scenarioComparisonSelectedIds = withNominal(service.length ? service : scenarios.slice(0, 1));
          }} else if (mode === "lead_time") {{
            scenarioComparisonSelectedIds = withNominal(scenarios.filter(s => familyIncludes(s, "lead_time") || familyIncludes(s, "delai")));
          }} else if (mode === "quality") {{
            scenarioComparisonSelectedIds = withNominal(scenarios.filter(s => familyIncludes(s, "quality")));
          }} else if (mode === "transport") {{
            scenarioComparisonSelectedIds = withNominal(scenarios.filter(s => familyIncludes(s, "transport")));
          }} else if (mode === "combined") {{
            scenarioComparisonSelectedIds = withNominal(scenarios.filter(s => familyIncludes(s, "combined")));
          }} else if (mode === "current") {{
            const current = scenarios.find(s => Boolean(s.is_current)) || scenarios[0];
            scenarioComparisonSelectedIds = new Set(current ? [String(current.id || "")] : []);
          }} else if (mode === "nominal_current") {{
            const ids = [];
            const current = scenarios.find(s => Boolean(s.is_current));
            if (nominal) ids.push(String(nominal.id || ""));
            if (current) ids.push(String(current.id || ""));
            scenarioComparisonSelectedIds = new Set(ids.length ? ids : scenarios.slice(0, 2).map(s => String(s.id || "")));
          }}
          applyScenarioComparisonFilter();
        }});
      }});
    }}

    function renderScenarioComparison() {{
      const content = document.getElementById("scenarioComparisonContent");
      if (!content) return false;
      if (SCENARIO_COMPARISON && SCENARIO_COMPARISON.html) {{
        content.innerHTML = SCENARIO_COMPARISON.html;
        bindScenarioComparisonControls();
        applyScenarioComparisonFilter();
        return true;
      }}
      content.innerHTML = '<div class="panelEmptyState">Aucune comparaison de scenarios disponible. Regenerer au moins un run nominal et un run risque dans etudecas/simulation/result.</div>';
      return false;
    }}

    function renderMonteCarloUncertainty() {{
      const content = document.getElementById("monteCarloContent");
      if (!content) return false;
      if (MONTECARLO_UNCERTAINTY && MONTECARLO_UNCERTAINTY.html) {{
        const uncertaintyDataHtml = String(MONTECARLO_UNCERTAINTY.html || "")
          .replace('<div id="monteCarloDynamicChartsAnchor"></div>', "");
        content.innerHTML = `
          <div class="monteCarloTabBar">
            <div class="lotTraceDirectionTabs" role="tablist" aria-label="Vues Monte Carlo">
              <button class="lotTraceDirectionBtn active" type="button" data-monte-carlo-tab="curves">Courbes globales</button>
              <button class="lotTraceDirectionBtn" type="button" data-monte-carlo-tab="data">Donnees d'incertitude</button>
            </div>
            <div class="monteCarloTabHint">Courbes = trajectoires et enveloppes. Donnees = synthese, priorites, propagation et details modele.</div>
          </div>
          <div id="monteCarloCurvesPane" class="monteCarloPane" role="tabpanel">
            <div id="monteCarloDynamicChartsAnchor"></div>
          </div>
          <div id="monteCarloDataPane" class="monteCarloPane hidden" role="tabpanel"></div>
        `;
        const dataPane = content.querySelector("#monteCarloDataPane");
        if (dataPane) dataPane.innerHTML = uncertaintyDataHtml;
        const tabButtons = Array.from(content.querySelectorAll("[data-monte-carlo-tab]"));
        const curvesPane = content.querySelector("#monteCarloCurvesPane");
        const setMonteCarloTab = (tab) => {{
          tabButtons.forEach(btn => btn.classList.toggle("active", String(btn.dataset.monteCarloTab || "") === tab));
          if (curvesPane) curvesPane.classList.toggle("hidden", tab !== "curves");
          if (dataPane) dataPane.classList.toggle("hidden", tab !== "data");
          if (tab === "curves" && window.Plotly) {{
            requestAnimationFrame(() => {{
              content.querySelectorAll("#monteCarloCurvesPane .riskDiagnosticChart").forEach(el => {{
                try {{ Plotly.Plots.resize(el); }} catch (e) {{}}
              }});
            }});
          }}
        }};
        tabButtons.forEach(btn => {{
          btn.addEventListener("click", () => setMonteCarloTab(String(btn.dataset.monteCarloTab || "curves")));
        }});
        const compareBtn = content.querySelector("#uncertaintyScenarioCompareBtn");
        if (compareBtn) {{
          compareBtn.addEventListener("click", () => {{
            const modal = document.getElementById("scenarioComparisonModal");
            renderScenarioComparison();
            if (modal) modal.classList.add("visible");
          }});
        }}
        const dynamicAnchor = content.querySelector("#monteCarloDynamicChartsAnchor") || content;
        const figures = (((MONTECARLO_UNCERTAINTY.trajectory_assets || {{}}).figures) || {{}});
        const factorTubeFigures = (((MONTECARLO_UNCERTAINTY.trajectory_assets || {{}}).factor_tube_figures) || {{}});
        const factorTubeKeys = [
          ["service_rate", "mcFactorTubeService"],
          ["backlog", "mcFactorTubeBacklog"],
          ["production_delay_active_orders", "mcFactorTubeProdDelayOrders"],
          ["production_reports", "mcFactorTubeReports"],
          ["supplier_capacity_binding", "mcFactorTubeSupplierBinding"],
          ["total_supply_cost_cum", "mcFactorTubeCost"],
        ].filter(([key]) => factorTubeFigures[key]);
        const figureKeys = [
          ["service_rate", "mcTrajectoryService"],
          ["backlog", "mcTrajectoryBacklog"],
          ["production_delay_active_orders", "mcTrajectoryProdDelayOrders"],
          ["production_reports", "mcTrajectoryReports"],
          ["supplier_capacity_binding", "mcTrajectorySupplierBinding"],
          ["total_supply_cost_cum", "mcTrajectoryCost"],
        ].filter(([key]) => figures[key]);
        if (!factorTubeKeys.length && !figureKeys.length) {{
          dynamicAnchor.innerHTML = '<div class="panelEmptyState">Aucune trajectoire Monte Carlo disponible. Relancer Monte Carlo avec sauvegarde des trajectoires.</div>';
        }}
        if (figureKeys.length) {{
          const chartsHtml = figureKeys.map(([_key, id]) => `<div id="${{id}}" class="riskDiagnosticChart"></div>`).join("");
          dynamicAnchor.insertAdjacentHTML("beforeend", `
            <section class="dataSummarySection">
              <div class="dataSummarySectionTitle">Courbes globales Monte Carlo</div>
              <div class="orderLedgerStatus">Lecture: ces courbes sont globales au run, pas locales a un noeud. La zone min-max contient toutes les courbes affichees ; les zones 5-95%, 10-90% et 25-75% sont des percentiles et excluent les extremes. Les courbes de scenarios restent visibles en noir fin, la mediane est pointillee et le nominal est noir plus epais.</div>
              <div class="riskDiagnosticChartGrid">${{chartsHtml}}</div>
            </section>
          `);
          requestAnimationFrame(() => renderDiagnosticFigureSlots(figures, figureKeys));
        }}
        if (factorTubeKeys.length) {{
          const factorChartsHtml = factorTubeKeys.map(([_key, id]) => `<div id="${{id}}" class="riskDiagnosticChart"></div>`).join("");
          dynamicAnchor.insertAdjacentHTML("beforeend", `
            <section class="dataSummarySection">
              <div class="dataSummarySectionTitle">Propagation temporelle par parametre d'incertitude</div>
              <div class="orderLedgerStatus">Lecture: chaque courbe est une zone. Elle compare les runs ou un input incertain fournisseur est bas avec les runs ou ce meme input est haut. Pour les KPI continus, la zone suit la mediane des groupes; pour les KPI rares en pics, elle peut suivre une moyenne ou un percentile haut de groupe afin de ne pas effacer les evenements tardifs. Le nominal reste en noir. Cliquer sur une zone surligne le noeud ou le driver concerne sur la carte.</div>
              <div class="riskDiagnosticChartGrid">${{factorChartsHtml}}</div>
            </section>
          `);
          requestAnimationFrame(() => renderDiagnosticFigureSlots(factorTubeFigures, factorTubeKeys));
        }}
        return true;
      }}
      content.innerHTML = '<div class="panelEmptyState">Aucun resultat Monte Carlo disponible pour ce run.</div>';
      return false;
    }}

    function init() {{
      initFilters();
      initRiskTooltipPortal();
      initLotTraceControls();
      syncYearInputs();
      updateTimelineWindowLabel();
      applyModeUi();
      const materialTableModal = document.getElementById("materialTableModal");
      document.getElementById("materialTableBtn").addEventListener("click", () => {{
        renderMaterialTable();
        materialTableModal.classList.add("visible");
      }});
      document.getElementById("materialTableCloseBtn").addEventListener("click", () => {{
        materialTableModal.classList.remove("visible");
      }});
      materialTableModal.addEventListener("click", (ev) => {{
        if (ev.target === materialTableModal) {{
          materialTableModal.classList.remove("visible");
        }}
      }});
      const sensitivityTop3Modal = document.getElementById("sensitivityTop3Modal");
      document.getElementById("sensitivityTop3Btn").addEventListener("click", () => {{
        setPanelMode("sensitivity");
        renderGlobalSensitivityTop3();
        sensitivityTop3Modal.classList.add("visible");
      }});
      document.getElementById("sensitivityTop3CloseBtn").addEventListener("click", () => {{
        sensitivityTop3Modal.classList.remove("visible");
      }});
      sensitivityTop3Modal.addEventListener("click", (ev) => {{
        if (ev.target === sensitivityTop3Modal) {{
          sensitivityTop3Modal.classList.remove("visible");
        }}
      }});
      const simulatedRiskGlobalModal = document.getElementById("simulatedRiskGlobalModal");
      const simulatedRiskStateBtn = document.getElementById("simulatedRiskStateBtn");
      if (simulatedRiskStateBtn) {{
        simulatedRiskStateBtn.addEventListener("click", () => {{
          setPanelMode("simulated_risk");
          setSimulatedRiskViewMode("state");
        }});
      }}
      const simulatedRiskGlobalBtn = document.getElementById("simulatedRiskGlobalBtn");
      if (simulatedRiskGlobalBtn) {{
        simulatedRiskGlobalBtn.addEventListener("click", () => {{
          setPanelMode("simulated_risk");
          setSimulatedRiskViewMode("state");
          simulatedRiskGlobalModal.classList.add("visible");
          renderSimulatedRiskGlobalDiagnostic();
        }});
      }}
      const supplierStressCampaignBtn = document.getElementById("supplierStressCampaignBtn");
      if (supplierStressCampaignBtn) {{
        supplierStressCampaignBtn.addEventListener("click", () => {{
          setPanelMode("simulated_risk");
          setSimulatedRiskViewMode("campaign");
          simulatedRiskGlobalModal.classList.add("visible");
          renderSimulatedRiskGlobalDiagnostic();
        }});
      }}
      const simulatedRiskCascadeSelect = document.getElementById("simulatedRiskCascadeSelect");
      if (simulatedRiskCascadeSelect) {{
        simulatedRiskCascadeSelect.addEventListener("change", (ev) => {{
          const cascadeKey = ev.target.value || "";
          setPanelMode("simulated_risk");
          setSimulatedRiskViewMode("state");
          setSelectedSimulatedRiskCascade(cascadeKey);
        }});
      }}
      const simulatedRiskCascadeStageFilterEl = document.getElementById("simulatedRiskCascadeStageFilter");
      if (simulatedRiskCascadeStageFilterEl) {{
        simulatedRiskCascadeStageFilterEl.addEventListener("change", (ev) => {{
          simulatedRiskCascadeStageFilter = String(ev.target.value || "all");
          selectedSimulatedRiskCascadeKey = "";
          setPanelMode("simulated_risk");
          setSimulatedRiskViewMode("state");
          updateSimulatedRiskControls();
          draw();
        }});
      }}
      const simulatedRiskCascadeFamilyFilterEl = document.getElementById("simulatedRiskCascadeFamilyFilter");
      if (simulatedRiskCascadeFamilyFilterEl) {{
        simulatedRiskCascadeFamilyFilterEl.addEventListener("change", (ev) => {{
          simulatedRiskCascadeFamilyFilter = String(ev.target.value || "all");
          selectedSimulatedRiskCascadeKey = "";
          setPanelMode("simulated_risk");
          setSimulatedRiskViewMode("state");
          updateSimulatedRiskControls();
          draw();
        }});
      }}
      const simulatedRiskCascadeClearBtn = document.getElementById("simulatedRiskCascadeClearBtn");
      if (simulatedRiskCascadeClearBtn) {{
        simulatedRiskCascadeClearBtn.addEventListener("click", () => setSelectedSimulatedRiskCascade(""));
      }}
      document.getElementById("simulatedRiskGlobalCloseBtn").addEventListener("click", () => {{
        simulatedRiskGlobalModal.classList.remove("visible");
      }});
      simulatedRiskGlobalModal.addEventListener("click", (ev) => {{
        if (ev.target === simulatedRiskGlobalModal) {{
          simulatedRiskGlobalModal.classList.remove("visible");
        }}
      }});
      const scenarioComparisonModal = document.getElementById("scenarioComparisonModal");
      const scenarioComparisonBtn = document.getElementById("scenarioComparisonBtn");
      if (scenarioComparisonBtn) {{
        scenarioComparisonBtn.addEventListener("click", () => {{
          setPanelMode("simulated_risk");
          scenarioComparisonModal.classList.add("visible");
          renderScenarioComparison();
        }});
      }}
      document.getElementById("scenarioComparisonCloseBtn").addEventListener("click", () => {{
        scenarioComparisonModal.classList.remove("visible");
      }});
      scenarioComparisonModal.addEventListener("click", (ev) => {{
        if (ev.target === scenarioComparisonModal) {{
          scenarioComparisonModal.classList.remove("visible");
        }}
      }});
      const monteCarloModal = document.getElementById("monteCarloModal");
      document.getElementById("monteCarloBtn").addEventListener("click", () => {{
        setPanelMode("uncertainty");
        renderMonteCarloUncertainty();
        monteCarloModal.classList.add("visible");
      }});
      document.getElementById("monteCarloCloseBtn").addEventListener("click", () => {{
        monteCarloModal.classList.remove("visible");
      }});
      monteCarloModal.addEventListener("click", (ev) => {{
        if (ev.target === monteCarloModal) {{
          monteCarloModal.classList.remove("visible");
        }}
      }});
      const uncertaintyModeSelect = document.getElementById("uncertaintyModeSelect");
      if (uncertaintyModeSelect) {{
        uncertaintyModeSelect.addEventListener("change", (ev) => {{
          uncertaintyMode = String(ev.target.value || "capacity");
          lastFactoryPanelRenderKey = "";
          updateUncertaintyControls();
          draw();
        }});
      }}
      const uncertaintyDisplaySelect = document.getElementById("uncertaintyDisplaySelect");
      if (uncertaintyDisplaySelect) {{
        uncertaintyDisplaySelect.addEventListener("change", (ev) => {{
          uncertaintyDisplayMode = String(ev.target.value || "dominant_type");
          lastFactoryPanelRenderKey = "";
          updateUncertaintyControls();
          draw();
        }});
      }}
      const kpiTreeModal = document.getElementById("kpiTreeModal");
      document.getElementById("kpiTreeBtn").addEventListener("click", () => {{
        kpiTreeModal.classList.add("visible");
        requestAnimationFrame(() => {{
          renderGlobalKpiTree();
          requestAnimationFrame(() => {{
            if (window.Plotly && Plotly.Plots && Plotly.Plots.resize) {{
              kpiTreeModal.querySelectorAll(".js-plotly-plot").forEach(plot => {{
                try {{ Plotly.Plots.resize(plot); }} catch (e) {{}}
              }});
            }}
          }});
        }});
      }});
      document.getElementById("kpiTreeCloseBtn").addEventListener("click", () => {{
        kpiTreeModal.classList.remove("visible");
      }});
      kpiTreeModal.addEventListener("click", (ev) => {{
        if (ev.target === kpiTreeModal) {{
          kpiTreeModal.classList.remove("visible");
        }}
      }});
      const modelEquationsModal = document.getElementById("modelEquationsModal");
      document.getElementById("modelEquationsBtn").addEventListener("click", () => {{
        modelEquationsModal.classList.add("visible");
      }});
      document.getElementById("modelEquationsCloseBtn").addEventListener("click", () => {{
        modelEquationsModal.classList.remove("visible");
      }});
      modelEquationsModal.addEventListener("click", (ev) => {{
        if (ev.target === modelEquationsModal) {{
          modelEquationsModal.classList.remove("visible");
        }}
      }});
      const panelDetailsToggle = document.getElementById("panelDetailsToggle");
      if (panelDetailsToggle) {{
        panelDetailsToggle.addEventListener("click", () => {{
          panelDetailsExpanded = !panelDetailsExpanded;
          applyPanelDetailVisibility(
            currentFactoryHoverId || selectedPanelNodeId || "",
            currentFactoryHoverType || selectedPanelNodeType || ""
          );
          requestAnimationFrame(() => {{
            placeAndResizeFactoryPanel();
            if (window.Plotly && Plotly.Plots && Plotly.Plots.resize) {{
              document.querySelectorAll("#factoryHoverPanel .js-plotly-plot").forEach(plot => {{
                try {{ Plotly.Plots.resize(plot); }} catch (e) {{}}
              }});
            }}
          }});
        }});
      }}
      document.getElementById("showDebugTools").addEventListener("change", (ev) => {{
        debugToolsVisible = Boolean(ev.target.checked);
        if (!debugToolsVisible && isDebugPanelMode(currentPanelMode)) {{
          setPanelMode("ops");
          return;
        }}
        lastFactoryPanelRenderKey = "";
        applyModeUi();
        draw();
      }});
      document.getElementById("showEdges").addEventListener("change", () => {{
        applyModeUi();
        draw();
      }});
      document.getElementById("edgeInteraction").addEventListener("change", () => {{
        applyModeUi();
        draw();
      }});
      document.getElementById("modeOps").addEventListener("click", () => setPanelMode("ops"));
      document.getElementById("modeData").addEventListener("click", () => setPanelMode("data"));
      document.getElementById("modeModel").addEventListener("click", () => setPanelMode("model"));
      document.getElementById("modeJson").addEventListener("click", () => setPanelMode("json"));
      document.getElementById("modeSensitivity").addEventListener("click", () => setPanelMode("sensitivity"));
      document.getElementById("modeSimulatedRisk").addEventListener("click", () => setPanelMode("simulated_risk"));
      document.getElementById("modeRisk").addEventListener("click", () => setPanelMode("risk"));
      document.getElementById("modeUncertainty").addEventListener("click", () => setPanelMode("uncertainty"));
      document.getElementById("modeStructural").addEventListener("click", () => setPanelMode("structural"));
      const hoverPanel = document.getElementById("factoryHoverPanel");
      hoverPanel.addEventListener("mouseenter", () => {{
        panelPointerInside = true;
        if (hoverClearTimeout) {{
          clearTimeout(hoverClearTimeout);
          hoverClearTimeout = null;
        }}
      }});
      hoverPanel.addEventListener("mouseleave", () => {{
        panelPointerInside = false;
        if (!selectedPanelNodeId) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
        }}
      }});
      document.getElementById("yearStart").addEventListener("input", (ev) => {{
        selectedYearStart = Number(ev.target.value || 1);
        if (selectedYearStart > selectedYearEnd) {{
          selectedYearEnd = selectedYearStart;
        }}
        syncYearInputs();
        updateTimelineWindowLabel();
        renderMaterialTable();
        refreshFactoryPanel();
        renderGlobalKpiTreeIfVisible();
        renderSimulatedRiskGlobalIfVisible();
        renderScenarioComparisonIfVisible();
      }});
      document.getElementById("yearEnd").addEventListener("input", (ev) => {{
        selectedYearEnd = Number(ev.target.value || 1);
        if (selectedYearEnd < selectedYearStart) {{
          selectedYearStart = selectedYearEnd;
        }}
        syncYearInputs();
        updateTimelineWindowLabel();
        renderMaterialTable();
        refreshFactoryPanel();
        renderGlobalKpiTreeIfVisible();
        renderSimulatedRiskGlobalIfVisible();
        renderScenarioComparisonIfVisible();
      }});
      document.getElementById("factoryHoverClearSelection").addEventListener("click", clearPanelSelection);
      window.addEventListener("resize", placeAndResizeFactoryPanel);
      for (const chk of document.querySelectorAll(".typeChk")) {{
        chk.addEventListener("change", draw);
      }}
      draw();
    }}

    window.addEventListener("load", init);
  </script>
</body>
</html>"""
