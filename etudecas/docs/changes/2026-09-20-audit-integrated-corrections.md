# Corrections après audit approfondi — 20 septembre 2026

Cette livraison répond à l'audit destiné au planificateur supply chain et au
responsable industriel. Les sources et les résultats historiques restent
conservés. Les nouveaux calculs se trouvent dans
`simulation/result/_reruns/audited_corrections_20260920`.

La livraison et ses contrôles d'intégration sont terminés dans le périmètre
documenté. Ouvrir la [carte corrigée](../../simulation/result/_reruns/audited_corrections_20260920/maps/supply_graph_audited_corrections_20260920.html),
le [diagnostic métier](../../simulation/result/_reruns/audited_corrections_20260920/decision_support/index.html)
ou l'[explorateur des lots du scénario de risque](../../simulation/result/_reruns/audited_corrections_20260920/scenario_runs/state_dependent_full/maps/lot_explorer_audited_20260920.html).
La [synthèse de vérification](../../artifacts/testing/audit_corrections_20260920/verification-summary.json)
relie les preuves aux fichiers exacts. Les conventions restant à qualifier
industriellement sont explicitées ci-dessous.

## Changements métier

| Sujet | Comportement corrigé | Vérification |
|---|---|---|
| Demande | Le lissage MRP ne déplace plus la demande client datée. | Excel et CSV : 14 600 lignes jour/article et leurs sommes hebdomadaires rapprochées sur les quatre calculs. |
| Sécurité | Jours ouvrés lundi-vendredi ; 100 % des jours sources au dépôt. | Décisions utilisateur, conversion datée depuis le snapshot du 1er janvier 2025 ; pas de fermeture implicite des opérations le week-end. |
| Valeurs et coûts | Prix absent explicitement inconnu ; retrait de la médiane qui mélangeait les unités. Coûts opérationnels, achats externes et exposition économique distingués. | Cas contradictoires et vérification indépendante des résumés, CSV et cartes. Une valorisation incomplète interdit le classement économique. |
| Délais et transports | Date prévue disponible à la décision distincte du délai constaté à réception ; réservé, parti et reçu séparés. | Tests avec départs/réceptions après horizon ; rapprochement des statuts et mouvements. |
| Bilans matière | Réceptions, consommations et clôtures viennent du registre physique. La consommation BOM reste une information théorique séparée. | Bilans annuels et fenêtres de lecture ; absence de source, année manquante et écarts compensés volontairement testés. |
| Courbes et alertes | Quantités groupées par unité ; besoin actif manquant distinct d'un article inactif à stock nul ; résidu prévisionnel distinct d'une unité client en retard. | Oracles CSV, contre-exemples et tests navigateur. |
| Risques | Application locale d'un événement distincte de sa configuration ; concomitance avec un retard aval explicitement non causale. | Cas sans application locale et retrait des montants de pertes client attribués sans preuve. |

`tau_process` conserve son sens actuel de planification, conformément à la
réponse utilisateur. Les 23 bases MRP statiques et la propriété économique du
stock réservé restent des conventions à examiner, sans substitution silencieuse.

## Résultats des nouveaux calculs

Les quatre calculs conservent la graine 42 et leurs graphes/scénarios exacts.
Les contrôles de sensibilité ×1,5 et d'accélération restent séparés du nominal ;
leurs cibles historiques sont conservées pour comparer la même intervention.

Pour 268091, la première semaine vaut désormais **13 300 UN**, conformément au
profil source retenu, au lieu de 22 908,142858 dans l'ancienne trajectoire lissée.
L'oracle décrit explicitement le traitement existant des semaines source
négatives : les corrections sont reportées dans le profil avant comparaison.
Il ne prétend pas que les demandes positives sont identiques aux lignes signées
brutes de l'Excel.

Sur 1 825 jours, chaque calcul sert 25 762 139 unités pour une demande exportée
de 25 762 139,9999. Le reliquat inférieur à une unité est prévisionnel ; le taux
cumulé arrondi ne mesure pas la livraison à l'heure. Le diagnostic FIFO conserve
les retards et les demandes ouvertes séparément.

Le maximum FIFO nominal de 29 jours pour 268967 porte ici sur quatre reliquats
prévisionnels inférieurs à une unité. Il ne représente pas une commande physique
retardée de 29 jours. Le diagnostic affiche cette limite de la reconstruction ;
les quantités physiques et les cohortes de prévision restent distinctes.

Pour **PBATCH-411EC755D7110AE0**, les nouveaux CSV du nominal donnent deux
contributions reçues chez le client : **1 835 + 12 565 = 14 400 UN**.
La découpe historique 3 473 + 10 927 reste attachée à l'ancien calcul. Le
contrôle du diagramme utilise désormais les identités et quantités du CSV
explicitement fourni, au lieu d'imposer cette ancienne découpe.

Les quatre valorisations restent **incomplètes** : certains taux de stock ne
disposent pas d'une base économique valable. Les montants connus sont
consultables, mais leur variation ne permet pas de conclure à une économie
globale. Une couverture de taux complète ne serait pas non plus une preuve
de calibration industrielle.

## Lecture de la carte

Les deux suivis de lots sont conservés. La carte s'ouvre sans lot sélectionné.
Les fenêtres disposent d'un focus au clavier, d'une fermeture par Échap et
d'un retour au bouton d'ouverture. Les 87 radars fournisseurs ont été parcourus
dans Chromium. Les onglets imbriqués donnent aussi accès aux différentes unités
des panneaux MRP. Les longues notes sont placées hors de la zone du graphique.

Le tableau matière affiche le stock final et un détail « Pourquoi ces chiffres ? ».
Le filtre annuel recalcule ouverture, mouvements et clôture sur la période
continue sélectionnée. Les diagnostics qui restent calculés sur l'horizon
complet portent cette mention. Une année absente ne donne pas un bilan qualifié.

## Travail multi-agent et documentation

Trois agents ont travaillé sur des périmètres distincts : moteur/données,
payloads/courbes, toolbox/replays. Le parent a intégré l'interface, les
contrats de livraison et la documentation. La contre-relecture a révélé des
défauts supplémentaires, corrigés avec des oracles séparés de l'implémentation.

Le dépôt contient quatre profils Codex et trois skills. La toolbox fournit
`doctor`, `tests`, `qualify`, `browser`, `docs`, `gate` et `handoff`. Les preuves
sont liées aux sources et données examinées. Un test faux, une preuve manquante,
un changement de JavaScript, de configuration ou de texte métier empêche de
réutiliser un ancien succès. Les 21 tests propres à cet outillage passent.

Onze registres documentaires relient désormais règles, fonctions et tests.
La génération détecte une divergence mais n'accepte pas automatiquement une
nouvelle règle métier. Le nouveau registre documente aussi les conventions
non décidées. Le [guide opérationnel](../MULTI_AGENT_OPERATIONNEL.md) précise
les commandes et les limites de l'orchestration native.

## Preuves disponibles

- [Vérification numérique finale](2026-09-20-final-map-numeric-verification.md) : 567 figures, 1 370 séries, 2 176 246 valeurs recalculées ; 8 627 contrôles sans écart.
- [Acceptation finale de la toolbox et du retour d'agent](../../artifacts/testing/audit_corrections_20260920/final-toolbox-v2/final-status.json) : doctor, tests, qualification, navigateur et documentation, avec empreintes actuelles.
- [Suites générales](../../artifacts/testing/audit_corrections_20260920/final-tests/README.md) : 1 035 tests et 70 sous-tests réussis, 2 ignorés ; cette exécution précède les derniers ajustements. Sur le code final, **156 tests ciblés et 3 sous-tests réussissent**, sans additionner les contrôles qui se recouvrent. Le refus de lancement Chromium dans la sandbox est conservé ; l'exécution autorisée a ensuite réussi.
- [Interface finale](../../artifacts/testing/audit_corrections_20260920/ui-final/report.json) : cinq fenêtres et leur clavier, 87 radars accessibles, périodes explicites ; 9 parcours généraux supplémentaires passent, sans erreur JavaScript.
- [Lots du nominal](../../artifacts/testing/audit_corrections_20260920/model/final-lot-browser/review.md) : 9 contrôles, dont les deux expéditions et 14 400 UN du PBATCH. L'explorateur risque passe séparément 7 contrôles.
- [Diagnostic indépendant](../../artifacts/testing/audit_corrections_20260920/model/final-dashboard/review.md) : 193 contrôles, oracles CSV et FIFO reconstruits sans appeler le producteur du rapport.
- [Rapprochement final carte/CSV](../../artifacts/testing/audit_corrections_20260920/final-map-delivery-v2.json) et [précision des exports de coûts](2026-09-20-cost-rounding-README.md) : refus initial conservé, borne d'arrondi démontrée et erreurs dépassant cette borne rejetées.
- [Quatre replays et commandes exactes](../../artifacts/testing/audit_corrections_20260920/replays/replay-finalized.json).
- [Rapprochements indépendants des quatre calculs](../../artifacts/testing/audit_corrections_20260920/replays/independent-verification.json) : 62 familles par calcul, 3 867 173 contrôles ponctuels, aucune violation ; 124 CSV/résumés inchangés pendant la revue.
- [Préservation des sources et résultats historiques](../../artifacts/testing/audit_corrections_20260920/preservation.json) : 135 fichiers identiques.
- [Corrections du moteur et leurs preuves](2026-09-20-audit-model-corrections.md).
- [Corrections des données de la carte](2026-09-20-audit-payload-corrections.md).
- [Revue indépendante de l'interface et des coûts](../../artifacts/testing/audit_corrections_20260920/model/review_parent/evidence.json).
- [Revue des changements documentaires](../../artifacts/testing/audit_corrections_20260920/documentation-review.json).

La couverture porte sur les contrats et parcours décrits dans les preuves.
Elle ne certifie pas tous les prototypes historiques ni les paramètres
industriels. Les identités fabricant, contenants, poids et dates de péremption
absents restent inconnus. Les incidents physiques ciblés sur des lots restent
l'étape suivante, après cette consolidation du suivi.

## Priorités après cette livraison

1. **Qualifier les hypothèses industrielles encore ouvertes** : sens physique de
   `tau_process`, base des 23 besoins MRP statiques, propriété du stock réservé,
   prix et profils de chargement manquants. Garder les valeurs inconnues visibles
   jusqu'à disposer d'une source ou d'une estimation explicitement acceptée.
2. **Préparer le premier incident physique de lot** : quarantaine, rebut ou retard
   choisi avec sa règle de propagation. Vérifier ensuite conservation, blocage,
   transport, consommation en production et service client dans les deux sens.
3. **Renforcer l'évaluation des politiques** : scénarios appariés, plusieurs graines,
   séparation calibration/évaluation et intervalles d'incertitude. Les scores
   descriptifs et une concomitance ne constituent pas une attribution causale.
4. **Poursuivre la simplification métier** : contexte article/site/date/scénario
   commun et accès direct à la preuve. Le poids du HTML autonome et les parcours
   non encore couverts restent des limites à mesurer dans l'usage quotidien.

Le [plan scientifique de l'audit](../audit_20260920/recherche_et_verification.md)
détaille les expériences et distingue vérification informatique et validation
industrielle. Le chargement effectif des quatre profils personnalisés lors d'une
nouvelle session Codex reste à observer ; l'installation, la découverte des skills
dans cette session et les commandes de la toolbox ont été vérifiées séparément.
