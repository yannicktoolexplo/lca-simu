#!/usr/bin/env python3
"""Build and embed compact daily curves for one audited nominal replay.

The helper is deliberately additive: it adds one button and one modal to an
existing autonomous map.  It does not replace or reinterpret any existing map
payload.  The embedded data remain a single simulated realisation, never an
observed history or a Monte-Carlo estimate.
"""

from __future__ import annotations

import csv
import html
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "etudecas.nominal_run_curves.v1"
INJECTION_MARKER = 'data-nominal-run-curves="v1"'
BUTTON_ID = "nominalRunCurvesBtn"
MODAL_ID = "nominalRunCurvesModal"
EXPECTED_SCENARIO_ID = "scn:BASE"
EXPECTED_SEED = 340281
EXPECTED_HORIZON_DAYS = 720
EXPECTED_WARMUP_DAYS = 240


class NominalRunCurvesError(RuntimeError):
    """Raised when the replay or the target map violates the data contract."""


@dataclass(frozen=True)
class ChainSpec:
    """A component-to-product chain selected for the industrial walkthrough."""

    key: str
    label: str
    supplier_id: str
    site_id: str
    component_id: str
    product_id: str
    customer_id: str = "C-XXXXX"


DEFAULT_CHAINS: tuple[ChainSpec, ...] = (
    ChainSpec(
        key="338929_268091",
        label="Composant 338929 vers le produit 268091",
        supplier_id="SDC-VD0914360C",
        site_id="M-1810",
        component_id="item:338929",
        product_id="item:268091",
    ),
    ChainSpec(
        key="344135_268967",
        label="Composant 344135 vers le produit 268967",
        supplier_id="SDC-VD0993480A",
        site_id="M-1430",
        component_id="item:344135",
        product_id="item:268967",
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NominalRunCurvesError(
            f"JSON nominal absent ou invalide: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise NominalRunCurvesError(f"Objet JSON nominal attendu: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            return [dict(row) for row in csv.DictReader(source)]
    except (OSError, UnicodeError, csv.Error) as error:
        raise NominalRunCurvesError(
            f"CSV nominal absent ou invalide: {path}"
        ) from error


def _number(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise NominalRunCurvesError(
            f"Valeur numérique invalide pour {label}: {value!r}"
        ) from error
    if not math.isfinite(number):
        raise NominalRunCurvesError(f"Valeur non finie pour {label}: {value!r}")
    return number


def _day(value: Any, *, label: str) -> int:
    number = _number(value, label=label)
    day = int(number)
    if number != day or day < 0:
        raise NominalRunCurvesError(f"Jour invalide pour {label}: {value!r}")
    return day


def _canonical_item(value: Any) -> str:
    item = str(value or "").strip()
    return item if item.startswith("item:") else f"item:{item}"


def _dense_sum(
    rows: Iterable[Mapping[str, Any]],
    *,
    horizon: int,
    value_field: str,
    label: str,
) -> list[float]:
    values = [0.0] * horizon
    for row in rows:
        day = _day(row.get("day"), label=f"{label}.day")
        if day >= horizon:
            continue
        value = _number(row.get(value_field) or 0.0, label=f"{label}.{value_field}")
        if value < -1e-9:
            raise NominalRunCurvesError(f"Quantité négative pour {label}.{value_field}")
        values[day] += value
    return [round(value, 6) for value in values]


def _dense_unique(
    rows: Iterable[Mapping[str, Any]],
    *,
    horizon: int,
    value_field: str,
    label: str,
) -> list[float]:
    by_day: dict[int, float] = {}
    for row in rows:
        day = _day(row.get("day"), label=f"{label}.day")
        if day >= horizon:
            continue
        if day in by_day:
            raise NominalRunCurvesError(f"Plusieurs états au jour {day} pour {label}")
        value = _number(row.get(value_field) or 0.0, label=f"{label}.{value_field}")
        if value < -1e-9:
            raise NominalRunCurvesError(f"État négatif pour {label}.{value_field}")
        by_day[day] = value
    missing = sorted(set(range(horizon)) - set(by_day))
    if missing:
        raise NominalRunCurvesError(
            f"Trajectoire incomplète pour {label}: {len(missing)} jours absents"
        )
    return [round(by_day[day], 6) for day in range(horizon)]


def _select(
    rows: Iterable[Mapping[str, Any]],
    **conditions: str,
) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        if all(
            str(row.get(field) or "").strip() == expected
            for field, expected in conditions.items()
        ):
            selected.append(row)
    return selected


def _assert_nominal_summary(
    summary: Mapping[str, Any],
    *,
    expected_summary: Mapping[str, Any] | None,
) -> None:
    policy = summary.get("policy") if isinstance(summary.get("policy"), Mapping) else {}
    supplier_risk = (
        policy.get("supplier_risk")
        if isinstance(policy.get("supplier_risk"), Mapping)
        else {}
    )
    state_risk = (
        policy.get("supplier_state_dependent_risk")
        if isinstance(policy.get("supplier_state_dependent_risk"), Mapping)
        else {}
    )
    checks = {
        "scenario_id": (summary.get("scenario_id"), EXPECTED_SCENARIO_ID),
        "sim_days": (summary.get("sim_days"), EXPECTED_HORIZON_DAYS),
        "warmup_days": (summary.get("warmup_days"), EXPECTED_WARMUP_DAYS),
        "seed": (policy.get("seed"), EXPECTED_SEED),
        "supplier_risk.enabled": (supplier_risk.get("enabled"), False),
        "supplier_risk.event_count": (supplier_risk.get("event_count"), 0),
        "supplier_state_dependent_risk.enabled": (state_risk.get("enabled"), False),
        "supplier_state_dependent_risk.generated_event_count": (
            state_risk.get("generated_event_count"),
            0,
        ),
    }
    invalid = [
        name for name, (actual, expected) in checks.items() if actual != expected
    ]
    if invalid:
        details = ", ".join(
            f"{name}={checks[name][0]!r} (attendu {checks[name][1]!r})"
            for name in invalid
        )
        raise NominalRunCurvesError(
            f"Le replay n'est pas la référence nominale attendue: {details}"
        )

    if expected_summary is None:
        return
    comparable_keys = (
        "input_sha256",
        "scenario_id",
        "sim_days",
        "warmup_days",
        "counts",
        "production_tracking",
        "kpis",
    )
    mismatches = [
        key for key in comparable_keys if summary.get(key) != expected_summary.get(key)
    ]
    if mismatches:
        raise NominalRunCurvesError(
            "Le replay ne reproduit pas le résumé de campagne: " + ", ".join(mismatches)
        )


def build_nominal_run_curves_payload(
    replay_dir: Path,
    *,
    expected_summary_path: Path | None = None,
    chains: Sequence[ChainSpec] = DEFAULT_CHAINS,
) -> dict[str, Any]:
    """Read one replay and return a compact, browser-ready trajectory payload."""

    replay_dir = replay_dir.resolve()
    summary = _read_json(replay_dir / "summaries" / "first_simulation_summary.json")
    expected_summary = (
        _read_json(expected_summary_path) if expected_summary_path else None
    )
    _assert_nominal_summary(summary, expected_summary=expected_summary)

    data_dir = replay_dir / "data"
    input_stock_rows = _read_csv(data_dir / "production_input_stocks_daily.csv")
    arrival_rows = _read_csv(
        data_dir / "production_input_replenishment_arrivals_daily.csv"
    )
    shipment_rows = _read_csv(data_dir / "production_supplier_shipments_daily.csv")
    product_rows = _read_csv(data_dir / "production_output_products_daily.csv")
    service_rows = _read_csv(data_dir / "production_demand_service_daily.csv")
    horizon = int(summary["sim_days"])
    days = list(range(horizon))

    chain_payloads: list[dict[str, Any]] = []
    for spec in chains:
        component = _canonical_item(spec.component_id)
        product = _canonical_item(spec.product_id)
        stock_scope = _select(
            input_stock_rows,
            node_id=spec.site_id,
            item_id=component,
        )
        arrival_scope = _select(
            arrival_rows,
            node_id=spec.site_id,
            item_id=component,
        )
        shipment_scope = _select(
            shipment_rows,
            src_node_id=spec.supplier_id,
            dst_node_id=spec.site_id,
            item_id=component,
        )
        product_scope = _select(
            product_rows,
            node_id=spec.site_id,
            item_id=product,
        )
        service_scope = _select(
            service_rows,
            node_id=spec.customer_id,
            item_id=product,
        )
        scopes = {
            "stock matière": stock_scope,
            "réceptions matière": arrival_scope,
            "expéditions fournisseur": shipment_scope,
            "production": product_scope,
            "service client": service_scope,
        }
        empty = [label for label, rows in scopes.items() if not rows]
        if empty:
            raise NominalRunCurvesError(
                f"Séries absentes pour {spec.key}: " + ", ".join(empty)
            )

        series = {
            "component_stock": _dense_unique(
                stock_scope,
                horizon=horizon,
                value_field="stock_end_of_day",
                label=f"{spec.key}.component_stock",
            ),
            "component_receipts": _dense_sum(
                arrival_scope,
                horizon=horizon,
                value_field="arrived_qty",
                label=f"{spec.key}.component_receipts",
            ),
            "component_shipments": _dense_sum(
                shipment_scope,
                horizon=horizon,
                value_field="shipped_qty",
                label=f"{spec.key}.component_shipments",
            ),
            "product_released": _dense_unique(
                product_scope,
                horizon=horizon,
                value_field="released_qty",
                label=f"{spec.key}.product_released",
            ),
            "product_stock": _dense_unique(
                product_scope,
                horizon=horizon,
                value_field="stock_end_of_day",
                label=f"{spec.key}.product_stock",
            ),
            "customer_demand": _dense_unique(
                service_scope,
                horizon=horizon,
                value_field="demand_qty",
                label=f"{spec.key}.customer_demand",
            ),
            "customer_served": _dense_unique(
                service_scope,
                horizon=horizon,
                value_field="served_qty",
                label=f"{spec.key}.customer_served",
            ),
            "customer_backlog": _dense_unique(
                service_scope,
                horizon=horizon,
                value_field="backlog_end_qty",
                label=f"{spec.key}.customer_backlog",
            ),
        }
        total_demand = sum(series["customer_demand"])
        total_served = sum(series["customer_served"])
        service_rate = (
            100.0 if total_demand <= 1e-12 else 100.0 * total_served / total_demand
        )
        chain_payloads.append(
            {
                "key": spec.key,
                "label": spec.label,
                "supplier_id": spec.supplier_id,
                "site_id": spec.site_id,
                "component_id": component.removeprefix("item:"),
                "product_id": product.removeprefix("item:"),
                "customer_id": spec.customer_id,
                "days": days,
                "series": series,
                "summary": {
                    "component_stock_min": round(min(series["component_stock"]), 6),
                    "component_stock_zero_days": sum(
                        value <= 1e-9 for value in series["component_stock"]
                    ),
                    "component_shipments_total": round(
                        sum(series["component_shipments"]), 6
                    ),
                    "component_receipts_total": round(
                        sum(series["component_receipts"]), 6
                    ),
                    "product_released_total": round(sum(series["product_released"]), 6),
                    "customer_demand_total": round(total_demand, 6),
                    "customer_served_total": round(total_served, 6),
                    "customer_service_rate_pct": round(service_rate, 6),
                    "customer_backlog_max": round(max(series["customer_backlog"]), 6),
                },
            }
        )

    if not chain_payloads:
        raise NominalRunCurvesError("Aucune chaîne nominale sélectionnée.")

    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "status": "simule_une_realisation_nominale",
        "scenario_id": summary["scenario_id"],
        "seed": summary["policy"]["seed"],
        "horizon_days": horizon,
        "warmup_days": int(summary["warmup_days"]),
        "supplier_incident_enabled": False,
        "supplier_state_dependent_risk_enabled": False,
        "simulated_global_service_rate_pct": round(
            100.0 * _number(summary["kpis"]["fill_rate"], label="fill_rate"), 6
        ),
        "chain_count": len(chain_payloads),
        "chains": chain_payloads,
    }


def compact_trajectory_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten the embedded payload to one compact row per chain and day."""

    rows: list[dict[str, Any]] = []
    for chain in payload.get("chains") or []:
        series = chain.get("series") or {}
        days = chain.get("days") or []
        for position, day in enumerate(days):
            rows.append(
                {
                    "chain_key": chain["key"],
                    "day": day,
                    "supplier_id": chain["supplier_id"],
                    "site_id": chain["site_id"],
                    "component_id": chain["component_id"],
                    "product_id": chain["product_id"],
                    "component_stock_end_qty": series["component_stock"][position],
                    "component_shipments_qty": series["component_shipments"][position],
                    "component_receipts_qty": series["component_receipts"][position],
                    "product_released_qty": series["product_released"][position],
                    "product_stock_end_qty": series["product_stock"][position],
                    "customer_demand_qty": series["customer_demand"][position],
                    "customer_served_qty": series["customer_served"][position],
                    "customer_backlog_end_qty": series["customer_backlog"][position],
                }
            )
    return rows


_STYLE = r"""
<style data-nominal-run-curves="v1">
  .nominalCurvesModal{position:fixed;inset:0;z-index:120000;background:rgba(15,23,42,.62);display:none;align-items:center;justify-content:center;padding:20px}
  .nominalCurvesModal.visible{display:flex}
  .nominalCurvesDialog{width:min(1500px,98vw);height:min(920px,96vh);overflow:auto;background:#f8fafc;border-radius:18px;box-shadow:0 28px 80px rgba(15,23,42,.34);border:1px solid #cbd5e1}
  .nominalCurvesHeader{position:sticky;top:0;z-index:3;background:#fff;border-bottom:1px solid #dbe4ef;padding:16px 20px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
  .nominalCurvesTitle{font:800 21px/1.25 "Segoe UI",Arial,sans-serif;color:#0f172a}
  .nominalCurvesSub{font:500 13px/1.45 "Segoe UI",Arial,sans-serif;color:#475569;margin-top:4px}
  .nominalCurvesClose{border:1px solid #cbd5e1;border-radius:10px;background:#fff;color:#0f172a;padding:8px 12px;cursor:pointer;font-weight:700}
  .nominalCurvesBody{padding:18px 20px 24px;font-family:"Segoe UI",Arial,sans-serif}
  .nominalCurvesNotice{border-left:5px solid #2563eb;background:#eff6ff;color:#1e3a8a;border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.5;margin-bottom:14px}
  .nominalCurvesControls{display:flex;align-items:end;gap:14px;flex-wrap:wrap;background:#fff;border:1px solid #dbe4ef;border-radius:12px;padding:12px 14px;margin-bottom:14px}
  .nominalCurvesControls label{display:grid;gap:5px;color:#334155;font-size:12px;font-weight:700}
  .nominalCurvesControls select{min-width:310px;border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:8px 10px;color:#0f172a}
  .nominalSmoothButtons{display:flex;gap:6px;flex-wrap:wrap}
  .nominalSmoothBtn{border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#334155;padding:7px 11px;cursor:pointer;font-weight:700}
  .nominalSmoothBtn.active{background:#0f766e;color:#fff;border-color:#0f766e}
  .nominalCurvesStats{display:grid;grid-template-columns:repeat(5,minmax(135px,1fr));gap:10px;margin:0 0 14px}
  .nominalCurvesStat{background:#fff;border:1px solid #dbe4ef;border-radius:11px;padding:10px 12px}
  .nominalCurvesStat span{display:block;color:#64748b;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
  .nominalCurvesStat strong{display:block;color:#0f172a;font-size:18px;margin-top:5px}
  .nominalCurvesGrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .nominalCurveCard{background:#fff;border:1px solid #dbe4ef;border-radius:13px;padding:10px;min-width:0}
  .nominalCurveChart{height:310px;width:100%}
  .nominalCurveExplain{color:#475569;font-size:12px;line-height:1.45;padding:4px 7px 6px}
  @media(max-width:900px){.nominalCurvesGrid{grid-template-columns:1fr}.nominalCurvesStats{grid-template-columns:repeat(2,minmax(120px,1fr))}.nominalCurvesControls select{min-width:min(310px,80vw)}}
</style>
"""


_MODAL = r"""
<div id="nominalRunCurvesModal" class="nominalCurvesModal" role="dialog" aria-modal="true" aria-labelledby="nominalRunCurvesTitle" data-nominal-run-curves="v1">
  <div class="nominalCurvesDialog">
    <div class="nominalCurvesHeader">
      <div><div id="nominalRunCurvesTitle" class="nominalCurvesTitle">Courbes du run nominal actuel</div><div class="nominalCurvesSub">Stocks, flux matière, production et service client — J0 à J719</div></div>
      <button id="nominalRunCurvesClose" class="nominalCurvesClose" type="button">Fermer</button>
    </div>
    <div class="nominalCurvesBody">
      <div class="nominalCurvesNotice"><strong>SIMULÉ — une seule réalisation nominale illustrative.</strong> Aucun incident fournisseur n’est injecté et la couche de risque fournisseur dépendante de l’état est désactivée dans ce run. Ces courbes décrivent la référence du moteur ; elles ne sont ni des données observées, ni une moyenne de plusieurs simulations.</div>
      <div class="nominalCurvesControls">
        <label>Chaîne affichée<select id="nominalRunChainSelect"></select></label>
        <label>Lissage des courbes<div class="nominalSmoothButtons"><button class="nominalSmoothBtn active" type="button" data-nominal-smooth="adapted">Adapté</button><button class="nominalSmoothBtn" type="button" data-nominal-smooth="raw">Brut</button><button class="nominalSmoothBtn" type="button" data-nominal-smooth="7">7 jours</button><button class="nominalSmoothBtn" type="button" data-nominal-smooth="28">28 jours</button></div></label>
      </div>
      <div id="nominalRunCurvesStats" class="nominalCurvesStats"></div>
      <div class="nominalCurvesGrid">
        <div class="nominalCurveCard"><div id="nominalComponentStockChart" class="nominalCurveChart"></div><div class="nominalCurveExplain">État du stock de composant disponible en fin de journée. Le lissage adapté utilise 7 jours pour conserver les passages proches de la rupture.</div></div>
        <div class="nominalCurveCard"><div id="nominalComponentFlowChart" class="nominalCurveChart"></div><div class="nominalCurveExplain">Expéditions quittant le fournisseur et réceptions arrivant à l’usine. Le décalage entre les deux traduit le transport ; la moyenne de 28 jours rend les lots visibles sans effacer la tendance.</div></div>
        <div class="nominalCurveCard"><div id="nominalProductChart" class="nominalCurveChart"></div><div class="nominalCurveExplain">Unités de produit fini libérées et stock disponible. La production est moyennée sur 28 jours ; le stock sur 7 jours dans le mode adapté.</div></div>
        <div class="nominalCurveCard"><div id="nominalCustomerChart" class="nominalCurveChart"></div><div class="nominalCurveExplain">Demande, quantité servie et retard restant. Le taux de service est recalculé sur une fenêtre glissante, à partir des sommes servies et demandées.</div></div>
      </div>
    </div>
  </div>
</div>
"""


_SCRIPT_TEMPLATE = r"""
<script data-nominal-run-curves="v1">
const NOMINAL_RUN_CURVES = __PAYLOAD__;
(() => {
  const button = document.getElementById("nominalRunCurvesBtn");
  const modal = document.getElementById("nominalRunCurvesModal");
  const closeButton = document.getElementById("nominalRunCurvesClose");
  const chainSelect = document.getElementById("nominalRunChainSelect");
  const stats = document.getElementById("nominalRunCurvesStats");
  if (!button || !modal || !closeButton || !chainSelect || !stats) return;
  let smoothing = "adapted";
  const plotConfig = {responsive:true,displaylogo:false,modeBarButtonsToRemove:["lasso2d","select2d"]};
  const formatQty = value => new Intl.NumberFormat("fr-FR", {maximumFractionDigits:0}).format(Number(value || 0));
  const rollingMean = (values, windowSize) => {
    if (windowSize <= 1) return values.map(Number);
    let sum = 0;
    return values.map((raw, index) => {
      sum += Number(raw || 0);
      if (index >= windowSize) sum -= Number(values[index - windowSize] || 0);
      return sum / Math.min(index + 1, windowSize);
    });
  };
  const rollingService = (served, demand, windowSize) => {
    let sumServed = 0;
    let sumDemand = 0;
    return demand.map((raw, index) => {
      sumServed += Number(served[index] || 0);
      sumDemand += Number(raw || 0);
      if (index >= windowSize) {
        sumServed -= Number(served[index - windowSize] || 0);
        sumDemand -= Number(demand[index - windowSize] || 0);
      }
      return sumDemand > 1e-12 ? 100 * sumServed / sumDemand : null;
    });
  };
  const windowFor = adaptedWindow => smoothing === "adapted" ? adaptedWindow : smoothing === "raw" ? 1 : Number(smoothing);
  const line = (name, x, values, color, adaptedWindow, extra={}) => {
    const windowSize = windowFor(adaptedWindow);
    const suffix = windowSize > 1 ? ` — moy. ${windowSize} j` : " — brut";
    return {type:"scatter",mode:"lines",name:name + suffix,x,y:rollingMean(values,windowSize),line:{color,width:2.2},hovertemplate:`${name}<br>J%{x}<br>%{y:,.1f}<extra></extra>`,...extra};
  };
  const layout = (title, yTitle, extra={}) => ({title:{text:title,font:{size:14}},margin:{l:64,r:24,t:48,b:48},paper_bgcolor:"#fff",plot_bgcolor:"#fff",xaxis:{title:"Jour simulé",gridcolor:"#e2e8f0"},yaxis:{title:yTitle,gridcolor:"#e2e8f0",rangemode:"tozero"},legend:{orientation:"h",y:-.23},hovermode:"x unified",...extra});
  const currentChain = () => NOMINAL_RUN_CURVES.chains.find(chain => chain.key === chainSelect.value) || NOMINAL_RUN_CURVES.chains[0];
  const stat = (label, value) => `<div class="nominalCurvesStat"><span>${label}</span><strong>${value}</strong></div>`;
  function render() {
    const chain = currentChain();
    if (!chain || !window.Plotly) return;
    const s = chain.series;
    const d = chain.days;
    const sum = chain.summary;
    stats.innerHTML = [
      stat("Service client", `${Number(sum.customer_service_rate_pct).toFixed(2).replace(".",",")} %`),
      stat("Retard client maximal", `${formatQty(sum.customer_backlog_max)} UN`),
      stat("Stock composant minimal", `${formatQty(sum.component_stock_min)} UN`),
      stat("Jours stock composant nul", formatQty(sum.component_stock_zero_days)),
      stat("Produit libéré", `${formatQty(sum.product_released_total)} UN`),
    ].join("");
    Plotly.react("nominalComponentStockChart", [line(`Stock composant ${chain.component_id}`, d, s.component_stock, "#0f766e", 7)], layout(`Stock ${chain.component_id} à ${chain.site_id}`, "Unités"), plotConfig);
    Plotly.react("nominalComponentFlowChart", [
      line("Expédié par le fournisseur", d, s.component_shipments, "#2563eb", 28),
      line("Reçu à l’usine", d, s.component_receipts, "#d97706", 28),
    ], layout(`${chain.supplier_id} → ${chain.site_id}`, "Unités par jour"), plotConfig);
    Plotly.react("nominalProductChart", [
      line(`Production ${chain.product_id} libérée`, d, s.product_released, "#7c3aed", 28),
      line("Stock produit fini", d, s.product_stock, "#0891b2", 7),
    ], layout(`Production et stock du produit ${chain.product_id}`, "Unités"), plotConfig);
    const serviceWindow = windowFor(28);
    const serviceValues = rollingService(s.customer_served, s.customer_demand, serviceWindow);
    const serviceSuffix = serviceWindow > 1 ? `${serviceWindow} j` : "journalier";
    Plotly.react("nominalCustomerChart", [
      line("Demande client", d, s.customer_demand, "#64748b", 28),
      line("Quantité servie", d, s.customer_served, "#16a34a", 28),
      line("Retard restant", d, s.customer_backlog, "#dc2626", 7),
      {type:"scatter",mode:"lines",name:`Taux de service ${serviceSuffix}`,x:d,y:serviceValues,yaxis:"y2",line:{color:"#111827",width:2,dash:"dot"},hovertemplate:"Service<br>J%{x}<br>%{y:.2f}%<extra></extra>"},
    ], layout(`Service client du produit ${chain.product_id}`, "Unités", {yaxis2:{title:"Service (%)",overlaying:"y",side:"right",range:[0,102],showgrid:false}}), plotConfig);
  }
  function open() { modal.classList.add("visible"); document.body.style.overflow="hidden"; render(); }
  function close() { modal.classList.remove("visible"); document.body.style.overflow=""; }
  function syncVisibility() { button.hidden = !document.getElementById("modeOps")?.classList.contains("active"); }
  NOMINAL_RUN_CURVES.chains.forEach(chain => {
    const option = document.createElement("option"); option.value=chain.key; option.textContent=chain.label; chainSelect.appendChild(option);
  });
  button.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  modal.addEventListener("click", event => { if (event.target === modal) close(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && modal.classList.contains("visible")) close(); });
  chainSelect.addEventListener("change", render);
  document.querySelectorAll("[data-nominal-smooth]").forEach(smoothButton => smoothButton.addEventListener("click", () => {
    smoothing = smoothButton.dataset.nominalSmooth || "adapted";
    document.querySelectorAll("[data-nominal-smooth]").forEach(candidate => candidate.classList.toggle("active", candidate === smoothButton));
    render();
  }));
  document.querySelectorAll(".modeBtn").forEach(modeButton => modeButton.addEventListener("click", () => setTimeout(syncVisibility, 0)));
  window.addEventListener("resize", () => { if (modal.classList.contains("visible")) render(); });
  syncVisibility();
})();
</script>
"""


def inject_nominal_run_curves(document: str, payload: Mapping[str, Any]) -> str:
    """Add the nominal-curves modal to an already rendered autonomous map."""

    if INJECTION_MARKER in document or BUTTON_ID in document or MODAL_ID in document:
        raise NominalRunCurvesError("Les courbes nominales sont déjà injectées.")
    if (
        "Plotly" not in document
        or "</head>" not in document
        or "</body>" not in document
    ):
        raise NominalRunCurvesError("Structure de carte autonome invalide.")
    if not payload.get("available") or not payload.get("chains"):
        raise NominalRunCurvesError("Payload de courbes nominales vide.")

    anchor = re.search(
        r'(<button\s+id=["\']kpiTreeBtn["\'][^>]*>.*?</button>)',
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if anchor is None:
        raise NominalRunCurvesError("Ancrage Run nominal de la carte introuvable.")
    button = (
        '<button id="nominalRunCurvesBtn" class="tableBtn" type="button" '
        'title="Afficher les trajectoires réellement exportées du run nominal actuel." '
        f"{INJECTION_MARKER}>Courbes du run nominal actuel</button>"
    )
    document = document[: anchor.end()] + "\n      " + button + document[anchor.end() :]
    document = document.replace("</head>", _STYLE + "</head>", 1)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    script = _SCRIPT_TEMPLATE.replace("__PAYLOAD__", serialized)
    document = document.replace("</body>", _MODAL + script + "</body>", 1)
    if document.count(INJECTION_MARKER) != 4:
        raise NominalRunCurvesError("Injection nominale incomplète.")
    return document


def csv_fieldnames() -> list[str]:
    return [
        "chain_key",
        "day",
        "supplier_id",
        "site_id",
        "component_id",
        "product_id",
        "component_stock_end_qty",
        "component_shipments_qty",
        "component_receipts_qty",
        "product_released_qty",
        "product_stock_end_qty",
        "customer_demand_qty",
        "customer_served_qty",
        "customer_backlog_end_qty",
    ]


def render_payload_summary_html(payload: Mapping[str, Any]) -> str:
    """Return a small, escaped status line for a parent delivery page."""

    return (
        f"<strong>{int(payload['chain_count'])} chaînes</strong> — "
        f"{int(payload['horizon_days'])} jours, une réalisation simulée, "
        f"graine {html.escape(str(payload['seed']))}."
    )
