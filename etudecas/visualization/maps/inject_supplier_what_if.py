#!/usr/bin/env python3
"""Inject a supplier parameter what-if panel into an existing autonomous map.

The panel is deliberately data-driven: it does not recompute the Python
simulation in the browser. It lets the user explore precomputed supplier
parameter scenarios from the normalized sensitivity `metrics.csv`.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

try:
    from etudecas.simulation.engine.contracts import (
        DEFAULT_INTERACTIVE_DAYS,
        DEFAULT_INTERACTIVE_INPUT_PATH,
        DEFAULT_INTERACTIVE_OUTPUT_PROFILE,
        DEFAULT_INTERACTIVE_SCENARIO_ID,
        supplier_parameter_overrides,
    )
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.simulation.engine.contracts import (
        DEFAULT_INTERACTIVE_DAYS,
        DEFAULT_INTERACTIVE_INPUT_PATH,
        DEFAULT_INTERACTIVE_OUTPUT_PROFILE,
        DEFAULT_INTERACTIVE_SCENARIO_ID,
        supplier_parameter_overrides,
    )


KPI_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("fill_rate", "Disponibilite produit", "%"),
    ("ending_backlog", "Backlog final", "qty"),
    ("production_replanning_count", "Volume replanifie associe", "count"),
    ("raw_material_stockout_days", "Jours rupture MP", "days"),
    ("total_cost", "Cout total", "eur"),
    ("total_produced", "Production totale", "qty"),
    ("product_availability", "Disponibilite produit", "%"),
    ("total_external_procured_arrived_qty", "Appro fournisseur arrive", "qty"),
)

PARAMETER_LABELS = {
    "supplier_stock_node": "Stock fournisseur accessible",
    "supplier_capacity_node": "Capacite fournisseur",
    "supplier_lead_time_node": "Delai fournisseur",
    "supplier_reliability_node": "Fiabilite fournisseur",
    "supplier_combined_capacity_delay_node": "Capacite + delai fournisseur",
    "supplier_combined_stock_reliability_node": "Stock + fiabilite fournisseur",
    "supplier_stock_global": "Stock fournisseurs global",
    "supplier_capacity_global": "Capacite fournisseurs globale",
    "supplier_lead_time_global": "Delai fournisseurs global",
    "supplier_reliability_global": "Fiabilite fournisseurs globale",
    "supplier_upstream_supply": "Appro fournisseur global",
    "supplier_combined_upstream_supply": "Appro fournisseur combine",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject supplier what-if panel into a generated map HTML.")
    parser.add_argument("--input", required=True, help="Input map HTML.")
    parser.add_argument(
        "--metrics",
        default="etudecas/simulation/experiments/result/supplier_parameter_ingested/metrics.csv",
        help="Normalized supplier parameter metrics CSV.",
    )
    parser.add_argument(
        "--simulation-input",
        default=DEFAULT_INTERACTIVE_INPUT_PATH,
        help="Input graph path to put in generated simulation request contracts.",
    )
    parser.add_argument("--scenario-id", default=DEFAULT_INTERACTIVE_SCENARIO_ID)
    parser.add_argument("--days", type=int, default=DEFAULT_INTERACTIVE_DAYS)
    parser.add_argument("--output-profile", default=DEFAULT_INTERACTIVE_OUTPUT_PROFILE)
    parser.add_argument("--output", help="Output HTML. Defaults to <input>.supplier_whatif.html")
    parser.add_argument("--execute", action="store_true", help="Write file. Default is dry-run.")
    return parser.parse_args()


def to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def supplier_from_row(row: dict[str, str]) -> str:
    parameter_key = str(row.get("parameter_key") or "")
    if "::" in parameter_key:
        return parameter_key.split("::", 1)[1]
    return "GLOBAL"


def kpis_from_row(row: dict[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for short_name, _, _ in KPI_FIELDS:
        value = to_float(row.get(f"kpi::{short_name}"))
        if value is not None:
            out[short_name] = value
    return out


def build_supplier_what_if_payload(
    metrics_csv: Path,
    *,
    simulation_input: str = DEFAULT_INTERACTIVE_INPUT_PATH,
    scenario_id: str = DEFAULT_INTERACTIVE_SCENARIO_ID,
    days: int = DEFAULT_INTERACTIVE_DAYS,
    output_profile: str = DEFAULT_INTERACTIVE_OUTPUT_PROFILE,
) -> dict[str, Any]:
    with metrics_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    baseline_row = next(
        (
            row
            for row in rows
            if str(row.get("parameter_group") or "") == "baseline"
            or str(row.get("case_id") or "").lower() == "baseline"
        ),
        None,
    )
    baseline = kpis_from_row(baseline_row or {})
    cases: list[dict[str, Any]] = []
    supplier_ids: set[str] = set()
    parameter_groups: set[str] = set()

    for row in rows:
        if str(row.get("status") or "ok").lower() not in {"ok", ""}:
            continue
        group = str(row.get("parameter_group") or "")
        if group == "baseline" or group not in PARAMETER_LABELS:
            continue
        level = to_float(row.get("level"))
        if level is None:
            continue
        supplier_id = supplier_from_row(row)
        supplier_ids.add(supplier_id)
        parameter_groups.add(group)
        cases.append(
            {
                "case_id": row.get("case_id") or "",
                "scenario_id": row.get("scenario_id") or "",
                "supplier_id": supplier_id,
                "parameter_group": group,
                "parameter_key": row.get("parameter_key") or "",
                "parameter_label": row.get("parameter_label") or PARAMETER_LABELS[group],
                "level": level,
                "kpis": kpis_from_row(row),
                "request_overrides": supplier_parameter_overrides(
                    parameter_group=group,
                    parameter_key=row.get("parameter_key") or "",
                    supplier_id=supplier_id,
                    level=level,
                ),
            }
        )

    cases.sort(key=lambda c: (str(c["supplier_id"]), str(c["parameter_group"]), float(c["level"])))
    return {
        "source": str(metrics_csv),
        "mode": "precomputed",
        "simulation_request_defaults": {
            "input_path": simulation_input,
            "scenario_id": scenario_id,
            "days": int(days),
            "output_profile": output_profile,
            "skip_map": True,
            "skip_plots": True,
        },
        "case_count": len(cases),
        "baseline": baseline,
        "kpi_fields": [{"key": key, "label": label, "unit": unit} for key, label, unit in KPI_FIELDS],
        "parameter_labels": PARAMETER_LABELS,
        "suppliers": sorted(supplier_ids, key=lambda value: (value == "GLOBAL", value)),
        "parameter_groups": sorted(parameter_groups),
        "cases": cases,
    }


def what_if_panel_html(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        r"""
<style id="supplierWhatIfStyle">
  #supplierWhatIfButton {
    position: fixed; right: 18px; bottom: 18px; z-index: 99997;
    border: 1px solid #0f172a; background: #0f172a; color: #fff;
    border-radius: 999px; padding: 10px 14px; font: 700 14px Arial, sans-serif;
    box-shadow: 0 10px 24px rgba(15, 23, 42, .22); cursor: pointer;
  }
  #supplierWhatIfPanel {
    position: fixed; inset: 72px 28px 28px 28px; z-index: 99998;
    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 10px;
    box-shadow: 0 20px 60px rgba(15, 23, 42, .25); display: none;
    color: #111827; font-family: Arial, sans-serif; overflow: hidden;
  }
  #supplierWhatIfPanel.open { display: grid; grid-template-rows: auto 1fr; }
  .supplierWhatIfHeader {
    display: flex; justify-content: space-between; align-items: center;
    gap: 12px; padding: 14px 18px; background: #fff; border-bottom: 1px solid #dbe3ef;
  }
  .supplierWhatIfHeader h2 { margin: 0; font-size: 18px; }
  .supplierWhatIfHeader p { margin: 3px 0 0 0; color: #475569; font-size: 13px; }
  .supplierWhatIfClose {
    border: 1px solid #cbd5e1; border-radius: 999px; background: #fff;
    padding: 7px 12px; font-weight: 700; cursor: pointer;
  }
  .supplierWhatIfBody {
    display: grid; grid-template-columns: 360px 1fr; min-height: 0;
  }
  .supplierWhatIfControls {
    background: #fff; border-right: 1px solid #dbe3ef; padding: 14px;
    overflow: auto;
  }
  .supplierWhatIfResults { padding: 14px; overflow: auto; }
  .supplierWhatIfField { margin-bottom: 12px; }
  .supplierWhatIfField label {
    display: block; font-size: 12px; color: #475569; font-weight: 700; margin-bottom: 4px;
    text-transform: uppercase;
  }
  .supplierWhatIfField select, .supplierWhatIfField input[type="range"] {
    width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1;
    border-radius: 7px; padding: 8px; font: inherit; background: #fff;
  }
  .supplierWhatIfNote {
    border-left: 4px solid #2563eb; background: #eff6ff; color: #1e3a8a;
    padding: 10px; border-radius: 8px; font-size: 13px; line-height: 1.35;
  }
  .supplierWhatIfCards {
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px;
  }
  .supplierWhatIfCard {
    border: 1px solid #dbe3ef; background: #fff; border-radius: 8px; padding: 10px;
  }
  .supplierWhatIfCard span { display: block; color: #64748b; font-size: 12px; }
  .supplierWhatIfCard b { display: block; font-size: 18px; margin-top: 4px; }
  .supplierWhatIfCard small { display: block; margin-top: 5px; color: #475569; }
  .supplierWhatIfDeltaBad { color: #dc2626; }
  .supplierWhatIfDeltaGood { color: #047857; }
  #supplierWhatIfChart, #supplierWhatIfCostChart {
    min-height: 300px; border: 1px solid #dbe3ef; background: #fff; border-radius: 8px; margin-bottom: 12px;
  }
  #supplierWhatIfTable {
    width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #dbe3ef; border-radius: 8px; overflow: hidden;
  }
  #supplierWhatIfTable th, #supplierWhatIfTable td {
    border-bottom: 1px solid #e5edf7; padding: 7px 8px; text-align: right; font-size: 13px;
  }
  #supplierWhatIfTable th:first-child, #supplierWhatIfTable td:first-child { text-align: left; }
  .supplierWhatIfContract {
    margin-top: 12px; border: 1px solid #dbe3ef; border-radius: 8px; background: #fff; overflow: hidden;
  }
  .supplierWhatIfContract summary {
    cursor: pointer; padding: 9px 10px; font-weight: 700; color: #1f2937;
  }
  #supplierWhatIfRequest {
    margin: 0; max-height: 220px; overflow: auto; background: #0f172a; color: #d8e4ff;
    padding: 10px; font: 12px Consolas, monospace; white-space: pre-wrap;
  }
  #supplierWhatIfCopyRequest {
    margin: 8px 10px 10px 10px; border: 1px solid #cbd5e1; background: #fff; border-radius: 7px;
    padding: 7px 10px; font-weight: 700; cursor: pointer;
  }
  @media (max-width: 1000px) {
    #supplierWhatIfPanel { inset: 16px; }
    .supplierWhatIfBody { grid-template-columns: 1fr; }
    .supplierWhatIfCards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
</style>
<button id="supplierWhatIfButton" type="button">What-if fournisseurs</button>
<div id="supplierWhatIfPanel" aria-hidden="true">
  <div class="supplierWhatIfHeader">
    <div>
      <h2>What-if fournisseurs</h2>
      <p>Exploration interactive de scenarios fournisseur deja simules.</p>
    </div>
    <button class="supplierWhatIfClose" type="button">Fermer</button>
  </div>
  <div class="supplierWhatIfBody">
    <div class="supplierWhatIfControls">
      <div class="supplierWhatIfField">
        <label for="supplierWhatIfSupplier">Fournisseur</label>
        <select id="supplierWhatIfSupplier"></select>
      </div>
      <div class="supplierWhatIfField">
        <label for="supplierWhatIfParameter">Parametre</label>
        <select id="supplierWhatIfParameter"></select>
      </div>
      <div class="supplierWhatIfField">
        <label for="supplierWhatIfLevel">Niveau teste: <span id="supplierWhatIfLevelText"></span></label>
        <input id="supplierWhatIfLevel" type="range" min="0" max="0" value="0" step="1"/>
      </div>
      <div class="supplierWhatIfField">
        <label for="supplierWhatIfKpi">Courbe principale</label>
        <select id="supplierWhatIfKpi"></select>
      </div>
      <div class="supplierWhatIfNote">
        Mode actuel : scenario pre-calcule. Le panneau construit aussi la requete moteur standard,
        mais ne l'envoie pas. Cela garde la carte autonome tout en preparant une execution live future.
      </div>
    </div>
    <div class="supplierWhatIfResults">
      <div id="supplierWhatIfCards" class="supplierWhatIfCards"></div>
      <div id="supplierWhatIfChart"></div>
      <div id="supplierWhatIfCostChart"></div>
      <table id="supplierWhatIfTable"></table>
      <details class="supplierWhatIfContract">
        <summary>Contrat simulation pret pour execution future</summary>
        <pre id="supplierWhatIfRequest"></pre>
        <button id="supplierWhatIfCopyRequest" type="button">Copier la requete</button>
      </details>
    </div>
  </div>
</div>
<script id="supplierWhatIfScript">
const SUPPLIER_WHATIF = __PAYLOAD__;

(function initSupplierWhatIf() {
  const panel = document.getElementById("supplierWhatIfPanel");
  const openBtn = document.getElementById("supplierWhatIfButton");
  const closeBtn = panel.querySelector(".supplierWhatIfClose");
  const supplierSelect = document.getElementById("supplierWhatIfSupplier");
  const parameterSelect = document.getElementById("supplierWhatIfParameter");
  const levelInput = document.getElementById("supplierWhatIfLevel");
  const levelText = document.getElementById("supplierWhatIfLevelText");
  const kpiSelect = document.getElementById("supplierWhatIfKpi");
  const cardsEl = document.getElementById("supplierWhatIfCards");
  const tableEl = document.getElementById("supplierWhatIfTable");
  const requestEl = document.getElementById("supplierWhatIfRequest");
  const copyRequestBtn = document.getElementById("supplierWhatIfCopyRequest");

  function fmt(value, unit) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "n/a";
    if (unit === "%") return (n * 100).toFixed(1) + "%";
    if (unit === "eur") return Math.round(n).toLocaleString("fr-FR") + " EUR";
    if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (Math.abs(n) >= 1000) return Math.round(n).toLocaleString("fr-FR");
    return n.toFixed(2).replace(/\.00$/, "");
  }

  function deltaClass(key, delta) {
    const goodWhenHigh = new Set(["fill_rate", "product_availability", "total_produced"]);
    const isGood = goodWhenHigh.has(key) ? delta >= 0 : delta <= 0;
    return isGood ? "supplierWhatIfDeltaGood" : "supplierWhatIfDeltaBad";
  }

  function availableCases() {
    return SUPPLIER_WHATIF.cases.filter(c =>
      c.supplier_id === supplierSelect.value && c.parameter_group === parameterSelect.value
    ).sort((a, b) => Number(a.level) - Number(b.level));
  }

  function unique(values) {
    return Array.from(new Set(values)).sort();
  }

  function fillSuppliers() {
    supplierSelect.innerHTML = SUPPLIER_WHATIF.suppliers.map(s => `<option value="${s}">${s}</option>`).join("");
    if (SUPPLIER_WHATIF.suppliers.includes("GLOBAL")) supplierSelect.value = "GLOBAL";
  }

  function fillParameters() {
    const supplier = supplierSelect.value;
    const groups = unique(SUPPLIER_WHATIF.cases.filter(c => c.supplier_id === supplier).map(c => c.parameter_group));
    parameterSelect.innerHTML = groups.map(g => `<option value="${g}">${SUPPLIER_WHATIF.parameter_labels[g] || g}</option>`).join("");
  }

  function fillKpis() {
    kpiSelect.innerHTML = SUPPLIER_WHATIF.kpi_fields.map(k => `<option value="${k.key}">${k.label}</option>`).join("");
    kpiSelect.value = "fill_rate";
  }

  function syncLevels() {
    const cases = availableCases();
    levelInput.max = Math.max(0, cases.length - 1);
    levelInput.value = String(Math.min(Number(levelInput.value || 0), cases.length - 1));
    const c = cases[Number(levelInput.value)] || cases[0];
    levelText.textContent = c ? String(c.level) : "n/a";
  }

  function activeCase() {
    const cases = availableCases();
    return cases[Number(levelInput.value)] || cases[0] || null;
  }

  function simulationRequestForCase(c) {
    if (!c) return null;
    return {
      ...SUPPLIER_WHATIF.simulation_request_defaults,
      run_id: `whatif_${c.case_id || c.scenario_id || "scenario"}`,
      overrides: c.request_overrides || {},
      metadata: {
        mode: SUPPLIER_WHATIF.mode || "precomputed",
        source_case_id: c.case_id,
        parameter_group: c.parameter_group,
        parameter_key: c.parameter_key,
        supplier_id: c.supplier_id,
        level: c.level
      }
    };
  }

  function renderCards(c) {
    if (!c) {
      cardsEl.innerHTML = "<div class='supplierWhatIfCard'>Aucun scenario disponible.</div>";
      return;
    }
    const primary = ["fill_rate", "ending_backlog", "production_replanning_count", "total_cost"];
    cardsEl.innerHTML = primary.map(key => {
      const meta = SUPPLIER_WHATIF.kpi_fields.find(k => k.key === key) || {label: key, unit: ""};
      const value = c.kpis[key];
      const base = SUPPLIER_WHATIF.baseline[key];
      const delta = Number(value) - Number(base);
      const deltaText = Number.isFinite(delta) ? (delta >= 0 ? "+" : "") + fmt(delta, meta.unit) : "n/a";
      return `<div class="supplierWhatIfCard">
        <span>${meta.label}</span>
        <b>${fmt(value, meta.unit)}</b>
        <small class="${deltaClass(key, delta)}">vs nominal ${deltaText}</small>
      </div>`;
    }).join("");
  }

  function renderTable(c) {
    if (!c) return;
    tableEl.innerHTML = `<thead><tr><th>KPI</th><th>Nominal</th><th>Scenario</th><th>Delta</th></tr></thead><tbody>` +
      SUPPLIER_WHATIF.kpi_fields.map(meta => {
        const base = SUPPLIER_WHATIF.baseline[meta.key];
        const value = c.kpis[meta.key];
        const delta = Number(value) - Number(base);
        return `<tr>
          <td>${meta.label}</td>
          <td>${fmt(base, meta.unit)}</td>
          <td>${fmt(value, meta.unit)}</td>
          <td class="${deltaClass(meta.key, delta)}">${Number.isFinite(delta) ? (delta >= 0 ? "+" : "") + fmt(delta, meta.unit) : "n/a"}</td>
        </tr>`;
      }).join("") + "</tbody>";
  }

  function renderRequest(c) {
    const request = simulationRequestForCase(c);
    requestEl.textContent = request ? JSON.stringify(request, null, 2) : "Aucune requete disponible.";
  }

  function renderCharts(cases) {
    if (!window.Plotly || !cases.length) return;
    const kpiKey = kpiSelect.value;
    const meta = SUPPLIER_WHATIF.kpi_fields.find(k => k.key === kpiKey) || {label: kpiKey, unit: ""};
    const x = cases.map(c => c.level);
    const selected = activeCase();
    const selectedLevel = selected ? selected.level : null;
    Plotly.newPlot("supplierWhatIfChart", [{
      x, y: cases.map(c => c.kpis[kpiKey]), type: "scatter", mode: "lines+markers",
      name: meta.label, line: {color: "#0f766e", width: 3}
    }, {
      x: [selectedLevel], y: [selected ? selected.kpis[kpiKey] : null], type: "scatter", mode: "markers",
      name: "niveau choisi", marker: {color: "#dc2626", size: 11}
    }], {
      title: `${meta.label} selon niveau fournisseur`,
      margin: {l: 60, r: 20, t: 45, b: 50},
      xaxis: {title: "Niveau teste"},
      yaxis: {title: meta.unit || meta.label}
    }, {displayModeBar: false, responsive: true});

    Plotly.newPlot("supplierWhatIfCostChart", [{
      x, y: cases.map(c => c.kpis.total_cost), type: "scatter", mode: "lines+markers",
      name: "Cout total", line: {color: "#ea580c", width: 3}
    }, {
      x, y: cases.map(c => c.kpis.production_replanning_count), type: "bar",
      name: "Volume replanifie associe", yaxis: "y2", marker: {color: "rgba(37,99,235,.35)"}
    }], {
      title: "Cout total et volume replanifie associe",
      margin: {l: 60, r: 60, t: 45, b: 50},
      xaxis: {title: "Niveau teste"},
      yaxis: {title: "Cout total"},
      yaxis2: {title: "Volume replanifie", overlaying: "y", side: "right", rangemode: "tozero"},
      legend: {orientation: "h"}
    }, {displayModeBar: false, responsive: true});
  }

  function render() {
    syncLevels();
    const cases = availableCases();
    const c = activeCase();
    renderCards(c);
    renderCharts(cases);
    renderTable(c);
    renderRequest(c);
  }

  openBtn.addEventListener("click", () => {
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    setTimeout(render, 30);
  });
  closeBtn.addEventListener("click", () => {
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
  });
  supplierSelect.addEventListener("change", () => { fillParameters(); levelInput.value = "0"; render(); });
  parameterSelect.addEventListener("change", () => { levelInput.value = "0"; render(); });
  levelInput.addEventListener("input", render);
  kpiSelect.addEventListener("change", render);
  copyRequestBtn.addEventListener("click", async () => {
    const text = requestEl.textContent || "";
    if (navigator.clipboard && text) {
      await navigator.clipboard.writeText(text);
      copyRequestBtn.textContent = "Requete copiee";
      setTimeout(() => { copyRequestBtn.textContent = "Copier la requete"; }, 1200);
    }
  });

  fillSuppliers();
  fillParameters();
  fillKpis();
  render();
})();
</script>
"""
    ).replace("__PAYLOAD__", payload_json)


def inject_supplier_what_if(html_text: str, payload: dict[str, Any]) -> str:
    marker = "</body>"
    panel = what_if_panel_html(payload)
    if marker not in html_text:
        raise ValueError("Cannot find </body> marker in HTML.")
    return html_text.replace(marker, panel + "\n" + marker, 1)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    metrics_path = Path(args.metrics)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".supplier_whatif.html")
    html_text = input_path.read_text(encoding="utf-8")
    payload = build_supplier_what_if_payload(
        metrics_path,
        simulation_input=args.simulation_input,
        scenario_id=args.scenario_id,
        days=args.days,
        output_profile=args.output_profile,
    )
    out = inject_supplier_what_if(html_text, payload)
    print(f"[INFO] Input HTML: {input_path} ({input_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"[INFO] What-if cases: {payload['case_count']}")
    print(f"[INFO] Suppliers: {len(payload['suppliers'])}")
    print(f"[INFO] Output estimate: {len(out.encode('utf-8')) / 1024 / 1024:.2f} MB -> {output_path}")
    if not args.execute:
        print("[DRY-RUN] pass --execute to write file")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(out, encoding="utf-8")
    print(f"[OK] Wrote {output_path.resolve()}")


if __name__ == "__main__":
    main()
