"""Deliver descriptive decision support, exploratory actions and a reviewed map.

python -m etudecas.decision_support --run <nominal_run> --execute-actions --render-map --browser
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import csv
import html
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from etudecas.testing.map_delivery import file_hash, reconcile_run, reconcile_browser
from etudecas.visualization.maps.scenario_comparison_payload import build_scenario_comparison_payload
from etudecas.visualization.maps.economic_valuation import economic_cost_view

REPO = Path(__file__).resolve().parents[1]


class DeliveryValidationError(ValueError):
    """Keep failed checks available when the CLI records the failure."""

    def __init__(self, report):
        super().__init__('Delivery checks failed; see delivery.json')
        self.delivery_report = report


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def fifo_delay(rows, days):
    """Reconstruct daily demand cohorts under FIFO; not observed order-level OTIF."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["node_id"], row["item_id"])].append(row)
    results = []
    for (node, item), series in sorted(groups.items()):
        series.sort(key=lambda r: int(r["day"]))
        if [int(r["day"]) for r in series] != list(range(days)):
            raise ValueError(f"Incomplete or duplicate daily series: {node}/{item}")
        queue = deque()
        demand = served = punctual = upper = delay = area = previous = 0.0
        max_delay = 0
        backlog_days = 0
        for row in series:
            day = int(row["day"])
            d, s, b, required = [float(row[k]) for k in
                ("demand_qty", "served_qty", "backlog_end_qty", "required_with_backlog_qty")]
            if any(not math.isfinite(v) or v < 0 for v in (d, s, b, required)):
                raise ValueError("Non-finite or negative demand/service")
            if abs(required - previous - d) > .02 or abs(previous + d - s - b) > .02:
                raise ValueError("Daily conservation failed or opening backlog has unknown age")
            if d:
                queue.append([day, d])
            remaining = s
            while remaining > 1e-7 and queue:
                due, qty = queue[0]
                delivered = min(qty, remaining)
                age = day - due
                delay += delivered * age
                if age == 0:
                    punctual += delivered
                if delivered > 1e-5:
                    max_delay = max(max_delay, age)
                remaining -= delivered
                queue[0][1] -= delivered
                if queue[0][1] <= 1e-7:
                    queue.popleft()
            if remaining > .02:
                raise ValueError("Service exceeds available demand cohorts")
            demand += d
            served += s
            upper += min(d, s)
            area += b
            backlog_days += b > .001
            previous = b
        results.append({"node_id": node, "item_id": item, "demand": demand,
                        "served": served, "ending_backlog": previous,
                        "same_day_service_lower_pct": 100 * punctual / demand if demand else None,
                        "same_day_service_upper_pct": 100 * upper / demand if demand else None,
                        "mean_delay_served_fifo_days": delay / served if served else None,
                        "max_delay_served_fifo_days": max_delay,
                        "oldest_unserved_fifo_days": days - 1 - queue[0][0] if queue else 0,
                        "backlog_quantity_days": area, "backlog_days_including_startup": backlog_days})
    return results


def score_breakdown(kpis):
    """Expose the existing score without changing weights or implying calibration."""
    parts = {"service": 5 * kpis["service_loss_pp"], "backlog": 3 * kpis["backlog_pct"],
             "extra_cost": .25 * kpis["cost_delta_pct"] if kpis.get("cost_delta_pct") is not None else None}
    total = sum(value for value in parts.values() if value is not None)
    if not math.isclose(total, kpis["observed_impact_score"], abs_tol=1e-8):
        raise ValueError("Score decomposition differs from displayed score")
    return {"total": total, "components": parts,
            "contribution_pct": {k: (100 * v / total if total else 0) if v is not None else None for k, v in parts.items()}}


def audit_losses(run, days):
    """Reconcile departures inside the measured horizon, retaining item and unit."""
    by_item = defaultdict(float)
    outside = 0.0
    ids = Counter()
    exact = Counter()
    for row in csv_rows(run / "data/production_supplier_shipments_daily.csv"):
        loss = max(0, float(row["pulled_qty"]) - float(row["shipped_qty"]))
        if not 0 <= int(row["day"]) < days:
            outside += loss
            continue
        if row["shipment_id"]:
            ids[row["shipment_id"]] += 1
        if loss > 0:
            exact[tuple(row.items())] += 1
        by_item[(row["src_node_id"], row["item_id"], row["uom"])] += loss
    expected = read_json(run / "summaries/first_simulation_summary.json")["kpis"]["total_unreliable_loss_qty"]
    total = sum(by_item.values())
    return {"arithmetic_total_in_horizon": total, "summary_total": expected,
            "summary_matches": math.isclose(total, expected, abs_tol=.02),
            "outside_horizon_qty": outside,
            "repeated_nonempty_shipment_ids": sum(v - 1 for v in ids.values()),
            "exact_duplicate_positive_loss_rows": sum(v - 1 for v in exact.values()),
            "by_item": [{"supplier_id": k[0], "item_id": k[1], "uom": k[2], "loss_qty": v}
                        for k, v in sorted(by_item.items(), key=lambda x: -x[1]) if v > 0],
            "interpretation": "Arithmetic reconciliation only: component units cannot be treated as equivalent finished products."}


def bottlenecks(run, graph, output):
    """Link recorded input constraints to supplying lanes; no causal inference from proximity."""
    groups = {}
    evidence = []
    for line, row in enumerate(csv_rows(run / "data/production_constraint_daily.csv"), 2):
        if float(row["shortfall_vs_lot_plan_qty"] or 0) <= .001:
            continue
        key = (row["node_id"], row["output_item_id"], row["binding_input_item_id"], row["binding_cause"])
        entry = groups.setdefault(key, {"node_id": key[0], "product_item_id": key[1],
             "component_item_id": key[2], "binding_cause": key[3], "days": set(), "repeated_shortfall_qty": 0.0})
        entry["days"].add(int(row["day"]))
        entry["repeated_shortfall_qty"] += float(row["shortfall_vs_lot_plan_qty"])
        evidence.append({"source_line": line, **row})
    export_csv(output / "constraint-evidence.csv", evidence)
    ranked = []
    for entry in groups.values():
        days = sorted(entry.pop("days"))
        entry.update(blocked_days=len(days), first_day=days[0], last_day=days[-1])
        entry["suppliers"] = sorted({e["from"] for e in graph["edges"]
             if e.get("to") == entry["node_id"] and entry["component_item_id"] in e.get("items", [])})
        ranked.append(entry)
    ranked.sort(key=lambda x: -x["blocked_days"])
    components = {x["component_item_id"] for x in ranked}
    causal_rows = []
    for line, row in enumerate(csv_rows(run / "data/lot_causal_links.csv"), 2):
        if row["item_id"] in components and row["causal_root_id"]:
            causal_rows.append({"source_line": line, **row})
    export_csv(output / "lot-causal-evidence.csv", causal_rows)
    return {"ranked": ranked, "explicit_causal_rows": len(causal_rows),
            "causal_examples": causal_rows[:12],
            "limit": "The engine records input shortages and upstream lot causal context; this does not quantify each supplier's share of customer delay."}


def export_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def action_metrics(run):
    summary = read_json(run / "summaries/first_simulation_summary.json")
    delays = fifo_delay(csv_rows(run / "data/production_demand_service_daily.csv"), summary["sim_days"])
    applied = Counter()
    for row in csv_rows(run / "data/canonical_action_ledger.csv"):
        if row.get("action") in {"safety_stock_multiplier", "expedite_level"}:
            neutral = 1 if row["action"] == "safety_stock_multiplier" else 0
            if abs(float(row.get("effective") or neutral) - neutral) > 1e-8:
                applied[(row["action"], row.get("status", ""))] += 1
    return {"run": str(run.resolve()), **economic_cost_view(summary), "fill_rate": summary["kpis"]["fill_rate"],
            "total_cost": summary["kpis"]["total_cost"], "ending_backlog": summary["kpis"]["ending_backlog"],
            "backlog_quantity_days": sum(r["backlog_quantity_days"] for r in delays),
            "delay_by_product": delays,
            "control_ledger_non_neutral_rows": [{"action": k[0], "status": k[1], "rows": v} for k, v in applied.items()]}


def render_report(output, report, map_path):
    esc = lambda x: html.escape(str(x))
    component_labels = {'service': 'Perte de service', 'backlog': 'Pic de reliquat',
        'replanning': 'Reports de production', 'extra_cost': 'Surcoût', 'material_loss': 'Pertes de composants'}
    action_labels = {'risk_reference': 'Scénario risqué — cibles réelles conservées',
        'safety_150': 'Sensibilité — cible de sécurité ×1,5',
        'expedite_50': 'Sensibilité — accélération des approvisionnements'}
    def table(rows, fields):
        return '<table><thead><tr>' + ''.join('<th>'+esc(label)+'</th>' for _, label in fields) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join('<td>'+esc('Non disponible / exclu' if row.get(key) is None else round(row[key], 3) if isinstance(row.get(key), float) else row.get(key, ''))+'</td>' for key, _ in fields) + '</tr>' for row in rows) + '</tbody></table>'
    parts = ['<!doctype html><html lang="fr"><meta charset="utf-8"><title>Aide à la décision — simulateur</title>',
        '<style>body{font:16px system-ui;margin:32px auto;max-width:1150px;padding:0 20px;color:#172b40;background:#f7fafc}section{background:white;padding:24px;margin:20px 0;border:1px solid #cbd5e1;border-radius:12px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;text-align:left;border-bottom:1px solid #ddd}a{color:#075985}p{line-height:1.5}</style>',
        '<h1>Référence, diagnostic et analyses de sensibilité</h1>',
        f'<p><a href="{esc(os.path.relpath(map_path, output).replace(os.sep, "/"))}">Ouvrir la carte du réseau</a> · <a href="decision-report.json">Rapport traçable JSON</a></p>',
        '<p><strong>Référence nominale : données et hypothèses du cas, cibles de sécurité réelles conservées.</strong> Le scénario risqué ajoute des hypothèses de stress. Les essais ×1,5 et d’accélération sont des analyses de sensibilité séparées : ils ne corrigent ni les données réelles ni la simulation de base.</p>',
        '<p>Les événements dépendants de l’état peuvent évoluer dans ces essais. Aucune recommandation de modifier les cibles réelles ni nouvelle campagne Monte Carlo.</p>',
        '<section><h2>1. Ce qui compose le score</h2>',
        table([{"part": component_labels[k], "score": v, "share": report["score"]["contribution_pct"][k]} for k,v in report["score"]["components"].items()], [("part","Composante"),("score","Points"),("share","Part du score (%)")]),
        '<p>Le score descriptif conserve les coefficients des composantes comparables. Les pertes matière et reports sans unité commune sont exclus. Le surcoût est également exclu lorsque la valorisation n’est pas complète ; une composante indisponible ne signifie pas un effet nul.</p>',
        '<h3>Audit des pertes</h3>',
        table(report['loss_audit']['by_item'],[("supplier_id","Fournisseur"),("item_id","Article"),("uom","Unité"),("loss_qty","Perte dans l’horizon")]),
        f'<p>Rapprochement avec le résumé : {esc(report["loss_audit"]["summary_matches"])}. Quantité arithmétique hors horizon exclue : {report["loss_audit"]["outside_horizon_qty"]:,.0f}. Doublons exacts avec perte positive : {report["loss_audit"]["exact_duplicate_positive_loss_rows"]}.</p></section>',
        '<section><h2>2. Service et retard par produit</h2><p>FIFO reconstruit : les plus anciennes demandes sont servies en premier. Ce ne sont pas des délais promis observés. La borne basse du service le jour de la demande correspond à FIFO ; la borne haute sert la demande du jour en premier. Les demandes encore ouvertes sont exclues du délai moyen des quantités servies.</p><p>Cette reconstruction conserve les fractions de demande prévisionnelle. Le délai maximal peut donc concerner un reliquat inférieur à une unité ; il ne prouve alors pas le retard d’une commande physique.</p>']
    for label, values in report['delays'].items():
        parts += ['<h3>'+esc({'nominal':'Nominal','risk':'Avec risques'}[label])+'</h3>', table(values,[("item_id","Produit"),("same_day_service_lower_pct","Service jour même : borne basse %"),("same_day_service_upper_pct","Borne haute %"),("mean_delay_served_fifo_days","Délai moyen FIFO servi (j)"),("max_delay_served_fifo_days","Délai max servi (j)"),("oldest_unserved_fifo_days","Âge max encore ouvert (j)")])]
    parts += ['</section><section><h2>3. Blocages de production et éléments justificatifs</h2>',
        table(report['bottlenecks']['ranked'],[("node_id","Usine"),("product_item_id","Produit"),("component_item_id","Composant limitant"),("blocked_days","Jours bloqués"),("suppliers","Fournisseurs de la liaison")]),
        '<p><a href="constraint-evidence.csv">Lignes de contraintes avec numéro de source</a> · <a href="lot-causal-evidence.csv">Liens explicites événements–lots</a></p>',
        '<p>Les fournisseurs sont reliés par les liaisons du graphe. Les événements et lots disposent de liens causaux explicites dans le moteur ; leur contribution au retard client n’est pas quantifiée ici. Les déficits répétés d’une campagne ne sont pas des unités perdues distinctes.</p></section>',
        '<section><h2>4. Analyses de sensibilité — hors référence nominale</h2>',
        table([{"action": action_labels[k], **v, "service_pct":100*v['fill_rate']} for k,v in report['actions'].items()],[("action","Action"),("service_pct","Service cumulé (%)"),("ending_backlog","Reliquat final"),("backlog_quantity_days","Reliquat cumulé (unités·jours)"),("operating_cost","Coût opérationnel connu"),("external_procurement_cost","Approvisionnement externe"),("economic_exposure","Exposition économique connue"),("valuation_status","Couverture de valorisation"),("cost_delta_vs_risk","Écart opérationnel vs risques")]),
        '<p>Les montants sont des coûts du modèle. Si la couverture est incomplète ou inconnue, ce sont des sous-totaux connus et leur différence ne prouve aucune économie globale. Aucun classement économique n’est alors qualifié. Une couverture complète des taux configurés ne certifie pas leur calibration industrielle.</p>',
        '<p>Stock : cible de sécurité ×1,5 sur les composants sélectionnés. Accélération : niveau modéré (0,5 sur l’échelle 0–1 du modèle) sur leurs liaisons fournisseurs. Les majorations de transport modélisées sont incluses ; les coûts de déploiement non modélisés ne le sont pas. Les journaux des commandes et leurs empreintes figurent dans le dossier actions.</p></section>',
        '<section><h2>5. Contrôles et limites</h2><p>Les rapprochements, empreintes et le statut de vérification du navigateur sont dans <a href="delivery.json">le bilan de livraison</a>. Un contrôle technique ne valide pas les hypothèses métier.</p></section></html>']
    (output/'index.html').write_text(''.join(parts), encoding='utf-8')


def deliver(run, execute_actions=False, render_map=False, browser=False):
    from etudecas.testing.qualification import require_run_invariants
    require_run_invariants(run)
    risk_candidate = run / "scenario_runs/state_dependent_full"
    if risk_candidate.exists():
        require_run_invariants(risk_candidate)
    risk = run / 'scenario_runs/state_dependent_full'
    output = run / 'decision_support'
    output.mkdir(parents=True, exist_ok=True)
    write_json(output/'delivery.json', {'ok': False, 'status': 'running'})
    previous = read_json(output/'decision-report.json') if (output/'decision-report.json').exists() else None
    manifest = read_json(risk/'run_manifest.json')
    graph_path = REPO / manifest['input_graph']
    graph = read_json(graph_path)
    nominal_graph_path = REPO / read_json(run/'run_manifest.json')['input_graph']
    payload = build_scenario_comparison_payload(run)
    risk_kpis = next(s['kpis'] for s in payload['scenarios'] if s['id'] == risk.name)
    report = {'scope': 'Descriptive score, FIFO reconstruction and exploratory controls',
              'score': score_breakdown(risk_kpis), 'delays': {}, 'actions': {},
              'loss_audit': audit_losses(risk, manifest['days']),
              'bottlenecks': bottlenecks(risk, graph, output), 'source_hashes': {}}
    for path in [graph_path, nominal_graph_path, Path(__file__), REPO/'etudecas/decision_actions.py',
                 REPO/'etudecas/simulation/engine/run_first_simulation.py']:
        report['source_hashes'][str(path.resolve())] = file_hash(path)
    for label, source in [('nominal', run), ('risk', risk)]:
        days = read_json(source/'summaries/first_simulation_summary.json')['sim_days']
        report['delays'][label] = fifo_delay(csv_rows(source/'data/production_demand_service_daily.csv'), days)
        for filename in ['production_demand_service_daily.csv','production_supplier_shipments_daily.csv','production_constraint_daily.csv','lot_causal_links.csv']:
            path=source/'data'/filename
            report['source_hashes'][str(path.resolve())]=file_hash(path)
        summary_path=source/'summaries/first_simulation_summary.json'
        report['source_hashes'][str(summary_path.resolve())]=file_hash(summary_path)
    report['actions']['risk_reference'] = action_metrics(risk)
    targets=[]
    for entry in report['bottlenecks']['ranked'][:2]:
        for supplier in entry['suppliers']:
            target=dict(supplier_id=supplier,dst_node_id=entry['node_id'],item_id=entry['component_item_id'])
            if target not in targets: targets.append(target)
    report['action_targets']=targets
    if execute_actions:
        from etudecas.decision_actions import execute_action
        for action in ('safety_150','expedite_50'):
            action_run=execute_action(risk,output/'actions',action,targets)
            require_run_invariants(action_run)
            report['actions'][action]=action_metrics(action_run)
            for path in [action_run/'summaries/first_simulation_summary.json',
                         action_run/'data/production_demand_service_daily.csv',
                         action_run/'data/canonical_action_ledger.csv',output/'actions'/f'{action}-execution.json']:
                report['source_hashes'][str(path.resolve())]=file_hash(path)
    for result in report['actions'].values():
        result['cost_delta_vs_risk']=result['total_cost']-report['actions']['risk_reference']['total_cost']
    map_path=run/'maps'/f'supply_graph_{run.name}.html'
    if render_map:
        from etudecas import run_etudecas_pipeline as pipeline
        map_path=pipeline.build_map_for_simulation_result(input_graph=nominal_graph_path,
            output_dir=run,supplier_criticality_dir=run/'supplier_criticality',simulated_risk_output_dir=risk,
            title='Simulation 5 ans - diagnostic et actions exploratoires')
    if not map_path.exists():
        raise ValueError('Map missing: use --render-map')
    # Relative link keeps the map usable offline and connects the evidence dashboard.
    text=map_path.read_text(encoding='utf-8')
    if 'id="decisionSupportLink"' not in text:
        text=text.replace('</body>', '<a id="decisionSupportLink" href="../decision_support/index.html" style="position:fixed;bottom:12px;left:12px;z-index:9999;background:white;padding:10px;border:1px solid #0369a1;border-radius:6px;color:#075985">Diagnostic métier et actions</a></body>')
        map_path.write_text(text,encoding='utf-8')
    write_json(output/'decision-report.json',report)
    render_report(output,report,map_path)
    from etudecas import run_etudecas_pipeline as pipeline
    pipeline.export_run_package(output_dir=run,input_graph=nominal_graph_path,map_html=map_path,
        extra_metadata={'decision_support':str(output.resolve()),'uncertainty':'not_computed'})
    for action in ('safety_150','expedite_50'):
        if action in report['actions']:
            pipeline.export_run_package(output_dir=Path(report['actions'][action]['run']),input_graph=graph_path,
                extra_metadata={'action':action,'reference_run':str(risk.resolve())})
    validations=[reconcile_run(run),reconcile_run(risk)]
    for action in ('safety_150','expedite_50'):
        if action in report['actions']: validations.append(reconcile_run(Path(report['actions'][action]['run'])))
    delivery={'runs':validations,'browser_requested':browser,'browser_errors':[],
        'html_sha256':file_hash(map_path),'report_sha256':file_hash(output/'decision-report.json'),
        'changes':{'previous_report_available':previous is not None,'score_before':previous['score']['total'] if previous else None,'score_after':report['score']['total']}}
    if browser:
        from etudecas.testing.map_browser import review_map
        reviewed=review_map(map_path,output/'browser')
        delivery['browser_errors']=reconcile_browser(reviewed,validations[:2])
        from etudecas.testing.lot_browser_review import review as review_lots
        lot_review = review_lots(map_path, output / 'browser-lots')
        delivery['lot_browser_ok'] = lot_review['ok']
        if not lot_review['ok']:
            delivery['browser_errors'].append('Lot causality or display checks failed')
    for command in ('build-all','check-all'):
        subprocess.run([sys.executable,'-S','-m','etudecas.documentation',command],cwd=REPO,check=True)
    delivery['ok']=all(r['ok'] for r in validations) and not delivery['browser_errors'] and report['loss_audit']['summary_matches']
    delivery['status']='complete' if delivery['ok'] else 'failed'
    write_json(output/'delivery.json',delivery)
    if not delivery['ok']: raise DeliveryValidationError(delivery)
    return output


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--execute-actions',action='store_true')
    parser.add_argument('--render-map',action='store_true')
    parser.add_argument('--browser',action='store_true')
    parser.add_argument('--rebuild',action='store_true',help='Create nominal and risk runs first; requires a new output directory. No Monte Carlo.')
    args=parser.parse_args(argv)
    if args.rebuild:
        if args.run.exists():
            parser.error('--rebuild requires a new output directory')
        subprocess.run([sys.executable,'etudecas/run_etudecas_pipeline.py','rebuild-map-5y',
            '--days','1825','--state-dependent-scenarios','full','--no-require-montecarlo',
            '--output-dir',str(args.run.resolve())],cwd=REPO,check=True)
    try:
        print(deliver(args.run.resolve(),args.execute_actions,args.render_map and not args.rebuild,args.browser))
    except Exception as exc:
        write_json(args.run.resolve()/'decision_support/delivery.json',
                   {**getattr(exc, 'delivery_report', {}), 'ok':False,'status':'failed','error':str(exc)})
        raise


if __name__=='__main__':
    main()
