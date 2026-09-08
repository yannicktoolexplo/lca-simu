#!/usr/bin/env python3
"""Run and extract a 2-by-2 state-dependent supplier-cascade pilot.

The pilot crosses a dated delay (absent/present) with the endogenous
state-dependent rules (disabled/enabled).  All four calculations reuse the
same seed, initialisation, graph and policies.  The engine command is derived
from the completed network-screen campaign so that the pilot cannot silently
drift from the main supply-chain configuration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import subprocess
import sys
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_REFERENCE_LOG = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\supplier_network_risk_screen_20260902_v2\cases"
    r"\sdc_vd0914360c_338929_m_1810__transport_delay__120"
    r"\seed_340281\campaign_engine.log"
)
DEFAULT_RISK_CSV = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\supplier_network_risk_screen_20260902_v2\inputs\risk_events"
    r"\sdc_vd0914360c_338929_m_1810__transport_delay__120.csv"
)
DEFAULT_FAMILIES = (
    "stock",
    "capacity",
    "lead",
    "availability",
    "upstream",
    "reliability",
    "cost",
)
FORBIDDEN_FAMILY = "quality"
TARGET_SUPPLIER = "SDC-VD0914360C"
TARGET_FACTORY = "M-1810"
TARGET_COMPONENT = "item:338929"
TARGET_PRODUCT = "item:268091"
TARGET_CUSTOMER = "C-XXXXX"
PRIMARY_EVENT_PREFIX = "sdc_vd0914360c_338929_m_1810__transport_delay__120"


@dataclass(frozen=True)
class PairCase:
    key: str
    label_fr: str
    risk_csv: Path | None
    state_enabled: bool


CASES = (
    PairCase(
        "state_off_nominal",
        "Sans regles dependantes de l'etat, sans incident impose",
        None,
        False,
    ),
    PairCase(
        "delay_only_state_off",
        "Sans regles dependantes de l'etat, avec retard impose sur 338929",
        DEFAULT_RISK_CSV,
        False,
    ),
    PairCase(
        "state_only",
        "Regles dependantes de l'etat, sans incident impose",
        None,
        True,
    ),
    PairCase(
        "state_plus_delay",
        "Regles dependantes de l'etat, avec retard impose sur 338929",
        DEFAULT_RISK_CSV,
        True,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def command_from_log(path: Path) -> list[str]:
    commands: list[list[str]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        marker = "COMMAND "
        if marker not in line:
            continue
        payload = line.split(marker, 1)[1]
        parsed = json.loads(payload)
        if not isinstance(parsed, list) or len(parsed) < 2:
            raise ValueError(f"Invalid command payload in {path}")
        commands.append([str(value) for value in parsed])
    if not commands:
        raise ValueError(f"No recorded engine command in {path}")
    return commands[-1]


def remove_option(command: Sequence[str], option: str, *, takes_value: bool) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(command):
        if command[index] == option:
            index += 2 if takes_value else 1
            continue
        output.append(command[index])
        index += 1
    return output


def replace_option(command: Sequence[str], option: str, value: str) -> list[str]:
    output = remove_option(command, option, takes_value=True)
    output.extend((option, value))
    return output


def build_case_command(
    reference_command: Sequence[str],
    *,
    case: PairCase,
    output_dir: Path,
    days: int,
    seed: int,
    families: Sequence[str],
    engine_path: Path | None = None,
) -> list[str]:
    command = list(reference_command)
    command[0] = sys.executable
    if engine_path is not None:
        command[1] = str(engine_path.resolve())
    for flag in (
        "--supplier-state-dependent-risks",
        "--no-supplier-state-dependent-risks",
    ):
        command = remove_option(command, flag, takes_value=False)
    command = remove_option(
        command, "--supplier-state-risk-families", takes_value=True
    )
    command = remove_option(command, "--supplier-risk-events-csv", takes_value=True)
    command = replace_option(command, "--output-dir", str(output_dir.resolve()))
    command = replace_option(command, "--days", str(days))
    command = replace_option(command, "--seed", str(seed))
    command = replace_option(
        command, "--supplier-state-risk-observation-warmup-days", "30"
    )
    command.extend(
        (
            (
                "--supplier-state-dependent-risks"
                if case.state_enabled
                else "--no-supplier-state-dependent-risks"
            ),
            "--supplier-state-risk-families",
            ",".join(families),
        )
    )
    if case.risk_csv is not None:
        command.extend(("--supplier-risk-events-csv", str(case.risk_csv.resolve())))
    return command


def validate_families(families: Sequence[str]) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(value.strip().casefold() for value in families if value.strip()))
    if not cleaned:
        raise ValueError("At least one state-risk family is required")
    if FORBIDDEN_FAMILY in cleaned:
        raise ValueError("The excluded risk family must not be enabled")
    unexpected = sorted(set(cleaned) - set(DEFAULT_FAMILIES))
    if unexpected:
        raise ValueError(f"Unsupported family in this pilot: {unexpected}")
    return cleaned


def validate_primary_risk(path: Path) -> tuple[int, int, str]:
    rows = read_csv_rows(path)
    if len(rows) != 1:
        raise ValueError("The causal pilot requires exactly one imposed incident")
    row = rows[0]
    exact_scope = (
        row.get("supplier_id") == TARGET_SUPPLIER
        and row.get("item_id") == TARGET_COMPONENT
        and row.get("dst_node_id") == TARGET_FACTORY
        and row.get("risk_type") == "lead_time_extra_days"
        and math.isclose(finite(row.get("multiplier")), 120.0, abs_tol=1e-12)
    )
    if not exact_scope:
        raise ValueError("The imposed incident does not match the frozen 338929 delay")
    event_id = str(row.get("event_id") or "")
    if not event_id.startswith(PRIMARY_EVENT_PREFIX):
        raise ValueError("Unexpected primary event identifier")
    return int(row["start_day"]), int(row["end_day"]), event_id


def service_metrics(rows: Iterable[Mapping[str, Any]], *, days: int) -> dict[str, float]:
    demand = 0.0
    on_due = 0.0
    backlog_qty_days = 0.0
    ending_backlog = 0.0
    observed_days: set[int] = set()
    for row in rows:
        if row.get("node_id") != TARGET_CUSTOMER or row.get("item_id") != TARGET_PRODUCT:
            continue
        day = int(finite(row.get("day"), -1.0))
        if day < 0 or day >= days:
            continue
        daily_demand = max(0.0, finite(row.get("demand_qty")))
        required = max(daily_demand, finite(row.get("required_with_backlog_qty")))
        served = max(0.0, finite(row.get("served_qty")))
        starting_backlog = max(0.0, required - daily_demand)
        demand += daily_demand
        on_due += min(daily_demand, max(0.0, served - starting_backlog))
        ending_backlog = max(0.0, finite(row.get("backlog_end_qty")))
        backlog_qty_days += ending_backlog
        observed_days.add(day)
    if observed_days != set(range(days)):
        raise ValueError("Incomplete daily service series for finished product 268091")
    return {
        "demand_qty": demand,
        "on_due_qty": on_due,
        "on_due_service": on_due / demand if demand else 1.0,
        "backlog_qty_days": backlog_qty_days,
        "ending_backlog_qty": ending_backlog,
    }


def filtered_rows(
    path: Path,
    *,
    node_id: str,
    item_id: str,
) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv_rows(path)
        if row.get("node_id") == node_id and row.get("item_id") == item_id
    ]


def series_by_day(rows: Iterable[Mapping[str, Any]], field: str) -> dict[int, float]:
    return {
        int(finite(row.get("day"), -1.0)): finite(row.get(field))
        for row in rows
        if int(finite(row.get("day"), -1.0)) >= 0
    }


def first_divergence_day(
    left: Mapping[int, float],
    right: Mapping[int, float],
    *,
    start_day: int,
    tolerance: float = 1e-9,
) -> int | None:
    for day in sorted(set(left) & set(right)):
        if day < start_day:
            continue
        if not math.isclose(
            float(left[day]), float(right[day]), rel_tol=0.0, abs_tol=tolerance
        ):
            return day
    return None


def state_event_signature(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(row.get(field) or "")
        for field in (
            "risk_family",
            "trigger_metric",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
        )
    )


def audit_state_rows(rows: Sequence[Mapping[str, Any]], families: Sequence[str]) -> None:
    allowed = set(families)
    for row in rows:
        family = str(row.get("risk_family") or "").casefold()
        if family not in allowed:
            raise ValueError(f"State event outside pilot allowlist: {family!r}")
        searchable = " ".join(
            str(row.get(field) or "")
            for field in ("event_id", "risk_family", "risk_type", "trigger_metric", "effect", "notes")
        ).casefold()
        if FORBIDDEN_FAMILY in searchable:
            raise ValueError("Excluded risk branch detected in a state-event row")


def event_aggregates(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, ...], dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[state_event_signature(row)].append(row)
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    for signature, group in grouped.items():
        trigger_days = sorted(int(finite(row.get("trigger_day"), -1.0)) for row in group)
        result[signature] = {
            "count": len(group),
            "first_trigger_day": trigger_days[0],
            "last_trigger_day": trigger_days[-1],
            "event_ids": [str(row.get("event_id") or "") for row in group],
            "effect": str(group[0].get("effect") or ""),
        }
    return result


def output_lot_exposure(
    genealogy_rows: Sequence[Mapping[str, Any]],
    *,
    primary_event_id: str,
    incremental_state_event_ids: set[str],
) -> list[dict[str, Any]]:
    parents: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    output_lots: dict[str, Mapping[str, Any]] = {}
    for row in genealogy_rows:
        child = str(row.get("child_lot_id") or "")
        if child:
            parents[child].append(row)
        if (
            row.get("child_node_id") == TARGET_FACTORY
            and row.get("child_item_id") == TARGET_PRODUCT
            and row.get("link_type") == "production"
        ):
            output_lots[child] = row

    exposures: list[dict[str, Any]] = []
    for output_lot_id, output_row in output_lots.items():
        queue: deque[str] = deque((output_lot_id,))
        visited: set[str] = set()
        ancestor_rows: list[Mapping[str, Any]] = []
        while queue:
            child = queue.popleft()
            if child in visited:
                continue
            visited.add(child)
            for row in parents.get(child, ()):  # One row per parent allocation.
                ancestor_rows.append(row)
                parent = str(row.get("parent_lot_id") or "")
                if parent:
                    queue.append(parent)
        risk_ids: set[str] = set()
        for row in ancestor_rows:
            risk_ids.update(
                value.strip()
                for value in str(row.get("risk_event_ids") or "").split(",")
                if value.strip()
            )
        primary = primary_event_id in risk_ids
        secondary_ids = sorted(risk_ids & incremental_state_event_ids)
        if not primary and not secondary_ids:
            continue
        exposures.append(
            {
                "finished_product_lot_id": output_lot_id,
                "release_day": int(finite(output_row.get("day"), -1.0)),
                "released_qty": finite(output_row.get("child_qty")),
                "primary_delay_in_ancestry": primary,
                "incremental_state_events_in_ancestry": ",".join(secondary_ids),
                "ancestor_lot_count": max(0, len(visited) - 1),
            }
        )
    return sorted(exposures, key=lambda row: (row["release_day"], row["finished_product_lot_id"]))


def build_offline_html(
    *,
    summary: Mapping[str, Any],
    metric_rows: Sequence[Mapping[str, Any]],
    curve_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    lot_rows: Sequence[Mapping[str, Any]],
) -> str:
    payload = {
        "summary": summary,
        "metrics": list(metric_rows),
        "curves": list(curve_rows),
        "events": [
            row
            for row in event_rows
            if int(row.get("incremental_count") or 0) != 0
            or row.get("first_trigger_shift_days") not in ("", 0, "0")
        ],
        "lots": list(lot_rows[:50]),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    pair = summary["pair_results"]
    metrics = {str(row["case"]): row for row in metric_rows}
    off_nominal = metrics["state_off_nominal"]
    off_delayed = metrics["delay_only_state_off"]
    state_only = metrics["state_only"]
    delayed = metrics["state_plus_delay"]

    def percent(value: Any, *, signed: bool = False) -> str:
        pattern = "+.2f" if signed else ".2f"
        return html.escape(format(finite(value), pattern).replace(".", ","))

    off_loss = percent(pair["service_loss_points_state_off"])
    on_loss = percent(pair["service_loss_points_state_on"])
    amplification = percent(pair["service_loss_amplification_points"])
    divergence = pair.get("first_divergence_days") or {}
    primary_qty = f"{finite(delayed['primary_event_pulled_qty']):,.0f}".replace(",", " ")

    def day_label(value: Any) -> str:
        return "aucun écart" if value is None else f"J{int(value)}"

    incident = summary["incident_window"]
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cascade dynamique 338929 vers 268091</title>
<style>
:root{{--ink:#10213d;--muted:#60708a;--line:#dbe4ef;--blue:#1769ff;--red:#df382c;--green:#12845c;--paper:#f4f7fb}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1440px;margin:auto;padding:24px}} h1{{font-size:30px;margin:0 0 6px}} h2{{font-size:21px;margin:0 0 12px}} p{{margin:6px 0}}
.lead{{color:var(--muted);font-size:17px;max-width:1050px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:20px 0}}
.card,.panel{{background:white;border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 24px #18355b0b}} .card{{padding:16px}}
.k{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}} .v{{font-size:27px;font-weight:750;margin-top:3px}} .s{{font-size:13px;color:var(--muted)}}
.panel{{padding:18px;margin:14px 0}} .chain{{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:15px 0}} .node{{padding:8px 12px;background:#edf4ff;border-radius:999px;font-weight:650}} .arrow{{color:var(--blue);font-size:20px}}
.legend{{display:flex;gap:18px;color:var(--muted);font-size:13px;margin-bottom:8px}} .dot{{display:inline-block;width:11px;height:3px;vertical-align:middle;margin-right:5px}} canvas{{width:100%;height:245px;display:block}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} th{{color:var(--muted);font-weight:650}}
.pill{{display:inline-block;padding:5px 9px;border-radius:999px;background:#fff0ef;color:#ad241d;font-size:12px}} .note{{padding:12px 14px;border-left:4px solid var(--blue);background:#eef5ff;border-radius:8px}}
.ok{{color:var(--green);font-weight:700}} .empty{{color:var(--muted);font-style:italic}} footer{{color:var(--muted);font-size:12px;margin-top:16px}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,1fr)}}}} @media(max-width:540px){{.grid{{grid-template-columns:1fr}}main{{padding:12px}}}}
</style>
</head>
<body><main>
<div class="pill">Résultat simulé · comparaison à conditions identiques</div>
<h1>Cascade dynamique : 338929 → M-1810 → 268091</h1>
<p class="lead"><strong>Hypothèse testée :</strong> un retard de 120 jours sur la liaison du composant 338929, de J{incident['start_day']} à J{incident['end_day']}. Ce n'est pas un incident observé en 2025. Quatre calculs séparent l'effet du retard de celui des règles qui réagissent à l'état du réseau ; chaque comparaison conserve le même état initial et la même série de tirages aléatoires.</p>
<p class="s">Incident effectivement appliqué dans les deux calculs perturbés : <strong>{int(off_delayed['primary_event_shipment_count'])} expédition(s)</strong> sans règles dynamiques et <strong>{int(delayed['primary_event_shipment_count'])}</strong> avec ces règles ; {primary_qty} unités commandées sont concernées dans le second calcul.</p>
<div class="chain"><span class="node">Fournisseur SDC-VD0914360C</span><span class="arrow">→</span><span class="node">Composant 338929</span><span class="arrow">→</span><span class="node">Usine M-1810</span><span class="arrow">→</span><span class="node">Produit 268091</span><span class="arrow">→</span><span class="node">Client</span></div>
<p class="note"><strong>Chronologie calculée :</strong> premier écart de stock {day_label(divergence.get('component_stock'))} → première différence de production {day_label(divergence.get('production_release'))} → première différence de service client {day_label(divergence.get('on_due_service'))} → premier écart de retard accumulé {day_label(divergence.get('backlog'))}.</p>
<section class="grid">
 <div class="card"><div class="k">Perte due au retard · règles inactives</div><div class="v">−{off_loss} pts</div><div class="s">{percent(off_nominal['service_268091_pct'])} % → {percent(off_delayed['service_268091_pct'])} %</div></div>
 <div class="card"><div class="k">Perte due au retard · règles actives</div><div class="v">−{on_loss} pts</div><div class="s">{percent(state_only['service_268091_pct'])} % → {percent(delayed['service_268091_pct'])} %</div></div>
 <div class="card"><div class="k">Amplification liée aux règles dynamiques</div><div class="v">+{amplification} pts</div><div class="s">perte de service supplémentaire dans cette répétition</div></div>
 <div class="card"><div class="k">Nouveaux signaux sur 338929</div><div class="v">{int(pair['new_target_chain_state_signal_count'])}</div><div class="s">{int(pair['new_target_chain_state_signal_group_count'])} types absents sans le retard, dès J{pair['first_new_target_chain_state_signal_day']}</div></div>
 <div class="card"><div class="k">Lots 268091 reliés</div><div class="v">{int(pair['finished_product_lots_with_primary_or_incremental_signal_ancestry'])}</div><div class="s">généalogie simulée portant l'incident ou un nouveau signal</div></div>
</section>
<section class="panel"><h2>1. Le stock du composant transmet-il le choc ?</h2><div class="legend"><span><i class="dot" style="background:#1769ff"></i>règles dynamiques actives, sans retard</span><span><i class="dot" style="background:#df382c"></i>règles dynamiques actives, avec retard</span><span>moyenne mobile 7 jours</span></div><canvas id="stock"></canvas></section>
<section class="panel"><h2>2. La production puis le client sont-ils touchés ?</h2><div class="legend"><span><i class="dot" style="background:#1769ff"></i>règles dynamiques actives, sans retard</span><span><i class="dot" style="background:#df382c"></i>règles dynamiques actives, avec retard</span></div><p class="s"><strong>Produit 268091 libéré par jour</strong> · moyenne mobile 28 jours</p><canvas id="production"></canvas><p class="s"><strong>Commandes 268091 restant en retard</strong> · moyenne mobile 7 jours</p><canvas id="backlog"></canvas></section>
<section class="panel"><h2>3. Comment les signaux du réseau changent-ils ?</h2><p>Ces signaux sont déclenchés par l'état simulé du réseau : tension de stock, saturation, retard calculé ou manque matière. Le tableau montre ceux qui apparaissent, disparaissent ou se décalent. Sur l'ensemble du réseau, le nombre total varie de {int(pair['state_event_count_change']):+d} : une baisse ne signifie pas que le risque diminue, car le choc peut supprimer ou déplacer d'autres commandes et donc d'autres signaux. Ces signaux ne représentent pas une probabilité historique de défaillance.</p><div id="events"></div></section>
<section class="panel"><h2>Lots finis reliés à la cascade</h2><p>La généalogie remonte des lots 268091 vers les réceptions de 338929 portant l'incident initial ou un signal secondaire propre à la trajectoire perturbée. « Relié » ne signifie pas automatiquement « livré en retard » : cela identifie le périmètre de lots à examiner. Les 25 premiers sont affichés ci-dessous.</p><div id="lots"></div></section>
<p class="note"><strong>Lecture métier.</strong> Les deux paires sont identiques avant J{incident['start_day']}. Sans les règles dynamiques, le retard fait perdre {off_loss} points de service ; avec elles, il en fait perdre {on_loss}. L'écart de {amplification} points mesure ici l'amplification associée aux réactions dépendantes de l'état. Cela démontre le mécanisme stock → production → client, mais pas la fréquence future de l'incident. Aucune action correctrice automatique n'est appliquée : cette vue isole la propagation du choc.</p>
<footer>Horizon : {summary['measured_days']} jours mesurés après 240 jours de mise en régime · dernière arrivée portant l'incident à J{pair['primary_event_last_arrival_day']}, puis {pair['days_observed_after_last_primary_arrival']} jours observés · une répétition · données de cette page intégrées au fichier, aucune connexion requise.</footer>
<script id="payload" type="application/json">{payload_json}</script>
<script>
const P=JSON.parse(document.getElementById('payload').textContent), COLORS={{a:'#1769ff',b:'#df382c'}}, start=P.summary.incident_window.start_day,end=P.summary.incident_window.end_day;
const rows=k=>P.curves.filter(r=>r.case===k), A=rows('state_only'),B=rows('state_plus_delay');
function ma(data,key,w){{let q=[],s=0;return data.map(r=>{{const v=+r[key]||0;q.push(v);s+=v;if(q.length>w)s-=q.shift();return s/q.length}})}}
function chart(id,a,b,opt={{}}){{const c=document.getElementById(id),dpr=devicePixelRatio||1,W=c.clientWidth,H=c.clientHeight;c.width=W*dpr;c.height=H*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);const pad={{l:58,r:16,t:16,b:30}},iw=W-pad.l-pad.r,ih=H-pad.t-pad.b,vals=a.concat(b),lo=opt.zero?0:Math.min(...vals),hi=Math.max(...vals,lo+1),X=i=>pad.l+iw*i/(a.length-1),Y=v=>pad.t+ih-(v-lo)*ih/(hi-lo);x.fillStyle='#fff0ef';x.fillRect(X(start),pad.t,X(end)-X(start),ih);x.strokeStyle='#e2e8f1';x.fillStyle='#60708a';x.font='12px system-ui';for(let i=0;i<5;i++){{const y=pad.t+ih*i/4;x.beginPath();x.moveTo(pad.l,y);x.lineTo(W-pad.r,y);x.stroke();const v=hi-(hi-lo)*i/4;x.fillText(new Intl.NumberFormat('fr-FR',{{notation:'compact',maximumFractionDigits:1}}).format(v),4,y+4)}}[['J0',0],['J'+start,start],['J'+end,end],['J'+(a.length-1),a.length-1]].forEach(t=>x.fillText(t[0],Math.min(W-45,X(t[1])),H-8));function line(v,color){{x.strokeStyle=color;x.lineWidth=2;x.beginPath();v.forEach((n,i)=>{{if(i)x.lineTo(X(i),Y(n));else x.moveTo(X(i),Y(n))}});x.stroke()}}line(a,COLORS.a);line(b,COLORS.b);}}
chart('stock',ma(A,'component_stock_338929_M1810',7),ma(B,'component_stock_338929_M1810',7),{{zero:true}});chart('production',ma(A,'production_released_268091',28),ma(B,'production_released_268091',28),{{zero:true}});chart('backlog',ma(A,'backlog_end_268091',7),ma(B,'backlog_end_268091',7),{{zero:true}});
const family={{stock:'stock fournisseur',capacity:'capacité',lead:'délai',availability:'disponibilité',upstream:'amont fournisseur',reliability:'fiabilité',cost:'coût'}};
const metric={{stock_cover_below_5d:'stock sous 5 jours de besoin',stock_cover_below_3d:'stock sous 3 jours de besoin',stock_cover_zero:'stock presque nul',factory_input_shortage_reported:'manque matière constaté à l’usine',factory_input_shortage_next_receipt_late:'prochaine réception trop tardive',factory_input_shortage_severe_or_repeated:'manque matière sévère ou répété',capacity_utilization_above_75pct:'utilisation supérieure à 75 %',capacity_utilization_full_day:'capacité entièrement utilisée',capacity_utilization_above_85pct:'utilisation supérieure à 85 %',capacity_utilization_above_90pct:'utilisation supérieure à 90 %',observed_lead_ratio_above_110pct:'délai observé supérieur de 10 %',observed_lead_ratio_above_125pct:'délai observé supérieur de 25 %',observed_lead_ratio_above_135pct:'délai observé supérieur de 35 %',upstream_rejection_avg_7d_above_10pct_with_stock_cover_below_7d:'approvisionnement amont insuffisant avec moins de 7 jours de stock',upstream_rejection_avg_14d_above_50pct_with_stock_cover_below_3d:'approvisionnement amont très insuffisant avec moins de 3 jours de stock',upstream_recourse_cost_ratio_above_250pct:'coût de recours amont très élevé',delivery_loss_rate_above_3pct:'quantité reçue inférieure à la quantité prévue'}};
function table(headers,body){{return `<table><thead><tr>${{headers.map(h=>`<th>${{h}}</th>`).join('')}}</tr></thead><tbody>${{body}}</tbody></table>`}}
const ev=[...P.events].sort((a,b)=>Math.abs(+b.incremental_count)-Math.abs(+a.incremental_count));document.getElementById('events').innerHTML=ev.length?table(['Signal','Périmètre','Sans retard','Avec retard','Écart','Premier déclenchement'],ev.slice(0,30).map(r=>`<tr><td>${{family[r.risk_family]||r.risk_family}}<br><span class="s">${{metric[r.trigger_metric]||r.trigger_metric}}</span></td><td>${{r.supplier_id}} · ${{r.item_id.replace('item:','')}}${{r.dst_node_id?' → '+r.dst_node_id:''}}</td><td>${{r.state_only_count}}</td><td>${{r.state_plus_delay_count}}</td><td>${{+r.incremental_count>0?'+':''}}${{r.incremental_count}}</td><td>J${{r.state_plus_delay_first_trigger_day||'—'}}</td></tr>`).join('')):'<p class="empty">Aucun signal secondaire supplémentaire : le choc se propage ici sans modifier le nombre de signaux dynamiques.</p>';
document.getElementById('lots').innerHTML=P.lots.length?table(['Lot 268091','Jour de libération','Quantité','Trace'],P.lots.slice(0,25).map(r=>`<tr><td>${{r.finished_product_lot_id}}</td><td>J${{r.release_day}}</td><td>${{new Intl.NumberFormat('fr-FR').format(r.released_qty)}}</td><td>${{r.primary_delay_in_ancestry?'incident initial':''}}${{r.incremental_state_events_in_ancestry?' + signal secondaire':''}}</td></tr>`).join('')):'<p class="empty">Aucun lot fini relié dans l’horizon retenu.</p>';
</script></main></body></html>"""


def validate_summary_policy(
    summary: Mapping[str, Any],
    *,
    families: Sequence[str],
    seed: int,
    days: int,
    state_enabled: bool,
) -> None:
    if int(summary.get("sim_days") or 0) != days:
        raise ValueError("Engine summary horizon mismatch")
    policy = summary.get("policy") or {}
    if int(policy.get("seed") or 0) != seed:
        raise ValueError("Engine summary seed mismatch")
    state = policy.get("supplier_state_dependent_risk") or {}
    if bool(state.get("enabled")) != state_enabled:
        raise ValueError("State-dependent supplier-risk mode mismatch")
    enabled = tuple(str(value) for value in state.get("enabled_families") or ())
    if set(enabled) != set(families):
        raise ValueError(f"State-risk family proof mismatch: {enabled}")
    if FORBIDDEN_FAMILY in enabled:
        raise ValueError("Excluded state-risk family appears enabled")
    if int(state.get("observation_warmup_days") or -1) != 30:
        raise ValueError("State-risk observation warm-up is not the frozen 30 days")


def extract_case(
    case_dir: Path,
    *,
    days: int,
    families: Sequence[str],
    seed: int,
    state_enabled: bool,
) -> dict[str, Any]:
    summary = read_json(case_dir / "summaries" / "first_simulation_summary.json")
    validate_summary_policy(
        summary,
        families=families,
        seed=seed,
        days=days,
        state_enabled=state_enabled,
    )
    state_rows = read_csv_rows(case_dir / "data" / "supplier_state_dependent_risk_events.csv")
    audit_state_rows(state_rows, families)
    if not state_enabled and state_rows:
        raise ValueError("State-dependent events exist in a disabled case")
    service_rows = read_csv_rows(
        case_dir / "data" / "production_demand_service_daily.csv"
    )
    service = service_metrics(service_rows, days=days)
    service_daily: dict[int, dict[str, float]] = {}
    for row in service_rows:
        if row.get("node_id") != TARGET_CUSTOMER or row.get("item_id") != TARGET_PRODUCT:
            continue
        day = int(finite(row.get("day"), -1.0))
        if day < 0 or day >= days:
            continue
        demand = max(0.0, finite(row.get("demand_qty")))
        required = max(demand, finite(row.get("required_with_backlog_qty")))
        served = max(0.0, finite(row.get("served_qty")))
        service_daily[day] = {
            "demand": demand,
            "on_due": min(demand, max(0.0, served - max(0.0, required - demand))),
            "backlog": max(0.0, finite(row.get("backlog_end_qty"))),
        }
    component_rows = filtered_rows(
        case_dir / "data" / "production_input_stocks_daily.csv",
        node_id=TARGET_FACTORY,
        item_id=TARGET_COMPONENT,
    )
    supplier_rows = filtered_rows(
        case_dir / "data" / "production_supplier_stocks_daily.csv",
        node_id=TARGET_SUPPLIER,
        item_id=TARGET_COMPONENT,
    )
    product_rows = filtered_rows(
        case_dir / "data" / "production_output_products_daily.csv",
        node_id=TARGET_FACTORY,
        item_id=TARGET_PRODUCT,
    )
    if any(len(rows) != days for rows in (component_rows, supplier_rows, product_rows)):
        raise ValueError("Incomplete paired trajectory")
    shipment_rows = [
        row
        for row in read_csv_rows(
            case_dir / "data" / "production_supplier_shipments_daily.csv"
        )
        if row.get("src_node_id") == TARGET_SUPPLIER
        and row.get("dst_node_id") == TARGET_FACTORY
        and row.get("item_id") == TARGET_COMPONENT
    ]
    component = series_by_day(component_rows, "stock_end_of_day")
    supplier = series_by_day(supplier_rows, "stock_end_of_day")
    production = series_by_day(product_rows, "released_qty")
    return {
        "summary": summary,
        "state_rows": state_rows,
        "service": service,
        "service_daily": service_daily,
        "component_stock": component,
        "supplier_stock": supplier,
        "production": production,
        "shipment_rows": shipment_rows,
        "genealogy_rows": read_csv_rows(case_dir / "data" / "production_lot_genealogy.csv"),
    }


def extract_pair(
    output_dir: Path,
    *,
    days: int,
    seed: int,
    families: Sequence[str],
    incident_start: int,
    incident_end: int,
    primary_event_id: str,
) -> dict[str, Any]:
    extracted = {
        case.key: extract_case(
            output_dir / "cases" / case.key,
            days=days,
            families=families,
            seed=seed,
            state_enabled=case.state_enabled,
        )
        for case in CASES
    }
    off_control = extracted["state_off_nominal"]
    off_incident = extracted["delay_only_state_off"]
    control = extracted["state_only"]
    incident = extracted["state_plus_delay"]
    preincident_fields = ("component_stock", "supplier_stock", "production")

    def assert_preincident_identity(
        left: Mapping[str, Any], right: Mapping[str, Any], label: str
    ) -> None:
        for field in preincident_fields:
            for day in range(incident_start):
                if not math.isclose(
                    float(left[field][day]),
                    float(right[field][day]),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    raise ValueError(
                        f"{label} trajectories diverge before the incident: {field}/J{day}"
                    )
        for day in range(incident_start):
            for field in ("demand", "on_due", "backlog"):
                if not math.isclose(
                    float(left["service_daily"][day][field]),
                    float(right["service_daily"][day][field]),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    raise ValueError(
                        f"{label} client trajectories diverge before the incident: {field}/J{day}"
                    )

    assert_preincident_identity(control, incident, "State-enabled pair")
    assert_preincident_identity(off_control, off_incident, "State-disabled pair")
    preincident_control_events = [
        dict(row)
        for row in control["state_rows"]
        if int(finite(row.get("trigger_day"), -1.0)) < incident_start
    ]
    preincident_incident_events = [
        dict(row)
        for row in incident["state_rows"]
        if int(finite(row.get("trigger_day"), -1.0)) < incident_start
    ]
    if preincident_control_events != preincident_incident_events:
        raise ValueError("State signals diverge before the imposed incident")
    metric_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for case in CASES:
        data = extracted[case.key]
        component = data["component_stock"]
        supplier = data["supplier_stock"]
        production = data["production"]
        service = data["service"]
        primary_shipments = [
            row
            for row in data["shipment_rows"]
            if primary_event_id
            in {
                value.strip()
                for value in str(row.get("risk_event_ids") or "").split(",")
                if value.strip()
            }
        ]
        metric_rows.append(
            {
                "case": case.key,
                "case_label_fr": case.label_fr,
                "state_dependent_rules_enabled": case.state_enabled,
                "seed": seed,
                "days": days,
                "state_event_count": len(data["state_rows"]),
                "service_268091_pct": round(100.0 * service["on_due_service"], 6),
                "on_due_qty_268091": round(service["on_due_qty"], 6),
                "backlog_qty_days_268091": round(service["backlog_qty_days"], 6),
                "ending_backlog_268091": round(service["ending_backlog_qty"], 6),
                "component_stock_min_qty": round(min(component.values()), 6),
                "component_stock_zero_days": sum(value <= 1e-9 for value in component.values()),
                "supplier_stock_min_qty": round(min(supplier.values()), 6),
                "production_released_268091_qty": round(sum(production.values()), 6),
                "production_zero_days_268091": sum(value <= 1e-9 for value in production.values()),
                "primary_event_shipment_count": len(primary_shipments),
                "primary_event_pulled_qty": round(
                    sum(finite(row.get("pulled_qty")) for row in primary_shipments), 6
                ),
                "primary_event_shipped_qty": round(
                    sum(finite(row.get("shipped_qty")) for row in primary_shipments), 6
                ),
                "primary_event_first_decision_day": (
                    min(int(finite(row.get("risk_decision_day"), -1.0)) for row in primary_shipments)
                    if primary_shipments
                    else ""
                ),
                "primary_event_last_arrival_day": (
                    max(int(finite(row.get("arrival_day"), -1.0)) for row in primary_shipments)
                    if primary_shipments
                    else ""
                ),
            }
        )
        for day in range(days):
            svc = data["service_daily"][day]
            curve_rows.append(
                {
                    "case": case.key,
                    "day": day,
                    "incident_window": int(incident_start <= day <= incident_end),
                    "component_stock_338929_M1810": round(component[day], 6),
                    "supplier_stock_338929": round(supplier[day], 6),
                    "production_released_268091": round(production[day], 6),
                    "demand_268091": round(svc["demand"], 6),
                    "served_on_due_268091": round(svc["on_due"], 6),
                    "backlog_end_268091": round(svc["backlog"], 6),
                }
            )

    control_agg = event_aggregates(control["state_rows"])
    incident_agg = event_aggregates(incident["state_rows"])
    event_rows: list[dict[str, Any]] = []
    incremental_ids: set[str] = set()
    for signature in sorted(set(control_agg) | set(incident_agg)):
        a = control_agg.get(signature, {})
        b = incident_agg.get(signature, {})
        count_a = int(a.get("count") or 0)
        count_b = int(b.get("count") or 0)
        delta = count_b - count_a
        first_a = a.get("first_trigger_day", "")
        first_b = b.get("first_trigger_day", "")
        if delta > 0:
            incremental_ids.update((b.get("event_ids") or [])[count_a:])
        event_rows.append(
            {
                "risk_family": signature[0],
                "trigger_metric": signature[1],
                "supplier_id": signature[2],
                "item_id": signature[3],
                "dst_node_id": signature[4],
                "edge_id": signature[5],
                "state_only_count": count_a,
                "state_plus_delay_count": count_b,
                "incremental_count": delta,
                "state_only_first_trigger_day": first_a,
                "state_plus_delay_first_trigger_day": first_b,
                "first_trigger_shift_days": (
                    int(first_b) - int(first_a)
                    if first_a != "" and first_b != ""
                    else ""
                ),
                "effect": b.get("effect") or a.get("effect") or "",
            }
        )

    exact_control_ids = {str(row.get("event_id") or "") for row in control["state_rows"]}
    exact_incident_ids = {str(row.get("event_id") or "") for row in incident["state_rows"]}
    incremental_ids.update(exact_incident_ids - exact_control_ids)
    lot_rows = output_lot_exposure(
        incident["genealogy_rows"],
        primary_event_id=primary_event_id,
        incremental_state_event_ids=incremental_ids,
    )
    off_lot_rows = output_lot_exposure(
        off_incident["genealogy_rows"],
        primary_event_id=primary_event_id,
        incremental_state_event_ids=set(),
    )
    new_target_signal_rows = [
        row
        for row in event_rows
        if row["supplier_id"] == TARGET_SUPPLIER
        and row["item_id"] == TARGET_COMPONENT
        and int(row["state_only_count"]) == 0
        and int(row["state_plus_delay_count"]) > 0
    ]
    new_target_signal_count = sum(
        int(row["state_plus_delay_count"]) for row in new_target_signal_rows
    )
    first_new_target_signal_day = min(
        (
            int(row["state_plus_delay_first_trigger_day"])
            for row in new_target_signal_rows
            if row["state_plus_delay_first_trigger_day"] != ""
        ),
        default=None,
    )
    write_csv(output_dir / "results" / "paired_metrics.csv", metric_rows)
    write_csv(output_dir / "results" / "daily_curves.csv", curve_rows)
    write_csv(output_dir / "results" / "state_event_differences.csv", event_rows)
    write_csv(output_dir / "results" / "finished_product_lot_exposure.csv", lot_rows)
    write_csv(
        output_dir / "results" / "finished_product_lot_exposure_state_off.csv",
        off_lot_rows,
    )

    by_case = {row["case"]: row for row in metric_rows}
    off_a_metric = by_case["state_off_nominal"]
    off_b_metric = by_case["delay_only_state_off"]
    a_metric = by_case["state_only"]
    b_metric = by_case["state_plus_delay"]
    if any(
        int(row["primary_event_shipment_count"]) != 0
        for row in (off_a_metric, a_metric)
    ):
        raise ValueError("Primary imposed event leaked into a no-incident case")
    if any(
        int(row["primary_event_shipment_count"]) <= 0
        for row in (off_b_metric, b_metric)
    ):
        raise ValueError("The primary imposed event did not affect an incident case")
    off_service_loss = (
        off_a_metric["service_268091_pct"] - off_b_metric["service_268091_pct"]
    )
    on_service_loss = a_metric["service_268091_pct"] - b_metric["service_268091_pct"]
    service_loss_amplification = on_service_loss - off_service_loss
    off_backlog_effect = (
        off_b_metric["backlog_qty_days_268091"]
        - off_a_metric["backlog_qty_days_268091"]
    )
    on_backlog_effect = (
        b_metric["backlog_qty_days_268091"] - a_metric["backlog_qty_days_268091"]
    )
    off_production_loss = (
        off_a_metric["production_released_268091_qty"]
        - off_b_metric["production_released_268091_qty"]
    )
    on_production_loss = (
        a_metric["production_released_268091_qty"]
        - b_metric["production_released_268091_qty"]
    )
    service_on_due_control = {
        day: values["on_due"] for day, values in control["service_daily"].items()
    }
    service_on_due_incident = {
        day: values["on_due"] for day, values in incident["service_daily"].items()
    }
    backlog_control = {
        day: values["backlog"] for day, values in control["service_daily"].items()
    }
    backlog_incident = {
        day: values["backlog"] for day, values in incident["service_daily"].items()
    }
    divergence_days = {
        "component_stock": first_divergence_day(
            control["component_stock"], incident["component_stock"], start_day=incident_start
        ),
        "production_release": first_divergence_day(
            control["production"], incident["production"], start_day=incident_start
        ),
        "on_due_service": first_divergence_day(
            service_on_due_control, service_on_due_incident, start_day=incident_start
        ),
        "backlog": first_divergence_day(
            backlog_control, backlog_incident, start_day=incident_start
        ),
    }
    summary = {
        "schema_version": "etudecas.supplier_state_cascade_pilot.v1",
        "created_utc": utc_now(),
        "status": "complete",
        "interpretation": "paired_counterfactual_single_seed_exploratory",
        "causal_change": "one dated +120-day transport delay on supplier 338929 lane",
        "seed": seed,
        "measured_days": days,
        "incident_window": {"start_day": incident_start, "end_day": incident_end},
        "state_risk_families_enabled": list(families),
        "pair_results": {
            "service_loss_points_state_off": round(off_service_loss, 6),
            "service_loss_points_state_on": round(on_service_loss, 6),
            "service_loss_amplification_points": round(service_loss_amplification, 6),
            "backlog_effect_state_off_qty_days": round(off_backlog_effect, 6),
            "backlog_effect_state_on_qty_days": round(on_backlog_effect, 6),
            "backlog_amplification_qty_days": round(
                on_backlog_effect - off_backlog_effect, 6
            ),
            "production_loss_state_off_qty": round(off_production_loss, 6),
            "production_loss_state_on_qty": round(on_production_loss, 6),
            "production_loss_amplification_qty": round(
                on_production_loss - off_production_loss, 6
            ),
            "service_268091_change_points": round(
                b_metric["service_268091_pct"] - a_metric["service_268091_pct"], 6
            ),
            "backlog_qty_days_change": round(
                b_metric["backlog_qty_days_268091"] - a_metric["backlog_qty_days_268091"], 6
            ),
            "production_released_change_qty": round(
                b_metric["production_released_268091_qty"]
                - a_metric["production_released_268091_qty"],
                6,
            ),
            "state_event_count_change": (
                b_metric["state_event_count"] - a_metric["state_event_count"]
            ),
            "new_target_chain_state_signal_count": new_target_signal_count,
            "new_target_chain_state_signal_group_count": len(new_target_signal_rows),
            "first_new_target_chain_state_signal_day": first_new_target_signal_day,
            "incremental_or_shifted_state_signal_groups": sum(
                int(row["incremental_count"] != 0)
                or (
                    row["first_trigger_shift_days"] != ""
                    and row["first_trigger_shift_days"] != 0
                )
                for row in event_rows
            ),
            "finished_product_lots_with_primary_or_incremental_signal_ancestry": len(lot_rows),
            "finished_product_lots_with_primary_ancestry_state_off": len(off_lot_rows),
            "primary_event_shipment_count": b_metric["primary_event_shipment_count"],
            "primary_event_pulled_qty": b_metric["primary_event_pulled_qty"],
            "primary_event_last_arrival_day": b_metric["primary_event_last_arrival_day"],
            "primary_event_arrivals_complete_within_horizon": (
                int(b_metric["primary_event_last_arrival_day"]) < days
            ),
            "days_observed_after_last_primary_arrival": max(
                0, days - 1 - int(b_metric["primary_event_last_arrival_day"])
            ),
            "preincident_pair_identity_proven": True,
            "preincident_identity_state_off_pair_proven": True,
            "preincident_identity_state_on_pair_proven": True,
            "first_divergence_days": divergence_days,
        },
        "files": {
            "metrics": "results/paired_metrics.csv",
            "daily_curves": "results/daily_curves.csv",
            "state_event_differences": "results/state_event_differences.csv",
            "finished_product_lot_exposure": "results/finished_product_lot_exposure.csv",
            "finished_product_lot_exposure_state_off": (
                "results/finished_product_lot_exposure_state_off.csv"
            ),
            "offline_html": "OUVRIR_CASCADE_DYNAMIQUE_338929.html",
        },
        "limits": [
            "One paired realization: this is a causal mechanism demonstration, not an average industrial forecast.",
            "Endogenous state signals are model rules to validate with operating experts.",
            "Lot exposure is reconstructed through the simulated genealogy; it is not observed historical attribution.",
        ],
    }
    write_json(output_dir / "state_cascade_summary.json", summary)
    html_document = build_offline_html(
        summary=summary,
        metric_rows=metric_rows,
        curve_rows=curve_rows,
        event_rows=event_rows,
        lot_rows=lot_rows,
    )
    (output_dir / "OUVRIR_CASCADE_DYNAMIQUE_338929.html").write_text(
        html_document, encoding="utf-8"
    )
    return summary


def run_pair(
    *,
    reference_log: Path,
    risk_csv: Path,
    output_dir: Path,
    days: int,
    seed: int,
    families: Sequence[str],
    execute: bool,
    engine_override: Path | None = None,
    workers: int = 1,
) -> dict[str, Any]:
    if not reference_log.is_file():
        raise FileNotFoundError(reference_log)
    if not risk_csv.is_file():
        raise FileNotFoundError(risk_csv)
    incident_start, incident_end, primary_event_id = validate_primary_risk(risk_csv)
    if days <= incident_end + 120:
        raise ValueError(
            "The measured horizon must extend at least 120 days beyond the incident window"
        )
    reference_command = command_from_log(reference_log)
    reference_engine = Path(reference_command[1]).resolve()
    engine = engine_override.resolve() if engine_override is not None else reference_engine
    if not engine.is_file():
        raise FileNotFoundError(engine)
    if engine_override is not None and engine == reference_engine:
        raise ValueError("--engine-override must designate an additive engine copy")
    engine_text = engine.read_text(encoding="utf-8")
    if "--supplier-state-risk-families" not in engine_text:
        raise RuntimeError("The engine state-risk family allowlist is not installed yet")

    resolved_cases = tuple(
        PairCase(
            case.key,
            case.label_fr,
            risk_csv if case.risk_csv is not None else None,
            case.state_enabled,
        )
        for case in CASES
    )
    commands: dict[str, list[str]] = {}
    for case in resolved_cases:
        case_dir = output_dir / "cases" / case.key
        commands[case.key] = build_case_command(
            reference_command,
            case=case,
            output_dir=case_dir,
            days=days,
            seed=seed,
            families=families,
            engine_path=engine,
        )
    manifest = {
        "schema_version": "etudecas.supplier_state_cascade_pilot_manifest.v1",
        "created_utc": utc_now(),
        "status": "planned" if not execute else "running",
        "reference_log": str(reference_log.resolve()),
        "reference_log_sha256": sha256_file(reference_log),
        "reference_engine": str(reference_engine),
        "reference_engine_sha256": sha256_file(reference_engine),
        "executed_engine": str(engine),
        "executed_engine_sha256": sha256_file(engine),
        "engine_override_used": engine_override is not None,
        "risk_csv": str(risk_csv.resolve()),
        "risk_csv_sha256": sha256_file(risk_csv),
        "seed": seed,
        "measured_days": days,
        "incident_window": {"start_day": incident_start, "end_day": incident_end},
        "families": list(families),
        "commands": commands,
    }
    write_json(output_dir / "pilot_manifest.json", manifest)
    if not execute:
        return manifest

    def execute_case(case: PairCase) -> None:
        case_dir = output_dir / "cases" / case.key
        summary_path = case_dir / "summaries" / "first_simulation_summary.json"
        if summary_path.is_file():
            return
        if case_dir.exists() and any(case_dir.iterdir()):
            raise RuntimeError(f"Partial case directory requires review: {case_dir}")
        case_dir.mkdir(parents=True, exist_ok=True)
        log_path = case_dir / "cascade_engine.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{utc_now()}] COMMAND {json.dumps(commands[case.key], ensure_ascii=False)}\n")
            completed = subprocess.run(
                commands[case.key],
                cwd=reference_engine.parents[3],
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failed for {case.key}; see {log_path}")

    pending_cases = [
        case
        for case in resolved_cases
        if not (
            output_dir / "cases" / case.key / "summaries" / "first_simulation_summary.json"
        ).is_file()
    ]
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), len(pending_cases) or 1))) as pool:
        futures = {pool.submit(execute_case, case): case for case in pending_cases}
        for future in as_completed(futures):
            future.result()

    summary = extract_pair(
        output_dir,
        days=days,
        seed=seed,
        families=families,
        incident_start=incident_start,
        incident_end=incident_end,
        primary_event_id=primary_event_id,
    )
    manifest["status"] = "complete"
    manifest["completed_utc"] = utc_now()
    manifest["summary"] = "state_cascade_summary.json"
    write_json(output_dir / "pilot_manifest.json", manifest)
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-log", type=Path, default=DEFAULT_REFERENCE_LOG)
    parser.add_argument("--risk-csv", type=Path, default=DEFAULT_RISK_CSV)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--seed", type=int, default=340281)
    parser.add_argument("--families", default=",".join(DEFAULT_FAMILIES))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--engine-override",
        type=Path,
        help=(
            "Use a tested additive copy of the engine. Only the executable script "
            "path in the reconstructed command is replaced."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run missing simulations. Without this flag, only validate and freeze commands.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    families = validate_families(args.families.split(","))
    result = run_pair(
        reference_log=args.reference_log.resolve(),
        risk_csv=args.risk_csv.resolve(),
        output_dir=args.output_dir.resolve(),
        days=args.days,
        seed=args.seed,
        families=families,
        execute=bool(args.execute),
        engine_override=(args.engine_override.resolve() if args.engine_override else None),
        workers=max(1, args.workers),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
