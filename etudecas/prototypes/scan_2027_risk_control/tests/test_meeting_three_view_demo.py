from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.meeting_three_view_demo import (
    MAP_PRESENTATIONS,
    build_meeting_package,
    transform_decision_view,
    transform_map_view,
)


def _map_document(title: str = "Carte") -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title></head>
<body><div class="toolbar"><button id="modeOps">Ops</button><button id="modeSimulatedRisk">Risque</button>
<select id="simulatedRiskCascadeSelect"><option value="">Toutes</option></select>
<select id="lotTraceSelect"><option value="">Aucun</option></select><button id="lotTraceOpenBtn">Lots</button></div>
<div id="chart"></div><p>Impact observé — Criticité fournisseurs</p></body></html>"""


def _decision_document() -> str:
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Anticiper la propagation d’un risque fournisseur — synthèse</title></head><body>
<header class="hero" id="synthese"><div class="kicker">PRÉVISION CONDITIONNELLE DES RISQUES FOURNISSEURS</div>
<p>La démonstration calcule la propagation d’un risque fournisseur imposé vers les stocks, les lots, la production et les clients. Elle ne prédit pas encore la probabilité d’apparition de l’incident.</p>
<div class="hero-grid"><div class="hero-card"><strong>9/10</strong><span>propagations jusqu’au client si la retenue qualité simulée survient</span></div><div class="hero-card"><strong>2/10</strong><span>propagations jusqu’au client si le retard simulé de 338929 survient</span></div><div class="hero-card"><strong>75–90 jours</strong><span>entre le premier effet moyen sur le stock et le premier retard client, selon le stress test</span></div></div></header>
<nav><a href="#synthese">Prévision fournisseur</a><a href="#qualite">Stress test qualité</a><a href="#retard">Stress test 338929</a></nav>
<main><section><h2>Ce que nous savons prévoir aujourd’hui — et la prochaine brique à calibrer</h2>
<div>75 jours selon le stress test</div>
<div class="summary-table"><div class="head">Cas</div><div class="head">Impact</div><div class="head">Action</div>
<div class="quality">Qualité</div><div class="quality">Q impact</div><div class="quality">Q action</div>
<div class="delay">338929</div><div class="delay">D impact</div><div class="delay">retard observé ramené à zéro</div></div>
<p class="definition">Pourquoi ces deux stress tests ? Ils ont été définis à l’avance.</p></section>
<section id="qualite"><div class="eyebrow">STRESS TEST D’IMPACT 1</div><p>Prévision conditionnelle :</p><article class="chart-card">Q chart</article></section>
<section id="retard"><div class="eyebrow">STRESS TEST D’IMPACT 2</div><p>Prévision conditionnelle :</p><article class="chart-card">D chart</article></section>
<section id="recommandations"><h2>Ce que nous proposons de tester avec l’industriel</h2>
<h3>1. Construire le signal fournisseur</h3><p>Relier OTIF, retards annoncés, qualité, commandes ouvertes, capacité, dépendance article et couverture projetée.</p>
<h3>2. Calibrer la prévision 30 / 60 / 90 jours</h3><p>Rejouer les incidents réels pour mesurer faux positifs, incidents manqués, avance obtenue et qualité des niveaux de risque.</p>
<h3>3. Relier chaque alerte à son impact</h3><p>Pour chaque fournisseur à risque, calculer automatiquement les lots, productions et clients exposés, puis comparer les réponses possibles.</p>
<p><strong>Proposition de collaboration :</strong> partir d’incidents fournisseurs historiques, calibrer le signal d’alerte, valider la physique des lots et les coûts, puis connecter la prévision à la simulation conditionnelle déjà démontrée ici.</p></section><section id="limites">Actions sans régulation</section></main>
</body></html>"""


def test_map_view_adds_three_step_route_and_canonical_vocabulary() -> None:
    transformed = transform_map_view(_map_document(), MAP_PRESENTATIONS["delay"])

    assert transformed.count('class="active" aria-current="page"') == 1
    assert transformed.count("01_retard_338929.html") == 1
    assert transformed.count("02_retenue_qualite.html") == 2  # route + hidden next link
    assert transformed.count("03_decisions.html") == 1
    assert "OBSERVÉ" in transformed
    assert "SIMULÉ" in transformed
    assert "SIGNAL DE PRIORITÉ" in transformed
    assert "HYPOTHÈSE" in transformed
    assert "SDC-VD0914360C|338929|M-1810|268091|service_client" in transformed
    assert "LOT-00003637" in transformed
    assert 'id="meetingPresentationRuntime"' in transformed


def test_decision_view_starts_with_338929_and_labels_results_as_simulated() -> None:
    transformed = transform_decision_view(_decision_document())

    assert transformed.index("<strong>542</strong>") < transformed.index("<strong>180</strong>")
    assert "<strong>6 actions</strong>" in transformed
    assert transformed.index('<section id="retard">') < transformed.index('<section id="qualite">')
    assert transformed.index("338929</div>") < transformed.index("Qualité</div>")
    assert "Ce que nous savons simuler aujourd’hui" in transformed
    assert "Résultat simulé sous l’hypothèse d’incident" in transformed
    assert "retard client simulé ramené à zéro" in transformed
    assert "selon l’étude d’impact simulée" in transformed
    assert "Elles ont été définies" in transformed
    assert "selon le étude" not in transformed
    assert "Ils ont été définis" not in transformed
    assert "simulations touchées dans les deux cas touchés" not in transformed
    assert transformed.count("SIMULÉ — moyenne de 10 répétitions · moyenne glissante causale") == 2
    assert "CE QUE VOUS NOUS AVEZ FOURNI — OBSERVÉ" in transformed
    assert "OÙ REGARDER D’ABORD — SIGNAL DE PRIORITÉ" in transformed
    assert 'id="leviers"' in transformed
    assert transformed.count('class="mini-curve"') == 4
    assert transformed.count('class="action-card') == 6
    assert transformed.count('class="not-action"') == 7
    assert "DÉJÀ SIMULÉ — SOUS CONDITIONS" in transformed
    assert "PRÉVENTIF — PILOTABLE" in transformed
    assert transformed.count("PILOTABLE — À AJOUTER AU MOTEUR") == 4
    assert transformed.count("<strong>Commande :</strong>") == 6
    assert transformed.count("<strong>Responsable :</strong>") == 6
    assert "bloquer seulement les lots réellement concernés" in transformed
    assert "prioriser et paralléliser les analyses autorisées" in transformed
    assert "transférer ou réaffecter une quantité conforme existante" in transformed
    assert "affecter la matière aux lots et commandes prioritaires" in transformed
    assert "Multiplier la capacité de production de M-1810" in transformed
    assert "Le plan d’action à construire avec vos équipes" in transformed
    assert "Surveiller les facteurs qui font bouger le service" in transformed
    assert "expédition et mode de transport nommés" in transformed
    assert "Déclencher l’action sur les bons lots" in transformed
    assert "Résultat attendu avec vos données" in transformed
    assert "proposition de pilote" not in transformed.lower()
    assert "simulations appariées" not in transformed
    assert "TESTÉ ET EFFICACE" not in transformed
    assert "Aucun gain mesuré" not in transformed
    assert "constituer le stock tampon avant la période de risque" in transformed
    assert "commandes ou ASN" not in transformed
    assert "renseigner ETA" not in transformed
    assert " MOQ" not in transformed
    assert "avec COA" not in transformed
    assert "raccourcir la décision de libération qualité" not in transformed
    assert "réserver une capacité amont qualifiée" not in transformed
    assert "libération qualité en 90, 60, 30 ou 15 jours" not in transformed


def test_package_builder_is_additive_and_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source_views = source / "views"
    source_views.mkdir(parents=True)
    delay = _map_document("Retard")
    quality = _map_document("Qualité")
    decision = _decision_document()
    (source_views / "carte_retard_338929_incident_lots.html").write_text(delay, encoding="utf-8")
    (source_views / "carte_qualite_incident_lots.html").write_text(quality, encoding="utf-8")
    (source_views / "stress_tests_incidents_lots.html").write_text(decision, encoding="utf-8")
    (source_views / "plotly-2.32.0.min.js").write_text("window.Plotly={};", encoding="utf-8")
    (source_views / "world_110m.json").write_text("{}", encoding="utf-8")

    output = tmp_path / "meeting"
    result = build_meeting_package(source, output)

    assert result["view_count"] == 3
    assert sorted(path.name for path in (output / "views").glob("*.html")) == [
        "01_retard_338929.html",
        "02_retenue_qualite.html",
        "03_decisions.html",
    ]
    assert (source_views / "carte_retard_338929_incident_lots.html").read_text(encoding="utf-8") == delay
    assert (source_views / "carte_qualite_incident_lots.html").read_text(encoding="utf-8") == quality
    assert (source_views / "stress_tests_incidents_lots.html").read_text(encoding="utf-8") == decision
    with pytest.raises(FileExistsError):
        build_meeting_package(source, output)
