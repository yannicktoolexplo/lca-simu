# Quels engagements couvrent déjà le 268091 avant le gel ?

Le même rapprochement a été testé à la clôture du **27 janvier** et
du **28 avril 2025**. Le plan reprend exactement les dates, quantités
et engagements du témoin qualifié sur sa fenêtre utile. La première
date révisable reste le 24 février puis le 26 mai. Les 95 reports
de l’essai précédent détérioraient tous la couverture en usine.
Cette fois, le calcul teste si le besoin diminue lorsqu’on affecte
une seule fois les engagements déjà présents.
[Protocole](../../artifacts/testing/couverture_avant_gel_20261121/protocol.json)

## Ce qui est déjà compté

| Quantité dans le scénario, en unités | 27 janvier | 28 avril |
| --- | ---: | ---: |
| Stock utilisable à D1920 en fin de journée | 250 796 | 552 827 |
| Stock déjà arrivé et en contrôle à D1920 | 139 660 | 531 795 |
| Expéditions encore en transit vers D1920 | 0 | 158 400 |
| Stock utilisable et encore à D1810 | 0 | 0 |
| Stock déjà conditionné et en contrôle à D1810 | 98 315 | 178 590 |
| Ensemble des engagements crédités dans le plan d’D1810 | 1 806 055 | 887 370 |

En janvier, les 139 660 unités en contrôle à D1920 proviennent de
la ligne d’ouverture 75, fractionnée en deux transferts. Les 10 060
du deuxième transfert passent du transit au contrôle le 27 janvier et
gardent le même crédit daté. En avril, cinq lots totalisant 158 400
unités sont expédiés le 28. Ils sortent du calcul d’D1810 et entrent
une seule fois à D1920, où ils sont utilisables le 14 mai dans le
scénario. Le journal ne montre aucun stock utilisable à D1810 laissé
sans expédition à la clôture de ces deux jours.

Les 98 315 unités encore retenues à D1810 en janvier viennent des
lignes d’ouverture 72 et 82. En avril, les 178 590 se répartissent en
36 795 et 141 795 unités, lignes 87 et 74. En appliquant deux jours
de trajet puis dix jours ouvrés de contrôle au dépôt, les premières
disponibilités calculées à D1920 sont le **21 février** en janvier,
et les **16 et 30 mai** en avril. Le plus gros apport d’avril arrive
ainsi à disponibilité après la date de couverture du 29 mai. Ces
dates appartiennent au scénario et restent conditionnelles au
départ prévu et aux jalons de contrôle.
[Stocks, engagements et identités](../../artifacts/testing/couverture_avant_gel_20261121/commitment_coverage.json)

## Le test conserve les quantités entre les deux sites

| Variante locale | Quantité lancée le 24 février | Quantité lancée le 26 mai |
| --- | ---: | ---: |
| Témoin | 259 200 | 345 600 |
| Réserver à D1920 le stock en contrôle et le retirer du crédit d’D1810 | 259 200 | 345 600 |
| Garder le crédit d’D1810 et ajouter une obligation d’expédition de même volume | 259 200 | 345 600 |
| Affecter tout le carnet d’ouverture une seule fois à D1920 | 259 200 | 345 600 |
| Affecter toutes les positions fermes d’D1810 une seule fois | 259 200 | 345 600 |
| Cas de contrôle volontairement invalide avec double crédit des stocks en contrôle | 158 400 | 172 800 |

La réservation du stock retenu réduit les nouveaux besoins proposés
à D1920 de **98 315 et 178 590 unités**. Le volume de fabrication
calculé à D1810 demeure identique. En avril, l’obligation d’expédition
fait passer le nombre de lots de onze à neuf le même jour, toujours
pour 345 600 unités. L’affectation et l’arrondi changent le découpage.
Le volume journalier reste le bon indicateur.

Affecter tout le carnet à D1920 relève d’une hypothèse plus large.
En janvier, le solde usine à la première date de disponibilité passe
de −1 402 636 à +19 714 unités sous cette hypothèse, avec toujours
259 200 concentrées le premier jour. En avril, **36 795 sur 440 970**
unités du carnet peuvent devenir utilisables à D1920 d’ici au 29 mai.
Les exports industriels donnent les quantités et les besoins
hebdomadaires. Ils ne permettent pas d’identifier un bon de transfert
ferme pour ces quantités à la date de revue.
[Contre-vérification indépendante](../../artifacts/testing/couverture_avant_gel_20261121/validation/disjoint_commitments_independent.json)

## Deux facteurs séparent encore plan et exécution

**État du stock au dépôt.** Le 27 janvier, le plan industriel avant
la journée rapporte 435 433 unités courantes et 57 600 futures, sur
une photo de 534 829. Le 28 avril, il rapporte 540 963 courantes et
271 530 futures, sur 819 138 physiques. En prenant ces catégories
comme hypothèses d’utilisation au début de la journée, puis en
appliquant les départs simulés du jour, le pic baisse à **244 800**
en février et monte à **691 200** en mai. Les deux bornes testées
pour le jour de libération dans chaque semaine donnent les mêmes
résultats. Les résidus de 41 796 puis 6 645 unités restent séparés.
Cette sensibilité mesure le poids du partage courant/futur.

**Prévision et sécurité.** À stocks et engagements constants, garder
la prévision précédente, celle du 30 décembre ou du 31 mars,
ramène le volume du premier jour à **zéro puis 28 800**. Dans un
contrôle séparé, neutraliser le plancher de sécurité ramène ce
volume à zéro aux deux dates. Le maximum journalier sur les quatre
premières semaines hors gel vaut alors 57 600 dans chaque épisode.
Le cumul sur ces quatre semaines diminue aussi, de 921 600 à 259 200
puis de 907 200 à 345 600. Les besoins clients projetés restent
présents. En mai, avec les seuls
engagements existants, le calcul laisse un manque projeté de **307 762**
unités à D1920 le 29 mai, avant le plancher de sécurité de **658 153**.
Les volumes sont ceux de la prévision connue à la décision. La
fabrication et le service réalisés restent des mesures distinctes.
[Stocks et prévision](../../artifacts/testing/couverture_avant_gel_20261121/validation/source_sensitivities_independent.json) · [Effet du plancher de sécurité](../../artifacts/testing/couverture_avant_gel_20261121/validation/safety_ablation_independent.json)

La concentration ne se résout donc pas par une règle commune de
réservation des flux existants. La question restante porte sur la
distinction, avant le gel, entre les quantités à livrer à une date
promise, les prévisions encore révisables et le stock de protection
à reconstituer. Les sécurités sources restent celles de la référence.
Les variantes de prévision et de sécurité servent à attribuer le pic.
Les résultats proviennent de calculs locaux en mémoire sur les
états qualifiés. Les contrôles indépendants recoupent 120 valeurs
sur la réservation des engagements, 42 sur l’état du dépôt et
la prévision, et 14 sur l’effet du plancher de sécurité.
[Manifeste des preuves](../../artifacts/testing/couverture_avant_gel_20261121/final_manifest.json)
