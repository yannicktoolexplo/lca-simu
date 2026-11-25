import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

// Run with the Codex bundled Node runtime from the repository root.
const repo = process.env.IC_REPO || process.cwd();
const runtimeModules = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
const runtimePython = process.env.CODEX_PRIMARY_RUNTIME_PYTHON;
if (!runtimeModules || !runtimePython) throw new Error('Codex primary runtime paths are required');
process.env.RUNTIME_NODE_MODULES = runtimeModules;
process.env.RUNTIME_PYTHON = runtimePython;
const runtimeRequire = createRequire(path.join(runtimeModules, '__artifact_loader__.cjs'));
const {Presentation, PresentationFile, FileBlob} = await import(pathToFileURL(runtimeRequire.resolve('@oai/artifact-tool')).href);
const skill = '/home/agent/.codex/skills/builtins/presentations';
const {finalizePresentation, resolvePresentationFont} = await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const font = resolvePresentationFont({fontFamily:'Liberation Sans'});
const workspaceDir = path.resolve(repo,'..');
const qa = process.env.IC_PPT_QA || path.join(workspaceDir,'qa-ppt',new Date().toISOString().replace(/[:.]/g,'-'));
const outputDir = path.join(repo,'ICs/Livrables-2026-11-25/PowerPoint');
await fs.mkdir(qa,{recursive:true});
await fs.mkdir(path.join(qa,'receipts'),{recursive:true});
await fs.mkdir(outputDir,{recursive:true});
const github = 'https://github.com/yannicktoolexplo/lca-simu/blob/main/docs/provenance-revisions.md?fichier=ICs/#rev-0415';
const cahier = github+'Cahiers-metier.md';
const consult = 'Sources consultées le 25 novembre 2026. Les résultats du cahier proviennent de simulations agrégées. Étude et compléments de calcul réalisés le 25 novembre 2026 pour la supervision, sans attribution individuelle.';
const C = {navy:'#193A58',blue:'#245A80',text:'#253342',gray:'#536474',line:'#CDD6DE',head:'#E9EFF4',alt:'#F6F8FA'};

function text(slide,name,value,x,y,w,h,size=20,bold=false,color=C.text){
  const s=slide.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{style:'solid',fill:'none',width:0}});
  s.text=value;
  s.text.style={typeface:font,fontSize:`${size}pt`,bold,color,wrap:'square',autoFit:'none',insets:0,verticalAlignment:'top'};
  return s;
}
function table(slide,values,widths,top=214,height=264){
  const t=slide.tables.add({rows:values.length,columns:values[0].length,left:68,top,width:1144,height,columnWidths:widths,values});
  t.borders.assign({style:'solid',fill:C.line,width:1});
  t.styleOptions={headerRow:true,bandedRows:false};
  for(let r=0;r<values.length;r++) for(let c=0;c<values[0].length;c++){
    const cell=t.getCell(r,c);
    cell.fill=r===0?C.head:(r%2===0?C.alt:'#FFFFFF');
    cell.text.style={typeface:font,fontSize:'19pt',bold:r===0,color:r===0?C.navy:C.text,alignment:c>0&&String(values[r][c]).length<25?'center':'left',verticalAlignment:'middle',insets:{top:8,right:12,bottom:8,left:12},wrap:'square',autoFit:'none'};
  }
  return t;
}
function addSlide(p,d,number){
  const s=p.slides.add();s.background.fill='#FFFFFF';
  text(s,'title',d.title,68,36,1144,66,32,true,C.navy);
  text(s,'context',d.context,68,116,1144,78,21,false,C.gray);
  table(s,d.rows,d.widths,d.top??214,d.height??264);
  text(s,'interpretation',d.takeaway,68,d.bottom??520,1144,108,21,true,C.text);
  text(s,'source',d.caption,68,658,1090,34,13,false,C.gray);
  text(s,'page',String(number),1162,658,50,30,13,false,C.gray);
  s.speakerNotes.text=`${consult}\n\n${d.notes}\n\nLecture : ${d.takeaway}`;
  return s;
}
const decks=[
{file:'01-Revue-achats.pptx',slides:[
 {title:'Cinq dossiers en revue fournisseurs',context:'Sur 27 fournisseurs évalués, six perturbations dégradent le service. Le budget reste fixé à cinq dossiers.',
  rows:[['Plan de sélection','Probabilité de ne repérer aucun cas','Cas repérés en moyenne sur 6'],['Tirage uniforme','25,21 %','1,11'],['Quatre mono-source et un autre','9,09 %','1,61'],['Cinq mono-source','4,35 %','1,92']],widths:[480,350,314],
  takeaway:'Le quota quatre plus un réduit les listes sans détection tout en gardant les deux groupes représentés. Il ne permet pas de repérer tous les cas.',
  caption:'Sources : cas fournisseurs et CSV public. Probabilités et moyennes recalculées le 25 novembre 2026.',
  notes:`${cahier}#L7-L11\n${github}Cas/Revue-fournisseurs.md\n${github}Cas/revues-fournisseurs.csv\nRecalcul : C(8,4)×C(13,1)/(C(13,4)×C(14,1))=910/10010. Le critère est de ne détecter aucun des six cas, pas la proportion des six cas détectés. Les deux résultats manquants parmi 29 fournisseurs restent inconnus.\nStatistique Canada, Probability sampling, mise à jour 2 septembre 2021 : https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/prob/5214899-eng.htm`},
 {title:'Quantité achetée en dépannage',context:'Le contrôle à réception modifie la quantité réellement utilisable à la date du besoin.',
  rows:[['Résultat du cahier','Valeur','Portée'],['Configurations sans rupture','46 sur 60','76,67 % des configurations testées'],['Besoin court avant contrainte réception','800 kg','Cas central publié'],['Besoin court avec 90 % utilisables','900 kg','100 kg supplémentaires']],widths:[565,180,399],
  takeaway:'La quantité de dépannage dépend du stock libéré à l’échéance. Le minimum de commande et la capacité peuvent encore modifier l’ordre réalisable.',
  caption:'Source : Cahiers métier, thème 02. Recalculs : 46/60 et écart de 100 kg.',
  notes:`${cahier}#L13-L17\nLes 60 configurations et les valeurs 800/900 kg sont rapportées par le cahier. Le ratio 46/60 n'est pas une probabilité de succès industriel. Recalcul : 900−800=100 kg.\nMicrosoft Default order settings, mise à jour 10 juillet 2025 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/default-order-settings\nMicrosoft Quality orders, mise à jour 26 octobre 2026 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-orders`},
 {title:'Les cotations qui changent un audit',context:'L’exercice programme trois visites à partir de 84 cotations. Il teste une cotation inconnue à la fois.',
  rows:[['Résultat du test isolé','Nombre de cotations','Part des 84 cotations'],['Peuvent changer la sélection','16','19,05 %'],['Ne la changent pas dans ce test','68','80,95 %'],['Total des cotations examinées','84','100 %']],widths:[610,267,267],
  takeaway:'Le résultat hiérarchise les justificatifs utiles au choix des visites. Il ne démontre pas la stabilité face à plusieurs informations incertaines simultanément.',
  caption:'Source : Cahiers métier, thème 03. Recalculs : 16/84 et 84−16.',
  notes:`${cahier}#L19-L23\n16 est un nombre de cotations pouvant modifier la sélection. Ce n'est ni un nombre de fournisseurs à risque ni une fréquence de panne. Les poids et bornes individuels ne sont pas publics.\nISO 19011:2026, quatrième édition publiée mai 2026, notice https://www.iso.org/standard/19011 ; communiqué du 9 juin 2026 https://committee.iso.org/sites/tc176/home/news/content-left-area/news-and-updates/iso-19011-2026-released.html\nJRC Step 8 Sensitivity analysis, mise à jour 1 décembre 2020 : https://knowledge-for-policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-8-sensitivity-analysis_en`},
 {title:'Bilan de la veille achats',context:'Les pratiques et les études consultées confortent une revue fondée sur les effets opérationnels et les preuves disponibles.',
  rows:[['Lecture vérifiée','Apport pour les achats'],['ISO 19011:2026, mai 2026','Un cadre actuel pour préparer et conduire les audits'],['Étude automobile, Interfaces, 2015','Évaluer l’effet d’un arrêt avant sa fréquence'],['Documentation ERP, 2025 et 2026','Relier commande, réception qualité et échéance']],widths:[530,614],
  takeaway:'Les pièces suffisent pour vérifier le quota de revue et expliquer les deux autres arbitrages. Les résultats détaillés restent propres aux cas simulés.',
  caption:'Veille réalisée le 25 novembre 2026. Références et liens directs dans les notes.',
  notes:`ISO 19011:2026, quatrième édition publiée mai 2026 : https://www.iso.org/standard/19011\nSimchi-Levi et al., Identifying Risks and Mitigating Disruptions in the Automotive Supply Chain, Interfaces45(5),375–390, publication en ligne20 octobre2015 : https://doi.org/10.1287/inte.2015.0804\nMicrosoft Quality orders,26 octobre2026 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-orders\nAkkerman et al., Solving Dual Sourcing Problems with Supply Mode Dependent Failure Rates, version auteur11 avril2025 : https://arxiv.org/html/2410.03887v2 . Le cas énergie concerne la fiabilité des pièces en service et ne valide pas directement les rendements à réception du cahier.`}
]},
{file:'02-Revue-planification.pptx',slides:[
 {title:'La couverture dépend du lieu et de la date',context:'Le stock du dépôt et le stock de l’usine amont ne servent pas la demande au même instant.',
  rows:[['Périmètre compté','Couverture annoncée','Condition'],['Dépôt utilisable au départ','4 jours complets','Disponible au point de livraison'],['Dépôt et stock amont','5 jours de quantité','Transfert utilisable avant le premier manque'],['Lot en attente de qualité','À sa date de libération','La réception physique ne suffit pas']],widths:[480,300,364],
  takeaway:'La cinquième journée reste conditionnée au transfert. Une promesse fiable s’appuie sur le solde daté au point où la demande doit être servie.',
  caption:'Source : Cahiers métier, thème 04. Les quatre et cinq jours sont des résultats rapportés.',
  notes:`${cahier}#L27-L31\nLes flux journaliers originaux ne sont pas publics. Aucun nouveau stock ou trajet n'a été inventé.\nOracle Promise Only After You Release Holds On Lots, documentation26A2026 : https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fascp/promise-only-after-you-release-holds-on-lots.html\nMicrosoft Net requirements and pegging information,21 juillet2025 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/net-requirements`},
 {title:'Volume repris et service quotidien',context:'Deux trajectoires de reprise sur cinq jours. Réserve disponible : deux unités avant J1, puis deux avant J3.',
  rows:[['Trajectoire','Volume de reprise publié','Résultat avec la réserve publiée'],['Première','90 %','Encore une unité manquante à J2'],['Seconde','84 %','Plancher de neuf livraisons par jour']],widths:[285,355,504],height:240,
  takeaway:'La seconde trajectoire satisfait ici l’engagement quotidien. Les six points de volume en faveur de la première ne garantissent pas le service chaque jour.',
  caption:'Source : Cahiers métier, thème 05. Écart recalculé : 90−84=6 points de pourcentage.',
  notes:`${cahier}#L33-L37\nLes taux de 90 % et 84 % décrivent les trajectoires de reprise publiées. Le résultat quotidien au plancher concerne la situation avec la réserve datée ajoutée. Ces taux ne sont pas présentés comme une couverture recalculée après réserve. L'objectif journalier et l'objectif de volume cumulé ne sont pas identiques. Les courbes journalières ne sont pas publiques et ne sont donc pas tracées ici.\nMicrosoft Calculate order promising dates,16 novembre2026 : https://learn.microsoft.com/en-us/dynamics365/business-central/sales-how-to-calculate-order-promising-dates\nIvanov, When is the supply chain resilient? Customer and operational perspectives,21 janvier2025 : https://doi.org/10.1080/00207543.2025.2454331 ; résumé primaire https://accurateproject.eu/publications/`},
 {title:'Le contrat détermine l’ordre de service',context:'Servir l’urgence améliore le plus grand retard, mais augmente le retard pondéré par les quantités.',
  rows:[['Ordre d’affectation','Retard maximal','Quantités retardées × jours'],['Ordre témoin','7 jours','28 unités-jours'],['Urgence servie d’abord','4 jours','32 unités-jours'],['Écart de la variante','3 jours de moins','4 unités-jours de plus']],widths:[485,300,359],
  takeaway:'Un plafond de quatre jours favorise l’urgence. Une pénalité uniforme par unité-jour favorise l’ordre témoin, si les autres clauses restent identiques.',
  caption:'Source : Cahiers métier, thème 06. Écarts recalculés sur les résultats agrégés.',
  notes:`${cahier}#L39-L43\nLes commandes, quantités et arrivages originaux sont absents. Les deux bilans sont rapportés, et leurs différences sont recalculées. L'affectation suppose un lot réellement libéré.\nMicrosoft Priority-based planning,17 juin2025 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/planning-optimization/priority-based-planning . La priorité de réapprovisionnement documentée n'est pas une preuve d'optimalité de l'allocation client.`},
 {title:'Bilan des comparaisons de planification',context:'Les trois résultats convergent sur la promesse faite au client et la disponibilité réellement utilisable.',
  rows:[['Décision étudiée','Ce qui départage les options'],['Couverture du dépôt','Date d’arrivée utilisable du transfert'],['Reprise de service','Engagement quotidien ou volume à échéance'],['Allocation d’un lot','Plafond de retard ou pénalité sur les unités-jours']],widths:[490,654],
  takeaway:'Les résultats agrégés suffisent pour expliquer ces choix. Ils ne permettent pas de rejouer les ordres ni de dessiner des trajectoires quotidiennes détaillées.',
  caption:'Étude du 25 novembre 2026. Pratiques ERP et publication de recherche citées dans les notes.',
  notes:`Sources de résultats : ${cahier}#L27-L43\nOracle, documentation26A2026 : https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fascp/promise-only-after-you-release-holds-on-lots.html\nMicrosoft Calculate order promising dates,16 novembre2026 : https://learn.microsoft.com/en-us/dynamics365/business-central/sales-how-to-calculate-order-promising-dates\nIvanov, When is the supply chain resilient? Customer and operational perspectives,21 janvier2025 : https://doi.org/10.1080/00207543.2025.2454331 . Trois réseaux simulés, plusieurs indicateurs de service. La différence des perspectives client et opérationnelle est un résultat publié, pas une validation supplémentaire de nos cas.`}
]},
{file:'03-Revue-transport.pptx',slides:[
 {title:'Deux tournées dépassent un chargement',context:'Chaque tournée transporte 40 unités. Le véhicule peut charger 60 unités à la fois.',
  rows:[['Configuration','Charge','Résultat de capacité'],['Une tournée séparée','40 unités','20 unités de marge'],['Deux tournées regroupées','80 unités','20 unités de dépassement'],['21 fermetures de créneau testées','Un chargement par regroupement','Aucun regroupement faisable']],widths:[490,255,399],
  takeaway:'Le regroupement en un chargement est exclu. Deux chargements peuvent mobiliser un ou deux véhicules selon les temps de rotation et les créneaux.',
  caption:'Source : Cahiers métier, thème 07. Recalculs : 40+40=80 unités, dépassement de 20.',
  notes:`${cahier}#L47-L51\nLe résultat0/21 est rapporté. Les21calendriers ne sont pas publics. La comparaison des horaires, coûts et émissions des variantes n'est pas réalisable sur ces agrégats.\nMicrosoft Set up an appointment for a load,17 février2025 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/transportation/tasks/set-up-appointment-load\nHuang et al., Optimization of external container delivery and pickup scheduling based on appointment mechanism,21 février2025 : https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0318606 . Cas portuaire simulé, gain de4,89%contre leur planning manuel, non transféré à notre quai.`},
 {title:'La collecte dépend du budget de demandes',context:'La couverture mesure des tonnes-kilomètres documentées. Elle ne prouve pas que tous les tronçons d’un parcours le sont.',
  rows:[['Budget de demandes','Parcours complets','Liaisons'],['Trois demandes','47,6 % des tonnes-kilomètres','42,0 % des tonnes-kilomètres'],['Écart à trois demandes','5,6 points en faveur des parcours','Écart recalculé'],['Dix demandes','Couverture absolue non fournie','Environ 13,6 points d’avance']],widths:[360,392,392],
  takeaway:'Les parcours sont devant à trois demandes et les liaisons à dix. Les agrégats ne donnent ni le point de bascule intermédiaire ni une stratégie optimale.',
  caption:'Source : Cahiers métier, thème 08. Recalcul : 47,6−42,0=5,6 points de pourcentage.',
  notes:`${cahier}#L53-L57\nLe dénominateur est le total des tonnes-kilomètres modélisées. Les résultats portent sur le budget de demandes présenté par le cahier. Aucune probabilité de réponse nouvelle n'est ajoutée.\nSmart Freight Centre, GLEC Frameworkv3.3,publié27 octobre2026 : https://smartfreightcentre.org/news/13311209/\nCrosswalk édition4,26 octobre2026 : https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311209/3b754d52417445123e4d321e33d4a3ab.pdf\nKallionpää et al., Development of logistics emissions reporting, en ligne novembre2025,numérojanvier2026,17entretiens : https://doi.org/10.1016/j.trd.2025.105083`},
 {title:'La charge de revue dépend de l’alerte',context:'Même périmètre de 956 mois-scénarios, dont 273 mois dégradés. Le signal utilise le mois précédent.',
  rows:[['Règle','Mois dégradés détectés sur 273','Fausses alertes','Dossiers ouverts'],['Saturation à 90 %','257','622','879'],['Saturation à 95 %','251','616','867'],['Saturation à 99 %','247','611','858'],['Persistance du service insuffisant','136','140','276']],widths:[450,270,207,217],top:206,height:290,bottom:524,
  takeaway:'Le seuil 95 % détecte 91,94 % des mois dégradés, mais seules 28,95 % des 867 alertes sont justifiées. La relance ne prouve pas un retard évité.',
  caption:'Source : alertes-fret.csv. Dossiers, rappel et précision recalculés le 25 novembre 2026.',
  notes:`${github}Cas/Alertes-fret.md\n${github}Cas/alertes-fret.csv\nRappel95%=251/273, précision95%=251/(251+616), dossiers=TP+FP. Service dégradé : masse servie strictement inférieure à99%de la demande. Les quatre trajectoires sont apparentées et ne constituent pas956observations indépendantes.\nIATA ONE Record, note de version25 juillet2026 : https://iata-cargo.github.io/ONE-Record/development/General/release-note/\nCargo iQ MOP,documentationjuillet2025 : https://iata-cargo.github.io/ONE-Record/2025-07/Orchestration/orchestration-mop/`},
 {title:'La comparaison complète change le seuil fret',context:'Coût comparé : fausses alertes + r × mois manqués. r est le coût d’un manque divisé par celui d’une fausse alerte.',
  rows:[['Rapport de coûts r','Meilleure des cinq règles publiées'],['De 0 à 1,0294','Aucune alerte'],['De 1,0294 à 3,9835','Persistance du service insuffisant'],['Au-delà de 3,9835','Saturation à 90 %']],widths:[460,684],
  takeaway:'Le seuil 4,14 reste correct pour 95 % face à la persistance. Parmi les cinq règles publiées, 95 % et 99 % ne minimisent jamais ce coût simplifié.',
  caption:'Recalcul sur le CSV public. Égalité aux seuils. Coût des revues justifiées fixé ici à zéro.',
  notes:`${github}Cas/alertes-fret.csv\nComparaison95%vs persistance : (616−140)/(137−22)=476/115=4,13913. Enveloppe des5règles : aucunealerteverspersistance140/(273−137)=35/34 ; persistancevers90%(622−140)/(137−16)=482/121. Aucunealerte aTP0,FP0,FN273,TN683.\nContrôle complémentaire dérivé des totaux, non inclus dans les5règles du tableau : toujoursalerter aTP273,FP683,FN0,TN0 et devient moins coûteux que la persistance à543/137=3,96350 si lesrevuesjustifiées ne coûtent rien et la capacité est illimitée. Ce résultat souligne la nécessité de chiffrer le traitement de tous lesdossiers avant un usage opérationnel. Ce modèle compare des erreurs de détection et n'est pas une mesure causale des pertes évitées.`}
]},
{file:'04-Revue-qualite-environnement.pptx',slides:[
 {title:'Le stock physique ne garantit pas un jeu complet',context:'Quatre variantes d’assemblage contrôlent séparément 163 composants. La disponibilité qualité reste déterminante.',
  rows:[['Observation de la variante modérée','Résultat rapporté','Lecture métier'],['Disponibilité reportée','Un mois','Le lot reste indisponible au besoin'],['Stock bloqué en clôture','115,12 kg','Le stock physique augmente'],['Jeux livrés','Une unité de moins','Le service diminue malgré ce stock']],widths:[475,230,439],
  takeaway:'Le lancement dépend de chaque référence utilisable au poste requis. La somme des kilogrammes ne démontre pas la présence de tous les composants.',
  caption:'Source : Cahiers métier, thème 10. Résultats rapportés, nomenclature détaillée non publique.',
  notes:`${cahier}#L67-L71\nLes bilans sur163composants et115,12kg sont rapportés par le cahier, sans reconstruction de nomenclature.\nMicrosoft Inventory blocking,miseàjour14 août2025 : https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-blocking\nGS1 EPCIS2.0,juin2022,états métier associés aux événements : https://ref.gs1.org/standards/epcis/\nISO9001:2026,annonce16 septembre2026 : https://www.iso.org/news/2026/09/ISO9001-2026 . Le communiqué ne suffit pas à attribuer des exigences détaillées aux clauses.`},
 {title:'Le trajet change le seuil de retouche',context:'Le cahier étudie un lot de six pièces. La comparaison inclut le transport déclenché par la décision.',
  rows:[['Transport associé à la retouche','Acceptations minimales sur 6','Condition de calcul'],['Navette déjà prévue','3 pièces','Effet marginal de la charge négligeable'],['Tournée dédiée de 12 kg CO₂e','4 pièces','Émissions du trajet incluses'],['Écart de seuil','Une acceptation de plus','Même comparaison de service']],widths:[500,295,349],
  takeaway:'Une retouche favorable avec une navette existante peut changer de résultat si elle déclenche une tournée dédiée. Le périmètre explique la bascule.',
  caption:'Source : Cahiers métier, thème 11. Seuils rapportés de trois et quatre acceptations.',
  notes:`${cahier}#L73-L77\nAucun inventaire de retouche, remplacement ou rebut détaillé n'est public. Les seuils3et4 ne sont pas reproduits à partir d'inventaires absents. L'effet marginal de charge négligeable ne signifie pas une allocation nulle dans tout inventaire transport.\nGHG Protocol Product Life Cycle Accounting and Reporting Standard,2011 : https://ghgprotocol.org/sites/default/files/standards/Product-Life-Cycle-Accounting-Reporting-Standard_041613.pdf\nJärnefelt,Ashouri,Behm,Does repair improve environmental performance?20 septembre2026 : https://doi.org/10.1016/j.jclepro.2026.149164 ; résumé primaire https://cris.vtt.fi/en/publications/does-repair-improve-environmental-performance-integrating-tempora/ . Effets du composant,de la date de panne et de la catégorie d'impact. Pas de transfert de gain au cahier.`},
 {title:'La pondération inverse le choix de conception',context:'Deux variantes à masse identique sont comparées sur la production et la livraison, avec seize indicateurs.',
  rows:[['Résultat de comparaison','Valeur rapportée','Interprétation'],['Indicateurs améliorés','8 sur 16','Une moitié évolue favorablement'],['Indicateurs dégradés','8 sur 16','L’autre moitié évolue défavorablement'],['Poids de bascule de l’eutrophisation','7,294 %','Autres poids ajustés proportionnellement']],widths:[515,225,404],
  takeaway:'Aucune variante ne domine sur les seize indicateurs. Le classement dépend de la préférence retenue et du même périmètre de comparaison.',
  caption:'Source : Cahiers métier, thème 12. Seuil rapporté, non recalculé faute des vecteurs détaillés.',
  notes:`${cahier}#L79-L83\nLe cahier ne nomme pas la variante gagnante de chaque côté du seuil. Masse égale ne démontre pas une fonction et une durée de service identiques. Les16vecteurs et facteurs de normalisation sont absents.\nCommission européenne,recommandation Empreinte environnementale16 décembre2021 : https://environment.ec.europa.eu/publications/recommendation-use-environmental-footprint-methods_en\nJRC EF3.1,rapport8 février2023 : https://op.europa.eu/en/publication-detail/-/publication/145f8401-a82a-11ed-b508-01aa75ed71a1\nJRC transition EF,miseàjour4 novembre2026 : https://knowledge-for-policy.ec.europa.eu/environmental-footprint-transition-phase_en . La page actualisée ne signifie pas publication d'une nouvelle méthode EF.`},
 {title:'Bilan de la veille qualité et environnement',context:'Les sources distinguent la disponibilité du lot, le périmètre environnemental et les préférences de décision.',
  rows:[['Référence consultée','Résultat utile pour la revue'],['ISO 9001:2026 et GS1 EPCIS','Un état de lot doit être relié à une date et une preuve'],['GHG Product Standard et étude réparation 2026','Le service équivalent et les étapes déclenchées comptent'],['Méthode EF et rapport JRC EF 3.1','Normalisation et pondération restent distinctes des impacts']],widths:[520,624],
  takeaway:'Les trois cahiers documentent des bascules de décision. Les agrégats permettent leur lecture, mais ne suffisent pas à reconstruire les inventaires et les lots.',
  caption:'Veille du 25 novembre 2026. Les références détaillées figurent dans les notes de chaque sujet.',
  notes:`ISO9001:2026,communiqué16 septembre2026 : https://www.iso.org/news/2026/09/ISO9001-2026\nGS1 EPCIS2.0,juin2022 : https://ref.gs1.org/standards/epcis/\nGHG Protocol Product Standard,2011 et groupe conjointISOannoncé9 février2026 : https://ghgprotocol.org/product-standard . Aucune nouvelle méthode finale n'est inférée de l'annonce du groupe de travail.\nJärnefelt etal.,2026 : https://doi.org/10.1016/j.jclepro.2026.149164\nJRC EF3.1,2023 : https://op.europa.eu/en/publication-detail/-/publication/145f8401-a82a-11ed-b508-01aa75ed71a1\nLes apports du tableau sont une synthèse de la veille. Le communiqué ISO seul ne démontre pas le détail des clauses appliquées aux événements de lot.`}
]},
{file:'05-Revue-controle-gestion.pptx',slides:[
 {title:'Le regroupement change le risque de coût',context:'L’exercice porte sur 240 jeux et compare l’achat à la fabrication en interne.',
  rows:[['Résultat publié','Valeur','Portée'],['Probabilité basse d’achat plus cher','Environ 15,0 %','Une hypothèse de regroupement'],['Probabilité haute d’achat plus cher','Environ 40,4 %','Une autre hypothèse de regroupement'],['Amplitude entre les deux','25,4 points','Sensibilité à la dépendance des urgences']],widths:[570,230,344],
  takeaway:'Le prix moyen d’une intervention ne décrit pas la valeur du plafond. Son niveau de remise à zéro et les urgences communes modifient le coût du contrat.',
  caption:'Source : Cahiers métier, thème 13. Recalcul : 40,4−15,0=25,4 points.',
  notes:`${cahier}#L87-L91\nLes probabilités sont rapportées et dépendent d'hypothèses de regroupement dont les données détaillées ne sont pas publiques. Leur différence approximative est calculée sur les pourcentages arrondis du cahier. Le cahier ne permet pas d'attribuer chaque extrême à une loi contractuelle précise.\nHM Treasury,Orange Book,miseàjour18 novembre2026 : https://www.gov.uk/government/publications/orange-book/the-orange-book-management-of-risk-principles-and-concepts . Dépendances entre risques.\nHM Treasury,Green Book2026,miseàjour28 octobre2026 : https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026 . Référence d'évaluation publique utilisée comme repère méthodologique privé,aucune obligation normative française inférée.`},
 {title:'L’accélération seule suffit dans le premier cas',context:'Le cahier distingue un retard d’approvisionnement et une retenue qualité. Les effets des interventions diffèrent.',
  rows:[['Incident simulé','Résultat de la comparaison','Choix économique sur cet indicateur'],['Retard d’approvisionnement','Même surcroît moyen d’arriéré annulé','Accélération seule moins chère'],['Retenue qualité','La combinaison réduit encore l’arriéré','Arbitrage selon le coût du retard'],['Seuil publié sous pénalité linéaire','Environ 2,49 unités monétaires par unité-jour','Propre au second essai']],widths:[350,410,384],
  takeaway:'À gain de service supplémentaire nul, l’accélération seule reste moins chère. La valeur de la combinaison dépend du mécanisme de l’incident.',
  caption:'Source : Cahiers métier, thème 14. Le seuil 2,49 est rapporté en unités monétaires simulées.',
  notes:`${cahier}#L93-L97\nLe seuil2,49 n'est pas en euros. Les coûts et arriérés détaillés par option ne sont pas publics et ne sont pas recréés.\nACCA,Relevant costs,sansdateaffichée : https://www.accaglobal.com/uk/en/student/exam-support-resources/fundamentals-exams-study-resources/f5/technical-articles/relevant-costs.html . Flux futurs modifiés par la décision,coûts d'opportunité et exclusion des dépenses déjà engagées communes.\nMüllerklein etFontaine,Resilient transportation network design with disruption uncertainty and lead times,2025,enligne22 novembre2024 : https://doi.org/10.1016/j.ejor.2024.11.021 . La capacité et le délai du réacheminement conditionnent les gains dans leur étude.`},
 {title:'Le coût pertinent est le surcoût de la décision',context:'Les deux sujets mettent en balance une dépense supplémentaire et un risque ou un retard supplémentaire évité.',
  rows:[['Décision étudiée','Calcul économique pertinent','Cas où l’option simple l’emporte'],['Prime de plafonnement','Frais évités selon le regroupement','Prime supérieure aux frais évités sous les deux hypothèses'],['Combinaison d’interventions','Surcoût / unités-jours supplémentaires évitées','Gain de service supplémentaire nul']],widths:[335,400,409],height:250,
  takeaway:'Les coûts moyens et les dépenses déjà engagées ne suffisent pas à départager les options. Le résultat dépend des clauses et des effets réellement supplémentaires.',
  caption:'Synthèse des thèmes 13 et 14 et de la veille ACCA.',
  notes:`${cahier}#L87-L97\nPour la combinaison : seuil=surcoût/(arriéré accélération−arriéré combinaison)si la différence est positive et si la pénalité est linéaire. À différence nulle,le quotient n'est pas défini et la comparaison retient le coût le plus faible à efficacité identique sur l'indicateur.\nACCA,Relevant costs,consulté25 novembre2026 : https://www.accaglobal.com/uk/en/student/exam-support-resources/fundamentals-exams-study-resources/f5/technical-articles/relevant-costs.html\nHM Treasury,Green Book2026,28 octobre2026 : https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026 . Les valeurs de bascule sont un repère méthodologique. Les franchises,plafonds et pénalités par commande nécessitent une application de la clause avant agrégation.`},
 {title:'Bilan de la veille en contrôle de gestion',context:'Les lectures professionnelles et les cas de recherche apportent des repères différents à la même comparaison de coût et de service.',
  rows:[['Lecture primaire','Apport établi','Limite du transfert'],['ACCA sans date, HM Treasury 2026','Coûts différentiels et valeurs de bascule','Aucun tarif industriel fourni'],['Ivanov, trésorerie supply chain, 2024','Les actions coordonnées changent les flux de trésorerie','L’étude ne chiffre pas un plafond d’urgences'],['Müllerklein et Fontaine, 2025','Capacité et délai affectent l’intérêt du réacheminement','Les gains publiés ne valent pas pour notre cas']],widths:[425,370,349],
  takeaway:'Les agrégats établissent la sensibilité des deux décisions. Ils ne permettent pas de reproduire les probabilités détaillées ni de convertir 2,49 en un tarif contractuel.',
  caption:'Veille et étude du 25 novembre 2026. Sources datées et liens directs dans les notes.',
  notes:`ACCA,Relevant costs,sansdateaffichée : https://www.accaglobal.com/uk/en/student/exam-support-resources/fundamentals-exams-study-resources/f5/technical-articles/relevant-costs.html\nHM Treasury,Green Book2026,miseàjour28 octobre2026 : https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026\nHM Treasury,Orange Book,miseàjour18 novembre2026 : https://www.gov.uk/government/publications/orange-book/the-orange-book-management-of-risk-principles-and-concepts\nIvanov,Cash flow dynamics in the supply chain during and after disruptions,mai2024 : https://doi.org/10.1016/j.tre.2024.103526 ; texteauteurouvert https://www.researchgate.net/publication/379997336_Cash_flow_dynamics_in_the_supply_chain_during_and_after_disruptions\nMüllerklein etFontaine,Resilient transportation network design with disruption uncertainty and lead times,2025,enligne22 novembre2024 : https://doi.org/10.1016/j.ejor.2024.11.021 ; articleuniversitaireouvert https://edoc.ku.de/id/eprint/34580/1/1-s2.0-S0377221724008907-main.pdf`}
]}
];

const receipts=[];
const selected = process.env.IC_PPT_ONLY ? process.env.IC_PPT_ONLY.split(',') : null;
for(const deck of decks.filter(d=>!selected || selected.includes(d.file))){
  const p=Presentation.create({slideSize:{width:1280,height:720}});
  deck.slides.forEach((d,i)=>addSlide(p,d,i+1));
  const dir=path.join(qa,deck.file.replace('.pptx',''));
  await fs.mkdir(dir,{recursive:true});
  const candidatePath=path.join(dir,'candidate.pptx');
  const finalPath=path.join(dir,'final.pptx');
  await (await PresentationFile.exportPptx(p)).save(candidatePath);
  const owners=[1,2,3,4];
  const result=await finalizePresentation({
    workspaceDir,candidatePath,finalPath,pythonExecutable:runtimePython,
    integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
    layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
    layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...owners.flatMap(n=>['--require-native-table-slide',String(n)])],
    explicitTotalSlideCount:4,requiredNativeTableOwnerSlides:owners,requiredNativeChartOwnerSlides:[],
    fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
    receiptPath:path.join(qa,'receipts',deck.file+'.validation.json')
  });
  const finalPresentation=await PresentationFile.importPptx(await FileBlob.load(finalPath));
  for(let i=0;i<4;i++){
    const blob=await finalPresentation.export({slide:finalPresentation.slides.getItem(i),format:'png',scale:1});
    await fs.writeFile(path.join(dir,`slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
  await fs.copyFile(finalPath,path.join(outputDir,deck.file));
  receipts.push({file:deck.file,slides:4,editableTables:4,finalizationReceipt:path.join(qa,'receipts',deck.file+'.validation.json'),renderDir:dir});
  console.log(JSON.stringify({file:deck.file,renderDir:dir,validated:true}));
}
await fs.writeFile(path.join(qa,'index.json'),JSON.stringify(receipts,null,2)+'\n');
console.log(`QA_INDEX=${path.join(qa,'index.json')}`);
