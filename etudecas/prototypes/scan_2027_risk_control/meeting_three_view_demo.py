#!/usr/bin/env python3
"""Build the compact, three-view meeting demo from an existing portable demo.

The source package is treated as immutable.  The builder creates a new package
containing only the two incident maps and the decision page, then the existing
``standalone_single_html`` builder can turn that package into one movable HTML.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


SOURCE_VIEWS = {
    "delay": "carte_retard_338929_incident_lots.html",
    "quality": "carte_qualite_incident_lots.html",
    "decisions": "stress_tests_incidents_lots.html",
}
OUTPUT_VIEWS = {
    "delay": "01_retard_338929.html",
    "quality": "02_retenue_qualite.html",
    "decisions": "03_decisions.html",
}
PLOTLY_FILE = "plotly-2.32.0.min.js"
TOPOLOGY_FILE = "world_110m.json"


@dataclass(frozen=True)
class MapPresentation:
    key: str
    step: int
    title: str
    question: str
    chain: str
    hypothesis: str
    result: str
    cascade_token: str
    cascade_value: str
    preferred_lot_id: str
    preferred_lot_tokens: tuple[str, ...]


MAP_PRESENTATIONS = {
    "delay": MapPresentation(
        key="delay",
        step=1,
        title="Retard 338929 — cascade et lots simulés",
        question="La protection absorbe-t-elle le retard du composant 338929 ?",
        chain="SDC-VD0914360C → stock 338929 à M-1810 → produit 268091 → client",
        hypothesis=(
            "Du J0 au J89, 35 jours sont ajoutés au transport des nouvelles expéditions "
            "de 338929. Les expéditions déjà en transit ne sont pas redatées."
        ),
        result=(
            "L’incident imposé est absorbé avant le client dans 8 simulations sur 10. "
            "Dans la simulation détaillée, 1,99 M d’unités et 180 lots finis 268091 sont exposés."
        ),
        cascade_token="338929",
        cascade_value="SDC-VD0914360C|338929|M-1810|268091|service_client",
        preferred_lot_id="LOT-00003637",
        preferred_lot_tokens=("268091", "338929"),
    ),
    "quality": MapPresentation(
        key="quality",
        step=2,
        title="Retenue qualité 021081 — cascade et lots simulés",
        question="Quels lots, productions et clients sont exposés par la retenue qualité ?",
        chain="3 sources → matière 021081 → intermédiaire 773474 → produit 268967 → client",
        hypothesis=(
            "Du J45 au J200, 90 jours sont ajoutés avant disponibilité aux nouveaux lots "
            "de 021081 provenant de trois sources. Le stock existant et la matière déjà en "
            "transit ne sont pas retenus ; aucune matière n’est détruite."
        ),
        result=(
            "La propagation atteint le client dans 9 simulations sur 10. Dans la simulation "
            "détaillée, 120 000 kg et 22 lots finis 268967 sont exposés."
        ),
        cascade_token="021081",
        cascade_value="scenario_aggregate|item:021081|quality",
        preferred_lot_id="LOT-00006213",
        preferred_lot_tokens=("268967", "021081", "773474"),
    ),
}


ROUTE_ITEMS = (
    ("01_retard_338929.html", "1/3 · Retard 338929"),
    ("02_retenue_qualite.html", "2/3 · Retenue qualité"),
    ("03_decisions.html", "3/3 · Décisions"),
)


MAP_STYLE = r"""
<style id="meetingPresentationStyle">
  body.meetingPresentation{background:#eef3f8}
  body.meetingPresentation .toolbar{padding:0;gap:0;align-items:stretch;border-bottom:0;box-shadow:0 8px 26px rgba(15,39,67,.12)}
  body.meetingPresentation .toolbar>.title,
  body.meetingPresentation .toolbar>.meta,
  body.meetingPresentation .toolbar>.box{display:none!important}
  body.meetingPresentation #meetingGuide{display:block;flex:0 0 100%;width:100%;background:#fff}
  body.meetingPresentation #simulatedRiskLegend,
  body.meetingPresentation #sensitivityLegend,
  body.meetingPresentation #riskLegend,
  body.meetingPresentation #uncertaintyLegend,
  body.meetingPresentation .supplierBriefReturn{display:none!important}
  #meetingGuide{display:none;font:14px/1.4 Inter,Segoe UI,Arial,sans-serif;color:#10233f}
  .meetingRoute{display:flex;align-items:center;gap:8px;padding:9px 16px;background:#0b2748;color:#fff;overflow:auto}
  .meetingRouteLabel{font-size:11px;font-weight:900;letter-spacing:.11em;white-space:nowrap;margin-right:4px;color:#9fe6d7}
  .meetingRoute a{color:#dceaf7;text-decoration:none;border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:6px 10px;white-space:nowrap;font-weight:750;font-size:12px}
  .meetingRoute a.active{background:#fff;color:#0b2748;border-color:#fff}
  .meetingStory{display:grid;grid-template-columns:minmax(340px,1.2fr) minmax(360px,1fr) auto;gap:14px;align-items:center;padding:12px 16px}
  .meetingStory h1{font-size:20px;line-height:1.15;margin:0 0 4px;color:#0b2748}
  .meetingStoryQuestion{margin:0;color:#526579;font-size:13px}.meetingStoryChain{margin:3px 0 0;color:#1e5c91;font-size:11px;font-weight:800}
  .meetingFacts{display:grid;gap:5px}.meetingFacts p{margin:0;font-size:12px;color:#334155}
  .proofTag{display:inline-block;border-radius:999px;padding:3px 7px;margin-right:5px;font-size:10px;font-weight:900;letter-spacing:.06em;vertical-align:1px}
  .proofTag.hypothesis{background:#fff4dc;color:#8a4b00}.proofTag.simulated{background:#e7f6f1;color:#087257}
  .meetingActions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;min-width:260px}
  .meetingActions button{border:0;border-radius:999px;padding:9px 12px;cursor:pointer;font-weight:800;background:#123e70;color:#fff}
  .meetingActions button.secondary{background:#eaf1f9;color:#123e70;border:1px solid #b8c9dc}
  .meetingProof{display:flex;gap:9px;align-items:center;overflow:auto;border-top:1px solid #e2e8f0;padding:7px 16px;background:#f8fafc;color:#526579;font-size:10.5px;white-space:nowrap}
  .meetingProof b{color:#0b2748}.meetingProof .separator{color:#a8b4c1}
  .meetingMapHint{margin-left:auto;color:#1e5c91;font-weight:750}
  body.meetingPresentation #chart{height:calc(100vh - 194px)!important;min-height:520px}
  @media(max-width:980px){.meetingStory{grid-template-columns:1fr}.meetingActions{justify-content:flex-start}.meetingProof{white-space:normal;flex-wrap:wrap}.meetingMapHint{margin-left:0}body.meetingPresentation #chart{height:calc(100vh - 285px)!important}}
</style>
"""


DECISION_STYLE = r"""
<style id="meetingDecisionStyle">
  .meetingGuideDecision{position:sticky;top:0;z-index:30;background:#fff;box-shadow:0 7px 24px rgba(15,39,67,.13);font:14px/1.4 Inter,Segoe UI,Arial,sans-serif}
  .meetingGuideDecision .meetingRoute{display:flex;align-items:center;gap:8px;padding:9px 16px;background:#0b2748;color:#fff;overflow:auto}
  .meetingGuideDecision .meetingRouteLabel{font-size:11px;font-weight:900;letter-spacing:.11em;white-space:nowrap;margin-right:4px;color:#9fe6d7}
  .meetingGuideDecision .meetingRoute a{color:#dceaf7;background:transparent;text-decoration:none;border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:6px 10px;white-space:nowrap;font-weight:750;font-size:12px}
  .meetingGuideDecision .meetingRoute a.active{background:#fff;color:#0b2748;border-color:#fff}
  .meetingGuideDecision .meetingProof{display:flex;gap:9px;align-items:center;overflow:auto;padding:7px 16px;background:#f8fafc;color:#526579;font-size:10.5px;white-space:nowrap;border-bottom:1px solid #e2e8f0}
  .meetingGuideDecision .meetingProof b{color:#0b2748}.meetingGuideDecision .separator{color:#a8b4c1}
  body>nav:not(.meetingRoute){top:70px}
  .evidence-board{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 0 28px;border-bottom:1px solid var(--line)}
  .evidence-card{background:#fff;border:1px solid var(--line);border-radius:15px;padding:16px;box-shadow:var(--shadow);font-size:14px}
  .evidence-card h3{font-size:14px;margin:0 0 7px}.evidence-card p{margin:0;color:var(--muted)}
  .evidence-card.observed{border-top:5px solid #475569}.evidence-card.simulated{border-top:5px solid #11875d}.evidence-card.priority{border-top:5px solid #246bfe}.evidence-card.hypothesis{border-top:5px solid #b86b00}
  .sensitivity-intro{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.6fr);gap:18px;align-items:start;margin:18px 0}
  .method-box{background:#fff;border:1px solid var(--line);border-radius:15px;padding:16px;box-shadow:var(--shadow);font-size:14px}.method-box strong{display:block;color:#123e70;font-size:24px}.method-box p{margin:5px 0 0;color:var(--muted)}
  .sensitivity-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:20px 0}.sensitivity-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:17px;box-shadow:var(--shadow)}
  .sensitivity-card h3{font-size:19px}.sensitivity-card>p{color:var(--muted);margin:7px 0}.sensitivity-card .verdict{border-left:4px solid #246bfe;background:#edf3ff;color:#173d69;padding:9px 11px;border-radius:8px}
  .mini-curve{display:block;width:100%;height:auto;margin:10px 0 5px;background:#fbfdff;border:1px solid #e5ebf2;border-radius:11px}.mini-grid{stroke:#dfe7ef;stroke-width:1}.mini-axis{font:11px Segoe UI,Arial;fill:#617286}.mini-line{fill:none;stroke-width:3;stroke-linejoin:round;stroke-linecap:round}.mini-point{stroke:#fff;stroke-width:2}
  .action-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:20px 0}.action-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:var(--shadow)}.action-card.effective{border-top:6px solid #11875d}.action-card.partial{border-top:6px solid #d58b19}.action-card.next{border-top:6px solid #246bfe}
  .action-status{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:900;letter-spacing:.04em;background:#edf3ff;color:#154f9b}.action-card.effective .action-status{background:#e7f6f1;color:#087257}.action-card.partial .action-status{background:#fff4df;color:#875100}.action-card h3{margin-top:10px}.action-card ul{padding-left:19px;color:var(--muted)}.action-card li{margin:6px 0}
  .not-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:16px}.not-action{background:#fff5f3;border:1px solid #efc2bc;border-radius:12px;padding:12px;font-size:13px}.not-action strong{display:block;color:#9f261e;margin-bottom:4px}
  .simChartNote{display:inline-block;margin:0 0 8px;border-radius:999px;padding:5px 9px;background:#e7f6f1;color:#087257;font-size:11px;font-weight:900;letter-spacing:.04em}
  .permanent-reading{max-width:1240px;margin:18px auto 0;padding:12px 18px;border:1px solid #9ccfc0;border-radius:13px;background:#eaf7f1;color:#125b49;font-weight:750}
  .supplierBriefReturn{display:none!important}
  @media(max-width:920px){.evidence-board,.sensitivity-grid{grid-template-columns:1fr 1fr}.action-grid{grid-template-columns:1fr}.not-actions{grid-template-columns:1fr 1fr}.sensitivity-intro{grid-template-columns:1fr}.meetingGuideDecision .meetingProof{white-space:normal;flex-wrap:wrap}body>nav:not(.meetingRoute){top:102px}}
  @media(max-width:620px){.evidence-board,.sensitivity-grid,.not-actions{grid-template-columns:1fr}}
</style>
"""


INDEX_HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Parcours rendez-vous Supply Chain — 3 vues</title>
  <style>
    :root{--navy:#0b2748;--blue:#246bfe;--green:#11875d;--paper:#eef3f8;--line:#d7e1ec;--ink:#10233f}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Inter,Segoe UI,Arial,sans-serif}
    header{padding:52px max(24px,calc((100vw - 1120px)/2));background:linear-gradient(125deg,#071a31,#123d70 65%,#0c6f67);color:#fff}
    header span{font-size:12px;font-weight:900;letter-spacing:.13em;color:#8de6d1}h1{font-size:clamp(36px,5vw,60px);line-height:1.05;margin:10px 0 15px}header p{max-width:800px;color:#d9e8f6;font-size:19px}
    main{max-width:1120px;margin:auto;padding:28px 22px 60px}.route{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.card{display:block;background:#fff;border:1px solid var(--line);border-radius:17px;padding:20px;text-decoration:none;box-shadow:0 14px 36px rgba(15,39,67,.08)}.card b{display:block;color:var(--blue);font-size:13px}.card h2{margin:6px 0 8px;font-size:23px}.card p{margin:0;color:#5b6c7f}.proof{margin-top:18px;padding:17px;background:#fff;border:1px solid var(--line);border-radius:15px}.proof b{color:var(--navy)}
    @media(max-width:760px){.route{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <header><span>PARCOURS RENDEZ-VOUS · TROIS VUES</span><h1>Du risque fournisseur à la décision</h1><p>Le fichier autonome ouvre directement le retard 338929, puis la retenue qualité, avant de comparer les décisions. Les anciennes cartes ne sont pas modifiées.</p></header>
  <main>
    <div class="route">
      <a class="card" href="views/01_retard_338929.html"><b>VUE 1/3</b><h2>Retard 338929</h2><p>Voir la cascade simulée et ouvrir la généalogie d’un lot exposé.</p></a>
      <a class="card" href="views/02_retenue_qualite.html"><b>VUE 2/3</b><h2>Retenue qualité</h2><p>Suivre la propagation multi-niveaux vers les lots, la production et le client.</p></a>
      <a class="card" href="views/03_decisions.html"><b>VUE 3/3</b><h2>Décisions</h2><p>Comparer les solutions simulées, les jours récupérés, le coût et le risque restant.</p></a>
    </div>
    <p class="proof"><b>Cadre de lecture :</b> OBSERVÉ = données industrielles 2025 ; SIMULÉ = résultat du moteur ; SIGNAL DE PRIORITÉ = dossier à instruire, pas une probabilité ; HYPOTHÈSE = incident, action ou paramètre à valider.</p>
  </main>
  <script>
    window.addEventListener("load", () => {
      let attempts = 0;
      const timer = setInterval(() => {
        if (window.ETUDECAS_SINGLE_HTML) {
          clearInterval(timer);
          window.ETUDECAS_SINGLE_HTML.openView("views/01_retard_338929.html");
        } else if (++attempts > 200) clearInterval(timer);
      }, 25);
    }, {once:true});
  </script>
</body>
</html>
"""


def _route(step: int, *, wrapper_class: str = "meetingRoute") -> str:
    links = []
    for index, (path, label) in enumerate(ROUTE_ITEMS, start=1):
        active = ' class="active" aria-current="page"' if index == step else ""
        links.append(f'<a href="{path}"{active}>{html.escape(label)}</a>')
    return (
        f'<nav class="{wrapper_class}" aria-label="Parcours de démonstration">'
        '<span class="meetingRouteLabel">PARCOURS RENDEZ-VOUS</span>'
        + "".join(links)
        + "</nav>"
    )


def _proof_line() -> str:
    return """<div class="meetingProof" aria-label="Cadre de preuve">
  <span><b>VOS DONNÉES 2025</b> (OBSERVÉ)</span><span class="separator">|</span>
  <span><b>CE QUI POURRAIT ARRIVER</b> (SIMULÉ)</span><span class="separator">|</span>
  <span><b>OÙ REGARDER D’ABORD</b> (SIGNAL DE PRIORITÉ)</span><span class="separator">|</span>
  <span><b>À CONFIRMER AVEC VOS ÉQUIPES</b> (HYPOTHÈSE)</span>
</div>"""


def _map_guide(spec: MapPresentation) -> str:
    next_path, next_label = ROUTE_ITEMS[spec.step]
    return f"""<div id="meetingGuide" aria-label="Mode présentation rendez-vous">
  {_route(spec.step)}
  <div class="meetingStory">
    <div><h1>{html.escape(spec.title)}</h1><p class="meetingStoryQuestion">{html.escape(spec.question)}</p><p class="meetingStoryChain">{html.escape(spec.chain)}</p></div>
    <div class="meetingFacts">
      <p><span class="proofTag hypothesis">HYPOTHÈSE</span>{html.escape(spec.hypothesis)}</p>
      <p><span class="proofTag simulated">SIMULÉ</span>{html.escape(spec.result)}</p>
    </div>
    <div class="meetingActions">
      <button id="meetingCascadeBtn" type="button">Recentrer sur la cascade</button>
      <button id="meetingLotBtn" class="secondary" type="button">Ouvrir un lot exposé</button>
      <a href="{next_path}" style="display:none" aria-hidden="true">{html.escape(next_label)}</a>
    </div>
  </div>
  {_proof_line()[:-6]}<span class="meetingMapHint">Carte, flux et lots de cette vue : SIMULÉS</span></div>
</div>"""


def _map_script(spec: MapPresentation) -> str:
    replacements = [
        ["Origine priorisée par impact aval observé", "Origine priorisée par impact aval simulé"],
        ["Origine priorisee par impact aval observe", "Origine priorisee par impact aval simule"],
        ["Origine dominante des problèmes observés", "Origine dominante des problèmes simulés"],
        ["Origine dominante des problemes observes", "Origine dominante des problemes simules"],
        ["Aval observé", "Aval simulé"],
        ["Aval observe", "Aval simule"],
        ["impact réel du scénario", "impact simulé du scénario"],
        ["impact reel du scenario", "impact simule du scenario"],
        ["impact supply réel", "impact supply simulé"],
        ["impact supply reel", "impact supply simule"],
        ["impact réel observé", "impact simulé calculé"],
        ["impact reel observe", "impact simule calcule"],
        ["Impact réel observé", "Impact simulé calculé"],
        ["Impact reel observe", "Impact simule calcule"],
        ["impact observé", "impact simulé"],
        ["impact observe", "impact simule"],
        ["Impact observé", "Impact simulé"],
        ["Impact observe", "Impact simule"],
        ["Impact réel", "Impact simulé"],
        ["Impact reel", "Impact simule"],
        ["propagation aval observée", "propagation aval simulée"],
        ["propagation aval observee", "propagation aval simulee"],
        ["Propagation aval observée", "Propagation aval simulée"],
        ["Propagation aval observee", "Propagation aval simulee"],
        ["effet observé", "effet simulé"],
        ["effet observe", "effet simule"],
        ["a créé un effet observable", "a produit un effet dans la simulation"],
        ["a cree un effet observable", "a produit un effet dans la simulation"],
        ["flux et transits observés", "flux et transits simulés"],
        ["flux et transits observes", "flux et transits simules"],
        ["transit observé", "transit simulé"],
        ["transit observe", "transit simule"],
        ["production réelle cumulée", "production exécutée dans la simulation"],
        ["production reelle cumulee", "production executee dans la simulation"],
        ["production réellement faite", "production exécutée par le simulateur"],
        ["production reellement faite", "production executee par le simulateur"],
        ["réception réelle", "réception simulée à la date calculée"],
        ["reception reelle", "reception simulee a la date calculee"],
        ["pas de report usine observé", "aucun report usine simulé dans cette simulation"],
        ["pas de report usine observe", "aucun report usine simule dans cette simulation"],
        ["Production : pas de report usine observé", "Production : aucun report usine simulé dans cette simulation"],
        ["Production : pas de report usine observe", "Production : aucun report usine simule dans cette simulation"],
        ["pas de backlog observé", "aucun retard client simulé dans cette simulation"],
        ["pas de backlog observe", "aucun retard client simule dans cette simulation"],
        ["Client : pas de backlog observé", "Client : aucun retard client simulé dans cette simulation"],
        ["Client : pas de backlog observe", "Client : aucun retard client simule dans cette simulation"],
        ["Filtre les cascades par impact observé", "Filtrer selon le type d’impact simulé"],
        ["Filtre les cascades par impact observe", "Filtrer selon le type d'impact simule"],
        ["écarts observés dans les runs Monte-Carlo", "écarts simulés entre les répétitions Monte-Carlo"],
        ["ecarts observes dans les runs Monte-Carlo", "ecarts simules entre les repetitions Monte-Carlo"],
        ["Scénario injecté", "Hypothèse d’incident simulée"],
        ["Scenario injecte", "Hypothese d'incident simulee"],
        ["Criticité fournisseurs", "Signal de priorité fournisseurs"],
        ["Criticite fournisseurs", "Signal de priorite fournisseurs"],
        ["Score criticité fournisseur", "Signal de priorité fournisseur"],
        ["Score criticite fournisseur", "Signal de priorite fournisseur"],
        ["Criticité fournisseur", "Signal de priorité fournisseur"],
        ["Criticite fournisseur", "Signal de priorite fournisseur"],
        ["Niveau de criticité", "Niveau du signal de priorité"],
        ["Niveau de criticite", "Niveau du signal de priorite"],
        ["Criticité = menace fournisseur x importance supply x sensibilité", "Signal de priorité = score exploratoire construit à partir des informations disponibles et des états simulés"],
        ["Criticite = menace fournisseur x importance supply x sensibilite", "Signal de priorite = score exploratoire construit a partir des informations disponibles et des etats simules"],
        ["quel fournisseur est critique et mérite une action ou une surveillance ?", "quels dossiers fournisseur–article instruire en premier ?"],
        ["quel fournisseur est critique et merite une action ou une surveillance ?", "quels dossiers fournisseur-article instruire en premier ?"],
        ["Action recommandée", "Action à examiner"],
        ["Action recommandee", "Action a examiner"],
        ["run courant", "simulation courante"],
        ["dans le run", "dans la simulation"],
    ]
    exact_replacements = {
        "Réel": "Exécuté (simulé)",
        "Reel": "Execute (simule)",
        "Criticité": "Signal de priorité",
        "Criticite": "Signal de priorite",
    }
    return f"""<script id="meetingPresentationRuntime">
(() => {{
  "use strict";
  const cascadeToken = {json.dumps(spec.cascade_token, ensure_ascii=False)};
  const cascadeValue = {json.dumps(spec.cascade_value, ensure_ascii=False)};
  const preferredLotId = {json.dumps(spec.preferred_lot_id, ensure_ascii=False)};
  const lotTokens = {json.dumps(spec.preferred_lot_tokens, ensure_ascii=False)};
  const replacements = {json.dumps(replacements, ensure_ascii=False)};
  const exactReplacements = {json.dumps(exact_replacements, ensure_ascii=False)};

  const normalizeVisibleText = (root = document.body) => {{
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {{
      const parent = node.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "NOSCRIPT"].includes(parent.tagName)) return;
      let value = node.nodeValue || "";
      const trimmed = value.trim();
      if (Object.prototype.hasOwnProperty.call(exactReplacements, trimmed)) {{
        value = value.replace(trimmed, exactReplacements[trimmed]);
      }}
      replacements.forEach(([from, to]) => {{ value = value.split(from).join(to); }});
      if (value !== node.nodeValue) node.nodeValue = value;
    }});
  }};

  const resizeMap = () => {{
    const chart = document.getElementById("chart");
    if (chart && window.Plotly && Plotly.Plots && Plotly.Plots.resize) {{
      try {{ Plotly.Plots.resize(chart); }} catch (_error) {{}}
    }}
  }};

  const chooseCascadeOption = (select) => {{
    const options = Array.from(select.options || []).filter((option) => option.value);
    return options.find((option) => option.value === cascadeValue)
      || options.find((option) => option.value.startsWith("scenario_aggregate") && option.textContent.includes(cascadeToken))
      || options.find((option) => option.textContent.includes(cascadeToken))
      || options.find((option) => option.value.includes(cascadeToken))
      || options[0];
  }};

  const showCascade = () => {{
    const mode = document.getElementById("modeSimulatedRisk");
    const select = document.getElementById("simulatedRiskCascadeSelect");
    if (!mode || !select || select.options.length < 2) return false;
    mode.click();
    setTimeout(() => {{
      const option = chooseCascadeOption(select);
      if (option) {{
        select.value = option.value;
        select.dispatchEvent(new Event("change", {{bubbles:true}}));
      }}
      normalizeVisibleText();
      resizeMap();
    }}, 60);
    return true;
  }};

  const showLot = () => {{
    const mode = document.getElementById("modeOps");
    const select = document.getElementById("lotTraceSelect");
    const open = document.getElementById("lotTraceOpenBtn");
    if (!mode || !select || !open || select.options.length < 2) return false;
    mode.click();
    setTimeout(() => {{
      const options = Array.from(select.options || []).filter((option) => option.value);
      let option = options.find((candidate) => candidate.value === preferredLotId);
      for (const token of lotTokens) {{
        if (option) break;
        option = options.find((candidate) => candidate.textContent.includes(token));
      }}
      option = option || options[0];
      if (option) {{
        select.value = option.value;
        select.dispatchEvent(new Event("change", {{bubbles:true}}));
      }}
      setTimeout(() => {{ open.click(); normalizeVisibleText(); }}, 90);
    }}, 90);
    return true;
  }};

  document.body.classList.add("meetingPresentation");
  const guide = document.getElementById("meetingGuide");
  const toolbar = document.querySelector(".toolbar");
  if (guide && toolbar) toolbar.prepend(guide);
  document.getElementById("meetingCascadeBtn")?.addEventListener("click", showCascade);
  document.getElementById("meetingLotBtn")?.addEventListener("click", showLot);
  normalizeVisibleText();
  const observer = new MutationObserver((records) => {{
    records.forEach((record) => record.addedNodes.forEach((node) => {{
      if (node.nodeType === Node.TEXT_NODE) normalizeVisibleText(node.parentElement);
      else if (node.nodeType === Node.ELEMENT_NODE) normalizeVisibleText(node);
    }}));
  }});
  observer.observe(document.body, {{childList:true, subtree:true}});

  let attempts = 0;
  const timer = setInterval(() => {{
    if (showCascade() || ++attempts > 400) clearInterval(timer);
  }}, 50);
  window.addEventListener("resize", resizeMap);
  setTimeout(resizeMap, 800);
}})();
</script>
"""


def transform_map_view(document: str, spec: MapPresentation) -> str:
    """Add a presentation-only shell around an existing detailed map."""
    if "</head>" not in document or "<body>" not in document or "</body>" not in document:
        raise ValueError("Map document is missing a plain head/body marker")
    if 'id="modeSimulatedRisk"' not in document or 'id="lotTraceSelect"' not in document:
        raise ValueError("Map document does not expose the required cascade and lot controls")
    document = re.sub(
        r"<title>.*?</title>",
        f"<title>Vue {spec.step}/3 — {html.escape(spec.title)}</title>",
        document,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    document = document.replace("</head>", MAP_STYLE + "</head>", 1)
    document = document.replace("<body>", "<body>" + _map_guide(spec), 1)
    document = document.replace("</body>", _map_script(spec) + "</body>", 1)
    return document


def _swap_hero_cards(document: str) -> str:
    pattern = re.compile(r'(<div class="hero-grid">)(.*?)(</div>\s*</header>)', re.DOTALL)
    match = pattern.search(document)
    if not match:
        raise ValueError("Decision page hero grid not found")
    cards = re.findall(r'<div class="hero-card">.*?</div>', match.group(2), flags=re.DOTALL)
    if len(cards) != 3:
        raise ValueError(f"Expected three hero cards, found {len(cards)}")
    replacement = match.group(1) + "\n      " + "\n      ".join((cards[1], cards[0], cards[2])) + "\n    " + match.group(3)
    return document[: match.start()] + replacement + document[match.end() :]


def _swap_summary_rows(document: str) -> str:
    pattern = re.compile(
        r'(<div class="summary-table">)(.*?)(</div>\s*<p class="definition">)',
        re.DOTALL,
    )
    match = pattern.search(document)
    if not match:
        raise ValueError("Decision summary table not found")
    cells = re.findall(r'<div class="(?:head|quality|delay)">.*?</div>', match.group(2), flags=re.DOTALL)
    if len(cells) != 9:
        raise ValueError(f"Expected nine summary cells, found {len(cells)}")
    ordered = cells[:3] + cells[6:9] + cells[3:6]
    replacement = match.group(1) + "\n        " + "\n        ".join(ordered) + "\n      " + match.group(3)
    return document[: match.start()] + replacement + document[match.end() :]


def _swap_incident_sections(document: str) -> str:
    quality_start = document.find('<section id="qualite">')
    delay_start = document.find('<section id="retard">')
    decisions_start = document.find('<section id="recommandations">')
    if not (0 <= quality_start < delay_start < decisions_start):
        raise ValueError("Decision page incident sections are missing or already reordered")
    return (
        document[:quality_start]
        + document[delay_start:decisions_start]
        + "\n\n    "
        + document[quality_start:delay_start]
        + document[decisions_start:]
    )


def _decision_guide() -> str:
    return f"""<div class="meetingGuideDecision" aria-label="Mode présentation rendez-vous">
  {_route(3)}
  {_proof_line()}
</div>
<p class="permanent-reading">Cette page distingue ce que vos données montrent, ce que le modèle teste et ce qui doit encore être confirmé. Une action n’est recommandée que si elle est réellement exécutée dans le moteur et produit un effet utile.</p>
"""


def _evidence_board() -> str:
    return """<section class="evidence-board" aria-label="Cadre de preuve commun">
  <article class="evidence-card observed"><h3>CE QUE VOUS NOUS AVEZ FOURNI — OBSERVÉ</h3><p>Vos chiffres 2025 établissent le niveau de service et le CA perdu par produit. Ils ne contiennent pas encore les incidents, lots ou retards fournisseurs qui expliquent ces résultats.</p></article>
  <article class="evidence-card simulated"><h3>CE QUE LE SCÉNARIO CALCULE — SIMULÉ</h3><p>Si l’incident décrit survient, le moteur calcule les stocks, productions, lots et clients susceptibles d’être touchés, puis compare les actions.</p></article>
  <article class="evidence-card priority"><h3>OÙ REGARDER D’ABORD — SIGNAL DE PRIORITÉ</h3><p>Le modèle aide à choisir les fournisseurs, composants et flux à examiner en premier. Ce classement n’est pas encore une probabilité de panne.</p></article>
  <article class="evidence-card hypothesis"><h3>CE QU’IL FAUT CONFIRMER — HYPOTHÈSE</h3><p>Délais, capacités, coûts, durée de retenue et faisabilité des actions doivent être remplacés par vos paramètres réels avant décision opérationnelle.</p></article>
</section>
"""


def _format_curve_x(value: float, kind: str) -> str:
    if kind == "units":
        return f"{value / 1000:.0f} k" if value >= 1000 else f"{value:.0f}"
    return (f"×{value:.2f}" if value < 1 else f"×{value:.2g}").replace(".", ",")


def _mini_curve_svg(
    points: tuple[tuple[float, float], ...],
    *,
    title: str,
    x_label: str,
    x_kind: str = "factor",
    color: str = "#246bfe",
) -> str:
    width, height = 520.0, 188.0
    left, right, top, bottom = 50.0, 16.0, 18.0, 43.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if y_max == y_min:
        y_min -= 0.5
        y_max += 0.5
    else:
        padding = max((y_max - y_min) * 0.12, 0.15)
        y_min -= padding
        y_max += padding

    def x_coord(value: float) -> float:
        return left + (value - x_min) * (width - left - right) / (x_max - x_min)

    def y_coord(value: float) -> float:
        return top + (y_max - value) * (height - top - bottom) / (y_max - y_min)

    coordinates = [(x_coord(x), y_coord(y)) for x, y in points]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinates)
    circles = "".join(
        f'<circle class="mini-point" cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>'
        for x, y in coordinates
    )
    tick_indices = sorted({0, len(points) // 2, len(points) - 1})
    x_ticks = "".join(
        f'<text class="mini-axis" x="{coordinates[index][0]:.1f}" y="{height - 22:.0f}" text-anchor="middle">{_format_curve_x(points[index][0], x_kind)}</text>'
        for index in tick_indices
    )
    y_ticks = "".join(
        f'<text class="mini-axis" x="{left - 7:.0f}" y="{y_coord(value) + 4:.1f}" text-anchor="end">{f"{value:.1f}%".replace(".", ",")}</text>'
        for value in (y_min, y_max)
    )
    return f"""<svg class="mini-curve" viewBox="0 0 520 188" role="img" aria-label="{html.escape(title, quote=True)}">
  <title>{html.escape(title)}</title>
  <line class="mini-grid" x1="{left:.0f}" y1="{top:.0f}" x2="{left:.0f}" y2="{height - bottom:.0f}"/>
  <line class="mini-grid" x1="{left:.0f}" y1="{height - bottom:.0f}" x2="{width - right:.0f}" y2="{height - bottom:.0f}"/>
  <polyline class="mini-line" points="{polyline}" stroke="{color}"/>{circles}{x_ticks}{y_ticks}
  <text class="mini-axis" x="{width / 2:.0f}" y="{height - 5:.0f}" text-anchor="middle">{html.escape(x_label)}</text>
  <text class="mini-axis" x="8" y="12">service du produit</text>
</svg>"""


def _decision_sensitivity_action_board() -> str:
    lead_curve = _mini_curve_svg(
        ((0.50, 95.83), (0.67, 95.03), (0.80, 93.82), (0.84, 94.22), (0.86, 91.81), (0.88, 93.42), (0.90, 91.00), (0.92, 91.00)),
        title="Sensibilité du service 268091 au délai du composant 338929",
        x_label="facteur appliqué au délai 338929",
        color="#246bfe",
    )
    plant_curve = _mini_curve_svg(
        ((1.05, 88.59), (1.15, 88.59), (1.30, 88.59), (1.50, 88.59), (2.00, 88.59), (3.00, 88.59)),
        title="Sensibilité du service 268091 à la capacité de M-1810",
        x_label="facteur appliqué à la capacité M-1810",
        color="#d92d20",
    )
    stock_curve = _mini_curve_svg(
        ((25000.0, 89.79), (50000.0, 91.41), (100000.0, 91.41), (200000.0, 91.41), (400000.0, 91.41)),
        title="Sensibilité du service 268091 au stock cible de 338929",
        x_label="stock cible 338929 (unités)",
        x_kind="units",
        color="#11875d",
    )
    upstream_curve = _mini_curve_svg(
        ((0.10, 69.89), (0.15, 69.89), (0.18, 69.89), (0.20, 83.58), (0.25, 83.58), (0.40, 100.00), (0.55, 100.00), (0.85, 100.00)),
        title="Sensibilité du service 268967 aux capacités fournisseurs directes vers M-1430",
        x_label="facteur de capacité fournisseur vers M-1430",
        color="#b86b00",
    )
    return f"""<section id="leviers" class="lever-board">
  <div class="eyebrow">CAUSE → GOULOT → ACTION</div>
  <h2>Dans le modèle, on repère les paramètres sensibles avant de choisir les leviers à tester sur vos flux</h2>
  <div class="sensitivity-intro">
    <p class="lead">Les 542 essais de sensibilité font varier un paramètre à la fois. Les 180 comparaisons d’incidents et d’actions repartent ensuite des mêmes dix situations initiales. Cette combinaison permet d’écarter les fausses bonnes idées avant de chiffrer une réponse.</p>
    <aside class="method-box"><strong>Deux analyses différentes</strong><p><b>Sensibilité :</b> quel paramètre rend la chaîne fragile ?<br><b>Comparaison d’actions :</b> quelle décision réduit effectivement l’impact ?</p></aside>
  </div>
  <div class="sensitivity-grid">
    <article class="sensitivity-card"><h3>338929 : le délai amont est sensible</h3>{lead_curve}<p>Dans les niveaux testés, le service de 268091 varie de 91,00 % à 95,83 %. La réponse est irrégulière car les lots et le calendrier créent des seuils.</p><p class="verdict"><strong>Conséquence métier :</strong> agir sur la date d’arrivée prévue et le transport est cohérent avec le goulot identifié.</p></article>
    <article class="sensitivity-card"><h3>M-1810 : ajouter de la capacité ne résout rien ici</h3>{plant_curve}<p>Multiplier la capacité de production de M-1810 de 1,05 à 3 laisse le service de 268091 inchangé à 88,59 % dans cette série d’essais.</p><p class="verdict"><strong>Conséquence métier :</strong> ne pas lancer d’heures supplémentaires ou d’investissement machine avant d’avoir sécurisé la matière.</p></article>
    <article class="sensitivity-card"><h3>338929 : le stock atteint rapidement un plateau</h3>{stock_curve}<p>Passer de 25 000 à 50 000 unités améliore le service de 1,61 point ; augmenter ensuite jusqu’à 400 000 n’apporte rien de plus dans ces essais.</p><p class="verdict"><strong>Conséquence métier :</strong> constituer un stock tampon avant l’incident, sans surstocker à l’aveugle.</p></article>
    <article class="sensitivity-card"><h3>268967 : une falaise de capacité existe en amont</h3>{upstream_curve}<p>Le service passe de 69,89 % à 83,58 %, puis presque 100 %, lorsque les capacités directes vers M-1430 franchissent des seuils. Ce test couvre d’autres composants de 268967 et n’attribue pas cette falaise à 021081.</p><p class="verdict"><strong>Conséquence métier :</strong> vérifier aussi les capacités réservées des autres composants, notamment 344135, avant de conclure qu’une seule action qualité suffira.</p></article>
  </div>

  <h2>Six actions pilotables : un responsable, une commande, un périmètre et un déclencheur</h2>
  <p class="definition"><strong>Règle de sélection :</strong> une action n’est retenue ici que si l’équipe peut décider quoi faire, sur quelle expédition, quel lot, quel stock ou quel ordre, et à quelle date. Une autorisation qualité favorable, une nouvelle capacité fournisseur ou une date de libération ne sont pas traitées comme des commandes disponibles.</p>
  <div class="action-grid">
    <article class="action-card effective"><span class="action-status">DÉJÀ SIMULÉ — SOUS CONDITIONS</span><h3>338929 — réserver un transport accéléré sur une expédition identifiée</h3><ul><li><strong>Commande :</strong> numéro d’expédition, mode de transport réservable, date de départ, jours gagnés et surcoût maximal.</li><li><strong>Responsable :</strong> approvisionneur et logisticien.</li><li><strong>Résultat du modèle :</strong> un gain de 7 jours supprime le retard dans les deux situations 338929 qui atteignent le client. La capacité du transport doit encore être confirmée.</li></ul></article>
    <article class="action-card partial"><span class="action-status">PRÉVENTIF — PILOTABLE</span><h3>338929 — constituer le stock tampon avant la période de risque</h3><ul><li><strong>Commande :</strong> quantité cible, site de stockage, date à laquelle le stock doit être disponible et commandes d’approvisionnement associées.</li><li><strong>Responsable :</strong> planificateur et approvisionneur.</li><li><strong>Résultat de sensibilité :</strong> passer de 25 000 à 50 000 unités gagne 1,61 point de service ; aucun gain supplémentaire n’apparaît ensuite dans les niveaux testés.</li></ul></article>
    <article class="action-card next"><span class="action-status">PILOTABLE — À AJOUTER AU MOTEUR</span><h3>Qualité — bloquer seulement les lots réellement concernés</h3><ul><li><strong>Commande :</strong> liste exacte des lots à bloquer, à maintenir disponibles ou à arrêter en production.</li><li><strong>Responsable :</strong> qualité, magasin et production.</li><li><strong>Déclencheur :</strong> avis d’incident relié à la livraison, au lot fournisseur et à sa généalogie 021081 → 773474 → 268967.</li></ul></article>
    <article class="action-card next"><span class="action-status">PILOTABLE — À AJOUTER AU MOTEUR</span><h3>Qualité — prioriser et paralléliser les analyses autorisées</h3><ul><li><strong>Commande :</strong> priorité du dossier, heures de laboratoire mobilisées, nombre d’essais parallèles et laboratoire de secours déjà qualifié.</li><li><strong>Responsable :</strong> responsable qualité et laboratoire.</li><li><strong>Mesure :</strong> date de décision obtenue, charge laboratoire et coût ; aucune date favorable n’est garantie à l’avance.</li></ul></article>
    <article class="action-card next"><span class="action-status">PILOTABLE — À AJOUTER AU MOTEUR</span><h3>Stocks — transférer ou réaffecter une quantité conforme existante</h3><ul><li><strong>Commande :</strong> lot conforme, site ou ordre source, site ou ordre destinataire, quantité et date d’expédition.</li><li><strong>Responsable :</strong> planification, qualité et logistique.</li><li><strong>Condition :</strong> le stock doit être physiquement présent, libéré et non déjà engagé sur une priorité supérieure.</li></ul></article>
    <article class="action-card next"><span class="action-status">PILOTABLE — À AJOUTER AU MOTEUR</span><h3>Planification — affecter la matière aux lots et commandes prioritaires</h3><ul><li><strong>Commande :</strong> liste ordonnée des ordres de fabrication et commandes clients, quantité attribuée et date promise.</li><li><strong>Responsable :</strong> planificateur, production et service clients.</li><li><strong>Mesure :</strong> lots servis, clients protégés, retard déplacé et chiffre d’affaires préservé ; le manque n’est pas masqué.</li></ul></article>
  </div>
  <p class="definition"><strong>Ce qui reste conditionnel ou n’est pas une commande pilotable :</strong></p>
  <div class="not-actions" aria-label="Résultats ou options non directement pilotables">
    <div class="not-action"><strong>Libération en 15, 30 ou 60 jours</strong>C’est un résultat espéré, pas une action que l’on peut imposer.</div>
    <div class="not-action"><strong>Dérogation ou libération partielle</strong>Possible uniquement après preuve de conformité et autorisation qualité ; jamais garantie au déclenchement.</div>
    <div class="not-action"><strong>Nouveau fournisseur ou nouvelle capacité</strong>Non pilotable pendant la crise sans source déjà qualifiée, capacité confirmée et engagement contractuel.</div>
    <div class="not-action"><strong>Achat exceptionnel non confirmé</strong>Une commande ne crée ni matière conforme ni capacité disponible.</div>
    <div class="not-action"><strong>Capacité M-1810</strong>Aucun gain simulé dans les niveaux testés, même jusqu’à trois fois la capacité.</div>
    <div class="not-action"><strong>Stock lancé au jour de l’alerte</strong>La matière manquante ne peut plus être créée à temps ; aucun gain client simulé.</div>
    <div class="not-action"><strong>Replanification générique</strong>Le réglage testé multiplie le retard 338929 par 4,32 ; il ne représente pas encore un planning réaliste tenant compte des capacités.</div>
  </div>
  <p class="definition"><strong>Portée des chiffres :</strong> ces courbes sont des essais du modèle, une modification à la fois, et non des mesures historiques chez vos fournisseurs. Elles servent à choisir les actions à approfondir, pas à annoncer un ROI ou une probabilité d’incident.</p>
</section>
"""


def transform_decision_view(document: str) -> str:
    """Turn the existing result page into the third, decision-oriented view."""
    if "</head>" not in document or "<body>" not in document or "<main>" not in document:
        raise ValueError("Decision document is missing a required marker")
    document = _swap_hero_cards(document)
    document = _swap_summary_rows(document)
    document = _swap_incident_sections(document)

    replacements = {
        "Anticiper la propagation d’un risque fournisseur — synthèse": "Vue 3/3 — sensibilité et plan d’action",
        "PRÉVISION CONDITIONNELLE DES RISQUES FOURNISSEURS": "SENSIBILITÉ ET ACTIONS SUR LES RISQUES FOURNISSEURS",
        "Si un fournisseur se dégrade, quand la production et le client seront-ils touchés ?": "Qu’est-ce qui fragilise la chaîne, et sur quel levier faut-il agir ?",
        "La démonstration calcule la propagation d’un risque fournisseur imposé vers les stocks, les lots, la production et les clients. Elle ne prédit pas encore la probabilité d’apparition de l’incident.": "Nous utilisons la sensibilité pour localiser le goulot, puis nous rejouons chaque action depuis les mêmes situations de départ pour vérifier si elle réduit réellement l’impact sur les lots et les clients.",
        '<strong>2/10</strong><span>propagations jusqu’au client si le retard simulé de 338929 survient</span>': '<strong>542</strong><span>essais de sensibilité pour identifier les facteurs qui fragilisent le réseau</span>',
        '<strong>9/10</strong><span>propagations jusqu’au client si la retenue qualité simulée survient</span>': '<strong>180</strong><span>comparaisons rejouées depuis les mêmes dix situations de départ</span>',
        '<strong>75–90 jours</strong><span>entre le premier effet moyen sur le stock et le premier retard client, selon le stress test</span>': '<strong>6 actions</strong><span>dont une déjà simulée, une préventive et quatre pilotables à ajouter au moteur</span>',
        "Prévision fournisseur": "Cadre de preuve",
        "Stress test qualité": "Retenue qualité",
        "Stress test 338929": "Retard 338929",
        "Ce que nous savons prévoir aujourd’hui — et la prochaine brique à calibrer": "Ce que nous savons simuler aujourd’hui — et ce qu’il reste à calibrer",
        "Risque fournisseur à 30 / 60 / 90 jours": "Probabilité d’incident à 30 / 60 / 90 jours : non disponible",
        "produire une probabilité exploitable": "produire une probabilité industrielle calibrée",
        "Couche démontrée ici.": "Résultat simulé disponible.",
        "Prévision conditionnelle :": "Résultat simulé sous l’hypothèse d’incident :",
        "Réponse recommandée dans ce test": "Meilleure option parmi celles simulées",
        "retard observé ramené à zéro": "retard client simulé ramené à zéro",
        "retard client observé est ramené à zéro": "retard client simulé est ramené à zéro",
        "Plus cher, sans gain supplémentaire observé": "Plus cher, sans gain simulé supplémentaire",
        "selon l’état observé": "selon l’état simulé du jour",
        "Ce proxy simplifié porte": "Ce réglage MRP/MPS simplifié porte",
        "Actions sans régulation": "Actions préprogrammées, sans régulation",
        "selon le stress test": "selon l’étude d’impact simulée",
        "stress tests": "études d’impact simulées",
        "stress test": "étude d’impact simulée",
        "Ils ont été définis": "Elles ont été définies",
        "Ils ne sont ni deux incidents historiques observés": "Elles ne sont ni deux incidents historiques observés",
        '<div class="quality"><strong>Plan préparé dès J0 :</strong> 2,39 M, soit 34,5 % restant</div>': '<div class="quality"><strong>Transport accéléré :</strong> impact moyen réduit de 39,5 %</div>',
        '<article class="decision good"><h3>Scénario préventif le plus protecteur</h3>': '<article class="decision stop"><h3>Protection maximale, mais non recommandée en l’état</h3>',
        '<p class="number">Plan préparé dès J0</p><p>2,39 M unités × jours restent, soit une réduction de 65,5 %. 129,0 jours sont récupérés en moyenne parmi les 9 cas touchés, avec une plage de 15,0 à 225,0 jours.</p>': '<p class="number">Plan combiné — plusieurs approximations</p><p>2,39 M unités × jours restent, soit une réduction de 65,5 %. Ce résultat donne une borne de protection, mais mélange achat amont, stock, priorité et replanification qui ne représentent pas encore des décisions industrielles complètes.</p>',
        '<article class="decision alt"><h3>Réponse plus légère à recalibrer</h3>': '<article class="decision good"><h3>Levier explicitement modélisé, à effet moyen favorable</h3>',
        "C’est le scénario le plus protecteur pour la qualité, mais plusieurs leviers restent approchés.": "Il donne la protection maximale du modèle, mais n’est pas retenu comme recommandation car plusieurs leviers restent approchés.",
        "STRESS TEST D’IMPACT 1": "ÉTUDE 2 — RETENUE QUALITÉ",
        "STRESS TEST D’IMPACT 2": "ÉTUDE 1 — RETARD 338929",
        "Ce que nous proposons de tester avec l’industriel": "Le plan d’action à construire avec vos équipes",
        "1. Construire le signal fournisseur": "1. Surveiller les facteurs qui font bouger le service",
        "Relier OTIF, retards annoncés, qualité, commandes ouvertes, capacité, dépendance article et couverture projetée.": "Pour chaque flux critique, suivre la dérive de la date d’arrivée prévue, la capacité fournisseur engagée, les commandes ouvertes et la couverture projetée. Confirmer en parallèle le transport réellement réservable, le stock conforme transférable, la capacité laboratoire disponible et les ordres que l’on peut explicitement prioriser.",
        "2. Calibrer la prévision 30 / 60 / 90 jours": "2. Mesurer l’effet des actions réelles",
        "Rejouer les incidents réels pour mesurer faux positifs, incidents manqués, avance obtenue et qualité des niveaux de risque.": "Rejouer chaque incident avec des commandes exécutables : expédition et mode de transport nommés ; lots bloqués ; heures de laboratoire ; stock conforme transféré ; ordres de fabrication et commandes clients explicitement prioritaires.",
        "3. Relier chaque alerte à son impact": "3. Déclencher l’action sur les bons lots",
        "Pour chaque fournisseur à risque, calculer automatiquement les lots, productions et clients exposés, puis comparer les réponses possibles.": "Relier l’alerte fournisseur aux commandes et expéditions concernées, puis aux lots, productions et clients exposés ; afficher qui doit agir, avant quelle date, sur quelle quantité et avec quel risque restant.",
        "Proposition de collaboration :</strong> partir d’incidents fournisseurs historiques, calibrer le signal d’alerte, valider la physique des lots et les coûts, puis connecter la prévision à la simulation conditionnelle déjà démontrée ici.": "Résultat attendu avec vos données :</strong> pour chaque fournisseur prioritaire, disposer d’une alerte expliquée, des lots et clients menacés, de deux ou trois actions réellement faisables et de leur effet comparé sur le retard, le service, le coût et le risque restant.",
    }
    for before, after in replacements.items():
        document = document.replace(before, after)

    document = re.sub(
        r"<title>.*?</title>",
        "<title>Vue 3/3 — sensibilité et plan d’action</title>",
        document,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    document = re.sub(
        r"<nav>.*?</nav>",
        '<nav><a href="#leviers">Sensibilité et leviers</a><a href="#retard">Retard 338929</a><a href="#qualite">Retenue qualité</a><a href="#recommandations">Plan d’action</a><a href="#limites">Limites</a></nav>',
        document,
        count=1,
        flags=re.DOTALL,
    )
    document = document.replace(
        '<article class="chart-card">',
        '<article class="chart-card"><span class="simChartNote">SIMULÉ — moyenne de 10 répétitions · moyenne glissante causale</span>',
    )
    document = document.replace("</head>", DECISION_STYLE + "</head>", 1)
    document = document.replace("<body>", "<body>" + _decision_guide(), 1)
    document = document.replace(
        "<main>", "<main>" + _evidence_board() + _decision_sensitivity_action_board(), 1
    )
    return document


def build_meeting_package(source_dir: Path, output_dir: Path) -> dict[str, object]:
    """Create a new three-view package without changing ``source_dir``."""
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    views_dir = source_dir / "views"
    if not source_dir.is_dir() or not views_dir.is_dir():
        raise FileNotFoundError(f"Portable source package not found: {source_dir}")
    required = [views_dir / name for name in SOURCE_VIEWS.values()]
    required.extend((views_dir / PLOTLY_FILE, views_dir / TOPOLOGY_FILE))
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing source file: {missing[0]}")
    if output_dir.exists():
        raise FileExistsError(f"Output package already exists: {output_dir}")
    if source_dir == output_dir or source_dir in output_dir.parents:
        raise ValueError("Output package must be outside the immutable source package")

    output_views = output_dir / "views"
    output_views.mkdir(parents=True)
    (output_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    delay_document = (views_dir / SOURCE_VIEWS["delay"]).read_text(encoding="utf-8")
    quality_document = (views_dir / SOURCE_VIEWS["quality"]).read_text(encoding="utf-8")
    decision_document = (views_dir / SOURCE_VIEWS["decisions"]).read_text(encoding="utf-8")
    (output_views / OUTPUT_VIEWS["delay"]).write_text(
        transform_map_view(delay_document, MAP_PRESENTATIONS["delay"]), encoding="utf-8"
    )
    (output_views / OUTPUT_VIEWS["quality"]).write_text(
        transform_map_view(quality_document, MAP_PRESENTATIONS["quality"]), encoding="utf-8"
    )
    (output_views / OUTPUT_VIEWS["decisions"]).write_text(
        transform_decision_view(decision_document), encoding="utf-8"
    )
    shutil.copy2(views_dir / PLOTLY_FILE, output_views / PLOTLY_FILE)
    shutil.copy2(views_dir / TOPOLOGY_FILE, output_views / TOPOLOGY_FILE)

    return {
        "source_package": str(source_dir),
        "output_package": str(output_dir),
        "view_count": 3,
        "view_paths": [f"views/{OUTPUT_VIEWS[key]}" for key in ("delay", "quality", "decisions")],
        "output_bytes": sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_meeting_package(args.source_dir, args.output_dir)
    print(f"[OK] Three-view package: {result['output_package']}")
    print(f"[OK] Views: {result['view_count']}")
    print(f"[OK] Bytes: {result['output_bytes']}")


if __name__ == "__main__":
    main()
