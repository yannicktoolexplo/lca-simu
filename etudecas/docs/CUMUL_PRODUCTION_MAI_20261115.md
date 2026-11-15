# Cumul de production en mai et application au second produit

Étude du 15 novembre 2026, code témoin `fdf42fd257e2a2b62a554b0b65ae3570eece7b70`.
La référence nominale est conservée. Cette étude distingue un défaut de graphique
d'une limite de la règle expérimentale de programme usine.

[Comparaison interactive](../resultats/cumul_production_mai_20261115.html) ·
[Protocole fixé avant essais](../artifacts/testing/cumul_mai_20261115/protocol.json) ·
[Preuves finales](../artifacts/testing/cumul_mai_20261115/final_manifest.json).

## Ce que mesure la courbe

Le réel est une **production estimée à partir des retraits d'étuis** : composant
333362 à 1430 pour 268967, composant 338929 à 1810 pour 268091. La nomenclature
compte un étui par unité de produit. Cela ne donne pas directement la date de
fin de fabrication ou de libération d'un lot.

La série simulée comparable est donc la consommation physique d'étuis du
produit, conditionnement des ordres initiaux inclus, usages externes exclus.
Le rapport distingue également travail nouveau, lots achevés, réception au
dépôt, disponibilité et réceptions clients. Une allocation MRP n'est pas une
consommation physique.

Une semaine source absente reste inconnue. Le cumul comparable additionne
uniquement les semaines complètes connues, **les mêmes dans les deux séries**.
Ce n'est pas un cumul industriel complet depuis janvier. Le cumul calendaire
simulé contient tous les jours calculés, y compris la dernière semaine partielle.

## Défaut de graphique corrigé

L'ancien graphique plaçait au lundi le cumul acquis à la fin du dimanche suivant,
soit six jours trop tôt. Il ne présentait que les semaines complètes : les
fabrications simulées du 12 au 15 mai n'apparaissaient pas dans le calcul de
135 jours terminé le 15 mai.

Pour 268091, les CSV donnent :

| Périmètre du témoin de 135 jours | Étuis simulés consommés |
|---|---:|
| Jusqu'au 11 mai, semaines comparables | 2 351 136 |
| Du 12 au 14 mai, hors dernière semaine complète | 256 980 |
| Tous les jours jusqu'au 15 mai | **2 608 116** |

Les ordres initiaux sont inclus : 1 945 715 unités conditionnées dans le total,
dont 141 780 le 12 mai. Aucune production perdue dans le moteur n'est démontrée
par cet écart d'affichage.

Le nouveau rapport date le cumul comparable au dimanche et propose séparément
le cumul simulé complet. Le clic donne la semaine, les lots, les composants et
les décisions disponibles. Les archives antérieures restent inchangées.

Contre-calcul indépendant :
[22 contrôles du rapport historique corrigé](../artifacts/testing/cumul_mai_20261115/validator/cumulative135_review.json).

## Pourquoi 268967 s'arrête après le 27 avril dans le témoin

Les deux campagnes de 107 800 unités finissent les 30 mars et 27 avril.
Après la seconde, aucun travail engagé ne reste en attente de composant.
Le cumul simulé reste donc à **215 600 unités** jusqu'au 15 mai.

Dans la règle expérimentale, un nouveau lot doit respecter les budgets de
consommation de composants connus pour la semaine courante. Les versions de
`Flow_Data_MRP_results.xlsx`, onglet `Feuille1`, donnent :

| Version connue | 333362, étuis | 730384, mètres | Conséquence pour un lot de 107 800 |
|---|---:|---:|---|
| 13 avril | 176 711 — I14657 | 37 462,52 — I14897 | Un lot engagé le 14 avril sur ce budget ; reliquat insuffisant pour un second |
| 20 avril | 0 — I15657 | 0 — I15921 | Zéros explicites |
| 27 avril | 16 188 — I16692 | 5 018,75 — I16948 | Budget insuffisant |
| 4 mai | 0 — I17705 | 0 — I17958 | Zéros explicites |
| 11 mai | 0 — I18700 | 0 — I18952 | Zéros explicites |
| 18 mai | 110 495 — I19704 | 23 424,94 — I19966 | Compatible avec un lot, sous autres conditions |

Après déduction du lot engagé le 14 avril sur le budget connu le 13 avril,
il reste 68 911 étuis et
14 608,92 mètres : pas de deuxième lot entier autorisable perdu pendant
l'exécution de la première campagne. Cette explication concurrente est réfutée
sur la fenêtre examinée.

Le composant 344135 impose une autre limite : le 20 avril, 66 100 unités
utilisables couvrent 53 900 unités de travail restant, laissant 12 200 unités
libres. Son stock utilisable ne remonte à 372 200 que le 9 mai. Cette contrainte
aurait limité un lancement supplémentaire ; elle n'explique pas à elle seule
le plateau, puisque la règle de programme n'autorise alors aucun nouveau lot.

Le 28 avril, une proposition de 107 800 existe encore le matin ; après révision
des besoins, le plan du soir la reporte au 10 juin. Le plan du 15 mai la place
au 22 juin. Ce sont des **propositions futures**, pas des fabrications exécutées.

Le réel estimé donne 15 500 unités pour la semaine du 28 avril, puis les semaines
du 5 et du 12 mai sont absentes. Au dernier point connu, fin du 4 mai, le cumul
comparable est **295 750 unités réelles estimées contre 215 600 simulées**,
soit **−80 150 unités, −27,10 %**. Le défaut de graphique n'efface pas cet écart.

Les budgets MRP sont des prévisions de consommation, **pas des ordres de
fabrication fermes identifiés**. Leur utilisation comme autorisation est une
hypothèse de rapprochement historique. Le plateau du simulateur ne prouve
donc pas un arrêt industriel.

## Ce qui est déjà commun à 268091

Le reliquat mensuel recalculé chaque semaine et le placement des lots sous
capacité finie s'appliquent aux deux produits. La correction des promesses avec
composants de remplacement est générique, mais aucune transition configurée
ne concerne les emballages de 268091.

Le programme d'autorisation du témoin ne couvrait que 268967. L'essai ajouté
pour 268091 utilise ses propres budgets 338928/338929, sa capacité déclarée
203 550 unités/jour, ses lots : minimum 28 800, multiple 14 400, maximum déclaré
142 485, soit un plus grand lot réalisable de 129 600. La cadence hypothétique
7 700 unités/jour de 268967 n'est pas copiée.

Une limite est identifiée avant calcul : la sélection d'un programme refuse
tout nouveau lot tant qu'un ordre initial de conditionnement du produit reste
en attente. Pour 268091, ces engagements vont jusqu'au 12 mai. Cette protection
contre le double comptage peut aussi bloquer des fabrications légitimes ; il
faut mesurer cette dégradation, sans supprimer les engagements initiaux.

Deux essais natifs de 152 jours, jusqu'au 1er juin inclus, comparent le programme
de 268967 seul à celui des deux produits. Les graphes ne diffèrent que par
l'ajout de 52 versions connues pour 268091. Le moteur reste inchangé.

Avant lancement, 28 contrôles en mémoire et 14 contrôles des entrées passent,
dont le rapprochement de 104 cellules Excel. Un premier lecteur avait refusé
les unités `ZUN` face à `UN` ; la normalisation source documentée a été corrigée
dans le lecteur, sans modifier aucune quantité. Le refus initial est conservé.

[Oracle des entrées](../artifacts/testing/cumul_mai_20261115/validator/input_and_memory_review_v2.json) ·
[Oracle en mémoire](../artifacts/testing/cumul_mai_20261115/validator/memory_review.json) ·
[Extraction de contexte](../artifacts/testing/cumul_mai_20261115/may_context.json).

## Résultats des deux essais de 152 jours

Les deux calculs terminent sans erreur, en 511,44 et 512,73 secondes, avec
662 fichiers source inchangés. Le préfixe de 135 jours du témoin reproduit les
sorties physiques précédentes : prolonger l'horizon n'a pas réécrit le passé.

| Produit / même couverture réelle | Réel estimé | Programme 268967 seul | Programme des deux produits |
|---|---:|---:|---:|
| 268967 — 13 semaines connues | 402 500 | 323 400 ; **−19,65 %** | 323 400 ; **−19,65 %** |
| 268091 — 21 semaines connues | 2 409 100 | 3 040 116 ; **+26,19 %** | 2 104 115 ; **−12,66 %** |

Le troisième lot de 268967 commence bien le **19 mai** et s'achève le **1er juin**,
107 800 unités fabriquées en 14 jours. La reprise vient de l'autorisation
connue le 18 mai, avec un lot proposé et des composants disponibles. Cela
confirme le mécanisme du simulateur, pas le calendrier industriel exact.

Pour 268091, le programme autorise **129 600 unités le 19 mai**, puis **28 800
le 26 mai**. Le travail nouveau passe de 1 094 400 à 158 400 unités ; les ordres
initiaux totalisent toujours 1 945 715 unités. La règle réduit donc les nouveaux
lancements de 85,53 %, sans supprimer les engagements initiaux.

Mais l'erreur hebdomadaire moyenne par rapport au réel estimé ne baisse que de
**91 346,19 à 90 377,38 unités : −1,06 %**. Le rapprochement du volume total
reste donc très insuffisant pour valider le calendrier. Les semaines avec
production simulée passent même de 16 à 14, contre 18 observées parmi les
21 semaines connues. La capacité propre à 268091 reste inchangée ; le programme
ne crée pas une fabrication quotidienne étalée sur quatre semaines.

Un ordre initial avance : les 120 600 unités de la ligne source 83 sont toutes
conditionnées le 29 avril, au lieu du 29 avril au 1er mai. Le composant 338928
dispose ce jour-là de 325 618 unités utilisables dans la variante contre 50 000
dans le témoin. L'identité et la quantité de l'ordre sont conservées ; ses dates
physiques ne sont donc pas strictement identiques entre scénarios.

### Conséquences en aval au 1er juin

| 268091 au dépôt 1920 | Programme 268967 seul | Programme des deux produits |
|---|---:|---:|
| Stock physique | 1 972 785 | 1 036 785 |
| Stock utilisable | 1 367 010 | 736 605 |
| Stock en contrôle | 605 775 | 300 180 |
| Réceptions clients simulées cumulées | 1 475 611 | 1 475 611 |

Les départs clients cumulés restent à 1 497 868 unités, avec 22 257 unités en
transit final. La baisse de production est absorbée par le stock : aucune
dégradation supplémentaire du service n'est observée dans cette fenêtre.
Cela ne prouve pas que le service industriel réel est reproduit.

Les séries de production et de service de 268967 sont identiques entre
variantes : aucun effet de couplage entre produits n'est constaté ici.

## Décision et prochain test utile

**La correction d'affichage est retenue. L'autorisation appliquée à 268091
reste un essai, sans promotion dans le nominal.** Elle améliore fortement le
biais de volume mais presque pas le rythme hebdomadaire. Les budgets de
composants ne doivent pas être assimilés à des ordres fermes démontrés.

Le prochain point à résoudre est la coexistence des ordres initiaux et des
fabrications nouvelles : rapprocher leurs identités, quantités restantes,
consommations déjà réalisées et périodes de besoin avant de remplacer le
blocage global par une déduction locale. Le test attendu devra autoriser un
nouveau lot réellement non couvert, conserver chaque engagement et refuser
tout double comptage. Il ne consiste pas à copier la cadence de 268967 ou à
ajuster une capacité semaine par semaine pour suivre les points réels.

Pour 268967, la cadence constante de 7 700 unités/jour reste insuffisante pour
expliquer une semaine réelle estimée à 94 000 unités. Dates des opérations,
charge machine partagée et dates de retraits d'étuis doivent départager une
cadence variable d'une comptabilisation regroupée.

Les vérifications indépendantes, les refus conservés et leurs limites sont
rassemblés dans le manifeste final. Aucun navigateur n'a été exécuté. Les
refus de qualification globale restent distincts de la réussite des calculs
ciblés ; aucune validation scientifique complète n'est annoncée.
