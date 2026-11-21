# Disponibilité début mars et besoin MRP du 16 juin

La simulation du 268091 fait arriver **544 100 unités à D1920 du 3
au 9 mars** et les garde en contrôle. Sur la même semaine, le stock
physique industriel diminue de **50 622 unités**. Le budget de
prévision ne suffit plus à expliquer cet écart. Il faut vérifier
les dates de transfert, de réception et de libération. En juin,
la hausse du besoin MRP se produit alors que la prévision commerciale
est inchangée pour la semaine cible.
[Cas à explorer](../../resultats/jalons_mars_besoins_juin_20261121.html) ·
[Preuves](../../artifacts/testing/jalons_mars_besoins_juin_20261121/final_manifest.json)

## Mars · le stock physique diverge avant le stock utilisable

Le tableau utilise les fins de dimanche simulées et les repères
industriels du lundi suivant. L’heure de prise des photos n’est pas
documentée. En comparant plutôt les fins de lundi, le signe de
l’écart change de la même façon.

| 268091 à D1920, en unités | Ouverture du 3 mars | Ouverture du 10 mars | Variation |
| --- | ---: | ---: | ---: |
| Stock physique industriel | 590 626 | 540 004 | −50 622 |
| Stock physique simulé | 486 585 | 935 531 | +448 946 |
| Écart simulé moins industriel | −104 041 | +395 527 | +499 568 |

Dans la simulation, **294 895 unités reçues** proviennent de trois
positions du carnet initial d’D1810, et **249 205** des nouvelles
fabrications. Le dépôt expédie **95 154 unités** le 3 mars et les
clients les reçoivent le 5 mars. Aucune des 544 100 unités arrivées
entre-temps n’est utilisable dans cette semaine. Le stock disponible
à D1920 est de **264 636 unités** du soir du 3 au soir du 9 mars.
Retirer par calcul les seules nouvelles arrivées encore en contrôle
laisserait un écart physique de **146 322 unités** au 10 mars, à
sorties identiques. C’est une décomposition du bilan et du rôle
des deux origines dans le simulateur.
[Bilans et lots d’origine](../../artifacts/testing/jalons_mars_besoins_juin_20261121/receipt_gap.json)

Le bilan industriel du 3 au 9 mars donne une variation nette de
mouvements de **−79 405** et **−17** d’ajustement. Il reste **+28 800
unités non expliquées** entre les deux photos. La semaine suivante
ferme exactement. Le carnet prévoit les 294 895 unités à D1810 aux
3, 5 et 6 mars. Les destinations et dates d’arrivée effectives de
ces lots ne sont pas identifiables dans les fichiers.
[Cellules industrielles](../../artifacts/testing/jalons_mars_besoins_juin_20261121/observed/march_industrial.json)

## Mars · quels retards exposent la demande ?

Du carnet connu au 27 janvier, quatre positions alimentent le
stock utilisable à D1920 avant le 10 mars dans la simulation.
Les quantités ont été suivies sur cinq expéditions, y compris dans
les réceptions qui regroupent plusieurs positions.

| Lignes du carnet d’D1810 | Utilisables à D1920 en simulation | Quantité |
| --- | --- | ---: |
| 72 et 82 | 21 février | 98 315 |
| 78 et 80 | 28 février | 158 595 |

Les **16 combinaisons de retard de 14 jours** ont été testées sur
deux conventions de datation de la demande. Sur les jours d’effet
reconstitués, les groupes minimaux sont **72, 78 et 82** et
**78, 80 et 82**. Décaler les quatre positions produit un
manque maximal de **28 713 unités** à partir du 4 mars, sur trois
jours. Aucun test ne crée de manque quand la demande hebdomadaire
est comptabilisée le lundi suivant. Le retard touche les dates
de disponibilité hypothétiques et conserve les quantités.
[32 essais et chemin des lots](../../artifacts/testing/jalons_mars_besoins_juin_20261121/march_lots.json) ·
[Contre-calcul indépendant](../../artifacts/testing/jalons_mars_besoins_juin_20261121/validator/march_independent_complete.json)

Dans les données industrielles, D1920 classe **358 444 unités** du
268091 en stock courant le 3 mars. La demande historique totalise
**173 158 unités** sur les deux semaines du 3 et du 10 mars.
Si **48,31 %** au moins du stock classé courant était mobilisable
au départ pour cette demande, elle aurait été couverte sans aucun
nouvel apport ni autre obligation. Pour le 268967, le seuil est de
**9,18 %**. Les montants de CA perdu du 4 au 10 mars sont
respectivement **7 971,10** et **12 220,60**. Ils appartiennent à un
périmètre financier et ne donnent pas le nombre d’unités en retard.

## Juin · le besoin est révisé avec les réceptions prévues

Pour la semaine du **16 juin**, la prévision commerciale du 268091
reste à **304 904 unités** entre les deux versions MRP. L’historique
indique **76 689 demandées**. Le besoin MRP de la même semaine passe
de **73 218 à 874 805 unités**.

| Écart de la nouvelle version à l’ancienne, en unités | Besoin | Réceptions prévues | Stock de départ pris en compte | Solde prévu en fin de première semaine |
| --- | ---: | ---: | ---: | ---: |
| 268091, 16 juin | +801 587 | +400 913 | +269 721 | −130 953 |
| 268967, 29 septembre | +364 920 | +232 286 | +124 779 | −7 855 |

La première réception du plan du 268091 avance du **14 juillet au
16 juin**. La version prévoit **400 913 unités d’entrée** le 16 juin.
Le solde prévu reste positif à **417 575 unités** cette semaine et
dépasse l’ancienne projection de **162 768** à quatre semaines.
Sur les **50** comparaisons du 268091 à date cible fixe, le premier
besoin et les réceptions de cette semaine augmentent ensemble.
Dans **39** de ces comparaisons, la prévision commerciale utilisée
pour la même date est identique. Les tests avec quatre ou cinq
semaines de sécurité calculées échouent à expliquer les sauts.
[Rapprochement des versions](../../artifacts/testing/jalons_mars_besoins_juin_20261121/mrp/rebase_mrp_final.json) ·
[Cellules vérifiées](../../artifacts/testing/jalons_mars_besoins_juin_20261121/mrp/anchor_xml_check.json)

La priorité industrielle porte sur deux extraits. Pour mars, suivre
les transferts d’D1810 de l’ordre initial à la libération réelle à
D1920 et les départs affectés aux échéances du 4 au 10 mars. Pour
juin, ventiler les 874 805 unités par type de besoin et échéance
avant/après, puis identifier les lignes qui forment les 400 913
réceptions prévues. Les 5 282 lignes disponibles des deux produits
sont des agrégats de D1920. Les essais utilisent les sources et
les journaux qualifiés du scénario archivé. La référence est conservée.
