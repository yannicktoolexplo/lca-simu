# Reprise des cascades dépendant de l'état — 13 novembre 2026

Précision ultérieure de l'utilisateur : la référence visée est
[`01_demonstration_complete`](2026-11-13-reference-01-risques-etat.md), qui combine
risques endogènes et pilotage V3. Le présent suivi conserve l'investigation 2×2
effectuée avant cette identification ; ses résultats ne constituent pas un
rejeu de `01`.

La demande est de reprendre la version la plus complète des cascades simulées,
avec leurs réactions aux états de la chaîne, puis leurs effets sur les lots.
Le suivi isolé des expéditions exposées livré le 12 novembre ne démontre pas
à lui seul une amplification par ces réactions.

## Version reprise

La démonstration historique la plus complète pour cette question est
`supplier_state_cascade_338929_meeting_20260904_v3_2x2_720d`, conservée dans
`C:/dev/lca-simu-pr40-validation-artifacts-20260726/`.
Elle croise incident absent/présent et réactions à l'état désactivées/activées.
Elle suit stocks, production, retards clients, nouveaux signaux, déclenchements
décalés et généalogie des lots.

Ses résultats ne sont pas repris comme résultats actuels : elle utilise un
ancien moteur, une autre mise en régime, moins de stock initial et exclut des
ordres initiaux. Les quatre calculs courants conservent les stocks, les ordres,
les règles MRP et les sécurités de `coherent-MRP-20261014`.

Le portefeuille actuel le plus complet est `full` dans
`run_etudecas_pipeline.py`. Il réunit les crises amont, qualité et emballages,
fiabilité, libération interne et distribution. Les scénarios ciblés restent
utiles en complément. Les campagnes `canonical` et le sidecar V8 désactivent
les réactions endogènes pour isoler le choc : ils ne remplacent pas cette
comparaison de dépendance à l'état.

## Ce que mesurent les quatre calculs

| Cas | Crises programmées | Réactions à l'état |
|---|---|---|
| A | Absentes | Désactivées |
| B | Absentes | Activées |
| C | Portefeuille complet | Désactivées |
| D | Même portefeuille complet | Activées |

Pour chaque indicateur, avec la même période et la même unité :

```text
Effet des crises seules = résultat C − résultat A
Effet des crises avec réactions = résultat D − résultat B
Effet additionnel des réactions = (résultat D − résultat B) − (résultat C − résultat A)
```

Les lettres désignent les quatre cas du tableau. Le résultat est une valeur
de stock, de production, de retard, de service ou de coût sur le même périmètre.
Un signe positif est une hausse de l'indicateur, pas nécessairement un progrès :
plus de retard dégrade le service. Les quantités d'articles et unités différents
ne sont pas additionnées. La comparaison ne se limite pas au nombre total de
signaux : des signaux nouveaux peuvent être compensés par des signaux disparus
ou déplacés dans le calendrier.

## Mécanisme existant conservé

Le moteur courant possède déjà 18 règles de déclenchement. Elles surveillent
notamment couverture de stock, capacité utilisée, délais constatés à réception,
refus d'approvisionnement, pertes et coût de recours amont. Exemple de règle
simulée : une couverture inférieure à trois jours pendant deux jours consécutifs
peut réduire la disponibilité à 85 % pendant 14 jours.

Les règles observent l'état, respectent une période initiale d'observation de
30 jours, puis leurs effets commencent le lendemain du déclenchement. Une
temporisation évite de réenregistrer chaque jour le même incident. Les effets
endogènes sont bornés. Aucun seuil n'est modifié pour forcer une cascade ou
retrouver une courbe industrielle.

## Première lecture sur 56 jours livrée

Le protocole et les preuves sont dans
`etudecas/artifacts/testing/cascade_etat_20261113/`.
Le pilote de 56 jours réutilise A/B du 12 novembre uniquement après contrôle
des empreintes de code, paramètres, demande, stocks et ordres initiaux. C/D
sont de nouveaux calculs avec les journaux complets de lots. Les 28 crises
du pilote gardent leurs dates originales ; les événements plus tardifs ne
sont jamais déplacés artificiellement au dernier jour.

La [carte complète](../../resultats/campagne_complete_20261109/carte_nominale_reel_2025.html)
contient maintenant le bouton **Comparer la crise et les réactions d'état · 2×2**
dans les contrôles de risques simulés. Les courbes se sélectionnent par article,
site et unité ; la chronologie donne état observé, seuil, déclenchement, période
d'effet et délai avant nouveau déclenchement. Les quatre contextes utilisent
les deux suivis de lots habituels et gardent les trois essais complémentaires.
Le nominal et ses 48 blocs de données compressés restent inchangés.

| Résultat vérifié sur 56 jours | Conclusion bornée |
|---|---|
| A : 0, B : 73, C : 0, D : 61 signaux endogènes | Douze groupes supprimés, aucun nouveau ou décalé |
| 9 600 kg non transférés de Gaillac à Gien | La crise a bien un effet physique, malgré l'absence d'effet client dans cette fenêtre |
| Replanification A/B : 27,97784 %, C/D : 28,09108 % | Réaction aux crises programmées ; effet additionnel des réactions d'état nul |
| Production, service et retard clients identiques entre les effets comparés | Aucune amplification client démontrée |
| Aucun lot exposé natif dans les quatre registres | Aucun lien incident-lot n'est inventé pour la comparaison complète courte |

Le coût de transport baisse de 957 696 unités monétaires du modèle parce que
des départs sont empêchés. Cette baisse n'est pas un gain de performance.
Deux déclenchements de capacité sont reconstruits indépendamment : utilisation
de 80 % pendant cinq jours, seuil de 75 %, signal à J30 et effet à J31.

Les douze alertes supprimées ne signifient pas un stock reconstitué. Les quatre
fournisseurs de 021081 gardent chacun 180 kg, dans B comme dans D. À partir de
J36, le besoin amont utilisé par la règle est de 28 608 kg/jour dans B, réparti
à parts égales entre ces fournisseurs, et nul dans D. La couverture dans B est
donc `180 kg / 7 152 kg par jour = 0,025168 jour`. Les trois règles de stock
se déclenchent à J36, J37 et J40 chez chacun des quatre fournisseurs. Dans D,
l'absence de besoin d'ancrage remet les compteurs à zéro. Il s'agit d'un effet
du signal de besoin, pas d'une hausse du stock ni d'une amélioration du service.

Les rapprochements historiques ne compensent pas cet écart différemment sur
56 jours : aucun événement `stock_reconciliation` dans les quatre calculs,
et cinq exports F3/Scan3/protection hebdomadaire strictement identiques. Les
9 290,6 kg de consommation externe résiduelle de Gien/773474 sont exécutés à
l'identique. Les adaptateurs publient les consommations à exécution ou clôture
et modifient des besoins et contraintes MRP, sans imposer une fabrication ou
injecter du stock. Cette conclusion ne transforme pas le rapprochement
historique en rejeu industriel autonome.

La revue comprend 1 743 contrôles CSV, 814 contrôles numériques du payload,
75 contrôles V8 sous DOM/Plotly simulés, deux tests de calcul exacts en mémoire
et doctor. La première candidate publiée a l'empreinte
`ad367f178c711d094f9fc532abfb66179c97ac29dfb5993ac8f52df5bf222c18`.
La [contre-validation](../../artifacts/testing/cascade_etat_20261113/validator/manifest.json)
et le [manifeste de livraison](../../artifacts/testing/cascade_etat_20261113/pilot_delivery_manifest.json)
relient les données, la candidate, la carte écrite et l'archive précédente.

La [reconstruction des alertes supprimées](../../artifacts/testing/cascade_etat_20261113/validator/changed_stock_oracle/manifest.json)
ajoute 466 contrôles indépendants. La comparaison des cinq exports de
rapprochement est conservée dans `historical_reconciliation_readonly_review.json`.

La version finale améliore uniquement la lecture : les 18 règles ont des
libellés métier français et des unités explicites ; les ratios sont affichés
avec leur seuil dans la même unité, et les clés natives restent disponibles
en détail. Les retards programmés sont exprimés en jours, les multiplicateurs
et les fractions de stock séparément. Les valeurs, courbes, quatre contextes,
48 blocs initiaux et trois scénarios complémentaires sont strictement conservés.
La [revue finale](../../artifacts/testing/cascade_etat_20261113/validator/final_readability/manifest.json)
comprend 32 contrôles de préservation et 115 contrôles V8 des affichages concernés.
Empreinte finale :
`8f2d1816a6ed5185485524632b02d1e35ec4f193b0ef9f88f4dc0c2f6330dba1`.
La [livraison finale](../../artifacts/testing/cascade_etat_20261113/pilot_readability_delivery_manifest.json)
conserve aussi l'archive de la première intégration. Aucune donnée annuelle
partielle n'entre dans la carte.

Le gate formel `toolbox/gate-a9d25b4c40384266ac1ea9b406a9f6e5/manifest.json`
reste refusé faute de preuve navigateur et de qualification globale courante.
Ces absences ne sont pas converties en succès par les contrôles ciblés.

## Extension sur 362 jours interrompue

Le portefeuille annuel contient 72 perturbations programmées, dont 44 débutent
après la fenêtre courte. La question d'une extension annuelle est donc de
suivre ces crises, leurs réceptions et leur propagation, avec quatre nouveaux
calculs appariés. Le pilote et sa contre-validation justifient cette extension ;
il ne s'agit pas de forcer une amplification positive.

Les quatre calculs étaient prévus en série sur 362 jours, avec les mêmes paramètres
et 72 crises dans C/D. Aucune ancienne année ni donnée du pilote ne se substitue
aux nouvelles sorties. Le contrôleur conserve les empreintes, les journaux, les
pics mémoire et les résultats partiels ; le premier échec ou dépassement arrête
la phase sans réessai automatique. Budget : quatre heures, 12 Gio de résultats,
un calcul à la fois, plafond mémoire de l'arbre possédé à 4 Gio et garde stricte
de 0,75 Gio de RAM disponible. Le seuil de démarrage a été examiné sur les mesures
locales, sans fermer aucun autre processus. Les décisions et leur révision sont
conservées dans `annual_decision.json` et `annual_decision_v2.json`.

La phase s'est arrêtée sur la garde de RAM disponible pendant A : dernier
jalon confirmé J270/362, après 1 168,69 secondes. La mémoire native a atteint
946 139 136 octets, mais la mémoire disponible de la machine est passée sous
0,75 Gio. Le contrôleur a arrêté uniquement son propre enfant. Aucun refus
d'écriture ni alerte de sécurité n'est identifié dans les journaux examinés.

Le bilan est **un essai annuel tenté, aucun complet, B/C/D non lancés**. Aucun
réessai n'est exécuté. Le CSV MRP partiel de 140,5 Mo est conservé pour diagnostic,
sans être présenté comme un résultat annuel ni comme une preuve de propagation.
Le [manifeste d'arrêt](../../artifacts/testing/cascade_etat_20261113/runner/annual_execution/failure_manifest.json)
et `runner/annual_execution/state.json` conservent les preuves et le point de
reprise. Il faut un budget de mémoire disponible suffisant avant de reprendre
les quatre calculs appariés dans de nouveaux dossiers.

## Limites conservées

- Les crises programmées et les règles d'état sont des hypothèses de stress,
  sans calibration industrielle démontrée.
- La référence courante comprend du rapprochement historique ; les calculs ne
  prouvent pas un rejeu industriel autonome. Les observations restent limitées
  à 2025 et ne deviennent pas des décisions anticipées.
- Les promesses agrégées d'achats MRP appliquent certains effets mais perdent
  leurs identifiants de risque entre commande et lot reçu. Leur départ est
  inconnu : aucun transport exécuté ni identifiant d'expédition n'est inventé.
- Le délai qualité supplémentaire et les observations de délai de cette
  branche demandent des corrections physiques distinctes. La réception et la
  disponibilité après contrôle doivent rester séparées.
- Un signal endogène porte sa propre racine causale. La comparaison des états
  et des quatre cas ne doit pas être présentée comme un arbre natif identifiant
  le parent certain de chaque incident secondaire.
- La qualification globale de C/D a aussi été exécutée sur les sorties actuelles
  de 56 jours : elle reste refusée dans les deux cas. Les écarts sont ceux déjà
  connus : une disponibilité de transfert orpheline, 393 écarts de budget Scan3,
  60 de provenance d'événement, 14 de champs de base et 14 de périmètre alternatif.
  Le manifeste est `toolbox/qualify-68cbe1c31fda4b519c072dcd080b17e5/manifest.json`
  sous le dossier de preuves courant. Les oracles ciblés ne lèvent pas ce refus.
- Les autres réserves de qualification précédentes restent ouvertes. Aucun navigateur,
  Node ou Word n'est relancé après les refus de sécurité antérieurs ; les
  contrôles JavaScript avec DOM simulé ne constituent pas une revue visuelle.

L'étude annuelle de sensibilité précédente est arrêtée après une erreur de
cible de lot physique nulle, sans refus d'écriture ni alerte de sécurité dans
le journal examiné. Ses 35 cas terminés et son essai partiel sont conservés.
Elle n'est pas relancée dans cette mission.
