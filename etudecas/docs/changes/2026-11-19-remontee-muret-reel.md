# Remonter les mouvements de Muret jusqu'à l'usine et aux composants

L'explorateur suit les références 268967 et 268091 sur 2025. Choisir un
produit puis une semaine sur le graphique permet d'ouvrir le bilan de
Muret, la demande commerciale et les versions du MRP. Le parcours
continue vers l'atelier et les composants de sa nomenclature. Pour un
composant, on peut lire les entrées, les sorties enregistrées pour le
périmètre des références étudiées, les autres sorties, le stock, les plans
et les lignes du carnet partiel. Les liaisons documentées montrent le
contexte amont.
[Ouvrir l'explorateur](../../resultats/remontee_muret_reel_20261119.html)

Les 53 périodes de chaque produit incluent les deux semaines à cheval sur
le début et la fin d'année. Le conditionnement estimé est renseigné sur
36 semaines pour 268967 et 46 pour 268091. Sur les 51 comparaisons de stock
possibles par produit, le bilan ferme exactement dans 46 cas pour 268967
et 38 pour 268091. Les autres semaines affichent leur résidu.

Les mouvements sont signés et suivent le repère hebdomadaire du
classeur. Le changement de stock correspond au total des entrées,
sorties et ajustements enregistrés, avec un résidu lorsque les quantités
ne se recoupent pas. Le mouvement appelé « Sorties » à Muret inclut des
variations nettes de stock. Les départs clients bruts et les identifiants
d'expédition manquent. Dans les deux séries de Muret, 43 lignes ont
une « Sortie » positive alors que l'entrée enregistrée vaut zéro.
Chaque rapprochement affiche ses cellules, sa
période et sa nature. Les versions MRP demeurent des plans connus à une
date. Les semaines absentes conservent le statut inconnu.

## Pourquoi 268967 semble fabriqué progressivement en mars

Les prélèvements d'étuis à 1430 s'étalent sur trois semaines. Le plan
d'étuis du 16 mars prévoit 110 495 unités. La version suivante en
reporte 61 245. La version du 30 mars en reporte 1 245. Les deux baisses
sont exactement égales aux prélèvements des deux premières semaines.

| Semaine du lundi | Étuis prélevés | Autre emballage 730384, mètres prélevés | Mètres théoriques pour les étuis de la semaine |
| --- | ---: | ---: | ---: |
| 17 mars | 49 250 | 12 452 | 10 441 |
| 24 mars | 60 000 | 10 500 | 12 720 |
| 31 mars | 5 080 | 1 310 | 1 076,96 |
| Total | 114 330 | 24 262 | 24 237,96 |

Le rapprochement de 730384 est à **24,04 mètres près** sur trois semaines
avec la nomenclature de 0,212 mètre par unité. Les répartitions
hebdomadaires diffèrent. Cela soutient un programme de conditionnement
suivi sur plusieurs semaines et des dates de prélèvement différentes selon
le composant. La baisse du besoin MRP porte sur une quantité planifiée
agrégée. Elle peut correspondre à un lot progressif, à plusieurs lots
ou à des écritures de prélèvement décalées par rapport au travail.

Les photos d'étuis passent de 400 250 à 351 000, puis 291 000 unités.
Les prélèvements expliquent ces baisses. Les photos ne montrent donc
aucun épuisement du stock physique d'étuis. Les disponibilités qualité,
les heures de travail et les identifiants d'ordre à l'origine des
consommations restent inconnus. Ces fichiers hebdomadaires ne
permettent pas d'identifier la cadence quotidienne ni de choisir entre
un découpage de l'atelier, une pause machine ou un décalage d'écriture.
Preuves dans les mouvements `J854:J856` et `J1162:J1164`, dans les plans
d'étuis `I10633,I11664,I12684` et dans `268967.xlsx / BOM`.

## Deux remontées vérifiables

**268967, du 17 mars au 6 avril.** Sous hypothèse de demande servie la
semaine où elle est comptée, les apports à Muret impliqués par le
bilan sont 40 824, 63 504 et 5 920 unités. Leur somme de 110 248
correspond au stock physique déclaré à disponibilité future dans le
MRP du 6 avril. Ce stock est déjà physique dans le plan et se
libère à une date ultérieure. Les 114 330 étuis donnent un ordre de
grandeur compatible sur ces semaines. Aucun export ne permet
d'apparier ces quantités à des identités de lots industriels.

Sur la première semaine, l'entrée de 773474 à 1430 est de **3 200 kg**.
Gaillac enregistre une sortie de **3 200 kg** sur la liaison documentée.
Cette concordance rend le transfert plausible. À Gaillac, le total des
mouvements serait de +3 200 kg, mais ses photos restent à 12 800 kg,
soit un écart de bilan de −3 200 kg. Il faut conserver cet écart
et les autres mouvements. À 1430, les prélèvements pour le périmètre
étudié de 773474 sont à zéro cette semaine puis atteignent **2 113,4 kg**
la suivante, pendant que les étuis sont prélevés sur les deux semaines.
Le stock photographié de semi-fini est supérieur à 17 tonnes sur
ces bornes. La disponibilité et l'affectation au travail restent
distinctes. Preuves des mouvements `G1246:J1247`, `G1289:J1289`,
et de la liaison dans `Data_poc.xlsx / Relations_acteurs A9:C9`.

**268091, semaine du 13 octobre.** Le stock de Muret passe de
919 902 à 918 532 unités. La baisse de 1 370 se décompose exactement
en un ajustement de −435 et un mouvement net de −935. La demande
commerciale est de 72 428 unités. Les −935 ne permettent pas de mesurer
la part livrée. Ce cas montre pourquoi la remontée commence par le
bilan et conserve l'hypothèse de service à part. Preuve des mouvements
`G785:J785`.

L'hypothèse de demande servie peut aussi aboutir à un apport net négatif.
C'est le cas le 22 décembre pour 268967 (−13 608 unités), et le 16 juin
pour 268091 (−6 611). Ces valeurs restent signées et signalent que
la demande ne suffit pas à isoler les réceptions physiques.

Les champs qui permettraient de conclure sur la cause de l'étalement
sont l'identifiant de l'ordre de fabrication et les dates réelles de
lancement, de prélèvement, de fin, de transfert et de libération.
Pour le service client réel, il faut les départs et réceptions bruts
avec quantités et dates. Le parcours reste une enquête de flux au
niveau article, site et semaine.

## Reproduction

L'extraction réutilise le dossier des données reliées du 12 novembre
après rapprochement de ses empreintes avec les classeurs locaux. Elle lit
directement les nomenclatures et contrôle des cellules sources. Pour
ouvrir une nouvelle livraison avec ses fichiers de preuve, choisir
des destinations neuves sous le dépôt.

```powershell
python -B -m etudecas.analysis.from_simulation.build_muret_real_trace --output <dossier_donnees>
python -B -m etudecas.visualization.maps.build_muret_real_trace --dataset <dossier_donnees>/muret_trace.json --output <page.html> --manifest <preuve_page.json>
```

Les 106 fiches semaine-produit et les tables des 30 couples article-site
ont été recalculées et rapprochées des classeurs en lecture seule.
La contrelecture source totalise 693 841 contrôles. Les 31 contrôles
de navigation ont été exercés en V8 sur un DOM simulé.
[Manifeste de livraison](../../artifacts/testing/remontee_muret_reel_20261119/final_manifest.json)
