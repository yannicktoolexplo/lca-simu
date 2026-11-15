# Ordres initiaux, besoins non couverts et courbes complètes

Étude du 15 novembre 2026, témoin `REV-0373`.

[Rapport interactif retenu](../resultats/couverture_initiale_protegee_20261115.html) ·
[Protocole avant essais](../artifacts/testing/couverture_initiale_20261115/protocol.json) ·
[Preuves et limites](../artifacts/testing/couverture_initiale_20261115/final_manifest.json).

## Résultat retenu sur janvier–mai 2025

Le cinquième essai remplace le blocage global dans la variante explicite.
**Les 20 ordres initiaux, soit 1 945 715 unités, gardent exactement leurs
fragments, dates de fabrication et disponibilités.** Les calculs des usages
reconstitués après production sont également conformes au registre physique.

| Produit / semaines complètes connues | Réel estimé | Blocage global | Variante retenue |
|---|---:|---:|---:|
| 268091 — 21 semaines | 2 409 100 | 2 104 115 ; −12,66 % | **2 420 915 ; +0,49 %** |
| 268967 — 13 semaines | 402 500 | 323 400 ; −19,65 % | 323 400 ; −19,65 % |

Pour 268091, l'erreur hebdomadaire moyenne passe de **90 377,38 à 78 377,38
unités**, soit une baisse de **13,28 %**. Le volume proche du réel ne signifie
pas que chaque semaine est reproduite : l'écart de calendrier reste important.
Les quatre fabrications supplémentaires sont de 28 800 unités le 18 avril,
129 600 le 21 avril, 28 800 le 28 avril et 129 600 le 5 mai : **316 800 unités**.
Capacités, tailles de lots et observations ne sont pas ajustées pour ce résultat.

Le service client est identique au témoin **chaque jour**, pour les deux
produits. Au 1er juin, le dépôt 1920 contient pour 268091 **1 353 585 unités
physiques**, dont **1 053 405 utilisables** et **300 180 en contrôle**. Le
supplément de 316 800 est donc entièrement en stock utilisable. Les 22 257
unités encore en transit vers les clients ne changent pas.

Il reste un léger report sur d'autres usages : pour 338928, la somme des
quantités en attente chaque jour augmente de **6 036 unités-jours**, de
7 489 381 à 7 495 417, avec le même volume finalement servi et aucune attente
résiduelle en fin de période. Pour 029313, l'augmentation est de **11,84
kilogrammes-jours**, à ne pas additionner aux unités-jours. Les baisses de
certains autres usages reconstitués viennent du calcul du résidu après la
hausse de fabrication propre ; elles ne sont pas des baisses observées chez
l'industriel.

La [contre-vérification finale](../artifacts/testing/couverture_initiale_20261115/validator/final_review_stage5.json)
accepte cette correction bornée. **La qualification globale reste refusée**
sur les cinq familles déjà identifiées : disponibilité de transfert interne,
contrat de budget Scan3, provenance des événements externes et deux contrôles
de traçabilité Scan3. La référence nominale n'est pas promue.

## Correction

Le programme expérimental refusait tout nouveau lot tant qu'un ordre initial
de conditionnement du produit restait en attente. Son placement machine
refusait également toute coexistence avec une charge initiale, même future.
Pour 268091, le dernier ordre initial se situe le 12 mai : ce blocage pouvait
donc empêcher des fabrications correspondant à des besoins non couverts.

La nouvelle option
`production_programme_policy.opening_commitment_policy = net_remaining_opening_orders_v1`
vérifie les engagements réellement présents dans le calcul des besoins nets.
Elle est compatible avec le mode `current_week_authorized_lot_multiday_v1`.
Sans option, le comportement historique est conservé pour le témoin.

- Chaque reste initial est identifié par sa ligne source, sa quantité et sa
  date de disponibilité ; il correspond à une réception ferme déjà déduite.
- Le nouveau programme choisit seulement un lot proposé pour le besoin net.
  Il ne supprime ni ne recrée les ordres initiaux.
- Les composants nécessaires à toutes les échéances initiales connues restent
  protégés, en déduisant uniquement les réceptions fermes utilisables à temps.
  Les budgets hebdomadaires sont vérifiés séparément.
- Les demandes de composants des autres usages déjà en attente et celles
  datées du jour réservent également leur matière. Une demande servie n'est
  pas déduite une seconde fois ; aucune demande réelle future n'est consultée.
- Les usages reconstitués à partir des fabrications du jour sont calculés
  après celles-ci. Ils ne sont pas présentés comme des demandes déjà connues
  dans l'aperçu ; une nouvelle autorisation concernée attend ce calcul.
- La charge initiale occupe ses créneaux datés ; le nouveau lot utilise la
  capacité restante. Toute incohérence de preuve empêche son autorisation.

Exemple : besoin de 250 unités, stock utilisable de 20 et réception initiale
ferme de 100 donnent **130 unités non couvertes avant lotification**. Une
réception tardive crée un retard, pas automatiquement un second besoin de 100.

La règle ne reconstruit pas les liens industriels entre chaque besoin et
chaque ordre. Elle vérifie la cohérence des identifiants et quantités déjà
présents dans notre MRP. La protection matière est conservatrice : le reliquat
initial entier est protégé dès sa prochaine date de travail prévue, même si
son exécution peut ensuite s'étaler. Un réapprovisionnement futur ne réduit
la réserve que s'il est déjà engagé dans le simulateur et utilisable avant
l'échéance concernée. Une promesse reste distincte d'une observation future.

## Affichage

Les courbes simulées montrent tous les jours et toutes les semaines du calcul,
y compris les semaines partielles aux bornes. Le masque des observations
réelles ne supprime plus de points simulés dans les vues principales.

Les valeurs réelles restent celles des retraits d'étuis observés, utilisés
comme estimation de production : 333362 pour 268967 et 338929 pour 268091.
Une semaine sans observation reste inconnue. Les points connus sont reliés
visuellement en pointillés au-dessus de ces intervalles signalés ; aucun point
intermédiaire n'est ajouté et aucun chiffre interpolé n'entre dans les mesures.

Le cumul simulé est complet sur la période exécutée. La somme des retraits
réels connus est explicitement **partielle** ; un palier de cette somme pendant
une semaine inconnue ne signifie pas une production réelle nulle. Les écarts
comparables restent calculés sur les mêmes semaines complètes documentées.

Le clic sur une semaine expose les ordres initiaux restants, les propositions
nettes, les réservations de machine et de composants, les lots exécutés et les
réceptions clients. « Engagement initial restant » ne signifie pas à lui seul
« besoin couvert ». Réception physique client et demande satisfaite au client
gardent leurs indicateurs distincts.

## Comparaison isolée

Les deux cas couvrent 152 jours, du 1er janvier au 1er juin 2025 inclus. Le
témoin exécuté au deuxième essai est réutilisé après preuve indépendante que
son chemin de calcul demeure inchangé. Les empreintes du code de chaque cas
restent distinctes. Les graphes viennent du même scénario portant les deux
produits ; seul le champ d'activation ci-dessus diffère. Capacités, lots,
stocks, sécurités, ordres initiaux, demande réelle et versions de prévision
restent identiques en entrée.

Les fabrications ne sont pas imposées pour passer par les observations. Les
budgets de composants restent une hypothèse d'autorisation et ne constituent
pas des ordres industriels fermes identifiés. La référence nominale n'est pas
promue par cette étude.

## Premier essai : meilleur rapprochement, mais variante refusée

Les deux calculs natifs terminent sans erreur en 498,59 secondes pour le témoin
et 497,26 secondes pour le candidat. Les 664 empreintes de code restent
identiques pendant les essais. Les capacités et les lots ne sont pas ajustés
aux points observés.

| Produit / couverture réelle commune | Réel estimé | Blocage global | Couverture locale |
|---|---:|---:|---:|
| 268967 — 13 semaines connues | 402 500 | 323 400 ; −19,65 % | 323 400 ; −19,65 % |
| 268091 — 21 semaines connues | 2 409 100 | 2 104 115 ; −12,66 % | 2 536 115 ; +5,27 % |

Pour **268091**, l'erreur hebdomadaire moyenne baisse de **90 377,38 à
74 757,29 unités, soit −17,28 %**. Cinq nouveaux lots deviennent possibles
alors que des ordres initiaux restent à terminer :

| Lancement simulé | Quantité du lot |
|---|---:|
| 20 janvier | 28 800 |
| 14 avril | 115 200 |
| 21 avril | 129 600 |
| 1er mai | 28 800 |
| 5 mai | 129 600 |
| **Total supplémentaire** | **432 000** |

Les fabrications nouvelles passent de 158 400 à 590 400 unités. Les ordres
initiaux représentent toujours **1 945 715 unités** achevées. Les deux lots
de 129 600 et 28 800 unités des 19 et 26 mai restent présents dans les deux cas.
268967 conserve ses trois lots de 107 800 unités et ses mêmes résultats.

L'amélioration de production n'est pas un gain de service observé sur cette
fenêtre : les réceptions clients simulées restent **1 475 611 unités pour
268091** et **623 081 pour 268967**. Le stock de 268091 absorbe les 432 000
unités supplémentaires :

| 268091 au dépôt 1920, fin du 1er juin | Blocage global | Couverture locale |
|---|---:|---:|
| Stock physique | 1 036 785 | 1 468 785 |
| Stock utilisable | 736 605 | 1 136 610 |
| Stock en contrôle | 300 180 | 332 175 |

Il faut donc conserver le double constat : le rythme hebdomadaire et le cumul
se rapprochent du réel estimé, **mais davantage de stock est immobilisé**.
Aucun gain économique n'est déduit de cette seule comparaison de quantités.

La contre-vérification des dates révèle une dégradation supplémentaire :
**298 982 unités d'ordres initiaux sont exécutées plus tard**, sur sept ordres
dont cinq finissent plus tard. Aucun ordre ne finit plus tôt. La dernière
tranche de 7 926 unités d'un ordre est retardée de 37 jours ; un autre ordre
de 11 300 unités subit 31 jours. Les 31 995 unités supplémentaires en contrôle
au dépôt proviennent d'un ordre initial dont les derniers fragments ont été
décalés. Les quantités sont conservées, mais cela ne protège pas leurs dates.

**Cette première variante est donc refusée.** Protéger seulement les matières
nécessaires avant la fin du nouveau lot est insuffisant : un lot terminé tôt
peut consommer du stock nécessaire à un engagement plus lointain, sans
réapprovisionnement assuré entre les deux. Le second essai ajoute une
protection de ces besoins futurs fondée sur les seules réceptions fermes
connues ; le [protocole complémentaire](../artifacts/testing/couverture_initiale_20261115/protocol_stage2.json)
fixe les critères avant calcul. Le code et les résultats du premier essai sont
conservés séparément.

Le rapport montre toutes les 152 dates simulées et les semaines partielles,
sans masquer la simulation quand le réel manque. Les semaines réelles
inconnues restent exclues des mesures comparables, jamais remplacées par zéro.

## Deuxième essai : protection future seule insuffisante

La protection des besoins initiaux futurs réduit le retard supplémentaire à
**68 582 unités**, sur un seul ordre, terminé deux jours plus tard. Elle ne
suffit donc pas au critère fixé : cette variante est également refusée.

La cause est identifiable au 21 avril : 150 000 emballages sont utilisables,
mais **121 200 sont déjà demandés par d'autres usages**. Le nouveau lot de
129 600 unités les considérait à tort comme libres. Les réceptions promises
sont toutes arrivées à temps : ce retard ne vient pas d'un aléa fournisseur.

Le [troisième protocole](../artifacts/testing/couverture_initiale_20261115/protocol_stage3.json)
ajoute cette file de besoins déjà connus aux réservations. Il reste alors
28 800 unités libres, avant les autres engagements. La règle est commune aux
composants ; aucun seuil propre à un article n'est ajouté. Le témoin du
deuxième essai ne peut être réutilisé qu'après contre-vérification de
l'absence de changement de son chemin d'exécution. Les deux versions de code
sont identifiées séparément.

## Troisième essai : la demande du jour arrive trop tard dans la décision

La réserve des demandes antérieures réduit encore le retard, mais laisse
**10 982 unités initiales retardées d'un jour**. Le troisième essai est refusé.

Au 28 avril, après la première fabrication initiale du jour, 129 036 emballages
sont utilisables. L'ordre initial du lendemain en nécessite 120 600, dont
50 000 couverts par une réception ferme : il faut conserver 70 600 unités.
Le simulateur autorise donc un lot de 57 600 unités dans les 58 436 restantes.
Mais il révèle ensuite 11 818 unités demandées ce même jour par d'autres
usages. Il ne reste que 109 618 unités pour l'ordre de 120 600 du lendemain.

Le [quatrième protocole](../artifacts/testing/couverture_initiale_20261115/protocol_stage4.json)
traite cette incohérence dans la journée : la demande datée du jour est rendue
visible avant l'allocation des matières, puis les mêmes demandes sont servies
à l'étape habituelle. Les demandes des jours futurs ne sont pas consultées.
Dans l'exemple, seules **46 618 unités** sont libres et le lot de 57 600 doit
être refusé. Cette convention appartient au modèle journalier ; elle ne
prouve pas l'ordre des événements dans les heures de la journée industrielle.

## Quatrième essai : dates préservées, raccord historique à corriger

Les 20 ordres initiaux et leurs 1 945 715 unités retrouvent exactement les
mêmes dates que le témoin. Mais l'aperçu du jour appelait aussi la clôture
historique de certains besoins reconstitués en amont, avant leurs fabrications.
Douze clôtures omettaient donc les consommations propres de la journée.
Les observations brutes ne changeaient pas ; leur utilisation devenait fausse.
Cette quatrième variante est refusée malgré la réussite du critère de dates.

Le [cinquième protocole](../artifacts/testing/couverture_initiale_20261115/protocol_stage5.json)
sépare l'aperçu sans effet de bord et la clôture après production. Oracle :
100 unités de retraits observés, moins 40 consommées avant l'aperçu puis
30 pendant la production, laissent un résidu de **30**, pas de 60. L'aperçu
ne doit publier aucune quantité résiduelle. Un besoin dont le calcul dépend
encore des fabrications du jour entraîne un refus local de nouvelle
autorisation, avec un motif explicite.

## Vérifications finales

Sur les sources finales gelées, **70 tests ciblés passent, sans exclusion**.
La contre-validation exécute 57 contrôles en mémoire avec le véritable
adaptateur, 20 contrôles d'entrées et de compatibilité, 60 contrôles de bilans,
34 de couverture, 37 de dates initiales, 17 de demandes courantes et en attente,
et 15 de clôture matière. Ce sont des contrôles distincts, pas autant de
simulations. Le candidat natif termine en 455,83 secondes ; les 664 empreintes
de source restent stables.

Les contrôles globaux et ceux de la documentation générée restent distincts
de ces preuves ciblées. Les anciens refus sont conservés. Le rapport fait
l'objet de contrôles de données et de syntaxe ; aucun navigateur n'est exécuté.

La suite scientifique reste le calendrier de 268967 et la confrontation des
capacités aux données industrielles. Cette correction n'établit pas une
cadence réelle, ne reconstruit pas les semaines inconnues et ne garantit pas
les engagements face à de nouveaux usages futurs encore inconnus.

## Vérifications historiques du premier essai

35 tests ciblés sans exclusion et 49 contrôles indépendants en mémoire
réussissent. Les entrées passent 25 contrôles indépendants ; les premières
comparaisons CSV passent 60 contrôles. Ces nombres désignent des vérifications
différentes, pas autant de simulations.

Le premier lecteur indépendant avait utilisé un constructeur incomplet de
protection de stock ; son refus est conservé avant la version corrigée. Les
vérifications de traçabilité, de capacité et d'affichage sont détaillées dans
le manifeste final avec leurs éventuels refus. Les contrôles globaux ne sont
pas assimilés aux seuls bilans locaux. Aucun navigateur n'a été exécuté.

Le rapprochement reste partiel : les retraits d'étuis sont une estimation de
production, les semaines manquantes ne sont pas reconstituées, les budgets
MRP ne prouvent pas un programme d'ordres fermes industriel, et les capacités
journalières ne sont pas toutes mesurées. La levée du blocage technique ne
suffit pas : la protection des engagements doit être vérifiée avant de retenir
la correction. Aucune reproduction industrielle complète n'est certifiée.
