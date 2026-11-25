import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

// Build from the repository root with the bundled Node and Python runtimes.
const repo = process.env.IC_REPO || process.cwd();
const runtimeModules = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
const runtimePython = process.env.CODEX_PRIMARY_RUNTIME_PYTHON;
if (!runtimeModules || !runtimePython) throw new Error('Codex primary runtime paths are required');
process.env.RUNTIME_NODE_MODULES = runtimeModules;
process.env.RUNTIME_PYTHON = runtimePython;
const requireRuntime = createRequire(path.join(runtimeModules, '__artifact_loader__.cjs'));
const {Presentation, PresentationFile, FileBlob} = await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')).href);
const skillDir = '/home/agent/.codex/skills/builtins/presentations';
const {finalizePresentation, applyPresentationChartFont} = await import(pathToFileURL(path.join(skillDir, 'container_tools/artifact_tool_utils.mjs')).href);
const workspaceDir = path.resolve(repo, '..');
const qa = process.env.IC_PPT_QA || path.join(workspaceDir, 'qa-ppt', new Date().toISOString().replace(/[:.]/g, '-'));
const outputDir = path.join(repo, 'ICs/Livrables-2026-11-25/PowerPoint');
const noLine = {style:'solid', fill:'none', width:0};

function label(slide, name, value, left, top, width, height, size, options = {}) {
  const shape = slide.shapes.add({geometry:'textbox', name, position:{left, top, width, height}, fill:'none', line:noLine});
  shape.text = value.replace(/ ([?!])/g, '\u00A0$1');
  shape.text.style = {
    typeface:slide.design.font, fontSize:size + 'pt', bold:options.bold || false,
    color:options.color || slide.design.ink, wrap:'square', autoFit:'none', insets:0,
    verticalAlignment:'top', alignment:options.align || 'left'
  };
  return shape;
}

function page(deck, title, notes, titleSize = 34) {
  const slide = deck.pres.slides.add();
  slide.design = deck;
  slide.background.fill = '#FFFFFF';
  label(slide, 'titre', title, 64, 45, 1150, 98, titleSize, {bold:true, color:deck.accent});
  slide.speakerNotes.text = notes.trim();
  return slide;
}

function table(slide, name, rows, widths, left, top, height, size = 18, numericCols = []) {
  const width = widths.reduce((sum, n) => sum + n, 0);
  const obj = slide.tables.add({rows:rows.length, columns:widths.length, left, top, width, height, columnWidths:widths, values:rows});
  obj.name = name;
  obj.borders.assign({style:'solid', fill:slide.design.rule, width:1});
  obj.styleOptions = {headerRow:true, bandedRows:false};
  for (let r = 0; r < rows.length; r++) {
    for (let c = 0; c < widths.length; c++) {
      const cell = obj.getCell(r, c);
      cell.fill = r === 0 ? slide.design.tint : '#FFFFFF';
      cell.text.style = {
        typeface:slide.design.font, fontSize:size + 'pt', bold:r === 0,
        color:r === 0 ? slide.design.accent : slide.design.ink, alignment:numericCols.includes(c) ? 'center' : 'left',
        verticalAlignment:'middle', insets:{top:7, right:10, bottom:7, left:10}, wrap:'square', autoFit:'none'
      };
    }
  }
  slide.design.tableOwners.push(slide.design.pres.slides.items.length);
}

function caption(slide, value, x, y, width) {
  label(slide, 'legende', value, x, y, width, 56, 14, {color:slide.design.muted});
}

function issue(slide, name, text, x, y, w) {
  label(slide, name, text, x, y, w, 54, 21, {bold:true, color:slide.design.accent});
}

function intro(slide, text) {
  label(slide, 'origine', text, 64, 133, 1140, 48, 16, {color:slide.design.muted});
}

// These are presentation notes, including the scope of the historical evidence
// and the professional sources that informed the original decision reviews.
const ref = {
  sample: 'Statistique Canada, Échantillonnage probabiliste, 2 septembre 2021. https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/prob/5214899-eng.htm',
  exposure: 'Simchi-Levi et al., volume 45 de Interfaces (2015), p. 375–390. Conséquences opérationnelles d’une rupture dans la chaîne automobile. https://doi.org/10.1287/inte.2015.0804',
  order: 'Microsoft, Default order settings, 10 juillet 2025. https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/default-order-settings',
  quality: 'Microsoft, Quality orders, 26 octobre 2026. https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-orders',
  dual: 'Akkerman et al., Solving Dual Sourcing Problems with Supply Mode Dependent Failure Rates, version du 11 avril 2025. Les taux de défaillance en service étudiés par les auteurs ont un autre périmètre que le rendement à réception. https://arxiv.org/html/2410.03887v2',
  audit: 'ISO 19011:2026, 4e édition, mai 2026. Lignes directrices pour l’audit des systèmes de management. https://www.iso.org/standard/19011',
  sensitivity: 'Commission européenne, JRC, Step 8. Sensitivity analysis, décembre 2020. https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-8-sensitivity-analysis_en',
  release: 'Oracle, Promise Only After You Release Holds On Lots, documentation 26A. https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fascp/promise-only-after-you-release-holds-on-lots.html',
  net: 'Microsoft, Net requirements and pegging information, 21 juillet 2025. https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/net-requirements',
  promise: 'Microsoft, Calculate order promising dates, 16 novembre 2026. https://learn.microsoft.com/en-us/dynamics365/business-central/sales-how-to-calculate-order-promising-dates',
  service: 'Ivanov, When is the supply chain resilient? Customer and operational perspectives, 2025. Trois réseaux simulés et plusieurs mesures de service. https://doi.org/10.1080/00207543.2025.2454331',
  priority: 'Microsoft, Priority-based planning, 17 juin 2025. Ce texte traite de la priorité au réapprovisionnement. Les deux ordres clients relèvent d’un autre arbitrage. https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/priority-based-planning',
  milestone: 'IATA Cargo iQ, Master Operating Plan, documentation de juillet 2025. https://iata-cargo.github.io/ONE-Record/2025-07/Orchestration/orchestration-mop/',
  record: 'IATA ONE Record, note de version du 25 juillet 2026. https://iata-cargo.github.io/ONE-Record/development/General/release-note/',
  dock: 'Microsoft, Set up an appointment for a load, 17 février 2025. https://learn.microsoft.com/en-us/dynamics365/supply-chain/transportation/tasks/set-up-appointment-load',
  port: 'Huang et al., PLOS ONE, 21 février 2025. Le gain de 4,89 % sur leur planning manuel concerne un cas portuaire simulé. https://doi.org/10.1371/journal.pone.0318606',
  glec: 'Smart Freight Centre, GLEC Framework v3.3, octobre 2026. https://smartfreightcentre.org/news/13311209/',
  crosswalk: 'Smart Freight Centre, Crosswalk, édition 4, 26 octobre 2026. https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311209/3b754d52417445123e4d321e33d4a3ab.pdf',
  logistics: 'Kallionpää et al., Development of logistics emissions reporting, numéro de janvier 2026. Les 17 entretiens portent sur les pratiques de déclaration. https://doi.org/10.1016/j.trd.2025.105083',
  blocking: 'Microsoft, Inventory blocking, 14 août 2025. https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-blocking',
  epcis: 'GS1 EPCIS 2.0, juin 2022. État métier et instant de l’événement. https://ref.gs1.org/standards/epcis/',
  iso9001: 'ISO 9001:2026. Le communiqué du 16 septembre 2026 annonce la nouvelle édition. https://www.iso.org/news/2026/09/ISO9001-2026',
  ghg: 'GHG Protocol, Product Life Cycle Accounting and Reporting Standard, 2011. https://ghgprotocol.org/sites/default/files/standards/Product-Life-Cycle-Accounting-Reporting-Standard_041613.pdf',
  repair: 'Järnefelt, Ashouri et Behm, Does repair improve environmental performance?, 2026. L’effet dépend du composant, de la date de panne et de la catégorie d’impact. https://doi.org/10.1016/j.jclepro.2026.149164',
  ef: 'Commission européenne, recommandation sur les méthodes d’empreinte environnementale, 16 décembre 2021. https://environment.ec.europa.eu/publications/recommendation-use-environmental-footprint-methods_en',
  ef31: 'JRC, méthode EF 3.1, rapport du 8 février 2023. https://op.europa.eu/en/publication-detail/-/publication/145f8401-a82a-11ed-b508-01aa75ed71a1',
  efUpdate: 'JRC, Environmental Footprint transition phase, actualisation du 4 novembre 2026. https://knowledge-for-policy.ec.europa.eu/environmental-footprint-transition-phase_en',
  risk: 'HM Treasury, Orange Book, actualisation du 18 novembre 2026. Dépendances entre risques. https://www.gov.uk/government/publications/orange-book/the-orange-book-management-of-risk-principles-and-concepts',
  appraisal: 'HM Treasury, Green Book 2026, actualisation du 28 octobre 2026. Valeurs de bascule dans l’évaluation publique. https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026',
  finance: 'ACCA, Relevant costs, sans date affichée. Coûts futurs modifiés par la décision et coûts d’opportunité. https://www.accaglobal.com/uk/en/student/exam-support-resources/fundamentals-exams-study-resources/f5/technical-articles/relevant-costs.html',
  cash: 'Ivanov, Cash flow dynamics in the supply chain during and after disruptions, mai 2024. Étude des flux après perturbation. Le plafond d’urgence ne fait pas partie du chiffrage. https://doi.org/10.1016/j.tre.2024.103526',
  routing: 'Müllerklein et Fontaine, Resilient transportation network design with disruption uncertainty and lead times, 2025. Les capacités et le délai conditionnent le gain de réacheminement. https://doi.org/10.1016/j.ejor.2024.11.021'
};

function notes(text, ...references) {
  return [text, '', ...references].join('\n');
}

function achats(d) {
  let s = page(d, 'Quels fournisseurs retenir pour les cinq places ?', notes(
    'Cas public de sélection, 29 fournisseurs dont 27 testés. Treize fournisseurs sont mono-source, avec cinq baisses de service, et quatorze ont une autre configuration, avec une baisse. Les deux résultats manquants restent inconnus. Le tirage s’effectue sans remise dans chaque groupe. Pour le plan quatre plus un, 910 listes sur 10 010 manquent les six cas. Les probabilités concernent le tirage, sans estimer une fréquence de panne. La sélection des cinq délais les plus longs manque les six cas.',
    ref.sample, ref.exposure));
  intro(s, 'Dossier préparé pour les achats le 25 novembre 2026 à partir des cas simulés.');
  table(s, 'Plans de revue', [
    ['Composition de la liste', 'Listes sans baisse détectée', 'Baisses détectées en moyenne'],
    ['Cinq tirés au hasard', '25,21 %', '1,11'],
    ['Quatre mono-source et un autre', '9,09 %', '1,61'],
    ['Cinq mono-source', '4,35 %', '1,92']
  ], [340,227,235], 64, 224, 256, 17, [1,2]);
  caption(s, 'Cas fournisseurs. Une revue de 5 dossiers tirés parmi 27, dont 6 avec baisse du service.', 64, 498, 802);
  issue(s, 'choix', 'Décision de l’acheteur', 904, 231, 311);
  label(s, 'consigne', 'Réserver une place aux autres fournisseurs si la revue doit couvrir les deux groupes. Un des six cas de baisse se trouve dans ce groupe.', 904, 305, 310, 250, 20);
  label(s, 'action', 'Avant la réunion, vérifier que la seconde source annoncée peut fabriquer la référence et livrer à temps.', 64, 598, 1150, 95, 21, {bold:true});

  s = page(d, 'La commande de dépannage passe à 900 kg', notes(
    'Cas central de double approvisionnement. Les quantités de 800 et 900 kg et le résultat de 46 configurations sur 60 sont rapportés. La différence est de 100 kg et la fraction des configurations sans rupture vaut 76,67 %. La distribution des paramètres et le calendrier complet ne sont pas fournis.',
    ref.order, ref.quality, ref.dual));
  label(s, 'ecart', '+100 kg', 64, 175, 560, 112, 61, {bold:true,color:d.accent});
  label(s, 'sens', 'de dépannage quand seule une partie du premier arrivage peut servir à l’échéance.', 69, 301, 537, 162, 24);
  issue(s, 'temoin', 'Commande du cas central', 655, 185, 550);
  label(s, 'besoin', '800 kg à couvrir avant de tenir compte de la contrainte de réception.', 655, 248, 550, 104, 22);
  issue(s, 'variante', 'Après contrôle à réception', 655, 364, 550);
  label(s, 'livraison', '900 kg à couvrir si 90 % de la première livraison sont utilisables à la date du besoin.', 655, 428, 548, 140, 22);
  caption(s, 'Exercice de double approvisionnement, au jour du besoin. Sur les 60 configurations simulées, 46 évitent la rupture.', 64, 552, 1150);
  label(s, 'action', 'Avant de commander, rapprocher la date de libération du lot, le minimum de commande et la capacité de réception.', 64, 610, 1150, 86, 20, {bold:true});

  s = page(d, 'Quels justificatifs demander avant les trois visites ?', notes(
    'Le test rend successivement chacune des 84 cotations incertaine. Seize peuvent modifier la liste. Les 68 restantes ne la modifient pas dans ces essais isolés. Parts recalculées de 19,05 % et 80,95 %. Les poids et bornes individuels manquent. La stabilité sous plusieurs valeurs incertaines à la fois reste à vérifier.',
    ref.audit, ref.sensitivity));
  label(s, 'chiffre', '16 sur 84', 68, 160, 530, 107, 58, {bold:true,color:d.accent});
  label(s, 'lien', 'cotations peuvent faire entrer ou sortir un dossier du programme de visites.', 68, 287, 490, 180, 23);
  issue(s, 'conduite', 'Au moment de demander une preuve', 620, 176, 584);
  label(s, 'question', 'Pour la cotation en suspens, quelles sont les deux valeurs encore défendables ?', 620, 252, 558, 114, 22);
  label(s, 'decision', 'Reclasser les dossiers avec chaque valeur, en gardant les ex æquo. Demander le justificatif en priorité si la liste de visites change.', 620, 397, 562, 174, 21, {bold:true});
  caption(s, 'Exercice de programmation d’audit. Trois visites, une cotation inconnue par essai. Les incertitudes simultanées restent à tester.', 68, 597, 1130);
}

function planification(d) {
  let s = page(d, 'Que peut-on promettre au dépôt ?', notes(
    'L’exercice de couverture indique quatre jours complets au dépôt et cinq jours en ajoutant le stock amont. L’état du stock et le temps de transfert conditionnent sa date de disponibilité. Les flux journaliers permettant de reconstituer le solde ne sont pas publics.',
    ref.release, ref.net));
  intro(s, 'Étude du 25 novembre 2026 pour la planification. Trois exercices simulés.');
  label(s, 'solde', '4 jours', 65, 218, 490, 130, 67, {bold:true,color:d.accent});
  label(s, 'physique', 'La quantité déjà utilisable au dépôt couvre quatre jours complets de besoin.', 69, 355, 470, 155, 24);
  issue(s, 'condition', 'Pour promettre le cinquième jour', 604, 231, 610);
  label(s, 'transfert', 'À quelle date le transfert de l’usine sera-t-il disponible au dépôt ? Le stock des deux sites représente cinq jours si le transfert arrive avant le premier manque.', 604, 313, 596, 225, 23);
  caption(s, 'Couverture au départ de l’exercice, en jours complets de besoin au dépôt. Un lot en attente de contrôle entre au solde à sa libération.', 64, 584, 1142);

  s = page(d, 'Neuf livraisons chaque jour ou un volume sur cinq jours ?', notes(
    'Les taux publiés de 90 % et 84 % portent sur les volumes de reprise. L’évaluation du plancher quotidien tient compte de la réserve datée qui s’ajoute aux trajectoires. Les taux ne sont pas recalculés après cette réserve. Six points de volume séparent les trajectoires. Les séries quotidiennes ne sont pas disponibles.',
    ref.promise, ref.service), 32);
  label(s, 'reserve', 'Pour tester la promesse quotidienne, ajouter deux unités de réserve avant J1 puis deux avant J3.', 64, 155, 1150, 93, 22);
  table(s, 'Trajectoires de service', [
    ['Trajectoire', 'Volume repris sur cinq jours', 'Livraisons après mobilisation de la réserve'],
    ['Première', '90 %', 'À J2, il manque encore une unité pour atteindre le plancher.'],
    ['Seconde', '84 %', 'Le plancher de neuf livraisons tient chaque jour.']
  ], [243,300,605], 64, 275, 218, 20, [1]);
  caption(s, 'Exercice de reprise. Les taux portent sur les cinq jours. Les résultats par jour incorporent la réserve disponible à cette date.', 64, 507, 1148);
  label(s, 'engagement', 'Pour un engagement quotidien, retenir la seconde trajectoire. Pour un engagement cumulé, comparer les volumes à l’échéance convenue.', 64, 594, 1150, 100, 21, {bold:true});

  s = page(d, 'Quel client reçoit le lot libéré ?', notes(
    'Exercice d’allocation entre deux commandes. Le témoin présente un retard maximal de 7 jours et 28 unités-jours de retard. L’urgence d’abord donne 4 jours et 32 unités-jours. Les écarts recoupés sont de −3 jours et +4 unités-jours. Les ordres et arrivages d’origine manquent. Les arbitrages supposent toutes les autres clauses identiques.',
    ref.priority));
  label(s, 'clause', 'La clause du client détermine la mesure à regarder avant de changer l’ordre de passage.', 64, 151, 1150, 78, 23);
  issue(s, 'priorite-delai', 'Le contrat plafonne le retard à quatre jours', 65, 252, 530);
  label(s, 'jour', '7 jours puis 4', 65, 355, 520, 83, 36, {bold:true,color:d.accent});
  label(s, 'règle-plafond', 'Servir l’urgence en premier ramène le plus grand retard au plafond.', 65, 466, 505, 152, 23);
  issue(s, 'priorite-penalite', 'Le contrat pénalise chaque unité et chaque jour', 652, 252, 540);
  label(s, 'unite-jour', '28 puis 32 unités-jours', 652, 355, 549, 83, 32, {bold:true,color:d.accent});
  label(s, 'règle-pénalité', 'Garder l’ordre témoin si la pénalité est uniforme et que les autres clauses sont identiques.', 652, 466, 540, 152, 23);
  caption(s, 'Cas de deux commandes pour un lot. Valeur témoin puis valeur avec priorité à l’urgence, sur le même épisode.', 64, 644, 1150);
}

function transport(d) {
  let s = page(d, 'Combien de dossiers faudra-t-il rouvrir ?', notes(
    'Cas des alertes de fret express, quatre trajectoires de 240 mois. Le signal du mois précédent s’applique aux mois 2 à 240. Sur 956 mois-scénarios, 273 ont un service inférieur à 99 % de la masse demandée. Pour les seuils 90, 95 et 99 %, les alertes justifiées sont respectivement 257, 251 et 247, les fausses alertes 622, 616 et 611, les dossiers ouverts 879, 867 et 858. À 95 %, le rappel est de 251/273 = 91,94 % et la précision de 251/867 = 28,95 %. Pour la persistance, ces nombres de dossiers sont de 136, 140 et 276. Les trajectoires partagent des hypothèses. Un comptage d’alertes ne mesure pas l’effet causal d’une relance sur un départ.',
    ref.milestone, ref.record));
  intro(s, 'Support du 25 novembre 2026 pour l’exploitation transport. Cas simulés.');
  const axisText = {typeface:d.font, fontSize:18, fill:d.ink};
  const chart = s.charts.add('bar', {
    position:{left:58, top:230, width:715, height:312}, categories:['90 %', '95 %', '99 %', 'Persistance'],
    series:[{name:'Dossiers ouverts', values:[879,867,858,276], fill:d.accent, line:noLine}],
    barOptions:{direction:'column', grouping:'clustered', gapWidth:85}, hasLegend:false,
    xAxis:{textStyle:axisText}, yAxis:{min:0, max:1000, majorUnit:250, textStyle:axisText, majorGridlines:{style:'solid', fill:'#D7DEE3', width:1}},
    dataLabels:{showValue:true, position:'outEnd', textStyle:{typeface:d.font, fontSize:18, bold:true, fill:d.ink}},
    chartFill:'#FFFFFF', chartLine:noLine, plotAreaLine:noLine
  });
  applyPresentationChartFont(chart, {fontFamily:d.font});
  d.chartOwners.push(1);
  caption(s, 'Dossiers ouverts sur 956 mois-scénarios (mois 2 à 240 de quatre trajectoires). Cas public des alertes de fret.', 64, 559, 700);
  issue(s, 'signal', 'Au seuil de saturation de 95 %', 813, 233, 395);
  label(s, 'comptes', '251 mois dégradés repérés sur 273, pour 616 fausses alertes.', 813, 327, 397, 132, 24, {bold:true});
  label(s, 'sens', 'La persistance déclenche une revue quand le mois précédent était déjà sous l’objectif de service.', 813, 494, 395, 170, 20);

  s = page(d, 'À quel coût une relance devient-elle préférable ?', notes(
    'Coût simplifié = fausses alertes + r × mois dégradés manqués, avec un coût nul des revues justifiées. Les cinq règles sont aucune alerte, persistance et saturation à 90 %, 95 % et 99 %. Mois manqués respectivement 273, 137, 16, 22 et 26. Les bascules de l’enveloppe sont 140 / (273 − 137) = 35/34 et (622 − 140) / (137 − 16) = 482/121. À ces rapports exacts, les deux règles voisines sont à égalité. Les seuils 95 % et 99 % ne minimisent jamais le coût parmi ces cinq options. La bascule 476/115 ≈ 4,14 compare uniquement 95 % et persistance. Une sixième règle théorique, toujours alerter, pourrait faire mieux que la persistance au-delà de 543/137 si toutes les revues justifiées étaient gratuites et la capacité illimitée. Les coûts et la capacité réels restent à mesurer.'));
  label(s, 'modele', 'Combien de fausses alertes coûteraient autant qu’un mois dégradé manqué ?', 64, 153, 1150, 80, 23);
  table(s, 'Règles au coût minimal', [
    ['Rapport de coûts', 'Règle la moins coûteuse parmi les cinq évaluées'],
    ['Sous 1,03 environ', 'Aucune alerte'],
    ['Entre 1,03 et 3,98 environ', 'Relancer après un mois de service insuffisant'],
    ['Au-dessus de 3,98 environ', 'Relancer à partir de 90 % de saturation le mois précédent']
  ], [402,746], 64, 254, 250, 18);
  caption(s, 'Calcul sur les mêmes 956 mois-scénarios. Égalité aux seuils exacts 35/34 et 482/121. Le modèle attribue un coût nul aux revues justifiées.', 64, 521, 1148);
  label(s, 'choix', 'Le seuil de 4,14 ne vaut que pour comparer la saturation à 95 % à la persistance. Pour dimensionner l’équipe, compter aussi le temps de traitement des dossiers justifiés.', 64, 594, 1148, 101, 20, {bold:true});

  s = page(d, 'Deux tournées sur un seul créneau ?', notes(
    'Cas de demande régulière, un départ tous les quatre jours. Chaque tournée transporte 40 unités, pour une capacité de 60. Une tournée laisse 20 unités libres. Deux tournées produisent 80 unités, soit 20 de trop. Les 21 fermetures de créneau donnent zéro regroupement faisable en un chargement. Sans horaires de rotation ni coûts détaillés, le nombre de véhicules et l’ordre des options de repli restent à examiner.',
    ref.dock, ref.port));
  label(s, 'charge-calculée', '40 + 40 = 80 unités', 65, 190, 674, 95, 41, {bold:true,color:d.accent});
  label(s, 'capacité', 'Le véhicule en accepte 60. Le dépassement de 20 unités exclut le regroupement en un seul chargement.', 68, 315, 611, 192, 25);
  issue(s, 'repli', 'Au quai, vérifier les heures', 753, 207, 455);
  label(s, 'options', 'Un départ avancé tient-il sur un créneau libre ? Deux rotations du même véhicule respectent-elles l’heure limite ? Sinon, chiffrer le deuxième véhicule.', 753, 298, 448, 253, 22);
  caption(s, 'Exercice de fermeture de quai, un départ tous les quatre jours. Aucun chargement groupé faisable sur les 21 fermetures testées.', 64, 605, 1130);

  s = page(d, 'Quels justificatifs demander au transporteur ?', notes(
    'Couverture mesurée en tonnes-kilomètres documentées sur le total modélisé. À trois demandes, les parcours complets couvrent 47,6 % et les liaisons 42,0 %. Écart de 5,6 points. À dix demandes, seuls l’ordre et l’écart de 13,6 points sont publiés. Ni la couverture absolue à dix ni la bascule intermédiaire ne sont connues. Les budgets ne sont pas des périodes.',
    ref.glec, ref.crosswalk, ref.logistics));
  issue(s, 'trois', 'Avec trois demandes', 64, 188, 549);
  label(s, 'couverture-trois', '47,6 %', 64, 255, 527, 110, 56, {bold:true,color:d.accent});
  label(s, 'parcours', 'des tonnes-kilomètres sont documentées en demandant des parcours complets, contre 42,0 % en demandant des liaisons.', 67, 397, 510, 170, 22);
  issue(s, 'dix', 'Avec dix demandes', 630, 188, 549);
  label(s, 'couverture-dix', '13,6 points', 630, 255, 575, 110, 52, {bold:true,color:d.accent});
  label(s, 'liaisons', 'd’avance environ pour les liaisons. La couverture absolue à ce budget et le point de bascule intermédiaire restent inconnus.', 634, 397, 563, 170, 22);
  caption(s, 'Exercice de collecte, deux budgets sur le même périmètre de transport. Pour une empreinte de bout en bout, contrôler aussi les tronçons dépourvus de justificatif.', 64, 613, 1145);
}

function qualite(d) {
  let s = page(d, 'Peut-on libérer un jeu pour le montage ?', notes(
    'Exercice d’assemblage, quatre variantes avec bilan séparé sur 163 composants. Dans la variante modérée, un décalage de disponibilité d’un mois laisse 115,12 kg bloqués à la clôture et réduit d’un le nombre de jeux livrés. La nomenclature et les stocks par référence ne sont pas publiés. Les identifiants et la date de libération sont nécessaires pour une décision d’atelier.',
    ref.blocking, ref.epcis, ref.iso9001));
  intro(s, 'Étude du 25 novembre 2026 pour la qualité et la conception, à partir de trois cas simulés.');
  label(s, 'stock', '115,12 kg', 64, 217, 527, 99, 52, {bold:true});
  label(s, 'stock-etat', 'restent bloqués en clôture si la disponibilité recule d’un mois dans la variante modérée.', 67, 340, 525, 173, 22);
  label(s, 'jeu', 'Un jeu livré de moins', 635, 235, 568, 79, 33, {bold:true});
  label(s, 'critère', 'Pour autoriser le lancement, le magasinier vérifie chaque référence, la quantité par jeu et la date de libération au poste concerné.', 637, 340, 562, 190, 23);
  caption(s, 'Bilan de quatre variantes d’assemblage, 163 composants contrôlés séparément. Stock en kg et variation du nombre de jeux livrés sur la période simulée.', 64, 592, 1149);

  s = page(d, 'Trois ou quatre pièces à accepter au recontrôle ?', notes(
    'Seuils rapportés pour un lot de six pièces et un service comparable. Une navette déjà programmée à charge marginale négligeable demande trois acceptations au recontrôle. Une tournée dédiée qui ajoute 12 kg de CO₂e en demande quatre. Les inventaires détaillés de retouche, de rebut et de remplacement ne sont pas disponibles pour recalculer ces seuils. La charge marginale négligeable de cet essai ne constitue pas une règle d’allocation générale.',
    ref.ghg, ref.repair), 30);
  table(s, 'Acceptations au recontrôle', [
    ['Trajet utilisé pour la retouche', 'Seuil pour réduire les émissions'],
    ['Navette déjà prévue, effet de la charge ajoutée négligeable', '3 pièces acceptées sur 6'],
    ['Tournée dédiée, 12 kg de CO₂e supplémentaires', '4 pièces acceptées sur 6']
  ], [628,520], 64, 175, 215, 20);
  caption(s, 'Lot d’essai de six pièces, du départ en retouche au recontrôle. Seuils rapportés pour un même service rendu.', 64, 407, 1148);
  issue(s, 'releve', 'Sur la fiche de retouche', 64, 502, 485);
  label(s, 'consigne', 'Inscrire le trajet réellement mobilisé, le nombre de pièces acceptées et les remplacements à prévoir parmi les pièces refusées.', 64, 563, 1130, 113, 24);

  s = page(d, 'À quel poids le choix de conception change-t-il ?', notes(
    'Deux variantes à masse identique sont comparées sur les étapes de production et de livraison. Huit indicateurs s’améliorent et huit se dégradent. La bascule concerne le poids relatif de l’eutrophisation des eaux douces. Les autres poids sont redistribués proportionnellement. Les vecteurs d’impact et les facteurs de normalisation manquent. Le cahier ne désigne pas la variante gagnante de part et d’autre du seuil. Une masse identique ne démontre pas une fonction ou une durée de vie identiques.',
    ref.ef, ref.ef31, ref.efUpdate));
  label(s, 'périmètre', 'La revue porte sur la production et la livraison de deux variantes de même masse.', 64, 151, 1135, 78, 23);
  issue(s, 'indicateurs', 'Résultats sur seize indicateurs', 65, 260, 527);
  label(s, 'opposition', 'Huit s’améliorent et huit se dégradent. Le nombre d’indicateurs favorables ne suffit pas à départager les variantes.', 65, 332, 508, 195, 23);
  issue(s, 'hypothèse', 'Poids de l’eutrophisation des eaux douces', 631, 260, 569);
  label(s, 'bascule', 'Le classement s’inverse quand son poids dépasse 7,294 % et que les autres poids sont ajustés proportionnellement.', 631, 360, 560, 184, 23);
  label(s, 'choix', 'Si les poids jugés recevables encadrent le seuil, conserver les deux variantes en discussion et expliciter l’impact qui prime.', 64, 570, 1145, 116, 22, {bold:true});
}

function gestion(d) {
  let s = page(d, 'Quelle prime accepter pour plafonner les urgences ?', notes(
    'Cas de 240 jeux, comparaison du coût de l’achat et de la fabrication en interne. Le cahier rapporte des probabilités d’achat plus coûteux allant d’environ 15,0 % à 40,4 % selon le regroupement des urgences. L’écart sur les valeurs arrondies est de 25,4 points. Les probabilités détaillées et les frais évités ne sont pas disponibles. Le cas ne permet pas d’affecter de façon certaine chaque extrême à une loi de dépendance ou à une clause précise. Une prime dépassant les frais évités dans les deux hypothèses alourdit le coût espéré dans les deux cas.',
    ref.risk, ref.appraisal, ref.cash), 31);
  intro(s, 'Étude préparée le 25 novembre 2026 pour le contrôle de gestion. Cas économiques simulés.');
  label(s, 'risque', '15,0 % à 40,4 %', 63, 209, 648, 99, 47, {bold:true,color:d.accent});
  label(s, 'exposition', 'C’est la probabilité estimée que l’achat coûte plus cher que la fabrication en interne, selon la façon de grouper les urgences.', 65, 333, 599, 190, 23);
  issue(s, 'prime', 'Avant de négocier la prime', 729, 222, 479);
  label(s, 'clause', 'À quel niveau le fournisseur remet-il le compteur à zéro ? Appliquer la clause à des urgences indépendantes, puis groupées. Dans chaque cas, comparer les frais évités à la prime.', 729, 313, 470, 246, 22);
  caption(s, 'Comparaison sur 240 jeux simulés. Écart de 25,4 points entre les deux probabilités arrondies. Le montant des frais évités reste à chiffrer sur le contrat.', 64, 604, 1144);

  s = page(d, 'Dans quel incident financer le deuxième levier ?', notes(
    'Deux incidents distincts. Dans le retard d’approvisionnement, accélération et combinaison annulent le même surcroît moyen d’arriéré. Sous retenue qualité, la combinaison évite des unités-jours supplémentaires. Si E est ce gain (positif) et ΔC le surcoût, le seuil sous pénalité linéaire vaut ΔC/E, environ 2,49 unités monétaires simulées par unité-jour dans le second essai. À l’égalité les coûts se compensent. Si E est nul, comparer directement les coûts. Une clause avec plafond, franchise ou pénalité par commande doit être appliquée aux flux avant agrégation. La valeur simulée n’est pas un tarif en euros.',
    ref.finance, ref.routing, ref.appraisal));
  table(s, 'Effet des interventions', [
    ['Incident', 'Effet sur l’arriéré', 'Décision de financement'],
    ['Retard d’approvisionnement', 'Accélération seule et combinaison annulent le même surcroît moyen.', 'Choisir l’accélération seule, moins coûteuse.'],
    ['Retenue qualité', 'La combinaison évite davantage d’unités-jours de retard.', 'Financer le supplément si la valeur du retard évité couvre le surcoût.']
  ], [279,424,445], 64, 171, 250, 18);
  caption(s, 'Deux incidents simulés distincts. Effets rapportés par épisode sur le même indicateur d’arriéré, exprimé en unités-jours.', 64, 438, 1147);
  issue(s, 'seuil', '2,49 unités monétaires simulées par unité-jour', 64, 521, 1148);
  label(s, 'condition', 'Seuil d’équilibre de la retenue qualité avec une pénalité linéaire. Pour décider en euros, appliquer le tarif et les règles de facturation du contrat.', 64, 594, 1140, 90, 20);
}

const decks = [
  {file:'01-Revue-achats.pptx', render:achats, font:'Arial', accent:'#284E40', ink:'#1B2822', muted:'#4A5650', tint:'#E8F0EA', rule:'#BACAC0'},
  {file:'02-Revue-planification.pptx', render:planification, font:'Calibri', accent:'#234B74', ink:'#182C40', muted:'#4A5C6E', tint:'#E5EDF6', rule:'#BAC8D6'},
  {file:'03-Revue-transport.pptx', render:transport, font:'Arial', accent:'#72411D', ink:'#332C27', muted:'#5F5750', tint:'#F4ECE5', rule:'#D5C6B7'},
  {file:'04-Revue-qualite-environnement.pptx', render:qualite, font:'Arial', accent:'#171717', ink:'#202020', muted:'#4F4F4F', tint:'#EEEEEE', rule:'#BDBDBD'},
  {file:'05-Revue-controle-gestion.pptx', render:gestion, font:'Calibri', accent:'#263849', ink:'#20272D', muted:'#4E5962', tint:'#E9EEF1', rule:'#BAC4CA'}
];

await fs.mkdir(path.join(qa, 'receipts'), {recursive:true});
await fs.mkdir(outputDir, {recursive:true});
const receipts = [];
const selected = process.env.IC_PPT_ONLY?.split(',');
for (const deck of decks.filter(d => !selected || selected.includes(d.file))) {
  deck.pres = Presentation.create({slideSize:{width:1280, height:720}});
  deck.tableOwners = [];
  deck.chartOwners = [];
  deck.render(deck);
  const slideCount = deck.pres.slides.items.length;
  const dir = path.join(qa, deck.file.replace('.pptx', ''));
  await fs.mkdir(dir, {recursive:true});
  const candidatePath = path.join(dir, 'candidate.pptx');
  const finalPath = path.join(dir, 'final.pptx');
  const receiptPath = path.join(qa, 'receipts', deck.file + '.validation.json');
  await (await PresentationFile.exportPptx(deck.pres)).save(candidatePath);
  await finalizePresentation({
    workspaceDir, candidatePath, finalPath, pythonExecutable:runtimePython,
    integrityValidatorPath:path.join(skillDir, 'container_tools/inspect_presentation_package_integrity.py'),
    layoutValidatorPath:path.join(skillDir, 'container_tools/inspect_presentation_layout_geometry.py'),
    layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',
      ...deck.tableOwners.flatMap(n => ['--require-native-table-slide',String(n)])],
    explicitTotalSlideCount:slideCount, requiredNativeTableOwnerSlides:deck.tableOwners, requiredNativeChartOwnerSlides:deck.chartOwners,
    materializeLiteralChartWorkbooks:deck.chartOwners.length > 0,
    fontPolicy:{basis:'design', families:[deck.font]}, verifyArtifactToolImport:true, receiptPath
  });
  const finalPresentation = await PresentationFile.importPptx(await FileBlob.load(finalPath));
  for (let i = 0; i < slideCount; i++) {
    const blob = await finalPresentation.export({slide:finalPresentation.slides.getItem(i), format:'png', scale:1});
    await fs.writeFile(path.join(dir, 'slide-' + (i+1) + '.png'), new Uint8Array(await blob.arrayBuffer()));
  }
  await fs.copyFile(finalPath, path.join(outputDir, deck.file));
  receipts.push({file:deck.file, slides:slideCount, tables:deck.tableOwners, charts:deck.chartOwners, receiptPath, renderDir:dir});
  console.log(deck.file + ' (' + slideCount + ' slides)');
}
await fs.writeFile(path.join(qa,'index.json'), JSON.stringify(receipts,null,2) + '\n');
console.log('QA_INDEX=' + path.join(qa,'index.json'));
