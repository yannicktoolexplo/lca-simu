# Prévision, stock de sécurité et lancements après le gel

Le contrôle hebdomadaire du stock de sécurité à Muret réduit 10 pics
sur 44 cas comparables en simulation. Seuls deux essais préservent aussi
la couverture des besoins prévus à date et les quatre cibles de stock.
Le signal le plus régulier dans les données industrielles concerne la
première semaine de chaque nouvelle prévision du 268091.
[Cas à explorer](../../resultats/arbitrage_avant_gel_20261121.html) ·
[Preuves et empreintes](../../artifacts/testing/arbitrage_avant_gel_20261121/final_manifest.json)

## Simulé · que déplace le stock de sécurité ?

L’essai conserve les besoins prévus à leurs dates, les stocks et
engagements datés, les tailles de lot, les délais et les gels de 4
semaines à Avène et 8 semaines à Gien. À Muret, la cible de sécurité
issue du scénario est appliquée chaque samedi, puis au dernier jour
couvert. Le retrait de la sécurité sert aussi de diagnostic distinct.
Le pic mesure la plus forte quantité proposée au lancement sur une
journée dans les 28 premiers jours révisables, sans plafond de capacité.

| Revue simulée | Pic journalier proposé, en unités | Plus fort manque supplémentaire projeté à Muret | Cibles du samedi atteintes |
| --- | ---: | ---: | ---: |
| 268091 · 27 janvier | 259 200 → 230 400 | +187 200 | 0 sur 4 |
| 268091 · 28 avril | 345 600 → 259 200 | 0 | 4 sur 4 |
| 268967 · 23 mars | 107 800 → 0 | 0 | 4 sur 4 |

Le manque mesure la dégradation maximale du solde journalier envers
les besoins prévus, avec des arrivées à Muret conditionnées aux dates
usine, au transport et au contrôle du scénario. Les quatre samedis
sont vérifiés dans les 28 jours à compter de la première arrivée
possible après le gel. En janvier, le premier manque additionnel
apparaît le 17 mars. Le zéro du 23 mars porte sur les lancements
proposés dans la fenêtre étudiée. Les livraisons clients réelles et la
faisabilité en atelier restent à établir à partir de leurs journaux.

Les 44 revues hebdomadaires retrouvent les propositions du dépôt.
À l’usine, le contrôle de la fenêtre utile concorde pour 42 de ces
44 revues et pour les deux dates de clôture ciblées. Les revues de Gien
du 6 avril et du 4 mai sont écartées du verdict. Un calcul indépendant
reproduit les séries et le verdict sur les 46 cas.
[Calculs](../../artifacts/testing/arbitrage_avant_gel_20261121/review_results.json) ·
[Oracle](../../artifacts/testing/arbitrage_avant_gel_20261121/validation/saturday_checkpoints_independent.json)

Dans les 304 revues de clôture du scénario archivé, dix regroupent
plusieurs lots le premier jour révisable. La marge de planification de
trois jours retrouve leurs dates de disponibilité prévues à Muret.
Une fin physique le jour du lancement donnerait une autre date pour
les dix cas. La durée physique reste inconnue. À Gien, les trois lots
de 107 800 prévus pour le 26 mai ont tous été annulés avant le début
de fabrication dans le scénario.
[Journaux de simulation](../../artifacts/testing/arbitrage_avant_gel_20261121/execution_traces.json)

## Industriel · la prévision change pour la même semaine

Sur 42 comparaisons de versions à 4 et 8 semaines, onze paires à
quatre semaines par produit permettent de suivre la même semaine
cible lorsqu’elle devient le premier point de la nouvelle version.
Les onze valeurs augmentent pour le 268091 et s’éloignent de la
demande observée. Elles diminuent toutes pour le 268967.

| Revue du 268091 | Ancienne prévision sur quatre semaines | Nouvelle prévision | Demande observée |
| --- | ---: | ---: | ---: |
| 27 janvier | 475 174 | 823 213 | 310 382 |
| 28 avril | 790 107 | 1 116 286 | 299 716 |

Répartir le même volume sur quatre semaines laisse inchangée la somme
des écarts hebdomadaires absolus pour ces deux épisodes. Dans le
scénario, le calcul de fin de mois explique aussi une amplification
du rythme quotidien. À budget mensuel constant, ce rythme augmente
dans 20 revues sur 20 pour le 268091 et 12 sur 20 pour le 268967.
La demande observée ultérieure sert uniquement à évaluer les versions.
[Prévisions et cellules source](../../artifacts/testing/arbitrage_avant_gel_20261121/source_cases.json)

## Industriel · la souplesse dépend de l’horizon

Sur 184 fenêtres du MRP de Muret, le stock physique inscrit dans
l’export couvre les besoins projetés sans nouvelles réceptions
prévues dans les proportions ci-dessous. Le calcul cumule les stocks
physiques renseignés et les besoins, puis les réceptions pour retrouver
le solde exporté. Il mesure la couverture au sens du plan publié.

| Produit | Quatre semaines | Huit semaines |
| --- | ---: | ---: |
| 268091 | 20 sur 48 | 1 sur 44 |
| 268967 | 38 sur 48 | 30 sur 44 |

Pour le 268091, la version du 20 juillet garde 126 635 unités au point
bas des quatre premières semaines sans ces réceptions. À huit semaines,
le solde devient négatif à partir du repère du 24 août. Dans les versions
des 17 et 24 août du 268967, 107 800 unités de réception planifiée
passent du repère du 28 septembre à celui du 5 octobre, à besoin et
stock physique renseignés identiques sur ces deux lignes. Le plan
affiche encore 106 612 unités au 28 septembre. L’identifiant du lot et
la date de transfert effective manquent pour prouver le report physique.
[Versions et cellules MRP](../../artifacts/testing/arbitrage_avant_gel_20261121/source_cases.json)

La priorité est de faire confirmer le sens du champ `Forecasted Demand`
en première semaine et de rapprocher les échéances clients fermes des
disponibilités datées à Muret. La sécurité hebdomadaire reste une piste
pour les situations dont la couverture est démontrée. Les règles du
nominal restent celles du scénario de référence. L’analyse réemploie
un scénario qualifié de 152 jours et les observations de 2025.
Les fenêtres industrielles se recouvrent. Elles décrivent cet historique.
